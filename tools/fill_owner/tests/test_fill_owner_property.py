"""fill_owner の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 問いごとに付く答えは 1 つだけで、置き場 8 値か別枠の理由のどちらか一方に入る。
  置き場に入った問いの置き場は、**必ず登録表のその行が指す先と同じ**(道具が印から導いた先ではない)。
  8 値と別枠の件数の合計、および旧軸の値ごとの内訳の合計は、どちらも問いの件数に等しい。
  どの場合も入力の表は 1 文字も書き換わらない。

登録表と問いの台帳を乱数で作る。登録表は 7 つの印の組み合わせを鍵にした 1〜8 行で、置き場の記号は
乱数で割り当てる(= 印と置き場の対応に意味を持たせない。道具が規則を内側に持っていれば、この
乱数の対応と食い違って落ちる)。問いは半分の確率でどこか 1 か所を崩す(宣言なし・空の出典・
壊れた一覧 id・記載と違う旧軸の値・登録外の記号・空の要求する欄・id の重複)。
derandomize=True で毎回同じ入力列を使い、database=None で見つけた例を保存しない。

**置き場の引き当てはテストの中で別に書く**(道具の sort_rows を呼ばない)。道具側の照合が壊れても
このテストで気づけるようにするため。
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import fill_owner as F  # noqa: E402

印 = st.sampled_from(["はい", "いいえ"])
組み合わせ = st.tuples(*([印] * len(F.MARK_COLS)))
記号 = st.sampled_from(["A", "C1", "C2", "C3", "C4", "C5", "C6", "C7"])
欄名 = st.sampled_from(["有効開始日", "順位の欄", "受け取る属性の名前", "供給する閾値の名前", "—"])
旧軸の値 = st.sampled_from(["道具の中で済む", "返るが一手残る", "外から渡す前提", "止まる"])


@st.composite
def 登録表(draw: st.DrawFn) -> dict[tuple[str, ...], dict[str, str]]:
    keys = draw(st.lists(組み合わせ, min_size=1, max_size=8, unique=True))
    out: dict[tuple[str, ...], dict[str, str]] = {}
    for k in keys:
        out[k] = {"印の組み合わせ": "|".join(k),
                  "置き場の記号": draw(st.sampled_from(list(F.PLACE_MARKS))),
                  "外し方の記号": draw(記号), "誰が決めるか": draw(st.sampled_from(["行政", "主体", "人", "数式側"])),
                  "要求する欄の名前": draw(欄名), "出典": "合成の登録の出典"}
    return out


@st.composite
def 台帳(draw: st.DrawFn, okiba: dict[tuple[str, ...], dict[str, str]]) -> list[dict[str, str]]:
    鍵 = list(okiba)
    rows: list[dict[str, str]] = []
    for i in range(draw(st.integers(1, 8))):
        marks = draw(st.one_of(st.sampled_from(鍵), 組み合わせ))
        old = draw(旧軸の値)
        r = {"問い id": f"Q{i:02d}", "求める値の名前": f"合成の値 {i}(架空)", "旧軸の値": old,
             "旧軸の一覧 id": f"L31#{i}#{old}", "外し方の記号": draw(記号),
             "要求する欄の値": draw(st.sampled_from(["合成の値(架空)", ""])),
             "出典": "合成の出典"}
        r |= dict(zip(F.MARK_COLS, marks))
        rows.append(r)
    if rows and draw(st.booleans()):   # 半分の確率でどこか 1 か所を崩す
        i = draw(st.integers(0, len(rows) - 1))
        how = draw(st.sampled_from(["宣言なし", "出典が空", "一覧 id", "記載と違う", "記号", "重複"]))
        if how == "宣言なし":
            rows[i] = {**rows[i], draw(st.sampled_from(list(F.MARK_COLS))): "宣言なし"}
        elif how == "出典が空":
            rows[i] = {**rows[i], "出典": ""}
        elif how == "一覧 id":
            rows[i] = {**rows[i], "旧軸の一覧 id": draw(st.sampled_from(["", "L31", "L31#1"]))}
        elif how == "記載と違う":
            rows[i] = {**rows[i], "旧軸の一覧 id": f"L31#{i}#よその値"}
        elif how == "記号":
            rows[i] = {**rows[i], "外し方の記号": "C9"}
        else:
            rows.append(dict(rows[i]))
    return rows


@st.composite
def 三枚(draw: st.DrawFn):
    okiba = draw(登録表())
    return draw(台帳(okiba)), okiba, {"新軸の欄名": "置き場", "旧軸の欄名": "出口と実装の状態",
                                      "出典": "合成の軸の出典"}


def 置き場をテストの側で引く(r: dict[str, str], okiba: dict[tuple[str, ...], dict[str, str]]) -> str:
    """道具の sort_rows を呼ばずに、登録表から置き場を引き直す。"""
    marks = tuple(r[c] for c in F.MARK_COLS)
    return F.PLACES[okiba[marks]["置き場の記号"]]


@settings(max_examples=300, derandomize=True, database=None, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(三枚())
def test_いつも成り立つこと_置き場か別枠のどちらか一方で登録表が指す先と同じ(data) -> None:
    toi, okiba, jiku = data
    写し = copy.deepcopy(toi)
    鍵の写し = copy.deepcopy(okiba)
    rows = F.sort_rows(toi, okiba, jiku)
    new, old = jiku["新軸の欄名"], jiku["旧軸の欄名"]

    assert len(rows) == len(toi)
    元 = {r["問い id"]: r for r in toi}
    for r in rows:
        assert bool(r[new]) != bool(r["別枠の理由"])      # 答えは 1 つだけ
        if r[new]:
            event("置き場に入った")
            assert r[new] == 置き場をテストの側で引く(元[r["問い id"]], okiba)
            assert r["別枠の理由"] == ""
        else:
            event(f"別枠 / {r['別枠の理由']}")
            assert r["別枠の理由"] in F.ASIDE

    got = F.judge(toi, okiba, jiku)
    n = len(toi)
    assert got["分母(問いの件数)"] == n
    assert sum(got["8 値"].values()) + sum(got["別枠"].values()) == n
    assert sum(sum(v.values()) for v in got[f"{old}ごとの内訳"].values()) == n
    assert got["合計が合う"] is True
    assert toi == 写し and okiba == 鍵の写し            # 入力は書き換わらない


@settings(max_examples=200, derandomize=True, database=None, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(三枚())
def test_登録表の1行を差し替えると答えもその行の指す先へ動く(data) -> None:
    """印から置き場を導く規則を道具が持っていないこと(= 登録表だけが行き先を決める)。"""
    toi, okiba, jiku = data
    base = F._answers(toi, okiba, jiku)
    for marks in list(okiba):
        for to in F.PLACE_MARKS:
            差し替え = F._swap_okiba(okiba, marks, to)
            after = F._answers(toi, 差し替え, jiku)
            for r in F._canon(toi):
                tid = r["問い id"]
                if tuple(r[c] for c in F.MARK_COLS) != marks:
                    continue
                if base[tid].startswith("別枠"):
                    assert after[tid] == base[tid]       # 別枠の理由は置き場では動かない
                else:
                    event("置き場が動いた" if after[tid] != base[tid] else "同じ記号で据え置き")
                    assert after[tid] == F.PLACES[to]
