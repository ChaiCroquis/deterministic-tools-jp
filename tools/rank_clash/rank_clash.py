"""rank_clash — 絞り終わって残った行が 1 本に決まるかを出す。引かない、決まるかを出すだけ。

**絞り終わって行が 2 本残ることは実際に起きる(本則と経過措置、地域別と産業別、公的な行と
事業所ごとの行)。そのとき勝つ行は、より具体的に書かれている方でも、後から書かれた方でも、
値の大きい方でもなく、順位の欄に宣言された方だけである。欄が無ければ黙ってどちらかが勝つ。**

この部品は、行の表・裁定の宣言・対象の表の 3 枚から、(rule × 対象)の組 1 つごとに 4 値
(**1 本に決まった / 当たらない / 決まらない / 止まった**)を付ける。決まらないものは理由別
(**同順位で 2 本以上 / 順位の欄が空 / 宣言に無い裁定が要る**)に分けて数え、分母(rule 数 ×
対象数)と内訳を併記して返す。

持たせていないものが規律になっている。

  - **具体さで勝たせない**(未指定次元が少ない行を勝たせる経路を持たない。宣言された記号で
    書かれた行と、具体的に書かれた行は、順位が同じなら同じ強さのまま並ぶ)
  - **行の並び順・後から書かれた順で勝たせない**(先頭・末尾・新しい方を採る引数が無い)
  - **値の大小で勝たせない**(高い方・低い方で勝たせる経路が無い。行の表に値の列が無い)
  - **順位の欄が空なら補わない**(空欄を 0 = 本則として扱わない)
  - **宣言に無い順位の値は使わずに止まる**(宣言された値の外が来たら意味を推測しない)
  - **同順位で 2 本以上なら「決まらない」に落ちる**(どちらでもよいにしない)
  - **未指定の記号を推測しない**(宣言された記号だけ。空欄と「未指定」の宣言を区別する)
  - **次元の優先順位を自分で決めない**(ある次元が別の次元より強い、を内蔵しない)
  - **日付で絞らない・期間も切らない・帯にも当てない・空欄の意味も読まない・日付の種別も
    決めない**(絞り終わった後の 1 段だけを持つ)
  - **件数は理由別に分母(rule 数 × 対象数)と内訳つきで出す**(率を単独で返さない)
  - **4 つを混ぜない**(1 本に決まった / 当たらない / 決まらない / 止まった)
  - **入力表を書き換えず、行も順位も生成しない**
  - **出典の欄が空の行は使わずに止まる**
  - **float を使わない**(件数と順位は整数、ほかは文字列のまま持つ)
  - **同じ入力には同じバイト列**(判定部分に時刻・絶対パス・ホスト名を入れない)

入力は 3 つ。行の表(CSV)、裁定の宣言(CSV)、対象の表(CSV)。

行の表の列は 5 つ。1 行が 1 行。

    row_id    行 id(空欄は「表として読めない」。2 行あると止まる)
    rule_id   その行が属する rule id。宣言表に無い rule は止まる
    seg       各次元の値。「名前=値」を縦棒で区切る。未指定は宣言された記号を書く
    priority  順位。**空欄のまま持つ**(0 と読み替えない)。整数でなければ読めない表
    source    出典。空欄は止まる

裁定の宣言の列は 6 つ。1 rule が 1 行。

    rule_id     rule id(空欄は「表として読めない」。2 行あると止まる)
    kind        使う裁定の種類。登録の 2 種(宣言された順位 / 宣言された順位では決まらない)
    priorities  許す順位の値と意味。「値=意味」を縦棒で区切る(例 0=本則|10=経過措置)
    wildcard    未指定次元の記号。**この記号だけが「未指定」になる**
    tie         同順位のときの扱い。登録の 1 種(例外にする)
    source      出典。空欄は止まる

対象の表の列は 4 つ。1 対象が 1 行。

    target_id   対象 id(空欄は「表として読めない」。2 行あると読めない表)
    seg         各次元の値。「名前=値」を縦棒で区切る。未指定に見える記号は書けない
    source      出典。空欄は止まる
    swap        入れ替え方。verify が 3 枚の行順を入れ替えるときの宣言。全行で同じ値

使い方:

    python rank_clash.py init ひな型/
    python rank_clash.py check   行の表.csv 裁定の宣言.csv 対象の表.csv
    python rank_clash.py resolve 行の表.csv 裁定の宣言.csv 対象の表.csv
    python rank_clash.py verify  行の表.csv 裁定の宣言.csv 対象の表.csv

終了コードは、決まらない組が 1 つも無いときだけ 0(当たらないが何件あっても 0)、決まらない
組があるときや止まったときは 3、表として読めなければ 2。
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
from pathlib import Path

GYOU_COLUMNS = ("row_id", "rule_id", "seg", "priority", "source")
SENGEN_COLUMNS = ("rule_id", "kind", "priorities", "wildcard", "tie", "source")
TAISHOU_COLUMNS = ("target_id", "seg", "source", "swap")

# 裁定の種類。登録の 2 種だけ(外は読めない表)
KINDS = ("宣言された順位", "宣言された順位では決まらない")
# 同順位のときの扱い。登録の 1 種だけ
TIES = ("例外にする",)
SWAPS = ("逆順", "両端入れ替え", "1 つずらす")

SEG_SEP = "|"
SEG_EQ = "="
PRIORITY_SEP = "|"
INTEGER = re.compile(r"\A(0|[1-9][0-9]*)\Z")

# 「未指定」に見える記号。宣言された記号と一致しない限り止まる(推測して読まない)
NITA_KIGOU = ("*", "-", "—", "ー", "全", "ALL", "all", "any", "なし", "指定なし")

# 4 値。混ぜない
RESULTS = ("1 本に決まった", "当たらない", "決まらない", "止まった")

# 決まらない理由。3 種
UNDECIDED = ("同順位で 2 本以上", "順位の欄が空", "宣言に無い裁定が要る")

# 止まる理由コード。9 個
STOP_REASONS = ("出典の欄が空", "行 id の重複", "宣言に無い順位の値",
                "未指定の記号が宣言外", "rule が宣言表に無い",
                "同じ rule に裁定の宣言が 2 行", "件数の合計が合わない",
                "2 回目の判定部分が不一致", "行順を入れ替えた表で出力が変わる")

SUBCOMMANDS = ("resolve", "check", "verify", "init")

# 判定部分に入れない欄(sha256 の対象にもしない)
SCOPE_KEYS = ("読んだ行の表の絶対パス", "読んだ裁定の宣言の絶対パス",
              "読んだ対象の表の絶対パス", "読んだ時刻", "ホスト名")


class ReadError(Exception):
    """表として読めない(理由コードにせず終了コード 2 で返す = 表を書く側の話)。"""


def parse_seg(text: str, where: str) -> tuple[tuple[str, str], ...]:
    """「名前=値」を縦棒で区切った次元の欄。順は入力に依らせない(並べ替えて持つ)。"""
    if not text.strip():
        raise ReadError(f"{where}: 次元の欄が空欄(未指定は宣言された記号を書く)")
    out: list[tuple[str, str]] = []
    for part in text.split(SEG_SEP):
        part = part.strip()
        if part.count(SEG_EQ) != 1:
            raise ReadError(f"{where}: 次元は「名前=値」で書く: {part or '空'}")
        name, value = (x.strip() for x in part.split(SEG_EQ))
        if not name:
            raise ReadError(f"{where}: 次元の名前が空欄")
        if not value:
            raise ReadError(f"{where}: 次元 {name} の値が空欄"
                            "(空欄と「未指定」の宣言は別のもの)")
        out.append((name, value))
    names = [n for n, _ in out]
    if len(set(names)) != len(names):
        raise ReadError(f"{where}: 同じ次元の名前が 2 つある")
    return tuple(sorted(out))


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


@dataclass(frozen=True)
class Pending:
    reason: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"reason": self.reason, "detail": self.detail}


# ------------------------------------------------------------ 行の表

@dataclass(frozen=True)
class Row:
    row_id: str
    rule_id: str
    seg: tuple[tuple[str, str], ...]
    priority: str          # 空欄のまま持つ(0 と読み替えない)
    source: str
    number: int

    @property
    def dims(self) -> tuple[str, ...]:
        return tuple(n for n, _ in self.seg)


@dataclass(frozen=True)
class Sheet:
    items: tuple[Row, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Sheet":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"行の表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Sheet":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in GYOU_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("行の表に " + " / ".join(lack) + " の列が無い")
        items: list[Row] = []
        pending: list[Pending] = []
        seen: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in GYOU_COLUMNS}
            where = f"行の表 行 {i}"
            if not cell["row_id"]:
                raise ReadError(f"{where}: 行 id が空欄")
            if not cell["rule_id"]:
                raise ReadError(f"{where}: rule id が空欄({cell['row_id']})")
            if cell["priority"] and not INTEGER.match(cell["priority"]):
                raise ReadError(f"{where}: 順位が整数でない({cell['priority']})")
            if cell["row_id"] in seen:
                pending.append(Pending(STOP_REASONS[1], f"{where}: {cell['row_id']}"))
            seen.add(cell["row_id"])
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0], f"{where}({cell['row_id']})"))
            items.append(Row(row_id=cell["row_id"], rule_id=cell["rule_id"],
                             seg=parse_seg(cell["seg"], f"{where} の次元"),
                             priority=cell["priority"], source=cell["source"],
                             number=i))
        if not items:
            raise ReadError("行の表に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    def of(self, rule_id: str) -> tuple[Row, ...]:
        """その rule の行を、行 id の順に並べて返す(表の行順には依らせない)。"""
        return tuple(sorted((r for r in self.items if r.rule_id == rule_id),
                            key=lambda r: r.row_id))

    @property
    def dims(self) -> tuple[str, ...]:
        return tuple(sorted({n for r in self.items for n in r.dims}))

    def swapped(self, how: str) -> "Sheet":
        return Sheet(items=tuple(swap_rows(list(self.items), how)),
                     pending=self.pending, path=self.path)


# ------------------------------------------------------------ 裁定の宣言

@dataclass(frozen=True)
class Rule:
    rule_id: str
    kind: str
    priorities: tuple[tuple[int, str], ...]
    wildcard: str
    tie: str
    source: str
    number: int

    @property
    def allowed(self) -> tuple[int, ...]:
        return tuple(v for v, _ in self.priorities)

    @property
    def by_priority(self) -> bool:
        """宣言された順位で比べてよい rule か(もう 1 種は比べずに決まらないへ落ちる)。"""
        return self.kind == KINDS[0]


def parse_priorities(text: str, where: str) -> tuple[tuple[int, str], ...]:
    """「値=意味」を縦棒で区切った、許す順位の一覧。"""
    out: list[tuple[int, str]] = []
    for part in text.split(PRIORITY_SEP):
        part = part.strip()
        if not part:
            continue
        if part.count(SEG_EQ) != 1:
            raise ReadError(f"{where}: 順位は「値=意味」で書く: {part}")
        value, meaning = (x.strip() for x in part.split(SEG_EQ))
        if not INTEGER.match(value):
            raise ReadError(f"{where}: 順位の値が整数でない({value or '空欄'})")
        if not meaning:
            raise ReadError(f"{where}: 順位 {value} の意味が空欄")
        out.append((int(value), meaning))
    if not out:
        raise ReadError(f"{where}: 許す順位が 1 つも書かれていない")
    values = [v for v, _ in out]
    if len(set(values)) != len(values):
        raise ReadError(f"{where}: 同じ順位の値が 2 つある")
    return tuple(sorted(out))


@dataclass(frozen=True)
class Declared:
    items: tuple[Rule, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Declared":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"裁定の宣言が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Declared":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in SENGEN_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("裁定の宣言に " + " / ".join(lack) + " の列が無い")
        items: list[Rule] = []
        pending: list[Pending] = []
        seen: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in SENGEN_COLUMNS}
            where = f"裁定の宣言 行 {i}"
            if not cell["rule_id"]:
                raise ReadError(f"{where}: rule id が空欄")
            if cell["kind"] not in KINDS:
                raise ReadError(f"{where}: 裁定の種類は {' / '.join(KINDS)} の宣言だけ"
                                f"({cell['kind'] or '空欄'})")
            if cell["tie"] not in TIES:
                raise ReadError(f"{where}: 同順位のときの扱いは "
                                f"{' / '.join(TIES)} の宣言だけ({cell['tie'] or '空欄'})")
            if not cell["wildcard"]:
                raise ReadError(f"{where}: 未指定次元の記号が空欄({cell['rule_id']})")
            if cell["rule_id"] in seen:
                pending.append(Pending(STOP_REASONS[5], f"{where}: {cell['rule_id']}"))
            seen.add(cell["rule_id"])
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0], f"{where}({cell['rule_id']})"))
            items.append(Rule(rule_id=cell["rule_id"], kind=cell["kind"],
                              priorities=parse_priorities(cell["priorities"],
                                                          f"{where} の順位"),
                              wildcard=cell["wildcard"], tie=cell["tie"],
                              source=cell["source"], number=i))
        if not items:
            raise ReadError("裁定の宣言に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    def of(self, rule_id: str) -> Rule | None:
        return next((r for r in self.items if r.rule_id == rule_id), None)

    @property
    def ordered(self) -> tuple[Rule, ...]:
        return tuple(sorted(self.items, key=lambda r: r.rule_id))

    def swapped(self, how: str) -> "Declared":
        return Declared(items=tuple(swap_rows(list(self.items), how)),
                        pending=self.pending, path=self.path)


# ------------------------------------------------------------ 対象の表

@dataclass(frozen=True)
class Target:
    target_id: str
    seg: tuple[tuple[str, str], ...]
    source: str
    number: int

    @property
    def dims(self) -> tuple[str, ...]:
        return tuple(n for n, _ in self.seg)


@dataclass(frozen=True)
class Targets:
    items: tuple[Target, ...]
    swap: str
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Targets":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"対象の表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Targets":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in TAISHOU_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("対象の表に " + " / ".join(lack) + " の列が無い")
        items: list[Target] = []
        pending: list[Pending] = []
        swaps: set[str] = set()
        seen: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in TAISHOU_COLUMNS}
            where = f"対象の表 行 {i}"
            if not cell["target_id"]:
                raise ReadError(f"{where}: 対象 id が空欄")
            if cell["target_id"] in seen:
                raise ReadError(f"{where}: 対象 id {cell['target_id']} が 2 行ある")
            seen.add(cell["target_id"])
            seg = parse_seg(cell["seg"], f"{where} の次元")
            for name, value in seg:
                if value in NITA_KIGOU:
                    raise ReadError(f"{where}: 対象の表に未指定に見える記号がある"
                                    f"({name}={value})")
            if cell["swap"]:
                if cell["swap"] not in SWAPS:
                    raise ReadError(f"{where}: 入れ替え方 {cell['swap']} は登録の外"
                                    f"({' / '.join(SWAPS)})")
                swaps.add(cell["swap"])
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0],
                                       f"{where}({cell['target_id']})"))
            items.append(Target(target_id=cell["target_id"], seg=seg,
                                source=cell["source"], number=i))
        if not items:
            raise ReadError("対象の表に行が無い(ヘッダだけ)")
        if len(swaps) > 1:
            raise ReadError("入れ替え方の宣言が 2 通り以上ある: "
                            + " / ".join(sorted(swaps)))
        return cls(items=tuple(items), swap=next(iter(swaps), ""),
                   pending=tuple(pending), path=path)

    @property
    def ordered(self) -> tuple[Target, ...]:
        return tuple(sorted(self.items, key=lambda t: t.target_id))

    @property
    def dims(self) -> tuple[str, ...]:
        return tuple(sorted({n for t in self.items for n in t.dims}))

    def swapped(self, how: str) -> "Targets":
        return Targets(items=tuple(swap_rows(list(self.items), how)), swap=self.swap,
                       pending=self.pending, path=self.path)


# ------------------------------------------------------------ 当たるかを見る

def touches(rule: Rule, row: Row, target: Target) -> bool:
    """その行がその対象に当たるか。未指定は宣言された記号のときだけ素通りする。"""
    value_of = dict(target.seg)
    for name, value in row.seg:
        if value == rule.wildcard:
            continue
        if value_of.get(name) != value:
            return False
    return True


# ------------------------------------------------------------ 決まるかを出す

@dataclass(frozen=True)
class Pair:
    """(rule × 対象)1 組の読み。引かないので、値も日付も持たない。"""
    rule_id: str
    target_id: str
    result: str
    why: str = ""          # 決まらないときだけ、3 種のどれか
    row_id: str = ""       # 1 本に決まったときだけ、勝った行 id
    priority: str = ""     # 1 本に決まったときだけ、その行の順位(空欄なら空のまま)
    hits: int = 0          # その組に当たった行の本数


@dataclass(frozen=True)
class Report:
    ok: bool
    pending: tuple[Pending, ...]
    sheet_rows: int
    rules: int
    targets: int


@dataclass(frozen=True)
class Table:
    report: Report
    pairs: tuple[Pair, ...]
    sheet: Sheet
    declared: Declared
    targets: Targets
    read_at: str
    host: str

    # -------------------------------------------------- 4 値と分母
    def by_result(self, result: str) -> tuple[Pair, ...]:
        return tuple(p for p in self.pairs if p.result == result)

    @property
    def verdict(self) -> str:
        """全体の結果。1 組でも決まらなければ 決まらない。"""
        self._guard()
        if self.by_result(RESULTS[2]):
            return RESULTS[2]
        if self.by_result(RESULTS[1]):
            return RESULTS[1]
        return RESULTS[0]

    def by_why(self) -> dict[str, int]:
        """決まらない理由別の件数(宣言の順に並べる。率は返さない)。"""
        out: dict[str, int] = {}
        for why in UNDECIDED:
            n = sum(1 for p in self.pairs if p.why == why)
            if n:
                out[why] = n
        return out

    @property
    def denominator(self) -> int:
        return self.report.rules * self.report.targets

    def counts(self) -> dict[str, object]:
        """件数は理由別に、分母(rule 数 × 対象数)と内訳つきで出す。率は単独で返さない。"""
        four = {r: len(self.by_result(r)) for r in RESULTS}
        why = self.by_why()
        out: dict[str, object] = {
            "行の表の行数": self.report.sheet_rows,
            "裁定の宣言の行数(rule 数)": self.report.rules,
            "対象数": self.report.targets,
            "分母(rule 数 × 対象数)": self.denominator,
            "4 値": four,
            "決まらない理由別": why,
            "読んだか": ("読んだ" if self.pairs else
                         "読んでいない(表が揃う前に止まったので 4 値は全て 0)"),
        }
        out["分母に含めたもの"] = (
            f"rule 数 {self.report.rules} × 対象数 {self.report.targets}"
            f" = {self.denominator} 組。4 値の内訳は "
            f"1 本に決まった {four[RESULTS[0]]} + 当たらない {four[RESULTS[1]]}"
            f" + 決まらない {four[RESULTS[2]]} + 止まった {four[RESULTS[3]]}。"
            f"決まらないの内訳は 決まらない理由別 の欄に出した")
        out["件数の合計の検算"] = (
            f"4 値の合計 {sum(four.values())} / 分母 {self.denominator}"
            f"(決まらない理由別の合計 {sum(why.values())} = 決まらない"
            f" {four[RESULTS[2]]})")
        out["具体さで勝たせない"] = (
            "宣言された記号で書かれた行と、具体的に書かれた行を、同じ強さのまま並べた。"
            "未指定次元の少ない行を勝たせる経路も、次元の優先順位を内蔵する経路も無い")
        out["並び順で勝たせない"] = (
            "行の表の並び順も、後から書かれた順も見ていない。先頭・末尾・新しい方を"
            "採る引数が無く、3 枚の行順を入れ替えても同じバイト列になる")
        out["値の大小で勝たせない"] = (
            "行の表に値の列が無い。高い方・低い方で勝たせる経路を持たないので、"
            "値で決まる裁定は「決まらない」に落ちる")
        out["順位の欄が空なら補わない"] = (
            "空欄の順位を 0(本則)として扱わない。2 本以上当たった組に空欄が混じって"
            "いたら、比べずに「決まらない」へ落とす")
        return out

    def table(self) -> list[dict[str, object]]:
        """組ごとの読み。率の欄は無い。"""
        return [{"rule id": p.rule_id, "対象 id": p.target_id, "結果": p.result,
                 "決まらない理由": p.why, "勝った行 id": p.row_id,
                 "その行の順位": p.priority, "当たった本数": p.hits}
                for p in self.pairs]

    def decided(self) -> list[dict[str, object]]:
        """1 本に決まった組だけを別に並べる(rule id と対象 id の順。順位は付けない)。"""
        return [{"rule id": p.rule_id, "対象 id": p.target_id, "勝った行 id": p.row_id,
                 "その行の順位": p.priority, "当たった本数": p.hits}
                for p in self.pairs if p.result == RESULTS[0]]

    # -------------------------------------------------- 判定部分
    def judgement_bytes(self) -> bytes:
        """判定部分 = 読んだ組の表。時刻・絶対パス・ホスト名は入れない。"""
        self._guard()
        lines = ["\t".join(["組", str(self.report.rules), str(self.report.targets),
                            str(self.denominator)])]
        for p in self.pairs:
            lines.append("\t".join([p.rule_id, p.target_id, p.result, p.why,
                                    p.row_id, p.priority, str(p.hits)]))
        return ("\n".join(lines) + "\n").encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.judgement_bytes()).hexdigest()

    def read_condition(self) -> dict[str, str]:
        return {SCOPE_KEYS[0]: self.sheet.path, SCOPE_KEYS[1]: self.declared.path,
                SCOPE_KEYS[2]: self.targets.path, SCOPE_KEYS[3]: self.read_at,
                SCOPE_KEYS[4]: self.host}

    def _guard(self) -> None:
        if not self.report.ok:
            raise RuntimeError("止まっているので読んだ組は無い。"
                               "report.pending の理由コードを見る")


def rank_clash(sheet: Sheet, declared: Declared, targets: Targets) -> Table:
    """残った行が宣言から 1 本に決まるかを出す。表が揃う前に止まったら 1 組も読まない。"""
    now = datetime.datetime.now().isoformat(timespec="seconds")
    host = platform.node()
    # 3 枚の次元の名前が揃っていないと、当たるかどうかを比べる土台が無い
    if sheet.dims != targets.dims:
        raise ReadError("次元の名前が表ごとに違う: 行の表 "
                        + " / ".join(sheet.dims) + "、対象の表 "
                        + " / ".join(targets.dims))
    pending = list(sheet.pending) + list(declared.pending) + list(targets.pending)

    for r in sheet.items:
        rule = declared.of(r.rule_id)
        if rule is None:
            pending.append(Pending(STOP_REASONS[4],
                                   f"行の表 行 {r.number}({r.row_id}): {r.rule_id}"))
            continue
        if r.priority and int(r.priority) not in rule.allowed:
            pending.append(Pending(STOP_REASONS[2],
                                   f"行の表 行 {r.number}({r.row_id}): "
                                   f"{r.priority} は {r.rule_id} の宣言 "
                                   + " / ".join(str(v) for v in rule.allowed)
                                   + " に無い"))
        for name, value in r.seg:
            if value != rule.wildcard and value in NITA_KIGOU:
                pending.append(Pending(STOP_REASONS[3],
                                       f"行の表 行 {r.number}({r.row_id}): "
                                       f"{name}={value}(宣言された記号は "
                                       f"{rule.wildcard})"))

    def made(pend: tuple[Pending, ...], pairs: tuple[Pair, ...] = ()) -> Table:
        return Table(report=Report(not pend, pend, len(sheet.items),
                                   len(declared.items), len(targets.items)),
                     pairs=pairs, sheet=sheet, declared=declared, targets=targets,
                     read_at=now, host=host)

    if pending:                      # 表が揃う前に止まる(1 組も読まない)
        return made(tuple(pending))

    pairs: list[Pair] = []
    for rule in declared.ordered:
        for t in targets.ordered:
            hit = [r for r in sheet.of(rule.rule_id) if touches(rule, r, t)]
            n = len(hit)
            if n == 0:
                pairs.append(Pair(rule.rule_id, t.target_id, RESULTS[1], hits=0))
            elif n == 1:
                pairs.append(Pair(rule.rule_id, t.target_id, RESULTS[0],
                                  row_id=hit[0].row_id, priority=hit[0].priority,
                                  hits=1))
            elif not rule.by_priority:
                # 宣言が「順位では決まらない」と言っている。順位で比べない
                pairs.append(Pair(rule.rule_id, t.target_id, RESULTS[2],
                                  why=UNDECIDED[2], hits=n))
            elif any(not r.priority for r in hit):
                # 空欄を 0(本則)として扱わない
                pairs.append(Pair(rule.rule_id, t.target_id, RESULTS[2],
                                  why=UNDECIDED[1], hits=n))
            else:
                top = max(int(r.priority) for r in hit)
                best = [r for r in hit if int(r.priority) == top]
                if len(best) == 1:
                    pairs.append(Pair(rule.rule_id, t.target_id, RESULTS[0],
                                      row_id=best[0].row_id,
                                      priority=best[0].priority, hits=n))
                else:
                    # どちらでもよいにしない。先に出てきた方も採らない
                    pairs.append(Pair(rule.rule_id, t.target_id, RESULTS[2],
                                      why=UNDECIDED[0], hits=n))
    return made((), tuple(pairs))


def verify(sheet: Sheet, declared: Declared, targets: Targets) -> dict[str, object]:
    """2 回読んで sha256 を比べ、3 枚の行順を入れ替えても同じかを見て、件数を検算する。"""
    first = rank_clash(sheet, declared, targets)
    if not first.report.ok:
        return {"ok": False, "stage": "止まった(読んだ組は返さない)", **first.counts(),
                "pending": [p.as_dict() for p in first.report.pending]}
    if not targets.swap:
        raise ReadError("対象の表に入れ替え方(swap)が無いので verify は走らせない")
    second = rank_clash(sheet, declared, targets)
    third = rank_clash(sheet.swapped(targets.swap), declared.swapped(targets.swap),
                       targets.swapped(targets.swap))
    pending: list[Pending] = []
    if first.sha256() != second.sha256():
        pending.append(Pending(STOP_REASONS[7], f"2 回目 {second.sha256()[:12]}"))
    if not (third.report.ok and first.sha256() == third.sha256()):
        pending.append(Pending(STOP_REASONS[8],
                               f"入れ替え方 {targets.swap} の 3 枚で "
                               f"{third.sha256()[:12]}" if third.report.ok else
                               f"入れ替え方 {targets.swap} の 3 枚では止まった"))
    four = {r: len(first.by_result(r)) for r in RESULTS}
    why = first.by_why()
    if sum(four.values()) != first.denominator:
        pending.append(Pending(STOP_REASONS[6],
                               f"4 値の合計 {sum(four.values())}"
                               f" / 分母 {first.denominator}"))
    if sum(why.values()) != four[RESULTS[2]]:
        pending.append(Pending(STOP_REASONS[6],
                               f"決まらない理由別の合計 {sum(why.values())}"
                               f" / 決まらない {four[RESULTS[2]]}"))
    out: dict[str, object] = {
        "ok": not pending, "読んだ結果": first.verdict, "読んだ回数": 2,
        "入れ替え方": targets.swap, "sha256": first.sha256(),
        "2 回目の sha256": second.sha256(),
        "入れ替えた 3 枚の sha256": third.sha256() if third.report.ok else "",
        "件数の検算": {"4 値": four, "4 値の合計": sum(four.values()),
                       "決まらない理由別の合計": sum(why.values()),
                       "分母(rule 数 × 対象数)": first.denominator},
    }
    if pending:
        out["観測"] = ("同じ表から違うバイト列が出た(平均も多数決もしない。"
                       "どちらが正しいかも決めない)")
        out["pending"] = [p.as_dict() for p in pending]
    return out


# ------------------------------------------------------------ ひな型

TEMPLATE_SHEET = [
    list(GYOU_COLUMNS),
    ["G01", "R01", "合成の次元A(架空)=*|合成の次元B(架空)=*", "0",
     "合成の行メモ(架空)L1"],
    ["G02", "R01", "合成の次元A(架空)=合成の値1(架空)|合成の次元B(架空)=*", "10",
     "合成の行メモ(架空)L2"],
]
TEMPLATE_DECLARED = [
    list(SENGEN_COLUMNS),
    ["R01", KINDS[0], "0=本則|10=経過措置|20=特例", "*", TIES[0],
     "合成の宣言メモ(架空)L1"],
]
TEMPLATE_TARGETS = [
    list(TAISHOU_COLUMNS),
    ["T01", "合成の次元A(架空)=合成の値1(架空)|合成の次元B(架空)=合成の値3(架空)",
     "合成の対象メモ(架空)L1", SWAPS[0]],
    ["T02", "合成の次元A(架空)=合成の値2(架空)|合成の次元B(架空)=合成の値3(架空)",
     "合成の対象メモ(架空)L2", ""],
]


def write_csv(path: Path, rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    return path


def init(dest: str | Path) -> tuple[Path, Path, Path]:
    d = Path(dest)
    return (write_csv(d / "行の表.csv", TEMPLATE_SHEET),
            write_csv(d / "裁定の宣言.csv", TEMPLATE_DECLARED),
            write_csv(d / "対象の表.csv", TEMPLATE_TARGETS))


# ------------------------------------------------------------ CLI

def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def build_parser() -> argparse.ArgumentParser:
    """CLI は resolve / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = argparse.ArgumentParser(prog="rank_clash",
                                 description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in SUBCOMMANDS[:3]:
        p = sub.add_parser(name)
        p.add_argument("sheet")
        p.add_argument("declared")
        p.add_argument("targets")
    sub.add_parser(SUBCOMMANDS[3]).add_argument("dest")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == "init":
        print("書いた: " + " / ".join(str(p) for p in init(a.dest)))
        return 0
    try:
        sheet, declared = Sheet.load(a.sheet), Declared.load(a.declared)
        targets = Targets.load(a.targets)
        if a.cmd == "verify":
            out = verify(sheet, declared, targets)
            _print(out)
            return 0 if out["ok"] else 3
        t = rank_clash(sheet, declared, targets)
    except ReadError as e:
        print(f"表として読めない: {e}", file=sys.stderr)
        return 2
    if not t.report.ok:
        _print({"ok": False, "stage": "止まった(読んだ組は返さない)", **t.counts(),
                "pending": [p.as_dict() for p in t.report.pending]})
        return 3
    body: dict[str, object] = {"ok": True, "読んだ結果": t.verdict, **t.counts()}
    if a.cmd == "resolve":
        body["組ごと"] = t.table()
        body["1 本に決まった組の一覧"] = t.decided()
        body["sha256"] = t.sha256()
        body["読んだ条件"] = t.read_condition()
    _print(body)
    return 0 if not t.by_result(RESULTS[2]) else 3


if __name__ == "__main__":
    raise SystemExit(main())
