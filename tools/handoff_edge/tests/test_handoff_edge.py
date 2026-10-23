"""handoff_edge のテスト。合成 fixture は `fixtures/` に commit 済(実データ・実在の値は入れない)。

test_measure_* が記事に載せた数値の出どころで、assert で固定している(値が変われば記事も変える前提)。
測っているものは 6 つある。

  (1) 問い 12 件が 5 値に分かれ、節の判定別・状態別の件数と 2 つの分母(問いの数 / 問いが要る
      節の延べ数)の内訳が付く側
  (2) 値が返る問い 8 件のうち、その値で計算が終わっているのは 2 件だけ、という側。= この記事の骨
  (3) 残る一手の一覧が、問いの数より多い 14 件になり、止まる問いにも一手が載る側
  (4) 未実装 と 設計上の外 が別の列のまま残る側(足して 1 つの数にしない)
  (5) 状態を 未実装 → 収録済 に替えると「返るが一手残る → 道具の中で済む」の 1 本だけが動き、
      同じ節を要る 4 問いのうち動くのは 1 問いだけ、という側
  (6) 節を宣言表から外すと別枠(宣言が無い)へ出るだけで、残りの節に収録済を当てた答えが
      出てこない側

(1) の 5 値は、テストの側でも 3 枚の表の行から直に組み立てて確かめている(部品の judge /
verdict / counts を呼ばず、fixture の行から別に数える)。
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
import handoff_edge as H  # noqa: E402
import make_fixtures as M  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの -> その行に在るはずの語
REAL_SOURCES = {
    M.SRC_SCOPE: "どちらも私が書いた文章で",
    M.SRC_STOCK: "1 つの終了コードに潰さず",
}

# 形容の語(出力にも実装にも持たせない = 数値が無いなら多寡を書かない)
KEIYOU = ("多い", "少ない", "ほとんど", "かなり", "著しく", "急いで")

# 持たせていない経路の名前(動く側のコードに 1 つも無いことを見る)
MOTANAI = ("eval", "exec", "網羅", "おすすめ", "推奨", "補完", "既定値",
           "とりあえず", "だいたい", "完成度", "割合", "提案")


def path_of(name: str) -> Path:
    return FIX / "kowashita" / f"{name[2:]}.csv" if name.startswith("K:") \
        else FIX / f"{name}.csv"


def pull(s: str = "syuubi_a", r: str = "recipe_a", t: str = "toi_a") -> H.Tally:
    return H.handoff_edge(H.Boundary.load(path_of(s)), H.Recipes.load(path_of(r)),
                          H.Questions.load(path_of(t)))


def asked_of(t: H.Tally, value_id: str) -> H.Asked:
    return next(a for a in t.asked if a.value_id == value_id)


def reasons_of(t: H.Tally) -> set[str]:
    return {p.reason for p in t.report.pending}


# ---------------------------------------------------------------- 別実装(テスト側)

def expect_five(syuubi: list[list[str]], recipe: list[list[str]],
                toi: list[list[str]]) -> dict[str, int]:
    """3 枚の行から 5 値を別に数える(部品の judge / verdict / counts を呼ばない)。"""
    nodes = {row[0]: row for row in syuubi}
    wants = {row[0]: [x for x in row[1].split("|") if x] for row in recipe}
    five = {r: 0 for r in H.RESULTS}
    for value_id, _, _ in toi:
        asked = wants[value_id]
        if any(n not in nodes for n in asked):
            five[H.ASIDE] += 1
            continue
        found: list[str] = []
        for node_id in asked:
            _, _, state, exit_kind, _, _ = nodes[node_id]
            if exit_kind == "止まる":
                found.append("止")
            elif state == "収録済":
                found.append("済")
            elif state == "設計上の外":
                found.append("外")
            else:
                found.append("手")
        if "止" in found:
            five[H.RESULTS[3]] += 1
        elif "外" in found:
            five[H.RESULTS[2]] += 1
        elif "手" in found:
            five[H.RESULTS[1]] += 1
        else:
            five[H.RESULTS[0]] += 1
    return five


# ---------------------------------------------------------------- 記事に載せた数値

def test_measure_12_questions_split_into_five() -> None:
    """(1) 問い 12 件が 5 値に分かれ、2 つの分母の内訳が付く。"""
    t = pull()
    assert t.report.ok and t.report.pending == ()
    c = t.counts()
    assert c["守備範囲の宣言表の行数(節の数)"] == 11
    assert c["計算のレシピ表の行数(求める値の数)"] == 12
    assert c["問いの数"] == 12 and t.denominator == 12
    assert c["5 値"] == {"道具の中で済む": 2, "返るが一手残る": 3, "外から渡す前提": 3,
                         "止まる": 3, "宣言が無い": 1}
    assert c["5 値"] == expect_five(M.syuubi_rows(), M.recipe_rows(), M.toi_rows())
    assert sum(c["5 値"].values()) == 12
    assert c["節の判定別(延べ数)"] == {"道具の中で済む": 6, "返るが一手残る": 6,
                                       "外から渡す前提": 5, "止まる": 3}
    assert t.node_denominator == 22 and t.counted_nodes() == 20
    assert not any(isinstance(v, float) for v in c.values())
    assert not any(str(k).endswith(("率", "割合")) for k in c)
    print("[measure] syuubi_a / recipe_a / toi_a: 節 11 / 求める値 12 / 問い 12 件"
          f" → 5 値 {c['5 値']}")
    print(f"[measure] 節の判定別(延べ数)= {c['節の判定別(延べ数)']}(分母は別で、"
          f"問いが要る節の延べ数 {t.node_denominator} のうち判定した {t.counted_nodes()}。"
          "別枠の問いの節は数えない)")
    print(f"[measure] 節の状態別 = {c['節の状態別(宣言表の行数)']}(合計 11 = 宣言表の行数)")


def test_measure_value_returns_but_calculation_is_not_over() -> None:
    """(2) 値が返る問い 8 件のうち、その値で計算が終わっているのは 2 件だけ。= 記事の骨。"""
    t = pull()
    returns = [a for a in t.asked
               if a.nodes and all(v != H.RESULTS[3] for _, v in a.nodes)]
    done = [a for a in returns if a.result == H.RESULTS[0]]
    left = [a for a in returns if a.result != H.RESULTS[0]]
    assert len(returns) == 8 and len(done) == 2 and len(left) == 6
    assert [a.value_id for a in done] == ["V01", "V02"]
    assert [a.value_id for a in left] == ["V03", "V04", "V06", "V07", "V08", "V12"]
    # 止まるのは 3 件。値が 1 つも返らないので「返ったのに終わっていない」側には入れない
    stopped = t.by_result(H.RESULTS[3])
    assert len(stopped) == 3 and [a.value_id for a in stopped] == ["V05", "V09", "V11"]
    print("[measure] 値が返る問いは 8 件 / 12。そのうち計算が終わっているのは 2 件だけで、"
          "6 件は値が返ってから一手が残る(返るが一手残る 3 + 外から渡す前提 3)")
    print("[measure] 値が 1 つも返らない(止まる)問いは 3 件 / 12。"
          "返るが一手残る と 止まる を同じ出口に潰さない")


def test_measure_remaining_steps_outnumber_the_questions() -> None:
    """(3) 残る一手は 14 件で、問いの数 12 より多い。止まる問いにも一手が載る。"""
    t = pull()
    rows = t.remaining()
    assert len(rows) == 14
    by_state = {s: sum(1 for r in rows if r["状態"] == s) for s in H.STATES[1:]}
    assert by_state == {"未実装": 6, "未対応": 3, "設計上の外": 5}
    in_stopped = [r for r in rows
                  if r["求める値"] in {"V05", "V09", "V11"}]
    assert len(in_stopped) == 5
    assert {r["残る一手"] for r in in_stopped} == {
        "乗率を取ってくる", "上限を当てる", "3 軸の表を分解する", "判断を属性で渡す",
        "行を足す"}
    assert all(r["出典"] for r in rows)       # 出典の無い一手は載らない
    print(f"[measure] 残る一手の一覧は 14 行で、問いの数 12 より多い(状態別 = {by_state})。"
          "1 つの問いに 2 つ残ることがあるため")
    print("[measure] 止まる問い 3 件にも一手が 5 件載る(値が返らないので「返ってから」の"
          "一手ではないが、呼び出し側に残る作業としては同じ欄に出る)")


def test_measure_unimplemented_and_out_of_design_stay_apart() -> None:
    """(4) 未実装 と 設計上の外 を足して 1 つの数にしない。"""
    t = pull()
    state = t.boundary.by_state()
    assert state == {"収録済": 2, "未実装": 3, "未対応": 3, "設計上の外": 3}
    node = t.by_node_verdict()
    assert node[H.RESULTS[1]] == 6 and node[H.RESULTS[2]] == 5
    # 「できていない」で 1 つにまとめると 11 件になるが、その数は出力に無い
    assert 11 not in [v for v in node.values()]
    body = str(t.counts())
    assert "できていない" not in body and "未完成の合計" not in body
    print("[measure] 節の状態は 収録済 2 / 未実装 3 / 未対応 3 / 設計上の外 3。"
          "延べでは 返るが一手残る 6 と 外から渡す前提 5 で、足して 11 にする欄は無い")


def test_measure_filling_a_node_moves_one_edge_only() -> None:
    """(5) 状態を直すと「返るが一手残る → 道具の中で済む」の 1 本だけが動く。"""
    boundary = H.Boundary.load(path_of("syuubi_a"))
    recipes = H.Recipes.load(path_of("recipe_a"))
    questions = H.Questions.load(path_of("toi_a"))
    first = H.handoff_edge(boundary, recipes, questions)
    probe = H.fill_probe(boundary, recipes, questions, first)
    assert probe["合うか"] is True
    per = {r["節"]: r["返るが一手残るの減り"] for r in probe["節ごと"]}
    assert per == {"N03": 1, "N09": 0, "N11": 1}
    whole = probe["未実装を全部 収録済 にした写し"]
    assert whole["移った先"] == {"返るが一手残る → 道具の中で済む": 3}
    assert whole["返るが一手残るの減り"] == whole["道具の中で済むの増え"] == 3
    # N03 は 4 つの問いが要るのに、状態を直して動くのは 1 問いだけ
    needs = [a.value_id for a in first.asked if "N03" in dict(a.nodes)]
    assert needs == ["V03", "V04", "V07", "V09"]
    assert {a.result for a in first.asked if a.value_id in needs} == {
        "返るが一手残る", "外から渡す前提", "止まる"}
    print("[measure] 状態を 未実装 → 収録済 に替える(3 節を 1 つずつ): 動いたのは"
          " N03 で 1 問い、N11 で 1 問い、N09 は 0 問い。移った先は"
          "「返るが一手残る → 道具の中で済む」の 1 本だけ(3 節とも)")
    print("[measure] 同じ未実装の節 N03 を要る問いは 4 件あり、その 4 件の結果は 3 通り"
          "(返るが一手残る 2 / 外から渡す前提 1 / 止まる 1)。"
          "1 つ直して動いたのは 1 件だけで、残り 3 件は別の一手に隠れている")


def test_measure_dropping_a_node_only_adds_the_aside() -> None:
    """(6) 節を外すと別枠へ出るだけ。残りの節に収録済を当てた答えが出てこない。"""
    boundary = H.Boundary.load(path_of("syuubi_a"))
    recipes = H.Recipes.load(path_of("recipe_a"))
    questions = H.Questions.load(path_of("toi_a"))
    first = H.handoff_edge(boundary, recipes, questions)
    probe = H.drop_probe(boundary, recipes, questions, first)
    assert probe["合うか"] is True
    gains = {r["外した節"]: r["別枠の増え"] for r in probe["節ごと"]}
    assert gains == {"N01": 5, "N02": 1, "N03": 4, "N04": 1, "N05": 3, "N06": 1,
                     "N07": 1, "N08": 1, "N09": 1, "N10": 1, "N11": 1}
    assert sum(gains.values()) == 20
    n01 = next(r for r in probe["節ごと"] if r["外した節"] == "N01")
    assert n01["移った先"] == {"道具の中で済む → 宣言が無い": 2,
                               "返るが一手残る → 宣言が無い": 1,
                               "外から渡す前提 → 宣言が無い": 1,
                               "止まる → 宣言が無い": 1}
    print("[measure] 節 1 つを宣言表から外す(11 節を 1 つずつ): 移った先は 11 節とも"
          "別枠(宣言が無い)だけで、延べ 20 件 / 分母 12。収録済を当てた答えに化ける"
          "問いは 0 件")
    print("[measure] N01(2 つの問いで 道具の中で済む を支えている節)を外すと、"
          "4 値の全部から 5 件が別枠へ移る")


def test_measure_counts_add_up_and_bytes_repeat() -> None:
    """2 回 + 3 枚の行順を入れ替えて読み直しても判定部分のバイト列が同じで、件数が合う。"""
    boundary = H.Boundary.load(path_of("syuubi_a"))
    recipes = H.Recipes.load(path_of("recipe_a"))
    questions = H.Questions.load(path_of("toi_a"))
    out = H.verify(boundary, recipes, questions)
    assert out["ok"] is True
    assert out["sha256"] == out["2 回目の sha256"] == out["入れ替えた 3 枚の sha256"]
    assert out["sha256"].startswith("69cd34562bce")
    check = out["件数の検算"]
    assert check["5 値の合計"] == check["分母(問いの数)"] == 12
    assert check["節の判定別の合計"] == check["判定した節"] == 20
    assert check["分母(問いが要る節の延べ数)"] == 22
    print(f"[measure] 2 回 + 3 枚の行順を逆順に入れ替えて読み直し: 判定部分の sha256 は"
          f" 3 回とも同じ(3/3 一致、先頭 12 桁 {out['sha256'][:12]})")
    print("[measure] 件数の検算: 5 値の合計 12 = 分母 12、節の判定別の合計 20 = "
          "判定した節 20(問いが要る節の延べ数 22 のうち、別枠の問いの 2 節は数えない)、"
          "節の状態別の合計 11 = 宣言表の行数 11")


def test_measure_order_is_the_spec() -> None:
    """裁定の順そのものが仕様。入れ替えると同じ宣言から別の答えが出る。"""
    t = pull()
    assert H.ORDER == ("宣言が無い", "止まる", "外から渡す前提", "返るが一手残る",
                       "道具の中で済む")
    v07 = asked_of(t, "V07")
    assert [v for _, v in v07.nodes] == ["道具の中で済む", "返るが一手残る",
                                         "外から渡す前提"]
    assert v07.result == "外から渡す前提"
    # 順を入れ替えたらどうなるかを、テストの側で別に組み立てて見る
    reversed_order = ("宣言が無い", "返るが一手残る", "外から渡す前提", "止まる",
                      "道具の中で済む")
    found = {v for _, v in v07.nodes}
    other = next(r for r in reversed_order if r in found or r == "道具の中で済む")
    assert other == "返るが一手残る" and other != v07.result
    # 止まるは 外から渡す前提 より先に出る(値が 1 つも返らないので)
    v11 = asked_of(t, "V11")
    assert [v for _, v in v11.nodes] == ["外から渡す前提", "止まる"]
    assert v11.result == "止まる"
    print("[measure] 3 つの節が別の値を返す問い V07 は、裁定の順のとおり 外から渡す前提 で"
          "返る。順を入れ替えると同じ宣言から 返るが一手残る になる(= 順番が仕様)")


def test_measure_no_clock_and_no_float() -> None:
    """判定部分に環境が入らない。値を計算する経路も、日付の欄も持たない。"""
    src = (ROOT / "handoff_edge.py").read_text(encoding="utf-8")
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
                        "json", "pathlib", "re", "sys"]
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
    args = {"syuubi": "syuubi_a", "recipe": "recipe_a", "toi": "toi_a"}
    args[name.split("_")[0]] = f"K:{name}"
    try:
        t = pull(s=args["syuubi"], r=args["recipe"], t=args["toi"])
    except H.ReadError:
        return "表として読めない", set()
    if not t.report.ok:
        return "1 件も判定せずに止まった", reasons_of(t)
    return "読んだ", set()


def test_measure_stop_reason_codes_all_reachable(monkeypatch) -> None:
    """止まる理由コード 14 個すべてに道がある(崩した表 + 差し替えた実装)。"""
    assert pull().report.pending == ()      # 基準の 3 枚は 1 件も止まらない
    seen: set[str] = set()
    group: dict[str, list[str]] = {}
    for name in M.kowashita():
        how, codes = read_kowashita(name)
        seen |= codes
        group.setdefault(how, []).append(name)
    assert {k: len(v) for k, v in sorted(group.items())} == {
        "1 件も判定せずに止まった": 13, "表として読めない": 16, "読んだ": 1}
    assert group["読んだ"] == ["toi_swap_nashi"]
    with pytest.raises(H.ReadError):
        H.verify(H.Boundary.load(path_of("syuubi_a")),
                 H.Recipes.load(path_of("recipe_a")),
                 H.Questions.load(path_of("K:toi_swap_nashi")))
    assert seen == set(H.TABLE_REASONS)

    boundary = H.Boundary.load(path_of("syuubi_a"))
    recipes = H.Recipes.load(path_of("recipe_a"))
    questions = H.Questions.load(path_of("toi_a"))
    count = {"n": 0}

    def flaky(self) -> str:            # 2 回目で違うバイト列を出す実装に差し替える
        count["n"] += 1
        return f"{count['n']:064d}"

    monkeypatch.setattr(H.Tally, "sha256", flaky)
    out = H.verify(boundary, recipes, questions)
    seen |= {p["理由コード"] for p in out["pending"]}
    monkeypatch.undo()
    monkeypatch.setattr(H.Tally, "by_node_verdict", lambda self: {})
    out2 = H.verify(boundary, recipes, questions)
    seen |= {p["理由コード"] for p in out2["pending"]}
    assert seen == set(H.STOP_REASONS)
    assert len(H.STOP_REASONS) == 14
    print("[measure] 止まる理由コード 14 個すべてに道がある(崩した表 13 枚で 11 個 + "
          "差し替えた実装 2 本で 3 個)")
    print("[measure] 崩した表 30 枚の内訳 = 表として読めない 16 枚 / 1 件も判定せずに"
          "止まる 13 枚 / 読めて verify だけが止まる 1 枚"
          "(「表として読めない」は理由コードに混ぜない)")


def test_broken_table_never_lands_in_the_four_values() -> None:
    """この部品の「読めない」を、測っている相手の「止まる」の欄に入れない。"""
    t = pull(s="K:syuubi_joutai_kuuran")
    assert not t.report.ok and t.asked == ()
    c = t.counts()
    assert c["5 値"] == {r: 0 for r in H.RESULTS}
    assert c["読んだか"].startswith("読んでいない")
    assert reasons_of(t) == {"節の状態が空"}
    for call in (lambda: t.verdict, t.judgement_bytes, t.sha256):
        with pytest.raises(RuntimeError):
            call()
    print("[measure] 宣言表が 1 行でも壊れていると 5 値は全て 0 で、理由コードだけが返る"
          "(相手の「止まる」3 件の欄に、この部品の「読めない」が混ざらない)")


def test_inputs_are_never_written() -> None:
    """読む前と後で、入力に置いた全ファイルの sha256 が変わらない。"""
    files = sorted(p for p in FIX.rglob("*.csv"))
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    t = pull()
    H.verify(H.Boundary.load(path_of("syuubi_a")), H.Recipes.load(path_of("recipe_a")),
             H.Questions.load(path_of("toi_a")))
    t.counts(), t.table(), t.remaining(), t.sha256()
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
    """CLI は edge / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = H.build_parser()
    sub = next(a for a in ap._actions if a.choices)
    assert tuple(sub.choices) == H.SUBCOMMANDS == ("edge", "check", "verify", "init")
    for name, parser in sub.choices.items():
        flags = [o for a in parser._actions for o in a.option_strings]
        assert flags == ["-h", "--help"], (name, flags)


def test_cli_exit_codes(tmp_path, capsys) -> None:
    """一手が残る問いが在れば 3、表として読めなければ 2、ひな型は 0。"""
    args = [str(FIX / "syuubi_a.csv"), str(FIX / "recipe_a.csv"),
            str(FIX / "toi_a.csv")]
    assert H.main(["check", *args]) == 3
    assert H.main(["edge", *args]) == 3
    assert H.main(["verify", *args]) == 0          # verify は検算が合えば 0
    broken = [str(FIX / "kowashita" / "syuubi_0gyou.csv"), args[1], args[2]]
    assert H.main(["check", *broken]) == 2
    assert H.main(["init", str(tmp_path / "ひな型")]) == 0
    made = sorted(p.name for p in (tmp_path / "ひな型").iterdir())
    assert made == ["問いの一覧.csv", "守備範囲の宣言表.csv", "計算のレシピ表.csv"]
    out = capsys.readouterr().out
    assert "完成度の割合を出さない" in out


def test_init_template_shows_the_handoff_trap() -> None:
    """ひな型の 3 枚は、そのまま読めて、3 つの問いが 3 通りの答えになる。"""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        paths = H.init(d)
        t = H.handoff_edge(H.Boundary.load(paths[0]), H.Recipes.load(paths[1]),
                           H.Questions.load(paths[2]))
        assert t.report.ok and t.denominator == 3
        five = {r: len(t.by_result(r)) for r in H.RESULTS}
        assert five == {"道具の中で済む": 1, "返るが一手残る": 1, "外から渡す前提": 1,
                        "止まる": 0, "宣言が無い": 0}
        assert len(t.remaining()) == 2


def test_missing_node_is_not_filled_with_recorded() -> None:
    """宣言表に無い節に収録済を当てない(別枠へ出し、残りの節の判定も出さない)。"""
    syuubi = "\n".join([",".join(H.SYUUBI_COLUMNS),
                        "N01,合成の rule 甲(架空),収録済,値が返る,,合成の出典メモ(架空)L1"])
    recipe = "\n".join([",".join(H.RECIPE_COLUMNS),
                        "V01,N01|N02,合成の出典メモ(架空)L2",
                        "V02,N01,合成の出典メモ(架空)L3"])
    toi = "\n".join([",".join(H.TOI_COLUMNS),
                     "V01,合成の出典メモ(架空)L4,逆順",
                     "V02,合成の出典メモ(架空)L5,"])
    t = H.handoff_edge(H.Boundary.parse(syuubi), H.Recipes.parse(recipe),
                       H.Questions.parse(toi))
    assert t.report.ok
    v01, v02 = t.asked
    assert v01.result == H.ASIDE and v01.nodes == () and v01.missing == ("N02",)
    assert v02.result == H.RESULTS[0]
    assert t.node_denominator == 3 and t.counted_nodes() == 1
