"""arrow_split の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 結果は 2 通りしかない。
  (a) 記載 1 行ごとに、4 値・割らない記号・別枠のどれか 1 つだけが付き、その合計が記載の台帳の行数に等しく、
      割る印の無い記号の行は前と後に割られず、割られた行の前と後は記載の文字列を矢印の字 1 つで切った左右
      そのままで、4 表の行順を入れ替えても判定部分が同じバイト列になる
  (b) 1 行も数えずに、理由コードが 1 つ返る
どちらの場合も 4 表は書き換わらない。

4 表は小さな語彙から乱数で作る(id の重複・空の出典・登録表に無い記号・矢印の無い文字列・矢印 2 つ・
収録の台帳に無い行を指す対・2 語以外の状態・3 値以外の側が、どれも出るようにしてある)。
derandomize=True で毎回同じ入力列を使い、database=None で見つけた例を保存しない。

区分の決め方は arrow_split.check を使わず、このテストの中で別に書く。道具の判定が壊れても、
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
import arrow_split as M  # noqa: E402

記号の語 = ["前後の値", "後だけ", "対応", "行き先", "値上げ"]
文字列 = st.sampled_from(["3%→5%", "上限 60→65 歳", "1/3→1/2 等", "帯→等級", "来月から 9% へ", "1→2→3", " a → b ", "→", ""])
出典 = st.sampled_from(["文書 L1", "文書 L2", "文書 L3", ""])
出典_多くは在る = st.sampled_from(["記録 L1", "記録 L2", "記録 L3", "記録 L4", "記録 L5", "記録 L6", "記録 L7", ""])

記載 = st.fixed_dictionaries({
    "entry_id": st.sampled_from(["E1", "E2", "E3", "E4", "E5", "E6"]),
    "rule": st.sampled_from(["r1", "r2"]), "field": st.sampled_from(["改定", "備考"]),
    "text": 文字列, "symbol": st.sampled_from(記号の語),
    "date_text": st.sampled_from(["2024-04", ""]), "source": 出典,
})
記号 = st.fixed_dictionaries({
    "symbol": st.sampled_from(記号の語[:4]), "split": st.sampled_from(["割る", "割る", ""]), "source": 出典_多くは在る,
})
収録 = st.fixed_dictionaries({
    "cov_id": st.sampled_from(["K1", "K2", "K3", "K4", "K5", "K6", "K7", "K8"]), "rule": st.sampled_from(["r1", "r2"]),
    "state": st.sampled_from(["収録", "収録", "収録", "未収録", "未収録", "未収録", "たぶん"]), "source": 出典_多くは在る,
})
対 = st.fixed_dictionaries({
    "entry_id": st.sampled_from(["E1", "E2", "E3", "E4", "E9"]), "cov_id": st.sampled_from(["K1", "K2", "K3", "K9"]),
    "side": st.sampled_from(["前", "前", "後", "後", "", "", "両方"]), "source": 出典_多くは在る,
})


def 別に書いた区分(e: dict, entries: list[dict], symbols: list[dict], coverage: list[dict], pairs: list[dict]) -> str:
    """道具の check を呼ばずに、1 行の区分を決め直す。"""
    割る印 = {s["symbol"]: s["split"] == "割る" for s in symbols}
    状態 = {c["cov_id"]: c["state"] for c in coverage}
    if sum(1 for x in entries if x["entry_id"] == e["entry_id"]) > 1:
        return "別枠"
    if e["source"] == "" or e["symbol"] not in 割る印:
        return "別枠"
    本数 = len(e["text"].split("→")) - 1
    if 割る印[e["symbol"]] and 本数 != 1:
        return "別枠"
    私の対 = [p for p in pairs if p["entry_id"] == e["entry_id"]]
    if any(p["cov_id"] not in 状態 for p in 私の対):
        return "別枠"
    if not 割る印[e["symbol"]]:
        return "割らない"
    if any(状態[p["cov_id"]] == "未収録" for p in 私の対):
        return "C"
    側 = {p["side"] for p in 私の対}
    if "前" in 側 and "後" in 側:
        return "A"
    return "B" if 私の対 else "D"


def 道具の区分(row: dict) -> str:
    if row["区分"].startswith("別枠: "):
        return "別枠"
    if row["区分"] == M.NOSPLIT:
        return "割らない"
    return row["区分"][1]


@settings(max_examples=300, derandomize=True, database=None, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(entries=st.lists(記載, min_size=1, max_size=6),
       symbols=st.lists(記号, min_size=1, max_size=3, unique_by=lambda s: s["symbol"]) | st.lists(記号, min_size=1, max_size=4),
       coverage=st.lists(収録, max_size=3, unique_by=lambda c: c["cov_id"]) | st.lists(収録, max_size=4),
       pairs=st.lists(対, max_size=4))
def test_いつも成り立つこと_行ごとに1つの区分か_理由コードか(entries, symbols, coverage, pairs) -> None:
    saved = copy.deepcopy((entries, symbols, coverage, pairs))
    out = M.check(entries, symbols, coverage, pairs)
    if out["ok"]:
        event("(a) 行ごとに 1 つの区分")
        rows = out["記載"]
        assert len(rows) == len(entries)
        want = sorted((e["entry_id"], e["text"], e["symbol"], e["source"],
                       別に書いた区分(e, entries, symbols, coverage, pairs)) for e in entries)
        got = sorted((r["記載 id"], r["記載"], r["意味の記号"], r["出典"], 道具の区分(r)) for r in rows)
        assert got == want
        n4 = sum(1 for r in rows if 道具の区分(r) in "ABCD")
        n割らない = sum(1 for r in rows if 道具の区分(r) == "割らない")
        n別枠 = sum(1 for r in rows if 道具の区分(r) == "別枠")
        assert n4 + n割らない + n別枠 == len(entries)
        assert sum(out["4 値"].values()) == n4 and out["割らない記号の件数"] == n割らない
        assert sum(out["別枠"].values()) == n別枠
        for r in rows:
            if 道具の区分(r) in "ABCD":
                左, 右 = r["記載"].split("→")
                assert (r["前"], r["後"]) == (左.strip(), 右.strip())
            else:
                assert (r["前"], r["後"]) == ("", "")
        逆 = M.check(entries[::-1], symbols[::-1], coverage[::-1], pairs[::-1])
        assert 逆["sha256"] == out["sha256"]
    else:
        event("(b) 理由コードで止まる")
        assert out["記載"] == [] and out["止まった理由"] in M.STOPS
        assert "4 値" not in out and "sha256" not in out
    assert (entries, symbols, coverage, pairs) == saved
