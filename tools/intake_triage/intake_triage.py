"""intake_triage — 取込先の仕様に入るかを、1 件も直さずに行ごと 3 つへ仕分ける部品。

取込先に渡す前に、行が仕様に入るかを見たい。ここで機械が「たぶんこう直せばいい」まで踏み込むと、
直した跡が残らないまま元の表と合わなくなる。だからこの部品は **値を 1 つも書き換えない**。
列ごとの違反を 3 値に分け、行の分類はその最悪値で決め、どの行のどの列が宣言とどう違うかだけを返す。

3 値の名前(そのまま通る / 宣言された直し方で通る / 人が決めるしかない)が線で、**2 本目と 3 本目の
境界は値ではなく宣言の側で決まる**。同じ違反でも、それを覆うと宣言された直し方の名前が仕様表に在れば
2 本目に入り、無ければ 3 本目に落ちる。だから「機械が決めてよい境界」は仕様表を書く人が動かすもので、
部品は自分で広げない。

持たせていないものが規律になっている。

  - **値を書き換える経路を持たない**(返すのは適用すべき直し方の名前と、対象の列と、現在の値だけ)
  - **推測で最も近い値に寄せる経路を持たない**。閾値で自動的に通す引数も持たない
  - **既定の型と既定の値域を持たない**(仕様表から取る。空欄の列は評価せずに止まる)
  - **部分出力の経路を持たない**(人が決めるしかない行が 1 件でもあれば、通る行だけを集めて渡さない)
  - **書き出しを持たない**(ファイルはこの部品からは開かない)
  - **取り込める率を単独で返さない**(3 分類の件数と、分母に何を含めたかを必ず一緒に返す)
  - **取込先の製品や分野の語彙を持たない**(列名・型の名前・値域・直し方の名前は全て仕様表の側にある)

入力は 2 つ。

    行        仕分ける対象。列名 → 値 の並び(前の工程が核の列仕様で渡してくる形)
    仕様表    取込先の宣言(1 列 = 1 行)。欄は 6 つ

      column     列名(重複は止まる)
      type       型の名前(**空欄は許さない**)
      domain     許容する値。集合 / 範囲 / 長さ / 長さ上限 / 形 / 制限なし(**空欄は許さない**)
      required   埋まっていなければ違反とする列に印を付ける
      repair     その列の違反を覆うと宣言する直し方の名前(空欄可。**空欄なら 3 本目に落ちる**)
      source     出典。報告に載る

順序を固定する。① 仕様表を検査する ② 行と仕様表を突き合わせる ③ 列ごとに判定して行を分類する。
前の段で止まったら次の段には進まない。

仕分けたことは「宣言された型と値域に照らして行がどこに落ちるか」までで、取込先が実際にその行を
受け取るか・値が業務として正しいかは判定しない。標準ライブラリのみ(csv / json / decimal / hashlib /
argparse / datetime)。
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

SPEC_COLUMNS = ("column", "type", "domain", "required", "repair", "source")

# 型の名前(この 5 つだけ。既定は無い)
TEXT, INTEGER, AMOUNT, CODE, DATE = "文字列", "整数", "金額", "コード", "日付"
TYPES = (TEXT, INTEGER, AMOUNT, CODE, DATE)

# 3 本の線。行の分類はその行の列の最悪値で決まる
PASSES, REPAIRABLE, JUDGMENT = "そのまま通る", "宣言された直し方で通る", "人が決めるしかない"
CLASSES = (PASSES, REPAIRABLE, JUDGMENT)
WORST = {PASSES: 0, REPAIRABLE: 1, JUDGMENT: 2}

# 段(どこまで進んだか)。止まった段がそのまま報告に出る
SPEC, MATCH, TRIAGE, DONE = "仕様表", "突き合わせ", "仕分け", "仕分けた"

# 列ごとの違反の名前(この 7 つで全部)
VIOLATIONS = {
    "必要な値が空": "埋まっていなければ違反と宣言した列が空。空欄で埋めると取込先では別の意味になる",
    "型と違う": "宣言した型の形で読めない(半角の数字以外の字・桁区切りのカンマ・符号以外の記号を含む)",
    "集合の外": "宣言した集合に無い値",
    "範囲の外": "宣言した範囲の外(引く側の列に正の数が入っている場合もここ)",
    "長さが違う": "宣言した長さとちょうど一致しない(先頭のゼロが落ちた場合もここ)",
    "桁あふれ": "宣言した長さの上限を超えている。切り詰めると別の値になる",
    "形が違う": "宣言した形で書かれていない(区切りの有無・暦に無い日)",
}

# 直し方の名前 → その名前が「覆う」と宣言している違反。
# **部品はここで値を書き換えない**。覆う違反の一覧を持つだけで、実際に直すのは人か後の工程。
REPAIRS = {
    "半角の数字に直す": ("型と違う",),
    "桁区切りのカンマを外す": ("型と違う",),
    "括弧は負": ("型と違う", "範囲の外"),
    "印字は符号なし": ("範囲の外",),
    "先頭をゼロで埋める": ("長さが違う",),
    "空欄を 0 とみなす": ("必要な値が空",),
    "区切りを外して 8 桁に": ("形が違う",),
    "年の表記を宣言した形に直す": ("形が違う",),
}

# 止まる理由コード(この 8 つで全部)
REASONS = {
    "型の名前が空欄": "列に型の名前が無い。部品は既定の型を持たない",
    "値域の宣言が空欄": "列に許容する値の宣言が無い。制限を付けないなら『制限なし』と書く",
    "仕様表に無い列が行に在る": "仕様表が知らない列が行に在る。どの宣言で判定するか決まらない",
    "同じ column が仕様表に 2 行": "同じ列の宣言が 2 行ある。どちらの宣言か表から決まらない",
    "repair の名前が辞書に無い": "宣言された直し方の名前を部品が知らない。覆う違反が決まらない",
    "必須列が仕様表に無い": "識別子の列が仕様表に無い、または埋まっていなければ違反とする列の宣言が 1 つも無い",
    "行の識別子が重複": "同じ識別子の行が 2 行ある。どの行の話か報告で決まらない",
    "判定前に出力を要求した": "① 仕様表 ② 突き合わせ ③ 仕分け を通る前に、結果か渡す行を取りに来た",
}

# 値域の宣言の書き方
ANY = "制限なし"
SET, RANGE, LENGTH, LENGTH_MAX, FORM = "集合", "範囲", "長さ", "長さ上限", "形"
DOMAIN_KINDS = (SET, RANGE, LENGTH, LENGTH_MAX, FORM)

# 日付の形の名前(この 3 つだけ)
DATE_FORMS = {
    "YYYYMMDD": re.compile(r"\A([0-9]{4})([0-9]{2})([0-9]{2})\Z"),
    "YYYY-MM-DD": re.compile(r"\A([0-9]{4})-([0-9]{2})-([0-9]{2})\Z"),
    "YYYY/MM/DD": re.compile(r"\A([0-9]{4})/([0-9]{2})/([0-9]{2})\Z"),
}

# 型の形(\d は半角以外の数字も通してしまうので、半角の文字種を明示する)
_INTEGER = re.compile(r"\A[+-]?[0-9]+\Z")
_AMOUNT = re.compile(r"\A[+-]?[0-9]+(?:\.[0-9]+)?\Z")
_CODE = re.compile(r"\A[0-9]+\Z")
_DATE_CHARS = re.compile(r"\A[0-9/-]+\Z")

# 型ごとに書ける値域の種類(噛み合わない宣言は仕様表の不備として終了コード 2 で返す)
DOMAIN_FOR_TYPE = {
    TEXT: (ANY, SET, LENGTH, LENGTH_MAX),
    CODE: (ANY, SET, LENGTH, LENGTH_MAX),
    INTEGER: (ANY, SET, RANGE),
    AMOUNT: (ANY, SET, RANGE),
    DATE: (FORM,),
}

TRUE_MARKS = {"○", "◯", "o", "O", "1", "はい", "true", "True", "TRUE", "yes", "Yes"}


class SpecError(ValueError):
    """仕様表そのものが読めない / 引数が噛み合わない(= 宣言の不備。理由コードでは扱わない)。"""


class TriageError(Exception):
    """仕分けを通っていないのに結果か渡す行を取りに来た。reason に理由コードが入る。"""

    def __init__(self, message: str, reason: str = "") -> None:
        super().__init__(message)
        self.reason = reason


def sha256_of(path: "str | Path") -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _marked(value: str) -> bool:
    return str(value).strip() in TRUE_MARKS


def _number(s: str) -> Decimal:
    try:
        return Decimal(str(s).strip())
    except InvalidOperation as e:   # pragma: no cover - 型の検査を通れば起きない
        raise SpecError(f"数として読めない: {s!r}") from e


# ---------------------------------------------------------------- 値域の宣言

@dataclass(frozen=True)
class Domain:
    """許容する値の宣言。空欄は許さない(既定は持たない)。"""

    kind: str
    text: str = ""
    values: tuple = ()
    low: "Decimal | None" = None
    high: "Decimal | None" = None
    length: int = 0
    form: str = ""

    @classmethod
    def parse(cls, text: str) -> "Domain":
        t = str(text or "").strip().replace("\uff1a", ":")
        if t == ANY:
            return cls(ANY, t)
        if ":" not in t:
            raise SpecError(f"値域の宣言は『{ANY}』か『種類: 中身』で書く: {text!r}"
                            f"(種類は {' / '.join(DOMAIN_KINDS)})")
        kind, rest = (x.strip() for x in t.split(":", 1))
        if kind not in DOMAIN_KINDS:
            raise SpecError(f"知らない値域の種類: {kind!r}"
                            f"(書けるのは {ANY} / {' / '.join(DOMAIN_KINDS)})")
        if kind == SET:
            values = tuple(v.strip() for v in rest.split("|") if v.strip())
            if not values:
                raise SpecError(f"集合が空: {text!r}(値を | で区切って並べる)")
            return cls(SET, t, values=values)
        if kind == RANGE:
            if ".." not in rest:
                raise SpecError(f"範囲は『下限..上限』で書く: {text!r}")
            lo, hi = (x.strip() for x in rest.split("..", 1))
            if not (_AMOUNT.match(lo) and _AMOUNT.match(hi)):
                raise SpecError(f"範囲の下限と上限は半角の数で書く: {text!r}")
            low, high = Decimal(lo), Decimal(hi)
            if low > high:
                raise SpecError(f"範囲の下限が上限より大きい: {text!r}")
            return cls(RANGE, t, low=low, high=high)
        if kind in (LENGTH, LENGTH_MAX):
            if not re.fullmatch(r"[0-9]+", rest) or int(rest) < 1:
                raise SpecError(f"{kind} は 1 以上の半角の整数で書く: {text!r}")
            return cls(kind, t, length=int(rest))
        if rest not in DATE_FORMS:
            raise SpecError(f"知らない形の名前: {rest!r}(書けるのは {' / '.join(DATE_FORMS)})")
        return cls(FORM, t, form=rest)


def _type_violation(value: str, type_name: str) -> str:
    if type_name == TEXT:
        return ""
    if type_name == INTEGER:
        return "" if _INTEGER.match(value) else "型と違う"
    if type_name == AMOUNT:
        return "" if _AMOUNT.match(value) else "型と違う"
    if type_name == CODE:
        return "" if _CODE.match(value) else "型と違う"
    return "" if _DATE_CHARS.match(value) else "型と違う"


def _domain_violation(value: str, domain: Domain) -> str:
    if domain.kind == ANY:
        return ""
    if domain.kind == SET:
        return "" if value in domain.values else "集合の外"
    if domain.kind == RANGE:
        d = _number(value)
        return "" if domain.low <= d <= domain.high else "範囲の外"
    if domain.kind == LENGTH:
        return "" if len(value) == domain.length else "長さが違う"
    if domain.kind == LENGTH_MAX:
        return "" if len(value) <= domain.length else "桁あふれ"
    m = DATE_FORMS[domain.form].match(value)
    if not m:
        return "形が違う"
    try:
        datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return "形が違う"
    return ""


# ---------------------------------------------------------------- 仕様表

@dataclass(frozen=True)
class Column:
    """1 列ぶんの宣言。部品はここに書かれた名前しか知らない。"""

    column: str
    type_name: str = ""
    domain: "Domain | None" = None
    domain_text: str = ""
    required: bool = False
    repair: str = ""
    source: str = ""

    @property
    def covers(self) -> tuple:
        """宣言された直し方が覆うと言っている違反。宣言が無ければ空(= 3 本目に落ちる)。"""
        return REPAIRS.get(self.repair, ()) if self.repair else ()

    def as_dict(self) -> dict:
        return {"column": self.column, "type": self.type_name, "domain": self.domain_text,
                "required": self.required, "repair": self.repair,
                "covers": list(self.covers), "source": self.source}


@dataclass(frozen=True)
class Spec:
    """取込先の仕様表。読めない宣言は SpecError、宣言漏れは理由コードで扱う。"""

    columns: tuple = ()
    name: str = ""
    sha256: str = ""

    @classmethod
    def of(cls, rows: list) -> "Spec":
        out = []
        for i, r in enumerate(rows, 1):
            if not isinstance(r, dict):
                raise SpecError(f"仕様表の行 {i} が object でない")
            name = str(r.get("column", "") or "").strip()
            if not name:
                raise SpecError(f"仕様表の行 {i} に column が無い")
            type_name = str(r.get("type", "") or "").strip()
            if type_name and type_name not in TYPES:
                raise SpecError(f"{name} の知らない型の名前: {type_name!r}"
                                f"(書けるのは {' / '.join(TYPES)})")
            domain_text = str(r.get("domain", "") or "").strip()
            domain = None
            if domain_text:
                domain = Domain.parse(domain_text)
                if type_name and domain.kind not in DOMAIN_FOR_TYPE[type_name]:
                    raise SpecError(f"{name}: 型『{type_name}』に書ける値域は"
                                    f" {' / '.join(DOMAIN_FOR_TYPE[type_name])}"
                                    f"({domain.kind} は書けない)")
            out.append(Column(name, type_name, domain, domain_text,
                              _marked(r.get("required", "")),
                              str(r.get("repair", "") or "").strip(),
                              str(r.get("source", "") or "").strip()))
        if not out:
            raise SpecError("仕様表が空")
        return cls(tuple(out))

    @classmethod
    def load(cls, path: "str | Path") -> "Spec":
        p = Path(path)
        text = p.read_text(encoding="utf-8-sig")
        if p.suffix.lower() == ".json":
            try:
                data = json.loads(text)
            except json.JSONDecodeError as e:
                raise SpecError(f"仕様表が JSON として読めない: {e}") from e
            rows = data.get("columns", data) if isinstance(data, dict) else data
            if not isinstance(rows, list):
                raise SpecError("仕様表の JSON は列の配列(または columns を持つ object)で書く")
            return cls.of(rows).from_file(p)
        rows = list(csv.DictReader(text.splitlines()))
        if not rows:
            raise SpecError("仕様表が空")
        missing = [c for c in SPEC_COLUMNS if c not in rows[0].keys()]
        if missing:
            raise SpecError(f"仕様表の見出しに無い欄: {' / '.join(missing)}"
                            f"(欄は {' / '.join(SPEC_COLUMNS)})")
        return cls.of(rows).from_file(p)

    def from_file(self, path: "str | Path") -> "Spec":
        """どのファイルのどの中身で判定したかを残す(報告に載る)。"""
        p = Path(path)
        return Spec(self.columns, p.name, sha256_of(p))

    @property
    def names(self) -> tuple:
        return tuple(c.column for c in self.columns)

    def by_name(self, name: str) -> "Column | None":
        for c in self.columns:
            if c.column == name:
                return c
        return None


def load_rows(path: "str | Path") -> list:
    """対象の行を CSV から読む(見出し行が列名)。この部品は書き出しを持たない。"""
    text = Path(path).read_text(encoding="utf-8-sig")
    return [dict(r) for r in csv.DictReader(text.splitlines())]


# ---------------------------------------------------------------- 結果

@dataclass(frozen=True)
class Pending:
    reason: str
    detail: str


@dataclass(frozen=True)
class Violation:
    """どの行のどの列が、どの宣言とどう違うか。値は現在の値のまま(書き換えない)。"""

    key: str
    column: str
    value: str
    violation: str
    judgment: str
    declared: str
    repair: str = ""
    source: str = ""

    def as_dict(self) -> dict:
        return {"識別子": self.key, "列": self.column, "現在の値": self.value,
                "違反": self.violation, "分類": self.judgment, "宣言": self.declared,
                "適用すべき直し方": self.repair, "出典": self.source}


@dataclass(frozen=True)
class Row:
    key: str
    judgment: str
    violations: tuple = ()

    def as_dict(self) -> dict:
        return {"識別子": self.key, "分類": self.judgment,
                "違反": [v.as_dict() for v in self.violations]}


@dataclass(frozen=True)
class Report:
    ok: bool
    stage: str
    rows: int = 0
    counts: "dict | None" = None
    results: tuple = ()
    pending: tuple = ()

    def as_dict(self) -> dict:
        return {"ok": self.ok, "stage": self.stage, "行": self.rows,
                "件数": dict(self.counts or {}),
                "pending": [{"reason": p.reason, "detail": p.detail} for p in self.pending]}

    def reasons(self) -> tuple:
        return tuple(dict.fromkeys(p.reason for p in self.pending))


def _ratio(n: int, d: int) -> str:
    if d == 0:
        return "分母が 0"
    return format((Decimal(n) / Decimal(d)).quantize(Decimal("0.0001")), "f")


# ------------------------------------------- 仕分け(① 仕様表 ② 突き合わせ ③ 仕分け)

class Triage:
    """3 段を固定の順序で通す。全部通った時だけ results と share() が返る。"""

    def __init__(self, rows: list, spec: Spec, key: str) -> None:
        self.rows = [dict(r) for r in rows]
        self.spec = spec
        self.key = str(key or "").strip()
        if not self.key:
            raise SpecError("識別子の列名を宣言する(既定は持たない)")
        self._report: "Report | None" = None
        self._results: list = []

    # -- ① 仕様表の検査(宣言漏れ。1 つでもあれば突き合わせに進まない) --------

    def spec_pending(self) -> list:
        out: list = []
        seen: dict = {}
        for c in self.spec.columns:
            seen[c.column] = seen.get(c.column, 0) + 1
        for name, n in seen.items():
            if n > 1:
                out.append(Pending("同じ column が仕様表に 2 行",
                                   f"列『{name}』の宣言が {n} 行ある"))
        for c in self.spec.columns:
            if not c.type_name:
                out.append(Pending("型の名前が空欄",
                                   f"列『{c.column}』に型の名前が無い(既定は持たない)"))
            if not c.domain_text:
                out.append(Pending("値域の宣言が空欄",
                                   f"列『{c.column}』に許容する値の宣言が無い"
                                   f"(制限を付けないなら『{ANY}』と書く)"))
            if c.repair and c.repair not in REPAIRS:
                out.append(Pending("repair の名前が辞書に無い",
                                   f"列『{c.column}』の直し方『{c.repair}』を部品は知らない"
                                   f"(知っているのは {' / '.join(REPAIRS)})"))
        if self.spec.by_name(self.key) is None:
            out.append(Pending("必須列が仕様表に無い", f"識別子の列『{self.key}』が仕様表に無い"))
        if not any(c.required for c in self.spec.columns):
            out.append(Pending("必須列が仕様表に無い",
                               "埋まっていなければ違反とする列の宣言が 1 つも無い"
                               "(行を同定できない)"))
        return out

    # -- ② 行と仕様表の突き合わせ ---------------------------------------------

    def match_pending(self) -> list:
        out: list = []
        known = set(self.spec.names)
        extra: dict = {}
        for i, row in enumerate(self.rows, 1):
            for name in row:
                if str(name).strip() not in known:
                    extra.setdefault(str(name).strip(), []).append(i)
        for name, where in extra.items():
            out.append(Pending("仕様表に無い列が行に在る",
                               f"列『{name}』は仕様表に無い({len(where)} 行に在る)"))
        seen: dict = {}
        for i, row in enumerate(self.rows, 1):
            seen.setdefault(str(row.get(self.key, "") or "").strip(), []).append(i)
        for k, where in seen.items():
            if len(where) > 1:
                out.append(Pending("行の識別子が重複",
                                   f"識別子『{k or '(空欄)'}』の行が {len(where)} 行ある"
                                   f"({' / '.join(str(w) + ' 行目' for w in where)})"))
        return out

    # -- ③ 列ごとに 3 値で判定し、行は最悪値で分類する ------------------------

    def judge_cell(self, row: dict, column: Column) -> "Violation | None":
        """1 つの列を 3 値で判定する。値は書き換えない(返すのは現在の値と直し方の名前)。"""
        value = str(row.get(column.column, "") or "").strip()
        if value == "":
            if not column.required:
                return None
            violation = "必要な値が空"
        else:
            violation = (_type_violation(value, column.type_name)
                         or _domain_violation(value, column.domain))
            if not violation:
                return None
        judgment = REPAIRABLE if violation in column.covers else JUDGMENT
        declared = (f"型 {column.type_name} / 値域 {column.domain_text}"
                    + ("(埋まっていなければ違反)" if column.required else ""))
        return Violation(str(row.get(self.key, "") or "").strip(), column.column, value,
                         violation, judgment, declared,
                         column.repair if judgment == REPAIRABLE else "", column.source)

    def run(self) -> Report:
        pend = self.spec_pending()
        if pend:
            self._report = Report(False, SPEC, len(self.rows), dict.fromkeys(CLASSES, 0),
                                  pending=tuple(pend))
            return self._report
        pend = self.match_pending()
        if pend:
            self._report = Report(False, MATCH, len(self.rows), dict.fromkeys(CLASSES, 0),
                                  pending=tuple(pend))
            return self._report

        results: list = []
        counts = dict.fromkeys(CLASSES, 0)
        for row in self.rows:
            found = [v for v in (self.judge_cell(row, c) for c in self.spec.columns) if v]
            judgment = PASSES
            for v in found:
                if WORST[v.judgment] > WORST[judgment]:
                    judgment = v.judgment
            counts[judgment] += 1
            results.append(Row(str(row.get(self.key, "") or "").strip(), judgment, tuple(found)))
        self._results = results
        self._report = Report(True, DONE, len(self.rows), counts, tuple(results))
        return self._report

    @property
    def report(self) -> Report:
        if self._report is None:
            raise TriageError("3 段を通る前に結果を見に来た", "判定前に出力を要求した")
        return self._report

    @property
    def results(self) -> tuple:
        r = self.report
        if not r.ok:
            raise TriageError(f"仕分けが通っていないので行の分類も出さない({r.stage}で止まった)",
                              r.reasons()[0] if r.pending else r.stage)
        return tuple(self._results)

    def violations(self) -> tuple:
        """どの行のどの列が、どの宣言とどう違うか。問い合わせの文面は作らない。"""
        return tuple(v for row in self.results for v in row.violations)

    def declared(self) -> dict:
        """判定に使った宣言の台帳(仕様表のファイル名と sha256、列ごとの宣言と覆う違反)。"""
        return {"仕様表": self.spec.name, "sha256": self.spec.sha256, "識別子": self.key,
                "列": [c.as_dict() for c in self.spec.columns]}

    def share(self) -> dict:
        """3 分類の件数と分母の内訳。**取り込める率だけは返さない**。"""
        r = self.report
        c = dict(r.counts or dict.fromkeys(CLASSES, 0))
        classified = sum(c.values())
        return {**c, "行": r.rows, "判定した行": classified,
                "判定しなかった行": r.rows - classified,
                "そのまま通る割合_判定した行のみ": _ratio(c[PASSES], classified),
                "そのまま通る割合_全ての行": _ratio(c[PASSES], r.rows),
                "分母に含めたもの": (
                    f"判定した行 = {PASSES} {c[PASSES]} + {REPAIRABLE} {c[REPAIRABLE]}"
                    f" + {JUDGMENT} {c[JUDGMENT]} = {classified}"
                    f" / 全ての行 = {r.rows}(仕分けできずに判定しなかった"
                    f" {r.rows - classified} 行を含む分母)")}

    def handoff(self) -> list:
        """全ての行がそのまま通った時だけ、次に渡す行を返す(部分出力の経路は無い)。"""
        rows = self.results
        if any(row.judgment != PASSES for row in rows):
            c = self.report.counts or {}
            raise TriageError(f"{PASSES} 以外の行が残っているので渡さない"
                              f"({REPAIRABLE} {c.get(REPAIRABLE, 0)} /"
                              f" {JUDGMENT} {c.get(JUDGMENT, 0)})",
                              JUDGMENT if c.get(JUDGMENT, 0) else REPAIRABLE)
        return [dict(r) for r in self.rows]


def triage(rows: list, spec: Spec, key: str) -> Triage:
    """3 段を通した Triage を返す(通れば results と share() が使える)。"""
    t = Triage(rows, spec, key)
    t.run()
    return t


# ---------------------------------------------------------------- CLI

def _build(args) -> Triage:
    return triage(load_rows(args.rows), Spec.load(args.spec), args.key)


def _cli_triage(args) -> int:
    t = _build(args)
    r = t.report
    out = r.as_dict()
    if r.ok:
        out["分類"] = [row.as_dict() for row in t.results]
        out["分母に含めたもの"] = t.share()["分母に含めたもの"]
    print(json.dumps(out, ensure_ascii=False))
    return 0 if r.ok and (r.counts or {}).get(PASSES, 0) == r.rows else 3


def _cli_report(args) -> int:
    t = _build(args)
    r = t.report
    if not r.ok:
        print(json.dumps(r.as_dict(), ensure_ascii=False))
        return 3
    if args.format == "csv":
        w = csv.DictWriter(sys.stdout, lineterminator="\n",
                           fieldnames=["識別子", "列", "現在の値", "違反", "分類", "宣言",
                                       "適用すべき直し方", "出典"])
        w.writeheader()
        w.writerows(v.as_dict() for v in t.violations())
    else:
        print(json.dumps({"ok": True, **t.share(), "宣言": t.declared(),
                          "違反": [v.as_dict() for v in t.violations()]}, ensure_ascii=False))
    return 0 if (r.counts or {}).get(PASSES, 0) == r.rows else 3


def _cli_init(args) -> int:
    p = Path(args.path)
    if p.exists():
        raise SpecError(f"すでにある: {p}(上書きしない)")
    rows = [{"column": "列名(識別子の列も宣言する)",
             "type": " / ".join(TYPES) + " のどれか",
             "domain": f"{ANY} / {SET}: a|b / {RANGE}: 0..100 / {LENGTH}: 6 /"
                       f" {LENGTH_MAX}: 40 / {FORM}: YYYYMMDD",
             "required": "○",
             "repair": " / ".join(REPAIRS) + " のどれか(空欄なら人の判断に落ちる)",
             "source": "出典"}]
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(SPEC_COLUMNS), lineterminator="\r\n")
        w.writeheader()
        w.writerows(rows)
    print(json.dumps({"ok": True, "wrote": str(p), "欄": list(SPEC_COLUMNS),
                      "型": list(TYPES), "直し方": {k: list(v) for k, v in REPAIRS.items()},
                      "違反": list(VIOLATIONS), "分類": list(CLASSES)}, ensure_ascii=False))
    return 0


def main(argv: "list | None" = None) -> int:
    p = argparse.ArgumentParser(
        description="取込先の仕様に入るかを 1 件も直さずに行ごと 3 つへ仕分ける"
                    "(値を書き換える経路と、通る行だけを抜き出す経路は持たない)")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, help_text, fn in (("triage", "行を 3 つに仕分ける", _cli_triage),
                                ("report", "違反の明細と分母の内訳を出す(JSON / CSV)",
                                 _cli_report)):
        s = sub.add_parser(name, help=help_text)
        s.add_argument("rows", help="仕分ける対象の行(CSV。見出し行が列名)")
        s.add_argument("--spec", required=True, help="取込先の仕様表(CSV / JSON)")
        s.add_argument("--key", required=True, help="識別子の列名(既定は持たない)")
        if name == "report":
            s.add_argument("--format", choices=("json", "csv"), default="json")
        s.set_defaults(func=fn)
    i = sub.add_parser("init", help="仕様表のひな型を書き出す")
    i.add_argument("path")
    i.set_defaults(func=_cli_init)
    args = p.parse_args(argv)
    try:
        return args.func(args)
    except (SpecError, TriageError) as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except OSError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
