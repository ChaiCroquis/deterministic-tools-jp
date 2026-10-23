"""handoff_edge の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 読んだ範囲は 2 通りしかない。
  (a) 問い 1 つごとに 5 値が 1 つだけ付き、5 値の合計が問いの数に等しく、節の判定別の合計が
      判定した節の延べ数に等しく(延べ数を超えず)、**別枠の問いは節を 1 つも判定せず**、
      状態を 未実装 → 収録済 に替えると「返るが一手残る → 道具の中で済む」の 1 本しか動かず、
      節を宣言表から外すと別枠へしか動かず、判定部分に絶対パスが入らず、3 枚の行順を入れ替えても
      同じバイト列になる
  (b) 1 件も判定せずに理由コードが返る(判定した問いや指紋を取りに行くと例外)
どちらの場合も、この部品は宣言表もレシピ表も問いの一覧も 1 文字も書き換えない。

節を 1〜3 つ作って(状態・出口・残る一手の 3 つ組は宣言として整合するものから引く)、レシピを
1〜3 本、各レシピが要る節を 1〜3 つ引く。3 割くらいの確率で 1 か所だけ崩す(出典を空にする /
同じ節 id を 2 行書く / 収録済の行に残る一手を書く / 収録済の出口を止まるにする / レシピの節 id
を空にする)。derandomize=True で毎回同じ入力列を使い、database=None で見つけた例を保存しない。

**節の判定と問いの 5 値はテストの側で別に実装している**(部品の verdict / judge を呼ばない)。
2 本目は「宣言表に無い節に収録済を当てない」ことを見ている(既定を当てる経路が無い、の物理形)。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from hypothesis import event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import handoff_edge as H  # noqa: E402

SOURCE = "合成の出典メモ(架空)L1"

# 宣言として整合する(状態, 出口, 残る一手)の 3 つ組。ここから引く限り理由コードは出ない
TRIPLES = (
    ("収録済", "値が返る", ""),
    ("未実装", "値が返る", "上限を当てる"),
    ("未実装", "止まる", "式の実装を足す"),
    ("未対応", "止まる", "乗率を取ってくる"),
    ("未対応", "値が返る", "3 軸の表を分解する"),
    ("設計上の外", "値が返る", "判断を属性で渡す"),
    ("設計上の外", "止まる", "主体ごとの値を渡す"),
)

KOWASHIKATA = ("出典を空にする", "同じ節 id を 2 行書く", "収録済に残る一手を書く",
               "収録済の出口を止まるにする", "レシピの節 id を空にする")

# テスト側の別実装(部品の verdict を呼ばない)。裁定の順は手前が勝つ
PRIORITY = ("宣言が無い", "止まる", "外から渡す前提", "返るが一手残る", "道具の中で済む")


def verdict_of(state: str, exit_kind: str) -> str:
    """節 1 つの判定の、テスト側の別実装。"""
    if exit_kind == "止まる":
        return "止まる"
    if state == "収録済":
        return "道具の中で済む"
    if state == "設計上の外":
        return "外から渡す前提"
    return "返るが一手残る"


def result_of(verdicts: list[str]) -> str:
    """問い 1 つの 5 値の、テスト側の別実装。"""
    found = set(verdicts)
    return next(r for r in PRIORITY if r in found or r == "道具の中で済む")


@st.composite
def 合成の3枚(draw: st.DrawFn) -> dict[str, object]:
    """守備範囲の宣言表 / 計算のレシピ表 / 問いの一覧(と崩し方)を作る。"""
    syuubi: list[list[str]] = []
    for i in range(draw(st.integers(1, 3))):
        state, exit_kind, step = draw(st.sampled_from(TRIPLES))
        syuubi.append([f"N{i + 1:02d}", f"合成の rule {i + 1}(架空)", state,
                       exit_kind, step, SOURCE])
    node_ids = [row[0] for row in syuubi] + ["N99"]   # N99 は宣言表に無い節

    recipe: list[list[str]] = []
    for i in range(draw(st.integers(1, 3))):
        ids = draw(st.lists(st.sampled_from(node_ids), min_size=1, max_size=3,
                            unique=True))
        recipe.append([f"V{i + 1:02d}", "|".join(ids), SOURCE])

    picked = draw(st.lists(st.sampled_from([r[0] for r in recipe]), min_size=1,
                           max_size=2, unique=True))
    toi = [[value_id, SOURCE, ""] for value_id in sorted(picked)]
    toi[0][2] = H.SWAPS[0]

    kowasu = draw(st.sampled_from([None] * 10 + list(KOWASHIKATA)))
    if kowasu == "出典を空にする":
        syuubi[0][5] = ""
    elif kowasu == "同じ節 id を 2 行書く":
        syuubi.append(list(syuubi[0]))
    elif kowasu == "収録済に残る一手を書く":
        syuubi[0][2], syuubi[0][3], syuubi[0][4] = "収録済", "値が返る", "上限を当てる"
    elif kowasu == "収録済の出口を止まるにする":
        syuubi[0][2], syuubi[0][3], syuubi[0][4] = "収録済", "止まる", ""
    elif kowasu == "レシピの節 id を空にする":
        recipe[0][1] = ""

    def csv(head: tuple[str, ...], body: list[list[str]]) -> str:
        return "\n".join([",".join(head)] + [",".join(r) for r in body])

    return {"syuubi": csv(H.SYUUBI_COLUMNS, syuubi),
            "recipe": csv(H.RECIPE_COLUMNS, recipe),
            "toi": csv(H.TOI_COLUMNS, toi),
            "syuubi_rows": syuubi, "recipe_rows": recipe, "toi_rows": toi,
            "kowasu": kowasu}


@settings(max_examples=200, derandomize=True, database=None, deadline=None)
@given(plan=合成の3枚())
def test_いつも成り立つこと_判定した問いか理由コードか(plan: dict[str, object]) -> None:
    boundary = H.Boundary.parse(plan["syuubi"])      # type: ignore[arg-type]
    recipes = H.Recipes.parse(plan["recipe"])        # type: ignore[arg-type]
    questions = H.Questions.parse(plan["toi"])       # type: ignore[arg-type]
    t = H.handoff_edge(boundary, recipes, questions)

    expect_stop = plan["kowasu"] is not None
    c = t.counts()
    five = c["5 値"]
    assert c["問いの数"] == len(plan["toi_rows"])              # type: ignore[arg-type]
    assert c["計算のレシピ表の行数(求める値の数)"] == len(plan["recipe_rows"])  # type: ignore[arg-type]
    assert c["分母(問いの数)"] == t.denominator
    assert sum(five.values()) == len(t.asked)                 # type: ignore[union-attr]
    # 宣言表が揃う前に止まったら 1 件も判定しない。判定したなら問いと 1 対 1 で付く
    assert len(t.asked) in (0, t.denominator)
    assert {a.result for a in t.asked} <= set(H.RESULTS)

    nodes = {row[0]: row for row in plan["syuubi_rows"]}       # type: ignore[union-attr]
    wants = {row[0]: [x for x in row[1].split("|") if x]
             for row in plan["recipe_rows"]}                   # type: ignore[union-attr]
    for a in t.asked:
        asked_ids = sorted(wants[a.value_id])
        missing = [n for n in asked_ids if n not in nodes]
        if missing:
            # 宣言が無い節が 1 つでもあれば別枠。残りの節に収録済を当てない
            assert a.result == H.ASIDE
            assert a.nodes == () and list(a.missing) == missing and a.steps == ()
            continue
        assert [n for n, _ in a.nodes] == asked_ids
        for node_id, v in a.nodes:
            assert v == verdict_of(nodes[node_id][2], nodes[node_id][3])
        assert a.result == result_of([v for _, v in a.nodes])
        # 残る一手は、道具の中で済む 以外の節の数だけ載り、名前は宣言のまま
        assert [n for n, _, _ in a.steps] == [n for n, v in a.nodes
                                              if v != H.RESULTS[0]]
        for node_id, state, step in a.steps:
            assert (state, step) == (nodes[node_id][2], nodes[node_id][4])

    if expect_stop:
        event("(b) 1 件も判定せずに止まった")
        assert t.report.ok is False and t.report.pending
        assert {p.reason for p in t.report.pending} <= set(H.TABLE_REASONS)
        for call in (lambda: t.verdict, t.judgement_bytes, t.sha256):
            with pytest.raises(RuntimeError):
                call()
    else:
        event("(a) 判定した")
        assert t.report.ok is True
        assert sum(five.values()) == t.denominator
        assert sum(t.by_node_verdict().values()) == t.counted_nodes()
        assert t.counted_nodes() <= t.node_denominator
        body = t.judgement_bytes().decode("utf-8")
        for word in ("読んだ条件", "絶対パス", str(ROOT)):
            assert word not in body
        how = questions.swap or H.SWAPS[0]
        again = H.handoff_edge(boundary.swapped(how), recipes.swapped(how),
                               questions.swapped(how))
        assert again.sha256() == t.sha256()
        assert again.judgement_bytes() == t.judgement_bytes()
        # 状態を 未実装 → 収録済 に替えると、動く辺は 1 本だけ
        want = f"{H.RESULTS[1]} → {H.RESULTS[0]}"
        for node in boundary.ordered:
            if node.state != H.STATES[1] or not node.returns:
                continue
            filled = H.handoff_edge(boundary.filled(node.node_id), recipes, questions)
            assert set(H.moves(t, filled)) <= {want}
        # 節を外すと、別枠へしか動かない
        for node in boundary.ordered:
            if len(boundary.items) <= 1:
                continue
            dropped = H.handoff_edge(boundary.without(node.node_id), recipes,
                                     questions)
            assert all(k.endswith(f"→ {H.ASIDE}") for k in H.moves(t, dropped))
            assert len(dropped.by_result(H.ASIDE)) >= len(t.by_result(H.ASIDE))

    # どちらの場合も入力は 1 文字も書き換わらない
    assert H.Boundary.parse(plan["syuubi"]).items == boundary.items    # type: ignore[arg-type]
    assert H.Recipes.parse(plan["recipe"]).items == recipes.items      # type: ignore[arg-type]
    assert H.Questions.parse(plan["toi"]).items == questions.items     # type: ignore[arg-type]


@settings(max_examples=300, derandomize=True, database=None)
@given(triple=st.sampled_from(TRIPLES), extra=st.sampled_from(TRIPLES),
       missing=st.booleans())
def test_宣言が無い節に収録済を当てない(triple: tuple[str, str, str],
                                        extra: tuple[str, str, str],
                                        missing: bool) -> None:
    """宣言表に無い節を参照している問いは別枠に出る。残りの節の判定も出さない。

    1 つでも宣言が無ければ、ほかの節が全部 収録済 でも「道具の中で済む」にはならない
    (既定を当てる経路が無い)。
    """
    rows = [["N01", "合成の rule 甲(架空)", *triple, SOURCE],
            ["N02", "合成の rule 乙(架空)", *extra, SOURCE]]
    syuubi = "\n".join([",".join(H.SYUUBI_COLUMNS)] + [",".join(r) for r in rows])
    asked = "N01|N02|N99" if missing else "N01|N02"
    recipe = "\n".join([",".join(H.RECIPE_COLUMNS), f"V01,{asked},{SOURCE}"])
    toi = "\n".join([",".join(H.TOI_COLUMNS), f"V01,{SOURCE},{H.SWAPS[0]}"])
    t = H.handoff_edge(H.Boundary.parse(syuubi), H.Recipes.parse(recipe),
                       H.Questions.parse(toi))
    assert t.report.ok
    a = t.asked[0]
    if missing:
        assert a.result == H.ASIDE and a.nodes == () and a.missing == ("N99",)
        assert t.counted_nodes() == 0 and t.node_denominator == 3
        assert t.by_node_verdict() == {v: 0 for v in H.NODE_VERDICTS}
    else:
        assert a.result == result_of([verdict_of(r[2], r[3]) for r in rows])
        assert a.result != H.ASIDE and len(a.nodes) == 2
        assert t.counted_nodes() == 2 == t.node_denominator
