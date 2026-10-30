"""run_kinds のテスト。合成 fixture は `fixtures/` に commit 済(実データ・実在の値は入れない)。

test_measure_* が記事に載せた数値の出どころで、assert で固定している(値が変われば記事も変える前提)。
測っているものは 7 つある。

  (1) 実行 17 回 が 6 値 + 別枠 2 種に分かれ、3 つの分母の内訳が付く側
  (2) **通ったと宣言された 11 回 が、初回 1・差分 0 で指紋も同じ 3・入れ替わった 5・
      噛み合わない 2 に分かれる**という側
  (3) **落ちたと宣言された 5 回 が、事前に試験と宣言された 2・事前の宣言が無い 2・
      落ちたのに指紋が動いた 1 に分かれる**という側。= 記事の骨
  (4) ② の 2 回が、言い方の違い(宣言が実行より後 / 宣言そのものが無い)のまま一覧に出る側
  (5) 指紋が履歴の前の回の値へ戻った回が 1 回で、⑥ の形が 2 通りで返る側
  (6) 試験の宣言を 1 件外すと、その回だけが ① から ② へ動く側
  (7) ④ の回の指紋を書き換えると、その回だけが ④ から ⑥ へ動き、戻りの印が付かない側

(1) の 8 値は、テストの側でも 3 枚の表の行から直に組み立てて確かめている(部品の judge /
six を呼ばず、fixture の行から別に分類する)。
"""
from __future__ import annotations

import ast
import hashlib
import io
import json
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
import run_kinds as H  # noqa: E402
import make_fixtures as M  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの -> その行に在るはずの語
REAL_SOURCES = {
    M.SRC_LEDGER: "台帳",
    M.SRC_CENSUS: "走らなかった",
}

# 良し悪しを指す語(件数の側に持たせない = 型 S1 の forbidden の物理形)
KINSOKU = ("障害", "異常", "事故", "健全", "劣化", "違反", "要注意")

# 形容の語(数値が無いなら多寡を書かない)
KEIYOU = ("多い", "少ない", "ほとんど", "かなり", "著しく", "ざっと")

# 持たせていない経路の名前(動く側のコードに 1 つも無いことを見る)
MOTANAI = ("eval", "exec", "round(", "float(", "now(", "today(", "time(",
           "subprocess", "random", "platform", "datetime", "urllib", "requests",
           "socket", "difflib", "SequenceMatcher")

OK, FAILED = M.OK, M.FAILED


def path_of(name: str) -> Path:
    return FIX / "kowashita" / f"{name}.csv" \
        if name not in ("runs_a", "intents_a", "words_a") else FIX / f"{name}.csv"


def pull(d: str = "runs_a", i: str = "intents_a", w: str = "words_a") -> H.Tally:
    return H.run_kinds(H.Runs.load(path_of(d)), H.Intents.load(path_of(i)),
                       H.Words.load(path_of(w)))


def three() -> tuple[H.Runs, H.Intents, H.Words]:
    return (H.Runs.load(path_of("runs_a")), H.Intents.load(path_of("intents_a")),
            H.Words.load(path_of("words_a")))


def reasons_of(t: H.Tally) -> set[str]:
    return {p.reason for p in t.report.pending}


def judged_of(t: H.Tally, run_id: str) -> H.Judged:
    return next(j for j in t.judged if j.run.run_id == run_id)


# ---------------------------------------------------------------- 別実装(テスト側)

def expect_eight() -> dict[str, int]:
    """3 枚の行から 8 値を別に数える(部品の judge / six / counts を呼ばない)。"""
    words = {row[0]: (row[1], row[2]) for row in M.words_rows()}
    intents = {row[0]: (row[1], row[2]) for row in M.intents_rows()}
    eight = {k: 0 for k in H.KEKKA}
    previous = ""
    for row in sorted(M.runs_rows(), key=lambda r: int(r[1])):
        status, fingerprint = row[2], row[7]
        diff = sum(int(row[k]) for k in (3, 4, 5))
        meaning, holds = words.get(status, ("", ""))
        if meaning not in (H.TOTTA, H.OCHITA):
            eight["登録表に無い status 語"] += 1
        elif holds == H.SUEOKI:
            if fingerprint:
                eight["落ちたのに指紋が動いた"] += 1
            else:
                code, when = intents.get(row[0], ("", ""))
                test = words.get(code, ("", ""))[0] == H.SHIKEN
                if test and when == H.MAE:
                    eight["据え置き・試験と事前に宣言されている"] += 1
                else:
                    eight["据え置き・試験の事前の宣言が無い"] += 1
        elif row[6] == H.SHOKAI:
            eight["初回(比べる相手が無い)"] += 1
        elif diff == 0 and fingerprint == previous:
            eight["差分 0 かつ指紋が直前と同じ"] += 1
        elif diff and fingerprint != previous:
            eight["差分ありかつ指紋が直前と違う"] += 1
        else:
            eight["差分の件数と指紋の動きが噛み合わない"] += 1
        if fingerprint:
            previous = fingerprint
    return eight


# ---------------------------------------------------------------- 記事に載せた数値

def test_measure_17_runs_split_into_eight() -> None:
    """(1) 実行 17 回 が 6 値 + 別枠 2 種に分かれ、分母の内訳が付く。"""
    t = pull()
    assert t.report.ok and t.report.pending == ()
    c = t.counts()
    assert c["実行の台帳の行数"] == 17
    assert c["意図の宣言表の行数"] == 5
    assert c["語の登録表の行数"] == 5
    assert c["分母(実行の件数)"] == 17 == t.run_denominator()
    assert c["分母(6 値が付いた回の数)"] == 15
    assert c["分母(別枠の数)"] == 2
    assert c["分母(台帳に出てくる status 語の数)"] == 3
    assert c["6 値 + 別枠"] == {
        "据え置き・試験と事前に宣言されている": 2,
        "据え置き・試験の事前の宣言が無い": 2,
        "初回(比べる相手が無い)": 1,
        "差分 0 かつ指紋が直前と同じ": 3,
        "差分ありかつ指紋が直前と違う": 5,
        "差分の件数と指紋の動きが噛み合わない": 2,
        "登録表に無い status 語": 1,
        "落ちたのに指紋が動いた": 1}
    assert c["6 値 + 別枠"] == expect_eight()
    assert sum(c["6 値 + 別枠"].values()) == 17
    assert c["理由別の止まった件数"] == {}
    assert not any(isinstance(v, float) for v in c.values())
    assert not any(str(k).endswith(("率", "割合", "点", "スコア")) for k in c)
    print("[measure] runs_a / intents_a / words_a: 台帳 17 行 / 宣言 5 行 / 登録 5 行"
          f" → 6 値 + 別枠 {c['6 値 + 別枠']}")
    print("[measure] 分母は 実行の件数 17 / 6 値が付いた回 15 / 別枠 2、"
          "それに 台帳に出てくる status 語 3")


def test_measure_eleven_ok_runs_are_four_kinds() -> None:
    """(2) 通ったと宣言された 11 回 が、4 つの値に分かれる。"""
    t = pull()
    rows = {r["status の語"]: r for r in t.by_status()}
    totta = rows[OK]
    assert totta["回の数"] == 11
    assert totta["意味"] == H.TOTTA and totta["据え置きを伴うか"] == H.SUEOKANAI
    assert totta["6 値 + 別枠"]["初回(比べる相手が無い)"] == 1
    assert totta["6 値 + 別枠"]["差分 0 かつ指紋が直前と同じ"] == 3
    assert totta["6 値 + 別枠"]["差分ありかつ指紋が直前と違う"] == 5
    assert totta["6 値 + 別枠"]["差分の件数と指紋の動きが噛み合わない"] == 2
    assert 1 + 3 + 5 + 2 == 11
    # 「ok の回数 = 更新された回数」と読むと 11、入れ替わった回だけ数えると 5
    assert totta["6 値 + 別枠"]["差分ありかつ指紋が直前と違う"] != totta["回の数"]
    print("[measure] 通ったと宣言された 11 回 の内訳 = 初回 1 + 差分 0 で指紋も同じ 3"
          " + 入れ替わった 5 + 噛み合わない 2。「通った回数 = 更新された回数」と読むと"
          " 11 回 だが、入れ替わった回は 5 回 しかない")


def test_measure_five_failed_runs_are_three_kinds() -> None:
    """(3) 落ちたと宣言された 5 回 が、3 つの値に分かれる(= 記事の骨)。"""
    t = pull()
    rows = {r["status の語"]: r for r in t.by_status()}
    ochita = rows[FAILED]
    assert ochita["回の数"] == 5
    assert ochita["意味"] == H.OCHITA and ochita["据え置きを伴うか"] == H.SUEOKI
    assert ochita["6 値 + 別枠"]["据え置き・試験と事前に宣言されている"] == 2
    assert ochita["6 値 + 別枠"]["据え置き・試験の事前の宣言が無い"] == 2
    assert ochita["6 値 + 別枠"]["落ちたのに指紋が動いた"] == 1
    assert 2 + 2 + 1 == 5
    # 落ちた回に差分と指紋の判定は付かない(見に行く経路が無い)
    for j in t.judged:
        if j.run.status == FAILED and j.result != "落ちたのに指紋が動いた":
            assert j.previous == "" and j.returned is False
    print("[measure] 落ちたと宣言された 5 回 の内訳 = 事前に試験と宣言された 2"
          " + 事前の宣言が無い 2 + 落ちたのに指紋が動いた 1。"
          "「落ちた回数 = 障害の件数」と読むと 5 回 になる")


def test_measure_two_kinds_of_missing_declaration() -> None:
    """(4) ② の 2 回は、言い方の違いのまま一覧に出る(事後の申告を試験に数えない)。"""
    t = pull()
    listed = t.no_declaration()
    assert len(listed) == 2
    kinds = sorted(x["事前の宣言が無い言い方"] for x in listed)
    assert kinds == ["宣言が実行より後", "宣言そのものが無い"]
    ato = next(x for x in listed if x["事前の宣言が無い言い方"] == "宣言が実行より後")
    assert ato["宣言されていた意図コード"] == M.SHIKEN_CODE
    assert all(x["出典"] for x in listed)
    # ① に入った 2 回は、どちらも事前の宣言を持っている
    for j in t.judged:
        if j.result == H.KEKKA[0]:
            x = t.intents.of(j.run.run_id)
            assert x is not None and x.before
    print("[measure] 事前の宣言が無い据え置きは 2 回 で、言い方は 2 通り"
          "(宣言が実行より後 1 / 宣言そのものが無い 1)。事後の宣言の回は"
          " 意図コードが書かれていても ① に入らない")


def test_measure_one_return_and_two_mismatch_shapes() -> None:
    """(5) 戻りの印は 1 回、⑥ の形は 2 通り。"""
    t = pull()
    back = t.returns()
    assert len(back) == 1
    assert back[0]["判定"] == "差分ありかつ指紋が直前と違う"
    assert back[0]["指紋"] == M.FP_A and back[0]["直前の指紋"] == M.FP_B
    assert back[0]["同じ指紋が前に出た回"] == ["R01", "R02"]
    wrong = t.mismatched()
    assert len(wrong) == 2
    assert sorted(x["食い違いの形"] for x in wrong) == \
        ["差分 0 なのに指紋が動いた", "差分ありなのに指紋が同じ"]
    assert all(x["出典"] for x in wrong)
    # ④ の回には戻りの印が付かない(指紋が直前と同じなので動いていない)
    assert [j.run.run_id for j in t.judged
            if j.result == "差分 0 かつ指紋が直前と同じ"] == ["R02", "R08", "R17"]
    assert not any(j.returned for j in t.judged
                   if j.result == "差分 0 かつ指紋が直前と同じ")
    print("[measure] 指紋が履歴の前の回の値へ戻った回は 1 回(R07、同じ指紋が前に"
          "出たのは R01 と R02)。⑥ は 2 回 で、形は 差分 0 なのに動いた 1 + "
          "差分ありなのに同じ 1")


def test_measure_dropping_one_declaration_moves_one_run() -> None:
    """(6) 試験の宣言を 1 件外すと、その回だけが ① から ② へ動く。"""
    runs, intents, words = three()
    first = H.run_kinds(runs, intents, words)
    probe = H.test_probe(runs, intents, words, first)
    assert probe["合うか"] is True
    assert len(probe["回ごと"]) == 2
    for row in probe["回ごと"]:
        assert row["据え置き・試験と事前に宣言されている"] == "2 → 1"
        assert row["据え置き・試験の事前の宣言が無い"] == "2 → 3"
        assert row["移った先の言い方"] == "宣言そのものが無い"
        assert row["ほかで動いた回"] == []
    print("[measure] 試験の宣言を 1 件外すと ① 2 → 1、② 2 → 3 で、動くのはその回"
          "だけ(ほかで動いた回は 2 回とも 0 件)。移った先の言い方は"
          "「宣言そのものが無い」")


def test_measure_repainting_one_fingerprint_moves_one_run() -> None:
    """(7) ④ の回の指紋を書き換えると、その回だけが ④ から ⑥ へ動き、戻りの印は付かない。"""
    runs, intents, words = three()
    first = H.run_kinds(runs, intents, words)
    probe = H.repaint_probe(runs, intents, words, first)
    assert probe["合うか"] is True
    assert [row["書き換えた回"] for row in probe["回ごと"]] == ["R02", "R08", "R17"]
    for row in probe["回ごと"]:
        assert row["差分 0 かつ指紋が直前と同じ"] == "3 → 2"
        assert row["差分の件数と指紋の動きが噛み合わない"] == "2 → 3"
        assert row["戻りの印"] == "付かない"
        assert row["戻りの回の数"] == "1 → 1"
        assert row["ほかで動いた回"] == []
    # 入力の指紋は 1 文字も書き換わらない
    assert H.Runs.load(path_of("runs_a")).items == runs.items
    print("[measure] ④ の 3 回(R02 / R08 / R17)の指紋を履歴に無い値へ書き換えると、"
          "④ 3 → 2、⑥ 2 → 3 で、戻りの回の数は 1 → 1 のまま。ほかで動いた回は"
          " 3 回とも 0 件")


# ---------------------------------------------------------------- 決定論と検算

def test_verify_passes_on_the_synthetic_tables() -> None:
    """verify の 5 つ(2 度走り / 3 通りの入れ替え / 件数の検算 / 写し 2 つ)が全部通る。"""
    runs, intents, words = three()
    out = H.verify(runs, intents, words)
    assert out["ok"] is True and "pending" not in out
    assert out["sha256"] == out["2 回目の sha256"]
    assert set(out["入れ替えた 3 枚の sha256"]) == set(H.SWAPS)
    assert set(out["入れ替えた 3 枚の sha256"].values()) == {out["sha256"]}
    assert out["件数の検算"]["合計"] == 17 == out["件数の検算"]["分母(実行の件数)"]
    assert out["件数の検算"]["6 値"] == 15
    assert out["件数の検算"]["status 語ごとの内訳の合計"] == 17
    assert out["試験の宣言を 1 件外した写し"]["合うか"] is True
    assert out["指紋を 1 つ書き換えた写し"]["合うか"] is True
    print("[measure] 2 回 + 3 通りの入れ替えで読み直し: 判定部分の sha256 は 4 回とも"
          f" 同じ(4/4 一致、先頭 12 桁 {out['sha256'][:12]})")
    print("[measure] 件数の検算: 6 値 + 別枠の合計 17 = 実行の件数 17、"
          "6 値 15 = 6 値が付いた回 15、status 語ごとの内訳の合計 17 = 実行の件数")


def test_order_of_rows_does_not_change_the_result() -> None:
    """3 枚の行順を入れ替えても、判定部分のバイト列が同じ(順は並び順の番号だけで決まる)。"""
    runs, intents, words = three()
    first = H.run_kinds(runs, intents, words)
    for how in H.SWAPS:
        again = H.run_kinds(runs.swapped(how), intents.swapped(how),
                            words.swapped(how))
        assert again.judgement_bytes() == first.judgement_bytes()
        assert again.six() == first.six()


def test_judgement_bytes_have_no_clock_or_path() -> None:
    """判定部分に時刻・絶対パス・ホスト名が入らない。"""
    t = pull()
    body = t.judgement_bytes().decode("utf-8")
    for word in ("読んだ条件", "絶対パス", str(ROOT), str(FIX)):
        assert word not in body
    assert t.read_condition()[H.SCOPE_KEYS[0]].endswith("runs_a.csv")


def test_nine_table_reason_codes_are_all_reachable() -> None:
    """崩した表で、1 回も数えずに止まる理由コード 9 個すべてに道がある。"""
    cases = {
        "runs_shutten_kuuran": H.STOP_REASONS[0],
        "runs_run_id_juufuku": H.STOP_REASONS[1],
        "runs_seq_tobi": H.STOP_REASONS[2],
        "runs_shokai_nikagyou": H.STOP_REASONS[3],
        "runs_sueoki_sabun": H.STOP_REASONS[4],
        "runs_shimon_nashi": H.STOP_REASONS[5],
        "runs_shokai_nashi": H.STOP_REASONS[8],
        "intents_futatsu": H.STOP_REASONS[6],
        "intents_mitouroku": H.STOP_REASONS[7],
        "words_shutten_kuuran": H.STOP_REASONS[0],
    }
    seen: set[str] = set()
    for name, reason in cases.items():
        kind = name.split("_")[0]
        key = {"runs": "d", "intents": "i", "words": "w"}[kind]
        t = pull(**{key: name})
        assert t.report.ok is False
        assert reasons_of(t) == {reason}, (name, reasons_of(t))
        assert t.judged == ()
        assert sum(t.six().values()) == 0
        assert t.returns() == [] and t.mismatched() == [] and t.asides() == []
        for call in (t.judgement_bytes, t.sha256):
            with pytest.raises(RuntimeError):
                call()
        seen.add(reason)
    assert seen == set(H.TABLE_REASONS)
    assert len(H.TABLE_REASONS) == 9 and len(H.VERIFY_REASONS) == 3
    assert len(H.STOP_REASONS) == 12
    print("[measure] 止まる理由コードは 12 個(表の側 9 + verify 3)で、表の側 9 個"
          "すべてに崩した表で道がある。止まった表では 6 値は全て 0 で、"
          "一覧も全て 0 件")


def test_three_verify_reason_codes_are_all_reachable(monkeypatch) -> None:
    """verify が見つける理由コード 3 個は、実装を差し替えると出る。"""
    runs, intents, words = three()
    monkeypatch.setattr(H.Tally, "six", lambda self: {k: 0 for k in H.KEKKA})
    out = H.verify(runs, intents, words)
    assert out["ok"] is False
    assert H.STOP_REASONS[9] in {p["理由コード"] for p in out["pending"]}
    monkeypatch.undo()

    counter = {"n": 0}

    def wobble(self) -> str:
        counter["n"] += 1
        return f"{counter['n']:064d}"

    monkeypatch.setattr(H.Tally, "sha256", wobble)
    out = H.verify(runs, intents, words)
    assert out["ok"] is False
    assert H.STOP_REASONS[10] in {p["理由コード"] for p in out["pending"]}
    monkeypatch.undo()

    monkeypatch.setattr(H.Runs, "ordered", property(lambda self: self.items))
    out = H.verify(runs, intents, words)
    assert out["ok"] is False
    assert H.STOP_REASONS[11] in {p["理由コード"] for p in out["pending"]}


def test_broken_tables_are_counted() -> None:
    """崩した表 30 枚の内訳(理由コード 11 枚 / 表として読めない 19 枚)。"""
    names = sorted(p.stem for p in (FIX / "kowashita").glob("*.csv"))
    assert len(names) == 30
    reason_files, unreadable = [], []
    for name in names:
        kind = name.split("_")[0]
        key = {"runs": "d", "intents": "i", "words": "w"}[kind]
        try:
            t = pull(**{key: name})
        except H.ReadError:
            unreadable.append(name)
            continue
        assert t.report.ok is False
        reason_files.append(name)
    assert len(reason_files) == 11
    assert len(unreadable) == 19
    print(f"[measure] 崩した表 30 枚の内訳 = 1 回も数えずに止まる 11 枚 / "
          f"表として読めない 19 枚")


def test_inputs_are_never_rewritten() -> None:
    """読む前後で入力ファイルの sha256 が同じ(写しはメモリの中だけ)。"""
    files = sorted(FIX.rglob("*.csv"))
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    runs, intents, words = three()
    H.verify(runs, intents, words)
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    assert before == after
    assert len(files) == 33
    print(f"[measure] 読む前後で入力 {len(files)} ファイルの sha256 が同じ")


# ---------------------------------------------------------------- 持たせていないもの

def test_implementation_has_no_clock_no_float_no_network() -> None:
    """時計・float・通信・再実行の経路が、動く側のコードに 1 つも無い。"""
    text = (ROOT / "run_kinds.py").read_text(encoding="utf-8")
    code = "".join(
        tok.string for tok in tokenize.generate_tokens(io.StringIO(text).readline)
        if tok.type not in (tokenize.COMMENT, tokenize.STRING))
    for word in MOTANAI:
        assert word not in code, word
    tree = ast.parse(text)
    imported = {n.names[0].name.split(".")[0] for n in ast.walk(tree)
                if isinstance(n, ast.Import)}
    imported |= {n.module.split(".")[0] for n in ast.walk(tree)
                 if isinstance(n, ast.ImportFrom) and n.module}
    assert imported == {"__future__", "argparse", "csv", "hashlib", "json", "sys",
                        "dataclasses", "pathlib"}
    print(f"[measure] 部品が import している module は {len(imported)} 個で、"
          "現在時刻を読む呼び出し・float / eval / exec / round / subprocess / "
          "random / platform / 通信 の呼び出しは 0 件")


def test_no_judgement_words_in_output_or_code() -> None:
    """良し悪しを指す語と形容の語が、件数の側にも、動く側のコードにも無い。

    「成功率を出さない」のような**出さないと書いた固定の行**は本文として出るので、
    数と一覧の側(= 文字列でない値)だけを見る。コードの側は文字列とコメントを外して見る。
    """
    t = pull()
    c = t.counts()
    body = json.dumps({k: v for k, v in c.items() if not isinstance(v, str)}
                      | {"一覧": t.listed(), "戻り": t.returns(),
                         "別枠": t.asides(), "噛み合わない": t.mismatched(),
                         "宣言が無い": t.no_declaration()}, ensure_ascii=False)
    text = (ROOT / "run_kinds.py").read_text(encoding="utf-8")
    code = "".join(
        tok.string for tok in tokenize.generate_tokens(io.StringIO(text).readline)
        if tok.type not in (tokenize.COMMENT, tokenize.STRING))
    for word in KINSOKU + KEIYOU:
        assert word not in body, word
        assert word not in code, word
    print(f"[measure] 良し悪しを指す語 {len(KINSOKU)} 個と形容の語 {len(KEIYOU)} 個は、"
          "件数と一覧にも、文字列を外したコードにも 0 件")


def test_counts_have_no_ratio_and_no_rank() -> None:
    """割合・点数・順位の欄が無く、値は全て整数(または文字列)。"""
    c = pull().counts()
    for key, value in c.items():
        assert not isinstance(value, float)
        if isinstance(value, str):
            continue        # 固定の説明行(出さないと書いてある側)
        for word in ("率", "割合", "順位", "点数", "推奨", "スコア"):
            assert word not in str(key), (key, word)
    assert isinstance(c["6 値 + 別枠"], dict)
    assert all(isinstance(v, int) for v in c["6 値 + 別枠"].values())


def test_intent_holds_column_is_recorded_but_not_used() -> None:
    """意図コードの行の「据え置きを伴うか」を書き換えても、判定も指紋も 1 つも動かない。"""
    runs, intents, words = three()
    first = H.run_kinds(runs, intents, words)
    rows = [[w.word, w.meaning,
             (H.SUEOKANAI if w.holds == H.SUEOKI else H.SUEOKI)
             if w.is_intent else w.holds, w.declared_in] for w in words.items]
    text = "\n".join([",".join(H.WORDS_COLUMNS)] + [",".join(r) for r in rows])
    after = H.run_kinds(runs, intents, H.Words.parse(text))
    assert after.report.ok
    assert after.sha256() == first.sha256()
    assert after.six() == first.six()
    print("[measure] 意図コードの行の 据え置きを伴うか を全部裏返しても、6 値も"
          "判定部分の sha256 も 1 つも動かない(= 判定に使っていない)")


def test_unused_and_dangling_declarations_are_listed_not_stopped() -> None:
    """逆向きの欠けと、据え置きでない回に付いた宣言は、止めずに一覧へ出る。"""
    t = pull()
    assert t.report.ok
    dangling = t.dangling_intents()
    assert len(dangling) == 1
    assert dangling[0]["指している実行 id"] == "R99"
    unused = t.unused_intents()
    assert len(unused) == 1
    assert unused[0]["実行 id"] == "R06"
    assert unused[0]["その回の判定"] == "差分ありかつ指紋が直前と違う"
    assert all(x["出典"] for x in dangling + unused)
    # どちらも 6 値の分母には入らない
    assert t.run_denominator() == 17
    print("[measure] 逆向きの欠けは 1 件(台帳に無い実行 id を指す宣言 R99)、"
          "据え置きでない回に付いた宣言も 1 件(R06)。どちらも止めずに一覧へ出て、"
          "実行の件数 17 の分母には入らない")


def test_registered_but_unused_word_is_fine() -> None:
    """登録表に在るが台帳に出てこない語が在っても、件数は動かない。"""
    t = pull()
    assert M.SKIPPED in t.words.status_words
    assert M.SKIPPED not in {r["status の語"] for r in t.by_status()}
    assert t.counts()["分母(台帳に出てくる status 語の数)"] == 3
    assert len(t.words.status_words) == 3


def test_unregistered_status_word_goes_aside_with_its_source() -> None:
    """登録表に無い status 語は別枠へ出て、出典が付く(語の形から意味を当てない)。"""
    t = pull()
    j = judged_of(t, "R14")
    assert j.result == "登録表に無い status 語"
    assert j.counted is False
    assert j.previous == "" and j.returned is False
    aside = [x for x in t.asides() if x["実行 id"] == "R14"]
    assert len(aside) == 1 and aside[0]["出典"]


def test_held_run_with_a_fingerprint_goes_aside() -> None:
    """落ちたと宣言されたのに指紋が動いている回は、6 値に入れずに別枠へ出す。"""
    t = pull()
    j = judged_of(t, "R15")
    assert j.result == "落ちたのに指紋が動いた"
    assert j.counted is False
    assert j.run.fingerprint == M.FP_F
    # 指紋の欄が埋まっているので、後ろの回の「直前」としては数える
    assert judged_of(t, "R16").previous == M.FP_F


def test_exit_codes() -> None:
    """終了コードは 0 / 3 / 2 の 3 通り(0 は欠けが無い、の意味)。"""
    argv = ["check", str(path_of("runs_a")), str(path_of("intents_a")),
            str(path_of("words_a"))]
    assert H.main(argv) == 3        # 別枠と ⑥ と ② が在るので 3
    assert H.main(["check", str(path_of("runs_shutten_kuuran")),
                   str(path_of("intents_a")), str(path_of("words_a"))]) == 3
    assert H.main(["check", str(path_of("runs_seq_zero")),
                   str(path_of("intents_a")), str(path_of("words_a"))]) == 2


def test_init_writes_three_tables_that_read_back(tmp_path) -> None:
    """ひな型の 3 枚は、そのまま読んで 6 値が付く(合成の値だけ)。"""
    paths = H.init(tmp_path / "ひな型")
    assert len(paths) == 3 and all(p.exists() for p in paths)
    t = H.run_kinds(H.Runs.load(paths[0]), H.Intents.load(paths[1]),
                    H.Words.load(paths[2]))
    assert t.report.ok
    assert sum(t.six().values()) == 4
    assert t.six()["据え置き・試験と事前に宣言されている"] == 1
    for p in paths:
        assert "架空" in p.read_text(encoding="utf-8")


def test_sources_point_at_real_lines_in_this_repo() -> None:
    """この repo 内の行を指す出典は、本当にその行に在る(ファイル名 + 行番号で照合)。"""
    for source, word in REAL_SOURCES.items():
        name, line_no = source.rsplit(" L", 1)
        lines = (PLAN / name).read_text(encoding="utf-8").splitlines()
        assert word in lines[int(line_no) - 1], (source, word)


def test_every_row_of_every_fixture_has_a_source() -> None:
    """合成した 3 枚の全ての行に出典が在る(出典の無い行は止まるので、入れない)。"""
    runs, intents, words = three()
    assert all(r.source for r in runs.items)
    assert all(x.source for x in intents.items)
    assert all(w.declared_in for w in words.items)
    assert len(runs.items) == 17 and len(intents.items) == 5
    assert len(words.items) == 5
