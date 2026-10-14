"""span_split — 期間を宣言された境界日で切り、小期間ごとにどの行が有効かを当てる。

**値が切り替わる日が期間の途中に来るとき、期間を 1 つのまま 1 本の日付で引くと、片側の値が
黙って期間全体に当たる。** この部品は、切る日を境界表からだけ取り、期間を小期間に割って、
小期間ごとに行を 1 つ当てる。当たらなければ値を返さない。

持たせていないものが規律になっている。

  - **境界表に無い日で切らない**(規定の自然文や行の表の有効開始日から境界を推測して足す
    経路が無い)
  - **当日の帰属が空欄の境界行は切らずに止まる**(境界日当日を新側に寄せる既定を持たない)
  - **境界日が決まっていない行(施行日が政令待ち)は、知識として読み込むが切るのには使わず、
    理由コードで止まる**(未定を今日の日付や公表日で埋めない)
  - **公表時点が期間より後の境界は、宣言された扱いで切るか切らないかを分け、どちらに寄せたかを
    必ず欄に残す**(黙ってどちらかに寄せない)
  - **金額を触らない**(按分・日割り・丸めの引数が無い。返すのは小期間の開始日・終了日・日数と
    当たった行まで)
  - **小期間の日数の合計が元の期間の日数と一致しない結果を返さない**(切り落ちと重複を自分で
    検算して、合わなければ止まる)
  - **同じ日に 2 行当たったら宣言された段階の順と行の順位で決め、どちらも空なら止まる**
    (並び順で静かに勝たせない)
  - **切れた期間の率を単独で返さない**(小期間の件数・境界で切れた期間の件数・止まった件数と
    分母の内訳を併記)
  - **入力表を書き換えず、境界行も期間行も生成しない**
  - **出典の欄が空の境界行・行の表の行は使わずに止まる**
  - **float を使わない**(日数は date の差の整数、値は文字列のまま運ぶ)
  - **「当たる行が決まらない」と「止まった」を混ぜない**(4 値を潰す引数が無い)

入力は 3 つ。期間表(CSV)、境界表(CSV)、行の表(CSV)。

期間表の列は 4 つ。

    target      対象(空欄は「表として読めない」)
    start       開始日(ISO)
    end         終了日(ISO、終わりの日を含む閉じた期間)
    basis       基準日の種別。登録の 6 種別の外は止まる

境界表の列は 8 つ。

    boundary    境界日(ISO)。空欄か「未定」は、知識として読むが切るのには使わず止まる
    moved       動いたもの(空欄は「表として読めない」)
    onday       当日の帰属。新側 / 旧側。空欄は止まる
    step        段階の順(整数か空欄)
    known_from  公表時点(ISO か空欄)
    known_use   公表時点が期間より後だったときの扱い。切る / 切らない。
                公表時点が空の行には書かない。公表時点が在って空欄なら止まる
    source      その行の出典(ファイル名 + 行番号 or URL)。空欄は止まる
    swap        入れ替え方(verify が境界表の行順を入れ替えるときの宣言。全行で同じ値)

行の表の列は 6 つ(基準日と公表時点の列を足した回と同じ形)。

    value       値(文字列のまま運ぶ)
    valid_from  有効開始日(ISO)
    known_from  公表時点(ISO か空欄)。この部品は引く時点で絞らず、出典と並べて返すだけ
    target      対象。空欄はどの対象にも当たる
    priority    順位(整数か空欄)。0 が本則、10 が経過措置
    source      出典。空欄は止まる

判定したことは「宣言された境界日で期間が切れるか、小期間ごとに当たる行が 1 つに決まるか」まで
で、どの切り方が制度として正しいかも、金額がいくらになるかも、境界表が足りているかも判定しない。
標準ライブラリのみ(csv / json / datetime / hashlib / platform / argparse)。
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import platform
import sys
from dataclasses import dataclass
from pathlib import Path

# 3 枚の表の列(どれも全部必要)
KIKAN_COLUMNS = ("target", "start", "end", "basis")
KYOUKAI_COLUMNS = ("boundary", "moved", "onday", "step", "known_from", "known_use", "source",
                   "swap")
GYOU_COLUMNS = ("value", "valid_from", "known_from", "target", "priority", "source")

# 登録されている語彙。この外は「表として読めない」(終了コード 2)にする
ONDAYS = ("新側", "旧側")
KNOWN_USES = ("切る", "切らない")
SWAPS = ("逆順", "先頭と末尾を入れ替え", "1 つずつずらす")

# 基準日の種別。棚卸しで出た 6 種別。この外は理由コードで止まる
BASIS_KINDS = ("対象月初日", "賃金締切日", "労働日", "資格取得日", "請求日", "離職日")

# 境界日が未定であることの書き方(空欄も同じ扱い)
MITEI = "未定"

# 期間ごとの 4 値。潰す引数は無い
RESULTS = ("境界で切れた", "境界に当たらず 1 本のまま", "当たる行が決まらない", "止まった")

# 止まる理由コード(12 個)
STOP_REASONS = ("境界表が 0 行", "当日の帰属が空", "境界日が未定",
                "公表時点の扱いが宣言されていない", "出典の欄が空", "基準日の種別が未登録",
                "同じ日に同じ動いたものが 2 行", "段階の順と順位がどちらも空",
                "開始日 > 終了日", "日数の合計が元の期間と合わない",
                "2 回目の判定部分が不一致", "境界表の行順を入れ替えた表で出力が変わる")

# CLI の下位コマンド。この 4 つだけで、option は -h 以外に 1 つも無い
SUBCOMMANDS = ("split", "check", "verify", "init")

# 判定部分に入れない欄(sha256 の対象にもしない)
READ_KEYS = ("読んだ期間表の絶対パス", "読んだ境界表の絶対パス", "読んだ行の表の絶対パス",
             "読んだ時刻", "ホスト名")

ONE_DAY = datetime.timedelta(days=1)


class ReadError(Exception):
    """表として読めない(理由コードにせず終了コード 2 で返す = 表を書く側の話)。"""


def as_date(text: str, where: str) -> datetime.date:
    """ISO の日付としてだけ読む(和暦も区切りの揺れも寄せない = 読む側の部品の仕事)。"""
    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        raise ReadError(f"{where}: 日付として読めない({text})") from None


def as_int(text: str, where: str) -> int | None:
    """整数か空欄。float は使わない。"""
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        raise ReadError(f"{where}: 整数として読めない({text})") from None


@dataclass(frozen=True)
class Pending:
    reason: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"reason": self.reason, "detail": self.detail}


# ------------------------------------------------------------------ 期間表

@dataclass(frozen=True)
class Span:
    target: str
    start: datetime.date
    end: datetime.date
    basis: str
    number: int

    @property
    def days(self) -> int:
        """終わりの日を含む日数。開始日 > 終了日 の行は止まるので、ここは 1 以上になる。"""
        return (self.end - self.start).days + 1


@dataclass(frozen=True)
class Spans:
    items: tuple[Span, ...]
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Spans":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"期間表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Spans":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in KIKAN_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("期間表に " + " / ".join(lack) + " の列が無い")
        items: list[Span] = []
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in KIKAN_COLUMNS}
            if not cell["target"]:
                raise ReadError(f"期間表 行 {i}: 対象が空欄")
            if not cell["basis"]:
                raise ReadError(f"期間表 行 {i}: 基準日の種別が空欄({cell['target']})")
            items.append(Span(target=cell["target"],
                              start=as_date(cell["start"], f"期間表 行 {i} の開始日"),
                              end=as_date(cell["end"], f"期間表 行 {i} の終了日"),
                              basis=cell["basis"], number=i))
        if not items:
            raise ReadError("期間表に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), path=path)

    @property
    def ordered(self) -> tuple[Span, ...]:
        """対象・開始日・終了日の順に並べ替えて返す(表の行順には依らせない)。"""
        return tuple(sorted(self.items, key=lambda s: (s.target, s.start, s.end, s.number)))


# ------------------------------------------------------------------ 境界表

@dataclass(frozen=True)
class Boundary:
    day: datetime.date | None        # None = 未定(施行日が政令待ち)
    moved: str
    onday: str
    step: int | None
    known_from: datetime.date | None
    known_use: str
    source: str
    number: int

    @property
    def cut_day(self) -> datetime.date | None:
        """切れ目の日。当日の帰属が 新側 なら境界日そのもの、旧側 なら翌日。"""
        if self.day is None or self.onday not in ONDAYS:
            return None
        return self.day if self.onday == ONDAYS[0] else self.day + ONE_DAY


@dataclass(frozen=True)
class Boundaries:
    items: tuple[Boundary, ...]
    swap: str
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Boundaries":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"境界表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Boundaries":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in KYOUKAI_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("境界表に " + " / ".join(lack) + " の列が無い")
        items: list[Boundary] = []
        pending: list[Pending] = []
        swaps: set[str] = set()
        seen: dict[tuple[str, str], int] = {}
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in KYOUKAI_COLUMNS}
            where = f"境界表 行 {i}({cell['moved'] or '動いたものが空欄'})"
            if not cell["moved"]:
                raise ReadError(f"境界表 行 {i}: 動いたものが空欄")
            if cell["onday"] and cell["onday"] not in ONDAYS:
                raise ReadError(f"境界表 行 {i}: 当日の帰属は "
                                f"{' / '.join(ONDAYS)}({cell['onday']})")
            if cell["known_use"] and cell["known_use"] not in KNOWN_USES:
                raise ReadError(f"境界表 行 {i}: 公表時点の扱いは "
                                f"{' / '.join(KNOWN_USES)}({cell['known_use']})")
            if not cell["known_from"] and cell["known_use"]:
                raise ReadError(f"境界表 行 {i}: 公表時点が空の行に扱いは書かない"
                                f"({cell['known_use']})")
            if cell["swap"]:
                if cell["swap"] not in SWAPS:
                    raise ReadError(f"境界表 行 {i}: 入れ替え方 {cell['swap']} は登録の外"
                                    f"({' / '.join(SWAPS)})")
                swaps.add(cell["swap"])
            day = (None if cell["boundary"] in ("", MITEI)
                   else as_date(cell["boundary"], f"境界表 行 {i} の境界日"))
            known = (as_date(cell["known_from"], f"境界表 行 {i} の公表時点")
                     if cell["known_from"] else None)
            if day is None:
                pending.append(Pending(STOP_REASONS[2], where + ": 境界日が "
                                       + (cell["boundary"] or "空欄")))
            if not cell["onday"]:
                pending.append(Pending(STOP_REASONS[1], where))
            if known is not None and not cell["known_use"]:
                pending.append(Pending(STOP_REASONS[3], where + f": 公表時点 {known}"))
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[4], where))
            key = (cell["boundary"], cell["moved"])
            if day is not None:
                if key in seen:
                    pending.append(Pending(STOP_REASONS[6],
                                           f"{cell['moved']} {cell['boundary']}"
                                           f": 行 {seen[key]} と行 {i}"))
                else:
                    seen[key] = i
            items.append(Boundary(day=day, moved=cell["moved"], onday=cell["onday"],
                                  step=as_int(cell["step"], f"境界表 行 {i} の段階の順"),
                                  known_from=known, known_use=cell["known_use"],
                                  source=cell["source"], number=i))
        if not items:
            pending.append(Pending(STOP_REASONS[0], "境界の行が 1 行も無い"))
        if len(swaps) > 1:
            raise ReadError("入れ替え方の宣言が 2 通り以上ある: " + " / ".join(sorted(swaps)))
        return cls(items=tuple(items), swap=next(iter(swaps), ""),
                   pending=tuple(pending), path=path)

    @property
    def undecided(self) -> tuple[Boundary, ...]:
        return tuple(b for b in self.items if b.day is None)

    def swapped(self, how: str) -> "Boundaries":
        """宣言された入れ替え方で境界表の行順だけを入れ替える(乱数の既定は持たない)。"""
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
        return Boundaries(items=tuple(rows), swap=self.swap, pending=self.pending,
                          path=self.path)


# ------------------------------------------------------------------ 行の表

@dataclass(frozen=True)
class Row:
    value: str
    valid_from: datetime.date
    known_from: datetime.date | None
    target: str
    priority: int | None
    source: str
    number: int

    def covers(self, target: str) -> bool:
        """対象が空欄の行はどの対象にも当たる(次元を後から足しても既存の行を直さない形)。"""
        return not self.target or self.target == target


@dataclass(frozen=True)
class Rows:
    items: tuple[Row, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Rows":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"行の表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Rows":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in GYOU_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("行の表に " + " / ".join(lack) + " の列が無い")
        items: list[Row] = []
        pending: list[Pending] = []
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in GYOU_COLUMNS}
            if not cell["value"]:
                raise ReadError(f"行の表 行 {i}: 値が空欄")
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[4], f"行の表 行 {i}({cell['value']})"))
            items.append(Row(value=cell["value"],
                             valid_from=as_date(cell["valid_from"],
                                                f"行の表 行 {i} の有効開始日"),
                             known_from=(as_date(cell["known_from"],
                                                 f"行の表 行 {i} の公表時点")
                                         if cell["known_from"] else None),
                             target=cell["target"],
                             priority=as_int(cell["priority"], f"行の表 行 {i} の順位"),
                             source=cell["source"], number=i))
        if not items:
            raise ReadError("行の表に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)


# ------------------------------------------------------------------ 切って当てる

@dataclass(frozen=True)
class Piece:
    """小期間 1 つ。金額の欄は無い(按分も日割りもしない)。"""
    start: datetime.date
    end: datetime.date
    opened_by: tuple[str, ...]        # この小期間を開いた境界の「動いたもの」(名前の順)
    step: int | None                  # 開いた境界の段階の順
    hit: str = ""                     # 当たった / 決まらない(0 件)/ 決まらない(2 行以上)
    value: str = ""
    valid_from: datetime.date | None = None
    priority: int | None = None
    known_from: datetime.date | None = None
    source: str = ""
    row_number: int = 0

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


@dataclass(frozen=True)
class Cut:
    """期間 1 本の切り方と、小期間ごとに当てた行。"""
    span: Span
    result: str
    pieces: tuple[Piece, ...]
    known_later: tuple[tuple[str, str, str], ...] = ()   # (動いたもの, 公表時点, 寄せた先)

    @property
    def total_days(self) -> int:
        return sum(p.days for p in self.pieces)


@dataclass(frozen=True)
class Report:
    ok: bool
    pending: tuple[Pending, ...]
    spans: int
    boundaries: int
    rows: int


HITS = ("当たった", "決まらない(0 件)", "決まらない(2 行以上)")


@dataclass(frozen=True)
class Split:
    report: Report
    cuts: tuple[Cut, ...]
    spans: Spans
    boundaries: Boundaries
    rows: Rows
    read_at: str
    host: str

    # -------------------------------------------------- 4 値と分母
    def by_result(self, result: str) -> tuple[Cut, ...]:
        return tuple(c for c in self.cuts if c.result == result)

    @property
    def verdict(self) -> str:
        """全体の結果。1 本でも決まらなければ 当たる行が決まらない。"""
        self._guard()
        if self.by_result(RESULTS[2]):
            return RESULTS[2]
        return RESULTS[0] if self.by_result(RESULTS[0]) else RESULTS[1]

    def counts(self) -> dict[str, object]:
        """切れた率は単独では返さない。件数と分母の内訳を必ず併記する。"""
        four = {r: len(self.by_result(r)) for r in RESULTS}
        pieces = sum(len(c.pieces) for c in self.cuts)
        hit = sum(1 for c in self.cuts for p in c.pieces if p.hit == HITS[0])
        out: dict[str, object] = {
            "期間表の行数": self.report.spans,
            "境界表の行数": self.report.boundaries,
            "境界日が未定の行数": len(self.boundaries.undecided),
            "行の表の行数": self.report.rows,
            "4 値": four,
            "小期間の件数": pieces,
            "境界で切れた期間の件数": four[RESULTS[0]],
            "止まった期間の件数": four[RESULTS[3]],
            "行が当たった小期間の件数": hit,
            "公表時点が期間より後だった境界の件数": sum(len(c.known_later) for c in self.cuts),
            "切ったか": ("切った" if self.cuts else
                         "切っていない(表が揃う前に止まったので 4 値は全て 0)"),
        }
        out["分母に含めたもの"] = (
            f"期間表の行数 {self.report.spans} = 境界で切れた {four[RESULTS[0]]}"
            f" + 境界に当たらず 1 本のまま {four[RESULTS[1]]}"
            f" + 当たる行が決まらない {four[RESULTS[2]]} + 止まった {four[RESULTS[3]]}。"
            f"小期間の件数 {pieces} のうち行が当たったのは {hit} 件。"
            f"境界表の行数 {self.report.boundaries} のうち境界日が未定の行は"
            f" {len(self.boundaries.undecided)} 行")
        out["境界は宣言された日だけ"] = (
            "切ったのは境界表に書かれた日だけで、規定の自然文や行の表の有効開始日から境界を"
            "推測して足す経路は無い。当日の帰属も表から取る(新側に寄せる既定を持たない)")
        out["日数の検算"] = (
            "小期間の日数の合計が元の期間の日数と一致しない結果は返さない"
            f"(切った期間 {len(self.cuts)} 本すべてで突き合わせた)")
        out["金額は触らない"] = (
            "返すのは小期間の開始日・終了日・日数と当たった行まで。按分・日割り・丸めの引数が"
            "無いので、分母を 30 にするか 31 にするかはこの部品の外になる")
        return out

    def pieces_of(self, span: Span) -> list[dict[str, object]]:
        cut = next(c for c in self.cuts if c.span.number == span.number)
        out: list[dict[str, object]] = []
        for i, p in enumerate(cut.pieces, start=1):
            out.append({"段": i, "開始日": str(p.start), "終了日": str(p.end), "日数": p.days,
                        "開いた境界": list(p.opened_by), "段階の順": p.step,
                        "当たり方": p.hit, "値": p.value,
                        "有効開始日": str(p.valid_from) if p.valid_from else "",
                        "順位": p.priority,
                        "公表時点": str(p.known_from) if p.known_from else "",
                        "出典": p.source, "行番号": p.row_number})
        return out

    def table(self) -> list[dict[str, object]]:
        """期間ごとの結果。金額の欄は無い。"""
        return [{"対象": c.span.target, "開始日": str(c.span.start), "終了日": str(c.span.end),
                 "基準日の種別": c.span.basis, "元の期間の日数": c.span.days,
                 "結果": c.result, "小期間": len(c.pieces), "日数の合計": c.total_days,
                 "公表時点が期間より後だった境界": [{"動いたもの": m, "公表時点": k,
                                                     "寄せた先": u}
                                                    for m, k, u in c.known_later],
                 "内訳": self.pieces_of(c.span)}
                for c in self.cuts]

    # -------------------------------------------------- 判定部分
    def judgement_bytes(self) -> bytes:
        """判定部分 = 切った結果の表。時刻・絶対パス・ホスト名は入れない。"""
        self._guard()
        lines: list[str] = []
        for c in self.cuts:
            lines.append("\t".join([c.span.target, str(c.span.start), str(c.span.end),
                                    c.span.basis, c.result, str(len(c.pieces))]))
            for m, k, u in c.known_later:
                lines.append("\t".join(["", "公表時点", m, k, u]))
            for i, p in enumerate(c.pieces, start=1):
                lines.append("\t".join(["", str(i), str(p.start), str(p.end), str(p.days),
                                        p.hit, p.value,
                                        str(p.valid_from) if p.valid_from else "",
                                        "" if p.priority is None else str(p.priority),
                                        "" if p.step is None else str(p.step),
                                        "|".join(p.opened_by)]))
        return ("\n".join(lines) + "\n").encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.judgement_bytes()).hexdigest()

    def read_condition(self) -> dict[str, str]:
        return {READ_KEYS[0]: self.spans.path, READ_KEYS[1]: self.boundaries.path,
                READ_KEYS[2]: self.rows.path, READ_KEYS[3]: self.read_at,
                READ_KEYS[4]: self.host}

    def _guard(self) -> None:
        if not self.report.ok:
            raise RuntimeError("止まっているので切った結果は無い。"
                               "report.pending の理由コードを見る")


def attach(span: Span, start: datetime.date, rows: Rows,
           steps: dict[datetime.date, int]) -> tuple[str, Row | None, str]:
    """小期間の開始日に有効な行を 1 つ当てる。決まらなければ当たり方の名前だけ返す。

    同じ有効開始日の行が 2 行当たったときは、その日に宣言された段階の順と行の順位で決める。
    どちらも空なら理由コードで止まる(表の並び順で静かに勝たせない)。
    """
    cand = [r for r in rows.items if r.covers(span.target) and r.valid_from <= start]
    if not cand:
        return HITS[1], None, ""
    newest = max(r.valid_from for r in cand)
    step = steps.get(newest)
    tied = [r for r in cand if r.valid_from == newest]
    if len(tied) == 1:
        return HITS[0], tied[0], ""
    ranked = [r for r in tied if r.priority is not None]
    if len(ranked) == len(tied):
        top = max(r.priority for r in ranked if r.priority is not None)
        best = [r for r in ranked if r.priority == top]
        if len(best) == 1:
            return HITS[0], best[0], ""
    if not ranked and step is None:
        return HITS[2], None, STOP_REASONS[7]
    return HITS[2], None, ""


def split(spans: Spans, boundaries: Boundaries, rows: Rows) -> Split:
    """期間を境界日で切り、小期間ごとに行を当てる。表が揃う前に止まったら 1 本も切らない。"""
    now = datetime.datetime.now().isoformat(timespec="seconds")
    host = platform.node()
    pending = list(boundaries.pending) + list(rows.pending)

    def made(pend: tuple[Pending, ...], cuts: tuple[Cut, ...] = ()) -> Split:
        return Split(report=Report(not pend, pend, len(spans.items), len(boundaries.items),
                                   len(rows.items)),
                     cuts=cuts, spans=spans, boundaries=boundaries, rows=rows,
                     read_at=now, host=host)

    if pending:                      # 表が揃う前に止まる(1 本も切らない)
        return made(tuple(pending))

    # 宣言された段階の順を切れ目の日ごとに持つ(同じ日に 2 行当たったときの決め手)
    steps: dict[datetime.date, int] = {}
    for b in boundaries.items:
        day = b.cut_day
        if day is not None and b.step is not None:
            steps[day] = min(b.step, steps[day]) if day in steps else b.step

    cuts: list[Cut] = []
    for span in spans.ordered:
        if span.start > span.end:
            pending.append(Pending(STOP_REASONS[8], f"期間表 行 {span.number}"
                                                    f"({span.target}): "
                                                    f"{span.start} > {span.end}"))
            cuts.append(Cut(span=span, result=RESULTS[3], pieces=()))
            continue
        if span.basis not in BASIS_KINDS:
            pending.append(Pending(STOP_REASONS[5], f"期間表 行 {span.number}"
                                                    f"({span.target}): {span.basis}"))
            cuts.append(Cut(span=span, result=RESULTS[3], pieces=()))
            continue

        # 期間の内側に来る切れ目だけを集める(境界表の行順には依らせない)
        later: list[tuple[str, str, str]] = []
        inside: dict[datetime.date, list[Boundary]] = {}
        for b in boundaries.items:
            if b.known_from is not None and b.known_from > span.end:
                later.append((b.moved, str(b.known_from), b.known_use))
                if b.known_use == KNOWN_USES[1]:
                    continue
            day = b.cut_day
            if day is not None and span.start < day <= span.end:
                inside.setdefault(day, []).append(b)
        later.sort()

        edges = sorted(inside)
        bounds = [span.start] + edges + [span.end + ONE_DAY]
        pieces: list[Piece] = []
        stopped = ""
        for i in range(len(bounds) - 1):
            s, e = bounds[i], bounds[i + 1] - ONE_DAY
            opened = inside.get(s, [])
            step = steps.get(s)
            hit, row, stop = attach(span, s, rows, steps)
            if stop:
                stopped = stop
                pending.append(Pending(stop, f"期間表 行 {span.number}({span.target})"
                                             f" の小期間 {s}〜{e}"))
            pieces.append(Piece(start=s, end=e,
                                opened_by=tuple(sorted(b.moved for b in opened)),
                                step=step, hit=hit,
                                value=row.value if row else "",
                                valid_from=row.valid_from if row else None,
                                priority=row.priority if row else None,
                                known_from=row.known_from if row else None,
                                source=row.source if row else "",
                                row_number=row.number if row else 0))
        total = sum(p.days for p in pieces)
        if total != span.days:
            pending.append(Pending(STOP_REASONS[9], f"期間表 行 {span.number}"
                                                    f"({span.target}): 小期間の合計"
                                                    f" {total} 日 / 元の期間 {span.days} 日"))
            cuts.append(Cut(span=span, result=RESULTS[3], pieces=tuple(pieces),
                            known_later=tuple(later)))
            continue
        if stopped:
            result = RESULTS[3]
        elif any(p.hit != HITS[0] for p in pieces):
            result = RESULTS[2]
        else:
            result = RESULTS[0] if len(pieces) > 1 else RESULTS[1]
        cuts.append(Cut(span=span, result=result, pieces=tuple(pieces),
                        known_later=tuple(later)))
    return made(tuple(pending), tuple(cuts))


def verify(spans: Spans, boundaries: Boundaries, rows: Rows) -> dict[str, object]:
    """2 回切って判定部分の sha256 を比べ、境界表の行順を入れ替えても同じかを見て、日数を検算する。"""
    first = split(spans, boundaries, rows)
    if not first.report.ok:
        return {"ok": False, "stage": "止まった(切った結果は返さない)", **first.counts(),
                "pending": [p.as_dict() for p in first.report.pending]}
    if not boundaries.swap:
        raise ReadError("境界表に入れ替え方(swap)が無いので verify は走らせない")
    second = split(spans, boundaries, rows)
    swapped = boundaries.swapped(boundaries.swap)
    third = split(spans, swapped, rows)
    pending: list[Pending] = []
    if first.sha256() != second.sha256():
        pending.append(Pending(STOP_REASONS[10], f"2 回目 {second.sha256()[:12]}"))
    if not (third.report.ok and first.sha256() == third.sha256()):
        pending.append(Pending(STOP_REASONS[11],
                               f"入れ替え方 {boundaries.swap} の表で {third.sha256()[:12]}"
                               if third.report.ok else
                               f"入れ替え方 {boundaries.swap} の表では止まった"))
    for c in first.cuts:
        if c.total_days != c.span.days:
            pending.append(Pending(STOP_REASONS[9], f"{c.span.target} {c.span.start}: "
                                                    f"{c.total_days} 日 / {c.span.days} 日"))
    out: dict[str, object] = {
        "ok": not pending, "切った結果": first.verdict, "切った回数": 2,
        "入れ替え方": boundaries.swap, "sha256": first.sha256(),
        "2 回目の sha256": second.sha256(),
        "入れ替えた表の sha256": third.sha256() if third.report.ok else "",
        "日数の検算": [{"対象": c.span.target, "開始日": str(c.span.start),
                        "元の期間の日数": c.span.days, "小期間の日数の合計": c.total_days,
                        "小期間": len(c.pieces)} for c in first.cuts],
    }
    if pending:
        out["観測"] = ("同じ表から違うバイト列が出た(平均も多数決もしない。"
                       "どちらが正しいかも決めない)")
        out["pending"] = [p.as_dict() for p in pending]
    return out


# ------------------------------------------------------------------ ひな型

TEMPLATE_SPANS = [
    list(KIKAN_COLUMNS),
    ["合成の区分A", "2024-11-01", "2025-07-31", "対象月初日"],
    ["合成の区分A", "2025-05-01", "2025-09-30", "対象月初日"],
]
TEMPLATE_BOUNDARIES = [
    list(KYOUKAI_COLUMNS),
    ["2025-04-01", "合成の率(架空)", "新側", "1", "2024-12-20", "切る",
     "合成の境界メモ(架空)L1", "逆順"],
    ["2028-10-01", "合成の要件(架空)", "新側", "2", "2026-06-01", "切らない",
     "合成の境界メモ(架空)L2", ""],
]
TEMPLATE_ROWS = [
    list(GYOU_COLUMNS),
    ["12.00", "2023-04-01", "2023-02-10", "", "0", "合成の数表メモ(架空)L1"],
    ["9.60", "2025-04-01", "2024-12-20", "", "0", "合成の数表メモ(架空)L2"],
]


def write_csv(path: Path, rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    return path


def init(dest: str | Path) -> tuple[Path, Path, Path]:
    d = Path(dest)
    return (write_csv(d / "期間表.csv", TEMPLATE_SPANS),
            write_csv(d / "境界表.csv", TEMPLATE_BOUNDARIES),
            write_csv(d / "行の表.csv", TEMPLATE_ROWS))


# ------------------------------------------------------------------ CLI

def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def build_parser() -> argparse.ArgumentParser:
    """CLI は split / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = argparse.ArgumentParser(prog="span_split", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in SUBCOMMANDS[:3]:
        p = sub.add_parser(name)
        p.add_argument("spans")
        p.add_argument("boundaries")
        p.add_argument("rows")
    sub.add_parser(SUBCOMMANDS[3]).add_argument("dest")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == "init":
        print("書いた: " + " / ".join(str(p) for p in init(a.dest)))
        return 0
    try:
        spans, boundaries = Spans.load(a.spans), Boundaries.load(a.boundaries)
        rows = Rows.load(a.rows)
        if a.cmd == "verify":
            out = verify(spans, boundaries, rows)
            _print(out)
            return 0 if out["ok"] else 3
        m = split(spans, boundaries, rows)
    except ReadError as e:
        print(f"表として読めない: {e}", file=sys.stderr)
        return 2
    if not m.report.ok:
        _print({"ok": False, "stage": "止まった(切った結果は返さない)", **m.counts(),
                "pending": [p.as_dict() for p in m.report.pending]})
        return 3
    body: dict[str, object] = {"ok": True, "切った結果": m.verdict, **m.counts()}
    if a.cmd == "split":
        body["期間ごと"] = m.table()
        body["sha256"] = m.sha256()
        body["読んだ条件"] = m.read_condition()
    _print(body)
    return 0 if m.verdict != RESULTS[2] else 3


if __name__ == "__main__":
    raise SystemExit(main())
