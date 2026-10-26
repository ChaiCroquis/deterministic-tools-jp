"""overlap_check の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 読んだ範囲は 2 通りしかない。
  (a) 問い 1 件ごとに、7 値のどれか 1 つが付くか、同じ年度の指定で止まるかのどちらかで、
      **7 値の合計 + 止まった問い = 問いの数**、**5 値 + 単位がそろわない = 重なり候補の数**、
      **年度ペアごとの内訳の合計 = 問いの数**、**寄せ方の宣言が無い項目は両側の欄を持たない
      まま「寄せ方が無い」に出て**(同じ文字列でも自動で寄せない)、**採用元が経路 B の欄
      そのものの問いは一致にも不一致にも入らず**、**資料が手元に無い年度の問いは重なり候補の
      分母に入らず**、判定部分に絶対パスが入らず、4 枚の行順を入れ替えても同じバイト列になる
  (b) 1 件も数えずに理由コードが返る(数えた問いや指紋を取りに行くと例外)
どちらの場合も、この部品は 4 枚の表を 1 文字も書き換えない。

資料を 2〜3 枚(年度は 1 枚に 1 つ)、項目を 1〜3 個、問いを 1〜3 件引く。各資料の変更前 /
変更後の欄に項目を入れるかを引き、単位は 円 / 日 / 空欄から、値は 2 通りから引くので、一致・
不一致・単位がそろわないが混ざる。寄せ方の宣言は項目ごとに引くので「寄せ方が無い」も混ざり、
問いの年度には資料の無い `T0` も混ざる。3 割くらいの確率でどこか 1 か所を崩す(出典を空にする /
値を空にする / 寄せてよい理由を空にする / 採用元の欄の役を登録外にする / 採用元の資料 id を
抽出表に無い id にする / 同じ項目名の採用元を 2 行書く)。derandomize=True で毎回同じ入力列を
使い、database=None で例を保存しない。

**7 値の分け方はテストの側で別に実装している**(部品の judge / seven を呼ばない)。
2 本目は「採用元が経路 B の欄そのものなら、両側の値が同じでも一致に入れない」ことを見ている。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from hypothesis import event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import overlap_check as H  # noqa: E402

SOURCE = "合成の出典メモ(架空)L1"
MAE, ATO = H.ROLES
UNITS = ("円", "日", "")
VALUES = ("v1", "v2")
MISSING_YEAR = "T0"          # 資料が手元に無い年度

KOWASHIKATA = ("出典を空にする", "値を空にする", "寄せてよい理由を空にする",
               "採用元の欄の役を登録外にする", "採用元の資料 id を抽出表に無い id にする",
               "同じ項目名の採用元を 2 行書く")


def classify(chuushutsu: list[list[str]], yose: list[list[str]],
             saiyou: list[list[str]], toi: list[list[str]]) -> list[tuple[str, str]]:
    """問いごとの (鍵, 7 値 または 止まった) をテストの側で別に出す(部品を呼ばない)。"""
    cells = {(r[0], r[3], r[2]): (r[4], r[5]) for r in chuushutsu}
    doc_of: dict[str, str] = {}
    for r in chuushutsu:
        doc_of.setdefault(r[1], r[0])
    bridge = {r[0]: r[1] for r in yose}
    take = {r[1]: (r[2], r[3]) for r in saiyou}
    out: list[tuple[str, str]] = []
    for year_a, year_b, item, _source, _swap in toi:
        key = f"{year_a}>{year_b}:{item}"
        if year_a == year_b:
            out.append((key, "止まった"))
            continue
        doc_a, doc_b = doc_of.get(year_a), doc_of.get(year_b)
        if doc_a is None or doc_b is None:
            out.append((key, "資料が手元に無い"))
            continue
        if item not in bridge:
            out.append((key, "寄せ方が無い"))
            continue
        a = cells.get((doc_a, ATO, item))
        b = cells.get((doc_b, MAE, bridge[item]))
        if a is None or b is None:
            out.append((key, "重なりが無い"))
        elif not a[0] or not b[0] or a[0] != b[0]:
            out.append((key, "単位がそろわない"))
        elif take.get(item) == (doc_b, MAE):
            out.append((key, "採用元が同じ欄"))
        else:
            out.append((key, "一致" if a[1] == b[1] else "不一致"))
    return sorted(out)


@st.composite
def 合成の4枚(draw: st.DrawFn) -> dict[str, object]:
    """抽出表 / 名前の寄せ方の表 / 採用元の宣言 / 問いの一覧(と崩し方)を作る。"""
    docs = [(f"S{i + 1}", f"T{i + 1}") for i in range(draw(st.integers(2, 3)))]
    items = [f"K{i + 1:02d}" for i in range(draw(st.integers(1, 3)))]

    chuushutsu = [["S1", "T1", items[0], ATO, "円", "v1", SOURCE]]
    for doc_id, year in docs:
        for item in items:
            for role in H.ROLES:
                if (doc_id, item, role) == ("S1", items[0], ATO):
                    continue              # 1 行目は必ず置く(0 行の表は読めない)
                if draw(st.booleans()):
                    chuushutsu.append([doc_id, year, item, role,
                                       draw(st.sampled_from(UNITS)),
                                       draw(st.sampled_from(VALUES)), SOURCE])

    yose = [[item, item, "年度で同じ項目名", SOURCE] for item in items
            if draw(st.booleans())]
    if not yose:                          # 0 行の表は読めないので 1 組は置く
        yose = [[items[0], items[0], "年度で同じ項目名", SOURCE]]

    # 採用元の資料 id は、抽出表に行が在る資料から引く(無い id は別の崩し方で試す)
    present = sorted({row[0] for row in chuushutsu})
    saiyou = [[f"G{i:02d}", item, draw(st.sampled_from(present)),
               draw(st.sampled_from(H.ROLES)), SOURCE]
              for i, item in enumerate(items)]

    years = [y for _, y in docs] + [MISSING_YEAR]
    asked = draw(st.lists(st.tuples(st.sampled_from(years), st.sampled_from(years),
                                    st.sampled_from(items)),
                          min_size=1, max_size=3, unique=True))
    toi = [[a, b, item, SOURCE, ""] for a, b, item in sorted(asked)]
    toi[0][4] = H.SWAPS[0]

    kowasu = draw(st.sampled_from([None] * 14 + list(KOWASHIKATA)))
    if kowasu == "出典を空にする":
        chuushutsu[0][6] = ""
    elif kowasu == "値を空にする":
        chuushutsu[0][5] = ""
    elif kowasu == "寄せてよい理由を空にする":
        yose[0][2] = ""
    elif kowasu == "採用元の欄の役を登録外にする":
        saiyou[0][3] = "改定後"
    elif kowasu == "採用元の資料 id を抽出表に無い id にする":
        saiyou[0][2] = "S9"
    elif kowasu == "同じ項目名の採用元を 2 行書く":
        saiyou.append(["G99", items[0], "S1", ATO, SOURCE])

    def csv(head: tuple[str, ...], body: list[list[str]]) -> str:
        return "\n".join([",".join(head)] + [",".join(r) for r in body])

    return {"chuushutsu": csv(H.CHUUSHUTSU_COLUMNS, chuushutsu),
            "yose": csv(H.YOSE_COLUMNS, yose),
            "saiyou": csv(H.SAIYOU_COLUMNS, saiyou),
            "toi": csv(H.TOI_COLUMNS, toi),
            "chuushutsu_rows": chuushutsu, "yose_rows": yose,
            "saiyou_rows": saiyou, "toi_rows": toi, "kowasu": kowasu}


@settings(max_examples=200, derandomize=True, database=None, deadline=None)
@given(plan=合成の4枚())
def test_いつも成り立つこと_数えた問いか理由コードか(plan: dict[str, object]) -> None:
    extracts = H.Extracts.parse(plan["chuushutsu"])   # type: ignore[arg-type]
    bridges = H.Bridges.parse(plan["yose"])           # type: ignore[arg-type]
    takes = H.Takes.parse(plan["saiyou"])             # type: ignore[arg-type]
    questions = H.Questions.parse(plan["toi"])        # type: ignore[arg-type]
    t = H.overlap_check(extracts, bridges, takes, questions)

    expect_stop = plan["kowasu"] is not None
    c = t.counts()
    seven = c["7 値"]
    assert c["抽出表の行数"] == len(plan["chuushutsu_rows"])      # type: ignore[arg-type]
    assert c["名前の寄せ方の表の行数"] == len(plan["yose_rows"])  # type: ignore[arg-type]
    assert c["採用元の宣言の行数"] == len(plan["saiyou_rows"])    # type: ignore[arg-type]
    assert c["問いの数"] == len(plan["toi_rows"])                 # type: ignore[arg-type]
    assert {j.result for j in t.judged} <= set(H.RESULTS)
    assert all(isinstance(v, int) for v in seven.values())        # type: ignore[union-attr]

    if expect_stop:
        event("(b) 1 件も数えずに止まった")
        assert t.report.ok is False and t.report.pending
        assert {p.reason for p in t.report.pending} <= set(H.TABLE_REASONS)
        assert t.judged == ()
        assert seven == {r: 0 for r in H.RESULTS}
        assert t.denominator == 0 and t.halted() == 0
        for call in (t.judgement_bytes, t.sha256):
            with pytest.raises(RuntimeError):
                call()
    else:
        event("(a) 数えた")
        assert t.report.ok is True
        # 問い 1 件ごとに 7 値のどれか 1 つ、または止まった。テスト側の別実装と一致する
        mine = sorted((f"{j.question.year_a}>{j.question.year_b}:{j.question.item}",
                       "止まった" if j.stopped else j.result) for j in t.judged)
        assert mine == classify(plan["chuushutsu_rows"], plan["yose_rows"],
                                plan["saiyou_rows"], plan["toi_rows"])
        # 3 通りの数え方が全て合う
        assert sum(seven.values()) + t.halted() == t.question_denominator()
        assert sum(seven[r] for r in H.GOUI) + seven["単位がそろわない"] \
            == t.denominator
        pairs = t.by_pair()
        assert sum(int(row["問いの数"]) for row in pairs) == t.question_denominator()
        for r in H.RESULTS:
            assert sum(int(row["7 値"][r]) for row in pairs) == seven[r]
        # 一覧の件数と 7 値が合う
        assert len(t.mismatches()) == seven["不一致"]
        assert len(t.self_checks()) == seven["採用元が同じ欄"]
        assert len(t.no_overlap()) == seven["重なりが無い"]
        assert len(t.stopped_questions()) == t.halted()
        declared = {row[0] for row in plan["yose_rows"]}   # type: ignore[union-attr]
        for j in t.judged:
            if j.stopped:
                assert j.reason == H.STOP_REASONS[9] and j.cell_a is None
                continue
            # 寄せ方の宣言が無い項目は、比べに行かないまま別の値に出る
            if j.question.item not in declared and j.result != "資料が手元に無い":
                assert j.result == "寄せ方が無い"
                assert j.cell_a is None and j.cell_b is None
            # 採用元が経路 B の欄そのものなら、一致にも不一致にも入らない
            take = takes.of(j.question.item)
            doc_b = extracts.doc_of_year(j.question.year_b)
            if (j.cell_a and j.cell_b and take
                    and (take.doc_id, take.role) == (doc_b, MAE)
                    and j.cell_a.unit == j.cell_b.unit and j.cell_a.unit):
                assert j.result == "採用元が同じ欄"
                assert j.result not in H.TOTSUGOU
            # 資料が手元に無い問いは重なり候補の分母に入らない
            if j.result == "資料が手元に無い":
                assert j.candidate is False
        body = t.judgement_bytes().decode("utf-8")
        for word in ("読んだ条件", "絶対パス", str(ROOT)):
            assert word not in body
        how = questions.swap or H.SWAPS[0]
        again = H.overlap_check(extracts.swapped(how), bridges.swapped(how),
                                takes.swapped(how), questions.swapped(how))
        assert again.sha256() == t.sha256()
        assert again.judgement_bytes() == t.judgement_bytes()

    # どちらの場合も入力は 1 文字も書き換わらない
    assert H.Extracts.parse(plan["chuushutsu"]).items == extracts.items  # type: ignore[arg-type]
    assert H.Bridges.parse(plan["yose"]).items == bridges.items          # type: ignore[arg-type]
    assert H.Takes.parse(plan["saiyou"]).items == takes.items            # type: ignore[arg-type]
    assert H.Questions.parse(plan["toi"]).items == questions.items       # type: ignore[arg-type]


@settings(max_examples=300, derandomize=True, database=None)
@given(role=st.sampled_from(H.ROLES), doc=st.sampled_from(("S1", "S2")),
       same=st.booleans(), declared=st.booleans())
def test_採用元が経路Bの欄なら一致に入れない(role: str, doc: str, same: bool,
                                              declared: bool) -> None:
    """両側の値が同じでも、行の値を採った欄が経路 B そのものなら「採用元が同じ欄」に出る。

    寄せ方の宣言が無ければ、値が同じでも比べに行かずに「寄せ方が無い」に出る(同じ文字列を
    自動で寄せる経路が無い)。
    """
    value_b = "v1" if same else "v2"
    chuushutsu = "\n".join([",".join(H.CHUUSHUTSU_COLUMNS),
                            f"S1,T1,K01,{ATO},円,v1,{SOURCE}",
                            f"S2,T2,K01,{MAE},円,{value_b},{SOURCE}"])
    yose = "\n".join([",".join(H.YOSE_COLUMNS),
                      f"{'K01' if declared else 'K99'},K01,年度で同じ項目名,{SOURCE}"])
    saiyou = "\n".join([",".join(H.SAIYOU_COLUMNS),
                        f"G01,K01,{doc},{role},{SOURCE}"])
    toi = "\n".join([",".join(H.TOI_COLUMNS),
                     f"T1,T2,K01,{SOURCE},{H.SWAPS[0]}"])
    t = H.overlap_check(H.Extracts.parse(chuushutsu), H.Bridges.parse(yose),
                        H.Takes.parse(saiyou), H.Questions.parse(toi))
    assert t.report.ok
    j = t.judged[0]
    if not declared:
        assert j.result == "寄せ方が無い" and j.cell_a is None
    elif (doc, role) == ("S2", MAE):
        assert j.result == "採用元が同じ欄"
        assert j.result not in H.TOTSUGOU
        assert len(t.self_checks()) == 1 and t.seven()["一致"] == 0
    else:
        assert j.result == ("一致" if same else "不一致")
        assert t.self_checks() == []
    assert t.question_denominator() == 1 and sum(t.seven().values()) == 1
