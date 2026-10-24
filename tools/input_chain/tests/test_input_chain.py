"""input_chain のテスト。合成 fixture は `fixtures/` に commit 済(実データ・実在の値は入れない)。

test_measure_* が記事に載せた数値の出どころで、assert で固定している(値が変われば記事も変える前提)。
測っているものは 6 つある。

  (1) 問い 10 件の依存を下まで辿ると葉が 39 枚になり、5 値と段別と 3 つの分母の内訳が付く側
  (2) **1 段目だけ数えると 人が用意する は 3 件だが、下まで辿ると 23 件**という側。= この記事の骨
  (3) 呼ぶ前に集めるものが、延べ 23 件・名前にすると 10 個に畳まれる側
  (4) 同じ名前が「導出すると宣言」と「人が用意する」の 2 つの列に出たまま残る側(足して 1 つに
      しない)
  (5) 入力の種別を case の欄 → 別の式 に替えると、その葉が消えて替えた式の入力が 1 段下に出る側
  (6) 循環は 辿れない に出るだけで、ほかの問いの葉には 1 枚も漏れない側

(1) の 5 値は、テストの側でも 3 枚の表の行から直に組み立てて確かめている(部品の walk /
counts を呼ばず、fixture の行から別に辿る)。
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
import input_chain as H  # noqa: E402
import make_fixtures as M  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの -> その行に在るはずの語
REAL_SOURCES = {
    M.SRC_BASIS: "代用しない",
    M.SRC_EDGE: "線の外に置くと決めたものだ",
}

# 形容の語(出力にも実装にも持たせない = 数値が無いなら多寡を書かない)
KEIYOU = ("多い", "少ない", "ほとんど", "かなり", "著しく", "急いで")

# 持たせていない経路の名前(動く側のコードに 1 つも無いことを見る)
MOTANAI = ("eval", "exec", "網羅", "おすすめ", "推奨", "補完", "既定値",
           "とりあえず", "だいたい", "完成度", "割合", "提案")


def path_of(name: str) -> Path:
    return FIX / "kowashita" / f"{name[2:]}.csv" if name.startswith("K:") \
        else FIX / f"{name}.csv"


def pull(s: str = "shiki_a", g: str = "gyou_a", t: str = "toi_a") -> H.Tally:
    return H.input_chain(H.Formulas.load(path_of(s)), H.Rows.load(path_of(g)),
                         H.Questions.load(path_of(t)))


def asked_of(t: H.Tally, value_id: str) -> H.Asked:
    return next(a for a in t.asked if a.value_id == value_id)


def reasons_of(t: H.Tally) -> set[str]:
    return {p.reason for p in t.report.pending}


# ---------------------------------------------------------------- 別実装(テスト側)

def expect_five(shiki: list[list[str]], gyou: list[list[str]],
                toi: list[list[str]]) -> dict[str, int]:
    """3 枚の行から 5 値を別に数える(部品の walk / judge / counts を呼ばない)。"""
    inputs: dict[str, list[list[str]]] = {}
    for row in shiki:
        inputs.setdefault(row[0], []).append(row)
    rules = {row[0]: row for row in gyou}
    five = {r: 0 for r in H.RESULTS}

    def leaf(name: str, hand: list[str]) -> None:
        five["手元に在る" if name in hand else "人が用意する"] += 1

    def go(fid: str, depth: int, path: list[str], hand: list[str]) -> None:
        for row in sorted(inputs.get(fid, []), key=lambda r: r[1]):
            name, kind, d = row[1], row[2], depth + 1
            if kind == "case の欄":
                leaf(name, hand)
            elif kind == "導出すると宣言":
                five["導出すると宣言"] += 1
            elif kind == "表の行":
                if name not in rules:
                    five["宣言が無い"] += 1
                else:
                    rule = rules[name]
                    need = [x for x in rule[1].split("|") if x] + \
                           sorted(x for x in rule[2].split("|") if x)
                    for one in need:
                        leaf(one, hand)
            elif name not in inputs:
                five["宣言が無い"] += 1
            elif name in path or d > H.MAX_DEPTH:
                five["辿れない"] += 1
            else:
                go(name, d, path + [name], hand)

    for value_id, at_hand, _, _ in toi:
        hand = [x for x in at_hand.split("|") if x]
        if value_id not in inputs:
            five["宣言が無い"] += 1
            continue
        go(value_id, 0, [value_id], hand)
    return five


# ---------------------------------------------------------------- 記事に載せた数値

def test_measure_10_questions_make_39_leaves() -> None:
    """(1) 問い 10 件を下まで辿ると葉が 39 枚になり、3 つの分母の内訳が付く。"""
    t = pull()
    assert t.report.ok and t.report.pending == ()
    c = t.counts()
    assert c["式の宣言表の行数(入力の数)"] == 20
    assert c["行の宣言表の行数(rule の数)"] == 4
    assert c["問いの数"] == 10 and t.denominator == 10
    assert c["分母(葉の数)"] == 39 and c["分母(段数の最大)"] == 4
    assert c["5 値"] == {"手元に在る": 8, "人が用意する": 23, "導出すると宣言": 3,
                         "宣言が無い": 3, "辿れない": 2}
    assert c["5 値"] == expect_five(M.shiki_rows(), M.gyou_rows(), M.toi_rows())
    assert sum(c["5 値"].values()) == 39
    assert c["段別の葉の数"] == {"0 段": 1, "1 段": 10, "2 段": 18, "3 段": 7, "4 段": 3}
    assert c["調達先種別別(宣言表の行数)"] == {"別の式": 7, "表の行": 4, "case の欄": 8,
                                              "導出すると宣言": 1}
    assert not any(isinstance(v, float) for v in c.values())
    assert not any(str(k).endswith(("率", "割合")) for k in c)
    print("[measure] shiki_a / gyou_a / toi_a: 入力 20 / rule 4 / 問い 10 件 → 葉 39 枚"
          f" 5 値 {c['5 値']}")
    print(f"[measure] 段別の葉の数 = {c['段別の葉の数']}(段 0 は求める値そのものが宣言表に"
          "無い 1 件。分母は 問いの数 10 / 葉の数 39 / 段数の最大 4 の 3 つ)")
    print(f"[measure] 調達先種別別 = {c['調達先種別別(宣言表の行数)']}(合計 20 = "
          "式の宣言表の行数)")


def test_measure_one_step_shows_3_but_the_walk_shows_23() -> None:
    """(2) 1 段目だけ数えると 人が用意する は 3 件、下まで辿ると 23 件。= 記事の骨。"""
    t = pull()
    leaves = t.leaves()
    first_step = [f for f in leaves if f.depth == 1 and f.result == H.RESULTS[1]]
    assert len(first_step) == 3
    assert sorted(f.name for f in first_step) == ["C02", "C03", "F08"]
    assert t.five()[H.RESULTS[1]] == 23
    # 葉 39 枚のうち、1 段目に出るのは 10 枚だけ
    assert sum(1 for f in leaves if f.depth == 1) == 10
    assert sum(1 for f in leaves if f.depth >= 2) == 28
    assert sum(1 for f in leaves if f.depth == 0) == 1
    # 1 段で終わる問いは 2 件だけ(F03 / F08)。段 0 の 1 件は求める値が宣言表に無い問い
    assert [a.value_id for a in t.asked if a.depth == 1] == ["F03", "F08"]
    assert [a.value_id for a in t.asked if a.depth >= 2] == ["F01", "F02", "F04",
                                                             "F05", "F06", "F07", "F09"]
    print("[measure] 1 段目だけ数えると 人が用意する は 3 件(C02 / C03 / F08)。"
          "下まで辿ると 23 件になる")
    print("[measure] 葉 39 枚のうち 1 段目に出るのは 10 枚で、28 枚は 2 段目より下にある"
          "(残る 1 枚は求める値そのものが宣言表に無い段 0 の葉)")
    print("[measure] 1 段で終わる問いは 10 件中 2 件(F03 / F08)。7 件は 2 段目より下に"
          "葉があり、段数の最大は 4(F09)")


def test_measure_collect_list_folds_23_into_10_names() -> None:
    """(3) 呼ぶ前に集めるものは延べ 23 件、名前にすると 10 個。"""
    t = pull()
    rows = t.collect()
    assert len(rows) == 10
    assert sum(int(r["延べ数"]) for r in rows) == 23
    assert [r["名前"] for r in rows] == ["C01", "C02", "C03", "C04", "C05", "C06",
                                         "C07", "C08", "C09", "F08"]
    c03 = next(r for r in rows if r["名前"] == "C03")
    assert c03["延べ数"] == 7 and c03["段"] == "1|2|3|4"
    assert c03["要る問い"] == "F04|F05|F06|F07|F08|F09"
    assert all(r["出典"] for r in rows)       # 出典の無い名前は載らない
    print("[measure] 呼ぶ前に集めるものは延べ 23 件で、名前にすると 10 個。いちばん多く"
          "出るのは C03 で、6 つの問いに延べ 7 回、1 段目から 4 段目まで散っている")


def test_measure_derived_and_case_field_stay_apart() -> None:
    """(4) 同じ名前が「導出すると宣言」と「人が用意する」の 2 列に出たまま残る。"""
    t = pull()
    leaves = t.leaves()
    derived = [f for f in leaves if f.name == "C02" and f.result == H.RESULTS[2]]
    by_hand = [f for f in leaves if f.name == "C02" and f.result == H.RESULTS[1]]
    assert len(derived) == 3 and len(by_hand) == 2
    assert sorted({f.source for f in derived}) == [M.SRC_BASIS]
    # 足して 5 にする欄は出力に無い
    body = str(t.counts())
    assert "導出すると宣言: 5" not in body and "できていない" not in body
    assert t.five()[H.RESULTS[2]] == 3
    print("[measure] 同じ入力 C02 は、ある式では 導出すると宣言(延べ 3 件)、別の式では"
          " 人が用意する(延べ 2 件)として出る。どちらが正しいかを決めず、足して 5 に"
          "する欄も持たない")


def test_measure_retyping_one_input_pushes_leaves_one_step_down() -> None:
    """(5) 種別を case の欄 → 別の式 に替えると、その葉が消えて 1 段下に出る。"""
    formulas = H.Formulas.load(path_of("shiki_a"))
    rows = H.Rows.load(path_of("gyou_a"))
    questions = H.Questions.load(path_of("toi_a"))
    first = H.input_chain(formulas, rows, questions)
    probe = H.retype_probe(formulas, rows, questions, first)
    assert probe["合うか"] is True
    assert len(probe["入力ごと"]) == 1          # 替えられる入力は 1 つだけ
    one = probe["入力ごと"][0]
    assert one["替えた入力"] == "F03 ← F08" and one["替えた式の入力の数"] == 2
    assert one["動いた問い"] == "F03|F04"
    assert one["葉の数"] == "39 → 41" and one["人が用意する"] == "23 → 25"
    after = H.input_chain(formulas.retyped("F03", "F08", H.KINDS[0]), rows, questions)
    # 段数が 1 増えたのは F03 だけ。F04 は元から 3 段あるので最大は変わらない
    moved = {a.value_id: (asked_of(first, a.value_id).depth, a.depth)
             for a in after.asked
             if a.leaves != asked_of(first, a.value_id).leaves}
    assert moved == {"F03": (1, 2), "F04": (3, 3)}
    assert first.deepest() == after.deepest() == 4
    print("[measure] 種別を case の欄 → 別の式 に替えられる入力は 1 つ(F03 ← F08)。"
          "替えると葉は 39 → 41、人が用意する は 23 → 25 になり、動いたのは 2 問いだけ")
    print("[measure] 段数が 1 増えたのは F03(1 → 2)だけで、F04 は元から 3 段あるので"
          "最大は 3 のまま。全体の段数の最大も 4 → 4 で動かない")


def test_measure_a_loop_stays_in_the_aside() -> None:
    """(6) 循環は 辿れない に出るだけで、ほかの問いの葉には 1 枚も漏れない。"""
    formulas = H.Formulas.load(path_of("shiki_a"))
    rows = H.Rows.load(path_of("gyou_a"))
    questions = H.Questions.load(path_of("toi_a"))
    first = H.input_chain(formulas, rows, questions)
    # 基準の 3 枚にも輪が 1 つ在る(F06 と F07 が互いを入力にしている)
    cut = first.cut()
    assert len(cut) == 2
    assert {r["なぜ"] for r in cut} == {H.WHY[0]}
    assert [(r["求める値"], r["枝"], r["段"]) for r in cut] == [("F06", "F06", 2),
                                                               ("F07", "F07", 2)]
    probe = H.loop_probe(formulas, rows, questions, first)
    assert probe["合うか"] is True
    hits = {r["循環を仕込んだ式"]: r["辿れない が出た問い"] for r in probe["式ごと"]}
    assert hits == {"F01": 2, "F02": 3, "F03": 2, "F04": 1, "F05": 2, "F06": 2,
                    "F07": 2, "F08": 1, "F09": 1}
    assert sum(hits.values()) == 16
    assert all(r["ほかの葉が動いたか"] == "動いていない" for r in probe["式ごと"])
    print("[measure] 基準の 3 枚には輪が 1 つ在り、辿れない は 2 件(F06 と F07 が互いを"
          "入力にしている)。どちらも理由は「経路に同じ式が 2 回出る」")
    print("[measure] 式 9 つに 1 つずつ循環を仕込むと、辿れない が出た問いは延べ 16 件。"
          "9 通りとも、ほかの葉は 1 枚も動かない(循環が別の問いに漏れない)")


def test_measure_depth_cap_cuts_the_deep_chain() -> None:
    """段数の上限に当たった枝も 辿れない に出て、打ち切った枝の名前と段を返す。"""
    t = pull(s="shiki_fukai", t="toi_fukai")
    assert t.report.ok
    assert H.MAX_DEPTH == 6
    assert t.five() == {"手元に在る": 0, "人が用意する": 0, "導出すると宣言": 0,
                        "宣言が無い": 0, "辿れない": 1}
    cut = t.cut()
    assert [(r["枝"], r["段"], r["なぜ"]) for r in cut] == [("D08", 7, H.WHY[1])]
    assert t.deepest() == 7 <= H.MAX_DEPTH + 2
    print("[measure] 9 段の鎖を訊くと、段数の上限 6 に当たった枝 D08(7 段目)が 辿れない"
          " に 1 件出る。無限に降りず、打ち切った枝の名前と段が返る")


def test_measure_counts_add_up_and_bytes_repeat() -> None:
    """2 回 + 3 枚の行順を入れ替えて読み直しても判定部分のバイト列が同じで、件数が合う。"""
    out = H.verify(H.Formulas.load(path_of("shiki_a")), H.Rows.load(path_of("gyou_a")),
                   H.Questions.load(path_of("toi_a")))
    assert out["ok"] is True
    assert out["sha256"] == out["2 回目の sha256"] == out["入れ替えた 3 枚の sha256"]
    assert out["sha256"].startswith("7aa570f90303")
    check = out["件数の検算"]
    assert check["5 値の合計"] == check["問いごとの内訳の合計"] == check["分母(葉の数)"] == 39
    assert check["分母(問いの数)"] == 10 and check["分母(段数の最大)"] == 4
    print("[measure] 2 回 + 3 枚の行順を逆順に入れ替えて読み直し: 判定部分の sha256 は"
          f" 3 回とも同じ(3/3 一致、先頭 12 桁 {out['sha256'][:12]})")
    print("[measure] 件数の検算: 5 値の合計 39 = 問いごとの内訳の合計 39 = 葉の数 39、"
          "調達先種別別の合計 20 = 式の宣言表の行数 20")


def test_measure_no_clock_and_no_float() -> None:
    """判定部分に環境が入らない。値を計算する経路も、日付の欄も持たない。"""
    src = (ROOT / "input_chain.py").read_text(encoding="utf-8")
    skip = {tokenize.STRING, tokenize.COMMENT} | {
        getattr(tokenize, n) for n in ("FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END")
        if hasattr(tokenize, n)}
    code = "".join(t.string for t in
                   tokenize.generate_tokens(io.StringIO(src).readline)
                   if t.type not in skip)
    for word in ("now(", "today(", "time(", "float(", "eval(", "exec(",
                 "subprocess", "random", "platform", "datetime"):
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
          "eval / exec / subprocess / random / platform / datetime / 今日を読む"
          "呼び出しは 0 件(この部品は日付の欄を持たない)")
    print("[measure] 判定部分のバイト列に絶対パスは入らない(読んだ条件は別の欄)。"
          "形容の語 6 つと、持たせていない経路の語 12 個は動く側のコードに 0 件")


def read_kowashita(name: str) -> tuple[str, set[str]]:
    """崩した表 1 枚を基準の 3 枚に差し込んで読む。返るのは 読み方 と 理由コードの集合。"""
    args = {"shiki": "shiki_a", "gyou": "gyou_a", "toi": "toi_a"}
    args[name.split("_")[0]] = f"K:{name}"
    try:
        t = pull(s=args["shiki"], g=args["gyou"], t=args["toi"])
    except H.ReadError:
        return "表として読めない", set()
    if not t.report.ok:
        return "1 枚も辿らずに止まった", reasons_of(t)
    return "読んだ", set()


def test_measure_stop_reason_codes_all_reachable(monkeypatch) -> None:
    """止まる理由コード 13 個すべてに道がある(崩した表 + 差し替えた実装)。"""
    assert pull().report.pending == ()      # 基準の 3 枚は 1 件も止まらない
    seen: set[str] = set()
    group: dict[str, list[str]] = {}
    for name in M.kowashita():
        how, codes = read_kowashita(name)
        seen |= codes
        group.setdefault(how, []).append(name)
    assert {k: len(v) for k, v in sorted(group.items())} == {
        "1 枚も辿らずに止まった": 12, "表として読めない": 15, "読んだ": 1}
    assert group["読んだ"] == ["toi_swap_nashi"]
    with pytest.raises(H.ReadError):
        H.verify(H.Formulas.load(path_of("shiki_a")), H.Rows.load(path_of("gyou_a")),
                 H.Questions.load(path_of("K:toi_swap_nashi")))
    assert seen == set(H.TABLE_REASONS)

    formulas = H.Formulas.load(path_of("shiki_a"))
    rows = H.Rows.load(path_of("gyou_a"))
    questions = H.Questions.load(path_of("toi_a"))
    count = {"n": 0}

    def flaky(self) -> str:            # 2 回目で違うバイト列を出す実装に差し替える
        count["n"] += 1
        return f"{count['n']:064d}"

    monkeypatch.setattr(H.Tally, "sha256", flaky)
    out = H.verify(formulas, rows, questions)
    seen |= {p["理由コード"] for p in out["pending"]}
    monkeypatch.undo()
    monkeypatch.setattr(H.Tally, "leaf_denominator", lambda self: 0)
    out2 = H.verify(formulas, rows, questions)
    seen |= {p["理由コード"] for p in out2["pending"]}
    assert seen == set(H.STOP_REASONS)
    assert len(H.STOP_REASONS) == 13
    print("[measure] 止まる理由コード 13 個すべてに道がある(崩した表 12 枚で 10 個 + "
          "差し替えた実装 2 本で 3 個)")
    print("[measure] 崩した表 28 枚の内訳 = 表として読めない 15 枚 / 1 枚も辿らずに"
          "止まる 12 枚 / 読めて verify だけが止まる 1 枚"
          "(「表として読めない」は理由コードに混ぜない)")


def test_broken_table_never_lands_in_the_five() -> None:
    """この部品の「読めない」を、測っている相手の「宣言が無い」の欄に入れない。"""
    t = pull(s="K:shiki_syubetsu_kuuran")
    assert not t.report.ok and t.asked == ()
    c = t.counts()
    assert c["5 値"] == {r: 0 for r in H.RESULTS}
    assert c["読んだか"].startswith("読んでいない")
    assert reasons_of(t) == {"調達先種別が空"}
    for call in (t.judgement_bytes, t.sha256):
        with pytest.raises(RuntimeError):
            call()
    print("[measure] 宣言表が 1 行でも壊れていると 5 値は全て 0 で、理由コードだけが返る"
          "(相手の「宣言が無い」3 件の欄に、この部品の「読めない」が混ざらない)")


def test_inputs_are_never_written() -> None:
    """読む前と後で、入力に置いた全ファイルの sha256 が変わらない。"""
    files = sorted(p for p in FIX.rglob("*.csv"))
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    t = pull()
    H.verify(H.Formulas.load(path_of("shiki_a")), H.Rows.load(path_of("gyou_a")),
             H.Questions.load(path_of("toi_a")))
    t.counts(), t.table(), t.collect(), t.cut(), t.sha256()
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    assert before == after
    print(f"[measure] 読む前後で入力 {len(files)} ファイルの sha256 が同じ(verify が作る"
          "写しはメモリの中だけで、表には書かない)")


def test_real_sources_point_at_lines_that_exist() -> None:
    """fixture の出典のうち repo 内の行を指すものは、その行に語が在る。"""
    for source, word in REAL_SOURCES.items():
        path, line = source.rsplit(" L", 1)
        text = (PLAN / path).read_text(encoding="utf-8").splitlines()[int(line) - 1]
        assert word in text, source
    print(f"[measure] fixture の出典のうち repo 内の実在の行を指すもの"
          f" {len(REAL_SOURCES)} 件は、その行に語が在ることをテストで確かめている")


def test_cli_has_four_subcommands_and_no_options() -> None:
    """CLI は chain / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = H.build_parser()
    sub = next(a for a in ap._actions if a.choices)
    assert tuple(sub.choices) == H.SUBCOMMANDS == ("chain", "check", "verify", "init")
    for name, parser in sub.choices.items():
        flags = [o for a in parser._actions for o in a.option_strings]
        assert flags == ["-h", "--help"], (name, flags)


def test_cli_exit_codes(tmp_path, capsys) -> None:
    """集めるものが残れば 3、表として読めなければ 2、ひな型は 0。"""
    args = [str(FIX / "shiki_a.csv"), str(FIX / "gyou_a.csv"), str(FIX / "toi_a.csv")]
    assert H.main(["check", *args]) == 3
    assert H.main(["chain", *args]) == 3
    assert H.main(["verify", *args]) == 0          # verify は検算が合えば 0
    broken = [str(FIX / "kowashita" / "shiki_0gyou.csv"), args[1], args[2]]
    assert H.main(["check", *broken]) == 2
    assert H.main(["init", str(tmp_path / "ひな型")]) == 0
    made = sorted(p.name for p in (tmp_path / "ひな型").iterdir())
    assert made == ["問いの一覧.csv", "式の宣言表.csv", "行の宣言表.csv"]
    out = capsys.readouterr().out
    assert "完成度の割合を出さない" in out


def test_init_template_shows_the_hidden_leaves() -> None:
    """ひな型の 3 枚は、そのまま読めて、1 段目に見えない葉が下から出てくる。"""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        paths = H.init(d)
        t = H.input_chain(H.Formulas.load(paths[0]), H.Rows.load(paths[1]),
                          H.Questions.load(paths[2]))
        assert t.report.ok and t.denominator == 2
        assert t.five() == {"手元に在る": 1, "人が用意する": 4, "導出すると宣言": 2,
                            "宣言が無い": 0, "辿れない": 0}
        assert asked_of(t, "F01").depth == 3
        assert len(t.collect()) == 2


def test_missing_reference_is_not_filled_with_a_default_kind() -> None:
    """宣言に無い参照に case の欄 を当てない(別枠へ出し、残りの葉はそのまま)。"""
    shiki = "\n".join([",".join(H.SHIKI_COLUMNS),
                       "F01,C01,case の欄,合成の出典メモ(架空)L1",
                       "F01,F77,別の式,合成の出典メモ(架空)L2",
                       "F01,R77,表の行,合成の出典メモ(架空)L3"])
    gyou = "\n".join([",".join(H.GYOU_COLUMNS),
                      "R01,C03,,合成の出典メモ(架空)L4"])
    toi = "\n".join([",".join(H.TOI_COLUMNS),
                     "F01,,合成の出典メモ(架空)L5,逆順"])
    t = H.input_chain(H.Formulas.parse(shiki), H.Rows.parse(gyou), H.Questions.parse(toi))
    assert t.report.ok
    a = t.asked[0]
    assert [(f.name, f.result, f.why) for f in a.leaves] == [
        ("C01", "人が用意する", ""),
        ("F77", "宣言が無い", H.WHY[3]),
        ("R77", "宣言が無い", H.WHY[4])]
    assert t.five()["宣言が無い"] == 2
