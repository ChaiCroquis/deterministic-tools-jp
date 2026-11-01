"""fill_owner の試験。合成した 3 枚の表だけを使う(実在の料率・金額・名前は入れない)。

記事に載せる数値は、このファイルの `assert 変数 == 値` が固定している(値が変われば記事も変える)。
`test_measure_*` が記事の「検証」節に載る出力をそのまま印字する。
"""
from __future__ import annotations

import ast
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FX))
import fill_owner as F  # noqa: E402
import make_fixtures as MF  # noqa: E402

TOI = FX / "toi_daichou.csv"
OKIBA = FX / "okiba_touroku.csv"
JIKU = FX / "jiku_teigi.csv"
P = F.PLACES


def load():
    return (F.read_table(TOI, F.TOI_COLS),
            F.load_okiba(F.read_table(OKIBA, F.OKIBA_COLS)),
            F.load_jiku(F.read_table(JIKU, F.JIKU_COLS)))


def run(args: list[str]) -> tuple[int, str]:
    r = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "fill_owner.py")] + args,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout


# ---- 読む / 止まる ------------------------------------------------------------------------

def test_合成の3枚が読める() -> None:
    toi, okiba, jiku = load()
    assert len(toi) == 20
    assert len(okiba) == 8
    assert jiku["新軸の欄名"] != jiku["旧軸の欄名"]


def test_理由コードは12個() -> None:
    assert len(F.TABLE_STOP) == 4
    assert len(F.ASIDE) == 8
    assert len(F.REASONS) == 12


def _broken(tmp_path: Path, which: str, mutate) -> Path:
    """3 枚を写して 1 枚だけ崩す(入力そのものは触らない)。"""
    MF.write_all(tmp_path)
    p = tmp_path / {"toi": "toi_daichou.csv", "okiba": "okiba_touroku.csv",
                    "jiku": "jiku_teigi.csv"}[which]
    rows = list(csv.reader(p.read_text(encoding="utf-8").splitlines()))
    rows = mutate(rows)
    with p.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(rows)
    return tmp_path


def _stop_code(d: Path) -> str:
    try:
        F.read_table(d / "toi_daichou.csv", F.TOI_COLS)
        F.load_okiba(F.read_table(d / "okiba_touroku.csv", F.OKIBA_COLS))
        F.load_jiku(F.read_table(d / "jiku_teigi.csv", F.JIKU_COLS))
    except F.Stop as e:
        return e.code
    return ""


崩し = [
    ("表が読めない", "toi", lambda r: [r[0][:-1]] + [x[:-1] for x in r[1:]]),
    ("表が読めない", "okiba", lambda r: r[:1]),
    ("軸が同じ", "jiku", lambda r: [r[0], ["出口と実装の状態", "出口と実装の状態", "合成の出典"]]),
    ("軸が同じ", "jiku", lambda r: r + [r[1]]),
    ("軸が同じ", "jiku", lambda r: [r[0], ["", r[1][1], r[1][2]]]),
    ("登録表の鍵が壊れている", "okiba", lambda r: [r[0]] + [["はい|はい|いいえ"] + r[1][1:]] + r[2:]),
    ("登録表の鍵が壊れている", "okiba", lambda r: [r[0]] + [["よそ|はい|いいえ|いいえ|いいえ|はい|はい"] + r[1][1:]] + r[2:]),
    ("登録表の鍵が壊れている", "okiba", lambda r: r + [r[1]]),
    ("登録表の欄が壊れている", "okiba", lambda r: [r[0]] + [[r[1][0], "⑨"] + r[1][2:]] + r[2:]),
    ("登録表の欄が壊れている", "okiba", lambda r: [r[0]] + [[r[1][0], r[1][1], ""] + r[1][3:]] + r[2:]),
    ("登録表の欄が壊れている", "okiba", lambda r: [r[0]] + [r[1][:5] + [""]] + r[2:]),
]


@pytest.mark.parametrize("want,which,mutate", 崩し)
def test_崩した表は1件も判定せずに止まる(tmp_path: Path, want: str, which: str, mutate) -> None:
    d = _broken(tmp_path, which, mutate)
    assert _stop_code(d) == want
    code, out = run(["check", str(d / "toi_daichou.csv"), str(d / "okiba_touroku.csv"),
                     str(d / "jiku_teigi.csv")])
    got = json.loads(out)
    assert code == 3 and got["ok"] is False and got["理由コード"] == want
    assert sum(got["8 値"].values()) == 0


def test_終了コード(tmp_path: Path) -> None:
    assert run(["check", str(TOI), str(OKIBA), str(JIKU)])[0] == 0
    assert run(["rows", str(TOI), str(OKIBA), str(JIKU)])[0] == 0
    assert run(["verify", str(TOI), str(OKIBA), str(JIKU)])[0] == 0
    assert run(["init", str(tmp_path)])[0] == 0
    assert (tmp_path / "toi_daichou.csv").exists()


# ---- 並べ直す ---------------------------------------------------------------------------

def test_問いごとに答えは1つだけ() -> None:
    toi, okiba, jiku = load()
    new = jiku["新軸の欄名"]
    for r in F.sort_rows(toi, okiba, jiku):
        assert bool(r[new]) != bool(r["別枠の理由"])


def test_8値と別枠の件数() -> None:
    toi, okiba, jiku = load()
    got = F.judge(toi, okiba, jiku)
    assert got["分母(問いの件数)"] == 20
    assert got["8 値"] == {P["①"]: 1, P["②"]: 2, P["③"]: 1, P["④"]: 2,
                           P["⑤"]: 2, P["⑥"]: 1, P["⑦"]: 2, P["⑧"]: 1}
    assert got["別枠"] == {"問い id の重複": 1, "出典が空": 1, "一覧 id が無い": 1,
                           "一覧の記載と違う": 1, "外し方の記号が登録外": 1, "宣言なしを含む": 1,
                           "組み合わせが登録外": 1, "要求する欄が空": 1}
    assert sum(got["8 値"].values()) == 12
    assert sum(got["別枠"].values()) == 8
    assert got["合計が合う"] is True


def test_別枠の理由8つすべてに道がある() -> None:
    toi, okiba, jiku = load()
    got = F.judge(toi, okiba, jiku)
    assert min(got["別枠"].values()) >= 1
    assert set(got["別枠"]) == set(F.ASIDE)


def test_旧軸の1列が新軸の7値に割れる() -> None:
    toi, okiba, jiku = load()
    old = jiku["旧軸の欄名"]
    uchi = F.judge(toi, okiba, jiku)[f"{old}ごとの内訳"]
    soto = uchi["外から渡す前提"]
    kettei = {k: v for k, v in soto.items() if not k.startswith("別枠")}
    assert sum(soto.values()) == 12
    assert sum(kettei.values()) == 8
    assert len(kettei) == 7
    assert P["①"] not in kettei
    assert sum(uchi["道具の中で済む"].values()) == 4
    assert sum(uchi["返るが一手残る"].values()) == 2
    assert sum(uchi["止まる"].values()) == 2


def test_新軸の1値は旧軸の2列から集まる() -> None:
    toi, okiba, jiku = load()
    old = jiku["旧軸の欄名"]
    uchi = F.judge(toi, okiba, jiku)[f"{old}ごとの内訳"]
    kara = sorted(k for k, v in uchi.items() if v.get(P["⑦"]))
    assert kara == ["外から渡す前提", "止まる"]


def test_外し方の記号ごとの件数() -> None:
    toi, okiba, jiku = load()
    got = F.judge(toi, okiba, jiku)
    assert got["原文の外し方の記号ごとの件数"] == {"A": 2, "C1": 3, "C2": 3, "C3": 4, "C4": 1,
                                                  "C5": 2, "C6": 2, "C7": 2, "C9": 1}
    assert sum(got["原文の外し方の記号ごとの件数"].values()) == 20
    assert got["原文の記号と登録表の記号が違う問い"] == 1


def test_どちらが正しいとも言わない() -> None:
    """原文の記号と登録表の記号が違っても、道具は両方を並べるだけで直さない。"""
    toi, okiba, jiku = load()
    r = next(x for x in F.sort_rows(toi, okiba, jiku) if x["問い id"] == "Q19")
    assert r["原文の外し方の記号"] == "C7"
    assert r["登録表の外し方の記号"] == "C1"
    assert "誤" not in json.dumps(r, ensure_ascii=False)


def test_しないことは消せない() -> None:
    toi, okiba, jiku = load()
    got = F.judge(toi, okiba, jiku)
    assert len(got["しないこと"]) == 13
    assert "分類の規則を持たない" in got["しないこと"]


# ---- 崩しにいく検算 ----------------------------------------------------------------------

def test_verifyが5つとも通る() -> None:
    toi, okiba, jiku = load()
    v = F.verify(toi, okiba, jiku)
    assert v["1 二度走りの sha256 が同じ"] is True
    assert v["2 3 表の行順を入れ替えても同じ"] is True
    assert v["3 件数の合計が合う"] is True
    assert v["4 行政一意の印を 1 件替えると登録表が指す先へ移る"]["登録表が指す先へ動く"] is True
    assert v["5 施行日確定の印を 1 件替えると ⑦ から ① へ移る"]["⑦ から ① へ移る"] is True
    assert v["ok"] is True
    assert v["sha256"][:12] == "8511a5d1648e"


def test_移り先は登録表が決める() -> None:
    """行政一意の印を 1 件替えたうえで、登録表の 1 行だけを差し替えると行き先が変わる。"""
    toi, okiba, jiku = load()
    four = F.verify(toi, okiba, jiku)["4 行政一意の印を 1 件替えると登録表が指す先へ移る"]
    assert four["替えた問い"] == "Q01"
    assert four["替える前"] == P["①"]
    assert four["登録表そのまま"] == P["③"]
    assert four["登録表の行だけ差し替え"] == P["⑧"]
    assert four["動いたのはこの問いだけ"] is True


def test_施行日の印1つで7と1が分かれる() -> None:
    toi, okiba, jiku = load()
    five = F.verify(toi, okiba, jiku)["5 施行日確定の印を 1 件替えると ⑦ から ① へ移る"]
    assert five["替えた問い"] == "Q09"
    assert five["替える前"] == P["⑦"]
    assert five["替えた後"] == P["①"]
    assert five["動いたのはこの問いだけ"] is True


def test_印を1つ替えるたびに動く問いの数() -> None:
    """7 つの印を 1 つずつ裏返して、動いた問いの数を数える(登録表は触らない)。"""
    toi, okiba, jiku = load()
    base = F._answers(toi, okiba, jiku)
    uniq = F._unique_ids(toi)
    moved: dict[str, int] = {}
    for col in F.MARK_COLS:
        n = 0
        for r in F._canon(toi):
            tid = r["問い id"]
            if tid not in uniq or r[col] not in ("はい", "いいえ"):
                continue
            to = "いいえ" if r[col] == "はい" else "はい"
            after = F._answers(F._swap_mark(toi, tid, col, to), okiba, jiku)
            if after[tid] != base[tid]:
                n += 1
        moved[col] = n
    assert moved == {"印_行政一意": 12, "印_主体内一意": 13, "印_履歴依存": 13,
                     "印_人が読む": 13, "印_起算日加算": 13, "印_施行日確定": 13,
                     "印_法が決める": 12}
    assert sum(moved.values()) == 89


def test_登録表を1行ずつ外すと別枠へしか動かない() -> None:
    """既定の置き場に化ける問いが 0 件であること(動いた先は別枠の 2 つの理由だけ)。"""
    toi, okiba, jiku = load()
    base = F._answers(toi, okiba, jiku)
    moved: dict[str, int] = {}
    for key in list(okiba):
        less = {k: v for k, v in okiba.items() if k != key}
        after = F._answers(toi, less, jiku)
        for tid in base:
            if after[tid] != base[tid]:
                assert after[tid].startswith("別枠 / ")
                moved[after[tid]] = moved.get(after[tid], 0) + 1
    assert moved == {"別枠 / 組み合わせが登録外": 14, "別枠 / 外し方の記号が登録外": 1}
    assert sum(moved.values()) == 15


def test_入力は読む前後で1文字も変わらない() -> None:
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(FX.glob("*.csv"))}
    toi, okiba, jiku = load()
    F.judge(toi, okiba, jiku)
    F.verify(toi, okiba, jiku)
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(FX.glob("*.csv"))}
    assert before == after and len(before) == 3


def test_時計も乱数も浮動小数も使わない() -> None:
    src = (ROOT / "fill_owner.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    mods = sorted({(n.names[0].name.split(".")[0] if isinstance(n, ast.Import)
                    else (n.module or "").split(".")[0])
                   for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))})
    assert mods == ["__future__", "argparse", "csv", "hashlib", "json", "pathlib", "sys"]
    for word in ("datetime", "time.", "random", "float(", "eval(", "exec(", "platform",
                 "subprocess", "requests", "urllib"):
        assert word not in src, word
    assert sum(isinstance(n, ast.Constant) and isinstance(n.value, float)
               for n in ast.walk(tree)) == 0


# ---- 記事に載せる出力 --------------------------------------------------------------------

def test_measure_narabenaoshi(capsys: pytest.CaptureFixture[str]) -> None:
    toi, okiba, jiku = load()
    got = F.judge(toi, okiba, jiku)
    v = F.verify(toi, okiba, jiku)
    old = jiku["旧軸の欄名"]
    uchi = got[f"{old}ごとの内訳"]
    soto = {k: x for k, x in uchi["外から渡す前提"].items() if not k.startswith("別枠")}
    with capsys.disabled():
        print(f"\n[measure] 問い 20 件 / 置き場の登録表 8 行 / 新軸の定義 1 行 → "
              f"8 値 {sum(got['8 値'].values())} + 別枠 {sum(got['別枠'].values())} = "
              f"{got['分母(問いの件数)']}")
        print(f"[measure] 8 値 = {json.dumps({k[0]: x for k, x in got['8 値'].items()}, ensure_ascii=False)}")
        print(f"[measure] 別枠 = {json.dumps(got['別枠'], ensure_ascii=False)}(8 つの理由に 1 件ずつ)")
        print(f"[measure] 旧軸「外から渡す前提」は 12 件。判定した 8 件が新軸の {len(soto)} 値に割れた "
              f"= {json.dumps({k[0]: x for k, x in soto.items()}, ensure_ascii=False)}。"
              f"① は 0 件(= 公的層の行で埋まるものは入っていなかった)")
        print(f"[measure] 旧軸の値ごとの件数 = "
              f"{json.dumps({k: sum(x.values()) for k, x in uchi.items()}, ensure_ascii=False)}"
              f"(合計 {sum(sum(x.values()) for x in uchi.values())} = 分母)")
        print(f"[measure] 新軸の ⑦ は旧軸の 2 列から集まる(外から渡す前提 1 + 止まる 1)。"
              f"旧軸と新軸は一対一でない")
        print(f"[measure] 原文の外し方の記号ごと = "
              f"{json.dumps(got['原文の外し方の記号ごとの件数'], ensure_ascii=False)}"
              f"(9 記号で 20 件。C9 は登録外)")
        print(f"[measure] 原文の記号と登録表の記号が違う問い {got['原文の記号と登録表の記号が違う問い']} 件"
              f"(両方を並べるだけで、どちらが正しいとも言わない)")
        print(f"[measure] 印を 1 つずつ裏返すと答えが動く問いは延べ 89 件(印 7 つ × 一意な問い 13 件。"
              f"行政一意 12 / 主体内一意 13 / 履歴依存 13 / 人が読む 13 / 起算日加算 13 / "
              f"施行日確定 13 / 法が決める 12)")
        print(f"[measure] 行政一意の印を Q01 で はい → いいえ: ① → ③。"
              f"登録表のその 1 行だけを差し替えると同じ印で ⑧ になる"
              f"(= 移り先を道具が決めていない)。動いた問いは 1 件")
        print(f"[measure] 施行日確定の印を Q09 で いいえ → はい: ⑦ → ①。動いた問いは 1 件"
              f"(= ⑦ と ① の分かれ目は印 1 つ)")
        print(f"[measure] 登録表を 1 行ずつ外すと、動いた延べ 15 件はすべて別枠"
              f"(組み合わせが登録外 14 / 外し方の記号が登録外 1)。"
              f"既定の置き場に化ける問いは 0 件")
        print(f"[measure] 崩した表 11 枚はすべて 1 件も判定せず、8 値は全て 0 で理由コードだけが返る")
        print(f"[measure] 理由コードは 12 個(表の側 4 + 問いごとの別枠 8)。すべてに道がある")
        print(f"[measure] 2 回 + 3 表の行順を逆順にして読み直し: 判定部分の sha256 は 3 回とも同じ"
              f"(先頭 12 桁 {v['sha256'][:12]})")
        print(f"[measure] 読む前後で入力 3 ファイルの sha256 が同じ(写しはメモリの中だけ)")
        print(f"[measure] import している module は 7 個で、datetime / random / float / eval / "
              f"exec / subprocess / urllib は 0 件")
    assert got["分母(問いの件数)"] == 20
    assert len(soto) == 7
    assert v["ok"] is True
