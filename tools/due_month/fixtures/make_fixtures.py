"""fixture を作り直す。gousei / kowashita は架空。suuhyo の台帳・対応・比べ方は、私の記録から人が写した登録表。

suuhyo/rows.csv だけは utsusu.py が数表の JSON から写す(このファイルは作らない)。
"""
from __future__ import annotations

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROWS = ["rule", "valid_from", "予定", "出どころ", "元の行数", "出典"]
LEDGERS = ["台帳id", "種別", "数表id", "予定", "出典"]
LINKS = ["出どころ", "台帳id", "出典"]
COMPARE = ["比べ方", "出典"]


def put(path: Path, head: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(head)
        w.writerows(rows)


# ---- gousei: 架空の料金表 8 rule ----
G = "架空の数表"
put(HERE / "gousei" / "rows.csv", ROWS, [
    ["送料表_甲", "2024-04-01", "2026-04-01", "写し_甲", "3", f"{G} 行 1"],
    ["送料表_甲", "2025-04-01", "2026-04-01", "写し_甲", "3", f"{G} 行 4"],
    ["送料表_乙", "2024-10-01", "2026-04-01", "写し_乙", "1", f"{G} 行 7"],
    ["送料表_乙", "2025-10-01", "2026-04-01", "写し_乙", "1", f"{G} 行 8"],
    ["単価表_丙", "2023-04-01", "2025-04-01", "写し_甲", "2", f"{G} 行 9"],
    ["単価表_丙", "2024-07-01", "2025-04-01", "写し_甲", "2", f"{G} 行 11"],
    ["等級表_丁", "2020-09-01", "2027-09-01", "写し_丁", "1", f"{G} 行 13"],
    ["等級表_丁", "2027-09-01", "2027-09-01", "写し_丁", "1", f"{G} 行 14"],
    ["料金表_戊", "2025-01-01", "2024-06-01", "写し_甲", "1", f"{G} 行 15"],
    ["税率表_己", "2019-10-01", "", "写し_己", "4", f"{G} 行 16"],
    ["税率表_庚", "2014-04-01", "", "", "1", f"{G} 行 20"],
    ["手当表_辛", "2024-04-01", "2026-04-01", "写し_甲", "1", f"{G} 行 21"],
    ["手当表_辛", "2025-04-01", "2026-07-01", "写し_辛", "1", f"{G} 行 22"],
])
put(HERE / "gousei" / "ledgers.csv", LEDGERS, [
    ["自前:送料", "自前", "送料", "2026-10-01", "架空の台帳 行 3"],
    ["上流:共通", "上流", "共通", "2026-04-01", "架空の上流の台帳 行 5"],
    ["自前:税率", "自前", "税率", "2026-04-01", "架空の台帳 行 9"],
    ["上流:等級", "上流", "等級", "2027-09-01", "架空の上流の台帳 行 12"],
])
put(HERE / "gousei" / "links.csv", LINKS, [
    ["写し_甲", "上流:共通", "架空の写しの手順 行 2"],
    ["写し_乙", "上流:共通", "架空の写しの手順 行 6"],
    ["写し_乙", "自前:送料", "架空の台帳 行 2"],
    ["写し_己", "自前:税率", "架空の台帳 行 8"],
    ["写し_丁", "上流:等級", "架空の写しの手順 行 10"],
])
put(HERE / "gousei" / "compare.csv", COMPARE, [["どれかの行", "架空の決めごと 行 1"]])

# ---- kowashita: 別枠 6 つに 1 件以上ずつ ----
put(HERE / "kowashita" / "rows.csv", ROWS, [
    ["送料表_甲", "2024-04-01", "来年の 4 月", "写し_甲", "1", f"{G} 行 1"],        # 日付の形でない予定
    ["", "2024-04-01", "2026-04-01", "写し_甲", "1", f"{G} 行 2"],                  # rule が空
    ["送料表_乙", "2024-10-01", "2026-04-01", "写し_乙", "1", ""],                  # 出典が空
    ["単価表_丙", "2023-04-01", "2025-04-01", "写し_甲", "1", f"{G} 行 4"],
    ["単価表_丙", "2023-04-01", "2025-04-01", "写し_甲", "1", f"{G} 行 5"],         # 同じ (rule, valid_from, 出どころ)
    ["手当表_辛", "2024-04-01", "2026-04-01", "写し_甲", "1", f"{G} 行 6"],         # 比べ方が別枠なので A か B に置けない
    ["料金表_戊", "2025-01-01", "2024-06-01", "写し_甲", "1", f"{G} 行 7"],         # C は比べ方に依らない
    ["税率表_庚", "2014-04-01", "", "", "1", f"{G} 行 8"],                          # D も比べ方に依らない
])
put(HERE / "kowashita" / "ledgers.csv", LEDGERS, [["上流:共通", "上流", "共通", "2026-04-01", "架空の上流の台帳 行 5"]])
put(HERE / "kowashita" / "links.csv", LINKS, [
    ["写し_甲", "上流:共通", "架空の写しの手順 行 2"],
    ["写し_乙", "上流:年金", "架空の写しの手順 行 6"],                               # 台帳の表に無い id
])
put(HERE / "kowashita" / "compare.csv", COMPARE, [["近い行", "架空の決めごと 行 1"]])   # 2 つの値以外

# ---- suuhyo: 私の記録から写した台帳・対応・比べ方(行の表は utsusu.py) ----
M, F, U = "sources_manifest.json", "freshness.json", "unify.py"
put(HERE / "suuhyo" / "ledgers.csv", LEDGERS, [
    ["自前:kyoukaikenpo", "自前", "kyoukaikenpo", "2027-03-01", f"{M} L11"],
    ["自前:koyou_kyufu", "自前", "koyou_kyufu", "2027-08-01", f"{M} L18"],
    ["自前:nenkin", "自前", "nenkin", "2027-04-01", f"{M} L33"],
    ["上流:social_insurance", "上流", "social_insurance", "2027-03-01", f"{F} L8"],
    ["上流:employment_insurance", "上流", "employment_insurance", "2027-04-01", f"{F} L18"],
    ["上流:minimum_wage", "上流", "minimum_wage", "2026-10-01", f"{F} L29"],
    ["上流:holidays", "上流", "holidays", "2027-02-01", f"{F} L40"],
    ["上流:consumption_tax", "上流", "consumption_tax", "", f"{F} L50(null)"],
    ["上流:corporate_number", "上流", "corporate_number", "", f"{F} L60(null)"],
    ["上流:pension_grade_table", "上流", "pension_grade_table", "2027-09-01", f"{F} L70"],
])
put(HERE / "suuhyo" / "links.csv", LINKS, [
    ["extract_kyoukaikenpo.py", "自前:kyoukaikenpo", f"{M} L9(extractor の欄が同じ字)"],
    ["extract_kyoukaikenpo.py", "上流:social_insurance", f"{U} L90"],
    ["extract_koyou.py", "自前:koyou_kyufu", f"{M} L16(extractor の欄が同じ字)"],
    ["extract_koyou.py", "上流:employment_insurance", f"{U} L171"],
    ["extract_nenkin.py", "自前:nenkin", f"{M} L31(extractor の欄が同じ字)"],
    ["extract_nenkin.py", "上流:pension", f"{U} L204"],
    ["厚生労働省のPDFから手入力", "上流:employment_insurance", f"{U} L131"],
    ["scripts/extract-minimum-wage.py", "上流:minimum_wage", f"{U} L142"],
    ["国税庁タックスアンサーから手入力", "上流:consumption_tax", f"{U} L155"],
    ["scripts/extract-insurance.py(等級は協会けんぽの保険料額表から)", "上流:pension_grade_table", f"{U} L116"],
])
put(HERE / "suuhyo" / "compare.csv", COMPARE, [["どれかの行", "私の決めごと(この記事のために登録)"]])
put(HERE / "suuhyo" / "compare_last.csv", COMPARE, [["最後の行", "私の決めごと(比べ方を替えた版)"]])
