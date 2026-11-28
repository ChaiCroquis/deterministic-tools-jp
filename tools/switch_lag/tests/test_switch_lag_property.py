"""switch_lag の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

行の表・見る日・比べ方を乱数で作る。出典・日付・回・セグメントはわざと壊し(空・日付でない字・重複・登録に無い値)、
別枠にも十分通す。derandomize=True で毎回同じ入力列を使い、database=None で例を保存しない。
**区分の決め方はテストの側で別に書いている**(部品の judge の中身を期待値づくりに使わない。日付は字のまま比べる)。
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from hypothesis import event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import switch_lag as S  # noqa: E402

日 = ["2030-04-01", "2030-10-01", "2030-10-15", "2030-12-20", "2031-01-10", "2031-04-01", "2031-10-01", "2031-10-20"]
開始 = st.sampled_from(日 + ["2031/04/01"])
終了 = st.sampled_from(日 + ["INF", "INF", "", "いつか"])
回 = ["一", "二", "三"]
全体 = ["甲", "乙", "丙"]


@st.composite
def 表(draw: st.DrawFn):
    rows = [{"rule": draw(st.sampled_from(["表", "表", "別表"])), "セグメント": draw(st.sampled_from(全体 + ["外"])),
             "回": draw(st.sampled_from(回 + ["九"])), "開始日": draw(開始), "終了日": draw(終了),
             "出典": draw(st.sampled_from(["x"] * 9 + [""]))} for _ in range(draw(st.integers(1, 10)))]
    picked = draw(st.lists(st.sampled_from(日 + ["2030-03-31", "2031-12-31", "来月"]), unique=True, max_size=4))
    days = [{"見る日": d, "理由": "試験", "出典": draw(st.sampled_from(["x"] * 5 + [""]))} for d in picked]
    edge = draw(st.sampled_from(["半開", "半開", "両閉", "両閉", "左閉"]))
    setup = ([{"種類": "回", "値": r, "出典": "x"} for r in 回] + [{"種類": "区間の端", "値": edge, "出典": "x"}]
             + [{"種類": "セグメント", "値": s, "出典": "x"} for s in 全体])
    return rows, days, setup, draw(st.permutations(rows)), edge


def 日付か(s: str) -> bool:
    return len(s) == 10 and s[:4].isdigit() and s[4] == "-" and s[7] == "-" and s[5:7].isdigit() and s[8:].isdigit()


def 使える行(rows: list[dict]) -> list[dict]:
    dup = Counter((r["rule"], r["セグメント"], r["回"]) for r in rows)
    return [r for r in rows if r["出典"] and 日付か(r["開始日"]) and (r["終了日"] in ("INF", "") or 日付か(r["終了日"]))
            and r["回"] in 回 and r["セグメント"] in 全体 and dup[(r["rule"], r["セグメント"], r["回"])] == 1]


def 別に決める(rows: list[dict], rule: str, seg: str, day: str, new: str, edge: str) -> str:
    """そのセグメントの行と、見る日と、回の順と、区間の端だけを見て区分を決める(ISO の日付は字の順 = 日の順)。"""
    mine = [r for r in 使える行(rows) if r["rule"] == rule and r["セグメント"] == seg]

    def 当たる(r: dict) -> bool:
        if day < r["開始日"]:
            return False
        if r["終了日"] in ("INF", ""):
            return True
        return day < r["終了日"] if edge == "半開" else day <= r["終了日"]

    hit = [回.index(r["回"]) for r in mine if 当たる(r)]
    if not hit:
        return "D"
    if max(hit) >= 回.index(new):
        return "A"
    nxt = [r for r in mine if r["回"] == new]
    return "B" if nxt and nxt[0]["開始日"] > day else "C"


@given(表())
@settings(max_examples=300, derandomize=True, database=None, deadline=None)
def test_each_segment_lands_in_exactly_one_category_decided_by_its_own_rows(t):
    rows, days, setup, shuffled, edge = t
    res = S.judge(rows, days, setup)
    good_days = sorted(d["見る日"] for d in days if d["出典"] and 日付か(d["見る日"]))
    rules = sorted({r["rule"] for r in rows})
    if edge == "左閉":
        # 区間の端が別枠なら、日ごとの表は出さない(窓だけ返す)
        assert res["日ごと"] == [] and len(res["別枠"]["比べ方"]) == 1
        event("端が別枠")
    else:
        # 見る日 × rule × 回の対 がちょうど 1 つずつ在る
        assert [(p["見る日"], p["rule"], p["新しい回"]) for p in res["日ごと"]] == \
            [(d, r, n) for d in good_days for r in rules for n in 回[1:]]
        for p in res["日ごと"]:
            got = {x["セグメント"]: x["区分"] for x in p["セグメント"]}
            # どのセグメントも 1 つの区分にだけ入り、件数の合計は全体の数と同じ
            assert sorted(got) == sorted(全体) and len(p["セグメント"]) == len(全体)
            assert sum(p["件数"].values()) == len(全体)
            assert p["件数"] == {c: list(got.values()).count(c) for c in "ABCD"}
            # 区分は、そのセグメントの行・見る日・回の順・区間の端だけで決まる
            expect = {s: 別に決める(rows, p["rule"], s, p["見る日"], p["新しい回"], edge) for s in 全体}
            assert got == expect
            # ほかのセグメントの行を除いても動かない
            for s in 全体:
                alone = S.judge([r for r in rows if r["セグメント"] == s and r["rule"] == p["rule"]], days, setup)
                mine = [x for q in alone["日ごと"] if (q["見る日"], q["新しい回"]) == (p["見る日"], p["新しい回"])
                        for x in q["セグメント"] if x["セグメント"] == s]
                assert [x["区分"] for x in mine] == ([expect[s]] if mine else [])
                if not mine:      # その rule の行が 1 つも残らないとき(行が無いので D のはず)
                    assert expect[s] == "D"
            for c in sorted(set(got.values())):
                event(f"区分 {c}")
    # 行の表の行順を入れ替えても同じ
    assert S.digest(S.judge(shuffled, days, setup)) == S.digest(res)
    # 行はどれも「使った行」か別枠のどちらか 1 か所
    assert res["件数"]["使った行"] == len(使える行(rows))
    assert res["件数"]["使った行"] + res["件数"]["別枠の行"] == len(rows)
    assert res["件数"]["回ごとの行数の合計"] == len(使える行(rows))
