"""asof_table のテスト。fixture は全て合成データ(fixtures/make_fixtures.py)、地域名も料率も出典名も架空。

後半の test_measure_* は、同じ合成の表に同じ引き当てを流して
  (a) 適用開始日つきの履歴(key と 1 つの日付だけで、その日以前の最新の行を採る)
  (b) この部品(基準日 → 知識時間 → 有効時間 → 対象 → 最高 priority の 1 行)
を比べる。記事の数値はここから取る。決定論なので、値が変われば記事の数字も変える。
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FX))
import asof_table as A  # noqa: E402
import make_fixtures as MF  # noqa: E402

TABLE = FX / "ryouritsu.csv"
BROKEN = FX / "ryouritsu_fuseigou.csv"

AREAS = MF.AREAS
BANDS = ["1960年度以前", "1961年度以降"]
# 2024-01 から 2026-06 までの 30 か月。給与 1 か月 = 1 件の case
MONTHS = [date(y, m, 1) for y in (2024, 2025, 2026) for m in range(1, 13)
          if date(y, m, 1) <= date(2026, 6, 1)]


@pytest.fixture(scope="module")
def table() -> A.Table:
    return A.Table.from_csv(TABLE)


def case_of(month: date, area: str, band: str) -> dict[str, str]:
    """1 か月分の給与の case。締切は前月末、支払は当月。基準日の名前は行の側が決める。"""
    shime = month.replace(day=1) - __import__("datetime").timedelta(days=1)
    return {"対象月初日": month.isoformat(), "賃金締切日": shime.isoformat(),
            "sel_地域": area, "sel_生年月日帯": band}


# ---------------------------------------------------------------- 表の読み込み

def test_clean_table_shape(table: A.Table) -> None:
    assert len(table) == 44
    assert table.keys() == ["保険料率_甲", "保険料率_乙", "継続給付_支給率", "適用要件_丁"]
    assert table.dims == ("sel_地域", "sel_生年月日帯")


def test_row_numbers_are_one_origin(table: A.Table) -> None:
    assert [r.number for r in table.rows][:3] == [1, 2, 3]
    assert table.rows[-1].number == 44


@pytest.mark.parametrize("drop", ["key", "basis", "valid_from", "known_from", "priority", "value", "source"])
def test_missing_column_is_a_table_error(table: A.Table, drop: str) -> None:
    rec = {c: "x" for c in MF.COLUMNS if c != drop}
    with pytest.raises(A.TableError, match="必要な列が無い"):
        A.Table.from_records([rec])


@pytest.mark.parametrize("col,msg", [("key", "key が空"), ("basis", "basis が空"),
                                     ("known_from", "known_from が空")])
def test_empty_required_value_is_a_table_error(col: str, msg: str) -> None:
    rec = {c: "" for c in MF.COLUMNS}
    rec.update({"key": "k", "basis": "b", "known_from": "2025-04-01", "priority": "0"})
    rec[col] = ""
    with pytest.raises(A.TableError, match=msg):
        A.Table.from_records([rec])


def test_priority_must_be_an_integer() -> None:
    rec = {c: "" for c in MF.COLUMNS}
    rec.update({"key": "k", "basis": "b", "known_from": "2025-04-01", "priority": "ふつう"})
    with pytest.raises(A.TableError, match="priority が整数でない"):
        A.Table.from_records([rec])


@pytest.mark.parametrize("col", ["valid_from", "valid_to", "known_from", "known_to"])
def test_date_must_be_iso(col: str) -> None:
    rec = {c: "" for c in MF.COLUMNS}
    rec.update({"key": "k", "basis": "b", "known_from": "2025-04-01", "priority": "0"})
    rec[col] = "令和7年4月1日"
    with pytest.raises(A.TableError, match="YYYY-MM-DD で読めない"):
        A.Table.from_records([rec])


def test_empty_table_is_an_error() -> None:
    with pytest.raises(A.TableError, match="行が 1 つも無い"):
        A.Table.from_records([])


def test_json_and_csv_give_the_same_table(tmp_path: Path, table: A.Table) -> None:
    recs = [{**{c: "" for c in MF.COLUMNS}, "key": r.key, "basis": r.basis,
             "valid_from": r.valid_from.isoformat() if r.valid_from else "",
             "valid_to": r.valid_to.isoformat() if r.valid_to else "",
             "known_from": r.known_from.isoformat(), "known_quality": r.known_quality,
             "priority": str(r.priority), "value": r.value, "source": r.source, **r.sel}
            for r in table.rows]
    p = tmp_path / "t.json"
    p.write_text(json.dumps(recs, ensure_ascii=False), encoding="utf-8")
    got = A.Table.load(p)
    assert len(got) == len(table)
    case = case_of(date(2025, 6, 1), "地域C", "1961年度以降")
    assert A.resolve(got, "保険料率_甲", case).value == A.resolve(table, "保険料率_甲", case).value


def test_a_table_without_any_selector_column_works() -> None:
    rec = {"key": "k", "basis": "日付", "valid_from": "2025-04-01", "valid_to": "",
           "known_from": "2025-01-01", "known_to": "", "known_quality": "実値",
           "priority": "0", "value": "7", "source": "合成"}
    t = A.Table.from_records([rec])
    assert t.dims == ()
    assert A.resolve(t, "k", {"日付": "2025-05-01"}).value == "7"


# ---------------------------------------------------------------- 引けたとき

def test_value_comes_with_source_valid_from_and_row(table: A.Table) -> None:
    r = A.resolve(table, "保険料率_甲", case_of(date(2025, 6, 1), "地域A", "1961年度以降"))
    assert r.ok
    assert r.basis == "対象月初日"
    assert r.value == "9.60"
    assert r.valid_from == date(2025, 3, 1)
    assert r.source == "合成の料率表 2025 年度版(架空)"
    assert r.row == 13
    assert r.priority == 0


def test_value_is_returned_as_text(table: A.Table) -> None:
    r = A.resolve(table, "保険料率_甲", case_of(date(2025, 6, 1), "地域A", "1961年度以降"))
    assert isinstance(r.value, str) and r.value == "9.60"


def test_each_area_gets_its_own_row(table: A.Table) -> None:
    got = [A.resolve(table, "保険料率_甲", case_of(date(2024, 6, 1), a, BANDS[1])).value for a in AREAS]
    assert got == ["9.50", "9.55", "9.60", "9.65", "9.70", "9.75",
                   "9.80", "9.85", "9.90", "9.95", "10.00", "10.05"]
    assert len(set(got)) == 12


def test_the_year_boundary_is_half_open(table: A.Table) -> None:
    before = A.resolve(table, "保険料率_甲", case_of(date(2025, 2, 1), "地域A", BANDS[1]))
    on = A.resolve(table, "保険料率_甲", case_of(date(2025, 3, 1), "地域A", BANDS[1]))
    assert (before.value, on.value) == ("9.50", "9.60")


def test_each_key_is_drawn_by_its_own_basis(table: A.Table) -> None:
    """同じ case でも、甲は対象月初日、乙は賃金締切日で引かれる(3 月・4 月で年度がずれる)。"""
    case = case_of(date(2025, 4, 1), "地域A", BANDS[1])
    assert table.basis_of("保険料率_甲") == "対象月初日"
    assert table.basis_of("保険料率_乙") == "賃金締切日"
    assert A.resolve(table, "保険料率_甲", case).valid_from == date(2025, 3, 1)
    assert A.resolve(table, "保険料率_乙", case).valid_from == date(2024, 4, 1)


# ---------------------------------------------------------------- 決まらないとき

def test_five_reason_codes_and_no_more() -> None:
    assert list(A.REASONS) == ["基準日が case に無い", "as_of 時点で未公表", "収録範囲の外",
                               "同順位で複数該当", "公表日が仮置き"]


def test_missing_basis_in_case(table: A.Table) -> None:
    r = A.resolve(table, "保険料率_乙", {"対象月初日": "2025-06-01"})
    assert not r.ok and r.reason == "基準日が case に無い"
    assert "賃金締切日" in r.detail


def test_key_not_in_table(table: A.Table) -> None:
    r = A.resolve(table, "存在しない率", {"対象月初日": "2025-06-01"})
    assert not r.ok and r.reason == "収録範囲の外"


def test_before_the_first_period(table: A.Table) -> None:
    r = A.resolve(table, "保険料率_甲", case_of(date(2024, 1, 1), "地域A", BANDS[1]))
    assert not r.ok and r.reason == "収録範囲の外"
    assert r.value == ""


def test_a_gap_in_the_periods_stops(tmp_path: Path) -> None:
    t = A.Table.from_csv(BROKEN)
    r = A.resolve(t, "穴のある表", {"対象月初日": "2025-07-01"})
    assert not r.ok and r.reason == "収録範囲の外"


def test_two_rows_at_the_same_priority_stop(table: A.Table) -> None:
    recs = [{"key": "k", "basis": "日付", "valid_from": "2025-04-01", "valid_to": "",
             "known_from": "2025-01-01", "known_to": "", "known_quality": "実値",
             "priority": "0", "value": v, "source": "合成", "sel_区分": s}
            for v, s in (("1", ""), ("2", "甲"))]
    t = A.Table.from_records(recs)
    r = A.resolve(t, "k", {"日付": "2025-05-01", "sel_区分": "甲"})
    assert not r.ok and r.reason == "同順位で複数該当"
    assert r.rows == (1, 2)


def test_not_published_yet_at_as_of(table: A.Table) -> None:
    case = case_of(date(2026, 3, 1), "地域A", BANDS[1])
    r = A.resolve(table, "保険料率_甲", case, as_of=date(2026, 2, 5))
    assert not r.ok and r.reason == "as_of 時点で未公表"
    assert r.rows == (25,)


def test_provisional_publication_date_stops(table: A.Table) -> None:
    """乙の known_from は valid_from で仮置きしてある。公表前かどうかは表から決まらないので止まる。"""
    case = case_of(date(2026, 5, 1), "地域A", BANDS[1])
    r = A.resolve(table, "保険料率_乙", case, as_of=date(2026, 3, 20))
    assert not r.ok and r.reason == "公表日が仮置き"
    assert r.rows == (39,)


def test_a_failed_result_carries_no_value(table: A.Table) -> None:
    for r in (A.resolve(table, "保険料率_乙", {"対象月初日": "2025-06-01"}),
              A.resolve(table, "保険料率_甲", case_of(date(2024, 1, 1), "地域A", BANDS[1]))):
        assert not r.ok
        assert (r.value, r.source, r.valid_from, r.row) == ("", "", None, None)


def test_every_reason_code_is_reachable(table: A.Table) -> None:
    broken = A.Table.from_records([
        {"key": "k", "basis": "日付", "valid_from": "2025-04-01", "valid_to": "",
         "known_from": "2025-01-01", "known_to": "", "known_quality": "実値",
         "priority": "0", "value": v, "source": "合成"} for v in ("1", "2")])
    got = {
        A.resolve(table, "保険料率_乙", {"対象月初日": "2025-06-01"}).reason,
        A.resolve(table, "保険料率_甲", case_of(date(2026, 3, 1), "地域A", BANDS[1]),
                  as_of=date(2026, 2, 5)).reason,
        A.resolve(table, "存在しない率", {"対象月初日": "2025-06-01"}).reason,
        A.resolve(broken, "k", {"日付": "2025-05-01"}).reason,
        A.resolve(table, "保険料率_乙", case_of(date(2026, 5, 1), "地域A", BANDS[1]),
                  as_of=date(2026, 3, 20)).reason,
    }
    assert got == set(A.REASONS)


# ---------------------------------------------------------------- 黙って落ちない

def test_resolve_has_no_fallback_argument() -> None:
    import inspect
    names = list(inspect.signature(A.resolve).parameters)
    assert names == ["table", "key", "case", "as_of"]


def test_no_fallback_to_the_latest_row(table: A.Table) -> None:
    """収録範囲の外で、直近の行が存在していても値は返らない(乙は 2024-04-01 から収録)。"""
    case = case_of(date(2024, 4, 1), "地域A", BANDS[1])     # 賃金締切日 = 2024-03-31
    r = A.resolve(table, "保険料率_乙", case)
    assert not r.ok and r.reason == "収録範囲の外"
    assert A.naive_lookup(table, "保険料率_乙", date(2024, 4, 1)).value == "0.60"


# ---------------------------------------------------------------- 遡及の再現

def test_as_of_alone_changes_which_row_is_hit(table: A.Table) -> None:
    """同じ key・同じ対象月初日のまま、引く時点だけを改定の公表前後に置く。"""
    case = case_of(date(2026, 3, 1), "地域A", BANDS[1])
    before = A.resolve(table, "保険料率_甲", case, as_of=date(2026, 2, 5))
    after = A.resolve(table, "保険料率_甲", case, as_of=date(2026, 2, 20))
    now = A.resolve(table, "保険料率_甲", case)
    assert (before.ok, after.ok, now.ok) == (False, True, True)
    assert before.reason == "as_of 時点で未公表"
    assert (after.value, now.value) == ("9.70", "9.70")
    assert after.valid_from == date(2026, 3, 1)


def test_as_of_before_the_previous_revision_gives_the_previous_row(table: A.Table) -> None:
    case = case_of(date(2025, 6, 1), "地域A", BANDS[1])
    assert A.resolve(table, "保険料率_甲", case, as_of=date(2025, 2, 20)).value == "9.60"
    assert A.resolve(table, "保険料率_甲", case, as_of=date(2025, 2, 1)).reason == "as_of 時点で未公表"


def test_a_superseded_row_is_invisible_to_the_latest_knowledge() -> None:
    recs = [{"key": "k", "basis": "日付", "valid_from": "2025-04-01", "valid_to": "",
             "known_from": "2025-01-01", "known_to": "2025-06-01", "known_quality": "実値",
             "priority": "0", "value": "旧", "source": "合成"},
            {"key": "k", "basis": "日付", "valid_from": "2025-04-01", "valid_to": "",
             "known_from": "2025-06-01", "known_to": "", "known_quality": "実値",
             "priority": "0", "value": "新", "source": "合成"}]
    t = A.Table.from_records(recs)
    assert A.resolve(t, "k", {"日付": "2025-07-01"}).value == "新"
    assert A.resolve(t, "k", {"日付": "2025-07-01"}, as_of=date(2025, 5, 1)).value == "旧"
    assert A.resolve(t, "k", {"日付": "2025-07-01"}, as_of=date(2025, 6, 1)).value == "新"


# ---------------------------------------------------------------- 施行日未定の行

def test_a_row_without_valid_from_never_matches(table: A.Table) -> None:
    for on in ("2025-01-01", "2026-09-28", "2030-01-01"):
        r = A.resolve(table, "適用要件_丁", {"資格取得日": on})
        assert r.value != "撤廃"
    assert A.resolve(table, "適用要件_丁", {"資格取得日": "2026-09-28"}).value == "51"
    assert [r.value for r in table.rows if r.valid_from is None] == ["撤廃"]


def test_a_row_without_valid_from_is_not_counted_as_overlap(table: A.Table) -> None:
    assert A.validate(table) == []


# ---------------------------------------------------------------- 対象(selector)

def test_blank_selector_is_a_wildcard(table: A.Table) -> None:
    got = {A.resolve(table, "保険料率_乙", case_of(date(2025, 6, 1), a, b)).value
           for a in AREAS for b in BANDS}
    assert got == {"0.55"}


def test_a_case_that_does_not_carry_the_dimension_misses_the_specific_row(table: A.Table) -> None:
    r = A.resolve(table, "保険料率_甲", {"対象月初日": "2025-06-01"})
    assert not r.ok and r.reason == "収録範囲の外"


def test_adding_a_dimension_later_leaves_the_old_rows_alone(table: A.Table) -> None:
    """列を 1 つ足しても、既存行は空欄のままワイルドカードとして動く。"""
    recs = [{"key": r.key, "basis": r.basis,
             "valid_from": r.valid_from.isoformat() if r.valid_from else "",
             "valid_to": r.valid_to.isoformat() if r.valid_to else "",
             "known_from": r.known_from.isoformat(), "known_to": "",
             "known_quality": r.known_quality, "priority": str(r.priority),
             "value": r.value, "source": r.source, **r.sel, "sel_新しい次元": ""}
            for r in table.rows]
    t = A.Table.from_records(recs)
    assert t.dims == ("sel_地域", "sel_生年月日帯", "sel_新しい次元")
    case = case_of(date(2025, 6, 1), "地域C", BANDS[1])
    case["sel_新しい次元"] = "何か"
    assert A.resolve(t, "保険料率_甲", case).value == "9.70"


# ---------------------------------------------------------------- priority

def test_the_transitional_row_wins_over_the_main_rule(table: A.Table) -> None:
    case_old = case_of(date(2025, 6, 1), "地域A", "1960年度以前")
    case_new = case_of(date(2025, 6, 1), "地域A", "1961年度以降")
    old = A.resolve(table, "継続給付_支給率", case_old)
    new = A.resolve(table, "継続給付_支給率", case_new)
    assert (old.value, old.priority) == ("15", 10)
    assert (new.value, new.priority) == ("10", 0)


def test_the_transitional_row_expires(table: A.Table) -> None:
    case = case_of(date(2030, 4, 1), "地域A", "1960年度以前")
    r = A.resolve(table, "継続給付_支給率", case)
    assert (r.value, r.priority) == ("10", 0)


def test_before_the_revision_both_bands_get_the_old_main_rule(table: A.Table) -> None:
    got = {A.resolve(table, "継続給付_支給率", case_of(date(2025, 3, 1), "地域A", b)).value for b in BANDS}
    assert got == {"15"}


# ---------------------------------------------------------------- validate

def test_validate_is_clean_for_the_clean_table(table: A.Table) -> None:
    assert A.validate(table) == []


def test_validate_lists_every_kind() -> None:
    found = A.validate(A.Table.from_csv(BROKEN))
    assert {f.kind for f in found} == set(A.FINDINGS)
    assert len(found) == 6


@pytest.mark.parametrize("kind,rows", [("期間の逆転", (5,)), ("知識期間の逆転", (6,)),
                                       ("priority が登録外", (9,)), ("基準日の不一致", (7, 8)),
                                       ("有効期間の重なり", (1, 2)), ("期間の穴", (3, 4))])
def test_validate_points_at_the_rows(kind: str, rows: tuple[int, ...]) -> None:
    found = [f for f in A.validate(A.Table.from_csv(BROKEN)) if f.kind == kind]
    assert len(found) == 1 and found[0].rows == rows


def test_validate_does_not_fix_anything() -> None:
    t = A.Table.from_csv(BROKEN)
    before = [(r.valid_from, r.valid_to, r.priority) for r in t.rows]
    A.validate(t)
    assert [(r.valid_from, r.valid_to, r.priority) for r in t.rows] == before


def test_rows_that_differ_in_knowledge_time_do_not_overlap() -> None:
    recs = [{"key": "k", "basis": "日付", "valid_from": "2025-04-01", "valid_to": "",
             "known_from": "2025-01-01", "known_to": "2025-06-01", "known_quality": "実値",
             "priority": "0", "value": "旧", "source": "合成"},
            {"key": "k", "basis": "日付", "valid_from": "2025-04-01", "valid_to": "",
             "known_from": "2025-06-01", "known_to": "", "known_quality": "実値",
             "priority": "0", "value": "新", "source": "合成"}]
    assert A.validate(A.Table.from_records(recs)) == []


def test_rows_that_differ_in_priority_do_not_overlap(table: A.Table) -> None:
    assert not [f for f in A.validate(table) if f.kind == "有効期間の重なり"]


def test_resolve_stops_when_the_basis_is_inconsistent() -> None:
    t = A.Table.from_csv(BROKEN)
    with pytest.raises(A.TableError, match="basis が行ごとに違う"):
        A.resolve(t, "基準日が揺れる表", {"対象月初日": "2025-06-01"})


# ---------------------------------------------------------------- 比較用の引き方

def test_naive_lookup_ignores_the_publication_date(table: A.Table) -> None:
    r = A.naive_lookup(table, "保険料率_甲", date(2026, 3, 1), {"sel_地域": "地域A"})
    assert r.value == "9.70"     # 引く時点が公表前でも同じ行を返す(受け取る口が無い)


def test_naive_lookup_returns_none_outside_the_table(table: A.Table) -> None:
    assert A.naive_lookup(table, "保険料率_乙", date(2024, 1, 1)) is None


def test_naive_lookup_breaks_ties_by_file_order(table: A.Table) -> None:
    """同じ適用開始日に本則と経過措置が並ぶと、後ろの行が採られる(どちらかの帯が必ず誤る)。"""
    r = A.naive_lookup(table, "継続給付_支給率", date(2025, 6, 1))
    assert (r.value, r.priority) == ("15", 10)


# ---------------------------------------------------------------- CLI

def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "asof_table.py"), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def test_cli_resolve_ok() -> None:
    p = run("resolve", str(TABLE), "--key", "保険料率_甲",
            "--case", "対象月初日=2025-06-01", "--case", "sel_地域=地域A")
    assert p.returncode == 0
    out = json.loads(p.stdout)
    assert out["value"] == "9.60" and out["row"] == 13
    assert out["source"] == "合成の料率表 2025 年度版(架空)"
    assert out["valid_from"] == "2025-03-01"


def test_cli_resolve_stops_with_a_reason() -> None:
    p = run("resolve", str(TABLE), "--key", "保険料率_甲",
            "--case", "対象月初日=2026-03-01", "--case", "sel_地域=地域A", "--as-of", "2026-02-05")
    assert p.returncode == 3
    out = json.loads(p.stdout)
    assert out["ok"] is False and out["reason"] == "as_of 時点で未公表"
    assert "value" not in out


def test_cli_validate_ok() -> None:
    p = run("validate", str(TABLE))
    assert p.returncode == 0
    out = json.loads(p.stdout)
    assert out == {"ok": True, "rows": 44, "keys": 4, "findings": []}


def test_cli_validate_lists_findings() -> None:
    p = run("validate", str(BROKEN))
    assert p.returncode == 3
    assert len(json.loads(p.stdout)["findings"]) == 6


def test_cli_rejects_a_bad_case_argument() -> None:
    p = run("resolve", str(TABLE), "--key", "保険料率_甲", "--case", "対象月初日")
    assert p.returncode == 2


def test_cli_rejects_a_missing_file() -> None:
    p = run("validate", str(FX / "無い表.csv"))
    assert p.returncode == 2


# ---------------------------------------------------------------- 測定(記事の数値)

def measure_main(table: A.Table) -> dict:
    """30 か月 × 12 地域 × 2 帯 × 3 rule の引き当てを、2 つの引き方で流して数える。"""
    fold = {"保険料率_甲": {"sel_地域": "x"}}      # 地域は key 側に畳めていた次元
    total = mismatch = naive_value_but_undetermined = stopped = 0
    by_cause = {"基準日": 0, "経過措置": 0, "残差": 0}
    for month in MONTHS:
        for area in AREAS:
            for band in BANDS:
                case = case_of(month, area, band)
                for key in ("保険料率_甲", "保険料率_乙", "継続給付_支給率"):
                    total += 1
                    good = A.resolve(table, key, case)
                    f = {"sel_地域": area} if key in fold else None
                    naive_row = A.naive_lookup(table, key, month, f)
                    a = naive_row.value if naive_row else None
                    b = good.value if good.ok else None
                    if not good.ok:
                        stopped += 1
                    if a == b:
                        continue
                    mismatch += 1
                    if b is None:
                        naive_value_but_undetermined += 1
                    if key == "保険料率_乙":
                        by_cause["基準日"] += 1
                    elif key == "継続給付_支給率":
                        by_cause["経過措置"] += 1
                    else:
                        by_cause["残差"] += 1
    return {"total": total, "mismatch": mismatch, "stopped": stopped,
            "naive_value_but_undetermined": naive_value_but_undetermined,
            "silently_different_value": mismatch - naive_value_but_undetermined,
            "by_cause": by_cause}


def measure_knowledge(table: A.Table) -> dict:
    """同じ key・同じ対象月初日のまま、引く時点(as_of)だけを改定の公表前後に置く。"""
    case_month, published = date(2026, 3, 1), date(2026, 2, 10)
    total = naive_same = tool_stopped = tool_value = 0
    naive_values, tool_values = set(), set()
    for area in AREAS:
        case = case_of(case_month, area, BANDS[1])
        for as_of in (date(2026, 2, 5), date(2026, 2, 20)):
            total += 1
            naive_row = A.naive_lookup(table, "保険料率_甲", case_month, {"sel_地域": area})
            naive_values.add((area, naive_row.value))
            r = A.resolve(table, "保険料率_甲", case, as_of=as_of)
            if r.ok:
                tool_value += 1
                tool_values.add((area, r.value))
            else:
                tool_stopped += 1
    naive_same = len(naive_values)
    return {"total": total, "published": published.isoformat(), "naive_distinct": naive_same,
            "tool_stopped": tool_stopped, "tool_value": tool_value}


def test_measure_main(table: A.Table, capsys: pytest.CaptureFixture) -> None:
    m = measure_main(table)
    assert m["total"] == 2160
    assert m["mismatch"] == 252
    assert m["by_cause"] == {"基準日": 72, "経過措置": 180, "残差": 0}
    assert m["silently_different_value"] == 228
    assert m["naive_value_but_undetermined"] == 24
    assert m["stopped"] == 144
    with capsys.disabled():
        print(f"\n[measure] 引き当て {m['total']} 件 / 答えが違った {m['mismatch']} 件 "
              f"(基準日 {m['by_cause']['基準日']} / 経過措置 {m['by_cause']['経過措置']} / "
              f"残差 {m['by_cause']['残差']})")
        print(f"[measure] うち 適用開始日 1 軸が黙って別の値を返した {m['silently_different_value']} 件、"
              f"値を返したが正しくは決まらない {m['naive_value_but_undetermined']} 件")
        print(f"[measure] この部品が理由コードで止めた {m['stopped']} 件(値を返した誤りは 0 件)")


def test_measure_knowledge(table: A.Table, capsys: pytest.CaptureFixture) -> None:
    m = measure_knowledge(table)
    assert m["total"] == 24
    assert m["naive_distinct"] == 12
    assert m["tool_stopped"] == 12
    assert m["tool_value"] == 12
    with capsys.disabled():
        print(f"[measure] 引く時点だけを動かす {m['total']} 件: "
              f"適用開始日 1 軸は as_of を受け取る口が無く {m['naive_distinct']} 通りのまま、"
              f"この部品は公表前の {m['tool_stopped']} 件を『as_of 時点で未公表』で止め、"
              f"公表後の {m['tool_value']} 件だけ値を返した")


def test_the_measurement_is_deterministic(table: A.Table) -> None:
    assert measure_main(table) == measure_main(A.Table.from_csv(TABLE))
    assert measure_knowledge(table) == measure_knowledge(A.Table.from_csv(TABLE))


def test_fixtures_are_reproducible(tmp_path: Path) -> None:
    """fixture は生成器から決定論的に出る(手で直した行が混ざっていない)。"""
    got = MF.rows_clean()
    assert len(got) == 44
    import csv as _csv
    with TABLE.open(encoding="utf-8-sig", newline="") as f:
        on_disk = list(_csv.DictReader(f))
    assert on_disk == got
    assert len(MF.rows_broken()) == 9
