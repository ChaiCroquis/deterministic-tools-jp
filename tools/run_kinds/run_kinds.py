"""run_kinds — 実行の記録を、回ごとに 6 値 + 別枠へ仕分ける。

**「ジョブが通ったか」と「本番の中身が入れ替わったか」は別の軸で、通った / 落ちたの 2 値だけを
数えると、どちらも読めない数字が出る。**

この部品は、実行の台帳・意図の宣言表・語の登録表の 3 枚から、実行 1 回ごとに 6 値
(**据え置き・試験と事前に宣言されている / 据え置き・試験の事前の宣言が無い / 初回(比べる
相手が無い)/ 差分 0 かつ指紋が直前と同じ / 差分ありかつ指紋が直前と違う / 差分の件数と指紋の
動きが噛み合わない**)か、別枠 2 種(**登録表に無い status 語 / 落ちたのに指紋が動いた**)の
どれか 1 つを付ける。**成功率も稼働率も出さない。失敗の原因も分類しない。良し悪しも判定しない。**

持たせていないものが規律になっている。

  - **成功率・稼働率・失敗率を出さない**(件数と内訳だけを返す。割合にする経路も option も
    無く、分母をこの部品が決めない)
  - **失敗の原因を分類しない**(入力に error の列が無く、本文を読む経路も無い。落ちた回に
    付くのは据え置きの有無と、事前の宣言が在るかだけ)
  - **事後の申告を試験として数えない**(宣言が実行より後の行は、宣言が無い回と同じ値へ落ちる。
    後から「あれは試験だった」と言える経路を持たない)
  - **実行を障害と呼ばない**(出力に障害・異常・事故の語が無い。落ちた回は「落ちたと宣言され、
    据え置きになった回」としか書かない)
  - **鮮度・最終更新日・次に動く日を出さない**(入力に日付の列も時刻の列も無い。現在時刻を
    読む呼び出しも 1 つも無い。基準は並び順の番号だけ)
  - **差分の中身を見ない**(どの行がどう変わったかの列が無い。件数 3 つと指紋だけを読む)
  - **再実行しない・取りに行かない**(走らせる経路も、通信の経路も無い)
  - **良し悪し・順位・推奨・次にすべきことを出さない**(点数欄も順位欄も無い)
  - **出典の欄が空の行は使わずに止まる**
  - **入力表を書き換えず、行も宣言も生成しない**
  - **同じ入力には同じバイト列**(判定部分に時刻・絶対パス・ホスト名を入れない。行順にも依らない)
  - **数は整数だけ**(件数も差分も整数で、float を使う経路が無い)

入力は 3 つ。

実行の台帳(CSV)の列は 9。**1 回の実行が 1 行**。

    run_id        実行 id(同じ id が 2 行あると止まる)
    seq           並び順の番号(1 から連続する整数。**時刻でなく、この欄で順を決める**)
    status        宣言された status の語(登録表に無ければ **別枠**)
    added         差分の件数・追加(0 以上の整数)
    removed       差分の件数・削除(同上)
    changed       差分の件数・変更(同上)
    first_run     初回の印(`初回` / 空欄)。**先頭の行以外に付いていたら止まる**
    fingerprint   出力の指紋(空欄可)
    source        出典(ファイル名 + 行番号)。空欄は止まる

意図の宣言表(CSV)の列は 4。**1 回の実行が 1 行**(ヘッダだけでも読める)。

    run_id             実行 id(台帳に無い id は一覧へ出すだけで止めない)
    intent             意図コード(登録表に意図コードとして無ければ止まる)
    declared_before    宣言された時点が実行より前かどうかの印(`実行より前` / `実行より後`)
    source             宣言の出典。空欄は止まる

語の登録表(CSV)の列は 4。**1 つの語が 1 行**。status の語と意図コードを同じ表に書く。

    word         語(`ok` / `failed` / `失敗試験` など)
    meaning      意味(`通った` / `落ちた` = status の語、`試験` / `試験でない` = 意図コード)
    holds        据え置きを伴うか(`据え置き` / `据え置かない`)。
                 **意図コードの行のこの欄は記録するだけで判定に使わない**
    declared_in  登録の出典。空欄は止まる

使い方:

    python run_kinds.py init ひな型/
    python run_kinds.py check 実行の台帳.csv 意図の宣言表.csv 語の登録表.csv
    python run_kinds.py kinds 実行の台帳.csv 意図の宣言表.csv 語の登録表.csv
    python run_kinds.py verify 実行の台帳.csv 意図の宣言表.csv 語の登録表.csv

終了コードは、別枠・噛み合わない回・事前の宣言が無い据え置き・逆向きの欠け・止まった行が 0 件の
ときだけ 0、在れば 3、表として読めなければ 2。**0 は「稼働率が高い」ではなく「台帳と宣言に
欠けが無い」の意味で、良し悪しはこの部品の終了コードにも出力にも出ない。**
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

RUNS_COLUMNS = ("run_id", "seq", "status", "added", "removed", "changed",
                "first_run", "fingerprint", "source")
INTENT_COLUMNS = ("run_id", "intent", "declared_before", "source")
WORDS_COLUMNS = ("word", "meaning", "holds", "declared_in")

TOTTA, OCHITA, SHIKEN, SHIKEN_DENAI = "通った", "落ちた", "試験", "試験でない"
MEANINGS = (TOTTA, OCHITA, SHIKEN, SHIKEN_DENAI)
STATUS_MEANINGS = (TOTTA, OCHITA)
INTENT_MEANINGS = (SHIKEN, SHIKEN_DENAI)

SUEOKI, SUEOKANAI = "据え置き", "据え置かない"
HOLDS = (SUEOKI, SUEOKANAI)

MAE, ATO = "実行より前", "実行より後"
BEFORE_MARKS = (MAE, ATO)

SHOKAI = "初回"
FIRST_MARKS = (SHOKAI, "")

# 実行 1 回に付く 6 値 + 別枠 2 種。**この 8 つの外に値を作る経路が無い。**
KEKKA = (
    "据え置き・試験と事前に宣言されている",
    "据え置き・試験の事前の宣言が無い",
    "初回(比べる相手が無い)",
    "差分 0 かつ指紋が直前と同じ",
    "差分ありかつ指紋が直前と違う",
    "差分の件数と指紋の動きが噛み合わない",
    "登録表に無い status 語",
    "落ちたのに指紋が動いた",
)
MUTSU = KEKKA[:6]       # 6 値
BEKKA = KEKKA[6:]       # 別枠 2 種

# ② に入った回の、事前の宣言が無い言い方の違い(**解釈で埋めず、言い方のまま分けて出す**)
NASHI_KINDS = ("宣言そのものが無い", "宣言が実行より後", "宣言された意図が試験でない")

SWAPS = ("逆順", "両端入れ替え", "1 つずらす")

STOP_REASONS = (
    # 3 枚の表の側。1 行も数えずに止まる(9)
    "出典の欄が空",
    "同じ実行 id が台帳に 2 行ある",
    "並び順の番号が 1 から連続していない",
    "初回の印が並び順の先頭の行以外に付いている",
    "据え置きを伴う語の回に差分の件数が書かれている",
    "据え置きを伴わない語の回に指紋が無い",
    "同じ実行 id に 2 通りの意図コードが宣言されている",
    "意図コードとして登録されていない語が宣言されている",
    "初回の印が無い回の前に指紋が 1 つも無い",
    # verify が見つける(3)
    "件数の合計が合わない", "2 回目の判定部分が不一致", "行順を入れ替えた表で出力が変わる",
)
TABLE_REASONS = STOP_REASONS[:9]
VERIFY_REASONS = STOP_REASONS[9:]

SUBCOMMANDS = ("kinds", "check", "verify", "init")
SCOPE_KEYS = ("読んだ実行の台帳の絶対パス", "読んだ意図の宣言表の絶対パス",
              "読んだ語の登録表の絶対パス")

NG_ID = set(" \t,|")


class ReadError(Exception):
    """表として読めない(終了コード 2)。実行は 1 回も数えない。"""


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


# ------------------------------------------------------------ 語の登録表


@dataclass(frozen=True)
class Word:
    """語 1 つ。**意味と据え置きの有無は人が書いた宣言で、道具が当てる経路が無い。**"""
    word: str
    meaning: str
    holds: str
    declared_in: str

    @property
    def is_status(self) -> bool:
        return self.meaning in STATUS_MEANINGS

    @property
    def is_intent(self) -> bool:
        return self.meaning in INTENT_MEANINGS

    @property
    def is_test(self) -> bool:
        """**試験かどうかは登録表の意味だけで決まる**(語の形から当てない)。"""
        return self.meaning == SHIKEN

    @property
    def holding(self) -> bool:
        return self.holds == SUEOKI


@dataclass(frozen=True)
class Words:
    items: tuple[Word, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Words":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"語の登録表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Words":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in WORDS_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("語の登録表に " + " / ".join(lack) + " の列が無い")
        items: list[Word] = []
        pending: list[Pending] = []
        seen: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in WORDS_COLUMNS}
            where = f"語の登録表 行 {i}"
            if bad_id(cell["word"]):
                raise ReadError(f"{where}: 語が空欄か、区切り文字を含む"
                                f"({cell['word'] or '空欄'})")
            if cell["meaning"] not in MEANINGS:
                raise ReadError(f"{where}: 意味が登録の 4 つでない"
                                f"({cell['meaning'] or '空欄'})")
            if cell["holds"] not in HOLDS:
                raise ReadError(f"{where}: 据え置きを伴うかが登録の 2 つでない"
                                f"({cell['holds'] or '空欄'})")
            if cell["word"] in seen:
                raise ReadError(f"{where}: 同じ語が 2 行ある({cell['word']})")
            seen.add(cell["word"])
            if not cell["declared_in"]:
                pending.append(Pending(STOP_REASONS[0], f"{where}: {cell['word']}"))
            items.append(Word(word=cell["word"], meaning=cell["meaning"],
                              holds=cell["holds"], declared_in=cell["declared_in"]))
        if not items:
            raise ReadError("語の登録表に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    def of(self, word: str) -> Word | None:
        """**登録に無い語には何も当てない**(None を返す = 別枠へ)。"""
        return next((w for w in self.items if w.word == word), None)

    def status_of(self, word: str) -> Word | None:
        """status の語として登録されているものだけを返す(意図コードは当てない)。"""
        w = self.of(word)
        return w if (w is not None and w.is_status) else None

    def intent_of(self, word: str) -> Word | None:
        w = self.of(word)
        return w if (w is not None and w.is_intent) else None

    @property
    def status_words(self) -> tuple[str, ...]:
        return tuple(sorted(w.word for w in self.items if w.is_status))

    @property
    def test_words(self) -> tuple[str, ...]:
        return tuple(sorted(w.word for w in self.items if w.is_test))

    def swapped(self, how: str) -> "Words":
        return Words(items=tuple(swap_rows(list(self.items), how)),
                     pending=self.pending, path=self.path)


# ------------------------------------------------------------ 意図の宣言表


@dataclass(frozen=True)
class Intent:
    """意図の宣言 1 つ。**宣言された時点が実行より前かどうかの印を必ず持つ。**"""
    run_id: str
    intent: str
    declared_before: str
    source: str
    number: int = 0

    @property
    def before(self) -> bool:
        return self.declared_before == MAE


@dataclass(frozen=True)
class Intents:
    items: tuple[Intent, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Intents":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"意図の宣言表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Intents":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in INTENT_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("意図の宣言表に " + " / ".join(lack) + " の列が無い")
        items: list[Intent] = []
        pending: list[Pending] = []
        seen: dict[str, str] = {}
        pairs: set[tuple[str, str]] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in INTENT_COLUMNS}
            where = f"意図の宣言表 行 {i}"
            if bad_id(cell["run_id"]):
                raise ReadError(f"{where}: 実行 id が空欄か、区切り文字を含む"
                                f"({cell['run_id'] or '空欄'})")
            if bad_id(cell["intent"]):
                raise ReadError(f"{where}: 意図コードが空欄か、区切り文字を含む"
                                f"({cell['intent'] or '空欄'})")
            if cell["declared_before"] not in BEFORE_MARKS:
                raise ReadError(f"{where}: 宣言の前後の印が登録の 2 つでない"
                                f"({cell['declared_before'] or '空欄'})")
            pair = (cell["run_id"], cell["intent"])
            if pair in pairs:
                raise ReadError(f"{where}: 同じ実行 id と意図コードの組が 2 行ある"
                                f"({' / '.join(pair)})")
            pairs.add(pair)
            if seen.setdefault(cell["run_id"], cell["intent"]) != cell["intent"]:
                pending.append(Pending(STOP_REASONS[6],
                                       f"{where}: {cell['run_id']} = "
                                       f"{seen[cell['run_id']]} / {cell['intent']}"))
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0],
                                       f"{where}: {cell['run_id']}"))
            items.append(Intent(run_id=cell["run_id"], intent=cell["intent"],
                                declared_before=cell["declared_before"],
                                source=cell["source"], number=i))
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    @property
    def ordered(self) -> tuple[Intent, ...]:
        return tuple(sorted(self.items, key=lambda x: (x.run_id, x.intent)))

    def of(self, run_id: str) -> Intent | None:
        return next((x for x in self.ordered if x.run_id == run_id), None)

    def without(self, run_id: str) -> "Intents":
        """宣言 1 件を外した写し(verify が使う。入力には書かない)。"""
        return Intents(items=tuple(x for x in self.items if x.run_id != run_id),
                       pending=self.pending, path=self.path)

    def issues(self, words: Words) -> tuple[Pending, ...]:
        """意図コードとして登録されていない語の宣言(= 1 行も数えずに止まる)。"""
        out: list[Pending] = []
        for x in self.ordered:
            if words.intent_of(x.intent) is None:
                out.append(Pending(STOP_REASONS[7],
                                   f"意図の宣言表 行 {x.number}: {x.intent}"))
        return tuple(out)

    def swapped(self, how: str) -> "Intents":
        return Intents(items=tuple(swap_rows(list(self.items), how)),
                       pending=self.pending, path=self.path)


# ------------------------------------------------------------ 実行の台帳


@dataclass(frozen=True)
class Run:
    """台帳 1 行 = 1 回の実行。**時刻の欄を持たない**(順は並び順の番号だけで決まる)。"""
    run_id: str
    seq: int
    status: str
    added: int
    removed: int
    changed: int
    first_run: str
    fingerprint: str
    source: str
    number: int = 0

    @property
    def first(self) -> bool:
        return self.first_run == SHOKAI

    @property
    def diff_total(self) -> int:
        """差分の件数の合計(整数のまま。割合にしない)。"""
        return self.added + self.removed + self.changed


@dataclass(frozen=True)
class Runs:
    items: tuple[Run, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Runs":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"実行の台帳が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Runs":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in RUNS_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("実行の台帳に " + " / ".join(lack) + " の列が無い")
        items: list[Run] = []
        pending: list[Pending] = []
        seen: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in RUNS_COLUMNS}
            where = f"実行の台帳 行 {i}"
            if bad_id(cell["run_id"]):
                raise ReadError(f"{where}: 実行 id が空欄か、区切り文字を含む"
                                f"({cell['run_id'] or '空欄'})")
            if bad_id(cell["status"]):
                raise ReadError(f"{where}: status の語が空欄か、区切り文字を含む"
                                f"({cell['status'] or '空欄'})")
            if cell["first_run"] not in FIRST_MARKS:
                raise ReadError(f"{where}: 初回の印が登録の語でない"
                                f"({cell['first_run']})")
            seq = whole(cell["seq"], "並び順の番号", where)
            if seq == 0:
                raise ReadError(f"{where}: 並び順の番号は 1 から始まる(0 は読めない)")
            counts = {k: whole(cell[k], f"差分の件数({k})", where)
                      for k in ("added", "removed", "changed")}
            if cell["run_id"] in seen:
                pending.append(Pending(STOP_REASONS[1], f"{where}: {cell['run_id']}"))
            seen.add(cell["run_id"])
            items.append(Run(run_id=cell["run_id"], seq=seq, status=cell["status"],
                             added=counts["added"], removed=counts["removed"],
                             changed=counts["changed"], first_run=cell["first_run"],
                             fingerprint=cell["fingerprint"], source=cell["source"],
                             number=i))
        if not items:
            raise ReadError("実行の台帳に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    @property
    def ordered(self) -> tuple[Run, ...]:
        """並び順の番号だけで順を決める(行順に依らない = 入れ替えても同じ出力)。"""
        return tuple(sorted(self.items, key=lambda r: (r.seq, r.run_id)))

    @property
    def total(self) -> int:
        return len(self.items)

    def of(self, run_id: str) -> Run | None:
        return next((r for r in self.ordered if r.run_id == run_id), None)

    def issues(self, words: Words) -> tuple[Pending, ...]:
        """1 回も数えずに止まる食い違い(出典・並び順・初回の印・据え置きと欄の食い違い)。"""
        out: list[Pending] = []
        for r in self.ordered:
            if not r.source:
                out.append(Pending(STOP_REASONS[0],
                                   f"実行の台帳 行 {r.number}({r.run_id})"))
        numbers = sorted(r.seq for r in self.items)
        if numbers != list(range(1, len(numbers) + 1)):
            out.append(Pending(STOP_REASONS[2],
                               f"並び順の番号 {numbers} / 件数 {len(numbers)}"))
        firsts = [r for r in self.ordered if r.first]
        for r in firsts:
            if r.seq != 1:
                out.append(Pending(STOP_REASONS[3],
                                   f"実行の台帳 行 {r.number}({r.run_id})"
                                   f": 並び順 {r.seq}"))
        if len(firsts) > 1:
            out.append(Pending(STOP_REASONS[3],
                               "初回の印が " + " / ".join(r.run_id for r in firsts)))
        for r in self.ordered:
            word = words.status_of(r.status)
            if word is None:
                continue        # 登録表に無い status 語は別枠へ出す(止めない)
            where = f"実行の台帳 行 {r.number}({r.run_id})"
            if word.holding and r.diff_total:
                out.append(Pending(STOP_REASONS[4],
                                   f"{where}: {r.added}/{r.removed}/{r.changed}"))
            if not word.holding and not r.fingerprint:
                out.append(Pending(STOP_REASONS[5], f"{where}: {r.status}"))
        return tuple(out)

    def repainted(self, run_id: str, fingerprint: str) -> "Runs":
        """ある回の指紋だけを書き換えた写し(verify が使う。入力には書かない)。"""
        return Runs(items=tuple(
            (r if r.run_id != run_id else
             Run(**{**{k: getattr(r, k) for k in r.__dataclass_fields__},
                    "fingerprint": fingerprint}))
            for r in self.items), pending=self.pending, path=self.path)

    def swapped(self, how: str) -> "Runs":
        return Runs(items=tuple(swap_rows(list(self.items), how)),
                    pending=self.pending, path=self.path)


# ------------------------------------------------------------ 仕分ける


@dataclass(frozen=True)
class Judged:
    """実行 1 回の結果。**成功率に使う欄も、原因の欄も持たない。**"""
    run: Run
    result: str
    previous: str = ""          # 直前の指紋(空 = 比べる相手が無い)
    returned: bool = False      # 履歴の前の回の値へ戻った印
    nashi: str = ""             # ② に入った回の、言い方の違い
    intent: str = ""            # 宣言されていた意図コード(在れば)

    @property
    def counted(self) -> bool:
        """6 値のどれかが付いたか(= 別枠でないか)。"""
        return self.result in MUTSU

    def verdict(self) -> str:
        """その回に付いた判定だけ(指紋の値は入れない)。**写しで動いた回を数える単位。**"""
        return f"{self.result}:{'戻り' if self.returned else ''}:{self.nashi}"

    def line(self) -> str:
        return (f"{self.run.seq:04d}/{self.run.run_id}:{self.result}"
                f":{self.run.status}:{self.run.diff_total}"
                f":{self.run.fingerprint}:{self.previous}"
                f":{'戻り' if self.returned else ''}:{self.nashi}:{self.intent}")

    def as_dict(self) -> dict[str, object]:
        return {"実行 id": self.run.run_id, "並び順": self.run.seq,
                "status の語": self.run.status,
                "差分の件数": {"追加": self.run.added, "削除": self.run.removed,
                               "変更": self.run.changed,
                               "合計": self.run.diff_total},
                "指紋": self.run.fingerprint, "直前の指紋": self.previous,
                "判定": self.result,
                "事前の宣言が無い言い方": self.nashi,
                "宣言されていた意図コード": self.intent,
                "履歴の前の回の値へ戻った": "戻り" if self.returned else "",
                "出典": self.run.source}


def judge(run: Run, words: Words, intents: Intents, previous: str,
          history: tuple[str, ...]) -> Judged:
    """実行 1 回に 6 値 + 別枠のどれか 1 つを付ける。**良し悪しは決めない。**

    上から順に見る。status の語が登録表に無ければ別枠(語の形から意味を当てる経路が無い)。
    据え置きを伴う語の回はここで終わり(差分と指紋の動きを見に行く経路が無い)。**試験として
    数えるのは、意味が「試験」として登録された意図コードが実行より前に宣言された回だけで、
    事後の宣言はここで ② 側へ落ちる。**
    """
    word = words.status_of(run.status)
    if word is None:
        return Judged(run, KEKKA[6])
    declared = intents.of(run.run_id)
    code = declared.intent if declared else ""
    if word.holding:
        if run.fingerprint:
            return Judged(run, KEKKA[7], intent=code)
        if declared is None:
            return Judged(run, KEKKA[1], nashi=NASHI_KINDS[0])
        kind = words.intent_of(declared.intent)
        if kind is not None and kind.is_test and declared.before:
            return Judged(run, KEKKA[0], intent=code)
        nashi = NASHI_KINDS[1] if not declared.before else NASHI_KINDS[2]
        return Judged(run, KEKKA[1], nashi=nashi, intent=code)
    if run.first:
        return Judged(run, KEKKA[2], intent=code)
    moved = run.fingerprint != previous
    returned = bool(moved and run.fingerprint in history)
    if run.diff_total == 0 and not moved:
        return Judged(run, KEKKA[3], previous=previous, intent=code)
    if run.diff_total and moved:
        return Judged(run, KEKKA[4], previous=previous, returned=returned,
                      intent=code)
    return Judged(run, KEKKA[5], previous=previous, returned=returned, intent=code)


@dataclass(frozen=True)
class Report:
    ok: bool
    pending: tuple[Pending, ...]
    runs: int
    intents: int
    words: int


@dataclass(frozen=True)
class Tally:
    report: Report
    judged: tuple[Judged, ...]
    runs: Runs
    intents: Intents
    words: Words

    # ---------------- 分母

    def run_denominator(self) -> int:
        return self.report.runs

    @property
    def counted_denominator(self) -> int:
        """6 値が付いた回の数(別枠を外した数)。"""
        return sum(1 for j in self.judged if j.counted)

    def aside_denominator(self) -> int:
        return sum(1 for j in self.judged if not j.counted)

    # ---------------- 件数

    def six(self) -> dict[str, int]:
        return {k: sum(1 for j in self.judged if j.result == k) for k in KEKKA}

    def by_status(self) -> list[dict[str, object]]:
        """status 語ごとの内訳(合計が全体に戻るかが二重集計の検算になる)。

        台帳に出てくる語を全て並べる(**登録表に無い語も 1 行として出す**。外すと合計が
        合わなくなるので、欠けを黙って落とさない)。
        """
        out: list[dict[str, object]] = []
        for status in sorted({r.status for r in self.runs.items}):
            here = [j for j in self.judged if j.run.status == status]
            word = self.words.status_of(status)
            out.append({"status の語": status,
                        "登録表に在るか": "在る" if word else "無い",
                        "意味": word.meaning if word else "",
                        "据え置きを伴うか": word.holds if word else "",
                        "回の数": len(here),
                        "6 値 + 別枠": {k: sum(1 for j in here if j.result == k)
                                        for k in KEKKA}})
        return out

    # ---------------- 一覧

    def listed(self) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for k in KEKKA:
            here = [j for j in self.judged if j.result == k]
            out.append({"判定": k, "件数": len(here),
                        "回": [j.as_dict() for j in here]})
        return out

    def returns(self) -> list[dict[str, object]]:
        """**指紋が履歴の前の回の値へ戻った回**の印つき一覧。良し悪しは書かない。"""
        return [{"実行 id": j.run.run_id, "並び順": j.run.seq, "判定": j.result,
                 "指紋": j.run.fingerprint, "直前の指紋": j.previous,
                 "同じ指紋が前に出た回":
                     [x.run.run_id for x in self.judged
                      if x.run.seq < j.run.seq
                      and x.run.fingerprint == j.run.fingerprint],
                 "出典": j.run.source}
                for j in self.judged if j.returned]

    def no_declaration(self) -> list[dict[str, object]]:
        """② に入った回の一覧(言い方の違いを 3 通りに分けたまま出す)。"""
        return [{"実行 id": j.run.run_id, "並び順": j.run.seq,
                 "status の語": j.run.status,
                 "事前の宣言が無い言い方": j.nashi,
                 "宣言されていた意図コード": j.intent,
                 "出典": j.run.source}
                for j in self.judged if j.result == KEKKA[1]]

    def mismatched(self) -> list[dict[str, object]]:
        """⑥ の一覧。**どちらが正しいかは書かない**(食い違いの形だけ出す)。"""
        return [{"実行 id": j.run.run_id, "並び順": j.run.seq,
                 "差分の件数": j.run.diff_total, "指紋": j.run.fingerprint,
                 "直前の指紋": j.previous,
                 "食い違いの形": ("差分 0 なのに指紋が動いた"
                                  if j.run.diff_total == 0
                                  else "差分ありなのに指紋が同じ"),
                 "履歴の前の回の値へ戻った": "戻り" if j.returned else "",
                 "出典": j.run.source}
                for j in self.judged if j.result == KEKKA[5]]

    def asides(self) -> list[dict[str, object]]:
        """別枠 2 種の一覧。**理由は当てず、出典を必ず付ける。**"""
        return [{"実行 id": j.run.run_id, "並び順": j.run.seq, "判定": j.result,
                 "status の語": j.run.status, "指紋": j.run.fingerprint,
                 "出典": j.run.source}
                for j in self.judged if not j.counted]

    def dangling_intents(self) -> list[dict[str, object]]:
        """台帳に無い実行 id を指す宣言(= 逆向きの欠け)。**止めずに並べる。**"""
        return [{"指している実行 id": x.run_id, "意図コード": x.intent,
                 "宣言の前後": x.declared_before, "出典": x.source}
                for x in self.intents.ordered if self.runs.of(x.run_id) is None]

    def unused_intents(self) -> list[dict[str, object]]:
        """据え置きでない回に付いた宣言(**判定には使わない**ので、使わないまま並べる)。"""
        out: list[dict[str, object]] = []
        for x in self.intents.ordered:
            j = next((y for y in self.judged if y.run.run_id == x.run_id), None)
            if j is None or j.result in (KEKKA[0], KEKKA[1]):
                continue
            out.append({"実行 id": x.run_id, "意図コード": x.intent,
                        "宣言の前後": x.declared_before, "その回の判定": j.result,
                        "出典": x.source})
        return out

    def stopped(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for p in self.report.pending:
            out[p.reason] = out.get(p.reason, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: STOP_REASONS.index(kv[0])))

    # ---------------- まとめ

    def counts(self) -> dict[str, object]:
        """件数を、分母の内訳つきで出す。**割合も点数も順位も返さない。**"""
        six = self.six()
        out: dict[str, object] = {
            "実行の台帳の行数": self.report.runs,
            "意図の宣言表の行数": self.report.intents,
            "語の登録表の行数": self.report.words,
            "分母(実行の件数)": self.run_denominator(),
            "分母(6 値が付いた回の数)": self.counted_denominator,
            "分母(別枠の数)": self.aside_denominator(),
            "分母(台帳に出てくる status 語の数)":
                len({r.status for r in self.runs.items}),
            "6 値 + 別枠": six,
            "履歴の前の回の値へ戻った回": len(self.returns()),
            "事前の宣言が無い据え置きの回": six[KEKKA[1]],
            "噛み合わない回": six[KEKKA[5]],
            "別枠(登録表に無い status 語)": six[KEKKA[6]],
            "別枠(落ちたのに指紋が動いた)": six[KEKKA[7]],
            "台帳に無い実行 id を指す宣言": len(self.dangling_intents()),
            "据え置きでない回に付いた宣言": len(self.unused_intents()),
            "status 語ごと": self.by_status(),
            "理由別の止まった件数": self.stopped(),
            "読んだか": ("読んだ" if self.judged else
                         "読んでいない(仕分ける前に止まったので 6 値は全て 0)"),
        }
        out["分母に含めたもの"] = (
            f"実行の件数 {self.run_denominator()} 回のうち、別枠が "
            f"{self.aside_denominator()} 回で、残る {self.counted_denominator} 回に "
            "6 値が付く。内訳は " + " + ".join(f"{k} {six[k]}" for k in MUTSU))
        out["件数の合計の検算"] = (
            f"6 値 + 別枠の合計 {sum(six.values())} / 実行の件数 "
            f"{self.run_denominator()}(6 値 {sum(six[k] for k in MUTSU)} = "
            f"{self.counted_denominator} も同じ、status 語ごとの内訳の合計 "
            f"{sum(int(r['回の数']) for r in self.by_status())} = 実行の件数 も同じ)")
        out["成功率も稼働率も出さない"] = (
            "返るのは件数と内訳だけで、割合にする経路も option も無い。分母をこの部品が"
            "決めない(通ったと宣言された回の中に、初回と、何も変わらなかった回が混ざるので、"
            "割ると何を言っている数字か分からなくなる)")
        out["失敗の原因を分類しない"] = (
            "入力に error の列が無く、本文を読む経路も無い。落ちたと宣言された回に付くのは"
            "据え置きの有無と、事前の宣言が在るかだけ")
        out["事後の申告を試験として数えない"] = (
            "試験として数えるのは、意味が 試験 として登録された意図コードが 実行より前 と"
            "宣言された回だけ。宣言が実行より後の回は、宣言が無い回と同じ値に落ちる(言い方"
            "の違いは一覧に残す)")
        out["実行を障害と呼ばない"] = (
            "出力に障害・異常・事故の語が無い。落ちた回は「落ちたと宣言され、据え置きに"
            "なった回」としか書かない")
        out["鮮度も次回も出さない"] = (
            "入力に日付の列も時刻の列も無く、現在時刻を読む呼び出しも持たない。最終更新日・"
            "鮮度・次に動く日はこの部品の外にある")
        out["差分の中身を見ない"] = (
            "読むのは件数 3 つと指紋だけ。どの行がどう変わったかの列が無く、開く経路も無い")
        out["再実行しない・取りに行かない"] = (
            "走らせる経路も、通信の経路も無い。読むのは手元の 3 枚だけ")
        out["良し悪しも順位も出さない"] = (
            "点数欄も順位欄も推奨欄も無い。どの回を調べるかは台帳を持つ人が決める")
        out["入力を書き換えない"] = (
            "verify が作る写し(宣言を 1 件外した表・指紋を 1 つ書き換えた表)はメモリの"
            "中だけで、入力の CSV には 1 文字も書かない")
        return out

    def judgement_bytes(self) -> bytes:
        """判定部分 = 回ごとの値と指紋の動き。時刻・絶対パスは入れない。"""
        self._guard()
        lines = ["\t".join(["件", str(self.report.runs), str(self.report.intents),
                            str(self.report.words)])]
        lines.extend(j.line() for j in self.judged)
        return ("\n".join(lines) + "\n").encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.judgement_bytes()).hexdigest()

    def read_condition(self) -> dict[str, str]:
        return {SCOPE_KEYS[0]: self.runs.path, SCOPE_KEYS[1]: self.intents.path,
                SCOPE_KEYS[2]: self.words.path}

    def _guard(self) -> None:
        if not self.report.ok:
            raise RuntimeError("止まっているので仕分けた回は無い。"
                               "report.pending の理由コードを見る")


def run_kinds(runs: Runs, intents: Intents, words: Words) -> Tally:
    """実行 1 回ごとに 6 値 + 別枠を付ける。

    3 枚のどれかが 1 行でも壊れていたら 1 回も数えない(6 値は全て 0)。
    """
    pending = list(runs.pending) + list(intents.pending) + list(words.pending)
    pending.extend(runs.issues(words))
    pending.extend(intents.issues(words))
    judged: list[Judged] = []
    previous = ""
    history: list[str] = []
    for run in runs.ordered:
        word = words.status_of(run.status)
        if word is not None and not word.holding and not run.first and not previous:
            pending.append(Pending(STOP_REASONS[8],
                                   f"実行の台帳 行 {run.number}({run.run_id})"))
        judged.append(judge(run, words, intents, previous, tuple(history[:-1])))
        if run.fingerprint:
            history.append(run.fingerprint)
            previous = run.fingerprint
    report = Report(not pending, tuple(pending), len(runs.items),
                    len(intents.items), len(words.items))
    if pending:                 # 1 回も数えずに止まる
        return Tally(report=report, judged=(), runs=runs, intents=intents,
                     words=words)
    return Tally(report=report, judged=tuple(judged), runs=runs, intents=intents,
                 words=words)


# ------------------------------------------------------------ verify


def moved_elsewhere(first: Tally, after: Tally, *keep: str) -> list[str]:
    """判定が動いた回のうち、動くはずだった回でないものの実行 id。

    見るのは判定(値・戻りの印・言い方)だけで、**直前の指紋が何だったかは見ない**。
    1 つ前の回の指紋を書き換えると、次の回が比べる相手の値は当然変わるが、それで判定が
    変わっていないなら「動いていない」と数える。
    """
    was = {j.run.run_id: j.verdict() for j in first.judged}
    return sorted(j.run.run_id for j in after.judged
                  if j.verdict() != was.get(j.run.run_id)
                  and j.run.run_id not in keep)


def test_probe_plan(first: Tally) -> list[Judged]:
    """試験の宣言を 1 件外す計画(① に入っている回だけを選ぶ)。"""
    return [j for j in first.judged if j.result == KEKKA[0]]


def test_probe(runs: Runs, intents: Intents, words: Words,
               first: Tally) -> dict[str, object]:
    """試験の宣言を 1 件外して数え直す。

    いつも成り立つはずのこと: **その回だけが ① から ② へ移り(言い方は「宣言そのものが
    無い」)、ほかの回の判定は 1 つも動かない**。合計も指紋の動きも変わらない。
    """
    rows: list[dict[str, object]] = []
    plans = test_probe_plan(first)
    ok = bool(plans)
    before = first.six()
    for j in plans:
        after = run_kinds(runs, intents.without(j.run.run_id), words)
        now = after.six()
        mine = next((x for x in after.judged if x.run.run_id == j.run.run_id), None)
        fits = (after.report.ok and mine is not None
                and mine.result == KEKKA[1]
                and mine.nashi == NASHI_KINDS[0]
                and now[KEKKA[0]] == before[KEKKA[0]] - 1
                and now[KEKKA[1]] == before[KEKKA[1]] + 1
                and all(now[k] == before[k] for k in KEKKA
                        if k not in (KEKKA[0], KEKKA[1]))
                and moved_elsewhere(first, after, j.run.run_id) == []
                and after.run_denominator() == first.run_denominator())
        ok = ok and fits
        rows.append({"外した宣言": f"{j.run.run_id} の {j.intent}",
                     KEKKA[0]: f"{before[KEKKA[0]]} → {now[KEKKA[0]]}",
                     KEKKA[1]: f"{before[KEKKA[1]]} → {now[KEKKA[1]]}",
                     "移った先の言い方": mine.nashi if mine else "",
                     "ほかで動いた回": moved_elsewhere(first, after, j.run.run_id),
                     "合うか": fits})
    return {"書き換えた欄": "意図の宣言表 1 行(写しはメモリの中だけ)",
            "分母(実行の件数)": first.run_denominator(), "回ごと": rows, "合うか": ok,
            "読み": ("試験の宣言を外すと、その回だけが ① から ② へ移る。事前の宣言が"
                     "在るかどうかだけで ① と ② が分かれていることが、ここで数として出る")}


NEW_FINGERPRINT = "合成の書き換えた指紋(架空)"     # 履歴に出てこない値(入力には書かない)


def repaint_probe_plan(first: Tally) -> list[Judged]:
    """「差分 0 かつ指紋が直前と同じ」の回の指紋を書き換える計画。

    その指紋を直前として見ている後ろの回が、書き換えで動かないものだけを選ぶ。
    **④ が 2 回続く台帳では次の回も動くので、そこは計画から外して正直に数える。**
    """
    out: list[Judged] = []
    for j in first.judged:
        if j.result != KEKKA[3]:
            continue
        later = [x for x in first.judged
                 if x.run.seq > j.run.seq and x.run.fingerprint]
        nxt = next((x for x in later if x.previous == j.run.fingerprint), None)
        if nxt is None or nxt.result == KEKKA[4]:
            out.append(j)
    return out


def repaint_probe(runs: Runs, intents: Intents, words: Words,
                  first: Tally) -> dict[str, object]:
    """「差分 0 かつ指紋が直前と同じ」の回の指紋を、履歴に無い値へ書き換えて数え直す。

    いつも成り立つはずのこと: **その回が ④ から ⑥ へ移り、「戻り」の印は付かず、6 値 + 別枠の
    合計は変わらない**(書き換えで戻りの印が増えることもない)。
    """
    rows: list[dict[str, object]] = []
    plans = repaint_probe_plan(first)
    ok = bool(plans)
    before = first.six()
    before_returns = {j.run.run_id for j in first.judged if j.returned}
    for j in plans:
        after = run_kinds(runs.repainted(j.run.run_id, NEW_FINGERPRINT), intents,
                          words)
        now = after.six()
        mine = next((x for x in after.judged if x.run.run_id == j.run.run_id), None)
        now_returns = {x.run.run_id for x in after.judged if x.returned}
        fits = (after.report.ok and mine is not None
                and mine.result == KEKKA[5]
                and mine.returned is False
                and now[KEKKA[3]] == before[KEKKA[3]] - 1
                and now[KEKKA[5]] == before[KEKKA[5]] + 1
                and all(now[k] == before[k] for k in KEKKA
                        if k not in (KEKKA[3], KEKKA[5]))
                and sum(now.values()) == sum(before.values())
                and now_returns <= before_returns
                and moved_elsewhere(first, after, j.run.run_id) == []
                and after.run_denominator() == first.run_denominator())
        ok = ok and fits
        rows.append({"書き換えた回": j.run.run_id,
                     "元の指紋": j.run.fingerprint,
                     KEKKA[3]: f"{before[KEKKA[3]]} → {now[KEKKA[3]]}",
                     KEKKA[5]: f"{before[KEKKA[5]]} → {now[KEKKA[5]]}",
                     "戻りの印": "付かない" if mine and not mine.returned else "付いた",
                     "戻りの回の数": f"{len(before_returns)} → {len(now_returns)}",
                     "ほかで動いた回": moved_elsewhere(first, after, j.run.run_id),
                     "合うか": fits})
    return {"書き換えた欄": "実行の台帳の指紋 1 つ(写しはメモリの中だけ)",
            "分母(実行の件数)": first.run_denominator(), "回ごと": rows, "合うか": ok,
            "読み": ("差分の件数を触らずに指紋だけ動かすと、その回は ④ から ⑥ へ移る。"
                     "差分と指紋を別の欄として読んでいることが、ここで数として出る")}


def verify(runs: Runs, intents: Intents, words: Words) -> dict[str, object]:
    """2 回読んで sha256 を比べ、3 枚の行順を 3 通りに入れ替えても同じかを見て、件数を検算し、
    さらに宣言を 1 件外した写しと、指紋を 1 つ書き換えた写しを読んで差分を出す。"""
    first = run_kinds(runs, intents, words)
    if not first.report.ok:
        return {"ok": False, "stage": "止まった(仕分けた回は返さない)",
                **first.counts(),
                "pending": [p.as_dict() for p in first.report.pending]}
    second = run_kinds(runs, intents, words)
    pending: list[Pending] = []
    if first.sha256() != second.sha256():
        pending.append(Pending(STOP_REASONS[10], f"2 回目 {second.sha256()[:12]}"))
    swapped: dict[str, str] = {}
    for how in SWAPS:
        third = run_kinds(runs.swapped(how), intents.swapped(how),
                          words.swapped(how))
        swapped[how] = third.sha256() if third.report.ok else ""
        if not (third.report.ok and first.sha256() == third.sha256()):
            pending.append(Pending(STOP_REASONS[11],
                                   f"入れ替え方 {how} で "
                                   f"{swapped[how] or '止まった'}"))
    six = first.six()
    if sum(six.values()) != first.run_denominator():
        pending.append(Pending(STOP_REASONS[9],
                               f"6 値 + 別枠の合計 {sum(six.values())} / 実行の件数 "
                               f"{first.run_denominator()}"))
    inner = sum(six[k] for k in MUTSU)
    if inner != first.counted_denominator:
        pending.append(Pending(STOP_REASONS[9],
                               f"6 値 {inner} / 6 値が付いた回 "
                               f"{first.counted_denominator}"))
    by_status = sum(int(r["回の数"]) for r in first.by_status())
    if by_status != first.run_denominator():
        pending.append(Pending(STOP_REASONS[9],
                               f"status 語ごとの内訳の合計 {by_status} / 実行の件数 "
                               f"{first.run_denominator()}"))
    for k in KEKKA:
        inner_k = sum(int(r["6 値 + 別枠"][k]) for r in first.by_status())
        if inner_k != six[k]:
            pending.append(Pending(STOP_REASONS[9],
                                   f"status 語ごとの {k} の合計 {inner_k} / {six[k]}"))
    out: dict[str, object] = {
        "ok": not pending, "読んだ回数": 2, "入れ替え方": list(SWAPS),
        "sha256": first.sha256(), "2 回目の sha256": second.sha256(),
        "入れ替えた 3 枚の sha256": swapped,
        "件数の検算": {"6 値 + 別枠": six, "合計": sum(six.values()), "6 値": inner,
                       "status 語ごとの内訳の合計": by_status,
                       "分母(実行の件数)": first.run_denominator(),
                       "分母(6 値が付いた回の数)": first.counted_denominator,
                       "分母(別枠の数)": first.aside_denominator(),
                       "履歴の前の回の値へ戻った回": len(first.returns())},
        "試験の宣言を 1 件外した写し": test_probe(runs, intents, words, first),
        "指紋を 1 つ書き換えた写し": repaint_probe(runs, intents, words, first),
    }
    for key in ("試験の宣言を 1 件外した写し", "指紋を 1 つ書き換えた写し"):
        if not out[key]["合うか"]:        # type: ignore[index]
            pending.append(Pending(STOP_REASONS[9], f"{key} の件数が合わない"))
            out["ok"] = False
    if pending:
        out["観測"] = ("同じ表から違うバイト列が出た、または件数が合わない(平均も多数決も"
                       "しない。落ちた理由も当てない)")
        out["pending"] = [p.as_dict() for p in pending]
    return out


# ------------------------------------------------------------ ひな型

T_SRC = "合成の実行の記録(架空)L1"
T_PLAN = "合成の計画の記録(架空)L1"
T_WORD = "合成の登録の記録(架空)L1"
T_FP1 = "合成の指紋 1(架空)"
T_FP2 = "合成の指紋 2(架空)"

TEMPLATE_RUNS = [
    list(RUNS_COLUMNS),
    ["R01", "1", "ok", "9", "0", "0", SHOKAI, T_FP1, T_SRC],
    ["R02", "2", "ok", "0", "0", "0", "", T_FP1, T_SRC],
    ["R03", "3", "failed", "0", "0", "0", "", "", T_SRC],
    ["R04", "4", "ok", "2", "0", "1", "", T_FP2, T_SRC],
]
TEMPLATE_INTENTS = [
    list(INTENT_COLUMNS),
    ["R03", "失敗試験", MAE, T_PLAN],
]
TEMPLATE_WORDS = [
    list(WORDS_COLUMNS),
    ["ok", TOTTA, SUEOKANAI, T_WORD],
    ["failed", OCHITA, SUEOKI, T_WORD],
    ["失敗試験", SHIKEN, SUEOKI, T_WORD],
]


def write_csv(path: Path, rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    return path


def init(dest: str | Path) -> tuple[Path, Path, Path]:
    d = Path(dest)
    return (write_csv(d / "実行の台帳.csv", TEMPLATE_RUNS),
            write_csv(d / "意図の宣言表.csv", TEMPLATE_INTENTS),
            write_csv(d / "語の登録表.csv", TEMPLATE_WORDS))


# ------------------------------------------------------------ CLI

def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def build_parser() -> argparse.ArgumentParser:
    """CLI は kinds / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = argparse.ArgumentParser(prog="run_kinds",
                                 description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in SUBCOMMANDS[:3]:
        p = sub.add_parser(name)
        p.add_argument("runs")
        p.add_argument("intents")
        p.add_argument("words")
    sub.add_parser(SUBCOMMANDS[3]).add_argument("dest")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == "init":
        print("書いた: " + " / ".join(str(p) for p in init(a.dest)))
        return 0
    try:
        runs, intents = Runs.load(a.runs), Intents.load(a.intents)
        words = Words.load(a.words)
        if a.cmd == "verify":
            out = verify(runs, intents, words)
            _print(out)
            return 0 if out["ok"] else 3
        t = run_kinds(runs, intents, words)
    except ReadError as e:
        print(f"表として読めない: {e}", file=sys.stderr)
        return 2
    if not t.report.ok:
        _print({"ok": False, "stage": "止まった(仕分けた回は返さない)", **t.counts(),
                "pending": [p.as_dict() for p in t.report.pending]})
        return 3
    body: dict[str, object] = {"ok": True, **t.counts()}
    if a.cmd == SUBCOMMANDS[0]:
        body["判定ごとの一覧"] = t.listed()
        body["履歴の前の回の値へ戻った回の一覧"] = t.returns()
        body["事前の宣言が無い据え置きの回の一覧"] = t.no_declaration()
        body["噛み合わない回の一覧"] = t.mismatched()
        body["別枠の一覧"] = t.asides()
        body["台帳に無い実行 id を指す宣言の一覧"] = t.dangling_intents()
        body["据え置きでない回に付いた宣言の一覧"] = t.unused_intents()
        body["sha256"] = t.sha256()
        body["読んだ条件"] = t.read_condition()
    _print(body)
    six = t.six()
    clean = (t.aside_denominator() == 0 and six[KEKKA[5]] == 0
             and six[KEKKA[1]] == 0 and not t.dangling_intents()
             and not t.stopped())
    return 0 if clean else 3


if __name__ == "__main__":
    raise SystemExit(main())
