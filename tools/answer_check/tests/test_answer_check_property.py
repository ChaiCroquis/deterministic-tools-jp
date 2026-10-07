"""answer_check の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 判定の結果は 2 通りしかない。
  (a) 文章から見つけた表記のひとつひとつがちょうど 1 つの箱に入り(接地 / 食い違い / 塊に無い /
      比べられない、または読めなかった表記)、その合計が見つけた表記の総数に等しく、同じ入力から
      2 回判定すれば同じバイト列になる
  (b) 判定は 1 件も返らず、理由コードが返る
どちらの場合も、文章は 1 文字も書き換わらず、塊の行も書き換わらず、どちらが正しいとも返らない。

入力は毎回乱数で作り直す。塊は 0〜3 件、宣言表は対象 3 つ(塊に無い対象も混ぜる)、文章は 0〜5 文で
1 文につき 1 つの表記を置く。表記は 9 とおり(読める / 読めない)、単位は 4 とおり(宣言にある 2 つ /
宣言に無い 1 つ / 単位なし)から引く。さらに 3 割くらいの確率で 1 か所だけ崩す(塊の出典 / 指紋 /
有効期間 / 公表時点を空にする、同じ対象の行を 2 件にする、宣言の単位を空にする、登録に無い丸めの
名前を呼ぶ、文章を空にする)。

**期待値は道具の関数を使わず、このテストの中に別に書く**(表記を数として読むところ、倍率と丸めを
当てるところ、4 値に分けるところを別実装で持つ)。道具自身の判定が壊れても、このテストで気づける
ようにするため。derandomize=True で毎回同じ 300 通りを試し、database=None で例を保存しない。
"""
from __future__ import annotations

import copy
import json
import re
import sys
import unicodedata
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import answer_check as A  # noqa: E402

SHA = "d8d3d48c3f2894ef2f63b9d8ce7994df8b6b1f4c1ad9cafaa87db74a5680de0c"
PERIOD = "2026-06-01"
ROUNDING = "小数2桁"
UNITS = ("%", "‰")
SCALES = ("そのまま", "10分の1")
TAI = {"甲": "対象A", "乙": "対象B", "丙": "対象C"}          # 呼び方 → 対象
BAI = {"%": Decimal("1"), "‰": Decimal("0.1")}               # 宣言した倍率(テスト側の別実装)

表記 = st.sampled_from(["9.70", "9.7", "1.60", "1120", "1,120", "１，１２０", "97",
                        "九・七", "9.70〜9.82", "3,57,000"])
単位 = st.sampled_from(list(UNITS) + ["円", ""])            # 円 は宣言に無い単位
呼び方 = st.sampled_from(list(TAI) + [""])                   # 空 = 呼び方の無い文
値 = st.sampled_from(["9.70", "1.60", "1120"])
崩し = st.sampled_from(["崩さない", "崩さない", "崩さない", "出典", "指紋", "有効期間",
                        "公表時点", "同じ対象 2 件", "単位の宣言", "丸めの名前", "文章を空"])


def 塊の行(selector: str, payload: str) -> dict:
    return {"selector": selector, "payload": payload, "valid_from": "2026-01-01", "valid_to": "",
            "known_from": "2026-01-10", "known_quality": "実値", "source": "合成の表(架空)",
            "source_file": "moto.csv", "source_row": "2", "source_sha256": SHA, "priority": "0"}


@st.composite
def 入力(draw: st.DrawFn) -> dict:
    selectors = draw(st.lists(st.sampled_from(sorted(TAI.values())), max_size=3, unique=True))
    pack = [塊の行(s, draw(値)) for s in selectors]
    decl_rows = [{"selector": s, "alias": a, "unit": "|".join(UNITS), "scale": "|".join(SCALES),
                  "period": PERIOD, "rounding": ROUNDING} for a, s in sorted(TAI.items())]
    文 = draw(st.lists(st.tuples(呼び方, 表記, 単位), max_size=5))
    kuzushi = draw(崩し)
    if kuzushi == "出典" and pack:
        pack[0]["source"] = ""
    elif kuzushi == "指紋" and pack:
        pack[0]["source_sha256"] = ""
    elif kuzushi == "有効期間" and pack:
        pack[0]["valid_from"] = ""
    elif kuzushi == "公表時点" and pack:
        pack[0]["known_quality"] = ""
    elif kuzushi == "同じ対象 2 件" and pack:
        pack.append(dict(pack[0]))
    elif kuzushi == "単位の宣言":
        decl_rows[0] = {**decl_rows[0], "unit": "", "scale": ""}
    elif kuzushi == "丸めの名前":
        decl_rows[0] = {**decl_rows[0], "rounding": "四捨五入"}
    elif kuzushi == "文章を空":
        文 = []
    return {"pack": pack, "decl": decl_rows, "文": 文, "崩し": kuzushi}


def 文章にする(文: list) -> str:
    return "".join(f"{a or '合計'}は {n}{u} だ。\n" for a, n, u in 文)


# ------------------------------------------------- 期待値(道具の関数を使わない別実装)

_STRICT = re.compile(r"\A(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?\Z")
_KANJI = re.compile(r"\A[〇一二三四五六七八九十][〇一二三四五六七八九十百千万・点]*\Z")


def 読む(表記: str) -> "Decimal | None":
    t = unicodedata.normalize("NFKC", 表記)
    return Decimal(t.replace(",", "")) if _STRICT.match(t) else None


def 二桁に(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def 期待する箱(文: list, pack: list) -> list:
    """1 文 1 表記について、どの箱に入るかをテスト側で決める。"""
    payload = {r["selector"]: r["payload"] for r in pack}
    out = []
    for alias, 表記, 書いた単位 in 文:
        # 部品が読み取る単位は宣言されたものだけ(宣言に無い単位は「単位なし」と同じ扱い)
        単位 = 書いた単位 if 書いた単位 in UNITS else ""
        if _KANJI.match(表記) and not 単位:
            continue                      # 単位の付かない漢数字は数の表記として拾わない
        mine = 読む(表記)
        if mine is None:
            out.append("読めなかった表記")
        elif not alias:
            out.append(A.ABSENT)
        elif not 単位:
            out.append(A.INCOMPARABLE)
        elif TAI[alias] not in payload:
            out.append(A.ABSENT)
        else:
            theirs = 読む(payload[TAI[alias]])
            out.append(A.GROUNDED if 二桁に(mine * BAI[単位]) == 二桁に(theirs) else A.DISAGREE)
    return out


# ------------------------------------------------- いつも成り立つこと

@settings(max_examples=300, derandomize=True, database=None, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(入力())
def test_いつも成り立つこと_全部が箱に入るか_理由コードか(入力: dict) -> None:
    pack, decl_rows, 文 = 入力["pack"], 入力["decl"], 入力["文"]
    body = 文章にする(文)
    before_pack = json.dumps(pack, ensure_ascii=False, sort_keys=True)
    before_body = body
    decl = A.Declaration.of(copy.deepcopy(decl_rows))

    c = A.check(copy.deepcopy(pack), decl, body)
    if c.report.ok:
        event("(a) 判定した")
        箱 = 期待する箱(文, pack)
        counts, d = c.counts(), c.denominator()
        assert d["見つけた表記の総数"] == len(箱)
        assert d["取り出せなかった表記"] == 箱.count("読めなかった表記")
        assert d["文章から取り出せた数値"] == sum(counts.values())
        for v in A.VERDICTS:
            assert counts[v] == 箱.count(v), (v, 箱, c.table())
        # 同じ入力から 2 回判定すれば同じバイト列
        assert A.check(copy.deepcopy(pack), decl, body).sha256() == c.sha256()
        # どちらが正しいとも返らない(返るのは 4 値と、塊のどの行と比べたかだけ)
        欄 = {"表記", "文", "単位", "読めた", "対象", "判定", "正規化", "塊の行", "塊の値", "なぜ"}
        for row in c.table():
            assert set(row) <= 欄, set(row) - 欄
            assert "正しい" not in json.dumps(row, ensure_ascii=False)
    else:
        event("(b) 理由コードで止まった")
        assert c.report.pending
        assert set(c.report.reasons()) <= set(A.REASONS)
        for call in (c.counts, c.table, c.rate, c.denominator):
            try:
                call()
                raise AssertionError("止まったのに結果が取れた")
            except A.CheckError:
                pass
    # 文章も塊も書き換わらない
    assert body == before_body
    assert json.dumps(pack, ensure_ascii=False, sort_keys=True) == before_pack


@settings(max_examples=300, derandomize=True, database=None, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(入力())
def test_分母の恒等式_狭い分母は必ず上振れする側に出る(入力: dict) -> None:
    c = A.check(copy.deepcopy(入力["pack"]), A.Declaration.of(copy.deepcopy(入力["decl"])),
                文章にする(入力["文"]))
    if not c.report.ok:
        event("止まった")
        return
    r = c.rate()
    counts, d = c.counts(), c.denominator()
    assert sum(counts.values()) == d["文章から取り出せた数値"]
    assert d["比べられた数値"] == counts[A.GROUNDED] + counts[A.DISAGREE]
    if d["比べられた数値"] and d["文章から取り出せた数値"]:
        event("両方の分母がある")
        assert float(r["接地率_比べられた数値のみ"]) >= float(r["接地率_取り出せた数値すべて"])
    else:
        assert "分母 0" in r["接地率_比べられた数値のみ"] + r["接地率_取り出せた数値すべて"]
