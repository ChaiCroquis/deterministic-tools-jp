"""jp_charset の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: どんなバイト列を渡しても、結果は 2 通りしかない。
  (a) 判定の順番(BOM → NUL → utf-8 → cp932)で最初に strict に通る文字コードの名前と、
      その文字コードで strict に読んだ本文(BOM は除く)が返る
  (b) UndecodableError で止まる
置換文字で読み進めた本文が返ることはない。

入力のバイト列は乱数で作る。書ける本文(かな・漢字・機種依存文字・半角カナ・英数・カンマ・改行)を
utf-8 / BOM 付き utf-8 / BOM 付き utf-16(LE・BE)/ cp932 のどれかで書いたものを主にし、半分の確率で
困るバイト列(空、末尾を 1 バイト欠いたもの、途中に NUL を挟んだもの、BOM 無し utf-16、2 つの書き方の連結、
何でもありのバイト列)に差し替える。derandomize=True で毎回同じ入力列を使う(他のテストと同じく決定論的に
再現する)。database=None で見つけた例を保存しない(この版の hypothesis は実行した場所に .hypothesis/ を作るが、git と公開側への export では除外される)。

期待値は jp_charset の関数を使わず、このテストの中で別に作る(標準ライブラリの codecs で段ごとに復号を試す)。
道具自身の判定が壊れても、このテストで気づけるようにするため。
"""
from __future__ import annotations

import codecs
import sys
from pathlib import Path

import pytest
from hypothesis import event, given, settings
from hypothesis import strategies as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import jp_charset as jc  # noqa: E402

# 書ける本文(cp932 にも utf-8 にも書ける字だけ。㈱ ① 髙 﨑 は NEC / IBM の拡張、ｱ ｲ ｳ ﾃ は半角カナ)
書ける字 = list("あいうアイウ山田髙﨑㈱①ｱｲｳﾃABCabc012,-・ー \r\n")
本文 = st.text(alphabet=st.sampled_from(書ける字), min_size=1, max_size=16)
書き方 = {
    "utf-8": lambda t: t.encode("utf-8"),
    "utf-8-sig": lambda t: b"\xef\xbb\xbf" + t.encode("utf-8"),
    "utf-16 LE": lambda t: b"\xff\xfe" + t.encode("utf-16-le"),
    "utf-16 BE": lambda t: b"\xfe\xff" + t.encode("utf-16-be"),
    "cp932": lambda t: t.encode("cp932"),
}
困る種類 = ["空", "末尾を欠く", "NUL を挟む", "BOM 無し utf-16", "2 つの書き方の連結", "何でもあり"]


@st.composite
def バイト列(draw: st.DrawFn) -> tuple[bytes, tuple[str, str] | None]:
    """(バイト列, 由来)。由来は書ける本文をそのまま書いたときだけ (書き方, 本文)、困るバイト列なら None。"""
    text = draw(本文)
    how = draw(st.sampled_from(sorted(書き方)))
    data = 書き方[how](text)
    if draw(st.booleans()):
        return data, (how, text)
    kind = draw(st.sampled_from(困る種類))
    if kind == "空":
        return b"", None
    if kind == "末尾を欠く":
        return data[:-1], None
    if kind == "NUL を挟む":
        i = draw(st.integers(0, len(data)))
        return data[:i] + b"\x00" + data[i:], None
    if kind == "BOM 無し utf-16":
        return text.encode(draw(st.sampled_from(["utf-16-le", "utf-16-be"]))), None
    if kind == "2 つの書き方の連結":
        return data + 書き方[draw(st.sampled_from(sorted(書き方)))](draw(本文)), None
    return draw(st.binary(max_size=24)), None


def 期待(data: bytes) -> tuple[str, str] | None:
    """README の判定の順番を、jp_charset を使わずに codecs で辿る。None は「止まる」。"""
    if data == b"":
        return ("utf-8", "")
    bom = {b"\xef\xbb\xbf": ("utf-8-sig", "utf-8"), b"\xff\xfe": ("utf-16", "utf-16-le"),
           b"\xfe\xff": ("utf-16", "utf-16-be")}
    for mark, (name, codec) in bom.items():
        if data.startswith(mark):
            try:
                return (name, codecs.decode(data[len(mark):], codec, "strict"))
            except UnicodeDecodeError:
                return None          # BOM は事実なので、ここで読めなければ次の段には進まない
    if 0 in data:
        return None
    for name in ("utf-8", "cp932"):
        try:
            return (name, codecs.decode(data, name, "strict"))
        except UnicodeDecodeError:
            continue
    return None


@settings(max_examples=600, derandomize=True, database=None, deadline=None)
@given(case=バイト列())
def test_いつも成り立つこと_最初に通る文字コードと本文か_止まるか(case: tuple[bytes, tuple[str, str] | None]) -> None:
    data, origin = case
    want = 期待(data)
    if want is None:
        event("(b) 止まる")
        with pytest.raises(jc.UndecodableError):
            jc.detect(data)
        return
    event(f"(a) 返る: {want[0]}")
    got = jc.detect(data)
    assert (got.encoding, got.text) == want
    if origin is not None:
        how, text = origin
        if how == "cp932" and got.encoding == "utf-8":
            # cp932 で書いたバイト列が utf-8 としても strict に通るとき(README「できないこと」)は順番どおり utf-8
            event("(a) cp932 で書いたが utf-8 としても通る")
        else:
            assert got.text == text      # 書いた本文が、そのまま戻る
