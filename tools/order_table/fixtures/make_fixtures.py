"""order_table の合成 fixture。金額も日付も氏名も架空で、実データ・実在の取引先名は 1 つも入れない。

書くもの(どれも決定論。同じ実行で同じバイト列になる)。

  data_shikyuu.csv              支給控除の形を写した合成のデータ表 12 行
  sengen_mitsu.csv              密な鍵(支給日 → 区分 → 社員番号)。順が一意に決まる側
  sengen_sokaku.csv             粗い鍵(支給日 → 区分)。同値の組が残って止まる側
  sengen_shain_seisuu.csv       社員番号を 整数 として宣言した 1 鍵
  sengen_shain_codepoint.csv    社員番号を コードポイント列 として宣言した 1 鍵(10 が 9 の前に来る)
  sengen_shain_kesson_saki.csv  上と同じで、欠損の置き場所だけ 先 に変えた表
  sengen_shain_kouzyun.csv      上と同じで、向きだけ 降順 に変えた表(欠損は 後 のまま)
  sengen_kingaku_decimal.csv    金額を Decimal として宣言(829 と 829.0 が同値になる)
  sengen_kingaku_codepoint.csv  金額を コードポイント列 として宣言(829 と 829.0 は別の値)
  kowashita/*.csv               止まる理由コードと「表として読めない」を出すために 1 か所だけ崩した表

使い方: python fixtures/make_fixtures.py   (この置き場に書き直す)
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

DATA_HEADER = ["社員番号", "氏名カナ", "区分", "支給日", "金額", "摘要"]

# 合成のデータ表。社員番号は文字列として全て別(1 行だけ空欄)、金額は文字列として全て別で、
# 829 と 829.0 だけが数として等しい
DATA_ROWS = [
    ["9", "ヤマダ", "甲", "2026-04-25", "8290", ""],
    ["10", "スズキ", "乙", "2026-04-25", "829.0", ""],
    ["2", "サトウ", "甲", "2026-04-25", "829", ""],
    ["100", "タナカ", "丙", "2026-04-25", "10450", "4 月分,調整あり(合成)"],
    ["7", "イトウ", "甲", "2026-05-25", "8291", ""],
    ["31", "ワタナベ", "乙", "2026-05-25", "9120", ""],
    ["45", "タカハシ", "丙", "2026-05-25", "11045", ""],
    ["103", "コバヤシ", "甲", "2026-05-25", "8536", ""],
    ["8", "ナカムラ", "乙", "2026-06-25", "9121", ""],
    ["12", "カトウ", "甲", "2026-06-25", "8537", ""],
    ["60", "ヨシダ", "丙", "2026-06-25", "11046", ""],
    ["", "モリ", "乙", "2026-06-25", "9122", "社員番号が空欄の行(合成)"],
]

DECL_HEADER = ["rank", "column", "direction", "kind", "missing", "choices", "source", "swap"]

# 宣言表の出典。repo 内の行を指すものは実在の行番号
SRC_HIDUKE = "articles/07_asof_table.md L28"
SRC_KUBUN = "articles/09_update_ledger.md L58"
SRC_SHAIN = "articles/05_intake_csv.md L24"
SRC_KINGAKU = "articles/19_variant_fan.md L232"
SRC_DECIMAL = "合成の並び順メモ(架空)L5"
SRC_GOUSEI = "合成の並び順メモ(架空)L1"

ENUM_KUBUN = ["", "区分", "", "", "", "甲|乙|丙", SRC_KUBUN, ""]


def write_csv(path: Path, header: list[str], rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
    return path


def key(rank: int, column: str, kind: str, missing: str, source: str,
        direction: str = "昇順", swap: str = "") -> list[str]:
    return [str(rank), column, direction, kind, missing, "", source, swap]


def build(dest: Path | None = None) -> Path:
    d = HERE if dest is None else Path(dest)
    write_csv(d / "data_shikyuu.csv", DATA_HEADER, DATA_ROWS)

    write_csv(d / "sengen_mitsu.csv", DECL_HEADER, [
        key(1, "支給日", "日付", "後", SRC_HIDUKE, swap="逆順"),
        key(2, "区分", "宣言された列挙", "後", SRC_KUBUN),
        ENUM_KUBUN,
        key(3, "社員番号", "整数", "先", SRC_SHAIN),
    ])
    write_csv(d / "sengen_sokaku.csv", DECL_HEADER, [
        key(1, "支給日", "日付", "後", SRC_HIDUKE, swap="逆順"),
        key(2, "区分", "宣言された列挙", "後", SRC_KUBUN),
        ENUM_KUBUN,
    ])
    write_csv(d / "sengen_shain_seisuu.csv", DECL_HEADER, [
        key(1, "社員番号", "整数", "後", SRC_SHAIN, swap="逆順")])
    write_csv(d / "sengen_shain_codepoint.csv", DECL_HEADER, [
        key(1, "社員番号", "コードポイント列", "後", SRC_SHAIN, swap="逆順")])
    write_csv(d / "sengen_shain_kesson_saki.csv", DECL_HEADER, [
        key(1, "社員番号", "整数", "先", SRC_SHAIN, swap="逆順")])
    write_csv(d / "sengen_shain_kouzyun.csv", DECL_HEADER, [
        key(1, "社員番号", "整数", "後", SRC_SHAIN, direction="降順", swap="逆順")])
    write_csv(d / "sengen_kingaku_decimal.csv", DECL_HEADER, [
        key(1, "金額", "Decimal", "後", SRC_DECIMAL, swap="逆順")])
    write_csv(d / "sengen_kingaku_codepoint.csv", DECL_HEADER, [
        key(1, "金額", "コードポイント列", "後", SRC_KINGAKU, swap="逆順")])

    k = d / "kowashita"
    # 止まる理由コードを出す表(1 か所だけ崩す)
    write_csv(k / "sengen_0gyou.csv", DECL_HEADER, [])
    write_csv(k / "sengen_juufuku.csv", DECL_HEADER, [
        key(1, "支給日", "日付", "後", SRC_HIDUKE),
        key(1, "社員番号", "整数", "後", SRC_SHAIN)])
    write_csv(k / "sengen_shutten_nashi.csv", DECL_HEADER, [
        key(1, "社員番号", "整数", "後", "")])
    write_csv(k / "sengen_shurui_kuuran.csv", DECL_HEADER, [
        key(1, "社員番号", "", "後", SRC_SHAIN)])
    write_csv(k / "sengen_shurui_mitouroku.csv", DECL_HEADER, [
        key(1, "社員番号", "文字列", "後", SRC_SHAIN)])
    write_csv(k / "sengen_rettukyo_kouho_nashi.csv", DECL_HEADER, [
        key(1, "区分", "宣言された列挙", "後", SRC_KUBUN)])
    write_csv(k / "sengen_kesson_kuuran.csv", DECL_HEADER, [
        key(1, "社員番号", "整数", "", SRC_SHAIN)])
    write_csv(k / "sengen_sengen_ni_nai_retsu.csv", DECL_HEADER, [
        key(1, "社員番号", "整数", "後", SRC_SHAIN),
        ["", "等級", "", "", "", "A|B|C", SRC_GOUSEI, ""]])
    write_csv(k / "sengen_data_ni_nai_retsu.csv", DECL_HEADER, [
        key(1, "等級", "コードポイント列", "後", SRC_GOUSEI)])
    write_csv(k / "data_float.csv", DATA_HEADER,
              [["1.5" if i == 0 else r[0], *r[1:]] for i, r in enumerate(DATA_ROWS)])
    write_csv(k / "data_rettukyo_gai.csv", DATA_HEADER,
              [[*r[:2], "丁" if i == 0 else r[2], *r[3:]] for i, r in enumerate(DATA_ROWS)])

    # 「表として読めない」(終了コード 2)に落とす表。台帳の理由コードには混ぜない
    write_csv(k / "sengen_retsu_nashi.csv", DECL_HEADER[:-1], [
        ["1", "社員番号", "昇順", "整数", "後", "", SRC_SHAIN]])
    write_csv(k / "sengen_muki_kuuran.csv", DECL_HEADER, [
        key(1, "社員番号", "整数", "後", SRC_SHAIN, direction="")])
    write_csv(k / "sengen_kesson_mitouroku.csv", DECL_HEADER, [
        key(1, "社員番号", "整数", "中", SRC_SHAIN)])
    write_csv(k / "sengen_junni_hi_seisuu.csv", DECL_HEADER, [
        ["一", "社員番号", "昇順", "整数", "後", "", SRC_SHAIN, ""]])
    write_csv(k / "sengen_irekae_mitouroku.csv", DECL_HEADER, [
        key(1, "社員番号", "整数", "後", SRC_SHAIN, swap="乱数で混ぜる")])
    write_csv(k / "data_hidzuke_yomenai.csv", DATA_HEADER,
              [[*r[:3], "2026-13-45" if i == 0 else r[3], *r[4:]] for i, r in enumerate(DATA_ROWS)])
    write_csv(k / "data_suu_yomenai.csv", DATA_HEADER,
              [["未定" if i == 0 else r[0], *r[1:]] for i, r in enumerate(DATA_ROWS)])
    return d


if __name__ == "__main__":
    print(f"書いた: {build(Path(sys.argv[1]) if len(sys.argv) > 1 else None)}")
