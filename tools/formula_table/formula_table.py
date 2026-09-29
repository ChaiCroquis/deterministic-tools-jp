"""formula_table — 数式を data の行として持ち、行のまま評価する部品。

値の履歴(post_007 の asof_table)では「計算の仕方そのものが改正される回」を表せない。
この部品は数式を文字列の列として行に持ち、有効期間と公表時点を値の行と同じ形で付け、
**丸め方は式の隣の列で必ず指定させる**(部品は既定の丸めを持たない)。

式の表(1 行 = 1 つの式の 1 つの版):

    id             何を計算するか
    expr           式の文字列。ast の allowlist で構文を絞る(下記)
    inputs         名前ごとの入力元。`名前=種類:参照先` を `;` で並べる
                   種類 = case(呼ぶ側が渡す項目)/ value(値の表の key)/ formula(別の式の id)
    rounding       丸めの名前。**空欄は許さない**(空欄の行は評価せずに止まる)
    valid_from     有効時間の始まり(半開区間 [valid_from, valid_to))。空 = 施行日未定(決して当たらない)
    valid_to       有効時間の終わり。空 = 開いたまま
    known_from     知識時間の始まり(公表日)。空は許さない
    known_to       知識時間の終わり。空 = 最新
    known_quality  known_from の質。実値 / 仮置き(空 = 仮置き)
    priority       0 本則 / 10 経過措置 / 20 特例
    source         出典。返り値に必ず付ける

値の表(式が `value:` で引く側)は key / value / valid_from / valid_to / known_from / known_to /
known_quality / priority / source。式の版と同じ引き方(知識時間 → 有効時間 → 最高 priority)で 1 行に決まる。

allowlist(構文の段で拒否するもの): import / 属性アクセス / 添字 / 内包表記 / lambda / 代入 / and・or など。
許すのは 四則・単項マイナス・比較・条件式・登録済み関数の呼び出し・名前の参照だけ。

数は Decimal のみ。float が混ざった時点で止める(二進小数の丸め誤差を端数処理に混ぜない)。
式の中の小数リテラルは、float を経由せず元の文字列から Decimal にする。

標準ライブラリのみ(ast / decimal / json / csv / datetime / argparse)。CLI と関数の両方。
"""
from __future__ import annotations

import argparse
import ast
import csv
import json
import sys
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

FORMULA_REQUIRED = ("id", "expr", "inputs", "rounding", "valid_from", "known_from", "priority", "source")
VALUE_REQUIRED = ("key", "value", "valid_from", "known_from", "priority", "source")
PRIORITIES = {0: "本則", 10: "経過措置", 20: "特例"}
REAL, PROVISIONAL = "実値", "仮置き"
KINDS = ("case", "value", "formula")


# ---------------------------------------------------------------- 丸めの registry
# 部品は既定の丸めを持たない。表の rounding 列から引いた名前の関数だけが丸める。

def _round50(x: Decimal) -> Decimal:
    """50 銭以下を切り捨て、50 銭を超えたら切り上げる。"""
    i = x.to_integral_value(rounding=ROUND_FLOOR)
    return i if x - i <= Decimal("0.5") else i + 1


def _floor1(x: Decimal) -> Decimal:
    """1 円未満を切り捨てる。"""
    return x.to_integral_value(rounding=ROUND_FLOOR)


def _half_up(x: Decimal) -> Decimal:
    """円未満を四捨五入する(端数 0.5 は上へ。実行環境の既定の偶数丸めとは違う)。"""
    return x.to_integral_value(rounding=ROUND_HALF_UP)


def _as_is(x: Decimal) -> Decimal:
    """丸めない(端数を残したまま次の式へ渡す)。"""
    return x


ROUNDINGS = {
    "50銭以下切捨て": _round50,
    "1円未満切捨て": _floor1,
    "円未満四捨五入": _half_up,
    "丸めない": _as_is,
}

# 式の中から呼べる関数。丸めはここに入れない(丸めは表の rounding 列だけが決める)
FUNCS = {"min": min, "max": max, "abs": abs}

# 決まらないときに返す理由コード(この 8 つで全部。値は返さない)
REASONS = {
    "丸めが空欄": "式の行に rounding が書かれていない。部品は既定の丸めを持たないので、どう丸めるかを機械では選べない",
    "未登録の丸めの名前": "rounding に書かれた名前が丸めの registry に無い",
    "未登録の関数": "式が呼んでいる名前が関数の registry に無い",
    "float 混入": "入力か定数に float が混ざっている。二進小数の丸め誤差が端数処理に乗る",
    "式の版が as_of 時点で未公表": "有効時間では当たる行があるが、その行は as_of の時点ではまだ公表されていない",
    "依存が循環している": "式が直接または間接に自分自身を参照している",
    "入力が足りない": "inputs が要求している case の項目が渡されていない",
    "依存先が決まらない": "引こうとした式の版か値の行が、収録範囲の外か、同順位で複数該当した",
}

# validate() が返す不備の種類(直さない、一覧で返すだけ)
FINDINGS = ("有効期間の重なり", "丸めが空欄", "許可外の構文", "依存の循環")


class TableError(ValueError):
    """表そのものが読めない / 形が違う。評価の失敗(理由コード)とは別に扱う。"""


class Stop(Exception):
    """評価を理由コードで止める(内部用。evaluate の外では Result になる)。"""

    def __init__(self, reason: str, detail: str):
        super().__init__(reason)
        self.reason, self.detail = reason, detail


# ---------------------------------------------------------------- 構文の allowlist

_ALLOWED_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Compare, ast.IfExp, ast.Call,
    ast.Name, ast.Constant, ast.Load,
    ast.Add, ast.Sub, ast.Mult, ast.Div,
    ast.USub, ast.UAdd,
    ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq,
)
_NODE_LABEL = {
    ast.Attribute: "属性アクセス", ast.Subscript: "添字", ast.Lambda: "lambda",
    ast.ListComp: "内包表記", ast.DictComp: "内包表記", ast.SetComp: "内包表記",
    ast.GeneratorExp: "内包表記", ast.NamedExpr: "代入", ast.Starred: "アンパック",
    ast.BoolOp: "and / or", ast.List: "リスト", ast.Dict: "dict", ast.Tuple: "タプル",
    ast.JoinedStr: "f 文字列", ast.Await: "await", ast.Mod: "剰余", ast.Pow: "べき乗",
    ast.FloorDiv: "切り捨て除算", ast.Not: "not",
}


def check_syntax(expr: str) -> list[str]:
    """式が allowlist に収まっているか。収まっていれば空リスト。

    許可外の節に当たったらそこで降りるのをやめる(内側の節まで数え上げて理由が増えないように)。
    """
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        return [f"式として読めない({e.msg})"]
    bad: list[str] = []

    def scan(node: ast.AST) -> None:
        if not isinstance(node, _ALLOWED_NODES):
            bad.append(_NODE_LABEL.get(type(node), type(node).__name__))
            return
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                bad.append("関数でないものの呼び出し")
            if node.keywords:
                bad.append("キーワード引数")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            bad.append(f"数でない定数({type(node.value).__name__})")
        for child in ast.iter_child_nodes(node):
            scan(child)

    scan(tree)
    return sorted(set(bad))


def _literal(node: ast.Constant, expr: str) -> Decimal:
    """式の中の数のリテラル。float を経由せず、元の文字列から Decimal にする。"""
    if isinstance(node.value, bool):
        raise Stop("float 混入", "真偽値は数として使わない")
    text = (ast.get_source_segment(expr, node) or "").strip()
    try:
        return Decimal(text)
    except InvalidOperation as e:
        raise TableError(f"数のリテラルとして読めない: {text!r}") from e


def to_decimal(v: object, what: str) -> Decimal:
    """入力を Decimal にする。float は理由コードで止める(文字列の '1.5' は通す)。"""
    if isinstance(v, Decimal):
        return v
    if isinstance(v, bool):
        raise Stop("float 混入", f"{what} が真偽値")
    if isinstance(v, float):
        raise Stop("float 混入", f"{what} が float({v!r})。Decimal か文字列で渡す")
    if isinstance(v, int):
        return Decimal(v)
    try:
        return Decimal(str(v).strip())
    except InvalidOperation as e:
        raise TableError(f"{what} が数として読めない: {v!r}") from e


# ---------------------------------------------------------------- 行

def parse_date(s: str, what: str) -> date:
    try:
        return date.fromisoformat(str(s).strip())
    except ValueError as e:
        raise TableError(f"{what} が YYYY-MM-DD で読めない: {s!r}({e})") from e


def _opt_date(s: str, what: str) -> date | None:
    s = (s or "").strip()
    return parse_date(s, what) if s else None


def parse_inputs(spec: str, where: str) -> dict[str, tuple[str, str]]:
    """`名前=種類:参照先;…` を {名前: (種類, 参照先)} にする。"""
    out: dict[str, tuple[str, str]] = {}
    for part in (p.strip() for p in (spec or "").split(";")):
        if not part:
            continue
        if "=" not in part or ":" not in part.split("=", 1)[1]:
            raise TableError(f"{where}: inputs は『名前=種類:参照先』で書く: {part!r}")
        name, rest = part.split("=", 1)
        kind, ref = rest.split(":", 1)
        kind, ref, name = kind.strip(), ref.strip(), name.strip()
        if kind not in KINDS:
            raise TableError(f"{where}: inputs の種類は {'/'.join(KINDS)} のどれか: {kind!r}")
        if not name or not ref:
            raise TableError(f"{where}: inputs の名前か参照先が空: {part!r}")
        out[name] = (kind, ref)
    return out


@dataclass(frozen=True)
class _Timed:
    number: int
    valid_from: date | None
    valid_to: date | None
    known_from: date
    known_to: date | None
    known_quality: str
    priority: int
    source: str

    @property
    def provisional(self) -> bool:
        return self.known_quality != REAL

    def valid_on(self, on: date) -> bool:
        if self.valid_from is None:
            return False
        return self.valid_from <= on and (self.valid_to is None or on < self.valid_to)

    def known_at(self, as_of: date | None) -> bool:
        if as_of is None:
            return self.known_to is None
        return self.known_from <= as_of and (self.known_to is None or as_of < self.known_to)


@dataclass(frozen=True)
class Formula(_Timed):
    id: str = ""
    expr: str = ""
    inputs: dict[str, tuple[str, str]] = field(default_factory=dict)
    rounding: str = ""


@dataclass(frozen=True)
class ValueRow(_Timed):
    key: str = ""
    value: str = ""


@dataclass(frozen=True)
class Used:
    """返り値に付ける出典。式の版と値の行の両方をこの形で並べる。"""
    kind: str          # 式 / 値
    name: str
    row: int
    valid_from: date | None
    source: str

    def as_dict(self) -> dict:
        return {"kind": self.kind, "name": self.name, "row": self.row,
                "valid_from": self.valid_from.isoformat() if self.valid_from else None,
                "source": self.source}


@dataclass(frozen=True)
class Result:
    ok: bool
    id: str
    value: str = ""
    raw: str = ""          # 丸める前の値
    rounding: str = ""
    used: tuple[Used, ...] = ()
    reason: str = ""
    detail: str = ""

    def as_dict(self) -> dict:
        if self.ok:
            return {"ok": True, "id": self.id, "value": self.value, "raw": self.raw,
                    "rounding": self.rounding, "used": [u.as_dict() for u in self.used]}
        return {"ok": False, "id": self.id, "reason": self.reason, "detail": self.detail}


@dataclass(frozen=True)
class Finding:
    kind: str
    name: str
    rows: tuple[int, ...]
    detail: str

    def as_dict(self) -> dict:
        return {"kind": self.kind, "name": self.name, "rows": list(self.rows), "detail": self.detail}


# ---------------------------------------------------------------- 表

def _records(path: str | Path) -> list[dict]:
    p = Path(path)
    if p.suffix.lower() == ".json":
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        if not isinstance(data, list):
            raise TableError("JSON は行の配列で書く")
        return data
    with p.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _cell(rec: dict, col: str) -> str:
    v = rec.get(col, "")
    return "" if v is None else str(v).strip()


def _common(rec: dict, i: int) -> dict:
    if not _cell(rec, "known_from"):
        raise TableError(f"行 {i}: known_from が空(公表時点を空にすると、当時の知識を再現できない)")
    pr = _cell(rec, "priority")
    if not pr.lstrip("-").isdigit():
        raise TableError(f"行 {i}: priority が整数でない: {pr!r}")
    return {"number": i,
            "valid_from": _opt_date(_cell(rec, "valid_from"), f"行 {i} の valid_from"),
            "valid_to": _opt_date(_cell(rec, "valid_to"), f"行 {i} の valid_to"),
            "known_from": parse_date(_cell(rec, "known_from"), f"行 {i} の known_from"),
            "known_to": _opt_date(_cell(rec, "known_to"), f"行 {i} の known_to"),
            "known_quality": _cell(rec, "known_quality") or PROVISIONAL,
            "priority": int(pr), "source": _cell(rec, "source")}


class FormulaTable:
    """式の行の表。読んだ時点で形だけを検査する(中身の検査は validate)。"""

    def __init__(self, rows: list[Formula], origin: str = ""):
        self.rows = rows
        self.origin = origin

    def __len__(self) -> int:
        return len(self.rows)

    def ids(self) -> list[str]:
        seen: dict[str, None] = {}
        for r in self.rows:
            seen.setdefault(r.id, None)
        return list(seen)

    @classmethod
    def from_records(cls, records: list[dict], origin: str = "") -> "FormulaTable":
        if not records:
            raise TableError("表に行が 1 つも無い")
        missing = [c for c in FORMULA_REQUIRED if c not in records[0]]
        if missing:
            raise TableError(f"必要な列が無い: {'/'.join(missing)}")
        rows: list[Formula] = []
        for i, rec in enumerate(records, 1):
            if not _cell(rec, "id"):
                raise TableError(f"行 {i}: id が空")
            if not _cell(rec, "expr"):
                raise TableError(f"行 {i}: expr が空")
            rows.append(Formula(id=_cell(rec, "id"), expr=_cell(rec, "expr"),
                                inputs=parse_inputs(_cell(rec, "inputs"), f"行 {i}"),
                                rounding=_cell(rec, "rounding"), **_common(rec, i)))
        return cls(rows, str(origin))

    @classmethod
    def load(cls, path: str | Path) -> "FormulaTable":
        return cls.from_records(_records(path), str(path))


class ValueTable:
    """値の行の表。式が `value:` で引く側。引き方は式の版と同じ。"""

    def __init__(self, rows: list[ValueRow], origin: str = ""):
        self.rows = rows
        self.origin = origin

    def __len__(self) -> int:
        return len(self.rows)

    def keys(self) -> list[str]:
        seen: dict[str, None] = {}
        for r in self.rows:
            seen.setdefault(r.key, None)
        return list(seen)

    @classmethod
    def from_records(cls, records: list[dict], origin: str = "") -> "ValueTable":
        if not records:
            raise TableError("表に行が 1 つも無い")
        missing = [c for c in VALUE_REQUIRED if c not in records[0]]
        if missing:
            raise TableError(f"必要な列が無い: {'/'.join(missing)}")
        rows: list[ValueRow] = []
        for i, rec in enumerate(records, 1):
            if not _cell(rec, "key"):
                raise TableError(f"行 {i}: key が空")
            rows.append(ValueRow(key=_cell(rec, "key"), value=_cell(rec, "value"), **_common(rec, i)))
        return cls(rows, str(origin))

    @classmethod
    def load(cls, path: str | Path) -> "ValueTable":
        return cls.from_records(_records(path), str(path))

    @staticmethod
    def empty() -> "ValueTable":
        return ValueTable([], "(値の表なし)")


def _pick(rows: list, what: str, name: str, on: date, as_of: date | None):
    """知識時間 → 有効時間 → 最高 priority の 1 行。決まらなければ理由コードで止める。"""
    if not rows:
        raise Stop("依存先が決まらない", f"{what}『{name}』は表に無い")
    shadow = [r for r in rows if r.valid_on(on)]
    matched = [r for r in shadow if r.known_at(as_of)]
    if not matched:
        if as_of is not None and shadow:
            raise Stop("式の版が as_of 時点で未公表",
                       f"{what}『{name}』の行 {'/'.join(str(r.number) for r in shadow)} は "
                       f"{as_of.isoformat()} の時点で未公表"
                       + ("(公表日が仮置きの行を含む)" if any(r.provisional for r in shadow) else ""))
        raise Stop("依存先が決まらない",
                   f"{what}『{name}』は {on.isoformat()} の時点で収録範囲の外")
    top = max(r.priority for r in matched)
    best = [r for r in matched if r.priority == top]
    if len(best) > 1:
        raise Stop("依存先が決まらない",
                   f"{what}『{name}』は priority {top}({PRIORITIES.get(top, '?')})の行が "
                   f"{len(best)} 本当たった: 行 {'/'.join(str(r.number) for r in best)}")
    return best[0]


# ---------------------------------------------------------------- 評価

class _Evaluator:
    def __init__(self, ft: FormulaTable, vt: ValueTable, case: dict, on: date, as_of: date | None):
        self.ft, self.vt, self.case, self.on, self.as_of = ft, vt, case, on, as_of
        self.used: list[Used] = []
        self.raw: Decimal | None = None      # いちばん外側の式の、丸める前の値
        self.rounding = ""                   # いちばん外側の式が使った丸めの名前

    def formula(self, fid: str, path: tuple[str, ...]) -> Decimal:
        if fid in path:
            raise Stop("依存が循環している", " → ".join(path + (fid,)))
        row = _pick([r for r in self.ft.rows if r.id == fid], "式", fid, self.on, self.as_of)
        if not row.rounding:
            raise Stop("丸めが空欄", f"式『{fid}』の行 {row.number} に rounding が無い")
        if row.rounding not in ROUNDINGS:
            raise Stop("未登録の丸めの名前",
                       f"式『{fid}』の行 {row.number} の rounding『{row.rounding}』は registry に無い"
                       f"(あるのは {'/'.join(ROUNDINGS)})")
        bad = check_syntax(row.expr)
        if bad:
            raise TableError(f"式『{fid}』の行 {row.number} に許可外の構文: {'/'.join(bad)}")
        self.used.append(Used("式", fid, row.number, row.valid_from, row.source))
        env = {name: self.input(kind, ref, path + (fid,))
               for name, (kind, ref) in row.inputs.items()}
        raw = self.node(ast.parse(row.expr, mode="eval").body, row.expr, env, fid)
        if not path:
            self.raw, self.rounding = raw, row.rounding
        return ROUNDINGS[row.rounding](raw)

    def input(self, kind: str, ref: str, path: tuple[str, ...]) -> Decimal:
        if kind == "case":
            if ref not in self.case:
                raise Stop("入力が足りない",
                           f"case に『{ref}』が無い(渡されたのは {'/'.join(sorted(self.case)) or '(空)'})")
            return to_decimal(self.case[ref], f"case の『{ref}』")
        if kind == "value":
            row = _pick([r for r in self.vt.rows if r.key == ref], "値", ref, self.on, self.as_of)
            self.used.append(Used("値", ref, row.number, row.valid_from, row.source))
            return to_decimal(row.value, f"値の表の『{ref}』")
        return self.formula(ref, path)

    def node(self, n: ast.AST, expr: str, env: dict[str, Decimal], fid: str) -> Decimal:
        if isinstance(n, ast.Constant):
            return _literal(n, expr)
        if isinstance(n, ast.Name):
            if n.id not in env:
                raise Stop("入力が足りない", f"式『{fid}』の名前『{n.id}』が inputs に無い")
            return env[n.id]
        if isinstance(n, ast.UnaryOp):
            v = self.node(n.operand, expr, env, fid)
            return -v if isinstance(n.op, ast.USub) else v
        if isinstance(n, ast.BinOp):
            a, b = self.node(n.left, expr, env, fid), self.node(n.right, expr, env, fid)
            if isinstance(n.op, ast.Add):
                return a + b
            if isinstance(n.op, ast.Sub):
                return a - b
            if isinstance(n.op, ast.Mult):
                return a * b
            if b == 0:
                raise Stop("依存先が決まらない", f"式『{fid}』で 0 による除算")
            return a / b
        if isinstance(n, ast.Compare):
            left = self.node(n.left, expr, env, fid)
            for op, right_node in zip(n.ops, n.comparators):
                right = self.node(right_node, expr, env, fid)
                if not _compare(op, left, right):
                    return Decimal(0)
                left = right
            return Decimal(1)
        if isinstance(n, ast.IfExp):
            cond = self.node(n.test, expr, env, fid)
            return self.node(n.body if cond != 0 else n.orelse, expr, env, fid)
        if isinstance(n, ast.Call):
            fn = n.func.id if isinstance(n.func, ast.Name) else "?"
            if fn not in FUNCS:
                raise Stop("未登録の関数",
                           f"式『{fid}』が呼んでいる『{fn}』は registry に無い(あるのは {'/'.join(FUNCS)})")
            return FUNCS[fn](*[self.node(a, expr, env, fid) for a in n.args])
        raise TableError(f"式『{fid}』に許可外の構文: {type(n).__name__}")


def _compare(op: ast.cmpop, a: Decimal, b: Decimal) -> bool:
    if isinstance(op, ast.Lt):
        return a < b
    if isinstance(op, ast.LtE):
        return a <= b
    if isinstance(op, ast.Gt):
        return a > b
    if isinstance(op, ast.GtE):
        return a >= b
    if isinstance(op, ast.Eq):
        return a == b
    return a != b


def evaluate(ft: FormulaTable, fid: str, case: dict, on: date,
             as_of: date | None = None, values: ValueTable | None = None) -> Result:
    """式 1 本を評価する。決まらないときは理由コードを返す(値は返さない)。

    on     = 式の版と値の版を引く日付(有効時間)
    as_of  = その時点の知識で引く(省略 = いまの知識)
    """
    ev = _Evaluator(ft, values or ValueTable.empty(), case, on, as_of)
    try:
        v = ev.formula(fid, ())
    except Stop as s:
        return Result(False, fid, reason=s.reason, detail=s.detail, used=tuple(ev.used))
    return Result(True, fid, value=str(v), raw=str(ev.raw), rounding=ev.rounding, used=tuple(ev.used))


def validate(ft: FormulaTable) -> list[Finding]:
    """式の表そのものの検査。直さない、一覧で返すだけ。"""
    out: list[Finding] = []
    for r in ft.rows:
        if not r.rounding:
            out.append(Finding("丸めが空欄", r.id, (r.number,), "rounding 列が空(評価せずに止まる行)"))
        bad = check_syntax(r.expr)
        if bad:
            out.append(Finding("許可外の構文", r.id, (r.number,), "/".join(bad)))
    groups: dict[tuple[str, int], list[Formula]] = {}
    for r in ft.rows:
        if r.valid_from is None:
            continue   # 施行日未定の行は期間を持たないので、重なりに数えない
        groups.setdefault((r.id, r.priority), []).append(r)
    for (fid, pr), rs in groups.items():
        rs = sorted(rs, key=lambda r: (r.valid_from, r.number))
        for i, a in enumerate(rs):
            for b in rs[i + 1:]:
                if _overlap(a.valid_from, a.valid_to, b.valid_from, b.valid_to) and \
                        _overlap(a.known_from, a.known_to, b.known_from, b.known_to):
                    out.append(Finding("有効期間の重なり", fid, (a.number, b.number),
                                       f"priority {pr}({PRIORITIES.get(pr, '?')})で期間が重なる"))
    for fid in ft.ids():
        cyc = _cycle_from(ft, fid)
        if cyc:
            out.append(Finding("依存の循環", fid,
                               tuple(r.number for r in ft.rows if r.id == fid), " → ".join(cyc)))
    return out


def _cycle_from(ft: FormulaTable, start: str) -> list[str]:
    """start から辿れる循環を 1 つ返す(期間を見ずに、表に書かれた依存の形だけを見る)。"""
    stack: list[tuple[str, tuple[str, ...]]] = [(start, ())]
    while stack:
        fid, path = stack.pop()
        if fid in path:
            return list(path[path.index(fid):] + (fid,))
        if len(path) > len(ft.ids()) + 1:
            continue
        for r in ft.rows:
            if r.id != fid:
                continue
            for kind, ref in r.inputs.values():
                if kind == "formula":
                    stack.append((ref, path + (fid,)))
    return []


def _overlap(af: date, at: date | None, bf: date, bt: date | None) -> bool:
    """半開区間 [af, at) と [bf, bt) が重なるか。None = 開いたまま。"""
    if at is not None and bf >= at:
        return False
    if bt is not None and af >= bt:
        return False
    return True


# ---------------------------------------------------------------- CLI

def _cli_eval(args) -> int:
    ft = FormulaTable.load(args.table)
    vt = ValueTable.load(args.values) if args.values else None
    case: dict[str, str] = {}
    for item in args.input or []:
        if "=" not in item:
            raise TableError(f"--input は 名前=値 で書く: {item!r}")
        k, v = item.split("=", 1)
        case[k.strip()] = v.strip()
    res = evaluate(ft, args.id, case, parse_date(args.on, "--on"),
                   parse_date(args.as_of, "--as-of") if args.as_of else None, vt)
    print(json.dumps(res.as_dict(), ensure_ascii=False))
    return 0 if res.ok else 3


def _cli_validate(args) -> int:
    ft = FormulaTable.load(args.table)
    found = validate(ft)
    print(json.dumps({"ok": not found, "rows": len(ft), "ids": len(ft.ids()),
                      "findings": [f.as_dict() for f in found]}, ensure_ascii=False))
    return 3 if found else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="数式を表の行として持ち、丸めを隣の列で指定して評価する")
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("eval", help="式 1 本を評価する")
    e.add_argument("table")
    e.add_argument("--id", required=True)
    e.add_argument("--input", action="append", metavar="名前=値", help="case の項目。繰り返せる")
    e.add_argument("--values", metavar="値の表", help="value: で引く表")
    e.add_argument("--on", required=True, metavar="YYYY-MM-DD", help="式の版・値の版を引く日付")
    e.add_argument("--as-of", metavar="YYYY-MM-DD", help="この時点の知識で引く(省略 = いまの知識)")
    e.set_defaults(func=_cli_eval)
    v = sub.add_parser("validate", help="式の表そのものを検査する")
    v.add_argument("table")
    v.set_defaults(func=_cli_validate)
    args = p.parse_args(argv)
    try:
        return args.func(args)
    except TableError as ex:
        print(json.dumps({"ok": False, "error": str(ex)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except OSError as ex:
        print(json.dumps({"ok": False, "error": str(ex)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
