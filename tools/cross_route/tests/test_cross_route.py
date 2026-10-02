"""cross_route のテスト。fixture は全て合成データ(fixtures/make_fixtures.py)、値も区分名も出典名も架空。

後半の test_measure_* が記事の数値の出どころ。
  measure_pairs     合成の 2 経路(13 行と 14 行)を突き合わせ、4 判定の内訳を数える
  measure_tampering 2 経路の表を 1 か所ずつ書き換え、判定が変わる / 止まるかを数える
  measure_rate      一致率を 2 つの分母で出し、分母に何を含めたかの文字列も見る
決定論なので、値が変われば記事の数字も変える。
"""
from __future__ import annotations

import csv
import hashlib
import inspect
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FX))
import cross_route as CR  # noqa: E402
import make_fixtures as MF  # noqa: E402

A_CSV, B_CSV = FX / "route_a.csv", FX / "route_b.csv"


def cross(a: Path = A_CSV, b: Path = B_CSV, name_a: str = MF.NAME_A, name_b: str = MF.NAME_B) -> CR.Cross:
    return CR.crosscheck(CR.Route.load(a, name_a), CR.Route.load(b, name_b))


def result_of(c: CR.Cross, key: str) -> CR.Result:
    return next(r for r in c.results if r.key == key)


def prepare(d: Path) -> tuple:
    """合成の出典と 2 経路の表を d に作り、(rows_a, rows_b) を返す。"""
    out = MF.build(d)
    return out["rows_a"], out["rows_b"]


def rerun(d: Path, ra: list, rb: list, name_a: str = MF.NAME_A, name_b: str = MF.NAME_B) -> CR.Cross:
    MF.write_route(d / "route_a.csv", ra)
    MF.write_route(d / "route_b.csv", rb)
    return cross(d / "route_a.csv", d / "route_b.csv", name_a, name_b)


def _row(rows: list, key: str) -> dict:
    return next(r for r in rows if r["key"] == key)


# ---------------------------------------------------------------- 正規化(既定を持たない)

def test_normalizers_are_named_not_guessed() -> None:
    assert set(CR.NORMALIZERS) == {"そのまま", "全角半角", "カンマ除去", "パーセント", "円", "桁そろえ", "日付"}
    assert CR.normalize(" 9.31 ", "そのまま") == "9.31"
    assert CR.normalize("9.31%", "パーセント") == "9.31"
    assert CR.normalize("9.310", "桁そろえ") == "9.31"
    assert CR.normalize("１，３１０，０００円", "全角半角+カンマ除去+円") == "1310000"
    assert CR.normalize("2017年4月1日", "日付") == "2017-04-01"
    assert CR.normalize("1,204", "カンマ除去") == "1204"


def test_trailing_zeros_need_a_name_too() -> None:
    """9.310 と 9.31 は、桁そろえ を名前で呼ばない限り別の文字として扱う。"""
    assert CR.normalize("9.310", "そのまま") == "9.310"
    assert CR.normalize("9.310", "そのまま") != CR.normalize("9.31", "そのまま")
    assert CR.normalize("9.310", "桁そろえ") == CR.normalize("9.31", "桁そろえ")
    # 桁そろえ は末尾の 0 をそろえるだけで、桁を落とす丸めはしない
    assert CR.normalize("9.315", "桁そろえ") == "9.315"


def test_unknown_normalizer_name_is_an_error() -> None:
    with pytest.raises(ValueError, match="登録されていない normalizer"):
        CR.normalize("9.31", "よくある正規化")
    assert not CR.known_chain("")
    assert not CR.known_chain("そのまま+よくある正規化")
    assert CR.known_chain("パーセント+桁そろえ")


# ---------------------------------------------------------------- 経路の表

def test_route_needs_the_comparison_columns_in_the_header(tmp_path: Path) -> None:
    p = tmp_path / "route.csv"
    p.write_text("key,value,unit\n料率,9.31,%\n", encoding="utf-8")
    with pytest.raises(CR.TableError, match="見出しの列が足りない"):
        CR.Route.load(p)


def test_two_routes_with_the_same_name_are_refused() -> None:
    a = CR.Route.load(A_CSV, "同じ名前")
    b = CR.Route.load(B_CSV, "同じ名前")
    with pytest.raises(CR.TableError, match="経路名が同じ"):
        CR.Cross(a, b)


def test_a_source_pin_row_becomes_a_route_row_by_adding_unit_and_scope(tmp_path: Path) -> None:
    """source_pin のピン行に unit と scope の 2 列を足せば経路の行として読める(持ち越す列は比較に使わない)。"""
    pin_columns = ["key", "value", "raw_text", "source_kind", "source_file", "source_sha256",
                   "locator", "method", "normalizer", "captured_at", "note"]   # source_pin のピン行
    p = tmp_path / "pins_plus.csv"   # 2 列(unit / scope)を足しただけの表
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=pin_columns + ["unit", "scope"])
        w.writeheader()
        w.writerow({"key": "料率_地域I", "value": "9.31", "raw_text": "9.31%",
                    "source_kind": "表形式の xlsx", "source_file": "genpon.xlsx",
                    "source_sha256": "0" * 64, "locator": "料率!B3", "method": "xlsx_cell",
                    "normalizer": "桁そろえ", "captured_at": MF.CAPTURED, "note": "合成(架空)",
                    "unit": "%", "scope": "地域I・労使折半"})
    route = CR.Route.load(p, "ピンの表")
    row = route.rows[0]
    assert (row.key, row.value, row.unit, row.scope) == ("料率_地域I", "9.31", "%", "地域I・労使折半")
    assert (row.raw_text, row.locator) == ("9.31%", "料率!B3")      # 持ち越すだけ
    # 持ち越した列は比較に使わない: raw_text と locator が違っても agree になる
    other = CR.Route(
        "別の表",
        (CR.Row(key="料率_地域I", value="9.310", unit="%", scope="地域I・労使折半",
                source_file="joryu.json", source_sha256="1" * 64, normalizer="桁そろえ",
                captured_at=MF.CAPTURED, raw_text="まったく別の生の文字", locator="別の場所"),))
    assert CR.crosscheck(route, other).get("料率_地域I").value == "9.31"


# ---------------------------------------------------------------- 突合の順序(指すものが先、値が後)

def test_same_value_is_not_compared_when_the_scope_is_not_declared() -> None:
    """値は一致しているが scope が空欄なので比較に進まない(= 値が合うかより先に見る)。"""
    r = result_of(cross(), "適用開始日_給付日数")
    assert (r.judgment, r.reason) == (CR.INCOMPARABLE, "scope 空欄")
    assert (r.value_a, r.value_b) == ("2017-04-01", "2017-04-01")   # 正規化後は一致している


def test_same_name_different_scheme_is_incomparable_not_disagree() -> None:
    """同じ名前で別の負担区分の数字を並べた組は、不一致ではなく『比べられない』になる。"""
    r = result_of(cross(), "支援金率")
    assert (r.judgment, r.reason) == (CR.INCOMPARABLE, "scope 不一致")
    assert "労使折半" in r.detail and "事業主のみ" in r.detail


def test_unit_mismatch_is_incomparable() -> None:
    r = result_of(cross(), "日額_区分C")
    assert (r.judgment, r.reason) == (CR.INCOMPARABLE, "unit 不一致")
    assert (r.value_a, r.value_b) == ("7294", "7294")


def test_empty_normalizer_stops_before_the_values_are_compared() -> None:
    r = result_of(cross(), "改定率_年1")
    assert (r.judgment, r.reason) == (CR.INCOMPARABLE, "normalizer 空欄")
    assert r.value_a == "" and r.value_b == ""


def test_one_route_only_is_recorded_as_single_route() -> None:
    for key in ("適用開始日_従前額", "最低賃金_地域I", "業種料率_業種A"):
        r = result_of(cross(), key)
        assert (r.judgment, r.reason) == (CR.SINGLE, CR.SINGLE_REASON)


def test_duplicate_key_in_one_route_is_incomparable(tmp_path: Path) -> None:
    ra, rb = prepare(tmp_path)
    ra.append(dict(_row(ra, "料率_地域I")))
    r = result_of(rerun(tmp_path, ra, rb), "料率_地域I")
    assert (r.judgment, r.reason) == (CR.INCOMPARABLE, "同じ key が同じ経路に 2 行")


def test_empty_key_row_is_kept_as_a_missing_column(tmp_path: Path) -> None:
    ra, rb = prepare(tmp_path)
    broken = dict(_row(ra, "料率_地域II"))
    broken["key"] = ""
    ra.append(broken)
    r = result_of(rerun(tmp_path, ra, rb), "(key 空欄)")
    assert (r.judgment, r.reason) == (CR.INCOMPARABLE, "列が足りない")


# ---------------------------------------------------------------- 引き当て(正を選ぶ経路が無い)

def test_get_returns_both_sources_for_an_agreeing_key() -> None:
    g = cross().get("料率_地域I")
    assert (g.value, g.unit, g.scope) == ("9.31", "%", "地域I・労使折半")
    assert (g.route_a, g.route_b) == (MF.NAME_A, MF.NAME_B)
    assert g.source_a == MF.A_FILE and g.source_b == MF.B_JSON
    assert g.sha256_a != g.sha256_b and len(g.sha256_a) == 64 and len(g.sha256_b) == 64
    assert (g.normalizer_a, g.normalizer_b) == ("パーセント+桁そろえ", "桁そろえ")
    assert [s["route"] for s in g.as_dict()["sources"]] == [MF.NAME_A, MF.NAME_B]


def test_get_stops_on_disagree_and_does_not_pick_a_side() -> None:
    c = cross()
    with pytest.raises(CR.CrossError) as e:
        c.get("上限額_区分B")
    assert e.value.reason == CR.DISAGREE
    # 止まったあとも、どちらが正かは返らない(両方の値が detail に並ぶだけ)
    r = result_of(c, "上限額_区分B")
    assert "8490" in r.detail and "8480" in r.detail


def test_get_stops_on_single_route_and_incomparable() -> None:
    c = cross()
    for key, reason in (("適用開始日_従前額", CR.SINGLE_REASON),
                        ("支援金率", "scope 不一致"),
                        ("日額_区分C", "unit 不一致"),
                        ("改定率_年1", "normalizer 空欄"),
                        ("適用開始日_給付日数", "scope 空欄")):
        with pytest.raises(CR.CrossError) as e:
            c.get(key)
        assert e.value.reason == reason
    with pytest.raises(CR.CrossError) as e:
        c.get("どちらにも無い key")
    assert e.value.reason == "どちらの経路にも無い"


def test_get_before_crosscheck_stops() -> None:
    c = CR.Cross(CR.Route.load(A_CSV, MF.NAME_A), CR.Route.load(B_CSV, MF.NAME_B))
    with pytest.raises(CR.CrossError) as e:
        c.get("料率_地域I")
    assert e.value.reason == "突合前に get を呼んだ"
    c.crosscheck()
    assert c.get("料率_地域I").value == "9.31"


def test_there_is_no_argument_for_choosing_the_authoritative_route() -> None:
    """不一致のときにどちらかを正として返す引数を、関数も CLI も持たない。"""
    assert list(inspect.signature(CR.Cross.get).parameters) == ["self", "key"]
    assert list(inspect.signature(CR.Cross.crosscheck).parameters) == ["self"]
    assert list(inspect.signature(CR.crosscheck).parameters) == ["a", "b"]
    assert list(inspect.signature(CR.Cross.rate).parameters) == ["self"]
    assert list(inspect.signature(CR.Cross.report).parameters) == ["self"]
    help_text = cli("get", "--help").stdout
    assert set(re.findall(r"--[a-z-]+", help_text)) == {"--help", "--name-a", "--name-b"}


# ---------------------------------------------------------------- 報告と一致率

def test_report_has_both_routes_values_judgment_reason_and_both_sources() -> None:
    c = cross()
    cols = c.report_columns()
    assert cols == ["key", f"{MF.NAME_A}_value", f"{MF.NAME_B}_value", "judgment", "reason",
                    "detail", f"{MF.NAME_A}_source", f"{MF.NAME_B}_source"]
    rows = c.report()
    assert len(rows) == 15
    row = next(r for r in rows if r["key"] == "料率_地域I")
    assert row[f"{MF.NAME_A}_value"] == "9.31" and row[f"{MF.NAME_B}_value"] == "9.31"
    assert MF.A_FILE in row[f"{MF.NAME_A}_source"] and MF.B_JSON in row[f"{MF.NAME_B}_source"]
    single = next(r for r in rows if r["key"] == "最低賃金_地域I")
    assert single[f"{MF.NAME_A}_value"] == "" and single[f"{MF.NAME_A}_source"] == ""


def test_rate_never_returns_a_bare_ratio() -> None:
    d = cross().rate()
    for k in CR.JUDGMENTS:
        assert k in d
    assert d["分母に含めたもの"]
    assert "一致率_比べられた行のみ" in d and "一致率_全ての行" in d
    assert d["compared"] == d[CR.AGREE] + d[CR.DISAGREE]
    assert d["unchecked"] == d[CR.SINGLE] + d[CR.INCOMPARABLE]
    assert d["rows"] == d["compared"] + d["unchecked"]
    # 一致率だけを返す呼び方が無い(関数名に ratio / 一致率 だけのものは存在しない)
    names = {n for n, _ in inspect.getmembers(CR.Cross, inspect.isfunction)}
    assert names & {"rate"} == {"rate"} and not names & {"ratio", "match_rate", "agreement_rate"}


def test_fixture_sha_matches_the_synthetic_source_files(tmp_path: Path) -> None:
    """出典の列は合成の原本の現物から計算されている(部品は現物を読まないが、fixture は噛み合っている)。"""
    ra, rb = prepare(tmp_path)
    for rows in (ra, rb):
        for row in rows:
            want = hashlib.sha256((tmp_path / row["source_file"]).read_bytes()).hexdigest()
            assert row["source_sha256"] == want
            assert CR.sha256_of(tmp_path / row["source_file"]) == want


# ---------------------------------------------------------------- 測定(記事の数値の出どころ)

def measure_pairs() -> dict:
    c = cross()
    cnt = c.counts()
    by_reason: dict = {}
    for r in c.results:
        if r.reason:
            by_reason[r.reason] = by_reason.get(r.reason, 0) + 1
    return {"rows_a": len(c.a), "rows_b": len(c.b), "keys": len(c.results), **cnt,
            "by_reason": by_reason}


def measure_tampering(d: Path) -> dict:
    """2 経路の表を 1 か所ずつ書き換え、判定が変わる / 止まるかを見る。"""
    KEY = "料率_地域I"

    def judge(ra: list, rb: list, name_a: str = MF.NAME_A, name_b: str = MF.NAME_B) -> str:
        try:
            c = rerun(d, ra, rb, name_a, name_b)
        except CR.TableError as e:
            return f"表を読まない: {str(e).split(':')[0]}"
        r = result_of(c, KEY)
        return f"{r.judgment}: {r.reason}" if r.reason else r.judgment

    cases: dict = {}

    def case(name: str, change) -> None:
        ra, rb = prepare(d)
        cases[name] = change(ra, rb)

    case("経路 A の value を 1 桁変える",
         lambda ra, rb: judge([*ra], rb) if _set(ra, KEY, "value", "9.41%") else "")
    case("経路 B の unit を変える",
         lambda ra, rb: judge(ra, rb) if _set(rb, KEY, "unit", "ポイント") else "")
    case("経路 A の scope を空にする",
         lambda ra, rb: judge(ra, rb) if _set(ra, KEY, "scope", "") else "")
    case("経路 B の scope を別の負担区分にする",
         lambda ra, rb: judge(ra, rb) if _set(rb, KEY, "scope", "地域I・事業主のみ") else "")
    case("経路 A の normalizer を空にする",
         lambda ra, rb: judge(ra, rb) if _set(ra, KEY, "normalizer", "") else "")
    case("経路 A の normalizer を登録外の名前にする",
         lambda ra, rb: judge(ra, rb) if _set(ra, KEY, "normalizer", "よくある正規化") else "")
    case("経路 A の normalizer を そのまま に変える",
         lambda ra, rb: judge(ra, rb) if _set(ra, KEY, "normalizer", "そのまま") else "")
    case("経路 A の value に注記が残る",
         lambda ra, rb: judge(ra, rb) if _set(ra, KEY, "value", "9.31%(改定後)") else "")
    case("経路 A の captured_at を空にする",
         lambda ra, rb: judge(ra, rb) if _set(ra, KEY, "captured_at", "") else "")
    case("経路 A の source_file を空にする",
         lambda ra, rb: judge(ra, rb) if _set(ra, KEY, "source_file", "") else "")
    case("経路 B からその行を消す",
         lambda ra, rb: judge(ra, [r for r in rb if r["key"] != KEY]))
    case("経路 A に同じ key の行を 2 行にする",
         lambda ra, rb: judge([*ra, dict(_row(ra, KEY))], rb))
    case("経路名を両方同じにする", lambda ra, rb: judge(ra, rb, "同じ名前", "同じ名前"))
    case("両経路の value を同じように書き換える",
         lambda ra, rb: judge(ra, rb) if (_set(ra, KEY, "value", "9.77%")
                                          and _set(rb, KEY, "value", "9.770")) else "")

    # 列の書き換えではないもの(呼ぶ順序)
    ra, rb = prepare(d)
    MF.write_route(d / "route_a.csv", ra)
    MF.write_route(d / "route_b.csv", rb)
    c = CR.Cross(CR.Route.load(d / "route_a.csv", MF.NAME_A), CR.Route.load(d / "route_b.csv", MF.NAME_B))
    try:
        c.get(KEY)
        cases["突合前に get を呼ぶ"] = "agree"
    except CR.CrossError as e:
        cases["突合前に get を呼ぶ"] = f"止まる: {e.reason}"
    # 経路 A に key が空の行を足す(対象の key ではなく、その行自体の判定を見る)
    ra, rb = prepare(d)
    broken = dict(_row(ra, "料率_地域II"))
    broken["key"] = ""
    r = result_of(rerun(d, [*ra, broken], rb), "(key 空欄)")
    cases["経路 A に key が空の行を足す"] = f"{r.judgment}: {r.reason}"

    changed = {k: v for k, v in cases.items() if v != "agree"}
    return {"cases": len(cases), "changed": len(changed), "by_case": cases}


def _set(rows: list, key: str, col: str, value: str) -> bool:
    _row(rows, key)[col] = value
    return True


def measure_rate() -> dict:
    return cross().rate()


def test_measure_pairs(capsys: pytest.CaptureFixture) -> None:
    m = measure_pairs()
    assert m["rows_a"] == 13 and m["rows_b"] == 14 and m["keys"] == 15
    assert m["agree"] == 7 and m["disagree"] == 1
    assert m["single_route"] == 3 and m["incomparable"] == 4
    assert m["by_reason"] == {"scope 空欄": 1, "scope 不一致": 1, "unit 不一致": 1,
                              "normalizer 空欄": 1, CR.SINGLE_REASON: 3}
    with capsys.disabled():
        print(f"\n[measure] 合成の 2 経路(経路 A {m['rows_a']} 行 / 経路 B {m['rows_b']} 行)"
              f"の key の和集合 {m['keys']}: "
              f"agree {m['agree']} / disagree {m['disagree']} / "
              f"片系統だけ {m['single_route']} / 比べられない {m['incomparable']}")
        for k, v in m["by_reason"].items():
            print(f"[measure]   {k}: {v} 件")


def test_measure_tampering(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    m = measure_tampering(tmp_path)
    assert m["cases"] == 16 and m["changed"] == 15
    assert m["by_case"]["両経路の value を同じように書き換える"] == "agree"
    assert m["by_case"]["経路 A の value を 1 桁変える"] == "disagree"
    assert m["by_case"]["経路 A の normalizer を そのまま に変える"] == "disagree"
    assert m["by_case"]["経路 B の unit を変える"] == "incomparable: unit 不一致"
    assert m["by_case"]["経路 A の scope を空にする"] == "incomparable: scope 空欄"
    assert m["by_case"]["経路 B の scope を別の負担区分にする"] == "incomparable: scope 不一致"
    assert m["by_case"]["経路 A の normalizer を空にする"] == "incomparable: normalizer 空欄"
    assert m["by_case"]["経路 A の normalizer を登録外の名前にする"] == "incomparable: 列が足りない"
    assert m["by_case"]["経路 A の value に注記が残る"] == "incomparable: normalizer を通せない"
    assert m["by_case"]["経路 A の captured_at を空にする"] == "incomparable: 列が足りない"
    assert m["by_case"]["経路 A の source_file を空にする"] == "incomparable: 列が足りない"
    assert m["by_case"]["経路 B からその行を消す"] == "single_route: 片方の経路にしか無い"
    assert m["by_case"]["経路 A に同じ key の行を 2 行にする"] == "incomparable: 同じ key が同じ経路に 2 行"
    assert m["by_case"]["経路名を両方同じにする"] == "表を読まない: 経路名が同じ"
    assert m["by_case"]["突合前に get を呼ぶ"] == "止まる: 突合前に get を呼んだ"
    assert m["by_case"]["経路 A に key が空の行を足す"] == "incomparable: 列が足りない"
    # 9 つの理由コードすべてに到達している
    reached = {v.split(": ", 1)[1] for v in m["by_case"].values() if ": " in v}
    assert reached == set(CR.REASONS) | {CR.SINGLE_REASON}
    with capsys.disabled():
        print(f"\n[measure] 2 経路の表を 1 か所ずつ書き換えた {m['cases']} 通り: "
              f"判定が変わった / 止まった {m['changed']} 通り"
              f"(変わらなかった 1 通り = 両経路の value を同じように書き換える)")
        for k, v in m["by_case"].items():
            print(f"[measure]   {k} → {v}")


def test_measure_rate(capsys: pytest.CaptureFixture) -> None:
    m = measure_rate()
    assert m["compared"] == 8 and m["unchecked"] == 7 and m["rows"] == 15
    assert m["一致率_比べられた行のみ"] == "0.8750"
    assert m["一致率_全ての行"] == "0.4667"
    assert "片系統だけ 3" in m["分母に含めたもの"] and "比べられない 4" in m["分母に含めたもの"]
    with capsys.disabled():
        print(f"\n[measure] 一致率: 比べられた {m['compared']} 行だけを分母にすると "
              f"{m['一致率_比べられた行のみ']}、全ての行 {m['rows']} を分母にすると {m['一致率_全ての行']}")
        print(f"[measure]   分母に含めたもの: {m['分母に含めたもの']}")


# ---------------------------------------------------------------- CLI

def cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "cross_route.py"), *args],
                          capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT))


def names(*args: str) -> list:
    return [*args, "--name-a", MF.NAME_A, "--name-b", MF.NAME_B]


def test_cli_check_exits_three_when_something_needs_a_human() -> None:
    r = cli(*names("check", str(A_CSV), str(B_CSV)))
    assert r.returncode == 3
    d = json.loads(r.stdout.strip())
    assert d["ok"] is False
    assert (d["agree"], d["disagree"], d["single_route"], d["incomparable"]) == (7, 1, 3, 4)


def test_cli_check_exits_zero_when_only_agree_and_single_route(tmp_path: Path) -> None:
    """片系統だけは異常ではなく記録なので止めない(取れない行を消す動機を作らない)。"""
    ra, rb = prepare(tmp_path)
    keep = {"料率_地域I", "料率_地域II", "最低額_年1"}
    MF.write_route(tmp_path / "a.csv", [r for r in ra if r["key"] in keep | {"適用開始日_従前額"}])
    MF.write_route(tmp_path / "b.csv", [r for r in rb if r["key"] in keep])
    r = cli(*names("check", str(tmp_path / "a.csv"), str(tmp_path / "b.csv")))
    assert r.returncode == 0
    d = json.loads(r.stdout.strip())
    assert d["ok"] is True and d["agree"] == 3 and d["single_route"] == 1
    assert d["disagree"] == 0 and d["incomparable"] == 0


def test_cli_get_exits_zero_on_agree_and_three_otherwise() -> None:
    ok = cli(*names("get", str(A_CSV), str(B_CSV), "料率_地域I"))
    assert ok.returncode == 0 and json.loads(ok.stdout)["value"] == "9.31"
    ng = cli(*names("get", str(A_CSV), str(B_CSV), "支援金率"))
    assert ng.returncode == 3 and json.loads(ng.stdout)["reason"] == "scope 不一致"


def test_cli_rate_prints_the_four_counts_and_the_denominator() -> None:
    r = cli(*names("rate", str(A_CSV), str(B_CSV)))
    assert r.returncode == 0
    d = json.loads(r.stdout.strip())
    assert all(k in d for k in CR.JUDGMENTS) and d["分母に含めたもの"]


def test_cli_report_csv_has_a_row_per_key() -> None:
    r = cli(*names("report", str(A_CSV), str(B_CSV), "--format", "csv"))
    assert r.returncode == 0
    rows = list(csv.DictReader(r.stdout.splitlines()))
    assert len(rows) == 15
    assert {row["judgment"] for row in rows} == set(CR.JUDGMENTS)


def test_cli_init_writes_the_header_and_refuses_to_overwrite(tmp_path: Path) -> None:
    p = tmp_path / "route_new.csv"
    r = cli("init", str(p))
    assert r.returncode == 0
    head = p.read_text(encoding="utf-8").splitlines()[0]
    assert head.split(",") == list(CR.COLUMNS)
    again = cli("init", str(p))
    assert again.returncode == 2 and "すでにある" in again.stderr


def test_cli_refuses_a_broken_table(tmp_path: Path) -> None:
    p = tmp_path / "broken.csv"
    p.write_text("key,value\n料率,9.31\n", encoding="utf-8")
    r = cli("check", str(p), str(B_CSV))
    assert r.returncode == 2 and "見出しの列が足りない" in r.stderr
