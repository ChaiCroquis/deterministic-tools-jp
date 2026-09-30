"""update_ledger の fixture を作る。全て合成データ(地域名・値・出典名は架空、実在の値は 1 つも入れていない)。

    python -X utf8 make_fixtures.py

出力(いずれも asof_table と同じ列の行の表):
    hyou_zenkai.csv         前回の表(43 行、不備なし)
    hyou_konkai.csv         今回の表(47 行)。差分 6 種が全部出るように書き換えてある
    hyou_kasanari.csv       有効期間が重なる表(44 行)
    hyou_ana.csv            期間に穴がある表(43 行)
    hyou_kyuhen.csv         行数が急に減った表(31 行)
    hyou_retsu_tarinai.csv  source 列が無い表(43 行)
"""
from __future__ import annotations

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent

COLUMNS = ["key", "basis", "valid_from", "valid_to", "known_from", "known_to", "known_quality",
           "priority", "value", "source", "sel_地域"]

# 合成の地域名(実在の都道府県ではない)
AREAS = [f"地域{c}" for c in "ABCDEFGHIJKL"]

# 料率_甲: 年度ごとに改定される。公表は施行の前月
KOU = [
    ("2024-03-01", "2025-03-01", "2024-02-01", "合成の料率表 2024 年度版(架空)"),
    ("2025-03-01", "2026-03-01", "2025-02-05", "合成の料率表 2025 年度版(架空)"),
    ("2026-03-01", "",           "2026-02-10", "合成の料率表 2026 年度版(架空)"),
]

# 上限額_乙: 対象を持たない 1 本の履歴
OTSU = [
    ("2023-04-01", "2024-04-01", "2023-02-01", "8400", "合成の上限額通知 2023(架空)"),
    ("2024-04-01", "2025-04-01", "2024-02-01", "8600", "合成の上限額通知 2024(架空)"),
    ("2025-04-01", "2026-04-01", "2025-02-01", "8800", "合成の上限額通知 2025(架空)"),
    ("2026-04-01", "",           "2026-02-01", "9000", "合成の上限額通知 2026(架空)"),
]


def _row(**over: str) -> dict:
    base = {c: "" for c in COLUMNS}
    base.update({"basis": "対象月初日", "known_quality": "実値", "priority": "0"})
    base.update(over)
    return base


def kou_value(area_index: int, period: int) -> str:
    return f"{9.50 + 0.05 * area_index + 0.10 * period:.2f}"


def rows_zenkai() -> list:
    """前回の表。料率_甲 36 行 + 上限額_乙 4 行 + 支給率_丙 3 行 = 43 行。"""
    rows: list = []
    for p, (vf, vt, kf, src) in enumerate(KOU):
        for i, area in enumerate(AREAS):
            rows.append(_row(key="料率_甲", valid_from=vf, valid_to=vt, known_from=kf,
                             value=kou_value(i, p), source=src, sel_地域=area))
    for vf, vt, kf, val, src in OTSU:
        rows.append(_row(key="上限額_乙", basis="請求日", valid_from=vf, valid_to=vt,
                         known_from=kf, value=val, source=src))
    rows.append(_row(key="支給率_丙", valid_from="2023-04-01", valid_to="2025-04-01",
                     known_from="2023-01-20", value="15", source="合成の改正通知 2023(架空)"))
    rows.append(_row(key="支給率_丙", valid_from="2025-04-01", valid_to="",
                     known_from="2024-06-10", value="10", source="合成の改正通知 2024(架空)"))
    rows.append(_row(key="支給率_丙", valid_from="2025-04-01", valid_to="2030-04-01",
                     known_from="2024-06-10", priority="10", value="15",
                     source="合成の改正通知 2024 附則(架空)"))
    return rows


def rows_konkai() -> list:
    """今回の表。差分 6 種が全部出て、2 行は 2 つの側面が同時に動く形にしてある(43 + 6 - 2 = 47 行)。"""
    rows = [dict(r) for r in rows_zenkai()]

    def find(key: str, valid_from: str, area: str = "", priority: str = "0") -> dict:
        for r in rows:
            if r["key"] == key and r["valid_from"] == valid_from and r["sel_地域"] == area \
                    and r["priority"] == priority:
                return r
        raise KeyError((key, valid_from, area, priority))

    # (a) 新年度 = 開いている行を閉じて(有効期間の変更 5)新しい行を足す(追加 5)
    for i, area in enumerate(AREAS[:5]):
        find("料率_甲", "2026-03-01", area)["valid_to"] = "2027-03-01"
        rows.append(_row(key="料率_甲", valid_from="2027-03-01", valid_to="", known_from="2027-02-10",
                         value=f"{9.50 + 0.05 * i + 0.30:.2f}",
                         source="合成の料率表 2027 年度版(架空)", sel_地域=area))
    # (b) 値だけの訂正(値の変更 3)
    for i, area in enumerate(AREAS[5:8], start=5):
        find("料率_甲", "2026-03-01", area)["value"] = f"{9.50 + 0.05 * i + 0.21:.2f}"
    # (c) 出典欄だけの書き換え(出典欄の変更 4)
    for area in AREAS[8:12]:
        find("料率_甲", "2025-03-01", area)["source"] = "合成の料率表 2025 年度版 訂正(架空)"
    # (d) 値と出典が同時に動く行(値の変更 2 / 出典欄の変更 2 / 動いた行としては 2)
    for i, area in enumerate(AREAS[8:10], start=8):
        r = find("料率_甲", "2024-03-01", area)
        r["value"] = f"{9.50 + 0.05 * i + 0.02:.2f}"
        r["source"] = "合成の料率表 2024 年度版 訂正(架空)"
    # (e) 公表側の差し替え = 前の行に known_to を入れ(公表時点の変更 1)、同じ期間の新しい行を足す(追加 1)
    find("上限額_乙", "2025-04-01")["known_to"] = "2026-01-15"
    rows.append(_row(key="上限額_乙", basis="請求日", valid_from="2025-04-01", valid_to="2026-04-01",
                     known_from="2026-01-15", value="8810",
                     source="合成の上限額通知 2025 訂正(架空)"))
    # (f) 削除 2 = 最古の上限額と、期限切れの経過措置
    rows.remove(find("上限額_乙", "2023-04-01"))
    rows.remove(find("支給率_丙", "2025-04-01", priority="10"))
    return rows


def rows_bumped(n: int) -> list:
    """今回の表の 1 行だけ値を変えた表。n が違えば必ず 1 行だけ違う(運用の測定で使う)。"""
    rows = [dict(r) for r in rows_konkai()]
    rows[0]["value"] = f"{9.50 + 0.01 * n:.2f}"
    return rows


def rows_kasanari() -> list:
    """有効期間が重なる表。地域A の 2 つの期にまたがる行を 1 本足す。"""
    rows = [dict(r) for r in rows_zenkai()]
    rows.append(_row(key="料率_甲", valid_from="2025-06-01", valid_to="2026-06-01",
                     known_from="2025-02-05", value="9.99",
                     source="合成の料率表 年度途中改定(架空)", sel_地域="地域A"))
    return rows


def rows_ana() -> list:
    """期間に穴がある表。上限額_乙 の 1 行の開始日を半年後ろへずらす。"""
    rows = [dict(r) for r in rows_zenkai()]
    for r in rows:
        if r["key"] == "上限額_乙" and r["valid_from"] == "2025-04-01":
            r["valid_from"] = "2025-10-01"
    return rows


def rows_kyuhen() -> list:
    """行数が急に減った表。取得に失敗して 1 年度ぶんが落ちた形(43 → 31 行)。"""
    return [dict(r) for r in rows_zenkai()
            if not (r["key"] == "料率_甲" and r["valid_from"] == "2024-03-01")]


def rows_retsu_tarinai() -> list:
    """source 列が無い表。"""
    return [{c: v for c, v in r.items() if c != "source"} for r in rows_zenkai()]


def write(path: Path, rows: list) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {path.name}: {len(rows)} 行")


def main() -> None:
    write(HERE / "hyou_zenkai.csv", rows_zenkai())
    write(HERE / "hyou_konkai.csv", rows_konkai())
    write(HERE / "hyou_kasanari.csv", rows_kasanari())
    write(HERE / "hyou_ana.csv", rows_ana())
    write(HERE / "hyou_kyuhen.csv", rows_kyuhen())
    write(HERE / "hyou_retsu_tarinai.csv", rows_retsu_tarinai())


if __name__ == "__main__":
    main()
