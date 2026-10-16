"""blank_kind のテスト。合成 fixture は `fixtures/` に commit 済(実データ・実在の値は入れない)。

test_measure_* が記事に載せた数値の出どころで、assert で固定している(値が変われば記事も変える前提)。
測っているものは 5 つある。

  (1) 対象 × 項目 の 12 マスが 4 値に分かれ、理由コード別の件数と分母の内訳が付く側(atai_a)
  (2) 値の列の空欄に「全部に当たる」を書くと、その 1 マスだけが「決まらない」に変わる側
      (atai_zenbu + koumoku_yurui)= この記事の骨
  (3) 0 と空欄をどちらにも寄せない側(atai_zero)
  (4) 「値が在る」と「空欄」と「止まった」が混ざらない側
  (5) 理由コード別の件数の合計 + 理由コードの無い行 = 対象 × 項目 の総数 が合う側

(1) の 4 値は、テストの側でも宣言から直に組み立てて確かめている(部品の read は使うが、
期待値は fixture の行と宣言から別に計算する)。
"""
from __future__ import annotations

import ast
import hashlib
import re
import sys
from decimal import Decimal
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIX = ROOT / "fixtures"
PLAN = ROOT.parent.parent          # 07_記事化商品化計画(出典の行を開くため)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FIX))
import blank_kind as B  # noqa: E402
import make_fixtures as M  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの -> その行に在るはずの語
REAL_SOURCES = {
    M.SRC_JUNI: "順位の列に書く",
    M.SRC_KITEI: "既定そのものを持たない",
    M.SRC_ANBUN: "按分も日割りも無い",
    M.SRC_KAZOERU: "別の欄で数えて出す",
}

# 形容の語(出力にも実装にも持たせない = 数値が無いなら多寡を書かない)
KEIYOU = ("多い", "少ない", "ほとんど", "かなり", "著しく")


def path_of(name: str) -> Path:
    return FIX / "kowashita" / f"{name[2:]}.csv" if name.startswith("K:") \
        else FIX / f"{name}.csv"


def pull(a: str = "atai_a", k: str = "koumoku_a", r: str = "riyuu_a") -> B.Table:
    return B.read(B.Sheet.load(path_of(a)), B.Columns.load(path_of(k)),
                  B.Reasons.load(path_of(r)))


def cell_of(t: B.Table, target: str, item: str) -> B.Read:
    return next(x for x in t.reads if x.cell.target == target and x.cell.item == item)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def every_fixture() -> list[Path]:
    return sorted(p for p in FIX.rglob("*.csv"))


def expect_four(rows: list[list[str]], koumoku: list[list[str]],
                riyuu: list[list[str]]) -> dict[str, int]:
    """4 値を、fixture の行と宣言から直に組み立てる(部品の分類には頼らない)。"""
    how = {r[0]: r[2] for r in riyuu[1:]}
    allowed = {r[0]: tuple(c for c in r[2].split(B.REASON_SEP) if c) for r in koumoku[1:]}
    zero_ok = {r[0]: r[3] == B.HAI for r in koumoku[1:]}
    all_match = {r[0]: r[4] == B.HAI for r in koumoku[1:]}
    out = dict.fromkeys(B.RESULTS, 0)
    for target, item, value, reason, _source, _swap in rows[1:]:
        if item not in allowed:
            out[B.RESULTS[3]] += 1
        elif not reason:
            if not value:
                out[B.RESULTS[3]] += 1
            elif Decimal(value) == 0 and not zero_ok[item]:
                out[B.RESULTS[2]] += 1
            else:
                out[B.RESULTS[0]] += 1
        elif reason not in how or reason not in allowed[item]:
            out[B.RESULTS[3]] += 1
        elif (how[reason] == B.HOWS[1]) == all_match[item]:
            out[B.RESULTS[1]] += 1
        else:
            out[B.RESULTS[2]] += 1
    return out


# ---------------------------------------------------------------- 入り口

def test_committed_tables_load() -> None:
    """commit 済の表は、表として読める(止まる理由が 0 件)。"""
    assert len(B.Sheet.load(FIX / "atai_a.csv").items) == 12
    assert B.Sheet.load(FIX / "atai_a.csv").swap == "逆順"
    assert len(B.Columns.load(FIX / "koumoku_a.csv").items) == 4
    assert len(B.Reasons.load(FIX / "riyuu_a.csv").items) == 9
    for name in ("atai_a", "atai_zenbu", "atai_zero"):
        assert B.Sheet.load(FIX / f"{name}.csv").pending == (), name
    for name in ("koumoku_a", "koumoku_yurui"):
        assert B.Columns.load(FIX / f"{name}.csv").pending == (), name
    assert B.Reasons.load(FIX / "riyuu_a.csv").pending == ()


def test_sources_point_at_real_lines() -> None:
    """出典のうち 4 件は、この repo 内の実在の行を指している。"""
    for src, word in REAL_SOURCES.items():
        rel, lineno = src.rsplit(" L", 1)
        line = (PLAN / rel).read_text(encoding="utf-8").splitlines()[int(lineno) - 1]
        assert word in line, f"{src} に {word} が無い: {line[:60]}"


def test_registered_vocabularies() -> None:
    """登録の語彙は固定(値の種類 6 / 返し方 3 / 4 値 4 / 理由コード 11)。"""
    assert len(B.KINDS) == 6
    assert B.HOWS == ("値として返さない", "全部に当たるとして扱う", "該当なしとして返す")
    assert B.YESNO == ("はい", "いいえ")
    assert len(B.RESULTS) == 4
    assert len(B.STOP_REASONS) == 11
    assert B.SUBCOMMANDS == ("read", "check", "verify", "init")


# ---------------------------------------------------------------- (1) 読む側

def test_measure_twelve_cells_split_into_four() -> None:
    """対象 3 × 項目 4 = 12 マスが、値が在る 4 と空欄 8 に分かれる。"""
    t = pull()
    c = t.counts()
    assert t.report.ok
    assert c["対象の数"] == 3 and c["項目の数"] == 4 and c["対象 × 項目"] == 12
    assert c["値の表の行数"] == 12 and c["項目の宣言の行数"] == 4
    assert c["理由コードの宣言の行数"] == 9
    assert c["4 値"] == {"値が在る": 4, "空欄(宣言された意味つき)": 8,
                         "決まらない": 0, "止まった": 0}
    assert c["4 値"] == expect_four(M.ATAI_A, M.KOUMOKU_A, M.RIYUU_A)
    print(f"[measure] atai_a / koumoku_a / riyuu_a: 対象 3 × 項目 4 = 12 マス → "
          f"4 値 {c['4 値']}")


def test_measure_counts_by_reason_code_with_a_denominator() -> None:
    """理由コード別は 7 種で合計 8 件。率は単独では返らない。"""
    t = pull()
    c = t.counts()
    per = c["理由コード別"]
    assert per == {"値が未取得": 1, "仮置き": 1, "未収録": 1, "施行日待ち": 1,
                   "該当なし": 1, "手で追加": 1, "全部に当たる": 2}
    assert len(per) == 7 and sum(per.values()) == 8
    assert c["理由コードの付いた行に値も在った件数(仮置き)"] == 1
    assert "理由コード別の件数の合計 8 + 理由コードの無い行 4 = 12" in \
        str(c["欠けている件数の検算"])
    assert len(t.blanks()) == 8
    print("[measure] 理由コード別 7 種 / 合計 8 件 + 理由コードの無い行 4 件 = 12 マス"
          "(宣言は 9 件。率は単独では返らない)")


def test_measure_provisional_value_is_not_returned_as_a_value() -> None:
    """仮置きの行は、値を持っていても値の欄では返らない(仮置きの欄に出る)。"""
    t = pull()
    h = cell_of(t, M.T_C, M.I_KINGAKU)
    assert h.cell.value == Decimal("95000")       # 入力には値が在る
    assert h.result == "空欄(宣言された意味つき)"
    assert h.provisional == "95000" and h.how == "値として返さない"
    row = next(r for r in t.table() if r["対象"] == M.T_C and r["項目"] == M.I_KINGAKU)
    assert row["値"] == "" and row["仮置きの値"] == "95000"
    print("[measure] 仮置きの 1 行は 値 の欄が空で 仮置きの値 の欄に 95000 が出る"
          "(値として返さない、仮置きを外す提案もしない)")


# ---------------------------------------------------------------- (2) 列で意味が変わる

def test_measure_one_reason_cell_makes_the_blank_undecidable() -> None:
    """値の列の空欄に「全部に当たる」を書くと、その 1 マスだけが決まらなくなる。"""
    base = pull()
    moved = pull(a="atai_zenbu", k="koumoku_yurui")
    assert moved.report.ok                   # 列の種類との食い違いは止めない(この回の主題)
    assert moved.counts()["4 値"] == {"値が在る": 4, "空欄(宣言された意味つき)": 7,
                                      "決まらない": 1, "止まった": 0}
    assert moved.counts()["4 値"] == expect_four(M.ATAI_ZENBU, M.KOUMOKU_YURUI, M.RIYUU_A)
    assert cell_of(base, M.T_B, M.I_KINGAKU).result == "空欄(宣言された意味つき)"
    assert cell_of(base, M.T_B, M.I_KINGAKU).meaning == "行は在るが値をまだ取っていない"
    assert cell_of(moved, M.T_B, M.I_KINGAKU).result == "決まらない"
    assert cell_of(moved, M.T_B, M.I_KINGAKU).meaning == ""   # 片方を選んで返さない
    # 変わったのはこの 1 マスだけで、ほかの 11 マスの結果は同じ
    other = {(x.cell.target, x.cell.item): x.result for x in base.reads
             if (x.cell.target, x.cell.item) != (M.T_B, M.I_KINGAKU)}
    assert {(x.cell.target, x.cell.item): x.result for x in moved.reads
            if (x.cell.target, x.cell.item) != (M.T_B, M.I_KINGAKU)} == other
    print("[measure] 値の列の空欄に 全部に当たる を 1 マス: 空欄(値が未取得)→ 決まらない。"
          "ほかの 11 マスは不変")


def test_measure_the_same_blank_sign_reads_differently_per_column() -> None:
    """同じ「全部に当たる」が、全部に当たる列では空欄として読まれる。"""
    moved = pull(a="atai_zenbu", k="koumoku_yurui")
    nenrei = cell_of(moved, M.T_A, M.I_NENREI)
    kingaku = cell_of(moved, M.T_B, M.I_KINGAKU)
    assert nenrei.cell.reason == kingaku.cell.reason == "全部に当たる"
    assert nenrei.result == "空欄(宣言された意味つき)"
    assert nenrei.meaning == "絞り込みを指定していない"
    assert kingaku.result == "決まらない"
    print("[measure] 同じ 全部に当たる が、全部に当たる列では 空欄(絞り込みを指定して"
          "いない)、値の列では 決まらない")


def test_measure_three_tables_three_fingerprints() -> None:
    """宣言を緩めただけでは指紋は動かず、マスの理由コードを書き換えると動く。"""
    got = {
        "atai_a + koumoku_a": pull().sha256()[:12],
        "atai_a + koumoku_yurui": pull(k="koumoku_yurui").sha256()[:12],
        "atai_zenbu + koumoku_yurui": pull(a="atai_zenbu", k="koumoku_yurui").sha256()[:12],
        "atai_zero + koumoku_a": pull(a="atai_zero").sha256()[:12],
    }
    assert got == {"atai_a + koumoku_a": "a8a3b1f6d1d9",
                   "atai_a + koumoku_yurui": "a8a3b1f6d1d9",
                   "atai_zenbu + koumoku_yurui": "d66287621438",
                   "atai_zero + koumoku_a": "552877524778"}
    print("[measure] 判定部分の sha256 先頭 12 桁 atai_a a8a3b1f6d1d9 / "
          "許す一覧を広げただけ a8a3b1f6d1d9(不変)/ 1 マス書き換え d66287621438 / "
          "0 を書いた表 552877524778")


def test_a_value_column_cannot_borrow_the_wildcard_code() -> None:
    """許す一覧に無いコードは、使われた時点で止まる(緩める前は決まらないにすら進まない)。"""
    stopped = pull(a="atai_zenbu")
    assert not stopped.report.ok
    assert {p.reason for p in stopped.report.pending} == {"宣言に無いコード"}
    assert stopped.counts()["4 値"]["止まった"] == 1


def test_measure_two_meanings_in_one_column_stop() -> None:
    """全部に当たる列が値扱いのコードも許していると、宣言の時点で止まる。"""
    t = pull(k="K:koumoku_futatsu")
    assert {p.reason for p in t.report.pending} == {"同じ列に 2 つの意味"}
    assert t.counts()["読んだか"].startswith("読んでいない")
    print("[measure] 全部に当たる列に 値として返さない のコードを足した宣言 → "
          "同じ列に 2 つの意味 で止まる(1 マスも読まない)")


# ---------------------------------------------------------------- (3) 0 と空欄

def test_measure_zero_and_blank_are_not_pulled_together() -> None:
    """0 が正規の値の項目では 0 は値のまま、正規でない項目の 0 は決まらない。"""
    base, zero = pull(), pull(a="atai_zero")
    assert cell_of(base, M.T_A, M.I_NINZUU).cell.value == Decimal("0")
    assert cell_of(base, M.T_A, M.I_NINZUU).result == "値が在る"      # 0 を落とさない
    assert cell_of(zero, M.T_A, M.I_TSUKISUU).result == "決まらない"
    assert cell_of(zero, M.T_A, M.I_NINZUU).result == "値が在る"      # 隣の列は不変
    assert zero.counts()["4 値"] == {"値が在る": 3, "空欄(宣言された意味つき)": 8,
                                     "決まらない": 1, "止まった": 0}
    # 空欄を 0 にする経路が無いので、空欄の件数は 0 を書いても減らない
    assert zero.counts()["4 値"]["空欄(宣言された意味つき)"] == \
        base.counts()["4 値"]["空欄(宣言された意味つき)"]
    print("[measure] 0 が正規の値の列の 0 は 値が在る のまま、正規でない列の 0 は "
          "決まらない。空欄を 0 にする経路が無いので空欄 8 件は変わらない")


def test_no_filling_arguments() -> None:
    """空欄を埋める引数も、前の値を引き継ぐ引数も、日付で版を選ぶ引数も無い。"""
    src = (ROOT / "blank_kind.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "add_argument":
            for a in node.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    names.add(a.value)
    assert names == {"sheet", "columns", "reasons", "dest"}
    for word in ("fillna", "ffill", "default_value", "as_of", "基準日", "按分"):
        assert word not in src, word


def test_no_adjectives_in_the_output() -> None:
    """形容の語を実装にも出力にも持たない(数値が無いなら多寡を書かない)。"""
    src = (ROOT / "blank_kind.py").read_text(encoding="utf-8")
    body = str(pull().counts()) + str(pull().table()) + str(
        B.verify(B.Sheet.load(FIX / "atai_a.csv"), B.Columns.load(FIX / "koumoku_a.csv"),
                 B.Reasons.load(FIX / "riyuu_a.csv")))
    for word in KEIYOU:
        assert word not in src, word
        assert word not in body, word


# ---------------------------------------------------------------- (4) 混ぜない

def test_measure_blank_is_not_a_stop() -> None:
    """空欄であることは止まることではない(理由コードは 1 件も出ない)。"""
    t = pull()
    assert t.report.ok and t.report.pending == ()
    assert t.counts()["4 値"]["空欄(宣言された意味つき)"] == 8
    assert t.counts()["4 値"]["止まった"] == 0
    kara = pull(a="K:atai_riyuu_kuuran")
    assert {p.reason for p in kara.report.pending} == {"理由コードが空"}
    print("[measure] 空欄 8 件は件数に残り、理由コードは 0 件。理由コードの無い空欄だけが "
          "理由コードが空 で止まる")


def test_all_eleven_stop_reasons_are_covered(monkeypatch: pytest.MonkeyPatch) -> None:
    """止まる理由コード 11 個すべてに道がある(崩した表 13 枚 + 差し替えた実装 2 本)。"""
    seen: set[str] = set()
    for a in ("K:atai_riyuu_kuuran", "K:atai_mitouroku_code", "K:atai_yurusanai_code",
              "K:atai_shutten_nashi", "K:atai_koumoku_mitouroku", "K:atai_tarinai",
              "K:atai_juufuku"):
        seen |= {p.reason for p in pull(a=a).report.pending}
    for k in ("K:koumoku_zero_kuuran", "K:koumoku_retsu_kuuran",
              "K:koumoku_shurui_kuuran", "K:koumoku_shutten_nashi",
              "K:koumoku_futatsu"):
        seen |= {p.reason for p in pull(k=k).report.pending}
    seen |= {p.reason for p in pull(r="K:riyuu_shutten_nashi").report.pending}
    assert len(seen) == 9
    # 2 回目の判定部分が不一致 / 行順を入れ替えた表で出力が変わる(毎回違うバイト列を返す)
    sheet = B.Sheet.load(FIX / "atai_a.csv")
    columns = B.Columns.load(FIX / "koumoku_a.csv")
    reasons = B.Reasons.load(FIX / "riyuu_a.csv")
    assert B.verify(sheet, columns, reasons)["ok"] is True
    real_bytes, box = B.Table.judgement_bytes, {"n": 0}

    def drifting(self: B.Table) -> bytes:
        box["n"] += 1
        return real_bytes(self) + str(box["n"]).encode("utf-8")

    monkeypatch.setattr(B.Table, "judgement_bytes", drifting)
    bad = B.verify(sheet, columns, reasons)
    seen |= {p["reason"] for p in bad["pending"]}           # type: ignore[index,union-attr]
    assert seen == set(B.STOP_REASONS), sorted(set(B.STOP_REASONS) - seen)
    print(f"[measure] 止まる理由コード {len(B.STOP_REASONS)} 個すべてに道がある"
          "(崩した表 13 枚 + 差し替えた実装 2 本)")


def test_measure_read_error_count() -> None:
    """「表として読めない」で返す崩した表は 20 枚(理由コードには混ぜない)。"""
    n = 0
    for p in sorted((FIX / "kowashita").glob("*.csv")):
        loader = (B.Sheet.load if p.name.startswith("atai") else
                  B.Columns.load if p.name.startswith("koumoku") else B.Reasons.load)
        try:
            loader(p)
        except B.ReadError:
            n += 1
    assert n == 20
    print(f"[measure] 「表として読めない」で返す崩した表 {n} 枚。理由コードには混ぜない")


# ---------------------------------------------------------------- (5) 件数の検算

def test_measure_the_grid_is_checked_before_any_cell() -> None:
    """対象 × 項目 のマスが 1 行ずつ在るかを、値を 1 つも読む前に突き合わせる。"""
    t = pull()
    assert t.grid.as_dict() == {"対象の数": 3, "項目の数": 4, "対象 × 項目": 12,
                                "宣言された項目の行数": 12, "足りないマス": [],
                                "2 行あるマス": []}
    assert t.grid.ok
    tarinai = pull(a="K:atai_tarinai")
    juufuku = pull(a="K:atai_juufuku")
    assert {p.reason for p in tarinai.report.pending} == {"件数の合計が合わない"}
    assert {p.reason for p in juufuku.report.pending} == {"件数の合計が合わない"}
    assert tarinai.grid.missing == ((M.T_C, M.I_NINZUU),)
    assert juufuku.grid.duplicated == ((M.T_A, M.I_KINGAKU),)
    print("[measure] 1 マス落とした表 → 件数の合計が合わない(足りないマス 1)/ "
          "1 マスを 2 行書いた表 → 件数の合計が合わない(2 行あるマス 1)")


def test_measure_verify_is_deterministic() -> None:
    """2 回読んだ指紋と、値の表の行順を入れ替えた指紋が、3 回とも同じになる。"""
    for a, k, want in (("atai_a", "koumoku_a", "a8a3b1f6d1d9"),
                       ("atai_zenbu", "koumoku_yurui", "d66287621438")):
        out = B.verify(B.Sheet.load(FIX / f"{a}.csv"), B.Columns.load(FIX / f"{k}.csv"),
                       B.Reasons.load(FIX / "riyuu_a.csv"))
        assert out["ok"] is True
        assert out["sha256"] == out["2 回目の sha256"] == out["入れ替えた表の sha256"]
        assert str(out["sha256"])[:12] == want
        print(f"[measure] {a} を 2 回 + 値の表の行順を逆順に入れ替えて読み直し: "
              f"判定部分の sha256 は 3 回とも同じ {want}(3/3 一致)")


def test_row_order_of_the_sheet_does_not_matter() -> None:
    """値の表の行順を入れ替えても、判定部分のバイト列が変わらない。"""
    base = pull()
    sheet = B.Sheet.load(FIX / "atai_a.csv")
    for how in B.SWAPS:
        again = B.read(sheet.swapped(how), B.Columns.load(FIX / "koumoku_a.csv"),
                       B.Reasons.load(FIX / "riyuu_a.csv"))
        assert again.judgement_bytes() == base.judgement_bytes(), how


def test_judgement_has_no_time_host_or_path() -> None:
    """判定部分に時刻・ホスト名・絶対パスが入らない。"""
    t = pull()
    body = t.judgement_bytes().decode("utf-8")
    for word in (t.read_at, t.host, "fixtures", ":\\", "読んだ時刻"):
        assert word not in body, word
    assert set(t.read_condition()) == set(B.READ_KEYS)


def test_measure_inputs_are_not_modified() -> None:
    """読む前後で入力 CSV の sha256 が変わらない(値も理由コードも生成しない)。"""
    before = {p: digest(p) for p in every_fixture()}
    assert len(before) == 39
    for a, k in (("atai_a", "koumoku_a"), ("atai_zenbu", "koumoku_yurui"),
                 ("atai_zero", "koumoku_a")):
        pull(a=a, k=k)
    B.verify(B.Sheet.load(FIX / "atai_a.csv"), B.Columns.load(FIX / "koumoku_a.csv"),
             B.Reasons.load(FIX / "riyuu_a.csv"))
    assert {p: digest(p) for p in every_fixture()} == before
    print(f"[measure] 読む前後で入力 {len(before)} ファイルの sha256 が同じ")


def test_measure_fixtures_are_deterministic(tmp_path: Path) -> None:
    """合成 fixture は生成器から決定論的に出る(ディスク上の CSV と 1 バイト違わない)。"""
    made = M.write_all(tmp_path)
    assert len(made) == 39
    for p in made:
        here = FIX / p.relative_to(tmp_path)
        assert here.read_bytes() == p.read_bytes(), here.name


def test_measure_no_float_no_subprocess() -> None:
    """float も subprocess も random も使っていない(値は Decimal で運ぶ)。"""
    src = (ROOT / "blank_kind.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    mods: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split(".")[0])
    assert mods & {"subprocess", "os", "random", "requests"} == set()
    assert "float(" not in src
    assert not re.search(r"(?<![\w.])\d+\.\d+(?![\w.])", src)   # 小数の literal も無い
    print(f"[measure] 部品が import している module は {len(mods)} 個で、"
          f"subprocess / os / random は 0 件")


# ---------------------------------------------------------------- CLI

def test_cli_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """全部のマスに値が在れば 0、空欄や決まらない行があれば 3、読めなければ 2。"""
    def run(*names: str) -> int:
        return B.main([names[0], *[str(path_of(n)) for n in names[1:]]])

    assert run("check", "atai_a", "koumoku_a", "riyuu_a") == 3      # 空欄 8 件
    assert run("read", "atai_zenbu", "koumoku_yurui", "riyuu_a") == 3
    assert run("verify", "atai_a", "koumoku_a", "riyuu_a") == 0
    assert run("check", "K:atai_tarinai", "koumoku_a", "riyuu_a") == 3
    assert run("check", "K:atai_yomenai", "koumoku_a", "riyuu_a") == 2
    assert run("check", "atai_a", "K:koumoku_juufuku", "riyuu_a") == 2
    assert B.main(["init", str(tmp_path / "ひな型")]) == 0
    capsys.readouterr()
    for name in ("値の表.csv", "項目の宣言.csv", "理由コードの宣言.csv"):
        assert (tmp_path / "ひな型" / name).exists()
    made = B.read(B.Sheet.load(tmp_path / "ひな型" / "値の表.csv"),
                  B.Columns.load(tmp_path / "ひな型" / "項目の宣言.csv"),
                  B.Reasons.load(tmp_path / "ひな型" / "理由コードの宣言.csv"))
    assert made.report.ok and made.verdict == "空欄(宣言された意味つき)"


def test_stopped_table_has_no_result() -> None:
    """止まっているときは結果も指紋も取れない(例外になる)。"""
    t = pull(a="K:atai_riyuu_kuuran")
    for call in (lambda: t.verdict, t.judgement_bytes, t.sha256):
        with pytest.raises(RuntimeError):
            call()
    assert t.counts()["読んだか"].startswith("読んでいない")
    assert t.counts()["4 値"]["止まった"] == 0        # 1 マスも読んでいない
