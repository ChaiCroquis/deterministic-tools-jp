"""call_axis の試験。合成した 4 表(fixtures/*_a.csv)と合成の文書だけを使う。実在の制度・名前は入っていない。

記事に載せる測定値は、ここで `assert 変数 == 値` として固定している(値が変われば記事も変える)。
`python -m pytest tools/call_axis -q -s` で [measure] の行が出る。
"""
from __future__ import annotations

import ast
import copy
import hashlib
import random
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
import call_axis as M  # noqa: E402

KINDS = ("words", "roles", "notes", "pairs")
PATHS = [FIX / f"{k}_a.csv" for k in KINDS]


def load() -> list[list[dict]]:
    return [M.read_table(p, k) for p, k in zip(PATHS, KINDS)]


def classed(out: dict) -> dict[str, dict]:
    return {r["語 id"]: r for r in out["語"] if not r["区分"].startswith(M.BOX_HEAD)}


def test_件数_区分と別枠の合計が語の台帳の行数に戻る() -> None:
    words, roles, notes, pairs = load()
    out = M.check(words, roles, notes, pairs)
    assert out["ok"]
    assert (len(words), len(roles), len(notes), len(pairs)) == (23, 6, 17, 21)
    n4 = list(out["区分"].values())
    assert n4 == [4, 3, 5, 3]
    assert sum(n4) == 15
    nb = list(out["別枠"].values())
    assert nb == [1, 1, 1, 2, 1, 2]
    assert sum(nb) == 8
    assert sum(n4) + sum(nb) == len(words) == 23
    assert out["件数の合計の検算"] == "区分 15 + 別枠 8 = 23 / 語の台帳の行数 23"
    print(f"\n[measure] words_a / roles_a / notes_a / pairs_a: 語の台帳 {len(words)} 行 / 働きの登録 {len(roles)} 行 / "
          f"記載の台帳 {len(notes)} 行 / 対の登録 {len(pairs)} 行")
    print(f"[measure] 区分は (A) {n4[0]} / (B) {n4[1]} / (C) {n4[2]} / (D) {n4[3]}(合計 {sum(n4)} 語)、"
          f"別枠は 6 枠で {sum(nb)} 行。合計 {sum(n4) + sum(nb)} = 語の台帳の行数")


def test_並びは働きの記号から旧軸の順で_旧軸の順とは別の並びになる() -> None:
    out = M.check(*load())
    rows = list(classed(out).values())
    keys = [(r["働きの記号"], r["旧軸の順"]) for r in rows]
    assert keys == sorted(keys)
    by_role = out["働きの記号ごとの語の件数"]
    assert by_role == {"まとめる": 2, "区間で分ける": 2, "大小で選ぶ": 3, "日を数える": 2, "端数を落とす": 3, "表を引く": 3}
    old = [r["旧軸の順"] for r in rows]
    assert old == [14, 15, 3, 13, 7, 8, 9, 10, 11, 4, 5, 6, 1, 2, 12]
    same_place = sum(1 for i, v in enumerate(old, 1) if v == i)
    assert same_place == 1
    # 旧軸で隣り合う語が、新軸でも同じ段に在る組の数
    role_of = {r["旧軸の順"]: r["働きの記号"] for r in rows}
    neighbours = sum(1 for i in range(1, 15) if role_of[i] == role_of[i + 1])
    assert neighbours == 7
    print("[measure] 働きの記号ごとの語の件数(別枠を除く 15 語、6 段): " + " / ".join(f"{k} {v}" for k, v in by_role.items()))
    print(f"[measure] 並べ直した後の旧軸の順: {old}。旧軸と同じ位置に残った語は {same_place} 語。"
          f"旧軸で隣り合う 14 組のうち同じ段に入ったのは {neighbours} 組")


def test_補助の印は区分に使わない() -> None:
    words, roles, notes, pairs = load()
    out = M.check(words, roles, notes, pairs)
    marks = out["補助の印(区分には使わない)"]
    assert marks[M.MARK_EDGE] == 5
    assert marks[M.MARK_LITERAL] == 10
    assert out["対"] == {"横に置いた対の数": 17, "うち語の文字列を literal に含む記載との対": 4,
                         "台帳に無い語 id を指す対の行数": 1, "同じ対が重なった行数": 1}
    edge_roles = {r["role"] for r in roles if r["edge"] == M.EDGE}
    edge_words = [r for r in classed(out).values() if r["働きの記号"] in edge_roles]
    assert len(edge_words) == 10
    assert sum(1 for r in edge_words if r[M.SIDE_V]) == 5
    # 境目の印を登録表から全部外しても、区分は 1 語も動かない
    flat = M.check(words, [dict(r, edge="") for r in roles], notes, pairs)
    moved = sum(1 for k, r in classed(out).items() if classed(flat)[k]["区分"] != r["区分"])
    assert moved == 0
    assert flat["補助の印(区分には使わない)"][M.MARK_EDGE] == 0
    unplaced = out["どの語の横にも置かれなかった記載の件数"]
    assert unplaced == {"式の一覧": 1, "検証の表": 2}
    print(f"[measure] 境目を持つ働きの語は {len(edge_words)} 語で、検証の側の記載が在るのは 5 語、無い印が付いたのは "
          f"{marks[M.MARK_EDGE]} 語。境目の印を登録表から全部外しても区分が動いた語は {moved} 語")
    print(f"[measure] 横に置いた対は 17 で、語の文字列が記載に literal で含まれるのは 4、含まれないのは 13。"
          f"`cut0` と `cut(` は含まれない側。どの語の横にも置かれなかった記載は 式の一覧 {unplaced['式の一覧']} / "
          f"検証の表 {unplaced['検証の表']}。台帳に無い語 id を指す対は 1 行で、行数に入らない")


def test_名前から働きを当てず_名前で記載と結び付けない() -> None:
    words, roles, notes, pairs = load()
    base = M.check(words, roles, notes, pairs)
    # 語の文字列を 23 行すべて同じ字に替えても、段と区分は変わらない
    same = M.check([dict(w, word="x") for w in words], roles, notes, pairs)
    a, b = classed(base), classed(same)
    kept = sum(1 for k in a if (a[k]["働きの記号"], a[k]["区分"], a[k]["旧軸の順"]) == (b[k]["働きの記号"], b[k]["区分"], b[k]["旧軸の順"]))
    assert kept == len(a) == 15
    assert same["区分"] == base["区分"] and same["別枠"] == base["別枠"]
    # どの語とも対にしていない記載 3 行の文字列を、語の文字列そのものに替えても、区分は変わらない
    free = [n["note_id"] for n in notes if n["note_id"] in ("S7", "T8", "T9")]
    lure = M.check(words, roles, [dict(n, text="up0 months avg_of") if n["note_id"] in free else n for n in notes], pairs)
    assert len(free) == 3
    assert lure["区分"] == base["区分"]
    assert [r["区分"] for r in lure["語"]] == [r["区分"] for r in base["語"]]
    assert lure["どの語の横にも置かれなかった記載の件数"] == base["どの語の横にも置かれなかった記載の件数"]
    # 対に書かれた記載の文字列を全部「x」に替えても区分は同じ(印だけが動く)
    blank = M.check(words, roles, [dict(n, text="x") for n in notes], pairs)
    assert blank["区分"] == base["区分"]
    assert blank["対"]["うち語の文字列を literal に含む記載との対"] == 0
    print(f"[measure] 語の文字列を 23 行すべて同じ字に替えても、段と区分が同じだった語は {kept}/15")
    print("[measure] 対にしていない記載 3 行の文字列を、(D) の 3 語の名前そのものに替えても、区分は 1 語も動かない"
          "(= 名前で結び付ける経路が無い)")


def test_行順を入れ替えても同じ_sha256() -> None:
    tables = load()
    base = M.check(*tables)
    rng = random.Random(61)
    same = 0
    for _ in range(5):
        shuffled = [rng.sample(t, len(t)) for t in tables]
        same += M.check(*shuffled)["sha256"] == base["sha256"]
    assert same == 5
    assert base["sha256"][:12] == "caea1e471f29"
    print(f"[measure] 4 表の行順を 5 通りに並べて読み直し: 判定部分の sha256 は 5 回とも同じ"
          f"({same}/5 一致、先頭 12 桁 {base['sha256'][:12]})")


def test_verify_5つ() -> None:
    out = M.verify(*load())
    assert out["ok"] and list(out["結果"].values()) == [True] * 5
    assert out["④ 試した語"] == "15/15"
    assert out["⑤ 試した対"] == "17/17"
    assert out["⑤ で区分が動いた対"] == 15
    print(f"[measure] verify: 働きの記号を別の登録済みの記号に替えると、その語の段だけが動き区分は変わらない"
          f"({out['④ 試した語']})。対を 1 行抜くと、その語だけが動く({out['⑤ 試した対']}、うち区分が動いたのは "
          f"{out['⑤ で区分が動いた対']})")


def test_文書の行の写しと突き合わせる() -> None:
    words, roles, notes, pairs = load()
    doc = (FIX / "doc_a.md").read_text(encoding="utf-8").splitlines()
    d = M.check_doc(words, notes, doc, "文書")
    assert d == {"文書の行数": 20, "出典がこの文書の行を指す行数": 39, "文字列が出典の行に無い id": []}
    bad_notes = [dict(n, text=n["text"].replace(" ", "")) if n["note_id"] == "T3" else n for n in notes]
    d2 = M.check_doc(words, bad_notes, doc, "文書")
    assert d2["文字列が出典の行に無い id"] == ["T3"]
    print(f"[measure] 合成の文書 {d['文書の行数']} 行に対し、出典がその行を指す {d['出典がこの文書の行を指す行数']} 行は"
          f"どれも文字列が出典の行に在る。記載 1 行から空白を抜くと、その 1 行が「出典の行に無い」と返る")


@pytest.mark.parametrize("code,table,patch", [
    ("ROLE_TABLE", 1, {"source": ""}),
    ("NOTE_TABLE", 2, {"side": "たぶん式"}),
    ("PAIR_TABLE", 3, {"source": ""}),
    ("WORD_TABLE", 0, {"order": "三"}),
])
def test_登録の側が崩れていたら理由コードで止まる(code, table, patch) -> None:
    tables = load()
    tables[table] = [dict(tables[table][0], **patch)] + tables[table][1:]
    out = M.check(*tables)
    assert not out["ok"] and out["止まった理由"] == code and out["語"] == []
    assert "区分" not in out and "sha256" not in out


def test_止まる理由は4個で_どれも区分を返さない() -> None:
    assert len(M.STOPS) == 4
    cases = [(1, {"role": "表を引く"}, 1), (1, {"edge": "たぶん"}, 0), (2, {"note_id": "S2"}, 0), (2, {"text": ""}, 0),
             (3, {"note_id": ""}, 0), (0, {"word": ""}, 0), (0, {"order": "1.5"}, 0), (0, {"order": "-1"}, 0)]
    stopped = 0
    for table, patch, at in cases:
        tables = load()
        tables[table] = [dict(r, **patch) if i == at else r for i, r in enumerate(tables[table])]
        out = M.check(*tables)
        stopped += (not out["ok"]) and out["語"] == []
    assert stopped == len(cases) == 8
    print(f"[measure] 止まる理由コードは {len(M.STOPS)} 個。崩し方 8 通りは 8 通りとも区分を 1 行も返さずに止まる({stopped}/8)")


def test_表として読めないものは例外(tmp_path: Path) -> None:
    good = PATHS[0].read_text(encoding="utf-8")
    broken = {
        "列の名前が違う": good.replace("word_id,word,order", "id,word,order", 1),
        "列の順が違う": good.replace("word_id,word,order,role,source", "word,word_id,order,role,source", 1),
        "欄が足りない行": good + "G99,zz,99\n",
        "欄が多い行": good + "G99,zz,99,表を引く,文書 L3,余り\n",
        "0 行": "word_id,word,order,role,source\n",
        "空のファイル": "",
    }
    raised = 0
    for name, text in broken.items():
        p = tmp_path / "w.csv"
        p.write_text(text, encoding="utf-8")
        with pytest.raises(M.TableError):
            M.read_table(p, "words")
        raised += 1
    assert raised == 6
    with pytest.raises(M.TableError):
        M.read_table(tmp_path / "無い.csv", "words")
    empty = tmp_path / "p.csv"
    empty.write_text("word_id,note_id,source\n", encoding="utf-8")
    assert M.read_table(empty, "pairs") == []
    words, roles, notes, _ = load()
    alone = M.check(words, roles, [], [])
    assert alone["ok"] and alone["区分"][M.CLASSES["D"]] == 16
    print(f"[measure] 表として読めない崩し方 6 通りは 6 通りとも例外で止まる({raised}/6)。"
          "記載の台帳と対の登録表は 0 行でも読め、そのときは別枠でない語がすべて (D) になる")


def test_コマンドの終了コードと_入力を書き換えないこと(tmp_path: Path, capsys) -> None:
    files = [str(p) for p in PATHS]
    doc = FIX / "doc_a.md"
    before = [hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in files + [str(doc)]]
    rc_check = M.main(["check", *files, "--doc", str(doc), "--label", "文書"])
    rc_verify = M.main(["verify", *files])
    bad = tmp_path / "bad.csv"
    bad.write_text("x,y\n1,2\n", encoding="utf-8")
    rc_bad = M.main(["check", str(bad), *files[1:]])
    stop = tmp_path / "roles.csv"
    stop.write_text("role,edge,source\n表を引く,境目,\n", encoding="utf-8")
    rc_stop = M.main(["check", files[0], str(stop), *files[2:]])
    capsys.readouterr()
    after = [hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in files + [str(doc)]]
    assert (rc_check, rc_verify, rc_bad, rc_stop) == (0, 0, 2, 3)
    assert before == after and len(before) == 5
    made = M.init(tmp_path / "t")
    assert made == ["words.csv", "roles.csv", "notes.csv", "pairs.csv"]
    assert len(M.read_table(tmp_path / "t" / "roles.csv", "roles")) == 3
    assert M.init(tmp_path / "t") == []          # 既に在るひな型は書き換えない
    print(f"[measure] コマンドの終了コードは check {rc_check} / verify {rc_verify} / 読めない表 {rc_bad} / "
          f"理由コードで停止 {rc_stop}。走らせる前後で入力 5 ファイルの sha256 は同じ。ひな型は 4 表で、働きの登録は 3 行")


def test_check_は入力を書き換えない() -> None:
    tables = load()
    saved = copy.deepcopy(tables)
    M.check(*tables)
    M.verify(*tables)
    assert tables == saved


def test_持たせていない経路が実装に無い() -> None:
    src = (ROOT / "call_axis.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split(".")[0])
    assert mods == {"__future__", "argparse", "csv", "hashlib", "json", "sys", "pathlib"}
    banned = {"eval", "exec", "compile", "float", "round", "system", "popen", "urlopen", "now", "today", "time"}
    calls = [n.func.id if isinstance(n.func, ast.Name) else n.func.attr for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, (ast.Name, ast.Attribute))]
    hits = [c for c in calls if c in banned]
    floats = [n for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, float)]
    assert hits == [] and floats == []
    assert len(M.NOT_HELD) == 9
    assert M.check(*load())["持たせていないもの"] == M.NOT_HELD
    print(f"[measure] 部品が import している module は {len(mods)} 個で、eval / exec / compile / float / round / 現在時刻 / "
          f"通信 / 外部コマンド の呼び出しと小数の定数は {len(hits) + len(floats)} 件。"
          f"出力の末尾の「持たせていないもの」は {len(M.NOT_HELD)} 行")
