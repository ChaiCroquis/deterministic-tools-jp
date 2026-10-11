"""variant_fan — 宣言された選び方の軸を全通り組み合わせて、同じ式から出る答えが何通りになるかを数える。

同じ式・同じ金額でも、**書かれていない選び方が 1 つ増えるごとに、どれももっともらしい答えが掛け算で増える**。
丸めの名前、丸めを掛ける段、基準日の取り方、区分の選び方、期間の切り方、入力の桁の扱い。
この部品は **宣言された軸の候補だけ** を組み合わせて全通り評価し、相異なる値ごとに「その値を出した軸の
組み合わせ」を verbatim で並べ、件数と分母の内訳(軸ごとの候補数と組み合わせ総数)を必ず一緒に出す。
**どれが正しいかは選ばない。**

持たせていないものが規律になっている。

  - **軸を自然文から推測して足さない**(軸表に無い軸は扇に入らない。出力には「扇は宣言された軸の
    範囲内」と分母の内訳が必ず付く)
  - **正解を選ぶ引数を持たない**(どの組み合わせが正しいかを返す経路が無い)
  - **平均・中央値・最頻値を返さない。多数決で 1 点に潰さない**(集約で扇を代表値にする経路が無い)。
    扇の幅は観測された最小値と最大値をそのまま併記する
  - **許容誤差の引数を持たない**(値が近いことを同じことにしない。相異なる値はバイト列の一致でだけ束ねる)
  - **宣言された既定の組み合わせには「宣言された既定」の印だけを付ける**(正しい・推奨と書く経路が無い)
  - **どの軸がどれだけ効いたかの寄与率・重要度・感度を出さない**(軸ごとの分解の経路が無い)
  - **扇の通り数を単独で返さない**(相異なる値の件数・組み合わせ総数・軸ごとの候補数を必ず併記)
  - **既定の丸めを持たない**(丸めは式表の rounding 列と軸表の候補からだけ掛かる)
  - **入力表を書き換えず、式も軸も生成しない**(直す・補う経路が無い)
  - **出典の欄が空の候補がある軸は、扇に入れずに止まる**(誰の宣言由来かを辿れない候補を台帳に入れない)
  - **組み合わせ数が軸表の宣言上限を超えたら止まる**(黙って間引いたり標本にしたりしない)

入力は 2 つ。

  式表(post_008 formula_table と同じ形)
    id / expr / rounding / valid_from / valid_to / known_from / known_to / source

  軸表
    axis    軸の名前。**式表のどこにこの名前を書いたかで、どの位置に効くかが決まる**
    choice  候補の値(1 行 1 候補)
    source  その候補の出典(記事か README のファイル名 + 行番号)。空欄は止まる
    default 宣言された既定の候補なら印を書く(軸ごとに 1 つまで)
    limit   組み合わせ数の上限(全行で同じ値)

軸が効く位置は 3 つで、**軸の名前をどこに書いたか** だけで決まる(意味からは決めない)。

    式の中の名前      expr の中にその名前が現れる     → 候補が数として束になる
    丸めの列          rounding の欄がその名前と一致    → 候補が丸めの名前になる
    基準日の引数      on / as_of にその名前を渡す      → 候補が日付になり、式の版の引き当てに効く

数えたことは「宣言された軸の組み合わせから出る値が何通りあるか」までで、どの値が制度として正しいかも、
実務でどの選び方が使われているかも、宣言されていない軸がほかに無いかも判定しない。
標準ライブラリのみ(decimal / itertools / ast / json / csv / hashlib / pathlib / datetime / argparse)。
"""
from __future__ import annotations

import argparse
import ast
import csv
import datetime
import hashlib
import itertools
import json
import platform
import sys
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

FORMULA_COLUMNS = ("id", "expr", "rounding", "valid_from", "valid_to", "known_from", "known_to", "source")
AXIS_COLUMNS = ("axis", "choice", "source", "default", "limit")

# 軸が効く位置(この 3 つで全部。名前をどこに書いたかだけで決まる)
POSITIONS = ("式の中の名前", "丸めの列", "基準日の引数")

# 止まる理由コード(この 9 つで全部)。止まったときは値を 1 件も返さない
STOP_REASONS = ("出典の欄が空", "候補が 1 件以下", "軸名の重複", "丸めの名前が空欄 or 未登録",
                "式の id が式表に無い or 2 件以上", "有効期間が基準日の候補を含まない",
                "float の混入", "組み合わせ数が上限超え", "2 回目の判定部分がバイト列として不一致")

# 判定部分に入る欄(この順で固定)。時刻・絶対パス・ホスト名は入れない
JUDGEMENT_KEYS = ("値", "件数", "印", "出した組み合わせ")
DEFAULT_MARK = "宣言された既定"


class TableError(ValueError):
    """表そのものが読めない / 形が違う(理由コードにせず終了コード 2 で返す = 表を書く側の話)。"""


class Stop(Exception):
    """理由コードで止める(内部用)。"""

    def __init__(self, reason: str, detail: str):
        super().__init__(reason)
        self.reason, self.detail = reason, detail


# ---------------------------------------------------------------- 丸めの registry
# 部品は既定の丸めを持たない。式表の rounding 列と軸表の候補から引いた名前の関数だけが丸める。

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


ROUNDINGS = {"50銭以下切捨て": _round50, "1円未満切捨て": _floor1,
             "円未満四捨五入": _half_up, "丸めない": _as_is}

# 式の中から呼べる関数。丸めはここに入れない
FUNCS = {"min": min, "max": max, "abs": abs}


# ---------------------------------------------------------------- 数
def to_decimal(v: object, what: str) -> Decimal:
    """Decimal にする。float は理由コードで止める(文字列の '1.5' は通す)。"""
    if isinstance(v, Decimal):
        return _finite(v, what, v)
    if isinstance(v, bool):
        raise Stop(STOP_REASONS[6], f"{what} が真偽値")
    if isinstance(v, float):
        raise Stop(STOP_REASONS[6], f"{what} が float({v!r})。Decimal か文字列で渡す")
    if isinstance(v, int):
        return Decimal(v)
    s = str(v).strip()
    if not s.isascii():            # 全角数字は数として読まない(勝手に半角へ寄せない)
        raise TableError(f"{what} が数として読めない(半角でない字を含む): {v!r}")
    try:
        d = Decimal(s)
    except InvalidOperation as e:
        raise TableError(f"{what} が数として読めない: {v!r}") from e
    return _finite(d, what, v)


def _finite(d: Decimal, what: str, v: object) -> Decimal:
    if not d.is_finite():
        raise TableError(f"{what} が数として読めない(有限の数でない): {v!r}")
    return d


def _as_date(s: str, what: str) -> date:
    try:
        return date.fromisoformat(s.strip())
    except ValueError as e:
        raise TableError(f"{what} が日付として読めない: {s!r}") from e


# ---------------------------------------------------------------- 式の allowlist
_ALLOWED = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Compare, ast.IfExp, ast.Call,
            ast.Name, ast.Constant, ast.Load,
            ast.Add, ast.Sub, ast.Mult, ast.Div, ast.USub, ast.UAdd,
            ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq)
_LABEL = {ast.Attribute: "属性アクセス", ast.Subscript: "添字", ast.Lambda: "lambda",
          ast.ListComp: "内包表記", ast.DictComp: "内包表記", ast.SetComp: "内包表記",
          ast.GeneratorExp: "内包表記", ast.NamedExpr: "代入", ast.Starred: "アンパック",
          ast.BoolOp: "and / or", ast.List: "リスト", ast.Dict: "dict", ast.Tuple: "タプル",
          ast.JoinedStr: "f 文字列", ast.Mod: "剰余", ast.Pow: "べき乗",
          ast.FloorDiv: "切り捨て除算", ast.Not: "not"}


def check_syntax(expr: str) -> list[str]:
    """式が allowlist に収まっているか。収まっていれば空リスト。"""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        return [f"式として読めない({e.msg})"]
    bad: list[str] = []

    def scan(node: ast.AST) -> None:
        if not isinstance(node, _ALLOWED):
            bad.append(_LABEL.get(type(node), type(node).__name__))
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


def names_in(expr: str) -> set[str]:
    """式の中に現れる名前(軸がどの位置に効くかを決めるのに使う)。"""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise TableError(f"式として読めない: {expr!r}({e.msg})") from e
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}


def _literal(node: ast.Constant, expr: str) -> Decimal:
    """式の中の数のリテラル。float を経由せず元の文字列から Decimal にする。"""
    if isinstance(node.value, bool):
        raise Stop(STOP_REASONS[6], "真偽値は数として使わない")
    text = (ast.get_source_segment(expr, node) or "").strip()
    try:
        return Decimal(text)
    except InvalidOperation as e:
        raise TableError(f"数のリテラルとして読めない: {text!r}") from e


_CMP = {ast.Lt: lambda a, b: a < b, ast.LtE: lambda a, b: a <= b, ast.Gt: lambda a, b: a > b,
        ast.GtE: lambda a, b: a >= b, ast.Eq: lambda a, b: a == b, ast.NotEq: lambda a, b: a != b}


def _walk(node: ast.AST, expr: str, value_of) -> object:
    if isinstance(node, ast.Constant):
        return _literal(node, expr)
    if isinstance(node, ast.Name):
        return value_of(node.id)
    if isinstance(node, ast.UnaryOp):
        v = _walk(node.operand, expr, value_of)
        return -v if isinstance(node.op, ast.USub) else v
    if isinstance(node, ast.BinOp):
        a, b = _walk(node.left, expr, value_of), _walk(node.right, expr, value_of)
        if isinstance(node.op, ast.Add):
            return a + b
        if isinstance(node.op, ast.Sub):
            return a - b
        if isinstance(node.op, ast.Mult):
            return a * b
        if b == 0:
            raise TableError(f"0 で割る式: {expr!r}")
        return a / b
    if isinstance(node, ast.Compare):
        left = _walk(node.left, expr, value_of)
        for op, right_node in zip(node.ops, node.comparators):
            right = _walk(right_node, expr, value_of)
            if not _CMP[type(op)](left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.IfExp):
        return _walk(node.body if _walk(node.test, expr, value_of) else node.orelse, expr, value_of)
    if isinstance(node, ast.Call):
        name = node.func.id if isinstance(node.func, ast.Name) else ""
        if name not in FUNCS:
            raise TableError(f"関数の registry に無い名前: {name!r}")
        return FUNCS[name](*[_walk(a, expr, value_of) for a in node.args])
    raise TableError(f"許可外の構文: {type(node).__name__}")


# ---------------------------------------------------------------- 表
@dataclass(frozen=True)
class Pending:
    reason: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"reason": self.reason, "detail": self.detail}


@dataclass(frozen=True)
class FormulaRow:
    id: str
    expr: str
    rounding: str
    valid_from: str
    valid_to: str
    known_from: str
    known_to: str
    source: str
    number: int


@dataclass(frozen=True)
class Axis:
    name: str
    choices: tuple[str, ...]
    sources: tuple[str, ...]
    default: str
    limit: int
    number: int


def _records(path: str | Path, columns: tuple[str, ...], what: str) -> list[dict[str, str]]:
    p = Path(path)
    if not p.exists():
        raise TableError(f"{what} が無い: {p}")
    reader = csv.DictReader(p.read_text(encoding="utf-8-sig").splitlines())
    missing = [c for c in columns if c not in (reader.fieldnames or ())]
    if missing:
        raise TableError(f"{what} に " + " / ".join(missing) + " の列が無い")
    return [{k: (r.get(k) or "").strip() for k in columns} for r in reader]


@dataclass
class Spec:
    """式表と軸表。読んだ時点で分かる不備は pending に入れ、1 件でもあれば扇を数えない。"""
    formulas: tuple[FormulaRow, ...]
    axes: tuple[Axis, ...]
    limit: int
    pending: tuple[Pending, ...] = ()
    formula_path: str = ""
    axis_path: str = ""

    @classmethod
    def load(cls, formula_table: str | Path, axis_table: str | Path) -> "Spec":
        rows = [FormulaRow(number=i, **r)
                for i, r in enumerate(_records(formula_table, FORMULA_COLUMNS, "式表"), start=2)]
        if not rows:
            raise TableError("式表に行が無い")
        for r in rows:
            if not r.id or not r.expr:
                raise TableError(f"式表 行 {r.number}: id と expr は空欄にできない")
            if not r.known_from:
                raise TableError(f"式表 行 {r.number}: known_from(公表時点)は空欄にできない")
            bad = check_syntax(r.expr)
            if bad:
                raise TableError(f"式表 行 {r.number} の式が allowlist の外: " + " / ".join(bad))

        pending: list[Pending] = []
        order: list[str] = []
        choices: dict[str, list[str]] = {}
        sources: dict[str, list[str]] = {}
        defaults: dict[str, list[str]] = {}
        limits: set[str] = set()
        lineno: dict[str, int] = {}
        for i, a in enumerate(_records(axis_table, AXIS_COLUMNS, "軸表"), start=2):
            name = a["axis"]
            if not name or not a["choice"]:
                raise TableError(f"軸表 行 {i}: axis と choice は空欄にできない")
            if name not in choices:
                order.append(name)
                choices[name], sources[name], defaults[name] = [], [], []
                lineno[name] = i
            elif a["choice"] in choices[name]:
                pending.append(Pending(STOP_REASONS[2],
                                       f"軸 {name}: 候補 {a['choice']} が行 {lineno[name]} 以降と行 {i} で重複"))
            choices[name].append(a["choice"])
            sources[name].append(a["source"])
            if a["default"]:
                defaults[name].append(a["choice"])
            if not a["source"]:
                pending.append(Pending(STOP_REASONS[0], f"軸表 行 {i}({name} / {a['choice']})"))
            limits.add(a["limit"])
        if not order:
            raise TableError("軸表に行が無い")
        if len(limits) != 1:
            raise TableError("軸表の limit(組み合わせ数の上限)が行ごとに違う: " + " / ".join(sorted(limits)))
        limit_text = limits.pop()
        if not limit_text.isdigit() or int(limit_text) < 1:
            raise TableError(f"軸表の limit が 1 以上の整数でない: {limit_text!r}")
        axes: list[Axis] = []
        for name in order:
            if len(defaults[name]) > 1:
                raise TableError(f"軸 {name} に『宣言された既定』の印が {len(defaults[name])} 件ある(1 つまで)")
            if len(choices[name]) <= 1:
                pending.append(Pending(STOP_REASONS[1], f"軸 {name}: 候補 {len(choices[name])} 件"))
            axes.append(Axis(name=name, choices=tuple(choices[name]), sources=tuple(sources[name]),
                             default=(defaults[name][0] if defaults[name] else ""),
                             limit=int(limit_text), number=lineno[name]))
        spec = cls(formulas=tuple(rows), axes=tuple(axes), limit=int(limit_text),
                   pending=tuple(pending), formula_path=str(Path(formula_table).resolve()),
                   axis_path=str(Path(axis_table).resolve()))
        spec.pending = tuple(pending) + spec._rounding_pending()
        return spec

    # -------------------------------------------------- 軸がどの位置に効くか
    def axis(self, name: str) -> Axis | None:
        return next((a for a in self.axes if a.name == name), None)

    def positions(self, on: str = "", as_of: str = "") -> dict[str, list[str]]:
        """軸の名前をどこに書いたかだけで、効く位置を決める(意味からは決めない)。"""
        in_expr: set[str] = set()
        for r in self.formulas:
            in_expr |= names_in(r.expr)
        in_round = {r.rounding for r in self.formulas}
        out: dict[str, list[str]] = {}
        for a in self.axes:
            where = []
            if a.name in in_expr:
                where.append(POSITIONS[0])
            if a.name in in_round:
                where.append(POSITIONS[1])
            if a.name in (on, as_of):
                where.append(POSITIONS[2])
            out[a.name] = where
        return out

    def _rounding_pending(self) -> tuple[Pending, ...]:
        """丸めの名前は registry か軸の名前のどちらか。軸なら候補が全部 registry に在ること。"""
        out: list[Pending] = []
        for r in self.formulas:
            if r.rounding in ROUNDINGS:
                continue
            a = self.axis(r.rounding)
            if a is None:
                out.append(Pending(STOP_REASONS[3],
                                   f"式表 行 {r.number}({r.id}): rounding = "
                                   f"{r.rounding or '空欄'}(丸めの registry にも軸表にも無い)"))
                continue
            for c in a.choices:
                if c not in ROUNDINGS:
                    out.append(Pending(STOP_REASONS[3],
                                       f"軸 {a.name} の候補 {c}(丸めの registry に無い)"))
        return tuple(out)

    def total_combinations(self) -> int:
        n = 1
        for a in self.axes:
            n *= len(a.choices)
        return n

    def choice_counts(self) -> dict[str, int]:
        return {a.name: len(a.choices) for a in self.axes}


# ---------------------------------------------------------------- 1 通りの評価
@dataclass(frozen=True)
class Combo:
    choices: tuple[tuple[str, str], ...]     # (軸の名前, 候補)を軸表の順に。verbatim
    value: str
    raw: str
    is_default: bool

    def verbatim(self) -> list[dict[str, str]]:
        return [{"軸": k, "候補": v} for k, v in self.choices]


def _pick(spec: Spec, fid: str, on: date, as_of: date) -> FormulaRow:
    """知識時間 → 有効時間 で 1 行に決める。0 件でも 2 件以上でも止まる。"""
    rows = [r for r in spec.formulas if r.id == fid]
    if not rows:
        raise Stop(STOP_REASONS[4], f"式の id {fid} が式表に無い")
    known = [r for r in rows
             if _as_date(r.known_from, f"式表 行 {r.number} の known_from") <= as_of
             and (not r.known_to or as_of < _as_date(r.known_to, f"式表 行 {r.number} の known_to"))]
    hit = [r for r in known
           if r.valid_from
           and _as_date(r.valid_from, f"式表 行 {r.number} の valid_from") <= on
           and (not r.valid_to or on < _as_date(r.valid_to, f"式表 行 {r.number} の valid_to"))]
    if len(hit) > 1:
        raise Stop(STOP_REASONS[4],
                   f"式の id {fid} が基準日 {on.isoformat()} に {len(hit)} 件該当"
                   f"(式表 行 {' / 行 '.join(str(r.number) for r in hit)})")
    if not hit:
        raise Stop(STOP_REASONS[5], f"式の id {fid}: 基準日 {on.isoformat()}"
                                    f"(公表時点 {as_of.isoformat()})に当たる版が式表に無い")
    return hit[0]


def _evaluate(spec: Spec, fid: str, inputs: dict[str, object], bind: dict[str, str],
              on: date, as_of: date, stack: frozenset[str]) -> tuple[Decimal, Decimal]:
    """1 つの組み合わせで式を評価する。返りは(丸める前, 丸めた後)。"""
    if fid in stack:
        raise TableError(f"式 {fid} の依存が循環している")
    row = _pick(spec, fid, on, as_of)
    name = row.rounding if row.rounding in ROUNDINGS else bind.get(row.rounding, "")
    if name not in ROUNDINGS:
        raise Stop(STOP_REASONS[3], f"式 {fid} の丸めの名前が決まらない: {row.rounding or '空欄'}")

    def value_of(n: str) -> Decimal:
        if n in bind:
            return to_decimal(bind[n], f"軸 {n} の候補")
        if any(r.id == n for r in spec.formulas):
            return _evaluate(spec, n, inputs, bind, on, as_of, stack | {fid})[1]
        if n in inputs:
            return to_decimal(inputs[n], f"入力 {n}")
        raise TableError(f"式 {fid} の名前 {n} は、軸・式の id・入力のどれにも無い")

    raw = _walk(ast.parse(row.expr, mode="eval").body, row.expr, value_of)
    if not isinstance(raw, Decimal):
        raise TableError(f"式 {fid} の値が数にならない(比較だけの式)")
    return raw, ROUNDINGS[name](raw)


# ---------------------------------------------------------------- 扇
@dataclass(frozen=True)
class Report:
    ok: bool
    pending: tuple[Pending, ...]
    total: int


@dataclass
class Fan:
    report: Report
    spec: Spec
    target: str
    combos: tuple[Combo, ...]
    on: str = ""
    as_of: str = ""
    read_at: str = ""
    host: str = ""

    def _guard(self) -> None:
        if not self.report.ok:
            raise RuntimeError("止まっているので扇は無い。report.pending の理由コードを見る")

    def distinct(self) -> list[tuple[str, list[Combo]]]:
        """相異なる値。束ねるのはバイト列が一致するときだけ(許容誤差を持たない)。順は値の昇順。"""
        self._guard()
        groups: dict[str, list[Combo]] = {}
        for c in self.combos:
            groups.setdefault(c.value, []).append(c)
        return sorted(groups.items(), key=lambda kv: (Decimal(kv[0]), kv[0]))

    def counts(self) -> dict[str, object]:
        """扇の通り数を単独では返さない。件数・組み合わせ総数・軸ごとの候補数が必ず付く。"""
        d = self.distinct()
        counts = self.spec.choice_counts()
        return {"相異なる値の件数": len(d),
                "組み合わせ総数": self.report.total,
                "軸ごとの候補数": counts,
                "分母に含めたもの": "組み合わせ総数 = 軸ごとの候補数の積 "
                                    + " × ".join(f"{k} {v}" for k, v in counts.items())
                                    + f" = {self.report.total}(宣言された軸だけを数えた分母)",
                "扇は宣言された軸の範囲内": f"軸表にある {len(counts)} 本の軸の候補だけを組み合わせた。"
                                            "軸表に無い軸を自然文から足す経路は無く、"
                                            "宣言されていない軸がほかに在るかは数えていない"}

    def width(self) -> dict[str, str]:
        """扇の幅は観測された最小と最大をそのまま。平均・中央値・最頻値は返さない。"""
        d = self.distinct()
        return {"最小": d[0][0], "最大": d[-1][0]}

    def table(self) -> list[dict[str, object]]:
        """相異なる値ごとに、その値を出した軸の組み合わせを verbatim で並べる。"""
        out: list[dict[str, object]] = []
        for value, combos in self.distinct():
            out.append({"値": value, "件数": len(combos),
                        "印": DEFAULT_MARK if any(c.is_default for c in combos) else "",
                        "出した組み合わせ": [c.verbatim() for c in combos]})
        return out

    def read_conditions(self) -> list[dict[str, str]]:
        """判定部分に入れない欄(絶対パス・時刻・ホスト名)。sha256 の対象にもしない。"""
        self._guard()
        return [{"読んだ式表の絶対パス": self.spec.formula_path,
                 "読んだ軸表の絶対パス": self.spec.axis_path,
                 "読んだ時刻": self.read_at, "ホスト名": self.host}]

    def judgement_bytes(self) -> bytes:
        payload = {"式の id": self.target, "基準日": self.on, "公表時点": self.as_of,
                   "組み合わせ総数": self.report.total, "値": self.table()}
        return json.dumps(payload, ensure_ascii=False, sort_keys=False,
                          separators=(",", ":")).encode("utf-8") + b"\n"

    def sha256(self) -> str:
        return hashlib.sha256(self.judgement_bytes()).hexdigest()


def _date_from(text: str, bind: dict[str, str], what: str) -> date:
    return _as_date(bind[text] if text in bind else text, what)


def fan(spec: Spec, target: str, inputs: dict[str, object], on: str, as_of: str) -> Fan:
    """宣言された軸の候補を全通り組み合わせて評価する。止まったら 1 件も返さない。"""
    read_at = datetime.datetime.now().isoformat(timespec="seconds")
    host = platform.node()
    total = spec.total_combinations()

    def stopped(pending: tuple[Pending, ...]) -> Fan:
        return Fan(Report(False, pending, total), spec, target, (), on, as_of, read_at, host)

    if spec.pending:
        return stopped(spec.pending)
    if total > spec.limit:
        return stopped((Pending(STOP_REASONS[7], f"組み合わせ数 {total} > 軸表の上限 {spec.limit}"
                                                 "(黙って間引いたり標本にしたりしない)"),))

    names = [a.name for a in spec.axes]
    default_combo = tuple(a.default for a in spec.axes) if all(a.default for a in spec.axes) else None
    combos: list[Combo] = []
    stops: list[Pending] = []
    for picked in itertools.product(*[a.choices for a in spec.axes]):
        bind = dict(zip(names, picked))
        try:
            d_on = _date_from(on, bind, "基準日")
            d_as_of = _date_from(as_of, bind, "公表時点")
            raw, value = _evaluate(spec, target, inputs, bind, d_on, d_as_of, frozenset())
        except Stop as e:
            p = Pending(e.reason, e.detail)
            if p not in stops:
                stops.append(p)
            continue
        combos.append(Combo(choices=tuple(zip(names, picked)), value=str(value), raw=str(raw),
                            is_default=picked == default_combo))
    if stops:
        return stopped(tuple(stops))
    return Fan(Report(True, (), total), spec, target, tuple(combos), on, as_of, read_at, host)


def verify(spec: Spec, target: str, inputs: dict[str, object], on: str, as_of: str) -> dict[str, object]:
    """2 回数えて判定部分の sha256 を突き合わせる。一致しなければ観測としてそのまま返す。"""
    first = fan(spec, target, inputs, on, as_of)
    if not first.report.ok:
        return {"ok": False, "stage": "表", "pending": [p.as_dict() for p in first.report.pending]}
    second = fan(spec, target, inputs, on, as_of)
    same = first.sha256() == second.sha256()
    out: dict[str, object] = {"ok": same, "一致": same, "数えた回数": 2,
                              "sha256": first.sha256(), "2 回目の sha256": second.sha256()}
    if not same:
        diffs = []
        for a, b in zip(first.table(), second.table()):
            differed = {k: [a[k], b[k]] for k in JUDGEMENT_KEYS if a[k] != b[k]}
            if differed:
                diffs.append({"値": a["値"], "違った欄": differed})
        out["観測"] = "同じ入力から 2 回数えて違う答えが出た(平均も多数決もしない)"
        out["不一致の内訳"] = diffs
        out["pending"] = [Pending(STOP_REASONS[8], f"不一致の行 {len(diffs)} 件").as_dict()]
    return out


# ---------------------------------------------------------------- ひな型
FORMULA_TEMPLATE = [
    list(FORMULA_COLUMNS),
    ["日額", "報酬月額 / 期間の切り方", "入力の桁の扱い", "2025-04-01", "", "2025-03-01", "",
     "合成の端数処理メモ(架空)L1"],
    ["対象額", "日額 * 出勤日数", "丸めを掛ける段", "2025-04-01", "2026-04-01", "2025-03-01", "",
     "合成の端数処理メモ(架空)L2"],
    ["対象額", "日額 * 出勤日数 * 102 / 100", "丸めを掛ける段", "2026-04-01", "", "2026-02-01", "",
     "合成の改定メモ(架空)L3"],
    ["負担額", "対象額 * 区分の選び方 / 200", "丸めの名前", "2025-04-01", "", "2025-03-01", "",
     "合成の端数処理メモ(架空)L4"],
]
AXIS_TEMPLATE = [
    list(AXIS_COLUMNS),
    ["基準日の取り方", "2026-04-01", "合成の宣言(架空)L10", "1", "200"],
    ["基準日の取り方", "2026-03-31", "合成の宣言(架空)L11", "", "200"],
    ["区分の選び方", "8.13", "合成の宣言(架空)L12", "1", "200"],
    ["区分の選び方", "9.98", "合成の宣言(架空)L13", "", "200"],
    ["期間の切り方", "30", "合成の宣言(架空)L14", "1", "200"],
    ["期間の切り方", "31", "合成の宣言(架空)L15", "", "200"],
    ["丸めの名前", "50銭以下切捨て", "合成の宣言(架空)L16", "1", "200"],
    ["丸めの名前", "1円未満切捨て", "合成の宣言(架空)L17", "", "200"],
    ["丸めの名前", "円未満四捨五入", "合成の宣言(架空)L18", "", "200"],
    ["丸めを掛ける段", "丸めない", "合成の宣言(架空)L19", "1", "200"],
    ["丸めを掛ける段", "1円未満切捨て", "合成の宣言(架空)L20", "", "200"],
    ["入力の桁の扱い", "丸めない", "合成の宣言(架空)L21", "1", "200"],
    ["入力の桁の扱い", "1円未満切捨て", "合成の宣言(架空)L22", "", "200"],
]


def init(folder: str | Path) -> tuple[Path, Path]:
    d = Path(folder)
    d.mkdir(parents=True, exist_ok=True)
    out = []
    for name, rows in (("shikihyou.csv", FORMULA_TEMPLATE), ("jikuhyou.csv", AXIS_TEMPLATE)):
        p = d / name
        with p.open("w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows(rows)
        out.append(p)
    return out[0], out[1]


# ---------------------------------------------------------------- CLI
def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1))


def build_parser() -> argparse.ArgumentParser:
    """CLI は fan / verify / init の 3 つ。正解を選ぶ・許容誤差・集約・寄与率・標本の引数は無い。"""
    ap = argparse.ArgumentParser(prog="variant_fan", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("fan", "verify"):
        s = sub.add_parser(name)
        s.add_argument("formulas")
        s.add_argument("axes")
        s.add_argument("--id", required=True)
        s.add_argument("--input", action="append", default=[], metavar="名前=値")
        s.add_argument("--on", required=True, help="基準日。ISO の日付か、軸の名前")
        s.add_argument("--as-of", required=True, dest="as_of", help="公表時点。ISO の日付か、軸の名前")
    sub.add_parser("init").add_argument("folder")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == "init":
        f, j = init(a.folder)
        print(f"書いた: {f}\n書いた: {j}")
        return 0
    try:
        spec = Spec.load(a.formulas, a.axes)
        inputs: dict[str, object] = {}
        for item in a.input:
            if "=" not in item:
                raise TableError(f"--input は 名前=値 で渡す: {item!r}")
            k, _, v = item.partition("=")
            inputs[k.strip()] = v.strip()
        f = verify(spec, a.id, inputs, a.on, a.as_of) if a.cmd == "verify" \
            else fan(spec, a.id, inputs, a.on, a.as_of)
    except TableError as e:
        print(f"表として読めない: {e}", file=sys.stderr)
        return 2
    if a.cmd == "verify":
        _print(f)
        return 0 if f["ok"] else 3
    if not f.report.ok:
        _print({"ok": False, "stage": "表", "組み合わせ総数": f.report.total,
                "pending": [p.as_dict() for p in f.report.pending]})
        return 3
    _print({"ok": True, "stage": "扇を数えた", "式の id": f.target, **f.counts(),
            "扇の幅": f.width(), "値": f.table(), "読んだ条件": f.read_conditions()})
    return 0 if len(f.distinct()) == 1 else 3


if __name__ == "__main__":
    raise SystemExit(main())
