"""scope_ledger のテスト。合成 fixture は make_fixtures が tmp に作る(実データ・実在の取引先名は入れない)。

test_measure_* が記事に載せた数値の出どころで、assert で固定している(値が変われば記事も変える前提)。
突き合わせる対象は 2 種類ある。

  (1) 合成の対象 script(make_fixtures が書く 15 本)と 18 行の宣言表 = 4 値と理由コードの出そろい
  (2) この repo の公開済み 17 本の道具のソースと、その宣言を verbatim で引いた 17 行の宣言表
      (fixtures/sengen_koukai17.csv)。出典はどれも repo 内の README の行番号

(2) は実行していない。読むのは構文木だけで、import もしない。
"""
from __future__ import annotations

import ast
import hashlib
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FIX))
import make_fixtures as M  # noqa: E402
import scope_ledger as S  # noqa: E402

# 図 2 の行(線の種類)。宣言表の 1 行がちょうど 1 つの種類に入る
SEN_SHURUI = {
    ("answer_check", "外向きの通信を持たない"): "外向きの通信を持たない",
    ("context_pack", "外向きの通信を持たない"): "外向きの通信を持たない",
    ("reader_registry", "外向きの通信を持たない"): "宣言が無い線",
    ("check_census", "シェルを経由しない"): "シェルを経由しない",
    ("intake_triage", "書き込まない"): "書き込まない",
    ("tally_gate", "書き込まない"): "書き込まない",
    ("wareki", "書き込まない"): "宣言が無い線",
    ("asof_table", "名指しの引数を持たない"): "名指しの引数を持たない",
    ("formula_table", "名指しの引数を持たない"): "名指しの引数を持たない",
    ("cross_route", "名指しの引数を持たない"): "名指しの引数を持たない",
    ("jp_charset", "判定しない範囲"): "文章だけの宣言",
    ("jp_name", "同一人物を決めない"): "文章だけの宣言",
    ("jp_corp", "同じ法人を決めない"): "文章だけの宣言",
    ("intake_csv", "差の原因を推定しない"): "文章だけの宣言",
    ("update_ledger", "値の正しさを判定しない"): "文章だけの宣言",
    ("source_pin", "原本の解釈を判定しない"): "文章だけの宣言",
    ("excel_report", "判断待ちを決めない"): "文章だけの宣言",
}
GRID_ROWS = ("外向きの通信を持たない", "シェルを経由しない", "書き込まない",
             "名指しの引数を持たない", "文章だけの宣言", "宣言が無い線")


@pytest.fixture(scope="session")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """合成の対象 script と宣言表を tmp に作る(壊れた .py は repo に置かない)。"""
    return M.build(tmp_path_factory.mktemp("scope_ledger"))


@pytest.fixture(scope="session")
def taicho(built: Path) -> S.Ledger:
    return S.ledger(S.Declaration.load(built / "sengen.csv"))


@pytest.fixture(scope="session")
def koukai() -> S.Ledger:
    return S.ledger(S.Declaration.load(FIX / "sengen_koukai17.csv"))


def tree_fingerprint(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            h.update(str(p.relative_to(root)).replace("\\", "/").encode("utf-8"))
            h.update(p.read_bytes())
    return h.hexdigest()


# ---------------------------------------------------------------- 入り口

def test_committed_real_table_loads() -> None:
    """repo に入れてある 17 行の宣言表は、宣言表として読める(止まる理由が 0 件)。"""
    decl = S.Declaration.load(FIX / "sengen_koukai17.csv")
    assert decl.pending == ()
    assert len(decl.rows) == 17
    assert all(r.source for r in decl.rows)


def test_missing_column_is_not_a_reason_code(built: Path) -> None:
    """列が足りない宣言表は理由コードにせず、宣言表として読めないことにする(終了コード 2)。"""
    with pytest.raises(S.DeclError):
        S.Declaration.load(built / "sengen_retsu_nashi.csv")
    assert S.main(["ledger", str(built / "sengen_retsu_nashi.csv")]) == 2


def test_table_order_is_kept(built: Path, taicho: S.Ledger) -> None:
    """台帳の行の順は宣言表の順(並べ替えない)。"""
    declared = [(r.tool, r.line) for r in S.Declaration.load(built / "sengen.csv").rows]
    assert [(r["道具名"], r["線の名前"]) for r in taicho.table()] == declared


def test_scanners_cover_the_five_kinds() -> None:
    """機械判定の種類は 5 種だけで、その 5 種に 1 つずつ突合の経路がある。"""
    assert set(S.SCANNERS) == set(S.KINDS) == {"import", "call", "kwarg", "option", "write"}
    assert len(S.UNREADABLE_REASONS) == 4
    assert len(S.STOP_REASONS) == 6


# ---------------------------------------------------------------- 合成の 18 行

def test_measure_synthetic_verdicts(taicho: S.Ledger) -> None:
    counts = taicho.counts()
    assert taicho.report.declared_rows == 18
    assert counts == {S.AS_DECLARED: 6, S.MISMATCH: 5, S.NO_DECLARATION: 1, S.UNREADABLE: 6}
    assert sum(counts.values()) == taicho.report.declared_rows
    print(f"[measure] 合成の宣言表 {taicho.report.declared_rows} 行を突き合わせる")
    print(f"[measure] 4 値: 宣言どおり {counts[S.AS_DECLARED]} / 一致しない {counts[S.MISMATCH]}"
          f" / 宣言が無い {counts[S.NO_DECLARATION]} / 機械では読めない {counts[S.UNREADABLE]}")


def test_measure_synthetic_rate_needs_two_denominators(taicho: S.Ledger) -> None:
    r = taicho.rate()
    d = taicho.denominator()
    assert d == {"宣言表の行数": 18, "機械で読めた数": 11, "機械では読めなかった数": 6, "宣言が無い数": 1}
    assert r["遵守率_機械で読めた行のみ"] == "0.5455"
    assert r["遵守率_宣言表の行すべて"] == "0.3333"
    assert "分母に含めたもの" in r and "機械では読めない行を宣言どおりに寄せていない" in r
    print(f"[measure] 遵守率: 機械で読めた行のみ(分母 {d['機械で読めた数']})= {r['遵守率_機械で読めた行のみ']}"
          f" / 宣言表の行すべて(分母 {d['宣言表の行数']})= {r['遵守率_宣言表の行すべて']}")


def test_measure_unreadable_reasons_all_reachable(taicho: S.Ledger) -> None:
    reasons = taicho.unreadable_reasons()
    assert reasons == {"種類の欄が無い": 1, "対象が Python でない": 1,
                       "構文解析できない": 1, "名前が動的に組み立てられている": 3}
    assert all(v > 0 for v in reasons.values())
    print("[measure] 機械では読めない 6 件の理由コード: "
          + " / ".join(f"{k} {v}" for k, v in reasons.items()) + " = 理由コード 4 個すべてに道がある")


def test_measure_mismatch_rows_carry_only_lineno(taicho: S.Ledger) -> None:
    """一致しない行が持つのは、宣言の verbatim と現れた行番号だけ。言葉を足さない。"""
    rows = [r for r in taicho.table() if r["判定"] == S.MISMATCH]
    assert len(rows) == 5
    for r in rows:
        assert r["現れた行"] and all(isinstance(n, int) for n in r["現れた行"])
        assert r["理由コード"] == ""
        assert r["宣言"] and r["出典"]
        assert tuple(r) == S.JUDGEMENT_KEYS
    text = taicho.judgement_bytes().decode("utf-8")
    for word in ("嘘", "違反", "不正", "悪い", "直すべき"):
        assert word not in text
    print(f"[measure] 一致しない 5 件: 現れた行番号は {[r['現れた行'] for r in rows]}"
          "、判定部分に『嘘 / 違反 / 不正』の語は 1 つも無い")


def test_dynamic_forms_are_not_folded_into_as_declared(taicho: S.Ledger) -> None:
    """追えない形を黙って『宣言どおり』に寄せない(見えなかったことを守られていることにしない)。"""
    dyn = [r for r in taicho.table() if r["理由コード"] == "名前が動的に組み立てられている"]
    assert len(dyn) == 3
    assert {r["判定"] for r in dyn} == {S.UNREADABLE}


def test_a_definite_hit_wins_over_an_unreadable_form(tmp_path: Path) -> None:
    """同じソースに『現れた行』と『追えない形』が両方あるときは、一致しない側に入れる。"""
    src = tmp_path / "両方.py"
    src.write_text('import urllib.request\n\n\ndef call(m, n):\n    return getattr(m, n)()\n',
                   encoding="utf-8", newline="\n")
    table = tmp_path / "sengen.csv"
    M.write_csv(table, M.HEADER, [["道具", "外向きの通信を持たない", "ネットワークを持たない",
                                   "合成 L1", "import", "urllib", "両方.py"]])
    lg = S.ledger(S.Declaration.load(table))
    assert lg.table()[0]["判定"] == S.MISMATCH
    assert lg.table()[0]["現れた行"] == [1]


def test_no_declaration_rows_keep_where_we_looked(taicho: S.Ledger) -> None:
    """宣言が無い行も、どこを見て無かったのかという出典を必ず持つ。"""
    rows = [r for r in taicho.table() if r["判定"] == S.NO_DECLARATION]
    assert len(rows) == 1
    for r in rows:
        assert r["宣言"] == "" and r["出典"] and r["現れた行"] == [] and r["理由コード"] == ""


def test_unreadable_rows_keep_the_source(taicho: S.Ledger) -> None:
    """機械では読めない行も、誰の宣言に由来するかを必ず併記する。"""
    for r in taicho.table():
        if r["判定"] == S.UNREADABLE:
            assert r["出典"] and r["宣言"] and r["理由コード"] in S.UNREADABLE_REASONS


# ---------------------------------------------------------------- 公開済み 17 本

def test_measure_real_17_verdicts(koukai: S.Ledger) -> None:
    counts = koukai.counts()
    assert koukai.report.declared_rows == 17
    assert counts == {S.AS_DECLARED: 6, S.MISMATCH: 2, S.NO_DECLARATION: 2, S.UNREADABLE: 7}
    assert koukai.denominator() == {"宣言表の行数": 17, "機械で読めた数": 8,
                                    "機械では読めなかった数": 7, "宣言が無い数": 2}
    r = koukai.rate()
    assert r["遵守率_機械で読めた行のみ"] == "0.7500"
    assert r["遵守率_宣言表の行すべて"] == "0.3529"
    assert koukai.unreadable_reasons()["種類の欄が無い"] == 7
    print(f"[measure] 公開済み 17 本の宣言表 {koukai.report.declared_rows} 行を突き合わせる")
    print(f"[measure] 4 値: 宣言どおり {counts[S.AS_DECLARED]} / 一致しない {counts[S.MISMATCH]}"
          f" / 宣言が無い {counts[S.NO_DECLARATION]} / 機械では読めない {counts[S.UNREADABLE]}")
    print(f"[measure] 遵守率: 機械で読めた行のみ(分母 8)= {r['遵守率_機械で読めた行のみ']}"
          f" / 宣言表の行すべて(分母 17)= {r['遵守率_宣言表の行すべて']}")
    print("[measure] 17 本のうち機械で読めたのは 8 行、残り 9 行は文章だけの宣言 7 と宣言が無い線 2")


def test_measure_real_17_mismatches(koukai: S.Ledger) -> None:
    """一致しない 2 件は、宣言の verbatim と現れた行番号だけを持つ。"""
    rows = [r for r in koukai.table() if r["判定"] == S.MISMATCH]
    assert [(r["道具名"], r["線の名前"], r["現れた行"]) for r in rows] == [
        ("intake_triage", "書き込まない", [635]),
        ("tally_gate", "書き込まない", [555]),
    ]
    for r in rows:
        assert r["宣言"].startswith("**書き出しを持たない**")
        assert r["出典"].endswith(("README.md L21", "README.md L18"))
        assert r["理由コード"] == ""
    print(f"[measure] 一致しない 2 件: {[(r['道具名'], r['現れた行'][0]) for r in rows]}"
          "(出すのは宣言の verbatim と行番号だけ)")


def test_measure_real_17_grid(koukai: S.Ledger) -> None:
    """図 2 の表。線の種類(6)× 4 値の件数。合計は宣言表の行数に等しい。"""
    grid = {row: {v: 0 for v in S.VERDICTS} for row in GRID_ROWS}
    for r in koukai.table():
        grid[SEN_SHURUI[(r["道具名"], r["線の名前"])]][r["判定"]] += 1
    assert grid == {
        "外向きの通信を持たない": {S.AS_DECLARED: 2, S.MISMATCH: 0, S.NO_DECLARATION: 0, S.UNREADABLE: 0},
        "シェルを経由しない": {S.AS_DECLARED: 1, S.MISMATCH: 0, S.NO_DECLARATION: 0, S.UNREADABLE: 0},
        "書き込まない": {S.AS_DECLARED: 0, S.MISMATCH: 2, S.NO_DECLARATION: 0, S.UNREADABLE: 0},
        "名指しの引数を持たない": {S.AS_DECLARED: 3, S.MISMATCH: 0, S.NO_DECLARATION: 0, S.UNREADABLE: 0},
        "文章だけの宣言": {S.AS_DECLARED: 0, S.MISMATCH: 0, S.NO_DECLARATION: 0, S.UNREADABLE: 7},
        "宣言が無い線": {S.AS_DECLARED: 0, S.MISMATCH: 0, S.NO_DECLARATION: 2, S.UNREADABLE: 0},
    }
    assert sum(sum(c.values()) for c in grid.values()) == 17
    for name, c in grid.items():
        print(f"[measure] 線『{name}』: " + " / ".join(f"{k} {v}" for k, v in c.items() if v))


def test_measure_real_17_verify_matches(koukai: S.Ledger) -> None:
    out = S.verify(S.Declaration.load(FIX / "sengen_koukai17.csv"))
    assert out["ok"] is True and out["一致"] is True and out["判定した回数"] == 2
    assert out["sha256"] == out["2 回目の sha256"] == koukai.sha256()
    assert out["sha256"].startswith("0dd9ed76d2d9")
    print(f"[measure] 同じ宣言表で 2 回判定: 判定部分の sha256 が一致(先頭 12 桁 {out['sha256'][:12]})")


def test_measure_real_17_sources_are_in_repo(koukai: S.Ledger) -> None:
    """17 行の出典は全てこの repo の中のファイルの行番号(一次出典が手元にある)。"""
    decl = S.Declaration.load(FIX / "sengen_koukai17.csv")
    assert len(decl.rows) == 17
    assert all(r.source.startswith("tools/") for r in decl.rows)
    assert len({r.tool for r in decl.rows}) == 17
    read = koukai.read_conditions()
    assert sum(1 for x in read if x["種類"]) == 8
    print("[measure] 出典は 17 行すべて repo 内の README の行番号、道具名は重複なしで 17 本")


# ---------------------------------------------------------------- 決定論と、書き換えないこと

def test_judgement_part_excludes_time_path_and_host(taicho: S.Ledger) -> None:
    raw = taicho.judgement_bytes().decode("utf-8")
    read = taicho.read_conditions()
    for key in ("読んだ時刻", "ホスト名", "読んだ絶対パス"):
        assert key not in raw
    assert all(tuple(x) == S.READ_KEYS for x in read)
    assert any(x["読んだ絶対パス"] for x in read)
    assert all(x["読んだ時刻"] and x["ホスト名"] for x in read)


def test_nothing_is_rewritten(built: Path, koukai: S.Ledger) -> None:
    """突き合わせの前後で、対象のソースも宣言表も 1 バイトも変わらない。"""
    before_built = tree_fingerprint(built)
    before_tools = tree_fingerprint(ROOT.parent)
    S.ledger(S.Declaration.load(built / "sengen.csv")).table()
    S.verify(S.Declaration.load(built / "sengen.csv"))
    S.verify(S.Declaration.load(FIX / "sengen_koukai17.csv"))
    assert tree_fingerprint(built) == before_built
    assert tree_fingerprint(ROOT.parent) == before_tools
    print("[measure] 突合の前後で、合成の対象と repo の tools/ 全体の sha256 が同じ = 1 文字も書き換えていない")


def test_source_has_no_execution_path() -> None:
    """対象を実行する経路・取りに行く経路を、この部品のソース自身が持たない(自分の規律を自分で読む)。"""
    tree = ast.parse(S.read_source(ROOT / "scope_ledger.py"))
    for mod in ("subprocess", "importlib", "urllib", "socket", "http", "requests"):
        assert S.scan_import(tree, mod)[0] == [], mod
    for name in ("exec", "eval", "literal_eval", "system", "Popen", "run"):
        assert S.scan_call(tree, name)[0] == [], name
    assert S.scan_import(tree, "ast")[0]


def test_cli_has_no_options_other_than_help() -> None:
    ap = S.build_parser()
    sub = [a for a in ap._actions if hasattr(a, "choices") and a.choices]
    assert set(sub[0].choices) == {"ledger", "verify", "init"}
    for name, parser in sub[0].choices.items():
        options = {o for a in parser._actions for o in a.option_strings}
        assert options == {"-h", "--help"}, name


def test_rate_always_comes_with_counts_and_denominator(taicho: S.Ledger) -> None:
    """遵守率だけを返す呼び方が無い(4 値の件数と分母の内訳が必ず付く)。"""
    r = taicho.rate()
    for key in (*S.VERDICTS, *taicho.denominator(), "分母に含めたもの", "一致しない行"):
        assert key in r


# ---------------------------------------------------------------- 止まる

@pytest.mark.parametrize("name,reason", [
    ("sengen_shutten_kuuhaku.csv", S.STOP_REASONS[0]),
    ("sengen_path_nashi.csv", S.STOP_REASONS[1]),
    ("sengen_shurui_gai.csv", S.STOP_REASONS[2]),
    ("sengen_meizashi_kuuhaku.csv", S.STOP_REASONS[3]),
    ("sengen_juufuku.csv", S.STOP_REASONS[4]),
])
def test_measure_stop_reasons(built: Path, name: str, reason: str) -> None:
    lg = S.ledger(S.Declaration.load(built / name))
    assert lg.report.ok is False
    assert [p.reason for p in lg.report.pending] == [reason]
    assert lg.results == ()
    for call in (lg.table, lg.rate, lg.judgement_bytes, lg.read_conditions):
        with pytest.raises(RuntimeError):
            call()
    print(f"[measure] 止まった: {reason}({lg.report.pending[0].detail})")


def test_measure_stop_reason_when_two_rounds_differ(built: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """2 回目の判定部分がバイト列として一致しないときは、吸収せず観測としてそのまま返す。"""
    seen: list[int] = []
    original = S.read_source

    def changing(path: Path) -> str:
        seen.append(1)
        return original(path) if len(seen) <= 15 else "import urllib.request\n"

    monkeypatch.setattr(S, "read_source", changing)
    out = S.verify(S.Declaration.load(built / "sengen.csv"))
    assert out["ok"] is False
    assert out["sha256"] != out["2 回目の sha256"]
    assert [p["reason"] for p in out["pending"]] == [S.STOP_REASONS[5]]
    assert out["不一致の内訳"]
    assert "平均も多数決もしない" in out["観測"]
    print(f"[measure] 止まった: {S.STOP_REASONS[5]}(違った行 {len(out['不一致の内訳'])} 件、"
          "違った欄は判定と現れた行だけ)")
    print("[measure] 止まる理由コード 6 個すべてに道がある")


def test_main_returns_three_when_something_mismatches(built: Path) -> None:
    assert S.main(["ledger", str(built / "sengen.csv")]) == 3
    assert S.main(["verify", str(FIX / "sengen_koukai17.csv")]) == 0


def test_init_writes_a_template(tmp_path: Path) -> None:
    p = S.init(tmp_path / "ひな型.csv")
    decl = S.Declaration.load(p)
    assert decl.pending == () or all(x.reason == S.STOP_REASONS[1] for x in decl.pending)
    assert [r.tool for r in decl.rows][:2] == ["道具A", "道具A"]
