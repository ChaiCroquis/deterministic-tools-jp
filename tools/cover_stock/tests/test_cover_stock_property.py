"""cover_stock の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 読んだ範囲は 2 通りしかない。
  (a) (レシピ × 年)ごとに 5 値が 1 つだけ付き、5 値の合計が レシピ数 × 年の数 に等しく、
      止まった理由別の合計が止まったの件数に、そろった数表 + 引けない理由別の合計が読んだ
      数表の延べ数に等しく、そろわない年に挙がる理由は 4 つのうちのどれかで、**収録開始を
      1 年後ろへずらしても全部そろうへ入ってくる年は 1 件も無く**、判定部分に絶対パスが
      入らず、3 枚の行順を入れ替えても同じバイト列になる
  (b) 1 件も読まずに理由コードが返る(読んだ年や指紋を取りに行くと例外)
どちらの場合も、この部品は在庫表もレシピ表も年の一覧も 1 文字も書き換えない。

数表を 1〜3 枚作って年の数え方・端の確度・終了の開き・穴を振り、レシピを 1〜3 本、各レシピが
要る数表を 1〜3 枚引く。年を 1〜2 件、年の数え方を 2 種から引く。さらに 3 割くらいの確率で
1 か所だけ崩す(出典を空にする / 同じ数表 id を 2 行書く)。derandomize=True で毎回同じ入力列を
使い、database=None で見つけた例を保存しない。

**年の覆いの判定はテストの側で別に実装している**(部品の look を呼ばない)。2 本目は「収録の
外の年には、近くの年の行を当てない」ことを見ている(穴を埋める経路・直近の端で代用する経路が
無い、の物理形)。
"""
from __future__ import annotations

import datetime
import sys
from pathlib import Path

import pytest
from hypothesis import event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import cover_stock as C  # noqa: E402

SOURCE = "合成の出典メモ(架空)L1"
MONTH = {"暦年": 1, "年度(3 月開始)": 3, "年度(4 月開始)": 4, "年度(8 月開始)": 8}
KAZOEKATA = ("暦年", "年度(4 月開始)")
HAJIME = ("2017-04-01", "2020-01-01", "2024-03-01", "2025-04-01")
OWARI = ("", "2026-01-01", "2027-04-01")
ANA = ("", "2021-01-01/2022-01-01", "2024-01-01/2024-07-01")
TOSHI = ("2017", "2021", "2024", "2026")

KOWASHIKATA = ("出典を空にする", "同じ数表 id を 2 行書く")


def covers(c_from: str, c_to: str, kind: str, edge: str, holes: str,
           year: int) -> str:
    """年の覆いの、テスト側の別実装(部品の look は呼ばない)。"""
    begin = datetime.date(*(int(x) for x in c_from.split("-")))
    finish = datetime.date(*(int(x) for x in c_to.split("-"))) if c_to else None
    start = datetime.date(year, MONTH[kind], 1)
    end = datetime.date(year + 1, MONTH[kind], 1)
    pairs = [tuple(datetime.date(*(int(x) for x in half.split("-")))
                   for half in part.split("/"))
             for part in holes.split(";") if part]
    if start < begin:
        return C.UNAVAILABLE[0]
    if any(start < b and a < end for a, b in pairs):
        return C.UNAVAILABLE[1]
    if finish is not None and end > finish:
        return C.UNAVAILABLE[2]
    edge_year = datetime.date(begin.year, MONTH[kind], 1)
    boundary = (edge_year if edge_year > begin
                else datetime.date(begin.year + 1, MONTH[kind], 1))
    if edge == C.EDGES[1] and start < boundary:
        return C.UNAVAILABLE[3]
    return C.AVAILABLE


@st.composite
def 合成の3枚(draw: st.DrawFn) -> dict[str, object]:
    """収録の在庫表 / 計算のレシピ表 / 数える年の一覧(と崩し方)を作る。"""
    zaiko: list[list[str]] = []
    for i in range(draw(st.integers(1, 3))):
        c_to = draw(st.sampled_from(OWARI))
        zaiko.append([f"T{i + 1:02d}", f"合成の領域{i + 1}(架空)",
                      draw(st.sampled_from(HAJIME)), c_to,
                      C.OPEN_ENDS[1] if c_to else C.OPEN_ENDS[0],
                      draw(st.sampled_from(KAZOEKATA)),
                      draw(st.sampled_from(C.EDGES)),
                      draw(st.sampled_from(ANA)), SOURCE])
    table_ids = [row[0] for row in zaiko]

    recipe: list[list[str]] = []
    for i in range(draw(st.integers(1, 3))):
        ids = draw(st.lists(st.sampled_from(table_ids), min_size=1,
                            max_size=3, unique=True))
        recipe.append([f"R{i + 1:02d}", "|".join(ids), SOURCE])

    years = draw(st.lists(st.tuples(st.sampled_from(TOSHI),
                                    st.sampled_from(KAZOEKATA)),
                          min_size=1, max_size=2, unique=True))
    nen = [[f"Y{i + 1:02d}", year, kind, SOURCE, ""]
           for i, (year, kind) in enumerate(sorted(years))]
    nen[0][4] = C.SWAPS[0]

    kowasu = draw(st.sampled_from([None] * 7 + list(KOWASHIKATA)))
    if kowasu == "出典を空にする":
        zaiko[0][8] = ""
    elif kowasu == "同じ数表 id を 2 行書く":
        zaiko.append(list(zaiko[0]))

    def csv(head: tuple[str, ...], body: list[list[str]]) -> str:
        return "\n".join([",".join(head)] + [",".join(r) for r in body])

    return {"zaiko": csv(C.ZAIKO_COLUMNS, zaiko),
            "recipe": csv(C.RECIPE_COLUMNS, recipe),
            "nen": csv(C.YEARS_COLUMNS, nen),
            "zaiko_rows": zaiko, "recipe_rows": recipe, "nen_rows": nen,
            "kowasu": kowasu}


@settings(max_examples=200, derandomize=True, database=None, deadline=None)
@given(plan=合成の3枚())
def test_いつも成り立つこと_読んだ年か理由コードか(plan: dict[str, object]) -> None:
    stock = C.Stock.parse(plan["zaiko"])            # type: ignore[arg-type]
    recipes = C.Recipes.parse(plan["recipe"])       # type: ignore[arg-type]
    years = C.Years.parse(plan["nen"])              # type: ignore[arg-type]
    t = C.cover_stock(stock, recipes, years)

    expect_stop = plan["kowasu"] is not None
    c = t.counts()
    five = c["5 値"]
    assert c["計算のレシピ表の行数"] == len(plan["recipe_rows"])   # type: ignore[arg-type]
    assert c["数える年の数"] == len(plan["nen_rows"])              # type: ignore[arg-type]
    assert c["分母(レシピ数 × 年の数)"] == t.denominator
    assert sum(five.values()) == len(t.pairs)                     # type: ignore[union-attr]
    # 表が揃う前に止まったら 1 件も読まない。読んだなら(レシピ × 年)と 1 対 1 で付く
    assert len(t.pairs) in (0, t.denominator)
    assert {p.result for p in t.pairs} <= set(C.RESULTS)

    for p in t.pairs:
        recipe = next(r for r in recipes.items if r.recipe_id == p.recipe_id)
        if p.result == C.RESULTS[3]:
            assert p.reason in C.PAIR_REASONS and p.sheets == ()
            continue
        assert p.reason == ""
        assert [t_id for t_id, _ in p.sheets] == sorted(recipe.table_ids)
        for table_id, verdict in p.sheets:
            sheet = stock.of(table_id)
            assert verdict == covers(sheet.covered_from, sheet.covered_to,
                                     sheet.year_kind, sheet.edge_confidence,
                                     sheet.holes, int(p.year))
        blocked = {v for _, v in p.sheets if v != C.AVAILABLE}
        assert blocked <= set(C.UNAVAILABLE)
        want = (C.RESULTS[0] if not blocked else
                C.ASIDE if blocked == {C.UNAVAILABLE[3]} else
                C.RESULTS[1] if p.available else C.RESULTS[2])
        assert p.result == want

    if expect_stop:
        event("(b) 1 件も読まずに止まった")
        assert t.report.ok is False and t.report.pending
        assert {p.reason for p in t.report.pending} <= set(C.TABLE_REASONS)
        for call in (lambda: t.verdict, t.judgement_bytes, t.sha256):
            with pytest.raises(RuntimeError):
                call()
    else:
        event("(a) 読んだ")
        assert t.report.ok is True
        assert sum(five.values()) == t.denominator
        assert sum(t.by_reason().values()) == five[C.RESULTS[3]]
        assert t.available_sheets() + sum(t.by_unavailable().values()) \
            == t.counted_sheets()
        body = t.judgement_bytes().decode("utf-8")
        for word in ("読んだ条件", "絶対パス", str(ROOT)):
            assert word not in body
        how = years.swap or C.SWAPS[0]
        again = C.cover_stock(stock.swapped(how), recipes.swapped(how),
                              years.swapped(how))
        assert again.sha256() == t.sha256()
        assert again.judgement_bytes() == t.judgement_bytes()
        # 収録開始を後ろへずらすと、全部そろうへ入ってくる年は 1 件も無い
        for sheet in stock.ordered:
            shifted = C.cover_stock(stock.start_shifted(sheet.table_id), recipes, years)
            assert len(shifted.by_result(C.RESULTS[0])) <= len(t.by_result(C.RESULTS[0]))

    # どちらの場合も入力は 1 文字も書き換わらない
    assert C.Stock.parse(plan["zaiko"]).items == stock.items        # type: ignore[arg-type]
    assert C.Recipes.parse(plan["recipe"]).items == recipes.items   # type: ignore[arg-type]
    assert C.Years.parse(plan["nen"]).items == years.items          # type: ignore[arg-type]


@settings(max_examples=300, derandomize=True, database=None)
@given(c_from=st.sampled_from(HAJIME), c_to=st.sampled_from(OWARI),
       kind=st.sampled_from(KAZOEKATA), edge=st.sampled_from(C.EDGES),
       holes=st.sampled_from(ANA), year=st.sampled_from(TOSHI))
def test_収録の外の年に近くの行を当てない(c_from: str, c_to: str, kind: str, edge: str,
                                          holes: str, year: str) -> None:
    """表の外の年には、近くの年の行を当てない。そろうは「その年の全部が収録の中」のときだけ。

    端が仮置きでも、穴が在っても、収録を始める前の年は いつも 収録を始める前 で返る(順番を
    入れ替えて穴や端の確度を先に見ると、同じ年が別の理由で返ってしまう)。
    """
    zaiko = "\n".join([",".join(C.ZAIKO_COLUMNS),
                       f"T01,合成の領域甲(架空),{c_from},{c_to},"
                       f"{C.OPEN_ENDS[1] if c_to else C.OPEN_ENDS[0]},{kind},{edge},"
                       f"{holes},{SOURCE}"])
    recipe = "\n".join([",".join(C.RECIPE_COLUMNS), f"R01,T01,{SOURCE}"])
    nen = "\n".join([",".join(C.YEARS_COLUMNS),
                     f"Y01,{year},{kind},{SOURCE},{C.SWAPS[0]}"])
    stock = C.Stock.parse(zaiko)
    t = C.cover_stock(stock, C.Recipes.parse(recipe), C.Years.parse(nen))
    assert t.report.ok
    p = t.pairs[0]
    if stock.items[0].issues():
        # 穴が収録範囲の外にある等、数表そのものの不備は 1 件も数えずに止まる
        assert p.result == C.RESULTS[3] and p.sheets == () and p.reason
        return
    verdict = p.sheets[0][1]
    assert verdict == covers(c_from, c_to, kind, edge, holes, int(year))

    begin = datetime.date(*(int(x) for x in c_from.split("-")))
    finish = datetime.date(*(int(x) for x in c_to.split("-"))) if c_to else None
    start = datetime.date(int(year), MONTH[kind], 1)
    end = datetime.date(int(year) + 1, MONTH[kind], 1)
    if start < begin:
        assert verdict == C.UNAVAILABLE[0]           # 穴も端の確度も先に見ない
        assert p.result == C.RESULTS[2]
    if verdict == C.AVAILABLE:
        assert begin <= start and (finish is None or end <= finish)
        assert p.result == C.RESULTS[0] and p.available == 1
    else:
        assert p.result in (C.RESULTS[1], C.RESULTS[2], C.ASIDE)
        assert p.available == 0
