"""regen_axis の試験。合成の 5 枚(fixtures/gousei/)で測る。記事に載せた数値はここの assert が固定している。
2 枚の一覧を写した 5 枚(examples/futatsu_no_ichiran/)は最後の 1 本でだけ通す。"""
from __future__ import annotations

import ast
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import regen_axis as R  # noqa: E402

FILES = ("files.csv", "writers.csv", "lines.csv", "sayings.csv", "lists.csv")
GOUSEI = [str(ROOT / "fixtures" / "gousei" / n) for n in FILES]
ICHIRAN = [str(ROOT / "examples" / "futatsu_no_ichiran" / n) for n in FILES]
A, B, C, D, E = R.KUBUN


@pytest.fixture()
def t() -> dict:
    return R.read_all(GOUSEI)


def by_id(res: dict) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in res["ファイルごと"]:
        out.setdefault(r["file id"], []).append(r)
    return out


def answers(res: dict) -> list[tuple]:
    return [(r["file id"], r["名前"], r["区分"], r["別枠の理由"]) for r in res["ファイルごと"]]


def sha(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ---- 件数 -------------------------------------------------------------------------
def test_合成の5枚が読める(t):
    assert [len(t[k]) for k in ("files", "writers", "lines", "sayings", "lists")] == [24, 6, 14, 7, 29]


def test_区分と別枠の件数(t):
    r = R.judge(t)
    assert r["分母(ファイルの件数)"] == 24
    assert r["区分"] == {A: 3, B: 4, C: 2, D: 2, E: 5}
    assert r["別枠"] == {"file id が重複": 2, "出典が空": 1, "書き手の記号が登録表に無い": 1,
                        "外から取るのに取り先が空": 1, "線の端が台帳に無い": 1, "線が輪になる": 2}
    assert sum(r["区分"].values()) == 16 and sum(r["別枠"].values()) == 8
    assert r["件数の合計の検算"] == "区分 16 + 別枠 8 = 24 / 分母 24"
    print(f"\n[measure] ファイル 24 件 → 区分 16 + 別枠 8 = 24。区分 = A 3 / B 4 / C 2 / D 2 / E 5")


def test_Eの内訳は3つに分かれる(t):
    r = R.judge(t)
    assert r["E の内訳"] == {"どの線にも出ない": 3, "入力にだけ出る": 1, "出力に出るが書き手が実行でない": 1}
    rows = by_id(r)
    assert rows["G14"][0]["E の内訳"] == "入力にだけ出る"
    assert rows["G15"][0]["E の内訳"] == "出力に出るが書き手が実行でない"
    assert rows["G16"][0]["書き手の記号"] == "実行のあと人が直す"     # 登録表に在る「その他」の記号は E


def test_ファイルごとに答えは1つだけ(t):
    for r in R.judge(t)["ファイルごと"]:
        assert bool(r["区分"]) != bool(r["別枠の理由"])
        assert (r["区分"] == E) == bool(r["E の内訳"])
        assert tuple(r) == R.ROW_COLUMNS
    assert len(R.ROW_COLUMNS) == 14


def test_線の数え方(t):
    r = R.judge(t)
    assert r["数えた線の本数"] == 11                       # 14 本のうち 3 本は数えない
    lines = [u for u in r["使わなかった行"] if u["表"] == "作る線の台帳"]
    assert sorted(u["理由"] for u in lines) == ["出典が空", "出力の端が台帳に無い"]
    rows = by_id(r)
    assert rows["G21"][0]["別枠の理由"] == "線の端が台帳に無い"     # 入力の端が無い線は、出力の側を別枠へ
    assert (rows["G01"][0]["入力に出る回数"], rows["G01"][0]["出力に出る回数"]) == (2, 0)
    assert (rows["G08"][0]["入力に出る回数"], rows["G08"][0]["出力に出る回数"]) == (1, 3)


def test_作り直す元と遡った端(t):
    rows = by_id(R.judge(t))
    assert rows["G08"][0]["作り直す元"] == "G01 / G06 / G07"
    assert rows["G08"][0]["遡った端"] == "G01 / G04 / G05"
    assert rows["G09"][0]["遡った端"] == "G01 / G02 / G04 / G05 / G14"
    assert rows["G03"][0]["作り直す元"] == R.NO_LINE
    no_line = [r for r in R.judge(t)["ファイルごと"] if r["作り直す元"] == R.NO_LINE]
    assert len(no_line) == 17
    print("\n[measure] 作り直す線の記載が無いファイルは 24 件中 17 件")


def test_置き場ごとの書き手(t):
    p = {x["置き場"]: x for x in R.judge(t)["置き場ごと"]}
    assert sorted(p) == ["入力/", "出力/", "取込/", "直下"]
    assert [k for k, v in sorted(p.items()) if v["印"] == R.MIXED] == ["出力/", "取込/", "直下"]
    assert p["取込/"]["内訳"] == {"外から取る": 2, "実行が書く": 2}
    assert p["直下"]["書き手の記号の種類の数"] == 2          # 「書き手の記載なし」は種類に数えない
    assert sum(v["ファイルの件数"] for v in p.values()) == 16   # 別枠のファイルは置き場に数えない
    print("\n[measure] 置き場 4 つのうち 3 つに「書き手が混ざる」の印")


def test_同じファイルへの言い方を並べる(t):
    s = R.judge(t)["同じファイルへの言い方"]
    assert [(x["file id"], x["行数"], x["文言の種類の数"]) for x in s] == [("G10", 2, 1), ("G12", 2, 2)]
    assert [y["文言"] for y in s[1]["言い方"]] == ["要らないかもしれない(架空)", "残すか決める(架空)"]


def test_片方の一覧にしか載らないファイル(t):
    r = R.judge(t)
    assert r["その一覧にしか載らないファイル"] == {
        "一覧 乙": ["G12", "G13", "G14", "G15", "G16", "G17"], "一覧 甲": ["G03"]}
    assert r["どの一覧にも載らないファイル"] == ["G18", "G19", "G20", "G21", "G22", "G23"]


def test_使わなかった行は理由つきで返る(t):
    u = R.judge(t)["使わなかった行"]
    assert len(u) == 7
    assert {x["理由"] for x in u} == {"file id が台帳に無い", "出力の端が台帳に無い", "出典が空"}


# ---- 別枠は手前の関門が勝つ ---------------------------------------------------------
def test_別枠の順番(t):
    files = [dict(f) for f in t["files"]]
    for f in files:
        if f["file id"] == "G22":                       # 輪の上のファイルの出典を空にする
            f["出典"] = ""
    rows = by_id(R.judge({**t, "files": files}))
    assert rows["G22"][0]["別枠の理由"] == "出典が空"
    assert rows["G23"][0]["別枠の理由"] == "線が輪になる"
    assert len(R.BETSUWAKU) == 6 and len(R.KUBUN) == 5


def test_自分に戻る線も輪(t):
    lines = t["lines"] + [{"線 id": "M99", "入力の file id": "G03", "出力の file id": "G03", "出典": "合成"}]
    assert by_id(R.judge({**t, "lines": lines}))["G03"][0]["別枠の理由"] == "線が輪になる"


# ---- 決定論 -------------------------------------------------------------------------
def test_二度走っても行順を替えても同じ(t):
    d1 = R.digest(R.judge(t))
    d2 = R.digest(R.judge(R.read_all(GOUSEI)))
    d3 = R.digest(R.judge({k: list(reversed(v)) for k, v in t.items()}))
    assert d1 == d2 == d3
    assert d1[:12] == "52a7a632b1c0"
    print(f"\n[measure] 2 回 + 5 枚の行順を逆順にして読み直し: 判定部分の sha256 は 3 回とも同じ(先頭 12 桁 {d1[:12]})")


def test_線を1行ずつ外す(t):
    base = R.judge(t)
    on_loop = {"G22", "G23"}
    moved_total, detail = 0, {}
    for n, ln in enumerate(t["lines"]):
        res = R.judge({**t, "lines": t["lines"][:n] + t["lines"][n + 1:]})
        moved = {a[0] for a, b in zip(answers(base), answers(res)) if a != b}
        assert moved <= {ln["出力の file id"]} | on_loop
        moved_total += len(moved)
        detail[ln["線 id"]] = sorted(moved)
    assert moved_total == 8
    assert detail["M03"] == [] and detail["M06"] == []        # 元が 3 つ在る出力は、1 本外しても動かない
    assert detail["M01"] == ["G06"] and detail["M09"] == ["G15"] and detail["M10"] == ["G21"]
    assert detail["M11"] == ["G22", "G23"] and detail["M12"] == ["G22", "G23"]
    assert sum(1 for v in detail.values() if not v) == 8
    print("\n[measure] 線 14 本を 1 本ずつ外すと、区分が動いたのは延べ 8 件。8 本は外しても何も動かない")


def test_書き手を1行だけ替える(t):
    base = R.judge(t)
    tried = moved = 0
    for n, f in enumerate(t["files"]):
        if f["書き手の記号"] != R.JIKKOU:
            continue
        tried += 1
        files = t["files"][:n] + [{**f, "書き手の記号": R.HITO}] + t["files"][n + 1:]
        res = R.judge({**t, "files": files})
        b = {(r["file id"], r["名前"]): (r["区分"], r["別枠の理由"]) for r in base["ファイルごと"]}
        a = {(r["file id"], r["名前"]): (r["区分"], r["別枠の理由"]) for r in res["ファイルごと"]}
        diff = {k for k in b if b[k] != a[k]}
        assert diff <= {(f["file id"], f["名前"])}
        moved += len(diff)
        pb = {p["置き場"]: p for p in base["置き場ごと"]}
        pa = {p["置き場"]: p for p in res["置き場ごと"]}
        assert {k for k in pb if pb[k] != pa.get(k)} <= {f["置き場"]}
    assert (tried, moved) == (10, 6)
    print("\n[measure] 実行が書く の 10 行を 1 行ずつ 人が書く に替えると、区分が動いたのは 6 件で、どれも替えた行だけ")


def test_verifyは5つ見る(t):
    v = R.verify(t)
    assert v["ok"] and len(v["検算"]) == 5 and all(v["検算"].values())
    assert v["線を 1 行ずつ外して区分が動いた延べ件数"] == 8
    assert (v["書き手を替えた行数"], v["書き手を替えて区分が動いた件数"]) == (10, 6)


# ---- 表の形が崩れていたら 1 件も判定しない -------------------------------------------
@pytest.mark.parametrize("kind", ["files", "writers", "lines", "sayings", "lists"])
def test_列が無い表は止まる(t, kind):
    broken = [{k: v for k, v in row.items() if k != "出典"} for row in t[kind]]
    with pytest.raises(R.TableError):
        R.judge({**t, kind: broken})


def test_ファイルの台帳が空なら止まる(t):
    with pytest.raises(R.TableError):
        R.judge({**t, "files": []})


# ---- 持たせないもの -----------------------------------------------------------------
def test_持たせない経路が無い():
    src = (ROOT / "regen_axis.py").read_text(encoding="utf-8")
    mods = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mods.add((node.module or "").split(".")[0])
    assert mods == {"__future__", "argparse", "csv", "hashlib", "json", "sys"}
    calls = {n.func.id for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert not calls & {"float", "eval", "exec", "compile", "__import__"}
    opens = [n for n in ast.walk(ast.parse(src))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "open"]
    assert len(opens) == 1 and not any(isinstance(a, ast.Constant) and "w" in str(a.value) for a in opens[0].args[1:])
    print("\n[measure] import は 6 個で、os / pathlib / datetime / time / random / subprocess / urllib は 0 件。open は読む 1 か所だけ")


def test_出力に消してよいかの欄が無い(t):
    res = R.check(t)
    keys = set(res) | set(R.ROW_COLUMNS) | {k for p in res["置き場ごと"] for k in p}
    for word in ("消し", "危な", "順位", "点数", "残骸", "理由の推定"):
        assert not any(word in k for k in keys)
    assert "消してよいかを決めない" in res["しないこと"]
    assert len(R.SHINAIKOTO) == 8


# ---- CLI ---------------------------------------------------------------------------
def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "regen_axis.py"), *args],
                          capture_output=True, text=True, encoding="utf-8")


def test_CLIは入力を書き換えない():
    before = [sha(p) for p in GOUSEI]
    c = run("check", *GOUSEI)
    assert c.returncode == 0 and json.loads(c.stdout)["判定部分の sha256"][:12] == "52a7a632b1c0"
    v = run("verify", *GOUSEI)
    assert v.returncode == 0 and json.loads(v.stdout)["ok"] is True
    rows = list(csv.DictReader(run("rows", *GOUSEI).stdout.splitlines()))
    assert len(rows) == 24 and tuple(rows[0]) == R.ROW_COLUMNS
    assert [sha(p) for p in GOUSEI] == before


def test_CLIは崩れた表で2を返す(tmp_path):
    bad = tmp_path / "files.csv"
    bad.write_text("file id,名前\nG01,x\n", encoding="utf-8")
    c = run("check", str(bad), *GOUSEI[1:])
    assert c.returncode == 2
    out = json.loads(c.stdout)
    assert out["ok"] is False and set(out["区分"].values()) == {0}


# ---- 2 枚の一覧を写した 5 枚(記事の実走例。この 1 本でだけ通す) -----------------------
def test_二枚の一覧を写した実走例():
    t = R.read_all(ICHIRAN)
    r = R.judge(t)
    assert r["分母(ファイルの件数)"] == 27
    assert r["区分"] == {A: 1, B: 5, C: 4, D: 2, E: 15}
    assert sum(r["別枠"].values()) == 0
    assert r["E の内訳"] == {"どの線にも出ない": 15, "入力にだけ出る": 0, "出力に出るが書き手が実行でない": 0}
    assert sum(1 for x in r["ファイルごと"] if x["書き手の記号"] == R.NO_WRITER) == 15
    assert r["数えた線の本数"] == 11
    # 旧軸(役割)の欄は 27 件すべて埋まっている
    assert all(x["役割"] for x in r["ファイルごと"])
    # (a) 1 つの置き場に書き手が 2 通り
    p = {x["置き場"]: x for x in r["置き場ごと"]}
    assert len(p) == 5 and sum(1 for x in p.values() if x["印"] == R.MIXED) == 4
    for name in ("sources/kyoukaikenpo/", "sources/mhlw/", "sources/nenkin/"):
        assert p[name]["内訳"] == {"外から取る": 1, "実行が書く": 1}
    # (b) 同じファイルへの言い方が 2 通り
    s = {x["file id"]: x for x in r["同じファイルへの言い方"]}
    assert sorted(s) == ["R05", "R11", "R27"] and all(x["文言の種類の数"] == 2 for x in s.values())
    assert [y["文言"] for y in s["R27"]["言い方"]] == [
        "残骸 (削除可)", "`_patch_pipeline.py` と `rulematrix_demo.py` を残すか"]
    # (c) 実行が書く 5 件はどれも、遡った端に人が書く 1 件(R17)が居る
    rows = {x["file id"]: x for x in r["ファイルごと"]}
    made = [x for x in r["ファイルごと"] if x["区分"] == B]
    assert len(made) == 5 and all("R17" in x["遡った端"].split(" / ") for x in made)
    assert rows["R19"]["作り直す元"] == "R18 / R22 / R24 / R26" and rows["R19"]["遡った端"] == "R17 / R18"
    assert rows["R17"]["区分"] == A and rows["R17"]["入力に出る回数"] == 3
    # (d) 控えは 2 件で、どちらもどの線にも出ない
    hikae = [x for x in r["ファイルごと"] if x["区分"] == D]
    assert [x["file id"] for x in hikae] == ["R13", "R20"]
    assert all(x["入力に出る回数"] == 0 and x["出力に出る回数"] == 0 for x in hikae)
    # 2 枚の一覧
    assert len(t["lists"]) == 41 and sum(1 for x in t["lists"] if x["一覧 id"] == "一覧①") == 14
    assert r["その一覧にしか載らないファイル"]["一覧①"] == []
    assert len(r["その一覧にしか載らないファイル"]["一覧②"]) == 13
    # 並べ直しても同じ段に入る 2 件
    assert (rows["R09"]["区分"], rows["R09"]["E の内訳"]) == (rows["R27"]["区分"], rows["R27"]["E の内訳"])
    v = R.verify(t)
    assert v["ok"] and v["線を 1 行ずつ外して区分が動いた延べ件数"] == 4
    assert (v["書き手を替えた行数"], v["書き手を替えて区分が動いた件数"]) == (5, 5)
    assert R.digest(r)[:12] == "32e38abd192b"
    print("\n[measure] 実走例: 27 件 → A 1 / B 5 / C 4 / D 2 / E 15、別枠 0。書き手の記載なし 15 件。"
          "置き場 5 つのうち 4 つに印。言い方が 2 通り在るファイル 3 件。一覧② にしか載らない 13 件")
