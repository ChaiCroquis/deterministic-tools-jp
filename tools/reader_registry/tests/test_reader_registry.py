"""reader_registry のテスト。合成 fixture(架空)だけを使う。

後半の test_measure_* が記事の数値の出どころ。
  measure_shapes   4 つの形を 4 つの係で読み、同じ核の列に何行そろったかを数える(記事の図 2)
  measure_quirks   形の癖ごとに、どの層が吸収したか(= 読めたか / どの理由コードで止まったか)
  measure_stops    止まった表の一覧(選定で止まるものと読み替えで止まるもの)
決定論なので、値が変われば記事の数字も変える。
"""
from __future__ import annotations

import ast
import copy
import hashlib
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
import reader_registry as RR  # noqa: E402

REGISTRY = FX / "registry.json"
OK_SHEETS = {"相手先A_横並び": "a_yokogata.csv", "相手先B_転置": "b_tenchi.csv",
             "相手先C_括弧": "c_kakko.csv", "相手先A_2026改名": "d_kaimei.csv"}


# ---------------------------------------------------------------- 土台

def registry(rows: "list | None" = None) -> RR.Registry:
    return RR.Registry.of(copy.deepcopy(rows if rows is not None else MF.READER_ROWS))


def sheet(name: str) -> RR.Sheet:
    return RR.Sheet.load(FX / name, "カンマ")


def reading(name: str, rows: "list | None" = None) -> RR.Reading:
    return RR.read(sheet(name), registry(rows))


def reasons_of(r: RR.Report) -> list:
    return sorted({p.reason for p in r.pending})


def test_fixture_files_match_the_generator() -> None:
    """ディスク上の fixture が生成器から決定論的に出ること。"""
    assert json.loads(REGISTRY.read_text(encoding="utf-8")) == {"readers": MF.READER_ROWS}
    for name, rows in MF.sheets().items():
        assert [list(r) for r in sheet(name).rows] == rows, name


def test_fixtures_are_synthetic() -> None:
    """fixture が合成であること(識別子は連番、相手先は A / B / C の呼び名)。"""
    ids = [r[0] for r in MF.A_BODY + MF.C_BODY + MF.D_BODY] + MF.B_TABLE[0][1:]
    assert all(i.isdigit() and len(i) == 6 for i in ids)
    assert [r["source"] for r in MF.READER_ROWS][0].startswith("合成の表")
    assert all("合成" in r["source"] for r in MF.READER_ROWS)


# ---------------------------------------------------------------- 4 つの形が同じ核の列に落ちる

def test_every_shape_lands_on_the_same_core_columns() -> None:
    cores = set()
    for reader_id, name in OK_SHEETS.items():
        rd = reading(name)
        assert rd.report.ok and rd.report.reader_id == reader_id, name
        for row in rd.rows():
            cores.add(tuple(row))
    assert cores == {MF.CORE}


def test_rows_fit_the_identity_of_the_next_stage() -> None:
    """読めた行が、次の工程(2 つの軸から足す関所)の恒等式を満たす形になっていること。"""
    for name in OK_SHEETS.values():
        for row in reading(name).rows():
            assert (Decimal(row["支給合計"]) + Decimal(row["控除合計"])
                    == Decimal(row["差引支給額"])), (name, row)


def test_two_printings_of_the_minus_side_land_on_the_same_form() -> None:
    """符号なしの印字と括弧の印字が、同じ『核では負』の形に落ちること。"""
    unsigned = [row["控除合計"] for row in reading("a_yokogata.csv").rows()]
    parens = [row["控除合計"] for row in reading("c_kakko.csv").rows()]
    assert all(v.startswith("-") for v in unsigned + parens)
    assert (unsigned, parens) == (["-48250", "-44120", "-38500"], ["-45300", "-41250", "-52900"])


def test_the_renamed_reader_differs_only_in_two_origin_headers() -> None:
    reg = registry()
    a, d = reg.by_id("相手先A_横並び"), reg.by_id("相手先A_2026改名")
    assert a.core_columns == d.core_columns
    assert [c for c in a.core_columns if a.origin_of(c) != d.origin_of(c)] == ["支給合計", "差引支給額"]


def test_tab_and_comma_give_the_same_rows() -> None:
    """区切りの宣言を変えるだけで、同じ係が同じ行を返すこと。"""
    tab = RR.read(RR.Sheet.load(FX / "a_yokogata.tsv", "タブ"), registry())
    assert tab.rows() == reading("a_yokogata.csv").rows()


def test_delimiter_has_no_default() -> None:
    with pytest.raises(RR.RegistryError):
        RR.Sheet.parse("a,b\n1,2\n", "")
    with pytest.raises(RR.RegistryError):
        RR.Sheet.parse("a,b\n1,2\n", "セミコロン")


def test_header_row_can_sit_below_explanation_rows() -> None:
    rd = reading("e_setsumei.csv")
    assert rd.report.ok and rd.report.records == 3
    assert rd.rows() == reading("a_yokogata.csv").rows()


# ---------------------------------------------------------------- 宣言表に無い見出し(unmapped)

def test_unmapped_headers_are_kept_not_dropped() -> None:
    led = reading("a_yokogata.csv").ledger()
    assert [u["origin"] for u in led["unmapped"]] == ["備考"]
    assert led["unmapped"][0]["values"] == ["新規", "", "再雇用"]
    assert "備考" not in reading("a_yokogata.csv").rows()[0]


def test_ledger_records_the_declaration_and_the_origin_hash() -> None:
    led = reading("b_tenchi.csv").ledger()
    assert led["reader_id"] == "相手先B_転置" and led["orientation"] == "列がレコード"
    assert led["sha256"] == hashlib.sha256((FX / "b_tenchi.csv").read_bytes()).hexdigest()
    assert [c["core"] for c in led["columns"]] == list(MF.CORE)
    assert [c["origin"] for c in led["columns"]][:2] == ["社員コード", "名前"]
    assert [c["core"] for c in led["columns"] if c["required"]] == list(MF.REQUIRED)


# ---------------------------------------------------------------- 選定(推測しない)

def test_no_candidate_stops_instead_of_choosing_the_nearest() -> None:
    r = reading("l_michi.csv").report
    assert not r.ok and r.stage == RR.SELECTION and r.candidates == ()
    assert reasons_of(r) == ["係が 0 件"]


def test_two_candidates_are_not_narrowed_down() -> None:
    r = reading("k_aimai.csv").report
    assert reasons_of(r) == ["係が 2 件以上"]
    assert list(r.candidates) == ["相手先A_横並び", "相手先A_2026改名"]
    assert r.records == 0


def test_added_columns_change_the_declared_width() -> None:
    """列が増えた表は『いちばん近い係』では読まない(宣言した列数と違うので係が 0 件)。"""
    r = reading("j_fueta.csv").report
    assert reasons_of(r) == ["係が 0 件"] and r.candidates == ()


def test_select_function_returns_the_candidates() -> None:
    assert RR.select(sheet("a_yokogata.csv"), registry()) == ("相手先A_横並び",)
    assert len(RR.select(sheet("k_aimai.csv"), registry())) == 2
    assert RR.select(sheet("l_michi.csv"), registry()) == ()


# ---------------------------------------------------------------- 理由コード(10 個)

def test_reason_same_reader_id_twice() -> None:
    rows = [*copy.deepcopy(MF.READER_ROWS), copy.deepcopy(MF.READER_ROWS[0])]
    r = reading("a_yokogata.csv", rows).report
    assert r.stage == RR.DECLARATION and reasons_of(r) == ["同じ reader_id が 2 行"]


def test_reason_column_map_is_not_one_to_one() -> None:
    rows = copy.deepcopy(MF.READER_ROWS)
    rows[0]["column_map"]["部署"] = "氏名"          # 1 つの見出しを 2 つの核の列へ
    r = reading("a_yokogata.csv", rows).report
    assert reasons_of(r) == ["column_map が 1 対 1 でない"]


def test_reason_value_form_is_empty() -> None:
    rows = copy.deepcopy(MF.READER_ROWS)
    rows[0]["value_form"]["支給合計"] = ""
    r = reading("a_yokogata.csv", rows).report
    assert reasons_of(r) == ["value_form 空欄"]
    assert "既定" in RR.REASONS["value_form 空欄"]


def test_reason_header_row_not_found() -> None:
    r = reading("f_nidan.csv").report
    assert r.stage == RR.CONVERSION and reasons_of(r) == ["見出し行が見つからない"]
    assert "差引支給" in r.pending[0].detail and r.records == 0


def test_reason_width_differs_from_the_declaration() -> None:
    r = reading("g_hasu.csv").report
    assert reasons_of(r) == ["列数が宣言と違う"] and "2 行目" in r.pending[0].detail


def test_reason_width_differs_in_a_transposed_sheet() -> None:
    rows = [list(r) for r in MF.sheets()["b_tenchi.csv"]]
    rows[3] = rows[3][:-1]
    r = RR.read(RR.Sheet.of(rows), registry()).report
    assert reasons_of(r) == ["列数が宣言と違う"]


def test_reason_value_does_not_fit_the_declared_form() -> None:
    r = reading("h_yomenai.csv").report
    assert reasons_of(r) == ["宣言した形で読めない値"]
    assert "60進の時間" in r.pending[0].detail


def test_reason_required_column_stays_empty() -> None:
    r = reading("i_kesson.csv").report
    assert reasons_of(r) == ["required の列が埋まらない"] and "氏名" in r.pending[0].detail


def test_reason_rows_requested_before_the_stages() -> None:
    rd = RR.Reading(sheet("a_yokogata.csv"), registry())
    for call in (lambda: rd.rows(), lambda: rd.ledger(), lambda: rd.report):
        with pytest.raises(RR.ReadError) as e:
            call()
        assert e.value.reason == "選定前に読み取りを要求した"


def test_all_ten_reason_codes_are_reachable() -> None:
    seen: set = set()
    for name in ("f_nidan.csv", "g_hasu.csv", "h_yomenai.csv", "i_kesson.csv",
                 "j_fueta.csv", "k_aimai.csv", "l_michi.csv"):
        seen |= set(reading(name).report.reasons())
    dup = [*copy.deepcopy(MF.READER_ROWS), copy.deepcopy(MF.READER_ROWS[0])]
    seen |= set(reading("a_yokogata.csv", dup).report.reasons())
    one_to_many = copy.deepcopy(MF.READER_ROWS)
    one_to_many[0]["column_map"]["部署"] = "氏名"
    seen |= set(reading("a_yokogata.csv", one_to_many).report.reasons())
    empty = copy.deepcopy(MF.READER_ROWS)
    empty[0]["value_form"]["支給合計"] = ""
    seen |= set(reading("a_yokogata.csv", empty).report.reasons())
    seen.add("選定前に読み取りを要求した")
    assert seen == set(RR.REASONS)


def test_stops_do_not_hand_over_rows() -> None:
    for name in ("f_nidan.csv", "g_hasu.csv", "h_yomenai.csv", "i_kesson.csv", "k_aimai.csv"):
        rd = reading(name)
        for call in (rd.rows, rd.ledger):
            with pytest.raises(RR.ReadError):
                call()


# ---------------------------------------------------------------- 宣言の不備(理由コードではなく exit 2)

@pytest.mark.parametrize("field,value", [
    ("orientation", "ななめ"),
    ("orientation", ""),
    ("match", {"headers": [], "columns": 8}),
    ("match", {"headers": ["社員番号"], "columns": "8"}),
    ("match", {"headers": ["社員番号"], "columns": 0}),
    ("column_map", {}),
    ("value_form", {"社員番号": "そんな形は無い"}),
    ("required", ["宣言していない核の列"]),
    ("reader_id", ""),
])
def test_broken_declaration_is_a_registry_error(field: str, value) -> None:
    rows = copy.deepcopy(MF.READER_ROWS)
    rows[0][field] = value
    with pytest.raises(RR.RegistryError):
        RR.Registry.of(rows)


def test_broken_json_is_a_registry_error(tmp_path: Path) -> None:
    bad = tmp_path / "registry.json"
    bad.write_text("{readers: }", encoding="utf-8")
    with pytest.raises(RR.RegistryError):
        RR.Registry.load(bad)


def test_empty_registry_is_a_registry_error() -> None:
    with pytest.raises(RR.RegistryError):
        RR.Registry.of([])


# ---------------------------------------------------------------- 値の形(名前で呼ぶ)

@pytest.mark.parametrize("form,value,want", [
    ("文字列", " 000101 ", "000101"),
    ("整数", "1,000", "1000"),
    ("金額そのまま", "1,234.56", "1234.56"),
    ("金額を50銭以下切捨て", "100.50", "100"),
    ("金額を50銭以下切捨て", "100.51", "101"),
    ("金額を1円未満切捨て", "100.99", "100"),
    ("金額を円未満四捨五入", "100.50", "101"),
    ("60進の時間", "7:30", "7.50"),
    ("60進の時間", "0:00", "0.00"),
    ("60進の時間", "0:20", "0.33"),
    ("60進の時間", "8:10", "8.17"),
    ("60進の時間", "10:00", "10.00"),
    ("印字は符号なし", "1,200", "-1200"),
    ("印字は符号なし", "0", "0"),        # 0 には符号を付けない
    ("括弧は負", "(1,200)", "-1200"),
    ("括弧は負", "1200", "1200"),
])
def test_value_form_boundaries(form: str, value: str, want: str) -> None:
    assert RR.convert(value, form) == want


@pytest.mark.parametrize("form,value", [
    ("整数", "1.5"),
    ("整数", "１０００"),            # 全角数字は素通りさせない
    ("整数", "1000円"),
    ("60進の時間", "7時間30分"),
    ("60進の時間", "7:60"),
    ("60進の時間", "7.5"),
    ("印字は符号なし", "-5"),
    ("括弧は負", "(-5)"),
    ("括弧は負", "1,2,3.4.5"),
])
def test_value_form_rejects_what_it_cannot_read(form: str, value: str) -> None:
    with pytest.raises(ValueError):
        RR.convert(value, form)


def test_blank_stays_blank_without_touching_the_form() -> None:
    for form in RR.VALUE_FORMS:
        assert RR.convert("", form) == ""
        assert RR.convert("  ", form) == ""


def test_unregistered_form_name_is_a_registry_error() -> None:
    with pytest.raises(RR.RegistryError):
        RR.convert("1", "そんな形は無い")


def test_full_width_digits_would_pass_a_bare_decimal() -> None:
    """Decimal は全角数字を受けてしまう。形の検査を先に置いている理由。"""
    assert Decimal("１０００") == Decimal(1000)
    with pytest.raises(ValueError):
        RR.convert("１０００", "整数")


# ---------------------------------------------------------------- 持たせていないもの

def test_no_guessing_argument_anywhere() -> None:
    """推測で 1 つに絞る引数を持たない(関数の引数名と CLI の option 名を全部見る)。"""
    tree = ast.parse((ROOT / "reader_registry.py").read_text(encoding="utf-8"))
    names: set = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            a = n.args
            names |= {x.arg for x in [*a.posonlyargs, *a.args, *a.kwonlyargs]}
        elif isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith("--"):
            names.add(n.value)
    for token in ("prefer", "priority", "first_match", "fallback", "best", "similar",
                  "score", "threshold", "fuzzy"):
        assert not [x for x in names if token in x.lower()], token
    assert list(inspect.signature(RR.read).parameters) == ["sheet", "registry"]
    assert list(inspect.signature(RR.Reading.rows).parameters) == ["self"]


def test_the_component_has_no_write_path() -> None:
    """読み取りそのものが書き出しを持たない(open / write がソースに無い)。"""
    body = inspect.getsource(RR.Reading) + inspect.getsource(RR.read) + inspect.getsource(RR.select)
    for token in ("open(", "write", "replace("):
        assert token not in body, token


def test_the_core_has_no_vocabulary_of_the_sheets() -> None:
    """核のソースに、原本の見出し・核の列名・業種の語が 1 つも無いこと。"""
    src = (ROOT / "reader_registry.py").read_text(encoding="utf-8")
    for word in ("社員", "氏名", "部署", "支給", "控除", "差引", "賃金", "給与", "事業所",
                 "従業員", "保険", "所定外", "残業", "手取", "相手先A", "相手先B", "相手先C"):
        assert word not in src, word
    assert all(c not in src for c in ("備考", "メモ", "調整"))


def test_the_quirk_names_live_in_the_core_but_the_assignment_does_not() -> None:
    """癖の名前(値の形)は核に登録してあるが、どの列がその癖かは宣言表の側にしか無い。"""
    src = (ROOT / "reader_registry.py").read_text(encoding="utf-8")
    assert "60進の時間" in src and "括弧は負" in src          # 呼べる名前の一覧
    reg = registry()
    for r in reg.readers:                                      # 割り当ては宣言表の側
        assert set(dict(r.value_form)) == set(r.core_columns)
    assert len(RR.VALUE_FORMS) == 9 and len(RR.REASONS) == 10


# ---------------------------------------------------------------- CLI

def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "reader_registry.py"), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def cli(name: str) -> list:
    return [str(FX / name), "--registry", str(REGISTRY), "--delimiter", "カンマ"]


def test_cli_read_exit_0_and_prints_the_core_columns() -> None:
    p = run("read", *cli("a_yokogata.csv"))
    assert p.returncode == 0
    out = json.loads(p.stdout)
    assert out["columns"] == list(MF.CORE) and len(out["rows"]) == 3


def test_cli_select_exit_3_when_two_candidates() -> None:
    p = run("select", *cli("k_aimai.csv"))
    assert p.returncode == 3
    assert json.loads(p.stdout)["pending"][0]["reason"] == "係が 2 件以上"


def test_cli_read_exit_3_when_it_stops() -> None:
    p = run("read", *cli("i_kesson.csv"))
    assert p.returncode == 3 and json.loads(p.stdout)["stage"] == RR.CONVERSION


def test_cli_exit_2_when_the_declaration_is_broken(tmp_path: Path) -> None:
    bad = tmp_path / "registry.json"
    bad.write_text(json.dumps({"readers": [{"reader_id": "x"}]}, ensure_ascii=False),
                   encoding="utf-8")
    p = run("read", str(FX / "a_yokogata.csv"), "--registry", str(bad), "--delimiter", "カンマ")
    assert p.returncode == 2 and "match" in p.stderr


def test_cli_exit_2_without_a_delimiter() -> None:
    p = run("read", str(FX / "a_yokogata.csv"), "--registry", str(REGISTRY))
    assert p.returncode == 2


def test_cli_ledger_csv_has_the_mapping_columns() -> None:
    p = run("ledger", *cli("a_yokogata.csv"), "--format", "csv")
    assert p.returncode == 0
    assert p.stdout.splitlines()[0].split(",") == ["core", "origin", "value_form", "required"]


def test_cli_creates_no_file(tmp_path: Path) -> None:
    """select / read / ledger を通してもファイルは 1 つも増えない(行と台帳を返すだけ)。"""
    MF.write(tmp_path)
    before = sorted(p.name for p in tmp_path.iterdir())
    for cmd in ("select", "read", "ledger"):
        run(cmd, str(tmp_path / "a_yokogata.csv"), "--registry", str(tmp_path / "registry.json"),
            "--delimiter", "カンマ")
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_cli_init_writes_the_registry_template(tmp_path: Path) -> None:
    out = tmp_path / "registry.json"
    p = run("init", str(out))
    assert p.returncode == 0 and out.exists()
    template = json.loads(out.read_text(encoding="utf-8"))["readers"][0]
    assert list(template) == list(RR.READER_COLUMNS)
    assert run("init", str(out)).returncode == 2        # 上書きしない


# ---------------------------------------------------------------- 測定(記事の数値)

def measure_shapes() -> dict:
    rows, unmapped, times, rounded, printings = 0, 0, [], [], {}
    reg = registry()
    for reader_id, name in OK_SHEETS.items():
        rd = reading(name)
        led = rd.ledger()
        rows += len(rd.rows())
        unmapped += len(led["unmapped"])
        reader = reg.by_id(reader_id)
        printings[reader.form_of("控除合計")] = printings.get(reader.form_of("控除合計"), 0) + 3
        origin = reader.origin_of("所定外時間")
        for _, raw in RR.Reading(sheet(name), reg)._records(reader)[0]:
            times.append(raw[origin])
            if (int(raw[origin].split(":")[1]) * 100) % 60:
                rounded.append(raw[origin])
    return {"行": rows, "核の列": len(MF.CORE), "係": len(OK_SHEETS), "unmapped": unmapped,
            "時間": len(times), "丸めた時間": len(rounded), "印字": printings}


def test_measure_shapes(capsys: pytest.CaptureFixture) -> None:
    m = measure_shapes()
    assert m == {"行": 12, "核の列": 7, "係": 4, "unmapped": 4, "時間": 12, "丸めた時間": 4,
                 "印字": {"印字は符号なし": 9, "括弧は負": 3}}
    with capsys.disabled():
        print(f"\n[measure] 4 つの形を 4 つの係で読む: 核の列 {m['核の列']} に {m['行']} 行"
              f"(宣言表に無い見出し {m['unmapped']} 件は台帳に残す)")
        print(f"[measure] 60 進の時間 {m['時間']} 件を 10 進に、うち {m['丸めた時間']} 件は 2 桁に丸めた"
              f"(落ちた差はどれも 1/300 時間)")
        print(f"[measure] 引く側の印字 2 通りが同じ形に: 符号なし {m['印字']['印字は符号なし']} 件 /"
              f" 括弧 {m['印字']['括弧は負']} 件")


def measure_quirks() -> dict:
    out = {}
    for quirk, name in (("行と列が入れ替わった表", "b_tenchi.csv"),
                        ("見出しの前に説明行がある", "e_setsumei.csv"),
                        ("見出しが 2 段に分かれる", "f_nidan.csv"),
                        ("項目名が年で改名される", "d_kaimei.csv"),
                        ("項目が増減する", "j_fueta.csv")):
        rd = reading(name)
        r = rd.report
        out[quirk] = {"候補": len(r.candidates), "行": len(rd.rows()) if r.ok else 0,
                      "unmapped": len(r.unmapped), "理由": list(r.reasons())}
    return out


def test_measure_quirks(capsys: pytest.CaptureFixture) -> None:
    m = measure_quirks()
    assert m["行と列が入れ替わった表"] == {"候補": 1, "行": 3, "unmapped": 1, "理由": []}
    assert m["見出しの前に説明行がある"] == {"候補": 1, "行": 3, "unmapped": 1, "理由": []}
    assert m["見出しが 2 段に分かれる"] == {"候補": 1, "行": 0, "unmapped": 0,
                                           "理由": ["見出し行が見つからない"]}
    assert m["項目名が年で改名される"] == {"候補": 1, "行": 3, "unmapped": 1, "理由": []}
    assert m["項目が増減する"] == {"候補": 0, "行": 0, "unmapped": 0, "理由": ["係が 0 件"]}
    with capsys.disabled():
        print("")
        for quirk, v in m.items():
            tail = f"読めた({v['行']} 行)" if not v["理由"] else f"止まった({' / '.join(v['理由'])})"
            print(f"[measure] {quirk}: 候補 {v['候補']} 件 → {tail}")


def measure_stops() -> dict:
    out = {}
    for name in ("k_aimai.csv", "l_michi.csv", "j_fueta.csv", "f_nidan.csv",
                 "g_hasu.csv", "h_yomenai.csv", "i_kesson.csv"):
        r = reading(name).report
        out[name] = {"段": r.stage, "候補": len(r.candidates), "理由": list(r.reasons())}
    return out


def test_measure_stops(capsys: pytest.CaptureFixture) -> None:
    m = measure_stops()
    assert [v["段"] for v in m.values()] == [RR.SELECTION] * 3 + [RR.CONVERSION] * 4
    assert m["k_aimai.csv"]["候補"] == 2 and m["l_michi.csv"]["候補"] == 0
    assert [v["理由"][0] for v in m.values()] == [
        "係が 2 件以上", "係が 0 件", "係が 0 件", "見出し行が見つからない",
        "列数が宣言と違う", "宣言した形で読めない値", "required の列が埋まらない"]
    with capsys.disabled():
        print("")
        for name, v in m.items():
            print(f"[measure] {name}: {v['段']}で止まった({' / '.join(v['理由'])})")
