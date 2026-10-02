"""cross_route — 同じ値を 2 つの経路で取った行を突き合わせる部品。

原本から値を取り出して行にする部品(source_pin)は、その値が原本の指定場所に書いてあることまでしか
言えない。取り出した値が合っているかは原本の中では確かめられないので、次の手は同じ値を別の経路で
もう 1 回取って突き合わせることになる。

そこで値が違ったとき、人がまずやるのは「どちらが正しいか」を選ぶことだが、私の記録に残っている
食い違いの実例は「別の制度の数字を同じ名前で並べていた」= 指しているものが違っただけだった。
だからこの部品は、値を比べる前に **同じものを指しているか**(対象・負担区分 = scope、単位 = unit、
正規化の名前 = normalizer)を検査し、宣言が足りない行は比べずに止める。

経路 1 本の行が持つ列:

    key            何の値か(2 経路の突き合わせはこの名前で行う)
    value          その経路が出した値(normalizer を通して比べる)
    unit           単位。一方でも空欄 / 不一致なら比べない
    scope          **その値が指しているもの**(対象の範囲・負担区分など)を呼び出し側が文字列で宣言する。
                   部品は業種の語彙を持たない。一方でも空欄なら比べない、違っていれば比べない
    source_file    出典のファイル
    source_sha256  出典の sha256(現物は見ない = source_pin の仕事。報告に載せるために持つ)
    normalizer     value を比較の形にする正規化の名前(+ で連ねる)。**既定は持たない**
    captured_at    取り出した時刻
    raw_text       原本にある生の文字(持ち越すだけ。比較には使わない)
    locator        原本の中の場所(持ち越すだけ。比較には使わない)
    note           覚え書き

判定は 4 値。

    agree          両経路にちょうど 1 行ずつあり、指しているものが同じで、正規化後の value が一致した
    disagree       指しているものは同じだが、正規化後の value が違った
    single_route   片方の経路にしか無い(= 照合できていない)
    incomparable   比べられない(scope・unit の不一致 / 空欄、normalizer 空欄など)

**disagree のときにどちらかを正として返す経路を持たない。** 優先する経路を選ぶ引数も、片方へ落ちる
引数も無い。get(key) は agree の行だけ値を返し、それ以外は理由コードで止める。

rate() は一致率を出すが、**分子分母だけを返さない**。4 判定の件数と、分母に何を含めたかの文字列を
必ず同時に返す(照合できていない行を分母から落とせない)。

値そのものの正しさ・どちらの経路が信頼できるかは判定しない(同じものを指しているか、指しているなら
合うかだけ)。標準ライブラリのみ(csv / json / hashlib / unicodedata / decimal / argparse)。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

# 比較に使う列(どれかが空なら比べない)と、持ち越すだけの列
REQUIRED_COLUMNS = ("key", "value", "unit", "scope", "source_file", "source_sha256",
                    "normalizer", "captured_at")
CARRIED_COLUMNS = ("raw_text", "locator", "note")   # source_pin のピン行から持ち越すだけ
COLUMNS = REQUIRED_COLUMNS + CARRIED_COLUMNS

AGREE, DISAGREE, SINGLE, INCOMPARABLE = "agree", "disagree", "single_route", "incomparable"
JUDGMENTS = (AGREE, DISAGREE, SINGLE, INCOMPARABLE)

# 止まる理由コード(この 9 つで全部)
REASONS = {
    "経路名が同じ": "2 つの経路に同じ名前が付いている。報告のどちらの列がどの経路か決まらない",
    "同じ key が同じ経路に 2 行": "片方の経路に同じ key が 2 行ある。その経路の値が表から決まらない",
    "列が足りない": "その行が経路の行として読めない(必要な列が空 / 登録されていない normalizer 名)",
    "normalizer 空欄": "正規化の名前が書かれていない。部品は既定の正規化を持たないので比べない",
    "normalizer を通せない": "名前の正規化が value を扱えない(数として読めない / 年月日として読めない)",
    "scope 空欄": "その値が何を指しているかの宣言が無い。値が合うかより先にここで止める",
    "scope 不一致": "2 経路が別のものを指している(対象・負担区分が違う)。値を比べない",
    "unit 不一致": "単位が違う、または一方が空欄。値を比べない",
    "突合前に get を呼んだ": "crosscheck() を通る前に値を取りに来た",
}
SINGLE_REASON = "片方の経路にしか無い"
CHAIN_SEP = "+"


class TableError(ValueError):
    """経路の表そのものが読めない(見出しの列が無い / CSV・JSON として壊れている / 経路名が同じ)。"""


class CrossError(Exception):
    """get() が値を返せない。reason に理由コード(または判定)が入る。"""

    def __init__(self, message: str, reason: str = "") -> None:
        super().__init__(message)
        self.reason = reason


# ---------------------------------------------------------------- 正規化(名前で呼ぶ。既定は無い)

def _decimal(s: str, what: str) -> Decimal:
    try:
        return Decimal(s)
    except InvalidOperation as e:
        raise ValueError(f"{what} を通したが数として読めない: {s!r}") from e


def _as_is(s: str) -> str:
    return s.strip()


def _nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s).strip()


def _drop_comma(s: str) -> str:
    return s.replace(",", "").replace("，", "").strip()


def _percent(s: str) -> str:
    return format(_decimal(_drop_comma(s.strip().rstrip("%").rstrip("％").strip()), "パーセント"), "f")


def _yen(s: str) -> str:
    return format(_decimal(_drop_comma(s.strip().rstrip("円").strip()), "円"), "f")


def _trim_zeros(s: str) -> str:
    """末尾の 0 をそろえる(9.310 と 9.31 を同じ形にする)。桁を落とす丸めはしない。"""
    return format(_decimal(_drop_comma(s.strip()), "桁そろえ").normalize(), "f")


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
               "パーセント": _percent, "円": _yen, "桁そろえ": _trim_zeros, "日付": _date}


def normalize(value: str, chain: str) -> str:
    """normalizer の名前(+ で連ねる)を左から順に適用する。登録されていない名前は ValueError。"""
    out = value
    for name in [p.strip() for p in chain.split(CHAIN_SEP)]:
        fn = NORMALIZERS.get(name)
        if fn is None:
            raise ValueError(f"登録されていない normalizer: {name!r}")
        out = fn(out)
    return out


def known_chain(chain: str) -> bool:
    return bool(chain.strip()) and all(p.strip() in NORMALIZERS for p in chain.split(CHAIN_SEP))


def sha256_of(path: "str | Path") -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- 経路の行

@dataclass(frozen=True)
class Row:
    key: str = ""
    value: str = ""
    unit: str = ""
    scope: str = ""
    source_file: str = ""
    source_sha256: str = ""
    normalizer: str = ""
    captured_at: str = ""
    raw_text: str = ""
    locator: str = ""
    note: str = ""

    @classmethod
    def of(cls, row: dict) -> "Row":
        return cls(**{k: str(row.get(k, "") or "").strip() for k in COLUMNS})

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in COLUMNS}

    def source(self) -> str:
        """報告に載せる出典(ファイル + 指紋の頭)。"""
        sha = f" {self.source_sha256[:12]}" if self.source_sha256 else ""
        return f"{self.source_file}{sha}" if self.source_file else "(出典の列が空)"


@dataclass(frozen=True)
class Route:
    """経路 1 本。name は報告の列の見出しになる(経路名が同じ 2 本は突き合わせない)。"""

    name: str
    rows: tuple = ()

    def __len__(self) -> int:
        return len(self.rows)

    @classmethod
    def load(cls, path: "str | Path", name: "str | None" = None) -> "Route":
        p = Path(path)
        text = p.read_text(encoding="utf-8-sig")
        if p.suffix.lower() == ".json":
            try:
                data = json.loads(text)
            except json.JSONDecodeError as e:
                raise TableError(f"JSON として読めない: {e}") from e
            rows = data.get("rows", data) if isinstance(data, dict) else data
            if not isinstance(rows, list):
                raise TableError("JSON は経路の行の配列(または rows を持つ object)で書く")
        else:
            reader = csv.DictReader(text.splitlines())
            head = reader.fieldnames or []
            missing = [c for c in REQUIRED_COLUMNS if c not in head]
            if missing:
                raise TableError(f"見出しの列が足りない: {' / '.join(missing)}")
            rows = list(reader)
        return cls(name or p.stem, tuple(Row.of(r) for r in rows))

    def by_key(self) -> dict:
        out: dict = {}
        for r in self.rows:
            out.setdefault(r.key, []).append(r)
        return out


# ---------------------------------------------------------------- 突合の結果

@dataclass(frozen=True)
class Result:
    key: str
    judgment: str
    reason: str = ""
    detail: str = ""
    a: "Row | None" = None
    b: "Row | None" = None
    value: str = ""        # agree のときだけ(正規化後の値)
    value_a: str = ""      # 正規化を通せた場合だけ
    value_b: str = ""

    @property
    def ok(self) -> bool:
        return self.judgment == AGREE

    def as_dict(self) -> dict:
        d = {"key": self.key, "judgment": self.judgment}
        if self.reason:
            d["reason"] = self.reason
        if self.detail:
            d["detail"] = self.detail
        if self.value:
            d["value"] = self.value
        return d


@dataclass(frozen=True)
class Got:
    """agree の行だけが返る。両経路の出典が必ず一緒に付いてくる。"""

    key: str
    value: str
    unit: str
    scope: str
    route_a: str
    route_b: str
    source_a: str
    source_b: str
    sha256_a: str
    sha256_b: str
    normalizer_a: str
    normalizer_b: str

    def as_dict(self) -> dict:
        return {"key": self.key, "value": self.value, "unit": self.unit, "scope": self.scope,
                "routes": [self.route_a, self.route_b],
                "sources": [{"route": self.route_a, "source_file": self.source_a,
                             "source_sha256": self.sha256_a, "normalizer": self.normalizer_a},
                            {"route": self.route_b, "source_file": self.source_b,
                             "source_sha256": self.sha256_b, "normalizer": self.normalizer_b}]}


# ---------------------------------------------------------------- 突合(順序を固定する)

class Cross:
    """2 経路を持ち、crosscheck() を通ってから get() / report() / rate() が使える。

    突合の順序は固定。① normalizer の名前を通して value を正規化する ② 指しているものが同じかを
    見る(scope・unit) ③ そこを通った組だけ value を比べる。② が ③ より先にあるのが要点で、
    値が合うかより先に「同じものを指しているか」を検査する。
    """

    def __init__(self, a: Route, b: Route) -> None:
        if a.name == b.name:
            raise TableError(f"経路名が同じ: {a.name!r}(報告のどちらの列がどの経路か決まらない)")
        self.a, self.b = a, b
        self._results: "list | None" = None

    @property
    def results(self) -> list:
        if self._results is None:
            raise CrossError("crosscheck() を通る前に値を取りに来た", "突合前に get を呼んだ")
        return self._results

    # -- 1 組の判定 ------------------------------------------------

    def _judge(self, key: str, a_rows: list, b_rows: list) -> Result:
        if len(a_rows) > 1 or len(b_rows) > 1:
            which = self.a.name if len(a_rows) > 1 else self.b.name
            n = max(len(a_rows), len(b_rows))
            return Result(key, INCOMPARABLE, "同じ key が同じ経路に 2 行",
                          f"経路 {which} に {key} が {n} 行ある")
        if not a_rows or not b_rows:
            only = self.a.name if a_rows else self.b.name
            missing = self.b.name if a_rows else self.a.name
            return Result(key, SINGLE, SINGLE_REASON,
                          f"{only} にはあるが {missing} に無い(照合できていない)",
                          a_rows[0] if a_rows else None, b_rows[0] if b_rows else None)
        a, b = a_rows[0], b_rows[0]

        def out(reason: str, detail: str, va: str = "", vb: str = "") -> Result:
            return Result(key, INCOMPARABLE, reason, detail, a, b, "", va, vb)

        # 列が足りない(比較に使う列が空)
        for name, row in ((self.a.name, a), (self.b.name, b)):
            for col in ("value", "source_file", "captured_at"):
                if not getattr(row, col):
                    return out("列が足りない", f"経路 {name} の {col} が空")
        # ① normalizer の名前を通して value を正規化する
        for name, row in ((self.a.name, a), (self.b.name, b)):
            if not row.normalizer:
                return out("normalizer 空欄", f"経路 {name} に正規化の名前が無い(既定は持たない)")
            if not known_chain(row.normalizer):
                return out("列が足りない",
                           f"経路 {name} の登録されていない normalizer: {row.normalizer!r}"
                           f"(登録済 {' / '.join(NORMALIZERS)})")
        try:
            va = normalize(a.value, a.normalizer)
        except ValueError as e:
            return out("normalizer を通せない", f"経路 {self.a.name}: {e}")
        try:
            vb = normalize(b.value, b.normalizer)
        except ValueError as e:
            return out("normalizer を通せない", f"経路 {self.b.name}: {e}", va)
        # ② 同じものを指しているか(値が合うかより先に見る)
        if not a.scope or not b.scope:
            empty = self.a.name if not a.scope else self.b.name
            return out("scope 空欄", f"経路 {empty} に scope の宣言が無い", va, vb)
        if a.scope != b.scope:
            return out("scope 不一致",
                       f"{self.a.name} は {a.scope!r}、{self.b.name} は {b.scope!r}", va, vb)
        if not a.unit or not b.unit or a.unit != b.unit:
            return out("unit 不一致",
                       f"{self.a.name} は {a.unit!r}、{self.b.name} は {b.unit!r}", va, vb)
        # ③ ここを通った組だけ value を比べる
        if va == vb:
            return Result(key, AGREE, "", "", a, b, va, va, vb)
        return Result(key, DISAGREE, "",
                      f"{self.a.name} は {va}、{self.b.name} は {vb}(どちらを正とするかは返さない)",
                      a, b, "", va, vb)

    def crosscheck(self) -> list:
        """両経路の key の和集合を 1 行ずつ判定する。key が空の行は 列が足りない で残す。"""
        ga, gb = self.a.by_key(), self.b.by_key()
        keys = list(dict.fromkeys([r.key for r in self.a.rows] + [r.key for r in self.b.rows]))
        out: list = []
        for k in keys:
            if not k:
                for name, rows in ((self.a.name, ga.get("", [])), (self.b.name, gb.get("", []))):
                    for _ in rows:
                        out.append(Result("(key 空欄)", INCOMPARABLE, "列が足りない",
                                          f"経路 {name} に key が空の行がある"))
                continue
            out.append(self._judge(k, ga.get(k, []), gb.get(k, [])))
        self._results = out
        return out

    # -- 引き当て(どちらかを正とする経路を持たない) ----------------

    def get(self, key: str) -> Got:
        """agree の行だけ値を返す。disagree・single_route・incomparable は止まる。"""
        rows = [r for r in self.results if r.key == key]
        if not rows:
            raise CrossError(f"どちらの経路にも無い key: {key}", "どちらの経路にも無い")
        r = rows[0]
        if r.judgment != AGREE:
            tail = f": {r.reason}" if r.reason else ""
            raise CrossError(f"突合を通らない key: {key}({r.judgment}{tail})",
                             r.reason or r.judgment)
        a, b = r.a, r.b
        return Got(key, r.value, a.unit, a.scope, self.a.name, self.b.name,
                   a.source_file, b.source_file, a.source_sha256, b.source_sha256,
                   a.normalizer, b.normalizer)

    # -- 報告 ------------------------------------------------------

    def report(self) -> list:
        """突合表。key × 経路 A の値 / 経路 B の値 / 判定 / 理由コード / 両経路の出典。"""
        out: list = []
        for r in self.results:
            out.append({
                "key": r.key,
                f"{self.a.name}_value": r.value_a or (r.a.value if r.a else ""),
                f"{self.b.name}_value": r.value_b or (r.b.value if r.b else ""),
                "judgment": r.judgment,
                "reason": r.reason,
                "detail": r.detail,
                f"{self.a.name}_source": r.a.source() if r.a else "",
                f"{self.b.name}_source": r.b.source() if r.b else "",
            })
        return out

    def report_columns(self) -> list:
        return ["key", f"{self.a.name}_value", f"{self.b.name}_value", "judgment", "reason",
                "detail", f"{self.a.name}_source", f"{self.b.name}_source"]

    def counts(self) -> dict:
        c = Counter(r.judgment for r in self.results)
        return {j: c.get(j, 0) for j in JUDGMENTS}

    def rate(self) -> dict:
        """一致率を出すが、分子分母だけは返さない。4 判定の件数と分母の説明を必ず一緒に返す。"""
        c = self.counts()
        rows = len(self.results)
        compared = c[AGREE] + c[DISAGREE]
        unchecked = c[SINGLE] + c[INCOMPARABLE]
        return {**c, "rows": rows, "compared": compared, "unchecked": unchecked,
                "一致率_比べられた行のみ": _ratio(c[AGREE], compared),
                "一致率_全ての行": _ratio(c[AGREE], rows),
                "分母に含めたもの": (
                    f"比べられた行のみ = agree {c[AGREE]} + disagree {c[DISAGREE]} = {compared}"
                    f"(照合できていない {unchecked} 行 = 片系統だけ {c[SINGLE]}"
                    f" + 比べられない {c[INCOMPARABLE]} を除いた分母)"
                    f" / 全ての行 = {rows}(照合できていない {unchecked} 行を含む分母)")}


def _ratio(n: int, d: int) -> str:
    if d == 0:
        return "分母が 0"
    return format((Decimal(n) / Decimal(d)).quantize(Decimal("0.0001")), "f")


def crosscheck(a: Route, b: Route) -> Cross:
    """2 経路を突き合わせた Cross を返す(crosscheck 済みなので get() が使える)。"""
    c = Cross(a, b)
    c.crosscheck()
    return c


# ---------------------------------------------------------------- CLI

def _load_pair(args) -> Cross:
    a = Route.load(args.route_a, args.name_a)
    b = Route.load(args.route_b, args.name_b)
    return crosscheck(a, b)


def _cli_check(args) -> int:
    c = _load_pair(args)
    cnt = c.counts()
    stopped = cnt[DISAGREE] + cnt[INCOMPARABLE] > 0
    print(json.dumps({"ok": not stopped, "routes": [c.a.name, c.b.name], **cnt,
                      "rows": [r.as_dict() for r in c.results]}, ensure_ascii=False))
    return 3 if stopped else 0


def _cli_report(args) -> int:
    c = _load_pair(args)
    if args.format == "csv":
        w = csv.DictWriter(sys.stdout, fieldnames=c.report_columns(), lineterminator="\n")
        w.writeheader()
        w.writerows(c.report())
    else:
        print(json.dumps({"ok": True, "columns": c.report_columns(), "rows": c.report()},
                         ensure_ascii=False))
    return 0


def _cli_rate(args) -> int:
    print(json.dumps({"ok": True, **_load_pair(args).rate()}, ensure_ascii=False))
    return 0


def _cli_get(args) -> int:
    c = _load_pair(args)
    try:
        print(json.dumps({"ok": True, **c.get(args.key).as_dict()}, ensure_ascii=False))
    except CrossError as e:
        print(json.dumps({"ok": False, "key": args.key, "reason": e.reason, "detail": str(e)},
                         ensure_ascii=False))
        return 3
    return 0


def _cli_init(args) -> int:
    p = Path(args.path)
    if p.exists():
        raise TableError(f"すでにある: {p}(上書きしない)")
    example = Row(key="突き合わせたい値の名前", unit="円", scope="対象と負担区分を言葉で宣言する",
                  normalizer="そのまま", note="scope が空欄の行は値を比べずに止まる")
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(COLUMNS))
        w.writeheader()
        w.writerow(example.as_dict())
    print(json.dumps({"ok": True, "wrote": str(p), "columns": list(COLUMNS)}, ensure_ascii=False))
    return 0


def main(argv: "list | None" = None) -> int:
    p = argparse.ArgumentParser(
        description="同じ値を 2 経路で取った行を突き合わせる(どちらが正しいかは選ばない)")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, help_text, fn in (("check", "4 値で判定して件数と行を出す", _cli_check),
                                ("report", "突合表を出す(CSV / JSON)", _cli_report),
                                ("rate", "一致率と 4 判定の件数と分母の説明を出す", _cli_rate)):
        s = sub.add_parser(name, help=help_text)
        s.add_argument("route_a")
        s.add_argument("route_b")
        s.add_argument("--name-a", dest="name_a", help="経路 A の名前(既定 = ファイル名)")
        s.add_argument("--name-b", dest="name_b", help="経路 B の名前(既定 = ファイル名)")
        if name == "report":
            s.add_argument("--format", choices=("csv", "json"), default="json")
        s.set_defaults(func=fn)
    g = sub.add_parser("get", help="agree の行だけ返す")
    g.add_argument("route_a")
    g.add_argument("route_b")
    g.add_argument("key")
    g.add_argument("--name-a", dest="name_a")
    g.add_argument("--name-b", dest="name_b")
    g.set_defaults(func=_cli_get)
    i = sub.add_parser("init", help="経路の表の見出しを書き出す")
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
