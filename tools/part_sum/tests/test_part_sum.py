"""part_sum のテスト。記事に載せた数は test_measure_* が `assert 変数 == 値` で固定している。"""
from __future__ import annotations

import hashlib
import inspect
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
import part_sum as P  # noqa: E402


def load(name: str) -> dict:
    d = FX / name
    return P.tally(P.read_table(d / "totals.csv", P.TOTAL_COLS),
                   P.read_table(d / "parts.csv", P.PART_COLS),
                   P.read_table(d / "kinds.csv", P.KIND_COLS))


def run_cli(name: str, *extra: str) -> subprocess.CompletedProcess:
    d = FX / name
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(ROOT / "part_sum.py"), "--totals", str(d / "totals.csv"),
         "--parts", str(d / "parts.csv"), "--kinds", str(d / "kinds.csv"), *extra],
        capture_output=True)


# ---- 測定: 私の収録範囲のメモから写した登録表 ----------------------------------

def test_measure_shuuroku_sums_and_diffs() -> None:
    r = load("shuuroku")
    assert len(r["総数ごと"]) == 1
    t = r["総数ごと"][0]
    assert r["内訳の台帳の行数"] == 36
    assert t["総数の宣言"] == 1681
    assert t["入れるの項目数"] == 30
    assert t["入れないの項目数"] == 1
    assert t["数の付いていない項目数"] == 5
    assert t["足した数_入れるだけ"] == 1632
    assert t["足した数_入れないも"] == 1648
    assert t["差_入れるだけ"] == 49
    assert t["差_入れないも"] == 33
    assert t["区分_入れるだけ"] == P.CAT_C
    assert t["区分_入れないも"] == P.CAT_C
    assert sum(r["別枠の件数"].values()) == 0


def test_measure_shuuroku_by_source_line() -> None:
    t = load("shuuroku")["総数ごと"][0]
    rows = {b["出典"].split("L")[-1]: b for b in t["出典の行ごとの小計"]}
    assert list(rows) == ["64", "65", "66", "70"]
    assert [rows[k]["入れるの項目数"] for k in rows] == [10, 5, 8, 7]
    assert [rows[k]["入れるの小計"] for k in rows] == [346, 78, 53, 1155]
    assert [rows[k]["入れないの項目数"] for k in rows] == [0, 1, 0, 0]
    assert [rows[k]["入れないの小計"] for k in rows] == [0, 16, 0, 0]
    assert [rows[k]["数の付いていない項目数"] for k in rows] == [0, 5, 0, 0]
    assert [rows[k]["単位の字が違う項目数"] for k in rows] == [0, 0, 0, 1]


def test_measure_shuuroku_names_and_marks() -> None:
    r = load("shuuroku")
    t = r["総数ごと"][0]
    assert [u["項目の名前"] for u in t["数の付いていない項目"]] == [
        "介護休業 3 種", "育児休業 67%/50%/賃金月額 上下", "出生時育休", "出生後休業支援", "育児時短 2 種"]
    assert [(u["項目の名前"], u["数"], u["単位"]) for u in t["印_単位の字が総数と違う"]] == [("労災保険率", 55, "業種")]
    assert len(t["印_同じ項目の名前が2回"]) == 5
    assert r["読みの種類ごとの項目数"] == {"そのまま写した": 30, "掛けて読んだ": 1, "記載なし": 5}
    # 一番大きい 1 項目と、それを除いた残り(どちらも足した数の内側の話で、差の説明ではない)
    biggest = 1079
    assert t["足した数_入れるだけ"] - biggest == 553
    assert t["入れるの項目数"] - 1 == 29


# ---- 測定: 合成(架空の備品の一覧)--------------------------------------------

def test_measure_gousei_four_categories() -> None:
    r = load("gousei")
    ts = r["総数ごと"]
    assert r["内訳の台帳の行数"] == 14
    assert [t["総数の宣言"] for t in ts] == [120, 200, 300, 60]
    assert [t["足した数_入れるだけ"] for t in ts] == [120, 195, 190, 70]
    assert [t["足した数_入れないも"] for t in ts] == [120, 195, 214, 70]
    assert [t["差_入れるだけ"] for t in ts] == [0, 5, 110, -10]
    assert [t["差_入れないも"] for t in ts] == [0, 5, 86, -10]
    assert [t["区分_入れるだけ"] for t in ts] == [P.CAT_A, P.CAT_B, P.CAT_C, P.CAT_D]
    assert [t["数の付いていない項目数"] for t in ts] == [0, 0, 2, 1]
    assert list(r["区分ごとの件数_入れるだけ"].values()) == [1, 1, 1, 1]
    assert r["読みの種類ごとの項目数"] == {"そのまま写した": 10, "掛けて読んだ": 1, "記載なし": 3}
    assert sum(len(t["印_単位の字が総数と違う"]) for t in ts) == 1
    assert sum(len(t["印_同じ項目の名前が2回"]) for t in ts) == 1


def test_measure_kowashita_six_reasons() -> None:
    r = load("kowashita")
    assert r["内訳の台帳の行数"] == 9
    assert len(r["別枠"]) == 8
    assert r["別枠の件数"] == {P.B_KIND: 1, P.B_TOTAL: 1, P.B_SOURCE: 1, P.B_DUP: 2, P.B_INT: 1, P.B_MISMATCH: 2}
    assert len(P.BETSU) == 6
    # 別枠の行はどの和にも入らない(足されたのは k01 の 40 だけ)
    assert [t["足した数_入れないも"] for t in r["総数ごと"]] == [40, 0, 0, 0]


def test_measure_not_held_lines_cannot_be_removed() -> None:
    assert len(P.NOT_HELD) == 6
    out = run_cli("gousei").stdout.decode("utf-8")
    assert out.count("経路は持たない") == 6
    flags = [a for a in inspect.signature(P.render).parameters]
    assert flags == ["result"]


# ---- 持たない経路 ---------------------------------------------------------------

def test_no_multiplication() -> None:
    for s in ("各 4", "4×4", "4*4", "4 種", "16.0", "１６", "-3", "1,07", "", " 16"):
        assert P.parse_int(s) is None
    assert P.parse_int("16") == 16
    assert P.parse_int("1,079") == 1079
    assert P.parse_int("1079") == 1079


def test_unnumbered_names_do_not_move_sums() -> None:
    d = FX / "shuuroku"
    totals = P.read_table(d / "totals.csv", P.TOTAL_COLS)
    parts = P.read_table(d / "parts.csv", P.PART_COLS)
    kinds = P.read_table(d / "kinds.csv", P.KIND_COLS)
    base = P.tally(totals, parts, kinds)["総数ごと"][0]
    fewer = [p for p in parts if p["読みの種類"] != "記載なし"]
    t = P.tally(totals, fewer, kinds)["総数ごと"][0]
    assert (t["足した数_入れるだけ"], t["足した数_入れないも"]) == (base["足した数_入れるだけ"], base["足した数_入れないも"])
    assert (t["差_入れるだけ"], t["差_入れないも"]) == (base["差_入れるだけ"], base["差_入れないも"])
    assert t["区分_入れるだけ"] == P.CAT_B  # 数の付いていない項目を消すと区分だけが替わる


def test_output_has_no_verdict_or_ratio_keys() -> None:
    text = json.dumps(load("shuuroku"), ensure_ascii=False)
    for word in ("正しい", "原因", "割合", "率\":", "割り振"):
        assert word not in text.replace("持たない", "").split("持たせていないもの")[0]


def test_order_is_table_order() -> None:
    d = FX / "gousei"
    totals = P.read_table(d / "totals.csv", P.TOTAL_COLS)
    parts = P.read_table(d / "parts.csv", P.PART_COLS)
    kinds = P.read_table(d / "kinds.csv", P.KIND_COLS)
    a = P.tally(totals, parts, kinds)
    b = P.tally(totals, list(reversed(parts)), kinds)
    assert [t["総数id"] for t in b["総数ごと"]] == ["G1", "G2", "G3", "G4"]
    for x, y in zip(a["総数ごと"], b["総数ごと"]):
        assert x["足した数_入れるだけ"] == y["足した数_入れるだけ"]
        assert x["足した数_入れないも"] == y["足した数_入れないも"]
    assert [u["項目id"] for u in b["総数ごと"][2]["数の付いていない項目"]] == ["g305", "g304"]


# ---- 止まる(1 件も足さない)----------------------------------------------------

KINDS = [{"読みの種類": "そのまま写した", "足す側": "入れる"}]
TOTAL = [{"総数id": "T", "数": "10", "単位": "点", "出典": "合成 L1"}]


@pytest.mark.parametrize("totals, kinds, word", [
    ([{**TOTAL[0], "数": "十"}], KINDS, "整数でない"),
    ([{**TOTAL[0], "出典": ""}], KINDS, "出典が空"),
    ([TOTAL[0], TOTAL[0]], KINDS, "2 回"),
    ([{**TOTAL[0], "総数id": ""}], KINDS, "総数id が空"),
    (TOTAL, [{"読みの種類": "そのまま写した", "足す側": "たぶん"}], "登録の 3 つに無い"),
    (TOTAL, KINDS + KINDS, "2 回"),
    (TOTAL, [{"読みの種類": "", "足す側": "入れる"}], "種類の字が空"),
])
def test_stops_on_broken_registry(totals: list, kinds: list, word: str) -> None:
    with pytest.raises(P.PartSumError, match=word):
        P.tally(totals, [], kinds)


def test_stops_on_missing_column(tmp_path: Path) -> None:
    p = tmp_path / "parts.csv"
    p.write_text("項目id,総数id,項目の名前,数\n", encoding="utf-8")
    with pytest.raises(P.PartSumError, match="必要な列が無い"):
        P.read_table(p, P.PART_COLS)


# ---- CLI ------------------------------------------------------------------------

def test_cli_exit_codes_and_inputs_unchanged(tmp_path: Path) -> None:
    files = sorted(FX.rglob("*.csv"))
    before = [hashlib.sha256(f.read_bytes()).hexdigest() for f in files]
    assert run_cli("shuuroku").returncode == 3
    assert run_cli("gousei").returncode == 3
    assert run_cli("kowashita").returncode == 3
    j = run_cli("shuuroku", "--json")
    assert json.loads(j.stdout.decode("utf-8"))["総数ごと"][0]["足した数_入れるだけ"] == 1632
    assert run_cli("shuuroku").stdout == run_cli("shuuroku").stdout
    assert [hashlib.sha256(f.read_bytes()).hexdigest() for f in files] == before

    # 区分 A だけの表は 0
    (tmp_path / "totals.csv").write_text("総数id,数,単位,出典\nG1,120,点,合成 L3\n", encoding="utf-8")
    src = (FX / "gousei" / "parts.csv").read_text(encoding="utf-8").splitlines()
    (tmp_path / "parts.csv").write_text("\n".join(src[:4]) + "\n", encoding="utf-8")
    (tmp_path / "kinds.csv").write_bytes((FX / "gousei" / "kinds.csv").read_bytes())
    base = [sys.executable, "-X", "utf8", str(ROOT / "part_sum.py"), "--totals", str(tmp_path / "totals.csv"),
            "--parts", str(tmp_path / "parts.csv"), "--kinds", str(tmp_path / "kinds.csv")]
    assert subprocess.run(base, capture_output=True).returncode == 0
    # 読めない表は 2
    (tmp_path / "kinds.csv").write_text("読みの種類\nそのまま写した\n", encoding="utf-8")
    bad = subprocess.run(base, capture_output=True)
    assert bad.returncode == 2 and bad.stdout == b""


def test_fixtures_match_generator() -> None:
    sys.path.insert(0, str(FX))
    import make_fixtures as M
    assert len(M.SHUUROKU_PARTS) == 36 and len(M.GOUSEI_PARTS) == 14 and len(M.KOWASHITA_PARTS) == 9
    got = P.read_table(FX / "shuuroku" / "parts.csv", P.PART_COLS)
    assert [[g[c] for c in P.PART_COLS] for g in got] == M.SHUUROKU_PARTS
