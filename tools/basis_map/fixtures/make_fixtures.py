"""basis_map の合成 fixture。値(料率・金額)は 1 つも入れない(この部品は値を持たない)。

対象 id・rule id・日付は全て架空だ。**実在の料率・金額・取引先名は 1 つも入っていない。**
写したのは形だけ、つまり「同じ種別が 2 通りの書かれ方で並ぶ」「候補の但し書きが付いた種別を
rule が要求している」「方針の例示に出てくる種別が手元に 1 行も無い」という 3 つで、これは
私の棚卸し記録に残っている形だ。記録そのものは出さない。

書くもの(どれも決定論。同じ実行で同じバイト列になる)。

  shubetsu_a.csv             種別の台帳 6 行。別名が宣言された種別が 2 つ、候補が 1 つ
  shubetsu_touroku.csv       shubetsu_a の 1 欄だけ、候補 → 登録済 に書き換えた表
  shubetsu_betsumei_nashi.csv shubetsu_a から別名の宣言を 1 つ外した表
  youkyuu_a.csv              要求表 5 行(rule が要求する種別 id)
  temoto_a.csv               手元の表 12 行 / 対象 4 件
  kowashita/*.csv            止まる理由コードと「表として読めない」を出すために 1 か所崩した表

使い方: python fixtures/make_fixtures.py   (この置き場に書き直す)
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import basis_map as B  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの(テストがその行を開いて語の在ることを見る)
SRC_SENGEN = "articles/07_asof_table.md L13"      # 「行の側に列として宣言させる」
SRC_TOMERU = "articles/07_asof_table.md L16"      # 「理由コードで止めて」
SRC_YURE = "articles/02_wareki.md L15"            # 「表記の揺れ」
SRC_SUITEI = "articles/22_span_split.md L13"      # 「推測して足す経路が無い」
SRC_SENGEN_KARA = "articles/22_span_split.md L14" # 「表の宣言から取る」

# 出典(動かした主体 + 非公開の棚卸し記録)。主体の名前は公表されている情報
TANAOROSHI = "私の棚卸し記録(非公開)"
SRC_KYOUKAI = f"協会けんぽ / {TANAOROSHI}"
SRC_KOUROU = f"厚生労働省 / {TANAOROSHI}"

# 種別 id(合成)
K_TAISHOU = "K01"      # 対象月初日(別名の宣言あり)
K_SHIMEKIRI = "K02"    # 賃金締切日(別名の宣言あり = 表記ゆれを寄せてよい唯一の経路)
K_RISHOKU = "K03"      # 離職日
K_SEIKYUU = "K04"      # 請求日
K_SHIKAKU = "K05"      # 資格取得日(候補どまり)
K_KYUUGYOU = "K06"     # 休業開始日(方針の例示にあるが手元に 1 行も無い)
K_SOTO = "K09"         # 台帳に無い種別 id

# 表記(正式な表記と、宣言された別名)
N_TAISHOU, A_TAISHOU = "対象月初日", "対象月の初日"
N_SHIMEKIRI, A_SHIMEKIRI = "賃金締切日", "賃金締め日"
N_RISHOKU = "離職日"
N_SEIKYUU = "請求日"
N_SHIKAKU = "資格取得日"
N_KYUUGYOU = "休業開始日"
N_SHIHARAI = "支払日"          # どの種別にも宣言されていない表記

FMT = "YYYY-MM-DD"
HEAD_SHUBETSU = list(B.SHUBETSU_COLUMNS)
HEAD_YOUKYUU = list(B.YOUKYUU_COLUMNS)
HEAD_TEMOTO = list(B.TEMOTO_COLUMNS)


def aliases(*names: str) -> str:
    return B.ALIAS_SEP.join(names)


# ---------------------------------------------------------------- 種別の台帳


def shubetsu_rows(status_shikaku: str = B.STATUSES[1],
                  alias_shimekiri: str = A_SHIMEKIRI) -> list[list[str]]:
    """種別の台帳 6 行。別名は宣言された分だけが寄せてよい表記になる。"""
    return [
        HEAD_SHUBETSU,
        [K_TAISHOU, N_TAISHOU, A_TAISHOU, "その月の 1 日", FMT,
         B.STATUSES[0], SRC_SENGEN],
        [K_SHIMEKIRI, N_SHIMEKIRI, alias_shimekiri, "賃金を締める日", FMT,
         B.STATUSES[0], SRC_YURE],
        [K_RISHOKU, N_RISHOKU, "", "雇用関係が終わる日", FMT,
         B.STATUSES[0], SRC_SENGEN_KARA],
        [K_SEIKYUU, N_SEIKYUU, "", "給付を請求した日", FMT,
         B.STATUSES[0], SRC_KYOUKAI],
        [K_SHIKAKU, N_SHIKAKU, "", "被保険者の資格を取る日", FMT,
         status_shikaku, TANAOROSHI],
        [K_KYUUGYOU, N_KYUUGYOU, "", "休業が始まる日", FMT,
         B.STATUSES[0], SRC_TOMERU],
    ]


# ---------------------------------------------------------------- 要求表


def youkyuu_rows() -> list[list[str]]:
    """rule ごとに「どの種別の日付を渡すか」を 1 行で書く。"""
    return [
        HEAD_YOUKYUU,
        ["R01", K_TAISHOU, SRC_SENGEN],
        ["R02", K_SHIMEKIRI, SRC_KOUROU],
        ["R03", K_RISHOKU, SRC_SUITEI],
        ["R04", K_SHIKAKU, TANAOROSHI],
        ["R05", K_KYUUGYOU, SRC_TOMERU],
    ]


# ---------------------------------------------------------------- 手元の表


def temoto_rows(date_taishou: str = "2026-04-01") -> list[list[str]]:
    """対象 4 件 × 手元にある日付の行。表記は正式名と別名の両方が混ざっている。"""
    return [
        HEAD_TEMOTO,
        ["T01", N_TAISHOU, date_taishou, SRC_KYOUKAI, B.SWAPS[0]],
        ["T01", A_SHIMEKIRI, "2026-04-20", TANAOROSHI, ""],
        ["T01", N_RISHOKU, "2026-03-31", TANAOROSHI, ""],
        ["T01", N_SHIKAKU, "2026-02-01", TANAOROSHI, ""],
        ["T02", A_TAISHOU, "2026-04-01", TANAOROSHI, ""],
        ["T02", N_SHIMEKIRI, "2026-04-20", SRC_KOUROU, ""],
        ["T02", N_SHIHARAI, "2026-04-25", TANAOROSHI, ""],
        ["T03", N_TAISHOU, "2026-04-01", TANAOROSHI, ""],
        ["T03", A_TAISHOU, "2026-04-02", TANAOROSHI, ""],
        ["T03", N_RISHOKU, "2026-03-31", SRC_SUITEI, ""],
        ["T04", N_SEIKYUU, "2026-05-10", TANAOROSHI, ""],
        ["T04", N_SHIKAKU, "2026-02-15", TANAOROSHI, ""],
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
    s, y, t = shubetsu_rows(), youkyuu_rows(), temoto_rows()
    out: dict[str, list[list[str]]] = {}

    # --- 止まる(理由コードが返る)
    out["shubetsu_shutten_nashi"] = drop(s, 6, "")                 # 出典の欄が空
    out["youkyuu_shutten_nashi"] = drop(y, 2, "")                  # 出典の欄が空
    out["temoto_shutten_nashi"] = drop(t, 3, "")                   # 出典の欄が空
    out["youkyuu_mitouroku"] = y + [["R06", K_SOTO, TANAOROSHI]]   # 種別 id が台帳に無い
    out["shubetsu_betsumei_juufuku"] = drop(s, 2, A_TAISHOU, at=3) # 同じ別名が 2 種別に宣言
    out["shubetsu_id_juufuku"] = s + [[K_TAISHOU, "対象月初日の写し", "",
                                       "2 行目の宣言", FMT, B.STATUSES[0],
                                       TANAOROSHI]]                # 同じ種別 id が 2 行
    out["temoto_shoshiki_gai"] = drop(t, 2, "2026/04/01")          # 書式が宣言外
    out["shubetsu_joutai_gai"] = drop(s, 5, "検討中", at=5)        # 状態が宣言外
    out["youkyuu_juufuku"] = y + [["R01", K_SEIKYUU, TANAOROSHI]]  # 件数の合計が合わない

    # --- 表として読めない(終了コード 2。理由コードには混ぜない)
    out["shubetsu_retsu_nashi"] = without_column(s, "status")
    out["shubetsu_0gyou"] = [HEAD_SHUBETSU]
    out["shubetsu_id_kuuran"] = drop(s, 0, "")
    out["shubetsu_na_kuuran"] = drop(s, 1, "")
    out["shubetsu_imi_kuuran"] = drop(s, 3, "")
    out["shubetsu_shoshiki_gai"] = drop(s, 4, "YYYY/MM/DD")
    out["shubetsu_betsumei_onaji"] = drop(s, 2, aliases(A_TAISHOU, A_TAISHOU))
    out["youkyuu_retsu_nashi"] = without_column(y, "kind_id")
    out["youkyuu_0gyou"] = [HEAD_YOUKYUU]
    out["youkyuu_id_kuuran"] = drop(y, 0, "")
    out["youkyuu_kind_kuuran"] = drop(y, 1, "")
    out["temoto_retsu_nashi"] = without_column(t, "date")
    out["temoto_0gyou"] = [HEAD_TEMOTO]
    out["temoto_taishou_kuuran"] = drop(t, 0, "")
    out["temoto_hyouki_kuuran"] = drop(t, 1, "")
    out["temoto_hizuke_kuuran"] = drop(t, 2, "")
    out["temoto_juufuku"] = t + [["T01", N_TAISHOU, "2026-04-03", TANAOROSHI, ""]]
    out["temoto_swap_gai"] = drop(t, 4, "ランダム")
    out["temoto_swap_futatsu"] = drop(t, 4, B.SWAPS[1], at=2)
    return out


# ---------------------------------------------------------------- 書き出し

def main() -> None:
    written: list[Path] = []
    base = {
        "shubetsu_a": shubetsu_rows(),
        "shubetsu_touroku": shubetsu_rows(status_shikaku=B.STATUSES[0]),
        "shubetsu_betsumei_nashi": shubetsu_rows(alias_shimekiri=""),
        "youkyuu_a": youkyuu_rows(),
        "temoto_a": temoto_rows(),
    }
    for name, rows in base.items():
        written.append(B.write_csv(HERE / f"{name}.csv", rows))
    for name, rows in kowashita().items():
        written.append(B.write_csv(HERE / "kowashita" / f"{name}.csv", rows))
    print(f"書いた: {len(written)} 枚")


if __name__ == "__main__":
    main()
