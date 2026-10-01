"""source_pin — 配布元の原本から取った値 1 件を「ピン 1 行」で持ち、原本の場所と生の文字に毎回突き合わせる部品。

数表を行で持つ部品(asof_table)も、更新を台帳に残す部品(update_ledger)も、「行がすでにある」ことを
前提にしている。その行を作る工程、つまり配布元の xlsx / PDF / HTML から値を取り出す工程は、
取れる場所と取れない場所がまだらで、取れなかった場所を空欄のまま下流に流すと、前年の値や近い行で静かに埋まる。

この部品は 値 1 件 = ピン 1 行 として次を持ち、毎回原本に突き合わせる。

    key            何の値か
    value          正規化したあとの値(下流が使う値)
    raw_text       原本にある生の文字そのまま
    source_kind    原本の種類(map() の行になる。空欄は「種類の記載なし」に入る)
    source_file    原本のファイル
    source_sha256  原本の sha256(配布元が差し替えたら止まる)
    locator        原本の中の場所(シート名!セル / 行番号 / 人が読んだ場所)
    method         取り出し方(METHODS の 5 種)
    normalizer     raw_text から value を作る正規化の名前(+ で連ねる)。**既定は持たない**
    captured_at    取り出した時刻
    note           覚え書き

検査(verify)は 3 つを見る。
    ① source_file の現物の sha256 が列と一致するか
    ② locator の指す場所に raw_text が literal で在るか(接地)
    ③ normalizer を通した raw_text が value と一致するか
normalizer が空欄の行は **評価せずに止める**(部品は既定の正規化を持たない)。

取れない原本は value を空にした unavailable の行として残す。**取れない物が表から消えないこと**が
この部品の要点で、map() にも必ず 1 行として現れる。get(key) は検査を通った行だけ返し、
近い key・前年の行・直近の値へ落ちる経路と fallback の引数を持たない。

PDF は自前で読まない。PDF から取り出したテキストを入力として受け、PDF 本体には sha256 と
locator だけを張る(画像だけの PDF は unavailable の行になる)。

値そのものの正しさ・原本の解釈は判定しない(原本の場所と文字に合っているかだけ)。
標準ライブラリのみ(zipfile / xml.etree / hashlib / csv / json / html.parser / unicodedata / decimal / argparse)。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import unicodedata
import zipfile
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

COLUMNS = ("key", "value", "raw_text", "source_kind", "source_file", "source_sha256",
           "locator", "method", "normalizer", "captured_at", "note")

# 取り出し方。4 種 + 1(取れない)。
METHODS = {
    "xlsx_cell": "表形式の xlsx を zipfile と xml.etree で直接読む。locator = シート名!セル",
    "text_line": "取り出し済みテキストの locator = 行番号。その行に raw_text が literal で在るか",
    "html_text": "html.parser で tag を外したテキストの行番号(空行を落として 1 から数える)",
    "manual": "人が転記した。値は使えるが返り値に必ず転記の印が付く(接地の検査はできない)",
    "unavailable": "原本から取れない。value は空でなければ止まる",
}
MACHINE = ("xlsx_cell", "text_line", "html_text")

# map() の列。取れない物が表から消えないように、3 列は常に出す。
CATEGORIES = ("機械で取り出せる", "人が転記するしかない", "取れない")
CATEGORY = {"xlsx_cell": CATEGORIES[0], "text_line": CATEGORIES[0], "html_text": CATEGORIES[0],
            "manual": CATEGORIES[1], "unavailable": CATEGORIES[2]}
NO_KIND = "(種類の記載なし)"

# 止まる理由コード(この 8 つで全部)
REASONS = {
    "原本の sha が違う": "source_file の現物の sha256 が列と一致しない(配布元が差し替えた / 原本が無い)",
    "locator が範囲外": "locator の指す場所が原本に無い(シート・セル・行番号が範囲の外)",
    "生の文字が指定場所に無い": "locator の場所に raw_text が literal で見つからない(接地が切れている)",
    "normalizer 空欄": "正規化の名前が書かれていない。部品は既定の正規化を持たないので評価せずに止める",
    "normalizer を通しても value と合わない": "normalizer を通した raw_text が value と一致しない",
    "unavailable なのに value がある": "取れないと書いた行に値が入っている(推測値の混入)",
    "同じ key が 2 行": "同じ key のピンが 2 行ある。どちらを使うかが表から決まらない",
    "列が足りない": "その行がピン行として読めない(必要な列が空 / method・normalizer に登録されていない名前)",
}

STATUS_OK, STATUS_FAILED, STATUS_UNAVAILABLE = "ok", "failed", "unavailable"
CHAIN_SEP = "+"


class TableError(ValueError):
    """ピンの表そのものが読めない(見出しの列が無い / CSV・JSON として壊れている)。"""


class PinError(Exception):
    """get() が値を返せない。reason に理由コード(検査落ちの場合)が入る。"""

    def __init__(self, message: str, reason: str = "") -> None:
        super().__init__(message)
        self.reason = reason


# ---------------------------------------------------------------- 正規化(名前で呼ぶ。既定は無い)

def _decimal_text(s: str, what: str) -> str:
    try:
        return format(Decimal(s), "f")
    except InvalidOperation as e:
        raise ValueError(f"{what} を通したが数として読めない: {s!r}") from e


def _as_is(s: str) -> str:
    return s.strip()


def _nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s).strip()


def _drop_comma(s: str) -> str:
    return s.replace(",", "").replace("，", "").strip()


def _percent(s: str) -> str:
    t = _drop_comma(s.strip().rstrip("%").rstrip("％").strip())
    return _decimal_text(t, "パーセント")


def _yen(s: str) -> str:
    t = _drop_comma(s.strip().rstrip("円").strip())
    return _decimal_text(t, "円")


def _date(s: str) -> str:
    t = _nfkc(s)
    for a, b in (("年", "-"), ("月", "-"), ("日", ""), ("/", "-"), (".", "-")):
        t = t.replace(a, b)
    parts = [p for p in t.strip("-").split("-") if p != ""]
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"日付 を通したが年月日として読めない: {s!r}")
    y, m, d = (int(p) for p in parts)
    if not (1 <= m <= 12 and 1 <= d <= 31):
        raise ValueError(f"日付 を通したが月日が範囲外: {s!r}")
    return f"{y:04d}-{m:02d}-{d:02d}"


NORMALIZERS = {"そのまま": _as_is, "全角半角": _nfkc, "カンマ除去": _drop_comma,
               "パーセント": _percent, "円": _yen, "日付": _date}


def normalize(raw: str, chain: str) -> str:
    """normalizer の名前(+ で連ねる)を左から順に適用する。登録されていない名前は ValueError。"""
    out = raw
    for name in [p.strip() for p in chain.split(CHAIN_SEP)]:
        fn = NORMALIZERS.get(name)
        if fn is None:
            raise ValueError(f"登録されていない normalizer: {name!r}")
        out = fn(out)
    return out


def known_chain(chain: str) -> bool:
    return bool(chain.strip()) and all(p.strip() in NORMALIZERS for p in chain.split(CHAIN_SEP))


# ---------------------------------------------------------------- 原本を読む(場所 → 生の文字)

class LocatorError(ValueError):
    """locator の指す場所が原本に無い。"""


def sha256_of(path: "str | Path") -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find_all(root, name: str) -> list:
    return [e for e in root.iter() if _local(e.tag) == name]


def _si_text(si) -> str:
    return "".join(t.text or "" for t in _find_all(si, "t"))


def _sheet_target(z: zipfile.ZipFile, rid: "str | None") -> "str | None":
    if not rid:
        return None
    rels = ElementTree.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    for r in _find_all(rels, "Relationship"):
        if r.get("Id") == rid:
            t = (r.get("Target") or "").lstrip("/")
            return t if t.startswith("xl/") else f"xl/{t}"
    return None


def read_xlsx_cell(path: "str | Path", locator: str) -> str:
    """xlsx の `シート名!セル` に入っている生の文字を返す(zipfile + xml.etree で直接読む)。"""
    if "!" not in locator:
        raise LocatorError(f"xlsx_cell の locator は シート名!セル で書く: {locator!r}")
    sheet_name, ref = locator.split("!", 1)
    sheet_name, ref = sheet_name.strip(), ref.strip().upper()
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            wb = ElementTree.fromstring(z.read("xl/workbook.xml"))
            target = None
            for sh in _find_all(wb, "sheet"):
                if sh.get("name") != sheet_name:
                    continue
                rid = next((v for k, v in sh.attrib.items() if _local(k) == "id"), None)
                target = _sheet_target(z, rid)
            if target is None or target not in names:
                raise LocatorError(f"シートが無い: {sheet_name!r}")
            shared = ([_si_text(si) for si in
                       _find_all(ElementTree.fromstring(z.read("xl/sharedStrings.xml")), "si")]
                      if "xl/sharedStrings.xml" in names else [])
            sheet = ElementTree.fromstring(z.read(target))
    except zipfile.BadZipFile as e:
        raise LocatorError(f"xlsx として開けない: {path}") from e
    except KeyError as e:
        raise LocatorError(f"xlsx の中身が足りない: {e}") from e
    for c in _find_all(sheet, "c"):
        if c.get("r") != ref:
            continue
        kind = c.get("t", "n")
        if kind == "s":
            v = next((e for e in _find_all(c, "v")), None)
            if v is None or not (v.text or "").strip().isdigit():
                raise LocatorError(f"共有文字列の番号が読めない: {locator!r}")
            i = int(v.text.strip())
            if not 0 <= i < len(shared):
                raise LocatorError(f"共有文字列の番号が範囲外: {locator!r}")
            return shared[i]
        if kind == "inlineStr":
            return "".join(_si_text(e) for e in _find_all(c, "is"))
        v = next((e for e in _find_all(c, "v")), None)
        return (v.text or "") if v is not None else ""
    raise LocatorError(f"セルが無い: {locator!r}")


def read_text_line(path: "str | Path", locator: str) -> str:
    """取り出し済みテキストの locator 行目(1 から数える)をそのまま返す。"""
    lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    return _nth(lines, locator, "行")


def html_text_lines(path: "str | Path") -> list:
    """html.parser で tag を外し、空行を落として並べたテキスト行。locator はこの並びの行番号。"""
    class Collect(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.out: list = []
            self.skip = 0

        def handle_starttag(self, tag, attrs) -> None:
            if tag in ("script", "style"):
                self.skip += 1

        def handle_endtag(self, tag) -> None:
            if tag in ("script", "style") and self.skip:
                self.skip -= 1

        def handle_data(self, data) -> None:
            if self.skip:
                return
            for part in data.splitlines():
                if part.strip():
                    self.out.append(part.strip())

    p = Collect()
    p.feed(Path(path).read_text(encoding="utf-8-sig"))
    p.close()
    return p.out


def read_html_line(path: "str | Path", locator: str) -> str:
    return _nth(html_text_lines(path), locator, "テキスト行")


def _nth(lines: list, locator: str, what: str) -> str:
    s = locator.strip()
    if not s.isdigit() or int(s) < 1:
        raise LocatorError(f"{what} の locator は 1 以上の行番号で書く: {locator!r}")
    i = int(s)
    if i > len(lines):
        raise LocatorError(f"{what} {i} は原本の範囲外(原本は {len(lines)} 行)")
    return lines[i - 1]


READERS = {"xlsx_cell": read_xlsx_cell, "text_line": read_text_line, "html_text": read_html_line}


# ---------------------------------------------------------------- ピンの表

@dataclass(frozen=True)
class Pin:
    key: str = ""
    value: str = ""
    raw_text: str = ""
    source_kind: str = ""
    source_file: str = ""
    source_sha256: str = ""
    locator: str = ""
    method: str = ""
    normalizer: str = ""
    captured_at: str = ""
    note: str = ""

    @classmethod
    def of(cls, row: dict) -> "Pin":
        return cls(**{k: str(row.get(k, "") or "").strip() for k in COLUMNS})

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in COLUMNS}


@dataclass(frozen=True)
class PinTable:
    pins: tuple = ()
    root: Path = field(default_factory=Path)

    def __len__(self) -> int:
        return len(self.pins)

    @classmethod
    def load(cls, path: "str | Path", root: "str | Path | None" = None) -> "PinTable":
        p = Path(path)
        text = p.read_text(encoding="utf-8-sig")
        if p.suffix.lower() == ".json":
            try:
                data = json.loads(text)
            except json.JSONDecodeError as e:
                raise TableError(f"JSON として読めない: {e}") from e
            rows = data.get("pins", data) if isinstance(data, dict) else data
            if not isinstance(rows, list):
                raise TableError("JSON はピン行の配列(または pins を持つ object)で書く")
        else:
            reader = csv.DictReader(text.splitlines())
            head = reader.fieldnames or []
            missing = [c for c in COLUMNS if c not in head]
            if missing:
                raise TableError(f"見出しの列が足りない: {' / '.join(missing)}")
            rows = list(reader)
        return cls(tuple(Pin.of(r) for r in rows), Path(root) if root else p.parent)

    def path_of(self, pin: Pin) -> Path:
        q = Path(pin.source_file)
        return q if q.is_absolute() else self.root / q


# ---------------------------------------------------------------- 検査

@dataclass(frozen=True)
class Result:
    key: str
    method: str
    status: str
    reason: str = ""
    detail: str = ""
    source_kind: str = ""
    transcribed: bool = False

    @property
    def ok(self) -> bool:
        return self.status == STATUS_OK

    def as_dict(self) -> dict:
        d = {"key": self.key, "method": self.method, "status": self.status,
             "source_kind": self.source_kind}
        if self.reason:
            d["reason"], d["detail"] = self.reason, self.detail
        if self.transcribed:
            d["transcribed"] = True
        return d


def _sha_mismatch(pin: Pin, table: PinTable) -> str:
    p = table.path_of(pin)
    if not p.exists():
        return f"原本が見つからない: {pin.source_file}"
    if not pin.source_sha256:
        return f"source_sha256 が空(現物は {sha256_of(p)[:12]}…)"
    have = sha256_of(p)
    if have != pin.source_sha256:
        return f"原本は {have[:12]}…、ピンの列は {pin.source_sha256[:12]}…"
    return ""


def verify_pin(pin: Pin, table: PinTable) -> Result:
    """ピン 1 行を原本に突き合わせる。止まるときは REASONS の理由コードを返す。"""
    def out(status: str, reason: str = "", detail: str = "") -> Result:
        return Result(pin.key, pin.method, status, reason, detail, pin.source_kind,
                      transcribed=(pin.method == "manual" and status == STATUS_OK))

    if not pin.key or pin.method not in METHODS:
        return out(STATUS_FAILED, "列が足りない",
                   f"key={pin.key!r} method={pin.method!r}(method は {' / '.join(METHODS)})")
    if pin.method == "unavailable":
        if pin.value:
            return out(STATUS_FAILED, "unavailable なのに value がある", f"value={pin.value!r}")
        if pin.source_file:
            bad = _sha_mismatch(pin, table)
            if bad:
                return out(STATUS_FAILED, "原本の sha が違う", bad)
        return out(STATUS_UNAVAILABLE)
    for name, cell in (("value", pin.value), ("raw_text", pin.raw_text),
                       ("source_file", pin.source_file), ("locator", pin.locator),
                       ("captured_at", pin.captured_at)):
        if not cell:
            return out(STATUS_FAILED, "列が足りない", f"{name} が空")
    if not pin.normalizer:
        return out(STATUS_FAILED, "normalizer 空欄", "部品は既定の正規化を持たないので評価しない")
    if not known_chain(pin.normalizer):
        return out(STATUS_FAILED, "列が足りない",
                   f"登録されていない normalizer: {pin.normalizer!r}"
                   f"(登録済 {' / '.join(NORMALIZERS)})")
    bad = _sha_mismatch(pin, table)
    if bad:
        return out(STATUS_FAILED, "原本の sha が違う", bad)
    if pin.method in MACHINE:
        try:
            place = READERS[pin.method](table.path_of(pin), pin.locator)
        except LocatorError as e:
            return out(STATUS_FAILED, "locator が範囲外", str(e))
        grounded = (place == pin.raw_text) if pin.method == "xlsx_cell" else (pin.raw_text in place)
        if not grounded:
            return out(STATUS_FAILED, "生の文字が指定場所に無い",
                       f"{pin.locator} にあるのは {place!r}、ピンの生の文字は {pin.raw_text!r}")
    try:
        got = normalize(pin.raw_text, pin.normalizer)
    except ValueError as e:
        return out(STATUS_FAILED, "normalizer を通しても value と合わない", str(e))
    if got != pin.value:
        return out(STATUS_FAILED, "normalizer を通しても value と合わない",
                   f"{pin.normalizer} を通すと {got!r}、value は {pin.value!r}")
    return out(STATUS_OK)


def verify(table: PinTable) -> list:
    """全ピンを検査する。同じ key が 2 行あれば、その key の行は全部止める。"""
    seen: dict = {}
    for pin in table.pins:
        seen[pin.key] = seen.get(pin.key, 0) + 1
    out: list = []
    for pin in table.pins:
        if pin.key and seen[pin.key] > 1:
            out.append(Result(pin.key, pin.method, STATUS_FAILED, "同じ key が 2 行",
                              f"{pin.key} のピンが {seen[pin.key]} 行ある", pin.source_kind))
            continue
        out.append(verify_pin(pin, table))
    return out


def summary(results: list) -> dict:
    by_reason: dict = {}
    for r in results:
        if r.reason:
            by_reason[r.reason] = by_reason.get(r.reason, 0) + 1
    return {"pins": len(results),
            "verified": sum(1 for r in results if r.status == STATUS_OK),
            "transcribed": sum(1 for r in results if r.transcribed),
            "unavailable": sum(1 for r in results if r.status == STATUS_UNAVAILABLE),
            "failed": sum(1 for r in results if r.status == STATUS_FAILED),
            "by_reason": by_reason}


# ---------------------------------------------------------------- 引き当て(落ちる経路を持たない)

@dataclass(frozen=True)
class Got:
    key: str
    value: str
    raw_text: str
    source_file: str
    source_sha256: str
    locator: str
    method: str
    normalizer: str
    transcribed: bool

    def as_dict(self) -> dict:
        return {"key": self.key, "value": self.value, "raw_text": self.raw_text,
                "source_file": self.source_file, "source_sha256": self.source_sha256,
                "locator": self.locator, "method": self.method,
                "normalizer": self.normalizer, "transcribed": self.transcribed}


def get(table: PinTable, key: str) -> Got:
    """検査を通った行だけ返す。近い key・前年の行・直近の値へ落ちる経路は無い(引数も持たない)。"""
    rows = [p for p in table.pins if p.key == key]
    if not rows:
        raise PinError(f"台帳に無い key: {key}", "台帳に無い")
    if len(rows) > 1:
        raise PinError(f"同じ key のピンが {len(rows)} 行ある: {key}", "同じ key が 2 行")
    pin = rows[0]
    r = verify_pin(pin, table)
    if r.status == STATUS_UNAVAILABLE:
        raise PinError(f"取れない原本として台帳にある key: {key}", STATUS_UNAVAILABLE)
    if not r.ok:
        raise PinError(f"検査を通らない key: {key}({r.reason}: {r.detail})", r.reason)
    return Got(pin.key, pin.value, pin.raw_text, pin.source_file, pin.source_sha256,
               pin.locator, pin.method, pin.normalizer, r.transcribed)


# ---------------------------------------------------------------- 地図(取れない物が消えない)

def source_map(table: PinTable) -> dict:
    """原本の種類 × 取り出し方の対応表。unavailable も必ず 1 行として現れる。"""
    kinds: list = []
    for pin in table.pins:
        k = pin.source_kind or NO_KIND
        if k not in kinds:
            kinds.append(k)
    cells = {k: {c: {"count": 0, "keys": []} for c in CATEGORIES} for k in kinds}
    for pin in table.pins:
        cat = CATEGORY.get(pin.method)
        if cat is None:
            continue
        cell = cells[pin.source_kind or NO_KIND][cat]
        cell["count"] += 1
        cell["keys"].append(pin.key)
    totals = {c: sum(cells[k][c]["count"] for k in kinds) for c in CATEGORIES}
    return {"kinds": kinds, "categories": list(CATEGORIES), "cells": cells,
            "totals": totals, "pins": len(table.pins)}


# ---------------------------------------------------------------- CLI

def _cli_verify(args) -> int:
    table = PinTable.load(args.pins, args.root)
    results = verify(table)
    stopped = any(r.status == STATUS_FAILED for r in results)
    print(json.dumps({"ok": not stopped, **summary(results),
                      "rows": [r.as_dict() for r in results]}, ensure_ascii=False))
    return 3 if stopped else 0


def _cli_get(args) -> int:
    table = PinTable.load(args.pins, args.root)
    try:
        print(json.dumps({"ok": True, **get(table, args.key).as_dict()}, ensure_ascii=False))
    except PinError as e:
        print(json.dumps({"ok": False, "key": args.key, "reason": e.reason, "detail": str(e)},
                         ensure_ascii=False))
        return 3
    return 0


def _cli_map(args) -> int:
    print(json.dumps({"ok": True, **source_map(PinTable.load(args.pins, args.root))},
                     ensure_ascii=False))
    return 0


def _cli_init(args) -> int:
    p = Path(args.path)
    if p.exists():
        raise TableError(f"すでにある: {p}(上書きしない)")
    example = Pin(key="取れない値の例", source_kind="画像だけの PDF", method="unavailable",
                  note="取れない原本も 1 行として残す。value は空のまま")
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(COLUMNS))
        w.writeheader()
        w.writerow(example.as_dict())
    print(json.dumps({"ok": True, "wrote": str(p), "columns": list(COLUMNS)}, ensure_ascii=False))
    return 0


def main(argv: "list | None" = None) -> int:
    p = argparse.ArgumentParser(description="原本から取った値 1 件を ピン 1 行 で持ち、毎回突き合わせる")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, help_text, fn in (("verify", "全ピンを原本に突き合わせる", _cli_verify),
                                ("map", "原本の種類 × 取り出し方の対応表を出す", _cli_map)):
        s = sub.add_parser(name, help=help_text)
        s.add_argument("pins")
        s.add_argument("--root", help="source_file の基準ディレクトリ(既定 = ピンの表の場所)")
        s.set_defaults(func=fn)
    g = sub.add_parser("get", help="検査を通った行だけ返す")
    g.add_argument("pins")
    g.add_argument("key")
    g.add_argument("--root")
    g.set_defaults(func=_cli_get)
    i = sub.add_parser("init", help="ピンの表の見出しを書き出す")
    i.add_argument("path")
    i.set_defaults(func=_cli_init)
    args = p.parse_args(argv)
    try:
        return args.func(args)
    except TableError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except OSError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
