"""cohort_close の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文を検査にする。

いつも成り立つこと: 読んだ範囲は 2 通りしかない。
  (a) 4 値を付けた: rule 1 件ごとに 4 値か別枠 5 のどれか 1 つが付き、その合計 = rule の件数、
      区分 × 収録の状態の内訳の合計 = 区分の件数になる。有効期間の終わりの記載が空の rule は
      (A)(C) に入らず、線が 1 本も無い rule は (B)(C) に入らず、収録の状態を入れ替えても
      線の文字列を入れ替えても線の台帳の行順を入れ替えても、判定部分は同じバイト列になる
  (b) 1 件も数えずに理由コードが返る(4 値や sha256 を取りに行くと例外)
どちらの場合も、この部品は 4 表を 1 文字も書き換えない。

**4 値の決め方はテストの側で別に実装している**(部品の judge / counts を呼ばずに my_value で
分類し直す)。derandomize=True で毎回同じ 200 通りを使い、database=None で例を保存しない。
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import cohort_close as C  # noqa: E402

SRC = "合成のメモ(架空)L1"
SYMBOLS = [[C.SYM_BIRTH, "合成(架空)", SRC], ["年齢の線", "合成(架空)", SRC],
           [C.SYM_UNSPLIT, "合成(架空)", SRC]]
RIDS = ("R1", "R2", "R3", "R4")

row_st = st.tuples(st.sampled_from(RIDS), st.sampled_from(("", "合成の終わりの記載(架空)")),
                   st.sampled_from(("", "", C.NONE_NOTE)), st.sampled_from((SRC, SRC, SRC, "")))
line_st = st.tuples(st.sampled_from(RIDS + ("R9",)),
                    st.sampled_from(("1970-01-01 以前", "合成の線(架空)", "〜1970 年度生まれ")),
                    st.sampled_from(("", "以前", "〜")),
                    st.sampled_from((C.SYM_BIRTH, "年齢の線", C.SYM_UNSPLIT, "登録していない記号")),
                    st.sampled_from((SRC, SRC, SRC, "")))
cover_st = st.dictionaries(st.sampled_from(RIDS),
                           st.tuples(st.sampled_from(C.STATES), st.sampled_from((SRC, SRC, ""))),
                           max_size=4)
break_st = st.sampled_from((None, None, "記号の登録表が空", "収録の状態が決めた外"))


def my_value(rid: str, rows: list[list[str]], lines: list[list[str]],
             cover: list[list[str]]) -> str:
    """rule 1 件の 4 値 / 別枠をテストの側で出す(部品の judge を呼ばない)。"""
    mine_rows = [r for r in rows if r[0] == rid]
    mine = [ln for ln in lines if ln[0] == rid]
    cov = [c for c in cover if c[0] == rid]
    row = mine_rows[0]
    registered = {s[0] for s in SYMBOLS}
    if len(mine_rows) > 1:
        return "重複"
    if row[3] == "" or any(ln[4] == "" for ln in mine) or any(c[2] == "" for c in cov):
        return "出典"
    if any(ln[3] not in registered for ln in mine):
        return "記号"
    if any(ln[3] == C.SYM_UNSPLIT for ln in mine):
        return "書き分け"
    end, has_line = row[1] != "", len(mine) > 0
    if row[2] == C.NONE_NOTE and (end or has_line):
        return "同時"
    return {(True, False): "A", (False, True): "B", (True, True): "C", (False, False): "D"}[
        (end, has_line)]


LABEL = {"A": C.KUBUN[0], "B": C.KUBUN[1], "C": C.KUBUN[2], "D": C.KUBUN[3],
         "重複": C.EXTRAS[0], "出典": C.EXTRAS[1], "記号": C.EXTRAS[2], "書き分け": C.EXTRAS[3],
         "同時": C.EXTRAS[4]}


@settings(max_examples=200, derandomize=True, database=None, deadline=None)
@given(st.lists(row_st, min_size=1, max_size=5), st.lists(line_st, max_size=6), cover_st,
       break_st, st.randoms(use_true_random=False))
def test_always_true_sentence(raw_rows, raw_lines, raw_cover, broken, rnd) -> None:
    rows = [list(r) for r in raw_rows]
    lines = [list(ln) for ln in raw_lines]
    known = {r[0] for r in rows}
    cover = [[rid, s, src] for rid, (s, src) in sorted(raw_cover.items()) if rid in known]
    symbols = [list(s) for s in SYMBOLS]
    if broken == "記号の登録表が空":
        symbols = []
    elif broken == "収録の状態が決めた外" and cover:
        cover[0][1] = "たぶん収録"
    else:
        broken = None
    keep = copy.deepcopy((rows, lines, symbols, cover))

    result = C.judge(rows, lines, symbols, cover)
    out = C.check(rows, lines, symbols, cover)

    if broken:   # (b) 1 件も数えずに理由コードが返る
        assert result["ok"] is False and len(result["止まった理由"]) >= 1
        assert sum(out["4 値"].values()) + sum(out["別枠"].values()) == 0
        with pytest.raises(C.Stopped):
            C.fingerprint(result)
        with pytest.raises(C.Stopped):
            C.counts(result)
    else:        # (a) 4 値を付けた
        rule_ids = sorted(known)
        want = {rid: LABEL[my_value(rid, rows, lines, cover)] for rid in rule_ids}
        got = {r["rule_id"]: r["区分"] for r in result["rules"]}
        assert got == want
        n_four, n_extra = sum(out["4 値"].values()), sum(out["別枠"].values())
        assert n_four + n_extra == len(rule_ids) == out["rule の件数"]
        for k in C.KUBUN:
            assert sum(out["区分 × 収録の状態"][k].values()) == out["4 値"][k]
        for r in result["rules"]:
            if r["有効期間の終わりの記載"] == "":
                assert r["区分"] not in (C.KUBUN[0], C.KUBUN[2])
            if not r["線"]:
                assert r["区分"] not in (C.KUBUN[1], C.KUBUN[2])
        assert result["台帳に無い rule id"] == sorted({ln[0] for ln in lines} - known)
        fp = C.fingerprint(result)
        shuffled = list(lines)
        rnd.shuffle(shuffled)
        assert C.fingerprint(C.judge(rows, shuffled, symbols, cover)) == fp
        renamed = [[ln[0], f"別の文字 {i}", ln[2], ln[3], ln[4]] for i, ln in enumerate(lines)]
        assert C.fingerprint(C.judge(rows, renamed, symbols, cover)) == fp
        flipped = [[c[0], C.STATES[0], c[2]] for c in cover]
        after = {r["rule_id"]: r["区分"] for r in C.judge(rows, lines, symbols, flipped)["rules"]}
        assert after == got

    assert (rows, lines, symbols, cover) == keep   # どちらの場合も入力は書き換わらない


BIRTHS = st.dates(min_value=__import__("datetime").date(1900, 1, 2),
                  max_value=__import__("datetime").date(2099, 12, 30)).map(lambda d: d.isoformat())


@settings(max_examples=200, derandomize=True, database=None, deadline=None)
@given(BIRTHS, BIRTHS, st.sampled_from(("以前", "以降")), st.sampled_from(("", "生まれ", "生まれのみ")))
def test_side_follows_the_word_and_stops_without_it(edge, birth, word, tail) -> None:
    """補助の判定: 境目の日は含む側に入り、語が無ければどの日でも止まる。比較はテストの側で書く。"""
    text = f"{edge} {word}{tail}"
    y, m, d = (int(x) for x in birth.split("-"))
    ey, em, ed = (int(x) for x in edge.split("-"))
    if word == "以前":
        inside = (y, m, d) <= (ey, em, ed)
    else:
        inside = (y, m, d) >= (ey, em, ed)
    assert C.side_of(text, word, C.SYM_BIRTH, birth) == (C.SIDE_IN if inside else C.SIDE_OUT)
    assert C.side_of(text, word, C.SYM_BIRTH, edge) == C.SIDE_IN
    assert C.side_of(text, "", C.SYM_BIRTH, birth) == C.SIDE_NO_WORD
    assert C.side_of(text, "〜", C.SYM_BIRTH, birth) == C.SIDE_UNREADABLE
    assert C.side_of(text, word, "年齢の線", birth) == C.SIDE_UNREADABLE
