"""edge_close の合成 fixture。**実在の料率も金額も行 id も 1 つも入っていない。**

数表の名前は `甲表` `乙表` …、次元の値は `地域=甲1` のような記号で、どれも架空だ。この部品は
鍵と日付の欄だけを読むので、中身が何でも同じように動く。写したのは形、つまり

  - 終了が開いたままの行が在る(閉じる端がある)
  - 終了が閉じていて、その次の単位が足す行の開始より後ろの行が在る(閉じ忘れると重なる)
  - 終了が閉じていて、その次の単位が足す行の開始より前の行が在る(閉じると隙間ができる)
  - 同じ鍵の既存の行が 1 つも無い提案が在る(閉じる端が無い)
  - 終了の欄が空で、開いている印も無い行が在る(終了が書かれていない = 端として指さない)
  - 有効期間は隣接しているのに、知識終了の印が開いたままの行が在る
  - 既存の行と足す行の開始が同じ日で、どちらも終了が開いている組が在る
  - 施行日未定の印が立った提案が在る(開始が空のまま登録されている)
  - 区間の閉じ方が `含む` の rule と `含まない` の rule が混ざり、端の単位も 日 と 月 が混ざる
  - どの足す行からも端として指されなかった既存の行が在る

の 10 で、これは私の記録に残っている形だ。記録そのものは出さない。**足す行を 17 件にして
あるのは、記録に出てこない形(別枠 3 種・二重開始・知識期間の開き)も 1 件ずつ入れて
数えるため。**

書くもの(どれも決定論。同じ実行で同じバイト列になる)。

  rows_a.csv          既存の行の表 15 行
  adds_a.csv          足す行の表 17 行
  declares_a.csv      閉じ方の宣言表 5 行
  kowashita/*.csv     理由コードと「表として読めない」を出すために 1 か所崩した表

使い方: python fixtures/make_fixtures.py   (この置き場に書き直す)
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import edge_close as H  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの(テストがその行を開いて語の在ることを見る)
SRC_SPAN = "articles/22_span_split.md L13"      # 期間を境界で切る側の記事
SRC_RANK = "articles/27_rank_clash.md L13"      # 順位で裁定する側の記事

GYOU = "私の行の記録(非公開)L32"
TEIAN = "私の提案の記録(非公開)L70"
SENGEN = "私の閉じ方の記録(非公開)L109"

KOU, OTSU, HEI, TEI, BO = "甲表", "乙表", "丙表", "丁表", "戊表"
KI = "己表"          # 宣言表に無い rule(別枠へ落ちる)

MARK = "*"           # 未指定次元の記号(宣言表に書く。道具はこれを展開しない)
G1 = "G1"            # 隙間を許す理由コード(記録するだけで判定に使わない)

OPEN = H.HIRAKI


def declares_rows() -> list[list[str]]:
    """閉じ方の宣言表 5 行。**区間の閉じ方と端の単位を rule ごとに分ける。**"""
    return [
        list(H.DECLARE_COLUMNS),
        [KOU, H.FUKUMANAI, H.TSUKI, H.YURUSANAI, "", MARK, H.TOJIRU, "0;10;20", "",
         SENGEN],
        [OTSU, H.FUKUMANAI, H.TSUKI, H.YURUSANAI, "", MARK, H.TOJINAI, "0;10;20", "",
         SENGEN],
        [HEI, H.FUKUMU, H.HI, H.YURUSU, G1, MARK, H.TOJIRU, "0;10;20", "", SRC_SPAN],
        [TEI, H.FUKUMU, H.TSUKI, H.YURUSANAI, "", MARK, H.TOJINAI, "0;10", "", SRC_RANK],
        [BO, H.FUKUMANAI, H.HI, H.YURUSANAI, "", MARK, H.TOJIRU, "0;10;20", "", SENGEN],
    ]


def rows_rows() -> list[list[str]]:
    """既存の行の表 15 行。開いている行・閉じている行・終了が書かれていない行を混ぜる。"""
    return [
        list(H.EXISTING_COLUMNS),
        # 開いたまま(= 閉じる端がある)
        ["E01", KOU, "地域=甲1", "0", "2025-04", "", OPEN, "2025-03", "", OPEN, GYOU],
        # 閉じているが、次の単位が足す行の開始より後ろ(= 重なる)
        ["E02", KOU, "地域=甲2", "0", "2025-04", "2026-04", "", "2025-03", "2026-03", "",
         GYOU],
        # 未指定の記号が入った行(どの足す行からも指されない)
        ["E03", KOU, f"地域={MARK}", "10", "2024-04", "2025-04", "", "2024-03",
         "2025-03", "", GYOU],
        ["E04", OTSU, "等級帯=乙1", "0", "2024-09", "", OPEN, "2024-06", "", OPEN, GYOU],
        ["E05", OTSU, "等級帯=乙2", "0", "2024-09", "2026-09", "", "2024-06", "2026-06",
         "", GYOU],
        # 閉じ方が `含む` の rule。終了の次の単位がちょうど足す行の開始(= 隣接)
        ["E06", HEI, "種別=丙1", "0", "2025-04-01", "2026-03-31", "", "2025-01-01",
         "2026-01-01", "", GYOU],
        # 1 日だけ手前で閉じている(= 隙間)
        ["E07", HEI, "種別=丙2", "0", "2025-04-01", "2026-03-30", "", "2025-01-01",
         "2026-01-01", "", GYOU],
        # 同じ鍵で 2 行。後ろの行が開いている(= 二重開始の相手)
        ["E08", TEI, "区分=丁1", "0", "2025-10", "", OPEN, "2025-09", "", OPEN, GYOU],
        ["E09", TEI, "区分=丁1", "0", "2024-10", "2025-09", "", "2024-06", "2025-06", "",
         GYOU],
        ["E10", BO, "都道府県=戊1", "0", "2024-10-01", "2025-10-01", "", "2024-09-01",
         "", OPEN, GYOU],
        ["E11", BO, "都道府県=戊2", "0", "2024-10-01", "", OPEN, "2024-09-01", "", OPEN,
         GYOU],
        # 終了の欄が空で、開いている印も無い(= 終了が書かれていない)
        ["E12", KOU, "地域=甲3", "0", "2025-04", "", "", "2025-03", "", OPEN, GYOU],
        ["E13", OTSU, "等級帯=乙3", "20", "2025-09", "2026-09", "", "2025-06", "2026-06",
         "", GYOU],
        # 有効期間は閉じているが、知識終了が開いたまま(= ⑤ の相手)
        ["E14", HEI, "種別=丙3", "0", "2025-04-01", "2026-03-31", "", "2025-01-01", "",
         OPEN, GYOU],
        ["E15", OTSU, "等級帯=乙4", "0", "2025-09", "", OPEN, "2025-06", "", OPEN, GYOU],
    ]


def adds_rows() -> list[list[str]]:
    """足す行の表 17 行。6 値 + 別枠 3 種のすべてに 1 件以上の道を付ける。"""
    o = ["", OPEN]      # valid_to は空 + 開いている印(新しく開く行)
    return [
        list(H.ADD_COLUMNS),
        ["A01", KOU, "地域=甲1", "0", "2026-04", "", *o, "2026-03", "", OPEN, TEIAN],
        ["A02", KOU, "地域=甲2", "0", "2026-02", "", *o, "2026-01", "", OPEN, TEIAN],
        ["A03", HEI, "種別=丙2", "0", "2026-04-01", "", *o, "2025-12-01", "", OPEN,
         TEIAN],
        ["A04", KOU, "地域=甲3", "0", "2026-04", "", *o, "2026-03", "", OPEN, TEIAN],
        ["A05", KOU, "地域=甲9", "0", "2026-04", "", *o, "2026-03", "", OPEN, TEIAN],
        ["A06", HEI, "種別=丙3", "0", "2026-04-01", "", *o, "2025-12-01", "", OPEN,
         TEIAN],
        ["A07", TEI, "区分=丁1", "0", "2025-10", "", *o, "2025-09", "", OPEN, TEIAN],
        ["A08", OTSU, "等級帯=乙1", "0", "2026-09", "", *o, "2026-06", "", OPEN, TEIAN],
        ["A09", BO, "都道府県=戊2", "0", "2025-10-01", "", *o, "2025-09-01", "", OPEN,
         TEIAN],
        ["A10", OTSU, "等級帯=乙3", "20", "2026-09", "", *o, "2026-04", "", OPEN, TEIAN],
        # 施行日未定の印。開始が空のまま登録されている
        ["A11", OTSU, "等級帯=乙4", "0", "", H.SEIREI, *o, "2026-06", "", OPEN, TEIAN],
        # 別枠: 鍵が宣言表に無い
        ["A12", KI, "地域=己1", "0", "2026-04", "", *o, "2026-03", "", OPEN, TEIAN],
        # 別枠: 日付の書式が宣言と違う(甲表の端の単位は 月)
        ["A13", KOU, "地域=甲1", "0", "2026-04-01", "", *o, "2026-03", "", OPEN, TEIAN],
        # 別枠: 施行日未定の印が立っているのに開始が入っている
        ["A14", BO, "都道府県=戊3", "0", "2026-04-01", H.SEIREI, *o, "2026-03-01", "",
         OPEN, TEIAN],
        ["A15", HEI, "種別=丙1", "0", "2026-04-01", "", *o, "2025-12-01", "", OPEN,
         TEIAN],
        ["A16", OTSU, "等級帯=乙2", "0", "2026-04", "", *o, "2026-04", "", OPEN, TEIAN],
        ["A17", BO, "都道府県=戊1", "0", "2025-11-01", "", *o, "2025-08-01", "", OPEN,
         TEIAN],
    ]


def _rows(rows: list[list[str]], number: int, column: int, value: str) \
        -> list[list[str]]:
    """1 か所だけ差し替えた写し(number は 2 から = CSV の行番号)。"""
    out = [list(r) for r in rows]
    out[number - 1][column] = value
    return out


def kowashita_rows() -> dict[str, list[list[str]]]:
    """既存の行の表を 1 か所崩した表。前半は理由コード、後半は「表として読めない」。"""
    base = rows_rows()
    col = {c: i for i, c in enumerate(H.EXISTING_COLUMNS)}
    out = {
        # 1 件も仕分けずに止まる(理由コード)
        "rows_shutten_kuuran": _rows(base, 2, col["source"], ""),
        "rows_row_id_juufuku": base + [list(base[2])],
        "rows_hiraki_to_shuuryou": _rows(base, 3, col["valid_open"], OPEN),
        "rows_shuuryou_gyakuten": _rows(base, 3, col["valid_to"], "2024-04"),
        "rows_known_gyakuten": _rows(base, 3, col["known_to"], "2024-02"),
        "rows_hizuke_shoshiki": _rows(base, 3, col["valid_to"], "2026-04-01"),
        "rows_junni_tourokugai": _rows(base, 9, col["priority"], "20"),
        "rows_kagi_nashi": _rows(base, 2, col["rule_id"], KI),
        # 表として読めない
        "rows_retsu_nashi": [list(H.EXISTING_COLUMNS)[:-1]] + [r[:-1] for r in base[1:]],
        "rows_0gyou": [list(H.EXISTING_COLUMNS)],
        "rows_row_id_kuuran": _rows(base, 2, col["row_id"], ""),
        "rows_dims_katachi": _rows(base, 2, col["dims"], "地域甲1"),
        "rows_dims_kuuran": _rows(base, 2, col["dims"], ""),
        "rows_dims_onaji_jigen": _rows(base, 2, col["dims"], "地域=甲1;地域=甲2"),
        "rows_junni_shousuu": _rows(base, 2, col["priority"], "0.5"),
        "rows_hiraki_gai": _rows(base, 2, col["valid_open"], "たぶん"),
        "rows_kaishi_kuuran": _rows(base, 2, col["valid_from"], ""),
    }
    return out


def kowashita_adds() -> dict[str, list[list[str]]]:
    """足す行の表を 1 か所崩した表(どれも「表として読めない」= 1 件も仕分けない)。"""
    base = adds_rows()
    col = {c: i for i, c in enumerate(H.ADD_COLUMNS)}
    return {
        "adds_retsu_nashi": [list(H.ADD_COLUMNS)[:-1]] + [r[:-1] for r in base[1:]],
        "adds_0gyou": [list(H.ADD_COLUMNS)],
        "adds_add_id_kuuran": _rows(base, 2, col["add_id"], ""),
        "adds_seirei_gai": _rows(base, 2, col["pending_order"], "たぶん"),
        "adds_hiraki_to_shuuryou": _rows(base, 2, col["valid_to"], "2027-04"),
        "adds_kaishi_kuuran": _rows(base, 2, col["valid_from"], ""),
        "adds_known_kaishi_kuuran": _rows(base, 2, col["known_from"], ""),
        "adds_dims_katachi": _rows(base, 2, col["dims"], "地域=甲1=甲2"),
    }


def kowashita_declares() -> dict[str, list[list[str]]]:
    """閉じ方の宣言表を 1 か所崩した表。"""
    base = declares_rows()
    col = {c: i for i, c in enumerate(H.DECLARE_COLUMNS)}
    return {
        # 1 件も仕分けずに止まる(理由コード)
        "declares_rule_juufuku": base + [list(base[1])],
        "declares_riyuu_nashi": _rows(base, 4, col["reason_code"], ""),
        "declares_shutten_kuuran": _rows(base, 2, col["source"], ""),
        # 表として読めない
        "declares_retsu_nashi": [list(H.DECLARE_COLUMNS)[:-1]] + [r[:-1]
                                                                  for r in base[1:]],
        "declares_0gyou": [list(H.DECLARE_COLUMNS)],
        "declares_tanni_gai": _rows(base, 2, col["edge_unit"], "年"),
        "declares_tojikata_gai": _rows(base, 2, col["end_included"], "たぶん"),
        "declares_sukima_gai": _rows(base, 2, col["gap_allowed"], "たぶん"),
        "declares_known_gai": _rows(base, 2, col["close_known"], "たぶん"),
        "declares_kigou_kuuran": _rows(base, 2, col["unspecified_mark"], ""),
        "declares_junni_kuuran": _rows(base, 2, col["priorities"], ""),
    }


def write_all() -> list[Path]:
    out = [H.write_csv(HERE / "rows_a.csv", rows_rows()),
           H.write_csv(HERE / "adds_a.csv", adds_rows()),
           H.write_csv(HERE / "declares_a.csv", declares_rows())]
    broken = HERE / "kowashita"
    for name, rows in {**kowashita_rows(), **kowashita_adds(),
                       **kowashita_declares()}.items():
        out.append(H.write_csv(broken / f"{name}.csv", rows))
    return out


if __name__ == "__main__":
    for p in write_all():
        print(f"wrote {p}")
