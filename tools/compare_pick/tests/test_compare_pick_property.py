"""compare_pick の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 読んだ範囲は 2 通りしかない。
  (a) (組 × 基準日)ごとに 4 値が 1 つだけ付き、4 値の合計が 組数 × 基準日の数 に等しく、
      止まった理由別の合計が止まったの件数に、決まらない理由別の合計が比較では決まらないの
      件数に等しく、決まった組の勝った行 id は候補の表にそのまま在る id で、勝った値は
      **同じ組の値のどれかを宣言された丸めに通したもの**(道具が別の値を作らない)、判定部分に
      時刻・ホスト名・絶対パスが入らず、3 枚の行順を入れ替えても同じバイト列になる
  (b) 1 組も読まずに理由コードが返る(読んだ組や指紋を取りに行くと例外)
どちらの場合も、この部品は宣言表も候補の表も基準日の表も 1 文字も書き換えない。

rule を 1〜3 本作って裁定の種類を振り、比較の宣言(比べる欄 / 向き / 単位 / 丸めの前後 /
丸めの名前 / 同値の扱い)を引く。組を 1〜3 組、各組の候補を 1〜3 本作り、値を合成の値と
読めない形から引き、単位を 2 種から、順位を 0 / 10 / 20 / 空欄から、有効期間を 2 種から引く。
基準日は 1〜2 件。さらに 3 割くらいの確率で 1 か所だけ崩す(出典を空にする / 同じ組に同じ行 id
を 2 行書く / 宣言に無い裁定の種類を書く / 同じ rule の宣言を 2 行書く)。
derandomize=True で毎回同じ入力列を使い、database=None で見つけた例を保存しない。

**丸めはテストの側で別に実装している**(部品の round_value を呼ばない)。2 本目は「値の比較で
決まる組は、順位の欄を入れ替えても勝者が変わらない」ことを見ている(比較の代わりに順位を読む
経路が無い、の物理形)。
"""
from __future__ import annotations

import sys
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from pathlib import Path

import pytest
from hypothesis import event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import compare_pick as C  # noqa: E402

SOURCE = "合成の出典メモ(架空)L1"
RAN_A, RAN_B = "欄A", "欄B"
TANNI_KOU, TANNI_OTSU = "単位甲", "単位乙"
VALUES = ("1026", "1049", "1211", "1224", "998.75", "1002.4", "未取得", "1.05e3")
JUNI = ("0", "10", "20", "")               # 空欄は「順位の欄が空」になる
KIKAN = (("2026-01-01", "2027-01-01"), ("2026-01-01", "2026-07-01"))
KIJUNBI = ("2026-04-01", "2026-10-01")

KOWASHIKATA = ("出典を空にする", "同じ組に同じ行 id を 2 行書く",
               "宣言に無い裁定の種類を書く", "同じ rule の宣言を 2 行書く")


def marume(value: Decimal, name: str) -> Decimal:
    """丸めの、テスト側の別実装(部品の round_value は呼ばない)。"""
    if name == C.ROUNDINGS[0]:
        return value
    if name == C.ROUNDINGS[1]:
        return (value / Decimal(50)).to_integral_value(rounding=ROUND_HALF_UP) \
            * Decimal(50)
    return value.to_integral_value(rounding=ROUND_FLOOR)


def readable(text: str) -> Decimal | None:
    try:
        return Decimal(text) if C.NUMBER.match(text) else None
    except Exception:       # pragma: no cover - NUMBER を通れば Decimal は読める
        return None


@st.composite
def 合成の3枚(draw: st.DrawFn) -> dict[str, object]:
    """裁定の宣言表 / 候補の表 / 基準日の表(と崩し方)を作る。"""
    rule_ids = [f"R{i + 1:02d}" for i in range(draw(st.integers(1, 3)))]
    sengen: list[list[str]] = []
    for rid in rule_ids:
        kind = draw(st.sampled_from(C.KINDS))
        if kind == C.KINDS[1]:
            sengen.append([rid, kind, RAN_A, draw(st.sampled_from(C.DIRECTIONS)),
                           TANNI_KOU, draw(st.sampled_from(C.ROUND_WHENS)),
                           draw(st.sampled_from(C.ROUNDINGS)),
                           draw(st.sampled_from(C.TIES)), SOURCE])
        else:
            sengen.append([rid, kind, "", "", "", "", "", "", SOURCE])

    kouho: list[list[str]] = []
    for g in range(draw(st.integers(1, 3))):
        group_id = f"P{g + 1:02d}"
        rule_id = draw(st.sampled_from(rule_ids))
        for _ in range(draw(st.integers(1, 3))):
            start, end = draw(st.sampled_from(KIKAN))
            kouho.append([group_id, rule_id, f"G{len(kouho) + 1:02d}",
                          draw(st.sampled_from(JUNI)),
                          draw(st.sampled_from((RAN_A, RAN_A, RAN_B))),
                          draw(st.sampled_from(VALUES)),
                          draw(st.sampled_from((TANNI_KOU, TANNI_KOU, TANNI_OTSU))),
                          start, end, SOURCE])

    days = draw(st.lists(st.sampled_from(KIJUNBI), min_size=1, max_size=2,
                         unique=True))
    kijunbi = [[f"K{i + 1:02d}", day, SOURCE, ""]
               for i, day in enumerate(sorted(days))]
    kijunbi[0][3] = C.SWAPS[0]

    kowasu = draw(st.sampled_from([None] * 7 + list(KOWASHIKATA)))
    if kowasu == "出典を空にする":
        kouho[0][9] = ""
    elif kowasu == "同じ組に同じ行 id を 2 行書く":
        kouho.append(list(kouho[0]))
    elif kowasu == "宣言に無い裁定の種類を書く":
        sengen[0][1] = "高い方が適用"
    elif kowasu == "同じ rule の宣言を 2 行書く":
        sengen.append(list(sengen[0]))

    def csv(head: tuple[str, ...], body: list[list[str]]) -> str:
        return "\n".join([",".join(head)] + [",".join(r) for r in body])

    return {"sengen": csv(C.SENGEN_COLUMNS, sengen),
            "kouho": csv(C.KOUHO_COLUMNS, kouho),
            "kijunbi": csv(C.KIJUNBI_COLUMNS, kijunbi),
            "sengen_rows": sengen, "kouho_rows": kouho, "kijunbi_rows": kijunbi,
            "kowasu": kowasu}


@settings(max_examples=200, derandomize=True, database=None, deadline=None)
@given(plan=合成の3枚())
def test_いつも成り立つこと_読んだ組か理由コードか(plan: dict[str, object]) -> None:
    declared = C.Declared.parse(plan["sengen"])            # type: ignore[arg-type]
    candidates = C.Candidates.parse(plan["kouho"])         # type: ignore[arg-type]
    asofs = C.Asofs.parse(plan["kijunbi"])                 # type: ignore[arg-type]
    t = C.compare_pick(declared, candidates, asofs)

    expect_stop = plan["kowasu"] is not None
    c = t.counts()
    four = c["4 値"]
    assert c["組数"] == len(candidates.group_ids)
    assert c["基準日の数"] == len(plan["kijunbi_rows"])     # type: ignore[arg-type]
    assert c["分母(組数 × 基準日の数)"] == t.denominator
    assert sum(four.values()) == len(t.pairs)              # type: ignore[union-attr]
    # 表が揃う前に止まったら 1 組も読まない。読んだなら組と 1 対 1 で付く
    assert len(t.pairs) in (0, t.denominator)
    assert {p.result for p in t.pairs} <= set(C.RESULTS)

    for p in t.pairs:
        rows = candidates.of(p.group_id)
        rule = declared.of(p.rule_id)
        if p.result in (C.RESULTS[0], C.RESULTS[1]):
            assert p.row_id in {r.row_id for r in rows}
            assert p.why == "" and p.reason == ""
            if p.value:
                # 勝った値は、同じ組の値のどれかを宣言された丸めに通したもの
                made = {str(marume(v, rule.rounding)) for v in
                        (readable(r.value) for r in rows) if v is not None}
                assert p.value in made
        else:
            assert p.row_id == "" and p.value == ""
            assert (p.why in C.UNDECIDED) == (p.result == C.RESULTS[2])
            assert (p.reason in C.PAIR_REASONS) == (p.result == C.RESULTS[3])
        assert p.hits == len(rows)

    if expect_stop:
        event("(b) 止まった")
        assert t.report.ok is False
        assert t.report.pending
        assert {p.reason for p in t.report.pending} <= set(C.TABLE_REASONS)
        for call in (lambda: t.verdict, t.judgement_bytes, t.sha256):
            with pytest.raises(RuntimeError):
                call()
    else:
        event("(a) 読んだ")
        assert t.report.ok is True
        assert sum(four.values()) == t.denominator
        assert sum(t.by_reason().values()) == four[C.RESULTS[3]]
        assert sum(t.by_why().values()) == four[C.RESULTS[2]]
        body = t.judgement_bytes().decode("utf-8")
        for word in (t.read_at, t.host, "読んだ時刻", "ホスト名"):
            assert word not in body
        # 3 枚の行順を入れ替えても同じバイト列
        how = asofs.swap or C.SWAPS[0]
        again = C.compare_pick(declared.swapped(how), candidates.swapped(how),
                               asofs.swapped(how))
        assert again.sha256() == t.sha256()
        assert again.judgement_bytes() == t.judgement_bytes()

    # どちらの場合も入力は 1 文字も書き換わらない
    assert C.Declared.parse(plan["sengen"]).items == declared.items     # type: ignore[arg-type]
    assert C.Candidates.parse(plan["kouho"]).items == candidates.items  # type: ignore[arg-type]
    assert C.Asofs.parse(plan["kijunbi"]).items == asofs.items          # type: ignore[arg-type]


@settings(max_examples=300, derandomize=True, database=None)
@given(left=st.sampled_from(("1026", "1049", "1211", "998.75")),
       right=st.sampled_from(("1026", "1049", "1211", "998.75")),
       juni_left=st.sampled_from(JUNI), juni_right=st.sampled_from(JUNI),
       direction=st.sampled_from(C.DIRECTIONS), tie=st.sampled_from(C.TIES))
def test_値の比較で決まる組は順位の欄で動かない(left: str, right: str, juni_left: str,
                                                juni_right: str, direction: str,
                                                tie: str) -> None:
    """値が違う 2 行の勝敗は、順位の欄をどう書いても向きと値だけで決まる。

    丸めは「丸めない」に固定しているので、2 つの値が違えば同値にならない。順位の欄は 0 / 10 /
    20 / 空欄のどれでもよく、勝者は変わらない(比較の代わりに順位を読む経路が無い)。同じ値の
    ときだけ、宣言のとおりに「決まらない」か「宣言された順位で裁定」へ落ちる。
    """
    sengen = "\n".join([",".join(C.SENGEN_COLUMNS),
                        f"R01,{C.KINDS[1]},{RAN_A},{direction},{TANNI_KOU},"
                        f"{C.ROUND_WHENS[1]},{C.ROUNDINGS[0]},{tie},{SOURCE}"])
    rows = [[f"G0{i + 1}", juni, value] for i, (juni, value)
            in enumerate(((juni_left, left), (juni_right, right)))]
    kouho = "\n".join([",".join(C.KOUHO_COLUMNS)]
                      + [f"P01,R01,{row_id},{juni},{RAN_A},{value},{TANNI_KOU},"
                         f"2026-01-01,2027-01-01,{SOURCE}"
                         for row_id, juni, value in rows])
    kijunbi = "\n".join([",".join(C.KIJUNBI_COLUMNS),
                         f"K01,2026-04-01,{SOURCE},{C.SWAPS[0]}"])
    t = C.compare_pick(C.Declared.parse(sengen), C.Candidates.parse(kouho),
                       C.Asofs.parse(kijunbi))
    assert t.report.ok
    p = t.pairs[0]
    assert p.hits == 2
    if left != right:
        want = max if direction == C.DIRECTIONS[0] else min
        won = want(rows, key=lambda r: Decimal(r[2]))[0]
        assert p.result == C.RESULTS[1]
        assert p.row_id == won
        assert p.value == str(Decimal(dict((r[0], r[2]) for r in rows)[won]))
    elif tie == C.TIES[0]:
        assert p.result == C.RESULTS[2] and p.why == C.UNDECIDED[3]
    elif not juni_left or not juni_right:
        assert p.result == C.RESULTS[2] and p.why == C.UNDECIDED[2]
    elif juni_left == juni_right:
        assert p.result == C.RESULTS[2] and p.why == C.UNDECIDED[4]
    else:
        assert p.result == C.RESULTS[0]
        assert p.row_id == ("G01" if int(juni_left) > int(juni_right) else "G02")
