"""intake_triage の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 仕分けの結果は 2 通りしかない。
  (a) 全ての行がちょうど 1 つの分類に入り、どの行の分類もその行の列の最悪値と一致する
  (b) 行は 1 つも分類されず、理由コードが返る
どちらの場合も、この部品は値を 1 つも書き換えず、ファイルを 1 つも開かない。

入力は乱数で作る。まず宣言どおりの行を作り、15 通りから 1 つ引いて 1 か所だけ壊す(「壊さない」も同じ
確率で引く。全角の数字 / 桁区切りのカンマ / 範囲の外 / 空欄 / 長さが違う / 桁あふれ / 日付の区切り /
暦に無い日 / 型と違う / 識別子の重複 / 余分な列 / 型の名前を空に / 値域の宣言を空に / 知らない直し方)。
さらに各列の repair の宣言を乱数で付け外しして、**同じ値のまま 2 本目と 3 本目が入れ替わる**ところまで
含める。(a) と (b) の両方を十分に通すため。derandomize=True で毎回同じ入力列を使い、database=None で
見つけた例を保存しない。

判定は intake_triage の関数を使わず、このテストの中で別に書く(型・値域・覆う違反の対応表)。
道具自身の判定が壊れても、このテストで気づけるようにするため。
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import intake_triage as T  # noqa: E402

KEY = "列1"

# 仕様表(型と値域は固定、repair の宣言だけ乱数で動かす)
DECLARED = {
    "列1": ("コード", "長さ: 4", True, ("", "先頭をゼロで埋める")),
    "列2": ("金額", "範囲: -1000..1000", True, ("", "印字は符号なし", "桁区切りのカンマを外す")),
    "列3": ("文字列", "長さ上限: 8", True, ("", "空欄を 0 とみなす")),
    "列4": ("日付", "形: YYYYMMDD", True, ("", "区切りを外して 8 桁に")),
    "列5": ("文字列", "制限なし", False, ("",)),
}

# 直し方の名前が覆うと言っている違反(このテストの中に別に書き写す)
COVERS = {
    "": set(),
    "先頭をゼロで埋める": {"長さが違う"},
    "印字は符号なし": {"範囲の外"},
    "桁区切りのカンマを外す": {"型と違う"},
    "空欄を 0 とみなす": {"必要な値が空"},
    "区切りを外して 8 桁に": {"形が違う"},
}

_HALF_DIGITS = re.compile(r"\A[0-9]+\Z")
_HALF_AMOUNT = re.compile(r"\A[+-]?[0-9]+(?:\.[0-9]+)?\Z")
_EIGHT = re.compile(r"\A([0-9]{4})([0-9]{2})([0-9]{2})\Z")


def 違反(column: str, value: str) -> str:
    """このテストの中で別に書いた判定(型 → 値域の順)。"""
    type_name, domain, required, _ = DECLARED[column]
    v = value.strip()
    if v == "":
        return "必要な値が空" if required else ""
    if column == "列1":
        if not _HALF_DIGITS.match(v):
            return "型と違う"
        return "" if len(v) == 4 else "長さが違う"
    if column == "列2":
        if not _HALF_AMOUNT.match(v):
            return "型と違う"
        return "" if Decimal(-1000) <= Decimal(v) <= Decimal(1000) else "範囲の外"
    if column == "列3":
        return "" if len(v) <= 8 else "桁あふれ"
    if column == "列4":
        if not re.match(r"\A[0-9/-]+\Z", v):
            return "型と違う"
        m = _EIGHT.match(v)
        if not m:
            return "形が違う"
        y, mo, d = (int(x) for x in m.groups())
        last = [31, 29 if (y % 4 == 0 and y % 100) or y % 400 == 0 else 28,
                31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        return "" if 1 <= mo <= 12 and 1 <= d <= last[mo - 1] else "形が違う"
    return ""


# -- 入力 ------------------------------------------------------------------------

良い金額 = st.integers(-1000, 1000).map(str)
良い文字 = st.text(alphabet=st.sampled_from(list("あいうABC012 ")), min_size=1, max_size=8)
良い日 = st.tuples(st.integers(2000, 2099), st.integers(1, 12), st.integers(1, 28)).map(
    lambda t: f"{t[0]:04d}{t[1]:02d}{t[2]:02d}")

壊し方 = st.sampled_from(["壊さない", "全角の数字", "桁区切りのカンマ", "範囲の外", "空欄",
                          "長さが違う", "桁あふれ", "日付の区切り", "暦に無い日", "型と違う",
                          "識別子の重複", "余分な列", "型の名前を空に", "値域の宣言を空に",
                          "知らない直し方"])


@st.composite
def 入力(draw: st.DrawFn) -> dict:
    n = draw(st.integers(1, 4))
    base = draw(st.integers(0, 9000))          # 識別子は重ならないように連番で作る
    codes = [f"{base + i:04d}" for i in range(n)]
    rows = [{"列1": codes[i], "列2": draw(良い金額), "列3": draw(良い文字),
             "列4": draw(良い日), "列5": draw(st.one_of(st.just(""), 良い文字))}
            for i in range(n)]
    repairs = {c: draw(st.sampled_from(DECLARED[c][3])) for c in DECLARED}
    spec = [{"column": c, "type": DECLARED[c][0], "domain": DECLARED[c][1],
             "required": "○" if DECLARED[c][2] else "", "repair": repairs[c],
             "source": "合成(架空)"} for c in DECLARED]

    kind = draw(壊し方)                 # 1 か所だけ壊す(「壊さない」も同じ確率で引く)
    event(kind)
    i = draw(st.integers(0, n - 1))
    if kind == "全角の数字":
        rows[i]["列2"] = "１２３"
    elif kind == "桁区切りのカンマ":
        rows[i]["列2"] = "1,200"
    elif kind == "範囲の外":
        rows[i]["列2"] = draw(st.integers(1001, 99999)).__str__()
    elif kind == "空欄":
        rows[i][draw(st.sampled_from(["列1", "列2", "列3", "列4"]))] = ""
    elif kind == "長さが違う":
        rows[i]["列1"] = draw(st.sampled_from(["1", "123", "12345"]))
    elif kind == "桁あふれ":
        rows[i]["列3"] = "長" * draw(st.integers(9, 12))
    elif kind == "日付の区切り":
        d = rows[i]["列4"]
        rows[i]["列4"] = f"{d[:4]}-{d[4:6]}-{d[6:]}"
    elif kind == "暦に無い日":
        rows[i]["列4"] = rows[i]["列4"][:4] + "0931"
    elif kind == "型と違う":
        rows[i]["列1"] = "00A1"
    elif kind == "識別子の重複":
        rows[i]["列1"] = rows[0]["列1"]
        if n == 1:
            rows.append(dict(rows[0]))
    elif kind == "余分な列":
        rows[i]["列6"] = "1"
    elif kind == "型の名前を空に":
        spec[draw(st.integers(0, 4))]["type"] = ""
    elif kind == "値域の宣言を空に":
        spec[draw(st.integers(0, 4))]["domain"] = ""
    elif kind == "知らない直し方":
        spec[draw(st.integers(0, 4))]["repair"] = "近い値に寄せる"
    return {"rows": rows, "spec": spec, "repairs": repairs, "kind": kind}


@settings(max_examples=300, derandomize=True, database=None, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(t=入力())
def test_いつも成り立つこと_最悪値で分類されるか_理由コードが返るか(t: dict) -> None:
    before = json.dumps(t["rows"], ensure_ascii=False, sort_keys=True)
    with tempfile.TemporaryDirectory() as d:
        triage = T.triage(t["rows"], T.Spec.of(t["spec"]), KEY)
        r = triage.report
        if r.ok:
            event("(a) 最悪値で分類された")
            assert r.stage == T.DONE and r.pending == ()
            results = triage.results
            assert len(results) == len(t["rows"]) == r.rows
            assert sum(r.counts.values()) == len(t["rows"])
            for row, given_row in zip(results, t["rows"]):
                # 期待する分類を、このテストの中で別に組み立てる
                want = T.PASSES
                detail = {}
                for column in DECLARED:
                    v = 違反(column, given_row.get(column, ""))
                    if not v:
                        continue
                    judged = (T.REPAIRABLE if v in COVERS[t["repairs"][column]]
                              else T.JUDGMENT)
                    detail[column] = (v, judged)
                    if T.WORST[judged] > T.WORST[want]:
                        want = judged
                assert row.judgment == want
                assert {v.column: (v.violation, v.judgment) for v in row.violations} == detail
                for v in row.violations:
                    assert v.value == given_row.get(v.column, "").strip()   # 値は書き換えない
                    assert (v.repair != "") == (v.judgment == T.REPAIRABLE)
            # 率は分母の説明と一緒にしか出てこない
            share = triage.share()
            assert share["判定した行"] == len(t["rows"]) and share["分母に含めたもの"]
            if all(row.judgment == T.PASSES for row in results):
                assert triage.handoff() == [dict(x) for x in t["rows"]]
            else:
                try:
                    triage.handoff()
                    raise AssertionError("そのまま通る以外の行があるのに渡ってきた")
                except T.TriageError:
                    pass
        else:
            event("(b) 行は 1 つも分類されず理由コードが返った")
            assert r.pending and all(p.reason in T.REASONS for p in r.pending)
            assert r.stage in (T.SPEC, T.MATCH)
            assert sum(r.counts.values()) == 0
            for call in (lambda: triage.results, triage.violations, triage.handoff):
                try:
                    call()
                    raise AssertionError("仕分けが通っていないのに返ってきた")
                except T.TriageError:
                    pass
        assert list(Path(d).iterdir()) == []      # この部品からファイルは開かれない
    assert json.dumps(t["rows"], ensure_ascii=False, sort_keys=True) == before
