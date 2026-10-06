"""context_pack の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 組み立ての結果は 2 通りしかない。
  (a) 必ず焼く 8 つの列が欠けなく入った塊が 1 つ返り、同じ問いから 2 回目を組み立てても同じバイト列になる
  (b) 塊は 1 つも作られず、理由コードが返る
どちらの場合も、この部品は入力の行を 1 つも書き換えず、要約も切り詰めもせず、ファイルを 1 つも開かない。

入力は乱数で作る。宣言どおりの行を 1〜4 行作り、9 通りから 1 つ引いて 1 か所だけ崩す(「崩さない」も
同じ確率で引く。出典を空に / sha256 を空に / 有効期間の始まりを空に / 公表時点を空に / 品質を空に /
出典を上限より長く / 同じ問いに当たる行を 2 行に / 問いを表の外に / 宣言に無い field を要求)。
さらに宣言表の側も乱数で動かす(max_chars の緩さ / 行に無い列を焼く宣言 / 任意の field の要求)。
(a) と (b) の両方を十分に通すため。derandomize=True で毎回同じ入力列を使い、database=None で
見つけた例を保存しない。

判定は context_pack の関数を使わず、このテストの中で別に書く(どの段でどの理由コードが返るか、
field ごとに何の文字が焼かれるか)。道具自身の判定が壊れても、このテストで気づけるようにするため。
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
import context_pack as C  # noqa: E402

# 宣言表(pin は固定、max_chars と任意 field だけ乱数で動かす)
DECLARED = (
    ("値", True, "payload"),
    ("対象", True, "rule|selector"),
    ("有効期間", True, "valid_from|valid_to"),
    ("公表時点", True, "known_from|known_quality"),
    ("出典", True, "source"),
    ("原本", True, "source_file|source_row|source_sha256"),
    ("順位", False, "priority"),
)

CORE = ("payload", "selector", "valid_from", "known_from", "source",
        "source_file", "source_row", "source_sha256")

# 空欄の列 → 返るべき理由コード(このテストの中に別に書き写す)
REASON_OF = {"source": "出典が空欄", "source_file": "出典が空欄", "source_row": "出典が空欄",
             "source_sha256": "sha256 が無い", "valid_from": "有効期間が空欄",
             "known_from": "公表時点が空欄"}

_NUM = re.compile(r"\A[+-]?[0-9]+(?:\.[0-9]+)?\Z")


def 焼く文字(column: str, row: dict) -> str:
    """このテストの中で別に書いた 1 列ぶんの文字。"""
    v = str(row.get(column, "") or "").strip()
    if not v:
        return "(なし)"
    if column in ("payload", "priority") and _NUM.match(v):
        return str(Decimal(v))
    return v


def 期待する理由(rows: list, decl: list, ask: dict, asked: tuple) -> tuple:
    """このテストの中で別に書いた「どの段でどの理由コードが返るか」(decl は 4 つ組)。"""
    names = {name for name, _, _, _ in decl}
    if [a for a in asked if a not in names]:
        return (C.DECL, {"宣言に無い field を要求"})
    hit = [r for r in rows
           if r.get("rule") == ask["rule"] and r.get("selector") == ask["selector"]]
    if not hit:
        return (C.MATCH, {"該当 0 件"})
    if len(hit) > 1:
        return (C.MATCH, {"該当 2 件以上"})
    row = hit[0]
    out = [(name, pins, limit) for name, required, pins, limit in decl
           if required or name in asked]
    missing = {"pin に指定された列が行に無い"
               for _, pins, _ in out for c in pins.split("|") if c not in row}
    if missing:
        return (C.BUILD, missing)
    empty = {REASON_OF[c] for c in CORE if not str(row.get(c, "") or "").strip()}
    if not str(row.get("known_quality", "") or "").strip():
        empty.add("公表時点が空欄")
    if empty:
        return (C.BUILD, empty)
    over = {"max_chars 超過" for _, pins, limit in out
            if limit and len(" / ".join(焼く文字(c, row) for c in pins.split("|"))) > limit}
    if over:
        return (C.BUILD, over)
    return (C.DONE, set())


# -- 入力 ------------------------------------------------------------------------

良い日 = st.tuples(st.integers(2020, 2029), st.integers(1, 12), st.integers(1, 28)).map(
    lambda t: f"{t[0]:04d}-{t[1]:02d}-{t[2]:02d}")
良い値 = st.one_of(st.integers(0, 999999).map(str),
                   st.tuples(st.integers(0, 99), st.integers(0, 99)).map(
                       lambda t: f"{t[0]}.{t[1]:02d}"))
良い指紋 = st.text(alphabet="0123456789abcdef", min_size=64, max_size=64)
良い出典 = st.text(alphabet=st.sampled_from(list("合成の表架空年度版ABC012 ")),
                   min_size=1, max_size=30)

崩し方 = st.sampled_from(["崩さない", "出典を空に", "sha256 を空に", "有効期間を空に",
                          "公表時点を空に", "品質を空に", "出典を長く", "同じ問いを 2 行に",
                          "問いを表の外に", "宣言に無い field を要求"])


@st.composite
def 入力(draw: st.DrawFn) -> dict:
    n = draw(st.integers(1, 4))
    rows = []
    for i in range(n):
        row = {"rule": f"ルール{i}", "selector": f"対象={i}",
               "valid_from": draw(良い日), "valid_to": draw(st.one_of(st.just(""), 良い日)),
               "known_from": draw(良い日), "known_quality": draw(st.sampled_from(C.QUALITIES)),
               "priority": draw(st.sampled_from(["0", "10", "20"])),
               "payload": draw(良い値), "source": draw(良い出典),
               "source_file": f"moto{i}.csv", "source_row": str(i + 2),
               "source_sha256": draw(良い指紋)}
        if draw(st.booleans()):
            row["known_to"] = ""        # 行の側に在ることもある列
        rows.append(row)

    # 宣言表(max_chars の緩さと、行に無い列を焼く宣言を乱数で動かす)
    limit = draw(st.sampled_from([0, 20, 40, 120]))
    decl = [(name, required, pins, 0 if name != "出典" else limit)
            for name, required, pins in DECLARED]
    if draw(st.booleans()):
        decl.append(("公表の終わり", True, "known_to", 0))
    asked = ("順位",) if draw(st.booleans()) else ()

    ask = {"rule": rows[0]["rule"], "selector": rows[0]["selector"]}
    kind = draw(崩し方)
    event(kind)
    i = 0
    if kind == "出典を空に":
        rows[i][draw(st.sampled_from(["source", "source_file", "source_row"]))] = ""
    elif kind == "sha256 を空に":
        rows[i]["source_sha256"] = ""
    elif kind == "有効期間を空に":
        rows[i]["valid_from"] = ""
    elif kind == "公表時点を空に":
        rows[i]["known_from"] = ""
    elif kind == "品質を空に":
        rows[i]["known_quality"] = ""
    elif kind == "出典を長く":
        rows[i]["source"] = "合" * draw(st.integers(21, 130))
    elif kind == "同じ問いを 2 行に":
        rows.append(dict(rows[0], payload=draw(良い値), priority="10"))
    elif kind == "問いを表の外に":
        ask = {"rule": "表に無いルール", "selector": "対象=表に無い"}
    elif kind == "宣言に無い field を要求":
        asked = asked + ("計算方法",)
    return {"rows": rows, "decl": decl, "ask": ask, "asked": asked, "kind": kind}


def _declaration(decl: list) -> C.Declaration:
    return C.Declaration.of([{"field": name, "required": "○" if required else "",
                              "max_chars": str(limit) if limit else "", "pin": pins}
                             for name, required, pins, limit in decl])


@settings(max_examples=300, derandomize=True, database=None, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(t=入力())
def test_いつも成り立つこと_欠けなく焼けた塊が返るか_理由コードが返るか(t: dict) -> None:
    before = json.dumps(t["rows"], ensure_ascii=False, sort_keys=True)
    decl = _declaration(t["decl"])
    want_stage, want_reasons = 期待する理由(t["rows"], t["decl"], t["ask"], t["asked"])
    with tempfile.TemporaryDirectory() as d:
        p = C.pack(t["rows"], decl, t["ask"], t["asked"])
        assert p.report.stage == want_stage
        if p.report.ok:
            event("(a) 欠けなく焼けた塊が返った")
            assert want_reasons == set() and p.report.pending == ()
            row = p.row
            text = p.text()
            lines = text.splitlines()
            out = [name for name, required, pins, _ in t["decl"]
                   if required or name in t["asked"]]
            note = 1 if row["known_quality"] == C.TENTATIVE else 0
            assert len(lines) == len(out) + note
            assert text.endswith("\n")
            # field ごとに何が焼かれるかを、このテストの中で別に組み立てる
            pins = {name: pin for name, _, pin, _ in t["decl"]}
            for line, name in zip(lines, out):
                want = " / ".join(焼く文字(c, row) for c in pins[name].split("|"))
                assert line == f"{name}: {want}"
            if note:
                assert lines[-1] == C.NOTE_TENTATIVE
            # 必ず焼く 8 つの列は塊の中に文字として在る(切り詰めない)
            for c in CORE:
                assert 焼く文字(c, row) in text
            # 2 回目も同じバイト列
            again = C.pack(t["rows"], decl, t["ask"], t["asked"])
            assert again.text().encode("utf-8") == text.encode("utf-8")
            assert again.sha256() == p.sha256()
            assert p.builds == 2
            # 大きさは文字数とバイト数だけ
            sizes = p.sizes()
            assert sizes["大きさ"] == {"文字数": len(text),
                                       "バイト数": len(text.encode("utf-8"))}
            assert all("token" not in k and "トークン" not in k for k in sizes)
        else:
            event("(b) 塊は作られず理由コードが返った")
            assert p.report.pending and all(x.reason in C.REASONS for x in p.report.pending)
            assert set(p.report.reasons()) == want_reasons
            assert p._text == ""
            for call in (p.text, p.sha256, p.sizes, p.pinned):
                try:
                    call()
                    raise AssertionError("塊ができていないのに返ってきた")
                except C.PackError:
                    pass
        assert list(Path(d).iterdir()) == []      # この部品からファイルは開かれない
    assert json.dumps(t["rows"], ensure_ascii=False, sort_keys=True) == before
