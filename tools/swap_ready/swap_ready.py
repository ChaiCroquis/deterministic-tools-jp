"""swap_ready — 入れ替えの経路 1 件を 1 行として、入れ替えられる状態かを 4 値に分ける。

**「ここは入れ替えてよい」と宣言された経路が在っても、入れ替えられる状態かどうかは別だ。**
受け入れ検査が入れ替える側と同じ束に入っている(内蔵)うちは、宣言は使われないまま残る。
しかも **「入れ替わっていない」と「入れ替わった跡を数える欄が無い」は別の事実**で、台帳に
欄が無い経路はどちらとも言えない。

この部品は、経路の台帳・受け入れ検査の台帳・跡の台帳(3 枚)と記号の登録表(2 枚)から、
経路 1 件ごとに 4 値 + 別枠 6 を付ける。**4 値の欄は 5 つある**((D) は線の外と未規定を
別の記号で返す)。

  (A) 許す宣言が在り、検査が独立で、跡が 1 件以上   = 使われている
  (B) 許す宣言は在るが、検査が内蔵か無い           = 入れ替えてよいが入れ替えられない
  (C) 許す宣言が在り検査も独立だが、跡が 0 件       = 入れ替えられるが入れ替えていない
  (D) 許さないと宣言(線の外)
  (D) 宣言なし(未規定)

別枠 6 = 出典が空 / 記号が登録の外 / その記号が要求する欄が空 / 矛盾する宣言 /
許可の範囲の外 / 跡を残す欄そのものが無い(= 0 件とは別の値。`数えられない` を返す)。

持たせていないものが規律になっている。

  - **入れ替えるべきかを決めない**(推奨の列・順位・点数・割合・合計の 1 値が無い)
  - **滞留の理由を推定しない**(理由は入力の注記を出典ごと写すだけ。空の行には
    `理由の記載なし` を入れる。理由を言い当てる辞書も分類器も持たない)
  - **自分では何も入れ替えない**(実行しない・import しない・構文解析しない・通信の経路が
    無い・入力フォルダの外を読まない)
  - **検査の中身を見ない**(検査が十分かは判定しない。走らせた結果を台帳に残すのも別の
    部品の領分)
  - **0 件と欄が無いを同じ値にしない**(跡の欄そのものが無い経路は別枠へ出し、`数えられない`
    を返す)
  - **範囲つきの許可を `許す` に寄せない**(`照合専用` のような限定の文字列を整数や真偽に
    直す経路が無い。範囲の判定は人が別の欄に書いた種別記号の列だけで行う)
  - **独立と書いただけでは独立にしない**(検査が在る束の名前を書かせ、入れ替える側の束と
    同じ名前なら矛盾する宣言として別枠へ出す)
  - **時計を読まない**(基準日は呼び出し側が渡す)、**入力を書き換えない**、
    **float を使わない**、判定部分に時刻・絶対パス・ホスト名を入れない

**登録表 2 枚の行に出典が無ければ、1 経路も数えずに止まる。**

経路の台帳(CSV)の列は 8。

    route_id     経路 id(同じ id が 2 行あると止まる)
    kind         入れ替える対象の種別記号(版 / 実装 / data / 行)
    bundle       入れ替える側の束の名前
    permission   許す宣言の記号(登録表に在る記号だけ。無ければ別枠へ)
    scope_note   許可の範囲の注記(`照合専用` のような限定の文字列を**生のまま**。無ければ `—`)
    scope_kinds  範囲に含める対象の種別記号を `/` で区切った列(無ければ `—`)
    declared_on  宣言された日(`YYYY-MM-DD`。記載が無ければ `—`)
    source       出典(ファイル名 + 行番号)。空欄のとき、その経路は別枠「出典が空」へ入る

受け入れ検査の台帳(CSV)の列は 5。**1 経路に 0〜N 行。**

    check_id   検査 id
    route_id   経路 id(経路の台帳に無いと読めない)
    placement  検査の所属記号(独立 / 内蔵 / 無い)
    bundle     検査が在る束の名前(`独立` の宣言が要求する欄)
    source     出典。空欄のとき、その経路は別枠「出典が空」へ入る

跡の台帳(CSV)の列は 6。**1 経路に 0〜N 行。** 理由だけの行は `field` を `—` にする。

    route_id   経路 id
    field      跡を残す欄の名前(`—` = 欄が無い)
    observed   その欄で入れ替わりが観測された件数(整数。`—` = 数えない)
    range      観測した行の範囲(例 `11 行`)
    reason     理由の注記(**入力の文字をそのまま写す**。空欄のときは `理由の記載なし`)
    source     出典。空欄のとき、その経路は別枠「出典が空」へ入る

記号の登録表 2 枚(CSV)の列は 4。**「その記号が何を要求するか」はここに在る。**

    許す宣言の登録表    permission / means / requires(— / 宣言された日 / 許可の範囲)/ source
    検査の所属の登録表  placement  / means / requires(— / 束の名前)/ source

使い方:

    python swap_ready.py init ひな型/
    python swap_ready.py check 経路.csv 検査.csv 跡.csv 許す宣言.csv 検査の所属.csv 2026-09-20
    python swap_ready.py report 経路.csv 検査.csv 跡.csv 許す宣言.csv 検査の所属.csv 2026-09-20
    python swap_ready.py verify 経路.csv 検査.csv 跡.csv 許す宣言.csv 検査の所属.csv 2026-09-20

終了コードは、止まらず・別枠 0 件・(B) と (C) と「(D) 宣言なし」が 0 件のときだけ 0、
在れば 3、表として読めなければ 2。**0 は「入れ替えてよい」ではなく「使われていない許可が
台帳に無い」の意味で、入れ替えるべきかはこの部品の出力に出ない。**
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROUTE_COLUMNS = ("route_id", "kind", "bundle", "permission", "scope_note",
                 "scope_kinds", "declared_on", "source")
CHECK_COLUMNS = ("check_id", "route_id", "placement", "bundle", "source")
TRACE_COLUMNS = ("route_id", "field", "observed", "range", "reason", "source")
PERM_COLUMNS = ("permission", "means", "requires", "source")
PLACE_COLUMNS = ("placement", "means", "requires", "source")

# 入れ替える対象の種別記号(**この 4 つの外に記号を作る経路が無い**)
KINDS = ("版", "実装", "data", "行")
# 許す宣言の記号(**登録表にこの 4 つが揃っていないと止まる**)
PERMISSIONS = ("許す", "範囲つきで許す", "許さない", "宣言なし")
# 検査の所属記号(**独立 = 入れ替える側と別の束 / 内蔵 = 同じ束 / 無い**)
PLACEMENTS = ("独立", "内蔵", "無い")
# 記号が要求できる欄(**記号の綴りから当てる経路が無く、登録表の側に書く**)
PERM_REQUIRES = ("—", "宣言された日", "許可の範囲")
PLACE_REQUIRES = ("—", "束の名前")

NO_MARK = "—"
NO_ROW = "(検査の行が無い)"
UNCOUNTABLE = "数えられない"
NO_REASON = "理由の記載なし"
NO_DECLARED = "宣言された日の記載なし"

# 経路 1 件に付く 4 値。**(D) は線の外と未規定を別の記号で返すので欄は 5 つ。**
VALUES = (
    "(A) 許す宣言が在り、検査が独立で、跡が 1 件以上",
    "(B) 許す宣言は在るが、検査が内蔵か無い",
    "(C) 許す宣言が在り検査も独立だが、跡が 0 件",
    "(D) 許さないと宣言(線の外)",
    "(D) 宣言なし(未規定)",
)
# 4 値の外へ出す別枠 6。**上から順に当たり、4 値より先に当たる。**
BETSUWAKU = (
    "出典が空",
    "記号が登録の外",
    "その記号が要求する欄が空",
    "矛盾する宣言",
    "許可の範囲の外",
    "跡を残す欄そのものが無い",
)
# 1 経路も数えずに止まる理由コード 7(**表と登録の側の不備**)
TABLE_REASONS = (
    "登録の行の出典が空",
    "経路 id の重複",
    "登録表に無い記号が在る",
    "要求する欄が決めた欄の外",
    "基準日が渡されていない",
    "宣言された日が基準日より後",
    "跡の件数が整数でない",
)
# 行順の入れ替え方(verify が 3 通り試す)
SWAPS = ("逆順", "先頭を末尾へ", "末尾を先頭へ")
SUBCOMMANDS = ("check", "report", "verify", "init")


class ReadError(Exception):
    """表として読めない(列・行・id・参照の形が決めた形でない)。"""


@dataclass(frozen=True)
class Pending:
    """止まった理由 1 件(**作った 4 値は返さない**)。"""
    reason: str
    where: str

    def as_dict(self) -> dict[str, str]:
        return {"理由": self.reason, "場所": self.where}


def bad_id(s: str) -> bool:
    return (not s) or s != s.strip() or "," in s


def swap_rows(rows: list, how: str) -> list:
    if how == SWAPS[0]:
        return list(reversed(rows))
    if how == SWAPS[1] and rows:
        return rows[1:] + rows[:1]
    if how == SWAPS[2] and rows:
        return rows[-1:] + rows[:-1]
    return list(rows)


def _rows_of(text: str, columns: tuple[str, ...], what: str,
             allow_empty: bool = False) -> list[list[str]]:
    r = csv.reader(io.StringIO(text))
    try:
        head = [c.strip() for c in next(r)]
    except StopIteration:
        raise ReadError(f"{what} に見出し行が無い")
    if tuple(head) != columns:
        raise ReadError(f"{what} の列が決めた形と違う: {head}")
    rows = [[c.strip() for c in row] for row in r if any(c.strip() for c in row)]
    for row in rows:
        if len(row) != len(columns):
            raise ReadError(f"{what} に列数の合わない行が在る: {row[:2]}")
    if not rows and not allow_empty:
        raise ReadError(f"{what} に行が無い")
    return rows


def _iso(s: str, what: str) -> dt.date | None:
    if s == NO_MARK or not s:
        return None
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        raise ReadError(f"{what} が日付の形でない: {s}")


# ------------------------------------------------------------ 入力の 5 枚

@dataclass(frozen=True)
class Route:
    route_id: str
    kind: str
    bundle: str
    permission: str
    scope_note: str
    scope_kinds: str
    declared_on: str
    source: str

    @property
    def in_scope(self) -> tuple[str, ...]:
        """範囲に含める種別記号の列。**注記の文字(`照合専用`)は読まない。**"""
        if self.scope_kinds in (NO_MARK, ""):
            return ()
        return tuple(x.strip() for x in self.scope_kinds.split("/") if x.strip())


class Routes:
    """経路の台帳。**行順を入れ替えても出力が同じになるよう、読んだ順は別に持つ。**"""

    def __init__(self, rows: list[list[str]]) -> None:
        self.rows = [list(r) for r in rows]
        self.items: tuple[Route, ...] = tuple(Route(*r) for r in rows)
        for x in self.items:
            if bad_id(x.route_id):
                raise ReadError(f"経路 id が空か区切り文字を含む: {x.route_id!r}")
            if x.kind not in KINDS:
                raise ReadError(f"対象の種別記号が決めた 4 つの外: {x.kind!r}")
            if not x.bundle:
                raise ReadError(f"入れ替える側の束の名前が空: 経路 {x.route_id}")
            _iso(x.declared_on, f"経路 {x.route_id} の宣言された日")

    @classmethod
    def parse(cls, text: str) -> "Routes":
        return cls(_rows_of(text, ROUTE_COLUMNS, "経路の台帳"))

    @classmethod
    def load(cls, path: str | Path) -> "Routes":
        return cls.parse(Path(path).read_text(encoding="utf-8-sig"))

    def swapped(self, how: str) -> "Routes":
        return Routes(swap_rows(self.rows, how))

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(sorted({x.route_id for x in self.items}))

    def duplicated(self) -> tuple[str, ...]:
        seen: dict[str, int] = {}
        for x in self.items:
            seen[x.route_id] = seen.get(x.route_id, 0) + 1
        return tuple(sorted(k for k, v in seen.items() if v > 1))

    def of(self, route_id: str) -> Route:
        return next(x for x in self.items if x.route_id == route_id)


@dataclass(frozen=True)
class Check:
    check_id: str
    route_id: str
    placement: str
    bundle: str
    source: str


class Checks:
    def __init__(self, rows: list[list[str]], route_ids: tuple[str, ...]) -> None:
        self.rows = [list(r) for r in rows]
        self.items: tuple[Check, ...] = tuple(Check(*r) for r in rows)
        self.route_ids = route_ids
        for x in self.items:
            if bad_id(x.check_id):
                raise ReadError(f"検査 id が空か区切り文字を含む: {x.check_id!r}")
            if x.route_id not in route_ids:
                raise ReadError(f"検査の経路 id が台帳に無い: {x.route_id}")

    @classmethod
    def parse(cls, text: str, route_ids: tuple[str, ...]) -> "Checks":
        return cls(_rows_of(text, CHECK_COLUMNS, "受け入れ検査の台帳", True), route_ids)

    @classmethod
    def load(cls, path: str | Path, route_ids: tuple[str, ...]) -> "Checks":
        return cls.parse(Path(path).read_text(encoding="utf-8-sig"), route_ids)

    def swapped(self, how: str) -> "Checks":
        return Checks(swap_rows(self.rows, how), self.route_ids)

    def of_route(self, route_id: str) -> tuple[Check, ...]:
        return tuple(sorted((x for x in self.items if x.route_id == route_id),
                            key=lambda x: x.check_id))


@dataclass(frozen=True)
class Trace:
    route_id: str
    field: str
    observed: str
    span: str
    reason: str
    source: str

    @property
    def counts(self) -> bool:
        """跡を残す欄が在る行か(`—` は欄が無い宣言で、0 件とは別の値)。"""
        return self.field not in (NO_MARK, "")


class Traces:
    def __init__(self, rows: list[list[str]], route_ids: tuple[str, ...]) -> None:
        self.rows = [list(r) for r in rows]
        self.items: tuple[Trace, ...] = tuple(Trace(*r) for r in rows)
        self.route_ids = route_ids
        for x in self.items:
            if x.route_id not in route_ids:
                raise ReadError(f"跡の経路 id が台帳に無い: {x.route_id}")

    @classmethod
    def parse(cls, text: str, route_ids: tuple[str, ...]) -> "Traces":
        return cls(_rows_of(text, TRACE_COLUMNS, "跡の台帳", True), route_ids)

    @classmethod
    def load(cls, path: str | Path, route_ids: tuple[str, ...]) -> "Traces":
        return cls.parse(Path(path).read_text(encoding="utf-8-sig"), route_ids)

    def swapped(self, how: str) -> "Traces":
        return Traces(swap_rows(self.rows, how), self.route_ids)

    def of_route(self, route_id: str) -> tuple[Trace, ...]:
        return tuple(x for x in self.items if x.route_id == route_id)

    def not_integer(self) -> tuple[str, ...]:
        out: list[str] = []
        for x in self.items:
            if x.observed in (NO_MARK, ""):
                continue
            if not x.observed.isdigit():
                out.append(f"経路 {x.route_id} の件数 {x.observed!r}")
        return tuple(out)


@dataclass(frozen=True)
class Symbol:
    name: str
    means: str
    requires: str
    source: str


class Registry:
    """記号の登録表 1 枚。**記号が要求する欄はここに在る(綴りから当てる経路が無い)。**"""

    def __init__(self, rows: list[list[str]], columns: tuple[str, ...],
                 allowed: tuple[str, ...], requires: tuple[str, ...],
                 what: str) -> None:
        self.rows = [list(r) for r in rows]
        self.columns, self.what = columns, what
        self.allowed, self.requires_allowed = allowed, requires
        self.items: tuple[Symbol, ...] = tuple(Symbol(*r) for r in rows)
        seen: set[str] = set()
        for x in self.items:
            if x.name not in allowed:
                raise ReadError(f"{what} に決めた記号の外が在る: {x.name!r}")
            if x.name in seen:
                raise ReadError(f"{what} に同じ記号が 2 行: {x.name}")
            seen.add(x.name)

    @classmethod
    def parse(cls, text: str, columns: tuple[str, ...], allowed: tuple[str, ...],
              requires: tuple[str, ...], what: str) -> "Registry":
        return cls(_rows_of(text, columns, what), columns, allowed, requires, what)

    @classmethod
    def load(cls, path: str | Path, columns: tuple[str, ...], allowed: tuple[str, ...],
             requires: tuple[str, ...], what: str) -> "Registry":
        return cls.parse(Path(path).read_text(encoding="utf-8-sig"),
                         columns, allowed, requires, what)

    def swapped(self, how: str) -> "Registry":
        return Registry(swap_rows(self.rows, how), self.columns, self.allowed,
                        self.requires_allowed, self.what)

    def has(self, name: str) -> bool:
        return any(x.name == name for x in self.items)

    def requires_of(self, name: str) -> str:
        return next(x.requires for x in self.items if x.name == name)

    def missing(self) -> tuple[str, ...]:
        return tuple(n for n in self.allowed if not self.has(n))

    def sourceless(self) -> tuple[str, ...]:
        return tuple(x.name for x in self.items if not x.source)

    def bad_requires(self) -> tuple[str, ...]:
        return tuple(f"{x.name} → {x.requires!r}" for x in self.items
                     if x.requires not in self.requires_allowed)


def load_permissions(path: str | Path) -> Registry:
    return Registry.load(path, PERM_COLUMNS, PERMISSIONS, PERM_REQUIRES,
                         "許す宣言の登録表")


def load_placements(path: str | Path) -> Registry:
    return Registry.load(path, PLACE_COLUMNS, PLACEMENTS, PLACE_REQUIRES,
                         "検査の所属の登録表")


# ------------------------------------------------------------ 4 値を付ける

@dataclass(frozen=True)
class Row:
    """経路 1 件の結果。**推奨・順位・点数の欄は無い。**"""
    route_id: str
    kind: str
    bundle: str
    permission: str
    placement: str
    check_bundle: str
    value: str
    field: str
    observed: str
    span: str
    days: str
    reasons: tuple[str, ...]

    @property
    def graded(self) -> bool:
        return self.value in VALUES

    @property
    def stalled(self) -> bool:
        return self.value in (VALUES[1], VALUES[2])

    def as_dict(self) -> dict[str, object]:
        return {"経路 id": self.route_id, "対象の種別": self.kind,
                "入れ替える側の束": self.bundle, "許す宣言": self.permission,
                "検査の所属": self.placement, "検査が在る束": self.check_bundle,
                "4 値 / 別枠": self.value, "跡の欄": self.field,
                "跡の件数": self.observed, "観測した行の範囲": self.span,
                "宣言された日からの日数": self.days,
                "理由(出典ごと写す)": list(self.reasons)}


def _reasons_of(traces: tuple[Trace, ...]) -> tuple[str, ...]:
    """**理由は入力の注記を出典ごと写すだけ。** 空の行には `理由の記載なし` を入れる。"""
    out = tuple(f"{x.reason}(出典 = {x.source})" for x in traces if x.reason)
    return out or (NO_REASON,)


def _trace_view(traces: tuple[Trace, ...]) -> tuple[str, str, str]:
    """跡の欄の名前 / 件数 / 観測した行の範囲。**欄が無ければ `数えられない`。**"""
    counted = [x for x in traces if x.counts]
    if not counted:
        return NO_MARK, UNCOUNTABLE, NO_MARK
    total = sum(int(x.observed) for x in counted if x.observed.isdigit())
    return (" / ".join(sorted(x.field for x in counted)), str(total),
            " / ".join(sorted({x.span for x in counted if x.span})) or NO_MARK)


def judge(route: Route, checks: tuple[Check, ...], traces: tuple[Trace, ...],
          perms: Registry, places: Registry, asof: dt.date) -> Row:
    """経路 1 件に 4 値か別枠を付ける。**別枠が 4 値より先に当たる。**"""
    field, observed, span = _trace_view(traces)
    declared = _iso(route.declared_on, "宣言された日")
    days = str((asof - declared).days) if declared else NO_DECLARED
    reasons = _reasons_of(traces)
    placements = sorted({x.placement for x in checks})
    placement = placements[0] if len(placements) == 1 else (
        " / ".join(placements) if placements else NO_ROW)
    check_bundle = checks[0].bundle if len(checks) == 1 else (
        " / ".join(sorted({x.bundle for x in checks})) if checks else NO_MARK)

    def row(value: str) -> Row:
        return Row(route.route_id, route.kind, route.bundle, route.permission,
                   placement, check_bundle, value, field, observed, span, days,
                   reasons)

    # 別枠(上から順に当たり、4 値より先に当たる)
    if (not route.source or any(not x.source for x in checks)
            or any(not x.source for x in traces)):
        return row(BETSUWAKU[0])
    if (not perms.has(route.permission)
            or any(not places.has(x.placement) for x in checks)):
        return row(BETSUWAKU[1])
    need = perms.requires_of(route.permission)
    if need == PERM_REQUIRES[1] and route.declared_on in (NO_MARK, ""):
        return row(BETSUWAKU[2])
    if need == PERM_REQUIRES[2] and (route.scope_note in (NO_MARK, "")
                                     or not route.in_scope):
        return row(BETSUWAKU[2])
    for x in checks:
        if places.requires_of(x.placement) == PLACE_REQUIRES[1] and not x.bundle:
            return row(BETSUWAKU[2])
    if len(placements) > 1:
        return row(BETSUWAKU[3])
    if any(x.placement == PLACEMENTS[0] and x.bundle == route.bundle for x in checks):
        return row(BETSUWAKU[3])
    fields = [x.field for x in traces if x.counts]
    if len(fields) != len(set(fields)):
        return row(BETSUWAKU[3])
    if route.permission == PERMISSIONS[1] and route.kind not in route.in_scope:
        return row(BETSUWAKU[4])

    # 4 値(欄は 5 つ)
    if route.permission == PERMISSIONS[2]:
        return row(VALUES[3])
    if route.permission == PERMISSIONS[3]:
        return row(VALUES[4])
    if placement != PLACEMENTS[0]:
        return row(VALUES[1])
    if observed == UNCOUNTABLE:
        return row(BETSUWAKU[5])
    return row(VALUES[0] if int(observed) >= 1 else VALUES[2])


# ------------------------------------------------------------ 表 1 枚ぶんの結果

@dataclass(frozen=True)
class Report:
    ok: bool
    pending: tuple[Pending, ...]


@dataclass(frozen=True)
class Table:
    routes: Routes
    checks: Checks
    traces: Traces
    perms: Registry
    places: Registry
    asof: str
    rows: tuple[Row, ...]
    report: Report

    # ---- 数え上げ

    def denominator(self) -> int:
        return len(self.rows)

    def five(self) -> dict[str, int]:
        return {k: sum(1 for x in self.rows if x.value == k) for k in VALUES}

    def extras(self) -> dict[str, int]:
        return {k: sum(1 for x in self.rows if x.value == k) for k in BETSUWAKU}

    def stopped(self) -> int:
        return len(self.report.pending)

    def by_kind(self) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for kind in KINDS:
            rows = [x for x in self.rows if x.kind == kind]
            out.append({"対象の種別": kind, "経路の件数": len(rows),
                        "内訳": {k: sum(1 for x in rows if x.value == k)
                                 for k in VALUES + BETSUWAKU}})
        return out

    def by_bundle(self) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for bundle in sorted({x.bundle for x in self.rows}):
            rows = [x for x in self.rows if x.bundle == bundle]
            out.append({"入れ替える側の束": bundle, "経路の件数": len(rows),
                        "内訳": {k: sum(1 for x in rows if x.value == k)
                                 for k in VALUES + BETSUWAKU}})
        return out

    def stall(self) -> dict[str, object]:
        """滞留の量は 3 つだけ。**推奨も順位も割合も返さない。**"""
        ordered = sorted(self.rows, key=lambda r: r.route_id)
        return {
            "(B) + (C) の件数": sum(1 for x in self.rows if x.stalled),
            "跡の件数(0 を含む / 欄が無い経路は 数えられない)":
                {x.route_id: x.observed for x in ordered},
            "宣言された日から基準日までの日数":
                {x.route_id: x.days for x in ordered},
        }

    def reasons(self) -> dict[str, list[str]]:
        return {x.route_id: list(x.reasons)
                for x in sorted(self.rows, key=lambda r: r.route_id)}

    def crosscheck(self) -> str:
        total = sum(self.five().values()) + sum(self.extras().values())
        by_kind = sum(int(r["経路の件数"]) for r in self.by_kind())
        by_bundle = sum(int(r["経路の件数"]) for r in self.by_bundle())
        return (f"4 値 + 別枠 の合計 {total} / 経路の件数 {self.denominator()}"
                f"(種別ごとの合計 {by_kind}、束ごとの合計 {by_bundle})")

    def counts(self) -> dict[str, object]:
        return {"基準日": self.asof,
                "経路の台帳の行数": len(self.routes.items),
                "受け入れ検査の台帳の行数": len(self.checks.items),
                "跡の台帳の行数": len(self.traces.items),
                "登録表の行数": {"許す宣言": len(self.perms.items),
                                 "検査の所属": len(self.places.items)},
                "分母(経路の件数)": self.denominator(),
                "4 値": self.five(),
                "別枠": self.extras(),
                "滞留の量": self.stall(),
                "件数の合計の検算": self.crosscheck(),
                **MOTANAI}

    def listed(self) -> list[dict[str, object]]:
        return [x.as_dict() for x in sorted(self.rows, key=lambda r: r.route_id)]

    # ---- 判定部分(**時刻・絶対パス・ホスト名を入れない**)

    def judgement_bytes(self) -> bytes:
        if not self.report.ok:
            raise RuntimeError("止まった表の判定部分は作らない")
        body = {"基準日": self.asof,
                "経路": [[x.route_id, x.kind, x.bundle, x.permission, x.placement,
                          x.value, x.field, x.observed, x.days, list(x.reasons)]
                         for x in sorted(self.rows, key=lambda r: r.route_id)]}
        return json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.judgement_bytes()).hexdigest()

    def read_condition(self) -> dict[str, object]:
        return {"経路の台帳の行数": len(self.routes.items),
                "受け入れ検査の台帳の行数": len(self.checks.items),
                "跡の台帳の行数": len(self.traces.items),
                "基準日": self.asof,
                "決めた対象の種別": list(KINDS),
                "決めた許す宣言の記号": list(PERMISSIONS),
                "決めた検査の所属記号": list(PLACEMENTS)}


# **出力の末尾に必ず並ぶ 10 行(消す引数も option も無い)**
MOTANAI: dict[str, str] = {
    "入れ替えるべきかを決めない":
        "推奨・順位・点数・割合・合計の 1 値を出す列が無い。終了コード 0 も"
        "「使われていない許可が台帳に無い」の意味で、入れ替えてよいの意味ではない",
    "滞留の理由を推定しない":
        "理由は入力の注記を出典ごと写すだけで、空の行には `理由の記載なし` を入れる。"
        "理由を言い当てる辞書も分類器も持たない",
    "自分では何も入れ替えない":
        "実行しない・import しない・構文解析しない・通信の経路が無い・"
        "入力フォルダの外を読まない",
    "検査の中身を見ない":
        "検査が十分かは判定しない。見るのは所属(どちらの束に在るか)と、"
        "その宣言が要求する欄が埋まっているかまで",
    "0 件と欄が無いを同じ値にしない":
        "跡の欄そのものが無い経路は別枠へ出し、件数の欄は `数えられない` を返す",
    "範囲つきの許可を `許す` に寄せない":
        "`照合専用` のような限定の文字列を整数や真偽に直す経路が無い。範囲の判定は"
        "人が別の欄に書いた種別記号の列だけで行い、注記の文字は読まない",
    "独立と書いただけでは独立にしない":
        "検査が在る束の名前を要求し、入れ替える側の束と同じ名前なら矛盾する宣言として"
        "別枠へ出す",
    "時計を読まない": "基準日は呼び出し側が渡す。現在時刻を読む呼び出しを持たない",
    "入力を書き換えない":
        "verify が作る写しはメモリの中だけで、5 枚の CSV に 1 文字も書かない",
    "float を使わない": "件数と日数は整数、ほかは文字列",
}


def swap_ready(routes: Routes, checks: Checks, traces: Traces, perms: Registry,
               places: Registry, asof: str) -> Table:
    """5 枚から経路ごとの 4 値を出す。**表と登録の側が壊れていたら 1 経路も数えない。**"""
    pending: list[Pending] = []
    for reg in (perms, places):
        for name in reg.sourceless():
            pending.append(Pending(TABLE_REASONS[0], f"{reg.what} の {name}"))
    for route_id in routes.duplicated():
        pending.append(Pending(TABLE_REASONS[1], f"経路 {route_id}"))
    for reg in (perms, places):
        for name in reg.missing():
            pending.append(Pending(TABLE_REASONS[2], f"{reg.what} に {name} が無い"))
        for bad in reg.bad_requires():
            pending.append(Pending(TABLE_REASONS[3], f"{reg.what} の {bad}"))
    try:
        base = dt.date.fromisoformat(asof) if asof else None
    except ValueError:
        base = None
    if base is None:
        pending.append(Pending(TABLE_REASONS[4], f"基準日 {asof!r}"))
    else:
        for x in routes.items:
            d = _iso(x.declared_on, f"経路 {x.route_id} の宣言された日")
            if d and d > base:
                pending.append(Pending(TABLE_REASONS[5],
                                       f"経路 {x.route_id}({x.declared_on})"))
    for bad in traces.not_integer():
        pending.append(Pending(TABLE_REASONS[6], bad))

    if pending:
        return Table(routes, checks, traces, perms, places, asof, (),
                     Report(False, tuple(pending)))
    assert base is not None
    rows = tuple(judge(routes.of(route_id), checks.of_route(route_id),
                       traces.of_route(route_id), perms, places, base)
                 for route_id in routes.ids)
    return Table(routes, checks, traces, perms, places, asof, rows, Report(True, ()))


# ------------------------------------------------------------ verify(5 つ)

def moved(first: Table, after: Table) -> list[str]:
    a = {x.route_id: x.value for x in first.rows}
    b = {x.route_id: x.value for x in after.rows}
    return sorted(k for k in a if a[k] != b.get(k))


def trace_probe_plan(first: Table) -> str | None:
    """跡の件数を 0 → 1 にする経路((C) の 1 件目)。"""
    for x in sorted(first.rows, key=lambda r: r.route_id):
        if x.value == VALUES[2]:
            return x.route_id
    return None


def trace_probe(routes: Routes, checks: Checks, traces: Traces, perms: Registry,
                places: Registry, asof: str, route_id: str) -> Table:
    """**写しはメモリの中だけ。** 跡の台帳の CSV には 1 文字も書かない。"""
    rows: list[list[str]] = []
    for r in traces.rows:
        r = list(r)
        if r[0] == route_id and r[1] not in (NO_MARK, "") and r[2].isdigit():
            r[2] = str(int(r[2]) + 1)
        rows.append(r)
    return swap_ready(routes, checks, Traces(rows, traces.route_ids), perms,
                      places, asof)


def placement_probe_plan(first: Table) -> str | None:
    """検査の所属を 内蔵 → 独立 にする経路((B) の 1 件目で、所属が内蔵のもの)。"""
    for x in sorted(first.rows, key=lambda r: r.route_id):
        if x.value == VALUES[1] and x.placement == PLACEMENTS[1]:
            return x.route_id
    return None


def placement_probe(routes: Routes, checks: Checks, traces: Traces, perms: Registry,
                    places: Registry, asof: str, route_id: str) -> Table:
    """**写しはメモリの中だけ。** 検査の台帳の CSV には 1 文字も書かない。"""
    rows: list[list[str]] = []
    for r in checks.rows:
        r = list(r)
        if r[1] == route_id and r[2] == PLACEMENTS[1]:
            r[2], r[3] = PLACEMENTS[0], "別の束(verify が置いた仮の名前)"
        rows.append(r)
    return swap_ready(routes, Checks(rows, checks.route_ids), traces, perms,
                      places, asof)


def verify(routes: Routes, checks: Checks, traces: Traces, perms: Registry,
           places: Registry, asof: str) -> dict[str, object]:
    """5 つ見る(二度走り / 行順 3 通り / 件数の検算 / 跡を 1 足す / 独立にする)。"""
    first = swap_ready(routes, checks, traces, perms, places, asof)
    if not first.report.ok:
        return {"ok": False, "止まった": [p.as_dict() for p in first.report.pending]}
    again = swap_ready(routes, checks, traces, perms, places, asof)
    same_twice = again.sha256() == first.sha256()
    swapped: list[bool] = []
    for how in SWAPS:
        t = swap_ready(routes.swapped(how), checks.swapped(how), traces.swapped(how),
                       perms.swapped(how), places.swapped(how), asof)
        swapped.append(t.sha256() == first.sha256())
    total = sum(first.five().values()) + sum(first.extras().values())
    sums_ok = (total == first.denominator()
               and sum(int(r["経路の件数"]) for r in first.by_kind()) == total
               and sum(int(r["経路の件数"]) for r in first.by_bundle()) == total)

    probe1: dict[str, object] = {"やったこと": "跡の件数が 0 の (C) の経路が無い",
                                 "ok": True}
    rid = trace_probe_plan(first)
    if rid:
        after = trace_probe(routes, checks, traces, perms, places, asof, rid)
        got = {x.route_id: x.value for x in after.rows}[rid]
        probe1 = {"やったこと": f"経路 {rid} の跡の件数に 1 足した",
                  "移った経路": moved(first, after), "移った先": got,
                  "ok": moved(first, after) == [rid] and got == VALUES[0]}

    probe2: dict[str, object] = {"やったこと": "所属が内蔵の (B) の経路が無い", "ok": True}
    rid2 = placement_probe_plan(first)
    if rid2:
        after = placement_probe(routes, checks, traces, perms, places, asof, rid2)
        got = {x.route_id: x.value for x in after.rows}[rid2]
        probe2 = {"やったこと": f"経路 {rid2} の検査の所属を 内蔵 → 独立 にした",
                  "移った経路": moved(first, after), "移った先": got,
                  "ok": (moved(first, after) == [rid2]
                         and got in (VALUES[0], VALUES[2], BETSUWAKU[5]))}

    return {"ok": bool(same_twice and all(swapped) and sums_ok
                       and probe1["ok"] and probe2["ok"]),
            "二度走りの判定部分が同一": same_twice,
            "行順を入れ替えても同一": dict(zip(SWAPS, swapped)),
            "件数の合計": first.crosscheck(), "合計が合う": sums_ok,
            "跡の件数に 1 足す": probe1, "検査の所属を独立にする": probe2,
            "判定部分の sha256": first.sha256(),
            "入力を書き換えない": MOTANAI["入力を書き換えない"]}


# ------------------------------------------------------------ ひな型

T_ROUTE = "合成の経路のメモ(架空)L1"
T_CHECK = "合成の検査のメモ(架空)L1"
T_TRACE = "合成の跡のメモ(架空)L1"
T_PERM = "合成の許す宣言の登録のメモ(架空)L1"
T_PLACE = "合成の検査の所属の登録のメモ(架空)L1"

TEMPLATE_ROUTES = [list(ROUTE_COLUMNS),
                   ["R01", KINDS[0], "借り物の束", PERMISSIONS[0], NO_MARK, NO_MARK,
                    "2026-01-05", T_ROUTE],
                   ["R02", KINDS[2], "借り物の束", PERMISSIONS[1], "照合専用", "data",
                    "2026-01-05", T_ROUTE]]
TEMPLATE_CHECKS = [list(CHECK_COLUMNS),
                   ["C01", "R01", PLACEMENTS[1], NO_MARK, T_CHECK],
                   ["C02", "R02", PLACEMENTS[0], "照合用の束", T_CHECK]]
TEMPLATE_TRACES = [list(TRACE_COLUMNS),
                   ["R01", NO_MARK, NO_MARK, NO_MARK, "欄そのものが無い", T_TRACE],
                   ["R02", "版の欄", "0", "11 行", "まだ一度も通していない", T_TRACE]]
TEMPLATE_PERMS = [list(PERM_COLUMNS),
                  [PERMISSIONS[0], "入れ替えてよいと書かれている", PERM_REQUIRES[1],
                   T_PERM],
                  [PERMISSIONS[1], "範囲を限って入れ替えてよいと書かれている",
                   PERM_REQUIRES[2], T_PERM],
                  [PERMISSIONS[2], "入れ替えないと書かれている", PERM_REQUIRES[0],
                   T_PERM],
                  [PERMISSIONS[3], "どちらの宣言も見つからない", PERM_REQUIRES[0],
                   T_PERM]]
TEMPLATE_PLACES = [list(PLACE_COLUMNS),
                   [PLACEMENTS[0], "入れ替える側と別の束に在る", PLACE_REQUIRES[1],
                    T_PLACE],
                   [PLACEMENTS[1], "入れ替える側と同じ束に在る", PLACE_REQUIRES[0],
                    T_PLACE],
                   [PLACEMENTS[2], "受け入れ検査が無い", PLACE_REQUIRES[0], T_PLACE]]


def write_csv(path: Path, rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    return path


def init(dest: str | Path) -> tuple[Path, ...]:
    d = Path(dest)
    return tuple([write_csv(d / "経路の台帳.csv", TEMPLATE_ROUTES),
                  write_csv(d / "受け入れ検査の台帳.csv", TEMPLATE_CHECKS),
                  write_csv(d / "跡の台帳.csv", TEMPLATE_TRACES),
                  write_csv(d / "許す宣言の登録表.csv", TEMPLATE_PERMS),
                  write_csv(d / "検査の所属の登録表.csv", TEMPLATE_PLACES)])


# ------------------------------------------------------------ CLI

def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def build_parser() -> argparse.ArgumentParser:
    """CLI は check / report / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = argparse.ArgumentParser(prog="swap_ready",
                                 description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in SUBCOMMANDS[:3]:
        p = sub.add_parser(name)
        for arg in ("routes", "checks", "traces", "permissions", "placements",
                    "asof"):
            p.add_argument(arg)
    sub.add_parser(SUBCOMMANDS[3]).add_argument("dest")
    return ap


def load_five(a) -> tuple[Routes, Checks, Traces, Registry, Registry]:
    routes = Routes.load(a.routes)
    ids = routes.ids
    return (routes, Checks.load(a.checks, ids), Traces.load(a.traces, ids),
            load_permissions(a.permissions), load_placements(a.placements))


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == SUBCOMMANDS[3]:
        print("書いた: " + " / ".join(str(p) for p in init(a.dest)))
        return 0
    try:
        five = load_five(a)
        if a.cmd == SUBCOMMANDS[2]:
            out = verify(*five, a.asof)
            _print(out)
            return 0 if out["ok"] else 3
        t = swap_ready(*five, a.asof)
    except ReadError as e:
        print(f"表として読めない: {e}", file=sys.stderr)
        return 2
    if not t.report.ok:
        _print({"ok": False, "stage": "止まった(4 値は返さない)",
                "基準日": a.asof, "分母(経路の件数)": 0,
                "pending": [p.as_dict() for p in t.report.pending]})
        return 3
    body: dict[str, object] = {"ok": True, **t.counts()}
    if a.cmd == SUBCOMMANDS[1]:
        body["経路ごとの一覧"] = t.listed()
        body["対象の種別ごと"] = t.by_kind()
        body["入れ替える側の束ごと"] = t.by_bundle()
        body["理由(出典ごと写す)"] = t.reasons()
        body["sha256"] = t.sha256()
        body["読んだ条件"] = t.read_condition()
    _print(body)
    five_counts = t.five()
    clean = (not sum(t.extras().values()) and not t.stopped()
             and not five_counts[VALUES[1]] and not five_counts[VALUES[2]]
             and not five_counts[VALUES[4]])
    return 0 if clean else 3


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
