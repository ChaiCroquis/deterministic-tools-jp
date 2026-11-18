"""cohort_close の試験。合成した 4 表(fixtures/*_a.csv)だけを使う。

test_measure_* が記事に載せた数値の出どころで、assert で固定している(値が変われば記事も
変える)。`python -m pytest tools/cohort_close -q -s` で [measure] の行が出る。
"""
from __future__ import annotations

import ast
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import cohort_close as C  # noqa: E402

FX = ROOT / "fixtures"
A, B, CC, D = C.KUBUN


def tables():
    return C.load(FX / "rows_a.csv", FX / "lines_a.csv", FX / "symbols_a.csv",
                  FX / "coverage_a.csv")


def values(result) -> dict[str, str]:
    return {r["rule_id"]: r["区分"] for r in result["rules"]}


# ---------------------------------------------------------------- 記事に載せた測定値

def test_measure_16_rules_split_into_four_values_and_five_extras() -> None:
    rows, lines, symbols, cover = tables()
    assert (len(rows), len(lines), len(symbols), len(cover)) == (17, 11, 6, 15)
    out = C.check(rows, lines, symbols, cover)
    assert out["rule の件数"] == 16
    assert list(out["4 値"].values()) == [2, 6, 1, 2]
    assert sum(out["4 値"].values()) == 11
    assert list(out["別枠"].values()) == [1, 1, 1, 1, 1]
    assert out[C.ORPHAN] == {"rule id の数": 1, "線の行数": 1}
    assert out["件数の合計の検算"] == "4 値 11 + 別枠 5 = 16 / rule の件数 16"
    print("[measure] rows_a / lines_a / symbols_a / coverage_a: 行の台帳 17 行(rule 16 件)/ "
          "線の台帳 11 行 / 記号の登録 6 行 / 収録の台帳 15 行")
    print("[measure] 4 値は (A) 2 / (B) 6 / (C) 1 / (D) 2(合計 11 件)、別枠は 5 枠が 1 件ずつ"
          "(合計 5 = 16 - 11)。台帳に無い rule id を指す線は 1 行で、rule の件数に入らない")


def test_measure_line_closed_rules_by_coverage() -> None:
    out = C.check(*tables())
    cross = out["区分 × 収録の状態"]
    assert cross[B] == {"収録": 1, "未収録": 4, "記載なし": 1, C.NO_COVER_ROW: 0}
    assert cross[CC] == {"収録": 1, "未収録": 0, "記載なし": 0, C.NO_COVER_ROW: 0}
    assert cross[A] == {"収録": 1, "未収録": 1, "記載なし": 0, C.NO_COVER_ROW: 0}
    assert cross[D] == {"収録": 1, "未収録": 0, "記載なし": 0, C.NO_COVER_ROW: 1}
    by_line = cross[B]["未収録"] + cross[CC]["未収録"]
    assert (out["4 値"][B] + out["4 値"][CC], by_line) == (7, 4)
    assert out["含む側の語なし の印が付いた rule"] == 3
    print("[measure] 対象の線で閉じる記載が在る rule((B) 6 + (C) 1)は 7 件。収録の状態は "
          "未収録 4 / 収録 2 / 記載なし 1 で、区分には使っていない")
    print("[measure] 日付で閉じる記載だけの (A) 2 件は 収録 1 / 未収録 1。(D) 2 件のうち 1 件は "
          "収録の台帳に行が無く、書かれた `記載なし` とは別の値で返る")
    print("[measure] 含む側の語なし の印が付いた rule は 3 件(R05・R07・R15)。3 件とも (B) の "
          "ままで、向きは当てていない")


def test_measure_end_date_alone_sees_three_of_nine() -> None:
    """日付の欄だけを見る掃除だと、閉じる記載の在る 9 件のうち 3 件しか見えない。"""
    rows, lines, symbols, cover = tables()
    out = C.check(rows, lines, symbols, cover)
    four = out["4 値"]
    with_close = four[A] + four[B] + four[CC]
    seen_by_date = four[A] + four[CC]
    assert (with_close, seen_by_date, four[B]) == (9, 3, 6)
    print("[measure] 閉じる記載が在る rule は 9 件((A) 2 + (B) 6 + (C) 1)。有効期間の終わりの欄 "
          "だけを見ると見えるのは 3 件で、残り 6 件は開いたままの行に見える")


def test_measure_removing_one_line_moves_only_that_rule() -> None:
    rows, lines, symbols, cover = tables()
    before = values(C.judge(rows, lines, symbols, cover))
    moves = {}
    for rid in ("R03", "R06"):
        cut = [ln for ln in lines if ln[0] != rid]
        assert len(cut) == len(lines) - 1
        after = values(C.judge(rows, cut, symbols, cover))
        changed = [k for k in before if before[k] != after[k]]
        assert changed == [rid]
        moves[rid] = (before[rid], after[rid])
    assert moves == {"R03": (B, D), "R06": (CC, A)}
    v = C.verify(rows, lines, symbols, cover)
    assert v["ok"] is True and v["④ で消してみた線の数"] == 7
    print("[measure] 線 1 行を消す: R03 だけが (B) → (D)、R06 だけが (C) → (A) へ動く。"
          "verify は線が 1 本の 7 件すべてで同じことを確かめる(7/7)")


def test_measure_boundary_day_follows_the_side_word() -> None:
    line = ("1970-01-01 以前生まれのみ", "以前", C.SYM_BIRTH)
    days = ("1969-12-31", "1970-01-01", "1970-01-02")
    got = [C.side_of(*line, d) for d in days]
    assert got == [C.SIDE_IN, C.SIDE_IN, C.SIDE_OUT]
    blank = [C.side_of(line[0], "", line[2], d) for d in days]
    assert blank == [C.SIDE_NO_WORD] * 3
    later = [C.side_of("1975-06-02 以降", "以降", C.SYM_BIRTH, d)
             for d in ("1975-06-01", "1975-06-02", "1975-06-03")]
    assert later == [C.SIDE_OUT, C.SIDE_IN, C.SIDE_IN]
    unreadable = ["〜1970 年度生まれ", "1970 年 1 月 1 日以前", "1970-01-01 より前",
                  "合成の年齢の基準(架空)", "1970-13-01 以前"]
    assert [C.side_of(t, "以前", C.SYM_BIRTH, days[1]) for t in unreadable] == [C.SIDE_UNREADABLE] * 5
    assert C.side_of(line[0], "以降", line[2], days[1]) == C.SIDE_UNREADABLE
    assert C.side_of(line[0], line[1], "年齢の線", days[1]) == C.SIDE_UNREADABLE
    print("[measure] 境目の前日・当日・翌日: `以前` の線は 内側 / 内側 / 外側、`以降` の線は "
          "外側 / 内側 / 内側。含む側の語を空にすると 3 日とも `含む側の語なし` で止まる(3/3)")
    print("[measure] 2 形の外の書き方 5 通り(年度生まれ / 年月日の漢字 / より前 / 日付なし / "
          "暦に無い日)は 5 通りとも `読めない線` で返る")


def test_measure_side_report_on_synthetic_tables() -> None:
    out = C.side(*tables(), "2026-11-18", "1970-01-01")
    got = {x["rule_id"]: x["判定"] for x in out["生年月日の線"]}
    assert got == {"R03": C.SIDE_IN, "R04": C.SIDE_OUT, "R16": C.SIDE_UNREADABLE}
    other = C.side(*tables(), "1999-01-01", "1970-01-01")
    assert other["生年月日の線"] == out["生年月日の線"]
    print("[measure] 生年月日の線は 3 本。生年月日 1970-01-01 の人は R03 で内側、R04 で外側、"
          "R16(年度生まれの形)は `読めない線`。基準日を変えても判定は 3 本とも同じ")


def test_measure_fingerprint_is_stable() -> None:
    rows, lines, symbols, cover = tables()
    fp = C.fingerprint(C.judge(rows, lines, symbols, cover))
    again = [C.fingerprint(C.judge(rows, p, symbols, cover))
             for p in (lines, list(reversed(lines)), lines[1:] + lines[:1],
                       sorted(lines), sorted(lines, reverse=True))]
    assert again == [fp] * 5
    assert fp[:12] == "ba3b890371f5"
    renamed = [[ln[0], f"別の文字 {i}", ln[2], ln[3], ln[4]] for i, ln in enumerate(lines)]
    assert C.fingerprint(C.judge(rows, renamed, symbols, cover)) == fp
    print(f"[measure] 線の台帳の行順を 5 通りに並べて読み直し: 判定部分の sha256 は 5 回とも同じ"
          f"(5/5 一致、先頭 12 桁 {fp[:12]})")
    print("[measure] 線の文字列を 11 行すべて別の文字に入れ替えても sha256 は同じ"
          "(= 語の似かたから記号を当てる経路が無い)")


def test_measure_stops_and_unreadables() -> None:
    rows, lines, symbols, cover = tables()
    broken = {
        C.STOPS[0]: (rows, lines, [], cover),
        C.STOPS[1]: (rows, lines, [[symbols[0][0], symbols[0][1], ""]] + symbols[1:], cover),
        C.STOPS[2]: (rows, lines, symbols, [[cover[0][0], "たぶん収録", cover[0][2]]] + cover[1:]),
        C.STOPS[3]: (rows[:1] + [[rows[1][0], "", "もう要らない", rows[1][3]]] + rows[2:],
                     lines, symbols, cover),
    }
    for reason, t in broken.items():
        out = C.check(*t)
        assert out["ok"] is False and reason in out["止まった理由"]
        assert sum(out["4 値"].values()) + sum(out["別枠"].values()) == 0
        with pytest.raises(C.Stopped):
            C.fingerprint(C.judge(*t))
    unreadable = [
        ([], lines, symbols, cover),
        ([["", "", "", "x"]] + rows, lines, symbols, cover),
        (rows, [["R03", "", "以前", C.SYM_BIRTH, "x"]], symbols, cover),
        (rows, lines, symbols + [symbols[0]], cover),
        (rows, lines, symbols, cover + [cover[0]]),
        (rows, lines, symbols, cover + [["R77", "収録", "x"]]),
    ]
    for t in unreadable:
        with pytest.raises(C.Unreadable):
            C.judge(*t)
    print("[measure] 止まる理由コードは 4 個で、4 通りとも 4 値を 1 件も返さない(4/4)。"
          "表として読めない崩し方 6 通りは 6 通りとも例外で止まる(6/6)")


def test_measure_no_forbidden_calls_in_the_tool() -> None:
    tree = ast.parse((ROOT / "cohort_close.py").read_text(encoding="utf-8"))
    mods = sorted({a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)
                   for a in n.names}
                  | {n.module.split(".")[0] for n in ast.walk(tree)
                     if isinstance(n, ast.ImportFrom) and n.module})
    assert mods == ["__future__", "argparse", "csv", "datetime", "hashlib", "json", "pathlib",
                    "re", "sys"]
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | \
            {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    banned = {"eval", "exec", "float", "round", "today", "now", "time", "subprocess", "random",
              "urlopen", "socket", "mean"}
    assert names & banned == set()
    assert len(C.NOT_HELD) == 10
    print("[measure] 部品が import している module は 9 個で、eval / exec / float / round / "
          "現在時刻 / subprocess / random / 通信 / 平均 の呼び出しは 0 件。"
          "出力の末尾の「持たせていないもの」は 10 行")


# ---------------------------------------------------------------- ふつうの試験

def test_each_rule_gets_the_expected_value() -> None:
    got = values(C.judge(*tables()))
    assert got == {
        "R01": A, "R02": A, "R03": B, "R04": B, "R05": B, "R06": CC, "R07": B, "R08": D,
        "R09": D, "R10": C.EXTRAS[3], "R11": C.EXTRAS[1], "R12": C.EXTRAS[2],
        "R13": C.EXTRAS[0], "R14": C.EXTRAS[4], "R15": B, "R16": B}


def test_coverage_never_changes_the_value() -> None:
    rows, lines, symbols, cover = tables()
    before = values(C.judge(rows, lines, symbols, cover))
    for state in C.STATES:
        flipped = [[c[0], state, c[2]] for c in cover]
        assert values(C.judge(rows, lines, symbols, flipped)) == before


def test_none_note_with_a_line_is_also_an_extra() -> None:
    rows, lines, symbols, cover = tables()
    rows2 = [[r[0], r[1], C.NONE_NOTE if r[0] == "R03" else r[2], r[3]] for r in rows]
    assert values(C.judge(rows2, lines, symbols, cover))["R03"] == C.EXTRAS[4]


def test_inputs_are_not_rewritten() -> None:
    t = tables()
    keep = copy.deepcopy(t)
    C.report(*t)
    C.verify(*t)
    C.side(*t, "2026-11-18", "1970-01-01")
    assert t == keep


def test_cli_exit_codes(tmp_path, capsys) -> None:
    args = [str(FX / n) for n in ("rows_a.csv", "lines_a.csv", "symbols_a.csv", "coverage_a.csv")]
    assert C.main(["check", *args]) == 3          # 別枠が在る
    assert C.main(["verify", *args]) == 0
    assert C.main(["side", *args, "2026-11-18", "1970-01-01"]) == 0
    assert C.main(["side", *args, "2026-11-18", "1970/01/01"]) == 2
    assert C.main(["init", str(tmp_path / "t")]) == 0
    t = [str(tmp_path / "t" / n) for n in ("rows.csv", "lines.csv", "symbols.csv", "coverage.csv")]
    assert C.main(["check", *t]) == 3             # ひな型の線は台帳に無い rule id を指している
    (tmp_path / "bad.csv").write_text("x,y\n1,2\n", encoding="utf-8")
    assert C.main(["check", str(tmp_path / "bad.csv"), *args[1:]]) == 2
    out = capsys.readouterr().out
    assert "表として読めない" in out
    json.loads(out[out.index("{"):out.index("\n}") + 2])
