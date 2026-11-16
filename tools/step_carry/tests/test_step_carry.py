"""step_carry の試験。合成の 4 枚(fixtures/gousei/)で測る。記事に載せた数値はここの assert が固定している。
手元の 2 文書を写した 4 枚(examples/jokyo/)は最後の 1 本でだけ通す。"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import step_carry as M  # noqa: E402

FILES = ("bunsho.csv", "yakusoku.csv", "kisai.csv", "kigou.csv")
GOUSEI = [str(ROOT / "fixtures" / "gousei" / n) for n in FILES]
JOKYO = [str(ROOT / "examples" / "jokyo" / n) for n in FILES]
A, B, C, D = M.YONCHI


@pytest.fixture()
def t() -> dict:
    return M.read_all(GOUSEI)


def label(r: dict) -> str:
    return r.get("4 値") or r["別枠"]


def by_id(res: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for r in res["約束ごと"]:
        out.setdefault(r["約束 id"], []).append(label(r))
    return out


def items(res: dict) -> dict[str, dict]:
    return {i["項目 id"]: i for i in res["項目ごと"]}


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "step_carry.py"), *args],
                          capture_output=True, text=True, encoding="utf-8")


def test_合成の4枚が読める(t: dict) -> None:
    assert [len(t[k]) for k in M.ORDER] == [2, 14, 13, 6]


def test_4値と別枠の件数(t: dict) -> None:
    res = M.judge(t)
    assert list(res["4 値"].values()) == [2, 2, 1, 2]
    assert list(res["別枠"].values()) == [1, 1, 1, 1, 2, 1]
    assert res["件数の合計の検算"] == "4 値 7 + 別枠 7 = 14 / 分母 14。約束に付いた記載 12 + 付かない記載 1 = 13 / 記載の行数 13"
    print("\n[measure] 約束 14 行 → 4 値 7(A 2 / B 2 / C 1 / D 2)+ 別枠 7 = 14。記載 13 行 = 付いた 12 + 付かない 1")


def test_4値の振り分け(t: dict) -> None:
    m = by_id(M.judge(t))
    assert {k: v for k, v in m.items() if k in ("K1-1", "K1-2", "K2-1", "K2-2", "K3", "K4-1", "K4-2")} == {
        "K1-1": [A], "K1-2": [D], "K2-1": [A], "K2-2": [B], "K3": [B], "K4-1": [C], "K4-2": [D]}


def test_近い語のみは4値に数えず別の列に並べる(t: dict) -> None:
    r = next(x for x in M.judge(t)["約束ごと"] if x["約束 id"] == "K1-2")
    assert r["4 値"] == D and r["記載"] == []
    assert [x["後の側の行"] for x in r["近い語のみ(数えない)"]] == ["30"]


def test_記載なしの語は固定(t: dict) -> None:
    assert D == "(D) 読んだ範囲に記載なし"
    res = M.judge(t)
    res.pop("しないこと")   # 「言い換えない」の説明文にだけ、その語が否定の形で出てくる
    text = json.dumps(res, ensure_ascii=False)
    for bad in ("やっていない", "放置", "未着手", "完了率", "進捗率"):
        assert bad not in text


def test_別枠の6つの理由(t: dict) -> None:
    m = by_id(M.judge(t))
    assert m["K6"] == ["出典が空"]
    assert m["K5"] == ["宣言の文字列が空"]
    assert m["K10"] == ["台帳に無い id を指す記載"]
    assert m["K8"] == ["登録表に無い記号"]
    assert m["K7"] == ["id の重複", "id の重複"]
    assert m["K9"] == ["同じ約束に (A) と (D) が同時に書かれた"]


def test_項目を1値に丸めず内訳を返す(t: dict) -> None:
    it = items(M.judge(t))
    assert [it["K1"]["内訳"][k] for k in (A, B, C, D, "別枠")] == [1, 0, 0, 1, 0]
    assert [it["K2"]["内訳"][k] for k in (A, B, C, D, "別枠")] == [1, 1, 0, 0, 0]
    assert [it["K4"]["内訳"][k] for k in (A, B, C, D, "別枠")] == [0, 0, 1, 1, 0]
    assert it["K7"]["約束の数"] == 2 and it["K7"]["内訳"]["別枠"] == 2
    assert all(sum(i["内訳"].values()) == i["約束の数"] for i in it.values())
    assert all(set(i) == {"項目 id", "約束の数", "内訳", "約束 id"} for i in it.values())


def test_次の候補で使われていない行(t: dict) -> None:
    c = M.judge(t)["後の文書の次の候補"]
    assert len(c) == 1 and c[0]["後の文書 id"] == "SHIN" and c[0]["次の候補の行数"] == 7
    assert c[0]["どの約束の記載にも使われていない行"] == [20, 22, 24, 25, 26]
    assert c[0]["使われていない行の数"] == 5


def test_どの約束にも付かない記載(t: dict) -> None:
    assert M.judge(t)["どの約束にも付かない記載"] == 1


def test_verifyの5つ(t: dict) -> None:
    v = M.verify(t)
    assert v["ok"] and len(v["検算"]) == 5 and all(v["検算"].values())
    assert v["使ったもの"] == {"消した記載": "K1-1 - 済みの記載(後の側の行 8)", "割り直した約束": "K1-1"}


def test_記載を1行消すとその約束だけDへ(t: dict) -> None:
    base = by_id(M.judge(t))
    v = {k: [dict(r) for r in rows] for k, rows in t.items()}
    v["kisai"] = [r for r in v["kisai"] if not (r["約束 id"] == "K4-1")]
    after = by_id(M.judge(v))
    assert after == {**base, "K4-1": [D]}


def test_約束を割り直すと親の項目だけ動く(t: dict) -> None:
    base = items(M.judge(t))
    v = {k: [dict(r) for r in rows] for k, rows in t.items()}
    v["yakusoku"].append({"約束 id": "K3-2", "項目 id": "K3", "宣言の文字列": "区分を決める", "宣言側の出典": "x L7"})
    after = items(M.judge(v))
    assert {k: x for k, x in after.items() if k != "K3"} == {k: x for k, x in base.items() if k != "K3"}
    assert after["K3"]["約束の数"] == 2 and after["K3"]["内訳"][D] == 1


def test_表の形の誤りは1件も判定しない(t: dict) -> None:
    for k, fix in (("kigou", lambda r: r.update({"記号": "完了"})),
                   ("bunsho", lambda r: r.update({"次の候補の行": "137〜143"})),
                   ("kisai", lambda r: r.update({"後の側の行": "L8"})),
                   ("yakusoku", lambda r: r.update({"項目 id": ""}))):
        v = {kk: [dict(r) for r in rows] for kk, rows in t.items()}
        fix(v[k][0])
        with pytest.raises(M.ShapeError):
            M.judge(v)


def test_CLIの終了コード(tmp_path: Path) -> None:
    assert run("check", *GOUSEI).returncode == 0
    assert run("verify", *GOUSEI).returncode == 0
    bad = tmp_path / "kigou.csv"
    bad.write_text("記号,意味,要求する欄,出典\n完了,x,,y\n", encoding="utf-8")
    p = run("check", *GOUSEI[:3], str(bad))
    assert p.returncode == 2 and json.loads(p.stdout)["ok"] is False
    rows = run("rows", *GOUSEI).stdout.splitlines()
    assert len(rows) == 15


def test_補助の語数えは判定に使わない(t: dict, tmp_path: Path) -> None:
    text = "1. 売上 CSV 取込 済\n2. 残高確認書との突合\n突合 と 突合\n"
    w = M.count_words(text, ["突合", "照合", "倉庫"])
    assert w["読んだ行数"] == 3
    assert [w["語"][x]["件数"] for x in ("突合", "照合", "倉庫")] == [3, 0, 0]
    assert w["語"]["突合"]["行と回数"] == [[2, 1], [3, 2]]
    assert by_id(M.judge(t))["K1-2"] == [D]   # 語数えの 0 件で何かが変わる経路は無い(judge は語数えを呼ばない)
    f = tmp_path / "later.txt"
    f.write_text(text, encoding="utf-8")
    assert json.loads(run("words", str(f), "突合").stdout)["語"]["突合"]["件数"] == 3


def test_持たせていない経路() -> None:
    src = (ROOT / "step_carry.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    mods = {n.names[0].name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)}
    mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert mods <= {"__future__", "argparse", "csv", "hashlib", "json", "sys"}
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    for bad in ("float", "difflib", "SequenceMatcher", "datetime", "time", "urllib", "socket", "re", "os", "walk", "glob"):
        assert bad not in names


def test_入力を書き換えない(t: dict) -> None:
    before = json.dumps(t, ensure_ascii=False, sort_keys=True)
    M.judge(t)
    M.verify(t)
    assert json.dumps(t, ensure_ascii=False, sort_keys=True) == before


def test_手元の2文書を写した実走例() -> None:
    s = M.read_all(JOKYO)
    res = M.judge(s)
    assert [len(s[k]) for k in M.ORDER] == [2, 5, 10, 6]
    assert {k: v for k, v in by_id(res).items()} == {"D1-a": [A], "D1-b": [D], "D2": [D], "D3-a": [A], "D3-b": [C]}
    assert list(res["4 値"].values()) == [2, 0, 1, 2] and sum(res["別枠"].values()) == 0
    it = items(res)
    assert [it["D1"]["内訳"][k] for k in (A, B, C, D)] == [1, 0, 0, 1]
    assert [it["D2"]["内訳"][k] for k in (A, B, C, D)] == [0, 0, 0, 1]
    assert [it["D3"]["内訳"][k] for k in (A, B, C, D)] == [1, 0, 1, 0]
    m = {r["約束 id"]: r for r in res["約束ごと"]}
    assert [x["後の側の行"] for x in m["D1-a"]["記載"]] == ["58", "64"]
    assert [x["後の側の行"] for x in m["D3-a"]["記載"]] == ["43", "74", "156"]
    assert [x["後の側の行"] for x in m["D3-b"]["記載"]] == ["131"]
    assert [x["後の側の行"] for x in m["D1-b"]["近い語のみ(数えない)"]] == ["86"]
    assert [x["後の側の行"] for x in m["D2"]["近い語のみ(数えない)"]] == ["31"]
    assert [x["後の側の行"] for x in m["D3-b"]["近い語のみ(数えない)"]] == ["65"]
    c = res["後の文書の次の候補"][0]
    assert c["次の候補の行数"] == 7 and c["どの約束の記載にも使われていない行"] == list(range(137, 144))
    v = M.verify(s)
    assert v["ok"] and v["使ったもの"] == {"消した記載": "D3-b - 別の欄に在る(後の側の行 131)", "割り直した約束": "D1-a"}
    print("[measure] 手元の 2 文書: 3 項目 → 約束 5 → A 2 / B 0 / C 1 / D 2、別枠 0。記載 10 行(うち近い語のみ 3)。"
          "次の候補 7 行のうち使われていない行 7")
