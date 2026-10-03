"""tally_gate の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 結果は 2 通りしかない。
  (a) 3 つの検査(人ごと / 項目ごと / 総計)が全部一致し、次の工程へ渡す行が返る
  (b) 行は返らず、理由コードか「どの軸で見えたか」の分類と差の一覧が返る
どちらの場合も、この部品からファイルは 1 つも開かれない(書き出しを持たない)。

入力の表は乱数で作る。まず人ごとの差引と集計行を**このテストの中の計算**でそろえた表を作り、半分の
確率で 1 か所だけ壊す(金額を変える / 読めない値にする / 空欄にする / 丸めの名前を消す / 人を 2 行に
する / 集計行を消す / 集計行の値を変える / 宣言表に無い列を足す)。(a) と (b) の両方を十分に通すため。
derandomize=True で毎回同じ入力列を使い、database=None で見つけた例を保存しない。

足し直しは tally_gate の関数を使わず、このテストの中で別に書く(丸めも別に書く)。道具自身の集計が
壊れても、このテストで気づけるようにするため。
"""
from __future__ import annotations

import sys
import tempfile
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from pathlib import Path

from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import tally_gate as TG  # noqa: E402

ID = "識別子"
TOTAL = "合計"
IDENTITY = "支給 - 控除 = 差引"
PLUS = ["支給1", "支給2", "支給3"]
MINUS = ["控除1", "控除2"]
NET = "差引1"
ITEMS = [*PLUS, *MINUS, NET]
SIGN = {**{n: "+" for n in PLUS}, "控除1": "+", "控除2": "-", NET: "+"}
GROUP = {**{n: "支給" for n in PLUS}, "控除1": "控除", "控除2": "控除", NET: "差引"}
NAMES = ["50銭以下切捨て", "1円未満切捨て", "円未満四捨五入", "丸めない"]


# -- 丸めと足し算を、このテストの中で別に書く ------------------------------------

def 丸める(x: Decimal, name: str) -> Decimal:
    if name == "50銭以下切捨て":
        i = x.to_integral_value(rounding=ROUND_FLOOR)
        return i if x - i <= Decimal("0.5") else i + 1
    if name == "1円未満切捨て":
        return x.to_integral_value(rounding=ROUND_FLOOR)
    if name == "円未満四捨五入":
        return x.to_integral_value(rounding=ROUND_HALF_UP)
    return x


def 数(cell: str) -> Decimal:
    s = str(cell or "").strip().replace(",", "")
    return Decimal(s) if s else Decimal(0)


def 左辺(cells: dict, rounding: dict) -> Decimal:
    plus = sum((丸める(数(cells[n]), rounding[n]) for n in PLUS), Decimal(0))
    minus = (丸める(数(cells["控除1"]), rounding["控除1"])
             - 丸める(数(cells["控除2"]), rounding["控除2"]))
    return plus - minus


# -- 入力 ------------------------------------------------------------------------

金額 = st.one_of(
    st.just(""),
    st.integers(0, 400000).map(str),
    st.integers(0, 40000000).map(lambda n: format(Decimal(n) / 100, "f")),
)
読めない値 = st.sampled_from(["８２９８", "1000円", "-", "1 000", "いくらか", "1.2.3"])


@st.composite
def 表(draw: st.DrawFn) -> dict:
    rounding = {n: draw(st.sampled_from(NAMES)) for n in [*PLUS, *MINUS]}
    rounding[NET] = "丸めない"      # 差引は印字されたままを使う(そろえた表が必ず通る形にする)
    people = []
    for i in range(draw(st.integers(1, 4))):
        cells = {n: draw(金額) for n in [*PLUS, *MINUS]}
        cells[NET] = format(左辺(cells, rounding), "f")
        people.append({ID: f"P{i + 1}", **cells})
    total = {ID: TOTAL}
    for n in ITEMS:
        total[n] = format(sum((丸める(数(r[n]), rounding[n]) for r in people), Decimal(0)), "f")
    rows = [*people, total]
    items = list(ITEMS)
    if draw(st.booleans()):         # 半分の確率で 1 か所だけ壊す
        kind = draw(st.sampled_from(["値を変える", "読めない値", "空欄", "丸めの名前を消す",
                                     "人を 2 行にする", "集計行を消す", "集計行の値を変える",
                                     "宣言表に無い列"]))
        event(kind)
        i = draw(st.integers(0, len(people) - 1))
        col = draw(st.sampled_from(ITEMS))
        if kind == "値を変える":
            rows[i][col] = draw(st.integers(0, 400000).map(str))
        elif kind == "読めない値":
            rows[i][col] = draw(読めない値)
        elif kind == "空欄":
            rows[i][col] = ""
        elif kind == "丸めの名前を消す":
            rounding[col] = ""
        elif kind == "人を 2 行にする":
            rows.insert(i, dict(rows[i]))
        elif kind == "集計行を消す":
            rows = rows[:-1]
        elif kind == "集計行の値を変える":
            rows[-1][col] = draw(st.integers(0, 400000).map(str))
        else:
            items = [*ITEMS, "宣言表に無い列"]
            rows = [{**r, "宣言表に無い列": "1"} for r in rows]
    else:
        event("そろえた表")
    spec = [{"item": n, "group": GROUP[n], "sign": SIGN[n], "rounding": rounding[n],
             "source": "合成(架空)"} for n in ITEMS]
    return {"rows": rows, "items": items, "spec": spec, "rounding": rounding}


@settings(max_examples=300, derandomize=True, database=None, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(t=表())
def test_いつも成り立つこと_渡す行が返るか_分類と差が返るか(t: dict) -> None:
    with tempfile.TemporaryDirectory() as d:
        table = TG.Table.of(ID, t["items"], t["rows"])
        gate = TG.check(table, TG.Spec.of(t["spec"]), TG.Declaration.of(IDENTITY, ID, TOTAL))
        r = gate.report
        if r.ok:
            event("(a) 渡す行が返った")
            assert r.visibility == "all_agree" and r.diffs == () and r.pending == ()
            rows = gate.handoff()
            people = [x for x in t["rows"] if x[ID] != TOTAL]
            assert len(rows) == len(people)
            assert all(x[ID] != TOTAL for x in rows)
            # 3 つの合計を、このテストの中で別に足し直す
            for got, want in zip(rows, people):
                assert 左辺(got, t["rounding"]) == 数(want[NET])
            for n in ITEMS:
                column = sum((丸める(数(x[n]), t["rounding"][n]) for x in rows), Decimal(0))
                assert column == 丸める(数(dict((x[ID], x) for x in t["rows"])[TOTAL][n]),
                                        t["rounding"][n])
            assert (sum((左辺(x, t["rounding"]) for x in rows), Decimal(0))
                    == 左辺(dict((x[ID], x) for x in t["rows"])[TOTAL], t["rounding"]))
        else:
            event("(b) 行は返らず分類と差が返った")
            assert r.pending or r.diffs
            assert r.visibility != "all_agree"
            if r.pending:
                assert r.visibility == TG.NOT_CHECKED
                assert all(p.reason in TG.REASONS for p in r.pending)
            else:
                assert r.visibility in TG.VISIBILITY.values() and r.axes
            try:
                gate.handoff()
                raise AssertionError("検査に通っていないのに行が返った")
            except TG.GateError:
                pass
        assert list(Path(d).iterdir()) == []      # この部品からファイルは開かれない
