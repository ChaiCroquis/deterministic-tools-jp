"""overlap_check — 年度の違う資料から取った抽出表どうしの、重なる欄だけを突き合わせる。

**公的な数表の資料は「変更前」と「変更後」を並べて出すので、同じ数字が 2 枚の資料に現れる。
その重なりは「突き合わせて検算にする」ことにも「片方しか資料が無い年を埋めて収録を 1 年
伸ばす」ことにも使えるが、同じ欄を両方の役に使うと一致件数が何を語っているか分からなくなる。**

この部品は、年度ごとの抽出表・名前の寄せ方の表・行ごとの採用元の宣言・問いの一覧の 4 枚から、
問い 1 件ごとに 7 値(**一致 / 不一致 / 重なりが無い / 寄せ方が無い / 採用元が同じ欄** の 5 値 +
別枠 **単位がそろわない / 資料が手元に無い**)を付ける。不一致の組は両側の値と出典を並べ、
「採用元が同じ欄」だけの一覧も別に返す。**値を計算しない。どちらの年度を正とも決めない。
原文を取りに行かない。数えるだけだ。**

持たせていないものが規律になっている。

  - **項目名を自動で寄せない**(寄せ方の表に無い項目は比べずに「寄せ方が無い」に出す。同じ
    文字列でも寄せたことを宣言させる = 表記ゆれを部品が判断する経路が無い)
  - **採用元と同じ欄との比較を突合に数えない**(行の値を採った欄が、突き合わせに使う今年の
    変更前の欄そのものなら「採用元が同じ欄」に分ける。自分自身との一致を件数に混ぜる経路が無い)
  - **どちらの年度を正とも決めない**(不一致は両方の値と両方の出典を並べて返すだけ。正を選ぶ
    引数も、優先順位の欄も無い)
  - **不一致を直さない・片方だけの項目を新設とも廃止とも取り逃しとも決めつけない**(「重なりが
    無い」の 1 値にまとめ、理由は人に戻す)
  - **資料そのものが手元に無い年度は別枠**(重なり候補の分母から外し、外した件数と年度を出す)
  - **値を計算しない・式を評価しない・丸め直さない**(文字列として取った値をそのまま比べ、
    単位の宣言がそろわない組は別枠)
  - **一致率を割合にしない**(件数と 3 つの分母の内訳だけを返す)
  - **出典の欄が空の行は使わずに止まる**
  - **原文を取りに行かない**(ネットワークに触る経路が無い。入力は手元の抽出表のみ)
  - **同じ年度どうしを突き合わせる指定を受け付けない**(その問いだけ止まる)
  - **入力表を書き換えず、行も項目も生成しない**
  - **同じ入力には同じバイト列**(判定部分に時刻・絶対パス・ホスト名を入れない。行順にも依らない)
  - **数は整数だけ**

入力は 4 つ。年度ごとの抽出表(CSV)、名前の寄せ方の表(CSV)、採用元の宣言(CSV)、問いの
一覧(CSV)。

抽出表の列は 7 つ。**1 つの資料の 1 つの欄の 1 項目が 1 行**。

    doc_id   資料 id
    year     年度(1 つの年度に 2 つの資料 id は置けない)
    item     項目名(資料に書かれたまま。寄せない)
    role     欄の役(変更前 / 変更後)
    unit     単位・桁の宣言。空欄はその組を別枠へ
    value    値(文字列としてそのまま比べる)。空欄は止まる
    source   出典。空欄は止まる

名前の寄せ方の表の列は 4 つ。**1 つの寄せが 1 行**。

    item_a   年度 A(去年)の項目名。同じ項目名が 2 行あると止まる
    item_b   年度 B(今年)の項目名
    reason   寄せてよい理由。空欄は止まる
    source   出典。空欄は止まる

採用元の宣言の列は 5 つ。**収録した行 1 件が 1 行**。

    row_id   行 id
    item     項目名(年度 A の名前)
    doc_id   どの資料から採ったか(抽出表に無い id は止まる)
    role     どちらの欄から採ったか(変更前 / 変更後。登録外は止まる)
    source   出典。空欄は止まる

問いの一覧の列は 5 つ。**1 つの突き合わせが 1 行**。

    year_a   去年の年度(この資料の「変更後」欄が経路 A)
    year_b   今年の年度(この資料の「変更前」欄が経路 B)
    item     対象の項目名(年度 A の名前)
    source   出典。空欄は止まる
    swap     入れ替え方。verify が 4 枚の行順を入れ替えるときの宣言

使い方:

    python overlap_check.py init ひな型/
    python overlap_check.py check   抽出表.csv 名前の寄せ方.csv 採用元の宣言.csv 問いの一覧.csv
    python overlap_check.py overlap 抽出表.csv 名前の寄せ方.csv 採用元の宣言.csv 問いの一覧.csv
    python overlap_check.py verify  抽出表.csv 名前の寄せ方.csv 採用元の宣言.csv 問いの一覧.csv

終了コードは、別枠と止まった問いが 0 件のときだけ 0、在れば 3、表として読めなければ 2。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

CHUUSHUTSU_COLUMNS = ("doc_id", "year", "item", "role", "unit", "value", "source")
YOSE_COLUMNS = ("item_a", "item_b", "reason", "source")
SAIYOU_COLUMNS = ("row_id", "item", "doc_id", "role", "source")
TOI_COLUMNS = ("year_a", "year_b", "item", "source", "swap")

# 欄の役(登録制)。既定は持たない = 空欄をどちらかに読み替える経路が無い
ROLES = ("変更前", "変更後")
MAE, ATO = ROLES

# 問い 1 件に付く 7 値。前の 5 つが判定、後の 2 つが別枠。7 つを混ぜない
RESULTS = ("一致", "不一致", "重なりが無い", "寄せ方が無い", "採用元が同じ欄",
           "単位がそろわない", "資料が手元に無い")
GOUI = RESULTS[:5]          # 重なり候補の 5 値
ASIDE = RESULTS[5:]         # 別枠 2 種
TOTSUGOU = RESULTS[:2]      # 突き合わせが成立した 2 値(一致 / 不一致)
SOTO = RESULTS[6]           # 重なり候補の分母から外す 1 種

SWAPS = ("逆順", "両端入れ替え", "1 つずらす")

STOP_REASONS = (
    # 表の側。1 行も数えずに止まる(9)
    "出典の欄が空", "値の欄が空", "同じ資料 id と欄の役と項目名の組が 2 行ある",
    "寄せてよい理由が空", "同じ年度 A の項目名が 2 行ある",
    "採用元の欄の役が登録の 2 つでない", "採用元の資料 id が抽出表に無い",
    "同じ項目名の採用元が 2 行ある", "採用元の宣言が無い",
    # 問い 1 件の側。その問いだけ止まる(1)
    "同じ年度を突き合わせる指定",
    # verify が見つける(3)
    "件数の合計が合わない", "2 回目の判定部分が不一致", "行順を入れ替えた表で出力が変わる",
)
TABLE_REASONS = STOP_REASONS[:9]
QUESTION_REASONS = STOP_REASONS[9:10]
VERIFY_REASONS = STOP_REASONS[10:]

SUBCOMMANDS = ("overlap", "check", "verify", "init")
SCOPE_KEYS = ("読んだ抽出表の絶対パス", "読んだ名前の寄せ方の表の絶対パス",
              "読んだ採用元の宣言の絶対パス", "読んだ問いの一覧の絶対パス")

NG_ID = set(" \t,|")


class ReadError(Exception):
    """表として読めない(終了コード 2)。問いは 1 件も数えない。"""


@dataclass(frozen=True)
class Pending:
    reason: str
    detail: str = ""

    def as_dict(self) -> dict[str, str]:
        return {"理由コード": self.reason, "どこ": self.detail}


def bad_id(s: str) -> bool:
    return (not s) or any(ch in NG_ID for ch in s)


def swap_rows(rows: list, how: str) -> list:
    """宣言された入れ替え方で行順を入れ替える(verify が使う)。"""
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


# ------------------------------------------------------------ 年度ごとの抽出表


@dataclass(frozen=True)
class Cell:
    """抽出表 1 行 = 1 つの資料の 1 つの欄の 1 項目。**値は文字列のまま持つ。**"""
    doc_id: str
    year: str
    item: str
    role: str
    unit: str
    value: str
    source: str
    number: int = 0

    def issues(self) -> tuple[Pending, ...]:
        where = f"抽出表 行 {self.number}({self.doc_id} / {self.role} / {self.item})"
        out: list[Pending] = []
        if not self.source:
            out.append(Pending(STOP_REASONS[0], where))
        if not self.value:
            out.append(Pending(STOP_REASONS[1], where))
        return tuple(out)

    def as_value(self, value: str) -> "Cell":
        return Cell(self.doc_id, self.year, self.item, self.role, self.unit, value,
                    self.source, self.number)


@dataclass(frozen=True)
class Extracts:
    items: tuple[Cell, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Extracts":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"抽出表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Extracts":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in CHUUSHUTSU_COLUMNS
                if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("抽出表に " + " / ".join(lack) + " の列が無い")
        items: list[Cell] = []
        pending: list[Pending] = []
        seen: set[tuple[str, str, str]] = set()
        year_of: dict[str, str] = {}
        doc_of: dict[str, str] = {}
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in CHUUSHUTSU_COLUMNS}
            where = f"抽出表 行 {i}"
            for key, name in (("doc_id", "資料 id"), ("year", "年度"),
                              ("item", "項目名")):
                if bad_id(cell[key]):
                    raise ReadError(f"{where}: {name}が空欄か、区切り文字を含む"
                                    f"({cell[key] or '空欄'})")
            if cell["role"] not in ROLES:
                raise ReadError(f"{where}: 欄の役が登録の 2 つでない"
                                f"({cell['role'] or '空欄'})")
            if year_of.setdefault(cell["doc_id"], cell["year"]) != cell["year"]:
                raise ReadError(f"{where}: 同じ資料 id に 2 つの年度がある"
                                f"({cell['doc_id']})")
            if doc_of.setdefault(cell["year"], cell["doc_id"]) != cell["doc_id"]:
                raise ReadError(f"{where}: 同じ年度に 2 つの資料 id がある"
                                f"({cell['year']})")
            key3 = (cell["doc_id"], cell["role"], cell["item"])
            if key3 in seen:
                pending.append(Pending(STOP_REASONS[2],
                                       f"{where}: {' / '.join(key3)}"))
            seen.add(key3)
            items.append(Cell(doc_id=cell["doc_id"], year=cell["year"],
                              item=cell["item"], role=cell["role"],
                              unit=cell["unit"], value=cell["value"],
                              source=cell["source"], number=i))
        if not items:
            raise ReadError("抽出表に行が無い(ヘッダだけ)")
        for c in items:
            pending.extend(c.issues())
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    @property
    def ordered(self) -> tuple[Cell, ...]:
        """資料 id・欄の役・項目名の順(行順に依らない = 入れ替えても同じ出力)。"""
        return tuple(sorted(self.items, key=lambda c: (c.doc_id, c.role, c.item)))

    @property
    def docs(self) -> tuple[str, ...]:
        return tuple(sorted({c.doc_id for c in self.items}))

    @property
    def years(self) -> tuple[str, ...]:
        return tuple(sorted({c.year for c in self.items}))

    def doc_of_year(self, year: str) -> str | None:
        """その年度の資料 id。**手元に無い年度には何も当てない**(None を返す = 別枠へ)。"""
        return next((c.doc_id for c in self.ordered if c.year == year), None)

    def cell(self, doc_id: str, role: str, item: str) -> Cell | None:
        return next((c for c in self.ordered
                     if (c.doc_id, c.role, c.item) == (doc_id, role, item)), None)

    def swapped(self, how: str) -> "Extracts":
        return Extracts(items=tuple(swap_rows(list(self.items), how)),
                        pending=self.pending, path=self.path)

    def with_value(self, doc_id: str, role: str, item: str, value: str) -> "Extracts":
        """欄 1 つの値を替えた写し(テストが使う。入力には書かない)。"""
        return Extracts(items=tuple(c.as_value(value)
                                    if (c.doc_id, c.role, c.item)
                                    == (doc_id, role, item) else c
                                    for c in self.items),
                        pending=self.pending, path=self.path)


# ------------------------------------------------------------ 名前の寄せ方の表


@dataclass(frozen=True)
class Bridge:
    """項目名 1 組の寄せ方。**同じ文字列でも宣言させる**(寄せたことを記録に残す)。"""
    item_a: str
    item_b: str
    reason: str
    source: str
    number: int = 0

    def issues(self) -> tuple[Pending, ...]:
        where = f"名前の寄せ方の表 行 {self.number}({self.item_a} → {self.item_b})"
        out: list[Pending] = []
        if not self.source:
            out.append(Pending(STOP_REASONS[0], where))
        if not self.reason:
            out.append(Pending(STOP_REASONS[3], where))
        return tuple(out)


@dataclass(frozen=True)
class Bridges:
    items: tuple[Bridge, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Bridges":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"名前の寄せ方の表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Bridges":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in YOSE_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("名前の寄せ方の表に " + " / ".join(lack) + " の列が無い")
        items: list[Bridge] = []
        pending: list[Pending] = []
        seen: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in YOSE_COLUMNS}
            where = f"名前の寄せ方の表 行 {i}"
            for key, name in (("item_a", "年度 A の項目名"),
                              ("item_b", "年度 B の項目名")):
                if bad_id(cell[key]):
                    raise ReadError(f"{where}: {name}が空欄か、区切り文字を含む"
                                    f"({cell[key] or '空欄'})")
            if cell["item_a"] in seen:
                pending.append(Pending(STOP_REASONS[4], f"{where}: {cell['item_a']}"))
            seen.add(cell["item_a"])
            items.append(Bridge(item_a=cell["item_a"], item_b=cell["item_b"],
                                reason=cell["reason"], source=cell["source"],
                                number=i))
        if not items:
            raise ReadError("名前の寄せ方の表に行が無い(ヘッダだけ)")
        for b in items:
            pending.extend(b.issues())
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    @property
    def ordered(self) -> tuple[Bridge, ...]:
        return tuple(sorted(self.items, key=lambda b: (b.item_a, b.item_b)))

    def to(self, item_a: str) -> Bridge | None:
        """宣言されていない項目名は**寄せない**(None を返す = 「寄せ方が無い」へ)。"""
        return next((b for b in self.ordered if b.item_a == item_a), None)

    def without(self, item_a: str) -> "Bridges":
        """寄せ方 1 組を外した写し(verify が使う。入力には書かない)。"""
        return Bridges(items=tuple(b for b in self.items if b.item_a != item_a),
                       pending=self.pending, path=self.path)

    def swapped(self, how: str) -> "Bridges":
        return Bridges(items=tuple(swap_rows(list(self.items), how)),
                       pending=self.pending, path=self.path)


# ------------------------------------------------------------ 採用元の宣言


@dataclass(frozen=True)
class Take:
    """収録した行 1 件が、どの資料のどちらの欄から値を採ったかの宣言。"""
    row_id: str
    item: str
    doc_id: str
    role: str
    source: str
    number: int = 0

    def issues(self, docs: tuple[str, ...]) -> tuple[Pending, ...]:
        where = f"採用元の宣言 行 {self.number}({self.row_id}: {self.item})"
        out: list[Pending] = []
        if not self.source:
            out.append(Pending(STOP_REASONS[0], where))
        if self.role not in ROLES:
            out.append(Pending(STOP_REASONS[5], f"{where}: {self.role or '空欄'}"))
        if self.doc_id not in docs:
            out.append(Pending(STOP_REASONS[6], f"{where}: {self.doc_id}"))
        return tuple(out)

    def as_source(self, doc_id: str, role: str) -> "Take":
        return Take(self.row_id, self.item, doc_id, role, self.source, self.number)


@dataclass(frozen=True)
class Takes:
    items: tuple[Take, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Takes":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"採用元の宣言が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Takes":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in SAIYOU_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("採用元の宣言に " + " / ".join(lack) + " の列が無い")
        items: list[Take] = []
        pending: list[Pending] = []
        seen_id: set[str] = set()
        seen_item: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in SAIYOU_COLUMNS}
            where = f"採用元の宣言 行 {i}"
            for key, name in (("row_id", "行 id"), ("item", "項目名"),
                              ("doc_id", "資料 id")):
                if bad_id(cell[key]):
                    raise ReadError(f"{where}: {name}が空欄か、区切り文字を含む"
                                    f"({cell[key] or '空欄'})")
            if cell["row_id"] in seen_id:
                raise ReadError(f"{where}: 同じ行 id が 2 行ある({cell['row_id']})")
            seen_id.add(cell["row_id"])
            if cell["item"] in seen_item:
                pending.append(Pending(STOP_REASONS[7], f"{where}: {cell['item']}"))
            seen_item.add(cell["item"])
            items.append(Take(row_id=cell["row_id"], item=cell["item"],
                              doc_id=cell["doc_id"], role=cell["role"],
                              source=cell["source"], number=i))
        if not items:
            raise ReadError("採用元の宣言に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    @property
    def ordered(self) -> tuple[Take, ...]:
        return tuple(sorted(self.items, key=lambda t: t.row_id))

    def of(self, item: str) -> Take | None:
        return next((t for t in self.ordered if t.item == item), None)

    def restated(self, item: str, doc_id: str, role: str) -> "Takes":
        """行 1 件の採用元を替えた写し(verify が使う。入力には書かない)。"""
        return Takes(items=tuple(t.as_source(doc_id, role) if t.item == item else t
                                 for t in self.items),
                     pending=self.pending, path=self.path)

    def swapped(self, how: str) -> "Takes":
        return Takes(items=tuple(swap_rows(list(self.items), how)),
                     pending=self.pending, path=self.path)


# ------------------------------------------------------------ 問いの一覧


@dataclass(frozen=True)
class Question:
    year_a: str
    year_b: str
    item: str
    source: str
    number: int = 0

    @property
    def pair(self) -> str:
        return f"{self.year_a} × {self.year_b}"

    def issues(self) -> tuple[Pending, ...]:
        where = f"問いの一覧 行 {self.number}({self.pair} / {self.item})"
        return (Pending(STOP_REASONS[0], where),) if not self.source else ()


@dataclass(frozen=True)
class Questions:
    items: tuple[Question, ...]
    pending: tuple[Pending, ...] = ()
    swap: str = ""
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Questions":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"問いの一覧が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Questions":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in TOI_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("問いの一覧に " + " / ".join(lack) + " の列が無い")
        items: list[Question] = []
        seen: set[tuple[str, str, str]] = set()
        swaps: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in TOI_COLUMNS}
            where = f"問いの一覧 行 {i}"
            for key, name in (("year_a", "去年の年度"), ("year_b", "今年の年度"),
                              ("item", "対象の項目名")):
                if bad_id(cell[key]):
                    raise ReadError(f"{where}: {name}が空欄か、区切り文字を含む"
                                    f"({cell[key] or '空欄'})")
            key3 = (cell["year_a"], cell["year_b"], cell["item"])
            if key3 in seen:
                raise ReadError(f"{where}: 同じ問いが 2 行ある({' / '.join(key3)})")
            seen.add(key3)
            if cell["swap"]:
                swaps.add(cell["swap"])
            items.append(Question(year_a=cell["year_a"], year_b=cell["year_b"],
                                  item=cell["item"], source=cell["source"],
                                  number=i))
        if not items:
            raise ReadError("問いの一覧に行が無い(ヘッダだけ)")
        if len(swaps) > 1:
            raise ReadError("入れ替え方の宣言が 2 通りある: " + " / ".join(sorted(swaps)))
        how = swaps.pop() if swaps else ""
        if how and how not in SWAPS:
            raise ReadError(f"登録されていない入れ替え方: {how}")
        pending: list[Pending] = []
        for q in items:
            pending.extend(q.issues())
        return cls(items=tuple(items), pending=tuple(pending), swap=how, path=path)

    @property
    def ordered(self) -> tuple[Question, ...]:
        return tuple(sorted(self.items, key=lambda q: (q.year_a, q.year_b, q.item)))

    @property
    def pairs(self) -> tuple[str, ...]:
        return tuple(sorted({q.pair for q in self.items}))

    def swapped(self, how: str) -> "Questions":
        return Questions(items=tuple(swap_rows(list(self.items), how)),
                         pending=self.pending, swap=self.swap, path=self.path)


# ------------------------------------------------------------ 突き合わせる


@dataclass(frozen=True)
class Judged:
    """問い 1 件の結果。止まった問いと、片側の欄が無い問いは、両側の欄を持たない。"""
    question: Question
    result: str
    stopped: bool = False
    reason: str = ""
    cell_a: Cell | None = None
    cell_b: Cell | None = None

    @property
    def candidate(self) -> bool:
        """重なり候補か(資料が手元に無い問いと、止まった問いは分母の外)。"""
        return not self.stopped and self.result != SOTO

    def line(self) -> str:
        return (f"{self.question.year_a}>{self.question.year_b}:{self.question.item}"
                f":{'止まった' if self.stopped else self.result}:{self.reason}")

    def both_sides(self) -> dict[str, object]:
        """両経路の値と出典を並べる。**どちらが正しいとは書かない。**"""
        return {"年度ペア": self.question.pair, "項目名(年度 A)": self.question.item,
                "項目名(年度 B)": self.cell_b.item if self.cell_b else "",
                "経路 A(去年の変更後)": {
                    "資料 id": self.cell_a.doc_id if self.cell_a else "",
                    "値": self.cell_a.value if self.cell_a else "",
                    "単位": self.cell_a.unit if self.cell_a else "",
                    "出典": self.cell_a.source if self.cell_a else ""},
                "経路 B(今年の変更前)": {
                    "資料 id": self.cell_b.doc_id if self.cell_b else "",
                    "値": self.cell_b.value if self.cell_b else "",
                    "単位": self.cell_b.unit if self.cell_b else "",
                    "出典": self.cell_b.source if self.cell_b else ""},
                "問いの出典": self.question.source}


def judge(q: Question, extracts: Extracts, bridges: Bridges,
          takes: Takes) -> Judged:
    """問い 1 件に 7 値のどれか 1 つを付ける。**項目名を寄せない。正も決めない。**

    同じ年度どうしの指定はその問いだけ止まる(同じ資料の 2 欄は年度をまたぐ重なりではない)。
    どちらかの年度の資料が手元に無ければ別枠。寄せ方の宣言が無い項目は比べずに「寄せ方が
    無い」。片側の欄が無ければ「重なりが無い」(新設とも取り逃しとも決めつけない)。単位の
    宣言がそろわなければ別枠。**行の値を採った欄が経路 B そのものなら「採用元が同じ欄」。**
    """
    if q.year_a == q.year_b:
        return Judged(q, RESULTS[2], stopped=True, reason=STOP_REASONS[9])
    doc_a, doc_b = extracts.doc_of_year(q.year_a), extracts.doc_of_year(q.year_b)
    if doc_a is None or doc_b is None:
        return Judged(q, SOTO)
    bridge = bridges.to(q.item)
    if bridge is None:
        return Judged(q, RESULTS[3])
    cell_a = extracts.cell(doc_a, ATO, q.item)
    cell_b = extracts.cell(doc_b, MAE, bridge.item_b)
    if cell_a is None or cell_b is None:
        return Judged(q, RESULTS[2], cell_a=cell_a, cell_b=cell_b)
    if not cell_a.unit or not cell_b.unit or cell_a.unit != cell_b.unit:
        return Judged(q, RESULTS[5], cell_a=cell_a, cell_b=cell_b)
    take = takes.of(q.item)
    if take is not None and (take.doc_id, take.role) == (doc_b, MAE):
        return Judged(q, RESULTS[4], cell_a=cell_a, cell_b=cell_b)
    same = cell_a.value == cell_b.value
    return Judged(q, RESULTS[0] if same else RESULTS[1], cell_a=cell_a, cell_b=cell_b)


@dataclass(frozen=True)
class Report:
    ok: bool
    pending: tuple[Pending, ...]
    cells: int
    bridges: int
    takes: int
    questions: int


@dataclass(frozen=True)
class Tally:
    report: Report
    judged: tuple[Judged, ...]
    extracts: Extracts
    bridges: Bridges
    takes: Takes
    questions: Questions

    # ---------------- 分母

    def question_denominator(self) -> int:
        return self.report.questions

    @property
    def denominator(self) -> int:
        """重なり候補の数(資料が手元に無い問いと、止まった問いを外した数)。"""
        return sum(1 for j in self.judged if j.candidate)

    def aside_denominator(self) -> int:
        return sum(1 for j in self.judged if not j.stopped and j.result in ASIDE)

    def halted(self) -> int:
        return sum(1 for j in self.judged if j.stopped)

    def missing_years(self) -> list[str]:
        """分母から外した年度(手元に資料が無い年度)。件数と年度を必ず出す。"""
        out: set[str] = set()
        for j in self.judged:
            if j.result == SOTO and not j.stopped:
                for year in (j.question.year_a, j.question.year_b):
                    if self.extracts.doc_of_year(year) is None:
                        out.add(year)
        return sorted(out)

    # ---------------- 件数

    def seven(self) -> dict[str, int]:
        return {r: sum(1 for j in self.judged if not j.stopped and j.result == r)
                for r in RESULTS}

    def by_pair(self) -> list[dict[str, object]]:
        """年度ペアごとの 7 値(内訳の合計が全体に戻るかが二重集計の検算になる)。"""
        out: list[dict[str, object]] = []
        for pair in self.questions.pairs:
            here = [j for j in self.judged if j.question.pair == pair]
            cells = {r: sum(1 for j in here if not j.stopped and j.result == r)
                     for r in RESULTS}
            out.append({"年度ペア": pair, "問いの数": len(here), "7 値": cells,
                        "重なり候補": sum(1 for j in here if j.candidate),
                        "止まった": sum(1 for j in here if j.stopped),
                        "突き合わせが成立": sum(cells[r] for r in TOTSUGOU)})
        return out

    def mismatches(self) -> list[dict[str, object]]:
        """不一致の組は両側の値と出典を並べるだけ。**どちらが正とも書かない。**"""
        return [j.both_sides() for j in self.judged if j.result == RESULTS[1]]

    def self_checks(self) -> list[dict[str, object]]:
        """「採用元が同じ欄」だけの一覧 = 検算に見えて検算になっていない行の名前。"""
        out: list[dict[str, object]] = []
        for j in self.judged:
            if j.result != RESULTS[4]:
                continue
            take = self.takes.of(j.question.item)
            out.append({"年度ペア": j.question.pair, "項目名": j.question.item,
                        "行 id": take.row_id if take else "",
                        "採用元": f"{take.doc_id} / {take.role}" if take else "",
                        "経路 B の欄": f"{j.cell_b.doc_id} / {MAE}" if j.cell_b else "",
                        "出典": take.source if take else ""})
        return out

    def no_overlap(self) -> list[dict[str, object]]:
        """重なりが無い組(片側しか欄が無い)。新設とも廃止とも取り逃しとも書かない。"""
        return [{"年度ペア": j.question.pair, "項目名": j.question.item,
                 "経路 A の欄": "在る" if j.cell_a else "無い",
                 "経路 B の欄": "在る" if j.cell_b else "無い",
                 "出典": j.question.source}
                for j in self.judged if j.result == RESULTS[2] and not j.stopped]

    def listed(self) -> list[dict[str, object]]:
        """7 値ごとに、問いと両側の欄を並べた一覧。"""
        out: list[dict[str, object]] = []
        for r in RESULTS:
            here = [j for j in self.judged if not j.stopped and j.result == r]
            out.append({"判定": r, "件数": len(here),
                        "問い": [j.both_sides() for j in here]})
        return out

    def stopped_questions(self) -> list[dict[str, str]]:
        return [{"年度ペア": j.question.pair, "項目名": j.question.item,
                 "理由コード": j.reason}
                for j in self.judged if j.stopped]

    def stopped(self) -> dict[str, int]:
        """理由別の止まった件数(表の側 + 問い 1 件の側)。"""
        out: dict[str, int] = {}
        for p in self.report.pending:
            out[p.reason] = out.get(p.reason, 0) + 1
        for j in self.judged:
            if j.stopped:
                out[j.reason] = out.get(j.reason, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: STOP_REASONS.index(kv[0])))

    def counts(self) -> dict[str, object]:
        """件数は丸めず、3 つの分母と内訳つきで出す。一致率も順位も返さない。"""
        seven = self.seven()
        out: dict[str, object] = {
            "抽出表の行数": self.report.cells,
            "名前の寄せ方の表の行数": self.report.bridges,
            "採用元の宣言の行数": self.report.takes,
            "問いの数": self.report.questions,
            "分母(問いの数)": self.question_denominator(),
            "分母(重なり候補の数)": self.denominator,
            "分母(別枠の数)": self.aside_denominator(),
            "7 値": seven,
            "突き合わせが成立した件数": sum(seven[r] for r in TOTSUGOU),
            "年度ペアごと": self.by_pair(),
            "分母から外した年度": self.missing_years(),
            "理由別の止まった件数": self.stopped(),
            "読んだか": ("読んだ" if self.judged else
                         "読んでいない(宣言が揃う前に止まったので 7 値は全て 0)"),
        }
        out["分母に含めたもの"] = (
            f"問いの数 {self.question_denominator()} 件のうち、止まった問い "
            f"{self.halted()} 件と、資料が手元に無い {seven[SOTO]} 件(年度 "
            f"{' / '.join(self.missing_years()) or '無し'})を外した "
            f"{self.denominator} 件が重なり候補。そのうち突き合わせが成立したのは "
            + " + ".join(f"{r} {seven[r]}" for r in TOTSUGOU)
            + f" の {sum(seven[r] for r in TOTSUGOU)} 件で、残りは "
            + " + ".join(f"{r} {seven[r]}" for r in RESULTS[2:6]))
        out["件数の合計の検算"] = (
            f"7 値の合計 {sum(seven.values())} + 止まった {self.halted()} / 問いの数 "
            f"{self.question_denominator()}(5 値 {sum(seven[r] for r in GOUI)} + "
            f"単位がそろわない {seven[RESULTS[5]]} = 重なり候補 {self.denominator} も"
            f"同じ、年度ペアごとの内訳の合計 "
            f"{sum(int(row['問いの数']) for row in self.by_pair())} = 問いの数 も同じ)")
        out["項目名を自動で寄せない"] = (
            "寄せ方の表に無い項目名は比べずに「寄せ方が無い」に出す。同じ文字列でも寄せた"
            "ことを宣言させるので、表記ゆれをこの部品が判断する経路が無い")
        out["採用元と同じ欄を突合に数えない"] = (
            "行の値を採った欄が経路 B(今年の変更前)そのものなら「採用元が同じ欄」に分ける。"
            "自分自身との一致を突き合わせの件数に混ぜる経路が無い")
        out["どちらの年度を正とも決めない"] = (
            "不一致は両方の値と両方の出典を並べて返すだけで、正を選ぶ引数も優先順位の欄も"
            "無い。直す経路も無い")
        out["片側しか無い項目を決めつけない"] = (
            "「重なりが無い」の 1 値にまとめ、新設・廃止・取り逃しのどれとも書かない。"
            "理由は読む人に戻す")
        out["一致率を割合にしない"] = (
            "何割が一致したかを返す呼び方も option も無い。件数には必ず 3 つの分母が付く")
        out["値を計算しない・原文を取りに行かない"] = (
            "値は文字列のまま比べ、式も丸めも持たない。単位の宣言がそろわない組は別枠に"
            "出す。ネットワークに触る経路も、原文を開く経路も無い")
        out["入力を書き換えない"] = (
            "verify が作る写し(採用元を替えた宣言・寄せ方を 1 組外した表)はメモリの中"
            "だけで、入力の CSV には 1 文字も書かない")
        return out

    def judgement_bytes(self) -> bytes:
        """判定部分 = 問いごとの 7 値。時刻・絶対パス・ホスト名は入れない。"""
        self._guard()
        lines = ["\t".join(["件", str(self.report.cells), str(self.report.bridges),
                            str(self.report.takes), str(self.report.questions)])]
        lines.extend(j.line() for j in self.judged)
        return ("\n".join(lines) + "\n").encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.judgement_bytes()).hexdigest()

    def read_condition(self) -> dict[str, str]:
        return {SCOPE_KEYS[0]: self.extracts.path, SCOPE_KEYS[1]: self.bridges.path,
                SCOPE_KEYS[2]: self.takes.path, SCOPE_KEYS[3]: self.questions.path}

    def _guard(self) -> None:
        if not self.report.ok:
            raise RuntimeError("止まっているので数えた問いは無い。"
                               "report.pending の理由コードを見る")


def overlap_check(extracts: Extracts, bridges: Bridges, takes: Takes,
                  questions: Questions) -> Tally:
    """問い 1 件ごとに 7 値を付ける。

    4 枚のどれかが 1 行でも壊れていたら 1 件も数えない(7 値は全て 0)。問いは 1 件ずつ
    判定するので、1 件が「同じ年度」で止まってもほかの問いは判定を続ける。
    """
    pending = (list(extracts.pending) + list(bridges.pending)
               + list(takes.pending) + list(questions.pending))
    for t in takes.ordered:
        pending.extend(t.issues(extracts.docs))
    for q in questions.ordered:
        if takes.of(q.item) is None:
            pending.append(Pending(STOP_REASONS[8],
                                   f"問いの一覧 行 {q.number}: {q.item}"))
    report = Report(not pending, tuple(pending), len(extracts.items),
                    len(bridges.items), len(takes.items), len(questions.items))
    if pending:                     # 1 件も数えずに止まる
        return Tally(report=report, judged=(), extracts=extracts, bridges=bridges,
                     takes=takes, questions=questions)
    judged = tuple(judge(q, extracts, bridges, takes) for q in questions.ordered)
    return Tally(report=report, judged=judged, extracts=extracts, bridges=bridges,
                 takes=takes, questions=questions)


# ------------------------------------------------------------ verify


def take_probe(extracts: Extracts, bridges: Bridges, takes: Takes,
               questions: Questions, first: Tally) -> dict[str, object]:
    """「採用元が同じ欄」の行 1 件を、採用元を去年の変更後に替えて数え直す。

    いつも成り立つはずのこと: 採用元を今年の変更前から去年の変更後に替えると、**採用元が
    同じ欄が 1 減って一致が 1 増える**(件数が 1 対 1 で移る)。ほかの年度ペアの件数は動かない。
    """
    rows = [j for j in first.judged if j.result == RESULTS[4]]
    out_rows: list[dict[str, object]] = []
    ok = bool(rows)
    before = first.seven()
    kept = {row["年度ペア"]: row["7 値"] for row in first.by_pair()}
    for j in rows:
        doc_a = extracts.doc_of_year(j.question.year_a)
        after = overlap_check(extracts, bridges,
                              takes.restated(j.question.item, doc_a or "", ATO),
                              questions)
        now = after.seven()
        same_pairs = {row["年度ペア"]: row["7 値"] for row in after.by_pair()}
        moved = [pair for pair in kept if same_pairs.get(pair) != kept[pair]]
        fits = (after.report.ok
                and now[RESULTS[4]] == before[RESULTS[4]] - 1
                and now[RESULTS[0]] == before[RESULTS[0]] + 1
                and all(now[r] == before[r] for r in RESULTS
                        if r not in (RESULTS[0], RESULTS[4]))
                and moved == [j.question.pair]
                and after.denominator == first.denominator)
        ok = ok and fits
        out_rows.append({"替えた項目名": j.question.item,
                         "年度ペア": j.question.pair,
                         "替えた先の採用元": f"{doc_a} / {ATO}",
                         "採用元が同じ欄": f"{before[RESULTS[4]]} → {now[RESULTS[4]]}",
                         "一致": f"{before[RESULTS[0]]} → {now[RESULTS[0]]}",
                         "動いた年度ペア": "|".join(moved), "合うか": fits})
    return {"書き換えた欄": "行 1 件の採用元(写しはメモリの中だけ)",
            "分母(重なり候補の数)": first.denominator, "行ごと": out_rows, "合うか": ok,
            "読み": ("採用元を経路 B から経路 A に替えると、件数は 1 対 1 で移る。"
                     "同じ欄を検算の相手にしていたことが、ここで数として出る")}


def bridge_probe(extracts: Extracts, bridges: Bridges, takes: Takes,
                 questions: Questions, first: Tally) -> dict[str, object]:
    """寄せ方の表から 1 組を外して数え直す(その項目を 1 件だけ使っている問いで試す)。

    いつも成り立つはずのこと: **寄せ方が無いが 1 増えた分だけ一致が 1 減り**、ほかの年度
    ペアの件数は動かない(項目名を自動で寄せる経路が無いことの実測)。
    """
    used: dict[str, int] = {}
    for j in first.judged:
        used[j.question.item] = used.get(j.question.item, 0) + 1
    rows = [j for j in first.judged
            if j.result == RESULTS[0] and used[j.question.item] == 1]
    out_rows: list[dict[str, object]] = []
    ok = bool(rows)
    before = first.seven()
    kept = {row["年度ペア"]: row["7 値"] for row in first.by_pair()}
    for j in rows:
        after = overlap_check(extracts, bridges.without(j.question.item), takes,
                              questions)
        now = after.seven()
        same_pairs = {row["年度ペア"]: row["7 値"] for row in after.by_pair()}
        moved = [pair for pair in kept if same_pairs.get(pair) != kept[pair]]
        fits = (after.report.ok
                and now[RESULTS[3]] == before[RESULTS[3]] + 1
                and now[RESULTS[0]] == before[RESULTS[0]] - 1
                and all(now[r] == before[r] for r in RESULTS
                        if r not in (RESULTS[0], RESULTS[3]))
                and moved == [j.question.pair])
        ok = ok and fits
        out_rows.append({"外した寄せ方": j.question.item,
                         "年度ペア": j.question.pair,
                         "寄せ方が無い": f"{before[RESULTS[3]]} → {now[RESULTS[3]]}",
                         "一致": f"{before[RESULTS[0]]} → {now[RESULTS[0]]}",
                         "動いた年度ペア": "|".join(moved), "合うか": fits})
    return {"書き換えた欄": "寄せ方の表 1 組(写しはメモリの中だけ)",
            "分母(重なり候補の数)": first.denominator, "行ごと": out_rows, "合うか": ok,
            "読み": ("寄せ方の宣言を外すと、その項目は比べずに「寄せ方が無い」へ移る。"
                     "同じ名前でも寄せたことを宣言させているので、代わりに寄せる経路が無い")}


def verify(extracts: Extracts, bridges: Bridges, takes: Takes,
           questions: Questions) -> dict[str, object]:
    """2 回読んで sha256 を比べ、4 枚の行順を入れ替えても同じかを見て、件数を検算する。
    さらに、採用元を替えた写しと、寄せ方を 1 組外した写しを読んで差分を出す。"""
    first = overlap_check(extracts, bridges, takes, questions)
    if not first.report.ok:
        return {"ok": False, "stage": "止まった(数えた問いは返さない)", **first.counts(),
                "pending": [p.as_dict() for p in first.report.pending]}
    if not questions.swap:
        raise ReadError("問いの一覧に入れ替え方(swap)が無いので verify は走らせない")
    second = overlap_check(extracts, bridges, takes, questions)
    how = questions.swap
    third = overlap_check(extracts.swapped(how), bridges.swapped(how),
                          takes.swapped(how), questions.swapped(how))
    pending: list[Pending] = []
    if first.sha256() != second.sha256():
        pending.append(Pending(STOP_REASONS[11], f"2 回目 {second.sha256()[:12]}"))
    if not (third.report.ok and first.sha256() == third.sha256()):
        pending.append(Pending(STOP_REASONS[12],
                               f"入れ替え方 {how} の 4 枚で {third.sha256()[:12]}"
                               if third.report.ok else
                               f"入れ替え方 {how} の 4 枚では止まった"))
    seven = first.seven()
    halted = first.halted()
    if sum(seven.values()) + halted != first.question_denominator():
        pending.append(Pending(STOP_REASONS[10],
                               f"7 値の合計 {sum(seven.values())} + 止まった {halted}"
                               f" / 問いの数 {first.question_denominator()}"))
    inner = sum(seven[r] for r in GOUI) + seven[RESULTS[5]]
    if inner != first.denominator:
        pending.append(Pending(STOP_REASONS[10],
                               f"5 値 + 単位がそろわない {inner} / 重なり候補 "
                               f"{first.denominator}"))
    by_pair = sum(int(row["問いの数"]) for row in first.by_pair())
    if by_pair != first.question_denominator():
        pending.append(Pending(STOP_REASONS[10],
                               f"年度ペアごとの内訳の合計 {by_pair} / 問いの数 "
                               f"{first.question_denominator()}"))
    if len(first.mismatches()) != seven[RESULTS[1]]:
        pending.append(Pending(STOP_REASONS[10],
                               f"不一致の一覧 {len(first.mismatches())} / 不一致 "
                               f"{seven[RESULTS[1]]}"))
    if len(first.self_checks()) != seven[RESULTS[4]]:
        pending.append(Pending(STOP_REASONS[10],
                               f"採用元が同じ欄の一覧 {len(first.self_checks())} / "
                               f"採用元が同じ欄 {seven[RESULTS[4]]}"))
    out: dict[str, object] = {
        "ok": not pending, "読んだ回数": 2, "入れ替え方": how,
        "sha256": first.sha256(), "2 回目の sha256": second.sha256(),
        "入れ替えた 4 枚の sha256": third.sha256() if third.report.ok else "",
        "件数の検算": {"7 値": seven, "7 値の合計": sum(seven.values()),
                       "止まった問い": halted,
                       "5 値 + 単位がそろわない": inner,
                       "年度ペアごとの内訳の合計": by_pair,
                       "分母(問いの数)": first.question_denominator(),
                       "分母(重なり候補の数)": first.denominator,
                       "分母(別枠の数)": first.aside_denominator()},
        "採用元を去年の変更後に替えた写し":
            take_probe(extracts, bridges, takes, questions, first),
        "寄せ方を 1 組外した写し":
            bridge_probe(extracts, bridges, takes, questions, first),
    }
    for key in ("採用元を去年の変更後に替えた写し", "寄せ方を 1 組外した写し"):
        if not out[key]["合うか"]:        # type: ignore[index]
            pending.append(Pending(STOP_REASONS[10], f"{key} の件数が合わない"))
            out["ok"] = False
    if pending:
        out["観測"] = ("同じ表から違うバイト列が出た、または件数が合わない(平均も多数決も"
                       "しない。どちらの年度が正しいかも決めない)")
        out["pending"] = [p.as_dict() for p in pending]
    return out


# ------------------------------------------------------------ ひな型

TEMPLATE_EXTRACTS = [
    list(CHUUSHUTSU_COLUMNS),
    ["S1", "T1", "K01", ATO, "円", "v11", "合成の資料のメモ(架空)L1"],
    ["S1", "T1", "K02", ATO, "円", "v21", "合成の資料のメモ(架空)L2"],
    ["S2", "T2", "K01", MAE, "円", "v11", "合成の資料のメモ(架空)L3"],
    ["S2", "T2", "K02", MAE, "円", "v29", "合成の資料のメモ(架空)L4"],
]
TEMPLATE_BRIDGES = [
    list(YOSE_COLUMNS),
    ["K01", "K01", "同じ項目名(寄せたことを宣言する)", "合成の寄せ方のメモ(架空)L1"],
    ["K02", "K02", "同じ項目名(寄せたことを宣言する)", "合成の寄せ方のメモ(架空)L2"],
]
TEMPLATE_TAKES = [
    list(SAIYOU_COLUMNS),
    ["G01", "K01", "S1", ATO, "合成の収録のメモ(架空)L1"],
    ["G02", "K02", "S2", MAE, "合成の収録のメモ(架空)L2"],
]
TEMPLATE_QUESTIONS = [
    list(TOI_COLUMNS),
    ["T1", "T2", "K01", "合成の問いのメモ(架空)L1", SWAPS[0]],
    ["T1", "T2", "K02", "合成の問いのメモ(架空)L2", ""],
]


def write_csv(path: Path, rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    return path


def init(dest: str | Path) -> tuple[Path, Path, Path, Path]:
    d = Path(dest)
    return (write_csv(d / "抽出表.csv", TEMPLATE_EXTRACTS),
            write_csv(d / "名前の寄せ方.csv", TEMPLATE_BRIDGES),
            write_csv(d / "採用元の宣言.csv", TEMPLATE_TAKES),
            write_csv(d / "問いの一覧.csv", TEMPLATE_QUESTIONS))


# ------------------------------------------------------------ CLI

def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def build_parser() -> argparse.ArgumentParser:
    """CLI は overlap / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = argparse.ArgumentParser(prog="overlap_check",
                                 description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in SUBCOMMANDS[:3]:
        p = sub.add_parser(name)
        p.add_argument("extracts")
        p.add_argument("bridges")
        p.add_argument("takes")
        p.add_argument("questions")
    sub.add_parser(SUBCOMMANDS[3]).add_argument("dest")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == "init":
        print("書いた: " + " / ".join(str(p) for p in init(a.dest)))
        return 0
    try:
        extracts, bridges = Extracts.load(a.extracts), Bridges.load(a.bridges)
        takes, questions = Takes.load(a.takes), Questions.load(a.questions)
        if a.cmd == "verify":
            out = verify(extracts, bridges, takes, questions)
            _print(out)
            return 0 if out["ok"] else 3
        t = overlap_check(extracts, bridges, takes, questions)
    except ReadError as e:
        print(f"表として読めない: {e}", file=sys.stderr)
        return 2
    if not t.report.ok:
        _print({"ok": False, "stage": "止まった(数えた問いは返さない)", **t.counts(),
                "pending": [p.as_dict() for p in t.report.pending]})
        return 3
    body: dict[str, object] = {"ok": True, **t.counts()}
    if a.cmd == SUBCOMMANDS[0]:
        body["判定ごとの一覧"] = t.listed()
        body["不一致の組"] = t.mismatches()
        body["採用元が同じ欄だけの一覧"] = t.self_checks()
        body["重なりが無い組"] = t.no_overlap()
        body["止まった問い"] = t.stopped_questions()
        body["sha256"] = t.sha256()
        body["読んだ条件"] = t.read_condition()
    _print(body)
    return 0 if t.aside_denominator() == 0 and not t.stopped() else 3


if __name__ == "__main__":
    raise SystemExit(main())
