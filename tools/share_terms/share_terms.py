"""share_terms — 配る前に、行ごとの許諾の宣言が揃っているかを数える。

**手元で引ける行と、外に出して配れる行は別で、配れる形かどうかは行の欄に書かれた許諾の
宣言からしか決まらない。**

この部品は、行の台帳・許諾の登録表・出典元の台帳・配布物の目録の 4 枚から、rule 1 件ごとに
5 値(**宣言が揃っている / 出すと宣言されたが欄が空 / 出さないと宣言された / 出す宣言が無い**
の 4 値 + 別枠 **登録表に無い許諾の名前**)を付け、空の欄を名前つきで並べる。
**配ってよいかを判定しない。許諾の名前を推測しない。規約の原文を取りに行かない。数えるだけだ。**

持たせていないものが規律になっている。

  - **許諾の名前を推測しない**(出典元の名前・URL の形・ファイル拡張子から名前を当てる経路が
    無い。登録表に無い名前は別枠に出し、「公式の公開情報だから大丈夫」の既定を持たない)
  - **配ってよいかを判定しない**(出力に 可否の欄も注意の欄も無い。返すのは宣言が揃っているか
    の 4 値 + 別枠だけで、配布の是非を指す語をこの部品は 1 つも持たない)
  - **規約の原文を取りに行かない・解釈しない**(ネットワーク経路も本文を読む経路も無い。
    要求する欄は登録表に宣言として渡される側で、この部品は規約の中身を知らない)
  - **帰属の文字列を生成しない**(verbatim の写しだけを扱い、出典元の名前から文面を組む経路が
    無い。空なら空のまま「欄が足りない」へ入れる)
  - **足りないのと決めていないのを同じ列に潰さない**(出すと宣言されたが欄が空の行と、出す
    宣言そのものが無い行は、別の値と別の行数で返る。これが骨の物理形)
  - **出さないと宣言された行を足りない側に数えない**(出す宣言が `出さない` の行は別の値に
    出て、欄が空の件数にも空の欄の一覧にも入らない)
  - **判断がつかない行は誰の宣言に由来するかを必ず併記する**(別枠の各行に出典の文字列を
    付け、出典が取れない行は入口で止める)
  - **出典元や上流の意図を推定しない**(なぜ名前が書かれていないか、なぜ出さないと宣言したかの
    理由欄が無い)
  - **件数を割合にしない**(件数と分母の内訳だけ。整備の度合いを返す経路が無い)
  - **順位も勧めも出さない**(どの出典元から埋めるべきかの順位欄が無い。埋める順は表を持つ人が
    決める)
  - **出典の欄が空の行は使わずに止まる**
  - **行を引かない・値を計算しない・式を評価しない・ファイルを配らない**(評価器も転送経路も
    持たない)
  - **入力表を書き換えず、行も宣言も生成しない**
  - **同じ入力には同じバイト列**(判定部分に時刻・絶対パス・ホスト名を入れない。行順にも依らない)
  - **数は整数だけ**(行数も件数も整数で、float を使う経路が無い)

入力は 4 つ。

行の台帳(CSV)の列は 10。**1 つの rule が 1 行**。

    table_id       数表 id
    rule_id        rule id(同じ id が 2 行あると止まる)
    rows           行数(0 以上の整数)
    origin_id      出典元 id(出典元の台帳に無い id は別枠の一覧へ)
    license_name   許諾の名前(空欄可。登録表に無ければ **別枠**)
    attribution    帰属の文字列(空欄可。verbatim の写しだけ)
    source_url     原文の URL(空欄可)
    fingerprint    版の指紋(空欄可。出典元の台帳と食い違えば止まる)
    share          外に出す宣言(`出す` / `出さない` / 空欄)
    source         出典(ファイル名 + 行番号)。空欄は止まる

許諾の登録表(CSV)の列は 5。**1 つの許諾の名前が 1 行**(ヘッダだけでも読める)。

    license_name        許諾の名前
    needs_attribution   帰属の文字列を要求すると宣言されているか(`要る` / `要らない`)
    needs_source_url    原文の URL を要求すると宣言されているか(同上)
    needs_fingerprint   版の指紋を要求すると宣言されているか(同上)
    declared_in         その宣言の出典。空欄は止まる

出典元の台帳(CSV)の列は 4。**1 つの出典元が 1 行**。

    origin_id            出典元 id
    fingerprint          取得した版の指紋
    got_on               取得日(`YYYY-MM-DD`)。**記録するだけで判定に使わない**
    license_written_at   許諾の名前が書かれている場所(ファイル名 + 行番号。空欄可)

配布物の目録(CSV)の列は 5。**1 つの (出す先, rule) の組が 1 行**。

    bundle_id   出す先 id(同じ id に 2 通りのファイル名があると止まる)
    file_name   出すファイル名
    rule_id     含む rule id(台帳に無い id は別枠の一覧へ)
    swap        入れ替え方(`逆順` / `両端入れ替え` / `1 つずらす`)。verify が使う宣言
    source      出典。空欄は止まる

使い方:

    python share_terms.py init ひな型/
    python share_terms.py check 行の台帳.csv 許諾の登録表.csv 出典元の台帳.csv 配布物の目録.csv
    python share_terms.py terms 行の台帳.csv 許諾の登録表.csv 出典元の台帳.csv 配布物の目録.csv
    python share_terms.py verify 行の台帳.csv 許諾の登録表.csv 出典元の台帳.csv 配布物の目録.csv

終了コードは、別枠・空の欄・逆向きの欠け・止まった行が 0 件のときだけ 0、在れば 3、表として
読めなければ 2。**0 は「配ってよい」ではなく「手元の 4 枚に欠けが無い」の意味で、配ってよいか
どうかはこの部品の終了コードにも出力にも出ない。**
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

DAICHOU_COLUMNS = ("table_id", "rule_id", "rows", "origin_id", "license_name",
                   "attribution", "source_url", "fingerprint", "share", "source")
KYODAKU_COLUMNS = ("license_name", "needs_attribution", "needs_source_url",
                   "needs_fingerprint", "declared_in")
SHUTTEN_COLUMNS = ("origin_id", "fingerprint", "got_on", "license_written_at")
MOKUROKU_COLUMNS = ("bundle_id", "file_name", "rule_id", "swap", "source")

# 許諾が要求すると宣言しうる欄。**この 3 つの外に増やす経路は入力側に無い。**
FIELDS = ("帰属の文字列", "原文の URL", "版の指紋")
FIELD_COLUMNS = {FIELDS[0]: "attribution", FIELDS[1]: "source_url",
                 FIELDS[2]: "fingerprint"}
NEEDS_COLUMNS = {FIELDS[0]: "needs_attribution", FIELDS[1]: "needs_source_url",
                 FIELDS[2]: "needs_fingerprint"}

DASU, DASANAI = "出す", "出さない"
SHARES = (DASU, DASANAI, "")
YESNO = ("要る", "要らない")

KEKKA = ("宣言が揃っている", "出すと宣言されたが欄が空", "出さないと宣言された",
         "出す宣言が無い", "登録表に無い許諾の名前")
YOTSU = KEKKA[:4]          # 4 値
BEKKA = KEKKA[4]           # 別枠 1 種

SWAPS = ("逆順", "両端入れ替え", "1 つずらす")

STOP_REASONS = (
    # 表の側。1 行も数えずに止まる(10)
    "出典の欄が空",
    "同じ rule id が台帳に 2 行ある",
    "同じ rule id が 2 つの数表に跨っている",
    "同じ出す先 id と rule id の組が目録に 2 行ある",
    "同じ出す先 id に 2 通りのファイル名が書かれている",
    "出さないと宣言された行が配布物の目録に載っている",
    "出す宣言の無い行が配布物の目録に載っている",
    "行の版の指紋が出典元の台帳の指紋と食い違う",
    "許諾の名前が書かれているのに出典元の台帳にその場所が無い",
    "許諾の名前が空なのに出典元の台帳に場所が書かれている",
    # verify が見つける(3)
    "件数の合計が合わない", "2 回目の判定部分が不一致", "行順を入れ替えた表で出力が変わる",
)
TABLE_REASONS = STOP_REASONS[:10]
VERIFY_REASONS = STOP_REASONS[10:]

SUBCOMMANDS = ("terms", "check", "verify", "init")
SCOPE_KEYS = ("読んだ行の台帳の絶対パス", "読んだ許諾の登録表の絶対パス",
              "読んだ出典元の台帳の絶対パス", "読んだ配布物の目録の絶対パス")

NG_ID = set(" \t,|")
MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


class ReadError(Exception):
    """表として読めない(終了コード 2)。rule は 1 件も数えない。"""


@dataclass(frozen=True)
class Pending:
    reason: str
    detail: str = ""

    def as_dict(self) -> dict[str, str]:
        return {"理由コード": self.reason, "どこ": self.detail}


def bad_id(s: str) -> bool:
    return (not s) or any(ch in NG_ID for ch in s)


def check_date(s: str) -> None:
    """`YYYY-MM-DD` の形かだけを見る。**時計を読む経路が無い**(引数は必ず文字列)。"""
    parts = s.split("-")
    if len(parts) != 3 or [len(p) for p in parts] != [4, 2, 2] \
            or not all(p.isascii() and p.isdigit() for p in parts):
        raise ReadError(f"取得日が YYYY-MM-DD の形でない: {s or '空欄'}")
    y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
    if not 1 <= m <= 12:
        raise ReadError(f"月が 1〜12 でない: {s}")
    leap = y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
    last = 29 if (m == 2 and leap) else MONTH_DAYS[m - 1]
    if not 1 <= d <= last:
        raise ReadError(f"その月に無い日付: {s}")


def whole(s: str, what: str, where: str) -> int:
    """0 以上の整数として読む。小数も符号も受け取らない(**float を使う経路が無い**)。"""
    if not (s.isascii() and s.isdigit()):
        raise ReadError(f"{where}: {what}が 0 以上の整数でない({s or '空欄'})")
    return int(s)


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


# ------------------------------------------------------------ 許諾の登録表


@dataclass(frozen=True)
class License:
    """許諾 1 つ。**要求する欄は人が書いた宣言を持つだけで、道具が当てる経路が無い。**"""
    name: str
    needs: tuple[str, ...]
    declared_in: str

    def missing_in(self, row: "Row") -> tuple[str, ...]:
        """その許諾が要求すると宣言された欄のうち、行で空のもの(名前のまま返す)。"""
        return tuple(f for f in self.needs if not getattr(row, FIELD_COLUMNS[f]))


@dataclass(frozen=True)
class Registry:
    items: tuple[License, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Registry":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"許諾の登録表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Registry":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in KYODAKU_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("許諾の登録表に " + " / ".join(lack) + " の列が無い")
        items: list[License] = []
        pending: list[Pending] = []
        seen: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in KYODAKU_COLUMNS}
            where = f"許諾の登録表 行 {i}"
            if bad_id(cell["license_name"]):
                raise ReadError(f"{where}: 許諾の名前が空欄か、区切り文字を含む"
                                f"({cell['license_name'] or '空欄'})")
            for field in FIELDS:
                if cell[NEEDS_COLUMNS[field]] not in YESNO:
                    raise ReadError(f"{where}: {field}を要求するかが登録の 2 つでない"
                                    f"({cell[NEEDS_COLUMNS[field]] or '空欄'})")
            if cell["license_name"] in seen:
                raise ReadError(f"{where}: 同じ許諾の名前が 2 行ある"
                                f"({cell['license_name']})")
            seen.add(cell["license_name"])
            if not cell["declared_in"]:
                pending.append(Pending(STOP_REASONS[0],
                                       f"{where}: {cell['license_name']}"))
            items.append(License(
                name=cell["license_name"],
                needs=tuple(f for f in FIELDS
                            if cell[NEEDS_COLUMNS[f]] == YESNO[0]),
                declared_in=cell["declared_in"]))
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(x.name for x in self.items))

    def of(self, name: str) -> License | None:
        """**登録に無い名前には何も当てない**(None を返す = 別枠へ)。"""
        return next((x for x in self.items if x.name == name), None)

    def without(self, name: str) -> "Registry":
        """許諾 1 件を外した写し(verify が使う。入力には書かない)。"""
        return Registry(items=tuple(x for x in self.items if x.name != name),
                        pending=self.pending, path=self.path)

    def swapped(self, how: str) -> "Registry":
        return Registry(items=tuple(swap_rows(list(self.items), how)),
                        pending=self.pending, path=self.path)


# ------------------------------------------------------------ 出典元の台帳


@dataclass(frozen=True)
class Origin:
    """出典元 1 つ。**取得日は記録するだけで判定に 1 度も使わない。**"""
    origin_id: str
    fingerprint: str
    got_on: str
    license_written_at: str


@dataclass(frozen=True)
class Origins:
    items: tuple[Origin, ...]
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Origins":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"出典元の台帳が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Origins":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in SHUTTEN_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("出典元の台帳に " + " / ".join(lack) + " の列が無い")
        items: list[Origin] = []
        seen: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in SHUTTEN_COLUMNS}
            where = f"出典元の台帳 行 {i}"
            if bad_id(cell["origin_id"]):
                raise ReadError(f"{where}: 出典元 id が空欄か、区切り文字を含む"
                                f"({cell['origin_id'] or '空欄'})")
            if cell["origin_id"] in seen:
                raise ReadError(f"{where}: 同じ出典元 id が 2 行ある"
                                f"({cell['origin_id']})")
            seen.add(cell["origin_id"])
            check_date(cell["got_on"])
            items.append(Origin(origin_id=cell["origin_id"],
                                fingerprint=cell["fingerprint"],
                                got_on=cell["got_on"],
                                license_written_at=cell["license_written_at"]))
        if not items:
            raise ReadError("出典元の台帳に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), path=path)

    @property
    def ordered(self) -> tuple[Origin, ...]:
        return tuple(sorted(self.items, key=lambda o: o.origin_id))

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(o.origin_id for o in self.items))

    def of(self, origin_id: str) -> Origin | None:
        return next((o for o in self.ordered if o.origin_id == origin_id), None)

    def swapped(self, how: str) -> "Origins":
        return Origins(items=tuple(swap_rows(list(self.items), how)), path=self.path)


# ------------------------------------------------------------ 行の台帳


@dataclass(frozen=True)
class Row:
    """台帳 1 行 = 1 rule。**帰属の文字列は写しだけで、組み立てる経路が無い。**"""
    table_id: str
    rule_id: str
    rows: int
    origin_id: str
    license_name: str
    attribution: str
    source_url: str
    fingerprint: str
    share: str
    source: str
    number: int = 0

    @property
    def declared_out(self) -> bool:
        return self.share == DASANAI

    def issues(self, origins: Origins) -> tuple[Pending, ...]:
        where = f"行の台帳 行 {self.number}({self.rule_id})"
        out: list[Pending] = []
        if not self.source:
            out.append(Pending(STOP_REASONS[0], where))
        origin = origins.of(self.origin_id)
        if origin is None:
            return tuple(out)       # 逆向きの欠けは止めずに一覧へ出す
        if self.fingerprint and origin.fingerprint \
                and self.fingerprint != origin.fingerprint:
            out.append(Pending(STOP_REASONS[7],
                               f"{where}: 行 {self.fingerprint} / 台帳 "
                               f"{origin.fingerprint}"))
        if self.license_name and not origin.license_written_at:
            out.append(Pending(STOP_REASONS[8],
                               f"{where}: {self.license_name} / {self.origin_id}"))
        if not self.license_name and origin.license_written_at:
            out.append(Pending(STOP_REASONS[9],
                               f"{where}: {self.origin_id} = "
                               f"{origin.license_written_at}"))
        return tuple(out)


@dataclass(frozen=True)
class Ledger:
    items: tuple[Row, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Ledger":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"行の台帳が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Ledger":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in DAICHOU_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("行の台帳に " + " / ".join(lack) + " の列が無い")
        items: list[Row] = []
        pending: list[Pending] = []
        seen: dict[str, str] = {}
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in DAICHOU_COLUMNS}
            where = f"行の台帳 行 {i}"
            for key, name in (("table_id", "数表 id"), ("rule_id", "rule id"),
                              ("origin_id", "出典元 id")):
                if bad_id(cell[key]):
                    raise ReadError(f"{where}: {name}が空欄か、区切り文字を含む"
                                    f"({cell[key] or '空欄'})")
            if cell["share"] not in SHARES:
                raise ReadError(f"{where}: 外に出す宣言が登録の 2 つと空欄のどれでもない"
                                f"({cell['share']})")
            count = whole(cell["rows"], "行数", where)
            if cell["rule_id"] in seen:
                code = STOP_REASONS[1] if seen[cell["rule_id"]] == cell["table_id"] \
                    else STOP_REASONS[2]
                pending.append(Pending(code, f"{where}: {cell['rule_id']}"))
            seen[cell["rule_id"]] = cell["table_id"]
            items.append(Row(table_id=cell["table_id"], rule_id=cell["rule_id"],
                             rows=count, origin_id=cell["origin_id"],
                             license_name=cell["license_name"],
                             attribution=cell["attribution"],
                             source_url=cell["source_url"],
                             fingerprint=cell["fingerprint"], share=cell["share"],
                             source=cell["source"], number=i))
        if not items:
            raise ReadError("行の台帳に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    @property
    def ordered(self) -> tuple[Row, ...]:
        """数表 id → rule id の順(行順に依らない = 入れ替えても同じ出力)。"""
        return tuple(sorted(self.items, key=lambda r: (r.table_id, r.rule_id)))

    @property
    def origin_ids(self) -> tuple[str, ...]:
        return tuple(sorted({r.origin_id for r in self.items}))

    @property
    def total_rows(self) -> int:
        return sum(r.rows for r in self.items)

    def of(self, rule_id: str) -> Row | None:
        return next((r for r in self.ordered if r.rule_id == rule_id), None)

    def blanked(self, rule_id: str, field: str) -> "Ledger":
        """ある行の 1 欄だけを空にした写し(verify が使う。入力には書かない)。"""
        column = FIELD_COLUMNS[field]
        return Ledger(items=tuple(
            (r if r.rule_id != rule_id else
             Row(**{**{k: getattr(r, k) for k in r.__dataclass_fields__},
                    column: ""}))
            for r in self.items), pending=self.pending, path=self.path)

    def swapped(self, how: str) -> "Ledger":
        return Ledger(items=tuple(swap_rows(list(self.items), how)),
                      pending=self.pending, path=self.path)


# ------------------------------------------------------------ 配布物の目録


@dataclass(frozen=True)
class Listing:
    bundle_id: str
    file_name: str
    rule_id: str
    source: str
    number: int = 0

    def issues(self) -> tuple[Pending, ...]:
        where = (f"配布物の目録 行 {self.number}"
                 f"({self.bundle_id} ← {self.rule_id})")
        return (Pending(STOP_REASONS[0], where),) if not self.source else ()


@dataclass(frozen=True)
class Bundles:
    items: tuple[Listing, ...]
    pending: tuple[Pending, ...] = ()
    swap: str = ""
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Bundles":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"配布物の目録が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Bundles":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in MOKUROKU_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("配布物の目録に " + " / ".join(lack) + " の列が無い")
        items: list[Listing] = []
        pending: list[Pending] = []
        seen: set[tuple[str, str]] = set()
        names: dict[str, str] = {}
        swaps: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in MOKUROKU_COLUMNS}
            where = f"配布物の目録 行 {i}"
            for key, name in (("bundle_id", "出す先 id"), ("rule_id", "rule id")):
                if bad_id(cell[key]):
                    raise ReadError(f"{where}: {name}が空欄か、区切り文字を含む"
                                    f"({cell[key] or '空欄'})")
            if not cell["file_name"]:
                raise ReadError(f"{where}: 出すファイル名が空欄")
            if cell["swap"]:
                swaps.add(cell["swap"])
            pair = (cell["bundle_id"], cell["rule_id"])
            if pair in seen:
                pending.append(Pending(STOP_REASONS[3],
                                       f"{where}: {' ← '.join(pair)}"))
            seen.add(pair)
            if names.setdefault(cell["bundle_id"], cell["file_name"]) \
                    != cell["file_name"]:
                pending.append(Pending(STOP_REASONS[4],
                                       f"{where}: {cell['bundle_id']} = "
                                       f"{names[cell['bundle_id']]} / "
                                       f"{cell['file_name']}"))
            items.append(Listing(bundle_id=cell["bundle_id"],
                                 file_name=cell["file_name"],
                                 rule_id=cell["rule_id"], source=cell["source"],
                                 number=i))
        if not items:
            raise ReadError("配布物の目録に行が無い(ヘッダだけ)")
        if len(swaps) > 1:
            raise ReadError("入れ替え方の宣言が 2 通りある: "
                            + " / ".join(sorted(swaps)))
        how = swaps.pop() if swaps else ""
        if how and how not in SWAPS:
            raise ReadError(f"登録されていない入れ替え方: {how}")
        for x in items:
            pending.extend(x.issues())
        return cls(items=tuple(items), pending=tuple(pending), swap=how, path=path)

    @property
    def ordered(self) -> tuple[Listing, ...]:
        return tuple(sorted(self.items, key=lambda x: (x.bundle_id, x.rule_id)))

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(sorted({x.bundle_id for x in self.items}))

    def rules_of(self, bundle_id: str) -> tuple[str, ...]:
        return tuple(x.rule_id for x in self.ordered if x.bundle_id == bundle_id)

    def file_of(self, bundle_id: str) -> str:
        return next(x.file_name for x in self.ordered if x.bundle_id == bundle_id)

    def swapped(self, how: str) -> "Bundles":
        return Bundles(items=tuple(swap_rows(list(self.items), how)),
                       pending=self.pending, swap=self.swap, path=self.path)


# ------------------------------------------------------------ 突き合わせる


@dataclass(frozen=True)
class Judged:
    """rule 1 件の結果。**空の欄と、出す宣言が無いことを 1 つに潰す経路が無い。**"""
    row: Row
    result: str
    needs: tuple[str, ...] = ()      # その許諾が要求すると宣言された欄
    missing: tuple[str, ...] = ()    # そのうち行で空のもの

    @property
    def settled(self) -> bool:
        """許諾の名前が登録表に在るか(= 要求される欄が分かる状態か)。"""
        return self.result != BEKKA

    def line(self) -> str:
        return (f"{self.row.table_id}/{self.row.rule_id}:{self.result}"
                f":{self.row.rows}:{self.row.license_name}"
                f":{'|'.join(self.needs)}/{'|'.join(self.missing)}")

    def as_dict(self) -> dict[str, object]:
        return {"数表 id": self.row.table_id, "rule id": self.row.rule_id,
                "行数": self.row.rows, "出典元 id": self.row.origin_id,
                "許諾の名前": self.row.license_name, "外に出す宣言": self.row.share,
                "判定": self.result, "要求される欄": list(self.needs),
                "空の欄": list(self.missing), "出典": self.row.source}


def judge(row: Row, registry: Registry) -> Judged:
    """rule 1 件に 5 値のどれか 1 つを付ける。**配ってよいかは決めない。**

    上から順に見る。出す宣言が `出さない` の行はここで終わり(要求される欄を見に行く経路が
    無い)。宣言そのものが無い行も、欄が空の行とは別の値に出す。出すと宣言された行だけが、
    登録表に書かれた「要求すると宣言された欄」と突き合わされる。
    """
    if row.declared_out:
        return Judged(row, KEKKA[2])
    if row.share != DASU:
        return Judged(row, KEKKA[3])
    license_ = registry.of(row.license_name)
    if license_ is None:
        return Judged(row, BEKKA)
    missing = license_.missing_in(row)
    return Judged(row, KEKKA[1] if missing else KEKKA[0], license_.needs, missing)


@dataclass(frozen=True)
class Report:
    ok: bool
    pending: tuple[Pending, ...]
    ledger: int
    registry: int
    origins: int
    bundles: int


@dataclass(frozen=True)
class Tally:
    report: Report
    judged: tuple[Judged, ...]
    ledger: Ledger
    registry: Registry
    origins: Origins
    bundles: Bundles

    # ---------------- 分母

    def rule_denominator(self) -> int:
        return self.report.ledger

    @property
    def settled_denominator(self) -> int:
        """許諾の名前が登録表に在る rule の数(別枠を外した数)。"""
        return sum(1 for j in self.judged if j.settled)

    def aside_denominator(self) -> int:
        return sum(1 for j in self.judged if not j.settled)

    # ---------------- 件数と行数

    def five(self) -> dict[str, int]:
        return {k: sum(1 for j in self.judged if j.result == k) for k in KEKKA}

    def rows_by_result(self) -> dict[str, int]:
        return {k: sum(j.row.rows for j in self.judged if j.result == k)
                for k in KEKKA}

    def total_rows(self) -> int:
        return self.ledger.total_rows

    def by_origin(self) -> list[dict[str, object]]:
        """出典元ごとの内訳(合計が全体に戻るかが二重集計の検算になる)。

        台帳に出てくる出典元を全て並べる(出典元の台帳に無い id も 1 行として出す。
        **外すと合計が合わなくなるので、欠けを黙って落とさない。**)
        """
        out: list[dict[str, object]] = []
        for origin_id in self.ledger.origin_ids:
            here = [j for j in self.judged if j.row.origin_id == origin_id]
            known = self.origins.of(origin_id)
            out.append({"出典元 id": origin_id,
                        "出典元の台帳に在るか": "在る" if known else "無い",
                        "許諾の名前が書かれている場所":
                            known.license_written_at if known else "",
                        "rule の数": len(here),
                        "行数": sum(j.row.rows for j in here),
                        "5 値": {k: sum(1 for j in here if j.result == k)
                                 for k in KEKKA}})
        return out

    def by_table(self) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for table_id in sorted({r.table_id for r in self.ledger.items}):
            here = [j for j in self.judged if j.row.table_id == table_id]
            out.append({"数表 id": table_id, "rule の数": len(here),
                        "行数": sum(j.row.rows for j in here),
                        "5 値": {k: sum(1 for j in here if j.result == k)
                                 for k in KEKKA}})
        return out

    # ---------------- 一覧

    def listed(self) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for k in KEKKA:
            here = [j for j in self.judged if j.result == k]
            out.append({"判定": k, "件数": len(here),
                        "行数": sum(j.row.rows for j in here),
                        "rule": [j.as_dict() for j in here]})
        return out

    def empty_fields(self) -> list[dict[str, object]]:
        """**空の欄の名前つき一覧**(rule → 許諾の名前 → 足りない欄)。文面は作らない。"""
        return [{"rule id": j.row.rule_id, "行数": j.row.rows,
                 "許諾の名前": j.row.license_name,
                 "要求される欄": list(j.needs), "足りない欄": list(j.missing),
                 "許諾の宣言の出典":
                     (self.registry.of(j.row.license_name) or
                      License("", (), "")).declared_in,
                 "行の出典": j.row.source}
                for j in self.judged if j.result == KEKKA[1]]

    def empty_field_count(self) -> int:
        return sum(len(j.missing) for j in self.judged)

    def unregistered_licenses(self) -> list[dict[str, object]]:
        """登録表に無い許諾の名前を指す行。**別枠に出すだけで、名前を当てない。**"""
        return [{"rule id": j.row.rule_id, "行数": j.row.rows,
                 "書かれていた許諾の名前": j.row.license_name or "(空欄)",
                 "出典元 id": j.row.origin_id, "出典": j.row.source}
                for j in self.judged if j.result == BEKKA]

    def unknown_origins(self) -> list[dict[str, object]]:
        """出典元の台帳に無い出典元 id を指す行(= 逆向きの欠け)。止めずに並べる。"""
        return [{"rule id": j.row.rule_id, "行数": j.row.rows,
                 "指している出典元 id": j.row.origin_id, "判定": j.result,
                 "出典": j.row.source}
                for j in self.judged if self.origins.of(j.row.origin_id) is None]

    def dangling_rules(self) -> list[dict[str, object]]:
        """目録に載っているのに台帳に無い rule。**止めずに並べる。**"""
        return [{"出す先 id": x.bundle_id, "出すファイル名": x.file_name,
                 "載っている rule id": x.rule_id, "出典": x.source}
                for x in self.bundles.ordered if self.ledger.of(x.rule_id) is None]

    def attributions(self) -> list[dict[str, object]]:
        """配布物ごとに要る帰属の文字列(verbatim のまま重複を畳む)。**文面は作らない。**"""
        out: list[dict[str, object]] = []
        for bundle_id in self.bundles.ids:
            rules = self.bundles.rules_of(bundle_id)
            texts: list[str] = []
            unsettled: list[str] = []
            absent: list[str] = []
            for rule_id in rules:
                j = next((x for x in self.judged if x.row.rule_id == rule_id), None)
                if j is None:
                    absent.append(rule_id)
                elif not j.settled:
                    unsettled.append(rule_id)
                elif FIELDS[0] in j.needs and j.row.attribution:
                    texts.append(j.row.attribution)
            folded = sorted(set(texts))
            out.append({"出す先 id": bundle_id,
                        "出すファイル名": self.bundles.file_of(bundle_id),
                        "含む rule の数": len(rules),
                        "要る帰属の文字列(畳む前)": len(texts),
                        "要る帰属の文字列": folded,
                        "許諾が登録表に無くて要否の分からない rule": unsettled,
                        "台帳に無い rule": absent})
        return out

    def stopped(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for p in self.report.pending:
            out[p.reason] = out.get(p.reason, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: STOP_REASONS.index(kv[0])))

    # ---------------- まとめ

    def counts(self) -> dict[str, object]:
        """件数と行数を、分母の内訳つきで出す。割合も点数も順位も返さない。"""
        five = self.five()
        rows = self.rows_by_result()
        out: dict[str, object] = {
            "行の台帳の行数": self.report.ledger,
            "許諾の登録表の行数": self.report.registry,
            "出典元の台帳の行数": self.report.origins,
            "配布物の目録の行数": self.report.bundles,
            "分母(rule の数)": self.rule_denominator(),
            "分母(許諾の名前が登録表に在る rule の数)": self.settled_denominator,
            "分母(別枠の数)": self.aside_denominator(),
            "分母(台帳に出てくる出典元の数)": len(self.ledger.origin_ids),
            "分母(出す先の数)": len(self.bundles.ids),
            "全体の行数": self.total_rows(),
            "5 値": five,
            "5 値ごとの行数": rows,
            "空の欄の数": self.empty_field_count(),
            "空の欄を持つ rule の数": five[KEKKA[1]],
            "登録表に無い許諾の名前を指す行": len(self.unregistered_licenses()),
            "出典元の台帳に無い出典元 id を指す行": len(self.unknown_origins()),
            "目録に載っているのに台帳に無い rule": len(self.dangling_rules()),
            "出典元ごと": self.by_origin(),
            "数表ごと": self.by_table(),
            "理由別の止まった件数": self.stopped(),
            "読んだか": ("読んだ" if self.judged else
                         "読んでいない(宣言が揃う前に止まったので 5 値は全て 0)"),
        }
        out["分母に含めたもの"] = (
            f"rule の数 {self.rule_denominator()} 件のうち、許諾の名前が登録表に無い "
            f"{five[BEKKA]} 件が別枠で、残る {self.settled_denominator} 件に 4 値が付く。"
            "内訳は " + " + ".join(f"{k} {five[k]}" for k in YOTSU))
        out["件数の合計の検算"] = (
            f"5 値の合計 {sum(five.values())} / rule の数 "
            f"{self.rule_denominator()}(4 値 {sum(five[k] for k in YOTSU)} = "
            f"{self.settled_denominator} も同じ、出典元ごとの内訳の合計 "
            f"{sum(int(r['rule の数']) for r in self.by_origin())} = rule の数 も同じ、"
            f"出典元ごとの行数の合計 "
            f"{sum(int(r['行数']) for r in self.by_origin())} = 全体の行数 "
            f"{self.total_rows()} も同じ、5 値ごとの行数の合計 "
            f"{sum(rows.values())} = 全体の行数 も同じ)")
        out["許諾の名前を推測しない"] = (
            "許諾の名前は行に書かれた文字列だけを見る。出典元の名前・URL の形・ファイルの"
            "拡張子から名前を当てる経路が無く、「公式の公開情報だから大丈夫」の既定も無い。"
            "登録表に無い名前と空欄は、どちらも別枠に出る")
        out["配ってよいかを判定しない"] = (
            "返るのは宣言が揃っているかの 4 値と別枠だけで、配布の是非を指す欄がこの出力に"
            "無い。どの規約が当たるかを決めるのは表を持つ人の仕事で、この部品の外にある")
        out["規約の原文を取りに行かない"] = (
            "要求される欄は許諾の登録表に宣言として渡される側で、この部品は規約の中身を"
            "知らない。原文を取りに行く経路も、本文を読む経路も持たない")
        out["帰属の文字列を生成しない"] = (
            "帰属の文字列は行に書かれた写しをそのまま畳むだけで、出典元の名前から文面を"
            "組み立てる経路が無い。空なら空のまま「足りない欄」へ入る")
        out["足りないのと決めていないを潰さない"] = (
            "出すと宣言されたが欄が空の行と、出す宣言そのものが無い行は、別の値と別の行数で"
            "返る。前者は埋める欄が決まっていて、後者はまだ誰も決めていない")
        out["出さないと宣言された行を足りない側に数えない"] = (
            "外に出す宣言が 出さない の行は別の値に出て、空の欄の一覧にも、欄が空の件数にも"
            "入らない。配らないと宣言された行に足りない欄は無い")
        out["理由を当てない"] = (
            "なぜ許諾の名前が書かれていないか、なぜ出さないと宣言したかの理由欄が無い。"
            "別枠の各行に出典を付けるところまでで、そこから先は読む人が書く")
        out["件数を割合にしない"] = (
            "返るのは件数と行数と分母の内訳だけで、整備の度合いを返す呼び方も option も無い")
        out["順位も勧めも出さない"] = (
            "どの出典元から埋めるべきかの順位欄が無い。埋める順は表を持つ人が決める")
        out["引かない・配らない"] = (
            "行を引く経路も、値を計算する経路も、ファイルを転送する経路も無い。読むのは"
            "手元の 4 枚だけ")
        out["入力を書き換えない"] = (
            "verify が作る写し(1 欄を空にした表・許諾を 1 件外した登録表)はメモリの中"
            "だけで、入力の CSV には 1 文字も書かない")
        return out

    def judgement_bytes(self) -> bytes:
        """判定部分 = rule ごとの 5 値と行数と要求される欄。時刻・絶対パスは入れない。"""
        self._guard()
        lines = ["\t".join(["件", str(self.report.ledger), str(self.report.registry),
                            str(self.report.origins), str(self.report.bundles)])]
        lines.extend(j.line() for j in self.judged)
        return ("\n".join(lines) + "\n").encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.judgement_bytes()).hexdigest()

    def read_condition(self) -> dict[str, str]:
        return {SCOPE_KEYS[0]: self.ledger.path, SCOPE_KEYS[1]: self.registry.path,
                SCOPE_KEYS[2]: self.origins.path, SCOPE_KEYS[3]: self.bundles.path}

    def _guard(self) -> None:
        if not self.report.ok:
            raise RuntimeError("止まっているので数えた rule は無い。"
                               "report.pending の理由コードを見る")


def share_terms(ledger: Ledger, registry: Registry, origins: Origins,
                bundles: Bundles) -> Tally:
    """rule 1 件ごとに 5 値を付ける。

    4 枚のどれかが 1 行でも壊れていたら 1 件も数えない(5 値は全て 0)。
    """
    pending = list(ledger.pending) + list(registry.pending) + list(bundles.pending)
    for row in ledger.ordered:
        pending.extend(row.issues(origins))
    for x in bundles.ordered:
        row = ledger.of(x.rule_id)
        if row is None:
            continue            # 逆向きの欠けは止めずに一覧へ出す
        where = f"配布物の目録 行 {x.number}: {x.bundle_id} ← {x.rule_id}"
        if row.declared_out:
            pending.append(Pending(STOP_REASONS[5], where))
        elif row.share != DASU:
            pending.append(Pending(STOP_REASONS[6], where))
    report = Report(not pending, tuple(pending), len(ledger.items),
                    len(registry.items), len(origins.items), len(bundles.items))
    if pending:                 # 1 件も数えずに止まる
        return Tally(report=report, judged=(), ledger=ledger, registry=registry,
                     origins=origins, bundles=bundles)
    judged = tuple(judge(row, registry) for row in ledger.ordered)
    return Tally(report=report, judged=judged, ledger=ledger, registry=registry,
                 origins=origins, bundles=bundles)


# ------------------------------------------------------------ verify


def moved_elsewhere(first: Tally, after: Tally, *keep: str) -> list[str]:
    """判定部分の行が動いた rule のうち、動くはずだった rule でないものの名前。"""
    was = {j.row.rule_id: j.line() for j in first.judged}
    return sorted(j.row.rule_id for j in after.judged
                  if j.line() != was.get(j.row.rule_id) and j.row.rule_id not in keep)


def blank_probe_plan(first: Tally) -> list[tuple[Judged, str]]:
    """1 欄を空にする計画。

    「宣言が揃っている」行のうち、その許諾が帰属の文字列を要求すると宣言していて、いま
    その欄が埋まっている行を選ぶ(空にすると **その行だけ** が「欄が空」へ動く)。
    """
    return [(j, FIELDS[0]) for j in first.judged
            if j.result == KEKKA[0] and FIELDS[0] in j.needs and j.row.attribution]


def blank_probe(ledger: Ledger, registry: Registry, origins: Origins,
                bundles: Bundles, first: Tally) -> dict[str, object]:
    """ある行の帰属の文字列を空にして数え直す。

    いつも成り立つはずのこと: **「宣言が揃っている」が 1 減って「出すと宣言されたが欄が空」が
    1 増え、空の欄の一覧にその欄名が 1 件現れ、行数の合計がその rule の行数だけ移る**
    (ほかの rule の判定は動かない)。
    """
    rows: list[dict[str, object]] = []
    plans = blank_probe_plan(first)
    ok = bool(plans)
    before, before_rows = first.five(), first.rows_by_result()
    before_fields = first.empty_field_count()
    for j, field in plans:
        after = share_terms(ledger.blanked(j.row.rule_id, field), registry, origins,
                            bundles)
        now, now_rows = after.five(), after.rows_by_result()
        mine = next((x for x in after.judged if x.row.rule_id == j.row.rule_id), None)
        listed = [e for e in after.empty_fields() if e["rule id"] == j.row.rule_id]
        fits = (after.report.ok and mine is not None
                and mine.result == KEKKA[1] and mine.missing == (field,)
                and now[KEKKA[0]] == before[KEKKA[0]] - 1
                and now[KEKKA[1]] == before[KEKKA[1]] + 1
                and all(now[k] == before[k] for k in KEKKA
                        if k not in (KEKKA[0], KEKKA[1]))
                and now_rows[KEKKA[0]] == before_rows[KEKKA[0]] - j.row.rows
                and now_rows[KEKKA[1]] == before_rows[KEKKA[1]] + j.row.rows
                and after.empty_field_count() == before_fields + 1
                and len(listed) == 1 and listed[0]["足りない欄"] == [field]
                and moved_elsewhere(first, after, j.row.rule_id) == []
                and after.total_rows() == first.total_rows())
        ok = ok and fits
        rows.append({"空にした欄": f"{j.row.rule_id} の {field}",
                     "許諾の名前": j.row.license_name,
                     "その rule の行数": j.row.rows,
                     KEKKA[0]: f"{before[KEKKA[0]]} → {now[KEKKA[0]]}",
                     KEKKA[1]: f"{before[KEKKA[1]]} → {now[KEKKA[1]]}",
                     "揃っている行数":
                         f"{before_rows[KEKKA[0]]} → {now_rows[KEKKA[0]]}",
                     "欄が空の行数":
                         f"{before_rows[KEKKA[1]]} → {now_rows[KEKKA[1]]}",
                     "空の欄の数":
                         f"{before_fields} → {after.empty_field_count()}",
                     "ほかで動いた rule": moved_elsewhere(first, after,
                                                          j.row.rule_id),
                     "合うか": fits})
    return {"書き換えた欄": "行の台帳の 1 欄(写しはメモリの中だけ)",
            "分母(rule の数)": first.rule_denominator(), "行ごと": rows, "合うか": ok,
            "読み": ("欄を 1 つ空にすると、その行だけが「揃っている」から「欄が空」へ"
                     "移り、行数の合計もその rule の行数だけ移る。件数と行数と欄の数を"
                     "別の経路で数えていることが、ここで数として出る")}


def moves_with(first: Tally, name: str) -> tuple[Judged, ...]:
    """その許諾の名前を外したときに別枠へ動く行(= 出すと宣言されている行だけ)。"""
    return tuple(j for j in first.judged
                 if j.result in (KEKKA[0], KEKKA[1]) and j.row.license_name == name)


def stays_with(first: Tally, name: str) -> tuple[Judged, ...]:
    """同じ名前を持つが動かない行(= 出さない / 出す宣言が無い の行)。"""
    return tuple(j for j in first.judged
                 if j.result in (KEKKA[2], KEKKA[3]) and j.row.license_name == name)


def license_probe_plan(first: Tally) -> list[str]:
    """許諾を 1 件外す計画。外すと 1 件以上の行が別枠へ動く名前だけを選ぶ。"""
    return [name for name in first.registry.names if moves_with(first, name)]


def license_probe(ledger: Ledger, registry: Registry, origins: Origins,
                  bundles: Bundles, first: Tally) -> dict[str, object]:
    """許諾の登録表から 1 件外して数え直す。

    いつも成り立つはずのこと: **その名前を指す「出す」の行だけが別枠へ移り、ほかの許諾を
    指す行の 4 値は変わらない**(出さないと宣言された行と、出す宣言の無い行も動かない)。
    """
    rows: list[dict[str, object]] = []
    plans = license_probe_plan(first)
    ok = bool(plans)
    before = first.five()
    for name in plans:
        shifted = moves_with(first, name)
        stayed = stays_with(first, name)
        after = share_terms(ledger, registry.without(name), origins, bundles)
        now = after.five()
        each = [next((x for x in after.judged if x.row.rule_id == j.row.rule_id),
                     None) for j in shifted]
        same = [next((x for x in after.judged if x.row.rule_id == j.row.rule_id),
                     None) for j in stayed]
        fits = (after.report.ok
                and all(x is not None and x.result == BEKKA and x.missing == ()
                        for x in each)
                and all(x is not None and x.result == j.result
                        for x, j in zip(same, stayed))
                and now[BEKKA] == before[BEKKA] + len(shifted)
                and sum(now[k] for k in YOTSU) == sum(before[k] for k in YOTSU) \
                - len(shifted)
                and now[KEKKA[2]] == before[KEKKA[2]]
                and now[KEKKA[3]] == before[KEKKA[3]]
                and moved_elsewhere(first, after,
                                    *[j.row.rule_id for j in shifted]) == []
                and after.total_rows() == first.total_rows())
        ok = ok and fits
        rows.append({"外した許諾の名前": name,
                     "動く rule": [j.row.rule_id for j in shifted],
                     "動く行数": sum(j.row.rows for j in shifted),
                     "同じ名前だが動かない rule": [j.row.rule_id for j in stayed],
                     KEKKA[0]: f"{before[KEKKA[0]]} → {now[KEKKA[0]]}",
                     KEKKA[1]: f"{before[KEKKA[1]]} → {now[KEKKA[1]]}",
                     KEKKA[2]: f"{before[KEKKA[2]]} → {now[KEKKA[2]]}",
                     KEKKA[3]: f"{before[KEKKA[3]]} → {now[KEKKA[3]]}",
                     BEKKA: f"{before[BEKKA]} → {now[BEKKA]}",
                     "ほかで動いた rule": moved_elsewhere(
                         first, after, *[j.row.rule_id for j in shifted]),
                     "合うか": fits})
    return {"書き換えた欄": "許諾の登録表 1 行(写しはメモリの中だけ)",
            "分母(rule の数)": first.rule_denominator(), "行ごと": rows, "合うか": ok,
            "読み": ("登録表から名前を 1 つ外すと、その名前を指す「出す」の行だけが別枠へ"
                     "移る。出さないと宣言された行が動かないことが、宣言を先に見ている"
                     "ことの数の形になる")}


def verify(ledger: Ledger, registry: Registry, origins: Origins,
           bundles: Bundles) -> dict[str, object]:
    """2 回読んで sha256 を比べ、4 枚の行順を入れ替えても同じかを見て、件数を検算する。
    さらに、1 欄を空にした写しと、許諾を 1 件外した写しを読んで差分を出す。"""
    first = share_terms(ledger, registry, origins, bundles)
    if not first.report.ok:
        return {"ok": False, "stage": "止まった(数えた rule は返さない)",
                **first.counts(),
                "pending": [p.as_dict() for p in first.report.pending]}
    if not bundles.swap:
        raise ReadError("配布物の目録に入れ替え方(swap)が無いので verify は走らせない")
    second = share_terms(ledger, registry, origins, bundles)
    how = bundles.swap
    third = share_terms(ledger.swapped(how), registry.swapped(how),
                        origins.swapped(how), bundles.swapped(how))
    pending: list[Pending] = []
    if first.sha256() != second.sha256():
        pending.append(Pending(STOP_REASONS[11], f"2 回目 {second.sha256()[:12]}"))
    if not (third.report.ok and first.sha256() == third.sha256()):
        pending.append(Pending(STOP_REASONS[12],
                               f"入れ替え方 {how} の 4 枚で {third.sha256()[:12]}"
                               if third.report.ok else
                               f"入れ替え方 {how} の 4 枚では止まった"))
    five = first.five()
    rows = first.rows_by_result()
    if sum(five.values()) != first.rule_denominator():
        pending.append(Pending(STOP_REASONS[10],
                               f"5 値の合計 {sum(five.values())} / rule の数 "
                               f"{first.rule_denominator()}"))
    inner = sum(five[k] for k in YOTSU)
    if inner != first.settled_denominator:
        pending.append(Pending(STOP_REASONS[10],
                               f"4 値 {inner} / 名前が登録表に在る rule "
                               f"{first.settled_denominator}"))
    by_origin_rules = sum(int(r["rule の数"]) for r in first.by_origin())
    if by_origin_rules != first.rule_denominator():
        pending.append(Pending(STOP_REASONS[10],
                               f"出典元ごとの内訳の合計 {by_origin_rules} / "
                               f"rule の数 {first.rule_denominator()}"))
    by_origin_rows = sum(int(r["行数"]) for r in first.by_origin())
    if by_origin_rows != first.total_rows():
        pending.append(Pending(STOP_REASONS[10],
                               f"出典元ごとの行数の合計 {by_origin_rows} / "
                               f"全体の行数 {first.total_rows()}"))
    if sum(rows.values()) != first.total_rows():
        pending.append(Pending(STOP_REASONS[10],
                               f"5 値ごとの行数の合計 {sum(rows.values())} / "
                               f"全体の行数 {first.total_rows()}"))
    out: dict[str, object] = {
        "ok": not pending, "読んだ回数": 2, "入れ替え方": how,
        "sha256": first.sha256(), "2 回目の sha256": second.sha256(),
        "入れ替えた 4 枚の sha256": third.sha256() if third.report.ok else "",
        "件数の検算": {"5 値": five, "5 値の合計": sum(five.values()), "4 値": inner,
                       "出典元ごとの内訳の合計": by_origin_rules,
                       "出典元ごとの行数の合計": by_origin_rows,
                       "5 値ごとの行数の合計": sum(rows.values()),
                       "空の欄の数": first.empty_field_count(),
                       "全体の行数": first.total_rows(),
                       "分母(rule の数)": first.rule_denominator(),
                       "分母(許諾の名前が登録表に在る rule の数)":
                           first.settled_denominator,
                       "分母(別枠の数)": first.aside_denominator()},
        "1 欄を空にした写し": blank_probe(ledger, registry, origins, bundles, first),
        "許諾を 1 件外した写し": license_probe(ledger, registry, origins, bundles,
                                               first),
    }
    for key in ("1 欄を空にした写し", "許諾を 1 件外した写し"):
        if not out[key]["合うか"]:        # type: ignore[index]
            pending.append(Pending(STOP_REASONS[10], f"{key} の件数が合わない"))
            out["ok"] = False
    if pending:
        out["観測"] = ("同じ表から違うバイト列が出た、または件数が合わない(平均も多数決も"
                       "しない。名前の書かれていない理由も当てない)")
        out["pending"] = [p.as_dict() for p in pending]
    return out


# ------------------------------------------------------------ ひな型

T_LICENSE = "合成の許諾(架空)"
T_SRC = "合成の台帳のメモ(架空)L1"

TEMPLATE_LEDGER = [
    list(DAICHOU_COLUMNS),
    ["H1", "K11", "6", "G1", T_LICENSE, "合成の帰属の文字列(架空)", "", "",
     DASU, T_SRC],
    ["H1", "K12", "4", "G1", T_LICENSE, "", "", "", DASU, T_SRC],
    ["H2", "K21", "9", "G2", "", "", "", "", "", T_SRC],
]
TEMPLATE_REGISTRY = [
    list(KYODAKU_COLUMNS),
    [T_LICENSE, YESNO[0], YESNO[1], YESNO[1], "合成の許諾のメモ(架空)L1"],
]
TEMPLATE_ORIGINS = [
    list(SHUTTEN_COLUMNS),
    ["G1", "", "2026-05-11", "合成の上流のメモ(架空)L18"],
    ["G2", "", "2026-05-11", ""],
]
TEMPLATE_BUNDLES = [
    list(MOKUROKU_COLUMNS),
    ["B1", "合成の配布物(架空).json", "K11", SWAPS[0], "合成の目録のメモ(架空)L1"],
]


def write_csv(path: Path, rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    return path


def init(dest: str | Path) -> tuple[Path, Path, Path, Path]:
    d = Path(dest)
    return (write_csv(d / "行の台帳.csv", TEMPLATE_LEDGER),
            write_csv(d / "許諾の登録表.csv", TEMPLATE_REGISTRY),
            write_csv(d / "出典元の台帳.csv", TEMPLATE_ORIGINS),
            write_csv(d / "配布物の目録.csv", TEMPLATE_BUNDLES))


# ------------------------------------------------------------ CLI

def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def build_parser() -> argparse.ArgumentParser:
    """CLI は terms / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = argparse.ArgumentParser(prog="share_terms",
                                 description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in SUBCOMMANDS[:3]:
        p = sub.add_parser(name)
        p.add_argument("ledger")
        p.add_argument("registry")
        p.add_argument("origins")
        p.add_argument("bundles")
    sub.add_parser(SUBCOMMANDS[3]).add_argument("dest")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == "init":
        print("書いた: " + " / ".join(str(p) for p in init(a.dest)))
        return 0
    try:
        ledger, registry = Ledger.load(a.ledger), Registry.load(a.registry)
        origins, bundles = Origins.load(a.origins), Bundles.load(a.bundles)
        if a.cmd == "verify":
            out = verify(ledger, registry, origins, bundles)
            _print(out)
            return 0 if out["ok"] else 3
        t = share_terms(ledger, registry, origins, bundles)
    except ReadError as e:
        print(f"表として読めない: {e}", file=sys.stderr)
        return 2
    if not t.report.ok:
        _print({"ok": False, "stage": "止まった(数えた rule は返さない)", **t.counts(),
                "pending": [p.as_dict() for p in t.report.pending]})
        return 3
    body: dict[str, object] = {"ok": True, **t.counts()}
    if a.cmd == SUBCOMMANDS[0]:
        body["判定ごとの一覧"] = t.listed()
        body["空の欄の一覧"] = t.empty_fields()
        body["登録表に無い許諾の名前を指す行の一覧"] = t.unregistered_licenses()
        body["出典元の台帳に無い出典元 id を指す行の一覧"] = t.unknown_origins()
        body["目録に載っているのに台帳に無い rule の一覧"] = t.dangling_rules()
        body["配布物ごとに要る帰属の文字列"] = t.attributions()
        body["sha256"] = t.sha256()
        body["読んだ条件"] = t.read_condition()
    _print(body)
    clean = (t.aside_denominator() == 0 and t.empty_field_count() == 0
             and not t.unknown_origins() and not t.dangling_rules()
             and not t.stopped())
    return 0 if clean else 3


if __name__ == "__main__":
    raise SystemExit(main())
