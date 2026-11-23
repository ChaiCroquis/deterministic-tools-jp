"""halt_depth の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 結果は 2 通りしかない。
  (a) 回 1 行ごとに、区分 5 値か別枠のどれか 1 つだけが付き、その合計が回の台帳の行数に等しく、
      印が「在る」と返るのは登録した字が行頭にそのまま在る行だけで、行の内訳の合計がエラーの欄の行数に戻り、
      伏せる字を含む行の中身はどの欄にも出ず、登録表の行順を入れ替えても判定部分が同じバイト列になる
  (b) 1 回も並べずに、理由コードが 1 つ返る
どちらの場合も 4 表は書き換わらない。

4 表は小さな語彙から乱数で作る(回 id の重複・空の出典・空の印・登録表に無い段・重なる並び順・
伏せる字に含まれる印・2 語以外の種類・整数でない並び順が、どれも出るようにしてある)。
derandomize=True で毎回同じ入力列を使い、database=None で見つけた例を保存しない。

区分と在る・無いの決め方は halt_depth.check を使わず、このテストの中で別に書く。道具の判定が壊れても、
このテストで気づけるようにするため。
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import halt_depth as M  # noqa: E402

SECRET = "ひみつ"            # 伏せる字。この字を含む行は、出力のどこにも出てはいけない
行 = st.sampled_from([
    "aa: 1", "aa: 2", "bb: 1", "  cc x", "  cc y", "STOP", "STOP: z", "other", "", " aa: 1", "AA: 1",
    f"aa: {SECRET} 9", f"  at {SECRET}/p.py", f"zz {SECRET}",
])
# 印が順に出て止まる形の記録(途中から後ろを落とす・止まった印を落とす・伏せる行を挟む、が出る)
通しの記録 = st.tuples(st.integers(min_value=1, max_value=5), st.booleans(), st.booleans()).map(
    lambda t: "\n".join(["aa: 1", "bb: 1", "  cc x", "  cc y", "at q"][:t[0]] + (["STOP: z"] if t[1] else [])
                        + ([f"  at {SECRET}/p.py", ""] if t[2] else [])))
出典 = st.sampled_from(["記録 L1", "記録 L2", "記録 L3", "記録 L4", "記録 L5", "記録 L6", "記録 L7", ""])

回 = st.fixed_dictionaries({
    "run_id": st.sampled_from(["r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9", "r10", "r11", "r12"]),
    "status": st.sampled_from(["failed", "ok", "error"]),
    "error": st.one_of(st.lists(行, min_size=0, max_size=6).map("\n".join), 通しの記録, 通しの記録),
    "source": 出典,
})
POOL = [
    {"mark_id": "K1", "text": "aa:", "stage": "S1", "order": "1", "kind": "通過の印", "source": "登録"},
    {"mark_id": "K2", "text": "bb:", "stage": "S1", "order": "2", "kind": "通過の印", "source": "登録"},
    {"mark_id": "K3", "text": "  cc", "stage": "S2", "order": "3", "kind": "通過の印", "source": "登録"},
    {"mark_id": "K4", "text": "STOP", "stage": "S2", "order": "4", "kind": "止まった印", "source": "登録"},
    {"mark_id": "K5", "text": "at", "stage": "S1", "order": "5", "kind": "通過の印", "source": "登録"},
    {"mark_id": "K6", "text": "STOP:", "stage": "S2", "order": "6", "kind": "止まった印", "source": "登録"},
]
# 崩し方(どれか 1 つを 1 行に当てる。None は崩さない)。前の 5 つは別枠、後ろの 3 つは理由コードで止まる側
崩し = st.sampled_from([None, None, None, None, None, None, ("text", ""), ("source", ""), ("stage", "S8"), ("order", "1"),
                       ("order", "4"), ("kind", "たぶん"), ("order", "x"), ("mark_id", "K1")])


def _印を崩す(args: tuple) -> list[dict]:
    ms, how, at = args
    ms = [dict(m) for m in ms]
    if ms and how is not None:
        ms[at % len(ms)][how[0]] = how[1]
    return ms


印の表 = st.tuples(st.one_of(st.just(POOL[:4]), st.just([POOL[0], POOL[1], POOL[5]]), st.just(POOL[::-1]),
                           st.lists(st.sampled_from(POOL), min_size=0, max_size=6, unique_by=lambda m: m["mark_id"])),
                  崩し, st.integers(min_value=0, max_value=5)).map(_印を崩す)
段の表 = st.sampled_from([
    [{"stage": "S1", "name": "取込", "source": "登録"}, {"stage": "S2", "name": "照合", "source": "登録"}],
    [{"stage": "S2", "name": "照合", "source": "登録"}, {"stage": "S1", "name": "取込", "source": "登録"}],
    [{"stage": "S1", "name": "取込", "source": "登録"}, {"stage": "S2", "name": "照合", "source": "登録"}],
    [{"stage": "S1", "name": "取込", "source": "登録"}],
    [],
    [{"stage": "S1", "name": "取込", "source": "登録"}, {"stage": "S1", "name": "照合", "source": "登録"}],
    [{"stage": "S1", "name": "", "source": "登録"}],
])
伏せる表 = st.lists(st.fixed_dictionaries({"text": st.sampled_from([SECRET, SECRET, f"  at {SECRET}", "p.py"]),
                                        "source": st.sampled_from(["登録"] * 9 + [""])}), min_size=0, max_size=2)


def 別に書いた止まり方(marks: list[dict], stages: list[dict], hides: list[dict]) -> bool:
    """道具を呼ばずに、登録の側が崩れているか(= 理由コードで止まるはずか)を決め直す。"""
    ids = [m["mark_id"] for m in marks]
    if "" in ids or len(ids) != len(set(ids)):
        return True
    if any(m["kind"] not in ("通過の印", "止まった印") for m in marks):
        return True
    if any(not m["order"].lstrip("-").isdigit() for m in marks):
        return True
    syms = [s["stage"] for s in stages]
    if len(syms) != len(set(syms)) or any(not (s["stage"] and s["name"] and s["source"]) for s in stages):
        return True
    return any(not (h["text"] and h["source"]) for h in hides)


def 別に書いた使える印(marks: list[dict], stages: list[dict], hides: list[dict]) -> list[dict]:
    syms = {s["stage"] for s in stages}
    orders = [int(m["order"]) for m in marks]
    ok = []
    for m in marks:
        if not m["text"] or not m["source"] or m["stage"] not in syms:
            continue
        if orders.count(int(m["order"])) > 1:
            continue
        if any(m["text"] in h["text"] for h in hides):
            continue
        ok.append(m)
    return ok


def 別に書いた区分(r: dict, usable: list[dict]) -> tuple[str, dict[str, list[int]]]:
    """道具を呼ばずに、1 回の区分の記号と、印ごとの行番号を決め直す。"""
    if r["error"] == "":
        return "D", {m["mark_id"]: [] for m in usable}
    lines = r["error"].replace("\r\n", "\n").split("\n")
    where = {m["mark_id"]: [n for n, line in enumerate(lines, 1) if line[:len(m["text"])] == m["text"]] for m in usable}
    got = {i for i, ns in where.items() if ns}
    if not got:
        return "C", where
    halts = [m["mark_id"] for m in usable if m["kind"] == "止まった印"]
    passes = [m["mark_id"] for m in usable if m["kind"] == "通過の印"]
    if not any(i in got for i in halts):
        return "E", where
    return ("A" if all(i in got for i in passes) else "B"), where


@settings(max_examples=300, derandomize=True, database=None, deadline=None,
          suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much])
@given(runs=st.lists(回, min_size=1, max_size=5), marks=印の表, stages=段の表, hides=伏せる表)
def test_いつも成り立つこと(runs: list[dict], marks: list[dict], stages: list[dict], hides: list[dict]) -> None:
    before = copy.deepcopy((runs, marks, stages, hides))
    out = M.check(runs, marks, stages, hides)
    assert (runs, marks, stages, hides) == before                      # どちらの場合も 4 表は書き換わらない

    if 別に書いた止まり方(marks, stages, hides):
        event("(b) 理由コードで止まる")
        assert out["ok"] is False
        assert out["理由コード"] in M.REASONS and out["回"] == []           # 1 回も並べない
        assert "区分" not in out
        return

    event("(a) 並べる")
    assert out["ok"] is True
    usable = 別に書いた使える印(marks, stages, hides)
    assert sorted(out["印ごとの在る回数"]) == sorted(m["mark_id"] for m in usable)

    # 回 1 行ごとに、区分 5 値か別枠のどれか 1 つだけ。合計が回の台帳の行数に等しい
    ids = [r["run_id"] for r in runs]
    expect_box = [r for r in runs if ids.count(r["run_id"]) > 1 or r["source"] == ""]
    expect_cls = [r for r in runs if ids.count(r["run_id"]) == 1 and r["source"] != ""]
    assert len(out["回"]) == len(expect_cls) and len(out["別枠の回"]) == len(expect_box)
    assert sum(out["区分"].values()) + sum(out["別枠"]["回"].values()) == len(runs)
    assert [r["回"] for r in out["回"]] == [r["run_id"] for r in expect_cls]           # 回の台帳の順

    hide_texts = [h["text"] for h in hides]
    total_lines = 0
    for r, got in zip(expect_cls, out["回"]):
        cls, where = 別に書いた区分(r, usable)
        assert got["区分"][1] == cls
        assert got["区分"] in M.CLASSES.values()
        event(f"区分 {cls}")
        # 印が「在る」と返るのは、登録した字が行頭にそのまま在る行だけ
        assert {p["印"]: p["行番号"] for p in got["印"]} == where
        orders = [p["並び順"] for p in got["印"]]
        assert orders == sorted(orders)                                         # 印の並び順
        lines = r["error"].split("\n") if r["error"] else []
        for p in got["印"]:
            text = next(m["text"] for m in usable if m["mark_id"] == p["印"])
            for n, tail in zip(p["行番号"], p["後ろの文字列"]):
                line = lines[n - 1]
                if any(h in line for h in hide_texts):
                    assert tail == ""                                           # 伏せた行は後ろの文字列を返さない
                else:
                    assert text + tail == line                                  # 原文のまま
        # 行の内訳の合計が、エラーの欄の行数に戻る
        n_hidden = sum(1 for line in lines if any(h in line for h in hide_texts))
        assert got["行数"] == len(lines) and got["伏せた行の件数"] == n_hidden
        assert got["印に当たった行の件数"] + got["伏せた行の件数"] + got["空の行の件数"] + got["どの印にも当たらなかった行の件数"] == len(lines)
        total_lines += len(lines)
    assert out["行の内訳"]["行数の合計"] == total_lines

    # 伏せる字を含む行の中身は、どの欄にも出ない(出力の文字列で伏せる字を含むのは、登録した印の字そのものだけ)
    leaked = []

    def walk(x: object, key: str = "") -> None:
        if isinstance(x, dict):
            for k, v in x.items():
                walk(v, k)
        elif isinstance(x, list):
            for v in x:
                walk(v, key)
        elif isinstance(x, str) and key != "印の文字列" and any(h in x for h in hide_texts):
            leaked.append((key, x))

    walk(out["回"])
    assert leaked == []
    if out["別枠の回"]:
        event("別枠の回が在る")
    if out["別枠の印"]:
        event("別枠の印が在る")
    if any(h in line for r in expect_cls for line in r["error"].split("\n") for h in hide_texts):
        event("伏せた行が在る")

    # 登録表の行順を入れ替えても、判定部分が同じバイト列になる
    again = M.check(runs, marks[::-1], stages[::-1], hides[::-1])
    assert json.dumps(again, ensure_ascii=False, sort_keys=True) == json.dumps(out, ensure_ascii=False, sort_keys=True)
