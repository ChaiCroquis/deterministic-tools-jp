"""source_pin の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: get(key) が値を返すのは、その key の行が 1 行だけで、原本の現物の sha256 が列と一致し、
locator の場所に raw_text が literal で在り(xlsx_cell はセルの中身と一致)、名前で指定した正規化を通した
raw_text が value と一致する行だけ。それ以外(unavailable・検査落ち・台帳に無い key)は値を返さず PinError で
止まる。manual の行は場所を検査できないので、返り値に必ず転記の印が付く。

既存の test_measure_tampering は、決まった fixture を 1 か所ずつ書き換えて検査が止めるかを数える。
このテストは、原本(テキスト・HTML・xlsx・手元の記録・画像だけの PDF に見立てたファイル)とピンの表を
毎回乱数で作り直し、get の答えを見る。

値は「正規化したあとの値」を先に乱数で決め、そこから原本に書く生の文字を組み立てる(例: 1230000 →
１，２３０，０００円 と 全角半角+カンマ除去+円)。だから期待値は道具の normalize を通さずに分かる。原本の中の
場所(行の並び・セルの中身)も組み立てたときに分かっているので、道具の読み取り(read_text_line /
html_text_lines / read_xlsx_cell)も、検査(verify / verify_pin)も、sha256_of も、期待を作るのには使わない。
テキストには空行を混ぜ(行番号に数える)、HTML には script と style と空行を混ぜる(行番号に数えない)。

困る値として、ピンの 3 割くらいに 1 か所だけ、value を 1 字変える・生の文字に原本に無い字を足す・locator を
原本の外や隣の行・セルへずらす・sha256 列を書き換える・normalizer を空欄 / 登録外の名前 / そのまま にする・
captured_at を空にする・method を登録外にする・xlsx の生の文字を部分文字列にする・unavailable の行に value を
入れる、を入れる。原本ファイルの書き換えと削除、同じ key の行、台帳に無い key の問い合わせも混ぜる。
derandomize=True で毎回同じ入力列を使い、database=None で見つけた例を保存しない(この版の hypothesis は実行した場所に .hypothesis/ を作るが、git と公開側への export では除外される)。
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
import sys
import tempfile
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import source_pin as SP  # noqa: E402

列 = ["key", "value", "raw_text", "source_kind", "source_file", "source_sha256",
      "locator", "method", "normalizer", "captured_at", "note"]           # README の「ピン 1 行の列」
取り出し方 = ("xlsx_cell", "text_line", "html_text", "manual", "unavailable")   # README の 4 種 + 1
正規化の名前 = ("そのまま", "全角半角", "カンマ除去", "パーセント", "円", "日付")   # README の 6 つ
CAPTURED = "2026-10-01T09:00:00+00:00"
SHEET = "料率"
TITLE = "合成(架空)の日数表"
全角 = str.maketrans("0123456789,", "０１２３４５６７８９，")
PDF = b"%PDF-1.4\n% synthetic image-only sample, no text layer\n%%EOF\n"
KIROKU = "配布元についての手元の記録(合成・架空)\npage-00042\n".encode("utf-8")
困りごと = ["生の文字に※を足す", "value を 1 字変える", "sha256 列を書き換える", "normalizer を空欄",
          "登録外の normalizer", "normalizer を そのまま に", "captured_at を空", "登録外の method"]
場所の困りごと = ["locator を隣へ", "locator を原本の外へ"]             # 機械で取り出す 3 種だけ


def 選べる困りごと(m: str, chain: str, raw: str) -> list[str]:
    """そのピンに入れられる困りごと(sampled_from は先頭を選びやすいので、method ごとの困りごとを先に並べる)。"""
    out = ([] if m != "xlsx_cell" or len(raw) < 2 else ["xlsx の生の文字を部分文字列に"])
    out += 場所の困りごと if m != "manual" else []
    return out + [h for h in 困りごと if h != "normalizer を そのまま に" or chain != "そのまま"]
NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------- 値 → 生の文字(組み立てる側で答えが分かる)

@st.composite
def 値の組(draw: st.DrawFn) -> tuple[str, str, str]:
    """(normalizer, raw_text, value)。value を先に決め、raw_text を組み立てる。"""
    chain = draw(st.sampled_from(["カンマ除去+円", "そのまま", "全角半角+カンマ除去+円", "パーセント",
                                  "日付", "カンマ除去"]))
    if chain == "そのまま":
        v = draw(st.one_of(st.sampled_from(["90", "120", "9.98", "650000", "page-00042"]),
                           st.from_regex(r"[0-9]{1,6}(\.[0-9]{1,2})?", fullmatch=True)))
        return chain, v, v
    if chain == "パーセント":
        v = f"{draw(st.integers(0, 20))}.{draw(st.integers(0, 99)):02d}"
        return chain, f"{v}%", v
    if chain == "日付":
        y, m, d = draw(st.integers(2000, 2040)), draw(st.integers(1, 12)), draw(st.integers(1, 28))
        return chain, f"{y}年{m}月{d}日", f"{y:04d}-{m:02d}-{d:02d}"
    n = draw(st.integers(0, 10_000_000))
    if chain == "カンマ除去":
        return chain, f"{n:,}", str(n)
    raw = f"{n:,}円"
    return chain, (raw.translate(全角) if chain.startswith("全角") else raw), str(n)


# ---------------------------------------------------------------- 原本を組む

def xlsx(cells: dict) -> bytes:
    """シート 1 枚の最小の OOXML。("s", 文字) は共有文字列、("inlineStr", 文字) はセル内の文字、("n", 数) は数値。"""
    shared: list = []
    rows: dict = {}
    for ref, (kind, text) in cells.items():
        col, r = ref[0], int(ref[1:])
        if kind == "s":
            if text not in shared:
                shared.append(text)
            c = f'<c r="{ref}" t="s"><v>{shared.index(text)}</v></c>'
        elif kind == "inlineStr":
            c = f'<c r="{ref}" t="inlineStr"><is><t>{escape(text)}</t></is></c>'
        else:
            c = f'<c r="{ref}"><v>{escape(text)}</v></c>'
        rows.setdefault(r, []).append((col, c))
    body = "".join(f'<row r="{r}">' + "".join(c for _, c in sorted(rows[r])) + "</row>" for r in sorted(rows))
    parts = {
        "[Content_Types].xml": (
            f'{DECL}<Types xmlns="{NS_CT}">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/></Types>'),
        "_rels/.rels": (f'{DECL}<Relationships xmlns="{NS_PKG}"><Relationship Id="rId1" '
                        f'Type="{NS_REL}/officeDocument" Target="xl/workbook.xml"/></Relationships>'),
        "xl/workbook.xml": (f'{DECL}<workbook xmlns="{NS_MAIN}" xmlns:r="{NS_REL}"><sheets>'
                            f'<sheet name="{SHEET}" sheetId="1" r:id="rId1"/></sheets></workbook>'),
        "xl/_rels/workbook.xml.rels": (
            f'{DECL}<Relationships xmlns="{NS_PKG}">'
            f'<Relationship Id="rId1" Type="{NS_REL}/worksheet" Target="worksheets/sheet1.xml"/>'
            f'<Relationship Id="rId2" Type="{NS_REL}/sharedStrings" Target="sharedStrings.xml"/></Relationships>'),
        "xl/worksheets/sheet1.xml": f'{DECL}<worksheet xmlns="{NS_MAIN}"><sheetData>{body}</sheetData></worksheet>',
        "xl/sharedStrings.xml": (f'{DECL}<sst xmlns="{NS_MAIN}" count="{len(shared)}" uniqueCount="{len(shared)}">'
                                 + "".join(f"<si><t>{escape(s)}</t></si>" for s in shared) + "</sst>"),
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in parts.items():
            z.writestr(zipfile.ZipInfo(name, date_time=(2026, 10, 1, 9, 0, 0)), text.encode("utf-8"))
    return buf.getvalue()


@dataclass
class ピン:
    row: dict
    場所: str | None = None        # locator の場所にある生の文字(組み立てで分かる。None = 原本の外)
    正規化後: str | None = None     # raw_text を normalizer に通した答え(None = value とは決して合わない)
    困りごと: str = ""


@dataclass
class 場面:
    files: dict                    # 原本のファイル名 → バイト列(手入れの後。消した原本は入らない)
    pins: list
    手入れ: str = ""


def _ピン行(**kw: str) -> dict:
    row = {c: "" for c in 列}
    row.update({"captured_at": CAPTURED, "note": "合成(架空)"}, **kw)
    return row


@st.composite
def 場面たち(draw: st.DrawFn) -> 場面:
    items = draw(st.lists(値の組(), min_size=3, max_size=8))
    text_lines = ["合成(架空)の限度額表", "この見本は PDF から取り出したテキストを模した合成データである。", ""]
    html_lines = [TITLE, "区分ごとの値(合成・架空)"]
    cells: dict = {"A1": ("s", "合成(架空)の料率表")}
    made: list = []   # (method, chain, raw, value, 場所の手がかり)
    for i, (chain, raw, value) in enumerate(items):
        m = draw(st.sampled_from(["text_line", "html_text", "xlsx_cell", "manual"]))
        if m == "text_line":
            if draw(st.booleans()):
                text_lines.append("")                          # 空行も行番号に数える
            text_lines.append(f"  項目{i}  {raw}")
            made.append((m, chain, raw, value, len(text_lines)))
        elif m == "html_text":
            html_lines.append(f"項目{i} {raw}")
            made.append((m, chain, raw, value, len(html_lines)))
        elif m == "xlsx_cell":
            ref = f"B{len(cells) + 1}"
            numeric = re.fullmatch(r"[0-9]+(\.[0-9]+)?", raw) is not None
            cells[ref] = ("n" if numeric and draw(st.booleans()) else draw(st.sampled_from(["s", "inlineStr"])), raw)
            made.append((m, chain, raw, value, ref))
        else:
            made.append((m, chain, raw, value, None))
    # HTML: script と style の中身、空行は行番号に数えない
    html = ["<!DOCTYPE html>", '<html lang="ja">', f'<head><meta charset="utf-8"><title>{TITLE}</title>',
            "<style>p { color: gray; }</style></head>", "<body>", f"<h2>{html_lines[1]}</h2>"]
    for line in html_lines[2:]:
        if draw(st.booleans()):
            html.append(f'<script>var 見本 = "{line}";</script>')
        html.append(f"<p>{line}</p>")
        if draw(st.booleans()):
            html.append("")
    files = {"genpon.txt": ("\n".join(text_lines) + "\n").encode("utf-8"),
             "genpon.html": ("\n".join(html + ["</body>", "</html>", ""])).encode("utf-8"),
             "genpon.xlsx": xlsx(cells), "kiroku.txt": KIROKU, "gazou.pdf": PDF}
    where = {"text_line": ("genpon.txt", "テキスト層のある PDF"), "html_text": ("genpon.html", "日付の無い HTML"),
             "xlsx_cell": ("genpon.xlsx", "表形式の xlsx"), "manual": ("kiroku.txt", "URL が変わる配布元")}
    lines_of = {"text_line": text_lines, "html_text": html_lines}

    def 場所(m: str, loc: str) -> str | None:
        if m in lines_of:
            lines = lines_of[m]
            return lines[int(loc) - 1] if loc.isdigit() and 1 <= int(loc) <= len(lines) else None
        sheet, _, ref = loc.partition("!")
        return cells[ref][1] if loc.count("!") == 1 and sheet == SHEET and ref in cells else None

    pins: list = []
    for i, (m, chain, raw, value, hint) in enumerate(made):
        f, kind = where[m]
        loc = f"{SHEET}!{hint}" if m == "xlsx_cell" else (str(hint) if hint else "手元の記録(機械で辿れない)")
        p = ピン(_ピン行(key=f"値_{i:02d}", value=value, raw_text=raw, source_kind=kind, source_file=f,
                       source_sha256=sha(files[f]), locator=loc, method=m, normalizer=chain),
                  場所(m, loc) if m != "manual" else None, value)
        if draw(st.integers(0, 9)) < 3:
            how = draw(st.sampled_from(選べる困りごと(m, chain, raw)))
            r = p.row
            if how == "value を 1 字変える":
                r["value"] = value + "0"
            elif how == "生の文字に※を足す":                    # 原本には ※ が無い
                r["raw_text"], p.正規化後 = raw + "※", None
            elif how == "locator を原本の外へ" and m in lines_of:
                r["locator"] = draw(st.sampled_from(["0", str(len(lines_of[m]) + 1), "-1", "abc"]))
                p.場所 = None
            elif how == "locator を原本の外へ" and m == "xlsx_cell":
                r["locator"] = draw(st.sampled_from([f"{SHEET}!Z99", f"別のシート!{hint}", str(hint)]))
                p.場所 = None
            elif how == "locator を隣へ" and m in lines_of:
                n = int(loc) + draw(st.sampled_from([-1, 1]))
                n = n if 1 <= n <= len(lines_of[m]) else int(loc) * 2 - n
                r["locator"] = str(n)
                p.場所 = 場所(m, r["locator"])
            elif how == "locator を隣へ" and m == "xlsx_cell":
                r["locator"] = f"{SHEET}!B{int(hint[1:]) + draw(st.sampled_from([-1, 1]))}"
                p.場所 = 場所(m, r["locator"])
            elif how == "sha256 列を書き換える":
                r["source_sha256"] = "0" * 64
            elif how == "normalizer を空欄":
                r["normalizer"] = ""
            elif how == "登録外の normalizer":
                r["normalizer"] = draw(st.sampled_from(["よくある正規化", "円+四捨五入", "全角半角+カンマ"]))
            elif how == "normalizer を そのまま に" and chain != "そのまま":
                r["normalizer"], p.正規化後 = "そのまま", raw.strip()      # そのまま = 何もしない
            elif how == "captured_at を空":
                r["captured_at"] = ""
            elif how == "登録外の method":
                r["method"] = "pdf_text"
            elif how == "xlsx の生の文字を部分文字列に" and m == "xlsx_cell" and len(raw) >= 2:
                r["raw_text"] = r["value"] = p.正規化後 = raw[:-1]
                r["normalizer"] = "そのまま"
            else:
                how = ""
            p.困りごと = how
        pins.append(p)
    for j in range(draw(st.integers(0, 2))):                    # 取れない原本も 1 行として残す
        with_file = draw(st.booleans())
        p = ピン(_ピン行(key=f"取れない_{j}", source_kind="画像だけの PDF",
                       source_file="gazou.pdf" if with_file else "",
                       source_sha256=sha(PDF) if with_file else "", locator="3 ページの表(テキスト層が無い)",
                       method="unavailable"), None, None, "unavailable")
        if draw(st.integers(0, 3)) == 0:
            p.row["value"], p.困りごと = "7.125", "unavailable に value"
        pins.append(p)
    if draw(st.integers(0, 6)) == 0:                            # 同じ key の行
        dup = draw(st.sampled_from(pins))
        pins.append(ピン(dict(dup.row), dup.場所, dup.正規化後, "同じ key"))
    手入れ = draw(st.sampled_from(["なし"] * 6 + ["書き換える", "消す"]))
    if 手入れ != "なし":
        f = draw(st.sampled_from(["genpon.txt", "genpon.html", "genpon.xlsx", "kiroku.txt"]))
        if 手入れ == "書き換える":
            files[f] = files[f] + b"\n"
        else:
            del files[f]
        手入れ = f"{f} を{手入れ}"
    return 場面(files, pins, 手入れ)


# ---------------------------------------------------------------- 期待(道具の関数を使わずに作る)

def 返るはず(p: ピン, keys: Counter, files: dict) -> bool:
    r = p.row
    if keys[r["key"]] != 1 or r["method"] not in 取り出し方 or r["method"] == "unavailable":
        return False
    if any(not r[c] for c in ("value", "raw_text", "source_file", "locator", "captured_at")):
        return False
    if not r["normalizer"] or any(n.strip() not in 正規化の名前 for n in r["normalizer"].split("+")):
        return False
    if r["source_file"] not in files or sha(files[r["source_file"]]) != r["source_sha256"]:
        return False
    if r["method"] != "manual":
        if p.場所 is None:
            return False
        if not ((p.場所 == r["raw_text"]) if r["method"] == "xlsx_cell" else (r["raw_text"] in p.場所)):
            return False
    return p.正規化後 is not None and p.正規化後 == r["value"]


# ---------------------------------------------------------------- 性質テスト

@settings(max_examples=200, derandomize=True, database=None, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(s=場面たち())
def test_いつも成り立つこと_検査を通った行だけが値を返す(s: 場面) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        for name, b in s.files.items():
            (d / name).write_bytes(b)
        with (d / "pins.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=列)
            w.writeheader()
            w.writerows(p.row for p in s.pins)
        table = SP.PinTable.load(d / "pins.csv")
        keys = Counter(p.row["key"] for p in s.pins)
        if s.手入れ != "なし":
            event(f"原本の手入れ: {s.手入れ.split(' を')[1]}")
        seen: set = set()
        for p in s.pins:
            key = p.row["key"]
            if key in seen:
                continue
            seen.add(key)
            want = 返るはず(p, keys, s.files)
            try:
                g = SP.get(table, key)
            except SP.PinError:
                event(f"(b) 止まった: {p.困りごと or ('同じ key' if keys[key] > 1 else '原本の手入れ')}")
                assert not want, (key, p.row, s.手入れ)
                continue
            event(f"(a) 値が返った: {p.row['method']}")
            assert want, (key, p.row, p.困りごと, s.手入れ)
            r = p.row
            assert (g.value, g.raw_text, g.locator, g.method) == (r["value"], r["raw_text"], r["locator"], r["method"])
            assert g.source_sha256 == sha(s.files[r["source_file"]])
            assert g.transcribed == (r["method"] == "manual")
        try:
            SP.get(table, "台帳に無い_key")
            missing_refused = False
        except SP.PinError:
            missing_refused = True
        assert missing_refused
