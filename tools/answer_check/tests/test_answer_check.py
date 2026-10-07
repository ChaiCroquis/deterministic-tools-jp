"""answer_check のテスト。fixture は全て合成データ(地域名・料率・限度額・出典名・文章は架空)。

test_measure_* が記事に載せた数値の出どころで、固定の fixture から決定論的に出る値を assert で
固定している(値が変われば記事も変える前提)。
"""
from __future__ import annotations

import builtins
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
import answer_check as A  # noqa: E402

KATA_TXT = FIX / "kata.txt"
KATA_CSV = FIX / "kata.csv"
SENGEN = FIX / "sengen.csv"
BUNSHOU = FIX / "bunshou.txt"

# 文章の文ごとに、何の「現れ方」を仕込んだか(図 2 の行)
ARAWAREKATA = {
    1: "同じ桁・単位で現れる",
    3: "丸めだけ違う",
    2: "単位が違う(‰ / 千円)",
    5: "単位が違う(‰ / 千円)",
    6: "全角や桁区切りで現れる",
    4: "前の版の値が出た",
    7: "塊にどの行も無い数値",
    8: "塊にどの行も無い数値",
    9: "単位の宣言が無い表記",
    10: "読めなかった表記",
    11: "読めなかった表記",
    12: "読めなかった表記",
}
ARAWAREKATA_ROWS = ("同じ桁・単位で現れる", "丸めだけ違う", "単位が違う(‰ / 千円)",
                    "全角や桁区切りで現れる", "前の版の値が出た", "塊にどの行も無い数値",
                    "単位の宣言が無い表記")


def decl(path: Path = SENGEN) -> A.Declaration:
    return A.Declaration.load(path)


def checked(pack: Path = KATA_TXT, body: Path = BUNSHOU, sengen: Path = SENGEN) -> A.Check:
    return A.check(A.load_pack(pack), decl(sengen), body.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- 入り口

def test_pack_text_and_csv_give_the_same_rows() -> None:
    assert A.load_pack(KATA_TXT) == A.load_pack(KATA_CSV)


def test_pack_text_and_csv_give_the_same_bytes() -> None:
    assert checked(KATA_TXT).sha256() == checked(KATA_CSV).sha256()


def test_pack_one_row_json_reads() -> None:
    rows = A.load_pack(FIX / "kata_1ken.json")
    assert len(rows) == 1 and rows[0]["payload"] == "9.70"


def test_pack_text_unknown_line_stops() -> None:
    with pytest.raises(A.DeclError, match="知らない行"):
        A.parse_pack_text("値: 9.70\n対象: 甲\n備考: なんでも\n")


def test_pack_text_note_must_agree_with_quality() -> None:
    first = KATA_TXT.read_text(encoding="utf-8").split("\n" * 2)[0]
    with pytest.raises(A.DeclError, match="仮置き"):
        A.parse_pack_text(first + "\n注記: 公表時点は仮置き(確定値ではない)\n")


def test_pack_unknown_column_stops() -> None:
    with pytest.raises(A.DeclError, match="知らない列"):
        A._check_pack_row({"selector": "甲", "単位": "%"}, 1)


def test_pack_bad_sha256_stops() -> None:
    row = dict(A.load_pack(KATA_CSV)[0])
    row["source_sha256"] = "abc"
    with pytest.raises(A.DeclError, match="64 桁"):
        A._check_pack_row(row, 1)


def test_decl_duplicate_alias_stops() -> None:
    with pytest.raises(A.DeclError, match="同じ alias"):
        A.Declaration.of([{"selector": "甲", "alias": "x", "unit": "%", "scale": "そのまま",
                           "period": "2026-06-01", "rounding": "しない"},
                          {"selector": "乙", "alias": "x", "unit": "%", "scale": "そのまま",
                           "period": "2026-06-01", "rounding": "しない"}])


def test_decl_unit_and_scale_must_pair() -> None:
    with pytest.raises(A.DeclError, match="unit と scale の数が違う"):
        A.Declaration.of([{"selector": "甲", "alias": "x", "unit": "%|‰", "scale": "そのまま",
                           "period": "2026-06-01", "rounding": "しない"}])


def test_decl_unknown_column_stops() -> None:
    with pytest.raises(A.DeclError, match="知らない欄"):
        A.Declaration.load(FIX / "kata.csv")


# ---------------------------------------------------------------- 取り出し

def test_numbers_are_exact_slices_of_the_text() -> None:
    """生の表記と位置が文章そのままであること(= 文章を書き換えていない)。"""
    body = BUNSHOU.read_text(encoding="utf-8")
    for f in A.find_numbers(body, decl()):
        assert body[f.start:f.start + len(f.text)] == f.text


def test_the_text_file_is_not_touched() -> None:
    before = BUNSHOU.read_bytes()
    checked()
    assert BUNSHOU.read_bytes() == before


def test_kanji_without_a_unit_is_not_a_number() -> None:
    """単位の付かない漢数字は数の表記として拾わない(「一致」「十分」など)。"""
    assert A.find_numbers("保険料率_甲は一致した。十分だ。", decl()) == []


def test_undeclared_unit_falls_to_incomparable() -> None:
    c = A.check(A.load_pack(KATA_TXT), decl(), "保険料率_甲は 9.70 ポイントだった。")
    assert [f["判定"] for f in c.table()] == [A.INCOMPARABLE]


def test_read_number_does_not_guess() -> None:
    assert A.read_number("１，１２０") is not None
    for bad in ("九・七", "9.70〜9.82", "3,57,000", "9.7.0", ""):
        assert A.read_number(bad) is None


# ---------------------------------------------------------------- 判定の規律

def test_pack_rows_are_never_rewritten() -> None:
    rows = A.load_pack(KATA_TXT)
    before = json.dumps(rows, ensure_ascii=False, sort_keys=True)
    A.check(rows, decl(), BUNSHOU.read_text(encoding="utf-8"))
    assert json.dumps(rows, ensure_ascii=False, sort_keys=True) == before


def test_the_original_files_are_never_opened(monkeypatch: pytest.MonkeyPatch) -> None:
    """塊の外へ値を取りに行かない(原本のファイルを 1 つも開かない)。"""
    pack, d, body = A.load_pack(KATA_TXT), decl(), BUNSHOU.read_text(encoding="utf-8")
    opened: list = []
    real_open = builtins.open

    def watching(file, *args, **kw):   # noqa: ANN001
        opened.append(str(file))
        return real_open(file, *args, **kw)

    monkeypatch.setattr(builtins, "open", watching)
    A.check(pack, d, body).table()
    assert opened == []


def test_no_tolerance_and_no_authoritative_side() -> None:
    """許容誤差 / 正とする側 / 訂正文 に相当する名前が、コードのどこにも無い。"""
    import ast
    tree = ast.parse((ROOT / "answer_check.py").read_text(encoding="utf-8"))
    names: set = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.arg):
            names.add(n.arg)
        elif isinstance(n, ast.Name):
            names.add(n.id)
        elif isinstance(n, ast.Attribute):
            names.add(n.attr)
        elif isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            names.add(n.name)
    forbidden = {"tolerance", "atol", "rtol", "epsilon", "margin", "prefer", "preferred",
                 "authoritative", "fallback", "correction", "rewrite", "summarize", "truncate",
                 "fix", "suggest", "refetch"}
    assert names & forbidden == set(), sorted(names & forbidden)


def test_the_cli_has_only_one_option() -> None:
    src = (ROOT / "answer_check.py").read_text(encoding="utf-8")
    assert set(re.findall(r'add_argument\("(--[a-z-]+)"', src)) == {"--decl"}


def test_counts_cannot_be_read_before_the_run() -> None:
    c = A.Check(A.load_pack(KATA_TXT), decl(), BUNSHOU.read_text(encoding="utf-8"))
    for call in (c.counts, c.table, c.rate, c.denominator):
        with pytest.raises(A.CheckError):
            call()


def test_rate_always_carries_the_four_counts_and_the_denominator() -> None:
    r = checked().rate()
    for key in (*A.VERDICTS, "文章から取り出せた数値", "取り出せなかった表記",
                "見つけた表記の総数", "比べられた数値", "分母に含めたもの"):
        assert key in r
    assert "接地率_比べられた数値のみ" in r and "接地率_取り出せた数値すべて" in r


def test_the_narrow_denominator_never_reads_lower() -> None:
    r = checked().rate()
    assert float(r["接地率_比べられた数値のみ"]) >= float(r["接地率_取り出せた数値すべて"])


def test_four_verdicts_add_up_to_the_numbers_read() -> None:
    c = checked()
    assert sum(c.counts().values()) == c.denominator()["文章から取り出せた数値"]
    assert (c.denominator()["見つけた表記の総数"]
            == c.denominator()["文章から取り出せた数値"] + c.denominator()["取り出せなかった表記"])


def test_the_fixture_sha256_is_the_real_fingerprint() -> None:
    import hashlib
    real = hashlib.sha256((FIX / "moto_ryouritsu.csv").read_bytes()).hexdigest()
    assert A.load_pack(KATA_TXT)[0]["source_sha256"] == real


def test_changing_the_original_by_one_character_changes_the_hash(tmp_path: Path) -> None:
    import hashlib
    original = (FIX / "moto_ryouritsu.csv").read_text(encoding="utf-8")
    changed = tmp_path / "moto_ryouritsu.csv"
    changed.write_text(original.replace("9.70", "9.71"), encoding="utf-8")
    assert (hashlib.sha256(changed.read_bytes()).hexdigest()
            != A.load_pack(KATA_TXT)[0]["source_sha256"])


# ---------------------------------------------------------------- 止まる

STOPS = (
    ("kata_shutten_nashi.csv", "sengen.csv", "bunshou.txt", "塊に出典が無い", A.PACK),
    ("kata_sha_nashi.csv", "sengen.csv", "bunshou.txt", "塊に sha256 が無い", A.PACK),
    ("kata_kikan_nashi.csv", "sengen.csv", "bunshou.txt", "塊に有効期間が無い", A.PACK),
    ("kata_kouhyou_nashi.csv", "sengen.csv", "bunshou.txt", "塊に公表時点が無い", A.PACK),
    ("kata_nijuu.csv", "sengen.csv", "bunshou.txt", "同じ selector の行が 2 件以上", A.PACK),
    ("kata.txt", "sengen_tani_nashi.csv", "bunshou.txt", "単位の宣言が無い列を要求", A.DECL),
    ("kata.txt", "sengen_shiranai_seikika.csv", "bunshou.txt", "宣言に無い正規化を要求", A.DECL),
    ("kata.txt", "sengen.csv", "bunshou_kara.txt", "文章が空", A.TEXT),
    ("kata_kikangai.csv", "sengen.csv", "bunshou.txt",
     "塊の有効期間が照合の基準日を含まない", A.JUDGE),
)


@pytest.mark.parametrize("pack,sengen,body,reason,stage", STOPS)
def test_stops_with_the_reason_code(pack: str, sengen: str, body: str, reason: str,
                                   stage: str) -> None:
    c = checked(FIX / pack, FIX / body, FIX / sengen)
    assert not c.report.ok and c.report.stage == stage
    assert reason in c.report.reasons()
    with pytest.raises(A.CheckError):
        c.counts()


def test_the_second_round_mismatch_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    """同じ入力から 2 回判定してバイト列が違う経路が、本当に止まるか。"""
    calls = {"n": 0}
    original = A.Check.as_dict

    def wobbly(self: A.Check) -> dict:
        calls["n"] += 1
        return {**original(self), "ゆらぎ": calls["n"]}

    monkeypatch.setattr(A.Check, "as_dict", wobbly)
    out = A.verify(A.load_pack(KATA_TXT), decl(), BUNSHOU.read_text(encoding="utf-8"))
    assert out["ok"] is False
    assert out["pending"][0]["reason"] == "2 回目の判定でバイト列が不一致"


def test_every_reason_code_has_a_path() -> None:
    reached = {reason for _, _, _, reason, _ in STOPS} | {"2 回目の判定でバイト列が不一致"}
    assert reached == set(A.REASONS)


# ---------------------------------------------------------------- CLI

def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "answer_check.py"), *args],
                          capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT))


def test_cli_check_returns_3_when_something_is_not_grounded() -> None:
    r = _run("check", str(KATA_TXT), str(BUNSHOU), "--decl", str(SENGEN))
    assert r.returncode == 3
    assert json.loads(r.stdout)["接地"] == 5


def test_cli_check_returns_0_when_everything_is_grounded(tmp_path: Path) -> None:
    body = tmp_path / "zenbu.txt"
    body.write_text("保険料率_甲は 9.70% だった。\n限度額_丁は 357 千円だった。\n",
                    encoding="utf-8")
    r = _run("check", str(KATA_TXT), str(body), "--decl", str(SENGEN))
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads(r.stdout)["接地"] == 2


def test_cli_verify_and_init(tmp_path: Path) -> None:
    r = _run("verify", str(KATA_TXT), str(BUNSHOU), "--decl", str(SENGEN))
    assert r.returncode == 0 and json.loads(r.stdout)["一致"] is True
    out = tmp_path / "sengen.csv"
    assert _run("init", str(out)).returncode == 0
    assert A.Declaration.load(out).targets
    assert _run("init", str(out)).returncode == 2   # 上書きしない


def test_cli_reads_the_text_from_stdin() -> None:
    r = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "answer_check.py"), "check",
                        str(KATA_TXT), "-", "--decl", str(SENGEN)],
                       input="保険料率_甲は 9.80% だった。\n", capture_output=True, text=True,
                       encoding="utf-8", cwd=str(ROOT))
    assert r.returncode == 3 and json.loads(r.stdout)["食い違い"] == 1


# ---------------------------------------------------------------- 測定(記事の数値)

def test_measure_verdicts(capsys: pytest.CaptureFixture) -> None:
    c = checked()
    counts, d = c.counts(), c.denominator()
    assert c.report.packs == 4
    assert counts == {"接地": 5, "食い違い": 1, "塊に無い": 2, "比べられない": 1}
    assert d == {"文章から取り出せた数値": 9, "取り出せなかった表記": 3,
                 "見つけた表記の総数": 12, "比べられた数値": 6}
    with capsys.disabled():
        print(f"\n[measure] 塊 {c.report.packs} 件と文章 12 文を突き合わせる:"
              f" 見つけた表記 {d['見つけた表記の総数']} / 取り出せた {d['文章から取り出せた数値']}"
              f" / 取り出せなかった {d['取り出せなかった表記']}")
        print(f"[measure] 4 値: 接地 {counts['接地']} / 食い違い {counts['食い違い']}"
              f" / 塊に無い {counts['塊に無い']} / 比べられない {counts['比べられない']}")


def test_measure_rate(capsys: pytest.CaptureFixture) -> None:
    r = checked().rate()
    assert r["接地率_比べられた数値のみ"] == "0.8333"
    assert r["接地率_取り出せた数値すべて"] == "0.5556"
    with capsys.disabled():
        print(f"[measure] 接地率: 比べられた数値のみ(分母 6)= "
              f"{r['接地率_比べられた数値のみ']} / 取り出せた数値すべて(分母 9)= "
              f"{r['接地率_取り出せた数値すべて']}")


def test_measure_arawarekata(capsys: pytest.CaptureFixture) -> None:
    """図 2 の各セルの件数(現れ方 × 4 値)。"""
    c = checked()
    grid: dict = {row: {v: 0 for v in A.VERDICTS} for row in ARAWAREKATA_ROWS}
    unreadable: dict = {}
    for f in c.found:
        row = ARAWAREKATA[f.sentence]
        if not f.readable:
            unreadable[row] = unreadable.get(row, 0) + 1
            continue
        grid[row][f.verdict] += 1
    assert grid["同じ桁・単位で現れる"] == {"接地": 1, "食い違い": 0, "塊に無い": 0,
                                               "比べられない": 0}
    assert grid["丸めだけ違う"]["接地"] == 1
    assert grid["単位が違う(‰ / 千円)"]["接地"] == 2
    assert grid["全角や桁区切りで現れる"]["接地"] == 1
    assert grid["前の版の値が出た"] == {"接地": 0, "食い違い": 1, "塊に無い": 0,
                                               "比べられない": 0}
    assert grid["塊にどの行も無い数値"]["塊に無い"] == 2
    assert grid["単位の宣言が無い表記"]["比べられない"] == 1
    assert sum(sum(v.values()) for v in grid.values()) == 9
    assert unreadable == {"読めなかった表記": 3}
    with capsys.disabled():
        for row in ARAWAREKATA_ROWS:
            got = {k: v for k, v in grid[row].items() if v}
            print(f"[measure] {row}: {got}")
        print(f"[measure] 読めなかった表記: {unreadable['読めなかった表記']} 件"
              f"(漢数字 / 範囲 / 桁区切りが 3 桁でない)")


def test_measure_table_is_the_only_thing_returned(capsys: pytest.CaptureFixture) -> None:
    rows = checked().table()
    assert len(rows) == 12
    grounded = [r for r in rows if r.get("判定") == A.GROUNDED]
    assert all(r["塊の行"] and r["塊の値"] for r in grounded)
    assert all(set(r) <= {"表記", "文", "単位", "読めた", "対象", "判定", "正規化",
                          "塊の行", "塊の値", "なぜ"} for r in rows)
    with capsys.disabled():
        print(f"[measure] 対応表は {len(rows)} 行で、欄は表記 / 文 / 単位 / 読めた / 対象 /"
              f" 判定 / 正規化 / 塊の行 / 塊の値 / なぜ だけ(訂正文の欄は無い)")


def test_measure_verify(capsys: pytest.CaptureFixture) -> None:
    out = A.verify(A.load_pack(KATA_TXT), decl(), BUNSHOU.read_text(encoding="utf-8"))
    assert out["ok"] is True and out["一致"] is True and out["判定した回数"] == 2
    assert out["sha256"] == out["2 回目の sha256"]
    same = checked(KATA_CSV).sha256()
    assert same == out["sha256"]
    with capsys.disabled():
        print(f"[measure] 同じ入力から 2 回判定: sha256 が一致(先頭 12 桁 {out['sha256'][:12]})。"
              f"入り口が塊の text でも CSV でも同じバイト列")


def test_measure_stops(capsys: pytest.CaptureFixture) -> None:
    lines = []
    for pack, sengen, body, reason, stage in STOPS:
        c = checked(FIX / pack, FIX / body, FIX / sengen)
        assert c.report.reasons()[0] == reason
        lines.append(f"[measure] 止まった({stage}の段): {reason}")
    assert len(lines) == 9
    with capsys.disabled():
        for line in lines:
            print(line)
        print("[measure] 残る 1 つ(2 回目の判定でバイト列が不一致)は"
              "判定を 1 か所差し替えて経路を確かめた = 理由コード 10 個すべてに道がある")


def test_measure_dates_are_picked_up_too(capsys: pytest.CaptureFixture) -> None:
    c = checked(KATA_TXT, FIX / "bunshou_hizuke.txt")
    assert c.counts() == {"接地": 1, "食い違い": 0, "塊に無い": 0, "比べられない": 3}
    with capsys.disabled():
        print("[measure] 暦の日付を含む 1 文: 表記 4 件のうち 接地 1 / 比べられない 3"
              "(年・月・日も数の表記として拾い、単位が無いので比べられないに落ちる)")
