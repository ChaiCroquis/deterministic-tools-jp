"""input_chain — 求める値から入力の出どころを下まで辿り、呼ぶ前に人が用意するものだけを残す。
値を計算せず、宣言どうしを繋いで数えるだけ。

**呼んだ後には使った行の出典が付くが、呼ぶ前に何を手元へ置けばよいかは誰も返さない。式の入力が
また式で、その式の入力が表の行で、その行を引くのにまた日付と区分が要る。最後に残る「人しか
出せないもの」は、一段見ただけでは見えない。だから呼ぶ前に入力の出どころを下まで辿って、葉だけ
を一覧にする。**

この部品は、式の宣言表・行の宣言表・問いの一覧の 3 枚から、問い(= 求める値)1 つごとに依存を
下まで辿り、葉 1 枚ごとに 5 値(**手元に在る / 人が用意する / 導出すると宣言 / 宣言が無い /
辿れない**)を付ける。段数つきの依存の一覧と、呼ぶ前に集めるものの名前と出典も返す。
**値を計算しない。式を評価しない。行を引かない。数えるだけだ。**

持たせていないものが規律になっている。

  - **宣言に無い入力の種別を推測しない**(`case の欄` を既定として当てる経路が無い。5 値目の
    別枠「宣言が無い」に出す)
  - **`導出すると宣言` と `case の欄` を同じに数えない**(導出すると書いてある入力と、呼び口で
    人が渡している入力は、どちらが正しいかを決めずに別の列で数える)
  - **循環を黙って切らない**(経路に同じ式が 2 回出る枝と、段数の上限に当たった枝は `辿れない`
    に出す。最長段数と打ち切った枝の名前を返す。無限に降りない)
  - **足りない入力を埋めない・代わりの式を提案しない**(既定値を入れる経路も、似た名前に寄せる
    経路も無い)
  - **出典の欄が空の行は止まる**
  - **値を計算しない・式を評価しない・行を実際に引かない**
  - **引けるかどうかは見ない**(節の状態の欄も、年の在庫の欄も持たない)
  - **完成度の割合を出さない**(5 値の件数と 3 つの分母の内訳だけを返す)
  - **入力表を書き換えず、式も行も生成しない**
  - **同じ入力には同じバイト列**(判定部分に時刻・絶対パス・ホスト名を入れない。行順にも依らない)
  - **数は整数だけ**(float を使う経路が無い)

入力は 3 つ。式の宣言表(CSV)、行の宣言表(CSV)、問いの一覧(CSV)。

式の宣言表の列は 4 つ。**1 つの式の 1 つの入力が 1 行**。

    formula_id  式 id(その入力を食う式)
    input_id    入力 id(別の式 id / rule id / case の欄の名前)
    kind        調達先種別。登録の 4 種(別の式 / 表の行 / case の欄 / 導出すると宣言)
    source      出典。空欄は止まる

行の宣言表の列は 4 つ。**1 つの rule が 1 行**。

    rule_id     rule id
    basis       その行を引くのに要る基準日の欄(ちょうど 1 つ。空欄も 2 つ以上も止まる)
    dims        区分の次元を `|` でつなぐ(空欄は次元なしで、止まらない)
    source      出典。空欄は止まる

問いの一覧の列は 4 つ。**1 つの問いが 1 行**。

    value_id    訊く求める値 id(= 式 id)
    at_hand     手元に在る case の欄を `|` でつなぐ(空欄可)
    source      出典。空欄は止まる
    swap        入れ替え方。verify が 3 枚の行順を入れ替えるときの宣言

使い方:

    python input_chain.py init ひな型/
    python input_chain.py check  式の宣言表.csv 行の宣言表.csv 問いの一覧.csv
    python input_chain.py chain  式の宣言表.csv 行の宣言表.csv 問いの一覧.csv
    python input_chain.py verify 式の宣言表.csv 行の宣言表.csv 問いの一覧.csv

終了コードは、葉が全部「手元に在る」ときだけ 0、呼ぶ前に集めるものか別枠が在るときは 3、表として
読めなければ 2。**何割そろっているかはこの終了コードにも出力にも出さない。**
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

SHIKI_COLUMNS = ("formula_id", "input_id", "kind", "source")
GYOU_COLUMNS = ("rule_id", "basis", "dims", "source")
TOI_COLUMNS = ("value_id", "at_hand", "source", "swap")

# 調達先種別(登録制)。既定は持たない = 空欄を case の欄 と読み替える経路が無い
KINDS = ("別の式", "表の行", "case の欄", "導出すると宣言")
# 葉 1 枚に付く 5 値。最後の 2 つが別枠。5 つを混ぜない
RESULTS = ("手元に在る", "人が用意する", "導出すると宣言", "宣言が無い", "辿れない")
SWAPS = ("逆順", "両端入れ替え", "1 つずらす")

# 段数の上限。経路に同じ式が 2 回出る枝はここに来る前に 辿れない へ出すが、枝分かれが深いだけの
# 木もここで打ち切る(無限にも指数にも降りない)。葉が付きうる最深は 上限 + 2 段
MAX_DEPTH = 6
WHY = ("経路に同じ式が 2 回出る", "段数の上限に当たった",
       "求める値の式が宣言表に無い", "別の式が式の宣言表に無い", "表の行が行の宣言表に無い")

STOP_REASONS = (
    # 1 件も判定せずに止まる(10)
    "出典の欄が空", "調達先種別が空", "登録されていない調達先種別",
    "同じ式に同じ入力 id が 2 行ある", "基準日の欄が空", "基準日の欄に 2 つ以上書いてある",
    "同じ区分の欄を 2 回要求している", "式 id と rule id に同じ名前がある",
    "手元に在る欄に同じ名前が 2 つある", "求める値を手元に在ると宣言している",
    # verify が見つける(3)
    "件数の合計が合わない", "2 回目の判定部分が不一致", "行順を入れ替えた表で出力が変わる",
)
TABLE_REASONS = STOP_REASONS[:10]
VERIFY_REASONS = STOP_REASONS[10:]

SUBCOMMANDS = ("chain", "check", "verify", "init")
SCOPE_KEYS = ("読んだ式の宣言表の絶対パス", "読んだ行の宣言表の絶対パス",
              "読んだ問いの一覧の絶対パス")

NG_ID = set(" \t,|")


class ReadError(Exception):
    """表として読めない(終了コード 2)。葉は 1 枚も返さない。"""


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


# ------------------------------------------------------------ 式の宣言表


@dataclass(frozen=True)
class Input:
    """式 1 つの入力 1 つの宣言。種別は**読めないまま持つ**(数える段で理由コードにする)。"""
    formula_id: str
    input_id: str
    kind: str
    source: str
    number: int = 0

    def issues(self) -> tuple[Pending, ...]:
        where = f"式の宣言表 行 {self.number}({self.formula_id} ← {self.input_id})"
        out: list[Pending] = []
        if not self.source:
            out.append(Pending(STOP_REASONS[0], where))
        if not self.kind:
            out.append(Pending(STOP_REASONS[1], where))
        elif self.kind not in KINDS:
            out.append(Pending(STOP_REASONS[2], f"{where}: {self.kind}"))
        return tuple(out)

    def as_kind(self, kind: str) -> "Input":
        return Input(self.formula_id, self.input_id, kind, self.source, self.number)


@dataclass(frozen=True)
class Formulas:
    items: tuple[Input, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Formulas":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"式の宣言表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Formulas":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in SHIKI_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("式の宣言表に " + " / ".join(lack) + " の列が無い")
        items: list[Input] = []
        pending: list[Pending] = []
        seen: set[tuple[str, str]] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in SHIKI_COLUMNS}
            where = f"式の宣言表 行 {i}"
            if bad_id(cell["formula_id"]):
                raise ReadError(f"{where}: 式 id が空欄か、区切り文字を含む"
                                f"({cell['formula_id'] or '空欄'})")
            if bad_id(cell["input_id"]):
                raise ReadError(f"{where}: 入力 id が空欄か、区切り文字を含む"
                                f"({cell['input_id'] or '空欄'})")
            key = (cell["formula_id"], cell["input_id"])
            if key in seen:
                pending.append(Pending(STOP_REASONS[3], f"{where}: {key[0]} ← {key[1]}"))
            seen.add(key)
            items.append(Input(formula_id=cell["formula_id"], input_id=cell["input_id"],
                               kind=cell["kind"], source=cell["source"], number=i))
        if not items:
            raise ReadError("式の宣言表に行が無い(ヘッダだけ)")
        for it in items:
            pending.extend(it.issues())
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    @property
    def declared(self) -> tuple[str, ...]:
        """宣言されている式 id(= 入力の行を 1 本以上持つ式)。"""
        return tuple(sorted({it.formula_id for it in self.items}))

    def inputs_of(self, formula_id: str) -> tuple[Input, ...]:
        """その式の入力を**入力 id の順**で返す(行順に依らない = 入れ替えても同じ出力)。"""
        return tuple(sorted((it for it in self.items if it.formula_id == formula_id),
                            key=lambda it: it.input_id))

    def swapped(self, how: str) -> "Formulas":
        return Formulas(items=tuple(swap_rows(list(self.items), how)),
                        pending=self.pending, path=self.path)

    def retyped(self, formula_id: str, input_id: str, kind: str) -> "Formulas":
        """入力 1 つの調達先種別を替えた写し(verify が使う。入力には書かない)。"""
        return Formulas(items=tuple(it.as_kind(kind)
                                    if (it.formula_id, it.input_id) == (formula_id, input_id)
                                    else it for it in self.items),
                        pending=self.pending, path=self.path)

    def with_self_loop(self, formula_id: str) -> "Formulas":
        """その式が自分自身を入力にしている写し(= 循環を仕込む。verify が使う)。"""
        row = next(it for it in self.items if it.formula_id == formula_id)
        loop = Input(formula_id, formula_id, KINDS[0], row.source, 0)
        return Formulas(items=self.items + (loop,), pending=self.pending, path=self.path)

    def by_kind(self) -> dict[str, int]:
        """調達先種別ごとの行数(宣言の順。4 種を 1 つに潰さない)。"""
        return {k: sum(1 for it in self.items if it.kind == k) for k in KINDS}


# ------------------------------------------------------------ 行の宣言表


@dataclass(frozen=True)
class Row:
    rule_id: str
    basis: tuple[str, ...]
    dims: tuple[str, ...]
    source: str
    number: int = 0

    def issues(self) -> tuple[Pending, ...]:
        where = f"行の宣言表 行 {self.number}({self.rule_id})"
        out: list[Pending] = []
        if not self.source:
            out.append(Pending(STOP_REASONS[0], where))
        if not self.basis:
            out.append(Pending(STOP_REASONS[4], where))
        elif len(self.basis) > 1:
            out.append(Pending(STOP_REASONS[5], f"{where}: {'|'.join(self.basis)}"))
        if len(set(self.dims)) != len(self.dims):
            out.append(Pending(STOP_REASONS[6], f"{where}: {'|'.join(self.dims)}"))
        return tuple(out)

    def needs(self) -> tuple[str, ...]:
        """その行を引くのに要る case の欄(基準日が先、区分は名前の順)。"""
        return tuple(self.basis) + tuple(sorted(self.dims))


@dataclass(frozen=True)
class Rows:
    items: tuple[Row, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Rows":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"行の宣言表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Rows":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in GYOU_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("行の宣言表に " + " / ".join(lack) + " の列が無い")
        items: list[Row] = []
        seen: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in GYOU_COLUMNS}
            where = f"行の宣言表 行 {i}"
            if bad_id(cell["rule_id"]):
                raise ReadError(f"{where}: rule id が空欄か、区切り文字を含む"
                                f"({cell['rule_id'] or '空欄'})")
            if cell["rule_id"] in seen:
                raise ReadError(f"{where}: 同じ rule id が 2 行ある({cell['rule_id']})")
            seen.add(cell["rule_id"])
            items.append(Row(rule_id=cell["rule_id"],
                             basis=tuple(x.strip() for x in cell["basis"].split("|") if x.strip()),
                             dims=tuple(x.strip() for x in cell["dims"].split("|") if x.strip()),
                             source=cell["source"], number=i))
        if not items:
            raise ReadError("行の宣言表に行が無い(ヘッダだけ)")
        pending: list[Pending] = []
        for r in items:
            pending.extend(r.issues())
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    def of(self, rule_id: str) -> Row | None:
        return next((r for r in self.items if r.rule_id == rule_id), None)

    @property
    def declared(self) -> tuple[str, ...]:
        return tuple(sorted(r.rule_id for r in self.items))

    def swapped(self, how: str) -> "Rows":
        return Rows(items=tuple(swap_rows(list(self.items), how)),
                    pending=self.pending, path=self.path)


# ------------------------------------------------------------ 問いの一覧


@dataclass(frozen=True)
class Question:
    value_id: str
    at_hand: tuple[str, ...]
    source: str
    number: int = 0

    def issues(self) -> tuple[Pending, ...]:
        where = f"問いの一覧 行 {self.number}({self.value_id})"
        out: list[Pending] = []
        if not self.source:
            out.append(Pending(STOP_REASONS[0], where))
        if len(set(self.at_hand)) != len(self.at_hand):
            out.append(Pending(STOP_REASONS[8], f"{where}: {'|'.join(self.at_hand)}"))
        if self.value_id in self.at_hand:
            out.append(Pending(STOP_REASONS[9], f"{where}: {self.value_id}"))
        return tuple(out)


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
        seen: set[str] = set()
        swaps: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in TOI_COLUMNS}
            where = f"問いの一覧 行 {i}"
            if bad_id(cell["value_id"]):
                raise ReadError(f"{where}: 求める値 id が空欄か、区切り文字を含む"
                                f"({cell['value_id'] or '空欄'})")
            if cell["value_id"] in seen:
                raise ReadError(f"{where}: 同じ問いが 2 行ある({cell['value_id']})")
            seen.add(cell["value_id"])
            if cell["swap"]:
                swaps.add(cell["swap"])
            items.append(Question(value_id=cell["value_id"],
                                  at_hand=tuple(x.strip() for x in cell["at_hand"].split("|")
                                                if x.strip()),
                                  source=cell["source"], number=i))
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
        return tuple(sorted(self.items, key=lambda q: q.value_id))

    def swapped(self, how: str) -> "Questions":
        return Questions(items=tuple(swap_rows(list(self.items), how)),
                         pending=self.pending, swap=self.swap, path=self.path)


# ------------------------------------------------------------ 辿る


@dataclass(frozen=True)
class Leaf:
    """枝の先。5 値のどれか 1 つと、何段目か、どの宣言から来たかを持つ。"""
    name: str
    result: str
    depth: int
    source: str
    why: str = ""

    def line(self) -> str:
        return f"{self.name}:{self.result}:{self.depth}"


def walk(value_id: str, at_hand: tuple[str, ...], formulas: Formulas,
         rows: Rows) -> tuple[Leaf, ...]:
    """求める値 1 つから入力の出どころを下まで辿り、葉を並べる。

    **種別に既定を当てない**(宣言が無い参照は 宣言が無い に出す)。**循環を黙って切らない**
    (経路に同じ式が 2 回出る枝と、段数の上限に当たった枝は 辿れない に出す)。
    """
    declared = set(formulas.declared)
    out: list[Leaf] = []
    if value_id not in declared:
        return (Leaf(value_id, RESULTS[3], 0, "", WHY[2]),)

    def leaf_of_case(name: str, depth: int, source: str) -> Leaf:
        return Leaf(name, RESULTS[0] if name in at_hand else RESULTS[1], depth, source)

    def descend(formula_id: str, depth: int, path: tuple[str, ...]) -> None:
        for it in formulas.inputs_of(formula_id):
            d = depth + 1
            if it.kind == KINDS[2]:                       # case の欄
                out.append(leaf_of_case(it.input_id, d, it.source))
            elif it.kind == KINDS[3]:                     # 導出すると宣言
                out.append(Leaf(it.input_id, RESULTS[2], d, it.source))
            elif it.kind == KINDS[1]:                     # 表の行
                row = rows.of(it.input_id)
                if row is None:
                    out.append(Leaf(it.input_id, RESULTS[3], d, it.source, WHY[4]))
                else:
                    for name in row.needs():
                        out.append(leaf_of_case(name, d + 1, row.source))
            else:                                         # 別の式
                if it.input_id not in declared:
                    out.append(Leaf(it.input_id, RESULTS[3], d, it.source, WHY[3]))
                elif it.input_id in path:
                    out.append(Leaf(it.input_id, RESULTS[4], d, it.source, WHY[0]))
                elif d > MAX_DEPTH:
                    out.append(Leaf(it.input_id, RESULTS[4], d, it.source, WHY[1]))
                else:
                    descend(it.input_id, d, path + (it.input_id,))

    descend(value_id, 0, (value_id,))
    return tuple(out)


@dataclass(frozen=True)
class Asked:
    value_id: str
    leaves: tuple[Leaf, ...]

    @property
    def depth(self) -> int:
        """この問いの段数(葉の最大。葉が無ければ 0)。"""
        return max((f.depth for f in self.leaves), default=0)

    def five(self) -> dict[str, int]:
        return {r: sum(1 for f in self.leaves if f.result == r) for r in RESULTS}

    def line(self) -> str:
        return "|".join(f.line() for f in self.leaves)


@dataclass(frozen=True)
class Report:
    ok: bool
    pending: tuple[Pending, ...]
    inputs: int
    rules: int
    questions: int


@dataclass(frozen=True)
class Tally:
    report: Report
    asked: tuple[Asked, ...]
    formulas: Formulas
    rows: Rows
    questions: Questions

    @property
    def denominator(self) -> int:
        return self.report.questions

    def leaves(self) -> tuple[Leaf, ...]:
        return tuple(f for a in self.asked for f in a.leaves)

    def leaf_denominator(self) -> int:
        """葉の分母(延べ数)。問いごとに枝の数が違うので掛け算にしない。"""
        return len(self.leaves())

    def deepest(self) -> int:
        return max((a.depth for a in self.asked), default=0)

    def five(self) -> dict[str, int]:
        return {r: sum(1 for f in self.leaves() if f.result == r) for r in RESULTS}

    def by_depth(self) -> dict[str, int]:
        """段別の葉の数(何段目に何枚あるか)。一段目だけ見たときとの差がここに出る。"""
        out: dict[str, int] = {}
        for f in self.leaves():
            out[f"{f.depth} 段"] = out.get(f"{f.depth} 段", 0) + 1
        return dict(sorted(out.items(), key=lambda kv: int(kv[0].split(" ")[0])))

    def collect(self) -> list[dict[str, object]]:
        """呼ぶ前に集めるもの(人が用意する葉)の名前と出典。**名前は宣言のまま**。"""
        names: dict[str, dict[str, list[str]]] = {}
        for a in self.asked:
            for f in a.leaves:
                if f.result != RESULTS[1]:
                    continue
                cell = names.setdefault(f.name, {"要る問い": [], "段": [], "出典": [],
                                                 "延べ": []})
                cell["延べ"].append(f.name)
                for key, value in (("要る問い", a.value_id), ("段", str(f.depth)),
                                   ("出典", f.source)):
                    if value not in cell[key]:
                        cell[key].append(value)
        out: list[dict[str, object]] = []
        for name in sorted(names):
            cell = names[name]
            out.append({"名前": name, "延べ数": len(cell["延べ"]),
                        "要る問い": "|".join(cell["要る問い"]),
                        "段": "|".join(sorted(cell["段"])),
                        "出典": " / ".join(sorted(cell["出典"]))})
        return out

    def cut(self) -> list[dict[str, object]]:
        """辿れない の一覧(打ち切った枝の名前と、なぜ打ち切ったか)。"""
        return [{"求める値": a.value_id, "枝": f.name, "段": f.depth, "なぜ": f.why,
                 "出典": f.source}
                for a in self.asked for f in a.leaves if f.result == RESULTS[4]]

    def counts(self) -> dict[str, object]:
        """件数は丸めず、3 つの分母と内訳つきで出す。割合は返さない。"""
        five = self.five()
        out: dict[str, object] = {
            "式の宣言表の行数(入力の数)": self.report.inputs,
            "行の宣言表の行数(rule の数)": self.report.rules,
            "問いの数": self.report.questions,
            "分母(問いの数)": self.denominator,
            "分母(葉の数)": self.leaf_denominator(),
            "分母(段数の最大)": self.deepest(),
            "5 値": five,
            "段別の葉の数": self.by_depth(),
            "調達先種別別(宣言表の行数)": self.formulas.by_kind(),
            "読んだか": ("読んだ" if self.asked else
                         "読んでいない(宣言が揃う前に止まったので 5 値は全て 0)"),
        }
        out["分母に含めたもの"] = (
            f"問いの数 {self.denominator} 件、葉の数 {self.leaf_denominator()} 枚(延べ)、"
            f"段数の最大 {self.deepest()}。5 値の内訳は 手元に在る {five[RESULTS[0]]}"
            f" + 人が用意する {five[RESULTS[1]]} + 導出すると宣言 {five[RESULTS[2]]}"
            f" + 宣言が無い {five[RESULTS[3]]} + 辿れない {five[RESULTS[4]]}")
        out["件数の合計の検算"] = (
            f"5 値の合計 {sum(five.values())} / 葉の数 {self.leaf_denominator()}"
            f"(問いごとの内訳の合計 {sum(sum(a.five().values()) for a in self.asked)} も同じ、"
            f"調達先種別別の合計 {sum(self.formulas.by_kind().values())} = 式の宣言表の行数 "
            f"{self.report.inputs})")
        out["完成度の割合を出さない"] = (
            "出すのは件数と 3 つの分母の内訳だけで、割合を返す呼び方も option も無い。"
            "何割そろっているかは、この部品の判定することではない")
        out["種別に既定を当てない"] = (
            "宣言に無い入力の種別を推測しない。宣言表に無い式も rule も、別枠の 宣言が無い に"
            "出す。case の欄 を既定として当てる経路が無い")
        out["導出すると宣言 と case の欄 を同じに数えない"] = (
            "導出すると書いてある入力と、呼び口で人が渡している入力は、どちらが正しいかを"
            "決めずに別の列で数える。足せば 1 つの数になるが、やることが別なので足さない")
        out["循環を黙って切らない"] = (
            "経路に同じ式が 2 回出る枝と、段数の上限 "
            f"{MAX_DEPTH} 段に当たった枝は 辿れない に出す。打ち切った枝の名前と段は一覧で返す")
        out["足りない入力を埋めない・提案しない"] = (
            "呼ぶ前に集めるものは宣言に書かれた名前をそのまま返すだけ。既定値を入れる経路も、"
            "似た名前に寄せる経路も、代わりの式を出す経路も無い")
        out["値を計算しない・式を評価しない・行を引かない"] = (
            "読むのは宣言の 3 枚だけで、値も日付も持たない。引けるかどうかの欄も持たない")
        out["入力を書き換えない"] = (
            "verify が作る写し(種別を替えた表・循環を仕込んだ表)はメモリの中だけで、"
            "入力の CSV には 1 文字も書かない")
        return out

    def table(self) -> list[dict[str, object]]:
        """問いごとの依存の一覧(段数つき)。割合の欄は無い。"""
        return [{"求める値": a.value_id, "段数": a.depth, "葉の数": len(a.leaves),
                 "5 値": a.five(), "葉ごと": a.line()} for a in self.asked]

    def judgement_bytes(self) -> bytes:
        """判定部分 = 問いごとの葉の並び。時刻・絶対パス・ホスト名は入れない。"""
        self._guard()
        lines = ["\t".join(["件", str(self.report.inputs), str(self.report.rules),
                            str(self.report.questions)])]
        for a in self.asked:
            lines.append("\t".join([a.value_id, str(a.depth), a.line()]))
        return ("\n".join(lines) + "\n").encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.judgement_bytes()).hexdigest()

    def read_condition(self) -> dict[str, str]:
        return {SCOPE_KEYS[0]: self.formulas.path, SCOPE_KEYS[1]: self.rows.path,
                SCOPE_KEYS[2]: self.questions.path}

    def _guard(self) -> None:
        if not self.report.ok:
            raise RuntimeError("止まっているので辿った葉は無い。"
                               "report.pending の理由コードを見る")


def input_chain(formulas: Formulas, rows: Rows, questions: Questions) -> Tally:
    """問い 1 つごとに入力の出どころを下まで辿る。宣言が揃う前に止まったら 1 枚も辿らない。"""
    both = set(formulas.declared) & set(rows.declared)
    pending = list(formulas.pending) + list(rows.pending) + list(questions.pending)
    for name in sorted(both):
        pending.append(Pending(STOP_REASONS[7], f"式 id にも rule id にも在る: {name}"))
    report = Report(not pending, tuple(pending), len(formulas.items), len(rows.items),
                    len(questions.items))
    if pending:                     # 1 枚も辿らずに止まる
        return Tally(report=report, asked=(), formulas=formulas, rows=rows,
                     questions=questions)
    asked = tuple(Asked(q.value_id, walk(q.value_id, q.at_hand, formulas, rows))
                  for q in questions.ordered)
    return Tally(report=report, asked=asked, formulas=formulas, rows=rows,
                 questions=questions)


# ------------------------------------------------------------ verify


def depth_hist(leaves: tuple[Leaf, ...]) -> dict[int, int]:
    """段ごとの葉の数(probe が「1 段下に増えたか」を数で言うために使う)。"""
    out: dict[int, int] = {}
    for f in leaves:
        out[f.depth] = out.get(f.depth, 0) + 1
    return out


def take_out(have: list[Leaf], drop: tuple[Leaf, ...]) -> list[Leaf]:
    """多重集合の引き算(同じ葉が 2 枚あっても 1 枚ずつ引く)。"""
    out = list(have)
    for f in drop:
        if f in out:
            out.remove(f)
    return out


def retype_probe(formulas: Formulas, rows: Rows, questions: Questions,
                 first: Tally) -> dict[str, object]:
    """`case の欄` と宣言された入力のうち、その名前が式 id でもあるものを `別の式` に替えて、
    葉がどう動くかを数える。

    替えて確かめるのは、**替えた先の式の入力が全部その場で葉になるもの**だけ(= 1 段下に出ると
    数で言えるもの)。いつも成り立つはずのこと: その葉が 1 枚消えて、**替えた式の入力の数だけ
    葉が 1 段下に増える**。段数は「元の段数」と「その葉の段 + 1」の大きい方になる。
    **替えた葉を持たない問いは 1 枚も動かない。**
    """
    declared = set(formulas.declared)
    candidates = [it for it in sorted(formulas.items,
                                      key=lambda x: (x.formula_id, x.input_id))
                  if it.kind == KINDS[2] and it.input_id in declared
                  and all(s.kind in KINDS[2:] for s in formulas.inputs_of(it.input_id))]
    out_rows: list[dict[str, object]] = []
    ok = True
    for it in candidates:
        after = input_chain(formulas.retyped(it.formula_id, it.input_id, KINDS[0]),
                            rows, questions)
        sub = len(formulas.inputs_of(it.input_id))
        fits = True
        moved: list[str] = []
        for b, a in zip(first.asked, after.asked):
            hit = tuple(f for f in b.leaves
                        if f.name == it.input_id and f.result in RESULTS[:2])
            if not hit:
                fits = fits and a.leaves == b.leaves
                continue
            moved.append(b.value_id)
            want = depth_hist(b.leaves)
            for f in hit:
                want[f.depth] = want.get(f.depth, 0) - 1
                want[f.depth + 1] = want.get(f.depth + 1, 0) + sub
            want = {d: n for d, n in want.items() if n}
            fits = fits and depth_hist(a.leaves) == want
            fits = fits and a.depth == max(b.depth, max(f.depth for f in hit) + 1)
        ok = ok and fits
        out_rows.append({"替えた入力": f"{it.formula_id} ← {it.input_id}",
                         "替えた式の入力の数": sub, "動いた問い": "|".join(moved),
                         "人が用意する": f"{first.five()[RESULTS[1]]} → "
                                         f"{after.five()[RESULTS[1]]}",
                         "葉の数": f"{first.leaf_denominator()} → "
                                   f"{after.leaf_denominator()}",
                         "段数の最大": f"{first.deepest()} → {after.deepest()}",
                         "合うか": fits})
    return {"書き換えた欄": "入力の調達先種別を case の欄 → 別の式(写しはメモリの中だけ)",
            "分母(問いの数)": first.denominator, "入力ごと": out_rows, "合うか": ok,
            "読み": ("種別を 1 つ替えると、その葉が消えて替えた式の入力が 1 段下に出る。"
                     "替えた葉を持たない問いは 1 枚も動かない"
                     "(種別を推測する経路が無いことの実測)")}


def loop_probe(formulas: Formulas, rows: Rows, questions: Questions,
               first: Tally) -> dict[str, object]:
    """式 1 つずつ、自分自身を入力にした写し(= 循環)を作って、辿れない がどこに出るかを数える。

    いつも成り立つはずのこと: 増えるのは **辿れない の葉だけ**で、ほかの葉は 1 枚も動かない
    (循環が別の問いの答えに漏れない。無限にも降りない)。
    """
    out_rows: list[dict[str, object]] = []
    ok = True
    for formula_id in formulas.declared:
        after = input_chain(formulas.with_self_loop(formula_id), rows, questions)
        hit = 0
        fits = True
        for b, a in zip(first.asked, after.asked):
            born = take_out(list(a.leaves), b.leaves)
            gone = take_out(list(b.leaves), a.leaves)
            fits = fits and not gone and a.depth <= MAX_DEPTH + 2
            fits = fits and all(f.result == RESULTS[4] and f.name == formula_id
                                and f.why == WHY[0] for f in born)
            hit += 1 if born else 0
        ok = ok and fits
        out_rows.append({"循環を仕込んだ式": formula_id, "辿れない が出た問い": hit,
                         "ほかの葉が動いたか": "動いていない" if fits else "動いた",
                         "合うか": fits})
    return {"書き換えた欄": "式 1 つが自分自身を入力にしている行を足す(写しはメモリの中だけ)",
            "分母(問いの数)": first.denominator, "式ごと": out_rows, "合うか": ok,
            "読み": ("循環は 辿れない に出るだけで、ほかの葉には漏れない。"
                     "段数は上限 + 2 を超えない(無限に降りる経路が無いことの実測)")}


def verify(formulas: Formulas, rows: Rows, questions: Questions) -> dict[str, object]:
    """2 回読んで sha256 を比べ、3 枚の行順を入れ替えても同じかを見て、件数を検算する。
    さらに、種別を替えた写しと、循環を仕込んだ写しを読んで差分を出す。"""
    first = input_chain(formulas, rows, questions)
    if not first.report.ok:
        return {"ok": False, "stage": "止まった(辿った葉は返さない)", **first.counts(),
                "pending": [p.as_dict() for p in first.report.pending]}
    if not questions.swap:
        raise ReadError("問いの一覧に入れ替え方(swap)が無いので verify は走らせない")
    second = input_chain(formulas, rows, questions)
    third = input_chain(formulas.swapped(questions.swap), rows.swapped(questions.swap),
                        questions.swapped(questions.swap))
    pending: list[Pending] = []
    if first.sha256() != second.sha256():
        pending.append(Pending(STOP_REASONS[11], f"2 回目 {second.sha256()[:12]}"))
    if not (third.report.ok and first.sha256() == third.sha256()):
        pending.append(Pending(STOP_REASONS[12],
                               f"入れ替え方 {questions.swap} の 3 枚で "
                               f"{third.sha256()[:12]}" if third.report.ok else
                               f"入れ替え方 {questions.swap} の 3 枚では止まった"))
    five = first.five()
    if sum(five.values()) != first.leaf_denominator():
        pending.append(Pending(STOP_REASONS[10], f"5 値の合計 {sum(five.values())}"
                                                 f" / 葉の数 {first.leaf_denominator()}"))
    per = sum(sum(a.five().values()) for a in first.asked)
    if per != first.leaf_denominator():
        pending.append(Pending(STOP_REASONS[10],
                               f"問いごとの内訳の合計 {per} / 葉の数 "
                               f"{first.leaf_denominator()}"))
    if sum(formulas.by_kind().values()) != len(formulas.items):
        pending.append(Pending(STOP_REASONS[10],
                               f"調達先種別別の合計 {sum(formulas.by_kind().values())}"
                               f" / 式の宣言表の行数 {len(formulas.items)}"))
    if first.deepest() > MAX_DEPTH + 2:
        pending.append(Pending(STOP_REASONS[10],
                               f"段数の最大 {first.deepest()} が上限 + 2 を超えた"))
    out: dict[str, object] = {
        "ok": not pending, "読んだ回数": 2, "入れ替え方": questions.swap,
        "sha256": first.sha256(), "2 回目の sha256": second.sha256(),
        "入れ替えた 3 枚の sha256": third.sha256() if third.report.ok else "",
        "件数の検算": {"5 値": five, "5 値の合計": sum(five.values()),
                       "問いごとの内訳の合計": per,
                       "分母(問いの数)": first.denominator,
                       "分母(葉の数)": first.leaf_denominator(),
                       "分母(段数の最大)": first.deepest()},
        "種別を 別の式 に替えた写し": retype_probe(formulas, rows, questions, first),
        "循環を仕込んだ写し": loop_probe(formulas, rows, questions, first),
    }
    for key in ("種別を 別の式 に替えた写し", "循環を仕込んだ写し"):
        if not out[key]["合うか"]:        # type: ignore[index]
            pending.append(Pending(STOP_REASONS[10], f"{key} の件数が合わない"))
            out["ok"] = False
    if pending:
        out["観測"] = ("同じ表から違うバイト列が出た、または件数が合わない(平均も多数決も"
                       "しない。どちらが正しいかも決めない)")
        out["pending"] = [p.as_dict() for p in pending]
    return out


# ------------------------------------------------------------ ひな型

TEMPLATE_FORMULAS = [
    list(SHIKI_COLUMNS),
    ["F01", "F02", KINDS[0], "合成の設計メモ(架空)L1"],
    ["F01", "C01", KINDS[2], "合成の設計メモ(架空)L2"],
    ["F02", "R01", KINDS[1], "合成の設計メモ(架空)L3"],
    ["F02", "C02", KINDS[3], "合成の設計メモ(架空)L4"],
]
TEMPLATE_ROWS = [
    list(GYOU_COLUMNS),
    ["R01", "C03", "C04", "合成の行メモ(架空)L1"],
]
TEMPLATE_QUESTIONS = [
    list(TOI_COLUMNS),
    ["F01", "C01", "合成の問いメモ(架空)L1", SWAPS[0]],
    ["F02", "", "合成の問いメモ(架空)L2", ""],
]


def write_csv(path: Path, rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    return path


def init(dest: str | Path) -> tuple[Path, Path, Path]:
    d = Path(dest)
    return (write_csv(d / "式の宣言表.csv", TEMPLATE_FORMULAS),
            write_csv(d / "行の宣言表.csv", TEMPLATE_ROWS),
            write_csv(d / "問いの一覧.csv", TEMPLATE_QUESTIONS))


# ------------------------------------------------------------ CLI

def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def build_parser() -> argparse.ArgumentParser:
    """CLI は chain / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = argparse.ArgumentParser(prog="input_chain",
                                 description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in SUBCOMMANDS[:3]:
        p = sub.add_parser(name)
        p.add_argument("formulas")
        p.add_argument("rows")
        p.add_argument("questions")
    sub.add_parser(SUBCOMMANDS[3]).add_argument("dest")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == "init":
        print("書いた: " + " / ".join(str(p) for p in init(a.dest)))
        return 0
    try:
        formulas, rows = Formulas.load(a.formulas), Rows.load(a.rows)
        questions = Questions.load(a.questions)
        if a.cmd == "verify":
            out = verify(formulas, rows, questions)
            _print(out)
            return 0 if out["ok"] else 3
        t = input_chain(formulas, rows, questions)
    except ReadError as e:
        print(f"表として読めない: {e}", file=sys.stderr)
        return 2
    if not t.report.ok:
        _print({"ok": False, "stage": "止まった(辿った葉は返さない)", **t.counts(),
                "pending": [p.as_dict() for p in t.report.pending]})
        return 3
    body: dict[str, object] = {"ok": True, **t.counts()}
    if a.cmd == SUBCOMMANDS[0]:
        body["問いごと"] = t.table()
        body["呼ぶ前に集めるもの"] = t.collect()
        body["辿れない の一覧"] = t.cut()
        body["sha256"] = t.sha256()
        body["読んだ条件"] = t.read_condition()
    _print(body)
    return 0 if t.five()[RESULTS[0]] == t.leaf_denominator() else 3


if __name__ == "__main__":
    raise SystemExit(main())
