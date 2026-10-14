"""span_split のテスト。合成 fixture は `fixtures/` に commit 済(実データ・実在の取引先名は入れない)。

test_measure_* が記事に載せた数値の出どころで、assert で固定している(値が変われば記事も変える前提)。
測っているものは 5 つある。

  (1) 宣言された境界日で期間が切れ、小期間ごとに行が 1 つ当たる側(kyoukai_a)
  (2) 当日の帰属を 1 行だけ 旧側 に変えると、切れ目が 1 日ずれて小期間の日数が入れ替わる側
      (kyoukai_b)= この記事の骨
  (3) 段階施行は複数の境界行として持つと 3 つの小期間になる側(kyoukai_c)
  (4) 公表時点が期間より後の境界は、宣言した扱いで切るか切らないかが分かれる側(kyoukai_e / f)
  (5) 「当たる行が決まらない」と「止まった」が混ざらない側(gyou_osoi / gyou_douten / 未定)

(2) の日数は、テストの側でも date の差で直に数えて確かめている(部品の split は呼ばない)。
"""
from __future__ import annotations

import ast
import datetime
import hashlib
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIX = ROOT / "fixtures"
PLAN = ROOT.parent.parent          # 07_記事化商品化計画(出典の行を開くため)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FIX))
import make_fixtures as M  # noqa: E402
import span_split as S  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの -> その行に在るはずの語
REAL_SOURCES = {
    M.SRC_TOUJITSU: "改元日当日は新元号",
    M.SRC_KAISHIBI: "開始日は改元日当日で",
    M.SRC_JUNI: "順位の列に書く",
    M.SRC_KOUHYOU: "いつ公表された知識か",
    M.SRC_KEIKA: "経過措置",
    M.SRC_KIRIKATA: "期間の切り方",
}


def spans(name: str) -> S.Spans:
    return S.Spans.load(FIX / f"{name}.csv")


def bounds(name: str) -> S.Boundaries:
    return S.Boundaries.load(FIX / f"{name}.csv")


def table(name: str) -> S.Rows:
    return S.Rows.load(FIX / f"{name}.csv")


def kowashita(name: str) -> Path:
    return FIX / "kowashita" / f"{name}.csv"


def cut(a: str = "kikan_a", b: str = "kyoukai_a", c: str = "gyou_a") -> S.Split:
    def path(n: str) -> Path:
        return kowashita(n[2:]) if n.startswith("K:") else FIX / f"{n}.csv"
    return S.split(S.Spans.load(path(a)), S.Boundaries.load(path(b)), S.Rows.load(path(c)))


def piece_days(m: S.Split, number: int) -> list[int]:
    return [p.days for c in m.cuts if c.span.number == number for p in c.pieces]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def every_fixture() -> list[Path]:
    return sorted(p for p in FIX.rglob("*.csv"))


# ---------------------------------------------------------------- 入り口

def test_committed_tables_load() -> None:
    """commit 済の 3 種の表は、表として読める(止まる理由が 0 件)。"""
    assert len(spans("kikan_a").items) == 5
    assert len(bounds("kyoukai_a").items) == 3 and bounds("kyoukai_a").swap == "逆順"
    assert len(table("gyou_a").items) == 5
    for name in ("kyoukai_a", "kyoukai_b", "kyoukai_c", "kyoukai_e", "kyoukai_f",
                 "kyoukai_step"):
        assert bounds(name).pending == (), name
    for name in ("gyou_a", "gyou_douten", "gyou_osoi"):
        assert table(name).pending == (), name
    assert len(bounds("kyoukai_d").undecided) == 1


def test_sources_point_at_real_lines() -> None:
    """出典のうち 6 件は、この repo 内の実在の行を指している。"""
    for src, word in REAL_SOURCES.items():
        rel, lineno = src.rsplit(" L", 1)
        line = (PLAN / rel).read_text(encoding="utf-8").splitlines()[int(lineno) - 1]
        assert word in line, f"{src} に {word} が無い: {line[:60]}"


def test_registered_vocabularies() -> None:
    """登録の語彙は固定(当日の帰属 2 / 公表時点の扱い 2 / 基準日の種別 6 / 4 値 4)。"""
    assert S.ONDAYS == ("新側", "旧側")
    assert S.KNOWN_USES == ("切る", "切らない")
    assert len(S.BASIS_KINDS) == 6
    assert len(S.RESULTS) == 4
    assert len(S.STOP_REASONS) == 12
    used = {s.basis for s in spans("kikan_a").items} | {s.basis for s in spans("kikan_b").items}
    assert used == {"対象月初日", "賃金締切日", "請求日"}


# ---------------------------------------------------------------- (1) 切れる側

def test_measure_declared_boundaries_cut() -> None:
    """宣言された境界日で 5 本のうち 4 本が切れ、9 つの小期間すべてに行が 1 つ当たる。"""
    m = cut()
    c = m.counts()
    assert m.report.ok and m.verdict == "境界で切れた"
    assert c["期間表の行数"] == 5 and c["境界表の行数"] == 3 and c["行の表の行数"] == 5
    assert c["4 値"] == {"境界で切れた": 4, "境界に当たらず 1 本のまま": 1,
                         "当たる行が決まらない": 0, "止まった": 0}
    assert c["小期間の件数"] == 9 and c["行が当たった小期間の件数"] == 9
    assert c["境界日が未定の行数"] == 0
    # 境界日が期間の開始日と同じ行は切れない(当日が新側なので、切れ目が期間の内側に来ない)
    assert piece_days(m, 3) == [183]
    print(f"[measure] kikan_a / kyoukai_a / gyou_a: 期間 {c['期間表の行数']} 本 /"
          f" 境界 {c['境界表の行数']} 行 / 行 {c['行の表の行数']} 行 →"
          f" 4 値 {c['4 値']} / 小期間 {c['小期間の件数']}")
    print(f"[measure] 行が当たった小期間 {c['行が当たった小期間の件数']} /"
          f" {c['小期間の件数']}。判定部分の sha256 先頭 12 桁 {m.sha256()[:12]}")


def test_measure_keika_row_wins_by_priority() -> None:
    """同じ有効開始日に 2 行当たったとき、順位 10 の経過措置の行が本則に勝つ。"""
    m = cut()
    honsoku = [p for c in m.cuts if c.span.target == M.TAISHOU_A for p in c.pieces
               if p.valid_from == datetime.date(2025, 4, 1)]
    keika = [p for c in m.cuts if c.span.target == M.TAISHOU_B for p in c.pieces
             if p.valid_from == datetime.date(2025, 4, 1)]
    assert len(honsoku) == 3 and {p.priority for p in honsoku} == {0}
    assert len(keika) == 1 and keika[0].priority == 10
    assert keika[0].value != honsoku[0].value
    assert keika[0].source == M.SRC_KEIKA
    print(f"[measure] 2025-04-01 に当たった小期間 {len(honsoku) + len(keika)} 件のうち、"
          f"経過措置の対象の 1 件だけ順位 {keika[0].priority} の行が当たり、"
          f"残る {len(honsoku)} 件は順位 0 の本則が当たった")


# ---------------------------------------------------------------- (2) 骨

def test_measure_onday_moves_the_cut_by_one_day() -> None:
    """当日の帰属を 1 行だけ 旧側 に変えると、切れ目が 1 日ずれて小期間の日数が入れ替わる。"""
    new, old = cut(b="kyoukai_a"), cut(b="kyoukai_b")
    assert new.counts()["4 値"]["境界で切れた"] == 4
    assert old.counts()["4 値"]["境界で切れた"] == 5
    assert new.counts()["小期間の件数"] == 9 and old.counts()["小期間の件数"] == 10
    assert piece_days(new, 2) == [90, 91] and piece_days(old, 2) == [91, 90]
    # 変えていない 2023-04-01 の境界をまたぐ期間は、どちらでも同じ切れ方になる
    assert piece_days(new, 6) == piece_days(old, 6) == [31, 61]
    # 境界日が開始日と同じ期間は、旧側 にすると 1 日の小期間ができる
    assert piece_days(old, 3) == [1, 182]
    # テストの側でも date の差で直に数える(部品の split は呼ばない)
    s, e = datetime.date(2025, 1, 1), datetime.date(2025, 6, 30)
    kyoukai = datetime.date(2025, 4, 1)
    assert [(kyoukai - s).days, (e - kyoukai).days + 1] == [90, 91]
    assert [(kyoukai - s).days + 1, (e - kyoukai).days] == [91, 90]
    assert new.sha256() != old.sha256()
    print(f"[measure] 当日の帰属 新側: 切れた期間 "
          f"{new.counts()['4 値']['境界で切れた']} 本 / 小期間 "
          f"{new.counts()['小期間の件数']} / 2025-01-01〜2025-06-30 は {piece_days(new, 2)} 日")
    print(f"[measure] 当日の帰属 旧側: 切れた期間 "
          f"{old.counts()['4 値']['境界で切れた']} 本 / 小期間 "
          f"{old.counts()['小期間の件数']} / 同じ期間は {piece_days(old, 2)} 日"
          f"(境界日当日がどちら側かだけで 1 日動く)")
    print(f"[measure] 判定部分の sha256 先頭 12 桁 新側 {new.sha256()[:12]} /"
          f" 旧側 {old.sha256()[:12]}")


def test_measure_days_always_sum_to_the_original() -> None:
    """どの切り方でも、小期間の日数の合計は元の期間の日数と一致する。"""
    total = {}
    for b in ("kyoukai_a", "kyoukai_b"):
        m = cut(b=b)
        for c in m.cuts:
            assert c.total_days == c.span.days, (b, c.span.target)
        total[b] = sum(c.span.days for c in m.cuts)
    assert total == {"kyoukai_a": 1094, "kyoukai_b": 1094}
    print(f"[measure] 期間 5 本の日数の合計 {total['kyoukai_a']} 日は、"
          f"新側 の小期間 9 つの合計とも、旧側 の小期間 10 つの合計とも一致"
          f"(切り落ちと重複が 0)")


# ---------------------------------------------------------------- (3) 段階施行

def test_measure_staged_boundaries_make_three_pieces() -> None:
    """段階施行を 2 つの境界行として持つと、1 本の期間が 3 つの小期間に割れる。"""
    m = cut(a="kikan_b", b="kyoukai_c")
    c = m.counts()
    assert m.report.ok and c["4 値"]["境界で切れた"] == 1 and c["小期間の件数"] == 3
    pieces = m.cuts[0].pieces
    assert [p.days for p in pieces] == [183, 183, 182]
    assert [p.step for p in pieces] == [None, 1, 2]
    assert sum(p.days for p in pieces) == m.cuts[0].span.days == 548
    print(f"[measure] kikan_b / kyoukai_c: 1 本の期間 {m.cuts[0].span.days} 日が"
          f" {c['小期間の件数']} つに割れ、日数は {[p.days for p in pieces]}、"
          f"段階の順は {[p.step for p in pieces]}(合計は元の期間と一致)")


# ---------------------------------------------------------------- (4) 公表時点

def test_measure_known_later_declaration_splits_the_result() -> None:
    """公表時点が期間より後の境界は、宣言した扱いだけで切るか切らないかが分かれる。"""
    nocut, docut = cut(a="kikan_c", b="kyoukai_e"), cut(a="kikan_c", b="kyoukai_f")
    assert nocut.counts()["4 値"]["境界に当たらず 1 本のまま"] == 1
    assert docut.counts()["4 値"]["境界で切れた"] == 1
    assert [p.days for p in nocut.cuts[0].pieces] == [273]
    assert [p.days for p in docut.cuts[0].pieces] == [182, 91]
    # どちらに寄せたかは必ず欄に残る(黙ってどちらかに寄せない)
    assert nocut.cuts[0].known_later == ((M.M_GOUSEI, "2026-07-10", "切らない"),)
    assert docut.cuts[0].known_later == ((M.M_GOUSEI, "2026-07-10", "切る"),)
    assert nocut.counts()["公表時点が期間より後だった境界の件数"] == 1
    print(f"[measure] kikan_c(273 日)の内側に、公表時点が期間の終わりより後の境界が 1 本。"
          f"宣言 切らない → 小期間 {[p.days for p in nocut.cuts[0].pieces]} /"
          f" 宣言 切る → 小期間 {[p.days for p in docut.cuts[0].pieces]}。"
          f"どちらに寄せたかは欄に残る")


# ---------------------------------------------------------------- (5) 決まらない / 止まった

def test_measure_undecided_boundary_stops_without_filling_the_date() -> None:
    """境界日が未定の行は、知識として読むが切るのには使わず、理由コードで止まる。"""
    m = cut(b="kyoukai_d")
    c = m.counts()
    assert m.report.ok is False
    assert [p.reason for p in m.report.pending] == [S.STOP_REASONS[2]]
    assert c["境界表の行数"] == 4 and c["境界日が未定の行数"] == 1
    assert c["4 値"] == dict.fromkeys(S.RESULTS, 0) and c["小期間の件数"] == 0
    with pytest.raises(RuntimeError):
        m.sha256()
    print(f"[measure] kyoukai_d: 境界表 {c['境界表の行数']} 行のうち"
          f" {c['境界日が未定の行数']} 行が未定 → 理由コード {m.report.pending[0].reason} で"
          f"止まり、決まっている 3 行での切り方も返さない(未定を今日の日付で埋めない)")


def test_measure_unresolved_row_is_not_a_stop() -> None:
    """行が当たらないのは 4 値の「当たる行が決まらない」で、理由コードでは止まらない。"""
    osoi = cut(c="gyou_osoi")
    assert osoi.report.ok is True and osoi.verdict == S.RESULTS[2]
    assert osoi.counts()["4 値"] == {"境界で切れた": 0, "境界に当たらず 1 本のまま": 1,
                                     "当たる行が決まらない": 4, "止まった": 0}
    assert osoi.counts()["行が当たった小期間の件数"] == 4
    assert osoi.counts()["小期間の件数"] == 9
    hits = {p.hit for c in osoi.cuts for p in c.pieces}
    assert hits == {S.HITS[0], S.HITS[1]}
    # 同じ日に 2 行、順位も段階の順も空 → こちらは理由コードで止まる
    douten = cut(c="gyou_douten")
    assert douten.report.ok is False
    assert {p.reason for p in douten.report.pending} == {S.STOP_REASONS[7]}
    # 段階の順が宣言されていれば、止まらずに「当たる行が決まらない」になる
    step = cut(b="kyoukai_step", c="gyou_douten")
    assert step.report.ok is True and step.verdict == S.RESULTS[2]
    assert step.counts()["4 値"]["当たる行が決まらない"] == 4
    print(f"[measure] gyou_osoi: 小期間 {osoi.counts()['小期間の件数']} のうち行が当たったのは"
          f" {osoi.counts()['行が当たった小期間の件数']} 件 → 4 値 {osoi.counts()['4 値']}"
          f"(止まった 0 件。決まらないことと止まることを混ぜない)")
    print(f"[measure] gyou_douten: 同じ日に 2 行で順位も段階の順も空 → 理由コード"
          f" {S.STOP_REASONS[7]}。段階の順を宣言した kyoukai_step では止まらず"
          f"「{S.RESULTS[2]}」が {step.counts()['4 値'][S.RESULTS[2]]} 件")


# ---------------------------------------------------------------- 持たせていないもの

def test_boundaries_are_never_inferred_from_the_rows() -> None:
    """行の表の有効開始日は境界にならない(境界表に書いた日だけで切る)。"""
    only_old = S.Boundaries.parse("\n".join(
        [",".join(S.KYOUKAI_COLUMNS),
         f"2020-09-01,{M.M_TOUKYUU},新側,,,,{M.SRC_NENKIN},逆順"]))
    m = S.split(spans("kikan_a"), only_old, table("gyou_a"))
    # 行の表には 2023-04-01 と 2025-04-01 の行が在るが、境界表に無いので切れ目にならない
    assert {r.valid_from for r in table("gyou_a").items} >= {datetime.date(2023, 4, 1),
                                                             datetime.date(2025, 4, 1)}
    assert m.counts()["4 値"]["境界で切れた"] == 0
    assert m.counts()["小期間の件数"] == len(spans("kikan_a").items) == 5


def test_no_money_and_no_tolerance_arguments() -> None:
    """按分・日割り・丸め・許容誤差の引数が 1 つも無い(CLI も関数も)。"""
    source = (ROOT / "span_split.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    names: set[str] = set()
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names |= {a.arg for a in fn.args.args + fn.args.kwonlyargs}
    for word in ("anbun", "hiwari", "round", "rounding", "tolerance", "atol", "rtol",
                 "denominator", "amount"):
        assert word not in names, word
    parser = S.build_parser()
    opts = {s for a in parser._actions for s in a.option_strings}
    assert opts == {"-h", "--help"}
    assert S.SUBCOMMANDS == ("split", "check", "verify", "init")


def test_no_float_no_subprocess_no_environment() -> None:
    """float も子プロセスも環境変数も使わない(日数は date の差の整数)。"""
    tree = ast.parse((ROOT / "span_split.py").read_text(encoding="utf-8"))
    mods: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split(".")[0])
        if isinstance(n, ast.Constant) and isinstance(n.value, float):
            raise AssertionError(f"float の定数がある: {n.value}")
        if isinstance(n, ast.Name) and n.id in ("float", "subprocess", "getenv"):
            raise AssertionError(f"使ってはいけない名前がある: {n.id}")
    assert "subprocess" not in mods and "os" not in mods and "random" not in mods
    assert mods == {"__future__", "argparse", "csv", "datetime", "hashlib", "json",
                    "platform", "sys", "dataclasses", "pathlib"}
    print(f"[measure] 部品が import している module は {len(mods)} 個で、"
          f"subprocess / os / random は 0 件")


def test_inputs_are_not_modified() -> None:
    """切る前と後で、入力の全 fixture の sha256 が変わらない(1 文字も書き換えない)。"""
    before = {p: digest(p) for p in every_fixture()}
    for a, b, c in (("kikan_a", "kyoukai_a", "gyou_a"), ("kikan_a", "kyoukai_b", "gyou_a"),
                    ("kikan_b", "kyoukai_c", "gyou_a"), ("kikan_c", "kyoukai_f", "gyou_a")):
        S.split(spans(a), bounds(b), table(c))
    after = {p: digest(p) for p in every_fixture()}
    assert before == after
    print(f"[measure] 切る前後で入力 {len(before)} ファイルの sha256 が同じ"
          f"(期間表 3 / 境界表 7 / 行の表 3 / 崩した表 "
          f"{len(list((FIX / 'kowashita').glob('*.csv')))})")


def test_judgement_has_no_time_path_or_host() -> None:
    """判定部分に時刻・絶対パス・ホスト名が入らない(sha256 の対象にもしない)。"""
    m = cut()
    body = m.judgement_bytes().decode("utf-8")
    assert m.read_at not in body and m.host not in body
    for key in S.READ_KEYS:
        assert key not in body
    assert str(FIX) not in body
    assert set(m.read_condition()) == set(S.READ_KEYS)


# ---------------------------------------------------------------- 理由コード 12 個

STOP_CASES = {
    S.STOP_REASONS[0]: ("kikan_a", "K:kyoukai_0gyou", "gyou_a"),
    S.STOP_REASONS[1]: ("kikan_a", "K:kyoukai_toujitsu_kuuran", "gyou_a"),
    S.STOP_REASONS[2]: ("kikan_a", "K:kyoukai_mitei", "gyou_a"),
    S.STOP_REASONS[3]: ("kikan_c", "K:kyoukai_koushu_mibun", "gyou_a"),
    S.STOP_REASONS[4]: ("kikan_a", "K:kyoukai_shutten_nashi", "gyou_a"),
    S.STOP_REASONS[5]: ("K:kikan_basis_mitouroku", "kyoukai_a", "gyou_a"),
    S.STOP_REASONS[6]: ("kikan_a", "K:kyoukai_juufuku", "gyou_a"),
    S.STOP_REASONS[7]: ("kikan_a", "kyoukai_a", "gyou_douten"),
    S.STOP_REASONS[8]: ("K:kikan_gyakusa", "kyoukai_a", "gyou_a"),
}


@pytest.mark.parametrize("reason", list(STOP_CASES))
def test_each_stop_reason_has_a_broken_table(reason: str) -> None:
    """崩した表 1 枚ごとに、狙った理由コードだけが返る(結果は 1 件も返らない)。"""
    m = cut(*STOP_CASES[reason])
    assert m.report.ok is False
    assert reason in {p.reason for p in m.report.pending}
    with pytest.raises(RuntimeError):
        m.judgement_bytes()


def test_source_empty_in_the_rows_also_stops() -> None:
    """出典の欄が空なのは、境界表でも行の表でも同じ理由コードで止まる。"""
    m = cut(c="K:gyou_shutten_nashi")
    assert m.report.ok is False
    assert {p.reason for p in m.report.pending} == {S.STOP_REASONS[4]}


def test_day_sum_mismatch_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    """日数の数え方を 1 日ずらした実装に差し替えると、切り落ちを自分で見つけて止まる。"""
    monkeypatch.setattr(S, "ONE_DAY", datetime.timedelta(days=2))
    m = cut()
    assert m.report.ok is False
    assert S.STOP_REASONS[9] in {p.reason for p in m.report.pending}


def test_verify_detects_a_second_run_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """2 回目だけ判定部分が変わる実装に差し替えると、verify がそれを拾う。"""
    original = S.Split.judgement_bytes
    seen: list[int] = []

    def flaky(self: S.Split) -> bytes:
        seen.append(1)
        body = original(self)
        return body + b"x" if len(seen) == 2 else body

    monkeypatch.setattr(S.Split, "judgement_bytes", flaky)
    out = S.verify(spans("kikan_a"), bounds("kyoukai_a"), table("gyou_a"))
    assert out["ok"] is False
    assert {p["reason"] for p in out["pending"]} == {S.STOP_REASONS[10]}


def test_verify_detects_boundary_order_dependence(monkeypatch: pytest.MonkeyPatch) -> None:
    """境界表の読み込み順に依存する実装に差し替えると、verify がそれを拾う。"""
    original = S.Split.judgement_bytes

    def ordered(self: S.Split) -> bytes:
        return original(self) + str(self.boundaries.items[0].number).encode("utf-8")

    monkeypatch.setattr(S.Split, "judgement_bytes", ordered)
    out = S.verify(spans("kikan_a"), bounds("kyoukai_a"), table("gyou_a"))
    assert out["ok"] is False
    assert {p["reason"] for p in out["pending"]} == {S.STOP_REASONS[11]}


def test_all_twelve_stop_reasons_are_covered() -> None:
    """理由コード 12 個のすべてに道がある(崩した表 9 枚 + 差し替えた実装 3 本)。"""
    covered = set(STOP_CASES) | {S.STOP_REASONS[9], S.STOP_REASONS[10], S.STOP_REASONS[11]}
    assert covered == set(S.STOP_REASONS)
    print(f"[measure] 止まる理由コード {len(S.STOP_REASONS)} 個すべてに道がある"
          f"(崩した表 {len(STOP_CASES)} 枚 + 差し替えた実装 3 本)")


# ---------------------------------------------------------------- 表として読めない側

READ_ERRORS = [
    ("kyoukai_retsu_nashi", "境界表"), ("kyoukai_toujitsu_mitouroku", "境界表"),
    ("kyoukai_koushu_mitouroku", "境界表"), ("kyoukai_koushu_nashi_ni_atsukai", "境界表"),
    ("kyoukai_swap_mitouroku", "境界表"), ("kyoukai_swap_futatsu", "境界表"),
    ("kyoukai_moved_kuuran", "境界表"), ("kyoukai_hizuke_yomenai", "境界表"),
    ("kyoukai_dankai_yomenai", "境界表"),
    ("kikan_taishou_kuuran", "期間表"), ("kikan_basis_kuuran", "期間表"),
    ("kikan_0gyou", "期間表"),
    ("gyou_atai_kuuran", "行の表"), ("gyou_0gyou", "行の表"),
]


@pytest.mark.parametrize("name,kind", READ_ERRORS)
def test_broken_tables_are_read_errors(name: str, kind: str) -> None:
    """語彙の外・列不足・読めない日付は、理由コードにせず「表として読めない」で返す。"""
    loader = {"境界表": S.Boundaries.load, "期間表": S.Spans.load, "行の表": S.Rows.load}[kind]
    with pytest.raises(S.ReadError):
        loader(kowashita(name))


def test_read_error_count() -> None:
    print(f"[measure] 「表として読めない」で返す崩した表 {len(READ_ERRORS)} 枚"
          f"(境界表 9 / 期間表 3 / 行の表 2)。理由コードには混ぜない")


# ---------------------------------------------------------------- verify

def test_measure_verify_is_deterministic() -> None:
    """2 回切っても、境界表の行順を入れ替えても、判定部分の sha256 は同じになる。"""
    out = S.verify(spans("kikan_a"), bounds("kyoukai_a"), table("gyou_a"))
    assert out["ok"] is True and out["入れ替え方"] == "逆順"
    assert out["sha256"] == out["2 回目の sha256"] == out["入れ替えた表の sha256"]
    assert len(out["日数の検算"]) == 5
    for row in out["日数の検算"]:
        assert row["元の期間の日数"] == row["小期間の日数の合計"]
    # 切れ方が違う表でも、切る手続きそのものは決定論
    other = S.verify(spans("kikan_a"), bounds("kyoukai_b"), table("gyou_a"))
    assert other["ok"] is True and other["sha256"] != out["sha256"]
    print(f"[measure] kyoukai_a を 2 回 + 境界表の行順を逆順に入れ替えて切り直し:"
          f" 判定部分の sha256 は 3 回とも同じ {out['sha256'][:12]}(3/3 一致)")
    print(f"[measure] 旧側 に変えた kyoukai_b でも 3 回とも同じ {other['sha256'][:12]}"
          f"(切れ方が変わることと、切る手続きが決定論であることは別)")


def test_verify_refuses_without_a_swap_declaration() -> None:
    """入れ替え方が宣言されていなければ verify は走らない(既定の並べ替えを持たない)。"""
    text = (FIX / "kyoukai_a.csv").read_text(encoding="utf-8").replace(",逆順", ",")
    with pytest.raises(S.ReadError):
        S.verify(spans("kikan_a"), S.Boundaries.parse(text), table("gyou_a"))


def test_verify_returns_the_reason_codes_when_stopped() -> None:
    """止まっている表では、verify も切った結果を返さない。"""
    out = S.verify(spans("kikan_a"), bounds("kyoukai_d"), table("gyou_a"))
    assert out["ok"] is False and out["stage"].startswith("止まった")
    assert "sha256" not in out


# ---------------------------------------------------------------- CLI

def exit_code(args: list[str]) -> int:
    return S.main(args)


def test_exit_codes(capsys: pytest.CaptureFixture[str]) -> None:
    """引けたら 0、決まらない / 止まったら 3、表として読めなければ 2。"""
    ok = [str(FIX / "kikan_a.csv"), str(FIX / "kyoukai_a.csv"), str(FIX / "gyou_a.csv")]
    assert exit_code(["split"] + ok) == 0
    assert exit_code(["check"] + ok) == 0
    assert exit_code(["verify"] + ok) == 0
    assert exit_code(["split", ok[0], str(FIX / "kyoukai_d.csv"), ok[2]]) == 3
    assert exit_code(["split", ok[0], ok[1], str(FIX / "gyou_osoi.csv")]) == 3
    assert exit_code(["split", ok[0], str(kowashita("kyoukai_moved_kuuran")), ok[2]]) == 2
    capsys.readouterr()


def test_init_writes_three_tables(tmp_path: Path) -> None:
    """ひな型は 3 枚で、そのまま切れる(止まらない)。"""
    kikan, kyoukai, gyou = S.init(tmp_path)
    assert kikan.exists() and kyoukai.exists() and gyou.exists()
    m = S.split(S.Spans.load(kikan), S.Boundaries.load(kyoukai), S.Rows.load(gyou))
    assert m.report.ok and m.verdict == S.RESULTS[0]


def test_counts_never_returns_a_bare_rate() -> None:
    """件数には必ず分母の内訳が付き、率を単独で返す鍵が無い。"""
    c = cut().counts()
    assert "率" not in "".join(k for k in c)
    for key in ("分母に含めたもの", "境界は宣言された日だけ", "日数の検算", "金額は触らない"):
        assert key in c and isinstance(c[key], str) and c[key]
    assert "按分" in c["金額は触らない"] and "推測して足す経路は無い" in c["境界は宣言された日だけ"]


# ---------------------------------------------------------------- fixture の決定論

def test_fixtures_are_regenerated_identically() -> None:
    """生成器の中身と、ディスク上の commit 済 CSV のバイト列が一致する。"""
    import csv as _csv
    import io

    def rendered(rows: list[list[str]]) -> bytes:
        buf = io.StringIO()
        _csv.writer(buf, lineterminator="\n").writerows(rows)
        return buf.getvalue().encode("utf-8")

    pairs = {
        "kikan_a": M.kikan(M.KIKAN_A), "kikan_b": M.kikan(M.KIKAN_B),
        "kikan_c": M.kikan(M.KIKAN_C), "kyoukai_a": M.kyoukai(M.KYOUKAI_A),
        "kyoukai_c": M.kyoukai(M.KYOUKAI_C), "kyoukai_e": M.kyoukai(M.KYOUKAI_E),
        "gyou_a": M.gyou(M.GYOU_A), "gyou_douten": M.gyou(M.GYOU_DOUTEN),
        "gyou_osoi": M.gyou(M.GYOU_OSOI),
    }
    for name, rows in pairs.items():
        assert (FIX / f"{name}.csv").read_bytes() == rendered(rows), name
