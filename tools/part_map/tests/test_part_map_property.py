"""part_map の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 詰まり方の行 1 つには 3 値か別枠の理由 5 つのうち 1 つだけが付き、その合計は詰まり方の行数に、
部品ごとの件数の合計は対応の行数に等しく、表の行順を入れ替えても答えは変わらず、渡した表は 1 文字も書き換わらない。

4 枚の表は乱数で作る(空の出典、片側が空の対応の出典、台帳に無い id、登録表に無い記号、重複した id、近い語のみ、
線の内と外を混ぜる)。3 値と別枠はこのテストの中で別の書き方で引き直して比べる(part_map の判定の関数は呼ばない)。
道具の側は対応の行ごとに理由を集めてから詰まり方へ寄せる書き方、テストの側は詰まり方の行ごとに関わる行を全部
引き直して印の集合を作り、優先順の表を 1 回だけ引く書き方にした。derandomize=True で毎回同じ入力列、database=None で例を保存しない。
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import part_map as M  # noqa: E402

出典 = st.sampled_from(["メモ 1 行目"] * 6 + ["", " "])
KIDS = ["K1", "K2", "K3", "K4"]
PIDS = ["P1", "P2", "P3", "P4"]


@st.composite
def 表(draw: st.DrawFn) -> dict[str, list[dict[str, str]]]:
    reg = draw(st.lists(st.sampled_from(list(M.LINES + M.KINDS)), unique=True, min_size=3, max_size=5))
    kigou = [{"記号": s, "意味": "x", "要求する欄": draw(st.sampled_from(["", "出典", "対応を書いた側の出典/部品の側の出典"])),
              "出典": "y"} for s in reg]
    kadai = [{"詰まり方 id": draw(st.sampled_from(KIDS)), "説明": "x", "該当本数": draw(st.sampled_from(["3", "8+", ""])),
              "出典": draw(出典)} for _ in range(draw(st.integers(0, 6)))]
    buhin = [{"部品 id": draw(st.sampled_from(PIDS)), "内容": "x",
              "線の記号": draw(st.sampled_from([M.LINE_IN, M.LINE_IN, M.LINE_OUT, "線の際", M.NEAR])),
              "業種依存": "なし", "出典": draw(出典)} for _ in range(draw(st.integers(0, 5)))]
    taiou = [{"詰まり方 id": draw(st.sampled_from(KIDS + ["K9"])), "部品 id": draw(st.sampled_from(PIDS + ["P9"])),
              "記載の種類": draw(st.sampled_from([M.SAME, M.WORD, M.NEAR, M.NEAR, "たぶん", M.LINE_IN])),
              "対応を書いた側の出典": draw(出典), "部品の側の出典": draw(出典)} for _ in range(draw(st.integers(0, 8)))]
    return {"kadai": draw(st.permutations(kadai)), "buhin": draw(st.permutations(buhin)),
            "taiou": draw(st.permutations(taiou)), "kigou": draw(st.permutations(kigou))}


def expected(t: dict, k: dict) -> str:
    """詰まり方の行 1 つについて、関わる行を全部引き直して印の集合を作り、最後に優先順を 1 回だけ引く。"""
    reg = {r["記号"].strip(): [c for c in r["要求する欄"].split("/") if c.strip()] for r in t["kigou"]}
    kid = k["詰まり方 id"].strip()
    same_k = [r for r in t["kadai"] if r["詰まり方 id"].strip() == kid]
    links = [r for r in t["taiou"] if r["詰まり方 id"].strip() == kid]
    marks: set[str] = set()

    def empty(s: str) -> bool:
        return s.strip() == ""

    if empty(k["出典"]):   # 自分の行の出典
        marks.add("出典が空")
    if links and any(empty(r["出典"]) for r in same_k):   # 対応の行を通すと、同じ id の行の印が全部乗る
        marks.add("出典が空")
    if len(same_k) > 1:
        marks.add("id の重複")
    for x in links:
        pid = x["部品 id"].strip()
        prow = [p for p in t["buhin"] if p["部品 id"].strip() == pid]
        kind = x["記載の種類"].strip()
        if empty(x["対応を書いた側の出典"]) or empty(x["部品の側の出典"]) or any(empty(x[c]) for c in reg.get(kind, []) if c in x):
            marks.add("対応の片側の出典が空")
        if not prow:
            marks.add("台帳に無い id を指す対応")
        if kind not in reg or kind not in M.KINDS:
            marks.add("登録表に無い記号")
        for p in prow:
            line = p["線の記号"].strip()
            if empty(p["出典"]) or any(empty(p[c]) for c in reg.get(line, []) if c in p):
                marks.add("出典が空")
            if line not in reg or line not in M.LINES:
                marks.add("登録表に無い記号")
        if len(prow) > 1:
            marks.add("id の重複")
    for b in M.BETSU:
        if b in marks:
            return b
    lines = [next(p for p in t["buhin"] if p["部品 id"].strip() == x["部品 id"].strip())["線の記号"].strip()
             for x in links if x["記載の種類"].strip() != M.NEAR]
    if M.LINE_IN in lines:
        return M.SANCHI[0]
    if lines:
        return M.SANCHI[1]
    return M.SANCHI[2]


@settings(derandomize=True, database=None, max_examples=300, suppress_health_check=[HealthCheck.too_slow])
@given(表())
def test_行1つに1つだけ付き合計が合い行順に依らず入力は変わらない(t: dict) -> None:
    before = copy.deepcopy(t)
    res = M.judge(t)
    assert t == before
    rows = res["詰まり方ごと"]
    assert all(("3 値" in r) != ("別枠" in r) for r in rows)
    assert sum(res["3 値"].values()) + sum(res["別枠"].values()) == len(t["kadai"]) == len(rows)
    assert sorted(r.get("3 値") or r["別枠"] for r in rows) == sorted(expected(t, k) for k in t["kadai"])
    per_part = sum(p["対応の記載(近い語のみを除く)"] + p["近い語のみ"] + p["別枠の対応"] for p in res["部品ごと"])
    missing = sum(1 for x in t["taiou"] if x["部品 id"].strip() not in {p["部品 id"].strip() for p in t["buhin"]})
    assert per_part + missing == len(t["taiou"])
    rev = M.judge({k: list(reversed(v)) for k, v in t.items()})
    assert rev == res
