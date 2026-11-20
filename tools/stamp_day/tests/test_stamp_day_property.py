"""stamp_day の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 読んだ結果は 2 通りしかない。
  (a) 時刻の台帳の 1 行ごとに、3 つの区分か 4 つの別枠のどれか 1 つだけが付き、その合計が台帳の行数に等しい。
      区分が付いた行では、換算後の日付と時刻が書かれた時刻と同じ瞬間を指し、区分は換算後の日付と
      頭の 10 文字の前後だけで決まる。日ごとの回数は 2 列とも合計が区分の付いた行数に等しい。
      台帳の行順を入れ替えても同じバイト列になる。
  (b) 1 行も区分せず、止まった理由が 1 つ返る。
どちらの場合も入力の 2 表は書き換わらない。

2 表は乱数で作る(derandomize=True で毎回同じ入力列。database=None で例を保存しない)。
換算と区分の照合は stamp_day の関数を使わず、このテストの中で別に書く。道具は「書かれた時刻に
時差の差を足す」形で計算しているので、こちらは時差つきの時刻を作って astimezone で換算する
別の道筋にしてある。
"""
from __future__ import annotations

import copy
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hypothesis import event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import stamp_day as T  # noqa: E402


@st.composite
def 時差の文字列(draw: st.DrawFn) -> str:
    sign = draw(st.sampled_from("+-"))
    return f"{sign}{draw(st.integers(0, 14)):02d}:{draw(st.sampled_from([0, 30, 45])):02d}"


@st.composite
def 読める時刻(draw: st.DrawFn) -> str:
    d = draw(st.datetimes(min_value=datetime(1990, 1, 1), max_value=datetime(2090, 12, 31)))
    body = d.replace(microsecond=0).isoformat()
    frac = draw(st.sampled_from(["", "", ".5", ".250", ".000001"]))
    mark = draw(st.one_of(st.just("Z"), st.just("+00:00"), 時差の文字列()))
    return body + frac + mark


困る時刻 = st.sampled_from([
    "", "2031-04-01", "2031-04-01T10:00:00", "2031-04-01T10:00:00.5", "2031-04-01 10:00:00+00:00",
    "2031-02-30T10:00:00+00:00", "2031-04-01T10:00:00+0900", "2031-04-01T25:00:00+00:00",
    "２０３１-04-01T10:00:00Z", "2031-04-01T10:00:00+00:00 ", "きのう",
])


@st.composite
def 二表(draw: st.DrawFn):
    """8 割は読める登録表(名前が重ならず、時差が読め、使う 1 行が決まる)。残りは崩れた登録表。"""
    n = draw(st.integers(0, 8))
    ids = draw(st.lists(st.sampled_from(["1", "2", "3", "4", "5", "6", "07", "7", "a", "b"]), min_size=n, max_size=n))
    stamps = [{"row_id": i,
               "stamp": draw(st.one_of(読める時刻(), 読める時刻(), 読める時刻(), 困る時刻)),
               "source": draw(st.sampled_from(["合成のメモ(架空)L1", "合成のメモ(架空)L2", "合成のメモ(架空)L3", ""]))}
              for i in ids]
    if stamps and draw(st.integers(0, 19)) == 0:
        stamps[0]["row_id"] = ""                                  # 行の番号が空(止まる)
    if draw(st.integers(0, 4)) > 0:
        names = draw(st.lists(st.sampled_from(["甲", "乙", "丙"]), min_size=1, max_size=3, unique=True))
        zones = [{"name": k, "offset": draw(時差の文字列())} for k in names]
        name = draw(st.sampled_from(names))
        if len(names) == 1 and draw(st.booleans()):
            name = None
    else:
        zones = draw(st.lists(st.fixed_dictionaries({
            "name": st.sampled_from(["甲", "乙"]),
            "offset": st.one_of(時差の文字列(), st.sampled_from(["JST", "+9:00", "", "+24:00"])),
        }), max_size=3))
        name = draw(st.sampled_from([None, "甲", "丙"]))
    return stamps, zones, name


READ = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d{1,6})?(Z|[+-]\d{2}:\d{2})$", re.ASCII)


def 別の道筋で換算(stamp: str, target: str) -> tuple[str, str]:
    """時差つきの時刻を作り、astimezone で換算先へ移す。stamp_day の関数は使わない。"""
    def tz(text: str) -> timezone:
        sign = -1 if text[0] == "-" else 1
        return timezone(sign * timedelta(hours=int(text[1:3]), minutes=int(text[4:6])))

    m = READ.match(stamp)
    assert m is not None
    micro = int((m.group(2) or ".0")[1:].ljust(6, "0"))
    mark = "+00:00" if m.group(3) == "Z" else m.group(3)
    aware = datetime.fromisoformat(m.group(1)).replace(microsecond=micro, tzinfo=tz(mark))
    moved = aware.astimezone(tz(target))
    assert moved == aware                                   # 同じ瞬間を指す
    return moved.date().isoformat(), moved.time().isoformat()


@settings(max_examples=300, derandomize=True, database=None, deadline=None)
@given(tables=二表())
def test_いつも成り立つこと_区分か別枠が1つずつ付くか_1行も区分せず止まるか(tables) -> None:
    stamps, zones, name = tables
    before = copy.deepcopy((stamps, zones))
    try:
        r = T.judge(stamps, zones, name)
    except T.Stop as e:
        event("(b) 止まった")
        assert e.reason in T.STOPS
        assert (stamps, zones) == before
        return
    event("(a) 読めた")
    assert (stamps, zones) == before

    # 1 行ごとに区分か別枠のどれか 1 つだけ。合計は台帳の行数
    assert all(x["区分"] in T.KUBUN and "別枠" not in x for x in r["rows"])
    assert all(x["別枠"] in T.ASIDES and "区分" not in x for x in r["aside"])
    assert len(r["rows"]) + len(r["aside"]) == len(stamps)
    assert sum(r["区分"].values()) == len(r["rows"])
    assert sum(r["別枠"].values()) == len(r["aside"])
    assert sorted((x["row_id"], x["書かれた時刻"], x["出典"]) for x in r["rows"] + r["aside"]) == \
        sorted((s["row_id"], s["stamp"], s["source"]) for s in stamps)

    # 区分が付いた行: 別の道筋の換算と一致し、区分は日付の前後だけで決まる
    target = r["換算先"]["時差"]
    for x in r["rows"]:
        day, clock = 別の道筋で換算(x["書かれた時刻"], target)
        assert (x["換算後の日付"], x["換算後の時刻"]) == (day, clock)
        assert x["書かれたままの日付"] == x["書かれた時刻"][:10]
        want = T.KUBUN_A if day == x["書かれたままの日付"] else T.KUBUN_B if day > x["書かれたままの日付"] else T.KUBUN_C
        assert x["区分"] == want
        assert x["出典"].strip() != ""
    # 時差の印が無い行は区分に入らない
    assert all(not re.search(r"(Z|[+-]\d{2}:\d{2})$", x["書かれた時刻"]) or x["別枠"] != T.ASIDE_NO_MARK
               for x in r["aside"])

    # 日ごとの回数は 2 列とも合計が区分の付いた行数
    assert sum(d["書かれたままの読み"] for d in r["日ごとの回数"]) == len(r["rows"])
    assert sum(d["換算後の読み"] for d in r["日ごとの回数"]) == len(r["rows"])

    # 行順を入れ替えても同じバイト列
    again = T.judge(list(reversed(stamps)), list(reversed(zones)), r["換算先"]["名前"])
    assert json.dumps(again, ensure_ascii=False, sort_keys=True) == json.dumps(r, ensure_ascii=False, sort_keys=True)
