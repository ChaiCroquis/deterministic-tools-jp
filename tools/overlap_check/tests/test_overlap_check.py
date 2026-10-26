"""overlap_check のテスト。合成 fixture は `fixtures/` に commit 済(実データ・実在の値は入れない)。

test_measure_* が記事に載せた数値の出どころで、assert で固定している(値が変われば記事も変える前提)。
測っているものは 6 つある。

  (1) 問い 17 件が 7 値 + 止まった 1 件に分かれ、3 つの分母の内訳が付く側
  (2) **重なり候補 15 件のうち、突き合わせが成立したのは 8 件だけ**という側。= 記事の骨
  (3) 年度ペア 4 通りの内訳の合計が全体に戻る側(二重集計の検算)
  (4) **「採用元が同じ欄」2 件は両側の値が同じなので、数え方を間違えると一致が 6 件から
      8 件に見える**側。= 検算に見えて検算になっていない行
  (5) 採用元を今年の変更前から去年の変更後に替えると、件数がちょうど 1 対 1 で移る側
  (6) 寄せ方を 1 組外すと、寄せ方が無いが 1 増えた分だけ一致が 1 減る側

(1) の 7 値は、テストの側でも 4 枚の表の行から直に組み立てて確かめている(部品の judge /
seven を呼ばず、fixture の行から別に分類する)。
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
import overlap_check as H  # noqa: E402
import make_fixtures as M  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの -> その行に在るはずの語
REAL_SOURCES = {
    M.SRC_CROSS: "片方の経路にしか無い",
    M.SRC_ANSWER: "塊に無い",
}

# 形容の語(出力にも実装にも持たせない = 数値が無いなら多寡を書かない)
KEIYOU = ("多い", "少ない", "ほとんど", "かなり", "著しく", "急いで")

# 持たせていない経路の名前(動く側のコードに 1 つも無いことを見る)
MOTANAI = ("eval", "exec", "網羅", "おすすめ", "推奨", "既定値", "とりあえず",
           "だいたい", "正しい方", "一致率", "許容誤差", "優先順位", "自動で寄せる")


def path_of(name: str) -> Path:
    return FIX / "kowashita" / f"{name[2:]}.csv" if name.startswith("K:") \
        else FIX / f"{name}.csv"


def pull(c: str = "chuushutsu_a", y: str = "yose_a", s: str = "saiyou_a",
         t: str = "toi_a") -> H.Tally:
    return H.overlap_check(H.Extracts.load(path_of(c)), H.Bridges.load(path_of(y)),
                           H.Takes.load(path_of(s)), H.Questions.load(path_of(t)))


def four() -> tuple[H.Extracts, H.Bridges, H.Takes, H.Questions]:
    return (H.Extracts.load(path_of("chuushutsu_a")),
            H.Bridges.load(path_of("yose_a")),
            H.Takes.load(path_of("saiyou_a")),
            H.Questions.load(path_of("toi_a")))


def reasons_of(t: H.Tally) -> set[str]:
    return {p.reason for p in t.report.pending}


def judged_of(t: H.Tally, pair: tuple[str, str], item: str) -> H.Judged:
    return next(j for j in t.judged
                if (j.question.year_a, j.question.year_b, j.question.item)
                == (pair[0], pair[1], item))


# ---------------------------------------------------------------- 別実装(テスト側)

def expect_seven() -> dict[str, int]:
    """4 枚の行から 7 値を別に数える(部品の judge / seven / counts を呼ばない)。"""
    cells = {(r[0], r[3], r[2]): (r[4], r[5]) for r in M.chuushutsu_rows()}
    doc_of = {}
    for r in M.chuushutsu_rows():
        doc_of.setdefault(r[1], r[0])
    yose = {r[0]: r[1] for r in M.yose_rows()}
    take = {r[1]: (r[2], r[3]) for r in M.saiyou_rows()}
    seven = {k: 0 for k in H.RESULTS}
    for year_a, year_b, item, _source, _swap in M.toi_rows():
        if year_a == year_b:
            continue                                  # 止まった問いは 7 値に入らない
        doc_a, doc_b = doc_of.get(year_a), doc_of.get(year_b)
        if doc_a is None or doc_b is None:
            seven["資料が手元に無い"] += 1
            continue
        if item not in yose:
            seven["寄せ方が無い"] += 1
            continue
        a = cells.get((doc_a, "変更後", item))
        b = cells.get((doc_b, "変更前", yose[item]))
        if a is None or b is None:
            seven["重なりが無い"] += 1
        elif not a[0] or not b[0] or a[0] != b[0]:
            seven["単位がそろわない"] += 1
        elif take.get(item) == (doc_b, "変更前"):
            seven["採用元が同じ欄"] += 1
        elif a[1] == b[1]:
            seven["一致"] += 1
        else:
            seven["不一致"] += 1
    return seven


# ---------------------------------------------------------------- 記事に載せた数値

def test_measure_17_questions_split_into_seven() -> None:
    """(1) 問い 17 件が 7 値 + 止まった 1 件に分かれ、3 つの分母の内訳が付く。"""
    t = pull()
    assert t.report.ok and t.report.pending == ()
    c = t.counts()
    assert c["抽出表の行数"] == 32
    assert c["名前の寄せ方の表の行数"] == 10
    assert c["採用元の宣言の行数"] == 11
    assert c["問いの数"] == 17 and t.question_denominator() == 17
    assert c["分母(重なり候補の数)"] == 15 and c["分母(別枠の数)"] == 3
    assert c["7 値"] == {"一致": 6, "不一致": 2, "重なりが無い": 2, "寄せ方が無い": 1,
                         "採用元が同じ欄": 2, "単位がそろわない": 2,
                         "資料が手元に無い": 1}
    assert c["7 値"] == expect_seven()
    assert sum(c["7 値"].values()) == 16 and t.halted() == 1
    assert sum(c["7 値"].values()) + t.halted() == 17
    assert c["分母から外した年度"] == ["T0"]
    assert c["理由別の止まった件数"] == {"同じ年度を突き合わせる指定": 1}
    assert not any(isinstance(v, float) for v in c.values())
    assert not any(str(k).endswith(("率", "割合")) for k in c)
    print(f"[measure] chuushutsu_a / yose_a / saiyou_a / toi_a: 抽出表 32 行 / 寄せ方 "
          f"10 組 / 採用元 11 行 / 問い 17 件 → 7 値 {c['7 値']}")
    print("[measure] 分母は 問いの数 17 / 重なり候補 15 / 別枠 3 の 3 つ"
          "(問い 17 件 = 7 値の合計 16 + 同じ年度で止まった 1)")
    print("[measure] 分母から外したのは、止まった問い 1 件と、資料が手元に無い年度 "
          "T0 の 1 件(外した年度を必ず出す)")


def test_measure_only_8_of_15_are_real_cross_checks() -> None:
    """(2) 重なり候補 15 件のうち、突き合わせが成立したのは 8 件。= 記事の骨。"""
    t = pull()
    seven = t.seven()
    done = sum(seven[r] for r in H.TOTSUGOU)
    assert done == 8 == t.counts()["突き合わせが成立した件数"]
    assert sum(seven[r] for r in H.RESULTS[2:6]) == 7
    assert done + 7 == t.denominator == 15
    # 突き合わせが成立した 8 件は、どちらの欄にも値と単位の宣言が在る
    both = [j for j in t.judged if j.result in H.TOTSUGOU]
    assert len(both) == 8
    assert all(j.cell_a and j.cell_b for j in both)
    assert all(j.cell_a.unit == j.cell_b.unit for j in both)
    assert all(j.cell_a.value and j.cell_b.value for j in both)
    print("[measure] 重なり候補 15 件のうち、突き合わせが成立したのは 8 件"
          "(一致 6 + 不一致 2)。残る 7 件は 重なりが無い 2 + 寄せ方が無い 1 + "
          "採用元が同じ欄 2 + 単位がそろわない 2")
    print("[measure] 成立した 8 件は両側に値と単位の宣言が在り、単位は両側で同じ"
          "(片側でも空なら別枠に出るので、この 8 件には入らない)")


def test_measure_four_year_pairs_add_up() -> None:
    """(3) 年度ペア 4 通りの内訳の合計が全体に戻る(二重集計の検算)。"""
    t = pull()
    pairs = t.by_pair()
    assert [row["年度ペア"] for row in pairs] == ["T0 × T1", "T1 × T2", "T2 × T2",
                                                  "T2 × T3"]
    assert [row["問いの数"] for row in pairs] == [1, 8, 1, 7]
    assert [row["重なり候補"] for row in pairs] == [0, 8, 0, 7]
    assert [row["止まった"] for row in pairs] == [0, 0, 1, 0]
    assert [row["突き合わせが成立"] for row in pairs] == [0, 3, 0, 5]
    assert sum(int(row["問いの数"]) for row in pairs) == 17
    assert sum(int(row["重なり候補"]) for row in pairs) == t.denominator == 15
    for r in H.RESULTS:              # 7 値も年度ペアごとの合計が全体に戻る
        assert sum(int(row["7 値"][r]) for row in pairs) == t.seven()[r]
    print("[measure] 年度ペアは 4 通り(T0 × T1 / T1 × T2 / T2 × T2 / T2 × T3)で、"
          "問いの数は 1 / 8 / 1 / 7、重なり候補は 0 / 8 / 0 / 7、突き合わせが成立した"
          "のは 0 / 3 / 0 / 5")
    print("[measure] 年度ペアごとの内訳の合計 17 = 問いの数 17、重なり候補の合計 15 = "
          "分母 15(2 通りの数え方が合う)")


def test_measure_self_checks_would_look_like_matches() -> None:
    """(4) 「採用元が同じ欄」2 件は両側の値が同じ = 数え方を間違えると一致 8 件に見える。"""
    t = pull()
    rows = t.self_checks()
    assert len(rows) == 2 == t.seven()["採用元が同じ欄"]
    assert [r["項目名"] for r in rows] == ["K04", "K03"]
    assert [r["年度ペア"] for r in rows] == ["T1 × T2", "T2 × T3"]
    assert [r["採用元"] for r in rows] == ["S2 / 変更前", "S3 / 変更前"]
    assert all(r["採用元"] == r["経路 B の欄"] for r in rows)
    assert all(r["出典"] for r in rows)
    # 両側の値は同じ(= この 2 件を突合に混ぜると、一致は 6 件ではなく 8 件に見える)
    both = [j for j in t.judged if j.result == "採用元が同じ欄"]
    assert all(j.cell_a.value == j.cell_b.value for j in both)
    assert t.seven()["一致"] + len(both) == 8
    print("[measure] 「採用元が同じ欄」は 2 件(K04 = T1 × T2、K03 = T2 × T3)で、"
          "どちらも採用元が経路 B の欄そのもの。両側の値は同じなので、突合に混ぜると"
          "一致は 6 件ではなく 8 件に見える")
    print("[measure] 一覧には 行 id / 採用元 / 経路 B の欄 / 出典 が残る"
          "(検算に見えて検算になっていない行の名前が、そのまま直す候補になる)")


def test_measure_restating_the_take_moves_exactly_one() -> None:
    """(5) 採用元を今年の変更前 → 去年の変更後 に替えると件数が 1 対 1 で移る。"""
    extracts, bridges, takes, questions = four()
    first = H.overlap_check(extracts, bridges, takes, questions)
    probe = H.take_probe(extracts, bridges, takes, questions, first)
    assert probe["合うか"] is True
    assert len(probe["行ごと"]) == 2
    assert [r["替えた項目名"] for r in probe["行ごと"]] == ["K04", "K03"]
    assert all(r["採用元が同じ欄"] == "2 → 1" for r in probe["行ごと"])
    assert all(r["一致"] == "6 → 7" for r in probe["行ごと"])
    assert [r["動いた年度ペア"] for r in probe["行ごと"]] == ["T1 × T2", "T2 × T3"]
    after = H.overlap_check(extracts, bridges, takes.restated("K04", "S1", "変更後"),
                            questions)
    assert after.seven()["採用元が同じ欄"] == 1 and after.seven()["一致"] == 7
    assert after.denominator == first.denominator == 15
    assert judged_of(after, ("T1", "T2"), "K04").result == "一致"
    assert judged_of(after, ("T2", "T3"), "K04").result == "一致"   # 元から一致
    print("[measure] 「採用元が同じ欄」2 件を 1 件ずつ、採用元を去年の変更後に替えると、"
          "2 通りとも 採用元が同じ欄 が 1 減って 一致 が 1 増える(ほかの 5 値は動かない)")
    print("[measure] 動いた年度ペアは替えた問いのペアだけ(T1 × T2 と T2 × T3 が 1 件ずつ)。"
          "重なり候補の分母 15 は動かない")


def test_measure_dropping_one_bridge_moves_exactly_one() -> None:
    """(6) 寄せ方を 1 組外すと、寄せ方が無いが 1 増えた分だけ一致が 1 減る。"""
    extracts, bridges, takes, questions = four()
    first = H.overlap_check(extracts, bridges, takes, questions)
    probe = H.bridge_probe(extracts, bridges, takes, questions, first)
    assert probe["合うか"] is True
    assert len(probe["行ごと"]) == 2
    assert [r["外した寄せ方"] for r in probe["行ごと"]] == ["K09", "K10"]
    assert all(r["寄せ方が無い"] == "1 → 2" for r in probe["行ごと"])
    assert all(r["一致"] == "6 → 5" for r in probe["行ごと"])
    assert all(r["動いた年度ペア"] == "T2 × T3" for r in probe["行ごと"])
    after = H.overlap_check(extracts, bridges.without("K09"), takes, questions)
    assert judged_of(after, ("T2", "T3"), "K09").result == "寄せ方が無い"
    assert judged_of(after, ("T2", "T3"), "K09").cell_a is None   # 比べに行かない
    print("[measure] 寄せ方の表から 1 組(K09 / K10)を外すと、2 通りとも 寄せ方が無い が "
          "1 増えて 一致 が 1 減る。ほかの年度ペアの件数は動かない")
    print("[measure] 外した項目は比べに行かない(両側の欄を持たないまま「寄せ方が無い」に"
          "出る)。K09 は年度で名前が揺れる組(K09 → K09x)で、宣言を外すと寄せられない")


def test_measure_counts_add_up_and_bytes_repeat() -> None:
    """2 回 + 4 枚の行順を入れ替えて読み直しても判定部分のバイト列が同じで、件数が合う。"""
    out = H.verify(*four())
    assert out["ok"] is True
    assert out["sha256"] == out["2 回目の sha256"] == out["入れ替えた 4 枚の sha256"]
    assert out["sha256"].startswith("c79ae282fe49")
    check = out["件数の検算"]
    assert check["7 値の合計"] == 16 and check["止まった問い"] == 1
    assert check["5 値 + 単位がそろわない"] == 15 == check["分母(重なり候補の数)"]
    assert check["年度ペアごとの内訳の合計"] == 17 == check["分母(問いの数)"]
    assert check["分母(別枠の数)"] == 3
    print("[measure] 2 回 + 4 枚の行順を逆順に入れ替えて読み直し: 判定部分の sha256 は"
          f" 3 回とも同じ(3/3 一致、先頭 12 桁 {out['sha256'][:12]})")
    print("[measure] 件数の検算: 7 値の合計 16 + 止まった 1 = 問いの数 17、"
          "5 値 13 + 単位がそろわない 2 = 重なり候補 15、年度ペアごとの内訳の合計 17 = "
          "問いの数 17(3 通りの数え方が合う)")


def test_measure_no_clock_and_no_float() -> None:
    """判定部分に環境が入らない。値を計算する経路も、正を決める経路も持たない。"""
    src = (ROOT / "overlap_check.py").read_text(encoding="utf-8")
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
    t = pull()
    body = t.judgement_bytes().decode("utf-8")
    assert str(FIX) not in body and "読んだ条件" not in body
    print(f"[measure] 部品が import している module は {len(imported)} 個で、float / "
          "eval / exec / round / subprocess / random / platform / datetime / 通信の"
          "呼び出しは 0 件(値を計算する経路も、原文を取りに行く経路も無い)")
    print("[measure] 判定部分のバイト列に絶対パスは入らない(読んだ条件は別の欄)。"
          "形容の語 6 つと、持たせていない経路の語 13 個は動く側のコードに 0 件")


def test_measure_mismatch_shows_both_sides_and_picks_neither() -> None:
    """不一致は両側の値と出典を並べるだけで、正を決める欄が 1 つも無い。"""
    t = pull()
    rows = t.mismatches()
    assert len(rows) == 2 == t.seven()["不一致"]
    assert [r["項目名(年度 A)"] for r in rows] == ["K03", "K02"]
    assert [r["年度ペア"] for r in rows] == ["T1 × T2", "T2 × T3"]
    for r in rows:
        a, b = r["経路 A(去年の変更後)"], r["経路 B(今年の変更前)"]
        assert a["値"] and b["値"] and a["値"] != b["値"]
        assert a["出典"] and b["出典"] and a["資料 id"] != b["資料 id"]
    flat = str(rows)
    for word in ("正", "優先", "採用すべき", "直した"):
        assert word not in flat, word
    print("[measure] 不一致は 2 件で、どちらも両側の値・単位・出典・資料 id が並ぶ。"
          "正を選ぶ欄も、優先順位の欄も出力に 0 件(どちらの年度が正しいかは返さない)")


def test_measure_name_drift_is_not_confused_with_absence() -> None:
    """寄せ方が無い(名前が合わなかった)と、重なりが無い(相手が無い)を混ぜない。"""
    t = pull()
    yose_nashi = judged_of(t, ("T1", "T2"), "K05")
    assert yose_nashi.result == "寄せ方が無い"
    assert yose_nashi.cell_a is None and yose_nashi.cell_b is None
    # K05 は両側の資料に欄が在るのに、寄せ方の宣言が無いので比べに行かない
    extracts = H.Extracts.load(path_of("chuushutsu_a"))
    assert extracts.cell("S1", "変更後", "K05") is not None
    assert extracts.cell("S2", "変更前", "K05") is not None
    kasanari = [j for j in t.judged if j.result == "重なりが無い" and not j.stopped]
    assert [j.question.item for j in kasanari] == ["K06", "K08"]
    assert all(j.cell_a is not None and j.cell_b is None for j in kasanari)
    assert [r["経路 B の欄"] for r in t.no_overlap()] == ["無い", "無い"]
    print("[measure] 寄せ方が無い 1 件(K05)は両側の資料に欄が在るのに比べに行かず、"
          "重なりが無い 2 件(K06 / K08)は経路 B の欄そのものが無い。"
          "この 2 つは別の値として数える(同じ塊に落とさない)")


def read_kowashita(name: str) -> tuple[str, set[str]]:
    """崩した表 1 枚を基準の 4 枚に差し込んで読む。返るのは 読み方 と 理由コードの集合。"""
    args = {"chuushutsu": "chuushutsu_a", "yose": "yose_a", "saiyou": "saiyou_a",
            "toi": "toi_a"}
    args[name.split("_")[0]] = f"K:{name}"
    try:
        t = pull(c=args["chuushutsu"], y=args["yose"], s=args["saiyou"], t=args["toi"])
    except H.ReadError:
        return "表として読めない", set()
    if not t.report.ok:
        return "1 件も数えずに止まった", reasons_of(t)
    return "読んだ", set(t.stopped())


def test_measure_stop_reason_codes_all_reachable(monkeypatch) -> None:
    """止まる理由コード 13 個すべてに道がある(崩した表 + 差し替えた実装)。"""
    assert pull().report.pending == ()      # 基準の 4 枚は 1 行も止まらない
    seen: set[str] = set()
    group: dict[str, list[str]] = {}
    for name in M.kowashita():
        how, codes = read_kowashita(name)
        seen |= codes
        group.setdefault(how, []).append(name)
    assert {k: len(v) for k, v in sorted(group.items())} == {
        "1 件も数えずに止まった": 12, "表として読めない": 24, "読んだ": 1}
    assert group["読んだ"] == ["toi_swap_nashi"]
    assert seen == set(H.TABLE_REASONS) | set(H.QUESTION_REASONS)
    with pytest.raises(H.ReadError):
        H.verify(H.Extracts.load(path_of("chuushutsu_a")),
                 H.Bridges.load(path_of("yose_a")),
                 H.Takes.load(path_of("saiyou_a")),
                 H.Questions.load(path_of("K:toi_swap_nashi")))

    extracts, bridges, takes, questions = four()
    count = {"n": 0}

    def flaky(self) -> str:            # 2 回目で違うバイト列を出す実装に差し替える
        count["n"] += 1
        return f"{count['n']:064d}"

    monkeypatch.setattr(H.Tally, "sha256", flaky)
    out = H.verify(extracts, bridges, takes, questions)
    seen |= {p["理由コード"] for p in out["pending"]}
    monkeypatch.undo()
    monkeypatch.setattr(H.Tally, "seven", lambda self: {r: 0 for r in H.RESULTS})
    out2 = H.verify(extracts, bridges, takes, questions)
    seen |= {p["理由コード"] for p in out2["pending"]}
    assert seen == set(H.STOP_REASONS)
    assert len(H.STOP_REASONS) == 13
    print("[measure] 止まる理由コード 13 個すべてに道がある(崩した表 13 枚で 10 個 + "
          "差し替えた実装 2 本で 3 個)")
    print("[measure] 崩した表 37 枚の内訳 = 表として読めない 24 枚 / 1 件も数えずに"
          "止まる 12 枚 / 読めて verify だけが止まる 1 枚"
          "(「表として読めない」は理由コードに混ぜない)")


def test_broken_table_never_lands_in_the_seven() -> None:
    """この部品の「読めない」を、測っている相手の「重なりが無い」の欄に入れない。"""
    t = pull(s="K:saiyou_sengen_nashi")
    assert not t.report.ok and t.judged == ()
    c = t.counts()
    assert c["7 値"] == {r: 0 for r in H.RESULTS}
    assert c["読んだか"].startswith("読んでいない")
    assert reasons_of(t) == {"採用元の宣言が無い"}
    for call in (t.judgement_bytes, t.sha256):
        with pytest.raises(RuntimeError):
            call()
    print("[measure] 採用元の宣言が 1 行欠けていると 7 値は全て 0 で、理由コードだけが"
          "返る(相手の「重なりが無い」の欄に、この部品の「読めない」が混ざらない)")


def test_inputs_are_never_written() -> None:
    """読む前と後で、入力に置いた全ファイルの sha256 が変わらない。"""
    files = sorted(p for p in FIX.rglob("*.csv"))
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    t = pull()
    H.verify(*four())
    (t.counts(), t.by_pair(), t.listed(), t.mismatches(), t.self_checks(),
     t.no_overlap(), t.sha256())
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
    """判定ごとの一覧に、止まった問い以外が 1 件ずつちょうど 1 回出る。"""
    t = pull()
    listed = t.listed()
    assert [x["判定"] for x in listed] == list(H.RESULTS)
    keys = [(q["年度ペア"], q["項目名(年度 A)"]) for x in listed for q in x["問い"]]
    assert len(keys) == 16 and len(set(keys)) == 16
    assert sum(int(x["件数"]) for x in listed) == 16
    assert len(t.stopped_questions()) == 1
    assert t.stopped_questions()[0]["理由コード"] == "同じ年度を突き合わせる指定"


def test_cli_has_four_subcommands_and_no_options() -> None:
    """CLI は overlap / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = H.build_parser()
    sub = next(a for a in ap._actions if a.choices)
    assert tuple(sub.choices) == H.SUBCOMMANDS == ("overlap", "check", "verify", "init")
    for name, parser in sub.choices.items():
        flags = [o for a in parser._actions for o in a.option_strings]
        assert flags == ["-h", "--help"], (name, flags)


def test_cli_exit_codes(tmp_path, capsys) -> None:
    """別枠や止まった問いが残れば 3、表として読めなければ 2、ひな型は 0。"""
    args = [str(FIX / "chuushutsu_a.csv"), str(FIX / "yose_a.csv"),
            str(FIX / "saiyou_a.csv"), str(FIX / "toi_a.csv")]
    assert H.main(["check", *args]) == 3
    assert H.main(["overlap", *args]) == 3
    assert H.main(["verify", *args]) == 0          # verify は検算が合えば 0
    broken = [str(FIX / "kowashita" / "chuushutsu_0gyou.csv"), *args[1:]]
    assert H.main(["check", *broken]) == 2
    assert H.main(["init", str(tmp_path / "ひな型")]) == 0
    made = sorted(p.name for p in (tmp_path / "ひな型").iterdir())
    assert made == ["名前の寄せ方.csv", "問いの一覧.csv", "抽出表.csv",
                    "採用元の宣言.csv"]
    out = capsys.readouterr().out
    assert "一致率を割合にしない" in out


def test_init_template_shows_both_roles() -> None:
    """ひな型の 4 枚は、そのまま読めて、一致と採用元が同じ欄が 1 件ずつ出る。"""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        paths = H.init(d)
        t = H.overlap_check(H.Extracts.load(paths[0]), H.Bridges.load(paths[1]),
                            H.Takes.load(paths[2]), H.Questions.load(paths[3]))
        assert t.report.ok and t.question_denominator() == 2 and t.denominator == 2
        assert t.seven() == {"一致": 1, "不一致": 0, "重なりが無い": 0,
                             "寄せ方が無い": 0, "採用元が同じ欄": 1,
                             "単位がそろわない": 0, "資料が手元に無い": 0}
        assert len(t.self_checks()) == 1 and t.aside_denominator() == 0
        assert t.stopped() == {}


def test_same_year_stops_only_that_question() -> None:
    """同じ年度どうしの指定はその問いだけを止め、ほかの問いは数え続ける。"""
    t = pull()
    halted = [j for j in t.judged if j.stopped]
    assert len(halted) == 1
    assert (halted[0].question.year_a, halted[0].question.year_b) == ("T2", "T2")
    assert halted[0].reason == "同じ年度を突き合わせる指定"
    assert halted[0].cell_a is None and halted[0].cell_b is None
    assert t.report.ok and t.denominator == 15      # ほかの問いは数えている
    assert t.seven()["一致"] == 6
