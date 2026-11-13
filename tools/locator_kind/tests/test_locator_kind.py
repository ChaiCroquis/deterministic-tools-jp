"""locator_kind の試験。合成の 5 枚(fixtures/gousei/)で測る。記事に載せた数値はここの assert が固定している。
手元の 2 文書を写した 5 枚(examples/temoto_no_nibunsho/)は最後の 1 本でだけ通す。"""
from __future__ import annotations

import ast
import copy
import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import locator_kind as L  # noqa: E402

FILES = ("places.csv", "origins.csv", "kinds.csv", "patterns.csv", "deps.csv")
GOUSEI = [str(ROOT / "fixtures" / "gousei" / n) for n in FILES]
TEMOTO = [str(ROOT / "examples" / "temoto_no_nibunsho" / n) for n in FILES]
A, B, C, D, E = L.KUBUN


@pytest.fixture()
def t() -> dict:
    return L.read_all(GOUSEI)


def by_id(res: dict) -> dict[str, dict]:
    return {r["出どころ id"]: r for r in res["出どころごと"]}


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "locator_kind.py"), *args],
                          capture_output=True, text=True, encoding="utf-8")


def test_合成の5枚が読める(t: dict) -> None:
    assert [len(t[k]) for k in L.ORDER] == [17, 18, 5, 4, 17]
    assert all(set(r) == set(L.COLUMNS[k]) for k in L.ORDER for r in t[k])


def test_区分と別枠の件数(t: dict) -> None:
    res = L.judge(t)
    assert res["分母(出どころの件数)"] == 19
    assert res["分母の内訳"] == {"出どころの台帳の行数": 18, "依存の台帳にだけ出る出どころ id": 1}
    assert list(res["区分"].values()) == [2, 2, 2, 2, 5]
    assert list(res["E の内訳"].values()) == [1, 1, 1, 1, 1]
    assert list(res["別枠"].values()) == [1, 1, 1, 1, 1, 1]
    assert res["件数の合計の検算"] == "区分 13 + 別枠 6 = 19 / 分母 19"
    print("\n[measure] 出どころ 19 件 → 区分 13 + 別枠 6 = 19。区分 = A 2 / B 2 / C 2 / D 2 / E 5")


def test_出どころごとに答えは1つだけ(t: dict) -> None:
    rows = L.judge(t)["出どころごと"]
    assert [r["出どころ id"] for r in rows] == sorted(r["出どころ id"] for r in rows)
    assert all((r["区分"] != "") != (r["別枠の理由"] != "") for r in rows)
    assert all((r["E の内訳"] != "") == (r["区分"] == E) for r in rows)
    got = {r["出どころ id"]: r["区分"] or r["別枠の理由"] for r in rows}
    assert got == {
        "S01": A, "S02": A, "S03": B, "S04": B, "S05": C, "S06": C, "S07": D, "S08": D,
        "S09": E, "S10": E, "S11": E, "S12": E, "S13": E,
        "S14": L.BETSU[0], "S15": L.BETSU[1], "S16": L.BETSU[2], "S17": L.BETSU[3], "S18": L.BETSU[4],
        "S99": L.BETSU[5],
    }
    assert [by_id(L.judge(t))[i]["E の内訳"] for i in ("S09", "S10", "S11", "S12", "S13")] == list(L.E_SUB)


def test_一致しない場所は出典つきで並べるだけ(t: dict) -> None:
    rows = by_id(L.judge(t))
    assert rows["S03"]["一致しない場所"] == [{
        "置き場 id": "Q08", "年度の記号": "2025", "台帳の場所": "kakaku-2025.csv",
        "型に年度の記号を当てた文字列": "kakaku_2025.csv", "出典": "合成の取得先 8 行目"}]
    assert rows["S04"]["一致しない場所"] == [{
        "置き場 id": "Q09", "年度の記号": "第11期", "台帳の場所": "",
        "型に年度の記号を当てた文字列": "第11期/ichiran.html", "出典": "合成の取得先 9 行目"}]
    assert sum(len(r["一致しない場所"]) for r in rows.values()) == 2
    assert not any("正しい" in k for r in rows.values() for m in r["一致しない場所"] for k in m)


def test_年度の記号は文字列の順で数として読まない(t: dict) -> None:
    rows = by_id(L.judge(t))
    assert rows["S01"]["年度の記号の一覧"] == ["2023", "2024", "2025"]
    assert rows["S04"]["年度の記号の一覧"] == ["第11期", "第12期"]
    c = copy.deepcopy(t)
    for p, k in zip([p for p in c["places"] if p["出どころ id"] == "S05"], ["10", "9", "R6"]):
        p["年度の記号"], p["出典"] = k, "x"
    assert by_id(L.judge(c))["S05"]["年度の記号の一覧"] == ["10", "9", "R6"]     # 数の順なら 9 が先
    assert L.apply_pattern("a{N}b{N}", "07") == "a07b07"                        # 0 を落とさない。印は全部置き換える


def test_ruleごとの内訳と混ざる印(t: dict) -> None:
    res = L.judge(t)
    rules = {r["rule id"]: r for r in res["rule ごと"]}
    assert len(rules) == 10
    assert res["決まり方が混ざる rule の数"] == 3
    assert sorted(k for k, r in rules.items() if r["印"] == L.MIXED) == ["U02", "U04", "U10"]
    assert rules["U10"]["決まり方の内訳"] == {"人が足す": 1, "型から作る": 2}
    assert rules["U06"] == {"rule id": "U06", "依存する出どころの数": 2, "出どころ": ["S07", "S08"],
                            "決まり方の内訳": {"上流が運ぶ": 2}, "印": ""}
    assert rules["U09"]["決まり方の内訳"] == {L.NOT_IN_LEDGER: 1}
    assert "U11" not in rules
    print("\n[measure] rule 10 本のうち 3 本に「決まり方が混ざる」の印")


def test_層の一覧は空の層を補わない(t: dict) -> None:
    rows = by_id(L.judge(t))
    assert rows["S01"]["層の 1 行"] == ("U01、U02、U10 → 仕入先 A の価格表 → Q01(2023)、Q02(2024)、Q03(2025) → "
                                    "型から作る(型 kakaku_{N}.csv) → 足す人の記載なし → 受け取った表の指紋の欄")
    assert rows["S06"]["層"] == {"rule": L.NONE, "出どころ": "案内のページ F", "置き場": L.NONE, "決まり方": "人が足す",
                               "足す人と機会": L.NO_WHO, "版の記録の在り所": L.NO_VERSION}
    assert sum(1 for r in rows.values() if r["層"]["足す人と機会"] == L.NO_WHO) == 16
    assert sum(1 for r in rows.values() if r["層"]["版の記録の在り所"] == L.NO_VERSION) == 15
    assert all(len(r["層"]) == 6 for r in rows.values())
    print("\n[measure] 出どころ 19 件のうち、足す人の記載が無いのは 16 件、版の記録の記載が無いのは 15 件")


def test_型に当てた文字列はAにだけ返し記号は引数で受ける(t: dict) -> None:
    assert "型に当てた文字列" not in L.judge(t)
    got = L.judge(t, "第13期")["型に当てた文字列"]
    assert got["渡された年度の記号"] == "第13期"
    assert [(x["出どころ id"], x["型に当てた文字列"]) for x in got["出どころ"]] == [
        ("S01", "kakaku_第13期.csv"), ("S02", "hyou-第13期-kai.pdf")]
    assert not any(w in json.dumps(got, ensure_ascii=False) for w in ("候補", "予定", "来年"))
    assert L.judge(t, "")["型に当てた文字列"]["出どころ"][0]["型に当てた文字列"] == "kakaku_.csv"


def test_使わなかった行は理由つきで返す(t: dict) -> None:
    un = L.judge(t)["使わなかった行"]
    assert [(u["表"], u["鍵"], u["理由"]) for u in un] == [
        ("依存の台帳", "U01 → S01", "同じ行が 2 度在る"), ("依存の台帳", "U11 → S06", "出典が空"),
        ("型の台帳", "T4", "出典が空"), ("決まり方の登録表", "掲示を見に行く", "出典が空"),
        ("置き場の台帳", "Q17", "出典が空"), ("置き場の台帳", "Q18", "出どころ id が出どころの台帳に無い")]


def test_別枠は手前の関門が勝つ(t: dict) -> None:
    def first(change) -> str:
        c = copy.deepcopy(t)
        o = next(o for o in c["origins"] if o["出どころ id"] == "S16")      # 置き場 id が重複 の行
        change(o)
        return by_id(L.judge(c))["S16"]["別枠の理由"]
    assert first(lambda o: o.update({"型 id": "T9"})) == L.BETSU[2]                       # 重複 が 型 id より手前
    assert first(lambda o: o.update({"決まり方の記号": "知らない記号"})) == L.BETSU[1]    # 登録外 が 重複 より手前
    assert first(lambda o: o.update({"決まり方の記号": "知らない記号", "出典": " "})) == L.BETSU[0]
    c = copy.deepcopy(t)
    next(o for o in c["origins"] if o["出どころ id"] == "S18")["型 id"] = "T9"
    assert by_id(L.judge(c))["S18"]["別枠の理由"] == L.BETSU[3]                           # 型 id 無し が 型 id 空 より手前


def test_二度走っても行順を替えても同じ(t: dict) -> None:
    a = L.judge(t)
    b = L.judge(copy.deepcopy(t))
    rev = L.judge({k: list(reversed(v)) for k, v in copy.deepcopy(t).items()})
    assert a["判定部分の sha256"] == b["判定部分の sha256"] == rev["判定部分の sha256"]
    assert rev == a
    assert a["判定部分の sha256"][:12] == "e82372aceca8"
    print("\n[measure] 2 回 + 5 枚の行順を逆順にして読み直し: 判定部分の sha256 は 3 回とも同じ(先頭 12 桁 e82372aceca8)")


def test_入力を書き換えない(t: dict) -> None:
    before = copy.deepcopy(t)
    L.judge(t, "R9")
    L.verify(t)
    assert t == before


def test_Aの場所を1文字替える(t: dict) -> None:
    base = by_id(L.judge(t))
    idx = [i for i, p in enumerate(t["places"]) if base.get(p["出どころ id"], {}).get("区分") == A]
    assert len(idx) == 5
    for i in idx:
        c = copy.deepcopy(t)
        c["places"][i]["場所"] = L._one_char(c["places"][i]["場所"])
        got = by_id(L.judge(c))
        moved = [k for k in base if (got[k]["区分"], got[k]["別枠の理由"]) != (base[k]["区分"], base[k]["別枠の理由"])]
        assert moved == [t["places"][i]["出どころ id"]]
        assert got[moved[0]]["区分"] == B and len(got[moved[0]]["一致しない場所"]) == 1
    print("\n[measure] (A) の出どころの場所 5 行を 1 行ずつ 1 文字替えると、区分が動いたのは 5 回とも替えた出どころだけで、どれも (B) へ")


def test_型から作るを人が足すに替える(t: dict) -> None:
    res = L.judge(t)
    base, rules = by_id(res), {r["rule id"]: r for r in res["rule ごと"]}
    idx = [i for i, o in enumerate(t["origins"])
           if o["決まり方の記号"] == L.K_PATTERN and base[o["出どころ id"]]["区分"] in (A, B)]
    assert [t["origins"][i]["出どころ id"] for i in idx] == ["S01", "S02", "S03", "S04"]
    moved_rules = 0
    for i in idx:
        oid = t["origins"][i]["出どころ id"]
        c = copy.deepcopy(t)
        c["origins"][i].update({"決まり方の記号": L.K_HAND, "型 id": ""})
        r2 = L.judge(c)
        got, got_rules = by_id(r2), {r["rule id"]: r for r in r2["rule ごと"]}
        assert [k for k in base if got[k] != base[k]] == [oid]
        assert got[oid]["区分"] == C
        changed = sorted(k for k in rules if got_rules[k] != rules[k])
        assert changed == sorted(k for k, r in rules.items() if oid in r["出どころ"])
        moved_rules += len(changed)
    assert moved_rules == 6
    print("\n[measure] 型から作る の 4 行を 1 行ずつ 人が足す に替えると、区分が動いたのは替えた行だけで、内訳が変わった rule は延べ 6 本")


def test_verifyは5つ見て全て通る(t: dict) -> None:
    v = L.verify(t)
    assert v["ok"] is True
    assert [c["ok"] for c in v["検算"]] == [True] * 5
    assert v["検算"][3]["詳細"] == "替えた行 5 / 合わない 0"
    assert v["検算"][4]["詳細"] == "替えた行 4 / 合わない 0"


@pytest.mark.parametrize("kind,change,word", [
    ("origins", lambda rows: rows.append(dict(rows[0])), "重複"),
    ("kinds", lambda rows: rows.append(dict(rows[0])), "重複"),
    ("patterns", lambda rows: rows[0].update({"型": "kakaku.csv"}), "印"),
    ("patterns", lambda rows: rows[0].update({"印に入れる欄名": "場所"}), "欄名"),
    ("places", lambda rows: rows[0].update({"置き場 id": " "}), "空"),
    ("deps", lambda rows: rows[0].update({"rule id": ""}), "空"),
])
def test_表の形の誤りは1件も判定しない(t: dict, kind: str, change, word: str) -> None:
    change(t[kind])
    with pytest.raises(L.FormError, match=word):
        L.judge(t)


def test_CLIの終了コード(tmp_path: Path) -> None:
    ok = run("check", *GOUSEI, "--kigou", "R9")
    assert ok.returncode == 0 and json.loads(ok.stdout)["分母(出どころの件数)"] == 19
    assert run("verify", *GOUSEI).returncode == 0
    rows = list(csv.reader(run("rows", *GOUSEI).stdout.splitlines()))
    assert rows[0] == list(L.ROW_HEAD) and len(rows) == 1 + 19
    assert not any(w in h for h in rows[0] for w in ("順位", "点数", "危な", "来年"))
    bad = tmp_path / "kinds.csv"
    bad.write_text("記号,意味\n型から作る,x\n", encoding="utf-8")
    r = run("check", GOUSEI[0], GOUSEI[1], str(bad), GOUSEI[3], GOUSEI[4])
    assert r.returncode == 2 and "列が無い" in r.stdout
    assert run("check", *GOUSEI[:4]).returncode == 2


def test_持たせない経路が無い() -> None:
    src = (ROOT / "locator_kind.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    mods = sorted({a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
                  | {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module})
    assert mods == ["__future__", "argparse", "csv", "hashlib", "json", "sys"]
    assert not set(mods) & {"os", "pathlib", "datetime", "time", "random", "subprocess", "urllib", "socket", "re", "glob"}
    calls = [n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
    assert calls.count("open") == 1
    assert not {"int", "float", "eval", "exec", "compile", "__import__"} & set(calls)   # 記号を数に直す経路が無い
    assert not any(isinstance(n, ast.Constant) and isinstance(n.value, float) for n in ast.walk(tree))
    print("\n[measure] import は 6 個で、os / pathlib / datetime / time / random / subprocess / urllib / socket は 0 件。"
          "open は読む 1 か所だけ。int / float の呼び出しは 0 件")


def test_手元の2文書を写した実走例() -> None:
    t = L.read_all(TEMOTO)
    assert [len(t[k]) for k in L.ORDER] == [9, 6, 3, 1, 14]
    res = L.judge(t, "9")
    assert res["分母(出どころの件数)"] == 6
    assert list(res["区分"].values()) == [1, 0, 2, 1, 2]
    assert list(res["E の内訳"].values()) == [2, 0, 0, 0, 0]
    assert sum(res["別枠"].values()) == 0 and res["使わなかった行"] == []
    rows = by_id(res)
    assert {k: r["区分"][:3] for k, r in rows.items()} == {
        "G1": "(A)", "G2": "(C)", "G3": "(E)", "G4": "(C)", "G5": "(E)", "G6": "(D)"}
    assert sum(1 for p in t["patterns"]) == 1                                          # 型が書かれた出どころは 1 つ
    assert sum(1 for p in t["places"] if not L.blank(p["場所"])) == 3                  # 場所が埋まるのは型の側の 3 行だけ
    assert rows["G1"]["年度の記号の一覧"] == ["6", "7", "8"] and rows["G2"]["年度の記号の一覧"] == ["R6", "R7", "R8"]
    assert rows["G5"]["年度の記号の一覧"] == ["令和 8 年度"]
    assert sum(1 for r in rows.values() if r["層"]["足す人と機会"] == L.NO_WHO) == 3
    assert sum(1 for r in rows.values() if r["層"]["版の記録の在り所"] == L.NO_VERSION) == 0
    assert sum(1 for r in rows.values() if r["層"]["rule"] == L.NONE) == 1
    assert len(res["rule ごと"]) == 13 and res["決まり方が混ざる rule の数"] == 1
    assert [r["rule id"] for r in res["rule ごと"] if r["印"]] == ["健保料率"]
    assert res["型に当てた文字列"]["出どころ"] == [
        {"出どころ id": "G1", "型 id": "T1", "型": "r{N}ippan3.xlsx", "型に当てた文字列": "r9ippan3.xlsx"}]
    v = L.verify(t)
    assert v["ok"] is True
    assert v["検算"][3]["詳細"] == "替えた行 3 / 合わない 0" and v["検算"][4]["詳細"] == "替えた行 1 / 合わない 0"
    c = copy.deepcopy(t)
    next(o for o in c["origins"] if o["出どころ id"] == "G1").update({"決まり方の記号": L.K_HAND, "型 id": ""})
    r2 = {r["rule id"]: r for r in L.judge(c)["rule ごと"]}
    r1 = {r["rule id"]: r for r in L.judge(t)["rule ごと"]}
    assert sorted(k for k in r1 if r1[k] != r2[k]) == ["介護保険料率", "健保料率", "厚年保険料率"]
    print("\n[measure] 実走例: 出どころ 6 件 → A 1 / B 0 / C 2 / D 1 / E 2、別枠 0。型が書かれた出どころは 1 件。"
          "決まり方の記載なし 2 件。足す人の記載なし 3 件。rule 13 本のうち「決まり方が混ざる」は 1 本")
