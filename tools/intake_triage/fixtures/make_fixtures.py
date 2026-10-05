"""intake_triage の合成 fixture を作る(人・金額・取込仕様はすべて架空)。

同じ 18 行を、仕様表だけを差し替えて何通りにも仕分けられるようにしてある。
`shiyou.csv` と `shiyou_fugou_nashi.csv` の差は 1 欄(控除合計の repair)だけで、
そこだけで 2 本目と 3 本目の線が動くことを見るための対になっている。

使い方: python make_fixtures.py   (このフォルダに CSV を書き出す)
"""
from __future__ import annotations

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = "合成の取込仕様(架空)"

SPEC_FIELDS = ("column", "type", "domain", "required", "repair", "source")

SPEC = [
    ("社員番号", "コード", "長さ: 6", "○", "先頭をゼロで埋める"),
    ("氏名", "文字列", "長さ上限: 40", "○", ""),
    ("部署コード", "コード", "集合: 10|20|30", "○", ""),
    ("支給年月日", "日付", "形: YYYYMMDD", "○", "区切りを外して 8 桁に"),
    ("支給合計", "金額", "範囲: 0..9999999", "○", "半角の数字に直す"),
    ("控除合計", "金額", "範囲: -9999999..0", "○", "印字は符号なし"),
    ("差引支給額", "金額", "範囲: -9999999..9999999", "○", "桁区切りのカンマを外す"),
    ("備考", "文字列", "制限なし", "", ""),
]

ROW_FIELDS = tuple(name for name, *_ in SPEC)

# 通る行(違反なし)
PASSING = [
    ("000101", "山田 花子", "10", "20260925", "312000", "-48250", "263750", "新規"),
    ("000102", "佐藤 太郎", "20", "20260925", "286500", "-44120", "242380", ""),
    ("000103", "鈴木 一郎", "30", "20260925", "240000", "-38500", "201500", "再雇用"),
    ("000104", "高橋 みどり", "10", "20260925", "268000", "-41300", "226700", ""),
    ("000105", "伊藤 健", "20", "20260925", "251000", "-39650", "211350", "交替"),
    ("000106", "渡辺 さくら", "30", "20260925", "305000", "-47800", "257200", ""),
]

# 1 行につき 1 か所だけ、宣言から外れた値を置く(列 / 値 / 期待する違反)
BROKEN = [
    ("101", "中村 大輔", "10", "20260925", "298400", "-45300", "253100", "", "長さが違う"),
    ("000108", "小林 良子", "20", "20260925", "３１２０００", "-48250", "263750", "", "型と違う"),
    ("000109", "加藤 誠", "30", "20260925", "287000", "44120", "242880", "", "範囲の外"),
    ("000110", "吉田 彩", "10", "20260925", "312000", "-48250", "263,750", "", "型と違う"),
    ("000111", "山本 修", "20", "2026-09-25", "264000", "-40200", "223800", "", "形が違う"),
    ("000112", "中島 千尋", "30", "20260931", "279000", "-43100", "235900", "", "形が違う"),
    ("000113", "岡田 直樹", "40", "20260925", "255000", "-40000", "215000", "", "集合の外"),
    ("000114", "", "10", "20260925", "243000", "-37900", "205100", "", "必要な値が空"),
    ("000115", "長" * 41, "20", "20260925", "261000", "-41000", "220000", "", "桁あふれ"),
    ("000116", "森 陽子", "30", "20260925", "99999999", "-48250", "263750", "", "範囲の外"),
    ("00010A", "池田 隆", "10", "20260925", "272000", "-42500", "229500", "", "型と違う"),
    ("000118", "原田 恵", "20", "令和8年9月25日", "258000", "-40800", "217200", "", "型と違う"),
]


def _write_spec(path: Path, rows: list) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(SPEC_FIELDS)
        for name, type_name, domain, required, repair in rows:
            w.writerow([name, type_name, domain, required, repair, SOURCE])


def _write_rows(path: Path, rows: list, fields: tuple = ROW_FIELDS) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(fields)
        for row in rows:
            w.writerow(list(row))


def build() -> dict:
    """fixture を書き出し、{ファイル名: 行数} を返す。"""
    rows = [r[:len(ROW_FIELDS)] for r in BROKEN]
    _write_spec(HERE / "shiyou.csv", SPEC)
    _write_spec(HERE / "shiyou_fugou_nashi.csv",
                [(n, t, d, q, "" if n == "控除合計" else p) for n, t, d, q, p in SPEC])
    _write_spec(HERE / "shiyou_kata_kuuhaku.csv",
                [(n, "" if n == "支給合計" else t, d, q, p) for n, t, d, q, p in SPEC])
    _write_spec(HERE / "shiyou_iki_kuuhaku.csv",
                [(n, t, "" if n == "氏名" else d, q, p) for n, t, d, q, p in SPEC])
    _write_spec(HERE / "shiyou_juufuku.csv", SPEC + [SPEC[4]])
    _write_spec(HERE / "shiyou_michi_repair.csv",
                [(n, t, d, q, "近い値に寄せる" if n == "部署コード" else p) for n, t, d, q, p in SPEC])
    _write_spec(HERE / "shiyou_shikibetsu_nashi.csv", [s for s in SPEC if s[0] != "社員番号"])
    _write_spec(HERE / "shiyou_hissu_nashi.csv", [(n, t, d, "", p) for n, t, d, q, p in SPEC])
    _write_rows(HERE / "gyou.csv", PASSING + rows)
    _write_rows(HERE / "gyou_tooru.csv", PASSING)
    _write_rows(HERE / "gyou_yobun.csv", [r + ("内部メモ",) for r in PASSING],
                ROW_FIELDS + ("摘要",))
    _write_rows(HERE / "gyou_juufuku.csv", PASSING + [PASSING[0]])
    return {p.name: len(p.read_text(encoding="utf-8").splitlines()) - 1
            for p in sorted(HERE.glob("*.csv"))}


if __name__ == "__main__":
    for name, n in build().items():
        print(f"{name}: {n} 行")
