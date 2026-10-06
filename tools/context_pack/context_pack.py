"""context_pack — 引いた行を AI のプロンプトへ貼る最小の塊に組み立てる部品。

数表から引いた 1 行を、そのまま AI のプロンプトへ貼る場面を扱う。人は表を開けば版が見え、機械は
引数で版を指定できるが、**AI は渡された塊の中にしか版を持てない**。だから版・有効期間・公表時点・
出典・原本の指紋が塊に焼かれていないと、もっともらしく古い値が通る。この部品は、宣言された列を
欠けなく焼いた塊を 1 つ作るか、作らずに理由コードで止まるかの 2 通りしかしない。

持たせていないものが規律になっている。

  - **モデル名・API・ネットワークを持たない**(推論は部品の外。塊を作るだけで、投げない)
  - **要約・言い換え・切り詰めの経路を持たない**(`max_chars` を超えたら黙って truncate せず止まる)
  - **表全体を貼る経路を持たない**(「全部渡して AI に選ばせる」引数が無い)
  - **近い行で埋める経路を持たない**(該当 0 件でも 2 件以上でも止まる。順位で勝ち負けを決め直さない)
  - **依頼文・判断の指示文を作らない**(「この値で計算して」等の文面は人が書く)
  - **トークン数を返さない**(分割器は部品の外にあり、出典にしてよいファイルにも無い。
    返すのは文字数とバイト数で、それが token 数の代わりにならないことを出力自体に書く)
  - **仮置きの公表時点を黙って確定値の顔で渡さない**(塊の中に仮置きと書く)

入力は 2 つ。

    行        引いた行(1 行 = 1 つの条項の適用単位。CSV か JSON)。列は ROW_COLUMNS だけ
    宣言表    貼り先の宣言(1 field = 1 行)。欄は 4 つ

      field       塊に出す行の名前(そのまま「名前: 値」の行になる)
      required    印が付いていれば必ず出す。空欄なら --field で要求された時だけ出す
      max_chars   その行の値の字数の上限(空欄 = 制限なし)。超えたら止まる
      pin         版として焼く列の名前。`|` で複数書ける(並び順がそのまま塊に出る)

順序を固定する。① 宣言を検査する ② 問いと行を突き合わせる ③ 組み立てる。前の段で止まったら
次の段には進まない。組み立ては 2 回行い、バイト列が一致しなければ止まる。

組み立てたことは「宣言された列を欠けなく焼いた塊を作った」までで、AI がその塊を使うか・答えが
正しいかは判定しない。標準ライブラリのみ(csv / json / decimal / hashlib / datetime / unicodedata /
argparse)。
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field as dc_field
from decimal import Decimal, InvalidOperation
from pathlib import Path

# 引いた行の列(この 13 だけ。post_007 の引き当てが返す形)
ROW_COLUMNS = ("rule", "selector", "valid_from", "valid_to", "known_from", "known_to",
               "known_quality", "priority", "payload", "source", "source_file",
               "source_row", "source_sha256")

# 必ず焼く列(宣言表がどれか 1 つでも pin していなければ宣言の不備)
CORE_PINS = ("payload", "selector", "valid_from", "known_from", "source",
             "source_file", "source_row", "source_sha256")

# 数として出す列(Decimal の文字列で出す。それ以外の列は行に書かれた文字のまま)
NUMERIC_COLUMNS = ("payload", "priority")

# 日付として読む列(空欄可。空欄でない時は YYYY-MM-DD)
DATE_COLUMNS = ("valid_from", "valid_to", "known_from", "known_to")

# 公表時点の品質(この 2 つだけ。既定は持たない)
REAL, TENTATIVE = "実値", "仮置き"
QUALITIES = (REAL, TENTATIVE)

# 塊の書式(固定。キーの順は宣言表の順、区切りと改行はここだけで決める)
LABEL_SEP = ": "
PIN_SEP = " / "
LINE_END = "\n"
EMPTY_MARK = "(なし)"
NOTE_TENTATIVE = "注記: 公表時点は仮置き(確定値ではない)"

# 宣言表の欄
DECL_COLUMNS = ("field", "required", "max_chars", "pin")

# 段(どこまで進んだか)。止まった段がそのまま報告に出る
DECL, MATCH, BUILD, DONE = "宣言", "突き合わせ", "組み立て", "組み立てた"

# 止まる理由コード(この 10 で全部)
REASONS = {
    "出典が空欄": "出典・原本のファイル名・原本の行番号のどれかが空欄。その値がどこの何行目から"
                  "来たかが塊から辿れない",
    "sha256 が無い": "原本の sha256 が空欄。原本が差し替わったかを塊から確かめられない",
    "有効期間が空欄": "有効期間の始まりが空欄。いつからの値かが塊から辿れない",
    "公表時点が空欄": "公表時点か、その品質(実値 / 仮置き)が空欄。当時の知識だったかが塊から辿れない",
    "該当 0 件": "問いに当たる行が無い。近い行で埋めない",
    "該当 2 件以上": "問いに当たる行が 2 行以上ある。どちらを焼くかは塊の側では決まらない"
                     "(順位で決め直すのは引く側の仕事)",
    "宣言に無い field を要求": "宣言表に無い名前の行を要求された。塊に出す行は宣言表の側で決まる",
    "max_chars 超過": "宣言された字数の上限を超えた。要約も切り詰めもしないので止まる",
    "2 回目の組み立てでバイト列が不一致": "同じ問いから 2 回組み立てて、バイト列が違った",
    "pin に指定された列が行に無い": "宣言表が焼くと言っている列が、渡された行に無い",
}

TRUE_MARKS = {"○", "◯", "o", "O", "1", "はい", "true", "True", "TRUE", "yes", "Yes"}

_NUMBER = re.compile(r"\A[+-]?[0-9]+(?:\.[0-9]+)?\Z")
_SHA256 = re.compile(r"\A[0-9a-f]{64}\Z")
_INTEGER = re.compile(r"\A[0-9]+\Z")


class DeclError(ValueError):
    """宣言表・引いた行・引数そのものが読めない(= 宣言の不備。理由コードでは扱わない)。"""


class PackError(Exception):
    """塊ができていないのに塊を取りに来た。reason に理由コードが入る。"""

    def __init__(self, message: str, reason: str = "") -> None:
        super().__init__(message)
        self.reason = reason


def sha256_of_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_of(path: "str | Path") -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _marked(value: str) -> bool:
    return str(value).strip() in TRUE_MARKS


def _has_control_char(value: str) -> bool:
    return any(unicodedata.category(ch)[0] == "C" for ch in value)


# ---------------------------------------------------------------- 宣言表

@dataclass(frozen=True)
class Field:
    """塊に出す 1 行ぶんの宣言。部品はここに書かれた名前と列しか知らない。"""

    name: str
    required: bool = False
    max_chars: int = 0          # 0 = 制限なし
    pins: tuple = ()

    def as_dict(self) -> dict:
        return {"field": self.name, "required": self.required,
                "max_chars": self.max_chars or "制限なし", "pin": list(self.pins)}


@dataclass(frozen=True)
class Declaration:
    """貼り先の宣言表。読めない宣言は DeclError、行の側の欠けは理由コードで扱う。"""

    fields: tuple = ()
    name: str = ""
    sha256: str = ""

    @classmethod
    def of(cls, rows: list, name: str = "", sha256: str = "") -> "Declaration":
        out: list = []
        seen: set = set()
        for i, r in enumerate(rows, 1):
            if not isinstance(r, dict):
                raise DeclError(f"宣言表の行 {i} が object でない")
            field_name = str(r.get("field", "") or "").strip()
            if not field_name:
                raise DeclError(f"宣言表の行 {i} に field が無い")
            if ":" in field_name or _has_control_char(field_name):
                raise DeclError(f"field に『:』や改行は書けない(1 field = 1 行): {field_name!r}")
            if field_name in seen:
                raise DeclError(f"同じ field が宣言表に 2 行ある: {field_name!r}")
            seen.add(field_name)
            max_text = str(r.get("max_chars", "") or "").strip()
            if max_text and not (_INTEGER.match(max_text) and int(max_text) >= 1):
                raise DeclError(f"{field_name} の max_chars は 1 以上の半角の整数か空欄で書く:"
                                f" {max_text!r}")
            pin_text = str(r.get("pin", "") or "").strip()
            pins = tuple(p.strip() for p in pin_text.split("|") if p.strip())
            if not pins:
                raise DeclError(f"{field_name} に pin が無い(焼く列の名前を書く)")
            for p in pins:
                if p not in ROW_COLUMNS:
                    raise DeclError(f"{field_name} の知らない列名: {p!r}"
                                    f"(書けるのは {' / '.join(ROW_COLUMNS)})")
            out.append(Field(field_name, _marked(r.get("required", "")),
                             int(max_text) if max_text else 0, pins))
        if not out:
            raise DeclError("宣言表が空")
        if not any(f.required for f in out):
            raise DeclError("必ず出す field が 1 つも無い(required に印を付ける)")
        pinned = {p for f in out if f.required for p in f.pins}
        missing = [c for c in CORE_PINS if c not in pinned]
        if missing:
            raise DeclError(f"必ず焼く列が宣言に無い: {' / '.join(missing)}"
                            f"(required の field の pin で焼く)")
        return cls(tuple(out), name, sha256)

    @classmethod
    def load(cls, path: "str | Path") -> "Declaration":
        p = Path(path)
        text = p.read_text(encoding="utf-8-sig")
        if p.suffix.lower() == ".json":
            data = json.loads(text)
            if not isinstance(data, list):
                raise DeclError(f"宣言表の JSON は object の配列で書く: {p.name}")
            rows = data
        else:
            rows = [dict(r) for r in csv.DictReader(text.splitlines())]
            unknown = sorted(set(rows[0]) - set(DECL_COLUMNS)) if rows else []
            if unknown:
                raise DeclError(f"宣言表に知らない欄がある: {' / '.join(unknown)}"
                                f"(欄は {' / '.join(DECL_COLUMNS)})")
        return cls.of(rows, p.name, sha256_of(p))

    def by_name(self, name: str) -> "Field | None":
        for f in self.fields:
            if f.name == name:
                return f
        return None

    def chosen(self, asked: tuple = ()) -> tuple:
        """出す field。required のものと、要求されたもの(宣言表の順は崩さない)。"""
        want = set(asked)
        return tuple(f for f in self.fields if f.required or f.name in want)

    def as_dict(self) -> dict:
        return {"宣言表": self.name, "sha256": self.sha256,
                "field": [f.as_dict() for f in self.fields]}


# ---------------------------------------------------------------- 引いた行

def _check_row(row: dict, i: int) -> dict:
    """引いた行として読めるかだけを見る(読めない行は理由コードにせず DeclError)。"""
    unknown = sorted(set(row) - set(ROW_COLUMNS))
    if unknown:
        raise DeclError(f"行 {i} に知らない列がある: {' / '.join(unknown)}"
                        f"(列は {' / '.join(ROW_COLUMNS)})")
    out = {k: str(v if v is not None else "").strip() for k, v in row.items()}
    for k, v in out.items():
        if _has_control_char(v):
            raise DeclError(f"行 {i} の {k} に改行か制御文字がある(1 field = 1 行にできない)")
    for k in ("rule", "selector", "payload"):
        if k in out and not out[k]:
            raise DeclError(f"行 {i} の {k} が空(引いた行として読めない)")
    for k in DATE_COLUMNS:
        if out.get(k):
            try:
                datetime.date.fromisoformat(out[k])
            except ValueError as e:
                raise DeclError(f"行 {i} の {k} が日付として読めない: {out[k]!r}") from e
    if out.get("known_quality") and out["known_quality"] not in QUALITIES:
        raise DeclError(f"行 {i} の known_quality は {' / '.join(QUALITIES)} のどちらかで書く:"
                        f" {out['known_quality']!r}")
    if out.get("source_sha256") and not _SHA256.match(out["source_sha256"]):
        raise DeclError(f"行 {i} の source_sha256 が 64 桁の 16 進でない")
    for k in ("priority", "source_row"):
        if out.get(k) and not _INTEGER.match(out[k]):
            raise DeclError(f"行 {i} の {k} は半角の整数で書く: {out[k]!r}")
    return out


def load_rows(path: "str | Path") -> list:
    """引いた行を CSV か JSON から読む(この部品は書き出しを持たない)。"""
    p = Path(path)
    text = p.read_text(encoding="utf-8-sig")
    if p.suffix.lower() == ".json":
        data = json.loads(text)
        raw = data if isinstance(data, list) else [data]
    else:
        raw = [dict(r) for r in csv.DictReader(text.splitlines())]
    return [_check_row(r, i) for i, r in enumerate(raw, 1)]


# ---------------------------------------------------------------- 組み立て

@dataclass(frozen=True)
class Pending:
    reason: str
    detail: str

    def as_dict(self) -> dict:
        return {"reason": self.reason, "detail": self.detail}


def _value_of(column: str, raw: str) -> str:
    """1 列ぶんの文字。数の列は Decimal の文字列、それ以外は行に書かれた文字のまま。"""
    v = str(raw or "").strip()
    if not v:
        return EMPTY_MARK
    if column in NUMERIC_COLUMNS and _NUMBER.match(v):
        try:
            return str(Decimal(v))
        except InvalidOperation:   # pragma: no cover - _NUMBER を通れば起きない
            return v
    return v


def _rendered(fields: tuple, row: dict) -> list:
    """field ごとの (名前, 値) を宣言表の順で返す。"""
    return [(f.name, PIN_SEP.join(_value_of(c, row.get(c, "")) for c in f.pins))
            for f in fields]


def _render(fields: tuple, row: dict) -> str:
    """塊のバイト列を決める 1 か所。区切り・改行・並び順はここだけで決まる。"""
    lines = [f"{name}{LABEL_SEP}{value}" for name, value in _rendered(fields, row)]
    if row.get("known_quality", "").strip() == TENTATIVE:
        lines.append(NOTE_TENTATIVE)
    return LINE_END.join(lines) + LINE_END


def _sizes(text: str) -> dict:
    return {"文字数": len(text), "バイト数": len(text.encode("utf-8"))}


def _as_one_line(row: dict) -> str:
    """機械が引数で引く形(1 行 JSON)。大きさを測るためだけに作り、塊としては返さない。"""
    return json.dumps(row, ensure_ascii=False, sort_keys=True)


@dataclass
class Report:
    stage: str = DECL
    ok: bool = False
    pending: tuple = ()
    matched: int = 0
    rows: int = 0

    def reasons(self) -> list:
        return [p.reason for p in self.pending]

    def as_dict(self) -> dict:
        out = {"ok": self.ok, "stage": self.stage, "行": self.rows, "該当": self.matched}
        if self.pending:
            out["pending"] = [p.as_dict() for p in self.pending]
        return out


@dataclass
class Pack:
    """1 つの問いに対する組み立て。通れば text() と sizes() が使える。"""

    rows: list
    decl: Declaration
    ask: dict
    asked_fields: tuple = ()
    report: Report = dc_field(default_factory=Report)
    row: "dict | None" = None
    fields: tuple = ()
    row_no: int = 0
    builds: int = 0
    _text: str = ""

    # -- ① 宣言 ---------------------------------------------------------------
    def _check_decl(self) -> list:
        return [Pending("宣言に無い field を要求",
                        f"宣言表 {self.decl.name or '(名前なし)'} に field『{name}』が無い")
                for name in self.asked_fields if self.decl.by_name(name) is None]

    # -- ② 突き合わせ ---------------------------------------------------------
    def _match(self) -> list:
        rule, selector = self.ask.get("rule", ""), self.ask.get("selector", "")
        hit = [(i, r) for i, r in enumerate(self.rows, 1)
               if r.get("rule", "") == rule and r.get("selector", "") == selector]
        if not hit:
            return [Pending("該当 0 件",
                            f"問い rule={rule} / selector={selector} に当たる行が"
                            f" {len(self.rows)} 行の中に無い")]
        if len(hit) > 1:
            return [Pending("該当 2 件以上",
                            f"問い rule={rule} / selector={selector} に {len(hit)} 行当たった"
                            f"(行 {' / '.join(str(i) for i, _ in hit)})")]
        self.report.matched = 1
        self.row_no, self.row = hit[0]
        return []

    # -- ③ 組み立て -----------------------------------------------------------
    def _check_core(self) -> list:
        row, out = self.row or {}, []
        for f in self.fields:
            for c in f.pins:
                if c not in row:
                    out.append(Pending("pin に指定された列が行に無い",
                                       f"field『{f.name}』が焼くと言っている列 {c} が行に無い"))
        if out:
            return out
        for c in CORE_PINS:
            if row.get(c, ""):
                continue
            if c == "source_sha256":
                out.append(Pending("sha256 が無い", "source_sha256 が空欄"))
            elif c == "valid_from":
                out.append(Pending("有効期間が空欄", "valid_from が空欄"))
            elif c == "known_from":
                out.append(Pending("公表時点が空欄", "known_from が空欄"))
            else:
                out.append(Pending("出典が空欄", f"{c} が空欄"))
        if not row.get("known_quality", ""):
            out.append(Pending("公表時点が空欄",
                               "known_quality が空欄(実値か仮置きかが塊から辿れない)"))
        return out

    def _check_limits(self) -> list:
        out = []
        for name, value in _rendered(self.fields, self.row or {}):
            f = self.decl.by_name(name)
            if f and f.max_chars and len(value) > f.max_chars:
                out.append(Pending("max_chars 超過",
                                   f"field『{name}』は {len(value)} 字で、宣言された上限"
                                   f" {f.max_chars} 字を超えた(切り詰めない)"))
        return out

    def _build(self) -> list:
        first = _render(self.fields, self.row or {})
        second = _render(self.fields, self.row or {})
        self.builds = 2
        if first.encode("utf-8") != second.encode("utf-8"):
            return [Pending("2 回目の組み立てでバイト列が不一致",
                            f"1 回目 {sha256_of_text(first)[:12]} /"
                            f" 2 回目 {sha256_of_text(second)[:12]}")]
        self._text = first
        return []

    # -- 進め方 ---------------------------------------------------------------
    def run(self) -> "Pack":
        self.report.rows = len(self.rows)
        self.fields = self.decl.chosen(self.asked_fields)
        for stage, step in ((DECL, self._check_decl), (MATCH, self._match),
                            (BUILD, self._check_core), (BUILD, self._check_limits),
                            (BUILD, self._build)):
            pending = step()
            if pending:
                self.report.stage = stage
                self.report.pending = tuple(pending)
                self.report.ok = False
                return self
        self.report.stage, self.report.ok = DONE, True
        return self

    # -- 結果 -----------------------------------------------------------------
    def _guard(self) -> None:
        if not self.report.ok:
            first = self.report.pending[0] if self.report.pending else Pending("", "")
            raise PackError(f"塊はできていない({first.reason}: {first.detail})", first.reason)

    def text(self) -> str:
        """塊。欠けなく焼けた時だけ返る(部分的な塊を返す経路は無い)。"""
        self._guard()
        return self._text

    def sha256(self) -> str:
        self._guard()
        return sha256_of_text(self._text)

    def sizes(self) -> dict:
        """減った量は文字数とバイト数で返す。トークン数は返さない。"""
        self._guard()
        whole = LINE_END.join(_as_one_line(r) for r in self.rows) + LINE_END
        one = _as_one_line(self.row or {}) + LINE_END
        only = _value_of("payload", (self.row or {}).get("payload", "")) + LINE_END
        block = _sizes(self._text)
        return {
            "大きさ": block,
            "比べた相手": {"表全体をそのまま貼る": _sizes(whole),
                           "機械が引数で引く 1 行": _sizes(one),
                           "値だけを貼る": _sizes(only)},
            "表全体から減った文字数": _sizes(whole)["文字数"] - block["文字数"],
            "値だけより増えた文字数": block["文字数"] - _sizes(only)["文字数"],
            "proxy の限界": "文字数とバイト数は token 数の代わりにならない。分割器は部品の外に"
                            "あり、出典にしてよいファイルにも無いので、token 数は返さない",
        }

    def pinned(self) -> dict:
        """何を焼いたか(field ごとの値と、焼いた列の名前)。"""
        self._guard()
        return {name: {"値": value, "pin": list(self.decl.by_name(name).pins)}
                for name, value in _rendered(self.fields, self.row or {})}

    def as_dict(self) -> dict:
        out = self.report.as_dict()
        if not self.report.ok:
            return out
        return {**out, "問い": dict(self.ask), "行番号": self.row_no,
                "塊": self._text, "塊の sha256": sha256_of_text(self._text),
                "組み立てた回数": self.builds,
                "公表時点": (self.row or {}).get("known_quality", ""),
                "宣言表": {"名前": self.decl.name, "sha256": self.decl.sha256},
                **self.sizes()}


def pack(rows: list, decl: Declaration, ask: dict, fields: tuple = ()) -> Pack:
    """3 段を通した Pack を返す(通れば text() と sizes() が使える)。"""
    for k in ("rule", "selector"):
        if not str(ask.get(k, "") or "").strip():
            raise DeclError(f"問いに {k} が無い(既定は持たない)")
    return Pack(rows, decl, dict(ask), tuple(fields)).run()


def verify(rows: list, decl: Declaration, ask: dict, fields: tuple = ()) -> dict:
    """同じ問いから 2 回組み立てて、バイト列の sha256 が一致するかを見る。"""
    a = pack(rows, decl, ask, fields)
    if not a.report.ok:
        return {"ok": False, **a.report.as_dict()}
    b = pack(rows, decl, ask, fields)
    same = a.sha256() == b.sha256()
    out = {"ok": same, "stage": DONE, "組み立てた回数": a.builds + b.builds,
           "sha256": a.sha256(), "2 回目の sha256": b.sha256(), "一致": same,
           **_sizes(a.text())}
    if not same:
        out["pending"] = [Pending("2 回目の組み立てでバイト列が不一致",
                                  "同じ問いから作った塊の sha256 が違う").as_dict()]
    return out


# ---------------------------------------------------------------- CLI

def _load(args) -> tuple:
    return load_rows(args.rows), Declaration.load(args.decl)


def _ask_of(args) -> dict:
    return {"rule": args.rule, "selector": args.select}


def _cli_pack(args) -> int:
    rows, decl = _load(args)
    p = pack(rows, decl, _ask_of(args), tuple(args.field or ()))
    print(json.dumps(p.as_dict(), ensure_ascii=False))
    return 0 if p.report.ok else 3


def _cli_verify(args) -> int:
    rows, decl = _load(args)
    out = verify(rows, decl, _ask_of(args), tuple(args.field or ()))
    print(json.dumps(out, ensure_ascii=False))
    return 0 if out["ok"] else 3


TEMPLATE = [
    {"field": "値", "required": "○", "max_chars": "40", "pin": "payload"},
    {"field": "対象", "required": "○", "max_chars": "120", "pin": "rule|selector"},
    {"field": "有効期間", "required": "○", "max_chars": "40", "pin": "valid_from|valid_to"},
    {"field": "公表時点", "required": "○", "max_chars": "40", "pin": "known_from|known_quality"},
    {"field": "出典", "required": "○", "max_chars": "120", "pin": "source"},
    {"field": "原本", "required": "○", "max_chars": "160",
     "pin": "source_file|source_row|source_sha256"},
    {"field": "順位", "required": "", "max_chars": "20", "pin": "priority"},
]


def _cli_init(args) -> int:
    p = Path(args.path)
    if p.exists():
        raise DeclError(f"すでにある: {p}(上書きしない)")
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(DECL_COLUMNS), lineterminator="\r\n")
        w.writeheader()
        w.writerows(TEMPLATE)
    print(json.dumps({"ok": True, "wrote": str(p), "欄": list(DECL_COLUMNS),
                      "必ず焼く列": list(CORE_PINS), "行の列": list(ROW_COLUMNS),
                      "理由コード": list(REASONS)}, ensure_ascii=False))
    return 0


def main(argv: "list | None" = None) -> int:
    p = argparse.ArgumentParser(
        description="引いた行を AI のプロンプトへ貼る最小の塊に組み立てる"
                    "(要約・切り詰め・表全体を貼る経路は持たない)")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, help_text, fn in (("pack", "塊を 1 つ組み立てる", _cli_pack),
                                ("verify", "2 回組み立てて sha256 の一致を見る", _cli_verify)):
        s = sub.add_parser(name, help=help_text)
        s.add_argument("rows", help="引いた行(CSV / JSON)")
        s.add_argument("--decl", required=True, help="貼り先の宣言表(CSV / JSON)")
        s.add_argument("--rule", required=True, help="問い: 何を求めるか(既定は持たない)")
        s.add_argument("--select", required=True, help="問い: 対象(既定は持たない)")
        s.add_argument("--field", action="append",
                       help="required でない field も出す(宣言表に在る名前だけ)")
        s.set_defaults(func=fn)
    i = sub.add_parser("init", help="宣言表のひな型を書き出す")
    i.add_argument("path")
    i.set_defaults(func=_cli_init)
    args = p.parse_args(argv)
    try:
        return args.func(args)
    except (DeclError, PackError) as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError) as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
