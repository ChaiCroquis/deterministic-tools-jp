"""stock_use の試験。合成の 4 枚(fixtures/gousei/)で測る。記事に載せた数値はここの assert が固定している。
手元の 1 文書を写した 4 枚(examples/temoto/)は最後の 1 本でだけ通す。"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import stock_use as M  # noqa: E402

FILES = ("okiba.csv", "kisai.csv", "kigou.csv", "tsui.csv")
GOUSEI = [str(ROOT / "fixtures" / "gousei" / n) for n in FILES]
TEMOTO = [str(ROOT / "examples" / "temoto" / n) for n in FILES]
A, B, C, D, E = M.GOCHI
SA = "差(取得の本数 − 名指された数)"


@pytest.fixture()
def t() -> dict:
    return M.read_all(GOUSEI)


def label(r: dict) -> str:
    return r.get("5 値") or r["別枠"]


def by_key(res: dict) -> dict[tuple[str, str], list[str]]:
    out: dict[tuple[str, str], list[str]] = {}
    for r in res["置き場の種類ごと"]:
        out.setdefault((r["置き場 id"], r["種類"]), []).append(label(r))
    return out


def rowmap(res: dict) -> dict[tuple[str, str], dict]:
    return {(r["置き場 id"], r["種類"]): r for r in res["置き場の種類ごと"]}


def per(res: dict) -> dict[str, dict]:
    return {p["置き場 id"]: p for p in res["置き場ごと"]}


def cp(t: dict) -> dict:
    return {k: [dict(r) for r in rows] for k, rows in t.items()}


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "stock_use.py"), *args],
                          capture_output=True, text=True, encoding="utf-8")


def test_合成の4枚が読める(t: dict) -> None:
    assert [len(t[k]) for k in M.ORDER] == [14, 12, 6, 13]


def test_5値と別枠の件数(t: dict) -> None:
    res = M.judge(t)
    assert list(res["5 値"].values()) == [2, 1, 2, 1, 1]
    assert list(res["別枠"].values()) == [1, 1, 1, 1, 2, 1]
    assert res["件数の合計の検算"] == "5 値 7 + 別枠 7 = 14 / 分母 14。置き場ごとの内訳の合計 14 / 分母 14"
    print("\n[measure] 置き場の種類 14 行 → 5 値 7(A 2 / B 1 / C 2 / D 1 / E 1)+ 別枠 7 = 14")


def test_5値の振り分け(t: dict) -> None:
    m = by_key(M.judge(t))
    assert {k: v for k, v in m.items() if k[0] in ("tori", "maker")} == {
        ("tori", "請求書 PDF"): [B], ("tori", "納品書 CSV"): [A], ("tori", "見積 HTML"): [C],
        ("maker", "商品マスタ CSV"): [D], ("maker", "画像"): [E], ("maker", "価格表 xlsx"): [A],
        ("maker", "カタログ PDF"): [C]}


def test_差は両側に数が在るときだけ整数で出す(t: dict) -> None:
    r = rowmap(M.judge(t))
    assert r[("tori", "請求書 PDF")][SA] == 1 and r[("tori", "請求書 PDF")]["名指された数"] == [6]
    assert all(SA not in x for k, x in r.items() if k != ("tori", "請求書 PDF"))
    assert r[("tori", "見積 HTML")]["比べない訳"] == "名指された数が無い"
    assert r[("maker", "カタログ PDF")]["比べない訳"] == "取得の本数が空"
    assert all(not isinstance(v, float) for x in r.values() for v in x.values())


def test_名指された数が記載ごとに違えば比べない(t: dict) -> None:
    v = cp(t)
    v["kisai"].append({"記載 id": "S20", "記号": "検証の欄に在る", "名指された数": "7", "後の側の文字列": "請求書 7 本",
                       "出典": "x L30"})
    v["tsui"].append({"記載 id": "S20", "置き場 id": "tori", "種類": "請求書 PDF", "出典": "私の対応付け"})
    r = rowmap(M.judge(v))[("tori", "請求書 PDF")]
    assert r["5 値"] == C and r["比べない訳"] == "名指された数が記載ごとに違う" and r["名指された数"] == [6, 7]


def test_言い方の違いは区分に効かせず別の列に並べる(t: dict) -> None:
    r = rowmap(M.judge(t))[("maker", "価格表 xlsx")]
    assert r["5 値"] == A
    assert [x["記載 id"] for x in r["言い方の違い(区分に効かせない)"]] == ["S6"]
    v = cp(t)
    v["tsui"] = [x for x in v["tsui"] if x["記載 id"] != "S6"]
    assert rowmap(M.judge(v))[("maker", "価格表 xlsx")]["5 値"] == A


def test_別枠の6つの理由(t: dict) -> None:
    m = by_key(M.judge(t))
    assert m[("souko", "出荷 CSV")] == ["出典が空"]
    assert m[("souko", "在庫 CSV")] == ["取得の本数が整数でない"]
    assert m[("souko", "返品 CSV")] == ["台帳に無い id を指す対"]
    assert m[("souko", "棚卸し xlsx")] == ["登録表に無い記号"]
    assert m[("souko", "伝票 PDF")] == ["id の重複", "id の重複"]
    assert m[("kanri", "契約書 PDF")] == ["同じ種類に (A)(B) と (E) が同時に書かれた"]


def test_1つの記載を2つの種類に当てたら別枠(t: dict) -> None:
    v = cp(t)
    v["tsui"].append({"記載 id": "S2", "置き場 id": "tori", "種類": "見積 HTML", "出典": "私の対応付け"})
    m = by_key(M.judge(v))
    assert m[("tori", "納品書 CSV")] == ["id の重複"] and m[("tori", "見積 HTML")] == ["id の重複"]


def test_置き場ごとに内訳を返し1値に丸めない(t: dict) -> None:
    p = per(M.judge(t))
    assert [p["tori"]["内訳"][k] for k in (A, B, C, D, E, "別枠")] == [1, 1, 1, 0, 0, 0]
    assert [p["maker"]["内訳"][k] for k in (A, B, C, D, E, "別枠")] == [1, 0, 1, 1, 1, 0]
    assert p["souko"]["種類の数"] == 6 and p["souko"]["内訳"]["別枠"] == 6
    assert all(set(x) == {"置き場 id", "種類の数", "内訳"} for x in p.values())


def test_当てていない記載と台帳に無い置き場を指す対(t: dict) -> None:
    res = M.judge(t)
    assert res["どの種類にも当てていない記載"] == [{"記載 id": "S11", "記号": "未抽出の欄に在る"}]
    assert res["台帳に無い置き場を指す対"] == 1


def test_量の語と率を出さない(t: dict) -> None:
    res = M.judge(t)
    res.pop("しないこと")   # 「量の語を出さない」の説明文にだけ、その語が否定の形で出てくる
    text = json.dumps(res, ensure_ascii=False)
    for bad in ("多い", "少ない", "利用率", "使っていない", "不要", "削除", "滞留の理由"):
        assert bad not in text


def test_verifyの5つ(t: dict) -> None:
    v = M.verify(t)
    assert v["ok"] and len(v["検算"]) == 5 and all(v["検算"].values())
    assert v["使ったもの"] == {"消した記載": "S7(maker / カタログ PDF: (C) → (E))", "本数を増やした種類": "maker / 価格表 xlsx"}


def test_本数を1増やすとその種類だけAからBへ(t: dict) -> None:
    base = rowmap(M.judge(t))
    v = cp(t)
    next(r for r in v["okiba"] if r["種類"] == "納品書 CSV")["取得の本数"] = "4"
    after = rowmap(M.judge(v))
    k = ("tori", "納品書 CSV")
    assert {kk: x for kk, x in after.items() if kk != k} == {kk: x for kk, x in base.items() if kk != k}
    assert after[k]["5 値"] == B and after[k][SA] == 1


def test_表の形の誤りは1件も判定しない(t: dict) -> None:
    for k, fix in (("kigou", lambda r: r.update({"記号": "使った"})),
                   ("kigou", lambda r: r.update({"要求する欄": "置き場 id"})),
                   ("kisai", lambda r: r.update({"名指された数": "6本"})),
                   ("okiba", lambda r: r.update({"種類": ""})),
                   ("tsui", lambda r: r.update({"記載 id": ""}))):
        v = cp(t)
        fix(v[k][0])
        with pytest.raises(M.ShapeError):
            M.judge(v)


def test_CLIの終了コード(tmp_path: Path) -> None:
    assert run("check", *GOUSEI).returncode == 0
    assert run("verify", *GOUSEI).returncode == 0
    bad = tmp_path / "kigou.csv"
    bad.write_text("記号,意味,要求する欄,出典\n使った,x,,y\n", encoding="utf-8")
    p = run("check", *GOUSEI[:2], str(bad), GOUSEI[3])
    assert p.returncode == 2 and json.loads(p.stdout)["ok"] is False
    assert len(run("rows", *GOUSEI).stdout.splitlines()) == 15


def test_補助の語数えは判定に使わない(t: dict, tmp_path: Path) -> None:
    text = "置き場: 請求書 PDF ×7\n出典: 請求書 PDF\nPDF と PDF\n次: 画像の整理\n"
    w = M.count_words(text, ["PDF", "画像", "倉庫"], (1, 3))
    assert w["読んだ範囲"] == "1-3"
    assert [w["語"][x]["件数"] for x in ("PDF", "画像", "倉庫")] == [4, 0, 0]
    assert w["語"]["PDF"]["行と回数"] == [[1, 1], [2, 1], [3, 2]]
    assert by_key(M.judge(t))[("maker", "画像")] == [E]   # judge は語数えを呼ばない
    f = tmp_path / "later.txt"
    f.write_text(text, encoding="utf-8")
    assert json.loads(run("words", str(f), "画像", "--lines", "1-4").stdout)["語"]["画像"]["件数"] == 1
    assert run("words", str(f), "画像", "--lines", "4〜1").returncode == 2


def test_持たせていない経路() -> None:
    src = (ROOT / "stock_use.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    mods = {n.names[0].name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)}
    mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert mods <= {"__future__", "argparse", "csv", "hashlib", "json", "sys"}
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    for bad in ("float", "difflib", "datetime", "time", "urllib", "socket", "re", "os", "walk", "glob",
                "listdir", "scandir", "iterdir", "Path", "remove", "unlink"):
        assert bad not in names


def test_入力を書き換えない(t: dict) -> None:
    before = json.dumps(t, ensure_ascii=False, sort_keys=True)
    M.judge(t)
    M.verify(t)
    assert json.dumps(t, ensure_ascii=False, sort_keys=True) == before


def test_手元の文書を写した実走例() -> None:
    s = M.read_all(TEMOTO)
    res = M.judge(s)
    assert [len(s[k]) for k in M.ORDER] == [7, 11, 6, 10]
    assert by_key(res) == {
        ("kyoukaikenpo", "xlsx"): [A], ("mhlw", "PDF"): [B], ("mhlw", "page"): [E], ("mhlw", "ハローワーク HTML"): [C],
        ("nenkin", "HTML"): [D], ("nenkin", "PDF"): [B], ("nenkin", "press PDF"): [A]}
    assert list(res["5 値"].values()) == [2, 2, 1, 1, 1] and sum(res["別枠"].values()) == 0
    r = rowmap(res)
    assert (r[("mhlw", "PDF")]["名指された数"], r[("mhlw", "PDF")][SA]) == ([6], 1)
    assert (r[("nenkin", "PDF")]["名指された数"], r[("nenkin", "PDF")][SA]) == ([4], 1)
    assert r[("kyoukaikenpo", "xlsx")]["名指された数"] == [3]
    assert r[("mhlw", "ハローワーク HTML")]["比べない訳"] == "名指された数が無い"
    assert [x["記載 id"] for x in r[("mhlw", "PDF")]["使われた記載"]] == ["L65-pdf", "L90-pdf"]
    assert [x["記載 id"] for x in r[("nenkin", "press PDF")]["言い方の違い(区分に効かせない)"]] == ["L66-iikata"]
    p = per(res)
    assert [p["mhlw"]["内訳"][k] for k in (A, B, C, D, E)] == [0, 1, 1, 0, 1]
    assert [p["nenkin"]["内訳"][k] for k in (A, B, C, D, E)] == [1, 1, 0, 1, 0]
    assert [p["kyoukaikenpo"]["内訳"][k] for k in (A, B, C, D, E)] == [1, 0, 0, 0, 0]
    assert res["どの種類にも当てていない記載"] == [{"記載 id": "L118", "記号": "未抽出の欄に在る"}]
    v = M.verify(s)
    assert v["ok"] and v["使ったもの"] == {"消した記載": "L64(kyoukaikenpo / xlsx: (A) → (E))",
                                           "本数を増やした種類": "kyoukaikenpo / xlsx"}
    print("[measure] 手元: 置き場 3 / 種類 7 → A 2 / B 2 / C 1 / D 1 / E 1、別枠 0。差は mhlw PDF 1、nenkin PDF 1。"
          "記載 11 行のうち種類に当てていない 1 行(L118)")
