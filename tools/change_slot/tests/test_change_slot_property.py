"""change_slot の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: rule ごとに付く答えは 1 つだけで、9 値か別枠の理由のどちらか一方に入る。
  9 値に入った rule の枠は、**置き場の登録表のその種別行が指す確認の置き所** と、台帳に宣言された
  時期の形・地域の印・直す場所の記号だけから決まる(改定の記載の文字列は一切使わない)。
  9 値と別枠の件数の合計、および種別ごとの内訳の合計は、どちらも rule の件数に等しい。
  年月の一覧と月日の一覧は交わらず、4 つの群の行数の合計も rule の件数に等しい。
  どの場合も入力の表は 1 文字も書き換わらない。

3 枚を乱数で作る。置き場の登録表は種別記号を鍵にした 1〜8 行で、(次に動く時期が言えるか ×
確認の置き所の記号)の対を公表している 6 対から乱数で選ぶ(= 種別記号と枠の対応に意味を持たせない。
道具が種別記号から枠を導く規則を内側に持っていれば、この乱数の対応と食い違って落ちる)。
**改定の記載は宣言された種別と矛盾する語を乱数で入れる**(「不定期」の記載に「動かない」の種別、
など)。記載の文字列を読む経路があれば、そこで食い違って落ちる。
台帳の行は半分の確率でどこか 1 か所を崩す(宣言なし・空の出典・3 形でない時期・登録外の記号・
空の要求する欄)。derandomize=True で毎回同じ入力列を使い、database=None で見つけた例を保存しない。

**枠の引き当てはテストの中で別に書く**(道具の slot_rows を呼ばない)。道具側の照合が壊れても
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
import change_slot as C  # noqa: E402

# 記載の文字列は宣言された種別と無関係に引く(= 記載を読む経路があれば食い違う)
記載 = st.sampled_from(["不定期", "固定", "通達", "法定", "年度", "撤廃予定・施行日は下位の定め",
                        "毎年 8/1", "合成の年月 新設", "合成の年月 廃止", "年度 (要照合)"])
時期 = st.sampled_from(["2031-04", "2029-10", "08-01", "04-01", "記載なし", "2031-4", "年度"])
地域 = st.sampled_from(["はい", "いいえ", "宣言なし"])
照合 = st.sampled_from(["照合済", "要照合"])
対象 = st.sampled_from(["率", "表", "式", "要件", "給付の有無"])
直す場所 = st.sampled_from(list(C.FIX_PLACES))
種別名 = st.sampled_from(["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛"])


@st.composite
def 置き場登録表(draw: st.DrawFn) -> dict[str, dict[str, str]]:
    kinds = draw(st.lists(種別名, min_size=1, max_size=8, unique=True))
    out: dict[str, dict[str, str]] = {}
    for k in kinds:
        sayable, slot = draw(st.sampled_from(list(C.FRAME_TABLE)))
        need = draw(st.sampled_from(["—", "時期の欄", "施行日の記載", "待っている根拠"]))
        out[f"種別 {k}"] = {"種別記号": f"種別 {k}", "次に動く時期が言えるか": sayable,
                            "確認の置き所の記号": slot, "要求する欄の名前": need,
                            "登録の出典": "合成の登録の出典"}
    return out


@st.composite
def 対象登録表(draw: st.DrawFn) -> dict[str, dict[str, str]]:
    keys = draw(st.lists(対象, min_size=1, max_size=5, unique=True))
    return {k: {"対象記号": k, "直す場所の記号": draw(直す場所),
                "再検証の範囲の記号": "合成の再検証の範囲", "出典": "合成の対象の出典"}
            for k in keys}


@st.composite
def 台帳(draw: st.DrawFn, okiba: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    鍵 = list(okiba)
    rows: list[dict[str, str]] = []
    for i in range(draw(st.integers(1, 8))):
        rows.append({
            "rule id": f"R{i:02d}",
            "領域": f"合成の領域 {i}",
            "改定の記載": draw(記載),
            "種別記号": draw(st.one_of(st.sampled_from(鍵), st.just("種別 登録外"))),
            "時期の欄": draw(時期),
            "地域で発効日が違うか": draw(地域),
            "対象記号": draw(st.one_of(対象, st.just("合成の登録外"))),
            "照合の印": draw(照合),
            "公表する側": f"合成の機関 {i}",
            "置き所が要求する欄の値": draw(st.sampled_from(["合成の記載(架空)", ""])),
            "出典": draw(st.sampled_from(["合成の棚卸し L99", ""])),
        })
    return rows


@st.composite
def 三枚(draw: st.DrawFn):
    okiba = draw(置き場登録表())
    taishou = draw(対象登録表())
    return draw(台帳(okiba)), okiba, taishou


def 枠をテストの側で引く(r: dict[str, str], okiba: dict[str, dict[str, str]],
                        taishou: dict[str, dict[str, str]]) -> str:
    """道具の slot_rows を呼ばずに、登録表と宣言された欄から枠を引き直す。"""
    reg = okiba[r["種別記号"]]
    frame = C.FRAME_TABLE[(reg["次に動く時期が言えるか"], reg["確認の置き所の記号"])]
    form = C.timing_form(r["時期の欄"])
    if frame == "定例":
        if r["地域で発効日が違うか"] == "はい":
            return C.PLACES["③"]
        if form == "月日":
            return C.PLACES["①"]
        if form == "年月":
            return C.PLACES["②"]
        return "別枠 / 定例の枠なのに時期が記載なし"
    if frame == "随時":
        return C.PLACES["④"]
    if frame == "済み":
        return C.PLACES["⑥"] if taishou[r["対象記号"]]["直す場所の記号"] in C.ADD_OR_CLOSE \
            else C.PLACES["⑤"]
    if frame == "動かない":
        return C.PLACES["⑨"]
    return C.PLACES["⑦"] if frame == "将来" else C.PLACES["⑧"]


@settings(max_examples=300, derandomize=True, database=None, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(三枚())
def test_いつも成り立つこと_9値か別枠のどちらか一方で登録表が指す先と同じ(data) -> None:
    kaitei, okiba, taishou = data
    写し = copy.deepcopy(kaitei)
    登録の写し = copy.deepcopy(okiba)
    対象の写し = copy.deepcopy(taishou)
    rows = C.slot_rows(kaitei, okiba, taishou)

    assert len(rows) == len(kaitei)
    元 = {r["rule id"]: r for r in kaitei}
    for r in rows:
        assert bool(r["枠"]) != bool(r["別枠の理由"])        # 答えは 1 つだけ
        if r["枠"]:
            event("枠に入った")
            assert r["枠"] == 枠をテストの側で引く(元[r["rule id"]], okiba, taishou)
            assert r["別枠の理由"] == ""
        else:
            event(f"別枠 / {r['別枠の理由']}")
            assert r["別枠の理由"] in C.ASIDE

    got = C.judge(kaitei, okiba, taishou)
    n = len(kaitei)
    assert got["分母(rule の件数)"] == n
    assert sum(got["9 値"].values()) + sum(got["別枠"].values()) == n
    assert sum(sum(v.values()) for v in got["種別ごとの内訳"].values()) == n
    assert sum(got["一覧の行数"].values()) == n
    assert got["合計が合う"] is True

    grouped = C.lists(rows)
    年月 = [r["時期の欄"] for r in grouped["年月の一覧"]]
    月日 = [r["時期の欄"] for r in grouped["月日の一覧"]]
    assert 年月 == sorted(年月) and 月日 == sorted(月日)     # 並びは時期の文字列だけ
    assert all(C.timing_form(x) == "年月" for x in 年月)
    assert all(C.timing_form(x) == "月日" for x in 月日)

    assert kaitei == 写し and okiba == 登録の写し and taishou == 対象の写し   # 入力は書き換わらない


@settings(max_examples=200, derandomize=True, database=None, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(三枚())
def test_登録表の1行を差し替えると答えもその行の指す先へ動く(data) -> None:
    """種別記号から枠を導く規則を道具が持っていないこと(= 登録表だけが行き先を決める)。"""
    kaitei, okiba, taishou = data
    base = C._answers(kaitei, okiba, taishou)
    for kind in list(okiba):
        for sayable, slot in C.FRAME_TABLE:
            差し替え = C._swap_okiba(okiba, kind, sayable, slot)
            after = C._answers(kaitei, 差し替え, taishou)
            for r in C._canon(kaitei):
                rid = r["rule id"]
                if r["種別記号"] != kind:
                    continue
                if base[rid].startswith("別枠"):
                    continue          # 別枠の理由は枠の差し替えでは動かないか、別の別枠へ動く
                event("枠が動いた" if after[rid] != base[rid] else "同じ組み合わせで据え置き")
                assert after[rid] == 枠をテストの側で引く(r, 差し替え, taishou)


@settings(max_examples=200, derandomize=True, database=None, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(三枚())
def test_改定の記載を入れ替えても答えは動かない(data) -> None:
    """記載の文字列から種別を当てる経路が無いこと。"""
    kaitei, okiba, taishou = data
    base = C._answers(kaitei, okiba, taishou)
    for word in ("不定期", "固定", "通達", "年度", "撤廃予定・施行日は下位の定め"):
        swapped = [{**r, "改定の記載": word} for r in kaitei]
        assert C._answers(swapped, okiba, taishou) == base
