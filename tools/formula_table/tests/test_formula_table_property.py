"""formula_table の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 評価の結果は 2 通りしかない。
  (a) その日付・時点で 1 行に決まった式の版の、rounding 列に書いた丸めで丸めた値が、出典付きで返る
  (b) 値は返らず、理由コード(8 つのどれか)が返る
丸めが空欄の版・registry に無い名前の版からは値が返らない。入力が数として読めないときは、
どちらでもなく表か引数の誤り(TableError)になる。

入力は乱数で作る。式の表は「対象」の版を 1〜3 行(有効期間・公表時点・priority・丸めの名前を乱数で振る)と、
「対象」から formula: で引かれる「下位」1 行。値の表は「合成単価」を 1〜2 行。式は四則・abs・min・max・
条件式を乱数で組む。入力の項目は数の文字列を主にし(端数ちょうど 0.5 などの境目を混ぜる)、
半分くらいの回で 1 か所を困る値(欠け・float・真偽値・数でない文字列)に差し替える。
金額は 0 以上で作る(負の金額で端数をどちらへ寄せるかは README に書いていないので、ここでは測らない)。
NaN / Infinity / sNaN と全角数字の文字列も困る値に入れる(どちらも数として読まず TableError になる。README)。

期待値は道具の関数(evaluate の中身・_pick・ROUNDINGS・check_syntax)を使わず、このテストの中で別に作る。
版の引き当て、式の計算(乱数で組んだ木をそのまま Decimal で計算する)、丸め(Fraction と math.floor / ceil)を
ここで書き直している。道具の側が壊れても、このテストで気づけるようにするため。
derandomize=True で毎回同じ入力列を使い、database=None で見つけた例を保存しない(この版の hypothesis は実行した場所に .hypothesis/ を作るが、git と公開側への export では除外される)。
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path

from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import formula_table as F  # noqa: E402

# README の「丸めの registry」の 4 つ。期待値の丸めはこの名前ごとにテストの中で書く
丸めの名前 = ("50銭以下切捨て", "1円未満切捨て", "円未満四捨五入", "丸めない")
# 空欄と registry に無い名前を混ぜる(sampled_from は先頭を選びやすいので、先頭は普通の名前にする)
丸めの欄 = ["円未満四捨五入", "50銭以下切捨て", "四捨五入", "1円未満切捨て", "丸めない", "",
           "円未満四捨五入", "50銭以下切捨て", "1円未満切捨て", "丸めない"]

定数 = ["1", "2", "3", "0.5", "1.5", "100", "200", "8.13", "0.001"]   # 0 は入力の側から入る
始まり = ["2025-04-01", "", "2024-04-01", "2026-04-01"]
終わり = ["", "2025-04-01", "2026-04-01", "2027-04-01"]
公表 = ["2024-01-01", "2025-02-01", "2026-02-10"]
公表の終わり = ["", "", "2026-02-10"]
引く日 = ["2025-04-01", "2026-04-01", "2024-04-01", "2026-03-31", "2027-06-01", "2025-03-31", "2024-03-31"]
時点 = [None, "2026-02-09", None, "2026-02-10", None, "2025-01-31", "2027-01-01"]

欠け = object()   # case にその項目を入れない印
INPUTS = {"報酬": ("case", "報酬月額"), "率": ("case", "料率"),
          "単価": ("value", "合成単価"), "下位値": ("formula", "下位")}


# ---------------------------------------------------------------- 式の木(乱数で組み、文字列にも数にもする)

def 木(names: list[str], depth: int = 2) -> st.SearchStrategy:
    """深さ depth までの式の木。葉は入力の名前か定数。"""
    葉 = st.one_of(st.sampled_from(names).map(lambda n: ("名", n)),
                  st.sampled_from(定数).map(lambda c: ("数", c)))
    if depth == 0:
        return 葉
    子 = 木(names, depth - 1)
    return st.one_of(
        葉,
        st.tuples(st.sampled_from(["+", "*", "/", "min", "max", "absdiff"]), 子, 子),
        st.tuples(st.just("if"), st.sampled_from(["<", "<=", ">", ">=", "==", "!="]), 子, 子, 子, 子))


def 書く(t: tuple) -> str:
    op = t[0]
    if op in ("名", "数"):
        return t[1]
    if op == "if":
        _, cmp, a, b, x, y = t
        return f"({書く(x)} if {書く(a)} {cmp} {書く(b)} else {書く(y)})"
    if op == "absdiff":
        return f"abs({書く(t[1])} - {書く(t[2])})"
    if op in ("min", "max"):
        return f"{op}({書く(t[1])}, {書く(t[2])})"
    return f"({書く(t[1])} {op} {書く(t[2])})"


比べる = {"<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b,
         ">=": lambda a, b: a >= b, "==": lambda a, b: a == b, "!=": lambda a, b: a != b}


class 止まる(Exception):
    """期待: 値は返らず理由コード。top = 「対象」の版を引く段か丸めの段で止まった(理由コードまで決まる)。"""

    def __init__(self, reason: str, top: bool = False):
        super().__init__(reason)
        self.reason, self.top = reason, top


class 読めない(Exception):
    """期待: 入力が数として読めない(TableError)。"""


def 計算(t: tuple, env: dict) -> Decimal:
    op = t[0]
    if op == "名":
        return env[t[1]]
    if op == "数":
        return Decimal(t[1])
    if op == "if":
        _, cmp, a, b, x, y = t
        return 計算(x if 比べる[cmp](計算(a, env), 計算(b, env)) else y, env)
    a, b = 計算(t[1], env), 計算(t[2], env)
    if op == "absdiff":
        return abs(a - b)
    if op == "+":
        return a + b
    if op == "*":
        return a * b
    if op == "min":
        return min(a, b)
    if op == "max":
        return max(a, b)
    if b == 0:
        raise 止まる("依存先が決まらない")
    return a / b


def 丸める(name: str, x: Decimal) -> Decimal:
    """README の表の言葉どおりに書いた丸め(x は 0 以上)。"""
    q = Fraction(x)
    if name == "50銭以下切捨て":       # 端数 0.50 以下は切り捨て、0.50 を超えたら切り上げ
        return Decimal(math.ceil(q - Fraction(1, 2)))
    if name == "1円未満切捨て":
        return Decimal(math.floor(q))
    if name == "円未満四捨五入":       # 端数 0.5 は上へ
        return Decimal(math.floor(q + Fraction(1, 2)))
    return x                           # 丸めない


# ---------------------------------------------------------------- 場面(表 2 つ + 入力 + 日付)

def _d(s: str) -> date | None:
    return date.fromisoformat(s) if s else None


@dataclass
class 行:
    番号: int
    名前: str
    vf: date | None
    vt: date | None
    kf: date
    kt: date | None
    priority: int
    木: tuple = ()
    inputs: tuple = ()
    rounding: str = ""
    value: str = ""


@dataclass
class 場面:
    式の行: list[dict]
    値の行: list[dict]
    式: list[行]
    値: list[行]
    入力: dict
    日: date
    時点: date | None
    困る: str = ""


def _期間(draw: st.DrawFn, kind: str) -> dict:
    """版の期間。最初 = 開いたままの本則 / 旧版 = 2026-04-01 で閉じた本則 /
    改正版 = 2026-04-01 から有効で 2026-02-10 に公表された本則 / 乱数 = 期間も priority も乱数。"""
    if kind == "最初":
        return {"valid_from": "2024-04-01", "valid_to": "", "known_from": "2024-01-01",
                "known_to": "", "priority": "0"}
    if kind == "旧版":
        return {"valid_from": "2024-04-01", "valid_to": "2026-04-01", "known_from": "2024-01-01",
                "known_to": "", "priority": "0"}
    if kind == "改正版":
        return {"valid_from": "2026-04-01", "valid_to": "", "known_from": "2026-02-10",
                "known_to": "", "priority": "0"}
    return {"valid_from": draw(st.sampled_from(始まり)), "valid_to": draw(st.sampled_from(終わり)),
            "known_from": draw(st.sampled_from(公表)), "known_to": draw(st.sampled_from(公表の終わり)),
            "priority": draw(st.sampled_from(["10", "20", "0", "10"]))}


def _行(n: int, name: str, rec: dict, **kw) -> 行:
    return 行(n, name, _d(rec["valid_from"]), _d(rec["valid_to"]), _d(rec["known_from"]),
             _d(rec["known_to"]), int(rec["priority"]), **kw)


報酬 = st.one_of(
    st.sampled_from(["0", "1", "0.5", "1.5", "2.5", "110000", "300000", "4471.50", "4471.51", "4472.49"]),
    st.integers(0, 2_000_000).map(str),
    st.decimals(min_value=0, max_value=1_000_000, places=2).map(str))
率 = st.one_of(st.sampled_from(["8.13", "9.15", "0.5", "1", "0"]),
              st.decimals(min_value=Decimal("0.01"), max_value=Decimal("20"), places=2).map(str))
困る値 = st.sampled_from([欠け, 110000.0, 0.5, True, "", "abc", "1,000", "12円", 110000,
                          "NaN", "Infinity", "-Infinity", "sNaN", "１２３", "１.５", "1２"])


@st.composite
def 場面たち(draw: st.DrawFn) -> 場面:
    use_val, use_sub = draw(st.booleans()), draw(st.booleans())
    names = ["報酬", "率"] + (["単価"] if use_val else []) + (["下位値"] if use_sub else [])
    式の行: list[dict] = []
    式: list[行] = []
    kinds = ["旧版", "改正版"] if draw(st.booleans()) else ["最初"]
    kinds += ["乱数"] * draw(st.integers(0, 3 - len(kinds)))
    for i, kind in enumerate(kinds):
        rec = _期間(draw, kind)
        used = draw(st.lists(st.sampled_from(names), min_size=1, max_size=len(names), unique=True))
        t = draw(木(used))
        rec.update({"id": "対象", "expr": 書く(t), "rounding": draw(st.sampled_from(丸めの欄)),
                    "inputs": ";".join(f"{n}={INPUTS[n][0]}:{INPUTS[n][1]}" for n in used),
                    "known_quality": "実値", "source": f"合成の式 {i + 1}(架空)"})
        式の行.append(rec)
        式.append(_行(len(式の行), "対象", rec, 木=t, inputs=tuple(used), rounding=rec["rounding"]))
    if use_sub:
        rec = _期間(draw, "最初")
        t = draw(木(["報酬"]))
        rec.update({"id": "下位", "expr": 書く(t), "rounding": draw(st.sampled_from(丸めの欄)),
                    "inputs": "報酬=case:報酬月額", "known_quality": "実値", "source": "合成の下位式(架空)"})
        式の行.append(rec)
        式.append(_行(len(式の行), "下位", rec, 木=t, inputs=("報酬",), rounding=rec["rounding"]))
    値の行: list[dict] = []
    値: list[行] = []
    for i in range(draw(st.integers(1, 2))):
        rec = {"key": "合成単価", "valid_from": "2024-04-01" if i == 0 else "2026-04-01",
               "valid_to": draw(st.sampled_from(["", "2026-04-01"])) if i == 0 else "",
               "known_from": "2024-01-01" if i == 0 else draw(st.sampled_from(公表)),
               "known_to": "", "priority": "0", "known_quality": "実値", "source": "合成の単価表(架空)",
               "value": draw(st.one_of(st.sampled_from(["1.234", "0.5", "1000", "0"]),
                                       st.decimals(min_value=0, max_value=1000, places=3).map(str)))}
        値の行.append(rec)
        値.append(_行(i + 1, "合成単価", rec, value=rec["value"]))
    入力 = {"報酬月額": draw(報酬), "料率": draw(率)}
    困る = ""
    if draw(st.booleans()):
        k = draw(st.sampled_from(["報酬月額", "料率"]))
        v = draw(困る値)
        困る = f"{k}={'欠け' if v is 欠け else repr(v)}"
        if v is 欠け:
            del 入力[k]
        else:
            入力[k] = v
    if use_val and draw(st.integers(0, 9)) == 0:
        値の行[0]["value"] = "未定"               # 値の表に数でない値(読めない)
        値[0].value = "未定"
        困る = 困る or "値の表=未定"
    as_of = draw(st.sampled_from(時点))
    return 場面(式の行, 値の行, 式, 値, 入力, date.fromisoformat(draw(st.sampled_from(引く日))),
               date.fromisoformat(as_of) if as_of else None, 困る)


# ---------------------------------------------------------------- 期待値(道具の関数を使わずに作る)

def 引く(rows: list[行], on: date, as_of: date | None, top: bool) -> 行:
    """知識時間 → 有効時間 → 最高 priority の 1 行(README の言葉どおり)。"""
    有効 = [r for r in rows if r.vf is not None and r.vf <= on and (r.vt is None or on < r.vt)]
    if as_of is None:
        既知 = [r for r in 有効 if r.kt is None]
    else:
        既知 = [r for r in 有効 if r.kf <= as_of and (r.kt is None or as_of < r.kt)]
    if not 既知:
        raise 止まる("式の版が as_of 時点で未公表" if as_of is not None and 有効 else "依存先が決まらない", top)
    最高 = max(r.priority for r in 既知)
    候補 = [r for r in 既知 if r.priority == 最高]
    if len(候補) != 1:
        raise 止まる("依存先が決まらない", top)
    return 候補[0]


def 数にする(v: object) -> Decimal:
    if isinstance(v, (bool, float)):
        raise 止まる("float 混入")
    if isinstance(v, int):
        return Decimal(v)
    s = str(v).strip()
    if any(not ("\x00" <= ch <= "\x7f") for ch in s):   # 半角でない字を含む(README)
        raise 読めない(repr(v))
    try:
        d = Decimal(s)
    except InvalidOperation as e:
        raise 読めない(repr(v)) from e
    if d.is_nan() or d.is_infinite():   # NaN / Infinity は数として読まない(README)
        raise 読めない(repr(v))
    return d


@dataclass
class 値が返る:
    value: Decimal
    raw: Decimal
    rounding: str
    used: list


def 期待(s: 場面) -> 値が返る:
    used: list = []
    top_raw: list = []

    def 式を(fid: str, top: bool) -> Decimal:
        row = 引く([r for r in s.式 if r.名前 == fid], s.日, s.時点, top)
        if not row.rounding:
            raise 止まる("丸めが空欄", top)
        if row.rounding not in 丸めの名前:
            raise 止まる("未登録の丸めの名前", top)
        used.append(("式", fid, row.番号))
        env = {}
        for name in row.inputs:
            kind, ref = INPUTS[name]
            if kind == "case":
                if ref not in s.入力:
                    raise 止まる("入力が足りない")
                env[name] = 数にする(s.入力[ref])
            elif kind == "value":
                v = 引く([r for r in s.値 if r.名前 == ref], s.日, s.時点, False)
                used.append(("値", ref, v.番号))
                env[name] = 数にする(v.value)
            else:
                env[name] = 式を(ref, False)
        raw = 計算(row.木, env)
        if top:
            top_raw.append((raw, row.rounding))
        return 丸める(row.rounding, raw)

    v = 式を("対象", True)
    return 値が返る(v, top_raw[0][0], top_raw[0][1], used)


# ---------------------------------------------------------------- 性質テスト

@settings(max_examples=500, derandomize=True, database=None, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(s=場面たち())
def test_いつも成り立つこと_指定の丸めで丸めた値か_理由コードか(s: 場面) -> None:
    ft = F.FormulaTable.from_records(s.式の行)
    vt = F.ValueTable.from_records(s.値の行)
    try:
        want: object = 期待(s)
    except (止まる, 読めない) as e:
        want = e
    try:
        r = F.evaluate(ft, "対象", s.入力, s.日, s.時点, vt)
    except F.TableError:
        event("(c) 入力が数として読めない → TableError")
        assert isinstance(want, 読めない), (want, s.困る)
        return
    if r.ok:
        event("(a) 値が返った")
        event(f"(a) 丸め: {r.rounding}")
        assert isinstance(want, 値が返る), (want, r)
        assert Fraction(Decimal(r.value)) == Fraction(want.value)
        assert Fraction(Decimal(r.raw)) == Fraction(want.raw)
        assert r.rounding == want.rounding
        assert sorted((u.kind, u.name, u.row) for u in r.used) == sorted(want.used)
        assert all(u.source for u in r.used)
        if want.raw % 1 == Decimal("0.5"):
            event("(a) 端数ちょうど 0.5")
    else:
        event(f"(b) 理由コード: {r.reason}")
        assert r.value == "" and r.reason in F.REASONS
        assert isinstance(want, 止まる), (want, r.reason, r.detail)
        if want.top:
            assert r.reason == want.reason, (want.reason, r.reason, r.detail)
