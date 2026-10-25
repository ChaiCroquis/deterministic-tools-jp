"""backing_axis — 既に並べた一覧を、裏付けの由来という別の軸で並べ直す。値を計算せず、
宣言と証跡の型が合うかだけを見て数える。

**欄が埋まっていることと、その値が原文で確かめられたことは別。引けば値は返るし、空欄でも
ないので誰も止まらない。だから普段「制度の領域」で並べている一覧を、「その欄の値はどこから
来たか」という軸に差し替えて数え直す。**

この部品は、行の台帳・由来の登録表・問いの一覧の 3 枚から、行 1 件ごとに 7 値(**機械の再計算 /
2 経路の一致 / 目視 / 写した仮置き / 取れない** の 5 値 + 別枠 **宣言が無い / 旧軸が無い**)を
付ける。新軸で並べ直した一覧、旧軸 × 新軸 の対応表、写した仮置きだけの一覧も返す。
**値を計算しない。行を引かない。原文を取りに行かない。数えるだけだ。**

持たせていないものが規律になっている。

  - **同じ軸で並べ直す指定を受け付けない**(問いの新軸が旧軸の欄名と同じなら、その問いは
    止まる。同じ軸で再掲する経路が無い)
  - **旧軸を指さない問いは判定しない**(別枠「旧軸が無い」に出す。差し替え前の軸が無い
    まま並べ直す経路が無い)
  - **由来の記号を推測しない**(登録表に無い記号は別枠「宣言が無い」に出す。既定の記号を
    当てる経路が無い)
  - **宣言と証跡の型が合わない行は止まる**(件数を要求する由来で件数の欄が空、写した仮置き
    なのに写し元の欄名が空、取れないのに理由が空、件数の欄に整数でない文字、など)
  - **写した仮置きを実値と同じ列に数えない**(写し元の欄名が在る行が、確かめた件数の列に
    入る経路が無い)
  - **由来に点数・順位・良し悪しを付けない**(5 値の件数と分母の内訳だけを返す。確度スコアを
    出す経路が無い)
  - **件数を割合にしない**
  - **出典の欄が空の行は止まる**
  - **値を計算しない・行を引かない・原文を取りに行かない**(ネットワークに触る経路が無い)
  - **入力表を書き換えず、行も記号も生成しない**
  - **同じ入力には同じバイト列**(判定部分に時刻・絶対パス・ホスト名を入れない。行順にも依らない)
  - **数は整数だけ**(float を使う経路が無い)

入力は 3 つ。行の台帳(CSV)、由来の登録表(CSV)、問いの一覧(CSV)。

行の台帳の列は 7 つ。**1 つの欄の値の裏付けが 1 行**。

    row_id      行 id
    rule_id     その行がどの rule のものか
    old_axis    旧軸の値(= これまで並べていた軸。空欄は別枠「旧軸が無い」)
    field       値を持つ欄名
    origin      由来の記号(登録表に無い記号は別枠「宣言が無い」)
    evidence    証跡。由来が要求する型で書く(件数 / 写し元の欄名 / 取れない理由)
    source      出典。空欄は止まる

由来の登録表の列は 3 つ。**1 つの記号が 1 行**。

    origin          由来の記号
    meaning         意味。空欄は止まる
    evidence_type   その記号が要求する証跡の型(登録の 5 種)。空欄も登録外も止まる

問いの一覧の列は 4 つ。**1 つの並べ直しが 1 行**。

    old_list_id   旧軸の一覧 id(= 旧軸の値)。空欄と、台帳に無い値は別枠「旧軸が無い」
    new_axis      新軸の定義(欄名)。登録の 2 つ。旧軸と同じならその問いは止まる
    source        出典。空欄は止まる
    swap          入れ替え方。verify が 3 枚の行順を入れ替えるときの宣言

使い方:

    python backing_axis.py init ひな型/
    python backing_axis.py check  行の台帳.csv 由来の登録表.csv 問いの一覧.csv
    python backing_axis.py axis   行の台帳.csv 由来の登録表.csv 問いの一覧.csv
    python backing_axis.py verify 行の台帳.csv 由来の登録表.csv 問いの一覧.csv

終了コードは、別枠と止まった問いが 0 件のときだけ 0、在れば 3、表として読めなければ 2。
**裏付けの良し悪しは終了コードにも出力にも出さない。**
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

DAICHOU_COLUMNS = ("row_id", "rule_id", "old_axis", "field", "origin", "evidence",
                   "source")
TOUROKU_COLUMNS = ("origin", "meaning", "evidence_type")
TOI_COLUMNS = ("old_list_id", "new_axis", "source", "swap")

# 証跡の型(登録制)。既定は持たない = 空欄を件数と読み替える経路が無い
EVIDENCE_TYPES = ("機械の再計算の件数", "2 経路の一致件数", "目視の件数",
                  "写した元の欄名", "取れない理由")
COUNT_TYPES = EVIDENCE_TYPES[:3]          # 整数の件数を要求する 3 種
COPIED_TYPE = EVIDENCE_TYPES[3]           # 写し元の欄名を要求する 1 種
MISSING_TYPE = EVIDENCE_TYPES[4]          # 取れない理由を要求する 1 種

# 行 1 件に付く 7 値。前の 5 つが由来、後の 2 つが別枠。7 つを混ぜない
RESULTS = ("機械の再計算", "2 経路の一致", "目視", "写した仮置き", "取れない",
           "宣言が無い", "旧軸が無い")
YURAI = RESULTS[:5]
ASIDE = RESULTS[5:]
# 原文で確かめた件数が付く 3 列(写した仮置きをここに入れる経路が無い)
CONFIRMED = RESULTS[:3]

# 軸の欄名(登録制)。旧軸を指定すると「同じ軸」で止まる
AXES = ("旧軸", "由来")
SWAPS = ("逆順", "両端入れ替え", "1 つずらす")
QSTATES = ("判定した", "旧軸が無い", "止まった")

STOP_REASONS = (
    # 台帳・登録表の側。1 行も数えずに止まる(10)
    "出典の欄が空", "件数の欄が空", "件数の欄に整数でない文字がある",
    "写し元の欄名が空", "写し元の欄名がその行の欄名と同じ", "取れない理由が空",
    "同じ rule id と欄名の組が 2 行ある", "証跡の型が空", "登録されていない証跡の型",
    "意味の欄が空",
    # 問い 1 件の側。その問いだけ止まる(1)
    "旧軸と同じ軸で並べ直す指定",
    # verify が見つける(3)
    "件数の合計が合わない", "2 回目の判定部分が不一致", "行順を入れ替えた表で出力が変わる",
)
TABLE_REASONS = STOP_REASONS[:10]
QUESTION_REASONS = STOP_REASONS[10:11]
VERIFY_REASONS = STOP_REASONS[11:]

SUBCOMMANDS = ("axis", "check", "verify", "init")
SCOPE_KEYS = ("読んだ行の台帳の絶対パス", "読んだ由来の登録表の絶対パス",
              "読んだ問いの一覧の絶対パス")

NG_ID = set(" \t,|")


class ReadError(Exception):
    """表として読めない(終了コード 2)。行は 1 件も数えない。"""


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


# ------------------------------------------------------------ 由来の登録表


@dataclass(frozen=True)
class Mark:
    """由来の記号 1 つの宣言。証跡の型は**読めないまま持つ**(数える段で理由コードにする)。"""
    origin: str
    meaning: str
    evidence_type: str
    number: int = 0

    def issues(self) -> tuple[Pending, ...]:
        where = f"由来の登録表 行 {self.number}({self.origin})"
        out: list[Pending] = []
        if not self.meaning:
            out.append(Pending(STOP_REASONS[9], where))
        if not self.evidence_type:
            out.append(Pending(STOP_REASONS[7], where))
        elif self.evidence_type not in EVIDENCE_TYPES:
            out.append(Pending(STOP_REASONS[8], f"{where}: {self.evidence_type}"))
        return tuple(out)


@dataclass(frozen=True)
class Registry:
    items: tuple[Mark, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Registry":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"由来の登録表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Registry":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in TOUROKU_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("由来の登録表に " + " / ".join(lack) + " の列が無い")
        items: list[Mark] = []
        seen: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in TOUROKU_COLUMNS}
            where = f"由来の登録表 行 {i}"
            if bad_id(cell["origin"]):
                raise ReadError(f"{where}: 由来の記号が空欄か、区切り文字を含む"
                                f"({cell['origin'] or '空欄'})")
            if cell["origin"] in seen:
                raise ReadError(f"{where}: 同じ記号が 2 行ある({cell['origin']})")
            seen.add(cell["origin"])
            items.append(Mark(origin=cell["origin"], meaning=cell["meaning"],
                              evidence_type=cell["evidence_type"], number=i))
        if not items:
            raise ReadError("由来の登録表に行が無い(ヘッダだけ)")
        pending: list[Pending] = []
        for m in items:
            pending.extend(m.issues())
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    def type_of(self, origin: str) -> str | None:
        """登録されていない記号には**何も当てない**(None を返す = 別枠へ)。"""
        return next((m.evidence_type for m in self.items if m.origin == origin), None)

    @property
    def marks(self) -> tuple[str, ...]:
        return tuple(sorted(m.origin for m in self.items))

    def marks_of(self, evidence_type: str) -> tuple[str, ...]:
        return tuple(sorted(m.origin for m in self.items
                            if m.evidence_type == evidence_type))

    def swapped(self, how: str) -> "Registry":
        return Registry(items=tuple(swap_rows(list(self.items), how)),
                        pending=self.pending, path=self.path)


# ------------------------------------------------------------ 行の台帳


@dataclass(frozen=True)
class Entry:
    row_id: str
    rule_id: str
    old_axis: str
    field: str
    origin: str
    evidence: str
    source: str
    number: int = 0

    def issues(self, evidence_type: str | None) -> tuple[Pending, ...]:
        """出典と、**宣言された証跡の型と欄の中身が合うか**だけを見る。"""
        where = f"行の台帳 行 {self.number}({self.row_id}: {self.field})"
        out: list[Pending] = []
        if not self.source:
            out.append(Pending(STOP_REASONS[0], where))
        if evidence_type is None:          # 登録表に無い記号 = 別枠。証跡は見ない
            return tuple(out)
        if evidence_type in COUNT_TYPES:
            if not self.evidence:
                out.append(Pending(STOP_REASONS[1], f"{where}: {self.origin}"))
            elif not self.evidence.isdecimal():
                out.append(Pending(STOP_REASONS[2], f"{where}: {self.evidence}"))
        elif evidence_type == COPIED_TYPE:
            if not self.evidence:
                out.append(Pending(STOP_REASONS[3], f"{where}: {self.origin}"))
            elif self.evidence == self.field:
                out.append(Pending(STOP_REASONS[4], f"{where}: {self.evidence}"))
        elif evidence_type == MISSING_TYPE:
            if not self.evidence:
                out.append(Pending(STOP_REASONS[5], f"{where}: {self.origin}"))
        return tuple(out)

    def as_origin(self, origin: str, evidence: str) -> "Entry":
        return Entry(self.row_id, self.rule_id, self.old_axis, self.field, origin,
                     evidence, self.source, self.number)


@dataclass(frozen=True)
class Ledger:
    items: tuple[Entry, ...]
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
        items: list[Entry] = []
        pending: list[Pending] = []
        seen_id: set[str] = set()
        seen_field: set[tuple[str, str]] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in DAICHOU_COLUMNS}
            where = f"行の台帳 行 {i}"
            if bad_id(cell["row_id"]):
                raise ReadError(f"{where}: 行 id が空欄か、区切り文字を含む"
                                f"({cell['row_id'] or '空欄'})")
            if cell["row_id"] in seen_id:
                raise ReadError(f"{where}: 同じ行 id が 2 行ある({cell['row_id']})")
            seen_id.add(cell["row_id"])
            if bad_id(cell["rule_id"]):
                raise ReadError(f"{where}: rule id が空欄か、区切り文字を含む"
                                f"({cell['rule_id'] or '空欄'})")
            if bad_id(cell["field"]):
                raise ReadError(f"{where}: 欄名が空欄か、区切り文字を含む"
                                f"({cell['field'] or '空欄'})")
            if cell["origin"] and any(ch in NG_ID for ch in cell["origin"]):
                raise ReadError(f"{where}: 由来の記号が区切り文字を含む"
                                f"({cell['origin']})")
            key = (cell["rule_id"], cell["field"])
            if key in seen_field:
                pending.append(Pending(STOP_REASONS[6], f"{where}: {key[0]} / {key[1]}"))
            seen_field.add(key)
            items.append(Entry(row_id=cell["row_id"], rule_id=cell["rule_id"],
                               old_axis=cell["old_axis"], field=cell["field"],
                               origin=cell["origin"], evidence=cell["evidence"],
                               source=cell["source"], number=i))
        if not items:
            raise ReadError("行の台帳に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    @property
    def ordered(self) -> tuple[Entry, ...]:
        """行 id の順(行順に依らない = 入れ替えても同じ出力)。"""
        return tuple(sorted(self.items, key=lambda e: e.row_id))

    @property
    def old_values(self) -> tuple[str, ...]:
        """台帳に在る旧軸の値(空欄は含めない)。"""
        return tuple(sorted({e.old_axis for e in self.items if e.old_axis}))

    def swapped(self, how: str) -> "Ledger":
        return Ledger(items=tuple(swap_rows(list(self.items), how)),
                      pending=self.pending, path=self.path)

    def restated(self, row_id: str, origin: str, evidence: str) -> "Ledger":
        """行 1 件の由来と証跡を替えた写し(verify が使う。入力には書かない)。"""
        return Ledger(items=tuple(e.as_origin(origin, evidence) if e.row_id == row_id
                                  else e for e in self.items),
                      pending=self.pending, path=self.path)


# ------------------------------------------------------------ 問いの一覧


@dataclass(frozen=True)
class Question:
    old_list_id: str
    new_axis: str
    source: str
    number: int = 0

    def issues(self) -> tuple[Pending, ...]:
        where = f"問いの一覧 行 {self.number}({self.old_list_id or '空欄'})"
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
        seen: set[tuple[str, str]] = set()
        swaps: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in TOI_COLUMNS}
            where = f"問いの一覧 行 {i}"
            if cell["old_list_id"] and any(ch in NG_ID for ch in cell["old_list_id"]):
                raise ReadError(f"{where}: 旧軸の一覧 id が区切り文字を含む"
                                f"({cell['old_list_id']})")
            if not cell["new_axis"]:
                raise ReadError(f"{where}: 新軸の定義(欄名)が空欄")
            if cell["new_axis"] not in AXES:
                raise ReadError(f"{where}: 登録されていない軸の欄名({cell['new_axis']})")
            key = (cell["old_list_id"], cell["new_axis"])
            if key in seen:
                raise ReadError(f"{where}: 同じ問いが 2 行ある"
                                f"({key[0] or '空欄'} / {key[1]})")
            seen.add(key)
            if cell["swap"]:
                swaps.add(cell["swap"])
            items.append(Question(old_list_id=cell["old_list_id"],
                                  new_axis=cell["new_axis"], source=cell["source"],
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
        return tuple(sorted(self.items, key=lambda q: (q.old_list_id, q.new_axis)))

    def swapped(self, how: str) -> "Questions":
        return Questions(items=tuple(swap_rows(list(self.items), how)),
                         pending=self.pending, swap=self.swap, path=self.path)

    def retargeted(self, old_list_id: str, new_axis: str) -> "Questions":
        """問い 1 件の新軸を替えた写し(verify が使う。入力には書かない)。"""
        return Questions(items=tuple(Question(q.old_list_id, new_axis, q.source,
                                              q.number)
                                     if q.old_list_id == old_list_id else q
                                     for q in self.items),
                         pending=self.pending, swap=self.swap, path=self.path)


# ------------------------------------------------------------ 数える


def judge(entry: Entry, registry: Registry) -> str:
    """行 1 件に 7 値のどれか 1 つを付ける。**記号を推測しない。**

    旧軸の欄が空なら別枠「旧軸が無い」(差し替え前の軸が無いので並べ直せない)。登録表に
    無い記号なら別枠「宣言が無い」。登録されていれば、その記号が要求する証跡の型の列に入る。
    """
    if not entry.old_axis:
        return RESULTS[6]
    kind = registry.type_of(entry.origin)
    if kind is None:
        return RESULTS[5]
    return RESULTS[EVIDENCE_TYPES.index(kind)]


@dataclass(frozen=True)
class Judged:
    entry: Entry
    result: str

    def line(self) -> str:
        return f"{self.entry.row_id}:{self.result}:{self.entry.old_axis or '-'}"


@dataclass(frozen=True)
class Asked:
    """問い 1 件の結果。止まった問いは並べ直した一覧を持たない。"""
    old_list_id: str
    new_axis: str
    state: str
    reason: str = ""
    rows: tuple[Judged, ...] = ()

    def seven(self) -> dict[str, int]:
        return {r: sum(1 for j in self.rows if j.result == r) for r in RESULTS}

    def line(self) -> str:
        return (f"{self.old_list_id or '-'}:{self.new_axis}:{self.state}:{self.reason}"
                f":{len(self.rows)}")


@dataclass(frozen=True)
class Report:
    ok: bool
    pending: tuple[Pending, ...]
    rows: int
    marks: int
    questions: int


@dataclass(frozen=True)
class Tally:
    report: Report
    judged: tuple[Judged, ...]
    asked: tuple[Asked, ...]
    ledger: Ledger
    registry: Registry
    questions: Questions

    # ---------------- 分母

    @property
    def denominator(self) -> int:
        return self.report.rows

    def question_denominator(self) -> int:
        return self.report.questions

    def aside_denominator(self) -> int:
        """別枠の数(行の別枠 2 種 + 旧軸を指さない問い)。"""
        return (sum(self.seven()[r] for r in ASIDE)
                + sum(1 for a in self.asked if a.state == QSTATES[1]))

    # ---------------- 件数

    def seven(self) -> dict[str, int]:
        return {r: sum(1 for j in self.judged if j.result == r) for r in RESULTS}

    def by_mark(self) -> dict[str, int]:
        """記号別の件数(登録されている記号の順。別枠はここに入らない)。"""
        out = {m: 0 for m in self.registry.marks}
        for j in self.judged:
            if j.result in YURAI and j.entry.origin in out:
                out[j.entry.origin] += 1
        return out

    def by_old_axis(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for j in self.judged:
            key = j.entry.old_axis or RESULTS[6]
            out[key] = out.get(key, 0) + 1
        return dict(sorted(out.items()))

    def cross(self) -> list[dict[str, object]]:
        """旧軸 × 新軸 の対応表。1 行がちょうど 1 つのセルに入るので、合計 = 行数。"""
        keys = list(self.ledger.old_values)
        if any(not j.entry.old_axis for j in self.judged):
            keys.append(RESULTS[6])
        out: list[dict[str, object]] = []
        for key in keys:
            here = [j for j in self.judged if (j.entry.old_axis or RESULTS[6]) == key]
            cells = {r: sum(1 for j in here if j.result == r) for r in RESULTS}
            out.append({"旧軸": key, "行数": len(here), "新軸の内訳": cells,
                        "割れた数": sum(1 for n in cells.values() if n)})
        return out

    def placeholders(self) -> list[dict[str, object]]:
        """写した仮置きだけの一覧(名前と写し元の欄名)。実値の列には 1 件も入れない。"""
        return [{"欄名": j.entry.field, "rule id": j.entry.rule_id,
                 "旧軸": j.entry.old_axis, "写し元の欄名": j.entry.evidence,
                 "出典": j.entry.source}
                for j in sorted(self.judged, key=lambda x: x.entry.row_id)
                if j.result == RESULTS[3]]

    def relisted(self) -> list[dict[str, object]]:
        """新軸で並べ直した一覧(7 値ごとに、行 id と欄名と証跡と出典)。"""
        out: list[dict[str, object]] = []
        for r in RESULTS:
            here = [j for j in sorted(self.judged, key=lambda x: x.entry.row_id)
                    if j.result == r]
            out.append({"新軸": r, "件数": len(here),
                        "行": [{"行 id": j.entry.row_id, "rule id": j.entry.rule_id,
                                "旧軸": j.entry.old_axis or RESULTS[6],
                                "欄名": j.entry.field, "証跡": j.entry.evidence,
                                "出典": j.entry.source} for j in here]})
        return out

    def stopped(self) -> dict[str, int]:
        """理由別の止まった件数(台帳の側 + 問い 1 件の側)。"""
        out: dict[str, int] = {}
        for p in self.report.pending:
            out[p.reason] = out.get(p.reason, 0) + 1
        for a in self.asked:
            if a.state == QSTATES[2]:
                out[a.reason] = out.get(a.reason, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: STOP_REASONS.index(kv[0])))

    def questions_by_state(self) -> dict[str, int]:
        return {s: sum(1 for a in self.asked if a.state == s) for s in QSTATES}

    def counts(self) -> dict[str, object]:
        """件数は丸めず、3 つの分母と内訳つきで出す。割合も点数も返さない。"""
        seven = self.seven()
        out: dict[str, object] = {
            "行の台帳の行数": self.report.rows,
            "由来の登録表の行数(記号の数)": self.report.marks,
            "問いの数": self.report.questions,
            "分母(行数)": self.denominator,
            "分母(問いの数)": self.question_denominator(),
            "分母(別枠の数)": self.aside_denominator(),
            "7 値": seven,
            "記号別の件数": self.by_mark(),
            "旧軸別の件数": self.by_old_axis(),
            "問いの状態": self.questions_by_state(),
            "理由別の止まった件数": self.stopped(),
            "読んだか": ("読んだ" if self.judged else
                         "読んでいない(宣言が揃う前に止まったので 7 値は全て 0)"),
        }
        out["分母に含めたもの"] = (
            f"行数 {self.denominator} 件、問いの数 {self.question_denominator()} 件、"
            f"別枠 {self.aside_denominator()} 件(行の別枠 "
            f"{sum(seven[r] for r in ASIDE)} 件 + 旧軸を指さない問い "
            f"{sum(1 for a in self.asked if a.state == QSTATES[1])} 件)。"
            "確かめた件数が付く 3 列は "
            + " + ".join(f"{r} {seven[r]}" for r in CONFIRMED)
            + "、残りは " + " + ".join(f"{r} {seven[r]}" for r in RESULTS[3:]))
        out["件数の合計の検算"] = (
            f"7 値の合計 {sum(seven.values())} / 行数 {self.denominator}"
            f"(記号別の合計 {sum(self.by_mark().values())} + 別枠 "
            f"{sum(seven[r] for r in ASIDE)} も同じ、旧軸 × 新軸 の対応表のセルの合計 "
            f"{sum(int(row['行数']) for row in self.cross())} も同じ)")
        out["由来に点数を付けない"] = (
            "出すのは 7 値の件数と 3 つの分母の内訳だけで、確度のスコアも順位も良し悪しも"
            "付けない。どの由来が良いかは、この部品の判定することではない")
        out["件数を割合にしない"] = (
            "何割が確かめ済かを返す呼び方も option も無い。件数には必ず分母が付く")
        out["由来の記号を推測しない"] = (
            "登録表に無い記号は別枠「宣言が無い」に出す。既定の記号を当てる経路が無い。"
            "旧軸の欄が空の行も別枠「旧軸が無い」に出し、領域を推測して埋めない")
        out["写した仮置きを実値と同じ列に数えない"] = (
            "写し元の欄名が在る行は、値が埋まっていても 機械の再計算 / 2 経路の一致 / 目視 の"
            "列に入る経路が無い。仮置きだけの一覧も別に返す")
        out["同じ軸で並べ直さない"] = (
            "問いの新軸が旧軸の欄名と同じなら、その問いは止まる。同じ軸で再掲する指定を"
            "受け付ける経路が無い。旧軸を指さない問いは判定せず別枠に出す")
        out["値を計算しない・行を引かない・原文を取りに行かない"] = (
            "読むのは宣言の 3 枚だけで、値も日付も持たない。ネットワークに触る経路も、"
            "原文を開く経路も無い")
        out["入力を書き換えない"] = (
            "verify が作る写し(由来を替えた台帳・新軸を替えた問い)はメモリの中だけで、"
            "入力の CSV には 1 文字も書かない")
        return out

    def table(self) -> list[dict[str, object]]:
        """問いごとの結果(止まった問いは一覧を持たない)。"""
        return [{"旧軸の一覧 id": a.old_list_id, "新軸": a.new_axis, "状態": a.state,
                 "理由コード": a.reason, "行数": len(a.rows), "7 値": a.seven(),
                 "割れた数": sum(1 for n in a.seven().values() if n)}
                for a in self.asked]

    def judgement_bytes(self) -> bytes:
        """判定部分 = 行ごとの 7 値と、問いごとの状態。時刻・絶対パス・ホスト名は入れない。"""
        self._guard()
        lines = ["\t".join(["件", str(self.report.rows), str(self.report.marks),
                            str(self.report.questions)])]
        lines.extend(j.line() for j in self.judged)
        lines.extend(a.line() for a in self.asked)
        return ("\n".join(lines) + "\n").encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.judgement_bytes()).hexdigest()

    def read_condition(self) -> dict[str, str]:
        return {SCOPE_KEYS[0]: self.ledger.path, SCOPE_KEYS[1]: self.registry.path,
                SCOPE_KEYS[2]: self.questions.path}

    def _guard(self) -> None:
        if not self.report.ok:
            raise RuntimeError("止まっているので数えた行は無い。"
                               "report.pending の理由コードを見る")


def backing_axis(ledger: Ledger, registry: Registry,
                 questions: Questions) -> Tally:
    """行 1 件ごとに 7 値を付け、問いごとに新軸で並べ直す。

    台帳・登録表の側が 1 行でも壊れていたら 1 行も数えない(7 値は全て 0)。問いは 1 件ずつ
    判定するので、1 件が「同じ軸」で止まってもほかの問いは判定を続ける。
    """
    pending = list(ledger.pending) + list(registry.pending) + list(questions.pending)
    for e in ledger.ordered:
        pending.extend(e.issues(registry.type_of(e.origin)))
    report = Report(not pending, tuple(pending), len(ledger.items), len(registry.items),
                    len(questions.items))
    if pending:                     # 1 行も数えずに止まる
        return Tally(report=report, judged=(), asked=(), ledger=ledger,
                     registry=registry, questions=questions)
    judged = tuple(Judged(e, judge(e, registry)) for e in ledger.ordered)
    known = set(ledger.old_values)
    asked: list[Asked] = []
    for q in questions.ordered:
        if q.new_axis == AXES[0]:
            asked.append(Asked(q.old_list_id, q.new_axis, QSTATES[2], STOP_REASONS[10]))
        elif not q.old_list_id or q.old_list_id not in known:
            asked.append(Asked(q.old_list_id, q.new_axis, QSTATES[1]))
        else:
            rows = tuple(j for j in judged if j.entry.old_axis == q.old_list_id)
            asked.append(Asked(q.old_list_id, q.new_axis, QSTATES[0], "", rows))
    return Tally(report=report, judged=judged, asked=tuple(asked), ledger=ledger,
                 registry=registry, questions=questions)


# ------------------------------------------------------------ verify


def restate_probe(ledger: Ledger, registry: Registry, questions: Questions,
                  first: Tally) -> dict[str, object]:
    """写した仮置きの行 1 件を「2 経路の一致」に替えて、件数と仮置きの一覧の動きを数える。

    いつも成り立つはずのこと: 件数の欄に整数を書いた写しでは、仮置きの一覧からその欄名が
    消えて 2 経路の一致が 1 増え、写した仮置きが 1 減る(ほかの 5 値は動かない)。**証跡の欄を
    写し元の欄名のまま、または空にした写しでは、代わりに止まる。**
    """
    target = registry.marks_of(EVIDENCE_TYPES[1])
    rows = [j for j in first.judged if j.result == RESULTS[3]]
    out_rows: list[dict[str, object]] = []
    ok = bool(target) and bool(rows)
    for j in rows:
        mark = target[0]
        after = backing_axis(ledger.restated(j.entry.row_id, mark, "1"), registry,
                             questions)
        kept = backing_axis(ledger.restated(j.entry.row_id, mark, j.entry.evidence),
                            registry, questions)
        empty = backing_axis(ledger.restated(j.entry.row_id, mark, ""), registry,
                             questions)
        before, now = first.seven(), after.seven()
        fits = (after.report.ok
                and now[RESULTS[1]] == before[RESULTS[1]] + 1
                and now[RESULTS[3]] == before[RESULTS[3]] - 1
                and all(now[r] == before[r] for r in RESULTS
                        if r not in (RESULTS[1], RESULTS[3]))
                and j.entry.field not in [str(x["欄名"]) for x in after.placeholders()]
                and not kept.report.ok
                and {p.reason for p in kept.report.pending} == {STOP_REASONS[2]}
                and not empty.report.ok
                and {p.reason for p in empty.report.pending} == {STOP_REASONS[1]})
        ok = ok and fits
        out_rows.append({"替えた行": j.entry.row_id, "欄名": j.entry.field,
                         "替えた先の記号": mark,
                         "2 経路の一致": f"{before[RESULTS[1]]} → {now[RESULTS[1]]}",
                         "写した仮置き": f"{before[RESULTS[3]]} → {now[RESULTS[3]]}",
                         "仮置きの一覧": f"{len(first.placeholders())} → "
                                         f"{len(after.placeholders())}",
                         "証跡をそのままにした写し":
                             sorted({p.reason for p in kept.report.pending}),
                         "証跡を空にした写し":
                             sorted({p.reason for p in empty.report.pending}),
                         "合うか": fits})
    return {"書き換えた欄": "行 1 件の由来の記号と証跡(写しはメモリの中だけ)",
            "分母(行数)": first.denominator, "行ごと": out_rows, "合うか": ok,
            "読み": ("由来を替えると件数はその分だけ動き、仮置きの一覧から名前が消える。"
                     "証跡の型が合わないままなら代わりに止まる"
                     "(宣言と証跡を別々に見ていることの実測)")}


def same_axis_probe(ledger: Ledger, registry: Registry, questions: Questions,
                    first: Tally) -> dict[str, object]:
    """問い 1 件の新軸を旧軸の欄名に替えて、その問いだけが止まることを数える。

    いつも成り立つはずのこと: 替えた問いは「同じ軸」で止まり、**ほかの問いの状態と一覧は
    1 件も動かない**。行の 7 値も動かない(問いは行の数え方を変えない)。
    """
    out_rows: list[dict[str, object]] = []
    ok = True
    for a in first.asked:
        if a.state != QSTATES[0]:
            continue
        after = backing_axis(ledger, registry,
                             questions.retargeted(a.old_list_id, AXES[0]))
        same = {b.old_list_id: b for b in after.asked}
        moved: list[str] = []
        fits = after.report.ok and after.seven() == first.seven()
        for b in first.asked:
            c = same.get(b.old_list_id)
            if b.old_list_id == a.old_list_id:
                fits = fits and c is not None and c.state == QSTATES[2] \
                    and c.reason == STOP_REASONS[10] and c.rows == ()
                moved.append(b.old_list_id)
            else:
                fits = fits and c is not None and c.state == b.state \
                    and c.rows == b.rows
        ok = ok and fits
        out_rows.append({"替えた問い": a.old_list_id, "替えた新軸": AXES[0],
                         "止まった理由": STOP_REASONS[10],
                         "動いた問い": "|".join(moved),
                         "7 値": "動いていない" if after.seven() == first.seven()
                                 else "動いた", "合うか": fits})
    return {"書き換えた欄": "問い 1 件の新軸の定義(写しはメモリの中だけ)",
            "分母(問いの数)": first.question_denominator(), "問いごと": out_rows,
            "合うか": ok,
            "読み": ("同じ軸で並べ直す指定はその問いだけを止める。ほかの問いの一覧も"
                     "行の 7 値も動かない(同じ軸で再掲する経路が無いことの実測)")}


def verify(ledger: Ledger, registry: Registry,
           questions: Questions) -> dict[str, object]:
    """2 回読んで sha256 を比べ、3 枚の行順を入れ替えても同じかを見て、件数を検算する。
    さらに、由来を替えた写しと、新軸を旧軸に替えた写しを読んで差分を出す。"""
    first = backing_axis(ledger, registry, questions)
    if not first.report.ok:
        return {"ok": False, "stage": "止まった(数えた行は返さない)", **first.counts(),
                "pending": [p.as_dict() for p in first.report.pending]}
    if not questions.swap:
        raise ReadError("問いの一覧に入れ替え方(swap)が無いので verify は走らせない")
    second = backing_axis(ledger, registry, questions)
    third = backing_axis(ledger.swapped(questions.swap),
                         registry.swapped(questions.swap),
                         questions.swapped(questions.swap))
    pending: list[Pending] = []
    if first.sha256() != second.sha256():
        pending.append(Pending(STOP_REASONS[12], f"2 回目 {second.sha256()[:12]}"))
    if not (third.report.ok and first.sha256() == third.sha256()):
        pending.append(Pending(STOP_REASONS[13],
                               f"入れ替え方 {questions.swap} の 3 枚で "
                               f"{third.sha256()[:12]}" if third.report.ok else
                               f"入れ替え方 {questions.swap} の 3 枚では止まった"))
    seven = first.seven()
    if sum(seven.values()) != first.denominator:
        pending.append(Pending(STOP_REASONS[11], f"7 値の合計 {sum(seven.values())}"
                                                 f" / 行数 {first.denominator}"))
    marks = sum(first.by_mark().values()) + sum(seven[r] for r in ASIDE)
    if marks != first.denominator:
        pending.append(Pending(STOP_REASONS[11],
                               f"記号別 + 別枠 {marks} / 行数 {first.denominator}"))
    cells = sum(int(row["行数"]) for row in first.cross())
    if cells != first.denominator:
        pending.append(Pending(STOP_REASONS[11],
                               f"対応表のセルの合計 {cells} / 行数 "
                               f"{first.denominator}"))
    if len(first.placeholders()) != seven[RESULTS[3]]:
        pending.append(Pending(STOP_REASONS[11],
                               f"仮置きの一覧 {len(first.placeholders())} / "
                               f"写した仮置き {seven[RESULTS[3]]}"))
    out: dict[str, object] = {
        "ok": not pending, "読んだ回数": 2, "入れ替え方": questions.swap,
        "sha256": first.sha256(), "2 回目の sha256": second.sha256(),
        "入れ替えた 3 枚の sha256": third.sha256() if third.report.ok else "",
        "件数の検算": {"7 値": seven, "7 値の合計": sum(seven.values()),
                       "記号別 + 別枠": marks, "対応表のセルの合計": cells,
                       "分母(行数)": first.denominator,
                       "分母(問いの数)": first.question_denominator(),
                       "分母(別枠の数)": first.aside_denominator()},
        "由来を 2 経路の一致 に替えた写し":
            restate_probe(ledger, registry, questions, first),
        "新軸を旧軸に替えた写し": same_axis_probe(ledger, registry, questions, first),
    }
    for key in ("由来を 2 経路の一致 に替えた写し", "新軸を旧軸に替えた写し"):
        if not out[key]["合うか"]:        # type: ignore[index]
            pending.append(Pending(STOP_REASONS[11], f"{key} の件数が合わない"))
            out["ok"] = False
    if pending:
        out["観測"] = ("同じ表から違うバイト列が出た、または件数が合わない(平均も多数決も"
                       "しない。どちらが正しいかも決めない)")
        out["pending"] = [p.as_dict() for p in pending]
    return out


# ------------------------------------------------------------ ひな型

TEMPLATE_LEDGER = [
    list(DAICHOU_COLUMNS),
    ["B01", "R01", "D1", "V01", "Y1", "12", "合成の検証の記録(架空)L1"],
    ["B02", "R01", "D1", "V02", "Y4", "V01", "合成の棚卸しの記録(架空)L2"],
    ["B03", "R02", "D2", "V03", "Y2", "4", "合成の検証の記録(架空)L3"],
    ["B04", "R03", "D2", "V04", "Y5", "画像のまま読めない", "合成の棚卸しの記録(架空)L4"],
]
TEMPLATE_REGISTRY = [
    list(TOUROKU_COLUMNS),
    ["Y1", "機械で再計算して合わせた", EVIDENCE_TYPES[0]],
    ["Y2", "2 つの経路で突き合わせた", EVIDENCE_TYPES[1]],
    ["Y3", "目で見て合わせた", EVIDENCE_TYPES[2]],
    ["Y4", "同じ行の別の列から写した仮置き", EVIDENCE_TYPES[3]],
    ["Y5", "原文が取れていない", EVIDENCE_TYPES[4]],
]
TEMPLATE_QUESTIONS = [
    list(TOI_COLUMNS),
    ["D1", AXES[1], "合成の問いのメモ(架空)L1", SWAPS[0]],
    ["D2", AXES[1], "合成の問いのメモ(架空)L2", ""],
]


def write_csv(path: Path, rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    return path


def init(dest: str | Path) -> tuple[Path, Path, Path]:
    d = Path(dest)
    return (write_csv(d / "行の台帳.csv", TEMPLATE_LEDGER),
            write_csv(d / "由来の登録表.csv", TEMPLATE_REGISTRY),
            write_csv(d / "問いの一覧.csv", TEMPLATE_QUESTIONS))


# ------------------------------------------------------------ CLI

def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def build_parser() -> argparse.ArgumentParser:
    """CLI は axis / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = argparse.ArgumentParser(prog="backing_axis",
                                 description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in SUBCOMMANDS[:3]:
        p = sub.add_parser(name)
        p.add_argument("ledger")
        p.add_argument("registry")
        p.add_argument("questions")
    sub.add_parser(SUBCOMMANDS[3]).add_argument("dest")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == "init":
        print("書いた: " + " / ".join(str(p) for p in init(a.dest)))
        return 0
    try:
        ledger, registry = Ledger.load(a.ledger), Registry.load(a.registry)
        questions = Questions.load(a.questions)
        if a.cmd == "verify":
            out = verify(ledger, registry, questions)
            _print(out)
            return 0 if out["ok"] else 3
        t = backing_axis(ledger, registry, questions)
    except ReadError as e:
        print(f"表として読めない: {e}", file=sys.stderr)
        return 2
    if not t.report.ok:
        _print({"ok": False, "stage": "止まった(数えた行は返さない)", **t.counts(),
                "pending": [p.as_dict() for p in t.report.pending]})
        return 3
    body: dict[str, object] = {"ok": True, **t.counts()}
    if a.cmd == SUBCOMMANDS[0]:
        body["問いごと"] = t.table()
        body["新軸で並べ直した一覧"] = t.relisted()
        body["旧軸 × 新軸 の対応表"] = t.cross()
        body["写した仮置きだけの一覧"] = t.placeholders()
        body["sha256"] = t.sha256()
        body["読んだ条件"] = t.read_condition()
    _print(body)
    return 0 if t.aside_denominator() == 0 and not t.stopped() else 3


if __name__ == "__main__":
    raise SystemExit(main())
