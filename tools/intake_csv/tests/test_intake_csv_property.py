"""intake_csv の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 書き出しの結果は 2 通りしかない。
  (a) 取込側に渡るファイルができ、取込側と同じ読み方で読み戻すと、見出し・件数・全セルが元データと一致する
  (b) ファイルはできず、理由(判断待ち または 差)が 1 つ以上返る
どちらの場合も作業ファイル(<出力先>.tmp)は残らない。

入力の表は乱数で作る。書ける値だけの表を作り、半分の確率で 1 か所だけ困る値(値の中のカンマ・改行・
引用符、cp932 に無い文字、全角数字、桁あふれ、空、何でもありの文字列)に差し替える。(a) と (b) の
両方を十分に通すため(差し替えた値が偶然書ける値のこともある)。derandomize=True で毎回同じ入力列を使う
(他のテストと同じく決定論的に再現する)。database=None で見つけた例を保存しない(ただし hypothesis
6.152.8 は実行した場所に .hypothesis/constants/ を作る。中に自前の .gitignore があるので git には載らず、
公開側への export でも除外している)。

読み戻しは intake_csv.read_back / verify を使わず、このテストの中で別に書く。道具自身の照合が
壊れても、このテストで気づけるようにするため。
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
import intake_csv as I  # noqa: E402

SPEC = I.Spec.from_csv(FX / "retsu_shiyou.csv")

# 書ける値(社員番号 = コード 6 桁、金額 = 10 桁、氏名は空を許さない、部署は空を許す)
良い数 = st.from_regex(r"[0-9]{1,6}", fullmatch=True)
書ける字 = list("あいうアイウ山田髙﨑㈱①ｱｲｳABCabc012-・ー")
良い文字 = st.text(alphabet=st.sampled_from(書ける字), min_size=1, max_size=12)
良い行 = st.fixed_dictionaries({
    "社員番号": 良い数, "氏名": 良い文字, "部署": st.one_of(st.just(""), 良い文字),
    "支給合計": 良い数, "控除合計": 良い数, "差引支給額": 良い数,
})

# 困る値(差し替え用)
困る字 = list(',"\n\r—～¬😀𠮷½€✓♬ 　\t')
困る値 = st.one_of(
    st.just(""),
    st.text(alphabet="0123456789０１２-,. a", max_size=12),               # 全角数字・区切り・桁あふれ
    st.text(alphabet=st.sampled_from(書ける字 + 困る字), max_size=12),     # 困る字が混ざった文字列
    st.text(max_size=12),                                                  # 何でもあり
)


@st.composite
def 表(draw: st.DrawFn) -> list[dict[str, str]]:
    rows = draw(st.lists(良い行, max_size=6))
    if rows and draw(st.booleans()):
        i = draw(st.integers(0, len(rows) - 1))
        col = draw(st.sampled_from(SPEC.names))
        rows[i] = {**rows[i], col: draw(困る値)}
    return rows


def 取込側の読み方(path: Path) -> list[list[str]]:
    """cp932 で読み、CRLF で行に、カンマで列に切る(クォートは解釈しない)。intake_csv の関数は使わない。"""
    text = path.read_bytes().decode("cp932")
    assert text.endswith("\r\n")
    return [line.split(",") for line in text.split("\r\n")[:-1]]


@settings(max_examples=300, derandomize=True, database=None, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(rows=表())
def test_いつも成り立つこと_一致するファイルか_ファイル無しか(rows: list[dict[str, str]]) -> None:
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "out.csv"
        r = I.write(out, SPEC, rows)
        if out.exists():
            event("(a) ファイルができた")
            assert r.written and not r.pending and not r.diffs
            got = 取込側の読み方(out)
            assert got[0] == list(SPEC.names)
            want = [[I.render(c, row[c.name]) for c in SPEC.columns] for row in rows]
            assert got[1:] == want
        else:
            event("(b) ファイル無し・理由あり")
            assert not r.written
            assert r.pending or r.diffs
        assert not (Path(d) / "out.csv.tmp").exists()
