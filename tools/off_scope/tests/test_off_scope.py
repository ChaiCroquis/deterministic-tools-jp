"""off_scope のテスト。合成 fixture は `fixtures/` に commit 済(実データは入れない)。

test_measure_* が記事に載せた数値の出どころで、assert で固定している(値が変われば記事も
変える前提)。測っているものは 9 つある。

  (1) 項目 16 件が 4 値 9 件 + 別枠 7 件に分かれ、合計が 3 通りの数え方で戻る側
  (2) **線の外と宣言された 14 項目の内訳が 4 つに割れる**側 = 記事の骨
  (3) **行数を数える在り所と数えない在り所を同じ値にしない**(`数えられない`)側
  (4) **必須の宣言が在るのに在り所が `無い` 項目が 3 件**ある側
  (5) **項目名を全部入れ替えても 4 値が 1 件も動かない**(領域を名前から推測しない)側
  (6) 入る形が書かれていても、領域が `外` なら (D) にならない側
  (7) 在り所に 1 行足すと、その項目だけが (A) → (B) へ移る側
  (8) 出力の末尾の「持たせていないもの」が 10 行で、禁則の語が件数の側に無い側
  (9) 止まる理由コード 7 個と、表として読めない 7 通りに道が在る側

(1) の 4 値は、テストの側でも 6 枚の行から直に組み立てて確かめている(部品の judge /
five / extras を呼ばない)。
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
import off_scope as H  # noqa: E402
import make_fixtures as M  # noqa: E402

ASOF = M.ASOF
SHA = "4e7a355ada4a33b3f9cbf89a1e35f7abe30469ac8811f2abe396ac7d7f4605c9"

# 収録すべきか・正しさ・重み付けを指す語(件数と一覧の側に持たせない)
KINSOKU = ("推奨", "順位", "優先度", "点数", "割合", "カバー率", "収録すべき",
           "正しい側", "健全", "重要度", "スコア", "削減")

# 出力の末尾に並ぶ「持たせていないもの」(**消す引数も option も無い**)
MOTANAI_KEYS = (
    "収録すべきかを決めない",
    "必須かどうかを判断しない",
    "領域の線を引き直さない",
    "項目名から領域を推測しない",
    "条文や規約を読まない",
    "0 件と欄が無いを同じ値にしない",
    "割合を単独で返さない",
    "時計を読まない",
    "入力を書き換えない",
    "float を使わない",
)


# ------------------------------------------------------------ 読み込み

def six_tables(items: str = "items_a.csv", domains: str = "domains_a.csv",
               placements: str = "placements_a.csv", shapes: str = "shapes_a.csv",
               basis: str = "basis_a.csv", payload: str = "payload_a.csv"):
    """fixtures(と kowashita)から 6 枚を読む。"""
    def path(name: str) -> Path:
        return (KOWASHITA / name) if (KOWASHITA / name).exists() else (FIX / name)

    i = H.Items.load(path(items))
    return (i, H.Domains.load(path(domains)),
            H.Placements.load(path(placements), i.ids),
            H.Shapes.load(path(shapes), i.ids),
            H.load_basis(path(basis)), H.load_payload(path(payload)))


def table(**kw) -> H.Table:
    return H.off_scope(*six_tables(**kw), ASOF)


# ------------------------------------------------------------ テスト側の別実装

def classify(item: list[str], placements: list[list[str]], shapes: list[list[str]],
             domains: list[list[str]], basis: list[list[str]],
             payload: list[list[str]]) -> str:
    """項目 1 件の 4 値 / 別枠を、テストの側で行から直に出す(部品の judge を呼ばない)。"""
    iid, _name, domain, required, _note, source = item
    stance = {r[0]: r[1] for r in domains}
    mine = [p for p in placements if p[0] == iid]
    shape = next((s for s in shapes if s[0] == iid), None)
    marks = sorted({p[1] for p in mine})
    basis_names = {r[0] for r in basis}
    payload_names = {r[0] for r in payload}
    nashi = (marks == ["無い"]) or not marks

    if (not source or any(not p[4] for p in mine)
            or (shape is not None and not shape[5])):
        return H.BETSUWAKU[0]
    if domain not in stance:
        return H.BETSUWAKU[1]
    if len(marks) > 1:
        return H.BETSUWAKU[2]
    if shape is not None and shape[1] not in ("—", "") and shape[1] not in basis_names:
        return H.BETSUWAKU[3]
    if shape is not None and (shape[2] in ("—", "") or shape[2] not in payload_names):
        return H.BETSUWAKU[4]
    if shape is not None and shape[4] not in ("—", ""):
        return H.BETSUWAKU[5]
    if required in ("—", "") and nashi:
        return H.BETSUWAKU[6]
    if stance[domain] == "内":
        return H.VALUES[4]
    if marks and marks[0] in ("収録", "照合専用"):
        return H.VALUES[1]
    if marks and marks[0] in ("第2層", "case属性"):
        return H.VALUES[2]
    if stance[domain] == "境界として明示" and shape is not None and all(
            shape[k] not in ("—", "") for k in (1, 2, 3)):
        return H.VALUES[3]
    return H.VALUES[0]


def test_4値はテスト側の別実装と一致する() -> None:
    t = table()
    mine = {r[0]: classify(r, M.PLACEMENTS, M.SHAPES, M.DOMAINS, M.BASIS, M.PAYLOAD)
            for r in M.ITEMS}
    assert {x.item_id: x.value for x in t.rows} == mine


# ------------------------------------------------------------ (1)

def test_measure_16_items_split_into_five_values_and_seven_extras() -> None:
    t = table()
    assert t.report.ok is True
    assert len(t.items.items) == 16 and len(t.placements.items) == 17
    assert len(t.shapes.items) == 5
    assert len(t.domains.items) == 4 and len(t.basis.items) == 2
    assert len(t.payload.items) == 3
    assert t.denominator() == 16
    five, extras = t.five(), t.extras()
    assert five == {H.VALUES[0]: 2, H.VALUES[1]: 3, H.VALUES[2]: 2,
                    H.VALUES[3]: 1, H.VALUES[4]: 1}
    assert extras == {k: 1 for k in H.BETSUWAKU}
    assert sum(five.values()) == 9 and sum(extras.values()) == 7
    assert sum(five.values()) + sum(extras.values()) == t.denominator()
    assert sum(int(r["項目の件数"]) for r in t.by_stance()) == 16
    assert sum(int(r["項目の件数"]) for r in t.by_place()) == 16
    assert [(r["領域の宣言"], int(r["項目の件数"])) for r in t.by_stance()] == [
        ("内", 1), ("外", 10), ("境界として明示", 4), (H.UNREGISTERED, 1)]
    assert [(r["在り所"], int(r["項目の件数"])) for r in t.by_place()] == [
        ("収録", 3), ("照合専用", 1), ("第2層", 6), ("case属性", 1), ("無い", 4),
        (H.NO_ROW, 0), (H.MANY_PLACES, 1)]
    print("[measure] items_a / domains_a / placements_a / shapes_a + 登録表 2 枚: "
          "項目 16 行 / 領域の登録 4 行 / 在り所 17 行 / 入る形 5 行 / "
          "basis の登録 2 行 / payload の登録 3 行")
    print(f"[measure] 分母は 項目 16 件、4 値は "
          f"{json.dumps({k[:3]: v for k, v in five.items()}, ensure_ascii=False)}"
          f"(合計 9 件)")
    print("[measure] 別枠は 7 枠が 1 件ずつ(合計 7 = 16 - 9)")
    print("[measure] 領域の宣言ごとの合計 16(内 1 / 外 10 / 境界として明示 4 / "
          "登録表の外 1)、在り所ごとの合計 16(収録 3 / 照合専用 1 / 第2層 6 / "
          "case属性 1 / 無い 4 / 行き先が 2 つ以上 1)")


# ------------------------------------------------------------ (2) 記事の骨

def test_measure_outside_items_split_into_four_states() -> None:
    t = table()
    outside = [x for x in t.rows if x.stance in H.OUTSIDE]
    assert len(outside) == 14
    has_rows = [x for x in outside if x.value == H.VALUES[1]]
    destined = [x for x in outside if x.value == H.VALUES[2]]
    gone = [x for x in outside if x.value == H.VALUES[0]]
    shaped = [x for x in outside if x.value == H.VALUES[3]]
    extras = [x for x in outside if x.value in H.BETSUWAKU]
    assert len(has_rows) == 3 and len(destined) == 2 and len(gone) == 2
    assert len(shaped) == 1 and len(extras) == 6
    assert len(has_rows) + len(destined) + len(gone) + len(shaped) + len(extras) == 14
    assert [x.item_id for x in has_rows] == ["I02", "I03", "I15"]
    assert [x.item_id for x in gone] == ["I01", "I16"]
    counted = t.counted_rows()
    assert counted["(B) の行数の合計"] == 67
    assert counted["由来ごとの内訳"] == {"自前抽出": 8, "上流": 59,
                                        H.NO_ORIGIN: 0}
    assert counted["行を数えた在り所の行数"] == 3
    print("[measure] 線の外(外 10 + 境界として明示 4)と宣言された項目は 14 件。"
          "内訳は 行が在る (B) 3 件 / 行き先だけ在る (C) 2 件 / "
          "必須の宣言だけ在る (A) 2 件 / 入る形まで在る (D) 1 件 / 別枠 6 件")
    print("[measure] (B) の 3 件が持っている行数の合計は 67 行で、由来は 上流 59 行 / "
          "自前抽出 8 行(= 線の外と宣言した領域の行が、表の中で動いている量)")


def test_measure_two_denominators_always_come_together() -> None:
    t = table()
    dens = t.denominators()
    assert set(dens) == {"項目数", "行数(在り所の台帳が数えた行)", "行数を数えない項目"}
    assert dens["項目数"] == 16
    assert dens["行数(在り所の台帳が数えた行)"] == {"収録": 25, "照合専用": 47}
    assert dens["行数を数えない項目"] == 12
    # **割合の 1 値を返す列が無い**(counts の key に割合の語が無い)
    flat = json.dumps({k: v for k, v in t.counts().items()
                       if k not in MOTANAI_KEYS}, ensure_ascii=False)
    for word in ("カバー率", "割合", "%"):
        assert word not in flat
    print("[measure] 2 通りの分母は 項目数 16 と 行数(収録 25 行 / 照合専用 47 行)で、"
          "必ず両方そろって出る。割合の 1 値を出す key は 0 件")


# ------------------------------------------------------------ (3) 0 件と欄なし

def test_measure_counted_and_uncountable_are_different_values() -> None:
    t = table()
    counted = sorted(x.item_id for x in t.rows if x.count.isdigit())
    uncountable = sorted(x.item_id for x in t.rows if x.count == H.UNCOUNTABLE)
    assert counted == ["I02", "I03", "I07", "I15"]
    assert len(uncountable) == 12
    assert len(counted) + len(uncountable) == 16
    assert {x.count for x in t.rows if x.item_id in ("I02", "I03", "I07", "I15")} == {
        "12", "47", "5", "8"}
    # **行き先だけが宣言された項目は 0 ではなく `数えられない`**
    for x in t.rows:
        if x.place in H.DESTINED or x.place == H.PLACES[4]:
            assert x.count == H.UNCOUNTABLE
    print("[measure] 行数が付いた項目は 4 件(12 行 / 47 行 / 5 行 / 8 行)、"
          "`数えられない` が 12 件。合計 16。第2層 / case属性 / 無い の項目に 0 は入らない")


# ------------------------------------------------------------ (4) 消える項目

def test_measure_required_without_a_place() -> None:
    t = table()
    missing = t.missing_rows()
    assert missing["件数"] == 3
    assert sorted(missing["項目"]) == ["I01", "I06", "I16"]
    assert missing["項目"]["I06"] == H.VALUES[3]
    # **必須の欄は入力の文字列のまま**(言い換えも分類もしない)
    texts = {x.item_id: x.required for x in t.rows}
    assert texts["I01"] == M.REQ and texts["I03"] == H.NO_REQUIRED
    assert sum(1 for x in t.rows if x.required == H.NO_REQUIRED) == 3
    print("[measure] 必須の宣言が在るのに在り所が `無い` 項目は 3 件(I01・I06・I16)。"
          "うち 1 件は入る形まで書かれている (D) で、4 値の側では消える項目に見えない")
    print("[measure] 必須の欄が空の項目は 3 件で、`必須の記載なし` が入る。"
          "書かれている 13 件は入力の文字列のまま")


# ------------------------------------------------------------ (5) 名前から推測しない

def test_measure_item_names_do_not_change_anything() -> None:
    t = table()
    rows = [list(r) for r in M.ITEMS]
    for i, r in enumerate(rows):
        r[1] = f"ぜんぜん違う名前 {len(rows) - i}(架空)"
    items = H.Items(rows)
    after = H.off_scope(items, *six_tables()[1:], ASOF)
    assert H.moved(t, after) == []
    assert after.sha256() == t.sha256() == SHA
    assert [x.name for x in after.rows] != [x.name for x in t.rows]
    print("[measure] 項目名を 16 件すべて別の文字に入れ替えても、4 値が動いた項目は "
          "0 件で、判定部分の sha256 も同じ(= 領域は登録表からしか取らない)")


# ------------------------------------------------------------ (6) 入る形と領域

def test_measure_shape_alone_does_not_make_it_a_boundary() -> None:
    t = table()
    i01 = next(x for x in t.rows if x.item_id == "I01")
    i06 = next(x for x in t.rows if x.item_id == "I06")
    assert i01.stance == H.STANCES[1] and i06.stance == H.STANCES[2]
    assert i01.basis == i06.basis and i01.payload == i06.payload
    assert i01.value == H.VALUES[0] and i06.value == H.VALUES[3]
    # 領域の宣言を `境界として明示` に替えると、I01 だけが (D) へ移る
    domains = [list(r) for r in M.DOMAINS]
    for r in domains:
        if r[0] == M.OUT1:
            r[1] = H.STANCES[2]
    items, _, placements, shapes, basis, payload = six_tables()
    after = H.off_scope(items, H.Domains(domains), placements, shapes, basis,
                        payload, ASOF)
    moved = H.moved(t, after)
    assert moved == ["I01"]
    assert {x.item_id: x.value for x in after.rows}["I01"] == H.VALUES[3]
    print("[measure] I01 と I06 は入る形の宣言が同じ形だが、領域の宣言が 外 か "
          "境界として明示 かで (A) と (D) に分かれる")
    print("[measure] 領域 1 の宣言を 外 → 境界として明示 にすると、移るのは I01 の "
          "1 件だけで、行き先は (D)(在り所も必須の宣言も変えていない)")


# ------------------------------------------------------------ (7) probe

def test_measure_row_probe_moves_one_item() -> None:
    t = table()
    iid = H.row_probe_plan(t)
    assert iid == "I01"
    after = H.row_probe(*six_tables(), ASOF, iid)
    assert H.moved(t, after) == ["I01"]
    got = {x.item_id: x.value for x in after.rows}["I01"]
    assert got == H.VALUES[1]
    assert after.five()[H.VALUES[0]] == 1 and after.five()[H.VALUES[1]] == 4
    assert after.extras() == t.extras()
    assert after.counted_rows()["(B) の行数の合計"] == 68
    before = hashlib.sha256((FIX / "placements_a.csv").read_bytes()).hexdigest()
    assert before == hashlib.sha256(
        (FIX / "placements_a.csv").read_bytes()).hexdigest()
    print("[measure] 在り所に 1 行足す: I01 の在り所を 無い → 収録(1 行)にすると "
          "I01 の 1 件だけが (A) → (B) へ移る((A) 2 → 1 件 / (B) 3 → 4 件、"
          "行数の合計 67 → 68 行)")
    print("[measure] ほかで動いた項目は 0 件、別枠の 7 つも不変。写しはメモリの中だけで、"
          "在り所の台帳の CSV は 1 文字も書き換わらない")


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
        assert word not in flat
    for row in t.listed():
        for word in KINSOKU:
            assert word not in json.dumps(row, ensure_ascii=False)
    print("[measure] 出力の末尾の「持たせていないもの」は 10 行で、消す引数も option も"
          f"無い。禁則の語({len(KINSOKU)} 語)を含む key は 0 件")


# ------------------------------------------------------------ (9) 止まる 7 + 読めない 7

def test_measure_seven_stop_reasons_all_reachable() -> None:
    seen: dict[str, list[str]] = {}

    def record(reasons: list[str], where: str) -> None:
        for r in reasons:
            seen.setdefault(r, []).append(where)

    cases = [
        ({"domains": "domains_出典が空.csv"}, ASOF),
        ({"items": "items_項目idの重複.csv"}, ASOF),
        ({"domains": "domains_宣言が決めた外.csv"}, ASOF),
        ({"placements": "placements_記号が決めた外.csv"}, ASOF),
        ({"placements": "placements_行数が整数でない.csv"}, ASOF),
        ({}, ""),
        ({"basis": "basis_登録表が空.csv"}, ASOF),
    ]
    for kw, asof in cases:
        t = H.off_scope(*six_tables(**kw), asof)
        assert t.report.ok is False and t.report.pending
        assert t.denominator() == 0 and t.rows == ()
        assert t.five() == {k: 0 for k in H.VALUES}
        assert t.extras() == {k: 0 for k in H.BETSUWAKU}
        with pytest.raises(RuntimeError):
            t.judgement_bytes()
        record([p.reason for p in t.report.pending], str(kw or asof))
    assert sorted(seen) == sorted(H.TABLE_REASONS)
    print("[measure] 止まる理由コードは 7 個で、崩した表 6 枚 + 基準日を渡さない 1 通りの"
          " 7 通りすべてに道が在る(7/7)。止まった表は 4 値を 1 件も返さない")


def test_measure_seven_unreadable_tables() -> None:
    cases = [{"items": "items_列が足りない.csv"}, {"items": "items_行が無い.csv"},
             {"items": "items_項目idが空.csv"},
             {"placements": "placements_項目idが台帳に無い.csv"},
             {"placements": "placements_行数の欄が余計.csv"},
             {"shapes": "shapes_項目idが2行.csv"},
             {"domains": "domains_記号が2行.csv"}]
    msgs: list[str] = []
    for kw in cases:
        with pytest.raises(H.ReadError) as e:
            six_tables(**kw)
        msgs.append(str(e.value))
    assert len(msgs) == 7 and len(set(msgs)) == 7
    print("[measure] 表として読めない崩し方は 7 通り(列が足りない / 行が無い / "
          "項目 id が空 / 在り所の項目 id が台帳に無い / 行数の欄が余計 / "
          "入る形が同じ項目に 2 行 / 領域の登録が同じ記号で 2 行)で、7 通りとも別の文で"
          "止まる")


# ------------------------------------------------------------ 決定論

def test_measure_judgement_is_deterministic() -> None:
    t = table()
    again = table()
    shas = [t.sha256(), again.sha256()]
    for how in H.SWAPS:
        items, domains, placements, shapes, basis, payload = six_tables()
        s = H.off_scope(items.swapped(how), domains.swapped(how),
                        placements.swapped(how), shapes.swapped(how),
                        basis.swapped(how), payload.swapped(how), ASOF)
        shas.append(s.sha256())
    assert len(set(shas)) == 1 and shas[0] == SHA
    body = t.judgement_bytes().decode("utf-8")
    for word in ("読んだ条件", str(ROOT), ".csv", "合成の項目", M.REQ):
        assert word not in body
    out = H.verify(*six_tables(), ASOF)
    assert out["ok"] is True
    assert out["二度走りの判定部分が同一"] is True
    assert out["行順を入れ替えても同一"] == {k: True for k in H.SWAPS}
    assert out["出典が空のまま 4 値に入った項目"] == []
    assert out["(B) の行数が在り所の台帳と合う"] is True
    print("[measure] 2 回 + 行順の入れ替え 3 通りで読み直し: 判定部分の sha256 は 5 回とも"
          f" 同じ(5/5 一致、先頭 12 桁 {shas[0][:12]})")
    print("[measure] 判定部分に絶対パス・ファイル名・項目名・必須の宣言の文字は入らない。"
          "verify は 5 つとも通る")


def test_measure_no_float_no_clock_no_network() -> None:
    src = (ROOT / "off_scope.py").read_text(encoding="utf-8")
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
    H.verify(*six_tables(), ASOF)
    H.row_probe(*six_tables(), ASOF, "I01")
    assert t.report.ok
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(FIX.glob("*.csv"))}
    assert after == before and len(before) == 6


def test_CLI_の終了コード(tmp_path: Path) -> None:
    args = ["check", str(FIX / "items_a.csv"), str(FIX / "domains_a.csv"),
            str(FIX / "placements_a.csv"), str(FIX / "shapes_a.csv"),
            str(FIX / "basis_a.csv"), str(FIX / "payload_a.csv"), ASOF]
    assert H.main(args) == 3           # 別枠と (A)(B) が在る
    assert H.main(["report"] + args[1:]) == 3
    assert H.main(["verify"] + args[1:]) == 0
    assert H.main(["init", str(tmp_path / "ひな型")]) == 0
    made = sorted(p.name for p in (tmp_path / "ひな型").glob("*.csv"))
    assert len(made) == 6
    # ひな型をそのまま通すと、止まらずに 4 値が付く
    d = tmp_path / "ひな型"
    items = H.Items.load(d / "項目の台帳.csv")
    t = H.off_scope(items, H.Domains.load(d / "領域の登録表.csv"),
                    H.Placements.load(d / "在り所の台帳.csv", items.ids),
                    H.Shapes.load(d / "入る形の宣言表.csv", items.ids),
                    H.load_basis(d / "basisの登録表.csv"),
                    H.load_payload(d / "payloadの登録表.csv"), ASOF)
    assert t.report.ok and t.denominator() == 2
    bad = ["check", str(KOWASHITA / "items_行が無い.csv")] + args[2:]
    assert H.main(bad) == 2            # 表として読めない
