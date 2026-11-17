"""stock_use の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 置き場の種類の行 1 つには 5 値か別枠の理由 6 つのうち 1 つだけが付き、その合計は置き場の種類の行数に、
置き場ごとの内訳の合計はその置き場の種類の数に等しく、差は 5 値が (B) の行にだけ 0 でない整数で付き、
記載の台帳の行順を入れ替えても答えは変わらず、渡した表は 1 文字も書き換わらない。

4 枚の表は乱数で作る(空の出典、整数でない本数、空の本数、台帳に無い記載 id、台帳に無い置き場、登録表に無い記号、
重複した種類と記載 id、1 つの記載を 2 つの種類に当てた対、使われた記載と記載なしの同居、言い方の違いを混ぜる)。
5 値と別枠はこのテストの中で別の書き方で引き直して比べる(stock_use の判定の関数は呼ばない)。
道具の側は理由の集合を作ってから優先順を引く書き方、テストの側は優先順の上から 1 つずつ条件を問い、当たった所で返す書き方にした。
derandomize=True で毎回同じ入力列、database=None で例を保存しない。
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import stock_use as M  # noqa: E402

出典 = st.sampled_from(["記録 1 行目"] * 6 + ["", " "])
OKIBA = ["P1", "P2"]
KINDS = ["PDF", "HTML", "xlsx"]
KIDS = ["K1", "K2", "K3", "K4", "K5"]
USED = ("出典の欄に在る", "検証の欄に在る")
KNOWN = ["出典の欄に在る", "検証の欄に在る", "未抽出の欄に在る", "次の作業の欄に在る", "読んだ範囲に記載なし",
         "置き場と書き手の言い方が違う"]
NO_DIFF = "-"


@st.composite
def 表(draw: st.DrawFn) -> dict[str, list[dict[str, str]]]:
    reg = draw(st.lists(st.sampled_from(KNOWN), unique=True, min_size=3, max_size=6))
    kigou = [{"記号": s, "意味": "x", "要求する欄": draw(st.sampled_from(["", "出典", "名指された数", "後の側の文字列/出典"])),
              "出典": "y"} for s in reg]
    okiba = [{"置き場 id": draw(st.sampled_from(OKIBA)), "種類": draw(st.sampled_from(KINDS)),
              "取得の本数": draw(st.sampled_from(["1", "2", "3", "", "3本", "２"])), "出典": draw(出典)}
             for _ in range(draw(st.integers(0, 6)))]
    kisai = [{"記載 id": draw(st.sampled_from(KIDS)), "記号": draw(st.sampled_from(KNOWN + ["出典の欄に在る", "たぶん"])),
              "名指された数": draw(st.sampled_from(["1", "2", "3", ""])), "後の側の文字列": draw(st.sampled_from(["あ", ""])),
              "出典": draw(出典)} for _ in range(draw(st.integers(0, 7)))]
    tsui = [{"記載 id": draw(st.sampled_from(KIDS + ["K9"])), "置き場 id": draw(st.sampled_from(OKIBA + ["P9"])),
             "種類": draw(st.sampled_from(KINDS)), "出典": draw(出典)} for _ in range(draw(st.integers(0, 8)))]
    return {"okiba": draw(st.permutations(okiba)), "kisai": draw(st.permutations(kisai)),
            "kigou": draw(st.permutations(kigou)), "tsui": draw(st.permutations(tsui))}


def expected(t: dict, o: dict) -> tuple[str, str]:
    """優先順の上から 1 つずつ問い、当たった所で返す。返すのは (区分, 差の文字列。差が無ければ "-")。"""
    reg = {r["記号"].strip(): [c for c in r["要求する欄"].split("/") if c.strip()] for r in t["kigou"]}
    key = (o["置き場 id"].strip(), o["種類"].strip())
    known_keys = [(r["置き場 id"].strip(), r["種類"].strip()) for r in t["okiba"]]
    pairs = [p for p in t["tsui"] if (p["置き場 id"].strip(), p["種類"].strip()) == key]
    ids = [r["記載 id"].strip() for r in t["kisai"]]
    first = set(ids)
    mine = [r for p in pairs for r in t["kisai"] if r["記載 id"].strip() == p["記載 id"].strip()]

    def empty(s: str) -> bool:
        return s.strip() == ""

    if (empty(o["出典"]) or any(empty(p["出典"]) for p in pairs) or any(empty(x["出典"]) for x in mine)
            or any(empty(x[c]) for x in mine for c in reg.get(x["記号"].strip(), []))):
        return "出典が空", NO_DIFF
    n = o["取得の本数"].strip()
    if n != "" and not (n.isascii() and n.isdigit()):
        return "取得の本数が整数でない", NO_DIFF
    if any(p["記載 id"].strip() not in first for p in pairs):
        return "台帳に無い id を指す対", NO_DIFF
    if any(x["記号"].strip() not in reg for x in mine):
        return "登録表に無い記号", NO_DIFF
    if known_keys.count(key) > 1:
        return "id の重複", NO_DIFF
    for x in mine:
        i = x["記載 id"].strip()
        if ids.count(i) > 1:
            return "id の重複", NO_DIFF
        if len({(p["置き場 id"].strip(), p["種類"].strip()) for p in t["tsui"] if p["記載 id"].strip() == i}) > 1:
            return "id の重複", NO_DIFF
    kinds = [x["記号"].strip() for x in mine]
    used = [x for x in mine if x["記号"].strip() in USED]
    if used and "読んだ範囲に記載なし" in kinds:
        return "同じ種類に (A)(B) と (E) が同時に書かれた", NO_DIFF
    if used:
        nums = {int(x["名指された数"]) for x in used if x["名指された数"].strip()}
        if n == "" or len(nums) != 1:
            return M.GOCHI[2], NO_DIFF
        d = int(n) - nums.pop()
        return (M.GOCHI[0], NO_DIFF) if d == 0 else (M.GOCHI[1], str(d))
    if "未抽出の欄に在る" in kinds or "次の作業の欄に在る" in kinds:
        return M.GOCHI[3], NO_DIFF
    return M.GOCHI[4], NO_DIFF


@settings(derandomize=True, database=None, max_examples=300, suppress_health_check=[HealthCheck.too_slow])
@given(表())
def test_行1つに1つだけ付き合計が合い差はBにだけ付き行順に依らず入力は変わらない(t: dict) -> None:
    before = copy.deepcopy(t)
    res = M.judge(t)
    assert t == before
    rows = res["置き場の種類ごと"]
    assert all(("5 値" in r) != ("別枠" in r) for r in rows)
    assert sum(res["5 値"].values()) + sum(res["別枠"].values()) == len(t["okiba"]) == len(rows)
    sa = "差(取得の本数 − 名指された数)"
    got = sorted((r.get("5 値") or r["別枠"], str(r[sa]) if sa in r else NO_DIFF) for r in rows)
    assert got == sorted(expected(t, o) for o in t["okiba"])
    for r in rows:
        assert (sa in r) == (r.get("5 値") == M.GOCHI[1])
        assert sa not in r or (type(r[sa]) is int and r[sa] != 0)
    for p in res["置き場ごと"]:
        assert sum(p["内訳"].values()) == p["種類の数"] == sum(1 for o in t["okiba"] if o["置き場 id"].strip() == p["置き場 id"])
    rev = copy.deepcopy(t)
    rev["kisai"] = list(reversed(rev["kisai"]))
    assert M.judge(rev) == res
