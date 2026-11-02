"""change_slot の試験。合成した 3 枚の表だけを使う(実在の料率・金額・機関名・人名は入れない)。

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
import change_slot as C  # noqa: E402
import make_fixtures as MF  # noqa: E402

KAITEI = FX / "kaitei_daichou.csv"
OKIBA = FX / "okiba_touroku.csv"
TAISHOU = FX / "taishou_touroku.csv"
P = C.PLACES


def load():
    return (C.read_table(KAITEI, C.KAITEI_COLS),
            C.load_okiba(C.read_table(OKIBA, C.OKIBA_COLS)),
            C.load_taishou(C.read_table(TAISHOU, C.TAISHOU_COLS)))


def run(args: list[str]) -> tuple[int, str]:
    r = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "change_slot.py")] + args,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout


# ---- 読む / 止まる ------------------------------------------------------------------------

def test_合成の3枚が読める() -> None:
    kaitei, okiba, taishou = load()
    assert len(kaitei) == 25
    assert len(okiba) == 11
    assert len(taishou) == 5


def test_理由コードは14個() -> None:
    assert len(C.TABLE_STOP) == 5
    assert len(C.ASIDE) == 9
    assert len(C.REASONS) == 14


def test_枠は9値_割り振りの表は6行() -> None:
    assert len(C.PLACE_MARKS) == 9
    assert len(C.PLACES) == 9
    assert len(C.FRAME_TABLE) == 6
    assert set(C.FRAME_TABLE) <= {(s, k) for s in C.SAYABLE for k in C.SLOTS}


def test_時期の欄の形は3つだけ() -> None:
    assert C.timing_form("2031-04") == "年月"
    assert C.timing_form("08-01") == "月日"
    assert C.timing_form("記載なし") == "記載なし"
    for bad in ("2031-4", "2031", "2031-04-01", "年度", "", "毎年 10 月頃", "２０３１-０４"):
        assert C.timing_form(bad) == ""


def _broken(tmp_path: Path, which: str, mutate) -> Path:
    """3 枚を写して 1 枚だけ崩す(入力そのものは触らない)。"""
    MF.write_all(tmp_path)
    p = tmp_path / {"kaitei": "kaitei_daichou.csv", "okiba": "okiba_touroku.csv",
                    "taishou": "taishou_touroku.csv"}[which]
    rows = mutate(list(csv.reader(p.read_text(encoding="utf-8").splitlines())))
    with p.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(rows)
    return tmp_path


def _stop_code(d: Path) -> str:
    try:
        C.read_table(d / "kaitei_daichou.csv", C.KAITEI_COLS)
        C.load_okiba(C.read_table(d / "okiba_touroku.csv", C.OKIBA_COLS))
        C.load_taishou(C.read_table(d / "taishou_touroku.csv", C.TAISHOU_COLS))
    except C.Stop as e:
        return e.code
    return ""


BROKEN_CASES = [
    ("表が読めない", "kaitei", lambda rows: [r[:-1] for r in rows]),
    ("表が読めない", "kaitei", lambda rows: rows[:1]),
    ("表が読めない", "okiba", lambda rows: [r[:-1] for r in rows]),
    ("表が読めない", "taishou", lambda rows: [r[:-1] for r in rows]),
    ("登録表の鍵が壊れている", "okiba", lambda rows: rows + [rows[1]]),
    ("登録表の鍵が壊れている", "okiba",
     lambda rows: rows[:1] + [["定例", "合成の登録外", "定例の枠", "時期の欄", "合成の出典"]] + rows[2:]),
    ("登録表の鍵が壊れている", "okiba",
     lambda rows: rows[:1] + [["定例", "言える", "合成の登録外", "時期の欄", "合成の出典"]] + rows[2:]),
    ("登録表の欄が壊れている", "okiba",
     lambda rows: rows[:1] + [["定例", "言える", "定例の枠", "", "合成の出典"]] + rows[2:]),
    ("枠の組み合わせが登録外", "okiba",
     lambda rows: rows[:1] + [["定例", "言える", "随時の枠", "時期の欄", "合成の出典"]] + rows[2:]),
    ("対象の登録表が壊れている", "taishou",
     lambda rows: rows[:1] + [["率", "合成の登録外", "その rule の行だけ", "合成の出典"]] + rows[2:]),
    ("対象の登録表が壊れている", "taishou", lambda rows: rows + [rows[1]]),
]


@pytest.mark.parametrize("want,which,mutate", BROKEN_CASES)
def test_崩した表は1件も割り振らずに止まる(tmp_path: Path, want: str, which: str, mutate) -> None:
    d = _broken(tmp_path, which, mutate)
    assert _stop_code(d) == want
    code, out = run(["check", str(d / "kaitei_daichou.csv"), str(d / "okiba_touroku.csv"),
                     str(d / "taishou_touroku.csv")])
    got = json.loads(out)
    assert code == 3
    assert got["ok"] is False and got["理由コード"] == want
    assert got["1 件も割り振らない"] is True
    assert sum(got["9 値"].values()) == 0


def test_終了コード(tmp_path: Path) -> None:
    code, _ = run(["check", str(KAITEI), str(OKIBA), str(TAISHOU)])
    assert code == 0
    code, _ = run(["check", str(tmp_path / "無い.csv"), str(OKIBA), str(TAISHOU)])
    assert code == 3


# ---- 割り振る ----------------------------------------------------------------------------

def test_ruleごとに答えは1つだけ() -> None:
    rows = C.slot_rows(*load())
    assert len(rows) == 25
    for r in rows:
        assert bool(r["枠"]) != bool(r["別枠の理由"])
        if r["別枠の理由"]:
            assert r["別枠の理由"] in C.ASIDE
        else:
            assert r["枠"] in P.values()
    assert len(rows[0]) == 15


def test_9値と別枠の件数() -> None:
    got = C.judge(*load())
    assert got["分母(rule の件数)"] == 25
    assert {k[0]: v for k, v in got["9 値"].items()} == {
        "①": 1, "②": 1, "③": 1, "④": 3, "⑤": 2, "⑥": 3, "⑦": 2, "⑧": 1, "⑨": 2}
    assert sum(got["9 値"].values()) == 16
    assert sum(got["別枠"].values()) == 9
    assert got["合計が合う"] is True


def test_別枠の理由9つすべてに道がある() -> None:
    got = C.judge(*load())
    assert got["別枠"] == {k: 1 for k in C.ASIDE}


def test_1つの種別が3つの枠に割れる() -> None:
    """定例の 1 種別が ①②③ に割れる(時期の形と地域の印の宣言だけで割れる)。"""
    got = C.judge(*load())
    teirei = got["種別ごとの内訳"]["定例"]
    枠 = {k[0]: v for k, v in teirei.items() if not k.startswith("別枠")}
    assert 枠 == {"①": 1, "②": 1, "③": 1}
    assert sum(teirei.values()) == 10


def test_1つの枠は複数の種別から集まる() -> None:
    """④ は 不定期 / 通達通知 / 経過措置 の 3 種別から、⑥ は 新設 / 廃止 / 期間限定 の 3 種別から。"""
    rows = C.slot_rows(*load())
    by_place: dict[str, set[str]] = {}
    for r in rows:
        if r["枠"]:
            by_place.setdefault(r["枠"][0], set()).add(r["種別"])
    assert by_place["④"] == {"不定期", "通達通知", "経過措置"}
    assert by_place["⑥"] == {"新設", "廃止", "期間限定"}
    assert by_place["⑤"] == {"済んだ改正"}
    assert len(by_place["④"]) == 3 and len(by_place["⑥"]) == 3


def test_直す場所ごとの件数() -> None:
    got = C.judge(*load())
    assert got["直す場所ごとの件数"] == {
        "式の実装": 3, "行の値": 6, "行の形": 1, "行の追加": 4, "行の閉じ": 2, "割り振らなかった": 9}
    assert sum(got["直す場所ごとの件数"].values()) == 25


def test_時期の形ごとの件数と一覧の行数が一致する() -> None:
    got = C.judge(*load())
    assert got["時期の形ごとの件数"] == {"年月": 14, "月日": 1, "記載なし": 9, "登録外": 1}
    assert got["一覧の行数"] == {"年月の一覧": 14, "月日の一覧": 1,
                                 "時期の記載なし": 9, "時期の形が登録外": 1}
    assert sum(got["一覧の行数"].values()) == 25


def test_年月と月日を同じ並びに混ぜない() -> None:
    grouped = C.lists(C.slot_rows(*load()))
    年月 = [r["時期の欄"] for r in grouped["年月の一覧"]]
    月日 = [r["時期の欄"] for r in grouped["月日の一覧"]]
    assert 年月 == sorted(年月)          # 文字列の昇順だけで並ぶ
    assert 月日 == sorted(月日)
    assert all(C.timing_form(x) == "年月" for x in 年月)
    assert all(C.timing_form(x) == "月日" for x in 月日)
    ids = [r["rule id"] for v in grouped.values() for r in v]
    assert len(ids) == 25
    assert not (set(r["rule id"] for r in grouped["年月の一覧"])
                & set(r["rule id"] for r in grouped["月日の一覧"]))


def test_記載の文字列から種別を当てない() -> None:
    """改定の記載を総入れ替えしても、rule ごとの答えは 1 件も動かない。"""
    kaitei, okiba, taishou = load()
    base = C._answers(kaitei, okiba, taishou)
    noise = ["不定期", "固定", "通達", "法定", "撤廃予定", "新設", "廃止", "毎年 8/1", "年度"]
    for i, word in enumerate(noise):
        swapped = [{**r, "改定の記載": word} for r in kaitei]
        assert C._answers(swapped, okiba, taishou) == base, word
    rotated = [{**r, "改定の記載": kaitei[(i + 1) % len(kaitei)]["改定の記載"]}
               for i, r in enumerate(kaitei)]
    assert C._answers(rotated, okiba, taishou) == base


def test_別枠の理由は手前が勝つ順で1つだけ付く() -> None:
    kaitei, okiba, taishou = load()
    # 出典が空(R24)に 地域の印の崩れを足しても、手前の「出典が空」が勝つ
    both = [({**r, "地域で発効日が違うか": "宣言なし"} if r["rule id"] == "R24" else dict(r))
            for r in kaitei]
    assert C._answers(both, okiba, taishou)["R24"] == "別枠 / 出典が空"
    # 要照合(R17)に 要求する欄の崩れを足しても、手前の「照合の印が要照合」が勝つ
    one = [({**r, "時期の欄": "記載なし"} if r["rule id"] == "R17" else dict(r)) for r in kaitei]
    assert C._answers(one, okiba, taishou)["R17"] == "別枠 / 照合の印が要照合"


def test_しないことは消せない() -> None:
    got = C.judge(*load())
    assert len(got["しないこと"]) == 14
    for key in ("種別を記載の文字列から推測しない", "今日を読まない", "日付を計算しない",
                "要照合を確定として扱わない", "値を引かない", "網羅と言わない",
                "枠を道具が決めない", "入力を書き換えない"):
        assert got["しないこと"][key]
    assert not any("割合" in k or "率" == k for k in got)   # 割合を返す鍵は無い


# ---- verify ------------------------------------------------------------------------------

def test_verifyが5つとも通る() -> None:
    v = C.verify(*load())
    assert v["1 二度走りの sha256 が同じ"] is True
    assert v["2 3 表の行順を入れ替えても同じ"] is True
    assert v["3 件数の合計が合う"] is True
    assert v["ok"] is True
    assert len(v["sha256"]) == 64


def test_移り先は登録表が決める() -> None:
    v = C.verify(*load())
    four = v["4 照合の印を 1 件替えると登録表が指す枠へ移る"]
    assert four["替えた rule"] == "R17"
    assert four["替える前"] == "別枠 / 照合の印が要照合"
    assert four["登録表そのまま"] == P["②"]
    assert four["登録表の種別行だけ差し替え"] == P["④"]
    assert four["動いたのはこの rule だけ"] is True
    assert four["合計は変わらない"] is True


def test_時期の欄を1つ埋めると年月の一覧が1行増える() -> None:
    v = C.verify(*load())
    five = v["5 時期の欄を記載なしから年月に替えると ② へ移る"]
    assert five["替えた rule"] == "R18"
    assert five["替える前"] == "別枠 / 定例の枠なのに時期が記載なし"
    assert five["替えた後"] == P["②"]
    assert five["年月の一覧"] == "14 行 → 15 行"
    assert five["動いたのはこの rule だけ"] is True


def test_登録表を1行ずつ外すと別枠へしか動かない() -> None:
    kaitei, okiba, taishou = load()
    base = C._answers(kaitei, okiba, taishou)
    moved, to_place = 0, 0
    reasons: dict[str, int] = {}
    for kind in list(okiba):
        thin = {k: v for k, v in okiba.items() if k != kind}
        after = C._answers(kaitei, thin, taishou)
        for rid in base:
            if after[rid] != base[rid]:
                moved += 1
                if after[rid].startswith("別枠"):
                    r = after[rid].split(" / ", 1)[1]
                    reasons[r] = reasons.get(r, 0) + 1
                else:
                    to_place += 1
    assert moved == 20
    assert to_place == 0
    assert reasons == {"種別記号が登録外": 20}


def test_対象の登録表を1行ずつ外すと別枠へしか動かない() -> None:
    kaitei, okiba, taishou = load()
    base = C._answers(kaitei, okiba, taishou)
    moved, to_place = 0, 0
    for key in list(taishou):
        thin = {k: v for k, v in taishou.items() if k != key}
        after = C._answers(kaitei, okiba, thin)
        for rid in base:
            if after[rid] != base[rid]:
                moved += 1
                if not after[rid].startswith("別枠"):
                    to_place += 1
    assert moved == 19
    assert to_place == 0


def test_入力は読む前後で1文字も変わらない() -> None:
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(FX.glob("*.csv"))}
    kaitei, okiba, taishou = load()
    C.judge(kaitei, okiba, taishou)
    C.verify(kaitei, okiba, taishou)
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(FX.glob("*.csv"))}
    assert before == after and len(before) == 3


def test_時計も乱数も浮動小数も使わない() -> None:
    src = (ROOT / "change_slot.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    mods = sorted({(n.names[0].name.split(".")[0] if isinstance(n, ast.Import)
                    else (n.module or "").split(".")[0])
                   for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))})
    assert mods == ["__future__", "argparse", "csv", "hashlib", "json", "pathlib", "sys"]
    for word in ("datetime", "time.", "random", "float(", "eval(", "exec(", "platform",
                 "subprocess", "requests", "urllib", "calendar", "locale"):
        assert word not in src, word
    assert sum(isinstance(n, ast.Constant) and isinstance(n.value, float)
               for n in ast.walk(tree)) == 0


# ---- 記事に載せる出力 --------------------------------------------------------------------

def test_measure_change_slot(capsys: pytest.CaptureFixture[str]) -> None:
    kaitei, okiba, taishou = load()
    got = C.judge(kaitei, okiba, taishou)
    v = C.verify(kaitei, okiba, taishou)
    four = v["4 照合の印を 1 件替えると登録表が指す枠へ移る"]
    five = v["5 時期の欄を記載なしから年月に替えると ② へ移る"]
    teirei = got["種別ごとの内訳"]["定例"]
    枠 = {k[0]: x for k, x in teirei.items() if not k.startswith("別枠")}
    with capsys.disabled():
        print(f"\n[measure] 改定の台帳 25 行 / 置き場の登録表 11 行 / 変わる対象の登録表 5 行 → "
              f"9 値 {sum(got['9 値'].values())} + 別枠 {sum(got['別枠'].values())} = "
              f"{got['分母(rule の件数)']}")
        print(f"[measure] 9 値 = {json.dumps({k[0]: x for k, x in got['9 値'].items()}, ensure_ascii=False)}")
        print(f"[measure] 別枠 = {json.dumps(got['別枠'], ensure_ascii=False)}"
              f"(9 つの理由に 1 件ずつ)")
        print(f"[measure] 種別「定例」の 10 件は 3 つの枠に割れた = "
              f"{json.dumps(枠, ensure_ascii=False)}(残り 7 件は別枠の 7 理由に 1 件ずつ)")
        print(f"[measure] 逆に 1 つの枠は複数の種別から集まる: ④ は 不定期 / 通達通知 / 経過措置 の "
              f"3 種別、⑥ は 新設 / 廃止 / 期間限定 の 3 種別。種別と枠は一対一でない")
        print(f"[measure] 時期の形ごと = "
              f"{json.dumps(got['時期の形ごとの件数'], ensure_ascii=False)}"
              f" → 一覧の行数 {json.dumps(got['一覧の行数'], ensure_ascii=False)}"
              f"(年月と月日は別の表で、合計 {sum(got['一覧の行数'].values())} = 分母)")
        print(f"[measure] 直す場所ごと = "
              f"{json.dumps(got['直す場所ごとの件数'], ensure_ascii=False)}"
              f"(率だけ動く行 6 / 表の形が動く行 1 / 式が動く行 3 / 行の追加 4 / 行の閉じ 2)")
        print(f"[measure] 改定の記載を 9 通りの語に総入れ替えしても、rule ごとの答えは 0 件動かない"
              f"(= 記載の文字列から種別を当てる経路が無い)")
        print(f"[measure] 照合の印を R17 で 要照合 → 照合済: 別枠 → ②。登録表の「定例」行だけを "
              f"{four['差し替えた先']} に差し替えると同じ印で ④ になる"
              f"(= 移り先を道具が決めていない)。動いた rule は 1 件")
        print(f"[measure] 時期の欄を R18 で 記載なし → 台帳に在る年月: 別枠 → ②、"
              f"年月の一覧が {five['年月の一覧']}。動いた rule は 1 件"
              f"(日付は作らず、台帳に在る年月を借りている)")
        print(f"[measure] 置き場の登録表を 1 行ずつ外すと、動いた延べ 20 件はすべて別枠"
              f"(種別記号が登録外 20。先に別の理由で別枠に居る 4 件は動かない)。既定の枠に化ける rule は 0 件")
        print(f"[measure] 変わる対象の登録表を 1 行ずつ外すと、動いた延べ 19 件はすべて別枠。"
              f"既定の直す場所に化ける rule は 0 件")
        print(f"[measure] 崩した表 11 枚はすべて 1 件も割り振らず、9 値は全て 0 で理由コードだけが返る")
        print(f"[measure] 理由コードは 14 個(表の側 5 + rule ごとの別枠 9)。すべてに道がある")
        print(f"[measure] 2 回 + 3 表の行順を逆順にして読み直し: 判定部分の sha256 は 3 回とも同じ"
              f"(先頭 12 桁 {v['sha256'][:12]})")
        print(f"[measure] 読む前後で入力 3 ファイルの sha256 が同じ(写しはメモリの中だけ)")
        print(f"[measure] import している module は 7 個で、datetime / calendar / random / float / "
              f"eval / exec / subprocess / urllib は 0 件")
    assert got["分母(rule の件数)"] == 25
    assert sum(got["9 値"].values()) == 16
    assert len(枠) == 3
    assert v["ok"] is True
