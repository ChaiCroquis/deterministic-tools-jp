"""backing_axis の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 読んだ範囲は 2 通りしかない。
  (a) 行 1 件ごとに 7 値のどれか 1 つが付き、**7 値の合計が行数**に等しく、**記号別の合計 +
      別枠が行数**に等しく、**旧軸 × 新軸 の対応表のセルの合計も行数**に等しく、**写し元の
      欄名が在る行は確かめた 3 列に 1 件も入らず**、**登録表に無い記号は別枠「宣言が無い」に
      出て**(既定の記号を当てない)、**旧軸を指さない問いは別枠に出て**、**新軸が旧軸と同じ
      問いはその問いだけが止まり**、判定部分に絶対パスが入らず、3 枚の行順を入れ替えても
      同じバイト列になる
  (b) 1 行も数えずに理由コードが返る(数えた行や指紋を取りに行くと例外)
どちらの場合も、この部品は行の台帳も由来の登録表も問いの一覧も 1 文字も書き換えない。

記号を 1〜3 つ登録して(証跡の型は 5 種から引く)、行を 1〜4 件、問いを 1〜2 件引く。行の由来は
登録した記号と登録表に無い記号から引き、旧軸は 2 つの値と空欄から引くので、別枠 2 種も混ざる。
証跡はその記号が要求する型に合わせて作る。3 割くらいの確率でどこか 1 か所を崩す(出典を空に
する / 同じ rule id と欄名の組を 2 行書く / 証跡の型を空にする / 登録外の証跡の型を書く /
意味の欄を空にする)。derandomize=True で毎回同じ入力列を使い、database=None で例を保存しない。

**7 値の分け方はテストの側で別に実装している**(部品の judge / seven を呼ばない)。
2 本目は「登録表に無い記号に既定を当てない」ことを見ている(既定を当てる経路が無い、の物理形)。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from hypothesis import event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import backing_axis as H  # noqa: E402

SOURCE = "合成の出典メモ(架空)L1"
MARKS = ("Y1", "Y2", "Y3")
UNKNOWN = "Y9"                    # 登録表に無い記号
OLD_VALUES = ("D1", "D2", "")     # 空欄は別枠「旧軸が無い」

KOWASHIKATA = ("出典を空にする", "同じ rule id と欄名の組を 2 行書く",
               "証跡の型を空にする", "登録外の証跡の型を書く", "意味の欄を空にする")


def evidence_for(kind: str | None, index: int) -> str:
    """その記号が要求する型に合う証跡を作る(登録表に無い記号には何も要らない)。"""
    if kind is None:
        return ""
    if kind in H.COUNT_TYPES:
        return str(index + 1)
    if kind == H.COPIED_TYPE:
        return f"W{index}"            # 自分の欄名 V{index} とは別の欄
    return "原文が取れていない理由"


def expect(daichou: list[list[str]], touroku: list[list[str]]) -> list[tuple[str, str]]:
    """行ごとの (行 id, 7 値) をテストの側で別に出す(部品の judge を呼ばない)。"""
    kinds = {row[0]: row[2] for row in touroku}
    out: list[tuple[str, str]] = []
    for row in daichou:
        if not row[2]:
            out.append((row[0], "旧軸が無い"))
        elif row[4] not in kinds:
            out.append((row[0], "宣言が無い"))
        else:
            out.append((row[0], H.RESULTS[H.EVIDENCE_TYPES.index(kinds[row[4]])]))
    return sorted(out)


@st.composite
def 合成の3枚(draw: st.DrawFn) -> dict[str, object]:
    """行の台帳 / 由来の登録表 / 問いの一覧(と崩し方)を作る。"""
    touroku = [[mark, f"{mark} の意味", draw(st.sampled_from(H.EVIDENCE_TYPES))]
               for mark in MARKS[:draw(st.integers(1, 3))]]
    kinds = {row[0]: row[2] for row in touroku}

    daichou: list[list[str]] = []
    for i in range(draw(st.integers(1, 4))):
        origin = draw(st.sampled_from(MARKS + (UNKNOWN,)))
        daichou.append([f"B{i:02d}", f"R{i:02d}", draw(st.sampled_from(OLD_VALUES)),
                        f"V{i}", origin, evidence_for(kinds.get(origin), i), SOURCE])

    pairs = draw(st.lists(st.tuples(st.sampled_from(OLD_VALUES + ("D9",)),
                                    st.sampled_from(H.AXES)),
                          min_size=1, max_size=2, unique=True))
    toi = [[old, axis, SOURCE, ""] for old, axis in sorted(pairs)]
    toi[0][3] = H.SWAPS[0]

    kowasu = draw(st.sampled_from([None] * 12 + list(KOWASHIKATA)))
    if kowasu == "出典を空にする":
        daichou[0][6] = ""
    elif kowasu == "同じ rule id と欄名の組を 2 行書く":
        daichou.append(["B99"] + list(daichou[0][1:]))
    elif kowasu == "証跡の型を空にする":
        touroku[0][2] = ""
    elif kowasu == "登録外の証跡の型を書く":
        touroku[0][2] = "たぶん件数"
    elif kowasu == "意味の欄を空にする":
        touroku[0][1] = ""

    def csv(head: tuple[str, ...], body: list[list[str]]) -> str:
        return "\n".join([",".join(head)] + [",".join(r) for r in body])

    return {"daichou": csv(H.DAICHOU_COLUMNS, daichou),
            "touroku": csv(H.TOUROKU_COLUMNS, touroku),
            "toi": csv(H.TOI_COLUMNS, toi), "daichou_rows": daichou,
            "touroku_rows": touroku, "toi_rows": toi, "kowasu": kowasu}


@settings(max_examples=200, derandomize=True, database=None, deadline=None)
@given(plan=合成の3枚())
def test_いつも成り立つこと_数えた行か理由コードか(plan: dict[str, object]) -> None:
    ledger = H.Ledger.parse(plan["daichou"])          # type: ignore[arg-type]
    registry = H.Registry.parse(plan["touroku"])      # type: ignore[arg-type]
    questions = H.Questions.parse(plan["toi"])        # type: ignore[arg-type]
    t = H.backing_axis(ledger, registry, questions)

    expect_stop = plan["kowasu"] is not None
    c = t.counts()
    seven = c["7 値"]
    assert c["行の台帳の行数"] == len(plan["daichou_rows"])     # type: ignore[arg-type]
    assert c["由来の登録表の行数(記号の数)"] == len(plan["touroku_rows"])  # type: ignore[arg-type]
    assert c["問いの数"] == len(plan["toi_rows"])               # type: ignore[arg-type]
    assert c["分母(行数)"] == t.denominator
    assert sum(seven.values()) == (t.denominator if t.judged else 0)  # type: ignore[union-attr]
    assert {j.result for j in t.judged} <= set(H.RESULTS)

    if expect_stop:
        event("(b) 1 行も数えずに止まった")
        assert t.report.ok is False and t.report.pending
        assert {p.reason for p in t.report.pending} <= set(H.TABLE_REASONS)
        assert t.judged == () and t.asked == ()
        assert seven == {r: 0 for r in H.RESULTS}
        for call in (t.judgement_bytes, t.sha256):
            with pytest.raises(RuntimeError):
                call()
    else:
        event("(a) 数えた")
        assert t.report.ok is True
        # 行 1 件ごとに 7 値のどれか 1 つ。テストの側の別実装と一致する
        assert sorted((j.entry.row_id, j.result) for j in t.judged) == \
            expect(plan["daichou_rows"], plan["touroku_rows"])   # type: ignore[arg-type]
        # 3 通りの数え方が全て行数に合う
        assert sum(t.by_mark().values()) + sum(seven[r] for r in H.ASIDE) == t.denominator
        assert sum(int(row["行数"]) for row in t.cross()) == t.denominator
        assert len(t.placeholders()) == seven[H.RESULTS[3]]
        # 写し元の欄名が在る行は、確かめた 3 列に 1 件も入らない
        kinds = {row[0]: row[2] for row in plan["touroku_rows"]}  # type: ignore[union-attr]
        for j in t.judged:
            if kinds.get(j.entry.origin) == H.COPIED_TYPE and j.entry.old_axis:
                assert j.result == H.RESULTS[3] and j.result not in H.CONFIRMED
            if j.result in H.CONFIRMED:
                assert j.entry.evidence.isdecimal()
        # 問いは 3 つの状態しかなく、旧軸を指さない問いは別枠、新軸が旧軸なら止まる
        known = set(ledger.old_values)
        for a in t.asked:
            assert a.state in H.QSTATES
            if a.new_axis == H.AXES[0]:
                assert a.state == H.QSTATES[2] and a.reason == H.STOP_REASONS[10]
                assert a.rows == ()
            elif not a.old_list_id or a.old_list_id not in known:
                assert a.state == H.QSTATES[1] and a.rows == ()
            else:
                assert a.state == H.QSTATES[0]
                assert all(j.entry.old_axis == a.old_list_id for j in a.rows)
        body = t.judgement_bytes().decode("utf-8")
        for word in ("読んだ条件", "絶対パス", str(ROOT)):
            assert word not in body
        how = questions.swap or H.SWAPS[0]
        again = H.backing_axis(ledger.swapped(how), registry.swapped(how),
                               questions.swapped(how))
        assert again.sha256() == t.sha256()
        assert again.judgement_bytes() == t.judgement_bytes()

    # どちらの場合も入力は 1 文字も書き換わらない
    assert H.Ledger.parse(plan["daichou"]).items == ledger.items      # type: ignore[arg-type]
    assert H.Registry.parse(plan["touroku"]).items == registry.items  # type: ignore[arg-type]
    assert H.Questions.parse(plan["toi"]).items == questions.items    # type: ignore[arg-type]


@settings(max_examples=300, derandomize=True, database=None)
@given(kind=st.sampled_from(H.EVIDENCE_TYPES), registered=st.booleans(),
       old_axis=st.sampled_from(OLD_VALUES))
def test_登録表に無い記号に既定を当てない(kind: str, registered: bool,
                                          old_axis: str) -> None:
    """登録表に無い記号は、証跡の欄が埋まっていても別枠「宣言が無い」に出る。

    旧軸の欄が空なら、記号が登録されていても別枠「旧軸が無い」に出る(どちらの別枠も、
    確かめた 3 列には入らない)。
    """
    origin = "Y1" if registered else UNKNOWN
    daichou = "\n".join([",".join(H.DAICHOU_COLUMNS),
                         f"B01,R01,{old_axis},V01,{origin},"
                         f"{evidence_for(kind, 0)},{SOURCE}"])
    touroku = "\n".join([",".join(H.TOUROKU_COLUMNS), f"Y1,Y1 の意味,{kind}"])
    toi = "\n".join([",".join(H.TOI_COLUMNS),
                     f"{old_axis},{H.AXES[1]},{SOURCE},{H.SWAPS[0]}"])
    t = H.backing_axis(H.Ledger.parse(daichou), H.Registry.parse(touroku),
                       H.Questions.parse(toi))
    assert t.report.ok
    j = t.judged[0]
    if not old_axis:
        assert j.result == H.RESULTS[6]
    elif not registered:
        assert j.result == H.RESULTS[5]
    else:
        assert j.result == H.RESULTS[H.EVIDENCE_TYPES.index(kind)]
    assert t.denominator == 1 and sum(t.seven().values()) == 1
    if j.result in H.ASIDE:
        assert t.by_mark().get("Y1", 0) == 0
