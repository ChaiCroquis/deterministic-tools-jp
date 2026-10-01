"""wareki の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 既定(strict=True)の和暦 → 西暦の変換(to_date)の結果は 2 通りしかない。
  (a) その元号の開始日から終了日までに入る実在の日なら、その日(元年の西暦 + 年 - 1 の、その月日)が返る
  (b) それ以外(改元後の旧元号・改元前の新元号・太陽暦以前・存在しない日)なら WarekiError で止まる
年の足し算で表の外の日付を黙って通すことはない。

入力は乱数で作る。実在の日(改元の境目の前後 3 日を多めに)を正しい元号で書いたものを主にし、半分の確率で
困る値(改元後の旧元号、改元前の新元号、太陽暦以前の明治、存在しない月日、0 年 = 元年の前の年)に差し替える。書き方は README の
「受け付ける表記」から選ぶ(漢字 / 空白入り / 一字 / 略字 / 小文字とスラッシュ / ゼロ埋めとハイフン / 全角)。
derandomize=True で毎回同じ入力列を使う(他のテストと同じく決定論的に再現する)。database=None で見つけた例を保存しない(この版の hypothesis は実行した場所に .hypothesis/ を作るが、git と公開側への export では除外される)。

期待値は wareki.ERAS を使わず、README の改元表をこのテストに書き写して別に作る。
道具自身の表や照合が壊れても、このテストで気づけるようにするため。
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from typing import NamedTuple

import pytest
from hypothesis import event, given, settings
from hypothesis import strategies as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import wareki as W  # noqa: E402


class 元号(NamedTuple):
    name: str
    letter: str
    first_year: int
    start: date
    end: date | None


# README「改元表」を書き写したもの(wareki.ERAS は使わない)
改元表 = (
    元号("明治", "M", 1868, date(1873, 1, 1), date(1912, 7, 29)),
    元号("大正", "T", 1912, date(1912, 7, 30), date(1926, 12, 24)),
    元号("昭和", "S", 1926, date(1926, 12, 25), date(1989, 1, 7)),
    元号("平成", "H", 1989, date(1989, 1, 8), date(2019, 4, 30)),
    元号("令和", "R", 2019, date(2019, 5, 1), None),
)
太陽暦の採用日 = date(1873, 1, 1)
最後の日 = date(2100, 12, 31)
全角 = str.maketrans("0123456789.MTSHR", "０１２３４５６７８９．ＭＴＳＨＲ")


def 正しい元号(d: date) -> 元号:
    return next(e for e in 改元表 if e.start <= d and (e.end is None or d <= e.end))


def 期待(era: 元号, y: int, m: int, d: int) -> date | str:
    """README の流れ(段 3・4)を wareki を使わずに辿る。date なら返る日、str なら止まる理由(event の名前)。"""
    if y < 1:
        return "0 年"                # 元年の前の年 = 改元前の新元号。理由を分けて数えるためだけに別の名前にする
    try:
        day = date(era.first_year + y - 1, m, d)
    except ValueError:
        return "存在しない日"
    if day < era.start:
        return "太陽暦以前" if day < 太陽暦の採用日 else "改元前の新元号"
    if era.end is not None and day > era.end:
        return "改元後の旧元号"
    return day


def 書く(era: 元号, y: int, m: int, d: int, style: str, gannen: bool) -> str:
    """README の「受け付ける表記」で書く。"""
    if style == "漢字":
        return f"{era.name}{'元' if (y == 1 and gannen) else y}年{m}月{d}日"
    if style == "空白入り":
        return f"{era.name} {y} 年 {m} 月 {d} 日"
    if style == "一字":
        return f"{era.name[0]}{y}.{m}.{d}"
    if style == "略字":
        return f"{era.letter}{y}.{m}.{d}"
    if style == "小文字とスラッシュ":
        return f"{era.letter.lower()}{y}/{m}/{d}"
    if style == "ゼロ埋めとハイフン":
        return f"{era.letter}{y:02d}-{m:02d}-{d:02d}"
    if style == "全角の漢字":
        return 書く(era, y, m, d, "漢字", gannen).translate(全角)
    return 書く(era, y, m, d, "略字", gannen).translate(全角)        # 全角の略字


書き方 = ["漢字", "空白入り", "一字", "略字", "小文字とスラッシュ", "ゼロ埋めとハイフン", "全角の漢字", "全角の略字"]
困る種類 = ["改元後の旧元号", "改元前の新元号", "太陽暦以前", "存在しない月日", "0 年"]


@st.composite
def 和暦(draw: st.DrawFn) -> tuple[元号, int, int, int]:
    """(元号, 年, 月, 日)。"""
    if draw(st.booleans()):
        # 書ける正しい値: 実在の日を正しい元号で書く。半分は改元の境目の前後 3 日
        if draw(st.booleans()):
            e = draw(st.sampled_from(改元表))
            base = draw(st.sampled_from([e.start] + ([e.end] if e.end else [])))
            day = max(base + timedelta(days=draw(st.integers(-3, 3))), 太陽暦の採用日)
        else:
            day = date.fromordinal(draw(st.integers(太陽暦の採用日.toordinal(), 最後の日.toordinal())))
        e = 正しい元号(day)
        return e, day.year - e.first_year + 1, day.month, day.day
    kind = draw(st.sampled_from(困る種類))
    i = draw(st.integers(0, len(改元表) - 1))
    if kind == "改元後の旧元号":
        e = 改元表[min(i, len(改元表) - 2)]
        day = e.end + timedelta(days=draw(st.integers(1, 400)))
    elif kind == "改元前の新元号":
        e = 改元表[max(i, 1)]
        day = e.start - timedelta(days=draw(st.integers(1, 400)))
    elif kind == "太陽暦以前":
        e = 改元表[0]
        day = date.fromordinal(draw(st.integers(date(1868, 1, 1).toordinal(), 太陽暦の採用日.toordinal() - 1)))
    else:
        e = 改元表[i]
        last = (e.end.year - e.first_year + 1) if e.end else 30
        y = 0 if kind == "0 年" else draw(st.integers(1, last))
        m, d = draw(st.sampled_from([(2, 30), (2, 31), (4, 31), (6, 31), (13, 1), (0, 1), (1, 0), (1, 32),
                                     (2, 29), (1, 1), (5, 1), (12, 31)]))
        return e, y, m, d
    return e, day.year - e.first_year + 1, day.month, day.day


@settings(max_examples=800, derandomize=True, database=None, deadline=None)
@given(w=和暦(), style=st.sampled_from(書き方), gannen=st.booleans())
def test_いつも成り立つこと_表の中の日か_止まるか(w: tuple[元号, int, int, int], style: str, gannen: bool) -> None:
    era, y, m, d = w
    text = 書く(era, y, m, d, style, gannen)
    want = 期待(era, y, m, d)
    if isinstance(want, date):
        event("(a) 日付が返る")
        assert W.to_date(text) == want, text
    else:
        event(f"(b) 止まる: {want}")
        with pytest.raises(W.WarekiError):
            W.to_date(text)
