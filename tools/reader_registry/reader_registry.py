"""reader_registry — 相手先ごとに形の違う表を、宣言どおりに核の列へ読み替える部品。

同じ内容の表が、相手先ごとに別の形で出てくる。行と列が入れ替わっている、時間が 60 進の表記に
なっている、引く側の値に符号が付いていない、語が年で改名された、という具合だ。ここで核(計算と
検査)の側に「この形も読む」を足していくと核が太り、どの形のために入れた分岐か誰も言えなくなる。

この部品は読み取りの層だけを担う。**核は形の癖を 1 つも知らない**。癖の名前(値の形)は呼べる名前の
一覧としてここに登録してあるが、**どの列にどの癖があるかは宣言表の側だけ**にある。持たせていない
ものが要点になる。

  - **推測で選ぶ経路を持たない**。宣言表の match に一致した係が 0 件でも 2 件以上でも止まる
  - **優先順位の引数を持たない**(宣言の順・一致した語の多さ・似ている度合いで 1 つに絞らない)
  - **既定の値の形を持たない**(宣言表の value_form から取る。空欄の列は変換せずに止める)
  - **既定の区切り文字を持たない**(呼び出し側がカンマかタブを宣言する)
  - **書き出しを持たない**(読めた行と読み替え台帳を返すだけ。表の側のファイルはこの部品からは書かない)
  - **業種の語彙を持たない**(核の列名・原本の見出し・係の名前は全て宣言表の側にある)

入力は 2 つ。

    表        読み取り対象(CSV / TSV のテキスト)。区切りは呼び出し側が宣言する
    宣言表    読み取り係の一覧(1 係 = 1 行)。列は 7 つ

      reader_id    係の名前(重複は止まる)
      match        選定の手がかり。headers = 見出しの軸に literal で在る語の集合、
                   columns = 見出しの軸に並ぶ語の数(行がレコードなら見出し行の列数、
                   列がレコードなら見出し列の行数)
      orientation  レコードの並び(行がレコード / 列がレコード)
      column_map   核の列名 ← 原本の見出し(1 対 1)
      value_form   核の列ごとの値の形の名前(**空欄は許さない**)
      required     埋まっていなければ行を返さない核の列
      source       出典。台帳に載る

順序を固定する。① 宣言表を検査する ② 係を選ぶ ③ 読み替える。前の段で止まったら次の段には進まない。

読めたことは「宣言した対応で原本のその列をその名前に移せた」までで、対応そのものが意図どおりか・値が
制度として正しいかは判定しない。標準ライブラリのみ(csv / json / decimal / hashlib / argparse)。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

READER_COLUMNS = ("reader_id", "match", "orientation", "column_map", "value_form", "required", "source")

ROWS_ARE_RECORDS = "行がレコード"
COLUMNS_ARE_RECORDS = "列がレコード"
ORIENTATIONS = (ROWS_ARE_RECORDS, COLUMNS_ARE_RECORDS)

DELIMITERS = {"カンマ": ",", "タブ": "\t"}

# 段(どこまで進んだか)。止まった段がそのまま報告に出る
DECLARATION, SELECTION, CONVERSION, DONE = "宣言表", "選定", "読み替え", "読めた"

# 止まる理由コード(この 10 で全部)
REASONS = {
    "同じ reader_id が 2 行": "宣言表に同じ係の名前が 2 行ある。どちらの宣言か表から決まらない",
    "column_map が 1 対 1 でない": "1 つの原本の見出しを 2 つの核の列に割り当てている。移し先が決まらない",
    "value_form 空欄": "核の列に値の形の名前が無い。部品は既定の形を持たない",
    "係が 0 件": "match に一致した係が無い。最も近い係を推測で選ぶ経路は持たない",
    "係が 2 件以上": "match に一致した係が複数ある。優先順位で 1 つに絞る経路は持たない",
    "見出し行が見つからない": "宣言した原本の見出しが全部そろう行(列)が表に無い",
    "列数が宣言と違う": "データの並びの長さが見出しの軸と合わない。どの列の値か決まらない",
    "宣言した形で読めない値": "宣言した値の形で読めない値がある。別の形として読み替えはしない",
    "required の列が埋まらない": "埋まっていなければ行を返さないと宣言した核の列が空のまま",
    "選定前に読み取りを要求した": "① 宣言表 ② 選定 を通る前に、読めた行か台帳を取りに来た",
}


class RegistryError(ValueError):
    """宣言表そのものが読めない / 引数が噛み合わない(= 宣言の不備。理由コードでは扱わない)。"""


class ReadError(Exception):
    """読み替えを通っていないのに行(台帳)を取りに来た。reason に理由コードが入る。"""

    def __init__(self, message: str, reason: str = "") -> None:
        super().__init__(message)
        self.reason = reason


# ---------------------------------------------------------------- 値の形(名前で呼ぶ。既定は無い)
# 丸めの名前と振る舞いは、これまでの部品(数式を表の行に置くもの・2 つの軸から足すもの)と同じにしてある。

_NUMBER = re.compile(r"[+-]?[0-9]+(?:\.[0-9]+)?\Z")     # 半角数字だけ(\d は全角も通してしまう)
_HOUR_MINUTE = re.compile(r"([0-9]+):([0-5][0-9])\Z")
_PARENTHESES = re.compile(r"\((.*)\)\Z")
_MINUTES = Decimal(60)
_CENT = Decimal("0.01")


def _number(s: str) -> Decimal:
    t = str(s).strip().replace(",", "")
    if not _NUMBER.match(t):
        raise ValueError(f"数として読めない: {s!r}")
    try:
        return Decimal(t)
    except InvalidOperation as e:   # pragma: no cover - 形の検査を通れば起きない
        raise ValueError(f"数として読めない: {s!r}") from e


def _as_text(s: str) -> str:
    """前後の空白だけ落として、そのまま文字列として渡す。"""
    return str(s).strip()


def _as_integer(s: str) -> str:
    d = _number(s)
    if d != d.to_integral_value():
        raise ValueError(f"整数でない: {s!r}")
    return format(d, "f")


def _as_amount(s: str) -> str:
    return format(_number(s), "f")


def _round50(x: Decimal) -> Decimal:
    """50 銭以下を切り捨て、50 銭を超えたら切り上げる。"""
    i = x.to_integral_value(rounding=ROUND_FLOOR)
    return i if x - i <= Decimal("0.5") else i + 1


def _amount_with(rounding):
    return lambda s: format(rounding(_number(s)), "f")


def _sexagesimal(s: str) -> str:
    """60 進の時間の表記を 10 進にする(7:30 → 7.50)。分は 60 で割って 2 桁に丸める。"""
    m = _HOUR_MINUTE.match(str(s).strip())
    if not m:
        raise ValueError(f"時:分 の形で読めない: {s!r}")
    hours = Decimal(m.group(1)) + Decimal(m.group(2)) / _MINUTES
    return format(hours.quantize(_CENT, rounding=ROUND_HALF_UP), "f")


def _unsigned_is_negative(s: str) -> str:
    """符号を付けずに印字される引く側の値に、マイナスを付ける。"""
    d = _number(s)
    if d < 0:
        raise ValueError(f"符号が付いている(符号なしで印字される列として宣言されている): {s!r}")
    return format(d if d == 0 else -d, "f")      # 0 には符号を付けない


def _parentheses_is_negative(s: str) -> str:
    """括弧で囲んで印字される引く側の値に、マイナスを付ける((1,200) → -1200)。"""
    t = str(s).strip()
    m = _PARENTHESES.match(t)
    if m:
        d = _number(m.group(1))
        if d < 0:
            raise ValueError(f"括弧の中に符号が付いている: {s!r}")
        return format(-d, "f")
    return format(_number(t), "f")


VALUE_FORMS = {
    "文字列": _as_text,
    "整数": _as_integer,
    "金額そのまま": _as_amount,
    "金額を50銭以下切捨て": _amount_with(_round50),
    "金額を1円未満切捨て": _amount_with(lambda x: x.to_integral_value(rounding=ROUND_FLOOR)),
    "金額を円未満四捨五入": _amount_with(lambda x: x.to_integral_value(rounding=ROUND_HALF_UP)),
    "60進の時間": _sexagesimal,
    "印字は符号なし": _unsigned_is_negative,
    "括弧は負": _parentheses_is_negative,
}


def convert(value: str, form: str) -> str:
    """宣言された形で 1 つの値を読み替える。空欄は変換せず空欄のまま返す。"""
    fn = VALUE_FORMS.get(form)
    if fn is None:
        raise RegistryError(f"登録されていない値の形の名前: {form!r}(登録済 {' / '.join(VALUE_FORMS)})")
    if str(value).strip() == "":
        return ""
    return fn(value)


def sha256_of(path: "str | Path") -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- 宣言表(読み取り係の一覧)

@dataclass(frozen=True)
class Reader:
    """1 係ぶんの宣言。部品はここに書かれた名前しか知らない。"""

    reader_id: str
    headers: tuple = ()        # match.headers(見出しの軸に literal で在る語)
    columns: int = 0           # match.columns(見出しの軸に並ぶ語の数)
    orientation: str = ROWS_ARE_RECORDS
    column_map: tuple = ()     # ((核の列名, 原本の見出し), ...)
    value_form: tuple = ()     # ((核の列名, 値の形の名前), ...)
    required: tuple = ()
    source: str = ""

    @property
    def core_columns(self) -> tuple:
        return tuple(core for core, _ in self.column_map)

    @property
    def origins(self) -> tuple:
        return tuple(origin for _, origin in self.column_map)

    def origin_of(self, core: str) -> str:
        return dict(self.column_map)[core]

    def form_of(self, core: str) -> str:
        return dict(self.value_form).get(core, "")

    def as_dict(self) -> dict:
        return {"reader_id": self.reader_id,
                "match": {"headers": list(self.headers), "columns": self.columns},
                "orientation": self.orientation,
                "column_map": {core: origin for core, origin in self.column_map},
                "value_form": {core: form for core, form in self.value_form},
                "required": list(self.required), "source": self.source}


@dataclass(frozen=True)
class Registry:
    """読み取り係の宣言表。読めない宣言は RegistryError、宣言漏れは理由コードで扱う。"""

    readers: tuple = ()

    @classmethod
    def load(cls, path: "str | Path") -> "Registry":
        text = Path(path).read_text(encoding="utf-8-sig")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise RegistryError(f"宣言表が JSON として読めない: {e}") from e
        rows = data.get("readers", data) if isinstance(data, dict) else data
        if not isinstance(rows, list):
            raise RegistryError("宣言表の JSON は係の配列(または readers を持つ object)で書く")
        return cls.of(rows)

    @classmethod
    def of(cls, rows: list) -> "Registry":
        readers = []
        for i, r in enumerate(rows, 1):
            if not isinstance(r, dict):
                raise RegistryError(f"宣言表の行 {i} が object でない")
            rid = str(r.get("reader_id", "") or "").strip()
            if not rid:
                raise RegistryError(f"宣言表の行 {i} に reader_id が無い")
            match = r.get("match") or {}
            if not isinstance(match, dict):
                raise RegistryError(f"{rid} の match は headers と columns を持つ object で書く")
            headers = tuple(str(h).strip() for h in (match.get("headers") or ()) if str(h).strip())
            if not headers:
                raise RegistryError(f"{rid} の match.headers が空(選定の手がかりが無い)")
            columns = match.get("columns")
            if isinstance(columns, bool) or not isinstance(columns, int) or columns < 1:
                raise RegistryError(f"{rid} の match.columns は 1 以上の整数で書く: {columns!r}")
            orientation = str(r.get("orientation", "") or "").strip()
            if orientation not in ORIENTATIONS:
                raise RegistryError(f"{rid} の orientation は {' / '.join(ORIENTATIONS)} のどちらかで"
                                    f"書く: {orientation!r}")
            cmap = r.get("column_map") or {}
            if not isinstance(cmap, dict) or not cmap:
                raise RegistryError(f"{rid} の column_map が空(核の列名 ← 原本の見出し を書く)")
            pairs = []
            for core, origin in cmap.items():
                core, origin = str(core).strip(), str(origin or "").strip()
                if not core or not origin:
                    raise RegistryError(f"{rid} の column_map に空の名前がある: {core!r} ← {origin!r}")
                pairs.append((core, origin))
            vform = r.get("value_form") or {}
            if not isinstance(vform, dict):
                raise RegistryError(f"{rid} の value_form は 核の列名 → 形の名前 の object で書く")
            forms = []
            for core, form in vform.items():
                form = str(form or "").strip()
                if form and form not in VALUE_FORMS:
                    raise RegistryError(f"{rid} の登録されていない値の形の名前: {form!r}"
                                        f"(登録済 {' / '.join(VALUE_FORMS)})")
                forms.append((str(core).strip(), form))
            required = tuple(str(c).strip() for c in (r.get("required") or ()) if str(c).strip())
            unknown = [c for c in required if c not in {core for core, _ in pairs}]
            if unknown:
                raise RegistryError(f"{rid} の required が column_map に無い核の列を指している:"
                                    f" {' / '.join(unknown)}")
            readers.append(Reader(rid, headers, columns, orientation, tuple(pairs), tuple(forms),
                                  required, str(r.get("source", "") or "").strip()))
        if not readers:
            raise RegistryError("宣言表が空")
        return cls(tuple(readers))

    @property
    def ids(self) -> tuple:
        return tuple(r.reader_id for r in self.readers)

    def by_id(self, reader_id: str) -> "Reader | None":
        for r in self.readers:
            if r.reader_id == reader_id:
                return r
        return None


# ---------------------------------------------------------------- 読み取り対象の表

@dataclass(frozen=True)
class Sheet:
    """読み取り対象の表。この部品はテキストを受け取る(文字コードを決めるのは前の層の仕事)。"""

    rows: tuple = ()
    sha256: str = ""
    name: str = ""

    @classmethod
    def of(cls, rows: list, sha256: str = "", name: str = "") -> "Sheet":
        return cls(tuple(tuple(str(c if c is not None else "") for c in row) for row in rows),
                   sha256, name)

    @classmethod
    def parse(cls, text: str, delimiter: str, sha256: str = "", name: str = "") -> "Sheet":
        d = DELIMITERS.get(str(delimiter).strip())
        if d is None:
            raise RegistryError(f"区切りは {' / '.join(DELIMITERS)} のどちらかを宣言する:"
                                f" {delimiter!r}(既定は持たない)")
        return cls.of(list(csv.reader(str(text).splitlines(), delimiter=d)), sha256, name)

    @classmethod
    def load(cls, path: "str | Path", delimiter: str) -> "Sheet":
        p = Path(path)
        return cls.parse(p.read_text(encoding="utf-8-sig"), delimiter, sha256_of(p), p.name)


# ---------------------------------------------------------------- 結果

@dataclass(frozen=True)
class Pending:
    reason: str
    detail: str


@dataclass(frozen=True)
class Report:
    ok: bool
    stage: str
    reader_id: str = ""
    candidates: tuple = ()
    records: int = 0
    unmapped: tuple = ()
    pending: tuple = ()

    def as_dict(self) -> dict:
        return {"ok": self.ok, "stage": self.stage, "reader_id": self.reader_id,
                "candidates": list(self.candidates), "records": self.records,
                "unmapped": [u["origin"] for u in self.unmapped],
                "pending": [{"reason": p.reason, "detail": p.detail} for p in self.pending]}

    def reasons(self) -> tuple:
        return tuple(dict.fromkeys(p.reason for p in self.pending))


# ---------------------------------------------------------------- 読み取り(① 宣言表 ② 選定 ③ 読み替え)

class Reading:
    """3 段を固定の順序で通す。全部通った時だけ rows() と ledger() が返る。"""

    def __init__(self, sheet: Sheet, registry: Registry) -> None:
        self.sheet, self.registry = sheet, registry
        self._report: "Report | None" = None
        self._rows: list = []
        self._ledger: dict = {}

    # -- ① 宣言表の検査(宣言漏れ。1 つでもあれば選定に進まない) --------------

    def declaration_pending(self) -> list:
        out: list = []
        seen: dict = {}
        for r in self.registry.readers:
            seen[r.reader_id] = seen.get(r.reader_id, 0) + 1
        for rid, n in seen.items():
            if n > 1:
                out.append(Pending("同じ reader_id が 2 行", f"係『{rid}』の宣言が {n} 行ある"))
        for r in self.registry.readers:
            backwards: dict = {}
            for core, origin in r.column_map:
                backwards.setdefault(origin, []).append(core)
            for origin, cores in backwards.items():
                if len(cores) > 1:
                    out.append(Pending("column_map が 1 対 1 でない",
                                       f"{r.reader_id}: 原本の見出し『{origin}』を"
                                       f" {' / '.join(cores)} に割り当てている"))
            for core in r.core_columns:
                if not r.form_of(core):
                    out.append(Pending("value_form 空欄",
                                       f"{r.reader_id}: 核の列『{core}』に値の形の名前が無い"
                                       "(既定は持たない)"))
        return out

    # -- ② 選定(match を全部評価する。0 件でも 2 件以上でも止まる) ----------

    def _axis(self, reader: Reader, words: "set | None" = None) -> "tuple | None":
        """見出しの軸(語の並びとその位置)を探す。words を全部含む軸だけを見つける。"""
        want = set(reader.headers) if words is None else set(words)
        if reader.orientation == ROWS_ARE_RECORDS:
            for i, row in enumerate(self.sheet.rows):
                axis = tuple(c.strip() for c in row)
                if len(row) == reader.columns and want <= set(axis):
                    return i, axis
            return None
        axis = tuple((row[0].strip() if row else "") for row in self.sheet.rows)
        if len(self.sheet.rows) == reader.columns and want <= set(axis):
            return 0, axis
        return None

    def candidates(self) -> tuple:
        return tuple(r for r in self.registry.readers if self._axis(r) is not None)

    # -- ③ 読み替え(宣言した見出しがそろう軸を特定し、形の名前で読む) --------

    def _records(self, reader: Reader) -> tuple:
        """(レコードの並び, 見出しの軸, 理由コード)。レコードは (呼び名, {原本の見出し: 値})。"""
        found = self._axis(reader, set(reader.headers) | set(reader.origins))
        if found is None:
            where = "行" if reader.orientation == ROWS_ARE_RECORDS else "列"
            near = self._axis(reader)
            missing = [o for o in reader.origins if near is None or o not in near[1]]
            return (), (), [Pending("見出し行が見つからない",
                                    f"{reader.reader_id}: 宣言した見出しが全部そろう{where}が無い"
                                    f"(足りないのは {' / '.join(missing)})")]
        at, axis = found
        place: dict = {}
        for i, word in enumerate(axis):
            place.setdefault(word, i)
        pending: list = []
        records: list = []
        if reader.orientation == ROWS_ARE_RECORDS:
            for i, row in enumerate(self.sheet.rows):
                if i <= at or not any(c.strip() for c in row):
                    continue
                if len(row) != reader.columns:
                    pending.append(Pending("列数が宣言と違う",
                                           f"{i + 1} 行目の列数が {len(row)}(宣言は {reader.columns})"))
                    continue
                records.append((f"{i + 1} 行目", {w: row[place[w]] for w in place if w}))
        else:
            widths = sorted({len(row) for row in self.sheet.rows})
            if len(widths) != 1:
                pending.append(Pending("列数が宣言と違う",
                                       f"{reader.reader_id}: 行ごとに列数が違う"
                                       f"({' / '.join(str(w) for w in widths)})"))
                return (), axis, pending
            for j in range(1, widths[0]):
                records.append((f"{j + 1} 列目",
                                {w: self.sheet.rows[place[w]][j] for w in place if w}))
        return tuple(records), axis, pending

    # -- 3 段を通す ----------------------------------------------------------

    def run(self) -> Report:
        pend = self.declaration_pending()
        if pend:
            self._report = Report(False, DECLARATION, pending=tuple(pend))
            return self._report

        found = self.candidates()
        if len(found) != 1:
            reason = "係が 0 件" if not found else "係が 2 件以上"
            detail = (f"match に一致した係が {len(found)} 件"
                      + (f": {' / '.join(r.reader_id for r in found)}" if found else ""))
            self._report = Report(False, SELECTION, candidates=tuple(r.reader_id for r in found),
                                  pending=(Pending(reason, detail),))
            return self._report

        reader = found[0]
        records, axis, pend = self._records(reader)
        rows: list = []
        for label, raw in records:
            out: dict = {}
            for core, origin in reader.column_map:
                try:
                    out[core] = convert(raw.get(origin, ""), reader.form_of(core))
                except ValueError as e:
                    out[core] = ""
                    pend.append(Pending("宣言した形で読めない値",
                                        f"{label}の『{origin}』({reader.form_of(core)}): {e}"))
            for core in reader.required:
                if out.get(core, "") == "":
                    pend.append(Pending("required の列が埋まらない",
                                        f"{label}の核の列『{core}』が空"
                                        f"(原本の見出し『{reader.origin_of(core)}』)"))
            rows.append(out)

        unmapped = tuple({"origin": w, "values": [raw.get(w, "") for _, raw in records]}
                         for w in axis if w and w not in set(reader.origins))
        if pend:
            self._report = Report(False, CONVERSION, reader.reader_id,
                                  (reader.reader_id,), len(records), unmapped, tuple(pend))
            return self._report

        self._rows = rows
        self._ledger = {
            "reader_id": reader.reader_id, "orientation": reader.orientation,
            "source": reader.source, "sheet": self.sheet.name, "sha256": self.sheet.sha256,
            "records": len(rows),
            "columns": [{"core": core, "origin": origin, "value_form": reader.form_of(core),
                         "required": core in reader.required} for core, origin in reader.column_map],
            "unmapped": [dict(u) for u in unmapped],
        }
        self._report = Report(True, DONE, reader.reader_id, (reader.reader_id,), len(rows), unmapped)
        return self._report

    @property
    def report(self) -> Report:
        if self._report is None:
            raise ReadError("3 段を通る前に結果を見に来た", "選定前に読み取りを要求した")
        return self._report

    def rows(self) -> list:
        """3 段を全部通った時だけ、核の列仕様に合う行を返す(ファイルは書かない)。"""
        r = self.report
        if not r.ok:
            raise ReadError(f"読み替えが通っていないので渡さない({r.stage}で止まった)",
                            r.reasons()[0] if r.pending else r.stage)
        return [dict(row) for row in self._rows]

    def ledger(self) -> dict:
        """読み替え台帳(原本の見出し → 核の列名 / 形の名前 / unmapped / 原本の sha256)。"""
        r = self.report
        if not r.ok:
            raise ReadError(f"読み替えが通っていないので台帳も出さない({r.stage}で止まった)",
                            r.reasons()[0] if r.pending else r.stage)
        return json.loads(json.dumps(self._ledger, ensure_ascii=False))


def select(sheet: Sheet, registry: Registry) -> tuple:
    """① 宣言表 ② 選定 だけを通して、一致した係の名前を返す(読み替えはしない)。"""
    reading = Reading(sheet, registry)
    if reading.declaration_pending():
        return ()
    return tuple(r.reader_id for r in reading.candidates())


def read(sheet: Sheet, registry: Registry) -> Reading:
    """3 段を通した Reading を返す(通れば rows() と ledger() が使える)。"""
    reading = Reading(sheet, registry)
    reading.run()
    return reading


# ---------------------------------------------------------------- CLI

def _build(args) -> Reading:
    return read(Sheet.load(args.sheet, args.delimiter), Registry.load(args.registry))


def _cli_select(args) -> int:
    reading = Reading(Sheet.load(args.sheet, args.delimiter), Registry.load(args.registry))
    pend = reading.declaration_pending()
    if pend:
        print(json.dumps({"ok": False, "stage": DECLARATION, "candidates": [],
                          "pending": [{"reason": p.reason, "detail": p.detail} for p in pend]},
                         ensure_ascii=False))
        return 3
    found = [r.reader_id for r in reading.candidates()]
    ok = len(found) == 1
    out = {"ok": ok, "stage": DONE if ok else SELECTION, "candidates": found}
    if not ok:
        reason = "係が 0 件" if not found else "係が 2 件以上"
        out["pending"] = [{"reason": reason, "detail": REASONS[reason]}]
    print(json.dumps(out, ensure_ascii=False))
    return 0 if ok else 3


def _cli_read(args) -> int:
    reading = _build(args)
    r = reading.report
    out = r.as_dict()
    if r.ok:
        rows = reading.rows()
        out["columns"] = list(rows[0]) if rows else []
        out["rows"] = rows
    print(json.dumps(out, ensure_ascii=False))
    return 0 if r.ok else 3


def _cli_ledger(args) -> int:
    reading = _build(args)
    r = reading.report
    if not r.ok:
        print(json.dumps(r.as_dict(), ensure_ascii=False))
        return 3
    led = reading.ledger()
    if args.format == "csv":
        w = csv.DictWriter(sys.stdout, fieldnames=["core", "origin", "value_form", "required"],
                           lineterminator="\n")
        w.writeheader()
        w.writerows(led["columns"])
    else:
        print(json.dumps(led, ensure_ascii=False))
    return 0


def _cli_init(args) -> int:
    p = Path(args.path)
    if p.exists():
        raise RegistryError(f"すでにある: {p}(上書きしない)")
    template = [{"reader_id": "係の名前(相手先の呼び名など)",
                 "match": {"headers": ["見出しの軸に literal で在る語", "もう 1 つ"], "columns": 8},
                 "orientation": ORIENTATIONS[0],
                 "column_map": {"核の列名": "原本の見出し"},
                 "value_form": {"核の列名": f"{' / '.join(VALUE_FORMS)} のどれか(空欄は止まる)"},
                 "required": ["核の列名"], "source": "出典"}]
    p.write_text(json.dumps({"readers": template}, ensure_ascii=False, indent=1) + "\n",
                 encoding="utf-8")
    print(json.dumps({"ok": True, "wrote": str(p), "columns": list(READER_COLUMNS),
                      "orientations": list(ORIENTATIONS), "value_forms": list(VALUE_FORMS)},
                     ensure_ascii=False))
    return 0


def main(argv: "list | None" = None) -> int:
    p = argparse.ArgumentParser(
        description="形の違う表を宣言どおりに核の列へ読み替える(推測で係を選ぶ経路は持たない)")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, help_text, fn in (("select", "係を選ぶ(読み替えはしない)", _cli_select),
                                ("read", "読み替えて核の列仕様の行を出す", _cli_read),
                                ("ledger", "読み替え台帳を出す(JSON / CSV)", _cli_ledger)):
        s = sub.add_parser(name, help=help_text)
        s.add_argument("sheet", help="読み取り対象の表(CSV / TSV)")
        s.add_argument("--registry", required=True, help="読み取り係の宣言表(JSON)")
        s.add_argument("--delimiter", required=True, choices=tuple(DELIMITERS),
                       help="区切り(既定は持たない)")
        if name == "ledger":
            s.add_argument("--format", choices=("json", "csv"), default="json")
        s.set_defaults(func=fn)
    i = sub.add_parser("init", help="宣言表のひな型を書き出す")
    i.add_argument("path")
    i.set_defaults(func=_cli_init)
    args = p.parse_args(argv)
    try:
        return args.func(args)
    except (RegistryError, ReadError) as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except OSError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
