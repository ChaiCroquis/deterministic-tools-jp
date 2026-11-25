"""label_fold のテスト。記事に載せた数は test_measure_* が assert で固定する。"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
import label_fold as L  # noqa: E402


def load(d: str):
    return (L.read_table(FX / d / "names.csv", L.NAME_COLS), L.read_table(FX / d / "steps.csv", L.STEP_COLS),
            L.read_table(FX / d / "pairs.csv", L.PAIR_COLS))


def counts(r: dict) -> list[int]:
    return [r["区分ごとの件数"][c] for c in L.CATS]


def of(r: dict, cat: str) -> list[str]:
    return [p["対id"] for p in r["対ごと"] if p["区分"] == cat]


def test_measure_shuuroku_categories() -> None:
    r = L.fold_pairs(*load("shuuroku"))
    assert counts(r) == [4, 1, 12, 1]
    assert r["対の登録表の行数"] == 18
    assert r["文書ごとの名前の数"] == {"例の右": 1, "例の左": 1, "収録範囲の記録": 17, "短い版": 16}
    assert of(r, L.CAT_A) == ["p09", "p10", "p11", "p16"]
    assert of(r, L.CAT_B) == ["p01"]
    assert of(r, L.CAT_D) == ["p17"]
    assert [s["件数"] for s in r["Bを同じになった段ごとに"]] == [0, 0, 1]
    assert r["別枠_対"] == [] and r["別枠_手順"] == [] and r["印_対に無いが畳むと同じ組"] == []


def test_measure_shuuroku_marks_and_example() -> None:
    r = L.fold_pairs(*load("shuuroku"))
    inside = [p["対id"] for p in r["対ごと"] if p["印_片側がもう片側に含まれる"]]
    assert inside == ["p04", "p06", "p08", "p13"]
    ex = r["対ごと"][-1]
    assert (ex["区分"], ex["段ごとの左"][-1], ex["段ごとの右"][-1]) == (L.CAT_C, "支給限度額上限額", "支給上限額")


@pytest.mark.parametrize("drop, want", [(L.S_NFKC, [4, 1, 12, 1]), (L.S_SPACE, [4, 0, 13, 1]),
                                        (L.S_SYMBOL, [4, 0, 13, 1])])
def test_measure_shuuroku_drop_one_step(drop: str, want: list[int]) -> None:
    n, s, p = load("shuuroku")
    assert counts(L.fold_pairs(n, [x for x in s if x["手順の種類"] != drop], p)) == want


def test_measure_shuuroku_empty_and_swapped_steps() -> None:
    n, s, p = load("shuuroku")
    assert counts(L.fold_pairs(n, [], p)) == [4, 0, 13, 1]
    order = {"1": "1", "2": "3", "3": "2"}                       # 空白と記号の順番を入れ替える
    r = L.fold_pairs(n, [{**x, "順番": order[x["順番"]]} for x in s], p)
    assert counts(r) == [4, 1, 12, 1]
    assert [x["同じになった段"]["種類"] for x in r["対ごと"] if x["区分"] == L.CAT_B] == [L.S_SPACE]


def test_measure_third_document() -> None:
    a, b = L.fold_pairs(*load("hojo_mijikai")), L.fold_pairs(*load("hojo_nagai"))
    assert counts(a) == [0, 1, 4, 0] and of(a, L.CAT_B) == ["q1"]
    assert counts(b) == [1, 0, 4, 0] and of(b, L.CAT_A) == ["q4"]


def test_measure_gousei() -> None:
    r = L.fold_pairs(*load("gousei"))
    assert counts(r) == [1, 7, 3, 2]
    assert r["対の登録表の行数"] == 13
    assert [s["件数"] for s in r["Bを同じになった段ごとに"]] == [2, 1, 3, 1]
    assert [p["対id"] for p in r["対ごと"] if p["印_片側がもう片側に含まれる"]] == ["g09", "g11"]
    assert r["印_対に無いが畳むと同じ組"] == [["a90", "b13"]]


def test_measure_kowashita_six_reasons() -> None:
    r = L.fold_pairs(*load("kowashita"))
    assert counts(r) == [1, 0, 0, 0]
    assert [b["理由"] for b in r["別枠_対"]] == [L.B_SOURCE, L.B_DUP, L.B_TWICE, L.B_TWICE, L.B_SAMEDOC, L.B_NAME]
    assert [b["理由"] for b in r["別枠_手順"]] == [L.B_STEP]
    assert {b["理由"] for b in r["別枠_対"] + r["別枠_手順"]} == set(L.BETSU)


@pytest.mark.parametrize("d", ["shuuroku", "hojo_mijikai", "hojo_nagai", "gousei", "kowashita"])
def test_verify_five(d: str) -> None:
    v = L.verify(*load(d))
    assert len(v) == 5 and all(v.values())


def one(left: str, right: str, steps: list[dict[str, str]]) -> dict:
    names = [{"名前id": "l", "文書id": "甲", "名前": left, "切り方のメモ": "", "出典": "x"},
             {"名前id": "r", "文書id": "乙", "名前": right, "切り方のメモ": "", "出典": "x"}]
    pairs = [{"対id": "p", "左の名前id": "l", "右の名前id": "r", "読みのメモ": "", "出典": "x"}]
    return L.fold_pairs(names, steps, pairs)["対ごと"][0]


def step(n: str, kind: str, symbols: str = "") -> dict[str, str]:
    return {"順番": n, "手順の種類": kind, "除く記号": symbols, "出典": "x"}


def test_both_empty_after_removal_is_not_same() -> None:
    assert one("・", "_", [step("1", L.S_SYMBOL, "・_")])["区分"] == L.CAT_C


def test_spaces_in_name_are_kept_as_written(tmp_path: Path) -> None:
    f = tmp_path / "n.csv"
    f.write_text("名前id,文書id,名前,切り方のメモ,出典\na,甲, 棚 ,,x\n", encoding="utf-8")
    assert L.read_table(f, L.NAME_COLS)[0]["名前"] == " 棚 "
    assert one(" 棚", "棚", [])["区分"] == L.CAT_C


@pytest.mark.parametrize("bad", [[step("a", L.S_NFKC)], [step("1", L.S_NFKC), step("1", L.S_SPACE)],
                                 [step("1", L.S_SYMBOL)], [step("1", L.S_SPACE, "_")]])
def test_unreadable_steps_stop(bad: list[dict[str, str]]) -> None:
    with pytest.raises(L.LabelFoldError):
        one("甲", "乙", bad)


def test_missing_column_stops(tmp_path: Path) -> None:
    f = tmp_path / "n.csv"
    f.write_text("名前id,名前\na,棚\n", encoding="utf-8")
    with pytest.raises(L.LabelFoldError):
        L.read_table(f, L.NAME_COLS)
    assert L.main(["--names", str(f), "--steps", str(f), "--pairs", str(f)]) == 2


def test_cli_exit_codes(tmp_path: Path, capfdbinary) -> None:
    def args(d: str) -> list[str]:
        return [x for k in ("names", "steps", "pairs") for x in (f"--{k}", str(FX / d / f"{k}.csv"))]
    assert L.main(args("shuuroku") + ["--verify"]) == 3
    out = capfdbinary.readouterr().out.decode("utf-8")
    assert out.count("合う") == 5 and "合わない" not in out
    assert L.main(args("gousei") + ["--json"]) == 3


def test_no_similarity_or_guess_argument() -> None:
    assert list(inspect.signature(L.fold_pairs).parameters) == ["names", "steps", "pairs"]
    src = (ROOT / "label_fold.py").read_text(encoding="utf-8")
    assert "difflib" not in src and "urllib" not in src and "socket" not in src
    assert len(L.NOT_HELD) == 8
