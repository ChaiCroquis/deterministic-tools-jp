"""input_chain の合成 fixture。**実在の料率・金額・取引先名は 1 つも入っていない。**

式 id・rule id・case の欄の名前・求める値 id は全て架空で、値も日付も 1 つも入っていない(この
部品は宣言を繋いで数えるだけなので、値が要らない)。写したのは形だけ、つまり

  - 式の入力がまた式で、その式の入力が表の行で、その行を引くのにまた日付と区分が要る(段が付く)
  - 同じ入力が、ある宣言では「導出する」と書かれ、別の呼び口では人が渡されている
  - 式が互いを参照して輪になることがある
  - 参照先が宣言表に無いことがある
  - 行を引くのに要る欄が、基準日 1 つ + 区分 0 個以上に分かれる

の 5 つで、これは私の設計の記録と公開済みの記事に残っている形だ。記録そのものは出さない。

書くもの(どれも決定論。同じ実行で同じバイト列になる)。

  shiki_a.csv       式の宣言表 20 行(1 つの式の 1 つの入力が 1 行)
  gyou_a.csv        行の宣言表 4 行(1 つの rule が 1 行)
  toi_a.csv         問いの一覧 10 行
  shiki_fukai.csv   段数の上限に当たる深い鎖(9 行)。toi_fukai.csv と対で使う
  toi_fukai.csv     深い鎖を訊く問い 1 行
  kowashita/*.csv   理由コードと「表として読めない」を出すために 1 か所崩した表

使い方: python fixtures/make_fixtures.py   (この置き場に書き直す)
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import input_chain as H  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの(テストがその行を開いて語の在ることを見る)
SRC_BASIS = "articles/26_basis_map.md L14"        # 手元に無い種別を代用しない
SRC_EDGE = "articles/31_handoff_edge.md L44"      # 線の外に置くと決めたもの

SEKKEI = "私の設計の記録(非公開)"
SRC_SHIKI = f"私の数式メモ / {SEKKEI}"
SRC_GYOU = f"私の行の記録 / {SEKKEI}"
SRC_TOI = f"私の問いのメモ / {SEKKEI}"

BETSU, HYOU, CASE, DOUSHUTSU = H.KINDS


def shiki_rows() -> list[list[str]]:
    """式ごとの入力の宣言。種別は 4 種で、宣言表に無い参照も輪も混ざっている。"""
    return [
        ["F01", "C01", CASE, SRC_SHIKI],
        ["F01", "F02", BETSU, SRC_SHIKI],
        ["F02", "C02", DOUSHUTSU, SRC_BASIS],
        ["F02", "R01", HYOU, SRC_SHIKI],
        ["F03", "C02", CASE, SRC_BASIS],
        ["F03", "C06", CASE, SEKKEI],
        ["F03", "F08", CASE, SRC_EDGE],
        ["F04", "F03", BETSU, SEKKEI],
        ["F04", "F05", BETSU, SEKKEI],
        ["F05", "C08", CASE, SEKKEI],
        ["F05", "F99", BETSU, SRC_SHIKI],
        ["F05", "R03", HYOU, SEKKEI],
        ["F06", "C09", CASE, SEKKEI],
        ["F06", "F07", BETSU, SRC_SHIKI],
        ["F07", "F06", BETSU, SRC_SHIKI],
        ["F07", "R04", HYOU, SEKKEI],
        ["F08", "C03", CASE, SRC_TOI],
        ["F08", "C07", CASE, SRC_TOI],
        ["F09", "F01", BETSU, SEKKEI],
        ["F09", "R02", HYOU, SEKKEI],
    ]


def gyou_rows() -> list[list[str]]:
    """行を引くのに要る case の欄。基準日はちょうど 1 つ、区分は 0 個以上。"""
    return [
        ["R01", "C03", "C04|C05", SRC_GYOU],
        ["R02", "C03", "C07", SEKKEI],
        ["R03", "C03", "", SRC_GYOU],
        ["R04", "C03", "C09", SEKKEI],
    ]


def toi_rows() -> list[list[str]]:
    """訊く求める値と、そのとき手元に在る case の欄。最後の 1 行は宣言表に無い求める値。"""
    return [
        ["F01", "C01|C03", SRC_TOI, H.SWAPS[0]],
        ["F02", "C03", SEKKEI, ""],
        ["F03", "C06", SRC_TOI, ""],
        ["F04", "", SEKKEI, ""],
        ["F05", "C08", SRC_TOI, ""],
        ["F06", "C09", SEKKEI, ""],
        ["F07", "", SRC_TOI, ""],
        ["F08", "C07", SEKKEI, ""],
        ["F09", "", SRC_TOI, ""],
        ["F88", "C01", SEKKEI, ""],
    ]


def fukai_shiki_rows() -> list[list[str]]:
    """段数の上限に当たる深い鎖(D01 → D02 → … → D09 → case の欄)。"""
    rows = [[f"D{i:02d}", f"D{i + 1:02d}", BETSU, SRC_SHIKI] for i in range(1, 9)]
    return rows + [["D09", "C01", CASE, SRC_SHIKI]]


def fukai_toi_rows() -> list[list[str]]:
    return [["D01", "", SRC_TOI, H.SWAPS[0]]]


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
    """理由コードと「表として読めない」を出すために 1 か所崩した表。"""
    s, g, t = shiki_rows(), gyou_rows(), toi_rows()
    S, G, T = H.SHIKI_COLUMNS, H.GYOU_COLUMNS, H.TOI_COLUMNS
    return {
        # 理由コード(式の宣言表)
        "shiki_shutten_nashi": (S, patch(s, {(0, 3): ""})),
        "shiki_syubetsu_kuuran": (S, patch(s, {(0, 2): ""})),
        "shiki_syubetsu_gai": (S, patch(s, {(0, 2): "たぶん case の欄"})),
        "shiki_nyuuryoku_juufuku": (S, patch(s, {}, extra=[s[0]])),
        "shiki_rule_to_doumei": (S, patch(s, {(0, 0): "R01"})),
        # 表として読めない(式の宣言表)
        "shiki_retsu_nashi": (S[:-1], [row[:-1] for row in s]),
        "shiki_0gyou": (S, []),
        "shiki_id_kuuran": (S, patch(s, {(0, 0): ""})),
        "shiki_id_katachi": (S, patch(s, {(0, 0): "F 01"})),
        "shiki_nyuuryoku_id_kuuran": (S, patch(s, {(0, 1): ""})),
        # 理由コード(行の宣言表)
        "gyou_shutten_nashi": (G, patch(g, {(0, 3): ""})),
        "gyou_kijunbi_kuuran": (G, patch(g, {(0, 1): ""})),
        "gyou_kijunbi_futatsu": (G, patch(g, {(0, 1): "C03|C10"})),
        "gyou_kubun_juufuku": (G, patch(g, {(0, 2): "C04|C04"})),
        # 表として読めない(行の宣言表)
        "gyou_retsu_nashi": (G[:-1], [row[:-1] for row in g]),
        "gyou_0gyou": (G, []),
        "gyou_id_kuuran": (G, patch(g, {(0, 0): ""})),
        "gyou_id_juufuku": (G, patch(g, {}, extra=[g[0]])),
        # 理由コード(問いの一覧)
        "toi_shutten_nashi": (T, patch(t, {(0, 2): ""})),
        "toi_temoto_juufuku": (T, patch(t, {(0, 1): "C01|C01"})),
        "toi_motomeru_ga_temoto": (T, patch(t, {(0, 1): "C01|C03|F01"})),
        # 表として読めない(問いの一覧)
        "toi_retsu_nashi": (T[:-1], [row[:-1] for row in t]),
        "toi_0gyou": (T, []),
        "toi_id_kuuran": (T, patch(t, {(0, 0): ""})),
        "toi_id_juufuku": (T, patch(t, {(1, 0): "F01"})),
        "toi_swap_gai": (T, patch(t, {(0, 3): "シャッフル"})),
        "toi_swap_futatsu": (T, patch(t, {(1, 3): H.SWAPS[1]})),
        # 読めるが verify だけが止まる
        "toi_swap_nashi": (T, patch(t, {(0, 3): ""})),
    }


def main() -> None:
    written = [H.write_csv(HERE / "shiki_a.csv", [list(H.SHIKI_COLUMNS)] + shiki_rows()),
               H.write_csv(HERE / "gyou_a.csv", [list(H.GYOU_COLUMNS)] + gyou_rows()),
               H.write_csv(HERE / "toi_a.csv", [list(H.TOI_COLUMNS)] + toi_rows()),
               H.write_csv(HERE / "shiki_fukai.csv",
                           [list(H.SHIKI_COLUMNS)] + fukai_shiki_rows()),
               H.write_csv(HERE / "toi_fukai.csv",
                           [list(H.TOI_COLUMNS)] + fukai_toi_rows())]
    for name, (head, rows) in kowashita().items():
        written.append(H.write_csv(HERE / "kowashita" / f"{name}.csv",
                                   [list(head)] + rows))
    print(f"書いた: {len(written)} 枚(うち崩した表 {len(kowashita())} 枚)")


if __name__ == "__main__":
    main()
