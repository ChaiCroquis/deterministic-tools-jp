"""cover_stock — 数表ごとの収録範囲を 1 行 1 件の年表にして、計算 1 件に要る行がそろう期間を
数える。行を引かない、期間を切らない、穴を埋めない、数えるだけ。

**同じ基準日を渡しても、引ける年は数表ごとに別で、ある年は料率が引けて別の表は収録の外にある。
しかも引けない理由は「収録を始める前」「収録の中の穴」「まだ公表されていない先」「収録の端が
仮置き」の 4 つに分かれるのに、引いた側に返るのは 1 つの終了コードだけで、どれだったかが残らない。
だから引く前に、数表ごとの収録の端と穴を 1 行 1 件の年表にして、計算 1 件に要る行がそろう期間を
数える。**

この部品は、収録の在庫表・計算のレシピ表・数える年の一覧の 3 枚から、(レシピ × 年)1 つごとに
5 値(**レシピの要る数表が全部そろう / 一部だけそろう / 1 つもそろわない / 止まった / 端が
仮置きの行に依存している**)を付ける。引けない数表は 4 つの理由に分け、止まったものは理由コード
別に数え、分母(レシピ数 × 年の数)と内訳を併記して返す。**行を引かない。数えるだけだ。**

持たせていないものが規律になっている。

  - **年の数え方が宣言されていない行は数えない**(暦年を既定として当てる経路が無い)
  - **年の数え方が違う数表を、換算せずに同じ年として突き合わせない**(換算表も換算の引数も
    持たない。揃えるのは表を書く人)
  - **端が「仮置き」の行は確定として数えない**(別枠の 5 値目に出す)
  - **穴を埋めない・直近の端で代用しない**(表の外の年に対して近くの年の行を当てる経路が無い)
  - **「今日」を使わない**(未来かどうかは入力の年の一覧だけで決める。システム日付を読む経路が
    1 つも無い)
  - **引けない理由を 1 つに潰さない**(4 つの理由コードを別の欄に分けて数える)
  - **行を引かない・版を選ばない・期間を境界で切らない・帯に当てない・空欄の意味を決めない・
    日付の種別を決めない・順位で裁定しない・未来の行を予定に分けない・値を比べない**
  - **足すべき年も、取りに行く先も提案しない**(在庫を数えるところで止める)
  - **網羅率を出さない**(在庫表に書かれた数表の範囲までしか言わない)
  - **件数は丸めず、理由別に分母(レシピ数 × 年の数)と内訳つきで出す**(率を単独で返さない)
  - **入力表を書き換えず、行も在庫も生成しない**
  - **出典の欄が空の行は使わずに止まる**
  - **同じ入力には同じバイト列**(判定部分に時刻・絶対パス・ホスト名を入れない)

入力は 3 つ。収録の在庫表(CSV)、計算のレシピ表(CSV)、数える年の一覧(CSV)。

収録の在庫表の列は 9 つ。1 数表が 1 行。

    table_id          数表 id(空欄は「表として読めない」。2 行あると止まる)
    area              領域
    covered_from      収録開始(ISO の日付)
    covered_to        収録終了(ISO の日付。半開区間で、終わりの日は含まない)
    open_end          終了が開いているか。登録の 2 種(開いている / 閉じている)
    year_kind         年の数え方。登録の 4 種。**空欄のまま持つ**(数える段で止まる)
    edge_confidence   収録開始の端の確度。登録の 2 種(実値 / 仮置き)。**空欄のまま持つ**
    holes             穴の一覧。`開始/終了` を `;` でつなぐ(半開区間)。空欄は穴なし
    source            出典。空欄は止まる

計算のレシピ表の列は 3 つ。1 レシピが 1 行。

    recipe_id   レシピ id(空欄も、同じ id が 2 行あるのも「表として読めない」)
    table_ids   そのレシピに要る数表 id を `|` でつなぐ。**空欄のまま持つ**(数える段で止まる)
    source      出典。空欄は止まる

数える年の一覧の列は 5 つ。1 年が 1 行。

    year_id     年 id(空欄も、同じ id が 2 行あるのも「表として読めない」)
    year        年(4 桁)
    year_kind   その年の数え方。登録の 4 種(空欄も登録外も「表として読めない」)
    source      出典。空欄は止まる
    swap        入れ替え方。verify が 3 枚の行順を入れ替えるときの宣言

使い方:

    python cover_stock.py init ひな型/
    python cover_stock.py check  収録の在庫表.csv 計算のレシピ表.csv 数える年の一覧.csv
    python cover_stock.py stock  収録の在庫表.csv 計算のレシピ表.csv 数える年の一覧.csv
    python cover_stock.py verify 収録の在庫表.csv 計算のレシピ表.csv 数える年の一覧.csv

終了コードは、全部そろった年しか無いときだけ 0、そろわない年か止まった年があるときは 3、表と
して読めなければ 2。
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ZAIKO_COLUMNS = ("table_id", "area", "covered_from", "covered_to", "open_end",
                 "year_kind", "edge_confidence", "holes", "source")
RECIPE_COLUMNS = ("recipe_id", "table_ids", "source")
YEARS_COLUMNS = ("year_id", "year", "year_kind", "source", "swap")

# 年の数え方(登録制)。既定は持たない = 空欄を暦年と読み替える経路が無い
YEAR_KINDS = ("暦年", "年度(3 月開始)", "年度(4 月開始)", "年度(8 月開始)")
START_MONTH = {YEAR_KINDS[0]: 1, YEAR_KINDS[1]: 3, YEAR_KINDS[2]: 4, YEAR_KINDS[3]: 8}
OPEN_ENDS = ("開いている", "閉じている")
EDGES = ("実値", "仮置き")
SWAPS = ("逆順", "両端入れ替え", "1 つずらす")

# (レシピ × 年)1 つに付く 5 値。最後の 1 つが別枠。5 つを混ぜない
RESULTS = ("レシピの要る数表が全部そろう", "一部だけそろう", "1 つもそろわない",
           "止まった", "端が仮置きの行に依存している")
ASIDE = RESULTS[4]

# 数表 1 つが引けない理由(4 つ。1 つの終了コードに潰さない)
UNAVAILABLE = ("収録を始める前", "収録の中の穴", "収録の終わりより後",
               "端が仮置きで確定できない")
AVAILABLE = "そろう"

STOP_REASONS = (
    # 1 件も読まずに止まる(2)
    "出典の欄が空", "数表 id の重複",
    # レシピと年ごとに止まる(11)
    "レシピが参照する数表 id が在庫表に無い", "レシピに数表 id が 1 つも無い",
    "年の数え方が空", "登録されていない年の数え方", "年の数え方が違う",
    "端の確度が空", "収録開始が収録終了より後", "穴が収録範囲の外にある",
    "穴どうしが重なる", "日付が暦として読めない", "開いている終了に日付が入っている",
    # verify が見つける(3)
    "件数の合計が合わない", "2 回目の判定部分が不一致", "行順を入れ替えた表で出力が変わる",
)
TABLE_REASONS = STOP_REASONS[:2]
PAIR_REASONS = STOP_REASONS[2:13]
VERIFY_REASONS = STOP_REASONS[13:]

SUBCOMMANDS = ("stock", "check", "verify", "init")
SCOPE_KEYS = ("読んだ在庫表の絶対パス", "読んだレシピ表の絶対パス", "読んだ年の一覧の絶対パス")

EVENTS = ("収録の開始", "収録の終わり", "穴の開始", "穴の終わり")

DATE = re.compile(r"\A(19|20)[0-9]{2}-[0-9]{2}-[0-9]{2}\Z")
YEAR = re.compile(r"\A(19|20)[0-9]{2}\Z")


class ReadError(Exception):
    """表として読めない(終了コード 2)。読んだ年は 1 件も返さない。"""


@dataclass(frozen=True)
class Pending:
    reason: str
    detail: str = ""

    def as_dict(self) -> dict[str, str]:
        return {"理由コード": self.reason, "どこ": self.detail}


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


def read_date(text: str) -> datetime.date | None:
    """ISO の日付として暦に在る日だけ返す。読めなければ None(理由コードで止める側が決める)。"""
    if not DATE.match(text):
        return None
    try:
        y, m, d = (int(x) for x in text.split("-"))
        return datetime.date(y, m, d)
    except ValueError:
        return None


def year_span(year: int, kind: str) -> tuple[datetime.date, datetime.date]:
    """年と数え方から半開区間を作る。暦年は 1 月開始、年度は宣言された開始月。"""
    month = START_MONTH[kind]
    return datetime.date(year, month, 1), datetime.date(year + 1, month, 1)


def next_boundary(day: datetime.date, kind: str) -> datetime.date:
    """その数え方で、day より後にくる最初の年境界。仮置きの端が揺れる幅を測るのに使う。"""
    month = START_MONTH[kind]
    this = datetime.date(day.year, month, 1)
    return this if this > day else datetime.date(day.year + 1, month, 1)


# ------------------------------------------------------------ 収録の在庫表


@dataclass(frozen=True)
class Sheet:
    """数表 1 つの収録範囲。日付も年の数え方も端の確度も、**読めないまま持つ**。
    直せるものを直さない代わりに、数える段で理由コードにする。"""
    table_id: str
    area: str
    covered_from: str
    covered_to: str
    open_end: str
    year_kind: str
    edge_confidence: str
    holes: str
    source: str
    number: int = 0

    @property
    def open_ended(self) -> bool:
        return self.open_end == OPEN_ENDS[0]

    @property
    def provisional(self) -> bool:
        return self.edge_confidence == EDGES[1]

    def hole_pairs(self) -> tuple[tuple[str, str], ...]:
        out: list[tuple[str, str]] = []
        for part in (p for p in self.holes.split(";") if p.strip()):
            halves = part.split("/")
            if len(halves) != 2:
                raise ReadError(f"在庫表 行 {self.number}: 穴は『開始/終了』で書く({part})")
            out.append((halves[0].strip(), halves[1].strip()))
        return tuple(out)

    def issues(self) -> tuple[Pending, ...]:
        """この数表そのものの不備。要るレシピと年の側で「止まった」になる。"""
        where = f"在庫表 行 {self.number}({self.table_id})"
        out: list[Pending] = []
        if not self.year_kind:
            out.append(Pending(STOP_REASONS[4], where))
        elif self.year_kind not in YEAR_KINDS:
            out.append(Pending(STOP_REASONS[5], f"{where}: {self.year_kind}"))
        if not self.edge_confidence:
            out.append(Pending(STOP_REASONS[7], where))
        start, end = read_date(self.covered_from), read_date(self.covered_to)
        if start is None:
            out.append(Pending(STOP_REASONS[11], f"{where}: 収録開始 {self.covered_from or '空欄'}"))
        if self.open_ended and self.covered_to:
            out.append(Pending(STOP_REASONS[12], f"{where}: 収録終了 {self.covered_to}"))
        elif not self.open_ended:
            if end is None:
                out.append(Pending(STOP_REASONS[11], f"{where}: 収録終了 {self.covered_to or '空欄'}"))
            elif start is not None and start >= end:
                out.append(Pending(STOP_REASONS[8], f"{where}: {self.covered_from} → {self.covered_to}"))
        holes: list[tuple[datetime.date, datetime.date]] = []
        for raw_from, raw_to in self.hole_pairs():
            hf, ht = read_date(raw_from), read_date(raw_to)
            if hf is None or ht is None:
                out.append(Pending(STOP_REASONS[11], f"{where}: 穴 {raw_from}/{raw_to}"))
                continue
            if hf >= ht:
                raise ReadError(f"{where}: 穴の開始が終了以降({raw_from}/{raw_to})")
            if start is not None and (hf < start or (end is not None and ht > end)):
                out.append(Pending(STOP_REASONS[9], f"{where}: 穴 {raw_from}/{raw_to}"))
            holes.append((hf, ht))
        for i, (af, at) in enumerate(holes):
            for bf, bt in holes[i + 1:]:
                if af < bt and bf < at:
                    out.append(Pending(STOP_REASONS[10], f"{where}: {af} と {bf}"))
        return tuple(out)

    def span(self) -> tuple[datetime.date, datetime.date | None,
                            tuple[tuple[datetime.date, datetime.date], ...]]:
        """不備が無いことを確かめた後に呼ぶ。収録開始 / 収録終了(開いていれば None)/ 穴。"""
        start = read_date(self.covered_from)
        if start is None:
            raise RuntimeError("不備のある数表の期間を取りに行った(issues を先に見る)")
        end = None if self.open_ended else read_date(self.covered_to)
        holes = tuple((read_date(a), read_date(b)) for a, b in self.hole_pairs())
        return start, end, holes   # type: ignore[return-value]

    def shifted_start(self) -> "Sheet":
        """収録開始を 1 年後ろへ書き換えた写し(verify が使う。入力の表には書かない)。"""
        start = read_date(self.covered_from)
        if start is None:
            return self
        moved = datetime.date(start.year + 1, start.month, start.day)
        return Sheet(**{**self.__dict__, "covered_from": moved.isoformat()})

    def as_actual(self) -> "Sheet":
        """端の確度を「仮置き」から「実値」に替えた写し(verify が使う)。"""
        if not self.provisional:
            return self
        return Sheet(**{**self.__dict__, "edge_confidence": EDGES[0]})

    def events(self) -> list[dict[str, str]]:
        """1 行 1 件の年表。収録の開始 / 終わり / 穴の開始 / 穴の終わり を別の行にする。"""
        rows = [{"日付": self.covered_from, "領域": self.area, "数表": self.table_id,
                 "出来事": EVENTS[0], "端の確度": self.edge_confidence,
                 "出典": self.source}]
        if not self.open_ended:
            rows.append({"日付": self.covered_to, "領域": self.area,
                         "数表": self.table_id, "出来事": EVENTS[1],
                         "端の確度": EDGES[0], "出典": self.source})
        for raw_from, raw_to in self.hole_pairs():
            for day, event in ((raw_from, EVENTS[2]), (raw_to, EVENTS[3])):
                rows.append({"日付": day, "領域": self.area, "数表": self.table_id,
                             "出来事": event, "端の確度": EDGES[0],
                             "出典": self.source})
        return rows


@dataclass(frozen=True)
class Stock:
    items: tuple[Sheet, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Stock":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"収録の在庫表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Stock":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in ZAIKO_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("収録の在庫表に " + " / ".join(lack) + " の列が無い")
        items: list[Sheet] = []
        pending: list[Pending] = []
        seen: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in ZAIKO_COLUMNS}
            where = f"収録の在庫表 行 {i}"
            if not cell["table_id"]:
                raise ReadError(f"{where}: 数表 id が空欄")
            if not cell["area"]:
                raise ReadError(f"{where}: 領域が空欄({cell['table_id']})")
            if cell["open_end"] not in OPEN_ENDS:
                raise ReadError(f"{where}: 終了が開いているかは {' / '.join(OPEN_ENDS)} "
                                f"の宣言だけ({cell['open_end'] or '空欄'})")
            if cell["edge_confidence"] and cell["edge_confidence"] not in EDGES:
                raise ReadError(f"{where}: 端の確度は {' / '.join(EDGES)} の宣言だけ"
                                f"({cell['edge_confidence']})")
            if cell["table_id"] in seen:
                pending.append(Pending(STOP_REASONS[1], f"{where}: {cell['table_id']}"))
            seen.add(cell["table_id"])
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0], f"{where}({cell['table_id']})"))
            items.append(Sheet(table_id=cell["table_id"], area=cell["area"],
                               covered_from=cell["covered_from"],
                               covered_to=cell["covered_to"],
                               open_end=cell["open_end"], year_kind=cell["year_kind"],
                               edge_confidence=cell["edge_confidence"],
                               holes=cell["holes"], source=cell["source"], number=i))
        if not items:
            raise ReadError("収録の在庫表に行が無い(ヘッダだけ)")
        for s in items:
            s.hole_pairs()      # 穴の形が読めないことは「表として読めない」にする
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    def of(self, table_id: str) -> Sheet | None:
        return next((s for s in self.items if s.table_id == table_id), None)

    @property
    def ordered(self) -> tuple[Sheet, ...]:
        return tuple(sorted(self.items, key=lambda s: s.table_id))

    def swapped(self, how: str) -> "Stock":
        return Stock(items=tuple(swap_rows(list(self.items), how)),
                     pending=self.pending, path=self.path)

    def start_shifted(self, table_id: str) -> "Stock":
        return Stock(items=tuple(s.shifted_start() if s.table_id == table_id else s
                                 for s in self.items),
                     pending=self.pending, path=self.path)

    def edges_as_actual(self) -> "Stock":
        return Stock(items=tuple(s.as_actual() for s in self.items),
                     pending=self.pending, path=self.path)

    def timeline(self) -> tuple[list[dict[str, str]], list[str]]:
        """1 行 1 件の年表(日付の順)と、日付が読めなくて出せなかった数表の id。"""
        rows: list[dict[str, str]] = []
        skipped: list[str] = []
        for s in self.ordered:
            if any(p.reason == STOP_REASONS[11] for p in s.issues()):
                skipped.append(s.table_id)
                continue
            rows.extend(s.events())
        rows.sort(key=lambda r: (r["日付"], r["数表"], r["出来事"]))
        return rows, skipped


# ------------------------------------------------------------ 計算のレシピ表


@dataclass(frozen=True)
class Recipe:
    recipe_id: str
    table_ids: tuple[str, ...]
    source: str
    number: int = 0


@dataclass(frozen=True)
class Recipes:
    items: tuple[Recipe, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Recipes":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"計算のレシピ表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Recipes":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in RECIPE_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("計算のレシピ表に " + " / ".join(lack) + " の列が無い")
        items: list[Recipe] = []
        pending: list[Pending] = []
        seen: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in RECIPE_COLUMNS}
            where = f"計算のレシピ表 行 {i}"
            if not cell["recipe_id"]:
                raise ReadError(f"{where}: レシピ id が空欄")
            if cell["recipe_id"] in seen:
                raise ReadError(f"{where}: レシピ id が 2 行ある({cell['recipe_id']})")
            seen.add(cell["recipe_id"])
            ids = tuple(x.strip() for x in cell["table_ids"].split("|") if x.strip())
            if len(set(ids)) != len(ids):
                raise ReadError(f"{where}: 同じ数表 id を 2 回参照している"
                                f"({cell['table_ids']})")
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0], f"{where}({cell['recipe_id']})"))
            items.append(Recipe(recipe_id=cell["recipe_id"], table_ids=ids,
                                source=cell["source"], number=i))
        if not items:
            raise ReadError("計算のレシピ表に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    @property
    def ordered(self) -> tuple[Recipe, ...]:
        return tuple(sorted(self.items, key=lambda r: r.recipe_id))

    def swapped(self, how: str) -> "Recipes":
        return Recipes(items=tuple(swap_rows(list(self.items), how)),
                       pending=self.pending, path=self.path)


# ------------------------------------------------------------ 数える年の一覧


@dataclass(frozen=True)
class Year:
    year_id: str
    year: int
    year_kind: str
    source: str
    number: int = 0

    def span(self) -> tuple[datetime.date, datetime.date]:
        return year_span(self.year, self.year_kind)

    @property
    def label(self) -> str:
        return f"{self.year}({self.year_kind})"


@dataclass(frozen=True)
class Years:
    items: tuple[Year, ...]
    pending: tuple[Pending, ...] = ()
    swap: str = ""
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Years":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"数える年の一覧が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Years":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in YEARS_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("数える年の一覧に " + " / ".join(lack) + " の列が無い")
        items: list[Year] = []
        pending: list[Pending] = []
        seen: set[str] = set()
        swaps: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in YEARS_COLUMNS}
            where = f"数える年の一覧 行 {i}"
            if not cell["year_id"]:
                raise ReadError(f"{where}: 年 id が空欄")
            if cell["year_id"] in seen:
                raise ReadError(f"{where}: 年 id が 2 行ある({cell['year_id']})")
            seen.add(cell["year_id"])
            if not YEAR.match(cell["year"]):
                raise ReadError(f"{where}: 年は 4 桁で書く({cell['year'] or '空欄'})")
            if cell["year_kind"] not in YEAR_KINDS:
                raise ReadError(f"{where}: 数える年の数え方は "
                                f"{' / '.join(YEAR_KINDS)} の宣言だけ"
                                f"({cell['year_kind'] or '空欄'})")
            if cell["swap"]:
                swaps.add(cell["swap"])
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0], f"{where}({cell['year_id']})"))
            items.append(Year(year_id=cell["year_id"], year=int(cell["year"]),
                              year_kind=cell["year_kind"], source=cell["source"],
                              number=i))
        if not items:
            raise ReadError("数える年の一覧に行が無い(ヘッダだけ)")
        if len(swaps) > 1:
            raise ReadError("入れ替え方の宣言が 2 通りある: " + " / ".join(sorted(swaps)))
        how = swaps.pop() if swaps else ""
        if how and how not in SWAPS:
            raise ReadError(f"登録されていない入れ替え方: {how}")
        return cls(items=tuple(items), pending=tuple(pending), swap=how, path=path)

    @property
    def ordered(self) -> tuple[Year, ...]:
        return tuple(sorted(self.items, key=lambda y: y.year_id))

    def swapped(self, how: str) -> "Years":
        return Years(items=tuple(swap_rows(list(self.items), how)),
                     pending=self.pending, swap=self.swap, path=self.path)


# ------------------------------------------------------------ 数える


def look(sheet: Sheet, year: Year) -> str:
    """数表 1 つが、その年の全部をそろえているか。そろっていなければ 4 つの理由のどれか。

    見る順番は 収録を始める前 → 収録の中の穴 → 収録の終わりより後 → 端が仮置き。
    **穴を埋めない。直近の端で代用しない。システム日付を読まない**(未来かどうかは
    入力の年と在庫表の端だけで決まる)。
    """
    start, end, holes = sheet.span()
    s, e = year.span()
    if s < start:
        return UNAVAILABLE[0]
    for hf, ht in holes:
        if s < ht and hf < e:
            return UNAVAILABLE[1]
    if end is not None and e > end:
        return UNAVAILABLE[2]
    if sheet.provisional and s < next_boundary(start, sheet.year_kind):
        # 端が仮置きなので、その端で決まる最初の年は確定として数えない
        return UNAVAILABLE[3]
    return AVAILABLE


def stops(recipe: Recipe, year: Year, stock: Stock) -> tuple[Pending, ...]:
    """そのレシピとその年を数えられない理由(= 止まった)。1 つに潰さず全部返す。"""
    out: list[Pending] = []
    if not recipe.table_ids:
        out.append(Pending(STOP_REASONS[3], f"レシピ {recipe.recipe_id}"))
    for table_id in recipe.table_ids:
        sheet = stock.of(table_id)
        if sheet is None:
            out.append(Pending(STOP_REASONS[2],
                               f"レシピ {recipe.recipe_id} の {table_id}"))
            continue
        out.extend(sheet.issues())
        if sheet.year_kind in YEAR_KINDS and sheet.year_kind != year.year_kind:
            out.append(Pending(STOP_REASONS[6],
                               f"{table_id} は {sheet.year_kind}、年 {year.year_id} は "
                               f"{year.year_kind}(換算しない)"))
    return tuple(out)


@dataclass(frozen=True)
class Pair:
    recipe_id: str
    year_id: str
    year: str
    year_kind: str
    result: str
    reason: str = ""
    detail: str = ""
    sheets: tuple[tuple[str, str], ...] = ()   # (数表 id, そろうか / 引けない理由)

    @property
    def available(self) -> int:
        return sum(1 for _, v in self.sheets if v == AVAILABLE)

    @property
    def unavailable(self) -> tuple[str, ...]:
        return tuple(v for _, v in self.sheets if v != AVAILABLE)

    def line(self) -> str:
        return "|".join(f"{t}={v}" for t, v in self.sheets)


def judge(recipe: Recipe, year: Year, stock: Stock) -> Pair:
    """(レシピ × 年)1 つに 5 値のどれか 1 つを付ける。5 つを混ぜない。"""
    base = dict(recipe_id=recipe.recipe_id, year_id=year.year_id, year=str(year.year),
                year_kind=year.year_kind)
    pending = stops(recipe, year, stock)
    if pending:
        first = min(pending, key=lambda p: STOP_REASONS.index(p.reason))
        return Pair(**base, result=RESULTS[3], reason=first.reason,
                    detail=" / ".join(f"{p.reason}: {p.detail}" for p in pending))
    sheets = tuple((t, look(stock.of(t), year)) for t in sorted(recipe.table_ids))
    blocked = {v for _, v in sheets if v != AVAILABLE}
    if not blocked:
        result = RESULTS[0]
    elif blocked == {UNAVAILABLE[3]}:
        result = ASIDE                      # 別枠。確定として数えない
    elif any(v == AVAILABLE for _, v in sheets):
        result = RESULTS[1]
    else:
        result = RESULTS[2]
    return Pair(**base, result=result, sheets=sheets,
                detail="|".join(f"{t}={v}" for t, v in sheets))


@dataclass(frozen=True)
class Report:
    ok: bool
    pending: tuple[Pending, ...]
    sheets: int
    recipes: int
    years: int


@dataclass(frozen=True)
class Tally:
    report: Report
    pairs: tuple[Pair, ...]
    stock: Stock
    recipes: Recipes
    years: Years

    def by_result(self, result: str) -> tuple[Pair, ...]:
        return tuple(p for p in self.pairs if p.result == result)

    @property
    def verdict(self) -> str:
        """全体の読み。1 件でも止まれば 止まった、そろわない年があればその名前。"""
        self._guard()
        for r in (RESULTS[3], RESULTS[2], RESULTS[1], ASIDE):
            if self.by_result(r):
                return r
        return RESULTS[0]

    @property
    def denominator(self) -> int:
        return self.report.recipes * self.report.years

    @property
    def sheet_denominator(self) -> int:
        """数表ごとの分母 = レシピが要る数表の延べ数 × 年の数。"""
        return sum(len(r.table_ids) for r in self.recipes.items) * self.report.years

    def by_reason(self) -> dict[str, int]:
        """止まった理由コード別の件数(宣言の順。率は返さない)。"""
        return {code: n for code in PAIR_REASONS
                if (n := sum(1 for p in self.pairs if p.reason == code))}

    def by_unavailable(self) -> dict[str, int]:
        """引けない理由別の件数(数表の延べ数で数える。4 つを 1 つに潰さない)。"""
        return {why: n for why in UNAVAILABLE
                if (n := sum(1 for p in self.pairs for v in p.unavailable if v == why))}

    def available_sheets(self) -> int:
        return sum(p.available for p in self.pairs)

    def counted_sheets(self) -> int:
        return sum(len(p.sheets) for p in self.pairs)

    def counts(self) -> dict[str, object]:
        """件数は丸めず、理由別に分母(レシピ数 × 年の数)と内訳つきで出す。率は単独では返さない。"""
        five = {r: len(self.by_result(r)) for r in RESULTS}
        reason, why = self.by_reason(), self.by_unavailable()
        out: dict[str, object] = {
            "収録の在庫表の行数(数表の数)": self.report.sheets,
            "計算のレシピ表の行数": self.report.recipes,
            "数える年の数": self.report.years,
            "分母(レシピ数 × 年の数)": self.denominator,
            "5 値": five,
            "引けない理由別(数表の延べ数)": why,
            "止まった理由別": reason,
            "読んだか": ("読んだ" if self.pairs else
                         "読んでいない(表が揃う前に止まったので 5 値は全て 0)"),
        }
        out["分母に含めたもの"] = (
            f"レシピ数 {self.report.recipes} × 年の数 {self.report.years}"
            f" = {self.denominator} 件。5 値の内訳は 全部そろう {five[RESULTS[0]]}"
            f" + 一部だけ {five[RESULTS[1]]} + 1 つもそろわない {five[RESULTS[2]]}"
            f" + 止まった {five[RESULTS[3]]} + 端が仮置きの行に依存している"
            f" {five[ASIDE]}。引けない理由別の分母は別で、レシピが要る数表の延べ数 × "
            f"年の数 = {self.sheet_denominator} 件(止まった件の数表は数えない)")
        out["件数の合計の検算"] = (
            f"5 値の合計 {sum(five.values())} / 分母 {self.denominator}"
            f"(止まった理由別の合計 {sum(reason.values())} = 止まった"
            f" {five[RESULTS[3]]}、そろった数表 {self.available_sheets()} + 引けない"
            f"理由別の合計 {sum(why.values())} = 読んだ数表 {self.counted_sheets()})")
        out["網羅率を出さない"] = (
            "言えるのは在庫表に書かれた数表の範囲までで、制度が実際に何年分あるかは判定"
            "しない。網羅率を返す呼び方も option も無い")
        out["年の数え方に既定を当てない"] = (
            "年の数え方が空欄の数表は、暦年を当てずに止まる。空欄のまま持って、数える段で"
            "理由コードにする")
        out["年の数え方を換算しない"] = (
            "年の数え方が違う数表と年は、換算せずに止まる。換算表も換算の引数も無い"
            "(揃えるのは表を書く人)")
        out["穴を埋めない・直近の端で代用しない"] = (
            "収録の中の穴も収録の外も、近くの年の行で埋めない。表の外の年に対して何かを"
            "返す経路が無い")
        out["仮置きの端を確定として数えない"] = (
            "端の確度が「仮置き」の数表は、その端で決まる最初の年を別枠に出す。4 値に"
            "混ぜない")
        out["システム日付を読まない"] = (
            "未来かどうかは入力の年の一覧と在庫表の端だけで決まる。今日を読む経路が 1 つも"
            "無い(同じ入力なら明日も同じバイト列)")
        out["行を引かない・足すべき年も取りに行く先も提案しない"] = (
            "引き当ても、版の選択も、期間の切り分けもしない。どの年まで収録すべきかも、"
            "どこから取ってくるかも出す経路が無い")
        return out

    def table(self) -> list[dict[str, object]]:
        """レシピと年ごとの読み。率の欄は無い。"""
        return [{"レシピ id": p.recipe_id, "年 id": p.year_id, "年": p.year,
                 "年の数え方": p.year_kind, "結果": p.result,
                 "止まった理由": p.reason, "数表ごと": p.detail,
                 "そろった数表": p.available, "要る数表": len(p.sheets)}
                for p in self.pairs]

    def timeline(self) -> list[dict[str, str]]:
        return self.stock.timeline()[0]

    def judgement_bytes(self) -> bytes:
        """判定部分 = 読んだ(レシピ × 年)の表。時刻・絶対パス・ホスト名は入れない。"""
        self._guard()
        lines = ["\t".join(["件", str(self.report.recipes), str(self.report.years),
                            str(self.denominator)])]
        for p in self.pairs:
            lines.append("\t".join([p.recipe_id, p.year_id, p.year, p.year_kind,
                                    p.result, p.reason, p.line()]))
        return ("\n".join(lines) + "\n").encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.judgement_bytes()).hexdigest()

    def read_condition(self) -> dict[str, str]:
        return {SCOPE_KEYS[0]: self.stock.path, SCOPE_KEYS[1]: self.recipes.path,
                SCOPE_KEYS[2]: self.years.path}

    def _guard(self) -> None:
        if not self.report.ok:
            raise RuntimeError("止まっているので読んだ年は無い。"
                               "report.pending の理由コードを見る")


def cover_stock(stock: Stock, recipes: Recipes, years: Years) -> Tally:
    """レシピと年の掛け合わせごとに、要る数表がそろう年かを数える。表が揃う前に止まったら
    1 件も読まない。"""
    pending = tuple(list(stock.pending) + list(recipes.pending) + list(years.pending))
    report = Report(not pending, pending, len(stock.items), len(recipes.items),
                    len(years.items))
    if pending:                     # 1 件も読まずに止まる
        return Tally(report=report, pairs=(), stock=stock, recipes=recipes, years=years)
    pairs = tuple(judge(r, y, stock)
                  for r in recipes.ordered for y in years.ordered)
    return Tally(report=report, pairs=pairs, stock=stock, recipes=recipes, years=years)


# ------------------------------------------------------------ verify


def moves(before: Tally, after: Tally) -> dict[str, int]:
    """同じ(レシピ × 年)の結果がどこへ移ったかを数える(平均も多数決もしない)。"""
    out: dict[str, int] = {}
    for b, a in zip(before.pairs, after.pairs):
        if b.result != a.result:
            out[f"{b.result} → {a.result}"] = out.get(f"{b.result} → {a.result}", 0) + 1
    return dict(sorted(out.items()))


def start_probe(stock: Stock, recipes: Recipes, years: Years,
                first: Tally) -> dict[str, object]:
    """数表 1 つずつ、収録開始を 1 年後ろへ書き換えて、全部そろうがどこへ移るかを数える。

    いつも成り立つはずのこと: 収録開始を後ろへずらすと、**全部そろうへ入ってくる年は 1 件も
    無い**(覆いは広がらない)。移った先の内訳をそのまま出す。
    """
    rows: list[dict[str, object]] = []
    ok = True
    for sheet in stock.ordered:
        shifted = cover_stock(stock.start_shifted(sheet.table_id), recipes, years)
        step = moves(first, shifted)
        into = sum(n for k, n in step.items() if k.endswith(f"→ {RESULTS[0]}"))
        out_of = sum(n for k, n in step.items() if k.startswith(f"{RESULTS[0]} →"))
        drop = (len(first.by_result(RESULTS[0]))
                - len(shifted.by_result(RESULTS[0])))
        fits = into == 0 and out_of == drop
        ok = ok and fits
        rows.append({"数表": sheet.table_id,
                     "書き換えた収録開始": f"{sheet.covered_from} → "
                                            f"{sheet.shifted_start().covered_from}",
                     "全部そろうの減り": drop, "全部そろうから移った先": step,
                     "全部そろうへ入ってきた件数": into, "合うか": fits})
    return {"書き換えた欄": "数表 1 つの収録開始を 1 年後ろへ(写しはメモリの中だけ)",
            "分母(レシピ数 × 年の数)": first.denominator, "数表ごと": rows,
            "合うか": ok,
            "読み": ("収録開始を後ろへずらすと、全部そろうへ入ってくる年は 1 件も無く、"
                     "減った分はそのまま一部だけ / 1 つもそろわない / 別枠 へ移る"
                     "(覆いが勝手に広がらないことの実測)")}


def edge_probe(stock: Stock, recipes: Recipes, years: Years,
               first: Tally) -> dict[str, object]:
    """端の確度を「仮置き」から「実値」に替えた写しを読み、別枠がどこへ移るかを数える。"""
    flipped = cover_stock(stock.edges_as_actual(), recipes, years)
    step = moves(first, flipped)
    to_whole = step.get(f"{ASIDE} → {RESULTS[0]}", 0)
    provisional = [s.table_id for s in stock.ordered if s.provisional]
    return {"書き換えた数表": provisional,
            "書き換えた欄": f"端の確度を {EDGES[1]} から {EDGES[0]} へ",
            "別枠だった件数": len(first.by_result(ASIDE)),
            "移った先": step,
            "全部そろうへ移った件数": to_whole,
            "書き換えた後の別枠": len(flipped.by_result(ASIDE)),
            "分母(レシピ数 × 年の数)": first.denominator,
            "合うか": (len(flipped.by_result(ASIDE)) == 0 and to_whole >= 1
                       if provisional else len(first.by_result(ASIDE)) == 0),
            "読み": ("仮置きの端を実値と読むと、別枠の年が全部そろうへ移る。"
                     "在庫がどれだけ広く見えるかの件数がこれ(分母つき)")}


def verify(stock: Stock, recipes: Recipes, years: Years) -> dict[str, object]:
    """2 回読んで sha256 を比べ、3 枚の行順を入れ替えても同じかを見て、件数を検算する。
    さらに、収録開始を 1 年後ろへずらした写しと、端の確度を実値に替えた写しを読んで差分を出す。"""
    first = cover_stock(stock, recipes, years)
    if not first.report.ok:
        return {"ok": False, "stage": "止まった(読んだ年は返さない)", **first.counts(),
                "pending": [p.as_dict() for p in first.report.pending]}
    if not years.swap:
        raise ReadError("数える年の一覧に入れ替え方(swap)が無いので verify は走らせない")
    second = cover_stock(stock, recipes, years)
    third = cover_stock(stock.swapped(years.swap), recipes.swapped(years.swap),
                        years.swapped(years.swap))
    pending: list[Pending] = []
    if first.sha256() != second.sha256():
        pending.append(Pending(STOP_REASONS[14], f"2 回目 {second.sha256()[:12]}"))
    if not (third.report.ok and first.sha256() == third.sha256()):
        pending.append(Pending(STOP_REASONS[15],
                               f"入れ替え方 {years.swap} の 3 枚で "
                               f"{third.sha256()[:12]}" if third.report.ok else
                               f"入れ替え方 {years.swap} の 3 枚では止まった"))
    five = {r: len(first.by_result(r)) for r in RESULTS}
    reason, why = first.by_reason(), first.by_unavailable()
    if sum(five.values()) != first.denominator:
        pending.append(Pending(STOP_REASONS[13], f"5 値の合計 {sum(five.values())}"
                                                 f" / 分母 {first.denominator}"))
    if sum(reason.values()) != five[RESULTS[3]]:
        pending.append(Pending(STOP_REASONS[13],
                               f"止まった理由別の合計 {sum(reason.values())}"
                               f" / 止まった {five[RESULTS[3]]}"))
    if first.available_sheets() + sum(why.values()) != first.counted_sheets():
        pending.append(Pending(STOP_REASONS[13],
                               f"そろった数表 {first.available_sheets()} + 引けない理由別"
                               f"の合計 {sum(why.values())} / 読んだ数表 "
                               f"{first.counted_sheets()}"))
    out: dict[str, object] = {
        "ok": not pending, "読んだ結果": first.verdict, "読んだ回数": 2,
        "入れ替え方": years.swap, "sha256": first.sha256(),
        "2 回目の sha256": second.sha256(),
        "入れ替えた 3 枚の sha256": third.sha256() if third.report.ok else "",
        "件数の検算": {"5 値": five, "5 値の合計": sum(five.values()),
                       "止まった理由別の合計": sum(reason.values()),
                       "そろった数表": first.available_sheets(),
                       "引けない理由別の合計": sum(why.values()),
                       "読んだ数表": first.counted_sheets(),
                       "分母(レシピ数 × 年の数)": first.denominator,
                       "数表ごとの分母": first.sheet_denominator},
        "収録開始を 1 年後ろへずらした写し": start_probe(stock, recipes, years, first),
        "端の確度を実値に替えた写し": edge_probe(stock, recipes, years, first),
    }
    for key in ("収録開始を 1 年後ろへずらした写し", "端の確度を実値に替えた写し"):
        if not out[key]["合うか"]:        # type: ignore[index]
            pending.append(Pending(STOP_REASONS[13], f"{key} の件数が合わない"))
            out["ok"] = False
    if pending:
        out["観測"] = ("同じ表から違うバイト列が出た、または件数が合わない(平均も多数決も"
                       "しない。どちらが正しいかも決めない)")
        out["pending"] = [p.as_dict() for p in pending]
    return out


# ------------------------------------------------------------ ひな型

TEMPLATE_STOCK = [
    list(ZAIKO_COLUMNS),
    ["T01", "合成の領域甲(架空)", "2020-01-01", "", OPEN_ENDS[0], YEAR_KINDS[0],
     EDGES[0], "", "合成の在庫メモ(架空)L1"],
    ["T02", "合成の領域乙(架空)", "2024-04-01", "", OPEN_ENDS[0], YEAR_KINDS[2],
     EDGES[1], "", "合成の在庫メモ(架空)L2"],
]
TEMPLATE_RECIPES = [
    list(RECIPE_COLUMNS),
    ["R01", "T01", "合成のレシピメモ(架空)L1"],
    ["R02", "T02", "合成のレシピメモ(架空)L2"],
]
TEMPLATE_YEARS = [
    list(YEARS_COLUMNS),
    ["Y01", "2024", YEAR_KINDS[0], "合成の年メモ(架空)L1", SWAPS[0]],
    ["Y02", "2025", YEAR_KINDS[2], "合成の年メモ(架空)L2", ""],
]


def write_csv(path: Path, rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    return path


def init(dest: str | Path) -> tuple[Path, Path, Path]:
    d = Path(dest)
    return (write_csv(d / "収録の在庫表.csv", TEMPLATE_STOCK),
            write_csv(d / "計算のレシピ表.csv", TEMPLATE_RECIPES),
            write_csv(d / "数える年の一覧.csv", TEMPLATE_YEARS))


# ------------------------------------------------------------ CLI

def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def build_parser() -> argparse.ArgumentParser:
    """CLI は stock / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = argparse.ArgumentParser(prog="cover_stock",
                                 description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in SUBCOMMANDS[:3]:
        p = sub.add_parser(name)
        p.add_argument("stock")
        p.add_argument("recipes")
        p.add_argument("years")
    sub.add_parser(SUBCOMMANDS[3]).add_argument("dest")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == "init":
        print("書いた: " + " / ".join(str(p) for p in init(a.dest)))
        return 0
    try:
        stock, recipes = Stock.load(a.stock), Recipes.load(a.recipes)
        years = Years.load(a.years)
        if a.cmd == "verify":
            out = verify(stock, recipes, years)
            _print(out)
            return 0 if out["ok"] else 3
        t = cover_stock(stock, recipes, years)
    except ReadError as e:
        print(f"表として読めない: {e}", file=sys.stderr)
        return 2
    if not t.report.ok:
        _print({"ok": False, "stage": "止まった(読んだ年は返さない)", **t.counts(),
                "pending": [p.as_dict() for p in t.report.pending]})
        return 3
    body: dict[str, object] = {"ok": True, "読んだ結果": t.verdict, **t.counts()}
    if a.cmd == SUBCOMMANDS[0]:
        body["レシピと年ごと"] = t.table()
        timeline, skipped = stock.timeline()
        body["在庫の年表(1 行 1 件)"] = timeline
        body["年表に出せなかった数表"] = skipped
        body["sha256"] = t.sha256()
        body["読んだ条件"] = t.read_condition()
    _print(body)
    return 0 if len(t.by_result(RESULTS[0])) == t.denominator else 3


if __name__ == "__main__":
    raise SystemExit(main())
