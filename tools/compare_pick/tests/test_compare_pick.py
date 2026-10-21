"""compare_pick のテスト。合成 fixture は `fixtures/` に commit 済(実データ・実在の値は入れない)。

test_measure_* が記事に載せた数値の出どころで、assert で固定している(値が変われば記事も変える前提)。
測っているものは 6 つある。

  (1) 11 組 × 基準日 2 件 = 22 組が 4 値に分かれ、理由別の件数と分母の内訳が付く側
  (2) 裁定の種類を 1 欄「宣言された順位」に変えると、止まった 11 → 3 に減り、順位で決まった
      2 → 12 に増え、同じ組の勝者が入れ替わる側(= この記事の骨。順位の欄が埋まっているので、
      順位で決める実装は 1 件も止まらない)
  (3) 値も向きも同じまま、丸めを比較の前にするか後にするかの宣言 1 欄で勝者が入れ替わる側
  (4) 単位が違う 2 行は換算せずに止まる側(verify の書き換えで、増えた分と減った分が合う)
  (5) 比べる 2 行の有効期間が基準日で重ならない組は、基準日ごとに別の結果になる側
  (6) 4 値の件数の合計 = 組数 × 基準日の数 が合う側

(1) の 4 値と、順位で決まる組の勝者は、テストの側でも 3 枚の表の行から直に組み立てて確かめて
いる(部品の判定を呼ばず、fixture の行から別に計算する)。
"""
from __future__ import annotations

import ast
import hashlib
import io
import re
import sys
import tokenize
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIX = ROOT / "fixtures"
PLAN = ROOT.parent.parent          # 07_記事化商品化計画(出典の行を開くため)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FIX))
import compare_pick as C  # noqa: E402
import make_fixtures as M  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの -> その行に在るはずの語
REAL_SOURCES = {
    M.SRC_SHUBI: "守備範囲の外",
    M.SRC_OOKII: "値の大きい方でもなく",
    M.SRC_YAJIRUSHI: "矢印も無い",
    M.SRC_KUURAN: "空欄は許さない",
}

# 形容の語(出力にも実装にも持たせない = 数値が無いなら多寡を書かない)
KEIYOU = ("多い", "少ない", "ほとんど", "かなり", "著しく", "急いで")

# 持たせていない経路の名前(実装に 1 つも無いことを見る)
MOTANAI = ("換算", "eval", "exec", "有利", "おすすめ", "推奨", "補完", "既定値",
           "とりあえず", "だいたい")


def path_of(name: str) -> Path:
    return FIX / "kowashita" / f"{name[2:]}.csv" if name.startswith("K:") \
        else FIX / f"{name}.csv"


def pull(s: str = "sengen_a", k: str = "kouho_a", j: str = "kijunbi_a") -> C.Table:
    return C.compare_pick(C.Declared.load(path_of(s)), C.Candidates.load(path_of(k)),
                          C.Asofs.load(path_of(j)))


def pair_of(table: C.Table, group_id: str, asof_id: str) -> C.Pair:
    return next(p for p in table.pairs
                if p.group_id == group_id and p.asof_id == asof_id)


def code_only(src: str) -> str:
    """コメントと文字列(docstring 込み)を外した、実行される側だけの写し。"""
    out = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        out.append(tok.string)
    return " ".join(out)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def every_fixture() -> list[Path]:
    return sorted(p for p in FIX.rglob("*.csv"))


def marume(value: Decimal, name: str) -> Decimal:
    """丸めの、テスト側の別実装(部品の round_value は呼ばない)。"""
    if name == "丸めない":
        return value
    if name == "50 の倍数に丸める":
        return (value / Decimal(50)).to_integral_value(rounding=ROUND_HALF_UP) \
            * Decimal(50)
    return value.to_integral_value(rounding=ROUND_FLOOR)


def expect_rank_winners(sengen: list[list[str]],
                        kouho: list[list[str]]) -> dict[str, str]:
    """裁定の種類が「宣言された順位」の組の勝者を、行から直に組み立てる(post_027 の読み方)。"""
    kinds = {r[0]: r[1] for r in sengen[1:]}
    groups: dict[str, list[list[str]]] = {}
    for row in kouho[1:]:
        groups.setdefault(row[0], []).append(row)
    out: dict[str, str] = {}
    for group_id, rows in sorted(groups.items()):
        if kinds[rows[0][1]] != "宣言された順位":
            continue
        if any(not r[3] for r in rows):
            out[group_id] = ""
            continue
        top = max(int(r[3]) for r in rows)
        best = [r for r in rows if int(r[3]) == top]
        out[group_id] = best[0][2] if len(best) == 1 else ""
    return out


NUMBER_TEXT = re.compile(r"-?(0|[1-9][0-9]{0,14})(\.[0-9]{1,6})?")


def kettei(rule: dict[str, str], rows: list[dict[str, str]], day: str) -> str:
    """1 組 1 基準日の 4 値を、行から直に決める(部品の判定は呼ばない)。"""
    if rule["kind"] == "決まらない":
        return C.RESULTS[2]
    if rule["kind"] == "宣言された順位":
        if any(not r["priority"] for r in rows):
            return C.RESULTS[2]
        top = max(int(r["priority"]) for r in rows)
        hit = sum(1 for r in rows if int(r["priority"]) == top)
        return C.RESULTS[0] if hit == 1 else C.RESULTS[2]
    if (not rule["unit"] or not rule["round_when"] or not rule["tie"]
            or rule["rounding"] not in C.ROUNDINGS):
        return C.RESULTS[3]
    values: dict[str, Decimal] = {}
    for r in rows:
        if (r["field"] != rule["field"] or not r["value"] or not r["unit"]
                or r["unit"] != rule["unit"]
                or not NUMBER_TEXT.fullmatch(r["value"])):
            return C.RESULTS[3]
        values[r["row_id"]] = Decimal(r["value"])
    if len(rows) < 2:
        return C.RESULTS[3]
    if any(not r["valid_from"] <= day < r["valid_to"] for r in rows):
        return C.RESULTS[3]
    keys = {k: (marume(v, rule["rounding"]) if rule["round_when"] == "前" else v)
            for k, v in values.items()}
    edge = (max(keys.values()) if rule["direction"] == "大きい方"
            else min(keys.values()))
    best = [k for k, v in keys.items() if v == edge]
    if len(best) == 1:
        return C.RESULTS[1]
    if rule["tie"] == "決まらない":
        return C.RESULTS[2]
    juni = {r["row_id"]: r["priority"] for r in rows if r["row_id"] in best}
    if any(not v for v in juni.values()):
        return C.RESULTS[2]
    top = max(int(v) for v in juni.values())
    hit = sum(1 for v in juni.values() if int(v) == top)
    return C.RESULTS[0] if hit == 1 else C.RESULTS[2]


def expect_four(sengen: list[list[str]], kouho: list[list[str]],
                kijunbi: list[list[str]]) -> dict[str, int]:
    """4 値を、3 枚の表の行から直に組み立てる(部品の判定には頼らない)。"""
    rules = {r[0]: dict(zip(M.HEAD_SENGEN, r)) for r in sengen[1:]}
    groups: dict[str, list[dict[str, str]]] = {}
    for row in kouho[1:]:
        groups.setdefault(row[0], []).append(dict(zip(M.HEAD_KOUHO, row)))
    out = dict.fromkeys(C.RESULTS, 0)
    for group_id, rows in sorted(groups.items()):
        rows = sorted(rows, key=lambda r: r["row_id"])
        rule = rules[rows[0]["rule_id"]]
        for asof in sorted(kijunbi[1:], key=lambda r: r[0]):
            out[kettei(rule, rows, asof[1])] += 1
    return out


# ---------------------------------------------------------------- 入り口

def test_committed_tables_load() -> None:
    """commit 済の表は、表として読める(止まる理由が 0 件)。"""
    assert len(C.Declared.load(FIX / "sengen_a.csv").items) == 5
    assert len(C.Candidates.load(FIX / "kouho_a.csv").items) == 21
    assert len(C.Candidates.load(FIX / "kouho_a.csv").group_ids) == 11
    assert len(C.Asofs.load(FIX / "kijunbi_a.csv").items) == 2
    assert C.Asofs.load(FIX / "kijunbi_a.csv").swap == "逆順"
    for name in ("sengen_a", "sengen_junide", "sengen_maeushiro"):
        assert C.Declared.load(FIX / f"{name}.csv").pending == (), name
    assert C.Candidates.load(FIX / "kouho_a.csv").pending == ()
    assert C.Asofs.load(FIX / "kijunbi_a.csv").pending == ()


def test_sources_point_at_real_lines() -> None:
    """fixture の出典のうち 4 件は、この repo の実在の行を指している。"""
    for src, word in REAL_SOURCES.items():
        rel, line = src.rsplit(" L", 1)
        text = (PLAN / rel).read_text(encoding="utf-8-sig").splitlines()
        assert word in text[int(line) - 1], src


def test_fixtures_carry_no_real_amounts() -> None:
    """fixture に単位としての円・% が 1 つも入っていない(単位の名前も架空)。"""
    for p in every_fixture():
        body = p.read_text(encoding="utf-8-sig")
        assert "円" not in body and "%" not in body and "‰" not in body, p.name


def test_declaration_has_the_five_columns() -> None:
    """比較の宣言に要る 5 つの欄が、宣言表の列として在る(= この回の骨の物理形)。"""
    for name in ("field", "unit", "round_when", "tie", "direction"):
        assert name in C.SENGEN_COLUMNS, name
    assert len(C.SENGEN_COLUMNS) == 9
    assert C.KINDS == ("宣言された順位", "値の比較", "決まらない")
    assert len(C.STOP_REASONS) == 18


# ---------------------------------------------------------------- 測ったもの

def test_measure_twenty_two_pairs_split_into_four() -> None:
    """(1) 11 組 × 基準日 2 件 = 22 組が 4 値に分かれ、理由別と分母の内訳が付く。"""
    t = pull()
    c = t.counts()
    assert c["裁定の宣言表の行数(rule 数)"] == 5
    assert c["候補の表の行数"] == 21
    assert c["組数"] == 11
    assert c["基準日の数"] == 2
    assert c["分母(組数 × 基準日の数)"] == 22
    assert c["4 値"] == {"順位で決まった": 2, "比較で決まった": 3,
                         "比較では決まらない": 6, "止まった": 11}
    assert c["止まった理由別"] == {"比べる欄が候補の表に無い": 2, "単位の不一致": 2,
                                   "値が数に読めない": 2, "float 混入": 2,
                                   "基準日で有効期間が重ならない": 1,
                                   "候補が 1 本しかない組に比較の宣言が付いている": 2}
    assert c["決まらない理由別"] == {"宣言が決まらないと言っている": 2,
                                     "同順位で決まらない": 2, "同値で決まらない": 2}
    assert t.verdict == "止まった"
    # 4 値を、3 枚の表の行から別に組み立てても同じになる(部品の判定を呼ばない)
    assert c["4 値"] == expect_four(M.sengen_rows(), M.kouho_rows(), M.kijunbi_rows())
    assert not any("率" in k for k in c)
    assert "22 組" in str(c["分母に含めたもの"])
    assert "4 値の合計 22 / 分母 22" in str(c["件数の合計の検算"])
    print(f"[measure] sengen_a / kouho_a / kijunbi_a: 11 組 × 基準日 2 件 = 22 組"
          f" → 4 値 {c['4 値']}")
    print(f"[measure] 止まった 11 件の内訳 = {c['止まった理由別']}")
    print(f"[measure] 比較では決まらない 6 件の内訳 = {c['決まらない理由別']}"
          "(分母は 組数 × 基準日の数 = 22。率は単独では返らない)")


def test_measure_priority_column_is_not_read_for_comparison() -> None:
    """(2) 裁定の種類を 1 欄「宣言された順位」に変えると、止まらずに別の勝者が出る。"""
    before, after = pull(), pull(s="sengen_junide")
    # 比較で決まる側: 高い方(1049)の行が勝つ。順位は 0 の行
    p = pair_of(before, "P03", "K01")
    assert (p.result, p.row_id, p.value) == ("比較で決まった", "G06", "1050")
    assert p.route == "値の比較(丸めは比較の後)"
    # 順位で決める側: 同じ表のまま、順位 10 の行(値は 1026)が勝つ
    q = pair_of(after, "P03", "K01")
    assert (q.result, q.row_id, q.route) == ("順位で決まった", "G05", "宣言された順位")
    assert before.counts()["4 値"]["止まった"] == 11
    assert after.counts()["4 値"]["止まった"] == 3
    assert after.counts()["4 値"]["順位で決まった"] == 12
    assert after.counts()["止まった理由別"] == {"比べる欄が候補の表に無い": 2,
                                                "基準日で有効期間が重ならない": 1}
    # 単位が違う組も、値が読めない組も、候補が 1 本の組も、順位の欄が埋まっているので決まる
    assert pair_of(after, "P05", "K01").row_id == "G10"      # 単位が違う 2 行
    assert pair_of(after, "P10", "K01").row_id == "G19"      # 値が「未取得」の 2 行
    assert pair_of(after, "P08", "K01").row_id == "G15"      # 候補が 1 本
    assert pair_of(before, "P05", "K01").reason == "単位の不一致"
    assert pair_of(before, "P10", "K01").reason == "値が数に読めない"
    assert after.counts()["4 値"] == expect_four(M.sengen_rows(kind_r02=C.KINDS[0]),
                                                 M.kouho_rows(), M.kijunbi_rows())
    print("[measure] 裁定の種類を 1 欄「値の比較」→「宣言された順位」に変える: 止まった"
          " 11 → 3、順位で決まった 2 → 12。P03 の勝者は G06(値 1049)→ G05(順位 10、"
          "値 1026)に入れ替わる")
    print("[measure] 順位で決める側は、単位が違う組(P05)も値が「未取得」の組(P10)も"
          "候補が 1 本の組(P08)も止めずに勝者を返す(順位の欄は埋まっている)")


def test_measure_round_when_swaps_the_winner() -> None:
    """(3) 値も向きも同じまま、丸めの前後の宣言 1 欄で勝者が入れ替わる。"""
    before, after = pull(), pull(s="sengen_maeushiro")
    assert pair_of(before, "P03", "K01").row_id == "G06"
    assert pair_of(after, "P03", "K01").row_id == "G05"
    assert pair_of(after, "P03", "K01").result == "順位で決まった"
    assert pair_of(after, "P03", "K01").route == \
        "値の比較(丸めは比較の前) → 同値 → 宣言された順位で裁定"
    # 逆向きの組(丸めを前にすると同値になり、宣言が「決まらない」なので落ちていた)
    assert pair_of(before, "P04", "K01").result == "比較では決まらない"
    assert pair_of(before, "P04", "K01").why == "同値で決まらない"
    assert pair_of(after, "P04", "K01").result == "比較で決まった"
    assert pair_of(after, "P04", "K01").row_id == "G08"
    assert after.counts()["4 値"] == {"順位で決まった": 4, "比較で決まった": 3,
                                      "比較では決まらない": 4, "止まった": 11}
    out = C.verify(C.Declared.load(FIX / "sengen_a.csv"),
                   C.Candidates.load(FIX / "kouho_a.csv"),
                   C.Asofs.load(FIX / "kijunbi_a.csv"))
    probe = out["丸めの前後を入れ替えた写し"]
    assert probe["勝者が入れ替わった"] == 2
    assert probe["勝者が入れ替わった組"] == ["P03/K01", "P03/K02"]
    assert probe["結果が変わった"] == 4
    assert probe["分母(組数 × 基準日の数)"] == 22
    print("[measure] 丸めを比較の前にするか後にするかの宣言 1 欄を入れ替える: 勝者が"
          "入れ替わった 2 組 / 22(P03 の 2 基準日。G06 → G05)、結果が変わった 4 組 / 22")
    print("[measure] P04 は 比較では決まらない(同値で決まらない)→ 比較で決まった"
          "(G08、丸めた値 1200)に動いた。値は 1 文字も変えていない")


def test_measure_unit_mismatch_stops_without_conversion() -> None:
    """(4) 単位が違う 2 行は換算せずに止まる。書き換えた分だけ件数が動く。"""
    t = pull()
    p = pair_of(t, "P05", "K01")
    assert p.result == "止まった" and p.reason == "単位の不一致"
    assert "換算しない" in p.detail
    assert p.row_id == "" and p.value == ""
    out = C.verify(C.Declared.load(FIX / "sengen_a.csv"),
                   C.Candidates.load(FIX / "kouho_a.csv"),
                   C.Asofs.load(FIX / "kijunbi_a.csv"))
    probe = out["単位を片方書き換えた写し"]
    assert probe["書き換えた組"] == ["P03"]
    assert probe["止まった(単位の不一致)の増え"] == 2
    assert probe["比較で決まったの減り"] == 2
    assert probe["合うか"] is True
    print("[measure] 単位が違う 2 行の組(P05)は 止まった(単位の不一致)。verify が"
          " P03 の単位を 1 欄書き換えると、止まった(単位の不一致)+2 / 比較で決まった −2"
          "(増えた分と減った分が一致)")


def test_measure_asof_decides_whether_rows_overlap() -> None:
    """(5) 比べる 2 行の有効期間が基準日で重ならない組は、基準日ごとに別の結果になる。"""
    t = pull()
    early, late = pair_of(t, "P06", "K01"), pair_of(t, "P06", "K02")
    assert (early.result, early.row_id, early.value) == ("比較で決まった", "G11", "998")
    assert late.result == "止まった"
    assert late.reason == "基準日で有効期間が重ならない"
    assert "2026-10-01" in late.detail
    print("[measure] 同じ 2 行の組(P06、小さい方を採る宣言)は、基準日 2026-04-01 では"
          " 比較で決まった(G11、丸めた値 998)、基準日 2026-10-01 では 止まった"
          "(基準日で有効期間が重ならない)")


def test_measure_unreadable_values_and_single_candidate() -> None:
    """値が数に読めない組・float から来た形の組・候補が 1 本の組は、比べずに止まる。"""
    t = pull()
    assert pair_of(t, "P10", "K01").reason == "値が数に読めない"
    assert pair_of(t, "P11", "K01").reason == "float 混入"
    assert pair_of(t, "P08", "K01").reason == \
        "候補が 1 本しかない組に比較の宣言が付いている"
    assert pair_of(t, "P09", "K01").reason == "比べる欄が候補の表に無い"
    # 読めた値は全て Decimal(float は 1 つも通らない)
    value, bad = C.read_number("1026")
    assert isinstance(value, Decimal) and bad == ""
    assert C.read_number("1.05e3") == (None, "float 混入")
    assert C.read_number("未取得") == (None, "値が数に読めない")
    assert C.read_number("0001") == (None, "値が数に読めない")
    print("[measure] 比べられない 4 形(値が「未取得」/ 指数表記 / 候補 1 本 / 比べる欄が"
          "無い)は、どれも勝者を返さずに理由コードで止まる")


def test_measure_rank_groups_match_a_second_implementation() -> None:
    """(6) 順位で決まる組の勝者は、テスト側の別実装(post_027 の読み方)と一致する。"""
    for name in ("sengen_a", "sengen_junide"):
        t = pull(s=name)
        kind = C.KINDS[0] if name == "sengen_junide" else C.KINDS[1]
        expect = expect_rank_winners(M.sengen_rows(kind_r02=kind), M.kouho_rows())
        got = {p.group_id: p.row_id for p in t.pairs
               if C.Declared.load(FIX / f"{name}.csv").of(p.rule_id).by_priority}
        assert got == expect, name
        # 勝った行は、順位の最大値を持つ 1 行(ほかの行には行 id が付かない)
        for group_id, row_id in expect.items():
            if row_id:
                rows = C.Candidates.load(FIX / "kouho_a.csv").of(group_id)
                top = max(int(r.priority) for r in rows)
                assert [r.row_id for r in rows if int(r.priority) == top] == [row_id]
    print("[measure] 裁定の種類が「宣言された順位」の組の勝者は、テスト側の別実装"
          "(順位の最大値を持つ 1 行)と 2 枚の宣言表で一致(1 件も食い違わない)")


def test_priority_column_does_not_move_the_comparison() -> None:
    """値の比較で決まる組は、順位の欄を入れ替えても勝者が変わらない。"""
    rows = [list(r) for r in M.kouho_rows()]
    juni = M.HEAD_KOUHO.index("priority")
    for r in rows[1:]:
        if r[0] == "P03":
            r[juni] = "20" if r[juni] == "0" else "0"       # 順位だけを入れ替える
    text = "\n".join(",".join(r) for r in rows)
    t = C.compare_pick(C.Declared.load(FIX / "sengen_a.csv"),
                       C.Candidates.parse(text), C.Asofs.load(FIX / "kijunbi_a.csv"))
    assert pair_of(t, "P03", "K01").row_id == "G06"          # 比較の勝者は動かない
    assert t.counts()["4 値"] == pull().counts()["4 値"]


def test_measure_stop_reason_codes_all_reachable(monkeypatch) -> None:
    """止まる理由コード 18 個すべてに道がある(合成 3 枚 + 崩した表 + 差し替えた実装 3 本)。"""
    got: set[str] = {p.reason for p in pull().pairs if p.reason}
    assert len(got) == 6                      # 合成 3 枚だけで 6 個に道がある
    table_level = [("K:sengen_shutten_nashi", "kouho_a", "kijunbi_a"),
                   ("sengen_a", "K:kouho_shutten_nashi", "kijunbi_a"),
                   ("sengen_a", "kouho_a", "K:kijunbi_shutten_nashi"),
                   ("sengen_a", "K:kouho_id_juufuku", "kijunbi_a"),
                   ("K:sengen_kind_gai", "kouho_a", "kijunbi_a"),
                   ("K:sengen_juufuku", "kouho_a", "kijunbi_a")]
    for s, k, j in table_level:
        t = pull(s, k, j)
        assert t.report.ok is False, (s, k, j)
        assert t.pairs == ()                  # 1 組も読まない
        got |= {p.reason for p in t.report.pending}
    pair_level = [("K:sengen_tanni_kuuran", "kouho_a"),
                  ("K:sengen_maeushiro_kuuran", "kouho_a"),
                  ("K:sengen_marume_kuuran", "kouho_a"),
                  ("K:sengen_marume_gai", "kouho_a"),
                  ("K:sengen_douchi_kuuran", "kouho_a"),
                  ("sengen_a", "K:kouho_atai_kuuran"),
                  ("sengen_a", "K:kouho_tanni_kuuran")]
    for s, k in pair_level:
        t = pull(s, k)
        assert t.report.ok is True, (s, k)
        got |= {p.reason for p in t.pairs if p.reason}
    # 残り 3 個は、実装を差し替えて読んだ組を 1 つ落とすと出る
    args = (C.Declared.load(FIX / "sengen_a.csv"),
            C.Candidates.load(FIX / "kouho_a.csv"),
            C.Asofs.load(FIX / "kijunbi_a.csv"))
    real = C.compare_pick
    for n in (1, 2, 3):
        calls = {"i": 0}

        def fake(declared, candidates, asofs, _n=n):
            calls["i"] += 1
            out = real(declared, candidates, asofs)
            if calls["i"] == _n:
                out = C.Table(report=out.report, pairs=out.pairs[:-1],
                              declared=out.declared, candidates=out.candidates,
                              asofs=out.asofs, read_at=out.read_at, host=out.host)
            return out

        monkeypatch.setattr(C, "compare_pick", fake)
        out = C.verify(*args)
        assert out["ok"] is False
        got |= {p["reason"] for p in out["pending"]}
        monkeypatch.setattr(C, "compare_pick", real)
    assert got == set(C.STOP_REASONS)
    assert len(C.STOP_REASONS) == 18
    print("[measure] 止まる理由コード 18 個すべてに道がある(合成 3 枚で 6 個 + 崩した表"
          " 13 枚 + 差し替えた実装 3 本)")


def test_measure_read_error_count() -> None:
    """「表として読めない」で返る崩した表の枚数(理由コードには混ぜない)。"""
    n = 0
    for p in sorted((FIX / "kowashita").glob("*.csv")):
        loader = (C.Declared if p.name.startswith("sengen")
                  else C.Candidates if p.name.startswith("kouho") else C.Asofs)
        try:
            loader.load(p)
        except C.ReadError:
            n += 1
    assert n == 25
    assert len(list((FIX / "kowashita").glob("*.csv"))) == 39
    # 宣言表に無い rule を名乗る表は、読めはするが 1 組も読まずに「読めない」で返る
    C.Candidates.load(FIX / "kowashita" / "kouho_rule_gai.csv")
    with pytest.raises(C.ReadError):
        pull(k="K:kouho_rule_gai")
    print("[measure] 「表として読めない」で返る崩した表 25 枚(崩した表 39 枚のうち。"
          "理由コードには混ぜない)")


def test_measure_determinism() -> None:
    """2 回 + 3 枚の行順を入れ替えて読み直しても、判定部分の sha256 は同じ。"""
    shas = {pull().sha256() for _ in range(2)}
    base = pull()
    swap = C.SWAPS[0]
    swapped = C.compare_pick(C.Declared.load(FIX / "sengen_a.csv").swapped(swap),
                             C.Candidates.load(FIX / "kouho_a.csv").swapped(swap),
                             C.Asofs.load(FIX / "kijunbi_a.csv").swapped(swap))
    shas.add(swapped.sha256())
    assert len(shas) == 1
    assert base.sha256()[:12] == "d65984051640"
    assert pull(s="sengen_junide").sha256()[:12] == "3096774ee046"
    assert pull(s="sengen_maeushiro").sha256()[:12] == "fcaa91f39564"
    body = base.judgement_bytes().decode("utf-8")
    for word in (base.read_at, base.host, "読んだ時刻", "ホスト名"):
        assert word not in body
    out = C.verify(C.Declared.load(FIX / "sengen_a.csv"),
                   C.Candidates.load(FIX / "kouho_a.csv"),
                   C.Asofs.load(FIX / "kijunbi_a.csv"))
    assert out["ok"] is True
    assert out["件数の検算"]["4 値の合計"] == out["件数の検算"]["分母(組数 × 基準日の数)"]
    print(f"[measure] 判定部分の sha256 先頭 12 桁 sengen_a {base.sha256()[:12]}"
          f" / 裁定の種類を変えた表 {pull(s='sengen_junide').sha256()[:12]}"
          f" / 丸めの前後を入れ替えた表 {pull(s='sengen_maeushiro').sha256()[:12]}")
    print("[measure] 2 回 + 3 枚の行順を逆順に入れ替えて読み直し: 判定部分の sha256 は"
          " 3 回とも同じ(3/3 一致)")


def test_measure_inputs_are_not_modified() -> None:
    """読む前後で、入力ファイルの sha256 が 1 つも変わらない。"""
    before = {p: digest(p) for p in every_fixture()}
    assert len(before) == 44
    for s in ("sengen_a", "sengen_junide", "sengen_maeushiro"):
        pull(s=s)
    C.verify(C.Declared.load(FIX / "sengen_a.csv"),
             C.Candidates.load(FIX / "kouho_a.csv"),
             C.Asofs.load(FIX / "kijunbi_a.csv"))
    assert {p: digest(p) for p in every_fixture()} == before
    print("[measure] 読む前後で入力 44 ファイルの sha256 が同じ(verify が作る写しは"
          "メモリの中だけで、表には書かない)")


def test_measure_no_float_no_eval() -> None:
    """float も eval も subprocess も os も random も使わない。"""
    tree = ast.parse((ROOT / "compare_pick.py").read_text(encoding="utf-8-sig"))
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split(".")[0])
    assert mods == {"__future__", "argparse", "csv", "datetime", "decimal", "hashlib",
                    "json", "platform", "re", "sys", "dataclasses", "pathlib"}
    assert len(mods) == 12
    code = code_only((ROOT / "compare_pick.py").read_text(encoding="utf-8-sig"))
    assert "float" not in code
    for word in ("subprocess", "os.", "random", "eval", "exec"):
        assert word not in code, word
    print("[measure] 部品が import している module は 12 個(decimal を含む)で、"
          "float / eval / subprocess / os / random は 0 件")


def test_no_other_winning_paths() -> None:
    """換算・既定値・おすすめで動く経路が 1 つも無い。"""
    code = code_only((ROOT / "compare_pick.py").read_text(encoding="utf-8-sig"))
    for word in MOTANAI:
        assert word not in code, word
    # 比べるのは 2 か所(大きい方と小さい方)だけで、どちらも宣言された向きでしか動かない
    assert code.count("max ( keys . values ( ) )") == 1
    assert code.count("min ( keys . values ( ) )") == 1
    # 丸めは 1 つの関数の中だけ。登録の 3 種以外は呼ぶ前に止まる
    assert code.count("def round_value") == 1


def test_no_adjective_words() -> None:
    """出力にも実装にも形容の語を持たせない(数値が無いなら多寡を書かない)。"""
    code = code_only((ROOT / "compare_pick.py").read_text(encoding="utf-8-sig"))
    for word in KEIYOU:
        assert word not in code, word


def test_cli_has_only_four_subcommands(capsys) -> None:
    """CLI は pick / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    assert C.SUBCOMMANDS == ("pick", "check", "verify", "init")
    sub = next(a for a in C.build_parser()._actions
               if hasattr(a, "choices") and a.choices)
    assert sorted(sub.choices) == sorted(C.SUBCOMMANDS)
    for name, p in sub.choices.items():
        flags = {o for a in p._actions for o in a.option_strings}
        assert flags == {"-h", "--help"}, name
    assert C.main(["check", str(FIX / "sengen_a.csv"), str(FIX / "kouho_a.csv"),
                   str(FIX / "kijunbi_a.csv")]) == 3
    assert "22 組" in capsys.readouterr().out


def test_exit_codes() -> None:
    """止まった組も決まらない組も無いときだけ 0、あれば 3、読めなければ 2。"""
    a = [str(FIX / "sengen_a.csv"), str(FIX / "kouho_a.csv"),
         str(FIX / "kijunbi_a.csv")]
    assert C.main(["check"] + a) == 3
    assert C.main(["verify"] + a) == 0
    assert C.main(["check", a[0], str(FIX / "kowashita" / "kouho_0gyou.csv"),
                   a[2]]) == 2


def test_init_writes_three_templates(tmp_path) -> None:
    """ひな型は 3 枚。書いたひな型はそのまま読めて、比較で 1 組が決まる。"""
    paths = C.init(tmp_path / "ひな型")
    assert len(paths) == 3 and all(p.exists() for p in paths)
    t = C.compare_pick(C.Declared.load(paths[0]), C.Candidates.load(paths[1]),
                       C.Asofs.load(paths[2]))
    assert t.report.ok is True
    assert t.counts()["分母(組数 × 基準日の数)"] == 1
    assert t.pairs[0].result == "比較で決まった"


def test_rate_is_not_returned_alone() -> None:
    """率だけを返す呼び方が無い。件数には必ず分母の内訳と検算と 5 つの固定行が付く。"""
    c = pull().counts()
    for key in ("分母に含めたもの", "件数の合計の検算", "順位の列で比較を代えない",
                "単位を揃えない", "丸めの前後に既定を当てない", "同値を向きで勝たせない",
                "式を評価しない"):
        assert c[key]
    assert not any("率" in k for k in c)
    code = code_only((ROOT / "compare_pick.py").read_text(encoding="utf-8-sig"))
    assert "/ len (" not in code and "* 100" not in code


def test_stopped_and_undecided_are_not_mixed() -> None:
    """止まったと決まらないを混ぜない。止まった組には勝った行も値も付かない。"""
    t = pull()
    for p in t.pairs:
        if p.result == "止まった":
            assert p.reason in C.PAIR_REASONS and p.why == ""
            assert p.row_id == "" and p.value == ""
        elif p.result == "比較では決まらない":
            assert p.why in C.UNDECIDED and p.reason == ""
            assert p.row_id == "" and p.value == ""
        else:
            assert p.row_id and p.reason == "" and p.why == ""
    have = {r.row_id for r in C.Candidates.load(FIX / "kouho_a.csv").items}
    assert {p.row_id for p in t.pairs if p.row_id} <= have
    assert len(t.decided()) == 5
