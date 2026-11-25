"""label_fold の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

名前・手順・対を乱数で作る。名前id と出典はわざと壊し(重複・空・台帳に無い id)、別枠にも十分通す。
derandomize=True で毎回同じ入力列を使い、database=None で例を保存しない。
**畳み方と仕分けはテストの側で別に書いている**(部品の apply_step / _trail / _steps を期待値づくりに使わない)。
"""
from __future__ import annotations

import copy
import re
import sys
import unicodedata
from pathlib import Path

from hypothesis import event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import label_fold as L  # noqa: E402

字 = st.sampled_from(["額", "額 ", "Ａ", "A", "a", "ｶ", "カ", "　", "_", "・", "限", "１", "1"])
名 = st.lists(字, min_size=1, max_size=3).map("".join).filter(lambda s: s.strip() != "")


@st.composite
def 表(draw: st.DrawFn):
    k = draw(st.integers(1, 5))
    names = []
    for i in range(k):
        for doc in ("甲", "乙"):
            names.append({"名前id": f"{doc}{i}", "文書id": doc, "名前": draw(名), "切り方のメモ": "",
                          "出典": draw(st.sampled_from(["x", "x", "x", "x", ""]))})
    if draw(st.integers(0, 3)) == 0:
        names.append({**names[0], "名前": draw(名)})                    # 同じ名前id が 2 回
    kinds = draw(st.permutations(["NFKC", "空白を除く", "登録した記号を除く", "英字の大文字小文字を揃える", "寄せる"]))
    kinds = kinds[:draw(st.integers(0, 5))]
    steps = [{"順番": str(i), "手順の種類": x, "除く記号": "_・" if x == "登録した記号を除く" else "", "出典": "x"}
             for i, x in enumerate(kinds, 1)]
    pairs = []
    for i in range(k):
        left = draw(st.sampled_from([f"甲{i}"] * 6 + ["", "甲0", "乙0", "丙9"]))
        right = draw(st.sampled_from([f"乙{i}"] * 8 + [""]))
        pairs.append({"対id": f"p{i}", "左の名前id": left, "右の名前id": right, "読みのメモ": "",
                      "出典": draw(st.sampled_from(["x"] * 6 + [""]))})
    return names, draw(st.permutations(names)), steps, pairs


def 別に畳む(s: str, kind: str) -> str:
    if kind == "NFKC":
        return unicodedata.normalize("NFKC", s)
    if kind == "空白を除く":
        return re.sub(r"\s+", "", s)
    if kind == "登録した記号を除く":
        return s.replace("_", "").replace("・", "")
    if kind == "英字の大文字小文字を揃える":
        return re.sub("[A-Z]", lambda m: m.group().lower(), s)
    return s                                                            # 登録に無い種類は当てない


@settings(max_examples=300, derandomize=True, database=None, deadline=None)
@given(t=表())
def test_いつも成り立つこと_対は1か所にだけ入り_区分は登録した手順だけで決まる(t) -> None:
    names, shuffled, steps, pairs = t
    before = copy.deepcopy((names, steps, pairs))
    r = L.fold_pairs(names, steps, pairs)
    assert (names, steps, pairs) == before                              # 入力を書き換えない
    assert L.fold_pairs(shuffled, steps, pairs) == r or len({n["名前id"] for n in names}) < len(names)

    by = {n["名前id"]: n for n in names}
    used = [x for p in pairs for x in (p["左の名前id"], p["右の名前id"]) if x]
    all_ids = [n["名前id"] for n in names]
    want: dict[str, tuple[str, int | None]] = {}
    betsu: list[str] = []
    for p in pairs:
        ids = [x for x in (p["左の名前id"], p["右の名前id"]) if x]
        ng = (not ids or any(x not in by for x in ids) or p["出典"] == ""
              or any(by[x]["出典"] == "" or all_ids.count(x) > 1 or used.count(x) > 1 for x in ids if x in by)
              or (len(ids) == 2 and by[ids[0]]["文書id"] == by[ids[1]]["文書id"]))
        if ng:
            betsu.append(p["対id"])
            continue
        if len(ids) == 1:
            want[p["対id"]] = ("D", None)
            continue
        a, b = by[ids[0]]["名前"], by[ids[1]]["名前"]
        if a == b:
            want[p["対id"]] = ("A", None)
            continue
        want[p["対id"]] = ("C", None)
        for s in steps:
            a, b = 別に畳む(a, s["手順の種類"]), 別に畳む(b, s["手順の種類"])
            if s["手順の種類"] != "寄せる" and a == b != "":
                want[p["対id"]] = ("B", int(s["順番"]))
                break

    got = {p["対id"]: (p["区分"][0], p["同じになった段"]["順番"] if p["同じになった段"] else None) for p in r["対ごと"]}
    assert got == want
    assert [b["対id"] for b in r["別枠_対"]] == betsu
    assert len(got) + len(betsu) == len(pairs)
    for c, _ in want.values():
        event(f"区分 {c}")
