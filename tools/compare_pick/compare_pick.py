"""compare_pick — 候補が 2 本以上残った組が、宣言された順位で決まるのか値の比較で決まるのかを
宣言表から読み、比較で決まる組は宣言が揃っているかを確かめてから勝者を出す。比べるだけ。

**順位の欄に値が入っていても、その順位では決まらない裁定が実在する。「高い方が適用」は順位の
上下ではなく値の比較で、比較は ① どの欄を比べるか ② 単位 ③ 丸めの前か後か ④ 同値のとき
どちらが勝つか ⑤ 比べる 2 行の有効期間が基準日で重なるか、の 5 つが宣言されていないと、同じ
「高い方」が実装ごとに別の答えを返す。しかも順位の欄は埋まっているので、同順位の重複を見る
検査はこの行を 1 件も止めない。**

この部品は、裁定の宣言表・候補の表・基準日の表の 3 枚から、(組 × 基準日)1 つごとに 4 値
(**順位で決まった / 比較で決まった / 比較では決まらない / 止まった**)を付ける。止まったものは
理由コード別、決まらないものは理由別に分けて数え、分母(組数 × 基準日の数)と内訳を併記して
返す。**式を評価しない。行を引かない。比べるだけだ。**

持たせていないものが規律になっている。

  - **裁定の種類が「値の比較」の組は、順位の欄に値が入っていても順位で決めない**(比較の代わり
    に順位を読む経路が無い。順位を読む経路は 1 つだけで、同値のときの扱いに「宣言された順位で
    裁定」と書いてある組に限る)
  - **単位が違う 2 行を比較しない**(換算表も換算の引数も持たない)
  - **丸めを比較の前にするか後にするかが空欄の組は比較しない**(既定を持たない)
  - **丸めの前後は宣言どおりにしか動かさない**(道具の側で有利な方を選ばない)
  - **同値は向きで勝たせない**(「大きい方」でも同値なら決まらない。宣言が「宣言された順位で
    裁定」なら順位へ落とすが、順位も同じなら決まらない)
  - **float を使わない**(値は文字列から Decimal にして比べる)
  - **比べる 2 行の有効期間が基準日で重なっていない組は比較しない**(重なりを確かめてから
    比べる。期間を切る段は持たない)
  - **式を評価しない・値を計算しない**(計算は宣言された丸め 1 段だけで、式を解く経路が無い)
  - **行を引かない・期間を切らない・帯に当てない・空欄の意味を決めない・日付の種別を決め
    ない・未来の行を分けない**
  - **件数は理由別に分母(組数 × 基準日の数)と内訳つきで出す**(率を単独で返さない)
  - **4 つを混ぜない**(順位で決まった / 比較で決まった / 比較では決まらない / 止まった)
  - **入力表を書き換えず、行も宣言も生成しない**
  - **出典の欄が空の行は使わずに止まる**
  - **同じ入力には同じバイト列**(判定部分に時刻・絶対パス・ホスト名を入れない)

入力は 3 つ。裁定の宣言表(CSV)、候補の表(CSV)、基準日の表(CSV)。

裁定の宣言表の列は 9 つ。1 rule が 1 行。

    rule_id     rule id(空欄は「表として読めない」。2 行あると止まる)
    kind        裁定の種類。登録の 3 種(宣言された順位 / 値の比較 / 決まらない)
    field       比べる欄の名前(裁定の種類が「値の比較」のときだけ要る)
    direction   向き。登録の 2 種(大きい方 / 小さい方)
    unit        単位。**空欄のまま持つ**(比較の段で止まる)
    round_when  丸めを比較の前にするか後にするか(前 / 後)。**空欄のまま持つ**
    rounding    丸めの名前。登録の 3 種の外(空欄も)は比較の段で止まる
    tie         同値のときの扱い。登録の 2 種(決まらない / 宣言された順位で裁定)
    source      出典。空欄は止まる

候補の表の列は 10。絞り終わって残った候補 1 本が 1 行。

    group_id    組 id。同じ組の行が比較の相手になる
    rule_id     その組が従う rule id。組の中で 1 つだけ
    row_id      行 id(組 id との組み合わせが 2 行あると止まる)
    priority    順位。**空欄のまま持つ**(0 と読み替えない)
    field       この行が持っている欄の名前。宣言の比べる欄と一致しなければ止まる
    value       比べる欄の値。**文字列のまま読み、Decimal にして比べる**
    unit        この行の単位。宣言の単位と違えば止まる
    valid_from  有効開始日(ISO の日付)
    valid_to    有効終了日(ISO の日付。半開区間で、終わりの日は含まない)
    source      出典。空欄は止まる

基準日の表の列は 4 つ。1 基準日が 1 行。

    asof_id     基準日 id(空欄も、同じ id が 2 行あるのも「表として読めない」)
    asof        基準日(ISO の日付)
    source      出典。空欄は止まる
    swap        入れ替え方。verify が 3 枚の行順を入れ替えるときの宣言。全行で同じ値

使い方:

    python compare_pick.py init ひな型/
    python compare_pick.py check  裁定の宣言表.csv 候補の表.csv 基準日の表.csv
    python compare_pick.py pick   裁定の宣言表.csv 候補の表.csv 基準日の表.csv
    python compare_pick.py verify 裁定の宣言表.csv 候補の表.csv 基準日の表.csv

終了コードは、止まった組も決まらない組も 1 つも無いときだけ 0、どちらかがあるときは 3、表と
して読めなければ 2。
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import platform
import re
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_FLOOR, ROUND_HALF_UP
from pathlib import Path

SENGEN_COLUMNS = ("rule_id", "kind", "field", "direction", "unit", "round_when",
                  "rounding", "tie", "source")
KOUHO_COLUMNS = ("group_id", "rule_id", "row_id", "priority", "field", "value", "unit",
                 "valid_from", "valid_to", "source")
KIJUNBI_COLUMNS = ("asof_id", "asof", "source", "swap")

# 裁定の種類。登録の 3 種だけ(外は理由コードで止まる)
KINDS = ("宣言された順位", "値の比較", "決まらない")
# 向き。登録の 2 種だけ
DIRECTIONS = ("大きい方", "小さい方")
# 丸めを比較の前にするか後にするか
ROUND_WHENS = ("前", "後")
# 丸めの名前。登録の 3 種だけ(空欄も登録に無い名前として扱う)
ROUNDINGS = ("丸めない", "50 の倍数に丸める", "小数点以下を切り捨てる")
# 同値のときの扱い。登録の 2 種だけ
TIES = ("決まらない", "宣言された順位で裁定")
SWAPS = ("逆順", "両端入れ替え", "1 つずらす")

# 4 値。混ぜない
RESULTS = ("順位で決まった", "比較で決まった", "比較では決まらない", "止まった")

# 決まらない理由。5 種
UNDECIDED = ("宣言が決まらないと言っている", "同順位で決まらない", "順位の欄が空",
             "同値で決まらない", "同値で順位も同じ")

# 止まる理由コード。18 個(先の 4 個は 1 組も読まずに止まる、次の 11 個は組ごと、
# 後の 3 個は verify が見つける)
STOP_REASONS = ("出典の欄が空", "組 id と行 id の重複", "宣言に無い裁定の種類",
                "同じ rule に宣言が 2 行",
                "比べる欄が候補の表に無い", "比べる欄の値が空", "単位の不一致",
                "単位の欄が空", "丸めの前後が空", "登録されていない丸めの名前",
                "同値のときの扱いが空", "値が数に読めない", "float 混入",
                "基準日で有効期間が重ならない",
                "候補が 1 本しかない組に比較の宣言が付いている",
                "件数の合計が合わない", "2 回目の判定部分が不一致",
                "行順を入れ替えた表で出力が変わる")
TABLE_REASONS = STOP_REASONS[:4]      # 1 組も読まずに止まる
PAIR_REASONS = STOP_REASONS[4:15]     # 組ごとに止まる
VERIFY_REASONS = STOP_REASONS[15:]    # verify が見つける

SUBCOMMANDS = ("pick", "check", "verify", "init")

# 判定部分に入れない欄(sha256 の対象にもしない)
SCOPE_KEYS = ("読んだ宣言表の絶対パス", "読んだ候補の表の絶対パス",
              "読んだ基準日の表の絶対パス", "読んだ時刻", "ホスト名")

INTEGER = re.compile(r"\A(0|[1-9][0-9]*)\Z")
# 比べる値の書き方。指数表記も桁あふれも入れない(Decimal で正確に比べられる形だけ)
NUMBER = re.compile(r"\A-?(0|[1-9][0-9]{0,14})(\.[0-9]{1,6})?\Z")
# float から来た形(指数表記・NaN・Infinity)。読めるが使わない
FLOATISH = re.compile(r"\A[+-]?([0-9.]+[eE][+-]?[0-9]+|[iI]nf(inity)?|[nN]a[nN])\Z")
DATE = re.compile(r"\A(19|20)[0-9]{2}-[0-9]{2}-[0-9]{2}\Z")
STEP = Decimal(50)


class ReadError(Exception):
    """表として読めない(理由コードにせず終了コード 2 で返す = 表を書く側の話)。"""


@dataclass(frozen=True)
class Pending:
    reason: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"reason": self.reason, "detail": self.detail}


def swap_rows(rows: list, how: str) -> list:
    """宣言された入れ替え方で行順だけを入れ替える(乱数の既定は持たない)。"""
    if how not in SWAPS:
        raise ReadError(f"入れ替え方が登録の外: {how}")
    out = list(rows)
    if len(out) >= 2:
        if how == SWAPS[0]:
            out.reverse()
        elif how == SWAPS[1]:
            out[0], out[-1] = out[-1], out[0]
        else:
            out = out[1:] + out[:1]
    return out


def read_date(text: str, where: str) -> datetime.date:
    """ISO の日付だけを読む(和暦も区切り違いも「表として読めない」)。"""
    if not DATE.match(text):
        raise ReadError(f"{where}: 日付は ISO(YYYY-MM-DD)で書く({text or '空欄'})")
    try:
        return datetime.date.fromisoformat(text)
    except ValueError as e:
        raise ReadError(f"{where}: 暦に無い日付({text}): {e}") from e


def read_number(text: str) -> tuple[Decimal | None, str]:
    """比べる値を文字列から Decimal にする。読めない形は理由コードで返す。"""
    try:
        Decimal(text)
    except InvalidOperation:
        return None, STOP_REASONS[11]
    if NUMBER.match(text):
        return Decimal(text), ""
    if FLOATISH.match(text):
        return None, STOP_REASONS[12]
    return None, STOP_REASONS[11]


def round_value(value: Decimal, name: str) -> Decimal:
    """宣言された丸め 1 段だけ。登録の 3 種以外は呼ぶ前に止める(既定を持たない)。"""
    if name == ROUNDINGS[0]:
        return value
    if name == ROUNDINGS[1]:
        return (value / STEP).to_integral_value(rounding=ROUND_HALF_UP) * STEP
    if name == ROUNDINGS[2]:
        return value.to_integral_value(rounding=ROUND_FLOOR)
    raise ReadError(f"登録されていない丸めの名前: {name or '空欄'}")


# ------------------------------------------------------------ 裁定の宣言表

@dataclass(frozen=True)
class Rule:
    rule_id: str
    kind: str
    field: str
    direction: str
    unit: str
    round_when: str
    rounding: str
    tie: str
    source: str
    number: int

    @property
    def by_priority(self) -> bool:
        return self.kind == KINDS[0]

    @property
    def by_compare(self) -> bool:
        return self.kind == KINDS[1]

    def with_round_when(self, when: str) -> "Rule":
        """丸めの前後だけを入れ替えた写しを返す(元の行は書き換えない)。"""
        return Rule(self.rule_id, self.kind, self.field, self.direction, self.unit,
                    when, self.rounding, self.tie, self.source, self.number)


@dataclass(frozen=True)
class Declared:
    items: tuple[Rule, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Declared":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"裁定の宣言表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Declared":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in SENGEN_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("裁定の宣言表に " + " / ".join(lack) + " の列が無い")
        items: list[Rule] = []
        pending: list[Pending] = []
        seen: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in SENGEN_COLUMNS}
            where = f"裁定の宣言表 行 {i}"
            if not cell["rule_id"]:
                raise ReadError(f"{where}: rule id が空欄")
            if cell["rule_id"] in seen:
                pending.append(Pending(STOP_REASONS[3], f"{where}: {cell['rule_id']}"))
            seen.add(cell["rule_id"])
            if cell["kind"] not in KINDS:
                # 何をする宣言か分からないので、1 組も読まずに止まる
                pending.append(Pending(STOP_REASONS[2],
                                       f"{where}: {cell['kind'] or '空欄'}"
                                       f"(登録は {' / '.join(KINDS)})"))
            elif cell["kind"] == KINDS[1]:
                # 比較の宣言だけに要る欄。空欄のまま持つ欄(単位 / 丸めの前後 / 丸めの
                # 名前 / 同値の扱い)は、組ごとの理由コードで止める
                if not cell["field"]:
                    raise ReadError(f"{where}: 比べる欄の名前が空欄"
                                    f"({cell['rule_id']})")
                if cell["direction"] not in DIRECTIONS:
                    raise ReadError(f"{where}: 向きは {' / '.join(DIRECTIONS)} の宣言"
                                    f"だけ({cell['direction'] or '空欄'})")
                if cell["round_when"] and cell["round_when"] not in ROUND_WHENS:
                    raise ReadError(f"{where}: 丸めの前後は "
                                    f"{' / '.join(ROUND_WHENS)} の宣言だけ"
                                    f"({cell['round_when']})")
                if cell["tie"] and cell["tie"] not in TIES:
                    raise ReadError(f"{where}: 同値のときの扱いは "
                                    f"{' / '.join(TIES)} の宣言だけ({cell['tie']})")
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0], f"{where}({cell['rule_id']})"))
            items.append(Rule(rule_id=cell["rule_id"], kind=cell["kind"],
                              field=cell["field"], direction=cell["direction"],
                              unit=cell["unit"], round_when=cell["round_when"],
                              rounding=cell["rounding"], tie=cell["tie"],
                              source=cell["source"], number=i))
        if not items:
            raise ReadError("裁定の宣言表に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    def of(self, rule_id: str) -> Rule | None:
        return next((r for r in self.items if r.rule_id == rule_id), None)

    @property
    def ordered(self) -> tuple[Rule, ...]:
        return tuple(sorted(self.items, key=lambda r: r.rule_id))

    def swapped(self, how: str) -> "Declared":
        return Declared(items=tuple(swap_rows(list(self.items), how)),
                        pending=self.pending, path=self.path)

    def round_when_swapped(self) -> "Declared":
        """比較の宣言の「前」と「後」だけを入れ替えた写しを返す(verify が使う)。"""
        flip = {ROUND_WHENS[0]: ROUND_WHENS[1], ROUND_WHENS[1]: ROUND_WHENS[0]}
        return Declared(items=tuple(r.with_round_when(flip[r.round_when])
                                    if r.by_compare and r.round_when in flip else r
                                    for r in self.items),
                        pending=self.pending, path=self.path)


# ------------------------------------------------------------ 候補の表

@dataclass(frozen=True)
class Row:
    group_id: str
    rule_id: str
    row_id: str
    priority: str          # 空欄のまま持つ(0 と読み替えない)
    field: str
    value: str             # 文字列のまま持つ(読むのは比較の段)
    unit: str
    valid_from: datetime.date
    valid_to: datetime.date
    source: str
    number: int

    def covers(self, asof: datetime.date) -> bool:
        """半開区間。終わりの日は含まない。"""
        return self.valid_from <= asof < self.valid_to

    def with_unit(self, unit: str) -> "Row":
        return Row(self.group_id, self.rule_id, self.row_id, self.priority, self.field,
                   self.value, unit, self.valid_from, self.valid_to, self.source,
                   self.number)


@dataclass(frozen=True)
class Candidates:
    items: tuple[Row, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Candidates":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"候補の表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Candidates":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in KOUHO_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("候補の表に " + " / ".join(lack) + " の列が無い")
        items: list[Row] = []
        pending: list[Pending] = []
        seen: set[tuple[str, str]] = set()
        rule_of: dict[str, str] = {}
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in KOUHO_COLUMNS}
            where = f"候補の表 行 {i}"
            if not cell["group_id"]:
                raise ReadError(f"{where}: 組 id が空欄")
            if not cell["row_id"]:
                raise ReadError(f"{where}: 行 id が空欄({cell['group_id']})")
            if not cell["rule_id"]:
                raise ReadError(f"{where}: rule id が空欄({cell['row_id']})")
            if cell["priority"] and not INTEGER.match(cell["priority"]):
                raise ReadError(f"{where}: 順位が整数でない({cell['priority']})")
            other = rule_of.setdefault(cell["group_id"], cell["rule_id"])
            if other != cell["rule_id"]:
                raise ReadError(f"{where}: 組 {cell['group_id']} の rule が 2 通りある"
                                f"({other} / {cell['rule_id']})")
            key = (cell["group_id"], cell["row_id"])
            if key in seen:
                pending.append(Pending(STOP_REASONS[1],
                                       f"{where}: {cell['group_id']} / "
                                       f"{cell['row_id']}"))
            seen.add(key)
            start = read_date(cell["valid_from"], f"{where} の有効開始日")
            end = read_date(cell["valid_to"], f"{where} の有効終了日")
            if not start < end:
                raise ReadError(f"{where}: 有効期間が逆順か 0 日"
                                f"({cell['valid_from']} / {cell['valid_to']})")
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0], f"{where}({cell['row_id']})"))
            items.append(Row(group_id=cell["group_id"], rule_id=cell["rule_id"],
                             row_id=cell["row_id"], priority=cell["priority"],
                             field=cell["field"], value=cell["value"],
                             unit=cell["unit"], valid_from=start, valid_to=end,
                             source=cell["source"], number=i))
        if not items:
            raise ReadError("候補の表に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    @property
    def group_ids(self) -> tuple[str, ...]:
        return tuple(sorted({r.group_id for r in self.items}))

    def of(self, group_id: str) -> tuple[Row, ...]:
        """その組の行を、行 id の順に並べて返す(表の行順には依らせない)。"""
        return tuple(sorted((r for r in self.items if r.group_id == group_id),
                            key=lambda r: r.row_id))

    def rule_of(self, group_id: str) -> str:
        return self.of(group_id)[0].rule_id

    def swapped(self, how: str) -> "Candidates":
        return Candidates(items=tuple(swap_rows(list(self.items), how)),
                          pending=self.pending, path=self.path)

    def unit_changed(self, group_ids: tuple[str, ...], unit: str) -> "Candidates":
        """宣言した組だけ、行 id が後の 1 行の単位を書き換えた写しを返す(verify が使う)。"""
        last = {g: self.of(g)[-1].row_id for g in group_ids if self.of(g)}
        return Candidates(items=tuple(r.with_unit(unit)
                                      if last.get(r.group_id) == r.row_id else r
                                      for r in self.items),
                          pending=self.pending, path=self.path)


# ------------------------------------------------------------ 基準日の表

@dataclass(frozen=True)
class Asof:
    asof_id: str
    asof: datetime.date
    source: str
    number: int


@dataclass(frozen=True)
class Asofs:
    items: tuple[Asof, ...]
    swap: str
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Asofs":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"基準日の表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Asofs":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in KIJUNBI_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("基準日の表に " + " / ".join(lack) + " の列が無い")
        items: list[Asof] = []
        pending: list[Pending] = []
        swaps: set[str] = set()
        seen: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in KIJUNBI_COLUMNS}
            where = f"基準日の表 行 {i}"
            if not cell["asof_id"]:
                raise ReadError(f"{where}: 基準日 id が空欄")
            if cell["asof_id"] in seen:
                raise ReadError(f"{where}: 基準日 id {cell['asof_id']} が 2 行ある")
            seen.add(cell["asof_id"])
            day = read_date(cell["asof"], f"{where} の基準日")
            if cell["swap"]:
                if cell["swap"] not in SWAPS:
                    raise ReadError(f"{where}: 入れ替え方 {cell['swap']} は登録の外"
                                    f"({' / '.join(SWAPS)})")
                swaps.add(cell["swap"])
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0], f"{where}({cell['asof_id']})"))
            items.append(Asof(asof_id=cell["asof_id"], asof=day,
                              source=cell["source"], number=i))
        if not items:
            raise ReadError("基準日の表に行が無い(ヘッダだけ)")
        if len(swaps) > 1:
            raise ReadError("入れ替え方の宣言が 2 通り以上ある: "
                            + " / ".join(sorted(swaps)))
        return cls(items=tuple(items), swap=next(iter(swaps), ""),
                   pending=tuple(pending), path=path)

    @property
    def ordered(self) -> tuple[Asof, ...]:
        return tuple(sorted(self.items, key=lambda a: a.asof_id))

    def swapped(self, how: str) -> "Asofs":
        return Asofs(items=tuple(swap_rows(list(self.items), how)), swap=self.swap,
                     pending=self.pending, path=self.path)


# ------------------------------------------------------------ 1 組の裁定

@dataclass(frozen=True)
class Verdict:
    result: str
    why: str = ""        # 比較では決まらない のときだけ
    reason: str = ""     # 止まった のときだけ(理由コード)
    detail: str = ""
    row_id: str = ""     # 決まったときだけ
    value: str = ""      # 決まったときだけ、宣言どおりに丸めた後の値
    route: str = ""      # どの経路で決まったか


def by_declared_priority(rows: tuple[Row, ...], route: str) -> Verdict:
    """順位の欄だけで決める(post_027 と同じ読み方。空欄は 0 と読み替えない)。"""
    if any(not r.priority for r in rows):
        return Verdict(RESULTS[2], why=UNDECIDED[2], route=route)
    top = max(int(r.priority) for r in rows)
    best = [r for r in rows if int(r.priority) == top]
    if len(best) == 1:
        return Verdict(RESULTS[0], row_id=best[0].row_id, route=route)
    return Verdict(RESULTS[2], why=UNDECIDED[1], route=route)


def check_declaration(rule: Rule) -> Verdict | None:
    """比較に要る宣言が揃っているか。既定を当てる経路は無い。"""
    if not rule.unit:
        return Verdict(RESULTS[3], reason=STOP_REASONS[7],
                       detail=f"{rule.rule_id}: 宣言の単位が空欄")
    if not rule.round_when:
        return Verdict(RESULTS[3], reason=STOP_REASONS[8],
                       detail=f"{rule.rule_id}: 丸めを比較の前にするか後にするかが空欄")
    if rule.rounding not in ROUNDINGS:
        return Verdict(RESULTS[3], reason=STOP_REASONS[9],
                       detail=f"{rule.rule_id}: {rule.rounding or '空欄'}"
                              f"(登録は {' / '.join(ROUNDINGS)})")
    if not rule.tie:
        return Verdict(RESULTS[3], reason=STOP_REASONS[10],
                       detail=f"{rule.rule_id}: 同値のときの扱いが空欄")
    return None


def read_rows(rule: Rule, rows: tuple[Row, ...]) -> tuple[dict[str, Decimal], Verdict | None]:
    """候補の側を読む。単位を揃える経路も、値を作る経路も無い。"""
    values: dict[str, Decimal] = {}
    for r in rows:
        where = f"{r.group_id} / {r.row_id}"
        if r.field != rule.field:
            return values, Verdict(RESULTS[3], reason=STOP_REASONS[4],
                                   detail=f"{where}: 宣言は {rule.field}、行は "
                                          f"{r.field or '空欄'}")
        if not r.value:
            return values, Verdict(RESULTS[3], reason=STOP_REASONS[5],
                                   detail=f"{where}: {rule.field} の値が空欄")
        if not r.unit:
            return values, Verdict(RESULTS[3], reason=STOP_REASONS[7],
                                   detail=f"{where}: 行の単位が空欄")
        if r.unit != rule.unit:
            return values, Verdict(RESULTS[3], reason=STOP_REASONS[6],
                                   detail=f"{where}: 宣言は {rule.unit}、行は {r.unit}"
                                          "(換算しない)")
        value, bad = read_number(r.value)
        if value is None:
            return values, Verdict(RESULTS[3], reason=bad,
                                   detail=f"{where}: {r.value}")
        values[r.row_id] = value
    return values, None


def judge(rule: Rule, rows: tuple[Row, ...], day: datetime.date) -> Verdict:
    """1 組 1 基準日の読み。順位の列を読む経路は、宣言が同値を順位へ落とすときだけ。"""
    if rule.kind == KINDS[2]:
        return Verdict(RESULTS[2], why=UNDECIDED[0], route="比べない(宣言が決まらない)")
    if rule.by_priority:
        return by_declared_priority(rows, KINDS[0])
    bad = check_declaration(rule)
    if bad is not None:
        return bad
    values, bad = read_rows(rule, rows)
    if bad is not None:
        return bad
    if len(rows) < 2:
        return Verdict(RESULTS[3], reason=STOP_REASONS[14],
                       detail=f"{rows[0].group_id}: 候補が 1 本"
                              f"({rows[0].row_id})なので比べる相手が無い")
    outside = [r.row_id for r in rows if not r.covers(day)]
    if outside:
        return Verdict(RESULTS[3], reason=STOP_REASONS[13],
                       detail=f"{day.isoformat()}: " + " / ".join(outside)
                              + " の有効期間に入らない")
    before = rule.round_when == ROUND_WHENS[0]
    keys = {k: (round_value(v, rule.rounding) if before else v)
            for k, v in values.items()}
    edge = max(keys.values()) if rule.direction == DIRECTIONS[0] else min(keys.values())
    best = tuple(r for r in rows if keys[r.row_id] == edge)
    route = f"値の比較(丸めは比較の{rule.round_when})"
    if len(best) == 1:
        won = best[0].row_id
        return Verdict(RESULTS[1], row_id=won,
                       value=str(round_value(values[won], rule.rounding)), route=route)
    # 同値。向きでは勝たせない
    if rule.tie == TIES[0]:
        return Verdict(RESULTS[2], why=UNDECIDED[3], route=f"{route} → 同値")
    fell = by_declared_priority(best, f"{route} → 同値 → {TIES[1]}")
    if fell.result == RESULTS[0]:
        return Verdict(RESULTS[0], row_id=fell.row_id,
                       value=str(round_value(values[fell.row_id], rule.rounding)),
                       route=fell.route)
    if fell.why == UNDECIDED[1]:
        return Verdict(RESULTS[2], why=UNDECIDED[4], route=fell.route)
    return fell


# ------------------------------------------------------------ 読んだ組の表

@dataclass(frozen=True)
class Pair:
    group_id: str
    rule_id: str
    asof_id: str
    asof: str
    result: str
    why: str = ""
    reason: str = ""
    detail: str = ""
    row_id: str = ""
    value: str = ""
    route: str = ""
    hits: int = 0


@dataclass(frozen=True)
class Report:
    ok: bool
    pending: tuple[Pending, ...]
    rules: int
    rows: int
    groups: int
    asofs: int


@dataclass(frozen=True)
class Table:
    report: Report
    pairs: tuple[Pair, ...]
    declared: Declared
    candidates: Candidates
    asofs: Asofs
    read_at: str
    host: str

    def by_result(self, result: str) -> tuple[Pair, ...]:
        return tuple(p for p in self.pairs if p.result == result)

    @property
    def verdict(self) -> str:
        """全体の結果。1 組でも止まれば 止まった、決まらなければ 決まらない。"""
        self._guard()
        for r in (RESULTS[3], RESULTS[2], RESULTS[1]):
            if self.by_result(r):
                return r
        return RESULTS[0]

    def by_reason(self) -> dict[str, int]:
        """止まった理由コード別の件数(宣言の順に並べる。率は返さない)。"""
        return {code: n for code in PAIR_REASONS
                if (n := sum(1 for p in self.pairs if p.reason == code))}

    def by_why(self) -> dict[str, int]:
        """決まらない理由別の件数(宣言の順に並べる。率は返さない)。"""
        return {why: n for why in UNDECIDED
                if (n := sum(1 for p in self.pairs if p.why == why))}

    @property
    def denominator(self) -> int:
        return self.report.groups * self.report.asofs

    def winners(self) -> dict[str, str]:
        """組 id と基準日 id ごとの勝った行 id(決まらなかった組は空のまま)。"""
        return {f"{p.group_id}/{p.asof_id}": p.row_id for p in self.pairs}

    def counts(self) -> dict[str, object]:
        """件数は理由別に、分母(組数 × 基準日の数)と内訳つきで出す。率は単独では返さない。"""
        four = {r: len(self.by_result(r)) for r in RESULTS}
        reason, why = self.by_reason(), self.by_why()
        out: dict[str, object] = {
            "裁定の宣言表の行数(rule 数)": self.report.rules,
            "候補の表の行数": self.report.rows,
            "組数": self.report.groups,
            "基準日の数": self.report.asofs,
            "分母(組数 × 基準日の数)": self.denominator,
            "4 値": four,
            "止まった理由別": reason,
            "決まらない理由別": why,
            "読んだか": ("読んだ" if self.pairs else
                         "読んでいない(表が揃う前に止まったので 4 値は全て 0)"),
        }
        out["分母に含めたもの"] = (
            f"組数 {self.report.groups} × 基準日の数 {self.report.asofs}"
            f" = {self.denominator} 組。4 値の内訳は "
            f"順位で決まった {four[RESULTS[0]]} + 比較で決まった {four[RESULTS[1]]}"
            f" + 比較では決まらない {four[RESULTS[2]]} + 止まった {four[RESULTS[3]]}。"
            "止まったの内訳は 止まった理由別、決まらないの内訳は 決まらない理由別 の欄")
        out["件数の合計の検算"] = (
            f"4 値の合計 {sum(four.values())} / 分母 {self.denominator}"
            f"(止まった理由別の合計 {sum(reason.values())} = 止まった"
            f" {four[RESULTS[3]]}、決まらない理由別の合計 {sum(why.values())}"
            f" = 比較では決まらない {four[RESULTS[2]]})")
        out["順位の列で比較を代えない"] = (
            "裁定の種類が「値の比較」の組では、順位の欄に値が入っていても比較の代わりに"
            "順位で決めない。順位を読む経路は、同値のときの扱いに「宣言された順位で裁定」と"
            "書いてある組の同値のときだけ")
        out["単位を揃えない"] = (
            "宣言の単位と行の単位が違う組は、換算せずに止まる。換算表も換算の引数も無い")
        out["丸めの前後に既定を当てない"] = (
            "丸めを比較の前にするか後にするかが空欄の組は、既定を当てずに止まる。"
            "宣言された前後のとおりにしか動かさない")
        out["同値を向きで勝たせない"] = (
            "「大きい方」でも同値なら決まらない。宣言が「宣言された順位で裁定」なら順位へ"
            "落とすが、順位も同じなら決まらない")
        out["式を評価しない"] = (
            "計算は宣言された丸め 1 段だけで、式を解く経路も、2 つの値から別の値を作る"
            "経路も無い。値は文字列から Decimal にして比べる(float を使わない)")
        return out

    def table(self) -> list[dict[str, object]]:
        """組ごとの読み。率の欄は無い。"""
        return [{"組 id": p.group_id, "rule id": p.rule_id, "基準日 id": p.asof_id,
                 "基準日": p.asof, "結果": p.result, "決まらない理由": p.why,
                 "止まった理由": p.reason, "内訳": p.detail, "勝った行 id": p.row_id,
                 "勝った値(丸めた後)": p.value, "経路": p.route, "候補の本数": p.hits}
                for p in self.pairs]

    def decided(self) -> list[dict[str, object]]:
        """決まった組だけを別に並べる(組 id と基準日 id の順。順位は付けない)。"""
        return [{"組 id": p.group_id, "基準日 id": p.asof_id, "結果": p.result,
                 "勝った行 id": p.row_id, "勝った値(丸めた後)": p.value,
                 "経路": p.route}
                for p in self.pairs if p.result in (RESULTS[0], RESULTS[1])]

    def judgement_bytes(self) -> bytes:
        """判定部分 = 読んだ組の表。時刻・絶対パス・ホスト名は入れない。"""
        self._guard()
        lines = ["\t".join(["組", str(self.report.groups), str(self.report.asofs),
                            str(self.denominator)])]
        for p in self.pairs:
            lines.append("\t".join([p.group_id, p.rule_id, p.asof_id, p.asof,
                                    p.result, p.why, p.reason, p.row_id, p.value,
                                    p.route, str(p.hits)]))
        return ("\n".join(lines) + "\n").encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.judgement_bytes()).hexdigest()

    def read_condition(self) -> dict[str, str]:
        return {SCOPE_KEYS[0]: self.declared.path, SCOPE_KEYS[1]: self.candidates.path,
                SCOPE_KEYS[2]: self.asofs.path, SCOPE_KEYS[3]: self.read_at,
                SCOPE_KEYS[4]: self.host}

    def _guard(self) -> None:
        if not self.report.ok:
            raise RuntimeError("止まっているので読んだ組は無い。"
                               "report.pending の理由コードを見る")


def compare_pick(declared: Declared, candidates: Candidates, asofs: Asofs) -> Table:
    """組ごとに、順位で決まるのか比較で決まるのかを宣言から読む。表が揃う前に止まったら
    1 組も読まない。"""
    now = datetime.datetime.now().isoformat(timespec="seconds")
    host = platform.node()
    for g in candidates.group_ids:
        if declared.of(candidates.rule_of(g)) is None:
            raise ReadError(f"候補の表が宣言表に無い rule を名乗っている: 組 {g} の "
                            f"{candidates.rule_of(g)}")
    pending = (list(declared.pending) + list(candidates.pending)
               + list(asofs.pending))

    def made(pend: tuple[Pending, ...], pairs: tuple[Pair, ...] = ()) -> Table:
        return Table(report=Report(not pend, pend, len(declared.items),
                                   len(candidates.items), len(candidates.group_ids),
                                   len(asofs.items)),
                     pairs=pairs, declared=declared, candidates=candidates,
                     asofs=asofs, read_at=now, host=host)

    if pending:                      # 表が揃う前に止まる(1 組も読まない)
        return made(tuple(pending))

    pairs: list[Pair] = []
    for group_id in candidates.group_ids:
        rows = candidates.of(group_id)
        rule = declared.of(rows[0].rule_id)
        for a in asofs.ordered:
            v = judge(rule, rows, a.asof)
            pairs.append(Pair(group_id=group_id, rule_id=rule.rule_id,
                              asof_id=a.asof_id, asof=a.asof.isoformat(),
                              result=v.result, why=v.why, reason=v.reason,
                              detail=v.detail, row_id=v.row_id, value=v.value,
                              route=v.route, hits=len(rows)))
    return made((), tuple(pairs))


def verify(declared: Declared, candidates: Candidates, asofs: Asofs) -> dict[str, object]:
    """2 回読んで sha256 を比べ、3 枚の行順を入れ替えても同じかを見て、件数を検算する。
    さらに、単位を片方書き換えた写しと、丸めの前後を入れ替えた写しを読んで差分を出す。"""
    first = compare_pick(declared, candidates, asofs)
    if not first.report.ok:
        return {"ok": False, "stage": "止まった(読んだ組は返さない)", **first.counts(),
                "pending": [p.as_dict() for p in first.report.pending]}
    if not asofs.swap:
        raise ReadError("基準日の表に入れ替え方(swap)が無いので verify は走らせない")
    second = compare_pick(declared, candidates, asofs)
    third = compare_pick(declared.swapped(asofs.swap), candidates.swapped(asofs.swap),
                         asofs.swapped(asofs.swap))
    pending: list[Pending] = []
    if first.sha256() != second.sha256():
        pending.append(Pending(STOP_REASONS[16], f"2 回目 {second.sha256()[:12]}"))
    if not (third.report.ok and first.sha256() == third.sha256()):
        pending.append(Pending(STOP_REASONS[17],
                               f"入れ替え方 {asofs.swap} の 3 枚で "
                               f"{third.sha256()[:12]}" if third.report.ok else
                               f"入れ替え方 {asofs.swap} の 3 枚では止まった"))
    four = {r: len(first.by_result(r)) for r in RESULTS}
    reason, why = first.by_reason(), first.by_why()
    if sum(four.values()) != first.denominator:
        pending.append(Pending(STOP_REASONS[15],
                               f"4 値の合計 {sum(four.values())}"
                               f" / 分母 {first.denominator}"))
    if sum(reason.values()) != four[RESULTS[3]]:
        pending.append(Pending(STOP_REASONS[15],
                               f"止まった理由別の合計 {sum(reason.values())}"
                               f" / 止まった {four[RESULTS[3]]}"))
    if sum(why.values()) != four[RESULTS[2]]:
        pending.append(Pending(STOP_REASONS[15],
                               f"決まらない理由別の合計 {sum(why.values())}"
                               f" / 比較では決まらない {four[RESULTS[2]]}"))
    out: dict[str, object] = {
        "ok": not pending, "読んだ結果": first.verdict, "読んだ回数": 2,
        "入れ替え方": asofs.swap, "sha256": first.sha256(),
        "2 回目の sha256": second.sha256(),
        "入れ替えた 3 枚の sha256": third.sha256() if third.report.ok else "",
        "件数の検算": {"4 値": four, "4 値の合計": sum(four.values()),
                       "止まった理由別の合計": sum(reason.values()),
                       "決まらない理由別の合計": sum(why.values()),
                       "分母(組数 × 基準日の数)": first.denominator},
        "単位を片方書き換えた写し": unit_probe(declared, candidates, asofs, first),
        "丸めの前後を入れ替えた写し": round_when_probe(declared, candidates, asofs, first),
    }
    if not out["単位を片方書き換えた写し"]["合うか"]:
        pending.append(Pending(STOP_REASONS[15],
                               "単位を書き換えた写しで、止まったの増えと"
                               "比較で決まったの減りが一致しない"))
        out["ok"] = False
    if pending:
        out["観測"] = ("同じ表から違うバイト列が出た、または件数が合わない(平均も"
                       "多数決もしない。どちらが正しいかも決めない)")
        out["pending"] = [p.as_dict() for p in pending]
    return out


CHANGED_UNIT = "verify が置いた別の単位"


def unit_probe(declared: Declared, candidates: Candidates, asofs: Asofs,
               first: Table) -> dict[str, object]:
    """比較で決まっていた組の単位を片方だけ書き換え、止まったの増えと決まったの減りを数える。"""
    whole = tuple(g for g in candidates.group_ids
                  if all(p.result == RESULTS[1]
                         for p in first.pairs if p.group_id == g))
    changed = compare_pick(declared, candidates.unit_changed(whole, CHANGED_UNIT),
                           asofs)
    before, after = first.by_reason(), changed.by_reason()
    grew = after.get(STOP_REASONS[6], 0) - before.get(STOP_REASONS[6], 0)
    shrank = (len(first.by_result(RESULTS[1])) - len(changed.by_result(RESULTS[1])))
    return {"書き換えた組": list(whole),
            "書き換えた欄": f"行 id が後の 1 行の単位を「{CHANGED_UNIT}」にした",
            "止まった(単位の不一致)の増え": grew,
            "比較で決まったの減り": shrank,
            "分母(組数 × 基準日の数)": first.denominator,
            "合うか": grew == shrank == len(whole) * first.report.asofs,
            "読み": ("単位を 1 欄書き換えると、その組は換算されずに止まる"
                     "(揃える経路が無いことの実測)")}


def round_when_probe(declared: Declared, candidates: Candidates, asofs: Asofs,
                     first: Table) -> dict[str, object]:
    """丸めの前後の宣言を入れ替えて、勝者が入れ替わる組を数える(同じ値・同じ向きのまま)。"""
    flipped = compare_pick(declared.round_when_swapped(), candidates, asofs)
    was, now = first.winners(), flipped.winners()
    swapped = [k for k in was if was[k] and now[k] and was[k] != now[k]]
    appeared = [k for k in was if bool(was[k]) != bool(now[k])]
    moved = [f"{p.group_id}/{p.asof_id}" for p, q in zip(first.pairs, flipped.pairs)
             if (p.result, p.why, p.reason) != (q.result, q.why, q.reason)]
    return {"入れ替えた rule": [r.rule_id for r in declared.ordered if r.by_compare
                                and r.round_when],
            "勝者が入れ替わった": len(swapped),
            "勝者が入れ替わった組": sorted(swapped),
            "勝者が付いた / 消えた": len(appeared),
            "結果が変わった": len(moved),
            "分母(組数 × 基準日の数)": first.denominator,
            "読み": ("値も向きも同じまま、丸めを比較の前にするか後にするかの宣言 1 欄で"
                     "勝者が入れ替わる組がある(同じ「高い方」が別の答えを返す、の実測)")}


# ------------------------------------------------------------ ひな型

TEMPLATE_DECLARED = [
    list(SENGEN_COLUMNS),
    ["R01", KINDS[1], "合成の欄A(架空)", DIRECTIONS[0], "合成の単位甲(架空)",
     ROUND_WHENS[1], ROUNDINGS[1], TIES[1], "合成の宣言メモ(架空)L1"],
]
TEMPLATE_CANDIDATES = [
    list(KOUHO_COLUMNS),
    ["P01", "R01", "G01", "10", "合成の欄A(架空)", "1026", "合成の単位甲(架空)",
     "2026-01-01", "2027-01-01", "合成の候補メモ(架空)L1"],
    ["P01", "R01", "G02", "0", "合成の欄A(架空)", "1049", "合成の単位甲(架空)",
     "2026-01-01", "2027-01-01", "合成の候補メモ(架空)L2"],
]
TEMPLATE_ASOFS = [
    list(KIJUNBI_COLUMNS),
    ["K01", "2026-04-01", "合成の基準日メモ(架空)L1", SWAPS[0]],
]


def write_csv(path: Path, rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    return path


def init(dest: str | Path) -> tuple[Path, Path, Path]:
    d = Path(dest)
    return (write_csv(d / "裁定の宣言表.csv", TEMPLATE_DECLARED),
            write_csv(d / "候補の表.csv", TEMPLATE_CANDIDATES),
            write_csv(d / "基準日の表.csv", TEMPLATE_ASOFS))


# ------------------------------------------------------------ CLI

def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def build_parser() -> argparse.ArgumentParser:
    """CLI は pick / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = argparse.ArgumentParser(prog="compare_pick",
                                 description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in SUBCOMMANDS[:3]:
        p = sub.add_parser(name)
        p.add_argument("declared")
        p.add_argument("candidates")
        p.add_argument("asofs")
    sub.add_parser(SUBCOMMANDS[3]).add_argument("dest")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == "init":
        print("書いた: " + " / ".join(str(p) for p in init(a.dest)))
        return 0
    try:
        declared, candidates = Declared.load(a.declared), Candidates.load(a.candidates)
        asofs = Asofs.load(a.asofs)
        if a.cmd == "verify":
            out = verify(declared, candidates, asofs)
            _print(out)
            return 0 if out["ok"] else 3
        t = compare_pick(declared, candidates, asofs)
    except ReadError as e:
        print(f"表として読めない: {e}", file=sys.stderr)
        return 2
    if not t.report.ok:
        _print({"ok": False, "stage": "止まった(読んだ組は返さない)", **t.counts(),
                "pending": [p.as_dict() for p in t.report.pending]})
        return 3
    body: dict[str, object] = {"ok": True, "読んだ結果": t.verdict, **t.counts()}
    if a.cmd == "pick":
        body["組ごと"] = t.table()
        body["決まった組の一覧"] = t.decided()
        body["sha256"] = t.sha256()
        body["読んだ条件"] = t.read_condition()
    _print(body)
    return 0 if not (t.by_result(RESULTS[2]) or t.by_result(RESULTS[3])) else 3


if __name__ == "__main__":
    raise SystemExit(main())
