"""part_map の試験。合成の 4 枚(fixtures/gousei/)で測る。記事に載せた数値はここの assert が固定している。
手元の記録を写した 4 枚(examples/shiwake/)は最後の 1 本でだけ通す。"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import part_map as M  # noqa: E402

FILES = ("kadai.csv", "buhin.csv", "taiou.csv", "kigou.csv")
GOUSEI = [str(ROOT / "fixtures" / "gousei" / n) for n in FILES]
SHIWAKE = [str(ROOT / "examples" / "shiwake" / n) for n in FILES]
A, B, C = M.SANCHI
KEN = "宣言の検算(件数だけ)"


@pytest.fixture()
def t() -> dict:
    return M.read_all(GOUSEI)


def by_id(res: dict) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in res["詰まり方ごと"]:
        out.setdefault(r["詰まり方 id"], []).append(r)
    return out


def label(r: dict) -> str:
    return r.get("3 値") or r["別枠"]


def parts(res: dict) -> dict[str, dict]:
    return {p["部品 id"]: p for p in res["部品ごと"]}


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "part_map.py"), *args],
                          capture_output=True, text=True, encoding="utf-8")


def test_合成の4枚が読める(t: dict) -> None:
    assert [len(t[k]) for k in M.ORDER] == [12, 7, 11, 5]


def test_3値と別枠の件数(t: dict) -> None:
    res = M.judge(t)
    assert list(res["3 値"].values()) == [3, 1, 2]
    assert list(res["別枠"].values()) == [1, 1, 1, 1, 2]
    assert res["件数の合計の検算"] == "3 値 6 + 別枠 6 = 12 / 分母 12。部品ごとの合計 11 / 対応の行数 11"
    print("\n[measure] 詰まり方 12 行 → 3 値 6(A 3 / B 1 / C 2)+ 別枠 6 = 12。対応 11 行 = 部品ごとの合計 11")


def test_3値の振り分け(t: dict) -> None:
    m = by_id(M.judge(t))
    assert [label(m[k][0]) for k in ("K01", "K02", "K12", "K03", "K04", "K05")] == [A, A, A, B, C, C]
    assert [x["部品 id"] for x in m["K02"][0]["線の内の部品"]] == ["P2", "P3"]
    assert [x["部品 id"] for x in m["K03"][0]["線の外の部品"]] == ["P4"] and m["K03"][0]["線の内の部品"] == []


def test_近い語のみは3値に数えず別の列に並べる(t: dict) -> None:
    r = by_id(M.judge(t))["K05"][0]
    assert r["3 値"] == C
    assert [x["部品 id"] for x in r["近い語のみ(数えない)"]] == ["P5"]
    assert r["線の内の部品"] == [] and r["線の外の部品"] == []


def test_記載なしの語は固定(t: dict) -> None:
    res = M.judge(t)
    out = json.dumps(res, ensure_ascii=False)
    assert "読んだ範囲に記載なし" in out
    assert "存在しない" not in out.replace(M.SHINAI["記載なしを言い換えない"], "")


def test_別枠の5つの理由(t: dict) -> None:
    m = by_id(M.judge(t))
    assert m["K06"][0]["別枠"] == "出典が空"
    assert m["K07"][0]["別枠"] == "対応の片側の出典が空"
    assert m["K08"][0]["別枠"] == "台帳に無い id を指す対応"
    assert m["K09"][0]["別枠"] == "登録表に無い記号"
    assert [r["別枠"] for r in m["K10"]] == ["id の重複", "id の重複"]


def test_部品ごとの件数(t: dict) -> None:
    res = M.judge(t)
    p = parts(res)
    got = {k: (v["対応の記載(近い語のみを除く)"], v["近い語のみ"], v["別枠の対応"]) for k, v in p.items()}
    assert got == {"P1": (1, 0, 1), "P2": (1, 0, 1), "P3": (2, 0, 0), "P4": (1, 0, 0),
                   "P5": (0, 1, 0), "P6": (0, 0, 0), "P7": (0, 0, 2)}
    assert res["台帳に無い部品 id を指す対応"] == 1
    assert [p[k]["件数の段"] for k in ("P6", "P1", "P3")] == ["0", "1", "2 以上"]


def test_宣言の検算は件数だけ(t: dict) -> None:
    k = M.judge(t)[KEN]
    assert [k["線の内と宣言された部品の数"], k["そのうち対応の記載がちょうど 1 件"], k["そのうち対応の記載が 0 件"],
            k["そのうち対応の記載が 2 件以上"], k["線の内の部品がちょうど 1 つの詰まり方"],
            k["(C) 読んだ範囲に記載なしの詰まり方"]] == [5, 2, 2, 1, 2, 2]
    assert not any(isinstance(v, bool) for v in k.values())   # 真偽の欄が無い
    assert not [kk for kk in k for w in ("一致率", "成り立つ", "合計") if w in kk]   # 一致率・真偽・合計の欄の名前が無い


def test_該当本数は文字列のまま足さない(t: dict) -> None:
    res = M.judge(t)
    m = by_id(res)
    assert m["K02"][0]["該当本数(文字列のまま)"] == "9+" and m["K05"][0]["該当本数(文字列のまま)"] == "3 本程度"
    assert not any("合計" in k for k in res["3 値"]) and "該当本数の合計" not in json.dumps(res, ensure_ascii=False)


def test_verifyの5つ(t: dict) -> None:
    v = M.verify(t)
    assert v["ok"] and len(v["検算"]) == 5 and all(v["検算"].values())
    assert v["使ったもの"] == {"消した対応": "K01 - P1", "線の外にした部品": "P1"}
    assert v["判定部分の sha256"] == M.judge(t)["判定部分の sha256"]
    print(f"[measure] verify 5/5。判定部分の sha256 = {v['判定部分の sha256'][:16]}…")


def test_対応を1行消すとその詰まり方と部品だけ動く(t: dict) -> None:
    base = M.judge(t)
    v = {k: [dict(r) for r in rows] for k, rows in t.items()}
    v["taiou"] = [r for r in v["taiou"] if not (r["詰まり方 id"] == "K01" and r["部品 id"] == "P1")]
    b2 = M.judge(v)
    assert label(by_id(b2)["K01"][0]) == C and parts(b2)["P1"]["対応の記載(近い語のみを除く)"] == 0
    for k in ("K02", "K03", "K12", "K10"):
        assert by_id(b2)[k] == by_id(base)[k]


def test_線の内の部品を外にするとAからBへ(t: dict) -> None:
    v = {k: [dict(r) for r in rows] for k, rows in t.items()}
    for r in v["buhin"]:
        if r["部品 id"] == "P1":
            r["線の記号"] = "線の外"
    res = M.judge(v)
    assert label(by_id(res)["K01"][0]) == B
    assert res[KEN]["線の内と宣言された部品の数"] == 4 and res[KEN]["線の内の部品がちょうど 1 つの詰まり方"] == 1


def test_表の形の誤りは1件も判定しない(t: dict) -> None:
    v = {k: [dict(r) for r in rows] for k, rows in t.items()}
    v["kigou"].append({"記号": "線の際", "意味": "x", "要求する欄": "", "出典": "y"})
    with pytest.raises(M.ShapeError):
        M.judge(v)
    v = {k: [dict(r) for r in rows] for k, rows in t.items()}
    v["kigou"][2]["要求する欄"] = "内容"
    with pytest.raises(M.ShapeError):
        M.judge(v)


def test_CLIの終了コード() -> None:
    assert run("check", *GOUSEI).returncode == 0
    assert run("verify", *GOUSEI).returncode == 0
    r = run("rows", *GOUSEI)
    assert r.returncode == 0 and len(r.stdout.strip().splitlines()) == 13
    bad = run("check", GOUSEI[0], GOUSEI[0], GOUSEI[2], GOUSEI[3])
    assert bad.returncode == 2


def test_持たせていない経路() -> None:
    src = (ROOT / "part_map.py").read_text(encoding="utf-8")
    mods = {n.names[0].name.split(".")[0] for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Import)}
    mods |= {n.module.split(".")[0] for n in ast.walk(ast.parse(src)) if isinstance(n, ast.ImportFrom) and n.module}
    assert mods <= {"__future__", "argparse", "csv", "hashlib", "json", "sys"}
    for w in ("difflib", "socket", "urllib", "datetime", "time", "float(", "os.walk", "glob", "SequenceMatcher"):
        assert w not in src
    assert len(M.SHINAI) == 7


def test_入力を書き換えない(t: dict) -> None:
    before = json.dumps(t, ensure_ascii=False, sort_keys=True)
    M.judge(t)
    M.verify(t)
    assert json.dumps(t, ensure_ascii=False, sort_keys=True) == before


def test_手元の記録を写した実走例() -> None:
    s = M.read_all(SHIWAKE)
    res = M.judge(s)
    assert [len(s[k]) for k in M.ORDER] == [6, 10, 6, 5]
    m = {r["詰まり方 id"]: r for r in res["詰まり方ごと"]}
    assert {k: label(r) for k, r in m.items()} == {"②": A, "③": A, "①": B, "④": C, "⑤": C, "⑥": C}
    assert [x["部品 id"] for x in m["③"]["線の内の部品"]] == ["P39", "P40"]
    assert [x["部品 id"] for x in m["④"]["近い語のみ(数えない)"]] == ["P45"]
    assert [x["部品 id"] for x in m["⑤"]["近い語のみ(数えない)"]] == ["P42"]
    assert m["⑥"]["近い語のみ(数えない)"] == []
    assert list(res["3 値"].values()) == [2, 1, 3] and sum(res["別枠"].values()) == 0
    k = res[KEN]
    assert [k["線の内と宣言された部品の数"], k["そのうち対応の記載がちょうど 1 件"], k["そのうち対応の記載が 0 件"],
            k["そのうち対応の記載が 2 件以上"], k["線の内の部品がちょうど 1 つの詰まり方"],
            k["(C) 読んだ範囲に記載なしの詰まり方"]] == [6, 3, 3, 0, 1, 3]
    p = parts(res)
    assert [x for x in p if p[x]["線の記号"] == ["線の内と宣言"] and p[x]["対応の記載(近い語のみを除く)"] == 0] == ["P41", "P42", "P43"]
    assert [x for x in p if p[x]["線の記号"] == ["線の外"] and p[x]["対応の記載(近い語のみを除く)"] == 0] == ["P45", "P46", "P47"]
    assert [m[x]["該当本数(文字列のまま)"] for x in ("①", "②", "③", "④", "⑤", "⑥")] == ["30", "26", "29", "27", "36", "39"]
    drop = {k: [dict(r) for r in rows] for k, rows in s.items()}
    drop["taiou"] = [r for r in drop["taiou"] if not (r["詰まり方 id"] == "①" and r["部品 id"] == "P44")]
    m2 = {r["詰まり方 id"]: label(r) for r in M.judge(drop)["詰まり方ごと"]}
    assert m2 == {**{k: label(r) for k, r in m.items()}, "①": C}
    out = {k: [dict(r) for r in rows] for k, rows in s.items()}
    for r in out["buhin"]:
        if r["部品 id"] == "P38":
            r["線の記号"] = "線の外"
    m3 = {r["詰まり方 id"]: label(r) for r in M.judge(out)["詰まり方ごと"]}
    assert m3 == {**{k: label(r) for k, r in m.items()}, "②": B}
    v = M.verify(s)
    assert v["ok"] and v["使ったもの"] == {"消した対応": "① - P44", "線の外にした部品": "P38"}
    print("[measure] 手元の記録: 詰まり方 6 → A 2 / B 1 / C 3、別枠 0。線の内 6 部品 → 1 件 3 / 0 件 3 / 2 件以上 0。"
          "線の内の部品がちょうど 1 つの詰まり方 1。対応 6 行(うち近い語のみ 2)")
