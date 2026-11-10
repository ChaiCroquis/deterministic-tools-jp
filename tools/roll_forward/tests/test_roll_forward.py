"""roll_forward の試験。合成した 3 表(fixtures/*_a.csv)だけを使う。記事に載せる数は assert == で固定する。"""
from __future__ import annotations

import ast
import copy
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
import roll_forward as R  # noqa: E402


def load():
    return (R.read_table(FX / "runs_a.csv", R.RUN_COLS), R.read_table(FX / "statuses_a.csv", R.STATUS_COLS),
            R.read_table(FX / "claims_a.csv", R.CLAIM_COLS))


def by_id(res):
    return {r["回"]: r for r in res["回"]}


# ---------- 記事に載せる測定値 ----------

def test_measure_13_runs_split_into_four():
    runs, statuses, claims = load()
    res = R.roll(runs, statuses, claims)
    assert res["ok"] is True
    assert len(runs) == 13 and len(statuses) == 2 and len(claims) == 4
    assert res["分母(回の件数)"] == 13
    counts = res["区分"]
    assert counts[R.CLASS_A] == 4
    assert counts[R.CLASS_B] == 5
    assert counts[R.CLASS_C] == 2
    assert counts[R.CLASS_D] == 2
    assert sum(counts.values()) + res["別枠(1 回も歩かずに止まった回)"] == 13
    print(f"\n[measure] 回 13 行 / 状態の記号 2 行 / 宣言 4 行 → 区分 (A) 4 / (B) 5 / (C) 2 / (D) 2、別枠 0、合計 13")


def test_measure_cumulative_walk():
    res = R.roll(*load())
    cum = [r["その回の累計"] for r in res["回"]]
    assert cum == [1301, 1301, 1301, 1301, 1302, 1301, 1301, 1501, 1681, 1681, 1681, 1681, 1681]
    # 道具の関数を使わずに足し直す
    runs, _, _ = load()
    total, mine = 0, []
    for r in sorted(runs, key=lambda r: r["run_id"]):
        if r["added"] != "":
            total += int(r["added"]) - int(r["removed"])
        mine.append(total)
    assert mine == cum
    print(f"[measure] 累計の列 = {cum}")


def test_measure_claims_hit_runs():
    res = R.roll(*load())
    c = {x["宣言"]: x for x in res["宣言"]}
    assert c["C1"]["累計が一致した回"] == ["R01", "R02", "R06", "R07"]
    assert c["C1"]["引き継ぎで同じ値の回(欄が無い)"] == ["R03", "R04"]
    assert c["C2"]["累計が一致した回"] == ["R09", "R10", "R11", "R12", "R13"]
    assert c["C3"]["累計が一致した回"] == c["C2"]["累計が一致した回"]
    assert c["C4"]["累計が一致した回"] == R.NO_HIT
    assert c["C4"]["最も近い累計との差(宣言 − 累計)"] == [19]
    assert res["当たる回が在る宣言の件数 / 宣言の総件数"] == "3 / 4"
    print("[measure] 宣言 4 件のうち当たる回が在るもの 3 件。1301 は 4 回 + 引き継ぎ 2 回、1681 は 5 回、"
          "1700 は当たる回なし(最も近い累計 1681 との差 +19)")


def test_measure_unseen_cumulatives():
    res = R.roll(*load())
    assert res["文書に現れない累計"] == [{"累計": 1302, "回": ["R05"]}, {"累計": 1501, "回": ["R08"]}]
    print("[measure] 文書に現れない累計は 2 つ = 1302(R05)と 1501(R08)")


def test_measure_net_and_gross_side_by_side():
    rows = by_id(R.roll(*load()))
    assert rows["R08"]["区分"] == R.CLASS_C
    assert (rows["R08"]["純増減"], rows["R08"]["総増減"]) == (200, 482)
    assert rows["R12"]["区分"] == R.CLASS_C
    assert (rows["R12"]["純増減"], rows["R12"]["総増減"]) == (0, 24)
    assert rows["R12"]["その回の累計"] == rows["R12"]["前の回の累計"] == 1681
    print("[measure] R08 は増 341 / 減 141 で純増減 200・総増減 482。R12 は増 12 / 減 12 で純増減 0・総増減 24"
          "(累計は 1681 のまま動かない)")


def test_measure_changed_does_not_move_cumulative():
    runs, statuses, claims = load()
    base = R.roll(runs, statuses, claims)
    assert by_id(base)["R13"]["替わった件数(累計に入れない)"] == 4
    assert by_id(base)["R13"]["区分"] == R.CLASS_B
    changed_total = sum(r["替わった件数(累計に入れない)"] for r in base["回"] if r["区分"] != R.CLASS_D)
    assert changed_total == 7
    bumped = copy.deepcopy(runs)
    for r in bumped:
        if r["changed"] != "":
            r["changed"] = str(int(r["changed"]) + 5)
    got = R.roll(bumped, statuses, claims)
    assert [r["その回の累計"] for r in got["回"]] == [r["その回の累計"] for r in base["回"]]
    assert [r["区分"] for r in got["回"]] == [r["区分"] for r in base["回"]]
    print("[measure] 替わった件数は 13 回の合計で 7 件。全部の回で 5 ずつ増やしても、累計も区分も 1 つも動かない")


def test_measure_no_field_is_not_zero():
    res = R.roll(*load())
    rows = by_id(res)
    for rid in ("R03", "R04"):
        assert rows[rid]["区分"] == R.CLASS_D
        assert rows[rid]["増"] == R.NO_FIELD and rows[rid]["減"] == R.NO_FIELD
        assert rows[rid]["その回の累計"] == rows[rid]["前の回の累計"] == 1301
        assert R.NO_FIELD in rows[rid]["印"]
    # 0 と書いた回は (B) で、(D) とは別の値
    assert rows["R02"]["区分"] == R.CLASS_B and rows["R02"]["増"] == 0
    assert res["登録と欄の有無が食い違う回"] == []
    print("[measure] 落ちた 2 回(R03 / R04)は (D)。増も減も「欄が無い」で、累計は前の回の 1301 を引き継ぐ")


def test_measure_verify_five_things():
    v = R.verify(*load())
    assert v["ok"] is True
    assert len(v["見たもの"]) == 5
    assert all(x["結果"] == "合う" for x in v["見たもの"])
    assert v["見たもの"][3]["中身"] == "写し 11 枚"
    assert v["見たもの"][4]["中身"].startswith("写し 10 枚")
    print(f"[measure] verify 5 つとも合う。+1 の写し 11 枚、空にした写し 10 枚。判定部分の sha256 の先頭は {v['見たもの'][0]['中身']}")


def test_measure_tail_lines_cannot_be_removed():
    res = R.roll(*load())
    assert len(res["持たせていないもの"]) == 9
    assert res["持たせていないもの"] == R.TAIL
    for word in ("正しい側", "一致率", "原因"):
        keys = [k for k in res if k != "持たせていないもの"]
        assert not any(word in k for k in keys)


# ---------- 止まる 6 つの理由 ----------

def _break(code):
    runs, statuses, claims = load()
    if code == "E1":
        runs[4]["source"] = ""
    elif code == "E2":
        runs[4]["status"] = "S9"
    elif code == "E3":
        runs[0]["opening"] = ""
    elif code == "E4":
        runs[4]["added"] = "-1"
    elif code == "E5":
        runs[1]["removed"] = "1400"
    elif code == "E6":
        claims[0]["unit"] = "rule"
    return runs, statuses, claims


@pytest.mark.parametrize("code", ["E1", "E2", "E3", "E4", "E5", "E6"])
def test_six_reasons_stop_without_walking(code):
    res = R.roll(*_break(code))
    assert res["ok"] is False
    assert code in {x["理由コード"] for x in res["止まった理由"]}
    assert all(v == 0 for v in res["区分"].values())
    assert res["別枠(1 回も歩かずに止まった回)"] == 13
    assert res["回"] == [] and res["宣言"] == [] and res["文書に現れない累計"] == []


def test_measure_six_reason_codes():
    assert len(R.REASONS) == 6
    print("[measure] 止まる理由コードは 6 個で、6 個すべてに崩した表で道がある。止まった表では区分は全て 0、別枠が 13")


@pytest.mark.parametrize("bad", ["1.5", "1,301", "１２", " 3", "+3", "三"])
def test_e4_rejects_non_integers(bad):
    runs, statuses, claims = load()
    runs[4]["added"] = bad
    assert "E4" in {x["理由コード"] for x in R.roll(runs, statuses, claims)["止まった理由"]}


def test_e4_partial_blank_is_not_read_as_zero():
    runs, statuses, claims = load()
    runs[4]["removed"] = ""
    assert "E4" in {x["理由コード"] for x in R.roll(runs, statuses, claims)["止まった理由"]}


def test_e3_variants():
    runs, statuses, claims = load()
    runs[1]["opening"] = R.OPENING_MARK
    assert "E3" in {x["理由コード"] for x in R.roll(runs, statuses, claims)["止まった理由"]}
    runs, statuses, claims = load()
    runs[0]["opening"], runs[1]["opening"] = "", R.OPENING_MARK
    assert "E3" in {x["理由コード"] for x in R.roll(runs, statuses, claims)["止まった理由"]}
    runs, statuses, claims = load()
    for c in ("added", "removed", "changed"):
        runs[0][c] = ""
    assert "E3" in {x["理由コード"] for x in R.roll(runs, statuses, claims)["止まった理由"]}


def test_table_errors():
    runs, statuses, claims = load()
    with pytest.raises(R.TableError):
        R.roll(runs + [dict(runs[0])], statuses, claims)
    with pytest.raises(R.TableError):
        R.roll(runs, [dict(statuses[0], meaning="たぶん通った")], claims)
    with pytest.raises(R.TableError):
        R.roll(runs, statuses, [])
    with pytest.raises(R.TableError):
        R.roll([dict(runs[0], opening="はい")] + runs[1:], statuses, claims)


def test_registry_mismatch_is_listed_not_stopped():
    runs, statuses, claims = load()
    for c in ("added", "removed", "changed"):
        runs[6][c] = ""          # R07 は S1(増減の欄が要る)なのに無い
    res = R.roll(runs, statuses, claims)
    assert res["ok"] is True
    assert res["登録と欄の有無が食い違う回"] == [{"回": "R07", "形": "登録では増減の欄が要るのに無い"}]
    assert by_id(res)["R07"]["区分"] == R.CLASS_D


def test_input_is_not_rewritten_and_order_free():
    runs, statuses, claims = load()
    snap = copy.deepcopy((runs, statuses, claims))
    a = R.roll(runs, statuses, claims)
    b = R.roll(list(reversed(runs)), list(reversed(statuses)), list(reversed(claims)))
    assert (runs, statuses, claims) == snap
    assert a["判定部分の sha256"] == b["判定部分の sha256"]
    R.verify(runs, statuses, claims)
    assert (runs, statuses, claims) == snap


def test_cli_exit_codes(tmp_path):
    args = [str(FX / "runs_a.csv"), str(FX / "statuses_a.csv"), str(FX / "claims_a.csv")]
    exe = [sys.executable, "-X", "utf8", str(ROOT / "roll_forward.py")]
    assert subprocess.run(exe + ["check"] + args, capture_output=True).returncode == 1   # C4 が当たる回なし
    assert subprocess.run(exe + ["verify"] + args, capture_output=True).returncode == 0
    only_hit = tmp_path / "claims.csv"
    lines = (FX / "claims_a.csv").read_text(encoding="utf-8").splitlines()
    only_hit.write_text("\n".join(lines[:4]) + "\n", encoding="utf-8")
    assert subprocess.run(exe + ["check"] + args[:2] + [str(only_hit)], capture_output=True).returncode == 0
    bad = tmp_path / "runs.csv"
    bad.write_text("run_id,status\nR01,S1\n", encoding="utf-8")
    assert subprocess.run(exe + ["check", str(bad)] + args[1:], capture_output=True).returncode == 2
    assert subprocess.run(exe + ["init", str(tmp_path / "hina")], capture_output=True).returncode == 0
    assert sorted(p.name for p in (tmp_path / "hina").iterdir()) == ["claims.csv", "runs.csv", "statuses.csv"]


def test_measure_no_clock_no_float_no_network():
    tree = ast.parse((ROOT / "roll_forward.py").read_text(encoding="utf-8"))
    mods = set()
    calls = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mods.add(node.module)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            calls.add(node.func.id)
    assert mods == {"__future__", "argparse", "csv", "hashlib", "json", "sys", "pathlib"}
    assert calls & {"float", "eval", "exec", "round", "open"} == {"open"}
    assert not any(isinstance(n, ast.Constant) and isinstance(n.value, float) for n in ast.walk(tree))
    assert not any(isinstance(n, ast.Div) for n in ast.walk(tree))
    print("[measure] 部品が import している module は 7 個で、時刻・乱数・通信・subprocess の module は 0 個。"
          "float の定数と割り算は 0 件")
