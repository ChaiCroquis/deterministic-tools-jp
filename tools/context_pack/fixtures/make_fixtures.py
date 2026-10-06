"""context_pack の合成 fixture を作る(地域名・料率・限度額・出典名はすべて架空)。

原本 2 枚(`moto_*.csv`)を先に書き、その sha256 と行番号を引いた行(`hiita.csv`)に焼く。
だから fixture の中の sha256 は本物の指紋で、原本を 1 文字でも変えれば一致しなくなる。

引いた行は 12 行。5 行は宣言どおりに焼ける行、6 行は必ず焼く列のどれかが欠けた行、
残り 1 行は同じ問いに当たる 2 行目(該当 2 件以上で止まる側)。

使い方: python make_fixtures.py   (このフォルダに CSV と JSON を書き出す)
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

ROW_FIELDS = ("rule", "selector", "valid_from", "valid_to", "known_from", "known_quality",
              "priority", "payload", "source", "source_file", "source_row", "source_sha256")

DECL_FIELDS = ("field", "required", "max_chars", "pin")

RYOURITSU = "合成の料率表 2026 年度版(架空)"
SAITEI = "合成の最低賃金表 2025 年度版(架空)"
GENDO = "合成の限度額表 2026 年度版(架空)"

# 上限を超える出典(切り詰めずに止まることを見るための行。値そのものは他の行と同じ作り)
NAGAI = ("合成の料率表 2026 年度版(架空。公表の体裁だけをまねて出典の文字列を長くしてある行で、"
         "宣言された字数の上限を超えたときに、黙って切り詰めずに止まることを見るために置いている。"
         "値そのものは他の行と同じ作りで、原本も同じ 1 枚を指している)")

# 原本 1 枚目: 地域 × 料率・最低賃金(行番号は 1 が見出し、2 から 地域A)
MOTO_RYOURITSU = [
    ("地域", "保険料率_甲", "保険料率_乙", "保険料率_丙", "最低賃金"),
    ("地域A", "9.70", "1.60", "2.40", "1120"),
    ("地域B", "9.82", "1.60", "2.40", "1095"),
    ("地域C", "9.55", "1.60", "2.40", "1081"),
    ("地域D", "9.61", "1.60", "2.40", "1104"),
    ("地域E", "9.74", "1.60", "2.40", "1073"),
    ("地域F", "9.68", "1.60", "2.40", "1088"),
    ("地域G", "9.90", "1.60", "2.40", "1142"),
]

# 原本 2 枚目: 区分 × 限度額
MOTO_GENDOGAKU = [
    ("区分", "限度額_丁"),
    ("区分1", "357000"),
    ("区分2", "298000"),
]


def _write(path: Path, rows: list) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerows([list(r) for r in rows])


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows_of(sha_ryouritsu: str, sha_gendogaku: str) -> list:
    """引いた行 12 行。R = 料率の原本、G = 限度額の原本。"""
    R, G = "moto_ryouritsu.csv", "moto_gendogaku.csv"
    return [
        # 宣言どおりに焼ける行(5 行。3 つめは公表時点が仮置き)
        ("保険料率_甲", "地域=地域A", "2026-03-01", "", "2026-02-10", "実値",
         "0", "9.70", RYOURITSU, R, "2", sha_ryouritsu),
        ("保険料率_甲", "地域=地域B", "2026-03-01", "", "2026-02-10", "実値",
         "0", "9.82", RYOURITSU, R, "3", sha_ryouritsu),
        ("保険料率_乙", "地域=地域A", "2026-03-01", "", "2026-03-01", "仮置き",
         "0", "1.60", RYOURITSU, R, "2", sha_ryouritsu),
        ("最低賃金", "地域=地域A", "2025-10-01", "", "2025-08-05", "実値",
         "0", "1120", SAITEI, R, "2", sha_ryouritsu),
        ("限度額_丁", "区分=区分1", "2026-04-01", "", "2026-01-20", "実値",
         "0", "357000", GENDO, G, "2", sha_gendogaku),
        # 必ず焼く列のどれかが欠けた行(6 行。1 行につき 1 か所だけ空にしてある)
        ("保険料率_甲", "地域=地域C", "2026-03-01", "", "2026-02-10", "実値",
         "0", "9.55", "", R, "4", sha_ryouritsu),                      # 出典が空欄
        ("保険料率_甲", "地域=地域D", "2026-03-01", "", "2026-02-10", "実値",
         "0", "9.61", RYOURITSU, R, "5", ""),                          # sha256 が無い
        ("保険料率_甲", "地域=地域E", "", "", "2026-02-10", "実値",
         "0", "9.74", RYOURITSU, R, "6", sha_ryouritsu),                # 有効期間が空欄
        ("保険料率_甲", "地域=地域F", "2026-03-01", "", "2026-03-01", "",
         "0", "9.68", RYOURITSU, R, "7", sha_ryouritsu),                # 公表時点が空欄
        ("保険料率_甲", "地域=地域G", "2026-03-01", "", "2026-02-10", "実値",
         "0", "9.90", NAGAI, R, "8", sha_ryouritsu),                    # max_chars 超過
        # 同じ問いに当たる 2 行(該当 2 件以上で止まる側。順位で決め直さない)
        ("保険料率_丙", "地域=地域A", "2026-03-01", "2026-09-01", "2026-02-10", "実値",
         "0", "2.40", RYOURITSU, R, "2", sha_ryouritsu),
        ("保険料率_丙", "地域=地域A", "2026-09-01", "", "2026-02-10", "実値",
         "10", "2.55", RYOURITSU, R, "2", sha_ryouritsu),
    ]


# 貼り先の宣言表(field / required / max_chars / pin)
DECL = [
    ("値", "○", "40", "payload"),
    ("対象", "○", "120", "rule|selector"),
    ("有効期間", "○", "40", "valid_from|valid_to"),
    ("公表時点", "○", "40", "known_from|known_quality"),
    ("出典", "○", "120", "source"),
    ("原本", "○", "160", "source_file|source_row|source_sha256"),
    ("順位", "", "20", "priority"),
]


def build() -> dict:
    """fixture を書き出し、{ファイル名: 行数} を返す。"""
    _write(HERE / "moto_ryouritsu.csv", MOTO_RYOURITSU)
    _write(HERE / "moto_gendogaku.csv", MOTO_GENDOGAKU)
    sha_r = _sha256(HERE / "moto_ryouritsu.csv")
    sha_g = _sha256(HERE / "moto_gendogaku.csv")

    rows = rows_of(sha_r, sha_g)
    _write(HERE / "hiita.csv", [ROW_FIELDS, *rows])

    # 引いた 1 行をそのまま JSON で渡す形(post_007 の CLI が返す 1 行 JSON)
    one = dict(zip(ROW_FIELDS, rows[0]))
    (HERE / "hiita_1gyou.json").write_text(
        json.dumps(one, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    _write(HERE / "sengen.csv", [DECL_FIELDS, *DECL])
    # 必ず焼く列(出典)を宣言から落とした表 = 宣言の不備(終了コード 2)
    _write(HERE / "sengen_shutten_nashi.csv",
           [DECL_FIELDS, *[d for d in DECL if d[0] != "出典"]])
    # 行に無い列を焼くと宣言した表 = 理由コード「pin に指定された列が行に無い」
    _write(HERE / "sengen_michi_hashira.csv",
           [DECL_FIELDS, *DECL, ("公表の終わり", "○", "40", "known_to")])
    return {"moto_ryouritsu.csv": len(MOTO_RYOURITSU) - 1,
            "moto_gendogaku.csv": len(MOTO_GENDOGAKU) - 1,
            "hiita.csv": len(rows), "sengen.csv": len(DECL)}


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
