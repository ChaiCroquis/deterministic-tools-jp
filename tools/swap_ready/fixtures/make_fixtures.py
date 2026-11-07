"""swap_ready の合成 fixture を作る。**実データ・実在の名前・実在のパスは 1 つも入れない。**

経路 id は記号、束の名前は「借り物の束 / 自前の束 / 本番の束 / 配る束 / 照合用の束」、
出典は「合成の…(架空)」。基準日は `ASOF`(2026-09-20)で、宣言された日だけ手元の記録と
同じ形(年の初め・年度の替わり目)にそろえてある。

    python fixtures/make_fixtures.py

`kowashita/` には、1 経路も数えずに止まる 7 つの理由コードと、表として読めない 7 通りに
道を付けた崩した表を書く(どのファイルがどの枠を差し替えるかは名前の先頭で分かる)。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import swap_ready as H  # noqa: E402

KOWASHITA = HERE / "kowashita"

ASOF = "2026-09-20"

R_SRC = "合成の経路のメモ(架空)"
C_SRC = "合成の検査のメモ(架空)"
T_SRC = "合成の跡のメモ(架空)"
P_SRC = "合成の許す宣言の登録のメモ(架空)"
Q_SRC = "合成の検査の所属の登録のメモ(架空)"

BORROWED = "借り物の束"
OWN = "自前の束"
PROD = "本番の束"
SHARED = "配る束"
CROSS = "照合用の束"

SCOPE = "照合専用"

# ---------------------------------------------------------------- 経路の台帳(14 行)

ROUTES = [
    # (A) 許す + 独立 + 跡 3 件
    ["R01", H.KINDS[0], BORROWED, H.PERMISSIONS[0], H.NO_MARK, H.NO_MARK,
     "2026-01-05", f"{R_SRC}L1"],
    # (B) 許す + 内蔵
    ["R02", H.KINDS[0], BORROWED, H.PERMISSIONS[0], H.NO_MARK, H.NO_MARK,
     "2026-03-02", f"{R_SRC}L2"],
    # (C) 範囲つきで許す(範囲の中) + 独立 + 跡 0 件
    ["R03", H.KINDS[2], BORROWED, H.PERMISSIONS[1], SCOPE, "data",
     "2026-01-05", f"{R_SRC}L3"],
    # 別枠「許可の範囲の外」(範囲は data だけなのに、通す対象は実装)
    ["R04", H.KINDS[1], BORROWED, H.PERMISSIONS[1], SCOPE, "data",
     "2026-01-05", f"{R_SRC}L4"],
    # 別枠「跡を残す欄そのものが無い」(許す + 独立だが、跡の欄が無い)
    ["R05", H.KINDS[1], OWN, H.PERMISSIONS[0], H.NO_MARK, H.NO_MARK,
     "2026-02-10", f"{R_SRC}L5"],
    # (D) 許さないと宣言(線の外)
    ["R06", H.KINDS[1], BORROWED, H.PERMISSIONS[2], H.NO_MARK, H.NO_MARK,
     H.NO_MARK, f"{R_SRC}L6"],
    # (D) 宣言なし(未規定)
    ["R07", H.KINDS[3], PROD, H.PERMISSIONS[3], H.NO_MARK, H.NO_MARK,
     H.NO_MARK, f"{R_SRC}L7"],
    # (B) 許す + 検査が無い
    ["R08", H.KINDS[3], PROD, H.PERMISSIONS[0], H.NO_MARK, H.NO_MARK,
     "2026-06-20", f"{R_SRC}L8"],
    # 別枠「出典が空」
    ["R09", H.KINDS[0], BORROWED, H.PERMISSIONS[0], H.NO_MARK, H.NO_MARK,
     "2026-01-05", ""],
    # 別枠「記号が登録の外」
    ["R10", H.KINDS[2], BORROWED, "たぶん許す", H.NO_MARK, H.NO_MARK,
     "2026-01-05", f"{R_SRC}L10"],
    # 別枠「その記号が要求する欄が空」(`許す` は宣言された日を要求する)
    ["R11", H.KINDS[1], OWN, H.PERMISSIONS[0], H.NO_MARK, H.NO_MARK,
     H.NO_MARK, f"{R_SRC}L11"],
    # 別枠「矛盾する宣言」(同じ経路に 独立 と 内蔵 の 2 行)
    ["R12", H.KINDS[3], PROD, H.PERMISSIONS[0], H.NO_MARK, H.NO_MARK,
     "2026-05-01", f"{R_SRC}L12"],
    # 別枠「矛盾する宣言」(独立と書いてあるが、束の名前が入れ替える側と同じ)
    ["R13", H.KINDS[0], BORROWED, H.PERMISSIONS[0], H.NO_MARK, H.NO_MARK,
     "2026-01-05", f"{R_SRC}L13"],
    # (A) 範囲つきで許す(範囲に 2 種別)+ 独立 + 跡 2 件
    ["R14", H.KINDS[2], BORROWED, H.PERMISSIONS[1], SCOPE, "data/行",
     "2026-01-05", f"{R_SRC}L14"],
]

# ---------------------------------------------------------------- 検査の台帳(10 行)

CHECKS = [
    ["C01", "R01", H.PLACEMENTS[0], CROSS, f"{C_SRC}L1"],
    ["C02", "R02", H.PLACEMENTS[1], H.NO_MARK, f"{C_SRC}L2"],
    ["C03", "R03", H.PLACEMENTS[0], CROSS, f"{C_SRC}L3"],
    ["C04", "R04", H.PLACEMENTS[0], CROSS, f"{C_SRC}L4"],
    ["C05", "R05", H.PLACEMENTS[0], CROSS, f"{C_SRC}L5"],
    ["C08", "R08", H.PLACEMENTS[2], H.NO_MARK, f"{C_SRC}L8"],
    ["C12", "R12", H.PLACEMENTS[0], CROSS, f"{C_SRC}L12"],
    ["C13", "R12", H.PLACEMENTS[1], H.NO_MARK, f"{C_SRC}L13"],
    ["C14", "R13", H.PLACEMENTS[0], BORROWED, f"{C_SRC}L14"],
    ["C15", "R14", H.PLACEMENTS[0], CROSS, f"{C_SRC}L15"],
]

# ---------------------------------------------------------------- 跡の台帳(7 行)

TRACES = [
    ["R01", "入れ替えの欄", "3", "11 行", "", f"{T_SRC}L1"],
    ["R02", "版の欄", "0", "11 行", "走らせる段取りが未登録", f"{T_SRC}L2"],
    ["R03", "版の欄", "0", "11 行", "", f"{T_SRC}L3"],
    # 理由だけの行(欄の名前を `—` にすると、跡を数える行にはならない)
    ["R03", H.NO_MARK, H.NO_MARK, H.NO_MARK, "取りに行く段取りが未登録",
     f"{T_SRC}L4"],
    ["R05", H.NO_MARK, H.NO_MARK, H.NO_MARK, "別の束の受け入れ検査がまだ無い",
     f"{T_SRC}L5"],
    ["R08", H.NO_MARK, H.NO_MARK, H.NO_MARK, "", f"{T_SRC}L6"],
    ["R14", "版の欄", "2", "11 行", "", f"{T_SRC}L7"],
]

PERMS = [
    [H.PERMISSIONS[0], "入れ替えてよいと書かれている", H.PERM_REQUIRES[1],
     f"{P_SRC}L1"],
    [H.PERMISSIONS[1], "範囲を限って入れ替えてよいと書かれている",
     H.PERM_REQUIRES[2], f"{P_SRC}L2"],
    [H.PERMISSIONS[2], "入れ替えないと書かれている", H.PERM_REQUIRES[0],
     f"{P_SRC}L3"],
    [H.PERMISSIONS[3], "どちらの宣言も見つからない", H.PERM_REQUIRES[0],
     f"{P_SRC}L4"],
]

PLACES = [
    [H.PLACEMENTS[0], "入れ替える側と別の束に在る", H.PLACE_REQUIRES[1], f"{Q_SRC}L1"],
    [H.PLACEMENTS[1], "入れ替える側と同じ束に在る", H.PLACE_REQUIRES[0], f"{Q_SRC}L2"],
    [H.PLACEMENTS[2], "受け入れ検査が無い", H.PLACE_REQUIRES[0], f"{Q_SRC}L3"],
]


def head(columns: tuple[str, ...], rows: list[list[str]]) -> list[list[str]]:
    return [list(columns)] + [list(r) for r in rows]


def write_base() -> list[Path]:
    return [
        H.write_csv(HERE / "routes_a.csv", head(H.ROUTE_COLUMNS, ROUTES)),
        H.write_csv(HERE / "checks_a.csv", head(H.CHECK_COLUMNS, CHECKS)),
        H.write_csv(HERE / "traces_a.csv", head(H.TRACE_COLUMNS, TRACES)),
        H.write_csv(HERE / "permissions_a.csv", head(H.PERM_COLUMNS, PERMS)),
        H.write_csv(HERE / "placements_a.csv", head(H.PLACE_COLUMNS, PLACES)),
    ]


def write_kowashita() -> list[Path]:
    """1 経路も数えずに止まる 7 つと、表として読めない 7 通りに道を付ける。"""
    out: list[Path] = []

    def w(name: str, columns: tuple[str, ...], rows: list[list[str]]) -> None:
        out.append(H.write_csv(KOWASHITA / name, head(columns, rows)))

    # --- 止まる理由コード 7(基準日が渡されていない は空文字を渡すので表は要らない)
    perms = [list(r) for r in PERMS]
    perms[0][3] = ""
    w("permissions_出典が空.csv", H.PERM_COLUMNS, perms)

    routes = [list(r) for r in ROUTES]
    routes.append(["R01", H.KINDS[0], BORROWED, H.PERMISSIONS[0], H.NO_MARK,
                   H.NO_MARK, "2026-01-05", f"{R_SRC}L99"])
    w("routes_経路idの重複.csv", H.ROUTE_COLUMNS, routes)

    w("permissions_記号が足りない.csv", H.PERM_COLUMNS, [list(r) for r in PERMS[:3]])

    perms = [list(r) for r in PERMS]
    perms[0][2] = "跡の欄"
    w("permissions_要求する欄が外.csv", H.PERM_COLUMNS, perms)

    routes = [list(r) for r in ROUTES]
    routes[0][6] = "2026-12-01"
    w("routes_宣言された日が未来.csv", H.ROUTE_COLUMNS, routes)

    traces = [list(r) for r in TRACES]
    traces[0][2] = "3 件"
    w("traces_件数が整数でない.csv", H.TRACE_COLUMNS, traces)

    # --- 表として読めない 7 通り
    w("routes_列が足りない.csv", H.ROUTE_COLUMNS[:-1],
      [r[:-1] for r in ROUTES])
    w("routes_行が無い.csv", H.ROUTE_COLUMNS, [])
    routes = [list(r) for r in ROUTES]
    routes[0][1] = "たぶん版"
    w("routes_種別記号が外.csv", H.ROUTE_COLUMNS, routes)
    routes = [list(r) for r in ROUTES]
    routes[0][0] = ""
    w("routes_経路idが空.csv", H.ROUTE_COLUMNS, routes)
    checks = [list(r) for r in CHECKS]
    checks[0][1] = "R99"
    w("checks_経路idが台帳に無い.csv", H.CHECK_COLUMNS, checks)
    places = [list(r) for r in PLACES]
    places.append([H.PLACEMENTS[0], "二重に登録した記号", H.PLACE_REQUIRES[1],
                   f"{Q_SRC}L9"])
    w("placements_記号が2行.csv", H.PLACE_COLUMNS, places)
    places = [list(r) for r in PLACES]
    places[0][0] = "たぶん独立"
    w("placements_決めた記号の外.csv", H.PLACE_COLUMNS, places)
    return out


def main() -> None:
    for p in write_base() + write_kowashita():
        print(f"書いた: {p}")


if __name__ == "__main__":
    main()
