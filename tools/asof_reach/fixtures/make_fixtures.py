"""asof_reach の合成 fixture を作る。**実データ・実在の名前・実在のパスは 1 つも入れない。**

行 id は記号、値の名前は「合成の値 …(架空)」、品質の記号は「記号 1〜5」(+ 登録表に無い
「記号 9」)、出典は「合成の…(架空)L<N>」。日付は架空の暦の上の日付で、実在の改定日と
一致させていない。

    python fixtures/make_fixtures.py

`kowashita/` には、1 行も数えずに止まる 8 つの理由コードと、表として読めない 7 通りに
道を付けた崩した表を書く(どのファイルがどの枠を差し替えるかは名前の先頭で分かる)。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import asof_reach as H  # noqa: E402

KOWASHITA = HERE / "kowashita"

R_SRC = "合成の行のメモ(架空)"
G_SRC = "合成の品質の登録のメモ(架空)"
Q_SRC = "合成の問いのメモ(架空)"
C_SRC = "合成の宣言のメモ(架空)"

REAL = "記号 1"        # 実値
BY_VALID = "記号 2"    # 施行日で仮置き
BY_HEAD = "記号 3"     # 範囲の先頭で仮置き
BY_PROM = "記号 4"     # 公布日で仮置き
UNSURE = "記号 5"      # 不明
UNKNOWN_GRADE = "記号 9"   # 登録表に無い

REASON = "合成の理由(架空)"
OPEN, NO = H.OPEN, H.NO_MARK

# ---------------------------------------------------------------- 行の台帳(19 行)

ROWS = [
    # (A) 実値 + 境界日が別の日(日数 28)
    ["R01", "合成の値 A(架空)", "2026-03-01", OPEN, "2026-02-01", OPEN,
     REAL, "2026-02-01", REASON, f"{R_SRC}L1"],
    # (A) 実値(日数 60)
    ["R02", "合成の値 B(架空)", "2026-04-01", OPEN, "2026-01-31", OPEN,
     REAL, "2026-01-31", REASON, f"{R_SRC}L2"],
    # (A) 実値(効き始める日がずっと先 = 未来有効行の形)
    ["R03", "合成の値 C(架空)", "2028-10-01", OPEN, "2026-06-05", OPEN,
     REAL, "2026-06-05", REASON, f"{R_SRC}L3"],
    # (B) 施行日で仮置き → 境界日が同じ日
    ["R04", "合成の値 D(架空)", "2026-04-01", OPEN, "2026-04-01", OPEN,
     BY_VALID, NO, REASON, f"{R_SRC}L4"],
    # (B) 施行日で仮置き(ずっと前の日)
    ["R05", "合成の値 E(架空)", "2017-04-01", OPEN, "2017-04-01", OPEN,
     BY_VALID, NO, REASON, f"{R_SRC}L5"],
    # (B) 範囲の先頭で仮置き
    ["R06", "合成の値 F(架空)", "2025-04-01", OPEN, "2025-04-01", OPEN,
     BY_HEAD, NO, REASON, f"{R_SRC}L6"],
    # (B) 公布日で仮置き(たまたま同じ日)
    ["R07", "合成の値 G(架空)", "2026-01-01", OPEN, "2026-01-01", OPEN,
     BY_PROM, NO, REASON, f"{R_SRC}L7"],
    # (C) 施行日で仮置きなのに別の日(日数 19)
    ["R08", "合成の値 H(架空)", "2026-03-01", "2027-03-01", "2026-02-10", OPEN,
     BY_VALID, NO, REASON, f"{R_SRC}L8"],
    # (C) 範囲の先頭で仮置き(日数 17)
    ["R09", "合成の値 I(架空)", "2026-04-01", OPEN, "2026-03-15", OPEN,
     BY_HEAD, NO, REASON, f"{R_SRC}L9"],
    # (C) 公布日で仮置き(日数 11)
    ["R10", "合成の値 J(架空)", "2026-10-01", OPEN, "2026-09-20", OPEN,
     BY_PROM, NO, REASON, f"{R_SRC}L10"],
    # (D) 品質が 不明(日付は 2 つそろっている)
    ["R11", "合成の値 K(架空)", "2026-04-01", OPEN, "2026-03-01", OPEN,
     UNSURE, NO, NO, f"{R_SRC}L11"],
    # (D) known_from が記載なし
    ["R12", "合成の値 L(架空)", "2026-04-01", OPEN, NO, OPEN,
     BY_VALID, NO, REASON, f"{R_SRC}L12"],
    # (D) known_to が記載なし(`開` と同じ値にしない)
    ["R13", "合成の値 M(架空)", "2026-04-01", OPEN, "2026-03-01", NO,
     BY_VALID, NO, REASON, f"{R_SRC}L13"],
    # 別枠 1「出典が空」
    ["R14", "合成の値 N(架空)", "2026-04-01", OPEN, "2026-03-01", OPEN,
     BY_VALID, NO, REASON, ""],
    # 別枠 2「品質の記号が登録表に無い」
    ["R15", "合成の値 O(架空)", "2026-04-01", OPEN, "2026-03-01", OPEN,
     UNKNOWN_GRADE, NO, REASON, f"{R_SRC}L15"],
    # 別枠 3「記号が要求する欄が空」(仮置きなのに理由の文字列が無い)
    ["R16", "合成の値 P(架空)", "2026-04-01", OPEN, "2026-03-01", OPEN,
     BY_VALID, NO, NO, f"{R_SRC}L16"],
    # 別枠 4「公表が施行の後(遡及の形)なのに公表日が仮置き」
    ["R17", "合成の値 Q(架空)", "2026-04-01", OPEN, "2026-06-01", OPEN,
     BY_PROM, NO, REASON, f"{R_SRC}L17"],
    # 別枠 5「品質が 実値 なのに別出典の公表日が空」
    ["R18", "合成の値 R(架空)", "2026-04-01", OPEN, "2026-03-01", OPEN,
     REAL, NO, REASON, f"{R_SRC}L18"],
    # 別枠 6「known_to が閉じているのに同じ値の名前の後続行が台帳に無い」
    ["R19", "合成の値 S(架空)", "2026-03-01", OPEN, "2026-02-01", "2026-12-01",
     REAL, "2026-02-01", REASON, f"{R_SRC}L19"],
]

# ---------------------------------------------------------------- 品質の登録表(5 行)

GRADES = [
    [REAL, H.MEANS[0], H.REQUIRES[0], f"{G_SRC}L1"],
    [BY_VALID, H.MEANS[1], H.REQUIRES[1], f"{G_SRC}L2"],
    [BY_HEAD, H.MEANS[2], H.REQUIRES[1], f"{G_SRC}L3"],
    [BY_PROM, H.MEANS[3], H.REQUIRES[1], f"{G_SRC}L4"],
    [UNSURE, H.MEANS[4], H.REQUIRES[2], f"{G_SRC}L5"],
]

# ---------------------------------------------------------------- 問いの台帳(9 行)

ASKS = [
    # (A) の行: as_of を公表日の前日へ戻すと 出ない と言える
    ["Q01", "R01", "2026-01-15", "2026-03-15", f"{Q_SRC}L1"],
    # (A) の行: 公表の後・施行の前(有効時間の端が決める)
    ["Q02", "R01", "2026-02-15", "2026-02-15", f"{Q_SRC}L2"],
    # (A) の行: 両方の中
    ["Q03", "R01", "2026-03-15", "2026-03-15", f"{Q_SRC}L3"],
    # (B) の行: 境界日が同じなので、消えた理由が 見分け不能
    ["Q04", "R04", "2026-03-15", "2026-03-15", f"{Q_SRC}L4"],
    # (B) の行: 両方の中(ここは答えが返る)
    ["Q05", "R04", "2026-05-01", "2026-05-01", f"{Q_SRC}L5"],
    # (C) の行: 仮置きの公表日が除外を決めている
    ["Q06", "R08", "2026-02-01", "2026-03-15", f"{Q_SRC}L6"],
    # (D) の行: 知識時間の経路が無い
    ["Q07", "R11", "2026-03-15", "2026-04-15", f"{Q_SRC}L7"],
    # (D) の行: known_from が記載なし
    ["Q08", "R12", "2026-03-15", "2026-04-15", f"{Q_SRC}L8"],
    # 別枠 7「問いの台帳が指す行 id が行の台帳に無い」
    ["Q09", "R99", "2026-03-15", "2026-04-15", f"{Q_SRC}L9"],
]

# ---------------------------------------------------------------- 宣言の台帳(3 行)

CLAIMS = [
    ["C01", "合成の宣言の文 1(架空)", H.SCOPES[2], f"{C_SRC}L1"],
    ["C02", "合成の宣言の文 2(架空)", H.SCOPES[1], f"{C_SRC}L2"],
    ["C03", "合成の宣言の文 3(架空)", H.SCOPES[0], f"{C_SRC}L3"],
]


def head(columns: tuple[str, ...], rows: list[list[str]]) -> list[list[str]]:
    return [list(columns)] + [list(r) for r in rows]


def write_base() -> list[Path]:
    return [
        H.write_csv(HERE / "rows_a.csv", head(H.ROW_COLUMNS, ROWS)),
        H.write_csv(HERE / "grades_a.csv", head(H.GRADE_COLUMNS, GRADES)),
        H.write_csv(HERE / "asks_a.csv", head(H.ASK_COLUMNS, ASKS)),
        H.write_csv(HERE / "claims_a.csv", head(H.CLAIM_COLUMNS, CLAIMS)),
    ]


def write_kowashita() -> list[Path]:
    """止まる理由コード 8 と、表として読めない 7 通りに道を付ける。"""
    out: list[Path] = []

    def w(name: str, columns: tuple[str, ...], rows: list[list[str]]) -> None:
        out.append(H.write_csv(KOWASHITA / name, head(columns, rows)))

    # --- 止まる理由コード 8
    grades = [list(r) for r in GRADES]
    grades[0][3] = ""
    w("grades_出典が空.csv", H.GRADE_COLUMNS, grades)

    rows = [list(r) for r in ROWS]
    rows.append(["R01", "合成の値 A(架空、2 行目)", "2026-05-01", OPEN,
                 "2026-04-01", OPEN, REAL, "2026-04-01", REASON, f"{R_SRC}L99"])
    w("rows_行idの重複.csv", H.ROW_COLUMNS, rows)

    grades = [list(r) for r in GRADES]
    grades[1][1] = "たぶん仮置き"
    w("grades_意味が決めた外.csv", H.GRADE_COLUMNS, grades)

    grades = [list(r) for r in GRADES]
    grades[1][2] = "たぶん理由"
    w("grades_要求する欄が決めた外.csv", H.GRADE_COLUMNS, grades)

    rows = [list(r) for r in ROWS]
    rows[0][4] = "2026年2月1日"
    w("rows_日付がISOでない.csv", H.ROW_COLUMNS, rows)

    claims = [list(r) for r in CLAIMS]
    claims[0][2] = "たぶん全行"
    w("claims_範囲が決めた外.csv", H.CLAIM_COLUMNS, claims)

    asks = [list(r) for r in ASKS]
    asks[0][2] = ""
    w("asks_as_ofが空.csv", H.ASK_COLUMNS, asks)

    w("grades_登録表が空.csv", H.GRADE_COLUMNS, [])

    # --- 表として読めない 7 通り
    w("rows_列が足りない.csv", H.ROW_COLUMNS[:-1], [r[:-1] for r in ROWS])
    w("rows_行が無い.csv", H.ROW_COLUMNS, [])
    rows = [list(r) for r in ROWS]
    rows[0][0] = ""
    w("rows_行idが空.csv", H.ROW_COLUMNS, rows)
    rows = [list(r) for r in ROWS]
    rows[0][3] = "2026-01-01"
    w("rows_期間の端が逆.csv", H.ROW_COLUMNS, rows)
    grades = [list(r) for r in GRADES]
    grades.append([REAL, H.MEANS[1], H.REQUIRES[1], f"{G_SRC}L9"])
    w("grades_記号が2行.csv", H.GRADE_COLUMNS, grades)
    asks = [list(r) for r in ASKS]
    asks.append(["Q01", "R02", "2026-03-15", "2026-04-15", f"{Q_SRC}L99"])
    w("asks_問いidが2行.csv", H.ASK_COLUMNS, asks)
    claims = [list(r) for r in CLAIMS]
    claims.append(["C01", "合成の宣言の文 9(架空)", H.SCOPES[0], f"{C_SRC}L9"])
    w("claims_宣言idが2行.csv", H.CLAIM_COLUMNS, claims)
    return out


def main() -> None:
    for p in write_base() + write_kowashita():
        print(f"書いた: {p}")


if __name__ == "__main__":
    main()
