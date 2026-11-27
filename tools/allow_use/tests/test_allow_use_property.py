"""allow_use の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 許可の台帳の語の種類((語, 種別) の組)は、区分 (A) (B) (C) か別枠のどれか 1 つにだけ入り、
その合計は語の種類数に等しい。(D) に並ぶのは、読めた式に出てきて許可の台帳に無い語だけ。式の台帳の行順を
入れ替えても判定部分は同じバイト列になる。どの場合も 4 表は書き換わらない。

4 表は乱数で作る(架空の語、読めない式、出典の空、2 つの値以外の種別、数え方、式の台帳に無い主の束を混ぜる)。
derandomize=True で毎回同じ入力列を使い、database=None で見つけた例を保存しない。

式から語を拾う処理と区分の決め方は、allow_use.words_of / judge を使わず、このテストの中で別に書く
(ast.walk でなく子を自分でたどる)。道具の判定が壊れても、このテストで気づけるようにするため。
"""
from __future__ import annotations

import ast
import copy
import re
import sys
from pathlib import Path

from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import allow_use as U  # noqa: E402

名前の候補 = ["f", "g", "h", "k"]
種類の候補 = ["Expression", "BinOp", "Add", "Sub", "Call", "Name", "Load", "Constant", "Compare", "Lt",
              "UnaryOp", "USub", "IfExp", "List", "Attribute", "Tuple"]
式の候補 = ["f(a)", "g(a) + 1", "a - b", "h(f(a))", "a < b", "-a", "a if b else c", "[a, b]", "a.g(c)", "12",
            "k", "f", "a +", "(", "g(1.5) - 2", ""]

許可の行 = st.fixed_dictionaries({
    "word": st.sampled_from(名前の候補 + 種類の候補),
    "kind": st.sampled_from(["名前"] * 4 + ["構文の種類"] * 4 + ["関数"]),
    "origin": st.sampled_from(["x", "y"]),
    "source": st.sampled_from(["s1", "s2", "s2", "s2", "s2", ""]),
})
式の行 = st.fixed_dictionaries({
    "expr_id": st.sampled_from(["e1", "e2", "e3", "e4"]),
    "bundle": st.sampled_from(["m", "m", "m", "n", "o"]),
    "expr": st.sampled_from(式の候補),
    "source": st.sampled_from(["t1", "t1", "t1", ""]),
})
数え方 = st.fixed_dictionaries({
    "mode": st.sampled_from([U.MODE_RAW] * 5 + [U.MODE_REWRITTEN] * 4 + ["だいたい"]),
    "main_bundle": st.sampled_from(["m"] * 7 + ["n", "n", "z"]),
    "pattern": st.just(r"(?<![\w.])(\d+\.\d+|\d+)(?![\w.])"),
    "repl": st.just(r"k('\1')"),
    "source": st.sampled_from(["r1"] * 9 + [""]),
})
在り所の行 = st.fixed_dictionaries({
    "word": st.sampled_from(名前の候補 + ["zz"]),
    "note": st.just("v = f(v)"),
    "source": st.sampled_from(["u1", ""]),
})


def 拾う(text: str):
    """式 1 本から (種別, 語) を拾う。道具の関数は使わない。読めなければ None。"""
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError:
        return None
    found, stack = set(), [tree]
    while stack:
        node = stack.pop()
        found.add(("構文の種類", node.__class__.__name__))
        if node.__class__ is ast.Call and node.func.__class__ is ast.Name:
            found.add(("名前", node.func.id))
        stack.extend(ast.iter_child_nodes(node))
    return found


def 期待(allow, exprs, reg):
    """語の種類ごとの (区分 または 別枠) と、(D) の語の集合を、テストの側で決め直す。"""
    keys = {(r["word"], r["kind"]) for r in allow}
    全体 = None
    if reg["mode"] not in (U.MODE_RAW, U.MODE_REWRITTEN):
        全体 = U.X_BAD_MODE
    elif reg["main_bundle"] not in {e["bundle"] for e in exprs}:
        全体 = U.X_NO_MAIN
    elif reg["source"] == "":
        全体 = U.X_NO_SOURCE
    if 全体:
        return {k: 全体 for k in keys}, set()
    束 = {}
    for e in exprs:
        if e["source"] == "":
            continue
        text = e["expr"]
        if reg["mode"] == U.MODE_REWRITTEN:
            text = re.sub(reg["pattern"], reg["repl"], text)
        got = 拾う(text)
        if got is not None:
            束.setdefault(e["bundle"], []).append(got)
    out, 落ちた語 = {}, set()
    for word, kind in keys:
        rows = [r for r in allow if (r["word"], r["kind"]) == (word, kind)]
        origins = [r["origin"] for r in rows]
        if kind not in ("名前", "構文の種類"):
            out[(word, kind)] = U.X_BAD_KIND
        elif len(set(origins)) != len(origins):
            out[(word, kind)] = U.X_DUP
        elif "" in [r["source"] for r in rows]:
            out[(word, kind)] = U.X_NO_SOURCE
        else:
            主 = any((kind, word) in s for s in 束.get(reg["main_bundle"], []))
            他 = any((kind, word) in s for b, ss in 束.items() for s in ss)
            out[(word, kind)] = U.A if 主 else (U.B if 他 else U.C)
            continue
        落ちた語.add(word)
    出た = set().union(*[s for ss in 束.values() for s in ss]) if 束 else set()
    外 = {(kind, word) for kind, word in 出た if (word, kind) not in keys and word not in 落ちた語}
    return out, 外


@settings(max_examples=300, derandomize=True, database=None, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(allow=st.lists(許可の行, max_size=10), exprs=st.lists(式の行, min_size=2, max_size=8), reg=数え方,
       elsewhere=st.lists(在り所の行, max_size=3), seed=st.randoms(use_true_random=False))
def test_いつも成り立つこと_語の種類はどれか_1_つにだけ入り合計が戻る(allow, exprs, reg, elsewhere, seed) -> None:
    snap = copy.deepcopy((allow, exprs, reg, elsewhere))
    r = U.judge(allow, exprs, [reg], elsewhere)
    want, want_outside = 期待(allow, exprs, reg)

    got = {}
    for row in r["語ごとの行"]:
        key = (row["語"], row["種別"])
        assert key not in got
        got[key] = row["区分"]
    for row in r["別枠に落ちた語"]:
        key = (row["語"], row["種別"])
        assert key not in got
        got[key] = row["別枠"]
    assert got == want
    n_class = sum(1 for v in got.values() if v in (U.A, U.B, U.C))
    n_side = sum(1 for v in got.values() if v in U.SIDE)
    assert n_class + n_side == len({(a["word"], a["kind"]) for a in allow})
    assert {(x["種別"], x["語"]) for x in r["線の外の語"]} == want_outside

    shuffled = list(exprs)
    seed.shuffle(shuffled)
    assert U.judge(allow, shuffled, [reg], elsewhere)["判定部分の sha256"] == r["判定部分の sha256"]
    assert (allow, exprs, reg, elsewhere) == snap

    event("区分が付いた" if n_class else ("別枠だけ" if n_side else "許可の台帳が空"))
    event("(D) が在る" if want_outside else "(D) が無い")
