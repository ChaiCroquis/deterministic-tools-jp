"""rank_clash の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 読んだ範囲は 2 通りしかない。
  (a) (rule × 対象)の組ごとに 4 値が 1 つだけ付き、4 値の合計が rule 数 × 対象数に等しく、
      決まらない理由別の合計が決まらないの件数に等しく、1 本に決まった組の勝った行 id は
      行の表にそのまま在る id で(ほかの 3 値には行 id も順位も付かない)、判定部分に時刻・
      ホスト名・絶対パスが入らず、3 枚の行順を入れ替えても同じバイト列になる
  (b) 1 組も読まずに理由コードが返る(読んだ組や指紋を取りに行くと例外)
どちらの場合も、この部品は行の表も裁定の宣言も対象の表も 1 文字も書き換えない。

rule を 1〜3 本作り、裁定の種類を振る。行を rule ごとに 1〜3 本作り、各次元の値を「宣言された
記号」と「具体的な値」から引き、順位を 0 / 10 / 20 / 空欄から引く。対象を 1〜3 件作る。さらに
3 割くらいの確率で 1 か所だけ崩す(出典を空にする / 宣言に無い順位の値を書く / 宣言外の記号を
書く / 宣言表に無い rule を名乗る / 同じ行 id を 2 行書く / 同じ rule の宣言を 2 行書く)。
derandomize=True で毎回同じ入力列を使い、database=None で見つけた例を保存しない。

**4 値はテストの側で別に組み立てている**(部品の判定を呼ばず、3 枚の表の行から直に決める)。
2 本目は「具体的に書かれた行は、順位が同じなら勝たない」ことを見ている(具体さで勝たせる経路
が無い、の物理形)。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from hypothesis import event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import rank_clash as R  # noqa: E402

SOURCE = "合成の出典メモ(架空)L1"
DIM_A, DIM_B = "次元A", "次元B"
WILD = "*"
A_VALUES = ("a1", "a2")
B_VALUES = ("b1", "b2")
PRIORITIES = "0=本則|10=経過措置|20=特例"
JUNI = ("0", "10", "20", "")          # 空欄は「順位の欄が空」になる

KOWASHIKATA = ("出典を空にする", "宣言に無い順位の値を書く", "宣言外の記号を書く",
               "宣言表に無い rule を名乗る", "同じ行 id を 2 行書く",
               "同じ rule の宣言を 2 行書く")


def seg(a: str, b: str) -> str:
    return f"{DIM_A}={a}{R.SEG_SEP}{DIM_B}={b}"


@st.composite
def 合成の3枚(draw: st.DrawFn) -> dict[str, object]:
    """行の表 / 裁定の宣言 / 対象の表(と崩し方)を作る。"""
    rule_ids = [f"R{i + 1:02d}" for i in range(draw(st.integers(1, 3)))]
    sengen = [[rid, draw(st.sampled_from(R.KINDS)), PRIORITIES, WILD, R.TIES[0],
               SOURCE] for rid in rule_ids]

    gyou: list[list[str]] = []
    for rid in rule_ids:
        for _ in range(draw(st.integers(1, 3))):
            gyou.append([f"G{len(gyou) + 1:02d}", rid,
                         seg(draw(st.sampled_from((WILD,) + A_VALUES)),
                             draw(st.sampled_from((WILD,) + B_VALUES))),
                         draw(st.sampled_from(JUNI)), SOURCE])

    combos = [(a, b) for a in A_VALUES for b in B_VALUES]
    chosen = draw(st.lists(st.sampled_from(combos), min_size=1, max_size=3,
                           unique=True))
    taishou = [[f"T{i + 1:02d}", seg(a, b), SOURCE, ""]
               for i, (a, b) in enumerate(sorted(chosen))]
    taishou[0][3] = R.SWAPS[0]

    kowasu = draw(st.sampled_from([None] * 6 + list(KOWASHIKATA)))
    if kowasu == "出典を空にする":
        gyou[0][4] = ""
    elif kowasu == "宣言に無い順位の値を書く":
        gyou[0][3] = "5"
    elif kowasu == "宣言外の記号を書く":
        gyou[0][2] = seg("-", WILD)
    elif kowasu == "宣言表に無い rule を名乗る":
        gyou[0][1] = "R09"
    elif kowasu == "同じ行 id を 2 行書く":
        gyou.append([gyou[0][0], rule_ids[0], seg(WILD, WILD), "0", SOURCE])
    elif kowasu == "同じ rule の宣言を 2 行書く":
        sengen.append([rule_ids[0], R.KINDS[0], PRIORITIES, WILD, R.TIES[0], SOURCE])

    def csv(head: tuple[str, ...], body: list[list[str]]) -> str:
        return "\n".join([",".join(head)] + [",".join(r) for r in body])

    return {"gyou": csv(R.GYOU_COLUMNS, gyou),
            "sengen": csv(R.SENGEN_COLUMNS, sengen),
            "taishou": csv(R.TAISHOU_COLUMNS, taishou),
            "gyou_rows": gyou, "sengen_rows": sengen, "taishou_rows": taishou,
            "kowasu": kowasu}


def 期待する4値(plan: dict[str, object]) -> dict[str, int]:
    """4 値を、3 枚の表の行から直に組み立てる(部品の判定は呼ばない)。"""
    rules = {row[0]: row[1] for row in plan["sengen_rows"]}   # type: ignore[union-attr]
    out = dict.fromkeys(R.RESULTS, 0)
    for rid in sorted(rules):
        for target in sorted(plan["taishou_rows"], key=lambda r: r[0]):   # type: ignore[arg-type]
            have = dict(part.split("=") for part in target[1].split(R.SEG_SEP))
            hit = []
            for row in plan["gyou_rows"]:                     # type: ignore[union-attr]
                if row[1] != rid:
                    continue
                cells = dict(part.split("=") for part in row[2].split(R.SEG_SEP))
                if all(v == WILD or have.get(k) == v for k, v in cells.items()):
                    hit.append(row)
            if not hit:
                out[R.RESULTS[1]] += 1
            elif len(hit) == 1:
                out[R.RESULTS[0]] += 1
            elif rules[rid] != R.KINDS[0] or any(not row[3] for row in hit):
                out[R.RESULTS[2]] += 1
            else:
                top = max(int(row[3]) for row in hit)
                best = [row for row in hit if int(row[3]) == top]
                out[R.RESULTS[0 if len(best) == 1 else 2]] += 1
    return out


@settings(max_examples=200, derandomize=True, database=None, deadline=None)
@given(plan=合成の3枚())
def test_いつも成り立つこと_読んだ組か理由コードか(plan: dict[str, object]) -> None:
    sheet = R.Sheet.parse(plan["gyou"])                       # type: ignore[arg-type]
    declared = R.Declared.parse(plan["sengen"])               # type: ignore[arg-type]
    targets = R.Targets.parse(plan["taishou"])                # type: ignore[arg-type]
    t = R.rank_clash(sheet, declared, targets)

    expect_stop = plan["kowasu"] is not None
    c = t.counts()
    four = c["4 値"]
    assert c["行の表の行数"] == len(plan["gyou_rows"])        # type: ignore[arg-type]
    assert c["裁定の宣言の行数(rule 数)"] == len(plan["sengen_rows"])   # type: ignore[arg-type]
    assert c["対象数"] == len(plan["taishou_rows"])           # type: ignore[arg-type]
    assert c["分母(rule 数 × 対象数)"] == t.report.rules * t.report.targets
    assert sum(four.values()) == len(t.pairs)                 # type: ignore[union-attr]
    # 表が揃う前に止まったら 1 組も読まない。読んだなら組と 1 対 1 で付く
    assert len(t.pairs) in (0, t.denominator)
    assert {p.result for p in t.pairs} <= set(R.RESULTS)
    if t.pairs:
        assert four == 期待する4値(plan)

    # 勝った行 id が付くのは「1 本に決まった」組だけ。しかも行の表にそのまま在る id
    have = {r.row_id for r in sheet.items}
    for p in t.pairs:
        if p.result == R.RESULTS[0]:
            assert p.row_id in have
            assert p.why == "" and p.hits >= 1
        else:
            assert p.row_id == "" and p.priority == ""
            assert (p.why in R.UNDECIDED) == (p.result == R.RESULTS[2])

    if expect_stop:
        event("(b) 止まった")
        assert t.report.ok is False
        assert t.report.pending
        assert {p.reason for p in t.report.pending} <= set(R.STOP_REASONS)
        for call in (lambda: t.verdict, t.judgement_bytes, t.sha256):
            with pytest.raises(RuntimeError):
                call()
    else:
        event("(a) 読んだ")
        assert t.report.ok is True
        assert four[R.RESULTS[3]] == 0                        # type: ignore[index]
        # 決まらない理由別の合計 = 決まらないの件数
        assert sum(t.by_why().values()) == four[R.RESULTS[2]]  # type: ignore[index]
        assert sum(four.values()) == t.denominator
        body = t.judgement_bytes().decode("utf-8")
        for word in (t.read_at, t.host, "読んだ時刻", "ホスト名"):
            assert word not in body
        # 3 枚の行順を入れ替えても同じバイト列
        again = R.rank_clash(sheet.swapped(R.SWAPS[0]), declared.swapped(R.SWAPS[0]),
                             targets.swapped(targets.swap or R.SWAPS[0]))
        assert again.sha256() == t.sha256()
        assert again.judgement_bytes() == t.judgement_bytes()

    # どちらの場合も入力は 1 文字も書き換わらない
    assert R.Sheet.parse(plan["gyou"]).items == sheet.items        # type: ignore[arg-type]
    assert R.Declared.parse(plan["sengen"]).items == declared.items  # type: ignore[arg-type]
    assert R.Targets.parse(plan["taishou"]).items == targets.items   # type: ignore[arg-type]


@settings(max_examples=300, derandomize=True, database=None)
@given(wild_priority=st.sampled_from(("0", "10", "20")),
       narrow_priority=st.sampled_from(("0", "10", "20")),
       narrow=st.sampled_from(A_VALUES), kind=st.sampled_from(R.KINDS))
def test_具体的に書かれた行は順位が同じなら勝たない(wild_priority: str,
                                                    narrow_priority: str,
                                                    narrow: str,
                                                    kind: str) -> None:
    """同じ対象に当たる 2 本の勝敗は、次元の具体さではなく順位の欄だけで決まる。

    片方は両次元が宣言された記号、もう片方は次元A が具体的な値。どちらも同じ対象に当たる。
    順位が同じなら「決まらない」に落ち、違えば順位の高い方が勝つ(具体的な方が自動で勝つ
    経路も、宣言された記号の行を弱くする経路も無い)。
    """
    gyou = "\n".join([",".join(R.GYOU_COLUMNS),
                      f"G01,R01,{seg(WILD, WILD)},{wild_priority},{SOURCE}",
                      f"G02,R01,{seg(narrow, WILD)},{narrow_priority},{SOURCE}"])
    sengen = "\n".join([",".join(R.SENGEN_COLUMNS),
                        f"R01,{kind},{PRIORITIES},{WILD},{R.TIES[0]},{SOURCE}"])
    taishou = "\n".join([",".join(R.TAISHOU_COLUMNS),
                         f"T01,{seg(narrow, B_VALUES[0])},{SOURCE},{R.SWAPS[0]}"])
    t = R.rank_clash(R.Sheet.parse(gyou), R.Declared.parse(sengen),
                     R.Targets.parse(taishou))
    assert t.report.ok
    p = t.pairs[0]
    assert p.hits == 2
    if kind != R.KINDS[0]:
        assert p.result == R.RESULTS[2] and p.why == R.UNDECIDED[2]
    elif wild_priority == narrow_priority:
        assert p.result == R.RESULTS[2] and p.why == R.UNDECIDED[0]
        assert p.row_id == ""
    else:
        assert p.result == R.RESULTS[0]
        higher = "G02" if int(narrow_priority) > int(wild_priority) else "G01"
        assert p.row_id == higher
