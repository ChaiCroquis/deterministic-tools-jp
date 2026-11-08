"""off_scope の合成 fixture を作る。**実データ・実在の名前・実在のパスは 1 つも入れない。**

項目 id は記号、項目名は「合成の項目 …(架空)」、領域の記号は「領域 1〜4」、出典は
「合成の…(架空)L<N>」。基準日は `ASOF`(2026-09-20)。

    python fixtures/make_fixtures.py

`kowashita/` には、1 項目も数えずに止まる 7 つの理由コードと、表として読めない 7 通りに
道を付けた崩した表を書く(どのファイルがどの枠を差し替えるかは名前の先頭で分かる)。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import off_scope as H  # noqa: E402

KOWASHITA = HERE / "kowashita"

ASOF = "2026-09-20"

I_SRC = "合成の項目のメモ(架空)"
D_SRC = "合成の領域の登録のメモ(架空)"
P_SRC = "合成の在り所のメモ(架空)"
S_SRC = "合成の入る形のメモ(架空)"
B_SRC = "合成の basis の登録のメモ(架空)"
Y_SRC = "合成の payload の登録のメモ(架空)"

OUT1 = "領域 1"      # 外
EDGE = "領域 2"      # 境界として明示
IN1 = "領域 3"       # 内
OUT2 = "領域 4"      # 外
UNKNOWN = "領域 9"   # 登録表に無い

REQ = "合成の必須の宣言(架空)"
BASIS_OK = "基準日 A"
BASIS_NG = "基準日 C"   # 候補の側にだけ在る欄名(登録表に無い)
PAYLOAD_OK = "表"

# ---------------------------------------------------------------- 項目の台帳(16 行)

ITEMS = [
    # (A) 外 + 在り所 無い + 必須の宣言が在る
    ["I01", "合成の項目 A(架空)", OUT1, REQ, H.NO_MARK, f"{I_SRC}L1"],
    # (B) 外 + 収録(上流由来 12 行)
    ["I02", "合成の項目 B(架空)", OUT1, REQ, H.NO_MARK, f"{I_SRC}L2"],
    # (B) 外 + 照合専用(上流由来 47 行)
    ["I03", "合成の項目 C(架空)", OUT1, H.NO_MARK, "合成の備考(架空)",
     f"{I_SRC}L3"],
    # (C) 外 + 第2層
    ["I04", "合成の項目 D(架空)", OUT1, REQ, H.NO_MARK, f"{I_SRC}L4"],
    # (C) 外 + case属性
    ["I05", "合成の項目 E(架空)", OUT1, H.NO_MARK, H.NO_MARK, f"{I_SRC}L5"],
    # (D) 境界として明示 + 入る形まで書かれている
    ["I06", "合成の項目 F(架空)", EDGE, REQ, H.NO_MARK, f"{I_SRC}L6"],
    # (D) 内 と宣言(収録 5 行が在るが、この部品の対象の外)
    ["I07", "合成の項目 G(架空)", IN1, REQ, H.NO_MARK, f"{I_SRC}L7"],
    # 別枠「出典が空」
    ["I08", "合成の項目 H(架空)", OUT1, REQ, H.NO_MARK, ""],
    # 別枠「領域の記号が登録表に無い」
    ["I09", "合成の項目 I(架空)", UNKNOWN, REQ, H.NO_MARK, f"{I_SRC}L9"],
    # 別枠「同じ項目が 2 か所で別の行き先を宣言されている」
    ["I10", "合成の項目 J(架空)", OUT1, REQ, "合成の備考(架空)",
     f"{I_SRC}L10"],
    # 別枠「basis の欄名が登録表に無い」
    ["I11", "合成の項目 K(架空)", EDGE, REQ, H.NO_MARK, f"{I_SRC}L11"],
    # 別枠「payload 種別が空か登録表に無い」
    ["I12", "合成の項目 L(架空)", EDGE, REQ, H.NO_MARK, f"{I_SRC}L12"],
    # 別枠「期間の終わりの記載が在る」
    ["I13", "合成の項目 M(架空)", EDGE, REQ, H.NO_MARK, f"{I_SRC}L13"],
    # 別枠「必須の宣言も在り所の宣言も無い」
    ["I14", "合成の項目 N(架空)", OUT1, H.NO_MARK, H.NO_MARK, f"{I_SRC}L14"],
    # (B) 外 + 収録(自前抽出 8 行)
    ["I15", "合成の項目 O(架空)", OUT2, REQ, H.NO_MARK, f"{I_SRC}L15"],
    # (A) 外 + 在り所 無い + 必須の宣言が在る(2 件目)
    ["I16", "合成の項目 P(架空)", OUT2, REQ, H.NO_MARK, f"{I_SRC}L16"],
]

# ---------------------------------------------------------------- 領域の登録表(4 行)

DOMAINS = [
    [OUT1, H.STANCES[1], f"{D_SRC}L1"],
    [EDGE, H.STANCES[2], f"{D_SRC}L2"],
    [IN1, H.STANCES[0], f"{D_SRC}L3"],
    [OUT2, H.STANCES[1], f"{D_SRC}L4"],
]

# ---------------------------------------------------------------- 在り所の台帳(14 行)

PLACEMENTS = [
    ["I01", H.PLACES[4], H.NO_MARK, H.NO_MARK, f"{P_SRC}L1"],
    ["I02", H.PLACES[0], "12", H.ORIGINS[1], f"{P_SRC}L2"],
    ["I03", H.PLACES[1], "47", H.ORIGINS[1], f"{P_SRC}L3"],
    ["I04", H.PLACES[2], H.NO_MARK, H.NO_MARK, f"{P_SRC}L4"],
    ["I05", H.PLACES[3], H.NO_MARK, H.NO_MARK, f"{P_SRC}L5"],
    ["I06", H.PLACES[4], H.NO_MARK, H.NO_MARK, f"{P_SRC}L6"],
    ["I07", H.PLACES[0], "5", H.ORIGINS[0], f"{P_SRC}L7"],
    ["I08", H.PLACES[2], H.NO_MARK, H.NO_MARK, f"{P_SRC}L8"],
    ["I09", H.PLACES[2], H.NO_MARK, H.NO_MARK, f"{P_SRC}L9"],
    # 同じ項目に別の行き先が 2 行(別枠へ)
    ["I10", H.PLACES[4], H.NO_MARK, H.NO_MARK, f"{P_SRC}L10"],
    ["I10", H.PLACES[2], H.NO_MARK, H.NO_MARK, f"{P_SRC}L11"],
    ["I11", H.PLACES[2], H.NO_MARK, H.NO_MARK, f"{P_SRC}L12"],
    ["I12", H.PLACES[2], H.NO_MARK, H.NO_MARK, f"{P_SRC}L13"],
    ["I13", H.PLACES[2], H.NO_MARK, H.NO_MARK, f"{P_SRC}L14"],
    ["I14", H.PLACES[4], H.NO_MARK, H.NO_MARK, f"{P_SRC}L15"],
    ["I15", H.PLACES[0], "8", H.ORIGINS[0], f"{P_SRC}L16"],
    ["I16", H.PLACES[4], H.NO_MARK, H.NO_MARK, f"{P_SRC}L17"],
]

# ---------------------------------------------------------------- 入る形の宣言表(5 行)

SHAPES = [
    # 3 欄とも埋まっている(= (D) へ進む)
    ["I06", BASIS_OK, PAYLOAD_OK, "区分 / 人数", H.NO_MARK, f"{S_SRC}L1"],
    # basis の欄名が登録表に無い(候補の側にだけ在る)
    ["I11", BASIS_NG, PAYLOAD_OK, "区分", H.NO_MARK, f"{S_SRC}L2"],
    # payload の欄が空
    ["I12", BASIS_OK, H.NO_MARK, "区分", H.NO_MARK, f"{S_SRC}L3"],
    # 期間の終わりの記載が在る
    ["I13", BASIS_OK, PAYLOAD_OK, "区分", "合成の期間の終わり(架空)",
     f"{S_SRC}L4"],
    # 入る形は書かれているが、領域が `外` なので (D) にはならない
    ["I01", BASIS_OK, PAYLOAD_OK, "区分", H.NO_MARK, f"{S_SRC}L5"],
]

# ---------------------------------------------------------------- 登録表 2 枚

BASIS = [
    [BASIS_OK, "合成の欄名(架空)", f"{B_SRC}L1"],
    ["基準日 B", "合成の欄名(架空)", f"{B_SRC}L2"],
]

PAYLOAD = [
    [PAYLOAD_OK, "合成の種別(架空)", f"{Y_SRC}L1"],
    ["値", "合成の種別(架空)", f"{Y_SRC}L2"],
    ["数式", "合成の種別(架空)", f"{Y_SRC}L3"],
]


def head(columns: tuple[str, ...], rows: list[list[str]]) -> list[list[str]]:
    return [list(columns)] + [list(r) for r in rows]


def write_base() -> list[Path]:
    return [
        H.write_csv(HERE / "items_a.csv", head(H.ITEM_COLUMNS, ITEMS)),
        H.write_csv(HERE / "domains_a.csv", head(H.DOMAIN_COLUMNS, DOMAINS)),
        H.write_csv(HERE / "placements_a.csv", head(H.PLACE_COLUMNS, PLACEMENTS)),
        H.write_csv(HERE / "shapes_a.csv", head(H.SHAPE_COLUMNS, SHAPES)),
        H.write_csv(HERE / "basis_a.csv", head(H.BASIS_COLUMNS, BASIS)),
        H.write_csv(HERE / "payload_a.csv", head(H.PAYLOAD_COLUMNS, PAYLOAD)),
    ]


def write_kowashita() -> list[Path]:
    """1 項目も数えずに止まる 7 つと、表として読めない 7 通りに道を付ける。"""
    out: list[Path] = []

    def w(name: str, columns: tuple[str, ...], rows: list[list[str]]) -> None:
        out.append(H.write_csv(KOWASHITA / name, head(columns, rows)))

    # --- 止まる理由コード 7(基準日が渡されていない は空文字を渡すので表は要らない)
    domains = [list(r) for r in DOMAINS]
    domains[0][2] = ""
    w("domains_出典が空.csv", H.DOMAIN_COLUMNS, domains)

    items = [list(r) for r in ITEMS]
    items.append(["I01", "合成の項目 A(架空、2 行目)", OUT1, REQ, H.NO_MARK,
                  f"{I_SRC}L99"])
    w("items_項目idの重複.csv", H.ITEM_COLUMNS, items)

    domains = [list(r) for r in DOMAINS]
    domains[0][1] = "たぶん外"
    w("domains_宣言が決めた外.csv", H.DOMAIN_COLUMNS, domains)

    placements = [list(r) for r in PLACEMENTS]
    placements[0][1] = "たぶん無い"
    w("placements_記号が決めた外.csv", H.PLACE_COLUMNS, placements)

    placements = [list(r) for r in PLACEMENTS]
    placements[1][2] = "12 行"
    w("placements_行数が整数でない.csv", H.PLACE_COLUMNS, placements)

    w("basis_登録表が空.csv", H.BASIS_COLUMNS, [])

    # --- 表として読めない 7 通り
    w("items_列が足りない.csv", H.ITEM_COLUMNS[:-1], [r[:-1] for r in ITEMS])
    w("items_行が無い.csv", H.ITEM_COLUMNS, [])
    items = [list(r) for r in ITEMS]
    items[0][0] = ""
    w("items_項目idが空.csv", H.ITEM_COLUMNS, items)
    placements = [list(r) for r in PLACEMENTS]
    placements[0][0] = "I99"
    w("placements_項目idが台帳に無い.csv", H.PLACE_COLUMNS, placements)
    shapes = [list(r) for r in SHAPES]
    shapes.append(["I06", BASIS_OK, PAYLOAD_OK, "区分", H.NO_MARK, f"{S_SRC}L9"])
    w("shapes_項目idが2行.csv", H.SHAPE_COLUMNS, shapes)
    domains = [list(r) for r in DOMAINS]
    domains.append([OUT1, H.STANCES[0], f"{D_SRC}L9"])
    w("domains_記号が2行.csv", H.DOMAIN_COLUMNS, domains)
    placements = [list(r) for r in PLACEMENTS]
    placements[3][2] = "3"
    w("placements_行数の欄が余計.csv", H.PLACE_COLUMNS, placements)
    return out


def main() -> None:
    for p in write_base() + write_kowashita():
        print(f"書いた: {p}")


if __name__ == "__main__":
    main()
