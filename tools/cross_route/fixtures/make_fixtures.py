"""cross_route の合成 fixture を作る。**全て合成データ(架空)** で、実在の料率・限度額・最低賃金は入っていない。

作るもの:
    keiro_a_genpon.txt    経路 A の出典に見立てた合成テキスト(自前抽出の元)
    keiro_b_joryu.json    経路 B の出典に見立てた合成 JSON(別系統の表)
    keiro_b_kouhyou.txt   経路 B の出典に見立てた合成テキスト(別の公表物)
    route_a.csv           経路 A の行(13 行)
    route_b.csv           経路 B の行(14 行)

出典の列(source_sha256)は上の 3 ファイルの現物から hashlib で計算するので、表と出典は内部で噛み合う
(cross_route 自体は現物を読まない = source_pin の仕事。test_fixture_sha_matches_the_files が噛み合いを見る)。

key の和集合は 15 で、判定の内訳は agree 7 / disagree 1 / single_route 3 / incomparable 4 になる。
値はすべて架空だが、**詰まり方の形** は私の記録から取っている(別の制度を同じ名前で並べていた =
scope 不一致、適用開始日が原本に無い = scope 空欄、上流の表しか無い項目 = 片系統だけ)。
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

NAME_A = "自前抽出"
NAME_B = "別の経路"
CAPTURED = "2026-10-02T09:00:00+00:00"

COLUMNS = ["key", "value", "unit", "scope", "source_file", "source_sha256",
           "normalizer", "captured_at", "raw_text", "locator", "note"]

A_FILE = "keiro_a_genpon.txt"
B_JSON = "keiro_b_joryu.json"
B_TEXT = "keiro_b_kouhyou.txt"

# ---------------------------------------------------------------- 合成の出典ファイル

A_TEXT_LINES = [
    "合成(架空)の料率・限度額の原本に見立てたテキスト",
    "この見本は実在の公表物ではない。値も区分名もすべて架空である。",
    "",
    "料率 地域I   9.31%",
    "料率 地域II  10.07%",
    "料率 地域III 9.64%",
    "上限額 区分A １，３１０，０００円",
    "上限額 区分B 8,490円",
    "最低額 年1 2,301",
    "最低額 年2 2,418",
    "最低額 年3 2,570",
    "給付日数の適用開始日 2017年4月1日(原本に日付の記載が無いため仮置き)",
    "従前額の適用開始日 2025年4月1日(原本に日付の記載が無いため仮置き)",
    "支援金率(労使折半) 0.31%",
    "日額 区分C 7,294円",
    "改定率 年1 1.027",
]

B_JSON_DATA = {
    "_note": "合成(架空)の別系統の表に見立てた JSON。実在の公表物ではない。",
    "料率": {"地域I": "9.310", "地域II": "10.07", "地域III": "9.64"},
    "拠出金率_事業主のみ": "0.47",
    "最低賃金_地域I": "1,204",
    "業種料率_業種A": "0.35%",
}

B_TEXT_LINES = [
    "合成(架空)の別の公表物に見立てたテキスト",
    "この見本は実在の公表物ではない。値も区分名もすべて架空である。",
    "",
    "上限額 区分A 1310000",
    "上限額 区分B 8,480円",
    "最低額 年1 2301",
    "最低額 年2 2418",
    "最低額 年3 2570",
    "給付日数の適用開始日 2017-04-01",
    "日額 区分C 7294",
    "改定率 年1 1.027",
]


def write_sources(d: Path) -> dict:
    """合成の出典 3 ファイルを書き、ファイル名 -> sha256 を返す。"""
    files = {
        A_FILE: ("\n".join(A_TEXT_LINES) + "\n").encode("utf-8"),
        B_JSON: (json.dumps(B_JSON_DATA, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        B_TEXT: ("\n".join(B_TEXT_LINES) + "\n").encode("utf-8"),
    }
    for name, blob in files.items():
        (d / name).write_bytes(blob)
    return {name: hashlib.sha256(blob).hexdigest() for name, blob in files.items()}


# ---------------------------------------------------------------- 経路の行

def _row(**kw: str) -> dict:
    row = {c: "" for c in COLUMNS}
    row.update({"captured_at": CAPTURED, "note": "合成(架空)"}, **kw)
    return row


def rows_a(sha: dict) -> list:
    """経路 A(自前抽出)の 13 行。"""
    f, s = A_FILE, sha[A_FILE]
    common = {"source_file": f, "source_sha256": s}
    return [
        _row(key="料率_地域I", value="9.31%", unit="%", scope="地域I・労使折半",
             normalizer="パーセント+桁そろえ", raw_text="9.31%", locator="4", **common),
        _row(key="料率_地域II", value="10.07%", unit="%", scope="地域II・労使折半",
             normalizer="パーセント+桁そろえ", raw_text="10.07%", locator="5", **common),
        _row(key="料率_地域III", value="9.64%", unit="%", scope="地域III・労使折半",
             normalizer="パーセント+桁そろえ", raw_text="9.64%", locator="6", **common),
        _row(key="上限額_区分A", value="１，３１０，０００円", unit="円", scope="区分A・月額",
             normalizer="全角半角+カンマ除去+円", raw_text="１，３１０，０００円", locator="7", **common),
        _row(key="上限額_区分B", value="8,490円", unit="円", scope="区分B・月額",
             normalizer="カンマ除去+円", raw_text="8,490円", locator="8", **common),
        _row(key="最低額_年1", value="2,301", unit="円/日", scope="全区分・計算から",
             normalizer="カンマ除去", raw_text="2,301", locator="9", **common),
        _row(key="最低額_年2", value="2,418", unit="円/日", scope="全区分・計算から",
             normalizer="カンマ除去", raw_text="2,418", locator="10", **common),
        _row(key="最低額_年3", value="2,570", unit="円/日", scope="全区分・計算から",
             normalizer="カンマ除去", raw_text="2,570", locator="11", **common),
        _row(key="適用開始日_給付日数", value="2017年4月1日", unit="日付", scope="全区分・仮置き",
             normalizer="日付", raw_text="2017年4月1日", locator="12",
             note="合成(架空)。原本に日付の記載が無い", **common),
        _row(key="適用開始日_従前額", value="2025年4月1日", unit="日付", scope="全区分・仮置き",
             normalizer="日付", raw_text="2025年4月1日", locator="13",
             note="合成(架空)。照合相手の経路が無い", **common),
        _row(key="支援金率", value="0.31%", unit="%", scope="労使折半",
             normalizer="パーセント+桁そろえ", raw_text="0.31%", locator="14", **common),
        _row(key="日額_区分C", value="7,294円", unit="円", scope="区分C・日額",
             normalizer="カンマ除去+円", raw_text="7,294円", locator="15", **common),
        _row(key="改定率_年1", value="1.027", unit="倍", scope="全区分",
             normalizer="", raw_text="1.027", locator="16",
             note="合成(架空)。正規化の名前を書いていない行", **common),
    ]


def rows_b(sha: dict) -> list:
    """経路 B(別の経路)の 14 行。"""
    j = {"source_file": B_JSON, "source_sha256": sha[B_JSON]}
    t = {"source_file": B_TEXT, "source_sha256": sha[B_TEXT]}
    return [
        _row(key="料率_地域I", value="9.310", unit="%", scope="地域I・労使折半",
             normalizer="桁そろえ", raw_text="9.310", locator="料率.地域I", **j),
        _row(key="料率_地域II", value="10.07", unit="%", scope="地域II・労使折半",
             normalizer="桁そろえ", raw_text="10.07", locator="料率.地域II", **j),
        _row(key="料率_地域III", value="9.64", unit="%", scope="地域III・労使折半",
             normalizer="桁そろえ", raw_text="9.64", locator="料率.地域III", **j),
        _row(key="上限額_区分A", value="1310000", unit="円", scope="区分A・月額",
             normalizer="そのまま", raw_text="1310000", locator="4", **t),
        _row(key="上限額_区分B", value="8,480円", unit="円", scope="区分B・月額",
             normalizer="カンマ除去+円", raw_text="8,480円", locator="5", **t),
        _row(key="最低額_年1", value="2301", unit="円/日", scope="全区分・計算から",
             normalizer="そのまま", raw_text="2301", locator="6", **t),
        _row(key="最低額_年2", value="2418", unit="円/日", scope="全区分・計算から",
             normalizer="そのまま", raw_text="2418", locator="7", **t),
        _row(key="最低額_年3", value="2570", unit="円/日", scope="全区分・計算から",
             normalizer="そのまま", raw_text="2570", locator="8", **t),
        _row(key="適用開始日_給付日数", value="2017-04-01", unit="日付", scope="",
             normalizer="日付", raw_text="2017-04-01", locator="9",
             note="合成(架空)。この経路は何を指す日付か宣言していない", **t),
        _row(key="支援金率", value="0.47%", unit="%", scope="事業主のみ",
             normalizer="パーセント+桁そろえ", raw_text="0.47", locator="拠出金率_事業主のみ",
             note="合成(架空)。同じ名前で別の負担区分の数字", **j),
        _row(key="日額_区分C", value="7294", unit="円/日", scope="区分C・日額",
             normalizer="そのまま", raw_text="7294", locator="10",
             note="合成(架空)。単位の宣言が A と違う", **t),
        _row(key="改定率_年1", value="1.027", unit="倍", scope="全区分",
             normalizer="桁そろえ", raw_text="1.027", locator="11", **t),
        _row(key="最低賃金_地域I", value="1,204", unit="円/時", scope="地域I",
             normalizer="カンマ除去", raw_text="1,204", locator="最低賃金_地域I",
             note="合成(架空)。照合相手の経路が無い", **j),
        _row(key="業種料率_業種A", value="0.35%", unit="%", scope="業種A・事業主のみ",
             normalizer="パーセント+桁そろえ", raw_text="0.35%", locator="業種料率_業種A",
             note="合成(架空)。照合相手の経路が無い", **j),
    ]


def write_route(path: Path, rows: list) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)


def build(d: Path) -> dict:
    """合成の出典 3 ファイルと経路 2 本の CSV を d に作り、(sha, rows_a, rows_b) を返す。"""
    d.mkdir(parents=True, exist_ok=True)
    sha = write_sources(d)
    ra, rb = rows_a(sha), rows_b(sha)
    write_route(d / "route_a.csv", ra)
    write_route(d / "route_b.csv", rb)
    return {"sha": sha, "rows_a": ra, "rows_b": rb}


if __name__ == "__main__":
    out = build(Path(__file__).resolve().parent)
    print(f"wrote {len(out['rows_a'])} rows (route_a) / {len(out['rows_b'])} rows (route_b)")
    for name, s in out["sha"].items():
        print(f"  {name}  sha256:{s}")
