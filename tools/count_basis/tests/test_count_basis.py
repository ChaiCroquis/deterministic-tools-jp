"""count_basis のテスト。合成 fixture は `fixtures/` に commit 済(実データ・実在の値は入れない)。

test_measure_* が記事に載せた数値の出どころで、assert で固定している(値が変われば記事も変える前提)。
測っているものは 7 つある。

  (1) 検証 16 件 が 7 値 + 別枠 4 種に分かれ、4 つの分母の内訳が付く側
  (2) **同じ列に並ぶ 16 件の単位が 7 通りで、単位ごとの内訳の合計が 16 に戻る**側
      (= 単位をまたいで足さない形。足した数 9,446 はどこにも出ない)
  (3) **7,050 と宣言された検証の元の行は 141 行で、倍率 50 は 1 行が持つ表の中に在る**という側。
      = 記事の骨
  (4) 重なり 2 件が、共有している数表 id をそのまま出す側
  (5) 別枠 5 件が、原文の表記のまま出る側(「通過」から件数を補完しない)
  (6) 次元を 1 つ外すと、その検証の積が倍率の分だけ減って「分解が合わない」へ移る側
  (7) 同じ数表を指すようにすると重なりが 1 増え、それでも総件数の欄が現れない側

(1) の 11 値は、テストの側でも 4 種 5 枚の行から直に組み立てて確かめている(部品の judge /
eleven を呼ばず、fixture の行から別に分類する)。
"""
from __future__ import annotations

import ast
import json
import hashlib
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FIX))
import count_basis as H  # noqa: E402
import make_fixtures as M  # noqa: E402

# 厚み・良し悪しを指す語(件数と一覧の側に持たせない = 型 I2 の forbidden の物理形)
KINSOKU = ("厚い", "薄い", "十分", "水増し", "強い", "弱い", "健全", "劣化", "違反", "推定")

# 形容の語(数値が無いなら多寡を書かない)
KEIYOU = ("多い", "少ない", "ほとんど", "かなり", "著しく", "ざっと")

# 持たせていない経路の名前(動く側のコードに 1 つも無いことを見る)
MOTANAI = ("eval", "exec", "round(", "float(", "now(", "today(", "time(",
           "subprocess", "random", "platform", "datetime", "urllib", "requests",
           "socket", "difflib", "SequenceMatcher", "statistics", "mean(",
           "median(")

# 単位をまたいで足した数(**この数がどこにも出ないことがこの部品の骨の物理形**)
TASHITA = 9446


def path_of(name: str) -> Path:
    normal = ("checks_a", "bases_a", "dims_a", "methods_a", "units_a")
    return FIX / f"{name}.csv" if name in normal else FIX / "kowashita" / f"{name}.csv"


def five(c: str = "checks_a", b: str = "bases_a", d: str = "dims_a",
         m: str = "methods_a", u: str = "units_a"):
    return (H.Checks.load(path_of(c)), H.Bases.load(path_of(b)),
            H.Dims.load(path_of(d)), H.Methods.load(path_of(m)),
            H.Units.load(path_of(u)))


def pull(**kw) -> H.Tally:
    return H.count_basis(*five(**kw))


def reasons_of(t: H.Tally) -> set[str]:
    return {p.reason for p in t.report.pending}


def judged_of(t: H.Tally, check_id: str) -> H.Judged:
    return next(j for j in t.judged if j.check.check_id == check_id)


# ---------------------------------------------------------------- 別実装(テスト側)

def expect_eleven() -> dict[str, int]:
    """4 種 5 枚の行から 11 値を別に数える(部品の judge / eleven / counts を呼ばない)。"""
    bases = {row[0]: (int(row[2]), row[3]) for row in M.bases_rows()}
    methods = {row[0] for row in M.methods_rows()}
    units = {row[0] for row in M.units_rows()}
    dims: dict[str, list[tuple[str, int, str]]] = {}
    for row in M.dims_rows():
        dims.setdefault(row[0], []).append((row[1], int(row[2]), row[3]))
    eleven = {k: 0 for k in H.KEKKA}
    first: list[tuple[str, str, tuple[str, ...]]] = []
    for row in sorted(M.checks_rows(), key=lambda r: r[0]):
        cid, raw, unit, tables, method, source = row
        ids = tuple(t for t in tables.split(";") if t)
        count = raw.replace(",", "")
        n = int(count) if count.isdigit() else None
        if not source:
            hit = H.KEKKA[7]
        elif method not in methods:
            hit = H.KEKKA[8]
        elif unit and unit not in units:
            hit = H.KEKKA[8]
        elif not unit:
            hit = H.KEKKA[9] if n is not None else H.KEKKA[2]
        elif n is None:
            hit = H.KEKKA[10]
        elif any(t not in bases for t in ids):
            hit = H.KEKKA[6]
        elif cid not in dims:
            hit = H.KEKKA[3]
        else:
            product = sum(bases[t][0] for t in ids)
            for _, factor, _ in dims[cid]:
                product *= factor
            if any(place == H.PLACES[1] for _, _, place in dims[cid]):
                hit = H.KEKKA[4]
            else:
                hit = H.KEKKA[0] if product == n else H.KEKKA[1]
        first.append((cid, hit, ids))
    # 重なりの印(自分より前の検証と数表 id が交わる側に付く)
    earlier: list[tuple[str, ...]] = []
    for _, hit, ids in first:
        if hit in H.KASANARI_MOTO:
            if any(set(e) & set(ids) for e in earlier):
                hit = H.KEKKA[5]
            earlier.append(ids)
        elif hit == H.KEKKA[5]:
            earlier.append(ids)
        eleven[hit] += 1
    return eleven


# ---------------------------------------------------------------- 測定(記事の数値)

def test_measure_16_checks_split_into_eleven() -> None:
    """(1) 検証 16 件 が 7 値 + 別枠 4 種に分かれ、分母の内訳が付く。"""
    t = pull()
    assert t.report.ok and t.report.pending == ()
    c = t.counts()
    assert c["検証の台帳の行数"] == 16
    assert c["元の行の台帳の行数"] == 9
    assert c["掛けた次元の宣言表の行数"] == 16
    assert c["確かめ方の登録表の行数"] == 5
    assert c["単位記号の登録表の行数"] == 6
    assert c["分母(検証の数)"] == 16 == t.check_denominator()
    assert c["分母(7 値が付いた検証の数)"] == 11
    assert c["分母(別枠の数)"] == 5
    assert c["分母(台帳に出てくる単位記号の数)"] == 7
    assert c["7 値 + 別枠"] == {
        "分解できた(宣言件数 = 元の行数 × 倍率の積)": 3,
        "分解が合わない": 1,
        "件数が書かれていない": 1,
        "次元の宣言が無い": 2,
        "倍率が 1 行の持つ表の中に在る": 1,
        "他の検証と元の行を共有している": 2,
        "元の行の台帳に無い数表を指している": 1,
        "別枠(出典が空)": 1,
        "別枠(登録表に無いコード)": 2,
        "別枠(単位記号が無い)": 1,
        "別枠(件数が整数でない)": 1}
    assert c["7 値 + 別枠"] == expect_eleven()
    assert sum(c["7 値 + 別枠"].values()) == 16
    assert c["理由別の止まった件数"] == {}
    assert c["台帳に無い検証 id を指す次元の宣言"] == 1
    assert c["どの検証も指していない数表"] == 0
    assert not any(isinstance(v, float) for v in c.values())
    assert not any(str(k).endswith(("率", "割合", "点", "スコア", "順位")) for k in c)
    print("[measure] checks_a / bases_a / dims_a / methods_a / units_a:"
          " 検証 16 行 / 元の行 9 行 / 次元 16 行 / 確かめ方 5 行 / 単位 6 行"
          f" → 7 値 + 別枠 {c['7 値 + 別枠']}")
    print("[measure] 分母は 検証の数 16 / 7 値が付いた検証 11 / 別枠 5、"
          "それに 台帳に出てくる単位記号 7")


def test_measure_seven_units_never_summed() -> None:
    """(2) 同じ列に並ぶ 16 件の単位が 7 通りで、単位ごとの内訳の合計が 16 に戻る。"""
    t = pull()
    rows = t.by_unit()
    assert len(rows) == 7
    assert [(r["単位記号"], r["検証の数"]) for r in rows] == [
        ("(空欄)", 2), ("cell", 2), ("item", 2), ("row", 6), ("shibu", 2),
        ("year", 1), ("合成の未登録の単位記号", 1)]
    assert sum(int(r["検証の数"]) for r in rows) == 16 == t.check_denominator()
    for k in H.KEKKA:
        assert sum(int(r["7 値 + 別枠"][k]) for r in rows) == t.eleven()[k]
    # 由来ごとの内訳は「元の行の台帳の行数」に戻る(件数ではなく数表の枚数を数える)
    assert [(r["由来記号"], r["数表の枚数"]) for r in t.by_origin()] == [
        ("上流", 2), ("照合専用", 1), ("自前抽出", 6)]
    assert sum(int(r["数表の枚数"]) for r in t.by_origin()) == 9
    # **単位をまたいで足した数は、出力のどこにも現れない**
    declared = [j.check.declared for j in t.judged if j.check.declared is not None]
    assert sum(declared) == TASHITA
    dumped = json.dumps({"counts": t.counts(), "listed": t.listed()},
                        ensure_ascii=False, default=str)
    assert str(TASHITA) not in dumped
    print("[measure] 同じ列に並ぶ 16 件の単位は 7 通り"
          " (空欄 2 / セル 2 / 項目 2 / 行 6 / 支部 2 / 年度 1 / 未登録 1) で、"
          "単位ごとの内訳の合計は 16 = 検証の数。由来ごとは 上流 2 + 照合専用 1 +"
          " 自前抽出 6 = 元の行の台帳 9 行")
    print(f"[measure] 宣言件数を単位の区別なく足すと {TASHITA} になるが、"
          "この数は出力にも一覧にも 1 度も現れない(足す関数を置いていない)")


def test_measure_declared_7050_is_141_rows() -> None:
    """(3) 7,050 と宣言された検証の元の行は 141 行(= 記事の骨)。"""
    t = pull()
    j = judged_of(t, "K01")
    assert j.check.declared_count == "7,050" and j.check.declared == 7050
    assert j.base_rows == 141
    assert j.factors == (("等級", 50, H.PLACES[1]),)
    assert j.product == 7050 and j.gap == "0"
    assert j.result == "倍率が 1 行の持つ表の中に在る"
    # 積は宣言件数と合うのに、7,050 行は台帳のどこにも無い
    assert 141 * 50 == 7050
    assert all(b.rows != 7050 for b in t.bases.items)
    assert max(b.rows for b in t.bases.items) == 1681
    inside = t.inside_only()
    assert len(inside) == 1 and inside[0]["元の行数"] == 141
    print("[measure] 7,050 と宣言された検証 K01 の元の行は 141 行 で、"
          "倍率 50 の在り所は 1 行が持つ表の中。141 × 50 = 7,050 と積は合うのに、"
          "7,050 行を持つ数表は元の行の台帳に 1 枚も無い(最大は 1,681 行)")


def test_measure_two_shares_keep_table_ids() -> None:
    """(4) 重なり 2 件が、共有している数表 id をそのまま出す。"""
    t = pull()
    shares = t.shares()
    assert len(shares) == 2 == t.eleven()["他の検証と元の行を共有している"]
    assert [(s["検証 id"], s["共有している数表 id"], s["共有している相手の検証 id"])
            for s in shares] == [("K06", ["T1"], ["K01"]), ("K16", ["T3"], ["K03"])]
    # 重なりの印が付くのは後ろの検証だけ(前の検証の区分は動かさない)
    assert judged_of(t, "K01").result == "倍率が 1 行の持つ表の中に在る"
    assert judged_of(t, "K03").result == "次元の宣言が無い"
    # 共有していると書くだけで、どちらを捨てるかは書かない
    dumped = json.dumps(shares, ensure_ascii=False)
    for word in ("捨て", "除外", "重複排除", "優先"):
        assert word not in dumped
    print("[measure] 重なりは 2 件(K06 が K01 と T1、K16 が K03 と T3)。"
          "印が付くのは後ろの検証だけで、前の検証の区分は動かない。"
          "出るのは共有している数表 id の集合と相手の検証 id だけ")


def test_measure_five_asides_keep_raw_text() -> None:
    """(5) 別枠 5 件が、原文の表記のまま出る(「通過」から件数を補完しない)。"""
    t = pull()
    asides = t.asides()
    assert len(asides) == 5 == t.aside_denominator()
    assert [(a["検証 id"], a["判定"]) for a in asides] == [
        ("K08", "別枠(出典が空)"),
        ("K09", "別枠(登録表に無いコード)"),
        ("K10", "別枠(登録表に無いコード)"),
        ("K11", "別枠(単位記号が無い)"),
        ("K12", "別枠(件数が整数でない)")]
    assert judged_of(t, "K12").check.declared_count == "1.251"
    assert judged_of(t, "K12").check.declared is None
    # 「通過」は 7 値の側に残り、件数は補完されない
    k02 = judged_of(t, "K02")
    assert k02.result == "件数が書かれていない"
    assert k02.check.declared_count == "通過" and k02.check.declared is None
    assert k02.base_rows == 0 and k02.factors == () and k02.gap == ""
    # 別枠の検証には元の行も倍率も付かない(見に行く経路が無い)
    for a in asides:
        j = judged_of(t, a["検証 id"])
        assert j.base_rows == 0 and j.factors == () and j.product == 0
    assert H.read_count("通過") is None and H.read_count("1,681") == 1681
    print("[measure] 別枠は 5 件(出典が空 1 / 登録表に無いコード 2 /"
          " 単位記号が無い 1 / 件数が整数でない 1)。原文の 通過 と 1.251 は"
          "読めない件数のまま残り、件数を当てた値はどこにも入らない")


def test_measure_dropping_one_dimension_moves_one_check() -> None:
    """(6) 次元を 1 つ外すと、その検証の積が倍率の分だけ減って「分解が合わない」へ移る。"""
    c, b, d, m, u = five()
    first = H.count_basis(c, b, d, m, u)
    probe = H.drop_probe(c, b, d, m, u, first)
    assert probe["合うか"] is True
    assert probe["外した検証 id"] == "K04" and probe["外した次元"] == "年"
    assert probe["外した倍率"] == 3
    assert probe["積(前)"] == 24 and probe["積(後)"] == 8
    assert probe["積(後)× 外した倍率"] == 24
    assert probe["移った先"] == "分解が合わない"
    assert probe["宣言件数 - 積(後)"] == "16"
    assert probe["ほかで動いた検証"] == []
    assert probe["単位ごとの検証の数は不変か"] is True
    assert probe["由来ごとの内訳は不変か"] is True
    after = probe["7 値 + 別枠(後)"]
    assert after["分解できた(宣言件数 = 元の行数 × 倍率の積)"] == 2
    assert after["分解が合わない"] == 2
    assert sum(after.values()) == 16
    # 入力の CSV は 1 文字も書き換わらない(写しはメモリの中だけ)
    assert H.Dims.load(path_of("dims_a")).items == d.items
    print("[measure] 次元を 1 つ外した写し: K04 の 年 ×3 を外すと積が 24 → 8 で、"
          "8 × 3 = 24。区分は 分解できた → 分解が合わない に移り、"
          "ほかで動いた検証は 0 件、単位ごと・由来ごとの内訳も不変")


def test_measure_sharing_one_more_table_adds_one_share() -> None:
    """(7) 同じ数表を指すようにすると重なりが 1 増え、総件数の欄は現れない。"""
    c, b, d, m, u = five()
    first = H.count_basis(c, b, d, m, u)
    probe = H.share_probe(c, b, d, m, u, first)
    assert probe["合うか"] is True
    assert probe["書き換えた検証 id"] == "K15"
    assert probe["指すようにした数表 id"] == ["T1"]
    assert probe["移った先"] == "他の検証と元の行を共有している"
    assert probe["共有している数表 id"] == ["T1"]
    assert probe["重なり(前)"] == 2 and probe["重なり(後)"] == 3
    assert probe["ほかで動いた検証"] == []
    assert probe["総件数や順位の欄"] == []
    assert probe["7 値 + 別枠の合計(後)"] == 16
    assert H.Checks.load(path_of("checks_a")).items == c.items
    print("[measure] 同じ数表を指すようにした写し: K15 が T1 を指すと"
          " 重なり 2 → 3 で、ほかで動いた検証は 0 件。"
          "それでも出力に総件数も順位の欄も現れない(合計は 16 のまま)")


# ---------------------------------------------------------------- verify

def test_verify_five_things() -> None:
    """verify が 5 つ見て、判定部分の sha256 が 4 回とも同じ。"""
    c, b, d, m, u = five()
    out = H.verify(c, b, d, m, u)
    assert out["ok"] is True
    assert out["読んだ回数"] == 2
    assert out["sha256"] == out["2 回目の sha256"]
    assert set(out["入れ替えた 5 枚の sha256"].values()) == {out["sha256"]}
    assert out["入れ替え方"] == list(H.SWAPS)
    tally = out["件数の検算"]
    assert tally["合計"] == 16 and tally["7 値"] == 11
    assert tally["単位ごとの内訳の合計"] == 16
    assert tally["由来ごとの内訳の合計"] == 9 == tally["元の行の台帳の行数"]
    assert "pending" not in out
    print(f"[measure] 2 回 + 3 通りの入れ替えで読み直し: 判定部分の sha256 は"
          f" 4 回とも同じ(4/4 一致、先頭 12 桁 {out['sha256'][:12]})")
    print("[measure] 件数の検算: 7 値 + 別枠の合計 16 = 検証の数 16、"
          "7 値 11 = 7 値が付いた検証 11、単位ごとの内訳の合計 16 = 検証の数、"
          "由来ごとの内訳の合計 9 = 元の行の台帳の行数 9")


def test_judgement_bytes_have_no_path_or_clock() -> None:
    """判定部分に絶対パス・ホスト名が入らない(= 同じ表なら同じバイト列)。"""
    t = pull()
    body = t.judgement_bytes().decode("utf-8")
    for word in ("読んだ条件", "絶対パス", str(ROOT), str(FIX)):
        assert word not in body
    assert t.sha256() == hashlib.sha256(t.judgement_bytes()).hexdigest()
    assert len(t.judgement_bytes().decode("utf-8").splitlines()) == 17


# ---------------------------------------------------------------- 止まる側

def test_measure_eleven_stop_reasons_and_broken_tables() -> None:
    """止まる理由コードは 11 個で、表の側 8 個すべてに崩した表で道がある。"""
    assert len(H.STOP_REASONS) == 11
    assert len(H.TABLE_REASONS) == 8 and len(H.VERIFY_REASONS) == 3
    broken = sorted((FIX / "kowashita").glob("*.csv"))
    seen: set[str] = set()
    stopped = read_error = 0
    for p in broken:
        kind = p.stem.split("_")[0]
        kw = {"checks": {}, "bases": {}, "dims": {}, "methods": {}, "units": {}}[kind]
        kw[kind[0] if kind != "checks" else "c"] = p.stem
        key = {"checks": "c", "bases": "b", "dims": "d", "methods": "m",
               "units": "u"}[kind]
        try:
            t = pull(**{key: p.stem})
        except H.ReadError:
            read_error += 1
            continue
        assert t.report.ok is False, p.stem
        assert t.judged == ()
        assert t.eleven() == {k: 0 for k in H.KEKKA}
        assert t.shares() == [] and t.asides() == [] and t.mismatched() == []
        for call in (t.judgement_bytes, t.sha256):
            with pytest.raises(RuntimeError):
                call()
        seen |= reasons_of(t)
        stopped += 1
    assert seen == set(H.TABLE_REASONS)
    assert stopped == 13 and read_error == 20 and len(broken) == 33
    print("[measure] 止まる理由コードは 11 個(表の側 8 + verify 3)で、表の側 8 個"
          "すべてに崩した表で道がある。止まった表では 11 値は全て 0、一覧も全て 0 件")
    print("[measure] 崩した表 33 枚の内訳 = 1 件も数えずに止まる 13 枚 /"
          " 表として読めない 20 枚")


def test_requires_column_is_checked() -> None:
    """確かめ方が要求する欄が埋まっていないと、1 件も数えずに止まる(3 通り)。"""
    for name in ("checks_youkyuu_mitamase", "checks_youkyuu_yurai",
                 "checks_youkyuu_kensuu"):
        t = pull(c=name)
        assert reasons_of(t) == {"確かめ方が要求する欄が埋まっていない"}, name


# ---------------------------------------------------------------- 持たせていない側

def test_no_forbidden_paths_in_source() -> None:
    """動く側のコードに、現在時刻 / float / 乱数 / 通信 / 平均 の呼び出しが 1 つも無い。"""
    src = (ROOT / "count_basis.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    # 文字列と注釈を外したコードだけを見る(説明文に語が出るのは許す)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            node.value = ""
    bare = ast.unparse(tree)
    for word in MOTANAI:
        assert word not in bare, word
    imports = {n.names[0].name.split(".")[0] for n in ast.walk(tree)
               if isinstance(n, ast.Import)}
    imports |= {n.module.split(".")[0] for n in ast.walk(tree)
                if isinstance(n, ast.ImportFrom) and n.module}
    assert imports == {"argparse", "csv", "hashlib", "json", "sys", "dataclasses",
                       "pathlib", "__future__"}
    print(f"[measure] 部品が import している module は {len(imports)} 個で、"
          "現在時刻を読む呼び出し・float / eval / exec / round / subprocess /"
          " random / 平均 / 通信 の呼び出しは 0 件")


def test_counts_have_no_rate_or_rank() -> None:
    """件数と一覧の側に、割合・点数・順位・厚みの語が無い。"""
    t = pull()
    structured = json.dumps({"件数": t.eleven(), "単位ごと": t.by_unit(),
                             "由来ごと": t.by_origin(), "一覧": t.listed(),
                             "重なり": t.shares(), "中に在る": t.inside_only(),
                             "合わない": t.mismatched(), "別枠": t.asides(),
                             "逆向き": t.dangling_dims(),
                             "使われていない数表": t.unused_bases()},
                            ensure_ascii=False, default=str)
    body = t.judgement_bytes().decode("utf-8")
    for word in KINSOKU + KEIYOU + ("%", "カバー率", "スコア"):
        assert word not in structured, word
        assert word not in body, word
    # 出力の key に総件数の欄が無い
    for key in t.counts():
        if "総件数" in key:
            assert key == "検証の総件数を出さない"


def test_inputs_are_not_rewritten() -> None:
    """読む前後で入力ファイルの sha256 が同じ(verify の写しも含む)。"""
    paths = sorted((FIX).rglob("*.csv"))
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    H.verify(*five())
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    assert before == after and len(paths) == 38


def test_registries_are_closed() -> None:
    """登録表の意味・在り所・由来は、登録の集合の外に出ない。"""
    assert len(H.METHOD_MEANINGS) == 5 and len(H.UNIT_MEANINGS) == 6
    assert len(H.REQUIRES) == 3 and len(H.PLACES) == 3 and len(H.ORIGINS) == 3
    assert len(H.KEKKA) == 11 and len(H.NANA) == 7 and len(H.BEKKA) == 4
    t = pull()
    assert {j.result for j in t.judged} <= set(H.KEKKA)
    assert {d.place for d in t.dims.items} <= set(H.PLACES)
    assert {b.origin for b in t.bases.items} <= set(H.ORIGINS)
    # 単位記号の意味は登録表からだけ引く(綴りから当てない)
    assert t.units.meaning_of("cell") == "セル"
    assert t.units.meaning_of("合成の未登録の単位記号") == ""
    assert t.methods.meaning_of("合成の未登録の確かめ方") == ""


def test_cli_exit_codes() -> None:
    """check は欠けが在れば 3、表として読めなければ 2、init はひな型を書いて 0。"""
    args = [str(path_of(n)) for n in ("checks_a", "bases_a", "dims_a", "methods_a",
                                      "units_a")]
    assert H.main(["check"] + args) == 3           # 別枠 5 件・重なり 2 件が在る
    assert H.main(["verify"] + args) == 0
    broken = [str(path_of("checks_0gyou"))] + args[1:]
    assert H.main(["check"] + broken) == 2
    stop = [str(path_of("checks_suuhyou_kuuran"))] + args[1:]
    assert H.main(["check"] + stop) == 3


def test_init_template_is_readable(tmp_path: Path) -> None:
    """ひな型 5 枚はそのまま読めて、出典の欄が全部埋まっている。"""
    written = H.init(tmp_path)
    assert len(written) == 5
    t = H.count_basis(H.Checks.load(written[0]), H.Bases.load(written[1]),
                      H.Dims.load(written[2]), H.Methods.load(written[3]),
                      H.Units.load(written[4]))
    assert t.report.ok, [p.as_dict() for p in t.report.pending]
    assert sum(t.eleven().values()) == 3 == t.check_denominator()
