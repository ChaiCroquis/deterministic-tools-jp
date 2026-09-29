"""formula_table のテスト。fixture は全て合成データ(fixtures/make_fixtures.py)、率も単価も出典名も架空。

後半の test_measure_* は、同じ合成の金額に対して
  (a) 表の rounding 列で丸めを明示指定した値
  (b) 実行環境の既定に任せた値(Python の round / Decimal の既定 quantize / int による切り捨て)
を突き合わせ、食い違う組み合わせを数える。記事の数値はここから取る。
決定論なので(乱数を使っていない)、値が変われば記事の数字も変える。
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FX))
import formula_table as F  # noqa: E402
import make_fixtures as MF  # noqa: E402

TABLE = FX / "keisan.csv"
VALUES = FX / "atai.csv"
BROKEN = FX / "keisan_fuseigou.csv"

ON_2025 = date(2025, 6, 1)          # 改正前(折半額 v1)
ON_2026 = date(2026, 4, 1)          # 改正後(折半額 v2)
PUBLISHED = date(2026, 2, 10)       # 合成の改正通知の公表日


@pytest.fixture(scope="module")
def ft() -> F.FormulaTable:
    return F.FormulaTable.load(TABLE)


@pytest.fixture(scope="module")
def vt() -> F.ValueTable:
    return F.ValueTable.load(VALUES)


# ---------------------------------------------------------------- 表の読み込み

def test_clean_table_shape(ft: F.FormulaTable, vt: F.ValueTable) -> None:
    assert len(ft) == 12
    assert len(vt) == 7
    assert ft.ids() == ["折半額", "給付日額", "年額", "月額", "免除判定",
                        "測定_50銭以下切捨て", "測定_1円未満切捨て",
                        "測定_円未満四捨五入", "測定_丸めない"]


def test_row_numbers_are_one_origin(ft: F.FormulaTable) -> None:
    assert [r.number for r in ft.rows][:3] == [1, 2, 3]
    assert ft.rows[-1].number == 12


def test_fixtures_are_reproducible() -> None:
    """fixture が生成器から決定論的に出る(ディスク上の CSV と突き合わせる)。"""
    import csv
    import io

    def rendered(columns: list[str], rows: list[dict]) -> str:
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=columns, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
        return buf.getvalue()

    assert rendered(MF.F_COLUMNS, MF.formulas_clean()) == TABLE.read_text(encoding="utf-8")
    assert rendered(MF.V_COLUMNS, MF.values_clean()) == VALUES.read_text(encoding="utf-8")
    assert rendered(MF.F_COLUMNS, MF.formulas_broken()) == BROKEN.read_text(encoding="utf-8")


@pytest.mark.parametrize("drop", F.FORMULA_REQUIRED)
def test_missing_column_is_a_table_error(drop: str) -> None:
    rec = {c: "x" for c in MF.F_COLUMNS if c != drop}
    with pytest.raises(F.TableError, match="必要な列が無い"):
        F.FormulaTable.from_records([rec])


def test_empty_known_from_is_a_table_error() -> None:
    rec = {c: "" for c in MF.F_COLUMNS}
    rec.update({"id": "x", "expr": "1", "rounding": "丸めない", "priority": "0"})
    with pytest.raises(F.TableError, match="known_from が空"):
        F.FormulaTable.from_records([rec])


@pytest.mark.parametrize("spec", ["報酬", "報酬=case", "報酬=なにか:報酬月額", "=case:報酬月額"])
def test_broken_inputs_spec_is_a_table_error(spec: str) -> None:
    with pytest.raises(F.TableError):
        F.parse_inputs(spec, "行 1")


# ---------------------------------------------------------------- 丸めの registry

def test_the_component_has_no_default_rounding() -> None:
    """丸めは表の rounding 列からしか来ない。既定の丸めを持たない。"""
    import inspect
    sig = inspect.signature(F.evaluate)
    assert "rounding" not in sig.parameters
    assert "fallback" not in sig.parameters
    assert set(F.ROUNDINGS) == {"50銭以下切捨て", "1円未満切捨て", "円未満四捨五入", "丸めない"}


@pytest.mark.parametrize("name,x,want", [
    ("50銭以下切捨て", "4471.50", "4471"),
    ("50銭以下切捨て", "4471.51", "4472"),
    ("50銭以下切捨て", "4472.50", "4472"),
    ("50銭以下切捨て", "4472.00", "4472"),
    ("1円未満切捨て", "4471.99", "4471"),
    ("1円未満切捨て", "4471.00", "4471"),
    ("円未満四捨五入", "4471.50", "4472"),
    ("円未満四捨五入", "4472.50", "4473"),
    ("円未満四捨五入", "4471.49", "4471"),
    ("丸めない", "4471.50", "4471.50"),
])
def test_each_rounding_name_is_its_own_rule(name: str, x: str, want: str) -> None:
    assert str(F.ROUNDINGS[name](Decimal(x))) == want


def test_the_environment_default_differs_at_the_half(ft: F.FormulaTable, vt: F.ValueTable) -> None:
    """端数ちょうど 0.5 で、表の指定と実行環境の既定が分かれることを固定する。"""
    case = {"報酬月額": "110000", "料率": "8.13"}
    raw = Decimal(F.evaluate(ft, "測定_丸めない", case, ON_2025, values=vt).value)
    assert str(raw) == "4471.50"
    assert F.evaluate(ft, "測定_50銭以下切捨て", case, ON_2025, values=vt).value == "4471"
    assert F.evaluate(ft, "測定_円未満四捨五入", case, ON_2025, values=vt).value == "4472"
    assert str(round(raw)) == "4472"                       # 実行環境の既定は偶数丸め
    assert str(raw.quantize(Decimal("1"))) == "4472"
    assert str(int(raw)) == "4471"


def test_the_environment_default_rounds_the_other_way_next_yen(ft: F.FormulaTable, vt: F.ValueTable) -> None:
    """同じ偶数丸めでも、整数部の偶奇で向きが変わる(だから項目ごとの規定と合わない)。"""
    assert str(round(Decimal("4471.5"))) == "4472"
    assert str(round(Decimal("4472.5"))) == "4472"
    assert str(F.ROUNDINGS["円未満四捨五入"](Decimal("4472.5"))) == "4473"


# ---------------------------------------------------------------- 評価と出典

def test_evaluate_returns_the_sources_it_used(ft: F.FormulaTable, vt: F.ValueTable) -> None:
    r = F.evaluate(ft, "折半額", {"報酬月額": "300000"}, ON_2025, values=vt)
    assert r.ok
    assert r.raw == "15030.00" and r.value == "15030"
    assert r.rounding == "50銭以下切捨て"
    assert [(u.kind, u.name, u.row) for u in r.used] == [("式", "折半額", 1), ("値", "合成料率_甲", 2)]
    assert r.used[0].source == "合成の端数処理メモ 2024(架空)"
    assert r.used[1].valid_from == date(2025, 3, 1)


def test_a_formula_can_depend_on_another_formula(ft: F.FormulaTable, vt: F.ValueTable) -> None:
    r = F.evaluate(ft, "月額", {"被保険者月数": "421"}, date(2025, 6, 1), values=vt)
    assert r.ok
    assert [u.name for u in r.used] == ["月額", "年額", "合成単価", "合成乗率"]
    assert r.raw == "60224.892" and r.value == "60225"   # 年額を丸めずに渡し、月額の側で円未満四捨五入


def test_the_formula_version_changes_with_the_date(ft: F.FormulaTable, vt: F.ValueTable) -> None:
    """同じ id・同じ入力でも、有効時間で当たる式の行が変わる(値の履歴では表せない改正)。"""
    case = {"報酬月額": "300000"}
    before = F.evaluate(ft, "折半額", case, date(2026, 3, 1), values=vt)
    after = F.evaluate(ft, "折半額", case, ON_2026, values=vt)
    assert before.used[0].row == 1 and after.used[0].row == 2
    assert before.value == "15525" and after.value == "15975"
    assert [u.name for u in after.used] == ["折半額", "合成料率_甲", "合成加算率"]


def test_the_input_set_can_differ_between_versions(ft: F.FormulaTable) -> None:
    """v1 は月末在籍だけ、v2 は日数の条件が足される(= 入力の数も版ごとに違う)。"""
    v1 = F.evaluate(ft, "免除判定", {"月末在籍": "0"}, date(2022, 6, 1))
    assert v1.ok and v1.value == "0"
    v2 = F.evaluate(ft, "免除判定", {"月末在籍": "0", "休業日数": "14"}, date(2023, 1, 1))
    assert v2.ok and v2.value == "1"
    missing = F.evaluate(ft, "免除判定", {"月末在籍": "0"}, date(2023, 1, 1))
    assert not missing.ok and missing.reason == "入力が足りない"


def test_a_row_without_a_start_date_never_applies(ft: F.FormulaTable) -> None:
    """施行日が政令待ちの行は、どの日付で引いても当たらない。"""
    assert any(r.valid_from is None for r in ft.rows if r.id == "免除判定")
    for on in (date(2026, 6, 30), date(2030, 1, 1)):
        r = F.evaluate(ft, "免除判定", {"月末在籍": "0", "休業日数": "9"}, on)
        assert r.ok and r.used[0].row == 7          # 政令待ちの行(8 行目)ではなく v2


# ---------------------------------------------------------------- 理由コード 8 つ

def test_there_are_exactly_eight_reason_codes() -> None:
    assert len(F.REASONS) == 8


def test_stop_when_rounding_is_empty() -> None:
    bad = F.FormulaTable.load(BROKEN)
    r = F.evaluate(bad, "丸めが無い式", {"報酬月額": "100"}, date(2025, 6, 1))
    assert not r.ok and r.reason == "丸めが空欄"
    assert r.value == ""


def test_stop_when_the_rounding_name_is_not_registered() -> None:
    bad = F.FormulaTable.load(BROKEN)
    r = F.evaluate(bad, "知らない丸めの式", {"報酬月額": "100"}, date(2025, 6, 1))
    assert not r.ok and r.reason == "未登録の丸めの名前"


def test_stop_when_the_function_is_not_registered() -> None:
    bad = F.FormulaTable.load(BROKEN)
    r = F.evaluate(bad, "知らない関数の式", {"報酬月額": "100"}, date(2025, 6, 1))
    assert not r.ok and r.reason == "未登録の関数"


def test_stop_when_a_float_gets_in(ft: F.FormulaTable, vt: F.ValueTable) -> None:
    r = F.evaluate(ft, "測定_50銭以下切捨て", {"報酬月額": 110000.0, "料率": "8.13"}, ON_2025, values=vt)
    assert not r.ok and r.reason == "float 混入"
    ok = F.evaluate(ft, "測定_50銭以下切捨て", {"報酬月額": "110000", "料率": "8.13"}, ON_2025, values=vt)
    assert ok.ok and ok.value == "4471"


def test_stop_when_the_version_is_not_published_yet(ft: F.FormulaTable, vt: F.ValueTable) -> None:
    case = {"報酬月額": "300000"}
    before = F.evaluate(ft, "折半額", case, ON_2026, PUBLISHED - __import__("datetime").timedelta(days=5), vt)
    assert not before.ok and before.reason == "式の版が as_of 時点で未公表"
    after = F.evaluate(ft, "折半額", case, ON_2026, PUBLISHED + __import__("datetime").timedelta(days=10), vt)
    assert after.ok and after.value == "15975"


def test_stop_on_a_dependency_cycle() -> None:
    bad = F.FormulaTable.load(BROKEN)
    r = F.evaluate(bad, "循環A", {}, date(2025, 6, 1))
    assert not r.ok and r.reason == "依存が循環している"
    assert r.detail == "循環A → 循環B → 循環A"


def test_stop_when_an_input_is_missing(ft: F.FormulaTable, vt: F.ValueTable) -> None:
    r = F.evaluate(ft, "折半額", {}, ON_2025, values=vt)
    assert not r.ok and r.reason == "入力が足りない"


def test_stop_when_a_dependency_is_undetermined(ft: F.FormulaTable, vt: F.ValueTable) -> None:
    out_of_range = F.evaluate(ft, "折半額", {"報酬月額": "300000"}, date(2020, 1, 1), values=vt)
    assert not out_of_range.ok and out_of_range.reason == "依存先が決まらない"
    no_values = F.evaluate(ft, "折半額", {"報酬月額": "300000"}, ON_2025)
    assert not no_values.ok and no_values.reason == "依存先が決まらない"
    unknown = F.evaluate(ft, "無い式", {}, ON_2025, values=vt)
    assert not unknown.ok and unknown.reason == "依存先が決まらない"


def test_every_reason_code_has_a_path(ft: F.FormulaTable, vt: F.ValueTable) -> None:
    """8 つの理由コードが全て実際に返る道を持つ(名前だけの理由コードを残さない)。"""
    bad = F.FormulaTable.load(BROKEN)
    dt = __import__("datetime")
    got = {
        F.evaluate(bad, "丸めが無い式", {"報酬月額": "1"}, date(2025, 6, 1)).reason,
        F.evaluate(bad, "知らない丸めの式", {"報酬月額": "1"}, date(2025, 6, 1)).reason,
        F.evaluate(bad, "知らない関数の式", {"報酬月額": "1"}, date(2025, 6, 1)).reason,
        F.evaluate(bad, "循環A", {}, date(2025, 6, 1)).reason,
        F.evaluate(ft, "測定_丸めない", {"報酬月額": 1.0, "料率": "8.13"}, ON_2025, values=vt).reason,
        F.evaluate(ft, "折半額", {"報酬月額": "1"}, ON_2026, ON_2026 - dt.timedelta(days=60), vt).reason,
        F.evaluate(ft, "折半額", {}, ON_2025, values=vt).reason,
        F.evaluate(ft, "折半額", {"報酬月額": "1"}, date(2020, 1, 1), values=vt).reason,
    }
    assert got == set(F.REASONS)


# ---------------------------------------------------------------- 構文の allowlist

@pytest.mark.parametrize("expr,label", [
    ("報酬.real", "属性アクセス"),
    ("報酬[0]", "添字"),
    ("min(x for x in 報酬)", "内包表記"),
    ("(lambda x: x)(報酬)", "lambda"),
    ("報酬 if 報酬 else 報酬 and 1", "and / or"),
    ("報酬 ** 2", "べき乗"),
    ("報酬 % 2", "剰余"),
    ("報酬 // 2", "切り捨て除算"),
    ("[報酬]", "リスト"),
    ("'abc'", "数でない定数(str)"),
])
def test_disallowed_syntax_is_refused_at_the_syntax_stage(expr: str, label: str) -> None:
    assert label in F.check_syntax(expr)


@pytest.mark.parametrize("expr", [
    "報酬 * 料率 / 200",
    "-報酬 + 1",
    "1 if 報酬 > 100 else 0",
    "min(報酬, 200) - max(報酬, 1)",
    "報酬 * 1.5",
])
def test_allowed_syntax_passes(expr: str) -> None:
    assert F.check_syntax(expr) == []


def test_a_decimal_literal_does_not_go_through_float() -> None:
    """式の中の 0.1 + 0.2 が 0.30000000000000004 にならない。"""
    t = F.FormulaTable.from_records([{
        "id": "小数", "expr": "0.1 + 0.2", "inputs": "", "rounding": "丸めない",
        "valid_from": "2025-04-01", "valid_to": "", "known_from": "2025-01-01",
        "known_to": "", "known_quality": "実値", "priority": "0", "source": "合成(架空)"}])
    assert F.evaluate(t, "小数", {}, date(2025, 6, 1)).value == "0.3"
    assert 0.1 + 0.2 != 0.3          # 実行環境の float ではこうなる


def test_a_disallowed_expression_is_a_table_error_not_a_reason_code() -> None:
    bad = F.FormulaTable.load(BROKEN)
    with pytest.raises(F.TableError, match="許可外の構文"):
        F.evaluate(bad, "属性を触る式", {"報酬月額": "1"}, date(2025, 6, 1))


# ---------------------------------------------------------------- validate

def test_validate_is_clean_on_the_clean_table(ft: F.FormulaTable) -> None:
    assert F.validate(ft) == []


def test_validate_lists_every_kind_without_fixing() -> None:
    bad = F.FormulaTable.load(BROKEN)
    found = F.validate(bad)
    kinds = {f.kind for f in found}
    assert kinds == set(F.FINDINGS)
    assert len(found) == 8
    assert {f.kind: f.rows for f in found}["有効期間の重なり"] == (8, 9)
    assert len(F.FormulaTable.load(BROKEN)) == len(bad)      # 直さない


# ---------------------------------------------------------------- CLI

def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "formula_table.py"), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def test_cli_eval_prints_one_json_line_and_exits_zero() -> None:
    p = run("eval", str(TABLE), "--values", str(VALUES), "--id", "折半額",
            "--input", "報酬月額=300000", "--on", "2025-06-01")
    assert p.returncode == 0
    out = json.loads(p.stdout)
    assert out["ok"] and out["value"] == "15030" and out["rounding"] == "50銭以下切捨て"
    assert out["used"][0]["source"] == "合成の端数処理メモ 2024(架空)"


def test_cli_eval_exits_three_when_it_stops() -> None:
    p = run("eval", str(TABLE), "--values", str(VALUES), "--id", "折半額",
            "--input", "報酬月額=300000", "--on", "2026-04-01", "--as-of", "2026-02-05")
    assert p.returncode == 3
    assert json.loads(p.stdout)["reason"] == "式の版が as_of 時点で未公表"


def test_cli_validate_exits_three_on_a_broken_table() -> None:
    ok = run("validate", str(TABLE))
    assert ok.returncode == 0 and json.loads(ok.stdout)["findings"] == []
    ng = run("validate", str(BROKEN))
    assert ng.returncode == 3 and len(json.loads(ng.stdout)["findings"]) == 8


def test_cli_rejects_a_bad_argument() -> None:
    assert run("eval", str(TABLE), "--id", "折半額", "--input", "報酬月額", "--on", "2025-06-01").returncode == 2
    assert run("validate", str(FX / "無い表.csv")).returncode == 2


# ---------------------------------------------------------------- 測定(記事の数値)

SPECIFIED = ["50銭以下切捨て", "1円未満切捨て", "円未満四捨五入"]


def measure_rounding(ft: F.FormulaTable, vt: F.ValueTable) -> dict:
    """合成の金額ごとに、表で明示指定した丸めと、実行環境の既定 3 通りを突き合わせる。"""
    out = {"total": 0, "fractional": 0, "exact_half": 0,
           "by_spec": {n: {"round": 0, "quantize": 0, "int": 0} for n in SPECIFIED}}
    for houshuu in MF.HOUSHUU:
        for ritsu in MF.RITSU:
            case = {"報酬月額": str(houshuu), "料率": ritsu}
            raw = Decimal(F.evaluate(ft, "測定_丸めない", case, ON_2025, values=vt).value)
            floor = raw.to_integral_value(rounding="ROUND_FLOOR")
            out["total"] += 1
            out["fractional"] += int(raw != floor)
            out["exact_half"] += int(raw - floor == Decimal("0.5"))
            env = {"round": Decimal(round(raw)),                 # Python の組み込み round
                   "quantize": raw.quantize(Decimal("1")),       # Decimal の既定 context
                   "int": Decimal(int(raw))}                     # int による切り捨て
            for name in SPECIFIED:
                spec = Decimal(F.evaluate(ft, f"測定_{name}", case, ON_2025, values=vt).value)
                for k, got in env.items():
                    out["by_spec"][name][k] += int(got != spec)
    return out


def measure_formula_version(ft: F.FormulaTable, vt: F.ValueTable) -> dict:
    """式をコードに 1 本固定し値だけ表から引く側と、式も表から引く側を比べる。"""
    fixed = F.FormulaTable([r for r in ft.rows if r.id == "折半額"][:1])   # v1 をコードに焼いた側
    out = {"total": 0, "mismatch": 0, "stopped_before_publication": 0, "value_after_publication": 0}
    for houshuu in MF.HOUSHUU:
        case = {"報酬月額": str(houshuu)}
        for on in (date(2026, 3, 1), ON_2026):
            out["total"] += 1
            a = F.evaluate(fixed, "折半額", case, on, values=vt)
            b = F.evaluate(ft, "折半額", case, on, values=vt)
            out["mismatch"] += int((a.value if a.ok else None) != (b.value if b.ok else None))
        for as_of in (date(2026, 2, 5), date(2026, 2, 20)):
            r = F.evaluate(ft, "折半額", case, ON_2026, as_of, vt)
            if r.ok:
                out["value_after_publication"] += 1
            else:
                out["stopped_before_publication"] += 1
    return out


def test_measure_rounding(ft: F.FormulaTable, vt: F.ValueTable, capsys: pytest.CaptureFixture) -> None:
    m = measure_rounding(ft, vt)
    assert m["total"] == 120
    assert m["fractional"] == 107
    assert m["exact_half"] == 18
    assert m["by_spec"]["50銭以下切捨て"] == {"round": 8, "quantize": 8, "int": 46}
    assert m["by_spec"]["1円未満切捨て"] == {"round": 54, "quantize": 54, "int": 0}
    assert m["by_spec"]["円未満四捨五入"] == {"round": 10, "quantize": 10, "int": 64}
    with capsys.disabled():
        print(f"\n[measure] 合成の金額 {m['total']} 件 / 端数が出た {m['fractional']} 件 "
              f"(うち端数ちょうど 0.5 が {m['exact_half']} 件)")
        for name in SPECIFIED:
            d = m["by_spec"][name]
            print(f"[measure] 表で『{name}』を指定 vs 実行環境の既定: "
                  f"round {d['round']} 件 / Decimal の既定 {d['quantize']} 件 / int {d['int']} 件 が食い違う")


def test_measure_formula_version(ft: F.FormulaTable, vt: F.ValueTable, capsys: pytest.CaptureFixture) -> None:
    m = measure_formula_version(ft, vt)
    assert m["total"] == 40
    assert m["mismatch"] == 20
    assert m["stopped_before_publication"] == 20
    assert m["value_after_publication"] == 20
    with capsys.disabled():
        print(f"[measure] 式の版 {m['total']} 件: 式をコードに固定して値だけ表から引く側と "
              f"{m['mismatch']} 件で答えが違った(改正後の 20 件が全部)")
        print(f"[measure] 同じ引き当てで as_of だけ動かすと、公表前の {m['stopped_before_publication']} 件は "
              f"『式の版が as_of 時点で未公表』で止まり、公表後の {m['value_after_publication']} 件だけ値を返した")


def test_the_measurement_is_deterministic(ft: F.FormulaTable, vt: F.ValueTable) -> None:
    assert measure_rounding(ft, vt) == measure_rounding(F.FormulaTable.load(TABLE), F.ValueTable.load(VALUES))
    assert measure_formula_version(ft, vt) == measure_formula_version(ft, F.ValueTable.load(VALUES))
