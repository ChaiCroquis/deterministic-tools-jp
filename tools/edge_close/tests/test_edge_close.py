"""edge_close のテスト。合成 fixture は `fixtures/` に commit 済(実データ・実在の値は入れない)。

test_measure_* が記事に載せた数値の出どころで、assert で固定している(値が変われば記事も
変える前提)。測っているものは 8 つある。

  (1) 足す行 17 件 が 6 値 + 別枠に分かれ、3 つの分母の内訳が付く側
  (2) **① の 6 件 が、開いている端を閉じる 3・すでに隣接 2・施行日未定 1 に分かれる**側
  (3) **② の 2 件 と ③ の 2 件 が、端の 1 単位の差だけで分かれる**という側。= 記事の骨
  (4) **有効期間が同じように隣接していても、知識期間も閉じる対象かの宣言で ⑤ と ① に
      分かれる**側
  (5) ④ の 2 件 が、終了が書かれていない行がある場合と同じ鍵の行が無い場合に分かれる側
  (6) 別枠 3 件 が理由ごとに 1 件ずつ出る側
  (7) 開いている印を 1 件外すと、その足す行だけが ① から ④ へ動く側
  (8) 開始を 1 単位ずつ動かすと ② → ① → ③ と動き、ほかの件が動かない側

(1) の 7 値は、テストの側でも 3 枚の表の行から直に組み立てて確かめている(部品の judge /
seven を呼ばず、fixture の行から別に分類する)。
"""
from __future__ import annotations

import ast
import hashlib
import io
import json
import sys
import tokenize
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIX = ROOT / "fixtures"
BROKEN = FIX / "kowashita"
PLAN = ROOT.parent.parent          # 07_記事化商品化計画(出典の行を開くため)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FIX))
import edge_close as H  # noqa: E402
import make_fixtures as M  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの -> その行に在るはずの語
REAL_SOURCES = {
    M.SRC_SPAN: "境界",
    M.SRC_RANK: "宣言",
}

# 良し悪しを指す語(件数の側に持たせない = 型 B3 の forbidden の物理形)
KINSOKU = ("誤り", "違反", "事故", "異常", "障害", "不正", "要注意")

# 形容の語(数値が無いなら多寡を書かない)
KEIYOU = ("多い", "少ない", "ほとんど", "かなり", "著しく", "ざっと")

# この部品が言い出してはいけない語(宣言表に在るときだけ写す)
NANORI = ("新設", "初", "初めて")

# 持たせていない経路の名前(動く側のコードに 1 つも無いことを見る)
MOTANAI = ("eval", "exec", "round(", "float(", "now(", "today(", "utcnow",
           "subprocess", "random", "platform", "urllib", "requests", "socket",
           "difflib", "SequenceMatcher", "time.")

KOU, OTSU, HEI, TEI, BO = M.KOU, M.OTSU, M.HEI, M.TEI, M.BO


def paths(**swap: Path) -> dict[str, Path]:
    """3 枚の置き場。崩した表を 1 枚だけ差し替えられる。"""
    out = {"rows": FIX / "rows_a.csv", "adds": FIX / "adds_a.csv",
           "declares": FIX / "declares_a.csv"}
    out.update(swap)
    return out


def load(**swap: Path) -> tuple[H.Rows, H.Adds, H.Declares]:
    p = paths(**swap)
    return (H.Rows.load(p["rows"]), H.Adds.load(p["adds"]),
            H.Declares.load(p["declares"]))


def pull(**swap: Path) -> H.Tally:
    return H.edge_close(*load(**swap))


def judged_of(t: H.Tally, add_id: str) -> H.Judged:
    return next(j for j in t.judged if j.add.add_id == add_id)


# ---------------------------------------------------------------- 別実装の分類

def expect_seven() -> dict[str, int]:
    """7 値を、テストの側で 3 枚の行から直に組み立てる(部品の judge / seven を呼ばない)。"""
    rows = [r for r in M.rows_rows()[1:]]
    adds = [a for a in M.adds_rows()[1:]]
    decl = {d[0]: d for d in M.declares_rows()[1:]}
    rc = {c: i for i, c in enumerate(H.EXISTING_COLUMNS)}
    ac = {c: i for i, c in enumerate(H.ADD_COLUMNS)}
    dc = {c: i for i, c in enumerate(H.DECLARE_COLUMNS)}
    out = {k: 0 for k in H.KEKKA}

    def limit(to: str, open_end: bool, d: list[str]) -> str:
        if open_end or not to:
            return ""
        unit = d[dc["edge_unit"]]
        return H.next_unit(to, unit) if d[dc["end_included"]] == H.FUKUMU else to

    def overlap(a0: str, a1: str, b0: str, b1: str) -> bool:
        return (not b1 or a0 < b1) and (not a1 or b0 < a1)

    for a in adds:
        d = decl.get(a[ac["rule_id"]])
        start, mark = a[ac["valid_from"]], a[ac["pending_order"]]
        if d is None:
            out[H.BEKKA] += 1
            continue
        if mark == H.SEIREI and start:
            out[H.BEKKA] += 1
            continue
        unit = d[dc["edge_unit"]]
        if any(v and not H.unit_ok(v, unit) for v in
               (start, a[ac["valid_to"]], a[ac["known_from"]], a[ac["known_to"]])):
            out[H.BEKKA] += 1
            continue
        same = [r for r in rows
                if r[rc["rule_id"]] == a[ac["rule_id"]]
                and r[rc["dims"]] == a[ac["dims"]]
                and r[rc["priority"]] == a[ac["priority"]]
                and overlap(r[rc["known_from"]],
                            limit(r[rc["known_to"]], r[rc["known_open"]] == H.HIRAKI, d),
                            a[ac["known_from"]],
                            limit(a[ac["known_to"]], a[ac["known_open"]] == H.HIRAKI, d))
                and (r[rc["valid_open"]] == H.HIRAKI or r[rc["valid_to"]])]
        same.sort(key=lambda r: r[rc["valid_from"]])
        if not start:
            found = same[-1] if same else None
        else:
            before = [r for r in same if r[rc["valid_from"]] <= start]
            found = before[-1] if before else None
        if found is None:
            out[H.KEKKA[3]] += 1
            continue
        open_end = found[rc["valid_open"]] == H.HIRAKI
        if open_end:
            if not start:
                out[H.KEKKA[0]] += 1
            elif a[ac["valid_open"]] == H.HIRAKI and found[rc["valid_from"]] == start:
                out[H.KEKKA[5]] += 1
            else:
                out[H.KEKKA[0]] += 1
            continue
        if not start:
            out[H.KEKKA[0]] += 1
            continue
        lim = limit(found[rc["valid_to"]], False, d)
        if lim > start:
            out[H.KEKKA[1]] += 1
        elif lim < start:
            out[H.KEKKA[2]] += 1
        elif (d[dc["close_known"]] == H.TOJIRU
              and found[rc["known_open"]] == H.HIRAKI):
            out[H.KEKKA[4]] += 1
        else:
            out[H.KEKKA[0]] += 1
    return out


# ---------------------------------------------------------------- 記事に載せた数値

def test_measure_17_adds_split_into_seven() -> None:
    """(1) 足す行 17 件 が 6 値 + 別枠に分かれ、分母の内訳が付く。"""
    t = pull()
    assert t.report.ok and t.report.pending == ()
    c = t.counts()
    assert c["既存の行の表の行数"] == 15
    assert c["足す行の表の行数"] == 17
    assert c["閉じ方の宣言表の行数"] == 5
    assert c["分母(足す行の件数)"] == 17 == t.add_denominator()
    assert c["分母(6 値が付いた件の数)"] == 14
    assert c["分母(別枠の数)"] == 3
    assert c["分母(足す行に出てくる rule の数)"] == 6
    assert c["6 値 + 別枠"] == {
        "閉じる端がある": 6,
        "閉じ忘れると重なる": 2,
        "閉じると隙間ができる": 2,
        "閉じる端が無い": 2,
        "有効期間は閉じたが知識期間の端が開いたまま": 1,
        "同じ日に 2 つ開く": 1,
        "別枠": 3}
    assert c["6 値 + 別枠"] == expect_seven()
    assert sum(c["6 値 + 別枠"].values()) == 17
    assert c["理由別の止まった件数"] == {}
    assert not any(isinstance(v, float) for v in c.values())
    assert not any(str(k).endswith(("率", "割合", "点", "スコア")) for k in c)
    print("[measure] rows_a / adds_a / declares_a: 既存 15 行 / 足す行 17 行 / 宣言 5 行"
          f" → 6 値 + 別枠 {c['6 値 + 別枠']}")
    print("[measure] 分母は 足す行の件数 17 / 6 値が付いた件 14 / 別枠 3、"
          "それに 足す行に出てくる rule 6")


def test_measure_six_edges_split_into_three_shapes() -> None:
    """(2) ① の 6 件 が、言い方の違いで 3 つに分かれる。"""
    t = pull()
    assert t.counts()["閉じる端がある件の言い方ごと"] == {
        "開いている端を足す行の開始で閉じる": 3,
        "すでに隣接しているので閉じる操作が要らない": 2,
        "開いている端があるが、施行日が未定なので閉じる日付が決まらない": 1}
    assert 3 + 2 + 1 == 6 == t.seven()[H.KEKKA[0]]
    # 開いている端を閉じる 3 件は、閉じる日付が入る(施行日未定の 1 件は空のまま)
    hiraki = [j for j in t.judged if j.shape == H.TOJIKATA[0]]
    assert sorted(j.add.add_id for j in hiraki) == ["A01", "A08", "A09"]
    assert all(j.at for j in hiraki)
    mitei = judged_of(t, "A11")
    assert mitei.result == H.KEKKA[0] and mitei.row_id == "E15" and mitei.at == ""
    print("[measure] ① の 6 件 の内訳 = 開いている端を閉じる 3(A01 / A08 / A09)"
          " + すでに隣接 2 + 施行日未定で日付が決まらない 1(A11、閉じる行 E15 は"
          "出るが日付の欄は空)")


def test_measure_two_overlaps_and_two_gaps() -> None:
    """(3) ② の 2 件 と ③ の 2 件 が、端の 1 単位の差だけで分かれる(= 記事の骨)。"""
    t = pull()
    assert t.seven()[H.KEKKA[1]] == 2 and t.seven()[H.KEKKA[2]] == 2
    assert sorted(j["提案 id"] for j in t.overlapping()) == ["A02", "A16"]
    assert sorted(j["提案 id"] for j in t.gaps()) == ["A03", "A17"]
    # 丙表(含む・日)の E06 と E07 は終了が 1 日違うだけで、片方は ①、片方は ③
    adjacent, gap = judged_of(t, "A15"), judged_of(t, "A03")
    assert adjacent.row_id == "E06" and adjacent.result == H.KEKKA[0]
    assert gap.row_id == "E07" and gap.result == H.KEKKA[2]
    assert H.next_unit("2026-03-31", H.HI) == "2026-04-01"
    assert H.next_unit("2026-03-30", H.HI) == "2026-03-31"
    assert adjacent.add.valid.start == gap.add.valid.start == "2026-04-01"
    print("[measure] ② は 2 件(A02 / A16)、③ は 2 件(A03 / A17)。丙表 の E06 と"
          " E07 は終了が 2026-03-31 と 2026-03-30 の 1 日違いで、同じ開始 2026-04-01"
          " の提案が ① と ③ に分かれる")


def test_measure_same_adjacency_splits_by_the_known_declaration() -> None:
    """(4) 有効期間が同じように隣接していても、知識期間の宣言で ⑤ と ① に分かれる。"""
    t = pull()
    assert t.seven()[H.KEKKA[4]] == 1
    assert [j["提案 id"] for j in t.known_left_open()] == ["A06"]
    hei, otsu = t.declares.of(HEI), t.declares.of(OTSU)
    assert hei is not None and otsu is not None
    assert hei.close_known == H.TOJIRU and otsu.close_known == H.TOJINAI
    # どちらも「有効期間は隣接、知識終了は開いたまま」の既存の行を指している
    for add_id, row_id, want in (("A06", "E14", H.KEKKA[4]), ("A10", "E13", H.KEKKA[0])):
        j = judged_of(t, add_id)
        assert j.row_id == row_id and j.result == want
    assert t.rows.of("E14").known.open_end is True
    assert t.rows.of("E13").known.open_end is False
    print("[measure] ⑤ は 1 件(A06、丙表 = 知識期間も閉じる)。乙表 は 知識期間を"
          "閉じない と宣言されているので、同じく有効期間が隣接している A10 は ① に"
          "入る(宣言を読まずに隣接だけ見ると、この 2 件が同じ値になる)")


def test_measure_one_double_open() -> None:
    """(5) ⑥ は 1 件で、既存の行と足す行の開始が同じ日。"""
    t = pull()
    assert t.seven()[H.KEKKA[5]] == 1
    j = judged_of(t, "A07")
    assert j.result == H.KEKKA[5] and j.row_id == "E08"
    row = t.rows.of("E08")
    assert row.valid.open_end and j.add.valid.open_end
    assert row.valid.start == j.add.valid.start == "2025-10"
    # 同じ鍵の古い行 E09 は知識期間が重ならないので端として指されない
    assert judged_of(t, "A07").row_id != "E09"
    print("[measure] ⑥ は 1 件(A07 と E08、どちらも開始 2025-10 で終了が開いている)。"
          "同じ鍵の古い行 E09 は知識期間が重ならないので端として指さない")


def test_measure_no_edge_has_two_shapes() -> None:
    """(6) ④ の 2 件 は、終了が書かれていない行がある場合と、同じ鍵の行が無い場合。"""
    t = pull()
    assert t.seven()[H.KEKKA[3]] == 2
    assert sorted(j["提案 id"] for j in t.no_edge()) == ["A04", "A05"]
    # A04 の鍵には既存の行 E12 が在るが、終了の欄が空で開いている印も無い
    e12 = t.rows.of("E12")
    assert e12.valid.end == "" and e12.valid.open_end is False
    assert e12.end_written is False
    assert e12.key() == judged_of(t, "A04").add.key()
    # A05 の鍵には既存の行が 1 行も無い
    assert not [r for r in t.rows.items if r.key() == judged_of(t, "A05").add.key()]
    # どちらも語を写さない(宣言表の ④ に写してよい語 が空)
    assert all(j["④ に写した語"] == "" for j in t.no_edge())
    print("[measure] ④ は 2 件。A04 は同じ鍵の E12 が在るが終了の欄が空で開いている印も"
          "無い(= 終了が書かれていない)、A05 は同じ鍵の行が 1 行も無い。どちらにも"
          "「新設」の語は付かない")


def test_measure_three_asides_one_per_reason() -> None:
    """(7) 別枠 3 件 が、理由ごとに 1 件ずつ出る。"""
    t = pull()
    assert t.aside_reasons() == {
        "鍵が宣言表に無い": 1, "出典が空": 0, "終了が開始より前": 0, "順位が登録外": 0,
        "提案 id の重複": 0, "日付の書式が宣言と違う": 1,
        "施行日未定の印が立っているのに開始が入っている": 1}
    assert sum(t.aside_reasons().values()) == 3 == t.aside_denominator()
    got = {j["提案 id"]: j["別枠の理由"] for j in t.asides()}
    assert got == {"A12": "鍵が宣言表に無い", "A13": "日付の書式が宣言と違う",
                   "A14": "施行日未定の印が立っているのに開始が入っている"}
    print("[measure] 別枠は 3 件 で、理由は 鍵が宣言表に無い 1(A12)/ 日付の書式が宣言と"
          "違う 1(A13、甲表 の端の単位は 月 なのに 2026-04-01)/ 施行日未定の印が"
          "立っているのに開始が入っている 1(A14)")


def test_measure_dropping_one_open_mark_moves_one_add() -> None:
    """(8) 開いている印を 1 件外すと、その足す行だけが ① から動く。"""
    rows, adds, declares = load()
    first = H.edge_close(rows, adds, declares)
    probe = H.open_probe(rows, adds, declares, first)
    assert probe["合うか"] is True
    assert probe["外した行 id"] == "E04" and probe["見た提案 id"] == "A08"
    assert probe["前の判定"] == H.KEKKA[0] and probe["後の判定"] == H.KEKKA[3]
    assert probe["ほかで動いた件"] == []
    assert probe["6 値 + 別枠(後)"][H.KEKKA[0]] == 5
    assert probe["6 値 + 別枠(後)"][H.KEKKA[3]] == 3
    print("[measure] E04 の 開 の印を外すと、A08 だけが ① → ④ へ動いて ① 6 → 5、"
          "④ 2 → 3。ほかで動いた件は 0 件(終了の欄が空のまま印を外すと、"
          "「終了が書かれていない」行になって端として指されなくなる)")


def test_measure_shifting_the_start_by_one_unit() -> None:
    """(9) 開始を 1 単位ずつ動かすと ② → ① → ③ と動き、ほかの件は動かない。"""
    rows, adds, declares = load()
    first = H.edge_close(rows, adds, declares)
    probe = H.shift_probe(rows, adds, declares, first)
    assert probe["合うか"] is True
    assert probe["見た提案 id"] == "A16"
    assert probe["既存の終了"] == "2026-09" and probe["終了の次の単位"] == "2026-09"
    assert probe["さらに 1 単位後ろ"] == "2026-10"
    assert probe["動いた順"] == [H.KEKKA[1], H.KEKKA[0], H.KEKKA[2]]
    for start in ("2026-09", "2026-10"):
        assert probe[f"開始を {start} にしたとき"]["ほかで動いた件"] == []
    print("[measure] A16 の開始を 2026-04 → 2026-09 → 2026-10 と動かすと、判定は"
          " ② → ① → ③ と動く(乙表 は 含まない なので、既存の終了 2026-09 が"
          "そのまま次の単位になる)。どちらの写しでもほかで動いた件は 0 件")


def test_measure_untouched_rows_are_listed() -> None:
    """どの足す行からも端として指されなかった既存の行を、止めずに並べる。"""
    t = pull()
    got = t.untouched_rows()
    assert [r["行 id"] for r in sorted(got, key=lambda r: r["行 id"])] == \
        ["E03", "E09", "E12"]
    assert t.counts()["どの足す行からも指されなかった既存の行"] == 3
    # E03 は未指定の記号が入った行。道具は記号を展開して当てない
    e03 = next(r for r in got if r["行 id"] == "E03")
    assert M.MARK in e03["次元の値"]
    print("[measure] どの足す行からも端として指されなかった既存の行は 3 行"
          "(E03 = 未指定の記号 * が入った行、E09 = 知識期間が重ならない古い行、"
          "E12 = 終了が書かれていない行)。止めずに一覧へ出す")


def test_verify_passes_on_the_synthetic_tables() -> None:
    out = H.verify(*load())
    assert out["ok"] is True and "pending" not in out
    assert out["読んだ回数"] == 2
    assert out["2 回目の sha256"] == out["sha256"]
    assert set(out["入れ替えた 3 枚の sha256"].values()) == {out["sha256"]}
    k = out["件数の検算"]
    assert k["合計"] == 17 == k["分母(足す行の件数)"]
    assert k["6 値"] == 14 == k["分母(6 値が付いた件の数)"]
    assert k["rule ごとの内訳の合計"] == k["次元の値ごとの内訳の合計"] == 17
    assert k["別枠の理由ごとの合計"] == 3
    assert k["① の言い方ごとの合計"] == 6
    print("[measure] 2 回 + 3 通りの入れ替えで読み直し: 判定部分の sha256 は 4 回とも"
          f" 同じ(4/4 一致、先頭 12 桁 {out['sha256'][:12]})")
    print("[measure] 件数の検算: 6 値 + 別枠の合計 17 = 足す行の件数 17、6 値 14 = "
          "6 値が付いた件 14、rule ごとと次元の値ごとの内訳の合計も 17")


# ---------------------------------------------------------------- 決定論

def test_order_of_rows_does_not_change_the_result() -> None:
    rows, adds, declares = load()
    first = H.edge_close(rows, adds, declares)
    for how in H.SWAPS:
        t = H.edge_close(rows.swapped(how), adds.swapped(how), declares.swapped(how))
        assert t.report.ok
        assert t.sha256() == first.sha256()
        assert t.seven() == first.seven()
    with pytest.raises(H.ReadError):
        H.swap_rows([1, 2, 3], "合成の未登録の入れ替え方(架空)")


def test_judgement_bytes_have_no_clock_or_path() -> None:
    t = pull()
    text = t.judgement_bytes().decode("utf-8")
    assert "C:\\" not in text and "/tools/" not in text
    assert ":" in text and "\t" in text
    for word in ("2026-10", "T0", "Z", "host"):
        if word == "2026-10":
            continue        # 入力の日付そのものは入る(時計由来の値ではない)
        assert word not in text
    # 絶対パスは「読んだ条件」にしか出ない(判定部分には入らない)
    assert str(FIX) in t.read_condition()[H.SCOPE_KEYS[0]]


def test_inputs_are_never_rewritten() -> None:
    files = sorted(p for p in FIX.rglob("*.csv"))
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    H.verify(*load())
    pull()
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    assert before == after
    print(f"[measure] 読む前後で入力 {len(files)} ファイルの sha256 が同じ")


# ---------------------------------------------------------------- 止まる

def test_nine_table_reason_codes_are_all_reachable() -> None:
    """表の側の理由コード 9 個すべてに、崩した表で道がある。"""
    hit: set[str] = set()
    for name in sorted({**M.kowashita_rows(), **M.kowashita_declares()}):
        kind = name.split("_")[0]
        try:
            t = pull(**{kind: BROKEN / f"{name}.csv"})
        except H.ReadError:
            continue
        if t.report.ok:
            continue
        hit |= set(t.stopped())
        assert t.judged == ()
        assert all(v == 0 for v in t.seven().values())
        assert t.counts()["読んだか"].startswith("読んでいない")
        with pytest.raises(RuntimeError):
            t.sha256()
    assert hit == set(H.TABLE_REASONS)
    assert len(H.STOP_REASONS) == 12 and len(H.VERIFY_REASONS) == 3
    print(f"[measure] 止まる理由コードは {len(H.STOP_REASONS)} 個(表の側 "
          f"{len(H.TABLE_REASONS)} + verify 3)で、表の側 {len(H.TABLE_REASONS)} 個"
          "すべてに崩した表で道がある。止まった表では 6 値は全て 0 で、一覧も全て 0 件")


def test_three_verify_reason_codes_are_all_reachable(monkeypatch) -> None:
    rows, adds, declares = load()
    real = H.edge_close

    def once(*args, **kwargs):      # 2 回目だけ 1 件消して返す
        t = real(*args, **kwargs)
        once.n += 1
        if once.n == 2 and t.report.ok:
            return H.Tally(report=t.report, judged=t.judged[1:], rows=t.rows,
                           adds=t.adds, declares=t.declares)
        return t
    once.n = 0
    monkeypatch.setattr(H, "edge_close", once)
    out = H.verify(rows, adds, declares)
    assert out["ok"] is False
    got = {p["理由コード"] for p in out["pending"]}
    assert got & set(H.VERIFY_REASONS)
    assert H.STOP_REASONS[9] in H.VERIFY_REASONS


def test_broken_tables_are_counted() -> None:
    stopped, unread = [], []
    for name in sorted({**M.kowashita_rows(), **M.kowashita_adds(),
                        **M.kowashita_declares()}):
        kind = name.split("_")[0]
        try:
            t = pull(**{kind: BROKEN / f"{name}.csv"})
        except H.ReadError:
            unread.append(name)
            continue
        assert not t.report.ok, name
        stopped.append(name)
    assert len(stopped) == 11 and len(unread) == 25
    assert len(stopped) + len(unread) == 36
    print(f"[measure] 崩した表 36 枚の内訳 = 1 件も仕分けずに止まる {len(stopped)} 枚 / "
          f"表として読めない {len(unread)} 枚")


# ---------------------------------------------------------------- 持たせていないもの

def code_without_strings(path: Path) -> str:
    """文字列リテラルとコメントを外したコード(語が「出力の文」でなく経路かを見る)。"""
    out: list[str] = []
    for tok in tokenize.generate_tokens(io.StringIO(
            path.read_text(encoding="utf-8")).readline):
        if tok.type in (tokenize.STRING, tokenize.COMMENT):
            continue
        out.append(tok.string)
    return " ".join(out)


def test_implementation_has_no_clock_no_float_no_network() -> None:
    src = ROOT / "edge_close.py"
    bare = code_without_strings(src)
    for name in MOTANAI:
        assert name not in bare, name
    tree = ast.parse(src.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imported |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            imported.add(n.module.split(".")[0])
    assert imported == {"__future__", "argparse", "csv", "hashlib", "json", "re",
                        "sys", "dataclasses", "datetime", "pathlib"}
    # datetime は入れているが、読むのは入力の日付だけ(date / timedelta の 2 つ)
    names = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
             and n.module == "datetime" for a in n.names}
    assert names == {"date", "timedelta"}
    print(f"[measure] 部品が import している module は {len(imported)} 個で、"
          "現在時刻を読む呼び出し・float / eval / exec / round / subprocess / random"
          " / platform / 通信 の呼び出しは 0 件(datetime は date と timedelta の"
          " 2 つだけを入力の日付計算に使う)")


def test_no_judgement_words_in_output_or_code() -> None:
    """件数・一覧の側に良し悪しの語が無い。

    「重なりを誤りと呼ばない」のような**持たせていないことの説明**は str の値として在るので、
    数える側(件数・内訳・一覧)だけを取り出して見る。説明文が在ること自体は別に assert する。
    """
    t = pull()
    counts = t.counts()
    data = {k: v for k, v in counts.items() if not isinstance(v, str)}
    body = json.dumps({**data, "一覧": t.listed(), "別枠": t.asides(),
                       "次元の値ごと": t.by_dims()}, ensure_ascii=False)
    bare = code_without_strings(ROOT / "edge_close.py")
    for word in KINSOKU + KEIYOU + NANORI:
        assert word not in body, word
        assert word not in bare, word
    assert "重なりを誤りと呼ばない" in counts
    assert "新設と名乗らない" in counts
    print(f"[measure] 良し悪しを指す語 {len(KINSOKU)} 個と形容の語 {len(KEIYOU)} 個、"
          f"名乗りの語 {len(NANORI)} 個は、件数と一覧にも、文字列を外したコードにも"
          " 0 件(「重なりを誤りと呼ばない」のような説明文は別に在る)")


def test_counts_have_no_ratio_and_no_rank() -> None:
    c = pull().counts()
    assert not any(str(k).endswith(("率", "割合", "点数", "スコア", "順位")) for k in c)
    assert not any(isinstance(v, float) for v in c.values())
    for row in c["rule ごと"]:
        assert not any(isinstance(v, float) for v in row.values())
        assert "率" not in "".join(str(k) for k in row)


def test_gap_allowed_column_is_recorded_but_not_used() -> None:
    """隙間を許すかの欄は記録するだけ。**全部裏返しても 6 値も sha256 も動かない。**"""
    rows, adds, declares = load()
    first = H.edge_close(rows, adds, declares)
    flipped = H.Declares(items=tuple(
        H.Rule(rule_id=r.rule_id, end_included=r.end_included, edge_unit=r.edge_unit,
               gap_allowed=(H.YURUSANAI if r.gap_allowed == H.YURUSU else H.YURUSU),
               reason_code=r.reason_code or M.G1,
               unspecified_mark=r.unspecified_mark, close_known=r.close_known,
               priorities=r.priorities, new_label=r.new_label, source=r.source)
        for r in declares.items), pending=declares.pending, path=declares.path)
    after = H.edge_close(rows, adds, flipped)
    assert after.report.ok
    assert after.seven() == first.seven()
    assert after.sha256() == first.sha256()
    print("[measure] 宣言表の 隙間を許すか を全部裏返しても、6 値も判定部分の sha256 も"
          " 1 つも動かない(= 判定に使っていない)")


def test_new_label_is_copied_only_when_declared() -> None:
    """④ に語を写すのは、宣言表の欄が埋まっているときだけ。"""
    rows, adds, declares = load()
    first = H.edge_close(rows, adds, declares)
    assert all(j.label == "" for j in first.judged)
    word = "合成の宣言された語(架空)"
    filled = H.Declares(items=tuple(
        H.Rule(rule_id=r.rule_id, end_included=r.end_included, edge_unit=r.edge_unit,
               gap_allowed=r.gap_allowed, reason_code=r.reason_code,
               unspecified_mark=r.unspecified_mark, close_known=r.close_known,
               priorities=r.priorities, new_label=word, source=r.source)
        for r in declares.items), pending=declares.pending, path=declares.path)
    after = H.edge_close(rows, adds, filled)
    labelled = [j for j in after.judged if j.label]
    assert sorted(j.add.add_id for j in labelled) == ["A04", "A05"]
    assert all(j.result == H.KEKKA[3] for j in labelled)
    assert all(j.label == word for j in labelled)
    assert after.seven() == first.seven()       # 値は動かない(写すのは語だけ)


def test_unspecified_mark_is_not_expanded() -> None:
    """未指定の記号は記号のまま鍵に入る(ワイルドカードを展開して当てる経路が無い)。"""
    t = pull()
    e03 = t.rows.of("E03")
    assert e03.dims == f"地域={M.MARK}"
    for j in t.judged:
        assert j.row_id != "E03"


# ---------------------------------------------------------------- 入り口

def test_exit_codes() -> None:
    p = paths()
    args = [str(p["rows"]), str(p["adds"]), str(p["declares"])]
    assert H.main(["check"] + args) == 3            # 重なり・隙間・別枠が在る
    assert H.main(["edges"] + args) == 3
    assert H.main(["verify"] + args) == 0           # 5 つの検証は通る
    broken = [str(BROKEN / "rows_shutten_kuuran.csv"), str(p["adds"]),
              str(p["declares"])]
    assert H.main(["check"] + broken) == 3
    unread = [str(BROKEN / "rows_0gyou.csv"), str(p["adds"]), str(p["declares"])]
    assert H.main(["check"] + unread) == 2


def test_clean_tables_return_zero(tmp_path) -> None:
    """閉じ忘れも閉じすぎも無い 3 枚なら 0 で返る(= 0 は「見つからなかった」の意味)。"""
    rows, adds, declares = H.init(tmp_path)
    # ひな型の A02 は重なるので、開始を既存の終了にそろえた表を作る
    text = adds.read_text(encoding="utf-8").replace("2026-02", "2026-04")
    adds.write_text(text, encoding="utf-8")
    assert H.main(["check", str(rows), str(adds), str(declares)]) == 0
    t = H.edge_close(H.Rows.load(rows), H.Adds.load(adds), H.Declares.load(declares))
    assert t.seven()[H.KEKKA[0]] == 2
    assert t.aside_denominator() == 0


def test_init_writes_three_tables_that_read_back(tmp_path) -> None:
    rows, adds, declares = H.init(tmp_path)
    for p in (rows, adds, declares):
        assert p.exists() and p.read_text(encoding="utf-8").endswith("\n")
    t = H.edge_close(H.Rows.load(rows), H.Adds.load(adds), H.Declares.load(declares))
    assert t.report.ok
    assert sum(t.seven().values()) == 2


# ---------------------------------------------------------------- 出典

def test_sources_point_at_real_lines_in_this_repo() -> None:
    for source, word in REAL_SOURCES.items():
        name, line = source.rsplit(" L", 1)
        text = (PLAN / name).read_text(encoding="utf-8-sig").splitlines()
        assert word in text[int(line) - 1], source


def test_every_row_of_every_fixture_has_a_source() -> None:
    rows, adds, declares = load()
    assert all(r.source for r in rows.items)
    assert all(a.source for a in adds.items)
    assert all(d.source for d in declares.items)


def test_no_real_rates_or_paths_in_fixtures() -> None:
    """合成 fixture に実在の料率・金額・パス・取引先の手がかりを入れない。"""
    for p in sorted(FIX.rglob("*.csv")):
        text = p.read_text(encoding="utf-8")
        assert "C:\\" not in text and "D:\\" not in text
        assert "%" not in text and "円" not in text
        assert "協会けんぽ" not in text and "厚生年金" not in text
