"""switch_lag の単体テスト。記事に載せた件数は test_measure_* の assert で固定している(値が変われば記事も変える)。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import switch_lag as S  # noqa: E402

FX = ROOT / "fixtures"


def load(name: str, days: str = "days.csv", setup: str = "setup.csv"):
    d = FX / name
    return [S.read_csv(d / f) for f in ("rows.csv", days, setup)]


def pair(res: dict, day: str, new: str) -> dict:
    return next(p for p in res["日ごと"] if p["見る日"] == day and p["新しい回"] == new)


def names(p: dict, cat: str) -> list[str]:
    return [x["セグメント"] for x in p["セグメント"] if x["区分"] == cat]


def window(res: dict, rd: str) -> dict:
    return next(w for w in res["窓"] if w["回"] == rd)


def row(seg="甲", rd="1", start="2030-04-01", end="INF", src="x", rule="表"):
    return {"rule": rule, "セグメント": seg, "回": rd, "開始日": start, "終了日": end, "出典": src}


def setup(rounds=("1", "2"), segs=("甲", "乙"), edge="半開"):
    return ([{"種類": "回", "値": r, "出典": "x"} for r in rounds] + [{"種類": "区間の端", "値": edge, "出典": "x"}]
            + [{"種類": "セグメント", "値": s, "出典": "x"} for s in segs])


def day(d, src="x"):
    return {"見る日": d, "理由": "試験", "出典": src}


# ---- 記事に載せた測定値(私の数表 1 本から起こした 3 表) ----
def test_measure_suuhyo_table_size():
    res = S.judge(*load("suuhyo"))
    n = res["件数"]
    assert n["行の表の行"] == 1079 and n["使った行"] == 1079 and n["別枠の行"] == 0
    assert n["回ごとの行数の合計"] == 1079
    assert len(res["回の順"]) == 24 and res["回の順"][0] == "2002" and res["回の順"][-1] == "2025"
    assert res["セグメントの全体の数"] == 47
    assert n["見る日"] == 11
    assert len(res["日ごと"]) == 253                       # 見る日 11 × 回の対 23
    assert sum(len(p["セグメント"]) for p in res["日ごと"]) == 11891   # × 地域 47


def test_measure_suuhyo_windows():
    res = S.judge(*load("suuhyo"))
    assert sum(1 for w in res["窓"] if w["行数"] == 47) == 22
    assert window(res, "2003")["行数"] == 5 and len(window(res, "2003")["行の無いセグメント"]) == 42
    assert window(res, "2020")["行数"] == 40
    assert window(res, "2020")["行の無いセグメント"] == ["京都", "北海道", "大阪", "山口", "広島", "東京", "静岡"]
    assert 47 * 24 - 1079 == 49 == 42 + 7
    assert window(res, "2006")["日数"] == 1
    assert window(res, "2011")["日数"] == 42 and window(res, "2011")["開始日の種類"] == 19
    assert window(res, "2024")["日数"] == 31 and window(res, "2024")["開始日の種類"] == 11
    w = window(res, "2025")
    assert (w["最初の開始日"], w["最後の開始日"], w["日数"], w["開始日の種類"]) == ("2025-10-01", "2026-03-31", 181, 18)
    assert max(x["日数"] for x in res["窓"] if x["回"] != "2025") == 42
    assert [x["回"] for x in res["窓"] if x["印_窓が暦の年をまたぐ"]] == ["2025"]


def test_measure_suuhyo_window_table():
    """記事の表(回ごとの窓、全 24 回)と同じ値。"""
    res = S.judge(*load("suuhyo"))
    got = [(w["回"], w["行数"], w["最初の開始日"], w["最後の開始日"], w["日数"], w["開始日の種類"]) for w in res["窓"]]
    assert got == [
        ("2002", 47, "2002-09-29", "2002-10-06", 7, 6), ("2003", 5, "2003-10-01", "2003-10-19", 18, 2),
        ("2004", 47, "2004-09-30", "2004-10-17", 17, 4), ("2005", 47, "2005-09-30", "2005-10-07", 7, 4),
        ("2006", 47, "2006-09-30", "2006-10-01", 1, 2), ("2007", 47, "2007-10-19", "2007-10-31", 12, 8),
        ("2008", 47, "2008-10-05", "2008-11-07", 33, 15), ("2009", 47, "2009-09-30", "2009-10-31", 31, 16),
        ("2010", 47, "2010-10-07", "2010-11-05", 29, 17), ("2011", 47, "2011-09-30", "2011-11-11", 42, 19),
        ("2012", 47, "2012-09-30", "2012-11-04", 35, 17), ("2013", 47, "2013-10-06", "2013-11-06", 31, 15),
        ("2014", 47, "2014-10-01", "2014-10-26", 25, 13), ("2015", 47, "2015-10-01", "2015-10-18", 17, 10),
        ("2016", 47, "2016-10-01", "2016-10-20", 19, 8), ("2017", 47, "2017-09-30", "2017-10-14", 14, 8),
        ("2018", 47, "2018-10-01", "2018-10-06", 5, 5), ("2019", 47, "2019-10-01", "2019-10-06", 5, 6),
        ("2020", 40, "2020-10-01", "2020-10-09", 8, 6), ("2021", 47, "2021-10-01", "2021-10-08", 7, 5),
        ("2022", 47, "2022-10-01", "2022-10-20", 19, 8), ("2023", 47, "2023-10-01", "2023-10-14", 13, 8),
        ("2024", 47, "2024-10-01", "2024-11-01", 31, 11), ("2025", 47, "2025-10-01", "2026-03-31", 181, 18)]


def test_measure_suuhyo_2025_days():
    res = S.judge(*load("suuhyo"))
    got = {d: (pair(res, d, "2025")["件数"]["A"], pair(res, d, "2025")["件数"]["B"]) for d in
           ("2025-09-30", "2025-10-01", "2025-11-01", "2025-12-01", "2026-01-01", "2026-02-01", "2026-03-01",
            "2026-03-30", "2026-03-31")}
    assert got == {"2025-09-30": (0, 47), "2025-10-01": (1, 46), "2025-11-01": (25, 22), "2025-12-01": (40, 7),
                   "2026-01-01": (45, 2), "2026-02-01": (45, 2), "2026-03-01": (46, 1), "2026-03-30": (46, 1),
                   "2026-03-31": (47, 0)}
    assert all(pair(res, d, "2025")["件数"]["C"] == 0 and pair(res, d, "2025")["件数"]["D"] == 0 for d in got)
    assert names(pair(res, "2025-10-01", "2025"), "A") == ["栃木"]
    assert names(pair(res, "2025-12-01", "2025"), "B") == ["大分", "山形", "徳島", "熊本", "福島", "秋田", "群馬"]
    assert names(pair(res, "2026-01-01", "2025"), "B") == ["秋田", "群馬"]
    assert names(pair(res, "2026-03-30", "2025"), "B") == ["秋田"]
    line = {x["セグメント"]: x for x in pair(res, "2025-10-01", "2025")["セグメント"]}
    assert line["秋田"]["その日までの日数"] == 181 and line["群馬"]["その日までの日数"] == 151
    assert line["新潟"]["その日までの日数"] == 1


def test_measure_suuhyo_2020_days():
    res = S.judge(*load("suuhyo"))
    assert pair(res, "2020-10-01", "2020")["件数"] == {"A": 22, "B": 18, "C": 7, "D": 0}
    assert pair(res, "2020-10-09", "2020")["件数"] == {"A": 40, "B": 0, "C": 7, "D": 0}
    c = [x for x in pair(res, "2020-10-09", "2020")["セグメント"] if x["区分"] == "C"]
    assert [x["セグメント"] for x in c] == ["京都", "北海道", "大阪", "山口", "広島", "東京", "静岡"]
    assert all(x["当たる行の回"] == "2019" and x["新しい回の開始日"] == "" for x in c)   # C は全て「行が表に無い」
    assert pair(res, "2020-10-09", "2021")["件数"] == {"A": 0, "B": 47, "C": 0, "D": 0}


def test_measure_suuhyo_rest():
    res = S.judge(*load("suuhyo"))
    # 2025 の回の日に見ると、それより前の回の対は全て A(行はもう先の回に移っている)
    assert all(p["件数"]["A"] == 47 for p in res["日ごと"] if p["見る日"] >= "2025-09-30" and p["新しい回"] != "2025")
    assert sum(p["印_つながらないの数"] for p in res["日ごと"]) == 0
    assert sum(p["件数"]["D"] for p in res["日ごと"]) == 0
    assert sum(1 for p in res["日ごと"] for x in p["セグメント"] if x["当たる行の数"] > 1) == 0
    assert S.exit_code(res) == 3
    assert all(ok for _, ok in S.verify(*load("suuhyo")))


def test_measure_gousei():
    res = S.judge(*load("gousei"))
    assert res["件数"]["行の表の行"] == 14 and res["件数"]["別枠の行"] == 0
    assert [(w["行数"], w["日数"], w["開始日の種類"]) for w in res["窓"]] == [(5, 0, 1), (4, 43, 3), (5, 31, 3)]
    assert window(res, "第2回")["行の無いセグメント"] == ["中の里"] and window(res, "第2回")["印_窓が暦の年をまたぐ"]
    assert pair(res, "2030-03-31", "第2回")["件数"] == {"A": 0, "B": 0, "C": 0, "D": 5}
    assert pair(res, "2031-01-15", "第2回")["件数"] == {"A": 3, "B": 1, "C": 1, "D": 0}
    assert names(pair(res, "2031-01-15", "第2回"), "C") == ["中の里"]
    assert pair(res, "2031-10-10", "第3回")["件数"] == {"A": 3, "B": 2, "C": 0, "D": 0}
    assert pair(res, "2031-10-28", "第3回")["件数"] == {"A": 4, "B": 0, "C": 0, "D": 1}
    assert [x["セグメント"] for x in pair(res, "2031-10-10", "第3回")["セグメント"] if x["印_つながらない"]] == ["北の里"]
    assert all(ok for _, ok in S.verify(*load("gousei")))


def test_measure_kowashita():
    res = S.judge(*load("kowashita"))
    why = [x["理由"] for x in res["別枠"]["行"]]
    assert len(why) == 8 and res["件数"]["使った行"] == 11
    assert {w: why.count(w) for w in set(why)} == {
        "同じ (rule, セグメント, 回) が 2 行": 4, "日付として読めない": 1, "出典が空": 1,
        "回の id が回の順に無い": 1, "セグメントが全体の一覧に無い": 1}
    assert [x["理由"] for x in res["別枠"]["見る日"]] == ["出典が空", "日付として読めない"]
    edge = S.judge(*load("kowashita", setup="setup_edge.csv"))
    assert edge["別枠"]["比べ方"] == [{"表": "比べ方", "値": "左閉", "理由": "区間の端が 2 つの値(半開 / 両閉)以外"}]
    assert edge["日ごと"] == [] and len(edge["窓"]) == 3      # 端が別枠なら窓だけ返す


# ---- 区分の決め方 ----
def test_four_categories_on_small_table():
    rows = [row("甲", "1", "2030-04-01", "2031-04-01"), row("甲", "2", "2031-04-01"),
            row("乙", "1", "2030-04-01", "2031-06-01"), row("乙", "2", "2031-06-01"),
            row("丙", "1", "2030-04-01"), row("丁", "2", "2031-08-01")]
    res = S.judge(rows, [day("2031-05-01")], setup(segs=("甲", "乙", "丙", "丁")))
    got = {x["セグメント"]: x["区分"] for x in res["日ごと"][0]["セグメント"]}
    assert got == {"甲": "A", "乙": "B", "丙": "C", "丁": "D"}
    assert [x["その日までの日数"] for x in res["日ごと"][0]["セグメント"] if x["区分"] == "B"] == [31]


def test_edge_changes_the_boundary_day():
    rows = [row("甲", "1", "2030-04-01", "2031-04-01"), row("甲", "2", "2031-04-02")]
    half = S.judge(rows, [day("2031-04-01")], setup(segs=("甲",), edge="半開"))["日ごと"][0]
    both = S.judge(rows, [day("2031-04-01")], setup(segs=("甲",), edge="両閉"))["日ごと"][0]
    assert half["件数"]["D"] == 1 and both["件数"]["B"] == 1
    assert half["印_つながらないの数"] == 1 and both["印_つながらないの数"] == 0   # 両閉は翌日に始まればつながる


def test_later_round_counts_as_already_moved():
    rows = [row("甲", "1", "2030-04-01", "2031-04-01"), row("甲", "3", "2031-04-01")]
    res = S.judge(rows, [day("2032-01-01")], setup(rounds=("1", "2", "3"), segs=("甲",)))
    assert [(p["新しい回"], p["件数"]["A"]) for p in res["日ごと"]] == [("2", 1), ("3", 1)]
    assert window(res, "2")["行数"] == 0 and window(res, "2")["日数"] is None


def test_row_order_and_digest():
    rows, days, st = load("gousei")
    assert S.digest(S.judge(rows[::-1], days, st)) == S.digest(S.judge(rows, days, st))
    assert S.digest(S.judge(rows, days[::-1], st)) == S.digest(S.judge(rows, days, st))


def test_empty_days_returns_windows_only():
    res = S.judge(*load("gousei", days="days_empty.csv"))
    assert res["日ごと"] == [] and len(res["窓"]) == 3


def test_no_payload_and_no_clock():
    src = (ROOT / "switch_lag.py").read_text(encoding="utf-8")
    assert S.clock_calls(src) == 0
    assert S.clock_calls("import datetime\nx = datetime.date.today()\ny = datetime.datetime.now()") == 2
    assert "payload" not in S.ROW_COLS and "値" not in S.ROW_COLS


@pytest.mark.parametrize("bad", [
    lambda r, d, s: ([{k: v for k, v in x.items() if k != "出典"} for x in r], d, s),
    lambda r, d, s: (r + [row(rule="")], d, s),
    lambda r, d, s: (r, d + [d[0]], s),
    lambda r, d, s: (r, d, s + [{"種類": "区間の端", "値": "両閉", "出典": "x"}]),
    lambda r, d, s: (r, d, s + [s[0]]),
    lambda r, d, s: (r, d, [x for x in s if x["種類"] != "セグメント"]),
    lambda r, d, s: (r, d, s + [{"種類": "順位", "値": "1", "出典": "x"}]),
])
def test_unreadable_tables_stop(bad):
    with pytest.raises(S.Unreadable):
        S.judge(*bad(*load("gousei")))


# ---- CLI ----
def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "switch_lag.py"), *args],
                          capture_output=True, text=True, encoding="utf-8")


def test_cli_exit_codes(tmp_path):
    g = FX / "gousei"
    r = run("--rows", str(g / "rows.csv"), "--days", str(g / "days.csv"), "--setup", str(g / "setup.csv"), "--verify")
    assert r.returncode == 3 and r.stdout.count(": 合う") == 5
    one = tmp_path / "rows.csv"
    one.write_text("rule,セグメント,回,開始日,終了日,出典\n表,甲,1,2030-04-01,2031-04-01,x\n表,甲,2,2031-04-01,INF,x\n",
                   encoding="utf-8")
    st = tmp_path / "setup.csv"
    st.write_text("種類,値,出典\n回,1,x\n回,2,x\n区間の端,半開,x\nセグメント,甲,x\n", encoding="utf-8")
    dy = tmp_path / "days.csv"
    dy.write_text("見る日,理由,出典\n2031-05-01,試験,x\n", encoding="utf-8")
    assert run("--rows", str(one), "--days", str(dy), "--setup", str(st), "--verify").returncode == 0
    bad = tmp_path / "bad.csv"
    bad.write_text("rule,セグメント\n表,甲\n", encoding="utf-8")
    assert run("--rows", str(bad), "--setup", str(st)).returncode == 2
    r = run("--rows", str(g / "rows.csv"), "--setup", str(g / "setup.csv"), "--json")
    assert '"日ごと": []' in r.stdout and '"sha256"' in r.stdout
