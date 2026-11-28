"""switch_lag の fixture を作り直す(合成と崩した表。架空の地域と架空の回だけ)。

使い方: python make_fixtures.py
私の数表から起こした表(suuhyo/)は utsusu.py が写す。見る日の登録表(suuhyo/days.csv)は手で書いたもの。
"""
from __future__ import annotations

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROW = ["rule", "セグメント", "回", "開始日", "終了日", "出典"]
DAY = ["見る日", "理由", "出典"]
SETUP = ["種類", "値", "出典"]


def write(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


R = "架空の運賃表"
GOUSEI_ROWS = [
    # 第1回: 全地域が同じ日に移る(窓 0 日)
    [R, "東の里", "第1回", "2030-04-01", "2030-12-20", "合成 L1"],
    [R, "西の里", "第1回", "2030-04-01", "2031-01-10", "合成 L2"],
    [R, "南の里", "第1回", "2030-04-01", "2031-01-10", "合成 L3"],
    [R, "北の里", "第1回", "2030-04-01", "2031-02-01", "合成 L4"],
    [R, "中の里", "第1回", "2030-04-01", "2031-10-01", "合成 L5"],
    # 第2回: 窓が年をまたぐ。中の里の行は無い
    [R, "東の里", "第2回", "2030-12-20", "2031-10-01", "合成 L6"],
    [R, "西の里", "第2回", "2031-01-10", "2031-10-01", "合成 L7"],
    [R, "南の里", "第2回", "2031-01-10", "2031-10-15", "合成 L8"],
    [R, "北の里", "第2回", "2031-02-01", "2031-10-25", "合成 L9(終了日が次の開始日とずれている)"],
    # 第3回: 北の里は前の行の終了日と開始日の間が空く
    [R, "東の里", "第3回", "2031-10-01", "INF", "合成 L10"],
    [R, "西の里", "第3回", "2031-10-01", "INF", "合成 L11"],
    [R, "南の里", "第3回", "2031-10-15", "INF", "合成 L12"],
    [R, "北の里", "第3回", "2031-11-01", "INF", "合成 L13"],
    [R, "中の里", "第3回", "2031-10-01", "INF", "合成 L14"],
]
GOUSEI_DAYS = [
    ["2030-03-31", "どの行も始まる前の日", "合成"],
    ["2031-01-15", "第2回の窓の中の日", "合成"],
    ["2031-10-10", "第3回の窓の中の日", "合成"],
    ["2031-10-28", "北の里の行が途切れている日", "合成"],
]
GOUSEI_SETUP = (
    [["回", f"第{i}回", "合成(回の順)"] for i in (1, 2, 3)]
    + [["区間の端", "半開", "合成"]]
    + [["セグメント", s, "合成(全体の一覧)"] for s in ("東の里", "西の里", "南の里", "北の里", "中の里")]
)

KOWASHITA_ROWS = GOUSEI_ROWS + [
    [R, "東の里", "第1回", "2030-04-01", "2030-12-20", "合成 L1 の写し(同じ rule・地域・回)"],
    [R, "西の里", "第2回", "2031/01/10", "2031-10-01", "合成(日付の形でない)"],
    [R, "南の里", "第3回", "2031-10-15", "INF", ""],
    [R, "北の里", "第9回", "2032-10-01", "INF", "合成(回の順に無い回)"],
    [R, "沖の里", "第3回", "2031-10-01", "INF", "合成(全体の一覧に無い地域)"],
]
KOWASHITA_DAYS = GOUSEI_DAYS + [["来月", "日付の形でない", "合成"], ["2031-12-01", "出典を書き忘れた日", ""]]
KOWASHITA_SETUP_EDGE = [[k, ("左閉" if k == "区間の端" else v), s] for k, v, s in GOUSEI_SETUP]


def main() -> None:
    write(HERE / "gousei" / "rows.csv", ROW, GOUSEI_ROWS)
    write(HERE / "gousei" / "days.csv", DAY, GOUSEI_DAYS)
    write(HERE / "gousei" / "days_empty.csv", DAY, [])
    write(HERE / "gousei" / "setup.csv", SETUP, GOUSEI_SETUP)
    write(HERE / "gousei" / "setup_ryouhei.csv", SETUP, [[k, ("両閉" if k == "区間の端" else v), s] for k, v, s in GOUSEI_SETUP])
    write(HERE / "kowashita" / "rows.csv", ROW, KOWASHITA_ROWS)
    write(HERE / "kowashita" / "days.csv", DAY, KOWASHITA_DAYS)
    write(HERE / "kowashita" / "setup.csv", SETUP, GOUSEI_SETUP)
    write(HERE / "kowashita" / "setup_edge.csv", SETUP, KOWASHITA_SETUP_EDGE)
    print("gousei / kowashita を書いた")


if __name__ == "__main__":
    main()
