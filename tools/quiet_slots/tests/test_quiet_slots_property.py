"""quiet_slots の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 読んだ範囲は 2 通りしかない。
  (a) 組を作った: 問い × 欄 の組 1 つごとに **4 値か別枠 3 か「手元に在ると宣言されている」の
      どれか 1 つ**が付き、**その合計 = 問いの件数 × 欄の件数**、**問いごとの内訳の合計も
      欄の種別ごとの内訳の合計も同じ数**になる。印が付くのは `空でよいと宣言されている` 組
      だけで(**印の合計 = その件数**)、**`宣言なし` と宣言された欄が `空でよい` 側へ移る
      経路は無く**、**`人かLLM` と宣言された欄は必ず (C)**、**問いが手元に在ると宣言した欄は
      空にする欄に数えず**、**出典が空の問いの組は 4 値に 1 つも入らない**。判定部分に
      絶対パスが入らず、4 枚の行順を 3 通りに入れ替えても同じバイト列になる
  (b) 1 組も数えずに理由コードが返る(作った組や sha256 を取りに行くと例外)
どちらの場合も、この部品は 4 枚の表を 1 文字も書き換えない。

問いを 1〜4 件、欄の登録を 5 欄(種別 / 空にできるか / 誰が埋めてよいか をそれぞれ引く。
`できない` の欄は止まる出口を引く)、同じ欄の 2 本目の宣言を 0〜1 本、行の在り方を 0〜3 行、
出口の登録を 4 行から引く。4 回に 1 回くらいどこか 1 か所を崩す(7 通りを平らに引き、
1 組も数えずに止まる理由コード 7 個すべてに道が付く)。derandomize=True で毎回同じ 250 通りを
使い、database=None で例を保存しない。

**4 値の分け方はテストの側で別に実装している**(部品の judge / four を呼ばない)。
2 本目は「空にできるか・誰が埋めてよいか・行数の宣言の 3 つだけが判定と印を決める」ことを
総当たりで見る。
"""
from __future__ import annotations

import csv as _csv
import io
import sys
from pathlib import Path

import pytest
from hypothesis import event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import quiet_slots as H  # noqa: E402

ASK = "合成の呼び出しのメモ(架空)L1"
WORD = "合成の宣言のメモ(架空)L1"
SHAPE = "合成の行数のメモ(架空)L1"

SLOT_NAMES = ("K1", "K2", "K3", "K4", "K5")
UNREGISTERED = "K6"
TARGETS = (H.NO_MARK, "R1", "R2")
DANGLING = "R9"
COMMANDS = ("status", "resolve", "compute")

EXIT_ROWS = [[H.EXITS[0], H.STOPS[0], WORD],
             [H.EXITS[1], H.STOPS[0], WORD],
             [H.EXITS[2], H.STOPS[0], WORD],
             [H.EXITS[3], H.STOPS[1], WORD]]

KOWASHIKATA = ("宣言の出典を空にする", "問い id を重複させる",
               "同じ問いに同じ欄名を 2 回書く", "空にできない欄の出口を外す",
               "空にできない欄の出口を通るにする",
               "同じ rule と次元の組を 2 行にする",
               "同じ出口記号で止まるかを食い違わせる")


def classify(asks: list[list[str]], slots: list[list[str]],
             shapes: list[list[str]]) -> dict[str, tuple[str, str]]:
    """組ごとの (判定, 印) をテストの側で別に出す(部品を呼ばない)。"""
    decls: dict[str, list[list[str]]] = {}
    for row in slots:
        decls.setdefault(row[0], []).append(row)
    rows = {(r[0], r[1]): int(r[2]) for r in shapes}
    names = sorted({r[0] for r in slots}
                   | {n for r in asks for n in r[3].split("|") if n}
                   | {r[1] for r in shapes})
    out: dict[str, tuple[str, str]] = {}
    for ask in sorted(asks, key=lambda r: r[0]):
        held = [n for n in ask[3].split("|") if n]
        for name in names:
            key = f"{ask[0]}>{name}"
            here = decls.get(name, [])
            if not ask[4]:
                out[key] = (H.BETSUWAKU[2], "")
            elif not here:
                out[key] = (H.BETSUWAKU[1], "")
            elif len({(r[2], r[3]) for r in here}) > 1:
                out[key] = (H.BETSUWAKU[0], "")
            elif name in held:
                out[key] = (H.AT_HAND, "")
            elif here[0][3] == H.FILLERS[2]:
                out[key] = (H.YOTSU[2], "")
            elif here[0][2] == H.EMPTIABLE[0]:
                out[key] = (H.YOTSU[0], "")
            elif here[0][2] == H.EMPTIABLE[2]:
                out[key] = (H.YOTSU[3], "")
            else:
                n = rows.get((ask[2], name))
                out[key] = (H.YOTSU[1],
                            H.MARKS[2] if n is None
                            else (H.MARKS[0] if n == 1 else H.MARKS[1]))
    return out


@st.composite
def 合成の4枚(draw: st.DrawFn) -> dict[str, object]:
    """問いの宣言表 / 欄の登録表 / 行の在り方の表 / 出口の登録表(と崩し方)を作る。"""
    slots: list[list[str]] = []
    for i, name in enumerate(SLOT_NAMES):
        kind = draw(st.sampled_from(H.KINDS))
        emptiable = (H.EMPTIABLE[0] if i == 0
                     else draw(st.sampled_from(H.EMPTIABLE)))
        filler = draw(st.sampled_from(H.FILLERS))
        exit_sym = (draw(st.sampled_from(H.EXITS[:3]))
                    if emptiable == H.EMPTIABLE[0] else H.NO_MARK)
        slots.append([name, kind, emptiable, filler, exit_sym, WORD])
    if draw(st.booleans()):     # 同じ欄の 2 本目(食い違う宣言)
        base = slots[-1]
        other = next(e for e in H.EMPTIABLE if e != base[2])
        slots.append([base[0], base[1], other,
                      draw(st.sampled_from(H.FILLERS)),
                      draw(st.sampled_from(H.EXITS[:3]))
                      if other == H.EMPTIABLE[0] else H.NO_MARK, WORD])

    asks: list[list[str]] = []
    for k in range(1, draw(st.integers(1, 4)) + 1):
        held = draw(st.lists(st.sampled_from(SLOT_NAMES + (UNREGISTERED,)),
                             max_size=3, unique=True))
        asks.append([f"Q{k}", draw(st.sampled_from(COMMANDS)),
                     draw(st.sampled_from(TARGETS)), "|".join(held),
                     draw(st.sampled_from((ASK, ASK, ASK, ASK, "")))])

    shapes: list[list[str]] = []
    for pair in draw(st.lists(st.tuples(st.sampled_from(TARGETS[1:] + (DANGLING,)),
                                        st.sampled_from(SLOT_NAMES[1:])),
                              max_size=3, unique=True)):
        shapes.append([pair[0], pair[1], str(draw(st.integers(1, 3))), SHAPE])

    exits = [list(r) for r in EXIT_ROWS]

    # 4 回に 1 回くらい崩す。崩す側は 7 通りを平らに引く
    kowasu = (draw(st.sampled_from(KOWASHIKATA))
              if draw(st.integers(0, 3)) == 0 else None)
    if kowasu == KOWASHIKATA[0]:
        slots[0][5] = ""
    elif kowasu == KOWASHIKATA[1]:
        asks.append([asks[0][0], COMMANDS[0], H.NO_MARK, "", ASK])
    elif kowasu == KOWASHIKATA[2]:
        asks[0][3] = f"{SLOT_NAMES[0]}|{SLOT_NAMES[0]}"
    elif kowasu == KOWASHIKATA[3]:
        slots[0][4] = H.NO_MARK
    elif kowasu == KOWASHIKATA[4]:
        slots[0][4] = H.EXITS[3]
    elif kowasu == KOWASHIKATA[5]:
        shapes = shapes + [[TARGETS[1], SLOT_NAMES[1], "1", SHAPE]] * 2
    elif kowasu == KOWASHIKATA[6]:
        exits.append([H.EXITS[0], H.STOPS[1], WORD])

    def csv(head: tuple[str, ...], body: list[list[str]]) -> str:
        buf = io.StringIO()
        _csv.writer(buf, lineterminator="\n").writerows([list(head)] + body)
        return buf.getvalue()

    return {"asks": csv(H.ASK_COLUMNS, asks),
            "slots": csv(H.SLOT_COLUMNS, slots),
            "shapes": csv(H.SHAPE_COLUMNS, shapes),
            "exits": csv(H.EXIT_COLUMNS, exits),
            "asks_rows": asks, "slots_rows": slots, "shapes_rows": shapes,
            "kowasu": kowasu}


@settings(max_examples=250, derandomize=True, database=None, deadline=None)
@given(plan=合成の4枚())
def test_いつも成り立つこと_作った組か理由コードか(plan: dict[str, object]) -> None:
    asks = H.Asks.parse(plan["asks"])        # type: ignore[arg-type]
    slots = H.Slots.parse(plan["slots"])     # type: ignore[arg-type]
    shapes = H.Shapes.parse(plan["shapes"])  # type: ignore[arg-type]
    exits = H.Exits.parse(plan["exits"])     # type: ignore[arg-type]
    t = H.quiet_slots(asks, slots, shapes, exits)

    expect_stop = plan["kowasu"] is not None
    c = t.counts()
    four, extras = c["4 値"], c["別枠"]
    assert c["問いの宣言表の行数"] == len(plan["asks_rows"])     # type: ignore[arg-type]
    assert c["欄の登録表の行数"] == len(plan["slots_rows"])      # type: ignore[arg-type]
    assert c["行の在り方の表の行数"] == len(plan["shapes_rows"])  # type: ignore[arg-type]
    assert {x.value for x in t.cells} <= set(H.YOTSU + H.BETSUWAKU + (H.AT_HAND,))
    assert all(isinstance(v, int) for v in four.values())   # type: ignore[union-attr]
    # **出力に「正しい埋め方」「推奨」の欄が無い**
    for key in c:
        for word in ("正しい埋め方", "推奨", "既定値", "割合", "一致率"):
            assert word not in key

    if expect_stop:
        event("(b) 1 組も数えずに止まった")
        assert t.report.ok is False and t.report.pending
        assert {x.reason for x in t.report.pending} <= set(H.TABLE_REASONS)
        assert t.cells == ()
        assert four == {k: 0 for k in H.YOTSU}
        assert extras == {k: 0 for k in H.BETSUWAKU}
        assert t.at_hand() == 0 and t.pair_denominator() == 0
        assert t.quiet_cells() == () and t.wide_cells() == ()
        assert t.marks() == {k: 0 for k in H.MARKS}
        for call in (t.judgement_bytes, t.sha256):
            with pytest.raises(RuntimeError):
                call()
    else:
        event("(a) 組を作った")
        assert t.report.ok is True
        # 組ごとに 1 つの値。テスト側の別実装と一致する
        mine = {x.name: (x.value, x.mark) for x in t.cells}
        assert mine == classify(plan["asks_rows"], plan["slots_rows"],  # type: ignore[arg-type]
                                plan["shapes_rows"])                   # type: ignore[arg-type]
        # 3 通りの数え方が合う
        total = sum(four.values()) + sum(extras.values()) + t.at_hand()
        assert total == t.pair_denominator()
        assert t.pair_denominator() == t.ask_denominator() * t.slot_denominator()
        assert sum(int(r["組の件数"]) for r in t.by_ask()) == total
        assert sum(int(r["組の件数"]) for r in t.by_kind()) == total
        assert sum(int(r["組の件数"]) for r in t.by_slot()) == total
        # 印が付くのは (B) の組だけで、合計はその件数
        assert sum(t.marks().values()) == four[H.YOTSU[1]]
        assert all(bool(x.mark) == (x.value == H.YOTSU[1]) for x in t.cells)
        assert all(x.rows == 0 for x in t.cells
                   if x.mark not in (H.MARKS[0], H.MARKS[1]))
        for x in t.cells:
            decls = slots.decls(x.slot)
            if not x.ask.source:
                assert x.value == H.BETSUWAKU[2]
                continue
            if not decls:
                assert x.value == H.BETSUWAKU[1] and x.kind == H.NOT_REGISTERED
                continue
            if len({(d.emptiable, d.filler) for d in decls}) > 1:
                assert x.value == H.BETSUWAKU[0] and len(x.sources) == len(decls)
                continue
            d = decls[0]
            if x.slot in x.ask.slots:
                assert x.value == H.AT_HAND and not x.mark
                continue
            # **`宣言なし` が `空でよい` 側へ移る経路が無い**
            if d.emptiable == H.EMPTIABLE[2]:
                assert x.value != H.YOTSU[1]
                assert x.value == (H.YOTSU[2] if d.filler == H.FILLERS[2]
                                   else H.YOTSU[3])
            # **`人かLLM` と宣言された欄は必ず (C)**
            if d.filler == H.FILLERS[2]:
                assert x.value == H.YOTSU[2] and x.quiet
            if x.value == H.YOTSU[0]:
                assert d.emptiable == H.EMPTIABLE[0] and not x.quiet
                assert exits.of(d.exit) is not None
                assert exits.of(d.exit).stops == H.STOPS[0]
            if x.value == H.YOTSU[1]:
                assert d.emptiable == H.EMPTIABLE[1] and x.quiet
                shape = shapes.of(x.ask.target, x.slot)
                if shape is None:
                    assert x.mark == H.MARKS[2] and x.rows == 0
                elif shape.rows == 1:
                    assert x.mark == H.MARKS[0]
                else:
                    assert x.mark == H.MARKS[1] and x.rows == shape.rows >= 2
        # 空でも止まらない欄 = (B) + (C)
        assert len(t.quiet_cells()) == four[H.YOTSU[1]] + four[H.YOTSU[2]]
        assert all(x.mark == H.MARKS[1] for x in t.wide_cells())
        body = t.judgement_bytes().decode("utf-8")
        for word in ("読んだ条件", "絶対パス", str(ROOT)):
            assert word not in body
        # 4 枚の行順を 3 通りに入れ替えても同じバイト列
        for how in H.SWAPS:
            again = H.quiet_slots(asks.swapped(how), slots.swapped(how),
                                  shapes.swapped(how), exits.swapped(how))
            assert again.judgement_bytes() == t.judgement_bytes()
            assert again.sha256() == t.sha256()

    # どちらの場合も入力は 1 文字も書き換わらない
    assert H.Asks.parse(plan["asks"]).items == asks.items        # type: ignore[arg-type]
    assert H.Slots.parse(plan["slots"]).items == slots.items     # type: ignore[arg-type]
    assert H.Shapes.parse(plan["shapes"]).items == shapes.items  # type: ignore[arg-type]
    assert H.Exits.parse(plan["exits"]).items == exits.items     # type: ignore[arg-type]


@settings(max_examples=300, derandomize=True, database=None)
@given(emptiable=st.sampled_from(H.EMPTIABLE),
       filler=st.sampled_from(H.FILLERS),
       rows=st.sampled_from((None, 1, 2, 47)))
def test_宣言の3つだけが判定と印を決める(emptiable: str, filler: str,
                                        rows: int | None) -> None:
    """空にできるか・誰が埋めてよいか・行数の宣言の 3 つだけが、判定と印を決める。

    **`宣言なし` は `空でよい` 側へ移らず**、**`人かLLM` は空にできるかに関わらず (C)**、
    **行数の宣言が無い (B) の組には `行数の宣言が無い` の印が付く**(0 とも 1 とも読まない)。
    """
    exit_sym = H.EXITS[0] if emptiable == H.EMPTIABLE[0] else H.NO_MARK
    asks = H.Asks.parse("\n".join([",".join(H.ASK_COLUMNS),
                                   f"Q1,resolve,R1,,{ASK}"]))
    slots = H.Slots.parse("\n".join(
        [",".join(H.SLOT_COLUMNS),
         f"K1,{H.KINDS[1]},{emptiable},{filler},{exit_sym},{WORD}"]))
    shape_rows = [",".join(H.SHAPE_COLUMNS)]
    if rows is not None:
        shape_rows.append(f"R1,K1,{rows},{SHAPE}")
    shapes = H.Shapes.parse("\n".join(shape_rows))
    exits = H.Exits.parse("\n".join([",".join(H.EXIT_COLUMNS)]
                                    + [",".join(r) for r in EXIT_ROWS]))
    t = H.quiet_slots(asks, slots, shapes, exits)
    assert t.report.ok, [p.as_dict() for p in t.report.pending]
    assert t.pair_denominator() == 1
    cell = t.cells[0]

    if filler == H.FILLERS[2]:
        want, mark = H.YOTSU[2], ""
    elif emptiable == H.EMPTIABLE[0]:
        want, mark = H.YOTSU[0], ""
    elif emptiable == H.EMPTIABLE[2]:
        want, mark = H.YOTSU[3], ""
    else:
        want = H.YOTSU[1]
        mark = (H.MARKS[2] if rows is None
                else (H.MARKS[0] if rows == 1 else H.MARKS[1]))
    assert (cell.value, cell.mark) == (want, mark)
    assert cell.quiet is (want in (H.YOTSU[1], H.YOTSU[2]))
    assert cell.rows == (rows if mark in (H.MARKS[0], H.MARKS[1]) else 0)
    assert sum(t.four().values()) == 1
    assert sum(t.marks().values()) == t.four()[H.YOTSU[1]]
