"""variant_fan の合成 fixture。率も日数も出典名も架空で、実データ・実在の取引先名は 1 つも入れない。

書くもの。

  shikihyou.csv / jikuhyou.csv            6 軸を全部宣言した式表と軸表(repo に commit 済)
  cumulative/k<N>_*.csv                   軸を 1 本ずつ宣言に戻していく 6 段(残りは式表に literal で書き切る)
  kakikiri_*.csv                          扇が 1 通りに潰れる組み合わせ(終了コード 0 の側)
  kowashita/*.csv                         止まる理由コードを出すために 1 か所だけ崩した表

軸が効く位置は「軸の名前をどこに書いたか」だけで決まるので、**軸を宣言から外すときは、その軸の
宣言された既定を式表の同じ場所に literal で書く**(= 選び方を書き切った状態)。これが扇の増え方を
1 軸ずつ測るやり方になる。
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

HEADER_F = ["id", "expr", "rounding", "valid_from", "valid_to", "known_from", "known_to", "source"]
HEADER_A = ["axis", "choice", "source", "default", "limit"]

LIMIT = "200"

# 入力(合成。架空の金額と日数)
INPUTS = {"報酬月額": "310000", "出勤日数": "21"}
AS_OF = "2026-05-01"

# 扇が 1 通りに潰れる側の入力(端数が出ない金額を選んである)
INPUTS_KAKIKIRI = {"報酬月額": "30000", "出勤日数": "20"}

# 軸表の順。この順が扇の組み合わせの順になり、記事の図 2 の行の順にもなる
ORDER = ("丸めの名前", "丸めを掛ける段", "基準日の取り方", "区分の選び方", "期間の切り方", "入力の桁の扱い")

# 軸 -> ((候補, その候補の出典), ...)。出典のうち repo 内の行を指すものは実在の行番号
CHOICES = {
    "丸めの名前": (("50銭以下切捨て", "tools/formula_table/README.md L37"),
                   ("1円未満切捨て", "tools/formula_table/README.md L38"),
                   ("円未満四捨五入", "tools/formula_table/README.md L39")),
    "丸めを掛ける段": (("丸めない", "tools/formula_table/README.md L40"),
                       ("1円未満切捨て", "tools/formula_table/README.md L38")),
    "基準日の取り方": (("2026-04-01", "articles/07_asof_table.md L28"),
                       ("2026-03-31", "articles/07_asof_table.md L28")),
    "区分の選び方": (("8.13", "合成の料率メモ(架空)L1"),
                     ("9.98", "合成の料率メモ(架空)L2")),
    "期間の切り方": (("30", "合成の日割りメモ(架空)L1"),
                     ("31", "合成の日割りメモ(架空)L2")),
    "入力の桁の扱い": (("丸めない", "tools/formula_table/README.md L40"),
                       ("1円未満切捨て", "tools/formula_table/README.md L38")),
}
# 宣言された既定の候補(= 宣言から外すときに式表へ literal で書き切る値)
DEFAULT = {name: rows[0][0] for name, rows in CHOICES.items()}

SRC = ("合成の端数処理メモ(架空)L1", "合成の端数処理メモ(架空)L2",
       "合成の改定メモ(架空)L3", "合成の端数処理メモ(架空)L4")


def write_csv(path: Path, header: list[str], rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return path


def formula_rows(pinned: tuple[str, ...] = ()) -> list[list[str]]:
    """式表。pinned に入れた軸は、その軸の宣言された既定を literal で書き切る。"""
    def v(name: str) -> str:
        return DEFAULT[name] if name in pinned else name

    days, rate = v("期間の切り方"), v("区分の選び方")
    r_in, r_mid, r_fin = v("入力の桁の扱い"), v("丸めを掛ける段"), v("丸めの名前")
    return [
        ["日額", f"報酬月額 / {days}", r_in, "2025-04-01", "", "2025-03-01", "", SRC[0]],
        ["対象額", "日額 * 出勤日数", r_mid, "2025-04-01", "2026-04-01", "2025-03-01", "", SRC[1]],
        ["対象額", "日額 * 出勤日数 * 102 / 100", r_mid, "2026-04-01", "", "2026-02-01", "", SRC[2]],
        ["負担額", f"対象額 * {rate} / 200", r_fin, "2025-04-01", "", "2025-03-01", "", SRC[3]],
    ]


def axis_rows(declared: tuple[str, ...]) -> list[list[str]]:
    rows = []
    for name in ORDER:
        if name not in declared:
            continue
        for choice, source in CHOICES[name]:
            rows.append([name, choice, source, "1" if choice == DEFAULT[name] else "", LIMIT])
    return rows


def on_arg(pinned: tuple[str, ...]) -> str:
    """基準日の引数。軸を宣言していればその軸の名前、書き切っていれば既定の日付そのもの。"""
    return DEFAULT["基準日の取り方"] if "基準日の取り方" in pinned else "基準日の取り方"


def build(dest: Path) -> Path:
    dest = Path(dest)
    write_csv(dest / "shikihyou.csv", HEADER_F, formula_rows())
    write_csv(dest / "jikuhyou.csv", HEADER_A, axis_rows(ORDER))

    # 軸を 1 本ずつ宣言に戻す 6 段(k 本だけ宣言、残りは式表に書き切る)
    for k in range(1, len(ORDER) + 1):
        declared, pinned = ORDER[:k], ORDER[k:]
        write_csv(dest / "cumulative" / f"k{k}_shikihyou.csv", HEADER_F, formula_rows(pinned))
        write_csv(dest / "cumulative" / f"k{k}_jikuhyou.csv", HEADER_A, axis_rows(declared))

    # 扇が 1 通りに潰れる側(丸めの名前だけ宣言、ほかは書き切り、端数が出ない金額)
    write_csv(dest / "kakikiri_shikihyou.csv", HEADER_F, formula_rows(ORDER[1:]))
    write_csv(dest / "kakikiri_jikuhyou.csv", HEADER_A, axis_rows(("丸めの名前",)))

    k = dest / "kowashita"
    full = axis_rows(ORDER)

    rows = [list(r) for r in full]
    rows[1][2] = ""                                          # 出典の欄が空
    write_csv(k / "jiku_shutten_nashi.csv", HEADER_A, rows)

    rows = [r for r in (list(x) for x in full) if not (r[0] == "期間の切り方" and r[1] == "31")]
    write_csv(k / "jiku_kouho_1.csv", HEADER_A, rows)          # 候補が 1 件以下

    rows = [list(r) for r in full]
    rows.insert(2, list(full[1]))                              # 同じ軸名 + 同じ候補が 2 行
    write_csv(k / "jiku_juufuku.csv", HEADER_A, rows)

    rows = [list(r) for r in full]
    rows[0][1] = "四捨五入"                                    # 丸めの registry に無い候補
    write_csv(k / "jiku_marume_mitouroku.csv", HEADER_A, rows)

    rows = [list(r) for r in full]
    for r in rows:
        r[4] = "10"                                            # 組み合わせ数が上限超え
    write_csv(k / "jiku_jougen_koe.csv", HEADER_A, rows)

    rows = [list(r) for r in formula_rows()]
    rows[3][2] = ""                                            # 丸めの名前が空欄
    write_csv(k / "shiki_marume_kuuran.csv", HEADER_F, rows)

    rows = [list(r) for r in formula_rows()]
    rows[1][3], rows[2][3] = "2026-06-01", "2026-06-01"        # 基準日の候補がどの版にも当たらない
    write_csv(k / "shiki_kikan_hazure.csv", HEADER_F, rows)

    rows = [list(r) for r in formula_rows()]
    rows[1][4] = ""                                            # 有効期間が重なり 2 件該当
    write_csv(k / "shiki_nijuu.csv", HEADER_F, rows)

    rows = [list(r) for r in formula_rows()]
    rows[3][0] = "負担額A"                                     # 式の id が式表に無い
    write_csv(k / "shiki_id_nashi.csv", HEADER_F, rows)

    # 列が足りない式表(理由コードにせず「表として読めない」= 終了コード 2 で返す側)
    write_csv(k / "shiki_retsu_nashi.csv", HEADER_F[:-1], [r[:-1] for r in formula_rows()])
    return dest


if __name__ == "__main__":
    print(f"書いた: {build(Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent))}")
