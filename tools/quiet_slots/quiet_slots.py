"""quiet_slots — 引く呼び出しの欄を「空にしたときの出口」で 4 つに分け、空でも止まらない欄を数える。

**「AI は推論せず、これを呼ぶ」と宣言しても、推論がやむのは数表の値の側だけで、呼ぶときに
どの欄を埋めるかの判断は宣言の外に残る。しかも残った欄は一様でなく、空なら例外で止まる欄と、
空でも宣言どおり通って広い行に当たる欄と、既定がどこにも宣言されていない欄が混ざっている。**

この部品は、問いの宣言表・欄の登録表・行の在り方の表・出口の登録表(4 枚)から、
問い × 欄 の組ごとに 4 値(**空にできない / 空でよいと宣言されている / 埋めるのは人か LLM だと
宣言されている / どちらの宣言も無い**)のどれか 1 つを付け、別枠 3(**同じ欄に 2 通りの宣言が
在る / 欄名が登録表に無い / 出典が空**)と、問いが手元に在ると宣言した欄を分けて数える。
`空でよいと宣言されている` 組には、行の在り方の表から **`1 行に決まる` / `2 行以上が当たる`
(行数つき)/ `行数の宣言が無い`** の印を付ける。

持たせていないものが規律になっている。

  - **CLI を呼ばない・引かない・走らせない**(外部プロセスを起こす経路が無い)
  - **欄に値を入れない**(入力は欄名だけで、値を持つ列が 1 つも無い)
  - **空白を推測で埋めない**(`宣言なし` を `できる` 側へ寄せる経路が無い。宣言が無い欄は
    `どちらの宣言も無い` のまま出る)
  - **トークン数・文字数・削減量を出さない**(数え方が手元に無い)
  - **どの問いを道具に回すべきか決めない**、**省略の正否を決めない**
  - **日付の種別の台帳を作らない**(欄名の種別そのものの台帳は別の部品の領分)
  - **入力を下へ辿らない**(見るのは 1 段目だけで、欄の中身がまた式かどうかは追わない)
  - **返り値の側に残る一手を見ない**(ここで数えるのは呼ぶ前の欄だけ)
  - **行の中身の値を読まない**(入るのは行数と記号と出典だけ)
  - **時計を読まない**、**入力を書き換えない**、**float を使わない**、判定部分に時刻・
    絶対パス・ホスト名を入れない

入力は 4 枚。**どの行にも出典の欄が要る。**

問いの宣言表(CSV)の列は 5。**1 つの問いが 1 行。**

    ask_id   問い id(同じ id が 2 行あると止まる)
    command  呼ぶコマンド名
    target   求める rule or 式の id(求めないなら `—`)
    slots    **手元に在る欄名の一覧**(`|` 区切り。空欄 = 0 本)。**値は書かない、名前だけ**
    source   出典(ファイル名 + 行番号)。空欄のときは、その問いの組が別枠「出典が空」へ入る

欄の登録表(CSV)の列は 6。**同じ欄名を 2 行書いてよい**(2 通りの宣言が在ることを写すため)。

    slot       欄名
    kind       欄の種別記号(基準日 / 選択の次元 / 知識時点 / 式の入力 / 判断の結果)
    emptiable  **空にできるか記号**(できない / できる / 宣言なし)
    filler     **誰が埋めてよいか記号**(表から引く / 人 / 人かLLM / 宣言なし)
    exit       空にできない欄が止まる出口記号(ほかは `—`)。**出口の登録表に在る記号だけ**
    source     宣言の出典。空欄は止まる

行の在り方の表(CSV)の列は 4。**その次元を空にしたとき当たる行数だけで、行の中身は入らない。**

    target     rule or 式の id
    dimension  次元名(= 欄名)
    rows       **その次元を空にしたとき当たる行数**(1 以上の整数)
    source     出典。空欄は止まる

出口の登録表(CSV)の列は 3。**「止まる」の定義はここに在る。**

    exit    出口記号(例外 / 終了コード2 / 終了コード3 / 通る)
    stops   止まるか記号(止まる / 止まらない)
    source  宣言の出典。空欄は止まる

使い方:

    python quiet_slots.py init ひな型/
    python quiet_slots.py check 問い.csv 欄.csv 行の在り方.csv 出口.csv
    python quiet_slots.py cells 問い.csv 欄.csv 行の在り方.csv 出口.csv
    python quiet_slots.py verify 問い.csv 欄.csv 行の在り方.csv 出口.csv

終了コードは、空でも止まらない欄と別枠と止まった行とどの問いも求めていない宣言が 0 件のときだけ
0、在れば 3、表として読めなければ 2。**0 は「呼び出しが正しい」ではなく「全ての組が、空に
できないか手元に在ると宣言されている」の意味で、省略の正否はこの部品の出力に出ない。**
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ASK_COLUMNS = ("ask_id", "command", "target", "slots", "source")
SLOT_COLUMNS = ("slot", "kind", "emptiable", "filler", "exit", "source")
SHAPE_COLUMNS = ("target", "dimension", "rows", "source")
EXIT_COLUMNS = ("exit", "stops", "source")

# 欄の種別(**この 5 つの外に種別を作る経路が無い**)
KINDS = ("基準日", "選択の次元", "知識時点", "式の入力", "判断の結果")
# 空にできるか(**3 番目が「宣言が無い」で、ほかへ寄せる経路が無い**)
EMPTIABLE = ("できない", "できる", "宣言なし")
# 誰が埋めてよいか(**3 番目が「人か LLM が起票してよい」と宣言された欄**)
FILLERS = ("表から引く", "人", "人かLLM", "宣言なし")
# 出口記号(**止まるかの定義は出口の登録表の側に在る**)
EXITS = ("例外", "終了コード2", "終了コード3", "通る")
STOPS = ("止まる", "止まらない")

NO_MARK = "—"           # 次元が無い / 出口を宣言しない欄
NOT_REGISTERED = "(登録に無い)"

# 問い × 欄 の組 1 つに付く 4 値。**この 4 つの外に値を作る経路が無い。**
YOTSU = (
    "空にできない",
    "空でよいと宣言されている",
    "埋めるのは人か LLM だと宣言されている",
    "どちらの宣言も無い",
)
# 4 値の外へ出す別枠 3。**4 値より先に当たる。**
BETSUWAKU = (
    "同じ欄に 2 通りの宣言が在る",
    "欄名が登録表に無い",
    "出典が空",
)
# 問いが手元に在ると宣言した欄(= 空にしない欄)
AT_HAND = "手元に在ると宣言されている"
# `空でよいと宣言されている` 組に付く印(**行数を数えるところまでで、引かない**)
MARKS = ("1 行に決まる", "2 行以上が当たる", "行数の宣言が無い")

SWAPS = ("逆順", "両端入れ替え", "1 つずらす")

STOP_REASONS = (
    # 表の側。1 組も数えずに止まる(7)
    "宣言の出典が空",
    "問い id の重複",
    "同じ問いに同じ欄名が 2 回",
    "空にできない欄の出口記号が出口の登録表に無い",
    "空にできない欄の出口が止まらないと宣言されている",
    "同じ rule と次元の組が行の在り方の表に 2 行ある",
    "同じ出口記号が出口の登録表で止まるかが食い違う",
    # verify が見つける(3)
    "件数の合計が合わない", "2 回目の判定部分が不一致", "行順を入れ替えた表で出力が変わる",
)
TABLE_REASONS = STOP_REASONS[:7]
VERIFY_REASONS = STOP_REASONS[7:]

SUBCOMMANDS = ("cells", "check", "verify", "init")
SCOPE_KEYS = ("読んだ問いの宣言表の絶対パス", "読んだ欄の登録表の絶対パス",
              "読んだ行の在り方の表の絶対パス", "読んだ出口の登録表の絶対パス")

NG_ID = set(" \t,|;")


class ReadError(Exception):
    """表として読めない(終了コード 2)。問い × 欄 の組は 1 つも数えない。"""


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


# ------------------------------------------------------------ 出口の登録表


@dataclass(frozen=True)
class Exit:
    """出口 1 つ。**止まるかは人が書いた宣言で、記号の綴りから当てる経路が無い。**"""
    exit: str
    stops: str
    source: str


@dataclass(frozen=True)
class Exits:
    items: tuple[Exit, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Exits":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"出口の登録表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Exits":
        items: list[Exit] = []
        pending: list[Pending] = []
        for i, cell in _rows_of(text, EXIT_COLUMNS, "出口の登録表"):
            where = f"出口の登録表 行 {i}"
            if cell["exit"] not in EXITS:
                raise ReadError(f"{where}: 出口記号が登録の 4 つでない"
                                f"({cell['exit'] or '空欄'})")
            if cell["stops"] not in STOPS:
                raise ReadError(f"{where}: 止まるか記号が登録の 2 つでない"
                                f"({cell['stops'] or '空欄'})")
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0], f"{where}: {cell['exit']}"))
            items.append(Exit(**cell))
        if not items:
            raise ReadError("出口の登録表に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    @property
    def ordered(self) -> tuple[Exit, ...]:
        return tuple(sorted(self.items, key=lambda e: EXITS.index(e.exit)))

    def of(self, sym: str) -> Exit | None:
        """**登録に無い出口記号には何も当てない**(None を返す = 止まる)。"""
        return next((e for e in self.items if e.exit == sym), None)

    def issues(self) -> list[Pending]:
        """同じ出口記号が 2 行あって止まるかが食い違う。"""
        out: list[Pending] = []
        for sym in EXITS:
            here = {e.stops for e in self.items if e.exit == sym}
            if len(here) > 1:
                out.append(Pending(STOP_REASONS[6],
                                   f"{sym}: " + " / ".join(sorted(here))))
        return out

    def swapped(self, how: str) -> "Exits":
        return Exits(items=tuple(swap_rows(list(self.items), how)),
                     pending=self.pending, path=self.path)


# ------------------------------------------------------------ 欄の登録表


@dataclass(frozen=True)
class SlotDecl:
    """欄 1 つについての宣言 1 本。**同じ欄名に 2 本あってよい**(食い違いを写すため)。"""
    slot: str
    kind: str
    emptiable: str
    filler: str
    exit: str
    source: str


@dataclass(frozen=True)
class Slots:
    items: tuple[SlotDecl, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Slots":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"欄の登録表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Slots":
        items: list[SlotDecl] = []
        pending: list[Pending] = []
        for i, cell in _rows_of(text, SLOT_COLUMNS, "欄の登録表"):
            where = f"欄の登録表 行 {i}"
            if bad_id(cell["slot"]):
                raise ReadError(f"{where}: 欄名が空欄か、区切り文字を含む"
                                f"({cell['slot'] or '空欄'})")
            for key, what, allowed in (("kind", "欄の種別記号", KINDS),
                                       ("emptiable", "空にできるか記号", EMPTIABLE),
                                       ("filler", "誰が埋めてよいか記号", FILLERS)):
                if cell[key] not in allowed:
                    raise ReadError(f"{where}: {what}が登録の {len(allowed)} つでない"
                                    f"({cell[key] or '空欄'})")
            if cell["exit"] not in EXITS + (NO_MARK,):
                raise ReadError(f"{where}: 出口記号が登録の 4 つでも {NO_MARK} でもない"
                                f"({cell['exit'] or '空欄'})")
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0], f"{where}: {cell['slot']}"))
            items.append(SlotDecl(**cell))
        if not items:
            raise ReadError("欄の登録表に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted({s.slot for s in self.items}))

    def decls(self, slot: str) -> tuple[SlotDecl, ...]:
        return tuple(sorted((s for s in self.items if s.slot == slot),
                            key=lambda s: (s.emptiable, s.filler, s.exit, s.source)))

    def conflicting(self, slot: str) -> bool:
        """**同じ欄に 2 通りの宣言が在るか**(空にできるか / 誰が埋めてよいかの食い違い)。"""
        here = self.decls(slot)
        return len({(s.emptiable, s.filler) for s in here}) > 1

    def one(self, slot: str) -> SlotDecl | None:
        """食い違いが無いときの 1 本(**食い違っていれば別枠へ行くので使わない**)。"""
        here = self.decls(slot)
        return here[0] if here else None

    def kind_of(self, slot: str) -> str:
        kinds = sorted({s.kind for s in self.decls(slot)})
        return "/".join(kinds) if kinds else NOT_REGISTERED

    def issues(self, exits: Exits) -> list[Pending]:
        """空にできないと宣言した欄の出口が、登録表で「止まる」と結べるか。"""
        out: list[Pending] = []
        for s in sorted(self.items, key=lambda x: (x.slot, x.source)):
            if s.emptiable != EMPTIABLE[0]:
                continue
            hit = exits.of(s.exit) if s.exit != NO_MARK else None
            if hit is None:
                out.append(Pending(STOP_REASONS[3], f"{s.slot}: {s.exit or '空欄'}"))
            elif hit.stops != STOPS[0]:
                out.append(Pending(STOP_REASONS[4], f"{s.slot}: {s.exit}"))
        return out

    def rewritten(self, slot: str, emptiable: str) -> "Slots":
        """空にできるかの宣言を 1 つ替えた写し(**メモリの中だけ**)。"""
        if emptiable not in EMPTIABLE:
            raise ReadError(f"登録されていない空にできるかの宣言: {emptiable or '空欄'}")
        return Slots(items=tuple(
            SlotDecl(s.slot, s.kind, emptiable, s.filler, s.exit, s.source)
            if s.slot == slot else s for s in self.items),
            pending=self.pending, path=self.path)

    def swapped(self, how: str) -> "Slots":
        return Slots(items=tuple(swap_rows(list(self.items), how)),
                     pending=self.pending, path=self.path)


# ------------------------------------------------------------ 行の在り方の表


@dataclass(frozen=True)
class Shape:
    """その次元を空にしたとき当たる行数 1 件。**行の中身は入らない。**"""
    target: str
    dimension: str
    rows: int
    source: str


@dataclass(frozen=True)
class Shapes:
    items: tuple[Shape, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Shapes":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"行の在り方の表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Shapes":
        items: list[Shape] = []
        pending: list[Pending] = []
        for i, cell in _rows_of(text, SHAPE_COLUMNS, "行の在り方の表"):
            where = f"行の在り方の表 行 {i}"
            for key, what in (("target", "rule or 式の id"), ("dimension", "次元名")):
                if bad_id(cell[key]):
                    raise ReadError(f"{where}: {what}が空欄か、区切り文字を含む"
                                    f"({cell[key] or '空欄'})")
            rows = whole(cell["rows"], "当たる行数", where, least=1)
            if not cell["source"]:
                pending.append(Pending(
                    STOP_REASONS[0],
                    f"{where}: {cell['target']} / {cell['dimension']}"))
            items.append(Shape(target=cell["target"], dimension=cell["dimension"],
                               rows=rows, source=cell["source"]))
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    @property
    def ordered(self) -> tuple[Shape, ...]:
        return tuple(sorted(self.items, key=lambda s: (s.target, s.dimension)))

    @property
    def dimensions(self) -> tuple[str, ...]:
        return tuple(sorted({s.dimension for s in self.items}))

    def of(self, target: str, dimension: str) -> Shape | None:
        """**宣言された分だけを写す。無ければ None(= 行数の宣言が無い)。**"""
        return next((s for s in self.items
                     if s.target == target and s.dimension == dimension), None)

    def issues(self) -> list[Pending]:
        out: list[Pending] = []
        seen: set[tuple[str, str]] = set()
        for s in self.ordered:
            key = (s.target, s.dimension)
            if key in seen:
                out.append(Pending(STOP_REASONS[5], " / ".join(key)))
            seen.add(key)
        return out

    def bumped(self, target: str, dimension: str, rows: int) -> "Shapes":
        """当たる行数を替えた写し(**メモリの中だけ**)。"""
        if rows < 1:
            raise ReadError(f"当たる行数が 1 以上でない({rows})")
        return Shapes(items=tuple(
            Shape(s.target, s.dimension, rows, s.source)
            if (s.target, s.dimension) == (target, dimension) else s
            for s in self.items), pending=self.pending, path=self.path)

    def swapped(self, how: str) -> "Shapes":
        return Shapes(items=tuple(swap_rows(list(self.items), how)),
                      pending=self.pending, path=self.path)


# ------------------------------------------------------------ 問いの宣言表


@dataclass(frozen=True)
class Ask:
    """問い 1 つ。**手元に在る欄の名前だけを持ち、値を持つ列が無い。**"""
    ask_id: str
    command: str
    target: str
    slots: tuple[str, ...]
    source: str

    @property
    def at_hand(self) -> int:
        return len(self.slots)


@dataclass(frozen=True)
class Asks:
    items: tuple[Ask, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Asks":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"問いの宣言表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Asks":
        items: list[Ask] = []
        pending: list[Pending] = []
        seen: set[str] = set()
        for i, cell in _rows_of(text, ASK_COLUMNS, "問いの宣言表"):
            where = f"問いの宣言表 行 {i}"
            if bad_id(cell["ask_id"]):
                raise ReadError(f"{where}: 問い id が空欄か、区切り文字を含む"
                                f"({cell['ask_id'] or '空欄'})")
            if not cell["command"]:
                raise ReadError(f"{where}: 呼ぶコマンド名が空欄")
            if cell["target"] != NO_MARK and bad_id(cell["target"]):
                raise ReadError(f"{where}: 求める rule or 式の id が空欄か、"
                                f"区切り文字を含む(求めないなら {NO_MARK})")
            names = tuple(x.strip() for x in cell["slots"].split("|") if x.strip())
            for n in names:
                if bad_id(n):
                    raise ReadError(f"{where}: 欄名が読めない({n})")
            if cell["ask_id"] in seen:
                pending.append(Pending(STOP_REASONS[1], f"{where}: {cell['ask_id']}"))
            seen.add(cell["ask_id"])
            if len(set(names)) != len(names):
                dup = sorted({n for n in names if names.count(n) > 1})
                pending.append(Pending(STOP_REASONS[2],
                                       f"{where}: " + " / ".join(dup)))
            items.append(Ask(ask_id=cell["ask_id"], command=cell["command"],
                             target=cell["target"], slots=names,
                             source=cell["source"]))
        if not items:
            raise ReadError("問いの宣言表に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    @property
    def ordered(self) -> tuple[Ask, ...]:
        return tuple(sorted(self.items, key=lambda a: a.ask_id))

    @property
    def named_slots(self) -> tuple[str, ...]:
        return tuple(sorted({n for a in self.items for n in a.slots}))

    @property
    def targets(self) -> tuple[str, ...]:
        return tuple(sorted({a.target for a in self.items if a.target != NO_MARK}))

    def swapped(self, how: str) -> "Asks":
        return Asks(items=tuple(swap_rows(list(self.items), how)),
                    pending=self.pending, path=self.path)


# ------------------------------------------------------------ 組を作る


@dataclass(frozen=True)
class Cell:
    """問い × 欄 の組 1 つ。**値を入れず、正しい埋め方も推奨も持たない。**"""
    ask: Ask
    slot: str
    value: str
    kind: str
    mark: str = ""
    rows: int = 0
    sources: tuple[str, ...] = ()

    @property
    def name(self) -> str:
        return f"{self.ask.ask_id}>{self.slot}"

    @property
    def quiet(self) -> bool:
        """**空でも止まらない組か**(空でよいと宣言されている / 人か LLM が埋めてよい)。"""
        return self.value in (YOTSU[1], YOTSU[2])

    def line(self) -> str:
        return (f"{self.name}:{self.value}:{self.kind}:{self.mark}:{self.rows}"
                f":{'/'.join(self.sources)}")

    def as_dict(self) -> dict[str, object]:
        out: dict[str, object] = {
            "問い": self.ask.ask_id, "呼ぶコマンド名": self.ask.command,
            "求める rule or 式の id": self.ask.target,
            "欄": self.slot, "欄の種別": self.kind, "判定": self.value,
            "出典": list(self.sources)}
        if self.mark:
            out["空でよい欄の印"] = self.mark
            out["当たる行数"] = self.rows if self.rows else "宣言なし"
        return out


def judge(ask: Ask, slot: str, slots: Slots, shapes: Shapes) -> Cell:
    """問い × 欄 の組 1 つに 4 値のどれか 1 つを付ける。**省略の正否は決めない。**

    上から順に見る。問いの行の出典が空なら、そこで終わり(別枠)。欄名が登録表に無ければ
    終わり(別枠)。同じ欄に 2 通りの宣言が在れば終わり(別枠)。問いが手元に在ると宣言した
    欄も、空にする欄ではないので別に数える。そこから先で、はじめて空にできるか記号で
    (A)(B)(D) へ振り分け、**誰が埋めてよいかが `人かLLM` の欄だけを (C) へ移す**。
    (B) の組には行の在り方の表から行数を引いて印を付ける(**無ければ推測せず
    「行数の宣言が無い」**)。
    """
    kind = slots.kind_of(slot)
    if not ask.source:
        return Cell(ask, slot, BETSUWAKU[2], kind)
    decls = slots.decls(slot)
    if not decls:
        return Cell(ask, slot, BETSUWAKU[1], kind)
    if slots.conflicting(slot):
        return Cell(ask, slot, BETSUWAKU[0], kind,
                    sources=tuple(d.source for d in decls))
    if slot in ask.slots:
        return Cell(ask, slot, AT_HAND, kind, sources=(ask.source,))
    d = decls[0]
    if d.emptiable == EMPTIABLE[0]:
        value = YOTSU[0]
    elif d.emptiable == EMPTIABLE[1]:
        value = YOTSU[1]
    else:
        value = YOTSU[3]
    if d.filler == FILLERS[2]:      # **`人かLLM` は (A)(B)(D) より後に当たる**
        value = YOTSU[2]
    if value != YOTSU[1]:
        return Cell(ask, slot, value, kind, sources=(d.source,))
    shape = shapes.of(ask.target, slot)
    if shape is None:
        return Cell(ask, slot, value, kind, mark=MARKS[2], sources=(d.source,))
    mark = MARKS[0] if shape.rows == 1 else MARKS[1]
    return Cell(ask, slot, value, kind, mark=mark, rows=shape.rows,
                sources=(d.source, shape.source))


@dataclass(frozen=True)
class Report:
    ok: bool
    pending: tuple[Pending, ...]
    asks: int
    slots: int
    shapes: int
    exits: int


@dataclass(frozen=True)
class Table:
    report: Report
    cells: tuple[Cell, ...]
    names: tuple[str, ...]
    asks: Asks
    slots: Slots
    shapes: Shapes
    exits: Exits

    # ---------------- 分母

    def ask_denominator(self) -> int:
        return self.report.asks

    def slot_denominator(self) -> int:
        return len(self.names)

    def pair_denominator(self) -> int:
        return len(self.cells)

    # ---------------- 件数

    def four(self) -> dict[str, int]:
        return {k: sum(1 for c in self.cells if c.value == k) for k in YOTSU}

    def extras(self) -> dict[str, int]:
        return {k: sum(1 for c in self.cells if c.value == k) for k in BETSUWAKU}

    def at_hand(self) -> int:
        return sum(1 for c in self.cells if c.value == AT_HAND)

    def marks(self) -> dict[str, int]:
        return {k: sum(1 for c in self.cells if c.mark == k) for k in MARKS}

    def quiet_cells(self) -> tuple[Cell, ...]:
        """**空でも止まらない組**((B) + (C))。"""
        return tuple(c for c in self.cells if c.quiet)

    def wide_cells(self) -> tuple[Cell, ...]:
        """そのうち `2 行以上が当たる` 印の付いた組。"""
        return tuple(c for c in self.quiet_cells() if c.mark == MARKS[1])

    def by_ask(self) -> list[dict[str, object]]:
        """問いごとの内訳(**合計が全組に戻るのが検算**)。"""
        out: list[dict[str, object]] = []
        for a in self.asks.ordered:
            here = [c for c in self.cells if c.ask.ask_id == a.ask_id]
            out.append({"問い": a.ask_id, "呼ぶコマンド名": a.command,
                        "求める rule or 式の id": a.target,
                        "手元に在ると宣言した欄の数": a.at_hand,
                        "4 値": {k: sum(1 for c in here if c.value == k)
                                 for k in YOTSU},
                        "別枠": {k: sum(1 for c in here if c.value == k)
                                 for k in BETSUWAKU},
                        AT_HAND: sum(1 for c in here if c.value == AT_HAND),
                        "空でも止まらない欄": sum(1 for c in here if c.quiet),
                        "うち 2 行以上が当たる": sum(1 for c in here
                                                   if c.quiet and c.mark == MARKS[1]),
                        "組の件数": len(here),
                        "出典": a.source or "(空欄)"})
        return out

    def by_kind(self) -> list[dict[str, object]]:
        """欄の種別ごとの内訳(**合計が全組に戻るのが 2 つめの検算**)。"""
        out: list[dict[str, object]] = []
        for kind in sorted({c.kind for c in self.cells}):
            here = [c for c in self.cells if c.kind == kind]
            out.append({"欄の種別": kind,
                        "欄の数": len({c.slot for c in here}),
                        "組の件数": len(here),
                        "4 値": {k: sum(1 for c in here if c.value == k)
                                 for k in YOTSU},
                        "空でも止まらない欄": sum(1 for c in here if c.quiet)})
        return out

    def by_slot(self) -> list[dict[str, object]]:
        """欄ごとの一覧(= 境界表の行。**正しい埋め方の列は無い**)。"""
        out: list[dict[str, object]] = []
        for name in self.names:
            here = [c for c in self.cells if c.slot == name]
            decls = self.slots.decls(name)
            out.append({"欄": name,
                        "欄の種別": self.slots.kind_of(name),
                        "宣言の本数": len(decls),
                        "空にできるか": sorted({d.emptiable for d in decls}),
                        "誰が埋めてよいか": sorted({d.filler for d in decls}),
                        "出口記号": sorted({d.exit for d in decls}),
                        "宣言の出典": [d.source for d in decls],
                        "4 値": {k: sum(1 for c in here if c.value == k)
                                 for k in YOTSU},
                        "別枠": {k: sum(1 for c in here if c.value == k)
                                 for k in BETSUWAKU},
                        "印": sorted({c.mark for c in here if c.mark}),
                        "組の件数": len(here)})
        return out

    def quiet_listed(self) -> list[dict[str, object]]:
        return [c.as_dict() for c in self.quiet_cells()]

    def extras_listed(self) -> list[dict[str, object]]:
        return [c.as_dict() for c in self.cells if c.value in BETSUWAKU]

    def listed(self) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for k in YOTSU + BETSUWAKU + (AT_HAND,):
            here = [c for c in self.cells if c.value == k]
            out.append({"判定": k, "件数": len(here),
                        "組": [c.as_dict() for c in here]})
        return out

    def dangling_shapes(self) -> list[dict[str, object]]:
        """どの問いも求めていない rule を指す行の在り方の宣言。**止めずに並べる。**"""
        want = set(self.asks.targets)
        return [{"指している rule or 式の id": s.target, "次元名": s.dimension,
                 "当たる行数": s.rows, "出典": s.source}
                for s in self.shapes.ordered if s.target not in want]

    def unused_exits(self) -> list[dict[str, object]]:
        """どの欄も指していない出口の登録(**黙って落とさずに並べる**)。"""
        used = {d.exit for d in self.slots.items}
        return [{"出口記号": e.exit, "止まるか": e.stops, "出典": e.source}
                for e in self.exits.ordered if e.exit not in used]

    def exit_rows(self) -> list[dict[str, str]]:
        """「止まる」の定義(**この表の側に在ることを出力でも示す**)。"""
        return [{"出口記号": e.exit, "止まるか": e.stops, "出典": e.source}
                for e in self.exits.ordered]

    def stopped(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for p in self.report.pending:
            out[p.reason] = out.get(p.reason, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: STOP_REASONS.index(kv[0])))

    # ---------------- まとめ

    def counts(self) -> dict[str, object]:
        """件数を、分母の内訳つきで出す。**正しい埋め方も削減量も返さない。**"""
        four, extras = self.four(), self.extras()
        quiet, wide = len(self.quiet_cells()), len(self.wide_cells())
        out: dict[str, object] = {
            "問いの宣言表の行数": self.report.asks,
            "欄の登録表の行数": self.report.slots,
            "行の在り方の表の行数": self.report.shapes,
            "出口の登録表の行数": self.report.exits,
            "分母(問いの件数)": self.ask_denominator(),
            "分母(欄の件数)": self.slot_denominator(),
            "分母(問い × 欄 の組の件数)": self.pair_denominator(),
            "4 値": four,
            "別枠": extras,
            AT_HAND: self.at_hand(),
            "空でよい欄の印": self.marks(),
            "空でも止まらない欄": quiet,
            "うち 2 行以上が当たる": wide,
            "問いごと": self.by_ask(),
            "欄の種別ごと": self.by_kind(),
            "止まるかの定義": self.exit_rows(),
            "どの問いも求めていない行の在り方の宣言": len(self.dangling_shapes()),
            "どの欄も指していない出口の登録": len(self.unused_exits()),
            "理由別の止まった件数": self.stopped(),
            "読んだか": ("読んだ" if self.cells else
                         "読んでいない(組を作る前に止まったので 4 値は全て 0)"),
        }
        out["分母に含めたもの"] = (
            f"問い {self.ask_denominator()} 件 × 欄 {self.slot_denominator()} 件 = "
            f"組 {self.pair_denominator()} 件。内訳は "
            + " + ".join(f"{k} {four[k]}" for k in YOTSU)
            + " + " + " + ".join(f"{k} {extras[k]}" for k in BETSUWAKU)
            + f" + {AT_HAND} {self.at_hand()}")
        out["件数の合計の検算"] = (
            f"4 値 + 別枠 + {AT_HAND} の合計 "
            f"{sum(four.values()) + sum(extras.values()) + self.at_hand()} / "
            f"組の件数 {self.pair_denominator()}(問いごとの内訳の合計 "
            f"{sum(int(r['組の件数']) for r in self.by_ask())}、"
            f"欄の種別ごとの内訳の合計 "
            f"{sum(int(r['組の件数']) for r in self.by_kind())} も同じ。"
            f"印の合計 {sum(self.marks().values())} / {YOTSU[1]} {four[YOTSU[1]]})")
        out["空白を推測で埋めない"] = (
            "`" + EMPTIABLE[2] + "` と宣言された欄は `" + YOTSU[3] + "` のまま出る。"
            "`" + EMPTIABLE[1] + "` 側へ寄せる引数も、既定を当てる辞書も持たない")
        out["CLI を呼ばない"] = (
            "読むのは 4 枚の表だけ。実際に引く経路・外部プロセスを起こす経路・"
            "通信の経路が無い。だから「空にして呼んだら何が返るか」はこの出力に出ない")
        out["欄に値を入れない"] = (
            "入力に値の列が 1 つも無い。入るのは欄名と記号と行数と出典だけで、"
            "実在の料率・金額・日付が入る欄そのものを持たない")
        out["行数は数え上げで、引いた結果ではない"] = (
            "`" + MARKS[1] + "` は行の在り方の表に人が宣言した行数の写し。空にして"
            "実際に引くと 1 行に決まるか同順位競合で止まるかは、この部品では分からない")
        out["トークン数・削減量を出さない"] = (
            "数え方が手元に無いので、文字数もトークン数も削減量も列に持たない")
        out["省略の正否を決めない"] = (
            "空にしてよいかを決める列が無い。4 値と印を並べるところまでで、"
            "どの欄を埋めるかは呼ぶ人が決める")
        out["どの問いを道具に回すべきか決めない"] = (
            "問いの宣言表に書いた問いだけを数える。問いを選ぶ経路も、"
            "問いごとに要る欄を当てる経路も無い")
        out["入力を下へ辿らない"] = (
            "見るのは 1 段目だけ。欄の中身がまた式か、その式の入力が何かは追わない")
        out["返り値の側を見ない"] = (
            "数えるのは呼ぶ前の欄だけ。返った値に残る一手は別の部品の領分")
        out["行の中身の値を読まない"] = (
            "行の在り方の表に入るのは行数だけで、行の payload を読む経路が無い")
        out["時計を読まない"] = (
            "入力に日付の列も時刻の列も無く、現在時刻を読む呼び出しも持たない")
        out["入力を書き換えない"] = (
            "verify が作る写し(空にできるかの宣言を替えた表・行数を替えた表)は"
            "メモリの中だけで、入力の CSV には 1 文字も書かない")
        return out

    def judgement_bytes(self) -> bytes:
        """判定部分 = 組ごとの判定と印。時刻・絶対パスは入れない。"""
        self._guard()
        lines = ["\t".join(["件", str(self.report.asks), str(self.report.slots),
                            str(self.report.shapes), str(self.report.exits),
                            str(self.slot_denominator())])]
        lines.extend(c.line() for c in self.cells)
        lines.append("\t".join(["静", str(len(self.quiet_cells())),
                                str(len(self.wide_cells())),
                                str(self.at_hand())]))
        return ("\n".join(lines) + "\n").encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.judgement_bytes()).hexdigest()

    def read_condition(self) -> dict[str, str]:
        return dict(zip(SCOPE_KEYS, (self.asks.path, self.slots.path,
                                     self.shapes.path, self.exits.path)))

    def _guard(self) -> None:
        if not self.report.ok:
            raise RuntimeError("止まっているので作った組は無い。"
                               "report.pending の理由コードを見る")


def quiet_slots(asks: Asks, slots: Slots, shapes: Shapes, exits: Exits) -> Table:
    """問い × 欄 の組ごとに 4 値を付け、別枠と印と空でも止まらない欄の件数を返す。

    4 枚のどれかが 1 行でも壊れていたら 1 組も数えない(4 値は全て 0)。
    """
    pending = (list(asks.pending) + list(slots.pending) + list(shapes.pending)
               + list(exits.pending))
    pending.extend(exits.issues())
    pending.extend(shapes.issues())
    pending.extend(slots.issues(exits))
    names = tuple(sorted(set(slots.names) | set(asks.named_slots)
                         | set(shapes.dimensions)))
    report = Report(not pending, tuple(pending), len(asks.items), len(slots.items),
                    len(shapes.items), len(exits.items))
    if pending:                 # 1 組も数えずに止まる
        return Table(report, (), names, asks, slots, shapes, exits)
    cells = tuple(judge(a, s, slots, shapes) for a in asks.ordered for s in names)
    return Table(report, cells, names, asks, slots, shapes, exits)


# ------------------------------------------------------------ verify


def moved_elsewhere(first: Table, after: Table, *keep: str) -> list[str]:
    """判定か印が動いた組のうち、動くはずだった組でないものの名前。"""
    before = {c.name: f"{c.value}:{c.mark}:{c.rows}" for c in first.cells}
    now = {c.name: f"{c.value}:{c.mark}:{c.rows}" for c in after.cells}
    return sorted(k for k in before if k not in keep and before[k] != now.get(k, ""))


def declare_probe_plan(first: Table) -> tuple[str, tuple[str, ...]] | None:
    """`できる` → `宣言なし` に替える欄を決める(= (B) の組を持つ最初の欄名)。"""
    for name in first.names:
        decls = first.slots.decls(name)
        if len(decls) != 1 or decls[0].emptiable != EMPTIABLE[1]:
            continue
        hit = tuple(c.name for c in first.cells
                    if c.slot == name and c.value == YOTSU[1])
        if hit:
            return name, hit
    return None


def declare_probe(asks: Asks, slots: Slots, shapes: Shapes, exits: Exits,
                  first: Table) -> dict[str, object]:
    """**`空にできるか` を 1 件 `できる` → `宣言なし` に替えると、その欄の組だけ (B) → (D)。**

    他の組と別枠の件数は変わらない(= `宣言なし` を `できる` 側へ寄せる経路が無いことの物理形)。
    """
    plan = declare_probe_plan(first)
    if plan is None:
        return {"合うか": True, "替えた欄": "",
                "観測": "`" + EMPTIABLE[1] + "` の宣言 1 本だけを持つ欄に (B) の組が"
                        "無いので、この写しは作らない"}
    name, moving = plan
    after = quiet_slots(asks, slots.rewritten(name, EMPTIABLE[2]), shapes, exits)
    if not after.report.ok:
        return {"合うか": False, "替えた欄": name,
                "観測": "写しが止まった(理由コードを見る)"}
    moved = moved_elsewhere(first, after, *moving)
    now = {c.name: c.value for c in after.cells}
    ok = (not moved and all(now.get(k) == YOTSU[3] for k in moving)
          and first.extras() == after.extras()
          and first.at_hand() == after.at_hand()
          and first.four()[YOTSU[1]] - len(moving) == after.four()[YOTSU[1]]
          and first.four()[YOTSU[3]] + len(moving) == after.four()[YOTSU[3]]
          and first.four()[YOTSU[0]] == after.four()[YOTSU[0]]
          and first.four()[YOTSU[2]] == after.four()[YOTSU[2]])
    return {"合うか": ok, "替えた欄": name, "替えた先": EMPTIABLE[2],
            "移った組": list(moving), "ほかで動いた組": moved,
            "4 値(前)": first.four(), "4 値(後)": after.four(),
            "別枠(前)": first.extras(), "別枠(後)": after.extras(),
            "印(前)": first.marks(), "印(後)": after.marks()}


def rows_probe_plan(first: Table) -> tuple[str, str, str] | None:
    """行数を 1 → 2 に替える相手を決める(= `1 行に決まる` の印が付いた最初の組)。"""
    for c in first.cells:
        if c.mark == MARKS[0]:
            return c.ask.target, c.slot, c.name
    return None


def rows_probe(asks: Asks, slots: Slots, shapes: Shapes, exits: Exits,
               first: Table) -> dict[str, object]:
    """**行の在り方の行数を 1 → 2 に替えると、その組の印だけが移り、4 値は変わらない。**"""
    plan = rows_probe_plan(first)
    if plan is None:
        return {"合うか": True, "替えた組": "",
                "観測": "`" + MARKS[0] + "` の印が付いた組が無いので、この写しは作らない"}
    target, dimension, who = plan
    after = quiet_slots(asks, slots, shapes.bumped(target, dimension, 2), exits)
    if not after.report.ok:
        return {"合うか": False, "替えた組": who,
                "観測": "写しが止まった(理由コードを見る)"}
    moved = moved_elsewhere(first, after, who)
    now = next(c for c in after.cells if c.name == who)
    ok = (not moved and now.mark == MARKS[1] and now.rows == 2
          and first.four() == after.four() and first.extras() == after.extras()
          and first.marks()[MARKS[0]] - 1 == after.marks()[MARKS[0]]
          and first.marks()[MARKS[1]] + 1 == after.marks()[MARKS[1]])
    return {"合うか": ok, "替えた組": who,
            "替えた rule or 式の id": target, "替えた次元名": dimension,
            "替える前の行数": 1, "替えた後の行数": 2,
            "印(前)": first.marks(), "印(後)": after.marks(),
            "4 値は不変か": first.four() == after.four(),
            "ほかで動いた組": moved,
            "空でも止まらない欄(前)": len(first.quiet_cells()),
            "空でも止まらない欄(後)": len(after.quiet_cells()),
            "うち 2 行以上が当たる(前)": len(first.wide_cells()),
            "うち 2 行以上が当たる(後)": len(after.wide_cells())}


def verify(asks: Asks, slots: Slots, shapes: Shapes,
           exits: Exits) -> dict[str, object]:
    """5 つ見る。二度走りの sha256 / 4 枚の行順の入れ替え / 合計の検算 /
    空にできるかの宣言を替えた写し / 行数を替えた写し。"""
    first = quiet_slots(asks, slots, shapes, exits)
    if not first.report.ok:
        return {"ok": False, "stage": "止まった(作った組は返さない)", **first.counts(),
                "pending": [p.as_dict() for p in first.report.pending]}
    second = quiet_slots(asks, slots, shapes, exits)
    pending: list[Pending] = []
    if first.sha256() != second.sha256():
        pending.append(Pending(STOP_REASONS[8], f"2 回目 {second.sha256()[:12]}"))
    swapped: dict[str, str] = {}
    for how in SWAPS:
        third = quiet_slots(asks.swapped(how), slots.swapped(how),
                            shapes.swapped(how), exits.swapped(how))
        swapped[how] = third.sha256() if third.report.ok else ""
        if not (third.report.ok and first.sha256() == third.sha256()):
            pending.append(Pending(STOP_REASONS[9],
                                   f"入れ替え方 {how} で {swapped[how] or '止まった'}"))
    four, extras = first.four(), first.extras()
    total = sum(four.values()) + sum(extras.values()) + first.at_hand()
    if total != first.pair_denominator():
        pending.append(Pending(STOP_REASONS[7],
                               f"4 値 + 別枠 + {AT_HAND} の合計 {total} / "
                               f"組の件数 {first.pair_denominator()}"))
    if first.pair_denominator() != first.ask_denominator() * first.slot_denominator():
        pending.append(Pending(STOP_REASONS[7],
                               f"組の件数 {first.pair_denominator()} / 問い "
                               f"{first.ask_denominator()} × 欄 "
                               f"{first.slot_denominator()}"))
    for what, rows in (("問いごと", first.by_ask()), ("欄の種別ごと", first.by_kind())):
        got = sum(int(r["組の件数"]) for r in rows)
        if got != first.pair_denominator():
            pending.append(Pending(STOP_REASONS[7],
                                   f"{what}の内訳の合計 {got} / 組の件数 "
                                   f"{first.pair_denominator()}"))
    if sum(first.marks().values()) != four[YOTSU[1]]:
        pending.append(Pending(STOP_REASONS[7],
                               f"印の合計 {sum(first.marks().values())} / "
                               f"{YOTSU[1]} {four[YOTSU[1]]}"))
    out: dict[str, object] = {
        "ok": not pending, "読んだ回数": 2, "入れ替え方": list(SWAPS),
        "sha256": first.sha256(), "2 回目の sha256": second.sha256(),
        "入れ替えた 4 枚の sha256": swapped,
        "件数の検算": {"4 値": four, "別枠": extras, AT_HAND: first.at_hand(),
                       "合計": total, "印": first.marks(),
                       "問いごとの内訳の合計":
                           sum(int(r["組の件数"]) for r in first.by_ask()),
                       "欄の種別ごとの内訳の合計":
                           sum(int(r["組の件数"]) for r in first.by_kind()),
                       "分母(問いの件数)": first.ask_denominator(),
                       "分母(欄の件数)": first.slot_denominator(),
                       "分母(問い × 欄 の組の件数)": first.pair_denominator(),
                       "空でも止まらない欄": len(first.quiet_cells()),
                       "うち 2 行以上が当たる": len(first.wide_cells())},
        "空にできるかの宣言を替えた写し":
            declare_probe(asks, slots, shapes, exits, first),
        "行数を替えた写し": rows_probe(asks, slots, shapes, exits, first),
    }
    for key in ("空にできるかの宣言を替えた写し", "行数を替えた写し"):
        if not out[key]["合うか"]:        # type: ignore[index]
            pending.append(Pending(STOP_REASONS[7], f"{key} の件数が合わない"))
            out["ok"] = False
    if pending:
        out["観測"] = ("同じ表から違うバイト列が出た、または件数が合わない"
                       "(平均も多数決もしない。正しい埋め方も当てない)")
        out["pending"] = [p.as_dict() for p in pending]
    return out


# ------------------------------------------------------------ ひな型

T_ASK = "合成の呼び出しのメモ(架空)L1"
T_WORD = "合成の宣言のメモ(架空)L1"
T_SHAPE = "合成の行数のメモ(架空)L1"

TEMPLATE_ASKS = [
    list(ASK_COLUMNS),
    ["Q1", "status", NO_MARK, "", T_ASK],
    ["Q2", "resolve", "R1", "K1|K3", T_ASK],
]
TEMPLATE_SLOTS = [
    list(SLOT_COLUMNS),
    ["K1", KINDS[0], EMPTIABLE[0], FILLERS[0], EXITS[0], T_WORD],
    ["K3", KINDS[1], EMPTIABLE[1], FILLERS[0], NO_MARK, T_WORD],
    ["K7", KINDS[2], EMPTIABLE[2], FILLERS[3], NO_MARK, T_WORD],
]
TEMPLATE_SHAPES = [
    list(SHAPE_COLUMNS),
    ["R1", "K3", "47", T_SHAPE],
]
TEMPLATE_EXITS = [
    list(EXIT_COLUMNS),
    [EXITS[0], STOPS[0], T_WORD],
    [EXITS[1], STOPS[0], T_WORD],
    [EXITS[3], STOPS[1], T_WORD],
]


def write_csv(path: Path, rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    return path


def init(dest: str | Path) -> tuple[Path, ...]:
    d = Path(dest)
    return (write_csv(d / "問いの宣言表.csv", TEMPLATE_ASKS),
            write_csv(d / "欄の登録表.csv", TEMPLATE_SLOTS),
            write_csv(d / "行の在り方の表.csv", TEMPLATE_SHAPES),
            write_csv(d / "出口の登録表.csv", TEMPLATE_EXITS))


# ------------------------------------------------------------ CLI

def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def build_parser() -> argparse.ArgumentParser:
    """CLI は cells / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = argparse.ArgumentParser(prog="quiet_slots",
                                 description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in SUBCOMMANDS[:3]:
        p = sub.add_parser(name)
        for arg in ("asks", "slots", "shapes", "exits"):
            p.add_argument(arg)
    sub.add_parser(SUBCOMMANDS[3]).add_argument("dest")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == "init":
        print("書いた: " + " / ".join(str(p) for p in init(a.dest)))
        return 0
    try:
        four = (Asks.load(a.asks), Slots.load(a.slots), Shapes.load(a.shapes),
                Exits.load(a.exits))
        if a.cmd == "verify":
            out = verify(*four)
            _print(out)
            return 0 if out["ok"] else 3
        t = quiet_slots(*four)
    except ReadError as e:
        print(f"表として読めない: {e}", file=sys.stderr)
        return 2
    if not t.report.ok:
        _print({"ok": False, "stage": "止まった(作った組は返さない)", **t.counts(),
                "pending": [p.as_dict() for p in t.report.pending]})
        return 3
    body: dict[str, object] = {"ok": True, **t.counts()}
    if a.cmd == SUBCOMMANDS[0]:
        body["判定ごとの一覧"] = t.listed()
        body["空でも止まらない欄の一覧"] = t.quiet_listed()
        body["別枠の一覧"] = t.extras_listed()
        body["欄ごと"] = t.by_slot()
        body["どの問いも求めていない行の在り方の宣言の一覧"] = t.dangling_shapes()
        body["どの欄も指していない出口の登録の一覧"] = t.unused_exits()
        body["sha256"] = t.sha256()
        body["読んだ条件"] = t.read_condition()
    _print(body)
    clean = (not t.quiet_cells() and not sum(t.extras().values())
             and not t.stopped() and not t.dangling_shapes())
    return 0 if clean else 3


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
