"""source_pin の合成 fixture を決定論的に作る。**実データは使わない**(地域名・値・出典名はすべて架空)。

作るもの(配布元の原本を 5 種類に見立てた合成ファイルと、それを指すピンの表):
    genpon_ryouritsu.xlsx   表形式の xlsx(zipfile で最小の OOXML を組む)
    genpon_gendogaku.txt    テキスト層のある PDF から取り出したテキスト
    genpon_nissu.html       日付が書かれていない HTML
    genpon_gazou.pdf        画像だけの PDF(テキストが取れない = unavailable の原本)
    haifu_kiroku.txt        配布 URL が毎年変わる配布元についての手元の記録
    pins.csv                ピンの表(上のファイルの sha256 を入れる)

使い方: python -X utf8 make_fixtures.py
"""
from __future__ import annotations

import csv
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import source_pin as SP  # noqa: E402

CAPTURED = "2026-10-01T09:00:00+00:00"
ZIP_DATE = (2026, 10, 1, 9, 0, 0)   # 固定(同じ fixture が毎回同じ sha256 になる)

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'

# シート「料率」の中身。("s", 文字列) は共有文字列、("n", 数) は数値セル。
SHEET_NAME = "料率"
CELLS = {
    "A1": ("s", "合成(架空)の料率表"),
    "A2": ("s", "地域"), "B2": ("s", "料率"), "C2": ("s", "上限額"),
    "A3": ("s", "地域I"), "B3": ("n", "9.98"), "C3": ("s", "１，２３０，０００円"),
    "A4": ("s", "地域II"), "B4": ("s", "1.60%"), "C4": ("n", "650000"),
}

TEXT_LINES = [
    "合成(架空)の限度額表",
    "この見本は PDF から取り出したテキストを模した合成データである。",
    "実在の料率・限度額・制度名は入っていない。",
    "",
    "第1表 区分ごとの日額の上限",
    "  区分A  上限 9,999円",
    "  区分B  上限 7,294円",
    "",
    "第2表 賃金日額の上下限",
    "  上限 15,555円",
    "  下限 2,869円",
    "",
    "改定日 2027年8月1日",
    "出典 合成(架空)",
]

HTML = """<!DOCTYPE html>
<html lang="ja">
<head><meta charset="utf-8"><title>合成(架空)の日数表</title></head>
<body>
<h2>区分ごとの日数(合成・架空)</h2>
<table>
<tr><th>区分</th><th>日数</th></tr>
<tr><td>区分A</td><td>90</td></tr>
<tr><td>区分B</td><td>120</td></tr>
</table>
<p>この表には適用開始日が書かれていない(合成データ)。</p>
</body>
</html>
"""

# 画像だけの PDF に見立てた合成ファイル。テキストは取り出せない(= unavailable の原本)。
GAZOU_PDF = b"%PDF-1.4\n% synthetic image-only sample, no text layer\n%%EOF\n"

HAIFU_KIROKU = """配布元についての手元の記録(合成・架空)
この配布元は年度ごとに配布ページの id が変わり、機械で辿れない。
page-00042
来年度のページはまだ公開されていない。
"""


def _xlsx_parts() -> list:
    shared: list = []
    rows: dict = {}
    for ref, (kind, text) in CELLS.items():
        col = "".join(ch for ch in ref if ch.isalpha())
        row = int("".join(ch for ch in ref if ch.isdigit()))
        if kind == "s":
            if text not in shared:
                shared.append(text)
            cell = f'<c r="{ref}" t="s"><v>{shared.index(text)}</v></c>'
        else:
            cell = f'<c r="{ref}"><v>{escape(text)}</v></c>'
        rows.setdefault(row, []).append((col, cell))
    body = ""
    for row in sorted(rows):
        cells = "".join(c for _, c in sorted(rows[row]))
        body += f'<row r="{row}">{cells}</row>'
    sheet = (f'{DECL}<worksheet xmlns="{NS_MAIN}"><sheetData>{body}</sheetData></worksheet>')
    sst_items = "".join(f"<si><t>{escape(s)}</t></si>" for s in shared)
    sst = (f'{DECL}<sst xmlns="{NS_MAIN}" count="{len(shared)}" '
           f'uniqueCount="{len(shared)}">{sst_items}</sst>')
    content_types = (
        f'{DECL}<Types xmlns="{NS_CT}">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-'
        'officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-'
        'officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-'
        'officedocument.spreadsheetml.sharedStrings+xml"/></Types>')
    root_rels = (f'{DECL}<Relationships xmlns="{NS_PKG}"><Relationship Id="rId1" '
                 f'Type="{NS_REL}/officeDocument" Target="xl/workbook.xml"/></Relationships>')
    workbook = (f'{DECL}<workbook xmlns="{NS_MAIN}" xmlns:r="{NS_REL}"><sheets>'
                f'<sheet name="{escape(SHEET_NAME)}" sheetId="1" r:id="rId1"/>'
                f'</sheets></workbook>')
    wb_rels = (f'{DECL}<Relationships xmlns="{NS_PKG}">'
               f'<Relationship Id="rId1" Type="{NS_REL}/worksheet" Target="worksheets/sheet1.xml"/>'
               f'<Relationship Id="rId2" Type="{NS_REL}/sharedStrings" Target="sharedStrings.xml"/>'
               f'</Relationships>')
    return [("[Content_Types].xml", content_types), ("_rels/.rels", root_rels),
            ("xl/workbook.xml", workbook), ("xl/_rels/workbook.xml.rels", wb_rels),
            ("xl/worksheets/sheet1.xml", sheet), ("xl/sharedStrings.xml", sst)]


def write_xlsx(path: Path) -> Path:
    """最小の OOXML を zipfile で組む(openpyxl を使わない = 外部依存なし、毎回同じ sha256)。"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in _xlsx_parts():
            info = zipfile.ZipInfo(name, date_time=ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, text.encode("utf-8"))
    return path


def write_originals(d: Path) -> dict:
    d.mkdir(parents=True, exist_ok=True)
    out = {}
    out["xlsx"] = write_xlsx(d / "genpon_ryouritsu.xlsx")
    out["text"] = d / "genpon_gendogaku.txt"
    out["text"].write_text("\n".join(TEXT_LINES) + "\n", encoding="utf-8", newline="\n")
    out["html"] = d / "genpon_nissu.html"
    out["html"].write_text(HTML, encoding="utf-8", newline="\n")
    out["pdf"] = d / "genpon_gazou.pdf"
    out["pdf"].write_bytes(GAZOU_PDF)
    out["kiroku"] = d / "haifu_kiroku.txt"
    out["kiroku"].write_text(HAIFU_KIROKU, encoding="utf-8", newline="\n")
    return out


def rows_pins(d: Path) -> list:
    """ピンの表。原本 5 種 × 取り出し方。取れない原本も value を空にした行として必ず残す。"""
    f = write_originals(d)
    sha = {k: SP.sha256_of(v) for k, v in f.items()}

    def pin(**kw) -> dict:
        row = {c: "" for c in SP.COLUMNS}
        row["captured_at"] = CAPTURED
        row.update(kw)
        return row

    xlsx, text, html = "genpon_ryouritsu.xlsx", "genpon_gendogaku.txt", "genpon_nissu.html"
    k_xlsx, k_text, k_html = "表形式の xlsx", "テキスト層のある PDF", "日付の無い HTML"
    k_gazou, k_haifu = "画像だけの PDF", "URL が変わる配布元"
    return [
        pin(key="料率_地域I", value="9.98", raw_text="9.98", source_kind=k_xlsx,
            source_file=xlsx, source_sha256=sha["xlsx"], locator="料率!B3",
            method="xlsx_cell", normalizer="そのまま", note="数値セル(合成・架空)"),
        pin(key="料率_地域II", value="1.60", raw_text="1.60%", source_kind=k_xlsx,
            source_file=xlsx, source_sha256=sha["xlsx"], locator="料率!B4",
            method="xlsx_cell", normalizer="パーセント", note="% 付きの文字列セル(合成・架空)"),
        pin(key="上限額_地域I", value="1230000", raw_text="１，２３０，０００円", source_kind=k_xlsx,
            source_file=xlsx, source_sha256=sha["xlsx"], locator="料率!C3",
            method="xlsx_cell", normalizer="全角半角+カンマ除去+円",
            note="全角・カンマ・円が混ざったセル(合成・架空)"),
        pin(key="等級上限", value="650000", raw_text="650000", source_kind=k_xlsx,
            source_file=xlsx, source_sha256=sha["xlsx"], locator="料率!C4",
            method="xlsx_cell", normalizer="そのまま", note="数値セル(合成・架空)"),
        pin(key="上限額_区分B", value="7294", raw_text="7,294円", source_kind=k_text,
            source_file=text, source_sha256=sha["text"], locator="7",
            method="text_line", normalizer="カンマ除去+円", note="PDF から取り出したテキストの 7 行目"),
        pin(key="賃金日額_下限", value="2869", raw_text="2,869円", source_kind=k_text,
            source_file=text, source_sha256=sha["text"], locator="11",
            method="text_line", normalizer="カンマ除去+円", note="同じテキストの 11 行目"),
        pin(key="改定日", value="2027-08-01", raw_text="2027年8月1日", source_kind=k_text,
            source_file=text, source_sha256=sha["text"], locator="13",
            method="text_line", normalizer="日付", note="同じテキストの 13 行目"),
        pin(key="日数_区分A", value="90", raw_text="90", source_kind=k_html,
            source_file=html, source_sha256=sha["html"], locator="6",
            method="html_text", normalizer="そのまま", note="tag を外したテキストの 6 行目"),
        pin(key="日数_適用開始日", value="2017-04-01", raw_text="2017-04-01", source_kind=k_html,
            source_file=html, source_sha256=sha["html"], locator="表の見出し(日付の記載が無い)",
            method="manual", normalizer="そのまま",
            note="HTML に日付が無いので人が仮置きした。接地の検査はできない"),
        pin(key="乗率_世代I", source_kind=k_gazou, source_file="genpon_gazou.pdf",
            source_sha256=sha["pdf"], locator="3 ページの表(テキスト層が無い)",
            method="unavailable", note="画像だけの PDF。value は空のまま残す"),
        pin(key="乗率_世代II", source_kind=k_gazou, source_file="genpon_gazou.pdf",
            source_sha256=sha["pdf"], locator="4 ページの表(テキスト層が無い)",
            method="unavailable", note="同じ PDF。取れない物も 1 行として残す"),
        pin(key="来年度の配布ページ", value="page-00042", raw_text="page-00042", source_kind=k_haifu,
            source_file="haifu_kiroku.txt", source_sha256=sha["kiroku"],
            locator="手元の記録 3 行目(機械で辿れない)", method="manual", normalizer="そのまま",
            note="配布ページの id を人が見て転記した"),
        pin(key="来年度の数表", source_kind=k_haifu, locator="来年度の配布(まだ無い)",
            method="unavailable", note="配布がまだ無いので原本のファイルも無い"),
    ]


def write_pins(path: Path, rows: list) -> Path:
    with open(path, "w", encoding="utf-8", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=list(SP.COLUMNS))
        w.writeheader()
        w.writerows(rows)
    return path


def build(d: Path) -> Path:
    return write_pins(d / "pins.csv", rows_pins(d))


if __name__ == "__main__":
    p = build(HERE)
    print(f"wrote {p} ({len(SP.PinTable.load(p))} pins)")
