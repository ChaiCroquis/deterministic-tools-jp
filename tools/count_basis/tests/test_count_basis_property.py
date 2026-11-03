"""count_basis の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 読んだ範囲は 2 通りしかない。
  (a) 検証 1 件ごとに 7 値 + 別枠 4 種のどれか 1 つが付き、**11 値の合計 = 検証の数**、
      **7 値の合計 = 7 値が付いた検証の数**、**単位ごとの内訳の合計 = 検証の数**(値ごとの
      内訳の合計も一致)、**由来ごとの内訳の合計 = 元の行の台帳の行数**で、**別枠の検証には
      元の行も倍率も付かず**、**「分解できた」の検証は必ず 元の行数 × 倍率の積 = 宣言件数 かつ
      在り所に「1 行が持つ表の中に在る」を持たず**、**「倍率が 1 行の持つ表の中に在る」の検証は
      その在り所を必ず持ち**、**「他の検証と元の行を共有している」の検証は共有している数表 id を
      必ず 1 つ以上持ち**、**出力に「検証の総件数」の欄が無く**、判定部分に絶対パスが入らず、
      5 枚の行順を 3 通りに入れ替えても同じバイト列になる
  (b) 1 件も数えずに理由コードが返る(分けた検証や sha256 を取りに行くと例外)
どちらの場合も、この部品は 4 種 5 枚の表を 1 文字も書き換えない。

検証を 1〜4 件、宣言件数を 6 通り(整数 4 つ + 「通過」+ 小数)、単位記号を 4 通り(登録表に
在る 2 つ + 空欄 + 無い 1 つ)、指す数表を元の行の台帳 1〜3 枚の部分集合(ときどき台帳に無い
id)、確かめ方を 3 通り(次元の宣言を要求 / 件数と単位を要求 / 登録表に無い)、次元を 0〜2 本
(倍率 1〜3、在り所 3 通り)から引く。4 回に 1 回くらいどこか 1 か所を崩す(8 通りで、1 件も
数えずに止まる理由コード 8 個すべてに道が付く)。derandomize=True で毎回同じ入力列を使い、
database=None で例を保存しない。

**7 値 + 別枠の分け方はテストの側で別に実装している**(部品の judge / eleven を呼ばない)。
2 本目は「倍率の在り所だけが『分解できた』と『1 行が持つ表の中に在る』を分ける」ことを、
在り所 × 倍率 × 宣言件数 の総当たりで見る。
"""
from __future__ import annotations

import csv as _csv
import io
import sys
from pathlib import Path

import pytest
from hypothesis import event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import count_basis as H  # noqa: E402

STATUS = "合成の作業状況のメモ(架空)L1"
RANGE = "合成の収録範囲のメモ(架空)L1"
PLAN = "合成の次元のメモ(架空)L1"
WORD = "合成の登録のメモ(架空)L1"

CELL, ROW = "cell", "row"
UNREG_UNIT = "合成の未登録の単位記号"
M_CALC, M_PUBLIC, UNREG_METHOD = "M1", "M4", "合成の未登録の確かめ方"
MISSING_TABLE = "T99"

ARU, NAKA, HIROGETA = H.PLACES
JIZEN, JORYU, SHOGO = H.ORIGINS

UNITS_ROWS = [[CELL, H.UNIT_MEANINGS[0], WORD], [ROW, H.UNIT_MEANINGS[2], WORD]]
METHODS_ROWS = [[M_CALC, H.METHOD_MEANINGS[0], H.REQUIRES[0], WORD],
                [M_PUBLIC, H.METHOD_MEANINGS[3], H.REQUIRES[2], WORD]]
UNIT_SET = {CELL, ROW}
METHOD_SET = {M_CALC, M_PUBLIC}

COUNTS = ("0", "1", "12", "1,681", "通過", "1.251")
DIM_NAMES = ("年", "支部", "等級")

KOWASHIKATA = ("出典を空にする", "同じ検証 id を 2 行書く", "同じ数表 id を 2 行書く",
               "同じ検証 id と次元名の組を 2 行書く", "要求する欄を埋めない",
               "指している数表 id を空にする", "同じ数表を 2 度指す", "次元名を空にする")


def classify(checks: list[list[str]], bases: list[list[str]],
             dims: list[list[str]]) -> list[tuple[str, str]]:
    """検証ごとの (検証 id, 11 値) をテストの側で別に出す(部品を呼ばない)。"""
    rows = {b[0]: int(b[2]) for b in bases}
    mine: dict[str, list[tuple[int, str]]] = {}
    for d in dims:
        mine.setdefault(d[0], []).append((int(d[2]), d[3]))
    out: list[tuple[str, str]] = []
    earlier: list[set[str]] = []
    for row in sorted(checks, key=lambda r: r[0]):
        cid, raw, unit, tables, method, source = row
        ids = [t for t in tables.split(";") if t]
        bare = raw.replace(",", "")
        n = int(bare) if bare.isdigit() else None
        if not source:
            hit = H.KEKKA[7]
        elif method not in METHOD_SET:
            hit = H.KEKKA[8]
        elif unit and unit not in UNIT_SET:
            hit = H.KEKKA[8]
        elif not unit:
            hit = H.KEKKA[9] if n is not None else H.KEKKA[2]
        elif n is None:
            hit = H.KEKKA[10]
        elif any(t not in rows for t in ids):
            hit = H.KEKKA[6]
        elif cid not in mine:
            hit = H.KEKKA[3]
        else:
            product = sum(rows[t] for t in ids)
            for factor, _ in mine[cid]:
                product *= factor
            if any(place == NAKA for _, place in mine[cid]):
                hit = H.KEKKA[4]
            else:
                hit = H.KEKKA[0] if product == n else H.KEKKA[1]
        if hit in H.KASANARI_MOTO:
            if any(e & set(ids) for e in earlier):
                hit = H.KEKKA[5]
            earlier.append(set(ids))
        elif hit == H.KEKKA[5]:
            earlier.append(set(ids))
        out.append((cid, hit))
    return sorted(out)


@st.composite
def 合成の5枚(draw: st.DrawFn) -> dict[str, object]:
    """検証の台帳 / 元の行の台帳 / 次元の宣言表(と崩し方)を作る。登録表 2 枚は固定。"""
    n_b = draw(st.integers(1, 3))
    bases = [[f"T{k:02d}", f"合成の数表_{k}(架空)", str(draw(st.integers(0, 3))),
              draw(st.sampled_from((JIZEN, JORYU, SHOGO))), RANGE]
             for k in range(1, n_b + 1)]
    table_ids = [b[0] for b in bases]

    n_c = draw(st.integers(1, 4))
    checks: list[list[str]] = []
    dims: list[list[str]] = []
    for k in range(1, n_c + 1):
        cid = f"K{k:02d}"
        method = draw(st.sampled_from((M_CALC, M_CALC, M_PUBLIC, UNREG_METHOD)))
        pick = draw(st.lists(st.sampled_from(table_ids + [MISSING_TABLE]),
                             min_size=1, max_size=2, unique=True))
        count = draw(st.sampled_from(COUNTS))
        unit = draw(st.sampled_from((CELL, ROW, "", UNREG_UNIT)))
        if method == M_PUBLIC:      # 件数と単位を要求する確かめ方(欄を埋めておく)
            count = draw(st.sampled_from(COUNTS[:4]))
            unit = draw(st.sampled_from((CELL, ROW)))
        source = draw(st.sampled_from((STATUS, STATUS, STATUS, "")))
        checks.append([cid, count, unit, ";".join(pick), method, source])
        # 次元の宣言を要求する確かめ方の回には必ず 1 本以上宣言しておく
        least = 1 if method == M_CALC else 0
        for name in draw(st.lists(st.sampled_from(DIM_NAMES), min_size=least,
                                  max_size=2, unique=True)):
            dims.append([cid, name, str(draw(st.integers(1, 3))),
                         draw(st.sampled_from((ARU, NAKA, HIROGETA))), PLAN])
    # 台帳に無い検証 id を指す宣言(= 逆向きの欠け。止まらずに一覧へ出る)
    if draw(st.booleans()):
        dims.append(["K99", DIM_NAMES[0], "2", ARU, PLAN])

    kowasu = draw(st.sampled_from([None] * 24 + list(KOWASHIKATA)))
    if kowasu == KOWASHIKATA[0]:
        bases[0][4] = ""
    elif kowasu == KOWASHIKATA[1]:
        checks.append(["K01", "1", ROW, table_ids[0], M_PUBLIC, STATUS])
    elif kowasu == KOWASHIKATA[2]:
        bases.append(list(bases[0]))
    elif kowasu == KOWASHIKATA[3]:
        dims.extend([["K01", DIM_NAMES[0], "2", ARU, PLAN],
                     ["K01", DIM_NAMES[0], "3", ARU, PLAN]])
    elif kowasu == KOWASHIKATA[4]:
        checks.append([f"K{n_c + 1:02d}", "1", ROW, table_ids[0], M_CALC, STATUS])
    elif kowasu == KOWASHIKATA[5]:
        checks[0][3] = ""
    elif kowasu == KOWASHIKATA[6]:
        checks[0][3] = f"{table_ids[0]};{table_ids[0]}"
    elif kowasu == KOWASHIKATA[7]:
        dims.append(["K01", "", "2", ARU, PLAN])

    def csv(head: tuple[str, ...], body: list[list[str]]) -> str:
        buf = io.StringIO()
        _csv.writer(buf, lineterminator="\n").writerows([list(head)] + body)
        return buf.getvalue()

    return {"checks": csv(H.CHECK_COLUMNS, checks),
            "bases": csv(H.BASE_COLUMNS, bases),
            "dims": csv(H.DIM_COLUMNS, dims),
            "methods": csv(H.METHOD_COLUMNS, METHODS_ROWS),
            "units": csv(H.UNIT_COLUMNS, UNITS_ROWS),
            "checks_rows": checks, "bases_rows": bases, "dims_rows": dims,
            "kowasu": kowasu}


@settings(max_examples=200, derandomize=True, database=None, deadline=None)
@given(plan=合成の5枚())
def test_いつも成り立つこと_分けた検証か理由コードか(plan: dict[str, object]) -> None:
    checks = H.Checks.parse(plan["checks"])     # type: ignore[arg-type]
    bases = H.Bases.parse(plan["bases"])        # type: ignore[arg-type]
    dims = H.Dims.parse(plan["dims"])           # type: ignore[arg-type]
    methods = H.Methods.parse(plan["methods"])  # type: ignore[arg-type]
    units = H.Units.parse(plan["units"])        # type: ignore[arg-type]
    t = H.count_basis(checks, bases, dims, methods, units)

    expect_stop = plan["kowasu"] is not None
    c = t.counts()
    eleven = c["7 値 + 別枠"]
    assert c["検証の台帳の行数"] == len(plan["checks_rows"])   # type: ignore[arg-type]
    assert c["元の行の台帳の行数"] == len(plan["bases_rows"])  # type: ignore[arg-type]
    assert c["掛けた次元の宣言表の行数"] == len(plan["dims_rows"])  # type: ignore[arg-type]
    assert {j.result for j in t.judged} <= set(H.KEKKA)
    assert all(isinstance(v, int) for v in eleven.values())   # type: ignore[union-attr]
    # **出力に「検証の総件数」の欄が無い**(宣言件数を単位をまたいで足した値を持たない)
    for key in c:
        if "総件数" in key:
            assert key == "検証の総件数を出さない"

    if expect_stop:
        event("(b) 1 件も数えずに止まった")
        assert t.report.ok is False and t.report.pending
        assert {p.reason for p in t.report.pending} <= set(H.TABLE_REASONS)
        assert t.judged == ()
        assert eleven == {k: 0 for k in H.KEKKA}
        assert t.counted_denominator == 0 and t.aside_denominator() == 0
        assert t.shares() == [] and t.asides() == [] and t.mismatched() == []
        assert t.inside_only() == []
        for call in (t.judgement_bytes, t.sha256):
            with pytest.raises(RuntimeError):
                call()
    else:
        event("(a) 分けた")
        assert t.report.ok is True
        # 検証 1 件ごとに 11 値のどれか 1 つ。テスト側の別実装と一致する
        mine = sorted((j.check.check_id, j.result) for j in t.judged)
        assert mine == classify(plan["checks_rows"],   # type: ignore[arg-type]
                                plan["bases_rows"],    # type: ignore[arg-type]
                                plan["dims_rows"])     # type: ignore[arg-type]
        # 4 通りの数え方が全て合う
        assert sum(eleven.values()) == t.check_denominator()
        assert sum(eleven[k] for k in H.NANA) == t.counted_denominator
        unit_rows = t.by_unit()
        assert sum(int(r["検証の数"]) for r in unit_rows) == t.check_denominator()
        for k in H.KEKKA:
            assert sum(int(r["7 値 + 別枠"][k]) for r in unit_rows) == eleven[k]
        assert (sum(int(r["数表の枚数"]) for r in t.by_origin())
                == len(plan["bases_rows"]))   # type: ignore[arg-type]
        for j in t.judged:
            if not j.counted:       # 別枠には元の行も倍率も付かない
                assert j.base_rows == 0 and j.factors == () and j.product == 0
                assert j.shared == () and j.gap == ""
            if j.result == H.KEKKA[0]:      # 分解できた
                assert j.product == j.check.declared
                assert j.factors and not any(p == NAKA for _, _, p in j.factors)
                assert j.gap == "0"
            if j.result == H.KEKKA[1]:      # 分解が合わない(差の値だけを出す)
                assert j.product != j.check.declared and j.gap
                assert not any(p == NAKA for _, _, p in j.factors)
            if j.result == H.KEKKA[4]:      # 倍率が 1 行の持つ表の中に在る
                assert any(p == NAKA for _, _, p in j.factors)
            if j.result == H.KEKKA[5]:      # 重なりは共有している数表 id を必ず持つ
                assert j.shared and j.with_checks
                assert set(j.shared) <= set(j.check.tables)
            if j.result == H.KEKKA[3]:      # 次元の宣言が無い
                assert j.factors == () and dims.for_check(j.check.check_id) == ()
            if j.result == H.KEKKA[6]:      # 台帳に無い数表を指している
                assert j.missing and j.base_rows == 0
        body = t.judgement_bytes().decode("utf-8")
        for word in ("読んだ条件", "絶対パス", str(ROOT)):
            assert word not in body
        # 5 枚の行順を 3 通りに入れ替えても同じバイト列
        for how in H.SWAPS:
            again = H.count_basis(checks.swapped(how), bases.swapped(how),
                                  dims.swapped(how), methods.swapped(how),
                                  units.swapped(how))
            assert again.judgement_bytes() == t.judgement_bytes()
            assert again.sha256() == t.sha256()

    # どちらの場合も入力は 1 文字も書き換わらない
    assert H.Checks.parse(plan["checks"]).items == checks.items   # type: ignore[arg-type]
    assert H.Bases.parse(plan["bases"]).items == bases.items      # type: ignore[arg-type]
    assert H.Dims.parse(plan["dims"]).items == dims.items         # type: ignore[arg-type]


@settings(max_examples=300, derandomize=True, database=None)
@given(place=st.sampled_from(H.PLACES), factor=st.integers(1, 4),
       rows=st.integers(0, 3), count=st.sampled_from(("0", "1", "2", "4", "12")))
def test_在り所だけが分解できたと中に在るを分ける(place: str, factor: int, rows: int,
                                                  count: str) -> None:
    """在り所 × 倍率 × 元の行数 × 宣言件数 の総当たり。

    **倍率の在り所が「1 行が持つ表の中に在る」なら、積が宣言件数と合っていても
    「分解できた」には入らない**(行は増えていないので、積の一致だけで「厚い」と読ませない)。
    """
    checks = H.Checks.parse("\n".join([
        ",".join(H.CHECK_COLUMNS),
        f'K01,"{count}",{ROW},T01,{M_CALC},{STATUS}']))
    bases = H.Bases.parse("\n".join([
        ",".join(H.BASE_COLUMNS), f"T01,合成の数表_1(架空),{rows},{JIZEN},{RANGE}"]))
    dims = H.Dims.parse("\n".join([
        ",".join(H.DIM_COLUMNS), f"K01,年,{factor},{place},{PLAN}"]))
    t = H.count_basis(checks, bases, dims, H.Methods.parse("\n".join(
        [",".join(H.METHOD_COLUMNS)] + [",".join(r) for r in METHODS_ROWS])),
        H.Units.parse("\n".join(
            [",".join(H.UNIT_COLUMNS)] + [",".join(r) for r in UNITS_ROWS])))
    assert t.report.ok, [p.as_dict() for p in t.report.pending]
    j = t.judged[0]
    assert j.product == rows * factor
    if place == NAKA:
        assert j.result == H.KEKKA[4]
        assert len(t.inside_only()) == 1
    elif j.product == int(count):
        assert j.result == H.KEKKA[0] and j.gap == "0"
    else:
        assert j.result == H.KEKKA[1] and j.gap == str(int(count) - j.product)
    assert sum(t.eleven().values()) == 1 == t.check_denominator()
    assert t.counted_denominator + t.aside_denominator() == 1
