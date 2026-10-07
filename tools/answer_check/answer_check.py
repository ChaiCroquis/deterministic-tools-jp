"""answer_check — AI へ渡した塊と、返ってきた文章を突き合わせる関所。

前の工程(引いた行を AI のプロンプトへ貼る塊に組み立てる部品)で、渡すところまでは機械で固まる。
固まらないのは、返ってきた文章のほうだ。文章に現れた数値が、渡した行の値なのか、塊の外から出てきた
値なのかは、文章を読んだだけでは区別できない。この部品は **文章に現れた数値が塊の行に在るかどうか**
だけを判定し、4 値の件数と分母の内訳を返して人に戻す。

持たせていないものが規律になっている。

  - **モデル名・API・ネットワークを持たない**(推論は関所の外。文章は人が貼る)
  - **どちらが正しいとも返さない**(正とする側を選ぶ引数が無い。AI を採点しない)
  - **許容誤差の引数を持たない**(差額を丸めて吸収する経路が無い。丸めは名前で宣言し、両側に同じ
    名前の丸めを当てる)
  - **文章を書き換えない**(訂正文・指摘文・再依頼文を作る経路が無い)
  - **接地率を単独で返さない**(4 値の件数と分母の内訳を必ず併記する)
  - **塊の外へ値を取りに行かない**(足りない行を表から引き直す経路が無い。原本のファイルを開かない)
  - **近い行で埋めない**(同じ対象の行が塊に 2 件以上あれば比べずに止める)
  - **推測で単位を補わない**(宣言に無い単位は正規化せず「比べられない」に落とす)

入力は 2 つ(と宣言表)。

    塊      前の工程が組んだ塊(text)、または同じ列を持つ 1 行 JSON / CSV。列は PACK_COLUMNS だけ
    文章    突き合わせる plain text(ファイルか標準入力)
    宣言表  比べる対象ごとの宣言(1 対象 = 1 行)。欄は 6 つ

      selector   塊の「対象」の行とそのまま一致する文字列
      alias      文章の中でその対象を指す呼び方。`|` で複数書ける
      unit       文章に出てよい単位。`|` で複数。**1 つめが塊の値の単位**
      scale      unit と同じ数だけ `|` で並べる倍率の名前。**1 つめは「そのまま」**
      period     照合の基準日(YYYY-MM-DD)。塊の有効期間がこの日を含まなければ止まる
      rounding   比べる前に両側へ当てる丸めの名前

順序を固定する。① 塊を検査する ② 宣言を検査する ③ 文章を読む ④ 基準日を見る ⑤ 4 値に分ける。
前の段で止まったら次の段には進まない。判定は 2 回行い、バイト列が一致しなければ止まる。

判定したことは「文章に現れた数値が塊の行に在るか」までで、文章の主張が妥当か・値が制度として
正しいか・モデルがなぜその数値を出したかは判定しない。標準ライブラリのみ(csv / json / re /
decimal / hashlib / datetime / unicodedata / argparse)。
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
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

# 塊 1 件ぶんの列(前の工程が焼いた 8 列 + 有効期間の終わり + 持ち越す 1 列)
PACK_COLUMNS = ("selector", "payload", "valid_from", "valid_to", "known_from", "known_quality",
                "source", "source_file", "source_row", "source_sha256", "priority")

# 塊に必ず在る列(1 つでも空欄なら判定に入らない。前の工程と同じ要件)
CORE_COLUMNS = ("selector", "payload", "valid_from", "known_from", "known_quality",
                "source", "source_file", "source_row", "source_sha256")

# 比較に使わない列(持ち越すだけ)
CARRIED = ("priority",)

# 塊の text を読むときの行の名前(前の工程の init が出すひな型の名前)
TEXT_FIELDS = {
    "値": ("payload",),
    "対象": ("selector",),
    "有効期間": ("valid_from", "valid_to"),
    "公表時点": ("known_from", "known_quality"),
    "出典": ("source",),
    "原本": ("source_file", "source_row", "source_sha256"),
    "順位": ("priority",),
}
TEXT_NOTE = "注記"            # 仮置きの注記の行(読み飛ばさず known_quality と突き合わせる)
TEXT_EMPTY = "(なし)"         # 空欄の列の書き方(前の工程と同じ)
TEXT_PIN_SEP = " / "
TEXT_LABEL_SEP = ": "

# 宣言表の欄
DECL_COLUMNS = ("selector", "alias", "unit", "scale", "period", "rounding")

# 公表時点の品質(この 2 つだけ)
REAL, TENTATIVE = "実値", "仮置き"
QUALITIES = (REAL, TENTATIVE)

# 判定(この 4 値で全部)
GROUNDED, DISAGREE, ABSENT, INCOMPARABLE = "接地", "食い違い", "塊に無い", "比べられない"
VERDICTS = (GROUNDED, DISAGREE, ABSENT, INCOMPARABLE)

# 倍率の名前(既定は持たない = 宣言表に名前を書かせる)
SCALES = {"そのまま": Decimal("1"), "10分の1": Decimal("0.1"), "100分の1": Decimal("0.01"),
          "1000分の1": Decimal("0.001"), "百倍": Decimal("100"), "千倍": Decimal("1000"),
          "万倍": Decimal("10000")}

# 丸めの名前(比べる前に両側へ同じ名前の丸めを当てる。差額で通す引数は無い)
ROUNDINGS = ("しない", "整数", "小数1桁", "小数2桁", "小数3桁", "小数4桁")

# 段(どこまで進んだか)。止まった段がそのまま報告に出る
PACK, DECL, TEXT, JUDGE, DONE = "塊", "宣言", "文章", "判定", "判定した"

# 止まる理由コード(この 10 で全部)
REASONS = {
    "塊に出典が無い": "塊の出典・原本のファイル名・原本の行番号のどれかが空欄。その値がどこの"
                      "何行目から来たかが塊から辿れないので、文章と突き合わせても接地と言えない",
    "塊に sha256 が無い": "塊に原本の指紋が無い。原本が差し替わったかを確かめられない",
    "塊に有効期間が無い": "塊に有効期間の始まりが無い。いつからの値かが塊から辿れない",
    "塊に公表時点が無い": "塊に公表時点か、その品質(実値 / 仮置き)が無い",
    "塊の有効期間が照合の基準日を含まない": "宣言された基準日が、塊の行の有効期間の外にある。"
                                            "別の版の行と文章を突き合わせることになるので止まる",
    "単位の宣言が無い列を要求": "宣言表の対象に unit が書かれていない。単位を推測で補わないので"
                                "比べられない",
    "同じ selector の行が 2 件以上": "同じ対象の行が塊に 2 行ある。どちらと比べるかは文章の側では"
                                     "決まらないので、近い行で埋めずに止まる",
    "文章が空": "突き合わせる文章が空。取り出せた数値 0 件を「全部接地」として返さない",
    "宣言に無い正規化を要求": "宣言表が、登録されていない正規化(倍率 / 丸め)の名前を呼んでいる",
    "2 回目の判定でバイト列が不一致": "同じ入力から 2 回判定して、返したバイト列が違った",
}

# 文章から数の表記を拾う(緩く拾って、厳しく読む)
_NUM_LOOSE = re.compile(r"[0-9０-９][0-9０-９,，.．〜～~ー]*[0-9０-９]|[0-9０-９]")
_KANJI_NUM = re.compile(r"[〇一二三四五六七八九十][〇一二三四五六七八九十百千万・点]*")
_NUM_STRICT = re.compile(r"\A(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?\Z")
_SPACE = " 　\t"
_SENTENCE = re.compile(r"[^。\n]+")
_SHA256 = re.compile(r"\A[0-9a-f]{64}\Z")
_INTEGER = re.compile(r"\A[0-9]+\Z")
_DECIMAL_PLACES = re.compile(r"\A小数([0-9])桁\Z")


class DeclError(ValueError):
    """塊・宣言表・文章そのものが読めない(= 入力の不備。理由コードでは扱わない)。"""


class CheckError(Exception):
    """判定が通っていないのに結果を取りに来た。reason に理由コードが入る。"""

    def __init__(self, message: str, reason: str = "") -> None:
        super().__init__(message)
        self.reason = reason


def sha256_of_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s)


def _has_control_char(value: str) -> bool:
    return any(unicodedata.category(ch)[0] == "C" for ch in value)


# ---------------------------------------------------------------- 塊

def _check_pack_row(row: dict, i: int) -> dict:
    """塊 1 件として読めるかだけを見る(読めないものは理由コードにせず DeclError)。"""
    unknown = sorted(set(row) - set(PACK_COLUMNS))
    if unknown:
        raise DeclError(f"塊 {i} に知らない列がある: {' / '.join(unknown)}"
                        f"(列は {' / '.join(PACK_COLUMNS)})")
    out = {k: str(v if v is not None else "").strip() for k, v in row.items()}
    for k, v in out.items():
        if _has_control_char(v):
            raise DeclError(f"塊 {i} の {k} に改行か制御文字がある")
    if not out.get("selector", ""):
        raise DeclError(f"塊 {i} に対象(selector)が無い")
    for k in ("valid_from", "valid_to", "known_from"):
        if out.get(k):
            try:
                datetime.date.fromisoformat(out[k])
            except ValueError as e:
                raise DeclError(f"塊 {i} の {k} が日付として読めない: {out[k]!r}") from e
    if out.get("known_quality") and out["known_quality"] not in QUALITIES:
        raise DeclError(f"塊 {i} の known_quality は {' / '.join(QUALITIES)} のどちらかで書く:"
                        f" {out['known_quality']!r}")
    if out.get("source_sha256") and not _SHA256.match(out["source_sha256"]):
        raise DeclError(f"塊 {i} の source_sha256 が 64 桁の 16 進でない")
    for k in ("source_row", "priority"):
        if out.get(k) and not _INTEGER.match(out[k]):
            raise DeclError(f"塊 {i} の {k} は半角の整数で書く: {out[k]!r}")
    return out


def parse_pack_text(text: str) -> list:
    """前の工程が組んだ塊(text)を読む。空行で区切って複数の塊を並べてよい。"""
    out: list = []
    for n, chunk in enumerate([c for c in re.split(r"\n\s*\n", text) if c.strip()], 1):
        row: dict = {}
        tentative = False
        for raw in chunk.splitlines():
            line = raw.strip()
            if not line:
                continue
            if TEXT_LABEL_SEP not in line:
                raise DeclError(f"塊 {n} の行が「名前{TEXT_LABEL_SEP}値」の形でない: {line!r}")
            name, value = line.split(TEXT_LABEL_SEP, 1)
            name = name.strip()
            if name == TEXT_NOTE:
                tentative = True
                continue
            if name not in TEXT_FIELDS:
                raise DeclError(f"塊 {n} に知らない行がある: {name!r}"
                                f"(読めるのは {' / '.join(TEXT_FIELDS)} と {TEXT_NOTE})")
            columns = TEXT_FIELDS[name]
            # 区切りで切るのは宣言された列の数まで(「対象」は 1 列なので切らない = 中に
            # 区切りが入っていてもそのまま 1 つの文字列として読む)
            parts = [p.strip() for p in value.split(TEXT_PIN_SEP, len(columns) - 1)]
            for col, part in zip(columns, parts):
                row[col] = "" if part == TEXT_EMPTY else part
        if not row:
            raise DeclError(f"塊 {n} が空")
        if tentative and row.get("known_quality", "") != TENTATIVE:
            raise DeclError(f"塊 {n} に仮置きの注記があるのに公表時点の品質が {TENTATIVE} でない")
        out.append(row)
    if not out:
        raise DeclError("塊が空")
    return out


def load_pack(path: "str | Path") -> list:
    """塊を読む(text / JSON / CSV)。この部品は塊を書き出す経路を持たない。"""
    p = Path(path)
    text = p.read_text(encoding="utf-8-sig")
    suffix = p.suffix.lower()
    if suffix == ".json":
        data = json.loads(text)
        raw = data if isinstance(data, list) else [data]
    elif suffix == ".csv":
        raw = [dict(r) for r in csv.DictReader(text.splitlines())]
    else:
        raw = parse_pack_text(text)
    if not raw:
        raise DeclError(f"塊が空: {p.name}")
    return [_check_pack_row(r, i) for i, r in enumerate(raw, 1)]


# ---------------------------------------------------------------- 宣言表

@dataclass(frozen=True)
class Target:
    """比べる対象 1 つぶんの宣言。部品はここに書かれた名前と列しか知らない。"""

    selector: str
    aliases: tuple = ()
    units: tuple = ()
    scales: tuple = ()
    period: str = ""
    rounding: str = ""

    def base_unit(self) -> str:
        return self.units[0] if self.units else ""

    def as_dict(self) -> dict:
        return {"selector": self.selector, "alias": list(self.aliases),
                "unit": list(self.units), "scale": list(self.scales),
                "period": self.period, "rounding": self.rounding}


@dataclass(frozen=True)
class Declaration:
    """比べる対象の宣言表。読めない宣言は DeclError、名前の不備は理由コードで扱う。"""

    targets: tuple = ()
    name: str = ""

    @classmethod
    def of(cls, rows: list, name: str = "") -> "Declaration":
        out: list = []
        seen_selector: set = set()
        seen_alias: dict = {}
        for i, r in enumerate(rows, 1):
            if not isinstance(r, dict):
                raise DeclError(f"宣言表の行 {i} が object でない")
            selector = str(r.get("selector", "") or "").strip()
            if not selector:
                raise DeclError(f"宣言表の行 {i} に selector が無い")
            if selector in seen_selector:
                raise DeclError(f"同じ selector が宣言表に 2 行ある: {selector!r}")
            seen_selector.add(selector)
            aliases = tuple(a.strip() for a in str(r.get("alias", "") or "").split("|")
                            if a.strip())
            if not aliases:
                raise DeclError(f"{selector} に alias が無い(文章での呼び方を書く)")
            for a in aliases:
                if a in seen_alias:
                    raise DeclError(f"同じ alias が 2 つの対象に書かれている: {a!r}"
                                    f"({seen_alias[a]} と {selector})")
                seen_alias[a] = selector
            units = tuple(u.strip() for u in str(r.get("unit", "") or "").split("|") if u.strip())
            scales = tuple(s.strip() for s in str(r.get("scale", "") or "").split("|") if s.strip())
            if units and len(units) != len(scales):
                raise DeclError(f"{selector} の unit と scale の数が違う"
                                f"({len(units)} と {len(scales)})。1 単位に 1 つの名前を書く")
            if units and len(set(units)) != len(units):
                raise DeclError(f"{selector} の unit に同じ単位が 2 つある")
            period = str(r.get("period", "") or "").strip()
            if period:
                try:
                    datetime.date.fromisoformat(period)
                except ValueError as e:
                    raise DeclError(f"{selector} の period が日付として読めない: {period!r}") from e
            out.append(Target(selector, aliases, units, scales, period,
                              str(r.get("rounding", "") or "").strip()))
        if not out:
            raise DeclError("宣言表が空")
        return cls(tuple(out), name)

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
        return cls.of(rows, p.name)

    def by_selector(self, selector: str) -> "Target | None":
        for t in self.targets:
            if t.selector == selector:
                return t
        return None

    def alias_map(self) -> dict:
        """呼び方 → selector。長い呼び方から先に当てる並びで返す。"""
        pairs = [(a, t.selector) for t in self.targets for a in t.aliases]
        return dict(sorted(pairs, key=lambda kv: (-len(kv[0]), kv[0])))

    def all_units(self) -> tuple:
        """宣言された単位の全部(長いものから先に当てる)。これ以外の単位は読み取らない。"""
        us = {u for t in self.targets for u in t.units}
        return tuple(sorted(us, key=lambda u: (-len(_nfkc(u)), u)))

    def as_dict(self) -> dict:
        return {"宣言表": self.name, "対象": [t.as_dict() for t in self.targets]}


# ---------------------------------------------------------------- 正規化

def _quantize(value: Decimal, rounding: str) -> Decimal:
    """宣言された名前の丸めを当てる(名前で呼ぶ。差額の大きさで通す経路は無い)。"""
    if rounding == "しない":
        return value
    if rounding == "整数":
        return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    m = _DECIMAL_PLACES.match(rounding)
    if not m:   # pragma: no cover - ROUNDINGS の検査を通れば起きない
        raise DeclError(f"知らない丸めの名前: {rounding!r}")
    return value.quantize(Decimal("1").scaleb(-int(m.group(1))), rounding=ROUND_HALF_UP)


def read_number(raw: str) -> "Decimal | None":
    """文章にあった表記を数として読む。読めなければ None(推測で直さない)。"""
    t = _nfkc(raw).strip()
    if not _NUM_STRICT.match(t):
        return None
    try:
        return Decimal(t.replace(",", ""))
    except InvalidOperation:   # pragma: no cover - _NUM_STRICT を通れば起きない
        return None


# ---------------------------------------------------------------- 取り出し

@dataclass(frozen=True)
class Found:
    """文章の中の 1 つの表記。生の表記は書き換えずに持ち越す。"""

    text: str
    sentence: int
    start: int
    unit: str = ""
    readable: bool = True
    selector: str = ""
    verdict: str = ""
    value: str = ""
    pack_value: str = ""
    pack_row: int = 0
    why: str = ""

    def as_dict(self) -> dict:
        out = {"表記": self.text, "文": self.sentence, "単位": self.unit,
               "読めた": self.readable, "対象": self.selector}
        if self.verdict:   # 読めなかった表記は 4 値に入らない(判定の欄を持たせない)
            out["判定"] = self.verdict
        if self.value:
            out["正規化"] = self.value
        if self.pack_row:
            out["塊の行"] = self.pack_row
            out["塊の値"] = self.pack_value
        if self.why:
            out["なぜ"] = self.why
        return out


def _unit_at(text: str, pos: int, units: tuple) -> str:
    """位置 pos の直後に書かれている単位(宣言されたものだけ)。無ければ空。"""
    i = pos
    while i < len(text) and text[i] in _SPACE:
        i += 1
    for u in units:
        n = _nfkc(u)
        for width in range(1, len(u) + 2):
            if _nfkc(text[i:i + width]) == n:
                return u
    return ""


def _aliases_in(sentence: str, alias_map: dict) -> list:
    """文の中の呼び方の出現(終わり位置, selector)。重なる呼び方は長いほうを採る。"""
    taken: list = []
    out: list = []
    for alias, selector in alias_map.items():
        start = 0
        while True:
            i = sentence.find(alias, start)
            if i < 0:
                break
            end = i + len(alias)
            if not any(a < end and i < b for a, b in taken):
                taken.append((i, end))
                out.append((end, selector))
            start = i + 1
    return sorted(out)


def find_numbers(body: str, decl: Declaration) -> list:
    """文章から数の表記を拾う(緩く拾って、厳しく読む)。文章は書き換えない。"""
    units, alias_map = decl.all_units(), decl.alias_map()
    out: list = []
    sentences = [m for m in _SENTENCE.finditer(body) if m.group(0).strip()]
    for n, m in enumerate(sentences, 1):
        sentence, base = m.group(0), m.start()
        aliases = _aliases_in(sentence, alias_map)
        hits = sorted(list(_NUM_LOOSE.finditer(sentence)) + list(_KANJI_NUM.finditer(sentence)),
                      key=lambda h: h.start())
        for hit in hits:
            raw = hit.group(0)
            unit = _unit_at(sentence, hit.end(), units)
            if _KANJI_NUM.fullmatch(raw) is not None and not unit:
                continue   # 単位の付かない漢数字は数の表記として拾わない(「一致」「十分」など)
            selector = ""
            for end, sel in aliases:
                if end <= hit.start():
                    selector = sel
            out.append(Found(raw, n, base + hit.start(), unit,
                             read_number(raw) is not None, selector))
    return out


# ---------------------------------------------------------------- 判定

@dataclass(frozen=True)
class Pending:
    reason: str
    detail: str

    def as_dict(self) -> dict:
        return {"reason": self.reason, "detail": self.detail}


@dataclass
class Report:
    stage: str = PACK
    ok: bool = False
    pending: tuple = ()
    packs: int = 0

    def reasons(self) -> list:
        return [p.reason for p in self.pending]

    def as_dict(self) -> dict:
        out = {"ok": self.ok, "stage": self.stage, "塊の行": self.packs}
        if self.pending:
            out["pending"] = [p.as_dict() for p in self.pending]
        return out


@dataclass
class Check:
    """塊 1 組と文章 1 本の突き合わせ。通れば counts() と table() が使える。"""

    pack: list
    decl: Declaration
    body: str
    report: Report = dc_field(default_factory=Report)
    found: tuple = ()
    rounds: int = 0

    # -- ① 塊 -----------------------------------------------------------------
    def _check_pack(self) -> list:
        out: list = []
        for i, row in enumerate(self.pack, 1):
            for c in CORE_COLUMNS:
                if row.get(c, ""):
                    continue
                if c == "source_sha256":
                    out.append(Pending("塊に sha256 が無い", f"塊 {i} の source_sha256 が空欄"))
                elif c == "valid_from":
                    out.append(Pending("塊に有効期間が無い", f"塊 {i} の valid_from が空欄"))
                elif c in ("known_from", "known_quality"):
                    out.append(Pending("塊に公表時点が無い", f"塊 {i} の {c} が空欄"))
                else:
                    out.append(Pending("塊に出典が無い", f"塊 {i} の {c} が空欄"))
        seen: dict = {}
        for i, row in enumerate(self.pack, 1):
            seen.setdefault(row["selector"], []).append(i)
        for selector, where in seen.items():
            if len(where) > 1:
                out.append(Pending("同じ selector の行が 2 件以上",
                                   f"対象「{selector}」の行が塊に {len(where)} 件ある"
                                   f"(塊 {' / '.join(str(i) for i in where)})"))
        return out

    # -- ② 宣言 ---------------------------------------------------------------
    def _check_decl(self) -> list:
        out: list = []
        for t in self.decl.targets:
            if not t.units:
                out.append(Pending("単位の宣言が無い列を要求",
                                   f"対象「{t.selector}」に unit が書かれていない"))
                continue
            if t.scales and t.scales[0] != "そのまま":
                out.append(Pending("宣言に無い正規化を要求",
                                   f"対象「{t.selector}」の scale の 1 つめは「そのまま」で書く"
                                   f"(1 つめの単位が塊の値の単位): {t.scales[0]!r}"))
            for s in t.scales:
                if s not in SCALES:
                    out.append(Pending("宣言に無い正規化を要求",
                                       f"対象「{t.selector}」の知らない倍率の名前: {s!r}"
                                       f"(書けるのは {' / '.join(SCALES)})"))
            if t.rounding and t.rounding not in ROUNDINGS:
                out.append(Pending("宣言に無い正規化を要求",
                                   f"対象「{t.selector}」の知らない丸めの名前: {t.rounding!r}"
                                   f"(書けるのは {' / '.join(ROUNDINGS)})"))
        return out

    # -- ③ 文章 ---------------------------------------------------------------
    def _check_body(self) -> list:
        if not self.body.strip():
            return [Pending("文章が空", "突き合わせる文章に文字が無い")]
        return []

    # -- ④ 基準日(塊と宣言の噛み合わせ) -------------------------------------
    def _check_period(self) -> list:
        out: list = []
        for t in self.decl.targets:
            if not t.period:
                continue
            for i, row in enumerate(self.pack, 1):
                if row["selector"] != t.selector:
                    continue
                day = datetime.date.fromisoformat(t.period)
                begin = datetime.date.fromisoformat(row["valid_from"])
                end = datetime.date.fromisoformat(row["valid_to"]) if row.get("valid_to") else None
                if day < begin or (end is not None and day >= end):
                    out.append(Pending("塊の有効期間が照合の基準日を含まない",
                                       f"対象「{t.selector}」の基準日 {t.period} が、塊 {i} の"
                                       f" {row['valid_from']} 〜"
                                       f" {row.get('valid_to') or '(なし)'} の外にある"))
        return out

    # -- ⑤ 4 値に分ける -------------------------------------------------------
    def _judge(self) -> list:
        self.found = tuple(self._verdict_of(f) for f in find_numbers(self.body, self.decl))
        return []

    def _verdict_of(self, f: Found) -> Found:
        if not f.readable:
            return f
        if not f.selector:
            return self._with(f, ABSENT,
                              why="同じ文に宣言された呼び方が無く、どの対象の数値か決まらない")
        t = self.decl.by_selector(f.selector)
        if t is None:   # pragma: no cover - alias_map は宣言から作るので起きない
            return self._with(f, ABSENT, why="宣言に無い対象")
        if not f.unit:
            return self._with(f, INCOMPARABLE, why="表記に単位が無い(推測で補わない)")
        if f.unit not in t.units:
            return self._with(f, INCOMPARABLE, why=f"単位「{f.unit}」はこの対象の宣言に無い")
        if not t.period:
            return self._with(f, INCOMPARABLE, why="照合の基準日が宣言されていない")
        if not t.rounding:
            return self._with(f, INCOMPARABLE, why="丸めの宣言が無い")
        rows = [(i, r) for i, r in enumerate(self.pack, 1) if r["selector"] == f.selector]
        if not rows:
            return self._with(f, ABSENT, why="この対象の行が塊に無い(塊の外へ取りに行かない)")
        i, row = rows[0]
        scale = SCALES[t.scales[t.units.index(f.unit)]]
        mine = _quantize(read_number(f.text) * scale, t.rounding)
        theirs = read_number(row["payload"])
        if theirs is None:
            return self._with(f, INCOMPARABLE, pack_row=i, pack_value=row["payload"],
                              value=str(mine), why="塊の値が数として読めない")
        theirs = _quantize(theirs, t.rounding)
        verdict = GROUNDED if str(mine) == str(theirs) else DISAGREE
        return self._with(f, verdict, value=str(mine), pack_row=i, pack_value=str(theirs))

    @staticmethod
    def _with(f: Found, verdict: str, **kw) -> Found:
        return Found(f.text, f.sentence, f.start, f.unit, f.readable, f.selector, verdict,
                     kw.get("value", ""), kw.get("pack_value", ""), kw.get("pack_row", 0),
                     kw.get("why", ""))

    # -- 進め方 ---------------------------------------------------------------
    def run(self) -> "Check":
        self.report.packs = len(self.pack)
        for stage, step in ((PACK, self._check_pack), (DECL, self._check_decl),
                            (TEXT, self._check_body), (JUDGE, self._check_period),
                            (JUDGE, self._judge)):
            pending = step()
            if pending:
                self.report.stage = stage
                self.report.pending = tuple(pending)
                self.report.ok = False
                return self
        self.rounds = 1
        self.report.stage, self.report.ok = DONE, True
        return self

    # -- 結果 -----------------------------------------------------------------
    def _guard(self) -> None:
        if not self.report.ok:
            first = self.report.pending[0] if self.report.pending else Pending("", "")
            raise CheckError(f"判定は通っていない({first.reason}: {first.detail})", first.reason)

    def counts(self) -> dict:
        """4 値の件数(単独で読む呼び方はしない。分母の内訳と一緒に使う)。"""
        self._guard()
        return {v: sum(1 for f in self.found if f.verdict == v) for v in VERDICTS}

    def denominator(self) -> dict:
        """分母の内訳。取り出せなかった表記を隠さない。"""
        self._guard()
        got = sum(1 for f in self.found if f.readable)
        missed = sum(1 for f in self.found if not f.readable)
        return {"文章から取り出せた数値": got, "取り出せなかった表記": missed,
                "見つけた表記の総数": got + missed,
                "比べられた数値": sum(1 for f in self.found
                                      if f.verdict in (GROUNDED, DISAGREE))}

    def table(self) -> list:
        """表記ごとの判定と、塊のどの行と比べたかの対応表(文章は書き換えない)。"""
        self._guard()
        return [f.as_dict() for f in self.found]

    def rate(self) -> dict:
        """接地率。4 値の件数と分母の内訳を必ず同時に返す(単独で返す呼び方は無い)。"""
        self._guard()
        c, d = self.counts(), self.denominator()
        compared, got = d["比べられた数値"], d["文章から取り出せた数値"]
        return {**c, **d,
                "接地率_比べられた数値のみ":
                    f"{Decimal(c[GROUNDED]) / compared:.4f}" if compared
                    else "分母 0(比べられた数値が無い)",
                "接地率_取り出せた数値すべて":
                    f"{Decimal(c[GROUNDED]) / got:.4f}" if got
                    else "分母 0(取り出せた数値が無い)",
                "分母に含めたもの":
                    f"比べられた数値のみ = {GROUNDED} {c[GROUNDED]} + {DISAGREE} {c[DISAGREE]}"
                    f" = {compared}({ABSENT} {c[ABSENT]} + {INCOMPARABLE} {c[INCOMPARABLE]}"
                    f" を除いた分母) / 取り出せた数値すべて = {got}"
                    f"(取り出せなかった表記 {d['取り出せなかった表記']} 件は"
                    f"どちらの分母にも入らない)"}

    def as_dict(self) -> dict:
        out = self.report.as_dict()
        if not self.report.ok:
            return out
        return {**out, "宣言表": self.decl.name,
                "文章": {"文字数": len(self.body),
                         "文の数": len([m for m in _SENTENCE.finditer(self.body)
                                        if m.group(0).strip()])},
                **self.rate(), "対応表": self.table(), "判定した回数": self.rounds,
                "読み替えた範囲": "経路A = 塊に焼いた行(出典と sha256 と有効期間つき)、"
                                  "経路B = 文章から取り出した数値。経路B が塊そのものに由来する"
                                  "場合は 2 経路が独立でないので、見えるのは転記の壊れまで"}

    def text(self) -> str:
        """同じ入力には同じバイト列。これが判定の結果そのもの。"""
        return json.dumps(self.as_dict(), ensure_ascii=False) + "\n"

    def sha256(self) -> str:
        return sha256_of_text(self.text())


def check(pack: list, decl: Declaration, body: str) -> Check:
    """5 段を通した Check を返す(通れば counts() と table() が使える)。"""
    return Check(list(pack), decl, body).run()


def verify(pack: list, decl: Declaration, body: str) -> dict:
    """同じ入力から 2 回判定して、返したバイト列の sha256 が一致するかを見る。"""
    a = check(pack, decl, body)
    if not a.report.ok:
        return {"ok": False, **a.report.as_dict()}
    b = check(pack, decl, body)
    same = a.sha256() == b.sha256()
    out = {"ok": same, "stage": DONE, "判定した回数": a.rounds + b.rounds,
           "sha256": a.sha256(), "2 回目の sha256": b.sha256(), "一致": same, **a.counts()}
    if not same:
        out["pending"] = [Pending("2 回目の判定でバイト列が不一致",
                                  "同じ入力から 2 回判定して、返したバイト列の sha256 が違う"
                                  ).as_dict()]
    return out


def all_grounded(c: Check) -> bool:
    """取り出せた数値が 1 件以上あり、その全部が接地し、読めない表記が無いか。"""
    counts, d = c.counts(), c.denominator()
    return (counts[GROUNDED] == d["文章から取り出せた数値"] > 0
            and d["取り出せなかった表記"] == 0)


# ---------------------------------------------------------------- CLI

def _body_of(args) -> str:
    if args.text == "-":
        return sys.stdin.read()
    return Path(args.text).read_text(encoding="utf-8-sig")


def _load(args) -> tuple:
    return load_pack(args.pack), Declaration.load(args.decl), _body_of(args)


def _cli_check(args) -> int:
    pack, decl, body = _load(args)
    c = check(pack, decl, body)
    if not c.report.ok:
        print(json.dumps(c.as_dict(), ensure_ascii=False))
        return 3
    sys.stdout.write(c.text())
    return 0 if all_grounded(c) else 3


def _cli_verify(args) -> int:
    pack, decl, body = _load(args)
    out = verify(pack, decl, body)
    print(json.dumps(out, ensure_ascii=False))
    return 0 if out["ok"] else 3


TEMPLATE = [
    {"selector": "保険料率_甲 / 地域=地域A", "alias": "保険料率_甲|甲の料率",
     "unit": "%|‰", "scale": "そのまま|10分の1", "period": "2026-06-01", "rounding": "小数2桁"},
    {"selector": "限度額_丁 / 区分=区分1", "alias": "限度額_丁",
     "unit": "円|千円", "scale": "そのまま|千倍", "period": "2026-06-01", "rounding": "整数"},
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
                      "塊の列": list(PACK_COLUMNS), "判定": list(VERDICTS),
                      "倍率の名前": list(SCALES), "丸めの名前": list(ROUNDINGS),
                      "理由コード": list(REASONS)}, ensure_ascii=False))
    return 0


def main(argv: "list | None" = None) -> int:
    p = argparse.ArgumentParser(
        description="AI へ渡した塊と、返ってきた文章を突き合わせる"
                    "(どちらが正しいとも決めない。許容誤差・訂正文・塊の外へ引き直す経路は無い)")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, help_text, fn in (("check", "4 値に分けて件数と分母の内訳を返す", _cli_check),
                                ("verify", "2 回判定して sha256 の一致を見る", _cli_verify)):
        s = sub.add_parser(name, help=help_text)
        s.add_argument("pack", help="AI へ渡した塊(text / JSON / CSV)")
        s.add_argument("text", help="返ってきた文章(ファイル、- で標準入力)")
        s.add_argument("--decl", required=True, help="比べる対象の宣言表(CSV / JSON)")
        s.set_defaults(func=fn)
    i = sub.add_parser("init", help="宣言表のひな型を書き出す")
    i.add_argument("path")
    i.set_defaults(func=_cli_init)
    args = p.parse_args(argv)
    try:
        return args.func(args)
    except (DeclError, CheckError) as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError) as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
