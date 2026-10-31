"""edge_close の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 読んだ範囲は 2 通りしかない。
  (a) 足す行 1 件ごとに 6 値 + 別枠のどれか 1 つが付き、**7 値の合計 = 足す行の件数**、
      **6 値の合計 = 6 値が付いた件の数**、**rule ごとと次元の値ごとの内訳の合計 =
      足す行の件数**、**① の言い方ごとの合計 = ① の数**、**別枠の理由ごとの合計 =
      別枠の数**で、**終了が書かれていない既存の行は閉じる端として指されず**、**⑤ が出るのは
      知識期間も閉じる対象と宣言された rule だけ**で、**閉じる端として指す行は必ず同じ鍵
      (rule + 次元 + 順位 + 知識期間の重なり)の行**で、判定部分に絶対パスが入らず、
      3 枚の行順を 3 通りに入れ替えても同じバイト列になる
  (b) 1 件も仕分けずに理由コードが返る(仕分けた件や sha256 を取りに行くと例外)
どちらの場合も、この部品は 3 枚の表を 1 文字も書き換えない。

既存の行を 1〜4 行、足す行を 1〜4 件、次元の値を 3 通り(未指定の記号を含む)、順位を 2 通り、
日付を 6 通りから引く。区間の閉じ方(含む / 含まない)・端の単位(日 / 月)・知識期間も閉じる
対象か を宣言表の側で振る。3 割くらいの確率でどこか 1 か所を崩す(9 通りで、1 件も仕分けずに
止まる理由コード 9 個すべてに道が付く)。derandomize=True で毎回同じ入力列を使い、
database=None で例を保存しない。

**6 値 + 別枠の分け方はテストの側で別に実装している**(部品の judge / candidate / seven を
呼ばない)。2 本目は「①・②・③ の分かれ目は端の 1 単位だけで、その 1 単位は区間の閉じ方と
端の単位の宣言から決まる」ことを、閉じ方 × 単位 × 終了の位置 × 開始の位置 の総当たりで見る。
"""
from __future__ import annotations

import csv
import hashlib
import io
import sys
from pathlib import Path

import pytest
from hypothesis import event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "fixtures"))
import edge_close as H  # noqa: E402

RULE = "合成の表(架空)"
GAI_RULE = "合成の宣言表に無い表(架空)"
SRC = "合成の記録(架空)L1"

MARK = "*"
DIMS = (f"地域={MARK}", "地域=甲1", "地域=甲2")
PRIORITIES = ("0", "10")
GAI_PRIORITY = "20"

MONTHS = ("2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06")
DAYS = ("2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04", "2025-01-05",
        "2025-01-06")

OPEN = H.HIRAKI

KOWASHIKATA = ("出典を空にする", "同じ行 id を 2 行書く",
               "開いている印と終了の日付を同じ行に書く", "終了を開始より前にする",
               "同じ rule id を宣言表に 2 行書く", "隙間を許すのに理由コードを書かない",
               "日付を宣言と違う単位で書く", "順位を登録外にする",
               "rule id を宣言表に無いものにする")

# 終了の書き方 3 通り(**空欄を「たぶん開いている」と読み替える経路が無いことを見るため**)
SHUURYOU = ("開いている", "閉じている", "書かれていない")


def dates(unit: str) -> tuple[str, ...]:
    return MONTHS if unit == H.TSUKI else DAYS


@st.composite
def three_tables(draw: st.DrawFn) -> tuple[list[list[str]], list[list[str]],
                                           list[list[str]], str]:
    """既存の行の表・足す行の表・閉じ方の宣言表 と、崩し方(崩さないときは空)。"""
    unit = draw(st.sampled_from(H.UNITS))
    included = draw(st.sampled_from(H.END_KINDS))
    close_known = draw(st.sampled_from(H.KNOWN_KINDS))
    gap = draw(st.sampled_from(H.GAP_KINDS))
    cal = dates(unit)

    declares = [list(H.DECLARE_COLUMNS),
                [RULE, included, unit, gap, "G1" if gap == H.YURUSU else "",
                 MARK, close_known, ";".join(PRIORITIES), "", SRC]]

    rows: list[list[str]] = [list(H.EXISTING_COLUMNS)]
    for i in range(draw(st.integers(1, 4))):
        a = draw(st.integers(0, len(cal) - 2))
        b = draw(st.integers(a, len(cal) - 1))
        kind = draw(st.sampled_from(SHUURYOU))
        valid_to = cal[b] if kind == SHUURYOU[1] else ""
        valid_open = OPEN if kind == SHUURYOU[0] else ""
        ka = draw(st.integers(0, len(cal) - 2))
        kb = draw(st.integers(ka, len(cal) - 1))
        known_open = draw(st.booleans())
        rows.append([f"E{i + 1}", RULE, draw(st.sampled_from(DIMS)),
                     draw(st.sampled_from(PRIORITIES)), cal[a], valid_to, valid_open,
                     cal[ka], "" if known_open else cal[kb], OPEN if known_open else "",
                     SRC])

    adds: list[list[str]] = [list(H.ADD_COLUMNS)]
    for i in range(draw(st.integers(1, 4))):
        undated = draw(st.booleans())
        a = draw(st.integers(0, len(cal) - 1))
        ka = draw(st.integers(0, len(cal) - 1))
        adds.append([f"A{i + 1}", RULE, draw(st.sampled_from(DIMS)),
                     draw(st.sampled_from(PRIORITIES)),
                     "" if undated else cal[a], H.SEIREI if undated else "",
                     "", OPEN, cal[ka], "", OPEN, SRC])

    how = draw(st.sampled_from(("",) + KOWASHIKATA)) if draw(
        st.integers(0, 9)) < 3 else ""
    if how == KOWASHIKATA[0]:
        rows[1][-1] = ""
    elif how == KOWASHIKATA[1]:
        rows.append(list(rows[1]))
    elif how == KOWASHIKATA[2]:
        rows[1][5], rows[1][6] = cal[-1], OPEN
    elif how == KOWASHIKATA[3]:
        rows[1][4], rows[1][5], rows[1][6] = cal[-1], cal[0], ""
    elif how == KOWASHIKATA[4]:
        declares.append(list(declares[1]))
    elif how == KOWASHIKATA[5]:
        declares[1][3], declares[1][4] = H.YURUSU, ""
    elif how == KOWASHIKATA[6]:
        rows[1][4] = "2025-01-01" if unit == H.TSUKI else "2025-01"
    elif how == KOWASHIKATA[7]:
        rows[1][3] = GAI_PRIORITY
    elif how == KOWASHIKATA[8]:
        rows[1][1] = GAI_RULE
    return rows, adds, declares, how


def limit_of(to: str, open_end: bool, included: str, unit: str) -> str:
    """覆っていない最初の単位(テストの側の実装。部品の Rule.limit を呼ばない)。"""
    if open_end or not to:
        return ""
    return H.next_unit(to, unit) if included == H.FUKUMU else to


def overlap(a0: str, a1: str, b0: str, b1: str) -> bool:
    return (not b1 or a0 < b1) and (not a1 or b0 < a1)


def classify(rows: list[list[str]], adds: list[list[str]],
             decl: list[str]) -> dict[str, tuple[str, str]]:
    """提案 id -> (7 値, 閉じることになる行 id)。**部品を 1 つも呼ばない。**"""
    included, unit, close_known = decl[1], decl[2], decl[6]
    out: dict[str, tuple[str, str]] = {}
    for a in adds[1:]:
        add_id, dims, prio, start = a[0], a[2], a[3], a[4]
        kfrom, kto, kopen = a[8], a[9], a[10]
        same = [r for r in rows[1:]
                if r[1] == RULE and r[2] == dims and r[3] == prio
                and (r[6] == OPEN or r[5])
                and overlap(r[7], limit_of(r[8], r[9] == OPEN, included, unit),
                            kfrom, limit_of(kto, kopen == OPEN, included, unit))]
        same.sort(key=lambda r: (r[4], r[0]))
        if not start:
            found = same[-1] if same else None
        else:
            before = [r for r in same if r[4] <= start]
            found = before[-1] if before else None
        if found is None:
            out[add_id] = (H.KEKKA[3], "")
            continue
        row_id, open_end = found[0], found[6] == OPEN
        if open_end:
            if not start:
                out[add_id] = (H.KEKKA[0], row_id)
            elif found[4] == start:
                out[add_id] = (H.KEKKA[5], row_id)
            else:
                out[add_id] = (H.KEKKA[0], row_id)
            continue
        if not start:
            out[add_id] = (H.KEKKA[0], row_id)
            continue
        lim = limit_of(found[5], False, included, unit)
        if lim > start:
            out[add_id] = (H.KEKKA[1], row_id)
        elif lim < start:
            out[add_id] = (H.KEKKA[2], row_id)
        elif close_known == H.TOJIRU and found[9] == OPEN:
            out[add_id] = (H.KEKKA[4], row_id)
        else:
            out[add_id] = (H.KEKKA[0], row_id)
    return out


def write(tmp: Path, name: str, rows: list[list[str]]) -> Path:
    p = tmp / name
    with p.open("w", encoding="utf-8", newline="") as f:
        import csv
        csv.writer(f, lineterminator="\n").writerows(rows)
    return p


@settings(derandomize=True, database=None, max_examples=200, deadline=None)
@given(three_tables())
def test_either_sorted_or_stopped(tables) -> None:
    """(a) 7 値がそろって合計が合うか、(b) 1 件も仕分けずに理由コードが返るか、の 2 通り。"""
    rows_rows, adds_rows, decl_rows, how = tables
    try:
        rows = H.Rows.parse(to_csv(rows_rows))
        adds = H.Adds.parse(to_csv(adds_rows))
        declares = H.Declares.parse(to_csv(decl_rows))
    except H.ReadError:
        event("表として読めない")
        return
    before = snapshot(rows_rows, adds_rows, decl_rows)
    t = H.edge_close(rows, adds, declares)
    if not t.report.ok:
        event("止まった")
        assert t.judged == ()
        assert all(v == 0 for v in t.seven().values())
        assert set(t.stopped()) <= set(H.TABLE_REASONS)
        assert set(t.stopped())
        with pytest.raises(RuntimeError):
            t.sha256()
        assert snapshot(rows_rows, adds_rows, decl_rows) == before
        return
    event(f"仕分けた(崩し方 {how or 'なし'})")
    seven = t.seven()
    n = len(adds_rows) - 1
    assert sum(seven.values()) == n == t.add_denominator()
    assert sum(seven[k] for k in H.MUTSU) == t.counted_denominator
    assert sum(t.aside_reasons().values()) == seven[H.BEKKA]
    assert sum(t.shapes().values()) == seven[H.KEKKA[0]]
    assert sum(int(r["足す行の数"]) for r in t.by_rule()) == n
    assert sum(int(r["足す行の数"]) for r in t.by_dims()) == n
    # 判定はテストの側の分類と一致する
    mine = classify(rows_rows, adds_rows, decl_rows[1])
    assert {j.add.add_id: (j.result, j.row_id) for j in t.judged} == mine
    # ⑤ が出るのは「知識期間も閉じる」と宣言された rule だけ
    if decl_rows[1][6] == H.TOJINAI:
        assert seven[H.KEKKA[4]] == 0
    # 終了が書かれていない行は端として指されない
    naked = {r[0] for r in rows_rows[1:] if r[6] != OPEN and not r[5]}
    assert not ({j.row_id for j in t.judged if j.row_id} & naked)
    # 指した行は必ず同じ鍵の行
    keys = {r[0]: (r[1], H.dims_key(r[2], "t"), r[3]) for r in rows_rows[1:]}
    for j in t.judged:
        if j.row_id:
            rule_id, dims, prio = keys[j.row_id]
            assert (rule_id, dims, int(prio)) == j.add.key()
    # 行順を入れ替えても同じバイト列
    for way in H.SWAPS:
        other = H.edge_close(rows.swapped(way), adds.swapped(way), declares.swapped(way))
        assert other.report.ok and other.sha256() == t.sha256()
    assert "C:\\" not in t.judgement_bytes().decode("utf-8")
    assert snapshot(rows_rows, adds_rows, decl_rows) == before


def to_csv(rows: list[list[str]]) -> str:
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows(rows)
    return buf.getvalue()


def snapshot(*tables: list[list[str]]) -> str:
    return hashlib.sha256("".join(to_csv(t) for t in tables).encode("utf-8")).hexdigest()


@settings(derandomize=True, database=None, max_examples=300, deadline=None)
@given(st.sampled_from(H.END_KINDS), st.sampled_from(H.UNITS),
       st.integers(1, 4), st.integers(0, 5), st.sampled_from(H.KNOWN_KINDS),
       st.booleans())
def test_one_unit_decides_overlap_adjacency_gap(included: str, unit: str, end_i: int,
                                                start_i: int, close_known: str,
                                                known_open: bool) -> None:
    """①・②・③ の分かれ目は端の 1 単位だけで、その 1 単位は宣言から決まる。

    既存の行を 1 行(閉じていて、有効期間も知識期間も空でない)、足す行を 1 件だけ置き、
    **開始の位置を 1 単位ずつ動かすと ② → ①(または ⑤)→ ③ の順に動く**ことを総当たりで見る。
    """
    cal = dates(unit)
    decl = [list(H.DECLARE_COLUMNS),
            [RULE, included, unit, H.YURUSANAI, "", MARK, close_known,
             ";".join(PRIORITIES), "", SRC]]
    rows = [list(H.EXISTING_COLUMNS),
            ["E1", RULE, "地域=甲1", "0", cal[0], cal[end_i], "", cal[0],
             "" if known_open else cal[-1], OPEN if known_open else "", SRC]]
    adds = [list(H.ADD_COLUMNS),
            ["A1", RULE, "地域=甲1", "0", cal[start_i], "", "", OPEN, cal[0], "", OPEN,
             SRC]]
    t = H.edge_close(H.Rows.parse(to_csv(rows)), H.Adds.parse(to_csv(adds)),
                     H.Declares.parse(to_csv(decl)))
    assert t.report.ok
    got = t.judged[0].result
    lim = limit_of(cal[end_i], False, included, unit)
    start = cal[start_i]
    if lim > start:
        assert got == H.KEKKA[1]
        event("重なる")
    elif lim < start:
        assert got == H.KEKKA[2]
        event("隙間")
    elif close_known == H.TOJIRU and known_open:
        assert got == H.KEKKA[4]
        event("知識期間の端が開いたまま")
    else:
        assert got == H.KEKKA[0]
        event("隣接")
    # 境界の 1 単位: 開始が終了の次の単位のときだけ、重なりも隙間も出ない
    assert (got in (H.KEKKA[1], H.KEKKA[2])) == (lim != start)
    # 閉じ方の宣言を裏返すと、同じ表でも 1 単位ずれる
    other = H.FUKUMANAI if included == H.FUKUMU else H.FUKUMU
    assert limit_of(cal[end_i], False, other, unit) != lim
