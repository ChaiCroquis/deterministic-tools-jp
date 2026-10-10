"""scope_ledger の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 台帳の結果は 2 通りしかない。
  (a) 宣言表の行のひとつひとつがちょうど 1 つの判定(宣言どおり / 一致しない / 宣言が無い /
      機械では読めない)に入り、その合計が宣言表の行数に等しく、宣言の欄が空の行は必ず「宣言が無い」、
      種類の欄が空で宣言がある行は必ず「機械では読めない」、「一致しない」の行には現れた行番号が
      1 つ以上あって他の 3 値には 1 つも無く、どの行にも出典が残り、判定部分のバイト列に
      時刻・ホスト名・絶対パスが 1 つも入らない
  (b) 判定は 1 件も返らず、理由コードが返る(台帳を取りに行くと例外になる)
どちらの場合も、この部品は対象のソースも宣言表も 1 文字も書き換えない。

宣言表は乱数で作る。行は 1〜3 行で、1 行ごとに 13 とおりの「在り方」(5 種 × 宣言どおり / 一致しない、
追えない形、構文解析できない、python でない、種類の欄が無い、宣言が無い)から引く。さらに 3 割くらいの
確率で、宣言表そのものを 1 か所だけ崩す(出典を空にする / パスを空にする / 種類を 5 種の外にする /
名指しを空にする / 同じ道具名と線の名前を 2 行にする)。derandomize=True で毎回同じ入力列を使い、
database=None で見つけた例を保存しない。

**期待する判定は部品の判定を呼ばずにテストの側で持っている**(合成の対象 script をテストが書いている
ので、その行が宣言どおりになるはずか一致しないはずかはテストの側で分かる)。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FIX))
import make_fixtures as M  # noqa: E402
import scope_ledger as S  # noqa: E402

SOURCE = "合成の宣言(架空)L1"
DECLARATION = "名指しの経路を持たない(合成の宣言)"

# 在り方 -> (kind, target, path, 期待する判定, 期待する理由コード)
ARIKATA = {
    "宣言どおり_import": ("import", "urllib", "src/net_ok.py", S.AS_DECLARED, ""),
    "一致しない_import": ("import", "urllib", "src/net_ng.py", S.MISMATCH, ""),
    "宣言どおり_kwarg": ("kwarg", "shell=True", "src/shell_ok.py", S.AS_DECLARED, ""),
    "一致しない_kwarg": ("kwarg", "shell=True", "src/shell_ng.py", S.MISMATCH, ""),
    "宣言どおり_write": ("write", "open", "src/write_ok.py", S.AS_DECLARED, ""),
    "一致しない_write": ("write", "open", "src/write_ng.py", S.MISMATCH, ""),
    "宣言どおり_option": ("option", "resolve:fallback", "src/opt_ok.py", S.AS_DECLARED, ""),
    "一致しない_option": ("option", "resolve:fallback", "src/opt_ng.py", S.MISMATCH, ""),
    "宣言どおり_call": ("call", "eval", "src/net_ok.py", S.AS_DECLARED, ""),
    "追えない形": ("call", "eval", "src/dyn_name.py", S.UNREADABLE, "名前が動的に組み立てられている"),
    "構文解析できない": ("import", "urllib", "src/kowareta.py", S.UNREADABLE, "構文解析できない"),
    "python でない": ("import", "urllib", "src/tsukurikake.txt", S.UNREADABLE, "対象が Python でない"),
    "種類の欄が無い": ("", "", "", S.UNREADABLE, "種類の欄が無い"),
    "宣言が無い": ("", "", "", S.NO_DECLARATION, ""),
}
KOWASHIKATA = ("出典を空にする", "パスを空にする", "種類を 5 種の外にする",
               "名指しを空にする", "同じ道具名と線の名前を 2 行にする")


@pytest.fixture(scope="session")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return M.build(tmp_path_factory.mktemp("scope_ledger_property"))


def write(dest: Path, built: Path, kinds: list[str], kowasu: str | None) -> tuple[Path, bool]:
    """宣言表を書き、崩したか(= (b) を期待するか)を返す。パスは合成の置き場を指す絶対パスにする。"""
    body: list[list[str]] = []
    for i, kind in enumerate(kinds, 1):
        k, target, path, *_ = ARIKATA[kind]
        declaration = "" if kind == "宣言が無い" else DECLARATION
        body.append([f"道具{i}", f"線{i}", declaration, SOURCE, k, target,
                     str(built / path) if path else ""])
    if kowasu == "出典を空にする":
        body[0][3] = ""
    elif kowasu == "パスを空にする":
        body[0][2], body[0][4], body[0][5], body[0][6] = DECLARATION, "import", "urllib", ""
    elif kowasu == "種類を 5 種の外にする":
        body[0][4] = "ast"
    elif kowasu == "名指しを空にする":
        body[0][2], body[0][4], body[0][5] = DECLARATION, "import", ""
        body[0][6] = str(built / "src/net_ok.py")
    elif kowasu == "同じ道具名と線の名前を 2 行にする":
        body.append(list(body[0]))
    p = dest / "sengen_property.csv"
    M.write_csv(p, M.HEADER, body)
    return p, kowasu is not None


@settings(max_examples=60, derandomize=True, database=None, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(kinds=st.lists(st.sampled_from(sorted(ARIKATA)), min_size=1, max_size=3),
       kowasu=st.sampled_from([None] * 10 + list(KOWASHIKATA)))
def test_いつも成り立つこと_台帳か理由コードか(built: Path, tmp_path: Path,
                                                      kinds: list[str], kowasu: str | None) -> None:
    before = {p: p.read_bytes() for p in sorted(built.rglob("*")) if p.is_file()}
    table, broken = write(tmp_path, built, kinds, kowasu)
    lg = S.ledger(S.Declaration.load(table))

    if broken:
        event("(b) 止まった")
        assert lg.report.ok is False
        assert lg.results == ()
        assert lg.report.pending
        assert {p.reason for p in lg.report.pending} <= set(S.STOP_REASONS)
        for call in (lg.table, lg.rate, lg.judgement_bytes, lg.read_conditions):
            with pytest.raises(RuntimeError):
                call()
    else:
        event("(a) 台帳ができた")
        assert lg.report.ok is True
        assert len(lg.results) == len(kinds) == lg.report.declared_rows
        assert sum(lg.counts().values()) == lg.report.declared_rows
        for kind, r in zip(kinds, lg.results):
            *_, verdict, reason = ARIKATA[kind]
            assert (r.verdict, r.reason) == (verdict, reason), kind
            assert r.source
            if r.verdict == S.MISMATCH:
                assert r.hits and all(n > 0 for n in r.hits)
            else:
                assert r.hits == ()
            if r.verdict == S.NO_DECLARATION:
                assert r.declaration == ""
            else:
                assert r.declaration
        raw = lg.judgement_bytes().decode("utf-8")
        for key in ("読んだ時刻", "ホスト名", "読んだ絶対パス", str(built)):
            assert key not in raw
    after = {p: p.read_bytes() for p in sorted(built.rglob("*")) if p.is_file()}
    assert before == after


@st.composite
def 判定の列(draw: st.DrawFn) -> S.Ledger:
    """ファイルを読まずに作った台帳(分母の恒等式だけを見るため)。"""
    verdicts = draw(st.lists(st.sampled_from(S.VERDICTS), min_size=1, max_size=12))
    results = tuple(
        S.Result(tool=f"道具{i}", line=f"線{i}", verdict=v,
                 reason=S.UNREADABLE_REASONS[0] if v == S.UNREADABLE else "",
                 hits=(3,) if v == S.MISMATCH else (),
                 declaration="" if v == S.NO_DECLARATION else DECLARATION,
                 source=SOURCE, kind="" if v in (S.NO_DECLARATION, S.UNREADABLE) else "import",
                 target="urllib", abs_path="", read_at="", host="合成")
        for i, v in enumerate(verdicts, 1))
    return S.Ledger(S.Report(True, (), len(results)), results)


@settings(max_examples=300, derandomize=True, database=None)
@given(lg=判定の列())
def test_狭い分母だけを引用すると必ず上振れする(lg: S.Ledger) -> None:
    """遵守率は、機械で読めた行だけを分母にすると宣言表の行すべてを分母にした値を下回らない。"""
    counts, d = lg.counts(), lg.denominator()
    assert sum(counts.values()) == d["宣言表の行数"]
    assert d["機械で読めた数"] + d["機械では読めなかった数"] + d["宣言が無い数"] == d["宣言表の行数"]
    r = lg.rate()
    wide = counts[S.AS_DECLARED] / d["宣言表の行数"]
    assert r["遵守率_宣言表の行すべて"] == f"{wide:.4f}"
    if d["機械で読めた数"] == 0:
        assert r["遵守率_機械で読めた行のみ"] == "分母が 0"
        assert counts[S.AS_DECLARED] == 0
    else:
        narrow = counts[S.AS_DECLARED] / d["機械で読めた数"]
        assert narrow >= wide                       # 狭い分母は下回らない
        assert r["遵守率_機械で読めた行のみ"] == f"{narrow:.4f}"
    assert "分母に含めたもの" in r and "機械では読めない行を宣言どおりに寄せていない" in r
