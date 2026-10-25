"""backing_axis のテスト。合成 fixture は `fixtures/` に commit 済(実データ・実在の値は入れない)。

test_measure_* が記事に載せた数値の出どころで、assert で固定している(値が変われば記事も変える前提)。
測っているものは 6 つある。

  (1) 行 22 件が 7 値(由来 5 + 別枠 2)に分かれ、3 つの分母の内訳が付く側
  (2) **欄が埋まっている 22 件のうち、原文で確かめた件数が付くのは 8 件だけ**という側。= 記事の骨
  (3) 旧軸 6 つの塊が、新軸に差し替えると 17 のセルに割れる側(どの領域も 2 つ以上に割れる)
  (4) 写した仮置き 5 件が確かめた 3 列に 1 件も入らず、**写し元の欄の由来を引き直すと 3 件は
      その写し元にも確かめた件数が無い**側
  (5) 行 1 件の由来を 写した仮置き → 2 経路の一致 に替えると件数がちょうど 1 ずつ動き、証跡を
      直さないままなら代わりに止まる側
  (6) 問い 1 件の新軸を旧軸にすると、その問いだけが止まってほかは 1 件も動かない側

(1) の 7 値は、テストの側でも 3 枚の表の行から直に組み立てて確かめている(部品の judge /
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
import backing_axis as H  # noqa: E402
import make_fixtures as M  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの -> その行に在るはずの語
REAL_SOURCES = {
    M.SRC_BLANK: "どちらにも寄せない",
    M.SRC_STOCK: "仮置きを実値と読む",
}

# 形容の語(出力にも実装にも持たせない = 数値が無いなら多寡を書かない)
KEIYOU = ("多い", "少ない", "ほとんど", "かなり", "著しく", "急いで")

# 持たせていない経路の名前(動く側のコードに 1 つも無いことを見る)
MOTANAI = ("eval", "exec", "網羅", "おすすめ", "推奨", "既定値", "とりあえず",
           "だいたい", "完成度", "点数を付ける", "スコア", "順位を付ける", "確度")


def path_of(name: str) -> Path:
    return FIX / "kowashita" / f"{name[2:]}.csv" if name.startswith("K:") \
        else FIX / f"{name}.csv"


def pull(d: str = "daichou_a", g: str = "touroku_a", t: str = "toi_a") -> H.Tally:
    return H.backing_axis(H.Ledger.load(path_of(d)), H.Registry.load(path_of(g)),
                          H.Questions.load(path_of(t)))


def asked_of(t: H.Tally, old_list_id: str) -> H.Asked:
    return next(a for a in t.asked if a.old_list_id == old_list_id)


def reasons_of(t: H.Tally) -> set[str]:
    return {p.reason for p in t.report.pending}


# ---------------------------------------------------------------- 別実装(テスト側)

def expect_seven(daichou: list[list[str]], touroku: list[list[str]]) -> dict[str, int]:
    """3 枚の行から 7 値を別に数える(部品の judge / seven / counts を呼ばない)。"""
    kinds = {row[0]: row[2] for row in touroku}
    seven = {r: 0 for r in H.RESULTS}
    for row in daichou:
        old_axis, origin = row[2], row[4]
        if not old_axis:
            seven["旧軸が無い"] += 1
        elif origin not in kinds:
            seven["宣言が無い"] += 1
        else:
            seven[H.RESULTS[H.EVIDENCE_TYPES.index(kinds[origin])]] += 1
    return seven


def origin_of_field(daichou: list[list[str]], field: str) -> str:
    """欄名からその欄の由来の記号を引く(写し元の欄をテストの側で辿るために使う)。"""
    return next((row[4] for row in daichou if row[3] == field), "")


# ---------------------------------------------------------------- 記事に載せた数値

def test_measure_22_rows_split_into_seven() -> None:
    """(1) 行 22 件が 7 値に分かれ、3 つの分母の内訳が付く。"""
    t = pull()
    assert t.report.ok and t.report.pending == ()
    c = t.counts()
    assert c["行の台帳の行数"] == 22 and t.denominator == 22
    assert c["由来の登録表の行数(記号の数)"] == 6
    assert len(H.EVIDENCE_TYPES) == 5          # 記号 6 つに対し、証跡の型は 5 種
    assert c["問いの数"] == 7 and c["分母(別枠の数)"] == 5
    assert c["7 値"] == {"機械の再計算": 3, "2 経路の一致": 4, "目視": 1,
                         "写した仮置き": 5, "取れない": 6, "宣言が無い": 2,
                         "旧軸が無い": 1}
    assert c["7 値"] == expect_seven(M.daichou_rows(), M.touroku_rows())
    assert sum(c["7 値"].values()) == 22
    assert c["記号別の件数"] == {"Y1": 3, "Y2": 4, "Y3": 1, "Y4": 5, "Y5": 2, "Y6": 4}
    assert sum(c["記号別の件数"].values()) == 19         # 別枠 3 件はここに入らない
    assert c["問いの状態"] == {"判定した": 5, "旧軸が無い": 2, "止まった": 0}
    assert not any(isinstance(v, float) for v in c.values())
    assert not any(str(k).endswith(("率", "割合")) for k in c)
    print(f"[measure] daichou_a / touroku_a / toi_a: 行 22 件 / 記号 6 つ / 問い 7 件"
          f" → 7 値 {c['7 値']}")
    print(f"[measure] 記号別 = {c['記号別の件数']}(合計 19 + 別枠 3 = 行数 22)。"
          "記号は 6 つだが、要求する証跡の型は 5 種(2 つの記号が同じ型を使う)")
    print(f"[measure] 問いの状態 = {c['問いの状態']}。分母は 行数 22 / 問いの数 7 / "
          "別枠 5(行の別枠 3 + 旧軸を指さない問い 2)の 3 つ")


def test_measure_only_8_of_22_have_a_counted_check() -> None:
    """(2) 欄が埋まっている 22 件のうち、確かめた件数が付くのは 8 件。= 記事の骨。"""
    t = pull()
    seven = t.seven()
    confirmed = sum(seven[r] for r in H.CONFIRMED)
    assert confirmed == 8
    assert sum(seven[r] for r in H.RESULTS[3:]) == 14
    assert confirmed + 14 == t.denominator == 22
    # 全部の行に値の欄名が在る(= 空欄ではない)。空欄かどうかの欄は持っていない
    assert all(j.entry.field for j in t.judged)
    # 確かめた 3 列の証跡は全部整数で、写し元の欄名は 1 つも混ざらない
    counts = [j.entry.evidence for j in t.judged if j.result in H.CONFIRMED]
    assert len(counts) == 8 and all(x.isdecimal() for x in counts)
    print("[measure] 欄が埋まっている 22 件のうち、原文で確かめた件数が付くのは 8 件"
          "(機械の再計算 3 + 2 経路の一致 4 + 目視 1)。残る 14 件は 写した仮置き 5 + "
          "取れない 6 + 宣言が無い 2 + 旧軸が無い 1")
    print("[measure] 22 件はどれも欄名が在り、値が入っている行として宣言されている"
          "(空欄かどうかを見る欄はこの部品に無い)")


def test_measure_cross_table_splits_6_domains_into_17_cells() -> None:
    """(3) 旧軸 6 つの塊が、新軸に差し替えると 17 のセルに割れる。"""
    t = pull()
    cross = t.cross()
    assert [row["旧軸"] for row in cross] == ["D1", "D2", "D3", "D4", "D5", "D6",
                                              "旧軸が無い"]
    assert [row["行数"] for row in cross] == [4, 3, 4, 3, 3, 4, 1]
    assert [row["割れた数"] for row in cross] == [3, 3, 3, 3, 2, 3, 1]
    named = [row for row in cross if row["旧軸"] != "旧軸が無い"]
    assert len(named) == 6
    assert sum(int(row["割れた数"]) for row in named) == 17
    assert all(int(row["割れた数"]) >= 2 for row in named)   # どの領域も 1 つに収まらない
    assert sum(int(row["行数"]) for row in cross) == 22      # 二重集計の検算
    # 問いごとに見ても同じ割れ方になる(問いは行の数え方を変えない)
    assert [a["割れた数"] for a in t.table() if a["状態"] == "判定した"] == [3, 3, 3, 3, 2]
    print("[measure] 旧軸では 6 つの塊だが、新軸(由来)に差し替えると 17 のセルに割れる"
          "(領域ごとの割れた数 = D1 3 / D2 3 / D3 3 / D4 3 / D5 2 / D6 3)。"
          "1 つの由来に収まる領域は 6 つのうち 0 件")
    print("[measure] 対応表のセルの合計 22 = 行数 22(旧軸が無い 1 件を含む)。"
          "行 1 件はちょうど 1 つのセルに入る")


def test_measure_placeholders_stay_out_of_the_confirmed_columns() -> None:
    """(4) 写した仮置き 5 件は確かめた 3 列に 1 件も入らず、写し元も 3 件は確かめていない。"""
    t = pull()
    rows = t.placeholders()
    assert len(rows) == 5 == t.seven()["写した仮置き"]
    assert [r["欄名"] for r in rows] == ["V06", "V09", "V11", "V14", "V22"]
    assert [r["写し元の欄名"] for r in rows] == ["V05", "V08", "V10", "V13", "V19"]
    assert all(r["出典"] for r in rows)
    assert all(str(r["欄名"]) != str(r["写し元の欄名"]) for r in rows)
    # 写し元の欄の由来をテストの側で引き直す(部品は写し元を辿らない)
    daichou = M.daichou_rows()
    kinds = {row[0]: row[2] for row in M.touroku_rows()}
    back = [H.RESULTS[H.EVIDENCE_TYPES.index(kinds[origin_of_field(
        daichou, str(r["写し元の欄名"]))])] for r in rows]
    assert back == ["2 経路の一致", "目視", "取れない", "取れない", "取れない"]
    assert sum(1 for b in back if b not in H.CONFIRMED) == 3
    print("[measure] 写した仮置きは 5 件で、確かめた 3 列(機械の再計算 / 2 経路の一致 /"
          " 目視)には 1 件も入らない。仮置きの一覧には写し元の欄名が必ず残る")
    print("[measure] その写し元の欄の由来をテストの側で引き直すと、5 件のうち 3 件は"
          "写し元にも確かめた件数が無い(取れない の欄から写していた)")


def test_measure_restating_one_row_moves_exactly_one() -> None:
    """(5) 由来を 写した仮置き → 2 経路の一致 に替えると件数が 1 ずつ動く。"""
    ledger = H.Ledger.load(path_of("daichou_a"))
    registry = H.Registry.load(path_of("touroku_a"))
    questions = H.Questions.load(path_of("toi_a"))
    first = H.backing_axis(ledger, registry, questions)
    probe = H.restate_probe(ledger, registry, questions, first)
    assert probe["合うか"] is True
    assert len(probe["行ごと"]) == 5
    one = probe["行ごと"][0]
    assert one["替えた行"] == "B06" and one["欄名"] == "V06"
    assert one["2 経路の一致"] == "4 → 5" and one["写した仮置き"] == "5 → 4"
    assert one["仮置きの一覧"] == "5 → 4"
    assert one["証跡をそのままにした写し"] == ["件数の欄に整数でない文字がある"]
    assert one["証跡を空にした写し"] == ["件数の欄が空"]
    after = H.backing_axis(ledger.restated("B06", "Y2", "1"), registry, questions)
    moved = [a.old_list_id for a in after.asked
             if a.rows != asked_of(first, a.old_list_id).rows]
    assert moved == ["D2"]                       # 動くのは替えた行が居る問いだけ
    print("[measure] 写した仮置き 5 件を 1 件ずつ 2 経路の一致 に替えると、5 通りとも"
          " 2 経路の一致 が 1 増え、写した仮置きと仮置きの一覧が 1 減る(ほかの 5 値は"
          "動かない)")
    print("[measure] 由来だけ替えて証跡を直さない写しでは、代わりに「件数の欄に整数でない"
          "文字がある」で止まる。証跡を空にした写しでは「件数の欄が空」で止まる。"
          "宣言と証跡を別々に見ている")


def test_measure_same_axis_stops_only_that_question() -> None:
    """(6) 新軸を旧軸にすると、その問いだけが止まる。"""
    ledger = H.Ledger.load(path_of("daichou_a"))
    registry = H.Registry.load(path_of("touroku_a"))
    questions = H.Questions.load(path_of("toi_a"))
    first = H.backing_axis(ledger, registry, questions)
    probe = H.same_axis_probe(ledger, registry, questions, first)
    assert probe["合うか"] is True
    assert len(probe["問いごと"]) == 5          # 判定した 5 件を 1 件ずつ替える
    assert all(r["動いた問い"] == r["替えた問い"] for r in probe["問いごと"])
    assert all(r["7 値"] == "動いていない" for r in probe["問いごと"])
    after = H.backing_axis(ledger, registry, questions.retargeted("D1", H.AXES[0]))
    a = asked_of(after, "D1")
    assert a.state == "止まった" and a.reason == "旧軸と同じ軸で並べ直す指定"
    assert a.rows == () and after.stopped() == {"旧軸と同じ軸で並べ直す指定": 1}
    assert after.seven() == first.seven()
    assert after.questions_by_state() == {"判定した": 4, "旧軸が無い": 2, "止まった": 1}
    print("[measure] 判定した 5 件を 1 件ずつ「旧軸で並べ直す」指定に替えると、5 通りとも"
          "その問いだけが止まり、ほかの問いの一覧と行の 7 値は 1 件も動かない")
    print("[measure] 止まった問いは一覧を持たない(行数 0)。問いの状態は 判定した 4 / "
          "旧軸が無い 2 / 止まった 1 になる")


def test_measure_counts_add_up_and_bytes_repeat() -> None:
    """2 回 + 3 枚の行順を入れ替えて読み直しても判定部分のバイト列が同じで、件数が合う。"""
    out = H.verify(H.Ledger.load(path_of("daichou_a")),
                   H.Registry.load(path_of("touroku_a")),
                   H.Questions.load(path_of("toi_a")))
    assert out["ok"] is True
    assert out["sha256"] == out["2 回目の sha256"] == out["入れ替えた 3 枚の sha256"]
    assert out["sha256"].startswith("c50006805a44")
    check = out["件数の検算"]
    assert check["7 値の合計"] == check["記号別 + 別枠"] == 22
    assert check["対応表のセルの合計"] == check["分母(行数)"] == 22
    assert check["分母(問いの数)"] == 7 and check["分母(別枠の数)"] == 5
    print("[measure] 2 回 + 3 枚の行順を逆順に入れ替えて読み直し: 判定部分の sha256 は"
          f" 3 回とも同じ(3/3 一致、先頭 12 桁 {out['sha256'][:12]})")
    print("[measure] 件数の検算: 7 値の合計 22 = 記号別 19 + 別枠 3 = 対応表のセルの合計 "
          "22 = 行数 22(3 通りの数え方が合う)")


def test_measure_no_clock_and_no_float() -> None:
    """判定部分に環境が入らない。値を計算する経路も、点数を付ける経路も持たない。"""
    src = (ROOT / "backing_axis.py").read_text(encoding="utf-8")
    skip = {tokenize.STRING, tokenize.COMMENT} | {
        getattr(tokenize, n) for n in ("FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END")
        if hasattr(tokenize, n)}
    code = "".join(t.string for t in
                   tokenize.generate_tokens(io.StringIO(src).readline)
                   if t.type not in skip)
    for word in ("now(", "today(", "time(", "float(", "eval(", "exec(",
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
          "eval / exec / subprocess / random / platform / datetime / 通信の呼び出しは"
          " 0 件(原文を取りに行く経路が無い)")
    print("[measure] 判定部分のバイト列に絶対パスは入らない(読んだ条件は別の欄)。"
          "形容の語 6 つと、持たせていない経路の語 13 個は動く側のコードに 0 件")


def read_kowashita(name: str) -> tuple[str, set[str]]:
    """崩した表 1 枚を基準の 3 枚に差し込んで読む。返るのは 読み方 と 理由コードの集合。"""
    args = {"daichou": "daichou_a", "touroku": "touroku_a", "toi": "toi_a"}
    args[name.split("_")[0]] = f"K:{name}"
    try:
        t = pull(d=args["daichou"], g=args["touroku"], t=args["toi"])
    except H.ReadError:
        return "表として読めない", set()
    if not t.report.ok:
        return "1 行も数えずに止まった", reasons_of(t)
    return "読んだ", set(t.stopped())


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
        "1 行も数えずに止まった": 11, "表として読めない": 19, "読んだ": 2}
    assert group["読んだ"] == ["toi_onaji_jiku", "toi_swap_nashi"]
    assert seen == set(H.TABLE_REASONS) | set(H.QUESTION_REASONS)
    with pytest.raises(H.ReadError):
        H.verify(H.Ledger.load(path_of("daichou_a")),
                 H.Registry.load(path_of("touroku_a")),
                 H.Questions.load(path_of("K:toi_swap_nashi")))

    ledger = H.Ledger.load(path_of("daichou_a"))
    registry = H.Registry.load(path_of("touroku_a"))
    questions = H.Questions.load(path_of("toi_a"))
    count = {"n": 0}

    def flaky(self) -> str:            # 2 回目で違うバイト列を出す実装に差し替える
        count["n"] += 1
        return f"{count['n']:064d}"

    monkeypatch.setattr(H.Tally, "sha256", flaky)
    out = H.verify(ledger, registry, questions)
    seen |= {p["理由コード"] for p in out["pending"]}
    monkeypatch.undo()
    monkeypatch.setattr(H.Tally, "seven", lambda self: {r: 0 for r in H.RESULTS})
    out2 = H.verify(ledger, registry, questions)
    seen |= {p["理由コード"] for p in out2["pending"]}
    assert seen == set(H.STOP_REASONS)
    assert len(H.STOP_REASONS) == 14
    print("[measure] 止まる理由コード 14 個すべてに道がある(崩した表 12 枚で 11 個 + "
          "差し替えた実装 2 本で 3 個)")
    print("[measure] 崩した表 32 枚の内訳 = 表として読めない 19 枚 / 1 行も数えずに"
          "止まる 11 枚 / 読めて問い 1 件だけ止まる 1 枚 / 読めて verify だけが止まる"
          " 1 枚(「表として読めない」は理由コードに混ぜない)")


def test_broken_table_never_lands_in_the_seven() -> None:
    """この部品の「読めない」を、測っている相手の「宣言が無い」の欄に入れない。"""
    t = pull(g="K:touroku_kata_kuuran")
    assert not t.report.ok and t.judged == () and t.asked == ()
    c = t.counts()
    assert c["7 値"] == {r: 0 for r in H.RESULTS}
    assert c["読んだか"].startswith("読んでいない")
    assert reasons_of(t) == {"証跡の型が空"}
    for call in (t.judgement_bytes, t.sha256):
        with pytest.raises(RuntimeError):
            call()
    print("[measure] 登録表が 1 行でも壊れていると 7 値は全て 0 で、理由コードだけが返る"
          "(相手の「宣言が無い」2 件の欄に、この部品の「読めない」が混ざらない)")


def test_inputs_are_never_written() -> None:
    """読む前と後で、入力に置いた全ファイルの sha256 が変わらない。"""
    files = sorted(p for p in FIX.rglob("*.csv"))
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    t = pull()
    H.verify(H.Ledger.load(path_of("daichou_a")), H.Registry.load(path_of("touroku_a")),
             H.Questions.load(path_of("toi_a")))
    t.counts(), t.table(), t.relisted(), t.cross(), t.placeholders(), t.sha256()
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


def test_relisted_keeps_every_row_once() -> None:
    """新軸で並べ直した一覧に、行が 1 件ずつちょうど 1 回出る。"""
    t = pull()
    listed = t.relisted()
    assert [x["新軸"] for x in listed] == list(H.RESULTS)
    ids = [r["行 id"] for x in listed for r in x["行"]]
    assert len(ids) == 22 and len(set(ids)) == 22
    assert sum(int(x["件数"]) for x in listed) == 22
    assert all(r["出典"] for x in listed for r in x["行"])


def test_cli_has_four_subcommands_and_no_options() -> None:
    """CLI は axis / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = H.build_parser()
    sub = next(a for a in ap._actions if a.choices)
    assert tuple(sub.choices) == H.SUBCOMMANDS == ("axis", "check", "verify", "init")
    for name, parser in sub.choices.items():
        flags = [o for a in parser._actions for o in a.option_strings]
        assert flags == ["-h", "--help"], (name, flags)


def test_cli_exit_codes(tmp_path, capsys) -> None:
    """別枠が残れば 3、表として読めなければ 2、ひな型は 0。"""
    args = [str(FIX / "daichou_a.csv"), str(FIX / "touroku_a.csv"),
            str(FIX / "toi_a.csv")]
    assert H.main(["check", *args]) == 3
    assert H.main(["axis", *args]) == 3
    assert H.main(["verify", *args]) == 0          # verify は検算が合えば 0
    broken = [str(FIX / "kowashita" / "daichou_0gyou.csv"), args[1], args[2]]
    assert H.main(["check", *broken]) == 2
    assert H.main(["init", str(tmp_path / "ひな型")]) == 0
    made = sorted(p.name for p in (tmp_path / "ひな型").iterdir())
    assert made == ["問いの一覧.csv", "由来の登録表.csv", "行の台帳.csv"]
    out = capsys.readouterr().out
    assert "件数を割合にしない" in out


def test_init_template_shows_the_split() -> None:
    """ひな型の 3 枚は、そのまま読めて、同じ領域の行が別の由来に割れる。"""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        paths = H.init(d)
        t = H.backing_axis(H.Ledger.load(paths[0]), H.Registry.load(paths[1]),
                           H.Questions.load(paths[2]))
        assert t.report.ok and t.denominator == 4 and t.question_denominator() == 2
        assert t.seven() == {"機械の再計算": 1, "2 経路の一致": 1, "目視": 0,
                             "写した仮置き": 1, "取れない": 1, "宣言が無い": 0,
                             "旧軸が無い": 0}
        assert [row["割れた数"] for row in t.cross()] == [2, 2]
        assert len(t.placeholders()) == 1
        assert t.aside_denominator() == 0 and t.stopped() == {}


def test_unregistered_mark_is_not_filled_with_a_default() -> None:
    """登録表に無い記号に既定を当てない(別枠へ出し、残りの行はそのまま)。"""
    daichou = "\n".join([",".join(H.DAICHOU_COLUMNS),
                         "B01,R01,D1,V01,Y1,3,合成の出典メモ(架空)L1",
                         "B02,R02,D1,V02,Y7,3,合成の出典メモ(架空)L2",
                         "B03,R03,D1,V03,,3,合成の出典メモ(架空)L3"])
    touroku = "\n".join([",".join(H.TOUROKU_COLUMNS),
                         f"Y1,機械で再計算して合わせた,{H.EVIDENCE_TYPES[0]}"])
    toi = "\n".join([",".join(H.TOI_COLUMNS),
                     f"D1,{H.AXES[1]},合成の出典メモ(架空)L4,{H.SWAPS[0]}"])
    t = H.backing_axis(H.Ledger.parse(daichou), H.Registry.parse(touroku),
                       H.Questions.parse(toi))
    assert t.report.ok
    assert [(j.entry.row_id, j.result) for j in t.judged] == [
        ("B01", "機械の再計算"), ("B02", "宣言が無い"), ("B03", "宣言が無い")]
    assert t.seven()["宣言が無い"] == 2
    assert t.by_mark() == {"Y1": 1}            # 別枠は記号別に入らない
