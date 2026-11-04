"""diff_tally のテスト。合成 fixture は `fixtures/` に commit 済(実データ・実在の値は入れない)。

test_measure_* が記事に載せた数値の出どころで、assert で固定している(値が変われば記事も変える前提)。
測っているものは 8 つある。

  (1) 回 13 件が 12 対に分かれ、6 値と分母の内訳が付く側
  (2) **2 経路の単位が別で、足せない**側(差分の 3 欄を全部足した 1,684 はどこにも出ない)
  (3) **差分 0 なのに指紋が変わった対が 1 件、指紋が過去の回へ戻った対が 2 件**という側。
      = 記事の骨
  (4) 累積 1,681 と棚卸しの宣言 1,681 が一致し、**中身が替わった行数を足すと合わなくなる**側
  (5) 落ちた 2 回が「差分の欄が記載なし」で、理由は宣言の写しだけになる側
  (6) ある回の指紋を前の回と同じにすると、その対が ④ から ③ へ移り、累積が動かない側
  (7) 累積の宣言を替えると累積だけが動き、中身が替わった行数を増やしても累積は動かない側
  (8) 出力の末尾に並ぶ「持たせていないもの」が 14 行で、合成の指紋が 20 文字そろいである側

(1) の 6 値は、テストの側でも 5 枚の行から直に組み立てて確かめている(部品の judge /
six を呼ばず、fixture の行から別に分類する)。
"""
from __future__ import annotations

import ast
import json
import hashlib
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FIX))
import diff_tally as H  # noqa: E402
import make_fixtures as M  # noqa: E402

# 良し悪し・正しさを指す語(件数と一覧の側に持たせない = 型 S2 の forbidden の物理形)
KINSOKU = ("正しい", "信頼", "一致率", "健全", "劣化", "違反", "推定", "原因",
           "成功率", "厚い", "薄い")

# 形容の語(数値が無いなら多寡を書かない)
KEIYOU = ("多い", "少ない", "ほとんど", "かなり", "著しく", "ざっと")

# 持たせていない経路の名前(動く側のコードに 1 つも無いことを見る)
MOTANAI = ("eval", "exec", "round(", "float(", "now(", "today(", "time(",
           "subprocess", "random", "platform", "datetime", "urllib", "requests",
           "socket", "difflib", "SequenceMatcher", "statistics", "mean(",
           "median(", "read_bytes")

# 差分の 3 欄を全部足した数(**この数がどこにも出ないことがこの部品の骨の物理形**)
TASHITA = 1684

LOADERS = (H.Runs.load, H.Stocks.load, H.Fields.load, H.Statuses.load,
           H.Reasons.load)
NORMAL = ("runs_a", "stocks_a", "fields_a", "statuses_a", "reasons_a")


def path_of(name: str) -> Path:
    return FIX / f"{name}.csv" if name in NORMAL else FIX / "kowashita" / f"{name}.csv"


def five(r: str = "runs_a", s: str = "stocks_a", f: str = "fields_a",
         t: str = "statuses_a", y: str = "reasons_a"):
    names = (r, s, f, t, y)
    return tuple(LOADERS[i](path_of(names[i])) for i in range(5))


def pull(**kw) -> H.Tally:
    return H.diff_tally(*five(**kw))


def reasons_of(t: H.Tally) -> set[str]:
    return {p.reason for p in t.report.pending}


def pair_of(t: H.Tally, name: str) -> H.Pair:
    return next(p for p in t.pairs if p.name == name)


# ---------------------------------------------------------------- 別実装(テスト側)

def expect_six() -> dict[str, int]:
    """5 枚の行から 6 値を別に数える(部品の judge / six / counts を呼ばない)。"""
    rows = sorted(M.runs_rows(), key=lambda r: int(r[1]))
    six = {k: 0 for k in H.MUTSU}
    for i in range(1, len(rows)):
        before, after = rows[i - 1], rows[i]
        tallies = after[3:6]
        if H.NONE_MARK in tallies:
            six[H.MUTSU[4]] += 1
            continue
        if after[6] == H.NONE_MARK or before[6] == H.NONE_MARK:
            six[H.MUTSU[5]] += 1
            continue
        zero = all(v == "0" for v in tallies)
        same = after[6] == before[6]
        if zero and same:
            six[H.MUTSU[0]] += 1
        elif zero:
            six[H.MUTSU[1]] += 1
        elif same:
            six[H.MUTSU[2]] += 1
        else:
            six[H.MUTSU[3]] += 1
    return six


def expect_backs() -> list[tuple[str, list[str]]]:
    """戻りの印をテストの側で別に出す(指紋が前の回でなく過去の回と同じ対)。"""
    rows = sorted(M.runs_rows(), key=lambda r: int(r[1]))
    out: list[tuple[str, list[str]]] = []
    for i in range(1, len(rows)):
        before, after = rows[i - 1], rows[i]
        if H.NONE_MARK in after[3:6] or H.NONE_MARK in (after[6], before[6]):
            continue
        if after[6] == before[6]:
            continue
        hit = sorted(r[0] for r in rows[:i - 1]
                     if r[6] != H.NONE_MARK and r[6] == after[6])
        if hit:
            out.append((f"{before[0]}>{after[0]}", hit))
    return out


# ---------------------------------------------------------------- 測る側

def test_measure_13_runs_split_into_six() -> None:
    """(1) 回 13 件が 12 対に分かれ、6 値と分母の内訳が付く。"""
    t = pull()
    assert t.report.ok and t.report.pending == ()
    c = t.counts()
    assert c["実行の記録の台帳の行数"] == 13
    assert c["棚卸しの台帳の行数"] == 2
    assert c["欄の登録表の行数"] == 3
    assert c["結果記号の登録表の行数"] == 3
    assert c["差の理由の宣言表の行数"] == 3
    assert c["分母(回の件数)"] == 13 == t.run_denominator()
    assert c["分母(回の対の件数)"] == 12 == t.pair_denominator()
    assert c["対象の期間"] == "順序番号 1〜13"
    assert c["6 値"] == {
        "差分が 0 で指紋も前の回と同じ": 3,
        "差分は 0 なのに指紋が前の回と違う": 1,
        "差分は 0 でないのに指紋が前の回と同じ": 1,
        "差分も指紋も動いた": 4,
        "差分の欄が記載なし": 2,
        "指紋が記載なし": 1}
    assert c["6 値"] == expect_six()
    assert sum(c["6 値"].values()) == 12
    assert c["2 経路が別の答えを返した対"] == 2
    assert c["片方の欄が記載なしの対"] == 3
    assert c["戻りの印"] == 2
    assert c["理由別の止まった件数"] == {}
    assert c["突合に使っていない棚卸しの時点"] == 1
    assert c["どの対にも当たらない理由の宣言"] == 1
    assert [(r["結果記号"], r["回の数"]) for r in t.by_status()] == [
        ("S1", 10), ("S2", 2), ("S3", 1)]
    assert sum(int(r["回の数"]) for r in t.by_status()) == 13
    assert not any(isinstance(v, float) for v in c.values())
    assert not any(str(k).endswith(("率", "割合", "スコア", "順位", "点数")) for k in c)
    print("[measure] runs_a / stocks_a / fields_a / statuses_a / reasons_a:"
          " 回 13 行 / 棚卸し 2 行 / 欄 3 行 / 結果記号 3 行 / 理由 3 行"
          f" → 回の対 12 件が 6 値 {c['6 値']}")
    print("[measure] 分母は 回の件数 13 / 回の対の件数 12、結果記号ごとは"
          " S1 10 + S2 2 + S3 1 = 13 = 回の件数")


def test_measure_two_routes_have_different_units() -> None:
    """(2) 2 経路の単位が別で、足せない(差分の 3 欄を全部足した 1,684 は出ない)。"""
    t = pull()
    units = t.units()
    assert len(units) == 4
    assert [(u["経路"], u["欄名"], u["行数を動かすか"], u["単位記号"]) for u in units] == [
        ("A(差分の記録)", "added", "増やす", "行"),
        ("A(差分の記録)", "changed", "動かさない", "行"),
        ("A(差分の記録)", "removed", "減らす", "行"),
        ("B(出力の指紋)", "fingerprint", "動かさない", "文字列の一致")]
    # **中身が替わった行数まで足した数は、出力のどこにも現れない**
    counted = set(t.statuses.counted())
    total = sum((r.value(f) or 0) * (1 if f != "removed" else -1)
                for r in t.runs.ordered if r.status in counted
                for f in H.DIFF_FIELDS)
    assert total == TASHITA
    dumped = json.dumps({"counts": t.counts(), "listed": t.listed()},
                        ensure_ascii=False, default=str)
    assert str(TASHITA) not in dumped
    print("[measure] 2 経路の単位は別で、経路A は 3 欄とも 行、経路B は 文字列の一致。"
          "行数を動かすのは added(増やす)と removed(減らす)の 2 欄だけで、"
          "changed は 動かさない")
    print(f"[measure] 中身が替わった行数まで足すと {TASHITA} になるが、"
          "この数は出力にも一覧にも 1 度も現れない(足す経路を置いていない)")


def test_measure_diff_zero_but_fingerprint_moved() -> None:
    """(3) 差分 0 なのに指紋が変わった対が 1 件、指紋が過去の回へ戻った対が 2 件(= 骨)。"""
    t = pull()
    split = t.split_pairs()
    assert len(split) == 2
    assert [(s["対"], s["判定"]) for s in split] == [
        ("R09 → R10", "差分は 0 なのに指紋が前の回と違う"),
        ("R11 → R12", "差分は 0 でないのに指紋が前の回と同じ")]
    # 差分 0 なのに指紋が変わった対(2 経路が別の答えを返す)
    p = pair_of(t, "R09>R10")
    assert p.after.zero_tally is True
    assert p.after.fingerprint != p.before.fingerprint
    assert p.gap == "2 経路が別の答え"
    assert p.reason == "出力の並べ方を変えた回"
    # 差分は 0 でないのに指紋が同じ対
    q = pair_of(t, "R11>R12")
    assert q.after.zero_tally is False
    assert q.after.fingerprint == q.before.fingerprint
    assert q.gap == "2 経路が別の答え" and q.reason == H.NOT_DECLARED
    # 戻りの印(指紋が前の回でなく過去のどれかの回と同じ文字列)
    backs = t.backs()
    assert len(backs) == 2
    assert [(b["対"], b["一致した run id"]) for b in backs] == [
        ("R05 → R06", ["R01", "R02"]), ("R12 → R13", ["R05"])]
    assert [(n, h) for n, h in expect_backs()] == [
        ("R05>R06", ["R01", "R02"]), ("R12>R13", ["R05"])]
    # **戻った回の差分は 0 でない**(片方の経路だけでは「動いていない」と書けない)
    assert pair_of(t, "R05>R06").after.zero_tally is False
    # どちらが正しいかは書かない
    dumped = json.dumps({"split": split, "backs": backs}, ensure_ascii=False)
    for word in ("正しい", "信頼", "一致率", "優先", "採用"):
        assert word not in dumped
    print("[measure] 差分 0 なのに指紋が前の回と違う対は 1 件(R09 → R10)、"
          "差分は 0 でないのに指紋が同じ対は 1 件(R11 → R12)。"
          "合わせて 2 件が「2 経路が別の答え」")
    print("[measure] 指紋が過去の回へ戻った対は 2 件(R05 → R06 が R01 / R02 と同じ、"
          "R12 → R13 が R05 と同じ)。どちらも差分は 0 でない")


def test_measure_cumulative_matches_only_without_changed() -> None:
    """(4) 累積 1,681 と棚卸しの宣言 1,681 が一致し、changed を足すと合わなくなる。"""
    t = pull()
    c = t.cumulative()
    assert c["足した欄"] == ["added"] and c["引いた欄"] == ["removed"]
    assert c["累積に入る経路が無い欄"] == ["changed"]
    assert c["累積に入れると宣言された結果記号"] == ["S1"]
    assert len(c["累積に足した回"]) == 10
    assert c["累積(増やす欄の和 - 減らす欄の和)"] == 1681
    assert c["突合に使った棚卸しの時点記号"] == "A2"
    assert c["棚卸しが宣言している行数"] == 1681
    assert c["棚卸しが宣言している rule 数"] == 45
    assert c["突合"] == H.MATCH and c["差(棚卸しの宣言 - 累積)"] == 0
    assert c["単位"] == "行" and c["対象の期間"] == "順序番号 1〜13"
    # changed を足すと 3 だけずれる(= 行の数を動かさない欄を足した分)
    counted = set(t.statuses.counted())
    changed = sum(r.value("changed") or 0 for r in t.runs.ordered
                  if r.status in counted)
    assert changed == 3
    assert 1681 + changed == TASHITA != c["棚卸しが宣言している行数"]
    # 突合に使っていない時点は黙って落とさずに並べる
    assert [(s["時点記号"], s["宣言された行数"]) for s in t.unused_stocks()] == [
        ("A1", 1301)]
    print("[measure] 累積に入れると宣言された回だけの(増えた - 減った)は 1,681 行 で、"
          "棚卸しの宣言 1,681 行(45 rule)と 一致、差 0。足した欄は added、"
          "引いた欄は removed、changed は累積に入る経路が無い")
    print(f"[measure] changed を足すと 1,681 + 3 = {TASHITA} で棚卸しの宣言と"
          "合わなくなる(行の数を動かさない欄を足した分だけずれる)")


def test_measure_failed_runs_have_no_tally_column() -> None:
    """(5) 落ちた 2 回が「差分の欄が記載なし」で、理由は宣言の写しだけ。"""
    t = pull()
    missing = t.missing_side()
    assert len(missing) == 3
    assert [(m["対"], m["判定"]) for m in missing] == [
        ("R02 → R03", "差分の欄が記載なし"),
        ("R03 → R04", "差分の欄が記載なし"),
        ("R04 → R05", "指紋が記載なし")]
    assert pair_of(t, "R02>R03").reason == "上流の値を崩した試験の回"
    assert pair_of(t, "R03>R04").reason == H.NOT_DECLARED
    assert pair_of(t, "R04>R05").reason == H.NOT_DECLARED
    # 落ちた回は本番の出力を差し替えず、累積にも入らない
    s = next(r for r in t.by_status() if r["結果記号"] == "S2")
    assert s["本番の出力を差し替えるか"] == "差し替えない"
    assert s["累積に入れるか"] == "入れない" and s["回の数"] == 2
    # 隣り合っていない対を指す宣言は、止めずに一覧へ出す
    assert [d["指している対"] for d in t.dangling_reasons()] == ["R01 → R11"]
    print("[measure] 片方の欄が記載なしの対は 3 件(差分の欄が記載なし 2 +"
          " 指紋が記載なし 1)。落ちた 2 回(S2)は本番の出力を差し替えず、累積にも"
          "入らない")
    print("[measure] 差の理由が宣言されていた対は 2 件で、残りは 宣言なし。"
          "隣り合っていない対を指す宣言 1 件は、止めずに一覧へ出す")


def test_measure_rewriting_one_fingerprint_moves_one_pair() -> None:
    """(6) ある回の指紋を前の回と同じにすると、その対が ④ から ③ へ移り累積は動かない。"""
    probe = H.fingerprint_probe(*five(), pull())
    assert probe["合うか"] is True
    assert probe["書き換えた run id"] == "R13" and probe["書き換えた対"] == "R12>R13"
    assert probe["判定(前)"] == "差分も指紋も動いた"
    assert probe["判定(後)"] == "差分は 0 でないのに指紋が前の回と同じ"
    assert probe["戻りの印(後)"] == [] and probe["ほかで動いた対"] == []
    assert probe["6 値(後)"]["差分も指紋も動いた"] == 3
    assert probe["6 値(後)"]["差分は 0 でないのに指紋が前の回と同じ"] == 2
    assert probe["累積(前)"] == probe["累積(後)"] == 1681
    assert probe["差(前)"] == probe["差(後)"] == 0
    print("[measure] 指紋を前の回と同じにした写し: R13 の指紋を R12 と同じにすると、"
          "その対が ④(4 → 3 件)から ③(1 → 2 件)へ移り、ほかで動いた対は 0 件。"
          "累積は 1,681 のまま、差も 0 のまま")


def test_measure_cumulative_moves_only_from_the_registry() -> None:
    """(7) 累積の宣言を替えると累積だけが動き、changed を増やしても累積は動かない。"""
    t = pull()
    bump = H.changed_probe(*five(), t)
    assert bump["合うか"] is True
    assert bump["増やした run id"] == "R05" and bump["増やした欄"] == "changed"
    assert bump["増やす前の件数"] == 1 and bump["増やした後の件数"] == 2
    assert bump["6 値は不変か"] is True and bump["ほかで動いた対"] == []
    assert bump["累積(前)"] == bump["累積(後)"] == 1681
    assert bump["差(前)"] == bump["差(後)"] == 0
    flip = H.include_probe(*five(), t)
    assert flip["合うか"] is True
    assert flip["替えた結果記号"] == "S3" and flip["替えた先"] == "入れる"
    assert flip["6 値は不変か"] is True and flip["ほかで動いた対"] == []
    assert len(flip["累積に足した回(前)"]) == 10
    assert len(flip["累積に足した回(後)"]) == 11
    assert flip["累積(前)"] == 1681 and flip["累積(後)"] == 1686
    assert flip["突合(前)"] == H.MATCH and flip["突合(後)"] == H.DIFFER
    assert flip["差(前)"] == 0 and flip["差(後)"] == -5
    print("[measure] 中身が替わった行数を 1 件増やした写し: R05 の changed を 1 → 2 に"
          "しても累積は 1,681 のままで、6 値も 1 つも動かない")
    print("[measure] 累積の宣言を替えた写し: S3 を 入れない → 入れる にすると"
          "累積に足す回が 10 → 11 件、累積が 1,681 → 1,686、突合が 一致 → 差がある"
          "(差 -5)。6 値は 1 つも動かない")


def test_verify_five_things() -> None:
    """verify が 5 つ見て、判定部分の sha256 が 4 回とも同じ。"""
    out = H.verify(*five())
    assert out["ok"] is True
    assert out["読んだ回数"] == 2
    assert out["sha256"] == out["2 回目の sha256"]
    assert set(out["入れ替えた 5 枚の sha256"].values()) == {out["sha256"]}
    assert out["入れ替え方"] == list(H.SWAPS)
    tally = out["件数の検算"]
    assert tally["合計"] == 12 == tally["分母(回の対の件数)"]
    assert tally["結果記号ごとの内訳の合計"] == 13 == tally["分母(回の件数)"]
    assert tally["戻りの印"] == 2
    assert "pending" not in out
    print(f"[measure] 2 回 + 3 通りの入れ替えで読み直し: 判定部分の sha256 は"
          f" 4 回とも同じ(4/4 一致、先頭 12 桁 {out['sha256'][:12]})")
    print("[measure] 件数の検算: 6 値の合計 12 = 回の対の件数 12、"
          "結果記号ごとの内訳の合計 13 = 回の件数 13")


def test_judgement_bytes_have_no_path_or_clock() -> None:
    """判定部分に絶対パス・ホスト名が入らない(= 同じ表なら同じバイト列)。"""
    t = pull()
    body = t.judgement_bytes().decode("utf-8")
    for word in ("読んだ条件", "絶対パス", str(ROOT), str(FIX)):
        assert word not in body
    assert t.sha256() == hashlib.sha256(t.judgement_bytes()).hexdigest()
    assert len(body.splitlines()) == 14      # 件数 1 + 対 12 + 累積 1


# ---------------------------------------------------------------- 止まる側

def test_measure_eleven_stop_reasons_and_broken_tables() -> None:
    """止まる理由コードは 11 個で、表の側 8 個すべてに崩した表で道がある。"""
    assert len(H.STOP_REASONS) == 11
    assert len(H.TABLE_REASONS) == 8 and len(H.VERIFY_REASONS) == 3
    broken = sorted((FIX / "kowashita").glob("*.csv"))
    keys = {"runs": "r", "stocks": "s", "fields": "f", "statuses": "t",
            "reasons": "y"}
    seen: set[str] = set()
    stopped = read_error = 0
    for p in broken:
        try:
            t = pull(**{keys[p.stem.split("_")[0]]: p.stem})
        except H.ReadError:
            read_error += 1
            continue
        assert t.report.ok is False, p.stem
        assert t.pairs == ()
        assert t.six() == {k: 0 for k in H.MUTSU}
        assert t.backs() == [] and t.split_pairs() == [] and t.missing_side() == []
        assert t.pair_denominator() == 0
        for call in (t.judgement_bytes, t.sha256):
            with pytest.raises(RuntimeError):
                call()
        seen |= reasons_of(t)
        stopped += 1
    assert seen == set(H.TABLE_REASONS)
    assert stopped == 15 and read_error == 25 and len(broken) == 40
    print("[measure] 止まる理由コードは 11 個(表の側 8 + verify 3)で、表の側 8 個"
          "すべてに崩した表で道がある。止まった表では 6 値は全て 0、一覧も全て 0 件")
    print("[measure] 崩した表 40 枚の内訳 = 1 対も数えずに止まる 15 枚 /"
          " 表として読めない 25 枚")


def test_field_registry_must_cover_all_three() -> None:
    """差分の 3 欄のどれかが登録表に無いと、1 対も数えずに止まる。"""
    t = pull(f="fields_ran_tarinai")
    assert reasons_of(t) == {"欄名が登録表に無い"}
    assert [p.detail for p in t.report.pending] == ["欄名 changed"]


def test_sequence_must_be_contiguous() -> None:
    """順序番号の重複と飛びは、どちらも同じ理由コードで止まる。"""
    for name in ("runs_junjo_juufuku", "runs_junjo_tobi"):
        t = pull(r=name)
        assert reasons_of(t) == {"順序番号の重複または飛び"}, name


# ---------------------------------------------------------------- 持たせていない側

def test_no_forbidden_paths_in_source() -> None:
    """動く側のコードに、現在時刻 / float / 乱数 / 通信 / 平均 の呼び出しが 1 つも無い。"""
    src = (ROOT / "diff_tally.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    # 文字列と注釈を外したコードだけを見る(説明文に語が出るのは許す)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            node.value = ""
    bare = ast.unparse(tree)
    for word in MOTANAI:
        assert word not in bare, word
    # **ハッシュを計算する経路は判定部分の 1 か所だけ**(file を読んで hash にしない)
    assert bare.count("hashlib.sha256") == 1
    imports = {n.names[0].name.split(".")[0] for n in ast.walk(tree)
               if isinstance(n, ast.Import)}
    imports |= {n.module.split(".")[0] for n in ast.walk(tree)
                if isinstance(n, ast.ImportFrom) and n.module}
    assert imports == {"argparse", "csv", "hashlib", "json", "sys", "dataclasses",
                       "pathlib", "__future__"}
    print(f"[measure] 部品が import している module は {len(imports)} 個で、"
          "現在時刻を読む呼び出し・float / eval / exec / round / subprocess /"
          " random / 平均 / 通信 の呼び出しは 0 件。hashlib を呼ぶのは判定部分の"
          " 1 か所だけ")


def test_counts_have_no_right_route_or_rate() -> None:
    """件数と一覧の側に、正しい経路・一致率・原因の語が無い。"""
    t = pull()
    structured = json.dumps({"件数": t.six(), "結果記号ごと": t.by_status(),
                             "単位": t.units(), "累積": t.cumulative(),
                             "一覧": t.listed(), "戻り": t.backs(),
                             "別の答え": t.split_pairs(),
                             "記載なし": t.missing_side(),
                             "逆向き": t.dangling_reasons(),
                             "使っていない時点": t.unused_stocks()},
                            ensure_ascii=False, default=str)
    body = t.judgement_bytes().decode("utf-8")
    for word in KINSOKU + KEIYOU + ("%", "カバー率", "スコア"):
        assert word not in structured, word
        assert word not in body, word
    # 出力の key に「正しい経路」「一致率」の欄が無い
    for key in t.counts():
        if "正しい" in key or "一致率" in key:
            assert key == "正しい経路を決めない"


def test_measure_fourteen_tail_lines_cannot_be_removed() -> None:
    """出力の末尾に並ぶ「持たせていないもの」は 14 行で、消す引数が無い。"""
    t = pull()
    keys = list(t.counts())
    tail = keys[keys.index("正しい経路を決めない"):]
    assert len(tail) == 14
    assert tail[0] == "正しい経路を決めない" and tail[-1] == "入力を書き換えない"
    # 合成の指紋は 20 文字でそろえてある(実在のハッシュ値ではない)
    lengths = {len(r.fingerprint) for r in t.runs.items if not r.missing_fingerprint}
    assert lengths == {20}
    print("[measure] 出力の末尾の「持たせていないもの」は 14 行で、"
          "消す引数も option も無い。合成の指紋は 20 文字でそろえてある")


def test_inputs_are_not_rewritten() -> None:
    """読む前後で入力ファイルの sha256 が同じ(verify の 3 つの写しも含む)。"""
    paths = sorted(FIX.rglob("*.csv"))
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    H.verify(*five())
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    assert before == after and len(paths) == 45


def test_registries_are_closed() -> None:
    """登録表の記号は、登録の集合の外に出ない。"""
    assert len(H.MUTSU) == 6 and len(H.DIFF_FIELDS) == 3
    assert len(H.MOVES) == 3 and len(H.FIELD_UNITS) == 2
    assert len(H.REPLACES) == 2 and len(H.CUMULATIVE) == 2
    t = pull()
    assert {p.value for p in t.pairs} <= set(H.MUTSU)
    assert {f.moves for f in t.fields.items} <= set(H.MOVES)
    assert {f.unit for f in t.fields.items} <= set(H.FIELD_UNITS)
    assert {s.cumulative for s in t.statuses.items} <= set(H.CUMULATIVE)
    # 結果記号の意味は登録表からだけ引く(記号の綴りから当てない)
    assert t.statuses.of("S1").cumulative == "入れる"
    assert t.statuses.of("合成の未登録の結果記号") is None
    assert t.fields.of("fingerprint") is None
    # 累積に入るのは 増やす / 減らす と宣言された欄だけ
    assert t.fields.moving("増やす") == ("added",)
    assert t.fields.moving("減らす") == ("removed",)
    assert "changed" not in t.fields.moving("増やす") + t.fields.moving("減らす")


def test_cli_exit_codes() -> None:
    """check は揃わない対が在れば 3、表として読めなければ 2、init はひな型を書いて 0。"""
    args = [str(path_of(n)) for n in NORMAL]
    assert H.main(["check"] + args) == 3           # ②③⑤⑥ と戻りの印が在る
    assert H.main(["verify"] + args) == 0
    broken = [str(path_of("runs_0gyou"))] + args[1:]
    assert H.main(["check"] + broken) == 2
    stop = [str(path_of("runs_junjo_tobi"))] + args[1:]
    assert H.main(["check"] + stop) == 3


def test_init_template_is_readable(tmp_path: Path) -> None:
    """ひな型 5 枚はそのまま読めて、出典の欄が全部埋まっている。"""
    written = H.init(tmp_path)
    assert len(written) == 5
    t = H.diff_tally(*[LOADERS[i](written[i]) for i in range(5)])
    assert t.report.ok, [p.as_dict() for p in t.report.pending]
    assert sum(t.six().values()) == 2 == t.pair_denominator()
