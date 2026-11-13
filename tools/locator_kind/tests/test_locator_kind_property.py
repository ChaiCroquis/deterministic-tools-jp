"""locator_kind の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 出どころ 1 件には、区分 5 つか別枠の理由 6 つのうち 1 つだけが付き、その合計は出どころの件数に
等しく、表の行順を入れ替えても答えは変わらず、型に当てた文字列は (A) の出どころにだけ返り、渡した表は 1 文字も
書き換わらない。

5 枚の表は乱数で作る(空の出典、登録に無い記号、台帳に無い型 id、重複した置き場 id、台帳に無い出どころ id、
型と合わない場所を混ぜる)。区分はこのテストの中で別の書き方で引き直して比べる(locator_kind.judge の中の
関数は呼ばない)。道具の側は出どころごとに上から関門を通す書き方、テストの側は先に全ての印を集合で作ってから
最後に 1 回だけ引く書き方にした。derandomize=True で毎回同じ入力列、database=None で例を保存しない。
"""
from __future__ import annotations

import copy
import sys
from collections import Counter
from pathlib import Path

from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import locator_kind as L  # noqa: E402

出典 = st.sampled_from(["手引き 1 行目", "手引き 2 行目", "", "  "])
多めの出典 = st.sampled_from(["手引き 1 行目"] * 5 + ["手引き 2 行目"] * 4 + [""])
記号 = st.sampled_from([L.K_PATTERN, L.K_PATTERN, L.K_HAND, L.K_UPSTREAM, "配布元が送る", "知らない記号", ""])
型id = st.sampled_from(["T1", "T2", "T3", "T1", "T2", "T9", "", "", ""])
年度 = st.sampled_from(["R6", "R7", "2024", "2025", "9", "10", "第3期", ""])
出どころid = st.sampled_from(["S1", "S2", "S3", "S4", "S5", "S6"])
型の候補 = {"T1": "a_{N}.csv", "T2": "{N}/b.html", "T3": "c{N}c{N}.pdf"}


@st.composite
def 表(draw: st.DrawFn) -> dict[str, list[dict[str, str]]]:
    kinds = [{"記号": k, "意味": "x", "出典": draw(多めの出典)}
             for k in (L.K_PATTERN, L.K_HAND, L.K_UPSTREAM, "配布元が送る")]
    patterns = [{"型 id": k, "型": v, "印に入れる欄名": "年度の記号", "出典": draw(多めの出典)}
                for k, v in 型の候補.items() if draw(st.integers(0, 4)) > 0]
    ids = sorted(draw(st.sets(出どころid, max_size=6)))
    origins = [{"出どころ id": i, "領域": draw(st.sampled_from(["表", ""])), "決まり方の記号": draw(記号),
                "型 id": draw(型id), "足す人と機会": draw(st.sampled_from(["人が足す", ""])),
                "版の記録の在り所": draw(st.sampled_from(["指紋の欄", ""])), "出典": draw(多めの出典)} for i in ids]
    places = []
    for n in range(draw(st.integers(0, 10))):
        oid, k = draw(st.sampled_from(["S1", "S2", "S3", "S4", "S5", "S6", "S1", "S2", "S8"])), draw(年度)
        mine = [o["型 id"] for o in origins if o["出どころ id"] == oid and o["型 id"] in 型の候補]
        tid = mine[0] if mine else draw(st.sampled_from(list(型の候補)))
        fit = 型の候補[tid].replace("{N}", k)
        where = draw(st.sampled_from([fit, fit, fit, fit, fit + "x", ""]))
        places.append({"置き場 id": draw(st.sampled_from([f"P{n}"] * 9 + ["P0"])), "出どころ id": oid,
                       "年度の記号": k, "場所": where, "出典": draw(多めの出典)})
    deps = [{"rule id": draw(st.sampled_from(["U1", "U2", "U3"])),
             "出どころ id": draw(st.sampled_from(["S1", "S2", "S3", "S4", "S9"])), "出典": draw(出典)}
            for _ in range(draw(st.integers(0, 6)))]
    return {"places": draw(st.permutations(places)), "origins": draw(st.permutations(origins)),
            "kinds": kinds, "patterns": patterns, "deps": deps}


def 引き直す(t: dict[str, list[dict[str, str]]]) -> dict[str, str]:
    """区分か別枠の理由を、出どころ id ごとに 1 つ返す。locator_kind の判定は使わない。"""
    有る = lambda s: s.strip() != ""  # noqa: E731
    登録 = {r["記号"] for r in t["kinds"] if 有る(r["出典"])}
    型 = {r["型 id"]: r["型"] for r in t["patterns"] if 有る(r["出典"])}
    台帳 = {r["出どころ id"]: r for r in t["origins"]}
    使う = [p for p in t["places"] if 有る(p["出典"]) and p["出どころ id"] in 台帳]
    回数 = Counter(p["置き場 id"] for p in 使う)
    重複の主 = {p["出どころ id"] for p in 使う if 回数[p["置き場 id"]] >= 2}
    持つ = Counter(p["出どころ id"] for p in 使う)
    合わない主 = {p["出どころ id"] for p in 使う
              if 台帳[p["出どころ id"]]["型 id"] in 型
              and p["場所"] != p["年度の記号"].join(型[台帳[p["出どころ id"]]["型 id"]].split("{N}"))}
    答え: dict[str, str] = {}
    for oid, o in 台帳.items():
        s, tid = o["決まり方の記号"], o["型 id"]
        印 = [not 有る(o["出典"]), 有る(s) and s not in 登録, oid in 重複の主, 有る(tid) and tid not in 型,
             s == L.K_PATTERN and not 有る(tid)]
        if any(印):
            答え[oid] = L.BETSU[印.index(True)]
        elif s == L.K_PATTERN and 持つ[oid] > 0:
            答え[oid] = L.KUBUN[1] if oid in 合わない主 else L.KUBUN[0]
        elif s == L.K_HAND and not 有る(tid):
            答え[oid] = L.KUBUN[2]
        elif s == L.K_UPSTREAM and 持つ[oid] == 0 and not 有る(tid):
            答え[oid] = L.KUBUN[3]
        else:
            答え[oid] = L.KUBUN[4]
    for r in t["deps"]:
        if 有る(r["出典"]) and r["出どころ id"] not in 台帳:
            答え[r["出どころ id"]] = L.BETSU[5]
    return 答え


@settings(max_examples=300, derandomize=True, database=None, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(t=表(), kigou=年度)
def test_いつも成り立つこと_答えは1つで合計は件数に等しく行順で変わらずAにだけ文字列が返り入力を書き換えない(
        t: dict[str, list[dict[str, str]]], kigou: str) -> None:
    before = copy.deepcopy(t)
    res = L.judge(t, kigou)
    rows = res["出どころごと"]
    got = {r["出どころ id"]: r["区分"] or r["別枠の理由"] for r in rows}
    for r in rows:
        assert (r["区分"] in L.KUBUN) != (r["別枠の理由"] in L.BETSU)
        event(r["区分"][:3] or "別枠")
    assert len(got) == len(rows)
    assert got == 引き直す(t)
    assert sum(res["区分"].values()) + sum(res["別枠"].values()) == len(rows) == res["分母(出どころの件数)"]
    rev = L.judge({k: list(reversed(v)) for k, v in copy.deepcopy(t).items()}, kigou)
    assert rev == res
    a_ids = sorted(k for k, v in got.items() if v == L.KUBUN[0])
    applied = res["型に当てた文字列"]["出どころ"]
    assert [x["出どころ id"] for x in applied] == a_ids
    assert all(x["型に当てた文字列"] == kigou.join(x["型"].split("{N}")) for x in applied)
    assert t == before
