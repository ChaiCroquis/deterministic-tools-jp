"""check_census の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 台帳の結果は 2 通りしかない。
  (a) 宣言表の行のひとつひとつがちょうど 1 つの判定(通った / 落ちた / 走らなかった / テストが無い)に
      入り、その合計が宣言の行数に等しく、走らなかった行とテストが無い行には終了コードが無く、通った行の
      終了コードは 0、落ちた行は 0 以外で、判定部分のバイト列に所要時間・時刻・ホスト名が 1 つも入らない
  (b) 判定は 1 件も返らず、理由コードが返る(台帳を取りに行くと例外になる)
どちらの場合も、この部品は宣言表もテストもコードも 1 文字も書き換えない。

宣言表は乱数で作る。行は 1〜2 行で、1 行ごとに 8 とおりの「在り方」(通る / 落ちる / timeout を超える /
runner が無い / 実行ファイルが無い / path が無い / 宣言の列が空欄 / テストが無い)から引く。さらに 3 割
くらいの確率で、宣言表そのものを 1 か所だけ崩す(runner を文字列にする / timeout を空にする / 出典を空に
する / 同じ name を 2 行にする)。derandomize=True で毎回同じ入力列を使い、database=None で見つけた例を
保存しない。

**期待する判定は道具の関数を使わず、テストの側で持っている。** 走らせる argv をテストが決めているので、
その行が通るはずか落ちるはずか走らないはずかはテストの側で分かる(run_row / census の判定を呼んで
突き合わせるのではなく、作った意図と突き合わせる)。
"""
from __future__ import annotations

import json
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
import check_census as C  # noqa: E402
import make_fixtures as M  # noqa: E402

PY = sys.executable
SOURCE = "合成(架空)"

# 在り方 -> (path, declared, argv(JSON か空), timeout, 期待する判定, 期待する理由コード, 期待する終了コード)
ARIKATA = {
    "通る": ("proj/tool_a", "在る", [PY, "-S", "-E", "-c", "raise SystemExit(0)"], "20",
               C.PASSED, "", 0),
    "落ちる": ("proj/tool_a", "在る", [PY, "-S", "-E", "-c", "raise SystemExit(3)"], "20",
                 C.FAILED, "", 3),
    "timeout を超える": ("proj/tool_a", "在る", [PY, "-S", "-E", "-c", "import time;time.sleep(3)"],
                             "1", C.NOT_RUN, "timeout", None),
    "runner が無い": ("proj/tool_a", "在る", None, "20", C.NOT_RUN, "runner が無い", None),
    "実行ファイルが無い": ("proj/tool_a", "不明", ["この実行ファイルは無い_check_census"], "20",
                               C.NOT_RUN, "runner が無い", None),
    "path が無い": ("proj/どこにも無い", "在る", [PY, "-S", "-E", "-c", "raise SystemExit(0)"], "20",
                       C.NOT_RUN, "path が無い", None),
    "宣言の列が空欄": ("", "在る", [PY, "-S", "-E", "-c", "raise SystemExit(0)"], "20",
                           C.NOT_RUN, "宣言の列が空欄", None),
    "テストが無い": ("proj/tool_a", "無い", None, "20", C.NO_TESTS, "", None),
}
KOWASHIKATA = ("runner を文字列にする", "timeout を空にする", "出典を空にする", "同じ name を 2 行にする")


@pytest.fixture(scope="session")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return M.build(tmp_path_factory.mktemp("census_property"), PY)


def write(dest: Path, kinds: list[str], kowasu: str | None) -> tuple[Path, bool]:
    """宣言表を書き、崩したか(= (b) を期待するか)を返す。"""
    body = []
    for i, kind in enumerate(kinds, 1):
        path, declared, argv, timeout, *_ = ARIKATA[kind]
        runner = "" if argv is None else json.dumps(argv, ensure_ascii=False)
        body.append([f"行{i}", path, declared, runner, timeout, "いいえ", "", SOURCE])
    if kowasu == "runner を文字列にする":
        body[0][3] = "python run_ok.py"
    elif kowasu == "timeout を空にする":
        body[0][4] = ""
    elif kowasu == "出典を空にする":
        body[0][7] = ""
    elif kowasu == "同じ name を 2 行にする":
        body.append(list(body[0]))
    p = dest / "sengen_property.csv"
    M.write_csv(p, M.HEADER, body)
    return p, kowasu is not None


@settings(max_examples=50, derandomize=True, database=None, deadline=None,
          suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
@given(kinds=st.lists(st.sampled_from(sorted(ARIKATA)), min_size=1, max_size=2),
       kowasu=st.sampled_from([None] * 6 + list(KOWASHIKATA)))
def test_いつも成り立つこと_台帳か理由コードか(built: Path, tmp_path: Path,
                                                      kinds: list[str], kowasu: str | None) -> None:
    before = {p: p.read_bytes() for p in sorted(built.rglob("*")) if p.is_file()}
    decl_path, broken = write(tmp_path, kinds, kowasu)
    decl = C.Declaration.load(decl_path)
    # path は宣言表のある場所からの相対パスなので、合成プロジェクトのある場所を base にして読み直す
    decl = C.Declaration(rows=decl.rows, base=built, pending=decl.pending)
    c = C.census(decl)

    if broken:
        event("(b) 止まった")
        assert c.report.ok is False
        assert c.results == ()
        assert {p.reason for p in c.report.pending} <= set(C.STOP_REASONS)
        assert c.report.pending
        for call in (c.table, c.rate, c.judgement_bytes):
            with pytest.raises(RuntimeError):
                call()
    else:
        event("(a) 台帳ができた")
        assert c.report.ok is True
        assert len(c.results) == len(kinds) == c.report.declared_rows
        assert sum(c.counts().values()) == c.report.declared_rows
        for kind, r in zip(kinds, c.results):
            *_, verdict, reason, code = ARIKATA[kind]
            assert (r.verdict, r.reason, r.exit_code) == (verdict, reason, code), kind
            if r.verdict in (C.NOT_RUN, C.NO_TESTS):
                assert r.exit_code is None and r.tail_sha256 == ""
            elif r.verdict == C.PASSED:
                assert r.exit_code == 0 and len(r.tail_sha256) == 64
            else:
                assert r.exit_code != 0 and len(r.tail_sha256) == 64
        raw = c.judgement_bytes().decode("utf-8")
        for key in ("所要秒", "始めた時刻", "ホスト名"):
            assert key not in raw
    after = {p: p.read_bytes() for p in sorted(built.rglob("*")) if p.is_file()}
    assert before == after


@st.composite
def 結果の列(draw: st.DrawFn) -> C.Census:
    """subprocess を使わずに作った台帳(分母の恒等式だけを見るため)。"""
    verdicts = draw(st.lists(st.sampled_from(C.VERDICTS), min_size=1, max_size=12))
    results = tuple(
        C.Result(name=f"行{i}", declared="在る" if v != C.NO_TESTS else "無い", verdict=v,
                 reason="runner が無い" if v == C.NOT_RUN else "",
                 exit_code=None if v in (C.NOT_RUN, C.NO_TESTS) else (0 if v == C.PASSED else 1),
                 tail_sha256="" if v in (C.NOT_RUN, C.NO_TESTS) else "0" * 64,
                 required=False, source=SOURCE, seconds="", started="", host="合成")
        for i, v in enumerate(verdicts, 1))
    return C.Census(C.Report(True, (), len(results)), results)


@settings(max_examples=300, derandomize=True, database=None)
@given(c=結果の列())
def test_狭い分母だけを引用すると必ず上振れする(c: C.Census) -> None:
    """合格率は、走らせた行だけを分母にすると宣言の行すべてを分母にした値を下回らない。"""
    counts, d = c.counts(), c.denominator()
    assert sum(counts.values()) == d["宣言の行数"]
    assert d["走らせた数"] + d["走らなかった数"] + d["テストが無い数"] == d["宣言の行数"]
    r = c.rate()
    wide = counts[C.PASSED] / d["宣言の行数"]
    assert r["合格率_宣言の行すべて"] == f"{wide:.4f}"
    if d["走らせた数"] == 0:
        assert r["合格率_走らせた行のみ"] == "分母が 0"
        assert counts[C.PASSED] == 0
    else:
        narrow = counts[C.PASSED] / d["走らせた数"]
        assert narrow >= wide                       # 狭い分母は下回らない
        assert r["合格率_走らせた行のみ"] == f"{narrow:.4f}"
    assert "分母に含めたもの" in r and "在ると数えた数は結果を 1 件も言わない" in r
