"""band_edge の合成 fixture。値は全て架空で、実データ・実在の金額や率は 1 つも入れない。

帯の軸の名前(報酬月額帯・賃金日額帯・休業日数帯・生年月日帯 など)だけは、私の棚卸し記録
(非公開)に出典つきで並んでいる実在の軸を写している。**境界値そのものは写していない**
(棚卸し自身が「値は未取得」「出典 URL 照合前」「条文照合は未実施」と書いているため)。
下の表に出てくる数は全て、私が決めた合成の刻みだ。

書くもの(どれも決定論。同じ実行で同じバイト列になる)。

  atai_a.csv           値の表 12 行。境界値ちょうどに当たる行を 7 行混ぜた
  atai_kansan.csv      値の表 2 行。宣言された換算(時間 → 分)で引く行だけ
  obi_a.csv            帯の表 8 行 / 3 項目。隙間も重なりも無い連結(等号は 以上・未満)
  obi_ten.csv          帯の表 8 行。obi_a の 1 欄(上限の等号)を 以下 にした = 点の重なり
  obi_chou.csv         帯の表 8 行。obi_a の 1 欄(下限の等号)を 超 にした = 1 つ下にずれる
  obi_koumoku_nashi.csv 帯の表 5 行。合成の時間(架空)の帯が 1 本も無い
  tani_a.csv           単位の宣言 3 行。合成の時間(架空)だけ換算(時間 → 分)を宣言
  kowashita/*.csv      止まる理由コードと「表として読めない」を出すために 1 か所だけ崩した表

使い方: python fixtures/make_fixtures.py   (この置き場に書き直す)
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import band_edge as B  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの(テストがその行を開いて語の在ることを見る)
SRC_JUNI = "articles/07_asof_table.md L15"        # 「どちらが勝つかは順位の列に書く」
SRC_MARUME = "articles/08_formula_table.md L14"   # 「丸めの名前は式の隣の列に書かせる」
SRC_KITEI = "articles/08_formula_table.md L42"    # 「既定そのものを持たない」
SRC_ANBUN = "articles/22_span_split.md L16"       # 「按分も日割りも無い」

# 帯の出典(動かした主体 + 非公開の棚卸し記録)。軸の名前は公表されている情報
TANAOROSHI = "私の棚卸し記録(非公開)"
SRC_KYOUKAI = f"協会けんぽ / {TANAOROSHI}"
SRC_KOUROU = f"厚生労働省 / {TANAOROSHI}"

# 項目(合成。棚卸しに在る「帯で引く軸」の形だけを写し、境界値は写していない)
I_GETSUGAKU = "合成の月額(架空)"
I_NISSUU = "合成の日数(架空)"
I_JIKAN = "合成の時間(架空)"

T_A, T_B, T_C = "合成の区分A", "合成の区分B", "合成の区分C"

HEAD_ATAI = list(B.ATAI_COLUMNS)
HEAD_OBI = list(B.OBI_COLUMNS)
HEAD_TANI = list(B.TANI_COLUMNS)

# ---------------------------------------------------------------- 値の表

ATAI_A = [
    HEAD_ATAI,
    [T_A, I_GETSUGAKU, "1", "金額", "円", SRC_JUNI],
    [T_A, I_GETSUGAKU, "99999", "金額", "円", SRC_KYOUKAI],
    [T_A, I_GETSUGAKU, "100000", "金額", "円", SRC_KYOUKAI],
    [T_A, I_GETSUGAKU, "150000", "金額", "円", SRC_KYOUKAI],
    [T_B, I_GETSUGAKU, "200000", "金額", "円", SRC_KYOUKAI],
    [T_B, I_NISSUU, "0", "日数", "日", SRC_KOUROU],
    [T_B, I_NISSUU, "179", "日数", "日", SRC_KOUROU],
    [T_B, I_NISSUU, "180", "日数", "日", SRC_KOUROU],
    [T_C, I_JIKAN, "1200", "時間", "分", SRC_MARUME],
    [T_C, I_JIKAN, "20", "時間", "時間", SRC_KITEI],
    [T_C, I_JIKAN, "3600", "時間", "分", SRC_ANBUN],
    [T_C, I_JIKAN, "7200", "時間", "分", SRC_KOUROU],
    [T_C, I_JIKAN, "7201", "時間", "分", SRC_KOUROU],
]

ATAI_KANSAN = [
    HEAD_ATAI,
    [T_C, I_JIKAN, "20", "時間", "時間", SRC_KITEI],
    [T_C, I_JIKAN, "60", "時間", "時間", SRC_KITEI],
]

# ---------------------------------------------------------------- 帯の表

OBI_A = [
    HEAD_OBI,
    [I_GETSUGAKU, "1", B.OPEN, "", "100000", "未満", "合成の段1(架空)", SRC_KYOUKAI, "逆順"],
    [I_GETSUGAKU, "2", "100000", "以上", "200000", "未満", "合成の段2(架空)", SRC_KYOUKAI, ""],
    [I_GETSUGAKU, "3", "200000", "以上", B.OPEN, "", "合成の段3(架空)", SRC_KYOUKAI, ""],
    [I_NISSUU, "1", "0", "以上", "180", "未満", "合成の前半(架空)", SRC_KOUROU, ""],
    [I_NISSUU, "2", "180", "以上", B.OPEN, "", "合成の後半(架空)", SRC_KOUROU, ""],
    [I_JIKAN, "1", B.OPEN, "", "1200", "未満", "合成の下(架空)", SRC_KOUROU, ""],
    [I_JIKAN, "2", "1200", "以上", "3600", "未満", "合成の中(架空)", SRC_KOUROU, ""],
    [I_JIKAN, "3", "3600", "以上", "7200", "以下", "合成の上(架空)", SRC_KOUROU, ""],
]


def obi(change: dict[tuple[int, int], str]) -> list[list[str]]:
    """obi_a の 1 欄だけ差し替えた帯の表を作る(行は 1 始まり = ヘッダの次が 1)。"""
    rows = [list(r) for r in OBI_A]
    for (row, col), value in change.items():
        rows[row][col] = value
    return rows


# obi_a の帯 1 の上限の等号(列 5)を 以下 にすると、100000 が帯 1 と帯 2 の両方に入る
OBI_TEN = obi({(1, 5): "以下"})
# obi_a の帯 2 の下限の等号(列 3)を 超 にすると、100000 は帯 1 に入り 1 つ下へずれる
OBI_CHOU = obi({(1, 5): "以下", (2, 3): "超"})
# 合成の時間(架空)の帯を落とした表(= 値の行はあるが帯が 0 件)
OBI_KOUMOKU_NASHI = [r for i, r in enumerate(OBI_A) if i == 0 or r[0] != I_JIKAN]

# ---------------------------------------------------------------- 単位の宣言

TANI_A = [
    HEAD_TANI,
    [I_GETSUGAKU, "金額", "円", "0", "千円", "1000"],
    [I_NISSUU, "日数", "日", "0", "", ""],
    [I_JIKAN, "時間", "分", "0", "時間", "60"],
]

# ---------------------------------------------------------------- 崩した表

KOWASHITA_OBI: dict[str, list[list[str]]] = {
    # 止まる理由コードを出すもの
    "obi_toukou_kuuran": obi({(2, 3): ""}),                       # 等号が空
    "obi_kaihou_kuuran": obi({(1, 2): ""}),                       # 開放の宣言が無い空欄
    "obi_kasanari": obi({(2, 2): "50000"}),                       # 帯の重なり(範囲)
    "obi_sukima": obi({(2, 2): "100001"}),                        # 帯の隙間
    "obi_shutten_nashi": obi({(1, 7): ""}),                       # 出典の欄が空
    "obi_gyakusa": obi({(2, 2): "200000", (2, 4): "100000"}),     # 下限 > 上限
    "obi_bangou_juufuku": obi({(3, 1): "2"}),                     # 帯の番号の重複
    "obi_koumoku_mitouroku": obi({(4, 0): "合成の未登録(架空)"}),  # 単位の宣言に無い項目
    # 「表として読めない」で返すもの
    "obi_toukou_gyaku": obi({(2, 3): "以下"}),                    # 下限に上限の等号
    "obi_hiraki_toukou": obi({(1, 3): "以上"}),                   # 開いている端に等号
    "obi_kaesu_kuuran": obi({(1, 6): ""}),                        # 返すものが空欄
    "obi_bangou_kuuran": obi({(1, 1): ""}),                       # 帯の番号が空欄
    "obi_shousuu_sugi": obi({(2, 2): "100000.5"}),                # 小数の桁に収まらない
    "obi_swap_futatsu": obi({(2, 8): "両端入れ替え"}),             # 入れ替え方が 2 通り
    "obi_swap_mitouroku": obi({(1, 8): "ランダム"}),               # 入れ替え方が登録の外
    "obi_yomenai": obi({(2, 2): "十万"}),                          # 数として読めない
}

KOWASHITA_ATAI: dict[str, list[list[str]]] = {
    "atai_shurui_kuuran": [HEAD_ATAI, [T_A, I_GETSUGAKU, "100000", "", "円", SRC_KYOUKAI]],
    "atai_shutten_nashi": [HEAD_ATAI, [T_A, I_GETSUGAKU, "100000", "金額", "円", ""]],
    "atai_kansan_mi": [HEAD_ATAI, [T_C, I_JIKAN, "1200", "時間", "秒", SRC_KOUROU]],
    "atai_koumoku_mitouroku": [HEAD_ATAI,
                               [T_A, "合成の未登録(架空)", "1", "金額", "円", SRC_KYOUKAI]],
    # 「表として読めない」で返すもの
    "atai_taishou_kuuran": [HEAD_ATAI, ["", I_GETSUGAKU, "100000", "金額", "円", SRC_KYOUKAI]],
    "atai_tani_kuuran": [HEAD_ATAI, [T_A, I_GETSUGAKU, "100000", "金額", "", SRC_KYOUKAI]],
    "atai_shurui_mitouroku": [HEAD_ATAI,
                              [T_A, I_GETSUGAKU, "100000", "料率", "円", SRC_KYOUKAI]],
    "atai_yomenai": [HEAD_ATAI, [T_A, I_GETSUGAKU, "十万", "金額", "円", SRC_KYOUKAI]],
    "atai_shisuu": [HEAD_ATAI, [T_A, I_GETSUGAKU, "1E5", "金額", "円", SRC_KYOUKAI]],
    "atai_kansan_hasuu": [HEAD_ATAI, [T_B, I_NISSUU, "0.5", "日数", "日", SRC_KOUROU]],
}

KOWASHITA_TANI: dict[str, list[list[str]]] = {
    "tani_seisuu_shousuu": [HEAD_TANI, [I_NISSUU, "日数", "日", "1", "", ""]],
    "tani_kakeru_nashi": [HEAD_TANI, [I_JIKAN, "時間", "分", "0", "時間", ""]],
    "tani_aite_nashi": [HEAD_TANI, [I_JIKAN, "時間", "分", "0", "", "60"]],
    "tani_shurui_mitouroku": [HEAD_TANI, [I_GETSUGAKU, "料率", "円", "0", "", ""]],
    "tani_juufuku": [HEAD_TANI, [I_GETSUGAKU, "金額", "円", "0", "", ""],
                     [I_GETSUGAKU, "金額", "千円", "0", "", ""]],
}


def write_all(dest: Path | None = None) -> list[Path]:
    d = dest or HERE
    out: list[Path] = [
        B.write_csv(d / "atai_a.csv", ATAI_A),
        B.write_csv(d / "atai_kansan.csv", ATAI_KANSAN),
        B.write_csv(d / "obi_a.csv", OBI_A),
        B.write_csv(d / "obi_ten.csv", OBI_TEN),
        B.write_csv(d / "obi_chou.csv", OBI_CHOU),
        B.write_csv(d / "obi_koumoku_nashi.csv", OBI_KOUMOKU_NASHI),
        B.write_csv(d / "tani_a.csv", TANI_A),
    ]
    for name, rows in {**KOWASHITA_OBI, **KOWASHITA_ATAI, **KOWASHITA_TANI}.items():
        out.append(B.write_csv(d / "kowashita" / f"{name}.csv", rows))
    # ヘッダだけの表(3 種とも「表として読めない」で返る)
    out.append(B.write_csv(d / "kowashita" / "atai_0gyou.csv", [HEAD_ATAI]))
    out.append(B.write_csv(d / "kowashita" / "obi_0gyou.csv", [HEAD_OBI]))
    out.append(B.write_csv(d / "kowashita" / "tani_0gyou.csv", [HEAD_TANI]))
    # 列そのものが足りない表
    out.append(B.write_csv(d / "kowashita" / "obi_retsu_nashi.csv",
                           [HEAD_OBI[:-1], [r for r in OBI_A[1]][:-1]]))
    return out


if __name__ == "__main__":
    for p in write_all():
        print(f"wrote {p}")
