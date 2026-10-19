"""rank_clash の合成 fixture。値(料率・金額)は 1 つも入れない(この部品は値を持たない)。

行 id・rule id・対象 id・次元の名前と値は全て架空だ。**実在の料率・金額・取引先名は 1 つも
入っていない。** 写したのは形だけ、つまり「宣言された記号で書かれた行と具体的に書かれた行が
同じ対象に当たる」「同じ順位の行が 2 本当たる」「順位の欄が空のまま 2 本当たる」「順位では
表せない裁定が要ると宣言に書いてある」という 4 つで、これは私の棚卸し記録に残っている形だ。
記録そのものは出さない。

書くもの(どれも決定論。同じ実行で同じバイト列になる)。

  gyou_a.csv             行の表 9 行(rule 5 本ぶん)
  gyou_kuuran_ume.csv    gyou_a の 1 欄だけ、空欄の順位を 20 に埋めた表
  gyou_guutai.csv        gyou_a の 1 欄だけ、同順位だった具体行の順位を 10 に上げた表
  sengen_a.csv           裁定の宣言 5 行(rule 1 本が 1 行)
  sengen_junide.csv      sengen_a の 1 欄だけ、裁定の種類を「宣言された順位」に変えた表
  taishou_a.csv          対象の表 4 行
  kowashita/*.csv        止まる理由コードと「表として読めない」を出すために 1 か所崩した表

使い方: python fixtures/make_fixtures.py   (この置き場に書き直す)
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import rank_clash as R  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの(テストがその行を開いて語の在ることを見る)
SRC_JUNBAN = "articles/07_asof_table.md L73"    # 「いちばん高い」
SRC_SOTO = "articles/07_asof_table.md L108"     # 「表の外の判断」
SRC_KITEI = "articles/23_band_edge.md L13"      # 「既定にしない」
SRC_MUGEN = "articles/23_band_edge.md L14"      # 「読み替えない」
SRC_KOUHO = "articles/26_basis_map.md L15"      # 「登録済みとして扱わない」

# 出典(動かした主体 + 非公開の棚卸し記録)。主体の名前は公表されている情報
TANAOROSHI = "私の棚卸し記録(非公開)"
SRC_KOUROU = f"厚生労働省 / {TANAOROSHI}"
SRC_KYOUKAI = f"協会けんぽ / {TANAOROSHI}"

# 次元の名前と値(合成)。業種の語彙は 1 つも入れない
DIM_A, DIM_B = "次元A", "次元B"
A1, A2 = "a1", "a2"
B1, B2 = "b1", "b2"
WILD = "*"

PRIORITIES = "0=本則|10=経過措置|20=特例"
HEAD_GYOU = list(R.GYOU_COLUMNS)
HEAD_SENGEN = list(R.SENGEN_COLUMNS)
HEAD_TAISHOU = list(R.TAISHOU_COLUMNS)


def seg(a: str, b: str) -> str:
    return f"{DIM_A}={a}{R.SEG_SEP}{DIM_B}={b}"


# ---------------------------------------------------------------- 行の表


def gyou_rows(priority_kuuran: str = "", priority_guutai: str = "0") -> list[list[str]]:
    """行の表 9 行。rule ごとに、同じ対象に 2 本当たる形を 1 つずつ置いてある。"""
    return [
        HEAD_GYOU,
        # R01 本則と経過措置。順位が違うので 1 本に決まる
        ["G01", "R01", seg(WILD, WILD), "0", SRC_JUNBAN],
        ["G02", "R01", seg(A1, WILD), "10", SRC_KOUROU],
        # R02 宣言された記号の行と具体的な行が、同じ順位のまま当たる
        ["G03", "R02", seg(WILD, WILD), "0", SRC_SOTO],
        ["G04", "R02", seg(A1, WILD), priority_guutai, TANAOROSHI],
        # R03 順位の欄が空のまま 2 本当たる
        ["G05", "R03", seg(WILD, WILD), "0", SRC_KITEI],
        ["G06", "R03", f"{DIM_A}={WILD}{R.SEG_SEP}{DIM_B}={B1}", priority_kuuran,
         TANAOROSHI],
        # R04 1 つの対象にしか当たらない
        ["G07", "R04", seg(A1, B1), "0", SRC_KYOUKAI],
        # R05 順位では表せない裁定が要ると宣言に書いてある rule
        ["G08", "R05", seg(WILD, WILD), "0", SRC_MUGEN],
        ["G09", "R05", seg(A2, WILD), "10", SRC_KOUHO],
    ]


# ---------------------------------------------------------------- 裁定の宣言


def sengen_rows(kind_r05: str = R.KINDS[1]) -> list[list[str]]:
    """rule ごとに「どの裁定で 1 本に絞るか」を 1 行で宣言する。"""
    return [
        HEAD_SENGEN,
        ["R01", R.KINDS[0], PRIORITIES, WILD, R.TIES[0], SRC_JUNBAN],
        ["R02", R.KINDS[0], PRIORITIES, WILD, R.TIES[0], SRC_SOTO],
        ["R03", R.KINDS[0], PRIORITIES, WILD, R.TIES[0], SRC_KITEI],
        ["R04", R.KINDS[0], PRIORITIES, WILD, R.TIES[0], SRC_KYOUKAI],
        ["R05", kind_r05, PRIORITIES, WILD, R.TIES[0], SRC_MUGEN],
    ]


# ---------------------------------------------------------------- 対象の表


def taishou_rows() -> list[list[str]]:
    """対象 4 件。どの次元にも具体的な値だけを書く(未指定に見える記号は書けない)。"""
    return [
        HEAD_TAISHOU,
        ["T01", seg(A1, B1), SRC_KYOUKAI, R.SWAPS[0]],
        ["T02", seg(A1, B2), TANAOROSHI, ""],
        ["T03", seg(A2, B1), SRC_KOUROU, ""],
        ["T04", seg(A2, B2), TANAOROSHI, ""],
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
    """止まる理由コード 6 個と「表として読めない」を出すための表。"""
    g, s, t = gyou_rows(), sengen_rows(), taishou_rows()
    out: dict[str, list[list[str]]] = {}

    # --- 止まる(理由コードが返る)
    out["gyou_shutten_nashi"] = drop(g, 4, "")                      # 出典の欄が空
    out["sengen_shutten_nashi"] = drop(s, 5, "")                    # 出典の欄が空
    out["taishou_shutten_nashi"] = drop(t, 2, "")                   # 出典の欄が空
    out["gyou_id_juufuku"] = g + [["G01", "R04", seg(A2, B2), "0",
                                   TANAOROSHI]]                     # 行 id の重複
    out["gyou_juni_gai"] = drop(g, 3, "5")                          # 宣言に無い順位の値
    out["gyou_kigou_gai"] = drop(g, 2, f"{DIM_A}=-{R.SEG_SEP}{DIM_B}={WILD}")
    out["gyou_rule_gai"] = g + [["G10", "R09", seg(A1, B1), "0",
                                 TANAOROSHI]]                       # rule が宣言表に無い
    out["sengen_juufuku"] = s + [["R01", R.KINDS[0], PRIORITIES, WILD, R.TIES[0],
                                  TANAOROSHI]]                      # 宣言が 2 行

    # --- 表として読めない(終了コード 2。理由コードには混ぜない)
    out["gyou_retsu_nashi"] = without_column(g, "priority")
    out["gyou_0gyou"] = [HEAD_GYOU]
    out["gyou_id_kuuran"] = drop(g, 0, "")
    out["gyou_rule_kuuran"] = drop(g, 1, "")
    out["gyou_seg_kuuran"] = drop(g, 2, "")
    out["gyou_seg_katachi"] = drop(g, 2, f"{DIM_A}{A1}{R.SEG_SEP}{DIM_B}={WILD}")
    out["gyou_seg_atai_kuuran"] = drop(g, 2, f"{DIM_A}={R.SEG_SEP}{DIM_B}={WILD}")
    out["gyou_seg_onaji"] = drop(g, 2, f"{DIM_A}={A1}{R.SEG_SEP}{DIM_A}={A2}")
    out["gyou_juni_seisuu"] = drop(g, 3, "高")
    out["gyou_jigen_chigai"] = drop(g, 2, f"次元C=c1{R.SEG_SEP}{DIM_B}={WILD}")
    out["sengen_retsu_nashi"] = without_column(s, "tie")
    out["sengen_0gyou"] = [HEAD_SENGEN]
    out["sengen_id_kuuran"] = drop(s, 0, "")
    out["sengen_kind_gai"] = drop(s, 1, "いちばん具体的な行")
    out["sengen_tie_gai"] = drop(s, 4, "先に書いた方")
    out["sengen_wildcard_kuuran"] = drop(s, 3, "")
    out["sengen_juni_katachi"] = drop(s, 2, "0本則|10=経過措置")
    out["sengen_juni_seisuu_gai"] = drop(s, 2, "高=本則")
    out["sengen_juni_0ko"] = drop(s, 2, "")
    out["sengen_juni_juufuku"] = drop(s, 2, "0=本則|0=別の意味")
    out["taishou_retsu_nashi"] = without_column(t, "seg")
    out["taishou_0gyou"] = [HEAD_TAISHOU]
    out["taishou_id_kuuran"] = drop(t, 0, "")
    out["taishou_seg_kuuran"] = drop(t, 1, "")
    out["taishou_juufuku"] = t + [["T01", seg(A2, B2), TANAOROSHI, ""]]
    out["taishou_kigou"] = drop(t, 1, seg(WILD, B1))
    out["taishou_swap_gai"] = drop(t, 3, "ランダム")
    out["taishou_swap_futatsu"] = drop(t, 3, R.SWAPS[1], at=2)
    return out


# ---------------------------------------------------------------- 書き出し

def main() -> None:
    written: list[Path] = []
    base = {
        "gyou_a": gyou_rows(),
        "gyou_kuuran_ume": gyou_rows(priority_kuuran="20"),
        "gyou_guutai": gyou_rows(priority_guutai="10"),
        "sengen_a": sengen_rows(),
        "sengen_junide": sengen_rows(kind_r05=R.KINDS[0]),
        "taishou_a": taishou_rows(),
    }
    for name, rows in base.items():
        written.append(R.write_csv(HERE / f"{name}.csv", rows))
    for name, rows in kowashita().items():
        written.append(R.write_csv(HERE / "kowashita" / f"{name}.csv", rows))
    print(f"書いた: {len(written)} 枚")


if __name__ == "__main__":
    main()
