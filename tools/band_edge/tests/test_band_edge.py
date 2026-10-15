"""band_edge のテスト。合成 fixture は `fixtures/` に commit 済(実データ・実在の金額は入れない)。

test_measure_* が記事に載せた数値の出どころで、assert で固定している(値が変われば記事も変える前提)。
測っているものは 5 つある。

  (1) 宣言された等号で値が帯に 1 つ当たり、境界値ちょうどに触れた行が別に数えられる側(obi_a)
  (2) 上限の等号を 1 欄だけ 以下 にすると、境界値ちょうどの行だけが
      「決まらない(重なり)」に変わる側(obi_ten)= この記事の骨
  (3) さらに下限の等号を 超 にすると、同じ境界値が隣の帯へ 1 つ動く側(obi_chou)
  (4) 宣言された換算(時間 → 分)だけが働き、宣言の無い単位では止まる側
  (5) 「当たる帯が無い」と「決まらない(重なり)」と「止まった」が混ざらない側

(1) の帯の当たり外れは、テストの側でも宣言された等号から直に比べて確かめている
(部品の holds は呼ばない)。
"""
from __future__ import annotations

import ast
import hashlib
import re
import sys
from decimal import Decimal
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIX = ROOT / "fixtures"
PLAN = ROOT.parent.parent          # 07_記事化商品化計画(出典の行を開くため)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FIX))
import band_edge as B  # noqa: E402
import make_fixtures as M  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの -> その行に在るはずの語
REAL_SOURCES = {
    M.SRC_JUNI: "順位の列に書く",
    M.SRC_MARUME: "隣の列に書かせる",
    M.SRC_KITEI: "既定そのものを持たない",
    M.SRC_ANBUN: "按分も日割りも無い",
}


def values(name: str) -> B.Values:
    return B.Values.load(FIX / f"{name}.csv")


def bands(name: str) -> B.Bands:
    return B.Bands.load(FIX / f"{name}.csv")


def units(name: str = "tani_a") -> B.Units:
    return B.Units.load(FIX / f"{name}.csv")


def kowashita(name: str) -> Path:
    return FIX / "kowashita" / f"{name}.csv"


def path_of(name: str) -> Path:
    return kowashita(name[2:]) if name.startswith("K:") else FIX / f"{name}.csv"


def pull(a: str = "atai_a", o: str = "obi_a", t: str = "tani_a") -> B.Match:
    return B.match(B.Values.load(path_of(a)), B.Bands.load(path_of(o)),
                   B.Units.load(path_of(t)))


def hit_of(m: B.Match, value: str) -> B.Hit:
    return next(h for h in m.hits if h.value.value == Decimal(value))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def every_fixture() -> list[Path]:
    return sorted(p for p in FIX.rglob("*.csv"))


def expect_bands(value: Decimal, rows: list[list[str]], item: str) -> list[int]:
    """当たる帯を、宣言された等号から直に比べて出す(部品の holds は呼ばない)。"""
    out: list[int] = []
    for r in rows[1:]:
        if r[0] != item:
            continue
        ok = True
        if r[2] != B.OPEN:
            ok = ok and (value >= Decimal(r[2]) if r[3] == "以上" else value > Decimal(r[2]))
        if r[4] != B.OPEN:
            ok = ok and (value < Decimal(r[4]) if r[5] == "未満" else value <= Decimal(r[4]))
        if ok:
            out.append(int(r[1]))
    return sorted(out)


# ---------------------------------------------------------------- 入り口

def test_committed_tables_load() -> None:
    """commit 済の表は、表として読める(止まる理由が 0 件)。"""
    assert len(values("atai_a").items) == 13
    assert len(bands("obi_a").items) == 8 and bands("obi_a").swap == "逆順"
    assert len(units().items) == 3
    for name in ("obi_a", "obi_ten", "obi_chou", "obi_koumoku_nashi"):
        assert bands(name).pending == (), name
    for name in ("atai_a", "atai_kansan"):
        assert values(name).pending == (), name


def test_sources_point_at_real_lines() -> None:
    """出典のうち 4 件は、この repo 内の実在の行を指している。"""
    for src, word in REAL_SOURCES.items():
        rel, lineno = src.rsplit(" L", 1)
        line = (PLAN / rel).read_text(encoding="utf-8").splitlines()[int(lineno) - 1]
        assert word in line, f"{src} に {word} が無い: {line[:60]}"


def test_registered_vocabularies() -> None:
    """登録の語彙は固定(下限の等号 2 / 上限の等号 2 / 値の種類 6 / 4 値 4 / 理由コード 13)。"""
    assert B.LOW_EQS == ("以上", "超")
    assert B.HIGH_EQS == ("未満", "以下")
    assert B.OPEN == "開いている"
    assert len(B.KINDS) == 6 and len(B.INTEGER_KINDS) == 4
    assert len(B.RESULTS) == 4
    assert len(B.STOP_REASONS) == 13
    assert B.SUBCOMMANDS == ("match", "check", "verify", "init")


def test_empty_is_not_open() -> None:
    """空欄は「開いている」ではない(空欄を無限と読み替えない)。"""
    stopped = B.Bands.load(kowashita("obi_kaihou_kuuran"))
    assert "開放の宣言が無い空欄" in {p.reason for p in stopped.pending}
    assert "開放の宣言が無い空欄" not in {p.reason for p in bands("obi_a").pending}


# ---------------------------------------------------------------- (1) 当たる側

def test_measure_declared_equalities_pick_one_band() -> None:
    """宣言された等号で 13 行のうち 12 行が 1 つの帯に決まり、1 行は当たる帯が無い。"""
    m = pull()
    c = m.counts()
    assert m.report.ok
    assert c["値の表の行数"] == 13 and c["帯の表の行数"] == 8 and c["項目の数"] == 3
    assert c["4 値"] == {"帯が 1 つに決まった": 12, "当たる帯が無い": 1,
                         "決まらない(重なり)": 0, "止まった": 0}
    assert c["点の重なり"] == 0
    assert hit_of(m, "7201").result == "当たる帯が無い"
    assert hit_of(m, "7201").bands == ()
    print(f"[measure] atai_a / obi_a / tani_a: 値 13 行 / 帯 8 行 / 3 項目 → "
          f"4 値 {c['4 値']}")


def test_measure_edge_counts_are_separate() -> None:
    """境界値ちょうどに触れた行は 8 件。下限ちょうど 7 / 上限ちょうど 7 / 両方 6。"""
    m = pull()
    c = m.counts()
    assert c["境界ちょうど"] == {"下限ちょうど": 7, "上限ちょうど": 7, "両方に触れた": 6}
    assert len(m.edges()) == 8
    assert hit_of(m, "0").low_edge == (1,) and hit_of(m, "0").high_edge == ()
    assert hit_of(m, "7200").low_edge == () and hit_of(m, "7200").high_edge == (3,)
    assert hit_of(m, "100000").low_edge == (2,) and hit_of(m, "100000").high_edge == (1,)
    print("[measure] 境界ちょうどに触れた行 8 / 13(下限ちょうど 7 / 上限ちょうど 7 / "
          "両方 6)。当たった率は単独では返らない")


def test_hits_match_an_independent_reading_of_the_equalities() -> None:
    """当たった帯は、テスト側で等号から直に比べた結果と一致する(部品の holds は呼ばない)。"""
    for name in ("obi_a", "obi_ten", "obi_chou"):
        rows = {"obi_a": M.OBI_A, "obi_ten": M.OBI_TEN, "obi_chou": M.OBI_CHOU}[name]
        m = pull(o=name)
        for h in m.hits:
            u = units().of(h.value.item)
            assert u is not None and h.used is not None
            assert list(h.bands) == expect_bands(h.used, rows, h.value.item), (name, h)


# ---------------------------------------------------------------- (2) 点の重なり

def test_measure_one_equality_cell_makes_the_edge_undecidable() -> None:
    """上限の等号を 1 欄だけ 以下 にすると、境界値ちょうどの 1 行だけが決まらなくなる。"""
    base, ten = pull(), pull(o="obi_ten")
    assert ten.report.ok                     # 点の重なりは止めない(この回の主題)
    c = ten.counts()
    assert c["4 値"] == {"帯が 1 つに決まった": 11, "当たる帯が無い": 1,
                         "決まらない(重なり)": 1, "止まった": 0}
    assert c["点の重なり"] == 1
    assert hit_of(base, "100000").result == "帯が 1 つに決まった"
    assert hit_of(base, "100000").bands == (2,)
    assert hit_of(ten, "100000").result == "決まらない(重なり)"
    assert hit_of(ten, "100000").bands == (1, 2)
    assert hit_of(ten, "100000").returns == ""      # 2 つのうち片方を選んで返さない
    # 変わったのはこの 1 行だけで、ほかの 12 行の結果は同じ
    other = {h.value.number: h.result for h in base.hits if h.value.value != Decimal("100000")}
    assert {h.value.number: h.result
            for h in ten.hits if h.value.value != Decimal("100000")} == other
    print("[measure] 上限の等号を 未満 → 以下 に 1 欄: 100000 が 帯が 1 つに決まった(帯 2)"
          " → 決まらない(重なり)(帯 1 と 2)。ほかの 12 行は不変")


def test_measure_changing_the_lower_equality_moves_the_edge_value() -> None:
    """下限の等号を 超 にすると、同じ境界値が隣の帯へ 1 つ動く(返すものが変わる)。"""
    base, chou = pull(), pull(o="obi_chou")
    assert chou.report.ok and chou.counts()["点の重なり"] == 0
    assert chou.counts()["4 値"] == {"帯が 1 つに決まった": 12, "当たる帯が無い": 1,
                                     "決まらない(重なり)": 0, "止まった": 0}
    assert hit_of(base, "100000").returns == "合成の段2(架空)"
    assert hit_of(chou, "100000").returns == "合成の段1(架空)"
    assert hit_of(base, "99999").returns == hit_of(chou, "99999").returns
    assert hit_of(base, "150000").returns == hit_of(chou, "150000").returns
    print("[measure] 下限の等号を 以上 → 超 に 1 欄: 100000 の返すものが 合成の段2 → 合成の段1。"
          "99999 と 150000 の返すものは変わらない")


def test_measure_three_tables_three_fingerprints() -> None:
    """同じ値の表でも、等号の 1 欄が違えば判定部分の指紋が変わる。"""
    got = {name: pull(o=name).sha256()[:12] for name in ("obi_a", "obi_ten", "obi_chou")}
    assert got == {"obi_a": "2097451c8e1d", "obi_ten": "f0a2c33595f6",
                   "obi_chou": "05c77b9e0bfb"}
    print(f"[measure] 判定部分の sha256 先頭 12 桁 obi_a {got['obi_a']} / "
          f"obi_ten {got['obi_ten']} / obi_chou {got['obi_chou']}")


# ---------------------------------------------------------------- (3) 覆いの検算

def test_measure_cover_is_checked_before_any_value() -> None:
    """項目ごとに、帯の連結の幅と帯ごとの個数の合計が一致する(値を 1 つも見る前に検算)。"""
    m = pull()
    got = {c.item: (str(c.width), str(c.counted), c.closed) for c in m.covers}
    assert got == {"合成の月額(架空)": ("100000", "100000", 1),
                   "合成の日数(架空)": ("180", "180", 1),
                   "合成の時間(架空)": ("6001", "6001", 2)}
    assert all(c.ok for c in m.covers)
    print(f"[measure] 覆いの検算(幅 / 帯ごとの個数の合計): {got}")


def test_measure_gap_and_range_overlap_stop() -> None:
    """隙間と範囲の重なりは止まる。点の重なりだけは止めずに 4 値で返す。"""
    gap = pull(o="K:obi_sukima")
    over = pull(o="K:obi_kasanari")
    assert {p.reason for p in gap.report.pending} == {"帯の隙間"}
    assert {p.reason for p in over.report.pending} == {"帯の重なり"}
    for m in (gap, over):
        assert not m.report.ok
        # 止まったのは崩した項目だけで、ほかの項目の行は巻き込まれない
        stopped = {h.value.item for h in m.hits if h.result == "止まった"}
        assert stopped == {"合成の月額(架空)"}
        assert len([h for h in m.hits if h.result == "止まった"]) == 5
    assert pull(o="obi_ten").report.ok
    print("[measure] 下限を 1 つずらした表 → 帯の隙間 で止まる / 下限を下げた表 → "
          "帯の重なり で止まる / 点の重なりは止めずに 決まらない(重なり)で返す")


def test_cover_check_catches_a_swapped_implementation(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """帯の個数の数え方を 1 つずらした実装に差し替えると、覆いの検算が自分で見つけて止まる。"""
    real = B.band_steps
    monkeypatch.setattr(B, "band_steps", lambda b, step: real(b, step) + 1)
    m = pull()
    assert not m.report.ok
    assert {p.reason for p in m.report.pending} == {"覆いの検算が合わない"}
    with pytest.raises(RuntimeError):
        m.sha256()


# ---------------------------------------------------------------- (4) 換算

def test_measure_declared_conversion_only() -> None:
    """宣言された換算(時間 → 分)だけが働き、宣言の無い単位(秒)では止まる。"""
    m = pull()
    assert m.counts()["換算した値の行数"] == 1
    h = hit_of(m, "20")
    assert h.used == Decimal("1200") and h.converted == "時間 → 分"
    assert h.returns == "合成の中(架空)"
    assert h.returns == hit_of(m, "1200").returns     # 換算しても同じ帯に入る
    byou = pull(a="K:atai_kansan_mi")
    assert {p.reason for p in byou.report.pending} == {"単位の宣言が無いか換算が未宣言"}
    print("[measure] 20 時間 → 1200 分 に換算して 合成の中(架空)に当たる。"
          "宣言の無い 秒 の行は 単位の宣言が無いか換算が未宣言 で止まる")


def test_conversion_never_rounds() -> None:
    """換算しても丸めない。宣言された小数の桁に収まらない値は表として読めないで返す。"""
    with pytest.raises(B.ReadError):
        pull(a="K:atai_kansan_hasuu")
    with pytest.raises(B.ReadError):
        B.Units.load(kowashita("tani_seisuu_shousuu"))


# ---------------------------------------------------------------- (5) 混ぜない

def test_measure_no_band_is_not_a_stop() -> None:
    """当たる帯が無いことは止まることではない(理由コードは 1 件も出ない)。"""
    m = pull()
    assert m.report.ok and m.report.pending == ()
    assert m.counts()["4 値"]["当たる帯が無い"] == 1
    assert m.counts()["4 値"]["止まった"] == 0
    nashi = pull(o="obi_koumoku_nashi")
    assert {p.reason for p in nashi.report.pending} == {"該当項目の帯が 0 件"}
    assert not nashi.report.ok
    print("[measure] 7201 は 当たる帯が無い で件数に残り、理由コードは 0 件。"
          "帯そのものが 0 件の項目は 該当項目の帯が 0 件 で止まる")


def test_no_snapping_arguments() -> None:
    """最寄りの帯に寄せる引数も、丸めの引数も、等号を総当たりする引数も無い。"""
    src = (ROOT / "band_edge.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "add_argument":
            for a in node.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    names.add(a.value)
    assert names == {"values", "bands", "units", "dest"}
    for word in ("quantize", "ROUND_", "round(", "nearest", "clamp", "itertools"):
        assert word not in src, word


def test_all_thirteen_stop_reasons_are_covered(monkeypatch: pytest.MonkeyPatch) -> None:
    """止まる理由コード 13 個すべてに道がある(崩した表 12 枚 + 差し替えた実装 2 本)。"""
    seen: set[str] = set()
    for o in ("K:obi_toukou_kuuran", "K:obi_kaihou_kuuran", "K:obi_kasanari", "K:obi_sukima",
              "K:obi_shutten_nashi", "K:obi_gyakusa", "K:obi_bangou_juufuku",
              "K:obi_koumoku_mitouroku", "obi_koumoku_nashi"):
        seen |= {p.reason for p in pull(o=o).report.pending}
    for a in ("K:atai_shurui_kuuran", "K:atai_shutten_nashi", "K:atai_kansan_mi"):
        seen |= {p.reason for p in pull(a=a).report.pending}
    assert len(seen) == 10
    # 覆いの検算が合わない(帯の個数の数え方を差し替える)
    real_steps = B.band_steps
    monkeypatch.setattr(B, "band_steps", lambda b, step: real_steps(b, step) + 1)
    seen |= {p.reason for p in pull().report.pending}
    monkeypatch.setattr(B, "band_steps", real_steps)
    # 2 回目の判定部分が不一致 / 行順を入れ替えた表で出力が変わる(毎回違うバイト列を返す)
    out = B.verify(values("atai_a"), bands("obi_a"), units())
    assert out["ok"] is True
    real_bytes, box = B.Match.judgement_bytes, {"n": 0}

    def drifting(self: B.Match) -> bytes:
        box["n"] += 1
        return real_bytes(self) + str(box["n"]).encode("utf-8")

    monkeypatch.setattr(B.Match, "judgement_bytes", drifting)
    bad = B.verify(values("atai_a"), bands("obi_a"), units())
    seen |= {p["reason"] for p in bad["pending"]}           # type: ignore[index,union-attr]
    assert seen == set(B.STOP_REASONS), sorted(set(B.STOP_REASONS) - seen)
    print(f"[measure] 止まる理由コード {len(B.STOP_REASONS)} 個すべてに道がある"
          "(崩した表 12 枚 + 差し替えた実装 2 本)")


def test_measure_read_error_count() -> None:
    """「表として読めない」で返す崩した表は 23 枚(理由コードには混ぜない)。"""
    n = 0
    for p in sorted((FIX / "kowashita").glob("*.csv")):
        loader = (B.Bands.load if p.name.startswith("obi") else
                  B.Values.load if p.name.startswith("atai") else B.Units.load)
        try:
            loader(p)
        except B.ReadError:
            n += 1
    assert n == 21
    # 残る 2 枚は、小数の桁が宣言されて初めて読めないと分かる(読み込みだけでは通る)
    later = 0
    for a, o in (("atai_a", "K:obi_shousuu_sugi"), ("K:atai_kansan_hasuu", "obi_a")):
        try:
            pull(a=a, o=o)
        except B.ReadError:
            later += 1
    assert later == 2
    print(f"[measure] 「表として読めない」で返す崩した表 {n + later} 枚"
          f"(読み込みで {n} 枚 / 小数の桁と突き合わせて {later} 枚)。理由コードには混ぜない")


# ---------------------------------------------------------------- 決定論と不変

def test_measure_verify_is_deterministic() -> None:
    """2 回引いた指紋と、帯の表の行順を入れ替えた指紋が、3 回とも同じになる。"""
    for name, want in (("obi_a", "2097451c8e1d"), ("obi_ten", "f0a2c33595f6")):
        out = B.verify(values("atai_a"), bands(name), units())
        assert out["ok"] is True
        assert out["sha256"] == out["2 回目の sha256"] == out["入れ替えた表の sha256"]
        assert str(out["sha256"])[:12] == want
        print(f"[measure] {name} を 2 回 + 帯の表の行順を逆順に入れ替えて引き直し: "
              f"判定部分の sha256 は 3 回とも同じ {want}(3/3 一致)")


def test_row_order_of_the_band_table_does_not_matter() -> None:
    """帯の表の行順を入れ替えても、判定部分のバイト列が変わらない。"""
    base = pull()
    for how in B.SWAPS:
        again = B.match(values("atai_a"), bands("obi_a").swapped(how), units())
        assert again.judgement_bytes() == base.judgement_bytes(), how


def test_judgement_has_no_time_host_or_path() -> None:
    """判定部分に時刻・ホスト名・絶対パスが入らない。"""
    m = pull()
    body = m.judgement_bytes().decode("utf-8")
    for word in (m.read_at, m.host, "fixtures", ":\\", "読んだ時刻"):
        assert word not in body, word
    assert set(m.read_condition()) == set(B.READ_KEYS)


def test_measure_inputs_are_not_modified() -> None:
    """引く前後で入力 CSV の sha256 が変わらない(帯の行も値の行も生成しない)。"""
    before = {p: digest(p) for p in every_fixture()}
    assert len(before) == 42
    for o in ("obi_a", "obi_ten", "obi_chou", "obi_koumoku_nashi"):
        pull(o=o)
    B.verify(values("atai_a"), bands("obi_a"), units())
    assert {p: digest(p) for p in every_fixture()} == before
    print(f"[measure] 引く前後で入力 {len(before)} ファイルの sha256 が同じ")


def test_measure_fixtures_are_deterministic(tmp_path: Path) -> None:
    """合成 fixture は生成器から決定論的に出る(ディスク上の CSV と 1 バイト違わない)。"""
    made = M.write_all(tmp_path)
    assert len(made) == 42
    for p in made:
        here = FIX / p.relative_to(tmp_path)
        assert here.read_bytes() == p.read_bytes(), here.name


def test_measure_no_float_no_subprocess() -> None:
    """float も subprocess も random も使っていない(値は Decimal で運ぶ)。"""
    src = (ROOT / "band_edge.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    mods: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split(".")[0])
    assert mods & {"subprocess", "os", "random", "requests"} == set()
    assert "float(" not in src
    assert not re.search(r"(?<![\w.])\d+\.\d+(?![\w.])", src)   # 小数の literal も無い
    print(f"[measure] 部品が import している module は {len(mods)} 個で、"
          f"subprocess / os / random は 0 件")


# ---------------------------------------------------------------- CLI

def test_cli_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """引けたら 0、決まらない行があれば 3、表として読めなければ 2。"""
    def run(*names: str) -> int:
        return B.main([names[0], *[str(path_of(n)) for n in names[1:]]])

    assert run("check", "atai_kansan", "obi_a", "tani_a") == 0
    assert run("match", "atai_a", "obi_a", "tani_a") == 3        # 当たる帯が無い 1 行
    assert run("check", "atai_a", "obi_ten", "tani_a") == 3      # 決まらない(重なり)
    assert run("verify", "atai_a", "obi_a", "tani_a") == 0
    assert run("check", "atai_a", "K:obi_sukima", "tani_a") == 3
    assert run("check", "atai_a", "K:obi_yomenai", "tani_a") == 2
    assert B.main(["init", str(tmp_path / "ひな型")]) == 0
    capsys.readouterr()
    for name in ("値の表.csv", "帯の表.csv", "単位の宣言.csv"):
        assert (tmp_path / "ひな型" / name).exists()
    made = B.match(B.Values.load(tmp_path / "ひな型" / "値の表.csv"),
                   B.Bands.load(tmp_path / "ひな型" / "帯の表.csv"),
                   B.Units.load(tmp_path / "ひな型" / "単位の宣言.csv"))
    assert made.report.ok and made.verdict == "帯が 1 つに決まった"


def test_stopped_match_has_no_result() -> None:
    """止まっているときは結果も指紋も取れない(例外になる)。"""
    m = pull(o="K:obi_sukima")
    for call in (lambda: m.verdict, m.judgement_bytes, m.sha256):
        with pytest.raises(RuntimeError):
            call()
    assert m.counts()["4 値"]["止まった"] == 5        # type: ignore[index]
    assert m.counts()["4 値"]["決まらない(重なり)"] == 0   # type: ignore[index]
