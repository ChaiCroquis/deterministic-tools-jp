"""idle_rows のテスト。合成 fixture は `fixtures/` に commit 済(実データ・実在の値は入れない)。

test_measure_* が記事に載せた数値の出どころで、assert で固定している(値が変われば記事も変える前提)。
測っているものは 7 つある。

  (1) rule 14 件 / 277 行が 6 値に分かれ、3 つの分母の内訳が付く側
  (2) **参照されているのは 4 rule・26 行だけで、滞留は 7 rule・196 行**という側
  (3) **滞留 196 行のうち 43 行は、参照する式は在るのに問いまで届かない二次の空白**という側。= 記事の骨
  (4) 照合専用の 47 行と未来有効行の 3 行が滞留に入らない側
  (5) 滞留の理由を道具が当てず、登録表に無いコードは別枠に出る側
  (6) 宣言 1 行を外すと一次の空白が rule の行数だけ増える側
  (7) 問い 1 件を外すと二次の空白だけが増える側

(1) の 6 値は、テストの側でも 4 枚の表の行から直に組み立てて確かめている(部品の judge /
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
import idle_rows as H  # noqa: E402
import make_fixtures as M  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの -> その行に在るはずの語
REAL_SOURCES = {
    M.SRC_PACK: "塊を作らずに止まる",
    M.SRC_CHAIN: "降りられなくなった先",
}

# 形容の語(出力にも実装にも持たせない = 数値が無いなら多寡を書かない)
KEIYOU = ("多い", "少ない", "ほとんど", "かなり", "著しく", "ざっと")

# 評価の語(出力に持たせない = 残すかどうかも、滞留の理由も返さない。B4 の禁則の物理形)
HYOUKA = ("無駄", "ゴミ", "死んで", "怠慢", "放置", "使えない")

# 持たせていない経路の名前(動く側のコードに 1 つも無いことを見る)
MOTANAI = ("eval", "exec", "推奨", "おすすめ", "優先順位", "参照率", "達成率",
           "文字数", "呼び出し回数", "似ている", "だいたい", "とりあえず",
           "既定の参照", "網羅")


def path_of(name: str) -> Path:
    return FIX / "kowashita" / f"{name[2:]}.csv" if name.startswith("K:") \
        else FIX / f"{name}.csv"


def pull(d: str = "daichou_a", s: str = "sengen_a", t: str = "toi_a",
         r: str = "riyuu_a") -> H.Tally:
    return H.idle_rows(H.Ledger.load(path_of(d)), H.Declarations.load(path_of(s)),
                       H.Questions.load(path_of(t)), H.Registry.load(path_of(r)))


def four() -> tuple[H.Ledger, H.Declarations, H.Questions, H.Registry]:
    return (H.Ledger.load(path_of("daichou_a")),
            H.Declarations.load(path_of("sengen_a")),
            H.Questions.load(path_of("toi_a")),
            H.Registry.load(path_of("riyuu_a")))


def reasons_of(t: H.Tally) -> set[str]:
    return {p.reason for p in t.report.pending}


def judged_of(t: H.Tally, rule_id: str) -> H.Judged:
    return next(j for j in t.judged if j.row.rule_id == rule_id)


# ---------------------------------------------------------------- 別実装(テスト側)

def expect_six() -> dict[str, int]:
    """4 枚の行から 6 値を別に数える(部品の judge / six / counts を呼ばない)。"""
    asof = M.ASOF
    table_of = {r[1]: r[0] for r in M.daichou_rows()}
    refs: dict[str, list[list[str]]] = {}
    for row in M.sengen_rows():
        refs.setdefault(row[2], []).append(row)
    surveyed = {table_of[row[2]] for row in M.sengen_rows() if row[2] in table_of}
    question_ids = {q[0] for q in M.toi_rows()}
    needed = {q[2] for q in M.toi_rows()}
    six = {k: 0 for k in H.KEKKA}
    for table_id, rule_id, _rows, origin, valid_from, *_rest in M.daichou_rows():
        mine = refs.get(rule_id, [])
        called = [r for r in mine
                  if (r[0] in question_ids if r[1] == "問い" else r[0] in needed)]
        if origin == "照合専用":
            six["照合専用"] += 1
        elif valid_from and valid_from > asof:
            six["基準日より後に有効になる行"] += 1
        elif table_id not in surveyed:
            six["参照の宣言が無い"] += 1
        elif not mine:
            six["どの参照元からも参照されない"] += 1
        elif not called:
            six["参照元は在るが問いから呼ばれない"] += 1
        else:
            six["参照されている"] += 1
    return six


# ---------------------------------------------------------------- 記事に載せた数値

def test_measure_14_rules_split_into_six() -> None:
    """(1) rule 14 件 / 277 行が 6 値に分かれ、3 つの分母の内訳が付く。"""
    t = pull()
    assert t.report.ok and t.report.pending == ()
    c = t.counts()
    assert c["行の台帳の行数"] == 14
    assert c["参照の宣言表の行数"] == 9
    assert c["問いの数"] == 3
    assert c["理由コードの登録表の行数"] == 3
    assert c["全体の行数"] == 277 == t.total_rows()
    assert c["分母(rule の数)"] == 14 == t.rule_denominator()
    assert c["分母(参照候補の数)"] == 13 and c["分母(別枠の数)"] == 1
    assert c["6 値"] == {"参照されている": 4, "どの参照元からも参照されない": 4,
                         "参照元は在るが問いから呼ばれない": 3,
                         "参照の宣言が無い": 1, "照合専用": 1,
                         "基準日より後に有効になる行": 1}
    assert c["6 値"] == expect_six()
    assert sum(c["6 値"].values()) == 14
    assert c["理由別の止まった件数"] == {}
    assert not any(isinstance(v, float) for v in c.values())
    assert not any(str(k).endswith(("率", "割合", "点", "スコア")) for k in c)
    print("[measure] daichou_a / sengen_a / toi_a / riyuu_a: 台帳 14 行(277 行)/ "
          f"宣言 9 行 / 問い 3 件 / 登録表 3 行 → 6 値 {c['6 値']}")
    print("[measure] 分母は rule の数 14 / 参照候補 13 / 別枠 1 の 3 つ"
          "(別枠 1 件 = 有効開始日が基準日より後の行)")


def test_measure_only_4_rules_are_referenced() -> None:
    """(2) 参照されているのは 4 rule・26 行だけで、滞留は 7 rule・196 行。"""
    t = pull()
    six, rows = t.six(), t.rows_by_result()
    assert six["参照されている"] == 4 and t.referenced_rows() == 26
    assert sum(six[k] for k in H.TAIRYUU) == 7
    assert t.idle_row_counts()["合計"] == 196
    assert rows == {"参照されている": 26, "どの参照元からも参照されない": 153,
                    "参照元は在るが問いから呼ばれない": 43, "参照の宣言が無い": 5,
                    "照合専用": 47, "基準日より後に有効になる行": 3}
    assert sum(rows.values()) == 277
    assert 26 + 196 + 5 + 47 + 3 == 277
    assert [j.row.rule_id for j in t.judged if j.result == "参照されている"] == \
        ["K11", "K12", "K14", "K24"]
    assert [j.row.rule_id for j in t.judged if j.idle] == \
        ["K13", "K21", "K22", "K23", "K31", "K32", "K33"]
    print("[measure] 参照されているのは 4 rule・26 行で、滞留は 7 rule・196 行"
          "(全体 14 rule・277 行)。残る 3 rule は 参照の宣言が無い 5 行 + "
          "照合専用 47 行 + 未来有効行 3 行")


def test_measure_43_of_196_rows_are_second_order() -> None:
    """(3) 滞留 196 行のうち 43 行は二次の空白。= 記事の骨。"""
    t = pull()
    idle = t.idle_row_counts()
    assert idle == {"一次の空白": 153, "二次の空白": 43, "合計": 196}
    assert idle["一次の空白"] + idle["二次の空白"] == idle["合計"]
    chains = t.unreachable_chains()
    assert len(chains) == 3 == t.counts()["問いまで届かない連なり"]
    assert [(c["rule id"], c["参照元 id"], c["行数"]) for c in chains] == \
        [("K31", "F3", 20), ("K32", "F3", 21), ("K33", "F4", 2)]
    assert all(c["届かない所"].endswith("を要る参照元に挙げた問いが無い")
               for c in chains)
    assert all(c["宣言の出典"] and c["行の出典"] for c in chains)
    # 二次の空白の行は「指している参照元」を持ち、「呼ばれている参照元」は空
    for rule_id in ("K31", "K32", "K33"):
        j = judged_of(t, rule_id)
        assert j.result == "参照元は在るが問いから呼ばれない"
        assert j.refs and j.called == ()
    # 一次の空白の行は、指している参照元が 1 つも無い
    for rule_id in ("K13", "K21", "K22", "K23"):
        j = judged_of(t, rule_id)
        assert j.result == "どの参照元からも参照されない"
        assert j.refs == () and j.called == ()
    print("[measure] 滞留 196 行の内訳は 一次の空白 153 行 / 二次の空白 43 行。"
          "二次の 43 行は 3 つの rule で、指している式は在るのに その式を要る参照元に"
          "挙げた問いが無い(連なりの一覧は 3 行)")
    print("[measure] 一次の空白 4 rule は「指している参照元」の欄が 0 件、二次の空白 "
          "3 rule は 1 件ずつ在って「呼ばれている参照元」が 0 件"
          "(1 つの列に潰すと、この違いが消える)")


def test_measure_shougou_and_future_rows_stay_out() -> None:
    """(4) 照合専用の 47 行と未来有効行の 3 行は滞留に入らない。"""
    t = pull()
    sho, mirai = judged_of(t, "K41"), judged_of(t, "K51")
    assert sho.result == "照合専用" and sho.row.rows == 47
    assert sho.refs == () and sho.idle is False
    assert mirai.result == "基準日より後に有効になる行" and mirai.row.rows == 3
    assert mirai.candidate is False and mirai.idle is False
    assert mirai.row.valid_from == "2027-09-01" > t.questions.asof == "2026-05-20"
    assert t.idle_row_counts()["合計"] == 196
    assert 196 + 47 + 3 == 246
    # 宣言が無い数表の行は、一次の空白とは別の値で返る
    none = judged_of(t, "K61")
    assert none.result == "参照の宣言が無い" and none.row.rows == 5
    assert none.idle is False
    print("[measure] 照合専用 47 行と未来有効行 3 行は滞留の 196 行に入らない"
          "(混ぜると 246 行になる)。参照の宣言が無い数表の 5 行も別の値で返る")


def test_measure_tool_never_decides_the_reason() -> None:
    """(5) 滞留の理由を道具が当てず、登録表に無いコードは別枠に出る。"""
    t = pull()
    c = t.counts()
    assert t.reason_counts() == {"未実装": 3, "未収録の相手がいる": 2,
                                 "未来の有効行": 1}
    assert c["登録表に無い理由コードを持つ行"] == 1
    rows = t.unregistered_reasons()
    assert [(r["rule id"], r["書かれていた理由コード"]) for r in rows] == \
        [("K61", "画像 PDF")]
    # 理由コードは判定に 1 度も使われない(理由を空にしても 6 値が動かない)
    plain = [list(r) for r in M.daichou_rows()]
    for row in plain:
        row[5], row[6] = "", ""
    text = "\n".join([",".join(H.DAICHOU_COLUMNS)] + [",".join(r) for r in plain])
    bare = H.idle_rows(H.Ledger.parse(text), *four()[1:])
    assert bare.report.ok and bare.six() == t.six()
    assert bare.reason_counts() == {} and bare.unregistered_reasons() == []
    assert bare.idle_row_counts() == t.idle_row_counts()
    # 理由の無い滞留行が在る(推測で埋めない = 空のまま返る)
    assert judged_of(t, "K13").row.reason == ""
    assert judged_of(t, "K23").row.reason == ""
    print("[measure] 理由コード別の件数は 未実装 3 / 未収録の相手がいる 2 / "
          "未来の有効行 1 で、登録表に無いコードの行は別枠に 1 件。理由の欄を全部空に"
          "しても 6 値と滞留している行数は 1 つも動かない(= 判定に使っていない)")
    print("[measure] 滞留 7 rule のうち 理由が書かれているのは 5 rule で、残る 2 rule "
          "(K13 / K23)は理由の欄が空のまま返る(道具が埋めない)")


def test_measure_dropping_one_declaration_moves_rows() -> None:
    """(6) 宣言 1 行を外すと一次の空白が rule の行数だけ増える。"""
    ledger, decls, questions, registry = four()
    first = H.idle_rows(ledger, decls, questions, registry)
    probe = H.ref_probe(ledger, decls, questions, registry, first)
    assert probe["合うか"] is True
    assert len(probe["行ごと"]) == 2
    assert [r["外した宣言"] for r in probe["行ごと"]] == ["F2 → K12", "F2 → K14"]
    assert [r["その rule の行数"] for r in probe["行ごと"]] == [4, 9]
    assert [r["一次の空白"] for r in probe["行ごと"]] == \
        ["153 → 157", "153 → 162"]
    assert [r["二次の空白"] for r in probe["行ごと"]] == ["43 → 43", "43 → 43"]
    assert [r["合計"] for r in probe["行ごと"]] == ["196 → 200", "196 → 205"]
    assert all(r["ほかで動いた rule"] == [] for r in probe["行ごと"])
    after = H.idle_rows(ledger, decls.without("F2", "K12"), questions, registry)
    mine = judged_of(after, "K12")
    assert mine.result == "どの参照元からも参照されない" and mine.refs == ()
    assert after.six()["参照されている"] == 3
    assert after.idle_row_counts() == {"一次の空白": 157, "二次の空白": 43,
                                       "合計": 200}
    print("[measure] 宣言 F2 → K12 を 1 行外すと、参照されている 4 → 3、一次の空白 "
          "4 → 5 で、滞留の行数は 196 → 200(= その rule の 4 行ちょうど)。"
          "二次の空白 43 行とほかの rule の判定は動かない")
    print("[measure] もう 1 組(F2 → K14、9 行)でも同じで、滞留は 196 → 205。"
          "件数と行数を別の経路で数えているので、片方だけ動くと検算が合わなくなる")


def test_measure_dropping_one_question_moves_only_the_second_order() -> None:
    """(7) 問い 1 件を外すと二次の空白だけが増える。"""
    ledger, decls, questions, registry = four()
    first = H.idle_rows(ledger, decls, questions, registry)
    probe = H.question_probe(ledger, decls, questions, registry, first)
    assert probe["合うか"] is True
    assert len(probe["行ごと"]) == 1
    row = probe["行ごと"][0]
    assert row["外した問い"] == "Q2" and row["要る参照元"] == "F2"
    assert row["動く rule"] == ["K12", "K14"] and row["動く行数"] == 13
    assert row["参照されている"] == "4 → 2"
    assert row["参照元は在るが問いから呼ばれない"] == "3 → 5"
    assert row["一次の空白"] == "153 → 153"
    assert row["二次の空白"] == "43 → 56"
    assert row["ほかで動いた rule"] == []
    after = H.idle_rows(ledger, decls, questions.without("Q2"), registry)
    for rule_id in ("K12", "K14"):
        mine = judged_of(after, rule_id)
        assert mine.result == "参照元は在るが問いから呼ばれない"
        assert mine.refs == ("F2",) and mine.called == ()
    assert after.idle_row_counts() == {"一次の空白": 153, "二次の空白": 56,
                                       "合計": 209}
    print("[measure] 問い Q2 を 1 件外すと、その問いだけが呼んでいた式 F2 の指す 2 "
          "rule(13 行)が二次の空白へ移り、二次は 43 → 56 行。一次の空白 153 行は"
          "動かない(= 宣言を外した写しとの違いがここで数として出る)")
    print("[measure] 移った 2 rule は「指している参照元」が F2 のまま残り、「呼ばれて"
          "いる参照元」だけが 0 件になる。一次の空白(指す参照元が 0 件)とは別の形")


def test_measure_counts_add_up_and_bytes_repeat() -> None:
    """2 回 + 3 枚の行順を入れ替えて読み直しても判定部分のバイト列が同じで、件数が合う。"""
    out = H.verify(*four())
    assert out["ok"] is True
    assert out["sha256"] == out["2 回目の sha256"] == out["入れ替えた 3 枚の sha256"]
    assert out["sha256"].startswith("93f1a0e20bc9")
    check = out["件数の検算"]
    assert check["6 値の合計"] == 14 == check["分母(rule の数)"]
    assert check["5 値"] == 13 == check["分母(参照候補の数)"]
    assert check["数表ごとの内訳の合計"] == 14
    assert check["由来ごとの行数の合計"] == 277 == check["全体の行数"]
    assert check["6 値ごとの行数の合計"] == 277
    assert check["滞留している行数"] == {"一次の空白": 153, "二次の空白": 43,
                                         "合計": 196}
    assert check["分母(別枠の数)"] == 1
    print("[measure] 2 回 + 3 枚の行順を逆順に入れ替えて読み直し: 判定部分の sha256 は"
          f" 3 回とも同じ(3/3 一致、先頭 12 桁 {out['sha256'][:12]})")
    print("[measure] 件数の検算: 6 値の合計 14 = rule の数 14、5 値 13 = 参照候補 13、"
          "数表ごとの内訳の合計 14 = rule の数、由来ごとの行数の合計 277 = 全体の行数、"
          "6 値ごとの行数の合計 277 = 全体の行数(5 通りの数え方が合う)")


def test_measure_origin_and_table_breakdowns() -> None:
    """由来 3 通りと数表 6 つの内訳の合計が全体に戻る(二重集計の検算)。"""
    t = pull()
    origins = t.by_origin()
    assert [r["由来"] for r in origins] == ["自前抽出", "上流", "照合専用"]
    assert [r["rule の数"] for r in origins] == [8, 5, 1]
    assert [r["行数"] for r in origins] == [70, 160, 47]
    assert sum(int(r["rule の数"]) for r in origins) == 14
    assert sum(int(r["行数"]) for r in origins) == 277
    tables = t.by_table()
    assert [r["数表 id"] for r in tables] == ["H1", "H2", "H3", "H4", "H5", "H6"]
    assert [r["rule の数"] for r in tables] == [4, 4, 3, 1, 1, 1]
    assert [r["行数"] for r in tables] == [22, 157, 43, 47, 3, 5]
    assert [r["滞留している行数"] for r in tables] == [3, 150, 43, 0, 0, 0]
    assert [r["参照の宣言の数"] for r in tables] == [4, 1, 3, 0, 0, 0]
    for k in H.KEKKA:
        assert sum(int(r["6 値"][k]) for r in tables) == t.six()[k]
        assert sum(int(r["6 値"][k]) for r in origins) == t.six()[k]
    print("[measure] 由来ごとは 自前抽出 8 rule / 70 行、上流 5 rule / 160 行、"
          "照合専用 1 rule / 47 行で、合計は 14 rule / 277 行")
    print("[measure] 数表は 6 つで、rule の数は 4 / 4 / 3 / 1 / 1 / 1、行数は "
          "22 / 157 / 43 / 47 / 3 / 5、滞留している行数は 3 / 150 / 43 / 0 / 0 / 0、"
          "参照の宣言の数は 4 / 1 / 3 / 0 / 0 / 0")


def test_measure_dangling_declaration_is_listed_not_judged() -> None:
    """台帳に無い rule を指す宣言は、止めずに別の一覧へ出す(= 逆向きの欠け)。"""
    t = pull()
    rows = t.dangling_refs()
    assert len(rows) == 1 == t.counts()["台帳に無い rule を指す宣言"]
    assert rows[0]["参照元 id"] == "F5" and rows[0]["指している rule id"] == "K99"
    assert rows[0]["出典"]
    assert all(j.row.rule_id != "K99" for j in t.judged)
    assert sum(t.six().values()) == 14      # 6 値の分母は台帳の行数のまま
    print("[measure] 台帳に無い rule を指す宣言は 1 件で、6 値の分母 14 には入らず"
          "別の一覧に出る(宣言の側の欠けと、行の側の滞留を同じ列で数えない)")


def test_measure_no_clock_and_no_float() -> None:
    """判定部分に環境が入らない。時計を読む経路も、評価の語も持たない。"""
    src = (ROOT / "idle_rows.py").read_text(encoding="utf-8")
    skip = {tokenize.STRING, tokenize.COMMENT} | {
        getattr(tokenize, n) for n in ("FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END")
        if hasattr(tokenize, n)}
    code = "".join(x.string for x in
                   tokenize.generate_tokens(io.StringIO(src).readline)
                   if x.type not in skip)
    for word in ("now(", "today(", "time(", "float(", "eval(", "exec(", "round(",
                 "subprocess", "random", "platform", "datetime", "urllib",
                 "requests", "socket", "difflib", "SequenceMatcher"):
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
          "random / platform / 通信 / 文字列の近さを測る呼び出しは 0 件")
    print(f"[measure] 評価の語 {len(HYOUKA)} 個は文字列も含めて 0 件、形容の語 "
          f"{len(KEIYOU)} 個と持たせていない経路の語 {len(MOTANAI)} 個は動く側の"
          "コードに 0 件。判定部分のバイト列に絶対パスは入らない")


def test_measure_day_number_reads_no_clock() -> None:
    """日付は文字列から整数の通算日に直すだけ(同じ入力なら何日後でも同じ答え)。"""
    assert H.day_number("2027-09-01") - H.day_number("2026-05-20") == 469
    assert H.day_number("2026-05-20") - H.day_number("2026-05-19") == 1
    assert H.day_number("2026-03-01") - H.day_number("2026-02-28") == 1
    assert H.day_number("2024-03-01") - H.day_number("2024-02-29") == 1
    assert H.day_number("2024-03-01") - H.day_number("2024-02-28") == 2
    assert H.day_number("2027-01-01") - H.day_number("2026-01-01") == 365
    assert H.day_number("2025-01-01") - H.day_number("2024-01-01") == 366
    for bad in ("2026-02-30", "2026-13-01", "2026-5-20", "2026/05/20", "", "きょう"):
        with pytest.raises(H.ReadError):
            H.day_number(bad)
    print("[measure] 日付は整数の通算日に直すだけで、未来有効行までの差は 469 日、"
          "閏日をまたぐ差も 1 日 / 2 日 と合う。1 年は 365 日 / 366 日 の 2 通りで、"
          "月や日の形が違う 6 通りは読めない")


def read_kowashita(name: str) -> tuple[str, set[str]]:
    """崩した表 1 枚を基準の 4 枚に差し込んで読む。返るのは 読み方 と 理由コードの集合。"""
    args = {"daichou": "daichou_a", "sengen": "sengen_a", "toi": "toi_a",
            "riyuu": "riyuu_a"}
    args[name.split("_")[0]] = f"K:{name}"
    try:
        t = pull(d=args["daichou"], s=args["sengen"], t=args["toi"],
                 r=args["riyuu"])
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
        "1 件も数えずに止まった": 10, "表として読めない": 28, "読んだ": 1}
    assert group["読んだ"] == ["toi_swap_nashi"]
    assert seen == set(H.TABLE_REASONS)
    with pytest.raises(H.ReadError):
        H.verify(H.Ledger.load(path_of("daichou_a")),
                 H.Declarations.load(path_of("sengen_a")),
                 H.Questions.load(path_of("K:toi_swap_nashi")),
                 H.Registry.load(path_of("riyuu_a")))

    ledger, decls, questions, registry = four()
    count = {"n": 0}

    def flaky(self) -> str:            # 2 回目で違うバイト列を出す実装に差し替える
        count["n"] += 1
        return f"{count['n']:064d}"

    monkeypatch.setattr(H.Tally, "sha256", flaky)
    out = H.verify(ledger, decls, questions, registry)
    seen |= {p["理由コード"] for p in out["pending"]}
    monkeypatch.undo()
    monkeypatch.setattr(H.Tally, "six", lambda self: {k: 0 for k in H.KEKKA})
    out2 = H.verify(ledger, decls, questions, registry)
    seen |= {p["理由コード"] for p in out2["pending"]}
    assert seen == set(H.STOP_REASONS)
    assert len(H.STOP_REASONS) == 13
    print("[measure] 止まる理由コード 13 個すべてに道がある(崩した表 10 枚で 10 個 + "
          "差し替えた実装 2 本で 3 個)")
    print("[measure] 崩した表 39 枚の内訳 = 表として読めない 28 枚 / 1 件も数えずに"
          "止まる 10 枚 / 読めて verify だけが止まる 1 枚"
          "(「表として読めない」は理由コードに混ぜない)")


def test_broken_table_never_lands_in_the_six() -> None:
    """この部品の「読めない」を、測っている相手の「参照されない」の欄に入れない。"""
    t = pull(d="K:daichou_shutten_nashi")
    assert not t.report.ok and t.judged == ()
    c = t.counts()
    assert c["6 値"] == {k: 0 for k in H.KEKKA}
    assert c["滞留している行数"] == {"一次の空白": 0, "二次の空白": 0, "合計": 0}
    assert c["読んだか"].startswith("読んでいない")
    assert reasons_of(t) == {"出典の欄が空"}
    for call in (t.judgement_bytes, t.sha256):
        with pytest.raises(RuntimeError):
            call()
    print("[measure] 出典の欄が空の行を 1 行混ぜると 6 値は全て 0、滞留している行数も "
          "0 行で、理由コードだけが返る(相手の「参照されない」の欄に、この部品の"
          "「読めない」が混ざらない)")


def test_shougou_row_with_a_reference_stops() -> None:
    """照合専用と宣言した行を指す参照の宣言が在れば止まる(食い違いを入口で止める)。"""
    t = pull(s="K:sengen_shougou_sanshou")
    assert not t.report.ok and t.judged == ()
    assert reasons_of(t) == {"照合専用の行を指す参照の宣言が在る"}
    t2 = pull(d="K:daichou_shougou_riyuu")
    assert not t2.report.ok
    assert reasons_of(t2) == {"照合専用の行に滞留の理由コードが入っている"}
    print("[measure] 照合専用の行を指す宣言 1 行、照合専用の行に理由コード 1 つで、"
          "どちらも 1 件も数えずに止まる(引く対象でない行を滞留の列に混ぜる前に"
          "食い違いを出す)")


def test_inputs_are_never_written() -> None:
    """読む前と後で、入力に置いた全ファイルの sha256 が変わらない。"""
    files = sorted(p for p in FIX.rglob("*.csv"))
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    t = pull()
    H.verify(*four())
    (t.counts(), t.by_origin(), t.by_table(), t.listed(), t.unreachable_chains(),
     t.dangling_refs(), t.unregistered_reasons(), t.sha256())
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
    assert len(keys) == 14 and len(set(keys)) == 14
    assert sum(int(x["件数"]) for x in listed) == 14
    assert sum(int(x["行数"]) for x in listed) == 277


def test_how_column_is_recorded_but_not_judged() -> None:
    """参照の仕方は記録するだけで、判定には使わない(1 段しか辿らない)。"""
    t = pull()
    assert judged_of(t, "K14").result == "参照されている"
    assert H.Declarations.load(path_of("sengen_a")).refs_for("K14")[0].how == \
        "別の式経由"
    swapped = [list(r) for r in M.sengen_rows()]
    for row in swapped:
        if row[1] == "式":
            row[3] = "式の入力"
    text = "\n".join([",".join(H.SENGEN_COLUMNS)] + [",".join(r) for r in swapped])
    ledger, _decls, questions, registry = four()
    again = H.idle_rows(ledger, H.Declarations.parse(text), questions, registry)
    assert again.report.ok and again.six() == t.six()
    assert again.idle_row_counts() == t.idle_row_counts()
    print("[measure] 参照の仕方を全部「式の入力」に書き換えても 6 値と滞留している"
          "行数は 1 つも動かない(= 別の式経由 の宣言でも 2 段目は辿らない)")


def test_cli_has_four_subcommands_and_no_options() -> None:
    """CLI は idle / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = H.build_parser()
    sub = next(a for a in ap._actions if a.choices)
    assert tuple(sub.choices) == H.SUBCOMMANDS == ("idle", "check", "verify", "init")
    for name, parser in sub.choices.items():
        flags = [o for a in parser._actions for o in a.option_strings]
        assert flags == ["-h", "--help"], (name, flags)


def test_cli_exit_codes(tmp_path, capsys) -> None:
    """別枠や止まった行が残れば 3、表として読めなければ 2、ひな型は 0。"""
    args = [str(FIX / "daichou_a.csv"), str(FIX / "sengen_a.csv"),
            str(FIX / "toi_a.csv"), str(FIX / "riyuu_a.csv")]
    assert H.main(["check", *args]) == 3
    assert H.main(["idle", *args]) == 3
    assert H.main(["verify", *args]) == 0          # verify は検算が合えば 0
    broken = [str(FIX / "kowashita" / "daichou_0gyou.csv"), *args[1:]]
    assert H.main(["check", *broken]) == 2
    assert H.main(["init", str(tmp_path / "ひな型")]) == 0
    made = sorted(p.name for p in (tmp_path / "ひな型").iterdir())
    assert set(made) == {"行の台帳.csv", "参照の宣言.csv", "問いの一覧.csv",
                         "理由コード.csv"}
    out = capsys.readouterr().out
    assert "点数も割合も返さない" in out


def test_init_template_shows_two_values(tmp_path) -> None:
    """ひな型の 4 枚は、そのまま読めて、参照されていると一次の空白が出る。"""
    paths = H.init(tmp_path / "ひな型")
    t = H.idle_rows(H.Ledger.load(paths[0]), H.Declarations.load(paths[1]),
                    H.Questions.load(paths[2]), H.Registry.load(paths[3]))
    assert t.report.ok and t.rule_denominator() == 3 and t.denominator == 3
    assert t.six() == {"参照されている": 2, "どの参照元からも参照されない": 0,
                       "参照元は在るが問いから呼ばれない": 0,
                       "参照の宣言が無い": 1, "照合専用": 0,
                       "基準日より後に有効になる行": 0}
    assert t.aside_denominator() == 0 and t.stopped() == {}
