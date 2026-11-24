"""part_sum の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 内訳の台帳の 1 行は、`入れる` で足された / `入れない` で 2 列目にだけ足された /
数の付いていない項目として名前だけ出た / 別枠に出た / 属する総数が無く別枠に出た、のどれか 1 つにだけ入り、
総数ごとに **足した数(入れるだけ)= `入れる` の項目の数の和**、**足した数(入れないも)= それに
`入れない` の項目の数を足したもの**、**差 = 総数の宣言 − 足した数** で、数の付いていない項目と
別枠の行はどの和も 1 も動かさない。

内訳は乱数で作る(総数 1〜3 個、内訳 0〜12 行)。数の字は整数・桁区切りつき・空・「各 4」のような
掛け算の字・小数から引き、読みの種類は登録の 3 つと登録に無い字から引き、出典は 5 回に 1 回くらい空にし、
項目id はわざと狭い範囲から引いて重複を起こす。derandomize=True で毎回同じ入力列を使い、
database=None で例を保存しない。

**足し算と行の仕分けはテストの側で別に書いている**(部品の tally / parse_int を期待値づくりに使わない)。
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

from hypothesis import event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import part_sum as P  # noqa: E402

KINDS = [{"読みの種類": "そのまま写した", "足す側": "入れる"},
         {"読みの種類": "掛けて読んだ", "足す側": "入れない"},
         {"読みの種類": "記載なし", "足す側": "数が無い"}]
SIDE = {"そのまま写した": "入れる", "掛けて読んだ": "入れない", "記載なし": "数が無い"}

数の字 = st.one_of(
    st.integers(0, 2000).map(str),
    st.integers(1000, 99999).map(lambda n: f"{n:,}"),
    st.just(""),
    st.sampled_from(["各 4", "4×4", "3 種", "1.5", "１２", "-2", "12,34"]),
)
内訳の行 = st.fixed_dictionaries({
    "項目id": st.integers(1, 9).map(lambda n: f"p{n}"),
    "総数id": st.sampled_from(["T1", "T2", "T3", "T9"]),
    "項目の名前": st.sampled_from(["甲", "乙", "丙 2 種", "丁/戊"]),
    "数": 数の字,
    "単位": st.sampled_from(["", "", "点", "箱"]),
    "読みの種類": st.sampled_from(["そのまま写した", "そのまま写した", "掛けて読んだ", "記載なし", "たぶん"]),
    "出典": st.sampled_from(["合成 L1", "合成 L2", "合成 L3", "合成 L4", ""]),
})
総数の表 = st.integers(1, 3).flatmap(lambda k: st.tuples(*[st.integers(0, 5000)] * k)).map(
    lambda ns: [{"総数id": f"T{i + 1}", "数": str(n), "単位": "点", "出典": "合成 L0"} for i, n in enumerate(ns)])


def 別に読む(s: str) -> int | None:
    """テストの側の整数読み(半角の数字と、3 桁ごとのカンマだけ)。"""
    if s == "":
        return None
    body = s.split(",")
    if not all(b.isascii() and b.isdigit() for b in body):
        return None
    if len(body) > 1 and not (1 <= len(body[0]) <= 3 and all(len(b) == 3 for b in body[1:])):
        return None
    return int("".join(body))


@settings(max_examples=300, derandomize=True, database=None, deadline=None)
@given(totals=総数の表, parts=st.lists(内訳の行, max_size=12))
def test_いつも成り立つこと_どの行も1か所にだけ入り_和は入れると入れないだけで決まる(
        totals: list[dict[str, str]], parts: list[dict[str, str]]) -> None:
    before = copy.deepcopy((totals, parts, KINDS))
    r = P.tally(totals, parts, KINDS)
    assert (totals, parts, KINDS) == before          # 入力を書き換えない

    ids = [t["総数id"] for t in totals]
    count = {}
    for p in parts:
        count[p["項目id"]] = count.get(p["項目id"], 0) + 1

    # テストの側の仕分け
    strict = {i: 0 for i in ids}
    wide = {i: 0 for i in ids}
    unnumbered = {i: 0 for i in ids}
    n_betsu = 0
    for p in parts:
        side = SIDE.get(p["読みの種類"])
        n = 別に読む(p["数"])
        ng = (side is None or p["総数id"] not in ids or p["出典"] == "" or count[p["項目id"]] > 1
              or (p["数"] != "" and n is None) or ((side == "数が無い") != (n is None)))
        if ng:
            n_betsu += 1
        elif side == "入れる":
            strict[p["総数id"]] += n
            wide[p["総数id"]] += n
        elif side == "入れない":
            wide[p["総数id"]] += n
        else:
            unnumbered[p["総数id"]] += 1

    assert [t["総数id"] for t in r["総数ごと"]] == ids
    placed = len(r["別枠"])
    for t, src in zip(r["総数ごと"], totals):
        i, total = t["総数id"], int(src["数"])
        assert t["足した数_入れるだけ"] == strict[i]
        assert t["足した数_入れないも"] == wide[i]
        assert t["差_入れるだけ"] == total - strict[i]
        assert t["差_入れないも"] == total - wide[i]
        assert t["数の付いていない項目数"] == unnumbered[i] == len(t["数の付いていない項目"])
        placed += t["入れるの項目数"] + t["入れないの項目数"] + t["数の付いていない項目数"]
        want = (("A" if strict[i] == total else "B") if unnumbered[i] == 0
                else ("C" if strict[i] <= total else "D"))
        assert t["区分_入れるだけ"][0] == want
        assert sum(b["入れるの小計"] for b in t["出典の行ごとの小計"]) == strict[i]
    assert len(r["別枠"]) == n_betsu == sum(r["別枠の件数"].values())
    assert placed == len(parts) == r["内訳の台帳の行数"]   # どの行も 1 か所にだけ入る
    event(f"別枠 {'あり' if n_betsu else 'なし'} / 数なし {'あり' if any(unnumbered.values()) else 'なし'}")

    # 数の付いていない項目と別枠の行を全部消しても、和と差は 1 も動かない
    betsu_rows = {b["行"] for b in r["別枠"]}
    kept = [p for k, p in enumerate(parts, start=1)
            if k not in betsu_rows and SIDE.get(p["読みの種類"]) != "数が無い"]
    r2 = P.tally(totals, kept, KINDS)
    assert not r2["別枠"]
    for t, t2 in zip(r["総数ごと"], r2["総数ごと"]):
        assert t2["足した数_入れるだけ"] == t["足した数_入れるだけ"]
        assert t2["足した数_入れないも"] == t["足した数_入れないも"]
        assert t2["差_入れないも"] == t["差_入れないも"]
