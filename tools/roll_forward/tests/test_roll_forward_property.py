"""roll_forward の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 読んだ結果は 2 通りしかない。
  (a) 回ごとに区分が 1 つ付き、4 値の合計が回の件数に等しく、どの回の累計も
      「前の回の累計 + 増 − 減」(増減の欄が無い回は前の回の累計のまま)に等しくて負にならず、
      当たる回が在る宣言はその回の累計が総数に等しく、当たる回なしの宣言の総数はどの累計とも違い、
      替わった件数をいくつ増やしても累計は動かない
  (b) 1 回も歩かずに理由コードが 1 つ以上返り、区分は全て 0 になる
どちらの場合も入力は 1 文字も書き換わらない。

累計の足し直しと宣言の突き合わせは roll_forward の関数を使わず、このテストの中で別に書く。
derandomize=True で毎回同じ入力列、database=None で見つけた例を保存しない。
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

from hypothesis import event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import roll_forward as R  # noqa: E402

STATUSES = [
    {"status": "S1", "meaning": "通った", "needs_delta": "要る", "source": "合成の登録(架空)L1"},
    {"status": "S2", "meaning": "落ちた", "needs_delta": "要らない", "source": "合成の登録(架空)L2"},
]

件数 = st.sampled_from(["0", "0", "1", "2", "5", "40"])
減る件数 = st.sampled_from(["0", "0", "0", "1", "2"])
困る件数 = st.sampled_from(["-1", "1.5", "", "x", "1,0"])


@st.composite
def 三表(draw: st.DrawFn):
    n = draw(st.integers(1, 6))
    runs = []
    for i in range(n):
        blank = i > 0 and draw(st.integers(0, 4)) == 0
        a, d, c = ("", "", "") if blank else (draw(件数), draw(減る件数), draw(件数))
        runs.append({"run_id": f"R{i + 1:02d}", "run_at": f"T{i + 1:02d}", "status": "S2" if blank else "S1",
                     "added": a, "removed": d, "changed": c, "opening": "期首" if i == 0 else "",
                     "unit": "行", "source": f"合成の履歴(架空)L{i + 1}"})
    claims = [{"claim_id": f"C{k + 1}", "total": str(draw(st.integers(0, 90))), "unit": "行",
               "quote": "架空の文", "source": f"合成の状況(架空)L{k + 1}"}
              for k in range(draw(st.integers(1, 3)))]
    # 半分弱の回で 1 か所だけ崩す(止まる 6 つの理由それぞれに道を付ける)
    kind = draw(st.sampled_from(["そのまま"] * 7 + ["E1", "E2", "E3", "E4", "E5", "E6"]))
    i = draw(st.integers(0, n - 1))
    if kind == "E1":
        runs[i]["source"] = ""
    elif kind == "E2":
        runs[i]["status"] = "S9"
    elif kind == "E3":
        runs[0]["opening"] = ""
    elif kind == "E4":
        runs[i]["added"] = draw(困る件数)
    elif kind == "E5":
        runs[i]["removed"] = "9999"
        if runs[i]["added"] == "":
            runs[i]["added"], runs[i]["changed"] = "0", "0"
    elif kind == "E6":
        claims[0]["unit"] = "件"
    return runs, claims


def 足し直す(runs: list[dict]) -> list[int]:
    """道具の関数を使わない足し直し。欄が無い回は前の回のまま。"""
    total, out = 0, []
    for r in sorted(runs, key=lambda r: r["run_id"]):
        if r["added"] != "":
            total = total + int(r["added"]) - int(r["removed"])
        out.append(total)
    return out


@settings(max_examples=200, derandomize=True, database=None, deadline=None)
@given(三表())
def test_always_two_outcomes(tables):
    runs, claims = tables
    snap = copy.deepcopy((runs, STATUSES, claims))
    res = R.roll(runs, STATUSES, claims)
    assert (runs, STATUSES, claims) == snap                      # 入力は書き換わらない

    if not res["ok"]:                                            # (b)
        event("b: 1 回も歩かずに止まる")
        assert len(res["止まった理由"]) >= 1
        assert all(v == 0 for v in res["区分"].values())
        assert res["別枠(1 回も歩かずに止まった回)"] == len(runs)
        assert res["回"] == [] and res["宣言"] == []
        return

    event("a: 歩いた")                                           # (a)
    rows = res["回"]
    assert len(rows) == len(runs)
    assert sum(res["区分"].values()) == len(runs)
    assert all(r["区分"] in R.CLASSES for r in rows)
    mine = 足し直す(runs)
    assert [r["その回の累計"] for r in rows] == mine
    assert all(v >= 0 for v in mine)
    prev = 0
    for r, src in zip(rows, sorted(runs, key=lambda r: r["run_id"])):
        assert r["前の回の累計"] == prev
        if src["added"] == "":
            assert r["区分"] == R.CLASS_D and r["その回の累計"] == prev and r["増"] == R.NO_FIELD
        else:
            assert r["区分"] != R.CLASS_D
            assert r["その回の累計"] == prev + int(src["added"]) - int(src["removed"])
        prev = r["その回の累計"]

    walked = {r["run_id"]: v for r, v in zip(sorted(runs, key=lambda r: r["run_id"]), mine) if r["added"] != ""}
    assert len(res["宣言"]) == len(claims)
    for c in res["宣言"]:
        want = [rid for rid, v in walked.items() if v == c["総数"]]
        if want:
            assert c["累計が一致した回"] == want
        else:
            assert c["累計が一致した回"] == R.NO_HIT
            assert all(v != c["総数"] for v in walked.values())
            assert all((c["総数"] - d) in walked.values() for d in c["最も近い累計との差(宣言 − 累計)"])
    totals = {int(c["total"]) for c in claims}
    assert [u["累計"] for u in res["文書に現れない累計"]] == sorted(set(walked.values()) - totals)

    bumped = copy.deepcopy(runs)                                 # 替わった件数は累計を動かさない
    for r in bumped:
        if r["changed"] != "":
            r["changed"] = str(int(r["changed"]) + 3)
    assert [r["その回の累計"] for r in R.roll(bumped, STATUSES, claims)["回"]] == mine
