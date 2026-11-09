"""asof_reach の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文を検査にする。

いつも成り立つこと: 読んだ範囲は 2 通りしかない。
  (a) 4 値を付けた: **行 1 件ごとに 4 値か行に付く別枠 6 のどれか 1 つ**が付き、
      **その合計 = 行の件数**、**品質の意味ごとの内訳の合計も同じ数**になる。
      **品質が `実値` でない行は (A) に入らず**、**境界日が同じ日の行は (A) と (C) に
      入らず**、**知識時間の経路が無い行は (A)(B)(C) に入らず**、**`開` と記載なしを
      同じ値にせず**、**値の名前は判定に入らない**(名前を入れ替えても判定部分は同じ
      バイト列)。4 枚の行順を 3 通りに入れ替えても同じバイト列になる。**問いの分母は
      行とは別**で、行の台帳に無い行 id を指す問いは 3 値に入らない
  (b) 1 行も数えずに理由コードが返る(4 値や sha256 を取りに行くと例外)
どちらの場合も、この部品は 4 枚の表を 1 文字も書き換えない。

行を 1〜3 件、問いを行ごとに 0〜2 件引く。3 回に 1 回くらいどこか 1 か所を崩す(崩し方は
8 通りで、どれが引かれるかは hypothesis が決めるので、8 通りすべてが毎回出るとは限らない。
**8 個の理由コード全部に道が在ることは、崩した表を直に通す
test_measure_eight_stop_reasons_all_reachable の側で決定論的に確かめている**)。
derandomize=True で毎回同じ 200 通りを使い、database=None で例を保存しない。

**4 値の決め方はテストの側で別に実装している**(部品の judge / four / extras を呼ばない)。
2 本目は「4 値を決めるのは品質の意味と境界日の形だけ」を総当たりで見る。
"""
from __future__ import annotations

import csv as _csv
import datetime as _dt
import io
import sys
from pathlib import Path

import pytest
from hypothesis import event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import asof_reach as H  # noqa: E402

R_SRC = "合成の行のメモ(架空)L1"
G_SRC = "合成の品質の登録のメモ(架空)L1"
Q_SRC = "合成の問いのメモ(架空)L1"
C_SRC = "合成の宣言のメモ(架空)L1"

REAL, BY_VALID, BY_HEAD, BY_PROM, UNSURE = (f"記号 {i}" for i in range(1, 6))
UNKNOWN_GRADE = "記号 9"
NAMES = ("合成の値 A(架空)", "合成の値 B(架空)")
REASONS = (H.NO_MARK, "", "合成の理由(架空)")
DATES = ("2026-01-01", "2026-03-01", "2026-04-01")
ENDS = (H.OPEN, H.NO_MARK, "2027-01-01")
KNOWNS = DATES + (H.NO_MARK, "")
ANNOUNCED = (H.NO_MARK, "", "2026-02-01")

GRADE_ROWS = [[REAL, H.MEANS[0], H.REQUIRES[0], G_SRC],
              [BY_VALID, H.MEANS[1], H.REQUIRES[1], G_SRC],
              [BY_HEAD, H.MEANS[2], H.REQUIRES[1], G_SRC],
              [BY_PROM, H.MEANS[3], H.REQUIRES[1], G_SRC],
              [UNSURE, H.MEANS[4], H.REQUIRES[2], G_SRC]]
CLAIM_ROWS = [["C01", "合成の宣言の文(架空)", H.SCOPES[2], C_SRC]]

KOWASHIKATA = ("品質の登録の出典を空にする", "行 id を重複させる",
               "品質の登録の意味を決めた外にする",
               "品質の登録の要求する欄を決めた外にする",
               "行の日付を ISO でない文字にする", "宣言の範囲を決めた外にする",
               "問いの as_of を空にする", "品質の登録表を空にする")


def _date(s: str):
    if s in (H.NO_MARK, "", H.OPEN):
        return None
    try:
        return _dt.date.fromisoformat(s)
    except ValueError:
        return None


def my_value(row: list[str], grades: list[list[str]],
             rows: list[list[str]]) -> str:
    """行 1 件の 4 値 / 別枠をテストの側で出す(部品の judge を呼ばない)。"""
    rid, name, vf, vt, kf, kt, grade, announced, reason, source = row
    reg = {r[0]: (r[1], r[2]) for r in grades}
    means, requires = reg.get(grade, (H.UNREGISTERED, H.NO_MARK))

    if not source:
        return H.BETSUWAKU[0]
    if grade not in reg:
        return H.BETSUWAKU[1]
    if requires == H.REQUIRES[1] and reason in (H.NO_MARK, ""):
        return H.BETSUWAKU[2]
    k, v = _date(kf), _date(vf)
    if k is not None and v is not None and k > v and means in H.KARIOKI:
        return H.BETSUWAKU[3]
    if means == H.MEANS[0] and announced in (H.NO_MARK, ""):
        return H.BETSUWAKU[4]
    end = _date(kt)
    if end is not None:
        later = [r for r in rows if r[0] != rid and r[1] == name
                 and _date(r[4]) is not None and _date(r[4]) >= end]
        if not later:
            return H.BETSUWAKU[5]
    if kf in (H.NO_MARK, "") or kt in (H.NO_MARK, "") or means == H.MEANS[4]:
        return H.VALUES[3]
    if k == v:
        return H.VALUES[1]
    if means == H.MEANS[0]:
        return H.VALUES[0]
    return H.VALUES[2]


@st.composite
def 合成の4枚(draw: st.DrawFn) -> dict[str, object]:
    """行 / 問い の 2 枚と登録表 2 枚(と崩し方)を作る。"""
    rows: list[list[str]] = []
    asks: list[list[str]] = []
    for k in range(1, draw(st.integers(1, 3)) + 1):
        rid = f"R{k}"
        rows.append([rid, draw(st.sampled_from(NAMES)),
                     draw(st.sampled_from(DATES)), draw(st.sampled_from(ENDS)),
                     draw(st.sampled_from(KNOWNS)), draw(st.sampled_from(ENDS)),
                     draw(st.sampled_from((REAL, BY_VALID, BY_HEAD, BY_PROM,
                                           UNSURE, UNKNOWN_GRADE))),
                     draw(st.sampled_from(ANNOUNCED)),
                     draw(st.sampled_from(REASONS)),
                     draw(st.sampled_from((R_SRC, R_SRC, R_SRC, "")))])
        for j in range(draw(st.integers(0, 2))):
            asks.append([f"Q{k}{j}",
                         draw(st.sampled_from((rid, rid, rid, "R99"))),
                         draw(st.sampled_from(DATES)),
                         draw(st.sampled_from(DATES)), Q_SRC])
    # 期間の端が逆の行は「表として読めない」側(ここでは作らない)
    for r in rows:
        if _date(r[3]) is not None and _date(r[3]) < _date(r[2]):
            r[3] = H.OPEN
    grades = [list(x) for x in GRADE_ROWS]
    claims = [list(x) for x in CLAIM_ROWS]

    # 3 回に 1 回くらい崩す。崩す側は 8 通りを平らに引く(負の数は「崩さない」)
    pick = draw(st.sampled_from(tuple(range(-16, len(KOWASHIKATA)))))
    kowasu = KOWASHIKATA[pick] if pick >= 0 else None
    if kowasu == KOWASHIKATA[0]:
        grades[0][3] = ""
    elif kowasu == KOWASHIKATA[1]:
        rows.append([rows[0][0], NAMES[0], DATES[0], H.OPEN, DATES[0], H.OPEN,
                     BY_VALID, H.NO_MARK, REASONS[2], R_SRC])
    elif kowasu == KOWASHIKATA[2]:
        grades[1][1] = "たぶん仮置き"
    elif kowasu == KOWASHIKATA[3]:
        grades[1][2] = "たぶん理由"
    elif kowasu == KOWASHIKATA[4]:
        rows[0][4] = "2026年2月1日"
    elif kowasu == KOWASHIKATA[5]:
        claims[0][2] = "たぶん全行"
    elif kowasu == KOWASHIKATA[6]:
        if asks:
            asks[0][2] = ""
        else:
            kowasu = None
    elif kowasu == KOWASHIKATA[7]:
        grades = []

    def tbl(head: tuple[str, ...], body: list[list[str]]) -> str:
        buf = io.StringIO()
        _csv.writer(buf, lineterminator="\n").writerows([list(head)] + body)
        return buf.getvalue()

    return {"rows": tbl(H.ROW_COLUMNS, rows),
            "grades": tbl(H.GRADE_COLUMNS, grades),
            "asks": tbl(H.ASK_COLUMNS, asks),
            "claims": tbl(H.CLAIM_COLUMNS, claims),
            "rows_rows": rows, "grades_rows": grades, "asks_rows": asks,
            "claims_rows": claims, "kowasu": kowasu}


def four_of(plan: dict[str, object]):
    return (H.Rows.parse(plan["rows"]),           # type: ignore[arg-type]
            H.Grades.parse(plan["grades"]),       # type: ignore[arg-type]
            H.Asks.parse(plan["asks"]),           # type: ignore[arg-type]
            H.Claims.parse(plan["claims"]))       # type: ignore[arg-type]


@settings(max_examples=200, derandomize=True, database=None, deadline=None)
@given(plan=合成の4枚())
def test_いつも成り立つこと_4値か理由コードか(plan: dict[str, object]) -> None:
    four = four_of(plan)
    rows, grades, asks, claims = four
    t = H.asof_reach(*four)

    expect_stop = plan["kowasu"] is not None
    c = t.counts()
    assert c["行の台帳の行数"] == len(plan["rows_rows"])     # type: ignore[arg-type]
    assert c["問いの台帳の行数"] == len(plan["asks_rows"])   # type: ignore[arg-type]
    assert {x.value for x in t.graded} <= set(H.VALUES + H.ROW_BETSUWAKU)
    assert all(isinstance(v, int) for v in t.four().values())
    # **件数の側に「正しい側」や率の欄が無い**(末尾の 10 行だけがその語を持つ)
    for key in (k for k in c if k not in H.MOTANAI):
        for word in ("推奨", "順位", "優先度", "点数", "率", "正しい側", "誤り"):
            assert word not in key

    if expect_stop:
        event(f"(b) 止まった: {plan['kowasu']}")
        assert t.report.ok is False and t.report.pending
        assert {x.reason for x in t.report.pending} <= set(H.TABLE_REASONS)
        assert t.graded == () and t.reaches == () and t.denominator() == 0
        assert t.four() == {k: 0 for k in H.VALUES}
        assert t.extras() == {k: 0 for k in H.ROW_BETSUWAKU}
        assert t.two_ways()["分母(知識時間の経路が在る行)"] == 0
        assert t.boundary_days()["日数が出た行"] == 0
        for call in (t.judgement_bytes, t.sha256):
            with pytest.raises(RuntimeError):
                call()
    else:
        event("(a) 4 値を付けた")
        assert t.report.ok is True
        mine = {r[0]: my_value(r, plan["grades_rows"],      # type: ignore[arg-type]
                               plan["rows_rows"])            # type: ignore[arg-type]
                for r in plan["rows_rows"]}                  # type: ignore[union-attr]
        assert {x.row_id: x.value for x in t.graded} == mine
        total = sum(t.four().values()) + sum(t.extras().values())
        assert total == t.denominator() == len(t.graded)
        assert sum(int(r["行の件数"]) for r in t.by_grade()) == total
        for x in t.graded:
            # **品質が `実値` でない行は (A) に入らない**
            if x.value == H.VALUES[0]:
                assert x.means == H.MEANS[0] and x.same_day == H.OTHER_DAY
                assert not H.blank(x.announced)
            # **境界日が同じ日の行は (A) と (C) に入らない**(どちらも別の日が要る)
            if x.same_day == H.SAME_DAY:
                assert x.value not in (H.VALUES[0], H.VALUES[2])
            # **(B) には `見分け不能` の印が付く**(ほかの値には付かない)
            assert (x.mark == H.MARK_UNKNOWN) == (x.value == H.VALUES[1])
            # **知識時間の経路が無い行は (A)(B)(C) に入らない**
            raw = rows.of(x.row_id)
            if not raw.has_known_path:
                assert x.value not in H.VALUES[:3]
            # **`開` と記載なしを同じ値にしない**(両端が書かれ品質が決まれば (D) でない)
            if raw.has_known_path and x.means != H.MEANS[4]:
                assert x.value != H.VALUES[3]
            # 日数は整数の文字列か `数えられない`
            assert x.days == H.UNCOUNTABLE or int(x.days) == int(x.days)
        # **2 通りの数え方の差は (C) − (B) のうち実値**
        two = t.two_ways()
        assert int(two["差"]) == t.four()[H.VALUES[2]] - t.real_same_day()
        assert two["分母(知識時間の経路が在る行)"] == sum(
            t.four()[k] for k in H.VALUES[:3])
        # **問いの分母は行とは別**で、台帳に無い行 id を指す問いは 3 値に入らない
        reach = t.reach_counts()
        assert reach["問いの件数"] == len(plan["asks_rows"])   # type: ignore[arg-type]
        assert sum(reach["3 値"].values()) == reach["道が付いた問い"]
        assert reach["道が付いた問い"] == len(t.reaches)
        assert all(x.row_id in rows.ids for x in t.reaches)
        body = t.judgement_bytes().decode("utf-8")
        for word in ("読んだ条件", str(ROOT), NAMES[0], REASONS[2]):
            assert word not in body
        # **値の名前を入れ替えても判定部分は同じバイト列**
        renamed = [list(r) for r in plan["rows_rows"]]    # type: ignore[union-attr]
        for r in renamed:
            r[1] = NAMES[1] if r[1] == NAMES[0] else NAMES[0]
        after = H.asof_reach(H.Rows(renamed), grades, asks, claims)
        assert after.judgement_bytes() == t.judgement_bytes()
        # 4 枚の行順を 3 通りに入れ替えても同じバイト列
        for how in H.SWAPS:
            again = H.asof_reach(rows.swapped(how), grades.swapped(how),
                                 asks.swapped(how), claims.swapped(how))
            assert again.judgement_bytes() == t.judgement_bytes()
            assert again.sha256() == t.sha256()

    # どちらの場合も入力は 1 文字も書き換わらない
    assert H.Rows.parse(plan["rows"]).rows == rows.rows       # type: ignore[arg-type]
    assert H.Asks.parse(plan["asks"]).rows == asks.rows       # type: ignore[arg-type]
    assert H.Grades.parse(plan["grades"]).rows == grades.rows  # type: ignore[arg-type]


@settings(max_examples=300, derandomize=True, database=None)
@given(grade=st.sampled_from((REAL, BY_VALID, BY_HEAD, BY_PROM, UNSURE)),
       known_from=st.sampled_from(KNOWNS), known_to=st.sampled_from(ENDS),
       name=st.sampled_from(NAMES))
def test_4値を決めるのは品質の意味と境界日の形だけ(grade: str, known_from: str,
                                                   known_to: str,
                                                   name: str) -> None:
    """値の名前が何であっても、同じ (品質の意味, 境界日, 経路の有無) なら同じ 4 値になる。"""
    row = ["R1", name, DATES[1], H.OPEN, known_from, known_to, grade,
           ANNOUNCED[2], REASONS[2], R_SRC]
    buf = io.StringIO()
    _csv.writer(buf, lineterminator="\n").writerows([list(H.ROW_COLUMNS), row])
    rows = H.Rows.parse(buf.getvalue())
    t = H.asof_reach(rows, H.Grades(GRADE_ROWS), H.Asks([]),
                     H.Claims([list(x) for x in CLAIM_ROWS]))
    assert t.report.ok
    got = t.graded[0].value
    assert got == my_value(row, GRADE_ROWS, [row])
    means = {r[0]: r[1] for r in GRADE_ROWS}[grade]
    k, v = _date(known_from), _date(DATES[1])
    # 当たる順は部品と同じ(遡及の別枠 → 閉じているのに後続行が無い → (D) → (B)(A)(C))
    if k is not None and k > v and means in H.KARIOKI:
        assert got == H.BETSUWAKU[3]      # 遡及の形なのに仮置き
    elif _date(known_to) is not None:
        assert got == H.BETSUWAKU[5]      # 閉じているのに後続行が無い
    elif H.blank(known_from) or H.blank(known_to) or means == H.MEANS[4]:
        assert got == H.VALUES[3]
    elif k == v:
        assert got == H.VALUES[1]
    elif means == H.MEANS[0]:
        assert got == H.VALUES[0]
    else:
        assert got == H.VALUES[2]
