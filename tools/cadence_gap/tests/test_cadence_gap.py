"""cadence_gap のテスト。合成 fixture は `fixtures/` に commit 済(実データ・実在の値は入れない)。

test_measure_* が記事に載せた数値の出どころで、assert で固定している(値が変われば記事も変える前提)。
測っているものは 7 つある。

  (1) 問い 9 件が 6 値に分かれ、3 つの分母の内訳が付く側
  (2) **鮮度候補 8 件のうち、日数まで出せたのは 5 件だけ**という側
  (3) **走った最後の日が 2 日前なのに、中身が動いた最後の日は 47 日前**という側。= 記事の骨
  (4) 走ったが中身は動いていない実行 4 件のうち、3 件がその数表の最後の実行である側
  (5) 同じ履歴でも基準日を替えると判定が変わる側(基準日が入力であることの実測)
  (6) 最後の実行を落ちた回に替えると、宣言どおりが動く問いの数だけ遅れているへ移る側
  (7) 中身が動いた件数を 0 に替えると、3 つの日付のうち 1 つだけが戻る側

(1) の 6 値は、テストの側でも 3 枚の表の行から直に組み立てて確かめている(部品の judge /
six を呼ばず、fixture の行から別に分類する)。
"""
from __future__ import annotations

import ast
import hashlib
import io
import sys
import tokenize
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIX = ROOT / "fixtures"
PLAN = ROOT.parent.parent          # 07_記事化商品化計画(出典の行を開くため)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FIX))
import cadence_gap as H  # noqa: E402
import make_fixtures as M  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの -> その行に在るはずの語
REAL_SOURCES = {
    M.SRC_LEDGER: "更新 1 回を台帳 1 行",
    M.SRC_CENSUS: "走らなかった",
}

# 形容の語(出力にも実装にも持たせない = 数値が無いなら多寡を書かない)
KEIYOU = ("多い", "少ない", "ほとんど", "かなり", "著しく", "急いで")

# 評価の語(出力に持たせない = 遅れの理由も是非も返さない。B5 の禁則の物理形)
HYOUKA = ("怠慢", "怠け", "放置", "サボ", "ずぼら", "いい加減", "ひどい", "だらしな")

# 持たせていない経路の名前(動く側のコードに 1 つも無いことを見る)
MOTANAI = ("eval", "exec", "網羅", "おすすめ", "推奨", "既定の周期", "とりあえず",
           "だいたい", "正しい方", "達成率", "許容誤差", "優先順位", "自動で登録")


def path_of(name: str) -> Path:
    return FIX / "kowashita" / f"{name[2:]}.csv" if name.startswith("K:") \
        else FIX / f"{name}.csv"


def pull(s: str = "sengen_a", r: str = "rireki_a", t: str = "toi_a") -> H.Tally:
    return H.cadence_gap(H.Declarations.load(path_of(s)), H.Runs.load(path_of(r)),
                         H.Questions.load(path_of(t)))


def three() -> tuple[H.Declarations, H.Runs, H.Questions]:
    return (H.Declarations.load(path_of("sengen_a")),
            H.Runs.load(path_of("rireki_a")),
            H.Questions.load(path_of("toi_a")))


def reasons_of(t: H.Tally) -> set[str]:
    return {p.reason for p in t.report.pending}


def judged_of(t: H.Tally, table_id: str, asof: str) -> H.Judged:
    return next(j for j in t.judged if j.question.key == f"{table_id}@{asof}")


# ---------------------------------------------------------------- 別実装(テスト側)

def expect_six() -> dict[str, int]:
    """3 枚の行から 6 値を別に数える(部品の judge / six / counts を呼ばない)。"""
    cycle = {r[0]: int(r[1]) for r in M.sengen_rows()}
    runs: dict[str, list[list[str]]] = {}
    for r in M.rireki_rows():
        runs.setdefault(r[1], []).append(r)
    six = {k: 0 for k in H.KEKKA}
    for table_id, asof, _source, _swap in M.toi_rows():
        here = sorted(runs.get(table_id, []), key=lambda r: (r[2], r[0]))
        upto = [r for r in here if r[2] <= asof]
        moved = [r for r in upto if r[3] == "ok" and int(r[4]) > 0]
        if table_id not in cycle:
            six["宣言が無い"] += 1
        elif not here:
            six["履歴が無い"] += 1
        elif not upto:
            six["基準日より前の実行が無い"] += 1
        elif not moved:
            six["一度も動いていない"] += 1
        else:
            gap = H.day_number(asof) - H.day_number(moved[-1][2])
            six["遅れている" if gap > cycle[table_id] else "宣言どおり"] += 1
    return six


# ---------------------------------------------------------------- 記事に載せた数値

def test_measure_9_questions_split_into_six() -> None:
    """(1) 問い 9 件が 6 値に分かれ、3 つの分母の内訳が付く。"""
    t = pull()
    assert t.report.ok and t.report.pending == ()
    c = t.counts()
    assert c["周期の宣言表の行数"] == 5
    assert c["実行の履歴表の行数"] == 11
    assert c["問いの数"] == 9 and t.question_denominator() == 9
    assert c["分母(鮮度候補の数)"] == 8 and c["分母(別枠の数)"] == 1
    assert c["6 値"] == {"宣言どおり": 3, "遅れている": 2, "一度も動いていない": 1,
                         "履歴が無い": 1, "宣言が無い": 1,
                         "基準日より前の実行が無い": 1}
    assert c["6 値"] == expect_six()
    assert sum(c["6 値"].values()) == 9
    assert c["理由別の止まった件数"] == {}
    assert not any(isinstance(v, float) for v in c.values())
    assert not any(str(k).endswith(("率", "割合", "点", "スコア")) for k in c)
    # 履歴の行数と結果の内訳だけは手元の記録と同じ形にそろえてある
    runs = H.Runs.load(path_of("rireki_a"))
    assert len(runs.items) == 11
    assert sum(1 for r in runs.items if r.result == "ok") == 9
    assert sum(1 for r in runs.items if r.result == "failed") == 2
    print(f"[measure] sengen_a / rireki_a / toi_a: 宣言 5 行 / 履歴 11 行"
          f"(ok 9 / 落ちた回 2)/ 問い 9 件 → 6 値 {c['6 値']}")
    print("[measure] 分母は 問いの数 9 / 鮮度候補 8 / 別枠 1 の 3 つ"
          "(別枠 1 件 = 基準日より後の実行しか無い数表)")


def test_measure_only_5_of_8_get_a_day_count() -> None:
    """(2) 鮮度候補 8 件のうち、日数まで出せたのは 5 件だけ。"""
    t = pull()
    six = t.six()
    assert t.denominator == 8
    assert t.dated_count() == 5 == sum(six[k] for k in H.HIZUKE)
    assert t.moved_date_count() == 5 == t.dated_count()
    assert sum(six[k] for k in H.KEKKA[2:5]) == 3
    assert t.dated_count() + 3 == t.denominator == 8
    # 日数が出た 5 件は、どれも中身が動いた最後の日を持つ
    dated = [j for j in t.judged if j.dated]
    assert len(dated) == 5
    assert all(j.moved_last and j.gap_days is not None for j in dated)
    assert all(j.over_days is not None for j in dated)
    # 日数が出なかった 3 件は、中身が動いた最後の日を 1 つも持たない
    rest = [j for j in t.judged if j.candidate and not j.dated]
    assert len(rest) == 3
    assert all(not j.moved_last and j.gap_days is None for j in rest)
    print("[measure] 鮮度候補 8 件のうち、日数まで出せたのは 5 件(宣言どおり 3 + "
          "遅れている 2)。残る 3 件は 一度も動いていない 1 + 履歴が無い 1 + "
          "宣言が無い 1 で、空き日数の欄は空のまま返る")
    print("[measure] 日数まで出せた 5 件 = 中身が動いた最後の日が在る問い 5 件"
          "(別の経路で数えた 2 つの数が合う)")


def test_measure_ran_two_days_ago_but_moved_47_days_ago() -> None:
    """(3) 走った最後の日は 2 日前、中身が動いた最後の日は 47 日前。= 記事の骨。"""
    t = pull()
    j = judged_of(t, "D2", "2026-05-20")
    assert j.result == "遅れている"
    assert j.ran_last == "2026-05-18"
    assert j.ok_last == "2026-05-18"
    assert j.moved_last == "2026-04-03"
    assert j.gap_days == 47 and j.over_days == 40
    # 走った最後の日から数えると、宣言された周期の内側に見える
    assert H.day_number("2026-05-20") - H.day_number(j.ran_last) == 2
    assert 2 < H.Declarations.load(path_of("sengen_a")).of("D2").cycle_days == 7
    assert j.ran_last != j.moved_last
    print("[measure] D2 を基準日 2026-05-20 で見ると、走った最後の日は 2 日前"
          "(2026-05-18)で宣言された周期 7 日の内側だが、中身が動いた最後の日は "
          "47 日前(2026-04-03)で、超過日数は 40 日")
    print("[measure] 3 つの日付のうち 走った最後の日 と 落ちた回を除いた最後の日 は"
          "どちらも 2026-05-18 で同じ。1 つの「最終実行」に潰すと、この問いは"
          "宣言どおりに見える")


def test_measure_three_of_four_zero_runs_are_the_latest() -> None:
    """(4) 走ったが中身は動いていない実行 4 件のうち、3 件がその数表の最後の実行。"""
    t = pull()
    rows = t.ran_but_not_moved()
    assert len(rows) == 4 == t.counts()["走ったが中身は動いていない実行"]
    assert [r["実行 id"] for r in rows] == ["R202", "R302", "R501", "R204"]
    assert all(r["中身が動いた件数"] == 0 for r in rows)
    assert all(r["出典"] for r in rows)
    latest = [r for r in rows if r["その数表の最後の実行か"] == "そう"]
    assert len(latest) == 3
    assert [r["実行 id"] for r in latest] == ["R302", "R501", "R204"]
    print("[measure] 走ったが中身は動いていない実行は 4 件で、そのうち 3 件は"
          "その数表の最後の実行(= 「最終実行」の名前で鮮度の答えになっていた回)")
    print("[measure] 一覧に残るのは 実行 id / 数表 id / 実行日 / 指紋 / 出典 で、"
          "そのまま確かめにいく行の名前になる")


def test_measure_same_history_different_asof() -> None:
    """(5) 同じ履歴でも基準日を替えると判定が変わる(基準日が入力であることの実測)。"""
    t = pull()
    rows = [judged_of(t, "D1", d) for d in
            ("2026-05-16", "2026-05-20", "2026-06-01")]
    assert [j.result for j in rows] == ["宣言どおり", "宣言どおり", "遅れている"]
    assert [j.gap_days for j in rows] == [1, 5, 17]
    assert [j.over_days for j in rows] == [0, 0, 10]
    # 3 件とも 3 つの日付は同じ(履歴は 1 つ、動いたのは基準日だけ)
    assert {(j.ran_last, j.moved_last, j.ok_last) for j in rows} == \
        {("2026-05-15", "2026-05-15", "2026-05-15")}
    print("[measure] 同じ数表 D1 を 3 つの基準日できくと、空き日数は 1 / 5 / 17 日、"
          "超過日数は 0 / 0 / 10 日で、判定は 宣言どおり / 宣言どおり / 遅れている。"
          "3 つの日付はどれも同じで、動いたのは基準日だけ")


def test_measure_failed_run_moves_the_count() -> None:
    """(6) 最後の実行を落ちた回に替えると、宣言どおりが動く問いの数だけ移る。"""
    decls, runs, questions = three()
    first = H.cadence_gap(decls, runs, questions)
    probe = H.result_probe(decls, runs, questions, first)
    assert probe["合うか"] is True
    assert len(probe["行ごと"]) == 1
    row = probe["行ごと"][0]
    assert row["替えた実行 id"] == "R103" and row["1 つ前に動いた実行"] == "R102"
    assert row["動く問い"] == ["D1@2026-05-16", "D1@2026-05-20"]
    assert row["宣言どおり"] == "3 → 1" and row["遅れている"] == "2 → 4"
    assert row["超過日数"] == ["0 → 1", "0 → 5"]
    assert row["ほかの数表で動いた問い"] == []
    after = H.cadence_gap(decls, runs.with_result("R103", "failed"), questions)
    mine = judged_of(after, "D1", "2026-05-20")
    assert mine.result == "遅れている"
    assert mine.ran_last == "2026-05-15"          # 走った最後の日は動かない
    assert mine.moved_last == "2026-05-08"        # 落ちた回は更新に数えない
    assert mine.ok_last == "2026-05-08"
    assert mine.over_days == 5 and after.denominator == first.denominator == 8
    print("[measure] R103 を落ちた回に替えると、D1 の基準日 2 件が同時に移って"
          "宣言どおり 3 → 1、遅れている 2 → 4(ほかの 4 値とほかの数表の件数は動かない)")
    print("[measure] 替えた後の中身が動いた最後の日は 1 つ前に動いた実行 R102 の "
          "2026-05-08 で、落ちた回を除いた最後の日も同じ日に戻る。走った最後の日 "
          "2026-05-15 だけは動かない")


def test_measure_zero_diff_moves_only_one_of_three_dates() -> None:
    """(7) 中身が動いた件数を 0 に替えると、3 つの日付のうち 1 つだけが戻る。"""
    decls, runs, questions = three()
    first = H.cadence_gap(decls, runs, questions)
    probe = H.moved_probe(decls, runs, questions, first)
    assert probe["合うか"] is True
    assert len(probe["行ごと"]) == 1
    row = probe["行ごと"][0]
    assert row["替えた実行 id"] == "R103"
    assert row["宣言どおり"] == "3 → 1" and row["遅れている"] == "2 → 4"
    assert row["空き日数"] == ["1 → 8", "5 → 12"]
    assert row["走った最後の日"] == "2026-05-15 → 2026-05-15"
    assert row["落ちた回を除いた最後の日"] == "2026-05-15 → 2026-05-15"
    assert row["中身が動いた最後の日"] == "2026-05-15 → 2026-05-08"
    after = H.cadence_gap(decls, runs.with_moved("R103", 0), questions)
    mine = judged_of(after, "D1", "2026-05-20")
    assert mine.result == "遅れている" and mine.gap_days == 12
    assert (mine.ran_last, mine.ok_last) == ("2026-05-15", "2026-05-15")
    assert mine.moved_last == "2026-05-08"
    print("[measure] R103 の中身が動いた件数を 0 に替えると、空き日数は 1 → 8 日 と "
          "5 → 12 日 に増え、宣言どおり 3 → 1、遅れている 2 → 4。走った最後の日と"
          "落ちた回を除いた最後の日はどちらも 2026-05-15 のまま動かない")
    print("[measure] 落ちた回に替えた写しとの違いはここで出る。あちらは 3 つの日付の"
          "うち 2 つが戻り、こちらは 1 つだけが戻る")


def test_measure_count_and_fingerprint_clash() -> None:
    """件数と指紋が食い違う実行を 2 種類に分けて並べ、どちらが正とも決めない。"""
    t = pull()
    rows = t.clashes()
    assert len(rows) == 2 == t.counts()["件数と指紋が食い違う実行"]
    assert [r["種類"] for r in rows] == list(H.CLASH)[::-1]
    assert {r["種類"] for r in rows} == set(H.CLASH)
    assert [r["実行 id"] for r in rows] == ["R102", "R204"]
    for r in rows:
        assert r["1 つ前の ok の実行"] and r["出典"]
    flat = str(rows)
    for word in ("正", "直すべき", "優先", "どちらか"):
        assert word not in flat, word
    print("[measure] 件数と指紋が食い違う実行は 2 件で、2 種類が 1 件ずつ"
          "(中身が動いたのに指紋が変わっていない / 差分 0 なのに指紋が変わった)。"
          "どちらを直すべきかを返す欄は出力に 0 件")


def test_measure_next_change_stays_in_its_own_list() -> None:
    """次回改定の近さは別枠で、鮮度の列にも 6 値にも入らない。"""
    t = pull()
    rows = t.next_changes()
    assert len(rows) == 3
    assert {r["数表 id"] for r in rows} == {"D1"}
    assert [r["基準日からの日数"] for r in rows] == [46, 42, 30]
    assert all(r["次回改定の予定"] == "2026-07-01" and r["出典"] for r in rows)
    for row in t.dates():
        assert "次回改定" not in str(row)
    assert "次回改定" not in str(t.six())
    print("[measure] 次回改定の予定を持つ数表は 1 つで、その 3 件の問いは別枠に出る"
          "(基準日からの日数は 46 / 42 / 30 日)。3 つの日付の一覧と 6 値に"
          "「次回改定」の語は 0 件")


def test_measure_counts_add_up_and_bytes_repeat() -> None:
    """2 回 + 3 枚の行順を入れ替えて読み直しても判定部分のバイト列が同じで、件数が合う。"""
    out = H.verify(*three())
    assert out["ok"] is True
    assert out["sha256"] == out["2 回目の sha256"] == out["入れ替えた 3 枚の sha256"]
    assert out["sha256"].startswith("41cacc0e689d")
    check = out["件数の検算"]
    assert check["6 値の合計"] == 9 == check["分母(問いの数)"]
    assert check["5 値"] == 8 == check["分母(鮮度候補の数)"]
    assert check["数表ごとの内訳の合計"] == 9
    assert check["日数まで出せた"] == 5 == check["中身が動いた最後の日が在る問い"]
    assert check["分母(別枠の数)"] == 1
    print("[measure] 2 回 + 3 枚の行順を逆順に入れ替えて読み直し: 判定部分の sha256 は"
          f" 3 回とも同じ(3/3 一致、先頭 12 桁 {out['sha256'][:12]})")
    print("[measure] 件数の検算: 6 値の合計 9 = 問いの数 9、5 値 8 = 鮮度候補 8、"
          "数表ごとの内訳の合計 9 = 問いの数、日数まで出せた 5 = 中身が動いた最後の日が"
          "在る問い 5(4 通りの数え方が合う)")


def test_measure_six_tables_add_up() -> None:
    """数表 6 つの内訳の合計が全体に戻る(二重集計の検算)。"""
    t = pull()
    rows = t.by_table()
    assert [r["数表 id"] for r in rows] == ["D1", "D2", "D3", "D4", "D5", "D6"]
    assert [r["問いの数"] for r in rows] == [3, 2, 1, 1, 1, 1]
    assert [r["鮮度候補"] for r in rows] == [3, 2, 1, 1, 1, 0]
    assert [r["日数まで出せた"] for r in rows] == [3, 2, 0, 0, 0, 0]
    assert [r["履歴の行数"] for r in rows] == [3, 4, 2, 0, 1, 1]
    assert [r["宣言された周期(日)"] for r in rows] == [7, 7, 30, 7, "", 7]
    assert sum(int(r["問いの数"]) for r in rows) == 9
    assert sum(int(r["履歴の行数"]) for r in rows) == 11
    for k in H.KEKKA:
        assert sum(int(r["6 値"][k]) for r in rows) == t.six()[k]
    print("[measure] 数表は 6 つで、問いの数は 3 / 2 / 1 / 1 / 1 / 1、履歴の行数は "
          "3 / 4 / 2 / 0 / 1 / 1、日数まで出せたのは 3 / 2 / 0 / 0 / 0 / 0")
    print("[measure] 数表ごとの内訳の合計 9 = 問いの数 9、履歴の行数の合計 11 = "
          "履歴表の行数 11(2 通りの数え方が合う)")


def test_measure_no_clock_and_no_float() -> None:
    """判定部分に環境が入らない。時計を読む経路も、評価の語も持たない。"""
    src = (ROOT / "cadence_gap.py").read_text(encoding="utf-8")
    skip = {tokenize.STRING, tokenize.COMMENT} | {
        getattr(tokenize, n) for n in ("FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END")
        if hasattr(tokenize, n)}
    code = "".join(t.string for t in
                   tokenize.generate_tokens(io.StringIO(src).readline)
                   if t.type not in skip)
    for word in ("now(", "today(", "time(", "float(", "eval(", "exec(", "round(",
                 "subprocess", "random", "platform", "datetime", "urllib",
                 "requests", "socket"):
        assert word not in code, word
    tree = ast.parse(src)
    imported = sorted({n.names[0].name.split(".")[0] for n in ast.walk(tree)
                       if isinstance(n, ast.Import)}
                      | {n.module.split(".")[0] for n in ast.walk(tree)
                         if isinstance(n, ast.ImportFrom) and n.module})
    assert imported == ["__future__", "argparse", "csv", "dataclasses", "hashlib",
                        "json", "pathlib", "sys"]
    for word in KEIYOU + MOTANAI:
        assert word not in code, word
    for word in HYOUKA:              # 評価の語は文字列も含めて 1 つも持たない
        assert word not in src, word
    t = pull()
    body = t.judgement_bytes().decode("utf-8")
    assert str(FIX) not in body and "読んだ条件" not in body
    print(f"[measure] 部品が import している module は {len(imported)} 個で、"
          "現在時刻を読む呼び出し・float / eval / exec / round / subprocess / "
          "random / platform / 通信の呼び出しは 0 件(時計を読む経路も、原文を"
          "取りに行く経路も無い)")
    print(f"[measure] 評価の語 {len(HYOUKA)} 個は文字列も含めて 0 件、形容の語 "
          f"{len(KEIYOU)} 個と持たせていない経路の語 {len(MOTANAI)} 個は動く側の"
          "コードに 0 件。判定部分のバイト列に絶対パスは入らない")


def test_measure_day_number_reads_no_clock() -> None:
    """日付は文字列から整数の通算日に直すだけ(同じ入力なら何日後でも同じ答え)。"""
    assert H.day_number("2026-05-20") - H.day_number("2026-05-15") == 5
    assert H.day_number("2026-05-20") - H.day_number("2026-04-03") == 47
    assert H.day_number("2026-06-01") - H.day_number("2026-05-15") == 17
    assert H.day_number("2026-03-01") - H.day_number("2026-02-28") == 1
    assert H.day_number("2024-03-01") - H.day_number("2024-02-29") == 1
    assert H.day_number("2024-03-01") - H.day_number("2024-02-28") == 2
    assert H.day_number("2027-01-01") - H.day_number("2026-01-01") == 365
    assert H.day_number("2025-01-01") - H.day_number("2024-01-01") == 366
    for bad in ("2026-02-30", "2026-13-01", "2026-5-20", "2026/05/20", "", "きょう"):
        with pytest.raises(H.ReadError):
            H.day_number(bad)
    print("[measure] 日付は整数の通算日に直すだけで、閏日をまたぐ差も 1 日 / 2 日 と"
          "合う(2024-02-28 → 03-01 が 2 日、2026-02-28 → 03-01 が 1 日)。"
          "1 年は 365 日 / 366 日 の 2 通りで、月や日の形が違う 6 通りは読めない")


def read_kowashita(name: str) -> tuple[str, set[str]]:
    """崩した表 1 枚を基準の 3 枚に差し込んで読む。返るのは 読み方 と 理由コードの集合。"""
    args = {"sengen": "sengen_a", "rireki": "rireki_a", "toi": "toi_a"}
    args[name.split("_")[0]] = f"K:{name}"
    try:
        t = pull(s=args["sengen"], r=args["rireki"], t=args["toi"])
    except H.ReadError:
        return "表として読めない", set()
    if not t.report.ok:
        return "1 件も数えずに止まった", reasons_of(t)
    return "読んだ", set(t.stopped())


def test_measure_stop_reason_codes_all_reachable(monkeypatch) -> None:
    """止まる理由コード 11 個すべてに道がある(崩した表 + 差し替えた実装)。"""
    assert pull().report.pending == ()      # 基準の 3 枚は 1 行も止まらない
    seen: set[str] = set()
    group: dict[str, list[str]] = {}
    for name in M.kowashita():
        how, codes = read_kowashita(name)
        seen |= codes
        group.setdefault(how, []).append(name)
    assert {k: len(v) for k, v in sorted(group.items())} == {
        "1 件も数えずに止まった": 11, "表として読めない": 21, "読んだ": 1}
    assert group["読んだ"] == ["toi_swap_nashi"]
    assert seen == set(H.TABLE_REASONS)
    with pytest.raises(H.ReadError):
        H.verify(H.Declarations.load(path_of("sengen_a")),
                 H.Runs.load(path_of("rireki_a")),
                 H.Questions.load(path_of("K:toi_swap_nashi")))

    decls, runs, questions = three()
    count = {"n": 0}

    def flaky(self) -> str:            # 2 回目で違うバイト列を出す実装に差し替える
        count["n"] += 1
        return f"{count['n']:064d}"

    monkeypatch.setattr(H.Tally, "sha256", flaky)
    out = H.verify(decls, runs, questions)
    seen |= {p["理由コード"] for p in out["pending"]}
    monkeypatch.undo()
    monkeypatch.setattr(H.Tally, "six", lambda self: {k: 0 for k in H.KEKKA})
    out2 = H.verify(decls, runs, questions)
    seen |= {p["理由コード"] for p in out2["pending"]}
    assert seen == set(H.STOP_REASONS)
    assert len(H.STOP_REASONS) == 11
    print("[measure] 止まる理由コード 11 個すべてに道がある(崩した表 11 枚で 8 個 + "
          "差し替えた実装 2 本で 3 個)")
    print("[measure] 崩した表 33 枚の内訳 = 表として読めない 21 枚 / 1 件も数えずに"
          "止まる 11 枚 / 読めて verify だけが止まる 1 枚"
          "(「表として読めない」は理由コードに混ぜない)")


def test_broken_table_never_lands_in_the_six() -> None:
    """この部品の「読めない」を、測っている相手の「履歴が無い」の欄に入れない。"""
    t = pull(s="K:sengen_shutten_nashi")
    assert not t.report.ok and t.judged == ()
    c = t.counts()
    assert c["6 値"] == {k: 0 for k in H.KEKKA}
    assert c["読んだか"].startswith("読んでいない")
    assert reasons_of(t) == {"出典の欄が空"}
    for call in (t.judgement_bytes, t.sha256):
        with pytest.raises(RuntimeError):
            call()
    print("[measure] 出典の欄が空の宣言を 1 行混ぜると 6 値は全て 0 で、理由コード"
          "だけが返る(相手の「履歴が無い」の欄に、この部品の「読めない」が混ざらない)")


def test_inputs_are_never_written() -> None:
    """読む前と後で、入力に置いた全ファイルの sha256 が変わらない。"""
    files = sorted(p for p in FIX.rglob("*.csv"))
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    t = pull()
    H.verify(*three())
    (t.counts(), t.by_table(), t.listed(), t.dates(), t.ran_but_not_moved(),
     t.clashes(), t.next_changes(), t.sha256())
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    assert before == after
    print(f"[measure] 読む前後で入力 {len(files)} ファイルの sha256 が同じ(verify が作る"
          "写しはメモリの中だけで、表には書かない)")


def test_real_sources_point_at_lines_that_exist() -> None:
    """fixture の出典のうち repo 内の実在の行を指すものは、その行に語が在る。"""
    for source, word in REAL_SOURCES.items():
        path, line = source.rsplit(" L", 1)
        text = (PLAN / path).read_text(encoding="utf-8").splitlines()[int(line) - 1]
        assert word in text, source
    print(f"[measure] fixture の出典のうち repo 内の実在の行を指すもの"
          f" {len(REAL_SOURCES)} 件は、その行に語が在ることをテストで確かめている")


def test_listed_keeps_every_question_once() -> None:
    """判定ごとの一覧に、問いが 1 件ずつちょうど 1 回出る。"""
    t = pull()
    listed = t.listed()
    assert [x["判定"] for x in listed] == list(H.KEKKA)
    keys = [(q["数表 id"], q["基準日"]) for x in listed for q in x["問い"]]
    assert len(keys) == 9 and len(set(keys)) == 9
    assert sum(int(x["件数"]) for x in listed) == 9
    assert len(t.dates()) == 9


def test_cli_has_four_subcommands_and_no_options() -> None:
    """CLI は cadence / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = H.build_parser()
    sub = next(a for a in ap._actions if a.choices)
    assert tuple(sub.choices) == H.SUBCOMMANDS == ("cadence", "check", "verify", "init")
    for name, parser in sub.choices.items():
        flags = [o for a in parser._actions for o in a.option_strings]
        assert flags == ["-h", "--help"], (name, flags)


def test_cli_exit_codes(tmp_path, capsys) -> None:
    """別枠や止まった行が残れば 3、表として読めなければ 2、ひな型は 0。"""
    args = [str(FIX / "sengen_a.csv"), str(FIX / "rireki_a.csv"),
            str(FIX / "toi_a.csv")]
    assert H.main(["check", *args]) == 3
    assert H.main(["cadence", *args]) == 3
    assert H.main(["verify", *args]) == 0          # verify は検算が合えば 0
    broken = [str(FIX / "kowashita" / "sengen_0gyou.csv"), *args[1:]]
    assert H.main(["check", *broken]) == 2
    assert H.main(["init", str(tmp_path / "ひな型")]) == 0
    made = sorted(p.name for p in (tmp_path / "ひな型").iterdir())
    assert set(made) == {"周期の宣言.csv", "実行の履歴.csv", "問いの一覧.csv"}
    out = capsys.readouterr().out
    assert "点数も割合も返さない" in out


def test_init_template_shows_two_values(tmp_path) -> None:
    """ひな型の 3 枚は、そのまま読めて、遅れていると一度も動いていないが 1 件ずつ出る。"""
    paths = H.init(tmp_path / "ひな型")
    t = H.cadence_gap(H.Declarations.load(paths[0]), H.Runs.load(paths[1]),
                      H.Questions.load(paths[2]))
    assert t.report.ok and t.question_denominator() == 2 and t.denominator == 2
    assert t.six() == {"宣言どおり": 0, "遅れている": 1, "一度も動いていない": 1,
                       "履歴が無い": 0, "宣言が無い": 0,
                       "基準日より前の実行が無い": 0}
    assert t.aside_denominator() == 0 and t.stopped() == {}


def test_runs_after_the_asof_are_never_used() -> None:
    """基準日より後の実行は 3 つの日付のどれにも入らない。"""
    t = pull()
    j = judged_of(t, "D6", "2026-05-20")
    assert j.result == "基準日より前の実行が無い"
    assert (j.ran_last, j.moved_last, j.ok_last) == ("", "", "")
    assert j.candidate is False and j.gap_days is None
    runs = H.Runs.load(path_of("rireki_a"))
    assert len(runs.of("D6")) == 1 and runs.of("D6")[0].ran_on == "2026-06-10"
    assert runs.upto("D6", H.day_number("2026-05-20")) == ()
    print("[measure] D6 の履歴は 1 行あるが実行日が基準日より後なので、3 つの日付は"
          "どれも空で、鮮度候補の分母にも入らない(外した件数は別枠に出る)")


def test_no_default_cycle_for_undeclared_table() -> None:
    """宣言が無い数表に、ほかの数表の周期を当てない。"""
    t = pull()
    j = judged_of(t, "D5", "2026-05-20")
    assert j.result == "宣言が無い"
    assert j.ran_last == "2026-05-12" and j.moved_last == ""
    assert j.gap_days is None and j.over_days is None
    decls = H.Declarations.load(path_of("sengen_a"))
    assert decls.of("D5") is None
    assert {d.cycle_days for d in decls.items} == {7, 30}
    print("[measure] 宣言が無い数表 D5 は、ほかの数表の周期(7 日 / 30 日)を借りずに"
          "「宣言が無い」に出る。走った最後の日は出るが、空き日数の欄は空のまま")
