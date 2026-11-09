"""asof_reach のテスト。合成 fixture は `fixtures/` に commit 済(実データは入れない)。

test_measure_* が記事に載せた数値の出どころで、assert で固定している(値が変われば記事も
変える前提)。測っているものは 9 つある。

  (1) 行 19 件が 4 値 13 件 + 行に付く別枠 6 件に分かれ、合計が 2 通りの数え方で戻る側
  (2) **知識時間の経路が在る 10 行のうち、公表日が実値なのは 3 行**という側 = 記事の骨
  (3) **仮置き 3 種が (B) と (C) へ別々に振れる**(種類ごとの内訳)側
  (4) **問いの分母は行とは別**で、8 問のうち答えが返るのが 4 問という側
  (5) **値の名前を全部入れ替えても 4 値が 1 件も動かない**(名前から品質を推測しない)側
  (6) **`開` と記載なしを同じ値にしない**(known_to を替えると行き先が変わる)側
  (7) 2 つの差し替え(同じ日に書き換える / 記号を仮置きに替える)が別の方向へ動く側
  (8) 出力の末尾の「持たせていないもの」が 10 行で、禁則の語が件数の側に無い側
  (9) 止まる理由コード 8 個と、表として読めない 7 通りに道が在る側

(1) の 4 値は、テストの側でも 4 枚の行から直に組み立てて確かめている(部品の judge /
four / extras を呼ばない)。
"""
from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIX = ROOT / "fixtures"
KOWASHITA = FIX / "kowashita"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FIX))
import asof_reach as H  # noqa: E402
import make_fixtures as M  # noqa: E402

SHA = "3ac6ee0053af78b05bcd13066db91ad8677effec8f373991773ec10c654aef4a"

# 良し悪し・直すべき順位・率を指す語(件数と一覧の側に持たせない)
KINSOKU = ("推奨", "順位", "優先度", "点数", "率", "カバー", "正しい側", "健全",
           "重要度", "スコア", "削減", "誤り")

# 出力の末尾に並ぶ「持たせていないもの」(**消す引数も option も無い**)
MOTANAI_KEYS = (
    "公表日を推定しない",
    "取りに行かない",
    "仮置きを実値へ格上げしない",
    "正しい側を決めない",
    "再現できる率を単独で返さない",
    "理由を言い当てない",
    "宣言の文を採点しない",
    "時計を読まない",
    "入力を書き換えない",
    "float を使わない",
)


# ------------------------------------------------------------ 読み込み

def four_tables(rows: str = "rows_a.csv", grades: str = "grades_a.csv",
                asks: str = "asks_a.csv", claims: str = "claims_a.csv"):
    """fixtures(と kowashita)から 4 枚を読む。"""
    def path(name: str) -> Path:
        return (KOWASHITA / name) if (KOWASHITA / name).exists() else (FIX / name)

    return (H.Rows.load(path(rows)), H.Grades.load(path(grades)),
            H.Asks.load(path(asks)), H.Claims.load(path(claims)))


def table(**kw) -> H.Table:
    return H.asof_reach(*four_tables(**kw))


# ------------------------------------------------------------ テスト側の別実装

def classify(row: list[str], grades: list[list[str]],
             rows: list[list[str]]) -> str:
    """行 1 件の 4 値 / 別枠を、テストの側で行から直に出す(部品の judge を呼ばない)。"""
    rid, name, vf, vt, kf, kt, grade, announced, reason, source = row
    reg = {r[0]: (r[1], r[2]) for r in grades}
    means = reg.get(grade, ("(登録表の外)", "—"))[0]
    requires = reg.get(grade, ("(登録表の外)", "—"))[1]

    def date(s: str):
        import datetime as dt
        if s in ("—", "", "開"):
            return None
        try:
            return dt.date.fromisoformat(s)
        except ValueError:
            return None

    if not source:
        return H.BETSUWAKU[0]
    if grade not in reg:
        return H.BETSUWAKU[1]
    if requires == "理由の文字列" and reason in ("—", ""):
        return H.BETSUWAKU[2]
    k, v = date(kf), date(vf)
    if k is not None and v is not None and k > v and means in H.KARIOKI:
        return H.BETSUWAKU[3]
    if means == "実値" and announced in ("—", ""):
        return H.BETSUWAKU[4]
    end = date(kt)
    if end is not None:
        later = [r for r in rows if r[0] != rid and r[1] == name
                 and date(r[4]) is not None and date(r[4]) >= end]
        if not later:
            return H.BETSUWAKU[5]
    if kf in ("—", "") or kt in ("—", "") or means == "不明":
        return H.VALUES[3]
    if k == v:
        return H.VALUES[1]
    if means == "実値":
        return H.VALUES[0]
    return H.VALUES[2]


def test_4値はテスト側の別実装と一致する() -> None:
    t = table()
    mine = {r[0]: classify(r, M.GRADES, M.ROWS) for r in M.ROWS}
    assert {x.row_id: x.value for x in t.graded} == mine


# ------------------------------------------------------------ (1)

def test_measure_19_rows_split_into_four_values_and_six_extras() -> None:
    t = table()
    assert t.report.ok is True
    assert len(t.rows.items) == 19 and len(t.grades.items) == 5
    assert len(t.asks.items) == 9 and len(t.claims.items) == 3
    assert t.denominator() == 19
    four, extras = t.four(), t.extras()
    assert four == {H.VALUES[0]: 3, H.VALUES[1]: 4, H.VALUES[2]: 3,
                    H.VALUES[3]: 3}
    assert extras == {k: 1 for k in H.ROW_BETSUWAKU}
    assert sum(four.values()) == 13 and sum(extras.values()) == 6
    assert sum(four.values()) + sum(extras.values()) == t.denominator()
    assert sum(int(r["行の件数"]) for r in t.by_grade()) == 19
    assert len(H.BETSUWAKU) == 7 and len(H.ROW_BETSUWAKU) == 6
    print("[measure] rows_a / grades_a / asks_a / claims_a: 行 19 行 / "
          "品質の登録 5 行 / 問い 9 行 / 宣言 3 行")
    print(f"[measure] 行の分母は 19 件、4 値は "
          f"{json.dumps({k[:3]: v for k, v in four.items()}, ensure_ascii=False)}"
          f"(合計 13 件)")
    print("[measure] 行に付く別枠は 6 枠が 1 件ずつ(合計 6 = 19 - 13)。別枠は 7 枠"
          "あるが、7 枠目は分母が問いなので行の合計に混ぜない")


# ------------------------------------------------------------ (2) 記事の骨

def test_measure_only_three_rows_have_a_real_announcement_date() -> None:
    t = table()
    two = t.two_ways()
    assert two["分母(知識時間の経路が在る行)"] == 10
    assert two["品質が 実値 の件数"] == 3
    assert two["境界日が別の日である件数"] == 6
    assert two["差"] == 3
    assert t.real_same_day() == 0
    assert two["差"] == t.four()[H.VALUES[2]] - t.real_same_day()
    # **率の 1 値を返す列が無い**(counts の key に率の語が無い)
    flat = json.dumps({k: v for k, v in t.counts().items()
                       if k not in MOTANAI_KEYS}, ensure_ascii=False)
    for word in ("カバー率", "割合", "%"):
        assert word not in flat
    print("[measure] 知識時間の経路が在る行は 10 件で、そのうち公表日が実値なのは 3 件。"
          "残り 7 件は仮置き(同じ日の (B) 4 件 + 別の日の (C) 3 件)")
    print("[measure] 2 通りの数え方は 品質が 実値 3 件 と 境界日が別の日 6 件 で、"
          "差は 3 = (C) の件数 3 − (B) のうち品質が 実値 0。率の 1 値を出す key は 0 件")


def test_measure_boundary_days() -> None:
    t = table()
    days = t.boundary_days()
    assert days[H.SAME_DAY] == 4 and days[H.OTHER_DAY] == 14
    assert days[H.UNCOUNTABLE] == 1
    assert days["日数が出た行"] == 18
    assert days["日数の小さい方"] == -61 and days["日数の大きい方"] == 849
    got = {x.row_id: x.days for x in t.graded}
    assert got["R01"] == "28" and got["R02"] == "60" and got["R03"] == "849"
    assert got["R08"] == "19" and got["R12"] == H.UNCOUNTABLE
    assert got["R17"] == "-61"
    # **平均を出す経路が無い**(日数は小さい方と大きい方だけ)
    assert "平均" not in json.dumps(days, ensure_ascii=False)
    print("[measure] 境界日は 同じ日 4 件 / 別の日 14 件 / 数えられない 1 件(合計 19)。"
          "日数は -61 日から 849 日で、負の 1 件が遡及の形(別枠へ出た行)")
    print("[measure] 日数は整数の日差で返る(28 / 60 / 849 / 19 / -61 日)。"
          "平均を出す key は 0 件、float の呼び出しも 0 件")


# ------------------------------------------------------------ (3) 仮置き 3 種

def test_measure_three_kinds_of_placeholder_behave_differently() -> None:
    t = table()
    by_grade = {r["品質の意味"]: r for r in t.by_grade()}
    assert [r["品質の意味"] for r in t.by_grade()] == list(H.MEANS) + [
        H.UNREGISTERED]
    assert by_grade[H.MEANS[0]]["行の件数"] == 5      # 実値
    assert by_grade[H.MEANS[1]]["行の件数"] == 7      # 施行日で仮置き
    assert by_grade[H.MEANS[2]]["行の件数"] == 2      # 範囲の先頭で仮置き
    assert by_grade[H.MEANS[3]]["行の件数"] == 3      # 公布日で仮置き
    assert by_grade[H.MEANS[4]]["行の件数"] == 1      # 不明
    assert by_grade[H.UNREGISTERED]["行の件数"] == 1
    # 仮置き 3 種の行き先が、種類ごとに別々に割れる
    assert [by_grade[m]["内訳"][H.VALUES[1]] for m in H.KARIOKI] == [2, 1, 1]
    assert [by_grade[m]["内訳"][H.VALUES[2]] for m in H.KARIOKI] == [1, 1, 1]
    assert by_grade[H.MEANS[3]]["内訳"][H.BETSUWAKU[3]] == 1
    assert by_grade[H.MEANS[0]]["内訳"][H.VALUES[0]] == 3
    # **実値の行が (A) だけになるとは限らない**(別枠へ出た実値が 2 件ある)
    assert by_grade[H.MEANS[0]]["内訳"][H.BETSUWAKU[4]] == 1
    assert by_grade[H.MEANS[0]]["内訳"][H.BETSUWAKU[5]] == 1
    print("[measure] 品質の意味ごとの行数は 実値 5 / 施行日で仮置き 7 / "
          "範囲の先頭で仮置き 2 / 公布日で仮置き 3 / 不明 1 / 登録表の外 1(合計 19)")
    print("[measure] 仮置き 3 種の行き先は別々に割れる: (B) へ 2 / 1 / 1 件、"
          "(C) へ 1 / 1 / 1 件、公布日で仮置きの 1 件だけが遡及の形で別枠へ")
    print("[measure] 実値 5 件のうち (A) は 3 件で、2 件は別枠(別出典の公表日が空 1 件 / "
          "known_to が閉じているのに後続行が無い 1 件)")


# ------------------------------------------------------------ (4) 問いの側

def test_measure_asks_have_their_own_denominator() -> None:
    t = table()
    reach = t.reach_counts()
    assert reach["問いの件数"] == 9
    assert reach[f"別枠「{H.ASK_BETSUWAKU}」"] == 1
    assert reach["その問い id"] == ["Q09"]
    assert reach["道が付いた問い"] == 8
    assert reach["3 値"] == {"出る": 2, "出ない": 2, "言えない": 4}
    assert sum(reach["3 値"].values()) == 8
    assert reach["答えが乗っているもの"] == {
        H.RESTS_REAL: 1, H.RESTS_VALID: 3, H.RESTS_SAME: 1, H.RESTS_KARIOKI: 1,
        H.RESTS_NONE: 2, H.RESTS_EXTRA: 0}
    got = {x.ask_id: (x.verdict, x.rests_on) for x in t.reaches}
    assert got["Q01"] == ("出ない", H.RESTS_REAL)
    assert got["Q04"] == ("言えない", H.RESTS_SAME)
    assert got["Q06"] == ("言えない", H.RESTS_KARIOKI)
    assert "Q09" not in got
    # **問いの分母は行の分母と別**(足し合わせる key が無い)
    assert reach["問いの件数"] != t.denominator()
    print("[measure] 問いは 9 件で、行の台帳に無い行 id を指す 1 件(Q09)は別枠。"
          "道が付いた 8 件の答えは 出る 2 / 出ない 2 / 言えない 4")
    print("[measure] 答えが乗っているものは 実値の公表日 1 / 有効時間の端 3 / "
          "同じ日の境界 1 / 仮置きの公表日 1 / 知識時間の経路が無い 2(合計 8)。"
          "= 8 問のうち公表時点の列が答えを支えたのは 1 問")


# ------------------------------------------------------------ (5) 名前から推測しない

def test_measure_value_names_do_not_change_anything() -> None:
    t = table()
    rows = [list(r) for r in M.ROWS]
    for i, r in enumerate(rows):
        r[1] = f"ぜんぜん違う名前 {len(rows) - i}(架空)"
    after = H.asof_reach(H.Rows(rows), *four_tables()[1:])
    assert H.moved(t, after) == []
    assert after.sha256() == t.sha256() == SHA
    assert [x.value_name for x in after.graded] != [x.value_name for x in t.graded]
    print("[measure] 値の名前を 19 件すべて別の文字に入れ替えても、4 値が動いた行は "
          "0 件で、判定部分の sha256 も同じ(= 品質は登録表からしか取らない)")


# ------------------------------------------------------------ (6) 開 と記載なし

def test_measure_open_end_and_unwritten_end_are_different() -> None:
    t = table()
    before = {x.row_id: x.value for x in t.graded}
    assert before["R01"] == H.VALUES[0] and before["R13"] == H.VALUES[3]
    # `開` → 記載なし にすると、その行だけが (A) から (D) へ移る
    rows = [list(r) for r in M.ROWS]
    for r in rows:
        if r[0] == "R01":
            r[5] = H.NO_MARK
    after = H.asof_reach(H.Rows(rows), *four_tables()[1:])
    assert H.moved(t, after) == ["R01"]
    assert {x.row_id: x.value for x in after.graded}["R01"] == H.VALUES[3]
    # `開` → 日付で閉じる にすると、後続行が無いので別枠へ移る
    rows = [list(r) for r in M.ROWS]
    for r in rows:
        if r[0] == "R01":
            r[5] = "2026-12-01"
    closed = H.asof_reach(H.Rows(rows), *four_tables()[1:])
    assert H.moved(t, closed) == ["R01"]
    assert {x.row_id: x.value for x in closed.graded}["R01"] == H.BETSUWAKU[5]
    print("[measure] R01 の known_to を 開 → 記載なし にすると、その行だけが (A) から "
          "(D) へ移る(ほかで動いた行は 0 件)。`開` と記載なしは同じ値にならない")
    print("[measure] 同じ欄を 開 → 日付で閉じる にすると、同じ値の名前の後続行が"
          "無いので別枠へ移る(1 件だけ)。3 通りの書き方が 3 通りの行き先になる")


# ------------------------------------------------------------ (7) 2 つの差し替え

def test_measure_two_probes_move_in_different_directions() -> None:
    t = table()
    plan = H.probe_plan(t)
    assert plan == "R01"
    day = H.probe_same_day(*four_tables(), plan)
    assert H.moved(t, day) == ["R01"]
    assert {x.row_id: x.value for x in day.graded}["R01"] == H.VALUES[1]
    assert day.four()[H.VALUES[0]] == 2 and day.four()[H.VALUES[1]] == 5
    assert int(day.two_ways()["差"]) == 2 and day.real_same_day() == 1
    assert int(day.two_ways()["差"]) == (day.four()[H.VALUES[2]]
                                        - day.real_same_day())
    grade = H.karioki_grade(four_tables()[1])
    assert grade == "記号 4"
    swap = H.probe_grade(*four_tables(), plan, grade)
    assert H.moved(t, swap) == ["R01"]
    assert {x.row_id: x.value for x in swap.graded}["R01"] == H.VALUES[2]
    assert int(swap.two_ways()["差"]) == 4
    assert swap.two_ways()["品質が 実値 の件数"] == 2
    before = hashlib.sha256((FIX / "rows_a.csv").read_bytes()).hexdigest()
    assert before == hashlib.sha256((FIX / "rows_a.csv").read_bytes()).hexdigest()
    print("[measure] 同じ日に書き換える: R01 の known_from を valid_from と同じ日に"
          "すると R01 の 1 件だけが (A) → (B) へ移る((A) 3 → 2 件 / (B) 4 → 5 件、"
          "2 通りの数え方の差 3 → 2)")
    print("[measure] 記号を仮置きに替える: R01 の品質を 記号 4(公布日で仮置き)に"
          "すると R01 の 1 件だけが (A) → (C) へ移る(実値の件数 3 → 2 件、"
          "差 3 → 4)。同じ 1 行が、どちらを触ったかで別の方向へ動く")
    print("[measure] 同じ日に書き換えた後は (B) のうち品質が 実値 が 1 件になり、"
          "差の検算の補正項がそこで初めて 0 でなくなる(2 = 3 − 1)")


# ------------------------------------------------------------ (8) 持たせていないもの

def test_measure_motanai_is_ten_lines() -> None:
    t = table()
    counts = t.counts()
    assert tuple(H.MOTANAI) == MOTANAI_KEYS and len(MOTANAI_KEYS) == 10
    for key in MOTANAI_KEYS:
        assert counts[key] == H.MOTANAI[key]
    numeric_part = {k: v for k, v in counts.items() if k not in MOTANAI_KEYS}
    flat = json.dumps(numeric_part, ensure_ascii=False)
    for word in KINSOKU:
        assert word not in flat, word
    for row in t.listed() + t.reach_listed():
        for word in KINSOKU:
            assert word not in json.dumps(row, ensure_ascii=False), word
    # 宣言の台帳は文を写すだけで、採点の欄が無い
    claims = t.claim_rows()
    assert len(claims) == 3
    assert [c["主張する範囲"] for c in claims] == [H.SCOPES[2], H.SCOPES[1],
                                                   H.SCOPES[0]]
    assert all(c["文(verbatim)"] == x.text
               for c, x in zip(claims, sorted(t.claims.items,
                                              key=lambda y: y.claim_id)))
    print("[measure] 出力の末尾の「持たせていないもの」は 10 行で、消す引数も option も"
          f"無い。禁則の語({len(KINSOKU)} 語)を含む key と値は 0 件")
    print("[measure] 宣言の台帳は 3 件で、主張する範囲は 記載なし / 一部 / 全行。"
          "文は verbatim の写しで、正しいかを返す欄は 0 件")


# ------------------------------------------------------------ (9) 止まる 8 + 読めない 7

def test_measure_eight_stop_reasons_all_reachable() -> None:
    seen: dict[str, list[str]] = {}
    cases = [
        {"grades": "grades_出典が空.csv"},
        {"rows": "rows_行idの重複.csv"},
        {"grades": "grades_意味が決めた外.csv"},
        {"grades": "grades_要求する欄が決めた外.csv"},
        {"rows": "rows_日付がISOでない.csv"},
        {"claims": "claims_範囲が決めた外.csv"},
        {"asks": "asks_as_ofが空.csv"},
        {"grades": "grades_登録表が空.csv"},
    ]
    for kw in cases:
        t = table(**kw)
        assert t.report.ok is False and t.report.pending
        assert t.denominator() == 0 and t.graded == () and t.reaches == ()
        assert t.four() == {k: 0 for k in H.VALUES}
        assert t.extras() == {k: 0 for k in H.ROW_BETSUWAKU}
        with pytest.raises(RuntimeError):
            t.judgement_bytes()
        for p in t.report.pending:
            seen.setdefault(p.reason, []).append(str(kw))
    assert sorted(seen) == sorted(H.TABLE_REASONS)
    assert len(H.TABLE_REASONS) == 8
    print("[measure] 止まる理由コードは 8 個で、崩した表 8 枚すべてに道が在る(8/8)。"
          "止まった表は 4 値を 1 件も返さない")


def test_measure_seven_unreadable_tables() -> None:
    cases = [{"rows": "rows_列が足りない.csv"}, {"rows": "rows_行が無い.csv"},
             {"rows": "rows_行idが空.csv"}, {"rows": "rows_期間の端が逆.csv"},
             {"grades": "grades_記号が2行.csv"},
             {"asks": "asks_問いidが2行.csv"},
             {"claims": "claims_宣言idが2行.csv"}]
    msgs: list[str] = []
    for kw in cases:
        with pytest.raises(H.ReadError) as e:
            four_tables(**kw)
        msgs.append(str(e.value))
    assert len(msgs) == 7 and len(set(msgs)) == 7
    print("[measure] 表として読めない崩し方は 7 通り(列が足りない / 行が無い / "
          "行 id が空 / 期間の端が逆 / 品質の登録が同じ記号で 2 行 / 問い id が 2 行 / "
          "宣言 id が 2 行)で、7 通りとも別の文で止まる")


# ------------------------------------------------------------ 決定論

def test_measure_judgement_is_deterministic() -> None:
    t = table()
    again = table()
    shas = [t.sha256(), again.sha256()]
    for how in H.SWAPS:
        rows, grades, asks, claims = four_tables()
        s = H.asof_reach(rows.swapped(how), grades.swapped(how),
                         asks.swapped(how), claims.swapped(how))
        shas.append(s.sha256())
    assert len(set(shas)) == 1 and shas[0] == SHA
    body = t.judgement_bytes().decode("utf-8")
    for word in ("読んだ条件", str(ROOT), ".csv", "合成の値", M.REASON):
        assert word not in body
    out = H.verify(*four_tables())
    assert out["ok"] is True
    assert out["二度走りの判定部分が同一"] is True
    assert out["行順を入れ替えても同一"] == {k: True for k in H.SWAPS}
    assert out["合計が合う"] is True
    assert out["同じ日に書き換える"]["ok"] is True
    assert out["記号を仮置きに替える"]["ok"] is True
    print("[measure] 2 回 + 行順の入れ替え 3 通りで読み直し: 判定部分の sha256 は 5 回とも"
          f" 同じ(5/5 一致、先頭 12 桁 {shas[0][:12]})")
    print("[measure] 判定部分に絶対パス・ファイル名・値の名前・理由の文字は入らない。"
          "verify は 5 つとも通る")


def test_measure_no_float_no_clock_no_network() -> None:
    src = (ROOT / "asof_reach.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    modules: set[str] = set()
    calls: list[str] = []
    hashed: list[str] = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            modules |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            modules.add(n.module.split(".")[0])
        elif isinstance(n, ast.Call):
            f = n.func
            name = f.id if isinstance(f, ast.Name) else (
                f.attr if isinstance(f, ast.Attribute) else "")
            calls.append(name)
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) \
                    and f.value.id == "hashlib":
                hashed.append(f.attr)
    assert modules == {"__future__", "argparse", "csv", "datetime", "hashlib",
                       "io", "json", "sys", "dataclasses", "pathlib"}
    for bad in ("eval", "exec", "float", "round", "now", "today", "urlopen",
                "request", "run", "Popen", "random", "mean", "compile"):
        assert bad not in calls, bad
    assert hashed == ["sha256"]
    assert "__import__" not in calls
    print(f"[measure] 部品が import している module は {len(modules)} 個で、eval / exec / "
          "float / round / 現在時刻 / subprocess / random / 平均 / 通信 の呼び出しは 0 件")
    print("[measure] hashlib.sha256 を呼ぶのは 1 か所(判定部分の指紋)だけ")


def test_入力は1文字も書き換わらない() -> None:
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(FIX.glob("*.csv"))}
    t = table()
    H.verify(*four_tables())
    H.probe_same_day(*four_tables(), "R01")
    H.probe_grade(*four_tables(), "R01", "記号 4")
    assert t.report.ok
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(FIX.glob("*.csv"))}
    assert after == before and len(before) == 4


def test_CLI_の終了コード(tmp_path: Path) -> None:
    args = ["check", str(FIX / "rows_a.csv"), str(FIX / "grades_a.csv"),
            str(FIX / "asks_a.csv"), str(FIX / "claims_a.csv")]
    assert H.main(args) == 3            # 別枠と (B)(C)(D) が在る
    assert H.main(["report"] + args[1:]) == 3
    assert H.main(["verify"] + args[1:]) == 0
    assert H.main(["init", str(tmp_path / "ひな型")]) == 0
    made = sorted(p.name for p in (tmp_path / "ひな型").glob("*.csv"))
    assert len(made) == 4
    # ひな型をそのまま通すと、止まらずに 4 値が付く
    d = tmp_path / "ひな型"
    t = H.asof_reach(H.Rows.load(d / "行の台帳.csv"),
                     H.Grades.load(d / "品質の登録表.csv"),
                     H.Asks.load(d / "問いの台帳.csv"),
                     H.Claims.load(d / "宣言の台帳.csv"))
    assert t.report.ok and t.denominator() == 2
    bad = ["check", str(KOWASHITA / "rows_行が無い.csv")] + args[2:]
    assert H.main(bad) == 2             # 表として読めない
