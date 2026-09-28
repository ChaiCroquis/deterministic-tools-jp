"""asof_table の fixture を作る。全て合成データ(地域名・料率・出典名は架空、実在の値は 1 つも入れていない)。

    python -X utf8 make_fixtures.py

出力:
    ryouritsu.csv           不備の無い表(44 行)。日付 1 軸で壊れる 4 点のうち 3 点を含む形にしてある
    ryouritsu_fuseigou.csv  わざと壊した表(validate の一覧を見るため)
"""
from __future__ import annotations

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent

COLUMNS = ["key", "basis", "valid_from", "valid_to", "known_from", "known_to", "known_quality",
           "priority", "value", "source", "sel_地域", "sel_生年月日帯"]

# 合成の地域名(実在の都道府県ではない)
AREAS = [f"地域{c}" for c in "ABCDEFGHIJKL"]

# 保険料率_甲: 年度ごとに改定され、公表は施行の前月(= 遡って適用されるわけではないが、公表と施行がずれる)
KOU_PERIODS = [
    ("2024-03-01", "2025-03-01", "2024-02-01", "合成の料率表 2024 年度版(架空)"),
    ("2025-03-01", "2026-03-01", "2025-02-05", "合成の料率表 2025 年度版(架空)"),
    ("2026-03-01", "",           "2026-02-10", "合成の料率表 2026 年度版(架空)"),
]

# 保険料率_乙: 基準日が甲と違う(賃金の締切日で引く)。公表日は記録が無く valid_from で仮置きしてある
OTSU_PERIODS = [
    ("2024-04-01", "2025-04-01", "0.60", "合成の年度通知 2024(架空)"),
    ("2025-04-01", "2026-04-01", "0.55", "合成の年度通知 2025(架空)"),
    ("2026-04-01", "",           "0.50", "合成の年度通知 2026(架空)"),
]


def rows_clean() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for p, (vf, vt, kf, src) in enumerate(KOU_PERIODS):
        for i, area in enumerate(AREAS):
            rows.append({"key": "保険料率_甲", "basis": "対象月初日", "valid_from": vf, "valid_to": vt,
                         "known_from": kf, "known_to": "", "known_quality": "実値", "priority": "0",
                         "value": f"{9.50 + 0.05 * i + 0.10 * p:.2f}", "source": src,
                         "sel_地域": area, "sel_生年月日帯": ""})
    for vf, vt, val, src in OTSU_PERIODS:
        rows.append({"key": "保険料率_乙", "basis": "賃金締切日", "valid_from": vf, "valid_to": vt,
                     "known_from": vf, "known_to": "", "known_quality": "仮置き", "priority": "0",
                     "value": val, "source": src, "sel_地域": "", "sel_生年月日帯": ""})
    # 継続給付_支給率: 本則が改定され、旧い帯だけ経過措置で据え置かれる(= 対象を限定する改正)
    rows.append({"key": "継続給付_支給率", "basis": "対象月初日", "valid_from": "2023-04-01",
                 "valid_to": "2025-04-01", "known_from": "2023-01-20", "known_to": "",
                 "known_quality": "実値", "priority": "0", "value": "15",
                 "source": "合成の改正通知 2023(架空)", "sel_地域": "", "sel_生年月日帯": ""})
    rows.append({"key": "継続給付_支給率", "basis": "対象月初日", "valid_from": "2025-04-01",
                 "valid_to": "", "known_from": "2024-06-10", "known_to": "",
                 "known_quality": "実値", "priority": "0", "value": "10",
                 "source": "合成の改正通知 2024(架空)", "sel_地域": "", "sel_生年月日帯": ""})
    rows.append({"key": "継続給付_支給率", "basis": "対象月初日", "valid_from": "2025-04-01",
                 "valid_to": "2030-04-01", "known_from": "2024-06-10", "known_to": "",
                 "known_quality": "実値", "priority": "10", "value": "15",
                 "source": "合成の改正通知 2024 附則(架空)", "sel_地域": "", "sel_生年月日帯": "1960年度以前"})
    # 適用要件_丁: 施行日が政令待ちの行(知識としては持つが、引き当てには決して当たらない)
    rows.append({"key": "適用要件_丁", "basis": "資格取得日", "valid_from": "2024-10-01", "valid_to": "",
                 "known_from": "2024-05-01", "known_to": "", "known_quality": "実値", "priority": "0",
                 "value": "51", "source": "合成の適用要件表(架空)", "sel_地域": "", "sel_生年月日帯": ""})
    rows.append({"key": "適用要件_丁", "basis": "資格取得日", "valid_from": "", "valid_to": "",
                 "known_from": "2026-06-13", "known_to": "", "known_quality": "実値", "priority": "0",
                 "value": "撤廃", "source": "合成の改正法(架空、施行日は政令)", "sel_地域": "", "sel_生年月日帯": ""})
    return rows


def rows_broken() -> list[dict[str, str]]:
    """validate が何を拾うかを見るための、わざと壊した表。"""
    def r(**over: str) -> dict[str, str]:
        base = {c: "" for c in COLUMNS}
        base.update({"basis": "対象月初日", "known_from": "2025-01-01", "known_quality": "実値",
                     "priority": "0", "source": "合成(架空)"})
        base.update(over)
        return base
    return [
        r(key="重なる表", valid_from="2025-04-01", valid_to="2026-04-01", value="1"),
        r(key="重なる表", valid_from="2026-01-01", valid_to="2027-01-01", value="2"),
        r(key="穴のある表", valid_from="2024-04-01", valid_to="2025-04-01", value="3"),
        r(key="穴のある表", valid_from="2025-10-01", valid_to="2026-10-01", value="4"),
        r(key="逆さの表", valid_from="2026-04-01", valid_to="2025-04-01", value="5"),
        r(key="知識が逆さの表", valid_from="2025-04-01", valid_to="",
          known_from="2025-06-01", known_to="2025-03-01", value="6"),
        r(key="基準日が揺れる表", basis="対象月初日", valid_from="2024-04-01", valid_to="2025-04-01", value="7"),
        r(key="基準日が揺れる表", basis="賃金締切日", valid_from="2025-04-01", valid_to="", value="8"),
        r(key="順位が登録外の表", valid_from="2025-04-01", valid_to="", priority="5", value="9"),
    ]


def write(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {path.name}: {len(rows)} 行")


def main() -> None:
    write(HERE / "ryouritsu.csv", rows_clean())
    write(HERE / "ryouritsu_fuseigou.csv", rows_broken())


if __name__ == "__main__":
    main()
