"""backing_axis の合成 fixture。**実在の料率・金額・取引先名は 1 つも入っていない。**

行 id・rule id・旧軸の値・欄名・由来の記号は全て架空で、値も日付も 1 つも入っていない(この
部品は宣言と証跡の型が合うかを数えるだけなので、値が要らない)。写したのは形だけ、つまり

  - 同じ旧軸(= 制度の領域)の行が、裏付けの由来で見ると別の塊に割れる
  - 由来は 6 つの記号に分かれるが、要求する証跡の型は 5 種しかない(2 つの記号が同じ型を使う)
  - 欄が埋まっていても、その値が同じ行の別の列から写した仮置きであることがある
  - 由来の記号が登録表に無い行がある(宣言が無い)
  - 旧軸の欄そのものが空の行がある(差し替え前の軸が無い)

の 5 つで、これは私の検証と棚卸しの記録に残っている形だ。記録そのものは出さない。

書くもの(どれも決定論。同じ実行で同じバイト列になる)。

  daichou_a.csv     行の台帳 22 行(1 つの欄の値の裏付けが 1 行)
  touroku_a.csv     由来の登録表 6 行(記号 6 つ、証跡の型 5 種)
  toi_a.csv         問いの一覧 7 行
  kowashita/*.csv   理由コードと「表として読めない」を出すために 1 か所崩した表

使い方: python fixtures/make_fixtures.py   (この置き場に書き直す)
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import backing_axis as H  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの(テストがその行を開いて語の在ることを見る)
SRC_BLANK = "articles/24_blank_kind.md L15"      # 0 と空欄をどちらにも寄せない
SRC_STOCK = "articles/30_cover_stock.md L15"     # 仮置きを実値と読むと在庫は広く見える

KENSHOU = "私の検証の記録(非公開)"
TANAOROSHI = "私の棚卸しの記録(非公開)"
SAGYOU = "私の作業状況の記録(非公開)"
SRC_TOI = f"私の並べ直しのメモ / {TANAOROSHI}"

KIKAI, KEIRO, MOKUSHI, UTSUSHI, TORENAI = "Y1", "Y2", "Y3", "Y4", "Y5"
AITE_NASHI = "Y6"          # 上流をそのまま採り、照合相手が無い(証跡の型は 取れない理由)
MIKKAI = "Y9"              # 登録表に無い記号(別枠「宣言が無い」に出る)


def touroku_rows() -> list[list[str]]:
    """由来の登録表。記号は 6 つで、要求する証跡の型は 5 種(Y5 と Y6 が同じ型)。"""
    return [
        [KIKAI, "機械で再計算して合わせた", H.EVIDENCE_TYPES[0]],
        [KEIRO, "独立した 2 つの経路で突き合わせた", H.EVIDENCE_TYPES[1]],
        [MOKUSHI, "原文と目で見て合わせた", H.EVIDENCE_TYPES[2]],
        [UTSUSHI, "同じ行の別の列から写した仮置き", H.EVIDENCE_TYPES[3]],
        [TORENAI, "原文が取れていない", H.EVIDENCE_TYPES[4]],
        [AITE_NASHI, "上流をそのまま採り、照合する相手が無い", H.EVIDENCE_TYPES[4]],
    ]


def daichou_rows() -> list[list[str]]:
    """行の台帳。旧軸 6 つ(D1〜D6)に、由来 6 記号と別枠 2 種が混ざっている。"""
    return [
        ["B01", "R01", "D1", "V01", KIKAI, "28", KENSHOU],
        ["B02", "R01", "D1", "V02", KIKAI, "12", KENSHOU],
        ["B03", "R02", "D1", "V03", KEIRO, "9", KENSHOU],
        ["B04", "R03", "D1", "V04", AITE_NASHI, "照合する相手の経路が無い", TANAOROSHI],
        ["B05", "R04", "D2", "V05", KEIRO, "4", KENSHOU],
        ["B06", "R05", "D2", "V06", UTSUSHI, "V05", SRC_STOCK],
        ["B07", "R06", "D2", "V07", AITE_NASHI, "上流の JSON をそのまま採った", TANAOROSHI],
        ["B08", "R07", "D3", "V08", MOKUSHI, "1", KENSHOU],
        ["B09", "R08", "D3", "V09", UTSUSHI, "V08", SRC_STOCK],
        ["B10", "R09", "D3", "V10", TORENAI, "原文が画像のままで読めない", SAGYOU],
        ["B11", "R10", "D3", "V11", UTSUSHI, "V10", SAGYOU],
        ["B12", "R11", "D4", "V12", KIKAI, "3", KENSHOU],
        ["B13", "R12", "D4", "V13", AITE_NASHI, "照合する相手の経路が無い", TANAOROSHI],
        ["B14", "R13", "D4", "V14", UTSUSHI, "V13", TANAOROSHI],
        ["B15", "R14", "D5", "V15", KEIRO, "6", KENSHOU],
        ["B16", "R15", "D5", "V16", KEIRO, "2", KENSHOU],
        ["B17", "R16", "D5", "V17", MIKKAI, "", SRC_BLANK],
        ["B18", "R17", "D6", "V18", TORENAI, "原文に日付の欄が無い", TANAOROSHI],
        ["B19", "R18", "D6", "V19", AITE_NASHI, "上流の JSON をそのまま採った", TANAOROSHI],
        ["B20", "R19", "D6", "V20", MIKKAI, "", SRC_BLANK],
        ["B21", "R20", "", "V21", KIKAI, "5", KENSHOU],
        ["B22", "R21", "D6", "V22", UTSUSHI, "V19", SRC_STOCK],
    ]


def toi_rows() -> list[list[str]]:
    """問いの一覧。5 件は旧軸を指し、2 件は指さない(別枠「旧軸が無い」)。"""
    return [
        ["D1", H.AXES[1], SRC_TOI, H.SWAPS[0]],
        ["D2", H.AXES[1], SRC_TOI, ""],
        ["D3", H.AXES[1], TANAOROSHI, ""],
        ["D4", H.AXES[1], SRC_TOI, ""],
        ["D5", H.AXES[1], TANAOROSHI, ""],
        ["", H.AXES[1], SRC_TOI, ""],
        ["D9", H.AXES[1], TANAOROSHI, ""],
    ]


def patch(rows: list[list[str]], edits: dict[tuple[int, int], str],
          extra: list[list[str]] | None = None) -> list[list[str]]:
    """1 か所だけ崩した写しを作る(元の行は書き換えない)。"""
    out = [list(r) for r in rows]
    for (i, j), value in edits.items():
        out[i][j] = value
    if extra:
        out.extend(list(r) for r in extra)
    return out


def kowashita() -> dict[str, tuple[tuple[str, ...], list[list[str]]]]:
    """理由コードと「表として読めない」を出すために 1 か所崩した表。"""
    d, g, t = daichou_rows(), touroku_rows(), toi_rows()
    D, G, T = H.DAICHOU_COLUMNS, H.TOUROKU_COLUMNS, H.TOI_COLUMNS
    return {
        # 理由コード(行の台帳)
        "daichou_shutten_nashi": (D, patch(d, {(0, 6): ""})),
        "daichou_kensuu_kuuran": (D, patch(d, {(0, 5): ""})),
        "daichou_kensuu_seisuu_gai": (D, patch(d, {(0, 5): "7,050"})),
        "daichou_utsushimoto_kuuran": (D, patch(d, {(5, 5): ""})),
        "daichou_utsushimoto_onaji": (D, patch(d, {(5, 5): "V06"})),
        "daichou_riyuu_kuuran": (D, patch(d, {(3, 5): ""})),
        "daichou_ran_juufuku": (D, patch(d, {}, extra=[
            ["B23", "R01", "D1", "V01", KIKAI, "28", KENSHOU]])),
        # 表として読めない(行の台帳)
        "daichou_retsu_nashi": (D[:-1], [row[:-1] for row in d]),
        "daichou_0gyou": (D, []),
        "daichou_id_kuuran": (D, patch(d, {(0, 0): ""})),
        "daichou_id_juufuku": (D, patch(d, {(1, 0): "B01"})),
        "daichou_rule_id_kuuran": (D, patch(d, {(0, 1): ""})),
        "daichou_ranmei_kuuran": (D, patch(d, {(0, 3): ""})),
        "daichou_yurai_katachi": (D, patch(d, {(0, 4): "Y 1"})),
        # 理由コード(由来の登録表)
        "touroku_kata_kuuran": (G, patch(g, {(0, 2): ""})),
        "touroku_kata_gai": (G, patch(g, {(0, 2): "たぶん件数"})),
        "touroku_imi_kuuran": (G, patch(g, {(0, 1): ""})),
        # 表として読めない(由来の登録表)
        "touroku_retsu_nashi": (G[:-1], [row[:-1] for row in g]),
        "touroku_0gyou": (G, []),
        "touroku_kigou_kuuran": (G, patch(g, {(0, 0): ""})),
        "touroku_kigou_juufuku": (G, patch(g, {(1, 0): KIKAI})),
        # 理由コード(問いの一覧)
        "toi_shutten_nashi": (T, patch(t, {(1, 2): ""})),
        "toi_onaji_jiku": (T, patch(t, {(1, 1): H.AXES[0]})),
        # 表として読めない(問いの一覧)
        "toi_retsu_nashi": (T[:-1], [row[:-1] for row in t]),
        "toi_0gyou": (T, []),
        "toi_shinjiku_kuuran": (T, patch(t, {(1, 1): ""})),
        "toi_shinjiku_gai": (T, patch(t, {(1, 1): "裏付けの濃さ"})),
        "toi_onaji_toi_juufuku": (T, patch(t, {(1, 0): "D1"})),
        "toi_kyuujiku_katachi": (T, patch(t, {(1, 0): "D 2"})),
        "toi_swap_gai": (T, patch(t, {(0, 3): "シャッフル"})),
        "toi_swap_futatsu": (T, patch(t, {(1, 3): H.SWAPS[1]})),
        # 読めるが verify だけが止まる
        "toi_swap_nashi": (T, patch(t, {(0, 3): ""})),
    }


def main() -> None:
    written = [H.write_csv(HERE / "daichou_a.csv",
                           [list(H.DAICHOU_COLUMNS)] + daichou_rows()),
               H.write_csv(HERE / "touroku_a.csv",
                           [list(H.TOUROKU_COLUMNS)] + touroku_rows()),
               H.write_csv(HERE / "toi_a.csv", [list(H.TOI_COLUMNS)] + toi_rows())]
    for name, (head, rows) in kowashita().items():
        written.append(H.write_csv(HERE / "kowashita" / f"{name}.csv",
                                   [list(head)] + rows))
    print(f"書いた: {len(written)} 枚(うち崩した表 {len(kowashita())} 枚)")


if __name__ == "__main__":
    main()
