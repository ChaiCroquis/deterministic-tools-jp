"""halt_depth の試験。合成した 4 表(fixtures/*_a.csv)だけを使う。段の名前も印も架空で、実在の記録は入っていない。

記事に載せる測定値は、ここで `assert 変数 == 値` として固定している(値が変われば記事も変える)。
`python -m pytest tools/halt_depth -q -s` で [measure] の行が出る。
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import random
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
import halt_depth as M  # noqa: E402

KINDS = ("runs", "marks", "stages", "hides")
PATHS = [FIX / f"{k}_a.csv" for k in KINDS]


def load() -> list[list[dict]]:
    return [M.read_table(p, k) for p, k in zip(PATHS, KINDS)]


def by_run(out: dict) -> dict[str, dict]:
    return {r["回"]: r for r in out["回"]}


def letter(r: dict) -> str:
    return r["区分"][1]


def test_件数_区分と別枠の合計が回の台帳の行数に戻る() -> None:
    runs, marks, stages, hides = load()
    out = M.check(runs, marks, stages, hides)
    assert out["ok"]
    assert (len(runs), len(marks), len(stages), len(hides)) == (16, 12, 4, 2)
    n5 = list(out["区分"].values())
    assert n5 == [2, 3, 2, 4, 2]
    assert sum(n5) == 13
    nb = list(out["別枠"]["回"].values())
    assert nb == [2, 1]
    assert sum(n5) + sum(nb) == 16 == len(runs)
    mb = list(out["別枠"]["印"].values())
    assert mb == [1, 1, 1, 2, 1]
    assert out["使った印"] == {"通過の印": 5, "止まった印": 1}
    assert sum(mb) + 5 + 1 == 12 == len(marks)
    print(f"\n[measure] runs_a / marks_a / stages_a / hides_a: 回の台帳 {len(runs)} 行 / 印の登録 {len(marks)} 行 / "
          f"段の登録 {len(stages)} 行 / 伏せる行の登録 {len(hides)} 行")
    print(f"[measure] 区分は (A) {n5[0]} / (B) {n5[1]} / (C) {n5[2]} / (D) {n5[3]} / (E) {n5[4]}(合計 {sum(n5)} 回)、"
          f"別枠の回は {sum(nb)} 回。合計 {sum(n5) + sum(nb)} = 回の台帳の行数。使った印は 6 個、別枠の印は 5 枠で {sum(mb)} 行")


def test_同じ状態の語の回が_下の層では別の区分に分かれる() -> None:
    out = M.check(*load())
    failed = [r for r in out["回"] if r["状態"] == "failed"]
    assert len(failed) == 8
    per = {}
    for r in failed:
        per[letter(r)] = per.get(letter(r), 0) + 1
    assert per == {"A": 2, "B": 3, "E": 2, "C": 1}
    last = [r["在った通過の印のうち並び順が最後のもの"] for r in failed if letter(r) == "B"]
    assert last == ["K2", "K1", "K3"]
    stages_seen = {tuple(r["印が在った段"]) for r in failed}
    assert len(stages_seen) == 6
    print(f"[measure] 状態が failed の回は {len(failed)} 回で、区分は (A) 2 / (B) 3 / (C) 1 / (E) 2 の 4 通りに分かれる。"
          f"(B) の 3 回で、在った通過の印のうち並び順が最後のものは {last} と 3 回とも違う")


def test_印ごとの在る回数と行の内訳() -> None:
    out = M.check(*load())
    assert out["印ごとの在る回数"] == {"K1": 6, "K2": 5, "K3": 3, "K4": 3, "K5": 3, "K9": 5}
    ln = out["行の内訳"]
    assert ln == {"行数の合計": 40, "印に当たった行": 27, "伏せた行": 4, "空の行": 4, "どの印にも当たらなかった行": 5}
    assert 27 + 4 + 4 + 5 == 40
    for r in out["回"]:
        assert r["印に当たった行の件数"] + r["伏せた行の件数"] + r["空の行の件数"] + r["どの印にも当たらなかった行の件数"] == r["行数"]
    print(f"[measure] エラーの欄を割った行は合わせて {ln['行数の合計']} 行で、印に当たった行 {ln['印に当たった行']} / 伏せた行 {ln['伏せた行']} / "
          f"空の行 {ln['空の行']} / どの印にも当たらなかった行 {ln['どの印にも当たらなかった行']}。4 つの合計は行数に戻る")


def test_補助の印は区分に入らない() -> None:
    runs, marks, stages, hides = load()
    out = M.check(runs, marks, stages, hides)
    flags = out["補助の印(区分には使わない)"]
    assert flags[M.FLAG_REPEAT] == [{"回": "r02", "印": "K3", "行数": 3}, {"回": "r09", "印": "K3", "行数": 2}]
    assert flags[M.FLAG_VARY] == ["K1", "K2", "K3", "K4", "K5", "K9"]
    # 印の後ろの文字列を全部落とし、同じ印の 2 行目以降も消す → 補助の印は 2 つとも消えるが、区分は動かない
    texts = [m["text"] for m in marks if m["text"]]
    cut = copy.deepcopy(runs)
    for r in cut:
        seen, lines = set(), []
        for line in M.split_lines(r["error"]):
            hit = [t for t in texts if line.startswith(t)]
            if hit and not any(h["text"] in line for h in hides):
                if hit[0] in seen:
                    continue
                seen.add(hit[0])
                line = hit[0]
            lines.append(line)
        r["error"] = "\n".join(lines)
    out2 = M.check(cut, marks, stages, hides)
    same = sum(1 for k, r in by_run(out).items() if by_run(out2)[k]["区分"] == r["区分"])
    assert same == 13
    f2 = out2["補助の印(区分には使わない)"]
    assert f2[M.FLAG_REPEAT] == []
    assert f2[M.FLAG_VARY] == []              # r09 の K1 は伏せた行にしか無く、比べる文字列が無いので数えない
    print(f"[measure] 補助の印: 同じ印が 1 回の中に 2 行以上在るのは 2 件(3 行と 2 行)、後ろの文字列が回によって違う印は 6 個。"
          f"後ろの文字列を落とし重なりを消しても、区分が同じだった回は {same}/13")


def test_状態の文字列は区分に使わない() -> None:
    runs, marks, stages, hides = load()
    out = M.check(runs, marks, stages, hides)
    same_word = copy.deepcopy(runs)
    for r in same_word:
        r["status"] = "ok"
    out2 = M.check(same_word, marks, stages, hides)
    same = sum(1 for k, r in by_run(out).items() if by_run(out2)[k]["区分"] == r["区分"])
    assert same == 13
    assert [r["状態"] for r in out["回"]] == [r["status"] for r in runs if r["run_id"] not in ("r14", "r15")]
    print(f"[measure] 状態の文字列を 16 行すべて ok に替えても、区分が同じだった回は {same}/13(状態の語は写すだけで読まない)")


def test_伏せる行は件数だけが返り_中身はどの欄にも無い() -> None:
    runs, marks, stages, hides = load()
    out = M.check(runs, marks, stages, hides)
    dump = json.dumps(out, ensure_ascii=False)
    secrets = ["run.py", "match.py", "x.py", "a.csv", "line 40", "/srv/"]
    found = [s for s in secrets if s in dump]
    assert found == []
    assert out["行の内訳"]["伏せた行"] == 4
    k1 = next(p for p in by_run(out)["r09"]["印"] if p["印"] == "K1")
    assert (k1["在る・無い"], k1["行番号"], k1["後ろの文字列"], k1["うち伏せた行"]) == ("在る", [1], [""], 1)
    # 伏せる行の登録表を空にすると、同じ字が出力に出てくる(伏せているのは登録表の字で、道具が当てたのではない)
    out2 = M.check(runs, marks, stages, [])
    dump2 = json.dumps(out2, ensure_ascii=False)
    assert out2["行の内訳"]["伏せた行"] == 0
    assert "/srv/in/a.csv" in dump2
    print(f"[measure] 伏せた行は {out['行の内訳']['伏せた行']} 行。伏せた行に在った字 {len(secrets)} 通りは出力のどこにも無い(0/{len(secrets)})。"
          f"印が伏せた行に当たった 1 件は、在る・行番号 1・後ろの文字列は空で返る")


def test_印は行頭の_literal_だけで当てる() -> None:
    marks = [{"mark_id": "K1", "text": "load done:", "stage": "S1", "order": "1", "kind": "通過の印", "source": "s"},
             {"mark_id": "K3", "text": "  DIFF", "stage": "S1", "order": "3", "kind": "通過の印", "source": "s"}]
    stages = [{"stage": "S1", "name": "取込", "source": "s"}]
    near = [" load done: 1", "LOAD DONE: 1", "xload done: 1", "load done 1", "DIFF id=1", " DIFF id=1", "\tDIFF id=1"]
    runs = [{"run_id": f"n{i}", "status": "failed", "error": e, "source": "s"} for i, e in enumerate(near)]
    out = M.check(runs, marks, stages, [])
    got = sum(1 for r in out["回"] for p in r["印"] if p["行番号"])
    assert got == 0
    assert list(out["区分"].values()) == [0, 0, 7, 0, 0]
    exact = [{"run_id": "e1", "status": "failed", "error": "load done:\n  DIFF", "source": "s"}]
    out2 = M.check(exact, marks, stages, [])
    assert [p["後ろの文字列"] for p in out2["回"][0]["印"]] == [[""], [""]]
    print(f"[measure] 印に似ているが行頭の字が違う 7 通り(前に空白・大文字・前に 1 字・コロン無し・空白の数が違う)は、"
          f"当たった印が {got} 件で 7 回とも (C)")


def test_印の後ろの文字列は数に直さない() -> None:
    marks = [{"mark_id": "K2", "text": "match rows:", "stage": "S1", "order": "1", "kind": "通過の印", "source": "s"}]
    stages = [{"stage": "S1", "name": "照合", "source": "s"}]
    runs = [{"run_id": "a", "status": "failed", "error": "match rows: 120", "source": "s"},
            {"run_id": "b", "status": "failed", "error": "match rows: 0120", "source": "s"},
            {"run_id": "c", "status": "failed", "error": "match rows: 120.0", "source": "s"}]
    out = M.check(runs, marks, stages, [])
    tails = [r["印"][0]["後ろの文字列"][0] for r in out["回"]]
    assert tails == [" 120", " 0120", " 120.0"]
    assert out["補助の印(区分には使わない)"][M.FLAG_VARY] == ["K2"]
    assert len({r["区分"] for r in out["回"]}) == 1
    print("[measure] 後ろの文字列が 120 / 0120 / 120.0 の 3 回は、3 つとも原文のまま返り、「回によって違う」の印が付く(区分は 3 回とも同じ)")


def test_登録表の行順を変えても指紋が同じ() -> None:
    runs, marks, stages, hides = load()
    base = M.check(runs, marks, stages, hides)["指紋"]
    rng = random.Random(62)
    same = 0
    for _ in range(5):
        m, s, h = marks[:], stages[:], hides[:]
        rng.shuffle(m), rng.shuffle(s), rng.shuffle(h)
        same += M.check(runs, m, s, h)["指紋"] == base
    assert same == 5
    assert base[:12] == "4d9f793acb86"
    rev = M.check(runs[::-1], marks, stages, hides)
    assert by_run(rev) == by_run(M.check(runs, marks, stages, hides))
    assert [r["回"] for r in rev["回"]] == [r["回"] for r in M.check(runs, marks, stages, hides)["回"]][::-1]
    print(f"[measure] 登録表 3 つの行順を 5 通りに並べて読み直し: 判定部分の sha256 は 5 回とも同じ({same}/5 一致、先頭 12 桁 {base[:12]})。"
          f"回の台帳を逆順にすると、回ごとの結果は同じで並びだけが逆になる")


def test_verify_は_5_つ見る() -> None:
    runs, marks, stages, hides = load()
    v = M.verify(runs, marks, stages, hides)
    assert v["ok"]
    assert len(v["検査"]) == 5 and all(v["検査"].values())
    assert v["④ 抜いて確かめた印の数"] == "6/6"
    assert v["⑤ 伏せた行の件数"] == 4
    print(f"[measure] verify: 5 つとも通る。印を 1 つ抜いても残りの印の在る・無い・行番号・後ろの文字列が変わらない({v['④ 抜いて確かめた印の数']})。"
          f"後ろの文字列に伏せる字は 0 件")


def test_登録の側が崩れていたら_1_回も並べずに止まる() -> None:
    runs, marks, stages, hides = load()

    def broken(table: str, idx: int, col: str, val: str) -> dict:
        t = {"marks": copy.deepcopy(marks), "stages": copy.deepcopy(stages), "hides": copy.deepcopy(hides)}
        t[table][idx][col] = val
        return M.check(runs, t["marks"], t["stages"], t["hides"])

    cases = [
        (broken("marks", 0, "mark_id", ""), "E1"),
        (broken("marks", 1, "mark_id", "K1"), "E1"),
        (broken("marks", 0, "kind", "たぶん通過"), "E2"),
        (broken("marks", 0, "order", "1.5"), "E3"),
        (broken("marks", 0, "order", ""), "E3"),
        (broken("stages", 0, "name", ""), "E4"),
        (broken("stages", 1, "stage", "S1"), "E4"),
        (broken("hides", 0, "text", ""), "E5"),
    ]
    stopped = 0
    for out, code in cases:
        assert out["ok"] is False and out["理由コード"] == code and out["回"] == []
        stopped += 1
    assert stopped == 8
    assert len(M.REASONS) == 5
    print(f"[measure] 止まる理由コードは {len(M.REASONS)} 個。崩し方 8 通りは 8 通りとも区分を 1 回も返さずに止まる({stopped}/8)")


def test_読めない表は例外で止まり_登録表は_0_行でも読める(tmp_path: Path) -> None:
    bad = {
        "列が足りない": "run_id,status,source\nr1,ok,s\n",
        "0 行": "run_id,status,error,source\n",
        "欄の数が足りない": "run_id,status,error,source\nr1,ok\n",
    }
    stopped = 0
    for name, body in bad.items():
        p = tmp_path / f"{name}.csv"
        p.write_text(body, encoding="utf-8")
        with pytest.raises(M.TableError):
            M.read_table(p, "runs")
        stopped += 1
    with pytest.raises(M.TableError):
        M.read_table(tmp_path / "無い.csv", "runs")
    stopped += 1
    p = tmp_path / "cp932.csv"
    p.write_bytes("run_id,status,error,source\nr1,失敗,,出典\n".encode("cp932"))
    with pytest.raises(M.TableError):
        M.read_table(p, "runs")
    stopped += 1
    p = tmp_path / "bad.jsonl"
    p.write_text('{"status": "ok"}\n', encoding="utf-8")
    with pytest.raises(M.TableError):
        M.read_runs(p)
    stopped += 1
    assert stopped == 6
    runs = load()[0]
    out = M.check(runs, [], [], [])
    assert out["ok"] and list(out["区分"].values()) == [0, 0, 9, 4, 0]
    print(f"[measure] 表として読めない崩し方 6 通りは 6 通りとも例外で止まる({stopped}/6)。登録表 3 つは 0 行でも読め、"
          f"そのときはエラーの文字列が在る 9 回がすべて (C)、空の 4 回が (D) になる")


def test_jsonl_の回の台帳と改行の割り方(tmp_path: Path) -> None:
    p = tmp_path / "history.jsonl"
    rows = [{"status": "ok", "error": None}, {"status": "failed", "error": "load done: 3\nHALT\n"},
            {"status": "failed", "error": "load done: 3\r\nHALT x"}]
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    runs = M.read_runs(p, "履歴")
    assert [(r["run_id"], r["source"]) for r in runs] == [("L1", "履歴 L1"), ("L2", "履歴 L2"), ("L3", "履歴 L3")]
    assert runs[0]["error"] == ""
    _, marks, stages, hides = load()
    out = M.check(runs, marks, stages, hides)
    assert [letter(r) for r in out["回"]] == ["D", "B", "B"]
    assert [r["行数"] for r in out["回"]] == [0, 3, 2]
    assert by_run(out)["L3"]["印"][0]["後ろの文字列"] == [" 3"]
    print("[measure] 1 行 1 回の JSON 3 行を回の台帳として読むと、回 id は L1〜L3、エラーの欄が null の回は (D)。"
          "末尾の改行は空の 1 行に数え(3 行)、CRLF は LF として割る(2 行)")


def test_コマンドの終了コードと_入力を書き換えないこと(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in PATHS]
    args = [str(p) for p in PATHS]
    rc_check = M.main(["check", *args])
    rc_text = M.main(["check", *args, "--text"])
    rc_verify = M.main(["verify", *args])
    rc_unread = M.main(["check", str(tmp_path / "無い.csv"), *args[1:]])
    bad = tmp_path / "marks_bad.csv"
    bad.write_text(PATHS[1].read_text(encoding="utf-8").replace("止まった印", "たぶん"), encoding="utf-8")
    rc_stop = M.main(["check", args[0], str(bad), *args[2:]])
    capsys.readouterr()
    assert (rc_check, rc_text, rc_verify, rc_unread, rc_stop) == (0, 0, 0, 2, 3)
    after = [hashlib.sha256(p.read_bytes()).hexdigest() for p in PATHS]
    assert before == after
    made = M.init(tmp_path / "t")
    assert len(made) == 4 and M.init(tmp_path / "t") == []
    tpl = [tmp_path / "t" / n for n in ("回.csv", "印.csv", "段.csv", "伏せる行.csv")]
    out = M.check(M.read_runs(tpl[0]), M.read_table(tpl[1], "marks"), M.read_table(tpl[2], "stages"), M.read_table(tpl[3], "hides"))
    assert list(out["区分"].values()) == [1, 0, 0, 1, 0]
    print(f"[measure] コマンドの終了コードは check {rc_check} / verify {rc_verify} / 読めない表 {rc_unread} / 理由コードで停止 {rc_stop}。"
          f"走らせる前後で入力 4 ファイルの sha256 は同じ。ひな型は 4 表で、既に在るファイルは書き換えない")


def test_持たせていない経路() -> None:
    src = (ROOT / "halt_depth.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mods.add((node.module or "").split(".")[0])
    assert mods == {"__future__", "argparse", "csv", "hashlib", "json", "sys", "pathlib"}
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    banned = {"eval", "exec", "compile", "float", "round", "Decimal", "re", "match", "search", "now", "today", "time",
              "urlopen", "socket", "system", "Popen", "run"}
    hit = sorted(names & banned)
    assert hit == []
    floats = [n for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, float)]
    assert floats == []
    assert len(M.NOT_HELD) == 7
    out = M.check(*load())
    keys = set(out) | {k for r in out["回"] for k in r} | {k for r in out["回"] for p in r["印"] for k in p}
    assert not [k for k in keys if "原因" in k or "理由" in k or "期待" in k]
    print(f"[measure] 部品が import している module は {len(mods)} 個で、eval / exec / compile / float / round / 正規表現 / 現在時刻 / 通信 / "
          f"外部コマンド の呼び出しと小数の定数は 0 件。出力に原因・理由・期待の欄は無く、「持たせていないもの」は {len(M.NOT_HELD)} 行")
