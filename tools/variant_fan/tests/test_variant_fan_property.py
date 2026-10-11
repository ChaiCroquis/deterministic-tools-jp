"""variant_fan の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 扇の結果は 2 通りしかない。
  (a) 宣言された軸の候補の組み合わせひとつひとつがちょうど 1 つの相異なる値に属し、各値の件数の合計が
      組み合わせ総数(= 軸ごとの候補数の積)に等しく、相異なる値は昇順で重複せず、どの値にも
      その値を出した組み合わせが verbatim で 1 つ以上付き、最小と最大は観測された値そのもので、
      印が付くのは宣言された既定の組み合わせを含む値だけ(多くて 1 つ)、判定部分のバイト列に
      時刻・ホスト名・絶対パスが 1 つも入らない
  (b) 判定が 1 件も返らず、理由コードが返る(扇を取りに行くと例外になる)
どちらの場合も、この部品は式表も軸表も 1 文字も書き換えない。

軸表は乱数で作る。軸は 1〜3 本で、1 本ごとに「式の中の名前になる軸(候補は数)」と「丸めの列になる軸
(候補は丸めの名前)」のどちらかから引き、候補は 2〜3 件。さらに 3 割くらいの確率で、表のどこか 1 か所を
崩す(出典を空にする / 候補を 1 件にする / 同じ候補を 2 行にする / 丸めの候補を registry の外にする /
上限を 1 にする)。derandomize=True で毎回同じ入力列を使い、database=None で見つけた例を保存しない。

**期待する値は部品の評価を呼ばずにテストの側で持っている**(式はテストが組み立てているので、
どの組み合わせがどの値になるかはテストの側で別に計算できる)。
"""
from __future__ import annotations

import itertools
import sys
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest
from hypothesis import event, given, settings
from hypothesis import strategies as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FIX))
import make_fixtures as M  # noqa: E402
import variant_fan as V  # noqa: E402

SOURCE = "合成の宣言(架空)L1"
VALUE_CHOICES = (("2", "3"), ("4", "5", "8"), ("10", "16"))
ROUND_CHOICES = (("1円未満切捨て", "円未満四捨五入"),
                 ("丸めない", "1円未満切捨て", "円未満四捨五入"))
KOWASHIKATA = ("出典を空にする", "候補を 1 件にする", "同じ候補を 2 行にする",
               "丸めの候補を registry の外にする", "上限を 1 にする")


def expect(x: Decimal, name: str) -> Decimal:
    """テストの側の丸め(部品の ROUNDINGS を呼ばずに別に書く)。"""
    if name == "丸めない":
        return x
    if name == "1円未満切捨て":
        return x.to_integral_value(rounding=ROUND_FLOOR)
    if name == "円未満四捨五入":
        return x.to_integral_value(rounding=ROUND_HALF_UP)
    raise AssertionError(name)


@st.composite
def 軸表(draw: st.DrawFn) -> tuple[list[tuple[str, tuple[str, ...], str]], str | None]:
    """(軸の名前, 候補, 種類)の列と、崩し方。種類は『値』か『丸め』で、丸めの列は多くて 1 本。"""
    n = draw(st.integers(min_value=1, max_value=3))
    marume = draw(st.sampled_from([None] + list(range(n))))   # 丸めの列になる軸の位置(無しも引く)
    axes = []
    for i in range(n):
        if i == marume:
            axes.append((f"軸{i + 1}", draw(st.sampled_from(ROUND_CHOICES)), "丸め"))
        else:
            axes.append((f"軸{i + 1}", draw(st.sampled_from(VALUE_CHOICES)), "値"))
    kowasu = draw(st.sampled_from([None] * 10 + list(KOWASHIKATA)))
    return axes, kowasu


def write(dest: Path, axes: list[tuple[str, tuple[str, ...], str]],
          kowasu: str | None) -> tuple[Path, Path, str, bool]:
    """式表と軸表を書く。返りは(式表, 軸表, 丸めの名前の欄に書いた文字列, 崩したか)。"""
    value_axes = [a for a in axes if a[2] == "値"]
    round_axis = next((a for a in axes if a[2] == "丸め"), None)
    expr = " + ".join(["金額"] + [name for name, *_ in value_axes]) or "金額"
    rounding = round_axis[0] if round_axis else "1円未満切捨て"
    f = dest / "shikihyou.csv"
    M.write_csv(f, M.HEADER_F,
                [["合計", expr, rounding, "2025-04-01", "", "2025-03-01", "", SOURCE]])
    body = []
    for name, choices, _ in axes:
        for i, c in enumerate(choices):
            body.append([name, c, SOURCE, "1" if i == 0 else "", "500"])
    if kowasu == "出典を空にする":
        body[0][2] = ""
    elif kowasu == "候補を 1 件にする":
        body = [r for r in body if not (r[0] == axes[0][0] and r[1] != axes[0][1][0])]
    elif kowasu == "同じ候補を 2 行にする":
        dup = list(body[0])
        dup[3] = ""                     # 既定の印は増やさない(増やすと表として読めない側になる)
        body.insert(1, dup)
    elif kowasu == "丸めの候補を registry の外にする":
        body.append(["丸めの軸X", "四捨五入", SOURCE, "1", "500"])
        body.append(["丸めの軸X", "切り上げ", SOURCE, "", "500"])
        rounding = "丸めの軸X"
        M.write_csv(f, M.HEADER_F,
                    [["合計", expr, rounding, "2025-04-01", "", "2025-03-01", "", SOURCE]])
    elif kowasu == "上限を 1 にする":
        for r in body:
            r[4] = "1"
    a = dest / "jikuhyou.csv"
    M.write_csv(a, M.HEADER_A, body)
    return f, a, rounding, kowasu is not None


@settings(max_examples=80, derandomize=True, database=None, deadline=None)
@given(spec=軸表())
def test_いつも成り立つこと_扇か理由コードか(tmp_path_factory: pytest.TempPathFactory,
                                             spec: tuple) -> None:
    axes, kowasu = spec
    dest = tmp_path_factory.mktemp("vf_property")
    f_path, a_path, rounding, broken = write(dest, axes, kowasu)
    before = {p: p.read_bytes() for p in (f_path, a_path)}
    s = V.Spec.load(f_path, a_path)
    fan = V.fan(s, "合計", {"金額": "100.5"}, "2026-04-01", "2026-05-01")

    if broken:
        event("(b) 止まった")
        assert fan.report.ok is False
        assert fan.combos == ()
        assert fan.report.pending
        assert {p.reason for p in fan.report.pending} <= set(V.STOP_REASONS)
        for call in (fan.distinct, fan.counts, fan.width, fan.read_conditions):
            with pytest.raises(RuntimeError):
                call()
    else:
        event("(a) 扇ができた")
        assert fan.report.ok is True
        names = [n for n, *_ in axes]
        pools = [c for _, c, _ in axes]
        total = 1
        for c in pools:
            total *= len(c)
        assert fan.report.total == total == len(fan.combos)

        # 期待する値はテストの側で別に計算する(部品の評価は呼ばない)
        mine: dict[str, int] = {}
        for picked in itertools.product(*pools):
            bind = dict(zip(names, picked))
            raw = Decimal("100.5")
            for n, c in zip(names, picked):
                if c not in V.ROUNDINGS:
                    raw += Decimal(c)
            name = bind.get(rounding, rounding)
            mine[str(expect(raw, name))] = mine.get(str(expect(raw, name)), 0) + 1

        d = fan.distinct()
        assert {v: len(cs) for v, cs in d} == mine
        assert sum(len(cs) for _, cs in d) == total
        assert [v for v, _ in d] == sorted({v for v, _ in d}, key=lambda s: (Decimal(s), s))
        assert fan.width() == {"最小": d[0][0], "最大": d[-1][0]}
        for row in fan.table():
            assert row["件数"] == len(row["出した組み合わせ"]) >= 1
            assert all(len(combo) == len(names) for combo in row["出した組み合わせ"])
            assert row["印"] in ("", V.DEFAULT_MARK)
        assert sum(1 for row in fan.table() if row["印"]) <= 1
        raw_bytes = fan.judgement_bytes().decode("utf-8")
        for key in ("読んだ時刻", "ホスト名", "絶対パス", str(dest)):
            assert key not in raw_bytes
    assert {p: p.read_bytes() for p in (f_path, a_path)} == before


@st.composite
def 扇の列(draw: st.DrawFn) -> V.Fan:
    """ファイルを読まずに作った扇(件数の恒等式と束ね方だけを見るため)。"""
    values = draw(st.lists(st.sampled_from(["829", "829.0", "830", "1000", "1001"]),
                           min_size=1, max_size=12))
    combos = tuple(V.Combo(choices=(("軸1", f"候補{i}"),), value=v, raw=v, is_default=(i == 0))
                   for i, v in enumerate(values))
    spec = V.Spec(formulas=(), axes=(V.Axis("軸1", tuple(f"候補{i}" for i in range(len(values))),
                                            ("出典",) * len(values), "候補0", 500, 2),),
                  limit=500)
    return V.Fan(V.Report(True, (), len(combos)), spec, "合計", combos)


@settings(max_examples=300, derandomize=True, database=None)
@given(fan=扇の列())
def test_相異なる値はバイト列の一致でだけ束ねる(fan: V.Fan) -> None:
    """近いことを同じことにしない。件数の合計はいつも組み合わせ総数に等しい。"""
    d = fan.distinct()
    assert sum(len(cs) for _, cs in d) == fan.report.total == len(fan.combos)
    assert len({v for v, _ in d}) == len(d)
    assert [v for v, _ in d] == sorted({v for v, _ in d}, key=lambda s: (Decimal(s), s))
    if "829" in dict(d) and "829.0" in dict(d):
        assert dict(d)["829"] is not dict(d)["829.0"]          # 数として等しくても別の値のまま
    c = fan.counts()
    assert c["相異なる値の件数"] == len(d)
    assert "分母に含めたもの" in c and "扇は宣言された軸の範囲内" in c
    assert sum(1 for row in fan.table() if row["印"]) <= 1
