"""order_table の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 並べた結果は 2 通りしかない。
  (a) 出力は入力の行の並べ替えにちょうどなっていて(1 行も増えず減らず書き換わらず、列も増えず)、
      行の順は宣言された鍵だけで決まり(入力表の行順を宣言された入れ替え方で入れ替えた表からでも
      同じバイト列)、判定部分に時刻・ホスト名・絶対パスが 1 つも入らない
  (b) 1 行も並べずに理由コードが返る(並べた表を取りに行くと例外になる)
どちらの場合も、この部品はデータ表も宣言表も 1 文字も書き換えない。

データ表と宣言表は乱数で作る。データ表は 2〜8 行、宣言表の鍵は 1〜3 本を 6 通りの宣言(列 × 値の
種類)から引き、向きと欠損の置き場所も乱数で振る。さらに 3 割くらいの確率で宣言表かデータ表を
1 か所だけ崩す(出典を空にする / 順位を重複させる / 種類を空にする / 種類を未登録にする / 欠損の
置き場所を空にする / 候補の並びを宣言表に無い列名にする / 鍵をデータ表に無い列名にする /
宣言された列挙の候補に無い値をデータに入れる / 鍵の行を 0 行にする)。derandomize=True で毎回同じ
入力列を使い、database=None で見つけた例を保存しない。

**期待する並びは部品の比較を呼ばずにテストの側で別に計算している**(値ごとの順位に直してから
整数の組として並べ替える、別の実装)。
"""
from __future__ import annotations

import csv
import datetime
import sys
from decimal import Decimal
from io import StringIO
from pathlib import Path

import pytest
from hypothesis import event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import order_table as O  # noqa: E402

SOURCE = "合成の並び順メモ(架空)L1"
HEADER = ["社員番号", "氏名カナ", "区分", "支給日", "金額"]
KUBUN = ("甲", "乙", "丙")
CHOICES_ROW = ["", "区分", "", "", "", "|".join(KUBUN), SOURCE, ""]

# 宣言できる (列, 値の種類) の組。生成するデータはどの宣言でも読める形にしてある
DECLARABLE = (("社員番号", "整数"), ("社員番号", "コードポイント列"), ("区分", "宣言された列挙"),
              ("支給日", "日付"), ("金額", "Decimal"), ("金額", "コードポイント列"))

KOWASHIKATA = ("出典を空にする", "順位を重複させる", "種類を空にする", "種類を未登録にする",
               "欠損の置き場所を空にする", "候補の並びを宣言表に無い列名にする",
               "鍵をデータ表に無い列名にする", "宣言された列挙の候補に無い値をデータに入れる",
               "鍵の行を 0 行にする")


def csv_text(header: list[str], rows: list[list[str]]) -> str:
    buf = StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue()


@st.composite
def 合成の表(draw: st.DrawFn) -> tuple[str, str, str | None]:
    """(データ表の text, 宣言表の text, 崩し方 or None)を作る。"""
    n = draw(st.integers(min_value=2, max_value=8))
    rows: list[list[str]] = []
    for i in range(n):
        shain = draw(st.one_of(st.just(""), st.integers(min_value=0, max_value=120).map(str)))
        kubun = draw(st.sampled_from(KUBUN))
        day = draw(st.sampled_from(("2026-04-25", "2026-05-25", "2026-06-25")))
        kingaku = draw(st.sampled_from(("829", "829.0", "8290", "9120", "10450", "")))
        rows.append([shain, f"氏名{i}", kubun, day, kingaku])

    picked = draw(st.lists(st.sampled_from(DECLARABLE), min_size=1, max_size=3, unique=True))
    decl: list[list[str]] = []
    for rank, (column, kind) in enumerate(picked, 1):
        direction = draw(st.sampled_from(O.DIRECTIONS))
        missing = draw(st.sampled_from(O.MISSING_PLACES))
        decl.append([str(rank), column, direction, kind, missing, "", SOURCE,
                     "逆順" if rank == 1 else ""])
    if any(kind == "宣言された列挙" for _, kind in picked):
        decl.append(list(CHOICES_ROW))

    kowasu = draw(st.sampled_from([None] * 7 + list(KOWASHIKATA)))
    if kowasu == "出典を空にする":
        decl[0][6] = ""
    elif kowasu == "順位を重複させる":
        decl.append([decl[0][0], *decl[0][1:6], SOURCE, ""])
    elif kowasu == "種類を空にする":
        decl[0][3] = ""
    elif kowasu == "種類を未登録にする":
        decl[0][3] = "文字列"
    elif kowasu == "欠損の置き場所を空にする":
        decl[0][4] = ""
    elif kowasu == "候補の並びを宣言表に無い列名にする":
        decl.append(["", "等級", "", "", "", "A|B|C", SOURCE, ""])
    elif kowasu == "鍵をデータ表に無い列名にする":
        decl[0][1] = "等級"
        decl[0][3] = "コードポイント列"
    elif kowasu == "宣言された列挙の候補に無い値をデータに入れる":
        if any(kind == "宣言された列挙" for _, kind in picked):
            rows[0][2] = "丁"
        else:
            decl[0][6], kowasu = "", "出典を空にする"
    elif kowasu == "鍵の行を 0 行にする":
        decl = [list(CHOICES_ROW)]
        decl[0][1] = "等級"              # 鍵が 0 行 + 宣言表に無い列名
    return csv_text(HEADER, rows), csv_text(O.DECL_COLUMNS, decl), kowasu


# ------------------------------------------------------------ テスト側の別実装

def 値を読む(text: str, kind: str) -> object | None:
    """宣言された種類として値を読む(部品の read_value は呼ばない)。空欄は None。"""
    if text.strip() == "":
        return None
    t = text.strip()
    if kind == "整数":
        return int(t)
    if kind == "Decimal":
        return Decimal(t)
    if kind == "日付":
        return datetime.date.fromisoformat(t)
    if kind == "宣言された列挙":
        return KUBUN.index(t)
    return t


def 順位の組(rows: list[list[str]], keys: list[tuple[str, str, str, str]]) -> list[tuple[int, ...]]:
    """各鍵について値を順位(整数)に直し、行ごとの整数の組にする。欠損は宣言の置き場所に寄せる。"""
    out: list[list[int]] = [[] for _ in rows]
    for column, kind, direction, missing in keys:
        col = HEADER.index(column)
        values = [値を読む(r[col], kind) for r in rows]
        distinct = sorted({v for v in values if v is not None})
        for i, v in enumerate(values):
            if v is None:
                out[i].append(-1 if missing == "先" else len(distinct))
            else:
                pos = distinct.index(v)
                out[i].append(len(distinct) - 1 - pos if direction == "降順" else pos)
    return [tuple(x) for x in out]


@settings(max_examples=120, derandomize=True, database=None, deadline=None)
@given(表=合成の表())
def test_いつも成り立つこと_並べた表か理由コードか(表: tuple[str, str, str | None]) -> None:
    data_text, decl_text, kowasu = 表
    table, order = O.Table.parse(data_text), O.Order.parse(decl_text)
    s = O.sort_table(table, order)

    body = list(csv.reader(data_text.splitlines()))[1:]
    keys = [(k.column, k.kind, k.direction, k.missing) for k in order.keys]
    readable = all(k.column in HEADER for k in order.keys) and not order.pending
    expect_stop = bool(kowasu)
    tie_expected = False
    if readable and not expect_stop:
        組 = 順位の組(body, keys)
        tie_expected = len(set(組)) != len(組)

    if expect_stop or tie_expected:
        event("(b) 止まった")
        assert s.report.ok is False
        assert s.index == ()
        assert s.report.pending
        assert {p.reason for p in s.report.pending} <= set(O.STOP_REASONS)
        if tie_expected and not expect_stop:
            assert O.STOP_REASONS[8] in {p.reason for p in s.report.pending}
        for call in (s.rows, s.judgement_bytes, s.sha256):
            with pytest.raises(RuntimeError):
                call()
    else:
        event("(a) 並べた")
        assert s.report.ok is True
        組 = 順位の組(body, keys)
        expected = sorted(range(len(body)), key=lambda i: (組[i], i))
        assert list(s.index) == expected                       # 期待する並びはテスト側の計算
        assert sorted(s.rows()) == sorted(table.rows)          # 行は増えず減らず書き換わらない
        out = O.Table.parse(s.judgement_bytes().decode("utf-8"))
        assert out.header == table.header                      # 列も増えない
        assert len(out.rows) == len(table.rows)
        raw = s.judgement_bytes().decode("utf-8")
        for word in (s.read_at, s.host, "読んだ時刻", "ホスト名"):
            assert word not in raw
        swapped = O.sort_table(table.swapped(order.swap or "逆順"), order)
        assert swapped.report.ok and swapped.sha256() == s.sha256()

    # どちらの場合も入力は 1 文字も書き換わらない
    assert O.Table.parse(data_text).rows == table.rows
    assert csv_text(HEADER, body) == data_text


@settings(max_examples=300, derandomize=True, database=None)
@given(kingaku=st.lists(st.sampled_from(("829", "829.0", "0829", "830", "830.00", "")),
                        min_size=2, max_size=8))
def test_数として等しい値は_Decimal_の宣言のときだけ同値になる(kingaku: list[str]) -> None:
    """近いことを同じことにはしないが、Decimal と宣言した列では数として等しい値は同値になる。"""
    rows = [["", f"氏名{i}", "甲", "2026-04-25", v] for i, v in enumerate(kingaku)]
    data = csv_text(HEADER, rows)
    out = {}
    for kind in ("Decimal", "コードポイント列"):
        decl = csv_text(O.DECL_COLUMNS, [["1", "金額", "昇順", kind, "後", "", SOURCE, "逆順"]])
        s = O.sort_table(O.Table.parse(data), O.Order.parse(decl))
        c = s.counts()
        # 分母の恒等式は、止まっても並んでも成り立つ
        assert c["順が一意に決まった行数"] + c["同値の組に関与した行数"] == c["データ表の行数"]
        assert c["鍵の組数"] <= c["データ表の行数"]
        out[kind] = c

    decimal_values = [Decimal(v) if v.strip() else None for v in kingaku]
    codepoint_values = [v.strip() or None for v in kingaku]
    assert out["Decimal"]["鍵の組数"] == len({str(v) if v is None else v for v in decimal_values})
    assert out["コードポイント列"]["鍵の組数"] == len(set(codepoint_values))
    # 数として等しい値を別の表記で並べた表は、Decimal の宣言では同値の組になる
    assert out["Decimal"]["鍵の組数"] <= out["コードポイント列"]["鍵の組数"]
    assert out["Decimal"]["同値の組に関与した行数"] >= out["コードポイント列"]["同値の組に関与した行数"]
