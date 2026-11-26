"""due_month の単体テスト。記事に載せた件数は test_measure_* の assert で固定している(値が変われば記事も変える)。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import due_month as D  # noqa: E402

FX = ROOT / "fixtures"


def load(name: str, compare: str = "compare.csv"):
    d = FX / name
    return [D.read_csv(d / f) for f in ("rows.csv", "ledgers.csv", "links.csv", compare)]


def cats(res: dict) -> dict[str, int]:
    return {c: res["件数"]["区分"][c]["rule"] for c in "ABCD"}


def by_rule(res: dict) -> dict[str, dict]:
    return {x["rule"]: x for x in res["rules"]}


def row(rule="表", vf="2024-04-01", plan="2025-04-01", origin="写し", n="1", src="x"):
    return {"rule": rule, "valid_from": vf, "予定": plan, "出どころ": origin, "元の行数": n, "出典": src}


ANY = [{"比べ方": "どれかの行", "出典": "x"}]
LAST = [{"比べ方": "最後の行", "出典": "x"}]


# ---- 記事に載せた測定値(私の記録から起こした 3 表) ----
def test_measure_suuhyo_table_size():
    res = D.judge(*load("suuhyo"))
    assert res["件数"]["rule の種類"] == 45
    assert res["件数"]["行の表の行"] == 343
    assert res["件数"]["元の行"] == 1681
    assert len(load("suuhyo")[1]) == 10          # 台帳の表(自前 3 + 上流 7)
    assert len(load("suuhyo")[2]) == 10          # 対応の登録表


def test_measure_suuhyo_categories_any():
    res = D.judge(*load("suuhyo"))
    assert cats(res) == {"A": 12, "B": 21, "C": 1, "D": 11}
    assert {c: res["件数"]["区分"][c]["元の行"] for c in "ABCD"} == {"A": 1428, "B": 136, "C": 4, "D": 113}
    assert {c: res["件数"]["区分"][c]["行"] for c in "ABCD"} == {"A": 258, "B": 63, "C": 4, "D": 18}
    assert res["件数"]["別枠の rule"] == 0


def test_measure_suuhyo_categories_last():
    res = D.judge(*load("suuhyo", "compare_last.csv"))
    assert cats(res) == {"A": 11, "B": 22, "C": 1, "D": 11}
    moved = [r for r, x in by_rule(D.judge(*load("suuhyo"))).items() if x["区分"] != by_rule(res)[r]["区分"]]
    assert moved == ["地域別最低賃金"]


def test_measure_suuhyo_minimum_wage_spread():
    x = by_rule(D.judge(*load("suuhyo")))["地域別最低賃金"]
    assert len(x["開始日"]) == 231
    assert len(x["月日"]) == 48
    assert x["開始日"][-1] == "2026-03-31"
    assert x["予定"] == ["2026-10-01"]
    assert x["元の行数"] == 1079


def test_measure_suuhyo_marks():
    res = D.judge(*load("suuhyo"))
    assert res["件数"]["印"] == {"台帳の予定と違う": 28, "予定が 2 通り以上": 0, "既に持っている行の開始日と同じ": 1}
    assert res["件数"]["台帳ごとの違う rule"] == {"自前:koyou_kyufu": 20, "自前:nenkin": 8}
    koyou = [x for x in res["rules"] if any(t["台帳id"] == "自前:koyou_kyufu" and not t["同じ"] for t in x["台帳"])]
    assert sorted({x["区分"] for x in koyou}) == ["A", "B"]
    assert [x["rule"] for x in koyou if x["区分"] == "A"] == ["所定給付日数"]
    assert len([x for x in koyou if x["区分"] == "B"]) == 19
    # 上流の台帳とは、結んだ全ての rule で同じ日付
    assert all(t["同じ"] for x in res["rules"] for t in x["台帳"] if t["種別"] == "上流")
    assert sum(1 for x in res["rules"] if any(t["種別"] == "上流" for t in x["台帳"])) == 36


def test_measure_suuhyo_b_month_days():
    res = D.judge(*load("suuhyo"))
    b = [x for x in res["rules"] if x["区分"] == "B"]
    assert sum(1 for x in b if x["月日"] == ["08-01"] and x["予定"] == ["2027-04-01"]) == 19
    assert sorted(x["rule"] for x in b if x["月日"] == ["04-01"] and x["予定"] == ["2027-03-01"]) == [
        "子ども子育て拠出金率", "子ども子育て支援金率"]


def test_measure_suuhyo_c_and_d():
    res = D.judge(*load("suuhyo"))
    c = [x for x in res["rules"] if x["区分"] == "C"]
    assert [x["rule"] for x in c] == ["標準報酬月額等級表_厚年"]
    assert c[0]["印"]["既に持っている行の開始日と同じ"] is True
    d = [x for x in res["rules"] if x["区分"] == "D"]
    assert sum(1 for x in d if x["出どころ"] == ["extract_nenkin.py"]) == 8
    assert sum(1 for x in d if x["出どころ"] == [""]) == 1
    assert sum(1 for x in d if x["rule"].startswith("消費税率")) == 2
    assert by_rule(res)["国民年金保険料_月額"]["開始日"] == ["2026-04-01", "2027-04-01"]


def test_measure_suuhyo_side():
    s = D.judge(*load("suuhyo"))["別枠"]
    assert s["対応"] == [{"出どころ": "extract_nenkin.py", "台帳id": "上流:pension", "理由": [D.R_LINK]}]
    assert (len(s["rule"]), len(s["行"]), len(s["台帳"]), len(s["比べ方"])) == (0, 0, 0, 0)


def test_measure_gousei():
    res = D.judge(*load("gousei"))
    assert res["件数"]["rule の種類"] == 8
    assert res["件数"]["行の表の行"] == 13
    assert cats(res) == {"A": 3, "B": 1, "C": 2, "D": 2}
    assert res["件数"]["印"] == {"台帳の予定と違う": 4, "予定が 2 通り以上": 1, "既に持っている行の開始日と同じ": 1}
    last = D.judge(*load("gousei")[:3], LAST)
    assert cats(last) == {"A": 2, "B": 2, "C": 2, "D": 2}


def test_measure_kowashita():
    res = D.judge(*load("kowashita"))
    s = res["別枠"]
    assert (len(s["rule"]), len(s["行"]), len(s["対応"]), len(s["比べ方"])) == (4, 1, 1, 1)
    reasons = {r for x in s["rule"] for r in x["理由"]} | {x["理由"] for x in s["行"]}
    reasons |= {r for x in s["対応"] for r in x["理由"]} | {x["理由"] for x in s["比べ方"]}
    assert reasons == {D.R_DATE, D.R_RULE, D.R_LINK, D.R_SRC, D.R_CMP, D.R_DUP}
    assert cats(res) == {"A": 0, "B": 0, "C": 1, "D": 1}
    assert res["件数"]["rule の種類"] == 6


# ---- 区分の決まり方 ----
def test_plan_equal_to_last_start_is_c():
    res = D.judge([row(vf="2024-04-01", plan="2024-04-01")], [], [], ANY)
    assert res["rules"][0]["区分"] == "C" and res["rules"][0]["印"]["既に持っている行の開始日と同じ"]


def test_plan_before_last_without_same_start():
    res = D.judge([row(vf="2024-04-01", plan="2023-12-31")], [], [], ANY)
    assert res["rules"][0]["区分"] == "C" and not res["rules"][0]["印"]["既に持っている行の開始日と同じ"]


def test_any_and_last_differ_only_when_older_row_matches():
    rows = [row(vf="2023-04-01"), row(vf="2024-07-01")]
    assert D.judge(rows, [], [], ANY)["rules"][0]["区分"] == "A"
    assert D.judge(rows, [], [], LAST)["rules"][0]["区分"] == "B"


def test_two_plans_use_earliest_and_mark():
    rows = [row(vf="2024-04-01", plan="2025-07-01", origin="甲"), row(vf="2023-04-01", plan="2025-04-01", origin="乙")]
    x = D.judge(rows, [], [], ANY)["rules"][0]
    assert x["区分"] == "A" and x["印"]["予定が 2 通り以上"] and x["予定"] == ["2025-04-01", "2025-07-01"]


def test_empty_and_dated_plans_mixed_is_not_d():
    rows = [row(vf="2024-04-01", plan=""), row(vf="2023-04-01", plan="2025-08-01")]
    x = D.judge(rows, [], [], ANY)["rules"][0]
    assert x["区分"] == "B" and x["印"]["予定が 2 通り以上"]


def test_ledger_mark_returns_both_dates_untouched():
    led = [{"台帳id": "自前:甲", "種別": "自前", "数表id": "甲", "予定": "2025-08-01", "出典": "x"}]
    lnk = [{"出どころ": "写し", "台帳id": "自前:甲", "出典": "x"}]
    x = D.judge([row()], led, lnk, ANY)["rules"][0]
    assert x["台帳"] == [{"出どころ": "写し", "台帳id": "自前:甲", "種別": "自前", "数表id": "甲",
                         "台帳の予定": "2025-08-01", "行の予定": ["2025-04-01"], "同じ": False}]
    assert x["予定"] == ["2025-04-01"] and x["区分"] == "A"      # 区分は台帳に寄らない


def test_ledger_with_bad_date_is_not_linked():
    led = [{"台帳id": "自前:甲", "種別": "自前", "数表id": "甲", "予定": "夏ごろ", "出典": "x"}]
    lnk = [{"出どころ": "写し", "台帳id": "自前:甲", "出典": "x"}]
    res = D.judge([row()], led, lnk, ANY)
    assert res["rules"][0]["台帳"] == [] and res["別枠"]["台帳"][0]["理由"] == [D.R_DATE]
    assert res["別枠"]["対応"][0]["理由"] == [D.R_LINK]


def test_compare_without_source_goes_aside():
    res = D.judge([row()], [], [], [{"比べ方": "どれかの行", "出典": ""}])
    assert res["rules"] == [] and res["別枠"]["rule"][0]["理由"] == ["比べ方の登録の出典が空"]


def test_input_is_not_mutated():
    rows = [row(n="")]
    before = [dict(r) for r in rows]
    D.judge(rows, [], [], ANY)
    assert rows == before


@pytest.mark.parametrize("bad", [
    lambda t: t[0].append({"rule": "表"}),                                   # 列が無い
    lambda t: t[0].append(row(vf="2024/04/01")),                             # valid_from が日付でない
    lambda t: t[0].append(row(n="0")),                                       # 元の行数
    lambda t: t[1].extend([dict(台帳id="甲", 種別="自前", 数表id="", 予定="", 出典="x")] * 2),   # 台帳id の重複
    lambda t: t[2].extend([dict(出どころ="写し", 台帳id="甲", 出典="x")] * 2),                   # 同じ対応が 2 行
    lambda t: t[3].append({"比べ方": "最後の行", "出典": "x"}),              # 比べ方が 2 行
])
def test_unreadable_tables_stop(bad):
    t = [[row()], [], [], list(ANY)]
    bad(t)
    with pytest.raises(D.TableError):
        D.judge(*t)


def test_verify_all_fixtures():
    for name in ("suuhyo", "gousei", "kowashita"):
        assert all(ok for _, ok in D.verify(*load(name))), name


def test_no_today_no_network_in_source():
    src = (ROOT / "due_month.py").read_text(encoding="utf-8")
    for word in ("today(", "now(", "urllib", "socket", "requests", "json.load"):
        assert word not in src, word


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "due_month.py"), *args],
                          capture_output=True, text=True, encoding="utf-8")


def cli(name: str, *extra: str) -> subprocess.CompletedProcess:
    d = FX / name
    return run("--rows", str(d / "rows.csv"), "--ledgers", str(d / "ledgers.csv"),
               "--links", str(d / "links.csv"), "--compare", str(d / "compare.csv"), *extra)


def test_cli_exit_codes(tmp_path):
    r = cli("suuhyo", "--verify")
    assert r.returncode == 3 and r.stdout.count(": 合う") == 5 and "合わない" not in r.stdout
    quiet = tmp_path / "rows.csv"
    quiet.write_text("rule,valid_from,予定,出どころ,元の行数,出典\n表,2024-04-01,2025-04-01,写し,1,x\n", encoding="utf-8")
    empty_l = tmp_path / "l.csv"
    empty_l.write_text("台帳id,種別,数表id,予定,出典\n", encoding="utf-8")
    empty_k = tmp_path / "k.csv"
    empty_k.write_text("出どころ,台帳id,出典\n", encoding="utf-8")
    cmp_ = tmp_path / "c.csv"
    cmp_.write_text("比べ方,出典\n最後の行,x\n", encoding="utf-8")
    ok = run("--rows", str(quiet), "--ledgers", str(empty_l), "--links", str(empty_k), "--compare", str(cmp_), "--verify")
    assert ok.returncode == 0
    ng = run("--rows", str(tmp_path / "無い.csv"), "--ledgers", str(empty_l), "--links", str(empty_k), "--compare", str(cmp_))
    assert ng.returncode == 2
