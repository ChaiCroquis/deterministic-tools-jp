"""off_scope — 別の領域と宣言された項目 1 件を 1 行として、触れている線と実際の在り所を 4 値に分ける。

**「ここは別の領域だから対象外」と書いた線のすぐ外側に、計算には要ると同じ 1 行で宣言された
項目が並んでいて、しかもその領域の行が実際には表の中で動いている。** 対象外という 1 語は、
少なくとも 4 つの別の状態をまとめている。

この部品は、項目の台帳・在り所の台帳・入る形の宣言表(3 枚)と登録表 3 枚(領域 / basis の
欄名 / payload 種別)から、項目 1 件ごとに 4 値 + 別枠 7 を付ける。**4 値の欄は 5 つある**
((D) は「入る形まで書かれている」と「線の内側」を別の記号で返す)。

  (A) 線の外と宣言され、在り所が `無い` で、必須の宣言が在る
  (B) 線の外と宣言されたのに `収録` か `照合専用` の行が在る(行数と由来つき)
  (C) 線の外と宣言され、行は無いが行き先が宣言されている(`第2層` / `case属性`)
  (D) `境界として明示` と宣言され、入る形(basis / payload / selector)まで書かれている
  (D) `内` と宣言(この部品の対象の外)

**「線の外」は領域の登録表が `外` か `境界として明示` と宣言した領域のこと**で、項目名から
推測する経路は無い。

別枠 7 = 出典が空 / 領域の記号が登録表に無い / 同じ項目が 2 か所で別の行き先を宣言されている
/ basis の欄名が登録表に無い / payload 種別が空か登録表に無い / 期間の終わりの記載が在る /
必須の宣言も在り所の宣言も無い。**別枠は 4 値より先に当たる。**

持たせていないものが規律になっている。

  - **収録すべきかを決めない**(推奨・順位・点数・合計の 1 値を出す列が無い)
  - **必須かどうかを判断しない**(必須の欄は入力の文字列を出典ごと写すだけで、空の行には
    `必須の記載なし` を入れる。要るかどうかを言い当てる辞書も分類器も持たない)
  - **領域の線を引き直さない**(`内` / `外` / `境界として明示` の 3 値は登録表から取るだけで、
    判定の辞書を持たない)
  - **項目名から領域を推測しない**(登録表に無い記号は別枠へ出す)
  - **条文や規約を読まない・取りに行かない・走らせない**(実行しない・import しない・
    構文解析しない・通信の経路が無い・入力フォルダの外を読まない)
  - **`0 件` と `欄が無い` を同じ値にしない**(行数を数えない在り所は `数えられない` を返す)
  - **割合を単独で返さない**(必ず 2 通りの分母 = 項目数と行数の内訳が付く)
  - **時計を読まない**(基準日は呼び出し側が渡す)、**入力を書き換えない**、
    **float を使わない**、判定部分に時刻・絶対パス・ホスト名を入れない

**登録表 3 枚の行に出典が無ければ、1 項目も数えずに止まる。**

項目の台帳(CSV)の列は 6。

    item_id   項目 id(同じ id が 2 行あると止まる)
    name      項目名(判定には使わない。領域はこの文字から推測しない)
    domain    領域の記号(領域の登録表に在る記号だけ。無ければ別枠へ)
    required  必須の宣言(どの計算が要ると書いているかの文字列。空欄可)
    note      備考(原文のまま。空欄可)
    source    出典(ファイル名 + 行番号)。空欄のとき、その項目は別枠「出典が空」へ入る

領域の登録表(CSV)の列は 3。**この表だけが線を引く。**

    domain   領域の記号(同じ記号が 2 行あると読めない)
    stance   この表の内か外かの宣言(`内` / `外` / `境界として明示`)
    source   出典。空欄のとき 1 項目も数えずに止まる

在り所の台帳(CSV)の列は 5。**1 項目に 0〜N 行。**

    item_id  項目 id(項目の台帳に無いと読めない)
    place    在り所の記号(`収録` / `照合専用` / `第2層` / `case属性` / `無い`)
    rows     行数(`収録` と `照合専用` のときは 0 以上の整数。ほかは `—`)
    origin   由来の記号(`自前抽出` / `上流` / `—`)
    source   出典。空欄のとき、その項目は別枠「出典が空」へ入る

入る形の宣言表(CSV)の列は 6。**1 項目に 0 か 1 行。**

    item_id     項目 id
    basis       basis の欄名(`—` = 記載なし)
    payload     payload 種別(`—` または空 = 記載なし → 別枠へ)
    selector    selector 次元の列挙(`/` 区切り。`—` = 記載なし)
    period_end  期間の終わりの記載(`—` = 記載なし。何か書かれていれば閉じている)
    source      出典。空欄のとき、その項目は別枠「出典が空」へ入る

basis の欄名の登録表 / payload 種別の登録表(CSV)の列は各 3。**登録表に無い欄名は、候補の
側にだけ在るものとして別枠へ出す。**

数えて返す量は 3 つだけ。

  - 4 値 + 別枠 の項目数
  - (B) の行数の合計(由来ごとの内訳つき)
  - 必須の宣言が在るのに在り所が `無い` 項目の数

止まる理由コード 7 = 登録表の行の出典が空 / 項目 id の重複 / 領域の登録表の宣言が決めた
3 つの外 / 在り所の記号が決めた 5 つの外 / `収録`・`照合専用` の行数が整数でない /
基準日が渡されていない / 登録表そのものが空。

使い方:

    python off_scope.py init ひな型/
    python off_scope.py check  項目.csv 領域.csv 在り所.csv 入る形.csv basis.csv payload.csv 2026-09-20
    python off_scope.py report 項目.csv 領域.csv 在り所.csv 入る形.csv basis.csv payload.csv 2026-09-20
    python off_scope.py verify 項目.csv 領域.csv 在り所.csv 入る形.csv basis.csv payload.csv 2026-09-20
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

ITEM_COLUMNS = ("item_id", "name", "domain", "required", "note", "source")
DOMAIN_COLUMNS = ("domain", "stance", "source")
PLACE_COLUMNS = ("item_id", "place", "rows", "origin", "source")
SHAPE_COLUMNS = ("item_id", "basis", "payload", "selector", "period_end", "source")
BASIS_COLUMNS = ("basis", "means", "source")
PAYLOAD_COLUMNS = ("payload", "means", "source")

# 領域の宣言(**この 3 つの外に宣言を作る経路が無い**)
STANCES = ("内", "外", "境界として明示")
# 「線の外」= `外` か `境界として明示`(**項目名から当てる経路が無い**)
OUTSIDE = (STANCES[1], STANCES[2])
# 在り所の記号(**この 5 つの外に記号を作る経路が無い**)
PLACES = ("収録", "照合専用", "第2層", "case属性", "無い")
# 行数を数える在り所(**ほかの記号の行数の欄は `—` でなければ読めない**)
COUNTED = (PLACES[0], PLACES[1])
# 行き先として宣言された在り所(**行は無いが、どの層へ行くかは書かれている**)
DESTINED = (PLACES[2], PLACES[3])
# 由来の記号
ORIGINS = ("自前抽出", "上流")

NO_MARK = "—"
NO_ROW = "(在り所の行が無い)"
NO_SHAPE = "(入る形の宣言が無い)"
MANY_PLACES = "(行き先が 2 つ以上)"
UNCOUNTABLE = "数えられない"
NO_REQUIRED = "必須の記載なし"
NO_ORIGIN = "由来の記載なし"
UNREGISTERED = "(登録表の外)"

# 項目 1 件に付く 4 値。**(D) は「入る形まで書かれている」と「線の内側」を別の記号で返す。**
VALUES = (
    "(A) 線の外と宣言され、在り所が 無い で、必須の宣言が在る",
    "(B) 線の外と宣言されたのに 収録 か 照合専用 の行が在る",
    "(C) 線の外と宣言され、行は無いが行き先が宣言されている",
    "(D) 境界として明示 と宣言され、入る形まで書かれている",
    "(D) 内 と宣言(この部品の対象の外)",
)
# 4 値の外へ出す別枠 7。**上から順に当たり、4 値より先に当たる。**
BETSUWAKU = (
    "出典が空",
    "領域の記号が登録表に無い",
    "同じ項目が 2 か所で別の行き先を宣言されている",
    "basis の欄名が登録表に無い",
    "payload 種別が空か登録表に無い",
    "期間の終わりの記載が在る",
    "必須の宣言も在り所の宣言も無い",
)
# 1 項目も数えずに止まる理由コード 7(**登録の側と基準日の不備**)
TABLE_REASONS = (
    "登録表の行の出典が空",
    "項目 id の重複",
    "領域の登録表の宣言が決めた 3 つの外",
    "在り所の記号が決めた 5 つの外",
    "収録・照合専用 の行数が整数でない",
    "基準日が渡されていない",
    "登録表そのものが空",
)
# 行順の入れ替え方(verify が 3 通り試す)
SWAPS = ("逆順", "先頭を末尾へ", "末尾を先頭へ")
SUBCOMMANDS = ("check", "report", "verify", "init")


class ReadError(Exception):
    """表として読めない(列・行・id・参照・記号の形が決めた形でない)。"""


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


# ------------------------------------------------------------ 入力の 6 枚

@dataclass(frozen=True)
class Item:
    item_id: str
    name: str
    domain: str
    required: str
    note: str
    source: str

    @property
    def required_text(self) -> str:
        """**入力の文字列を写すだけ。** 空の行(`—` を含む)には `必須の記載なし` を入れる。"""
        return NO_REQUIRED if blank(self.required) else self.required


class Items:
    """項目の台帳。**行順を入れ替えても出力が同じになるよう、読んだ順は別に持つ。**"""

    def __init__(self, rows: list[list[str]]) -> None:
        self.rows = [list(r) for r in rows]
        self.items: tuple[Item, ...] = tuple(Item(*r) for r in rows)
        for x in self.items:
            if bad_id(x.item_id):
                raise ReadError(f"項目 id が空か区切り文字を含む: {x.item_id!r}")
            if not x.domain:
                raise ReadError(f"領域の記号が空: 項目 {x.item_id}")

    @classmethod
    def parse(cls, text: str) -> "Items":
        return cls(_rows_of(text, ITEM_COLUMNS, "項目の台帳"))

    @classmethod
    def load(cls, path: str | Path) -> "Items":
        return cls.parse(Path(path).read_text(encoding="utf-8-sig"))

    def swapped(self, how: str) -> "Items":
        return Items(swap_rows(self.rows, how))

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(sorted({x.item_id for x in self.items}))

    def duplicated(self) -> tuple[str, ...]:
        seen: dict[str, int] = {}
        for x in self.items:
            seen[x.item_id] = seen.get(x.item_id, 0) + 1
        return tuple(sorted(k for k, v in seen.items() if v > 1))

    def of(self, item_id: str) -> Item:
        return next(x for x in self.items if x.item_id == item_id)


@dataclass(frozen=True)
class Domain:
    domain: str
    stance: str
    source: str


class Domains:
    """領域の登録表。**この表だけが線を引く(記号の綴りから当てる経路が無い)。**"""

    what = "領域の登録表"

    def __init__(self, rows: list[list[str]]) -> None:
        self.rows = [list(r) for r in rows]
        self.items: tuple[Domain, ...] = tuple(Domain(*r) for r in rows)
        seen: set[str] = set()
        for x in self.items:
            if not x.domain:
                raise ReadError("領域の登録表に記号が空の行が在る")
            if x.domain in seen:
                raise ReadError(f"領域の登録表に同じ記号が 2 行: {x.domain}")
            seen.add(x.domain)

    @classmethod
    def parse(cls, text: str) -> "Domains":
        return cls(_rows_of(text, DOMAIN_COLUMNS, "領域の登録表", True))

    @classmethod
    def load(cls, path: str | Path) -> "Domains":
        return cls.parse(Path(path).read_text(encoding="utf-8-sig"))

    def swapped(self, how: str) -> "Domains":
        return Domains(swap_rows(self.rows, how))

    def has(self, domain: str) -> bool:
        return any(x.domain == domain for x in self.items)

    def stance_of(self, domain: str) -> str:
        return next((x.stance for x in self.items if x.domain == domain),
                    UNREGISTERED)

    def bad_stance(self) -> tuple[str, ...]:
        return tuple(f"{x.domain} → {x.stance!r}" for x in self.items
                     if x.stance not in STANCES)

    def sourceless(self) -> tuple[str, ...]:
        return tuple(x.domain for x in self.items if not x.source)


@dataclass(frozen=True)
class Placement:
    item_id: str
    place: str
    count: str
    origin: str
    source: str

    @property
    def counts(self) -> bool:
        """行数を数える在り所か(`第2層` などは数えない = `数えられない`)。"""
        return self.place in COUNTED


class Placements:
    """在り所の台帳。**1 項目に 0〜N 行。**"""

    def __init__(self, rows: list[list[str]], item_ids: tuple[str, ...]) -> None:
        self.rows = [list(r) for r in rows]
        self.items: tuple[Placement, ...] = tuple(Placement(*r) for r in rows)
        self.item_ids = item_ids
        for x in self.items:
            if x.item_id not in item_ids:
                raise ReadError(f"在り所の項目 id が台帳に無い: {x.item_id}")
            if not x.counts and not blank(x.count):
                raise ReadError(f"行数の欄は 収録 と 照合専用 のときだけ埋める: "
                                f"項目 {x.item_id} の {x.place} に {x.count!r}")

    @classmethod
    def parse(cls, text: str, item_ids: tuple[str, ...]) -> "Placements":
        return cls(_rows_of(text, PLACE_COLUMNS, "在り所の台帳", True), item_ids)

    @classmethod
    def load(cls, path: str | Path, item_ids: tuple[str, ...]) -> "Placements":
        return cls.parse(Path(path).read_text(encoding="utf-8-sig"), item_ids)

    def swapped(self, how: str) -> "Placements":
        return Placements(swap_rows(self.rows, how), self.item_ids)

    def of_item(self, item_id: str) -> tuple[Placement, ...]:
        return tuple(sorted((x for x in self.items if x.item_id == item_id),
                            key=lambda x: (x.place, x.count, x.origin)))

    def bad_place(self) -> tuple[str, ...]:
        return tuple(f"項目 {x.item_id} の {x.place!r}" for x in self.items
                     if x.place not in PLACES)

    def not_integer(self) -> tuple[str, ...]:
        return tuple(f"項目 {x.item_id} の行数 {x.count!r}" for x in self.items
                     if x.counts and not x.count.isdigit())


@dataclass(frozen=True)
class Shape:
    item_id: str
    basis: str
    payload: str
    selector: str
    period_end: str
    source: str

    @property
    def written(self) -> bool:
        """入る形が basis / payload / selector の 3 欄とも埋まっているか。"""
        return not (blank(self.basis) or blank(self.payload) or blank(self.selector))

    @property
    def closed(self) -> bool:
        """期間の終わりの記載が在るか(**記載の有無だけを見て、文字は読まない**)。"""
        return not blank(self.period_end)


class Shapes:
    """入る形の宣言表。**1 項目に 0 か 1 行。**"""

    def __init__(self, rows: list[list[str]], item_ids: tuple[str, ...]) -> None:
        self.rows = [list(r) for r in rows]
        self.items: tuple[Shape, ...] = tuple(Shape(*r) for r in rows)
        self.item_ids = item_ids
        seen: set[str] = set()
        for x in self.items:
            if x.item_id not in item_ids:
                raise ReadError(f"入る形の項目 id が台帳に無い: {x.item_id}")
            if x.item_id in seen:
                raise ReadError(f"入る形の宣言表に同じ項目 id が 2 行: {x.item_id}")
            seen.add(x.item_id)

    @classmethod
    def parse(cls, text: str, item_ids: tuple[str, ...]) -> "Shapes":
        return cls(_rows_of(text, SHAPE_COLUMNS, "入る形の宣言表", True), item_ids)

    @classmethod
    def load(cls, path: str | Path, item_ids: tuple[str, ...]) -> "Shapes":
        return cls.parse(Path(path).read_text(encoding="utf-8-sig"), item_ids)

    def swapped(self, how: str) -> "Shapes":
        return Shapes(swap_rows(self.rows, how), self.item_ids)

    def of_item(self, item_id: str) -> Shape | None:
        return next((x for x in self.items if x.item_id == item_id), None)


@dataclass(frozen=True)
class Name:
    name: str
    means: str
    source: str


class NameRegistry:
    """欄名 / 種別の登録表 1 枚(basis と payload で同じ形)。"""

    def __init__(self, rows: list[list[str]], columns: tuple[str, ...],
                 what: str) -> None:
        self.rows = [list(r) for r in rows]
        self.columns, self.what = columns, what
        self.items: tuple[Name, ...] = tuple(Name(*r) for r in rows)
        seen: set[str] = set()
        for x in self.items:
            if not x.name:
                raise ReadError(f"{what} に名前が空の行が在る")
            if x.name in seen:
                raise ReadError(f"{what} に同じ名前が 2 行: {x.name}")
            seen.add(x.name)

    @classmethod
    def parse(cls, text: str, columns: tuple[str, ...], what: str) -> "NameRegistry":
        return cls(_rows_of(text, columns, what, True), columns, what)

    @classmethod
    def load(cls, path: str | Path, columns: tuple[str, ...],
             what: str) -> "NameRegistry":
        return cls.parse(Path(path).read_text(encoding="utf-8-sig"), columns, what)

    def swapped(self, how: str) -> "NameRegistry":
        return NameRegistry(swap_rows(self.rows, how), self.columns, self.what)

    def has(self, name: str) -> bool:
        return any(x.name == name for x in self.items)

    def sourceless(self) -> tuple[str, ...]:
        return tuple(x.name for x in self.items if not x.source)


def load_basis(path: str | Path) -> NameRegistry:
    return NameRegistry.load(path, BASIS_COLUMNS, "basis の欄名の登録表")


def load_payload(path: str | Path) -> NameRegistry:
    return NameRegistry.load(path, PAYLOAD_COLUMNS, "payload 種別の登録表")


# ------------------------------------------------------------ 4 値を付ける

@dataclass(frozen=True)
class Row:
    """項目 1 件の結果。**推奨・順位・点数の欄は無い。**"""
    item_id: str
    name: str
    domain: str
    stance: str
    required: str
    place: str
    count: str
    origin: str
    basis: str
    payload: str
    selector: str
    period_end: str
    value: str
    note: str

    @property
    def graded(self) -> bool:
        return self.value in VALUES

    @property
    def missing_row(self) -> bool:
        """必須の宣言が在るのに在り所が `無い`(か行が無い)項目か。"""
        return self.required != NO_REQUIRED and self.place in (PLACES[4], NO_ROW)

    def as_dict(self) -> dict[str, object]:
        return {"項目 id": self.item_id, "項目名": self.name,
                "領域の記号": self.domain, "領域の宣言": self.stance,
                "必須の宣言(出典ごと写す)": self.required,
                "在り所": self.place, "行数": self.count, "由来": self.origin,
                "basis の欄名": self.basis, "payload 種別": self.payload,
                "selector 次元": self.selector,
                "期間の終わりの記載": self.period_end,
                "4 値 / 別枠": self.value, "備考(原文のまま)": self.note}


def _place_view(places: tuple[Placement, ...]) -> tuple[str, str, str]:
    """在り所 / 行数 / 由来。**行数を数えない在り所は `数えられない`。**"""
    if not places:
        return NO_ROW, UNCOUNTABLE, NO_MARK
    marks = sorted({x.place for x in places})
    if len(marks) > 1:
        return MANY_PLACES, UNCOUNTABLE, NO_MARK
    counted = [x for x in places if x.counts]
    if not counted:
        return marks[0], UNCOUNTABLE, NO_MARK
    total = sum(int(x.count) for x in counted if x.count.isdigit())
    origins = sorted({x.origin for x in counted if not blank(x.origin)})
    return marks[0], str(total), " / ".join(origins) or NO_ORIGIN


def judge(item: Item, places: tuple[Placement, ...], shape: Shape | None,
          domains: Domains, basis: NameRegistry, payload: NameRegistry) -> Row:
    """項目 1 件に 4 値か別枠を付ける。**別枠が 4 値より先に当たる。**"""
    place, count, origin = _place_view(places)
    stance = domains.stance_of(item.domain)

    def row(value: str) -> Row:
        return Row(item.item_id, item.name, item.domain, stance,
                   item.required_text, place, count, origin,
                   shape.basis if shape else NO_SHAPE,
                   shape.payload if shape else NO_SHAPE,
                   shape.selector if shape else NO_SHAPE,
                   shape.period_end if shape else NO_SHAPE,
                   value, item.note or NO_MARK)

    # 別枠(上から順に当たり、4 値より先に当たる)
    if (not item.source or any(not x.source for x in places)
            or (shape is not None and not shape.source)):
        return row(BETSUWAKU[0])
    if not domains.has(item.domain):
        return row(BETSUWAKU[1])
    if place == MANY_PLACES:
        return row(BETSUWAKU[2])
    if shape is not None and not blank(shape.basis) and not basis.has(shape.basis):
        return row(BETSUWAKU[3])
    if shape is not None and (blank(shape.payload) or not payload.has(shape.payload)):
        return row(BETSUWAKU[4])
    if shape is not None and shape.closed:
        return row(BETSUWAKU[5])
    if item.required_text == NO_REQUIRED and place in (PLACES[4], NO_ROW):
        return row(BETSUWAKU[6])

    # 4 値(欄は 5 つ)
    if stance == STANCES[0]:
        return row(VALUES[4])
    if place in COUNTED:
        return row(VALUES[1])
    if place in DESTINED:
        return row(VALUES[2])
    if stance == STANCES[2] and shape is not None and shape.written:
        return row(VALUES[3])
    # ここへ来る項目は在り所が `無い` か行が無く、必須の宣言が在る(無い行は別枠 7 で落ちる)
    return row(VALUES[0])


# ------------------------------------------------------------ 表 1 枚ぶんの結果

@dataclass(frozen=True)
class Report:
    ok: bool
    pending: tuple[Pending, ...]


@dataclass(frozen=True)
class Table:
    items: Items
    domains: Domains
    placements: Placements
    shapes: Shapes
    basis: NameRegistry
    payload: NameRegistry
    asof: str
    rows: tuple[Row, ...]
    report: Report

    # ---- 数え上げ

    def denominator(self) -> int:
        return len(self.rows)

    def five(self) -> dict[str, int]:
        return {k: sum(1 for x in self.rows if x.value == k) for k in VALUES}

    def extras(self) -> dict[str, int]:
        return {k: sum(1 for x in self.rows if x.value == k) for k in BETSUWAKU}

    def stopped(self) -> int:
        return len(self.report.pending)

    def by_stance(self) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for stance in STANCES + (UNREGISTERED,):
            rows = [x for x in self.rows if x.stance == stance]
            out.append({"領域の宣言": stance, "項目の件数": len(rows),
                        "内訳": {k: sum(1 for x in rows if x.value == k)
                                 for k in VALUES + BETSUWAKU}})
        return out

    def by_place(self) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for place in PLACES + (NO_ROW, MANY_PLACES):
            rows = [x for x in self.rows if x.place == place]
            out.append({"在り所": place, "項目の件数": len(rows),
                        "内訳": {k: sum(1 for x in rows if x.value == k)
                                 for k in VALUES + BETSUWAKU}})
        return out

    def counted_rows(self) -> dict[str, object]:
        """(B) の行数の合計と、由来ごとの内訳。**割合は返さない。**"""
        b_ids = {x.item_id for x in self.rows if x.value == VALUES[1]}
        mine = [x for x in self.placements.items
                if x.item_id in b_ids and x.counts and x.count.isdigit()]
        by_origin: dict[str, int] = {o: sum(int(x.count) for x in mine
                                            if x.origin == o) for o in ORIGINS}
        by_origin[NO_ORIGIN] = sum(int(x.count) for x in mine if blank(x.origin))
        return {"(B) の行数の合計": sum(int(x.count) for x in mine),
                "由来ごとの内訳": by_origin,
                "行を数えた在り所の行数": len(mine)}

    def missing_rows(self) -> dict[str, object]:
        """必須の宣言が在るのに在り所が `無い` 項目。**別枠へ出た項目も数える。**"""
        mine = sorted((x for x in self.rows if x.missing_row),
                      key=lambda r: r.item_id)
        return {"件数": len(mine), "項目": {x.item_id: x.value for x in mine}}

    def denominators(self) -> dict[str, object]:
        """**2 通りの分母。** 割合を単独で返す経路が無いので、必ずこの 2 つが付く。"""
        rows_by_place = {place: sum(int(x.count) for x in self.placements.items
                                    if x.place == place and x.count.isdigit())
                         for place in COUNTED}
        return {"項目数": self.denominator(),
                "行数(在り所の台帳が数えた行)": rows_by_place,
                "行数を数えない項目": sum(1 for x in self.rows
                                          if x.count == UNCOUNTABLE)}

    def crosscheck(self) -> str:
        total = sum(self.five().values()) + sum(self.extras().values())
        by_stance = sum(int(r["項目の件数"]) for r in self.by_stance())
        by_place = sum(int(r["項目の件数"]) for r in self.by_place())
        return (f"4 値 + 別枠 の合計 {total} / 項目の件数 {self.denominator()}"
                f"(領域の宣言ごとの合計 {by_stance}、在り所ごとの合計 {by_place})")

    def counts(self) -> dict[str, object]:
        return {"基準日": self.asof,
                "項目の台帳の行数": len(self.items.items),
                "在り所の台帳の行数": len(self.placements.items),
                "入る形の宣言表の行数": len(self.shapes.items),
                "登録表の行数": {"領域": len(self.domains.items),
                                 "basis の欄名": len(self.basis.items),
                                 "payload 種別": len(self.payload.items)},
                "2 通りの分母": self.denominators(),
                "4 値": self.five(),
                "別枠": self.extras(),
                "収録の量": self.counted_rows(),
                "必須の宣言が在るのに在り所が 無い 項目": self.missing_rows(),
                "件数の合計の検算": self.crosscheck(),
                **MOTANAI}

    def listed(self) -> list[dict[str, object]]:
        return [x.as_dict() for x in sorted(self.rows, key=lambda r: r.item_id)]

    # ---- 判定部分(**時刻・絶対パス・ホスト名・原文の備考を入れない**)

    def judgement_bytes(self) -> bytes:
        if not self.report.ok:
            raise RuntimeError("止まった表の判定部分は作らない")
        body = {"基準日": self.asof,
                "項目": [[x.item_id, x.domain, x.stance, x.place, x.count,
                          x.origin, x.value]
                         for x in sorted(self.rows, key=lambda r: r.item_id)]}
        return json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.judgement_bytes()).hexdigest()

    def read_condition(self) -> dict[str, object]:
        return {"項目の台帳の行数": len(self.items.items),
                "在り所の台帳の行数": len(self.placements.items),
                "入る形の宣言表の行数": len(self.shapes.items),
                "基準日": self.asof,
                "決めた領域の宣言": list(STANCES),
                "線の外とみなす宣言": list(OUTSIDE),
                "決めた在り所の記号": list(PLACES)}


# **出力の末尾に必ず並ぶ 10 行(消す引数も option も無い)**
MOTANAI: dict[str, str] = {
    "収録すべきかを決めない":
        "推奨・順位・点数・合計の 1 値を出す列が無い。終了コード 0 も「別枠と (A)(B) が"
        "台帳に無い」の意味で、収録しなくてよいの意味ではない",
    "必須かどうかを判断しない":
        "必須の欄は入力の文字列を出典ごと写すだけで、空の行には `必須の記載なし` を"
        "入れる。要るかどうかを言い当てる辞書も分類器も持たない",
    "領域の線を引き直さない":
        "内 / 外 / 境界として明示 の 3 値は領域の登録表から取るだけで、判定の辞書を"
        "持たない。登録表に無い記号は別枠へ出す",
    "項目名から領域を推測しない":
        "項目名の欄は一覧に写すだけで、判定に使う経路が無い",
    "条文や規約を読まない":
        "取りに行かない・走らせない・実行しない・import しない・構文解析しない・"
        "通信の経路が無い・入力フォルダの外を読まない",
    "0 件と欄が無いを同じ値にしない":
        "行数を数えない在り所(第2層 / case属性 / 無い / 行が無い)は `数えられない` を"
        "返し、台帳に 0 と書かれた行とは別の値になる",
    "割合を単独で返さない":
        "カバー率の 1 値を出す列が無い。必ず 2 通りの分母(項目数と、在り所の台帳が"
        "数えた行数)が付く",
    "時計を読まない": "基準日は呼び出し側が渡す。現在時刻を読む呼び出しを持たない",
    "入力を書き換えない":
        "verify が作る写しはメモリの中だけで、6 枚の CSV に 1 文字も書かない",
    "float を使わない": "行数と件数は整数、ほかは文字列",
}


def off_scope(items: Items, domains: Domains, placements: Placements,
              shapes: Shapes, basis: NameRegistry, payload: NameRegistry,
              asof: str) -> Table:
    """6 枚から項目ごとの 4 値を出す。**登録の側が壊れていたら 1 項目も数えない。**"""
    pending: list[Pending] = []
    for reg in (domains, basis, payload):
        for name in reg.sourceless():
            pending.append(Pending(TABLE_REASONS[0], f"{reg.what} の {name}"))
    for item_id in items.duplicated():
        pending.append(Pending(TABLE_REASONS[1], f"項目 {item_id}"))
    for bad in domains.bad_stance():
        pending.append(Pending(TABLE_REASONS[2], f"領域の登録表の {bad}"))
    for bad in placements.bad_place():
        pending.append(Pending(TABLE_REASONS[3], bad))
    for bad in placements.not_integer():
        pending.append(Pending(TABLE_REASONS[4], bad))
    try:
        base = dt.date.fromisoformat(asof) if asof else None
    except ValueError:
        base = None
    if base is None:
        pending.append(Pending(TABLE_REASONS[5], f"基準日 {asof!r}"))
    for reg in (domains, basis, payload):
        if not reg.items:
            pending.append(Pending(TABLE_REASONS[6], reg.what))

    if pending:
        return Table(items, domains, placements, shapes, basis, payload, asof, (),
                     Report(False, tuple(pending)))
    rows = tuple(judge(items.of(item_id), placements.of_item(item_id),
                       shapes.of_item(item_id), domains, basis, payload)
                 for item_id in items.ids)
    return Table(items, domains, placements, shapes, basis, payload, asof, rows,
                 Report(True, ()))


# ------------------------------------------------------------ verify(5 つ)

def moved(first: Table, after: Table) -> list[str]:
    a = {x.item_id: x.value for x in first.rows}
    b = {x.item_id: x.value for x in after.rows}
    return sorted(k for k in a if a[k] != b.get(k))


def row_probe_plan(first: Table) -> str | None:
    """在り所が `無い` の (A) の 1 件目(ここに行が 1 行在ることにすると (B) へ移る)。"""
    for x in sorted(first.rows, key=lambda r: r.item_id):
        if x.value == VALUES[0] and x.place == PLACES[4]:
            return x.item_id
    return None


def row_probe(items: Items, domains: Domains, placements: Placements,
              shapes: Shapes, basis: NameRegistry, payload: NameRegistry,
              asof: str, item_id: str) -> Table:
    """**写しはメモリの中だけ。** 在り所の台帳の CSV には 1 文字も書かない。"""
    rows: list[list[str]] = []
    for r in placements.rows:
        r = list(r)
        if r[0] == item_id and r[1] == PLACES[4]:
            r[1], r[2], r[3] = PLACES[0], "1", ORIGINS[0]
        rows.append(r)
    return off_scope(items, domains, Placements(rows, placements.item_ids), shapes,
                     basis, payload, asof)


def sourceless_graded(table: Table) -> list[str]:
    """出典が空のまま 4 値に入った項目(**0 件でなければならない**)。"""
    out: list[str] = []
    for x in table.rows:
        if not x.graded:
            continue
        item = table.items.of(x.item_id)
        shape = table.shapes.of_item(x.item_id)
        if (not item.source or any(not p.source
                                   for p in table.placements.of_item(x.item_id))
                or (shape is not None and not shape.source)):
            out.append(x.item_id)
    return sorted(out)


def verify(items: Items, domains: Domains, placements: Placements, shapes: Shapes,
           basis: NameRegistry, payload: NameRegistry,
           asof: str) -> dict[str, object]:
    """5 つ見る(二度走り + 行順 3 通り / 件数の検算 / (B) の行数 / 2 通りの分母と
    出典が空の行 / 在り所に 1 行足す)。"""
    first = off_scope(items, domains, placements, shapes, basis, payload, asof)
    if not first.report.ok:
        return {"ok": False, "止まった": [p.as_dict() for p in first.report.pending]}
    again = off_scope(items, domains, placements, shapes, basis, payload, asof)
    same_twice = again.sha256() == first.sha256()
    swapped: list[bool] = []
    for how in SWAPS:
        t = off_scope(items.swapped(how), domains.swapped(how),
                      placements.swapped(how), shapes.swapped(how),
                      basis.swapped(how), payload.swapped(how), asof)
        swapped.append(t.sha256() == first.sha256())
    total = sum(first.five().values()) + sum(first.extras().values())
    sums_ok = (total == first.denominator()
               and sum(int(r["項目の件数"]) for r in first.by_stance()) == total
               and sum(int(r["項目の件数"]) for r in first.by_place()) == total)

    b_ids = {x.item_id for x in first.rows if x.value == VALUES[1]}
    ledger = sum(int(x.count) for x in placements.items
                 if x.item_id in b_ids and x.counts and x.count.isdigit())
    rows_ok = int(first.counted_rows()["(B) の行数の合計"]) == ledger

    dens = first.denominators()
    sourceless = sourceless_graded(first)
    grounded_ok = ("項目数" in dens and "行数(在り所の台帳が数えた行)" in dens
                   and not sourceless)

    probe: dict[str, object] = {"やったこと": "在り所が 無い の (A) の項目が無い",
                                "ok": True}
    iid = row_probe_plan(first)
    if iid:
        after = row_probe(items, domains, placements, shapes, basis, payload,
                          asof, iid)
        got = {x.item_id: x.value for x in after.rows}[iid]
        probe = {"やったこと": f"項目 {iid} の在り所を 無い → 収録(1 行)にした",
                 "移った項目": moved(first, after), "移った先": got,
                 "ok": moved(first, after) == [iid] and got == VALUES[1]}

    return {"ok": bool(same_twice and all(swapped) and sums_ok and rows_ok
                       and grounded_ok and probe["ok"]),
            "二度走りの判定部分が同一": same_twice,
            "行順を入れ替えても同一": dict(zip(SWAPS, swapped)),
            "件数の合計": first.crosscheck(), "合計が合う": sums_ok,
            "(B) の行数が在り所の台帳と合う": rows_ok,
            "収録の量": first.counted_rows(),
            "2 通りの分母": dens,
            "出典が空のまま 4 値に入った項目": sourceless,
            "在り所に 1 行足す": probe,
            "判定部分の sha256": first.sha256(),
            "入力を書き換えない": MOTANAI["入力を書き換えない"]}


# ------------------------------------------------------------ ひな型

T_ITEM = "合成の項目のメモ(架空)L1"
T_DOMAIN = "合成の領域の登録のメモ(架空)L1"
T_PLACE = "合成の在り所のメモ(架空)L1"
T_SHAPE = "合成の入る形のメモ(架空)L1"
T_BASIS = "合成の basis の登録のメモ(架空)L1"
T_PAYLOAD = "合成の payload の登録のメモ(架空)L1"

TEMPLATE_ITEMS = [list(ITEM_COLUMNS),
                  ["I01", "合成の項目 A(架空)", "領域 1",
                   "合成の必須の宣言(架空)", NO_MARK, T_ITEM],
                  ["I02", "合成の項目 B(架空)", "領域 2",
                   "合成の必須の宣言(架空)", NO_MARK, T_ITEM]]
TEMPLATE_DOMAINS = [list(DOMAIN_COLUMNS),
                    ["領域 1", STANCES[1], T_DOMAIN],
                    ["領域 2", STANCES[2], T_DOMAIN]]
TEMPLATE_PLACES = [list(PLACE_COLUMNS),
                   ["I01", PLACES[4], NO_MARK, NO_MARK, T_PLACE],
                   ["I02", PLACES[4], NO_MARK, NO_MARK, T_PLACE]]
TEMPLATE_SHAPES = [list(SHAPE_COLUMNS),
                   ["I02", "基準日 A", "表", "区分 / 人数", NO_MARK, T_SHAPE]]
TEMPLATE_BASIS = [list(BASIS_COLUMNS),
                  ["基準日 A", "合成の欄名(架空)", T_BASIS]]
TEMPLATE_PAYLOAD = [list(PAYLOAD_COLUMNS),
                    ["表", "合成の種別(架空)", T_PAYLOAD]]


def write_csv(path: Path, rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    return path


def init(dest: str | Path) -> tuple[Path, ...]:
    d = Path(dest)
    return tuple([write_csv(d / "項目の台帳.csv", TEMPLATE_ITEMS),
                  write_csv(d / "領域の登録表.csv", TEMPLATE_DOMAINS),
                  write_csv(d / "在り所の台帳.csv", TEMPLATE_PLACES),
                  write_csv(d / "入る形の宣言表.csv", TEMPLATE_SHAPES),
                  write_csv(d / "basisの登録表.csv", TEMPLATE_BASIS),
                  write_csv(d / "payloadの登録表.csv", TEMPLATE_PAYLOAD)])


# ------------------------------------------------------------ CLI

def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def build_parser() -> argparse.ArgumentParser:
    """CLI は check / report / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = argparse.ArgumentParser(prog="off_scope",
                                 description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in SUBCOMMANDS[:3]:
        p = sub.add_parser(name)
        for arg in ("items", "domains", "placements", "shapes", "basis", "payload",
                    "asof"):
            p.add_argument(arg)
    sub.add_parser(SUBCOMMANDS[3]).add_argument("dest")
    return ap


def load_six(a) -> tuple[Items, Domains, Placements, Shapes, NameRegistry,
                         NameRegistry]:
    items = Items.load(a.items)
    ids = items.ids
    return (items, Domains.load(a.domains), Placements.load(a.placements, ids),
            Shapes.load(a.shapes, ids), load_basis(a.basis), load_payload(a.payload))


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == SUBCOMMANDS[3]:
        print("書いた: " + " / ".join(str(p) for p in init(a.dest)))
        return 0
    try:
        six = load_six(a)
        if a.cmd == SUBCOMMANDS[2]:
            out = verify(*six, a.asof)
            _print(out)
            return 0 if out["ok"] else 3
        t = off_scope(*six, a.asof)
    except ReadError as e:
        print(f"表として読めない: {e}", file=sys.stderr)
        return 2
    if not t.report.ok:
        _print({"ok": False, "stage": "止まった(4 値は返さない)",
                "基準日": a.asof, "2 通りの分母": {"項目数": 0, "行数": {}},
                "pending": [p.as_dict() for p in t.report.pending]})
        return 3
    body: dict[str, object] = {"ok": True, **t.counts()}
    if a.cmd == SUBCOMMANDS[1]:
        body["項目ごとの一覧"] = t.listed()
        body["領域の宣言ごと"] = t.by_stance()
        body["在り所ごと"] = t.by_place()
        body["sha256"] = t.sha256()
        body["読んだ条件"] = t.read_condition()
    _print(body)
    five = t.five()
    clean = (not sum(t.extras().values()) and not t.stopped()
             and not five[VALUES[0]] and not five[VALUES[1]])
    return 0 if clean else 3


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
