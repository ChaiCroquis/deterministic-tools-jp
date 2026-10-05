"""intake_triage の検査。合成データだけを使う(人・金額・取込仕様はすべて架空)。

test_measure_* が記事に載せた数値の出どころで、固定の fixture から決定論的に出る値を
`assert 変数 == 値` で固定している(値が変われば記事も変える前提)。
"""
from __future__ import annotations

import csv
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
import intake_triage as T  # noqa: E402

sys.path.insert(0, str(FIX))
import make_fixtures  # noqa: E402

SPEC = T.Spec.load(FIX / "shiyou.csv")
KEY = "社員番号"


def rows_of(name: str) -> list:
    return T.load_rows(FIX / name)


def spec_of(name: str) -> T.Spec:
    return T.Spec.load(FIX / name)


def one_row(**over) -> dict:
    row = {"社員番号": "000101", "氏名": "山田 花子", "部署コード": "10",
           "支給年月日": "20260925", "支給合計": "312000", "控除合計": "-48250",
           "差引支給額": "263750", "備考": ""}
    row.update(over)
    return row


def judge_one(spec: T.Spec, **over) -> T.Row:
    t = T.triage([one_row(**over)], spec, KEY)
    return t.results[0]


# ---------------------------------------------------------------- 値域の宣言

def test_domain_parse_covers_every_kind() -> None:
    assert T.Domain.parse("制限なし").kind == T.ANY
    assert T.Domain.parse("集合: 10|20|30").values == ("10", "20", "30")
    d = T.Domain.parse("範囲: -100..100")
    assert (d.low, d.high) == (T.Decimal("-100"), T.Decimal("100"))
    assert T.Domain.parse("長さ: 6").length == 6
    assert T.Domain.parse("長さ上限: 40").length == 40
    assert T.Domain.parse("形: YYYYMMDD").form == "YYYYMMDD"


def test_domain_accepts_a_full_width_colon() -> None:
    assert T.Domain.parse("長さ: 6") == T.Domain.parse("長さ: 6")


def test_blank_domain_is_not_unrestricted() -> None:
    with pytest.raises(T.SpecError):
        T.Domain.parse("")


@pytest.mark.parametrize("text", ["集合 10|20", "知らない種類: 1", "集合: ", "範囲: 0-100",
                                  "範囲: あ..100", "範囲: 100..0", "長さ: 0", "長さ: 六",
                                  "形: YYYY年MM月DD日"])
def test_unreadable_domain_is_a_spec_error(text: str) -> None:
    with pytest.raises(T.SpecError):
        T.Domain.parse(text)


def test_unknown_type_name_is_a_spec_error() -> None:
    with pytest.raises(T.SpecError):
        T.Spec.of([{"column": "列", "type": "数値", "domain": "制限なし", "required": "○"}])


@pytest.mark.parametrize("type_name,domain", [("日付", "範囲: 0..100"), ("金額", "長さ: 6"),
                                              ("文字列", "範囲: 0..100"), ("日付", "制限なし"),
                                              ("コード", "範囲: 0..100")])
def test_domain_kind_must_fit_the_type(type_name: str, domain: str) -> None:
    with pytest.raises(T.SpecError):
        T.Spec.of([{"column": "列", "type": type_name, "domain": domain, "required": "○"}])


def test_spec_csv_must_have_all_six_fields() -> None:
    bad = FIX / "_tmp_spec.csv"
    bad.write_text("column,type,domain\n列,文字列,制限なし\n", encoding="utf-8")
    try:
        with pytest.raises(T.SpecError):
            T.Spec.load(bad)
    finally:
        bad.unlink()


def test_spec_can_be_json() -> None:
    p = FIX / "_tmp_spec.json"
    p.write_text(json.dumps({"columns": [{"column": "列", "type": "文字列",
                                          "domain": "制限なし", "required": "○"}]},
                            ensure_ascii=False), encoding="utf-8")
    try:
        assert T.Spec.load(p).names == ("列",)
    finally:
        p.unlink()


def test_empty_spec_is_a_spec_error() -> None:
    with pytest.raises(T.SpecError):
        T.Spec.of([])


def test_the_key_column_name_has_no_default() -> None:
    with pytest.raises(T.SpecError):
        T.Triage([one_row()], SPEC, "")


# ---------------------------------------------------------------- 列ごとの 3 値

@pytest.mark.parametrize("over,violation", [
    ({"支給合計": "３１２０００"}, "型と違う"),
    ({"差引支給額": "263,750"}, "型と違う"),
    ({"社員番号": "00010A"}, "型と違う"),
    ({"支給年月日": "令和8年9月25日"}, "型と違う"),
    ({"控除合計": "48250"}, "範囲の外"),
    ({"支給合計": "99999999"}, "範囲の外"),
    ({"社員番号": "101"}, "長さが違う"),
    ({"氏名": "長" * 41}, "桁あふれ"),
    ({"部署コード": "40"}, "集合の外"),
    ({"氏名": ""}, "必要な値が空"),
    ({"支給年月日": "2026-09-25"}, "形が違う"),
    ({"支給年月日": "20260931"}, "形が違う"),
])
def test_each_violation_name_is_reachable(over: dict, violation: str) -> None:
    row = judge_one(SPEC, **over)
    assert [v.violation for v in row.violations] == [violation]
    assert violation in T.VIOLATIONS


def test_the_seven_violation_names_are_all_the_names() -> None:
    assert len(T.VIOLATIONS) == 7
    reachable = set()
    for over in ({"支給合計": "３１２０００"}, {"控除合計": "48250"}, {"社員番号": "101"},
                 {"氏名": "長" * 41}, {"部署コード": "40"}, {"氏名": ""},
                 {"支給年月日": "2026-09-25"}):
        reachable |= {v.violation for v in judge_one(SPEC, **over).violations}
    assert reachable == set(T.VIOLATIONS)


def test_a_blank_is_a_violation_only_where_it_was_declared() -> None:
    assert judge_one(SPEC, 備考="").judgment == T.PASSES          # 備考 は空を許す列
    assert judge_one(SPEC, 氏名="").judgment == T.JUDGMENT


def test_the_line_moves_with_the_declaration_not_with_the_value() -> None:
    """同じ値・同じ違反でも、覆うと宣言された直し方が在れば 2 本目、無ければ 3 本目。"""
    with_repair = judge_one(SPEC, 控除合計="48250")
    without = judge_one(spec_of("shiyou_fugou_nashi.csv"), 控除合計="48250")
    assert with_repair.judgment == T.REPAIRABLE
    assert without.judgment == T.JUDGMENT
    assert with_repair.violations[0].violation == without.violations[0].violation == "範囲の外"
    assert with_repair.violations[0].value == without.violations[0].value == "48250"


def test_a_declared_repair_that_does_not_cover_the_violation_falls_to_judgment() -> None:
    """支給合計には直し方が宣言されているが、覆うのは『型と違う』だけ。"""
    assert judge_one(SPEC, 支給合計="３１２０００").judgment == T.REPAIRABLE
    row = judge_one(SPEC, 支給合計="99999999")
    assert row.judgment == T.JUDGMENT
    assert row.violations[0].violation == "範囲の外"
    assert row.violations[0].repair == ""      # 適用すべき直し方は返らない


def test_no_repair_covers_an_overflow() -> None:
    covered = {v for names in T.REPAIRS.values() for v in names}
    assert "桁あふれ" not in covered


def test_every_repair_covers_only_names_that_exist() -> None:
    for name, covers in T.REPAIRS.items():
        assert covers, f"{name} が覆う違反が空"
        assert set(covers) <= set(T.VIOLATIONS)


def test_a_row_takes_the_worst_of_its_columns() -> None:
    row = judge_one(SPEC, 控除合計="48250", 部署コード="40")
    assert {v.judgment for v in row.violations} == {T.REPAIRABLE, T.JUDGMENT}
    assert row.judgment == T.JUDGMENT
    assert judge_one(SPEC, 控除合計="48250", 支給合計="３１２０００").judgment == T.REPAIRABLE


def test_the_detail_keeps_the_value_as_it_is() -> None:
    v = judge_one(SPEC, 差引支給額="263,750").violations[0]
    assert v.value == "263,750"                      # 書き換えた値は返さない
    assert v.repair == "桁区切りのカンマを外す"       # 返るのは名前だけ
    assert "宣言" in v.as_dict() and v.as_dict()["現在の値"] == "263,750"


def test_the_rows_that_went_in_are_not_touched() -> None:
    given = [one_row(控除合計="48250"), one_row(社員番号="000102", 部署コード="40")]
    before = json.dumps(given, ensure_ascii=False, sort_keys=True)
    t = T.triage(given, SPEC, KEY)
    assert t.report.ok
    assert json.dumps(given, ensure_ascii=False, sort_keys=True) == before


# ---------------------------------------------------------------- 止まる理由コード

@pytest.mark.parametrize("spec_file,reason", [
    ("shiyou_kata_kuuhaku.csv", "型の名前が空欄"),
    ("shiyou_iki_kuuhaku.csv", "値域の宣言が空欄"),
    ("shiyou_juufuku.csv", "同じ column が仕様表に 2 行"),
    ("shiyou_michi_repair.csv", "repair の名前が辞書に無い"),
    ("shiyou_shikibetsu_nashi.csv", "必須列が仕様表に無い"),
    ("shiyou_hissu_nashi.csv", "必須列が仕様表に無い"),
])
def test_the_spec_stage_stops_before_any_row_is_judged(spec_file: str, reason: str) -> None:
    t = T.triage(rows_of("gyou.csv"), spec_of(spec_file), KEY)
    r = t.report
    assert not r.ok and r.stage == T.SPEC and reason in r.reasons()
    assert sum(r.counts.values()) == 0
    with pytest.raises(T.TriageError):
        t.results


@pytest.mark.parametrize("rows_file,reason", [
    ("gyou_yobun.csv", "仕様表に無い列が行に在る"),
    ("gyou_juufuku.csv", "行の識別子が重複"),
])
def test_the_match_stage_stops_before_any_row_is_judged(rows_file: str, reason: str) -> None:
    t = T.triage(rows_of(rows_file), SPEC, KEY)
    r = t.report
    assert not r.ok and r.stage == T.MATCH and reason in r.reasons()
    assert sum(r.counts.values()) == 0


def test_asking_for_the_result_before_the_three_stages_stops() -> None:
    t = T.Triage(rows_of("gyou.csv"), SPEC, KEY)
    with pytest.raises(T.TriageError) as e:
        t.report
    assert e.value.reason == "判定前に出力を要求した"
    with pytest.raises(T.TriageError):
        t.handoff()


def test_the_eight_reason_codes_are_all_the_codes() -> None:
    assert len(T.REASONS) == 8
    seen = set()
    for f in ("shiyou_kata_kuuhaku.csv", "shiyou_iki_kuuhaku.csv", "shiyou_juufuku.csv",
              "shiyou_michi_repair.csv", "shiyou_shikibetsu_nashi.csv"):
        seen |= set(T.triage(rows_of("gyou.csv"), spec_of(f), KEY).report.reasons())
    for f in ("gyou_yobun.csv", "gyou_juufuku.csv"):
        seen |= set(T.triage(rows_of(f), SPEC, KEY).report.reasons())
    t = T.Triage(rows_of("gyou.csv"), SPEC, KEY)
    try:
        t.report
    except T.TriageError as e:
        seen.add(e.reason)
    assert seen == set(T.REASONS)


def test_a_blank_key_in_a_row_is_reported_as_a_duplicate_only_when_it_repeats() -> None:
    once = T.triage([one_row(社員番号=""), one_row(社員番号="000102")], SPEC, KEY)
    assert once.report.ok                     # 空欄 1 行は『長さが違う』で 3 本目に落ちるだけ
    twice = T.triage([one_row(社員番号=""), one_row(社員番号="")], SPEC, KEY)
    assert "行の識別子が重複" in twice.report.reasons()


# ---------------------------------------------------------------- 持たせていない経路

def test_no_partial_handoff_while_anything_is_left() -> None:
    t = T.triage(rows_of("gyou.csv"), SPEC, KEY)
    with pytest.raises(T.TriageError) as e:
        t.handoff()
    assert e.value.reason == T.JUDGMENT
    only_repairable = [r for r in rows_of("gyou.csv")
                       if r[KEY] in ("000101", "000109")]
    t2 = T.triage(only_repairable, SPEC, KEY)
    with pytest.raises(T.TriageError) as e2:
        t2.handoff()
    assert e2.value.reason == T.REPAIRABLE       # 直し方待ちの行も渡さない


def test_handoff_returns_rows_only_when_every_row_passes() -> None:
    t = T.triage(rows_of("gyou_tooru.csv"), SPEC, KEY)
    assert len(t.handoff()) == 6
    assert t.handoff()[0][KEY] == "000101"


def test_the_source_has_no_path_that_rewrites_a_value() -> None:
    src = (ROOT / "intake_triage.py").read_text(encoding="utf-8")
    for word in ("def repair(", "def fix(", ".replace(value", "row[column.column] ="):
        assert word not in src, word


def test_nothing_is_written_while_triaging(tmp_path: Path) -> None:
    before = sorted(p.name for p in FIX.iterdir())
    T.triage(rows_of("gyou.csv"), SPEC, KEY).violations()
    assert sorted(p.name for p in FIX.iterdir()) == before
    assert list(tmp_path.iterdir()) == []


def test_there_is_no_threshold_or_preference_argument() -> None:
    import inspect
    for fn in (T.triage, T.Triage.__init__, T.Triage.judge_cell, T.Triage.handoff):
        names = set(inspect.signature(fn).parameters)
        assert not names & {"tolerance", "threshold", "prefer", "priority", "auto",
                            "first_match", "fuzzy", "repair"}
    out = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "intake_triage.py"),
                          "triage", "--help"], capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    for word in ("--tolerance", "--threshold", "--prefer", "--auto", "--repair", "--fix"):
        assert word not in out.stdout


def test_the_share_never_comes_without_its_denominator() -> None:
    s = T.triage(rows_of("gyou.csv"), SPEC, KEY).share()
    assert "分母に含めたもの" in s and "判定した行" in s and "判定しなかった行" in s
    assert set(T.CLASSES) <= set(s)
    src = (ROOT / "intake_triage.py").read_text(encoding="utf-8")
    assert "def rate(" not in src          # 率だけを返す口は持たない


def test_the_component_writes_no_message_to_anyone() -> None:
    src = (ROOT / "intake_triage.py").read_text(encoding="utf-8")
    for word in ("ご確認", "お世話に", "下記のとおり", "宛先", "お問い合わせ", "拝啓"):
        assert word not in src, word


def test_the_core_has_no_vocabulary_of_any_field() -> None:
    src = (ROOT / "intake_triage.py").read_text(encoding="utf-8")
    for word in ("給与", "社員", "支給", "控除", "賃金", "部署", "氏名", "勤怠", "仕訳",
                 "受注", "請求"):
        assert word not in src, word


# ---------------------------------------------------------------- CLI と fixture

def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "intake_triage.py"), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def test_cli_exit_codes() -> None:
    mixed = run_cli("triage", str(FIX / "gyou.csv"), "--spec", str(FIX / "shiyou.csv"),
                    "--key", KEY)
    assert mixed.returncode == 3
    assert json.loads(mixed.stdout)["件数"][T.JUDGMENT] == 6
    clean = run_cli("triage", str(FIX / "gyou_tooru.csv"), "--spec", str(FIX / "shiyou.csv"),
                    "--key", KEY)
    assert clean.returncode == 0
    stopped = run_cli("triage", str(FIX / "gyou.csv"), "--spec",
                      str(FIX / "shiyou_juufuku.csv"), "--key", KEY)
    assert stopped.returncode == 3 and not json.loads(stopped.stdout)["ok"]
    bad = run_cli("triage", str(FIX / "gyou.csv"), "--spec", str(FIX / "shiyou.csv"),
                  "--key", "在りもしない列")
    assert bad.returncode == 3      # 識別子の列が仕様表に無い = 理由コード
    missing = run_cli("triage", str(FIX / "無い.csv"), "--spec", str(FIX / "shiyou.csv"),
                      "--key", KEY)
    assert missing.returncode == 2


def test_cli_report_csv_lists_one_line_per_violation() -> None:
    r = run_cli("report", str(FIX / "gyou.csv"), "--spec", str(FIX / "shiyou.csv"),
                "--key", KEY, "--format", "csv")
    assert r.returncode == 3
    rows = list(csv.DictReader(io.StringIO(r.stdout)))
    assert len(rows) == 12
    assert rows[0]["識別子"] == "101" and rows[0]["違反"] == "長さが違う"
    assert all(row["列"] and row["違反"] and row["宣言"] for row in rows)
    assert [row["現在の値"] for row in rows].count("") == 1      # 空欄の違反 1 件だけ


def test_cli_init_writes_a_template_and_never_overwrites() -> None:
    p = FIX / "_tmp_init.csv"
    try:
        assert run_cli("init", str(p)).returncode == 0
        head = p.read_text(encoding="utf-8").splitlines()[0]
        assert head.split(",") == list(T.SPEC_COLUMNS)
        again = run_cli("init", str(p))
        assert again.returncode == 2
    finally:
        p.unlink(missing_ok=True)


def test_the_fixtures_on_disk_are_what_the_generator_makes() -> None:
    before = {p.name: p.read_bytes() for p in sorted(FIX.glob("*.csv"))}
    counts = make_fixtures.build()
    after = {p.name: p.read_bytes() for p in sorted(FIX.glob("*.csv"))}
    assert before == after
    assert counts["gyou.csv"] == 18 and counts["shiyou.csv"] == 8


def test_the_fixtures_are_synthetic_only() -> None:
    src = (FIX / "make_fixtures.py").read_text(encoding="utf-8")
    assert "架空" in src
    assert "C:" not in src and "D:" not in src


# ---------------------------------------------------------------- 測定(記事の数値)

def measure_triage() -> dict:
    t = T.triage(rows_of("gyou.csv"), SPEC, KEY)
    counts = dict(t.report.counts)
    by_violation: dict = {}
    for v in t.violations():
        by_violation.setdefault(v.violation, {T.REPAIRABLE: 0, T.JUDGMENT: 0})
        by_violation[v.violation][v.judgment] += 1
    return {"行": t.report.rows, "件数": counts, "違反": len(t.violations()),
            "違反なしの行": counts[T.PASSES], "内訳": by_violation}


def test_measure_triage(capsys: pytest.CaptureFixture) -> None:
    m = measure_triage()
    assert m["行"] == 18
    assert m["件数"] == {T.PASSES: 6, T.REPAIRABLE: 6, T.JUDGMENT: 6}
    assert m["違反"] == 12
    assert m["内訳"] == {
        "長さが違う": {T.REPAIRABLE: 1, T.JUDGMENT: 0},
        "型と違う": {T.REPAIRABLE: 2, T.JUDGMENT: 2},
        "範囲の外": {T.REPAIRABLE: 1, T.JUDGMENT: 1},
        "形が違う": {T.REPAIRABLE: 2, T.JUDGMENT: 0},
        "集合の外": {T.REPAIRABLE: 0, T.JUDGMENT: 1},
        "必要な値が空": {T.REPAIRABLE: 0, T.JUDGMENT: 1},
        "桁あふれ": {T.REPAIRABLE: 0, T.JUDGMENT: 1},
    }
    with capsys.disabled():
        print(f"\n[measure] 合成の行 {m['行']} 行を仕分ける: そのまま通る {m['件数'][T.PASSES]} /"
              f" 宣言された直し方で通る {m['件数'][T.REPAIRABLE]} /"
              f" 人が決めるしかない {m['件数'][T.JUDGMENT]}(違反は {m['違反']} 件)")
        for name, by in m["内訳"].items():
            print(f"[measure] 違反『{name}』: 2 本目 {by[T.REPAIRABLE]} 件 /"
                  f" 3 本目 {by[T.JUDGMENT]} 件")


def measure_declaration_moves_the_line() -> dict:
    rows = rows_of("gyou.csv")
    before = T.triage(rows, SPEC, KEY).report.counts
    after = T.triage(rows, spec_of("shiyou_fugou_nashi.csv"), KEY).report.counts
    diff = [c.column for c in SPEC.columns
            if c.repair != (spec_of("shiyou_fugou_nashi.csv").by_name(c.column).repair)]
    return {"前": dict(before), "後": dict(after), "差のある列": diff}


def test_measure_declaration_moves_the_line(capsys: pytest.CaptureFixture) -> None:
    m = measure_declaration_moves_the_line()
    assert len(m["差のある列"]) == 1
    assert m["前"] == {T.PASSES: 6, T.REPAIRABLE: 6, T.JUDGMENT: 6}
    assert m["後"] == {T.PASSES: 6, T.REPAIRABLE: 5, T.JUDGMENT: 7}
    with capsys.disabled():
        print(f"\n[measure] 仕様表の直し方を 1 欄だけ空にする({' / '.join(m['差のある列'])}):"
              f" {m['前'][T.REPAIRABLE]} / {m['前'][T.JUDGMENT]} →"
              f" {m['後'][T.REPAIRABLE]} / {m['後'][T.JUDGMENT]}"
              f"(そのまま通る行は {m['後'][T.PASSES]} のまま動かない)")


def test_measure_share(capsys: pytest.CaptureFixture) -> None:
    s = T.triage(rows_of("gyou.csv"), SPEC, KEY).share()
    assert s["行"] == 18 and s["判定した行"] == 18 and s["判定しなかった行"] == 0
    assert s["そのまま通る割合_判定した行のみ"] == "0.3333"
    assert s["そのまま通る割合_全ての行"] == "0.3333"
    stopped = T.triage(rows_of("gyou.csv"), spec_of("shiyou_juufuku.csv"), KEY).share()
    assert stopped["判定した行"] == 0 and stopped["判定しなかった行"] == 18
    assert stopped["そのまま通る割合_判定した行のみ"] == "分母が 0"
    with capsys.disabled():
        print(f"\n[measure] そのまま通る割合 {s['そのまま通る割合_判定した行のみ']}"
              f"({s['分母に含めたもの']})")
        print(f"[measure] 仕様表で止まった時: 判定した行 {stopped['判定した行']} /"
              f" 判定しなかった行 {stopped['判定しなかった行']} →"
              f" 割合は {stopped['そのまま通る割合_判定した行のみ']}")


def test_measure_the_calendar_day_lands_on_the_second_line(capsys: pytest.CaptureFixture) -> None:
    """宣言が覆うと言った違反は、直せない値でも 2 本目に入る(宣言の正しさは判定しない)。"""
    row = judge_one(SPEC, 支給年月日="20260931")
    assert row.judgment == T.REPAIRABLE
    assert row.violations[0].repair == "区切りを外して 8 桁に"
    with capsys.disabled():
        print(f"\n[measure] 暦に無い日 1 件は、形の直し方が宣言されているので 2 本目"
              f"({row.violations[0].repair})。部品は宣言の正しさを判定しない")


def test_measure_stops(capsys: pytest.CaptureFixture) -> None:
    out = {}
    for f in ("shiyou_kata_kuuhaku.csv", "shiyou_iki_kuuhaku.csv", "shiyou_juufuku.csv",
              "shiyou_michi_repair.csv", "shiyou_shikibetsu_nashi.csv",
              "shiyou_hissu_nashi.csv"):
        r = T.triage(rows_of("gyou.csv"), spec_of(f), KEY).report
        out[f] = (r.stage, r.reasons()[0], sum(r.counts.values()))
    for f in ("gyou_yobun.csv", "gyou_juufuku.csv"):
        r = T.triage(rows_of(f), SPEC, KEY).report
        out[f] = (r.stage, r.reasons()[0], sum(r.counts.values()))
    assert len(out) == 8
    assert all(judged == 0 for _, _, judged in out.values())
    with capsys.disabled():
        print()
        for name, (stage, reason, judged) in out.items():
            print(f"[measure] {name}: {stage}で止まった({reason})。判定した行 {judged}")


def test_the_declaration_ledger_names_the_spec_file_and_its_hash() -> None:
    import hashlib
    t = T.triage(rows_of("gyou.csv"), SPEC, KEY)
    led = t.declared()
    assert led["仕様表"] == "shiyou.csv" and led["識別子"] == KEY
    want = hashlib.sha256((FIX / "shiyou.csv").read_bytes()).hexdigest()
    assert led["sha256"] == want
    covers = {c["column"]: c["covers"] for c in led["列"]}
    assert covers["控除合計"] == ["範囲の外"] and covers["氏名"] == []
    assert len(led["列"]) == 8


def test_two_spec_files_that_differ_in_one_cell_have_different_hashes() -> None:
    a, b = SPEC, spec_of("shiyou_fugou_nashi.csv")
    assert a.sha256 != b.sha256
    assert [c.column for c in a.columns] == [c.column for c in b.columns]
    assert [(c.type_name, c.domain_text) for c in a.columns] == \
           [(c.type_name, c.domain_text) for c in b.columns]
    assert sum(1 for x, y in zip(a.columns, b.columns) if x.repair != y.repair) == 1
