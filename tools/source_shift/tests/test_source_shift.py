"""source_shift の試験。合成した 5 枚の表(fixtures/*_a.csv)に対する測定は等号で固定する。

記事に載せた数はここの assert が固定している。値が変われば記事も変える。
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
import source_shift as SS  # noqa: E402

PATHS = [str(FX / f"{n}_a.csv") for n in ("moves", "sources", "roles", "checks", "current")]


@pytest.fixture()
def t() -> dict:
    return SS.load(PATHS)


def cats(res: dict) -> dict[str, str]:
    return {r["rule"]: r["区分"] for r in res["rule ごとの行"]}


# ---------- 測定(記事に載せる数) ----------

def test_measure_10_rules_split(t):
    res = SS.judge(t)
    got = [res["区分"][c] for c in SS.CATEGORIES]
    assert len(t["moves"]) == 15 and len(t["sources"]) == 4 and len(t["roles"]) == 4
    assert len(t["checks"]) == 3 and len(t["current"]) == 10
    assert res["分母(rule の件数)"] == 10
    assert got == [2, 2, 2, 2]
    assert res[SS.SIDE] == 2
    assert sum(got) + res[SS.SIDE] == 10
    assert res["件数の検算"] == "区分 4 値 + 別枠の合計 10 / rule の件数 10"
    print(f"\n[measure] 動き 15 行 / 出どころ 4 行 / 役の記号 4 行 / 突合 3 行 / いまの由来 10 行 → "
          f"区分 (A) {got[0]} / (B) {got[1]} / (C) {got[2]} / (D) {got[3]}、別枠 {res[SS.SIDE]}、合計 10")


def test_measure_each_rule(t):
    c = cats(SS.judge(t))
    assert [k for k, v in c.items() if v == SS.CAT_A] == ["K01", "K02"]
    assert [k for k, v in c.items() if v == SS.CAT_B] == ["K03", "K08"]
    assert [k for k, v in c.items() if v == SS.CAT_C] == ["K04", "K05"]
    assert [k for k, v in c.items() if v == SS.CAT_D] == ["K06", "K07"]
    assert [k for k, v in c.items() if v == SS.SIDE] == ["K09", "K10"]
    rows = {r["rule"]: r for r in SS.judge(t)["rule ごとの行"]}
    assert rows["K09"]["止まった理由"] == [SS.R_CHAIN]
    assert rows["K10"]["止まった理由"] == [SS.R_ROLE]
    assert rows["K05"]["最後に動いた順の番号"] == "動きなし"
    assert rows["K08"]["動きの回数(台帳の行数)"] == 3 and rows["K08"]["うち主が替わった回数"] == 2
    assert rows["K08"]["突合の記載が無い入れ替え"] == ["M11"]
    print("\n[measure] (A) K01・K02 / (B) K03・K08 / (C) K04・K05 / (D) K06・K07 / 別枠 K09(線がつながらない)・"
          "K10(古い側の役が空)。K08 は動き 3 行のうち主の入れ替えが 2 回で、突合が無いのは M11")


def test_measure_checks_side_by_side(t):
    moves = {r["動き"]: r for r in SS.judge(t)["動きごとの行"]}
    assert len(moves) == 11          # 別枠の 2 rule の 4 行は歩かない
    c1 = moves["M05"]["引き継ぎの突合"][0]
    c2 = moves["M06"]["引き継ぎの突合"][0]
    c3 = moves["M10"]["引き継ぎの突合"][0]
    assert (c1["比べた件数"], c1["一致した件数"], c1["範囲"]) == (47, 47, "範囲が違う")
    assert (c2["比べた件数"], c2["一致した件数"], c2["範囲"]) == (120, 118, "同じ文字列")
    assert (c3["比べた件数"], c3["一致した件数"], c3["範囲"]) == (30, 30, "同じ文字列")
    assert moves["M07"]["引き継ぎの突合"] == "突合の記載なし"
    assert moves["M07"]["日付"] == "日付の記載なし" and moves["M07"]["動かした主体"] == "記載なし"
    assert moves["M01"]["前"] == "無かった" and moves["M01"]["古い側の役"] == "古い側なし"
    text = json.dumps(SS.judge(t), ensure_ascii=False)
    assert "率" not in text.replace("直近 1 期の率", "").replace("一致率を出さない", "")
    print("\n[measure] 歩いた動きは 11 行(別枠の 2 rule の 4 行は歩かない)。突合 3 件は "
          "比べた 47・一致 47(範囲が違う)/ 比べた 120・一致 118(同じ文字列)/ 比べた 30・一致 30(同じ文字列)。"
          "割った値はどこにも出ない")


def test_measure_gap_between_walk_and_current(t):
    res = SS.judge(t)
    gaps = res["歩いた最後の主といまの由来の台帳が食い違う rule"]
    assert gaps == [{"rule": "K08", "歩いた最後の主": "S1", "いまの由来の台帳の主": "S2"}]
    assert res["ok"] is False
    print("\n[measure] 歩いた最後の主といまの由来の台帳が食い違う rule は 1 件(K08 = 歩くと S1、台帳は S2)。"
          "どちらが正しいかは出ない")


def test_measure_verify_five_things(t):
    v = SS.verify(t)
    assert v["ok"] is True
    assert list(v["verify"].values()) == [True, True, True, True, True]
    assert v["突合を外した写しの枚数"] == 2
    assert v["動きを足した写しの枚数"] == 3
    assert v["判定部分の sha256"][:12] == "e42a4c1774c5"
    print(f"\n[measure] verify 5 つとも合う。突合を外した写し 2 枚、動きを足した写し 3 枚。"
          f"判定部分の sha256 の先頭は {v['判定部分の sha256'][:12]}")


def test_measure_modules_and_no_float():
    tree = ast.parse((ROOT / "source_shift.py").read_text(encoding="utf-8"))
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module != "__future__":
            mods.add(n.module.split(".")[0])
    assert sorted(mods) == ["argparse", "csv", "hashlib", "json", "pathlib", "sys"]
    assert len(mods) == 6
    banned = {"time", "datetime", "random", "socket", "urllib", "subprocess", "http", "secrets", "os"}
    assert len(mods & banned) == 0
    floats = [n for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, float)]
    divs = [n for n in ast.walk(tree) if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Div, ast.FloorDiv, ast.Mod))]
    assert len(floats) == 0 and len(divs) == 0
    print("\n[measure] 部品が import している module は 6 個で、時刻・乱数・通信・subprocess の module は 0 個。"
          "float の定数と割り算は 0 件")


def test_check_on_first_placement_does_not_count_as_handover(t):
    """最初に置いた動き(前が無い)に付いた突合は写すだけで、区分にも verify の写しにも数えない。

    手元の記録を写した台帳を通したときに verify が合わなかった形を、合成の表で固定したもの。
    """
    x = copy.deepcopy(t)
    x["checks"].append({"check_id": "C0", "move_id": "M01", "scope": "配布元の見本", "compared": "250",
                        "matched": "250", "source": "合成の検証のメモ(架空)L0"})
    res = SS.judge(x)
    assert cats(res) == cats(SS.judge(t))
    [m01] = [r for r in res["動きごとの行"] if r["動き"] == "M01"]
    assert m01["引き継ぎの突合"][0]["比べた件数"] == 250 and m01["引き継ぎの突合"][0]["範囲"] == "範囲が違う"
    v = SS.verify(x)
    assert v["ok"] is True and v["突合を外した写しの枚数"] == 2


# ---------- 別枠の 6 つの理由 ----------

def _break(t: dict, table: str, key: str, ident: str, col: str, value: str) -> dict:
    x = copy.deepcopy(t)
    [row] = [r for r in x[table] if r[key] == ident]
    row[col] = value
    return x


BREAKS = [
    (SS.R_SOURCE, ("moves", "move_id", "M05", "source", ""), "K01"),
    (SS.R_SOURCE, ("checks", "check_id", "C1", "source", ""), "K01"),
    (SS.R_SOURCE, ("current", "rule", "K04", "source", ""), "K04"),
    (SS.R_UNREGISTERED, ("moves", "move_id", "M05", "to_source", "S9"), "K01"),
    (SS.R_UNREGISTERED, ("moves", "move_id", "M05", "old_role", "予備"), "K01"),
    (SS.R_UNREGISTERED, ("current", "rule", "K07", "current_source", "S9"), "K07"),
    (SS.R_SEQ, ("moves", "move_id", "M05", "seq", "五"), "K01"),
    (SS.R_SEQ, ("moves", "move_id", "M05", "seq", "5.0"), "K01"),
    (SS.R_CHAIN, ("moves", "move_id", "M05", "from_source", "S3"), "K01"),
    (SS.R_ROLE, ("moves", "move_id", "M05", "old_role", ""), "K01"),
    (SS.R_COUNT, ("checks", "check_id", "C1", "matched", "48"), "K01"),
    (SS.R_COUNT, ("checks", "check_id", "C1", "compared", "-1"), "K01"),
    (SS.R_COUNT, ("checks", "check_id", "C1", "matched", "四十七"), "K01"),
]


@pytest.mark.parametrize("reason,brk,rule", BREAKS)
def test_six_reasons_put_only_that_rule_aside(t, reason, brk, rule):
    base = {r["rule"]: r for r in SS.judge(t)["rule ごとの行"]}
    res = SS.judge(_break(t, *brk))
    rows = {r["rule"]: r for r in res["rule ごとの行"]}
    assert rows[rule]["区分"] == SS.SIDE
    assert reason in rows[rule]["止まった理由"]
    assert all(rows[k] == base[k] for k in base if k != rule)      # 他の rule は 1 つも動かない
    assert sum(res["区分"].values()) + res[SS.SIDE] == 10


def test_measure_six_reasons_all_have_a_path():
    assert len(SS.REASONS) == 6
    assert {b[0] for b in BREAKS} == set(SS.REASONS)
    assert len(BREAKS) == 13
    print("\n[measure] 別枠の理由コードは 6 個で、6 個すべてに崩した表で道がある(崩し方は 13 通り)。"
          "崩した rule だけが別枠へ移り、ほかの rule の行は 1 つも変わらない")


def test_duplicate_seq_puts_both_rules_aside(t):
    res = SS.judge(_break(t, "moves", "move_id", "M06", "seq", "05"))   # 5 と 05 は同じ整数
    c = cats(res)
    assert c["K01"] == SS.SIDE and c["K02"] == SS.SIDE
    assert c["K03"] == SS.CAT_B


def test_registry_row_without_citation_touches_only_users(t):
    res = SS.judge(_break(t, "sources", "source_id", "S4", "source", ""))
    c = cats(res)
    assert c["K07"] == SS.SIDE and c["K01"] == SS.CAT_A


# ---------- 区分の境目 ----------

def test_dropping_a_check_moves_only_that_rule_from_a_to_b(t):
    x = copy.deepcopy(t)
    x["checks"] = [c for c in x["checks"] if c["check_id"] != "C2"]
    before, after = cats(SS.judge(t)), cats(SS.judge(x))
    assert before["K02"] == SS.CAT_A and after["K02"] == SS.CAT_B
    assert {k: v for k, v in after.items() if k != "K02"} == {k: v for k, v in before.items() if k != "K02"}


def test_unmatched_counts_do_not_change_category(t):
    """一致した件数が少なくても (A) のまま。道具は突合が在るかだけを見て、合ったかどうかで分けない。"""
    res = SS.judge(_break(t, "checks", "check_id", "C2", "matched", "0"))
    assert cats(res)["K02"] == SS.CAT_A


def test_c_and_d_depend_on_registry_only(t):
    x = copy.deepcopy(t)
    [s3] = [s for s in x["sources"] if s["source_id"] == "S3"]
    s3["covers"] = "K09"                      # K05 の相手を登録表から外す
    assert cats(SS.judge(x))["K05"] == SS.CAT_D
    y = copy.deepcopy(t)
    [s3] = [s for s in y["sources"] if s["source_id"] == "S3"]
    s3["covers"] = "K05;K07;K09"              # K07 に相手を足す
    assert cats(SS.judge(y))["K07"] == SS.CAT_C


def test_rule_missing_from_current_is_listed(t):
    x = copy.deepcopy(t)
    x["current"] = [c for c in x["current"] if c["rule"] != "K01"]
    res = SS.judge(x)
    assert {"rule": "K01", "歩いた最後の主": "S2", "いまの由来の台帳の主": "いまの由来の記載なし"} \
        in res["歩いた最後の主といまの由来の台帳が食い違う rule"]


def test_loose_check_is_listed_not_dropped(t):
    x = copy.deepcopy(t)
    x["checks"].append({"check_id": "C9", "move_id": "M99", "scope": "全項目", "compared": "1",
                        "matched": "1", "source": "合成の検証のメモ(架空)L9"})
    res = SS.judge(x)
    assert [r["突合"] for r in res["動きに結び付かない突合"]] == ["C9"]
    assert cats(res) == cats(SS.judge(t))


# ---------- 決定論と入力の不変 ----------

def test_row_order_of_every_table_does_not_matter(t):
    base = SS.judge(t)["判定部分の sha256"]
    for name in t:
        x = copy.deepcopy(t)
        x[name] = x[name][::-1]
        assert SS.judge(x)["判定部分の sha256"] == base


def test_inputs_are_never_rewritten(t):
    before = {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in PATHS}
    snapshot = copy.deepcopy(t)
    SS.judge(t)
    SS.verify(t)
    assert t == snapshot
    assert before == {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in PATHS}


def test_not_held_list_is_always_returned(t):
    res = SS.judge(t)
    assert res["持たせていないもの"] == list(SS.NOT_HELD) and len(SS.NOT_HELD) == 8


# ---------- 表として読めないとき ----------

def test_missing_column_is_refused(tmp_path):
    p = tmp_path / "moves.csv"
    p.write_text("move_id,seq\nM01,1\n", encoding="utf-8")
    with pytest.raises(SS.ShiftError):
        SS.read_table(str(p), SS.MOVE_COLS)


def test_duplicate_id_is_refused(t):
    x = copy.deepcopy(t)
    x["moves"].append(dict(x["moves"][0]))
    with pytest.raises(SS.ShiftError):
        SS.judge(x)


# ---------- CLI ----------

def test_cli_exit_codes(tmp_path, capsys):
    assert SS.main(["check", *PATHS]) == 3            # 別枠 2 件と食い違い 1 件が在る
    assert SS.main(["verify", *PATHS]) == 0
    assert SS.main(["rows", *PATHS]) == 3
    assert SS.main(["check", str(tmp_path / "無い.csv"), *PATHS[1:]]) == 2
    capsys.readouterr()
    assert SS.main(["init", str(tmp_path / "ひな型")]) == 0
    made = sorted(p.name for p in (tmp_path / "ひな型").iterdir())
    assert made == ["checks.csv", "current.csv", "moves.csv", "roles.csv", "sources.csv"]
    assert SS.main(["init", str(tmp_path / "ひな型")]) == 2      # 既に在るひな型には書かない


def test_cli_clean_tables_exit_zero(t, tmp_path, capsys):
    import csv
    keep = {"K01", "K02", "K03", "K04", "K05", "K06", "K07"}
    x = copy.deepcopy(t)
    x["moves"] = [m for m in x["moves"] if m["rule"] in keep]
    x["current"] = [c for c in x["current"] if c["rule"] in keep]
    x["checks"] = [c for c in x["checks"] if c["check_id"] != "C3"]
    paths = []
    for name, cols, _ in SS.TABLES:
        p = tmp_path / f"{name}.csv"
        with open(p, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(x[name])
        paths.append(str(p))
    assert SS.main(["check", *paths]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True and out[SS.SIDE] == 0
