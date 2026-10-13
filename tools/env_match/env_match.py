"""env_match — 同じ入力を別の環境で走らせた出力どうしを、宣言された判定部分だけで突き合わせる。

**同じ入力・同じ道具でも、判定に入れる欄を宣言しないまま指紋を比べると、環境が違うだけで一致が
崩れる。** この部品は「判定に入れる欄 / 入れない欄」を宣言表からだけ取り、ラベル間でバイト列を
突き合わせ、欄ごとに 4 値(一致 / 不一致 / 判定部分が取れない / 宣言が無い)に分ける。

持たせていないものが規律になっている。

  - **宣言表に無い欄を勝手に判定から外さない**(一致させるために黙って除外する経路が無い。
    宣言に無い欄は 4 値の「宣言が無い」に入って数に残る)
  - **外した欄の件数と分母(全欄数)を必ず併記**し、一致率を単独で返さない
  - **正規化しない**(改行の揃え・空白の詰め・キーの並べ替え・数の書式の寄せが無い。寄せれば
    一致するのを一致と呼ばない)
  - **許容誤差・近似一致の引数を持たない**(相異なるかはバイト列の一致でだけ決める)
  - **自分で走らせない**(子プロセスを起動せず、環境変数も読み書きしない。走らせるのは人で、
    この部品は突き合わせるだけ)
  - **現在の環境を既定のラベルとして混ぜない**(基準にするラベルも宣言から取る)
  - **差が出た理由を環境要素に割り当てない**(1 要素だけ違う対でも「その対で差が出た」までで
    止める)
  - **不一致と「判定部分が取れない」を混ぜない**(4 値を潰す引数が無い)
  - **不一致の行は差が現れた欄名と行番号**(と、判定に入れた欄の値)だけを返す(原因も直し方も
    書かない)
  - **出力の束もラベル表も宣言表も書き換えず、欄を足さない**
  - **出典の欄が空のラベル行・宣言行は使わずに止まる**
  - **float を比較に使わない**(バイト列の一致だけ)

入力は 3 つ。出力の束(ラベルごとのファイル)、ラベル表(CSV)、判定部分の宣言表(CSV)。

出力の束は、ラベル 1 つにつき `<ラベル名>.tsv` の 1 ファイル。中身は 1 行 1 欄で、
**欄名 → タブ → 値** とだけ書く(値の中にタブと改行は書けない)。行の終わりは触らないので、
端末の既定の改行が違えば値のバイト列も違ったままになる。

ラベル表の列は 6 つ。

    label       ラベル名(= 出力の束のファイル名)
    element     変えた環境要素(空欄は止まる)
    setting     設定した値
    source      その行の出典(記事か README のファイル名 + 行番号)。空欄は止まる
    base        基準にするラベル名(書く行は 1 行でよい。全行で同じ値)
    swap        入れ替え方(verify がラベル表の行順を入れ替えるときの宣言。全行で同じ値)

判定部分の宣言表の列は 4 つ。

    field       欄名(出力の束の 1 行目の列)
    judge       判定に入れる / 入れない
    reason      入れない行の理由の分類(時刻 / 絶対パス / ホスト名 / 版 / 乱数の種)
    source      その宣言の出典(ファイル名 + 行番号)。空欄は止まる

判定したことは「宣言された判定部分がラベル間でバイト列として一致するか」までで、どの環境が
正しいかも、差の原因も、外す欄の一覧が足りているかも判定しない。標準ライブラリのみ
(csv / json / hashlib / pathlib / datetime / platform / argparse)。
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import platform
import sys
from dataclasses import dataclass
from pathlib import Path

# ラベル表と宣言表の列(どちらも全部必要)
LABEL_COLUMNS = ("label", "element", "setting", "source", "base", "swap")
DECL_COLUMNS = ("field", "judge", "reason", "source")

# 登録されている語彙。この外は「表として読めない」(終了コード 2)にする
JUDGES = ("入れる", "入れない")
REASONS = ("時刻", "絶対パス", "ホスト名", "版", "乱数の種")
SWAPS = ("逆順", "先頭と末尾を入れ替え", "1 つずつずらす")

# 欄ごとの 4 値。潰す引数は無い
RESULTS = ("一致", "不一致", "判定部分が取れない", "宣言が無い")

# 止まる理由コード(12 個)。止まったときは 1 欄も突き合わせた結果を返さない
STOP_REASONS = ("宣言表が 0 行", "ラベルが 1 つ", "ラベル名の重複", "環境要素の欄が空",
                "出典の欄が空", "理由の分類が未登録", "宣言表に無い欄名", "出力に無い欄名",
                "判定部分が取れない", "基準ラベルが表に無い",
                "2 回目の判定部分がバイト列として不一致",
                "ラベル順を入れ替えた表で出力が変わる")

# CLI の下位コマンド。この 4 つだけで、option は -h 以外に 1 つも無い
SUBCOMMANDS = ("match", "check", "verify", "init")

# 判定部分に入れない欄(sha256 の対象にもしない)
READ_KEYS = ("読んだ束の絶対パス", "読んだラベル表の絶対パス", "読んだ宣言表の絶対パス",
             "読んだ時刻", "ホスト名")

SUFFIX = ".tsv"


class ReadError(Exception):
    """表として読めない(理由コードにせず終了コード 2 で返す = 表を書く側の話)。"""


def show(value: bytes) -> str:
    """値を見えるようにして返す(復帰文字は見えないので書き換えずに印で示す)。寄せも詰めもしない。"""
    return value.decode("utf-8", "backslashreplace").replace("\r", "\\r")


@dataclass(frozen=True)
class Pending:
    reason: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"reason": self.reason, "detail": self.detail}


# ------------------------------------------------------------------ ラベル表

@dataclass(frozen=True)
class Label:
    name: str
    element: str
    setting: str
    source: str
    number: int          # ラベル表の行番号


@dataclass(frozen=True)
class Labels:
    items: tuple[Label, ...]
    base: str
    swap: str
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Labels":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"ラベル表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Labels":
        reader = csv.DictReader(text.splitlines())
        header = tuple(reader.fieldnames or ())
        lack = [c for c in LABEL_COLUMNS if c not in header]
        if lack:
            raise ReadError("ラベル表に " + " / ".join(lack) + " の列が無い")
        items: list[Label] = []
        pending: list[Pending] = []
        bases: set[str] = set()
        swaps: set[str] = set()
        seen: dict[str, int] = {}
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in LABEL_COLUMNS}
            if not cell["label"]:
                raise ReadError(f"行 {i}: ラベル名が空欄")
            if not cell["setting"]:
                raise ReadError(f"行 {i}: 設定した値が空欄({cell['label']})")
            if cell["base"]:
                bases.add(cell["base"])
            if cell["swap"]:
                if cell["swap"] not in SWAPS:
                    raise ReadError(f"行 {i}: 入れ替え方 {cell['swap']} は登録の外"
                                    f"({' / '.join(SWAPS)})")
                swaps.add(cell["swap"])
            where = f"行 {i}({cell['label']})"
            if cell["label"] in seen:
                pending.append(Pending(STOP_REASONS[2],
                                       f"{cell['label']}: 行 {seen[cell['label']]} と行 {i}"))
            else:
                seen[cell["label"]] = i
            if not cell["element"]:
                pending.append(Pending(STOP_REASONS[3], where))
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[4], where))
            items.append(Label(name=cell["label"], element=cell["element"],
                               setting=cell["setting"], source=cell["source"], number=i))
        if not items:
            raise ReadError("ラベル表に行が無い(ヘッダだけ)")
        if len(bases) > 1:
            raise ReadError("基準ラベルの宣言が 2 通り以上ある: " + " / ".join(sorted(bases)))
        if len(swaps) > 1:
            raise ReadError("入れ替え方の宣言が 2 通り以上ある: " + " / ".join(sorted(swaps)))
        if len(items) < 2:
            pending.append(Pending(STOP_REASONS[1],
                                   f"ラベルは {items[0].name} の 1 つだけ(突き合わせる相手が無い)"))
        base = next(iter(bases), "")
        if not base:
            pending.append(Pending(STOP_REASONS[9], "基準にするラベルが宣言されていない"))
        elif base not in seen:
            pending.append(Pending(STOP_REASONS[9], f"宣言された基準ラベル {base} が表に無い"))
        return cls(items=tuple(items), base=base, swap=next(iter(swaps), ""),
                   pending=tuple(pending), path=path)

    @property
    def names(self) -> tuple[str, ...]:
        """ラベル名をコードポイント列の順で返す(表の行順には依らせない)。"""
        return tuple(sorted({x.name for x in self.items}))

    @property
    def others(self) -> tuple[str, ...]:
        return tuple(n for n in self.names if n != self.base)

    def of(self, name: str) -> Label:
        return next(x for x in self.items if x.name == name)

    def swapped(self, how: str) -> "Labels":
        """宣言された入れ替え方でラベル表の行順だけを入れ替える(乱数の既定は持たない)。"""
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
        return Labels(items=tuple(rows), base=self.base, swap=self.swap,
                      pending=self.pending, path=self.path)


# ------------------------------------------------------------------ 宣言表

@dataclass(frozen=True)
class Field:
    name: str
    judge: str
    reason: str
    source: str
    number: int          # 宣言表の行番号

    @property
    def included(self) -> bool:
        return self.judge == JUDGES[0]


@dataclass(frozen=True)
class Decl:
    fields: tuple[Field, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Decl":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"宣言表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Decl":
        reader = csv.DictReader(text.splitlines())
        header = tuple(reader.fieldnames or ())
        lack = [c for c in DECL_COLUMNS if c not in header]
        if lack:
            raise ReadError("宣言表に " + " / ".join(lack) + " の列が無い")
        fields: list[Field] = []
        pending: list[Pending] = []
        seen: dict[str, int] = {}
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in DECL_COLUMNS}
            if not cell["field"]:
                raise ReadError(f"行 {i}: 欄名が空欄")
            if cell["field"] in seen:
                raise ReadError(f"行 {i}: 同じ欄名の宣言が 2 行ある({cell['field']})")
            seen[cell["field"]] = i
            if cell["judge"] not in JUDGES:
                raise ReadError(f"行 {i}: 判定は {' / '.join(JUDGES)}"
                                f"({cell['judge'] or '空欄'})")
            where = f"行 {i}({cell['field']})"
            if cell["judge"] == JUDGES[0] and cell["reason"]:
                raise ReadError(f"行 {i}: 入れる 行に理由の分類は書かない({cell['reason']})")
            if cell["judge"] == JUDGES[1] and cell["reason"] not in REASONS:
                pending.append(Pending(STOP_REASONS[5],
                                       where + "の理由: " + (cell["reason"] or "空欄")))
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[4], where))
            fields.append(Field(name=cell["field"], judge=cell["judge"], reason=cell["reason"],
                                source=cell["source"], number=i))
        if not fields:
            pending.append(Pending(STOP_REASONS[0], "宣言の行が 1 行も無い"))
        return cls(fields=tuple(fields), pending=tuple(pending), path=path)

    @property
    def names(self) -> frozenset[str]:
        return frozenset(f.name for f in self.fields)

    @property
    def included(self) -> tuple[Field, ...]:
        return tuple(f for f in self.fields if f.included)

    @property
    def excluded(self) -> tuple[Field, ...]:
        return tuple(f for f in self.fields if not f.included)


# ------------------------------------------------------------------ 出力の束

@dataclass(frozen=True)
class Output:
    label: str
    values: dict[str, bytes]
    lines: dict[str, int]
    path: str = ""

    @classmethod
    def parse(cls, label: str, data: bytes, path: str = "") -> "Output":
        """1 行 1 欄(欄名 → タブ → 値)として読む。行の終わりは触らない。"""
        records = data.split(b"\n")
        if records and records[-1] == b"":
            records.pop()
        if not records:
            raise ReadError(f"{label}: 出力が空(1 欄も無い)")
        values: dict[str, bytes] = {}
        lines: dict[str, int] = {}
        for i, rec in enumerate(records, start=1):
            parts = rec.split(b"\t")
            if len(parts) != 2:
                raise ReadError(f"{label} 行 {i}: 欄名とタブと値の 1 行 1 欄で書く"
                                f"(タブが {len(parts) - 1} 個)")
            try:
                name = parts[0].decode("utf-8")
            except UnicodeDecodeError:
                raise ReadError(f"{label} 行 {i}: 欄名が utf-8 として読めない") from None
            if not name.strip():
                raise ReadError(f"{label} 行 {i}: 欄名が空欄")
            if name in values:
                raise ReadError(f"{label} 行 {i}: 同じ欄名が 2 行ある({name})")
            values[name] = parts[1]
            lines[name] = i
        return cls(label=label, values=values, lines=lines, path=path)

    @classmethod
    def load(cls, root: str | Path, label: str) -> "Output":
        p = Path(root) / f"{label}{SUFFIX}"
        if not p.exists():
            raise ReadError(f"出力の束に {label}{SUFFIX} が無い: {p}")
        return cls.parse(label, p.read_bytes(), str(p.resolve()))


@dataclass(frozen=True)
class Outputs:
    items: dict[str, Output]
    root: str = ""

    @classmethod
    def load(cls, root: str | Path, labels: Labels) -> "Outputs":
        d = Path(root)
        if not d.is_dir():
            raise ReadError(f"出力の束の置き場が無い: {d}")
        return cls(items={n: Output.load(d, n) for n in labels.names}, root=str(d.resolve()))

    @classmethod
    def from_bytes(cls, bundle: dict[str, bytes], labels: Labels) -> "Outputs":
        items: dict[str, Output] = {}
        for n in labels.names:
            if n not in bundle:
                raise ReadError(f"出力の束に {n}{SUFFIX} が無い")
            items[n] = Output.parse(n, bundle[n])
        return cls(items=items)

    @property
    def union(self) -> tuple[str, ...]:
        """どれかのラベルの出力に現れた欄名(コードポイント列の順)。"""
        out: set[str] = set()
        for o in self.items.values():
            out |= set(o.values)
        return tuple(sorted(out))


# ------------------------------------------------------------------ 突き合わせる

@dataclass(frozen=True)
class Cell:
    field: str
    judge: str
    result: str
    differs: tuple[str, ...]      # 基準ラベルと差が出たラベル(コードポイント列の順)
    missing: tuple[str, ...]      # この欄が出力に無かったラベル
    reason: str = ""              # 判定から外した理由の分類
    number: int = 0               # 宣言表の行番号


@dataclass(frozen=True)
class Report:
    ok: bool
    pending: tuple[Pending, ...]
    labels: int
    declared: int


@dataclass(frozen=True)
class Matched:
    report: Report
    cells: tuple[Cell, ...]
    labels: Labels
    decl: Decl
    outputs: Outputs
    read_at: str
    host: str

    # -------------------------------------------------- 4 値と分母
    @property
    def verdict(self) -> str:
        """全体の結果。判定に入れた欄が 1 つも食い違っていなければ 一致。"""
        self._guard()
        return RESULTS[1] if self.by_result(RESULTS[1]) else RESULTS[0]

    def by_result(self, result: str) -> tuple[Cell, ...]:
        return tuple(c for c in self.cells if c.result == result)

    def counts(self) -> dict[str, object]:
        """一致率を単独では返さない。4 値の件数と分母の内訳を必ず併記する。"""
        four = {r: len(self.by_result(r)) for r in RESULTS}
        included, excluded = len(self.decl.included), len(self.decl.excluded)
        union = self.outputs.union
        out: dict[str, object] = {
            "ラベル数": self.report.labels,
            "基準ラベル": self.labels.base,
            "突き合わせた対の数": max(self.report.labels - 1, 0),
            "宣言表の行数": self.report.declared,
            "判定に入れた欄数": included,
            "判定から外した欄数": excluded,
            "出力に現れた欄数": len(union),
            "4 値": four,
            "外した欄の内訳": {r: len([f for f in self.decl.excluded if f.reason == r])
                               for r in REASONS
                               if any(f.reason == r for f in self.decl.excluded)},
            "外した欄で差が出た欄数": len([c for c in self.cells
                                           if c.judge == JUDGES[1] and c.differs]),
            "突き合わせたか": ("突き合わせた" if self.cells else
                               "突き合わせていない(表が揃う前に止まったので 4 値は全て 0)"),
        }
        out["分母に含めたもの"] = (
            f"宣言表の行数 {self.report.declared} = 判定に入れた欄数 {included}"
            f" + 判定から外した欄数 {excluded}。4 値のうち"
            f"一致 {four[RESULTS[0]]} + 不一致 {four[RESULTS[1]]}"
            f" + 判定部分が取れない {four[RESULTS[2]]} = 判定に入れた欄数 {included}。"
            f"宣言が無い {four[RESULTS[3]]} は出力に現れた欄数 {len(union)}"
            f" のうち宣言表に無かった欄の数")
        out["外した欄は宣言された欄だけ"] = (
            f"判定から外したのは宣言表で {JUDGES[1]} と書かれた {excluded} 欄だけで、"
            "一致させるために欄を外す経路は無い。宣言に無い欄は「宣言が無い」として数に残る")
        out["差の原因は書かない"] = (
            "差が出た対はそのまま返すが、どの環境要素のせいかは書かない"
            "(1 要素だけ違う対でも『その対で差が出た』までで止める)")
        return out

    def pairs(self) -> list[dict[str, object]]:
        """基準ラベルとの対ごとに、差が出た欄数を返す(原因は割り当てない)。"""
        out: list[dict[str, object]] = []
        for name in self.labels.others:
            x = self.labels.of(name)
            out.append({
                "ラベル": name,
                "変えた環境要素": x.element,
                "設定した値": x.setting,
                "判定に入れた欄で差が出た欄数": len([c for c in self.cells
                                                     if c.judge == JUDGES[0]
                                                     and name in c.differs]),
                "外した欄で差が出た欄数": len([c for c in self.cells
                                               if c.judge == JUDGES[1]
                                               and name in c.differs]),
                "宣言が無い欄で差が出た欄数": len([c for c in self.cells
                                                     if c.result == RESULTS[3]
                                                     and name in c.differs]),
                "この欄が出力に無かった": [c.field for c in self.cells if name in c.missing],
            })
        return out

    def mismatches(self) -> list[dict[str, object]]:
        """不一致の欄。差が現れた欄名と行番号(と判定に入れた欄の値)だけを返す。"""
        base = self.outputs.items[self.labels.base]
        out: list[dict[str, object]] = []
        for c in self.by_result(RESULTS[1]):
            out.append({
                "欄名": c.field,
                "基準ラベルの行番号": base.lines[c.field],
                "基準ラベルの値": show(base.values[c.field]),
                "差が出たラベル": [{"ラベル": n,
                                    "行番号": self.outputs.items[n].lines[c.field],
                                    "値": show(self.outputs.items[n].values[c.field])}
                                   for n in c.differs],
            })
        return out

    def undeclared(self) -> list[dict[str, object]]:
        """宣言が無い欄。出力に在るのに宣言表に無いので、判定にも外す側にも入れられない。"""
        return [{"欄名": c.field,
                 "この欄が在ったラベル": [n for n in self.labels.names
                                          if c.field in self.outputs.items[n].values],
                 "基準ラベルと差が出たラベル": list(c.differs)}
                for c in self.by_result(RESULTS[3])]

    # -------------------------------------------------- 判定部分
    def judgement_bytes(self) -> bytes:
        """判定部分 = 突き合わせた結果の表。時刻・絶対パス・ホスト名は入れない。"""
        self._guard()
        lines = [f"基準ラベル\t{self.labels.base}"]
        for c in self.cells:
            lines.append(f"{c.field}\t{c.judge}\t{c.result}\t{'|'.join(c.differs)}")
        return ("\n".join(lines) + "\n").encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.judgement_bytes()).hexdigest()

    def read_condition(self) -> dict[str, str]:
        return {READ_KEYS[0]: self.outputs.root, READ_KEYS[1]: self.labels.path,
                READ_KEYS[2]: self.decl.path, READ_KEYS[3]: self.read_at,
                READ_KEYS[4]: self.host}

    def _guard(self) -> None:
        if not self.report.ok:
            raise RuntimeError("止まっているので突き合わせた結果は無い。"
                               "report.pending の理由コードを見る")


def match(outputs: Outputs, labels: Labels, decl: Decl) -> Matched:
    """宣言表の 入れる 欄だけを基準ラベルのバイト列と突き合わせ、欄ごとに 4 値に分ける。"""
    now = datetime.datetime.now().isoformat(timespec="seconds")
    host = platform.node()
    pending = list(decl.pending) + list(labels.pending)

    def made(pend: tuple[Pending, ...], cells: tuple[Cell, ...] = ()) -> Matched:
        return Matched(report=Report(not pend, pend, len(labels.names), len(decl.fields)),
                       cells=cells, labels=labels, decl=decl, outputs=outputs,
                       read_at=now, host=host)

    if pending:                      # 表が揃う前に止まる(1 欄も突き合わせない)
        return made(tuple(pending))

    base = outputs.items[labels.base]
    cells: list[Cell] = []
    for f in decl.fields:
        missing = tuple(n for n in labels.names if f.name not in outputs.items[n].values)
        if missing:
            code = STOP_REASONS[8] if f.included else STOP_REASONS[7]
            pending.append(Pending(code, f"行 {f.number}({f.name}): "
                                         + " / ".join(missing) + " の出力に無い"))
            cells.append(Cell(field=f.name, judge=f.judge,
                              result=RESULTS[2] if f.included else "", differs=(),
                              missing=missing, reason=f.reason, number=f.number))
            continue
        differs = tuple(n for n in labels.others
                        if outputs.items[n].values[f.name] != base.values[f.name])
        result = ""
        if f.included:
            result = RESULTS[1] if differs else RESULTS[0]
        cells.append(Cell(field=f.name, judge=f.judge, result=result, differs=differs,
                          missing=(), reason=f.reason, number=f.number))
    for name in outputs.union:
        if name in decl.names:
            continue
        holders = tuple(n for n in labels.names if name in outputs.items[n].values)
        differs = tuple(n for n in labels.others
                        if outputs.items[n].values.get(name) != base.values.get(name))
        pending.append(Pending(STOP_REASONS[6], f"{name}: " + " / ".join(holders)
                                                + " の出力に在るが宣言表に無い"))
        cells.append(Cell(field=name, judge="", result=RESULTS[3], differs=differs,
                          missing=tuple(n for n in labels.names if n not in holders)))
    return made(tuple(pending), tuple(cells))


def verify(root: str | Path, labels: Labels, decl: Decl) -> dict[str, object]:
    """2 回突き合わせて判定部分の sha256 を比べ、ラベル順を入れ替えた表でも同じかを見る。"""
    first = match(Outputs.load(root, labels), labels, decl)
    if not first.report.ok:
        return {"ok": False, "stage": "止まった(突き合わせの結果は返さない)", **first.counts(),
                "pending": [p.as_dict() for p in first.report.pending]}
    if not labels.swap:
        raise ReadError("ラベル表に入れ替え方(swap)が無いので verify は走らせない")
    second = match(Outputs.load(root, labels), labels, decl)
    swap = labels.swapped(labels.swap)
    third = match(Outputs.load(root, swap), swap, decl)
    pending: list[Pending] = []
    if first.sha256() != second.sha256():
        pending.append(Pending(STOP_REASONS[10], f"2 回目 {second.sha256()[:12]}"))
    if not (third.report.ok and first.sha256() == third.sha256()):
        pending.append(Pending(STOP_REASONS[11],
                               f"入れ替え方 {labels.swap} の表で {third.sha256()[:12]}"
                               if third.report.ok else
                               f"入れ替え方 {labels.swap} の表では止まった"))
    out: dict[str, object] = {"ok": not pending, "突き合わせの結果": first.verdict,
                              "突き合わせた回数": 2, "入れ替え方": labels.swap,
                              "sha256": first.sha256(), "2 回目の sha256": second.sha256(),
                              "入れ替えた表の sha256": third.sha256() if third.report.ok else ""}
    if pending:
        out["観測"] = ("同じ束から違うバイト列が出た(平均も多数決もしない。"
                       "どちらが正しいかも決めない)")
        out["pending"] = [p.as_dict() for p in pending]
    return out


# ------------------------------------------------------------------ ひな型

TEMPLATE_LABELS = [
    list(LABEL_COLUMNS),
    ["既定", "なし(基準)", "既定のまま", "合成の環境メモ(架空)L1", "既定", "逆順"],
    ["別の端末", "ホスト名と置き場所", "別の端末の作業用フォルダ", "合成の環境メモ(架空)L2", "", ""],
]
TEMPLATE_DECL = [
    list(DECL_COLUMNS),
    ["データ表の行数", "入れる", "", "合成の宣言メモ(架空)L1"],
    ["sha256", "入れる", "", "合成の宣言メモ(架空)L2"],
    ["読んだデータ表の絶対パス", "入れない", "絶対パス", "合成の宣言メモ(架空)L3"],
    ["読んだ時刻", "入れない", "時刻", "合成の宣言メモ(架空)L4"],
    ["ホスト名", "入れない", "ホスト名", "合成の宣言メモ(架空)L5"],
]
TEMPLATE_BUNDLE = {
    "既定": [("データ表の行数", "12"), ("sha256", "0" * 64),
             ("読んだデータ表の絶対パス", "(合成)置き場/データ表.csv"),
             ("読んだ時刻", "2026-10-13T09:12:08"), ("ホスト名", "合成の端末A")],
    "別の端末": [("データ表の行数", "12"), ("sha256", "0" * 64),
                 ("読んだデータ表の絶対パス", "(合成)別の置き場/データ表.csv"),
                 ("読んだ時刻", "2026-10-13T09:40:51"), ("ホスト名", "合成の端末B")],
}


def write_bundle(root: str | Path, rows: list[tuple[str, str]], label: str,
                 newline: str = "\n") -> Path:
    """出力の束の 1 ファイルを書く(欄名 → タブ → 値)。行の終わりは呼ぶ側が決める。"""
    p = Path(root) / f"{label}{SUFFIX}"
    body = newline.join(f"{k}\t{v}" for k, v in rows) + newline
    p.write_bytes(body.encode("utf-8"))
    return p


def init(dest: str | Path) -> tuple[Path, Path, Path]:
    d = Path(dest)
    bundle = d / "束"
    bundle.mkdir(parents=True, exist_ok=True)
    labels, decl = d / "ラベル表.csv", d / "判定部分.csv"
    for path, body in ((labels, TEMPLATE_LABELS), (decl, TEMPLATE_DECL)):
        with path.open("w", encoding="utf-8", newline="") as f:
            csv.writer(f, lineterminator="\n").writerows(body)
    for label, rows in TEMPLATE_BUNDLE.items():
        write_bundle(bundle, rows, label)
    return bundle, labels, decl


# ------------------------------------------------------------------ CLI

def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def build_parser() -> argparse.ArgumentParser:
    """CLI は match / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = argparse.ArgumentParser(prog="env_match", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in SUBCOMMANDS[:3]:
        p = sub.add_parser(name)
        p.add_argument("bundle")
        p.add_argument("labels")
        p.add_argument("decl")
    sub.add_parser(SUBCOMMANDS[3]).add_argument("dest")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == "init":
        bundle, labels, decl = init(a.dest)
        print(f"書いた: {bundle} / {labels} / {decl}")
        return 0
    try:
        labels, decl = Labels.load(a.labels), Decl.load(a.decl)
        if a.cmd == "verify":
            out = verify(a.bundle, labels, decl)
            _print(out)
            return 0 if out["ok"] else 3
        m = match(Outputs.load(a.bundle, labels), labels, decl)
    except ReadError as e:
        print(f"表として読めない: {e}", file=sys.stderr)
        return 2
    if not m.report.ok:
        _print({"ok": False, "stage": "止まった(突き合わせの結果は返さない)", **m.counts(),
                "対ごとの差": m.pairs(), "pending": [p.as_dict() for p in m.report.pending]})
        return 3
    body: dict[str, object] = {"ok": True, "突き合わせの結果": m.verdict, **m.counts(),
                               "対ごとの差": m.pairs()}
    if a.cmd == "match":
        body["不一致の欄"] = m.mismatches()
        body["宣言が無い欄"] = m.undeclared()
        body["sha256"] = m.sha256()
        body["読んだ条件"] = m.read_condition()
    _print(body)
    return 0 if m.verdict == RESULTS[0] else 3


if __name__ == "__main__":
    raise SystemExit(main())
