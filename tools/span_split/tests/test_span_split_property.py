"""span_split の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 切った結果は 2 通りしかない。
  (a) 小期間の日数の合計が元の期間の日数と一致し(切り落ちも重複も 0)、小期間は隙間なく
      連続し、小期間の開始日は元の期間の開始日か境界表に宣言された切れ目の日だけで、
      4 値の合計が期間表の行数に等しく、判定部分に時刻・ホスト名・絶対パスが入らず、
      境界表の行順を入れ替えても同じバイト列になる
  (b) 1 本も結果を返さずに理由コードが返る(結果や指紋を取りに行くと例外になる)
どちらの場合も、この部品は期間表も境界表も行の表も 1 文字も書き換えない。

期間は 1〜3 本、境界は 1〜3 行、行は 1〜3 行を乱数で引き、当日の帰属・段階の順・公表時点と
その扱いも振る。さらに 3 割くらいの確率で 1 か所だけ崩す(出典を空にする / 当日の帰属を空に
する / 境界日を未定にする / 公表時点の扱いを空にする / 境界表を 0 行にする / 開始日と終了日を
入れ替える / 基準日の種別を未登録にする / 同じ日に同じ動いたものを 2 行にする)。
derandomize=True で毎回同じ入力列を使い、database=None で見つけた例を保存しない。

**期待する切れ目は部品の split を呼ばずにテストの側で計算している**(境界日と当日の帰属から
date の足し算で直に出す、別の実装)。
"""
from __future__ import annotations

import datetime
import sys
from pathlib import Path

import pytest
from hypothesis import event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import span_split as S  # noqa: E402

ONE = datetime.timedelta(days=1)
DAY_POOL = ("2024-01-01", "2024-07-01", "2025-01-01", "2025-04-01", "2025-10-01",
            "2026-01-01", "2026-07-01")
VALID_POOL = ("2020-01-01", "2021-01-01", "2022-01-01")
KNOWN_POOL = ("", "2024-03-10", "2026-12-20")
TARGET = "合成の区分A"
SOURCE = "合成の境界メモ(架空)L1"
MOVED = ("合成の改定1(架空)", "合成の改定2(架空)", "合成の改定3(架空)")

KOWASHIKATA = ("出典を空にする", "当日の帰属を空にする", "境界日を未定にする",
               "公表時点の扱いを空にする", "境界表を 0 行にする",
               "開始日と終了日を入れ替える", "基準日の種別を未登録にする",
               "同じ日に同じ動いたものを 2 行にする")


def d(text: str) -> datetime.date:
    return datetime.date.fromisoformat(text)


@st.composite
def 合成の表(draw: st.DrawFn) -> dict[str, object]:
    """期間表 / 境界表 / 行の表(と崩し方)を作る。"""
    spans: list[tuple[str, str, str]] = []
    for pair in draw(st.lists(st.lists(st.sampled_from(DAY_POOL), min_size=2, max_size=2,
                                       unique=True), min_size=1, max_size=3)):
        start, end = sorted(pair)
        spans.append((start, end, draw(st.sampled_from(S.BASIS_KINDS))))

    bounds: list[list[str]] = []
    for i, day in enumerate(draw(st.lists(st.sampled_from(DAY_POOL), min_size=1, max_size=3,
                                          unique=True))):
        known = draw(st.sampled_from(KNOWN_POOL))
        bounds.append([day, MOVED[i], draw(st.sampled_from(S.ONDAYS)),
                       draw(st.sampled_from(("", "1", "2"))), known,
                       draw(st.sampled_from(S.KNOWN_USES)) if known else "", SOURCE,
                       "逆順" if i == 0 else ""])

    rows: list[list[str]] = []
    for i, valid in enumerate(sorted(draw(st.lists(st.sampled_from(VALID_POOL), min_size=1,
                                                   max_size=3, unique=True)))):
        rows.append([f"合成の値{i + 1}(架空)", valid, "", "", str(i), SOURCE])

    kowasu = draw(st.sampled_from([None] * 7 + list(KOWASHIKATA)))
    if kowasu == "出典を空にする":
        bounds[0][6] = ""
    elif kowasu == "当日の帰属を空にする":
        bounds[-1][2] = ""
    elif kowasu == "境界日を未定にする":
        bounds[0][0] = S.MITEI
    elif kowasu == "公表時点の扱いを空にする":
        with_known = [b for b in bounds if b[4]]
        if with_known:
            with_known[0][5] = ""
        else:
            bounds[0][6], kowasu = "", "出典を空にする"
    elif kowasu == "境界表を 0 行にする":
        bounds = []
    elif kowasu == "開始日と終了日を入れ替える":
        s, e, b = spans[0]
        spans[0] = (e, s, b) if s != e else (s, e, b)
        if spans[0][0] <= spans[0][1]:
            bounds[0][6], kowasu = "", "出典を空にする"
    elif kowasu == "基準日の種別を未登録にする":
        spans[0] = (spans[0][0], spans[0][1], "支払日")
    elif kowasu == "同じ日に同じ動いたものを 2 行にする":
        bounds.append(list(bounds[0]))

    kikan_text = "\n".join([",".join(S.KIKAN_COLUMNS)]
                           + [f"{TARGET},{s},{e},{b}" for s, e, b in spans])
    kyoukai_text = "\n".join([",".join(S.KYOUKAI_COLUMNS)] + [",".join(b) for b in bounds])
    gyou_text = "\n".join([",".join(S.GYOU_COLUMNS)] + [",".join(r) for r in rows])
    return {"kikan_text": kikan_text, "kyoukai_text": kyoukai_text, "gyou_text": gyou_text,
            "spans": spans, "bounds": bounds, "rows": rows, "kowasu": kowasu}


def 期待する切れ目(start: str, end: str, bounds: list[list[str]]) -> list[datetime.date]:
    """切れ目の日をテストの側で別に出す(部品の split は呼ばない)。"""
    s, e = d(start), d(end)
    out: set[datetime.date] = set()
    for day, _moved, onday, _step, known, known_use, _src, _swap in bounds:
        if day in ("", S.MITEI) or onday not in S.ONDAYS:
            continue
        if known and d(known) > e and known_use == S.KNOWN_USES[1]:
            continue
        c = d(day) if onday == S.ONDAYS[0] else d(day) + ONE
        if s < c <= e:
            out.add(c)
    return sorted(out)


@settings(max_examples=150, derandomize=True, database=None, deadline=None)
@given(plan=合成の表())
def test_いつも成り立つこと_切った結果か理由コードか(plan: dict[str, object]) -> None:
    kikan_text = plan["kikan_text"]
    kyoukai_text = plan["kyoukai_text"]
    gyou_text = plan["gyou_text"]
    spans = S.Spans.parse(kikan_text)                         # type: ignore[arg-type]
    bounds = S.Boundaries.parse(kyoukai_text)                 # type: ignore[arg-type]
    rows = S.Rows.parse(gyou_text)                            # type: ignore[arg-type]
    m = S.split(spans, bounds, rows)

    expect_stop = plan["kowasu"] is not None
    c = m.counts()
    four = c["4 値"]
    assert c["期間表の行数"] == len(plan["spans"])             # type: ignore[arg-type]
    assert c["境界表の行数"] == len(plan["bounds"])            # type: ignore[arg-type]

    if m.cuts:
        # 4 値の合計は、切った期間の本数に等しい
        assert sum(four.values()) == len(m.cuts)
        for cut in m.cuts:
            if cut.result == S.RESULTS[3]:
                continue                                      # 止まった期間は切っていない
            # 日数の合計と、隙間なく連続していること
            assert cut.total_days == cut.span.days
            for a, b in zip(cut.pieces, cut.pieces[1:]):
                assert a.end + ONE == b.start
            assert cut.pieces[0].start == cut.span.start
            assert cut.pieces[-1].end == cut.span.end
            # 小期間の開始日は、元の期間の開始日か宣言された切れ目の日だけ
            expect = 期待する切れ目(str(cut.span.start), str(cut.span.end),
                                    plan["bounds"])            # type: ignore[arg-type]
            assert [p.start for p in cut.pieces[1:]] == expect

    if expect_stop:
        event("(b) 止まった")
        assert m.report.ok is False
        assert m.report.pending
        assert {p.reason for p in m.report.pending} <= set(S.STOP_REASONS)
        for call in (lambda: m.verdict, m.judgement_bytes, m.sha256):
            with pytest.raises(RuntimeError):
                call()
    else:
        event("(a) 切った")
        assert m.report.ok is True
        assert four[S.RESULTS[2]] == four[S.RESULTS[3]] == 0
        assert c["行が当たった小期間の件数"] == c["小期間の件数"]
        body = m.judgement_bytes().decode("utf-8")
        for word in (m.read_at, m.host, "読んだ時刻", "絶対パス"):
            assert word not in body
        # 境界表の行順を入れ替えても同じバイト列
        again = S.split(spans, bounds.swapped(bounds.swap or "逆順"), rows)
        assert again.sha256() == m.sha256()
        assert again.judgement_bytes() == m.judgement_bytes()

    # どちらの場合も入力は 1 文字も書き換わらない
    assert S.Spans.parse(kikan_text).items == spans.items      # type: ignore[arg-type]
    assert S.Boundaries.parse(kyoukai_text).items == bounds.items   # type: ignore[arg-type]
    assert S.Rows.parse(gyou_text).items == rows.items         # type: ignore[arg-type]


@settings(max_examples=300, derandomize=True, database=None)
@given(pair=st.lists(st.sampled_from(DAY_POOL), min_size=2, max_size=2, unique=True),
       day=st.sampled_from(DAY_POOL), basis=st.sampled_from(S.BASIS_KINDS))
def test_当日の帰属を旧側にすると切れ目が1日後ろへ動く(pair: list[str], day: str,
                                                        basis: str) -> None:
    """境界日が期間の内側にあるかぎり、当日の帰属だけで切れ目が 1 日動く。

    新側 なら境界日が新しい小期間の初日、旧側 なら境界日が古い小期間の最終日になる。
    どちらに寄せるかの既定を部品が持たないので、表の 1 欄だけで結果が変わる。
    """
    start, end = sorted(pair)
    kikan = S.Spans.parse("\n".join([",".join(S.KIKAN_COLUMNS),
                                     f"{TARGET},{start},{end},{basis}"]))
    rows = S.Rows.parse("\n".join([",".join(S.GYOU_COLUMNS),
                                   f"合成の値(架空),2020-01-01,,,0,{SOURCE}"]))

    def cut(onday: str) -> S.Split:
        text = "\n".join([",".join(S.KYOUKAI_COLUMNS),
                          f"{day},{MOVED[0]},{onday},,,,{SOURCE},逆順"])
        return S.split(kikan, S.Boundaries.parse(text), rows)

    new, old = cut(S.ONDAYS[0]), cut(S.ONDAYS[1])
    assert new.report.ok and old.report.ok
    inside = d(start) < d(day) < d(end)
    if inside:
        assert new.verdict == old.verdict == S.RESULTS[0]
        assert len(new.cuts[0].pieces) == len(old.cuts[0].pieces) == 2
        assert old.cuts[0].pieces[0].days == new.cuts[0].pieces[0].days + 1
        assert old.cuts[0].pieces[1].days == new.cuts[0].pieces[1].days - 1
        assert new.sha256() != old.sha256()
    # どちらの寄せ方でも、日数の合計は元の期間と一致する
    for m in (new, old):
        assert m.cuts[0].total_days == m.cuts[0].span.days
