"""run_kinds の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 読んだ範囲は 2 通りしかない。
  (a) 実行 1 回ごとに 6 値 + 別枠 2 種のどれか 1 つが付き、**8 値の合計 = 実行の件数**、
      **6 値の合計 = 6 値が付いた回の数**、**status 語ごとの内訳の合計 = 実行の件数**(値ごとの
      内訳の合計も一致)で、**据え置きを伴う語の回には差分と指紋の判定が付かず**(直前の指紋も
      戻りの印も空)、**① に入るのは意味が 試験 として登録された意図コードが 実行より前 と
      宣言された回だけ**で、**差分 0 かつ指紋が直前と同じ回に戻りの印が付かず**、**指紋の欄が
      空の回は履歴に入らず**、判定部分に絶対パスが入らず、3 枚の行順を 3 通りに入れ替えても
      同じバイト列になる
  (b) 1 回も数えずに理由コードが返る(仕分けた回や指紋を取りに行くと例外)
どちらの場合も、この部品は 3 枚の表を 1 文字も書き換えない。

実行を 1〜5 回、status の語を 3 通り(登録表に在る 2 つ + 無い 1 つ)、差分の件数を 0〜2 から
3 欄ぶん、指紋を小さな値の集まりと空欄から、意図の宣言を 4 通り(無し / 試験 × 前・後 /
試験でない)引く。3 割くらいの確率でどこか 1 か所を崩す(9 通りで、1 回も数えずに止まる理由
コード 9 個すべてに道が付く。並び順の番号を飛ばす崩し方は初回の印の位置も同時にずれるので、
1 枚で 2〜3 個の理由コードが同時に出る)。derandomize=True で毎回同じ入力列を使い、
database=None で例を保存しない。

**6 値 + 別枠の分け方はテストの側で別に実装している**(部品の judge / six を呼ばない)。
2 本目は「① と ② の分かれ目は事前の宣言だけで、据え置きの回に差分と指紋の判定が付かない」ことを、
status × 差分 × 指紋 × 宣言 の総当たりで見る。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from hypothesis import event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import run_kinds as H  # noqa: E402

SOURCE = "合成の実行のメモ(架空)L1"
PLAN_SRC = "合成の計画のメモ(架空)L1"
WORD_SRC = "合成の登録のメモ(架空)L1"

OK, FAILED, UNREG = "ok", "failed", "合成の未登録の語(架空)"
SHIKEN_CODE, TORIKOMI = "失敗試験", "仕様変更の取り込み"
MITOUROKU_CODE = "合成の未登録の意図(架空)"

FPS = ("fp1", "fp2", "fp3")

WORDS_ROWS = [[OK, H.TOTTA, H.SUEOKANAI, WORD_SRC],
              [FAILED, H.OCHITA, H.SUEOKI, WORD_SRC],
              [SHIKEN_CODE, H.SHIKEN, H.SUEOKI, WORD_SRC],
              [TORIKOMI, H.SHIKEN_DENAI, H.SUEOKANAI, WORD_SRC]]
MEANING = {OK: (H.TOTTA, H.SUEOKANAI), FAILED: (H.OCHITA, H.SUEOKI)}
IS_TEST = {SHIKEN_CODE: True, TORIKOMI: False}

KOWASHIKATA = ("出典を空にする", "同じ実行 id を台帳に 2 行書く",
               "並び順の番号を飛ばす", "初回の印を 2 行目にも付ける",
               "据え置きの回に差分の件数を書く", "通った回の指紋を空にする",
               "同じ実行 id に 2 通りの意図コードを書く",
               "登録表に無い意図コードを宣言する", "初回の印を外す")


def classify(runs: list[list[str]], intents: list[list[str]]) \
        -> list[tuple[str, str]]:
    """回ごとの (実行 id, 8 値) をテストの側で別に出す(部品を呼ばない)。"""
    declared = {row[0]: (row[1], row[2]) for row in intents}
    out: list[tuple[str, str]] = []
    previous = ""
    for row in sorted(runs, key=lambda r: int(r[1])):
        status, fingerprint = row[2], row[7]
        diff = sum(int(row[k]) for k in (3, 4, 5))
        if status not in MEANING:
            out.append((row[0], "登録表に無い status 語"))
        elif MEANING[status][1] == H.SUEOKI:
            if fingerprint:
                out.append((row[0], "落ちたのに指紋が動いた"))
            else:
                code, when = declared.get(row[0], ("", ""))
                if IS_TEST.get(code, False) and when == H.MAE:
                    out.append((row[0], "据え置き・試験と事前に宣言されている"))
                else:
                    out.append((row[0], "据え置き・試験の事前の宣言が無い"))
        elif row[6] == H.SHOKAI:
            out.append((row[0], "初回(比べる相手が無い)"))
        elif diff == 0 and fingerprint == previous:
            out.append((row[0], "差分 0 かつ指紋が直前と同じ"))
        elif diff and fingerprint != previous:
            out.append((row[0], "差分ありかつ指紋が直前と違う"))
        else:
            out.append((row[0], "差分の件数と指紋の動きが噛み合わない"))
        if fingerprint:
            previous = fingerprint
    return sorted(out)


@st.composite
def 合成の3枚(draw: st.DrawFn) -> dict[str, object]:
    """実行の台帳 / 意図の宣言表 / 語の登録表(と崩し方)を作る。"""
    n = draw(st.integers(1, 5))
    runs: list[list[str]] = [
        # 1 回目は必ず 通った + 初回の印 + 指紋あり(比べる相手の無い回を 1 つ残す)
        ["R01", "1", OK, str(draw(st.integers(0, 2))), "0", "0", H.SHOKAI,
         FPS[0], SOURCE]]
    for k in range(2, n + 1):
        status = draw(st.sampled_from((OK, OK, FAILED, UNREG)))
        fingerprint = draw(st.sampled_from(FPS)) if status == OK \
            else draw(st.sampled_from(("", "", *FPS)))
        counts = ["0", "0", "0"] if status == FAILED else \
            [str(draw(st.integers(0, 2))) for _ in range(3)]
        runs.append([f"R{k:02d}", str(k), status, counts[0], counts[1], counts[2],
                     "", fingerprint, SOURCE])

    intents: list[list[str]] = []
    for row in runs:
        pick = draw(st.sampled_from((None, None, (SHIKEN_CODE, H.MAE),
                                     (SHIKEN_CODE, H.ATO), (TORIKOMI, H.MAE))))
        if pick is not None:
            intents.append([row[0], pick[0], pick[1], PLAN_SRC])
    # 台帳に無い実行 id を指す宣言(= 逆向きの欠け。止まらずに一覧へ出る)
    if draw(st.booleans()):
        intents.append(["R99", SHIKEN_CODE, H.MAE, PLAN_SRC])

    kowasu = draw(st.sampled_from([None] * 21 + list(KOWASHIKATA)))
    if kowasu == KOWASHIKATA[0]:
        runs[0][8] = ""
    elif kowasu == KOWASHIKATA[1]:
        runs.append(["R01", str(n + 1), FAILED, "0", "0", "0", "", "", SOURCE])
    elif kowasu == KOWASHIKATA[2]:
        runs[0][1] = str(n + 2)
    elif kowasu == KOWASHIKATA[3]:
        runs.append([f"R{n + 1:02d}", str(n + 1), OK, "0", "0", "0", H.SHOKAI,
                     FPS[0], SOURCE])
    elif kowasu == KOWASHIKATA[4]:
        runs.append([f"R{n + 1:02d}", str(n + 1), FAILED, "1", "0", "0", "", "",
                     SOURCE])
    elif kowasu == KOWASHIKATA[5]:
        runs.append([f"R{n + 1:02d}", str(n + 1), OK, "0", "0", "0", "", "",
                     SOURCE])
    elif kowasu == KOWASHIKATA[6]:
        intents = [x for x in intents if x[0] != "R01"]
        intents.extend([["R01", SHIKEN_CODE, H.MAE, PLAN_SRC],
                        ["R01", TORIKOMI, H.MAE, PLAN_SRC]])
    elif kowasu == KOWASHIKATA[7]:
        intents.append([f"R{n + 1:02d}", MITOUROKU_CODE, H.MAE, PLAN_SRC])
        runs.append([f"R{n + 1:02d}", str(n + 1), FAILED, "0", "0", "0", "", "",
                     SOURCE])
    elif kowasu == KOWASHIKATA[8]:
        runs[0][6] = ""

    def csv(head: tuple[str, ...], body: list[list[str]]) -> str:
        return "\n".join([",".join(head)] + [",".join(r) for r in body])

    return {"runs": csv(H.RUNS_COLUMNS, runs),
            "intents": csv(H.INTENT_COLUMNS, intents),
            "words": csv(H.WORDS_COLUMNS, WORDS_ROWS),
            "runs_rows": runs, "intents_rows": intents, "kowasu": kowasu}


@settings(max_examples=200, derandomize=True, database=None, deadline=None)
@given(plan=合成の3枚())
def test_いつも成り立つこと_仕分けた回か理由コードか(plan: dict[str, object]) -> None:
    runs = H.Runs.parse(plan["runs"])            # type: ignore[arg-type]
    intents = H.Intents.parse(plan["intents"])   # type: ignore[arg-type]
    words = H.Words.parse(plan["words"])         # type: ignore[arg-type]
    t = H.run_kinds(runs, intents, words)

    expect_stop = plan["kowasu"] is not None
    c = t.counts()
    eight = c["6 値 + 別枠"]
    assert c["実行の台帳の行数"] == len(plan["runs_rows"])        # type: ignore[arg-type]
    assert c["意図の宣言表の行数"] == len(plan["intents_rows"])   # type: ignore[arg-type]
    assert c["語の登録表の行数"] == len(WORDS_ROWS)
    assert {j.result for j in t.judged} <= set(H.KEKKA)
    assert all(isinstance(v, int) for v in eight.values())    # type: ignore[union-attr]

    if expect_stop:
        event("(b) 1 回も数えずに止まった")
        assert t.report.ok is False and t.report.pending
        assert {p.reason for p in t.report.pending} <= set(H.TABLE_REASONS)
        assert t.judged == ()
        assert eight == {k: 0 for k in H.KEKKA}
        assert t.counted_denominator == 0 and t.aside_denominator() == 0
        assert t.returns() == [] and t.mismatched() == [] and t.asides() == []
        assert t.no_declaration() == []
        for call in (t.judgement_bytes, t.sha256):
            with pytest.raises(RuntimeError):
                call()
    else:
        event("(a) 仕分けた")
        assert t.report.ok is True
        # 回 1 つごとに 8 値のどれか 1 つ。テスト側の別実装と一致する
        mine = sorted((j.run.run_id, j.result) for j in t.judged)
        assert mine == classify(plan["runs_rows"],      # type: ignore[arg-type]
                                plan["intents_rows"])   # type: ignore[arg-type]
        # 3 通りの数え方が全て合う
        assert sum(eight.values()) == t.run_denominator()
        assert sum(eight[k] for k in H.MUTSU) == t.counted_denominator
        rows = t.by_status()
        assert sum(int(r["回の数"]) for r in rows) == t.run_denominator()
        for k in H.KEKKA:
            assert sum(int(r["6 値 + 別枠"][k]) for r in rows) == eight[k]
        # 据え置きを伴う語の回には差分と指紋の判定が付かない
        for j in t.judged:
            if j.result in (H.KEKKA[0], H.KEKKA[1]):
                assert j.run.fingerprint == "" and j.run.diff_total == 0
                assert j.previous == "" and j.returned is False
                assert words.status_of(j.run.status).holding is True
            if j.result == H.KEKKA[0]:      # ① は事前の宣言が在る回だけ
                x = intents.of(j.run.run_id)
                assert x is not None and x.before
                assert words.intent_of(x.intent).is_test is True
            if j.result == H.KEKKA[1]:      # ② は言い方の違いを必ず持つ
                assert j.nashi in H.NASHI_KINDS
            if j.result == H.KEKKA[3]:      # ④ に戻りの印は付かない
                assert j.returned is False
                assert j.run.fingerprint == j.previous
            if j.result == H.KEKKA[7]:      # 別枠 = 落ちたのに指紋が動いた
                assert j.run.fingerprint != ""
            if j.result == H.KEKKA[6]:      # 別枠 = 登録表に無い status 語
                assert words.status_of(j.run.status) is None
        # 指紋の欄が空の回は履歴に入らない(直前として数えられない)
        kept = [j.run.fingerprint for j in t.judged if j.run.fingerprint]
        for j in t.judged:
            if j.previous:
                assert j.previous in kept
        # ② の一覧の件数が、② の件数と合う
        assert len(t.no_declaration()) == eight[H.KEKKA[1]]
        assert len(t.mismatched()) == eight[H.KEKKA[5]]
        assert len(t.asides()) == eight[H.KEKKA[6]] + eight[H.KEKKA[7]]
        body = t.judgement_bytes().decode("utf-8")
        for word in ("読んだ条件", "絶対パス", str(ROOT)):
            assert word not in body
        # 3 枚の行順を 3 通りに入れ替えても同じバイト列
        for how in H.SWAPS:
            again = H.run_kinds(runs.swapped(how), intents.swapped(how),
                                words.swapped(how))
            assert again.judgement_bytes() == t.judgement_bytes()
            assert again.sha256() == t.sha256()

    # どちらの場合も入力は 1 文字も書き換わらない
    assert H.Runs.parse(plan["runs"]).items == runs.items          # type: ignore[arg-type]
    assert H.Intents.parse(plan["intents"]).items == intents.items  # type: ignore[arg-type]
    assert H.Words.parse(plan["words"]).items == words.items       # type: ignore[arg-type]


@settings(max_examples=300, derandomize=True, database=None)
@given(status=st.sampled_from((OK, FAILED, UNREG)),
       added=st.integers(0, 2), fingerprint=st.sampled_from(("", *FPS)),
       declaration=st.sampled_from((None, (SHIKEN_CODE, H.MAE),
                                    (SHIKEN_CODE, H.ATO), (TORIKOMI, H.MAE),
                                    (TORIKOMI, H.ATO))))
def test_据え置きの回は宣言だけで分かれる(status: str, added: int,
                                          fingerprint: str,
                                          declaration: tuple[str, str] | None) -> None:
    """status × 差分 × 指紋 × 宣言 の総当たり。

    **① に入るのは「落ちたと宣言され、指紋が空で、意味が 試験 の意図コードが 実行より前 と
    宣言された回」だけ。** 事後の宣言と、試験でない意図と、宣言そのものが無い回は、どれも ②
    に入って言い方だけが違う。通った回と登録表に無い語の回は、宣言が在っても ① にも ② にも
    入らない。
    """
    held = status == FAILED
    if held:
        added = 0           # 据え置きの回に差分を書くと止まるので、ここでは 0 に置く
    rows = [["R01", "1", OK, "1", "0", "0", H.SHOKAI, FPS[0], SOURCE],
            ["R02", "2", status, str(added), "0", "0", "",
             fingerprint if (status != OK or fingerprint) else FPS[1], SOURCE]]
    intents = [["R02", declaration[0], declaration[1], PLAN_SRC]] \
        if declaration else []
    t = H.run_kinds(H.Runs.parse("\n".join(
        [",".join(H.RUNS_COLUMNS)] + [",".join(r) for r in rows])),
        H.Intents.parse("\n".join(
            [",".join(H.INTENT_COLUMNS)] + [",".join(r) for r in intents])),
        H.Words.parse("\n".join(
            [",".join(H.WORDS_COLUMNS)] + [",".join(r) for r in WORDS_ROWS])))
    assert t.report.ok, [p.as_dict() for p in t.report.pending]
    j = next(x for x in t.judged if x.run.run_id == "R02")
    if status == UNREG:
        assert j.result == H.KEKKA[6]
    elif held and fingerprint:
        assert j.result == H.KEKKA[7]
    elif held:
        test_before = declaration is not None and declaration[0] == SHIKEN_CODE \
            and declaration[1] == H.MAE
        assert j.result == (H.KEKKA[0] if test_before else H.KEKKA[1])
        if not test_before:
            if declaration is None:
                assert j.nashi == H.NASHI_KINDS[0]
            elif declaration[1] == H.ATO:
                assert j.nashi == H.NASHI_KINDS[1]
            else:
                assert j.nashi == H.NASHI_KINDS[2]
    else:
        assert j.result in (H.KEKKA[3], H.KEKKA[4], H.KEKKA[5])
        assert j.nashi == ""
    assert sum(t.six().values()) == 2 == t.run_denominator()
    assert t.counted_denominator + t.aside_denominator() == 2
