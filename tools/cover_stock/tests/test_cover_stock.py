"""cover_stock のテスト。合成 fixture は `fixtures/` に commit 済(実データ・実在の値は入れない)。

test_measure_* が記事に載せた数値の出どころで、assert で固定している(値が変われば記事も変える前提)。
測っているものは 6 つある。

  (1) 11 レシピ × 7 年 = 77 件が 5 値に分かれ、引けない理由別・止まった理由別の件数と 2 つの
      分母(レシピ数 × 年の数 / 数表の延べ数 × 年の数)の内訳が付く側
  (2) 引けない理由が 4 つに分かれて残る側(1 つの終了コードに潰れない)。= この記事の骨
  (3) 収録開始を 1 年後ろへずらすと、全部そろうへ入ってくる年が 1 件も無く、減った分が
      一部だけ / 1 つもそろわない / 別枠 へそのまま移る側
  (4) 端の確度を「仮置き」から「実値」に替えると、別枠の年が全部そろうへ移る側
      (= 仮置きの端を確定と読むと在庫が広く見えることの実測)
  (5) 年の数え方が違う数表と年は、換算せずに止まる側
  (6) 5 値の件数の合計 = レシピ数 × 年の数、そろった数表 + 引けない理由別の合計 = 読んだ数表

(1) の 5 値は、テストの側でも 3 枚の表の行から直に組み立てて確かめている(部品の判定を呼ばず、
fixture の行から別に数える)。
"""
from __future__ import annotations

import ast
import datetime
import hashlib
import io
import re
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
import cover_stock as C  # noqa: E402
import make_fixtures as M  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの -> その行に在るはずの語
REAL_SOURCES = {
    M.SRC_CHOKKIN: "直近の行を返すことは決してしない",
    M.SRC_SUITEI: "日付を推定して入れない",
}

# 形容の語(出力にも実装にも持たせない = 数値が無いなら多寡を書かない)
KEIYOU = ("多い", "少ない", "ほとんど", "かなり", "著しく", "急いで")

# 持たせていない経路の名前(実装に 1 つも無いことを見る)
MOTANAI = ("換算", "eval", "exec", "網羅率", "おすすめ", "推奨", "補完", "既定値",
           "とりあえず", "だいたい", "直近の端")


def path_of(name: str) -> Path:
    return FIX / "kowashita" / f"{name[2:]}.csv" if name.startswith("K:") \
        else FIX / f"{name}.csv"


def pull(z: str = "zaiko_a", r: str = "recipe_a", n: str = "nen_a") -> C.Tally:
    return C.cover_stock(C.Stock.load(path_of(z)), C.Recipes.load(path_of(r)),
                         C.Years.load(path_of(n)))


def pair_of(t: C.Tally, recipe_id: str, year_id: str) -> C.Pair:
    return next(p for p in t.pairs
                if p.recipe_id == recipe_id and p.year_id == year_id)


# ---------------------------------------------------------------- 別実装(テスト側)

MONTH = {"暦年": 1, "年度(3 月開始)": 3, "年度(4 月開始)": 4, "年度(8 月開始)": 8}


def day_of(text: str) -> datetime.date | None:
    """テスト側の別実装。ISO の日付として暦に在る日だけ返す。"""
    if not re.fullmatch(r"(19|20)\d{2}-\d{2}-\d{2}", text):
        return None
    try:
        return datetime.date(*(int(x) for x in text.split("-")))
    except ValueError:
        return None


def expect_five(zaiko: list[list[str]], recipe: list[list[str]],
                nen: list[list[str]]) -> dict[str, int]:
    """3 枚の行から 5 値を別に数える(部品の look / judge / counts を呼ばない)。"""
    sheets = {row[0]: row for row in zaiko}
    five = {r: 0 for r in C.RESULTS}
    for _, ids, _ in ((r[0], r[1], r[2]) for r in recipe):
        wanted = [x for x in ids.split("|") if x]
        for _, year, kind, _, _ in nen:
            start, end = (datetime.date(int(year) + k, MONTH[kind], 1) for k in (0, 1))
            found: list[str] = []
            stop = not wanted
            for table_id in wanted:
                row = sheets.get(table_id)
                if row is None:
                    stop = True
                    break
                _, _, c_from, c_to, open_end, y_kind, edge, holes, _ = row
                begin, finish = day_of(c_from), day_of(c_to)
                pairs = [tuple(day_of(x) for x in part.split("/"))
                         for part in holes.split(";") if part]
                if (y_kind not in MONTH or not edge or begin is None
                        or (open_end == "開いている" and c_to)
                        or (open_end == "閉じている"
                            and (finish is None or begin >= finish))
                        or any(None in p for p in pairs)
                        or any(p[0] < begin or (finish and p[1] > finish)
                               for p in pairs)
                        or y_kind != kind):
                    stop = True
                    break
                if start < begin:
                    found.append("前")
                elif any(start < b and a < end for a, b in pairs):
                    found.append("穴")
                elif open_end == "閉じている" and finish and end > finish:
                    found.append("後")
                elif edge == "仮置き" and start < (
                        datetime.date(begin.year, MONTH[y_kind], 1)
                        if datetime.date(begin.year, MONTH[y_kind], 1) > begin
                        else datetime.date(begin.year + 1, MONTH[y_kind], 1)):
                    found.append("仮")
                else:
                    found.append("可")
            if stop:
                five[C.RESULTS[3]] += 1
            elif all(v == "可" for v in found):
                five[C.RESULTS[0]] += 1
            elif set(found) - {"可"} == {"仮"}:
                five[C.ASIDE] += 1
            elif "可" in found:
                five[C.RESULTS[1]] += 1
            else:
                five[C.RESULTS[2]] += 1
    return five


# ---------------------------------------------------------------- 記事に載せた数値

def test_measure_77_pairs_split_into_five() -> None:
    """(1) 11 レシピ × 7 年 = 77 件が 5 値に分かれ、2 つの分母の内訳が付く。"""
    t = pull()
    c = t.counts()
    assert c["収録の在庫表の行数(数表の数)"] == 10
    assert c["計算のレシピ表の行数"] == 11
    assert c["数える年の数"] == 7
    assert c["分母(レシピ数 × 年の数)"] == 77
    assert c["5 値"] == {"レシピの要る数表が全部そろう": 12, "一部だけそろう": 2,
                         "1 つもそろわない": 4, "止まった": 57,
                         "端が仮置きの行に依存している": 2}
    assert c["5 値"] == expect_five(M.zaiko_rows(), M.recipe_rows(), M.nen_rows())
    assert t.sheet_denominator == 105
    assert t.counted_sheets() == 30 and t.available_sheets() == 20
    assert [k for k in c if "率" in k] == ["網羅率を出さない"]   # 率は返らない
    assert not any(isinstance(v, float) for v in c.values())
    assert "77 件" in str(c["分母に含めたもの"])
    assert "5 値の合計 77 / 分母 77" in str(c["件数の合計の検算"])
    print(f"[measure] zaiko_a / recipe_a / nen_a: 11 レシピ × 7 年 = 77 件"
          f" → 5 値 {c['5 値']}")
    print(f"[measure] 引けない理由別(数表の延べ数)= {c['引けない理由別(数表の延べ数)']}"
          "(分母は 数表の延べ数 × 年の数 = 105。読んだ数表は 30、そろった数表は 20。"
          "率は単独では返らない)")
    print(f"[measure] 止まった理由別 = {c['止まった理由別']}")


def test_measure_four_reasons_do_not_collapse() -> None:
    """(2) 引けない理由が 4 つに分かれて残る(= この記事の骨)。"""
    t = pull()
    assert t.by_unavailable() == {"収録を始める前": 4, "収録の中の穴": 2,
                                  "収録の終わりより後": 1,
                                  "端が仮置きで確定できない": 3}
    assert pair_of(t, "R04", "Y05").detail == "T04=収録を始める前|T07=収録を始める前"
    assert pair_of(t, "R02", "Y02").detail == "T01=そろう|T06=収録の中の穴"
    assert pair_of(t, "R02", "Y04").detail == "T01=そろう|T06=収録の終わりより後"
    assert pair_of(t, "R05", "Y05").result == C.ASIDE
    assert pair_of(t, "R11", "Y06").detail == "T08=収録の中の穴"
    # 同じ 1 枚の在庫表でも、年が 1 つ違うだけで理由が変わる
    assert pair_of(t, "R02", "Y03").result == C.RESULTS[0]
    print("[measure] 引けない 10 件は 4 つの理由に分かれた(収録を始める前 4 / 収録の中の"
          "穴 2 / 収録の終わりより後 1 / 端が仮置きで確定できない 3)。同じ組を 1 つの"
          "終了コードに潰さない")
    print("[measure] R02(2 枚要るレシピ)は、2024 暦年 で 全部そろう、2010 暦年 で 穴、"
          "2026 暦年 で 収録の終わりより後 = 年を 1 つ変えると理由が変わる")


def test_measure_shifting_the_start_never_widens_cover() -> None:
    """(3) 収録開始を 1 年後ろへずらすと、全部そろうへ入ってくる年は 1 件も無い。"""
    t = pull()
    probe = C.start_probe(C.Stock.load(path_of("zaiko_a")),
                          C.Recipes.load(path_of("recipe_a")),
                          C.Years.load(path_of("nen_a")), t)
    assert probe["合うか"] is True
    rows = {r["数表"]: r for r in probe["数表ごと"]}
    assert all(r["全部そろうへ入ってきた件数"] == 0 for r in rows.values())
    assert rows["T06"]["全部そろうの減り"] == 1
    assert rows["T06"]["全部そろうから移った先"] == {
        "レシピの要る数表が全部そろう → 一部だけそろう": 1}
    assert rows["T04"]["全部そろうの減り"] == 2
    assert rows["T04"]["全部そろうから移った先"] == {
        "レシピの要る数表が全部そろう → 一部だけそろう": 2}
    assert rows["T01"]["全部そろうの減り"] == 0
    print("[measure] 収録開始を 1 年後ろへずらす(数表 10 枚を 1 枚ずつ): 全部そろうへ"
          "入ってきた年は 10 枚とも 0 件。T06 は 全部そろう −1 → 一部だけ +1、T04 は"
          " −2 → 一部だけ +2")
    print("[measure] T05 / T08(端が仮置き)をずらすと 別枠 −1 → 1 つもそろわない +1。"
          "T01 / T02 / T03 / T07 / T09 / T10 は 0 件のまま(数える年の外なので動かない)")


def test_measure_provisional_edge_read_as_actual() -> None:
    """(4) 端の確度を「仮置き」から「実値」に替えると、別枠の年が全部そろうへ移る。"""
    t = pull()
    probe = C.edge_probe(C.Stock.load(path_of("zaiko_a")),
                         C.Recipes.load(path_of("recipe_a")),
                         C.Years.load(path_of("nen_a")), t)
    assert probe["書き換えた数表"] == ["T05", "T08"]
    assert probe["別枠だった件数"] == 2
    assert probe["全部そろうへ移った件数"] == 2
    assert probe["書き換えた後の別枠"] == 0
    assert probe["移った先"] == {
        "1 つもそろわない → 一部だけそろう": 1,
        "端が仮置きの行に依存している → レシピの要る数表が全部そろう": 2}
    assert probe["分母(レシピ数 × 年の数)"] == 77
    assert probe["合うか"] is True
    print("[measure] 端の確度を 仮置き → 実値 に替える(T05 / T08 の 2 枚): 別枠 2 件 / 77"
          " が全部そろうへ移り、別枠は 0 件になる。ほかに 1 件が 1 つもそろわない → "
          "一部だけそろう へ動いた(動いた年は計 3 件 / 77)")
    print("[measure] 仮置きの端を確定と読むと、全部そろうは 12 件 → 14 件に見える"
          "(値も日付も 1 文字も変えていない。替えたのは端の確度の欄だけ)")


def test_measure_year_kind_is_not_converted() -> None:
    """(5) 年の数え方が違う数表と年は、換算せずに止まる。"""
    t = pull()
    assert t.by_reason()["年の数え方が違う"] == 32
    stopped = pair_of(t, "R02", "Y06")       # 暦年の 2 枚を 年度(4 月開始)で数える
    assert stopped.result == C.RESULTS[3]
    assert stopped.reason == "年の数え方が違う"
    assert "換算しない" in stopped.detail
    # 3 枚の数表が 3 通りの数え方を宣言しているレシピは、どの年でも止まる
    assert all(pair_of(t, "R03", y.year_id).reason == "年の数え方が違う"
               for y in C.Years.load(path_of("nen_a")).ordered)
    assert "換算" not in str(t.counts()["年の数え方を換算しない"]).replace(
        "換算せずに止まる", "").replace("換算表も換算の引数も無い", "")
    print("[measure] 年の数え方が違う組は 32 件 / 77 が止まった(換算しない)。数表 3 枚が"
          " 3 通りの数え方を宣言している R03 は、7 年のうち 7 年とも止まる")
    print("[measure] 止まった 57 件は 5 つの理由に分かれた(年の数え方が違う 32 / 参照先が"
          "在庫表に無い 7 / レシピに数表 id が無い 7 / 年の数え方が空 7 / 端の確度が空 4)")


def test_measure_counts_add_up() -> None:
    """(6) 5 値の合計 = レシピ数 × 年の数、そろった数表 + 引けない = 読んだ数表。"""
    out = C.verify(C.Stock.load(path_of("zaiko_a")),
                   C.Recipes.load(path_of("recipe_a")),
                   C.Years.load(path_of("nen_a")))
    assert out["ok"] is True
    kensan = out["件数の検算"]
    assert kensan["5 値の合計"] == kensan["分母(レシピ数 × 年の数)"] == 77
    assert kensan["止まった理由別の合計"] == 57
    assert kensan["そろった数表"] + kensan["引けない理由別の合計"] == 30
    assert kensan["読んだ数表"] == 30 and kensan["数表ごとの分母"] == 105
    assert out["sha256"] == out["2 回目の sha256"] == out["入れ替えた 3 枚の sha256"]
    print(f"[measure] 2 回 + 3 枚の行順を逆順に入れ替えて読み直し: 判定部分の sha256 は"
          f" 3 回とも同じ(3/3 一致、先頭 12 桁 {out['sha256'][:12]})")
    print("[measure] 件数の検算: 5 値の合計 77 = 分母 77、止まった理由別の合計 57 = "
          "止まった 57、そろった数表 20 + 引けない 10 = 読んだ数表 30(数表ごとの分母は"
          " 105 で、止まった件の数表は数えない)")


def test_measure_timeline_is_one_row_per_event() -> None:
    """在庫の年表は 1 行 1 件(収録の開始 / 終わり / 穴の開始 / 穴の終わり を混ぜない)。"""
    stock = C.Stock.load(path_of("zaiko_a"))
    rows, skipped = stock.timeline()
    assert skipped == []
    assert len(rows) == 16
    kinds = {e: sum(1 for r in rows if r["出来事"] == e) for e in C.EVENTS}
    assert kinds == {"収録の開始": 10, "収録の終わり": 2, "穴の開始": 2, "穴の終わり": 2}
    assert [r["日付"] for r in rows] == sorted(r["日付"] for r in rows)
    assert all(r["出典"] for r in rows)
    starts = [r for r in rows if r["出来事"] == "収録の開始"]
    assert starts[0]["日付"] == "1989-01-01" and starts[-1]["日付"] == "2025-04-01"
    assert int(starts[-1]["日付"][:4]) - int(starts[0]["日付"][:4]) == 36
    assert len({r["日付"][5:7] for r in starts}) == 4      # 1 月 / 3 月 / 4 月 / 8 月
    assert sum(1 for r in rows if r["端の確度"] == "仮置き") == 2
    print("[measure] 在庫の年表は 16 行(収録の開始 10 / 収録の終わり 2 / 穴の開始 2 / "
          "穴の終わり 2)。1 行 1 件で、出来事を 1 つの欄に混ぜない")
    print("[measure] 収録開始がいちばん古い数表と新しい数表の差は 36 年、収録開始の月は"
          " 4 通り(1 月 / 3 月 / 4 月 / 8 月)、端が仮置きの行は 2 件")


def test_measure_no_clock_and_no_float() -> None:
    """判定部分に環境が入らない。今日を読む経路も、値を計算する経路も持たない。"""
    src = (ROOT / "cover_stock.py").read_text(encoding="utf-8")
    # 文字列・コメント・f 文字列の地の文を落として、動く側のコードだけを残す
    skip = {tokenize.STRING, tokenize.COMMENT} | {
        getattr(tokenize, n) for n in ("FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END")
        if hasattr(tokenize, n)}
    code = "".join(t.string for t in
                   tokenize.generate_tokens(io.StringIO(src).readline)
                   if t.type not in skip)
    for word in ("now(", "today(", "time(", "float(", "eval(", "exec(",
                 "subprocess", "random", "platform"):
        assert word not in code, word
    tree = ast.parse(src)
    imported = sorted({n.names[0].name.split(".")[0] for n in ast.walk(tree)
                       if isinstance(n, ast.Import)}
                      | {n.module.split(".")[0] for n in ast.walk(tree)
                         if isinstance(n, ast.ImportFrom) and n.module})
    assert imported == ["__future__", "argparse", "csv", "dataclasses", "datetime",
                        "hashlib", "json", "pathlib", "re", "sys"]
    t = pull()
    body = t.judgement_bytes().decode("utf-8")
    for word in (str(FIX), "読んだ条件", str(datetime.date.today().year) + "-"):
        assert word not in body or word == "2026-"   # 年は入力の年として入る
    assert str(FIX) not in body
    for word in KEIYOU + MOTANAI:
        assert word not in code, word
    print(f"[measure] 部品が import している module は {len(imported)} 個で、float / "
          "eval / exec / subprocess / random / platform / 今日を読む呼び出しは 0 件")
    print("[measure] 判定部分のバイト列に絶対パスは入らない(読んだ条件は別の欄)。"
          "形容の語 6 つと、持たせていない経路の語 11 個は実装に 0 件")


def read_kowashita(name: str) -> tuple[str, set[str]]:
    """崩した表 1 枚を基準の 3 枚に差し込んで読む。返るのは 読み方 と 理由コードの集合。"""
    args = {"zaiko": "zaiko_a", "recipe": "recipe_a", "nen": "nen_a"}
    args[name.split("_")[0]] = f"K:{name}"
    try:
        t = pull(z=args["zaiko"], r=args["recipe"], n=args["nen"])
    except C.ReadError:
        return "表として読めない", set()
    if not t.report.ok:
        return "1 件も読まずに止まった", {p.reason for p in t.report.pending}
    return "読んだ", set(t.by_reason())


def test_measure_stop_reason_codes_all_reachable(monkeypatch) -> None:
    """止まる理由コード 16 個すべてに道がある(合成 3 枚 + 崩した表 + 差し替えた実装)。"""
    seen = set(pull().by_reason())
    assert seen == {"レシピが参照する数表 id が在庫表に無い", "レシピに数表 id が 1 つも無い",
                    "年の数え方が空", "年の数え方が違う", "端の確度が空"}
    base, group = set(seen), {}
    for name in M.kowashita():
        how, reasons = read_kowashita(name)
        seen |= reasons
        key = how if how != "読んだ" else (
            "読んだ(理由コードが増えた)" if reasons - base else "読んだ(変化なし)")
        group.setdefault(key, []).append(name)
    assert {k: len(v) for k, v in sorted(group.items())} == {
        "1 件も読まずに止まった": 4, "表として読めない": 22,
        "読んだ(変化なし)": 1, "読んだ(理由コードが増えた)": 6}
    # 入れ替え方の宣言が無い表だけは、読めて止まらず、verify のときだけ読めなくなる
    assert group["読んだ(変化なし)"] == ["nen_swap_nashi"]
    with pytest.raises(C.ReadError):
        C.verify(C.Stock.load(path_of("zaiko_a")), C.Recipes.load(path_of("recipe_a")),
                 C.Years.load(path_of("K:nen_swap_nashi")))
    assert set(C.TABLE_REASONS) | set(C.PAIR_REASONS) <= seen

    stock, recipes = C.Stock.load(path_of("zaiko_a")), C.Recipes.load(path_of("recipe_a"))
    years = C.Years.load(path_of("nen_a"))
    count = {"n": 0}

    def flaky(self) -> str:            # 2 回目で違うバイト列を出す実装に差し替える
        count["n"] += 1
        return f"{count['n']:064d}"

    monkeypatch.setattr(C.Tally, "sha256", flaky)
    out = C.verify(stock, recipes, years)
    seen |= {p["理由コード"] for p in out["pending"]}
    monkeypatch.undo()
    monkeypatch.setattr(C.Tally, "by_reason", lambda self: {})
    out2 = C.verify(stock, recipes, years)
    seen |= {p["理由コード"] for p in out2["pending"]}
    assert seen == set(C.STOP_REASONS)
    assert len(C.STOP_REASONS) == 16
    print("[measure] 止まる理由コード 16 個すべてに道がある(合成 3 枚で 5 個 + 崩した表"
          " 10 枚で 8 個 + 差し替えた実装 2 本で 3 個)")
    print("[measure] 崩した表 33 枚の内訳 = 表として読めない 22 枚 / 1 件も読まずに止まる"
          " 4 枚 / 読めて理由コードが増える 6 枚 / 読めて verify だけが止まる 1 枚"
          "(「表として読めない」は理由コードに混ぜない)")


def test_inputs_are_never_written() -> None:
    """読む前と後で、入力に置いた全ファイルの sha256 が変わらない。"""
    files = sorted(p for p in FIX.rglob("*.csv"))
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    t = pull()
    C.verify(C.Stock.load(path_of("zaiko_a")), C.Recipes.load(path_of("recipe_a")),
             C.Years.load(path_of("nen_a")))
    t.counts(), t.table(), t.timeline(), t.sha256()
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
    """CLI は stock / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = C.build_parser()
    sub = next(a for a in ap._actions if a.choices)
    assert tuple(sub.choices) == C.SUBCOMMANDS == ("stock", "check", "verify", "init")
    for name, parser in sub.choices.items():
        flags = [o for a in parser._actions for o in a.option_strings]
        assert flags == ["-h", "--help"], (name, flags)


def test_cli_exit_codes(tmp_path, capsys) -> None:
    """そろわない年が在れば 3、表として読めなければ 2、ひな型は 0。"""
    args = [str(FIX / "zaiko_a.csv"), str(FIX / "recipe_a.csv"), str(FIX / "nen_a.csv")]
    assert C.main(["check", *args]) == 3
    assert C.main(["stock", *args]) == 3
    assert C.main(["verify", *args]) == 0          # verify は検算が合えば 0
    broken = [str(FIX / "kowashita" / "zaiko_0gyou.csv"), args[1], args[2]]
    assert C.main(["check", *broken]) == 2
    assert C.main(["init", str(tmp_path / "ひな型")]) == 0
    made = sorted(p.name for p in (tmp_path / "ひな型").iterdir())
    assert made == ["収録の在庫表.csv", "数える年の一覧.csv", "計算のレシピ表.csv"]
    out = capsys.readouterr().out
    assert "網羅率を出さない" in out


def test_init_template_shows_the_year_kind_trap() -> None:
    """ひな型の 3 枚は、そのまま読めて、年の数え方が違う組だけが止まる。"""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        paths = C.init(d)
        t = C.cover_stock(C.Stock.load(paths[0]), C.Recipes.load(paths[1]),
                          C.Years.load(paths[2]))
        assert t.report.ok
        five = {r: len(t.by_result(r)) for r in C.RESULTS}
        assert t.denominator == 4 and sum(five.values()) == 4
        assert five[C.RESULTS[0]] == 2 and five[C.RESULTS[3]] == 2
        assert t.by_reason() == {"年の数え方が違う": 2}


def test_no_nearest_row_for_years_outside_cover() -> None:
    """表の外の年に、近くの年の行を当てない(そろうが 1 件も出ない)。"""
    zaiko = "\n".join([",".join(C.ZAIKO_COLUMNS),
                       "T01,合成の領域甲(架空),2030-01-01,,開いている,暦年,実値,,"
                       "合成の出典メモ(架空)L1"])
    recipe = "\n".join([",".join(C.RECIPE_COLUMNS), "R01,T01,合成の出典メモ(架空)L2"])
    nen = "\n".join([",".join(C.YEARS_COLUMNS),
                     "Y01,2029,暦年,合成の出典メモ(架空)L3,逆順",
                     "Y02,2030,暦年,合成の出典メモ(架空)L4,"])
    t = C.cover_stock(C.Stock.parse(zaiko), C.Recipes.parse(recipe), C.Years.parse(nen))
    assert [p.detail for p in t.pairs] == ["T01=収録を始める前", "T01=そろう"]
    assert t.by_unavailable() == {"収録を始める前": 1}
