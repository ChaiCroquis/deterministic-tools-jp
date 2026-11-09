"""asof_reach — 公表時点の列が「当時の知識」の再現にどこまで届くかを、行ごとに 4 値へ分ける。

**公表時点を列に持てば当時の知識を再現できる、と宣言した表でも、その列が実値で埋まっている
行はごく一部で、残りは施行日をそのまま写した仮置きのことがある。しかも仮置きには種類が
あり、施行日で埋めた行・確認済の範囲の先頭で埋めた行・公布日で埋めた行で、`as_of` を
戻したときの振る舞いが別々になる。**

この部品は、行の台帳・品質の記号の登録表・問いの台帳・宣言の台帳(4 枚)から、行 1 件ごとに
4 値 + 別枠を付ける。

  (A) 公表の前と後が行で分かれる(品質が `実値`、`known_from` と `valid_from` が別の日)
  (B) `known_from` が `valid_from` と同じ日(`as_of` を戻すと行は消えるが、消えた理由が
      「まだ公表されていない」と「まだ効いていない」の 2 通りあり、どちらとも言えない
      = `見分け不能` の印が付く)
  (C) 境界日は別の日だが、品質が仮置き 3 種のどれか(日付が動いているので (A) と同じ形に
      見えるが実値ではない)
  (D) 知識時間の経路が無い(`known_from` が記載なし / `known_to` が記載なし / 品質が `不明`)

**品質の記号は登録表に在るものだけを使い、日付の形から種類を推測する経路を持たない。**

別枠は 7 枠ある。**6 枠は行に付き、1 枠だけは問いに付く**(分母が行ではなく問いなので、
件数の合計に混ぜない)。

  行に付く 6 = 出典が空 / 品質の記号が登録表に無い / 記号が要求する欄が空 /
               公表が施行の後(遡及の形)なのに公表日が仮置き / 品質が `実値` なのに
               別出典の公表日が空 / `known_to` が閉じているのに同じ値の名前の後続行が
               台帳に無い
  問いに付く 1 = 問いの台帳が指す行 id が行の台帳に無い

**別枠は 4 値より先に当たる。**

持たせていないものが規律になっている。

  - **公表日を推定しない**(暦・版の名前・日付の形から種類を当てる経路が無い)
  - **取りに行かない・走らせない**(実行しない・import しない・構文解析しない・通信の
    経路が無い・入力フォルダの外を読まない)
  - **仮置きを実値へ格上げしない**(品質の記号は登録表から取るだけで、書き換える経路が無い)
  - **正しい側を決めない**(仮置きが誤りだと言う列も、直すべき順位の列も無い)
  - **再現できる率を単独で返さない**(件数には必ず分母が並ぶ)
  - **理由を言い当てない**(理由の欄は注記の写しだけで、空なら `理由の記載なし`)
  - **宣言の文を採点しない**(宣言の台帳の文と、観測の側の件数を並べるだけ)
  - **時計を読まない**(`as_of` と基準日は問いの台帳から来る = 呼ぶ側が渡す)
  - **入力を書き換えない**、**float を使わない**(日数と件数は整数、ほかは文字列)

行の台帳(CSV)の列は 10。

    row_id      行 id(同じ id が 2 行あると止まる)
    value_name  求める値の名前(**判定には使わない**。この文字から品質を推測しない)
    valid_from  効き始める日(ISO の日付。`開` にはできない)
    valid_to    効き終わる日(ISO の日付 / `開` = 開いている / `—` = 記載なし)
    known_from  公表時点の始まり(ISO の日付 / `—` = 記載なし → (D))
    known_to    公表時点の終わり(ISO の日付 / `開` / `—` = 記載なし → (D))
    grade       品質の記号(登録表に在る記号だけ。無ければ別枠へ)
    announced   別出典の公表日(空可。品質が `実値` のとき空だと別枠へ)
    reason      理由の文字列(空可。**原文の写しだけ**。空なら `理由の記載なし`)
    source      出典(ファイル名 + 行番号)。空欄のとき、その行は別枠「出典が空」へ入る

品質の記号の登録表(CSV)の列は 4。**この表だけが仮置きの種類を決める。**

    grade     記号(同じ記号が 2 行あると読めない)
    means     意味(`実値` / `施行日で仮置き` / `範囲の先頭で仮置き` / `公布日で仮置き` /
              `不明`。ほかの語が在ると止まる)
    requires  その記号が要求する欄(`別出典の公表日` / `理由の文字列` / `—`)
    source    出典。空欄のとき 1 行も数えずに止まる

問いの台帳(CSV)の列は 5。**`as_of` と基準日は、この表から来る。**

    ask_id      問い id(同じ id が 2 行あると読めない)
    row_id      行 id(行の台帳に無いと別枠 7 へ)
    as_of       渡す as_of(ISO の日付。空だと止まる)
    basis_date  渡す基準日(ISO の日付。空だと止まる)
    source      出典

宣言の台帳(CSV)の列は 4。**この文が正しいかを採点する経路は無い。**

    claim_id  宣言 id(同じ id が 2 行あると読めない)
    text      再現できると書いた文の verbatim
    scope     その文が主張する範囲(`全行` / `一部` / `記載なし`)
    source    出典

止まる理由コード 8 = 登録表の行の出典が空 / 行 id の重複 / 品質の登録表の意味が決めた
5 つの外 / 品質の登録表の要求する欄が決めた 3 つの外 / 日付の欄が ISO の日付でない /
宣言の台帳の範囲が決めた 3 つの外 / 問いの台帳の as_of か渡す基準日が空 / 登録表そのものが空。

使い方:

    python asof_reach.py init ひな型/
    python asof_reach.py check  行.csv 品質.csv 問い.csv 宣言.csv
    python asof_reach.py report 行.csv 品質.csv 問い.csv 宣言.csv
    python asof_reach.py verify 行.csv 品質.csv 問い.csv 宣言.csv
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROW_COLUMNS = ("row_id", "value_name", "valid_from", "valid_to", "known_from",
               "known_to", "grade", "announced", "reason", "source")
GRADE_COLUMNS = ("grade", "means", "requires", "source")
ASK_COLUMNS = ("ask_id", "row_id", "as_of", "basis_date", "source")
CLAIM_COLUMNS = ("claim_id", "text", "scope", "source")

# 品質の意味(**この 5 つの外に意味を作る経路が無い**)
MEANS = ("実値", "施行日で仮置き", "範囲の先頭で仮置き", "公布日で仮置き", "不明")
# 仮置き 3 種(**実値へ格上げする経路が無い**)
KARIOKI = MEANS[1:4]
# 記号が要求する欄(**実値は別出典の公表日、仮置き 3 種は理由の文字列**)
REQUIRES = ("別出典の公表日", "理由の文字列", "—")
# 宣言の文が主張する範囲(**この 3 つの外は止まる**)
SCOPES = ("全行", "一部", "記載なし")

OPEN = "開"          # 開いていると宣言された端
NO_MARK = "—"        # 記載なし(**`開` と同じ値にしない**)
UNCOUNTABLE = "数えられない"
NO_REASON = "理由の記載なし"
UNREGISTERED = "(登録表の外)"
SAME_DAY = "同じ日"
OTHER_DAY = "別の日"
MARK_UNKNOWN = "見分け不能"

# 行 1 件に付く 4 値
VALUES = (
    "(A) 公表の前と後が行で分かれる(公表日が実値で、境界日が別の日)",
    "(B) 境界日が同じ日で、消えた理由が 見分け不能",
    "(C) 境界日は別の日だが、公表日が仮置き",
    "(D) 知識時間の経路が無い",
)
# 別枠 7。**上から順に当たり、4 値より先に当たる。** 7 枠目だけ分母が問いの側。
BETSUWAKU = (
    "出典が空",
    "品質の記号が登録表に無い",
    "記号が要求する欄が空",
    "公表が施行の後(遡及の形)なのに公表日が仮置き",
    "品質が 実値 なのに別出典の公表日が空",
    "known_to が閉じているのに同じ値の名前の後続行が台帳に無い",
    "問いの台帳が指す行 id が行の台帳に無い",
)
ROW_BETSUWAKU = BETSUWAKU[:6]
ASK_BETSUWAKU = BETSUWAKU[6]

# 問い 1 件に返る 3 値(**率にしない**)
VERDICTS = ("出る", "出ない", "言えない")

# 1 行も数えずに止まる理由コード 8
TABLE_REASONS = (
    "登録表の行の出典が空",
    "行 id の重複",
    "品質の登録表の意味が決めた 5 つの外",
    "品質の登録表の要求する欄が決めた 3 つの外",
    "日付の欄が ISO の日付でない",
    "宣言の台帳の範囲が決めた 3 つの外",
    "問いの台帳の as_of か渡す基準日が空",
    "登録表そのものが空",
)
# 行順の入れ替え方(verify が 3 通り試す)
SWAPS = ("逆順", "先頭を末尾へ", "末尾を先頭へ")
SUBCOMMANDS = ("check", "report", "verify", "init")


class ReadError(Exception):
    """表として読めない(列・行・id・参照・期間の端の形が決めた形でない)。"""


@dataclass(frozen=True)
class Pending:
    """止まった理由 1 件(**作った 4 値は返さない**)。"""
    reason: str
    where: str

    def as_dict(self) -> dict[str, str]:
        return {"理由": self.reason, "場所": self.where}


def bad_id(s: str) -> bool:
    return (not s) or s != s.strip() or "," in s


def blank(s: str) -> bool:
    """記載なしか(`—` と空欄を同じに扱う欄のための判定)。"""
    return s in (NO_MARK, "")


def is_open(s: str) -> bool:
    """開いていると宣言された端か(**記載なしと同じ値にしない**)。"""
    return s == OPEN


def as_date(s: str) -> dt.date | None:
    """ISO の日付として読めれば日付、読めなければ None(**暦から推測しない**)。"""
    if blank(s) or is_open(s):
        return None
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        return None


def date_like(s: str) -> bool:
    """日付の欄として形が合っているか(記載なし / 開 / ISO の日付のどれか)。"""
    return blank(s) or is_open(s) or as_date(s) is not None


def swap_rows(rows: list, how: str) -> list:
    if how == SWAPS[0]:
        return list(reversed(rows))
    if how == SWAPS[1] and rows:
        return rows[1:] + rows[:1]
    if how == SWAPS[2] and rows:
        return rows[-1:] + rows[:-1]
    return list(rows)


def _rows_of(text: str, columns: tuple[str, ...], what: str,
             allow_empty: bool = False) -> list[list[str]]:
    r = csv.reader(io.StringIO(text))
    try:
        head = [c.strip() for c in next(r)]
    except StopIteration:
        raise ReadError(f"{what} に見出し行が無い")
    if tuple(head) != columns:
        raise ReadError(f"{what} の列が決めた形と違う: {head}")
    rows = [[c.strip() for c in row] for row in r if any(c.strip() for c in row)]
    for row in rows:
        if len(row) != len(columns):
            raise ReadError(f"{what} に列数の合わない行が在る: {row[:2]}")
    if not rows and not allow_empty:
        raise ReadError(f"{what} に行が無い")
    return rows


# ------------------------------------------------------------ 入力の 4 枚

@dataclass(frozen=True)
class RuleRow:
    row_id: str
    value_name: str
    valid_from: str
    valid_to: str
    known_from: str
    known_to: str
    grade: str
    announced: str
    reason: str
    source: str

    @property
    def reason_text(self) -> str:
        """**入力の文字列を写すだけ。** 空の行には `理由の記載なし` を入れる。"""
        return NO_REASON if blank(self.reason) else self.reason

    @property
    def known_closed(self) -> bool:
        """`known_to` が日付で閉じているか(`開` と記載なしは閉じていない)。"""
        return as_date(self.known_to) is not None

    @property
    def has_known_path(self) -> bool:
        """知識時間の経路が在るか(始まりと終わりの両方が書かれているか)。"""
        return not blank(self.known_from) and not blank(self.known_to)

    def days(self) -> str:
        """境界日の間の日数(整数の日差。**float を使わない**)。"""
        k, v = as_date(self.known_from), as_date(self.valid_from)
        return UNCOUNTABLE if (k is None or v is None) else str((v - k).days)

    def same_day(self) -> str:
        k, v = as_date(self.known_from), as_date(self.valid_from)
        if k is None or v is None:
            return UNCOUNTABLE
        return SAME_DAY if k == v else OTHER_DAY

    def bad_dates(self) -> tuple[str, ...]:
        out: list[str] = []
        if as_date(self.valid_from) is None:
            out.append(f"行 {self.row_id} の valid_from {self.valid_from!r}"
                       "(効き始める日は 開 にも 記載なし にもできない)")
        for name in ("valid_to", "known_from", "known_to"):
            value = getattr(self, name)
            if not date_like(value):
                out.append(f"行 {self.row_id} の {name} {value!r}")
        return tuple(out)


class Rows:
    """行の台帳。**行順を入れ替えても出力が同じになるよう、読んだ順は別に持つ。**"""

    def __init__(self, rows: list[list[str]]) -> None:
        self.rows = [list(r) for r in rows]
        self.items: tuple[RuleRow, ...] = tuple(RuleRow(*r) for r in rows)
        for x in self.items:
            if bad_id(x.row_id):
                raise ReadError(f"行 id が空か区切り文字を含む: {x.row_id!r}")
            if not x.grade:
                raise ReadError(f"品質の記号が空: 行 {x.row_id}")
            lo, hi = as_date(x.valid_from), as_date(x.valid_to)
            if lo is not None and hi is not None and hi < lo:
                raise ReadError(f"期間の端が逆: 行 {x.row_id} の "
                                f"{x.valid_from} → {x.valid_to}")

    @classmethod
    def parse(cls, text: str) -> "Rows":
        return cls(_rows_of(text, ROW_COLUMNS, "行の台帳"))

    @classmethod
    def load(cls, path: str | Path) -> "Rows":
        return cls.parse(Path(path).read_text(encoding="utf-8-sig"))

    def swapped(self, how: str) -> "Rows":
        return Rows(swap_rows(self.rows, how))

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(sorted({x.row_id for x in self.items}))

    def duplicated(self) -> tuple[str, ...]:
        seen: dict[str, int] = {}
        for x in self.items:
            seen[x.row_id] = seen.get(x.row_id, 0) + 1
        return tuple(sorted(k for k, v in seen.items() if v > 1))

    def of(self, row_id: str) -> RuleRow:
        return next(x for x in self.items if x.row_id == row_id)

    def successor(self, row: RuleRow) -> bool:
        """同じ値の名前で、この行の `known_to` 以後に公表された行が台帳に在るか。"""
        end = as_date(row.known_to)
        if end is None:
            return False
        for x in self.items:
            if x.row_id == row.row_id or x.value_name != row.value_name:
                continue
            start = as_date(x.known_from)
            if start is not None and start >= end:
                return True
        return False


@dataclass(frozen=True)
class Grade:
    grade: str
    means: str
    requires: str
    source: str


class Grades:
    """品質の記号の登録表。**この表だけが仮置きの種類を決める。**"""

    what = "品質の記号の登録表"

    def __init__(self, rows: list[list[str]]) -> None:
        self.rows = [list(r) for r in rows]
        self.items: tuple[Grade, ...] = tuple(Grade(*r) for r in rows)
        seen: set[str] = set()
        for x in self.items:
            if not x.grade:
                raise ReadError(f"{self.what} に記号が空の行が在る")
            if x.grade in seen:
                raise ReadError(f"{self.what} に同じ記号が 2 行: {x.grade}")
            seen.add(x.grade)

    @classmethod
    def parse(cls, text: str) -> "Grades":
        return cls(_rows_of(text, GRADE_COLUMNS, cls.what, True))

    @classmethod
    def load(cls, path: str | Path) -> "Grades":
        return cls.parse(Path(path).read_text(encoding="utf-8-sig"))

    def swapped(self, how: str) -> "Grades":
        return Grades(swap_rows(self.rows, how))

    def has(self, grade: str) -> bool:
        return any(x.grade == grade for x in self.items)

    def means_of(self, grade: str) -> str:
        return next((x.means for x in self.items if x.grade == grade), UNREGISTERED)

    def requires_of(self, grade: str) -> str:
        return next((x.requires for x in self.items if x.grade == grade), NO_MARK)

    def bad_means(self) -> tuple[str, ...]:
        return tuple(f"{x.grade} → {x.means!r}" for x in self.items
                     if x.means not in MEANS)

    def bad_requires(self) -> tuple[str, ...]:
        return tuple(f"{x.grade} → {x.requires!r}" for x in self.items
                     if x.requires not in REQUIRES)

    def sourceless(self) -> tuple[str, ...]:
        return tuple(x.grade for x in self.items if not x.source)


@dataclass(frozen=True)
class Ask:
    ask_id: str
    row_id: str
    as_of: str
    basis_date: str
    source: str


class Asks:
    """問いの台帳。**`as_of` と基準日はここから来る(時計を読まない)。**"""

    what = "問いの台帳"

    def __init__(self, rows: list[list[str]]) -> None:
        self.rows = [list(r) for r in rows]
        self.items: tuple[Ask, ...] = tuple(Ask(*r) for r in rows)
        seen: set[str] = set()
        for x in self.items:
            if bad_id(x.ask_id):
                raise ReadError(f"{self.what} の問い id が空か区切り文字を含む: "
                                f"{x.ask_id!r}")
            if x.ask_id in seen:
                raise ReadError(f"{self.what} に同じ問い id が 2 行: {x.ask_id}")
            seen.add(x.ask_id)
            if not x.row_id:
                raise ReadError(f"{self.what} の行 id が空: 問い {x.ask_id}")

    @classmethod
    def parse(cls, text: str) -> "Asks":
        return cls(_rows_of(text, ASK_COLUMNS, cls.what, True))

    @classmethod
    def load(cls, path: str | Path) -> "Asks":
        return cls.parse(Path(path).read_text(encoding="utf-8-sig"))

    def swapped(self, how: str) -> "Asks":
        return Asks(swap_rows(self.rows, how))

    def dateless(self) -> tuple[str, ...]:
        return tuple(f"問い {x.ask_id}" for x in self.items
                     if blank(x.as_of) or blank(x.basis_date))

    def bad_dates(self) -> tuple[str, ...]:
        out: list[str] = []
        for x in self.items:
            for name in ("as_of", "basis_date"):
                value = getattr(x, name)
                if not blank(value) and as_date(value) is None:
                    out.append(f"問い {x.ask_id} の {name} {value!r}")
        return tuple(out)


@dataclass(frozen=True)
class Claim:
    claim_id: str
    text: str
    scope: str
    source: str


class Claims:
    """宣言の台帳。**文が正しいかを採点する経路が無い。**"""

    what = "宣言の台帳"

    def __init__(self, rows: list[list[str]]) -> None:
        self.rows = [list(r) for r in rows]
        self.items: tuple[Claim, ...] = tuple(Claim(*r) for r in rows)
        seen: set[str] = set()
        for x in self.items:
            if bad_id(x.claim_id):
                raise ReadError(f"{self.what} の宣言 id が空か区切り文字を含む: "
                                f"{x.claim_id!r}")
            if x.claim_id in seen:
                raise ReadError(f"{self.what} に同じ宣言 id が 2 行: {x.claim_id}")
            seen.add(x.claim_id)

    @classmethod
    def parse(cls, text: str) -> "Claims":
        return cls(_rows_of(text, CLAIM_COLUMNS, cls.what, True))

    @classmethod
    def load(cls, path: str | Path) -> "Claims":
        return cls.parse(Path(path).read_text(encoding="utf-8-sig"))

    def swapped(self, how: str) -> "Claims":
        return Claims(swap_rows(self.rows, how))

    def bad_scope(self) -> tuple[str, ...]:
        return tuple(f"{x.claim_id} → {x.scope!r}" for x in self.items
                     if x.scope not in SCOPES)

    def sourceless(self) -> tuple[str, ...]:
        return tuple(x.claim_id for x in self.items if not x.source)


# ------------------------------------------------------------ 4 値を付ける

@dataclass(frozen=True)
class Row:
    """行 1 件の結果。**正しい側の列も、直すべき順位の列も無い。**"""
    row_id: str
    value_name: str
    valid_from: str
    valid_to: str
    known_from: str
    known_to: str
    grade: str
    means: str
    announced: str
    reason: str
    same_day: str
    days: str
    value: str
    mark: str

    @property
    def graded(self) -> bool:
        return self.value in VALUES

    @property
    def has_known_path(self) -> bool:
        """4 値のうち (A)(B)(C) = 知識時間の経路が在る行か。"""
        return self.value in VALUES[:3]

    def as_dict(self) -> dict[str, object]:
        return {"行 id": self.row_id, "値の名前": self.value_name,
                "valid_from": self.valid_from, "valid_to": self.valid_to,
                "known_from": self.known_from, "known_to": self.known_to,
                "品質の記号": self.grade, "品質の意味": self.means,
                "別出典の公表日": self.announced or NO_MARK,
                "理由(出典ごと写す)": self.reason,
                "境界日": self.same_day, "境界日の間の日数": self.days,
                "4 値 / 別枠": self.value, "印": self.mark}


def judge(row: RuleRow, grades: Grades, rows: Rows) -> Row:
    """行 1 件に 4 値か別枠を付ける。**別枠が 4 値より先に当たる。**"""
    means = grades.means_of(row.grade)

    def out(value: str, mark: str = NO_MARK) -> Row:
        return Row(row.row_id, row.value_name, row.valid_from, row.valid_to,
                   row.known_from, row.known_to, row.grade, means, row.announced,
                   row.reason_text, row.same_day(), row.days(), value, mark)

    # 別枠(上から順に当たり、4 値より先に当たる)
    if not row.source:
        return out(BETSUWAKU[0])
    if not grades.has(row.grade):
        return out(BETSUWAKU[1])
    if grades.requires_of(row.grade) == REQUIRES[1] and blank(row.reason):
        return out(BETSUWAKU[2])
    k, v = as_date(row.known_from), as_date(row.valid_from)
    if k is not None and v is not None and k > v and means in KARIOKI:
        return out(BETSUWAKU[3])
    if means == MEANS[0] and blank(row.announced):
        return out(BETSUWAKU[4])
    if row.known_closed and not rows.successor(row):
        return out(BETSUWAKU[5])

    # 4 値
    if not row.has_known_path or means == MEANS[4]:
        return out(VALUES[3])
    if row.same_day() == SAME_DAY:
        return out(VALUES[1], MARK_UNKNOWN)
    if means == MEANS[0]:
        return out(VALUES[0])
    return out(VALUES[2])


# ------------------------------------------------------------ 問い 1 件の道

IN_RANGE, OUT_RANGE = "中", "外"
RESTS_REAL = "実値の公表日"
RESTS_KARIOKI = "仮置きの公表日"
RESTS_SAME = "同じ日の境界(見分け不能)"
RESTS_VALID = "有効時間の端"
RESTS_NONE = "知識時間の経路が無い"
RESTS_EXTRA = "別枠(4 値が付いていない行)"
RESTS = (RESTS_REAL, RESTS_VALID, RESTS_SAME, RESTS_KARIOKI, RESTS_NONE,
         RESTS_EXTRA)


@dataclass(frozen=True)
class Reach:
    """問い 1 件の結果。**率にしない(3 値と、どの境界が決めたかだけ)。**"""
    ask_id: str
    row_id: str
    as_of: str
    basis_date: str
    value: str
    knowledge: str
    valid: str
    verdict: str
    rests_on: str

    def as_dict(self) -> dict[str, object]:
        return {"問い id": self.ask_id, "行 id": self.row_id,
                "渡した as_of": self.as_of, "渡した基準日": self.basis_date,
                "行の 4 値 / 別枠": self.value,
                "知識時間の中か": self.knowledge, "有効時間の中か": self.valid,
                "答え": self.verdict, "答えが乗っているもの": self.rests_on}


def _within(start: str, end: str, when: dt.date) -> str:
    """`when` がその期間の中か(端は始まりを含み、終わりを含まない)。"""
    lo, hi = as_date(start), as_date(end)
    if lo is None or when < lo:
        return OUT_RANGE
    if hi is not None and when >= hi:
        return OUT_RANGE
    return IN_RANGE


def reach_of(ask: Ask, row: Row, raw: RuleRow) -> Reach:
    """問い 1 件に 3 値を付ける。**答えが仮置きに乗っているときは `言えない`。**"""
    as_of = as_date(ask.as_of)
    basis = as_date(ask.basis_date)
    if not row.graded or row.value == VALUES[3] or as_of is None or basis is None:
        rests = RESTS_NONE if row.graded else RESTS_EXTRA
        return Reach(ask.ask_id, ask.row_id, ask.as_of, ask.basis_date, row.value,
                     UNCOUNTABLE, UNCOUNTABLE, VERDICTS[2], rests)
    knowledge = _within(raw.known_from, raw.known_to, as_of)
    valid = _within(raw.valid_from, raw.valid_to, basis)
    if knowledge == OUT_RANGE:
        if row.value == VALUES[1]:
            rests = RESTS_SAME
        elif row.value == VALUES[2]:
            rests = RESTS_KARIOKI
        else:
            rests = RESTS_REAL
        verdict = VERDICTS[1] if rests == RESTS_REAL else VERDICTS[2]
    else:
        verdict = VERDICTS[0] if valid == IN_RANGE else VERDICTS[1]
        rests = RESTS_VALID
    return Reach(ask.ask_id, ask.row_id, ask.as_of, ask.basis_date, row.value,
                 knowledge, valid, verdict, rests)


# ------------------------------------------------------------ 表 1 枚ぶんの結果

@dataclass(frozen=True)
class Report:
    ok: bool
    pending: tuple[Pending, ...]


@dataclass(frozen=True)
class Table:
    rows: Rows
    grades: Grades
    asks: Asks
    claims: Claims
    graded: tuple[Row, ...]
    reaches: tuple[Reach, ...]
    report: Report

    # ---- 数え上げ

    def denominator(self) -> int:
        return len(self.graded)

    def four(self) -> dict[str, int]:
        return {k: sum(1 for x in self.graded if x.value == k) for k in VALUES}

    def extras(self) -> dict[str, int]:
        """**行に付く 6 枠だけ**(7 枠目は分母が問いなので混ぜない)。"""
        return {k: sum(1 for x in self.graded if x.value == k)
                for k in ROW_BETSUWAKU}

    def stopped(self) -> int:
        return len(self.report.pending)

    def by_grade(self) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for means in MEANS + (UNREGISTERED,):
            rows = [x for x in self.graded if x.means == means]
            out.append({"品質の意味": means, "行の件数": len(rows),
                        "内訳": {k: sum(1 for x in rows if x.value == k)
                                 for k in VALUES + ROW_BETSUWAKU}})
        return out

    def boundary_days(self) -> dict[str, object]:
        """境界日が同じ日か別の日か、と日数の幅。**平均を出さない。**"""
        days = sorted(int(x.days) for x in self.graded if x.days != UNCOUNTABLE)
        return {SAME_DAY: sum(1 for x in self.graded if x.same_day == SAME_DAY),
                OTHER_DAY: sum(1 for x in self.graded if x.same_day == OTHER_DAY),
                UNCOUNTABLE: sum(1 for x in self.graded
                                 if x.same_day == UNCOUNTABLE),
                "日数が出た行": len(days),
                "日数の小さい方": days[0] if days else UNCOUNTABLE,
                "日数の大きい方": days[-1] if days else UNCOUNTABLE}

    def two_ways(self) -> dict[str, object]:
        """**2 通りの数え方と差。** 分母は (A)(B)(C) = 知識時間の経路が在る行。"""
        mine = [x for x in self.graded if x.has_known_path]
        real = sum(1 for x in mine if x.means == MEANS[0])
        other = sum(1 for x in mine if x.same_day == OTHER_DAY)
        return {"分母(知識時間の経路が在る行)": len(mine),
                "品質が 実値 の件数": real,
                "境界日が別の日である件数": other,
                "差": other - real}

    def real_same_day(self) -> int:
        """(B) のうち品質が `実値` の行(**2 通りの数え方の差の補正項**)。"""
        return sum(1 for x in self.graded
                   if x.value == VALUES[1] and x.means == MEANS[0])

    def dangling_asks(self) -> list[str]:
        return sorted(x.ask_id for x in self.asks.items
                      if x.row_id not in self.rows.ids)

    def reach_counts(self) -> dict[str, object]:
        """問いの側。**分母は行ではなく問い。**"""
        dangling = self.dangling_asks()
        return {"問いの件数": len(self.asks.items),
                f"別枠「{ASK_BETSUWAKU}」": len(dangling),
                "その問い id": dangling,
                "道が付いた問い": len(self.asks.items) - len(dangling),
                "3 値": {k: sum(1 for x in self.reaches if x.verdict == k)
                         for k in VERDICTS},
                "答えが乗っているもの": {
                    k: sum(1 for x in self.reaches if x.rests_on == k)
                    for k in RESTS}}

    def claim_rows(self) -> list[dict[str, object]]:
        """宣言の文と、観測の側の件数を並べるだけ。**採点しない。**"""
        four, two = self.four(), self.two_ways()
        return [{"宣言 id": x.claim_id, "文(verbatim)": x.text,
                 "主張する範囲": x.scope, "出典": x.source,
                 "観測の側(件数)": {"行の件数": self.denominator(),
                                    VALUES[0]: four[VALUES[0]],
                                    "2 通りの数え方": two},
                 "この文が正しいかは採点しない": MOTANAI["宣言の文を採点しない"]}
                for x in sorted(self.claims.items, key=lambda c: c.claim_id)]

    def crosscheck(self) -> str:
        four, extras, two = self.four(), self.extras(), self.two_ways()
        total = sum(four.values()) + sum(extras.values())
        by_grade = sum(int(r["行の件数"]) for r in self.by_grade())
        return (f"4 値 + 行に付く別枠 6 の合計 {total} / 行の件数 "
                f"{self.denominator()}(品質の意味ごとの合計 {by_grade})。"
                f"2 通りの数え方の差 {two['差']} = (C) の件数 {four[VALUES[2]]} "
                f"− (B) のうち品質が 実値 {self.real_same_day()}。"
                f"問いは別の分母 = {len(self.asks.items)} 件"
                f"(別枠 {len(self.dangling_asks())} 件)")

    def counts(self) -> dict[str, object]:
        return {"行の台帳の行数": len(self.rows.items),
                "品質の登録表の行数": len(self.grades.items),
                "問いの台帳の行数": len(self.asks.items),
                "宣言の台帳の行数": len(self.claims.items),
                "4 値": self.four(),
                "別枠(行に付く 6)": self.extras(),
                "境界日": self.boundary_days(),
                "2 通りの数え方": self.two_ways(),
                "(B) のうち品質が 実値": self.real_same_day(),
                "再現が届く範囲(問いの側)": self.reach_counts(),
                "件数の合計の検算": self.crosscheck(),
                **MOTANAI}

    def listed(self) -> list[dict[str, object]]:
        return [x.as_dict() for x in sorted(self.graded, key=lambda r: r.row_id)]

    def reach_listed(self) -> list[dict[str, object]]:
        return [x.as_dict() for x in sorted(self.reaches, key=lambda r: r.ask_id)]

    # ---- 判定部分(**時刻・絶対パス・値の名前・理由の文字を入れない**)

    def judgement_bytes(self) -> bytes:
        if not self.report.ok:
            raise RuntimeError("止まった表の判定部分は作らない")
        body = {"行": [[x.row_id, x.grade, x.means, x.same_day, x.days, x.value,
                        x.mark]
                       for x in sorted(self.graded, key=lambda r: r.row_id)],
                "問い": [[x.ask_id, x.row_id, x.as_of, x.basis_date, x.verdict,
                          x.rests_on]
                         for x in sorted(self.reaches, key=lambda r: r.ask_id)]}
        return json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.judgement_bytes()).hexdigest()

    def read_condition(self) -> dict[str, object]:
        return {"行の台帳の行数": len(self.rows.items),
                "問いの台帳の行数": len(self.asks.items),
                "決めた品質の意味": list(MEANS),
                "仮置き 3 種": list(KARIOKI),
                "決めた要求する欄": list(REQUIRES),
                "決めた宣言の範囲": list(SCOPES)}


# **出力の末尾に必ず並ぶ 10 行(消す引数も option も無い)**
MOTANAI: dict[str, str] = {
    "公表日を推定しない":
        "暦・版の名前・日付の形から品質の種類を当てる経路が無い。品質の記号は登録表に"
        "在るものだけを使い、無い記号は別枠へ出す",
    "取りに行かない":
        "外へ取りに行かない・走らせない・実行しない・import しない・構文解析しない・"
        "通信の経路が無い・入力フォルダの外を読まない",
    "仮置きを実値へ格上げしない":
        "品質の記号を書き換える経路が無い。別出典の公表日の欄が埋まっていても、記号が"
        "仮置きなら仮置きのまま数える",
    "正しい側を決めない":
        "仮置きが誤りだと言う列も、直すべき順位の列も、点数の列も無い。4 値は状態の"
        "名前で、良し悪しの順ではない",
    "再現できる率を単独で返さない":
        "率の 1 値を出す列が無い。件数には必ず分母が並び、行の側と問いの側で分母が"
        "別になる",
    "理由を言い当てない":
        "理由の欄は注記の写しだけで、空なら `理由の記載なし` を入れる。なぜ仮置きに"
        "したかを当てる辞書も分類器も持たない",
    "宣言の文を採点しない":
        "宣言の台帳の文と、その文が主張する範囲と、観測の側の件数を並べるだけ。文が"
        "正しいかを返す列が無い",
    "時計を読まない":
        "`as_of` と基準日は問いの台帳から来る(呼ぶ側が渡す)。現在時刻を読む呼び出しを"
        "持たない",
    "入力を書き換えない":
        "verify が作る写しはメモリの中だけで、4 枚の CSV に 1 文字も書かない",
    "float を使わない": "日数と件数は整数、ほかは文字列",
}


def asof_reach(rows: Rows, grades: Grades, asks: Asks,
               claims: Claims) -> Table:
    """4 枚から行ごとの 4 値と問いごとの 3 値を出す。**登録の側が壊れていたら数えない。**"""
    pending: list[Pending] = []
    for name in grades.sourceless():
        pending.append(Pending(TABLE_REASONS[0], f"{grades.what} の {name}"))
    for name in claims.sourceless():
        pending.append(Pending(TABLE_REASONS[0], f"{claims.what} の {name}"))
    for row_id in rows.duplicated():
        pending.append(Pending(TABLE_REASONS[1], f"行 {row_id}"))
    for bad in grades.bad_means():
        pending.append(Pending(TABLE_REASONS[2], f"{grades.what} の {bad}"))
    for bad in grades.bad_requires():
        pending.append(Pending(TABLE_REASONS[3], f"{grades.what} の {bad}"))
    for x in rows.items:
        for bad in x.bad_dates():
            pending.append(Pending(TABLE_REASONS[4], bad))
    for bad in asks.bad_dates():
        pending.append(Pending(TABLE_REASONS[4], bad))
    for bad in claims.bad_scope():
        pending.append(Pending(TABLE_REASONS[5], f"{claims.what} の {bad}"))
    for where in asks.dateless():
        pending.append(Pending(TABLE_REASONS[6], where))
    if not grades.items:
        pending.append(Pending(TABLE_REASONS[7], grades.what))

    if pending:
        return Table(rows, grades, asks, claims, (), (),
                     Report(False, tuple(pending)))
    graded = tuple(judge(rows.of(row_id), grades, rows) for row_id in rows.ids)
    by_id = {x.row_id: x for x in graded}
    reaches = tuple(reach_of(a, by_id[a.row_id], rows.of(a.row_id))
                    for a in sorted(asks.items, key=lambda x: x.ask_id)
                    if a.row_id in by_id)
    return Table(rows, grades, asks, claims, graded, reaches, Report(True, ()))


# ------------------------------------------------------------ verify(5 つ)

def moved(first: Table, after: Table) -> list[str]:
    a = {x.row_id: x.value for x in first.graded}
    b = {x.row_id: x.value for x in after.graded}
    return sorted(k for k in a if a[k] != b.get(k))


def probe_plan(first: Table) -> str | None:
    """(A) の 1 件目(ここを差し替えると (B) と (C) へ分かれて動く)。"""
    for x in sorted(first.graded, key=lambda r: r.row_id):
        if x.value == VALUES[0]:
            return x.row_id
    return None


def _rows_with(rows: Rows, row_id: str, column: str, value: str) -> Rows:
    """**写しはメモリの中だけ。** 行の台帳の CSV には 1 文字も書かない。"""
    i = ROW_COLUMNS.index(column)
    out: list[list[str]] = []
    for r in rows.rows:
        r = list(r)
        if r[0] == row_id:
            r[i] = value
        out.append(r)
    return Rows(out)


def probe_same_day(rows: Rows, grades: Grades, asks: Asks, claims: Claims,
                   row_id: str) -> Table:
    """`known_from` を `valid_from` と同じ日に書き換える((A) → (B))。"""
    raw = rows.of(row_id)
    return asof_reach(_rows_with(rows, row_id, "known_from", raw.valid_from),
                      grades, asks, claims)


def probe_grade(rows: Rows, grades: Grades, asks: Asks, claims: Claims,
                row_id: str, grade: str) -> Table:
    """品質の記号を仮置きの記号に替える((A) → (C))。"""
    return asof_reach(_rows_with(rows, row_id, "grade", grade), grades, asks,
                      claims)


def karioki_grade(grades: Grades) -> str | None:
    """登録表の中で `公布日で仮置き` の記号(無ければ仮置き 3 種のどれか)。"""
    for want in (MEANS[3],) + KARIOKI:
        for x in grades.items:
            if x.means == want:
                return x.grade
    return None


def verify(rows: Rows, grades: Grades, asks: Asks,
           claims: Claims) -> dict[str, object]:
    """5 つ見る(二度走り / 行順 3 通り / 件数の検算 / 同じ日に書き換える /
    記号を仮置きに替える)。"""
    first = asof_reach(rows, grades, asks, claims)
    if not first.report.ok:
        return {"ok": False,
                "止まった": [p.as_dict() for p in first.report.pending]}
    again = asof_reach(rows, grades, asks, claims)
    same_twice = again.sha256() == first.sha256()
    swapped: list[bool] = []
    for how in SWAPS:
        t = asof_reach(rows.swapped(how), grades.swapped(how), asks.swapped(how),
                       claims.swapped(how))
        swapped.append(t.sha256() == first.sha256())

    four, extras = first.four(), first.extras()
    total = sum(four.values()) + sum(extras.values())
    sums_ok = (total == first.denominator()
               and sum(int(r["行の件数"]) for r in first.by_grade()) == total
               and int(first.two_ways()["差"])
               == four[VALUES[2]] - first.real_same_day())

    plan = probe_plan(first)
    day_probe: dict[str, object] = {"やったこと": "(A) の行が無い", "ok": True}
    grade_probe: dict[str, object] = {"やったこと": "(A) の行が無い", "ok": True}
    if plan:
        after = probe_same_day(rows, grades, asks, claims, plan)
        got = {x.row_id: x.value for x in after.graded}[plan]
        day_probe = {
            "やったこと": f"行 {plan} の known_from を valid_from と同じ日にした",
            "移った行": moved(first, after), "移った先": got,
            "2 通りの数え方": after.two_ways(),
            "ok": moved(first, after) == [plan] and got == VALUES[1]
            and int(after.two_ways()["差"])
            == int(first.two_ways()["差"]) - 1}
        grade = karioki_grade(grades)
        if grade:
            after2 = probe_grade(rows, grades, asks, claims, plan, grade)
            got2 = {x.row_id: x.value for x in after2.graded}[plan]
            grade_probe = {
                "やったこと": f"行 {plan} の品質の記号を {grade}(仮置き)に替えた",
                "移った行": moved(first, after2), "移った先": got2,
                "2 通りの数え方": after2.two_ways(),
                "ok": moved(first, after2) == [plan] and got2 == VALUES[2]
                and int(after2.two_ways()["差"])
                == int(first.two_ways()["差"]) + 1}

    return {"ok": bool(same_twice and all(swapped) and sums_ok
                       and day_probe["ok"] and grade_probe["ok"]),
            "二度走りの判定部分が同一": same_twice,
            "行順を入れ替えても同一": dict(zip(SWAPS, swapped)),
            "件数の合計": first.crosscheck(), "合計が合う": sums_ok,
            "2 通りの数え方": first.two_ways(),
            "境界日": first.boundary_days(),
            "同じ日に書き換える": day_probe,
            "記号を仮置きに替える": grade_probe,
            "判定部分の sha256": first.sha256(),
            "入力を書き換えない": MOTANAI["入力を書き換えない"]}


# ------------------------------------------------------------ ひな型

T_ROW = "合成の行のメモ(架空)L1"
T_GRADE = "合成の品質の登録のメモ(架空)L1"
T_ASK = "合成の問いのメモ(架空)L1"
T_CLAIM = "合成の宣言のメモ(架空)L1"

TEMPLATE_ROWS = [list(ROW_COLUMNS),
                 ["R01", "合成の値 A(架空)", "2026-03-01", OPEN, "2026-02-01",
                  OPEN, "記号 1", "2026-02-01", "合成の理由(架空)", T_ROW],
                 ["R02", "合成の値 B(架空)", "2026-04-01", OPEN, "2026-04-01",
                  OPEN, "記号 2", NO_MARK, "合成の理由(架空)", T_ROW]]
TEMPLATE_GRADES = [list(GRADE_COLUMNS),
                   ["記号 1", MEANS[0], REQUIRES[0], T_GRADE],
                   ["記号 2", MEANS[1], REQUIRES[1], T_GRADE]]
TEMPLATE_ASKS = [list(ASK_COLUMNS),
                 ["Q01", "R01", "2026-01-15", "2026-03-15", T_ASK],
                 ["Q02", "R02", "2026-03-15", "2026-03-15", T_ASK]]
TEMPLATE_CLAIMS = [list(CLAIM_COLUMNS),
                   ["C01", "合成の宣言の文(架空)", SCOPES[2], T_CLAIM]]


def write_csv(path: Path, rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    return path


def init(dest: str | Path) -> tuple[Path, ...]:
    d = Path(dest)
    return tuple([write_csv(d / "行の台帳.csv", TEMPLATE_ROWS),
                  write_csv(d / "品質の登録表.csv", TEMPLATE_GRADES),
                  write_csv(d / "問いの台帳.csv", TEMPLATE_ASKS),
                  write_csv(d / "宣言の台帳.csv", TEMPLATE_CLAIMS)])


# ------------------------------------------------------------ CLI

def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def build_parser() -> argparse.ArgumentParser:
    """CLI は check / report / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = argparse.ArgumentParser(prog="asof_reach",
                                 description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in SUBCOMMANDS[:3]:
        p = sub.add_parser(name)
        for arg in ("rows", "grades", "asks", "claims"):
            p.add_argument(arg)
    sub.add_parser(SUBCOMMANDS[3]).add_argument("dest")
    return ap


def load_four(a) -> tuple[Rows, Grades, Asks, Claims]:
    return (Rows.load(a.rows), Grades.load(a.grades), Asks.load(a.asks),
            Claims.load(a.claims))


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == SUBCOMMANDS[3]:
        print("書いた: " + " / ".join(str(p) for p in init(a.dest)))
        return 0
    try:
        four_tables = load_four(a)
        if a.cmd == SUBCOMMANDS[2]:
            out = verify(*four_tables)
            _print(out)
            return 0 if out["ok"] else 3
        t = asof_reach(*four_tables)
    except ReadError as e:
        print(f"表として読めない: {e}", file=sys.stderr)
        return 2
    if not t.report.ok:
        _print({"ok": False, "stage": "止まった(4 値は返さない)",
                "2 通りの数え方": {"分母(知識時間の経路が在る行)": 0},
                "pending": [p.as_dict() for p in t.report.pending]})
        return 3
    body: dict[str, object] = {"ok": True, **t.counts()}
    if a.cmd == SUBCOMMANDS[1]:
        body["行ごとの一覧"] = t.listed()
        body["問いごとの一覧"] = t.reach_listed()
        body["品質の意味ごと"] = t.by_grade()
        body["宣言の台帳"] = t.claim_rows()
        body["sha256"] = t.sha256()
        body["読んだ条件"] = t.read_condition()
    _print(body)
    counts = t.four()
    clean = (not sum(t.extras().values()) and not t.stopped()
             and not counts[VALUES[1]] and not counts[VALUES[2]]
             and not counts[VALUES[3]] and not t.dangling_asks())
    return 0 if clean else 3


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
