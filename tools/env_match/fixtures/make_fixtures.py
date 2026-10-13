"""env_match の合成 fixture。中身は全て架空で、実データ・実在の取引先名は 1 つも入れない。

出力の束は、公開済みの道具 order_table の `check` が返す欄の形を写した合成の出力。
**同じ入力を別の環境で走らせた結果そのものではなく、その形だけを合成している**(ラベルごとの
違いは、変えた環境要素の欄に書いたとおりに手で作った)。

書くもの(どれも決定論。同じ実行で同じバイト列になる)。

  sengen_hantei.csv          判定部分の宣言表 12 行(入れる 8 / 入れない 4)
  label_a.csv / taba_a/      既定 / タイムゾーン UTC / 別の端末。入れた欄は 8/8 一致する側
  label_b.csv / taba_b/      既定 / 改行 CRLF。入れた欄 8 つ全部で差が出る側
  label_c.csv / taba_c/      既定 / 版 3.13。宣言表に無い欄が 1 つ在る側
  label_d.csv / taba_d/      既定 / sha256 の欄が無い版。判定部分が取れない側
  kowashita/*.csv            止まる理由コードと「表として読めない」を出すために 1 か所だけ崩した表

使い方: python fixtures/make_fixtures.py   (この置き場に書き直す)
"""
from __future__ import annotations

import csv
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import env_match as E  # noqa: E402

# 宣言の出典のうち、この repo 内の実在の行を指すもの(テストがその行を開いて語の在ることを見る)
SRC_SHA = "articles/19_variant_fan.md L143"
SRC_SOTO = "articles/20_order_table.md L146"
SRC_BUNBO = "articles/20_order_table.md L105"
SRC_KAGI = "articles/20_order_table.md L107"
SRC_KENSUU = "articles/20_order_table.md L103"
SRC_GYOUSUU = "articles/20_order_table.md L104"
SRC_CI = "public/README.md L50"

# 合成の「並べた表」。sha256 の欄の値はこの文字列から計算する(架空の 4 行)
SORTED_CSV = (
    "社員番号,氏名カナ,区分,支給日,金額\n"
    "2,サトウ,甲,2026-04-25,829\n"
    "9,ヤマダ,甲,2026-04-25,8290\n"
    "10,スズキ,乙,2026-04-25,829.0\n"
)
SHA = hashlib.sha256(SORTED_CSV.encode("utf-8")).hexdigest()

# 判定部分の宣言表(12 行)。入れる 8 / 入れない 4
DECL_ROWS = [
    ["データ表の行数", "入れる", "", SRC_KENSUU],
    ["鍵の組数", "入れる", "", SRC_KENSUU],
    ["同値の組の件数", "入れる", "", SRC_KENSUU],
    ["同値の組に関与した行数", "入れる", "", SRC_GYOUSUU],
    ["順が一意に決まった行数", "入れる", "", SRC_GYOUSUU],
    ["分母に含めたもの", "入れる", "", SRC_BUNBO],
    ["鍵は宣言された列だけ", "入れる", "", SRC_KAGI],
    ["sha256", "入れる", "", SRC_SHA],
    ["読んだデータ表の絶対パス", "入れない", "絶対パス", SRC_SOTO],
    ["読んだ宣言表の絶対パス", "入れない", "絶対パス", SRC_SOTO],
    ["読んだ時刻", "入れない", "時刻", SRC_SOTO],
    ["ホスト名", "入れない", "ホスト名", SRC_SOTO],
]

# 合成の出力(基準ラベル)。欄の形は order_table の check の出力を写した
BASE_ROWS = [
    ("データ表の行数", "12"),
    ("鍵の組数", "12"),
    ("同値の組の件数", "0"),
    ("同値の組に関与した行数", "0"),
    ("順が一意に決まった行数", "12"),
    ("分母に含めたもの",
     "データ表の行数 12 = 順が一意に決まった行数 12 + 同値の組に関与した行数 0"
     "(同値の組 0 組、鍵の組数 12)"),
    ("鍵は宣言された列だけ", "宣言表の鍵 3 行の列だけで比較した"),
    ("sha256", SHA),
    ("読んだデータ表の絶対パス", "(合成)置き場A/データ表.csv"),
    ("読んだ宣言表の絶対パス", "(合成)置き場A/並び順.csv"),
    ("読んだ時刻", "2026-10-13T09:12:08"),
    ("ホスト名", "合成の端末A"),
]

KIJUN = "既定"
L_TZ = "タイムゾーン UTC"
L_HOST = "別の端末"
L_CRLF = "改行 CRLF"
L_VER = "版 3.13"
L_OLD = "sha256 の欄が無い版"

LABEL_ROWS = {
    KIJUN: ["なし(基準)", "既定のまま", "合成の環境メモ(架空)L1"],
    L_TZ: ["タイムゾーン", "UTC(基準は +09:00)", "合成の環境メモ(架空)L2"],
    L_HOST: ["ホスト名と置き場所", "別の端末の作業用フォルダ", "合成の環境メモ(架空)L3"],
    L_CRLF: ["書き出しの改行", "CRLF(基準は LF)", "合成の環境メモ(架空)L4"],
    L_VER: ["道具を動かした版", "3.13(基準は 3.12)", "合成の環境メモ(架空)L5"],
    L_OLD: ["道具の版", "sha256 の欄を出さない版", SRC_CI],
}


def replaced(rows: list[tuple[str, str]], **changes: str) -> list[tuple[str, str]]:
    return [(k, changes.get(k, v)) for k, v in rows]


def label_table(names: list[str], base: str = KIJUN, swap: str = "逆順") -> list[list[str]]:
    out = [list(E.LABEL_COLUMNS)]
    for i, n in enumerate(names):
        element, setting, source = LABEL_ROWS[n]
        out.append([n, element, setting, source, base if i == 0 else "", swap if i == 0 else ""])
    return out


def write_csv(path: Path, rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)


def bundle(name: str, items: dict[str, tuple[list[tuple[str, str]], str]]) -> Path:
    d = HERE / name
    d.mkdir(parents=True, exist_ok=True)
    for label, (rows, newline) in items.items():
        E.write_bundle(d, rows, label, newline)
    return d


def main() -> None:
    decl = [list(E.DECL_COLUMNS)] + [list(r) for r in DECL_ROWS]
    write_csv(HERE / "sengen_hantei.csv", decl)

    tz = replaced(BASE_ROWS, **{"読んだ時刻": "2026-10-13T00:12:08"})
    host = replaced(BASE_ROWS, **{"読んだデータ表の絶対パス": "(合成)置き場B/データ表.csv",
                                  "読んだ宣言表の絶対パス": "(合成)置き場B/並び順.csv",
                                  "ホスト名": "合成の端末B"})
    ver = list(BASE_ROWS) + [("Python の版", "3.13.1")]
    old = [(k, v) for k, v in BASE_ROWS if k != "sha256"]

    write_csv(HERE / "label_a.csv", label_table([KIJUN, L_TZ, L_HOST]))
    bundle("taba_a", {KIJUN: (list(BASE_ROWS), "\n"), L_TZ: (tz, "\n"), L_HOST: (host, "\n")})

    write_csv(HERE / "label_b.csv", label_table([KIJUN, L_CRLF]))
    bundle("taba_b", {KIJUN: (list(BASE_ROWS), "\n"), L_CRLF: (list(BASE_ROWS), "\r\n")})

    write_csv(HERE / "label_c.csv", label_table([KIJUN, L_VER]))
    bundle("taba_c", {KIJUN: (list(BASE_ROWS), "\n"), L_VER: (ver, "\n")})

    write_csv(HERE / "label_d.csv", label_table([KIJUN, L_OLD]))
    bundle("taba_d", {KIJUN: (list(BASE_ROWS), "\n"), L_OLD: (old, "\n")})

    # ---------------------------------------------------------- 崩した表
    k = HERE / "kowashita"

    # 止まる理由コードを出す側(宣言表)
    write_csv(k / "sengen_0gyou.csv", [list(E.DECL_COLUMNS)])
    no_src = [list(r) for r in DECL_ROWS]
    no_src[0][3] = ""
    write_csv(k / "sengen_shutten_nashi.csv", [list(E.DECL_COLUMNS)] + no_src)
    bad_reason = [list(r) for r in DECL_ROWS]
    bad_reason[10][2] = "既定の文字コード"          # 登録の 5 分類の外
    write_csv(k / "sengen_riyuu_mitouroku.csv", [list(E.DECL_COLUMNS)] + bad_reason)
    not_in_out = [list(r) for r in DECL_ROWS] + [["乱数の種", "入れない", "乱数の種",
                                                  "合成の宣言メモ(架空)L6"]]
    write_csv(k / "sengen_shutsuryoku_ni_nai.csv", [list(E.DECL_COLUMNS)] + not_in_out)

    # 「表として読めない」側(宣言表)
    write_csv(k / "sengen_retsu_nashi.csv",
              [["field", "judge", "source"]] + [[r[0], r[1], r[3]] for r in DECL_ROWS])
    bad_judge = [list(r) for r in DECL_ROWS]
    bad_judge[0][1] = "参考"
    write_csv(k / "sengen_hantei_mitouroku.csv", [list(E.DECL_COLUMNS)] + bad_judge)
    ireru_riyuu = [list(r) for r in DECL_ROWS]
    ireru_riyuu[0][2] = "時刻"                      # 入れる 行に理由の分類
    write_csv(k / "sengen_ireru_ni_riyuu.csv", [list(E.DECL_COLUMNS)] + ireru_riyuu)
    write_csv(k / "sengen_onaji_ran.csv",
              [list(E.DECL_COLUMNS)] + [list(r) for r in DECL_ROWS] + [list(DECL_ROWS[0])])

    # 止まる理由コードを出す側(ラベル表)
    write_csv(k / "label_hitotsu.csv", label_table([KIJUN]))
    write_csv(k / "label_juufuku.csv",
              label_table([KIJUN, L_TZ, L_HOST]) + [[L_TZ, "タイムゾーン", "UTC(2 行目)",
                                                     "合成の環境メモ(架空)L7", "", ""]])
    no_element = label_table([KIJUN, L_TZ, L_HOST])
    no_element[2][1] = ""
    write_csv(k / "label_element_kuuran.csv", no_element)
    no_lsrc = label_table([KIJUN, L_TZ, L_HOST])
    no_lsrc[3][3] = ""
    write_csv(k / "label_shutten_nashi.csv", no_lsrc)
    write_csv(k / "label_kijun_ihou.csv", label_table([KIJUN, L_TZ, L_HOST], base="合成の端末C"))
    write_csv(k / "label_kijun_nashi.csv", label_table([KIJUN, L_TZ, L_HOST], base=""))

    # 「表として読めない」側(ラベル表)
    write_csv(k / "label_0gyou.csv", [list(E.LABEL_COLUMNS)])
    write_csv(k / "label_swap_mitouroku.csv",
              label_table([KIJUN, L_TZ, L_HOST], swap="ランダムに並べ替え"))
    write_csv(k / "label_setting_kuuran.csv",
              [list(E.LABEL_COLUMNS), [KIJUN, "なし(基準)", "", "合成の環境メモ(架空)L1",
                                       KIJUN, "逆順"]])
    futatsu = label_table([KIJUN, L_TZ, L_HOST])
    futatsu[2][4] = L_TZ                            # 基準の宣言が 2 通り
    write_csv(k / "label_kijun_futatsu.csv", futatsu)

    print(f"書いた: {HERE}(宣言表 1 / ラベル表 4 / 束 4 / 崩した表 "
          f"{len(list(k.glob('*.csv')))})")
    print(f"合成の sha256: {SHA}")


if __name__ == "__main__":
    main()
