"""off_scope の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文を検査にする。

いつも成り立つこと: 読んだ範囲は 2 通りしかない。
  (a) 4 値を付けた: **項目 1 件ごとに 4 値の 5 欄か別枠 7 のどれか 1 つ**が付き、
      **その合計 = 項目の件数**、**領域の宣言ごとの内訳の合計も在り所ごとの内訳の合計も
      同じ数**になる。**領域が `内` と宣言された項目は (A)(B)(C) と (D) 境界 に入らず**、
      **行数を数えない在り所は `数えられない` を返して 0 件と同じ値にならず**、
      **必須の欄が空で在り所も `無い` 項目は 4 値に入らず**、**項目名は判定に入らない**
      (名前を入れ替えても判定部分は同じバイト列)。6 枚の行順を 3 通りに入れ替えても
      同じバイト列になる
  (b) 1 項目も数えずに理由コードが返る(4 値や sha256 を取りに行くと例外)
どちらの場合も、この部品は 6 枚の表を 1 文字も書き換えない。

項目を 1〜3 件、在り所を項目ごとに 0〜2 件、入る形を項目ごとに 0〜1 件引く。3 回に 1 回
くらいどこか 1 か所を崩す(崩し方は 7 通りで、どれが引かれるかは hypothesis が決めるので、
7 通りすべてが毎回出るとは限らない。**7 個の理由コード全部に道が在ることは、崩した表を
直に通す test_measure_seven_stop_reasons_all_reachable の側で決定論的に確かめている**)。
derandomize=True で毎回同じ 200 通りを使い、database=None で例を保存しない。

**4 値の決め方はテストの側で別に実装している**(部品の judge / five / extras を呼ばない)。
2 本目は「4 値を決めるのは領域の宣言と在り所と入る形だけ」を総当たりで見る。
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
import off_scope as H  # noqa: E402

ASOF = "2026-09-20"
I_SRC = "合成の項目のメモ(架空)L1"
D_SRC = "合成の領域の登録のメモ(架空)L1"
P_SRC = "合成の在り所のメモ(架空)L1"
S_SRC = "合成の入る形のメモ(架空)L1"
B_SRC = "合成の basis の登録のメモ(架空)L1"
Y_SRC = "合成の payload の登録のメモ(架空)L1"

OUT1, EDGE, IN1 = "領域 1", "領域 2", "領域 3"
UNREGISTERED_DOMAIN = "領域 9"
NAMES = ("合成の項目 A(架空)", "合成の項目 B(架空)")
REQUIRED = ("—", "", "合成の必須の宣言(架空)")
BASIS_OK = "基準日 A"
BASIS_NG = "基準日 C"
PAYLOADS = ("—", "表", "値 1 つ")
SELECTORS = ("—", "区分", "区分 / 人数")
PERIODS = ("—", "合成の期間の終わり(架空)")
COUNTS = ("0", "1", "12")

DOMAIN_ROWS = [[OUT1, H.STANCES[1], D_SRC],
               [EDGE, H.STANCES[2], D_SRC],
               [IN1, H.STANCES[0], D_SRC]]
BASIS_ROWS = [[BASIS_OK, "合成の欄名(架空)", B_SRC]]
PAYLOAD_ROWS = [["表", "合成の種別(架空)", Y_SRC]]

KOWASHIKATA = ("領域の登録の出典を空にする", "項目 id を重複させる",
               "領域の登録の宣言を決めた外にする", "在り所の記号を決めた外にする",
               "行数を整数でない文字にする", "基準日を渡さない",
               "basis の登録表を空にする")


def my_value(item: list[str], placements: list[list[str]], shapes: list[list[str]],
             domains: list[list[str]], basis: list[list[str]],
             payload: list[list[str]]) -> str:
    """項目 1 件の 4 値 / 別枠をテストの側で出す(部品の judge を呼ばない)。"""
    iid, _name, domain, required, _note, source = item
    stance = {r[0]: r[1] for r in domains}
    mine = [p for p in placements if p[0] == iid]
    shape = next((s for s in shapes if s[0] == iid), None)
    marks = sorted({p[1] for p in mine})
    nashi = (marks == [H.PLACES[4]]) or not marks

    if (not source or any(not p[4] for p in mine)
            or (shape is not None and not shape[5])):
        return H.BETSUWAKU[0]
    if domain not in stance:
        return H.BETSUWAKU[1]
    if len(marks) > 1:
        return H.BETSUWAKU[2]
    if shape is not None and shape[1] not in ("—", "") and \
            shape[1] not in {r[0] for r in basis}:
        return H.BETSUWAKU[3]
    if shape is not None and (shape[2] in ("—", "")
                              or shape[2] not in {r[0] for r in payload}):
        return H.BETSUWAKU[4]
    if shape is not None and shape[4] not in ("—", ""):
        return H.BETSUWAKU[5]
    if required in ("—", "") and nashi:
        return H.BETSUWAKU[6]
    if stance[domain] == H.STANCES[0]:
        return H.VALUES[4]
    if marks and marks[0] in H.COUNTED:
        return H.VALUES[1]
    if marks and marks[0] in H.DESTINED:
        return H.VALUES[2]
    if stance[domain] == H.STANCES[2] and shape is not None and all(
            shape[k] not in ("—", "") for k in (1, 2, 3)):
        return H.VALUES[3]
    return H.VALUES[0]


@st.composite
def 合成の6枚(draw: st.DrawFn) -> dict[str, object]:
    """項目 / 在り所 / 入る形 の 3 枚と登録表 3 枚(と崩し方)を作る。"""
    items: list[list[str]] = []
    placements: list[list[str]] = []
    shapes: list[list[str]] = []
    for k in range(1, draw(st.integers(1, 3)) + 1):
        iid = f"I{k}"
        items.append([iid, draw(st.sampled_from(NAMES)),
                      draw(st.sampled_from((OUT1, EDGE, IN1,
                                            UNREGISTERED_DOMAIN))),
                      draw(st.sampled_from(REQUIRED)), "—",
                      draw(st.sampled_from((I_SRC, I_SRC, I_SRC, "")))])
        for _ in range(draw(st.integers(0, 2))):
            place = draw(st.sampled_from(H.PLACES))
            count = draw(st.sampled_from(COUNTS)) if place in H.COUNTED else "—"
            origin = draw(st.sampled_from(H.ORIGINS + ("—",))) \
                if place in H.COUNTED else "—"
            placements.append([iid, place, count, origin,
                               draw(st.sampled_from((P_SRC, P_SRC, P_SRC, "")))])
        if draw(st.booleans()):
            shapes.append([iid, draw(st.sampled_from((BASIS_OK, BASIS_NG, "—"))),
                           draw(st.sampled_from(PAYLOADS)),
                           draw(st.sampled_from(SELECTORS)),
                           draw(st.sampled_from(PERIODS)),
                           draw(st.sampled_from((S_SRC, S_SRC, S_SRC, "")))])
    domains = [list(r) for r in DOMAIN_ROWS]
    basis = [list(r) for r in BASIS_ROWS]
    payload = [list(r) for r in PAYLOAD_ROWS]
    asof = ASOF

    # 3 回に 1 回くらい崩す。崩す側は 7 通りを平らに引く(負の数は「崩さない」)
    pick = draw(st.sampled_from(tuple(range(-14, len(KOWASHIKATA)))))
    kowasu = KOWASHIKATA[pick] if pick >= 0 else None
    if kowasu == KOWASHIKATA[0]:
        domains[0][2] = ""
    elif kowasu == KOWASHIKATA[1]:
        items.append([items[0][0], NAMES[0], OUT1, REQUIRED[2], "—", I_SRC])
    elif kowasu == KOWASHIKATA[2]:
        domains[0][1] = "たぶん外"
    elif kowasu == KOWASHIKATA[3]:
        placements.append([items[0][0], "たぶん無い", "—", "—", P_SRC])
    elif kowasu == KOWASHIKATA[4]:
        placements.append([items[0][0], H.PLACES[0], "3 件", H.ORIGINS[0], P_SRC])
    elif kowasu == KOWASHIKATA[5]:
        asof = ""
    elif kowasu == KOWASHIKATA[6]:
        basis = []

    def tbl(head: tuple[str, ...], body: list[list[str]]) -> str:
        buf = io.StringIO()
        _csv.writer(buf, lineterminator="\n").writerows([list(head)] + body)
        return buf.getvalue()

    return {"items": tbl(H.ITEM_COLUMNS, items),
            "domains": tbl(H.DOMAIN_COLUMNS, domains),
            "placements": tbl(H.PLACE_COLUMNS, placements),
            "shapes": tbl(H.SHAPE_COLUMNS, shapes),
            "basis": tbl(H.BASIS_COLUMNS, basis),
            "payload": tbl(H.PAYLOAD_COLUMNS, payload),
            "items_rows": items, "placements_rows": placements,
            "shapes_rows": shapes, "domains_rows": domains,
            "basis_rows": basis, "payload_rows": payload,
            "asof": asof, "kowasu": kowasu}


def six_of(plan: dict[str, object]):
    items = H.Items.parse(plan["items"])        # type: ignore[arg-type]
    ids = items.ids
    return (items, H.Domains.parse(plan["domains"]),           # type: ignore[arg-type]
            H.Placements.parse(plan["placements"], ids),       # type: ignore[arg-type]
            H.Shapes.parse(plan["shapes"], ids),               # type: ignore[arg-type]
            H.NameRegistry.parse(plan["basis"], H.BASIS_COLUMNS,     # type: ignore[arg-type]
                                 "basis の欄名の登録表"),
            H.NameRegistry.parse(plan["payload"], H.PAYLOAD_COLUMNS,  # type: ignore[arg-type]
                                 "payload 種別の登録表"))


@settings(max_examples=200, derandomize=True, database=None, deadline=None)
@given(plan=合成の6枚())
def test_いつも成り立つこと_4値か理由コードか(plan: dict[str, object]) -> None:
    six = six_of(plan)
    items, domains, placements, shapes, basis, payload = six
    asof = plan["asof"]
    t = H.off_scope(*six, asof)    # type: ignore[arg-type]

    expect_stop = plan["kowasu"] is not None
    c = t.counts()
    assert c["項目の台帳の行数"] == len(plan["items_rows"])          # type: ignore[arg-type]
    assert c["在り所の台帳の行数"] == len(plan["placements_rows"])   # type: ignore[arg-type]
    assert {x.value for x in t.rows} <= set(H.VALUES + H.BETSUWAKU)
    assert all(isinstance(v, int) for v in t.five().values())
    # **件数の側に「収録すべきか」の欄が無い**(末尾の 10 行だけがその語を持つ)
    for key in (k for k in c if k not in H.MOTANAI):
        for word in ("推奨", "順位", "優先度", "点数", "割合", "カバー率",
                     "収録すべき"):
            assert word not in key

    if expect_stop:
        event(f"(b) 止まった: {plan['kowasu']}")
        assert t.report.ok is False and t.report.pending
        assert {x.reason for x in t.report.pending} <= set(H.TABLE_REASONS)
        assert t.rows == () and t.denominator() == 0
        assert t.five() == {k: 0 for k in H.VALUES}
        assert t.extras() == {k: 0 for k in H.BETSUWAKU}
        assert t.counted_rows()["(B) の行数の合計"] == 0
        assert t.missing_rows()["件数"] == 0
        for call in (t.judgement_bytes, t.sha256):
            with pytest.raises(RuntimeError):
                call()
    else:
        event("(a) 4 値を付けた")
        assert t.report.ok is True
        mine = {r[0]: my_value(r, plan["placements_rows"], plan["shapes_rows"],   # type: ignore[arg-type]
                               plan["domains_rows"], plan["basis_rows"],          # type: ignore[arg-type]
                               plan["payload_rows"])                              # type: ignore[arg-type]
                for r in plan["items_rows"]}                                      # type: ignore[union-attr]
        assert {x.item_id: x.value for x in t.rows} == mine
        total = sum(t.five().values()) + sum(t.extras().values())
        assert total == t.denominator() == len(t.rows)
        assert sum(int(r["項目の件数"]) for r in t.by_stance()) == total
        assert sum(int(r["項目の件数"]) for r in t.by_place()) == total
        for x in t.rows:
            # **領域が `内` と宣言された項目は (A)(B)(C) と (D) 境界 に入らない**
            if x.stance == H.STANCES[0]:
                assert x.value in (H.VALUES[4],) + H.BETSUWAKU
            # **登録表の外の記号は 4 値に入らない**
            if x.stance == H.UNREGISTERED:
                assert x.value in H.BETSUWAKU
            # **0 件と行数を数えない在り所を同じ値にしない**
            if x.place in H.COUNTED:
                assert x.count.isdigit()
            else:
                assert x.count == H.UNCOUNTABLE
            # **必須の欄が空で在り所も `無い` 項目は 4 値に入らない**
            if x.required == H.NO_REQUIRED and x.place in (H.PLACES[4], H.NO_ROW):
                assert x.value in H.BETSUWAKU   # 先に当たる別枠が在れば そちらへ出る
            # (A) は在り所が `無い` か行が無い項目だけ
            if x.value == H.VALUES[0]:
                assert x.place in (H.PLACES[4], H.NO_ROW)
                assert x.required != H.NO_REQUIRED
        # **2 通りの分母が必ず両方出る**
        dens = t.denominators()
        assert dens["項目数"] == len(t.rows)
        assert set(dens["行数(在り所の台帳が数えた行)"]) == set(H.COUNTED)
        body = t.judgement_bytes().decode("utf-8")
        for word in ("読んだ条件", str(ROOT), NAMES[0], REQUIRED[2]):
            assert word not in body
        # **項目名を入れ替えても判定部分は同じバイト列**
        renamed = [list(r) for r in plan["items_rows"]]     # type: ignore[union-attr]
        for r in renamed:
            r[1] = NAMES[1] if r[1] == NAMES[0] else NAMES[0]
        after = H.off_scope(H.Items(renamed), domains, placements, shapes, basis,
                            payload, asof)    # type: ignore[arg-type]
        assert after.judgement_bytes() == t.judgement_bytes()
        # 6 枚の行順を 3 通りに入れ替えても同じバイト列
        for how in H.SWAPS:
            again = H.off_scope(items.swapped(how), domains.swapped(how),
                                placements.swapped(how), shapes.swapped(how),
                                basis.swapped(how), payload.swapped(how),
                                asof)   # type: ignore[arg-type]
            assert again.judgement_bytes() == t.judgement_bytes()
            assert again.sha256() == t.sha256()

    # どちらの場合も入力は 1 文字も書き換わらない
    assert H.Items.parse(plan["items"]).rows == items.rows               # type: ignore[arg-type]
    assert H.Placements.parse(plan["placements"], items.ids).rows == placements.rows   # type: ignore[arg-type]
    assert H.Shapes.parse(plan["shapes"], items.ids).rows == shapes.rows   # type: ignore[arg-type]


@settings(max_examples=300, derandomize=True, database=None)
@given(stance=st.sampled_from(H.STANCES), place=st.sampled_from(H.PLACES),
       payload_kind=st.sampled_from(PAYLOADS), selector=st.sampled_from(SELECTORS),
       name=st.sampled_from(NAMES))
def test_4値を決めるのは領域と在り所と入る形だけ(stance: str, place: str,
                                                payload_kind: str, selector: str,
                                                name: str) -> None:
    """項目名が何であっても、同じ (領域の宣言, 在り所, 入る形) なら同じ 4 値になる。"""
    count = "2" if place in H.COUNTED else "—"
    item = ["I1", name, OUT1, REQUIRED[2], "—", I_SRC]
    domains = [[OUT1, stance, D_SRC]]
    placements = [["I1", place, count, "—" if count == "—" else H.ORIGINS[1], P_SRC]]
    shapes = [["I1", BASIS_OK, payload_kind, selector, "—", S_SRC]]
    buf = io.StringIO()
    _csv.writer(buf, lineterminator="\n").writerows([list(H.ITEM_COLUMNS), item])
    items = H.Items.parse(buf.getvalue())
    t = H.off_scope(items, H.Domains(domains),
                    H.Placements(placements, items.ids),
                    H.Shapes(shapes, items.ids),
                    H.NameRegistry(BASIS_ROWS, H.BASIS_COLUMNS,
                                   "basis の欄名の登録表"),
                    H.NameRegistry(PAYLOAD_ROWS, H.PAYLOAD_COLUMNS,
                                   "payload 種別の登録表"), ASOF)
    assert t.report.ok
    got = t.rows[0].value
    assert got == my_value(item, placements, shapes, domains, BASIS_ROWS,
                           PAYLOAD_ROWS)
    if payload_kind in ("—", "値 1 つ"):
        assert got == H.BETSUWAKU[4]     # 空か、登録表に無い種別
    elif stance == H.STANCES[0]:
        assert got == H.VALUES[4]
    elif place in H.COUNTED:
        assert got == H.VALUES[1]
    elif place in H.DESTINED:
        assert got == H.VALUES[2]
    elif stance == H.STANCES[2] and selector != "—":
        assert got == H.VALUES[3]
    else:
        assert got == H.VALUES[0]
