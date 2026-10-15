"""band_edge の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 引いた結果は 2 通りしかない。
  (a) 値の行ごとに 4 値が 1 つだけ付き、4 値の合計が値の表の行数に等しく、当たった帯は
      宣言された等号で値を含む帯だけで、境界ちょうどの件数が宣言された境界値と一致した行数に
      等しく、判定部分に時刻・ホスト名・絶対パスが入らず、帯の表の行順を入れ替えても
      同じバイト列になる
  (b) 1 行も「帯が 1 つに決まった」を返さずに理由コードが返る(結果や指紋を取りに行くと例外)
どちらの場合も、この部品は値の表も帯の表も単位の宣言も 1 文字も書き換えない。

帯は 1〜3 本(刻みの境目を乱数で引いて隙間なく連ねる)、値は 1〜3 行、等号の向きも振る。
さらに 3 割くらいの確率で 1 か所だけ崩す(等号を空にする / 下限を空にする(開放の宣言が無い)/
出典を空にする / 値の種類を空にする / 隙間を作る / 範囲を重ねる / 下限と上限を逆にする /
帯の番号を重複させる / 単位の宣言に無い項目を書く)。derandomize=True で毎回同じ入力列を使い、
database=None で見つけた例を保存しない。

**当たる帯はテストの側で別に計算している**(部品の holds を呼ばず、宣言された等号から
Decimal の大小比較で直に出す)。
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import band_edge as B  # noqa: E402

ITEM = "合成の項目(架空)"
TARGET = "合成の区分A"
SOURCE = "合成の帯メモ(架空)L1"
CUT_POOL = ("100", "200", "300", "400")
VALUE_POOL = ("0", "50", "100", "150", "200", "250", "300", "350", "400", "450")

KOWASHIKATA = ("等号を空にする", "下限を空にする", "出典を空にする", "値の種類を空にする",
               "隙間を作る", "範囲を重ねる", "下限と上限を逆にする", "帯の番号を重複させる",
               "単位の宣言に無い項目を書く")


@st.composite
def 合成の表(draw: st.DrawFn) -> dict[str, object]:
    """値の表 / 帯の表 / 単位の宣言(と崩し方)を作る。帯は隙間なく連ねる。"""
    cuts = sorted(draw(st.lists(st.sampled_from(CUT_POOL), min_size=1, max_size=3,
                                unique=True)), key=Decimal)
    # 境目ごとに「上側を 以上・未満 で閉じる」か「超・以下 で閉じる」かを振る
    styles = [draw(st.sampled_from(("以上未満", "超以下"))) for _ in cuts]
    bands: list[list[str]] = []
    for i in range(len(cuts) + 1):
        low = B.OPEN if i == 0 else cuts[i - 1]
        high = B.OPEN if i == len(cuts) else cuts[i]
        low_eq = "" if i == 0 else ("以上" if styles[i - 1] == "以上未満" else "超")
        high_eq = "" if i == len(cuts) else ("未満" if styles[i] == "以上未満" else "以下")
        bands.append([ITEM, str(i + 1), low, low_eq, high, high_eq, f"合成の段{i + 1}(架空)",
                      SOURCE, "逆順" if i == 0 else ""])

    values = [[TARGET, ITEM, v, "金額", "円", SOURCE]
              for v in draw(st.lists(st.sampled_from(VALUE_POOL), min_size=1, max_size=3))]
    units = [[ITEM, "金額", "円", "0", "", ""]]

    kowasu = draw(st.sampled_from([None] * 7 + list(KOWASHIKATA)))
    if kowasu == "等号を空にする":
        if len(bands) >= 2:
            bands[1][3] = ""
        else:
            kowasu = None
    elif kowasu == "下限を空にする":
        bands[0][2] = ""
    elif kowasu == "出典を空にする":
        bands[0][7] = ""
    elif kowasu == "値の種類を空にする":
        values[0][3] = ""
    elif kowasu == "隙間を作る":
        if len(bands) >= 2:
            bands[1][2] = str(Decimal(bands[1][2]) + 10)
        else:
            kowasu = None
    elif kowasu == "範囲を重ねる":
        if len(bands) >= 2:
            bands[1][2] = str(Decimal(bands[1][2]) - 10)
        else:
            kowasu = None
    elif kowasu == "下限と上限を逆にする":
        if len(bands) >= 3:
            bands[1][2], bands[1][4] = bands[1][4], bands[1][2]
        else:
            kowasu = None
    elif kowasu == "帯の番号を重複させる":
        if len(bands) >= 2:
            bands[1][1] = bands[0][1]
        else:
            kowasu = None
    elif kowasu == "単位の宣言に無い項目を書く":
        values[0][1] = "合成の未登録(架空)"

    return {"atai": "\n".join([",".join(B.ATAI_COLUMNS)] + [",".join(r) for r in values]),
            "obi": "\n".join([",".join(B.OBI_COLUMNS)] + [",".join(r) for r in bands]),
            "tani": "\n".join([",".join(B.TANI_COLUMNS)] + [",".join(r) for r in units]),
            "bands": bands, "values": values, "kowasu": kowasu}


def 期待する帯(value: Decimal, bands: list[list[str]]) -> list[int]:
    """当たる帯を、宣言された等号から直に比べて出す(部品の holds は呼ばない)。"""
    out: list[int] = []
    for _item, no, low, low_eq, high, high_eq, *_rest in bands:
        ok = True
        if low != B.OPEN:
            ok = ok and (value >= Decimal(low) if low_eq == "以上" else value > Decimal(low))
        if high != B.OPEN:
            ok = ok and (value < Decimal(high) if high_eq == "未満" else value <= Decimal(high))
        if ok:
            out.append(int(no))
    return sorted(out)


@settings(max_examples=150, derandomize=True, database=None, deadline=None)
@given(plan=合成の表())
def test_いつも成り立つこと_引いた結果か理由コードか(plan: dict[str, object]) -> None:
    atai, obi, tani = plan["atai"], plan["obi"], plan["tani"]
    values = B.Values.parse(atai)                              # type: ignore[arg-type]
    bands = B.Bands.parse(obi)                                 # type: ignore[arg-type]
    units = B.Units.parse(tani)                                # type: ignore[arg-type]
    m = B.match(values, bands, units)

    expect_stop = plan["kowasu"] is not None
    c = m.counts()
    four = c["4 値"]
    assert c["値の表の行数"] == len(plan["values"])             # type: ignore[arg-type]
    assert c["帯の表の行数"] == len(plan["bands"])              # type: ignore[arg-type]
    assert sum(four.values()) == len(m.hits)                   # type: ignore[union-attr]
    # 表が揃う前に止まったら 1 行も引かない。引いたなら値の行と 1 対 1 で付く
    assert len(m.hits) in (0, len(plan["values"]))             # type: ignore[arg-type]
    assert {h.result for h in m.hits} <= set(B.RESULTS)

    # 当たった帯は、テスト側で等号から直に比べた結果と一致する
    for h in m.hits:
        if h.result == B.RESULTS[3]:
            continue                                           # 止まった行は引いていない
        assert h.used is not None
        want = 期待する帯(h.used, plan["bands"])                # type: ignore[arg-type]
        assert list(h.bands) == want
        assert h.result == (B.RESULTS[0] if len(want) == 1 else
                            B.RESULTS[1] if not want else B.RESULTS[2])
        # 境界ちょうどは、宣言された境界値との一致だけで決まる
        assert list(h.low_edge) == sorted(int(b[1]) for b in plan["bands"]   # type: ignore
                                          if b[2] != B.OPEN and Decimal(b[2]) == h.used)
        assert list(h.high_edge) == sorted(int(b[1]) for b in plan["bands"]  # type: ignore
                                           if b[4] != B.OPEN and Decimal(b[4]) == h.used)

    if expect_stop:
        event("(b) 止まった")
        assert m.report.ok is False
        assert m.report.pending
        assert {p.reason for p in m.report.pending} <= set(B.STOP_REASONS)
        for call in (lambda: m.verdict, m.judgement_bytes, m.sha256):
            with pytest.raises(RuntimeError):
                call()
    else:
        event("(a) 引いた")
        assert m.report.ok is True
        assert four[B.RESULTS[3]] == 0                         # type: ignore[index]
        edges = c["境界ちょうど"]
        assert edges["下限ちょうど"] == sum(1 for h in m.hits if h.low_edge)   # type: ignore
        assert edges["上限ちょうど"] == sum(1 for h in m.hits if h.high_edge)  # type: ignore
        body = m.judgement_bytes().decode("utf-8")
        for word in (m.read_at, m.host, "読んだ時刻", "絶対パス"):
            assert word not in body
        # 帯の表の行順を入れ替えても同じバイト列
        again = B.match(values, bands.swapped(bands.swap or "逆順"), units)
        assert again.sha256() == m.sha256()
        assert again.judgement_bytes() == m.judgement_bytes()

    # どちらの場合も入力は 1 文字も書き換わらない
    assert B.Values.parse(atai).items == values.items          # type: ignore[arg-type]
    assert B.Bands.parse(obi).items == bands.items             # type: ignore[arg-type]
    assert B.Units.parse(tani).items == units.items            # type: ignore[arg-type]


@settings(max_examples=300, derandomize=True, database=None)
@given(cut=st.sampled_from(CUT_POOL), value=st.sampled_from(VALUE_POOL))
def test_上限の等号を以下にすると境界値ちょうどだけが2つの帯に入る(cut: str,
                                                                  value: str) -> None:
    """境界値ちょうどの行だけが、上限の等号 1 欄で「決まらない(重なり)」に変わる。

    等号の向きは部品が決めず、帯の表の 1 欄が決める。だから同じ値・同じ境界でも、
    その 1 欄を書き換えるだけで答えが 1 つに決まったり決まらなくなったりする。
    """
    tani = "\n".join([",".join(B.TANI_COLUMNS), f"{ITEM},金額,円,0,,"])
    atai = "\n".join([",".join(B.ATAI_COLUMNS), f"{TARGET},{ITEM},{value},金額,円,{SOURCE}"])

    def pull(high_eq: str) -> B.Match:
        obi = "\n".join([
            ",".join(B.OBI_COLUMNS),
            f"{ITEM},1,{B.OPEN},,{cut},{high_eq},合成の段1(架空),{SOURCE},逆順",
            f"{ITEM},2,{cut},以上,{B.OPEN},,合成の段2(架空),{SOURCE},",
        ])
        return B.match(B.Values.parse(atai), B.Bands.parse(obi), B.Units.parse(tani))

    miman, ika = pull("未満"), pull("以下")
    assert miman.report.ok and ika.report.ok
    assert miman.counts()["点の重なり"] == 0 and ika.counts()["点の重なり"] == 1
    on_edge = Decimal(value) == Decimal(cut)
    a, b = miman.hits[0], ika.hits[0]
    assert a.result == B.RESULTS[0]                      # 連結した帯はいつも 1 つに決まる
    if on_edge:
        assert a.bands == (2,) and a.returns == "合成の段2(架空)"
        assert b.result == B.RESULTS[2] and b.bands == (1, 2) and b.returns == ""
        assert miman.sha256() != ika.sha256()
    else:
        assert b.result == B.RESULTS[0] and b.bands == a.bands
        assert b.returns == a.returns
