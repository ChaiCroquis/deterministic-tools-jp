"""formula_table の fixture を作る。全て合成データ(率・単価・出典名は架空、実在の値は 1 つも入れていない)。

    python -X utf8 make_fixtures.py

出力:
    keisan.csv           不備の無い式の表。数式の改正・公表時点・丸めの指定を含む
    atai.csv             式が `value:` で引く値の表(式の版と同じ引き方で 1 行に決まる)
    keisan_fuseigou.csv  わざと壊した式の表(validate の一覧を見るため)
"""
from __future__ import annotations

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent

F_COLUMNS = ["id", "expr", "inputs", "rounding", "valid_from", "valid_to",
             "known_from", "known_to", "known_quality", "priority", "source"]
V_COLUMNS = ["key", "value", "valid_from", "valid_to",
             "known_from", "known_to", "known_quality", "priority", "source"]

# 測定に使う合成の報酬月額(架空。実在の標準報酬月額の等級表ではない)
HOUSHUU = [110000, 123000, 137000, 145000, 152000, 168000, 174000, 189000, 196000, 203000,
           217000, 225000, 238000, 246000, 251000, 264000, 279000, 283000, 297000, 305000]

# 測定に使う合成の料率(%、架空)
RITSU = ["8.13", "9.27", "9.50", "10.04", "10.71", "11.38"]


def f(id: str, expr: str, inputs: str, rounding: str, valid_from: str, valid_to: str,
      known_from: str, source: str, known_quality: str = "実値", priority: str = "0") -> dict[str, str]:
    return {"id": id, "expr": expr, "inputs": inputs, "rounding": rounding,
            "valid_from": valid_from, "valid_to": valid_to, "known_from": known_from,
            "known_to": "", "known_quality": known_quality, "priority": priority, "source": source}


def v(key: str, value: str, valid_from: str, valid_to: str, known_from: str,
      source: str, known_quality: str = "実値", priority: str = "0") -> dict[str, str]:
    return {"key": key, "value": value, "valid_from": valid_from, "valid_to": valid_to,
            "known_from": known_from, "known_to": "", "known_quality": known_quality,
            "priority": priority, "source": source}


def formulas_clean() -> list[dict[str, str]]:
    return [
        # 数式そのものの改正。2026-04-01 から加算率が式に入る(値の履歴では表せない改正)
        f("折半額", "報酬 * 料率 / 200",
          "報酬=case:報酬月額;料率=value:合成料率_甲", "50銭以下切捨て",
          "2024-03-01", "2026-04-01", "2024-02-01", "合成の端数処理メモ 2024(架空)"),
        f("折半額", "報酬 * (料率 + 加算率) / 200",
          "報酬=case:報酬月額;料率=value:合成料率_甲;加算率=value:合成加算率", "50銭以下切捨て",
          "2026-04-01", "", "2026-02-10", "合成の改正通知 2026(架空)"),
        # 別の丸めの項目。1 円未満を切り捨てる
        f("給付日額", "賃金日額 * 給付率 / 100",
          "賃金日額=case:賃金日額;給付率=value:合成給付率", "1円未満切捨て",
          "2024-08-01", "", "2024-07-01", "合成の給付額メモ(架空)"),
        # 式が式を引く。年額は丸めずに次へ渡し、月額の側で円未満を四捨五入する
        f("年額", "単価 * 乗率 * 月数",
          "単価=value:合成単価;乗率=value:合成乗率;月数=case:被保険者月数", "丸めない",
          "2025-04-01", "", "2025-01-27", "合成の年額メモ(架空)"),
        f("月額", "年額 / 12", "年額=formula:年額", "円未満四捨五入",
          "2025-04-01", "", "2025-01-27", "合成の年額メモ(架空)"),
        # 数式改正の 2 つめ。条件が 1 つ増える(v1 は月末在籍だけ、v2 は日数の条件が足される)
        f("免除判定", "1 if 在籍 > 0 else 0", "在籍=case:月末在籍", "丸めない",
          "2022-04-01", "2022-10-01", "2022-01-15", "合成の免除要件 v1(架空)"),
        f("免除判定", "1 if 在籍 > 0 else (1 if 日数 >= 14 else 0)",
          "在籍=case:月末在籍;日数=case:休業日数", "丸めない",
          "2022-10-01", "", "2022-08-20", "合成の免除要件 v2(架空)"),
        # 施行日が政令待ちの行。知識としては持つが、評価には決して当たらない
        f("免除判定", "1 if 在籍 > 0 else (1 if 日数 >= 10 else 0)",
          "在籍=case:月末在籍;日数=case:休業日数", "丸めない",
          "", "", "2026-06-13", "合成の改正法(架空、施行日は政令)"),
        # 測定用。同じ式・同じ入力を、丸めの名前だけ変えて 3 本置く
        f("測定_50銭以下切捨て", "報酬 * 料率 / 200", "報酬=case:報酬月額;料率=case:料率",
          "50銭以下切捨て", "2024-03-01", "", "2024-02-01", "合成の測定用(架空)"),
        f("測定_1円未満切捨て", "報酬 * 料率 / 200", "報酬=case:報酬月額;料率=case:料率",
          "1円未満切捨て", "2024-03-01", "", "2024-02-01", "合成の測定用(架空)"),
        f("測定_円未満四捨五入", "報酬 * 料率 / 200", "報酬=case:報酬月額;料率=case:料率",
          "円未満四捨五入", "2024-03-01", "", "2024-02-01", "合成の測定用(架空)"),
        f("測定_丸めない", "報酬 * 料率 / 200", "報酬=case:報酬月額;料率=case:料率",
          "丸めない", "2024-03-01", "", "2024-02-01", "合成の測定用(架空)"),
    ]


def values_clean() -> list[dict[str, str]]:
    return [
        v("合成料率_甲", "9.85", "2024-03-01", "2025-03-01", "2024-02-01", "合成の料率表 2024 年度版(架空)"),
        v("合成料率_甲", "10.02", "2025-03-01", "2026-03-01", "2025-02-05", "合成の料率表 2025 年度版(架空)"),
        v("合成料率_甲", "10.35", "2026-03-01", "", "2026-02-10", "合成の料率表 2026 年度版(架空)"),
        v("合成加算率", "0.30", "2026-04-01", "", "2026-02-10", "合成の改正通知 2026(架空)"),
        v("合成給付率", "63", "2024-08-01", "", "2024-07-01", "合成の給付率表(架空)"),
        v("合成単価", "1703", "2025-04-01", "", "2025-01-27", "合成の単価表(架空)"),
        v("合成乗率", "1.008", "2025-04-01", "", "2025-01-27", "合成の乗率表(架空)"),
    ]


def formulas_broken() -> list[dict[str, str]]:
    """validate が何を拾うかを見るための、わざと壊した表。"""
    return [
        f("丸めが無い式", "報酬 * 2", "報酬=case:報酬月額", "",
          "2025-04-01", "", "2025-01-01", "合成(架空)"),
        f("知らない丸めの式", "報酬 * 2", "報酬=case:報酬月額", "銀行丸め",
          "2025-04-01", "", "2025-01-01", "合成(架空)"),
        f("属性を触る式", "報酬.real", "報酬=case:報酬月額", "丸めない",
          "2025-04-01", "", "2025-01-01", "合成(架空)"),
        f("添字を使う式", "報酬[0]", "報酬=case:報酬月額", "丸めない",
          "2025-04-01", "", "2025-01-01", "合成(架空)"),
        f("内包表記の式", "min(x for x in 報酬)", "報酬=case:報酬月額", "丸めない",
          "2025-04-01", "", "2025-01-01", "合成(架空)"),
        f("lambda の式", "(lambda x: x)(報酬)", "報酬=case:報酬月額", "丸めない",
          "2025-04-01", "", "2025-01-01", "合成(架空)"),
        f("知らない関数の式", "ラウンド(報酬)", "報酬=case:報酬月額", "丸めない",
          "2025-04-01", "", "2025-01-01", "合成(架空)"),
        f("重なる式", "報酬 * 2", "報酬=case:報酬月額", "丸めない",
          "2025-04-01", "2026-04-01", "2025-01-01", "合成(架空)"),
        f("重なる式", "報酬 * 3", "報酬=case:報酬月額", "丸めない",
          "2026-01-01", "2027-01-01", "2025-01-01", "合成(架空)"),
        f("循環A", "甲 + 1", "甲=formula:循環B", "丸めない",
          "2025-04-01", "", "2025-01-01", "合成(架空)"),
        f("循環B", "乙 + 1", "乙=formula:循環A", "丸めない",
          "2025-04-01", "", "2025-01-01", "合成(架空)"),
    ]


def write(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=columns, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {path.name}: {len(rows)} 行")


def main() -> None:
    write(HERE / "keisan.csv", F_COLUMNS, formulas_clean())
    write(HERE / "atai.csv", V_COLUMNS, values_clean())
    write(HERE / "keisan_fuseigou.csv", F_COLUMNS, formulas_broken())


if __name__ == "__main__":
    main()
