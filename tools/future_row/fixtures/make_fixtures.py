"""future_row の合成 fixture。値(料率・金額)は 1 つも入れない(この部品は値の列を持たない)。

行 id・rule id・基準日 id・対象の次元の名前と値・公表元・日付は **全て架空** だ。実在の料率・
金額・取引先名は 1 つも入っていない。写したのは形だけ、つまり「前の行を閉じたうえで未来の行が
並ぶ」「同じ rule に効き始める日の違う行が 3 本並ぶ(段階施行)」「効き始める日の欄が空のまま
持つ行がある」「もう効き終わった行が残っている」という 4 つで、これは私の棚卸し記録に残って
いる形だ。記録そのものは出さない。

書くもの(どれも決定論。同じ実行で同じバイト列になる)。

  gyou_a.csv             行の表 10 行(rule 5 本ぶん)
  gyou_kouhyoubi.csv     gyou_a の 1 欄だけ、効き始める日を知った日(公布日)で代用した表
  gyou_kuuran_ume.csv    gyou_a の 1 欄だけ、空の効き始める日を年度初めで埋めた表
  gyou_kasanari.csv      gyou_a の 1 欄だけ、前の行を閉じずに効き始める日を早めた表
  sengen_a.csv           状態の宣言 5 行(rule 1 本が 1 行)
  kijunbi_a.csv          基準日の表 3 行
  kowashita/*.csv        止まる理由コードと「表として読めない」を出すために 1 か所崩した表

使い方: python fixtures/make_fixtures.py   (この置き場に書き直す)
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import future_row as F  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの(テストがその行を開いて語の在ることを見る)
SRC_NURI = "articles/07_asof_table.md L32"      # 「塗り直した」
SRC_NOKOSU = "articles/09_update_ledger.md L13"  # 「1 行残り」
SRC_UMENAI = "articles/22_span_split.md L15"     # 「埋めない」
SRC_SEIREI = "articles/22_span_split.md L46"     # 「ゆだねられて」
SRC_YOMIKAE = "articles/27_rank_clash.md L15"    # 「読み替えず」

# 非公開の棚卸し記録(パス・機器名・取引先名は書かない)
TANAOROSHI = "私の棚卸し記録(非公開)"

# 空欄の記号(宣言された記号。これだけが「欄が空」になる)
MARK = F.MARK

# 対象の次元の名前と値(合成)。業種の語彙は 1 つも入れない
DIM = "次元A"
A1, A2, A3, A4, A5 = "a1", "a2", "a3", "a4", "a5"
A9 = "a9"   # 行 id を重複させた崩した表だけで使う値(重なりを起こさないため別の対象にする)

# 公表元(架空)。判定には使わず素通しする欄
KOU1, KOU2, KOU3 = "公表元甲(架空)", "公表元乙(架空)", "公表元丙(架空)"
KOU4, KOU5 = "公表元丁(架空)", "公表元戊(架空)"

STATES_TEXT = F.STATE_SEP.join([
    f"{F.STATES[0]}=効き終わる日が基準日以前",
    f"{F.STATES[1]}=基準日が効いている期間の中",
    f"{F.STATES[2]}=効き始める日が基準日より後",
    f"{F.STATES[3]}=効き始める日が宣言された空の記号",
])

HEAD_GYOU = list(F.GYOU_COLUMNS)
HEAD_SENGEN = list(F.SENGEN_COLUMNS)
HEAD_KIJUNBI = list(F.KIJUNBI_COLUMNS)


def seg(value: str) -> str:
    return f"{DIM}{F.SEG_EQ}{value}"


# ---------------------------------------------------------------- 行の表


def gyou_rows(vf_kouhyoubi: str = "2005-10-01", vf_kuuran: str = MARK,
              vf_kasanari: str = "2005-07-01") -> list[list[str]]:
    """行の表 10 行。rule ごとに、効き始めの前後が分かれる形を 1 つずつ置いてある。"""
    return [
        HEAD_GYOU,
        # R01 本則の行と、公布済・効き始める日が確定している未来の行(前の行は閉じてある)
        ["G01", "R01", "2001-04-01", "2001-04-01", "2007-10-01", seg(A1), "0",
         KOU1, SRC_NURI],
        ["G02", "R01", "2004-06-01", "2007-10-01", MARK, seg(A1), "0",
         KOU1, TANAOROSHI],
        # R02 段階施行。効き始める日の違う行が 3 本、順に閉じながら並ぶ
        ["G03", "R02", "2002-04-01", "2002-04-01", "2005-07-01", seg(A2), "0",
         KOU2, SRC_NOKOSU],
        ["G04", "R02", "2004-06-01", vf_kasanari, "2006-07-01", seg(A2), "0",
         KOU2, TANAOROSHI],
        ["G05", "R02", "2004-06-01", "2006-07-01", MARK, seg(A2), "0",
         KOU2, TANAOROSHI],
        # R03 効き始める日の欄が空のまま持つ行(順位の欄も空のまま)
        ["G06", "R03", "2003-04-01", "2003-04-01", MARK, seg(A3), "0",
         KOU3, SRC_YOMIKAE],
        ["G07", "R03", "2004-06-01", vf_kuuran, MARK, seg(A3), "",
         KOU3, SRC_SEIREI],
        # R04 新設の 1 行だけ。知った日より後に効き始める
        ["G08", "R04", "2004-06-01", vf_kouhyoubi, MARK, seg(A4), "0",
         KOU4, SRC_UMENAI],
        # R05 もう効き終わった行と、いま効いている行
        ["G09", "R05", "2001-04-01", "2001-04-01", "2004-04-01", seg(A5), "0",
         KOU5, TANAOROSHI],
        ["G10", "R05", "2004-02-01", "2004-04-01", MARK, seg(A5), "0",
         KOU5, TANAOROSHI],
    ]


# ---------------------------------------------------------------- 状態の宣言


def sengen_rows() -> list[list[str]]:
    """rule ごとに「使う状態」「空のときの扱い」「空欄の記号」を 1 行で宣言する。"""
    return [
        HEAD_SENGEN,
        ["R01", STATES_TEXT, F.BLANK_RULES[0], F.OPEN_RULES[0], MARK, SRC_NURI],
        ["R02", STATES_TEXT, F.BLANK_RULES[0], F.OPEN_RULES[0], MARK, SRC_NOKOSU],
        ["R03", STATES_TEXT, F.BLANK_RULES[0], F.OPEN_RULES[0], MARK, SRC_SEIREI],
        ["R04", STATES_TEXT, F.BLANK_RULES[0], F.OPEN_RULES[0], MARK, SRC_UMENAI],
        ["R05", STATES_TEXT, F.BLANK_RULES[0], F.OPEN_RULES[0], MARK, SRC_YOMIKAE],
    ]


# ---------------------------------------------------------------- 基準日の表


def kijunbi_rows() -> list[list[str]]:
    """基準日 3 件。A01 の翌日が A02 で、その日に効き始める行がある。"""
    return [
        HEAD_KIJUNBI,
        ["A01", "2005-06-30", SRC_NURI, F.SWAPS[0]],
        ["A02", "2005-07-01", TANAOROSHI, ""],
        ["A03", "2008-01-01", TANAOROSHI, ""],
    ]


# ---------------------------------------------------------------- 崩した表


def drop(rows: list[list[str]], col: int, value: str, at: int = 1) -> list[list[str]]:
    """1 か所だけ書き換えた写しを作る(元の表は書き換えない)。"""
    out = [list(r) for r in rows]
    out[at][col] = value
    return out


def without_column(rows: list[list[str]], name: str) -> list[list[str]]:
    i = rows[0].index(name)
    return [[c for j, c in enumerate(r) if j != i] for r in rows]


def kowashita() -> dict[str, list[list[str]]]:
    """止まる理由コード 7 個と「表として読めない」を出すための表。"""
    g, s, k = gyou_rows(), sengen_rows(), kijunbi_rows()
    out: dict[str, list[list[str]]] = {}

    # --- 止まる(理由コードが返る)
    out["gyou_shutten_nashi"] = drop(g, 8, "")                      # 出典の欄が空
    out["sengen_shutten_nashi"] = drop(s, 5, "")                    # 出典の欄が空
    out["kijunbi_shutten_nashi"] = drop(k, 2, "")                   # 出典の欄が空
    out["gyou_id_juufuku"] = g + [["G01", "R04", "2004-06-01", "2009-01-01", MARK,
                                   seg(A9), "0", KOU4, TANAOROSHI]]  # 行 id の重複
    out["gyou_shitta_ato"] = drop(g, 2, "2005-10-01", at=8)         # 知った日 > 基準日
    out["gyou_sakanobori"] = drop(g, 3, "2003-01-01", at=8)         # 知った日より前に効き始める
    out["gyou_owari_mae"] = drop(g, 4, "2000-01-01")                # 効き終わる日 ≦ 効き始める日
    out["gyou_kigou_gai"] = drop(g, 3, "未定", at=7)                # 宣言に無い記号
    out["sengen_juufuku"] = s + [["R01", STATES_TEXT, F.BLANK_RULES[0],
                                  F.OPEN_RULES[0], MARK, TANAOROSHI]]  # 宣言が 2 行

    # --- 表として読めない(終了コード 2。理由コードには混ぜない)
    out["gyou_retsu_nashi"] = without_column(g, "priority")
    out["gyou_0gyou"] = [HEAD_GYOU]
    out["gyou_id_kuuran"] = drop(g, 0, "")
    out["gyou_rule_kuuran"] = drop(g, 1, "")
    out["gyou_rule_gai"] = drop(g, 1, "R09")
    out["gyou_shitta_kuuran"] = drop(g, 2, "")
    out["gyou_hizuke_katachi"] = drop(g, 3, "2001/04/01")
    out["gyou_hizuke_koyomi"] = drop(g, 3, "2001-02-30")
    out["gyou_vf_kuuran"] = drop(g, 3, "")
    out["gyou_vt_kuuran"] = drop(g, 4, "")
    out["gyou_seg_kuuran"] = drop(g, 5, "")
    out["gyou_seg_katachi"] = drop(g, 5, f"{DIM}{A1}")
    out["gyou_seg_atai_kuuran"] = drop(g, 5, f"{DIM}{F.SEG_EQ}")
    out["gyou_seg_onaji"] = drop(g, 5, f"{seg(A1)}{F.SEG_SEP}{seg(A2)}")
    out["gyou_seg_kigou"] = drop(g, 5, seg("*"))
    out["gyou_juni_seisuu"] = drop(g, 6, "高")
    out["sengen_retsu_nashi"] = without_column(s, "open_rule")
    out["sengen_0gyou"] = [HEAD_SENGEN]
    out["sengen_id_kuuran"] = drop(s, 0, "")
    out["sengen_states_gai"] = drop(s, 1, STATES_TEXT.replace(F.STATES[2],
                                                              "そのうち効き始める"))
    out["sengen_states_katachi"] = drop(s, 1, STATES_TEXT.replace(
        f"{F.STATES[0]}{F.SEG_EQ}", F.STATES[0]))
    out["sengen_states_imi_kuuran"] = drop(s, 1, STATES_TEXT.replace(
        "効き終わる日が基準日以前", ""))
    out["sengen_states_juufuku"] = drop(s, 1, STATES_TEXT.replace(
        F.STATES[1], F.STATES[0]))
    out["sengen_blank_gai"] = drop(s, 2, "基準日で埋める")
    out["sengen_open_gai"] = drop(s, 3, "基準日で閉じる")
    out["sengen_mark_kuuran"] = drop(s, 4, "")
    out["kijunbi_retsu_nashi"] = without_column(k, "asof")
    out["kijunbi_0gyou"] = [HEAD_KIJUNBI]
    out["kijunbi_id_kuuran"] = drop(k, 0, "")
    out["kijunbi_juufuku"] = k + [["A01", "2009-01-01", TANAOROSHI, ""]]
    out["kijunbi_hizuke_katachi"] = drop(k, 1, "2005 年 6 月 30 日")
    out["kijunbi_swap_gai"] = drop(k, 3, "ランダム")
    out["kijunbi_swap_futatsu"] = drop(k, 3, F.SWAPS[1], at=2)
    return out


# ---------------------------------------------------------------- 書き出し

def main() -> None:
    written: list[Path] = []
    base = {
        "gyou_a": gyou_rows(),
        "gyou_kouhyoubi": gyou_rows(vf_kouhyoubi="2004-06-01"),
        "gyou_kuuran_ume": gyou_rows(vf_kuuran="2005-04-01"),
        "gyou_kasanari": gyou_rows(vf_kasanari="2004-06-01"),
        "sengen_a": sengen_rows(),
        "kijunbi_a": kijunbi_rows(),
    }
    for name, rows in base.items():
        written.append(F.write_csv(HERE / f"{name}.csv", rows))
    for name, rows in kowashita().items():
        written.append(F.write_csv(HERE / "kowashita" / f"{name}.csv", rows))
    print(f"書いた: {len(written)} 枚")


if __name__ == "__main__":
    main()
