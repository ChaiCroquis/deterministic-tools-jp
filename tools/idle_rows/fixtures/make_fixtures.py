"""idle_rows の合成 fixture。**実在の料率・金額・取引先名は 1 つも入っていない。**

数表 id・rule id・参照元 id・問い id はすべて架空で、値そのものは 1 行も入っていない
(この部品は行数と参照の有無を数えるだけなので、中身が何でも同じように動く)。写したのは
形だけ、つまり

  - 引ける許可は在る(CLI で引ける / 出典と依存行が付く)のに、どの参照元からも指されて
    いない行が、行数の大きい数表に在る
  - 参照する参照元は在るのに、その参照元を要る参照元に挙げた問いが無い行が在る
    (= 二次の空白。上に来る値が未実装のまま残っている形)
  - 引く対象でないと宣言された行(照合専用)が在る
  - 有効開始日が基準日より後の行が在る(未来有効行)
  - 参照の宣言を 1 行も書いていない数表が在る
  - 台帳に無い rule を指している宣言が在る(= 逆向きの欠け)
  - 滞留の理由コードが、登録表に無い語で書かれている行が在る

の 7 つで、これは私の棚卸し記録に残っている形だ。記録そのものは出さない。**rule の数と
行数の桁(14 rule / 277 行、うち滞留 196 行)だけは手元の記録と同じ形にそろえてある**
(値は架空)。

書くもの(どれも決定論。同じ実行で同じバイト列になる)。

  daichou_a.csv      行の台帳 14 行(数表 6 つ、由来 3 通り)
  sengen_a.csv       参照の宣言表 9 行(参照元 6 つ、うち 1 行は台帳に無い rule を指す)
  toi_a.csv          問いの一覧 3 行(基準日 2026-05-20)
  riyuu_a.csv        理由コードの登録表 3 行
  kowashita/*.csv    理由コードと「表として読めない」を出すために 1 か所崩した表

使い方: python fixtures/make_fixtures.py   (この置き場に書き直す)
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import idle_rows as H  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの(テストがその行を開いて語の在ることを見る)
SRC_PACK = "articles/15_context_pack.md L13"    # 引いた行を塊に焼く回
SRC_CHAIN = "articles/32_input_chain.md L13"    # 入力を下へ辿る回

TANA = "私の棚卸し記録(非公開)"
GENKAI = "私の限界のメモ(非公開)"
SHIKI = "私の式の記録(非公開)"
TOI = f"私の参照のメモ / {TANA}"

ASOF = "2026-05-20"
JIMAE, JOURYUU, SHOUGOU = H.ORIGINS
SHIKI_KIND, TOI_KIND = H.REF_KINDS
NYUURYOKU, CHOKUSETSU, KEIYU = H.HOWS
IRU, IRANAI = H.SOURCE_NEEDED

MIJISSOU = "未実装"
MISHUUROKU = "未収録の相手がいる"
MIRAI = "未来の有効行"
MITOUROKU = "画像 PDF"        # 登録表に無い理由コード(別枠の一覧に出る)


def riyuu_rows() -> list[list[str]]:
    """理由コードの登録表 3 行。**意味は人が書いた語をそのまま持つだけ。**"""
    return [
        [MIJISSOU, "参照する側の実装がまだ", IRU],
        [MISHUUROKU, "参照する側の行がまだ台帳に無い", IRU],
        [MIRAI, "有効開始日が基準日より後", IRANAI],
    ]


def daichou_rows() -> list[list[str]]:
    """行の台帳 14 行。H6 の rule を指す宣言は 1 行も置かない(= 参照の宣言が無い)。"""
    return [
        # H1: 宣言が在る数表。K13 だけがどの参照元からも指されていない(一次の空白)
        ["H1", "K11", "6", JIMAE, "", "", "", SRC_PACK],
        ["H1", "K12", "4", JIMAE, "", "", "", TANA],
        ["H1", "K13", "3", JIMAE, "", "", "", TANA],
        ["H1", "K14", "9", JIMAE, "", "", "", TANA],
        # H2: 上流由来。K24 だけが式の入力に出てきて、残る 3 行は一次の空白
        ["H2", "K21", "90", JOURYUU, "", MISHUUROKU, GENKAI, TANA],
        ["H2", "K22", "48", JOURYUU, "", MISHUUROKU, GENKAI, TANA],
        ["H2", "K23", "12", JOURYUU, "", "", "", TANA],
        ["H2", "K24", "7", JOURYUU, "", "", "", TANA],
        # H3: 参照する式は在るが、その式を要る参照元に挙げた問いが無い(二次の空白)
        ["H3", "K31", "20", JIMAE, "", MIJISSOU, GENKAI, SRC_CHAIN],
        ["H3", "K32", "21", JIMAE, "", MIJISSOU, GENKAI, TANA],
        ["H3", "K33", "2", JIMAE, "", MIJISSOU, GENKAI, TANA],
        # H4: 引く対象でないと宣言された行(照合専用)
        ["H4", "K41", "47", SHOUGOU, "", "", "", TANA],
        # H5: 有効開始日が基準日より後(未来有効行)
        ["H5", "K51", "3", JOURYUU, "2027-09-01", MIRAI, "", TANA],
        # H6: 参照の宣言を 1 行も書いていない数表。理由コードも登録表に無い語
        ["H6", "K61", "5", JIMAE, "", MITOUROKU, GENKAI, TANA],
    ]


def sengen_rows() -> list[list[str]]:
    """参照の宣言表 9 行。F5 → K99 は台帳に無い rule を指す(= 逆向きの欠け)。"""
    return [
        ["F1", SHIKI_KIND, "K11", NYUURYOKU, SHIKI],
        ["F1", SHIKI_KIND, "K24", NYUURYOKU, SHIKI],
        ["F2", SHIKI_KIND, "K12", NYUURYOKU, SHIKI],
        ["F2", SHIKI_KIND, "K14", KEIYU, SHIKI],
        ["F3", SHIKI_KIND, "K31", NYUURYOKU, SHIKI],
        ["F3", SHIKI_KIND, "K32", NYUURYOKU, SHIKI],
        ["F4", SHIKI_KIND, "K33", NYUURYOKU, SHIKI],
        ["Q1", TOI_KIND, "K11", CHOKUSETSU, SHIKI],
        ["F5", SHIKI_KIND, "K99", NYUURYOKU, SHIKI],
    ]


def toi_rows() -> list[list[str]]:
    """問いの一覧 3 行。基準日と入れ替え方は 1 行目だけに書く。"""
    return [
        ["Q1", "合成の求める値 A(架空)", "F1", ASOF, H.SWAPS[0], TOI],
        ["Q2", "合成の求める値 B(架空)", "F2", "", "", TOI],
        ["Q3", "合成の求める値 C(架空)", "F1", "", "", TOI],
    ]


def patch(rows: list[list[str]], edits: dict[tuple[int, int], str],
          extra: list[list[str]] | None = None,
          drop: tuple[int, ...] = ()) -> list[list[str]]:
    """1 か所だけ崩した写しを作る(元の行は書き換えない)。"""
    out = [list(r) for i, r in enumerate(rows) if i not in drop]
    for (i, j), value in edits.items():
        out[i][j] = value
    if extra:
        out.extend(list(r) for r in extra)
    return out


def kowashita() -> dict[str, tuple[tuple[str, ...], list[list[str]]]]:
    """理由コードと「表として読めない」を出すために 1 か所崩した表。"""
    d, s, t, r = daichou_rows(), sengen_rows(), toi_rows(), riyuu_rows()
    D, S, T, R = (H.DAICHOU_COLUMNS, H.SENGEN_COLUMNS, H.TOI_COLUMNS,
                  H.RIYUU_COLUMNS)
    return {
        # 理由コード(行の台帳)
        "daichou_shutten_nashi": (D, patch(d, {(0, 7): ""})),
        "daichou_rule_id_juufuku": (D, patch(d, {}, extra=[
            ["H1", "K11", "6", JIMAE, "", "", "", TANA]])),
        "daichou_rule_id_matagi": (D, patch(d, {}, extra=[
            ["H9", "K11", "6", JIMAE, "", "", "", TANA]])),
        "daichou_riyuu_shutten_nashi": (D, patch(d, {(4, 6): ""})),
        "daichou_shougou_riyuu": (D, patch(d, {(11, 5): MIJISSOU,
                                               (11, 6): GENKAI})),
        # 表として読めない(行の台帳)
        "daichou_retsu_nashi": (D[:-1], [row[:-1] for row in d]),
        "daichou_0gyou": (D, []),
        "daichou_rule_id_kuuran": (D, patch(d, {(0, 1): ""})),
        "daichou_table_id_kuuran": (D, patch(d, {(0, 0): ""})),
        "daichou_yurai_gai": (D, patch(d, {(0, 3): "自前"})),
        "daichou_gyousuu_shousuu": (D, patch(d, {(0, 2): "6.5"})),
        "daichou_hizuke_katachi": (D, patch(d, {(12, 4): "2027/09/01"})),
        "daichou_hizuke_nai_hi": (D, patch(d, {(12, 4): "2027-02-30"})),
        # 理由コード(参照の宣言表)
        "sengen_kumi_juufuku": (S, patch(s, {}, extra=[
            ["F1", SHIKI_KIND, "K11", NYUURYOKU, SHIKI]])),
        "sengen_shougou_sanshou": (S, patch(s, {}, extra=[
            ["F6", SHIKI_KIND, "K41", NYUURYOKU, SHIKI]])),
        "sengen_toi_atesaki_nashi": (S, patch(s, {(7, 0): "Q9"})),
        "sengen_shubetsu_shikata_kuichigai": (S, patch(s, {(0, 3): CHOKUSETSU})),
        # 表として読めない(参照の宣言表)
        "sengen_retsu_nashi": (S[:-1], [row[:-1] for row in s]),
        "sengen_0gyou": (S, []),
        "sengen_ref_id_kuuran": (S, patch(s, {(0, 0): ""})),
        "sengen_rule_id_kuuran": (S, patch(s, {(0, 2): ""})),
        "sengen_shubetsu_gai": (S, patch(s, {(0, 1): "関数"})),
        "sengen_shikata_gai": (S, patch(s, {(0, 3): "なんとなく"})),
        # 理由コード(問いの一覧)
        "toi_needs_atesaki_nashi": (T, patch(t, {(1, 2): "F9"})),
        # 表として読めない(問いの一覧)
        "toi_retsu_nashi": (T[:-1], [row[:-1] for row in t]),
        "toi_0gyou": (T, []),
        "toi_id_kuuran": (T, patch(t, {(0, 0): ""})),
        "toi_needs_kuuran": (T, patch(t, {(1, 2): ""})),
        "toi_id_juufuku": (T, patch(t, {(1, 0): "Q1"})),
        "toi_kijunbi_nashi": (T, patch(t, {(0, 3): ""})),
        "toi_kijunbi_futatsu": (T, patch(t, {(1, 3): "2026-06-01"})),
        "toi_kijunbi_katachi": (T, patch(t, {(0, 3): "2026-5-20"})),
        "toi_swap_gai": (T, patch(t, {(0, 4): "シャッフル"})),
        "toi_swap_futatsu": (T, patch(t, {(1, 4): H.SWAPS[1]})),
        # 表として読めない(理由コードの登録表)
        "riyuu_retsu_nashi": (R[:-1], [row[:-1] for row in r]),
        "riyuu_code_kuuran": (R, patch(r, {(0, 0): ""})),
        "riyuu_code_juufuku": (R, patch(r, {}, extra=[
            [MIJISSOU, "別の意味", IRU]])),
        "riyuu_shutten_gai": (R, patch(r, {(0, 2): "たぶん"})),
        # 読めるが verify だけが止まる
        "toi_swap_nashi": (T, patch(t, {(0, 4): ""})),
    }


def main() -> None:
    written = [H.write_csv(HERE / "daichou_a.csv",
                           [list(H.DAICHOU_COLUMNS)] + daichou_rows()),
               H.write_csv(HERE / "sengen_a.csv",
                           [list(H.SENGEN_COLUMNS)] + sengen_rows()),
               H.write_csv(HERE / "toi_a.csv", [list(H.TOI_COLUMNS)] + toi_rows()),
               H.write_csv(HERE / "riyuu_a.csv",
                           [list(H.RIYUU_COLUMNS)] + riyuu_rows())]
    for name, (head, rows) in kowashita().items():
        written.append(H.write_csv(HERE / "kowashita" / f"{name}.csv",
                                   [list(head)] + rows))
    print(f"書いた: {len(written)} 枚(うち崩した表 {len(kowashita())} 枚)")


if __name__ == "__main__":
    main()
