"""recall_tally の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 対 1 件には、区分 5 つか別枠の理由 6 つのうち 1 つだけが付き、その合計は対の件数に等しく、
表の行順を入れ替えても答えは変わらず、差は (B) の対にだけ返り、渡した表は 1 文字も書き換わらない。

4 枚の表は乱数で作る(空の出典、登録に無い単位、重複した数 id、台帳に無い数 id、同じ経路どうしの対、概数の印、
空の数、整数の形でない数、空白の混じった数を混ぜる)。区分はこのテストの中で別の書き方で引き直して比べる
(recall_tally の判定の関数は呼ばない)。道具の側は対ごとに上から関門を通す書き方、テストの側は先に全ての印を
集合で作ってから優先順の表を 1 回だけ引く書き方にした。derandomize=True で毎回同じ入力列、database=None で例を保存しない。
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import recall_tally as R  # noqa: E402

数 = st.sampled_from(["3", "3", "4", " 4", "10", "", "約 3", "1.5", "１", "2〜3", "07", "7"])
単位 = st.sampled_from(["行", "行", "区分", "等級", "箱"])
出典 = st.sampled_from(["メモ 1 行目"] * 6 + ["", " "])
数id = st.sampled_from(["N1", "N2", "N3", "N4", "N5", "N6", "N9", ""])


@st.composite
def 表(draw: st.DrawFn) -> dict[str, list[dict[str, str]]]:
    routes = [{"経路 id": k, "経路の素性": "x", "出典": "y"} for k in ("S1", "S2")]
    units = [{"記号": k, "意味": "x", "出典": "y"} for k in ("行", "区分", "等級")]
    counts = [{"数 id": draw(st.sampled_from(["N1", "N2", "N3", "N4", "N5", "N6", "N1"])),
               "経路 id": draw(st.sampled_from(["S1", "S2"])), "項目 id": draw(st.sampled_from(["i1", "i2"])),
               "数の文字列": draw(数), "単位の記号": draw(単位), "概数の印": draw(st.sampled_from(["無い", "無い", "在る"])),
               "数え方の記載": draw(st.sampled_from(["", "z"])), "出典": draw(出典)}
              for _ in range(draw(st.integers(0, 8)))]
    pairs = []
    for _ in range(draw(st.integers(0, 6))):
        a, b = draw(数id), draw(数id)
        if a == "" and b == "":
            a = "N1"
        pairs.append({"項目 id": draw(st.sampled_from(["i1", "i2"])), "経路 1 の数 id": a, "経路 2 の数 id": b,
                      "根拠": "x", "出典": draw(出典)})
    return {"routes": draw(st.permutations(routes)), "counts": draw(st.permutations(counts)),
            "units": draw(st.permutations(units)), "pairs": draw(st.permutations(pairs))}


PRIORITY = list(R.BETSU[:5]) + [R.KUBUN[3], R.KUBUN[4], R.KUBUN[2], R.KUBUN[0], R.KUBUN[1], R.BETSU[5]]


def expected(t: dict, p: dict) -> str:
    """先に全ての印を集合で作り、最後に優先順の表を 1 回だけ引く(道具の関数は使わない)。"""
    ids = [x for x in (p["経路 1 の数 id"].strip(), p["経路 2 の数 id"].strip()) if x]
    sides = [[c for c in t["counts"] if c["数 id"].strip() == i] for i in ids]   # 同じ id が両側に在っても 2 つと数える
    reg = {u["記号"].strip() for u in t["units"]}
    marks = set()
    allrows = [c for v in sides for c in v]
    if not p["出典"].strip() or any(not c["出典"].strip() for c in allrows):
        marks.add(R.BETSU[0])
    if any(c["単位の記号"].strip() not in reg for c in allrows):
        marks.add(R.BETSU[1])
    if any(len(v) > 1 for v in sides):
        marks.add(R.BETSU[2])
    if any(len(v) == 0 for v in sides):
        marks.add(R.BETSU[3])
    one = [v[0] for v in sides if len(v) == 1]
    if len(ids) == 2 and len(one) == 2 and one[0]["経路 id"] == one[1]["経路 id"]:
        marks.add(R.BETSU[4])
    s = ["".join(ch for ch in c["数の文字列"] if ch not in " 　\t") for c in one]
    if len(one) < len(ids):
        pass   # 台帳に無い・重複した数 id。別枠の印が既に付いている
    elif len(ids) < 2 or any(x == "" for x in s):
        marks.add(R.KUBUN[3])
    elif any(c["概数の印"] == "在る" for c in one):
        marks.add(R.KUBUN[4])
    elif one[0]["単位の記号"].strip() != one[1]["単位の記号"].strip():
        marks.add(R.KUBUN[2])
    elif s[0] == s[1]:
        marks.add(R.KUBUN[0])
    elif all(x and all("0" <= ch <= "9" for ch in x) for x in s):
        marks.add(R.KUBUN[1])
    else:
        marks.add(R.BETSU[5])
    return next(k for k in PRIORITY if k in marks)


@settings(derandomize=True, database=None, max_examples=300, suppress_health_check=[HealthCheck.too_slow])
@given(表())
def test_対1件に1つだけ付き合計が合い行順に依らず差はBにだけ返り入力は変わらない(t: dict) -> None:
    before = copy.deepcopy(t)
    res = R.judge(t)
    assert t == before
    labels = [r.get("区分") or r.get("別枠") for r in res["対ごと"]]
    assert all(("区分" in r) != ("別枠" in r) for r in res["対ごと"])
    assert sum(res["区分"].values()) + sum(res["別枠"].values()) == len(t["pairs"]) == len(labels)
    assert sorted(labels) == sorted(expected(t, p) for p in t["pairs"])
    assert all((R.KUBUN[1] == r.get("区分")) == ("差(経路 2 − 経路 1)" in r) for r in res["対ごと"])
    rev = R.judge({k: list(reversed(v)) for k, v in t.items()})
    assert rev == res
