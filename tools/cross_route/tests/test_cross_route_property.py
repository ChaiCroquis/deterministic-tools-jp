"""cross_route の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: get(key) が値を返すのは、その key が両方の経路にちょうど 1 行ずつあり、比較に使う列
(value / source_file / captured_at)がどちらも空でなく、両方の normalizer が登録済みの名前で空欄でなく
通せて、scope がどちらも空でなく一致し、unit がどちらも空でなく一致し、名前で指定した正規化を通した
value が両経路で文字として一致する組だけ。それ以外(disagree・single_route・incomparable・突合前の
呼び出し)は値を返さず CrossError で止まり、どちらかを正として選ぶ経路は無い。

2 本目の性質テストは分母の恒等式を見る。agree + disagree + single_route + incomparable が常に突合表の
行数に等しく、照合できていない行を分母から外した一致率は、全ての行を分母にした一致率を下回らない
(= 狭い分母だけを引用すると一致率は必ず上振れする側に出る)。

決まった fixture を 1 か所ずつ書き換える test_measure_tampering と違い、こちらは 2 経路の表を毎回
乱数で作り直す。値は「正規化したあとの答え」を先に決め、そこから各経路が持つ value と normalizer の
名前を組み立てる(9.31 から 9.31% + パーセント、9.3100 + 桁そろえ、などを作る)ので、期待値は道具の
normalize / crosscheck / rate を通さずに分かる。困りごとは行の 3 割くらいに 1 か所だけ入れる。
derandomize=True で毎回同じ入力列を使い、database=None で見つけた例を保存しない。
"""
from __future__ import annotations

import csv
import sys
import tempfile
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import cross_route as CR  # noqa: E402

列 = ["key", "value", "unit", "scope", "source_file", "source_sha256",
      "normalizer", "captured_at", "raw_text", "locator", "note"]          # README の「経路 1 本の行」
正規化の名前 = ("そのまま", "全角半角", "カンマ除去", "パーセント", "円", "桁そろえ", "日付")   # README の 7 つ
NAME_A, NAME_B = "経路A", "経路B"
CAPTURED = "2026-10-02T09:00:00+00:00"
SHA_A, SHA_B = "a" * 64, "b" * 64
全角 = str.maketrans("0123456789,", "０１２３４５６７８９，")

困りごと = ["別の値にする", "scope を空にする", "scope を変える", "unit を変える", "unit を空にする",
          "normalizer を空欄", "登録外の normalizer", "captured_at を空", "source_file を空",
          "正規化を通せない value", "そのまま に変える", "同じ key を 2 行にする"]


# ---------------------------------------------------------------- 答え → 各経路の value(組み立てる側で答えが分かる)

@st.composite
def 値の種(draw: st.DrawFn) -> tuple:
    """(正規化後の答え, [(normalizer, value), ..])。答えを先に決め、value を組み立てる。"""
    kind = draw(st.sampled_from(["整数", "率", "日付"]))
    if kind == "整数":
        n = draw(st.integers(0, 10_000_000))
        answer = str(n)
        forms = [("そのまま", answer), ("カンマ除去", f"{n:,}"), ("カンマ除去+円", f"{n:,}円"),
                 ("全角半角+カンマ除去+円", f"{n:,}円".translate(全角)), ("桁そろえ", answer)]
    elif kind == "率":
        a = draw(st.integers(0, 20))
        f = draw(st.sampled_from([str(i) for i in range(1, 10)]
                                 + [f"{i}{j}" for i in range(10) for j in range(1, 10)]))
        answer = f"{a}.{f}"                       # 末尾に 0 を置かない形を答えにする
        forms = [("そのまま", answer), ("パーセント", answer + "%"),
                 ("パーセント+桁そろえ", answer + "0%"), ("桁そろえ", answer + "00")]
    else:
        y, m, d = draw(st.integers(2000, 2040)), draw(st.integers(1, 12)), draw(st.integers(1, 28))
        answer = f"{y:04d}-{m:02d}-{d:02d}"
        forms = [("そのまま", answer), ("日付", f"{y}年{m}月{d}日"), ("日付", f"{y}/{m}/{d}"),
                 ("日付", answer)]
    return answer, forms


@dataclass
class 行:
    row: dict
    正規化後: "str | None"                 # 名前の正規化を通した答え(None = 通せない)


@dataclass
class 組:
    key: str
    a: list = field(default_factory=list)   # 経路 A のその key の行(0 / 1 / 2 行)
    b: list = field(default_factory=list)
    答え: str = ""
    困りごと: str = ""


def _行(key: str, value: str, unit: str, scope: str, normalizer: str, sha: str, src: str) -> dict:
    return {"key": key, "value": value, "unit": unit, "scope": scope, "source_file": src,
            "source_sha256": sha, "normalizer": normalizer, "captured_at": CAPTURED,
            "raw_text": value, "locator": "合成(架空)", "note": "合成(架空)"}


@st.composite
def 場面たち(draw: st.DrawFn) -> list:
    種 = draw(st.lists(値の種(), min_size=2, max_size=6))
    組たち: list = []
    for i, (answer, forms) in enumerate(種):
        key = f"値_{i:02d}"
        scope = f"対象{i}・" + draw(st.sampled_from(["甲の負担", "乙の負担", "全区分"]))
        unit = draw(st.sampled_from(["円", "%", "円/日", "日付", "倍"]))
        在る = draw(st.sampled_from(["両方"] * 4 + ["A だけ", "B だけ"]))
        p = 組(key, 答え=answer)
        if 在る != "B だけ":
            na, va = draw(st.sampled_from(forms))
            p.a.append(行(_行(key, va, unit, scope, na, SHA_A, "keiro_a.txt"), answer))
        if 在る != "A だけ":
            nb, vb = draw(st.sampled_from(forms))
            p.b.append(行(_行(key, vb, unit, scope, nb, SHA_B, "keiro_b.json"), answer))
        if 在る == "両方" and draw(st.integers(0, 9)) < 3:
            p.困りごと = draw(st.sampled_from(困りごと))
            側 = draw(st.sampled_from(["a", "b"]))
            t = (p.a if 側 == "a" else p.b)[0]
            r = t.row
            if p.困りごと == "別の値にする":
                r["normalizer"], r["value"] = "そのまま", answer + "9"
                t.正規化後 = answer + "9"
            elif p.困りごと == "scope を空にする":
                r["scope"] = ""
            elif p.困りごと == "scope を変える":
                r["scope"] = scope + "(別の区分)"
            elif p.困りごと == "unit を変える":
                r["unit"] = unit + "/月"
            elif p.困りごと == "unit を空にする":
                r["unit"] = ""
            elif p.困りごと == "normalizer を空欄":
                r["normalizer"], t.正規化後 = "", None
            elif p.困りごと == "登録外の normalizer":
                r["normalizer"], t.正規化後 = draw(st.sampled_from(["よくある正規化", "円+四捨五入"])), None
            elif p.困りごと == "captured_at を空":
                r["captured_at"] = ""
            elif p.困りごと == "source_file を空":
                r["source_file"] = ""
            elif p.困りごと == "正規化を通せない value":
                r["normalizer"], r["value"], t.正規化後 = "パーセント", "約 " + answer, None
            elif p.困りごと == "そのまま に変える":
                r["normalizer"], t.正規化後 = "そのまま", r["value"].strip()
            elif p.困りごと == "同じ key を 2 行にする":
                (p.a if 側 == "a" else p.b).append(行(dict(r), t.正規化後))
        組たち.append(p)
    return 組たち


# ---------------------------------------------------------------- 期待(道具の関数を使わずに作る)

def 返るはず(p: 組) -> bool:
    if len(p.a) != 1 or len(p.b) != 1:
        return False
    for t in (p.a[0], p.b[0]):
        r = t.row
        if any(not r[c] for c in ("value", "source_file", "captured_at")):
            return False
        if not r["normalizer"] or any(n.strip() not in 正規化の名前 for n in r["normalizer"].split("+")):
            return False
        if t.正規化後 is None:
            return False
    ra, rb = p.a[0].row, p.b[0].row
    if not ra["scope"] or not rb["scope"] or ra["scope"] != rb["scope"]:
        return False
    if not ra["unit"] or not rb["unit"] or ra["unit"] != rb["unit"]:
        return False
    return p.a[0].正規化後 == p.b[0].正規化後


def 突合(d: Path, 組たち: list) -> CR.Cross:
    for name, pick in ((("route_a.csv"), lambda p: p.a), (("route_b.csv"), lambda p: p.b)):
        with (d / name).open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=列)
            w.writeheader()
            for p in 組たち:
                w.writerows(t.row for t in pick(p))
    return CR.crosscheck(CR.Route.load(d / "route_a.csv", NAME_A),
                         CR.Route.load(d / "route_b.csv", NAME_B))


# ---------------------------------------------------------------- 性質テスト

@settings(max_examples=200, derandomize=True, database=None, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(組たち=場面たち())
def test_いつも成り立つこと_突合を通った組だけが値を返す(組たち: list) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        c = 突合(Path(tmp), 組たち)
        for p in 組たち:
            want = 返るはず(p)
            try:
                g = c.get(p.key)
            except CR.CrossError as e:
                event(f"(b) 止まった: {p.困りごと or e.reason}")
                assert not want, (p.key, p.困りごと, p.a[0].row if p.a else None,
                                  p.b[0].row if p.b else None)
                continue
            event("(a) 値が返った")
            assert want, (p.key, p.困りごと, p.a[0].row, p.b[0].row)
            # 返るのは正規化後の答えで、両経路の出典が必ず付いてくる
            assert g.value == p.a[0].正規化後 == p.b[0].正規化後
            assert (g.route_a, g.route_b) == (NAME_A, NAME_B)
            assert (g.source_a, g.source_b) == ("keiro_a.txt", "keiro_b.json")
            assert (g.sha256_a, g.sha256_b) == (SHA_A, SHA_B)
            assert (g.unit, g.scope) == (p.a[0].row["unit"], p.a[0].row["scope"])
        # 突合前に get を呼ぶと、同じ表でも値は返らない
        before = CR.Cross(CR.Route.load(Path(tmp) / "route_a.csv", NAME_A),
                          CR.Route.load(Path(tmp) / "route_b.csv", NAME_B))
        try:
            before.get(組たち[0].key)
            止まった = False
        except CR.CrossError as e:
            止まった = e.reason == "突合前に get を呼んだ"
        assert 止まった


@settings(max_examples=200, derandomize=True, database=None, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(組たち=場面たち())
def test_いつも成り立つこと_照合できていない行を分母から落とせない(組たち: list) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        c = 突合(Path(tmp), 組たち)
        d = c.rate()
        rows = len(c.report())
        assert d["rows"] == rows
        assert d[CR.AGREE] + d[CR.DISAGREE] + d[CR.SINGLE] + d[CR.INCOMPARABLE] == rows
        assert d["compared"] == d[CR.AGREE] + d[CR.DISAGREE]
        assert d["unchecked"] == d[CR.SINGLE] + d[CR.INCOMPARABLE]
        assert str(d["unchecked"]) in d["分母に含めたもの"] and str(rows) in d["分母に含めたもの"]
        if d["compared"] == 0:
            event("比べられた行が無い")
            assert d["一致率_比べられた行のみ"] == "分母が 0"
            return
        狭い, 全体 = Decimal(d["一致率_比べられた行のみ"]), Decimal(d["一致率_全ての行"])
        event(f"照合できていない行: {d['unchecked']}")
        # 照合できていない行を分母から外した一致率は、全ての行を分母にした一致率を下回らない
        assert 狭い >= 全体
        if d["unchecked"] > 0 and d[CR.AGREE] > 0:
            assert 狭い > 全体
