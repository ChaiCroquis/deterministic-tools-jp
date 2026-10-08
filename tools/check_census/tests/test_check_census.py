"""check_census のテスト。fixture は全て合成データ(プロジェクト名・runner・出典は架空)。

test_measure_* が記事に載せた数値の出どころで、固定の合成プロジェクトから決定論的に出る値を assert で
固定している(値が変われば記事も変える前提)。宣言表は走っている処理系を argv[0] に入れて作り直すので、
PATH 上の python に依存しない。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FIX))
import check_census as C  # noqa: E402
import make_fixtures as M  # noqa: E402

# 図 2 の行(検証の在り方)。宣言表の 1 行がちょうど 1 つの在り方に入る
ARIKATA = {
    "道具A_通る": "在ると数えた",
    "道具B_落ちる": "在ると数えた",
    "道具H_外向き不許可": "在ると数えた",
    "道具J_path無し": "在ると数えた",
    "道具K_外向き許可": "在ると数えた",
    "道具D_テスト無し": "無いと数えた",
    "道具E_在るか不明": "在るか不明",
    "道具G_試験ゼロ": "試験が 1 件も無い",
    "道具F_runner未宣言": "runner 未宣言",
    "道具C_時間超過": "timeout 超過",
}
ARIKATA_ROWS = ("在ると数えた", "無いと数えた", "在るか不明",
                "試験が 1 件も無い", "runner 未宣言",
                "timeout 超過", "2 回で変わる")
GRID_COLS = ("宣言では在る", C.PASSED, C.FAILED, C.NOT_RUN, C.NO_TESTS)


@pytest.fixture(scope="session")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """合成プロジェクトと宣言表を、走っている処理系を指す形で作り直す。"""
    return M.build(tmp_path_factory.mktemp("census"), sys.executable)


@pytest.fixture(scope="session")
def taicho(built: Path) -> C.Census:
    return C.census(C.Declaration.load(built / "sengen.csv"))


def tree_fingerprint(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(root)).replace("\\", "/").encode("utf-8"))
            h.update(p.read_bytes())
    return h.hexdigest()


# ---------------------------------------------------------------- 入り口

def test_committed_fixture_table_loads(built: Path) -> None:
    """repo に入れてある宣言表(argv[0] が PATH 上の python)も宣言として読める。"""
    decl = C.Declaration.load(FIX / "sengen.csv")
    assert decl.pending == ()
    assert len(decl.rows) == 10
    assert [r.name for r in decl.rows] == [r.name for r in C.Declaration.load(built / "sengen.csv").rows]


def test_declaration_keeps_the_order_of_the_table(built: Path, taicho: C.Census) -> None:
    """台帳の行の順は宣言表の順(並べ替えない)。"""
    declared = [r.name for r in C.Declaration.load(built / "sengen.csv").rows]
    assert [r["name"] for r in taicho.table()] == declared
    assert sorted(declared) == sorted(ARIKATA)


def test_unreadable_table_is_not_a_reason_code(built: Path) -> None:
    with pytest.raises(C.DeclError):
        C.Declaration.load(built / "sengen_yomenai.csv")
    with pytest.raises(C.DeclError):
        C.Declaration.load(built / "sengen_nai.csv")


# ---------------------------------------------------------------- 4 値

def test_measure_verdicts(taicho: C.Census, capsys: pytest.CaptureFixture) -> None:
    counts, d, dec = taicho.counts(), taicho.denominator(), taicho.declared_counts()
    assert dec == {"在る": 8, "無い": 1, "不明": 1}
    assert counts == {"通った": 3, "落ちた": 3, "走らなかった": 3, "テストが無い": 1}
    assert d == {"宣言の行数": 10, "走らせた数": 6, "走らなかった数": 3, "テストが無い数": 1}
    assert sum(counts.values()) == d["宣言の行数"]
    with capsys.disabled():
        print(f"\n[measure] 宣言表 {d['宣言の行数']} 行(テストが在る {dec['在る']} / 無い {dec['無い']}"
              f" / 不明 {dec['不明']})を走らせる")
        print(f"[measure] 4 値: 通った {counts['通った']} / 落ちた {counts['落ちた']}"
              f" / 走らなかった {counts['走らなかった']} / テストが無い {counts['テストが無い']}")


def test_measure_rate_needs_two_denominators(taicho: C.Census, capsys: pytest.CaptureFixture) -> None:
    r = taicho.rate()
    assert r["合格率_走らせた行のみ"] == "0.5000"
    assert r["合格率_宣言の行すべて"] == "0.3000"
    assert r["在ると数えた数は結果を 1 件も言わない"] == "宣言では在る 8 / 走らせて通った 3"
    with capsys.disabled():
        print(f"[measure] 合格率: 走らせた行のみ(分母 {taicho.denominator()['走らせた数']})= "
              f"{r['合格率_走らせた行のみ']} / 宣言の行すべて(分母 "
              f"{taicho.denominator()['宣言の行数']})= {r['合格率_宣言の行すべて']}")
        print(f"[measure] 在ると数えた数は結果を言わない: {r['在ると数えた数は結果を 1 件も言わない']}")


def test_measure_arikata_grid(taicho: C.Census, capsys: pytest.CaptureFixture) -> None:
    """図 2 の各セルの件数(検証の在り方 × 宣言では在る + 4 値)。"""
    grid = {row: {col: 0 for col in GRID_COLS} for row in ARIKATA_ROWS}
    for r in taicho.results:
        row = grid[ARIKATA[r.name]]
        row[r.verdict] += 1
        if r.declared == "在る":
            row["宣言では在る"] += 1
    assert grid["在ると数えた"] == {"宣言では在る": 5, "通った": 2, "落ちた": 2,
                                                  "走らなかった": 1, "テストが無い": 0}
    assert grid["無いと数えた"] == {"宣言では在る": 0, "通った": 0, "落ちた": 0,
                                          "走らなかった": 0, "テストが無い": 1}
    assert grid["在るか不明"] == {"宣言では在る": 0, "通った": 1, "落ちた": 0,
                                    "走らなかった": 0, "テストが無い": 0}
    assert grid["試験が 1 件も無い"] == {"宣言では在る": 1, "通った": 0, "落ちた": 1,
                                             "走らなかった": 0, "テストが無い": 0}
    assert grid["runner 未宣言"] == {"宣言では在る": 1, "通った": 0, "落ちた": 0,
                                                    "走らなかった": 1, "テストが無い": 0}
    assert grid["timeout 超過"] == {"宣言では在る": 1, "通った": 0, "落ちた": 0,
                                           "走らなかった": 1, "テストが無い": 0}
    assert grid["2 回で変わる"] == {c: 0 for c in GRID_COLS}
    with capsys.disabled():
        for row in ARIKATA_ROWS:
            got = {k: v for k, v in grid[row].items() if v}
            print(f"[measure] 在り方『{row}』: {got or '本体の台帳には入れない(verify で観測)'}")


def test_measure_not_run_reasons(taicho: C.Census, built: Path,
                                 capsys: pytest.CaptureFixture) -> None:
    got = {r.reason for r in taicho.results if r.verdict == C.NOT_RUN}
    assert got == {"timeout", "runner が無い", "path が無い"}
    # 4 つめの理由コードは別の宣言表(path 欄が空)で通す
    other = C.census(C.Declaration.load(built / "sengen_retsu_kuuhaku.csv"))
    assert [(r.verdict, r.reason) for r in other.results] == [(C.NOT_RUN, "宣言の列が空欄")]
    assert set(C.NOT_RUN_REASONS) == got | {"宣言の列が空欄"}
    with capsys.disabled():
        print(f"[measure] 走らなかった 3 件の理由コード: "
              f"{' / '.join(sorted(got))}(本体の宣言表)")
        print(f"[measure] 4 つめの理由コード『宣言の列が空欄』は path 欄を空にした宣言表で通した"
              f" = 理由コード {len(C.NOT_RUN_REASONS)} 個すべてに道がある")


def test_measure_failed_rows_keep_their_exit_code(taicho: C.Census,
                                                  capsys: pytest.CaptureFixture) -> None:
    failed = {r.name: r.exit_code for r in taicho.results if r.verdict == C.FAILED}
    assert failed == {"道具B_落ちる": 1, "道具G_試験ゼロ": 5, "道具H_外向き不許可": 1}
    with capsys.disabled():
        print(f"[measure] 落ちた 3 件の終了コード: 1 が 2 件(落ちる runner / 外向きを落として走らせた"
              f" runner)、5 が 1 件(試験が 1 件も無い)")


def test_not_run_rows_have_no_exit_code(taicho: C.Census) -> None:
    for r in taicho.results:
        if r.verdict in (C.NOT_RUN, C.NO_TESTS):
            assert r.exit_code is None and r.tail_sha256 == ""
        else:
            assert isinstance(r.exit_code, int) and len(r.tail_sha256) == 64


def test_there_is_no_way_to_fold_four_verdicts_into_three(taicho: C.Census) -> None:
    """4 値を 3 値に潰す引数も、走らなかったを通ったに混ぜる呼び方も無い。"""
    assert set(taicho.counts()) == set(C.VERDICTS)
    assert not hasattr(taicho, "pass_rate") and not hasattr(taicho, "合格率")
    assert "分母に含めたもの" in taicho.rate()
    src = (ROOT / "check_census.py").read_text(encoding="utf-8")
    for word in ("shell=True", "coverage", "--fix", "autofix", "rerun", "tolerance", "ignore_"):
        assert word not in src


# ---------------------------------------------------------------- 決定論

def test_measure_verify_matches(built: Path, capsys: pytest.CaptureFixture) -> None:
    out = C.verify(C.Declaration.load(built / "sengen.csv"))
    assert out["ok"] is True and out["一致"] is True and out["判定した回数"] == 2
    assert out["sha256"] == out["2 回目の sha256"]
    assert out["sha256"] == "ab67d3d980edd5a7e1d582792bf7310823a4017818a5601843affdd01cebc3ef"
    with capsys.disabled():
        print(f"[measure] 同じ宣言表で 2 回走らせる: 判定部分の sha256 が一致"
              f"(先頭 12 桁 {out['sha256'][:12]})")


def test_measure_verify_reports_a_mismatch_as_it_is(built: Path,
                                                    capsys: pytest.CaptureFixture) -> None:
    out = C.verify(C.Declaration.load(built / "sengen_yureru.csv"))
    assert out["ok"] is False and out["一致"] is False
    assert out["sha256"] != out["2 回目の sha256"]
    assert out["pending"][0]["reason"] == "2 回目の判定部分がバイト列として不一致"
    (one,) = out["不一致の内訳"]
    assert list(one["違った欄"]) == ["出力の末尾の指紋"]      # 終了コードは両回 0 のまま
    assert "平均も多数決もしない" in str(out["観測"])
    with capsys.disabled():
        print(f"[measure] 2 回で出力が変わる 1 行: 不一致として返る。違った欄は"
              f" {list(one['違った欄'])} だけで、終了コードは 2 回とも同じ")


def test_judgement_part_has_no_clock_in_it(taicho: C.Census) -> None:
    raw = taicho.judgement_bytes().decode("utf-8")
    for key in ("所要秒", "始めた時刻", "ホスト名"):
        assert key not in raw
    assert list(json.loads(raw)["行"][0]) == list(C.JUDGEMENT_KEYS)
    assert [k for k in C.TIMING_KEYS if k != "name"] == ["所要秒", "始めた時刻", "ホスト名"]
    assert all(set(t) == set(C.TIMING_KEYS) for t in taicho.timing())


def test_measure_judgement_bytes_are_byte_identical_from_either_run(
        built: Path, capsys: pytest.CaptureFixture) -> None:
    a = C.census(C.Declaration.load(built / "sengen.csv"))
    b = C.census(C.Declaration.load(built / "sengen.csv"))
    assert a.judgement_bytes() == b.judgement_bytes()
    assert a.timing() != b.timing()      # 時刻は毎回違う(判定部分には入っていない)
    with capsys.disabled():
        print(f"[measure] 判定部分はバイト列として同一、測った条件(所要秒 / 時刻 / ホスト名)は"
              f" 2 回で違う = 非決定な値は一致判定に混ざっていない")


# ---------------------------------------------------------------- 止まる

def test_measure_all_stop_reasons_have_a_path(built: Path, capsys: pytest.CaptureFixture) -> None:
    table = {
        "sengen_runner_retsu_nashi.csv": "宣言表に必要な列が無い",
        "sengen_argv_moji.csv": "argv が配列でない",
        "sengen_timeout_kuuhaku.csv": "timeout が空欄か数でない",
        "sengen_shutten_kuuhaku.csv": "出典の列が空欄",
        "sengen_name_juufuku.csv": "同じ name の行が 2 件以上",
    }
    seen = []
    for name, reason in table.items():
        c = C.census(C.Declaration.load(built / name))
        assert c.report.ok is False
        assert [p.reason for p in c.report.pending] == [reason]
        assert c.results == ()            # 止まったら 1 行も走らせない
        seen.append(reason)
        with capsys.disabled():
            print(f"[measure] 止まった: {reason}({c.report.pending[0].detail})")
    mismatch = C.verify(C.Declaration.load(built / "sengen_yureru.csv"))
    seen.append(mismatch["pending"][0]["reason"])
    assert set(seen) == set(C.STOP_REASONS)
    with capsys.disabled():
        print(f"[measure] 止まる理由コード {len(C.STOP_REASONS)} 個すべてに道がある")


def test_stopped_census_has_no_ledger(built: Path) -> None:
    c = C.census(C.Declaration.load(built / "sengen_name_juufuku.csv"))
    for call in (c.table, c.rate, c.timing, c.judgement_bytes, c.sha256):
        with pytest.raises(RuntimeError):
            call()


# ---------------------------------------------------------------- 書き換えない

def test_measure_nothing_is_rewritten(built: Path, capsys: pytest.CaptureFixture) -> None:
    before = tree_fingerprint(built)
    C.census(C.Declaration.load(built / "sengen.csv"))
    after = tree_fingerprint(built)
    assert before == after
    with capsys.disabled():
        print(f"[measure] 走らせる前と後で合成プロジェクト全体({len(list(built.rglob('*.py')))} 本の script"
              f" を含む)の sha256 が同じ = 宣言表もテストもコードも書き換えていない")


def test_rows_declared_as_having_no_tests_are_never_executed(built: Path) -> None:
    """無い と書かれた行の runner は読まない(走らせない)。"""
    mark = built / "走った証跡.txt"
    argv = json.dumps([sys.executable, "-c", f"open(r'{mark}', 'w').close()"], ensure_ascii=False)
    decl = built / "sengen_nashi_demo_runner.csv"
    M.write_csv(decl, M.HEADER,
                [["道具X", "proj/tool_a", "無い", argv, "20", "いいえ", "", "合成(架空)"]])
    c = C.census(C.Declaration.load(decl))
    assert [r.verdict for r in c.results] == [C.NO_TESTS]
    assert not mark.exists()


# ---------------------------------------------------------------- 外向き

def test_network_is_dropped_unless_the_row_declares_it(taicho: C.Census) -> None:
    env_off, env_on = C._env(False), C._env(True)
    assert env_off["https_proxy"].endswith(":9") and env_off["CHECK_CENSUS_NETWORK"] == "dropped"
    assert not env_on.get("https_proxy", "").endswith(":9")
    assert env_on["CHECK_CENSUS_NETWORK"] == "allowed"
    got = {r.name: r.verdict for r in taicho.results}
    assert got["道具H_外向き不許可"] == C.FAILED      # 同じ runner でも宣言が無ければ落ちる
    assert got["道具K_外向き許可"] == C.PASSED


# ---------------------------------------------------------------- CLI

def test_cli_has_no_options_other_than_help() -> None:
    ap = C.build_parser()
    opts = {s for a in ap._actions for s in a.option_strings}
    subs = [a for a in ap._actions if hasattr(a, "choices") and a.choices]
    assert opts == {"-h", "--help"}
    assert sorted(subs[0].choices) == ["census", "init", "verify"]
    for name, parser in subs[0].choices.items():
        assert {s for a in parser._actions for s in a.option_strings} == {"-h", "--help"}, name


def test_cli_exit_codes(built: Path, capsys: pytest.CaptureFixture) -> None:
    assert C.main(["census", str(built / "sengen.csv")]) == 0          # 必須の行が通った
    assert C.main(["census", str(built / "sengen_name_juufuku.csv")]) == 3
    assert C.main(["verify", str(built / "sengen_yureru.csv")]) == 3
    assert C.main(["census", str(built / "sengen_yomenai.csv")]) == 2
    out = capsys.readouterr().out
    assert "台帳にした" in out and "分母に含めたもの" in out


def test_cli_exit_3_when_a_required_row_does_not_pass(built: Path) -> None:
    decl = built / "sengen_hissu_ochiru.csv"
    argv = json.dumps([sys.executable, "run_ng.py"], ensure_ascii=False)
    M.write_csv(decl, M.HEADER,
                [["道具Y", "proj/tool_b", "在る", argv, "20", "はい", "", "合成(架空)"]])
    c = C.census(C.Declaration.load(decl))
    assert c.not_passed_required() == ("道具Y",)
    assert C.main(["census", str(decl)]) == 3


def test_init_writes_the_eight_columns(tmp_path: Path) -> None:
    p = C.init(tmp_path / "hinagata.csv")
    decl = C.Declaration.load(p)
    assert decl.pending == ()
    assert p.read_text(encoding="utf-8").splitlines()[0].split(",") == list(C.DECL_COLUMNS)
