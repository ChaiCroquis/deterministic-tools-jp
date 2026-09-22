"""wareki のテスト。fixture は全て合成データ(fixtures/make_fixtures.py)。

後半の test_measure_* は「正規表現 + 年の足し算」だけの素朴な変換と、この道具を合成 1,000 件で比べる
(記事の数値はここから取る。値は固定 seed で決定論的に再現し、変わったら記事の数字も変える)。
"""
from __future__ import annotations

import csv
import random
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
import wareki as W  # noqa: E402


# ---- 表記の揺れ(F2 の各行) ----------------------------------------------------------------

@pytest.mark.parametrize("text, expected", [
    ("令和6年4月1日", date(2024, 4, 1)),
    ("令和 6 年 4 月 1 日", date(2024, 4, 1)),
    ("令6.4.1", date(2024, 4, 1)),
    ("R6.4.1", date(2024, 4, 1)),
    ("r6/4/1", date(2024, 4, 1)),
    ("R06-04-01", date(2024, 4, 1)),
    ("令和６年４月１日", date(2024, 4, 1)),      # 全角数字
    ("Ｒ６．４．１", date(2024, 4, 1)),          # 全角英字 + 全角ピリオド
    ("令和元年5月1日", date(2019, 5, 1)),        # 元年
    ("R1.5.1", date(2019, 5, 1)),
    ("平成31年4月30日", date(2019, 4, 30)),      # 改元の前日
    ("昭和64年1月7日", date(1989, 1, 7)),
    ("平成元年1月8日", date(1989, 1, 8)),        # 改元日当日は新元号
    ("大正15年12月24日", date(1926, 12, 24)),
    ("昭和元年12月25日", date(1926, 12, 25)),
    ("明治45年7月29日", date(1912, 7, 29)),
    ("大正元年7月30日", date(1912, 7, 30)),
    ("明治6年1月1日", date(1873, 1, 1)),         # 太陽暦の採用日 = この道具の下限
    ("M6.1.1", date(1873, 1, 1)),
])
def test_to_date(text, expected):
    assert W.to_date(text) == expected


@pytest.mark.parametrize("text, reason", [
    ("平成31年5月1日", "改元後"),      # 平成は 2019-04-30 まで
    ("平成32年4月1日", "改元後"),
    ("昭和64年1月8日", "改元後"),      # 昭和は 1989-01-07 まで
    ("大正15年12月25日", "改元後"),
    ("明治45年7月30日", "改元後"),
    ("大正元年1月1日", "改元前"),      # 大正は 1912-07-30 から
    ("令和元年4月30日", "改元前"),
    ("令和0年5月1日", "0年"),
    ("令和6年2月30日", "存在しない日"),
    ("令和6年13月1日", "存在しない日"),
    ("明治5年12月31日", "太陽暦"),     # 太陽暦の採用より前
    ("明治元年1月1日", "太陽暦"),
    ("令和6年4月", "解釈できない"),
    ("和暦6.4.1", "解釈できない"),
    ("X6.4.1", "解釈できない"),
    ("", "解釈できない"),
])
def test_stops(text, reason):
    with pytest.raises(W.WarekiError) as ei:
        W.to_date(text)
    assert reason in str(ei.value)


def test_lenient_only_relaxes_the_end_side():
    """strict=False は「終了日を過ぎた旧元号」だけ読み替える。改元前の新元号・存在しない日は変わらず止まる。"""
    assert W.to_date("平成31年5月1日", strict=False) == date(2019, 5, 1)
    assert W.to_date("平成32年4月1日", strict=False) == date(2020, 4, 1)
    assert W.to_date("昭和64年1月8日", strict=False) == date(1989, 1, 8)
    with pytest.raises(W.WarekiError):
        W.to_date("令和元年4月30日", strict=False)
    with pytest.raises(W.WarekiError):
        W.to_date("平成32年2月30日", strict=False)


def test_error_message_offers_the_new_era_name():
    with pytest.raises(W.WarekiError) as ei:
        W.to_date("平成31年5月1日")
    assert "令和元年5月1日" in str(ei.value)


def test_parse_date_accepts_seireki_in_the_same_column():
    assert W.parse_date("2024-04-01") == date(2024, 4, 1)
    assert W.parse_date("2024/4/1") == date(2024, 4, 1)
    assert W.parse_date("２０２４年４月１日") == date(2024, 4, 1)
    assert W.parse_date("令和6年4月1日") == date(2024, 4, 1)
    with pytest.raises(W.WarekiError):
        W.parse_date("2024-02-30")
    with pytest.raises(W.WarekiError):
        W.parse_date("1872-12-31")


def test_str_input_is_type_error():
    with pytest.raises(TypeError):
        W.to_date(20240401)  # type: ignore[arg-type]


# ---- 逆変換(同じ表から引く。改元日当日は新元号) ------------------------------------------

@pytest.mark.parametrize("d, kanji, letter", [
    (date(2024, 4, 1), "令和6年4月1日", "R6.4.1"),
    (date(2019, 5, 1), "令和元年5月1日", "R1.5.1"),
    (date(2019, 4, 30), "平成31年4月30日", "H31.4.30"),
    (date(1989, 1, 8), "平成元年1月8日", "H1.1.8"),
    (date(1989, 1, 7), "昭和64年1月7日", "S64.1.7"),
    (date(1926, 12, 25), "昭和元年12月25日", "S1.12.25"),
    (date(1926, 12, 24), "大正15年12月24日", "T15.12.24"),
    (date(1912, 7, 30), "大正元年7月30日", "T1.7.30"),
    (date(1912, 7, 29), "明治45年7月29日", "M45.7.29"),
    (date(1873, 1, 1), "明治6年1月1日", "M6.1.1"),
])
def test_to_wareki(d, kanji, letter):
    assert W.to_wareki(d) == kanji
    assert W.to_wareki(d, style="letter") == letter


def test_to_wareki_refuses_before_gregorian():
    with pytest.raises(W.WarekiError):
        W.to_wareki(date(1872, 12, 31))


def test_era_table_is_contiguous():
    """表の不変式: 各元号の終了日の翌日が次の元号の開始日(隙間も重なりも無い)。最後だけ open。"""
    for a, b in zip(W.ERAS, W.ERAS[1:]):
        assert a.end is not None and a.end + timedelta(days=1) == b.start
        assert a.first_year <= a.end.year and b.first_year == b.start.year
    assert W.ERAS[-1].end is None


# ---- fixture(和暦と西暦が同じ列に混ざった入社日) ------------------------------------------

def test_fixture_mixed_dates():
    rows = list(csv.DictReader((FX / "mixed_dates.csv").open(encoding="utf-8", newline="")))
    assert len(rows) == 17
    for r in rows:
        if r["期待"] == "NG":
            with pytest.raises(W.WarekiError):
                W.parse_date(r["入社日"])
        else:
            assert W.parse_date(r["入社日"]).isoformat() == r["期待"], r["入社日"]


# ---- CLI ----------------------------------------------------------------------------------

def run_cli(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "wareki.py"), *args],
                          capture_output=True, text=True, encoding="utf-8", input=stdin)


def test_cli_prints_iso():
    r = run_cli("令和6年4月1日", "R6.4.1")
    assert r.returncode == 0 and r.stdout.split() == ["2024-04-01", "2024-04-01"]


def test_cli_reverse():
    r = run_cli("--reverse", "2019-05-01")
    assert r.returncode == 0 and r.stdout.strip() == "令和元年5月1日"


def test_cli_exit3_when_out_of_table():
    r = run_cli("平成31年5月1日")
    assert r.returncode == 3 and "NG" in r.stderr and r.stdout == ""


def test_cli_lenient():
    r = run_cli("--lenient", "平成31年5月1日")
    assert r.returncode == 0 and r.stdout.strip() == "2019-05-01"


def test_cli_stdin_tab_separated():
    r = run_cli("-", stdin="令和6年4月1日\n平成31年5月1日\n")
    assert r.returncode == 3
    assert r.stdout.splitlines() == ["令和6年4月1日\t2024-04-01", "平成31年5月1日\tNG"]


# ---- 素朴な変換(正規表現 + 年の足し算)との比較。合成 1,000 件、固定 seed ----------------------

SEED = 20260922
NAIVE_OFFSET = {"明治": 1867, "大正": 1911, "昭和": 1925, "平成": 1988, "令和": 2018}
NAIVE_RE = re.compile(r"^(明治|大正|昭和|平成|令和)(\d+)年(\d+)月(\d+)日$")


def naive_offset(s: str) -> date | None:
    """私の記録に散在していた形: 漢字元号 + 年の足し算。改元表を持たない。"""
    m = NAIVE_RE.match(s)
    if not m:
        return None
    try:
        return date(NAIVE_OFFSET[m.group(1)] + int(m.group(2)), int(m.group(3)), int(m.group(4)))
    except ValueError:
        return None


def synth_dates(n: int, seed: int = SEED) -> list[date]:
    rng = random.Random(seed)
    lo, hi = date(1873, 1, 1).toordinal(), date(2100, 12, 31).toordinal()
    return [date.fromordinal(rng.randint(lo, hi)) for _ in range(n)]


def test_measure_roundtrip_1000():
    """西暦 → 和暦 → 西暦 が 1,000 件全部で元に戻る(漢字と略字の両方)。"""
    ds = synth_dates(1000)
    ok_kanji = sum(1 for d in ds if W.to_date(W.to_wareki(d)) == d)
    ok_letter = sum(1 for d in ds if W.to_date(W.to_wareki(d, style="letter")) == d)
    print(f"\n[measure] roundtrip kanji: {ok_kanji}/1000, letter: {ok_letter}/1000")
    assert ok_kanji == 1000 and ok_letter == 1000


def synth_boundary_strings(n: int, seed: int = SEED) -> list[str]:
    """元号ごとに「最終年 + 2」までの年を等確率で振る。改元をまたぐ表記が自然に混ざる。日は 1〜28。"""
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        era = rng.choice(W.ERAS)
        last = (era.end.year - era.first_year + 1) if era.end else 10
        y = rng.randint(1, last + 2)
        out.append(f"{era.name}{y}年{rng.randint(1, 12)}月{rng.randint(1, 28)}日")
    return out


def _ok(s: str, **kw) -> bool:
    try:
        W.to_date(s, **kw)
        return True
    except W.WarekiError:
        return False


def test_measure_naive_offset_passes_dates_outside_the_table():
    """素朴な足し算は何件を『黙って通す』か。この道具はその全件で止まる。"""
    ss = synth_boundary_strings(1000)
    naive_ok = sum(1 for s in ss if naive_offset(s) is not None)
    kinds = {"改元後の旧元号": 0, "改元前の新元号": 0, "太陽暦以前": 0}
    for s in ss:
        if naive_offset(s) is None:
            continue
        try:
            W.to_date(s)
        except W.WarekiError as e:
            msg = str(e)
            kinds["改元後の旧元号" if "終わっている" in msg else "太陽暦以前" if "太陽暦" in msg else "改元前の新元号"] += 1
    silent = sum(kinds.values())
    print(f"\n[measure] naive offset converted: {naive_ok}/1000, of which outside the era table: {silent} {kinds}")
    assert naive_ok == 1000                  # 素朴な足し算は暦として存在する日なら全部通す
    # 記事に載せた値。固定 seed(20260922)で決定論的に再現する。変わったら記事の数字も変える
    assert silent == 98
    assert kinds == {"改元後の旧元号": 52, "改元前の新元号": 24, "太陽暦以前": 22}
    # strict=False なら、終了日側の超過分(改元後の旧元号)だけは読み替えられる。改元前の新元号・太陽暦以前は変わらず止まる
    lenient_ok = sum(1 for s in ss if _ok(s, strict=False))
    print(f"[measure] this tool strict: {1000 - silent}/1000, lenient: {lenient_ok}/1000")
    assert 1000 - silent == 902 and lenient_ok == 954


STYLES = ("kanji", "kanji_spaced", "one_kanji_dot", "letter_dot", "letter_slash_zero",
          "fullwidth_kanji", "fullwidth_letter", "hyphen")


def render(d: date, style: str) -> str:
    era = next(e for e in W.ERAS if e.start <= d and (e.end is None or d <= e.end))
    y = d.year - era.first_year + 1
    if style == "kanji":
        return W.to_wareki(d)
    if style == "kanji_spaced":
        return f"{era.name} {y} 年 {d.month} 月 {d.day} 日"
    if style == "one_kanji_dot":
        return f"{era.name[0]}{y}.{d.month}.{d.day}"
    if style == "letter_dot":
        return W.to_wareki(d, style="letter")
    if style == "letter_slash_zero":
        return f"{era.letter}{y:02d}/{d.month:02d}/{d.day:02d}"
    if style == "fullwidth_kanji":
        return W.to_wareki(d).translate(str.maketrans("0123456789", "０１２３４５６７８９"))
    if style == "fullwidth_letter":
        return W.to_wareki(d, style="letter").translate(str.maketrans("0123456789.MTSHR", "０１２３４５６７８９．ＭＴＳＨＲ"))
    if style == "hyphen":
        return f"{era.name}{y}-{d.month}-{d.day}"
    raise ValueError(style)


def test_measure_notation_variety():
    """同じ 1,000 日を 8 種類の表記に散らす。素朴な正規表現は何件読めるか、この道具は何件読めるか。"""
    rng = random.Random(SEED)
    pairs = [(d, rng.choice(STYLES)) for d in synth_dates(1000)]
    naive_ok = sum(1 for d, st in pairs if naive_offset(render(d, st)) == d)
    this_ok = sum(1 for d, st in pairs if W.to_date(render(d, st)) == d)
    print(f"\n[measure] 8 notations x 1000: naive regex read {naive_ok}/1000, this tool {this_ok}/1000")
    assert this_ok == 1000
    # 記事に載せた値。固定 seed で決定論的に再現する。変わったら記事の数字も変える。
    # 素朴な正規表現が読めるのは「令和6年4月1日」と、その全角数字版(Python の \d は全角数字にも一致する)の 2 種類。元年は読めない
    assert naive_ok == 276
