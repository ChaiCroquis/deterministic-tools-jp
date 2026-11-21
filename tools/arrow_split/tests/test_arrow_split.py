"""arrow_split の試験。入力は fixtures/ の合成した 4 表と合成の文書だけ(実在の制度・名前は入っていない)。

記事に載せる測定値は `assert 変数 == 値` で固定する。値が変われば記事も変える。
"""
from __future__ import annotations

import ast
import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
import arrow_split as M  # noqa: E402

FILES = ("entries_a.csv", "symbols_a.csv", "coverage_a.csv", "pairs_a.csv")
KINDS = ("entries", "symbols", "coverage", "pairs")
SHA12 = "9cb25ec34d09"


def load() -> list[list[dict]]:
    return [M.read_table(FX / f, k) for f, k in zip(FILES, KINDS)]


def by_id(out: dict) -> dict[str, dict]:
    return {r["記載 id"]: r for r in out["記載"]}


def test_4表の行数と区分の件数() -> None:
    e, s, c, p = load()
    out = M.check(e, s, c, p)
    sizes = (len(e), len(s), len(c), len(p))
    assert sizes == (26, 7, 12, 13)
    four = [out["4 値"][k] for k in M.CLASSES]
    assert four == [2, 2, 3, 2]
    assert sum(four) == 9
    assert out["割らない記号の件数"] == 10
    extra = [out["別枠"][k] for k in M.EXTRAS]
    assert extra == [2, 1, 1, 1, 1, 1]
    assert sum(extra) == 7
    assert out["件数の合計の検算"] == "4 値 9 + 割らない記号 10 + 別枠 7 = 26 / 記載の台帳の行数 26"
    assert out["検算が合う"] is True
    assert out["台帳に無い記載 id を指す対の行数"] == 1
    assert out["対に使われていない収録の台帳の行数"] == 1
    print(f"\n[measure] entries_a / symbols_a / coverage_a / pairs_a: 記載の台帳 {sizes[0]} 行 / 記号の登録 {sizes[1]} 行 / "
          f"収録の台帳 {sizes[2]} 行 / 対の登録 {sizes[3]} 行")
    print(f"[measure] 4 値は (A) {four[0]} / (B) {four[1]} / (C) {four[2]} / (D) {four[3]}(合計 {sum(four)} 行)、"
          f"割らない記号は {out['割らない記号の件数']} 行、別枠は 6 枠で {sum(extra)} 行(id の重複だけ 2 行)。"
          f"合計 {sum(four) + 10 + sum(extra)} = 記載の台帳の行数")
    print("[measure] 台帳に無い記載 id を指す対は 1 行で、行数に入らない。対に使われていない収録の行は 1 行"
          "(名前が似ていても結び付かない)")


def test_意味の記号ごとの件数() -> None:
    out = M.check(*load())
    got = out["意味の記号ごとの件数"]
    assert got == {"公表と適用": 2, "前後の値": 9, "対応": 3, "後だけ": 2, "日付と出来事": 1, "版": 1, "行き先": 1}
    assert sum(got.values()) == 19
    not_before_after = sum(v for k, v in got.items() if k not in ("前後の値", "後だけ"))
    assert not_before_after == 8
    print(f"[measure] 意味の記号ごとの件数(別枠を除く {sum(got.values())} 行): 前後の値 9 / 後だけ 2 / 対応 3 / 公表と適用 2 / "
          f"日付と出来事 1 / 行き先 1 / 版 1。前後の値でも後だけでもない記号は {not_before_after} 行")


def test_矢印の字だけで拾うと混ざる行数() -> None:
    e, s, c, p = load()
    out = by_id(M.check(e, s, c, p))
    one_arrow = [x for x in e if x["text"].count(M.ARROW) == 1]
    any_arrow = [x for x in e if M.ARROW in x["text"]]
    no_arrow = [x for x in e if M.ARROW not in x["text"]]
    split = [x for x in one_arrow if out[x["entry_id"]]["前"]]
    other_meaning = [x for x in one_arrow if out[x["entry_id"]]["区分"] == M.NOSPLIT]
    after_only_no_arrow = [x for x in no_arrow if x["symbol"] == "後だけ"]
    assert (len(any_arrow), len(one_arrow), len(split), len(other_meaning)) == (23, 22, 9, 8)
    assert len(one_arrow) - len(split) - len(other_meaning) == 5
    assert len(after_only_no_arrow) == 2
    print(f"[measure] 矢印の字を含む記載は {len(any_arrow)} 行、ちょうど 1 つ含むのは {len(one_arrow)} 行。"
          f"そのうち前と後に割られたのは {len(split)} 行で、{len(other_meaning)} 行は前後の値でない意味の記号、"
          f"残り 5 行は別枠。矢印の字が無いのに線が動いた記載(後だけ)は {len(after_only_no_arrow)} 行")


def test_切った文字列はそのまま返る() -> None:
    out = by_id(M.check(*load()))
    got = {i: (out[i]["前"], out[i]["後"], out[i]["日付の記載"]) for i in ("E01", "E03", "E04", "E05", "E06", "E08")}
    assert got == {
        "E01": ("300 円", "320 円", "2024-04"),
        "E03": ("上限 60", "65 歳", "2021-04"),
        "E04": ("2", "1 か月", "2025-04"),
        "E05": ("0.5%", "0.4%", "2022-04"),
        "E06": ("1/3", "1/2 等", "2009-04"),
        "E08": ("A 区分", "B 区分", "2023-01"),
    }
    assert out["E07"]["日付の記載"] == "" and out["E09"]["日付の記載"] == ""
    for r in out.values():
        for v in (r["前"], r["後"]):
            assert isinstance(v, str)
    print("[measure] 切った文字列: `上限 60→65 歳` は 前 `上限 60` / 後 `65 歳`、`1/3→1/2 等` は 前 `1/3` / 後 `1/2 等`。"
          "数にも直さず、単位も日も補わない(日付の記載が空の 2 行は空のまま)")


def test_印の件数() -> None:
    out = M.check(*load())
    rows = [r for r in out["記載"] if r["区分"] in M.CLASSES]
    n = {f: sorted(r["記載 id"] for r in rows if f in r["印"]) for f in (M.F_UNIT, M.F_ETC, M.F_NOSIDE, M.F_MIXED)}
    assert n == {M.F_UNIT: ["E03", "E04"], M.F_ETC: ["E06", "E09"], M.F_NOSIDE: ["E04"], M.F_MIXED: ["E07"]}
    b = by_id(out)
    assert b["E03"]["区分"] == M.B and b["E04"]["区分"] == M.B and b["E07"]["区分"] == M.C
    # 印は判定に入らない: 文字列の印が付く行の文字列を、印が付かない形に替えても区分は同じ
    e, s, c, p = load()
    e2 = [{**x, "text": "60 歳→65 歳"} if x["entry_id"] == "E03" else x for x in e]
    assert by_id(M.check(e2, s, c, p))["E03"]["区分"] == M.B
    assert by_id(M.check(e2, s, c, p))["E03"]["印"] == []
    print(f"[measure] 補助の印: 単位の字が片側だけ {len(n[M.F_UNIT])} 行 / 後ろに「等」が付く {len(n[M.F_ETC])} 行。"
          f"収録の側の印: 前後の別が書かれていない {len(n[M.F_NOSIDE])} 行 / 収録と未収録が両方在る {len(n[M.F_MIXED])} 行。"
          "どれも区分には使っていない")


def test_収録の記載は対に書いた分だけ横に置く() -> None:
    e, s, c, p = load()
    out = by_id(M.check(e, s, c, p))
    assert [x["収録の id"] for x in out["E10"]["収録の記載"]] == ["K11"]
    assert out["E10"]["区分"] == M.NOSPLIT
    assert out["E05"]["収録の記載"] == [{"収録の id": "K07", "状態": "未収録", "側": "", "出典": "合成の状況の記録 L31"}]
    # 収録の台帳の rule 名を全部同じ字にしても、区分は 1 行も動かない(名前の似かたで結び付けない)
    base = M.check(e, s, c, p)
    c2 = [{**x, "rule": "減額の率"} for x in c]
    same_name = M.check(e, s, c2, p)
    assert same_name["sha256"] == base["sha256"]
    # 対に使われていない収録の行(K12 = 名前が E05 の rule と似ている)を未収録に替えても同じ
    c3 = [{**x, "state": "未収録"} if x["cov_id"] == "K12" else x for x in c]
    moved = sum(1 for i, r in by_id(M.check(e, s, c3, p)).items() if r != out[i])
    assert moved == 0
    print(f"[measure] 収録の台帳の rule 名を {len(c)} 行すべて同じ字に替えても sha256 は同じ。"
          f"対に書かれていない収録の行の状態を替えて動いた記載は {moved} 行(= 名前で結び付ける経路が無い)")


def test_字面から意味を当てない() -> None:
    e, s, c, p = load()
    base = by_id(M.check(e, s, c, p))
    targets = [x["entry_id"] for x in e if base[x["entry_id"]]["区分"] == M.NOSPLIT]
    e2 = [{**x, "text": "10%→20%"} if x["entry_id"] in targets else x for x in e]
    got = by_id(M.check(e2, s, c, p))
    still = sum(1 for i in targets if got[i]["区分"] == M.NOSPLIT and got[i]["前"] == "")
    assert (len(targets), still) == (10, 10)
    print(f"[measure] 割らない記号の {len(targets)} 行の文字列を、前後の値に見える `10%→20%` に替えても "
          f"{still} 行とも割られない({still}/{len(targets)})")


def test_文書の行の写しから矢印の行を数える() -> None:
    e = load()[0]
    lines = (FX / "doc_a.md").read_text(encoding="utf-8").split("\n")[:-1]
    got = M.scan(lines, "合成の文書", e)
    assert got["文書の行数"] == 37
    assert got["矢印の字を含む行"] == 26
    assert got["うち台帳に在る行"] == 22
    assert got["矢印の字を含むのに台帳に無い行"] == {"件数": 4, "行番号": [27, 34, 35, 36]}
    assert got["記載の文字列が出典の行に無い記載 id"] == []
    e2 = [{**x, "text": "300円→320円"} if x["entry_id"] == "E01" else x for x in e]
    assert M.scan(lines, "合成の文書", e2)["記載の文字列が出典の行に無い記載 id"] == ["E01"]
    print(f"[measure] 合成の文書 {got['文書の行数']} 行のうち矢印の字を含むのは {got['矢印の字を含む行']} 行、"
          f"台帳に在るのは {got['うち台帳に在る行']} 行、台帳に無いのは 4 行。"
          "台帳の文字列から空白を 2 つ抜くと、その 1 行が「出典の行に無い」と返る")


def test_行順を入れ替えても同じ指紋() -> None:
    e, s, c, p = load()
    base = M.check(e, s, c, p)["sha256"]
    shas = []
    for k in range(5):
        if k == 4:
            tables = [t[::-1] for t in (e, s, c, p)]
        else:
            tables = [t[k * 3 % len(t):] + t[:k * 3 % len(t)] for t in (e, s, c, p)]
        shas.append(M.check(*tables)["sha256"])
    same = sum(1 for x in shas if x == base)
    assert same == 5
    assert base[:12] == SHA12
    print(f"[measure] 4 表の行順を 5 通りに並べて読み直し: 判定部分の sha256 は 5 回とも同じ"
          f"({same}/5 一致、先頭 12 桁 {base[:12]})")


def test_verify_5つ() -> None:
    v = M.verify(*load())
    assert v["ok"] is True
    assert v["4 記号を割らない記号に替えるとその 1 行だけが割られなくなる"] == {"確かめた件数": 9, "合った件数": 9}
    assert v["5 対を 1 行抜くとその記載だけが (D) へ動く"] == {"確かめた件数": 4, "合った件数": 4}
    print("[measure] verify: 記号を `前後の値` から割らない記号へ替えると、その 1 行だけが割られなくなる(9/9)。"
          "対が 1 行だけの 4 行は、その対を抜くとその記載だけが (D) へ動く(4/4)")


def test_止まる理由コード() -> None:
    e, s, c, p = load()
    cases = {
        M.STOP_SYM_SRC: (e, [{**s[0], "source": ""}] + s[1:], c, p),
        M.STOP_SYM_DUP: (e, s + [s[0]], c, p),
        M.STOP_COV: (e, s, [{**c[0], "state": "たぶん収録"}] + c[1:], p),
        M.STOP_PAIR: (e, s, c, [{**p[0], "side": "両方"}] + p[1:]),
    }
    stopped = 0
    for reason, tables in cases.items():
        out = M.check(*tables)
        assert out["ok"] is False and out["止まった理由"] == reason and out["記載"] == []
        assert "4 値" not in out
        stopped += 1
    assert (len(M.STOPS), stopped) == (4, 4)
    assert M.check(e, s, c + [c[0]], p)["止まった理由"] == M.STOP_COV
    assert M.check(e, s, [{**c[0], "source": ""}] + c[1:], p)["止まった理由"] == M.STOP_COV
    assert M.check(e, s, c, [{**p[0], "source": ""}] + p[1:])["止まった理由"] == M.STOP_PAIR
    print(f"[measure] 止まる理由コードは {len(M.STOPS)} 個で、4 通りとも区分を 1 行も返さない({stopped}/4)")


def test_表として読めない崩し方は例外(tmp_path: Path) -> None:
    bad = {
        "列が足りない記載": ("entries", "entry_id,rule,text\nE1,r,a→b\n"),
        "行が無い記載": ("entries", "entry_id,rule,field,text,symbol,date_text,source\n"),
        "列が足りない記号": ("symbols", "symbol,source\n前後の値,x\n"),
        "行が無い記号": ("symbols", "symbol,split,source\n"),
        "列が足りない収録": ("coverage", "cov_id,state\nK1,収録\n"),
        "列が足りない対": ("pairs", "entry_id,cov_id\nE1,K1\n"),
    }
    raised = 0
    for kind, body in bad.values():
        f = tmp_path / f"{kind}_{raised}.csv"
        f.write_text(body, encoding="utf-8")
        with pytest.raises(ValueError):
            M.read_table(f, kind)
        raised += 1
    assert raised == 6
    empty_pairs = tmp_path / "p.csv"
    empty_pairs.write_text("entry_id,cov_id,side,source\n", encoding="utf-8")
    assert M.read_table(empty_pairs, "pairs") == []
    print(f"[measure] 表として読めない崩し方 6 通りは 6 通りとも例外で止まる({raised}/6)。対の登録表だけは 0 行でも読める")


def test_CLIは入力を書き換えない(tmp_path: Path) -> None:
    names = FILES + ("doc_a.md",)
    before = {f: hashlib.sha256((FX / f).read_bytes()).hexdigest() for f in names}
    args = [str(FX / f) for f in FILES]
    exe = [sys.executable, "-X", "utf8", str(ROOT / "arrow_split.py")]
    r1 = subprocess.run([*exe, "check", *args, "--doc", str(FX / "doc_a.md"), "--label", "合成の文書"], capture_output=True)
    r2 = subprocess.run([*exe, "verify", *args], capture_output=True)
    bad = tmp_path / "bad.csv"
    bad.write_text("x\n1\n", encoding="utf-8")
    r3 = subprocess.run([*exe, "check", str(bad), *args[1:]], capture_output=True)
    codes = (r1.returncode, r2.returncode, r3.returncode)
    assert codes == (0, 0, 2)
    assert "矢印の字を含むのに台帳に無い行" in r1.stdout.decode("utf-8")
    after = {f: hashlib.sha256((FX / f).read_bytes()).hexdigest() for f in names}
    assert after == before
    made = M.init(tmp_path / "hinagata")
    assert len(made) == 4
    sym = M.read_table(tmp_path / "hinagata" / "symbols.csv", "symbols")
    assert len(sym) == 7 and [x["symbol"] for x in sym if x["split"] == M.SPLIT_MARK] == ["前後の値"]
    with pytest.raises(ValueError):
        M.init(tmp_path / "hinagata")
    print(f"[measure] コマンドの終了コードは check 0 / verify 0 / 読めない表 2。走らせる前後で入力 {len(names)} ファイルの "
          f"sha256 は同じ。ひな型は 4 表で、記号の登録は {len(sym)} 行(割る印は `前後の値` の 1 行だけ)")


def test_持たせていない呼び出し() -> None:
    tree = ast.parse((ROOT / "arrow_split.py").read_text(encoding="utf-8"))
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mods.add((node.module or "").split(".")[0])
    assert mods == {"__future__", "argparse", "csv", "hashlib", "json", "pathlib", "sys"}
    banned = {"eval", "exec", "float", "round", "urlopen", "now", "today", "time", "system", "Popen", "run"}
    calls = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name in banned:
                calls += 1
        if isinstance(node, ast.Constant) and isinstance(node.value, float):
            calls += 1
    assert calls == 0
    assert len(mods) == 7
    assert len(M.NOT_HELD) == 10
    assert len(M.EXTRAS) == 6 and len(M.CLASSES) == 4
    print(f"[measure] 部品が import している module は {len(mods)} 個で、eval / exec / float / round / 現在時刻 / "
          f"通信 / 外部コマンド の呼び出しと小数の定数は {calls} 件。出力の末尾の「持たせていないもの」は {len(M.NOT_HELD)} 行")
