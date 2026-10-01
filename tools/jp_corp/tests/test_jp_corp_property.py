"""jp_corp の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 突合の結果は「照合」か「理由コード付きの判断待ち」の 2 通りしかない。
  照合になるのは、相手側に、法人番号が同じ行か、照合キー(法人格の種類 + 屋号 + 事業所の印)が同じ行が
  ちょうど 1 件あるときだけ。法人格の種類が違う相手と名前で照合されることはなく、
  検査数字が合わない番号を持つ行は、名前が合っても照合にならない。

入力の台帳 2 つは乱数で作る。会社名は先に材料(法人格の種類 / 屋号 / 事業所の名前)を決めてから、
法人格の書き方(株式会社 / (株) / 全角括弧 / ㈱)、置く位置(前・後・中)、全角英字・大文字・半角カナ、
空白と区切りを混ぜて組み立てる。相手側には、左と同じ材料(書き方だけ違う)・法人格だけ違う行・
事業所だけ違う行・同じ材料の 2 件目を混ぜる。困る値として、空の会社名(法人格だけ・区切りだけ)、
壊れた番号(検査数字違い・12 桁・14 桁)、何でもありの文字列(左の台帳だけ)を混ぜる。
derandomize=True で毎回同じ入力列を使う。database=None で見つけた例を保存しない(この版の hypothesis は実行した場所に .hypothesis/ を作るが、git と公開側への export では除外される)。

照合キーと番号の正しさは、このテストの中で別に持つ。キーは会社名を組み立てた材料から作り、
検査数字は README に書いてある算式から書く。jp_corp.parse / to_key / number_reason / check_digit は
判定に使わない。道具自身の正規化や算式が壊れても、このテストで気づけるようにするため。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import NamedTuple, Union

from hypothesis import event, given, settings
from hypothesis import strategies as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import jp_corp as J  # noqa: E402


# ---- 会社名の材料(照合キーの期待値はここから作る) ---------------------------------------------

# 種類 → 書き方。㈱ ㈲ と全角括弧は NFKC で (株) (有) に寄る(README「法人格の表」)
書き方 = {
    "株式会社": ["株式会社", "(株)", "（株）", "㈱"],
    "有限会社": ["有限会社", "(有)", "㈲"],
    "合同会社": ["合同会社"],
    "医療法人": ["医療法人"],
    "医療法人社団": ["医療法人社団"],   # 医療法人 と頭が同じ(長い方が先に当たること)
    "協同組合": ["協同組合"],
    "事業協同組合": ["事業協同組合"],   # 協同組合 と尻が同じ
    "": [""],                          # 法人格なし
}
屋号の元 = ["山田商会", "青葉運輸", "abc", "アイウ"]          # 法人格の表の語を含まない字だけで作る
事業所の名前 = {"": "", "大阪支店": "支店", "本町営業所": "営業所", "北支部": "支部"}   # 名前 → 事業所の印
字の書き方 = {"a": "aAａＡ", "b": "bBｂＢ", "c": "cCｃＣ", "ア": "アｱ", "イ": "イｲ", "ウ": "ウｳ"}
区切り = [" ", "　", "・", "-"]
空の会社名 = ["", "株式会社", "㈱", "(有)　", " ・ ", "-"]   # 法人格だけ / 区切りだけ / 空


class 材料(NamedTuple):
    種類: str
    屋号: str
    事業所: str    # 事業所の名前(大阪支店 など。"" = なし)

    @property
    def キー(self) -> tuple[str, str, str]:
        """照合キーの期待値 = (法人格の種類, 屋号 + 事業所の名前, 事業所の印)。英字は小文字で持っている。"""
        return (self.種類, self.屋号 + self.事業所, 事業所の名前[self.事業所])


空 = "空の会社名"
何でも = "何でもありの文字列"
行の材料 = Union[材料, str]      # 材料 / 空 / 何でも


def 検査数字(下12桁: str) -> int:
    """README の算式: 9 -(下 12 桁を右から数え、奇数番目は 1 倍・偶数番目は 2 倍して合計)を 9 で割った余り。"""
    合計 = 0
    for 番目 in range(1, 13):                 # 右から 1 番目, 2 番目, ...
        合計 += int(下12桁[-番目]) * (1 if 番目 % 2 == 1 else 2)
    return 9 - 合計 % 9


def 番号の状態(番号: str) -> str:
    """'空' / '正' / '壊'。このテストが作る番号は半角数字だけなので、正規化は要らない。"""
    if 番号 == "":
        return "空"
    if len(番号) == 13 and 番号.isdigit() and int(番号[0]) == 検査数字(番号[1:]):
        return "正"
    return "壊"


材料たち = st.builds(材料, 種類=st.sampled_from(list(書き方)), 屋号=st.sampled_from(屋号の元),
                  事業所=st.sampled_from(list(事業所の名前)))


@st.composite
def 会社名(draw: st.DrawFn, m: 材料) -> str:
    """材料から会社名の表記を組み立てる(書き方・位置・字の形・区切りを乱数で変える)。"""
    屋号 = "".join(draw(st.sampled_from(字の書き方.get(ch, ch))) for ch in m.屋号 + m.事業所)
    法人格 = draw(st.sampled_from(書き方[m.種類]))
    位置 = draw(st.sampled_from(["前", "後", "中"]))
    if 位置 == "前":
        s = 法人格 + 屋号
    elif 位置 == "後":
        s = 屋号 + 法人格
    else:
        k = draw(st.integers(1, len(屋号) - 1))
        s = 屋号[:k] + 法人格 + 屋号[k:]
    for _ in range(draw(st.integers(0, 2))):  # 空白と区切りをどこかに挟む
        k = draw(st.integers(0, len(s)))
        s = s[:k] + draw(st.sampled_from(区切り)) + s[k:]
    return s


@st.composite
def 番号の束(draw: st.DrawFn) -> list[str]:
    """左右で共有する番号。先頭 3 つが正しい番号、4 つ目が壊れた番号(検査数字違い / 12 桁 / 14 桁)。"""
    束 = []
    for i in range(4):
        下12桁 = draw(st.from_regex(r"[0-9]{12}", fullmatch=True))
        正 = str(検査数字(下12桁)) + 下12桁
        if i < 3:
            束.append(正)
            continue
        壊し方 = draw(st.sampled_from(["検査数字違い", "12 桁", "14 桁"]))
        if 壊し方 == "検査数字違い":
            束.append(str((int(正[0]) + draw(st.integers(1, 9))) % 10) + 下12桁)
        elif 壊し方 == "12 桁":
            束.append(下12桁)
        else:
            束.append(正 + draw(st.sampled_from("0123456789")))
    return 束


台帳の行 = tuple[J.Row, 行の材料]


@st.composite
def 台帳(draw: st.DrawFn) -> tuple[list[台帳の行], list[台帳の行]]:
    """(左の台帳, 右の台帳)。各行は (Row, 材料 / 空 / 何でも)。"""
    束 = draw(番号の束())
    番号 = st.one_of(st.just(""), st.sampled_from(束))

    left: list[台帳の行] = []
    for _ in range(draw(st.integers(1, 5))):
        which = draw(st.integers(0, 11))
        if which == 0:
            left.append((J.Row(draw(st.sampled_from(空の会社名)), draw(番号)), 空))
        elif which == 1:
            left.append((J.Row(draw(st.text(max_size=10)), draw(番号)), 何でも))
        else:
            m = draw(材料たち)
            left.append((J.Row(draw(会社名(m)), draw(番号)), m))
            if draw(st.integers(0, 11)) == 0:     # 自分側の重複(同じ材料を書き方を変えてもう 1 行)
                left.append((J.Row(draw(会社名(m)), draw(番号)), m))

    right: list[台帳の行] = []
    元 = [(r, m) for r, m in left if isinstance(m, 材料)]
    for _ in range(draw(st.integers(1, 6))):
        how = draw(st.sampled_from(["同じ", "同じ", "同じ", "同じ", "法人格違い", "事業所違い", "新規", "空"]))
        if how == "空":
            right.append((J.Row(draw(st.sampled_from(空の会社名)), draw(番号)), 空))
            continue
        n = draw(番号)
        if how == "新規" or not 元:
            m = draw(材料たち)
        else:
            r0, m = draw(st.sampled_from(元))
            if how == "法人格違い":
                m = m._replace(種類=draw(st.sampled_from([k for k in 書き方 if k != m.種類])))
            elif how == "事業所違い":
                m = m._replace(事業所=draw(st.sampled_from([b for b in 事業所の名前 if b != m.事業所])))
            番号の持たせ方 = draw(st.sampled_from(["左と同じ", "別の正しい番号", "乱数"]))
            if 番号の持たせ方 == "左と同じ":
                n = r0.number
            elif 番号の持たせ方 == "別の正しい番号" and any(b != r0.number for b in 束[:3]):
                n = draw(st.sampled_from([b for b in 束[:3] if b != r0.number]))
        right.append((J.Row(draw(会社名(m)), n), m))
        if draw(st.integers(0, 5)) == 0:          # 相手側の 2 件目(同じ材料、書き方だけ違う)
            right.append((J.Row(draw(会社名(m)), draw(番号)), m))
    return left, right


@settings(max_examples=400, derandomize=True, database=None, deadline=None)
@given(両側=台帳())
def test_いつも成り立つこと_照合は番号かキーがちょうど1件のときだけ(両側: tuple[list[台帳の行], list[台帳の行]]) -> None:
    left, right = 両側
    decisions = J.match_all([r for r, _ in left], [r for r, _ in right])
    assert len(decisions) == len(left)
    event("(例) 照合を含む" if any(d.status == J.OK for d in decisions) else "(例) 全て判断待ち")
    for d, (row, m) in zip(decisions, left):
        assert d.row is row
        assert d.status in (J.OK, J.PENDING)
        if d.status == J.PENDING:
            event(f"判断待ち: {d.reason}")
            assert d.reason in J.REASONS and d.by == ""
            continue
        # ここから照合。相手はちょうど 1 件で、相手側の台帳の行そのもの
        assert d.reason == "" and len(d.candidates) == 1
        相手 = d.candidates[0]
        assert sum(r is 相手 for r, _ in right) == 1
        assert 番号の状態(row.number) != "壊", "検査数字が合わない番号の行が照合になった"
        if d.by == J.BY_NUMBER:
            event("照合(番号)")
            assert 番号の状態(row.number) == "正"
            同じ番号 = [r for r, _ in right if r.number == row.number]
            assert len(同じ番号) == 1 and 同じ番号[0] is 相手, "番号が同じ相手が 1 件に決まっていない"
            continue
        assert d.by == J.BY_NAME
        assert m != 空, "空の会社名が名前で照合になった"
        if m == 何でも:
            event("照合(名前・何でもありの文字列)")
            continue
        event("照合(名前)")
        同じキー = [r for r, rm in right if isinstance(rm, 材料) and rm.キー == m.キー]
        assert len(同じキー) == 1 and 同じキー[0] is 相手, "照合キーが同じ相手が 1 件に決まっていない"
        相手の材料 = next(rm for r, rm in right if r is 相手)
        assert 相手の材料.種類 == m.種類, "法人格の種類が違う相手と名前で照合された"
