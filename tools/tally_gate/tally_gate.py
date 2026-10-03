"""tally_gate — 人 × 項目の表を 2 つの軸から足して突き合わせる関所の部品。

支給控除の一覧は「人 × 項目」の表で、人ごとに横へ足した差引の額と、項目ごとに縦へ足した集計行と、
総計の 3 つが、**同じ数字集合**から出てくる。だから 3 つが全部一致するまで取込用の出力を作らない、
という関所が作れる。この部品はその関所で、持たせていないものが要点になる。

  - **許容誤差の引数を持たない**(tolerance / atol / 丸めて吸収する経路が無い)。差が 1 円でも不一致
  - **既定の丸めを持たない**(項目の宣言表の rounding 列から取る。空欄の項目は評価せずに止める)
  - **書き出しを持たない**(全部一致した時に次の工程へ渡す行を返すだけ。ファイルはこの部品からは開かない)
  - **業種の語彙を持たない**(group の名前・恒等式・集計行の名前・識別子の列名は、全て呼び出し側が宣言する)

入力は 2 つ。

    明細      行 = 人の識別子、列 = 項目の名前、値 = 金額。1 行だけ集計行(名前は呼び出し側が宣言する)
    宣言表    列 = item / group / sign / rounding / source

      item      項目の名前(明細の列の見出しと一致する)
      group     その項目がどの group に属するか(名前は呼び出し側が宣言する)
      sign      その項目を group の中で足すときの符号(+ / -)。印字が符号なしの項目に - を付ける
      rounding  丸めの名前。**空欄は許さない**(既定を持たない)
      source    出典。報告に載る

検査は 3 つで、順序を固定する。

    ① 行方向   人ごとに group ごとへ足し、宣言された恒等式の形で差引の列と突き合わせる
    ② 列方向   項目ごとに全員ぶんを足し、集計行と突き合わせる(印字されたままの値を足す = 符号は使わない)
    ③ 総計     行方向の和(人ごとの恒等式の左辺を全員ぶん足す)と、列方向の和(集計行から恒等式の
               左辺を作る)を 2 経路として突き合わせる

不一致は「どの軸で見えたか」で分類して返す。同じ数字集合でも、人の軸で並べ直すか項目の軸で並べ直すかで
見える壊れ方が違う(符号の所属を取り違えた行は人ごとの合計では出るが項目ごとの合計では出ない、人が 1 行
抜けた形は項目ごとの合計では出るが人ごとの合計では出ない、など)。

合計が一致したことは「同じ数字集合を 2 つの軸から足して同じになった」までで、値そのものが制度として
正しいか・項目の所属が正しいかは判定しない。標準ライブラリのみ(csv / json / decimal / argparse / hashlib)。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

SPEC_COLUMNS = ("item", "group", "sign", "rounding", "source")
ROW, COLUMN, TOTAL = "row", "column", "total"
AXES = (ROW, COLUMN, TOTAL)

# どの軸で見えたか(軸の組み合わせの名前)。total_only と row_and_total は作れない
# (列方向が全部一致すれば総計も必ず一致する = test_total_is_implied_by_column が示す)。
VISIBILITY = {
    (): "all_agree",
    (ROW,): "row_only",
    (COLUMN,): "column_only",
    (TOTAL,): "total_only",
    (ROW, COLUMN): "invisible_in_total",     # 行と列には出たが総計では消えた(交点は特定できる)
    (ROW, TOTAL): "row_and_total",
    (COLUMN, TOTAL): "column_and_total",
    (ROW, COLUMN, TOTAL): "row_and_column",  # 3 つ全部に出た(交点が特定でき、総計でも消えなかった)
}
NOT_CHECKED = "not_checked"                  # 理由コードで止まり、3 つの検査に進まなかった

# 止まる理由コード(この 7 つで全部)
REASONS = {
    "rounding 空欄": "宣言表の項目に丸めの名前が書かれていない。部品は既定の丸めを持たない",
    "group 未宣言": "宣言表の項目に group の宣言が無い。どの軸にも足せない",
    "項目が宣言表に無い": "明細に、宣言表に無い列がある。符号も丸めも決まらないので足さない",
    "同じ人が 2 行": "明細に同じ識別子の行が 2 行ある。その人の横の合計が表から決まらない",
    "集計行が無い": "宣言された名前の集計行が明細に無い。項目ごとの合計の突き合わせ先が無い",
    "数字として読めない値": "金額の欄が数として読めない(全角数字・単位つきなど)",
    "検査前に出力を要求した": "check() を通る前に、次の工程へ渡す行を取りに来た",
}


class TableError(ValueError):
    """表そのものが読めない / 2 つの表が噛み合わない(= 表の不備。理由コードでは扱わない)。"""


class GateError(Exception):
    """関所を通っていないのに行を取りに来た。reason に理由コード(または分類)が入る。"""

    def __init__(self, message: str, reason: str = "") -> None:
        super().__init__(message)
        self.reason = reason


# ---------------------------------------------------------------- 丸め(名前で呼ぶ。既定は無い)
# 名前と振る舞いは formula_table(数式を表の行に置く部品)と同じにしてある。

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
    """丸めない。"""
    return x


ROUNDINGS = {
    "50銭以下切捨て": _round50,
    "1円未満切捨て": _floor1,
    "円未満四捨五入": _half_up,
    "丸めない": _as_is,
}


def round_by(value: Decimal, name: str) -> Decimal:
    fn = ROUNDINGS.get(name)
    if fn is None:
        raise TableError(f"登録されていない丸めの名前: {name!r}(登録済 {' / '.join(ROUNDINGS)})")
    return fn(value)


_AMOUNT = re.compile(r"[+-]?[0-9]+(?:\.[0-9]+)?\Z")   # 半角数字だけ(\d は全角も通してしまう)


def read_amount(cell: str) -> Decimal:
    """金額の欄を Decimal にする。空欄は 0 として足す(空欄と 0 は区別しない)。

    半角数字・符号・小数点・桁区切りのカンマ以外が入っていたら読まない。Decimal は全角数字を
    そのまま受けてしまうので(`Decimal("８")` が通る)、形のほうを先に見る。
    """
    s = str(cell or "").strip().replace(",", "")
    if s == "":
        return Decimal(0)
    if not _AMOUNT.match(s):
        raise ValueError(f"数として読めない: {cell!r}")
    try:
        return Decimal(s)
    except InvalidOperation as e:   # pragma: no cover - 形の検査を通れば起きない
        raise ValueError(f"数として読めない: {cell!r}") from e


def sha256_of(path: "str | Path") -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- 宣言表

@dataclass(frozen=True)
class Item:
    item: str
    group: str
    sign: int
    rounding: str
    source: str = ""

    def signed(self, value: Decimal) -> Decimal:
        return self.sign * round_by(value, self.rounding)


@dataclass(frozen=True)
class Spec:
    """項目の宣言表。部品は項目の意味を知らない(group の名前も呼び出し側が宣言する)。"""

    items: tuple = ()

    @classmethod
    def load(cls, path: "str | Path") -> "Spec":
        p = Path(path)
        text = p.read_text(encoding="utf-8-sig")
        if p.suffix.lower() == ".json":
            try:
                data = json.loads(text)
            except json.JSONDecodeError as e:
                raise TableError(f"宣言表が JSON として読めない: {e}") from e
            rows = data.get("items", data) if isinstance(data, dict) else data
            if not isinstance(rows, list):
                raise TableError("宣言表の JSON は項目の配列(または items を持つ object)で書く")
        else:
            reader = csv.DictReader(text.splitlines())
            missing = [c for c in SPEC_COLUMNS if c not in (reader.fieldnames or [])]
            if missing:
                raise TableError(f"宣言表の見出しの列が足りない: {' / '.join(missing)}")
            rows = list(reader)
        return cls.of(rows)

    @classmethod
    def of(cls, rows: list) -> "Spec":
        items = []
        seen: set = set()
        for i, r in enumerate(rows, 1):
            name = str(r.get("item", "") or "").strip()
            if not name:
                raise TableError(f"宣言表の行 {i} に item が無い")
            if name in seen:
                raise TableError(f"宣言表に同じ item が 2 行ある: {name}")
            seen.add(name)
            raw_sign = str(r.get("sign", "") or "").strip()
            if raw_sign not in ("+", "-"):
                raise TableError(f"宣言表の行 {i}({name})の sign は + か - で書く: {raw_sign!r}")
            rounding = str(r.get("rounding", "") or "").strip()
            if rounding and rounding not in ROUNDINGS:
                raise TableError(f"宣言表の行 {i}({name})の登録されていない丸めの名前: {rounding!r}"
                                 f"(登録済 {' / '.join(ROUNDINGS)})")
            items.append(Item(name, str(r.get("group", "") or "").strip(),
                              1 if raw_sign == "+" else -1, rounding,
                              str(r.get("source", "") or "").strip()))
        if not items:
            raise TableError("宣言表が空")
        return cls(tuple(items))

    @property
    def names(self) -> tuple:
        return tuple(i.item for i in self.items)

    @property
    def groups(self) -> tuple:
        return tuple(dict.fromkeys(i.group for i in self.items if i.group))

    def by_item(self, name: str) -> "Item | None":
        for i in self.items:
            if i.item == name:
                return i
        return None

    def of_group(self, group: str) -> tuple:
        return tuple(i for i in self.items if i.group == group)


# ---------------------------------------------------------------- 恒等式(group の名前で書く)

_TERM = re.compile(r"([+-]?)\s*([^+\-=]+)")


@dataclass(frozen=True)
class Identity:
    """`支給 - 控除 = 差引` の形。group の名前だけで書く(項目の名前も業種の語彙も出てこない)。"""

    terms: tuple = ()       # 左辺 ((+1 | -1, group), ...)
    rhs: str = ""           # 右辺(group 1 つ)
    text: str = ""

    @classmethod
    def parse(cls, text: str) -> "Identity":
        if str(text or "").count("=") != 1:
            raise TableError(f"恒等式は『左辺 = 右辺』の形で = を 1 つ書く: {text!r}")
        left, right = text.split("=")
        rhs = right.strip()
        if not rhs or any(c in rhs for c in "+-"):
            raise TableError(f"恒等式の右辺は group 1 つで書く: {right!r}")
        terms = []
        for m in _TERM.finditer(left.strip()):
            name = m.group(2).strip()
            if name:
                terms.append((-1 if m.group(1) == "-" else 1, name))
        if not terms:
            raise TableError(f"恒等式の左辺が読めない: {left!r}")
        if len({g for _, g in terms}) != len(terms) or rhs in {g for _, g in terms}:
            raise TableError(f"恒等式に同じ group が 2 回出てくる: {text!r}")
        return cls(tuple(terms), rhs, str(text).strip())

    def groups(self) -> tuple:
        return tuple(dict.fromkeys([g for _, g in self.terms] + [self.rhs]))

    def left(self, sums: dict) -> Decimal:
        return sum((s * sums[g] for s, g in self.terms), Decimal(0))


@dataclass(frozen=True)
class Declaration:
    """呼び出し側が宣言するもの。部品の中には 1 つも既定を置かない。"""

    identity: Identity
    id_column: str
    total_row: str

    @classmethod
    def of(cls, identity: str, id_column: str, total_row: str) -> "Declaration":
        for what, v in (("識別子の列名", id_column), ("集計行の名前", total_row)):
            if not str(v or "").strip():
                raise TableError(f"{what} が宣言されていない(部品は既定を持たない)")
        return cls(Identity.parse(identity), id_column.strip(), total_row.strip())


# ---------------------------------------------------------------- 明細

@dataclass(frozen=True)
class Table:
    """人 × 項目の表。1 行だけ集計行(名前は宣言で決まる)。"""

    id_column: str
    items: tuple = ()
    rows: tuple = ()        # (識別子, {項目: 文字列}) の並び。集計行も含む

    @classmethod
    def load(cls, path: "str | Path", id_column: str) -> "Table":
        p = Path(path)
        reader = csv.DictReader(p.read_text(encoding="utf-8-sig").splitlines())
        head = list(reader.fieldnames or [])
        if id_column not in head:
            raise TableError(f"明細に識別子の列が無い: {id_column}(見出し {' / '.join(head)})")
        items = tuple(c for c in head if c != id_column and str(c or "").strip())
        if not items:
            raise TableError("明細に項目の列が無い")
        rows = tuple((str(r.get(id_column, "") or "").strip(),
                      {c: str(r.get(c, "") or "") for c in items}) for r in reader)
        return cls(id_column, items, rows)

    @classmethod
    def of(cls, id_column: str, items: list, rows: list) -> "Table":
        return cls(id_column, tuple(items),
                   tuple((str(r.get(id_column, "") or "").strip(),
                          {c: str(r.get(c, "") or "") for c in items}) for r in rows))

    def to_dicts(self) -> list:
        return [{self.id_column: who, **cells} for who, cells in self.rows]


# ---------------------------------------------------------------- 結果

@dataclass(frozen=True)
class Pending:
    reason: str
    detail: str


@dataclass(frozen=True)
class Diff:
    axis: str
    who: str                # 人の識別子(行方向)
    item: str               # 項目の名前(列方向)
    expected: str           # 表に印字されている側
    actual: str             # 足して出た側
    delta: str
    source: str = ""

    def as_dict(self) -> dict:
        return {"axis": self.axis, "who": self.who, "item": self.item,
                "expected": self.expected, "actual": self.actual, "delta": self.delta,
                "source": self.source}


@dataclass(frozen=True)
class Report:
    ok: bool
    visibility: str
    axes: tuple = ()
    pending: tuple = ()
    diffs: tuple = ()
    people: int = 0
    items: int = 0
    row_total: str = ""        # 行方向の和(人ごとの左辺を全員ぶん)
    column_total: str = ""     # 列方向の和(集計行から作った左辺)

    def as_dict(self) -> dict:
        return {"ok": self.ok, "visibility": self.visibility, "axes": list(self.axes),
                "people": self.people, "items": self.items,
                "row_total": self.row_total, "column_total": self.column_total,
                "pending": [{"reason": p.reason, "detail": p.detail} for p in self.pending],
                "diffs": [d.as_dict() for d in self.diffs]}

    def by_axis(self, axis: str) -> tuple:
        return tuple(d for d in self.diffs if d.axis == axis)

    def crossing(self) -> tuple:
        """行と列の両方に出たときの交点(人 × 項目)。片方だけなら空。"""
        if not (self.by_axis(ROW) and self.by_axis(COLUMN)):
            return ()
        return tuple((d.who, c.item) for d in self.by_axis(ROW) for c in self.by_axis(COLUMN))


# ---------------------------------------------------------------- 関所

class Gate:
    """3 つの検査を固定の順序で通す関所。全部一致した時だけ handoff() が行を返す。"""

    def __init__(self, table: Table, spec: Spec, decl: Declaration) -> None:
        if table.id_column != decl.id_column:
            raise TableError(f"明細の識別子の列と宣言が違う: {table.id_column} / {decl.id_column}")
        missing = [n for n in spec.names if n not in table.items]
        if missing:
            raise TableError(f"宣言表にある項目が明細に無い: {' / '.join(missing)}")
        unknown = [g for g in spec.groups if g not in decl.identity.groups()]
        if unknown:
            raise TableError(f"恒等式に出てこない group がある: {' / '.join(unknown)}"
                             f"(恒等式 {decl.identity.text})")
        short = [g for g in decl.identity.groups() if g not in spec.groups]
        if short:
            raise TableError(f"恒等式の group に属する項目が宣言表に無い: {' / '.join(short)}")
        self.table, self.spec, self.decl = table, spec, decl
        self._report: "Report | None" = None

    # -- 入口の検査(理由コード。1 つでもあれば 3 つの検査に進まない) ----------

    def _pending(self) -> list:
        out: list = []
        for i in self.spec.items:
            if not i.group:
                out.append(Pending("group 未宣言", f"項目『{i.item}』に group の宣言が無い"))
            if not i.rounding:
                out.append(Pending("rounding 空欄",
                                   f"項目『{i.item}』に丸めの名前が無い(既定は持たない)"))
        for col in self.table.items:
            if self.spec.by_item(col) is None:
                out.append(Pending("項目が宣言表に無い", f"明細の列『{col}』が宣言表に無い"))
        seen: dict = {}
        for who, _ in self.table.rows:
            seen[who] = seen.get(who, 0) + 1
        for who, n in seen.items():
            if n > 1:
                out.append(Pending("同じ人が 2 行", f"識別子『{who}』の行が {n} 行ある"))
        if self.decl.total_row not in seen:
            out.append(Pending("集計行が無い", f"集計行『{self.decl.total_row}』が明細に無い"))
        for who, cells in self.table.rows:
            for col in self.table.items:
                try:
                    read_amount(cells.get(col, ""))
                except ValueError as e:
                    out.append(Pending("数字として読めない値", f"{who} の『{col}』: {e}"))
        return out

    # -- 3 つの検査 -------------------------------------------------

    def _group_sums(self, cells: dict) -> dict:
        sums = {g: Decimal(0) for g in self.decl.identity.groups()}
        for i in self.spec.items:
            sums[i.group] += i.signed(read_amount(cells.get(i.item, "")))
        return sums

    def _printed(self, cells: dict, item: Item) -> Decimal:
        """印字されたままの値(符号は使わない)。列方向の突き合わせはこの形で行う。"""
        return round_by(read_amount(cells.get(item.item, "")), item.rounding)

    def check(self) -> Report:
        """① 行方向 → ② 列方向 → ③ 総計 の順に検査し、どの軸で見えたかを返す。"""
        pend = self._pending()
        if pend:
            self._report = Report(False, NOT_CHECKED, (), tuple(pend), (),
                                  people=0, items=len(self.table.items))
            return self._report
        people = [(who, cells) for who, cells in self.table.rows if who != self.decl.total_row]
        total_cells = dict(self.table.rows)[self.decl.total_row]
        diffs: list = []

        # ① 行方向(人ごとに group へ足し、恒等式の形で差引の列と突き合わせる)
        row_total = Decimal(0)
        for who, cells in people:
            sums = self._group_sums(cells)
            left, right = self.decl.identity.left(sums), sums[self.decl.identity.rhs]
            row_total += left
            if left != right:
                diffs.append(Diff(ROW, who, "", format(right, "f"), format(left, "f"),
                                  format(left - right, "f"), self.decl.identity.text))

        # ② 列方向(項目ごとに全員ぶんを足し、集計行と突き合わせる)
        for i in self.spec.items:
            got = sum((self._printed(cells, i) for _, cells in people), Decimal(0))
            want = self._printed(total_cells, i)
            if got != want:
                diffs.append(Diff(COLUMN, "", i.item, format(want, "f"), format(got, "f"),
                                  format(got - want, "f"), i.source))

        # ③ 総計(行方向の和と、集計行から作った列方向の和を 2 経路として突き合わせる)
        column_total = self.decl.identity.left(self._group_sums(total_cells))
        if row_total != column_total:
            diffs.append(Diff(TOTAL, "", "", format(column_total, "f"), format(row_total, "f"),
                              format(row_total - column_total, "f"), self.decl.identity.text))

        axes = tuple(a for a in AXES if any(d.axis == a for d in diffs))
        self._report = Report(not diffs, VISIBILITY[axes], axes, (), tuple(diffs),
                              people=len(people), items=len(self.spec.items),
                              row_total=format(row_total, "f"),
                              column_total=format(column_total, "f"))
        return self._report

    @property
    def report(self) -> Report:
        if self._report is None:
            raise GateError("check() を通る前に結果を見に来た", "検査前に出力を要求した")
        return self._report

    # -- 次の工程へ渡す(全部一致した時だけ。ファイルはこの部品からは開かない) ----

    def handoff(self) -> list:
        """3 つの検査が全部一致した時だけ、人の行(集計行を除く)を返す。

        返すのは行だけで、書き出しはしない(取込用 CSV を書くのは別の部品 = intake_csv の仕事)。
        """
        r = self.report
        if not r.ok:
            raise GateError(f"検査に通っていないので渡さない({r.visibility})", r.visibility)
        return [{self.table.id_column: who,
                 **{i.item: cells.get(i.item, "") for i in self.spec.items}}
                for who, cells in self.table.rows if who != self.decl.total_row]

    def rows_for_report(self) -> list:
        r = self.report
        if r.pending:
            return [{"axis": "", "who": "", "item": "", "expected": "", "actual": "", "delta": "",
                     "reason": p.reason, "detail": p.detail, "source": ""} for p in r.pending]
        return [{**d.as_dict(), "reason": "", "detail": ""} for d in r.diffs]


REPORT_COLUMNS = ("axis", "who", "item", "expected", "actual", "delta", "reason", "detail", "source")


def check(table: Table, spec: Spec, decl: Declaration) -> Gate:
    """検査まで通した Gate を返す(handoff() が使える)。"""
    g = Gate(table, spec, decl)
    g.check()
    return g


# ---------------------------------------------------------------- CLI

def _build(args) -> Gate:
    decl = Declaration.of(args.identity, args.id_column, args.total_row)
    return check(Table.load(args.meisai, decl.id_column), Spec.load(args.spec), decl)


def _cli_check(args) -> int:
    g = _build(args)
    print(json.dumps(g.report.as_dict(), ensure_ascii=False))
    return 0 if g.report.ok else 3


def _cli_report(args) -> int:
    g = _build(args)
    rows = g.rows_for_report()
    if args.format == "csv":
        w = csv.DictWriter(sys.stdout, fieldnames=list(REPORT_COLUMNS), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    else:
        print(json.dumps({"visibility": g.report.visibility, "columns": list(REPORT_COLUMNS),
                          "rows": rows}, ensure_ascii=False))
    return 0 if g.report.ok else 3


def _cli_init(args) -> int:
    p = Path(args.path)
    if p.exists():
        raise TableError(f"すでにある: {p}(上書きしない)")
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(SPEC_COLUMNS))
        w.writeheader()
        w.writerow({"item": "項目の名前(明細の列の見出しと同じ)",
                    "group": "呼び出し側が宣言する group", "sign": "+",
                    "rounding": f"{' / '.join(ROUNDINGS)} のどれか(空欄は止まる)",
                    "source": "出典"})
    print(json.dumps({"ok": True, "wrote": str(p), "columns": list(SPEC_COLUMNS),
                      "roundings": list(ROUNDINGS)}, ensure_ascii=False))
    return 0


def main(argv: "list | None" = None) -> int:
    p = argparse.ArgumentParser(
        description="人 × 項目の表を 2 つの軸から足して突き合わせる(許容誤差は持たない)")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, help_text, fn in (("check", "3 つの検査を通して分類と差を出す", _cli_check),
                                ("report", "差の一覧を出す(CSV / JSON)", _cli_report)):
        s = sub.add_parser(name, help=help_text)
        s.add_argument("meisai", help="明細(人 × 項目の CSV)")
        s.add_argument("--spec", required=True, help="項目の宣言表(CSV / JSON)")
        s.add_argument("--identity", required=True, help="恒等式(例: 支給 - 控除 = 差引)")
        s.add_argument("--id-column", dest="id_column", required=True, help="人の識別子の列名")
        s.add_argument("--total-row", dest="total_row", required=True, help="集計行の識別子")
        if name == "report":
            s.add_argument("--format", choices=("csv", "json"), default="json")
        s.set_defaults(func=fn)
    i = sub.add_parser("init", help="宣言表の見出しを書き出す")
    i.add_argument("path")
    i.set_defaults(func=_cli_init)
    args = p.parse_args(argv)
    try:
        return args.func(args)
    except (TableError, GateError) as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except OSError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
