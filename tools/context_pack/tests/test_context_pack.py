"""context_pack の検査。合成データだけを使う(地域名・料率・限度額・出典名はすべて架空)。

test_measure_* が記事に載せた数値の出どころで、固定の fixture から決定論的に出る値を
`assert 変数 == 値` で固定している(値が変われば記事も変える前提)。
"""
from __future__ import annotations

import itertools
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
import context_pack as C  # noqa: E402

sys.path.insert(0, str(FIX))
import make_fixtures  # noqa: E402

ROWS = C.load_rows(FIX / "hiita.csv")
DECL = C.Declaration.load(FIX / "sengen.csv")

# 問い 12 件(前の 5 件は塊ができる、後の 7 件は 7 つの理由コードで止まる)
ASKS = (("保険料率_甲", "地域=地域A"), ("保険料率_甲", "地域=地域B"),
        ("保険料率_乙", "地域=地域A"), ("最低賃金", "地域=地域A"),
        ("限度額_丁", "区分=区分1"),
        ("保険料率_甲", "地域=地域C"), ("保険料率_甲", "地域=地域D"),
        ("保険料率_甲", "地域=地域E"), ("保険料率_甲", "地域=地域F"),
        ("保険料率_甲", "地域=地域G"), ("保険料率_丙", "地域=地域A"),
        ("保険料率_甲", "地域=地域Z"))

ASK = {"rule": "保険料率_甲", "selector": "地域=地域A"}
ASK_TENTATIVE = {"rule": "保険料率_乙", "selector": "地域=地域A"}


def ask_of(pair: tuple) -> dict:
    return {"rule": pair[0], "selector": pair[1]}


def packed(ask: dict = None, decl: C.Declaration = None, fields: tuple = ()) -> C.Pack:
    return C.pack(ROWS, decl or DECL, ask or ASK, fields)


# ---------------------------------------------------------------- 宣言表

def test_the_declaration_names_the_file_and_its_hash() -> None:
    import hashlib
    assert DECL.name == "sengen.csv"
    assert DECL.sha256 == hashlib.sha256((FIX / "sengen.csv").read_bytes()).hexdigest()
    assert [f.name for f in DECL.fields] == ["値", "対象", "有効期間", "公表時点", "出典",
                                             "原本", "順位"]


def test_required_fields_are_always_out_and_the_rest_only_when_asked() -> None:
    assert [f.name for f in DECL.chosen()] == ["値", "対象", "有効期間", "公表時点", "出典", "原本"]
    assert [f.name for f in DECL.chosen(("順位",))] == ["値", "対象", "有効期間", "公表時点",
                                                        "出典", "原本", "順位"]


def test_max_chars_and_pins_are_read_from_the_declaration() -> None:
    assert DECL.by_name("出典").max_chars == 120
    assert DECL.by_name("原本").pins == ("source_file", "source_row", "source_sha256")
    assert DECL.by_name("順位").required is False


def test_a_declaration_that_drops_a_core_column_is_a_defect_not_a_reason_code() -> None:
    with pytest.raises(C.DeclError) as e:
        C.Declaration.load(FIX / "sengen_shutten_nashi.csv")
    assert "必ず焼く列が宣言に無い" in str(e.value) and "source" in str(e.value)


@pytest.mark.parametrize("rows, message", [
    ([{"field": "値", "required": "○", "max_chars": "40", "pin": "payload"}], "必ず焼く列"),
    ([{"field": "", "required": "○", "max_chars": "", "pin": "payload"}], "field が無い"),
    ([{"field": "値: 円", "required": "○", "max_chars": "", "pin": "payload"}], "1 field = 1 行"),
    ([{"field": "値", "required": "○", "max_chars": "", "pin": ""}], "pin が無い"),
    ([{"field": "値", "required": "○", "max_chars": "", "pin": "知らない列"}], "知らない列名"),
    ([{"field": "値", "required": "○", "max_chars": "0", "pin": "payload"}], "max_chars"),
    ([{"field": "値", "required": "○", "max_chars": "ななじゅう", "pin": "payload"}], "max_chars"),
    ([], "宣言表が空"),
])
def test_an_unreadable_declaration_stops_with_exit_code_two(rows: list, message: str) -> None:
    with pytest.raises(C.DeclError) as e:
        C.Declaration.of(rows)
    assert message in str(e.value)


def test_two_fields_with_the_same_name_stop() -> None:
    rows = [{"field": "値", "required": "○", "max_chars": "", "pin": "payload"},
            {"field": "値", "required": "○", "max_chars": "", "pin": "selector"}]
    with pytest.raises(C.DeclError) as e:
        C.Declaration.of(rows)
    assert "2 行ある" in str(e.value)


def test_a_declaration_with_no_required_field_stops() -> None:
    rows = [{"field": "値", "required": "", "max_chars": "", "pin": "payload"}]
    with pytest.raises(C.DeclError) as e:
        C.Declaration.of(rows)
    assert "必ず出す field が 1 つも無い" in str(e.value)


def test_an_unknown_column_in_the_declaration_file_stops(tmp_path: Path) -> None:
    p = tmp_path / "sengen_yobun.csv"
    p.write_text("field,required,max_chars,pin,summarize\n値,○,40,payload,はい\n",
                 encoding="utf-8")
    with pytest.raises(C.DeclError) as e:
        C.Declaration.load(p)
    assert "知らない欄" in str(e.value)


# ---------------------------------------------------------------- 引いた行

def test_the_rows_are_read_from_csv_and_from_a_one_line_json() -> None:
    assert len(ROWS) == 12
    one = C.load_rows(FIX / "hiita_1gyou.json")
    assert len(one) == 1 and one[0]["rule"] == "保険料率_甲"


def test_the_same_block_comes_out_of_the_table_and_out_of_the_one_line_json() -> None:
    a = packed()
    b = C.pack(C.load_rows(FIX / "hiita_1gyou.json"), DECL, ASK)
    assert a.text() == b.text() and a.sha256() == b.sha256()


@pytest.mark.parametrize("over, message", [
    ({"payload": ""}, "payload が空"),
    ({"selector": ""}, "selector が空"),
    ({"rule": ""}, "rule が空"),
    ({"valid_from": "2026/03/01"}, "日付として読めない"),
    ({"known_from": "令和8年2月10日"}, "日付として読めない"),
    ({"known_quality": "たぶん実値"}, "known_quality"),
    ({"source_sha256": "abc"}, "64 桁"),
    ({"priority": "ゼロ"}, "整数"),
    ({"source_row": "2 行目"}, "整数"),
])
def test_a_row_that_cannot_be_read_stops_with_exit_code_two(over: dict, message: str) -> None:
    row = dict(ROWS[0])
    row.update(over)
    with pytest.raises(C.DeclError) as e:
        C._check_row(row, 1)
    assert message in str(e.value)


def test_an_unknown_column_in_the_rows_stops() -> None:
    row = dict(ROWS[0], 備考="あとで直す")
    with pytest.raises(C.DeclError) as e:
        C._check_row(row, 1)
    assert "知らない列" in str(e.value)


def test_a_value_with_a_line_break_stops_because_one_field_is_one_line() -> None:
    row = dict(ROWS[0], source="合成の料率表\n2026 年度版")
    with pytest.raises(C.DeclError) as e:
        C._check_row(row, 1)
    assert "改行" in str(e.value)


# ---------------------------------------------------------------- 焼いたもの

def test_every_core_column_is_burned_into_the_block() -> None:
    p = packed()
    text = p.text()
    row = p.row
    for column in C.CORE_PINS:
        assert row[column] in text or C._value_of(column, row[column]) in text


def test_the_block_is_one_line_per_field_in_the_order_of_the_declaration() -> None:
    lines = packed().text().splitlines()
    assert [line.split(": ", 1)[0] for line in lines] == ["値", "対象", "有効期間",
                                                          "公表時点", "出典", "原本"]


def test_the_pinned_columns_are_reported_with_their_names() -> None:
    pinned = packed().pinned()
    assert pinned["原本"]["pin"] == ["source_file", "source_row", "source_sha256"]
    assert pinned["有効期間"]["値"] == "2026-03-01 / (なし)"


def test_an_empty_end_of_the_period_is_written_not_guessed() -> None:
    assert C.EMPTY_MARK in packed().text()
    assert "以降" not in packed().text()      # 言い換えをしない


def test_numbers_come_out_as_decimal_strings() -> None:
    assert C._value_of("payload", "9.70") == "9.70"      # 末尾の 0 を落とさない
    assert C._value_of("payload", "357000") == "357000"
    assert C._value_of("priority", "0") == "0"
    assert C._value_of("source_row", "007") == "007"     # 数の列でなければそのまま
    assert C._value_of("payload", "表: 等級表") == "表: 等級表"


def test_a_tentative_known_from_is_written_into_the_block() -> None:
    p = packed(ASK_TENTATIVE)
    assert p.row["known_quality"] == C.TENTATIVE
    assert C.NOTE_TENTATIVE in p.text()
    assert C.NOTE_TENTATIVE not in packed().text()


def test_asking_for_an_optional_field_adds_exactly_one_line() -> None:
    before, after = packed().text(), packed(fields=("順位",)).text()
    assert after.splitlines()[:-1] == before.splitlines()
    assert after.splitlines()[-1] == "順位: 0"


# ---------------------------------------------------------------- 止まる

def test_zero_hits_stops_instead_of_filling_with_a_near_row() -> None:
    p = packed({"rule": "保険料率_甲", "selector": "地域=地域Z"})
    assert p.report.stage == C.MATCH and p.report.reasons() == ["該当 0 件"]
    assert p.report.matched == 0


def test_two_hits_stop_and_priority_is_not_used_to_pick_a_winner() -> None:
    p = packed({"rule": "保険料率_丙", "selector": "地域=地域A"})
    assert p.report.reasons() == ["該当 2 件以上"]
    assert "11 / 12" in p.report.pending[0].detail
    hit = [r for r in ROWS if r["rule"] == "保険料率_丙"]
    assert {r["priority"] for r in hit} == {"0", "10"}      # 順位は違うが勝たせない


@pytest.mark.parametrize("selector, reason", [
    ("地域=地域C", "出典が空欄"),
    ("地域=地域D", "sha256 が無い"),
    ("地域=地域E", "有効期間が空欄"),
    ("地域=地域F", "公表時点が空欄"),
    ("地域=地域G", "max_chars 超過"),
])
def test_a_missing_core_value_stops_the_whole_block(selector: str, reason: str) -> None:
    p = packed({"rule": "保険料率_甲", "selector": selector})
    assert p.report.stage == C.BUILD and p.report.reasons() == [reason]
    with pytest.raises(C.PackError) as e:
        p.text()
    assert e.value.reason == reason


def test_asking_for_a_field_that_is_not_declared_stops() -> None:
    p = packed(fields=("計算方法",))
    assert p.report.stage == C.DECL
    assert p.report.reasons() == ["宣言に無い field を要求"]


def test_a_pin_for_a_column_that_is_not_in_the_rows_stops() -> None:
    p = packed(decl=C.Declaration.load(FIX / "sengen_michi_hashira.csv"))
    assert p.report.reasons() == ["pin に指定された列が行に無い"]
    assert "known_to" in p.report.pending[0].detail


def test_a_second_build_that_differs_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    original, turn = C._render, itertools.count()
    monkeypatch.setattr(C, "_render",
                        lambda f, r: original(f, r) + ("" if next(turn) % 2 == 0 else "x"))
    p = packed()
    assert p.report.reasons() == ["2 回目の組み立てでバイト列が不一致"]


def test_over_the_limit_is_not_truncated() -> None:
    p = packed({"rule": "保険料率_甲", "selector": "地域=地域G"})
    long_source = [r for r in ROWS if r["selector"] == "地域=地域G"][0]["source"]
    assert len(long_source) == 122 and DECL.by_name("出典").max_chars == 120
    assert "122 字" in p.report.pending[0].detail
    assert p._text == ""        # 途中まで作った塊も残さない


def test_every_reason_code_has_a_path() -> None:
    seen = set()
    for pair in ASKS:
        seen |= set(packed(ask_of(pair)).report.reasons())
    seen |= set(packed(fields=("計算方法",)).report.reasons())
    seen |= set(packed(decl=C.Declaration.load(FIX / "sengen_michi_hashira.csv")).report.reasons())
    original, turn = C._render, itertools.count()
    try:
        C._render = lambda f, r: original(f, r) + ("" if next(turn) % 2 == 0 else "x")
        seen |= set(packed().report.reasons())
    finally:
        C._render = original
    assert len(C.REASONS) == 10
    assert seen == set(C.REASONS)


# ---------------------------------------------------------------- 持たせていないもの

def test_there_is_no_argument_for_summarising_or_truncating_or_pasting_the_whole_table() -> None:
    src = (ROOT / "context_pack.py").read_text(encoding="utf-8")
    for banned in ("--summary", "--truncate", "--all", "--max-tokens", "--model",
                   "textwrap", "requests", "urllib", "openai", "anthropic"):
        assert banned not in src


def test_the_component_does_not_return_a_token_count() -> None:
    p = packed()
    text = json.dumps(p.as_dict(), ensure_ascii=False)
    assert "token 数は返さない" in text
    assert "トークン数" not in {k for k in p.sizes()}
    assert all("token" not in k for k in p.sizes())


def test_the_component_does_not_write_a_request_sentence() -> None:
    text = packed().text()
    for banned in ("計算して", "お願い", "してください", "判断して", "回答"):
        assert banned not in text


def test_the_input_rows_are_not_rewritten() -> None:
    before = json.dumps(ROWS, ensure_ascii=False, sort_keys=True)
    for pair in ASKS:
        packed(ask_of(pair))
    assert json.dumps(ROWS, ensure_ascii=False, sort_keys=True) == before


def test_the_ask_has_no_default() -> None:
    for ask in ({"rule": "保険料率_甲"}, {"selector": "地域=地域A"}, {}):
        with pytest.raises(C.DeclError):
            C.pack(ROWS, DECL, ask)


# ---------------------------------------------------------------- 大きさ

def test_the_sizes_are_returned_with_what_they_were_compared_against() -> None:
    s = packed().sizes()
    assert set(s["比べた相手"]) == {"表全体をそのまま貼る", "機械が引数で引く 1 行", "値だけを貼る"}
    assert s["表全体から減った文字数"] == (s["比べた相手"]["表全体をそのまま貼る"]["文字数"]
                                          - s["大きさ"]["文字数"])


def test_the_whole_table_is_measured_but_never_returned() -> None:
    out = json.dumps(packed().as_dict(), ensure_ascii=False)
    assert "限度額_丁" not in out       # 他の行の値は塊にも報告にも出ない
    assert "9.82" not in out


# ---------------------------------------------------------------- CLI

def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "context_pack.py"), *args],
                          capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT))


def test_cli_pack_returns_zero_and_prints_the_block() -> None:
    r = _run("pack", "fixtures/hiita.csv", "--decl", "fixtures/sengen.csv",
             "--rule", "保険料率_甲", "--select", "地域=地域A")
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["塊"] == packed().text() and out["塊の sha256"] == packed().sha256()


def test_cli_pack_returns_three_when_it_stops() -> None:
    r = _run("pack", "fixtures/hiita.csv", "--decl", "fixtures/sengen.csv",
             "--rule", "保険料率_甲", "--select", "地域=地域Z")
    assert r.returncode == 3 and json.loads(r.stdout)["pending"][0]["reason"] == "該当 0 件"


def test_cli_returns_two_when_the_declaration_is_a_defect() -> None:
    r = _run("pack", "fixtures/hiita.csv", "--decl", "fixtures/sengen_shutten_nashi.csv",
             "--rule", "保険料率_甲", "--select", "地域=地域A")
    assert r.returncode == 2 and "必ず焼く列" in r.stderr


def test_cli_verify_builds_twice_and_compares() -> None:
    r = _run("verify", "fixtures/hiita.csv", "--decl", "fixtures/sengen.csv",
             "--rule", "保険料率_甲", "--select", "地域=地域A")
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["一致"] is True and out["組み立てた回数"] == 4


def test_cli_init_writes_a_template_and_does_not_overwrite(tmp_path: Path) -> None:
    p = tmp_path / "sengen.csv"
    r = _run("init", str(p))
    assert r.returncode == 0 and p.exists()
    decl = C.Declaration.load(p)
    assert [f.name for f in decl.fields] == [f.name for f in DECL.fields]
    again = _run("init", str(p))
    assert again.returncode == 2 and "すでにある" in again.stderr


def test_the_fixtures_are_synthetic_only() -> None:
    src = (FIX / "make_fixtures.py").read_text(encoding="utf-8")
    assert "架空" in src
    assert "C:" not in src and "D:" not in src


def test_the_fixtures_come_out_of_the_generator() -> None:
    before = {p.name: p.read_bytes() for p in sorted(FIX.glob("*.csv"))}
    make_fixtures.build()
    assert {p.name: p.read_bytes() for p in sorted(FIX.glob("*.csv"))} == before


def test_the_hash_in_the_rows_is_the_hash_of_the_synthetic_original() -> None:
    import hashlib
    want = hashlib.sha256((FIX / "moto_ryouritsu.csv").read_bytes()).hexdigest()
    assert packed().row["source_sha256"] == want
    assert want in packed().text()


def test_changing_the_original_by_one_character_changes_the_hash(tmp_path: Path) -> None:
    original = (FIX / "moto_ryouritsu.csv").read_text(encoding="utf-8")
    changed = tmp_path / "moto_ryouritsu.csv"
    changed.write_text(original.replace("9.70", "9.71"), encoding="utf-8")
    assert C.sha256_of(changed) != C.sha256_of(FIX / "moto_ryouritsu.csv")


# ---------------------------------------------------------------- 測定(記事の数値)

def measure_asks() -> dict:
    made, stopped, reasons = [], [], []
    for pair in ASKS:
        p = packed(ask_of(pair))
        if p.report.ok:
            made.append((pair, len(p.text()), len(p.text().encode("utf-8"))))
        else:
            stopped.append(pair)
            reasons += p.report.reasons()
    return {"問い": len(ASKS), "塊ができた": len(made), "止まった": len(stopped),
            "理由コード": reasons, "塊": made}


def test_measure_asks(capsys: pytest.CaptureFixture) -> None:
    m = measure_asks()
    assert m["問い"] == 12 and m["塊ができた"] == 5 and m["止まった"] == 7
    assert m["理由コード"] == ["出典が空欄", "sha256 が無い", "有効期間が空欄", "公表時点が空欄",
                               "max_chars 超過", "該当 2 件以上", "該当 0 件"]
    assert len(set(m["理由コード"])) == 7
    assert [chars for _, chars, _ in m["塊"]] == [192, 192, 215, 192, 194]
    with capsys.disabled():
        print(f"\n[measure] 引いた行 {len(ROWS)} 行に問い {m['問い']} 件:"
              f" 塊ができた {m['塊ができた']} 件 / 止まった {m['止まった']} 件"
              f"(理由コードは {len(set(m['理由コード']))} 種類)")
        for pair, chars, byts in m["塊"]:
            print(f"[measure] 塊 {pair[0]} / {pair[1]}: {chars} 字 / {byts} バイト")
        for pair, reason in zip([p for p in ASKS if p not in [x for x, _, _ in m['塊']]],
                                m["理由コード"]):
            print(f"[measure] 止まった {pair[0]} / {pair[1]}: {reason}")


def test_measure_sizes(capsys: pytest.CaptureFixture) -> None:
    s = packed().sizes()
    assert s["大きさ"] == {"文字数": 192, "バイト数": 270}
    assert s["比べた相手"]["表全体をそのまま貼る"] == {"文字数": 4174, "バイト数": 4880}
    assert s["比べた相手"]["機械が引数で引く 1 行"] == {"文字数": 346, "バイト数": 390}
    assert s["比べた相手"]["値だけを貼る"] == {"文字数": 5, "バイト数": 5}
    assert s["表全体から減った文字数"] == 3982
    assert s["値だけより増えた文字数"] == 187
    with capsys.disabled():
        print(f"\n[measure] 同じ 1 件を渡す 4 つの形(文字数 / バイト数):"
              f" 表全体 {s['比べた相手']['表全体をそのまま貼る']['文字数']} /"
              f" {s['比べた相手']['表全体をそのまま貼る']['バイト数']}、"
              f" 機械が引数で引く 1 行 {s['比べた相手']['機械が引数で引く 1 行']['文字数']} /"
              f" {s['比べた相手']['機械が引数で引く 1 行']['バイト数']}、"
              f" 塊 {s['大きさ']['文字数']} / {s['大きさ']['バイト数']}、"
              f" 値だけ {s['比べた相手']['値だけを貼る']['文字数']} /"
              f" {s['比べた相手']['値だけを貼る']['バイト数']}")
        print(f"[measure] 返すのは文字数とバイト数だけ({s['proxy の限界']})")


def test_measure_tentative_note(capsys: pytest.CaptureFixture) -> None:
    real, tentative = packed(), packed(ASK_TENTATIVE)
    assert len(real.text()) == 192 and len(tentative.text()) == 215
    assert len(tentative.text()) - len(real.text()) == 23
    assert tentative.text().splitlines()[-1] == C.NOTE_TENTATIVE
    with capsys.disabled():
        print(f"\n[measure] 公表時点が仮置きの行の塊は {len(tentative.text())} 字で、"
              f"実値の行の {len(real.text())} 字より 1 行(23 字)長い"
              f"(注記『{C.NOTE_TENTATIVE}』が入る)")


def test_measure_verify(capsys: pytest.CaptureFixture) -> None:
    same, total = 0, 0
    for pair in ASKS[:5]:
        v = C.verify(ROWS, DECL, ask_of(pair))
        total += 1
        same += 1 if v["一致"] else 0
        assert v["組み立てた回数"] == 4
    assert (same, total) == (5, 5)
    with capsys.disabled():
        print(f"\n[measure] 塊ができた {total} 件を 2 回ずつ組み立てる:"
              f" sha256 が一致 {same} / {total} 件(1 件あたり 4 回組み立てた)")


def test_measure_one_line_json_gives_the_same_bytes(capsys: pytest.CaptureFixture) -> None:
    a, b = packed(), C.pack(C.load_rows(FIX / "hiita_1gyou.json"), DECL, ASK)
    assert a.sha256() == b.sha256()
    assert a.sizes()["比べた相手"]["表全体をそのまま貼る"]["文字数"] == 4174
    assert b.sizes()["比べた相手"]["表全体をそのまま貼る"]["文字数"] == 346
    with capsys.disabled():
        print(f"\n[measure] 入り口が 12 行の CSV でも 1 行 JSON でも塊は同じバイト列"
              f"(sha256 {a.sha256()[:12]})。表全体の文字数だけが"
              f" 4174 → 346 と変わる")


def test_measure_stops(capsys: pytest.CaptureFixture) -> None:
    out = {}
    for selector in ("地域=地域C", "地域=地域D", "地域=地域E", "地域=地域F", "地域=地域G"):
        p = packed({"rule": "保険料率_甲", "selector": selector})
        out[selector] = (p.report.stage, p.report.reasons()[0])
    for ask, label in ((({"rule": "保険料率_丙", "selector": "地域=地域A"}), "該当 2 件"),
                       (({"rule": "保険料率_甲", "selector": "地域=地域Z"}), "該当 0 件")):
        p = packed(ask)
        out[label] = (p.report.stage, p.report.reasons()[0])
    p = packed(fields=("計算方法",))
    out["宣言に無い field"] = (p.report.stage, p.report.reasons()[0])
    p = packed(decl=C.Declaration.load(FIX / "sengen_michi_hashira.csv"))
    out["行に無い列を焼く宣言"] = (p.report.stage, p.report.reasons()[0])
    assert len(out) == 9
    assert all(stage in (C.DECL, C.MATCH, C.BUILD) for stage, _ in out.values())
    with capsys.disabled():
        print()
        for name, (stage, reason) in out.items():
            print(f"[measure] {name}: {stage}の段で止まった({reason})。塊は作られない")
