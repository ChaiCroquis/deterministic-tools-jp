"""future_row — もう知っているがまだ効き始めていない行を、基準日の答えから分けて返す。引かない、分けるだけ。

**公布された改正は、効き始める前に表へ入る。だから同じ表の中に「もう知っているが、まだ
効き始めていない行」が並ぶ。基準日の答えに混ぜれば早すぎる値が返り、入れずに捨てれば「次に
いつ変わるか」を答えられない。さらに施行日が政令にゆだねられた改正は効き始める日の欄が空で、
空を基準日や年度初めや公布日で埋めると、まだ効き始めていない改正が効いてしまう。**

この部品は、行の表・状態の宣言・基準日の表の 3 枚から、(行 × 基準日)1 組ごとに 5 値
(**もう効き終わった / 基準日に効いている / これから効き始める / 効き始める日が未定 /
止まった**)を付ける。そのうえで rule ごとに「次にいつ変わるか」を、基準日より後でいちばん
早い効き始める日 1 件だけ、出典つきで返す。件数は分母(行数 × 基準日の数)と内訳つきで出す。

持たせていないものが規律になっている。

  - **効き始める日が空の行に日付を推定して入れない**(基準日・年度初め・公布日・次の月初へ
    丸める引数が 1 つも無い。空の行は予定に置き、日付を返さない)
  - **知った日を効き始める日として代用しない**(公布日で引く経路が無い)
  - **判定にシステム日付を使わない**(基準日は表から受け取る。システムの日付と時刻は
    「読んだ条件」の欄に書き出すだけで、判定部分には入れない)
  - **まだ効き始めていない行を基準日の答えに混ぜない**(答えの口と予定の口を物理的に分け、
    1 つの配列にまとめる経路が無い)
  - **段階施行を 1 行にまとめない**(効き始める日ごとに別の行として数える)
  - **前の行を閉じていない重なりは止まる**(同じ rule・同じ対象・同じ順位で効いている期間が
    重なったら、読まずに止まる)
  - **知った日が基準日より後の行は扱わずに止まる**(当時の知識を再現するのは asof_table の
    領域で、この部品は「もう知っている行」だけを分ける)
  - **「次にいつ変わるか」は 1 件だけ返す**(近い日を探して代用しない。効き始める日が空の行を
    混ぜない。無ければ「無い」と返す)
  - **値を返さない**(行の表に値の列が無い)
  - **順位で裁定しない・期間を切らない・帯に当てない・空欄の意味を決めない・日付の種別を
    決めない**(この部品が持つのは基準日に対する効き始めの前後 1 段だけ)
  - **件数は理由別に分母(行数 × 基準日の数)と内訳つきで出す**(率を単独で返さない)
  - **5 つを混ぜない**
  - **入力表を書き換えず、行も日付も生成しない**
  - **出典の欄が空の行は使わずに止まる**
  - **float を使わない**(件数は整数、日付は年月日の文字列のまま比べる)
  - **同じ入力には同じバイト列**(判定部分に時刻・絶対パス・ホスト名を入れない)

入力は 3 つ。行の表(CSV)、状態の宣言(CSV)、基準日の表(CSV)。

行の表の列は 9 つ。1 行が 1 条項適用単位。

    row_id      行 id(空欄は「表として読めない」。2 行あると止まる)
    rule_id     その行が属する rule id。宣言表に無い rule は「表として読めない」
    known_from  知った日(公表日)。年月日。空欄は「表として読めない」
    valid_from  効き始める日。年月日、または**宣言された空の記号**
    valid_to    効き終わる日。年月日、または**宣言された空の記号**(= まだ閉じていない)
    seg         対象セグメント。「名前=値」を縦棒で区切る。未指定に見える記号は書けない
    priority    順位。**空欄のまま持つ**(0 と読み替えない)。整数でなければ読めない表
    announcer   公表元。判定には使わず素通しする
    source      出典。空欄は止まる

状態の宣言の列は 6 つ。1 rule が 1 行。

    rule_id     rule id(空欄は「表として読めない」。2 行あると止まる)
    states      使う状態の名前と意味。「名前=意味」を縦棒で区切る。**名前は登録の 4 つと同一**
    blank_rule  効き始める日が空のときの扱い。登録の 1 種(予定に置き、日付は返さない)
    open_rule   効き終わる日が空のときの扱い。登録の 1 種(まだ閉じていないものとして扱う)
    blank_mark  空欄の記号。**この記号だけが「欄が空」になる**(似た記号は宣言外として止まる)
    source      出典。空欄は止まる

基準日の表の列は 4 つ。1 基準日が 1 行。

    asof_id     基準日 id(空欄も、同じ id が 2 行あるのも「表として読めない」)
    asof        基準日。年月日
    source      出典。空欄は止まる
    swap        入れ替え方。verify が 3 枚の行順を入れ替えるときの宣言。全行で同じ値

有効期間は半開区間で読む。効き始める日は含み、効き終わる日は含まない。

使い方:

    python future_row.py init ひな型/
    python future_row.py check 行の表.csv 状態の宣言.csv 基準日の表.csv
    python future_row.py split 行の表.csv 状態の宣言.csv 基準日の表.csv
    python future_row.py next  行の表.csv 状態の宣言.csv 基準日の表.csv
    python future_row.py verify 行の表.csv 状態の宣言.csv 基準日の表.csv

終了コードは、止まる理由が 1 件も無いときだけ 0(未定の行が何件あっても 0)、止まったときは 3、
表として読めなければ 2。
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

GYOU_COLUMNS = ("row_id", "rule_id", "known_from", "valid_from", "valid_to", "seg",
                "priority", "announcer", "source")
SENGEN_COLUMNS = ("rule_id", "states", "blank_rule", "open_rule", "blank_mark",
                  "source")
KIJUNBI_COLUMNS = ("asof_id", "asof", "source", "swap")

# 5 値。混ぜない。先の 4 つが(行 × 基準日)1 組に 1 つだけ付く
STATES = ("もう効き終わった", "基準日に効いている", "これから効き始める",
          "効き始める日が未定")
RESULTS = STATES + ("止まった",)

# 効き始める日が空のときの扱い。登録の 1 種だけ
BLANK_RULES = ("予定に置き、日付は返さない",)
# 効き終わる日が空のときの扱い。登録の 1 種だけ
OPEN_RULES = ("まだ閉じていないものとして扱う",)

SWAPS = ("逆順", "両端入れ替え", "1 つずらす")

SEG_SEP = "|"
SEG_EQ = "="
STATE_SEP = "|"
INTEGER = re.compile(r"\A(0|[1-9][0-9]*)\Z")
ISO_DAY = re.compile(r"\A[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")

# 「欄が空」に見える記号。宣言された記号と一致しない限り止まる(推測して読まない)
NITA_KIGOU = ("*", "-", "—", "ー", "未定", "なし", "不明", "TBD", "tbd", "null",
              "None", "？", "?")

# 止まる理由コード。11 個
STOP_REASONS = ("出典の欄が空", "行 id の重複", "知った日が基準日より後",
                "知った日より前に効き始める日がある",
                "効き終わる日が効き始める日より前か同じ", "状態の宣言に無い記号",
                "同じ rule に状態の宣言が 2 行", "効いている期間の重なり",
                "件数の合計が合わない", "2 回目の判定部分が不一致",
                "行順を入れ替えた表で出力が変わる")

SUBCOMMANDS = ("split", "next", "check", "verify", "init")

# 判定部分に入れない欄(sha256 の対象にもしない)
SCOPE_KEYS = ("読んだ行の表の絶対パス", "読んだ状態の宣言の絶対パス",
              "読んだ基準日の表の絶対パス", "読んだ時刻", "ホスト名")

NAI = "無い"
TOMEDA = "9999-12-31"   # 閉じていない期間の右端として比べるためだけの印(出力しない)


class ReadError(Exception):
    """表として読めない(理由コードにせず終了コード 2 で返す = 表を書く側の話)。"""


def parse_day(text: str, where: str) -> str:
    """年月日 1 つ。文字列のまま持つ(年月日の文字列は辞書順 = 時間順になる)。"""
    if not ISO_DAY.match(text):
        raise ReadError(f"{where}: 年月日は 1999-12-31 の形で書く({text or '空欄'})")
    try:
        datetime.date.fromisoformat(text)
    except ValueError as e:
        raise ReadError(f"{where}: 暦に無い日付({text})") from e
    return text


def parse_seg(text: str, where: str) -> tuple[tuple[str, str], ...]:
    """「名前=値」を縦棒で区切った対象の欄。順は入力に依らせない(並べ替えて持つ)。"""
    if not text.strip():
        raise ReadError(f"{where}: 対象の欄が空欄")
    out: list[tuple[str, str]] = []
    for part in text.split(SEG_SEP):
        part = part.strip()
        if part.count(SEG_EQ) != 1:
            raise ReadError(f"{where}: 対象は「名前=値」で書く: {part or '空'}")
        name, value = (x.strip() for x in part.split(SEG_EQ))
        if not name:
            raise ReadError(f"{where}: 対象の次元の名前が空欄")
        if not value:
            raise ReadError(f"{where}: 次元 {name} の値が空欄")
        if value in NITA_KIGOU:
            raise ReadError(f"{where}: 未指定に見える記号は書けない({name}={value})"
                            "。未指定を読むのは rank_clash の役")
        out.append((name, value))
    names = [n for n, _ in out]
    if len(set(names)) != len(names):
        raise ReadError(f"{where}: 同じ次元の名前が 2 つある")
    return tuple(sorted(out))


def parse_states(text: str, where: str) -> tuple[tuple[str, str], ...]:
    """「名前=意味」を縦棒で区切った状態の宣言。名前は登録の 4 つと同一でなければ読めない。"""
    out: list[tuple[str, str]] = []
    for part in text.split(STATE_SEP):
        part = part.strip()
        if not part:
            continue
        if part.count(SEG_EQ) != 1:
            raise ReadError(f"{where}: 状態は「名前=意味」で書く: {part}")
        name, meaning = (x.strip() for x in part.split(SEG_EQ))
        if not meaning:
            raise ReadError(f"{where}: 状態 {name or '(名前なし)'} の意味が空欄")
        out.append((name, meaning))
    names = [n for n, _ in out]
    if len(set(names)) != len(names):
        raise ReadError(f"{where}: 同じ状態の名前が 2 つある")
    if tuple(sorted(names)) != tuple(sorted(STATES)):
        raise ReadError(f"{where}: 状態の名前は登録の 4 つと同じに書く("
                        + " / ".join(STATES) + ")")
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


# ------------------------------------------------------------ 状態の宣言

@dataclass(frozen=True)
class Rule:
    rule_id: str
    states: tuple[tuple[str, str], ...]
    blank_rule: str
    open_rule: str
    blank_mark: str
    source: str
    number: int


@dataclass(frozen=True)
class Declared:
    items: tuple[Rule, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Declared":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"状態の宣言が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Declared":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in SENGEN_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("状態の宣言に " + " / ".join(lack) + " の列が無い")
        items: list[Rule] = []
        pending: list[Pending] = []
        seen: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in SENGEN_COLUMNS}
            where = f"状態の宣言 行 {i}"
            if not cell["rule_id"]:
                raise ReadError(f"{where}: rule id が空欄")
            if cell["blank_rule"] not in BLANK_RULES:
                raise ReadError(f"{where}: 効き始める日が空のときの扱いは "
                                + " / ".join(BLANK_RULES)
                                + f" の宣言だけ({cell['blank_rule'] or '空欄'})")
            if cell["open_rule"] not in OPEN_RULES:
                raise ReadError(f"{where}: 効き終わる日が空のときの扱いは "
                                + " / ".join(OPEN_RULES)
                                + f" の宣言だけ({cell['open_rule'] or '空欄'})")
            if not cell["blank_mark"]:
                raise ReadError(f"{where}: 空欄の記号が空欄({cell['rule_id']})")
            if cell["rule_id"] in seen:
                pending.append(Pending(STOP_REASONS[6], f"{where}: {cell['rule_id']}"))
            seen.add(cell["rule_id"])
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0], f"{where}({cell['rule_id']})"))
            items.append(Rule(rule_id=cell["rule_id"],
                              states=parse_states(cell["states"], f"{where} の状態"),
                              blank_rule=cell["blank_rule"],
                              open_rule=cell["open_rule"],
                              blank_mark=cell["blank_mark"], source=cell["source"],
                              number=i))
        if not items:
            raise ReadError("状態の宣言に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    def of(self, rule_id: str) -> Rule | None:
        return next((r for r in self.items if r.rule_id == rule_id), None)

    @property
    def ordered(self) -> tuple[Rule, ...]:
        return tuple(sorted(self.items, key=lambda r: r.rule_id))

    def swapped(self, how: str) -> "Declared":
        return Declared(items=tuple(swap_rows(list(self.items), how)),
                        pending=self.pending, path=self.path)


# ------------------------------------------------------------ 行の表

@dataclass(frozen=True)
class Row:
    row_id: str
    rule_id: str
    known_from: str
    valid_from: str        # 年月日、または "" (= 宣言された空の記号だった)
    valid_to: str          # 年月日、または "" (= まだ閉じていない)
    seg: tuple[tuple[str, str], ...]
    priority: str          # 空欄のまま持つ(0 と読み替えない)
    announcer: str
    source: str
    number: int

    @property
    def undated(self) -> bool:
        """効き始める日が宣言された空の記号だった行(日付を推定して入れない)。"""
        return self.valid_from == ""

    @property
    def key(self) -> tuple[object, ...]:
        """重なりを見る鍵。同じ rule・同じ対象・同じ順位。"""
        return (self.rule_id, self.seg, self.priority)


@dataclass(frozen=True)
class Sheet:
    items: tuple[Row, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path, declared: Declared | None = None) -> "Sheet":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"行の表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()),
                         declared)

    @classmethod
    def parse(cls, text: str, path: str = "",
              declared: Declared | None = None) -> "Sheet":
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
            rule = declared.of(cell["rule_id"]) if declared else None
            if declared is not None and rule is None:
                raise ReadError(f"{where}: rule {cell['rule_id']} が状態の宣言に無い"
                                "(行が勝手に新 rule を名乗れない)")
            mark = rule.blank_mark if rule else ""
            known = parse_day(cell["known_from"], f"{where} の知った日")
            days = {"valid_from": "", "valid_to": ""}
            for name, label in (("valid_from", "効き始める日"),
                                ("valid_to", "効き終わる日")):
                value = cell[name]
                if not value:
                    raise ReadError(f"{where}: {label} の欄が空"
                                    "(空であることは宣言された記号で書く)")
                if mark and value == mark:
                    continue
                if value in NITA_KIGOU:
                    pending.append(Pending(STOP_REASONS[5],
                                           f"{where}({cell['row_id']}): "
                                           f"{label} {value}"
                                           f"(宣言された記号は {mark or '不明'})"))
                    continue
                days[name] = parse_day(value, f"{where} の{label}")
            vf, vt = days["valid_from"], days["valid_to"]
            if cell["priority"] and not INTEGER.match(cell["priority"]):
                raise ReadError(f"{where}: 順位が整数でない({cell['priority']})")
            if cell["row_id"] in seen:
                pending.append(Pending(STOP_REASONS[1], f"{where}: {cell['row_id']}"))
            seen.add(cell["row_id"])
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0], f"{where}({cell['row_id']})"))
            if vf and vf < known:
                pending.append(Pending(STOP_REASONS[3],
                                       f"{where}({cell['row_id']}): "
                                       f"効き始める日 {vf} < 知った日 {known}"))
            if vf and vt and vt <= vf:
                pending.append(Pending(STOP_REASONS[4],
                                       f"{where}({cell['row_id']}): "
                                       f"効き終わる日 {vt} ≦ 効き始める日 {vf}"))
            items.append(Row(row_id=cell["row_id"], rule_id=cell["rule_id"],
                             known_from=known, valid_from=vf, valid_to=vt,
                             seg=parse_seg(cell["seg"], f"{where} の対象"),
                             priority=cell["priority"],
                             announcer=cell["announcer"], source=cell["source"],
                             number=i))
        if not items:
            raise ReadError("行の表に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    @property
    def ordered(self) -> tuple[Row, ...]:
        """行 id の順(表の行順には依らせない)。"""
        return tuple(sorted(self.items, key=lambda r: r.row_id))

    def of(self, rule_id: str) -> tuple[Row, ...]:
        return tuple(r for r in self.ordered if r.rule_id == rule_id)

    def swapped(self, how: str) -> "Sheet":
        return Sheet(items=tuple(swap_rows(list(self.items), how)),
                     pending=self.pending, path=self.path)


# ------------------------------------------------------------ 基準日の表

@dataclass(frozen=True)
class Asof:
    asof_id: str
    asof: str
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
            if cell["swap"]:
                if cell["swap"] not in SWAPS:
                    raise ReadError(f"{where}: 入れ替え方 {cell['swap']} は登録の外"
                                    f"({' / '.join(SWAPS)})")
                swaps.add(cell["swap"])
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0], f"{where}({cell['asof_id']})"))
            items.append(Asof(asof_id=cell["asof_id"],
                              asof=parse_day(cell["asof"], f"{where} の基準日"),
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


# ------------------------------------------------------------ 5 値を付ける

def state_of(row: Row, asof: str) -> str:
    """基準日に対する行の状態。日付は年月日の文字列のまま比べる(半開区間)。"""
    if row.undated:
        return STATES[3]
    if row.valid_from > asof:
        return STATES[2]
    if row.valid_to and row.valid_to <= asof:
        return STATES[0]
    return STATES[1]


@dataclass(frozen=True)
class Pair:
    """(行 × 基準日)1 組の読み。引かないので値は持たない。"""
    row_id: str
    rule_id: str
    asof_id: str
    state: str

    def as_dict(self) -> dict[str, str]:
        return {"行 id": self.row_id, "rule id": self.rule_id,
                "基準日 id": self.asof_id, "状態": self.state}


@dataclass(frozen=True)
class Change:
    """rule ごと・基準日ごとの「次にいつ変わるか」。1 件だけ。"""
    rule_id: str
    asof_id: str
    day: str
    row_id: str
    source: str

    def as_dict(self) -> dict[str, str]:
        return {"rule id": self.rule_id, "基準日 id": self.asof_id,
                "次に変わる日": self.day, "行 id": self.row_id, "出典": self.source}


@dataclass(frozen=True)
class Report:
    ok: bool
    pending: tuple[Pending, ...]
    rows: int
    rules: int
    asofs: int


def next_change(rows: tuple[Row, ...], asof: str) -> Row | None:
    """基準日より後でいちばん早い効き始める日の行を 1 本。無ければ None。"""
    ahead = [r for r in rows if not r.undated and r.valid_from > asof]
    if not ahead:
        return None
    return min(ahead, key=lambda r: (r.valid_from, r.row_id))


@dataclass(frozen=True)
class Table:
    report: Report
    pairs: tuple[Pair, ...]
    changes: tuple[Change, ...]
    sheet: Sheet
    declared: Declared
    asofs: Asofs
    read_at: str
    host: str

    # -------------------------------------------------- 5 値と分母
    def by_state(self, state: str, asof_id: str = "") -> tuple[Pair, ...]:
        return tuple(p for p in self.pairs if p.state == state
                     and (not asof_id or p.asof_id == asof_id))

    @property
    def denominator(self) -> int:
        return self.report.rows * self.report.asofs

    def five(self, asof_id: str = "") -> dict[str, int]:
        return {s: len(self.by_state(s, asof_id)) for s in RESULTS}

    def counts(self) -> dict[str, object]:
        """件数は分母(行数 × 基準日の数)と内訳つきで出す。率は単独で返さない。"""
        five = self.five()
        per = {a.asof_id: self.five(a.asof_id) for a in self.asofs.ordered}
        changes_per = {a.asof_id: len([c for c in self.changes
                                       if c.asof_id == a.asof_id])
                       for a in self.asofs.ordered}
        out: dict[str, object] = {
            "行の表の行数": self.report.rows,
            "状態の宣言の行数(rule 数)": self.report.rules,
            "基準日の数": self.report.asofs,
            "分母(行数 × 基準日の数)": self.denominator,
            "5 値": five,
            "基準日ごとの 5 値": per,
            "次に変わる日の件数": len(self.changes),
            "基準日ごとの次に変わる日の件数": changes_per,
            "読んだか": ("読んだ" if self.pairs else
                         "読んでいない(表が揃う前に止まったので 5 値は全て 0)"),
        }
        out["分母に含めたもの"] = (
            f"行数 {self.report.rows} × 基準日の数 {self.report.asofs}"
            f" = {self.denominator} 組。5 値の内訳は "
            + " + ".join(f"{s} {five[s]}" for s in RESULTS)
            + "。次に変わる日は rule ごと・基準日ごとに 1 件以下なので、"
            f"{self.report.rules} × {self.report.asofs} 件を超えない")
        out["件数の合計の検算"] = (
            f"5 値の合計 {sum(five.values())} / 分母 {self.denominator}"
            f"(次に変わる日 {len(self.changes)} ≦ rule 数 {self.report.rules}"
            f" × 基準日の数 {self.report.asofs})")
        out["空の効き始める日を埋めない"] = (
            "効き始める日が宣言された空の記号だった行は、予定に置いて日付を返さない。"
            "基準日・年度初め・公布日・次の月初へ丸める引数が 1 つも無い")
        out["知った日で引かない"] = (
            "知った日は「もう知っているか」を見るためだけに使う。"
            "効き始める日の代わりに知った日で引く経路が無い")
        out["判定にシステム日付を使わない"] = (
            "基準日は基準日の表から受け取る。システムの日付と時刻は「読んだ条件」の欄に"
            "書き出すだけで判定部分に入れないので、同じ 3 枚なら明日読んでも同じバイト列になる")
        out["まだ効き始めていない行を答えに混ぜない"] = (
            "答えの口(基準日に効いている)と予定の口(これから効き始める / "
            "効き始める日が未定)は別の配列で返す。1 つにまとめる経路が無い")
        out["段階施行を 1 行にまとめない"] = (
            "効き始める日ごとに別の行として数える。まとめる引数が無いので、"
            "段階施行は行数のまま残る")
        out["値を返さない"] = (
            "行の表に値の列が無い。返るのは状態と、次に変わる日と、その行の id と"
            "出典だけで、料率も金額も丸めも計算も無い")
        return out

    # -------------------------------------------------- 答えの口と予定の口
    def today(self) -> list[dict[str, str]]:
        """答えの口。基準日に効いている組だけ。"""
        return [p.as_dict() for p in self.by_state(STATES[1])]

    def ahead(self) -> list[dict[str, str]]:
        """予定の口のうち、効き始める日が決まっている組。"""
        return [p.as_dict() for p in self.by_state(STATES[2])]

    def undated(self) -> list[dict[str, str]]:
        """予定の口のうち、効き始める日が未定の組(日付は返さない)。"""
        return [p.as_dict() for p in self.by_state(STATES[3])]

    def closed(self) -> list[dict[str, str]]:
        return [p.as_dict() for p in self.by_state(STATES[0])]

    def next_days(self) -> list[dict[str, str]]:
        """rule ごと・基準日ごとに 1 件。無い組は「無い」とだけ返す。"""
        got = {(c.rule_id, c.asof_id): c for c in self.changes}
        out: list[dict[str, str]] = []
        for rule in self.declared.ordered:
            for a in self.asofs.ordered:
                c = got.get((rule.rule_id, a.asof_id))
                out.append(c.as_dict() if c else
                           {"rule id": rule.rule_id, "基準日 id": a.asof_id,
                            "次に変わる日": NAI, "行 id": "", "出典": ""})
        return out

    # -------------------------------------------------- 判定部分
    def judgement_bytes(self) -> bytes:
        """判定部分 = 読んだ組と次に変わる日。時刻・絶対パス・ホスト名は入れない。"""
        self._guard()
        lines = ["\t".join(["組", str(self.report.rows), str(self.report.asofs),
                            str(self.denominator)])]
        for p in self.pairs:
            lines.append("\t".join([p.row_id, p.rule_id, p.asof_id, p.state]))
        for c in self.changes:
            lines.append("\t".join(["次", c.rule_id, c.asof_id, c.day, c.row_id]))
        return ("\n".join(lines) + "\n").encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.judgement_bytes()).hexdigest()

    def read_condition(self) -> dict[str, str]:
        return {SCOPE_KEYS[0]: self.sheet.path, SCOPE_KEYS[1]: self.declared.path,
                SCOPE_KEYS[2]: self.asofs.path, SCOPE_KEYS[3]: self.read_at,
                SCOPE_KEYS[4]: self.host}

    def _guard(self) -> None:
        if not self.report.ok:
            raise RuntimeError("止まっているので読んだ組は無い。"
                               "report.pending の理由コードを見る")


def future_row(sheet: Sheet, declared: Declared, asofs: Asofs) -> Table:
    """まだ効き始めていない行を基準日の答えから分ける。表が揃う前に止まったら 1 組も読まない。"""
    now = datetime.datetime.now().isoformat(timespec="seconds")
    host = platform.node()
    pending = list(sheet.pending) + list(declared.pending) + list(asofs.pending)

    # 知った日が基準日より後の行は扱わない(当時の知識を再現するのは別の部品)
    for r in sheet.ordered:
        for a in asofs.ordered:
            if r.known_from > a.asof:
                pending.append(Pending(STOP_REASONS[2],
                                       f"行の表 行 {r.number}({r.row_id}): "
                                       f"知った日 {r.known_from} > 基準日 "
                                       f"{a.asof}({a.asof_id})"))

    # 同じ rule・同じ対象・同じ順位で、効いている期間が重なっていないか
    groups: dict[tuple[object, ...], list[Row]] = {}
    for r in sheet.ordered:
        if not r.undated:
            groups.setdefault(r.key, []).append(r)
    for _, rows in sorted(groups.items(), key=lambda kv: str(kv[0])):
        ordered = sorted(rows, key=lambda r: (r.valid_from, r.row_id))
        for first, second in zip(ordered, ordered[1:]):
            if second.valid_from < (first.valid_to or TOMEDA):
                pending.append(Pending(STOP_REASONS[7],
                                       f"{first.row_id} [{first.valid_from},"
                                       f"{first.valid_to or '開いている'}) と "
                                       f"{second.row_id} [{second.valid_from},"
                                       f"{second.valid_to or '開いている'}) が重なる"
                                       f"(rule {first.rule_id}、順位 "
                                       f"{first.priority or '空欄'})"))

    def made(pend: tuple[Pending, ...], pairs: tuple[Pair, ...] = (),
             changes: tuple[Change, ...] = ()) -> Table:
        return Table(report=Report(not pend, pend, len(sheet.items),
                                   len(declared.items), len(asofs.items)),
                     pairs=pairs, changes=changes, sheet=sheet, declared=declared,
                     asofs=asofs, read_at=now, host=host)

    if pending:                      # 表が揃う前に止まる(1 組も読まない)
        return made(tuple(pending))

    pairs = tuple(Pair(r.row_id, r.rule_id, a.asof_id, state_of(r, a.asof))
                  for r in sheet.ordered for a in asofs.ordered)
    changes: list[Change] = []
    for rule in declared.ordered:
        for a in asofs.ordered:
            hit = next_change(sheet.of(rule.rule_id), a.asof)
            if hit is not None:
                changes.append(Change(rule.rule_id, a.asof_id, hit.valid_from,
                                      hit.row_id, hit.source))
    return made((), pairs, tuple(changes))


# ------------------------------------------------------------ verify

def shift_check(sheet: Sheet, declared: Declared, asofs: Asofs,
                table: Table) -> dict[str, object]:
    """基準日を次に変わる日まで進めると、これから効き始める が減った分だけ効き始めた側が増える。

    進めた先の日は、その日に前の行が閉じることもある(施行日 = 前の行の終わりの日)。だから
    増える先は「基準日に効いている」だけとは限らず、「もう効き終わった」に入ることもある。
    検算は「減った分 = 効き始めた側(2 つの合計)の増えた分」で見て、内訳も別に数える。
    """
    out: list[dict[str, object]] = []
    for a in asofs.ordered:
        day = next_change(sheet.ordered, a.asof)
        if day is None:
            out.append({"基準日 id": a.asof_id, "進めた先": NAI})
            continue
        moved = Asofs(items=(Asof(a.asof_id, day.valid_from, a.source, a.number),),
                      swap=asofs.swap, path=asofs.path)
        after = future_row(sheet, declared, moved)
        if not after.report.ok:
            out.append({"基準日 id": a.asof_id, "進めた先": day.valid_from,
                        "読めたか": "止まった"})
            continue
        before, later = table.five(a.asof_id), after.five()
        down = before[STATES[2]] - later[STATES[2]]
        up_today = later[STATES[1]] - before[STATES[1]]
        up_closed = later[STATES[0]] - before[STATES[0]]
        out.append({"基準日 id": a.asof_id, "進めた先": day.valid_from,
                    "これから効き始める が減った分": down,
                    "基準日に効いている が増えた分": up_today,
                    "もう効き終わった が増えた分": up_closed,
                    "合うか": down == up_today + up_closed})
    return {"進めた基準日の数": len([x for x in out if x.get("進めた先") != NAI]),
            "基準日ごと": out}


def verify(sheet: Sheet, declared: Declared, asofs: Asofs) -> dict[str, object]:
    """2 回読んで sha256 を比べ、3 枚の行順を入れ替えても同じかを見て、件数を検算する。"""
    first = future_row(sheet, declared, asofs)
    if not first.report.ok:
        return {"ok": False, "stage": "止まった(読んだ組は返さない)", **first.counts(),
                "pending": [p.as_dict() for p in first.report.pending]}
    if not asofs.swap:
        raise ReadError("基準日の表に入れ替え方(swap)が無いので verify は走らせない")
    second = future_row(sheet, declared, asofs)
    third = future_row(sheet.swapped(asofs.swap), declared.swapped(asofs.swap),
                       asofs.swapped(asofs.swap))
    pending: list[Pending] = []
    if first.sha256() != second.sha256():
        pending.append(Pending(STOP_REASONS[9], f"2 回目 {second.sha256()[:12]}"))
    if not (third.report.ok and first.sha256() == third.sha256()):
        pending.append(Pending(STOP_REASONS[10],
                               f"入れ替え方 {asofs.swap} の 3 枚で "
                               f"{third.sha256()[:12]}" if third.report.ok else
                               f"入れ替え方 {asofs.swap} の 3 枚では止まった"))
    five = first.five()
    if sum(five.values()) != first.denominator:
        pending.append(Pending(STOP_REASONS[8],
                               f"5 値の合計 {sum(five.values())}"
                               f" / 分母 {first.denominator}"))
    for a in asofs.ordered:
        n = len([c for c in first.changes if c.asof_id == a.asof_id])
        if n > first.report.rules:
            pending.append(Pending(STOP_REASONS[8],
                                   f"次に変わる日 {n} 件 > rule 数 "
                                   f"{first.report.rules}({a.asof_id})"))
    shift = shift_check(sheet, declared, asofs, first)
    for row in shift["基準日ごと"]:                       # type: ignore[union-attr]
        if row.get("合うか") is False:
            pending.append(Pending(STOP_REASONS[8],
                                   "基準日を進めた突合が合わない"
                                   f"({row['基準日 id']})"))
    out: dict[str, object] = {
        "ok": not pending, "読んだ回数": 2, "入れ替え方": asofs.swap,
        "sha256": first.sha256(), "2 回目の sha256": second.sha256(),
        "入れ替えた 3 枚の sha256": third.sha256() if third.report.ok else "",
        "件数の検算": {"5 値": five, "5 値の合計": sum(five.values()),
                       "分母(行数 × 基準日の数)": first.denominator,
                       "次に変わる日の件数": len(first.changes),
                       "rule 数 × 基準日の数": (first.report.rules
                                                * first.report.asofs)},
        "基準日を次に変わる日まで進めた突合": shift,
    }
    if pending:
        out["観測"] = ("同じ表から違う読みが出た(平均も多数決もしない。"
                       "どちらが正しいかも決めない)")
        out["pending"] = [p.as_dict() for p in pending]
    return out


# ------------------------------------------------------------ ひな型

MARK = "政令待ち"
TEMPLATE_DECLARED = [
    list(SENGEN_COLUMNS),
    ["R01",
     STATE_SEP.join([f"{STATES[0]}=効き終わる日が基準日以前",
                     f"{STATES[1]}=基準日が効いている期間の中",
                     f"{STATES[2]}=効き始める日が基準日より後",
                     f"{STATES[3]}=効き始める日が宣言された空の記号"]),
     BLANK_RULES[0], OPEN_RULES[0], MARK, "合成の宣言メモ(架空)L1"],
]
TEMPLATE_SHEET = [
    list(GYOU_COLUMNS),
    ["G01", "R01", "2001-04-01", "2001-04-01", "2007-10-01",
     "合成の次元A(架空)=合成の値1(架空)", "0", "合成の公表元(架空)",
     "合成の行メモ(架空)L1"],
    ["G02", "R01", "2004-06-01", "2007-10-01", MARK,
     "合成の次元A(架空)=合成の値1(架空)", "0", "合成の公表元(架空)",
     "合成の行メモ(架空)L2"],
    ["G03", "R01", "2004-06-01", MARK, MARK,
     "合成の次元A(架空)=合成の値2(架空)", "10", "合成の公表元(架空)",
     "合成の行メモ(架空)L3"],
]
TEMPLATE_ASOFS = [
    list(KIJUNBI_COLUMNS),
    ["A01", "2005-06-30", "合成の基準日メモ(架空)L1", SWAPS[0]],
    ["A02", "2008-01-01", "合成の基準日メモ(架空)L2", ""],
]


def write_csv(path: Path, rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    return path


def init(dest: str | Path) -> tuple[Path, Path, Path]:
    d = Path(dest)
    return (write_csv(d / "行の表.csv", TEMPLATE_SHEET),
            write_csv(d / "状態の宣言.csv", TEMPLATE_DECLARED),
            write_csv(d / "基準日の表.csv", TEMPLATE_ASOFS))


# ------------------------------------------------------------ CLI

def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def build_parser() -> argparse.ArgumentParser:
    """CLI は split / next / check / verify / init の 5 つで、option は -h 以外に 1 つも無い。"""
    ap = argparse.ArgumentParser(prog="future_row",
                                 description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in SUBCOMMANDS[:4]:
        p = sub.add_parser(name)
        p.add_argument("sheet")
        p.add_argument("declared")
        p.add_argument("asofs")
    sub.add_parser(SUBCOMMANDS[4]).add_argument("dest")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == "init":
        print("書いた: " + " / ".join(str(p) for p in init(a.dest)))
        return 0
    try:
        declared = Declared.load(a.declared)
        sheet = Sheet.load(a.sheet, declared)
        asofs = Asofs.load(a.asofs)
        if a.cmd == "verify":
            out = verify(sheet, declared, asofs)
            _print(out)
            return 0 if out["ok"] else 3
        t = future_row(sheet, declared, asofs)
    except ReadError as e:
        print(f"表として読めない: {e}", file=sys.stderr)
        return 2
    if not t.report.ok:
        _print({"ok": False, "stage": "止まった(読んだ組は返さない)", **t.counts(),
                "pending": [p.as_dict() for p in t.report.pending]})
        return 3
    body: dict[str, object] = {"ok": True, **t.counts()}
    if a.cmd == "split":
        body["答えの口(基準日に効いている)"] = t.today()
        body["予定の口(これから効き始める)"] = t.ahead()
        body["予定の口(効き始める日が未定)"] = t.undated()
        body["もう効き終わった"] = t.closed()
        body["sha256"] = t.sha256()
        body["読んだ条件"] = t.read_condition()
    if a.cmd == "next":
        body["次に変わる日"] = t.next_days()
        body["sha256"] = t.sha256()
    _print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
