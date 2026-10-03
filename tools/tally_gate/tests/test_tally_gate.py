"""tally_gate のテスト。合成 fixture(架空)だけを使う。

後半の test_measure_* が記事の数値の出どころ。
  measure_clean       きれいな状態の表で 3 つの検査が全部一致することと、人・項目・総計の数
  measure_visibility  壊れ方を 1 つずつ仕込み、どの軸で見えたかを数える(記事の図 2 がこの出力)
  measure_tolerance   1 円の差を吸収する引数が無いことと、丸めの名前を変えた時の差
決定論なので、値が変われば記事の数字も変える。
"""
from __future__ import annotations

import ast
import copy
import inspect
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FX))
import make_fixtures as MF  # noqa: E402
import tally_gate as TG  # noqa: E402

MEISAI, SPEC = FX / "meisai.csv", FX / "koumoku.csv"
DECL = TG.Declaration.of(MF.IDENTITY, MF.ID_COLUMN, MF.TOTAL_ROW)


# ---------------------------------------------------------------- 土台

def spec_of(rows: "list | None" = None) -> TG.Spec:
    return TG.Spec.of(copy.deepcopy(rows if rows is not None else MF.SPEC_ROWS))


def table_of(rows: "list | None" = None) -> TG.Table:
    return TG.Table.of(MF.ID_COLUMN, MF.ITEMS,
                       copy.deepcopy(rows if rows is not None else MF.meisai_rows()))


def gate(rows: "list | None" = None, spec_rows: "list | None" = None,
         decl: "TG.Declaration | None" = None) -> TG.Gate:
    return TG.check(table_of(rows), spec_of(spec_rows), decl or DECL)


def reasons_of(report: TG.Report) -> list:
    return sorted({p.reason for p in report.pending})


def test_fixture_files_match_the_generator() -> None:
    """ディスク上の fixture が生成器から決定論的に出ること。"""
    disk_t = TG.Table.load(MEISAI, MF.ID_COLUMN)
    assert disk_t.to_dicts() == MF.meisai_rows()
    assert TG.Spec.load(SPEC) == spec_of()


def test_clean_table_passes_all_three() -> None:
    r = gate().check()
    assert r.ok and r.visibility == "all_agree" and r.axes == ()
    assert r.diffs == () and r.pending == ()
    assert r.people == 8 and r.items == 8
    assert r.row_total == r.column_total == "1623308"


def test_handoff_returns_people_rows_only_when_all_agree() -> None:
    g = gate()
    rows = g.handoff()
    assert len(rows) == 8
    assert all(row[MF.ID_COLUMN] != MF.TOTAL_ROW for row in rows)
    assert list(rows[0]) == [MF.ID_COLUMN, *MF.ITEMS]


def test_handoff_before_check_stops() -> None:
    g = TG.Gate(table_of(), spec_of(), DECL)
    with pytest.raises(TG.GateError) as e:
        g.handoff()
    assert e.value.reason == "検査前に出力を要求した"


def test_handoff_after_failed_check_stops() -> None:
    rows = MF.meisai_rows()
    rows[2]["基本給"] = "201000"
    g = gate(rows)
    assert not g.report.ok
    with pytest.raises(TG.GateError) as e:
        g.handoff()
    assert e.value.reason == g.report.visibility


def test_the_component_has_no_write_path() -> None:
    """関所そのものが書き出しを持たない(open / write がソースに無い)。"""
    body = inspect.getsource(TG.Gate) + inspect.getsource(TG.check)
    for token in ("open(", "write", "replace("):
        assert token not in body, token


def test_check_and_report_create_no_file(tmp_path: Path) -> None:
    """CLI の check / report を通しても、ファイルは 1 つも増えない(行を返すだけ)。"""
    MF.write(tmp_path)
    before = sorted(p.name for p in tmp_path.iterdir())
    for cmd in ("check", "report"):
        run(cmd, str(tmp_path / "meisai.csv"), "--spec", str(tmp_path / "koumoku.csv"),
            "--identity", MF.IDENTITY, "--id-column", MF.ID_COLUMN, "--total-row", MF.TOTAL_ROW)
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_no_tolerance_argument_anywhere() -> None:
    """許容誤差の引数を持たない(関数の引数名と CLI の option 名を全部見る)。"""
    tree = ast.parse((ROOT / "tally_gate.py").read_text(encoding="utf-8"))
    names: set = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            a = n.args
            names |= {x.arg for x in [*a.posonlyargs, *a.args, *a.kwonlyargs]}
        elif isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith("--"):
            names.add(n.value)
    for token in ("tolerance", "atol", "rtol", "epsilon", "margin", "fuzzy"):
        assert not [x for x in names if token in x], token
    for fn in (TG.Gate.check, TG.Gate.handoff, TG.check):
        assert list(inspect.signature(fn).parameters) in (["self"], ["table", "spec", "decl"])


def test_one_yen_is_a_difference() -> None:
    rows = MF.meisai_rows()
    rows[0]["差引支給額"] = str(int(rows[0]["差引支給額"]) + 1)
    r = gate(rows).check()
    assert not r.ok and r.by_axis(TG.ROW)[0].delta == "-1"


# ---------------------------------------------------------------- 理由コード(7 つ)

def test_reason_rounding_empty() -> None:
    sp = copy.deepcopy(MF.SPEC_ROWS)
    sp[3]["rounding"] = ""
    r = gate(spec_rows=sp).check()
    assert reasons_of(r) == ["rounding 空欄"] and r.visibility == TG.NOT_CHECKED
    assert r.diffs == ()          # 3 つの検査に進んでいない


def test_reason_group_missing() -> None:
    sp = copy.deepcopy(MF.SPEC_ROWS)
    sp[1]["group"] = ""
    r = gate(spec_rows=sp).check()
    assert reasons_of(r) == ["group 未宣言"] and r.diffs == ()


def test_reason_group_missing_for_an_extra_column() -> None:
    """宣言表に足した項目の group が空欄でも、理由コードで止まる。"""
    sp = copy.deepcopy(MF.SPEC_ROWS)
    sp.append({"item": "予備", "group": "", "sign": "+", "rounding": "丸めない", "source": ""})
    rows = [{**r, "予備": ""} for r in MF.meisai_rows()]
    t = TG.Table.of(MF.ID_COLUMN, [*MF.ITEMS, "予備"], rows)
    r = TG.check(t, spec_of(sp), DECL).report
    assert reasons_of(r) == ["group 未宣言"]


def test_reason_item_not_declared() -> None:
    sp = [r for r in copy.deepcopy(MF.SPEC_ROWS) if r["item"] != "役職手当"]
    rows = MF.meisai_rows()
    t = TG.Table.of(MF.ID_COLUMN, MF.ITEMS, rows)
    r = TG.check(t, TG.Spec.of(sp), DECL).report
    assert reasons_of(r) == ["項目が宣言表に無い"]


def test_reason_same_person_twice() -> None:
    rows = MF.meisai_rows()
    rows.insert(1, copy.deepcopy(rows[0]))
    r = gate(rows).check()
    assert reasons_of(r) == ["同じ人が 2 行"]


def test_reason_total_row_missing() -> None:
    rows = [r for r in MF.meisai_rows() if r[MF.ID_COLUMN] != MF.TOTAL_ROW]
    r = gate(rows).check()
    assert reasons_of(r) == ["集計行が無い"]


@pytest.mark.parametrize("value", ["８２９８", "8298円", "8,29８", "-", "8 298"])
def test_reason_not_a_number(value: str) -> None:
    rows = MF.meisai_rows()
    rows[0]["源泉税"] = value
    r = gate(rows).check()
    assert reasons_of(r) == ["数字として読めない値"]


def test_full_width_digits_would_pass_a_bare_decimal() -> None:
    """全角数字は Decimal がそのまま受けてしまうので、形の検査を先に置いてある。"""
    assert Decimal("８２９８") == Decimal(8298)
    with pytest.raises(ValueError):
        TG.read_amount("８２９８")


def test_all_seven_reason_codes_are_reachable() -> None:
    assert len(TG.REASONS) == 7
    got = {"検査前に出力を要求した"}
    for fn in (test_reason_rounding_empty, test_reason_group_missing,
               test_reason_item_not_declared, test_reason_same_person_twice,
               test_reason_total_row_missing):
        fn()
    test_reason_not_a_number("8298円")
    got |= {"rounding 空欄", "group 未宣言", "項目が宣言表に無い", "同じ人が 2 行",
            "集計行が無い", "数字として読めない値"}
    assert got == set(TG.REASONS)


def test_blank_cell_counts_as_zero() -> None:
    assert TG.read_amount("") == Decimal(0)
    assert TG.read_amount(" 1,234 ") == Decimal(1234)
    assert TG.read_amount("-1,234.50") == Decimal("-1234.50")


# ---------------------------------------------------------------- 表の不備(理由コードではなく exit 2)

@pytest.mark.parametrize("text", ["支給 - 控除", "支給 = 控除 = 差引", "支給 - 控除 = 差引 + 予備",
                                  "= 差引", "支給 - 支給 = 差引", "支給 - 控除 = 支給"])
def test_broken_identity_is_a_table_error(text: str) -> None:
    with pytest.raises(TG.TableError):
        TG.Identity.parse(text)


def test_identity_parses_signs() -> None:
    i = TG.Identity.parse("支給 - 控除 = 差引")
    assert i.terms == ((1, "支給"), (-1, "控除")) and i.rhs == "差引"


@pytest.mark.parametrize("field,value", [("sign", ""), ("sign", "1"), ("rounding", "四捨五入"),
                                         ("item", "")])
def test_broken_spec_is_a_table_error(field: str, value: str) -> None:
    sp = copy.deepcopy(MF.SPEC_ROWS)
    sp[0][field] = value
    with pytest.raises(TG.TableError):
        TG.Spec.of(sp)


def test_duplicate_item_in_spec_is_a_table_error() -> None:
    sp = copy.deepcopy(MF.SPEC_ROWS)
    sp.append(copy.deepcopy(sp[0]))
    with pytest.raises(TG.TableError):
        TG.Spec.of(sp)


def test_group_outside_the_identity_is_a_table_error() -> None:
    sp = copy.deepcopy(MF.SPEC_ROWS)
    sp[1]["group"] = "別の何か"
    with pytest.raises(TG.TableError):
        gate(spec_rows=sp)


def test_declaration_requires_every_name() -> None:
    for args in ((MF.IDENTITY, "", MF.TOTAL_ROW), (MF.IDENTITY, MF.ID_COLUMN, "")):
        with pytest.raises(TG.TableError):
            TG.Declaration.of(*args)


def test_missing_id_column_is_a_table_error() -> None:
    with pytest.raises(TG.TableError):
        TG.Table.load(MEISAI, "社員番号")


def test_unregistered_rounding_name_is_a_table_error() -> None:
    with pytest.raises(TG.TableError):
        TG.round_by(Decimal(1), "いいかんじに")


# ---------------------------------------------------------------- 丸め

@pytest.mark.parametrize("name,value,want", [
    ("50銭以下切捨て", "8844.50", "8844"), ("50銭以下切捨て", "8844.51", "8845"),
    ("50銭以下切捨て", "8844.49", "8844"), ("1円未満切捨て", "8844.99", "8844"),
    ("円未満四捨五入", "8844.50", "8845"), ("円未満四捨五入", "8845.50", "8846"),
    ("丸めない", "8844.50", "8844.50"),
])
def test_rounding_boundaries(name: str, value: str, want: str) -> None:
    assert format(TG.round_by(Decimal(value), name), "f") == want


def test_half_up_differs_from_the_runtime_default() -> None:
    """円未満四捨五入は実行環境の既定(偶数丸め)とは違う。"""
    assert format(TG.round_by(Decimal("8844.50"), "円未満四捨五入"), "f") == "8845"
    assert round(Decimal("8844.50")) == 8844


# ---------------------------------------------------------------- 軸ごとの見え方

def visibility_of(rows: "list | None" = None, spec_rows: "list | None" = None) -> TG.Report:
    return gate(rows, spec_rows).report


def break_one_cell() -> TG.Report:
    rows = MF.meisai_rows()
    rows[2]["基本給"] = str(int(rows[2]["基本給"]) + 1000)
    return visibility_of(rows)


def break_sign() -> TG.Report:
    sp = copy.deepcopy(MF.SPEC_ROWS)
    sp[6]["sign"] = "+"                     # 控除の中で引く側の項目を足す側にする
    return visibility_of(spec_rows=sp)


def break_group() -> TG.Report:
    sp = copy.deepcopy(MF.SPEC_ROWS)
    sp[2]["group"] = "控除"                  # 通勤手当を控除に入れる
    return visibility_of(spec_rows=sp)


def break_offsetting() -> TG.Report:
    rows = MF.meisai_rows()
    rows[0]["役職手当"] = str(int(rows[0]["役職手当"]) + 1000)
    rows[3]["通勤手当"] = str(int(rows[3]["通勤手当"]) - 1000)
    return visibility_of(rows)


def break_missing_person() -> TG.Report:
    rows = [r for r in MF.meisai_rows() if r[MF.ID_COLUMN] != "10005"]
    return visibility_of(rows)


def break_stale_total() -> TG.Report:
    rows = MF.meisai_rows()
    rows[-1]["基本給"] = str(int(rows[-1]["基本給"]) - 1000)
    return visibility_of(rows)


BREAKAGES = {
    "1 か所の値のずれ": break_one_cell,
    "符号の所属の取り違え": break_sign,
    "項目を別の group に入れた": break_group,
    "別の人の別の項目で差が打ち消し合う": break_offsetting,
    "人が 1 行抜けた": break_missing_person,
    "集計行だけ古い": break_stale_total,
}


def measure_visibility() -> dict:
    out = {}
    for name, fn in BREAKAGES.items():
        r = fn()
        out[name] = {"visibility": r.visibility, "axes": list(r.axes),
                     "row": len(r.by_axis(TG.ROW)), "column": len(r.by_axis(TG.COLUMN)),
                     "total": len(r.by_axis(TG.TOTAL)), "crossing": len(r.crossing())}
    return out


def test_measure_visibility(capsys: pytest.CaptureFixture) -> None:
    m = measure_visibility()
    assert m["1 か所の値のずれ"] == {"visibility": "row_and_column",
                                     "axes": ["row", "column", "total"],
                                     "row": 1, "column": 1, "total": 1, "crossing": 1}
    assert m["符号の所属の取り違え"] == {"visibility": "row_only", "axes": ["row"],
                                        "row": 2, "column": 0, "total": 0, "crossing": 0}
    assert m["項目を別の group に入れた"] == {"visibility": "row_only", "axes": ["row"],
                                             "row": 7, "column": 0, "total": 0, "crossing": 0}
    assert m["別の人の別の項目で差が打ち消し合う"] == {"visibility": "invisible_in_total",
                                                     "axes": ["row", "column"],
                                                     "row": 2, "column": 2, "total": 0,
                                                     "crossing": 4}
    assert m["人が 1 行抜けた"] == {"visibility": "column_and_total", "axes": ["column", "total"],
                                   "row": 0, "column": 6, "total": 1, "crossing": 0}
    assert m["集計行だけ古い"] == {"visibility": "column_and_total", "axes": ["column", "total"],
                                  "row": 0, "column": 1, "total": 1, "crossing": 0}
    with capsys.disabled():
        print("")
        for name, v in m.items():
            print(f"[measure] {name}: {v['visibility']}"
                  f"(人ごと {v['row']} 件 / 項目ごと {v['column']} 件 / 総計 {v['total']} 件)")


def test_only_the_row_axis_sees_a_sign_mistake() -> None:
    """符号の所属の取り違えは、項目ごとの合計では出ない(印字されたままの値を足すから)。

    出るのは、その項目に値が入っている人の行だけ(合成の表では 2 人)。
    """
    r = break_sign()
    assert r.by_axis(TG.COLUMN) == () and len(r.by_axis(TG.ROW)) == 2
    assert [(d.who, d.delta) for d in r.by_axis(TG.ROW)] == [("10002", "-2400"),
                                                             ("10006", "-6800")]


def test_only_the_row_axis_sees_a_group_mistake() -> None:
    """項目を別の group に入れた形も人ごとの合計だけに出る(値が空欄の 1 人は出ない)。"""
    r = break_group()
    assert r.by_axis(TG.COLUMN) == () and len(r.by_axis(TG.ROW)) == 7
    assert "10003" not in {d.who for d in r.by_axis(TG.ROW)}      # 通勤手当が空欄の人
    assert r.row_total == r.column_total                           # 総計でも消える


def test_only_the_column_axis_sees_a_missing_person() -> None:
    """人が 1 行抜けた形は、人ごとの検査では 1 件も出ない。"""
    r = break_missing_person()
    assert r.by_axis(TG.ROW) == () and len(r.by_axis(TG.COLUMN)) == 6
    assert r.by_axis(TG.TOTAL)[0].delta == "-197833"               # 抜けた人の差引支給額


def test_crossing_is_identified_when_both_axes_see_it() -> None:
    r = break_one_cell()
    assert ("10003", "基本給") in r.crossing()


def test_offsetting_pair_passes_the_total() -> None:
    """打ち消し合う 2 か所は総計では消え、交点も 1 つに決まらない(2 × 2 = 4 通り)。"""
    r = break_offsetting()
    assert r.row_total == r.column_total and r.by_axis(TG.TOTAL) == ()
    assert not r.ok and len(r.crossing()) == 4
    assert [(d.who, d.delta) for d in r.by_axis(TG.ROW)] == [("10001", "1000"),
                                                             ("10004", "-1000")]


def test_total_is_implied_by_column() -> None:
    """列方向が全部一致すれば総計も必ず一致する(= total_only と row_and_total は作れない)。"""
    for fn in BREAKAGES.values():
        r = fn()
        if not r.by_axis(TG.COLUMN):
            assert r.by_axis(TG.TOTAL) == ()
        assert r.visibility not in ("total_only", "row_and_total")


def test_visibility_names_cover_every_combination() -> None:
    assert len(TG.VISIBILITY) == 8
    assert TG.VISIBILITY[()] == "all_agree"


# ---------------------------------------------------------------- 丸めの効き

def measure_rounding() -> dict:
    """保険料の丸めの名前を 50 銭以下切捨てから四捨五入に変えると、何人ぶん答えが変わるか。"""
    sp = copy.deepcopy(MF.SPEC_ROWS)
    for row in sp:
        if row["item"] in ("保険料甲", "保険料乙"):
            row["rounding"] = "円未満四捨五入"
    r = visibility_of(spec_rows=sp)
    return {"visibility": r.visibility, "row": len(r.by_axis(TG.ROW)),
            "column": len(r.by_axis(TG.COLUMN)), "total": len(r.by_axis(TG.TOTAL)),
            "deltas": sorted({d.delta for d in r.by_axis(TG.ROW)}),
            "boundary": sum(1 for row in MF.person_rows()
                            for name in ("保険料甲", "保険料乙")
                            if Decimal(row[name]) % 1 == Decimal("0.5"))}


def test_measure_rounding(capsys: pytest.CaptureFixture) -> None:
    m = measure_rounding()
    assert m["boundary"] == 4
    assert m["row"] == 2 and m["column"] == 2 and m["total"] == 1
    assert m["deltas"] == ["-2"] and m["visibility"] == "row_and_column"
    with capsys.disabled():
        print(f"\n[measure] 端数ちょうど 50 銭の欄 {m['boundary']} 件: 丸めの名前を"
              f"『50銭以下切捨て』から『円未満四捨五入』に変えると、人ごとの検査が {m['row']} 件 / "
              f"項目ごとの検査が {m['column']} 件 / 総計が {m['total']} 件 落ちる"
              f"(人ごとの差は {' / '.join(m['deltas'])} 円)")


def test_rounding_is_taken_from_the_column_not_a_default() -> None:
    sp = copy.deepcopy(MF.SPEC_ROWS)
    sp[3]["rounding"] = ""
    r = visibility_of(spec_rows=sp)
    assert [p.reason for p in r.pending] == ["rounding 空欄"]
    assert "既定" in TG.REASONS["rounding 空欄"]


# ---------------------------------------------------------------- CLI

def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "tally_gate.py"), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def cli_args(meisai: "Path | None" = None) -> list:
    return [str(meisai or MEISAI), "--spec", str(SPEC), "--identity", MF.IDENTITY,
            "--id-column", MF.ID_COLUMN, "--total-row", MF.TOTAL_ROW]


def test_cli_check_exit_0_when_all_agree() -> None:
    p = run("check", *cli_args())
    assert p.returncode == 0
    assert json.loads(p.stdout)["visibility"] == "all_agree"


def test_cli_check_exit_3_when_a_difference(tmp_path: Path) -> None:
    rows = MF.meisai_rows()
    rows[2]["基本給"] = "201000"
    bad = tmp_path / "meisai.csv"
    MF.write(tmp_path)
    import csv as _csv
    with open(bad, "w", encoding="utf-8", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=[MF.ID_COLUMN, *MF.ITEMS])
        w.writeheader()
        w.writerows(rows)
    p = run("check", str(bad), "--spec", str(SPEC), "--identity", MF.IDENTITY,
            "--id-column", MF.ID_COLUMN, "--total-row", MF.TOTAL_ROW)
    assert p.returncode == 3
    assert json.loads(p.stdout)["visibility"] == "row_and_column"


def test_cli_check_exit_2_when_the_table_is_broken() -> None:
    p = run("check", str(MEISAI), "--spec", str(SPEC), "--identity", "支給 - 控除",
            "--id-column", MF.ID_COLUMN, "--total-row", MF.TOTAL_ROW)
    assert p.returncode == 2 and "恒等式" in p.stderr


def test_cli_report_csv_has_the_axis_column() -> None:
    p = run("report", *cli_args(), "--format", "csv")
    assert p.returncode == 0
    assert p.stdout.splitlines()[0].split(",")[:3] == ["axis", "who", "item"]


def test_cli_init_writes_the_spec_header(tmp_path: Path) -> None:
    out = tmp_path / "koumoku.csv"
    p = run("init", str(out))
    assert p.returncode == 0 and out.exists()
    assert out.read_text(encoding="utf-8").splitlines()[0] == "item,group,sign,rounding,source"
    assert run("init", str(out)).returncode == 2        # 上書きしない


def test_fixtures_are_synthetic() -> None:
    """fixture に実在の氏名・顧客名が入っていないこと(識別子は連番、金額は計算値)。"""
    rows = MF.person_rows()
    assert [r[MF.ID_COLUMN] for r in rows] == [f"1{i:04d}" for i in range(1, 9)]
    assert all(c.isdigit() or c in ".-" for r in rows for v in r.values() for c in str(v))
