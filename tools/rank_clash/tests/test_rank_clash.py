"""rank_clash のテスト。合成 fixture は `fixtures/` に commit 済(実データ・実在の値は入れない)。

test_measure_* が記事に載せた数値の出どころで、assert で固定している(値が変われば記事も変える前提)。
測っているものは 5 つある。

  (1) rule 5 × 対象 4 = 20 組が 4 値に分かれ、決まらない理由別の件数と分母の内訳が付く側
  (2) 同じ順位の行が 2 本当たる組は、具体的に書かれた行を勝たせずに「決まらない」へ落ちる側。
      その 1 欄の順位を上げると、その 2 組だけが動く(= この記事の骨)
  (3) 順位の欄が空のまま 2 本当たる組は、空欄を 0(本則)と読まずに「決まらない」へ落ちる側
  (4) 裁定の宣言が「順位では決まらない」と言っている rule は、順位を比べずに落ちる側
  (5) 4 値の件数の合計 = rule 数 × 対象数 が合う側

(1) の 4 値は、テストの側でも 3 枚の表の行から直に組み立てて確かめている(部品の判定は呼ばず、
fixture の行から別に計算する)。
"""
from __future__ import annotations

import ast
import hashlib
import io
import re
import sys
import tokenize
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIX = ROOT / "fixtures"
PLAN = ROOT.parent.parent          # 07_記事化商品化計画(出典の行を開くため)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FIX))
import rank_clash as R  # noqa: E402
import make_fixtures as M  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの -> その行に在るはずの語
REAL_SOURCES = {
    M.SRC_JUNBAN: "いちばん高い",
    M.SRC_SOTO: "表の外の判断",
    M.SRC_KITEI: "既定にしない",
    M.SRC_MUGEN: "読み替えない",
    M.SRC_KOUHO: "登録済みとして扱わない",
}

# 形容の語(出力にも実装にも持たせない = 数値が無いなら多寡を書かない)
KEIYOU = ("多い", "少ない", "ほとんど", "かなり", "著しく", "急いで")

# 勝たせ方の経路の名前(実装に 1 つも無いことを見る)
KATASEKATA = ("具体度", "specificity", "新しい方", "最後の行", "最初の行",
              "payload", "金額", "料率", "amount", "最長一致", "勝たせる")


def path_of(name: str) -> Path:
    return FIX / "kowashita" / f"{name[2:]}.csv" if name.startswith("K:") \
        else FIX / f"{name}.csv"


def pull(g: str = "gyou_a", s: str = "sengen_a", t: str = "taishou_a") -> R.Table:
    return R.rank_clash(R.Sheet.load(path_of(g)), R.Declared.load(path_of(s)),
                        R.Targets.load(path_of(t)))


def pair_of(table: R.Table, rule_id: str, target_id: str) -> R.Pair:
    return next(p for p in table.pairs
                if p.rule_id == rule_id and p.target_id == target_id)


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


def expect_four(gyou: list[list[str]], sengen: list[list[str]],
                taishou: list[list[str]]) -> dict[str, int]:
    """4 値を、3 枚の表の行から直に組み立てる(部品の判定には頼らない)。"""
    rules = {row[0]: {"kind": row[1], "wild": row[3]} for row in sengen[1:]}
    out = dict.fromkeys(R.RESULTS, 0)
    for rule_id in sorted(rules):
        wild, kind = rules[rule_id]["wild"], rules[rule_id]["kind"]
        for target in sorted(taishou[1:], key=lambda r: r[0]):
            have = dict(part.split("=") for part in target[1].split("|"))
            hit = []
            for row in gyou[1:]:
                if row[1] != rule_id:
                    continue
                seg = dict(part.split("=") for part in row[2].split("|"))
                if all(v == wild or have.get(k) == v for k, v in seg.items()):
                    hit.append(row)
            if len(hit) == 0:
                out[R.RESULTS[1]] += 1
            elif len(hit) == 1:
                out[R.RESULTS[0]] += 1
            elif kind != R.KINDS[0] or any(not row[3] for row in hit):
                out[R.RESULTS[2]] += 1
            else:
                top = max(int(row[3]) for row in hit)
                best = [row for row in hit if int(row[3]) == top]
                out[R.RESULTS[0 if len(best) == 1 else 2]] += 1
    return out


# ---------------------------------------------------------------- 入り口

def test_committed_tables_load() -> None:
    """commit 済の表は、表として読める(止まる理由が 0 件)。"""
    assert len(R.Sheet.load(FIX / "gyou_a.csv").items) == 9
    assert len(R.Declared.load(FIX / "sengen_a.csv").items) == 5
    assert len(R.Targets.load(FIX / "taishou_a.csv").items) == 4
    assert R.Targets.load(FIX / "taishou_a.csv").swap == "逆順"
    assert R.Sheet.load(FIX / "gyou_a.csv").dims == ("次元A", "次元B")
    assert R.Targets.load(FIX / "taishou_a.csv").dims == ("次元A", "次元B")
    for name in ("gyou_a", "gyou_kuuran_ume", "gyou_guutai"):
        assert R.Sheet.load(FIX / f"{name}.csv").pending == (), name
    for name in ("sengen_a", "sengen_junide"):
        assert R.Declared.load(FIX / f"{name}.csv").pending == (), name
    assert R.Targets.load(FIX / "taishou_a.csv").pending == ()


def test_sources_point_at_real_lines() -> None:
    """fixture の出典のうち 5 件は、この repo の実在の行を指している。"""
    for src, word in REAL_SOURCES.items():
        rel, line = src.rsplit(" L", 1)
        text = (PLAN / rel).read_text(encoding="utf-8-sig").splitlines()
        assert word in text[int(line) - 1], src


def test_fixtures_carry_no_values() -> None:
    """fixture に料率・金額が 1 つも入っていない(この部品は値を持たない)。"""
    for p in every_fixture():
        body = p.read_text(encoding="utf-8-sig")
        assert "%" not in body and "円" not in body, p.name
        rest = re.sub(r"articles/\S+?\.md", "", body)            # 出典の記事名
        rest = re.sub(r"[GRT]\d{2}", "", rest)                   # 行 / rule / 対象 id
        rest = re.sub(r"L\d+", "", rest)                         # 出典の行番号
        assert not re.search(r"\d{2,}", rest.replace("10", "").replace("20", "")), \
            p.name


def test_row_table_has_no_value_column() -> None:
    """行の表に値の列が無い(値の大小で勝たせる経路を持てない、の物理形)。"""
    assert R.GYOU_COLUMNS == ("row_id", "rule_id", "seg", "priority", "source")
    assert len(R.GYOU_COLUMNS) == 5
    assert not [c for c in R.GYOU_COLUMNS if c in ("value", "payload", "amount")]


# ---------------------------------------------------------------- 測ったもの

def test_measure_twenty_pairs_split_into_four() -> None:
    """(1) rule 5 × 対象 4 = 20 組が 4 値に分かれ、理由別と分母の内訳が付く。"""
    t = pull()
    c = t.counts()
    assert c["行の表の行数"] == 9
    assert c["裁定の宣言の行数(rule 数)"] == 5
    assert c["対象数"] == 4
    assert c["分母(rule 数 × 対象数)"] == 20
    assert c["4 値"] == {"1 本に決まった": 11, "当たらない": 3, "決まらない": 6,
                         "止まった": 0}
    assert c["決まらない理由別"] == {"同順位で 2 本以上": 2, "順位の欄が空": 2,
                                     "宣言に無い裁定が要る": 2}
    assert t.verdict == "決まらない"
    # 4 値を、3 枚の表の行から別に組み立てても同じになる(部品の判定を呼ばない)
    assert c["4 値"] == expect_four(M.gyou_rows(), M.sengen_rows(), M.taishou_rows())
    # 率の欄は無い。分母の内訳と検算は消せない
    assert not any("率" in k for k in c)
    assert "20 組" in str(c["分母に含めたもの"])
    assert "4 値の合計 20 / 分母 20" in str(c["件数の合計の検算"])
    print(f"[measure] gyou_a / sengen_a / taishou_a: rule 5 × 対象 4 = 20 組"
          f" → 4 値 {c['4 値']}")
    print(f"[measure] 決まらない 6 件の内訳 = {c['決まらない理由別']}"
          "(分母は rule 数 × 対象数 = 20。率は単独では返らない)")


def test_measure_specific_row_does_not_win() -> None:
    """(2) 同順位なら具体的な行も勝たない。順位を 1 欄上げるとその 2 組だけが動く。"""
    before, after = pull(), pull(g="gyou_guutai")
    for target in ("T01", "T02"):
        p = pair_of(before, "R02", target)
        assert p.result == "決まらない" and p.why == "同順位で 2 本以上"
        assert p.hits == 2 and p.row_id == "" and p.priority == ""
    assert before.counts()["4 値"]["決まらない"] == 6
    assert after.counts()["4 値"]["決まらない"] == 4
    assert after.counts()["決まらない理由別"] == {"順位の欄が空": 2,
                                                  "宣言に無い裁定が要る": 2}
    moved = [(p.rule_id, p.target_id) for p, q in zip(before.pairs, after.pairs)
             if (p.result, p.why) != (q.result, q.why)]
    assert moved == [("R02", "T01"), ("R02", "T02")]
    assert len([p for p, q in zip(before.pairs, after.pairs)
                if (p.result, p.why) == (q.result, q.why)]) == 18
    # 勝ったのは「具体的だから」ではなく「順位が 10 と書いてあるから」
    assert pair_of(after, "R02", "T01").row_id == "G04"
    assert pair_of(after, "R02", "T01").priority == "10"
    assert pair_of(after, "R02", "T01").hits == 2
    print("[measure] 同順位で 2 本当たる R02 の T01 / T02 は 決まらない。勝った行 id も"
          "順位も空のまま(具体的に書かれた行を勝たせる経路が無い)")
    print("[measure] 行の順位を 1 欄 0 → 10: 決まらない 6 → 4。動いたのは R02 の 2 組"
          "だけで、残る 18 組は結果も理由も変わらない(勝ったのは G04、順位 10)")


def test_measure_blank_priority_is_not_filled() -> None:
    """(3) 順位の欄が空のまま 2 本当たる組は、空欄を 0 と読まずに落ちる。"""
    before, after = pull(), pull(g="gyou_kuuran_ume")
    for target in ("T01", "T03"):
        p = pair_of(before, "R03", target)
        assert p.result == "決まらない" and p.why == "順位の欄が空"
        assert p.hits == 2 and p.row_id == ""
    # 1 本しか当たらない組は、順位が空でも「1 本に決まった」(裁定が要らない)
    assert pair_of(before, "R03", "T02").result == "1 本に決まった"
    assert pair_of(before, "R03", "T02").row_id == "G05"
    assert after.counts()["4 値"]["決まらない"] == 4
    assert after.counts()["決まらない理由別"] == {"同順位で 2 本以上": 2,
                                                  "宣言に無い裁定が要る": 2}
    moved = [(p.rule_id, p.target_id) for p, q in zip(before.pairs, after.pairs)
             if (p.result, p.why) != (q.result, q.why)]
    assert moved == [("R03", "T01"), ("R03", "T03")]
    assert pair_of(after, "R03", "T01").row_id == "G06"
    assert pair_of(after, "R03", "T01").priority == "20"
    print("[measure] 順位の欄が空のまま 2 本当たる R03 の T01 / T03 は 決まらない"
          "(空欄を 0 = 本則と読まない)。空欄を 20 で埋めると 決まらない 6 → 4")
    print("[measure] 1 本しか当たらない R03 の T02 は、順位が空でも 1 本に決まった"
          "(裁定が要らない組には順位を求めない)")


def test_measure_declared_non_priority_adjudication() -> None:
    """(4) 宣言が「順位では決まらない」と言う rule は、順位を比べずに落ちる。"""
    before, after = pull(), pull(s="sengen_junide")
    for target in ("T03", "T04"):
        p = pair_of(before, "R05", target)
        assert p.result == "決まらない" and p.why == "宣言に無い裁定が要る"
        assert p.hits == 2
    assert R.Declared.load(FIX / "sengen_a.csv").of("R05").by_priority is False
    assert R.Declared.load(FIX / "sengen_junide.csv").of("R05").by_priority is True
    assert after.counts()["4 値"]["決まらない"] == 4
    moved = [(p.rule_id, p.target_id) for p, q in zip(before.pairs, after.pairs)
             if (p.result, p.why) != (q.result, q.why)]
    assert moved == [("R05", "T03"), ("R05", "T04")]
    assert pair_of(after, "R05", "T03").row_id == "G09"
    # 当たった本数が 1 本以下の組は、宣言の種類に関わらず結果が変わらない
    assert pair_of(before, "R05", "T01").result == "1 本に決まった"
    assert pair_of(after, "R05", "T01").result == "1 本に決まった"
    print("[measure] 裁定の宣言が「宣言された順位では決まらない」の R05 は、2 本当たった"
          " T03 / T04 で順位を比べずに 決まらない(宣言に無い裁定が要る)")
    print("[measure] 宣言の 1 欄を「宣言された順位」に変える: 決まらない 6 → 4。動いたのは"
          " R05 の 2 組だけで、1 本しか当たらない T01 / T02 は変わらない")


def test_measure_row_order_does_not_decide() -> None:
    """並び順でも後から書かれた順でも勝たない(3 枚の行順を入れ替えても同じ)。"""
    base = pull()
    swapped = R.rank_clash(R.Sheet.load(FIX / "gyou_a.csv").swapped("逆順"),
                           R.Declared.load(FIX / "sengen_a.csv").swapped("逆順"),
                           R.Targets.load(FIX / "taishou_a.csv").swapped("逆順"))
    assert swapped.sha256() == base.sha256()
    assert swapped.judgement_bytes() == base.judgement_bytes()
    # 2 本当たった組は、入れ替えても「決まらない」のまま(先頭の行を採らない)
    assert pair_of(swapped, "R02", "T01").result == "決まらない"
    assert {p.row_id for p in swapped.pairs} == {p.row_id for p in base.pairs}
    print("[measure] 3 枚の行順を逆順に入れ替えて読み直し: 判定部分のバイト列が同じ"
          "(先頭・末尾・後から書かれた方を採る経路が無い)")


def test_measure_no_hit_and_undecided_are_not_mixed() -> None:
    """当たらないと決まらないを混ぜない。当たらない組には勝った行が付かない。"""
    t = pull()
    nothing = [p for p in t.pairs if p.result == "当たらない"]
    assert len(nothing) == 3
    assert [(p.rule_id, p.target_id) for p in nothing] == [("R04", "T02"),
                                                           ("R04", "T03"),
                                                           ("R04", "T04")]
    assert all(p.row_id == "" and p.priority == "" and p.hits == 0 for p in nothing)
    # 勝った行 id は、行の表にそのまま在る id だけ(作った行は 1 つも無い)
    have = {r.row_id for r in R.Sheet.load(FIX / "gyou_a.csv").items}
    assert {p.row_id for p in t.pairs if p.row_id} <= have
    assert len({p.row_id for p in t.pairs if p.row_id}) == 6
    print("[measure] 当たらない 3 組はどれも勝った行 id が空。返した行 id は 11 組とも"
          "行の表にそのまま在る 6 種類で、作った行は 0 件")


def test_measure_stop_reason_codes_all_reachable(monkeypatch) -> None:
    """止まる理由コード 9 個すべてに道がある(崩した表 8 枚 + 差し替えた実装 3 本)。"""
    got: set[str] = set()
    cases = [("K:gyou_shutten_nashi", "sengen_a", "taishou_a"),
             ("gyou_a", "K:sengen_shutten_nashi", "taishou_a"),
             ("gyou_a", "sengen_a", "K:taishou_shutten_nashi"),
             ("K:gyou_id_juufuku", "sengen_a", "taishou_a"),
             ("K:gyou_juni_gai", "sengen_a", "taishou_a"),
             ("K:gyou_kigou_gai", "sengen_a", "taishou_a"),
             ("K:gyou_rule_gai", "sengen_a", "taishou_a"),
             ("gyou_a", "K:sengen_juufuku", "taishou_a")]
    for g, s, t in cases:
        table = pull(g, s, t)
        assert table.report.ok is False, (g, s, t)
        assert table.pairs == ()                 # 1 組も読まない
        got |= {p.reason for p in table.report.pending}
    assert len(cases) == 8
    # 残り 3 個は、実装を差し替えて読んだ組を 1 つ落とすと出る
    args = (R.Sheet.load(FIX / "gyou_a.csv"), R.Declared.load(FIX / "sengen_a.csv"),
            R.Targets.load(FIX / "taishou_a.csv"))
    real = R.rank_clash
    for n in (1, 2, 3):
        calls = {"i": 0}

        def fake(sheet, declared, targets, _n=n):
            calls["i"] += 1
            out = real(sheet, declared, targets)
            if calls["i"] == _n:
                out = R.Table(report=out.report, pairs=out.pairs[:-1],
                              sheet=out.sheet, declared=out.declared,
                              targets=out.targets, read_at=out.read_at,
                              host=out.host)
            return out

        monkeypatch.setattr(R, "rank_clash", fake)
        out = R.verify(*args)
        assert out["ok"] is False
        got |= {p["reason"] for p in out["pending"]}
        monkeypatch.setattr(R, "rank_clash", real)
    assert got == set(R.STOP_REASONS)
    assert len(R.STOP_REASONS) == 9
    print("[measure] 止まる理由コード 9 個すべてに道がある(崩した表 8 枚 +"
          " 差し替えた実装 3 本)")


def test_measure_read_error_count() -> None:
    """「表として読めない」で返る崩した表は 27 枚(理由コードには混ぜない)。"""
    n = 0
    for p in sorted((FIX / "kowashita").glob("*.csv")):
        loader = (R.Sheet if p.name.startswith("gyou")
                  else R.Declared if p.name.startswith("sengen") else R.Targets)
        try:
            loader.load(p)
        except R.ReadError:
            n += 1
    assert n == 27
    assert len(list((FIX / "kowashita").glob("*.csv"))) == 36
    print("[measure] 「表として読めない」で返る崩した表 27 枚"
          "(崩した表 36 枚のうち。理由コードには混ぜない)")


def test_dimension_names_must_match() -> None:
    """次元の名前が表ごとに違うのは、理由コードでなく「表として読めない」で返る。"""
    with pytest.raises(R.ReadError):
        pull(g="K:gyou_jigen_chigai")
    assert R.Sheet.load(path_of("K:gyou_jigen_chigai")).dims == ("次元A", "次元B",
                                                                 "次元C")


def test_measure_determinism() -> None:
    """2 回 + 3 枚の行順を入れ替えて読み直しても、判定部分の sha256 は同じ。"""
    shas = {pull().sha256() for _ in range(2)}
    base = pull()
    swapped = R.rank_clash(R.Sheet.load(FIX / "gyou_a.csv").swapped("逆順"),
                           R.Declared.load(FIX / "sengen_a.csv").swapped("逆順"),
                           R.Targets.load(FIX / "taishou_a.csv").swapped("逆順"))
    shas.add(swapped.sha256())
    assert len(shas) == 1
    assert base.sha256()[:12] == "b17b13f912f4"
    assert pull(g="gyou_guutai").sha256()[:12] == "d5a3970e87c5"
    body = base.judgement_bytes().decode("utf-8")
    for word in (base.read_at, base.host, "読んだ時刻", "ホスト名"):
        assert word not in body
    out = R.verify(R.Sheet.load(FIX / "gyou_a.csv"),
                   R.Declared.load(FIX / "sengen_a.csv"),
                   R.Targets.load(FIX / "taishou_a.csv"))
    assert out["ok"] is True
    assert out["件数の検算"]["4 値の合計"] == out["件数の検算"]["分母(rule 数 × 対象数)"]
    print(f"[measure] 判定部分の sha256 先頭 12 桁 gyou_a {base.sha256()[:12]}"
          f" / 順位を上げた表 {pull(g='gyou_guutai').sha256()[:12]}")
    print("[measure] 2 回 + 3 枚の行順を逆順に入れ替えて読み直し: 判定部分の sha256 は"
          " 3 回とも同じ(3/3 一致)")


def test_measure_inputs_are_not_modified() -> None:
    """読む前後で、入力ファイルの sha256 が 1 つも変わらない。"""
    before = {p: digest(p) for p in every_fixture()}
    assert len(before) == 42
    for g in ("gyou_a", "gyou_guutai", "gyou_kuuran_ume"):
        pull(g=g)
    pull(s="sengen_junide")
    assert {p: digest(p) for p in every_fixture()} == before
    print("[measure] 読む前後で入力 42 ファイルの sha256 が同じ")


def test_measure_no_float_no_subprocess() -> None:
    """float も subprocess も os も random も使わない。"""
    tree = ast.parse((ROOT / "rank_clash.py").read_text(encoding="utf-8-sig"))
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split(".")[0])
    assert mods == {"__future__", "argparse", "csv", "datetime", "hashlib", "json",
                    "platform", "re", "sys", "dataclasses", "pathlib"}
    assert len(mods) == 11
    code = code_only((ROOT / "rank_clash.py").read_text(encoding="utf-8-sig"))
    assert "float" not in code
    for word in ("subprocess", "os.", "random"):
        assert word not in code, word
    print("[measure] 部品が import している module は 11 個で、subprocess / os /"
          " random / float は 0 件")


def test_no_other_winning_paths() -> None:
    """具体さ・並び順・値の大小で勝たせる引数も関数も 1 つも無い。"""
    code = code_only((ROOT / "rank_clash.py").read_text(encoding="utf-8-sig"))
    for word in KATASEKATA:
        assert word not in code, word
    # 順位を比べるのは 1 か所だけ(その 1 か所も priority の整数しか見ない)
    assert code.count("max ( int (") == 1


def test_no_adjective_words() -> None:
    """出力にも実装にも形容の語を持たせない(数値が無いなら多寡を書かない)。"""
    code = code_only((ROOT / "rank_clash.py").read_text(encoding="utf-8-sig"))
    for word in KEIYOU:
        assert word not in code, word


def test_cli_has_only_four_subcommands(capsys) -> None:
    """CLI は resolve / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    assert R.SUBCOMMANDS == ("resolve", "check", "verify", "init")
    sub = next(a for a in R.build_parser()._actions
               if hasattr(a, "choices") and a.choices)
    assert sorted(sub.choices) == sorted(R.SUBCOMMANDS)
    for name, p in sub.choices.items():
        flags = {o for a in p._actions for o in a.option_strings}
        assert flags == {"-h", "--help"}, name
    assert R.main(["check", str(FIX / "gyou_a.csv"), str(FIX / "sengen_a.csv"),
                   str(FIX / "taishou_a.csv")]) == 3
    assert "20 組" in capsys.readouterr().out


def test_exit_codes() -> None:
    """決まらない組が 1 つも無いときだけ 0、止まれば 3、読めなければ 2。"""
    a = [str(FIX / "gyou_a.csv"), str(FIX / "sengen_a.csv"),
         str(FIX / "taishou_a.csv")]
    assert R.main(["check"] + a) == 3
    assert R.main(["verify"] + a) == 0
    assert R.main(["check", str(FIX / "kowashita" / "gyou_0gyou.csv"),
                   a[1], a[2]]) == 2


def test_init_writes_three_templates(tmp_path) -> None:
    """ひな型は 3 枚。書いたひな型はそのまま読める。"""
    paths = R.init(tmp_path / "ひな型")
    assert len(paths) == 3 and all(p.exists() for p in paths)
    t = R.rank_clash(R.Sheet.load(paths[0]), R.Declared.load(paths[1]),
                     R.Targets.load(paths[2]))
    assert t.report.ok is True
    assert t.counts()["分母(rule 数 × 対象数)"] == 2


def test_rate_is_not_returned_alone() -> None:
    """率だけを返す呼び方が無い。件数には必ず分母の内訳と検算と 4 つの固定行が付く。"""
    c = pull().counts()
    for key in ("分母に含めたもの", "件数の合計の検算", "具体さで勝たせない",
                "並び順で勝たせない", "値の大小で勝たせない", "順位の欄が空なら補わない"):
        assert c[key]
    assert not any("率" in k for k in c)
    code = code_only((ROOT / "rank_clash.py").read_text(encoding="utf-8-sig"))
    assert "/ len (" not in code and "* 100" not in code
