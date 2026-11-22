"""call_axis の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 結果は 2 通りしかない。
  (a) 語 1 行ごとに、区分 4 値か別枠のどれか 1 つだけが付き、その合計が語の台帳の行数に等しく、
      横に置かれる記載は対の登録表に書かれた行だけで、別枠でない語は働きの記号 → 旧軸の順に並び、
      4 表の行順を入れ替えても判定部分が同じバイト列になる
  (b) 1 行も数えずに、理由コードが 1 つ返る
どちらの場合も 4 表は書き換わらない。

4 表は小さな語彙から乱数で作る(id の重複・空の出典・空の働き・登録表に無い働き・重なる旧軸の順・
台帳に無い記載や語を指す対・2 語以外の側・整数でない順が、どれも出るようにしてある)。
derandomize=True で毎回同じ入力列を使い、database=None で見つけた例を保存しない。

区分の決め方は call_axis.check を使わず、このテストの中で別に書く。道具の判定が壊れても、
このテストで気づけるようにするため。
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import call_axis as M  # noqa: E402

働きの語 = ["引く", "落とす", "選ぶ", "ばらす"]
出典 = st.sampled_from(["文書 L1", "文書 L2", "文書 L3", ""])
出典_多くは在る = st.sampled_from(["記録 L1", "記録 L2", "記録 L3", "記録 L4", "記録 L5", "記録 L6", "記録 L7", ""])

語 = st.fixed_dictionaries({
    "word_id": st.sampled_from(["W1", "W2", "W3", "W4", "W5", "W6"]),
    "word": st.sampled_from(["f", "g", "cut", "cut0"]),
    "order": st.sampled_from(["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "x"]),
    "role": st.sampled_from(働きの語 + ["引く", "落とす", ""]),
    "source": 出典,
})
働き = st.fixed_dictionaries({
    "role": st.sampled_from(働きの語[:3]), "edge": st.sampled_from(["境目", "境目", "", "", "たぶん"]), "source": 出典_多くは在る,
})
記載 = st.fixed_dictionaries({
    "note_id": st.sampled_from(["N1", "N2", "N3", "N4", "N5", "N6", "N7", "N8"]),
    "side": st.sampled_from(["式の一覧", "式の一覧", "式の一覧", "検証の表", "検証の表", "検証の表", "たぶん"]),
    "text": st.sampled_from(["cut(0.5 × 下限)", "f の境目", "帯の連続性", "g"]),
    "result": st.sampled_from(["通過", ""]), "source": 出典_多くは在る,
})
対 = st.fixed_dictionaries({
    "word_id": st.sampled_from(["W1", "W2", "W3", "W4", "W9"]), "note_id": st.sampled_from(["N1", "N2", "N3", "N9"]),
    "source": 出典_多くは在る,
})


def 別に書いた区分(w: dict, words: list[dict], roles: list[dict], notes: list[dict], pairs: list[dict]) -> tuple[str, list[str]]:
    """道具の check を呼ばずに、1 語の区分と、横に置かれる記載 id を決め直す。"""
    登録 = {r["role"] for r in roles}
    側 = {n["note_id"]: n["side"] for n in notes}
    私の対 = sorted({p["note_id"] for p in pairs if p["word_id"] == w["word_id"]})
    if sum(1 for x in words if x["word_id"] == w["word_id"]) > 1:
        return "別枠", []
    if w["source"] == "" or w["role"] == "" or w["role"] not in 登録:
        return "別枠", []
    if sum(1 for x in words if int(x["order"]) == int(w["order"])) > 1:
        return "別枠", []
    if any(i not in 側 for i in 私の対):
        return "別枠", []
    式 = any(側[i] == "式の一覧" for i in 私の対)
    検証 = any(側[i] == "検証の表" for i in 私の対)
    return ("A" if 式 and 検証 else "B" if 検証 else "C" if 式 else "D"), 私の対


def 道具の区分(row: dict) -> str:
    return "別枠" if row["区分"].startswith(M.BOX_HEAD) else row["区分"][1]


@settings(max_examples=300, derandomize=True, database=None, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(words=st.lists(語, min_size=1, max_size=6),
       roles=st.lists(働き, min_size=1, max_size=3, unique_by=lambda r: r["role"]) | st.lists(働き, min_size=1, max_size=4),
       notes=st.lists(記載, max_size=4, unique_by=lambda n: n["note_id"]) | st.lists(記載, max_size=5),
       pairs=st.lists(対, max_size=5))
def test_いつも成り立つこと_語ごとに1つの区分か_理由コードか(words, roles, notes, pairs) -> None:
    saved = copy.deepcopy((words, roles, notes, pairs))
    out = M.check(words, roles, notes, pairs)
    if out["ok"]:
        event("(a) 語ごとに 1 つの区分")
        rows = out["語"]
        assert len(rows) == len(words)
        want = sorted((w["word_id"], w["word"], int(w["order"]), w["role"], w["source"],
                       *別に書いた区分(w, words, roles, notes, pairs)) for w in words)
        got = sorted((r["語 id"], r["語"], r["旧軸の順"], r["働きの記号"], r["出典"], 道具の区分(r),
                      sorted(x["記載 id"] for x in r[M.SIDE_F] + r[M.SIDE_V])) for r in rows)
        assert got == want
        n4 = sum(1 for r in rows if 道具の区分(r) in "ABCD")
        n別枠 = sum(1 for r in rows if 道具の区分(r) == "別枠")
        assert n4 + n別枠 == len(words)
        assert sum(out["区分"].values()) == n4 and sum(out["別枠"].values()) == n別枠
        書かれた対 = {(p["word_id"], p["note_id"]) for p in pairs}
        for r in rows:
            for x in r[M.SIDE_F] + r[M.SIDE_V]:
                assert (r["語 id"], x["記載 id"]) in 書かれた対
        並び = [(r["働きの記号"], r["旧軸の順"]) for r in rows if 道具の区分(r) != "別枠"]
        assert 並び == sorted(並び)
        逆 = M.check(words[::-1], roles[::-1], notes[::-1], pairs[::-1])
        assert 逆["sha256"] == out["sha256"]
    else:
        event("(b) 理由コードで止まる")
        assert out["語"] == [] and out["止まった理由"] in M.STOPS
        assert "区分" not in out and "sha256" not in out
    assert (words, roles, notes, pairs) == saved
