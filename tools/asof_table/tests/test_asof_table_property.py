"""asof_table の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 引き当ての結果は 2 通りしかない。
  (a) 値が返る。返るのは、基準日(case の basis の日付)が有効期間 [valid_from, valid_to) に入り、知識時間と
      対象(sel_*)にも当たる行のうち、最高 priority の行がちょうど 1 行あるときだけで、返る値・出典・
      有効開始日・行番号はその行のもの
  (b) 値は返らず、README の 5 つの理由コードのどれかで止まる
表の外の日付や期間の穴に、直近の行の値が返ることはない。

入力は乱数で作る。表は 1〜6 行、key 2 つ(basis はそれぞれ 対象月初日 / 賃金締切日)、対象の次元 2 つ
(sel_地域 / sel_帯、空欄 = ワイルドカード)。日付は 30 日ほどの狭い範囲から取り、基準日・as_of が
valid_from / valid_to / known_from / known_to にちょうど重なる境界をよく踏むようにしている。
困る値として、施行日未定(valid_from 空)、開いたままの期間(valid_to 空)、逆転した期間、差し替え済みの行
(known_to あり)、仮置きの公表日、同じ priority の行、登録外の priority、case に basis の日付が無い、
case に対象の次元が無い、表に無い key、値が空や記号だけの行を混ぜる。
derandomize=True で毎回同じ入力列を使う。database=None で見つけた例を保存しない(この版の hypothesis は実行した場所に .hypothesis/ を作るが、git と公開側への export では除外される)。

範囲: 表は形の正しいもの(日付は YYYY-MM-DD、key ごとに basis は 1 種類)だけで作る。値の前後に半角空白を
付けた行は混ぜる(落として返ることを見る)。
形の誤りは TableError で止まる別の経路で、既存のテストが見ている。

どの行が当たるかの期待値は、asof_table.resolve / Row.valid_on / known_at / matches を使わず、
このテストの中で README の「引き方」から別に書く。
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

from hypothesis import event, given, settings
from hypothesis import strategies as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import asof_table as A  # noqa: E402

理由コード = {"基準日が case に無い", "as_of 時点で未公表", "収録範囲の外", "同順位で複数該当", "公表日が仮置き"}
BASIS = {"料率_甲": "対象月初日", "料率_乙": "賃金締切日"}
次元 = {"sel_地域": ["地域A", "地域B"], "sel_帯": ["甲", "乙"]}
起点 = date(2025, 1, 1)

日 = st.integers(0, 30).map(lambda n: 起点 + timedelta(days=n))
# 値: 文字列のまま返ることを見るので、数字・記号・全角・空を混ぜる。前後に半角空白を付けた値も混ぜ、
# 空白だけが落ちて返ることを見る(README「どの欄も前後の空白だけは落とす」)。ほかの値には空白類を入れない
値 = st.one_of(st.from_regex(r"[0-9]{1,2}\.[0-9]{2}", fullmatch=True),
              st.from_regex(r"[0-9]{1,2}\.[0-9]{2}", fullmatch=True).map(lambda v: f" {v}  "),
              st.sampled_from(["", "=A1", "１２．５", "0.0", "-", "9.60%", "1,234"]),
              st.text(alphabet=st.characters(exclude_categories=("Zs", "Zl", "Zp", "Cc", "Cs")), max_size=6))


def _前後(基準: date, 手前: int, 先: int) -> st.SearchStrategy[date]:
    """基準日の 手前 日前 〜 先 日後。0 日 = ちょうど基準日(境界)。"""
    return st.integers(-手前, 先).map(lambda k: 基準 + timedelta(days=k))


@st.composite
def 行(draw: st.DrawFn, n: int, key0: str, on: date, as_of: date | None, case: dict[str, str]) -> dict[str, str]:
    """表の 1 行。3 分の 2 は、この引き当てに当たりそうな行(基準日・as_of の境界の前後)を狙って作る。"""
    狙う = key0 in BASIS and draw(st.integers(0, 2)) > 0
    key = key0 if 狙う else draw(st.sampled_from(list(BASIS)))
    if 狙う:
        vf = None if draw(st.integers(0, 9)) == 0 else draw(_前後(on, 3, 1))       # 翌日から = 当たらない
        vt = None if draw(st.booleans()) else draw(_前後(on, 0, 3))                 # 基準日で終わる = 当たらない
        kf = draw(_前後(as_of or on, 3, 1))                                         # as_of の翌日に公表 = 未公表
        kt = None if draw(st.integers(0, 3)) else draw(_前後(as_of or on, 0, 3))    # as_of で差し替え = 当たらない
    else:
        vf = None if draw(st.integers(0, 7)) == 0 else draw(日)                     # 施行日未定
        vt = None if vf is None or draw(st.integers(0, 3)) == 0 else draw(日)      # 開いたまま / 逆転もありうる
        kf = draw(日)
        kt = None if draw(st.integers(0, 2)) else kf + timedelta(days=draw(st.integers(1, 15)))
    rec = {
        "key": key, "basis": BASIS[key],
        "valid_from": vf.isoformat() if vf else "", "valid_to": vt.isoformat() if vt else "",
        "known_from": kf.isoformat(), "known_to": kt.isoformat() if kt else "",
        "known_quality": draw(st.sampled_from(["実値", "実値", "仮置き", ""])),
        "priority": str(draw(st.sampled_from([0, 0, 10, 20, 5]))),               # 5 は登録外
        "value": draw(値), "source": f"合成の出典 {n}",
    }
    for d, vs in 次元.items():                                                    # "" = ワイルドカード
        rec[d] = draw(st.sampled_from(["", "", case[d], case[d]] if 狙う and d in case else [""] + vs))
    return rec


@st.composite
def 引き当て(draw: st.DrawFn):
    key = draw(st.sampled_from(list(BASIS) * 4 + ["表に無い key"]))
    on = draw(日)
    case: dict[str, str] = {}
    if draw(st.integers(0, 7)):
        case[BASIS.get(key, "対象月初日")] = on.isoformat()
    else:                                                                          # 基準日が case に無いかもしれない
        case[draw(st.sampled_from(["対象月初日", "賃金締切日", "請求日"]))] = on.isoformat()
    for d, vs in 次元.items():
        if draw(st.integers(0, 5)):                                                # たまに対象の次元が無い
            case[d] = draw(st.sampled_from(vs))
    as_of = draw(st.one_of(st.none(), 日))
    records = [draw(行(n, key, on, as_of, case)) for n in range(1, draw(st.integers(1, 6)) + 1)]
    return records, key, case, as_of


def _日付(s: str) -> date | None:
    return date.fromisoformat(s) if s else None


def 当たる行(records, key, case, as_of) -> list[tuple[int, dict[str, str]]]:
    """README「引き方」の 3〜6 段を、このテストの中で別に書いたもの。最高 priority の行(1 行とは限らない)を返す。"""
    basis = BASIS.get(key)
    if basis is None or basis not in case:
        return []
    on = date.fromisoformat(case[basis])
    hits = []
    for i, rec in enumerate(records, 1):
        if rec["key"] != key:
            continue
        vf, vt = _日付(rec["valid_from"]), _日付(rec["valid_to"])
        if vf is None or not (vf <= on and (vt is None or on < vt)):              # 有効時間(半開区間)
            continue
        kf, kt = _日付(rec["known_from"]), _日付(rec["known_to"])
        known = kt is None if as_of is None else (kf <= as_of and (kt is None or as_of < kt))
        if not known:                                                              # 知識時間
            continue
        if any(rec[d] and case.get(d, "") != rec[d] for d in 次元):                 # 対象(空欄は何にでも当たる)
            continue
        hits.append((i, rec))
    if not hits:
        return []
    top = max(int(rec["priority"]) for _, rec in hits)
    return [(i, rec) for i, rec in hits if int(rec["priority"]) == top]


@settings(max_examples=500, derandomize=True, database=None, deadline=None)
@given(入力=引き当て())
def test_いつも成り立つこと_値が返るのは当たる行がちょうど1行のときだけ(入力) -> None:
    records, key, case, as_of = 入力
    table = A.Table.from_records(records)
    r = A.resolve(table, key, case, as_of)
    best = 当たる行(records, key, case, as_of)
    if r.ok:
        event("(a) 値が返った")
        assert len(best) == 1, f"当たる最高 priority の行が {len(best)} 行なのに値が返った"
        i, rec = best[0]
        assert (r.row, r.value, r.source) == (i, rec["value"].strip(" "), rec["source"]), "返った値が当たる行のものでない"
        assert r.valid_from == date.fromisoformat(rec["valid_from"]) and r.priority == int(rec["priority"])
        assert r.reason == ""
    else:
        event(f"(b) 止まった: {r.reason}")
        assert r.reason in 理由コード
        assert (r.value, r.source, r.row, r.valid_from) == ("", "", None, None), "止まったのに値が付いている"
