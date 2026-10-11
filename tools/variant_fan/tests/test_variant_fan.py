"""variant_fan のテスト。合成 fixture は make_fixtures が書く(実データ・実在の取引先名は入れない)。

test_measure_* が記事に載せた数値の出どころで、assert で固定している(値が変われば記事も変える前提)。
測るものは 3 つある。

  (1) 6 軸を全部宣言した式表と軸表に 96 通りを流したときの、相異なる値と扇の幅
  (2) 軸を 1 本ずつ宣言に戻していく 6 段(残りは式表に literal で書き切る)の、組み合わせ数と
      相異なる値の増え方。**この増分は道具の出力ではなく、テストが表を 6 段に作り分けて数え直したもの**
      (道具には軸ごとの寄与を出す経路が無い)
  (3) 丸めの名前の軸だけを動かしたときに、扇が開く組と開かない組の数
"""
from __future__ import annotations

import collections
import hashlib
import sys
from decimal import Decimal
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIX = ROOT / "fixtures"
PLAN = ROOT.parent.parent          # 07_記事化商品化計画
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FIX))
import make_fixtures as M  # noqa: E402
import variant_fan as V  # noqa: E402

TARGET = "負担額"
KOWASHITA = FIX / "kowashita"

# 軸表の出典のうち repo 内の実在の行を指すもの -> その行に在るはずの語
GENPON = {"tools/formula_table/README.md L37": "50銭以下切捨て",
          "tools/formula_table/README.md L38": "1円未満切捨て",
          "tools/formula_table/README.md L39": "円未満四捨五入",
          "tools/formula_table/README.md L40": "丸めない",
          "articles/07_asof_table.md L28": "締切日"}


@pytest.fixture(scope="session", autouse=True)
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """崩した表と累積の表を tmp に書き直す(repo に置くのは clean な 2 枚だけ)。"""
    return M.build(tmp_path_factory.mktemp("variant_fan"))


@pytest.fixture(scope="session")
def spec() -> V.Spec:
    return V.Spec.load(FIX / "shikihyou.csv", FIX / "jikuhyou.csv")


@pytest.fixture(scope="session")
def ogi(spec: V.Spec) -> V.Fan:
    return V.fan(spec, TARGET, M.INPUTS, "基準日の取り方", M.AS_OF)


def fingerprint(*paths: Path) -> str:
    h = hashlib.sha256()
    for p in paths:
        h.update(p.name.encode("utf-8"))
        h.update(p.read_bytes())
    return h.hexdigest()


def broken(built: Path, formulas: str, axes: str) -> V.Spec:
    f = built / "kowashita" / formulas if formulas else FIX / "shikihyou.csv"
    a = built / "kowashita" / axes if axes else FIX / "jikuhyou.csv"
    return V.Spec.load(f, a)


# ---------------------------------------------------------------- 入り口
def test_committed_tables_load(spec: V.Spec) -> None:
    """repo に入れてある式表と軸表は、表として読める(止まる理由が 0 件)。"""
    assert spec.pending == ()
    assert len(spec.formulas) == 4
    assert [a.name for a in spec.axes] == list(M.ORDER)
    assert all(s for a in spec.axes for s in a.sources)


def test_missing_column_is_not_a_reason_code(built: Path) -> None:
    """列が足りない式表は理由コードにせず、表として読めないことにする(終了コード 2)。"""
    path = built / "kowashita" / "shiki_retsu_nashi.csv"
    with pytest.raises(V.TableError):
        V.Spec.load(path, FIX / "jikuhyou.csv")
    assert V.main(["fan", str(path), str(FIX / "jikuhyou.csv"), "--id", TARGET,
                   "--on", "基準日の取り方", "--as-of", M.AS_OF]) == 2


def test_the_three_positions_are_decided_by_where_the_name_is_written(spec: V.Spec) -> None:
    """軸がどこに効くかは、軸の名前をどこに書いたかだけで決まる(意味からは決めない)。"""
    pos = spec.positions("基準日の取り方", M.AS_OF)
    assert pos == {"丸めの名前": ["丸めの列"], "丸めを掛ける段": ["丸めの列"],
                   "入力の桁の扱い": ["丸めの列"], "基準日の取り方": ["基準日の引数"],
                   "区分の選び方": ["式の中の名前"], "期間の切り方": ["式の中の名前"]}
    assert len(V.POSITIONS) == 3
    assert set(V.ROUNDINGS) == {"50銭以下切捨て", "1円未満切捨て", "円未満四捨五入", "丸めない"}
    assert len(V.STOP_REASONS) == 9


def test_every_choice_keeps_its_source_and_the_repo_ones_resolve(spec: V.Spec) -> None:
    """出典は 13 行すべてに在り、repo 内を指す出典はその行に宣言の語が実在する。"""
    rows = [(a.name, c, s) for a in spec.axes for c, s in zip(a.choices, a.sources)]
    assert len(rows) == 13
    genpon = [r for r in rows if r[2] in GENPON]
    assert len(genpon) == 9
    for _, _, source in genpon:
        rel, _, line = source.rpartition(" L")
        text = (PLAN / rel).read_text(encoding="utf-8-sig").splitlines()[int(line) - 1]
        assert GENPON[source] in text, source
    assert all("架空" in r[2] for r in rows if r[2] not in GENPON)


# ---------------------------------------------------------------- 測定 1: 96 通り
def test_measure_the_fan_over_all_six_axes(ogi: V.Fan) -> None:
    c = ogi.counts()
    assert ogi.report.ok is True
    assert c["組み合わせ総数"] == 96
    assert c["軸ごとの候補数"] == {"丸めの名前": 3, "丸めを掛ける段": 2, "基準日の取り方": 2,
                                   "区分の選び方": 2, "期間の切り方": 2, "入力の桁の扱い": 2}
    assert c["相異なる値の件数"] == 13
    values = [v for v, _ in ogi.distinct()]
    assert values == ["8536", "8537", "8707", "8820", "8821", "8997", "10479",
                      "10688", "10689", "10827", "10828", "11044", "11045"]
    assert [len(cs) for _, cs in ogi.distinct()] == [8, 4, 12, 2, 10, 12, 12, 4, 8, 2, 10, 6, 6]
    assert sum(len(cs) for _, cs in ogi.distinct()) == c["組み合わせ総数"]
    print(f"[measure] 6 軸の候補を全通り組み合わせた: 組み合わせ総数 {c['組み合わせ総数']} / "
          f"相異なる値 {c['相異なる値の件数']} 通り")
    print(f"[measure] 相異なる値: {' / '.join(values)}")


def test_measure_the_width_is_the_observed_min_and_max(ogi: V.Fan) -> None:
    w = ogi.width()
    assert (w["最小"], w["最大"]) == ("8536", "11045")
    assert Decimal(w["最大"]) - Decimal(w["最小"]) == Decimal("2509")
    print(f"[measure] 扇の幅: {w['最小']} 〜 {w['最大']}(開き 2509)。平均・中央値・最頻値は返さない")


def test_measure_only_one_of_the_thirteen_is_marked_as_declared_default(ogi: V.Fan) -> None:
    """宣言された既定の組み合わせには印だけを付ける(正しい・推奨とは書かない)。"""
    marked = [row for row in ogi.table() if row["印"]]
    assert len(marked) == 1
    assert marked[0]["値"] == "8997"
    assert marked[0]["印"] == V.DEFAULT_MARK == "宣言された既定"
    assert all(row["印"] in ("", V.DEFAULT_MARK) for row in ogi.table())
    print(f"[measure] 13 通りのうち印が付いたのは 1 つだけ(宣言された既定の組み合わせ = {marked[0]['値']})")


def test_measure_every_value_carries_the_combinations_verbatim(ogi: V.Fan) -> None:
    """値ごとに、その値を出した軸の組み合わせが verbatim で並ぶ。"""
    for row in ogi.table():
        assert row["件数"] == len(row["出した組み合わせ"]) >= 1
        for combo in row["出した組み合わせ"]:
            assert [x["軸"] for x in combo] == list(M.ORDER)
            for x in combo:
                assert x["候補"] in [c for c, _ in M.CHOICES[x["軸"]]]
    total = sum(row["件数"] for row in ogi.table())
    assert total == 96
    print(f"[measure] 96 通りの組み合わせはどれもちょうど 1 つの値に属し、値ごとに候補の verbatim が付く")


# ---------------------------------------------------------------- 測定 2: 1 軸ずつ
def test_measure_adding_one_axis_at_a_time(built: Path) -> None:
    """軸を 1 本ずつ宣言に戻す(残りは式表に書き切る)。組み合わせは掛け算、値はそれより遅く増える。"""
    totals, distincts = [], []
    for k in range(1, len(M.ORDER) + 1):
        pinned = M.ORDER[k:]
        spec = V.Spec.load(built / "cumulative" / f"k{k}_shikihyou.csv",
                           built / "cumulative" / f"k{k}_jikuhyou.csv")
        assert spec.pending == ()
        f = V.fan(spec, TARGET, M.INPUTS, M.on_arg(pinned), M.AS_OF)
        assert f.report.ok is True
        totals.append(f.report.total)
        distincts.append(len(f.distinct()))
    assert totals == [3, 6, 12, 24, 48, 96]
    assert distincts == [1, 1, 2, 5, 11, 13]
    zoubun = [b - a for a, b in zip([1] + distincts, distincts)]
    assert zoubun == [0, 0, 1, 3, 6, 2]
    for name, t, d, z in zip(M.ORDER, totals, distincts, zoubun):
        print(f"[measure] 軸を {name} まで宣言に戻す: 組み合わせ {t} / 相異なる値 {d} 通り(増えた分 {z})")
    print("[measure] 組み合わせは 3 から 96 へ掛け算で増え、相異なる値は 1 から 13 へそれより遅く増えた")
    print("[measure] この増分は道具の出力ではなく、テストが表を 6 段に作り分けて数え直したもの")


def test_measure_the_fan_can_collapse_to_one_value(built: Path) -> None:
    """選び方を書き切り、端数が境目から離れている金額では、丸めの 3 候補でも値は 1 通りになる。"""
    spec = V.Spec.load(built / "kakikiri_shikihyou.csv", built / "kakikiri_jikuhyou.csv")
    f = V.fan(spec, TARGET, M.INPUTS_KAKIKIRI, M.on_arg(M.ORDER[1:]), M.AS_OF)
    assert f.report.ok is True
    assert f.report.total == 3
    assert [v for v, _ in f.distinct()] == ["829"]
    assert V.main(["fan", str(built / "kakikiri_shikihyou.csv"), str(built / "kakikiri_jikuhyou.csv"),
                   "--id", TARGET, "--input", "報酬月額=30000", "--input", "出勤日数=20",
                   "--on", M.on_arg(M.ORDER[1:]), "--as-of", M.AS_OF]) == 0
    print("[measure] 書き切った式表に丸めの名前 3 候補だけを残すと、3 通りの組み合わせから値は 1 通り(829)"
          "、終了コードは 0")


# ---------------------------------------------------------------- 測定 3: 丸めの軸は端数次第
def test_measure_the_rounding_axis_opens_the_fan_only_at_the_boundary(ogi: V.Fan) -> None:
    """ほかの 5 軸を固定した 32 組のうち、丸めの名前の 3 候補で値が分かれた組を数える。"""
    groups: dict[tuple[str, ...], set[str]] = collections.defaultdict(set)
    for c in ogi.combos:
        groups[tuple(v for k, v in c.choices if k != "丸めの名前")].add(c.value)
    assert len(groups) == 32
    hiraita = [g for g in groups.values() if len(g) > 1]
    assert len(hiraita) == 15
    assert sorted(collections.Counter(len(g) for g in groups.values()).items()) == [(1, 17), (2, 15)]
    print(f"[measure] ほかの 5 軸を固定した {len(groups)} 組のうち、丸めの名前で値が分かれたのは {len(hiraita)} 組、"
          f"残り 17 組は 3 候補とも同じ値")
    print("[measure] 分かれた 15 組はどれも 2 通りで、3 通りに分かれた組は 0 組")


def test_measure_the_as_of_axis_opens_every_group(ogi: V.Fan) -> None:
    """基準日の軸は、ほかを固定した 48 組すべてで値を分けた(版が変わるため)。"""
    groups: dict[tuple[str, ...], set[str]] = collections.defaultdict(set)
    for c in ogi.combos:
        groups[tuple(v for k, v in c.choices if k != "基準日の取り方")].add(c.value)
    assert len(groups) == 48
    assert all(len(g) == 2 for g in groups.values())
    print("[measure] 基準日の取り方は、ほかを固定した 48 組すべてで値を 2 通りに分けた")


# ---------------------------------------------------------------- 止まる
def test_measure_all_nine_stop_reasons_have_a_path(built: Path, spec: V.Spec, monkeypatch) -> None:
    seen: list[str] = []
    table_level = [("", "jiku_shutten_nashi.csv"), ("", "jiku_kouho_1.csv"), ("", "jiku_juufuku.csv"),
                   ("", "jiku_marume_mitouroku.csv"), ("", "jiku_jougen_koe.csv"),
                   ("shiki_marume_kuuran.csv", ""), ("shiki_kikan_hazure.csv", ""),
                   ("shiki_nijuu.csv", ""), ("shiki_id_nashi.csv", "")]
    for f_name, a_name in table_level:
        s = broken(built, f_name, a_name)
        f = V.fan(s, TARGET, M.INPUTS, "基準日の取り方", M.AS_OF)
        assert f.report.ok is False
        assert f.combos == ()
        for call in (f.distinct, f.read_conditions):
            with pytest.raises(RuntimeError):
                call()
        seen += [p.reason for p in f.report.pending]
    f = V.fan(spec, TARGET, {"報酬月額": 310000.0, "出勤日数": "21"}, "基準日の取り方", M.AS_OF)
    assert f.report.ok is False
    seen += [p.reason for p in f.report.pending]

    real = V._evaluate
    state = {"n": 0}

    def flaky(sp, fid, inputs, bind, on, as_of, stack):          # 2 回目の数え上げだけ 1 円ずらす
        raw, value = real(sp, fid, inputs, bind, on, as_of, stack)
        if not stack:
            state["n"] += 1
            if state["n"] > 96:
                value = value + 1
        return raw, value

    monkeypatch.setattr(V, "_evaluate", flaky)
    out = V.verify(spec, TARGET, M.INPUTS, "基準日の取り方", M.AS_OF)
    assert out["ok"] is False and out["一致"] is False
    assert out["sha256"] != out["2 回目の sha256"]
    assert out["不一致の内訳"]
    seen += [p["reason"] for p in out["pending"]]

    assert set(seen) == set(V.STOP_REASONS)
    print(f"[measure] 止まる理由コード {len(V.STOP_REASONS)} 個すべてに道がある: "
          f"{' / '.join(V.STOP_REASONS)}")
    print("[measure] 止まったときは値を 1 件も返さない(扇を取りに行くと例外)")


def test_an_out_of_range_name_in_the_table_is_a_table_error() -> None:
    """軸・式の id・入力のどれにも無い名前は、理由コードでなく表の誤りにする。"""
    spec = V.Spec.load(FIX / "shikihyou.csv", FIX / "jikuhyou.csv")
    with pytest.raises(V.TableError):
        V.fan(spec, TARGET, {"報酬月額": "310000"}, "基準日の取り方", M.AS_OF)   # 出勤日数 が無い


# ---------------------------------------------------------------- 決定論と不変
def test_measure_counting_twice_matches_on_the_judgement_part(spec: V.Spec, ogi: V.Fan) -> None:
    out = V.verify(spec, TARGET, M.INPUTS, "基準日の取り方", M.AS_OF)
    assert out["ok"] is True and out["数えた回数"] == 2
    assert out["sha256"] == out["2 回目の sha256"] == ogi.sha256()
    assert ogi.sha256().startswith("2f21cb7e43f1")
    print(f"[measure] 同じ入力で 2 回数える: 判定部分の sha256 が一致(先頭 12 桁 {ogi.sha256()[:12]})")


def test_the_judgement_part_has_no_clock_or_path_or_host(ogi: V.Fan) -> None:
    raw = ogi.judgement_bytes().decode("utf-8")
    for key in ("読んだ時刻", "ホスト名", "読んだ式表の絶対パス", str(FIX)):
        assert key not in raw
    read = ogi.read_conditions()[0]
    assert read["読んだ時刻"] and read["ホスト名"] and read["読んだ式表の絶対パス"]
    assert list(ogi.table()[0]) == list(V.JUDGEMENT_KEYS)


def test_measure_the_input_tables_are_untouched(spec: V.Spec) -> None:
    before = fingerprint(FIX / "shikihyou.csv", FIX / "jikuhyou.csv")
    V.fan(spec, TARGET, M.INPUTS, "基準日の取り方", M.AS_OF)
    V.verify(spec, TARGET, M.INPUTS, "基準日の取り方", M.AS_OF)
    after = fingerprint(FIX / "shikihyou.csv", FIX / "jikuhyou.csv")
    assert before == after
    print(f"[measure] 数える前後で式表と軸表の sha256 が同じ = 1 文字も書き換えていない(先頭 12 桁 {after[:12]})")


def test_values_are_grouped_only_by_byte_equality() -> None:
    """近いことを同じことにしない。相異なる値はバイト列の一致でだけ束ねる。"""
    spec = V.Spec.load(FIX / "shikihyou.csv", FIX / "jikuhyou.csv")
    combos = tuple(V.Combo(choices=(("軸", c),), value=v, raw=v, is_default=False)
                   for c, v in (("甲", "829"), ("乙", "829.0"), ("丙", "829")))
    f = V.Fan(V.Report(True, (), 3), spec, TARGET, combos)
    assert [v for v, _ in f.distinct()] == ["829", "829.0"]
    assert [len(cs) for _, cs in f.distinct()] == [2, 1]


def test_the_order_is_the_axis_table_order_and_the_value_order(ogi: V.Fan) -> None:
    values = [Decimal(v) for v, _ in ogi.distinct()]
    assert values == sorted(values)
    for row in ogi.table():
        for combo in row["出した組み合わせ"]:
            assert [x["軸"] for x in combo] == list(M.ORDER)


# ---------------------------------------------------------------- 持たせていないもの
def test_the_cli_has_no_option_for_picking_a_winner() -> None:
    """正解を選ぶ・許容誤差・集約・寄与率・標本・上限の上書きに相当する option が 1 つも無い。"""
    sub = next(a for a in V.build_parser()._actions if hasattr(a, "choices") and a.choices)
    for name in ("fan", "verify"):
        options = {s for act in sub.choices[name]._actions for s in act.option_strings}
        assert options == {"-h", "--help", "--id", "--input", "--on", "--as-of"}, name
    assert set(sub.choices) == {"fan", "verify", "init"}


def test_no_aggregate_or_contribution_anywhere() -> None:
    members = set(dir(V.Fan)) | set(dir(V))
    for banned in ("mean", "median", "mode", "average", "tolerance", "contribution",
                   "sensitivity", "sample", "平均", "中央値", "最頻値", "寄与率", "許容誤差"):
        assert not any(banned in m for m in members), banned
    source = (ROOT / "variant_fan.py").read_text(encoding="utf-8-sig")
    for banned in ("statistics", "Counter("):
        assert banned not in source, banned


def test_counts_never_returns_the_fan_size_alone(ogi: V.Fan) -> None:
    c = ogi.counts()
    for key in ("相異なる値の件数", "組み合わせ総数", "軸ごとの候補数",
                "分母に含めたもの", "扇は宣言された軸の範囲内"):
        assert key in c
    assert str(ogi.report.total) in str(c["分母に含めたもの"])


def test_the_tool_has_no_default_rounding(built: Path) -> None:
    """丸めの名前が決まらない式からは、値が返らない(既定の丸めを持たない)。"""
    spec = broken(built, "shiki_marume_kuuran.csv", "")
    f = V.fan(spec, TARGET, M.INPUTS, "基準日の取り方", M.AS_OF)
    assert f.report.ok is False
    assert V.STOP_REASONS[3] in {p.reason for p in f.report.pending}


# ---------------------------------------------------------------- CLI
def test_cli_fan_exits_three_when_the_fan_is_wider_than_one() -> None:
    code = V.main(["fan", str(FIX / "shikihyou.csv"), str(FIX / "jikuhyou.csv"), "--id", TARGET,
                   "--input", "報酬月額=310000", "--input", "出勤日数=21",
                   "--on", "基準日の取り方", "--as-of", M.AS_OF])
    assert code == 3


def test_cli_verify_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    code = V.main(["verify", str(FIX / "shikihyou.csv"), str(FIX / "jikuhyou.csv"), "--id", TARGET,
                   "--input", "報酬月額=310000", "--input", "出勤日数=21",
                   "--on", "基準日の取り方", "--as-of", M.AS_OF])
    assert code == 0
    assert "2 回目の sha256" in capsys.readouterr().out


def test_cli_init_writes_two_tables_that_load(tmp_path: Path) -> None:
    assert V.main(["init", str(tmp_path / "ひな型")]) == 0
    spec = V.Spec.load(tmp_path / "ひな型" / "shikihyou.csv", tmp_path / "ひな型" / "jikuhyou.csv")
    assert spec.pending == ()
    f = V.fan(spec, TARGET, M.INPUTS, "基準日の取り方", M.AS_OF)
    assert f.report.ok is True
    assert f.report.total == 96


def test_cli_fan_exits_three_when_it_stops(built: Path) -> None:
    code = V.main(["fan", str(FIX / "shikihyou.csv"), str(built / "kowashita" / "jiku_jougen_koe.csv"),
                   "--id", TARGET, "--input", "報酬月額=310000", "--input", "出勤日数=21",
                   "--on", "基準日の取り方", "--as-of", M.AS_OF])
    assert code == 3


# ---------------------------------------------------------------- 式の allowlist
@pytest.mark.parametrize("expr", ["対象額 ** 2", "対象額.real", "対象額[0]", "[x for x in 対象額]",
                                  "lambda x: x", "対象額 and 1", "対象額 % 2", "対象額 // 2"])
def test_the_expression_allowlist_rejects_at_the_syntax_stage(expr: str) -> None:
    assert V.check_syntax(expr)


def test_decimal_literals_do_not_go_through_float() -> None:
    """式の中の小数リテラルは float を経由しない(0.1 + 0.2 が 0.3 になる)。"""
    spec = V.Spec.load(FIX / "shikihyou.csv", FIX / "jikuhyou.csv")
    out = V._walk(__import__("ast").parse("0.1 + 0.2", mode="eval").body, "0.1 + 0.2", lambda n: None)
    assert str(out) == "0.3"
    assert spec.limit == 200
