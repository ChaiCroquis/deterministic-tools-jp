"""cadence_gap の合成 fixture。**実在の料率・金額・取引先名は 1 つも入っていない。**

数表 id・実行 id・指紋・日付はすべて架空で(指紋は `fp11` のような記号)、実在の値は 1 つも
入っていない(この部品は日付と件数を数えるだけなので、中身が何でも同じように動く)。
写したのは形だけ、つまり

  - 自動で走る宣言が在り、周期も日数で宣言されている数表がある
  - 走った最後の日は新しいのに、中身が動いた最後の日はずっと古い数表がある
  - 落ちた回が履歴に残っていて、その回には指紋が無い
  - 中身が動いた件数が 0 の実行があり、そのうちいくつかは数表の最後の実行になっている
  - 周期の宣言が無い数表の履歴がある / 宣言は在るのに履歴が 1 行も無い数表がある
  - 基準日より後の実行しか無い数表がある
  - 中身が動いた件数と指紋が食い違う実行が、2 通りの向きで在る

の 7 つで、これは私の更新の記録に残っている形だ。記録そのものは出さない。**履歴の行数と
結果の内訳(11 行 / ok 9 / 落ちた回 2)だけは手元の記録と同じ形にそろえてある**(値は架空)。

書くもの(どれも決定論。同じ実行で同じバイト列になる)。

  sengen_a.csv       周期の宣言表 5 行
  rireki_a.csv       実行の履歴表 11 行(ok 9 / 落ちた回 2)
  toi_a.csv          問いの一覧 9 行(数表 6 つ、基準日 4 通り)
  kowashita/*.csv    理由コードと「表として読めない」を出すために 1 か所崩した表

使い方: python fixtures/make_fixtures.py   (この置き場に書き直す)
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import cadence_gap as H  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの(テストがその行を開いて語の在ることを見る)
SRC_LEDGER = "articles/09_update_ledger.md L13"   # 更新 1 回 = 台帳 1 行の回
SRC_CENSUS = "articles/17_check_census.md L13"    # 在るかを数えず走らせる回

HOSHIN = "私の方針の記録(非公開)"
RIREKI = "私の更新の記録(非公開)"
TOI = f"私の鮮度のメモ / {RIREKI}"

ARU, NASHI = H.AUTO
OK, FAILED = H.OK, H.FAILED


def sengen_rows() -> list[list[str]]:
    """周期の宣言表。D5 は意図的に載せない(= 宣言が無い数表)。"""
    return [
        ["D1", "7", ARU, HOSHIN, SRC_LEDGER, "2026-07-01", HOSHIN],
        ["D2", "7", ARU, HOSHIN, HOSHIN, "", ""],
        ["D3", "30", NASHI, HOSHIN, SRC_CENSUS, "", ""],
        ["D4", "7", ARU, HOSHIN, HOSHIN, "", ""],
        ["D6", "7", ARU, HOSHIN, HOSHIN, "", ""],
    ]


def rireki_rows() -> list[list[str]]:
    """実行の履歴表 11 行(ok 9 / 落ちた回 2)。D4 の行は 1 つも無い。"""
    return [
        # D1: 3 回とも中身が動いた。R102 は動いたのに指紋が 1 つ前と同じ
        ["R101", "D1", "2026-05-01", OK, "5", "fp11", RIREKI],
        ["R102", "D1", "2026-05-08", OK, "2", "fp11", RIREKI],
        ["R103", "D1", "2026-05-15", OK, "3", "fp13", RIREKI],
        # D2: 走った最後の日は新しいが、中身が動いた最後の日は 4 月の頭
        ["R201", "D2", "2026-04-03", OK, "9", "fp21", RIREKI],
        ["R202", "D2", "2026-04-10", OK, "0", "fp21", RIREKI],
        ["R203", "D2", "2026-04-17", FAILED, "0", "", RIREKI],
        ["R204", "D2", "2026-05-18", OK, "0", "fp24", RIREKI],
        # D3: 落ちた回と、動いた件数 0 の回しかない
        ["R301", "D3", "2026-05-02", FAILED, "0", "", RIREKI],
        ["R302", "D3", "2026-05-09", OK, "0", "fp32", RIREKI],
        # D5: 周期の宣言が無い数表の履歴
        ["R501", "D5", "2026-05-12", OK, "0", "fp51", RIREKI],
        # D6: 基準日より後の実行しかない
        ["R601", "D6", "2026-06-10", OK, "6", "fp61", RIREKI],
    ]


def toi_rows() -> list[list[str]]:
    """問いの一覧 9 行。D1 と D2 は基準日を替えて 2 回以上きいている。"""
    return [
        ["D1", "2026-05-16", TOI, H.SWAPS[0]],
        ["D1", "2026-05-20", TOI, ""],
        ["D1", "2026-06-01", TOI, ""],
        ["D2", "2026-04-08", TOI, ""],
        ["D2", "2026-05-20", TOI, ""],
        ["D3", "2026-05-20", RIREKI, ""],
        ["D4", "2026-05-20", RIREKI, ""],
        ["D5", "2026-05-20", RIREKI, ""],
        ["D6", "2026-05-20", RIREKI, ""],
    ]


def patch(rows: list[list[str]], edits: dict[tuple[int, int], str],
          extra: list[list[str]] | None = None,
          drop: tuple[int, ...] = ()) -> list[list[str]]:
    """1 か所だけ崩した写しを作る(元の行は書き換えない)。"""
    out = [list(r) for i, r in enumerate(rows) if i not in drop]
    for (i, j), value in edits.items():
        out[i][j] = value
    if extra:
        out.extend(list(r) for r in extra)
    return out


def kowashita() -> dict[str, tuple[tuple[str, ...], list[list[str]]]]:
    """理由コードと「表として読めない」を出すために 1 か所崩した表。"""
    s, r, t = sengen_rows(), rireki_rows(), toi_rows()
    S, R, T = H.SENGEN_COLUMNS, H.RIREKI_COLUMNS, H.TOI_COLUMNS
    return {
        # 理由コード(周期の宣言表)
        "sengen_shutten_nashi": (S, patch(s, {(0, 3): ""})),
        "sengen_shuuki_shutten_nashi": (S, patch(s, {(1, 4): ""})),
        "sengen_id_juufuku": (S, patch(s, {}, extra=[
            ["D1", "7", ARU, HOSHIN, HOSHIN, "", ""]])),
        "sengen_shuuki_zero": (S, patch(s, {(0, 1): "0"})),
        "sengen_kaitei_shutten_nashi": (S, patch(s, {(0, 6): ""})),
        # 表として読めない(周期の宣言表)
        "sengen_retsu_nashi": (S[:-1], [row[:-1] for row in s]),
        "sengen_0gyou": (S, []),
        "sengen_id_kuuran": (S, patch(s, {(0, 0): ""})),
        "sengen_jidou_gai": (S, patch(s, {(0, 2): "ある"})),
        "sengen_shuuki_shousuu": (S, patch(s, {(0, 1): "7.5"})),
        "sengen_kaitei_katachi": (S, patch(s, {(0, 5): "2026/07/01"})),
        # 理由コード(実行の履歴表)
        "rireki_shutten_nashi": (R, patch(r, {(0, 6): ""})),
        "rireki_ochita_kensuu": (R, patch(r, {(5, 4): "3"})),
        "rireki_shimon_nashi": (R, patch(r, {(0, 5): ""})),
        "rireki_ochita_shimon": (R, patch(r, {(7, 5): "fp31"})),
        # 表として読めない(実行の履歴表)
        "rireki_retsu_nashi": (R[:-1], [row[:-1] for row in r]),
        "rireki_0gyou": (R, []),
        "rireki_run_id_juufuku": (R, patch(r, {(1, 0): "R101"})),
        "rireki_id_kuuran": (R, patch(r, {(0, 1): ""})),
        "rireki_kekka_gai": (R, patch(r, {(0, 3): "成功"})),
        "rireki_kensuu_shousuu": (R, patch(r, {(0, 4): "1.5"})),
        "rireki_hizuke_katachi": (R, patch(r, {(0, 2): "2026/05/01"})),
        "rireki_hizuke_nai_hi": (R, patch(r, {(0, 2): "2026-02-30"})),
        # 理由コード(問いの一覧)
        "toi_shutten_nashi": (T, patch(t, {(1, 2): ""})),
        "toi_atesaki_nashi": (T, patch(t, {(6, 0): "D9"})),
        # 表として読めない(問いの一覧)
        "toi_retsu_nashi": (T[:-1], [row[:-1] for row in t]),
        "toi_0gyou": (T, []),
        "toi_id_kuuran": (T, patch(t, {(1, 0): ""})),
        "toi_onaji_toi_juufuku": (T, patch(t, {(1, 1): "2026-05-16"})),
        "toi_kijunbi_katachi": (T, patch(t, {(1, 1): "2026-5-20"})),
        "toi_swap_gai": (T, patch(t, {(0, 3): "シャッフル"})),
        "toi_swap_futatsu": (T, patch(t, {(1, 3): H.SWAPS[1]})),
        # 読めるが verify だけが止まる
        "toi_swap_nashi": (T, patch(t, {(0, 3): ""})),
    }


def main() -> None:
    written = [H.write_csv(HERE / "sengen_a.csv",
                           [list(H.SENGEN_COLUMNS)] + sengen_rows()),
               H.write_csv(HERE / "rireki_a.csv",
                           [list(H.RIREKI_COLUMNS)] + rireki_rows()),
               H.write_csv(HERE / "toi_a.csv", [list(H.TOI_COLUMNS)] + toi_rows())]
    for name, (head, rows) in kowashita().items():
        written.append(H.write_csv(HERE / "kowashita" / f"{name}.csv",
                                   [list(head)] + rows))
    print(f"書いた: {len(written)} 枚(うち崩した表 {len(kowashita())} 枚)")


if __name__ == "__main__":
    main()
