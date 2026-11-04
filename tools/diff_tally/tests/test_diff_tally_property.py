"""diff_tally の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 読んだ範囲は 2 通りしかない。
  (a) 回の対 1 つごとに 6 値のどれか 1 つが付き、**6 値の合計 = 回の件数 - 1**、
      **結果記号ごとの内訳の合計 = 回の件数**で、**「差分が 0 で指紋も前の回と同じ」の対は
      差分の 3 欄が 0 かつ指紋が前の回と同一**、**「差分は 0 なのに指紋が前の回と違う」の対は
      差分の 3 欄が 0 かつ指紋が前の回と別**、**「差分は 0 でないのに指紋が前の回と同じ」の対は
      その逆**、**戻りの印が付く対は指紋が前の回と違い、かつ過去のどれかの回と同じ文字列**、
      **累積は `増やす` / `減らす` と宣言された欄だけで決まり、`動かさない` と宣言された欄を
      1 件増やしても動かない**、**出力に「正しい経路」「一致率」の欄が無く**、判定部分に
      絶対パスが入らず、5 枚の行順を 3 通りに入れ替えても同じバイト列になる
  (b) 1 対も数えずに理由コードが返る(作った対や sha256 を取りに行くと例外)
どちらの場合も、この部品は 5 枚の表を 1 文字も書き換えない。

回を 2〜5 件、差分の 3 欄をそれぞれ 4 通り(0 / 1 / 12 / `記載なし`)、指紋を 4 通り(20 文字の
合成文字列 3 つ + `記載なし`)、結果記号を 2 通り(累積に入れる / 入れない)、棚卸しを 1〜2 件、
差の理由の宣言を 0〜2 件(実在する run id の対)から引く。4 回に 1 回くらいどこか 1 か所を
崩す(8 通りで、1 対も数えずに止まる理由コード 8 個すべてに道が付く)。derandomize=True で
毎回同じ入力列を使い、database=None で例を保存しない。

**6 値の分け方はテストの側で別に実装している**(部品の judge / six を呼ばない)。
2 本目は「差分の 3 欄が 0 かと、指紋が前の回と同じかの 2 つだけが ①②③④ を分ける」ことを
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
import diff_tally as H  # noqa: E402

LOG = "合成の実行履歴のメモ(架空)L1"
STOCK = "合成の収録範囲のメモ(架空)L1"
WORD = "合成の登録のメモ(架空)L1"
REASON = "合成の理由のメモ(架空)L1"

NONE = H.NONE_MARK
S_OK, S_OUT, UNREG = "S1", "S2", "合成の未登録の結果記号"
FP1, FP2, FP3 = "p1" + "0" * 18, "p2" + "0" * 18, "p3" + "0" * 18
SHORT_FP = "p4000"
MISSING_RUN = "R99"

FIELDS_ROWS = [[H.DIFF_FIELDS[0], H.MOVES[0], H.FIELD_UNITS[0], WORD],
               [H.DIFF_FIELDS[1], H.MOVES[1], H.FIELD_UNITS[0], WORD],
               [H.DIFF_FIELDS[2], H.MOVES[2], H.FIELD_UNITS[0], WORD]]
STATUSES_ROWS = [[S_OK, H.REPLACES[0], H.CUMULATIVE[0], WORD],
                 [S_OUT, H.REPLACES[1], H.CUMULATIVE[1], WORD]]

TALLIES = ("0", "1", "12", NONE)
PRINTS = (FP1, FP2, FP3, NONE)

KOWASHIKATA = ("出典を空にする", "欄の登録を 1 つ落とす", "登録表に無い結果記号を使う",
               "順序番号を重複させる", "件数を整数でない文字にする",
               "指紋の長さを変える", "棚卸しの時点記号を重複させる",
               "理由の宣言を実在しない run id に向ける")


def classify(runs: list[list[str]]) -> list[tuple[str, str, list[str]]]:
    """対ごとの (対の名前, 6 値, 戻りの印) をテストの側で別に出す(部品を呼ばない)。"""
    rows = sorted(runs, key=lambda r: (int(r[1]), r[0]))
    out: list[tuple[str, str, list[str]]] = []
    for i in range(1, len(rows)):
        before, after = rows[i - 1], rows[i]
        name = f"{before[0]}>{after[0]}"
        back: list[str] = []
        if NONE in after[3:6]:
            hit = H.MUTSU[4]
        elif after[6] == NONE or before[6] == NONE:
            hit = H.MUTSU[5]
        else:
            zero = all(v == "0" for v in after[3:6])
            same = after[6] == before[6]
            hit = H.MUTSU[0] if (zero and same) else (
                H.MUTSU[1] if zero else (H.MUTSU[2] if same else H.MUTSU[3]))
            if not same:
                back = sorted(r[0] for r in rows[:i - 1]
                              if r[6] != NONE and r[6] == after[6])
        out.append((name, hit, back))
    return out


@st.composite
def 合成の5枚(draw: st.DrawFn) -> dict[str, object]:
    """実行の記録の台帳 / 棚卸しの台帳 / 差の理由の宣言表(と崩し方)を作る。

    欄の登録表と結果記号の登録表は固定(崩し方のときだけ触る)。
    """
    n = draw(st.integers(2, 5))
    runs: list[list[str]] = []
    for k in range(1, n + 1):
        runs.append([f"R{k:02d}", str(k),
                     draw(st.sampled_from((S_OK, S_OK, S_OUT))),
                     draw(st.sampled_from(TALLIES)),
                     draw(st.sampled_from(TALLIES)),
                     draw(st.sampled_from(TALLIES)),
                     draw(st.sampled_from(PRINTS)), LOG])
    run_ids = [r[0] for r in runs]

    stocks = [["A1", str(draw(st.integers(0, 30))), str(draw(st.integers(0, 9))),
               STOCK]]
    if draw(st.booleans()):
        stocks.append(["A2", str(draw(st.integers(0, 30))),
                       str(draw(st.integers(0, 9))), STOCK])

    reasons: list[list[str]] = []
    for pair in draw(st.lists(st.tuples(st.sampled_from(run_ids),
                                        st.sampled_from(run_ids)),
                              max_size=2, unique=True)):
        reasons.append([pair[0], pair[1], "合成の理由コード", REASON])

    fields = [list(r) for r in FIELDS_ROWS]
    statuses = [list(r) for r in STATUSES_ROWS]

    kowasu = draw(st.sampled_from([None] * 24 + list(KOWASHIKATA)))
    if kowasu == KOWASHIKATA[0]:
        runs[0][7] = ""
    elif kowasu == KOWASHIKATA[1]:
        fields.pop()
    elif kowasu == KOWASHIKATA[2]:
        runs[0][2] = UNREG
    elif kowasu == KOWASHIKATA[3]:
        runs[1][1] = runs[0][1]
    elif kowasu == KOWASHIKATA[4]:
        runs[0][3] = "合成の読めない件数"
    elif kowasu == KOWASHIKATA[5]:
        runs[0][6] = SHORT_FP
        runs[-1][6] = FP1
    elif kowasu == KOWASHIKATA[6]:
        stocks.append(["A1", "1", "1", STOCK])
    elif kowasu == KOWASHIKATA[7]:
        reasons.append([run_ids[0], MISSING_RUN, "合成の理由コード", REASON])

    def csv(head: tuple[str, ...], body: list[list[str]]) -> str:
        buf = io.StringIO()
        _csv.writer(buf, lineterminator="\n").writerows([list(head)] + body)
        return buf.getvalue()

    return {"runs": csv(H.RUN_COLUMNS, runs),
            "stocks": csv(H.STOCK_COLUMNS, stocks),
            "fields": csv(H.FIELD_COLUMNS, fields),
            "statuses": csv(H.STATUS_COLUMNS, statuses),
            "reasons": csv(H.REASON_COLUMNS, reasons),
            "runs_rows": runs, "stocks_rows": stocks, "reasons_rows": reasons,
            "kowasu": kowasu}


@settings(max_examples=200, derandomize=True, database=None, deadline=None)
@given(plan=合成の5枚())
def test_いつも成り立つこと_作った対か理由コードか(plan: dict[str, object]) -> None:
    runs = H.Runs.parse(plan["runs"])            # type: ignore[arg-type]
    stocks = H.Stocks.parse(plan["stocks"])      # type: ignore[arg-type]
    fields = H.Fields.parse(plan["fields"])      # type: ignore[arg-type]
    statuses = H.Statuses.parse(plan["statuses"])  # type: ignore[arg-type]
    reasons = H.Reasons.parse(plan["reasons"])   # type: ignore[arg-type]
    t = H.diff_tally(runs, stocks, fields, statuses, reasons)

    expect_stop = plan["kowasu"] is not None
    c = t.counts()
    six = c["6 値"]
    assert c["実行の記録の台帳の行数"] == len(plan["runs_rows"])    # type: ignore[arg-type]
    assert c["棚卸しの台帳の行数"] == len(plan["stocks_rows"])      # type: ignore[arg-type]
    assert c["差の理由の宣言表の行数"] == len(plan["reasons_rows"])  # type: ignore[arg-type]
    assert {p.value for p in t.pairs} <= set(H.MUTSU)
    assert all(isinstance(v, int) for v in six.values())   # type: ignore[union-attr]
    # **出力に「正しい経路」「一致率」の欄が無い**
    for key in c:
        if "正しい" in key or "一致率" in key:
            assert key == "正しい経路を決めない"

    if expect_stop:
        event("(b) 1 対も数えずに止まった")
        assert t.report.ok is False and t.report.pending
        assert {p.reason for p in t.report.pending} <= set(H.TABLE_REASONS)
        assert t.pairs == ()
        assert six == {k: 0 for k in H.MUTSU}
        assert t.pair_denominator() == 0
        assert t.backs() == [] and t.split_pairs() == [] and t.missing_side() == []
        for call in (t.judgement_bytes, t.sha256):
            with pytest.raises(RuntimeError):
                call()
    else:
        event("(a) 対を作った")
        assert t.report.ok is True
        # 対ごとに 6 値のどれか 1 つ。テスト側の別実装と一致する
        mine = [(p.name, p.value, list(p.back_to)) for p in t.pairs]
        assert mine == classify(plan["runs_rows"])   # type: ignore[arg-type]
        # 2 通りの数え方が合う
        assert sum(six.values()) == t.pair_denominator()
        assert t.pair_denominator() == t.run_denominator() - 1
        assert (sum(int(r["回の数"]) for r in t.by_status())
                == t.run_denominator() == len(plan["runs_rows"]))  # type: ignore[arg-type]
        for p in t.pairs:
            zero = p.after.zero_tally
            same = (not p.after.missing_fingerprint
                    and not p.before.missing_fingerprint
                    and p.after.fingerprint == p.before.fingerprint)
            if p.value == H.MUTSU[0]:
                assert zero and same and p.gap == "2 経路が同じ答え"
            if p.value == H.MUTSU[1]:
                assert zero and not same and p.gap == "2 経路が別の答え"
            if p.value == H.MUTSU[2]:
                assert not zero and same and p.gap == "2 経路が別の答え"
            if p.value == H.MUTSU[3]:
                assert not zero and not same and p.gap == "2 経路が同じ答え"
            if p.value == H.MUTSU[4]:
                # 差分の欄が `記載なし` なら、指紋が在っても 0 と読まずにここで終わる
                assert p.after.missing_tally and not p.after.zero_tally
                assert p.gap == "片方の欄が " + NONE
            if p.value == H.MUTSU[5]:
                assert not p.after.missing_tally
                assert p.after.missing_fingerprint or p.before.missing_fingerprint
            if p.back_to:       # 戻りの印は前の回と違い、過去のどれかの回と同じ
                assert not same and not p.after.missing_fingerprint
                assert p.value in (H.MUTSU[1], H.MUTSU[3])
            if p.reason == H.NOT_DECLARED:
                assert (p.before.run_id, p.after.run_id) not in {
                    (r[0], r[1]) for r in plan["reasons_rows"]}  # type: ignore[arg-type]
        # **累積は宣言された欄だけで決まり、`動かさない` の欄を増やしても動かない**
        cum = t.cumulative()
        assert cum["足した欄"] == [H.DIFF_FIELDS[0]]
        assert cum["引いた欄"] == [H.DIFF_FIELDS[1]]
        assert cum["累積に入る経路が無い欄"] == [H.DIFF_FIELDS[2]]
        counted = set(statuses.counted())
        hand = sum((r.value(H.DIFF_FIELDS[0]) or 0) - (r.value(H.DIFF_FIELDS[1]) or 0)
                   for r in runs.ordered if r.status in counted)
        assert cum["累積(増やす欄の和 - 減らす欄の和)"] == hand
        assert cum["差(棚卸しの宣言 - 累積)"] == cum["棚卸しが宣言している行数"] - hand
        assert cum["突合"] == (H.MATCH if cum["差(棚卸しの宣言 - 累積)"] == 0
                               else H.DIFFER)
        target = next((r.run_id for r in runs.ordered
                       if r.status in counted
                       and r.value(H.DIFF_FIELDS[2]) is not None), None)
        if target is not None:
            bumped = H.diff_tally(runs.bumped(target, H.DIFF_FIELDS[2]), stocks,
                                  fields, statuses, reasons)
            assert (bumped.cumulative()["累積(増やす欄の和 - 減らす欄の和)"]
                    == cum["累積(増やす欄の和 - 減らす欄の和)"])
        body = t.judgement_bytes().decode("utf-8")
        for word in ("読んだ条件", "絶対パス", str(ROOT)):
            assert word not in body
        # 5 枚の行順を 3 通りに入れ替えても同じバイト列
        for how in H.SWAPS:
            again = H.diff_tally(runs.swapped(how), stocks.swapped(how),
                                 fields.swapped(how), statuses.swapped(how),
                                 reasons.swapped(how))
            assert again.judgement_bytes() == t.judgement_bytes()
            assert again.sha256() == t.sha256()

    # どちらの場合も入力は 1 文字も書き換わらない
    assert H.Runs.parse(plan["runs"]).items == runs.items        # type: ignore[arg-type]
    assert H.Stocks.parse(plan["stocks"]).items == stocks.items  # type: ignore[arg-type]
    assert H.Reasons.parse(plan["reasons"]).items == reasons.items  # type: ignore[arg-type]


@settings(max_examples=300, derandomize=True, database=None)
@given(added=st.sampled_from(("0", "1", "12")),
       removed=st.sampled_from(("0", "1")),
       changed=st.sampled_from(("0", "1")),
       same=st.booleans())
def test_差分の0と指紋の一致だけが4値を分ける(added: str, removed: str, changed: str,
                                              same: bool) -> None:
    """差分の 3 欄が 0 かと、指紋が前の回と同じかの 2 つだけが ①②③④ を分ける。

    **中身が替わった行数が 1 件でも在れば「差分が 0」ではない**(行の数は動かないが、
    差分の記録の側は動いたと言っている)。
    """
    rows = [[",".join(H.RUN_COLUMNS)],
            [f"R01,1,{S_OK},0,0,0,{FP1},{LOG}"],
            [f"R02,2,{S_OK},{added},{removed},{changed},"
             f"{FP1 if same else FP2},{LOG}"]]
    runs = H.Runs.parse("\n".join(r[0] for r in rows))
    t = H.diff_tally(runs, H.Stocks.parse("\n".join(
        [",".join(H.STOCK_COLUMNS), f"A1,0,0,{STOCK}"])),
        H.Fields.parse("\n".join([",".join(H.FIELD_COLUMNS)]
                                 + [",".join(r) for r in FIELDS_ROWS])),
        H.Statuses.parse("\n".join([",".join(H.STATUS_COLUMNS)]
                                   + [",".join(r) for r in STATUSES_ROWS])),
        H.Reasons.parse(",".join(H.REASON_COLUMNS)))
    assert t.report.ok, [p.as_dict() for p in t.report.pending]
    p = t.pairs[0]
    zero = added == "0" and removed == "0" and changed == "0"
    want = H.MUTSU[0] if (zero and same) else (
        H.MUTSU[1] if zero else (H.MUTSU[2] if same else H.MUTSU[3]))
    assert p.value == want
    assert p.after.zero_tally is zero
    assert (p.after.fingerprint == p.before.fingerprint) is same
    # 累積は added - removed だけで決まる(changed は入らない)
    assert (t.cumulative()["累積(増やす欄の和 - 減らす欄の和)"]
            == int(added) - int(removed))
    assert sum(t.six().values()) == 1 == t.pair_denominator()
    assert p.back_to == ()
