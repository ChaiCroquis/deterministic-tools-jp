"""band_edge — 宣言された帯の表で値を引き、境界ちょうどに当たった件数を別に数える。

**帯の境界ちょうどの値は、以上と未満のどちらを書いたかが表に無いと、どちらの帯にも入れられる
(そして黙ってどちらかに入る)。** この部品は、等号の向きを帯の表の欄からだけ取り、値を帯に
当て、値の行ごとに 4 値に分ける。境界値ちょうどに触れた件数は別の欄で数えて返す。

持たせていないものが規律になっている。

  - **等号の欄が空の帯行は使わずに止まる**(「以上・未満」を既定にしない)
  - **上端・下端が開いている帯は、宣言で「開いている」と書かれた時だけ許す**(空欄と開放を
    区別し、空欄を無限と読み替えない)
  - **帯の重なりと隙間を自分で検算し、合わなければ止まる**(宣言された範囲を帯の連結が
    覆うか、同じ値が 2 つの帯に入らないか)
  - **値を帯に入れるために丸めない・寄せない**(四捨五入・切上げ・切捨ての引数が無い)
  - **単位が違う値を黙って換算しない**(換算の宣言が無ければ止まる)
  - **境界ちょうどに当たった件数を必ず別の欄で数えて出す**(下限ちょうど / 上限ちょうど /
    その両方。当たった率を単独で返さず分母の内訳を併記)
  - **当たる帯が 2 つなら「決まらない(重なり)」、0 なら「当たる帯が無い」として返す**
    (最寄りの帯に寄せる経路が無い、端の帯に押し込まない)
  - **等号の向きを総当たりで並べない**(以上と超を両方試して答えが 2 通り出る経路は無い)
  - **日付で帯の表の版を選ばない**(基準日・公表時点の引数が無い)
  - **帯の行も値の行も生成せず、入力表を書き換えない**
  - **出典の欄が空の帯行・値の行は使わずに止まる**
  - **float を使わない**(値は Decimal、比較は宣言された値の種類でのみ行う)

入力は 3 つ。値の表(CSV)、帯の表(CSV)、単位の宣言(CSV)。

値の表の列は 6 つ。

    target      対象(空欄は「表として読めない」)
    item        項目(単位の宣言に無い項目は止まる)
    value       値(Decimal。小数の桁は単位の宣言から取る)
    kind        値の種類。登録の 6 種。空欄は止まる
    unit        単位。項目の宣言と違うときは換算の宣言が要る
    source      出典。空欄は止まる

帯の表の列は 9 つ。

    item        項目
    no          帯の番号(整数。同じ項目で重複したら止まる)
    low         下限(数 か 開いている。空欄は止まる)
    low_eq      下限の等号。以上 / 超。下限が数のときに空欄なら止まる
    high        上限(数 か 開いている。空欄は止まる)
    high_eq     上限の等号。未満 / 以下。上限が数のときに空欄なら止まる
    returns     当たったときに返すもの(空欄は「表として読めない」)
    source      出典。空欄は止まる
    swap        入れ替え方(verify が帯の表の行順を入れ替えるときの宣言。全行で同じ値)

単位の宣言の列は 6 つ。

    item        項目
    kind        値の種類。登録の 6 種
    unit        この項目を引くときの単位
    digits      小数の桁(整数。日数・月数・年数・人数は 0 だけ)
    from_unit   換算の相手(空欄 = 換算を宣言していない)
    factor      係数(from_unit の値に掛けると unit になる)

使い方:

    python band_edge.py init ひな型/
    python band_edge.py check  値の表.csv 帯の表.csv 単位の宣言.csv
    python band_edge.py match  値の表.csv 帯の表.csv 単位の宣言.csv
    python band_edge.py verify 値の表.csv 帯の表.csv 単位の宣言.csv
"""
from __future__ import annotations

import argparse
import csv
import datetime
import decimal
import hashlib
import json
import platform
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

ATAI_COLUMNS = ("target", "item", "value", "kind", "unit", "source")
OBI_COLUMNS = ("item", "no", "low", "low_eq", "high", "high_eq", "returns", "source", "swap")
TANI_COLUMNS = ("item", "kind", "unit", "digits", "from_unit", "factor")

# 登録の語彙。ここに無い語は「表として読めない」で返す(理由コードには混ぜない)
KINDS = ("金額", "日数", "月数", "年数", "時間", "人数")
INTEGER_KINDS = ("日数", "月数", "年数", "人数")   # 小数の桁は 0 だけ
LOW_EQS = ("以上", "超")
HIGH_EQS = ("未満", "以下")
OPEN = "開いている"                                  # 空欄と区別する(空欄を無限と読み替えない)
SWAPS = ("逆順", "両端入れ替え", "1 つずらす")

# 値の行ごとの 4 値。「決まらない」と「止まった」を混ぜない
RESULTS = ("帯が 1 つに決まった", "当たる帯が無い", "決まらない(重なり)", "止まった")

# 止まる理由コード(13 個)
STOP_REASONS = ("等号が空", "開放の宣言が無い空欄", "帯の重なり", "帯の隙間",
                "単位の宣言が無いか換算が未宣言", "出典の欄が空", "値の種類が空",
                "下限 > 上限", "帯の番号の重複", "該当項目の帯が 0 件",
                "覆いの検算が合わない", "2 回目の判定部分が不一致",
                "行順を入れ替えた表で出力が変わる")

# CLI の下位コマンド。この 4 つだけで、option は -h 以外に 1 つも無い
SUBCOMMANDS = ("match", "check", "verify", "init")

# 判定部分に入れない欄(sha256 の対象にもしない)
READ_KEYS = ("読んだ値の表の絶対パス", "読んだ帯の表の絶対パス", "読んだ単位の宣言の絶対パス",
             "読んだ時刻", "ホスト名")


class ReadError(Exception):
    """表として読めない(理由コードにせず終了コード 2 で返す = 表を書く側の話)。"""


def as_decimal(text: str, where: str) -> Decimal:
    """Decimal としてだけ読む(float は使わない。指数表記も受けない)。"""
    try:
        v = Decimal(text)
    except decimal.InvalidOperation:
        raise ReadError(f"{where}: 数として読めない({text})") from None
    if not v.is_finite() or "E" in text.upper():
        raise ReadError(f"{where}: 数として読めない({text})")
    return v


def as_int(text: str, where: str) -> int | None:
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        raise ReadError(f"{where}: 整数として読めない({text})") from None


def fits(value: Decimal, digits: int) -> bool:
    """宣言された小数の桁に、丸めずにそのまま収まるか。"""
    return -int(value.as_tuple().exponent) <= digits


@dataclass(frozen=True)
class Pending:
    reason: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"reason": self.reason, "detail": self.detail}


# ------------------------------------------------------------------ 単位の宣言

@dataclass(frozen=True)
class Unit:
    item: str
    kind: str
    unit: str
    digits: int
    from_unit: str
    factor: Decimal | None
    number: int

    @property
    def step(self) -> Decimal:
        """この項目で隣り合う 2 つの値の間隔(小数の桁から出す)。"""
        return Decimal(1).scaleb(-self.digits)

    def convert(self, value: Decimal, unit: str) -> Decimal | None:
        """宣言された換算だけを行う。宣言が無ければ None(= 黙って換算しない)。"""
        if unit == self.unit:
            return value
        if self.from_unit and unit == self.from_unit and self.factor is not None:
            return value * self.factor
        return None


@dataclass(frozen=True)
class Units:
    items: tuple[Unit, ...]
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Units":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"単位の宣言が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Units":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in TANI_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("単位の宣言に " + " / ".join(lack) + " の列が無い")
        items: list[Unit] = []
        seen: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in TANI_COLUMNS}
            where = f"単位の宣言 行 {i}"
            if not cell["item"]:
                raise ReadError(f"{where}: 項目が空欄")
            if cell["item"] in seen:
                raise ReadError(f"{where}: 項目 {cell['item']} の宣言が 2 行ある")
            seen.add(cell["item"])
            if cell["kind"] not in KINDS:
                raise ReadError(f"{where}: 値の種類は {' / '.join(KINDS)}({cell['kind']})")
            if not cell["unit"]:
                raise ReadError(f"{where}: 単位が空欄")
            digits = as_int(cell["digits"], f"{where} の小数の桁")
            if digits is None or digits < 0:
                raise ReadError(f"{where}: 小数の桁は 0 以上の整数({cell['digits']})")
            if cell["kind"] in INTEGER_KINDS and digits != 0:
                raise ReadError(f"{where}: 値の種類 {cell['kind']} の小数の桁は 0 だけ"
                                f"({digits})")
            if cell["factor"] and not cell["from_unit"]:
                raise ReadError(f"{where}: 換算の相手が空の行に係数は書かない")
            if cell["from_unit"] and not cell["factor"]:
                raise ReadError(f"{where}: 換算の相手を書いた行には係数が要る")
            if cell["from_unit"] and cell["from_unit"] == cell["unit"]:
                raise ReadError(f"{where}: 換算の相手が単位そのもの({cell['unit']})")
            items.append(Unit(item=cell["item"], kind=cell["kind"], unit=cell["unit"],
                              digits=digits, from_unit=cell["from_unit"],
                              factor=(as_decimal(cell["factor"], f"{where} の係数")
                                      if cell["factor"] else None), number=i))
        if not items:
            raise ReadError("単位の宣言に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), path=path)

    def of(self, item: str) -> Unit | None:
        return next((u for u in self.items if u.item == item), None)


# ------------------------------------------------------------------ 帯の表

@dataclass(frozen=True)
class Band:
    item: str
    no: int
    low: Decimal | None          # None = 開いている(下端が無い)
    low_eq: str
    high: Decimal | None         # None = 開いている(上端が無い)
    high_eq: str
    returns: str
    source: str
    number: int

    def lo_inc(self, step: Decimal) -> Decimal | None:
        """この帯に入るいちばん小さい値(開いていれば None)。"""
        if self.low is None:
            return None
        return self.low if self.low_eq == LOW_EQS[0] else self.low + step

    def hi_inc(self, step: Decimal) -> Decimal | None:
        """この帯に入るいちばん大きい値(開いていれば None)。"""
        if self.high is None:
            return None
        return self.high if self.high_eq == HIGH_EQS[1] else self.high - step

    def holds(self, value: Decimal, step: Decimal) -> bool:
        """宣言された等号だけで判定する(寄せも丸めもしない)。"""
        lo, hi = self.lo_inc(step), self.hi_inc(step)
        return (lo is None or value >= lo) and (hi is None or value <= hi)


@dataclass(frozen=True)
class Bands:
    items: tuple[Band, ...]
    swap: str
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Bands":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"帯の表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Bands":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in OBI_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("帯の表に " + " / ".join(lack) + " の列が無い")
        items: list[Band] = []
        pending: list[Pending] = []
        swaps: set[str] = set()
        seen: dict[tuple[str, int], int] = {}
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in OBI_COLUMNS}
            if not cell["item"]:
                raise ReadError(f"帯の表 行 {i}: 項目が空欄")
            if not cell["returns"]:
                raise ReadError(f"帯の表 行 {i}: 返すものが空欄({cell['item']})")
            no = as_int(cell["no"], f"帯の表 行 {i} の帯の番号")
            if no is None:
                raise ReadError(f"帯の表 行 {i}: 帯の番号が空欄")
            where = f"帯の表 行 {i}({cell['item']} 帯 {no})"
            if cell["low_eq"] and cell["low_eq"] not in LOW_EQS:
                raise ReadError(f"帯の表 行 {i}: 下限の等号は {' / '.join(LOW_EQS)}"
                                f"({cell['low_eq']})")
            if cell["high_eq"] and cell["high_eq"] not in HIGH_EQS:
                raise ReadError(f"帯の表 行 {i}: 上限の等号は {' / '.join(HIGH_EQS)}"
                                f"({cell['high_eq']})")
            if cell["low"] == OPEN and cell["low_eq"]:
                raise ReadError(f"帯の表 行 {i}: 開いている下端に等号は書かない"
                                f"({cell['low_eq']})")
            if cell["high"] == OPEN and cell["high_eq"]:
                raise ReadError(f"帯の表 行 {i}: 開いている上端に等号は書かない"
                                f"({cell['high_eq']})")
            if cell["swap"]:
                if cell["swap"] not in SWAPS:
                    raise ReadError(f"帯の表 行 {i}: 入れ替え方 {cell['swap']} は登録の外"
                                    f"({' / '.join(SWAPS)})")
                swaps.add(cell["swap"])
            low = (None if cell["low"] in ("", OPEN)
                   else as_decimal(cell["low"], f"帯の表 行 {i} の下限"))
            high = (None if cell["high"] in ("", OPEN)
                    else as_decimal(cell["high"], f"帯の表 行 {i} の上限"))
            # 空欄は「開いている」ではない。宣言されていないものを無限と読み替えない
            if not cell["low"]:
                pending.append(Pending(STOP_REASONS[1], where + ": 下限が空欄"))
            elif cell["low"] != OPEN and not cell["low_eq"]:
                pending.append(Pending(STOP_REASONS[0], where + ": 下限の等号が空"))
            if not cell["high"]:
                pending.append(Pending(STOP_REASONS[1], where + ": 上限が空欄"))
            elif cell["high"] != OPEN and not cell["high_eq"]:
                pending.append(Pending(STOP_REASONS[0], where + ": 上限の等号が空"))
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[5], where))
            key = (cell["item"], no)
            if key in seen:
                pending.append(Pending(STOP_REASONS[8],
                                       f"{cell['item']} 帯 {no}: 行 {seen[key]} と行 {i}"))
            else:
                seen[key] = i
            items.append(Band(item=cell["item"], no=no, low=low, low_eq=cell["low_eq"],
                              high=high, high_eq=cell["high_eq"], returns=cell["returns"],
                              source=cell["source"], number=i))
        if not items:
            raise ReadError("帯の表に行が無い(ヘッダだけ)")
        if len(swaps) > 1:
            raise ReadError("入れ替え方の宣言が 2 通り以上ある: " + " / ".join(sorted(swaps)))
        return cls(items=tuple(items), swap=next(iter(swaps), ""),
                   pending=tuple(pending), path=path)

    def of(self, item: str) -> tuple[Band, ...]:
        return tuple(b for b in self.items if b.item == item)

    def swapped(self, how: str) -> "Bands":
        """宣言された入れ替え方で帯の表の行順だけを入れ替える(乱数の既定は持たない)。"""
        if how not in SWAPS:
            raise ReadError(f"入れ替え方が登録の外: {how}")
        rows = list(self.items)
        if len(rows) >= 2:
            if how == SWAPS[0]:
                rows.reverse()
            elif how == SWAPS[1]:
                rows[0], rows[-1] = rows[-1], rows[0]
            else:
                rows = rows[1:] + rows[:1]
        return Bands(items=tuple(rows), swap=self.swap, pending=self.pending, path=self.path)


# ------------------------------------------------------------------ 値の表

@dataclass(frozen=True)
class Value:
    target: str
    item: str
    value: Decimal
    kind: str
    unit: str
    source: str
    number: int


@dataclass(frozen=True)
class Values:
    items: tuple[Value, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Values":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"値の表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Values":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in ATAI_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("値の表に " + " / ".join(lack) + " の列が無い")
        items: list[Value] = []
        pending: list[Pending] = []
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in ATAI_COLUMNS}
            if not cell["target"]:
                raise ReadError(f"値の表 行 {i}: 対象が空欄")
            if not cell["item"]:
                raise ReadError(f"値の表 行 {i}: 項目が空欄({cell['target']})")
            if not cell["unit"]:
                raise ReadError(f"値の表 行 {i}: 単位が空欄({cell['item']})")
            if cell["kind"] and cell["kind"] not in KINDS:
                raise ReadError(f"値の表 行 {i}: 値の種類は {' / '.join(KINDS)}"
                                f"({cell['kind']})")
            where = f"値の表 行 {i}({cell['target']} / {cell['item']})"
            if not cell["kind"]:
                pending.append(Pending(STOP_REASONS[6], where))
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[5], where))
            items.append(Value(target=cell["target"], item=cell["item"],
                               value=as_decimal(cell["value"], f"値の表 行 {i} の値"),
                               kind=cell["kind"], unit=cell["unit"],
                               source=cell["source"], number=i))
        if not items:
            raise ReadError("値の表に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    @property
    def ordered(self) -> tuple[Value, ...]:
        """項目・値・行番号の順に並べ替えて返す(表の行順には依らせない)。"""
        return tuple(sorted(self.items, key=lambda v: (v.item, v.value, v.number)))


# ------------------------------------------------------------------ 覆いの検算

@dataclass(frozen=True)
class Cover:
    """1 つの項目について、帯の連結が宣言された範囲を覆っているかの実測。"""
    item: str
    bands: int
    closed: int
    low: Decimal | None
    high: Decimal | None
    width: Decimal | None        # 覆いの幅(刻みの個数)
    counted: Decimal | None      # 帯ごとの個数の合計 - 点の重なり
    point_overlaps: tuple[tuple[int, int], ...] = ()
    gaps: tuple[tuple[int, int], ...] = ()
    range_overlaps: tuple[tuple[int, int], ...] = ()
    reversed_bands: tuple[int, ...] = ()

    @property
    def ok(self) -> bool:
        return (not self.gaps and not self.range_overlaps and not self.reversed_bands
                and (self.width is None or self.width == self.counted))

    def as_dict(self) -> dict[str, object]:
        return {"項目": self.item, "帯の数": self.bands, "両端が閉じた帯": self.closed,
                "覆いの下端": str(self.low) if self.low is not None else "開いている",
                "覆いの上端": str(self.high) if self.high is not None else "開いている",
                "覆いの幅(刻みの個数)": str(self.width) if self.width is not None else "",
                "帯ごとの個数の合計": str(self.counted) if self.counted is not None else "",
                "点の重なり": [list(p) for p in self.point_overlaps],
                "隙間": [list(p) for p in self.gaps],
                "範囲の重なり": [list(p) for p in self.range_overlaps]}


def band_steps(b: Band, step: Decimal) -> Decimal:
    """両端が閉じた帯に入る値の個数。覆いの検算だけが使う(当たり外れの判定とは別の道)。"""
    lo, hi = b.lo_inc(step), b.hi_inc(step)
    if lo is None or hi is None:
        return Decimal(0)
    return (hi - lo) / step + 1


def cover_of(item: str, bands: tuple[Band, ...], step: Decimal) -> Cover:
    """帯の連結を実測する。隣り合う帯の等号から、隙間・点の重なり・範囲の重なりを分ける。

    点の重なり(= 境界値ちょうど 1 つだけが 2 つの帯に入る)は止めない。この部品の主題は
    そこなので、当たった値の行を「決まらない(重なり)」として返す。範囲の重なりと隙間は
    帯の表そのものの不備なので止まる。
    """
    reversed_bands = tuple(sorted(b.no for b in bands
                                  if b.lo_inc(step) is not None and b.hi_inc(step) is not None
                                  and b.lo_inc(step) > b.hi_inc(step)))
    if reversed_bands:
        return Cover(item=item, bands=len(bands), closed=0, low=None, high=None,
                     width=None, counted=None, reversed_bands=reversed_bands)

    def key(b: Band) -> tuple[int, Decimal, int, Decimal]:
        lo, hi = b.lo_inc(step), b.hi_inc(step)
        return (0 if lo is None else 1, lo if lo is not None else Decimal(0),
                1 if hi is None else 0, hi if hi is not None else Decimal(0))

    order = sorted(bands, key=key)
    gaps: list[tuple[int, int]] = []
    points: list[tuple[int, int]] = []
    ranges: list[tuple[int, int]] = []
    for a, b in zip(order, order[1:]):
        a_hi, b_lo = a.hi_inc(step), b.lo_inc(step)
        if a_hi is None or b_lo is None:
            # 開いた端が内側を向いている = どこまでも重なる
            ranges.append((a.no, b.no))
            continue
        shared = (a_hi - b_lo) / step + 1
        if shared < 0:
            gaps.append((a.no, b.no))
        elif shared == 1:
            points.append((a.no, b.no))
        elif shared > 1:
            ranges.append((a.no, b.no))
    closed = [b for b in order if b.lo_inc(step) is not None and b.hi_inc(step) is not None]
    low = high = width = counted = None
    if closed:
        low = min(b.lo_inc(step) for b in closed)        # type: ignore[type-var]
        high = max(b.hi_inc(step) for b in closed)       # type: ignore[type-var]
        width = (high - low) / step + 1
        counted = sum((band_steps(b, step) for b in closed), Decimal(0))
        counted -= Decimal(len([p for p in points
                                if p[0] in {b.no for b in closed}
                                and p[1] in {b.no for b in closed}]))
    return Cover(item=item, bands=len(bands), closed=len(closed), low=low, high=high,
                 width=width, counted=counted, point_overlaps=tuple(points),
                 gaps=tuple(gaps), range_overlaps=tuple(ranges))


# ------------------------------------------------------------------ 引く

@dataclass(frozen=True)
class Hit:
    """値の行 1 つの引き当て。丸めも寄せもしていない。"""
    value: Value
    result: str
    used: Decimal | None = None          # 宣言された単位に揃えた値
    converted: str = ""                  # 換算したときだけ「<元の単位> → <単位>」
    bands: tuple[int, ...] = ()          # 当たった帯の番号(2 つ以上なら 決まらない)
    returns: str = ""
    source: str = ""
    low_edge: tuple[int, ...] = ()       # 下限ちょうどに触れた帯の番号
    high_edge: tuple[int, ...] = ()      # 上限ちょうどに触れた帯の番号

    @property
    def on_edge(self) -> bool:
        return bool(self.low_edge or self.high_edge)


@dataclass(frozen=True)
class Report:
    ok: bool
    pending: tuple[Pending, ...]
    values: int
    bands: int
    units: int


@dataclass(frozen=True)
class Match:
    report: Report
    hits: tuple[Hit, ...]
    covers: tuple[Cover, ...]
    values: Values
    bands: Bands
    units: Units
    read_at: str
    host: str

    # -------------------------------------------------- 4 値と分母
    def by_result(self, result: str) -> tuple[Hit, ...]:
        return tuple(h for h in self.hits if h.result == result)

    @property
    def verdict(self) -> str:
        """全体の結果。1 行でも決まらなければ 決まらない(重なり)。"""
        self._guard()
        if self.by_result(RESULTS[2]):
            return RESULTS[2]
        if self.by_result(RESULTS[1]):
            return RESULTS[1]
        return RESULTS[0]

    def counts(self) -> dict[str, object]:
        """当たった率は単独では返さない。件数と分母の内訳を必ず併記する。"""
        four = {r: len(self.by_result(r)) for r in RESULTS}
        low = sum(1 for h in self.hits if h.low_edge)
        high = sum(1 for h in self.hits if h.high_edge)
        both = sum(1 for h in self.hits if h.low_edge and h.high_edge)
        points = sum(len(c.point_overlaps) for c in self.covers)
        out: dict[str, object] = {
            "値の表の行数": self.report.values,
            "帯の表の行数": self.report.bands,
            "単位の宣言の行数": self.report.units,
            "項目の数": len(self.covers),
            "4 値": four,
            "境界ちょうど": {"下限ちょうど": low, "上限ちょうど": high, "両方に触れた": both},
            "換算した値の行数": sum(1 for h in self.hits if h.converted),
            "点の重なり": points,
            "引いたか": ("引いた" if self.hits else
                         "引いていない(表が揃う前に止まったので 4 値は全て 0)"),
        }
        out["分母に含めたもの"] = (
            f"値の表の行数 {self.report.values} = 帯が 1 つに決まった {four[RESULTS[0]]}"
            f" + 当たる帯が無い {four[RESULTS[1]]}"
            f" + 決まらない(重なり){four[RESULTS[2]]} + 止まった {four[RESULTS[3]]}。"
            f"そのうち境界値ちょうどに触れた行は {low + high - both} 件"
            f"(下限ちょうど {low} / 上限ちょうど {high} / 両方 {both})。"
            f"帯の表の行数 {self.report.bands} は {len(self.covers)} 項目に分かれる")
        out["等号は宣言された欄だけ"] = (
            "当たり外れは帯の表に書かれた等号だけで決めた。以上・未満を補う既定も、"
            "以上と超を総当たりで並べる経路も無い(関数にも CLI にも引数が無い)")
        out["覆いの検算"] = (
            "項目ごとに、帯の連結の幅と帯ごとの個数の合計を突き合わせた"
            f"(点の重なり {points} 件を差し引いた上で一致しなければ止まる)")
        out["丸めない・寄せない"] = (
            "値を帯に入れるために四捨五入も切上げも切捨てもしない。最寄りの帯に寄せる経路も、"
            "端の帯に押し込む経路も無いので、当たらなければ「当たる帯が無い」で返る")
        return out

    def table(self) -> list[dict[str, object]]:
        """値の行ごとの結果。当たった率の欄は無い。"""
        return [{"対象": h.value.target, "項目": h.value.item, "値": str(h.value.value),
                 "値の種類": h.value.kind, "単位": h.value.unit,
                 "引いた値": str(h.used) if h.used is not None else "",
                 "換算": h.converted, "結果": h.result, "当たった帯": list(h.bands),
                 "返すもの": h.returns, "下限ちょうど": list(h.low_edge),
                 "上限ちょうど": list(h.high_edge), "出典": h.source,
                 "行番号": h.value.number}
                for h in self.hits]

    def edges(self) -> list[dict[str, object]]:
        """境界ちょうどに当たった行だけを別に並べる(件数の内訳がどの行から来たか)。"""
        return [{"対象": h.value.target, "項目": h.value.item, "値": str(h.value.value),
                 "引いた値": str(h.used) if h.used is not None else "",
                 "下限ちょうど": list(h.low_edge), "上限ちょうど": list(h.high_edge),
                 "結果": h.result, "行番号": h.value.number}
                for h in self.hits if h.on_edge]

    # -------------------------------------------------- 判定部分
    def judgement_bytes(self) -> bytes:
        """判定部分 = 引いた結果の表。時刻・絶対パス・ホスト名は入れない。"""
        self._guard()
        lines: list[str] = []
        for c in sorted(self.covers, key=lambda x: x.item):
            lines.append("\t".join(["覆い", c.item, str(c.bands), str(c.closed),
                                    "" if c.width is None else str(c.width),
                                    "|".join(f"{a}-{b}" for a, b in c.point_overlaps)]))
        for h in self.hits:
            lines.append("\t".join([h.value.item, h.value.target, str(h.value.value),
                                    h.value.kind, h.value.unit,
                                    "" if h.used is None else str(h.used), h.converted,
                                    h.result, "|".join(str(n) for n in h.bands), h.returns,
                                    "|".join(str(n) for n in h.low_edge),
                                    "|".join(str(n) for n in h.high_edge)]))
        return ("\n".join(lines) + "\n").encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.judgement_bytes()).hexdigest()

    def read_condition(self) -> dict[str, str]:
        return {READ_KEYS[0]: self.values.path, READ_KEYS[1]: self.bands.path,
                READ_KEYS[2]: self.units.path, READ_KEYS[3]: self.read_at,
                READ_KEYS[4]: self.host}

    def _guard(self) -> None:
        if not self.report.ok:
            raise RuntimeError("止まっているので引いた結果は無い。"
                               "report.pending の理由コードを見る")


def match(values: Values, bands: Bands, units: Units) -> Match:
    """値を帯に当てる。表が揃う前に止まったら 1 行も引かない。"""
    now = datetime.datetime.now().isoformat(timespec="seconds")
    host = platform.node()
    pending = list(bands.pending) + list(values.pending)

    def made(pend: tuple[Pending, ...], hits: tuple[Hit, ...] = (),
             covers: tuple[Cover, ...] = ()) -> Match:
        return Match(report=Report(not pend, pend, len(values.items), len(bands.items),
                                   len(units.items)),
                     hits=hits, covers=covers, values=values, bands=bands, units=units,
                     read_at=now, host=host)

    if pending:                      # 表が揃う前に止まる(1 行も引かない)
        return made(tuple(pending))

    # 項目ごとに、帯の連結を先に実測する(値を 1 つも見る前の L4 横断検算)
    covers: list[Cover] = []
    for item in sorted({b.item for b in bands.items}):
        u = units.of(item)
        if u is None:
            pending.append(Pending(STOP_REASONS[4], f"帯の表の項目 {item} が単位の宣言に無い"))
            continue
        for b in bands.of(item):
            for name, bound in (("下限", b.low), ("上限", b.high)):
                if bound is not None and not fits(bound, u.digits):
                    raise ReadError(f"帯の表 行 {b.number}: {name} {bound} が"
                                    f"小数の桁 {u.digits} に収まらない(丸めない)")
        c = cover_of(item, bands.of(item), u.step)
        covers.append(c)
        for no in c.reversed_bands:
            pending.append(Pending(STOP_REASONS[7], f"{item} 帯 {no}"))
        for a, b in c.range_overlaps:
            pending.append(Pending(STOP_REASONS[2], f"{item} 帯 {a} と帯 {b}"))
        for a, b in c.gaps:
            pending.append(Pending(STOP_REASONS[3], f"{item} 帯 {a} と帯 {b} のあいだ"))
        if not c.reversed_bands and not c.gaps and not c.range_overlaps and not c.ok:
            pending.append(Pending(STOP_REASONS[10],
                                   f"{item}: 覆いの幅 {c.width} / 帯ごとの個数の合計"
                                   f" {c.counted}"))

    hits: list[Hit] = []
    for v in values.ordered:
        u = units.of(v.item)
        if u is None:
            pending.append(Pending(STOP_REASONS[4], f"値の表 行 {v.number}: 項目 {v.item} が"
                                                    f"単位の宣言に無い"))
            hits.append(Hit(value=v, result=RESULTS[3]))
            continue
        mine = bands.of(v.item)
        if not mine:
            pending.append(Pending(STOP_REASONS[9], f"値の表 行 {v.number}: {v.item}"))
            hits.append(Hit(value=v, result=RESULTS[3]))
            continue
        used = u.convert(v.value, v.unit)
        if used is None:
            pending.append(Pending(STOP_REASONS[4], f"値の表 行 {v.number}: {v.item} は"
                                                    f"{u.unit} で引くが値は {v.unit}"))
            hits.append(Hit(value=v, result=RESULTS[3]))
            continue
        if not fits(used, u.digits):
            raise ReadError(f"値の表 行 {v.number}: {v.unit} から {u.unit} へ換算した値"
                            f" {used} が小数の桁 {u.digits} に収まらない(丸めない)")
        if any(c.item == v.item and not c.ok for c in covers):
            hits.append(Hit(value=v, result=RESULTS[3],
                            used=used, converted="" if v.unit == u.unit
                            else f"{v.unit} → {u.unit}"))
            continue
        inside = tuple(sorted(b.no for b in mine if b.holds(used, u.step)))
        low_edge = tuple(sorted(b.no for b in mine if b.low is not None and b.low == used))
        high_edge = tuple(sorted(b.no for b in mine if b.high is not None and b.high == used))
        if len(inside) == 1:
            result = RESULTS[0]
        elif not inside:
            result = RESULTS[1]
        else:
            result = RESULTS[2]
        won = next((b for b in mine if b.no == inside[0]), None) if len(inside) == 1 else None
        hits.append(Hit(value=v, result=result, used=used,
                        converted="" if v.unit == u.unit else f"{v.unit} → {u.unit}",
                        bands=inside, returns=won.returns if won else "",
                        source=won.source if won else "",
                        low_edge=low_edge, high_edge=high_edge))
    return made(tuple(pending), tuple(hits), tuple(covers))


def verify(values: Values, bands: Bands, units: Units) -> dict[str, object]:
    """2 回引いて sha256 を比べ、帯の表の行順を入れ替えても同じかを見て、覆いを検算する。"""
    first = match(values, bands, units)
    if not first.report.ok:
        return {"ok": False, "stage": "止まった(引いた結果は返さない)", **first.counts(),
                "pending": [p.as_dict() for p in first.report.pending]}
    if not bands.swap:
        raise ReadError("帯の表に入れ替え方(swap)が無いので verify は走らせない")
    second = match(values, bands, units)
    third = match(values, bands.swapped(bands.swap), units)
    pending: list[Pending] = []
    if first.sha256() != second.sha256():
        pending.append(Pending(STOP_REASONS[11], f"2 回目 {second.sha256()[:12]}"))
    if not (third.report.ok and first.sha256() == third.sha256()):
        pending.append(Pending(STOP_REASONS[12],
                               f"入れ替え方 {bands.swap} の表で {third.sha256()[:12]}"
                               if third.report.ok else
                               f"入れ替え方 {bands.swap} の表では止まった"))
    for c in first.covers:
        if not c.ok:
            pending.append(Pending(STOP_REASONS[10],
                                   f"{c.item}: 覆いの幅 {c.width} / 合計 {c.counted}"))
    out: dict[str, object] = {
        "ok": not pending, "引いた結果": first.verdict, "引いた回数": 2,
        "入れ替え方": bands.swap, "sha256": first.sha256(),
        "2 回目の sha256": second.sha256(),
        "入れ替えた表の sha256": third.sha256() if third.report.ok else "",
        "覆いの検算": [c.as_dict() for c in first.covers],
    }
    if pending:
        out["観測"] = ("同じ表から違うバイト列が出た(平均も多数決もしない。"
                       "どちらが正しいかも決めない)")
        out["pending"] = [p.as_dict() for p in pending]
    return out


# ------------------------------------------------------------------ ひな型

TEMPLATE_VALUES = [
    list(ATAI_COLUMNS),
    ["合成の区分A", "合成の月額(架空)", "100000", "金額", "円", "合成の値メモ(架空)L1"],
    ["合成の区分A", "合成の月額(架空)", "150000", "金額", "円", "合成の値メモ(架空)L2"],
]
TEMPLATE_BANDS = [
    list(OBI_COLUMNS),
    ["合成の月額(架空)", "1", "開いている", "", "100000", "未満", "合成の段1(架空)",
     "合成の帯メモ(架空)L1", "逆順"],
    ["合成の月額(架空)", "2", "100000", "以上", "200000", "未満", "合成の段2(架空)",
     "合成の帯メモ(架空)L2", ""],
    ["合成の月額(架空)", "3", "200000", "以上", "開いている", "", "合成の段3(架空)",
     "合成の帯メモ(架空)L3", ""],
]
TEMPLATE_UNITS = [
    list(TANI_COLUMNS),
    ["合成の月額(架空)", "金額", "円", "0", "千円", "1000"],
]


def write_csv(path: Path, rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    return path


def init(dest: str | Path) -> tuple[Path, Path, Path]:
    d = Path(dest)
    return (write_csv(d / "値の表.csv", TEMPLATE_VALUES),
            write_csv(d / "帯の表.csv", TEMPLATE_BANDS),
            write_csv(d / "単位の宣言.csv", TEMPLATE_UNITS))


# ------------------------------------------------------------------ CLI

def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def build_parser() -> argparse.ArgumentParser:
    """CLI は match / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = argparse.ArgumentParser(prog="band_edge", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in SUBCOMMANDS[:3]:
        p = sub.add_parser(name)
        p.add_argument("values")
        p.add_argument("bands")
        p.add_argument("units")
    sub.add_parser(SUBCOMMANDS[3]).add_argument("dest")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == "init":
        print("書いた: " + " / ".join(str(p) for p in init(a.dest)))
        return 0
    try:
        values, bands = Values.load(a.values), Bands.load(a.bands)
        units = Units.load(a.units)
        if a.cmd == "verify":
            out = verify(values, bands, units)
            _print(out)
            return 0 if out["ok"] else 3
        m = match(values, bands, units)
    except ReadError as e:
        print(f"表として読めない: {e}", file=sys.stderr)
        return 2
    if not m.report.ok:
        _print({"ok": False, "stage": "止まった(引いた結果は返さない)", **m.counts(),
                "pending": [p.as_dict() for p in m.report.pending]})
        return 3
    body: dict[str, object] = {"ok": True, "引いた結果": m.verdict, **m.counts()}
    if a.cmd == "match":
        body["値ごと"] = m.table()
        body["境界ちょうどの行"] = m.edges()
        body["sha256"] = m.sha256()
        body["読んだ条件"] = m.read_condition()
    _print(body)
    return 0 if m.verdict == RESULTS[0] else 3


if __name__ == "__main__":
    raise SystemExit(main())
