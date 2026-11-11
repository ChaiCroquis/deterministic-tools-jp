"""source_shift の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: どの rule にも区分 (A)(B)(C)(D) か別枠のどれか 1 つが付き、5 つの件数の合計は
rule の件数に等しい。(A) の rule は主の入れ替えのすべてに突合が 1 件以上在り、(B) の rule には突合の無い
主の入れ替えが 1 件以上在り、(C)(D) の rule には主の入れ替えが 1 件も無く、別枠の rule には理由コードが
1 つ以上付く。動きの台帳の行順を入れ替えても出力は同じで、入力は 1 文字も書き換わらない。

表は乱数で作る。rule を 1〜5 件、rule ごとに動きを 0〜3 行つなげ、主の入れ替えには半分強の確率で突合を
付ける。そのうえで 4 割ほどの表で 1 か所だけ崩す(別枠の 6 つの理由それぞれに道を付ける)。
derandomize=True で毎回同じ入力列を使う。database=None で見つけた例を保存しない。

区分の数え直しは source_shift.judge を使わず、このテストの中で別に書く(下の「別に数える」)。
道具の判定が壊れても、ここで気づけるようにするため。
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import source_shift as SS  # noqa: E402

出どころ = ["S1", "S2", "S3"]
役 = ["照合専用", "退いた", "併用"]
崩し方 = ["出典を空に", "登録に無い出どころ", "登録に無い役", "順を整数でなく", "順を重複", "線を切る",
          "役を空に", "一致が比べたを超える", "件数を負に"]


@st.composite
def 表(draw: st.DrawFn) -> dict:
    rules = [f"K{i}" for i in range(1, draw(st.integers(1, 5)) + 1)]
    sources = [{"source_id": s, "name": f"合成の出どころ {s}", "kind": draw(st.sampled_from(["原本", "上流の写し"])),
                "covers": ";".join(r for r in rules if draw(st.booleans())), "source": f"合成の登録 {s}"}
               for s in 出どころ]
    roles = [{"role": r, "meaning": "合成", "source": f"合成の登録 {r}"} for r in 役]
    moves, checks, current, seq = [], [], [], 0
    for rule in rules:
        at = ""
        for _ in range(draw(st.integers(0, 3))):
            seq += 1
            to = draw(st.sampled_from([s for s in 出どころ if s != at]))
            moves.append({"move_id": f"M{seq}", "seq": str(seq), "date_text": draw(st.sampled_from(["", "T1"])),
                          "rule": rule, "from_source": at, "to_source": to,
                          "old_role": draw(st.sampled_from(役)) if at else "",
                          "actor": "", "scope": draw(st.sampled_from(["全項目", "一部"])),
                          "source": f"合成の経緯 L{seq}"})
            if at and draw(st.integers(0, 9)) < 6:
                n = draw(st.integers(0, 50))
                checks.append({"check_id": f"C{seq}", "move_id": f"M{seq}",
                               "scope": draw(st.sampled_from(["全項目", "一部"])), "compared": str(n),
                               "matched": str(draw(st.integers(0, n))), "source": f"合成の検証 L{seq}"})
            at = to
        main = at or draw(st.sampled_from(出どころ))
        if draw(st.integers(0, 9)) < 2 and at:
            main = draw(st.sampled_from(出どころ))          # たまに、いまの由来の台帳だけ別の出どころにする
        current.append({"rule": rule, "current_source": main, "source": f"合成の収録 {rule}"})
    t = {"moves": moves, "sources": sources, "roles": roles, "checks": checks, "current": current}
    if moves and draw(st.integers(0, 9)) < 4:
        how = draw(st.sampled_from(崩し方))
        m = draw(st.sampled_from(moves))
        if how == "出典を空に":
            m["source"] = ""
        elif how == "登録に無い出どころ":
            m["to_source"] = "S9"
        elif how == "登録に無い役":
            m["old_role"] = "予備"
        elif how == "順を整数でなく":
            m["seq"] = draw(st.sampled_from(["", "一", "1.5", "+1", "１"]))
        elif how == "順を重複":
            m["seq"] = draw(st.sampled_from(moves))["seq"]
        elif how == "線を切る":
            m["from_source"] = draw(st.sampled_from(出どころ + [""]))
        elif how == "役を空に":
            m["old_role"] = ""
        elif checks:
            c = draw(st.sampled_from(checks))
            if how == "一致が比べたを超える":
                c["matched"] = str(int(c["compared"]) + 1)
            else:
                c["compared"] = "-1"
        event(f"崩した: {how}")
    return t


def 整数か(s: str) -> bool:
    return s.isascii() and s.isdigit() or (s.startswith("-") and s[1:].isascii() and s[1:].isdigit())


def 別に数える(t: dict) -> dict[str, str]:
    """rule → A / B / C / D / 別枠。source_shift の関数は 1 つも使わない。"""
    登録 = {s["source_id"] for s in t["sources"]}
    役の登録 = {r["role"] for r in t["roles"]}
    順の数: dict[object, int] = {}
    for m in t["moves"]:
        k = int(m["seq"]) if 整数か(m["seq"]) else m["seq"]
        順の数[k] = 順の数.get(k, 0) + 1
    out = {}
    for c in t["current"]:
        rule = c["rule"]
        ms = [m for m in t["moves"] if m["rule"] == rule]
        cs = [x for x in t["checks"] if x["move_id"] in {m["move_id"] for m in ms}]
        bad = c["current_source"] not in 登録
        for m in ms:
            bad |= m["source"] == "" or m["to_source"] not in 登録
            bad |= m["from_source"] != "" and m["from_source"] not in 登録
            bad |= m["old_role"] != "" and m["old_role"] not in 役の登録
            bad |= m["from_source"] != "" and m["old_role"] == ""
            bad |= not 整数か(m["seq"]) or 順の数[int(m["seq"])] > 1
        for x in cs:
            bad |= not (整数か(x["compared"]) and 整数か(x["matched"]))
            bad |= not bad and not 0 <= int(x["matched"]) <= int(x["compared"])
        if not bad:
            ms.sort(key=lambda m: int(m["seq"]))
            for i in range(1, len(ms)):
                bad |= ms[i]["from_source"] != ms[i - 1]["to_source"]
        if bad:
            out[rule] = "別枠"
            continue
        入れ替え = [m for m in ms if m["from_source"]]
        if 入れ替え:
            突合の在る動き = {x["move_id"] for x in cs}
            out[rule] = "A" if all(m["move_id"] in 突合の在る動き for m in 入れ替え) else "B"
        else:
            主 = ms[-1]["to_source"] if ms else c["current_source"]
            相手 = [s for s in t["sources"] if rule in s["covers"].split(";") and s["source_id"] != 主]
            out[rule] = "C" if 相手 else "D"
    return out


短い名 = {SS.CAT_A: "A", SS.CAT_B: "B", SS.CAT_C: "C", SS.CAT_D: "D", SS.SIDE: "別枠"}


@settings(max_examples=200, derandomize=True, database=None, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(t=表())
def test_いつも成り立つこと_区分は1つずつで合計はruleの件数(t: dict) -> None:
    snapshot = copy.deepcopy(t)
    res = SS.judge(t)
    rows = res["rule ごとの行"]
    got = {r["rule"]: 短い名[r["区分"]] for r in rows}
    want = 別に数える(t)
    assert got == want
    n = {k: sum(1 for v in got.values() if v == k) for k in ("A", "B", "C", "D", "別枠")}
    assert sum(n.values()) == len(t["current"]) == res["分母(rule の件数)"]
    assert [res["区分"][c] for c in SS.CATEGORIES] == [n["A"], n["B"], n["C"], n["D"]]
    assert res[SS.SIDE] == n["別枠"]
    突合の在る動き = {c["move_id"] for c in t["checks"]}
    for r in rows:
        入れ替え = [m["move_id"] for m in t["moves"] if m["rule"] == r["rule"] and m["from_source"]]
        if got[r["rule"]] == "A":
            assert 入れ替え and set(入れ替え) <= 突合の在る動き
        elif got[r["rule"]] == "B":
            assert set(r["突合の記載が無い入れ替え"]) == set(入れ替え) - 突合の在る動き != set()
        elif got[r["rule"]] in ("C", "D"):
            assert 入れ替え == []
        else:
            assert len(r["止まった理由"]) >= 1 and set(r["止まった理由"]) <= set(SS.REASONS)
    x = copy.deepcopy(t)
    x["moves"] = x["moves"][::-1]
    assert SS.judge(x)["判定部分の sha256"] == res["判定部分の sha256"]
    assert t == snapshot
    event("別枠が在る" if n["別枠"] else "全ての rule に区分が付いた")
    for k, v in n.items():
        if v:
            event(f"区分 {k} の rule が在る")
