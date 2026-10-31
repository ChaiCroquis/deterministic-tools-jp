"""edge_close — 足す行ごとに「前の行のどの端を閉じることになるか」を仕分ける。

**行を足す操作と、前の行の端を閉じる操作は別で、足す側の 1 行だけを見ていると閉じ忘れが
見えない。閉じ忘れた表は同じ日に 2 つの答えを返し、閉じすぎた表は答えの無い日を作る。**

この部品は、既存の行の表・足す行の表・閉じ方の宣言表の 3 枚から、足す行 1 件ごとに 6 値
(**閉じる端がある / 閉じ忘れると重なる / 閉じると隙間ができる / 閉じる端が無い /
有効期間は閉じたが知識期間の端が開いたまま / 同じ日に 2 つ開く**)か、別枠のどれか 1 つを
付ける。**閉じない。足さない。直さない。引かない。**

持たせていないものが規律になっている。

  - **閉じる操作をしない**(入力を書き換える経路が無い。閉じた後の表を返す関数も、閉じる
    日付を既存の行へ書き込む関数も無い。出すのは端の一覧だけ)
  - **どちらの期間が正しいかを決めない**(重なりを片方に寄せる引数が無い)
  - **重なりを誤り・違反・事故と呼ばない**(語彙を持たない)
  - **④ を新設と名乗らない**(宣言表の「④ に写してよい語」が埋まっているときだけ、その語を
    そのまま写す。空なら何も書かない)
  - **隙間を埋めない・前の行を延ばさない**(埋める関数が無い)
  - **順位で裁定しない**(勝ち負けを決める経路が無い。順位は鍵の一部として使うだけ)
  - **期間を切らない**(料率が変わる日で期間を分割する経路が無い)
  - **値を開かない・計算しない**(payload を読む列が無い)
  - **時計を読まない**(今日より前・後で判定しない。基準は入力の日付の欄だけ)
  - **出典の欄が空の行は使わずに止まる**(足す行の出典が空のときは、その行だけが別枠へ出る)
  - **同じ入力には同じバイト列**(判定部分に時刻・絶対パス・ホスト名を入れない。行順にも依らない)
  - **数は整数だけ**(件数も順位も整数で、float を使う経路が無い)

入力は 3 つ。

既存の行の表(CSV)の列は 11。**1 行が 1 行**。

    row_id        行 id(同じ id が 2 行あると止まる)
    rule_id       どの数表の rule か
    dims          各次元の値。`名前=値` を `;` でつないで書く(未指定は宣言された記号)
    priority      順位(宣言表の「許す順位の値」に無ければ止まる)
    valid_from    有効開始
    valid_to      有効終了(**開いている印が立っている行は空**)
    valid_open    終了が開いているかの印(`開` / 空)
    known_from    知識開始
    known_to      知識終了(同じく開いている行は空)
    known_open    知識終了が開いているかの印(`開` / 空)
    source        出典。空欄は止まる

終了の欄と印の組み合わせは 3 通りだけを受け取る。**印あり + 終了が空 = 開いている**、
**印なし + 終了が埋まっている = 閉じている**、**印なし + 終了も空 = 終了が書かれていない**
(閉じる端として指さない = ④ 側へ落ちる)。印あり + 終了が埋まっている は止まる。

足す行の表(CSV)の列は 12。**1 件が 1 行**。

    add_id         提案 id(同じ id が 2 行あると、その行が別枠へ出る)
    rule_id        どの数表の rule か(宣言表に無ければ別枠)
    dims           各次元の値(既存の行の表と同じ書き方)
    priority       順位
    valid_from     有効開始(**施行日未定の印**が立っている行は空でよい)
    pending_order  施行日未定の印(`政令待ち` / 空)
    valid_to       有効終了
    valid_open     終了が開いているかの印
    known_from     知識開始
    known_to       知識終了
    known_open     知識終了が開いているかの印
    source         出典

閉じ方の宣言表(CSV)の列は 10。**1 つの rule が 1 行**。

    rule_id           どの数表の rule か(同じ id が 2 行あると止まる)
    end_included      区間の閉じ方 = 終了を含むか(`含む` / `含まない`)
    edge_unit         端の単位(`日` / `月`)
    gap_allowed       隙間を許すか(`許す` / `許さない`)。**記録するだけで判定に使わない**
    reason_code       隙間を許す場合は必須の理由コード
    unspecified_mark  未指定次元の記号(この記号は**記号のまま鍵に入る**)
    close_known       知識期間も閉じる対象か(`閉じる` / `閉じない`)
    priorities        許す順位の値(`0;10;20`)
    new_label         ④ の行に写してよい語(空なら何も写さない)
    source            出典。空欄は止まる

鍵は **rule id + 次元の値 + 順位 + 知識期間の重なり** で組む。**鍵の作り方を道具が決めない**
(次元を文字列の似かたで寄せる経路が無い。未指定の記号を展開して当てる経路も無い)。

使い方:

    python edge_close.py init ひな型/
    python edge_close.py check 既存の行.csv 足す行.csv 閉じ方の宣言.csv
    python edge_close.py edges 既存の行.csv 足す行.csv 閉じ方の宣言.csv
    python edge_close.py verify 既存の行.csv 足す行.csv 閉じ方の宣言.csv

終了コードは、別枠・重なり・隙間・二重開始・知識期間の開き・止まった行が 0 件のときだけ 0、
在れば 3、表として読めなければ 2。**0 は「表が正しい」ではなく「閉じ忘れと閉じすぎが
見つからなかった」の意味で、良し悪しはこの部品の終了コードにも出力にも出ない。**
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

EXISTING_COLUMNS = ("row_id", "rule_id", "dims", "priority", "valid_from", "valid_to",
                    "valid_open", "known_from", "known_to", "known_open", "source")
ADD_COLUMNS = ("add_id", "rule_id", "dims", "priority", "valid_from", "pending_order",
               "valid_to", "valid_open", "known_from", "known_to", "known_open",
               "source")
DECLARE_COLUMNS = ("rule_id", "end_included", "edge_unit", "gap_allowed", "reason_code",
                   "unspecified_mark", "close_known", "priorities", "new_label",
                   "source")

FUKUMU, FUKUMANAI = "含む", "含まない"
END_KINDS = (FUKUMU, FUKUMANAI)

HI, TSUKI = "日", "月"
UNITS = (HI, TSUKI)

YURUSU, YURUSANAI = "許す", "許さない"
GAP_KINDS = (YURUSU, YURUSANAI)

TOJIRU, TOJINAI = "閉じる", "閉じない"
KNOWN_KINDS = (TOJIRU, TOJINAI)

HIRAKI = "開"
OPEN_MARKS = (HIRAKI, "")

SEIREI = "政令待ち"
PENDING_MARKS = (SEIREI, "")

# 足す行 1 件に付く 6 値 + 別枠。**この 7 つの外に値を作る経路が無い。**
KEKKA = (
    "閉じる端がある",
    "閉じ忘れると重なる",
    "閉じると隙間ができる",
    "閉じる端が無い",
    "有効期間は閉じたが知識期間の端が開いたまま",
    "同じ日に 2 つ開く",
    "別枠",
)
MUTSU = KEKKA[:6]
BEKKA = KEKKA[6]

# 別枠の理由(**足す行 1 件ごとに付く。表ぜんたいを止めない**)
BEKKA_REASONS = (
    "鍵が宣言表に無い",
    "出典が空",
    "終了が開始より前",
    "順位が登録外",
    "提案 id の重複",
    "日付の書式が宣言と違う",
    "施行日未定の印が立っているのに開始が入っている",
)

# ① に入った行の言い方の違い(**解釈で埋めず、形のまま分けて出す**)
TOJIKATA = (
    "開いている端を足す行の開始で閉じる",
    "すでに隣接しているので閉じる操作が要らない",
    "開いている端があるが、施行日が未定なので閉じる日付が決まらない",
)

SWAPS = ("逆順", "両端入れ替え", "1 つずらす")

STOP_REASONS = (
    # 3 枚の表の側。1 件も仕分けずに止まる(9)
    "出典の欄が空",
    "同じ行 id が既存の行の表に 2 行ある",
    "開いている印と終了の日付が同じ行に在る",
    "終了が開始より前",
    "同じ rule id が宣言表に 2 行ある",
    "隙間を許すと書いてあるのに理由コードが無い",
    "日付の書式が宣言と違う",
    "順位が登録外",
    "鍵が宣言表に無い",
    # verify が見つける(3)
    "件数の合計が合わない", "2 回目の判定部分が不一致", "行順を入れ替えた表で出力が変わる",
)
TABLE_REASONS = STOP_REASONS[:9]
VERIFY_REASONS = STOP_REASONS[9:]

SUBCOMMANDS = ("edges", "check", "verify", "init")
SCOPE_KEYS = ("読んだ既存の行の表の絶対パス", "読んだ足す行の表の絶対パス",
              "読んだ閉じ方の宣言表の絶対パス")

NG_ID = set(" \t,|;=")
MONTH = re.compile(r"\A\d{4}-(0[1-9]|1[0-2])\Z")
DAY = re.compile(r"\A\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\Z")
PAIR = re.compile(r"\A[^\s;=]+=[^\s;=]+\Z")


class ReadError(Exception):
    """表として読めない(終了コード 2)。足す行は 1 件も仕分けない。"""


@dataclass(frozen=True)
class Pending:
    reason: str
    detail: str = ""

    def as_dict(self) -> dict[str, str]:
        return {"理由コード": self.reason, "どこ": self.detail}


def bad_id(s: str) -> bool:
    return (not s) or any(ch in NG_ID for ch in s)


def whole(s: str, what: str, where: str) -> int:
    """0 以上の整数として読む。小数も符号も受け取らない(**float を使う経路が無い**)。"""
    if not (s.isascii() and s.isdigit()):
        raise ReadError(f"{where}: {what}が 0 以上の整数でない({s or '空欄'})")
    return int(s)


def dims_key(s: str, where: str) -> str:
    """次元の欄を `名前=値` の並びとして読み、名前の順にそろえる。

    **値を寄せない**(全角半角も、似た綴りも、未指定の記号も、書かれたままで鍵に入る)。
    """
    pairs = [p.strip() for p in s.split(";") if p.strip()]
    if not pairs:
        raise ReadError(f"{where}: 次元の欄が空")
    for p in pairs:
        if not PAIR.match(p):
            raise ReadError(f"{where}: 次元の欄が 名前=値 の形でない({p})")
    names = [p.split("=", 1)[0] for p in pairs]
    if len(set(names)) != len(names):
        raise ReadError(f"{where}: 同じ次元の名前が 2 回書かれている({s})")
    return ";".join(sorted(pairs))


def unit_ok(value: str, unit: str) -> bool:
    """日付が宣言された端の単位の書式どおりか。**書式を当てずに、宣言と突き合わせる。**"""
    if unit == TSUKI:
        return bool(MONTH.match(value))
    if not DAY.match(value):
        return False
    y, m, d = (int(x) for x in value.split("-"))
    try:
        date(y, m, d)
    except ValueError:
        return False
    return True


def next_unit(value: str, unit: str) -> str:
    """端の単位で 1 つ後ろ。**今日を読まない**(入力の日付だけから計算する)。"""
    if unit == TSUKI:
        y, m = (int(x) for x in value.split("-"))
        return f"{y + 1:04d}-01" if m == 12 else f"{y:04d}-{m + 1:02d}"
    return (date.fromisoformat(value) + timedelta(days=1)).isoformat()


def prev_unit(value: str, unit: str) -> str:
    """端の単位で 1 つ前。`含む` の宣言で閉じる日付を出すときに使う。"""
    if unit == TSUKI:
        y, m = (int(x) for x in value.split("-"))
        return f"{y - 1:04d}-12" if m == 1 else f"{y:04d}-{m - 1:02d}"
    return (date.fromisoformat(value) - timedelta(days=1)).isoformat()


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


# ------------------------------------------------------------ 閉じ方の宣言表


@dataclass(frozen=True)
class Rule:
    """1 つの rule の閉じ方。**閉じ方を道具が決めず、ここに書かれたものだけを使う。**"""
    rule_id: str
    end_included: str
    edge_unit: str
    gap_allowed: str
    reason_code: str
    unspecified_mark: str
    close_known: str
    priorities: tuple[int, ...]
    new_label: str
    source: str

    @property
    def inclusive(self) -> bool:
        return self.end_included == FUKUMU

    @property
    def closing_known(self) -> bool:
        return self.close_known == TOJIRU

    def limit(self, to: str, open_end: bool) -> str:
        """覆っていない最初の単位。開いていれば空文字(= 果てが無い)。"""
        if open_end or not to:
            return ""
        return next_unit(to, self.edge_unit) if self.inclusive else to

    def close_at(self, start: str) -> str:
        """足す行の開始で閉じるときに、既存の行の終了の欄へ入ることになる日付。"""
        return prev_unit(start, self.edge_unit) if self.inclusive else start


@dataclass(frozen=True)
class Declares:
    items: tuple[Rule, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Declares":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"閉じ方の宣言表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Declares":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in DECLARE_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("閉じ方の宣言表に " + " / ".join(lack) + " の列が無い")
        items: list[Rule] = []
        pending: list[Pending] = []
        seen: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in DECLARE_COLUMNS}
            where = f"閉じ方の宣言表 行 {i}"
            if bad_id(cell["rule_id"]):
                raise ReadError(f"{where}: rule id が空欄か、区切り文字を含む"
                                f"({cell['rule_id'] or '空欄'})")
            if cell["end_included"] not in END_KINDS:
                raise ReadError(f"{where}: 区間の閉じ方が登録の 2 つでない"
                                f"({cell['end_included'] or '空欄'})")
            if cell["edge_unit"] not in UNITS:
                raise ReadError(f"{where}: 端の単位が 日 / 月 でない"
                                f"({cell['edge_unit'] or '空欄'})")
            if cell["gap_allowed"] not in GAP_KINDS:
                raise ReadError(f"{where}: 隙間を許すかが登録の 2 つでない"
                                f"({cell['gap_allowed'] or '空欄'})")
            if cell["close_known"] not in KNOWN_KINDS:
                raise ReadError(f"{where}: 知識期間も閉じる対象かが登録の 2 つでない"
                                f"({cell['close_known'] or '空欄'})")
            if not cell["unspecified_mark"]:
                raise ReadError(f"{where}: 未指定次元の記号が空欄")
            prios = tuple(whole(x.strip(), "許す順位の値", where)
                          for x in cell["priorities"].split(";") if x.strip())
            if not prios:
                raise ReadError(f"{where}: 許す順位の値が空欄")
            if cell["rule_id"] in seen:
                pending.append(Pending(STOP_REASONS[4], f"{where}: {cell['rule_id']}"))
            seen.add(cell["rule_id"])
            if cell["gap_allowed"] == YURUSU and not cell["reason_code"]:
                pending.append(Pending(STOP_REASONS[5], f"{where}: {cell['rule_id']}"))
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0], f"{where}: {cell['rule_id']}"))
            items.append(Rule(rule_id=cell["rule_id"],
                              end_included=cell["end_included"],
                              edge_unit=cell["edge_unit"],
                              gap_allowed=cell["gap_allowed"],
                              reason_code=cell["reason_code"],
                              unspecified_mark=cell["unspecified_mark"],
                              close_known=cell["close_known"], priorities=prios,
                              new_label=cell["new_label"], source=cell["source"]))
        if not items:
            raise ReadError("閉じ方の宣言表に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    def of(self, rule_id: str) -> Rule | None:
        """**宣言に無い rule には何も当てない**(None を返す = 別枠へ)。"""
        return next((r for r in self.items if r.rule_id == rule_id), None)

    def swapped(self, how: str) -> "Declares":
        return Declares(items=tuple(swap_rows(list(self.items), how)),
                        pending=self.pending, path=self.path)


# ------------------------------------------------------------ 期間の 1 つ分


@dataclass(frozen=True)
class Span:
    """期間 1 つ。**開いている端は空文字で持つ**(果ての日付を道具が作らない)。"""
    start: str
    end: str
    open_end: bool

    def limit(self, rule: Rule) -> str:
        return rule.limit(self.end, self.open_end)

    def overlaps(self, other: "Span", rule: Rule) -> bool:
        """2 つの期間が重なるか。

        日付は `YYYY-MM` / `YYYY-MM-DD` のどちらも辞書順 = 暦順なので、比べるのは文字列の
        まま。覆っていない最初の単位(空文字 = 果てが無い)を境にした半開区間として見る。
        """
        a, b = self.limit(rule), other.limit(rule)
        return (not b or self.start < b) and (not a or other.start < a)


# ------------------------------------------------------------ 既存の行の表


@dataclass(frozen=True)
class Row:
    """既存の行 1 行。**閉じる操作をこの部品がしないので、書き換える method を持たない。**"""
    row_id: str
    rule_id: str
    dims: str
    priority: int
    valid: Span
    known: Span
    source: str
    number: int = 0

    @property
    def end_written(self) -> bool:
        """終了が書かれているか。

        開いている印も無く終了も空の行は False(= 閉じる端として指さない)。**空欄を
        「たぶん開いている」と読み替える経路を持たない**ため。
        """
        return self.valid.open_end or bool(self.valid.end)

    def key(self) -> tuple[str, str, int]:
        return (self.rule_id, self.dims, self.priority)

    def end_text(self) -> str:
        if self.valid.end:
            return self.valid.end
        return "(開いている)" if self.valid.open_end else "(書かれていない)"


def read_span(cell: dict[str, str], prefix: str, where: str, what: str) -> Span:
    mark = cell[f"{prefix}_open"]
    if mark not in OPEN_MARKS:
        raise ReadError(f"{where}: {what}の開いている印が `{HIRAKI}` でも空でもない({mark})")
    if not cell[f"{prefix}_from"]:
        raise ReadError(f"{where}: {what}の開始が空欄")
    return Span(start=cell[f"{prefix}_from"], end=cell[f"{prefix}_to"],
                open_end=mark == HIRAKI)


@dataclass(frozen=True)
class Rows:
    items: tuple[Row, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Rows":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"既存の行の表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Rows":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in EXISTING_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("既存の行の表に " + " / ".join(lack) + " の列が無い")
        items: list[Row] = []
        pending: list[Pending] = []
        seen: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in EXISTING_COLUMNS}
            where = f"既存の行の表 行 {i}"
            if bad_id(cell["row_id"]):
                raise ReadError(f"{where}: 行 id が空欄か、区切り文字を含む"
                                f"({cell['row_id'] or '空欄'})")
            if bad_id(cell["rule_id"]):
                raise ReadError(f"{where}: rule id が空欄か、区切り文字を含む"
                                f"({cell['rule_id'] or '空欄'})")
            if cell["row_id"] in seen:
                pending.append(Pending(STOP_REASONS[1], f"{where}: {cell['row_id']}"))
            seen.add(cell["row_id"])
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0], f"{where}: {cell['row_id']}"))
            items.append(Row(row_id=cell["row_id"], rule_id=cell["rule_id"],
                             dims=dims_key(cell["dims"], where),
                             priority=whole(cell["priority"], "順位", where),
                             valid=read_span(cell, "valid", where, "有効期間"),
                             known=read_span(cell, "known", where, "知識期間"),
                             source=cell["source"], number=i))
        if not items:
            raise ReadError("既存の行の表に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    @property
    def ordered(self) -> tuple[Row, ...]:
        """**鍵と日付の欄だけで並べる**(ファイルの行順に依らない)。"""
        return tuple(sorted(self.items, key=lambda r: (r.rule_id, r.dims, r.priority,
                                                       r.valid.start, r.row_id)))

    def of(self, row_id: str) -> Row | None:
        return next((r for r in self.items if r.row_id == row_id), None)

    def issues(self, declares: Declares) -> tuple[Pending, ...]:
        """宣言と突き合わせないと分からない形の崩れ。**1 件でも在れば仕分けない。**"""
        out: list[Pending] = []
        for r in self.items:
            where = f"既存の行の表 行 {r.number}({r.row_id})"
            rule = declares.of(r.rule_id)
            if rule is None:
                out.append(Pending(STOP_REASONS[8], f"{where}: {r.rule_id}"))
                continue
            if r.priority not in rule.priorities:
                out.append(Pending(STOP_REASONS[7], f"{where}: 順位 {r.priority}"))
            for span, what in ((r.valid, "有効期間"), (r.known, "知識期間")):
                if span.open_end and span.end:
                    out.append(Pending(STOP_REASONS[2], f"{where}: {what}"))
                for value in (span.start, span.end):
                    if value and not unit_ok(value, rule.edge_unit):
                        out.append(Pending(
                            STOP_REASONS[6],
                            f"{where}: {what} {value} は {rule.edge_unit}単位でない"))
                if span.end and span.end < span.start:
                    out.append(Pending(STOP_REASONS[3], f"{where}: {what}"))
        return tuple(out)

    def unopened(self, row_id: str) -> "Rows":
        """1 行の「終了が開いている」印を外した写し(**メモリの中だけ**。入力は触らない)。"""
        items = tuple(
            Row(row_id=r.row_id, rule_id=r.rule_id, dims=r.dims, priority=r.priority,
                valid=Span(r.valid.start, r.valid.end, False), known=r.known,
                source=r.source, number=r.number) if r.row_id == row_id else r
            for r in self.items)
        return Rows(items=items, pending=self.pending, path=self.path)

    def swapped(self, how: str) -> "Rows":
        return Rows(items=tuple(swap_rows(list(self.items), how)),
                    pending=self.pending, path=self.path)


# ------------------------------------------------------------ 足す行の表


@dataclass(frozen=True)
class Add:
    """足す行 1 件。**この部品は足さないので、表へ書き戻す method を持たない。**"""
    add_id: str
    rule_id: str
    dims: str
    priority: int
    valid: Span
    known: Span
    pending_order: str
    source: str
    number: int = 0

    @property
    def undated(self) -> bool:
        """施行日未定の印が立っていて、開始が空の行。"""
        return self.pending_order == SEIREI and not self.valid.start

    def key(self) -> tuple[str, str, int]:
        return (self.rule_id, self.dims, self.priority)


@dataclass(frozen=True)
class Adds:
    items: tuple[Add, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Adds":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"足す行の表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Adds":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in ADD_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("足す行の表に " + " / ".join(lack) + " の列が無い")
        items: list[Add] = []
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in ADD_COLUMNS}
            where = f"足す行の表 行 {i}"
            if bad_id(cell["add_id"]):
                raise ReadError(f"{where}: 提案 id が空欄か、区切り文字を含む"
                                f"({cell['add_id'] or '空欄'})")
            if bad_id(cell["rule_id"]):
                raise ReadError(f"{where}: rule id が空欄か、区切り文字を含む"
                                f"({cell['rule_id'] or '空欄'})")
            if cell["pending_order"] not in PENDING_MARKS:
                raise ReadError(f"{where}: 施行日未定の印が `{SEIREI}` でも空でもない"
                                f"({cell['pending_order']})")
            for prefix, what in (("valid", "有効期間"), ("known", "知識期間")):
                if cell[f"{prefix}_open"] not in OPEN_MARKS:
                    raise ReadError(f"{where}: {what}の開いている印が `{HIRAKI}` でも"
                                    f"空でもない({cell[f'{prefix}_open']})")
                if cell[f"{prefix}_open"] == HIRAKI and cell[f"{prefix}_to"]:
                    raise ReadError(f"{where}: {what}の開いている印と終了の日付が"
                                    f"同じ行に在る({cell[f'{prefix}_to']})")
            if not cell["known_from"]:
                raise ReadError(f"{where}: 知識期間の開始が空欄")
            if cell["pending_order"] != SEIREI and not cell["valid_from"]:
                raise ReadError(f"{where}: 有効開始が空欄(施行日未定の印も立っていない)")
            items.append(Add(
                add_id=cell["add_id"], rule_id=cell["rule_id"],
                dims=dims_key(cell["dims"], where),
                priority=whole(cell["priority"], "順位", where),
                valid=Span(cell["valid_from"], cell["valid_to"],
                           cell["valid_open"] == HIRAKI),
                known=Span(cell["known_from"], cell["known_to"],
                           cell["known_open"] == HIRAKI),
                pending_order=cell["pending_order"], source=cell["source"], number=i))
        if not items:
            raise ReadError("足す行の表に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=(), path=path)

    @property
    def ordered(self) -> tuple[Add, ...]:
        """**鍵と日付の欄だけで並べる**(ファイルの行順に依らない)。"""
        return tuple(sorted(self.items, key=lambda a: (a.rule_id, a.dims, a.priority,
                                                       a.valid.start, a.add_id)))

    def restarted(self, add_id: str, start: str) -> "Adds":
        """1 件の有効開始を差し替えた写し(**メモリの中だけ**。入力は触らない)。"""
        items = tuple(
            Add(add_id=a.add_id, rule_id=a.rule_id, dims=a.dims, priority=a.priority,
                valid=Span(start, a.valid.end, a.valid.open_end), known=a.known,
                pending_order=a.pending_order, source=a.source, number=a.number)
            if a.add_id == add_id else a
            for a in self.items)
        return Adds(items=items, pending=self.pending, path=self.path)

    def swapped(self, how: str) -> "Adds":
        return Adds(items=tuple(swap_rows(list(self.items), how)),
                    pending=self.pending, path=self.path)


# ------------------------------------------------------------ 仕分ける


@dataclass(frozen=True)
class Judged:
    """足す行 1 件の結果。**是非の欄も、順位の欄も、推奨の欄も持たない。**"""
    add: Add
    result: str
    row_id: str = ""        # 閉じることになる既存の行(在れば)
    at: str = ""            # 閉じる端の日付(施行日未定なら空)
    shape: str = ""         # ① の言い方 / ②③ の形
    reason: str = ""        # 別枠の理由
    label: str = ""         # ④ に写してよい語(宣言表に在るときだけ)

    @property
    def counted(self) -> bool:
        return self.result in MUTSU

    def line(self) -> str:
        return (f"{self.add.rule_id}/{self.add.dims}/{self.add.priority:04d}"
                f"/{self.add.valid.start}/{self.add.add_id}:{self.result}"
                f":{self.row_id}:{self.at}:{self.shape}:{self.reason}:{self.label}")

    def verdict(self) -> str:
        """その件に付いた判定だけ(日付は入れない)。**写しで動いた件を数える単位。**"""
        return f"{self.result}:{self.row_id}:{self.shape}:{self.reason}"

    def as_dict(self) -> dict[str, object]:
        return {"提案 id": self.add.add_id, "rule id": self.add.rule_id,
                "次元の値": self.add.dims, "順位": self.add.priority,
                "足す行の有効開始": self.add.valid.start or "(施行日未定)",
                "判定": self.result, "閉じることになる行 id": self.row_id,
                "閉じる端の日付": self.at, "形": self.shape,
                "別枠の理由": self.reason, "④ に写した語": self.label,
                "出典": self.add.source}


def aside_reason(add: Add, rule: Rule | None, duplicated: bool) -> str:
    """別枠に落ちる理由を 1 つだけ返す(**上から順。複数当たっても 1 件は 1 理由**)。"""
    if rule is None:
        return BEKKA_REASONS[0]
    if not add.source:
        return BEKKA_REASONS[1]
    if duplicated:
        return BEKKA_REASONS[4]
    if add.pending_order == SEIREI and add.valid.start:
        return BEKKA_REASONS[6]
    for span in (add.valid, add.known):
        for value in (span.start, span.end):
            if value and not unit_ok(value, rule.edge_unit):
                return BEKKA_REASONS[5]
    if add.priority not in rule.priorities:
        return BEKKA_REASONS[3]
    for span in (add.valid, add.known):
        if span.start and span.end and span.end < span.start:
            return BEKKA_REASONS[2]
    return ""


def candidate(add: Add, rows: Rows, rule: Rule) -> Row | None:
    """閉じる端になりうる既存の行を 1 行だけ選ぶ。

    同じ鍵(**rule + 次元 + 順位 + 知識期間の重なり**)の行のうち、**有効開始が足す行の開始
    以前で最も後ろの行**。施行日未定の行は開始が無いので、同じ鍵のうち最も後ろの行を指す。
    終了が書かれていない行(開いている印も終了も空)は端として指さない。
    """
    same = [r for r in rows.ordered
            if r.key() == add.key() and r.known.overlaps(add.known, rule)
            and r.end_written]
    if not same:
        return None
    if add.undated:
        return same[-1]
    before = [r for r in same if r.valid.start <= add.valid.start]
    return before[-1] if before else None


def judge(add: Add, rows: Rows, rule: Rule | None, duplicated: bool) -> Judged:
    """足す行 1 件に 6 値 + 別枠のどれか 1 つを付ける。**良し悪しは決めない。**

    上から順に見る。別枠の理由が在ればそこで終わり。同じ鍵の既存の行が無ければ ④。在る場合は、
    **開いているか / 終了の次の単位が足す行の開始の前か後か / 知識期間の端が開いたままか**
    だけで分ける。**どちらの期間が正しいかは決めない。閉じる操作もしない。**
    """
    reason = aside_reason(add, rule, duplicated)
    if reason or rule is None:
        return Judged(add, BEKKA, reason=reason or BEKKA_REASONS[0])
    found = candidate(add, rows, rule)
    if found is None:
        return Judged(add, KEKKA[3], label=rule.new_label)
    if found.valid.open_end:
        if add.undated:
            return Judged(add, KEKKA[0], row_id=found.row_id, shape=TOJIKATA[2])
        if add.valid.open_end and found.valid.start == add.valid.start:
            return Judged(add, KEKKA[5], row_id=found.row_id,
                          shape=f"どちらも開始 {add.valid.start} で終了が開いている")
        return Judged(add, KEKKA[0], row_id=found.row_id,
                      at=rule.close_at(add.valid.start), shape=TOJIKATA[0])
    if add.undated:
        return Judged(add, KEKKA[0], row_id=found.row_id, shape=TOJIKATA[2])
    limit = found.valid.limit(rule)
    if limit > add.valid.start:
        return Judged(add, KEKKA[1], row_id=found.row_id, at=found.valid.end,
                      shape=f"既存の終了 {found.valid.end} の次は {limit} で、"
                            f"足す行の開始 {add.valid.start} より後")
    if limit < add.valid.start:
        return Judged(add, KEKKA[2], row_id=found.row_id, at=found.valid.end,
                      shape=f"既存の終了 {found.valid.end} の次は {limit} で、"
                            f"足す行の開始 {add.valid.start} より前")
    if rule.closing_known and found.known.open_end:
        return Judged(add, KEKKA[4], row_id=found.row_id, at=found.valid.end,
                      shape=f"有効期間は {limit} で隣接しているが、知識終了の印が "
                            f"{HIRAKI} のまま")
    return Judged(add, KEKKA[0], row_id=found.row_id, at=found.valid.end,
                  shape=TOJIKATA[1])


@dataclass(frozen=True)
class Report:
    ok: bool
    pending: tuple[Pending, ...]
    rows: int
    adds: int
    declares: int


@dataclass(frozen=True)
class Tally:
    report: Report
    judged: tuple[Judged, ...]
    rows: Rows
    adds: Adds
    declares: Declares

    # ---------------- 分母

    def add_denominator(self) -> int:
        return self.report.adds

    @property
    def counted_denominator(self) -> int:
        """6 値が付いた件の数(別枠を外した数)。"""
        return sum(1 for j in self.judged if j.counted)

    def aside_denominator(self) -> int:
        return sum(1 for j in self.judged if not j.counted)

    # ---------------- 件数

    def seven(self) -> dict[str, int]:
        out = {k: 0 for k in KEKKA}
        for j in self.judged:
            out[j.result] += 1
        return out

    def aside_reasons(self) -> dict[str, int]:
        out = {k: 0 for k in BEKKA_REASONS}
        for j in self.judged:
            if not j.counted:
                out[j.reason] += 1
        return out

    def shapes(self) -> dict[str, int]:
        """① の言い方の内訳(**どれが良いとは書かない**)。"""
        out = {k: 0 for k in TOJIKATA}
        for j in self.judged:
            if j.result == KEKKA[0]:
                out[j.shape] += 1
        return out

    def _counts_of(self, judged: list[Judged]) -> dict[str, int]:
        out = {k: 0 for k in KEKKA}
        for j in judged:
            out[j.result] += 1
        return out

    def by_rule(self) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for rule_id in sorted({a.rule_id for a in self.adds.items}):
            mine = [j for j in self.judged if j.add.rule_id == rule_id]
            rule = self.declares.of(rule_id)
            nai = "(宣言表に無い)"
            out.append({"rule id": rule_id, "足す行の数": len(mine),
                        "区間の閉じ方": rule.end_included if rule else nai,
                        "端の単位": rule.edge_unit if rule else nai,
                        "知識期間も閉じる対象か": rule.close_known if rule else nai,
                        "隙間を許すか(記録するだけ)": rule.gap_allowed if rule else nai,
                        "6 値 + 別枠": self._counts_of(mine),
                        "出典": rule.source if rule else ""})
        return out

    def by_dims(self) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for dims in sorted({a.dims for a in self.adds.items}):
            mine = [j for j in self.judged if j.add.dims == dims]
            out.append({"次元の値": dims, "足す行の数": len(mine),
                        "6 値 + 別枠": self._counts_of(mine)})
        return out

    # ---------------- 一覧

    def listed(self) -> list[dict[str, object]]:
        return [j.as_dict() for j in self.judged]

    def _of(self, *results: str) -> list[dict[str, object]]:
        return [j.as_dict() for j in self.judged if j.result in results]

    def edges(self) -> list[dict[str, object]]:
        return self._of(KEKKA[0])

    def overlapping(self) -> list[dict[str, object]]:
        return self._of(KEKKA[1])

    def gaps(self) -> list[dict[str, object]]:
        return self._of(KEKKA[2])

    def no_edge(self) -> list[dict[str, object]]:
        return self._of(KEKKA[3])

    def known_left_open(self) -> list[dict[str, object]]:
        return self._of(KEKKA[4])

    def double_open(self) -> list[dict[str, object]]:
        return self._of(KEKKA[5])

    def asides(self) -> list[dict[str, object]]:
        return [j.as_dict() for j in self.judged if not j.counted]

    def untouched_rows(self) -> list[dict[str, object]]:
        """どの足す行からも端として指されなかった既存の行(**止めずに並べるだけ**)。"""
        pointed = {j.row_id for j in self.judged if j.row_id}
        return [{"行 id": r.row_id, "rule id": r.rule_id, "次元の値": r.dims,
                 "順位": r.priority, "有効開始": r.valid.start,
                 "有効終了": r.end_text(), "出典": r.source}
                for r in self.rows.ordered if r.row_id not in pointed]

    def stopped(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for p in self.report.pending:
            out[p.reason] = out.get(p.reason, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: STOP_REASONS.index(kv[0])))

    # ---------------- まとめ

    def counts(self) -> dict[str, object]:
        """件数を、分母の内訳つきで出す。**割合も点数も順位も返さない。**"""
        seven = self.seven()
        out: dict[str, object] = {
            "既存の行の表の行数": self.report.rows,
            "足す行の表の行数": self.report.adds,
            "閉じ方の宣言表の行数": self.report.declares,
            "分母(足す行の件数)": self.add_denominator(),
            "分母(6 値が付いた件の数)": self.counted_denominator,
            "分母(別枠の数)": self.aside_denominator(),
            "分母(足す行に出てくる rule の数)": len({a.rule_id for a in self.adds.items}),
            "6 値 + 別枠": seven,
            "別枠の理由ごと": self.aside_reasons(),
            "閉じる端がある件の言い方ごと": self.shapes(),
            "どの足す行からも指されなかった既存の行": len(self.untouched_rows()),
            "rule ごと": self.by_rule(),
            "理由別の止まった件数": self.stopped(),
            "読んだか": ("読んだ" if self.judged else
                         "読んでいない(仕分ける前に止まったので 6 値は全て 0)"),
        }
        out["分母に含めたもの"] = (
            f"足す行の件数 {self.add_denominator()} 件のうち、別枠が "
            f"{self.aside_denominator()} 件で、残る {self.counted_denominator} 件に "
            "6 値が付く。内訳は " + " + ".join(f"{k} {seven[k]}" for k in MUTSU))
        out["件数の合計の検算"] = (
            f"6 値 + 別枠の合計 {sum(seven.values())} / 足す行の件数 "
            f"{self.add_denominator()}(6 値 {sum(seven[k] for k in MUTSU)} = "
            f"{self.counted_denominator} も同じ、rule ごとの内訳の合計 "
            f"{sum(int(r['足す行の数']) for r in self.by_rule())} と 次元の値ごとの"
            f"内訳の合計 {sum(int(r['足す行の数']) for r in self.by_dims())} も同じ)")
        out["閉じる操作をしない"] = (
            "入力を書き換える経路が無い。閉じた後の表を返す関数も、閉じる日付を既存の行へ"
            "書き込む関数も無い。出すのは端の一覧だけで、閉じるのは表を持つ人の仕事")
        out["どちらの期間が正しいかを決めない"] = (
            "重なりを片方に寄せる引数が無い。既存の終了を動かすのか、足す行の開始を動かすの"
            "かは、この部品が決めない")
        out["重なりを誤りと呼ばない"] = (
            "出力に誤り・違反・事故・異常の語が無い。重なりは「既存の終了の次が足す行の開始"
            "より後」という形としか書かない")
        out["新設と名乗らない"] = (
            "④ の件に語を写すのは、宣言表の ④ に写してよい語 の欄が埋まっているときだけ。"
            "空なら何も書かない(この部品が「初」「新設」を言い出す経路が無い)")
        out["隙間を埋めない"] = (
            "前の行を延ばす経路も、間に行を作る経路も無い。隙間を許すかの欄は記録するだけで"
            "判定に使わない(全部裏返しても 6 値は動かない)")
        out["順位で裁定しない"] = (
            "順位は鍵の一部として同じ値どうしを突き合わせるだけ。勝ち負けを決める経路が無い")
        out["期間を切らない"] = (
            "料率が変わる日で期間を分割する経路が無い。切るのはこの部品の外")
        out["値を開かない"] = (
            "payload の列が無い。料率も金額も読まないので、値が合っているかは分からない")
        out["時計を読まない"] = (
            "現在時刻を読む呼び出しを持たない。今日より前・後で判定しない。基準は入力の"
            "日付の欄だけ")
        return out

    def judgement_bytes(self) -> bytes:
        """判定部分 = 足す行ごとの値と端。時刻・絶対パスは入れない。"""
        self._guard()
        head = "\t".join(["件", str(self.report.rows), str(self.report.adds),
                          str(self.report.declares)])
        lines = [head] + sorted(j.line() for j in self.judged)
        return ("\n".join(lines) + "\n").encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.judgement_bytes()).hexdigest()

    def verdicts(self) -> dict[str, str]:
        """提案 id ごとの判定だけ(日付は入れない)。**写しで動いた件を数える単位。**"""
        return {j.add.add_id: j.verdict() for j in self.judged}

    def read_condition(self) -> dict[str, str]:
        return {SCOPE_KEYS[0]: self.rows.path, SCOPE_KEYS[1]: self.adds.path,
                SCOPE_KEYS[2]: self.declares.path}

    def _guard(self) -> None:
        if not self.report.ok:
            raise RuntimeError("止まっているので仕分けた足す行は無い。"
                               "report.pending の理由コードを見る")


def edge_close(rows: Rows, adds: Adds, declares: Declares) -> Tally:
    """足す行 1 件ごとに 6 値 + 別枠を付ける。

    3 枚のどれかが 1 行でも壊れていたら 1 件も仕分けない(6 値は全て 0)。
    """
    pending = list(rows.pending) + list(adds.pending) + list(declares.pending)
    pending.extend(rows.issues(declares))
    report = Report(not pending, tuple(pending), len(rows.items), len(adds.items),
                    len(declares.items))
    if pending:                 # 1 件も仕分けずに止まる
        return Tally(report=report, judged=(), rows=rows, adds=adds, declares=declares)
    seen: dict[str, int] = {}
    for a in adds.items:
        seen[a.add_id] = seen.get(a.add_id, 0) + 1
    judged = tuple(judge(a, rows, declares.of(a.rule_id), seen[a.add_id] > 1)
                   for a in adds.ordered)
    return Tally(report=report, judged=judged, rows=rows, adds=adds, declares=declares)


# ------------------------------------------------------------ verify


def moved_elsewhere(first: Tally, after: Tally, *keep: str) -> list[str]:
    """判定が動いた提案 id のうち、動くはずだった件でないもの。

    見るのは判定(値・閉じることになる行 id・形・別枠の理由)だけで、**閉じる端の日付は
    見ない**。写しで日付の表示だけが変わっても「動いていない」と数える。
    """
    before, now = first.verdicts(), after.verdicts()
    return sorted(k for k in before if k not in keep and before[k] != now.get(k, ""))


def open_probe_plan(first: Tally) -> Judged | None:
    """① のうち、開いている端を足す行の開始で閉じることになる最初の 1 件。

    順は鍵と日付の欄だけで決まるので、**同じ 3 枚なら毎回同じ件が選ばれる**。
    """
    for j in first.judged:
        if j.result == KEKKA[0] and j.shape == TOJIKATA[0]:
            row = first.rows.of(j.row_id)
            if row is not None and row.valid.open_end:
                return j
    return None


def open_probe(rows: Rows, adds: Adds, declares: Declares,
               first: Tally) -> dict[str, object]:
    """既存の行の「終了が開いている」印を 1 件外すと、その足す行だけが ① から動くか。"""
    plan = open_probe_plan(first)
    if plan is None:
        return {"合うか": True, "外せる端が無い": "① に開いている端の件が無いので試さない"}
    after = edge_close(rows.unopened(plan.row_id), adds, declares)
    if not after.report.ok:
        return {"合うか": False, "観測": "印を外した写しが止まった",
                "pending": [p.as_dict() for p in after.report.pending]}
    moved = moved_elsewhere(first, after, plan.add.add_id)
    now = next(j for j in after.judged if j.add.add_id == plan.add.add_id)
    ok = (now.result in (KEKKA[2], KEKKA[3]) and not moved
          and after.seven()[KEKKA[0]] == first.seven()[KEKKA[0]] - 1)
    return {"合うか": ok, "外した行 id": plan.row_id, "見た提案 id": plan.add.add_id,
            "前の判定": plan.result, "後の判定": now.result, "ほかで動いた件": moved,
            "6 値 + 別枠(前)": first.seven(), "6 値 + 別枠(後)": after.seven()}


def shift_probe_plan(first: Tally) -> Judged | None:
    """② のうち最初の 1 件。"""
    return next((j for j in first.judged if j.result == KEKKA[1]), None)


def shift_probe(rows: Rows, adds: Adds, declares: Declares,
                first: Tally) -> dict[str, object]:
    """開始を既存の終了の次の単位にすると ② が ① になり、さらに 1 単位後ろで ③ になるか。"""
    plan = shift_probe_plan(first)
    if plan is None:
        return {"合うか": True, "重なる件が無い": "② が 0 件なので試さない"}
    rule = declares.of(plan.add.rule_id)
    row = rows.of(plan.row_id)
    if rule is None or row is None:
        return {"合うか": False, "観測": "② の件の既存の行か宣言が引けない"}
    limit = row.valid.limit(rule)
    beyond = next_unit(limit, rule.edge_unit)
    out: dict[str, object] = {"見た提案 id": plan.add.add_id, "前の判定": plan.result,
                              "既存の終了": row.valid.end, "終了の次の単位": limit,
                              "さらに 1 単位後ろ": beyond}
    got: list[str] = []
    for start, want in ((limit, KEKKA[0]), (beyond, KEKKA[2])):
        after = edge_close(rows, adds.restarted(plan.add.add_id, start), declares)
        if not after.report.ok:
            return {**out, "合うか": False, "観測": f"開始を {start} にした写しが止まった"}
        now = next(j for j in after.judged if j.add.add_id == plan.add.add_id)
        got.append(now.result)
        moved = moved_elsewhere(first, after, plan.add.add_id)
        out[f"開始を {start} にしたとき"] = {"判定": now.result, "期待": want,
                                            "ほかで動いた件": moved}
        if now.result != want or moved:
            out["合うか"] = False
            return out
    out["合うか"] = True
    out["動いた順"] = [plan.result] + got
    return out


def verify(rows: Rows, adds: Adds, declares: Declares) -> dict[str, object]:
    """2 回読んで sha256 を比べ、3 枚の行順を 3 通りに入れ替えても同じかを見て、件数を検算し、
    さらに「開いている印を 1 件外した写し」と「開始を 1 単位ずつ動かした写し」の差を出す。"""
    first = edge_close(rows, adds, declares)
    if not first.report.ok:
        return {"ok": False, "stage": "止まった(仕分けた足す行は返さない)",
                **first.counts(),
                "pending": [p.as_dict() for p in first.report.pending]}
    second = edge_close(rows, adds, declares)
    pending: list[Pending] = []
    if first.sha256() != second.sha256():
        pending.append(Pending(STOP_REASONS[10], f"2 回目 {second.sha256()[:12]}"))
    swapped: dict[str, str] = {}
    for how in SWAPS:
        third = edge_close(rows.swapped(how), adds.swapped(how), declares.swapped(how))
        swapped[how] = third.sha256() if third.report.ok else ""
        if not (third.report.ok and first.sha256() == third.sha256()):
            pending.append(Pending(STOP_REASONS[11],
                                   f"入れ替え方 {how} で {swapped[how] or '止まった'}"))
    seven = first.seven()
    if sum(seven.values()) != first.add_denominator():
        pending.append(Pending(STOP_REASONS[9],
                               f"6 値 + 別枠の合計 {sum(seven.values())} / 足す行の件数 "
                               f"{first.add_denominator()}"))
    inner = sum(seven[k] for k in MUTSU)
    if inner != first.counted_denominator:
        pending.append(Pending(STOP_REASONS[9],
                               f"6 値 {inner} / 6 値が付いた件 "
                               f"{first.counted_denominator}"))
    if sum(first.aside_reasons().values()) != seven[BEKKA]:
        pending.append(Pending(STOP_REASONS[9], "別枠の理由ごとの合計が別枠の数と違う"))
    if sum(first.shapes().values()) != seven[KEKKA[0]]:
        pending.append(Pending(STOP_REASONS[9], "① の言い方ごとの合計が ① の数と違う"))
    for name, group in (("rule ごと", first.by_rule()),
                        ("次元の値ごと", first.by_dims())):
        total = sum(int(r["足す行の数"]) for r in group)
        if total != first.add_denominator():
            pending.append(Pending(STOP_REASONS[9],
                                   f"{name}の内訳の合計 {total} / 足す行の件数 "
                                   f"{first.add_denominator()}"))
        for k in KEKKA:
            got = sum(int(r["6 値 + 別枠"][k]) for r in group)
            if got != seven[k]:
                pending.append(Pending(STOP_REASONS[9],
                                       f"{name}の {k} の合計 {got} / {seven[k]}"))
    out: dict[str, object] = {
        "ok": not pending, "読んだ回数": 2, "入れ替え方": list(SWAPS),
        "sha256": first.sha256(), "2 回目の sha256": second.sha256(),
        "入れ替えた 3 枚の sha256": swapped,
        "件数の検算": {"6 値 + 別枠": seven, "合計": sum(seven.values()), "6 値": inner,
                       "別枠の理由ごとの合計": sum(first.aside_reasons().values()),
                       "① の言い方ごとの合計": sum(first.shapes().values()),
                       "rule ごとの内訳の合計":
                           sum(int(r["足す行の数"]) for r in first.by_rule()),
                       "次元の値ごとの内訳の合計":
                           sum(int(r["足す行の数"]) for r in first.by_dims()),
                       "分母(足す行の件数)": first.add_denominator(),
                       "分母(6 値が付いた件の数)": first.counted_denominator,
                       "分母(別枠の数)": first.aside_denominator()},
        "開いている印を 1 件外した写し": open_probe(rows, adds, declares, first),
        "開始を 1 単位ずつ動かした写し": shift_probe(rows, adds, declares, first),
    }
    for key in ("開いている印を 1 件外した写し", "開始を 1 単位ずつ動かした写し"):
        if not out[key]["合うか"]:        # type: ignore[index]
            pending.append(Pending(STOP_REASONS[9], f"{key} の判定が合わない"))
            out["ok"] = False
    if pending:
        out["観測"] = ("同じ表から違うバイト列が出た、または件数が合わない(平均も多数決も"
                       "しない。どちらの期間が正しいかも当てない)")
        out["pending"] = [p.as_dict() for p in pending]
    return out


# ------------------------------------------------------------ ひな型

T_ROW = "合成の行の記録(架空)L1"
T_ADD = "合成の提案の記録(架空)L1"
T_DEC = "合成の宣言の記録(架空)L1"

TEMPLATE_ROWS = [
    list(EXISTING_COLUMNS),
    ["E01", "甲表", "地域=甲1", "0", "2025-04", "", HIRAKI, "2025-03", "", HIRAKI, T_ROW],
    ["E02", "甲表", "地域=甲2", "0", "2025-04", "2026-04", "", "2025-03", "2026-03", "",
     T_ROW],
]
TEMPLATE_ADDS = [
    list(ADD_COLUMNS),
    ["A01", "甲表", "地域=甲1", "0", "2026-04", "", "", HIRAKI, "2026-03", "", HIRAKI,
     T_ADD],
    ["A02", "甲表", "地域=甲2", "0", "2026-02", "", "", HIRAKI, "2026-01", "", HIRAKI,
     T_ADD],
]
TEMPLATE_DECLARES = [
    list(DECLARE_COLUMNS),
    ["甲表", FUKUMANAI, TSUKI, YURUSANAI, "", "*", TOJIRU, "0;10;20", "", T_DEC],
]


def write_csv(path: Path, rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    return path


def init(dest: str | Path) -> tuple[Path, Path, Path]:
    d = Path(dest)
    return (write_csv(d / "既存の行.csv", TEMPLATE_ROWS),
            write_csv(d / "足す行.csv", TEMPLATE_ADDS),
            write_csv(d / "閉じ方の宣言.csv", TEMPLATE_DECLARES))


# ------------------------------------------------------------ CLI

def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def build_parser() -> argparse.ArgumentParser:
    """CLI は edges / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = argparse.ArgumentParser(prog="edge_close",
                                 description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in SUBCOMMANDS[:3]:
        p = sub.add_parser(name)
        p.add_argument("rows")
        p.add_argument("adds")
        p.add_argument("declares")
    sub.add_parser(SUBCOMMANDS[3]).add_argument("dest")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == "init":
        print("書いた: " + " / ".join(str(p) for p in init(a.dest)))
        return 0
    try:
        rows, adds = Rows.load(a.rows), Adds.load(a.adds)
        declares = Declares.load(a.declares)
        if a.cmd == "verify":
            out = verify(rows, adds, declares)
            _print(out)
            return 0 if out["ok"] else 3
        t = edge_close(rows, adds, declares)
    except ReadError as e:
        print(f"表として読めない: {e}", file=sys.stderr)
        return 2
    if not t.report.ok:
        _print({"ok": False, "stage": "止まった(仕分けた足す行は返さない)", **t.counts(),
                "pending": [p.as_dict() for p in t.report.pending]})
        return 3
    body: dict[str, object] = {"ok": True, **t.counts()}
    if a.cmd == SUBCOMMANDS[0]:
        body["判定ごとの一覧"] = t.listed()
        body["閉じる端の一覧"] = t.edges()
        body["重なる一覧"] = t.overlapping()
        body["隙間の一覧"] = t.gaps()
        body["閉じる端が無い一覧"] = t.no_edge()
        body["知識期間の端が開いたままの一覧"] = t.known_left_open()
        body["同じ日に 2 つ開く一覧"] = t.double_open()
        body["別枠の一覧"] = t.asides()
        body["どの足す行からも指されなかった既存の行の一覧"] = t.untouched_rows()
        body["次元の値ごと"] = t.by_dims()
        body["sha256"] = t.sha256()
        body["読んだ条件"] = t.read_condition()
    _print(body)
    seven = t.seven()
    clean = (t.aside_denominator() == 0 and seven[KEKKA[1]] == 0
             and seven[KEKKA[2]] == 0 and seven[KEKKA[4]] == 0
             and seven[KEKKA[5]] == 0 and not t.stopped())
    return 0 if clean else 3


if __name__ == "__main__":
    raise SystemExit(main())
