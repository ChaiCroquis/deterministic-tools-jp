"""diff_tally — 「表が変わったか」を独立な 2 経路(差分の件数 / 出力の指紋)で並べ、差だけを返す。

**「表が変わったか」には独立な 2 経路の数があり(① 差分の記録に出る増えた / 減った / 中身が
替わった行数、② 出力の指紋)、同じ回について別の答えを返す回が実際に在る。片方だけを見て
「変わっていない」と書くと、もう片方が変わった回を取りこぼす。**

この部品は、実行の記録の台帳・棚卸しの台帳・欄の登録表・結果記号の登録表・差の理由の宣言表
(5 枚)から、順序番号で隣り合う回の対ごとに 6 値(**差分が 0 で指紋も前の回と同じ / 差分は
0 なのに指紋が前の回と違う / 差分は 0 でないのに指紋が前の回と同じ / 差分も指紋も動いた /
差分の欄が記載なし / 指紋が記載なし**)のどれか 1 つを付け、併せて **戻りの印**(指紋が前の回
ではなく過去のどれかの回と同じ文字列)を出す。さらに累積の突合を 1 行だけ返す。

持たせていないものが規律になっている。

  - **出力に「正しい経路」「信頼できる方」「一致率」の欄が無い**(2 経路の値と差を並べるだけ。
    どちらが正しいかを決める引数も、並べ替える引数も無い)
  - **差の原因を推定しない**(理由は差の理由の宣言表の写しだけで、宣言が無ければ「宣言なし」。
    原因を当てる辞書も regex も持たない)
  - **単位と期間を入力に宣言させてから出す**(欄ごとの単位記号が登録の外なら表として読めない。
    対象の期間は入力の順序番号の最小と最大をそのまま写す)
  - **ハッシュを計算しない**(指紋は入力の文字列を比べるだけ。file を読んで hash にする経路が
    無い。判定部分の sha256 だけが唯一の hashlib の呼び出し)
  - **中身が替わった行数を累積に足す関数そのものを置かない**(累積に入るのは欄の登録表で
    `増やす` / `減らす` と宣言された欄だけ。`動かさない` と宣言された欄は入る経路が無い)
  - **指紋から行数を推測しない / 行数から指紋を作らない**
  - **成功率を出さない**(落ちた回の仕分けは別の部品の領分)
  - **周期を読まない**(入力に日付も時刻も無い)
  - **検証の件数を分解しない**(入るのは実行の記録の件数だけ)
  - **どの行を出し直すかを決めない**
  - **差分の中身の値を読まない**(入るのは件数と記号と指紋の文字列と出典だけ)
  - **現在時刻を読まない**、**pipeline を走らせない**、**入力を書き換えない**、**float を
    使わない**(件数・行数・順序番号は整数、ほかは文字列)

入力は 5 枚。**どの行にも出典の欄が要る。**

実行の記録の台帳(CSV)の列は 8。**1 回の実行が 1 行。**

    run_id       実行 id(同じ id が 2 行あると読めない)
    seq          順序番号(1 以上の整数。重複や飛びが在ると 1 対も数えずに止まる)
    status       結果記号(登録表に無ければ止まる)
    added        増えた行数(0 以上の整数 または `記載なし`)
    removed      減った行数(同じ)
    changed      中身が替わった行数(同じ。**累積に足す経路が無い**)
    fingerprint  出力の指紋の文字列(または `記載なし`)。**長さが揃っていないと止まる**
    source       出典(ファイル名 + 行番号)。空欄は止まる

棚卸しの台帳(CSV)の列は 4。**1 つの時点が 1 行。**

    asof     時点記号(重複すると止まる)
    rows     宣言された行数(0 以上の整数)
    rules    宣言された rule 数(0 以上の整数)
    source   出典。空欄は止まる

欄の登録表(CSV)の列は 4。**差分の 3 欄すべてを登録する**(1 つでも無いと止まる)。

    field    欄名(`added` / `removed` / `changed`)
    moves    行数を動かすか記号(`増やす` / `減らす` / `動かさない`)
    unit     単位記号(`行` / `回`)。**登録の外なら表として読めない**
    source   登録の出典。空欄は止まる

結果記号の登録表(CSV)の列は 4。

    status      結果記号
    replaces    本番の出力を差し替えるか(`差し替える` / `差し替えない`)
    cumulative  累積に入れるか(`入れる` / `入れない`)。**累積の定義はここに在る**
    source      登録の出典。空欄は止まる

差の理由の宣言表(CSV)の列は 4。**ヘッダだけでもよい**(宣言が無ければ「宣言なし」)。

    from_run  対の前の実行 id
    to_run    対の後の実行 id(**どちらも台帳に実在しないと止まる**)
    reason    理由コード(人が書いた宣言。**この部品は原因を当てない**)
    source    出典。空欄は止まる

使い方:

    python diff_tally.py init ひな型/
    python diff_tally.py check 実行の記録.csv 棚卸し.csv 欄.csv 結果記号.csv 差の理由.csv
    python diff_tally.py pairs 実行の記録.csv 棚卸し.csv 欄.csv 結果記号.csv 差の理由.csv
    python diff_tally.py verify 実行の記録.csv 棚卸し.csv 欄.csv 結果記号.csv 差の理由.csv

終了コードは、2 経路が揃わない対(差分は 0 なのに指紋が違う / 差分は 0 でないのに指紋が同じ /
差分の欄が記載なし / 指紋が記載なし)と戻りの印と累積の差と止まった行が 0 件のときだけ 0、
在れば 3、表として読めなければ 2。**0 は「変わっていない」ではなく「2 経路が全ての対で同じ
答えを返した」の意味で、どちらが正しいかはこの部品の終了コードにも出力にも出ない。**
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

RUN_COLUMNS = ("run_id", "seq", "status", "added", "removed", "changed",
               "fingerprint", "source")
STOCK_COLUMNS = ("asof", "rows", "rules", "source")
FIELD_COLUMNS = ("field", "moves", "unit", "source")
STATUS_COLUMNS = ("status", "replaces", "cumulative", "source")
REASON_COLUMNS = ("from_run", "to_run", "reason", "source")

# 差分の 3 欄。**この 3 つの外に欄を作る経路が無い。**
DIFF_FIELDS = ("added", "removed", "changed")
# 行数を動かすか(**3 番目だけが「行の数は動かない」を意味する**)
MOVES = ("増やす", "減らす", "動かさない")
# 欄の単位(**件数の単位はこの 2 つの記号つきでしか受け取らない**)
FIELD_UNITS = ("行", "回")
# 本番の出力を差し替えるか
REPLACES = ("差し替える", "差し替えない")
# 累積に入れるか(**累積の定義は結果記号の側に在る**)
CUMULATIVE = ("入れる", "入れない")

NONE_MARK = "記載なし"
# 指紋の経路の単位。**件数の単位と足せないことを記号で示す。**
FP_UNIT = "文字列の一致"
# 累積の突合の返り値(**どちらが正しいかは言わない**)
MATCH, DIFFER = "一致", "差がある"
NOT_DECLARED = "宣言なし"
# 出力に写す指紋の長さ(**全文は比べるだけで、出すのは先頭だけ**)
FP_HEAD = 12

# 回の対 1 つに付く 6 値。**この 6 つの外に値を作る経路が無い。**
MUTSU = (
    "差分が 0 で指紋も前の回と同じ",
    "差分は 0 なのに指紋が前の回と違う",
    "差分は 0 でないのに指紋が前の回と同じ",
    "差分も指紋も動いた",
    "差分の欄が記載なし",
    "指紋が記載なし",
)

SWAPS = ("逆順", "両端入れ替え", "1 つずらす")

STOP_REASONS = (
    # 表の側。1 対も数えずに止まる(8)
    "出典の欄が空",
    "欄名が登録表に無い",
    "結果記号が登録表に無い",
    "順序番号の重複または飛び",
    "件数が整数でない",
    "指紋の文字列の長さが揃っていない",
    "棚卸しの時点記号の重複",
    "理由の宣言表が実在しない run id の対を指す",
    # verify が見つける(3)
    "件数の合計が合わない", "2 回目の判定部分が不一致", "行順を入れ替えた表で出力が変わる",
)
TABLE_REASONS = STOP_REASONS[:8]
VERIFY_REASONS = STOP_REASONS[8:]

SUBCOMMANDS = ("pairs", "check", "verify", "init")
SCOPE_KEYS = ("読んだ実行の記録の台帳の絶対パス", "読んだ棚卸しの台帳の絶対パス",
              "読んだ欄の登録表の絶対パス", "読んだ結果記号の登録表の絶対パス",
              "読んだ差の理由の宣言表の絶対パス")

NG_ID = set(" \t,|;")


class ReadError(Exception):
    """表として読めない(終了コード 2)。回の対は 1 つも数えない。"""


@dataclass(frozen=True)
class Pending:
    reason: str
    detail: str = ""

    def as_dict(self) -> dict[str, str]:
        return {"理由コード": self.reason, "どこ": self.detail}


def bad_id(s: str) -> bool:
    return (not s) or any(ch in NG_ID for ch in s)


def whole(s: str, what: str, where: str, least: int = 0) -> int:
    """整数として読む。小数も符号も受け取らない(**float を使う経路が無い**)。"""
    if not (s.isascii() and s.isdigit()):
        raise ReadError(f"{where}: {what}が整数でない({s or '空欄'})")
    v = int(s)
    if v < least:
        raise ReadError(f"{where}: {what}が {least} 以上でない({v})")
    return v


def read_tally(s: str) -> tuple[int | None, bool]:
    """件数の欄を読む。**`記載なし` は None、読めなければ読めないまま別枠へ出す。**"""
    if s == NONE_MARK:
        return None, True
    if s.isascii() and s.isdigit():
        return int(s), True
    return None, False


def swap_rows(rows: list, how: str) -> list:
    """登録された入れ替え方で行順を入れ替える(verify が使う)。"""
    if how == SWAPS[0]:
        return list(reversed(rows))
    if how == SWAPS[1]:
        out = list(rows)
        if len(out) >= 2:
            out[0], out[-1] = out[-1], out[0]
        return out
    if how == SWAPS[2]:
        return list(rows[1:]) + list(rows[:1])
    raise ReadError(f"登録されていない入れ替え方: {how or '空欄'}")


def _rows_of(text: str, columns: tuple[str, ...], what: str):
    reader = csv.DictReader(text.splitlines())
    lack = [c for c in columns if c not in tuple(reader.fieldnames or ())]
    if lack:
        raise ReadError(f"{what}に " + " / ".join(lack) + " の列が無い")
    for i, raw in enumerate(reader, start=2):
        yield i, {k: (raw.get(k) or "").strip() for k in columns}


# ------------------------------------------------------------ 欄の登録表


@dataclass(frozen=True)
class Field:
    """差分の欄 1 つ。**行数を動かすかと単位は人が書いた宣言で、欄名から当てる経路が無い。**"""
    field: str
    moves: str
    unit: str
    source: str


@dataclass(frozen=True)
class Fields:
    items: tuple[Field, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Fields":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"欄の登録表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Fields":
        items: list[Field] = []
        pending: list[Pending] = []
        seen: set[str] = set()
        for i, cell in _rows_of(text, FIELD_COLUMNS, "欄の登録表"):
            where = f"欄の登録表 行 {i}"
            if bad_id(cell["field"]):
                raise ReadError(f"{where}: 欄名が空欄か、区切り文字を含む"
                                f"({cell['field'] or '空欄'})")
            if cell["moves"] not in MOVES:
                raise ReadError(f"{where}: 行数を動かすか記号が登録の 3 つでない"
                                f"({cell['moves'] or '空欄'})")
            if cell["unit"] not in FIELD_UNITS:
                raise ReadError(f"{where}: 単位記号が登録の 2 つでない"
                                f"({cell['unit'] or '空欄'})")
            if cell["field"] in seen:
                raise ReadError(f"{where}: 同じ欄名が 2 行ある({cell['field']})")
            seen.add(cell["field"])
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0], f"{where}: {cell['field']}"))
            items.append(Field(**cell))
        if not items:
            raise ReadError("欄の登録表に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    def of(self, field: str) -> Field | None:
        """**登録に無い欄名には何も当てない**(None を返す = 止まる)。"""
        return next((f for f in self.items if f.field == field), None)

    def moving(self, how: str) -> tuple[str, ...]:
        """`増やす` / `減らす` と宣言された欄名(**`動かさない` はここに入らない**)。"""
        return tuple(f.field for f in sorted(self.items, key=lambda x: x.field)
                     if f.moves == how and f.field in DIFF_FIELDS)

    def unit_of(self, field: str) -> str:
        f = self.of(field)
        return f.unit if f else ""

    def swapped(self, how: str) -> "Fields":
        return Fields(items=tuple(swap_rows(list(self.items), how)),
                      pending=self.pending, path=self.path)


# ------------------------------------------------------------ 結果記号の登録表


@dataclass(frozen=True)
class Status:
    """結果記号 1 つ。**累積に入れるかの宣言をここで持つ**(回の側では決めない)。"""
    status: str
    replaces: str
    cumulative: str
    source: str


@dataclass(frozen=True)
class Statuses:
    items: tuple[Status, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Statuses":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"結果記号の登録表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Statuses":
        items: list[Status] = []
        pending: list[Pending] = []
        seen: set[str] = set()
        for i, cell in _rows_of(text, STATUS_COLUMNS, "結果記号の登録表"):
            where = f"結果記号の登録表 行 {i}"
            if bad_id(cell["status"]):
                raise ReadError(f"{where}: 結果記号が空欄か、区切り文字を含む"
                                f"({cell['status'] or '空欄'})")
            if cell["replaces"] not in REPLACES:
                raise ReadError(f"{where}: 本番の出力を差し替えるかが登録の 2 つでない"
                                f"({cell['replaces'] or '空欄'})")
            if cell["cumulative"] not in CUMULATIVE:
                raise ReadError(f"{where}: 累積に入れるかが登録の 2 つでない"
                                f"({cell['cumulative'] or '空欄'})")
            if cell["status"] in seen:
                raise ReadError(f"{where}: 同じ結果記号が 2 行ある({cell['status']})")
            seen.add(cell["status"])
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0], f"{where}: {cell['status']}"))
            items.append(Status(**cell))
        if not items:
            raise ReadError("結果記号の登録表に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    def of(self, status: str) -> Status | None:
        return next((s for s in self.items if s.status == status), None)

    def counted(self) -> tuple[str, ...]:
        return tuple(s.status for s in sorted(self.items, key=lambda x: x.status)
                     if s.cumulative == CUMULATIVE[0])

    def flipped(self, status: str, to: str) -> "Statuses":
        """累積に入れるかの宣言を 1 つ替えた写し(**メモリの中だけ**)。"""
        if to not in CUMULATIVE:
            raise ReadError(f"登録されていない累積の宣言: {to or '空欄'}")
        return Statuses(items=tuple(
            Status(s.status, s.replaces, to, s.source) if s.status == status else s
            for s in self.items), pending=self.pending, path=self.path)

    def swapped(self, how: str) -> "Statuses":
        return Statuses(items=tuple(swap_rows(list(self.items), how)),
                        pending=self.pending, path=self.path)


# ------------------------------------------------------------ 棚卸しの台帳


@dataclass(frozen=True)
class Stock:
    """棚卸しの 1 時点。**宣言された行数と rule 数だけで、値の列を持たない。**"""
    asof: str
    rows: int
    rules: int
    source: str


@dataclass(frozen=True)
class Stocks:
    items: tuple[Stock, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Stocks":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"棚卸しの台帳が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Stocks":
        items: list[Stock] = []
        pending: list[Pending] = []
        seen: set[str] = set()
        for i, cell in _rows_of(text, STOCK_COLUMNS, "棚卸しの台帳"):
            where = f"棚卸しの台帳 行 {i}"
            if bad_id(cell["asof"]):
                raise ReadError(f"{where}: 時点記号が空欄か、区切り文字を含む"
                                f"({cell['asof'] or '空欄'})")
            rows = whole(cell["rows"], "宣言された行数", where)
            rules = whole(cell["rules"], "宣言された rule 数", where)
            if cell["asof"] in seen:
                pending.append(Pending(STOP_REASONS[6], f"{where}: {cell['asof']}"))
            seen.add(cell["asof"])
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0], f"{where}: {cell['asof']}"))
            items.append(Stock(asof=cell["asof"], rows=rows, rules=rules,
                               source=cell["source"]))
        if not items:
            raise ReadError("棚卸しの台帳に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    @property
    def ordered(self) -> tuple[Stock, ...]:
        return tuple(sorted(self.items, key=lambda s: s.asof))

    @property
    def last(self) -> Stock:
        """突合に使う時点(**時点記号の並びで最後の 1 行だけ**。残りは一覧へ出す)。"""
        return self.ordered[-1]

    def swapped(self, how: str) -> "Stocks":
        return Stocks(items=tuple(swap_rows(list(self.items), how)),
                      pending=self.pending, path=self.path)


# ------------------------------------------------------------ 差の理由の宣言表


@dataclass(frozen=True)
class Reason:
    """差が生じる既知の理由 1 つ。**人が書いた宣言で、この部品は原因を当てない。**"""
    from_run: str
    to_run: str
    reason: str
    source: str


@dataclass(frozen=True)
class Reasons:
    items: tuple[Reason, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Reasons":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"差の理由の宣言表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Reasons":
        items: list[Reason] = []
        pending: list[Pending] = []
        seen: set[tuple[str, str]] = set()
        for i, cell in _rows_of(text, REASON_COLUMNS, "差の理由の宣言表"):
            where = f"差の理由の宣言表 行 {i}"
            for key, what in (("from_run", "対の前の実行 id"),
                              ("to_run", "対の後の実行 id")):
                if bad_id(cell[key]):
                    raise ReadError(f"{where}: {what}が空欄か、区切り文字を含む"
                                    f"({cell[key] or '空欄'})")
            if not cell["reason"]:
                raise ReadError(f"{where}: 理由コードが空欄")
            pair = (cell["from_run"], cell["to_run"])
            if pair in seen:
                raise ReadError(f"{where}: 同じ対が 2 行ある({' → '.join(pair)})")
            seen.add(pair)
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0],
                                       f"{where}: {' → '.join(pair)}"))
            items.append(Reason(**cell))
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    @property
    def ordered(self) -> tuple[Reason, ...]:
        return tuple(sorted(self.items, key=lambda r: (r.from_run, r.to_run)))

    def of(self, from_run: str, to_run: str) -> str:
        """**宣言された分だけを写す。無ければ「宣言なし」。**"""
        hit = next((r for r in self.items
                    if r.from_run == from_run and r.to_run == to_run), None)
        return hit.reason if hit else NOT_DECLARED

    def swapped(self, how: str) -> "Reasons":
        return Reasons(items=tuple(swap_rows(list(self.items), how)),
                       pending=self.pending, path=self.path)


# ------------------------------------------------------------ 実行の記録の台帳


@dataclass(frozen=True)
class Run:
    """実行 1 回。**2 経路(差分の 3 欄と指紋の文字列)を同じ 1 行で持つ。**"""
    run_id: str
    seq: int
    status: str
    tallies: tuple[tuple[str, int | None], ...]
    raw: tuple[tuple[str, str], ...]
    fingerprint: str
    source: str

    def value(self, field: str) -> int | None:
        return dict(self.tallies).get(field)

    def written(self, field: str) -> str:
        return dict(self.raw).get(field, "")

    @property
    def missing_tally(self) -> bool:
        """差分の欄に `記載なし` が在るか。"""
        return any(v is None for _, v in self.tallies)

    @property
    def zero_tally(self) -> bool:
        """差分の 3 欄が全て 0 か(**`記載なし` は 0 と読まない**)。"""
        return not self.missing_tally and all(v == 0 for _, v in self.tallies)

    @property
    def missing_fingerprint(self) -> bool:
        return self.fingerprint == NONE_MARK

    @property
    def head(self) -> str:
        """出力に写す指紋(**全文は比べるだけで、出すのは先頭 12 文字**)。"""
        return (self.fingerprint if self.missing_fingerprint
                else self.fingerprint[:FP_HEAD])


@dataclass(frozen=True)
class Runs:
    items: tuple[Run, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Runs":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"実行の記録の台帳が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Runs":
        items: list[Run] = []
        pending: list[Pending] = []
        seen: set[str] = set()
        for i, cell in _rows_of(text, RUN_COLUMNS, "実行の記録の台帳"):
            where = f"実行の記録の台帳 行 {i}"
            if bad_id(cell["run_id"]):
                raise ReadError(f"{where}: 実行 id が空欄か、区切り文字を含む"
                                f"({cell['run_id'] or '空欄'})")
            seq = whole(cell["seq"], "順序番号", where, least=1)
            if not cell["fingerprint"]:
                raise ReadError(f"{where}: 指紋の欄が空欄"
                                f"(記録が無いなら {NONE_MARK} と書く)")
            if cell["run_id"] in seen:
                raise ReadError(f"{where}: 同じ実行 id が 2 行ある({cell['run_id']})")
            seen.add(cell["run_id"])
            tallies: list[tuple[str, int | None]] = []
            for field in DIFF_FIELDS:
                v, ok = read_tally(cell[field])
                if not ok:
                    pending.append(Pending(
                        STOP_REASONS[4],
                        f"{where}: {field} = {cell[field] or '空欄'}"))
                tallies.append((field, v))
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0], f"{where}: {cell['run_id']}"))
            items.append(Run(run_id=cell["run_id"], seq=seq, status=cell["status"],
                             tallies=tuple(tallies),
                             raw=tuple((f, cell[f]) for f in DIFF_FIELDS),
                             fingerprint=cell["fingerprint"], source=cell["source"]))
        if not items:
            raise ReadError("実行の記録の台帳に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    @property
    def ordered(self) -> tuple[Run, ...]:
        """**順序番号だけで並べる**(行の順も時刻も見ない)。"""
        return tuple(sorted(self.items, key=lambda r: (r.seq, r.run_id)))

    def of(self, run_id: str) -> Run | None:
        return next((r for r in self.items if r.run_id == run_id), None)

    @property
    def span(self) -> str:
        """対象の期間 = **入力の順序番号の最小と最大をそのまま写す**(推測しない)。"""
        seqs = [r.seq for r in self.items]
        return f"順序番号 {min(seqs)}〜{max(seqs)}"

    def issues(self, fields: Fields, statuses: Statuses) -> list[Pending]:
        out: list[Pending] = []
        for field in DIFF_FIELDS:
            if fields.of(field) is None:
                out.append(Pending(STOP_REASONS[1], f"欄名 {field}"))
        seqs = sorted(r.seq for r in self.items)
        if len(set(seqs)) != len(seqs):
            dup = sorted({s for s in seqs if seqs.count(s) > 1})
            out.append(Pending(STOP_REASONS[3],
                               "重複した順序番号 " + " / ".join(str(s) for s in dup)))
        elif seqs != list(range(seqs[0], seqs[0] + len(seqs))):
            gaps = [str(s + 1) for s, t in zip(seqs, seqs[1:]) if t != s + 1]
            out.append(Pending(STOP_REASONS[3], "飛んだ順序番号 " + " / ".join(gaps)))
        for r in self.ordered:
            if statuses.of(r.status) is None:
                out.append(Pending(STOP_REASONS[2],
                                   f"{r.run_id}: {r.status or '空欄'}"))
        lengths = sorted({len(r.fingerprint) for r in self.items
                          if not r.missing_fingerprint})
        if len(lengths) > 1:
            out.append(Pending(STOP_REASONS[5],
                               "指紋の長さ " + " / ".join(str(n) for n in lengths)))
        return out

    def rewritten(self, run_id: str, fingerprint: str) -> "Runs":
        """指紋を 1 つ書き換えた写し(**メモリの中だけ**)。"""
        return Runs(items=tuple(
            Run(r.run_id, r.seq, r.status, r.tallies, r.raw, fingerprint, r.source)
            if r.run_id == run_id else r for r in self.items),
            pending=self.pending, path=self.path)

    def bumped(self, run_id: str, field: str) -> "Runs":
        """件数を 1 件増やした写し(**メモリの中だけ**)。"""
        out: list[Run] = []
        for r in self.items:
            if r.run_id != run_id:
                out.append(r)
                continue
            now = r.value(field)
            if now is None:
                raise ReadError(f"{run_id}: {field} は {NONE_MARK} なので増やせない")
            tallies = tuple((f, now + 1 if f == field else v) for f, v in r.tallies)
            raw = tuple((f, str(now + 1) if f == field else v) for f, v in r.raw)
            out.append(Run(r.run_id, r.seq, r.status, tallies, raw, r.fingerprint,
                           r.source))
        return Runs(items=tuple(out), pending=self.pending, path=self.path)

    def swapped(self, how: str) -> "Runs":
        return Runs(items=tuple(swap_rows(list(self.items), how)),
                    pending=self.pending, path=self.path)


# ------------------------------------------------------------ 対を作る


@dataclass(frozen=True)
class Pair:
    """回の対 1 つ。**2 経路の値と差を並べるだけで、正しい方を決めない。**"""
    before: Run
    after: Run
    value: str
    back_to: tuple[str, ...] = ()
    reason: str = NOT_DECLARED

    @property
    def name(self) -> str:
        return f"{self.before.run_id}>{self.after.run_id}"

    @property
    def tally_route(self) -> str:
        """経路A(差分の記録)の値。**原文の表記のまま写す。**"""
        return " / ".join(f"{f}={self.after.written(f) or '空欄'}"
                          for f in DIFF_FIELDS)

    @property
    def fp_route(self) -> str:
        """経路B(出力の指紋)の値。**先頭 12 文字の写しと、同じか違うかだけ。**"""
        if self.after.missing_fingerprint or self.before.missing_fingerprint:
            return NONE_MARK
        same = self.after.fingerprint == self.before.fingerprint
        return f"{self.after.head}({'前の回と同じ' if same else '前の回と違う'})"

    @property
    def gap(self) -> str:
        """2 経路の差。**どちらが正しいかは言わない**(食い違っている形だけ)。"""
        if self.value in (MUTSU[0], MUTSU[3]):
            return "2 経路が同じ答え"
        if self.value in (MUTSU[4], MUTSU[5]):
            return "片方の欄が " + NONE_MARK
        return "2 経路が別の答え"

    def line(self) -> str:
        return (f"{self.name}:{self.value}:{self.tally_route}:{self.fp_route}"
                f":{self.gap}:{'/'.join(self.back_to)}:{self.reason}")

    def as_dict(self) -> dict[str, object]:
        return {"対": f"{self.before.run_id} → {self.after.run_id}",
                "順序番号": f"{self.before.seq} → {self.after.seq}",
                "結果記号(後の回)": self.after.status,
                "経路A(差分の記録)": self.tally_route,
                "経路A の出典": self.after.source,
                "経路B(出力の指紋)": self.fp_route,
                "経路B の出典": self.after.source,
                "差": self.gap,
                "判定": self.value,
                "戻りの印(一致した run id)": list(self.back_to),
                "差が生じる既知の理由": self.reason}


def judge(before: Run, after: Run, earlier: tuple[Run, ...],
          reasons: Reasons) -> Pair:
    """回の対 1 つに 6 値のどれか 1 つを付ける。**どちらの経路が正しいかは決めない。**

    上から順に見る。差分の欄に `記載なし` が在れば、そこで終わり(本番の出力を差し替えて
    いない回の形)。どちらかの指紋が `記載なし` でも終わり。そこから先で、はじめて差分の
    3 欄が 0 かを見て、指紋の文字列を比べる(**計算はしない**)。
    """
    reason = reasons.of(before.run_id, after.run_id)
    if after.missing_tally:
        return Pair(before, after, MUTSU[4], reason=reason)
    if after.missing_fingerprint or before.missing_fingerprint:
        return Pair(before, after, MUTSU[5], reason=reason)
    same = after.fingerprint == before.fingerprint
    zero = after.zero_tally
    value = MUTSU[0] if (zero and same) else (
        MUTSU[1] if (zero and not same) else (
            MUTSU[2] if same else MUTSU[3]))
    back: tuple[str, ...] = ()
    if not same:        # **前の回でなく過去のどれかの回と同じ文字列なら戻りの印**
        back = tuple(sorted(r.run_id for r in earlier
                            if not r.missing_fingerprint
                            and r.fingerprint == after.fingerprint))
    return Pair(before, after, value, back_to=back, reason=reason)


@dataclass(frozen=True)
class Report:
    ok: bool
    pending: tuple[Pending, ...]
    runs: int
    stocks: int
    fields: int
    statuses: int
    reasons: int


@dataclass(frozen=True)
class Tally:
    report: Report
    pairs: tuple[Pair, ...]
    runs: Runs
    stocks: Stocks
    fields: Fields
    statuses: Statuses
    reasons: Reasons

    # ---------------- 分母

    def run_denominator(self) -> int:
        return self.report.runs

    def pair_denominator(self) -> int:
        return max(self.report.runs - 1, 0) if self.report.ok else 0

    # ---------------- 件数

    def six(self) -> dict[str, int]:
        return {k: sum(1 for p in self.pairs if p.value == k) for k in MUTSU}

    def backs(self) -> list[dict[str, object]]:
        """戻りの印の一覧。**一致した run id をそのまま出す**(良し悪しは書かない)。"""
        return [{"対": f"{p.before.run_id} → {p.after.run_id}",
                 "判定": p.value,
                 "一致した run id": list(p.back_to),
                 "指紋(先頭 12 文字)": p.after.head,
                 "経路A(差分の記録)": p.tally_route,
                 "差が生じる既知の理由": p.reason,
                 "出典": p.after.source}
                for p in self.pairs if p.back_to]

    def by_status(self) -> list[dict[str, object]]:
        """結果記号ごとの内訳(**数えるのは回の数**。合計が回の件数に戻るのが検算)。

        台帳に出てくる結果記号を全て並べる(**登録表に無い記号も 1 行として出す**)。
        """
        out: list[dict[str, object]] = []
        for name in sorted({r.status for r in self.runs.items}):
            here = [r for r in self.runs.ordered if r.status == name]
            s = self.statuses.of(name)
            out.append({"結果記号": name or "(空欄)",
                        "登録表に在るか": "在る" if s else "無い",
                        "本番の出力を差し替えるか": s.replaces if s else "",
                        "累積に入れるか": s.cumulative if s else "",
                        "回の数": len(here),
                        "run id": [r.run_id for r in here]})
        return out

    # ---------------- 累積

    def cumulative(self) -> dict[str, object]:
        """累積の突合を 1 行。**差の値だけを出し、どちらが正しいかは言わない。**

        足すのは欄の登録表で `増やす` / `減らす` と宣言された欄だけで、`動かさない` と
        宣言された欄が入る経路は無い。`記載なし` の欄は足さない(0 と読まない)。
        """
        plus, minus = self.fields.moving(MOVES[0]), self.fields.moving(MOVES[1])
        counted = set(self.statuses.counted())
        total = 0
        used: list[str] = []
        for r in self.runs.ordered:
            if r.status not in counted:
                continue
            moved = False
            for f in plus:
                v = r.value(f)
                if v is not None:
                    total += v
                    moved = True
            for f in minus:
                v = r.value(f)
                if v is not None:
                    total -= v
                    moved = True
            if moved:
                used.append(r.run_id)
        stock = self.stocks.last
        return {"累積に入れると宣言された結果記号": list(self.statuses.counted()),
                "累積に足した回": used,
                "足した欄": list(plus), "引いた欄": list(minus),
                "累積に入る経路が無い欄": [f.field for f in self.fields.items
                                           if f.moves == MOVES[2]],
                "累積(増やす欄の和 - 減らす欄の和)": total,
                "突合に使った棚卸しの時点記号": stock.asof,
                "棚卸しが宣言している行数": stock.rows,
                "棚卸しが宣言している rule 数": stock.rules,
                "棚卸しの出典": stock.source,
                "単位": self.fields.unit_of(DIFF_FIELDS[0]),
                "対象の期間": self.runs.span,
                "突合": MATCH if total == stock.rows else DIFFER,
                "差(棚卸しの宣言 - 累積)": stock.rows - total}

    def unused_stocks(self) -> list[dict[str, object]]:
        """突合に使っていない棚卸しの時点(**黙って落とさずに並べる**)。"""
        last = self.stocks.last.asof
        return [{"時点記号": s.asof, "宣言された行数": s.rows,
                 "宣言された rule 数": s.rules, "出典": s.source}
                for s in self.stocks.ordered if s.asof != last]

    # ---------------- 一覧

    def listed(self) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for k in MUTSU:
            here = [p for p in self.pairs if p.value == k]
            out.append({"判定": k, "件数": len(here),
                        "対": [p.as_dict() for p in here]})
        return out

    def split_pairs(self) -> list[dict[str, object]]:
        """2 経路が別の答えを返した対の一覧(**②と③だけ**)。"""
        return [p.as_dict() for p in self.pairs if p.value in (MUTSU[1], MUTSU[2])]

    def missing_side(self) -> list[dict[str, object]]:
        """片方の欄が `記載なし` の対の一覧(**⑤と⑥だけ**)。"""
        return [p.as_dict() for p in self.pairs if p.value in (MUTSU[4], MUTSU[5])]

    def dangling_reasons(self) -> list[dict[str, object]]:
        """どの対にも当たらない理由の宣言(= 隣り合っていない対を指す宣言)。**止めずに並べる。**"""
        made = {(p.before.run_id, p.after.run_id) for p in self.pairs}
        return [{"指している対": f"{r.from_run} → {r.to_run}", "理由コード": r.reason,
                 "出典": r.source}
                for r in self.reasons.ordered
                if (r.from_run, r.to_run) not in made]

    def units(self) -> list[dict[str, str]]:
        """2 経路の単位(**この 2 つを足す経路が無いことを記号で示す**)。"""
        return ([{"経路": "A(差分の記録)", "欄名": f.field,
                  "行数を動かすか": f.moves, "単位記号": f.unit, "出典": f.source}
                 for f in sorted(self.fields.items, key=lambda x: x.field)]
                + [{"経路": "B(出力の指紋)", "欄名": "fingerprint",
                    "行数を動かすか": MOVES[2], "単位記号": FP_UNIT,
                    "出典": "この部品の規約(指紋は文字列の一致だけを見る)"}])

    def stopped(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for p in self.report.pending:
            out[p.reason] = out.get(p.reason, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: STOP_REASONS.index(kv[0])))

    # ---------------- まとめ

    def counts(self) -> dict[str, object]:
        """件数を、分母の内訳つきで出す。**正しい経路も一致率も返さない。**"""
        six = self.six()
        out: dict[str, object] = {
            "実行の記録の台帳の行数": self.report.runs,
            "棚卸しの台帳の行数": self.report.stocks,
            "欄の登録表の行数": self.report.fields,
            "結果記号の登録表の行数": self.report.statuses,
            "差の理由の宣言表の行数": self.report.reasons,
            "分母(回の件数)": self.run_denominator(),
            "分母(回の対の件数)": self.pair_denominator(),
            "対象の期間": self.runs.span,
            "6 値": six,
            "2 経路が別の答えを返した対": six[MUTSU[1]] + six[MUTSU[2]],
            "片方の欄が記載なしの対": six[MUTSU[4]] + six[MUTSU[5]],
            "戻りの印": len(self.backs()),
            "結果記号ごと": self.by_status(),
            "2 経路の単位": self.units(),
            "累積の突合": self.cumulative(),
            "突合に使っていない棚卸しの時点": len(self.unused_stocks()),
            "どの対にも当たらない理由の宣言": len(self.dangling_reasons()),
            "理由別の止まった件数": self.stopped(),
            "読んだか": ("読んだ" if self.pairs else
                         "読んでいない(対を作る前に止まったので 6 値は全て 0)"),
        }
        out["分母に含めたもの"] = (
            f"回 {self.run_denominator()} 件を順序番号で並べ、隣り合う対 "
            f"{self.pair_denominator()} 件に 6 値が付く。内訳は "
            + " + ".join(f"{k} {six[k]}" for k in MUTSU))
        out["件数の合計の検算"] = (
            f"6 値の合計 {sum(six.values())} / 回の対の件数 "
            f"{self.pair_denominator()}(結果記号ごとの内訳の合計 "
            f"{sum(int(r['回の数']) for r in self.by_status())} = 回の件数 "
            f"{self.run_denominator()} も同じ)")
        out["正しい経路を決めない"] = (
            "この出力に「正しい経路」「信頼できる方」「一致率」の欄が無い。2 経路の値と、"
            "食い違っている形だけを並べる(どちらを直すかは台帳を持つ人が決める)")
        out["差の原因を推定しない"] = (
            "理由は差の理由の宣言表の写しだけ。宣言が無ければ「" + NOT_DECLARED
            + "」で、原因を当てる辞書も regex も持たない")
        out["単位と期間を先に宣言させる"] = (
            "欄ごとの単位記号が登録の 2 つでなければ表として読めない。対象の期間は入力の"
            "順序番号の最小と最大をそのまま写し、推測で広げない")
        out["ハッシュを計算しない"] = (
            "指紋は入力の文字列を比べるだけ。file を読んで hash にする経路が無く、"
            "hashlib を呼ぶのは判定部分の sha256 の 1 か所だけ")
        out["中身が替わった行数を累積に足さない"] = (
            "累積に入るのは欄の登録表で「" + MOVES[0] + "」「" + MOVES[1]
            + "」と宣言された欄だけ。「" + MOVES[2] + "」と宣言された欄が入る経路が無い")
        out["指紋から行数を推測しない"] = (
            "指紋は文字列の一致しか見ない。行数から指紋を作る経路も、指紋から行数を"
            "読む経路も無い")
        out["成功率を出さない"] = (
            "落ちた回の仕分けと成功率はこの部品の領分でない。結果記号ごとの回の数を"
            "そのまま並べるだけ")
        out["周期を読まない"] = (
            "入力に日付の列も時刻の列も無く、宣言された周期と比べる経路が無い")
        out["検証の件数を分解しない"] = (
            "入るのは実行の記録の件数だけ。検証の報告の件数を層へ分けるのは別の部品")
        out["どの行を出し直すかを決めない"] = (
            "出し直す範囲の欄が無い。2 経路が別の答えを返した対を並べるところまで")
        out["差分の中身の値を読まない"] = (
            "入力に差分の中身の列が無い。実在の料率・金額が入る欄そのものを持たない")
        out["現在時刻を読まない"] = (
            "入力に日付の列も時刻の列も無く、現在時刻を読む呼び出しも持たない")
        out["pipeline を走らせない"] = (
            "実行の記録を読むだけで、pipeline を動かす経路も通信の経路も無い")
        out["入力を書き換えない"] = (
            "verify が作る写し(指紋を書き換えた表・件数を増やした表・累積の宣言を替えた"
            "表)はメモリの中だけで、入力の CSV には 1 文字も書かない")
        return out

    def judgement_bytes(self) -> bytes:
        """判定部分 = 対ごとの判定と 2 経路の値。時刻・絶対パスは入れない。"""
        self._guard()
        c = self.cumulative()
        lines = ["\t".join(["件", str(self.report.runs), str(self.report.stocks),
                            str(self.report.fields), str(self.report.statuses),
                            str(self.report.reasons)])]
        lines.extend(p.line() for p in self.pairs)
        lines.append("\t".join(["累", str(c["累積(増やす欄の和 - 減らす欄の和)"]),
                                str(c["棚卸しが宣言している行数"]), str(c["突合"]),
                                str(c["差(棚卸しの宣言 - 累積)"])]))
        return ("\n".join(lines) + "\n").encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.judgement_bytes()).hexdigest()

    def read_condition(self) -> dict[str, str]:
        return dict(zip(SCOPE_KEYS, (self.runs.path, self.stocks.path,
                                     self.fields.path, self.statuses.path,
                                     self.reasons.path)))

    def _guard(self) -> None:
        if not self.report.ok:
            raise RuntimeError("止まっているので作った対は無い。"
                               "report.pending の理由コードを見る")


def diff_tally(runs: Runs, stocks: Stocks, fields: Fields, statuses: Statuses,
               reasons: Reasons) -> Tally:
    """順序番号で隣り合う回の対ごとに 6 値を付け、戻りの印と累積の突合を返す。

    5 枚のどれかが 1 行でも壊れていたら 1 対も数えない(6 値は全て 0)。
    """
    pending = (list(runs.pending) + list(stocks.pending) + list(fields.pending)
               + list(statuses.pending) + list(reasons.pending))
    pending.extend(runs.issues(fields, statuses))
    pending.extend(Pending(STOP_REASONS[7], f"{r.from_run} → {r.to_run}")
                   for r in reasons.ordered
                   if runs.of(r.from_run) is None or runs.of(r.to_run) is None)
    report = Report(not pending, tuple(pending), len(runs.items), len(stocks.items),
                    len(fields.items), len(statuses.items), len(reasons.items))
    if pending:                 # 1 対も数えずに止まる
        return Tally(report, (), runs, stocks, fields, statuses, reasons)

    order = runs.ordered
    pairs = tuple(judge(order[i - 1], order[i], order[:i - 1], reasons)
                  for i in range(1, len(order)))
    return Tally(report, pairs, runs, stocks, fields, statuses, reasons)


# ------------------------------------------------------------ verify


def moved_elsewhere(first: Tally, after: Tally, *keep: str) -> list[str]:
    """判定が動いた対のうち、動くはずだった対でないものの名前。"""
    before = {p.name: f"{p.value}:{'/'.join(p.back_to)}" for p in first.pairs}
    now = {p.name: f"{p.value}:{'/'.join(p.back_to)}" for p in after.pairs}
    return sorted(k for k in before if k not in keep and before[k] != now.get(k, ""))


def fingerprint_probe_plan(first: Tally) -> Pair | None:
    """指紋を前の回と同じにする相手を決める(= ④ の対で、後の回が最後の回のもの)。"""
    last = max((r.seq for r in first.runs.items), default=0)
    return next((p for p in first.pairs
                 if p.value == MUTSU[3] and p.after.seq == last), None)


def fingerprint_probe(runs: Runs, stocks: Stocks, fields: Fields,
                      statuses: Statuses, reasons: Reasons,
                      first: Tally) -> dict[str, object]:
    """**ある回の指紋を前の回と同じ文字列に替えると、その対が ④ から ③ へ移る。**

    累積の突合の数は変わらない(= 指紋と累積が別経路であることの物理形)。
    """
    plan = fingerprint_probe_plan(first)
    if plan is None:
        return {"合うか": True, "書き換えた run id": "",
                "観測": "最後の回が ④ の対でないので、この写しは作らない"}
    after = diff_tally(runs.rewritten(plan.after.run_id, plan.before.fingerprint),
                       stocks, fields, statuses, reasons)
    if not after.report.ok:
        return {"合うか": False, "書き換えた run id": plan.after.run_id,
                "観測": "写しが止まった(理由コードを見る)"}
    now = next(p for p in after.pairs if p.after.run_id == plan.after.run_id)
    moved = moved_elsewhere(first, after, plan.name)
    before_c, after_c = first.cumulative(), after.cumulative()
    ok = (now.value == MUTSU[2] and not now.back_to and not moved
          and before_c["累積(増やす欄の和 - 減らす欄の和)"]
          == after_c["累積(増やす欄の和 - 減らす欄の和)"]
          and before_c["差(棚卸しの宣言 - 累積)"] == after_c["差(棚卸しの宣言 - 累積)"]
          and first.six()[MUTSU[3]] - 1 == after.six()[MUTSU[3]]
          and first.six()[MUTSU[2]] + 1 == after.six()[MUTSU[2]])
    return {"合うか": ok, "書き換えた run id": plan.after.run_id,
            "書き換えた対": plan.name,
            "判定(前)": plan.value, "判定(後)": now.value,
            "戻りの印(後)": list(now.back_to),
            "ほかで動いた対": moved,
            "6 値(後)": after.six(),
            "累積(前)": before_c["累積(増やす欄の和 - 減らす欄の和)"],
            "累積(後)": after_c["累積(増やす欄の和 - 減らす欄の和)"],
            "差(前)": before_c["差(棚卸しの宣言 - 累積)"],
            "差(後)": after_c["差(棚卸しの宣言 - 累積)"]}


def changed_probe_plan(first: Tally) -> str | None:
    """中身が替わった行数を 1 件増やす相手を決める(= すでに 1 件以上ある回)。"""
    counted = set(first.statuses.counted())
    return next((r.run_id for r in first.runs.ordered
                 if r.status in counted and (r.value(DIFF_FIELDS[2]) or 0) >= 1), None)


def changed_probe(runs: Runs, stocks: Stocks, fields: Fields, statuses: Statuses,
                  reasons: Reasons, first: Tally) -> dict[str, object]:
    """**中身が替わった行数を 1 件増やしても、累積の突合の差は変わらない。**"""
    target = changed_probe_plan(first)
    if target is None:
        return {"合うか": True, "増やした run id": "",
                "観測": "中身が替わった行数が 1 件以上の回が無いので、この写しは作らない"}
    before_n = next(r.value(DIFF_FIELDS[2]) for r in runs.items
                    if r.run_id == target)
    after = diff_tally(runs.bumped(target, DIFF_FIELDS[2]), stocks, fields, statuses,
                       reasons)
    if not after.report.ok:
        return {"合うか": False, "増やした run id": target,
                "観測": "写しが止まった(理由コードを見る)"}
    before_c, after_c = first.cumulative(), after.cumulative()
    moved = moved_elsewhere(first, after)
    ok = (not moved and first.six() == after.six()
          and before_c["累積(増やす欄の和 - 減らす欄の和)"]
          == after_c["累積(増やす欄の和 - 減らす欄の和)"]
          and before_c["差(棚卸しの宣言 - 累積)"] == after_c["差(棚卸しの宣言 - 累積)"])
    return {"合うか": ok, "増やした run id": target, "増やした欄": DIFF_FIELDS[2],
            "増やす前の件数": before_n, "増やした後の件数": (before_n or 0) + 1,
            "ほかで動いた対": moved,
            "6 値は不変か": first.six() == after.six(),
            "累積(前)": before_c["累積(増やす欄の和 - 減らす欄の和)"],
            "累積(後)": after_c["累積(増やす欄の和 - 減らす欄の和)"],
            "差(前)": before_c["差(棚卸しの宣言 - 累積)"],
            "差(後)": after_c["差(棚卸しの宣言 - 累積)"]}


def include_probe_plan(runs: Runs, statuses: Statuses) -> str | None:
    """累積の宣言を替える相手を決める(= `入れない` で、件数が読める回を持つ結果記号)。"""
    for s in sorted(statuses.items, key=lambda x: x.status):
        if s.cumulative != CUMULATIVE[1]:
            continue
        here = [r for r in runs.ordered if r.status == s.status]
        if any(r.value(f) is not None for r in here for f in DIFF_FIELDS):
            return s.status
    return None


def include_probe(runs: Runs, stocks: Stocks, fields: Fields, statuses: Statuses,
                  reasons: Reasons, first: Tally) -> dict[str, object]:
    """**累積の宣言を `入れない` から `入れる` に替えると累積だけが動き、6 値は変わらない。**

    = 累積の定義が結果記号の登録表の側に在ることの物理形。
    """
    target = include_probe_plan(runs, statuses)
    if target is None:
        return {"合うか": True, "替えた結果記号": "",
                "観測": "`入れない` で件数が読める回を持つ結果記号が無いので、"
                        "この写しは作らない"}
    after = diff_tally(runs, stocks, fields,
                       statuses.flipped(target, CUMULATIVE[0]), reasons)
    if not after.report.ok:
        return {"合うか": False, "替えた結果記号": target,
                "観測": "写しが止まった(理由コードを見る)"}
    before_c, after_c = first.cumulative(), after.cumulative()
    moved = moved_elsewhere(first, after)
    ok = (not moved and first.six() == after.six()
          and before_c["累積(増やす欄の和 - 減らす欄の和)"]
          != after_c["累積(増やす欄の和 - 減らす欄の和)"]
          and before_c["突合"] != after_c["突合"])
    return {"合うか": ok, "替えた結果記号": target,
            "替えた先": CUMULATIVE[0],
            "ほかで動いた対": moved,
            "6 値は不変か": first.six() == after.six(),
            "累積に足した回(前)": before_c["累積に足した回"],
            "累積に足した回(後)": after_c["累積に足した回"],
            "累積(前)": before_c["累積(増やす欄の和 - 減らす欄の和)"],
            "累積(後)": after_c["累積(増やす欄の和 - 減らす欄の和)"],
            "突合(前)": before_c["突合"], "突合(後)": after_c["突合"],
            "差(前)": before_c["差(棚卸しの宣言 - 累積)"],
            "差(後)": after_c["差(棚卸しの宣言 - 累積)"]}


def verify(runs: Runs, stocks: Stocks, fields: Fields, statuses: Statuses,
           reasons: Reasons) -> dict[str, object]:
    """5 つ見る。二度走りの sha256 / 5 枚の行順の入れ替え / 合計の検算 /
    指紋を前の回と同じにした写し / 累積の 2 つの写し。"""
    first = diff_tally(runs, stocks, fields, statuses, reasons)
    if not first.report.ok:
        return {"ok": False, "stage": "止まった(作った対は返さない)", **first.counts(),
                "pending": [p.as_dict() for p in first.report.pending]}
    second = diff_tally(runs, stocks, fields, statuses, reasons)
    pending: list[Pending] = []
    if first.sha256() != second.sha256():
        pending.append(Pending(STOP_REASONS[9], f"2 回目 {second.sha256()[:12]}"))
    swapped: dict[str, str] = {}
    for how in SWAPS:
        third = diff_tally(runs.swapped(how), stocks.swapped(how), fields.swapped(how),
                           statuses.swapped(how), reasons.swapped(how))
        swapped[how] = third.sha256() if third.report.ok else ""
        if not (third.report.ok and first.sha256() == third.sha256()):
            pending.append(Pending(STOP_REASONS[10],
                                   f"入れ替え方 {how} で {swapped[how] or '止まった'}"))
    six = first.six()
    if sum(six.values()) != first.pair_denominator():
        pending.append(Pending(STOP_REASONS[8],
                               f"6 値の合計 {sum(six.values())} / 回の対の件数 "
                               f"{first.pair_denominator()}"))
    by_status = sum(int(r["回の数"]) for r in first.by_status())
    if by_status != first.run_denominator():
        pending.append(Pending(STOP_REASONS[8],
                               f"結果記号ごとの内訳の合計 {by_status} / 回の件数 "
                               f"{first.run_denominator()}"))
    out: dict[str, object] = {
        "ok": not pending, "読んだ回数": 2, "入れ替え方": list(SWAPS),
        "sha256": first.sha256(), "2 回目の sha256": second.sha256(),
        "入れ替えた 5 枚の sha256": swapped,
        "件数の検算": {"6 値": six, "合計": sum(six.values()),
                       "結果記号ごとの内訳の合計": by_status,
                       "分母(回の件数)": first.run_denominator(),
                       "分母(回の対の件数)": first.pair_denominator(),
                       "戻りの印": len(first.backs())},
        "指紋を前の回と同じにした写し":
            fingerprint_probe(runs, stocks, fields, statuses, reasons, first),
        "中身が替わった行数を 1 件増やした写し":
            changed_probe(runs, stocks, fields, statuses, reasons, first),
        "累積の宣言を入れるに替えた写し":
            include_probe(runs, stocks, fields, statuses, reasons, first),
    }
    for key in ("指紋を前の回と同じにした写し", "中身が替わった行数を 1 件増やした写し",
                "累積の宣言を入れるに替えた写し"):
        if not out[key]["合うか"]:        # type: ignore[index]
            pending.append(Pending(STOP_REASONS[8], f"{key} の件数が合わない"))
            out["ok"] = False
    if pending:
        out["観測"] = ("同じ表から違うバイト列が出た、または件数が合わない(平均も多数決も"
                       "しない。どちらの経路が正しいかも当てない)")
        out["pending"] = [p.as_dict() for p in pending]
    return out


# ------------------------------------------------------------ ひな型

T_LOG = "合成の実行履歴のメモ(架空)L1"
T_STOCK = "合成の収録範囲のメモ(架空)L1"
T_WORD = "合成の登録のメモ(架空)L1"
T_REASON = "合成の理由のメモ(架空)L1"

TEMPLATE_RUNS = [
    list(RUN_COLUMNS),
    ["R01", "1", "S1", "1301", "0", "0", "a" * 20, T_LOG],
    ["R02", "2", "S1", "0", "0", "0", "a" * 20, T_LOG],
    ["R03", "3", "S2", NONE_MARK, NONE_MARK, NONE_MARK, NONE_MARK, T_LOG],
]
TEMPLATE_STOCKS = [
    list(STOCK_COLUMNS),
    ["A1", "1301", "15", T_STOCK],
]
TEMPLATE_FIELDS = [
    list(FIELD_COLUMNS),
    ["added", MOVES[0], FIELD_UNITS[0], T_WORD],
    ["removed", MOVES[1], FIELD_UNITS[0], T_WORD],
    ["changed", MOVES[2], FIELD_UNITS[0], T_WORD],
]
TEMPLATE_STATUSES = [
    list(STATUS_COLUMNS),
    ["S1", REPLACES[0], CUMULATIVE[0], T_WORD],
    ["S2", REPLACES[1], CUMULATIVE[1], T_WORD],
]
TEMPLATE_REASONS = [
    list(REASON_COLUMNS),
    ["R02", "R03", "上流の値を崩した試験の回", T_REASON],
]


def write_csv(path: Path, rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    return path


def init(dest: str | Path) -> tuple[Path, ...]:
    d = Path(dest)
    return (write_csv(d / "実行の記録の台帳.csv", TEMPLATE_RUNS),
            write_csv(d / "棚卸しの台帳.csv", TEMPLATE_STOCKS),
            write_csv(d / "欄の登録表.csv", TEMPLATE_FIELDS),
            write_csv(d / "結果記号の登録表.csv", TEMPLATE_STATUSES),
            write_csv(d / "差の理由の宣言表.csv", TEMPLATE_REASONS))


# ------------------------------------------------------------ CLI

def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def build_parser() -> argparse.ArgumentParser:
    """CLI は pairs / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = argparse.ArgumentParser(prog="diff_tally",
                                 description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in SUBCOMMANDS[:3]:
        p = sub.add_parser(name)
        for arg in ("runs", "stocks", "fields", "statuses", "reasons"):
            p.add_argument(arg)
    sub.add_parser(SUBCOMMANDS[3]).add_argument("dest")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == "init":
        print("書いた: " + " / ".join(str(p) for p in init(a.dest)))
        return 0
    try:
        five = (Runs.load(a.runs), Stocks.load(a.stocks), Fields.load(a.fields),
                Statuses.load(a.statuses), Reasons.load(a.reasons))
        if a.cmd == "verify":
            out = verify(*five)
            _print(out)
            return 0 if out["ok"] else 3
        t = diff_tally(*five)
    except ReadError as e:
        print(f"表として読めない: {e}", file=sys.stderr)
        return 2
    if not t.report.ok:
        _print({"ok": False, "stage": "止まった(作った対は返さない)", **t.counts(),
                "pending": [p.as_dict() for p in t.report.pending]})
        return 3
    body: dict[str, object] = {"ok": True, **t.counts()}
    if a.cmd == SUBCOMMANDS[0]:
        body["判定ごとの一覧"] = t.listed()
        body["2 経路が別の答えを返した対の一覧"] = t.split_pairs()
        body["片方の欄が記載なしの対の一覧"] = t.missing_side()
        body["戻りの印の一覧"] = t.backs()
        body["突合に使っていない棚卸しの時点の一覧"] = t.unused_stocks()
        body["どの対にも当たらない理由の宣言の一覧"] = t.dangling_reasons()
        body["sha256"] = t.sha256()
        body["読んだ条件"] = t.read_condition()
    _print(body)
    six = t.six()
    clean = (six[MUTSU[1]] == 0 and six[MUTSU[2]] == 0 and six[MUTSU[4]] == 0
             and six[MUTSU[5]] == 0 and not t.backs() and not t.stopped()
             and t.cumulative()["突合"] == MATCH and not t.dangling_reasons())
    return 0 if clean else 3


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
