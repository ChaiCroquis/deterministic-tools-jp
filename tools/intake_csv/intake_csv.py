"""intake_csv — 取込用 CSV を「書いて、読み戻して、元データと突き合わせる」書き出し部品。

取込側が要求する形(cp932 / CRLF / クォート無し)で CSV を書くと、書いた瞬間には気づけない壊れ方をする。
値の中のカンマで列がずれ、cp932 に無い文字が置換文字に化け、書けても読み戻すと別の文字になる字がある。
この部品は次の順で動く。判断は 1 つも入れない。

  1. 列仕様(列の順・見出し・型・桁・ゼロ埋め・空を許すか・合計を取るか)を 1 つの表で持つ
  2. 値を検査する。仕様と両立しない値は「判断待ち」として理由コード付きで返す(クォートで逃がさない)
  3. 判断待ちが 1 件でもあれば、出力ファイルを作らない(書きかけを取込側に渡さない)
  4. 書いたら、その作業ファイルを取込側と同じ読み方で読み戻し、件数・指定列の合計・全セルの文字列を突き合わせる
  5. 1 つでも合わなければ作業ファイルを消して、差の一覧(行番号・列名・元の値・読み戻した値)を返して止める
  6. 差の原因は推定しない。どちらが正しいとも決めない

依存なし(標準ライブラリの csv / decimal / argparse のみ)。
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Sequence

# 取込側が要求する形。ここは設定にしない(揺らすと読み戻しの意味が無くなる)
ENCODING = "cp932"
NEWLINE = "\r\n"
DELIM = ","
QUOTE = '"'

KINDS = ("文字列", "整数", "金額", "コード")
SPACES = " \t　"

REASONS = {
    "必要な値が空": "空を許さない列が空。空欄で埋めると取込側では別の意味になる",
    "数字でない": "整数・金額・コードの列に、符号と数字以外が入っている",
    "桁あふれ": "列仕様の桁を超えている。切り詰めると別の値になる",
    "改行が値の中にある": "1 行 1 レコードの形と両立しない",
    "引用符が値の中にある": "クォート無しの要求と両立しない",
    "区切り文字が値の中にある": "クォート無しで書くと列がずれる。クォートで逃がすと取込側が読めない",
    "cp932 に無い文字": "cp932 で表せない。置換文字で書き進めると元の字が失われる",
    "書いて読むと別の文字になる": "cp932 に書けるが、読み戻すと別の符号位置の字になる(多対一の対応)",
}


class SpecError(Exception):
    """列仕様とデータが噛み合っていない(列が足りない・仕様そのものが壊れている)。"""


@dataclass(frozen=True)
class Column:
    """列仕様 1 行。桁 0 = 制限なし。"""
    name: str
    kind: str = "文字列"
    width: int = 0
    zero_pad: bool = False
    needed: bool = True
    total: bool = False

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise SpecError(f"型が表に無い: {self.kind}(使えるのは {' / '.join(KINDS)})")
        if self.zero_pad and not self.width:
            raise SpecError(f"ゼロ埋めには桁が要る: {self.name}")
        if self.total and self.kind not in ("整数", "金額"):
            raise SpecError(f"合計を取れるのは整数と金額の列だけ: {self.name}")


@dataclass(frozen=True)
class Spec:
    """列仕様の表。出力の列の順はこの表の順で、表に無い列は書かない。"""
    columns: tuple[Column, ...]

    def __post_init__(self) -> None:
        names = [c.name for c in self.columns]
        if not names:
            raise SpecError("列仕様が空")
        if len(set(names)) != len(names):
            raise SpecError("列仕様に同じ見出しが 2 つある")

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.columns)

    @property
    def total_names(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.columns if c.total)

    @classmethod
    def from_rows(cls, rows: Iterable[dict[str, str]]) -> "Spec":
        """列仕様を表(見出し, 型, 桁, ゼロ埋め, 空を許す, 合計)から作る。"""
        cols = []
        for i, r in enumerate(rows, 1):
            try:
                name = (r["見出し"] or "").strip()
                width = int((r.get("桁") or "0").strip() or 0)
                cols.append(Column(name, (r["型"] or "文字列").strip(), width,
                                   _yes(r.get("ゼロ埋め")), not _yes(r.get("空を許す")), _yes(r.get("合計"))))
            except KeyError as e:
                raise SpecError(f"列仕様の表に {e} の欄が無い") from e
            except ValueError as e:
                raise SpecError(f"列仕様 {i} 行目の桁が数でない: {e}") from e
        return cls(tuple(cols))

    @classmethod
    def from_csv(cls, path: str | os.PathLike[str]) -> "Spec":
        with open(path, encoding="utf-8-sig", newline="") as f:
            return cls.from_rows(list(csv.DictReader(f)))


def _yes(v: str | None) -> bool:
    return (v or "").strip() in ("1", "○", "はい", "yes", "true", "TRUE")


@dataclass(frozen=True)
class Pending:
    """機械では書けない値。原因は推定せず、見つけた事実だけを返す。"""
    row: int
    column: str
    value: str
    reason: str
    note: str = ""
    detail: str = ""


@dataclass(frozen=True)
class Diff:
    """元データと読み戻しの差。row 0 = 件数・合計・見出しなど行に紐づかない差。"""
    row: int
    column: str
    original: str
    readback: str


@dataclass(frozen=True)
class Result:
    path: str
    written: bool
    count: int = 0
    totals: dict[str, str] = field(default_factory=dict)
    pending: tuple[Pending, ...] = ()
    diffs: tuple[Diff, ...] = ()
    dropped_columns: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.written and not self.pending and not self.diffs


# ---- 値を出力の形にする(勝手に変えない) ------------------------------------------------------

def render(col: Column, value: str | None) -> str:
    """列仕様に従って出力する文字列を作る。することはゼロ埋めと前後の空白落としだけ。

    正規化(NFKC)はしない。半角カナを全角に寄せたり、波ダッシュを付け替えたりもしない。
    値を勝手に書き換えないので、読み戻したときにここで作った文字列と一致するはず、という形にできる。
    """
    s = "" if value is None else str(value).strip(SPACES)
    if col.zero_pad and s and not s.startswith("-") and len(s) < col.width:
        s = s.rjust(col.width, "0")
    return s


def _decimal(s: str) -> Decimal | None:
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def _bad_char(s: str) -> tuple[str, str]:
    """cp932 で書けない字、または書けても読み戻すと別の字になる字を 1 つ返す。(理由, 字)。"""
    for ch in s:
        try:
            back = ch.encode(ENCODING).decode(ENCODING)
        except UnicodeEncodeError:
            return "cp932 に無い文字", ch
        if back != ch:
            return "書いて読むと別の文字になる", ch
    return "", ""


def check_value(col: Column, value: str, row: int) -> Pending | None:
    """1 つの値を検査する。見つけた理由を 1 つだけ返す(直す順に並べてある)。"""
    def pend(reason: str, detail: str = "") -> Pending:
        return Pending(row, col.name, value, reason, REASONS[reason], detail)

    if not value:
        return pend("必要な値が空") if col.needed else None
    if col.kind in ("整数", "金額", "コード"):
        body = value[1:] if value[0] == "-" else value
        if col.kind == "コード":
            if not (body.isascii() and body.isdigit()):
                return pend("数字でない", value)
        elif _decimal(value) is None or not value.isascii():
            return pend("数字でない", value)
    if col.width and len(value) > col.width:
        return pend("桁あふれ", f"{len(value)} 桁 > {col.width} 桁")
    if "\n" in value or "\r" in value:
        return pend("改行が値の中にある")
    if QUOTE in value:
        return pend("引用符が値の中にある", QUOTE)
    if DELIM in value:
        return pend("区切り文字が値の中にある", DELIM)
    reason, ch = _bad_char(value)
    if reason:
        return pend(reason, f"{ch} (U+{ord(ch):04X})")
    return None


def check_rows(spec: Spec, rows: Sequence[dict[str, str]]) -> tuple[list[list[str]], list[Pending], list[str]]:
    """全行を検査して (出力する行, 判断待ち, 仕様に無くて書かない列) を返す。列が足りなければ止まる。"""
    seen: set[str] = set()
    for r in rows:
        seen |= set(r)
    missing = [c.name for c in spec.columns if c.name not in seen] if rows else []
    if missing:
        raise SpecError(f"列がデータに無い: {', '.join(missing)}(空欄で埋めない)")
    dropped = sorted(seen - set(spec.names))
    out: list[list[str]] = []
    pending: list[Pending] = []
    for i, r in enumerate(rows, 1):
        line = []
        for col in spec.columns:
            v = render(col, r.get(col.name))
            p = check_value(col, v, i)
            if p:
                pending.append(p)
            line.append(v)
        out.append(line)
    return out, pending, dropped


def totals_of(spec: Spec, lines: Sequence[Sequence[str]]) -> dict[str, Decimal]:
    """合計を取る列の合計。数でない値は足さずに飛ばす(検査側が拾う)。"""
    idx = {c.name: i for i, c in enumerate(spec.columns)}
    out: dict[str, Decimal] = {}
    for name in spec.total_names:
        s = Decimal(0)
        for line in lines:
            d = _decimal(line[idx[name]])
            if d is not None:
                s += d
        out[name] = s
    return out


# ---- 書く / 読み戻す / 突き合わせる ----------------------------------------------------------

def read_back(path: str | os.PathLike[str]) -> list[list[str]]:
    """取込側と同じ読み方をする。cp932 で読み、CRLF で行に切り、カンマで列に切るだけ。

    クォートは解釈しない(取込側がクォート無しを要求しているので、引用符は値の一部として見える)。
    """
    text = Path(path).read_bytes().decode(ENCODING)   # errors 指定なし = 読めなければ例外で止まる
    if not text:
        return []
    if not text.endswith(NEWLINE):
        raise ValueError("行末が CRLF で終わっていない")
    return [line.split(DELIM) for line in text.split(NEWLINE)[:-1]]


def verify(path: str | os.PathLike[str], spec: Spec, lines: Sequence[Sequence[str]]) -> list[Diff]:
    """出力ファイルを読み戻して、見出し・件数・合計・全セルを元データと突き合わせる。"""
    got = read_back(path)
    if not got:
        return [Diff(0, "件数", str(len(lines)), "0")]
    diffs: list[Diff] = []
    head, body = got[0], got[1:]
    if head != list(spec.names):
        diffs.append(Diff(0, "見出し", DELIM.join(spec.names), DELIM.join(head)))
    if len(body) != len(lines):
        diffs.append(Diff(0, "件数", str(len(lines)), str(len(body))))
    for i, (want, have) in enumerate(zip(lines, body), 1):
        if len(have) != len(want):
            diffs.append(Diff(i, "列数", str(len(want)), str(len(have))))
        for col, a, b in zip(spec.columns, want, have):
            if a != b:
                diffs.append(Diff(i, col.name, a, b))
    want_totals = totals_of(spec, lines)
    have_totals = totals_of(spec, [r for r in body if len(r) == len(spec.columns)])
    for name, w in want_totals.items():
        h = have_totals.get(name, Decimal(0))
        if w != h:
            diffs.append(Diff(0, name, str(w), str(h)))
    return diffs


def _write_lines(path: str | os.PathLike[str], spec: Spec, lines: Sequence[Sequence[str]]) -> None:
    """取込側が要求する形で書くだけの段。クォートは使わず、cp932 で書けない字は例外で止まる。"""
    with open(path, "w", encoding=ENCODING, errors="strict", newline="") as f:
        w = csv.writer(f, delimiter=DELIM, quoting=csv.QUOTE_NONE, quotechar=None,
                       escapechar=None, lineterminator=NEWLINE)
        w.writerow(spec.names)
        w.writerows(lines)


def write(path: str | os.PathLike[str], spec: Spec, rows: Sequence[dict[str, str]]) -> Result:
    """検査 → 作業ファイルに書く → 読み戻して突き合わせる → 通ったものだけ本来の名前にする。

    判断待ちが 1 件でもあれば何も書かない。突合で差が出たら作業ファイルを消す。
    どちらの場合も、取込側に渡るファイルは作られない。
    """
    dest = Path(path)
    lines, pending, dropped = check_rows(spec, rows)
    if pending:
        return Result(str(dest), False, pending=tuple(pending), dropped_columns=tuple(dropped))
    tmp = dest.with_name(dest.name + ".tmp")
    _write_lines(tmp, spec, lines)
    diffs = verify(tmp, spec, lines)
    if diffs:
        tmp.unlink()
        return Result(str(dest), False, diffs=tuple(diffs), dropped_columns=tuple(dropped))
    os.replace(tmp, dest)
    return Result(str(dest), True, len(lines), {k: str(v) for k, v in totals_of(spec, lines).items()},
                  dropped_columns=tuple(dropped))


def naive_write(path: str | os.PathLike[str], spec: Spec, rows: Sequence[dict[str, str]]) -> int:
    """比較用。現場でよく見る書き出し方をそのまま書く(検査なし・読み戻しなし)。

    cp932 に無い字は置換文字(?)に化け、値の中のカンマはクォートで逃がす。
    どちらも書いた側では例外にならないので、気づけるのは取込の後になる。
    """
    lines, _pending, _dropped = check_rows(spec, rows)
    with open(path, "w", encoding=ENCODING, errors="replace", newline="") as f:
        w = csv.writer(f, delimiter=DELIM, lineterminator=NEWLINE)   # 既定 = QUOTE_MINIMAL
        w.writerow(spec.names)
        w.writerows(lines)
    return len(lines)


# ---- CLI --------------------------------------------------------------------------------------

def _read_source(path: str) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _show(value: str) -> str:
    """1 行 1 件で表示するため、値の中の改行とタブだけ見える形にする(値そのものは変えない)。"""
    return value.replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="intake_csv",
                                 description="取込用 CSV を書いて、読み戻して、元データと突き合わせる")
    ap.add_argument("source", help="元データ(UTF-8 の CSV)")
    ap.add_argument("dest", nargs="?", help="出力先(cp932 / CRLF / クォート無し)。--check のときは不要")
    ap.add_argument("--spec", required=True, help="列仕様の表(CSV)")
    ap.add_argument("--check", action="store_true", help="検査だけして書かない")
    ap.add_argument("--naive", action="store_true", help="比較用: 検査も読み戻しもせずに書く")
    a = ap.parse_args(argv)
    try:
        spec = Spec.from_csv(a.spec)
        rows = _read_source(a.source)
        if a.check:
            _lines, pending, dropped = check_rows(spec, rows)
            for p in pending:
                print(f"{p.row}\t{p.column}\t{p.reason}\t{_show(p.value)}\t{_show(p.detail)}")
            for d in dropped:
                print(f"仕様に無い列(書かない): {d}", file=sys.stderr)
            print(f"検査 {len(rows)} 行 / 判断待ち {len(pending)} 件", file=sys.stderr)
            return 3 if pending else 0
        if not a.dest:
            ap.error("出力先が要る(検査だけなら --check)")
        if a.naive:
            n = naive_write(a.dest, spec, rows)
            print(f"書いた {n} 行(検査なし・読み戻しなし)", file=sys.stderr)
            return 0
        r = write(a.dest, spec, rows)
    except SpecError as e:
        print(f"列仕様: {e}", file=sys.stderr)
        return 2
    except (OSError, UnicodeDecodeError, ValueError) as e:
        print(f"読み書き: {e}", file=sys.stderr)
        return 2
    for p in r.pending:
        print(f"{p.row}\t{p.column}\t{p.reason}\t{_show(p.value)}\t{_show(p.detail)}")
    for d in r.diffs:
        print(f"{d.row or '-'}\t{d.column}\t突合で差\t{_show(d.original)}\t{_show(d.readback)}")
    for c in r.dropped_columns:
        print(f"仕様に無い列(書かない): {c}", file=sys.stderr)
    if r.ok:
        t = " / ".join(f"{k} {v}" for k, v in r.totals.items())
        print(f"書いて読み戻して一致: {r.count} 行" + (f" / {t}" if t else ""), file=sys.stderr)
        return 0
    print(f"書かなかった: 判断待ち {len(r.pending)} 件 / 突合の差 {len(r.diffs)} 件", file=sys.stderr)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
