"""answer_check の合成 fixture を作る(地域名・料率・限度額・出典名・文章はすべて架空)。

原本 2 枚(`moto_*.csv`)を先に書き、その sha256 と行番号を塊に焼く。だから fixture の中の
sha256 は本物の指紋で、原本を 1 文字でも変えれば一致しなくなる。

塊は 4 件(前の工程が組んだ text 形 `kata.txt` と、同じ中身の CSV `kata.csv` の 2 通り)。
文章は AI が返した答えに見立てた合成の plain text で、数の現れ方を 7 とおり仕込んである。
止まる段を見るための塊 6 枚と宣言表 2 枚も書き出す。

使い方: python make_fixtures.py   (このフォルダに CSV / TXT を書き出す)
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

PACK_FIELDS = ("selector", "payload", "valid_from", "valid_to", "known_from", "known_quality",
               "source", "source_file", "source_row", "source_sha256")
DECL_FIELDS = ("selector", "alias", "unit", "scale", "period", "rounding")

RYOURITSU = "合成の料率表 2026 年度版(架空)"
SAITEI = "合成の最低賃金表 2025 年度版(架空)"
GENDO = "合成の限度額表 2026 年度版(架空)"

R, G = "moto_ryouritsu.csv", "moto_gendogaku.csv"

# 原本 1 枚目: 地域 × 料率・最低賃金(行番号は 1 が見出し、2 から 地域A)
MOTO_RYOURITSU = [
    ("地域", "保険料率_甲", "保険料率_乙", "保険料率_丙", "最低賃金"),
    ("地域A", "9.70", "1.60", "2.40", "1120"),
    ("地域B", "9.82", "1.60", "2.40", "1095"),
    ("地域C", "9.55", "1.60", "2.40", "1081"),
]

# 原本 2 枚目: 区分 × 限度額
MOTO_GENDOGAKU = [
    ("区分", "限度額_丁"),
    ("区分1", "357000"),
    ("区分2", "298000"),
]

# 文章(AI が返した答えに見立てた合成 text)。数の現れ方を 7 とおり仕込んである
BUNSHOU = """保険料率_甲は 9.70% で計算した。
甲の料率は 97‰ と書いても同じ値を指す。
保険料率_甲を 9.7% と丸めて書いた場合も同じ行になる。
保険料率_乙は 1.50% として計算した。
限度額_丁は 357 千円が上限になる。
最低賃金は １，１２０円 を使った。
保険料率_丙は 2.40% だった。
社会保険料の合計は 48,250 円になった。
保険料率_甲は 9.70 と書いてある表もある。
保険料率_甲は 九・七% と読めることもある。
保険料率_甲は 9.70〜9.82% の幅がある。
限度額_丁は 3,57,000 円と書いた資料もあった。
"""

# 暦の日付を含む文章(年月日も数の表記として拾うことを見るための別の fixture)
BUNSHOU_HIZUKE = "保険料率_甲は 2026-03-01 から 9.70% になる。\n"


def _write(path: Path, rows: list) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows([list(r) for r in rows])


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pack_rows(sha_r: str, sha_g: str) -> list:
    """塊 4 件(どれも必ず在る 8 列が埋まっている)。"""
    return [
        ("保険料率_甲 / 地域=地域A", "9.70", "2026-03-01", "", "2026-02-10", "実値",
         RYOURITSU, R, "2", sha_r),
        ("保険料率_乙 / 地域=地域A", "1.60", "2026-03-01", "", "2026-03-01", "仮置き",
         RYOURITSU, R, "2", sha_r),
        ("限度額_丁 / 区分=区分1", "357000", "2026-04-01", "", "2026-01-20", "実値",
         GENDO, G, "2", sha_g),
        ("最低賃金 / 地域=地域A", "1120", "2025-10-01", "", "2025-08-05", "実値",
         SAITEI, R, "2", sha_r),
    ]


# 塊の text(前の工程の init が出すひな型の名前と並び)
TEXT_ORDER = (("値", ("payload",)), ("対象", ("selector",)),
              ("有効期間", ("valid_from", "valid_to")),
              ("公表時点", ("known_from", "known_quality")), ("出典", ("source",)),
              ("原本", ("source_file", "source_row", "source_sha256")))
NOTE = "注記: 公表時点は仮置き(確定値ではない)"


def pack_text(rows: list) -> str:
    """塊 4 件を text 形で並べる(空行で区切る)。"""
    out = []
    for row in rows:
        d = dict(zip(PACK_FIELDS, row))
        lines = [f"{name}: " + " / ".join(d[c] if d[c] else "(なし)" for c in cols)
                 for name, cols in TEXT_ORDER]
        if d["known_quality"] == "仮置き":
            lines.append(NOTE)
        out.append("\n".join(lines))
    return "\n\n".join(out) + "\n"


# 宣言表(比べる対象 5 つ。保険料率_丙 は宣言にあるが塊に無い = 塊に無い に落ちる側)
DECL = [
    ("保険料率_甲 / 地域=地域A", "保険料率_甲|甲の料率", "%|‰", "そのまま|10分の1",
     "2026-06-01", "小数2桁"),
    ("保険料率_乙 / 地域=地域A", "保険料率_乙", "%", "そのまま", "2026-06-01", "小数2桁"),
    ("限度額_丁 / 区分=区分1", "限度額_丁", "円|千円", "そのまま|千倍", "2026-06-01", "整数"),
    ("最低賃金 / 地域=地域A", "最低賃金", "円", "そのまま", "2026-06-01", "整数"),
    ("保険料率_丙 / 地域=地域A", "保険料率_丙", "%", "そのまま", "2026-06-01", "小数2桁"),
]


def build() -> dict:
    """fixture を書き出し、{ファイル名: 件数} を返す。"""
    _write(HERE / R, MOTO_RYOURITSU)
    _write(HERE / G, MOTO_GENDOGAKU)
    sha_r, sha_g = _sha256(HERE / R), _sha256(HERE / G)

    rows = pack_rows(sha_r, sha_g)
    _write(HERE / "kata.csv", [PACK_FIELDS, *rows])
    (HERE / "kata.txt").write_text(pack_text(rows), encoding="utf-8")
    (HERE / "kata_1ken.json").write_text(
        json.dumps(dict(zip(PACK_FIELDS, rows[0])), ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8")

    # 止まる段を見るための塊(1 件につき 1 か所だけ崩してある)
    one = list(rows[0])
    def kuzushita(index: int, value: str) -> list:
        out = list(one)
        out[index] = value
        return [PACK_FIELDS, tuple(out)]
    _write(HERE / "kata_shutten_nashi.csv", kuzushita(PACK_FIELDS.index("source"), ""))
    _write(HERE / "kata_sha_nashi.csv", kuzushita(PACK_FIELDS.index("source_sha256"), ""))
    _write(HERE / "kata_kikan_nashi.csv", kuzushita(PACK_FIELDS.index("valid_from"), ""))
    _write(HERE / "kata_kouhyou_nashi.csv", kuzushita(PACK_FIELDS.index("known_quality"), ""))
    # 有効期間が照合の基準日(2026-06-01)を含まない塊
    kikangai = list(one)
    kikangai[PACK_FIELDS.index("valid_from")] = "2025-03-01"
    kikangai[PACK_FIELDS.index("valid_to")] = "2026-03-01"
    _write(HERE / "kata_kikangai.csv", [PACK_FIELDS, tuple(kikangai)])
    # 同じ対象の行が 2 件ある塊(近い行で埋めずに止まる側)
    futatsume = list(one)
    futatsume[PACK_FIELDS.index("payload")] = "9.82"
    _write(HERE / "kata_nijuu.csv", [PACK_FIELDS, tuple(one), tuple(futatsume)])

    _write(HERE / "sengen.csv", [DECL_FIELDS, *DECL])
    # 単位の宣言が無い対象を含む表
    _write(HERE / "sengen_tani_nashi.csv",
           [DECL_FIELDS, *[(d[0], d[1], "", "", d[4], d[5]) if d[0] == DECL[0][0] else d
                           for d in DECL]])
    # 登録されていない丸めの名前を呼ぶ表
    _write(HERE / "sengen_shiranai_seikika.csv",
           [DECL_FIELDS, *[(*d[:5], "四捨五入") if d[0] == DECL[0][0] else d for d in DECL]])

    (HERE / "bunshou.txt").write_text(BUNSHOU, encoding="utf-8")
    (HERE / "bunshou_kara.txt").write_text("   \n\n", encoding="utf-8")
    (HERE / "bunshou_hizuke.txt").write_text(BUNSHOU_HIZUKE, encoding="utf-8")

    return {R: len(MOTO_RYOURITSU) - 1, G: len(MOTO_GENDOGAKU) - 1,
            "kata.csv": len(rows), "kata.txt": len(rows), "sengen.csv": len(DECL),
            "bunshou.txt": len(BUNSHOU.splitlines())}


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
