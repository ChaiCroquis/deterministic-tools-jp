"""wareki — 和暦の日付文字列を、改元の日を境界とする 1 つの表で西暦 date に直す変換器。

正規表現の寄せ集めで和暦を読むと、改元をまたぐ日付(平成 31 年 5 月 1 日、昭和 64 年 1 月 8 日)が
「年に offset を足すだけ」で黙って通る。この道具は元号ごとの開始日と終了日を 1 つの表(ERAS)に持ち、
表の外の日付は例外で止まる。逆変換(西暦 → 和暦)も同じ表から引く。改元日当日は新元号。

流れ(固定。変えない):
  1. 表記の正規化   NFKC(全角 → 半角)/ 空白除去 / 元年 → 1 年 / 区切り(年月日 . / -)を統一
  2. 元号の解決     漢字(令和)/ 一字(令)/ 略字(R)→ 表の行。解決できなければ止まる
  3. date を作る    存在しない日(2 月 30 日)は止まる
  4. 改元表で照合   開始日 <= date <= 終了日 でなければ止まる(strict=False で終了日側の超過だけ許す)

対象は明治 6 年 1 月 1 日(1873-01-01、太陽暦の採用日)以降。それより前は暦が違うので変換しない(止まる)。
stdlib のみ(datetime / re / unicodedata)。関数(to_date / parse_date / to_wareki)と CLI の両方。
CLI: python wareki.py 令和6年4月1日 R6.4.1     → 1 行 1 件で ISO 日付を出力(exit 0)
     python wareki.py --reverse 2024-04-01      → 令和6年4月1日
     python wareki.py -                         → 標準入力の各行を変換(入力 TAB 結果)。1 件でも止まれば exit 3
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from datetime import date
from typing import NamedTuple

__all__ = ["ERAS", "GREGORIAN_START", "Era", "WarekiError", "to_date", "parse_date", "to_wareki", "main"]


class Era(NamedTuple):
    name: str          # 漢字(令和)
    letter: str        # 略字(R)
    first_year: int    # 元年の西暦
    start: date        # この元号の初日(改元日当日は新元号)
    end: date | None   # 最終日(None = 現在も続く)


# 改元表。これが唯一の正本。開始日・終了日の両方を持つので「表の外」が機械で決まる。
ERAS: tuple[Era, ...] = (
    Era("明治", "M", 1868, date(1873, 1, 1), date(1912, 7, 29)),   # 開始は太陽暦の採用日(明治 6 年 1 月 1 日)
    Era("大正", "T", 1912, date(1912, 7, 30), date(1926, 12, 24)),
    Era("昭和", "S", 1926, date(1926, 12, 25), date(1989, 1, 7)),
    Era("平成", "H", 1989, date(1989, 1, 8), date(2019, 4, 30)),
    Era("令和", "R", 2019, date(2019, 5, 1), None),
)
GREGORIAN_START = ERAS[0].start

_BY_KEY: dict[str, Era] = {}
for _e in ERAS:
    _BY_KEY[_e.name] = _e
    _BY_KEY[_e.name[0]] = _e
    _BY_KEY[_e.letter] = _e

_ERA_ALT = "|".join([e.name for e in ERAS] + [e.name[0] for e in ERAS] + [e.letter for e in ERAS])
_SEP = r"[年月.\-/]"
_WAREKI = re.compile(rf"^({_ERA_ALT})(元|\d{{1,2}}){_SEP}(\d{{1,2}}){_SEP}(\d{{1,2}})日?$")
_SEIREKI = re.compile(rf"^(\d{{4}}){_SEP}(\d{{1,2}}){_SEP}(\d{{1,2}})日?$")


class WarekiError(ValueError):
    """解釈できない表記 / 存在しない日 / 改元表の外(改元後の旧元号・改元前の新元号・太陽暦以前)。"""


def normalize(s: str) -> str:
    """NFKC で全角を半角に寄せ、空白を除く。「令和６年４月１日」「Ｒ６．４．１」を同じ形にする。"""
    if not isinstance(s, str):
        raise TypeError("文字列を渡す")
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", "", s)
    return s.upper() if s[:1].isascii() else s


def _check_range(era: Era, d: date, text: str, strict: bool) -> date:
    if d < era.start:
        if d < GREGORIAN_START:
            raise WarekiError(f"{text}: 太陽暦の採用(明治6年1月1日)より前。この道具は変換しない")
        raise WarekiError(f"{text}: {era.name}の開始日 {era.start.isoformat()} より前(改元前の日付に新元号)")
    if era.end is not None and d > era.end:
        if strict:
            raise WarekiError(f"{text}: {era.name}は {era.end.isoformat()} で終わっている(改元後の日付に旧元号)。"
                              f"strict=False なら {to_wareki(d)} と読み替える")
    return d


def to_date(text: str, *, strict: bool = True) -> date:
    """和暦の日付文字列を西暦 date に直す。表の外なら WarekiError。

    受け付ける表記: 令和6年4月1日 / 令和 6 年 4 月 1 日 / 令6.4.1 / R6.4.1 / R06/04/01 / Ｒ６－４－１ / 令和元年5月1日
    strict=False は「終了日を過ぎた旧元号」(平成 31 年 5 月 1 日、平成 32 年)だけを年の足し算で読み替える。
    改元前の日付に新元号を付けたもの(令和 0 年、大正元年 1 月 1 日)と、存在しない日は strict に関わらず止まる。
    """
    s = normalize(text)
    m = _WAREKI.match(s)
    if not m:
        raise WarekiError(f"{text}: 和暦として解釈できない表記")
    era = _BY_KEY[m.group(1)]
    y = 1 if m.group(2) == "元" else int(m.group(2))
    if y < 1:
        raise WarekiError(f"{text}: {era.name}0年は存在しない(元年 = 1 年)")
    try:
        d = date(era.first_year + y - 1, int(m.group(3)), int(m.group(4)))
    except ValueError as e:
        raise WarekiError(f"{text}: 存在しない日({e})") from None
    return _check_range(era, d, text, strict)


def parse_date(text: str, *, strict: bool = True) -> date:
    """和暦と西暦が同じ列に混ざっているとき用。4 桁で始まれば西暦、それ以外は和暦として読む。"""
    s = normalize(text)
    m = _SEIREKI.match(s)
    if m:
        try:
            d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError as e:
            raise WarekiError(f"{text}: 存在しない日({e})") from None
        if d < GREGORIAN_START:
            raise WarekiError(f"{text}: 太陽暦の採用(明治6年1月1日)より前。この道具は変換しない")
        return d
    return to_date(text, strict=strict)


def to_wareki(d: date, *, style: str = "kanji") -> str:
    """西暦 date を和暦の文字列に直す。改元日当日は新元号。style = kanji(令和6年4月1日)/ letter(R6.4.1)。"""
    if d < GREGORIAN_START:
        raise WarekiError(f"{d.isoformat()}: 太陽暦の採用(明治6年1月1日)より前。この道具は変換しない")
    for era in ERAS:
        if era.start <= d and (era.end is None or d <= era.end):
            y = d.year - era.first_year + 1
            if style == "kanji":
                return f"{era.name}{'元' if y == 1 else y}年{d.month}月{d.day}日"
            if style == "letter":
                return f"{era.letter}{y}.{d.month}.{d.day}"
            raise ValueError(f"style は kanji か letter: {style!r}")
    raise WarekiError(f"{d.isoformat()}: 改元表に無い")     # 表の最後が open なので到達しない


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="wareki", description="和暦の日付を改元表で西暦に直す(表の外は止まる)")
    ap.add_argument("values", nargs="+", help="日付文字列。'-' なら標準入力の各行")
    ap.add_argument("--reverse", action="store_true", help="西暦(YYYY-MM-DD)→ 和暦")
    ap.add_argument("--lenient", action="store_true", help="終了日を過ぎた旧元号(平成32年)を読み替える")
    a = ap.parse_args(argv)
    values = [ln.rstrip("\r\n") for ln in sys.stdin] if a.values == ["-"] else a.values
    tab = a.values == ["-"]
    bad = 0
    for v in values:
        if v == "":
            continue
        try:
            out = to_wareki(date.fromisoformat(v)) if a.reverse else parse_date(v, strict=not a.lenient).isoformat()
            print(f"{v}\t{out}" if tab else out)
        except (WarekiError, ValueError) as e:
            bad += 1
            print(f"NG: {e}", file=sys.stderr)
            if tab:
                print(f"{v}\tNG")
    return 3 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
