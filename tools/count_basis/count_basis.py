"""count_basis — 検証の報告に出る件数を、元の行 × 掛けた次元 × 確かめ方 の 3 層へ分ける。

**検証の報告に並ぶ「N 件一致」は、N 行を独立に確かめたという意味ではない。多くは「元の行 ×
掛けた次元」の積で、単位も確かめ方も検証ごとに別なのに、同じ 1 つの列に並ぶと足し合わせて
読める。**

この部品は、検証の台帳・元の行の台帳・掛けた次元の宣言表・登録表 2 枚(4 種 5 枚)から、検証
1 件ごとに 7 値(**分解できた / 分解が合わない / 件数が書かれていない / 次元の宣言が無い /
倍率が 1 行の持つ表の中に在る / 他の検証と元の行を共有している / 元の行の台帳に無い数表を
指している**)か、別枠 4 種(**出典が空 / 登録表に無いコード / 単位記号が無い / 件数が整数で
ない**)のどれか 1 つを付ける。

持たせていないものが規律になっている。

  - **出力に「検証の総件数」の欄が無い**(内訳は検証ごと・単位ごと・由来ごとに分けて出す。
    **単位の違う件数を足す関数そのものを置いていない**)
  - **確かめ方の強さを点数や順位にしない**(登録表に無いコードは別枠へ出すだけ。強い / 弱いの
    欄も、並べ替える引数も無い)
  - **独立かどうかを名前の近さで推測しない**(宣言表に無い次元は「宣言なし」。数表 id が似て
    いるかを見る経路が無い)
  - **割合・カバー率・%を出さない**(返るのは件数と分母の内訳だけ)
  - **原文の「通過」から件数を補完しない**(読めない件数の文字列は読めないまま別の値へ落ちる)
  - **検証を走らせない**(宣言された検証を実走する経路も、通信の経路も無い)
  - **検証が十分かを判定しない**(足りている / 足りないの欄が無い)
  - **計算の分岐数を数えない**(式も選択肢も読まない)
  - **2 経路の値そのものを突き合わせない**(入るのは件数と記号と出典だけ)
  - **実在の料率・金額を読まない**(値の列が無い)
  - **現在時刻を読まない**(日付の列も時刻の列も無い)
  - **入力を書き換えない**(verify が作る写しはメモリの中だけ)
  - **float を使わない**(件数・行数・倍率は整数、ほかは文字列)

入力は 4 種 5 枚。**どの行にも出典の欄が要る。**

検証の台帳(CSV)の列は 6。**検証 1 件が 1 行。**

    check_id         検証 id(同じ id が 2 行あると止まる)
    declared_count   宣言されている件数の文字列(**原文の表記のまま**。「7,050」「通過」など)
    unit             単位記号(登録表に無ければ別枠、空欄なら別枠か「件数が書かれていない」)
    tables           対象の数表 id の列挙(`;` 区切り。空欄は止まる)
    method           確かめ方コード(登録表に無ければ別枠)
    source           出典(ファイル名 + 行番号)。**空欄の行は別枠へ出す**

元の行の台帳(CSV)の列は 5。**数表 1 枚が 1 行。**

    table_id    数表 id(同じ id が 2 行あると止まる)
    rule_id     rule id
    rows        行数(0 以上の整数)
    origin      由来記号(`自前抽出` / `上流` / `照合専用`)
    source      出典。空欄は止まる

掛けた次元の宣言表(CSV)の列は 5。**1 つの次元が 1 行**(ヘッダだけでも読める)。

    check_id    検証 id(台帳に無い id は一覧へ出すだけで止めない)
    dim_name    次元名(同じ検証に同じ次元名が 2 行あると止まる)
    factor      倍率(1 以上の整数)
    place       倍率の在り所(`行として在る` / `1 行が持つ表の中に在る` / `計算で広げた`)
    source      出典。空欄は止まる

確かめ方コードの登録表(CSV)の列は 4。

    method     確かめ方コード
    meaning    意味(`機械の再計算` / `独立 2 経路` / `内部の隣接整合` / `公表値との突合` /
               `人の目視`)
    requires   その確かめ方が要求する欄(`次元の宣言` / `2 系統の由来` / `件数と単位`)
    source     登録の出典。空欄は止まる

単位記号の登録表(CSV)の列は 3。

    unit       単位記号
    meaning    意味(`セル` / `支部` / `行` / `項目` / `年度` / `回`)
    source     登録の出典。空欄は止まる

使い方:

    python count_basis.py init ひな型/
    python count_basis.py check 検証の台帳.csv 元の行の台帳.csv 次元の宣言表.csv 確かめ方.csv 単位.csv
    python count_basis.py layers 検証の台帳.csv 元の行の台帳.csv 次元の宣言表.csv 確かめ方.csv 単位.csv
    python count_basis.py verify 検証の台帳.csv 元の行の台帳.csv 次元の宣言表.csv 確かめ方.csv 単位.csv

終了コードは、別枠・分解が合わない検証・重なり・台帳に無い数表・逆向きの欠け・止まった行が
0 件のときだけ 0、在れば 3、表として読めなければ 2。**0 は「検証が厚い」ではなく「4 種 5 枚に
欠けが無い」の意味で、厚みはこの部品の終了コードにも出力にも出ない。**
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

CHECK_COLUMNS = ("check_id", "declared_count", "unit", "tables", "method", "source")
BASE_COLUMNS = ("table_id", "rule_id", "rows", "origin", "source")
DIM_COLUMNS = ("check_id", "dim_name", "factor", "place", "source")
METHOD_COLUMNS = ("method", "meaning", "requires", "source")
UNIT_COLUMNS = ("unit", "meaning", "source")

# 確かめ方の意味(**この 5 つの外に意味を作る経路が無い。強い / 弱いの順位も付けない**)
METHOD_MEANINGS = ("機械の再計算", "独立 2 経路", "内部の隣接整合", "公表値との突合", "人の目視")
# その確かめ方が要求する欄
REQUIRES = ("次元の宣言", "2 系統の由来", "件数と単位")
# 単位の意味(**件数の単位はこの 6 つの記号つきでしか受け取らない**)
UNIT_MEANINGS = ("セル", "支部", "行", "項目", "年度", "回")
# 元の行の由来
ORIGINS = ("自前抽出", "上流", "照合専用")
# 倍率の在り所(**2 番目だけが「行は増えていない」を意味する**)
PLACES = ("行として在る", "1 行が持つ表の中に在る", "計算で広げた")

# 検証 1 件に付く 7 値 + 別枠 4 種。**この 11 の外に値を作る経路が無い。**
KEKKA = (
    "分解できた(宣言件数 = 元の行数 × 倍率の積)",
    "分解が合わない",
    "件数が書かれていない",
    "次元の宣言が無い",
    "倍率が 1 行の持つ表の中に在る",
    "他の検証と元の行を共有している",
    "元の行の台帳に無い数表を指している",
    "別枠(出典が空)",
    "別枠(登録表に無いコード)",
    "別枠(単位記号が無い)",
    "別枠(件数が整数でない)",
)
NANA = KEKKA[:7]        # 7 値
BEKKA = KEKKA[7:]       # 別枠 4 種
# 重なりの印で上書きされる側の値(**別枠と「件数が書かれていない」と「台帳に無い数表」は
# 上書きしない** = 元の行が引けていない検証に重なりの印を付けない)
KASANARI_MOTO = (KEKKA[0], KEKKA[1], KEKKA[3], KEKKA[4])

SWAPS = ("逆順", "両端入れ替え", "1 つずらす")

STOP_REASONS = (
    # 表の側。1 件も数えずに止まる(8)
    "出典の欄が空",
    "同じ検証 id が検証の台帳に 2 行ある",
    "同じ数表 id が元の行の台帳に 2 行ある",
    "同じ検証 id と次元名の組が 2 行ある",
    "確かめ方が要求する欄が埋まっていない",
    "指している数表 id の欄が空",
    "同じ数表 id を 1 つの検証が 2 度指している",
    "次元名が空",
    # verify が見つける(3)
    "件数の合計が合わない", "2 回目の判定部分が不一致", "行順を入れ替えた表で出力が変わる",
)
TABLE_REASONS = STOP_REASONS[:8]
VERIFY_REASONS = STOP_REASONS[8:]

SUBCOMMANDS = ("layers", "check", "verify", "init")
SCOPE_KEYS = ("読んだ検証の台帳の絶対パス", "読んだ元の行の台帳の絶対パス",
              "読んだ次元の宣言表の絶対パス", "読んだ確かめ方の登録表の絶対パス",
              "読んだ単位記号の登録表の絶対パス")

NG_ID = set(" \t,|;")


class ReadError(Exception):
    """表として読めない(終了コード 2)。検証は 1 件も数えない。"""


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


def read_count(s: str) -> int | None:
    """宣言されている件数の文字列を整数として読む。

    **読めなければ None を返すだけで、補完も推測もしない。** 原文の「通過」「1.251」
    「2,295 / 2,411 / 2,562 の 3 年一致」は、どれも読めない件数として扱う(桁区切りの
    カンマだけは落とす)。
    """
    t = s.replace(",", "").strip()
    return int(t) if (t.isascii() and t.isdigit()) else None


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


# ------------------------------------------------------------ 単位記号の登録表


@dataclass(frozen=True)
class Unit:
    """単位記号 1 つ。**意味は人が書いた宣言で、記号の綴りから当てる経路が無い。**"""
    unit: str
    meaning: str
    source: str


@dataclass(frozen=True)
class Units:
    items: tuple[Unit, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Units":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"単位記号の登録表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Units":
        items: list[Unit] = []
        pending: list[Pending] = []
        seen: set[str] = set()
        for i, cell in _rows_of(text, UNIT_COLUMNS, "単位記号の登録表"):
            where = f"単位記号の登録表 行 {i}"
            if bad_id(cell["unit"]):
                raise ReadError(f"{where}: 単位記号が空欄か、区切り文字を含む"
                                f"({cell['unit'] or '空欄'})")
            if cell["meaning"] not in UNIT_MEANINGS:
                raise ReadError(f"{where}: 意味が登録の 6 つでない"
                                f"({cell['meaning'] or '空欄'})")
            if cell["unit"] in seen:
                raise ReadError(f"{where}: 同じ単位記号が 2 行ある({cell['unit']})")
            seen.add(cell["unit"])
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0], f"{where}: {cell['unit']}"))
            items.append(Unit(**cell))
        if not items:
            raise ReadError("単位記号の登録表に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    def of(self, unit: str) -> Unit | None:
        """**登録に無い記号には何も当てない**(None を返す = 別枠へ)。"""
        return next((u for u in self.items if u.unit == unit), None)

    def meaning_of(self, unit: str) -> str:
        u = self.of(unit)
        return u.meaning if u else ""

    def swapped(self, how: str) -> "Units":
        return Units(items=tuple(swap_rows(list(self.items), how)),
                     pending=self.pending, path=self.path)


# ------------------------------------------------------------ 確かめ方の登録表


@dataclass(frozen=True)
class Method:
    """確かめ方 1 つ。**順位も点数も持たない**(意味と、要求する欄だけ)。"""
    method: str
    meaning: str
    requires: str
    source: str


@dataclass(frozen=True)
class Methods:
    items: tuple[Method, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Methods":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"確かめ方の登録表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Methods":
        items: list[Method] = []
        pending: list[Pending] = []
        seen: set[str] = set()
        for i, cell in _rows_of(text, METHOD_COLUMNS, "確かめ方の登録表"):
            where = f"確かめ方の登録表 行 {i}"
            if bad_id(cell["method"]):
                raise ReadError(f"{where}: 確かめ方コードが空欄か、区切り文字を含む"
                                f"({cell['method'] or '空欄'})")
            if cell["meaning"] not in METHOD_MEANINGS:
                raise ReadError(f"{where}: 意味が登録の 5 つでない"
                                f"({cell['meaning'] or '空欄'})")
            if cell["requires"] not in REQUIRES:
                raise ReadError(f"{where}: 要求する欄が登録の 3 つでない"
                                f"({cell['requires'] or '空欄'})")
            if cell["method"] in seen:
                raise ReadError(f"{where}: 同じ確かめ方コードが 2 行ある({cell['method']})")
            seen.add(cell["method"])
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0], f"{where}: {cell['method']}"))
            items.append(Method(**cell))
        if not items:
            raise ReadError("確かめ方の登録表に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    def of(self, method: str) -> Method | None:
        return next((m for m in self.items if m.method == method), None)

    def meaning_of(self, method: str) -> str:
        m = self.of(method)
        return m.meaning if m else ""

    def swapped(self, how: str) -> "Methods":
        return Methods(items=tuple(swap_rows(list(self.items), how)),
                       pending=self.pending, path=self.path)


# ------------------------------------------------------------ 元の行の台帳


@dataclass(frozen=True)
class Base:
    """数表 1 枚。**行数と由来だけで、値(料率・金額)の列を持たない。**"""
    table_id: str
    rule_id: str
    rows: int
    origin: str
    source: str
    number: int = 0


@dataclass(frozen=True)
class Bases:
    items: tuple[Base, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Bases":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"元の行の台帳が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Bases":
        items: list[Base] = []
        pending: list[Pending] = []
        seen: set[str] = set()
        for i, cell in _rows_of(text, BASE_COLUMNS, "元の行の台帳"):
            where = f"元の行の台帳 行 {i}"
            if bad_id(cell["table_id"]):
                raise ReadError(f"{where}: 数表 id が空欄か、区切り文字を含む"
                                f"({cell['table_id'] or '空欄'})")
            if cell["origin"] not in ORIGINS:
                raise ReadError(f"{where}: 由来記号が登録の 3 つでない"
                                f"({cell['origin'] or '空欄'})")
            rows = whole(cell["rows"], "行数", where)
            if cell["table_id"] in seen:
                pending.append(Pending(STOP_REASONS[2], f"{where}: {cell['table_id']}"))
            seen.add(cell["table_id"])
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0], f"{where}: {cell['table_id']}"))
            items.append(Base(table_id=cell["table_id"], rule_id=cell["rule_id"],
                              rows=rows, origin=cell["origin"], source=cell["source"],
                              number=i))
        if not items:
            raise ReadError("元の行の台帳に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    def of(self, table_id: str) -> Base | None:
        return next((b for b in self.items if b.table_id == table_id), None)

    @property
    def ordered(self) -> tuple[Base, ...]:
        return tuple(sorted(self.items, key=lambda b: b.table_id))

    def rows_of(self, table_ids: tuple[str, ...]) -> int:
        """指している数表の行数を足す(**同じ単位の行数どうしだけを足す**)。"""
        return sum(b.rows for b in (self.of(t) for t in table_ids) if b is not None)

    def swapped(self, how: str) -> "Bases":
        return Bases(items=tuple(swap_rows(list(self.items), how)),
                     pending=self.pending, path=self.path)


# ------------------------------------------------------------ 掛けた次元の宣言表


@dataclass(frozen=True)
class Dim:
    """掛けた次元 1 つ。**在り所の記号を必ず持つ**(行として在るのか、1 行の中なのか)。"""
    check_id: str
    dim_name: str
    factor: int
    place: str
    source: str
    number: int = 0

    @property
    def inside(self) -> bool:
        """**倍率が 1 行の持つ表の中に在る**(= 行は増えていない)。"""
        return self.place == PLACES[1]


@dataclass(frozen=True)
class Dims:
    items: tuple[Dim, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Dims":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"掛けた次元の宣言表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Dims":
        items: list[Dim] = []
        pending: list[Pending] = []
        seen: set[tuple[str, str]] = set()
        for i, cell in _rows_of(text, DIM_COLUMNS, "掛けた次元の宣言表"):
            where = f"掛けた次元の宣言表 行 {i}"
            if bad_id(cell["check_id"]):
                raise ReadError(f"{where}: 検証 id が空欄か、区切り文字を含む"
                                f"({cell['check_id'] or '空欄'})")
            if cell["place"] not in PLACES:
                raise ReadError(f"{where}: 在り所記号が登録の 3 つでない"
                                f"({cell['place'] or '空欄'})")
            factor = whole(cell["factor"], "倍率", where, least=1)
            if not cell["dim_name"]:
                pending.append(Pending(STOP_REASONS[7], f"{where}: {cell['check_id']}"))
            key = (cell["check_id"], cell["dim_name"])
            if key in seen:
                pending.append(Pending(STOP_REASONS[3],
                                       f"{where}: {cell['check_id']} / "
                                       f"{cell['dim_name']}"))
            seen.add(key)
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0],
                                       f"{where}: {cell['check_id']} / "
                                       f"{cell['dim_name']}"))
            items.append(Dim(check_id=cell["check_id"], dim_name=cell["dim_name"],
                             factor=factor, place=cell["place"],
                             source=cell["source"], number=i))
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    def for_check(self, check_id: str) -> tuple[Dim, ...]:
        """その検証に宣言された次元(**宣言表に無い次元を足す経路が無い**)。"""
        return tuple(sorted((d for d in self.items if d.check_id == check_id),
                            key=lambda d: d.dim_name))

    @property
    def ordered(self) -> tuple[Dim, ...]:
        return tuple(sorted(self.items, key=lambda d: (d.check_id, d.dim_name)))

    def without(self, check_id: str, dim_name: str) -> "Dims":
        """次元 1 つを外した写し(**メモリの中だけ。入力の CSV は触らない**)。"""
        return Dims(items=tuple(d for d in self.items
                                if not (d.check_id == check_id
                                        and d.dim_name == dim_name)),
                    pending=self.pending, path=self.path)

    def swapped(self, how: str) -> "Dims":
        return Dims(items=tuple(swap_rows(list(self.items), how)),
                    pending=self.pending, path=self.path)


# ------------------------------------------------------------ 検証の台帳


@dataclass(frozen=True)
class Check:
    """検証 1 件。**宣言されている件数は原文の文字列のまま持つ。**"""
    check_id: str
    declared_count: str
    unit: str
    tables: tuple[str, ...]
    method: str
    source: str
    number: int = 0

    @property
    def declared(self) -> int | None:
        return read_count(self.declared_count)


@dataclass(frozen=True)
class Checks:
    items: tuple[Check, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Checks":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"検証の台帳が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Checks":
        items: list[Check] = []
        pending: list[Pending] = []
        seen: set[str] = set()
        for i, cell in _rows_of(text, CHECK_COLUMNS, "検証の台帳"):
            where = f"検証の台帳 行 {i}"
            if bad_id(cell["check_id"]):
                raise ReadError(f"{where}: 検証 id が空欄か、区切り文字を含む"
                                f"({cell['check_id'] or '空欄'})")
            tables = tuple(t.strip() for t in cell["tables"].split(";") if t.strip())
            if not tables:
                pending.append(Pending(STOP_REASONS[5], f"{where}: {cell['check_id']}"))
            if len(set(tables)) != len(tables):
                pending.append(Pending(STOP_REASONS[6], f"{where}: {cell['check_id']}"))
            if cell["check_id"] in seen:
                pending.append(Pending(STOP_REASONS[1], f"{where}: {cell['check_id']}"))
            seen.add(cell["check_id"])
            items.append(Check(check_id=cell["check_id"],
                               declared_count=cell["declared_count"],
                               unit=cell["unit"], tables=tables,
                               method=cell["method"], source=cell["source"],
                               number=i))
        if not items:
            raise ReadError("検証の台帳に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    def of(self, check_id: str) -> Check | None:
        return next((c for c in self.items if c.check_id == check_id), None)

    @property
    def ordered(self) -> tuple[Check, ...]:
        return tuple(sorted(self.items, key=lambda c: c.check_id))

    def retabled(self, check_id: str, tables: tuple[str, ...]) -> "Checks":
        """1 件の指す数表を書き換えた写し(**メモリの中だけ**)。"""
        return Checks(items=tuple(
            Check(check_id=c.check_id, declared_count=c.declared_count, unit=c.unit,
                  tables=tables if c.check_id == check_id else c.tables,
                  method=c.method, source=c.source, number=c.number)
            for c in self.items), pending=self.pending, path=self.path)

    def issues(self, methods: "Methods", bases: "Bases", dims: "Dims") -> list[Pending]:
        """確かめ方が要求する欄が埋まっているか(**登録に無いコードの行は見に行かない**)。"""
        out: list[Pending] = []
        for c in self.ordered:
            m = methods.of(c.method)
            if m is None:
                continue
            where = f"検証の台帳 行 {c.number}({c.check_id})"
            if m.requires == REQUIRES[0] and not dims.for_check(c.check_id):
                out.append(Pending(STOP_REASONS[4], f"{where}: {m.requires}"))
            if m.requires == REQUIRES[1]:
                origins = {b.origin for b in (bases.of(t) for t in c.tables)
                           if b is not None}
                if len(origins) < 2:
                    out.append(Pending(STOP_REASONS[4], f"{where}: {m.requires}"))
            if m.requires == REQUIRES[2] and not (c.declared_count and c.unit):
                out.append(Pending(STOP_REASONS[4], f"{where}: {m.requires}"))
        return out

    def swapped(self, how: str) -> "Checks":
        return Checks(items=tuple(swap_rows(list(self.items), how)),
                      pending=self.pending, path=self.path)


# ------------------------------------------------------------ 分ける


@dataclass(frozen=True)
class Judged:
    """検証 1 件の結果。**厚みの点数も順位も持たない。**"""
    check: Check
    result: str
    base_rows: int = 0
    factors: tuple[tuple[str, int, str], ...] = ()
    product: int = 0
    missing: tuple[str, ...] = ()
    shared: tuple[str, ...] = ()
    with_checks: tuple[str, ...] = ()

    @property
    def counted(self) -> bool:
        """7 値のどれかが付いたか(= 別枠でないか)。"""
        return self.result in NANA

    @property
    def inside(self) -> bool:
        return any(p == PLACES[1] for _, _, p in self.factors)

    @property
    def gap(self) -> str:
        """宣言件数と積の差。**どちらが正しいかは言わない**(値だけ)。"""
        d = self.check.declared
        return "" if (d is None or not self.factors) else str(d - self.product)

    def verdict(self) -> str:
        """その検証に付いた区分だけ(行数や積の値は入れない)。**写しで動いた件を数える単位。**"""
        return f"{self.result}:{'/'.join(self.shared)}:{'/'.join(self.missing)}"

    def line(self) -> str:
        return (f"{self.check.check_id}:{self.result}:{self.check.declared_count}"
                f":{self.check.unit}:{self.base_rows}"
                f":{'*'.join(f'{n}={f}@{p}' for n, f, p in self.factors)}"
                f":{self.product}:{self.gap}:{'/'.join(self.missing)}"
                f":{'/'.join(self.shared)}:{'/'.join(self.with_checks)}")

    def as_dict(self) -> dict[str, object]:
        return {"検証 id": self.check.check_id,
                "宣言されている件数(原文のまま)": self.check.declared_count,
                "単位記号": self.check.unit,
                "確かめ方コード": self.check.method,
                "指している数表 id": list(self.check.tables),
                "元の行数": self.base_rows,
                "掛けた次元": [{"次元名": n, "倍率": f, "倍率の在り所": p}
                               for n, f, p in self.factors],
                "元の行数 × 倍率の積": self.product,
                "宣言件数 - 積": self.gap,
                "台帳に無い数表 id": list(self.missing),
                "共有している数表 id": list(self.shared),
                "共有している相手の検証 id": list(self.with_checks),
                "判定": self.result,
                "出典": self.check.source}


def judge(check: Check, bases: Bases, dims: Dims, methods: Methods,
          units: Units) -> Judged:
    """検証 1 件に 7 値 + 別枠のどれか 1 つを付ける。**厚みは決めない。**

    上から順に見る。出典が空、確かめ方コードが登録表に無い、単位記号が登録表に無い行は別枠。
    単位記号が空なら、件数が整数として読めるかで別枠と「件数が書かれていない」に分かれる
    (**「通過」から件数を補完する経路が無い**)。そこから先で、はじめて元の行を引き、宣言
    された次元の倍率を掛け、宣言件数と比べる。
    """
    if not check.source:
        return Judged(check, KEKKA[7])
    if methods.of(check.method) is None:
        return Judged(check, KEKKA[8])
    if check.unit and units.of(check.unit) is None:
        return Judged(check, KEKKA[8])
    declared = check.declared
    if not check.unit:
        return Judged(check, KEKKA[9] if declared is not None else KEKKA[2])
    if declared is None:
        return Judged(check, KEKKA[10])
    missing = tuple(t for t in check.tables if bases.of(t) is None)
    if missing:
        return Judged(check, KEKKA[6], missing=missing)
    rows = bases.rows_of(check.tables)
    mine = dims.for_check(check.check_id)
    if not mine:
        return Judged(check, KEKKA[3], base_rows=rows)
    factors = tuple((d.dim_name, d.factor, d.place) for d in mine)
    product = rows
    for d in mine:
        product *= d.factor
    if any(d.inside for d in mine):
        return Judged(check, KEKKA[4], base_rows=rows, factors=factors,
                      product=product)
    hit = KEKKA[0] if product == declared else KEKKA[1]
    return Judged(check, hit, base_rows=rows, factors=factors, product=product)


@dataclass(frozen=True)
class Report:
    ok: bool
    pending: tuple[Pending, ...]
    checks: int
    bases: int
    dims: int
    methods: int
    units: int


@dataclass(frozen=True)
class Tally:
    report: Report
    judged: tuple[Judged, ...]
    checks: Checks
    bases: Bases
    dims: Dims
    methods: Methods
    units: Units

    # ---------------- 分母

    def check_denominator(self) -> int:
        return self.report.checks

    @property
    def counted_denominator(self) -> int:
        """7 値が付いた検証の数(別枠を外した数)。"""
        return sum(1 for j in self.judged if j.counted)

    def aside_denominator(self) -> int:
        return sum(1 for j in self.judged if not j.counted)

    # ---------------- 件数

    def eleven(self) -> dict[str, int]:
        return {k: sum(1 for j in self.judged if j.result == k) for k in KEKKA}

    def by_unit(self) -> list[dict[str, object]]:
        """単位ごとの内訳(**単位をまたいで足さない**。合計が検証の数に戻るのが検算)。

        台帳に出てくる単位記号を全て並べる(**登録表に無い記号も空欄も 1 行として出す**。
        外すと合計が合わなくなるので、欠けを黙って落とさない)。
        """
        out: list[dict[str, object]] = []
        for unit in sorted({c.unit for c in self.checks.items}):
            here = [j for j in self.judged if j.check.unit == unit]
            u = self.units.of(unit)
            out.append({"単位記号": unit or "(空欄)",
                        "登録表に在るか": "在る" if u else "無い",
                        "意味": u.meaning if u else "",
                        "検証の数": len(here),
                        "7 値 + 別枠": {k: sum(1 for j in here if j.result == k)
                                        for k in KEKKA}})
        return out

    def by_origin(self) -> list[dict[str, object]]:
        """由来ごとの内訳。**数えるのは元の行の台帳の行数**(合計がその行数に戻るのが検算)。"""
        out: list[dict[str, object]] = []
        for origin in sorted({b.origin for b in self.bases.items}):
            here = [b for b in self.bases.ordered if b.origin == origin]
            out.append({"由来記号": origin, "数表の枚数": len(here),
                        "数表 id": [b.table_id for b in here],
                        "行数の内訳": {b.table_id: b.rows for b in here}})
        return out

    # ---------------- 一覧

    def listed(self) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for k in KEKKA:
            here = [j for j in self.judged if j.result == k]
            out.append({"判定": k, "件数": len(here),
                        "検証": [j.as_dict() for j in here]})
        return out

    def shares(self) -> list[dict[str, object]]:
        """重なりの一覧。**共有している数表 id の集合をそのまま出す**(良し悪しは書かない)。"""
        return [{"検証 id": j.check.check_id,
                 "共有している数表 id": list(j.shared),
                 "共有している相手の検証 id": list(j.with_checks),
                 "宣言されている件数(原文のまま)": j.check.declared_count,
                 "単位記号": j.check.unit, "出典": j.check.source}
                for j in self.judged if j.result == KEKKA[5]]

    def inside_only(self) -> list[dict[str, object]]:
        """倍率が 1 行の持つ表の中に在る検証の一覧(= 行は増えていない)。"""
        return [{"検証 id": j.check.check_id,
                 "宣言されている件数(原文のまま)": j.check.declared_count,
                 "単位記号": j.check.unit, "元の行数": j.base_rows,
                 "掛けた次元": [{"次元名": n, "倍率": f, "倍率の在り所": p}
                                for n, f, p in j.factors],
                 "元の行数 × 倍率の積": j.product, "宣言件数 - 積": j.gap,
                 "出典": j.check.source}
                for j in self.judged if j.result == KEKKA[4]]

    def mismatched(self) -> list[dict[str, object]]:
        """分解が合わない検証の一覧。**差の値だけを出し、どちらが正しいかは書かない。**"""
        return [{"検証 id": j.check.check_id,
                 "宣言されている件数(原文のまま)": j.check.declared_count,
                 "元の行数": j.base_rows,
                 "掛けた次元": [{"次元名": n, "倍率": f, "倍率の在り所": p}
                                for n, f, p in j.factors],
                 "元の行数 × 倍率の積": j.product, "宣言件数 - 積": j.gap,
                 "出典": j.check.source}
                for j in self.judged if j.result == KEKKA[1]]

    def asides(self) -> list[dict[str, object]]:
        """別枠 4 種の一覧。**理由は当てず、原文の表記をそのまま出す。**"""
        return [{"検証 id": j.check.check_id, "判定": j.result,
                 "宣言されている件数(原文のまま)": j.check.declared_count,
                 "単位記号": j.check.unit, "確かめ方コード": j.check.method,
                 "出典": j.check.source}
                for j in self.judged if not j.counted]

    def dangling_dims(self) -> list[dict[str, object]]:
        """台帳に無い検証 id を指す次元の宣言(= 逆向きの欠け)。**止めずに並べる。**"""
        return [{"指している検証 id": d.check_id, "次元名": d.dim_name,
                 "倍率": d.factor, "倍率の在り所": d.place, "出典": d.source}
                for d in self.dims.ordered if self.checks.of(d.check_id) is None]

    def unused_bases(self) -> list[dict[str, object]]:
        """どの検証も指していない数表(**使われていないまま並べる**)。"""
        pointed = {t for c in self.checks.items for t in c.tables}
        return [{"数表 id": b.table_id, "rule id": b.rule_id, "行数": b.rows,
                 "由来記号": b.origin, "出典": b.source}
                for b in self.bases.ordered if b.table_id not in pointed]

    def stopped(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for p in self.report.pending:
            out[p.reason] = out.get(p.reason, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: STOP_REASONS.index(kv[0])))

    # ---------------- まとめ

    def counts(self) -> dict[str, object]:
        """件数を、分母の内訳つきで出す。**総件数も割合も点数も順位も返さない。**"""
        eleven = self.eleven()
        out: dict[str, object] = {
            "検証の台帳の行数": self.report.checks,
            "元の行の台帳の行数": self.report.bases,
            "掛けた次元の宣言表の行数": self.report.dims,
            "確かめ方の登録表の行数": self.report.methods,
            "単位記号の登録表の行数": self.report.units,
            "分母(検証の数)": self.check_denominator(),
            "分母(7 値が付いた検証の数)": self.counted_denominator,
            "分母(別枠の数)": self.aside_denominator(),
            "分母(台帳に出てくる単位記号の数)": len({c.unit for c in self.checks.items}),
            "7 値 + 別枠": eleven,
            "倍率が 1 行の持つ表の中に在る検証": eleven[KEKKA[4]],
            "他の検証と元の行を共有している検証": eleven[KEKKA[5]],
            "分解が合わない検証": eleven[KEKKA[1]],
            "台帳に無い数表を指している検証": eleven[KEKKA[6]],
            "台帳に無い検証 id を指す次元の宣言": len(self.dangling_dims()),
            "どの検証も指していない数表": len(self.unused_bases()),
            "単位ごと": self.by_unit(),
            "由来ごと": self.by_origin(),
            "理由別の止まった件数": self.stopped(),
            "読んだか": ("読んだ" if self.judged else
                         "読んでいない(分ける前に止まったので 7 値は全て 0)"),
        }
        out["分母に含めたもの"] = (
            f"検証の数 {self.check_denominator()} 件のうち、別枠が "
            f"{self.aside_denominator()} 件で、残る {self.counted_denominator} 件に "
            "7 値が付く。内訳は " + " + ".join(f"{k} {eleven[k]}" for k in NANA))
        out["件数の合計の検算"] = (
            f"7 値 + 別枠の合計 {sum(eleven.values())} / 検証の数 "
            f"{self.check_denominator()}(7 値 {sum(eleven[k] for k in NANA)} = "
            f"{self.counted_denominator} も同じ、単位ごとの内訳の合計 "
            f"{sum(int(r['検証の数']) for r in self.by_unit())} = 検証の数 も同じ、"
            f"由来ごとの内訳の合計 "
            f"{sum(int(r['数表の枚数']) for r in self.by_origin())} = 元の行の台帳の行数 "
            f"{self.report.bases} も同じ)")
        out["検証の総件数を出さない"] = (
            "この出力に総件数の欄が無い。単位の違う件数を足す関数も置いていないので、"
            "7,050 セルの検証と 1 件を目で見た検証を同じ列で足す経路が無い"
            "(内訳は検証ごと・単位ごと・由来ごとに分けて出す)")
        out["確かめ方に点数も順位も付けない"] = (
            "確かめ方コードに付くのは意味と、要求する欄だけ。強い / 弱いの欄も、並べ替える"
            "引数も無い(登録表に無いコードは別枠へ出すだけ)")
        out["独立かどうかを名前から推測しない"] = (
            "次元は宣言表に書かれた分だけを掛ける。数表 id の綴りが似ているかを見る経路が"
            "無く、宣言されていない次元は「宣言なし」のまま")
        out["割合もカバー率も出さない"] = (
            "返るのは件数と分母の内訳だけ。割合・カバー率・% にする経路も option も無い")
        out["通過から件数を補完しない"] = (
            "読めない件数の文字列は読めないまま別の値へ落ちる。原文の「通過」に件数を"
            "当てる経路が無い")
        out["検証を走らせない"] = (
            "宣言された検証を実走する経路も、通信の経路も無い。読むのは手元の 4 種 5 枚だけ")
        out["検証が十分かを判定しない"] = (
            "足りている / 足りないの欄が無い。何を分母にするかは台帳を持つ人が決める")
        out["計算の分岐数を数えない"] = (
            "式も選択肢も読まない。入るのは件数と記号と出典だけ")
        out["2 経路の値を突き合わせない"] = (
            "値の列が無いので、2 つの経路が同じ数字を出したかはこの部品では分からない")
        out["料率も金額も読まない"] = (
            "入力に値の列が無い。実在の料率・金額が入る欄そのものを持たない")
        out["鮮度も次回も出さない"] = (
            "入力に日付の列も時刻の列も無く、現在時刻を読む呼び出しも持たない")
        out["入力を書き換えない"] = (
            "verify が作る写し(次元を 1 つ外した表・指す数表を書き換えた表)はメモリの"
            "中だけで、入力の CSV には 1 文字も書かない")
        return out

    def judgement_bytes(self) -> bytes:
        """判定部分 = 検証ごとの区分と層。時刻・絶対パスは入れない。"""
        self._guard()
        lines = ["\t".join(["件", str(self.report.checks), str(self.report.bases),
                            str(self.report.dims), str(self.report.methods),
                            str(self.report.units)])]
        lines.extend(j.line() for j in self.judged)
        return ("\n".join(lines) + "\n").encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.judgement_bytes()).hexdigest()

    def read_condition(self) -> dict[str, str]:
        return dict(zip(SCOPE_KEYS, (self.checks.path, self.bases.path,
                                     self.dims.path, self.methods.path,
                                     self.units.path)))

    def _guard(self) -> None:
        if not self.report.ok:
            raise RuntimeError("止まっているので分けた検証は無い。"
                               "report.pending の理由コードを見る")


def count_basis(checks: Checks, bases: Bases, dims: Dims, methods: Methods,
                units: Units) -> Tally:
    """検証 1 件ごとに 7 値 + 別枠を付ける。

    4 種 5 枚のどれかが 1 行でも壊れていたら 1 件も数えない(7 値は全て 0)。
    """
    pending = (list(checks.pending) + list(bases.pending) + list(dims.pending)
               + list(methods.pending) + list(units.pending))
    pending.extend(checks.issues(methods, bases, dims))
    report = Report(not pending, tuple(pending), len(checks.items), len(bases.items),
                    len(dims.items), len(methods.items), len(units.items))
    if pending:                 # 1 件も数えずに止まる
        return Tally(report, (), checks, bases, dims, methods, units)

    first = [judge(c, bases, dims, methods, units) for c in checks.ordered]
    # 重なりの印。**自分より前の検証と数表 id が交わる側に付く**(前の検証の区分は動かさない)。
    judged: list[Judged] = []
    earlier: list[Judged] = []
    for j in first:
        if j.result in KASANARI_MOTO:
            mine = set(j.check.tables)
            hits = sorted({t for e in earlier for t in set(e.check.tables) & mine})
            if hits:
                with_checks = sorted(e.check.check_id for e in earlier
                                     if set(e.check.tables) & mine)
                j = Judged(j.check, KEKKA[5], base_rows=j.base_rows,
                           factors=j.factors, product=j.product,
                           shared=tuple(hits), with_checks=tuple(with_checks))
        judged.append(j)
        if j.result in KASANARI_MOTO or j.result == KEKKA[5]:
            earlier.append(j)
    return Tally(report, tuple(judged), checks, bases, dims, methods, units)


# ------------------------------------------------------------ verify


def moved_elsewhere(first: Tally, after: Tally, *keep: str) -> list[str]:
    """区分が動いた検証のうち、動くはずだった件でないものの検証 id。"""
    before = {j.check.check_id: j.verdict() for j in first.judged}
    now = {j.check.check_id: j.verdict() for j in after.judged}
    return sorted(cid for cid in before
                  if cid not in keep and before[cid] != now.get(cid, ""))


def drop_probe_plan(first: Tally) -> tuple[Judged, str] | None:
    """次元を 1 つ外す相手を決める(= 分解できた検証で、次元が 2 つ以上あるもの)。"""
    for j in first.judged:
        if j.result == KEKKA[0] and len(j.factors) >= 2:
            return j, j.factors[-1][0]
    return None


def drop_probe(checks: Checks, bases: Bases, dims: Dims, methods: Methods,
               units: Units, first: Tally) -> dict[str, object]:
    """**次元を 1 つ外すと、その検証の積が倍率の分だけ減って「分解が合わない」へ移る。**

    他の検証の区分と、単位ごと・由来ごとの内訳は 1 つも動かないこと。
    """
    plan = drop_probe_plan(first)
    if plan is None:
        return {"合うか": True, "外した次元": "",
                "観測": "分解できた検証で次元が 2 つ以上のものが無いので、この写しは作らない"}
    target, dim_name = plan
    dropped = next(d for d in dims.items
                   if d.check_id == target.check.check_id and d.dim_name == dim_name)
    after = count_basis(checks, bases, dims.without(target.check.check_id, dim_name),
                        methods, units)
    if not after.report.ok:
        return {"合うか": False, "外した次元": dim_name,
                "観測": "写しが止まった(理由コードを見る)"}
    moved = moved_elsewhere(first, after, target.check.check_id)
    now = next(j for j in after.judged
               if j.check.check_id == target.check.check_id)
    before_e, after_e = first.eleven(), after.eleven()
    unit_same = ([r["検証の数"] for r in first.by_unit()]
                 == [r["検証の数"] for r in after.by_unit()])
    origin_same = first.by_origin() == after.by_origin()
    ok = (now.result == KEKKA[1]
          and now.product * dropped.factor == target.product
          and not moved
          and before_e[KEKKA[0]] - 1 == after_e[KEKKA[0]]
          and before_e[KEKKA[1]] + 1 == after_e[KEKKA[1]]
          and unit_same and origin_same)
    return {"合うか": ok, "外した検証 id": target.check.check_id,
            "外した次元": dim_name, "外した倍率": dropped.factor,
            "積(前)": target.product, "積(後)": now.product,
            "積(後)× 外した倍率": now.product * dropped.factor,
            "移った先": now.result, "宣言件数 - 積(後)": now.gap,
            "ほかで動いた検証": moved,
            "7 値 + 別枠(後)": after_e,
            "単位ごとの検証の数は不変か": unit_same,
            "由来ごとの内訳は不変か": origin_same}


def share_probe_plan(first: Tally) -> tuple[str, tuple[str, ...]] | None:
    """重なりを 1 件増やす相手を決める(= いま重なっていない検証と、前に在る検証の数表)。"""
    pool = [j for j in first.judged if j.result in KASANARI_MOTO]
    if len(pool) < 2:
        return None
    donor = pool[0]
    targets = [j for j in pool[1:] if j.check.tables
               and not (set(j.check.tables) & set(donor.check.tables))]
    if not targets:
        return None
    return targets[-1].check.check_id, donor.check.tables


def share_probe(checks: Checks, bases: Bases, dims: Dims, methods: Methods,
                units: Units, first: Tally) -> dict[str, object]:
    """**2 つの検証が同じ数表 id を指すようにすると重なりが 1 増え、総件数の欄は現れない。**"""
    plan = share_probe_plan(first)
    if plan is None:
        return {"合うか": True, "書き換えた検証 id": "",
                "観測": "重なっていない検証が 2 件そろわないので、この写しは作らない"}
    target, tables = plan
    after = count_basis(checks.retabled(target, tables), bases, dims, methods, units)
    if not after.report.ok:
        return {"合うか": False, "書き換えた検証 id": target,
                "観測": "写しが止まった(理由コードを見る)"}
    moved = moved_elsewhere(first, after, target)
    before_e, after_e = first.eleven(), after.eleven()
    forbidden = sorted(k for k in after.counts()
                       if ("総件数" in k or "合計件数" in k or "カバー率" in k
                           or "順位" in k) and "出さない" not in k
                       and "付けない" not in k)
    now = next(j for j in after.judged if j.check.check_id == target)
    ok = (now.result == KEKKA[5]
          and before_e[KEKKA[5]] + 1 == after_e[KEKKA[5]]
          and not moved and not forbidden
          and sum(after_e.values()) == after.check_denominator())
    return {"合うか": ok, "書き換えた検証 id": target,
            "指すようにした数表 id": list(tables),
            "移った先": now.result,
            "共有している数表 id": list(now.shared),
            "重なり(前)": before_e[KEKKA[5]], "重なり(後)": after_e[KEKKA[5]],
            "ほかで動いた検証": moved,
            "総件数や順位の欄": forbidden,
            "7 値 + 別枠の合計(後)": sum(after_e.values())}


def verify(checks: Checks, bases: Bases, dims: Dims, methods: Methods,
           units: Units) -> dict[str, object]:
    """5 つ見る。二度走りの sha256 / 5 枚の行順の入れ替え / 3 通りの合計の検算 /
    次元を 1 つ外した写し / 同じ数表を指すようにした写し。"""
    first = count_basis(checks, bases, dims, methods, units)
    if not first.report.ok:
        return {"ok": False, "stage": "止まった(分けた検証は返さない)", **first.counts(),
                "pending": [p.as_dict() for p in first.report.pending]}
    second = count_basis(checks, bases, dims, methods, units)
    pending: list[Pending] = []
    if first.sha256() != second.sha256():
        pending.append(Pending(STOP_REASONS[9], f"2 回目 {second.sha256()[:12]}"))
    swapped: dict[str, str] = {}
    for how in SWAPS:
        third = count_basis(checks.swapped(how), bases.swapped(how), dims.swapped(how),
                            methods.swapped(how), units.swapped(how))
        swapped[how] = third.sha256() if third.report.ok else ""
        if not (third.report.ok and first.sha256() == third.sha256()):
            pending.append(Pending(STOP_REASONS[10],
                                   f"入れ替え方 {how} で {swapped[how] or '止まった'}"))
    eleven = first.eleven()
    if sum(eleven.values()) != first.check_denominator():
        pending.append(Pending(STOP_REASONS[8],
                               f"7 値 + 別枠の合計 {sum(eleven.values())} / 検証の数 "
                               f"{first.check_denominator()}"))
    inner = sum(eleven[k] for k in NANA)
    if inner != first.counted_denominator:
        pending.append(Pending(STOP_REASONS[8],
                               f"7 値 {inner} / 7 値が付いた検証 "
                               f"{first.counted_denominator}"))
    by_unit = sum(int(r["検証の数"]) for r in first.by_unit())
    if by_unit != first.check_denominator():
        pending.append(Pending(STOP_REASONS[8],
                               f"単位ごとの内訳の合計 {by_unit} / 検証の数 "
                               f"{first.check_denominator()}"))
    for k in KEKKA:
        inner_k = sum(int(r["7 値 + 別枠"][k]) for r in first.by_unit())
        if inner_k != eleven[k]:
            pending.append(Pending(STOP_REASONS[8],
                                   f"単位ごとの {k} の合計 {inner_k} / {eleven[k]}"))
    by_origin = sum(int(r["数表の枚数"]) for r in first.by_origin())
    if by_origin != first.report.bases:
        pending.append(Pending(STOP_REASONS[8],
                               f"由来ごとの内訳の合計 {by_origin} / 元の行の台帳の行数 "
                               f"{first.report.bases}"))
    out: dict[str, object] = {
        "ok": not pending, "読んだ回数": 2, "入れ替え方": list(SWAPS),
        "sha256": first.sha256(), "2 回目の sha256": second.sha256(),
        "入れ替えた 5 枚の sha256": swapped,
        "件数の検算": {"7 値 + 別枠": eleven, "合計": sum(eleven.values()),
                       "7 値": inner, "単位ごとの内訳の合計": by_unit,
                       "由来ごとの内訳の合計": by_origin,
                       "分母(検証の数)": first.check_denominator(),
                       "分母(7 値が付いた検証の数)": first.counted_denominator,
                       "分母(別枠の数)": first.aside_denominator(),
                       "元の行の台帳の行数": first.report.bases},
        "次元を 1 つ外した写し": drop_probe(checks, bases, dims, methods, units, first),
        "同じ数表を指すようにした写し": share_probe(checks, bases, dims, methods, units,
                                                   first),
    }
    for key in ("次元を 1 つ外した写し", "同じ数表を指すようにした写し"):
        if not out[key]["合うか"]:        # type: ignore[index]
            pending.append(Pending(STOP_REASONS[8], f"{key} の件数が合わない"))
            out["ok"] = False
    if pending:
        out["観測"] = ("同じ表から違うバイト列が出た、または件数が合わない(平均も多数決も"
                       "しない。どちらが正しいかも当てない)")
        out["pending"] = [p.as_dict() for p in pending]
    return out


# ------------------------------------------------------------ ひな型

T_STATUS = "合成の作業状況のメモ(架空)L1"
T_RANGE = "合成の収録範囲のメモ(架空)L1"
T_PLAN = "合成の次元のメモ(架空)L1"
T_WORD = "合成の登録のメモ(架空)L1"

TEMPLATE_CHECKS = [
    list(CHECK_COLUMNS),
    ["K01", "7,050", "cell", "T1", "M1", T_STATUS],
    ["K02", "通過", "", "T2", "M1", T_STATUS],
    ["K03", "47", "shibu", "T3;T8", "M2", T_STATUS],
]
TEMPLATE_BASES = [
    list(BASE_COLUMNS),
    ["T1", "料率表_甲", "141", ORIGINS[0], T_RANGE],
    ["T2", "等級表_甲", "3", ORIGINS[0], T_RANGE],
    ["T3", "料率表_乙", "47", ORIGINS[1], T_RANGE],
    ["T8", "照合用の料率表", "47", ORIGINS[2], T_RANGE],
]
TEMPLATE_DIMS = [
    list(DIM_COLUMNS),
    ["K01", "等級", "50", PLACES[1], T_PLAN],
    ["K02", "年", "3", PLACES[0], T_PLAN],
]
TEMPLATE_METHODS = [
    list(METHOD_COLUMNS),
    ["M1", METHOD_MEANINGS[0], REQUIRES[0], T_WORD],
    ["M2", METHOD_MEANINGS[1], REQUIRES[1], T_WORD],
]
TEMPLATE_UNITS = [
    list(UNIT_COLUMNS),
    ["cell", UNIT_MEANINGS[0], T_WORD],
    ["shibu", UNIT_MEANINGS[1], T_WORD],
]


def write_csv(path: Path, rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    return path


def init(dest: str | Path) -> tuple[Path, ...]:
    d = Path(dest)
    return (write_csv(d / "検証の台帳.csv", TEMPLATE_CHECKS),
            write_csv(d / "元の行の台帳.csv", TEMPLATE_BASES),
            write_csv(d / "掛けた次元の宣言表.csv", TEMPLATE_DIMS),
            write_csv(d / "確かめ方の登録表.csv", TEMPLATE_METHODS),
            write_csv(d / "単位記号の登録表.csv", TEMPLATE_UNITS))


# ------------------------------------------------------------ CLI

def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def build_parser() -> argparse.ArgumentParser:
    """CLI は layers / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = argparse.ArgumentParser(prog="count_basis",
                                 description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in SUBCOMMANDS[:3]:
        p = sub.add_parser(name)
        for arg in ("checks", "bases", "dims", "methods", "units"):
            p.add_argument(arg)
    sub.add_parser(SUBCOMMANDS[3]).add_argument("dest")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == "init":
        print("書いた: " + " / ".join(str(p) for p in init(a.dest)))
        return 0
    try:
        five = (Checks.load(a.checks), Bases.load(a.bases), Dims.load(a.dims),
                Methods.load(a.methods), Units.load(a.units))
        if a.cmd == "verify":
            out = verify(*five)
            _print(out)
            return 0 if out["ok"] else 3
        t = count_basis(*five)
    except ReadError as e:
        print(f"表として読めない: {e}", file=sys.stderr)
        return 2
    if not t.report.ok:
        _print({"ok": False, "stage": "止まった(分けた検証は返さない)", **t.counts(),
                "pending": [p.as_dict() for p in t.report.pending]})
        return 3
    body: dict[str, object] = {"ok": True, **t.counts()}
    if a.cmd == SUBCOMMANDS[0]:
        body["判定ごとの一覧"] = t.listed()
        body["重なりの一覧"] = t.shares()
        body["倍率が 1 行の持つ表の中に在る検証の一覧"] = t.inside_only()
        body["分解が合わない検証の一覧"] = t.mismatched()
        body["別枠の一覧"] = t.asides()
        body["台帳に無い検証 id を指す次元の宣言の一覧"] = t.dangling_dims()
        body["どの検証も指していない数表の一覧"] = t.unused_bases()
        body["sha256"] = t.sha256()
        body["読んだ条件"] = t.read_condition()
    _print(body)
    e = t.eleven()
    clean = (t.aside_denominator() == 0 and e[KEKKA[1]] == 0 and e[KEKKA[5]] == 0
             and e[KEKKA[6]] == 0 and not t.dangling_dims() and not t.stopped())
    return 0 if clean else 3


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
