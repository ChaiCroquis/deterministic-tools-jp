"""reader_registry の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 読み取りの結果は 2 通りしかない。
  (a) 宣言どおりに読めた行が返る(核の列が宣言ぶんそろい、required の列が全部埋まっている)
  (b) 行は返らず、理由コードが返る
どちらの場合も、この部品からファイルは 1 つも開かれない(書き出しを持たない)。

入力は乱数で作る。まず宣言どおりの形の表(行がレコード / 列がレコードの両方)を作り、9 通りから 1 つ引いて
1 か所だけ壊す(「壊さない」も同じ確率で引く。宣言した形で読めない値にする / 空欄にする / 見出しを 1 つ別の語にする / 列数を変える /
value_form を消す / 同じ係を 2 行にする / 同じ match の係をもう 1 つ足す / match の語を表に無い語にする)。
(a) と (b) の両方を十分に通すため。derandomize=True で毎回同じ入力列を使い、database=None で
見つけた例を保存しない。

読み替えは reader_registry の関数を使わず、このテストの中で別に書く(文字列 / 整数 / 60 進の時間)。
道具自身の読み替えが壊れても、このテストで気づけるようにするため。
"""
from __future__ import annotations

import sys
import tempfile
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import reader_registry as RR  # noqa: E402

CORE = ("核1", "核2", "核3")
ORIGIN = {"核1": "見出し1", "核2": "見出し2", "核3": "見出し3"}
FORM = {"核1": "文字列", "核2": "整数", "核3": "60進の時間"}
REQUIRED = ("核1", "核2")
HEADERS = ("見出し1", "見出し3")
EXTRA = "その他"            # 宣言表に無い見出し(捨てずに台帳へ)


# -- 読み替えを、このテストの中で別に書く ----------------------------------------

def 読む(value: str, form: str) -> str:
    s = str(value).strip()
    if s == "":
        return ""
    if form == "文字列":
        return s
    if form == "整数":
        return str(int(s.replace(",", "")))
    h, m = s.split(":")
    return format((Decimal(h) + Decimal(m) / Decimal(60)).quantize(Decimal("0.01"),
                                                                   rounding=ROUND_HALF_UP), "f")


# -- 入力 ------------------------------------------------------------------------

良い識別子 = st.text(alphabet=st.sampled_from(list("あいうABC012-")), min_size=1, max_size=6)
良い数 = st.integers(0, 999999).map(str)
良い時間 = st.tuples(st.integers(0, 23), st.integers(0, 59)).map(lambda t: f"{t[0]}:{t[1]:02d}")
読めない値 = st.sampled_from(["7時間30分", "１２３", "1000円", "7.5", "7:60", "-", "いくらか"])

壊し方 = st.sampled_from(["壊さない", "読めない値", "空欄", "見出しを別の語に", "列数を変える",
                          "value_form を消す", "同じ係を 2 行に", "同じ match の係を足す",
                          "match の語を表に無い語に"])


@st.composite
def 入力(draw: st.DrawFn) -> dict:
    orientation = draw(st.sampled_from(RR.ORIENTATIONS))
    extra = draw(st.booleans())
    axis = [*(ORIGIN[c] for c in CORE), *([EXTRA] if extra else [])]
    records = []
    for _ in range(draw(st.integers(1, 4))):
        rec = {ORIGIN["核1"]: draw(良い識別子), ORIGIN["核2"]: draw(良い数),
               ORIGIN["核3"]: draw(良い時間)}
        if extra:
            rec[EXTRA] = draw(st.one_of(st.just(""), 良い識別子))
        records.append(rec)
    forms = dict(FORM)
    reader = {"reader_id": "係", "match": {"headers": list(HEADERS), "columns": len(axis)},
              "orientation": orientation,
              "column_map": {c: ORIGIN[c] for c in CORE}, "value_form": forms,
              "required": list(REQUIRED), "source": "合成(架空)"}
    readers = [reader]

    kind = draw(壊し方)                 # 1 か所だけ壊す(「壊さない」も同じ確率で引く)
    event(kind)
    if kind != "壊さない":
        i = draw(st.integers(0, len(records) - 1))
        col = draw(st.sampled_from(CORE))
        if kind == "読めない値":
            records[i][ORIGIN[col]] = draw(読めない値)
        elif kind == "空欄":
            records[i][ORIGIN[col]] = ""
        elif kind == "見出しを別の語に":
            axis[axis.index(ORIGIN[col])] = "別の語"
        elif kind == "列数を変える":
            records[i]["はみ出し"] = "1"
        elif kind == "value_form を消す":
            forms[col] = ""
        elif kind == "同じ係を 2 行に":
            readers = [reader, dict(reader)]
        elif kind == "同じ match の係を足す":
            readers = [reader, {**reader, "reader_id": "別の係"}]
        else:
            reader["match"] = {"headers": ["表に無い語"], "columns": len(axis)}

    # 表を組む(行がレコード / 列がレコード)
    if orientation == RR.ROWS_ARE_RECORDS:
        rows = [list(axis)]
        for rec in records:
            row = [rec.get(w, "") for w in axis]
            if "はみ出し" in rec:
                row.append(rec["はみ出し"])
            rows.append(row)
    else:
        rows = []
        for w in axis:
            row = [w, *[rec.get(w, "") for rec in records]]
            rows.append(row)
        for n, rec in enumerate(records):
            if "はみ出し" in rec:
                rows[0].append(rec["はみ出し"])
                break
    return {"rows": rows, "readers": readers, "axis": axis, "records": records,
            "orientation": orientation, "forms": forms}


@settings(max_examples=300, derandomize=True, database=None, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(t=入力())
def test_いつも成り立つこと_読めた行が返るか_理由コードが返るか(t: dict) -> None:
    with tempfile.TemporaryDirectory() as d:
        reading = RR.read(RR.Sheet.of(t["rows"]), RR.Registry.of(t["readers"]))
        r = reading.report
        if r.ok:
            event("(a) 読めた行が返った")
            assert r.stage == RR.DONE and r.pending == ()
            rows = reading.rows()
            # 期待するレコードを、このテストの中で別に数え直す
            if t["orientation"] == RR.ROWS_ARE_RECORDS:
                want = [rec for rec in t["records"]
                        if any(str(rec.get(w, "")).strip() for w in t["axis"])]
            else:
                want = list(t["records"])
            assert len(rows) == len(want)
            for got, rec in zip(rows, want):
                assert tuple(got) == CORE
                for c in CORE:
                    assert got[c] == 読む(rec[ORIGIN[c]], t["forms"][c])
                for c in REQUIRED:
                    assert got[c] != ""
            led = reading.ledger()
            assert [u["origin"] for u in led["unmapped"]] == [w for w in t["axis"]
                                                              if w not in ORIGIN.values()]
            assert led["records"] == len(rows) and led["sha256"] == ""
        else:
            event("(b) 行は返らず理由コードが返った")
            assert r.pending and all(p.reason in RR.REASONS for p in r.pending)
            assert r.stage in (RR.DECLARATION, RR.SELECTION, RR.CONVERSION)
            for call in (reading.rows, reading.ledger):
                try:
                    call()
                    raise AssertionError("読み替えが通っていないのに返ってきた")
                except RR.ReadError:
                    pass
        assert list(Path(d).iterdir()) == []      # この部品からファイルは開かれない
