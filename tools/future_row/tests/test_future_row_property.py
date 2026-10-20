"""future_row の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 読んだ範囲は 2 通りしかない。
  (a) (行 × 基準日)の組ごとに 4 つの状態が 1 つだけ付き、5 値の合計が 行数 × 基準日の数 に
      等しく、「次にいつ変わるか」は rule ごと・基準日ごとに 1 件以下で、返る日付は行の表に
      そのまま在る効き始める日(しかも基準日より後)で、効き始める日が未定の行は 1 件も
      混ざらず、判定部分に時刻・ホスト名・絶対パスが入らず、3 枚の行順を入れ替えても同じ
      バイト列になる
  (b) 1 組も読まずに理由コードが返る(読んだ組や指紋を取りに行くと例外になる)
どちらの場合も、この部品は行の表も状態の宣言も基準日の表も 1 文字も書き換えない。

rule を 1〜3 本作り、rule ごとに行を 1〜3 本、効き始める日を日付の候補から引いて前の行を閉じ
ながら並べる(最後の行だけ効き終わる日を宣言された空の記号にする)。3 割くらいの確率で効き
始める日が空の行を 1 本足す。基準日は 1〜3 件。さらに 3 割くらいの確率で 1 か所だけ崩す
(出典を空にする / 同じ行 id を 2 行書く / 知った日を基準日より後にする / 知った日より前に
効き始める日を書く / 宣言外の記号を書く / 同じ rule の宣言を 2 行書く / 期間を重ねる)。
derandomize=True で毎回同じ入力列を使い、database=None で見つけた例を保存しない。

**5 値はテストの側で別に組み立てている**(部品の判定を呼ばず、2 枚の表の行から直に決める)。
2 本目は「効き始める日の前日と当日で状態が 1 日だけずれる」ことを見ている(空を埋めて早める
経路が無い、の物理形)。入力は 日付 6 × 基準日のずれ 5 × 空かどうか 2 × 順位 3 ×
効き終わる日が空かどうか 2 = 360 通りから 300 通りを引く。
"""
from __future__ import annotations

import datetime
import sys
from pathlib import Path

import pytest
from hypothesis import event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import future_row as F  # noqa: E402

SOURCE = "合成の出典メモ(架空)L1"
DIM = "次元A"
MARK = F.MARK
KOU = "公表元(架空)"
KNOWN = "2000-01-01"
DAYS = ("2002-01-01", "2003-01-01", "2004-01-01", "2005-01-01", "2006-01-01",
        "2007-01-01")
ASOFS = ("2001-06-30", "2003-01-01", "2004-06-30", "2006-01-01", "2008-01-01")
JUNI = ("0", "10", "")          # 空欄は空欄のまま持つ

STATES_TEXT = F.STATE_SEP.join([
    f"{F.STATES[0]}=効き終わる日が基準日以前",
    f"{F.STATES[1]}=基準日が効いている期間の中",
    f"{F.STATES[2]}=効き始める日が基準日より後",
    f"{F.STATES[3]}=効き始める日が宣言された空の記号",
])

KOWASHIKATA = ("出典を空にする", "同じ行 id を 2 行書く", "知った日を基準日より後にする",
               "知った日より前に効き始める日を書く", "宣言外の記号を書く",
               "同じ rule の宣言を 2 行書く", "期間を重ねる")


def seg(value: str) -> str:
    return f"{DIM}{F.SEG_EQ}{value}"


@st.composite
def 合成の3枚(draw: st.DrawFn) -> dict[str, object]:
    """行の表 / 状態の宣言 / 基準日の表(と崩し方)を作る。"""
    rule_ids = [f"R{i + 1:02d}" for i in range(draw(st.integers(1, 3)))]
    sengen = [[rid, STATES_TEXT, F.BLANK_RULES[0], F.OPEN_RULES[0], MARK, SOURCE]
              for rid in rule_ids]

    gyou: list[list[str]] = []
    for rid in rule_ids:
        n = draw(st.integers(1, 3))
        days = sorted(draw(st.lists(st.sampled_from(DAYS), min_size=n, max_size=n,
                                    unique=True)))
        juni = draw(st.sampled_from(JUNI))
        for i, day in enumerate(days):           # 前の行を閉じながら並べる
            end = days[i + 1] if i + 1 < len(days) else MARK
            gyou.append([f"G{len(gyou) + 1:02d}", rid, KNOWN, day, end, seg(rid),
                         juni, KOU, SOURCE])
        if draw(st.sampled_from([True] + [False] * 2)):   # 効き始める日が空の行
            gyou.append([f"G{len(gyou) + 1:02d}", rid, KNOWN, MARK, MARK, seg(rid),
                         juni, KOU, SOURCE])

    chosen = sorted(draw(st.lists(st.sampled_from(ASOFS), min_size=1, max_size=3,
                                  unique=True)))
    kijunbi = [[f"A{i + 1:02d}", day, SOURCE, ""] for i, day in enumerate(chosen)]
    kijunbi[0][3] = F.SWAPS[0]

    kowasu = draw(st.sampled_from([None] * 7 + list(KOWASHIKATA)))
    if kowasu == "出典を空にする":
        gyou[0][8] = ""
    elif kowasu == "同じ行 id を 2 行書く":
        gyou.append([gyou[0][0], rule_ids[0], KNOWN, MARK, MARK, seg("betsu"),
                     "0", KOU, SOURCE])
    elif kowasu == "知った日を基準日より後にする":
        gyou[0][2] = "2099-01-01"
        gyou[0][3] = "2099-01-01"
    elif kowasu == "知った日より前に効き始める日を書く":
        gyou[0][3] = "1999-01-01"
    elif kowasu == "宣言外の記号を書く":
        gyou[0][3] = "未定"
    elif kowasu == "同じ rule の宣言を 2 行書く":
        sengen.append([rule_ids[0], STATES_TEXT, F.BLANK_RULES[0], F.OPEN_RULES[0],
                       MARK, SOURCE])
    elif kowasu == "期間を重ねる":
        gyou.append([f"G{len(gyou) + 1:02d}", gyou[0][1], KNOWN, gyou[0][3], MARK,
                     gyou[0][5], gyou[0][6], KOU, SOURCE])

    def csv(head: tuple[str, ...], body: list[list[str]]) -> str:
        return "\n".join([",".join(head)] + [",".join(r) for r in body])

    return {"gyou": csv(F.GYOU_COLUMNS, gyou),
            "sengen": csv(F.SENGEN_COLUMNS, sengen),
            "kijunbi": csv(F.KIJUNBI_COLUMNS, kijunbi),
            "gyou_rows": gyou, "sengen_rows": sengen, "kijunbi_rows": kijunbi,
            "kowasu": kowasu}


def 期待する5値(plan: dict[str, object]) -> dict[str, int]:
    """5 値を、2 枚の表の行から直に組み立てる(部品の判定は呼ばない)。"""
    out = dict.fromkeys(F.RESULTS, 0)
    for row in plan["gyou_rows"]:                 # type: ignore[union-attr]
        for asof in plan["kijunbi_rows"]:         # type: ignore[union-attr]
            vf, vt, day = row[3], row[4], asof[1]
            if vf == MARK:
                out[F.STATES[3]] += 1
            elif vf > day:
                out[F.STATES[2]] += 1
            elif vt != MARK and vt <= day:
                out[F.STATES[0]] += 1
            else:
                out[F.STATES[1]] += 1
    return out


@settings(max_examples=200, derandomize=True, database=None, deadline=None)
@given(plan=合成の3枚())
def test_いつも成り立つこと_読んだ組か理由コードか(plan: dict[str, object]) -> None:
    declared = F.Declared.parse(plan["sengen"])              # type: ignore[arg-type]
    sheet = F.Sheet.parse(plan["gyou"], "", declared)        # type: ignore[arg-type]
    asofs = F.Asofs.parse(plan["kijunbi"])                   # type: ignore[arg-type]
    t = F.future_row(sheet, declared, asofs)

    expect_stop = plan["kowasu"] is not None
    c = t.counts()
    five = c["5 値"]
    assert c["行の表の行数"] == len(plan["gyou_rows"])        # type: ignore[arg-type]
    assert c["状態の宣言の行数(rule 数)"] == len(plan["sengen_rows"])  # type: ignore[arg-type]
    assert c["基準日の数"] == len(plan["kijunbi_rows"])       # type: ignore[arg-type]
    assert c["分母(行数 × 基準日の数)"] == t.report.rows * t.report.asofs
    assert sum(five.values()) == len(t.pairs)                # type: ignore[union-attr]
    # 表が揃う前に止まったら 1 組も読まない。読んだなら組と 1 対 1 で付く
    assert len(t.pairs) in (0, t.denominator)
    assert {p.state for p in t.pairs} <= set(F.STATES)
    if t.pairs:
        assert five == 期待する5値(plan)
        assert five[F.RESULTS[4]] == 0                       # type: ignore[index]

    if expect_stop:
        event("(b) 止まった")
        assert t.report.ok is False
        assert t.report.pending and t.changes == ()
        assert {p.reason for p in t.report.pending} <= set(F.STOP_REASONS)
        for call in (t.judgement_bytes, t.sha256):
            with pytest.raises(RuntimeError):
                call()
    else:
        event("(a) 読んだ")
        assert t.report.ok is True
        assert sum(five.values()) == t.denominator
        # 答えの口と予定の口は別の配列で、足し合わせると 5 値の 4 つに戻る
        assert (len(t.today()) + len(t.ahead()) + len(t.undated())
                + len(t.closed())) == t.denominator
        # 次に変わる日は rule ごと・基準日ごとに 1 件以下
        seen: set[tuple[str, str]] = set()
        have = {r.valid_from for r in sheet.items if not r.undated}
        asof_of = {a.asof_id: a.asof for a in asofs.items}
        for ch in t.changes:
            key = (ch.rule_id, ch.asof_id)
            assert key not in seen
            seen.add(key)
            assert ch.day in have and ch.day > asof_of[ch.asof_id]
            assert ch.row_id and ch.source
        assert len(t.changes) <= t.report.rules * t.report.asofs
        for a in asofs.items:
            n = len([ch for ch in t.changes if ch.asof_id == a.asof_id])
            assert n <= t.report.rules
        body = t.judgement_bytes().decode("utf-8")
        for word in (t.read_at, t.host, "読んだ時刻", "ホスト名"):
            assert word not in body
        # 3 枚の行順を入れ替えても同じバイト列
        again = F.future_row(sheet.swapped(F.SWAPS[0]),
                             declared.swapped(F.SWAPS[0]),
                             asofs.swapped(asofs.swap or F.SWAPS[0]))
        assert again.sha256() == t.sha256()
        assert again.judgement_bytes() == t.judgement_bytes()

    # どちらの場合も入力は 1 文字も書き換わらない
    assert F.Declared.parse(plan["sengen"]).items == declared.items   # type: ignore[arg-type]
    assert F.Sheet.parse(plan["gyou"], "", declared).items == sheet.items  # type: ignore[arg-type]
    assert F.Asofs.parse(plan["kijunbi"]).items == asofs.items        # type: ignore[arg-type]


@settings(max_examples=300, derandomize=True, database=None)
@given(day=st.sampled_from(DAYS), offset=st.sampled_from((-2, -1, 0, 1, 2)),
       undated=st.booleans(), juni=st.sampled_from(JUNI), open_end=st.booleans())
def test_効き始めの前日と当日で状態が1日だけずれる(day: str, offset: int,
                                                   undated: bool, juni: str,
                                                   open_end: bool) -> None:
    """効き始める日の前日は「これから効き始める」、当日からは「基準日に効いている」。

    効き始める日が宣言された空の記号なら、どの基準日でも「効き始める日が未定」のままで、
    次に変わる日も返らない(空を基準日や年度初めで埋める経路が無い、の物理形)。
    """
    asof = (datetime.date.fromisoformat(day)
            + datetime.timedelta(days=offset)).isoformat()
    vf = MARK if undated else day
    gyou = "\n".join([",".join(F.GYOU_COLUMNS),
                      f"G01,R01,{KNOWN},{vf},{MARK},{seg('r1')},{juni},{KOU},"
                      f"{SOURCE}"])
    sengen = "\n".join([",".join(F.SENGEN_COLUMNS),
                        f"R01,{STATES_TEXT},{F.BLANK_RULES[0]},{F.OPEN_RULES[0]},"
                        f"{MARK},{SOURCE}"])
    kijunbi = "\n".join([",".join(F.KIJUNBI_COLUMNS),
                         f"A01,{asof},{SOURCE},{F.SWAPS[0]}"])
    declared = F.Declared.parse(sengen)
    t = F.future_row(F.Sheet.parse(gyou, "", declared), declared,
                     F.Asofs.parse(kijunbi))
    assert t.report.ok
    assert len(t.pairs) == 1
    state = t.pairs[0].state
    if undated:
        assert state == F.STATES[3]
        assert t.changes == ()
    elif offset < 0:
        assert state == F.STATES[2]
        assert [ch.day for ch in t.changes] == [day]
    else:
        assert state == F.STATES[1]
        assert t.changes == ()
