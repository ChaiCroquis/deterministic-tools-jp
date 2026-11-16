"""step_carry の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 約束の行 1 つには 4 値か別枠の理由 6 つのうち 1 つだけが付き、その合計は約束の行数に、
項目ごとの内訳の合計はその項目の約束の数に等しく、記載の台帳の行順を入れ替えても答えは変わらず、渡した表は 1 文字も書き換わらない。

4 枚の表は乱数で作る(空の出典、空の宣言、台帳に無い約束 id と文書 id、登録表に無い記号、重複した id、
済みと記載なしの同居、近い語のみを混ぜる)。4 値と別枠はこのテストの中で別の書き方で引き直して比べる
(step_carry の判定の関数は呼ばない)。道具の側は理由の集合を作ってから優先順を引く書き方、テストの側は
優先順の上から 1 つずつ条件を問い、当たった所で返す書き方にした。derandomize=True で毎回同じ入力列、database=None で例を保存しない。
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import step_carry as M  # noqa: E402

出典 = st.sampled_from(["メモ 1 行目"] * 6 + ["", " "])
YIDS = ["Y1", "Y2", "Y3", "Y4", "Y5"]
ITEMS = ["I1", "I2", "I3"]
DOCS = ["S1", "S2"]
KNOWN = ["済みの記載", "次の候補に在る", "判断待ちに在る", "別の欄に在る", "読んだ範囲に記載なし", "近い語のみ"]


@st.composite
def 表(draw: st.DrawFn) -> dict[str, list[dict[str, str]]]:
    reg = draw(st.lists(st.sampled_from(KNOWN), unique=True, min_size=3, max_size=6))
    kigou = [{"記号": s, "意味": "x", "要求する欄": draw(st.sampled_from(["", "後の側の出典", "後の側の行/後の側の文字列"])),
              "出典": "y"} for s in reg]
    bunsho = [{"文書 id": d, "時点": "z", "次の候補の行": draw(st.sampled_from(["", "1-3", "2,5"])), "出典": draw(出典)}
              for d in DOCS]
    yakusoku = [{"約束 id": draw(st.sampled_from(YIDS)), "項目 id": draw(st.sampled_from(ITEMS)),
                 "宣言の文字列": draw(st.sampled_from(["する", "する", ""])), "宣言側の出典": draw(出典)}
                for _ in range(draw(st.integers(0, 7)))]
    kisai = [{"約束 id": draw(st.sampled_from(YIDS + ["Y9"])), "後の文書 id": draw(st.sampled_from(DOCS + ["S9"])),
              "記号": draw(st.sampled_from(KNOWN + ["済みの記載", "たぶん"])),
              "後の側の行": draw(st.sampled_from(["1", "2", "3", "5", ""])), "後の側の出典": draw(出典),
              "後の側の文字列": draw(st.sampled_from(["あ", ""]))} for _ in range(draw(st.integers(0, 9)))]
    return {"bunsho": draw(st.permutations(bunsho)), "yakusoku": draw(st.permutations(yakusoku)),
            "kisai": draw(st.permutations(kisai)), "kigou": draw(st.permutations(kigou))}


def expected(t: dict, y: dict) -> str:
    """優先順の上から 1 つずつ問い、当たった所で返す。"""
    reg = {r["記号"].strip(): [c for c in r["要求する欄"].split("/") if c.strip()] for r in t["kigou"]}
    docs = {r["文書 id"]: r for r in t["bunsho"]}
    yid = y["約束 id"].strip()
    mine = [r for r in t["kisai"] if r["約束 id"].strip() == yid]

    def empty(s: str) -> bool:
        return s.strip() == ""

    if (empty(y["宣言側の出典"]) or any(empty(r["後の側の出典"]) for r in mine)
            or any(empty(r[c]) for r in mine for c in reg.get(r["記号"].strip(), []))
            or any(r["後の文書 id"] in docs and empty(docs[r["後の文書 id"]]["出典"]) for r in mine)):
        return "出典が空"
    if empty(y["宣言の文字列"]):
        return "宣言の文字列が空"
    if any(r["後の文書 id"] not in docs for r in mine):
        return "台帳に無い id を指す記載"
    if any(r["記号"].strip() not in reg for r in mine):
        return "登録表に無い記号"
    if sum(1 for r in t["yakusoku"] if r["約束 id"].strip() == yid) > 1:
        return "id の重複"
    kinds = [r["記号"].strip() for r in mine]
    if "済みの記載" in kinds and "読んだ範囲に記載なし" in kinds:
        return "同じ約束に (A) と (D) が同時に書かれた"
    if "済みの記載" in kinds:
        return M.YONCHI[0]
    if "次の候補に在る" in kinds or "判断待ちに在る" in kinds:
        return M.YONCHI[1]
    if "別の欄に在る" in kinds:
        return M.YONCHI[2]
    return M.YONCHI[3]


@settings(derandomize=True, database=None, max_examples=300, suppress_health_check=[HealthCheck.too_slow])
@given(表())
def test_行1つに1つだけ付き合計が合い行順に依らず入力は変わらない(t: dict) -> None:
    before = copy.deepcopy(t)
    res = M.judge(t)
    assert t == before
    rows = res["約束ごと"]
    assert all(("4 値" in r) != ("別枠" in r) for r in rows)
    assert sum(res["4 値"].values()) + sum(res["別枠"].values()) == len(t["yakusoku"]) == len(rows)
    assert sorted(r.get("4 値") or r["別枠"] for r in rows) == sorted(expected(t, y) for y in t["yakusoku"])
    for it in res["項目ごと"]:
        assert sum(it["内訳"].values()) == it["約束の数"] == sum(1 for y in t["yakusoku"] if y["項目 id"].strip() == it["項目 id"])
    rev = copy.deepcopy(t)
    rev["kisai"] = list(reversed(rev["kisai"]))
    assert M.judge(rev) == res
