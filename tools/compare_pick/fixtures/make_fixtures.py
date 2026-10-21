"""compare_pick の合成 fixture。**実在の料率・金額・取引先名は 1 つも入っていない。**

組 id・行 id・rule id・基準日 id・欄の名前・単位の名前は全て架空で、値も合成だ(この部品は
値の大小だけを見るので、桁の並びが同じでも制度の数字ではない)。写したのは形だけ、つまり
「順位の欄に値が入っているのに、その順位では決まらない裁定が宣言に書いてある」「単位が違う
2 行が同じ組に入っている」「丸めを比較の前にするか後にするかで勝者が入れ替わる」「比べる 2 行
の有効期間が基準日によって重ならない」という 4 つで、これは私の棚卸し記録に残っている形だ。
記録そのものは出さない。

書くもの(どれも決定論。同じ実行で同じバイト列になる)。

  sengen_a.csv            裁定の宣言表 5 行(rule 1 本が 1 行)
  sengen_junide.csv       sengen_a の 1 欄だけ、R02 の裁定の種類を「宣言された順位」にした表
  sengen_maeushiro.csv    sengen_a の丸めの前後(前 / 後)だけを入れ替えた表
  kouho_a.csv             候補の表 21 行(11 組)
  kijunbi_a.csv           基準日の表 2 行
  kowashita/*.csv         止まる理由コードと「表として読めない」を出すために 1 か所崩した表

使い方: python fixtures/make_fixtures.py   (この置き場に書き直す)
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import compare_pick as C  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの(テストがその行を開いて語の在ることを見る)
SRC_SHUBI = "articles/27_rank_clash.md L101"     # 「守備範囲の外」
SRC_OOKII = "articles/27_rank_clash.md L8"       # 「値の大きい方でもなく」
SRC_YAJIRUSHI = "articles/27_rank_clash.md L212"  # 「矢印も無い」
SRC_KUURAN = "articles/08_formula_table.md L61"  # 「空欄は許さない」

# 出典(動かした主体 + 非公開の棚卸し記録)。主体の名前は公表されている情報
TANAOROSHI = "私の棚卸し記録(非公開)"
SRC_KOUROU = f"厚生労働省 / {TANAOROSHI}"

# 欄と単位の名前(合成)。業種の語彙は 1 つも入れない
RAN_A, RAN_B = "欄A", "欄B"
TANNI_KOU, TANNI_OTSU = "単位甲", "単位乙"

HIRAKI, TOJI = "2026-01-01", "2027-01-01"          # どちらの基準日にも重なる有効期間
TOJI_HAYAI = "2026-07-01"                          # 後の基準日には重ならない有効期間

HEAD_SENGEN = list(C.SENGEN_COLUMNS)
HEAD_KOUHO = list(C.KOUHO_COLUMNS)
HEAD_KIJUNBI = list(C.KIJUNBI_COLUMNS)


# ---------------------------------------------------------------- 裁定の宣言表


def sengen_rows(kind_r02: str = C.KINDS[1], swap_round_when: bool = False) -> list[list[str]]:
    """rule ごとに「2 本以上残ったときに何で決めるか」を 1 行で宣言する。"""
    mae, ushiro = C.ROUND_WHENS            # 前 / 後
    if swap_round_when:
        mae, ushiro = ushiro, mae
    return [
        HEAD_SENGEN,
        # R01 順位で決まる rule(比較の欄は空欄のまま持つ)
        ["R01", C.KINDS[0], "", "", "", "", "", "", SRC_OOKII],
        # R02 「高い方が適用」。順位の欄は埋まっているが、順位では決まらない
        ["R02", kind_r02, RAN_A, C.DIRECTIONS[0], TANNI_KOU, ushiro, C.ROUNDINGS[1],
         C.TIES[1], SRC_SHUBI],
        # R03 丸めを比較の前にする宣言。同値は決まらないへ落とす
        ["R03", C.KINDS[1], RAN_A, C.DIRECTIONS[0], TANNI_KOU, mae, C.ROUNDINGS[1],
         C.TIES[0], SRC_KUURAN],
        # R04 順位でも比較でも決まらない、と宣言に書いてある rule
        ["R04", C.KINDS[2], "", "", "", "", "", "", SRC_YAJIRUSHI],
        # R05 小さい方を採る宣言。切り捨ては比較の後
        ["R05", C.KINDS[1], RAN_B, C.DIRECTIONS[1], TANNI_OTSU, ushiro,
         C.ROUNDINGS[2], C.TIES[0], SRC_KOUROU],
    ]


# ---------------------------------------------------------------- 候補の表


def kouho_rows() -> list[list[str]]:
    """11 組。順位で決まる組・比較で決まる組・止まる組を 1 つずつ置いてある。"""
    def row(group: str, rule: str, row_id: str, priority: str, field: str, value: str,
            unit: str, source: str, to: str = TOJI) -> list[str]:
        return [group, rule, row_id, priority, field, value, unit, HIRAKI, to, source]

    return [
        HEAD_KOUHO,
        # P01 順位が違うので順位で決まる(値が入っていても読まない)
        row("P01", "R01", "G01", "0", RAN_A, "1100", TANNI_KOU, SRC_OOKII),
        row("P01", "R01", "G02", "10", RAN_A, "1050", TANNI_KOU, TANAOROSHI),
        # P02 同順位なので決まらない
        row("P02", "R01", "G03", "10", RAN_A, "1200", TANNI_KOU, SRC_OOKII),
        row("P02", "R01", "G04", "10", RAN_A, "1250", TANNI_KOU, TANAOROSHI),
        # P03 「高い方が適用」。丸めを比較の前にすると同値になり、順位へ落ちる
        row("P03", "R02", "G05", "10", RAN_A, "1026", TANNI_KOU, SRC_SHUBI),
        row("P03", "R02", "G06", "0", RAN_A, "1049", TANNI_KOU, SRC_KOUROU),
        # P04 丸めを比較の前にすると同値。宣言が「決まらない」なので落ちる
        row("P04", "R03", "G07", "0", RAN_A, "1211", TANNI_KOU, SRC_KUURAN),
        row("P04", "R03", "G08", "0", RAN_A, "1224", TANNI_KOU, TANAOROSHI),
        # P05 単位が違う 2 行(換算しない)
        row("P05", "R02", "G09", "0", RAN_A, "1100", TANNI_KOU, SRC_SHUBI),
        row("P05", "R02", "G10", "10", RAN_A, "1200", TANNI_OTSU, TANAOROSHI),
        # P06 後の基準日には有効期間が重ならない 2 行
        row("P06", "R05", "G11", "0", RAN_B, "998.75", TANNI_OTSU, SRC_KOUROU,
            TOJI_HAYAI),
        row("P06", "R05", "G12", "10", RAN_B, "1002.4", TANNI_OTSU, TANAOROSHI,
            TOJI_HAYAI),
        # P07 宣言が「決まらない」と言っている rule の組
        row("P07", "R04", "G13", "0", RAN_A, "1300", TANNI_KOU, SRC_YAJIRUSHI),
        row("P07", "R04", "G14", "10", RAN_A, "1400", TANNI_KOU, TANAOROSHI),
        # P08 比較の宣言が付いているのに候補が 1 本しかない組
        row("P08", "R02", "G15", "0", RAN_A, "1300", TANNI_KOU, TANAOROSHI),
        # P09 宣言の比べる欄が候補の表に無い
        row("P09", "R03", "G16", "0", RAN_B, "1500", TANNI_KOU, SRC_KUURAN),
        row("P09", "R03", "G17", "10", RAN_B, "1600", TANNI_KOU, TANAOROSHI),
        # P10 値が数に読めない(棚卸しの「未取得」をそのまま入れた形)
        row("P10", "R02", "G18", "0", RAN_A, "未取得", TANNI_KOU, SRC_SHUBI),
        row("P10", "R02", "G19", "10", RAN_A, "未取得", TANNI_KOU, TANAOROSHI),
        # P11 float から来た形(指数表記)
        row("P11", "R02", "G20", "0", RAN_A, "1.05e3", TANNI_KOU, SRC_SHUBI),
        row("P11", "R02", "G21", "10", RAN_A, "1.06e3", TANNI_KOU, TANAOROSHI),
    ]


# ---------------------------------------------------------------- 基準日の表


def kijunbi_rows() -> list[list[str]]:
    """基準日 2 件。前の基準日では重なる組が、後の基準日では重ならない。"""
    return [
        HEAD_KIJUNBI,
        ["K01", "2026-04-01", SRC_KOUROU, C.SWAPS[0]],
        ["K02", "2026-10-01", TANAOROSHI, ""],
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
    """止まる理由コードと「表として読めない」を出すための表。"""
    s, k, j = sengen_rows(), kouho_rows(), kijunbi_rows()
    # 列番号(宣言表 / 候補の表 / 基準日の表)
    S = {name: i for i, name in enumerate(HEAD_SENGEN)}
    K = {name: i for i, name in enumerate(HEAD_KOUHO)}
    J = {name: i for i, name in enumerate(HEAD_KIJUNBI)}
    R02, R02_ROW = "R02", 2          # 宣言表の R02 は 2 行目(ヘッダの次が R01)
    G06_ROW = 6                      # 候補の表の P03 / G06
    out: dict[str, list[list[str]]] = {}

    # --- 止まる(理由コードが返る)
    out["sengen_shutten_nashi"] = drop(s, S["source"], "")
    out["kouho_shutten_nashi"] = drop(k, K["source"], "")
    out["kijunbi_shutten_nashi"] = drop(j, J["source"], "")
    out["kouho_id_juufuku"] = k + [["P01", "R01", "G01", "0", RAN_A, "1500",
                                    TANNI_KOU, HIRAKI, TOJI, TANAOROSHI]]
    out["sengen_kind_gai"] = drop(s, S["kind"], "高い方が適用", at=R02_ROW)
    out["sengen_juufuku"] = s + [[R02, C.KINDS[1], RAN_A, C.DIRECTIONS[0], TANNI_KOU,
                                  C.ROUND_WHENS[1], C.ROUNDINGS[1], C.TIES[1],
                                  TANAOROSHI]]
    out["sengen_tanni_kuuran"] = drop(s, S["unit"], "", at=R02_ROW)
    out["sengen_maeushiro_kuuran"] = drop(s, S["round_when"], "", at=R02_ROW)
    out["sengen_marume_kuuran"] = drop(s, S["rounding"], "", at=R02_ROW)
    out["sengen_marume_gai"] = drop(s, S["rounding"], "いい感じに丸める", at=R02_ROW)
    out["sengen_douchi_kuuran"] = drop(s, S["tie"], "", at=R02_ROW)
    out["kouho_tanni_kuuran"] = drop(k, K["unit"], "", at=G06_ROW)
    out["kouho_atai_kuuran"] = drop(k, K["value"], "", at=G06_ROW)

    # --- 表として読めない(終了コード 2。理由コードには混ぜない)
    out["sengen_retsu_nashi"] = without_column(s, "tie")
    out["sengen_0gyou"] = [HEAD_SENGEN]
    out["sengen_id_kuuran"] = drop(s, S["rule_id"], "")
    out["sengen_ran_kuuran"] = drop(s, S["field"], "", at=R02_ROW)
    out["sengen_muki_kuuran"] = drop(s, S["direction"], "", at=R02_ROW)
    out["sengen_muki_gai"] = drop(s, S["direction"], "高い方", at=R02_ROW)
    out["sengen_maeushiro_gai"] = drop(s, S["round_when"], "まんなか", at=R02_ROW)
    out["sengen_douchi_gai"] = drop(s, S["tie"], "先に書いた方", at=R02_ROW)
    out["kouho_retsu_nashi"] = without_column(k, "unit")
    out["kouho_0gyou"] = [HEAD_KOUHO]
    out["kouho_group_kuuran"] = drop(k, K["group_id"], "")
    out["kouho_row_kuuran"] = drop(k, K["row_id"], "")
    out["kouho_rule_kuuran"] = drop(k, K["rule_id"], "")
    out["kouho_rule_futatsu"] = drop(k, K["rule_id"], "R02", at=2)
    out["kouho_juni_seisuu"] = drop(k, K["priority"], "高")
    out["kouho_hizuke_katachi"] = drop(k, K["valid_from"], "2026/01/01")
    out["kouho_hizuke_koyomi"] = drop(k, K["valid_from"], "2026-02-30")
    out["kouho_kikan_sakasa"] = drop(k, K["valid_to"], HIRAKI)
    out["kijunbi_retsu_nashi"] = without_column(j, "asof")
    out["kijunbi_0gyou"] = [HEAD_KIJUNBI]
    out["kijunbi_id_kuuran"] = drop(j, J["asof_id"], "")
    out["kijunbi_hizuke_katachi"] = drop(j, J["asof"], "令和8年4月1日")
    out["kijunbi_juufuku"] = j + [["K01", "2026-12-01", TANAOROSHI, ""]]
    out["kijunbi_swap_gai"] = drop(j, J["swap"], "ランダム")
    out["kijunbi_swap_futatsu"] = drop(j, J["swap"], C.SWAPS[1], at=2)

    # --- 宣言表に無い rule を名乗る(compare_pick の側で「表として読めない」になる)
    out["kouho_rule_gai"] = k + [["P12", "R09", "G22", "0", RAN_A, "1500", TANNI_KOU,
                                  HIRAKI, TOJI, TANAOROSHI]]
    return out


# ---------------------------------------------------------------- 書き出し

def main() -> None:
    written: list[Path] = []
    base = {
        "sengen_a": sengen_rows(),
        "sengen_junide": sengen_rows(kind_r02=C.KINDS[0]),
        "sengen_maeushiro": sengen_rows(swap_round_when=True),
        "kouho_a": kouho_rows(),
        "kijunbi_a": kijunbi_rows(),
    }
    for name, rows in base.items():
        written.append(C.write_csv(HERE / f"{name}.csv", rows))
    for name, rows in kowashita().items():
        written.append(C.write_csv(HERE / "kowashita" / f"{name}.csv", rows))
    print(f"書いた: {len(written)} 枚")


if __name__ == "__main__":
    main()
