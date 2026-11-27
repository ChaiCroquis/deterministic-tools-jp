"""allow_use の試験。合成の一覧と合成の式(架空の語)だけを使う。

[measure] の行は記事に載せる測定値で、どれも `assert 変数 == 値` で固定している(値が変われば記事も変える)。
python -m pytest tools/allow_use -q -s
"""
from __future__ import annotations

import ast
import copy
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
import allow_use as U  # noqa: E402


def load(counting: str = "counting_raw.csv"):
    return (U.read_table(FX / "allow_a.csv", "allow"), U.read_table(FX / "exprs_a.csv", "exprs"),
            U.read_table(FX / counting, "counting"), U.read_table(FX / "elsewhere_a.csv", "elsewhere"))


def by_word(result: dict) -> dict:
    return {(r["種別"], r["語"]): r for r in result["語ごとの行"]}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_measure_表の大きさと区分():
    allow, exprs, counting, elsewhere = load()
    r = U.judge(allow, exprs, counting, elsewhere)
    n_allow, n_types, n_exprs, n_else = len(allow), r["許可の台帳の語の種類数"], len(exprs), len(elsewhere)
    assert n_allow == 41
    assert n_types == 33
    assert n_exprs == 22
    assert n_else == 3
    a, b, c, d = (r["区分ごとの語数"][k] for k in U.CLASSES)
    assert a == 18
    assert b == 5
    assert c == 7
    assert d == 3
    n_side = len(r["別枠に落ちた語"])
    assert n_side == 3
    assert a + b + c == 30
    assert a + b + c + n_side == n_types
    assert r["検算が合うか"] is True
    print(f"\n[measure] allow_a / exprs_a / counting_raw / elsewhere_a: 許可の台帳 {n_allow} 行(語の種類 {n_types})/ "
          f"式の台帳 {n_exprs} 行 / 数え方の登録 1 行 / 別の在り所 {n_else} 行")
    print(f"[measure] 区分は (A) {a} / (B) {b} / (C) {c}(合計 {a + b + c} 語)、別枠に落ちた語は {n_side}。"
          f"合計 {a + b + c + n_side} = 語の種類数。線の外の (D) は {d} 語")


def test_measure_種別ごとの区分と束の本数():
    r = U.judge(*load())
    k = r["種別ごとの区分の語数"]
    names = [k["名前"][c] for c in U.CLASSES]
    nodes = [k["構文の種類"][c] for c in U.CLASSES]
    assert names == [6, 1, 2, 1]
    assert nodes == [12, 4, 5, 2]
    read = r["束ごとの読めた式の本数"]
    assert read == {"式の一覧": 12, "行の式": 7}
    side = r["別枠"]
    n_unreadable = side[U.X_UNREADABLE]["式"]
    n_nosrc_expr = side[U.X_NO_SOURCE]["式"]
    assert n_unreadable == 2
    assert n_nosrc_expr == 1
    assert read["式の一覧"] + read["行の式"] + n_unreadable + n_nosrc_expr == 22
    side_words = sorted((s["語"], s["別枠"]) for s in r["別枠に落ちた語"])
    assert side_words == [("mix", U.X_BAD_KIND), ("old_cut", U.X_NO_SOURCE), ("pick", U.X_DUP)]
    b_words = sorted(w for (_, w), row in by_word(r).items() if row["区分"] == U.B)
    c_words = sorted(w for (_, w), row in by_word(r).items() if row["区分"] == U.C)
    d_words = sorted(x["語"] for x in r["線の外の語"])
    assert b_words == ["Pow", "Sub", "USub", "UnaryOp", "lower"]
    assert c_words == ["Compare", "GtE", "List", "Lt", "Tuple", "clip", "upper"]
    assert d_words == ["And", "BoolOp", "ghost"]
    print(f"\n[measure] 名前は (A) {names[0]} / (B) {names[1]} / (C) {names[2]} / (D) {names[3]}、"
          f"構文の種類は (A) {nodes[0]} / (B) {nodes[1]} / (C) {nodes[2]} / (D) {nodes[3]}")
    print(f"[measure] 読めた式は 式の一覧 {read['式の一覧']} 本 / 行の式 {read['行の式']} 本。"
          f"読めない式 {n_unreadable} 本と出典が空の式 {n_nosrc_expr} 本は別枠(合計 22 = 式の台帳の行数)")
    print(f"[measure] (B) の語: {b_words} / (C) の語: {c_words} / (D) の語: {d_words}")


def test_measure_印と別の在り所():
    r = U.judge(*load())
    w = by_word(r)
    one_sided = sorted(k[1] for k, row in w.items() if U.MARK_ONE_SIDED in row["印"])
    c_else = sorted(k[1] for k, row in w.items() if U.MARK_ELSEWHERE in row["印"])
    assert one_sided == ["Num", "clip"]
    assert c_else == ["upper"]
    # tier にも在り所の登録が在るが、(A) なので印は付かない(記載は横に置かれる)
    assert len(w[("名前", "tier")]["別の在り所"]) == 1
    assert U.MARK_ELSEWHERE not in w[("名前", "tier")]["印"]
    n_unknown = r["台帳に無い語を指す在り所の行数"]
    assert n_unknown == 1
    # 構文の種類は出どころが「実装」1 つだけなので、片方だけの印は 1 語も付かない
    n_node_marked = sum(1 for k, row in w.items() if k[0] == "構文の種類" and row["印"])
    assert n_node_marked == 0
    # 在り所の登録を全部外しても、区分は 1 語も動かない
    allow, exprs, counting, _ = load()
    r0 = U.judge(allow, exprs, counting, [])
    moved = sum(1 for k, row in by_word(r0).items() if row["区分"] != w[k]["区分"])
    assert moved == 0
    print(f"\n[measure] 出どころの片方にしか無い印は {len(one_sided)} 語 {one_sided}、(C) で別の在り所の登録が在る印は "
          f"{len(c_else)} 語 {c_else}。台帳に無い語を指す在り所は {n_unknown} 行。"
          f"在り所の登録を全部外して区分が動いた語は {moved} 語")


def test_measure_変数の名前は拾わない():
    allow, exprs, counting, elsewhere = load()
    r = U.judge(allow, exprs, counting, elsewhere)
    assert any("clip" in e["expr"] for e in exprs)            # clip という字は式の台帳に在る
    assert by_word(r)[("名前", "clip")]["区分"] == U.C          # 変数の名前としてなので、数えない
    e2 = [dict(e, expr="clip(qty) * months") if e["expr_id"] == "E09" else e for e in exprs]
    r2 = U.judge(allow, e2, counting, elsewhere)
    changed = sorted(k[1] for k, row in by_word(r2).items() if row["区分"] != by_word(r)[k]["区分"])
    assert changed == ["clip"]
    assert by_word(r2)[("名前", "clip")]["区分"] == U.A
    print(f"\n[measure] 式 E09 の clip は変数の名前なので (C) のまま。呼び出しに書き替えると区分が動いた語は "
          f"{len(changed)} 語 {changed}")


def test_measure_数え方で本数が動く():
    raw = U.judge(*load("counting_raw.csv"))
    rew = U.judge(*load("counting_rewritten.csv"))
    a, b = by_word(raw), by_word(rew)
    diff = sorted(k[1] for k in a if a[k]["束ごとの式の本数"] != b[k]["束ごとの式の本数"])
    assert diff == ["Call", "Load", "Name", "Num"]
    name = (a[("構文の種類", "Name")]["束ごとの式の本数"], b[("構文の種類", "Name")]["束ごとの式の本数"])
    assert name == ({"式の一覧": 12, "行の式": 6}, {"式の一覧": 12, "行の式": 7})
    assert a[("構文の種類", "Load")]["束ごとの式の本数"] == name[0]
    assert b[("構文の種類", "Load")]["束ごとの式の本数"] == name[1]
    call = (a[("構文の種類", "Call")]["束ごとの式の本数"], b[("構文の種類", "Call")]["束ごとの式の本数"])
    num = (a[("名前", "Num")]["束ごとの式の本数"], b[("名前", "Num")]["束ごとの式の本数"])
    assert call == ({"式の一覧": 7, "行の式": 1}, {"式の一覧": 8, "行の式": 7})
    assert num == ({"式の一覧": 1, "行の式": 0}, {"式の一覧": 2, "行の式": 7})
    cls_moved = sum(1 for k in a if a[k]["区分"] != b[k]["区分"])
    assert cls_moved == 0
    assert raw["判定部分の sha256"] != rew["判定部分の sha256"]
    assert raw["書き換えの規則を使ったか"] is False and rew["書き換えの規則を使ったか"] is True
    # 主の束に数字を含む式が無い束を作ると、区分も動く(Num の呼び出しを書いた式を抜く)
    allow, exprs, _, elsewhere = load()
    no_num = [e for e in exprs if e["expr_id"] != "E07"]
    r1 = U.judge(allow, no_num, U.read_table(FX / "counting_raw.csv", "counting"), elsewhere)
    r2 = U.judge(allow, no_num, U.read_table(FX / "counting_rewritten.csv", "counting"), elsewhere)
    pair = (by_word(r1)[("名前", "Num")]["区分"], by_word(r2)[("名前", "Num")]["区分"])
    assert pair == (U.C, U.A)
    print(f"\n[measure] 書かれた字のまま → 書き換えの後 で本数が動いた語は {len(diff)} 語 {diff}。"
          f"Call は 式の一覧 {call[0]['式の一覧']} → {call[1]['式の一覧']} 本 / 行の式 {call[0]['行の式']} → {call[1]['行の式']} 本、"
          f"Num は 式の一覧 {num[0]['式の一覧']} → {num[1]['式の一覧']} 本 / 行の式 {num[0]['行の式']} → {num[1]['行の式']} 本。"
          f"Name と Load は 行の式 {name[0]['行の式']} → {name[1]['行の式']} 本(数字だけの式 R04 に呼び出しの名前が出る)。"
          f"区分が動いた語は {cls_moved} 語")
    print("[measure] Num を呼ぶ式 E07 を抜いた束では、Num は 書かれた字のまま (C) / 書き換えの後 (A) に分かれる")


def test_measure_行順と指紋():
    allow, exprs, counting, elsewhere = load()
    base = U.judge(allow, exprs, counting, elsewhere)["判定部分の sha256"]
    orders = [exprs, exprs[::-1], sorted(exprs, key=lambda e: e["expr"]), exprs[7:] + exprs[:7],
              sorted(exprs, key=lambda e: e["expr_id"], reverse=True)]
    same = sum(1 for o in orders if U.judge(allow[::-1], o, counting, elsewhere[::-1])["判定部分の sha256"] == base)
    assert same == 5
    head = base[:12]
    assert head == "1251096bdee3"
    print(f"\n[measure] 式の台帳の行順を 5 通りに並べ、許可の台帳と別の在り所も逆順にして読み直し: "
          f"判定部分の sha256 は 5 回とも同じ({same}/5 一致、先頭 12 桁 {head})")


def test_measure_verify():
    v = U.verify(*load())
    n_ok = sum(1 for x in v["verify"].values() if x)
    assert n_ok == 5
    assert v["ok"] is True
    assert v["④ の内訳"] == "7/7"
    assert v["⑤ の件数"] == 0
    # ④ を式の文字列で確かめる: 名前は「upper(x)」1 本で upper だけが動く(Call などは既に (A))
    allow, exprs, counting, elsewhere = load()
    r = by_word(U.judge(allow, exprs, counting, elsewhere))
    add = lambda text: exprs + [{"expr_id": "Z1", "bundle": "式の一覧", "expr": text, "source": "試験"}]  # noqa: E731
    moved_name = sorted(k[1] for k, row in by_word(U.judge(allow, add("upper(x)"), counting, elsewhere)).items()
                        if row["区分"] != r[k]["区分"])
    assert moved_name == ["upper"]
    # 構文の種類は 1 つだけを使う式が書けない: 「a < b」は Compare と Lt の 2 語を同時に動かす
    moved_node = sorted(k[1] for k, row in by_word(U.judge(allow, add("a < b"), counting, elsewhere)).items()
                        if row["区分"] != r[k]["区分"])
    assert moved_node == ["Compare", "Lt"]
    print(f"\n[measure] verify は {n_ok}/5 通過。④ は (C) の {v['④ の内訳']} 語で、その語だけが (A) へ動く。"
          f"式の文字列で足した場合、upper(x) で動くのは {len(moved_name)} 語、a < b で動くのは {len(moved_node)} 語 {moved_node}")


def test_measure_全体に掛かる別枠():
    allow, exprs, counting, elsewhere = load()
    cases = {
        U.X_BAD_MODE: [dict(counting[0], mode="だいたい")],
        U.X_NO_MAIN: [dict(counting[0], main_bundle="どこにも無い束")],
        U.X_NO_SOURCE: [dict(counting[0], source="")],
    }
    hit = 0
    for reason, reg in cases.items():
        r = U.judge(allow, exprs, reg, elsewhere)
        n = sum(1 for s in r["別枠に落ちた語"] if s["別枠"] == reason)
        assert n == 33
        assert r["語ごとの行"] == [] and r["線の外の語"] == []
        assert r["検算が合うか"] is True
        hit += 1
    assert hit == 3
    print(f"\n[measure] 数え方が 2 つの値以外 / 主の束の id が式の台帳に無い / 数え方の登録の出典が空 の {hit} 通りは、"
          f"どれも 33 語すべてが別枠に落ち、区分は 1 語も返らない")


def test_measure_読めない表は例外():
    allow, exprs, counting, elsewhere = load()
    reg = counting[0]
    bad = [
        [],                                                                  # 数え方の登録が 0 行
        [reg, reg],                                                          # 2 行
        [dict(reg, mode=U.MODE_REWRITTEN, pattern="")],                      # 規則が空
        [dict(reg, mode=U.MODE_REWRITTEN, pattern="(", repl="x")],           # 正規表現が読めない
        [dict(reg, mode=U.MODE_REWRITTEN, pattern=r"\d+", repl=r"\9")],      # 置き換えの字が読めない
    ]
    raised = 0
    for b in bad:
        with pytest.raises(U.TableError):
            U.judge(allow, exprs, b, elsewhere)
        raised += 1
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "allow.csv"
        p.write_text("word,kind,origin\nf,名前,x\n", encoding="utf-8")       # source の列が無い
        with pytest.raises(U.TableError):
            U.read_table(p, "allow")
        raised += 1
    assert raised == 6
    # 許可の台帳・式の台帳・別の在り所は 0 行でも読める(主の束が式の台帳に無い扱いになる)
    r = U.judge([], [], counting, [])
    assert r["許可の台帳の語の種類数"] == 0 and r["検算が合うか"] is True
    print(f"\n[measure] 表として読めない崩し方 {raised} 通りは {raised} 通りとも例外で止まる({raised}/{raised})")


def test_measure_コマンドと入力の不変():
    files = [FX / n for n in ("allow_a.csv", "exprs_a.csv", "counting_raw.csv", "counting_rewritten.csv",
                              "elsewhere_a.csv")]
    before = [sha(f) for f in files]
    args = [str(FX / "allow_a.csv"), str(FX / "exprs_a.csv"), str(FX / "counting_raw.csv"),
            str(FX / "elsewhere_a.csv")]
    run = lambda *a: subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "allow_use.py"), *a],  # noqa: E731
                                    capture_output=True, text=True, encoding="utf-8")
    c1, c2 = run("check", *args), run("verify", *args)
    c3 = run("check", args[1], args[0], args[2], args[3])          # 表を取り違えた(列が足りない)
    c4 = run("check", *args, "--lines")
    codes = [c1.returncode, c2.returncode, c3.returncode]
    assert codes == [0, 0, 2]
    n_lines = len(c4.stdout.strip().splitlines())
    assert n_lines == 36                                            # 30 語 + (D) 3 語 + 別枠 3 語
    assert [sha(f) for f in files] == before
    with tempfile.TemporaryDirectory() as d:
        made = U.init(d)
        assert len(made) == 4
        assert U.init(d) == []                                      # 在るファイルは上書きしない
    print(f"\n[measure] コマンドの終了コードは check {codes[0]} / verify {codes[1]} / 読めない表 {codes[2]}。"
          f"--lines の出力は {n_lines} 行。走らせる前後で入力 {len(files)} ファイルの sha256 は同じ。ひな型は {len(made)} 表")


def test_measure_道具のソース():
    src = (ROOT / "allow_use.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    mods = sorted({a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
                  | {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)})
    assert mods == ["__future__", "argparse", "ast", "csv", "hashlib", "json", "pathlib", "re", "sys", "warnings"]
    calls = [n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", "")
             for n in ast.walk(tree) if isinstance(n, ast.Call)]
    banned = sum(1 for c in calls if c in {"eval", "exec", "compile", "float", "round", "urlopen", "system", "Popen"})
    assert banned == 0
    assert U.own_forbidden_calls() == 0
    n_not_held = len(U.NOT_HELD)
    assert n_not_held == 9
    assert len(U.SIDE) == 6
    print(f"\n[measure] 部品が import している module は {len(mods)} 個で、eval / exec / compile / float / round / "
          f"通信 / 外部コマンド の呼び出しは {banned} 件。出力の末尾の「持たせていないもの」は {n_not_held} 行")


def test_入力を書き換えない():
    tables = load()
    snap = copy.deepcopy(tables)
    U.judge(*tables)
    U.verify(*tables)
    assert tables == snap
