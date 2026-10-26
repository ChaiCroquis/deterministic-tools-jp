"""overlap_check の合成 fixture。**実在の料率・金額・取引先名は 1 つも入っていない。**

資料 id・年度・項目名・値は全て架空で(値は `v11` のような記号)、実在の金額も料率も 1 つも
入っていない(この部品は値を文字列として比べるだけなので、中身が何でも同じように動く)。
写したのは形だけ、つまり

  - 今年の資料の「変更前」欄と、去年の資料の「変更後」欄に、同じ項目が両方現れる
  - 同じ項目でも年度で項目名が揺れる(寄せ方を宣言しないと比べられない)
  - 収録した行の値を、今年の「変更前」欄から採っている(= 1 年遡らせた行)
  - 片方の年度にしか無い項目がある(新設か取り逃しかは分からない)
  - 単位の宣言が空の欄、単位が年度で違う欄がある
  - 資料そのものが手元に無い年度を指した問いがある

の 6 つで、これは私の検証と収録の記録に残っている形だ。記録そのものは出さない。

書くもの(どれも決定論。同じ実行で同じバイト列になる)。

  chuushutsu_a.csv   年度ごとの抽出表 32 行(資料 3 枚 × 変更前 / 変更後)
  yose_a.csv         名前の寄せ方の表 10 行(1 組は年度で名前が揺れる)
  saiyou_a.csv       採用元の宣言 11 行
  toi_a.csv          問いの一覧 17 行(年度ペア 4 通り)
  kowashita/*.csv    理由コードと「表として読めない」を出すために 1 か所崩した表

使い方: python fixtures/make_fixtures.py   (この置き場に書き直す)
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import overlap_check as H  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの(テストがその行を開いて語の在ることを見る)
SRC_CROSS = "articles/11_cross_route.md L14"    # 片方の経路にしか無い、を 4 値に持つ回
SRC_ANSWER = "articles/16_answer_check.md L13"  # 塊に無い、を 4 値に持つ回

SHIRYOU = "私の資料の記録(非公開)"
SHUUROKU = "私の収録の記録(非公開)"
KENSHOU = "私の検証の記録(非公開)"
YOSEKATA = f"私の寄せ方のメモ / {SHUUROKU}"
SRC_TOI = f"私の突き合わせのメモ / {KENSHOU}"

MAE, ATO = H.ROLES
EN, HI = "円", "日"          # 単位の宣言(架空の表でも単位は宣言させる)


def chuushutsu_rows() -> list[list[str]]:
    """年度ごとの抽出表。資料 3 枚(S1/T1・S2/T2・S3/T3)の変更前と変更後の欄。"""
    return [
        # 去年の資料(T1)。変更後の欄が経路 A になる
        ["S1", "T1", "K01", MAE, EN, "v10", SHIRYOU],
        ["S1", "T1", "K02", MAE, EN, "v20", SHIRYOU],
        ["S1", "T1", "K01", ATO, EN, "v11", SHIRYOU],
        ["S1", "T1", "K02", ATO, EN, "v21", SHIRYOU],
        ["S1", "T1", "K03", ATO, EN, "v31", SHIRYOU],
        ["S1", "T1", "K04", ATO, EN, "v41", SHIRYOU],
        ["S1", "T1", "K05", ATO, EN, "v51", SHIRYOU],
        ["S1", "T1", "K06", ATO, EN, "v61", SHIRYOU],
        ["S1", "T1", "K07", ATO, EN, "v71", SHIRYOU],
        ["S1", "T1", "K11", ATO, EN, "vB1", SHIRYOU],
        # 今年の資料(T2)。変更前の欄が経路 B、変更後の欄が次のペアの経路 A になる
        ["S2", "T2", "K01", MAE, EN, "v11", SHIRYOU],
        ["S2", "T2", "K02", MAE, EN, "v21", SHIRYOU],
        ["S2", "T2", "K03", MAE, EN, "v39", SHIRYOU],
        ["S2", "T2", "K04", MAE, EN, "v41", SHIRYOU],
        ["S2", "T2", "K05", MAE, EN, "v51", SHIRYOU],
        ["S2", "T2", "K07", MAE, "", "v71", SHIRYOU],      # 単位の宣言が空
        ["S2", "T2", "K11", MAE, HI, "vB1", SHIRYOU],      # 単位が年度で違う
        ["S2", "T2", "K01", ATO, EN, "v12", SHIRYOU],
        ["S2", "T2", "K02", ATO, EN, "v22", SHIRYOU],
        ["S2", "T2", "K03", ATO, EN, "v32", SHIRYOU],
        ["S2", "T2", "K04", ATO, EN, "v42", SHIRYOU],
        ["S2", "T2", "K08", ATO, EN, "v82", SHIRYOU],
        ["S2", "T2", "K09", ATO, EN, "v92", SHIRYOU],
        ["S2", "T2", "K10", ATO, EN, "vA2", SHIRYOU],
        # 翌年の資料(T3)
        ["S3", "T3", "K01", MAE, EN, "v12", SHIRYOU],
        ["S3", "T3", "K02", MAE, EN, "v29", SHIRYOU],
        ["S3", "T3", "K03", MAE, EN, "v32", SHIRYOU],
        ["S3", "T3", "K04", MAE, EN, "v42", SHIRYOU],
        ["S3", "T3", "K09x", MAE, EN, "v92", SHIRYOU],     # 項目名が年度で揺れる
        ["S3", "T3", "K10", MAE, EN, "vA2", SHIRYOU],
        ["S3", "T3", "K01", ATO, EN, "v13", SHIRYOU],
        ["S3", "T3", "K02", ATO, EN, "v23", SHIRYOU],
    ]


def yose_rows() -> list[list[str]]:
    """名前の寄せ方の表。**同じ文字列でも寄せたことを宣言する**(K05 だけ宣言が無い)。"""
    onaji = "年度で同じ項目名(寄せたことを宣言する)"
    return [
        ["K01", "K01", onaji, YOSEKATA],
        ["K02", "K02", onaji, YOSEKATA],
        ["K03", "K03", onaji, YOSEKATA],
        ["K04", "K04", onaji, YOSEKATA],
        ["K06", "K06", onaji, YOSEKATA],
        ["K07", "K07", onaji, YOSEKATA],
        ["K08", "K08", onaji, YOSEKATA],
        ["K09", "K09x", "年度で文言が揺れた同じ項目(正規化の規則をここに宣言する)",
         YOSEKATA],
        ["K10", "K10", onaji, YOSEKATA],
        ["K11", "K11", onaji, YOSEKATA],
    ]


def saiyou_rows() -> list[list[str]]:
    """採用元の宣言。K03 と K04 は今年の「変更前」欄から採った行(= 1 年遡らせた行)。"""
    return [
        ["G01", "K01", "S1", ATO, SHUUROKU],
        ["G02", "K02", "S1", ATO, SHUUROKU],
        ["G03", "K03", "S3", MAE, SRC_ANSWER],
        ["G04", "K04", "S2", MAE, SRC_CROSS],
        ["G05", "K05", "S1", ATO, SHUUROKU],
        ["G06", "K06", "S1", ATO, SHUUROKU],
        ["G07", "K07", "S1", ATO, SHUUROKU],
        ["G08", "K08", "S2", ATO, SHUUROKU],
        ["G09", "K09", "S2", ATO, SHUUROKU],
        ["G10", "K10", "S2", ATO, SHUUROKU],
        ["G11", "K11", "S1", ATO, SHUUROKU],
    ]


def toi_rows() -> list[list[str]]:
    """問いの一覧。年度ペア 4 通り(T0 は資料が手元に無い、T2 × T2 は同じ年度)。"""
    return [
        ["T1", "T2", "K01", SRC_TOI, H.SWAPS[0]],
        ["T1", "T2", "K02", SRC_TOI, ""],
        ["T1", "T2", "K03", SRC_TOI, ""],
        ["T1", "T2", "K04", SRC_TOI, ""],
        ["T1", "T2", "K05", KENSHOU, ""],
        ["T1", "T2", "K06", KENSHOU, ""],
        ["T1", "T2", "K07", KENSHOU, ""],
        ["T1", "T2", "K11", KENSHOU, ""],
        ["T2", "T3", "K01", SRC_TOI, ""],
        ["T2", "T3", "K02", SRC_TOI, ""],
        ["T2", "T3", "K03", SRC_TOI, ""],
        ["T2", "T3", "K04", SRC_TOI, ""],
        ["T2", "T3", "K08", KENSHOU, ""],
        ["T2", "T3", "K09", KENSHOU, ""],
        ["T2", "T3", "K10", KENSHOU, ""],
        ["T0", "T1", "K01", KENSHOU, ""],
        ["T2", "T2", "K02", KENSHOU, ""],
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
    c, y, s, t = chuushutsu_rows(), yose_rows(), saiyou_rows(), toi_rows()
    C, Y, S, T = (H.CHUUSHUTSU_COLUMNS, H.YOSE_COLUMNS, H.SAIYOU_COLUMNS,
                  H.TOI_COLUMNS)
    return {
        # 理由コード(抽出表)
        "chuushutsu_shutten_nashi": (C, patch(c, {(0, 6): ""})),
        "chuushutsu_atai_kuuran": (C, patch(c, {(2, 5): ""})),
        "chuushutsu_kumi_juufuku": (C, patch(c, {}, extra=[
            ["S1", "T1", "K01", ATO, EN, "v11", SHIRYOU]])),
        # 表として読めない(抽出表)
        "chuushutsu_retsu_nashi": (C[:-1], [row[:-1] for row in c]),
        "chuushutsu_0gyou": (C, []),
        "chuushutsu_doc_id_kuuran": (C, patch(c, {(0, 0): ""})),
        "chuushutsu_nendo_kuuran": (C, patch(c, {(0, 1): ""})),
        "chuushutsu_item_kuuran": (C, patch(c, {(0, 2): ""})),
        "chuushutsu_yaku_gai": (C, patch(c, {(0, 3): "改定前"})),
        "chuushutsu_nendo_futatsu": (C, patch(c, {(1, 1): "T9"})),
        "chuushutsu_shiryou_futatsu": (C, patch(c, {(1, 0): "S9"})),
        # 理由コード(名前の寄せ方の表)
        "yose_shutten_nashi": (Y, patch(y, {(0, 3): ""})),
        "yose_riyuu_kuuran": (Y, patch(y, {(0, 2): ""})),
        "yose_item_a_juufuku": (Y, patch(y, {}, extra=[
            ["K01", "K01x", "同じ年度 A の項目名を 2 行書いた", YOSEKATA]])),
        # 表として読めない(名前の寄せ方の表)
        "yose_retsu_nashi": (Y[:-1], [row[:-1] for row in y]),
        "yose_0gyou": (Y, []),
        "yose_item_a_kuuran": (Y, patch(y, {(0, 0): ""})),
        "yose_item_b_kuuran": (Y, patch(y, {(0, 1): ""})),
        # 理由コード(採用元の宣言)
        "saiyou_shutten_nashi": (S, patch(s, {(0, 4): ""})),
        "saiyou_yaku_gai": (S, patch(s, {(0, 3): "改定後"})),
        "saiyou_shiryou_nashi": (S, patch(s, {(0, 2): "S9"})),
        "saiyou_item_juufuku": (S, patch(s, {}, extra=[
            ["G99", "K01", "S2", MAE, SHUUROKU]])),
        "saiyou_sengen_nashi": (S, patch(s, {}, drop=(8,))),
        # 表として読めない(採用元の宣言)
        "saiyou_retsu_nashi": (S[:-1], [row[:-1] for row in s]),
        "saiyou_0gyou": (S, []),
        "saiyou_row_id_juufuku": (S, patch(s, {(1, 0): "G01"})),
        "saiyou_item_kuuran": (S, patch(s, {(0, 1): ""})),
        # 理由コード(問いの一覧)
        "toi_shutten_nashi": (T, patch(t, {(1, 3): ""})),
        # 表として読めない(問いの一覧)
        "toi_retsu_nashi": (T[:-1], [row[:-1] for row in t]),
        "toi_0gyou": (T, []),
        "toi_nendo_kuuran": (T, patch(t, {(1, 0): ""})),
        "toi_item_kuuran": (T, patch(t, {(1, 2): ""})),
        "toi_onaji_toi_juufuku": (T, patch(t, {(1, 2): "K01"})),
        "toi_nendo_katachi": (T, patch(t, {(1, 1): "T 2"})),
        "toi_swap_gai": (T, patch(t, {(0, 4): "シャッフル"})),
        "toi_swap_futatsu": (T, patch(t, {(1, 4): H.SWAPS[1]})),
        # 読めるが verify だけが止まる
        "toi_swap_nashi": (T, patch(t, {(0, 4): ""})),
    }


def main() -> None:
    written = [H.write_csv(HERE / "chuushutsu_a.csv",
                           [list(H.CHUUSHUTSU_COLUMNS)] + chuushutsu_rows()),
               H.write_csv(HERE / "yose_a.csv",
                           [list(H.YOSE_COLUMNS)] + yose_rows()),
               H.write_csv(HERE / "saiyou_a.csv",
                           [list(H.SAIYOU_COLUMNS)] + saiyou_rows()),
               H.write_csv(HERE / "toi_a.csv", [list(H.TOI_COLUMNS)] + toi_rows())]
    for name, (head, rows) in kowashita().items():
        written.append(H.write_csv(HERE / "kowashita" / f"{name}.csv",
                                   [list(head)] + rows))
    print(f"書いた: {len(written)} 枚(うち崩した表 {len(kowashita())} 枚)")


if __name__ == "__main__":
    main()
