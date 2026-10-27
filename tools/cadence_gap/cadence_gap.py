"""cadence_gap — 宣言された更新周期と、実行の履歴を突き合わせて、数表ごとの鮮度を数える。

**「自動で週 1 回更新する」と書いてある数表でも、履歴に残っている実行は別の話で、
最後に中身が動いた日を見ないと古い行をそのまま引く。**

この部品は、周期の宣言表・実行の履歴表・問いの一覧の 3 枚から、問い 1 件ごとに 6 値
(**宣言どおり / 遅れている / 一度も動いていない / 履歴が無い / 宣言が無い** の 5 値 +
別枠 **基準日より前の実行が無い**)を付け、問いごとに 3 つの日付(**走った最後の日 /
中身が動いた最後の日 / 落ちた回を除いた最後の日**)を別の列で返す。**走らせない。
時計を読まない。値を引かない。原文を取りに行かない。数えるだけだ。**

持たせていないものが規律になっている。

  - **基準日を時計から取らない**(現在時刻を読む経路が無い。基準日は必ず入力の列で、
    日付は文字列から整数の通算日に直すだけ)
  - **落ちた回を最後の更新に数えない**(`failed` の行は「走った最後の日」にだけ入り、
    「中身が動いた最後の日」と「落ちた回を除いた最後の日」に入る経路が無い)
  - **中身が動いた件数が 0 の実行を更新に数えない**(走った最後の日と中身が動いた最後の
    日を別の列で返し、1 つに潰す経路が無い。これが骨の物理形)
  - **周期の宣言が無い数表に既定の周期を当てない**(週 1 を既定にする引数が無い。別の値
    「宣言が無い」に出す)
  - **遅れの理由を決めない**(登録がまだ / 資料がまだ公表されていない / 改定が無かった を
    区別せず「遅れている」の 1 値 + 空き日数 + 超過日数で返し、理由は読む人に戻す)
  - **評価の語を出力に持たない**(出すのは日数と件数だけ)
  - **鮮度を点数や割合にしない**(件数と日数と 3 つの分母の内訳だけを返す)
  - **次回改定の近さを鮮度と同じ列に入れない**(予定を受け取っても別枠で返す)
  - **件数と指紋の食い違いを、どちらが正しいとも決めない**(2 種類に分けて並べるだけ)
  - **出典の欄が空の行は使わずに止まる**
  - **走らせない・値を引かない・計算しない・原文を取りに行かない**(実行経路もネット
    ワーク経路も持たない)
  - **入力表を書き換えず、行も実行も生成しない**
  - **同じ入力には同じバイト列**(判定部分に時刻・絶対パス・ホスト名を入れない。行順にも
    依らない)
  - **数は整数だけ**(日数も件数も整数で、float を使う経路が無い)

入力は 3 つ。周期の宣言表(CSV)、実行の履歴表(CSV)、問いの一覧(CSV)。

周期の宣言表の列は 7 つ。**1 つの数表が 1 行**。

    table_id             数表 id(同じ id が 2 行あると止まる)
    cycle_days           宣言された周期(日数、整数。1 日より短いと止まる)
    auto                 自動で走る宣言の有無(在る / 無い。登録外は読めない)
    auto_source          自動で走る宣言の出典。空欄は止まる
    cycle_source         周期の出典。空欄は止まる
    next_change          次回改定の予定日(空欄可。在れば別枠で返す)
    next_change_source   次回改定の出典(予定が在るのに空欄なら止まる)

実行の履歴表の列は 7 つ。**1 回の実行が 1 行**。

    run_id        実行 id(空欄・区切り文字入り・重複は読めない)
    table_id      数表 id
    ran_on        実行日(`YYYY-MM-DD`。形が違えば読めない)
    result        結果(ok / failed。登録外は読めない)
    moved         中身が動いた件数(0 以上の整数)
    fingerprint   出力の指紋(落ちた回は空欄。動いた件数が 1 以上で空欄なら止まる)
    source        出典。空欄は止まる

問いの一覧の列は 4 つ。**1 つの問いが 1 行**。

    table_id   数表 id(宣言表にも履歴表にも無いと止まる)
    asof       **基準日**(いつ時点の鮮度を見るか。`YYYY-MM-DD`)
    source     出典。空欄は止まる
    swap       入れ替え方(逆順 / 両端入れ替え / 1 つずらす)。verify が使う宣言

使い方:

    python cadence_gap.py init ひな型/
    python cadence_gap.py check   周期の宣言.csv 実行の履歴.csv 問いの一覧.csv
    python cadence_gap.py cadence 周期の宣言.csv 実行の履歴.csv 問いの一覧.csv
    python cadence_gap.py verify  周期の宣言.csv 実行の履歴.csv 問いの一覧.csv

終了コードは、別枠と止まった行が 0 件のときだけ 0、在れば 3、表として読めなければ 2。
**遅れていることの是非は、終了コードにも出力にも出さない。**
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

SENGEN_COLUMNS = ("table_id", "cycle_days", "auto", "auto_source", "cycle_source",
                  "next_change", "next_change_source")
RIREKI_COLUMNS = ("run_id", "table_id", "ran_on", "result", "moved", "fingerprint",
                  "source")
TOI_COLUMNS = ("table_id", "asof", "source", "swap")

AUTO = ("在る", "無い")
OK, FAILED = "ok", "failed"
RUN_RESULTS = (OK, FAILED)

KEKKA = ("宣言どおり", "遅れている", "一度も動いていない", "履歴が無い", "宣言が無い",
         "基準日より前の実行が無い")
GOCHI = KEKKA[:5]        # 5 値
ASIDE = KEKKA[5:]        # 別枠 1 種
HIZUKE = KEKKA[:2]       # 日数まで出せた 2 値
SOTO = KEKKA[5]

DATE_KEYS = ("走った最後の日", "中身が動いた最後の日", "落ちた回を除いた最後の日")
CLASH = ("差分 0 なのに指紋が変わった", "中身が動いたのに指紋が変わっていない")

SWAPS = ("逆順", "両端入れ替え", "1 つずらす")

STOP_REASONS = (
    # 表の側。1 行も数えずに止まる(8)
    "出典の欄が空",
    "同じ数表 id が宣言表に 2 行ある",
    "宣言された周期が 1 日より短い",
    "落ちた回に中身が動いた件数が入っている",
    "中身が動いた回に指紋が無い",
    "落ちた回に指紋が入っている",
    "問いの数表 id が宣言表にも履歴表にも無い",
    "次回改定の予定が在るのに出典が空",
    # verify が見つける(3)
    "件数の合計が合わない", "2 回目の判定部分が不一致", "行順を入れ替えた表で出力が変わる",
)
TABLE_REASONS = STOP_REASONS[:8]
VERIFY_REASONS = STOP_REASONS[8:]

SUBCOMMANDS = ("cadence", "check", "verify", "init")
SCOPE_KEYS = ("読んだ周期の宣言表の絶対パス", "読んだ実行の履歴表の絶対パス",
              "読んだ問いの一覧の絶対パス")

NG_ID = set(" \t,|")
MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


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


# ------------------------------------------------------------ 周期の宣言表


@dataclass(frozen=True)
class Declared:
    """数表 1 つの建前。**周期はここに書かれた日数だけで、既定を当てる経路が無い。**"""
    table_id: str
    cycle_days: int
    auto: str
    auto_source: str
    cycle_source: str
    next_change: str = ""
    next_change_source: str = ""
    number: int = 0

    def issues(self) -> tuple[Pending, ...]:
        where = f"周期の宣言表 行 {self.number}({self.table_id})"
        out: list[Pending] = []
        if not self.auto_source or not self.cycle_source:
            out.append(Pending(STOP_REASONS[0], where))
        if self.cycle_days < 1:
            out.append(Pending(STOP_REASONS[2], f"{where}: {self.cycle_days}"))
        if self.next_change and not self.next_change_source:
            out.append(Pending(STOP_REASONS[7], f"{where}: {self.next_change}"))
        return tuple(out)


@dataclass(frozen=True)
class Declarations:
    items: tuple[Declared, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Declarations":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"周期の宣言表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Declarations":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in SENGEN_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("周期の宣言表に " + " / ".join(lack) + " の列が無い")
        items: list[Declared] = []
        pending: list[Pending] = []
        seen: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in SENGEN_COLUMNS}
            where = f"周期の宣言表 行 {i}"
            if bad_id(cell["table_id"]):
                raise ReadError(f"{where}: 数表 id が空欄か、区切り文字を含む"
                                f"({cell['table_id'] or '空欄'})")
            if cell["auto"] not in AUTO:
                raise ReadError(f"{where}: 自動で走る宣言が登録の 2 つでない"
                                f"({cell['auto'] or '空欄'})")
            cycle = whole(cell["cycle_days"], "宣言された周期", where)
            if cell["next_change"]:
                day_number(cell["next_change"])      # 形が違えば読めない
            if cell["table_id"] in seen:
                pending.append(Pending(STOP_REASONS[1], f"{where}: {cell['table_id']}"))
            seen.add(cell["table_id"])
            items.append(Declared(table_id=cell["table_id"], cycle_days=cycle,
                                  auto=cell["auto"], auto_source=cell["auto_source"],
                                  cycle_source=cell["cycle_source"],
                                  next_change=cell["next_change"],
                                  next_change_source=cell["next_change_source"],
                                  number=i))
        if not items:
            raise ReadError("周期の宣言表に行が無い(ヘッダだけ)")
        for d in items:
            pending.extend(d.issues())
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    @property
    def ordered(self) -> tuple[Declared, ...]:
        return tuple(sorted(self.items, key=lambda d: d.table_id))

    @property
    def tables(self) -> tuple[str, ...]:
        return tuple(sorted({d.table_id for d in self.items}))

    def of(self, table_id: str) -> Declared | None:
        """**宣言が無い数表には何も当てない**(None を返す = 「宣言が無い」へ)。"""
        return next((d for d in self.ordered if d.table_id == table_id), None)

    def swapped(self, how: str) -> "Declarations":
        return Declarations(items=tuple(swap_rows(list(self.items), how)),
                            pending=self.pending, path=self.path)


# ------------------------------------------------------------ 実行の履歴表


@dataclass(frozen=True)
class Run:
    """実行 1 回。**落ちた回に「中身が動いた件数」と「指紋」を持たせない。**"""
    run_id: str
    table_id: str
    ran_on: str
    result: str
    moved: int
    fingerprint: str
    source: str
    day: int = 0
    number: int = 0

    def issues(self) -> tuple[Pending, ...]:
        where = f"実行の履歴表 行 {self.number}({self.run_id}: {self.table_id})"
        out: list[Pending] = []
        if not self.source:
            out.append(Pending(STOP_REASONS[0], where))
        if self.result == FAILED and self.moved > 0:
            out.append(Pending(STOP_REASONS[3], f"{where}: {self.moved}"))
        if self.moved > 0 and not self.fingerprint:
            out.append(Pending(STOP_REASONS[4], where))
        if self.result == FAILED and self.fingerprint:
            out.append(Pending(STOP_REASONS[5], f"{where}: {self.fingerprint}"))
        return tuple(out)

    @property
    def counted_as_moved(self) -> bool:
        """**落ちた回と、動いた件数が 0 の回は、中身が動いた日に入らない。**"""
        return self.result == OK and self.moved > 0

    def as_result(self, result: str) -> "Run":
        """結果を替えた写し(verify が使う)。落ちた回には件数と指紋を残さない。"""
        failed = result == FAILED
        return Run(self.run_id, self.table_id, self.ran_on, result,
                   0 if failed else self.moved, "" if failed else self.fingerprint,
                   self.source, self.day, self.number)

    def as_moved(self, moved: int) -> "Run":
        return Run(self.run_id, self.table_id, self.ran_on, self.result, moved,
                   self.fingerprint, self.source, self.day, self.number)


@dataclass(frozen=True)
class Runs:
    items: tuple[Run, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Runs":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"実行の履歴表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Runs":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in RIREKI_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("実行の履歴表に " + " / ".join(lack) + " の列が無い")
        items: list[Run] = []
        seen: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in RIREKI_COLUMNS}
            where = f"実行の履歴表 行 {i}"
            for key, name in (("run_id", "実行 id"), ("table_id", "数表 id")):
                if bad_id(cell[key]):
                    raise ReadError(f"{where}: {name}が空欄か、区切り文字を含む"
                                    f"({cell[key] or '空欄'})")
            if cell["result"] not in RUN_RESULTS:
                raise ReadError(f"{where}: 結果が登録の 2 つでない"
                                f"({cell['result'] or '空欄'})")
            if cell["run_id"] in seen:
                raise ReadError(f"{where}: 同じ実行 id が 2 行ある({cell['run_id']})")
            seen.add(cell["run_id"])
            items.append(Run(run_id=cell["run_id"], table_id=cell["table_id"],
                             ran_on=cell["ran_on"], result=cell["result"],
                             moved=whole(cell["moved"], "中身が動いた件数", where),
                             fingerprint=cell["fingerprint"], source=cell["source"],
                             day=day_number(cell["ran_on"]), number=i))
        if not items:
            raise ReadError("実行の履歴表に行が無い(ヘッダだけ)")
        pending: list[Pending] = []
        for r in items:
            pending.extend(r.issues())
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    @property
    def ordered(self) -> tuple[Run, ...]:
        """実行日 → 実行 id の順(行順に依らない = 入れ替えても同じ出力)。"""
        return tuple(sorted(self.items, key=lambda r: (r.day, r.run_id)))

    @property
    def tables(self) -> tuple[str, ...]:
        return tuple(sorted({r.table_id for r in self.items}))

    def of(self, table_id: str) -> tuple[Run, ...]:
        return tuple(r for r in self.ordered if r.table_id == table_id)

    def upto(self, table_id: str, asof_day: int) -> tuple[Run, ...]:
        """**基準日より後の実行は 1 つも使わない**(3 つの日付のどれにも入らない)。"""
        return tuple(r for r in self.of(table_id) if r.day <= asof_day)

    def by_id(self, run_id: str) -> Run | None:
        return next((r for r in self.ordered if r.run_id == run_id), None)

    def with_result(self, run_id: str, result: str) -> "Runs":
        """実行 1 回の結果を替えた写し(verify が使う。入力には書かない)。"""
        return Runs(items=tuple(r.as_result(result) if r.run_id == run_id else r
                                for r in self.items),
                    pending=self.pending, path=self.path)

    def with_moved(self, run_id: str, moved: int) -> "Runs":
        return Runs(items=tuple(r.as_moved(moved) if r.run_id == run_id else r
                                for r in self.items),
                    pending=self.pending, path=self.path)

    def swapped(self, how: str) -> "Runs":
        return Runs(items=tuple(swap_rows(list(self.items), how)),
                    pending=self.pending, path=self.path)


# ------------------------------------------------------------ 問いの一覧


@dataclass(frozen=True)
class Question:
    table_id: str
    asof: str
    source: str
    day: int = 0
    number: int = 0

    @property
    def key(self) -> str:
        return f"{self.table_id}@{self.asof}"

    def issues(self) -> tuple[Pending, ...]:
        where = f"問いの一覧 行 {self.number}({self.key})"
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
            if bad_id(cell["table_id"]):
                raise ReadError(f"{where}: 数表 id が空欄か、区切り文字を含む"
                                f"({cell['table_id'] or '空欄'})")
            key = (cell["table_id"], cell["asof"])
            if key in seen:
                raise ReadError(f"{where}: 同じ問いが 2 行ある({' / '.join(key)})")
            seen.add(key)
            if cell["swap"]:
                swaps.add(cell["swap"])
            items.append(Question(table_id=cell["table_id"], asof=cell["asof"],
                                  source=cell["source"],
                                  day=day_number(cell["asof"]), number=i))
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
        return tuple(sorted(self.items, key=lambda q: (q.table_id, q.asof)))

    @property
    def tables(self) -> tuple[str, ...]:
        return tuple(sorted({q.table_id for q in self.items}))

    def swapped(self, how: str) -> "Questions":
        return Questions(items=tuple(swap_rows(list(self.items), how)),
                         pending=self.pending, swap=self.swap, path=self.path)


# ------------------------------------------------------------ 突き合わせる


@dataclass(frozen=True)
class Judged:
    """問い 1 件の結果。3 つの日付は別の列で、1 つに潰す経路が無い。"""
    question: Question
    result: str
    ran_last: str = ""
    moved_last: str = ""
    ok_last: str = ""
    gap_days: int | None = None
    over_days: int | None = None

    @property
    def candidate(self) -> bool:
        """鮮度候補か(基準日より前の実行が無い問いは分母の外)。"""
        return self.result != SOTO

    @property
    def dated(self) -> bool:
        return self.result in HIZUKE

    def line(self) -> str:
        days = (f"{'' if self.gap_days is None else self.gap_days}"
                f"/{'' if self.over_days is None else self.over_days}")
        return (f"{self.question.key}:{self.result}:{self.ran_last}"
                f"/{self.moved_last}/{self.ok_last}:{days}")

    def three_dates(self) -> dict[str, object]:
        """3 つの日付を別の列で並べる。**基準日より前の実行だけから出す。**"""
        return {"数表 id": self.question.table_id, "基準日": self.question.asof,
                "判定": self.result,
                DATE_KEYS[0]: self.ran_last, DATE_KEYS[1]: self.moved_last,
                DATE_KEYS[2]: self.ok_last,
                "空き日数": "" if self.gap_days is None else self.gap_days,
                "超過日数": "" if self.over_days is None else self.over_days,
                "問いの出典": self.question.source}


def judge(q: Question, decls: Declarations, runs: Runs) -> Judged:
    """問い 1 件に 6 値のどれか 1 つを付ける。**時計を読まない。理由も決めない。**

    宣言の無い数表には既定の周期を当てない。履歴が 1 行も無い数表と、基準日より前の実行が
    無い数表を分ける。落ちた回と中身が動いた件数 0 の回は「中身が動いた最後の日」に入れない。
    """
    rows = runs.upto(q.table_id, q.day)
    oks = [r for r in rows if r.result == OK]
    moved = [r for r in rows if r.counted_as_moved]
    dates = (rows[-1].ran_on if rows else "",
             moved[-1].ran_on if moved else "",
             oks[-1].ran_on if oks else "")
    d = decls.of(q.table_id)
    if d is None:
        return Judged(q, KEKKA[4], *dates)            # 宣言が無い
    if not runs.of(q.table_id):
        return Judged(q, KEKKA[3], *dates)            # 履歴が無い
    if not rows:
        return Judged(q, SOTO, *dates)                # 別枠
    if not moved:
        return Judged(q, KEKKA[2], *dates)            # 一度も動いていない
    gap = q.day - moved[-1].day
    over = gap - d.cycle_days
    return Judged(q, KEKKA[1] if over > 0 else KEKKA[0], *dates,
                  gap_days=gap, over_days=over if over > 0 else 0)


@dataclass(frozen=True)
class Report:
    ok: bool
    pending: tuple[Pending, ...]
    decls: int
    runs: int
    questions: int


@dataclass(frozen=True)
class Tally:
    report: Report
    judged: tuple[Judged, ...]
    decls: Declarations
    runs: Runs
    questions: Questions

    # ---------------- 分母

    def question_denominator(self) -> int:
        return self.report.questions

    @property
    def denominator(self) -> int:
        """鮮度候補の数(基準日より前の実行が無い問いを外した数)。"""
        return sum(1 for j in self.judged if j.candidate)

    def aside_denominator(self) -> int:
        return sum(1 for j in self.judged if not j.candidate)

    def dated_count(self) -> int:
        return sum(1 for j in self.judged if j.dated)

    def moved_date_count(self) -> int:
        return sum(1 for j in self.judged if j.moved_last)

    def datable_count(self) -> int:
        """日数を出せる条件がそろった問い = 中身が動いた最後の日が在り、周期の宣言も在る。

        **宣言が無い数表にも「中身が動いた最後の日」は出る**(履歴さえ在れば出る)。
        そこに既定の周期を当てないので、日数の欄は空のまま返る。だからこの数と
        「中身が動いた最後の日が在る問い」は同じにならないことがある。
        """
        return sum(1 for j in self.judged
                   if j.moved_last and self.decls.of(j.question.table_id) is not None)

    # ---------------- 件数

    def six(self) -> dict[str, int]:
        return {k: sum(1 for j in self.judged if j.result == k) for k in KEKKA}

    def by_table(self) -> list[dict[str, object]]:
        """数表ごとの内訳(合計が全体に戻るかが二重集計の検算になる)。"""
        out: list[dict[str, object]] = []
        for table_id in self.questions.tables:
            here = [j for j in self.judged if j.question.table_id == table_id]
            d = self.decls.of(table_id)
            out.append({"数表 id": table_id,
                        "宣言された周期(日)": d.cycle_days if d else "",
                        "自動で走る宣言": d.auto if d else "",
                        "問いの数": len(here),
                        "6 値": {k: sum(1 for j in here if j.result == k)
                                 for k in KEKKA},
                        "鮮度候補": sum(1 for j in here if j.candidate),
                        "日数まで出せた": sum(1 for j in here if j.dated),
                        "履歴の行数": len(self.runs.of(table_id))})
        return out

    def dates(self) -> list[dict[str, object]]:
        return [j.three_dates() for j in self.judged]

    def ran_but_not_moved(self) -> list[dict[str, object]]:
        """走ったが中身は動いていない実行だけの一覧(= 「最終実行」の名前で返る回)。"""
        out: list[dict[str, object]] = []
        for r in self.runs.ordered:
            if r.result != OK or r.moved > 0:
                continue
            last = self.runs.of(r.table_id)[-1]
            out.append({"実行 id": r.run_id, "数表 id": r.table_id,
                        "実行日": r.ran_on, "中身が動いた件数": r.moved,
                        "指紋": r.fingerprint,
                        "その数表の最後の実行か":
                            "そう" if last.run_id == r.run_id else "違う",
                        "出典": r.source})
        return out

    def clashes(self) -> list[dict[str, object]]:
        """件数と指紋が食い違う実行。**どちらが正しいとは決めない**(2 種類に分けるだけ)。"""
        out: list[dict[str, object]] = []
        for table_id in self.runs.tables:
            prev: Run | None = None
            for r in self.runs.of(table_id):
                if r.result != OK:
                    continue
                if prev is not None:
                    same = r.fingerprint == prev.fingerprint
                    kind = ""
                    if r.moved == 0 and not same:
                        kind = CLASH[0]
                    elif r.moved > 0 and same:
                        kind = CLASH[1]
                    if kind:
                        out.append({"種類": kind, "実行 id": r.run_id,
                                    "数表 id": table_id, "実行日": r.ran_on,
                                    "中身が動いた件数": r.moved, "指紋": r.fingerprint,
                                    "1 つ前の ok の実行": prev.run_id,
                                    "1 つ前の指紋": prev.fingerprint,
                                    "出典": r.source})
                prev = r
        return out

    def next_changes(self) -> list[dict[str, object]]:
        """次回改定の近さ。**鮮度と同じ列に入れない**(別の問いとして別枠で返す)。"""
        out: list[dict[str, object]] = []
        for j in self.judged:
            d = self.decls.of(j.question.table_id)
            if d is None or not d.next_change:
                continue
            out.append({"数表 id": d.table_id, "基準日": j.question.asof,
                        "次回改定の予定": d.next_change,
                        "基準日からの日数": day_number(d.next_change) - j.question.day,
                        "出典": d.next_change_source})
        return out

    def listed(self) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for k in KEKKA:
            here = [j for j in self.judged if j.result == k]
            out.append({"判定": k, "件数": len(here),
                        "問い": [j.three_dates() for j in here]})
        return out

    def stopped(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for p in self.report.pending:
            out[p.reason] = out.get(p.reason, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: STOP_REASONS.index(kv[0])))

    def counts(self) -> dict[str, object]:
        """件数は丸めず、3 つの分母と内訳つきで出す。達成率も点数も返さない。"""
        six = self.six()
        out: dict[str, object] = {
            "周期の宣言表の行数": self.report.decls,
            "実行の履歴表の行数": self.report.runs,
            "問いの数": self.report.questions,
            "分母(問いの数)": self.question_denominator(),
            "分母(鮮度候補の数)": self.denominator,
            "分母(別枠の数)": self.aside_denominator(),
            "6 値": six,
            "日数まで出せた件数": self.dated_count(),
            "中身が動いた最後の日が在る問い": self.moved_date_count(),
            "日数を出せる条件がそろった問い": self.datable_count(),
            "走ったが中身は動いていない実行": len(self.ran_but_not_moved()),
            "件数と指紋が食い違う実行": len(self.clashes()),
            "数表ごと": self.by_table(),
            "理由別の止まった件数": self.stopped(),
            "読んだか": ("読んだ" if self.judged else
                         "読んでいない(宣言が揃う前に止まったので 6 値は全て 0)"),
        }
        out["分母に含めたもの"] = (
            f"問いの数 {self.question_denominator()} 件のうち、基準日より前の実行が無い "
            f"{six[SOTO]} 件を外した {self.denominator} 件が鮮度候補。そのうち日数まで"
            f"出せたのは " + " + ".join(f"{k} {six[k]}" for k in HIZUKE)
            + f" の {self.dated_count()} 件で、残りは "
            + " + ".join(f"{k} {six[k]}" for k in KEKKA[2:5]))
        out["件数の合計の検算"] = (
            f"6 値の合計 {sum(six.values())} / 問いの数 "
            f"{self.question_denominator()}(5 値 {sum(six[k] for k in GOCHI)} = "
            f"鮮度候補 {self.denominator} も同じ、数表ごとの内訳の合計 "
            f"{sum(int(row['問いの数']) for row in self.by_table())} = 問いの数 も同じ、"
            f"日数まで出せた {self.dated_count()} = 日数を出せる条件がそろった問い "
            f"{self.datable_count()} も同じ)")
        out["基準日を時計から取らない"] = (
            "基準日は問いの一覧の列で、現在時刻を読む呼び出しがこの部品に 1 つも無い。"
            "日付は文字列から整数の通算日に直すだけなので、同じ入力なら何日後に走らせても"
            "同じ答えになる")
        out["落ちた回を最後の更新に数えない"] = (
            "結果が failed の行は「走った最後の日」にだけ入り、「中身が動いた最後の日」と"
            "「落ちた回を除いた最後の日」に入る経路が無い")
        out["差分 0 の実行を更新に数えない"] = (
            "中身が動いた件数が 0 の実行は「走った最後の日」にだけ入る。走った最後の日と"
            "中身が動いた最後の日は別の列で返り、1 つの「最終実行」に潰す経路が無い")
        out["既定の周期を当てない"] = (
            "宣言表に無い数表は「宣言が無い」に出す。週 1 を既定にする引数も、ほかの数表の"
            "周期を借りる経路も無い")
        out["遅れの理由を決めない"] = (
            "出すのは空き日数と超過日数だけで、登録がまだか・資料がまだ公表されていないか・"
            "改定が無かったかを分ける列が無い。自動で走る宣言の有無で判定を変える経路も無い")
        out["点数も割合も返さない"] = (
            "返るのは件数と日数と 3 つの分母だけで、達成の度合いを返す呼び方も option も無い")
        out["次回改定の近さは別枠"] = (
            "予定を受け取っても鮮度の列には入れず、別の一覧で返す。鮮度と改定の近さは"
            "別の問いだから、同じ列で足さない")
        out["食い違いをどちらが正とも決めない"] = (
            "件数と指紋が合わない実行は 2 種類に分けて並べるだけで、どちらを直すべきかを"
            "返す欄が無い")
        out["走らせない・取りに行かない"] = (
            "実行する経路もネットワークに触る経路も無く、数表の値を引く経路も計算する"
            "経路も無い。読むのは手元の 3 枚だけ")
        out["入力を書き換えない"] = (
            "verify が作る写し(結果を替えた履歴・動いた件数を替えた履歴)はメモリの中"
            "だけで、入力の CSV には 1 文字も書かない")
        return out

    def judgement_bytes(self) -> bytes:
        """判定部分 = 問いごとの 6 値と 3 つの日付。時刻・絶対パス・ホスト名は入れない。"""
        self._guard()
        lines = ["\t".join(["件", str(self.report.decls), str(self.report.runs),
                            str(self.report.questions)])]
        lines.extend(j.line() for j in self.judged)
        return ("\n".join(lines) + "\n").encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.judgement_bytes()).hexdigest()

    def read_condition(self) -> dict[str, str]:
        return {SCOPE_KEYS[0]: self.decls.path, SCOPE_KEYS[1]: self.runs.path,
                SCOPE_KEYS[2]: self.questions.path}

    def _guard(self) -> None:
        if not self.report.ok:
            raise RuntimeError("止まっているので数えた問いは無い。"
                               "report.pending の理由コードを見る")


def cadence_gap(decls: Declarations, runs: Runs, questions: Questions) -> Tally:
    """問い 1 件ごとに 6 値を付ける。

    3 枚のどれかが 1 行でも壊れていたら 1 件も数えない(6 値は全て 0)。
    """
    pending = list(decls.pending) + list(runs.pending) + list(questions.pending)
    known = set(decls.tables) | set(runs.tables)
    for q in questions.ordered:
        if q.table_id not in known:
            pending.append(Pending(STOP_REASONS[6],
                                   f"問いの一覧 行 {q.number}: {q.table_id}"))
    report = Report(not pending, tuple(pending), len(decls.items), len(runs.items),
                    len(questions.items))
    if pending:                     # 1 件も数えずに止まる
        return Tally(report=report, judged=(), decls=decls, runs=runs,
                     questions=questions)
    judged = tuple(judge(q, decls, runs) for q in questions.ordered)
    return Tally(report=report, judged=judged, decls=decls, runs=runs,
                 questions=questions)


# ------------------------------------------------------------ verify


def tail_is(runs: Runs, q: Question, run: Run, prev: Run) -> bool:
    """その問いから見て、直近 2 回の「中身が動いた実行」がちょうど prev → run か。"""
    moved = [r for r in runs.upto(q.table_id, q.day) if r.counted_as_moved]
    return (len(moved) >= 2 and moved[-1].run_id == run.run_id
            and moved[-2].run_id == prev.run_id)


def probe_plan(decls: Declarations, runs: Runs,
               first: Tally) -> list[tuple[Run, Run, tuple[Judged, ...]]]:
    """写しを当てる計画。**実行 1 回につき 1 組**で、(替える実行 / 1 つ前に動いた実行 /
    その写しで「宣言どおり」から動く問い)を返す。

    1 回の実行は複数の問い(基準日の違う問い)に効くので、**動く問いを入力から先に数えて
    おく**。替えた後の件数がこの数と合うかが verify の見るところになる。
    """
    plans: list[tuple[Run, Run, tuple[Judged, ...]]] = []
    seen: set[str] = set()
    for j in first.judged:
        if j.result != KEKKA[0]:
            continue
        rows = runs.upto(j.question.table_id, j.question.day)
        moved = [r for r in rows if r.counted_as_moved]
        if len(moved) < 2 or not rows or rows[-1].run_id != moved[-1].run_id:
            continue
        run, prev = moved[-1], moved[-2]
        if run.run_id in seen:
            continue
        seen.add(run.run_id)
        d = decls.of(run.table_id)
        cycle = d.cycle_days if d else 0
        shifted = tuple(x for x in first.judged
                        if x.result == KEKKA[0]
                        and x.question.table_id == run.table_id
                        and tail_is(runs, x.question, run, prev)
                        and x.question.day - prev.day > cycle)
        plans.append((run, prev, shifted))
    return plans


def moved_elsewhere(first: Tally, after: Tally, table_id: str) -> list[str]:
    """判定部分の行が動いた問いのうち、替えた実行の数表でないものの名前。"""
    was = {j.question.key: j.line() for j in first.judged}
    return sorted(j.question.key for j in after.judged
                  if j.line() != was.get(j.question.key)
                  and j.question.table_id != table_id)


def result_probe(decls: Declarations, runs: Runs, questions: Questions,
                 first: Tally) -> dict[str, object]:
    """最後の実行を ok から落ちた回に替えて数え直す。

    いつも成り立つはずのこと: **宣言どおりが動く問いの数だけ減って、遅れているが同じ数だけ
    増え**、超過日数が 1 つ前に動いた実行からの日数で出る。落ちた回を最後の更新に数えない
    ことの実測で、動くのは替えた実行と同じ数表の問いだけ。
    """
    rows: list[dict[str, object]] = []
    plans = probe_plan(decls, runs, first)
    ok = bool(plans) and all(shifted for _, _, shifted in plans)
    before = first.six()
    for run, prev, shifted in plans:
        after = cadence_gap(decls, runs.with_result(run.run_id, FAILED), questions)
        now = after.six()
        d = decls.of(run.table_id)
        cycle = d.cycle_days if d else 0
        each = []
        for x in shifted:
            mine = next(y for y in after.judged
                        if y.question.key == x.question.key)
            each.append(mine.result == KEKKA[1]
                        and mine.moved_last == prev.ran_on
                        and mine.ok_last == prev.ran_on
                        and mine.ran_last == x.ran_last
                        and mine.over_days == x.question.day - prev.day - cycle)
        fits = (after.report.ok and all(each)
                and now[KEKKA[0]] == before[KEKKA[0]] - len(shifted)
                and now[KEKKA[1]] == before[KEKKA[1]] + len(shifted)
                and all(now[k] == before[k] for k in KEKKA
                        if k not in (KEKKA[0], KEKKA[1]))
                and moved_elsewhere(first, after, run.table_id) == []
                and after.denominator == first.denominator)
        ok = ok and fits
        rows.append({"替えた実行 id": run.run_id, "数表 id": run.table_id,
                     "1 つ前に動いた実行": prev.run_id,
                     "動く問い": [x.question.key for x in shifted],
                     "宣言どおり": f"{before[KEKKA[0]]} → {now[KEKKA[0]]}",
                     "遅れている": f"{before[KEKKA[1]]} → {now[KEKKA[1]]}",
                     DATE_KEYS[0]: f"{run.ran_on} → {run.ran_on}",
                     DATE_KEYS[1]: f"{run.ran_on} → {prev.ran_on}",
                     DATE_KEYS[2]: f"{run.ran_on} → {prev.ran_on}",
                     "超過日数": [f"{x.over_days} → "
                                  f"{x.question.day - prev.day - cycle}"
                                  for x in shifted],
                     "ほかの数表で動いた問い":
                         moved_elsewhere(first, after, run.table_id),
                     "合うか": fits})
    return {"書き換えた欄": "実行 1 回の結果(写しはメモリの中だけ)",
            "分母(鮮度候補の数)": first.denominator, "行ごと": rows, "合うか": ok,
            "読み": ("落ちた回は「中身が動いた最後の日」にも「落ちた回を除いた最後の日」"
                     "にも入らないので、超過日数は 1 つ前に動いた実行から数え直される。"
                     "走った最後の日だけは動かない")}


def moved_probe(decls: Declarations, runs: Runs, questions: Questions,
                first: Tally) -> dict[str, object]:
    """最後の実行の中身が動いた件数を 0 に替えて数え直す(結果は ok のまま)。

    いつも成り立つはずのこと: **中身が動いた最後の日が 1 つ前に戻り、空き日数がその分だけ
    増える一方で、走った最後の日と落ちた回を除いた最後の日は動かない。**
    """
    rows: list[dict[str, object]] = []
    plans = probe_plan(decls, runs, first)
    ok = bool(plans) and all(shifted for _, _, shifted in plans)
    before = first.six()
    for run, prev, shifted in plans:
        after = cadence_gap(decls, runs.with_moved(run.run_id, 0), questions)
        now = after.six()
        each = []
        for x in shifted:
            mine = next(y for y in after.judged
                        if y.question.key == x.question.key)
            each.append(mine.result == KEKKA[1]
                        and mine.moved_last == prev.ran_on
                        and mine.ran_last == x.ran_last
                        and mine.ok_last == x.ok_last
                        and mine.gap_days == (x.gap_days or 0)
                        + (run.day - prev.day))
        fits = (after.report.ok and all(each)
                and now[KEKKA[0]] == before[KEKKA[0]] - len(shifted)
                and now[KEKKA[1]] == before[KEKKA[1]] + len(shifted)
                and all(now[k] == before[k] for k in KEKKA
                        if k not in (KEKKA[0], KEKKA[1]))
                and moved_elsewhere(first, after, run.table_id) == []
                and after.denominator == first.denominator)
        ok = ok and fits
        rows.append({"替えた実行 id": run.run_id, "数表 id": run.table_id,
                     "1 つ前に動いた実行": prev.run_id,
                     "動く問い": [x.question.key for x in shifted],
                     "宣言どおり": f"{before[KEKKA[0]]} → {now[KEKKA[0]]}",
                     "遅れている": f"{before[KEKKA[1]]} → {now[KEKKA[1]]}",
                     DATE_KEYS[0]: f"{run.ran_on} → {run.ran_on}",
                     DATE_KEYS[1]: f"{run.ran_on} → {prev.ran_on}",
                     DATE_KEYS[2]: f"{run.ran_on} → {run.ran_on}",
                     "空き日数": [f"{x.gap_days} → "
                                  f"{(x.gap_days or 0) + (run.day - prev.day)}"
                                  for x in shifted],
                     "ほかの数表で動いた問い":
                         moved_elsewhere(first, after, run.table_id),
                     "合うか": fits})
    return {"書き換えた欄": "実行 1 回の中身が動いた件数(写しはメモリの中だけ)",
            "分母(鮮度候補の数)": first.denominator, "行ごと": rows, "合うか": ok,
            "読み": ("走っても中身が動かなければ鮮度は進まない。走った最後の日と落ちた回を"
                     "除いた最後の日はどちらも動かないので、3 つの日付を分けて持つ意味が"
                     "ここで数として出る")}


def verify(decls: Declarations, runs: Runs, questions: Questions) -> dict[str, object]:
    """2 回読んで sha256 を比べ、3 枚の行順を入れ替えても同じかを見て、件数を検算する。
    さらに、結果を替えた写しと、動いた件数を替えた写しを読んで差分を出す。"""
    first = cadence_gap(decls, runs, questions)
    if not first.report.ok:
        return {"ok": False, "stage": "止まった(数えた問いは返さない)", **first.counts(),
                "pending": [p.as_dict() for p in first.report.pending]}
    if not questions.swap:
        raise ReadError("問いの一覧に入れ替え方(swap)が無いので verify は走らせない")
    second = cadence_gap(decls, runs, questions)
    how = questions.swap
    third = cadence_gap(decls.swapped(how), runs.swapped(how), questions.swapped(how))
    pending: list[Pending] = []
    if first.sha256() != second.sha256():
        pending.append(Pending(STOP_REASONS[9], f"2 回目 {second.sha256()[:12]}"))
    if not (third.report.ok and first.sha256() == third.sha256()):
        pending.append(Pending(STOP_REASONS[10],
                               f"入れ替え方 {how} の 3 枚で {third.sha256()[:12]}"
                               if third.report.ok else
                               f"入れ替え方 {how} の 3 枚では止まった"))
    six = first.six()
    if sum(six.values()) != first.question_denominator():
        pending.append(Pending(STOP_REASONS[8],
                               f"6 値の合計 {sum(six.values())} / 問いの数 "
                               f"{first.question_denominator()}"))
    inner = sum(six[k] for k in GOCHI)
    if inner != first.denominator:
        pending.append(Pending(STOP_REASONS[8],
                               f"5 値 {inner} / 鮮度候補 {first.denominator}"))
    by_table = sum(int(row["問いの数"]) for row in first.by_table())
    if by_table != first.question_denominator():
        pending.append(Pending(STOP_REASONS[8],
                               f"数表ごとの内訳の合計 {by_table} / 問いの数 "
                               f"{first.question_denominator()}"))
    if first.dated_count() != first.datable_count():
        pending.append(Pending(STOP_REASONS[8],
                               f"日数まで出せた {first.dated_count()} / 日数を出せる"
                               f"条件がそろった問い {first.datable_count()}"))
    if len(first.dates()) != first.question_denominator():
        pending.append(Pending(STOP_REASONS[8],
                               f"3 つの日付の一覧 {len(first.dates())} / 問いの数 "
                               f"{first.question_denominator()}"))
    out: dict[str, object] = {
        "ok": not pending, "読んだ回数": 2, "入れ替え方": how,
        "sha256": first.sha256(), "2 回目の sha256": second.sha256(),
        "入れ替えた 3 枚の sha256": third.sha256() if third.report.ok else "",
        "件数の検算": {"6 値": six, "6 値の合計": sum(six.values()), "5 値": inner,
                       "数表ごとの内訳の合計": by_table,
                       "日数まで出せた": first.dated_count(),
                       "中身が動いた最後の日が在る問い": first.moved_date_count(),
                       "日数を出せる条件がそろった問い": first.datable_count(),
                       "分母(問いの数)": first.question_denominator(),
                       "分母(鮮度候補の数)": first.denominator,
                       "分母(別枠の数)": first.aside_denominator()},
        "最後の実行を落ちた回に替えた写し": result_probe(decls, runs, questions, first),
        "中身が動いた件数を 0 に替えた写し": moved_probe(decls, runs, questions, first),
    }
    for key in ("最後の実行を落ちた回に替えた写し", "中身が動いた件数を 0 に替えた写し"):
        if not out[key]["合うか"]:        # type: ignore[index]
            pending.append(Pending(STOP_REASONS[8], f"{key} の件数が合わない"))
            out["ok"] = False
    if pending:
        out["観測"] = ("同じ表から違うバイト列が出た、または件数が合わない(平均も多数決も"
                       "しない。遅れていることの理由も決めない)")
        out["pending"] = [p.as_dict() for p in pending]
    return out


# ------------------------------------------------------------ ひな型

TEMPLATE_DECLS = [
    list(SENGEN_COLUMNS),
    ["D1", "7", AUTO[0], "合成の方針のメモ(架空)L1", "合成の方針のメモ(架空)L2",
     "", ""],
    ["D2", "30", AUTO[1], "合成の方針のメモ(架空)L3", "合成の方針のメモ(架空)L4",
     "", ""],
]
TEMPLATE_RUNS = [
    list(RIREKI_COLUMNS),
    ["R01", "D1", "2026-05-01", OK, "4", "fp1", "合成の履歴のメモ(架空)L1"],
    ["R02", "D1", "2026-05-08", OK, "0", "fp1", "合成の履歴のメモ(架空)L2"],
    ["R03", "D2", "2026-05-02", FAILED, "0", "", "合成の履歴のメモ(架空)L3"],
]
TEMPLATE_QUESTIONS = [
    list(TOI_COLUMNS),
    ["D1", "2026-05-20", "合成の問いのメモ(架空)L1", SWAPS[0]],
    ["D2", "2026-05-20", "合成の問いのメモ(架空)L2", ""],
]


def write_csv(path: Path, rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    return path


def init(dest: str | Path) -> tuple[Path, Path, Path]:
    d = Path(dest)
    return (write_csv(d / "周期の宣言.csv", TEMPLATE_DECLS),
            write_csv(d / "実行の履歴.csv", TEMPLATE_RUNS),
            write_csv(d / "問いの一覧.csv", TEMPLATE_QUESTIONS))


# ------------------------------------------------------------ CLI

def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def build_parser() -> argparse.ArgumentParser:
    """CLI は cadence / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = argparse.ArgumentParser(prog="cadence_gap",
                                 description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in SUBCOMMANDS[:3]:
        p = sub.add_parser(name)
        p.add_argument("decls")
        p.add_argument("runs")
        p.add_argument("questions")
    sub.add_parser(SUBCOMMANDS[3]).add_argument("dest")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == "init":
        print("書いた: " + " / ".join(str(p) for p in init(a.dest)))
        return 0
    try:
        decls, runs = Declarations.load(a.decls), Runs.load(a.runs)
        questions = Questions.load(a.questions)
        if a.cmd == "verify":
            out = verify(decls, runs, questions)
            _print(out)
            return 0 if out["ok"] else 3
        t = cadence_gap(decls, runs, questions)
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
        body["3 つの日付"] = t.dates()
        body["走ったが中身は動いていない実行"] = t.ran_but_not_moved()
        body["件数と指紋が食い違う実行"] = t.clashes()
        body["次回改定の近さ(別の問い)"] = t.next_changes()
        body["sha256"] = t.sha256()
        body["読んだ条件"] = t.read_condition()
    _print(body)
    return 0 if t.aside_denominator() == 0 and not t.stopped() else 3


if __name__ == "__main__":
    raise SystemExit(main())
