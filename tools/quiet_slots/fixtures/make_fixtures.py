"""quiet_slots の fixture を作り直す。**合成した 4 枚と、崩した表だけ**。

実データ・実在の料率・実在の金額・実在の日付は 1 つも入れない。問い id は記号(Q1〜Q5)、
欄名は記号(K1〜K10)、rule or 式の id は記号(R1〜R3、R9)、出典は「合成の…(架空)」で、
行数の桁だけ手元の棚卸しと同じ形(47 / 55)にそろえてある。

    python fixtures/make_fixtures.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import quiet_slots as Q  # noqa: E402

ASK = "合成の呼び出しのメモ(架空)"
WORD = "合成の宣言のメモ(架空)"
SHAPE = "合成の行数のメモ(架空)"

# 問いの宣言表 5 行。Q1 は欄が 0 本、Q5 は出典が空欄(別枠「出典が空」の道)
ASKS = [
    ["Q1", "status", Q.NO_MARK, "", f"{ASK}L1"],
    ["Q2", "resolve", "R1", "K1|K3", f"{ASK}L2"],
    ["Q3", "compute", "R2", "K1|K5|K6", f"{ASK}L3"],
    ["Q4", "compute", "R3", "K2|K4|K5|K10", f"{ASK}L4"],
    ["Q5", "resolve", "R1", "K1", ""],
]

# 欄の登録表 10 行(9 欄 + K9 の 2 本目 = 同じ欄に 2 通りの宣言)
SLOTS = [
    ["K1", Q.KINDS[0], Q.EMPTIABLE[0], Q.FILLERS[0], Q.EXITS[0], f"{WORD}L1"],
    ["K2", Q.KINDS[0], Q.EMPTIABLE[0], Q.FILLERS[0], Q.EXITS[1], f"{WORD}L2"],
    ["K3", Q.KINDS[1], Q.EMPTIABLE[1], Q.FILLERS[0], Q.NO_MARK, f"{WORD}L3"],
    ["K4", Q.KINDS[1], Q.EMPTIABLE[1], Q.FILLERS[0], Q.NO_MARK, f"{WORD}L4"],
    ["K5", Q.KINDS[3], Q.EMPTIABLE[0], Q.FILLERS[0], Q.EXITS[1], f"{WORD}L5"],
    ["K6", Q.KINDS[4], Q.EMPTIABLE[1], Q.FILLERS[2], Q.NO_MARK, f"{WORD}L6"],
    ["K7", Q.KINDS[2], Q.EMPTIABLE[2], Q.FILLERS[3], Q.NO_MARK, f"{WORD}L7"],
    ["K8", Q.KINDS[1], Q.EMPTIABLE[2], Q.FILLERS[3], Q.NO_MARK, f"{WORD}L8"],
    ["K9", Q.KINDS[4], Q.EMPTIABLE[1], Q.FILLERS[2], Q.NO_MARK, f"{WORD}L9"],
    ["K9", Q.KINDS[4], Q.EMPTIABLE[0], Q.FILLERS[0], Q.EXITS[0], f"{WORD}L10"],
]

# 行の在り方の表 6 行(R9 の 1 行は、どの問いも求めていない宣言の道)
SHAPES = [
    ["R1", "K3", "47", f"{SHAPE}L1"],
    ["R1", "K4", "1", f"{SHAPE}L2"],
    ["R2", "K3", "47", f"{SHAPE}L3"],
    ["R2", "K4", "1", f"{SHAPE}L4"],
    ["R3", "K3", "55", f"{SHAPE}L5"],
    ["R9", "K3", "3", f"{SHAPE}L6"],
]

# 出口の登録表 4 行(「止まる」の定義はここに在る)
EXITS = [
    [Q.EXITS[0], Q.STOPS[0], f"{WORD}L11"],
    [Q.EXITS[1], Q.STOPS[0], f"{WORD}L12"],
    [Q.EXITS[2], Q.STOPS[0], f"{WORD}L13"],
    [Q.EXITS[3], Q.STOPS[1], f"{WORD}L14"],
]


def rows(head: tuple[str, ...], body: list[list[str]]) -> list[list[str]]:
    return [list(head)] + [list(r) for r in body]


def clean() -> dict[str, list[list[str]]]:
    return {"asks_a.csv": rows(Q.ASK_COLUMNS, ASKS),
            "slots_a.csv": rows(Q.SLOT_COLUMNS, SLOTS),
            "shapes_a.csv": rows(Q.SHAPE_COLUMNS, SHAPES),
            "exits_a.csv": rows(Q.EXIT_COLUMNS, EXITS)}


def drop(body: list[list[str]], i: int) -> list[list[str]]:
    out = [list(r) for r in body]
    out.pop(i)
    return out


def put(body: list[list[str]], i: int, j: int, v: str) -> list[list[str]]:
    out = [list(r) for r in body]
    out[i][j] = v
    return out


def add(body: list[list[str]], row: list[str]) -> list[list[str]]:
    return [list(r) for r in body] + [list(row)]


def kowashita() -> dict[str, list[list[str]]]:
    """崩した表。**1 組も数えずに止まるもの 7 + 表として読めないもの**。"""
    out: dict[str, list[list[str]]] = {}

    # --- 1 組も数えずに止まる(理由コード 7 個すべてに道を付ける)
    out["slots_shutten_kuuran.csv"] = rows(Q.SLOT_COLUMNS, put(SLOTS, 0, 5, ""))
    out["shapes_shutten_kuuran.csv"] = rows(Q.SHAPE_COLUMNS, put(SHAPES, 0, 3, ""))
    out["exits_shutten_kuuran.csv"] = rows(Q.EXIT_COLUMNS, put(EXITS, 0, 2, ""))
    out["asks_id_juufuku.csv"] = rows(
        Q.ASK_COLUMNS, add(ASKS, ["Q1", "status", Q.NO_MARK, "", f"{ASK}L6"]))
    out["asks_ran_juufuku.csv"] = rows(
        Q.ASK_COLUMNS, put(ASKS, 1, 3, "K1|K3|K1"))
    out["slots_deguchi_nashi.csv"] = rows(
        Q.SLOT_COLUMNS, put(SLOTS, 0, 4, Q.NO_MARK))
    out["exits_toranai.csv"] = rows(Q.EXIT_COLUMNS, drop(EXITS, 0))
    out["slots_deguchi_tooru.csv"] = rows(
        Q.SLOT_COLUMNS, put(SLOTS, 0, 4, Q.EXITS[3]))
    out["shapes_kumi_juufuku.csv"] = rows(
        Q.SHAPE_COLUMNS, add(SHAPES, ["R1", "K3", "47", f"{SHAPE}L7"]))
    out["exits_kigou_juufuku.csv"] = rows(
        Q.EXIT_COLUMNS, add(EXITS, [Q.EXITS[0], Q.STOPS[1], f"{WORD}L15"]))

    # --- 表として読めない(終了コード 2)
    out["asks_retsu_nashi.csv"] = [["ask_id", "command", "target", "source"]] + [
        [r[0], r[1], r[2], r[4]] for r in ASKS]
    out["asks_0gyou.csv"] = rows(Q.ASK_COLUMNS, [])
    out["asks_id_kugiri.csv"] = rows(Q.ASK_COLUMNS, put(ASKS, 0, 0, "Q 1"))
    out["asks_command_kuuran.csv"] = rows(Q.ASK_COLUMNS, put(ASKS, 0, 1, ""))
    out["asks_target_kuuran.csv"] = rows(Q.ASK_COLUMNS, put(ASKS, 1, 2, ""))
    out["slots_retsu_nashi.csv"] = [["slot", "kind", "emptiable", "source"]] + [
        [r[0], r[1], r[2], r[5]] for r in SLOTS]
    out["slots_0gyou.csv"] = rows(Q.SLOT_COLUMNS, [])
    out["slots_shubetsu_gai.csv"] = rows(
        Q.SLOT_COLUMNS, put(SLOTS, 0, 1, "合成の未登録の種別"))
    out["slots_akeru_gai.csv"] = rows(
        Q.SLOT_COLUMNS, put(SLOTS, 0, 2, "合成の未登録の記号"))
    out["slots_umeru_gai.csv"] = rows(
        Q.SLOT_COLUMNS, put(SLOTS, 0, 3, "合成の未登録の記号"))
    out["slots_deguchi_gai.csv"] = rows(
        Q.SLOT_COLUMNS, put(SLOTS, 0, 4, "合成の未登録の出口"))
    out["slots_ran_kuuran.csv"] = rows(Q.SLOT_COLUMNS, put(SLOTS, 0, 0, ""))
    out["shapes_retsu_nashi.csv"] = [["target", "dimension", "source"]] + [
        [r[0], r[1], r[3]] for r in SHAPES]
    out["shapes_gyousuu_shousuu.csv"] = rows(
        Q.SHAPE_COLUMNS, put(SHAPES, 0, 2, "47.5"))
    out["shapes_gyousuu_zero.csv"] = rows(Q.SHAPE_COLUMNS, put(SHAPES, 0, 2, "0"))
    out["shapes_jigen_kuuran.csv"] = rows(Q.SHAPE_COLUMNS, put(SHAPES, 0, 1, ""))
    out["exits_retsu_nashi.csv"] = [["exit", "source"]] + [
        [r[0], r[2]] for r in EXITS]
    out["exits_0gyou.csv"] = rows(Q.EXIT_COLUMNS, [])
    out["exits_kigou_gai.csv"] = rows(
        Q.EXIT_COLUMNS, put(EXITS, 0, 0, "合成の未登録の出口"))
    out["exits_tomaru_gai.csv"] = rows(
        Q.EXIT_COLUMNS, put(EXITS, 0, 1, "合成の未登録の記号"))
    return out


def main() -> None:
    wrote = 0
    for name, body in clean().items():
        Q.write_csv(HERE / name, body)
        wrote += 1
    for name, body in kowashita().items():
        Q.write_csv(HERE / "kowashita" / name, body)
        wrote += 1
    print(f"書いた: {wrote} 枚(合成 4 + 崩した {len(kowashita())})")


if __name__ == "__main__":
    main()
