"""cadence_gap の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 読んだ範囲は 2 通りしかない。
  (a) 問い 1 件ごとに 6 値のどれか 1 つが付き、**6 値の合計 = 問いの数**、**5 値の合計 =
      鮮度候補の数**、**数表ごとの内訳の合計 = 問いの数**、**日数まで出せた件数 = 日数を
      出せる条件がそろった問い(= 中身が動いた最後の日も周期の宣言も在る問い)の数**で、
      **落ちた回と中身が動いた件数 0 の回は「中身が動いた最後の日」に出ず**、**基準日より
      後の実行は 3 つの日付のどれにも入らず**、
      **中身が動いた最後の日は走った最後の日より後にならず**、**宣言が無い数表には周期を
      当てず**、判定部分に絶対パスが入らず、3 枚の行順を入れ替えても同じバイト列になる
  (b) 1 件も数えずに理由コードが返る(数えた問いや指紋を取りに行くと例外)
どちらの場合も、この部品は 3 枚の表を 1 文字も書き換えない。

数表を 1〜3 つ、周期を 3 通り、実行を 0〜2 回ずつ、問いを 1〜3 件引く。実行の結果と中身が
動いた件数と指紋を引くので、宣言どおり・遅れている・一度も動いていないが混ざり、宣言表と
履歴表の載せ方を引くので「宣言が無い」と「履歴が無い」も混ざる。基準日は 5 通りから引くので
「基準日より前の実行が無い」も出る。3 割くらいの確率でどこか 1 か所を崩す(出典を空にする /
落ちた回に中身が動いた件数を入れる / 中身が動いた回の指紋を空にする / 落ちた回に指紋を入れる /
同じ数表 id を宣言表に 2 行書く / 周期を 0 にする / 問いの数表 id をどちらの表にも無い id に
する)。derandomize=True で毎回同じ入力列を使い、database=None で例を保存しない。

**6 値の分け方はテストの側で別に実装している**(部品の judge / six を呼ばない)。
2 本目は「落ちた回と差分 0 の回は中身が動いた最後の日に出ない」ことだけを、総当たりで見ている。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from hypothesis import event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import cadence_gap as H  # noqa: E402

SOURCE = "合成の出典メモ(架空)L1"
OK, FAILED = H.OK, H.FAILED
ARU, NASHI = H.AUTO
DATES = ("2026-05-01", "2026-05-08", "2026-05-15", "2026-05-22", "2026-06-01")
CYCLES = ("1", "7", "30")
FINGERPRINTS = ("fp1", "fp2")

KOWASHIKATA = ("出典を空にする", "落ちた回に中身が動いた件数を入れる",
               "中身が動いた回の指紋を空にする", "落ちた回に指紋を入れる",
               "同じ数表 id を宣言表に 2 行書く", "周期を 0 にする",
               "問いの数表 id をどちらの表にも無い id にする")


def classify(sengen: list[list[str]], rireki: list[list[str]],
             toi: list[list[str]]) -> list[tuple[str, str]]:
    """問いごとの (鍵, 6 値) をテストの側で別に出す(部品を呼ばない)。"""
    cycle = {r[0]: int(r[1]) for r in sengen}
    runs: dict[str, list[list[str]]] = {}
    for r in rireki:
        runs.setdefault(r[1], []).append(r)
    out: list[tuple[str, str]] = []
    for table_id, asof, _source, _swap in toi:
        here = sorted(runs.get(table_id, []), key=lambda r: (r[2], r[0]))
        upto = [r for r in here if r[2] <= asof]
        moved = [r for r in upto if r[3] == OK and int(r[4]) > 0]
        key = f"{table_id}@{asof}"
        if table_id not in cycle:
            out.append((key, "宣言が無い"))
        elif not here:
            out.append((key, "履歴が無い"))
        elif not upto:
            out.append((key, "基準日より前の実行が無い"))
        elif not moved:
            out.append((key, "一度も動いていない"))
        else:
            gap = H.day_number(asof) - H.day_number(moved[-1][2])
            out.append((key, "遅れている" if gap > cycle[table_id] else "宣言どおり"))
    return sorted(out)


@st.composite
def 合成の3枚(draw: st.DrawFn) -> dict[str, object]:
    """周期の宣言表 / 実行の履歴表 / 問いの一覧(と崩し方)を作る。"""
    tables = [f"D{i + 1}" for i in range(draw(st.integers(1, 3)))]

    sengen: list[list[str]] = []
    for table_id in tables:
        if table_id == "D1" or draw(st.booleans()):   # 1 行目は必ず置く
            sengen.append([table_id, draw(st.sampled_from(CYCLES)),
                           draw(st.sampled_from(H.AUTO)), SOURCE, SOURCE, "", ""])

    rireki: list[list[str]] = []
    for table_id in tables:
        for k in range(draw(st.integers(0, 2))):
            result = draw(st.sampled_from(H.RUN_RESULTS))
            moved = draw(st.sampled_from(("0", "1", "2"))) if result == OK else "0"
            fp = "" if result == FAILED else draw(st.sampled_from(FINGERPRINTS))
            rireki.append([f"R{table_id[1:]}{k + 1}", table_id,
                           draw(st.sampled_from(DATES)), result, moved, fp, SOURCE])
    if not rireki:                     # 0 行の表は読めないので 1 回は置く
        rireki.append(["R11", "D1", DATES[0], OK, "1", FINGERPRINTS[0], SOURCE])

    # 問いは、宣言表か履歴表のどちらかに出てくる数表だけから引く(宛先の無い問いは崩し方で試す)
    asked_from = sorted({r[0] for r in sengen} | {r[1] for r in rireki})
    asked = draw(st.lists(st.tuples(st.sampled_from(asked_from),
                                    st.sampled_from(DATES)),
                          min_size=1, max_size=3, unique=True))
    toi = [[table_id, asof, SOURCE, ""] for table_id, asof in sorted(asked)]
    toi[0][3] = H.SWAPS[0]

    kowasu = draw(st.sampled_from([None] * 16 + list(KOWASHIKATA)))
    if kowasu == "出典を空にする":
        sengen[0][3] = ""
    elif kowasu == "落ちた回に中身が動いた件数を入れる":
        rireki[0][3], rireki[0][4], rireki[0][5] = FAILED, "2", FINGERPRINTS[0]
    elif kowasu == "中身が動いた回の指紋を空にする":
        rireki[0][3], rireki[0][4], rireki[0][5] = OK, "1", ""
    elif kowasu == "落ちた回に指紋を入れる":
        rireki[0][3], rireki[0][4], rireki[0][5] = FAILED, "0", FINGERPRINTS[1]
    elif kowasu == "同じ数表 id を宣言表に 2 行書く":
        sengen.append([sengen[0][0], "7", ARU, SOURCE, SOURCE, "", ""])
    elif kowasu == "周期を 0 にする":
        sengen[0][1] = "0"
    elif kowasu == "問いの数表 id をどちらの表にも無い id にする":
        toi[0][0] = "D9"

    def csv(head: tuple[str, ...], body: list[list[str]]) -> str:
        return "\n".join([",".join(head)] + [",".join(r) for r in body])

    return {"sengen": csv(H.SENGEN_COLUMNS, sengen),
            "rireki": csv(H.RIREKI_COLUMNS, rireki),
            "toi": csv(H.TOI_COLUMNS, toi),
            "sengen_rows": sengen, "rireki_rows": rireki, "toi_rows": toi,
            "kowasu": kowasu}


@settings(max_examples=200, derandomize=True, database=None, deadline=None)
@given(plan=合成の3枚())
def test_いつも成り立つこと_数えた問いか理由コードか(plan: dict[str, object]) -> None:
    decls = H.Declarations.parse(plan["sengen"])     # type: ignore[arg-type]
    runs = H.Runs.parse(plan["rireki"])              # type: ignore[arg-type]
    questions = H.Questions.parse(plan["toi"])       # type: ignore[arg-type]
    t = H.cadence_gap(decls, runs, questions)

    expect_stop = plan["kowasu"] is not None
    c = t.counts()
    six = c["6 値"]
    assert c["周期の宣言表の行数"] == len(plan["sengen_rows"])   # type: ignore[arg-type]
    assert c["実行の履歴表の行数"] == len(plan["rireki_rows"])   # type: ignore[arg-type]
    assert c["問いの数"] == len(plan["toi_rows"])                # type: ignore[arg-type]
    assert {j.result for j in t.judged} <= set(H.KEKKA)
    assert all(isinstance(v, int) for v in six.values())        # type: ignore[union-attr]

    if expect_stop:
        event("(b) 1 件も数えずに止まった")
        assert t.report.ok is False and t.report.pending
        assert {p.reason for p in t.report.pending} <= set(H.TABLE_REASONS)
        assert t.judged == ()
        assert six == {k: 0 for k in H.KEKKA}
        assert t.denominator == 0 and t.dated_count() == 0
        for call in (t.judgement_bytes, t.sha256):
            with pytest.raises(RuntimeError):
                call()
    else:
        event("(a) 数えた")
        assert t.report.ok is True
        # 問い 1 件ごとに 6 値のどれか 1 つ。テスト側の別実装と一致する
        mine = sorted((j.question.key, j.result) for j in t.judged)
        assert mine == classify(plan["sengen_rows"], plan["rireki_rows"],
                                plan["toi_rows"])
        # 4 通りの数え方が全て合う
        assert sum(six.values()) == t.question_denominator()
        assert sum(six[k] for k in H.GOCHI) == t.denominator
        rows = t.by_table()
        assert sum(int(r["問いの数"]) for r in rows) == t.question_denominator()
        for k in H.KEKKA:
            assert sum(int(r["6 値"][k]) for r in rows) == six[k]
        assert t.dated_count() == t.datable_count()
        assert len(t.dates()) == t.question_denominator()
        declared = {r[0] for r in plan["sengen_rows"]}   # type: ignore[union-attr]
        for j in t.judged:
            # 宣言が無い数表に周期を当てない(日数の欄が空のまま返る)
            if j.question.table_id not in declared:
                assert j.result == "宣言が無い"
                assert j.gap_days is None and j.over_days is None
            # 基準日より後の実行は 3 つの日付のどれにも入らない
            for day in (j.ran_last, j.moved_last, j.ok_last):
                assert (not day) or day <= j.question.asof
            # 落ちた回と中身が動いた件数 0 の回は、中身が動いた最後の日に出ない
            if j.moved_last:
                hit = [r for r in runs.upto(j.question.table_id, j.question.day)
                       if r.ran_on == j.moved_last]
                assert any(r.counted_as_moved for r in hit)
                assert j.moved_last <= j.ran_last and j.ok_last <= j.ran_last
                assert j.moved_last <= j.ok_last
            # 日数が出るのは、中身が動いた最後の日が在り、周期の宣言も在る問いだけ
            assert (j.gap_days is not None) == (bool(j.moved_last)
                                                and j.question.table_id in declared)
            if j.gap_days is not None:
                assert j.gap_days >= 0 and j.over_days >= 0
        body = t.judgement_bytes().decode("utf-8")
        for word in ("読んだ条件", "絶対パス", str(ROOT)):
            assert word not in body
        how = questions.swap or H.SWAPS[0]
        again = H.cadence_gap(decls.swapped(how), runs.swapped(how),
                              questions.swapped(how))
        assert again.sha256() == t.sha256()
        assert again.judgement_bytes() == t.judgement_bytes()

    # どちらの場合も入力は 1 文字も書き換わらない
    assert H.Declarations.parse(plan["sengen"]).items == decls.items  # type: ignore[arg-type]
    assert H.Runs.parse(plan["rireki"]).items == runs.items           # type: ignore[arg-type]
    assert H.Questions.parse(plan["toi"]).items == questions.items    # type: ignore[arg-type]


@settings(max_examples=300, derandomize=True, database=None)
@given(result=st.sampled_from(H.RUN_RESULTS), moved=st.sampled_from(("0", "1")),
       second=st.sampled_from(DATES[:3]), cycle=st.sampled_from(CYCLES))
def test_落ちた回と差分0の回は中身が動いた日に出ない(result: str, moved: str,
                                                      second: str,
                                                      cycle: str) -> None:
    """2 回目の実行が落ちた回か差分 0 の回なら、中身が動いた最後の日は 1 回目に残る。

    走った最後の日と落ちた回を除いた最後の日は別の列なので、2 回目の結果によって動き方が
    違う(落ちた回なら落ちた回を除いた最後の日も 1 回目に戻り、差分 0 なら 2 回目のまま)。
    """
    if result == FAILED:
        moved = "0"
    fp = "" if result == FAILED else FINGERPRINTS[1]
    sengen = "\n".join([",".join(H.SENGEN_COLUMNS),
                        f"D1,{cycle},{ARU},{SOURCE},{SOURCE},,"])
    rireki = "\n".join([",".join(H.RIREKI_COLUMNS),
                        f"R1,D1,{DATES[0]},{OK},3,{FINGERPRINTS[0]},{SOURCE}",
                        f"R2,D1,{second},{result},{moved},{fp},{SOURCE}"])
    toi = "\n".join([",".join(H.TOI_COLUMNS),
                     f"D1,{DATES[3]},{SOURCE},{H.SWAPS[0]}"])
    t = H.cadence_gap(H.Declarations.parse(sengen), H.Runs.parse(rireki),
                      H.Questions.parse(toi))
    assert t.report.ok
    j = t.judged[0]
    assert j.ran_last == max(DATES[0], second)
    if result == OK and moved != "0":
        assert j.moved_last == max(DATES[0], second)
    else:
        assert j.moved_last == DATES[0]            # 1 回目に残る
    assert j.ok_last == (max(DATES[0], second) if result == OK else DATES[0])
    assert j.gap_days == H.day_number(DATES[3]) - H.day_number(j.moved_last)
    assert j.over_days == max(0, j.gap_days - int(cycle))
    assert j.result == ("遅れている" if j.over_days > 0 else "宣言どおり")
    assert t.question_denominator() == 1 and sum(t.six().values()) == 1
