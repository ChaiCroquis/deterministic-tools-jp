"""share_terms のテスト。合成 fixture は `fixtures/` に commit 済(実データ・実在の値は入れない)。

test_measure_* が記事に載せた数値の出どころで、assert で固定している(値が変われば記事も変える前提)。
測っているものは 7 つある。

  (1) rule 15 件 / 867 行が 5 値に分かれ、3 つの分母の内訳が付く側
  (2) **出すと宣言された 12 rule・769 行 のうち、宣言が揃っているのは 5 rule・389 行**という側
  (3) **欄が空の 3 rule・169 行 と、出す宣言が無い 2 rule・51 行 と、名前が登録表に無い
      4 rule・211 行 が、別の値と別の行数で返る**という側。= 記事の骨
  (4) 出さないと宣言された 47 行が、空の欄の一覧にも欄が空の件数にも入らない側
  (5) 配布物ごとに要る帰属の文字列が verbatim のまま畳まれる側
  (6) 1 欄を空にすると「揃っている」が 1 減って「欄が空」が 1 増える側
  (7) 許諾を 1 件外すと、その名前の「出す」の行だけが別枠へ動く側

(1) の 5 値は、テストの側でも 4 枚の表の行から直に組み立てて確かめている(部品の judge /
five を呼ばず、fixture の行から別に分類する)。
"""
from __future__ import annotations

import ast
import hashlib
import io
import json
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
import share_terms as H  # noqa: E402
import make_fixtures as M  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの -> その行に在るはずの語
REAL_SOURCES = {
    M.SRC_PIN: "原本のファイルの指紋",
    M.SRC_AXIS: "宣言と証跡の型",
}

# 配布の是非を指す語(出力にも実装にも持たせない = 型 B2 の forbidden の物理形)
KINSOKU = ("違法", "許諾なし", "要注意", "グレー", "無断", "侵害", "セーフ", "アウト")

# 形容の語(数値が無いなら多寡を書かない)
KEIYOU = ("多い", "少ない", "ほとんど", "かなり", "著しく", "ざっと")

# 持たせていない経路の名前(動く側のコードに 1 つも無いことを見る)
MOTANAI = ("eval", "exec", "round(", "float(", "now(", "today(", "time(",
           "subprocess", "random", "platform", "datetime", "urllib", "requests",
           "socket", "difflib", "SequenceMatcher")


def path_of(name: str) -> Path:
    return FIX / "kowashita" / f"{name[2:]}.csv" if name.startswith("K:") \
        else FIX / f"{name}.csv"


def pull(d: str = "daichou_a", k: str = "kyodaku_a", s: str = "shutten_a",
         m: str = "mokuroku_a") -> H.Tally:
    return H.share_terms(H.Ledger.load(path_of(d)), H.Registry.load(path_of(k)),
                         H.Origins.load(path_of(s)), H.Bundles.load(path_of(m)))


def four() -> tuple[H.Ledger, H.Registry, H.Origins, H.Bundles]:
    return (H.Ledger.load(path_of("daichou_a")),
            H.Registry.load(path_of("kyodaku_a")),
            H.Origins.load(path_of("shutten_a")),
            H.Bundles.load(path_of("mokuroku_a")))


def reasons_of(t: H.Tally) -> set[str]:
    return {p.reason for p in t.report.pending}


def judged_of(t: H.Tally, rule_id: str) -> H.Judged:
    return next(j for j in t.judged if j.row.rule_id == rule_id)


# ---------------------------------------------------------------- 別実装(テスト側)

def expect_five() -> dict[str, int]:
    """4 枚の行から 5 値を別に数える(部品の judge / five / counts を呼ばない)。"""
    needs = {row[0]: [f for f, cell in zip(H.FIELDS, row[1:4]) if cell == "要る"]
             for row in M.kyodaku_rows()}
    column = {H.FIELDS[0]: 5, H.FIELDS[1]: 6, H.FIELDS[2]: 7}
    five = {k: 0 for k in H.KEKKA}
    for row in M.daichou_rows():
        share, name = row[8], row[4]
        if share == "出さない":
            five["出さないと宣言された"] += 1
        elif share != "出す":
            five["出す宣言が無い"] += 1
        elif name not in needs:
            five["登録表に無い許諾の名前"] += 1
        elif all(row[column[f]] for f in needs[name]):
            five["宣言が揃っている"] += 1
        else:
            five["出すと宣言されたが欄が空"] += 1
    return five


# ---------------------------------------------------------------- 記事に載せた数値

def test_measure_15_rules_split_into_five() -> None:
    """(1) rule 15 件 / 867 行が 5 値に分かれ、分母の内訳が付く。"""
    t = pull()
    assert t.report.ok and t.report.pending == ()
    c = t.counts()
    assert c["行の台帳の行数"] == 15
    assert c["許諾の登録表の行数"] == 3
    assert c["出典元の台帳の行数"] == 7
    assert c["配布物の目録の行数"] == 8
    assert c["全体の行数"] == 867 == t.total_rows()
    assert c["分母(rule の数)"] == 15 == t.rule_denominator()
    assert c["分母(許諾の名前が登録表に在る rule の数)"] == 11
    assert c["分母(別枠の数)"] == 4
    assert c["分母(台帳に出てくる出典元の数)"] == 8
    assert c["分母(出す先の数)"] == 3
    assert c["5 値"] == {"宣言が揃っている": 5, "出すと宣言されたが欄が空": 3,
                         "出さないと宣言された": 1, "出す宣言が無い": 2,
                         "登録表に無い許諾の名前": 4}
    assert c["5 値"] == expect_five()
    assert sum(c["5 値"].values()) == 15
    assert c["理由別の止まった件数"] == {}
    assert not any(isinstance(v, float) for v in c.values())
    assert not any(str(k).endswith(("率", "割合", "点", "スコア")) for k in c)
    print("[measure] daichou_a / kyodaku_a / shutten_a / mokuroku_a: 台帳 15 行"
          f"(867 行)/ 登録表 3 行 / 出典元 7 行 / 目録 8 行 → 5 値 {c['5 値']}")
    print("[measure] 分母は rule の数 15 / 名前が登録表に在る rule 11 / 別枠 4、"
          "それに 台帳に出てくる出典元 8 と 出す先 3")


def test_measure_only_5_rules_are_settled() -> None:
    """(2) 出すと宣言された 12 rule・769 行 のうち、揃っているのは 5 rule・389 行。"""
    t = pull()
    five, rows = t.five(), t.rows_by_result()
    dasu = ("宣言が揃っている", "出すと宣言されたが欄が空", "登録表に無い許諾の名前")
    assert sum(five[k] for k in dasu) == 12
    assert sum(rows[k] for k in dasu) == 769
    assert five["宣言が揃っている"] == 5 and rows["宣言が揃っている"] == 389
    assert rows == {"宣言が揃っている": 389, "出すと宣言されたが欄が空": 169,
                    "出さないと宣言された": 47, "出す宣言が無い": 51,
                    "登録表に無い許諾の名前": 211}
    assert sum(rows.values()) == 867
    assert 389 + 169 + 211 == 769
    assert [j.row.rule_id for j in t.judged if j.result == "宣言が揃っている"] == \
        ["K11", "K13", "K14", "K21", "K71"]
    print("[measure] 出すと宣言されたのは 12 rule・769 行 で、そのうち宣言が揃って"
          "いるのは 5 rule・389 行。残る 7 rule・380 行 は 欄が空 3 rule・169 行 + "
          "名前が登録表に無い 4 rule・211 行")
    print("[measure] 全体 15 rule・867 行 の残りは 出さないと宣言された 1 rule・47 行 "
          "+ 出す宣言が無い 2 rule・51 行")


def test_measure_empty_fields_and_unsettled_names_stay_apart() -> None:
    """(3) 欄が空 / 出す宣言が無い / 名前が登録表に無い が別の値で返る。= 記事の骨。"""
    t = pull()
    c = t.counts()
    assert c["空の欄の数"] == 5 and c["空の欄を持つ rule の数"] == 3
    empty = t.empty_fields()
    assert [(e["rule id"], e["許諾の名前"], e["足りない欄"]) for e in empty] == [
        ("K12", "MIT", ["帰属の文字列"]),
        ("K22", "公共データ利用規約", ["原文の URL", "版の指紋"]),
        ("K23", "公共データ利用規約", ["帰属の文字列", "原文の URL"])]
    assert sum(len(e["足りない欄"]) for e in empty) == 5
    assert all(e["許諾の宣言の出典"] and e["行の出典"] for e in empty)
    # 出す宣言が無い行は、欄が空の一覧に 1 件も出ない(別の値・別の行数)
    assert [j.row.rule_id for j in t.judged if j.result == "出す宣言が無い"] == \
        ["K41", "K42"]
    assert t.rows_by_result()["出す宣言が無い"] == 51
    assert all(e["rule id"] not in ("K41", "K42") for e in empty)
    for rule_id in ("K41", "K42"):
        assert judged_of(t, rule_id).missing == ()
    # 名前が登録表に無い行は、空欄のものと書かれているものの両方が別枠に出る
    aside = t.unregistered_licenses()
    assert [(a["rule id"], a["書かれていた許諾の名前"], a["行数"]) for a in aside] == [
        ("K31", "(空欄)", 141), ("K32", "(空欄)", 47), ("K51", "(空欄)", 20),
        ("K72", "合成の未登録の許諾(架空)", 3)]
    assert sum(int(a["行数"]) for a in aside) == 211
    assert all(a["出典"] for a in aside)
    assert all(j.missing == () and j.needs == () for j in t.judged
               if j.result == "登録表に無い許諾の名前")
    print("[measure] 欄が空は 3 rule・169 行 で、空の欄は 5 件(K12 に 1 欄、K22 と "
          "K23 に 2 欄ずつ)。出す宣言が無い 2 rule・51 行 はこの一覧に 1 件も出ない")
    print("[measure] 名前が登録表に無いのは 4 rule・211 行 で、内訳は 名前の欄が空 "
          "3 rule・208 行 と 書かれているが登録に無い 1 rule・3 行。どれも足りない欄を"
          "数えずに別枠へ出る(要求される欄が分からないため)")


def test_measure_declared_out_rows_are_not_short_of_anything() -> None:
    """(4) 出さないと宣言された 47 行は、空の欄の一覧にも件数にも入らない。"""
    t = pull()
    out = judged_of(t, "K61")
    assert out.result == "出さないと宣言された" and out.row.rows == 47
    assert out.needs == () and out.missing == ()
    assert out.row.license_name == "MIT" and out.row.attribution == ""
    # MIT は帰属の文字列を要求すると宣言されているが、出さない行では見に行かない
    assert H.Registry.load(path_of("kyodaku_a")).of("MIT").needs == ("帰属の文字列",)
    assert all(e["rule id"] != "K61" for e in t.empty_fields())
    assert t.counts()["空の欄の数"] == 5
    assert 5 + 1 == 6       # 出さない行の帰属の文字列まで数えると 6 件になる
    print("[measure] 出さないと宣言された 1 rule・47 行 は、許諾が帰属の文字列を要求"
          "すると宣言されていても空の欄に数えない(混ぜると空の欄は 5 件から 6 件に"
          "なる)。配らないと宣言された行に足りない欄は無い")


def test_measure_attributions_are_folded_verbatim() -> None:
    """(5) 配布物ごとに要る帰属の文字列が verbatim のまま畳まれる。"""
    t = pull()
    rows = t.attributions()
    assert [r["出す先 id"] for r in rows] == ["B1", "B2", "B3"]
    assert [r["含む rule の数"] for r in rows] == [4, 3, 1]
    assert [r["要る帰属の文字列(畳む前)"] for r in rows] == [3, 2, 0]
    assert [len(r["要る帰属の文字列"]) for r in rows] == [2, 2, 0]
    assert rows[0]["要る帰属の文字列"] == [M.ATTR_A, M.ATTR_B]
    assert rows[1]["要る帰属の文字列"] == [M.ATTR_B, M.ATTR_C]
    assert rows[1]["許諾が登録表に無くて要否の分からない rule"] == ["K31"]
    assert rows[2]["台帳に無い rule"] == ["K99"]
    # 文面は作らない(入力に無い文字列は 1 つも出ない)
    written = {r[5] for r in M.daichou_rows()}
    for r in rows:
        assert all(text in written for text in r["要る帰属の文字列"])
    print("[measure] B1 は 4 rule を含み、要る帰属の文字列は 3 件 → 畳んで 2 件"
          "(同じ文字列を 2 つの rule が持つ)。B2 は 2 件 + 許諾が登録表に無くて要否の"
          "分からない rule 1 件、B3 は 0 件 + 台帳に無い rule 1 件")


def test_measure_blanking_one_field_moves_one_rule() -> None:
    """(6) 1 欄を空にすると「揃っている」が 1 減って「欄が空」が 1 増える。"""
    ledger, registry, origins, bundles = four()
    first = H.share_terms(ledger, registry, origins, bundles)
    probe = H.blank_probe(ledger, registry, origins, bundles, first)
    assert probe["合うか"] is True
    assert len(probe["行ごと"]) == 4
    assert [r["空にした欄"] for r in probe["行ごと"]] == [
        "K11 の 帰属の文字列", "K14 の 帰属の文字列", "K21 の 帰属の文字列",
        "K71 の 帰属の文字列"]
    assert [r["その rule の行数"] for r in probe["行ごと"]] == [120, 15, 240, 6]
    assert all(r["宣言が揃っている"] == "5 → 4" for r in probe["行ごと"])
    assert all(r["出すと宣言されたが欄が空"] == "3 → 4" for r in probe["行ごと"])
    assert all(r["空の欄の数"] == "5 → 6" for r in probe["行ごと"])
    assert [r["揃っている行数"] for r in probe["行ごと"]] == [
        "389 → 269", "389 → 374", "389 → 149", "389 → 383"]
    assert all(r["ほかで動いた rule"] == [] for r in probe["行ごと"])
    after = H.share_terms(ledger.blanked("K21", H.FIELDS[0]), registry, origins,
                          bundles)
    mine = judged_of(after, "K21")
    assert mine.result == "出すと宣言されたが欄が空"
    assert mine.needs == ("帰属の文字列", "原文の URL", "版の指紋")
    assert mine.missing == ("帰属の文字列",)
    assert after.rows_by_result()["出すと宣言されたが欄が空"] == 409
    print("[measure] K21 の帰属の文字列 1 欄を空にすると、揃っている 5 → 4、欄が空 "
          "3 → 4、空の欄 5 → 6 件、揃っている行数は 389 → 149(= その rule の 240 行"
          "ちょうど)。ほかの rule の判定は動かない")
    print("[measure] 同じことを 4 つの行(120 / 15 / 240 / 6 行)で測っても、動く件数は"
          "いつも 1 で、動く行数はその rule の行数ちょうど")


def test_measure_dropping_one_license_moves_only_the_dasu_rows() -> None:
    """(7) 許諾を 1 件外すと、その名前の「出す」の行だけが別枠へ動く。"""
    ledger, registry, origins, bundles = four()
    first = H.share_terms(ledger, registry, origins, bundles)
    probe = H.license_probe(ledger, registry, origins, bundles, first)
    assert probe["合うか"] is True
    assert [r["外した許諾の名前"] for r in probe["行ごと"]] == [
        "MIT", "公共データ利用規約", "合成の公開の宣言(架空)"]
    mit = probe["行ごと"][0]
    assert mit["動く rule"] == ["K11", "K12", "K14", "K71"] and mit["動く行数"] == 196
    assert mit["同じ名前だが動かない rule"] == ["K61"]
    assert mit["登録表に無い許諾の名前"] == "4 → 8"
    assert mit["出さないと宣言された"] == "1 → 1"
    assert mit["出す宣言が無い"] == "2 → 2"
    kou = probe["行ごと"][1]
    assert kou["動く rule"] == ["K21", "K22", "K23"] and kou["動く行数"] == 354
    assert kou["登録表に無い許諾の名前"] == "4 → 7"
    assert probe["行ごと"][2]["動く rule"] == ["K13"]
    after = H.share_terms(ledger, registry.without("MIT"), origins, bundles)
    assert judged_of(after, "K61").result == "出さないと宣言された"
    assert after.five()["登録表に無い許諾の名前"] == 8
    print("[measure] 登録表から MIT を外すと、MIT を指す「出す」の 4 rule・196 行 だけ"
          "が別枠へ移り(別枠 4 → 8)、同じ MIT を指す「出さない」の K61 は動かない"
          "(= 出す宣言を先に見ていることが数の形になる)")
    print("[measure] 公共データ利用規約 を外すと 3 rule・354 行、合成の公開の宣言 を"
          "外すと 1 rule が別枠へ移る。ほかの許諾を指す行の 4 値は 1 つも動かない")


def test_measure_counts_add_up_and_bytes_repeat() -> None:
    """2 回 + 4 枚の行順を入れ替えて読み直しても判定部分のバイト列が同じで、件数が合う。"""
    out = H.verify(*four())
    assert out["ok"] is True
    assert out["sha256"] == out["2 回目の sha256"] == out["入れ替えた 4 枚の sha256"]
    assert out["sha256"].startswith("3da303422082")
    check = out["件数の検算"]
    assert check["5 値の合計"] == 15 == check["分母(rule の数)"]
    assert check["4 値"] == 11 == check["分母(許諾の名前が登録表に在る rule の数)"]
    assert check["出典元ごとの内訳の合計"] == 15
    assert check["出典元ごとの行数の合計"] == 867 == check["全体の行数"]
    assert check["5 値ごとの行数の合計"] == 867
    assert check["空の欄の数"] == 5 and check["分母(別枠の数)"] == 4
    print("[measure] 2 回 + 4 枚の行順を逆順に入れ替えて読み直し: 判定部分の sha256 は"
          f" 3 回とも同じ(3/3 一致、先頭 12 桁 {out['sha256'][:12]})")
    print("[measure] 件数の検算: 5 値の合計 15 = rule の数 15、4 値 11 = 名前が登録表に"
          "在る rule 11、出典元ごとの内訳の合計 15 = rule の数、出典元ごとの行数の合計 "
          "867 = 全体の行数、5 値ごとの行数の合計 867 = 全体の行数(5 通りが合う)")


def test_measure_origin_and_table_breakdowns() -> None:
    """出典元 8 つと数表 7 つの内訳の合計が全体に戻る(二重集計の検算)。"""
    t = pull()
    origins = t.by_origin()
    assert [r["出典元 id"] for r in origins] == ["G1", "G2", "G3", "G4", "G5", "G6",
                                                 "G7", "G9"]
    assert [r["rule の数"] for r in origins] == [4, 3, 2, 1, 1, 2, 1, 1]
    assert [r["行数"] for r in origins] == [198, 354, 188, 39, 20, 9, 47, 12]
    assert [r["出典元の台帳に在るか"] for r in origins] == \
        ["在る"] * 7 + ["無い"]
    assert [bool(r["許諾の名前が書かれている場所"]) for r in origins] == \
        [True, True, False, False, False, True, True, False]
    assert sum(int(r["rule の数"]) for r in origins) == 15
    assert sum(int(r["行数"]) for r in origins) == 867
    tables = t.by_table()
    assert [r["数表 id"] for r in tables] == ["H1", "H2", "H3", "H4", "H5", "H6", "H7"]
    assert [r["rule の数"] for r in tables] == [4, 3, 2, 2, 1, 1, 2]
    assert [r["行数"] for r in tables] == [198, 354, 188, 51, 20, 47, 9]
    for k in H.KEKKA:
        assert sum(int(r["5 値"][k]) for r in tables) == t.five()[k]
        assert sum(int(r["5 値"][k]) for r in origins) == t.five()[k]
    print("[measure] 出典元は 8 つで、許諾の名前が書かれている場所が在るのは 4 つ"
          "(G1 / G2 / G6 / G7)、無いのは 4 つ(G3 / G4 / G5 と、台帳に無い G9)。"
          "rule の数の合計 15 と行数の合計 867 はどちらも全体に戻る")
    print("[measure] 数表は 7 つで、rule の数は 4 / 3 / 2 / 2 / 1 / 1 / 2、行数は "
          "198 / 354 / 188 / 51 / 20 / 47 / 9")


def test_measure_two_reverse_gaps_are_listed_not_judged() -> None:
    """逆向きの欠け 2 種は、止めずに別の一覧へ出す。"""
    t = pull()
    unknown = t.unknown_origins()
    assert len(unknown) == 1 == t.counts()["出典元の台帳に無い出典元 id を指す行"]
    assert unknown[0]["rule id"] == "K42" and unknown[0]["指している出典元 id"] == "G9"
    assert unknown[0]["出典"]
    dangling = t.dangling_rules()
    assert len(dangling) == 1 == t.counts()["目録に載っているのに台帳に無い rule"]
    assert dangling[0]["出す先 id"] == "B3"
    assert dangling[0]["載っている rule id"] == "K99"
    assert all(j.row.rule_id != "K99" for j in t.judged)
    assert sum(t.five().values()) == 15      # 5 値の分母は台帳の行数のまま
    print("[measure] 逆向きの欠けは 2 種で各 1 件(出典元の台帳に無い G9 を指す行 "
          "K42 と、目録に載っているのに台帳に無い rule K99)。どちらも 5 値の分母 15 に"
          "は入らず、止めもせずに別の一覧へ出る")


def test_measure_no_clock_and_no_verdict_words() -> None:
    """判定部分に環境が入らない。配布の是非を指す語も、時計を読む経路も持たない。"""
    src = (ROOT / "share_terms.py").read_text(encoding="utf-8")
    skip = {tokenize.STRING, tokenize.COMMENT} | {
        getattr(tokenize, n) for n in ("FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END")
        if hasattr(tokenize, n)}
    code = "".join(x.string for x in
                   tokenize.generate_tokens(io.StringIO(src).readline)
                   if x.type not in skip)
    for word in MOTANAI:
        assert word not in code, word
    tree = ast.parse(src)
    imported = sorted({n.names[0].name.split(".")[0] for n in ast.walk(tree)
                       if isinstance(n, ast.Import)}
                      | {n.module.split(".")[0] for n in ast.walk(tree)
                         if isinstance(n, ast.ImportFrom) and n.module})
    assert imported == ["__future__", "argparse", "csv", "dataclasses", "hashlib",
                        "json", "pathlib", "sys"]
    for word in KINSOKU + KEIYOU:        # 文字列も含めて 1 つも持たない
        assert word not in src, word
    t = pull()
    body = t.judgement_bytes().decode("utf-8")
    assert str(FIX) not in body and "読んだ条件" not in body
    assert M.GOT_ON not in body          # 取得日は記録するだけ(判定部分に入れない)
    dumped = json.dumps([t.counts(), t.listed(), t.empty_fields(), t.attributions()],
                        ensure_ascii=False)
    for word in KINSOKU:
        assert word not in dumped, word
    print(f"[measure] 部品が import している module は {len(imported)} 個で、"
          "現在時刻を読む呼び出し・float / eval / exec / round / subprocess / "
          "random / platform / 通信 / 文字列の近さを測る呼び出しは 0 件")
    print(f"[measure] 配布の是非を指す語 {len(KINSOKU)} 個と形容の語 "
          f"{len(KEIYOU)} 個は、実装にも出力にも 0 件。判定部分のバイト列に絶対パスも"
          "取得日も入らない")


def test_measure_got_on_is_recorded_but_not_judged() -> None:
    """取得日は記録するだけで判定に使わない(日付を全部替えても 5 値が動かない)。"""
    t = pull()
    swapped = [list(r) for r in M.shutten_rows()]
    for row in swapped:
        row[2] = "2024-02-29"
    text = "\n".join([",".join(H.SHUTTEN_COLUMNS)] + [",".join(r) for r in swapped])
    ledger, registry, _origins, bundles = four()
    again = H.share_terms(ledger, registry, H.Origins.parse(text), bundles)
    assert again.report.ok and again.five() == t.five()
    assert again.rows_by_result() == t.rows_by_result()
    assert again.sha256() == t.sha256()
    for bad in ("2026-02-30", "2026-13-01", "2026-5-11", "2026/05/11", "", "きょう"):
        with pytest.raises(H.ReadError):
            H.check_date(bad)
    print("[measure] 出典元の取得日を全部 閏日 に書き換えても 5 値も行数も判定部分の "
          "sha256 も 1 つも動かない(= 判定に使っていない)。日付の形が違う 6 通りは"
          "読めない側で止まる")


def read_kowashita(name: str) -> tuple[str, set[str]]:
    """崩した表 1 枚を基準の 4 枚に差し込んで読む。返るのは 読み方 と 理由コードの集合。"""
    args = {"daichou": "daichou_a", "kyodaku": "kyodaku_a", "shutten": "shutten_a",
            "mokuroku": "mokuroku_a"}
    args[name.split("_")[0]] = f"K:{name}"
    try:
        t = pull(d=args["daichou"], k=args["kyodaku"], s=args["shutten"],
                 m=args["mokuroku"])
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
        "1 件も数えずに止まった": 10, "表として読めない": 24, "読んだ": 1}
    assert group["読んだ"] == ["mokuroku_swap_nashi"]
    assert seen == set(H.TABLE_REASONS)
    with pytest.raises(H.ReadError):
        H.verify(H.Ledger.load(path_of("daichou_a")),
                 H.Registry.load(path_of("kyodaku_a")),
                 H.Origins.load(path_of("shutten_a")),
                 H.Bundles.load(path_of("K:mokuroku_swap_nashi")))

    ledger, registry, origins, bundles = four()
    count = {"n": 0}

    def flaky(self) -> str:            # 2 回目で違うバイト列を出す実装に差し替える
        count["n"] += 1
        return f"{count['n']:064d}"

    monkeypatch.setattr(H.Tally, "sha256", flaky)
    out = H.verify(ledger, registry, origins, bundles)
    seen |= {p["理由コード"] for p in out["pending"]}
    monkeypatch.undo()
    monkeypatch.setattr(H.Tally, "five", lambda self: {k: 0 for k in H.KEKKA})
    out2 = H.verify(ledger, registry, origins, bundles)
    seen |= {p["理由コード"] for p in out2["pending"]}
    assert seen == set(H.STOP_REASONS)
    assert len(H.STOP_REASONS) == 13
    print("[measure] 止まる理由コード 13 個すべてに道がある(崩した表 10 枚で 10 個 + "
          "差し替えた実装 2 本で 3 個)")
    print("[measure] 崩した表 35 枚の内訳 = 表として読めない 24 枚 / 1 件も数えずに"
          "止まる 10 枚 / 読めて verify だけが止まる 1 枚"
          "(「表として読めない」は理由コードに混ぜない)")


def test_broken_table_never_lands_in_the_five() -> None:
    """この部品の「読めない」を、測っている相手の「欄が空」の欄に入れない。"""
    t = pull(d="K:daichou_shutten_nashi")
    assert not t.report.ok and t.judged == ()
    c = t.counts()
    assert c["5 値"] == {k: 0 for k in H.KEKKA}
    assert c["空の欄の数"] == 0 and c["読んだか"].startswith("読んでいない")
    assert reasons_of(t) == {"出典の欄が空"}
    for call in (t.judgement_bytes, t.sha256):
        with pytest.raises(RuntimeError):
            call()
    print("[measure] 出典の欄が空の行を 1 行混ぜると 5 値は全て 0、空の欄の数も 0 件で、"
          "理由コードだけが返る(相手の「欄が空」に、この部品の「読めない」が混ざらない)")


def test_name_and_place_must_agree() -> None:
    """許諾の名前と、それが書かれている場所の有無が食い違えば止まる。"""
    t = pull(d="K:daichou_namae_basho_nashi")
    assert not t.report.ok and t.judged == ()
    assert reasons_of(t) == {"許諾の名前が書かれているのに出典元の台帳にその場所が無い"}
    t2 = pull(d="K:daichou_namae_kuuran")
    assert not t2.report.ok
    assert reasons_of(t2) == {"許諾の名前が空なのに出典元の台帳に場所が書かれている"}
    t3 = pull(d="K:daichou_shimon_kuichigai")
    assert not t3.report.ok
    assert reasons_of(t3) == {"行の版の指紋が出典元の台帳の指紋と食い違う"}
    print("[measure] 名前と場所の食い違い 2 通りと、版の指紋の食い違い 1 通りは、"
          "どれも 1 件も数えずに止まる(名前を推測して埋める前に食い違いを出す)")


def test_listing_a_row_that_is_not_declared_out_stops() -> None:
    """出さないと宣言された行・出す宣言の無い行が目録に載っていれば止まる。"""
    t = pull(m="K:mokuroku_dasanai")
    assert not t.report.ok and t.judged == ()
    assert reasons_of(t) == {"出さないと宣言された行が配布物の目録に載っている"}
    t2 = pull(m="K:mokuroku_sengen_nashi")
    assert not t2.report.ok
    assert reasons_of(t2) == {"出す宣言の無い行が配布物の目録に載っている"}
    print("[measure] 出さないと宣言された行を目録に載せた表と、出す宣言の無い行を載せた"
          "表は、どちらも 1 件も数えずに止まる(宣言と目録の食い違いを入口で出す)")


def test_inputs_are_never_written() -> None:
    """読む前と後で、入力に置いた全ファイルの sha256 が変わらない。"""
    files = sorted(p for p in FIX.rglob("*.csv"))
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    t = pull()
    H.verify(*four())
    (t.counts(), t.by_origin(), t.by_table(), t.listed(), t.empty_fields(),
     t.unregistered_licenses(), t.unknown_origins(), t.dangling_rules(),
     t.attributions(), t.sha256())
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


def test_listed_keeps_every_rule_once() -> None:
    """判定ごとの一覧に、rule が 1 件ずつちょうど 1 回出る。"""
    t = pull()
    listed = t.listed()
    assert [x["判定"] for x in listed] == list(H.KEKKA)
    keys = [r["rule id"] for x in listed for r in x["rule"]]
    assert len(keys) == 15 and len(set(keys)) == 15
    assert sum(int(x["件数"]) for x in listed) == 15
    assert sum(int(x["行数"]) for x in listed) == 867


def test_empty_registry_puts_every_dasu_row_in_the_aside() -> None:
    """許諾を 1 つも登録していない状態は正常で、出す行が全部別枠に出る。"""
    text = ",".join(H.KYODAKU_COLUMNS)
    ledger, _registry, origins, bundles = four()
    t = H.share_terms(ledger, H.Registry.parse(text), origins, bundles)
    assert t.report.ok
    assert t.five() == {"宣言が揃っている": 0, "出すと宣言されたが欄が空": 0,
                        "出さないと宣言された": 1, "出す宣言が無い": 2,
                        "登録表に無い許諾の名前": 12}
    assert t.counts()["空の欄の数"] == 0
    assert all(r["要る帰属の文字列"] == [] for r in t.attributions())
    print("[measure] 許諾の登録表がヘッダだけの状態は正常に読め、出すと宣言された "
          "12 rule が全部別枠に出る。空の欄は 0 件で、要る帰属の文字列も 0 件"
          "(要求される欄が宣言されていないので、足りない欄も数えない)")


def test_cli_has_four_subcommands_and_no_options() -> None:
    """CLI は terms / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = H.build_parser()
    sub = next(a for a in ap._actions if a.choices)
    assert tuple(sub.choices) == H.SUBCOMMANDS == ("terms", "check", "verify", "init")
    for name, parser in sub.choices.items():
        flags = [o for a in parser._actions for o in a.option_strings]
        assert flags == ["-h", "--help"], (name, flags)


def test_cli_exit_codes(tmp_path, capsys) -> None:
    """欠けが残れば 3、表として読めなければ 2、ひな型は 0。"""
    args = [str(FIX / "daichou_a.csv"), str(FIX / "kyodaku_a.csv"),
            str(FIX / "shutten_a.csv"), str(FIX / "mokuroku_a.csv")]
    assert H.main(["check", *args]) == 3
    assert H.main(["terms", *args]) == 3
    assert H.main(["verify", *args]) == 0          # verify は検算が合えば 0
    broken = [str(FIX / "kowashita" / "daichou_0gyou.csv"), *args[1:]]
    assert H.main(["check", *broken]) == 2
    assert H.main(["init", str(tmp_path / "ひな型")]) == 0
    made = sorted(p.name for p in (tmp_path / "ひな型").iterdir())
    assert set(made) == {"行の台帳.csv", "許諾の登録表.csv", "出典元の台帳.csv",
                         "配布物の目録.csv"}
    out = capsys.readouterr().out
    assert "配ってよいかを判定しない" in out


def test_init_template_shows_three_values(tmp_path) -> None:
    """ひな型の 4 枚は、そのまま読めて、3 つの値が出る。"""
    paths = H.init(tmp_path / "ひな型")
    t = H.share_terms(H.Ledger.load(paths[0]), H.Registry.load(paths[1]),
                      H.Origins.load(paths[2]), H.Bundles.load(paths[3]))
    assert t.report.ok and t.rule_denominator() == 3
    assert t.five() == {"宣言が揃っている": 1, "出すと宣言されたが欄が空": 1,
                        "出さないと宣言された": 0, "出す宣言が無い": 1,
                        "登録表に無い許諾の名前": 0}
    assert t.empty_field_count() == 1
    assert t.attributions()[0]["要る帰属の文字列"] == ["合成の帰属の文字列(架空)"]
