"""future_row のテスト。合成 fixture は `fixtures/` に commit 済(実データ・実在の値は入れない)。

test_measure_* が記事に載せた数値の出どころで、assert で固定している(値が変われば記事も変える前提)。
測っているものは 6 つある。

  (1) 行 10 × 基準日 3 = 30 組が 5 値に分かれ、基準日ごとの内訳と分母が付く側
  (2) 「次にいつ変わるか」が rule ごと・基準日ごとに 1 件以下で返る側
  (3) 効き始める日を知った日(公布日)で代用すると、基準日の答えに早すぎる行が混ざり、
      「次にいつ変わるか」の答えも減る側(= この記事の骨)
  (4) 空の効き始める日を年度初めで埋めると、まだ効き始めていない行が効いてしまう側
  (5) 前の行を閉じずに効き始める日を早めると、1 組も読まずに重なりで止まる側
  (6) 基準日を次に変わる日まで進めたときの突合(これから効き始める が減った分 =
      効き始めた側が増えた分)

(1) の 5 値は、テストの側でも 3 枚の表の行から直に組み立てて確かめている(部品の判定は呼ばず、
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
import future_row as F  # noqa: E402
import make_fixtures as M  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの -> その行に在るはずの語
REAL_SOURCES = {
    M.SRC_NURI: "塗り直した",
    M.SRC_NOKOSU: "1 行残り",
    M.SRC_UMENAI: "埋めない",
    M.SRC_SEIREI: "ゆだねられて",
    M.SRC_YOMIKAE: "読み替えず",
}

# 形容の語(出力にも実装にも持たせない = 数値が無いなら多寡を書かない)
KEIYOU = ("多い", "少ない", "ほとんど", "かなり", "著しく", "急いで")

# 空の効き始める日を埋める経路の名前(実装に 1 つも無いことを見る)
UMEKATA = ("年度初め", "次の月初", "推定", "見込み", "丸め", "fiscal", "fallback",
           "date.today", "utcnow", "timedelta", "公布日で引く")


def path_of(name: str) -> Path:
    p = FIX / "kowashita" / f"{name}.csv"
    return p if p.exists() else FIX / f"{name}.csv"


def pull(g: str = "gyou_a", s: str = "sengen_a", k: str = "kijunbi_a") -> F.Table:
    declared = F.Declared.load(path_of(s))
    return F.future_row(declared=declared, sheet=F.Sheet.load(path_of(g), declared),
                        asofs=F.Asofs.load(path_of(k)))


def pair_of(table: F.Table, row_id: str, asof_id: str) -> F.Pair:
    return next(p for p in table.pairs
                if p.row_id == row_id and p.asof_id == asof_id)


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


def expect_five(gyou: list[list[str]], kijunbi: list[list[str]],
                mark: str) -> dict[str, int]:
    """5 値を、2 枚の表の行から直に組み立てる(部品の判定には頼らない)。"""
    out = dict.fromkeys(F.RESULTS, 0)
    for row in gyou[1:]:
        vf, vt = row[3], row[4]
        for asof in kijunbi[1:]:
            day = asof[1]
            if vf == mark:
                out[F.STATES[3]] += 1
            elif vf > day:
                out[F.STATES[2]] += 1
            elif vt != mark and vt <= day:
                out[F.STATES[0]] += 1
            else:
                out[F.STATES[1]] += 1
    return out


def expect_next(gyou: list[list[str]], kijunbi: list[list[str]],
                mark: str) -> dict[tuple[str, str], str]:
    """「次にいつ変わるか」を、2 枚の表の行から直に組み立てる。"""
    out: dict[tuple[str, str], str] = {}
    for asof in kijunbi[1:]:
        day = asof[1]
        for row in gyou[1:]:
            rule, vf = row[1], row[3]
            if vf == mark or vf <= day:
                continue
            key = (rule, asof[0])
            if key not in out or vf < out[key]:
                out[key] = vf
    return out


# ---------------------------------------------------------------- 入り口

def test_committed_tables_load() -> None:
    """commit 済の表は、表として読める(止まる理由が 0 件)。"""
    declared = F.Declared.load(FIX / "sengen_a.csv")
    assert len(declared.items) == 5
    assert len(F.Sheet.load(FIX / "gyou_a.csv", declared).items) == 10
    assert len(F.Asofs.load(FIX / "kijunbi_a.csv").items) == 3
    assert F.Asofs.load(FIX / "kijunbi_a.csv").swap == "逆順"
    for name in ("gyou_a", "gyou_kouhyoubi", "gyou_kuuran_ume"):
        assert F.Sheet.load(FIX / f"{name}.csv", declared).pending == (), name
    assert declared.pending == ()
    assert F.Asofs.load(FIX / "kijunbi_a.csv").pending == ()
    # 空の効き始める日は宣言された記号で書かれ、読んだ後は「日付なし」として持たれる
    g07 = next(r for r in F.Sheet.load(FIX / "gyou_a.csv", declared).items
               if r.row_id == "G07")
    assert g07.undated is True and g07.valid_from == "" and g07.priority == ""


def test_sources_point_at_real_lines() -> None:
    """fixture の出典のうち 5 件は、この repo の実在の行を指している。"""
    for src, word in REAL_SOURCES.items():
        rel, line = src.rsplit(" L", 1)
        text = (PLAN / rel).read_text(encoding="utf-8-sig").splitlines()
        assert word in text[int(line) - 1], src


def test_fixtures_carry_no_values() -> None:
    """fixture に料率・金額が 1 つも入っていない(この部品は値の列を持たない)。"""
    for p in every_fixture():
        body = p.read_text(encoding="utf-8-sig")
        assert "%" not in body and "円" not in body, p.name
        rest = re.sub(r"articles/\S+?\.md", "", body)          # 出典の記事名
        rest = re.sub(r"\d{4}[-/]\d{2}[-/]\d{2}", "", rest)    # 日付
        rest = re.sub(r"2005 年 6 月 30 日", "", rest)          # 崩した表の日付
        rest = re.sub(r"[GRA]\d{2}", "", rest)                 # 行 / rule / 基準日 id
        rest = re.sub(r"L\d+", "", rest)                       # 出典の行番号
        assert not re.search(r"\d{2,}", rest), (p.name, rest[:80])


def test_row_table_has_no_value_column() -> None:
    """行の表に値の列が無い(値を返す経路を持てない、の物理形)。"""
    assert F.GYOU_COLUMNS == ("row_id", "rule_id", "known_from", "valid_from",
                              "valid_to", "seg", "priority", "announcer", "source")
    assert len(F.GYOU_COLUMNS) == 9
    assert not [c for c in F.GYOU_COLUMNS
                if c in ("value", "payload", "amount", "rate")]


# ---------------------------------------------------------------- 測ったもの

def test_measure_thirty_pairs_split_into_five() -> None:
    """(1) 行 10 × 基準日 3 = 30 組が 5 値に分かれ、基準日ごとの内訳と分母が付く。"""
    t = pull()
    c = t.counts()
    assert c["行の表の行数"] == 10
    assert c["状態の宣言の行数(rule 数)"] == 5
    assert c["基準日の数"] == 3
    assert c["分母(行数 × 基準日の数)"] == 30
    assert c["5 値"] == {"もう効き終わった": 7, "基準日に効いている": 13,
                         "これから効き始める": 7, "効き始める日が未定": 3,
                         "止まった": 0}
    assert c["基準日ごとの 5 値"]["A01"] == {"もう効き終わった": 1,
                                             "基準日に効いている": 4,
                                             "これから効き始める": 4,
                                             "効き始める日が未定": 1, "止まった": 0}
    assert c["基準日ごとの 5 値"]["A03"] == {"もう効き終わった": 4,
                                             "基準日に効いている": 5,
                                             "これから効き始める": 0,
                                             "効き始める日が未定": 1, "止まった": 0}
    # 5 値を、2 枚の表の行から別に組み立てても同じになる(部品の判定を呼ばない)
    assert c["5 値"] == expect_five(M.gyou_rows(), M.kijunbi_rows(), M.MARK)
    # 率の欄は無い。分母の内訳と検算は消せない
    assert not any("率" in k for k in c)
    assert "30 組" in str(c["分母に含めたもの"])
    assert "5 値の合計 30 / 分母 30" in str(c["件数の合計の検算"])
    print(f"[measure] gyou_a / sengen_a / kijunbi_a: 行 10 × 基準日 3 = 30 組"
          f" → 5 値 {c['5 値']}")
    print(f"[measure] 基準日ごとの内訳 A01 {c['基準日ごとの 5 値']['A01']}"
          f" / A03 {c['基準日ごとの 5 値']['A03']}"
          "(分母は 行数 × 基準日の数 = 30。率は単独では返らない)")


def test_measure_next_change_is_one_per_rule_and_asof() -> None:
    """(2) 「次にいつ変わるか」は rule ごと・基準日ごとに 1 件以下で、未定の行を混ぜない。"""
    t = pull()
    c = t.counts()
    assert c["次に変わる日の件数"] == 6
    assert c["基準日ごとの次に変わる日の件数"] == {"A01": 3, "A02": 3, "A03": 0}
    for n in c["基準日ごとの次に変わる日の件数"].values():
        assert n <= t.report.rules
    got = {(ch.rule_id, ch.asof_id): ch.day for ch in t.changes}
    assert got == expect_next(M.gyou_rows(), M.kijunbi_rows(), M.MARK)
    assert got[("R02", "A01")] == "2005-07-01"
    assert got[("R02", "A02")] == "2006-07-01"
    assert got[("R01", "A01")] == "2007-10-01"
    # 効き始める日が未定の行しか残っていない rule は「無い」で、日付を代用しない
    assert ("R03", "A01") not in got
    nai = [x for x in t.next_days() if x["次に変わる日"] == F.NAI]
    assert len(nai) == 9
    assert all(x["行 id"] == "" and x["出典"] == "" for x in nai)
    # 返した日付は、行の表にそのまま在る効き始める日だけ(作った日付は 0 件)
    have = {r.valid_from for r in t.sheet.items if not r.undated}
    assert {ch.day for ch in t.changes} <= have
    assert all(ch.source for ch in t.changes)
    print("[measure] 次に変わる日 6 件(基準日ごとに A01 3 / A02 3 / A03 0、"
          "どれも rule 数 5 以下)。残る 9 組は「無い」で、日付も行 id も空のまま")
    print("[measure] 段階施行の R02 は、基準日が 1 日進むと次に変わる日が"
          " 2005-07-01 → 2006-07-01 に入れ替わる(行をまとめずに別の行として数える)")


def test_measure_known_day_is_not_used_as_start() -> None:
    """(3) 効き始める日を知った日(公布日)で代用すると、答えに早すぎる行が混ざる。"""
    before, after = pull(), pull(g="gyou_kouhyoubi")
    # 元の表では、G08 は 2 つの基準日で「これから効き始める」のまま
    for asof in ("A01", "A02"):
        assert pair_of(before, "G08", asof).state == "これから効き始める"
    assert before.counts()["5 値"]["これから効き始める"] == 7
    assert after.counts()["5 値"] == {"もう効き終わった": 7, "基準日に効いている": 15,
                                      "これから効き始める": 5,
                                      "効き始める日が未定": 3, "止まった": 0}
    moved = [(p.row_id, p.asof_id) for p, q in zip(before.pairs, after.pairs)
             if p.state != q.state]
    assert moved == [("G08", "A01"), ("G08", "A02")]
    assert len([1 for p, q in zip(before.pairs, after.pairs)
                if p.state == q.state]) == 28
    # 同じ 1 欄で、「次にいつ変わるか」の答えも 2 件消える
    assert before.counts()["次に変わる日の件数"] == 6
    assert after.counts()["次に変わる日の件数"] == 4
    assert after.counts()["基準日ごとの次に変わる日の件数"] == {"A01": 2, "A02": 2,
                                                                "A03": 0}
    print("[measure] 効き始める日を知った日(公布日)で代用した表: 基準日に効いている"
          " 13 → 15、これから効き始める 7 → 5。動いたのは G08 の 2 組だけで、"
          "残る 28 組は変わらない")
    print("[measure] 同じ 1 欄で、次に変わる日は 6 → 4 件(R04 の答えが A01 / A02 で"
          "「無い」に変わる = 次の改定を答えられなくなる)")


def test_measure_blank_start_is_not_filled() -> None:
    """(4) 空の効き始める日を年度初めで埋めると、まだ効き始めていない行が効いてしまう。"""
    before, after = pull(), pull(g="gyou_kuuran_ume")
    for asof in ("A01", "A02", "A03"):
        assert pair_of(before, "G07", asof).state == "効き始める日が未定"
    assert before.counts()["5 値"]["効き始める日が未定"] == 3
    assert after.counts()["5 値"] == {"もう効き終わった": 7, "基準日に効いている": 16,
                                      "これから効き始める": 7,
                                      "効き始める日が未定": 0, "止まった": 0}
    moved = [(p.row_id, p.asof_id) for p, q in zip(before.pairs, after.pairs)
             if p.state != q.state]
    assert moved == [("G07", "A01"), ("G07", "A02"), ("G07", "A03")]
    # 未定の組には日付が付かない(予定の口に置くだけ)
    assert all(x["状態"] == "効き始める日が未定" for x in before.undated())
    assert len(before.undated()) == 3
    assert "年度初め" in str(before.counts()["空の効き始める日を埋めない"])
    print("[measure] 空の効き始める日を年度初め(2005-04-01)で埋めた表: 効き始める日が"
          "未定 3 → 0、基準日に効いている 13 → 16。3 組とも、まだ効き始めていない行が"
          "答えの口に入った")


def test_measure_unclosed_overlap_stops() -> None:
    """(5) 前の行を閉じずに効き始める日を早めると、1 組も読まずに止まる。"""
    t = pull(g="gyou_kasanari")
    assert t.report.ok is False
    assert t.pairs == () and t.changes == ()
    assert [p.reason for p in t.report.pending] == ["効いている期間の重なり"]
    assert "G03" in t.report.pending[0].detail
    assert "G04" in t.report.pending[0].detail
    assert t.counts()["5 値"] == dict.fromkeys(F.RESULTS, 0)
    assert "読んでいない" in str(t.counts()["読んだか"])
    for call in (t.judgement_bytes, t.sha256):
        with pytest.raises(RuntimeError):
            call()
    print("[measure] 前の行を閉じずに効き始める日を 2005-07-01 → 2004-06-01 に早めた表:"
          " 理由コード「効いている期間の重なり」で止まり、30 組とも読まない"
          "(5 値は全て 0、指紋を取りに行くと例外)")


def test_measure_shift_to_next_change_day() -> None:
    """(6) 基準日を次に変わる日まで進めると、減った分だけ効き始めた側が増える。"""
    declared = F.Declared.load(FIX / "sengen_a.csv")
    sheet = F.Sheet.load(FIX / "gyou_a.csv", declared)
    asofs = F.Asofs.load(FIX / "kijunbi_a.csv")
    out = F.verify(sheet, declared, asofs)
    assert out["ok"] is True
    shift = out["基準日を次に変わる日まで進めた突合"]
    assert shift["進めた基準日の数"] == 2
    rows = {x["基準日 id"]: x for x in shift["基準日ごと"]}
    assert rows["A03"]["進めた先"] == F.NAI
    assert rows["A01"]["進めた先"] == "2005-07-01"
    assert rows["A01"]["これから効き始める が減った分"] == 1
    assert rows["A01"]["基準日に効いている が増えた分"] == 0
    assert rows["A01"]["もう効き終わった が増えた分"] == 1
    assert rows["A02"]["進めた先"] == "2005-10-01"
    assert rows["A02"]["これから効き始める が減った分"] == 1
    assert rows["A02"]["基準日に効いている が増えた分"] == 1
    assert rows["A02"]["もう効き終わった が増えた分"] == 0
    assert all(x.get("合うか", True) for x in shift["基準日ごと"])
    print("[measure] 基準日を次に変わる日まで進めた突合: 3 件のうち 2 件で進めた"
          "(A03 は進める先が無い)。A02 → 2005-10-01 では これから効き始める が 1 減って"
          " 基準日に効いている が 1 増えた")
    print("[measure] A01 → 2005-07-01 では これから効き始める が 1 減ったが、"
          "基準日に効いている は増えず もう効き終わった が 1 増えた"
          "(その日は前の行が閉じる日でもある = 減った 1 と増えた 1 は合う)")


def test_measure_stop_reason_codes_all_reachable(monkeypatch) -> None:
    """止まる理由コード 11 個すべてに道がある(崩した表 10 枚 + 差し替えた実装 3 本)。"""
    got: set[str] = set()
    cases = [("gyou_shutten_nashi", "sengen_a", "kijunbi_a"),
             ("gyou_a", "sengen_shutten_nashi", "kijunbi_a"),
             ("gyou_a", "sengen_a", "kijunbi_shutten_nashi"),
             ("gyou_id_juufuku", "sengen_a", "kijunbi_a"),
             ("gyou_shitta_ato", "sengen_a", "kijunbi_a"),
             ("gyou_sakanobori", "sengen_a", "kijunbi_a"),
             ("gyou_owari_mae", "sengen_a", "kijunbi_a"),
             ("gyou_kigou_gai", "sengen_a", "kijunbi_a"),
             ("gyou_a", "sengen_juufuku", "kijunbi_a"),
             ("gyou_kasanari", "sengen_a", "kijunbi_a")]
    for g, s, k in cases:
        table = pull(g, s, k)
        assert table.report.ok is False, (g, s, k)
        assert table.pairs == ()                 # 1 組も読まない
        got |= {p.reason for p in table.report.pending}
    assert len(cases) == 10
    # 残り 3 個は、実装を差し替えて読んだ組を 1 つ落とすと出る
    declared = F.Declared.load(FIX / "sengen_a.csv")
    args = (F.Sheet.load(FIX / "gyou_a.csv", declared), declared,
            F.Asofs.load(FIX / "kijunbi_a.csv"))
    real = F.future_row
    for n in (1, 2, 3):
        calls = {"i": 0}

        def fake(sheet, declared, asofs, _n=n):
            calls["i"] += 1
            out = real(sheet, declared, asofs)
            if calls["i"] == _n:
                out = F.Table(report=out.report, pairs=out.pairs[:-1],
                              changes=out.changes, sheet=out.sheet,
                              declared=out.declared, asofs=out.asofs,
                              read_at=out.read_at, host=out.host)
            return out

        monkeypatch.setattr(F, "future_row", fake)
        out = F.verify(*args)
        assert out["ok"] is False
        got |= {p["reason"] for p in out["pending"]}
        monkeypatch.setattr(F, "future_row", real)
    assert got == set(F.STOP_REASONS)
    assert len(F.STOP_REASONS) == 11
    print("[measure] 止まる理由コード 11 個すべてに道がある(崩した表 9 枚 +"
          " 差し替えた実装 3 本)")


def test_measure_read_error_count() -> None:
    """「表として読めない」で返る崩した表は 33 枚(理由コードには混ぜない)。"""
    declared = F.Declared.load(FIX / "sengen_a.csv")
    n = 0
    for p in sorted((FIX / "kowashita").glob("*.csv")):
        try:
            if p.name.startswith("gyou"):
                F.Sheet.load(p, declared)
            elif p.name.startswith("sengen"):
                F.Declared.load(p)
            else:
                F.Asofs.load(p)
        except F.ReadError:
            n += 1
    assert n == 33
    assert len(list((FIX / "kowashita").glob("*.csv"))) == 42
    print("[measure] 「表として読めない」で返る崩した表 33 枚"
          "(崩した表 42 枚のうち。理由コードには混ぜない)")


def test_measure_determinism() -> None:
    """2 回 + 3 枚の行順を入れ替えて読み直しても、判定部分の sha256 は同じ。"""
    shas = {pull().sha256() for _ in range(2)}
    base = pull()
    declared = F.Declared.load(FIX / "sengen_a.csv")
    swapped = F.future_row(
        F.Sheet.load(FIX / "gyou_a.csv", declared).swapped("逆順"),
        declared.swapped("逆順"),
        F.Asofs.load(FIX / "kijunbi_a.csv").swapped("逆順"))
    shas.add(swapped.sha256())
    assert len(shas) == 1
    assert base.sha256()[:12] == "d5bce09169b9"
    assert pull(g="gyou_kouhyoubi").sha256()[:12] == "4f9b1e74779b"
    body = base.judgement_bytes().decode("utf-8")
    for word in (base.read_at, base.host, "読んだ時刻", "ホスト名"):
        assert word not in body
    assert str(FIX) not in body
    print(f"[measure] 判定部分の sha256 先頭 12 桁 gyou_a {base.sha256()[:12]}"
          f" / 公布日で代用した表 {pull(g='gyou_kouhyoubi').sha256()[:12]}")
    print("[measure] 2 回 + 3 枚の行順を逆順に入れ替えて読み直し: 判定部分の sha256 は"
          " 3 回とも同じ(3/3 一致)。判定部分に時刻・ホスト名・絶対パスは 0 件")


def test_measure_inputs_are_not_modified() -> None:
    """読む前後で、入力ファイルの sha256 が 1 つも変わらない。"""
    before = {p: digest(p) for p in every_fixture()}
    assert len(before) == 48
    for g in ("gyou_a", "gyou_kouhyoubi", "gyou_kuuran_ume", "gyou_kasanari"):
        pull(g=g)
    assert {p: digest(p) for p in every_fixture()} == before
    print("[measure] 読む前後で入力 48 ファイルの sha256 が同じ")


def test_measure_no_float_no_subprocess() -> None:
    """float も subprocess も os も random も使わない。"""
    tree = ast.parse((ROOT / "future_row.py").read_text(encoding="utf-8-sig"))
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split(".")[0])
    assert mods == {"__future__", "argparse", "csv", "datetime", "hashlib", "json",
                    "platform", "re", "sys", "dataclasses", "pathlib"}
    assert len(mods) == 11
    code = code_only((ROOT / "future_row.py").read_text(encoding="utf-8-sig"))
    assert "float" not in code
    for word in ("subprocess", "os.", "random"):
        assert word not in code, word
    print("[measure] 部品が import している module は 11 個で、subprocess / os /"
          " random / float は 0 件")


# ---------------------------------------------------------------- 無い経路

def test_no_filling_paths() -> None:
    """空の効き始める日を埋める引数も関数も 1 つも無い。"""
    code = code_only((ROOT / "future_row.py").read_text(encoding="utf-8-sig"))
    for word in UMEKATA:
        assert word not in code, word
    # 日付を比べるのは文字列の大小だけ(日付の足し算が無い)
    assert "datetime . date . fromisoformat" in code
    assert code.count("datetime . datetime . now") == 1   # 読んだ条件の欄だけ


def test_system_date_only_in_read_condition() -> None:
    """システムの日付と時刻は「読んだ条件」の欄にしか出てこない。"""
    t = pull()
    assert t.read_at in t.read_condition().values()
    assert t.host in t.read_condition().values()
    assert t.read_at not in str(t.counts())
    assert t.host not in str(t.counts())
    assert F.SCOPE_KEYS[3] == "読んだ時刻" and F.SCOPE_KEYS[4] == "ホスト名"


def test_answer_and_plan_are_separate_arrays() -> None:
    """答えの口と予定の口は別の配列で、1 つにまとめる関数が無い。"""
    t = pull()
    assert len(t.today()) == 13
    assert len(t.ahead()) == 7
    assert len(t.undated()) == 3
    assert len(t.closed()) == 7
    assert {x["状態"] for x in t.today()} == {"基準日に効いている"}
    assert {x["状態"] for x in t.ahead()} == {"これから効き始める"}
    assert {x["状態"] for x in t.undated()} == {"効き始める日が未定"}
    names = [n for n in dir(t) if not n.startswith("_")]
    assert not [n for n in names if "all" in n.lower() or "merge" in n.lower()]


def test_no_adjective_words() -> None:
    """出力にも実装にも形容の語を持たせない(数値が無いなら多寡を書かない)。"""
    code = code_only((ROOT / "future_row.py").read_text(encoding="utf-8-sig"))
    for word in KEIYOU:
        assert word not in code, word


def test_overlap_key_is_declared_three() -> None:
    """重なりを見る鍵は rule・対象・順位の 3 つだけ(次元の優先順位を内蔵しない)。"""
    declared = F.Declared.load(FIX / "sengen_a.csv")
    rows = F.Sheet.load(FIX / "gyou_a.csv", declared).items
    g06 = next(r for r in rows if r.row_id == "G06")
    assert g06.key == ("R03", (("次元A", "a3"),), "0")
    assert len(g06.key) == 3


def test_states_must_be_declared_by_name() -> None:
    """状態の名前が登録の 4 つと違う宣言は、理由コードでなく「表として読めない」で返る。"""
    with pytest.raises(F.ReadError):
        F.Declared.load(path_of("sengen_states_gai"))
    assert len(F.STATES) == 4
    assert len(F.RESULTS) == 5


def test_cli_has_only_five_subcommands(capsys) -> None:
    """CLI は split / next / check / verify / init の 5 つで、option は -h 以外に無い。"""
    assert F.SUBCOMMANDS == ("split", "next", "check", "verify", "init")
    sub = next(a for a in F.build_parser()._actions
               if hasattr(a, "choices") and a.choices)
    assert sorted(sub.choices) == sorted(F.SUBCOMMANDS)
    for name, p in sub.choices.items():
        flags = {o for a in p._actions for o in a.option_strings}
        assert flags == {"-h", "--help"}, name
    assert F.main(["check", str(FIX / "gyou_a.csv"), str(FIX / "sengen_a.csv"),
                   str(FIX / "kijunbi_a.csv")]) == 0
    assert "30 組" in capsys.readouterr().out


def test_exit_codes() -> None:
    """止まる理由が 1 件も無いときだけ 0、止まれば 3、読めなければ 2。"""
    a = [str(FIX / "gyou_a.csv"), str(FIX / "sengen_a.csv"),
         str(FIX / "kijunbi_a.csv")]
    assert F.main(["check"] + a) == 0
    assert F.main(["next"] + a) == 0
    assert F.main(["verify"] + a) == 0
    assert F.main(["check", str(FIX / "gyou_kasanari.csv"), a[1], a[2]]) == 3
    assert F.main(["check", str(FIX / "kowashita" / "gyou_0gyou.csv"),
                   a[1], a[2]]) == 2


def test_init_writes_three_templates(tmp_path) -> None:
    """ひな型は 3 枚。書いたひな型はそのまま読める。"""
    paths = F.init(tmp_path / "ひな型")
    assert len(paths) == 3 and all(p.exists() for p in paths)
    declared = F.Declared.load(paths[1])
    t = F.future_row(F.Sheet.load(paths[0], declared), declared,
                     F.Asofs.load(paths[2]))
    assert t.report.ok is True
    assert t.counts()["分母(行数 × 基準日の数)"] == 6
    assert t.counts()["5 値"]["効き始める日が未定"] == 2


def test_rate_is_not_returned_alone() -> None:
    """率だけを返す呼び方が無い。件数には必ず分母の内訳と検算と 6 つの固定行が付く。"""
    c = pull().counts()
    for key in ("分母に含めたもの", "件数の合計の検算", "空の効き始める日を埋めない",
                "知った日で引かない", "判定にシステム日付を使わない",
                "まだ効き始めていない行を答えに混ぜない", "段階施行を 1 行にまとめない",
                "値を返さない"):
        assert c[key]
    assert not any("率" in k for k in c)
    code = code_only((ROOT / "future_row.py").read_text(encoding="utf-8-sig"))
    assert "/ len (" not in code and "* 100" not in code
