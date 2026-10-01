"""jp_name の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 名簿の突合(match_all)で、左の各行の結果は 2 通りしかない。
  (a) 対象外表記でも空でもなく、照合キーが同じ行が右にちょうど 1 件・左に自分だけのときに限り、
      その 1 件を候補にした「照合」
  (b) それ以外は、理由コード(REASONS の 5 つ)を付けた「判断待ち」
照合キー(表記の揺れ・同値表の異体字・ひらがなとカタカナを寄せたもの)が違う相手と照合されることはない。

入力の名簿は乱数で作る。少人数の「人」(漢字・カナ・ローマ字の架空の姓名)を決め、左右の名簿にその人を
README の範囲の揺れ(区切り無し・半角空白・全角空白・中黒(全角・半角)・コンマ・読点、前後の空白、
同値表の異体字、ひらがな・半角カナ、全角英字)で書いて並べる。同じ人が左に 2 回出る・右に 0 件 / 2 件ある、が自然に起きるようにし、5 行に 1 行は
困る値(空・記号だけ、旧姓や通称の併記、3 語)に差し替える。derandomize=True で毎回同じ入力列を使う
(他のテストと同じく決定論的に再現する)。database=None で見つけた例を保存しない(この版の hypothesis は実行した場所に .hypothesis/ を作るが、git と公開側への export では除外される)。

期待値は jp_name の関数(to_key / scope_reason / build_index)を使わず、「どの人をどう書いたか」から別に作る。
同値表も README の表をこのテストに書き写したものを使う。道具自身の正規化や照合が壊れても、このテストで
気づけるようにするため。
"""
from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

from hypothesis import event, given, settings
from hypothesis import strategies as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import jp_name as J  # noqa: E402

# README「同値表」を書き写したもの(jp_name.VARIANT_GROUPS は使わない)。代表字 → 異体字
同値表 = {"辺": "邊邉", "斉": "齊", "斎": "齋", "高": "髙", "崎": "﨑", "沢": "澤", "浜": "濱濵", "島": "嶋嶌",
          "吉": "𠮷", "富": "冨", "徳": "德", "国": "國", "広": "廣", "郎": "郞", "竜": "龍", "真": "眞",
          "恵": "惠", "瀬": "瀨", "柳": "栁", "桧": "檜", "亀": "龜", "増": "增"}
理由コード = {"空の氏名", "対象外表記", "相手なし", "相手が複数", "自分側が重複"}   # README「判断待ちの理由コードは 5 つ」

# 架空の姓名。斉藤 と 斎藤、井ノ口 と 井之口 は README が「畳まない」と書いている組なので、別の人として両方置く
漢字の姓 = ["渡辺", "高橋", "山崎", "吉田", "沢田", "斉藤", "斎藤", "浜田", "島田", "広瀬", "富田", "井ノ口", "井之口",
           "佐藤", "亀井", "柳瀬"]
漢字の名 = ["太郎", "一郎", "恵子", "真一", "竜也", "花子", "徳子", "国広", "増美"]
カナの姓 = ["ワタナベ", "サトウ", "ヤマダ", "イノクチ"]
カナの名 = ["ハナコ", "タロウ", "マリー", "ジュン"]
ローマ字の姓 = ["Yamada", "Sato"]
ローマ字の名 = ["Taro", "Hanako"]
人 = st.one_of(
    st.tuples(st.just("漢字"), st.sampled_from(漢字の姓), st.sampled_from(漢字の名)),
    st.tuples(st.just("カナ"), st.sampled_from(カナの姓), st.sampled_from(カナの名)),
    st.tuples(st.just("ローマ字"), st.sampled_from(ローマ字の姓), st.sampled_from(ローマ字の名)),
)
区切り = ["", " ", "　", "・", "･", ",", "、"]
_半角 = {unicodedata.normalize("NFKC", chr(c)): chr(c) for c in range(0xFF61, 0xFFA0)}


def ひらがな(s: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def 半角カナ(s: str) -> str:
    out = []
    for ch in s:
        d = unicodedata.normalize("NFD", ch)
        if ch in _半角:
            out.append(_半角[ch])
        elif len(d) == 2 and d[0] in _半角 and d[1] in _半角:       # 濁点・半濁点は 2 文字に分ける
            out.append(_半角[d[0]] + _半角[d[1]])
        else:
            out.append(ch)
    return "".join(out)


def 全角英字(s: str) -> str:
    return "".join(chr(ord(c) + 0xFEE0) if "!" <= c <= "~" else c for c in s)


def 照合キー(p: tuple[str, str, str]) -> str:
    """この人の照合キー(README: 代表字・カタカナ・区切り無し)。書き方の揺れに関わらず同じになるはずのもの。"""
    return p[1] + p[2]


@st.composite
def 書く(draw: st.DrawFn, p: tuple[str, str, str]) -> str:
    script, sei, mei = p
    if script == "漢字":
        sei, mei = ("".join(draw(st.sampled_from(c + 同値表.get(c, ""))) for c in w) for w in (sei, mei))
    elif script == "カナ":
        f = draw(st.sampled_from([str, ひらがな, 半角カナ]))
        sei, mei = f(sei), f(mei)
    elif draw(st.booleans()):
        sei, mei = 全角英字(sei), 全角英字(mei)
    sep = draw(st.sampled_from(区切り))
    if script == "ローマ字" and sep == "":
        sep = " "                     # ローマ字は区切りを省くと読めないので、空白で書く
    pad = draw(st.sampled_from(["", " ", "　"]))
    return f"{pad}{sei}{sep}{mei}{pad}"


@st.composite
def 困る行(draw: st.DrawFn, p: tuple[str, str, str]) -> tuple[str, str]:
    """(表記, README の理由コード)。"""
    _, sei, mei = p
    kind = draw(st.sampled_from(["空", "旧姓の併記", "通称の併記", "3 語"]))
    if kind == "空":
        return draw(st.sampled_from(["", " ", "　", "・・", "---", " , "])), "空の氏名"
    other = draw(st.sampled_from(漢字の姓))
    if kind == "旧姓の併記":
        return draw(st.sampled_from([f"{sei}(旧姓 {other}) {mei}", f"{sei}（{other}）{mei}"])), "対象外表記"
    if kind == "通称の併記":
        return f"{sei} {mei} 通称 {draw(st.sampled_from(['タロー', 'ハナ']))}", "対象外表記"
    return f"{sei} {draw(st.sampled_from(['マリア', 'エマ']))} {mei}", "対象外表記"


@st.composite
def 名簿(draw: st.DrawFn):
    """左 = [(表記, 困る行の理由コード or "", 照合キー or None)]、右 = [(表記, 照合キー or None)]。"""
    pool = list(dict.fromkeys(draw(st.lists(人, min_size=1, max_size=4))))
    left = []
    for p in pool:
        for _ in range(draw(st.sampled_from([1, 1, 1, 1, 2]))):      # 5 人に 1 人は左に 2 回(同姓同名)
            if draw(st.integers(0, 4)) == 0:                          # 5 行に 1 行は困る値
                text, reason = draw(困る行(p))
                left.append((text, reason, None))
            else:
                left.append((draw(書く(p)), "", 照合キー(p)))
    right = []
    for p in pool:
        for _ in range(draw(st.sampled_from([0, 1, 1, 1, 1, 2]))):   # 右に 0 件(未登録)/ 2 件(同姓同名)もある
            right.append((draw(書く(p)), 照合キー(p)))
    if draw(st.integers(0, 4)) == 0:
        right.append((draw(困る行(draw(st.sampled_from(pool))))[0], None))
    return draw(st.permutations(left)), draw(st.permutations(right))


@settings(max_examples=500, derandomize=True, database=None, deadline=None)
@given(case=名簿())
def test_いつも成り立つこと_キーが1対1なら照合_それ以外は理由つきの判断待ち(case) -> None:
    left, right = case
    decisions = J.match_all([t for t, _, _ in left], [t for t, _ in right])
    assert len(decisions) == len(left)
    for (text, trouble, key), d in zip(left, decisions):
        assert d.name == text
        if key is None:
            event(f"判断待ち: {trouble}")
            assert (d.status, d.reason) == ("判断待ち", trouble), text
            continue
        mine = sorted(t for t, _, k in left if k == key)
        hits = sorted(t for t, k in right if k == key)
        if len(mine) == 1 and len(hits) == 1:
            event("照合")
            assert (d.status, d.reason, d.candidates) == ("照合", "", (hits[0],)), text
            continue
        want = ({"自分側が重複"} if len(mine) >= 2 else set()) | ({"相手なし"} if not hits else set()) \
            | ({"相手が複数"} if len(hits) >= 2 else set())
        assert d.status == "判断待ち" and d.reason in want, (text, d)
        event(f"判断待ち: {d.reason}")
        assert d.reason in 理由コード
        assert sorted(d.candidates) == {"相手なし": [], "相手が複数": hits, "自分側が重複": mine}[d.reason]
