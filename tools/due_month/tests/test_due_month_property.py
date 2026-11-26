"""due_month の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

行の表・台帳・対応・比べ方を乱数で作る。出典・予定・rule はわざと壊し(空・日付でない字・重複)、別枠にも十分通す。
derandomize=True で毎回同じ入力列を使い、database=None で例を保存しない。
**区分の決め方はテストの側で別に書いている**(部品の judge の中身を期待値づくりに使わない)。
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from hypothesis import event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import due_month as D  # noqa: E402

日付 = st.sampled_from(["2023-04-01", "2023-08-01", "2024-04-01", "2024-08-01", "2025-03-31", "2025-04-01", "2026-04-01"])
予定 = st.sampled_from(["", "", "2024-04-01", "2025-08-01", "2026-04-01", "2026-08-01", "2027-03-31", "来年"])
名 = st.sampled_from(["甲", "甲", "乙", "乙", "丙", "丁", ""])
元 = st.sampled_from(["写し1", "写し2", ""])


@st.composite
def 表(draw: st.DrawFn):
    rows = [{"rule": draw(名), "valid_from": draw(日付), "予定": draw(予定), "出どころ": draw(元),
             "元の行数": draw(st.sampled_from(["", "1", "3"])), "出典": draw(st.sampled_from(["x"] * 9 + [""]))}
            for _ in range(draw(st.integers(1, 9)))]
    ledgers = [{"台帳id": f"台帳{i}", "種別": draw(st.sampled_from(["自前", "上流"])), "数表id": "s",
                "予定": draw(予定), "出典": draw(st.sampled_from(["x", "x", "x", ""]))} for i in range(draw(st.integers(0, 3)))]
    pairs = draw(st.lists(st.tuples(st.sampled_from(["写し1", "写し2"]), st.sampled_from(["台帳0", "台帳1", "台帳9"])),
                          unique=True, max_size=4))
    links = [{"出どころ": a, "台帳id": b, "出典": "x"} for a, b in pairs]
    compare = [{"比べ方": draw(st.sampled_from(["どれかの行", "どれかの行", "最後の行", "最後の行", "近い行"])),
                "出典": draw(st.sampled_from(["x", "x", "x", "x", ""]))}]
    return rows, ledgers, links, compare, draw(st.permutations(rows))


def 日付か(s: str) -> bool:
    return len(s) == 10 and s[:4].isdigit() and s[4] == "-" and s[7] == "-"


def 別に決める(rows: list[dict], compare: list[dict]) -> dict[str, str]:
    """rule → 区分(A〜D か「別枠」)。その rule の行と比べ方だけを見る。"""
    way = compare[0]["比べ方"] if compare[0]["比べ方"] in ("どれかの行", "最後の行") and compare[0]["出典"] else None
    out = {}
    for rule in {r["rule"] for r in rows if r["rule"]}:
        mine = [r for r in rows if r["rule"] == rule]
        dup = max(Counter((r["valid_from"], r["出どころ"]) for r in mine).values()) > 1
        bad = any(r["出典"] == "" for r in mine) or any(r["予定"] and not 日付か(r["予定"]) for r in mine)
        if dup or bad:
            out[rule] = "別枠"
            continue
        dated = sorted(r["予定"] for r in mine if r["予定"])
        if not dated:
            out[rule] = "D"
            continue
        last = max(r["valid_from"] for r in mine)
        if dated[0] <= last:
            out[rule] = "C"
        elif way is None:
            out[rule] = "別枠"
        else:
            md = {last[5:]} if way == "最後の行" else {r["valid_from"][5:] for r in mine}
            out[rule] = "A" if dated[0][5:] in md else "B"
    return out


@given(表())
@settings(max_examples=300, derandomize=True, database=None, deadline=None)
def test_each_rule_lands_in_exactly_one_place_decided_by_its_own_rows(t):
    rows, ledgers, links, compare, shuffled = t
    res = D.judge(rows, ledgers, links, compare)
    placed = [x["rule"] for x in res["rules"]] + [x["rule"] for x in res["別枠"]["rule"]]
    expect = 別に決める(rows, compare)
    # どの rule も 1 か所にだけ入る
    assert sorted(placed) == sorted(expect)
    assert len(placed) == len(set(placed))
    # 区分は、その rule の行の開始日・予定と、登録した比べ方だけで決まる
    got = {x["rule"]: x["区分"] for x in res["rules"]}
    got.update({x["rule"]: "別枠" for x in res["別枠"]["rule"]})
    assert got == expect
    # 行順を入れ替えても、台帳と対応を空にしても、区分は動かない
    assert D.digest(D.judge(shuffled, ledgers, links, compare)) == D.digest(res)
    bare = D.judge(rows, [], [], compare)
    bare_got = {x["rule"]: x["区分"] for x in bare["rules"]}
    bare_got.update({x["rule"]: "別枠" for x in bare["別枠"]["rule"]})
    assert bare_got == expect
    # 件数の検算
    n = res["件数"]
    assert sum(v["rule"] for v in n["区分"].values()) + n["別枠の rule"] == n["rule の種類"] == len(expect)
    for c in sorted(set(expect.values())):
        event(f"区分 {c}")
