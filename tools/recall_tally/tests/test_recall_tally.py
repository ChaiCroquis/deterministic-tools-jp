"""recall_tally の試験。合成の 4 枚(fixtures/gousei/)で測る。記事に載せた数値はここの assert が固定している。
手元の 2 文書を写した 4 枚(examples/temoto_no_nibunsho/)は最後の 1 本でだけ通す。"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import recall_tally as R  # noqa: E402

FILES = ("routes.csv", "counts.csv", "units.csv", "pairs.csv")
GOUSEI = [str(ROOT / "fixtures" / "gousei" / n) for n in FILES]
TEMOTO = [str(ROOT / "examples" / "temoto_no_nibunsho" / n) for n in FILES]
A, B, C, D, E = R.KUBUN
DIFF = "差(経路 2 − 経路 1)"


@pytest.fixture()
def t() -> dict:
    return R.read_all(GOUSEI)


def by_item(res: dict) -> dict[str, dict]:
    return {r["項目 id"]: r for r in res["対ごと"]}


def label(r: dict) -> str:
    return r.get("区分") or r["別枠"]


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "recall_tally.py"), *args],
                          capture_output=True, text=True, encoding="utf-8")


def test_合成の4枚が読める(t: dict) -> None:
    assert [len(t[k]) for k in R.ORDER] == [3, 32, 5, 16]


def test_区分と別枠の件数(t: dict) -> None:
    res = R.judge(t)
    assert list(res["区分"].values()) == [2, 2, 2, 2, 2]
    assert list(res["別枠"].values()) == [1, 1, 1, 1, 1, 1]
    assert res["件数の合計の検算"] == "区分 10 + 別枠 6 = 16 / 分母 16"
    print("\n[measure] 対 16 件 → 区分 10 + 別枠 6 = 16。区分 = A 2 / B 2 / C 2 / D 2 / E 2、別枠は 6 つの理由が 1 件ずつ")


def test_差はBにだけ返り符号は経路2から経路1を引く(t: dict) -> None:
    res = R.judge(t)
    m = by_item(res)
    assert m["品目の数"][DIFF] == 7 and m["仕入先の数"][DIFF] == -2
    assert [r["項目 id"] for r in res["対ごと"] if DIFF in r] == ["仕入先の数", "品目の数"]
    print("[measure] 差が返ったのは (B) の 2 件だけ = 品目の数 +7(480 → 487)、仕入先の数 -2(40 → 38)")


def test_空白だけは除いて比べる(t: dict) -> None:
    m = by_item(R.judge(t))
    assert m["倉庫の区分"]["経路 2"]["数の文字列"] == " 3 " and label(m["倉庫の区分"]) == A


def test_概数の印が在れば比べない(t: dict) -> None:
    m = by_item(R.judge(t))
    for k in ("取引先の数", "部門"):
        assert label(m[k]) == E and DIFF not in m[k]
    assert m["部門"]["経路 1"]["単位の記号"] != m["部門"]["経路 2"]["単位の記号"]   # 単位が違っても印が先に勝つ


def test_片側が無いときは0と書かない(t: dict) -> None:
    m = by_item(R.judge(t))
    assert m["担当者"]["経路 2"]["数の文字列"] == R.NO_NUM
    assert m["返品理由"]["経路 1"]["数の文字列"] == R.NO_NUM
    assert label(m["担当者"]) == D and label(m["返品理由"]) == D


def test_整数の形でない数は差を返さない(t: dict) -> None:
    m = by_item(R.judge(t))
    assert m["端末の数"]["別枠"] == R.BETSU[5] and DIFF not in m["端末の数"]
    assert not R.int_form("1,200") and not R.int_form("1.5") and not R.int_form("１２") and R.int_form(" 12 ")


def test_対の外の数も捨てない(t: dict) -> None:
    res = R.judge(t)
    outside = [(i["項目 id"], c["数 id"]) for i in res["項目ごと"] for c in i["数"] if c["対"] == "対の外"]
    assert outside == [("品目の数", "N08"), ("店舗の数", "N03")]
    assert res["対の外の数の件数"] == 2
    many = [i["項目 id"] for i in res["項目ごと"] if i["数の件数"] >= 3]
    assert many == ["品目の数", "店舗の数"]
    print("[measure] 数が 3 つ在る項目は 2 件で、対に入らなかった 2 件は「対の外」として並ぶ")


def test_経路ごとの内訳(t: dict) -> None:
    res = R.judge(t)
    got = [(r["経路 id"], r["数の件数"], r["数え方の記載が空"]) for r in res["経路ごと"]]
    assert got == [("S1", 16, 16), ("S2", 14, 13), ("S3", 2, 2)]
    assert res["経路ごと"][0]["単位の記号ごと"] == {"区分": 6, "品目": 1, "店舗": 1, "率": 1, "箱": 1, "行": 6}
    print("[measure] 数 32 件のうち、数え方の記載が在るのは 1 件だけ(31 件は記載なし)")


def test_二度走っても行順を替えても同じ(t: dict) -> None:
    a, b = R.judge(t), R.judge(t)
    c = R.judge({k: list(reversed(v)) for k, v in t.items()})
    assert a["判定部分の sha256"] == b["判定部分の sha256"] == c["判定部分の sha256"]
    assert json.dumps(a, ensure_ascii=False) == json.dumps(c, ensure_ascii=False)
    assert a["判定部分の sha256"][:12] == "99911e3bd9a4"
    print(f"[measure] 2 回 + 4 枚の行順を逆順にして読み直し: 判定部分の sha256 は 3 回とも同じ(先頭 12 桁 {a['判定部分の sha256'][:12]})")


def _moved(a: dict, b: dict) -> list[str]:
    ma = by_item(a)
    return [k for k, r in by_item(b).items() if r != ma[k]]


def test_Aの片側を1だけ替えるとその対だけBへ(t: dict) -> None:
    base = R.judge(t)
    targets = [r for r in base["対ごと"] if label(r) == A]
    for r in targets:
        v = R._variant(t, "counts", r["経路 2 の数 id"], "数の文字列", str(int(r["経路 2"]["数の文字列"]) + 1))
        b = R.judge(v)
        assert _moved(base, b) == [r["項目 id"]]
        hit = by_item(b)[r["項目 id"]]
        assert label(hit) == B and hit[DIFF] == 1
    assert len(targets) == 2
    print("[measure] (A) の 2 件を 1 件ずつ片側だけ 1 増やすと、動いたのは 2 回とも替えた対だけで、どれも (B) へ、差は 1")


def test_Bの片側の単位を替えるとその対だけCへ(t: dict) -> None:
    base = R.judge(t)
    targets = [r for r in base["対ごと"] if label(r) == B]
    for r in targets:
        b = R.judge(R._variant(t, "counts", r["経路 2 の数 id"], "単位の記号", "店舗"))
        assert _moved(base, b) == [r["項目 id"]]
        hit = by_item(b)[r["項目 id"]]
        assert label(hit) == C and DIFF not in hit
    assert len(targets) == 2


def test_verifyの5つ(t: dict) -> None:
    res = R.verify(t)
    assert res["ok"] and len(res["検算"]) == 5 and all(res["検算"].values())


def test_表の行を節ごとに数える() -> None:
    text = "\n".join(["| a | b |", "|---|---|", "| 1 | 2 |", "", "# 一",
                      "| a |", "|---|", "| x |", "| x |", "文", "| a |", "|---|", "| y |",
                      "## 二", "本文だけ", "### 三", "| a |", "|---|"])
    res = R.count_table_rows(text)
    assert [(s["節"], s["表の数"], s["表の行の数"]) for s in res["節ごと"]] == [
        ("(見出しの前)", 1, 1), ("一", 2, 3), ("三", 1, 0)]
    assert res["表の行の数の合計"] == 4   # 同じ x の 2 行は重複を除かない
    assert R.count_table_rows(text, head=0)["表の行の数の合計"] == 12


def test_表の形の誤りは1件も判定しない(t: dict) -> None:
    bad = {k: [dict(r) for r in v] for k, v in t.items()}
    bad["counts"][0]["概数の印"] = "たぶん"
    with pytest.raises(R.ShapeError):
        R.judge(bad)
    bad = {k: [dict(r) for r in v] for k, v in t.items()}
    bad["pairs"][0]["経路 1 の数 id"] = bad["pairs"][0]["経路 2 の数 id"] = ""
    with pytest.raises(R.ShapeError):
        R.judge(bad)
    bad = {k: [dict(r) for r in v] for k, v in t.items()}
    del bad["units"][0]["意味"]
    with pytest.raises(R.ShapeError):
        R.judge(bad)


def test_CLIの終了コード() -> None:
    assert run("check", *GOUSEI).returncode == 0
    assert run("verify", *GOUSEI).returncode == 0
    r = run("rows", *GOUSEI)
    assert r.returncode == 0 and len(r.stdout.strip().splitlines()) == 17
    assert run("check", *GOUSEI[:3], GOUSEI[0]).returncode == 2


def test_持たせない経路() -> None:
    tree = ast.parse((ROOT / "recall_tally.py").read_text(encoding="utf-8"))
    mods = sorted({a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
                  | {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module})
    assert mods == ["__future__", "argparse", "csv", "hashlib", "json", "re", "sys"]
    calls = [n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
    assert calls.count("float") == 0 and calls.count("open") == 2 and calls.count("eval") == 0
    print(f"[measure] import は {len(mods)} 個で、os / pathlib / datetime / time / random / urllib / socket は 0 件。"
          "float の呼び出しは 0 件、open は読む 2 か所だけ")


def test_手元の2文書を写した実走例() -> None:
    t = R.read_all(TEMOTO)
    res = R.judge(t)
    assert list(res["区分"].values()) == [2, 1, 3, 1, 1] and sum(res["別枠"].values()) == 0
    m = by_item(res)
    assert [k for k, r in m.items() if label(r) == A] == ["3 健保の等級", "6 育児休業の給付率"]
    assert m["1 労災保険率の区分"][DIFF] == 1
    assert [k for k, r in m.items() if label(r) == C] == ["2 厚年保険料率の行", "4 厚年の等級表", "5 雇用保険料率の事業の種類"]
    assert label(m["7 rule の総数"]) == E and label(m["8 在職老齢の支給停止調整額"]) == D
    seven = {i["項目 id"]: i for i in res["項目ごと"]}["7 rule の総数"]
    assert [(c["数の文字列"], c["単位の記号"], c["対"]) for c in seven["数"]] == [
        ("≈50", "rule", "対の中"), ("45", "rule", "対の中"), ("58", "表の行", "対の外")]
    assert res["対の外の数の件数"] == 2
    assert [(r["経路 id"], r["数の件数"], r["数え方の記載が空"]) for r in res["経路ごと"]] == [("R1", 9, 8), ("R2", 8, 7)]
    rows = R.count_table_rows((ROOT / "examples" / "temoto_no_nibunsho" / "rule_catalog_A.md").read_text(encoding="utf-8"))
    assert [s["表の行の数"] for s in rows["節ごと"]] == [12, 4, 10, 19, 6, 4, 3] and rows["表の行の数の合計"] == 58
    v = R.verify(t)
    assert v["ok"] and v["使った対"] == {"(A) → (B) に使った対": "3 健保の等級", "(B) → (C) に使った対": "1 労災保険率の区分"}
    assert res["判定部分の sha256"][:12] == "07bfec1b2d3d"
    print(f"[measure] 実走例: 対 8 件 → A 2 / B 1 / C 3 / D 1 / E 1、別枠 0。B の差は +1(54 → 55)。対の外 2 件。"
          f"数 17 件のうち数え方の記載が空は 15 件。A 章の表の行は 7 節で計 58。sha256 先頭 {res['判定部分の sha256'][:12]}")
