"""handoff_edge の合成 fixture。**実在の料率・金額・取引先名は 1 つも入っていない。**

節 id・rule と式の名前・求める値 id は全て架空で、値も日付も 1 つも入っていない(この部品は
宣言を突き合わせるだけなので、値が要らない)。写したのは形だけ、つまり「状態が 4 種に分かれて
いる」「出口が 2 種に分かれていて、未実装なのに値が返る節が在る」「設計上の外に置いた節が在る」
「レシピが参照する節が宣言表に無いことが在る」「1 つの求める値が複数の節を要る」という 5 つで、
これは私の設計の記録と公開済みの記事に残っている形だ。記録そのものは出さない。

書くもの(どれも決定論。同じ実行で同じバイト列になる)。

  syuubi_a.csv      守備範囲の宣言表 11 行(節 1 つが 1 行)
  recipe_a.csv      計算のレシピ表 12 行(求める値 1 つが 1 行)
  toi_a.csv         問いの一覧 12 行
  kowashita/*.csv   止まる理由コードと「表として読めない」を出すために 1 か所崩した表

使い方: python fixtures/make_fixtures.py   (この置き場に書き直す)
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import handoff_edge as H  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの(テストがその行を開いて語の在ることを見る)
SRC_SCOPE = "articles/18_scope_ledger.md L32"      # できないことの宣言と経路の突き合わせ
SRC_STOCK = "articles/30_cover_stock.md L14"       # 引けない理由を 1 つに潰さない

SEKKEI = "私の設計の記録(非公開)"
SRC_SEKKEI = f"私の設計メモ / {SEKKEI}"

OSAMARI, MIJISSOU, MITAIOU, SOTO = H.STATES
KAERU, TOMARU = H.EXITS


def syuubi_rows() -> list[list[str]]:
    """節ごとの宣言。状態も出口も残る一手もそろっていない。"""
    return [
        ["N01", "合成の rule 甲(架空)", OSAMARI, KAERU, "", SRC_SEKKEI],
        ["N02", "合成の rule 乙(架空)", OSAMARI, KAERU, "", SRC_SEKKEI],
        ["N03", "合成の式 丙(架空)", MIJISSOU, KAERU, "上限を当てる", SRC_STOCK],
        ["N04", "合成の rule 丁(架空)", MITAIOU, TOMARU, "乗率を取ってくる", SEKKEI],
        ["N05", "合成の rule 戊(架空)", SOTO, KAERU, "判断を属性で渡す", SRC_SCOPE],
        ["N06", "合成の rule 己(架空)", SOTO, KAERU, "主体ごとの値を渡す", SEKKEI],
        ["N07", "合成の式 庚(架空)", SOTO, KAERU, "履歴の走査を外で回す", SEKKEI],
        ["N08", "合成の rule 辛(架空)", MITAIOU, TOMARU, "3 軸の表を分解する", SEKKEI],
        ["N09", "合成の式 壬(架空)", MIJISSOU, KAERU, "式の実装を足す", SRC_SEKKEI],
        ["N10", "合成の rule 癸(架空)", MITAIOU, TOMARU, "行を足す", SEKKEI],
        ["N11", "合成の rule 子(架空)", MIJISSOU, KAERU, "手で追記する", SEKKEI],
    ]


def recipe_rows() -> list[list[str]]:
    """求める値 1 件に要る節の組。1 つで足りるものも、3 つ要るものも在る。"""
    return [
        ["V01", "N01", SRC_SEKKEI],
        ["V02", "N01|N02", SEKKEI],
        ["V03", "N01|N03", SRC_STOCK],
        ["V04", "N03|N09", SEKKEI],
        ["V05", "N01|N04", SEKKEI],
        ["V06", "N05", SRC_SCOPE],
        ["V07", "N01|N03|N05", SEKKEI],
        ["V08", "N06|N07", SEKKEI],
        ["V09", "N03|N08", SEKKEI],
        ["V10", "N01|N99", SEKKEI],
        ["V11", "N05|N10", SEKKEI],
        ["V12", "N11", SEKKEI],
    ]


def toi_rows() -> list[list[str]]:
    """訊く求める値。レシピ表の全部を 1 回ずつ訊く。"""
    rows = [[f"V{i:02d}", SEKKEI if i % 2 else SRC_SEKKEI, ""] for i in range(1, 13)]
    rows[0][2] = H.SWAPS[0]
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
    s, r, t = syuubi_rows(), recipe_rows(), toi_rows()
    S, R, T = H.SYUUBI_COLUMNS, H.RECIPE_COLUMNS, H.TOI_COLUMNS
    return {
        # 止まる理由コード(宣言表)
        "syuubi_shutten_nashi": (S, patch(s, {(0, 5): ""})),
        "syuubi_id_juufuku": (S, patch(s, {}, extra=[s[0]])),
        "syuubi_zokusuru_kuuran": (S, patch(s, {(0, 1): ""})),
        "syuubi_joutai_kuuran": (S, patch(s, {(2, 2): ""})),
        "syuubi_joutai_gai": (S, patch(s, {(2, 2): "だいたい収録済"})),
        "syuubi_deguchi_kuuran": (S, patch(s, {(3, 3): ""})),
        "syuubi_deguchi_gai": (S, patch(s, {(3, 3): "たぶん返る"})),
        "syuubi_nokoru_kuuran": (S, patch(s, {(2, 4): ""})),
        "syuubi_osamari_ni_nokoru": (S, patch(s, {(0, 4): "上限を当てる"})),
        "syuubi_osamari_ga_tomaru": (S, patch(s, {(0, 3): TOMARU})),
        # 表として読めない(宣言表)
        "syuubi_retsu_nashi": (S[:-1], [row[:-1] for row in s]),
        "syuubi_0gyou": (S, []),
        "syuubi_id_kuuran": (S, patch(s, {(0, 0): ""})),
        "syuubi_id_katachi": (S, patch(s, {(0, 0): "N 01"})),
        # レシピ表
        "recipe_setsu_nashi": (R, patch(r, {(0, 1): ""})),
        "recipe_shutten_nashi": (R, patch(r, {(0, 2): ""})),
        "recipe_retsu_nashi": (R[:-1], [row[:-1] for row in r]),
        "recipe_0gyou": (R, []),
        "recipe_id_kuuran": (R, patch(r, {(0, 0): ""})),
        "recipe_id_juufuku": (R, patch(r, {}, extra=[r[0]])),
        "recipe_onaji_sansyou": (R, patch(r, {(1, 1): "N01|N01"})),
        # 問いの一覧
        "toi_shutten_nashi": (T, patch(t, {(0, 1): ""})),
        "toi_retsu_nashi": (T[:-1], [row[:-1] for row in t]),
        "toi_0gyou": (T, []),
        "toi_id_kuuran": (T, patch(t, {(0, 0): ""})),
        "toi_id_juufuku": (T, patch(t, {(1, 0): "V01"})),
        "toi_recipe_ni_nai": (T, patch(t, {(1, 0): "V99"})),
        "toi_swap_gai": (T, patch(t, {(0, 2): "シャッフル"})),
        "toi_swap_futatsu": (T, patch(t, {(1, 2): H.SWAPS[1]})),
        "toi_swap_nashi": (T, patch(t, {(0, 2): ""})),
    }


def main() -> None:
    written = [H.write_csv(HERE / "syuubi_a.csv",
                           [list(H.SYUUBI_COLUMNS)] + syuubi_rows()),
               H.write_csv(HERE / "recipe_a.csv",
                           [list(H.RECIPE_COLUMNS)] + recipe_rows()),
               H.write_csv(HERE / "toi_a.csv", [list(H.TOI_COLUMNS)] + toi_rows())]
    for name, (head, rows) in kowashita().items():
        written.append(H.write_csv(HERE / "kowashita" / f"{name}.csv",
                                   [list(head)] + rows))
    print(f"書いた: {len(written)} 枚(うち崩した表 {len(kowashita())} 枚)")


if __name__ == "__main__":
    main()
