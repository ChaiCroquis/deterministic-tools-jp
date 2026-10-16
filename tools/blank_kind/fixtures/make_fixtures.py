"""blank_kind の合成 fixture。値は全て架空で、実データ・実在の金額や率は 1 つも入れない。

空欄の類型の名前(値が未取得・要照合・仮置き・未収録・施行日待ち・該当なし・手で追加・
全部に当たる など)だけは、私の棚卸し記録(非公開)に文言として残っている区別を写している。
**値そのものは写していない**(その記録自身が「値は未取得」「要照合」「未実施」と書いている
ため)。下の表に出てくる数は全て、私が決めた合成の値だ。

書くもの(どれも決定論。同じ実行で同じバイト列になる)。

  atai_a.csv         値の表 12 行。対象 3 × 項目 4 のマスが 1 行ずつ埋まっている
  atai_zenbu.csv     atai_a の 1 マスだけ、値の列の空欄に「全部に当たる」を書いた表
  atai_zero.csv      atai_a の 1 マスだけ、0 が正規の値でない項目に 0 を書いた表
  koumoku_a.csv      項目の宣言 4 行。1 列だけ「全部に当たる」列
  koumoku_yurui.csv  koumoku_a の 1 欄だけ、値の列にも「全部に当たる」を許した表
  riyuu_a.csv        理由コードの宣言 9 行
  kowashita/*.csv    止まる理由コードと「表として読めない」を出すために 1 か所だけ崩した表

使い方: python fixtures/make_fixtures.py   (この置き場に書き直す)
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import blank_kind as B  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの(テストがその行を開いて語の在ることを見る)
SRC_JUNI = "articles/07_asof_table.md L15"        # 「どちらが勝つかは順位の列に書く」
SRC_KITEI = "articles/08_formula_table.md L42"    # 「既定そのものを持たない」
SRC_ANBUN = "articles/22_span_split.md L16"       # 「按分も日割りも無い」
SRC_KAZOERU = "articles/23_band_edge.md L16"      # 「別の欄で数えて出す」

# 出典(動かした主体 + 非公開の棚卸し記録)。主体の名前は公表されている情報
TANAOROSHI = "私の棚卸し記録(非公開)"
SRC_KYOUKAI = f"協会けんぽ / {TANAOROSHI}"
SRC_KOUROU = f"厚生労働省 / {TANAOROSHI}"
SRC_NENKIN = f"日本年金機構 / {TANAOROSHI}"

# 項目(合成。棚卸しに在る「意味の違う空欄」の形だけを写し、値は写していない)
I_KINGAKU = "合成の金額の列(架空)"
I_TSUKISUU = "合成の月数の列(架空)"
I_NENREI = "合成の年齢の列(架空)"
I_NINZUU = "合成の人数の列(架空)"

T_A, T_B, T_C = "合成の区分A", "合成の区分B", "合成の区分C"

# 理由コード(合成)
R_MISHUTOKU = "値が未取得"
R_YOUSHOUGOU = "要照合"
R_KARIOKI = "仮置き"
R_MISHUUROKU = "未収録"
R_YOBIDASHI = "呼び出し側で補う"
R_SHIKOUBI = "施行日待ち"
R_GAITOU_NASHI = "該当なし"
R_TE_DE = "手で追加"
R_ZENBU = "全部に当たる"

HEAD_ATAI = list(B.ATAI_COLUMNS)
HEAD_KOUMOKU = list(B.KOUMOKU_COLUMNS)
HEAD_RIYUU = list(B.RIYUU_COLUMNS)

# ---------------------------------------------------------------- 理由コードの宣言

RIYUU_A = [
    HEAD_RIYUU,
    [R_MISHUTOKU, "行は在るが値をまだ取っていない", B.HOWS[0], SRC_KYOUKAI],
    [R_YOUSHOUGOU, "値は在るが出典の照合が済んでいない", B.HOWS[0], SRC_KYOUKAI],
    [R_KARIOKI, "確認できた範囲の先頭に仮に置いた", B.HOWS[0], SRC_NENKIN],
    [R_MISHUUROKU, "行そのものをまだ入れていない", B.HOWS[0], SRC_NENKIN],
    [R_YOBIDASHI, "数式の一部をまだ実装していない", B.HOWS[0], SRC_KITEI],
    [R_SHIKOUBI, "施行日が決まらないので登録だけする", B.HOWS[0], SRC_KOUROU],
    [R_GAITOU_NASHI, "制度として当たらない", B.HOWS[2], SRC_KOUROU],
    [R_TE_DE, "自動で見つける手だてが無いので手で足す", B.HOWS[0], SRC_ANBUN],
    [R_ZENBU, "絞り込みを指定していない", B.HOWS[1], SRC_JUNI],
]

# ---------------------------------------------------------------- 項目の宣言

KOUMOKU_A = [
    HEAD_KOUMOKU,
    [I_KINGAKU, "金額", B.REASON_SEP.join([R_MISHUTOKU, R_YOUSHOUGOU, R_KARIOKI]),
     B.HAI, B.IIE, SRC_KYOUKAI],
    [I_TSUKISUU, "月数", B.REASON_SEP.join([R_MISHUUROKU, R_YOBIDASHI, R_SHIKOUBI]),
     B.IIE, B.IIE, SRC_NENKIN],
    [I_NENREI, "年数", R_ZENBU, B.HAI, B.HAI, SRC_JUNI],
    [I_NINZUU, "人数", B.REASON_SEP.join([R_GAITOU_NASHI, R_TE_DE]),
     B.HAI, B.IIE, SRC_KAZOERU],
]

# 1 欄だけ違う: 値の列(金額)にも「全部に当たる」を許した表
KOUMOKU_YURUI = [
    HEAD_KOUMOKU,
    [I_KINGAKU, "金額",
     B.REASON_SEP.join([R_MISHUTOKU, R_YOUSHOUGOU, R_KARIOKI, R_ZENBU]),
     B.HAI, B.IIE, SRC_KYOUKAI],
    *[list(r) for r in KOUMOKU_A[2:]],
]

# さらに 1 欄: 金額を「全部に当たる」列にすると、同じ空欄記号に 2 つの意味が宣言される
KOUMOKU_FUTATSU = [
    HEAD_KOUMOKU,
    [I_KINGAKU, "金額",
     B.REASON_SEP.join([R_MISHUTOKU, R_YOUSHOUGOU, R_KARIOKI, R_ZENBU]),
     B.HAI, B.HAI, SRC_KYOUKAI],
    *[list(r) for r in KOUMOKU_A[2:]],
]

# ---------------------------------------------------------------- 値の表


def atai_rows(swap: str = "逆順") -> list[list[str]]:
    """対象 3 × 項目 4 = 12 マスが 1 行ずつ埋まった表。"""
    return [
        [T_A, I_KINGAKU, "120000", "", SRC_KYOUKAI, swap],
        [T_B, I_KINGAKU, "", R_MISHUTOKU, SRC_KYOUKAI, ""],
        [T_C, I_KINGAKU, "95000", R_KARIOKI, SRC_KYOUKAI, ""],
        [T_A, I_TSUKISUU, "24", "", SRC_NENKIN, ""],
        [T_B, I_TSUKISUU, "", R_MISHUUROKU, SRC_NENKIN, ""],
        [T_C, I_TSUKISUU, "", R_SHIKOUBI, SRC_KOUROU, ""],
        [T_A, I_NENREI, "", R_ZENBU, SRC_JUNI, ""],
        [T_B, I_NENREI, "60", "", SRC_KITEI, ""],
        [T_C, I_NENREI, "", R_ZENBU, SRC_ANBUN, ""],
        [T_A, I_NINZUU, "0", "", SRC_KOUROU, ""],
        [T_B, I_NINZUU, "", R_GAITOU_NASHI, SRC_KOUROU, ""],
        [T_C, I_NINZUU, "", R_TE_DE, SRC_KAZOERU, ""],
    ]


def sheet(rows: list[list[str]]) -> list[list[str]]:
    return [HEAD_ATAI, *rows]


def edited(**cell: str) -> list[list[str]]:
    """atai_a の 1 マスだけを差し替えた表を作る(どこを 1 か所変えたかが分かる形)。"""
    target, item, col, value = (cell["target"], cell["item"],
                                cell["col"], cell["value"])
    rows = atai_rows()
    j = HEAD_ATAI.index(col)
    for r in rows:
        if r[0] == target and r[1] == item:
            r[j] = value
    return sheet(rows)


ATAI_A = sheet(atai_rows())
# 1 マスだけ: 値の列の空欄に「全部に当たる」を書く(列の種類と返し方が食い違う)
ATAI_ZENBU = edited(target=T_B, item=I_KINGAKU, col="reason", value=R_ZENBU)
# 1 マスだけ: 0 が正規の値でない項目(月数)に 0 を書く
ATAI_ZERO = edited(target=T_A, item=I_TSUKISUU, col="value", value="0")

# ---------------------------------------------------------------- 崩した表

KOWASHITA_ATAI: dict[str, list[list[str]]] = {
    # 止まる理由コードが出る側
    "atai_riyuu_kuuran": edited(target=T_B, item=I_KINGAKU, col="reason", value=""),
    "atai_mitouroku_code": edited(target=T_B, item=I_KINGAKU, col="reason",
                                  value="合成の未登録コード(架空)"),
    "atai_yurusanai_code": edited(target=T_B, item=I_KINGAKU, col="reason",
                                  value=R_GAITOU_NASHI),
    "atai_shutten_nashi": edited(target=T_A, item=I_KINGAKU, col="source", value=""),
    "atai_koumoku_mitouroku": sheet(atai_rows() + [
        [T_A, "合成の未登録の列(架空)", "1", "", SRC_KYOUKAI, ""]]),
    "atai_tarinai": sheet([r for r in atai_rows()
                           if not (r[0] == T_C and r[1] == I_NINZUU)]),
    "atai_juufuku": sheet(atai_rows() + [
        [T_A, I_KINGAKU, "120000", "", SRC_KYOUKAI, ""]]),
    # 「表として読めない」で返る側
    "atai_yomenai": edited(target=T_A, item=I_KINGAKU, col="value", value="十二万"),
    "atai_shisuu": edited(target=T_A, item=I_KINGAKU, col="value", value="1.2E5"),
    "atai_taishou_kuuran": edited(target=T_A, item=I_KINGAKU, col="target", value=""),
    "atai_koumoku_kuuran": edited(target=T_A, item=I_KINGAKU, col="item", value=""),
    "atai_swap_mitouroku": edited(target=T_A, item=I_KINGAKU, col="swap",
                                  value="でたらめ"),
    "atai_swap_futatsu": edited(target=T_B, item=I_KINGAKU, col="swap",
                                value="両端入れ替え"),
}

KOWASHITA_KOUMOKU: dict[str, list[list[str]]] = {
    "koumoku_zero_kuuran": [HEAD_KOUMOKU,
                            [I_KINGAKU, "金額", R_MISHUTOKU, "", B.IIE, SRC_KYOUKAI]],
    "koumoku_retsu_kuuran": [HEAD_KOUMOKU,
                             [I_KINGAKU, "金額", R_MISHUTOKU, B.HAI, "", SRC_KYOUKAI]],
    "koumoku_shurui_kuuran": [HEAD_KOUMOKU,
                              [I_KINGAKU, "", R_MISHUTOKU, B.HAI, B.IIE, SRC_KYOUKAI]],
    "koumoku_shutten_nashi": [HEAD_KOUMOKU,
                              [I_KINGAKU, "金額", R_MISHUTOKU, B.HAI, B.IIE, ""]],
    "koumoku_futatsu": KOUMOKU_FUTATSU,
    "koumoku_shurui_mitouroku": [HEAD_KOUMOKU,
                                 [I_KINGAKU, "料率", R_MISHUTOKU, B.HAI, B.IIE,
                                  SRC_KYOUKAI]],
    "koumoku_juufuku": [HEAD_KOUMOKU,
                        [I_KINGAKU, "金額", R_MISHUTOKU, B.HAI, B.IIE, SRC_KYOUKAI],
                        [I_KINGAKU, "月数", R_MISHUUROKU, B.HAI, B.IIE, SRC_NENKIN]],
    "koumoku_hai_iie": [HEAD_KOUMOKU,
                        [I_KINGAKU, "金額", R_MISHUTOKU, "yes", B.IIE, SRC_KYOUKAI]],
    "koumoku_code_juufuku": [HEAD_KOUMOKU,
                             [I_KINGAKU, "金額",
                              B.REASON_SEP.join([R_MISHUTOKU, R_MISHUTOKU]),
                              B.HAI, B.IIE, SRC_KYOUKAI]],
}

KOWASHITA_RIYUU: dict[str, list[list[str]]] = {
    "riyuu_shutten_nashi": [HEAD_RIYUU,
                            [R_MISHUTOKU, "行は在るが値をまだ取っていない", B.HOWS[0], ""]],
    "riyuu_kaeshikata_mitouroku": [HEAD_RIYUU,
                                   [R_MISHUTOKU, "行は在るが値をまだ取っていない",
                                    "そのまま返す", SRC_KYOUKAI]],
    "riyuu_juufuku": [HEAD_RIYUU,
                      [R_MISHUTOKU, "行は在るが値をまだ取っていない", B.HOWS[0],
                       SRC_KYOUKAI],
                      [R_MISHUTOKU, "別の意味", B.HOWS[2], SRC_KYOUKAI]],
    "riyuu_imi_kuuran": [HEAD_RIYUU, [R_MISHUTOKU, "", B.HOWS[0], SRC_KYOUKAI]],
    "riyuu_code_kuuran": [HEAD_RIYUU,
                          ["", "行は在るが値をまだ取っていない", B.HOWS[0], SRC_KYOUKAI]],
}


def write_all(dest: Path | None = None) -> list[Path]:
    d = dest or HERE
    out: list[Path] = [
        B.write_csv(d / "atai_a.csv", ATAI_A),
        B.write_csv(d / "atai_zenbu.csv", ATAI_ZENBU),
        B.write_csv(d / "atai_zero.csv", ATAI_ZERO),
        B.write_csv(d / "koumoku_a.csv", KOUMOKU_A),
        B.write_csv(d / "koumoku_yurui.csv", KOUMOKU_YURUI),
        B.write_csv(d / "riyuu_a.csv", RIYUU_A),
    ]
    for name, rows in {**KOWASHITA_ATAI, **KOWASHITA_KOUMOKU,
                       **KOWASHITA_RIYUU}.items():
        out.append(B.write_csv(d / "kowashita" / f"{name}.csv", rows))
    # ヘッダだけの表(3 種とも「表として読めない」で返る)
    out.append(B.write_csv(d / "kowashita" / "atai_0gyou.csv", [HEAD_ATAI]))
    out.append(B.write_csv(d / "kowashita" / "koumoku_0gyou.csv", [HEAD_KOUMOKU]))
    out.append(B.write_csv(d / "kowashita" / "riyuu_0gyou.csv", [HEAD_RIYUU]))
    # 列そのものが足りない表
    out.append(B.write_csv(d / "kowashita" / "atai_retsu_nashi.csv",
                           [HEAD_ATAI[:-1], ATAI_A[1][:-1]]))
    out.append(B.write_csv(d / "kowashita" / "koumoku_retsu_nashi.csv",
                           [HEAD_KOUMOKU[:-1], KOUMOKU_A[1][:-1]]))
    out.append(B.write_csv(d / "kowashita" / "riyuu_retsu_nashi.csv",
                           [HEAD_RIYUU[:-1], RIYUU_A[1][:-1]]))
    return out


if __name__ == "__main__":
    for p in write_all():
        print(f"wrote {p}")
