"""input_chain の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 読んだ範囲は 2 通りしかない。
  (a) 問い 1 つごとに葉が 0 枚以上付き、**5 値の合計が葉の数**に等しく、**問いごとの内訳の合計が
      全体**に等しく、**宣言に無い参照は 宣言が無い に出て**(case の欄 を既定として当てない)、
      **導出すると宣言 の葉は 人が用意する に混ざらず**、**経路に同じ式が 2 回出る枝と段数の
      上限に当たった枝は 辿れない に出て**段数が 上限 + 2 を超えず、判定部分に絶対パスが入らず、
      3 枚の行順を入れ替えても同じバイト列になる
  (b) 1 枚も辿らずに理由コードが返る(辿った葉や指紋を取りに行くと例外)
どちらの場合も、この部品は式の宣言表も行の宣言表も問いの一覧も 1 文字も書き換えない。

式を 1〜3 つ作って(入力は 1〜3 つ、種別は登録の 4 種から引く)、rule を 1〜2 本、問いを 1〜2 件
引く。入力 id は 式 id・rule id・case の欄・宣言表に無い id から引くので、輪も宣言の穴も混ざる。
3 割くらいの確率で 1 か所だけ崩す(出典を空にする / 種別を空にする / 登録外の種別を書く /
同じ式に同じ入力 id を 2 行書く / 基準日の欄を空にする / 手元に在る欄に同じ名前を 2 つ書く)。
derandomize=True で毎回同じ入力列を使い、database=None で見つけた例を保存しない。

**葉の辿り方と 5 値はテストの側で別に実装している**(部品の walk / counts を呼ばない)。
2 本目は「宣言に無い参照に case の欄 を当てない」ことを見ている(既定を当てる経路が無い、の物理形)。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from hypothesis import event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import input_chain as H  # noqa: E402

SOURCE = "合成の出典メモ(架空)L1"
FORMULAS = ("F1", "F2", "F3")
RULES = ("R1", "R2")
CASES = ("C1", "C2", "C3")
UNKNOWN = ("X9", "Y9")            # どの宣言表にも無い id
POOL = FORMULAS + RULES + CASES + UNKNOWN

KOWASHIKATA = ("出典を空にする", "種別を空にする", "登録外の種別を書く",
               "同じ式に同じ入力 id を 2 行書く", "基準日の欄を空にする",
               "手元に在る欄に同じ名前を 2 つ書く")


def expect(shiki: list[list[str]], gyou: list[list[str]],
           value_id: str, hand: list[str]) -> list[tuple[str, str, int]]:
    """問い 1 つの葉を、テストの側で別に辿る(部品の walk を呼ばない)。"""
    inputs: dict[str, list[list[str]]] = {}
    for row in shiki:
        inputs.setdefault(row[0], []).append(row)
    rules = {row[0]: row for row in gyou}
    out: list[tuple[str, str, int]] = []

    def case_leaf(name: str, depth: int) -> None:
        out.append((name, "手元に在る" if name in hand else "人が用意する", depth))

    def go(fid: str, depth: int, path: list[str]) -> None:
        for row in sorted(inputs.get(fid, []), key=lambda r: r[1]):
            name, kind, d = row[1], row[2], depth + 1
            if kind == "case の欄":
                case_leaf(name, d)
            elif kind == "導出すると宣言":
                out.append((name, "導出すると宣言", d))
            elif kind == "表の行":
                if name not in rules:
                    out.append((name, "宣言が無い", d))
                else:
                    rule = rules[name]
                    for one in ([x for x in rule[1].split("|") if x]
                                + sorted(x for x in rule[2].split("|") if x)):
                        case_leaf(one, d + 1)
            elif name not in inputs:
                out.append((name, "宣言が無い", d))
            elif name in path or d > H.MAX_DEPTH:
                out.append((name, "辿れない", d))
            else:
                go(name, d, path + [name])

    if value_id not in inputs:
        return [(value_id, "宣言が無い", 0)]
    go(value_id, 0, [value_id])
    return out


@st.composite
def 合成の3枚(draw: st.DrawFn) -> dict[str, object]:
    """式の宣言表 / 行の宣言表 / 問いの一覧(と崩し方)を作る。"""
    shiki: list[list[str]] = []
    for fid in FORMULAS[:draw(st.integers(1, 3))]:
        ids = draw(st.lists(st.sampled_from(POOL), min_size=1, max_size=3, unique=True))
        for one in ids:
            shiki.append([fid, one, draw(st.sampled_from(H.KINDS)), SOURCE])

    gyou: list[list[str]] = []
    for rid in RULES[:draw(st.integers(1, 2))]:
        dims = draw(st.lists(st.sampled_from(CASES), min_size=0, max_size=2, unique=True))
        gyou.append([rid, draw(st.sampled_from(CASES)), "|".join(dims), SOURCE])

    asked = draw(st.lists(st.sampled_from(FORMULAS + UNKNOWN[:1]), min_size=1,
                          max_size=2, unique=True))
    toi = [[value_id, "|".join(draw(st.lists(st.sampled_from(CASES), min_size=0,
                                             max_size=2, unique=True))), SOURCE, ""]
           for value_id in sorted(asked)]
    toi[0][3] = H.SWAPS[0]

    kowasu = draw(st.sampled_from([None] * 14 + list(KOWASHIKATA)))
    if kowasu == "出典を空にする":
        shiki[0][3] = ""
    elif kowasu == "種別を空にする":
        shiki[0][2] = ""
    elif kowasu == "登録外の種別を書く":
        shiki[0][2] = "たぶん case の欄"
    elif kowasu == "同じ式に同じ入力 id を 2 行書く":
        shiki.append(list(shiki[0]))
    elif kowasu == "基準日の欄を空にする":
        gyou[0][1] = ""
    elif kowasu == "手元に在る欄に同じ名前を 2 つ書く":
        toi[0][1] = f"{CASES[0]}|{CASES[0]}"

    def csv(head: tuple[str, ...], body: list[list[str]]) -> str:
        return "\n".join([",".join(head)] + [",".join(r) for r in body])

    return {"shiki": csv(H.SHIKI_COLUMNS, shiki), "gyou": csv(H.GYOU_COLUMNS, gyou),
            "toi": csv(H.TOI_COLUMNS, toi), "shiki_rows": shiki, "gyou_rows": gyou,
            "toi_rows": toi, "kowasu": kowasu}


@settings(max_examples=200, derandomize=True, database=None, deadline=None)
@given(plan=合成の3枚())
def test_いつも成り立つこと_辿った葉か理由コードか(plan: dict[str, object]) -> None:
    formulas = H.Formulas.parse(plan["shiki"])       # type: ignore[arg-type]
    rows = H.Rows.parse(plan["gyou"])                # type: ignore[arg-type]
    questions = H.Questions.parse(plan["toi"])       # type: ignore[arg-type]
    t = H.input_chain(formulas, rows, questions)

    expect_stop = plan["kowasu"] is not None
    c = t.counts()
    five = c["5 値"]
    assert c["問いの数"] == len(plan["toi_rows"])                # type: ignore[arg-type]
    assert c["式の宣言表の行数(入力の数)"] == len(plan["shiki_rows"])  # type: ignore[arg-type]
    assert c["分母(問いの数)"] == t.denominator
    assert sum(five.values()) == t.leaf_denominator()            # type: ignore[union-attr]
    assert len(t.asked) in (0, t.denominator)
    assert {f.result for f in t.leaves()} <= set(H.RESULTS)

    for a in t.asked:
        hand = [x for x in dict((q[0], q[1]) for q in
                                plan["toi_rows"])[a.value_id].split("|") if x]  # type: ignore[union-attr]
        want = expect(plan["shiki_rows"], plan["gyou_rows"], a.value_id, hand)  # type: ignore[arg-type]
        assert [(f.name, f.result, f.depth) for f in a.leaves] == want
        # 導出すると宣言 の葉は、その名前が手元に在っても 手元に在る / 人が用意する に
        # 混ざらない(5 値の別の列に残る)
        derived = {row[1] for row in plan["shiki_rows"]                 # type: ignore[union-attr]
                   if row[2] == H.RESULTS[2]}
        for f in a.leaves:
            if f.name in derived and f.result == H.RESULTS[2]:
                assert f.result not in H.RESULTS[:2]
            if f.result == H.RESULTS[3]:
                assert f.why in (H.WHY[2], H.WHY[3], H.WHY[4])
            if f.result == H.RESULTS[4]:
                assert f.why in (H.WHY[0], H.WHY[1])
        assert a.depth <= H.MAX_DEPTH + 2

    if expect_stop:
        event("(b) 1 枚も辿らずに止まった")
        assert t.report.ok is False and t.report.pending
        assert {p.reason for p in t.report.pending} <= set(H.TABLE_REASONS)
        assert t.asked == () and t.leaf_denominator() == 0
        for call in (t.judgement_bytes, t.sha256):
            with pytest.raises(RuntimeError):
                call()
    else:
        event("(a) 辿った")
        assert t.report.ok is True
        assert sum(sum(a.five().values()) for a in t.asked) == t.leaf_denominator()
        body = t.judgement_bytes().decode("utf-8")
        for word in ("読んだ条件", "絶対パス", str(ROOT)):
            assert word not in body
        how = questions.swap or H.SWAPS[0]
        again = H.input_chain(formulas.swapped(how), rows.swapped(how),
                              questions.swapped(how))
        assert again.sha256() == t.sha256()
        assert again.judgement_bytes() == t.judgement_bytes()

    # どちらの場合も入力は 1 文字も書き換わらない
    assert H.Formulas.parse(plan["shiki"]).items == formulas.items   # type: ignore[arg-type]
    assert H.Rows.parse(plan["gyou"]).items == rows.items            # type: ignore[arg-type]
    assert H.Questions.parse(plan["toi"]).items == questions.items   # type: ignore[arg-type]


@settings(max_examples=300, derandomize=True, database=None)
@given(kind=st.sampled_from(H.KINDS), name=st.sampled_from(("X9", "C1")),
       in_hand=st.booleans())
def test_宣言に無い参照に既定の種別を当てない(kind: str, name: str,
                                              in_hand: bool) -> None:
    """宣言表に無い id を指している入力は、手元に在る名前と同じでも 宣言が無い に出る。

    `case の欄` と `導出すると宣言` は宣言そのものなので辿らない(= 名前が宣言表に無いことは
    理由にならない)。`別の式` と `表の行` だけが参照で、参照先が無ければ別枠に出す。
    """
    shiki = "\n".join([",".join(H.SHIKI_COLUMNS), f"F1,{name},{kind},{SOURCE}"])
    gyou = "\n".join([",".join(H.GYOU_COLUMNS), f"R1,C1,,{SOURCE}"])
    toi = "\n".join([",".join(H.TOI_COLUMNS),
                     f"F1,{'C1' if in_hand else ''},{SOURCE},{H.SWAPS[0]}"])
    t = H.input_chain(H.Formulas.parse(shiki), H.Rows.parse(gyou), H.Questions.parse(toi))
    assert t.report.ok
    leaf = t.asked[0].leaves[0]
    assert leaf.name == name and leaf.depth == 1
    if kind == "case の欄":
        assert leaf.result == ("手元に在る" if in_hand and name == "C1"
                               else "人が用意する")
    elif kind == "導出すると宣言":
        assert leaf.result == "導出すると宣言"
    else:
        assert leaf.result == "宣言が無い"
        assert leaf.why == (H.WHY[3] if kind == "別の式" else H.WHY[4])
    assert t.leaf_denominator() == 1
