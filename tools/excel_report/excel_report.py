"""excel_report — 差異一覧を色分け Excel で人に返す部品。色は値ではないので、理由の列を先に置いてから塗る。

差異を色だけで示した Excel は、値だけを読む下流の工程(CSV 化・別のブックへ書き写す・値の貼り付け)で
意味が落ちる。この部品は判定結果を「理由コード」という値として表に持ち、色はその列から決定論で決まる
従属表示として静的に焼く。順は次のとおりで、判断は 1 つも入れない。

  1. 呼ぶ側から 3 つを受け取る = 値の表 / セルごとの理由コード / 理由コードの表(コード・意味・塗り)
  2. 理由コードの表に無いコード、値の表に無い行・列が来たら止まる(勝手に色を決めない)
  3. 明細シートに値をそのまま置き、各行の隣に理由コードの列を併置する
  4. 塗りは「理由コード → 塗り」の対応表 1 か所から引き、セルに静的に焼く(条件付き書式・数式は使わない)
  5. 凡例シートに「理由コード / 意味 / 塗りの hex / 見本」を書き、判断待ちシートに 1 セル 1 行で座標を書く
  6. 書いたら読み戻して「セル座標 → 理由コード」・件数・理由ごとの件数・塗りを突き合わせる
  7. 1 つでも合わなければ出力ファイルを消し、差の一覧(シート名・セル座標・何の差・入力・読み戻し)を返して止める
  8. 色から理由を逆算する経路は作らない。差の原因は推定しない

依存は openpyxl だけ(この環境は 3.1.5)。読み戻しの一部は stdlib の zipfile でも見る
(同じ道具で同じ道具を確かめる形を避けるため)。
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

SHEET_DETAIL = "明細"
SHEET_LEGEND = "凡例"
SHEET_PENDING = "判断待ち"
REASON_COLUMN = "理由コード"          # 値の隣に併置する列の見出し
JOIN = " "                            # 1 行に理由が 2 つ以上あるときの区切り
HEADER_ROW = 1
FIRST_DATA_ROW = 2
LEGEND_FIELDS = ("理由コード", "意味", "塗り", "見本")
PENDING_FIELDS = ("シート", "セル座標", "行番号", "列名", "値", "理由コード")
REASON_FIELDS = ("理由コード", "意味", "塗り")
HEX = re.compile(r"\A[0-9A-F]{6}\Z")
NO_FILL = (None, "00000000")          # openpyxl が「塗りなし」を返す形


class SpecError(Exception):
    """呼ぶ側から渡されたものが噛み合っていない(表に無いコード、表に無い行・列、壊れた対応表)。"""


# ---- 呼ぶ側から受け取る 3 つ ------------------------------------------------------------------

@dataclass(frozen=True)
class Reason:
    """理由コード 1 行。塗りは RRGGBB の 6 桁(大文字)。意味の 1 行説明を空にできない。"""
    code: str
    meaning: str
    fill: str

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise SpecError("理由コードが空")
        if not self.meaning.strip():
            raise SpecError(f"意味の 1 行説明が空: {self.code}(凡例に書けない)")
        if not HEX.match(self.fill):
            raise SpecError(f"塗りが RRGGBB の 6 桁(大文字)でない: {self.code} = {self.fill}")


@dataclass(frozen=True)
class ReasonTable:
    """理由コードの表。色はここから 1 方向に引くだけで、逆に引く経路は作らない。"""
    reasons: tuple[Reason, ...]

    def __post_init__(self) -> None:
        if not self.reasons:
            raise SpecError("理由コードの表が空")
        codes = [r.code for r in self.reasons]
        if len(set(codes)) != len(codes):
            raise SpecError("理由コードの表に同じコードが 2 つある")

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(r.code for r in self.reasons)

    def fill_of(self, code: str) -> str:
        """理由コード → 塗り。表に無いコードは止まる(近い色を選ぶような判断はしない)。"""
        for r in self.reasons:
            if r.code == code:
                return r.fill
        raise SpecError(f"理由コードの表に無いコード: {code}")

    def meaning_of(self, code: str) -> str:
        for r in self.reasons:
            if r.code == code:
                return r.meaning
        raise SpecError(f"理由コードの表に無いコード: {code}")

    @classmethod
    def from_rows(cls, rows: Iterable[dict[str, str]]) -> "ReasonTable":
        out = []
        for i, r in enumerate(rows, 1):
            try:
                out.append(Reason((r["理由コード"] or "").strip(), (r["意味"] or "").strip(),
                                  (r["塗り"] or "").strip().upper()))
            except KeyError as e:
                raise SpecError(f"理由コードの表 {i} 行目に {e} の欄が無い") from e
        return cls(tuple(out))

    @classmethod
    def from_csv(cls, path: str | os.PathLike[str]) -> "ReasonTable":
        with open(path, encoding="utf-8-sig", newline="") as f:
            return cls.from_rows(list(csv.DictReader(f)))


@dataclass(frozen=True)
class Judgment:
    """上流の部品が返した「このセルは機械では決まらない」1 件。行番号は 1 始まり(見出し行は数えない)。"""
    row: int
    column: str
    code: str


@dataclass(frozen=True)
class Table:
    """値の表。見出しの順がそのまま出力の列の順になる。値は文字列のまま扱う(型を推測しない)。"""
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]

    def __post_init__(self) -> None:
        if not self.columns:
            raise SpecError("値の表に列が無い")
        if len(set(self.columns)) != len(self.columns):
            raise SpecError("値の表に同じ見出しが 2 つある")
        if REASON_COLUMN in self.columns:
            raise SpecError(f"値の表に {REASON_COLUMN} という列がある(この部品が併置する列と衝突する)")
        for i, r in enumerate(self.rows, 1):
            if len(r) != len(self.columns):
                raise SpecError(f"{i} 行目の列数が見出しと違う: {len(r)} != {len(self.columns)}")

    def index_of(self, column: str) -> int:
        try:
            return self.columns.index(column)
        except ValueError:
            raise SpecError(f"値の表に無い列: {column}") from None

    def value_at(self, row: int, column: str) -> str:
        return self.rows[row - 1][self.index_of(column)]

    @classmethod
    def from_rows(cls, columns: Sequence[str], rows: Iterable[dict[str, str]]) -> "Table":
        cols = tuple(columns)
        return cls(cols, tuple(tuple("" if r.get(c) is None else str(r[c]) for c in cols) for r in rows))

    @classmethod
    def from_csv(cls, path: str | os.PathLike[str]) -> "Table":
        with open(path, encoding="utf-8-sig", newline="") as f:
            rd = csv.DictReader(f)
            cols = tuple(rd.fieldnames or ())
            return cls.from_rows(cols, list(rd))


# ---- 出力と突合の結果 -------------------------------------------------------------------------

@dataclass(frozen=True)
class Diff:
    """入力の判定と読み戻しの差。cell が空の差は、件数のように 1 セルに紐づかないもの。"""
    sheet: str
    cell: str
    what: str
    original: str
    readback: str


@dataclass(frozen=True)
class Result:
    path: str
    written: bool
    rows: int = 0
    pending: int = 0
    by_reason: dict[str, int] = field(default_factory=dict)
    diffs: tuple[Diff, ...] = ()

    @property
    def ok(self) -> bool:
        return self.written and not self.diffs


# ---- 置き場所を決める(色より先に、値としての理由の列を作る) --------------------------------

def check_judgments(table: Table, reasons: ReasonTable, judgments: Sequence[Judgment]) -> None:
    """表に無いコード・行・列、同じセルの二重判定を止める。ここを通ってから初めて色の話になる。"""
    seen: set[tuple[int, str]] = set()
    for j in judgments:
        if not 1 <= j.row <= len(table.rows):
            raise SpecError(f"値の表に無い行: {j.row}(1〜{len(table.rows)})")
        table.index_of(j.column)
        reasons.fill_of(j.code)
        if (j.row, j.column) in seen:
            raise SpecError(f"同じセルに理由が 2 つある: {j.row} 行 {j.column}(どちらを塗るかは機械では決まらない)")
        seen.add((j.row, j.column))


def reason_column_values(table: Table, judgments: Sequence[Judgment]) -> list[str]:
    """各行の理由コード列の中身。列の順で並べ、同じコードは 1 回だけ書く。"""
    out = []
    for i in range(1, len(table.rows) + 1):
        here = [j for j in judgments if j.row == i]
        here.sort(key=lambda j: table.index_of(j.column))
        codes: list[str] = []
        for j in here:
            if j.code not in codes:
                codes.append(j.code)
        out.append(JOIN.join(codes))
    return out


def cell_of(table: Table, row: int, column: str) -> str:
    """明細シートのセル座標。見出し行があるので行番号は 1 つ増える。"""
    return f"{get_column_letter(table.index_of(column) + 1)}{row + HEADER_ROW}"


def expected_reason_map(table: Table, judgments: Sequence[Judgment]) -> dict[str, str]:
    """入力の判定から作る「セル座標 → 理由コード」。突合はこれと読み戻しを比べる。"""
    return {cell_of(table, j.row, j.column): j.code for j in judgments}


def counts_by_reason(reasons: ReasonTable, judgments: Sequence[Judgment]) -> dict[str, int]:
    """理由コードごとの件数。表の順で、0 件のコードも 0 として並べる。"""
    got = {c: 0 for c in reasons.codes}
    for j in judgments:
        got[j.code] += 1
    return got


# ---- 書く(静的に焼く。開いた時に評価される形にはしない) ------------------------------------

def _solid(fill: str) -> PatternFill:
    return PatternFill(start_color=f"FF{fill}", end_color=f"FF{fill}", fill_type="solid")


def _write_detail(ws, table: Table, reasons: ReasonTable, judgments: Sequence[Judgment]) -> None:
    ws.append(list(table.columns) + [REASON_COLUMN])
    for c in range(1, len(table.columns) + 2):
        ws.cell(HEADER_ROW, c).font = Font(bold=True)
    col_values = reason_column_values(table, judgments)
    for i, row in enumerate(table.rows, 1):
        ws.append(list(row) + [col_values[i - 1]])
    for j in judgments:
        ws[cell_of(table, j.row, j.column)].fill = _solid(reasons.fill_of(j.code))
    ws.freeze_panes = f"A{FIRST_DATA_ROW}"


def _write_legend(ws, reasons: ReasonTable) -> None:
    ws.append(list(LEGEND_FIELDS))
    for c in range(1, len(LEGEND_FIELDS) + 1):
        ws.cell(HEADER_ROW, c).font = Font(bold=True)
    for i, r in enumerate(reasons.reasons, FIRST_DATA_ROW):
        ws.append([r.code, r.meaning, r.fill, ""])
        ws.cell(i, len(LEGEND_FIELDS)).fill = _solid(r.fill)
    ws.column_dimensions["B"].width = 60


def _write_pending(ws, table: Table, judgments: Sequence[Judgment]) -> None:
    ws.append(list(PENDING_FIELDS))
    for c in range(1, len(PENDING_FIELDS) + 1):
        ws.cell(HEADER_ROW, c).font = Font(bold=True)
    for j in sorted(judgments, key=lambda j: (j.row, table.index_of(j.column))):
        ws.append([SHEET_DETAIL, cell_of(table, j.row, j.column), j.row, j.column,
                   table.value_at(j.row, j.column), j.code])


def _build(path: str | os.PathLike[str], table: Table, reasons: ReasonTable,
           judgments: Sequence[Judgment]) -> None:
    wb = Workbook()
    _write_detail(wb.active, table, reasons, judgments)
    wb.active.title = SHEET_DETAIL
    _write_legend(wb.create_sheet(SHEET_LEGEND), reasons)
    _write_pending(wb.create_sheet(SHEET_PENDING), table, judgments)
    wb.save(path)


# ---- 読み戻す(値として読む。色から理由は引かない) ------------------------------------------

def read_values(path: str | os.PathLike[str], sheet: str = SHEET_DETAIL) -> list[list[str]]:
    """値だけを読む。CSV 化・別のブックへの書き写し・値の貼り付けが見ているのはここだけ。"""
    wb = load_workbook(path, data_only=True)
    if sheet not in wb.sheetnames:
        raise SpecError(f"シートが無い: {sheet}")
    return [["" if c is None else str(c) for c in row] for row in wb[sheet].iter_rows(values_only=True)]


def recover_reasons(path: str | os.PathLike[str]) -> dict[str, str]:
    """出力から「セル座標 → 理由コード」を復元する。読むのは文字だけで、塗りは見ない。"""
    wb = load_workbook(path, data_only=True)
    if SHEET_PENDING not in wb.sheetnames:
        return {}
    got: dict[str, str] = {}
    head: list[str] | None = None
    for row in wb[SHEET_PENDING].iter_rows(values_only=True):
        if head is None:
            head = [str(c) for c in row]
            continue
        r = dict(zip(head, ["" if c is None else str(c) for c in row]))
        got[r["セル座標"]] = r["理由コード"]
    return got


def read_fills(path: str | os.PathLike[str], sheet: str = SHEET_DETAIL) -> dict[str, str]:
    """塗りが実際に焼かれているセルを読む。突合のためだけに読み、ここから理由は引かない。"""
    wb = load_workbook(path)
    got: dict[str, str] = {}
    for row in wb[sheet].iter_rows():
        for c in row:
            rgb = getattr(c.fill.start_color, "rgb", None)
            if c.fill.fill_type == "solid" and rgb not in NO_FILL:
                got[c.coordinate] = str(rgb)[-6:]
    return got


def read_legend(path: str | os.PathLike[str]) -> list[tuple[str, str, str]]:
    """凡例シートの (理由コード, 意味, 塗りの hex)。色ではなく文字として読む。"""
    wb = load_workbook(path, data_only=True)
    if SHEET_LEGEND not in wb.sheetnames:
        return []
    out = []
    for i, row in enumerate(wb[SHEET_LEGEND].iter_rows(values_only=True)):
        if i:
            out.append((str(row[0]), str(row[1]), str(row[2])))
    return out


CHARREF = re.compile(rb"&#(\d+);")


def _plain(raw: bytes) -> str:
    """xlsx の中の XML は日本語を &#12471; の形の文字参照で書くので、文字に戻してから探す。"""
    return CHARREF.sub(lambda m: chr(int(m.group(1))).encode("utf-8"), raw).decode("utf-8", "replace")


def where_it_lives(path: str | os.PathLike[str], needle: str) -> list[str]:
    """xlsx を zip として開き、その文字列を含む部品の名前を返す(openpyxl を通さずに見る)。"""
    with zipfile.ZipFile(path) as z:
        return [n for n in sorted(z.namelist()) if needle in _plain(z.read(n))]


def verify(path: str | os.PathLike[str], table: Table, reasons: ReasonTable,
           judgments: Sequence[Judgment]) -> list[Diff]:
    """出力を読み戻して、値・理由コードの列・座標 → 理由・件数・塗り・凡例を入力の判定と突き合わせる。"""
    diffs: list[Diff] = []
    values = read_values(path)
    want_head = list(table.columns) + [REASON_COLUMN]
    if not values or values[0] != want_head:
        diffs.append(Diff(SHEET_DETAIL, "", "見出し", ",".join(want_head),
                          ",".join(values[0]) if values else ""))
        return diffs
    body, col_values = values[1:], reason_column_values(table, judgments)
    if len(body) != len(table.rows):
        diffs.append(Diff(SHEET_DETAIL, "", "件数", str(len(table.rows)), str(len(body))))
    for i, (want, have) in enumerate(zip(table.rows, body), 1):
        for k, (a, b) in enumerate(zip(list(want) + [col_values[i - 1]], have)):
            if a != b:
                diffs.append(Diff(SHEET_DETAIL, f"{get_column_letter(k + 1)}{i + HEADER_ROW}",
                                  "値" if k < len(table.columns) else REASON_COLUMN, a, b))
    want_map = expected_reason_map(table, judgments)
    have_map = recover_reasons(path)
    for cell in sorted(set(want_map) | set(have_map)):
        if want_map.get(cell, "") != have_map.get(cell, ""):
            diffs.append(Diff(SHEET_PENDING, cell, "座標 → 理由コード",
                              want_map.get(cell, "なし"), have_map.get(cell, "なし")))
    if len(have_map) != len(want_map):
        diffs.append(Diff(SHEET_PENDING, "", "判断待ちの件数", str(len(want_map)), str(len(have_map))))
    unknown = sorted(set(have_map.values()) - set(reasons.codes))
    if unknown:
        diffs.append(Diff(SHEET_PENDING, "", "理由コードの表に無いコード", "", JOIN.join(unknown)))
    else:
        want_counts = counts_by_reason(reasons, judgments)
        have_counts = counts_by_reason(reasons, [Judgment(0, "", c) for c in have_map.values()])
        for code, n in want_counts.items():
            if have_counts[code] != n:
                diffs.append(Diff(SHEET_PENDING, "", f"{code} の件数", str(n), str(have_counts[code])))
    want_fills = {cell: reasons.fill_of(code) for cell, code in want_map.items()}
    have_fills = read_fills(path)
    for cell in sorted(set(want_fills) | set(have_fills)):
        if want_fills.get(cell, "") != have_fills.get(cell, ""):
            diffs.append(Diff(SHEET_DETAIL, cell, "塗り", want_fills.get(cell, "なし"),
                              have_fills.get(cell, "なし")))
    want_legend = [(r.code, r.meaning, r.fill) for r in reasons.reasons]
    have_legend = read_legend(path)
    if have_legend != want_legend:
        diffs.append(Diff(SHEET_LEGEND, "", "凡例の行数", str(len(want_legend)), str(len(have_legend))))
    return diffs


# ---- 書いて突き合わせて渡す ------------------------------------------------------------------

def write(path: str | os.PathLike[str], table: Table, reasons: ReasonTable,
          judgments: Sequence[Judgment]) -> Result:
    """作業ファイルに書く → 読み戻して突き合わせる → 通ったものだけ本来の名前にする。

    差が 1 つでもあれば作業ファイルを消す。人に渡るファイルは作られない。
    """
    dest = Path(path)
    check_judgments(table, reasons, judgments)
    tmp = dest.with_name(dest.name + ".tmp.xlsx")   # openpyxl は拡張子で読み書きを断るので .xlsx を残す
    _build(tmp, table, reasons, judgments)
    diffs = verify(tmp, table, reasons, judgments)
    if diffs:
        tmp.unlink()
        return Result(str(dest), False, diffs=tuple(diffs))
    os.replace(tmp, dest)
    return Result(str(dest), True, len(table.rows), len(judgments),
                  counts_by_reason(reasons, judgments))


def naive_write(path: str | os.PathLike[str], table: Table, reasons: ReasonTable,
                judgments: Sequence[Judgment]) -> int:
    """比較用。差異を色だけで示す書き出し(理由コードの列・凡例・判断待ちシートを持たない)。

    人が開けば色は見えるので、書いた側では足りているように見える。
    """
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_DETAIL
    ws.append(list(table.columns))
    for row in table.rows:
        ws.append(list(row))
    for j in judgments:
        ws[cell_of(table, j.row, j.column)].fill = _solid(reasons.fill_of(j.code))
    wb.save(path)
    return len(judgments)


def _write_detail_without_fill(ws, table: Table, judgments: Sequence[Judgment]) -> None:
    ws.append(list(table.columns) + [REASON_COLUMN])
    col_values = reason_column_values(table, judgments)
    for i, row in enumerate(table.rows, 1):
        ws.append(list(row) + [col_values[i - 1]])


def conditional_write(path: str | os.PathLike[str], table: Table, reasons: ReasonTable,
                      judgments: Sequence[Judgment]) -> int:
    """比較用。塗りを条件付き書式で指定する書き出し(開いた時に Excel が評価する形)。

    理由コードの列は置くが、塗りはファイルの中で確定していない。
    """
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_DETAIL
    _write_detail_without_fill(ws, table, judgments)
    last = get_column_letter(len(table.columns) + 1)
    span = f"A{FIRST_DATA_ROW}:{last}{len(table.rows) + HEADER_ROW}"
    for r in reasons.reasons:
        rule = FormulaRule(formula=[f'ISNUMBER(SEARCH("{r.code}",${last}{FIRST_DATA_ROW}))'],
                           fill=_solid(r.fill))
        ws.conditional_formatting.add(span, rule)
    wb.save(path)
    return len(reasons.reasons)


# ---- CLI --------------------------------------------------------------------------------------

def _judgments_from_csv(path: str | os.PathLike[str]) -> list[Judgment]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        out = []
        for i, r in enumerate(csv.DictReader(f), 1):
            try:
                out.append(Judgment(int((r["行番号"] or "").strip()), (r["列名"] or "").strip(),
                                    (r["理由コード"] or "").strip()))
            except KeyError as e:
                raise SpecError(f"判定の表 {i} 行目に {e} の欄が無い") from e
            except ValueError as e:
                raise SpecError(f"判定の表 {i} 行目の行番号が数でない: {e}") from e
        return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="excel_report",
                                 description="差異一覧を色分け Excel で人に返す(理由の列を先に置いてから塗る)")
    ap.add_argument("values", help="値の表(UTF-8 の CSV)")
    ap.add_argument("dest", nargs="?", help="出力先(.xlsx)。--check のときは不要")
    ap.add_argument("--judgments", required=True, help="セルごとの判定(行番号,列名,理由コード)")
    ap.add_argument("--reasons", required=True, help="理由コードの表(理由コード,意味,塗り)")
    ap.add_argument("--check", action="store_true", help="受け取ったものが噛み合うかだけ見て書かない")
    ap.add_argument("--naive", action="store_true", help="比較用: 色だけで示す(理由の列も凡例も持たない)")
    a = ap.parse_args(argv)
    try:
        table = Table.from_csv(a.values)
        reasons = ReasonTable.from_csv(a.reasons)
        judgments = _judgments_from_csv(a.judgments)
        if a.check:
            check_judgments(table, reasons, judgments)
            for code, n in counts_by_reason(reasons, judgments).items():
                print(f"{code}\t{n}")
            print(f"検査 {len(table.rows)} 行 / 判断待ち {len(judgments)} 件", file=sys.stderr)
            return 0
        if not a.dest:
            ap.error("出力先が要る(受け取ったものを見るだけなら --check)")
        if a.naive:
            n = naive_write(a.dest, table, reasons, judgments)
            print(f"色だけで書いた {n} セル(理由の列・凡例・判断待ちシートなし)", file=sys.stderr)
            return 0
        r = write(a.dest, table, reasons, judgments)
    except SpecError as e:
        print(f"受け取ったもの: {e}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as e:
        print(f"読み書き: {e}", file=sys.stderr)
        return 2
    for d in r.diffs:
        print(f"{d.sheet}\t{d.cell or '-'}\t{d.what}\t{d.original}\t{d.readback}")
    if r.ok:
        t = " / ".join(f"{k} {v}" for k, v in r.by_reason.items() if v)
        print(f"書いて読み戻して一致: {r.rows} 行 / 判断待ち {r.pending} 件" + (f" / {t}" if t else ""),
              file=sys.stderr)
        return 0
    print(f"書かなかった: 突合の差 {len(r.diffs)} 件", file=sys.stderr)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
