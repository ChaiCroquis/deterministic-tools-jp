"""cohort_close の合成 fixture を作る。**実データ・実在の名前・実在のパスは 1 つも入れない。**

rule id は記号(R01〜)、終わりの記載は「合成の終わりの記載(架空)」、線の日付は架空、
出典は「合成の…(架空)L<N>」。

    python fixtures/make_fixtures.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import cohort_close as C  # noqa: E402

R_SRC = "合成の行のメモ(架空)"
L_SRC = "合成の線のメモ(架空)"
S_SRC = "合成の登録のメモ(架空)"
V_SRC = "合成の収録のメモ(架空)"
END = "合成の終わりの記載(架空)"

# ---------------------------------------------------------------- 行の台帳(17 行 = rule 16 件)
ROWS = [
    ["R01", END, "", f"{R_SRC}L1"],             # (A) 収録
    ["R02", END, "", f"{R_SRC}L2"],             # (A) 未収録
    ["R03", "", "", f"{R_SRC}L3"],              # (B) 生年月日の線(以前)未収録
    ["R04", "", "", f"{R_SRC}L4"],              # (B) 生年月日の線(以降)未収録
    ["R05", "", "", f"{R_SRC}L5"],              # (B) 年齢の線、含む側の語なし、収録
    ["R06", END, "", f"{R_SRC}L6"],             # (C) 到達日の線 + 終わりの記載、収録
    ["R07", "", "", f"{R_SRC}L7"],              # (B) 裁定の別、含む側の語なし、記載なし
    ["R08", "", C.NONE_NOTE, f"{R_SRC}L8"],     # (D) 収録
    ["R09", "", "", f"{R_SRC}L9"],              # (D) 収録の台帳に行が無い
    ["R10", "", "", f"{R_SRC}L10"],             # 別枠 書き分けなし
    ["R11", "", "", f"{R_SRC}L11"],             # 別枠 出典が空(線の側)
    ["R12", "", "", f"{R_SRC}L12"],             # 別枠 登録表に無い記号
    ["R13", END, "", f"{R_SRC}L13"],            # 別枠 id の重複
    ["R13", "", "", f"{R_SRC}L14"],
    ["R14", END, C.NONE_NOTE, f"{R_SRC}L15"],   # 別枠 同時に書かれた
    ["R15", "", "", f"{R_SRC}L16"],             # (B) 文書に閉じると書いてある、語なし、未収録
    ["R16", "", "", f"{R_SRC}L17"],             # (B) 生年月日の線だが年度の形(読めない線)未収録
]

# ---------------------------------------------------------------- 線の台帳(11 行)
LINES = [
    ["R03", "1970-01-01 以前生まれのみ", "以前", C.SYM_BIRTH, f"{L_SRC}L1"],
    ["R04", "1975-06-02 以降", "以降", C.SYM_BIRTH, f"{L_SRC}L2"],
    ["R05", "合成の年齢の基準(架空)", "", "年齢の線", f"{L_SRC}L3"],
    ["R06", "合成の到達日(架空)", "以降", "到達日の線", f"{L_SRC}L4"],
    ["R07", "合成の裁定の別(架空)", "", "裁定の別", f"{L_SRC}L5"],
    ["R10", "合成の年齢の範囲(架空)", "〜", C.SYM_UNSPLIT, f"{L_SRC}L6"],
    ["R11", "合成の線(架空)", "以前", "年齢の線", ""],
    ["R12", "合成の線(架空)", "以前", "登録していない記号", f"{L_SRC}L8"],
    ["R15", "合成の閉じるという記載(架空)", "", "文書に閉じると書いてある", f"{L_SRC}L9"],
    ["R16", "〜1970 年度生まれ", "〜", C.SYM_BIRTH, f"{L_SRC}L10"],
    ["R99", "合成の線(架空)", "以前", "年齢の線", f"{L_SRC}L11"],
]

# ---------------------------------------------------------------- 記号の登録表(6 行)
SYMBOLS = [[r[0], r[1], f"{S_SRC}L{i}"] for i, r in enumerate(C.TEMPLATES["symbols.csv"][1:], 1)]

# ---------------------------------------------------------------- 収録の台帳(15 行)
COVER = [
    ["R01", "収録", f"{V_SRC}L1"], ["R02", "未収録", f"{V_SRC}L2"],
    ["R03", "未収録", f"{V_SRC}L3"], ["R04", "未収録", f"{V_SRC}L4"],
    ["R05", "収録", f"{V_SRC}L5"], ["R06", "収録", f"{V_SRC}L6"],
    ["R07", "記載なし", f"{V_SRC}L7"], ["R08", "収録", f"{V_SRC}L8"],
    ["R10", "収録", f"{V_SRC}L9"], ["R11", "未収録", f"{V_SRC}L10"],
    ["R12", "未収録", f"{V_SRC}L11"], ["R13", "収録", f"{V_SRC}L12"],
    ["R14", "記載なし", f"{V_SRC}L13"], ["R15", "未収録", f"{V_SRC}L14"],
    ["R16", "未収録", f"{V_SRC}L15"],
]

FILES = {"rows_a.csv": (C.ROW_COLS, ROWS), "lines_a.csv": (C.LINE_COLS, LINES),
         "symbols_a.csv": (C.SYMBOL_COLS, SYMBOLS), "coverage_a.csv": (C.COVER_COLS, COVER)}


def main() -> None:
    for name, (cols, body) in FILES.items():
        with (HERE / name).open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows(body)
        print(f"{name}: {len(body)} 行")


if __name__ == "__main__":
    main()
