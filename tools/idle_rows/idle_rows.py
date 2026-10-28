"""idle_rows — 収録済みの行のうち、どの式・どの問いからも参照されないものを数える。

**引ける状態にした行と、どれかの問いが実際に参照する行は別で、参照されない行を塊に
積んでも答えは変わらない。**

この部品は、行の台帳・参照の宣言表・問いの一覧の 3 枚(と理由コードの登録表)から、
rule 1 件ごとに 6 値(**参照されている / どの参照元からも参照されない / 参照元は在るが
問いから呼ばれない / 参照の宣言が無い / 照合専用** の 5 値 + 別枠 **基準日より後に
有効になる行**)を付け、滞留している行数を **一次の空白と二次の空白に分けて** 返す。
**引かない。計算しない。式を評価しない。時計を読まない。数えるだけだ。**

持たせていないものが規律になっている。

  - **参照を推測で補わない**(rule 名の文字列が近いから参照と見なす経路が無い。宣言表に
    無い組は参照 0 として数え、「収録済だから参照されているはず」の既定を持たない)
  - **滞留の理由を決めない**(理由コードが登録表に無い行は別枠の一覧に出すだけで、理由を
    当てる経路が無い。理由コードは判定に 1 度も使わない)
  - **照合専用と宣言された行を滞留に数えない**(由来の欄が照合専用の行は別の値に出て、
    滞留している行数に足される経路が無い)
  - **一次の空白と二次の空白を同じ列に潰さない**(どの参照元からも指されない行と、指す
    参照元は在るがその参照元を呼ぶ問いが無い行を、別の値と別の行数で返す。これが骨の
    物理形)
  - **未来有効行を滞留に混ぜない**(基準日は必ず問いの一覧の列で、有効開始日が基準日より
    後の行は別枠。現在時刻を読む経路が無い)
  - **大きさを見積もらない**(返るのは rule の数と行数だけ。長さや量を掛ける経路が無く、
    減る分を主張する経路も無い)
  - **参照されない行の是非を判定しない**(出力に順位の欄も勧めの欄も無い。残すかどうかは
    表を持つ人が決める)
  - **件数を割合にしない**(件数と 3 つの分母の内訳だけ。参照の度合いを返す経路が無い)
  - **実際に何回呼ばれたかは数えない**(呼び出しの記録を読む経路が無い。数えるのは宣言の
    上での参照だけで、そのことを入力の形で明示する)
  - **出典の欄が空の行は使わずに止まる**
  - **行を引かない・値を計算しない・式を評価しない・原文を取りに行かない**(評価器も
    ネットワーク経路も持たない)
  - **入力表を書き換えず、行も宣言も生成しない**
  - **同じ入力には同じバイト列**(判定部分に時刻・絶対パス・ホスト名を入れない。行順にも
    依らない)
  - **数は整数だけ**(行数も件数も整数で、float を使う経路が無い)

入力は 3 つ。行の台帳(CSV)、参照の宣言表(CSV)、問いの一覧(CSV)。別に理由コードの
登録表(CSV)を取る。

行の台帳の列は 8 つ。**1 つの rule が 1 行**。

    table_id        数表 id
    rule_id         rule id(同じ id が 2 行あると止まる)
    rows            行数(0 以上の整数)
    origin          由来(自前抽出 / 上流 / 照合専用。登録外は読めない)
    valid_from      有効開始日(空欄可。`YYYY-MM-DD`。基準日より後なら別枠)
    reason          滞留の理由コード(空欄可。登録表に無ければ別枠の一覧へ)
    reason_source   理由の出典(登録表が「要る」と言うコードで空欄なら止まる)
    source          出典(ファイル名 + 行番号)。空欄は止まる

参照の宣言表の列は 5 つ。**1 つの (参照元, rule) の組が 1 行**。

    ref_id      参照元 id(式 または 問い の id)
    ref_kind    参照元の種別(式 / 問い。登録外は読めない)
    rule_id     参照する rule id(台帳に無い id は別枠の一覧へ)
    how         参照の仕方(式の入力 / 問いが直接引く / 別の式経由)。**判定には使わない**
    source      出典。空欄は止まる

問いの一覧の列は 6 つ。**1 つの (問い, 要る参照元) の組が 1 行**。

    question_id   問い id(同じ id が 2 行あると読めない)
    wants         求める値
    needs         その値に要る参照元 id(1 行に 1 つ。区切り文字で並べる経路が無い)
    asof          **基準日**。1 行だけ埋める(2 通りあると読めない、1 つも無いと読めない)
    swap          入れ替え方(逆順 / 両端入れ替え / 1 つずらす)。verify が使う宣言
    source        出典。空欄は止まる

理由コードの登録表の列は 3 つ。**1 つのコードが 1 行**(ヘッダだけでも読める)。

    code            理由コード
    means           意味
    source_needed   出典が要るか(要る / 要らない。登録外は読めない)

使い方:

    python idle_rows.py init ひな型/
    python idle_rows.py check 行の台帳.csv 参照の宣言.csv 問いの一覧.csv 理由コード.csv
    python idle_rows.py idle  行の台帳.csv 参照の宣言.csv 問いの一覧.csv 理由コード.csv
    python idle_rows.py verify 行の台帳.csv 参照の宣言.csv 問いの一覧.csv 理由コード.csv

終了コードは、別枠と止まった行が 0 件のときだけ 0、在れば 3、表として読めなければ 2。
**参照されない行を残すべきかどうかは、終了コードにも出力にも出さない。**
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

DAICHOU_COLUMNS = ("table_id", "rule_id", "rows", "origin", "valid_from", "reason",
                   "reason_source", "source")
SENGEN_COLUMNS = ("ref_id", "ref_kind", "rule_id", "how", "source")
TOI_COLUMNS = ("question_id", "wants", "needs", "asof", "swap", "source")
RIYUU_COLUMNS = ("code", "means", "source_needed")

ORIGINS = ("自前抽出", "上流", "照合専用")
SHOUGOU = ORIGINS[2]
REF_KINDS = ("式", "問い")
HOWS = ("式の入力", "問いが直接引く", "別の式経由")
HOW_OF_KIND = {REF_KINDS[0]: (HOWS[0], HOWS[2]), REF_KINDS[1]: (HOWS[1],)}
SOURCE_NEEDED = ("要る", "要らない")

KEKKA = ("参照されている", "どの参照元からも参照されない",
         "参照元は在るが問いから呼ばれない", "参照の宣言が無い", "照合専用",
         "基準日より後に有効になる行")
GOCHI = KEKKA[:5]          # 5 値
SOTO = KEKKA[5]            # 別枠 1 種
TAIRYUU = KEKKA[1:3]       # 滞留 2 値(一次の空白 / 二次の空白)
KUUHAKU = ("一次の空白", "二次の空白", "合計")

SWAPS = ("逆順", "両端入れ替え", "1 つずらす")

STOP_REASONS = (
    # 表の側。1 行も数えずに止まる(10)
    "出典の欄が空",
    "同じ rule id が台帳に 2 行ある",
    "同じ rule id が 2 つの数表に跨っている",
    "同じ参照元 id と rule id の組が宣言表に 2 行ある",
    "登録表が出典を要ると言うコードなのに理由の出典が空",
    "照合専用の行に滞留の理由コードが入っている",
    "照合専用の行を指す参照の宣言が在る",
    "問いが要る参照元を指す宣言が 1 行も無い",
    "参照元の種別が問いなのに問いの一覧に無い",
    "参照元の種別と参照の仕方が食い違う",
    # verify が見つける(3)
    "件数の合計が合わない", "2 回目の判定部分が不一致", "行順を入れ替えた表で出力が変わる",
)
TABLE_REASONS = STOP_REASONS[:10]
VERIFY_REASONS = STOP_REASONS[10:]

SUBCOMMANDS = ("idle", "check", "verify", "init")
SCOPE_KEYS = ("読んだ行の台帳の絶対パス", "読んだ参照の宣言表の絶対パス",
              "読んだ問いの一覧の絶対パス", "読んだ理由コードの登録表の絶対パス")

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


def day_number(s: str) -> int:
    """`YYYY-MM-DD` を通算日の整数に直す。**時計を読む経路が無い**(引数は必ず文字列)。"""
    parts = s.split("-")
    if len(parts) != 3 or [len(p) for p in parts] != [4, 2, 2] \
            or not all(p.isascii() and p.isdigit() for p in parts):
        raise ReadError(f"日付が YYYY-MM-DD の形でない: {s or '空欄'}")
    y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
    if not 1 <= m <= 12:
        raise ReadError(f"月が 1〜12 でない: {s}")
    leap = y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
    last = 29 if (m == 2 and leap) else MONTH_DAYS[m - 1]
    if not 1 <= d <= last:
        raise ReadError(f"その月に無い日付: {s}")
    m2 = (m + 9) % 12
    y2 = y - m2 // 10
    return (365 * y2 + y2 // 4 - y2 // 100 + y2 // 400
            + (m2 * 306 + 5) // 10 + (d - 1))


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


# ------------------------------------------------------------ 理由コードの登録表


@dataclass(frozen=True)
class Reason:
    """理由コード 1 つ。**意味は人が書いたものを持つだけで、道具が当てる経路が無い。**"""
    code: str
    means: str
    source_needed: str

    @property
    def needs_source(self) -> bool:
        return self.source_needed == SOURCE_NEEDED[0]


@dataclass(frozen=True)
class Registry:
    items: tuple[Reason, ...]
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Registry":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"理由コードの登録表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Registry":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in RIYUU_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("理由コードの登録表に " + " / ".join(lack) + " の列が無い")
        items: list[Reason] = []
        seen: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in RIYUU_COLUMNS}
            where = f"理由コードの登録表 行 {i}"
            if bad_id(cell["code"]):
                raise ReadError(f"{where}: コードが空欄か、区切り文字を含む"
                                f"({cell['code'] or '空欄'})")
            if cell["source_needed"] not in SOURCE_NEEDED:
                raise ReadError(f"{where}: 出典が要るかが登録の 2 つでない"
                                f"({cell['source_needed'] or '空欄'})")
            if cell["code"] in seen:
                raise ReadError(f"{where}: 同じコードが 2 行ある({cell['code']})")
            seen.add(cell["code"])
            items.append(Reason(cell["code"], cell["means"], cell["source_needed"]))
        return cls(items=tuple(items), path=path)

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(r.code for r in self.items)

    def of(self, code: str) -> Reason | None:
        """**登録に無いコードには何も当てない**(None を返す = 別枠の一覧へ)。"""
        return next((r for r in self.items if r.code == code), None)


# ------------------------------------------------------------ 行の台帳


@dataclass(frozen=True)
class Row:
    """台帳 1 行 = 1 rule。**行数はここに書かれた数だけで、推し測る経路が無い。**"""
    table_id: str
    rule_id: str
    rows: int
    origin: str
    valid_from: str
    reason: str
    reason_source: str
    source: str
    number: int = 0

    @property
    def shougou(self) -> bool:
        """引く対象でないと宣言された行(照合専用)。**滞留には数えない。**"""
        return self.origin == SHOUGOU

    def issues(self, registry: Registry) -> tuple[Pending, ...]:
        where = f"行の台帳 行 {self.number}({self.rule_id})"
        out: list[Pending] = []
        if not self.source:
            out.append(Pending(STOP_REASONS[0], where))
        if self.shougou and self.reason:
            out.append(Pending(STOP_REASONS[5], f"{where}: {self.reason}"))
        known = registry.of(self.reason) if self.reason else None
        if known is not None and known.needs_source and not self.reason_source:
            out.append(Pending(STOP_REASONS[4], f"{where}: {self.reason}"))
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
            for key, name in (("table_id", "数表 id"), ("rule_id", "rule id")):
                if bad_id(cell[key]):
                    raise ReadError(f"{where}: {name}が空欄か、区切り文字を含む"
                                    f"({cell[key] or '空欄'})")
            if cell["origin"] not in ORIGINS:
                raise ReadError(f"{where}: 由来が登録の 3 つでない"
                                f"({cell['origin'] or '空欄'})")
            count = whole(cell["rows"], "行数", where)
            if cell["valid_from"]:
                day_number(cell["valid_from"])      # 形が違えば読めない
            if cell["rule_id"] in seen:
                code = STOP_REASONS[1] if seen[cell["rule_id"]] == cell["table_id"] \
                    else STOP_REASONS[2]
                pending.append(Pending(code, f"{where}: {cell['rule_id']}"))
            seen[cell["rule_id"]] = cell["table_id"]
            items.append(Row(table_id=cell["table_id"], rule_id=cell["rule_id"],
                             rows=count, origin=cell["origin"],
                             valid_from=cell["valid_from"], reason=cell["reason"],
                             reason_source=cell["reason_source"],
                             source=cell["source"], number=i))
        if not items:
            raise ReadError("行の台帳に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    @property
    def ordered(self) -> tuple[Row, ...]:
        """数表 id → rule id の順(行順に依らない = 入れ替えても同じ出力)。"""
        return tuple(sorted(self.items, key=lambda r: (r.table_id, r.rule_id)))

    @property
    def tables(self) -> tuple[str, ...]:
        return tuple(sorted({r.table_id for r in self.items}))

    @property
    def total_rows(self) -> int:
        return sum(r.rows for r in self.items)

    def of(self, rule_id: str) -> Row | None:
        return next((r for r in self.ordered if r.rule_id == rule_id), None)

    def in_table(self, table_id: str) -> tuple[Row, ...]:
        return tuple(r for r in self.ordered if r.table_id == table_id)

    def swapped(self, how: str) -> "Ledger":
        return Ledger(items=tuple(swap_rows(list(self.items), how)),
                      pending=self.pending, path=self.path)


# ------------------------------------------------------------ 参照の宣言表


@dataclass(frozen=True)
class Ref:
    """宣言 1 行 = (参照元, rule) の 1 組。**参照の仕方は記録するだけで判定に使わない。**"""
    ref_id: str
    ref_kind: str
    rule_id: str
    how: str
    source: str
    number: int = 0

    def issues(self) -> tuple[Pending, ...]:
        where = (f"参照の宣言表 行 {self.number}"
                 f"({self.ref_id} → {self.rule_id})")
        out: list[Pending] = []
        if not self.source:
            out.append(Pending(STOP_REASONS[0], where))
        if self.how not in HOW_OF_KIND[self.ref_kind]:
            out.append(Pending(STOP_REASONS[9],
                               f"{where}: {self.ref_kind} / {self.how}"))
        return tuple(out)


@dataclass(frozen=True)
class Declarations:
    items: tuple[Ref, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Declarations":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"参照の宣言表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Declarations":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in SENGEN_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("参照の宣言表に " + " / ".join(lack) + " の列が無い")
        items: list[Ref] = []
        pending: list[Pending] = []
        seen: set[tuple[str, str]] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in SENGEN_COLUMNS}
            where = f"参照の宣言表 行 {i}"
            for key, name in (("ref_id", "参照元 id"), ("rule_id", "rule id")):
                if bad_id(cell[key]):
                    raise ReadError(f"{where}: {name}が空欄か、区切り文字を含む"
                                    f"({cell[key] or '空欄'})")
            if cell["ref_kind"] not in REF_KINDS:
                raise ReadError(f"{where}: 参照元の種別が登録の 2 つでない"
                                f"({cell['ref_kind'] or '空欄'})")
            if cell["how"] not in HOWS:
                raise ReadError(f"{where}: 参照の仕方が登録の 3 つでない"
                                f"({cell['how'] or '空欄'})")
            pair = (cell["ref_id"], cell["rule_id"])
            if pair in seen:
                pending.append(Pending(STOP_REASONS[3],
                                       f"{where}: {' → '.join(pair)}"))
            seen.add(pair)
            items.append(Ref(ref_id=cell["ref_id"], ref_kind=cell["ref_kind"],
                             rule_id=cell["rule_id"], how=cell["how"],
                             source=cell["source"], number=i))
        if not items:
            raise ReadError("参照の宣言表に行が無い(ヘッダだけ)")
        for ref in items:
            pending.extend(ref.issues())
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    @property
    def ordered(self) -> tuple[Ref, ...]:
        return tuple(sorted(self.items, key=lambda r: (r.rule_id, r.ref_id)))

    @property
    def ref_ids(self) -> tuple[str, ...]:
        return tuple(sorted({r.ref_id for r in self.items}))

    def refs_for(self, rule_id: str) -> tuple[Ref, ...]:
        """**宣言表に無い組は参照 0**(名前の近さで補う経路が無い)。"""
        return tuple(r for r in self.ordered if r.rule_id == rule_id)

    def without(self, ref_id: str, rule_id: str) -> "Declarations":
        """宣言 1 行を外した写し(verify が使う。入力には書かない)。"""
        return Declarations(items=tuple(r for r in self.items
                                        if (r.ref_id, r.rule_id) != (ref_id, rule_id)),
                            pending=self.pending, path=self.path)

    def swapped(self, how: str) -> "Declarations":
        return Declarations(items=tuple(swap_rows(list(self.items), how)),
                            pending=self.pending, path=self.path)


# ------------------------------------------------------------ 問いの一覧


@dataclass(frozen=True)
class Question:
    question_id: str
    wants: str
    needs: str
    source: str
    number: int = 0

    def issues(self) -> tuple[Pending, ...]:
        where = f"問いの一覧 行 {self.number}({self.question_id})"
        return (Pending(STOP_REASONS[0], where),) if not self.source else ()


@dataclass(frozen=True)
class Questions:
    items: tuple[Question, ...]
    pending: tuple[Pending, ...] = ()
    asof: str = ""
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
        seen: set[str] = set()
        asofs: set[str] = set()
        swaps: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in TOI_COLUMNS}
            where = f"問いの一覧 行 {i}"
            for key, name in (("question_id", "問い id"), ("needs", "要る参照元 id")):
                if bad_id(cell[key]):
                    raise ReadError(f"{where}: {name}が空欄か、区切り文字を含む"
                                    f"({cell[key] or '空欄'})")
            if cell["question_id"] in seen:
                raise ReadError(f"{where}: 同じ問い id が 2 行ある"
                                f"({cell['question_id']})")
            seen.add(cell["question_id"])
            if cell["asof"]:
                day_number(cell["asof"])
                asofs.add(cell["asof"])
            if cell["swap"]:
                swaps.add(cell["swap"])
            items.append(Question(question_id=cell["question_id"], wants=cell["wants"],
                                  needs=cell["needs"], source=cell["source"],
                                  number=i))
        if not items:
            raise ReadError("問いの一覧に行が無い(ヘッダだけ)")
        if not asofs:
            raise ReadError("問いの一覧に基準日が 1 つも無い(1 行だけ埋める)")
        if len(asofs) > 1:
            raise ReadError("基準日の宣言が 2 通りある: " + " / ".join(sorted(asofs)))
        if len(swaps) > 1:
            raise ReadError("入れ替え方の宣言が 2 通りある: "
                            + " / ".join(sorted(swaps)))
        how = swaps.pop() if swaps else ""
        if how and how not in SWAPS:
            raise ReadError(f"登録されていない入れ替え方: {how}")
        pending: list[Pending] = []
        for q in items:
            pending.extend(q.issues())
        return cls(items=tuple(items), pending=tuple(pending), asof=asofs.pop(),
                   swap=how, path=path)

    @property
    def ordered(self) -> tuple[Question, ...]:
        return tuple(sorted(self.items, key=lambda q: q.question_id))

    @property
    def asof_day(self) -> int:
        """**基準日は入力の列から**(現在時刻を読む呼び出しがこの部品に 1 つも無い)。"""
        return day_number(self.asof)

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(sorted({q.question_id for q in self.items}))

    @property
    def needs(self) -> tuple[str, ...]:
        return tuple(sorted({q.needs for q in self.items}))

    def without(self, question_id: str) -> "Questions":
        """問い 1 件を外した写し(verify が使う。入力には書かない)。"""
        return Questions(items=tuple(q for q in self.items
                                     if q.question_id != question_id),
                         pending=self.pending, asof=self.asof, swap=self.swap,
                         path=self.path)

    def swapped(self, how: str) -> "Questions":
        return Questions(items=tuple(swap_rows(list(self.items), how)),
                         pending=self.pending, asof=self.asof, swap=self.swap,
                         path=self.path)


# ------------------------------------------------------------ 突き合わせる


def is_called(ref: Ref, questions: Questions) -> bool:
    """その参照元が問いから呼ばれているか。**辿るのは 1 段だけ**(式が式を呼ぶ連なりは
    辿らない。宣言表の「別の式経由」は記録で、ここでは使わない)。"""
    if ref.ref_kind == REF_KINDS[1]:
        return ref.ref_id in questions.ids
    return ref.ref_id in questions.needs


def tables_with_refs(ledger: Ledger, decls: Declarations) -> frozenset[str]:
    """参照の宣言が 1 行以上ある数表の集合(= 調べた跡が在る数表)。"""
    out: set[str] = set()
    for ref in decls.ordered:
        row = ledger.of(ref.rule_id)
        if row is not None:
            out.add(row.table_id)
    return frozenset(out)


@dataclass(frozen=True)
class Judged:
    """rule 1 件の結果。一次の空白と二次の空白は別の値で、1 つに潰す経路が無い。"""
    row: Row
    result: str
    refs: tuple[str, ...] = ()        # その行を指している参照元 id
    called: tuple[str, ...] = ()      # そのうち問いから呼ばれている参照元 id

    @property
    def candidate(self) -> bool:
        """参照候補か(基準日より後に有効になる行は分母の外)。"""
        return self.result != SOTO

    @property
    def idle(self) -> bool:
        return self.result in TAIRYUU

    def line(self) -> str:
        return (f"{self.row.table_id}/{self.row.rule_id}:{self.result}"
                f":{self.row.rows}:{'|'.join(self.refs)}/{'|'.join(self.called)}")

    def as_dict(self) -> dict[str, object]:
        return {"数表 id": self.row.table_id, "rule id": self.row.rule_id,
                "行数": self.row.rows, "由来": self.row.origin, "判定": self.result,
                "指している参照元": list(self.refs),
                "問いから呼ばれている参照元": list(self.called),
                "滞留の理由コード": self.row.reason, "出典": self.row.source}


def judge(row: Row, decls: Declarations, questions: Questions,
          have: frozenset[str], asof_day: int) -> Judged:
    """rule 1 件に 6 値のどれか 1 つを付ける。**時計を読まない。理由も決めない。**

    上から順に見る。照合専用と宣言された行は滞留に数えない。基準日より後に有効になる行は
    別枠に出す。その数表に宣言が 1 行も無い行(= 調べていない)と、宣言は在るのに指されて
    いない行(= 一次の空白)を分ける。指す参照元は在るがその参照元を呼ぶ問いが無い行は
    二次の空白に出す。
    """
    refs = decls.refs_for(row.rule_id)
    names = tuple(r.ref_id for r in refs)
    called = tuple(r.ref_id for r in refs if is_called(r, questions))
    if row.shougou:
        return Judged(row, KEKKA[4], names, called)
    if row.valid_from and day_number(row.valid_from) > asof_day:
        return Judged(row, SOTO, names, called)
    if row.table_id not in have:
        return Judged(row, KEKKA[3], names, called)
    if not refs:
        return Judged(row, KEKKA[1], (), ())
    if not called:
        return Judged(row, KEKKA[2], names, ())
    return Judged(row, KEKKA[0], names, called)


@dataclass(frozen=True)
class Report:
    ok: bool
    pending: tuple[Pending, ...]
    ledger: int
    decls: int
    questions: int
    registry: int


@dataclass(frozen=True)
class Tally:
    report: Report
    judged: tuple[Judged, ...]
    ledger: Ledger
    decls: Declarations
    questions: Questions
    registry: Registry

    # ---------------- 分母

    def rule_denominator(self) -> int:
        return self.report.ledger

    @property
    def denominator(self) -> int:
        """参照候補の数(基準日より後に有効になる行を外した数)。"""
        return sum(1 for j in self.judged if j.candidate)

    def aside_denominator(self) -> int:
        return sum(1 for j in self.judged if not j.candidate)

    # ---------------- 件数と行数

    def six(self) -> dict[str, int]:
        return {k: sum(1 for j in self.judged if j.result == k) for k in KEKKA}

    def rows_by_result(self) -> dict[str, int]:
        return {k: sum(j.row.rows for j in self.judged if j.result == k)
                for k in KEKKA}

    def idle_row_counts(self) -> dict[str, int]:
        """**一次の空白と二次の空白を別の値で返す**(1 つに潰す経路が無い)。"""
        rows = self.rows_by_result()
        first, second = rows[TAIRYUU[0]], rows[TAIRYUU[1]]
        return {KUUHAKU[0]: first, KUUHAKU[1]: second, KUUHAKU[2]: first + second}

    def referenced_rows(self) -> int:
        return self.rows_by_result()[KEKKA[0]]

    def total_rows(self) -> int:
        return self.ledger.total_rows

    def by_origin(self) -> list[dict[str, object]]:
        """由来ごとの内訳(合計が全体に戻るかが二重集計の検算になる)。"""
        out: list[dict[str, object]] = []
        for origin in ORIGINS:
            here = [j for j in self.judged if j.row.origin == origin]
            out.append({"由来": origin, "rule の数": len(here),
                        "行数": sum(j.row.rows for j in here),
                        "6 値": {k: sum(1 for j in here if j.result == k)
                                 for k in KEKKA}})
        return out

    def by_table(self) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for table_id in self.ledger.tables:
            here = [j for j in self.judged if j.row.table_id == table_id]
            out.append({"数表 id": table_id, "rule の数": len(here),
                        "行数": sum(j.row.rows for j in here),
                        "6 値": {k: sum(1 for j in here if j.result == k)
                                 for k in KEKKA},
                        "滞留している行数": sum(j.row.rows for j in here if j.idle),
                        "参照の宣言の数": sum(
                            len(self.decls.refs_for(j.row.rule_id)) for j in here)})
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

    def unreachable_chains(self) -> list[dict[str, object]]:
        """**参照する参照元は在るが、問いまで届かない連なり**(行 → 参照元 → 届かない所)。"""
        out: list[dict[str, object]] = []
        for j in self.judged:
            if j.result != KEKKA[2]:
                continue
            for ref in self.decls.refs_for(j.row.rule_id):
                out.append({"rule id": j.row.rule_id, "行数": j.row.rows,
                            "参照元 id": ref.ref_id, "参照元の種別": ref.ref_kind,
                            "参照の仕方": ref.how,
                            "届かない所": f"{ref.ref_id} を要る参照元に挙げた問いが無い",
                            "宣言の出典": ref.source, "行の出典": j.row.source})
        return out

    def dangling_refs(self) -> list[dict[str, object]]:
        """台帳に無い rule を指している宣言(= 逆向きの欠け)。**止めずに並べる。**"""
        return [{"参照元 id": r.ref_id, "参照元の種別": r.ref_kind,
                 "指している rule id": r.rule_id, "参照の仕方": r.how,
                 "出典": r.source}
                for r in self.decls.ordered if self.ledger.of(r.rule_id) is None]

    def unregistered_reasons(self) -> list[dict[str, object]]:
        """登録表に無い理由コードを持つ行。**別枠に出すだけで、理由を当てない。**"""
        return [{"rule id": r.rule_id, "行数": r.rows,
                 "書かれていた理由コード": r.reason, "出典": r.source}
                for r in self.ledger.ordered
                if r.reason and self.registry.of(r.reason) is None]

    def reason_counts(self) -> dict[str, int]:
        """登録されている理由コード別の件数(登録表の行の順)。"""
        out: dict[str, int] = {}
        for code in self.registry.codes:
            n = sum(1 for r in self.ledger.ordered if r.reason == code)
            if n:
                out[code] = n
        return out

    def stopped(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for p in self.report.pending:
            out[p.reason] = out.get(p.reason, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: STOP_REASONS.index(kv[0])))

    # ---------------- まとめ

    def counts(self) -> dict[str, object]:
        """件数と行数を、3 つの分母と内訳つきで出す。割合も点数も返さない。"""
        six = self.six()
        rows = self.rows_by_result()
        idle = self.idle_row_counts()
        out: dict[str, object] = {
            "行の台帳の行数": self.report.ledger,
            "参照の宣言表の行数": self.report.decls,
            "問いの数": self.report.questions,
            "理由コードの登録表の行数": self.report.registry,
            "基準日": self.questions.asof,
            "分母(rule の数)": self.rule_denominator(),
            "分母(参照候補の数)": self.denominator,
            "分母(別枠の数)": self.aside_denominator(),
            "全体の行数": self.total_rows(),
            "6 値": six,
            "6 値ごとの行数": rows,
            "滞留している行数": idle,
            "参照されている行数": self.referenced_rows(),
            "問いまで届かない連なり": len(self.unreachable_chains()),
            "台帳に無い rule を指す宣言": len(self.dangling_refs()),
            "登録表に無い理由コードを持つ行": len(self.unregistered_reasons()),
            "理由コード別の件数": self.reason_counts(),
            "由来ごと": self.by_origin(),
            "数表ごと": self.by_table(),
            "理由別の止まった件数": self.stopped(),
            "読んだか": ("読んだ" if self.judged else
                         "読んでいない(宣言が揃う前に止まったので 6 値は全て 0)"),
        }
        out["分母に含めたもの"] = (
            f"rule の数 {self.rule_denominator()} 件のうち、基準日 "
            f"{self.questions.asof} より後に有効になる {six[SOTO]} 件を外した "
            f"{self.denominator} 件が参照候補。そのうち滞留は "
            + " + ".join(f"{k} {six[k]}" for k in TAIRYUU)
            + f" の {six[TAIRYUU[0]] + six[TAIRYUU[1]]} 件で、残りは "
            + " + ".join(f"{k} {six[k]}" for k in (KEKKA[0], KEKKA[3], KEKKA[4])))
        out["件数の合計の検算"] = (
            f"6 値の合計 {sum(six.values())} / rule の数 "
            f"{self.rule_denominator()}(5 値 {sum(six[k] for k in GOCHI)} = "
            f"参照候補 {self.denominator} も同じ、数表ごとの内訳の合計 "
            f"{sum(int(r['rule の数']) for r in self.by_table())} = rule の数 も同じ、"
            f"由来ごとの行数の合計 "
            f"{sum(int(r['行数']) for r in self.by_origin())} = 全体の行数 "
            f"{self.total_rows()} も同じ、6 値ごとの行数の合計 "
            f"{sum(rows.values())} = 全体の行数 も同じ)")
        out["参照を推測で補わない"] = (
            "参照は宣言表に書かれた組だけ。rule 名の文字列が近いから参照と見なす経路が"
            "無く、「収録済だから参照されているはず」の既定も無い。宣言表に無い組は"
            "参照 0 として数える")
        out["滞留の理由を決めない"] = (
            "理由コードは台帳の列をそのまま写して数えるだけで、判定に 1 度も使わない。"
            "登録表に無いコードは別枠の一覧に出し、未実装か未収録かを当てる経路が無い")
        out["照合専用を滞留に数えない"] = (
            "由来の欄が照合専用の行は別の値に出て、滞留している行数に足される経路が無い。"
            "引く対象でないと宣言された行を、参照されていない行の件数に混ぜない")
        out["一次と二次の空白を潰さない"] = (
            "どの参照元からも指されない行と、指す参照元は在るがその参照元を呼ぶ問いが"
            "無い行は、別の値と別の行数で返る。1 つの「参照されない行」に潰す経路が無い")
        out["未来有効行を滞留に混ぜない"] = (
            "基準日は問いの一覧の列で、現在時刻を読む呼び出しがこの部品に 1 つも無い。"
            "有効開始日が基準日より後の行は別枠に出て、滞留の行数に入らない")
        out["大きさを見積もらない"] = (
            "返るのは rule の数と行数だけ。長さや量を掛ける経路が無く、入力が小さくなる"
            "と主張する欄も無い")
        out["残すかどうかを判定しない"] = (
            "出力に順位の欄も勧めの欄も無く、参照されない行をどうするかは表を持つ人が"
            "決める。この部品が返すのは件数と行数と行の名前だけ")
        out["点数も割合も返さない"] = (
            "返るのは件数と行数と 3 つの分母だけで、参照の度合いを返す呼び方も option も"
            "無い")
        out["呼ばれた回数は数えない"] = (
            "呼び出しの記録を読む経路が無い。数えるのは宣言の上での参照だけで、実際に"
            "何回引かれたかはこの部品の外側にある")
        out["引かない・取りに行かない"] = (
            "行を引く経路も、式を評価する経路も、原文を取りに行く経路も無い。読むのは"
            "手元の 4 枚だけ")
        out["入力を書き換えない"] = (
            "verify が作る写し(宣言 1 行を外した表・問い 1 件を外した表)はメモリの中"
            "だけで、入力の CSV には 1 文字も書かない")
        return out

    def judgement_bytes(self) -> bytes:
        """判定部分 = rule ごとの 6 値と行数と参照元。時刻・絶対パス・ホスト名は入れない。"""
        self._guard()
        lines = ["\t".join(["件", str(self.report.ledger), str(self.report.decls),
                            str(self.report.questions), str(self.report.registry),
                            self.questions.asof])]
        lines.extend(j.line() for j in self.judged)
        return ("\n".join(lines) + "\n").encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.judgement_bytes()).hexdigest()

    def read_condition(self) -> dict[str, str]:
        return {SCOPE_KEYS[0]: self.ledger.path, SCOPE_KEYS[1]: self.decls.path,
                SCOPE_KEYS[2]: self.questions.path, SCOPE_KEYS[3]: self.registry.path}

    def _guard(self) -> None:
        if not self.report.ok:
            raise RuntimeError("止まっているので数えた rule は無い。"
                               "report.pending の理由コードを見る")


def idle_rows(ledger: Ledger, decls: Declarations, questions: Questions,
              registry: Registry) -> Tally:
    """rule 1 件ごとに 6 値を付ける。

    4 枚のどれかが 1 行でも壊れていたら 1 件も数えない(6 値は全て 0)。
    """
    pending = list(ledger.pending) + list(decls.pending) + list(questions.pending)
    for row in ledger.ordered:
        pending.extend(row.issues(registry))
    for ref in decls.ordered:
        row = ledger.of(ref.rule_id)
        where = f"参照の宣言表 行 {ref.number}: {ref.ref_id} → {ref.rule_id}"
        if row is not None and row.shougou:
            pending.append(Pending(STOP_REASONS[6], where))
        if ref.ref_kind == REF_KINDS[1] and ref.ref_id not in questions.ids:
            pending.append(Pending(STOP_REASONS[8], where))
    for q in questions.ordered:
        if q.needs not in decls.ref_ids:
            pending.append(Pending(STOP_REASONS[7],
                                   f"問いの一覧 行 {q.number}: {q.needs}"))
    report = Report(not pending, tuple(pending), len(ledger.items), len(decls.items),
                    len(questions.items), len(registry.items))
    if pending:                     # 1 件も数えずに止まる
        return Tally(report=report, judged=(), ledger=ledger, decls=decls,
                     questions=questions, registry=registry)
    have = tables_with_refs(ledger, decls)
    day = questions.asof_day
    judged = tuple(judge(row, decls, questions, have, day) for row in ledger.ordered)
    return Tally(report=report, judged=judged, ledger=ledger, decls=decls,
                 questions=questions, registry=registry)


# ------------------------------------------------------------ verify


def moved_elsewhere(first: Tally, after: Tally, *keep: str) -> list[str]:
    """判定部分の行が動いた rule のうち、動くはずだった rule でないものの名前。"""
    was = {j.row.rule_id: j.line() for j in first.judged}
    return sorted(j.row.rule_id for j in after.judged
                  if j.line() != was.get(j.row.rule_id) and j.row.rule_id not in keep)


def ref_probe_plan(ledger: Ledger, decls: Declarations,
                   first: Tally) -> list[tuple[Ref, Row]]:
    """宣言 1 行を外す計画。

    外すと **その rule だけ** が「参照されている」から「どの参照元からも参照されない」へ
    動く組を選ぶ。ほかの参照元も指している rule と、外すとその数表の宣言が 0 行になる組
    (= ほかの rule まで「参照の宣言が無い」へ動く)は使わない。
    """
    plans: list[tuple[Ref, Row]] = []
    for ref in decls.ordered:
        row = ledger.of(ref.rule_id)
        if row is None:
            continue
        j = next((x for x in first.judged if x.row.rule_id == ref.rule_id), None)
        if j is None or j.result != KEKKA[0]:
            continue
        if len(decls.refs_for(ref.rule_id)) != 1:
            continue
        if row.table_id not in tables_with_refs(ledger,
                                                decls.without(ref.ref_id, ref.rule_id)):
            continue
        plans.append((ref, row))
    return plans


def ref_probe(ledger: Ledger, decls: Declarations, questions: Questions,
              registry: Registry, first: Tally) -> dict[str, object]:
    """ある参照元の入力から rule を 1 件外して数え直す。

    いつも成り立つはずのこと: **「参照されている」が 1 減って「どの参照元からも参照され
    ない」が 1 増え、一次の空白の行数がその rule の行数だけ増える**(二次の空白の行数と
    ほかの rule の判定は動かない)。
    """
    rows: list[dict[str, object]] = []
    plans = ref_probe_plan(ledger, decls, first)
    ok = bool(plans)
    before, before_idle = first.six(), first.idle_row_counts()
    for ref, row in plans:
        after = idle_rows(ledger, decls.without(ref.ref_id, ref.rule_id), questions,
                          registry)
        now = after.six()
        now_idle = after.idle_row_counts()
        mine = next((j for j in after.judged if j.row.rule_id == row.rule_id), None)
        fits = (after.report.ok and mine is not None
                and mine.result == KEKKA[1] and mine.refs == () and mine.called == ()
                and now[KEKKA[0]] == before[KEKKA[0]] - 1
                and now[KEKKA[1]] == before[KEKKA[1]] + 1
                and all(now[k] == before[k] for k in KEKKA
                        if k not in (KEKKA[0], KEKKA[1]))
                and now_idle[KUUHAKU[0]] == before_idle[KUUHAKU[0]] + row.rows
                and now_idle[KUUHAKU[1]] == before_idle[KUUHAKU[1]]
                and now_idle[KUUHAKU[2]] == before_idle[KUUHAKU[2]] + row.rows
                and moved_elsewhere(first, after, row.rule_id) == []
                and after.denominator == first.denominator)
        ok = ok and fits
        rows.append({"外した宣言": f"{ref.ref_id} → {ref.rule_id}",
                     "参照の仕方": ref.how, "その rule の行数": row.rows,
                     KEKKA[0]: f"{before[KEKKA[0]]} → {now[KEKKA[0]]}",
                     KEKKA[1]: f"{before[KEKKA[1]]} → {now[KEKKA[1]]}",
                     KUUHAKU[0]: f"{before_idle[KUUHAKU[0]]} → {now_idle[KUUHAKU[0]]}",
                     KUUHAKU[1]: f"{before_idle[KUUHAKU[1]]} → {now_idle[KUUHAKU[1]]}",
                     KUUHAKU[2]: f"{before_idle[KUUHAKU[2]]} → {now_idle[KUUHAKU[2]]}",
                     "ほかで動いた rule": moved_elsewhere(first, after, row.rule_id),
                     "合うか": fits})
    return {"書き換えた欄": "参照の宣言 1 行(写しはメモリの中だけ)",
            "分母(参照候補の数)": first.denominator, "行ごと": rows, "合うか": ok,
            "読み": ("宣言を 1 行外すと、その行は一次の空白へ移る。滞留の行数が rule の"
                     "行数ちょうどだけ増えるので、件数と行数が別の経路で数えられている"
                     "ことがここで数として出る")}


def question_probe_plan(ledger: Ledger, decls: Declarations, questions: Questions,
                        first: Tally) -> list[tuple[Question, tuple[Judged, ...]]]:
    """問い 1 件を外す計画。

    外しても宣言の宛先が消えない問い(= その問い id が参照元として宣言表に出てこない問い)
    だけを選び、**外すと「参照されている」から「参照元は在るが問いから呼ばれない」へ動く
    rule を入力から先に数えておく**。
    """
    plans: list[tuple[Question, tuple[Judged, ...]]] = []
    for q in questions.ordered:
        if q.question_id in decls.ref_ids:
            continue
        rest = questions.without(q.question_id)
        if not rest.items:
            continue
        shifted = tuple(j for j in first.judged if j.result == KEKKA[0]
                        and not any(is_called(r, rest)
                                    for r in decls.refs_for(j.row.rule_id)))
        if not shifted:
            continue
        plans.append((q, shifted))
    return plans


def question_probe(ledger: Ledger, decls: Declarations, questions: Questions,
                   registry: Registry, first: Tally) -> dict[str, object]:
    """問いの一覧から 1 件外して数え直す。

    いつも成り立つはずのこと: **その問いだけが呼んでいた参照元が指す行が「参照元は在るが
    問いから呼ばれない」へ移り、二次の空白の行数がその分だけ増える**(一次の空白の行数と
    ほかの rule の判定は動かない)。
    """
    rows: list[dict[str, object]] = []
    plans = question_probe_plan(ledger, decls, questions, first)
    ok = bool(plans)
    before, before_idle = first.six(), first.idle_row_counts()
    for q, shifted in plans:
        after = idle_rows(ledger, decls, questions.without(q.question_id), registry)
        now = after.six()
        now_idle = after.idle_row_counts()
        moved = sum(j.row.rows for j in shifted)
        each = []
        for x in shifted:
            mine = next((y for y in after.judged
                         if y.row.rule_id == x.row.rule_id), None)
            each.append(mine is not None and mine.result == KEKKA[2]
                        and mine.refs == x.refs and mine.called == ())
        fits = (after.report.ok and all(each)
                and now[KEKKA[0]] == before[KEKKA[0]] - len(shifted)
                and now[KEKKA[2]] == before[KEKKA[2]] + len(shifted)
                and all(now[k] == before[k] for k in KEKKA
                        if k not in (KEKKA[0], KEKKA[2]))
                and now_idle[KUUHAKU[0]] == before_idle[KUUHAKU[0]]
                and now_idle[KUUHAKU[1]] == before_idle[KUUHAKU[1]] + moved
                and now_idle[KUUHAKU[2]] == before_idle[KUUHAKU[2]] + moved
                and moved_elsewhere(first, after,
                                    *[j.row.rule_id for j in shifted]) == []
                and after.denominator == first.denominator)
        ok = ok and fits
        rows.append({"外した問い": q.question_id, "求める値": q.wants,
                     "要る参照元": q.needs,
                     "動く rule": [j.row.rule_id for j in shifted],
                     "動く行数": moved,
                     KEKKA[0]: f"{before[KEKKA[0]]} → {now[KEKKA[0]]}",
                     KEKKA[2]: f"{before[KEKKA[2]]} → {now[KEKKA[2]]}",
                     KUUHAKU[0]: f"{before_idle[KUUHAKU[0]]} → {now_idle[KUUHAKU[0]]}",
                     KUUHAKU[1]: f"{before_idle[KUUHAKU[1]]} → {now_idle[KUUHAKU[1]]}",
                     "ほかで動いた rule": moved_elsewhere(
                         first, after, *[j.row.rule_id for j in shifted]),
                     "合うか": fits})
    return {"書き換えた欄": "問いの一覧 1 行(写しはメモリの中だけ)",
            "分母(参照候補の数)": first.denominator, "行ごと": rows, "合うか": ok,
            "読み": ("問いを 1 件外すと、その問いだけが呼んでいた参照元が指す行は二次の"
                     "空白へ移る。指している参照元の欄は動かないので、一次の空白との"
                     "違いがここで数として出る")}


def verify(ledger: Ledger, decls: Declarations, questions: Questions,
           registry: Registry) -> dict[str, object]:
    """2 回読んで sha256 を比べ、3 枚の行順を入れ替えても同じかを見て、件数を検算する。
    さらに、宣言 1 行を外した写しと、問い 1 件を外した写しを読んで差分を出す。"""
    first = idle_rows(ledger, decls, questions, registry)
    if not first.report.ok:
        return {"ok": False, "stage": "止まった(数えた rule は返さない)",
                **first.counts(),
                "pending": [p.as_dict() for p in first.report.pending]}
    if not questions.swap:
        raise ReadError("問いの一覧に入れ替え方(swap)が無いので verify は走らせない")
    second = idle_rows(ledger, decls, questions, registry)
    how = questions.swap
    third = idle_rows(ledger.swapped(how), decls.swapped(how), questions.swapped(how),
                      registry)
    pending: list[Pending] = []
    if first.sha256() != second.sha256():
        pending.append(Pending(STOP_REASONS[11], f"2 回目 {second.sha256()[:12]}"))
    if not (third.report.ok and first.sha256() == third.sha256()):
        pending.append(Pending(STOP_REASONS[12],
                               f"入れ替え方 {how} の 3 枚で {third.sha256()[:12]}"
                               if third.report.ok else
                               f"入れ替え方 {how} の 3 枚では止まった"))
    six = first.six()
    rows = first.rows_by_result()
    if sum(six.values()) != first.rule_denominator():
        pending.append(Pending(STOP_REASONS[10],
                               f"6 値の合計 {sum(six.values())} / rule の数 "
                               f"{first.rule_denominator()}"))
    inner = sum(six[k] for k in GOCHI)
    if inner != first.denominator:
        pending.append(Pending(STOP_REASONS[10],
                               f"5 値 {inner} / 参照候補 {first.denominator}"))
    by_table = sum(int(r["rule の数"]) for r in first.by_table())
    if by_table != first.rule_denominator():
        pending.append(Pending(STOP_REASONS[10],
                               f"数表ごとの内訳の合計 {by_table} / rule の数 "
                               f"{first.rule_denominator()}"))
    by_origin = sum(int(r["行数"]) for r in first.by_origin())
    if by_origin != first.total_rows():
        pending.append(Pending(STOP_REASONS[10],
                               f"由来ごとの行数の合計 {by_origin} / 全体の行数 "
                               f"{first.total_rows()}"))
    if sum(rows.values()) != first.total_rows():
        pending.append(Pending(STOP_REASONS[10],
                               f"6 値ごとの行数の合計 {sum(rows.values())} / "
                               f"全体の行数 {first.total_rows()}"))
    idle = first.idle_row_counts()
    if idle[KUUHAKU[0]] + idle[KUUHAKU[1]] != idle[KUUHAKU[2]]:
        pending.append(Pending(STOP_REASONS[10],
                               f"一次 {idle[KUUHAKU[0]]} + 二次 {idle[KUUHAKU[1]]} / "
                               f"合計 {idle[KUUHAKU[2]]}"))
    out: dict[str, object] = {
        "ok": not pending, "読んだ回数": 2, "入れ替え方": how,
        "sha256": first.sha256(), "2 回目の sha256": second.sha256(),
        "入れ替えた 3 枚の sha256": third.sha256() if third.report.ok else "",
        "件数の検算": {"6 値": six, "6 値の合計": sum(six.values()), "5 値": inner,
                       "数表ごとの内訳の合計": by_table,
                       "由来ごとの行数の合計": by_origin,
                       "6 値ごとの行数の合計": sum(rows.values()),
                       "滞留している行数": idle,
                       "全体の行数": first.total_rows(),
                       "分母(rule の数)": first.rule_denominator(),
                       "分母(参照候補の数)": first.denominator,
                       "分母(別枠の数)": first.aside_denominator()},
        "宣言 1 行を外した写し": ref_probe(ledger, decls, questions, registry, first),
        "問い 1 件を外した写し": question_probe(ledger, decls, questions, registry,
                                                first),
    }
    for key in ("宣言 1 行を外した写し", "問い 1 件を外した写し"):
        if not out[key]["合うか"]:        # type: ignore[index]
            pending.append(Pending(STOP_REASONS[10], f"{key} の件数が合わない"))
            out["ok"] = False
    if pending:
        out["観測"] = ("同じ表から違うバイト列が出た、または件数が合わない(平均も多数決も"
                       "しない。滞留している理由も決めない)")
        out["pending"] = [p.as_dict() for p in pending]
    return out


# ------------------------------------------------------------ ひな型

TEMPLATE_LEDGER = [
    list(DAICHOU_COLUMNS),
    ["H1", "K11", "6", ORIGINS[0], "", "", "", "合成の台帳のメモ(架空)L1"],
    ["H1", "K12", "4", ORIGINS[0], "", "", "", "合成の台帳のメモ(架空)L2"],
    ["H2", "K21", "90", ORIGINS[1], "", "未収録の相手がいる",
     "合成の理由のメモ(架空)L1", "合成の台帳のメモ(架空)L3"],
]
TEMPLATE_DECLS = [
    list(SENGEN_COLUMNS),
    ["F1", REF_KINDS[0], "K11", HOWS[0], "合成の宣言のメモ(架空)L1"],
    ["F1", REF_KINDS[0], "K12", HOWS[0], "合成の宣言のメモ(架空)L2"],
]
TEMPLATE_QUESTIONS = [
    list(TOI_COLUMNS),
    ["Q1", "合成の求める値(架空)", "F1", "2026-05-20", SWAPS[0],
     "合成の問いのメモ(架空)L1"],
]
TEMPLATE_REGISTRY = [
    list(RIYUU_COLUMNS),
    ["未収録の相手がいる", "参照する側の行がまだ台帳に無い", SOURCE_NEEDED[0]],
    ["未来の有効行", "有効開始日が基準日より後", SOURCE_NEEDED[1]],
]


def write_csv(path: Path, rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    return path


def init(dest: str | Path) -> tuple[Path, Path, Path, Path]:
    d = Path(dest)
    return (write_csv(d / "行の台帳.csv", TEMPLATE_LEDGER),
            write_csv(d / "参照の宣言.csv", TEMPLATE_DECLS),
            write_csv(d / "問いの一覧.csv", TEMPLATE_QUESTIONS),
            write_csv(d / "理由コード.csv", TEMPLATE_REGISTRY))


# ------------------------------------------------------------ CLI

def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def build_parser() -> argparse.ArgumentParser:
    """CLI は idle / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = argparse.ArgumentParser(prog="idle_rows",
                                 description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in SUBCOMMANDS[:3]:
        p = sub.add_parser(name)
        p.add_argument("ledger")
        p.add_argument("decls")
        p.add_argument("questions")
        p.add_argument("registry")
    sub.add_parser(SUBCOMMANDS[3]).add_argument("dest")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == "init":
        print("書いた: " + " / ".join(str(p) for p in init(a.dest)))
        return 0
    try:
        ledger, decls = Ledger.load(a.ledger), Declarations.load(a.decls)
        questions, registry = Questions.load(a.questions), Registry.load(a.registry)
        if a.cmd == "verify":
            out = verify(ledger, decls, questions, registry)
            _print(out)
            return 0 if out["ok"] else 3
        t = idle_rows(ledger, decls, questions, registry)
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
        body["問いまで届かない連なりの一覧"] = t.unreachable_chains()
        body["台帳に無い rule を指す宣言の一覧"] = t.dangling_refs()
        body["登録表に無い理由コードを持つ行の一覧"] = t.unregistered_reasons()
        body["sha256"] = t.sha256()
        body["読んだ条件"] = t.read_condition()
    _print(body)
    return 0 if t.aside_denominator() == 0 and not t.stopped() else 3


if __name__ == "__main__":
    raise SystemExit(main())
