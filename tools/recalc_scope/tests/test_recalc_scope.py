"""recalc_scope のテスト。合成 fixture は `fixtures/` に commit 済(実データ・実在の値は入れない)。

test_measure_* が記事に載せた数値の出どころで、assert で固定している(値が変われば記事も変える前提)。
測っているものは 5 つある。

  (1) 結果 12 行が 4 値に分かれ、決まらない理由別の件数と分母の内訳が付く側(kekka_a)
  (2) 差分台帳の「見本だけ」を「全件」に書き換えると、その区間を跨ぐ 2 行だけが決まらないから
      出る側(sabun_zenken)= この記事の骨
  (3) 同じキーを引いた結果が、引いた版だけの違いで 影響あり / 影響なし に分かれる側
  (4) 日付(版の日付・出した日)を書き換えても判定部分の指紋が 1 桁も動かない側
  (5) 4 値の件数の合計 = 結果台帳の行数 が合う側

(1) の 4 値は、テストの側でも台帳から直に組み立てて確かめている(部品の判定は呼ばず、
fixture の行と鎖から別に計算する)。
"""
from __future__ import annotations

import ast
import hashlib
import re
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
import recalc_scope as R  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの -> その行に在るはずの語
REAL_SOURCES = {
    M.SRC_SENGEN: "行の側に列として宣言させる",
    M.SRC_TOMERU: "理由コードで止めて",
    M.SRC_DAICHOU: "台帳 1 行にする",
    M.SRC_KUSARI: "そのまま次の行に繋がる",
    M.SRC_KARIOKI: "仮置きだと塊の中に書く",
}

# 形容の語(出力にも実装にも持たせない = 数値が無いなら多寡を書かない)
KEIYOU = ("多い", "少ない", "ほとんど", "かなり", "著しく", "急いで")


def path_of(name: str) -> Path:
    return FIX / "kowashita" / f"{name[2:]}.csv" if name.startswith("K:") \
        else FIX / f"{name}.csv"


def pull(k: str = "kekka_a", h: str = "han_a", s: str = "sabun_a") -> R.Table:
    return R.scope(R.Ledger.load(path_of(k)), R.Versions.load(path_of(h)),
                   R.Diffs.load(path_of(s)))


def row_of(t: R.Table, result_id: str) -> R.Scope:
    return next(s for s in t.scopes if s.row.result_id == result_id)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def every_fixture() -> list[Path]:
    return sorted(p for p in FIX.rglob("*.csv"))


def expect_four(kekka: list[list[str]], han: list[list[str]],
                sabun: list[list[str]]) -> dict[str, int]:
    """4 値を、台帳の行から直に組み立てる(部品の判定には頼らない)。"""
    parent = {r[0]: r[2] for r in han[1:]}
    # 鎖(古い → 新しい)を親子だけで組む。日付は見ない
    used = {p for p in parent.values() if p in parent}
    head = next(v for v in parent if v not in used)
    chain: list[str] = []
    cur = head
    while True:
        chain.append(cur)
        if parent[cur] not in parent:
            break
        cur = parent[cur]
    chain.reverse()
    out = dict.fromkeys(R.RESULTS, 0)
    for _rid, _t, _i, version, keys, _issued, _src, _swap in kekka[1:]:
        i = chain.index(version)
        steps = [(chain[k], chain[k + 1]) for k in range(i, len(chain) - 1)]
        mine = {x for x in keys.split(R.KEY_SEP) if x}
        rows = [[d for d in sabun[1:] if (d[0], d[1]) == st] for st in steps]
        if not mine:
            out[R.RESULTS[2]] += 1
        elif any(not g for g in rows):
            out[R.RESULTS[2]] += 1
        elif any(d[4] == R.COVERAGES[1] for g in rows for d in g):
            out[R.RESULTS[2]] += 1
        else:
            changed = {x for g in rows for d in g
                       for x in d[2].split(R.KEY_SEP) if x}
            out[R.RESULTS[0] if mine & changed else R.RESULTS[1]] += 1
    return out


# ---------------------------------------------------------------- 入り口

def test_committed_tables_load() -> None:
    """commit 済の表は、表として読める(止まる理由が 0 件)。"""
    assert len(R.Ledger.load(FIX / "kekka_a.csv").items) == 12
    assert R.Ledger.load(FIX / "kekka_a.csv").swap == "逆順"
    assert len(R.Versions.load(FIX / "han_a.csv").items) == 5
    assert len(R.Diffs.load(FIX / "sabun_a.csv").items) == 4
    for name in ("kekka_a", "kekka_hizuke"):
        assert R.Ledger.load(FIX / f"{name}.csv").pending == (), name
    for name in ("han_a", "han_hizuke"):
        assert R.Versions.load(FIX / f"{name}.csv").pending == (), name
    for name in ("sabun_a", "sabun_zenken"):
        assert R.Diffs.load(FIX / f"{name}.csv").pending == (), name


def test_sources_point_at_real_lines() -> None:
    """出典のうち 5 件は、この repo 内の実在の行を指している。"""
    for src, word in REAL_SOURCES.items():
        rel, lineno = src.rsplit(" L", 1)
        line = (PLAN / rel).read_text(encoding="utf-8").splitlines()[int(lineno) - 1]
        assert word in line, f"{src} に {word} が無い: {line[:60]}"


def test_registered_vocabularies() -> None:
    """登録の語彙は固定(変更種別 3 / 覆いの宣言 2 / 4 値 4 / 決まらない 3 / 理由コード 9)。"""
    assert R.CHANGES == ("追加", "削除", "変更")
    assert R.COVERAGES == ("全件", "見本だけ")
    assert R.RESULTS == ("影響あり", "影響なし", "決まらない", "止まった")
    assert R.UNDECIDED == ("見本だけ", "キー無し", "鎖が切れている")
    assert len(R.STOP_REASONS) == 9
    assert R.SUBCOMMANDS == ("scope", "check", "verify", "init")


def test_measure_the_chain_is_built_from_fingerprints_only() -> None:
    """鎖は前の版の指紋だけで組む(日付の列は 1 度も見ない)。"""
    t = pull()
    assert t.chain is not None
    assert t.chain.order == (M.V1, M.V2, M.V3, M.V4, M.V5)
    assert t.chain.newest == M.V5
    assert len(t.chain.steps(M.V1)) == 4 and len(t.chain.steps(M.V5)) == 0
    src = (ROOT / "recalc_scope.py").read_text(encoding="utf-8")
    body = src[src.index("def chain_of"):src.index("# ---", src.index("def chain_of"))]
    assert "date" not in body            # 鎖を組む関数は日付の欄に触っていない
    print("[measure] 版の鎖は 5 段(指紋の親子だけで組む。鎖を組む関数は日付の欄を"
          "1 度も読まない)")


# ---------------------------------------------------------------- (1) 範囲を出す側

def test_measure_twelve_results_split_into_four() -> None:
    """結果 12 行が、影響あり 3 / 影響なし 4 / 決まらない 5 / 止まった 0 に分かれる。"""
    t = pull()
    c = t.counts()
    assert t.report.ok
    assert c["結果の台帳の行数"] == 12 and c["版の台帳の行数"] == 5
    assert c["差分の台帳の行数"] == 4 and c["版の鎖の段数"] == 5
    assert c["4 値"] == {"影響あり": 3, "影響なし": 4, "決まらない": 5, "止まった": 0}
    assert c["4 値"] == expect_four(M.KEKKA_A, M.HAN_A, M.SABUN_A)
    assert c["出し直す対象"] == 3
    print(f"[measure] kekka_a / han_a / sabun_a: 結果 12 行 → 4 値 {c['4 値']}")


def test_measure_undecided_counts_by_reason_with_a_denominator() -> None:
    """決まらない 5 件は 3 つの理由に分かれる。率は単独では返らない。"""
    t = pull()
    c = t.counts()
    assert c["決まらない理由別"] == {"見本だけ": 2, "キー無し": 2, "鎖が切れている": 1}
    assert sum(c["決まらない理由別"].values()) == 5
    assert "4 値の合計 12 / 結果の台帳の行数 12" in str(c["件数の合計の検算"])
    assert "結果の台帳の行数 12 行" in str(c["分母に含めたもの"])
    print("[measure] 決まらない 5 件の内訳 = 見本だけ 2 / キー無し 2 / 鎖が切れている 1"
          "(分母は結果の台帳の行数 12。率は単独では返らない)")


def test_measure_the_interval_is_counted_in_steps() -> None:
    """区間は段数で数える(いちばん古い版の結果は 4 段、新しい版の結果は 0 段)。"""
    t = pull()
    assert row_of(t, "R07").steps == 4
    assert row_of(t, "R01").steps == 2
    assert row_of(t, "R03").steps == 1
    assert row_of(t, "R05").steps == 0
    assert row_of(t, "R05").result == "影響なし"      # 区間が 0 段なら何も変わっていない
    print("[measure] 区間の段数は R07 が 4 段 / R01 が 2 段 / R03 が 1 段 / "
          "R05 が 0 段(0 段は 影響なし)")


def test_no_order_and_no_recommendation() -> None:
    """出し直す対象に順番を付けない(返るのは結果 id の順)。"""
    t = pull()
    ids = [x["結果 id"] for x in t.targets()]
    assert ids == sorted(ids) == ["R01", "R03", "R09"]
    # 出力のどこにも順位の欄が無く、勧める語も入らない
    body = str(t.counts()) + str(t.table()) + str(t.targets())
    for word in ("順位", "優先", "おすすめ", "推奨", "先にやる"):
        assert word not in body, word
    for row in t.targets():
        assert set(row) == {"結果 id", "対象", "項目", "引いた版", "当たったキー"}


# ---------------------------------------------------------------- (2) 見本だけ → 全件

def test_measure_one_coverage_cell_moves_two_results() -> None:
    """差分台帳の 1 欄(見本だけ → 全件)で、その区間を跨ぐ 2 行だけが決まらないから出る。"""
    base = pull()
    zen = pull(s="sabun_zenken")
    assert zen.report.ok
    assert zen.counts()["4 値"] == {"影響あり": 4, "影響なし": 5, "決まらない": 3,
                                    "止まった": 0}
    assert zen.counts()["4 値"] == expect_four(M.KEKKA_A, M.HAN_A, M.SABUN_ZENKEN)
    assert zen.counts()["決まらない理由別"] == {"キー無し": 2, "鎖が切れている": 1}
    assert row_of(base, "R06").why == "見本だけ" and row_of(zen, "R06").result == "影響あり"
    assert row_of(base, "R11").why == "見本だけ" and row_of(zen, "R11").result == "影響なし"
    # 動いたのはこの 2 行だけで、ほかの 10 行の結果は同じ
    moved = {"R06", "R11"}
    other = {s.row.result_id: s.result for s in base.scopes
             if s.row.result_id not in moved}
    assert {s.row.result_id: s.result for s in zen.scopes
            if s.row.result_id not in moved} == other
    assert len(other) == 10
    print("[measure] 差分台帳の 1 欄 見本だけ → 全件: 決まらない 5 → 3。"
          "R06 は 影響あり、R11 は 影響なし に分かれ、ほかの 10 行は不変")


def test_measure_sampled_span_is_not_filled_in() -> None:
    """見本だけの区間は、見本のキーで当て直さない(キーが載っていても決まらない)。"""
    base = pull()
    assert row_of(base, "R06").row.keys == (M.K_A,)
    assert row_of(base, "R06").hit == ()            # 見本のキーと突き合わせない
    assert row_of(base, "R06").compared == 0
    src = (ROOT / "recalc_scope.py").read_text(encoding="utf-8")
    for word in ("推定", "補完", "ffill", "fillna", "sample_to_all"):
        assert word not in src or word == "推定", word
    print("[measure] 見本だけの区間を跨ぐ R06 は、突き合わせたキー 0 件のまま決まらない"
          "(見本から全件を補う経路が無い)")


def test_measure_broken_chain_is_not_bridged() -> None:
    """区間の差分が台帳に無いとき、間を推定で繋がない(鎖が切れている)。"""
    t = pull()
    assert row_of(t, "R07").why == "鎖が切れている"
    assert row_of(t, "R07").steps == 4
    assert t.diffs.of_step((M.V1, M.V2)) == ()      # この区間の宣言が無い
    assert len(t.diffs.of_step((M.V3, M.V4))) == 2  # 1 区間に変更種別 2 行
    print("[measure] V1 → V2 の区間は差分台帳に無く、そこを跨ぐ R07 は 鎖が切れている。"
          "V3 → V4 は変更種別が 2 行(追加と変更を 1 行に丸めない)")


# ---------------------------------------------------------------- (3) 版で分かれる

def test_measure_the_same_key_splits_by_the_version_it_was_drawn_at() -> None:
    """同じキーを引いた 2 つの結果が、引いた版だけの違いで 影響あり / 影響なし に分かれる。"""
    t = pull()
    old, new = row_of(t, "R01"), row_of(t, "R04")
    assert old.row.keys == new.row.keys == (M.K_A,)
    assert old.row.version == M.V3 and new.row.version == M.V4
    assert old.result == "影響あり" and new.result == "影響なし"
    assert old.compared == 4 and new.compared == 1
    print("[measure] 同じキーを引いた R01(版 c5d2e9f4)と R04(版 d9e4f1a8): "
          "突き合わせたキーは 4 件と 1 件で、影響あり と 影響なし に分かれる")


def test_measure_empty_keys_are_not_pushed_to_no_impact() -> None:
    """キーが空の結果を「影響なし」に寄せない(区間が 0 段でも決まらない)。"""
    t = pull()
    assert row_of(t, "R08").why == "キー無し" and row_of(t, "R08").steps == 2
    assert row_of(t, "R10").why == "キー無し" and row_of(t, "R10").steps == 0
    assert row_of(t, "R05").result == "影響なし"    # 同じ 0 段でもキーが在れば決まる
    print("[measure] キーが空の R08(2 段)と R10(0 段)は どちらも キー無し。"
          "区間が同じ 0 段でもキーが在る R05 は 影響なし")


def test_stopped_on_an_empty_or_unknown_fingerprint() -> None:
    """指紋が空の版も、版台帳に無い指紋も、1 行も読まずに止まる。"""
    kara = pull(k="K:kekka_han_kuuran")
    assert {p.reason for p in kara.report.pending} == {"指紋が空の版を参照"}
    assert kara.counts()["読んだか"].startswith("読んでいない")
    soto = pull(k="K:kekka_mitouroku_han")
    assert {p.reason for p in soto.report.pending} == {"版の指紋が版台帳に無い"}


def test_measure_two_dates_on_one_fingerprint_stop() -> None:
    """同じ指紋に別の日付が 2 行あると、日付で版を指せないので止まる。"""
    t = pull(h="K:han_hizuke_futatsu")
    assert {p.reason for p in t.report.pending} == {"同じ指紋に別の日付が 2 つ"}
    assert t.counts()["読んだか"].startswith("読んでいない")
    print("[measure] 同じ指紋に 2 つの日付を書いた版台帳 → 同じ指紋に別の日付が 2 つ "
          "で止まる(1 行も読まない)")


# ---------------------------------------------------------------- (4) 日付を入れない

def test_measure_dates_do_not_move_the_fingerprint() -> None:
    """版の日付と出した日を書き換えても、判定部分の指紋は 1 桁も動かない。"""
    got = {
        "kekka_a + han_a + sabun_a": pull().sha256()[:12],
        "出した日をずらした表": pull(k="kekka_hizuke").sha256()[:12],
        "版の日付をずらした表": pull(h="han_hizuke").sha256()[:12],
        "見本だけ → 全件": pull(s="sabun_zenken").sha256()[:12],
    }
    assert got == {"kekka_a + han_a + sabun_a": "4bd7347135db",
                   "出した日をずらした表": "4bd7347135db",
                   "版の日付をずらした表": "4bd7347135db",
                   "見本だけ → 全件": "16778ec7e413"}
    print("[measure] 判定部分の sha256 先頭 12 桁 kekka_a 4bd7347135db / "
          "出した日をずらした表 4bd7347135db(不変)/ 版の日付をずらした表 "
          "4bd7347135db(不変)/ 見本だけ → 全件 16778ec7e413")


def test_judgement_has_no_time_host_path_or_date() -> None:
    """判定部分に時刻・ホスト名・絶対パス・日付が入らない。"""
    t = pull()
    body = t.judgement_bytes().decode("utf-8")
    for word in (t.read_at, t.host, "fixtures", ":\\", "読んだ時刻", "2026-"):
        assert word not in body, word
    assert set(t.read_condition()) == set(R.SCOPE_KEYS)


def test_no_recalculation_arguments() -> None:
    """値を計算し直す引数も、他の道具を呼ぶ経路も、順番を付ける引数も無い。"""
    src = (ROOT / "recalc_scope.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "add_argument":
            for a in node.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    names.add(a.value)
    assert names == {"ledger", "versions", "diffs", "dest"}
    for word in ("compute", "recalc(", "as_of", "基準日", "按分", "import subprocess"):
        assert word not in src, word


def test_no_adjectives_in_the_output() -> None:
    """形容の語を実装にも出力にも持たない(件数が無いなら多寡を書かない)。"""
    src = (ROOT / "recalc_scope.py").read_text(encoding="utf-8")
    t = pull()
    body = str(t.counts()) + str(t.table()) + str(
        R.verify(R.Ledger.load(FIX / "kekka_a.csv"), R.Versions.load(FIX / "han_a.csv"),
                 R.Diffs.load(FIX / "sabun_a.csv")))
    for word in KEIYOU:
        assert word not in src, word
        assert word not in body, word


# ---------------------------------------------------------------- (5) 混ぜない・検算

def test_all_nine_stop_reasons_are_covered(monkeypatch: pytest.MonkeyPatch) -> None:
    """止まる理由コード 9 個すべてに道がある(崩した表 10 枚 + 差し替えた実装 1 本)。"""
    seen: set[str] = set()
    for k in ("K:kekka_shutten_nashi", "K:kekka_mitouroku_han", "K:kekka_han_kuuran",
              "K:kekka_juufuku"):
        seen |= {p.reason for p in pull(k=k).report.pending}
    for h in ("K:han_shutten_nashi", "K:han_hizuke_futatsu"):
        seen |= {p.reason for p in pull(h=h).report.pending}
    for s in ("K:sabun_shutten_nashi", "K:sabun_hani_kuuran", "K:sabun_shubetsu_gai",
              "K:sabun_shubetsu_kuuran"):
        seen |= {p.reason for p in pull(s=s).report.pending}
    assert len(seen) == 7
    # 2 回目の判定部分が不一致 / 行順を入れ替えた表で出力が変わる(毎回違うバイト列を返す)
    ledger = R.Ledger.load(FIX / "kekka_a.csv")
    versions = R.Versions.load(FIX / "han_a.csv")
    diffs = R.Diffs.load(FIX / "sabun_a.csv")
    assert R.verify(ledger, versions, diffs)["ok"] is True
    real_bytes, box = R.Table.judgement_bytes, {"n": 0}

    def drifting(self: R.Table) -> bytes:
        box["n"] += 1
        return real_bytes(self) + str(box["n"]).encode("utf-8")

    monkeypatch.setattr(R.Table, "judgement_bytes", drifting)
    bad = R.verify(ledger, versions, diffs)
    seen |= {p["reason"] for p in bad["pending"]}        # type: ignore[index,union-attr]
    assert seen == set(R.STOP_REASONS), sorted(set(R.STOP_REASONS) - seen)
    print(f"[measure] 止まる理由コード {len(R.STOP_REASONS)} 個すべてに道がある"
          "(崩した表 10 枚 + 差し替えた実装 1 本)")


def test_measure_read_error_count() -> None:
    """「表として読めない」で返す崩した表は 26 枚(理由コードには混ぜない)。"""
    n = 0
    for p in sorted((FIX / "kowashita").glob("*.csv")):
        loader = (R.Ledger.load if p.name.startswith("kekka") else
                  R.Versions.load if p.name.startswith("han") else R.Diffs.load)
        try:
            loader(p)
        except R.ReadError:
            n += 1
    # 鎖が 1 本に決まらない 3 枚は、読み込みではなく鎖を組むところで返る
    for h in ("K:han_atama_futatsu", "K:han_atama_nashi", "K:han_hanarete"):
        with pytest.raises(R.ReadError):
            pull(h=h)
        n += 1
    assert n == 26
    print(f"[measure] 「表として読めない」で返す崩した表 {n} 枚"
          "(うち 3 枚は鎖が 1 本に決まらない表)。理由コードには混ぜない")


def test_measure_duplicate_result_id_breaks_the_denominator() -> None:
    """結果 id が 2 行あると、件数を結果 1 件ずつに割り当てられないので止まる。"""
    t = pull(k="K:kekka_juufuku")
    assert {p.reason for p in t.report.pending} == {"件数の合計が合わない"}
    assert t.counts()["結果の台帳の行数"] == 13
    assert t.counts()["4 値"] == {"影響あり": 0, "影響なし": 0, "決まらない": 0,
                                  "止まった": 0}
    print("[measure] 同じ結果 id を 2 行書いた台帳 → 件数の合計が合わない で止まる"
          "(13 行のまま 1 行も読まない)")


def test_measure_verify_is_deterministic() -> None:
    """2 回読んだ指紋と、行順を入れ替えた指紋が、3 回とも同じになる。"""
    for s, want in (("sabun_a", "4bd7347135db"), ("sabun_zenken", "16778ec7e413")):
        out = R.verify(R.Ledger.load(FIX / "kekka_a.csv"),
                       R.Versions.load(FIX / "han_a.csv"),
                       R.Diffs.load(FIX / f"{s}.csv"))
        assert out["ok"] is True
        assert out["sha256"] == out["2 回目の sha256"] == out["入れ替えた表の sha256"]
        assert str(out["sha256"])[:12] == want
        assert out["件数の検算"]["4 値の合計"] == 12        # type: ignore[index]
        print(f"[measure] {s} を 2 回 + 結果の台帳の行順を逆順に入れ替えて読み直し: "
              f"判定部分の sha256 は 3 回とも同じ {want}(3/3 一致)")


def test_row_order_of_the_ledger_does_not_matter() -> None:
    """結果の台帳の行順を入れ替えても、判定部分のバイト列が変わらない。"""
    base = pull()
    ledger = R.Ledger.load(FIX / "kekka_a.csv")
    for how in R.SWAPS:
        again = R.scope(ledger.swapped(how), R.Versions.load(FIX / "han_a.csv"),
                        R.Diffs.load(FIX / "sabun_a.csv"))
        assert again.judgement_bytes() == base.judgement_bytes(), how


def test_measure_inputs_are_not_modified() -> None:
    """読む前後で入力 CSV の sha256 が変わらない(キーも指紋も生成しない)。"""
    before = {p: digest(p) for p in every_fixture()}
    assert len(before) == 42
    for s in ("sabun_a", "sabun_zenken"):
        pull(s=s)
    R.verify(R.Ledger.load(FIX / "kekka_a.csv"), R.Versions.load(FIX / "han_a.csv"),
             R.Diffs.load(FIX / "sabun_a.csv"))
    assert {p: digest(p) for p in every_fixture()} == before
    print(f"[measure] 読む前後で入力 {len(before)} ファイルの sha256 が同じ")


def test_measure_fixtures_are_deterministic(tmp_path: Path) -> None:
    """合成 fixture は生成器から決定論的に出る(ディスク上の CSV と 1 バイト違わない)。"""
    made = M.write_all(tmp_path)
    assert len(made) == 42
    for p in made:
        here = FIX / p.relative_to(tmp_path)
        assert here.read_bytes() == p.read_bytes(), here.name


def test_measure_no_float_no_subprocess() -> None:
    """float も subprocess も random も使っていない(値を 1 つも持たない)。"""
    src = (ROOT / "recalc_scope.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    mods: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split(".")[0])
    assert mods & {"subprocess", "os", "random", "requests"} == set()
    assert "float(" not in src
    assert not re.search(r"(?<![\w.])\d+\.\d+(?![\w.])", src)   # 小数の literal も無い
    print(f"[measure] 部品が import している module は {len(mods)} 個で、"
          f"subprocess / os / random は 0 件")


# ---------------------------------------------------------------- CLI

def test_cli_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """決まらない行が無いときだけ 0、あれば 3、読めなければ 2。"""
    def run(*names: str) -> int:
        return R.main([names[0], *[str(path_of(n)) for n in names[1:]]])

    assert run("check", "kekka_a", "han_a", "sabun_a") == 3        # 決まらない 5 件
    assert run("scope", "kekka_a", "han_a", "sabun_zenken") == 3   # 決まらない 3 件
    assert run("verify", "kekka_a", "han_a", "sabun_a") == 0
    assert run("check", "K:kekka_juufuku", "han_a", "sabun_a") == 3
    assert run("check", "K:kekka_id_kuuran", "han_a", "sabun_a") == 2
    assert run("check", "kekka_a", "K:han_atama_futatsu", "sabun_a") == 2
    assert R.main(["init", str(tmp_path / "ひな型")]) == 0
    capsys.readouterr()
    for name in ("結果の台帳.csv", "版の台帳.csv", "差分の台帳.csv"):
        assert (tmp_path / "ひな型" / name).exists()
    made = R.scope(R.Ledger.load(tmp_path / "ひな型" / "結果の台帳.csv"),
                   R.Versions.load(tmp_path / "ひな型" / "版の台帳.csv"),
                   R.Diffs.load(tmp_path / "ひな型" / "差分の台帳.csv"))
    assert made.report.ok and made.verdict == "影響あり"


def test_stopped_table_has_no_result() -> None:
    """止まっているときは結果も指紋も取れない(例外になる)。"""
    t = pull(k="K:kekka_han_kuuran")
    for call in (lambda: t.verdict, t.judgement_bytes, t.sha256):
        with pytest.raises(RuntimeError):
            call()
    assert t.counts()["読んだか"].startswith("読んでいない")
    assert t.counts()["4 値"]["止まった"] == 0        # 1 行も読んでいない
