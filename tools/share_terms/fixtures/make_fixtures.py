"""share_terms の合成 fixture。**実在の料率・金額・取引先名は 1 つも入っていない。**

数表 id・rule id・出典元 id・出す先 id はすべて架空で、値そのものは 1 行も入っていない
(この部品は行数と宣言の有無を数えるだけなので、中身が何でも同じように動く)。許諾の名前
だけは、実際に使われている名前の形が分からないと読めないので `MIT` と `公共データ利用規約`
を置き、3 つ目は架空の名前にしてある。写したのは形だけ、つまり

  - 許諾の名前が書かれている出典元(上流由来)と、書かれていない出典元(自前抽出)が混ざる
  - 出すと宣言され、その許諾が要求すると宣言した欄も埋まっている行が在る
  - 出すと宣言されたが、要求される欄が空の行が在る(足りない欄は 1 つとは限らない)
  - 出さないと宣言された行が在る(照合専用にあたるもの)
  - 出すとも出さないとも書かれていない行が在る
  - 要求すると宣言された欄が 0 個の許諾が在る(欄が全部空でも揃っている)
  - 出典元の台帳に無い出典元 id を指す行が在る(= 逆向きの欠け)
  - 配布物の目録に載っているのに台帳に無い rule が在る
  - 同じ帰属の文字列を 2 つの rule が持つ配布物が在る(畳むと件数が減る)

の 9 つで、これは私の記録に残っている形だ。記録そのものは出さない。**rule の数と行数の桁
(15 rule / 867 行)だけは手元の記録と同じ形にそろえてある**(値は架空)。

書くもの(どれも決定論。同じ実行で同じバイト列になる)。

  daichou_a.csv      行の台帳 15 行(数表 7 つ、出典元 8 つ)
  kyodaku_a.csv      許諾の登録表 3 行
  shutten_a.csv      出典元の台帳 7 行
  mokuroku_a.csv     配布物の目録 8 行(出す先 3 つ、うち 1 行は台帳に無い rule を指す)
  kowashita/*.csv    理由コードと「表として読めない」を出すために 1 か所崩した表

使い方: python fixtures/make_fixtures.py   (この置き場に書き直す)
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import share_terms as H  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの(テストがその行を開いて語の在ることを見る)
SRC_PIN = "articles/10_source_pin.md L13"       # 原本の場所と生の文字に突き合わせる回
SRC_AXIS = "articles/33_backing_axis.md L13"    # 裏付けの由来の軸で並べ直す回

TANA = "私の棚卸し記録(非公開)L37"
JOURYUU = "私の上流のメモ(非公開)L68"
JIMAE = "私の抽出のメモ(非公開)L64"
JIBUN = "私の配る側のメモ(非公開)L95"
MOKU = "私の配布のメモ(非公開)L12"

LIC_MIT = "MIT"
LIC_KOUKYOU = "公共データ利用規約"
LIC_KOUKAI = "合成の公開の宣言(架空)"
LIC_MITOUROKU = "合成の未登録の許諾(架空)"

ATTR_A = "合成の帰属の文字列 A(架空)"
ATTR_B = "合成の帰属の文字列 B(架空)"
ATTR_C = "合成の帰属の文字列 C(架空)"

URL_B = "https://example.invalid/synthetic-b"

FP_G1 = "9a1c0f22b7d4"
FP_G2 = "3e77be05c918"
FP_G3 = "c40d2a6b1f85"
FP_G4 = "71b9e3d08a2c"
FP_G5 = "5d26af94c7e1"
FP_G6 = "0b83cf15e2a7"
FP_G7 = "e619d7c3b45f"

GOT_ON = "2026-05-11"
FILE_A = "合成の配布 A(架空).json"
FILE_B = "合成の配布 B(架空).csv"
FILE_C = "合成の配布 C(架空).md"

IRU, IRANAI = H.YESNO
DASU, DASANAI = H.DASU, H.DASANAI


def kyodaku_rows() -> list[list[str]]:
    """許諾の登録表 3 行。**要求する欄は人が書いた宣言をそのまま持つだけ。**"""
    return [
        [LIC_MIT, IRU, IRANAI, IRANAI, "私の上流のメモ(非公開)L18"],
        [LIC_KOUKYOU, IRU, IRU, IRU, JOURYUU],
        [LIC_KOUKAI, IRANAI, IRANAI, IRANAI, JIBUN],
    ]


def shutten_rows() -> list[list[str]]:
    """出典元の台帳 7 行。G3 / G4 / G5 は許諾の名前の書かれている場所が無い。"""
    return [
        ["G1", FP_G1, GOT_ON, "私の上流のメモ(非公開)L18"],
        ["G2", FP_G2, GOT_ON, JOURYUU],
        ["G3", FP_G3, GOT_ON, ""],
        ["G4", FP_G4, GOT_ON, ""],
        ["G5", FP_G5, GOT_ON, ""],
        ["G6", FP_G6, GOT_ON, JIBUN],
        ["G7", FP_G7, GOT_ON, "私の上流のメモ(非公開)L72"],
    ]


def daichou_rows() -> list[list[str]]:
    """行の台帳 15 行。K42 は出典元の台帳に無い G9 を指す(= 逆向きの欠け)。"""
    return [
        # H1 / G1: 名前が書かれている上流由来。K12 だけ帰属の文字列が空
        ["H1", "K11", "120", "G1", LIC_MIT, ATTR_A, "", FP_G1, DASU, SRC_PIN],
        ["H1", "K12", "55", "G1", LIC_MIT, "", "", FP_G1, DASU, TANA],
        ["H1", "K13", "8", "G1", LIC_KOUKAI, "", "", "", DASU, TANA],
        ["H1", "K14", "15", "G1", LIC_MIT, ATTR_A, "", FP_G1, DASU, TANA],
        # H2 / G2: 3 欄を要求する許諾。K22 は 2 欄、K23 も 2 欄が空
        ["H2", "K21", "240", "G2", LIC_KOUKYOU, ATTR_B, URL_B, FP_G2, DASU, TANA],
        ["H2", "K22", "96", "G2", LIC_KOUKYOU, ATTR_B, "", "", DASU, TANA],
        ["H2", "K23", "18", "G2", LIC_KOUKYOU, "", "", FP_G2, DASU, TANA],
        # H3 / G3: 自前抽出。許諾の名前の欄が空のまま「出す」と宣言されている
        ["H3", "K31", "141", "G3", "", "", "", FP_G3, DASU, JIMAE],
        ["H3", "K32", "47", "G3", "", "", "", FP_G3, DASU, SRC_AXIS],
        # H4 / G4・G9: 出すとも出さないとも書かれていない
        ["H4", "K41", "39", "G4", "", "", "", FP_G4, "", JIMAE],
        ["H4", "K42", "12", "G9", "", "", "", "", "", JIMAE],
        # H5 / G5: 同上の自前抽出だが「出す」と宣言されている
        ["H5", "K51", "20", "G5", "", "", "", FP_G5, DASU, JIMAE],
        # H6 / G7: 出さないと宣言された行(照合専用にあたる)
        ["H6", "K61", "47", "G7", LIC_MIT, "", "", FP_G7, DASANAI, JOURYUU],
        # H7 / G6: 自分の書いたもの。K72 は登録表に無い名前
        ["H7", "K71", "6", "G6", LIC_MIT, ATTR_C, "", FP_G6, DASU, JIBUN],
        ["H7", "K72", "3", "G6", LIC_MITOUROKU, ATTR_C, "", FP_G6, DASU, JIBUN],
    ]


def mokuroku_rows() -> list[list[str]]:
    """配布物の目録 8 行。B3 → K99 は台帳に無い rule を指す(= 逆向きの欠け)。"""
    return [
        ["B1", FILE_A, "K11", H.SWAPS[0], MOKU],
        ["B1", FILE_A, "K13", "", MOKU],
        ["B1", FILE_A, "K14", "", MOKU],
        ["B1", FILE_A, "K21", "", MOKU],
        ["B2", FILE_B, "K21", "", MOKU],
        ["B2", FILE_B, "K31", "", MOKU],
        ["B2", FILE_B, "K71", "", MOKU],
        ["B3", FILE_C, "K99", "", MOKU],
    ]


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
    d, k, s, m = daichou_rows(), kyodaku_rows(), shutten_rows(), mokuroku_rows()
    D, K, S, M = (H.DAICHOU_COLUMNS, H.KYODAKU_COLUMNS, H.SHUTTEN_COLUMNS,
                  H.MOKUROKU_COLUMNS)
    return {
        # 理由コード(行の台帳)
        "daichou_shutten_nashi": (D, patch(d, {(0, 9): ""})),
        "daichou_rule_id_juufuku": (D, patch(d, {}, extra=[list(d[0])])),
        "daichou_rule_id_matagi": (D, patch(d, {}, extra=[["H9"] + list(d[0][1:])])),
        "daichou_shimon_kuichigai": (D, patch(d, {(0, 7): FP_G2})),
        "daichou_namae_basho_nashi": (D, patch(d, {(7, 4): LIC_MIT})),
        "daichou_namae_kuuran": (D, patch(d, {(0, 4): ""})),
        # 理由コード(配布物の目録)
        "mokuroku_kumi_juufuku": (M, patch(m, {}, extra=[list(m[0])])),
        "mokuroku_filename_kuichigai": (M, patch(m, {(1, 1): FILE_C})),
        "mokuroku_dasanai": (M, patch(m, {}, extra=[["B1", FILE_A, "K61", "", MOKU]])),
        "mokuroku_sengen_nashi": (M, patch(m, {}, extra=[["B1", FILE_A, "K41", "",
                                                          MOKU]])),
        # 表として読めない(行の台帳)
        "daichou_retsu_nashi": (D[:-1], [row[:-1] for row in d]),
        "daichou_0gyou": (D, []),
        "daichou_rule_id_kuuran": (D, patch(d, {(0, 1): ""})),
        "daichou_table_id_kuuran": (D, patch(d, {(0, 0): ""})),
        "daichou_origin_id_kuuran": (D, patch(d, {(0, 3): ""})),
        "daichou_gyousuu_shousuu": (D, patch(d, {(0, 2): "120.5"})),
        "daichou_dasu_sengen_gai": (D, patch(d, {(0, 8): "たぶん"})),
        # 表として読めない(許諾の登録表)
        "kyodaku_retsu_nashi": (K[:-1], [row[:-1] for row in k]),
        "kyodaku_namae_kuuran": (K, patch(k, {(0, 0): ""})),
        "kyodaku_namae_juufuku": (K, patch(k, {}, extra=[list(k[0])])),
        "kyodaku_iru_gai": (K, patch(k, {(0, 1): "たぶん"})),
        # 表として読めない(出典元の台帳)
        "shutten_retsu_nashi": (S[:-1], [row[:-1] for row in s]),
        "shutten_0gyou": (S, []),
        "shutten_origin_id_kuuran": (S, patch(s, {(0, 0): ""})),
        "shutten_origin_id_juufuku": (S, patch(s, {}, extra=[list(s[0])])),
        "shutten_shutoku_bi_katachi": (S, patch(s, {(0, 2): "2026/05/11"})),
        "shutten_shutoku_bi_nai_hi": (S, patch(s, {(0, 2): "2026-02-30"})),
        # 表として読めない(配布物の目録)
        "mokuroku_retsu_nashi": (M[:-1], [row[:-1] for row in m]),
        "mokuroku_0gyou": (M, []),
        "mokuroku_bundle_id_kuuran": (M, patch(m, {(0, 0): ""})),
        "mokuroku_rule_id_kuuran": (M, patch(m, {(0, 2): ""})),
        "mokuroku_filename_kuuran": (M, patch(m, {(0, 1): ""})),
        "mokuroku_swap_gai": (M, patch(m, {(0, 3): "シャッフル"})),
        "mokuroku_swap_futatsu": (M, patch(m, {(1, 3): H.SWAPS[1]})),
        # 読めるが verify だけが止まる
        "mokuroku_swap_nashi": (M, patch(m, {(0, 3): ""})),
    }


def main() -> None:
    written = [H.write_csv(HERE / "daichou_a.csv",
                           [list(H.DAICHOU_COLUMNS)] + daichou_rows()),
               H.write_csv(HERE / "kyodaku_a.csv",
                           [list(H.KYODAKU_COLUMNS)] + kyodaku_rows()),
               H.write_csv(HERE / "shutten_a.csv",
                           [list(H.SHUTTEN_COLUMNS)] + shutten_rows()),
               H.write_csv(HERE / "mokuroku_a.csv",
                           [list(H.MOKUROKU_COLUMNS)] + mokuroku_rows())]
    for name, (head, rows) in kowashita().items():
        written.append(H.write_csv(HERE / "kowashita" / f"{name}.csv",
                                   [list(head)] + rows))
    print(f"書いた: {len(written)} 枚(うち崩した表 {len(kowashita())} 枚)")


if __name__ == "__main__":
    main()
