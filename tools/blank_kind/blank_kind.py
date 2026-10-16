"""blank_kind — 空欄の意味を列ごとの宣言から決め、宣言が無い空欄では止まる。

**同じ空欄が、列によって「全部に当たる」とも「まだ取っていない」とも「制度として該当なし」
とも読める。どれかを書いていないと、空欄は黙って 0 か現行値になる。** この部品は、空欄の
意味を値の表の理由コードと列の宣言からだけ取り、マスごとに 4 値に分ける。欠けている件数は
理由コード別に数え、分母(対象 × 項目の総数)と内訳を併記して返す。

持たせていないものが規律になっている。

  - **空欄に理由コードが無ければ止まる**(空欄の既定の意味を持たない)
  - **同じ空欄記号を列ごとに別の意味で読む**(「全部に当たる」列の空欄と、値の列の空欄を
    同じ経路に流さない。列の宣言が無ければ止まる)
  - **0 と空欄をどちらにも寄せない**(0 が正規の値になりうる項目で空欄を 0 にしない、
    0 を空欄として落とさない)
  - **仮置きの値を黙って値として返さない**(理由コードの付いた行は、値を持っていても
    仮置きの欄で返す。仮置きを外す提案もしない)
  - **空欄を前の行・前の期間・前の版の値で埋めない**(引き継ぎの引数が無い)
  - **欠けている件数を理由コード別に数え、分母と内訳を必ず併記する**(率を単独で返さない)
  - **「値が在る」と「空欄」と「止まった」を混ぜない**
  - **入力表を書き換えず、値も理由コードも生成しない**
  - **出典の欄が空の行・宣言は使わずに止まる**
  - **float を使わない**(値は Decimal、件数は整数)
  - **空欄の理由を推定して埋めない、足すべき理由コードも提案しない**
  - **形容の語を出力に持たない**(返すのは件数と分母と内訳だけ)
  - **日付で表の版を選ばない / 期間を切らない / 値を帯に当てない**(役割を重ねない)

入力は 3 つ。値の表(CSV)、項目の宣言(CSV)、理由コードの宣言(CSV)。

値の表の列は 6 つ。

    target      対象(空欄は「表として読めない」)
    item        項目。項目の宣言に無い項目は止まる
    value       値(Decimal。空欄なら理由コードが要る)
    reason      空欄の理由コード。空欄で値も空なら止まる
    source      出典。空欄は止まる
    swap        入れ替え方(verify が値の表の行順を入れ替えるときの宣言。全行で同じ値)

項目の宣言の列は 6 つ。

    item        項目(2 行書くと「表として読めない」)
    kind        値の種類。登録の 6 種。空欄は止まる
    reasons     空欄に許す理由コードの一覧(縦棒で区切る。空欄 = 空欄を 1 つも許さない)
    zero_ok     0 が正規の値になりうるか(はい / いいえ)。空欄は止まる
    all_match   空欄が「全部に当たる」を意味する列か(はい / いいえ)。空欄は止まる
    source      出典。空欄は止まる

理由コードの宣言の列は 4 つ。

    code        コード(2 行書くと「表として読めない」)
    meaning     意味
    how         引いたときの返し方。登録の 3 種
    source      出典。空欄は止まる

使い方:

    python blank_kind.py init ひな型/
    python blank_kind.py check  値の表.csv 項目の宣言.csv 理由コードの宣言.csv
    python blank_kind.py read   値の表.csv 項目の宣言.csv 理由コードの宣言.csv
    python blank_kind.py verify 値の表.csv 項目の宣言.csv 理由コードの宣言.csv
"""
from __future__ import annotations

import argparse
import csv
import datetime
import decimal
import hashlib
import json
import platform
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

ATAI_COLUMNS = ("target", "item", "value", "reason", "source", "swap")
KOUMOKU_COLUMNS = ("item", "kind", "reasons", "zero_ok", "all_match", "source")
RIYUU_COLUMNS = ("code", "meaning", "how", "source")

# 登録の語彙。ここに無い語は「表として読めない」で返す(理由コードには混ぜない)
KINDS = ("金額", "日数", "月数", "年数", "時間", "人数")
HOWS = ("値として返さない", "全部に当たるとして扱う", "該当なしとして返す")
HAI = "はい"
IIE = "いいえ"
YESNO = (HAI, IIE)
SWAPS = ("逆順", "両端入れ替え", "1 つずらす")
REASON_SEP = "|"

# マスごとの 4 値。「空欄」と「決まらない」と「止まった」を混ぜない
RESULTS = ("値が在る", "空欄(宣言された意味つき)", "決まらない", "止まった")

# 止まる理由コード(11 個)
STOP_REASONS = ("理由コードが空", "宣言に無いコード", "項目が宣言に無い",
                "同じ列に 2 つの意味", "0 の扱いが未宣言", "列の種類が未宣言",
                "出典の欄が空", "値の種類が空", "件数の合計が合わない",
                "2 回目の判定部分が不一致", "行順を入れ替えた表で出力が変わる")

# CLI の下位コマンド。この 4 つだけで、option は -h 以外に 1 つも無い
SUBCOMMANDS = ("read", "check", "verify", "init")

# 判定部分に入れない欄(sha256 の対象にもしない)
READ_KEYS = ("読んだ値の表の絶対パス", "読んだ項目の宣言の絶対パス",
             "読んだ理由コードの宣言の絶対パス", "読んだ時刻", "ホスト名")


class ReadError(Exception):
    """表として読めない(理由コードにせず終了コード 2 で返す = 表を書く側の話)。"""


def as_decimal(text: str, where: str) -> Decimal:
    """Decimal としてだけ読む(float は使わない。指数表記も受けない)。"""
    try:
        v = Decimal(text)
    except decimal.InvalidOperation:
        raise ReadError(f"{where}: 数として読めない({text})") from None
    if not v.is_finite() or "E" in text.upper():
        raise ReadError(f"{where}: 数として読めない({text})")
    return v


def as_yesno(text: str, where: str) -> bool | None:
    """はい / いいえ だけを読む。空欄は None(= 宣言していない)。"""
    if not text:
        return None
    if text not in YESNO:
        raise ReadError(f"{where}: {HAI} か {IIE} で書く({text})")
    return text == HAI


@dataclass(frozen=True)
class Pending:
    reason: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"reason": self.reason, "detail": self.detail}


# ------------------------------------------------------------ 理由コードの宣言

@dataclass(frozen=True)
class Reason:
    code: str
    meaning: str
    how: str
    source: str
    number: int


@dataclass(frozen=True)
class Reasons:
    items: tuple[Reason, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Reasons":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"理由コードの宣言が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Reasons":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in RIYUU_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("理由コードの宣言に " + " / ".join(lack) + " の列が無い")
        items: list[Reason] = []
        pending: list[Pending] = []
        seen: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in RIYUU_COLUMNS}
            where = f"理由コードの宣言 行 {i}"
            if not cell["code"]:
                raise ReadError(f"{where}: コードが空欄")
            if cell["code"] in seen:
                raise ReadError(f"{where}: コード {cell['code']} の宣言が 2 行ある")
            seen.add(cell["code"])
            if not cell["meaning"]:
                raise ReadError(f"{where}: 意味が空欄({cell['code']})")
            if cell["how"] not in HOWS:
                raise ReadError(f"{where}: 返し方は {' / '.join(HOWS)}({cell['how']})")
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[6], f"{where}({cell['code']})"))
            items.append(Reason(code=cell["code"], meaning=cell["meaning"],
                                how=cell["how"], source=cell["source"], number=i))
        if not items:
            raise ReadError("理由コードの宣言に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    def of(self, code: str) -> Reason | None:
        return next((r for r in self.items if r.code == code), None)


# ------------------------------------------------------------ 項目の宣言

@dataclass(frozen=True)
class Column:
    item: str
    kind: str
    allowed: tuple[str, ...]
    zero_ok: bool | None
    all_match: bool | None
    source: str
    number: int


@dataclass(frozen=True)
class Columns:
    items: tuple[Column, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Columns":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"項目の宣言が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Columns":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in KOUMOKU_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("項目の宣言に " + " / ".join(lack) + " の列が無い")
        items: list[Column] = []
        pending: list[Pending] = []
        seen: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in KOUMOKU_COLUMNS}
            where = f"項目の宣言 行 {i}"
            if not cell["item"]:
                raise ReadError(f"{where}: 項目が空欄")
            if cell["item"] in seen:
                raise ReadError(f"{where}: 項目 {cell['item']} の宣言が 2 行ある")
            seen.add(cell["item"])
            if cell["kind"] and cell["kind"] not in KINDS:
                raise ReadError(f"{where}: 値の種類は {' / '.join(KINDS)}({cell['kind']})")
            allowed = tuple(c.strip() for c in cell["reasons"].split(REASON_SEP)
                            if c.strip())
            if len(set(allowed)) != len(allowed):
                raise ReadError(f"{where}: 許す理由コードの一覧に同じコードが 2 つある")
            where_item = f"{where}({cell['item']})"
            if not cell["kind"]:
                pending.append(Pending(STOP_REASONS[7], where_item))
            zero_ok = as_yesno(cell["zero_ok"], f"{where} の 0 の扱い")
            if zero_ok is None:
                pending.append(Pending(STOP_REASONS[4], where_item))
            all_match = as_yesno(cell["all_match"], f"{where} の列の種類")
            if all_match is None:
                pending.append(Pending(STOP_REASONS[5], where_item))
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[6], where_item))
            items.append(Column(item=cell["item"], kind=cell["kind"], allowed=allowed,
                                zero_ok=zero_ok, all_match=all_match,
                                source=cell["source"], number=i))
        if not items:
            raise ReadError("項目の宣言に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    def of(self, item: str) -> Column | None:
        return next((c for c in self.items if c.item == item), None)


def declaration_conflicts(columns: Columns, reasons: Reasons) -> list[Pending]:
    """列の種類と、その列が許す理由コードの返し方が食い違っていないか。

    「全部に当たる」列の空欄は 1 つの意味しか持てない。その列が 値として返さない や
    該当なしとして返す のコードも許していると、同じ空欄記号に 2 つの意味が宣言される。
    """
    out: list[Pending] = []
    for c in columns.items:
        if c.all_match is not True:
            continue
        for code in c.allowed:
            r = reasons.of(code)
            if r is not None and r.how != HOWS[1]:
                out.append(Pending(
                    STOP_REASONS[3],
                    f"{c.item}: 全部に当たる列が {code}({r.how})も許している"))
    return out


# ------------------------------------------------------------ 値の表

@dataclass(frozen=True)
class Cell:
    target: str
    item: str
    value: Decimal | None
    reason: str
    source: str
    number: int


@dataclass(frozen=True)
class Sheet:
    items: tuple[Cell, ...]
    swap: str
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Sheet":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"値の表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Sheet":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in ATAI_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("値の表に " + " / ".join(lack) + " の列が無い")
        items: list[Cell] = []
        pending: list[Pending] = []
        swaps: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in ATAI_COLUMNS}
            where = f"値の表 行 {i}"
            if not cell["target"]:
                raise ReadError(f"{where}: 対象が空欄")
            if not cell["item"]:
                raise ReadError(f"{where}: 項目が空欄({cell['target']})")
            if cell["swap"]:
                if cell["swap"] not in SWAPS:
                    raise ReadError(f"{where}: 入れ替え方 {cell['swap']} は登録の外"
                                    f"({' / '.join(SWAPS)})")
                swaps.add(cell["swap"])
            where_cell = f"{where}({cell['target']} / {cell['item']})"
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[6], where_cell))
            if not cell["value"] and not cell["reason"]:
                # 空欄の既定の意味を持たない。ここがこの部品の骨
                pending.append(Pending(STOP_REASONS[0], where_cell))
            items.append(Cell(target=cell["target"], item=cell["item"],
                              value=(as_decimal(cell["value"], f"{where} の値")
                                     if cell["value"] else None),
                              reason=cell["reason"], source=cell["source"], number=i))
        if not items:
            raise ReadError("値の表に行が無い(ヘッダだけ)")
        if len(swaps) > 1:
            raise ReadError("入れ替え方の宣言が 2 通り以上ある: " + " / ".join(sorted(swaps)))
        return cls(items=tuple(items), swap=next(iter(swaps), ""),
                   pending=tuple(pending), path=path)

    @property
    def ordered(self) -> tuple[Cell, ...]:
        """項目・対象の順に並べ替えて返す(表の行順には依らせない)。"""
        return tuple(sorted(self.items, key=lambda c: (c.item, c.target)))

    @property
    def targets(self) -> tuple[str, ...]:
        return tuple(sorted({c.target for c in self.items}))

    def swapped(self, how: str) -> "Sheet":
        """宣言された入れ替え方で値の表の行順だけを入れ替える(乱数の既定は持たない)。"""
        if how not in SWAPS:
            raise ReadError(f"入れ替え方が登録の外: {how}")
        rows = list(self.items)
        if len(rows) >= 2:
            if how == SWAPS[0]:
                rows.reverse()
            elif how == SWAPS[1]:
                rows[0], rows[-1] = rows[-1], rows[0]
            else:
                rows = rows[1:] + rows[:1]
        return Sheet(items=tuple(rows), swap=self.swap, pending=self.pending,
                     path=self.path)


# ------------------------------------------------------------ 覆いの検算

@dataclass(frozen=True)
class Grid:
    """対象 × 項目 のマスが、値の表にちょうど 1 行ずつ在るかの実測。"""
    targets: int
    columns: int
    rows: int
    missing: tuple[tuple[str, str], ...] = ()
    duplicated: tuple[tuple[str, str], ...] = ()

    @property
    def total(self) -> int:
        return self.targets * self.columns

    @property
    def ok(self) -> bool:
        return not self.missing and not self.duplicated and self.rows == self.total

    def as_dict(self) -> dict[str, object]:
        return {"対象の数": self.targets, "項目の数": self.columns,
                "対象 × 項目": self.total, "宣言された項目の行数": self.rows,
                "足りないマス": [list(p) for p in self.missing],
                "2 行あるマス": [list(p) for p in self.duplicated]}


def grid_of(sheet: Sheet, columns: Columns) -> Grid:
    """対象 × 項目 の総数と、値の表に在るマスを突き合わせる(値を 1 つも読む前の検算)。"""
    declared = tuple(c.item for c in columns.items)
    seen: dict[tuple[str, str], int] = {}
    for c in sheet.items:
        if c.item in declared:
            key = (c.target, c.item)
            seen[key] = seen.get(key, 0) + 1
    missing = tuple(sorted((t, i) for t in sheet.targets for i in declared
                           if (t, i) not in seen))
    duplicated = tuple(sorted(k for k, n in seen.items() if n > 1))
    return Grid(targets=len(sheet.targets), columns=len(declared),
                rows=sum(seen.values()), missing=missing, duplicated=duplicated)


# ------------------------------------------------------------ 読む

@dataclass(frozen=True)
class Read:
    """マス 1 つの読み。値も理由コードも生成していない。"""
    cell: Cell
    result: str
    meaning: str = ""            # 空欄のときだけ、宣言から取った意味
    how: str = ""                # 空欄のときだけ、宣言から取った返し方
    provisional: str = ""        # 理由コードの付いた行に値も在ったとき(= 仮置き)
    source: str = ""

    @property
    def coded(self) -> bool:
        return bool(self.cell.reason)


@dataclass(frozen=True)
class Report:
    ok: bool
    pending: tuple[Pending, ...]
    cells: int
    columns: int
    reasons: int


@dataclass(frozen=True)
class Table:
    report: Report
    reads: tuple[Read, ...]
    grid: Grid
    sheet: Sheet
    columns: Columns
    reasons: Reasons
    read_at: str
    host: str

    # -------------------------------------------------- 4 値と分母
    def by_result(self, result: str) -> tuple[Read, ...]:
        return tuple(r for r in self.reads if r.result == result)

    @property
    def verdict(self) -> str:
        """全体の結果。1 マスでも決まらなければ 決まらない。"""
        self._guard()
        if self.by_result(RESULTS[2]):
            return RESULTS[2]
        if self.by_result(RESULTS[1]):
            return RESULTS[1]
        return RESULTS[0]

    def by_reason(self) -> dict[str, int]:
        """理由コード別の件数(コードの宣言の順に並べる。率は返さない)。"""
        out: dict[str, int] = {}
        for r in self.reasons.items:
            n = sum(1 for x in self.reads if x.cell.reason == r.code)
            if n:
                out[r.code] = n
        other = sum(1 for x in self.reads
                    if x.cell.reason and self.reasons.of(x.cell.reason) is None)
        if other:
            out[STOP_REASONS[1]] = other
        return out

    def counts(self) -> dict[str, object]:
        """欠けている件数は率を単独で返さない。分母と内訳を必ず併記する。"""
        four = {r: len(self.by_result(r)) for r in RESULTS}
        per = self.by_reason()
        coded = sum(per.values())
        plain = sum(1 for r in self.reads if not r.coded)
        provisional = sum(1 for r in self.reads if r.provisional)
        out: dict[str, object] = {
            "値の表の行数": self.report.cells,
            "項目の宣言の行数": self.report.columns,
            "理由コードの宣言の行数": self.report.reasons,
            "対象の数": self.grid.targets, "項目の数": self.grid.columns,
            "対象 × 項目": self.grid.total,
            "4 値": four,
            "理由コード別": per,
            "理由コードの付いた行に値も在った件数(仮置き)": provisional,
            "読んだか": ("読んだ" if self.reads else
                         "読んでいない(表が揃う前に止まったので 4 値は全て 0)"),
        }
        out["分母に含めたもの"] = (
            f"対象 {self.grid.targets} × 項目 {self.grid.columns} = {self.grid.total} マス。"
            f"4 値の内訳は 値が在る {four[RESULTS[0]]} + 空欄 {four[RESULTS[1]]}"
            f" + 決まらない {four[RESULTS[2]]} + 止まった {four[RESULTS[3]]}。"
            f"そのうち理由コードの付いた行は {coded} 件で、内訳は理由コード別の欄に出した")
        out["欠けている件数の検算"] = (
            f"理由コード別の件数の合計 {coded} + 理由コードの無い行 {plain}"
            f" = {coded + plain}(対象 × 項目 = {self.grid.total})")
        out["空欄の意味は宣言から取る"] = (
            "空欄の意味は値の表の理由コードと列の宣言からだけ取った。空欄の既定の意味も、"
            "理由を推定して埋める経路も、足すべき理由コードを提案する経路も無い"
            "(関数にも CLI にも引数が無い)")
        out["0 と空欄を寄せない"] = (
            "0 が正規の値になりうる項目で空欄を 0 にせず、0 を空欄として落とさない。"
            "0 が正規の値でない項目に書かれた 0 は 決まらない で返る")
        out["前の値で埋めない"] = (
            "空欄を前の行・前の期間・前の版の値で埋めない(引き継ぎの引数が無い)。"
            "日付で表の版を選ぶ経路も、期間を切る経路も、値を帯に当てる経路も持たない")
        return out

    def table(self) -> list[dict[str, object]]:
        """マスごとの読み。率の欄は無い。"""
        return [{"対象": r.cell.target, "項目": r.cell.item,
                 "値": ("" if r.cell.value is None or r.coded else str(r.cell.value)),
                 "結果": r.result, "理由コード": r.cell.reason, "空欄の意味": r.meaning,
                 "返し方": r.how, "仮置きの値": r.provisional, "出典": r.source}
                for r in self.reads]

    def blanks(self) -> list[dict[str, object]]:
        """理由コードの付いたマスだけを別に並べる(件数の内訳がどのマスから来たか)。"""
        return [{"対象": r.cell.target, "項目": r.cell.item, "理由コード": r.cell.reason,
                 "空欄の意味": r.meaning, "返し方": r.how, "仮置きの値": r.provisional,
                 "結果": r.result}
                for r in self.reads if r.coded]

    # -------------------------------------------------- 判定部分
    def judgement_bytes(self) -> bytes:
        """判定部分 = 読んだ結果の表。時刻・絶対パス・ホスト名・行番号は入れない。"""
        self._guard()
        lines = ["\t".join(["覆い", str(self.grid.targets), str(self.grid.columns),
                            str(self.grid.total), str(self.grid.rows)])]
        for r in self.reads:
            lines.append("\t".join([
                r.cell.item, r.cell.target,
                "" if r.cell.value is None else str(r.cell.value),
                r.cell.reason, r.result, r.meaning, r.how, r.provisional]))
        return ("\n".join(lines) + "\n").encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.judgement_bytes()).hexdigest()

    def read_condition(self) -> dict[str, str]:
        return {READ_KEYS[0]: self.sheet.path, READ_KEYS[1]: self.columns.path,
                READ_KEYS[2]: self.reasons.path, READ_KEYS[3]: self.read_at,
                READ_KEYS[4]: self.host}

    def _guard(self) -> None:
        if not self.report.ok:
            raise RuntimeError("止まっているので読んだ結果は無い。"
                               "report.pending の理由コードを見る")


def read(sheet: Sheet, columns: Columns, reasons: Reasons) -> Table:
    """空欄の意味を宣言から決める。表が揃う前に止まったら 1 マスも読まない。"""
    now = datetime.datetime.now().isoformat(timespec="seconds")
    host = platform.node()
    pending = (list(sheet.pending) + list(columns.pending) + list(reasons.pending)
               + declaration_conflicts(columns, reasons))
    grid = grid_of(sheet, columns)

    def made(pend: tuple[Pending, ...], reads: tuple[Read, ...] = ()) -> Table:
        return Table(report=Report(not pend, pend, len(sheet.items),
                                   len(columns.items), len(reasons.items)),
                     reads=reads, grid=grid, sheet=sheet, columns=columns,
                     reasons=reasons, read_at=now, host=host)

    if pending:                      # 表が揃う前に止まる(1 マスも読まない)
        return made(tuple(pending))

    # 対象 × 項目 のマスが揃っているかを、値を 1 つも読む前に突き合わせる
    if not grid.ok:
        for t, i in grid.missing:
            pending.append(Pending(STOP_REASONS[8], f"足りないマス: {t} / {i}"))
        for t, i in grid.duplicated:
            pending.append(Pending(STOP_REASONS[8], f"2 行あるマス: {t} / {i}"))
        if not grid.missing and not grid.duplicated:
            pending.append(Pending(STOP_REASONS[8],
                                   f"行数 {grid.rows} / 対象 × 項目 {grid.total}"))

    reads: list[Read] = []
    for c in sheet.ordered:
        col = columns.of(c.item)
        if col is None:
            pending.append(Pending(STOP_REASONS[2], f"値の表 行 {c.number}: {c.item}"))
            reads.append(Read(cell=c, result=RESULTS[3]))
            continue
        if not c.reason:
            if c.value is None:                      # 読み込みで既に止めてある
                reads.append(Read(cell=c, result=RESULTS[3]))
            elif c.value == 0 and col.zero_ok is False:
                # 0 が正規の値でない項目の 0。空欄の代わりなのか値なのか決まらない
                reads.append(Read(cell=c, result=RESULTS[2], source=c.source))
            else:
                reads.append(Read(cell=c, result=RESULTS[0], source=c.source))
            continue
        r = reasons.of(c.reason)
        if r is None or c.reason not in col.allowed:
            detail = (f"値の表 行 {c.number}: {c.reason} は"
                      + ("コードの宣言に無い" if r is None
                         else f"{c.item} の許す一覧に無い"))
            pending.append(Pending(STOP_REASONS[1], detail))
            reads.append(Read(cell=c, result=RESULTS[3]))
            continue
        # 同じ空欄記号を列ごとに別の意味で読む。列の種類と返し方が食い違えば決まらない。
        # 決まらないマスは、2 つの読みのどちらも返さない(意味も返し方も空のまま返る)
        fits = (r.how == HOWS[1]) == bool(col.all_match)
        if not fits:
            reads.append(Read(cell=c, result=RESULTS[2]))
            continue
        reads.append(Read(cell=c, result=RESULTS[1], meaning=r.meaning, how=r.how,
                          provisional="" if c.value is None else str(c.value),
                          source=r.source))
    return made(tuple(pending), tuple(reads))


def verify(sheet: Sheet, columns: Columns, reasons: Reasons) -> dict[str, object]:
    """2 回読んで sha256 を比べ、値の表の行順を入れ替えても同じかを見て、件数を検算する。"""
    first = read(sheet, columns, reasons)
    if not first.report.ok:
        return {"ok": False, "stage": "止まった(読んだ結果は返さない)", **first.counts(),
                "pending": [p.as_dict() for p in first.report.pending]}
    if not sheet.swap:
        raise ReadError("値の表に入れ替え方(swap)が無いので verify は走らせない")
    second = read(sheet, columns, reasons)
    third = read(sheet.swapped(sheet.swap), columns, reasons)
    pending: list[Pending] = []
    if first.sha256() != second.sha256():
        pending.append(Pending(STOP_REASONS[9], f"2 回目 {second.sha256()[:12]}"))
    if not (third.report.ok and first.sha256() == third.sha256()):
        pending.append(Pending(STOP_REASONS[10],
                               f"入れ替え方 {sheet.swap} の表で {third.sha256()[:12]}"
                               if third.report.ok else
                               f"入れ替え方 {sheet.swap} の表では止まった"))
    per = first.by_reason()
    coded = sum(per.values())
    plain = sum(1 for r in first.reads if not r.coded)
    if coded + plain != first.grid.total:
        pending.append(Pending(STOP_REASONS[8],
                               f"理由コード別の合計 {coded} + 理由コードの無い行 {plain}"
                               f" / 対象 × 項目 {first.grid.total}"))
    out: dict[str, object] = {
        "ok": not pending, "読んだ結果": first.verdict, "読んだ回数": 2,
        "入れ替え方": sheet.swap, "sha256": first.sha256(),
        "2 回目の sha256": second.sha256(),
        "入れ替えた表の sha256": third.sha256() if third.report.ok else "",
        "件数の検算": {"理由コード別の合計": coded, "理由コードの無い行": plain,
                       **first.grid.as_dict()},
    }
    if pending:
        out["観測"] = ("同じ表から違うバイト列が出た(平均も多数決もしない。"
                       "どちらが正しいかも決めない)")
        out["pending"] = [p.as_dict() for p in pending]
    return out


# ------------------------------------------------------------ ひな型

TEMPLATE_SHEET = [
    list(ATAI_COLUMNS),
    ["合成の区分A", "合成の金額の列(架空)", "120000", "", "合成の値メモ(架空)L1", "逆順"],
    ["合成の区分A", "合成の年齢の列(架空)", "", "全部に当たる", "合成の値メモ(架空)L2", ""],
    ["合成の区分B", "合成の金額の列(架空)", "", "値が未取得", "合成の値メモ(架空)L3", ""],
    ["合成の区分B", "合成の年齢の列(架空)", "60", "", "合成の値メモ(架空)L4", ""],
]
TEMPLATE_COLUMNS = [
    list(KOUMOKU_COLUMNS),
    ["合成の金額の列(架空)", "金額", "値が未取得|仮置き", "はい", "いいえ",
     "合成の列メモ(架空)L1"],
    ["合成の年齢の列(架空)", "年数", "全部に当たる", "はい", "はい",
     "合成の列メモ(架空)L2"],
]
TEMPLATE_REASONS = [
    list(RIYUU_COLUMNS),
    ["値が未取得", "行は在るが値をまだ取っていない", "値として返さない",
     "合成のコードメモ(架空)L1"],
    ["仮置き", "確認できた範囲の先頭に仮に置いた", "値として返さない",
     "合成のコードメモ(架空)L2"],
    ["全部に当たる", "絞り込みを指定していない", "全部に当たるとして扱う",
     "合成のコードメモ(架空)L3"],
]


def write_csv(path: Path, rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    return path


def init(dest: str | Path) -> tuple[Path, Path, Path]:
    d = Path(dest)
    return (write_csv(d / "値の表.csv", TEMPLATE_SHEET),
            write_csv(d / "項目の宣言.csv", TEMPLATE_COLUMNS),
            write_csv(d / "理由コードの宣言.csv", TEMPLATE_REASONS))


# ------------------------------------------------------------ CLI

def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def build_parser() -> argparse.ArgumentParser:
    """CLI は read / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = argparse.ArgumentParser(prog="blank_kind", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in SUBCOMMANDS[:3]:
        p = sub.add_parser(name)
        p.add_argument("sheet")
        p.add_argument("columns")
        p.add_argument("reasons")
    sub.add_parser(SUBCOMMANDS[3]).add_argument("dest")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == "init":
        print("書いた: " + " / ".join(str(p) for p in init(a.dest)))
        return 0
    try:
        sheet, columns = Sheet.load(a.sheet), Columns.load(a.columns)
        reasons = Reasons.load(a.reasons)
        if a.cmd == "verify":
            out = verify(sheet, columns, reasons)
            _print(out)
            return 0 if out["ok"] else 3
        t = read(sheet, columns, reasons)
    except ReadError as e:
        print(f"表として読めない: {e}", file=sys.stderr)
        return 2
    if not t.report.ok:
        _print({"ok": False, "stage": "止まった(読んだ結果は返さない)", **t.counts(),
                "pending": [p.as_dict() for p in t.report.pending]})
        return 3
    body: dict[str, object] = {"ok": True, "読んだ結果": t.verdict, **t.counts()}
    if a.cmd == "read":
        body["マスごと"] = t.table()
        body["空欄のマス"] = t.blanks()
        body["sha256"] = t.sha256()
        body["読んだ条件"] = t.read_condition()
    _print(body)
    return 0 if t.verdict == RESULTS[0] else 3


if __name__ == "__main__":
    raise SystemExit(main())
