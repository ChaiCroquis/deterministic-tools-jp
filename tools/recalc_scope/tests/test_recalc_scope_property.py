"""recalc_scope の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 読んだ範囲は 2 通りしかない。
  (a) 結果ごとに 4 値が 1 つだけ付き、4 値の合計が結果台帳の行数に等しく、決まらない理由別の
      合計が決まらないの件数に等しく、影響ありの結果には当たったキーが 1 件以上あり(影響なしは
      0 件)、判定部分に時刻・ホスト名・絶対パス・日付が入らず、結果台帳の行順を入れ替えても
      同じバイト列になる
  (b) 1 行も読まずに理由コードが返る(結果や指紋を取りに行くと例外)
どちらの場合も、この部品は結果の台帳も版の台帳も差分の台帳も 1 文字も書き換えない。

版を 2〜4 段の鎖にし、区間ごとに差分の宣言を入れるかどうかと全件 / 見本だけを振り、結果を
1〜4 行作る(引いた版と引いたキーをそれぞれ振る)。さらに 3 割くらいの確率で 1 か所だけ崩す
(出典を空にする / 台帳に無い指紋を書く / 指紋を空にする / 同じ結果 id を 2 行書く /
版の出典を空にする / 同じ指紋に別の日付を書く / 全件か見本かの宣言を空にする /
変更種別を宣言外にする)。derandomize=True で毎回同じ入力列を使い、database=None で
見つけた例を保存しない。

**4 値はテストの側で別に組み立てている**(部品の判定を呼ばず、台帳の行と鎖から直に決める)。
2 本目は「版の日付と出した日を振り直しても判定部分のバイト列が 1 バイトも変わらない」
ことを見ている(日付は突き合わせに使わない、の物理形)。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from hypothesis import event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import recalc_scope as R  # noqa: E402

SOURCE = "合成の出典メモ(架空)L1"
# 合成の指紋(16 桁。数字が 2 つ続かない形にして、記事の本文と取り違えないようにした)
POOL = ("a7b2c1d4e8f3a6b9", "b3c8d1e6f2a9b4c7", "c5d2e9f4a1b8c3d6", "d9e4f1a8b3c6d2e7")
OUTSIDE = "f4a1b7c2d9e6f3a8"
KEYS = ("合成のキーA(架空)", "合成のキーB(架空)", "合成のキーC(架空)")
DATES = ("2026-01-05", "2026-02-09", "2026-03-02", "2026-04-06")

KOWASHIKATA = ("出典を空にする", "台帳に無い指紋を書く", "指紋を空にする",
               "同じ結果 id を 2 行書く", "版の出典を空にする",
               "同じ指紋に別の日付を書く", "全件か見本かの宣言を空にする",
               "変更種別を宣言外にする")


@st.composite
def 合成の台帳(draw: st.DrawFn) -> dict[str, object]:
    """結果の台帳 / 版の台帳 / 差分の台帳(と崩し方)を作る。"""
    n = draw(st.integers(2, 4))
    versions = list(POOL[:n])
    han = [[v, draw(st.sampled_from(DATES)), versions[i - 1] if i else "", SOURCE]
           for i, v in enumerate(versions)]

    # 区間ごとに、差分の宣言を入れるか / 全件か見本だけか / 変わったキー
    sabun: list[list[str]] = []
    include = [draw(st.booleans()) for _ in range(n - 1)]
    if not any(include):
        include[0] = True                      # 差分の台帳が 0 行だと表として読めない
    for i, yes in enumerate(include):
        if not yes:
            continue
        ks = draw(st.lists(st.sampled_from(KEYS), max_size=3, unique=True))
        sabun.append([versions[i], versions[i + 1], R.KEY_SEP.join(sorted(ks)),
                      draw(st.sampled_from(R.CHANGES)),
                      draw(st.sampled_from(R.COVERAGES)), SOURCE])

    kekka: list[list[str]] = []
    for i in range(draw(st.integers(1, 4))):
        ks = draw(st.lists(st.sampled_from(KEYS), max_size=3, unique=True))
        kekka.append([f"R{i + 1:02d}", f"合成の区分{i + 1}", "合成の項目(架空)",
                      draw(st.sampled_from(versions)), R.KEY_SEP.join(sorted(ks)),
                      draw(st.sampled_from(DATES)), SOURCE, ""])
    kekka[0][7] = "逆順"

    kowasu = draw(st.sampled_from([None] * 7 + list(KOWASHIKATA)))
    if kowasu == "出典を空にする":
        kekka[0][6] = ""
    elif kowasu == "台帳に無い指紋を書く":
        kekka[0][3] = OUTSIDE
    elif kowasu == "指紋を空にする":
        kekka[0][3] = ""
    elif kowasu == "同じ結果 id を 2 行書く":
        kekka.append([kekka[0][0], "合成の区分X", "合成の項目(架空)", versions[0],
                      "", DATES[0], SOURCE, ""])
    elif kowasu == "版の出典を空にする":
        han[0][3] = ""
    elif kowasu == "同じ指紋に別の日付を書く":
        other = next((d for d in DATES if d != han[0][1]), None)
        han.append([han[0][0], other, han[0][2], SOURCE])
    elif kowasu == "全件か見本かの宣言を空にする":
        sabun[0][4] = ""
    elif kowasu == "変更種別を宣言外にする":
        sabun[0][3] = "入れ替え"

    def csv(head: tuple[str, ...], body: list[list[str]]) -> str:
        return "\n".join([",".join(head)] + [",".join(r) for r in body])

    return {"kekka": csv(R.KEKKA_COLUMNS, kekka), "han": csv(R.HAN_COLUMNS, han),
            "sabun": csv(R.SABUN_COLUMNS, sabun), "kekka_rows": kekka,
            "han_rows": han, "sabun_rows": sabun, "versions": versions,
            "kowasu": kowasu}


def 期待する4値(plan: dict[str, object]) -> dict[str, int]:
    """4 値を、台帳の行と鎖から直に組み立てる(部品の判定は呼ばない)。"""
    chain = list(plan["versions"])             # type: ignore[arg-type]
    sabun = plan["sabun_rows"]                 # type: ignore[assignment]
    out = dict.fromkeys(R.RESULTS, 0)
    for row in plan["kekka_rows"]:             # type: ignore[union-attr]
        version, keys = row[3], row[4]
        i = chain.index(version)
        steps = [(chain[k], chain[k + 1]) for k in range(i, len(chain) - 1)]
        mine = {x for x in keys.split(R.KEY_SEP) if x}
        groups = [[d for d in sabun if (d[0], d[1]) == st_] for st_ in steps]
        if not mine or any(not g for g in groups):
            out[R.RESULTS[2]] += 1
        elif any(d[4] == R.COVERAGES[1] for g in groups for d in g):
            out[R.RESULTS[2]] += 1
        else:
            changed = {x for g in groups for d in g
                       for x in d[2].split(R.KEY_SEP) if x}
            out[R.RESULTS[0] if mine & changed else R.RESULTS[1]] += 1
    return out


@settings(max_examples=150, derandomize=True, database=None, deadline=None)
@given(plan=合成の台帳())
def test_いつも成り立つこと_読んだ範囲か理由コードか(plan: dict[str, object]) -> None:
    kekka, han, sabun = plan["kekka"], plan["han"], plan["sabun"]
    ledger = R.Ledger.parse(kekka)                             # type: ignore[arg-type]
    versions = R.Versions.parse(han)                           # type: ignore[arg-type]
    diffs = R.Diffs.parse(sabun)                               # type: ignore[arg-type]
    t = R.scope(ledger, versions, diffs)

    expect_stop = plan["kowasu"] is not None
    c = t.counts()
    four = c["4 値"]
    assert c["結果の台帳の行数"] == len(plan["kekka_rows"])    # type: ignore[arg-type]
    assert c["版の台帳の行数"] == len(plan["han_rows"])        # type: ignore[arg-type]
    assert c["差分の台帳の行数"] == len(plan["sabun_rows"])    # type: ignore[arg-type]
    assert sum(four.values()) == len(t.scopes)                 # type: ignore[union-attr]
    # 表が揃う前に止まったら 1 行も読まない。読んだなら結果と 1 対 1 で付く
    assert len(t.scopes) in (0, len(plan["kekka_rows"]))       # type: ignore[arg-type]
    assert {s.result for s in t.scopes} <= set(R.RESULTS)
    if t.scopes:
        assert four == 期待する4値(plan)

    # 当たったキーは、影響ありのときだけ 1 件以上付く
    for s in t.scopes:
        if s.result == R.RESULTS[0]:
            assert s.hit and set(s.hit) <= set(s.row.keys)
            assert s.why == ""
        elif s.result == R.RESULTS[1]:
            assert s.hit == () and s.why == ""
        else:
            assert s.hit == () and s.why in R.UNDECIDED

    if expect_stop:
        event("(b) 止まった")
        assert t.report.ok is False
        assert t.report.pending
        assert {p.reason for p in t.report.pending} <= set(R.STOP_REASONS)
        for call in (lambda: t.verdict, t.judgement_bytes, t.sha256):
            with pytest.raises(RuntimeError):
                call()
    else:
        event("(a) 読んだ")
        assert t.report.ok is True
        assert four[R.RESULTS[3]] == 0                          # type: ignore[index]
        # 決まらない理由別の合計 = 決まらないの件数
        assert sum(t.by_why().values()) == four[R.RESULTS[2]]   # type: ignore[index]
        body = t.judgement_bytes().decode("utf-8")
        for word in (t.read_at, t.host, "読んだ時刻", "2026-"):
            assert word not in body
        # 結果の台帳の行順を入れ替えても同じバイト列
        again = R.scope(ledger.swapped(ledger.swap or "逆順"), versions, diffs)
        assert again.sha256() == t.sha256()
        assert again.judgement_bytes() == t.judgement_bytes()

    # どちらの場合も入力は 1 文字も書き換わらない
    assert R.Ledger.parse(kekka).items == ledger.items         # type: ignore[arg-type]
    assert R.Versions.parse(han).items == versions.items       # type: ignore[arg-type]
    assert R.Diffs.parse(sabun).items == diffs.items           # type: ignore[arg-type]


@settings(max_examples=300, derandomize=True, database=None)
@given(han_date=st.sampled_from(DATES), issued=st.sampled_from(DATES),
       coverage=st.sampled_from(R.COVERAGES))
def test_日付を振り直しても判定部分は動かない(han_date: str, issued: str,
                                              coverage: str) -> None:
    """版の日付も出した日も、判定部分のバイト列に入らない(突き合わせに使わない)。

    同じ 3 枚の台帳で日付の欄だけを振り直す。鎖は指紋の親子だけで組むので、鎖の形も 4 値も
    指紋も動かない。動くのは全件 / 見本だけの宣言を書き換えたときだけだ。
    """
    v1, v2 = POOL[0], POOL[1]
    key = KEYS[0]
    han = "\n".join([",".join(R.HAN_COLUMNS),
                     f"{v1},{han_date},,{SOURCE}",
                     f"{v2},2026-05-11,{v1},{SOURCE}"])
    sabun = "\n".join([",".join(R.SABUN_COLUMNS),
                       f"{v1},{v2},{key},{R.CHANGES[2]},{coverage},{SOURCE}"])
    kekka = "\n".join([",".join(R.KEKKA_COLUMNS),
                       f"R01,合成の区分1,合成の項目(架空),{v1},{key},{issued},"
                       f"{SOURCE},逆順"])
    t = R.scope(R.Ledger.parse(kekka), R.Versions.parse(han), R.Diffs.parse(sabun))
    assert t.report.ok
    # 全件なら 影響あり、見本だけなら 決まらない。どちらも日付には依らない
    want = R.RESULTS[0] if coverage == R.COVERAGES[0] else R.RESULTS[2]
    assert t.scopes[0].result == want
    assert t.chain is not None and t.chain.order == (v1, v2)
    base = "\n".join([",".join(R.HAN_COLUMNS),
                      f"{v1},{DATES[0]},,{SOURCE}",
                      f"{v2},2026-05-11,{v1},{SOURCE}"])
    base_kekka = "\n".join([",".join(R.KEKKA_COLUMNS),
                            f"R01,合成の区分1,合成の項目(架空),{v1},{key},{DATES[0]},"
                            f"{SOURCE},逆順"])
    same = R.scope(R.Ledger.parse(base_kekka), R.Versions.parse(base),
                   R.Diffs.parse(sabun))
    assert same.judgement_bytes() == t.judgement_bytes()
