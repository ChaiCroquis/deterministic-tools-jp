"""basis_map のテスト。合成 fixture は `fixtures/` に commit 済(実データ・実在の値は入れない)。

test_measure_* が記事に載せた数値の出どころで、assert で固定している(値が変われば記事も変える前提)。
測っているものは 5 つある。

  (1) rule 5 × 対象 4 = 20 組が 4 値に分かれ、決まらない理由別の件数と分母の内訳が付く側
  (2) 台帳の 1 欄を 候補 → 登録済 に書き換えると、その種別の 4 組だけが動く側(= この記事の骨)
  (3) 別名の宣言を 1 つ外すと、その表記が宣言外になり 2 組が決まらないへ動く側
      (文字列が似ていることを理由に寄せる経路が無い、の物理形)
  (4) 手元に無い種別を別の日付で代用せず、日付を 1 つも作らない側
  (5) 4 値の件数の合計 = rule 数 × 対象数 が合う側

(1) の 4 値は、テストの側でも台帳から直に組み立てて確かめている(部品の判定は呼ばず、
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
import basis_map as B  # noqa: E402
import make_fixtures as M  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの -> その行に在るはずの語
REAL_SOURCES = {
    M.SRC_SENGEN: "行の側に列として宣言させる",
    M.SRC_TOMERU: "理由コードで止めて",
    M.SRC_YURE: "表記の揺れ",
    M.SRC_SUITEI: "推測して足す経路が無い",
    M.SRC_SENGEN_KARA: "表の宣言から取る",
}

# 形容の語(出力にも実装にも持たせない = 数値が無いなら多寡を書かない)
KEIYOU = ("多い", "少ない", "ほとんど", "かなり", "著しく", "急いで")

# 日付を作る / ずらす / 今日を使う経路の名前(実装に 1 つも無いことを見る)
TSUKURU = ("月初", "月末", "前営業日", "翌営業日", "today", "now(", "date.today",
           "timedelta", "relativedelta", "fromtimestamp")


def path_of(name: str) -> Path:
    return FIX / "kowashita" / f"{name[2:]}.csv" if name.startswith("K:") \
        else FIX / f"{name}.csv"


def pull(s: str = "shubetsu_a", y: str = "youkyuu_a",
         t: str = "temoto_a") -> B.Table:
    return B.basis_map(B.Registry.load(path_of(s)), B.Demands.load(path_of(y)),
                       B.Hand.load(path_of(t)))


def pair_of(t: B.Table, rule_id: str, target_id: str) -> B.Pair:
    return next(p for p in t.pairs
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


def expect_four(shubetsu: list[list[str]], youkyuu: list[list[str]],
                temoto: list[list[str]]) -> dict[str, int]:
    """4 値を、3 枚の表の行から直に組み立てる(部品の判定には頼らない)。"""
    label_of: dict[str, str] = {}
    status: dict[str, str] = {}
    for kid, name, alias, _m, _f, st, _s in shubetsu[1:]:
        status.setdefault(kid, st)
        for lab in [name] + [a for a in alias.split(B.ALIAS_SEP) if a]:
            label_of.setdefault(lab, kid)
    targets = sorted({r[0] for r in temoto[1:]})
    out = dict.fromkeys(B.RESULTS, 0)
    for _rid, kind_id, _src in youkyuu[1:]:
        for t in targets:
            rows = [r for r in temoto[1:] if r[0] == t]
            others = sum(1 for r in rows if r[1] not in label_of)
            hit = [r for r in rows if label_of.get(r[1]) == kind_id]
            if status[kind_id] != B.STATUSES[0]:
                out[B.RESULTS[2]] += 1
            elif len(hit) >= 2 or (not hit and others):
                out[B.RESULTS[2]] += 1
            elif hit:
                out[B.RESULTS[0]] += 1
            else:
                out[B.RESULTS[1]] += 1
    return out


# ---------------------------------------------------------------- 入り口

def test_committed_tables_load() -> None:
    """commit 済の表は、表として読める(止まる理由が 0 件)。"""
    assert len(B.Registry.load(FIX / "shubetsu_a.csv").items) == 6
    assert len(B.Demands.load(FIX / "youkyuu_a.csv").items) == 5
    assert len(B.Hand.load(FIX / "temoto_a.csv").items) == 12
    assert B.Hand.load(FIX / "temoto_a.csv").swap == "逆順"
    assert B.Hand.load(FIX / "temoto_a.csv").targets == ("T01", "T02", "T03", "T04")
    for name in ("shubetsu_a", "shubetsu_touroku", "shubetsu_betsumei_nashi"):
        assert B.Registry.load(FIX / f"{name}.csv").pending == (), name
    assert B.Demands.load(FIX / "youkyuu_a.csv").pending == ()
    assert B.Hand.load(FIX / "temoto_a.csv").pending == ()


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
        # 日付(YYYY-MM-DD / YYYY/MM/DD)以外の 2 桁以上の数字を置かない
        rest = re.sub(r"articles/\S+?\.md", "", body)            # 出典の記事名
        rest = re.sub(r"\d{4}[-/]\d{2}[-/]\d{2}", "", rest)       # 日付
        rest = re.sub(r"[KRT]\d{2}", "", rest)                 # 種別 / rule / 対象 id
        rest = re.sub(r"L\d+", "", rest)                       # 出典の行番号
        assert not re.search(r"\d{2,}", rest), p.name


# ---------------------------------------------------------------- 測ったもの

def test_measure_twenty_pairs_split_into_four() -> None:
    """(1) rule 5 × 対象 4 = 20 組が 4 値に分かれ、理由別と分母の内訳が付く。"""
    t = pull()
    c = t.counts()
    assert c["要求表の行数"] == 5
    assert c["対象数"] == 4
    assert c["手元の表の行数"] == 12
    assert c["分母(rule 数 × 対象数)"] == 20
    assert c["4 値"] == {"決まった": 6, "手元に無い": 7, "決まらない": 7, "止まった": 0}
    assert c["決まらない理由別"] == {"候補どまり": 4, "宣言外の表記": 2,
                                     "同じ種別に 2 つ": 1}
    assert t.verdict == "決まらない"
    # 4 値を、台帳の行から別に組み立てても同じになる(部品の判定を呼ばない)
    assert c["4 値"] == expect_four(M.shubetsu_rows(), M.youkyuu_rows(),
                                    M.temoto_rows())
    # 率の欄は無い。分母の内訳と検算は消せない
    assert "率" not in "".join(k for k in c)
    assert "20 組" in str(c["分母に含めたもの"])
    assert "4 値の合計 20 / 分母 20" in str(c["件数の合計の検算"])
    print(f"[measure] shubetsu_a / youkyuu_a / temoto_a: rule 5 × 対象 4 = 20 組"
          f" → 4 値 {c['4 値']}")
    print(f"[measure] 決まらない 7 件の内訳 = {c['決まらない理由別']}"
          "(分母は rule 数 × 対象数 = 20。率は単独では返らない)")


def test_measure_one_status_cell_moves_four_pairs() -> None:
    """(2) 台帳の 1 欄を 候補 → 登録済 に書き換えると、その種別の 4 組だけが動く。"""
    before, after = pull(), pull(s="shubetsu_touroku")
    assert before.counts()["4 値"]["決まらない"] == 7
    assert after.counts()["4 値"]["決まらない"] == 4
    assert after.counts()["決まらない理由別"] == {"宣言外の表記": 3,
                                                  "同じ種別に 2 つ": 1}
    moved = [(p.rule_id, p.target_id) for p, q in zip(before.pairs, after.pairs)
             if (p.result, p.why) != (q.result, q.why)]
    assert moved == [("R04", "T01"), ("R04", "T02"), ("R04", "T03"), ("R04", "T04")]
    assert [pair_of(after, "R04", t).result for t in ("T01", "T02", "T03", "T04")]         == ["決まった", "決まらない", "手元に無い", "決まった"]
    assert pair_of(after, "R04", "T02").why == "宣言外の表記"
    other = [p for p, q in zip(before.pairs, after.pairs)
             if (p.result, p.why) == (q.result, q.why)]
    assert len(other) == 16
    # 候補のままの時、どの組にも日付は付かない(候補を登録済み扱いにしない)
    assert all(p.date == "" for p in before.pairs if p.rule_id == "R04")
    assert pair_of(after, "R04", "T01").date == "2026-02-01"
    assert pair_of(after, "R04", "T04").date == "2026-02-15"
    print("[measure] 種別の台帳の 1 欄 候補 → 登録済: 決まらない 7 → 4。動いたのは"
          " R04 の 4 組だけで、残る 16 組は結果も理由も変わらない")
    print("[measure] 動いた 4 組の行き先 = T01 決まった / T02 決まらない(宣言外の表記)"
          " / T03 手元に無い / T04 決まった(4 つに割れる)")


def test_measure_alias_declaration_is_the_only_bridge() -> None:
    """(3) 別名の宣言を 1 つ外すと、その表記は宣言外になり 2 組が決まらないへ動く。"""
    before, after = pull(), pull(s="shubetsu_betsumei_nashi")
    assert pair_of(before, "R02", "T01").result == "決まった"
    assert pair_of(before, "R02", "T01").label == "賃金締め日"
    assert pair_of(after, "R02", "T01").result == "決まらない"
    assert pair_of(after, "R02", "T01").why == "宣言外の表記"
    assert pair_of(before, "R05", "T01").result == "手元に無い"
    assert pair_of(after, "R05", "T01").why == "宣言外の表記"
    moved = [(p.rule_id, p.target_id) for p, q in zip(before.pairs, after.pairs)
             if p.result != q.result]
    assert moved == [("R02", "T01"), ("R05", "T01")]
    assert after.counts()["4 値"] == {"決まった": 5, "手元に無い": 6,
                                      "決まらない": 9, "止まった": 0}
    # 「賃金締め日」と「賃金締切日」は 2 文字しか違わないが、宣言が無ければ寄らない
    assert B.Registry.load(FIX / "shubetsu_betsumei_nashi.csv").by_label("賃金締め日") is None
    print("[measure] 別名の宣言 1 行を外す: 決まった 6 → 5 / 手元に無い 7 → 6 /"
          " 決まらない 7 → 9。動いたのは その表記を持つ T01 の 2 組だけ")
    print("[measure] 「賃金締め日」は「賃金締切日」と 2 文字しか違わないが、宣言が"
          "無ければ写らない(by_label は None)")


def test_measure_same_kind_twice_is_not_picked() -> None:
    """同じ種別に日付が 2 つある対象は、新しい方も先の方も採らずに決まらない。"""
    p = pair_of(pull(), "R01", "T03")
    assert p.result == "決まらない" and p.why == "同じ種別に 2 つ"
    assert p.date == "" and p.label == ""
    # 同じ対象の別の rule は、巻き込まれずに決まる
    assert pair_of(pull(), "R03", "T03").result == "決まった"
    print("[measure] 同じ種別に日付が 2 つある T03 の R01 は 決まらない。"
          "渡す日付も手元の表記も空のまま(新しい方も先の方も採らない)")


def test_measure_missing_kind_is_not_substituted() -> None:
    """(4) 手元に無い種別を、別の日付で代用しない(日付を 1 つも作らない)。"""
    t = pull()
    nothing = [p for p in t.pairs if p.result == "手元に無い"]
    assert len(nothing) == 7
    assert all(p.date == "" and p.label == "" for p in nothing)
    # R05(休業開始日)は手元に 1 行も無い。T02 だけは写せない表記があるので別の読み
    assert [p.result for p in t.pairs if p.rule_id == "R05"] == \
        ["手元に無い", "決まらない", "手元に無い", "手元に無い"]
    # 渡す日付は、手元の表にそのまま在る文字列だけ(作った日付が 1 つも無い)
    have = {r.date for r in B.Hand.load(FIX / "temoto_a.csv").items}
    assert {p.date for p in t.pairs if p.date} <= have
    print("[measure] 手元に無い 7 組はどれも渡す日付が空。渡した日付は 6 組とも"
          "手元の表にそのまま在る文字列で、作った日付は 0 件")


def test_measure_unmapped_label_blocks_the_missing_verdict() -> None:
    """写せない表記が残っている間は「手元に無い」と言い切らない。"""
    t = pull()
    assert pair_of(t, "R03", "T02").why == "宣言外の表記"
    assert pair_of(t, "R03", "T02").others == 1
    assert pair_of(t, "R03", "T04").result == "手元に無い"
    assert pair_of(t, "R03", "T04").others == 0
    print("[measure] 写せない表記が 1 行ある T02 は 決まらない(宣言外の表記)、"
          "写せない表記が 0 行の T04 は 手元に無い")


def test_measure_format_is_not_guessed() -> None:
    """書式を推測して読まない。宣言された書式に合わない日付は止まる。"""
    t = pull(t="K:temoto_shoshiki_gai")
    assert t.report.ok is False
    assert [p.reason for p in t.report.pending] == ["書式が宣言外"]
    assert "2026/04/01" in t.report.pending[0].detail
    assert t.pairs == ()
    assert B.fits("2026-04-01", "YYYY-MM-DD") is True
    assert B.fits("2026-04-31", "YYYY-MM-DD") is False
    assert B.fits("2026-04", "YYYY-MM-DD") is False
    print("[measure] 書式が宣言外の日付 1 件で止まる(1 組も読まない)。"
          "2026-04-31 も 2026-04 も YYYY-MM-DD では読まない")


def test_measure_stop_reason_codes_all_reachable(monkeypatch) -> None:
    """止まる理由コード 9 個すべてに道がある(崩した表 9 枚 + 差し替えた実装 2 本)。"""
    got: set[str] = set()
    cases = [("K:shubetsu_shutten_nashi", "youkyuu_a", "temoto_a"),
             ("shubetsu_a", "K:youkyuu_shutten_nashi", "temoto_a"),
             ("shubetsu_a", "youkyuu_a", "K:temoto_shutten_nashi"),
             ("shubetsu_a", "K:youkyuu_mitouroku", "temoto_a"),
             ("K:shubetsu_betsumei_juufuku", "youkyuu_a", "temoto_a"),
             ("K:shubetsu_id_juufuku", "youkyuu_a", "temoto_a"),
             ("shubetsu_a", "youkyuu_a", "K:temoto_shoshiki_gai"),
             ("K:shubetsu_joutai_gai", "youkyuu_a", "temoto_a"),
             ("shubetsu_a", "K:youkyuu_juufuku", "temoto_a")]
    for s, y, t in cases:
        table = pull(s, y, t)
        assert table.report.ok is False, (s, y, t)
        assert table.pairs == ()                 # 1 組も読まない
        got |= {p.reason for p in table.report.pending}
    assert len(cases) == 9
    # 残り 2 個は、実装を差し替えて 2 回目 / 入れ替えた 3 枚の出力を動かすと出る
    args = (B.Registry.load(FIX / "shubetsu_a.csv"),
            B.Demands.load(FIX / "youkyuu_a.csv"),
            B.Hand.load(FIX / "temoto_a.csv"))
    real = B.basis_map
    for n in (2, 3):
        calls = {"i": 0}

        def fake(registry, demands, hand, _n=n):
            calls["i"] += 1
            out = real(registry, demands, hand)
            if calls["i"] == _n:
                out = B.Table(report=out.report, pairs=out.pairs[:-1],
                              registry=out.registry, demands=out.demands,
                              hand=out.hand, read_at=out.read_at, host=out.host)
            return out

        monkeypatch.setattr(B, "basis_map", fake)
        out = B.verify(*args)
        got |= {p["reason"] for p in out["pending"]}
        monkeypatch.setattr(B, "basis_map", real)
    assert got == set(B.STOP_REASONS)
    assert len(B.STOP_REASONS) == 9
    print("[measure] 止まる理由コード 9 個すべてに道がある(崩した表 9 枚 +"
          " 差し替えた実装 2 本)")


def test_measure_read_error_count() -> None:
    """「表として読めない」で返る崩した表は 19 枚(理由コードには混ぜない)。"""
    n = 0
    for p in sorted((FIX / "kowashita").glob("*.csv")):
        loader = (B.Registry if p.name.startswith("shubetsu")
                  else B.Demands if p.name.startswith("youkyuu") else B.Hand)
        try:
            loader.load(p)
        except B.ReadError:
            n += 1
    assert n == 19
    assert len(list((FIX / "kowashita").glob("*.csv"))) == 28
    print("[measure] 「表として読めない」で返る崩した表 19 枚"
          "(崩した表 28 枚のうち。理由コードには混ぜない)")


def test_measure_duplicate_rule_id_breaks_the_denominator() -> None:
    """同じ rule id が 2 行あると、件数を rule 1 件ずつに割り当てられないので止まる。"""
    t = pull(y="K:youkyuu_juufuku")
    assert t.report.ok is False
    assert "件数の合計が合わない" in {p.reason for p in t.report.pending}
    assert t.counts()["要求表の行数"] == 6
    assert t.counts()["分母(rule 数 × 対象数)"] == 24
    assert t.counts()["4 値"] == dict.fromkeys(B.RESULTS, 0)
    print("[measure] 同じ rule id を 2 行書いた要求表 → 件数の合計が合わない で"
          "止まる(6 行 × 対象 4 = 24 のまま 1 組も読まない)")
    with pytest.raises(RuntimeError):
        t.judgement_bytes()


def test_measure_determinism() -> None:
    """2 回 + 3 枚の行順を入れ替えて読み直しても、判定部分の sha256 は同じ。"""
    shas = set()
    for _ in range(2):
        shas.add(pull().sha256())
    base = pull()
    swapped = B.basis_map(B.Registry.load(FIX / "shubetsu_a.csv").swapped("逆順"),
                          B.Demands.load(FIX / "youkyuu_a.csv").swapped("逆順"),
                          B.Hand.load(FIX / "temoto_a.csv").swapped("逆順"))
    shas.add(swapped.sha256())
    assert len(shas) == 1
    assert base.sha256()[:12] == "94a452a5ddb9"
    assert pull(s="shubetsu_touroku").sha256()[:12] == "13c33776b86e"
    body = base.judgement_bytes().decode("utf-8")
    for word in (base.read_at, base.host, "読んだ時刻", "ホスト名"):
        assert word not in body
    out = B.verify(B.Registry.load(FIX / "shubetsu_a.csv"),
                   B.Demands.load(FIX / "youkyuu_a.csv"),
                   B.Hand.load(FIX / "temoto_a.csv"))
    assert out["ok"] is True
    assert out["件数の検算"]["4 値の合計"] == out["件数の検算"]["分母(rule 数 × 対象数)"]
    print(f"[measure] 判定部分の sha256 先頭 12 桁 shubetsu_a {base.sha256()[:12]}"
          f" / 候補 → 登録済 {pull(s='shubetsu_touroku').sha256()[:12]}")
    print("[measure] 2 回 + 3 枚の行順を逆順に入れ替えて読み直し: 判定部分の sha256 は"
          " 3 回とも同じ(3/3 一致)")


def test_measure_inputs_are_not_modified() -> None:
    """読む前後で、入力ファイルの sha256 が 1 つも変わらない。"""
    before = {p: digest(p) for p in every_fixture()}
    assert len(before) == 33
    for s in ("shubetsu_a", "shubetsu_touroku", "shubetsu_betsumei_nashi"):
        pull(s=s)
    assert {p: digest(p) for p in every_fixture()} == before
    print("[measure] 読む前後で入力 33 ファイルの sha256 が同じ")


def test_measure_no_float_no_subprocess() -> None:
    """float も subprocess も os も random も使わない。datetime は書式の検査だけ。"""
    tree = ast.parse((ROOT / "basis_map.py").read_text(encoding="utf-8-sig"))
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split(".")[0])
    assert mods == {"__future__", "argparse", "csv", "datetime", "hashlib", "json",
                    "platform", "sys", "dataclasses", "pathlib"}
    assert len(mods) == 10
    code = code_only((ROOT / "basis_map.py").read_text(encoding="utf-8-sig"))
    assert "float" not in code
    for word in ("subprocess", "os.", "random"):
        assert word not in code, word
    # datetime を使うのは 2 か所。書式の検査と、判定部分に入れない読んだ時刻だけ
    assert code.count("datetime . datetime .") == 2
    print("[measure] 部品が import している module は 10 個で、subprocess / os /"
          " random / float は 0 件。datetime を使うのは 2 か所だけ")


def test_no_date_arithmetic_paths() -> None:
    """日付を作る / ずらす / 今日を使う引数も関数も 1 つも無い。"""
    code = code_only((ROOT / "basis_map.py").read_text(encoding="utf-8-sig"))
    for word in TSUKURU:
        assert word not in code, word


def test_no_adjective_words() -> None:
    """出力にも実装にも形容の語を持たせない(数値が無いなら多寡を書かない)。"""
    code = code_only((ROOT / "basis_map.py").read_text(encoding="utf-8-sig"))
    for word in KEIYOU:
        assert word not in code, word


def test_cli_has_only_four_subcommands(capsys) -> None:
    """CLI は map / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    assert B.SUBCOMMANDS == ("map", "check", "verify", "init")
    sub = next(a for a in B.build_parser()._actions
               if hasattr(a, "choices") and a.choices)
    assert sorted(sub.choices) == sorted(B.SUBCOMMANDS)
    for name, p in sub.choices.items():
        flags = {o for a in p._actions for o in a.option_strings}
        assert flags == {"-h", "--help"}, name
    assert B.main(["check", str(FIX / "shubetsu_a.csv"),
                   str(FIX / "youkyuu_a.csv"), str(FIX / "temoto_a.csv")]) == 3
    assert "20 組" in capsys.readouterr().out


def test_exit_codes() -> None:
    """決まらない行が 1 行も無いときだけ 0、止まれば 3、読めなければ 2。"""
    a = [str(FIX / "shubetsu_a.csv"), str(FIX / "youkyuu_a.csv"),
         str(FIX / "temoto_a.csv")]
    assert B.main(["check"] + a) == 3
    assert B.main(["verify"] + a) == 0
    assert B.main(["check", str(FIX / "kowashita" / "shubetsu_0gyou.csv"),
                   a[1], a[2]]) == 2


def test_init_writes_three_templates(tmp_path) -> None:
    """ひな型は 3 枚。書いたひな型はそのまま読める。"""
    paths = B.init(tmp_path / "ひな型")
    assert len(paths) == 3 and all(p.exists() for p in paths)
    t = B.basis_map(B.Registry.load(paths[0]), B.Demands.load(paths[1]),
                    B.Hand.load(paths[2]))
    assert t.report.ok is True
    assert t.counts()["分母(rule 数 × 対象数)"] == 4


def test_rate_is_not_returned_alone() -> None:
    """率だけを返す呼び方が無い。件数には必ず分母の内訳と検算と 3 つの固定行が付く。"""
    c = pull().counts()
    for key in ("分母に含めたもの", "件数の合計の検算", "似た表記を自分で寄せない",
                "手元に無い種別を代用しない", "日付を作らない・ずらさない・比べない"):
        assert c[key]
    assert not any("率" in k for k in c)
    code = code_only((ROOT / "basis_map.py").read_text(encoding="utf-8-sig"))
    assert "/ len (" not in code and "* 100" not in code
