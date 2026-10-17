"""recalc_scope の合成 fixture。値は 1 つも入れない(この部品は値を持たない)。

指紋・キー・対象・項目は全て架空だ。**実在の料率・金額・取引先名は 1 つも入っていない。**
写したのは形だけ、つまり「同じ内容に戻った版がある」「差分のキーが見本だけの区間がある」
「検証に落ちた回は指紋が無い」という 3 つの形で、これは私の更新の実行記録に残っている。
記録そのものは出さない(その記録は値の側も含むため)。

書くもの(どれも決定論。同じ実行で同じバイト列になる)。

  kekka_a.csv         結果の台帳 12 行。引いた版が 5 通りに散っている
  kekka_hizuke.csv    kekka_a の「出した日」だけを全部ずらした表(判定部分は動かない)
  han_a.csv           版の台帳 5 行。指紋の親子で 1 本の鎖になる
  han_hizuke.csv      han_a の「版の日付」だけを全部ずらした表(同じく動かない)
  sabun_a.csv         差分の台帳 4 行。1 区間が見本だけ、1 区間が台帳に無い
  sabun_zenken.csv    sabun_a の 1 欄だけ、見本だけ → 全件 に書き換えた表
  kowashita/*.csv     止まる理由コードと「表として読めない」を出すために 1 か所崩した表

使い方: python fixtures/make_fixtures.py   (この置き場に書き直す)
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import recalc_scope as R  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの(テストがその行を開いて語の在ることを見る)
SRC_SENGEN = "articles/07_asof_table.md L13"      # 「行の側に列として宣言させる」
SRC_TOMERU = "articles/07_asof_table.md L16"      # 「理由コードで止めて」
SRC_DAICHOU = "articles/09_update_ledger.md L13"  # 「更新 1 回を台帳 1 行にする」
SRC_KUSARI = "articles/09_update_ledger.md L15"   # 「そのまま次の行に繋がる」
SRC_KARIOKI = "articles/15_context_pack.md L15"   # 「仮置きだと塊の中に書く」

# 出典(動かした主体 + 非公開の棚卸し記録)。主体の名前は公表されている情報
TANAOROSHI = "私の棚卸し記録(非公開)"
SRC_KYOUKAI = f"協会けんぽ / {TANAOROSHI}"
SRC_KOUROU = f"厚生労働省 / {TANAOROSHI}"

# 版の指紋(合成。16 桁。実在の指紋は 1 つも写していない)
V1 = "a7b2c1d4e8f3a6b9"
V2 = "b3c8d1e6f2a9b4c7"
V3 = "c5d2e9f4a1b8c3d6"
V4 = "d9e4f1a8b3c6d2e7"
V5 = "e1f6a3b9c4d7e2f8"
V_SOTO = "f4a1b7c2d9e6f3a8"     # 版台帳に無い指紋
V_WA1 = "a3c6b1d8e4f7a2b5"      # 鎖から外れた輪(2 行で互いを指す)
V_WA2 = "b8d3c7e1f6a4b9c2"

# 引いた行のキー(合成)
K_A = "合成のキーA(架空)"
K_B = "合成のキーB(架空)"
K_C = "合成のキーC(架空)"
K_D = "合成のキーD(架空)"
K_E = "合成のキーE(架空)"
K_Z = "合成のキーZ(架空)"

I_SHIKYUU = "合成の支給の項目(架空)"
I_KOUJO = "合成の控除の項目(架空)"
T_A, T_B, T_C = "合成の区分A", "合成の区分B", "合成の区分C"

HEAD_KEKKA = list(R.KEKKA_COLUMNS)
HEAD_HAN = list(R.HAN_COLUMNS)
HEAD_SABUN = list(R.SABUN_COLUMNS)


def keys(*names: str) -> str:
    return R.KEY_SEP.join(names)


# ---------------------------------------------------------------- 版の台帳


def han_rows(shift: int = 0) -> list[list[str]]:
    """指紋の親子で 1 本の鎖(V1 → V2 → V3 → V4 → V5)。日付は表示だけに使う。"""
    days = [5, 9, 2, 6, 11]
    months = [1, 2, 3, 4, 5]
    return [
        [V1, f"2026-{months[0]:02d}-{days[0] + shift:02d}", "", SRC_DAICHOU],
        [V2, f"2026-{months[1]:02d}-{days[1] + shift:02d}", V1, SRC_KUSARI],
        [V3, f"2026-{months[2]:02d}-{days[2] + shift:02d}", V2, SRC_KYOUKAI],
        [V4, f"2026-{months[3]:02d}-{days[3] + shift:02d}", V3, SRC_KOUROU],
        [V5, f"2026-{months[4]:02d}-{days[4] + shift:02d}", V4, SRC_SENGEN],
    ]


def han(rows: list[list[str]]) -> list[list[str]]:
    return [HEAD_HAN, *rows]


HAN_A = han(han_rows())
HAN_HIZUKE = han(han_rows(shift=7))      # 版の日付だけを 7 日ずらした表

# ---------------------------------------------------------------- 差分の台帳


def sabun_rows(coverage_v2v3: str = R.COVERAGES[1]) -> list[list[str]]:
    """1 区間 × 1 変更種別で 1 行。V1 → V2 の区間は台帳に無い(鎖が切れている)。"""
    return [
        [V2, V3, keys(K_E), R.CHANGES[0], coverage_v2v3, SRC_KARIOKI],
        [V3, V4, keys(K_A, K_B), R.CHANGES[2], R.COVERAGES[0], SRC_KYOUKAI],
        [V3, V4, keys(K_D), R.CHANGES[0], R.COVERAGES[0], SRC_KYOUKAI],
        [V4, V5, keys(K_C), R.CHANGES[0], R.COVERAGES[0], SRC_KOUROU],
    ]


def sabun(rows: list[list[str]]) -> list[list[str]]:
    return [HEAD_SABUN, *rows]


SABUN_A = sabun(sabun_rows())
SABUN_ZENKEN = sabun(sabun_rows(coverage_v2v3=R.COVERAGES[0]))

# ---------------------------------------------------------------- 結果の台帳


def kekka_rows(swap: str = "逆順", shift: int = 0) -> list[list[str]]:
    """結果 12 行。引いた版が 5 通りに散り、引いたキーが 0 件の行も 2 行ある。"""
    def day(n: int) -> str:
        return f"2026-{(n + shift) // 28 + 1:02d}-{(n + shift) % 28 + 1:02d}"

    return [
        ["R01", T_A, I_SHIKYUU, V3, keys(K_A), day(70), SRC_KYOUKAI, swap],
        ["R02", T_B, I_SHIKYUU, V3, keys(K_Z), day(71), SRC_KYOUKAI, ""],
        ["R03", T_A, I_KOUJO, V4, keys(K_C), day(100), SRC_KOUROU, ""],
        ["R04", T_B, I_KOUJO, V4, keys(K_A), day(101), SRC_KOUROU, ""],
        ["R05", T_C, I_KOUJO, V5, keys(K_A, K_C), day(135), SRC_KOUROU, ""],
        ["R06", T_A, I_SHIKYUU, V2, keys(K_A), day(40), SRC_KARIOKI, ""],
        ["R07", T_B, I_SHIKYUU, V1, keys(K_A), day(10), SRC_DAICHOU, ""],
        ["R08", T_C, I_SHIKYUU, V3, "", day(72), SRC_TOMERU, ""],
        ["R09", T_C, I_KOUJO, V3, keys(K_B, K_Z), day(73), SRC_KYOUKAI, ""],
        ["R10", T_A, "合成の控えの項目(架空)", V5, "", day(136), SRC_TOMERU, ""],
        ["R11", T_B, I_KOUJO, V2, keys(K_Z), day(41), SRC_KARIOKI, ""],
        ["R12", T_C, "合成の控えの項目(架空)", V4, keys(K_Z), day(102), SRC_KOUROU, ""],
    ]


def kekka(rows: list[list[str]]) -> list[list[str]]:
    return [HEAD_KEKKA, *rows]


def edited(result_id: str, col: str, value: str) -> list[list[str]]:
    """kekka_a の 1 行 1 欄だけを差し替えた表(どこを 1 か所変えたかが分かる形)。"""
    rows = kekka_rows()
    j = HEAD_KEKKA.index(col)
    for r in rows:
        if r[0] == result_id:
            r[j] = value
    return kekka(rows)


KEKKA_A = kekka(kekka_rows())
KEKKA_HIZUKE = kekka(kekka_rows(shift=9))      # 出した日だけを 9 日ずらした表

# ---------------------------------------------------------------- 崩した表

KOWASHITA_KEKKA: dict[str, list[list[str]]] = {
    # 止まる理由コードが出る側
    "kekka_shutten_nashi": edited("R01", "source", ""),
    "kekka_mitouroku_han": edited("R01", "version", V_SOTO),
    "kekka_han_kuuran": edited("R01", "version", ""),
    "kekka_juufuku": kekka(kekka_rows() + [
        ["R01", T_A, I_SHIKYUU, V3, keys(K_A), "2026-03-15", SRC_KYOUKAI, ""]]),
    # 「表として読めない」で返る側
    "kekka_id_kuuran": edited("R01", "result_id", ""),
    "kekka_taishou_kuuran": edited("R01", "target", ""),
    "kekka_koumoku_kuuran": edited("R01", "item", ""),
    "kekka_hi_kuuran": edited("R01", "issued", ""),
    "kekka_kagi_juufuku": edited("R01", "keys", keys(K_A, K_A)),
    "kekka_swap_mitouroku": edited("R01", "swap", "でたらめ"),
    "kekka_swap_futatsu": edited("R02", "swap", "両端入れ替え"),
}

KOWASHITA_HAN: dict[str, list[list[str]]] = {
    # 止まる理由コードが出る側
    "han_shutten_nashi": han([[V1, "2026-01-05", "", ""], *han_rows()[1:]]),
    "han_hizuke_futatsu": han(han_rows() + [[V3, "2026-06-01", V2, SRC_KYOUKAI]]),
    # 「表として読めない」で返る側
    "han_shimon_kuuran": han([["", "2026-01-05", "", SRC_DAICHOU], *han_rows()[1:]]),
    "han_hizuke_kuuran": han([[V1, "", "", SRC_DAICHOU], *han_rows()[1:]]),
    "han_juufuku": han(han_rows() + [[V3, "2026-03-02", V2, SRC_KYOUKAI]]),
    "han_jibun": han([[V1, "2026-01-05", V1, SRC_DAICHOU], *han_rows()[1:]]),
    "han_atama_futatsu": han(han_rows() + [[V_SOTO, "2026-03-20", V2, SRC_KYOUKAI]]),
    # 鎖の先頭が無い(V1 の前の版に V5 を書いて輪にした。日付順なら 1 本に見える表)
    "han_atama_nashi": han([[V1, "2026-01-05", V5, SRC_DAICHOU], *han_rows()[1:]]),
    "han_hanarete": han(han_rows() + [[V_WA1, "2026-06-02", V_WA2, SRC_KYOUKAI],
                                      [V_WA2, "2026-06-03", V_WA1, SRC_KYOUKAI]]),
}

KOWASHITA_SABUN: dict[str, list[list[str]]] = {
    # 止まる理由コードが出る側
    "sabun_shutten_nashi": sabun([[V2, V3, keys(K_E), R.CHANGES[0], R.COVERAGES[1], ""],
                                  *sabun_rows()[1:]]),
    "sabun_hani_kuuran": sabun([[V2, V3, keys(K_E), R.CHANGES[0], "", SRC_KARIOKI],
                                *sabun_rows()[1:]]),
    "sabun_shubetsu_gai": sabun([[V2, V3, keys(K_E), "入れ替え", R.COVERAGES[1],
                                  SRC_KARIOKI], *sabun_rows()[1:]]),
    "sabun_shubetsu_kuuran": sabun([[V2, V3, keys(K_E), "", R.COVERAGES[1],
                                     SRC_KARIOKI], *sabun_rows()[1:]]),
    # 「表として読めない」で返る側
    "sabun_hani_mitouroku": sabun([[V2, V3, keys(K_E), R.CHANGES[0], "だいたい",
                                    SRC_KARIOKI], *sabun_rows()[1:]]),
    "sabun_from_kuuran": sabun([["", V3, keys(K_E), R.CHANGES[0], R.COVERAGES[1],
                                 SRC_KARIOKI], *sabun_rows()[1:]]),
    "sabun_to_kuuran": sabun([[V2, "", keys(K_E), R.CHANGES[0], R.COVERAGES[1],
                               SRC_KARIOKI], *sabun_rows()[1:]]),
    "sabun_onaji": sabun([[V2, V2, keys(K_E), R.CHANGES[0], R.COVERAGES[1],
                           SRC_KARIOKI], *sabun_rows()[1:]]),
    "sabun_juufuku": sabun(sabun_rows() + [
        [V4, V5, keys(K_D), R.CHANGES[0], R.COVERAGES[0], SRC_KOUROU]]),
    "sabun_kagi_juufuku": sabun([[V2, V3, keys(K_E, K_E), R.CHANGES[0],
                                  R.COVERAGES[1], SRC_KARIOKI], *sabun_rows()[1:]]),
}


def write_all(dest: Path | None = None) -> list[Path]:
    d = dest or HERE
    out: list[Path] = [
        R.write_csv(d / "kekka_a.csv", KEKKA_A),
        R.write_csv(d / "kekka_hizuke.csv", KEKKA_HIZUKE),
        R.write_csv(d / "han_a.csv", HAN_A),
        R.write_csv(d / "han_hizuke.csv", HAN_HIZUKE),
        R.write_csv(d / "sabun_a.csv", SABUN_A),
        R.write_csv(d / "sabun_zenken.csv", SABUN_ZENKEN),
    ]
    for name, rows in {**KOWASHITA_KEKKA, **KOWASHITA_HAN,
                       **KOWASHITA_SABUN}.items():
        out.append(R.write_csv(d / "kowashita" / f"{name}.csv", rows))
    # ヘッダだけの表(3 種とも「表として読めない」で返る)
    out.append(R.write_csv(d / "kowashita" / "kekka_0gyou.csv", [HEAD_KEKKA]))
    out.append(R.write_csv(d / "kowashita" / "han_0gyou.csv", [HEAD_HAN]))
    out.append(R.write_csv(d / "kowashita" / "sabun_0gyou.csv", [HEAD_SABUN]))
    # 列そのものが足りない表
    out.append(R.write_csv(d / "kowashita" / "kekka_retsu_nashi.csv",
                           [HEAD_KEKKA[:-1], KEKKA_A[1][:-1]]))
    out.append(R.write_csv(d / "kowashita" / "han_retsu_nashi.csv",
                           [HEAD_HAN[:-1], HAN_A[1][:-1]]))
    out.append(R.write_csv(d / "kowashita" / "sabun_retsu_nashi.csv",
                           [HEAD_SABUN[:-1], SABUN_A[1][:-1]]))
    return out


if __name__ == "__main__":
    for p in write_all():
        print(f"wrote {p}")
