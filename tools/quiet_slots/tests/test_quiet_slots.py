"""quiet_slots のテスト。合成 fixture は `fixtures/` に commit 済(実データ・実在の値は入れない)。

test_measure_* が記事に載せた数値の出どころで、assert で固定している(値が変われば記事も変える前提)。
測っているものは 8 つある。

  (1) 問い 5 件 × 欄 10 件 = 組 50 件が 4 値 + 別枠 3 + 手元に在る に分かれ、分母の内訳が付く側
  (2) **空でも止まらない欄が 9 組、そのうち `2 行以上が当たる` が 2 組**という側 = 記事の骨
  (3) **宣言が無い欄が 8 組ある**側(`as_of` に当たる知識時点の欄と、次元の 1 つ)
  (4) **同じ欄に 2 通りの宣言が在る欄が 1 つ(4 組)**で、4 値に入らず別枠へ出る側
  (5) 出典が空の問いの 10 組が 4 値に 1 つも入らない側
  (6) 空にできるかを `できる` → `宣言なし` に替えると、その欄の組だけ (B) → (D) へ移る側
  (7) 行の在り方の行数を 1 → 2 に替えると、その組の印だけが移り 4 値は動かない側
  (8) 出力の末尾の「持たせていないもの」が 12 行で、禁則の語が件数の側に 1 つも無い側

(1) の 4 値は、テストの側でも 4 枚の行から直に組み立てて確かめている(部品の judge /
four を呼ばず、fixture の行から別に分類する)。
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FIX))
import quiet_slots as H  # noqa: E402
import make_fixtures as M  # noqa: E402

# 正しさ・推奨・量を指す語(件数と一覧の側に持たせない = 型 B1 の forbidden の物理形)
KINSOKU = ("正しい埋め方", "推奨", "既定値", "一致率", "割合", "削減", "トークン",
           "成功率", "健全", "違反", "原因", "厚い", "薄い")

# 出力の末尾に並ぶ「持たせていないもの」(**消す引数も option も無い**)
MOTANAI_KEYS = (
    "空白を推測で埋めない",
    "CLI を呼ばない",
    "欄に値を入れない",
    "行数は数え上げで、引いた結果ではない",
    "トークン数・削減量を出さない",
    "省略の正否を決めない",
    "どの問いを道具に回すべきか決めない",
    "入力を下へ辿らない",
    "返り値の側を見ない",
    "行の中身の値を読まない",
    "時計を読まない",
    "入力を書き換えない",
)

# 持たせていない呼び出し(動く側のコードに 1 つも無いことを見る)
MOTANAI_CALLS = ("eval", "exec", "round", "float", "now", "today", "time",
                 "Popen", "check_output", "random", "choice", "shuffle",
                 "mean", "median", "urlopen", "read_bytes", "ratio")

LOADERS = (H.Asks.load, H.Slots.load, H.Shapes.load, H.Exits.load)
NORMAL = ("asks_a", "slots_a", "shapes_a", "exits_a")


def path_of(name: str) -> Path:
    return FIX / f"{name}.csv" if name in NORMAL else FIX / "kowashita" / f"{name}.csv"


def four_tables(a: str = "asks_a", s: str = "slots_a", p: str = "shapes_a",
                e: str = "exits_a"):
    names = (a, s, p, e)
    return tuple(LOADERS[i](path_of(names[i])) for i in range(4))


def pull(**kw) -> H.Table:
    return H.quiet_slots(*four_tables(**kw))


def reasons_of(t: H.Table) -> set[str]:
    return {x.reason for x in t.report.pending}


def cell_of(t: H.Table, name: str) -> H.Cell:
    return next(c for c in t.cells if c.name == name)


# ---------------------------------------------------------------- 別実装(テスト側)

def expect_cells() -> dict[str, tuple[str, str]]:
    """4 枚の行から (判定, 印) を別に出す(部品の judge / four / counts を呼ばない)。"""
    decls: dict[str, list[list[str]]] = {}
    for row in M.SLOTS:
        decls.setdefault(row[0], []).append(row)
    shapes = {(row[0], row[1]): int(row[2]) for row in M.SHAPES}
    names = sorted({r[0] for r in M.SLOTS}
                   | {n for r in M.ASKS for n in r[3].split("|") if n}
                   | {r[1] for r in M.SHAPES})
    out: dict[str, tuple[str, str]] = {}
    for ask in sorted(M.ASKS, key=lambda r: r[0]):
        held = [n for n in ask[3].split("|") if n]
        for name in names:
            key = f"{ask[0]}>{name}"
            if not ask[4]:
                out[key] = (H.BETSUWAKU[2], "")
                continue
            here = decls.get(name, [])
            if not here:
                out[key] = (H.BETSUWAKU[1], "")
                continue
            if len({(r[2], r[3]) for r in here}) > 1:
                out[key] = (H.BETSUWAKU[0], "")
                continue
            if name in held:
                out[key] = (H.AT_HAND, "")
                continue
            emptiable, filler = here[0][2], here[0][3]
            if filler == H.FILLERS[2]:
                out[key] = (H.YOTSU[2], "")
            elif emptiable == H.EMPTIABLE[0]:
                out[key] = (H.YOTSU[0], "")
            elif emptiable == H.EMPTIABLE[2]:
                out[key] = (H.YOTSU[3], "")
            else:
                rows = shapes.get((ask[2], name))
                mark = (H.MARKS[2] if rows is None
                        else (H.MARKS[0] if rows == 1 else H.MARKS[1]))
                out[key] = (H.YOTSU[1], mark)
    return out


# ---------------------------------------------------------------- 測る側

def test_measure_50_pairs_split_into_four_values() -> None:
    """(1) 問い 5 件 × 欄 10 件 = 組 50 件が 4 値 + 別枠 3 + 手元に在る に分かれる。"""
    t = pull()
    assert t.report.ok and t.report.pending == ()
    assert (t.report.asks, t.report.slots, t.report.shapes, t.report.exits) == \
        (5, 10, 6, 4)
    assert t.ask_denominator() == 5
    assert t.slot_denominator() == 10
    assert t.pair_denominator() == 50 == 5 * 10
    four, extras = t.four(), t.extras()
    assert four == {H.YOTSU[0]: 7, H.YOTSU[1]: 6, H.YOTSU[2]: 3, H.YOTSU[3]: 8}
    assert extras == {H.BETSUWAKU[0]: 4, H.BETSUWAKU[1]: 4, H.BETSUWAKU[2]: 10}
    assert t.at_hand() == 8
    assert sum(four.values()) + sum(extras.values()) + t.at_hand() == 50
    # 判定は、テストの側で 4 枚の行から別に組み立てたものと 1 組ずつ一致する
    mine = {c.name: (c.value, c.mark) for c in t.cells}
    assert mine == expect_cells()
    assert sum(int(r["組の件数"]) for r in t.by_ask()) == 50
    assert sum(int(r["組の件数"]) for r in t.by_kind()) == 50
    assert len(t.by_kind()) == 6
    print("[measure] asks_a / slots_a / shapes_a / exits_a: 問い 5 行 / 欄の登録 10 行"
          "(9 欄 + 2 通り目 1 行)/ 行の在り方 6 行 / 出口 4 行")
    print(f"[measure] 分母は 問い 5 × 欄 10 = 組 50 件、4 値は "
          f"{json.dumps(four, ensure_ascii=False)}")
    print(f"[measure] 別枠は {json.dumps(extras, ensure_ascii=False)}、"
          f"手元に在ると宣言されている 8。合計 "
          f"{sum(four.values()) + sum(extras.values()) + t.at_hand()} = 組 50")
    print("[measure] 欄の種別ごとは 6 区分(基準日 2 欄 / 選択の次元 3 欄 / 知識時点 1 欄"
          " / 式の入力 1 欄 / 判断の結果 2 欄 / 登録に無い 1 欄)で、内訳の合計 50 = 組 50")


def test_measure_quiet_slots_and_wide_rows() -> None:
    """(2) 空でも止まらない欄が 9 組で、そのうち `2 行以上が当たる` が 2 組。= 記事の骨"""
    t = pull()
    quiet = t.quiet_cells()
    assert len(quiet) == 9
    assert len(quiet) == t.four()[H.YOTSU[1]] + t.four()[H.YOTSU[2]] == 6 + 3
    wide = t.wide_cells()
    assert len(wide) == 2
    assert sorted(c.name for c in wide) == ["Q3>K3", "Q4>K3"]
    assert [c.rows for c in sorted(wide, key=lambda c: c.name)] == [47, 55]
    marks = t.marks()
    assert marks == {H.MARKS[0]: 2, H.MARKS[1]: 2, H.MARKS[2]: 2}
    assert sum(marks.values()) == t.four()[H.YOTSU[1]] == 6
    # 印が付くのは (B) の組だけ
    assert all(bool(c.mark) == (c.value == H.YOTSU[1]) for c in t.cells)
    print("[measure] 空でも止まらない欄は 9 組(空でよいと宣言されている 6 + 人か LLM が"
          "埋めてよい 3)。問いごとは Q1 3 / Q2 2 / Q3 2 / Q4 2 / Q5 0")
    print(f"[measure] 印の内訳は {json.dumps(marks, ensure_ascii=False)}。"
          "`2 行以上が当たる` は 2 組(Q3>K3 が 47 行、Q4>K3 が 55 行)で、"
          "どちらも宣言表の行数の写し")


def test_measure_undeclared_slots_stay_undeclared() -> None:
    """(3) 宣言が無い欄が 8 組ある(`空にできるか` も `誰が埋めてよいか` も `宣言なし`)。"""
    t = pull()
    nashi = [c for c in t.cells if c.value == H.YOTSU[3]]
    assert len(nashi) == 8
    assert sorted({c.slot for c in nashi}) == ["K7", "K8"]
    for c in nashi:
        d = t.slots.decls(c.slot)[0]
        assert (d.emptiable, d.filler) == (H.EMPTIABLE[2], H.FILLERS[3])
        assert c.mark == ""     # **推測で印を付けない**
    # `宣言なし` が `できる` 側へ寄る経路が無い
    assert not [c for c in nashi if c.value == H.YOTSU[1]]
    kinds = {c.slot: t.slots.kind_of(c.slot) for c in nashi}
    assert kinds == {"K7": H.KINDS[2], "K8": H.KINDS[1]}
    print("[measure] どちらの宣言も無い組は 8 件で、欄は 2 つ(K7 = 知識時点、"
          "K8 = 選択の次元)。4 問い × 2 欄 = 8(出典が空の Q5 は別枠なので入らない)")
    print("[measure] 8 組とも印は空(行数の宣言が無くても `できる` 側へ寄せる経路が無い)")


def test_measure_two_declarations_go_to_extras() -> None:
    """(4) 同じ欄に 2 通りの宣言が在る欄は 4 値に入らず別枠へ出る。"""
    t = pull()
    conflict = [c for c in t.cells if c.value == H.BETSUWAKU[0]]
    assert len(conflict) == 4
    assert sorted({c.slot for c in conflict}) == ["K9"]
    decls = t.slots.decls("K9")
    assert len(decls) == 2
    assert {(d.emptiable, d.filler) for d in decls} == {
        (H.EMPTIABLE[0], H.FILLERS[0]), (H.EMPTIABLE[1], H.FILLERS[2])}
    assert all(len(c.sources) == 2 for c in conflict)
    assert t.slots.conflicting("K9") and not t.slots.conflicting("K3")
    # 欄名が登録表に無い組も別枠(= 4 問い × K10)
    missing = [c for c in t.cells if c.value == H.BETSUWAKU[1]]
    assert len(missing) == 4 and sorted({c.slot for c in missing}) == ["K10"]
    assert all(c.kind == H.NOT_REGISTERED for c in missing)
    print("[measure] 同じ欄に 2 通りの宣言が在る組は 4 件で、欄は 1 つ(K9 = 片方が"
          "「空にできない・表から引く」、もう片方が「空でよい・人かLLM」)。"
          "出典は 2 本とも出す")
    print("[measure] 欄名が登録表に無い組は 4 件で、欄は 1 つ(K10 = 問いが挙げた欄名の"
          "うち登録表に行が無いもの)。種別は (登録に無い) のまま")


def test_measure_ask_without_source_counts_nothing() -> None:
    """(5) 出典が空の問いの 10 組は、4 値に 1 つも入らない。"""
    t = pull()
    kara = [c for c in t.cells if c.value == H.BETSUWAKU[2]]
    assert len(kara) == 10
    assert sorted({c.ask.ask_id for c in kara}) == ["Q5"]
    assert all(c.mark == "" and c.sources == () for c in kara)
    q5 = next(r for r in t.by_ask() if r["問い"] == "Q5")
    assert q5["4 値"] == {k: 0 for k in H.YOTSU}
    assert q5["空でも止まらない欄"] == 0 and q5["組の件数"] == 10
    assert q5["出典"] == "(空欄)"
    # 手元に在ると宣言した欄が 1 本あっても、出典が無いので数えない
    assert q5["手元に在ると宣言した欄の数"] == 1 and q5[H.AT_HAND] == 0
    print("[measure] 出典が空の問いは 1 件(Q5)で、その 10 組は 4 値に 1 つも入らない。"
          "手元に在ると宣言した欄が 1 本あっても数えない")
    print("[measure] どの問いも求めていない行の在り方の宣言は 1 件(R9 / K3)、"
          "どの欄も指していない出口の登録は 2 件。どちらも止めずに一覧へ出す")


def test_measure_flipping_one_declaration_moves_one_slot() -> None:
    """(6) `できる` → `宣言なし` に替えると、その欄の組だけ (B) → (D) へ移る。"""
    tables = four_tables()
    first = H.quiet_slots(*tables)
    out = H.declare_probe(*tables, first)
    assert out["合うか"] is True
    assert out["替えた欄"] == "K3" and out["替えた先"] == H.EMPTIABLE[2]
    assert out["移った組"] == ["Q1>K3", "Q3>K3", "Q4>K3"]
    assert out["ほかで動いた組"] == []
    assert out["4 値(後)"][H.YOTSU[1]] == 3 == 6 - 3
    assert out["4 値(後)"][H.YOTSU[3]] == 11 == 8 + 3
    assert out["別枠(前)"] == out["別枠(後)"]
    # Q2 は K3 を手元に在ると宣言しているので動かない
    assert "Q2>K3" not in out["移った組"]
    print("[measure] 空にできるかの宣言を替えた写し: K3 を `できる` → `宣言なし` に"
          "すると、その欄の 3 組だけが (B) → (D) へ移り(6 → 3 件 / 8 → 11 件)、"
          "ほかで動いた組は 0 件、別枠も不変")
    print("[measure] K3 を手元に在ると宣言している Q2 の組は動かない"
          "(空にする欄でないので印も付かない)")


def test_measure_bumping_row_count_moves_only_the_mark() -> None:
    """(7) 行数を 1 → 2 に替えると、その組の印だけが移り、4 値は動かない。"""
    tables = four_tables()
    first = H.quiet_slots(*tables)
    out = H.rows_probe(*tables, first)
    assert out["合うか"] is True
    assert out["替えた組"] == "Q2>K4"
    assert (out["替えた rule or 式の id"], out["替えた次元名"]) == ("R1", "K4")
    assert out["印(前)"] == {H.MARKS[0]: 2, H.MARKS[1]: 2, H.MARKS[2]: 2}
    assert out["印(後)"] == {H.MARKS[0]: 1, H.MARKS[1]: 3, H.MARKS[2]: 2}
    assert out["4 値は不変か"] is True and out["ほかで動いた組"] == []
    assert out["空でも止まらない欄(前)"] == out["空でも止まらない欄(後)"] == 9
    assert out["うち 2 行以上が当たる(後)"] == 3 == 2 + 1
    print("[measure] 行数を替えた写し: R1 / K4 の行数を 1 → 2 にすると Q2>K4 の印だけが"
          "`1 行に決まる` → `2 行以上が当たる` へ移り(2 → 1 件 / 2 → 3 件)、"
          "4 値は 1 つも動かない")
    print("[measure] 空でも止まらない欄は 9 件のまま、うち 2 行以上が当たるが 2 → 3 件。"
          "入力の CSV は 1 文字も書き換わらない(写しはメモリの中だけ)")


def test_measure_output_has_no_recommendation_column() -> None:
    """(8) 出力の末尾の「持たせていないもの」が 12 行で、禁則の語が件数の側に無い。"""
    t = pull()
    c = t.counts()
    assert tuple(k for k in c if k in MOTANAI_KEYS) == MOTANAI_KEYS
    assert len(MOTANAI_KEYS) == 12
    for word in KINSOKU:
        hit = [k for k in c if word in k]
        assert set(hit) <= set(MOTANAI_KEYS), (word, hit)
    # 組の一覧にも「正しい埋め方」「推奨」の欄が無い
    for cell in t.cells:
        for key in cell.as_dict():
            assert not any(w in key for w in KINSOKU), key
    # 動く側のコードに、持たせていない呼び出しが 1 つも無い
    tree = ast.parse((ROOT / "quiet_slots.py").read_text(encoding="utf-8"))
    called: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            f = n.func
            called.add(f.id if isinstance(f, ast.Name) else
                       (f.attr if isinstance(f, ast.Attribute) else ""))
    assert not (called & set(MOTANAI_CALLS)), called & set(MOTANAI_CALLS)
    mods = {n.names[0].name.split(".")[0] if isinstance(n, ast.Import)
            else (n.module or "").split(".")[0]
            for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))}
    assert len(mods) == 8
    assert sum(1 for n in ast.walk(tree) if isinstance(n, ast.Call)
               and isinstance(n.func, ast.Attribute)
               and isinstance(n.func.value, ast.Name)
               and n.func.value.id == "hashlib") == 1
    print(f"[measure] 出力の末尾の「持たせていないもの」は 12 行で、消す引数も option も"
          f"無い。禁則の語({len(KINSOKU)} 語)を含む key は、その 12 行だけ")
    print("[measure] 部品が import している module は 8 個で、eval / exec / float /"
          " round / 現在時刻 / subprocess / random / 平均 / 通信 の呼び出しは 0 件。"
          "hashlib を呼ぶのは判定部分の 1 か所だけ")


# ---------------------------------------------------------------- 止まる側

def test_stop_reasons_are_ten() -> None:
    """止まる理由コードは 10 個(表の側 7 + verify 3)。"""
    assert len(H.STOP_REASONS) == 10
    assert len(H.TABLE_REASONS) == 7 and len(H.VERIFY_REASONS) == 3
    assert len(set(H.STOP_REASONS)) == 10


@pytest.mark.parametrize("name,reason", [
    ("slots_shutten_kuuran", H.STOP_REASONS[0]),
    ("shapes_shutten_kuuran", H.STOP_REASONS[0]),
    ("exits_shutten_kuuran", H.STOP_REASONS[0]),
    ("asks_id_juufuku", H.STOP_REASONS[1]),
    ("asks_ran_juufuku", H.STOP_REASONS[2]),
    ("slots_deguchi_nashi", H.STOP_REASONS[3]),
    ("exits_toranai", H.STOP_REASONS[3]),
    ("slots_deguchi_tooru", H.STOP_REASONS[4]),
    ("shapes_kumi_juufuku", H.STOP_REASONS[5]),
    ("exits_kigou_juufuku", H.STOP_REASONS[6]),
])
def test_broken_table_counts_nothing(name: str, reason: str) -> None:
    """崩した表では 1 組も数えず、理由コードが返る(4 値は全て 0)。"""
    which = name.split("_")[0]
    t = pull(**{{"asks": "a", "slots": "s", "shapes": "p", "exits": "e"}[which]: name})
    assert t.report.ok is False
    assert reason in reasons_of(t)
    assert t.cells == ()
    assert t.four() == {k: 0 for k in H.YOTSU}
    assert t.extras() == {k: 0 for k in H.BETSUWAKU}
    assert t.at_hand() == 0 and t.pair_denominator() == 0
    assert t.quiet_cells() == () and t.wide_cells() == ()
    for call in (t.judgement_bytes, t.sha256):
        with pytest.raises(RuntimeError):
            call()


def test_all_table_reasons_have_a_broken_fixture() -> None:
    """表の側 7 個の理由コードすべてに、崩した表で道がある。"""
    seen: set[str] = set()
    for p in sorted((FIX / "kowashita").glob("*.csv")):
        which = p.name.split("_")[0]
        key = {"asks": "a", "slots": "s", "shapes": "p", "exits": "e"}[which]
        try:
            t = pull(**{key: p.stem})
        except H.ReadError:
            continue
        seen |= reasons_of(t)
    assert seen == set(H.TABLE_REASONS)
    print(f"[measure] 止まる理由コードは 10 個(表の側 7 + verify 3)で、"
          f"表の側 7 個すべてに崩した表で道がある")


def test_unreadable_tables_exit_two() -> None:
    """表として読めない形は終了コード 2(組は 1 つも数えない)。"""
    stop, unread = 0, 0
    for p in sorted((FIX / "kowashita").glob("*.csv")):
        which = p.name.split("_")[0]
        key = {"asks": "a", "slots": "s", "shapes": "p", "exits": "e"}[which]
        try:
            t = pull(**{key: p.stem})
        except H.ReadError:
            unread += 1
            continue
        assert t.report.ok is False
        stop += 1
    assert (stop, unread) == (10, 20)
    assert stop + unread == 30
    print("[measure] 崩した表 30 枚の内訳 = 1 組も数えずに止まる 10 枚 / "
          "表として読めない 20 枚")


# ---------------------------------------------------------------- verify / CLI

def test_verify_is_deterministic() -> None:
    """二度走りと 3 通りの入れ替えで、判定部分の sha256 が 4 回とも同じ。"""
    out = H.verify(*four_tables())
    assert out["ok"] is True
    prints = {out["sha256"], out["2 回目の sha256"],
              *out["入れ替えた 4 枚の sha256"].values()}
    assert len(prints) == 1
    assert out["件数の検算"]["合計"] == 50
    assert out["件数の検算"]["問いごとの内訳の合計"] == 50
    assert out["件数の検算"]["欄の種別ごとの内訳の合計"] == 50
    assert sum(out["件数の検算"]["印"].values()) == 6
    body = H.quiet_slots(*four_tables()).judgement_bytes().decode("utf-8")
    for word in ("読んだ条件", "絶対パス", str(ROOT)):
        assert word not in body
    print(f"[measure] 2 回 + 3 通りの入れ替えで読み直し: 判定部分の sha256 は 4 回とも"
          f"同じ(4/4 一致、先頭 12 桁 {out['sha256'][:12]})")


def test_cli_prints_counts(capsys: pytest.CaptureFixture[str]) -> None:
    """check は件数、cells は一覧つき。終了コードは空でも止まらない欄が在れば 3。"""
    args = [str(path_of(n)) for n in NORMAL]
    assert H.main(["check", *args]) == 3
    got = json.loads(capsys.readouterr().out)
    assert got["ok"] is True
    assert got["分母(問い × 欄 の組の件数)"] == 50
    assert got["空でも止まらない欄"] == 9
    assert H.main(["cells", *args]) == 3
    got = json.loads(capsys.readouterr().out)
    assert len(got["空でも止まらない欄の一覧"]) == 9
    assert len(got["別枠の一覧"]) == 18 == 4 + 4 + 10
    assert len(got["欄ごと"]) == 10
    assert len(got["どの問いも求めていない行の在り方の宣言の一覧"]) == 1
    assert len(got["どの欄も指していない出口の登録の一覧"]) == 2
    assert sum(int(r["件数"]) for r in got["判定ごとの一覧"]) == 50
    assert H.main(["verify", *args]) == 0
    capsys.readouterr()


def test_init_writes_four_templates(tmp_path: Path) -> None:
    """ひな型は 4 枚。そのまま check を通すと、組を作れる。"""
    paths = H.init(tmp_path)
    assert len(paths) == 4 and all(p.exists() for p in paths)
    t = H.quiet_slots(H.Asks.load(paths[0]), H.Slots.load(paths[1]),
                      H.Shapes.load(paths[2]), H.Exits.load(paths[3]))
    assert t.report.ok
    assert t.pair_denominator() == t.ask_denominator() * t.slot_denominator()


def test_input_is_never_rewritten() -> None:
    """verify の写しはメモリの中だけで、入力の CSV は 1 バイトも変わらない。"""
    before = {n: path_of(n).read_bytes() for n in NORMAL}
    H.verify(*four_tables())
    assert {n: path_of(n).read_bytes() for n in NORMAL} == before
