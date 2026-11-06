"""copy_grade の合成 fixture を作る。**実データ・実在のコード・実在の名前は 1 つも入れない。**

部品 id は記号、箇所 id は記号、写しは「同じ形の処理を書いてみた小さな断片」で、
出典は「合成の…(架空)」。箇所数の文字列だけ、手元の棚卸しと同じ形(`17` / `8+` /
`18 ファイル` / `4 + 5`)にそろえてある。

    python fixtures/make_fixtures.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import copy_grade as H  # noqa: E402

BOX = HERE / "copies"
KOWASHITA = HERE / "kowashita"

PART = "合成の棚卸しのメモ(架空)"
SITE = "合成の箇所のメモ(架空)"
NOTE = "合成の注記の登録のメモ(架空)"

# ---------------------------------------------------------------- 写し(合成の断片)

# P1 = 文字コードの判定(7 行)
X = (
    "def read_text(path):\n"
    "    raw = path.read_bytes()\n"
    '    for enc in ("cp932", "utf-8-sig", "utf-8"):\n'
    "        try:\n"
    "            return raw.decode(enc)\n"
    "        except UnicodeDecodeError:\n"
    "            continue\n"
)
# X の 3 行目だけ順番が違う(行数は同じ)
X_ORDER = X.replace('("cp932", "utf-8-sig", "utf-8")',
                    '("utf-8-sig", "utf-8", "cp932")')
# X を CRLF にして 2 行目の行末に空白を足し、末尾に空行を足したもの
X_SPACE = (X.replace("    raw = path.read_bytes()\n", "    raw = path.read_bytes()  \n")
           .replace("\n", "\r\n") + "\r\n")

# P2 = 氏名の正規化(4 行 / 5 行)
Y = (
    "def norm_name(s):\n"
    '    s = unicodedata.normalize("NFKC", s)\n'
    '    s = s.replace(" ", "")\n'
    "    return s\n"
)
Y_PLUS = Y.replace("    return s\n", "    s = s.strip()\n    return s\n")

# P3 = 会社名の正規化(5 行。2 行目と 4 行目が違う)
Z = (
    "def norm_corp(s):\n"
    '    s = s.replace("株式会社", "")\n'
    '    s = s.replace("有限会社", "")\n'
    "    s = s.strip()\n"
    "    return s\n"
)
Z_OTHER = (Z.replace('    s = s.replace("株式会社", "")\n',
                     '    s = s.replace("(株)", "")\n')
           .replace("    s = s.strip()\n", "    s = s.rstrip()\n"))

# P4 = 和暦の処理(3 行 / 4 行。組は別枠へ入るので段は付かない)
W1 = (
    'PAT = re.compile(r"(令和|平成|昭和)([0-9]+)年")\n'
    "def to_seireki(s):\n"
    "    return PAT.sub(conv, s)\n"
)
W2 = (
    'PAT = re.compile(r"(令和|平成|昭和)([0-9]+)年([0-9]+)月")\n'
    "def to_seireki(s):\n"
    "    out = PAT.sub(conv, s)\n"
    "    return out\n"
)

# P5 = 台帳のパーサ(7 行 / 8 行 / 9 行)
V1 = (
    "def parse_ledger(rows):\n"
    "    out = []\n"
    "    for row in rows:\n"
    "        if not row[0]:\n"
    "            continue\n"
    "        out.append(to_record(row))\n"
    "    return out\n"
)
V2 = V1.replace("    return out\n", "    out.sort()\n    return out\n")
V3 = V2.replace("    out = []\n", "    out = []\n    rows = list(rows)\n")

# P6 = 送信と認証(4 行。行末の空白と改行だけが違う)
U = (
    "def post(url, body):\n"
    "    r = session.post(url, json=body, timeout=5)\n"
    "    r.raise_for_status()\n"
    "    return r.json()\n"
)
U_SPACE = U.replace("    r.raise_for_status()\n", "    r.raise_for_status()\t\n")

# P7 = ルールマスタの読込(3 行。組は別枠へ入る)
T1 = (
    "def rules_dir():\n"
    "    if getattr(sys, \"frozen\", False):\n"
    "        return Path(sys.executable).parent\n"
)
T2 = T1.replace("        return Path(sys.executable).parent\n",
                "        return Path(sys.argv[0]).parent\n")

# P8 = 外部サービスの API 呼び出し(2 行。箇所は 1 件だけ = 組は 0)
R1 = (
    "def get_records(app, query):\n"
    '    return client.get("/records.json", app=app, query=query)\n'
)

COPIES = {
    "S01.txt": X, "S02.txt": X, "S03.txt": X_SPACE, "S04.txt": X_ORDER,
    "S05.txt": Y, "S06.txt": Y_PLUS,
    "S08.txt": Z, "S09.txt": Z_OTHER,
    "S10.txt": W1, "S11.txt": W2,
    "S12.txt": V1, "S13.txt": V2, "S14.txt": V3,
    "S15.txt": U, "S16.txt": U_SPACE,
    "S17.txt": T1, "S18.txt": T2,
    "S19.txt": R1,
}

# ---------------------------------------------------------------- 3 枚(正常)

PARTS = [
    list(H.PART_COLUMNS),
    ["P1", "CSV の文字コードの判定", "17", "なし", "宣言なし", f"{PART}L1"],
    ["P2", "氏名の正規化", "8+", "なし", "宣言なし", f"{PART}L2"],
    ["P3", "会社名の正規化", "7", "なし", "宣言なし", f"{PART}L3"],
    ["P4", "和暦の処理", "18 ファイル", "なし", "モジュール化は 1 本だけと宣言",
     f"{PART}L4"],
    ["P5", "台帳のパーサ", "3 本が派生複製(451 / 483 / 486 行)", "あり", "宣言なし",
     f"{PART}L5"],
    ["P6", "外部サービスへの送信と認証", "4 / 3", "なし", "宣言なし", f"{PART}L6"],
    ["P7", "ルールマスタの読込", "5(同一関数コピー)", "なし", "宣言なし", f"{PART}L7"],
    ["P8", "外部サービスの API 呼び出し", "8+", "あり", "統一済みと宣言", f"{PART}L8"],
    ["P9", "色分けした表の書き出し", "4 + 5", "なし", "宣言なし", f"{PART}L9"],
]

SITES = [
    list(H.SITE_COLUMNS),
    ["S01", "P1", "S01.txt", "注記なし", "—", f"{SITE}L1"],
    ["S02", "P1", "S02.txt", "注記なし", "—", f"{SITE}L2"],
    ["S03", "P1", "S03.txt", "注記なし", "—", f"{SITE}L3"],
    ["S04", "P1", "S04.txt", "別実装と注記のみ", "—", f"{SITE}L4"],
    ["S05", "P2", "S05.txt", "注記なし", "—", f"{SITE}L5"],
    ["S06", "P2", "S06.txt", "注記なし", "—", f"{SITE}L6"],
    ["S07", "P2", "", "注記なし", "—", f"{SITE}L7"],
    ["S08", "P3", "S08.txt", "同型と注記", "—", f"{SITE}L8"],
    ["S09", "P3", "S09.txt", "同型と注記", "—", f"{SITE}L9"],
    ["S10", "P4", "S10.txt", "散在と注記のみ", "—", f"{SITE}L10"],
    ["S11", "P4", "S11.txt", "散在と注記のみ", "—", ""],
    ["S12", "P5", "S12.txt", "派生と注記", "451", f"{SITE}L12"],
    ["S13", "P5", "S13.txt", "派生と注記", "483", f"{SITE}L13"],
    ["S14", "P5", "S14.txt", "派生と注記", "", f"{SITE}L14"],
    ["S15", "P6", "S15.txt", "指紋一致と注記", "—", f"{SITE}L15"],
    ["S16", "P6", "S16.txt", "指紋一致と注記", "—", f"{SITE}L16"],
    ["S17", "P7", "S17.txt", "注記なし", "—", f"{SITE}L17"],
    ["S18", "P7", "S18.txt", "同一関数コピーと注記", "—", f"{SITE}L18"],
    ["S19", "P8", "S19.txt", "注記なし", "—", f"{SITE}L19"],
]

NOTES = [
    list(H.NOTE_COLUMNS),
    ["指紋一致と注記", "機械が出した指紋が一致すると書かれている", "写し", f"{NOTE}L1"],
    ["同型と注記", "人が見て同じ形だと書かれている", "写し", f"{NOTE}L2"],
    ["派生と注記", "行数の違う派生だと書かれている", "行数", f"{NOTE}L3"],
    ["散在と注記のみ", "散在とだけ書かれ、何か所が同じ実装かは数えていない", "—",
     f"{NOTE}L4"],
    ["注記なし", "同じだと言える根拠が書かれていない", "—", f"{NOTE}L5"],
    ["別実装と注記のみ", "別の実装だと書かれ、同じかどうかは書かれていない", "—",
     f"{NOTE}L6"],
    ["版が違うと注記", "版の違う写しだと書かれている", "行数", f"{NOTE}L7"],
]


def rows_without(rows: list[list[str]], column: str) -> list[list[str]]:
    k = rows[0].index(column)
    return [r[:k] + r[k + 1:] for r in rows]


def replaced(rows: list[list[str]], row_index: int, column: str,
             value: str) -> list[list[str]]:
    out = [list(r) for r in rows]
    out[row_index][rows[0].index(column)] = value
    return out


def main() -> None:
    BOX.mkdir(parents=True, exist_ok=True)
    KOWASHITA.mkdir(parents=True, exist_ok=True)
    for name, body in sorted(COPIES.items()):
        (BOX / name).write_bytes(body.encode("utf-8"))
    # utf-8 として読めない写し(段を付ける前に止まることの材料)
    (BOX / "bin.dat").write_bytes(b"\x89\x50\xff\xfe\x00\x81")

    H.write_csv(HERE / "parts_a.csv", PARTS)
    H.write_csv(HERE / "sites_a.csv", SITES)
    H.write_csv(HERE / "notes_a.csv", NOTES)

    # 1 組も数えずに止まる 6 つの理由コードに、それぞれ道を付ける
    H.write_csv(KOWASHITA / "parts_shutten_kuuran.csv",
                replaced(PARTS, 1, "source", ""))
    H.write_csv(KOWASHITA / "notes_shutten_kuuran.csv",
                replaced(NOTES, 1, "source", ""))
    H.write_csv(KOWASHITA / "parts_id_juufuku.csv",
                PARTS + [["P1", "二重に書いた部品", "17", "なし", "宣言なし",
                          f"{PART}L10"]])
    H.write_csv(KOWASHITA / "sites_id_juufuku.csv",
                SITES + [["S01", "P1", "S02.txt", "注記なし", "—", f"{SITE}L20"]])
    H.write_csv(KOWASHITA / "sites_buhin_nashi.csv",
                SITES + [["S20", "P99", "S01.txt", "注記なし", "—", f"{SITE}L20"]])
    H.write_csv(KOWASHITA / "notes_kigou_juufuku.csv",
                NOTES + [["注記なし", "二重に登録した記号", "—", f"{NOTE}L8"]])
    H.write_csv(KOWASHITA / "sites_onaji_utsushi.csv",
                replaced(SITES, 2, "copy", "S01.txt"))

    # 表として読めない(終了コード 2。組は 1 つも数えない)
    H.write_csv(KOWASHITA / "parts_retsu_nashi.csv", rows_without(PARTS, "declared"))
    H.write_csv(KOWASHITA / "sites_retsu_nashi.csv", rows_without(SITES, "note"))
    H.write_csv(KOWASHITA / "notes_retsu_nashi.csv", rows_without(NOTES, "requires"))
    H.write_csv(KOWASHITA / "parts_0gyou.csv", [list(H.PART_COLUMNS)])
    H.write_csv(KOWASHITA / "sites_0gyou.csv", [list(H.SITE_COLUMNS)])
    H.write_csv(KOWASHITA / "notes_0gyou.csv", [list(H.NOTE_COLUMNS)])
    H.write_csv(KOWASHITA / "parts_gyoushu_gai.csv",
                replaced(PARTS, 1, "industry", "たぶん なし"))
    H.write_csv(KOWASHITA / "parts_touitsu_gai.csv",
                replaced(PARTS, 1, "unified", "たぶん統一済み"))
    H.write_csv(KOWASHITA / "notes_requires_gai.csv",
                replaced(NOTES, 1, "requires", "指紋"))
    H.write_csv(KOWASHITA / "parts_id_kuuran.csv", replaced(PARTS, 1, "part_id", ""))
    H.write_csv(KOWASHITA / "sites_id_kugiri.csv",
                replaced(SITES, 1, "site_id", "S01|S02"))
    H.write_csv(KOWASHITA / "notes_kigou_kuuran.csv", replaced(NOTES, 1, "note", ""))
    H.write_csv(KOWASHITA / "sites_file_nai.csv",
                replaced(SITES, 1, "copy", "S99.txt"))
    H.write_csv(KOWASHITA / "sites_soto.csv",
                replaced(SITES, 1, "copy", "../parts_a.csv"))
    H.write_csv(KOWASHITA / "sites_decode.csv",
                replaced(SITES, 1, "copy", "bin.dat"))

    print(f"写し {len(COPIES)} 本 + utf-8 として読めない 1 本 → {BOX}")
    print(f"3 枚(部品 {len(PARTS) - 1} 行 / 箇所 {len(SITES) - 1} 行 / "
          f"注記 {len(NOTES) - 1} 行)→ {HERE}")
    print(f"崩した表 {len(list(KOWASHITA.glob('*.csv')))} 枚 → {KOWASHITA}")


if __name__ == "__main__":
    main()
