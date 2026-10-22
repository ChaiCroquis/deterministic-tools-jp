"""cover_stock の合成 fixture。**実在の料率・金額・取引先名は 1 つも入っていない。**

数表 id・領域の名前・レシピ id・年 id は全て架空で、入っているのは日付と年と件数だけだ(この
部品は収録の端と年の重なりだけを見るので、値は 1 つも要らない)。写したのは形だけ、つまり
「収録の端が領域ごとに 30 年以上ずれている」「同じ『3 年分』でも年の数え始めが違う」「収録の端
が仮置きの行が在る」「収録の中に穴が在る」「収録の先に未来有効行が入っている」という 5 つで、
これは私の棚卸し記録と公開済みの記事に残っている形だ。記録そのものは出さない。

書くもの(どれも決定論。同じ実行で同じバイト列になる)。

  zaiko_a.csv       収録の在庫表 10 行(数表 1 つが 1 行)
  recipe_a.csv      計算のレシピ表 11 行(レシピ 1 つが 1 行)
  nen_a.csv         数える年の一覧 7 行
  kowashita/*.csv   止まる理由コードと「表として読めない」を出すために 1 か所崩した表

使い方: python fixtures/make_fixtures.py   (この置き場に書き直す)
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import cover_stock as C  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの(テストがその行を開いて語の在ることを見る)
SRC_CHOKKIN = "articles/07_asof_table.md L185"   # 「直近の行を返すことは決してしない」
SRC_SUITEI = "articles/28_future_row.md L14"     # 「日付を推定して入れない」

TANAOROSHI = "私の棚卸し記録(非公開)"
SRC_KOUROU = f"厚生労働省 / {TANAOROSHI}"

KOREKI, NENDO3, NENDO4, NENDO8 = C.YEAR_KINDS
HIRAKI, TOJI = C.OPEN_ENDS
JITSUCHI, KARI = C.EDGES


def zaiko_rows() -> list[list[str]]:
    """数表ごとの収録範囲。端の月も、年の数え方も、端の確度もそろっていない。"""
    return [
        ["T01", "合成の領域甲(架空)", "1989-01-01", "", HIRAKI, KOREKI, JITSUCHI, "",
         SRC_CHOKKIN],
        ["T02", "合成の領域乙(架空)", "2024-03-01", "", HIRAKI, NENDO3, JITSUCHI, "",
         SRC_KOUROU],
        ["T03", "合成の領域丙(架空)", "2023-08-01", "", HIRAKI, NENDO8, JITSUCHI, "",
         SRC_KOUROU],
        ["T04", "合成の領域丁(架空)", "2025-04-01", "", HIRAKI, NENDO4, JITSUCHI, "",
         TANAOROSHI],
        ["T05", "合成の領域戊(架空)", "2017-04-01", "", HIRAKI, NENDO4, KARI, "",
         SRC_SUITEI],
        ["T06", "合成の領域己(架空)", "2002-01-01", "2026-01-01", TOJI, KOREKI,
         JITSUCHI, "2010-01-01/2011-01-01", TANAOROSHI],
        ["T07", "合成の領域庚(架空)", "2024-04-01", "2027-04-01", TOJI, NENDO4,
         JITSUCHI, "", SRC_KOUROU],
        ["T08", "合成の領域辛(架空)", "2025-04-01", "", HIRAKI, NENDO4, KARI,
         "2026-04-01/2027-04-01", TANAOROSHI],
        ["T09", "合成の領域壬(架空)", "2025-04-01", "", HIRAKI, "", JITSUCHI, "",
         TANAOROSHI],
        ["T10", "合成の領域癸(架空)", "2025-04-01", "", HIRAKI, KOREKI, "", "",
         TANAOROSHI],
    ]


def recipe_rows() -> list[list[str]]:
    """計算 1 件に要る数表の組。1 枚で足りるものも、3 枚要るものも在る。"""
    return [
        ["R01", "T01", SRC_KOUROU],
        ["R02", "T01|T06", TANAOROSHI],
        ["R03", "T02|T03|T04", TANAOROSHI],
        ["R04", "T04|T07", SRC_KOUROU],
        ["R05", "T05", SRC_SUITEI],
        ["R06", "T04|T05", TANAOROSHI],
        ["R07", "T99", TANAOROSHI],
        ["R08", "", TANAOROSHI],
        ["R09", "T09", TANAOROSHI],
        ["R10", "T10", TANAOROSHI],
        ["R11", "T08", TANAOROSHI],
    ]


def nen_rows() -> list[list[str]]:
    """数える年。暦年と年度(4 月開始)が混ざっている(揃えるのは表を書く人)。"""
    rows = [
        ["Y01", "2002", KOREKI, SRC_KOUROU, ""],
        ["Y02", "2010", KOREKI, TANAOROSHI, ""],
        ["Y03", "2024", KOREKI, SRC_KOUROU, ""],
        ["Y04", "2026", KOREKI, TANAOROSHI, ""],
        ["Y05", "2017", NENDO4, SRC_SUITEI, ""],
        ["Y06", "2026", NENDO4, SRC_KOUROU, ""],
        ["Y07", "2025", NENDO4, TANAOROSHI, ""],
    ]
    rows[0][4] = C.SWAPS[0]
    return rows


def patch(rows: list[list[str]], edits: dict[tuple[int, int], str],
          extra: list[list[str]] | None = None) -> list[list[str]]:
    """1 か所だけ崩した写しを作る(元の行は書き換えない)。"""
    out = [list(r) for r in rows]
    for (i, j), value in edits.items():
        out[i][j] = value
    if extra:
        out.extend(list(r) for r in extra)
    return out


def kowashita() -> dict[str, tuple[tuple[str, ...], list[list[str]]]]:
    """止まる理由コードと「表として読めない」を出すために 1 か所崩した表。"""
    z, r, n = zaiko_rows(), recipe_rows(), nen_rows()
    Z, R, N = C.ZAIKO_COLUMNS, C.RECIPE_COLUMNS, C.YEARS_COLUMNS
    return {
        # 止まる理由コード(在庫表)
        "zaiko_shutten_nashi": (Z, patch(z, {(0, 8): ""})),
        "zaiko_id_juufuku": (Z, patch(z, {}, extra=[z[0]])),
        "zaiko_kazoekata_gai": (Z, patch(z, {(0, 5): "年度(5 月開始)"})),
        "zaiko_kikan_sakasa": (Z, patch(z, {(5, 2): "2027-01-01", (5, 7): ""})),
        "zaiko_ana_gai": (Z, patch(z, {(5, 7): "1999-01-01/2000-01-01"})),
        "zaiko_ana_kasanari": (Z, patch(z, {(5, 7): "2010-01-01/2012-01-01;"
                                                    "2011-01-01/2013-01-01"})),
        "zaiko_hizuke_katachi": (Z, patch(z, {(5, 2): "2002-02-30", (5, 7): ""})),
        "zaiko_hiraki_ni_hizuke": (Z, patch(z, {(0, 3): "2030-01-01"})),
        # 表として読めない(在庫表)
        "zaiko_retsu_nashi": (Z[:-1], [row[:-1] for row in z]),
        "zaiko_0gyou": (Z, []),
        "zaiko_id_kuuran": (Z, patch(z, {(0, 0): ""})),
        "zaiko_ryouiki_kuuran": (Z, patch(z, {(0, 1): ""})),
        "zaiko_hiraki_gai": (Z, patch(z, {(0, 4): "半分開いている"})),
        "zaiko_kakudo_gai": (Z, patch(z, {(0, 6): "たぶん実値"})),
        "zaiko_ana_katachi": (Z, patch(z, {(5, 7): "2010-01-01"})),
        "zaiko_ana_sakasa": (Z, patch(z, {(5, 7): "2011-01-01/2010-01-01"})),
        # レシピ表
        "recipe_shutten_nashi": (R, patch(r, {(0, 2): ""})),
        "recipe_retsu_nashi": (R[:-1], [row[:-1] for row in r]),
        "recipe_0gyou": (R, []),
        "recipe_id_kuuran": (R, patch(r, {(0, 0): ""})),
        "recipe_id_juufuku": (R, patch(r, {}, extra=[r[0]])),
        "recipe_onaji_sansyou": (R, patch(r, {(1, 1): "T01|T01"})),
        # 年の一覧
        "nen_shutten_nashi": (N, patch(n, {(0, 3): ""})),
        "nen_retsu_nashi": (N[:-1], [row[:-1] for row in n]),
        "nen_0gyou": (N, []),
        "nen_id_kuuran": (N, patch(n, {(0, 0): ""})),
        "nen_id_juufuku": (N, patch(n, {(1, 0): "Y01"})),
        "nen_toshi_katachi": (N, patch(n, {(0, 1): "平成14"})),
        "nen_kazoekata_kuuran": (N, patch(n, {(0, 2): ""})),
        "nen_kazoekata_gai": (N, patch(n, {(0, 2): "年度(5 月開始)"})),
        "nen_swap_gai": (N, patch(n, {(0, 4): "シャッフル"})),
        "nen_swap_futatsu": (N, patch(n, {(1, 4): C.SWAPS[1]})),
        "nen_swap_nashi": (N, patch(n, {(0, 4): ""})),
    }


def main() -> None:
    written = [C.write_csv(HERE / "zaiko_a.csv", [list(C.ZAIKO_COLUMNS)] + zaiko_rows()),
               C.write_csv(HERE / "recipe_a.csv",
                           [list(C.RECIPE_COLUMNS)] + recipe_rows()),
               C.write_csv(HERE / "nen_a.csv", [list(C.YEARS_COLUMNS)] + nen_rows())]
    for name, (head, rows) in kowashita().items():
        written.append(C.write_csv(HERE / "kowashita" / f"{name}.csv",
                                   [list(head)] + rows))
    print(f"書いた: {len(written)} 枚(うち崩した表 {len(kowashita())} 枚)")


if __name__ == "__main__":
    main()
