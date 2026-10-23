"""handoff_edge — 求める値ごとに、道具の中で済む節と、外に残る一手を分ける。値を計算せず、
宣言を突き合わせて数えるだけ。

**値が返ってきたことと、その値で計算が終わっていることは別。行が無ければ例外で止まるが、式の
節が未実装のときは値がそのまま返り、仕上げの一手だけが呼び出し側に残る。設計上そもそも表の外に
置いたもの(人の判断・事業所固有の値・履歴の走査)も返り値には現れない。だから引く前に、求める
値ごとに「道具の中で済む」「返るが一手残る」「外から渡す前提」「止まる」の 4 つを境界の表 1 枚に
して、線の外に何が在るかを数える。**

この部品は、守備範囲の宣言表・計算のレシピ表・問いの一覧の 3 枚から、問い(= 求める値)1 つごと
に 5 値(**道具の中で済む / 返るが一手残る / 外から渡す前提 / 止まる / 宣言が無い**)を付ける。
最後の 1 つが別枠で、宣言表に無い節を参照していた問いがここに出る。節ごとの内訳と、残る一手の
一覧(名前と出典)も返す。**値を計算しない。数えるだけだ。**

持たせていないものが規律になっている。

  - **宣言表に無い節は判定しない**(収録済を既定として当てる経路が無い。別枠に出す)
  - **「止まる」と「値が返る」を同じ出口に潰さない**(終了コードを返す経路を持たない)
  - **`未実装` と `設計上の外` を同じに数えない**(線の内側の未完成と、線の外に置いた設計判断を
    別の列にする)
  - **残る一手を道具側で埋めない・提案しない**(上限を当てる引数も、代わりの式を選ぶ経路も、
    足すべき節を出す経路も無い)
  - **残る一手の名前が空の行は止まる**(状態だけ書いて何が残るかを書かない行を通さない)
  - **出典の欄が空の行は止まる**
  - **値を計算しない・式を評価しない・行を実際に引かない**
  - **端が仮置きかどうかは扱わない**(確度の欄も日付の欄も持たない)
  - **完成度の割合を出さない**(件数と 2 つの分母の内訳だけを返す)
  - **この部品自身の「読めない」を、測っている相手の「止まる」と同じ欄に入れない**(宣言表が
    壊れていたら 1 件も判定しないで理由コードを返す。相手の出口の話と混ぜない)
  - **入力表を書き換えず、節も宣言も生成しない**
  - **同じ入力には同じバイト列**(判定部分に時刻・絶対パス・ホスト名を入れない)
  - **数は整数だけ**(float を使う経路が無い)

入力は 3 つ。守備範囲の宣言表(CSV)、計算のレシピ表(CSV)、問いの一覧(CSV)。

守備範囲の宣言表の列は 6 つ。1 節が 1 行。

    node_id         節 id(空欄は「表として読めない」。2 行あると止まる)
    belongs_to      その節が属する rule または式 id。**空欄のまま持つ**(数える段で止まる)
    state           節の状態。登録の 4 種(収録済 / 未実装 / 未対応 / 設計上の外)
    exit            出口。登録の 2 種(値が返る / 止まる)
    remaining_step  呼び出し側に残る一手の名前。収録済以外は要る。収録済は空欄
    source          出典。空欄は止まる

計算のレシピ表の列は 3 つ。求める値 1 つが 1 行。

    value_id   求める値 id(空欄も、同じ id が 2 行あるのも「表として読めない」)
    node_ids   その値に要る節 id を `|` でつなぐ。**空欄のまま持つ**(数える段で止まる)
    source     出典。空欄は止まる

問いの一覧の列は 3 つ。問い 1 つが 1 行。

    value_id   訊く求める値 id(レシピ表に無い id は「表として読めない」)
    source     出典。空欄は止まる
    swap       入れ替え方。verify が 3 枚の行順を入れ替えるときの宣言

使い方:

    python handoff_edge.py init ひな型/
    python handoff_edge.py check  守備範囲の宣言表.csv 計算のレシピ表.csv 問いの一覧.csv
    python handoff_edge.py edge   守備範囲の宣言表.csv 計算のレシピ表.csv 問いの一覧.csv
    python handoff_edge.py verify 守備範囲の宣言表.csv 計算のレシピ表.csv 問いの一覧.csv

終了コードは、全部の問いが道具の中で済むときだけ 0、一手が残る問いか別枠があるときは 3、表として
読めなければ 2。**測っている相手の出口をこの終了コードに写さない**(相手の 4 値は本文の欄に出す)。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

SYUUBI_COLUMNS = ("node_id", "belongs_to", "state", "exit", "remaining_step", "source")
RECIPE_COLUMNS = ("value_id", "node_ids", "source")
TOI_COLUMNS = ("value_id", "source", "swap")

# 節の状態(登録制)。既定は持たない = 空欄を収録済と読み替える経路が無い
STATES = ("収録済", "未実装", "未対応", "設計上の外")
# 出口(登録制)。2 つを 1 つの終了コードに潰さない
EXITS = ("値が返る", "止まる")
SWAPS = ("逆順", "両端入れ替え", "1 つずらす")

# 問い 1 つに付く 5 値。最後の 1 つが別枠。5 つを混ぜない。
# 前の 4 つは節 1 つの判定にも同じ名前で使う(節の判定を集めて問いの 1 値にする)
RESULTS = ("道具の中で済む", "返るが一手残る", "外から渡す前提", "止まる", "宣言が無い")
ASIDE = RESULTS[4]
NODE_VERDICTS = RESULTS[:4]

# 裁定の順(手前の関門が勝つ)。**順番そのものが仕様**で、入れ替えない。
#   宣言が無い     … そもそも判定できない(既定を当てない)
#   止まる         … 値が 1 つも返らない。いちばん強い言い方なので先に出す
#   外から渡す前提 … 呼ぶ前に外から渡しておく一手。時間の順で手前
#   返るが一手残る … 値が返った後に残る一手
#   道具の中で済む … 残る一手が無い
ORDER = (RESULTS[4], RESULTS[3], RESULTS[2], RESULTS[1], RESULTS[0])

STOP_REASONS = (
    # 1 件も判定せずに止まる(11)
    "出典の欄が空", "節 id の重複", "レシピに節 id が 1 つも無い",
    "節の状態が空", "登録されていない節の状態", "出口が空", "登録されていない出口",
    "残る一手の名前が空", "収録済なのに残る一手が書いてある", "収録済なのに出口が止まる",
    "属する rule も式 id も空",
    # verify が見つける(3)
    "件数の合計が合わない", "2 回目の判定部分が不一致", "行順を入れ替えた表で出力が変わる",
)
TABLE_REASONS = STOP_REASONS[:11]
VERIFY_REASONS = STOP_REASONS[11:]

SUBCOMMANDS = ("edge", "check", "verify", "init")
SCOPE_KEYS = ("読んだ宣言表の絶対パス", "読んだレシピ表の絶対パス", "読んだ問いの一覧の絶対パス")

ID = re.compile(r"\A[A-Za-z0-9_\-]+\Z")


class ReadError(Exception):
    """表として読めない(終了コード 2)。判定した問いは 1 件も返さない。"""


@dataclass(frozen=True)
class Pending:
    reason: str
    detail: str = ""

    def as_dict(self) -> dict[str, str]:
        return {"理由コード": self.reason, "どこ": self.detail}


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


# ------------------------------------------------------------ 守備範囲の宣言表


@dataclass(frozen=True)
class Node:
    """節 1 つの宣言。状態も出口も**読めないまま持つ**(直せるものを直さない代わりに、
    数える段で理由コードにする)。"""
    node_id: str
    belongs_to: str
    state: str
    exit_kind: str
    remaining_step: str
    source: str
    number: int = 0

    @property
    def recorded(self) -> bool:
        return self.state == STATES[0]

    @property
    def returns(self) -> bool:
        return self.exit_kind == EXITS[0]

    def issues(self) -> tuple[Pending, ...]:
        """この節の宣言そのものの不備。1 件でもあると、どの問いも判定しない。"""
        where = f"宣言表 行 {self.number}({self.node_id})"
        out: list[Pending] = []
        if not self.belongs_to:
            out.append(Pending(STOP_REASONS[10], where))
        if not self.state:
            out.append(Pending(STOP_REASONS[3], where))
        elif self.state not in STATES:
            out.append(Pending(STOP_REASONS[4], f"{where}: {self.state}"))
        if not self.exit_kind:
            out.append(Pending(STOP_REASONS[5], where))
        elif self.exit_kind not in EXITS:
            out.append(Pending(STOP_REASONS[6], f"{where}: {self.exit_kind}"))
        if self.state in STATES[1:] and not self.remaining_step:
            out.append(Pending(STOP_REASONS[7], f"{where}: 状態は {self.state}"))
        if self.recorded and self.remaining_step:
            out.append(Pending(STOP_REASONS[8], f"{where}: {self.remaining_step}"))
        if self.recorded and self.exit_kind == EXITS[1]:
            out.append(Pending(STOP_REASONS[9], where))
        return tuple(out)

    def verdict(self) -> str:
        """節 1 つの判定。不備が無いことを確かめた後に呼ぶ。

        収録済で値が返る → 道具の中で済む / 出口が止まる → 止まる /
        設計上の外で値が返る → 外から渡す前提 / 未実装・未対応で値が返る → 返るが一手残る。
        **未実装と設計上の外を同じ列に入れない。**
        """
        if self.issues():
            raise RuntimeError("不備のある節の判定を取りに行った(issues を先に見る)")
        if not self.returns:
            return RESULTS[3]
        if self.recorded:
            return RESULTS[0]
        if self.state == STATES[3]:
            return RESULTS[2]
        return RESULTS[1]

    def as_recorded(self) -> "Node":
        """状態を「未実装」から「収録済」に替えた写し(verify が使う。入力には書かない)。

        替えるのは **未実装で、いま値が返っている節だけ**。出口が「止まる」の節まで一緒に
        替えると、止まる → 道具の中で済む という 2 段の飛びが混ざって「残る一手が 1 つ消えた
        分だけ中で済むが増えた」という読みにならないので、そこは替えない。
        """
        if self.state != STATES[1] or not self.returns:
            return self
        return Node(**{**self.__dict__, "state": STATES[0], "exit_kind": EXITS[0],
                       "remaining_step": ""})


@dataclass(frozen=True)
class Boundary:
    items: tuple[Node, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Boundary":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"守備範囲の宣言表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Boundary":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in SYUUBI_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("守備範囲の宣言表に " + " / ".join(lack) + " の列が無い")
        items: list[Node] = []
        pending: list[Pending] = []
        seen: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in SYUUBI_COLUMNS}
            where = f"守備範囲の宣言表 行 {i}"
            if not cell["node_id"]:
                raise ReadError(f"{where}: 節 id が空欄")
            if not ID.match(cell["node_id"]):
                raise ReadError(f"{where}: 節 id は英数字と - _ だけ({cell['node_id']})")
            if cell["node_id"] in seen:
                pending.append(Pending(STOP_REASONS[1], f"{where}: {cell['node_id']}"))
            seen.add(cell["node_id"])
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0], f"{where}({cell['node_id']})"))
            items.append(Node(node_id=cell["node_id"], belongs_to=cell["belongs_to"],
                              state=cell["state"], exit_kind=cell["exit"],
                              remaining_step=cell["remaining_step"],
                              source=cell["source"], number=i))
        if not items:
            raise ReadError("守備範囲の宣言表に行が無い(ヘッダだけ)")
        for n in items:
            pending.extend(n.issues())
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    def of(self, node_id: str) -> Node | None:
        return next((n for n in self.items if n.node_id == node_id), None)

    @property
    def ordered(self) -> tuple[Node, ...]:
        return tuple(sorted(self.items, key=lambda n: n.node_id))

    def swapped(self, how: str) -> "Boundary":
        return Boundary(items=tuple(swap_rows(list(self.items), how)),
                        pending=self.pending, path=self.path)

    def filled(self, node_id: str) -> "Boundary":
        """節 1 つの状態を 未実装 → 収録済 に替えた写し。"""
        return Boundary(items=tuple(n.as_recorded() if n.node_id == node_id else n
                                    for n in self.items),
                        pending=self.pending, path=self.path)

    def all_filled(self) -> "Boundary":
        """未実装で値が返っている節を全部 収録済 に替えた写し。"""
        return Boundary(items=tuple(n.as_recorded() for n in self.items),
                        pending=self.pending, path=self.path)

    def without(self, node_id: str) -> "Boundary":
        """節 1 つを宣言表から外した写し(= 宣言が無い状態を作る)。"""
        rest = tuple(n for n in self.items if n.node_id != node_id)
        if not rest:
            return self
        return Boundary(items=rest, pending=self.pending, path=self.path)

    def by_state(self) -> dict[str, int]:
        """状態別の節の数(宣言の順)。未実装と設計上の外を同じに数えない。"""
        return {s: sum(1 for n in self.items if n.state == s) for s in STATES}


# ------------------------------------------------------------ 計算のレシピ表


@dataclass(frozen=True)
class Recipe:
    value_id: str
    node_ids: tuple[str, ...]
    source: str
    number: int = 0


@dataclass(frozen=True)
class Recipes:
    items: tuple[Recipe, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Recipes":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"計算のレシピ表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Recipes":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in RECIPE_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("計算のレシピ表に " + " / ".join(lack) + " の列が無い")
        items: list[Recipe] = []
        pending: list[Pending] = []
        seen: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in RECIPE_COLUMNS}
            where = f"計算のレシピ表 行 {i}"
            if not cell["value_id"]:
                raise ReadError(f"{where}: 求める値 id が空欄")
            if cell["value_id"] in seen:
                raise ReadError(f"{where}: 求める値 id が 2 行ある({cell['value_id']})")
            seen.add(cell["value_id"])
            ids = tuple(x.strip() for x in cell["node_ids"].split("|") if x.strip())
            if len(set(ids)) != len(ids):
                raise ReadError(f"{where}: 同じ節 id を 2 回参照している({cell['node_ids']})")
            if not ids:
                pending.append(Pending(STOP_REASONS[2], f"{where}({cell['value_id']})"))
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0], f"{where}({cell['value_id']})"))
            items.append(Recipe(value_id=cell["value_id"], node_ids=ids,
                                source=cell["source"], number=i))
        if not items:
            raise ReadError("計算のレシピ表に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    def of(self, value_id: str) -> Recipe | None:
        return next((r for r in self.items if r.value_id == value_id), None)

    @property
    def ordered(self) -> tuple[Recipe, ...]:
        return tuple(sorted(self.items, key=lambda r: r.value_id))

    def swapped(self, how: str) -> "Recipes":
        return Recipes(items=tuple(swap_rows(list(self.items), how)),
                       pending=self.pending, path=self.path)


# ------------------------------------------------------------ 問いの一覧


@dataclass(frozen=True)
class Question:
    value_id: str
    source: str
    number: int = 0


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
        pending: list[Pending] = []
        seen: set[str] = set()
        swaps: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in TOI_COLUMNS}
            where = f"問いの一覧 行 {i}"
            if not cell["value_id"]:
                raise ReadError(f"{where}: 求める値 id が空欄")
            if cell["value_id"] in seen:
                raise ReadError(f"{where}: 同じ問いが 2 行ある({cell['value_id']})")
            seen.add(cell["value_id"])
            if cell["swap"]:
                swaps.add(cell["swap"])
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0], f"{where}({cell['value_id']})"))
            items.append(Question(value_id=cell["value_id"], source=cell["source"],
                                  number=i))
        if not items:
            raise ReadError("問いの一覧に行が無い(ヘッダだけ)")
        if len(swaps) > 1:
            raise ReadError("入れ替え方の宣言が 2 通りある: " + " / ".join(sorted(swaps)))
        how = swaps.pop() if swaps else ""
        if how and how not in SWAPS:
            raise ReadError(f"登録されていない入れ替え方: {how}")
        return cls(items=tuple(items), pending=tuple(pending), swap=how, path=path)

    @property
    def ordered(self) -> tuple[Question, ...]:
        return tuple(sorted(self.items, key=lambda q: q.value_id))

    def swapped(self, how: str) -> "Questions":
        return Questions(items=tuple(swap_rows(list(self.items), how)),
                         pending=self.pending, swap=self.swap, path=self.path)


# ------------------------------------------------------------ 数える


@dataclass(frozen=True)
class Asked:
    value_id: str
    result: str
    nodes: tuple[tuple[str, str], ...] = ()       # (節 id, 4 値のどれか)
    missing: tuple[str, ...] = ()                 # 宣言表に無かった節 id
    steps: tuple[tuple[str, str, str], ...] = ()  # (節 id, 状態, 残る一手の名前)

    def line(self) -> str:
        return "|".join(f"{n}={v}" for n, v in self.nodes) or \
               "宣言が無い:" + ",".join(self.missing)


def judge(recipe: Recipe, boundary: Boundary) -> Asked:
    """問い 1 つに 5 値のどれか 1 つを付ける。5 つを混ぜない。

    **宣言表に無い節が 1 つでもあれば別枠**(残りの節に収録済を当てて判定しない)。
    それ以外は節の判定を集めて、裁定の順(ORDER)でいちばん手前の 1 値を返す。
    """
    missing = tuple(n for n in sorted(recipe.node_ids) if boundary.of(n) is None)
    if missing:
        return Asked(value_id=recipe.value_id, result=ASIDE, missing=missing)
    nodes = tuple((n, boundary.of(n).verdict()) for n in sorted(recipe.node_ids))
    steps = tuple((n, boundary.of(n).state, boundary.of(n).remaining_step)
                  for n, v in nodes if v != RESULTS[0])
    found = {v for _, v in nodes}
    result = next(r for r in ORDER if r in found or r == RESULTS[0])
    return Asked(value_id=recipe.value_id, result=result, nodes=nodes, steps=steps)


@dataclass(frozen=True)
class Report:
    ok: bool
    pending: tuple[Pending, ...]
    nodes: int
    recipes: int
    questions: int


@dataclass(frozen=True)
class Tally:
    report: Report
    asked: tuple[Asked, ...]
    boundary: Boundary
    recipes: Recipes
    questions: Questions

    def by_result(self, result: str) -> tuple[Asked, ...]:
        return tuple(a for a in self.asked if a.result == result)

    @property
    def verdict(self) -> str:
        """全体の読み。裁定の順でいちばん手前に在る値を返す。"""
        self._guard()
        for r in ORDER:
            if self.by_result(r):
                return r
        return RESULTS[0]

    @property
    def denominator(self) -> int:
        return self.report.questions

    @property
    def node_denominator(self) -> int:
        """節ごとの分母 = 問いが要る節の延べ数(問いごとに要る節の数が違うので掛け算にしない)。"""
        return sum(len(self.recipes.of(q.value_id).node_ids)
                   for q in self.questions.items)

    def counted_nodes(self) -> int:
        """判定した節の延べ数(別枠の問いの節は数えない)。"""
        return sum(len(a.nodes) for a in self.asked)

    def by_node_verdict(self) -> dict[str, int]:
        """節の判定別の件数(延べ数。4 つを 1 つに潰さない)。"""
        return {v: sum(1 for a in self.asked for _, x in a.nodes if x == v)
                for v in NODE_VERDICTS}

    def remaining(self) -> list[dict[str, str]]:
        """残る一手の一覧。名前と出典をそのまま返す(埋めない・提案しない)。"""
        out: list[dict[str, str]] = []
        for a in self.asked:
            for node_id, state, step in a.steps:
                node = self.boundary.of(node_id)
                out.append({"求める値": a.value_id, "節": node_id, "状態": state,
                            "残る一手": step, "出典": node.source if node else ""})
        return out

    def counts(self) -> dict[str, object]:
        """件数は丸めず、2 つの分母と内訳つきで出す。割合は返さない。"""
        five = {r: len(self.by_result(r)) for r in RESULTS}
        node = self.by_node_verdict()
        out: dict[str, object] = {
            "守備範囲の宣言表の行数(節の数)": self.report.nodes,
            "計算のレシピ表の行数(求める値の数)": self.report.recipes,
            "問いの数": self.report.questions,
            "分母(問いの数)": self.denominator,
            "5 値": five,
            "節の判定別(延べ数)": node,
            "節の状態別(宣言表の行数)": self.boundary.by_state(),
            "読んだか": ("読んだ" if self.asked else
                         "読んでいない(宣言表が揃う前に止まったので 5 値は全て 0)"),
        }
        out["分母に含めたもの"] = (
            f"問いの数 {self.denominator} 件。5 値の内訳は 道具の中で済む"
            f" {five[RESULTS[0]]} + 返るが一手残る {five[RESULTS[1]]}"
            f" + 外から渡す前提 {five[RESULTS[2]]} + 止まる {five[RESULTS[3]]}"
            f" + 宣言が無い {five[ASIDE]}。節の判定別の分母は別で、問いが要る節の延べ数"
            f" {self.node_denominator} 件のうち判定した {self.counted_nodes()} 件"
            f"(別枠の問いの節は数えない)")
        out["件数の合計の検算"] = (
            f"5 値の合計 {sum(five.values())} / 分母 {self.denominator}"
            f"(節の判定別の合計 {sum(node.values())} = 判定した節 {self.counted_nodes()}、"
            f"節の状態別の合計 {sum(self.boundary.by_state().values())} = 宣言表の行数 "
            f"{self.report.nodes})")
        out["完成度の割合を出さない"] = (
            "出すのは件数と 2 つの分母の内訳だけで、割合を返す呼び方も option も無い。"
            "何割できているかは、この部品の判定することではない")
        out["状態に既定を当てない"] = (
            "宣言表に無い節を参照している問いは別枠に出す。残りの節に収録済を当てて"
            "判定する経路が無い")
        out["未実装と設計上の外を同じに数えない"] = (
            "線の内側の未完成(未実装・未対応)と、線の外に置いた設計判断(設計上の外)は"
            "別の列で数える。足せば 1 つの数になるが、やることが別なので足さない")
        out["残る一手を埋めない・提案しない"] = (
            "残る一手は宣言表に書かれた名前をそのまま返すだけ。上限を当てる引数も、"
            "代わりの式を選ぶ経路も、足すべき節を出す経路も無い")
        out["出口を終了コードに潰さない"] = (
            "値が返るのか止まるのかは節ごとの欄に残す。この部品の終了コードは"
            "「全部が道具の中で済むか」だけを言い、測っている相手の出口を写さない")
        out["値を計算しない・式を評価しない・行を引かない"] = (
            "読むのは宣言の 3 枚だけで、値も式も日付も持たない。確度の欄も持たない")
        out["入力を書き換えない"] = (
            "verify が作る写し(状態を替えた表・節を外した表)はメモリの中だけで、"
            "入力の CSV には 1 文字も書かない")
        return out

    def table(self) -> list[dict[str, object]]:
        """問いごとの読み。割合の欄は無い。"""
        return [{"求める値": a.value_id, "結果": a.result, "節ごと": a.line(),
                 "要る節": len(self.recipes.of(a.value_id).node_ids),
                 "判定した節": len(a.nodes),
                 "宣言が無い節": "|".join(a.missing),
                 "残る一手の数": len(a.steps)}
                for a in self.asked]

    def judgement_bytes(self) -> bytes:
        """判定部分 = 判定した問いの表。時刻・絶対パス・ホスト名は入れない。"""
        self._guard()
        lines = ["\t".join(["件", str(self.report.recipes), str(self.report.questions),
                            str(self.denominator)])]
        for a in self.asked:
            lines.append("\t".join([a.value_id, a.result, a.line(),
                                    ",".join(f"{n}:{s}" for n, _, s in a.steps)]))
        return ("\n".join(lines) + "\n").encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.judgement_bytes()).hexdigest()

    def read_condition(self) -> dict[str, str]:
        return {SCOPE_KEYS[0]: self.boundary.path, SCOPE_KEYS[1]: self.recipes.path,
                SCOPE_KEYS[2]: self.questions.path}

    def _guard(self) -> None:
        if not self.report.ok:
            raise RuntimeError("止まっているので判定した問いは無い。"
                               "report.pending の理由コードを見る")


def handoff_edge(boundary: Boundary, recipes: Recipes,
                 questions: Questions) -> Tally:
    """問い 1 つごとに、要る節が道具の中で済むか、外に一手が残るかを数える。
    宣言表が揃う前に止まったら 1 件も判定しない。"""
    for q in questions.items:
        if recipes.of(q.value_id) is None:
            raise ReadError(f"問いの一覧 行 {q.number}: 計算のレシピ表に無い求める値"
                            f"({q.value_id})")
    pending = tuple(list(boundary.pending) + list(recipes.pending)
                    + list(questions.pending))
    report = Report(not pending, pending, len(boundary.items), len(recipes.items),
                    len(questions.items))
    if pending:                     # 1 件も判定せずに止まる
        return Tally(report=report, asked=(), boundary=boundary, recipes=recipes,
                     questions=questions)
    asked = tuple(judge(recipes.of(q.value_id), boundary)
                  for q in questions.ordered)
    return Tally(report=report, asked=asked, boundary=boundary, recipes=recipes,
                 questions=questions)


# ------------------------------------------------------------ verify


def moves(before: Tally, after: Tally) -> dict[str, int]:
    """同じ問いの結果がどこへ移ったかを数える(平均も多数決もしない)。"""
    out: dict[str, int] = {}
    for b, a in zip(before.asked, after.asked):
        if b.result != a.result:
            key = f"{b.result} → {a.result}"
            out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))


def fill_probe(boundary: Boundary, recipes: Recipes, questions: Questions,
               first: Tally) -> dict[str, object]:
    """節 1 つずつ、状態を 未実装 → 収録済 に替えて、結果がどこへ移るかを数える。

    いつも成り立つはずのこと: 移る先は **返るが一手残る → 道具の中で済む の 1 本だけ**で、
    返るが一手残るの減りと 道具の中で済むの増えが同じ件数になる(状態を直すと答えは良くなる
    方向にしか動かない)。
    """
    rows: list[dict[str, object]] = []
    ok = True
    want = f"{RESULTS[1]} → {RESULTS[0]}"
    for node in boundary.ordered:
        if node.state != STATES[1] or not node.returns:
            continue
        filled = handoff_edge(boundary.filled(node.node_id), recipes, questions)
        step = moves(first, filled)
        drop = len(first.by_result(RESULTS[1])) - len(filled.by_result(RESULTS[1]))
        gain = len(filled.by_result(RESULTS[0])) - len(first.by_result(RESULTS[0]))
        fits = set(step) <= {want} and drop == gain == step.get(want, 0)
        ok = ok and fits
        rows.append({"節": node.node_id, "残る一手": node.remaining_step,
                     "返るが一手残るの減り": drop, "道具の中で済むの増え": gain,
                     "移った先": step, "合うか": fits})
    whole = handoff_edge(boundary.all_filled(), recipes, questions)
    step = moves(first, whole)
    drop = len(first.by_result(RESULTS[1])) - len(whole.by_result(RESULTS[1]))
    gain = len(whole.by_result(RESULTS[0])) - len(first.by_result(RESULTS[0]))
    whole_fits = set(step) <= {want} and drop == gain == step.get(want, 0)
    return {"書き換えた欄": "節の状態を 未実装 → 収録済(出口と残る一手も宣言どおりに揃える。"
                            "写しはメモリの中だけ)",
            "分母(問いの数)": first.denominator, "節ごと": rows,
            "未実装を全部 収録済 にした写し": {"移った先": step,
                                               "返るが一手残るの減り": drop,
                                               "道具の中で済むの増え": gain,
                                               "合うか": whole_fits},
            "合うか": ok and whole_fits,
            "読み": ("状態を直すと、返るが一手残る → 道具の中で済む の 1 本しか動かない"
                     "(減った分だけ増える)。残る一手を道具側で埋める経路が無いことの実測")}


def drop_probe(boundary: Boundary, recipes: Recipes, questions: Questions,
               first: Tally) -> dict[str, object]:
    """節 1 つずつ、宣言表から外して、別枠がどこから増えるかを数える。

    いつも成り立つはずのこと: 移る先は **別枠(宣言が無い)1 つだけ**で、別枠の増えと
    ほかの 4 値の減りの合計が同じ件数になる(宣言が無い節に既定を当てない)。
    """
    rows: list[dict[str, object]] = []
    ok = True
    for node in boundary.ordered:
        if len(boundary.items) <= 1:
            continue
        dropped = handoff_edge(boundary.without(node.node_id), recipes, questions)
        step = moves(first, dropped)
        gain = len(dropped.by_result(ASIDE)) - len(first.by_result(ASIDE))
        lost = sum(len(first.by_result(r)) - len(dropped.by_result(r))
                   for r in RESULTS[:4])
        to_aside = all(k.endswith(f"→ {ASIDE}") for k in step)
        fits = to_aside and gain == lost == sum(step.values())
        ok = ok and fits
        rows.append({"外した節": node.node_id, "別枠の増え": gain,
                     "ほかの 4 値の減り": lost, "移った先": step, "合うか": fits})
    return {"書き換えた欄": "節 1 つを宣言表から外す(写しはメモリの中だけ)",
            "分母(問いの数)": first.denominator, "節ごと": rows, "合うか": ok,
            "読み": ("節を外すと、その節を要る問いは別枠へ出るだけで、残りの節に収録済を"
                     "当てた答えが出てこない(既定を当てる経路が無いことの実測)")}


def verify(boundary: Boundary, recipes: Recipes,
           questions: Questions) -> dict[str, object]:
    """2 回読んで sha256 を比べ、3 枚の行順を入れ替えても同じかを見て、件数を検算する。
    さらに、状態を 収録済 に替えた写しと、節を外した写しを読んで差分を出す。"""
    first = handoff_edge(boundary, recipes, questions)
    if not first.report.ok:
        return {"ok": False, "stage": "止まった(判定した問いは返さない)", **first.counts(),
                "pending": [p.as_dict() for p in first.report.pending]}
    if not questions.swap:
        raise ReadError("問いの一覧に入れ替え方(swap)が無いので verify は走らせない")
    second = handoff_edge(boundary, recipes, questions)
    third = handoff_edge(boundary.swapped(questions.swap),
                         recipes.swapped(questions.swap),
                         questions.swapped(questions.swap))
    pending: list[Pending] = []
    if first.sha256() != second.sha256():
        pending.append(Pending(STOP_REASONS[12], f"2 回目 {second.sha256()[:12]}"))
    if not (third.report.ok and first.sha256() == third.sha256()):
        pending.append(Pending(STOP_REASONS[13],
                               f"入れ替え方 {questions.swap} の 3 枚で "
                               f"{third.sha256()[:12]}" if third.report.ok else
                               f"入れ替え方 {questions.swap} の 3 枚では止まった"))
    five = {r: len(first.by_result(r)) for r in RESULTS}
    node = first.by_node_verdict()
    if sum(five.values()) != first.denominator:
        pending.append(Pending(STOP_REASONS[11], f"5 値の合計 {sum(five.values())}"
                                                 f" / 分母 {first.denominator}"))
    if sum(node.values()) != first.counted_nodes():
        pending.append(Pending(STOP_REASONS[11],
                               f"節の判定別の合計 {sum(node.values())} / 判定した節 "
                               f"{first.counted_nodes()}"))
    if first.counted_nodes() > first.node_denominator:
        pending.append(Pending(STOP_REASONS[11],
                               f"判定した節 {first.counted_nodes()} / 延べ数 "
                               f"{first.node_denominator}"))
    if sum(boundary.by_state().values()) != len(boundary.items):
        pending.append(Pending(STOP_REASONS[11],
                               f"節の状態別の合計 {sum(boundary.by_state().values())}"
                               f" / 宣言表の行数 {len(boundary.items)}"))
    out: dict[str, object] = {
        "ok": not pending, "読んだ結果": first.verdict, "読んだ回数": 2,
        "入れ替え方": questions.swap, "sha256": first.sha256(),
        "2 回目の sha256": second.sha256(),
        "入れ替えた 3 枚の sha256": third.sha256() if third.report.ok else "",
        "件数の検算": {"5 値": five, "5 値の合計": sum(five.values()),
                       "節の判定別": node, "節の判定別の合計": sum(node.values()),
                       "判定した節": first.counted_nodes(),
                       "分母(問いの数)": first.denominator,
                       "分母(問いが要る節の延べ数)": first.node_denominator},
        "状態を 収録済 に替えた写し": fill_probe(boundary, recipes, questions, first),
        "節を外した写し": drop_probe(boundary, recipes, questions, first),
    }
    for key in ("状態を 収録済 に替えた写し", "節を外した写し"):
        if not out[key]["合うか"]:        # type: ignore[index]
            pending.append(Pending(STOP_REASONS[11], f"{key} の件数が合わない"))
            out["ok"] = False
    if pending:
        out["観測"] = ("同じ表から違うバイト列が出た、または件数が合わない(平均も多数決も"
                       "しない。どちらが正しいかも決めない)")
        out["pending"] = [p.as_dict() for p in pending]
    return out


# ------------------------------------------------------------ ひな型

TEMPLATE_BOUNDARY = [
    list(SYUUBI_COLUMNS),
    ["N01", "合成の rule 甲(架空)", STATES[0], EXITS[0], "", "合成の設計メモ(架空)L1"],
    ["N02", "合成の式 乙(架空)", STATES[1], EXITS[0], "上限を当てる",
     "合成の設計メモ(架空)L2"],
    ["N03", "合成の rule 丙(架空)", STATES[3], EXITS[0], "判断を属性で渡す",
     "合成の設計メモ(架空)L3"],
]
TEMPLATE_RECIPES = [
    list(RECIPE_COLUMNS),
    ["V01", "N01", "合成のレシピメモ(架空)L1"],
    ["V02", "N01|N02", "合成のレシピメモ(架空)L2"],
    ["V03", "N01|N03", "合成のレシピメモ(架空)L3"],
]
TEMPLATE_QUESTIONS = [
    list(TOI_COLUMNS),
    ["V01", "合成の問いメモ(架空)L1", SWAPS[0]],
    ["V02", "合成の問いメモ(架空)L2", ""],
    ["V03", "合成の問いメモ(架空)L3", ""],
]


def write_csv(path: Path, rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    return path


def init(dest: str | Path) -> tuple[Path, Path, Path]:
    d = Path(dest)
    return (write_csv(d / "守備範囲の宣言表.csv", TEMPLATE_BOUNDARY),
            write_csv(d / "計算のレシピ表.csv", TEMPLATE_RECIPES),
            write_csv(d / "問いの一覧.csv", TEMPLATE_QUESTIONS))


# ------------------------------------------------------------ CLI

def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def build_parser() -> argparse.ArgumentParser:
    """CLI は edge / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = argparse.ArgumentParser(prog="handoff_edge",
                                 description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in SUBCOMMANDS[:3]:
        p = sub.add_parser(name)
        p.add_argument("boundary")
        p.add_argument("recipes")
        p.add_argument("questions")
    sub.add_parser(SUBCOMMANDS[3]).add_argument("dest")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == "init":
        print("書いた: " + " / ".join(str(p) for p in init(a.dest)))
        return 0
    try:
        boundary, recipes = Boundary.load(a.boundary), Recipes.load(a.recipes)
        questions = Questions.load(a.questions)
        if a.cmd == "verify":
            out = verify(boundary, recipes, questions)
            _print(out)
            return 0 if out["ok"] else 3
        t = handoff_edge(boundary, recipes, questions)
    except ReadError as e:
        print(f"表として読めない: {e}", file=sys.stderr)
        return 2
    if not t.report.ok:
        _print({"ok": False, "stage": "止まった(判定した問いは返さない)", **t.counts(),
                "pending": [p.as_dict() for p in t.report.pending]})
        return 3
    body: dict[str, object] = {"ok": True, "読んだ結果": t.verdict, **t.counts()}
    if a.cmd == SUBCOMMANDS[0]:
        body["問いごと"] = t.table()
        body["残る一手の一覧"] = t.remaining()
        body["sha256"] = t.sha256()
        body["読んだ条件"] = t.read_condition()
    _print(body)
    return 0 if len(t.by_result(RESULTS[0])) == t.denominator else 3


if __name__ == "__main__":
    raise SystemExit(main())
