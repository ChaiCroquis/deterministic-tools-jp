"""order_table — 行の並べ方を宣言表から取り、同じ値の行が残ったら並べずに止める。

**行の並べ方を宣言しないまま並べると、中身が同じでも出力のバイト列が変わる。** 差分も sha256 も
毎回ずれる。この部品は並び順を宣言表からだけ取り、宣言された鍵で行の順が一意に決まるかを見て、
決まらなければ **並べずに止まる**(同値の組の件数・関与した行数・分母の内訳を付けて返す)。

持たせていないものが規律になっている。

  - **宣言表に無い列で並べない**(鍵を自然文や列名から推測して足す経路が無い)
  - **同値の組が残ったら並べない**(安定ソートの結果を返す経路が無い = 入力順に依存した出力を
    黙って渡さない)
  - **行番号・連番・ハッシュを振って一意にしない**(鍵が足りないことを隠す経路が無い。足すべき
    鍵の候補も提案しない)
  - **ロケール依存の照合順を使わない**(文字列はコードポイント列としてだけ比較。NFKC も異体字の
    寄せもしない)
  - **値の種類が宣言されていない列は止まる**(文字列として並べて 10 が 9 の前に来る経路が無い)
  - **欠損の置き場所が宣言されていない列は止まる**(空欄を黙って先頭や末尾に寄せない。空欄を 0 や
    直前の行で埋める経路も無い)
  - **float が混ざったら止まる**(数は整数か Decimal の宣言どおりにだけ比較)
  - **許容誤差・近似一致の引数を持たない**(近い値を同じ値として束ねない)
  - **一意になった率を単独で返さない**(同値の組の件数・関与した行数・分母の内訳を必ず併記)
  - **入力表も宣言表も書き換えず、列を足さない**(直す・補う経路が無い)
  - **出典の欄が空の宣言行は使わずに止まる**(誰の宣言由来かを辿れない鍵で並べない)

入力は 2 つ。データ表(CSV)と並び順の宣言表(CSV)。宣言表の列は 8 つ。

    rank        順位。鍵の行はここに整数を書く(空欄の行は列挙の候補の並びを書く行)
    column      列名。データ表のヘッダに無ければ止まる
    direction   向き(昇順 / 降順)
    kind        値の種類(コードポイント列 / 整数 / Decimal / 日付 / 宣言された列挙)
    missing     欠損の置き場所(先 / 後)
    choices     種類が「宣言された列挙」の列について、候補の並びを | で区切って書く行で使う
    source      その宣言の出典(記事か README のファイル名 + 行番号)。空欄は止まる
    swap        入れ替え方(verify で入力表の行順を入れ替えるときの宣言。全行で同じ値)

判定したことは「宣言された鍵で行の順が一意に決まるか」までで、どの並び順が業務として正しいかも、
どの列を鍵にすべきかも、宣言の良し悪しも判定しない。標準ライブラリのみ(csv / json / decimal /
datetime / hashlib / pathlib / platform / re / argparse)。
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import platform
import re
import sys
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import cmp_to_key
from io import StringIO
from pathlib import Path

# 宣言表の列(全部必要)
DECL_COLUMNS = ("rank", "column", "direction", "kind", "missing", "choices", "source", "swap")

# 登録されている語彙。この外は「表として読めない」(終了コード 2)にする
DIRECTIONS = ("昇順", "降順")
KINDS = ("コードポイント列", "整数", "Decimal", "日付", "宣言された列挙")
MISSING_PLACES = ("先", "後")
SWAPS = ("逆順", "先頭と末尾を入れ替え", "1 つずつずらす")

# CLI の下位コマンド。この 4 つだけで、option は -h 以外に 1 つも無い
SUBCOMMANDS = ("sort", "check", "verify", "init")

# 止まる理由コード(11 個)。止まったときは 1 行も並べない
STOP_REASONS = ("宣言表が 0 行", "順位の重複", "出典の欄が空", "値の種類が空欄 or 未登録",
                "欠損の置き場所が空欄", "宣言表に無い列名", "データ表に無い列名", "float の混入",
                "同値の組が残る", "2 回目の判定部分がバイト列として不一致",
                "行順を入れ替えた表で出力が変わる")

INT_RE = re.compile(r"-?\d+\Z")
DEC_RE = re.compile(r"-?\d+(\.\d+)?\Z")
FLOAT_SHAPE_RE = re.compile(r"-?(\d+\.\d*|\.\d+|\d+(\.\d*)?[eE][-+]?\d+)\Z")

# 判定部分に入れない欄(sha256 の対象にもしない)
READ_KEYS = ("読んだデータ表の絶対パス", "読んだ宣言表の絶対パス", "読んだ時刻", "ホスト名")

MISSING = object()   # 欠損を表す印。値とは別の箱に入れる


class ReadError(Exception):
    """表として読めない(理由コードにせず終了コード 2 で返す = 表を書く側の話)。"""


@dataclass(frozen=True)
class Pending:
    reason: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"reason": self.reason, "detail": self.detail}


@dataclass(frozen=True)
class Key:
    rank: int
    column: str
    direction: str
    kind: str
    missing: str
    source: str
    number: int          # 宣言表の行番号

    @property
    def descending(self) -> bool:
        return self.direction == DIRECTIONS[1]

    @property
    def missing_first(self) -> bool:
        return self.missing == MISSING_PLACES[0]


@dataclass(frozen=True)
class Choices:
    column: str
    values: tuple[str, ...]
    source: str
    number: int


@dataclass(frozen=True)
class Report:
    ok: bool
    pending: tuple[Pending, ...]
    rows: int            # データ表の行数
    declared: int        # 宣言表の鍵の行数


# ------------------------------------------------------------------ 宣言表

@dataclass
class Order:
    keys: tuple[Key, ...]
    choices: dict[str, Choices]
    swap: str
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Order":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"宣言表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Order":
        reader = csv.DictReader(text.splitlines())
        header = tuple(reader.fieldnames or ())
        missing_cols = [c for c in DECL_COLUMNS if c not in header]
        if missing_cols:
            raise ReadError("宣言表に " + " / ".join(missing_cols) + " の列が無い")
        keys: list[Key] = []
        choices: dict[str, Choices] = {}
        pending: list[Pending] = []
        swaps: set[str] = set()
        seen_rank: dict[int, int] = {}
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in DECL_COLUMNS}
            if cell["swap"]:
                if cell["swap"] not in SWAPS:
                    raise ReadError(f"行 {i}: 入れ替え方 {cell['swap']} は登録の外"
                                    f"({' / '.join(SWAPS)})")
                swaps.add(cell["swap"])
            if not cell["column"]:
                raise ReadError(f"行 {i}: 列名が空欄")
            if not cell["rank"]:
                if not cell["choices"]:
                    raise ReadError(f"行 {i}: 順位も候補の並びも空欄(どちらの行なのか決まらない)")
                values = tuple(v.strip() for v in cell["choices"].split("|"))
                if len(values) < 2 or any(not v for v in values) or len(set(values)) != len(values):
                    raise ReadError(f"行 {i}: 候補の並びは 2 件以上の重複しない値を | で区切る")
                if cell["column"] in choices:
                    raise ReadError(f"行 {i}: 同じ列の候補の並びが 2 行ある: {cell['column']}")
                if not cell["source"]:
                    pending.append(Pending(STOP_REASONS[2], f"行 {i}(候補の並び {cell['column']})"))
                choices[cell["column"]] = Choices(cell["column"], values, cell["source"], i)
                continue
            if not INT_RE.match(cell["rank"]) or int(cell["rank"]) < 1:
                raise ReadError(f"行 {i}: 順位は 1 以上の整数({cell['rank']})")
            rank = int(cell["rank"])
            if cell["direction"] not in DIRECTIONS:
                raise ReadError(f"行 {i}: 向きは {' / '.join(DIRECTIONS)}"
                                f"({cell['direction'] or '空欄'})")
            if cell["missing"] and cell["missing"] not in MISSING_PLACES:
                raise ReadError(f"行 {i}: 欠損の置き場所は {' / '.join(MISSING_PLACES)}"
                                f"({cell['missing']})")
            where = f"行 {i}({cell['column']})"
            if rank in seen_rank:
                pending.append(Pending(STOP_REASONS[1], f"順位 {rank}: 行 {seen_rank[rank]} と行 {i}"))
            else:
                seen_rank[rank] = i
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[2], where))
            if cell["kind"] not in KINDS:
                pending.append(Pending(STOP_REASONS[3], where + "の種類: " + (cell["kind"] or "空欄")))
            if not cell["missing"]:
                pending.append(Pending(STOP_REASONS[4], where))
            keys.append(Key(rank=rank, column=cell["column"], direction=cell["direction"],
                            kind=cell["kind"], missing=cell["missing"], source=cell["source"],
                            number=i))
        if not keys:
            pending.append(Pending(STOP_REASONS[0], "鍵の行が 1 行も無い"))
        if len(swaps) > 1:
            raise ReadError("入れ替え方の宣言が 2 通り以上ある: " + " / ".join(sorted(swaps)))
        declared_columns = {k.column for k in keys}
        for col, ch in sorted(choices.items(), key=lambda kv: kv[1].number):
            if col not in declared_columns:
                pending.append(Pending(STOP_REASONS[5], f"行 {ch.number}: 候補の並びの列名 {col}"))
        for k in keys:
            if k.kind == KINDS[4] and k.column not in choices:
                pending.append(Pending(STOP_REASONS[3], f"行 {k.number}({k.column})の種類: "
                                                        "宣言された列挙だが候補の並びの行が無い"))
        return cls(keys=tuple(sorted(keys, key=lambda k: k.rank)), choices=choices,
                   swap=next(iter(swaps), ""), pending=tuple(pending), path=path)

    def sha256(self) -> str:
        return hashlib.sha256(Path(self.path).read_bytes()).hexdigest() if self.path else ""


# ------------------------------------------------------------------ データ表

@dataclass
class Table:
    header: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Table":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"データ表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Table":
        rows = list(csv.reader(text.splitlines()))
        if not rows:
            raise ReadError("データ表が空(ヘッダの行が無い)")
        header = tuple(c.strip() for c in rows[0])
        if len(set(header)) != len(header):
            raise ReadError("データ表のヘッダに同じ列名が 2 つある")
        body: list[tuple[object, ...]] = []
        for i, r in enumerate(rows[1:], start=2):
            if len(r) != len(header):
                raise ReadError(f"データ表 行 {i}: 列の数がヘッダと違う({len(r)} / {len(header)})")
            body.append(tuple(r))
        return cls(header=header, rows=tuple(body), path=path)

    def index_of(self, column: str) -> int:
        return self.header.index(column)

    def swapped(self, how: str) -> "Table":
        """宣言された入れ替え方で行順だけを入れ替えた表を作る(乱数の既定は持たない)。"""
        if how not in SWAPS:
            raise ReadError(f"入れ替え方が登録の外: {how}")
        rows = list(self.rows)
        if len(rows) >= 2:
            if how == SWAPS[0]:
                rows.reverse()
            elif how == SWAPS[1]:
                rows[0], rows[-1] = rows[-1], rows[0]
            else:
                rows = rows[1:] + rows[:1]
        return Table(header=self.header, rows=tuple(rows), path=self.path)

    def csv_text(self, index: tuple[int, ...] | None = None) -> str:
        order = range(len(self.rows)) if index is None else index
        buf = StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(self.header)
        for i in order:
            w.writerow(self.rows[i])
        return buf.getvalue()

    def sha256(self) -> str:
        return hashlib.sha256(Path(self.path).read_bytes()).hexdigest() if self.path else ""


# ------------------------------------------------------------------ 値を宣言どおりに読む

def read_value(cell: object, key: Key, choices: dict[str, Choices],
               where: str) -> tuple[object, Pending | None]:
    """宣言された種類としてだけ値を読む。読めない形は理由コードか「表として読めない」に落とす。"""
    if isinstance(cell, float):
        return MISSING, Pending(STOP_REASONS[7], where + f": float を受け取った({cell!r})")
    text = cell if isinstance(cell, str) else str(cell)
    if text.strip() == "":
        return MISSING, None
    text = text.strip()
    if key.kind == KINDS[0]:                               # コードポイント列
        return text, None
    if key.kind == KINDS[1]:                               # 整数
        if INT_RE.match(text):
            return int(text), None
        if FLOAT_SHAPE_RE.match(text):
            return MISSING, Pending(STOP_REASONS[7], where + f": 整数の宣言に小数({text})")
        raise ReadError(f"{where}: 整数の宣言だが数として読めない({text})")
    if key.kind == KINDS[2]:                               # Decimal
        if DEC_RE.match(text):
            try:
                return Decimal(text), None
            except InvalidOperation:                       # pragma: no cover - DEC_RE が先に落とす
                raise ReadError(f"{where}: Decimal として読めない({text})")
        if FLOAT_SHAPE_RE.match(text):
            return MISSING, Pending(STOP_REASONS[7], where + f": 指数表記({text})")
        raise ReadError(f"{where}: Decimal の宣言だが数として読めない({text})")
    if key.kind == KINDS[3]:                               # 日付
        try:
            return datetime.date.fromisoformat(text), None
        except ValueError:
            raise ReadError(f"{where}: 日付の宣言だが {text} は ISO の日付として読めない")
    ch = choices[key.column]                               # 宣言された列挙
    if text not in ch.values:
        return MISSING, Pending(STOP_REASONS[3], where + f": 宣言された列挙の候補に無い値({text})")
    return ch.values.index(text), None


# ------------------------------------------------------------------ 並べる

@dataclass
class Sorted:
    report: Report
    table: Table
    order: Order
    index: tuple[int, ...]
    key_rows: tuple[tuple[object, ...], ...]
    read_at: str
    host: str

    # -------------------------------------------------- 件数と分母
    def groups(self) -> list[tuple[tuple[object, ...], list[int]]]:
        out: dict[tuple[object, ...], list[int]] = {}
        for i, k in enumerate(self.key_rows):
            out.setdefault(k, []).append(i)
        return list(out.items())

    def tie_groups(self) -> list[tuple[tuple[object, ...], list[int]]]:
        return [(k, rows) for k, rows in self.groups() if len(rows) >= 2]

    def counts(self) -> dict[str, object]:
        """一意になった率を単独では返さない。件数と分母の内訳を必ず併記する。"""
        ties = self.tie_groups()
        involved = sum(len(rows) for _, rows in ties)
        total = self.report.rows
        out: dict[str, object] = {
            "データ表の行数": total,
            "鍵の列": [f"{k.rank}:{k.column}({k.kind} / {k.direction} / "
                       f"欠損は{k.missing or '空欄'})" for k in self.order.keys],
            "鍵の組数": len(self.groups()),
            "同値の組の件数": len(ties),
            "同値の組に関与した行数": involved,
            "順が一意に決まった行数": total - involved,
        }
        out["分母に含めたもの"] = (
            f"データ表の行数 {total} = 順が一意に決まった行数 {total - involved}"
            f" + 同値の組に関与した行数 {involved}(同値の組 {len(ties)} 組、"
            f"鍵の組数 {len(self.groups())})")
        out["鍵は宣言された列だけ"] = (
            f"宣言表の鍵 {self.report.declared} 行の列だけで比較した。列名や自然文から鍵を"
            "推測して足す経路は無く、行番号や連番を振って一意にする経路も無い")
        return out

    def ties(self) -> list[dict[str, object]]:
        """同値の組。鍵の verbatim と、データ表の行番号を出す(行番号は振らずに読むだけ)。"""
        out: list[dict[str, object]] = []
        for _, rows in sorted(self.tie_groups(), key=lambda kv: kv[1][0]):
            out.append({"鍵": self._verbatim(rows[0]),
                        "データ表の行番号": [i + 2 for i in rows],
                        "行数": len(rows)})
        return out

    def _verbatim(self, i: int) -> dict[str, str]:
        return {k.column: str(self.table.rows[i][self.table.index_of(k.column)])
                for k in self.order.keys if k.column in self.table.header}

    # -------------------------------------------------- 並べた表
    def rows(self) -> list[tuple[object, ...]]:
        self._guard()
        return [self.table.rows[i] for i in self.index]

    def judgement_bytes(self) -> bytes:
        """判定部分 = 並べた CSV のバイト列。時刻・絶対パス・ホスト名は入れない。"""
        self._guard()
        return self.table.csv_text(self.index).encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.judgement_bytes()).hexdigest()

    def read_condition(self) -> dict[str, str]:
        return {"読んだデータ表の絶対パス": self.table.path,
                "読んだ宣言表の絶対パス": self.order.path,
                "読んだ時刻": self.read_at, "ホスト名": self.host}

    def _guard(self) -> None:
        if not self.report.ok:
            raise RuntimeError("止まっているので並べた表は無い。report.pending の理由コードを見る")


def _compare(a: tuple[object, ...], b: tuple[object, ...], keys: tuple[Key, ...]) -> int:
    """宣言された鍵だけで前後を決める。欠損は宣言された置き場所に従い、向きには引きずられない。"""
    for k, va, vb in zip(keys, a, b):
        ma, mb = va is MISSING, vb is MISSING
        if ma and mb:
            continue
        if ma or mb:
            return -1 if (ma if k.missing_first else mb) else 1
        if va == vb:
            continue
        return -1 if (va < vb) != k.descending else 1
    return 0


def sort_table(table: Table, order: Order) -> Sorted:
    """宣言表を検査し、通れば宣言された鍵だけで並べる。同値の組が残れば 1 行も並べない。"""
    now = datetime.datetime.now().isoformat(timespec="seconds")
    host = platform.node()

    def made(pending: tuple[Pending, ...], index: tuple[int, ...] = (),
             key_rows: tuple[tuple[object, ...], ...] = ()) -> Sorted:
        return Sorted(report=Report(not pending, pending, len(table.rows), len(order.keys)),
                      table=table, order=order, index=index, key_rows=key_rows,
                      read_at=now, host=host)

    pending = list(order.pending)
    for k in order.keys:
        if k.column not in table.header:
            pending.append(Pending(STOP_REASONS[6], f"行 {k.number}: 鍵の列名 {k.column}"))
    if pending:
        return made(tuple(pending))

    key_rows: list[tuple[object, ...]] = []
    for i, row in enumerate(table.rows):
        values: list[object] = []
        for k in order.keys:
            where = f"データ表 行 {i + 2} 列 {k.column}"
            v, bad = read_value(row[table.index_of(k.column)], k, order.choices, where)
            if bad is not None:
                pending.append(bad)
            values.append(v)
        key_rows.append(tuple(values))
    if pending:
        return made(tuple(pending))

    normalized = tuple(key_rows)
    counted = Counter(normalized)
    ties = [k for k, n in counted.items() if n >= 2]
    if ties:
        involved = sum(counted[k] for k in ties)
        pending.append(Pending(STOP_REASONS[8],
                               f"同値の組 {len(ties)} 組 / 関与した行数 {involved}"
                               f" / 分母はデータ表の行数 {len(table.rows)}"
                               f" と鍵の組数 {len(counted)}"))
        return made(tuple(pending), key_rows=normalized)

    index = tuple(sorted(range(len(table.rows)),
                         key=cmp_to_key(lambda i, j: _compare(normalized[i], normalized[j],
                                                              order.keys))))
    return made((), index=index, key_rows=normalized)


def verify(table: Table, order: Order) -> dict[str, object]:
    """2 回並べて判定部分の sha256 を突き合わせ、宣言された入れ替え方の表でも同じ出力かを見る。"""
    first = sort_table(table, order)
    if not first.report.ok:
        return {"ok": False, "stage": "並べる前に止まった", **first.counts(),
                "pending": [p.as_dict() for p in first.report.pending]}
    if not order.swap:
        raise ReadError("宣言表に入れ替え方(swap)が無いので verify は走らせない")
    second = sort_table(table, order)
    swapped = sort_table(table.swapped(order.swap), order)
    pending: list[Pending] = []
    if first.sha256() != second.sha256():
        pending.append(Pending(STOP_REASONS[9], f"2 回目 {second.sha256()[:12]}"))
    if not (swapped.report.ok and first.sha256() == swapped.sha256()):
        pending.append(Pending(STOP_REASONS[10],
                               f"入れ替え方 {order.swap} の表で {swapped.sha256()[:12]}"
                               if swapped.report.ok else
                               f"入れ替え方 {order.swap} の表では止まった"))
    out: dict[str, object] = {"ok": not pending, "一致": not pending, "並べた回数": 2,
                              "入れ替え方": order.swap, "sha256": first.sha256(),
                              "2 回目の sha256": second.sha256(),
                              "入れ替えた表の sha256": swapped.sha256() if swapped.report.ok else ""}
    if pending:
        out["観測"] = ("同じ宣言表から違うバイト列が出た(平均も多数決もしない。"
                       "どちらが正しいかも決めない)")
        out["pending"] = [p.as_dict() for p in pending]
    return out


# ------------------------------------------------------------------ ひな型

TEMPLATE_DATA = [
    ["社員番号", "氏名カナ", "区分", "支給日", "金額"],
    ["9", "ヤマダ", "甲", "2026-04-25", "8290"],
    ["10", "スズキ", "乙", "2026-04-25", "829.0"],
]
TEMPLATE_ORDER = [
    list(DECL_COLUMNS),
    ["1", "支給日", "昇順", "日付", "後", "", "合成の並び順メモ(架空)L1", "逆順"],
    ["2", "区分", "昇順", "宣言された列挙", "後", "", "合成の並び順メモ(架空)L2", ""],
    ["", "区分", "", "", "", "甲|乙|丙", "合成の並び順メモ(架空)L3", ""],
    ["3", "社員番号", "昇順", "整数", "先", "", "合成の並び順メモ(架空)L4", ""],
]


def init(dest: str | Path) -> tuple[Path, Path]:
    d = Path(dest)
    d.mkdir(parents=True, exist_ok=True)
    data, order = d / "データ表.csv", d / "並び順.csv"
    for path, body in ((data, TEMPLATE_DATA), (order, TEMPLATE_ORDER)):
        with path.open("w", encoding="utf-8", newline="") as f:
            csv.writer(f, lineterminator="\n").writerows(body)
    return data, order


# ------------------------------------------------------------------ CLI

def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def build_parser() -> argparse.ArgumentParser:
    """CLI は sort / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = argparse.ArgumentParser(prog="order_table", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in SUBCOMMANDS[:3]:
        p = sub.add_parser(name)
        p.add_argument("data")
        p.add_argument("order")
    sub.add_parser(SUBCOMMANDS[3]).add_argument("dest")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == "init":
        data, order = init(a.dest)
        print(f"書いた: {data} / {order}")
        return 0
    try:
        table, order = Table.load(a.data), Order.load(a.order)
        if a.cmd == "verify":
            out = verify(table, order)
            _print(out)
            return 0 if out["ok"] else 3
        s = sort_table(table, order)
    except ReadError as e:
        print(f"表として読めない: {e}", file=sys.stderr)
        return 2
    if not s.report.ok:
        _print({"ok": False, "stage": "並べる前に止まった", **s.counts(),
                "同値の組": s.ties(), "pending": [p.as_dict() for p in s.report.pending]})
        return 3
    if a.cmd == "check":
        _print({"ok": True, "stage": "順が一意に決まった", **s.counts(),
                "sha256": s.sha256(), "読んだ条件": s.read_condition()})
        return 0
    sys.stdout.write(s.table.csv_text(s.index))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
