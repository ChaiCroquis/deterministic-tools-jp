"""blank_kind の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 読んだ結果は 2 通りしかない。
  (a) マスごとに 4 値が 1 つだけ付き、4 値の合計が対象 × 項目 の総数に等しく、空欄の意味は
      宣言された理由コードと列の種類からだけ付き、理由コード別の件数の合計 + 理由コードの
      無い行の件数が総数に等しく、判定部分に時刻・ホスト名・絶対パスが入らず、値の表の
      行順を入れ替えても同じバイト列になる
  (b) 1 マスも読まずに理由コードが返る(結果や指紋を取りに行くと例外)
どちらの場合も、この部品は値の表も項目の宣言も理由コードの宣言も 1 文字も書き換えない。

対象を 1〜3、項目を 1〜3、各マスを「値」か「空欄 + 許された理由コード」で振る。さらに
3 割くらいの確率で 1 か所だけ崩す(理由コードを空にする / 許さないコードを書く / 1 マス落とす /
出典を空にする / 0 の扱いを空にする / 列の種類を空にする / 値の種類を空にする /
全部に当たる列に値扱いのコードも許す / 宣言に無い項目の行を足す)。derandomize=True で毎回
同じ入力列を使い、database=None で見つけた例を保存しない。

**4 値はテストの側で別に組み立てている**(部品の分類を呼ばず、fixture の行と宣言から直に
決める)。
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import blank_kind as B  # noqa: E402

SOURCE = "合成の出典メモ(架空)L1"
VALUE_POOL = ("0", "1", "100")
# 合成の理由コード。返し方だけが違う 3 つ
CODES = (("合成のコードA(架空)", B.HOWS[0]),
         ("合成のコードB(架空)", B.HOWS[1]),
         ("合成のコードC(架空)", B.HOWS[2]))
WILDCARD = CODES[1][0]

KOWASHIKATA = ("理由コードを空にする", "許さないコードを書く", "1 マス落とす",
               "出典を空にする", "0 の扱いを空にする", "列の種類を空にする",
               "値の種類を空にする", "全部に当たる列に値扱いのコードも許す",
               "宣言に無い項目の行を足す")


@st.composite
def 合成の表(draw: st.DrawFn) -> dict[str, object]:
    """値の表 / 項目の宣言 / 理由コードの宣言(と崩し方)を作る。"""
    targets = [f"合成の区分{n}" for n in range(1, draw(st.integers(1, 3)) + 1)]
    koumoku: list[list[str]] = []
    for n in range(1, draw(st.integers(1, 3)) + 1):
        item = f"合成の列{n}(架空)"
        all_match = draw(st.booleans())
        if all_match:
            allowed = [WILDCARD]            # 全部に当たる列は 1 つの意味しか持てない
        else:
            allowed = draw(st.lists(st.sampled_from([c for c, _ in CODES]),
                                    min_size=1, max_size=3, unique=True))
        koumoku.append([item, draw(st.sampled_from(B.KINDS)),
                        B.REASON_SEP.join(allowed),
                        B.HAI if draw(st.booleans()) else B.IIE,
                        B.HAI if all_match else B.IIE, SOURCE])

    rows: list[list[str]] = []
    for t in targets:
        for k in koumoku:
            item, allowed = k[0], [c for c in k[2].split(B.REASON_SEP) if c]
            if draw(st.booleans()):
                rows.append([t, item, draw(st.sampled_from(VALUE_POOL)), "", SOURCE, ""])
            else:
                rows.append([t, item, "", draw(st.sampled_from(allowed)), SOURCE, ""])
    rows[0][5] = "逆順"

    riyuu = [[c, f"{c} の意味", how, SOURCE] for c, how in CODES]

    kowasu = draw(st.sampled_from([None] * 7 + list(KOWASHIKATA)))
    if kowasu == "理由コードを空にする":
        rows[0][2], rows[0][3] = "", ""
    elif kowasu == "許さないコードを書く":
        spare = [c for c, _ in CODES
                 if c not in koumoku[0][2].split(B.REASON_SEP)]
        if spare:
            rows[0][2], rows[0][3] = "", spare[0]
        else:
            kowasu = None
    elif kowasu == "1 マス落とす":
        # 列が 2 つ以上あるときだけ(1 列だと対象ごと消えて、表としては揃ってしまう)
        if len(koumoku) >= 2:
            rows.pop()
        else:
            kowasu = None
    elif kowasu == "出典を空にする":
        rows[0][4] = ""
    elif kowasu == "0 の扱いを空にする":
        koumoku[0][3] = ""
    elif kowasu == "列の種類を空にする":
        koumoku[0][4] = ""
    elif kowasu == "値の種類を空にする":
        koumoku[0][1] = ""
    elif kowasu == "全部に当たる列に値扱いのコードも許す":
        wild = next((k for k in koumoku if k[4] == B.HAI), None)
        if wild is None:
            kowasu = None
        else:
            wild[2] = B.REASON_SEP.join([WILDCARD, CODES[0][0]])
    elif kowasu == "宣言に無い項目の行を足す":
        rows.append([targets[0], "合成の未登録の列(架空)", "1", "", SOURCE, ""])

    def csv(head: tuple[str, ...], body: list[list[str]]) -> str:
        return "\n".join([",".join(head)] + [",".join(r) for r in body])

    return {"atai": csv(B.ATAI_COLUMNS, rows), "koumoku": csv(B.KOUMOKU_COLUMNS, koumoku),
            "riyuu": csv(B.RIYUU_COLUMNS, riyuu), "rows": rows, "koumoku_rows": koumoku,
            "targets": targets, "kowasu": kowasu}


def 期待する4値(plan: dict[str, object]) -> dict[str, int]:
    """4 値を、行と宣言から直に組み立てる(部品の分類は呼ばない)。"""
    how = {c: h for c, h in CODES}
    decl = {k[0]: k for k in plan["koumoku_rows"]}          # type: ignore[union-attr]
    out = dict.fromkeys(B.RESULTS, 0)
    for target, item, value, reason, _source, _swap in plan["rows"]:  # type: ignore
        k = decl.get(item)
        if k is None:
            out[B.RESULTS[3]] += 1
        elif not reason:
            if not value:
                out[B.RESULTS[3]] += 1
            elif Decimal(value) == 0 and k[3] == B.IIE:
                out[B.RESULTS[2]] += 1
            else:
                out[B.RESULTS[0]] += 1
        elif reason not in [c for c in k[2].split(B.REASON_SEP) if c]:
            out[B.RESULTS[3]] += 1
        elif (how[reason] == B.HOWS[1]) == (k[4] == B.HAI):
            out[B.RESULTS[1]] += 1
        else:
            out[B.RESULTS[2]] += 1
    return out


@settings(max_examples=150, derandomize=True, database=None, deadline=None)
@given(plan=合成の表())
def test_いつも成り立つこと_読んだ結果か理由コードか(plan: dict[str, object]) -> None:
    atai, koumoku, riyuu = plan["atai"], plan["koumoku"], plan["riyuu"]
    sheet = B.Sheet.parse(atai)                                # type: ignore[arg-type]
    columns = B.Columns.parse(koumoku)                         # type: ignore[arg-type]
    reasons = B.Reasons.parse(riyuu)                           # type: ignore[arg-type]
    t = B.read(sheet, columns, reasons)

    expect_stop = plan["kowasu"] is not None
    c = t.counts()
    four = c["4 値"]
    assert c["値の表の行数"] == len(plan["rows"])               # type: ignore[arg-type]
    assert c["項目の宣言の行数"] == len(plan["koumoku_rows"])   # type: ignore[arg-type]
    assert c["対象の数"] == len({r[0] for r in plan["rows"]})   # type: ignore[union-attr]
    assert sum(four.values()) == len(t.reads)                   # type: ignore[union-attr]
    # 表が揃う前に止まったら 1 マスも読まない。読んだならマスと 1 対 1 で付く
    assert len(t.reads) in (0, len(plan["rows"]))               # type: ignore[arg-type]
    assert {r.result for r in t.reads} <= set(B.RESULTS)
    if t.reads:
        assert four == 期待する4値(plan)

    # 空欄の意味と返し方は、宣言された理由コードからだけ付く
    for r in t.reads:
        if r.result == B.RESULTS[1]:
            decl = reasons.of(r.cell.reason)
            assert decl is not None
            assert r.meaning == decl.meaning and r.how == decl.how
        else:
            assert r.meaning == "" and r.how == ""      # 片方を選んで返さない

    if expect_stop:
        event("(b) 止まった")
        assert t.report.ok is False
        assert t.report.pending
        assert {p.reason for p in t.report.pending} <= set(B.STOP_REASONS)
        for call in (lambda: t.verdict, t.judgement_bytes, t.sha256):
            with pytest.raises(RuntimeError):
                call()
    else:
        event("(a) 読んだ")
        assert t.report.ok is True
        assert four[B.RESULTS[3]] == 0                          # type: ignore[index]
        # 理由コード別の件数の合計 + 理由コードの無い行 = 対象 × 項目 の総数
        coded = sum(t.by_reason().values())
        plain = sum(1 for r in t.reads if not r.coded)
        assert coded + plain == t.grid.total == len(t.reads)
        body = t.judgement_bytes().decode("utf-8")
        for word in (t.read_at, t.host, "読んだ時刻", "絶対パス"):
            assert word not in body
        # 値の表の行順を入れ替えても同じバイト列
        again = B.read(sheet.swapped(sheet.swap or "逆順"), columns, reasons)
        assert again.sha256() == t.sha256()
        assert again.judgement_bytes() == t.judgement_bytes()

    # どちらの場合も入力は 1 文字も書き換わらない
    assert B.Sheet.parse(atai).items == sheet.items            # type: ignore[arg-type]
    assert B.Columns.parse(koumoku).items == columns.items     # type: ignore[arg-type]
    assert B.Reasons.parse(riyuu).items == reasons.items       # type: ignore[arg-type]


@settings(max_examples=300, derandomize=True, database=None)
@given(code=st.sampled_from([c for c, _ in CODES]), value=st.sampled_from(VALUE_POOL))
def test_列の種類を変えると同じ理由コードの空欄だけが入れ替わる(code: str,
                                                                value: str) -> None:
    """同じ空欄記号・同じ理由コードでも、列の種類の 1 欄で 空欄 ↔ 決まらない が入れ替わる。

    空欄の意味は部品が決めず、列の宣言と理由コードの宣言が決める。だから同じマスでも、
    その 1 欄を書き換えるだけで意味が付いたり決まらなくなったりする。
    """
    item = "合成の列1(架空)"
    riyuu = "\n".join([",".join(B.RIYUU_COLUMNS)]
                      + [f"{c},{c} の意味,{h},{SOURCE}" for c, h in CODES])
    atai = "\n".join([",".join(B.ATAI_COLUMNS),
                      f"合成の区分1,{item},,{code},{SOURCE},逆順",
                      f"合成の区分2,{item},{value},,{SOURCE},"])

    def pull(all_match: str) -> B.Table:
        koumoku = "\n".join([",".join(B.KOUMOKU_COLUMNS),
                             f"{item},金額,{code},{B.HAI},{all_match},{SOURCE}"])
        return B.read(B.Sheet.parse(atai), B.Columns.parse(koumoku),
                      B.Reasons.parse(riyuu))

    atai_col, wild_col = pull(B.IIE), pull(B.HAI)
    wildcard = code == WILDCARD
    # 全部に当たる列が値扱いのコードを許していると、宣言の時点で止まる
    assert wild_col.report.ok is wildcard
    assert atai_col.report.ok is True
    blank = next(r for r in atai_col.reads if r.cell.target == "合成の区分1")
    assert blank.result == (B.RESULTS[2] if wildcard else B.RESULTS[1])
    if wildcard:
        wild_blank = next(r for r in wild_col.reads if r.cell.target == "合成の区分1")
        assert wild_blank.result == B.RESULTS[1]
        assert wild_blank.meaning == f"{code} の意味"
        assert atai_col.sha256() != wild_col.sha256()
    # 値の側のマスは、列の種類を変えても動かない
    assert next(r for r in atai_col.reads
                if r.cell.target == "合成の区分2").result == B.RESULTS[0]
