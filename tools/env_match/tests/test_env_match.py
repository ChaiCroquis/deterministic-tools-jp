"""env_match のテスト。合成 fixture は `fixtures/` に commit 済(実データ・実在の取引先名は入れない)。

test_measure_* が記事に載せた数値の出どころで、assert で固定している(値が変われば記事も変える前提)。
測っているものは 4 つある。

  (1) 宣言した 4 欄(時刻 / 絶対パス 2 つ / ホスト名)を外しておけば、環境を変えたラベルでも
      判定に入れた 8 欄が一致する側(taba_a)
  (2) 宣言表に載っていない要素(書き出しの改行)が動くと、判定に入れた 8 欄すべてで差が出る側
      (taba_b)= この記事の骨
  (3) 宣言表に無い欄が出力に在ると「宣言が無い」として数に残り、黙って外されない側(taba_c)
  (4) 判定に入れた欄が出力に無いと「判定部分が取れない」になり、不一致と混ざらない側(taba_d)

(2) の比較はテストの側でもバイト列を直に突き合わせて確かめている(部品の match は呼ばない)。
"""
from __future__ import annotations

import ast
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
import env_match as E  # noqa: E402
import make_fixtures as M  # noqa: E402

DECL = FIX / "sengen_hantei.csv"

# 宣言表・ラベル表の出典のうち、この repo 内の実在の行を指すもの -> その行に在るはずの語
REAL_SOURCES = {
    M.SRC_SOTO: "判定とは別の欄に出る",
    M.SRC_SHA: "読んだ表の絶対パス",
    M.SRC_BUNBO: "分母に含めたもの",
    M.SRC_KAGI: "鍵は宣言された列だけ",
    M.SRC_KENSUU: "データ表の行数",
    M.SRC_GYOUSUU: "同値の組に関与した行数",
    M.SRC_CI: "venv",
}


def decl(name: str = "sengen_hantei") -> E.Decl:
    return E.Decl.load(FIX / f"{name}.csv")


def labels(name: str) -> E.Labels:
    return E.Labels.load(FIX / f"label_{name}.csv")


def matched(name: str, label: str | None = None, d: str = "sengen_hantei") -> E.Matched:
    lb = labels(label or name)
    return E.match(E.Outputs.load(FIX / f"taba_{name}", lb), lb, d and decl(d))


def kowashita(name: str) -> Path:
    return FIX / "kowashita" / f"{name}.csv"


def raw(name: str, label: str) -> bytes:
    return (FIX / f"taba_{name}" / f"{label}{E.SUFFIX}").read_bytes()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inline(bundle: dict[str, list[tuple[str, str]]], decl_rows: list[list[str]],
           base: str = "既定", swap: str = "逆順",
           newline: dict[str, str] | None = None) -> E.Matched:
    """表と束を文字列から組んで突き合わせる(fixture を増やさずに 1 点だけ変えて見るため)。"""
    nl = newline or {}
    rows = [",".join(E.LABEL_COLUMNS)]
    for i, name in enumerate(bundle):
        rows.append(f"{name},合成の要素,合成の設定,合成のメモ L{i + 1},"
                    f"{base if i == 0 else ''},{swap if i == 0 else ''}")
    lb = E.Labels.parse("\n".join(rows))
    d = E.Decl.parse("\n".join([",".join(E.DECL_COLUMNS)] + [",".join(r) for r in decl_rows]))
    data = {k: (nl.get(k, "\n").join(f"{a}\t{b}" for a, b in v) + nl.get(k, "\n")).encode("utf-8")
            for k, v in bundle.items()}
    return E.match(E.Outputs.from_bytes(data, lb), lb, d)


# ---------------------------------------------------------------- 入り口

def test_committed_tables_load() -> None:
    """commit 済の宣言表とラベル表は、表として読める(止まる理由が 0 件)。"""
    d = decl()
    assert len(d.fields) == 12
    assert len(d.included) == 8 and len(d.excluded) == 4
    assert d.pending == ()
    for name in ("a", "b", "c", "d"):
        lb = labels(name)
        assert lb.pending == () and lb.base == "既定" and lb.swap == "逆順"


def test_sources_point_at_real_lines() -> None:
    """宣言表の出典のうち 7 件は、この repo 内の実在の行を指している。"""
    for src, word in REAL_SOURCES.items():
        rel, lineno = src.rsplit(" L", 1)
        line = (PLAN / rel).read_text(encoding="utf-8").splitlines()[int(lineno) - 1]
        assert word in line, f"{src} に {word} が無い: {line[:60]}"


def test_reasons_vocabulary_is_five() -> None:
    """理由の分類は 5 語で、commit 済の宣言表が使っているのはそのうち 3 語。"""
    assert len(E.REASONS) == 5
    used = {f.reason for f in decl().excluded}
    assert used == {"時刻", "絶対パス", "ホスト名"}


# ---------------------------------------------------------------- (1) 一致する側

def test_measure_declared_exclusions_match() -> None:
    """宣言した 4 欄を外しておけば、環境を変えた 2 つの対でも判定に入れた 8 欄が一致する。"""
    m = matched("a")
    c = m.counts()
    assert m.report.ok and m.verdict == "一致"
    assert c["ラベル数"] == 3 and c["突き合わせた対の数"] == 2
    assert c["4 値"] == {"一致": 8, "不一致": 0, "判定部分が取れない": 0, "宣言が無い": 0}
    assert c["判定に入れた欄数"] == 8 and c["判定から外した欄数"] == 4
    assert c["外した欄で差が出た欄数"] == 4
    assert c["外した欄の内訳"] == {"時刻": 1, "絶対パス": 2, "ホスト名": 1}
    pairs = {p["ラベル"]: p for p in m.pairs()}
    assert pairs["タイムゾーン UTC"]["判定に入れた欄で差が出た欄数"] == 0
    assert pairs["タイムゾーン UTC"]["外した欄で差が出た欄数"] == 1
    assert pairs["別の端末"]["判定に入れた欄で差が出た欄数"] == 0
    assert pairs["別の端末"]["外した欄で差が出た欄数"] == 3
    print(f"[measure] taba_a(既定 / タイムゾーン UTC / 別の端末): ラベル {c['ラベル数']} /"
          f" 対 {c['突き合わせた対の数']} / 判定に入れた欄 {c['判定に入れた欄数']} /"
          f" 外した欄 {c['判定から外した欄数']} → 4 値 {c['4 値']}")
    print(f"[measure] 外した欄で差が出た欄数 {c['外した欄で差が出た欄数']}"
          f"(タイムゾーン UTC の対で {pairs['タイムゾーン UTC']['外した欄で差が出た欄数']} /"
          f" 別の端末の対で {pairs['別の端末']['外した欄で差が出た欄数']})。"
          f"判定に入れた欄での差は両方の対で 0")
    print(f"[measure] 突き合わせた判定部分の sha256 先頭 12 桁 {m.sha256()[:12]}")


# ---------------------------------------------------------------- (2) 骨

def test_measure_newline_breaks_every_included_field() -> None:
    """宣言表に無い要素(書き出しの改行)が動くと、判定に入れた 8 欄すべてで差が出る。"""
    m = matched("b")
    c = m.counts()
    assert m.report.ok and m.verdict == "不一致"
    assert c["4 値"] == {"一致": 0, "不一致": 8, "判定部分が取れない": 0, "宣言が無い": 0}
    pair = m.pairs()[0]
    assert pair["判定に入れた欄で差が出た欄数"] == 8 and pair["外した欄で差が出た欄数"] == 4
    # テストの側でもバイト列を直に突き合わせる(部品の match は呼ばない)
    base, crlf = raw("b", "既定"), raw("b", "改行 CRLF")
    assert base != crlf
    assert crlf.replace(b"\r\n", b"\n") == base      # 寄せれば同じ = 寄せていないから違う
    assert len([x for x in crlf.split(b"\n") if x.endswith(b"\r")]) == 12
    mis = {x["欄名"]: x for x in m.mismatches()}
    assert len(mis) == 8 and mis["データ表の行数"]["基準ラベルの行番号"] == 1
    assert mis["データ表の行数"]["差が出たラベル"][0]["値"] == "12\\r"
    print(f"[measure] taba_b(既定 / 改行 CRLF): 4 値 {c['4 値']} /"
          f" 改行 CRLF の対で判定に入れた欄 {pair['判定に入れた欄で差が出た欄数']} 欄 +"
          f" 外した欄 {pair['外した欄で差が出た欄数']} 欄に差")
    print(f"[measure] CRLF の束は 12 行すべての値が復帰文字で終わる"
          f"(例: データ表の行数 = {mis['データ表の行数']['差が出たラベル'][0]['値']} /"
          f" 基準は {mis['データ表の行数']['基準ラベルの値']})。"
          f"改行を寄せれば基準とバイト列が一致するが、寄せる経路は無い")
    print(f"[measure] 判定部分の sha256 先頭 12 桁 {m.sha256()[:12]}"
          f"(一致した taba_a とは別)")


def test_normalization_has_no_path() -> None:
    """空白の詰め・数の書式の寄せ・近似一致が無い(どれも別のバイト列として残る)。"""
    rows = [["欄", "入れる", "", "合成のメモ L1"]]
    for other in ("12 ", "012", "12.0", "１２"):
        m = inline({"既定": [("欄", "12")], "別": [("欄", other)]}, rows)
        assert m.verdict == "不一致", other
    assert inline({"既定": [("欄", "12")], "別": [("欄", "12")]}, rows).verdict == "一致"


# ---------------------------------------------------------------- (3)(4) 4 値

def test_measure_undeclared_field_stays_in_the_count() -> None:
    """宣言表に無い欄は「宣言が無い」として数に残り、黙って判定から外されない。"""
    m = matched("c")
    c = m.counts()
    assert c["4 値"] == {"一致": 8, "不一致": 0, "判定部分が取れない": 0, "宣言が無い": 1}
    assert c["出力に現れた欄数"] == 13 and c["宣言表の行数"] == 12
    assert [p.reason for p in m.report.pending] == [E.STOP_REASONS[6]]
    assert m.report.ok is False
    with pytest.raises(RuntimeError):
        m.sha256()
    un = m.undeclared()
    assert len(un) == 1 and un[0]["欄名"] == "Python の版"
    assert un[0]["この欄が在ったラベル"] == ["版 3.13"]
    print(f"[measure] taba_c(既定 / 版 3.13): 出力に現れた欄 {c['出力に現れた欄数']} /"
          f" 宣言表 {c['宣言表の行数']} 行 → 4 値 {c['4 値']}。理由コード "
          f"{m.report.pending[0].reason}({un[0]['欄名']})で止まり、"
          f"判定に入れた 8 欄が一致していても結果は返らない")


def test_measure_missing_included_field_is_not_a_mismatch() -> None:
    """判定に入れた欄が出力に無いと「判定部分が取れない」になり、不一致と混ざらない。"""
    m = matched("d")
    c = m.counts()
    assert c["4 値"] == {"一致": 7, "不一致": 0, "判定部分が取れない": 1, "宣言が無い": 0}
    assert [p.reason for p in m.report.pending] == [E.STOP_REASONS[8]]
    cell = m.by_result("判定部分が取れない")[0]
    assert cell.field == "sha256" and cell.missing == ("sha256 の欄が無い版",)
    print(f"[measure] taba_d(既定 / sha256 の欄が無い版): 4 値 {c['4 値']}。"
          f"取れない 1 欄は {cell.field} で、理由コードは {m.report.pending[0].reason}"
          f"(不一致 0 と別に数える)")


def test_four_values_have_no_collapsing_argument() -> None:
    """4 値を 3 値に潰す引数が無い(by_result は 4 値のどれかでしか引けない)。"""
    assert E.RESULTS == ("一致", "不一致", "判定部分が取れない", "宣言が無い")
    m = matched("a")
    assert sum(len(m.by_result(r)) for r in E.RESULTS) == len(decl().included)
    assert m.by_result("通った") == ()


# ---------------------------------------------------------------- 分母と率

def test_rate_is_never_alone() -> None:
    """一致率を単独で返す呼び方が無い。件数には必ず分母の内訳と 2 つの固定行が付く。"""
    for name in ("a", "b", "c", "d"):
        c = matched(name).counts()
        assert "分母に含めたもの" in c and "外した欄は宣言された欄だけ" in c
        assert "差の原因は書かない" in c
        assert "率" not in "".join(k for k in c if k != "分母に含めたもの")
        four = c["4 値"]
        assert four["一致"] + four["不一致"] + four["判定部分が取れない"] == c["判定に入れた欄数"]
        assert c["判定に入れた欄数"] + c["判定から外した欄数"] == c["宣言表の行数"]


def test_pairs_do_not_assign_a_cause() -> None:
    """対ごとの差は返すが、どの環境要素のせいかは書かない。"""
    m = matched("a")
    assert "どの環境要素のせいかは書かない" in str(m.counts()["差の原因は書かない"])
    for p in m.pairs():
        assert set(p) == {"ラベル", "変えた環境要素", "設定した値", "判定に入れた欄で差が出た欄数",
                          "外した欄で差が出た欄数", "宣言が無い欄で差が出た欄数",
                          "この欄が出力に無かった"}
        assert "せい" not in str(p) and "原因" not in str(p)


# ---------------------------------------------------------------- 判定部分

def test_judgement_excludes_time_host_and_path() -> None:
    """判定部分に時刻・ホスト名・絶対パスの **値** が 1 つも入らない(欄名は宣言表の写しなので入る)。"""
    m = matched("a")
    body = m.judgement_bytes().decode("utf-8")
    for word in (m.read_at, m.host, "合成の端末A", "合成の端末B", "置き場A", "置き場B",
                 "2026-10-13T09:12:08", "2026-10-13T00:12:08"):
        assert word not in body, word
    assert "読んだ時刻	入れない" in body          # 欄名と判定だけが入る
    assert set(m.read_condition()) == set(E.READ_KEYS)
    assert m.read_condition()["読んだ時刻"] == m.read_at
    assert m.read_condition()["ホスト名"] == m.host


def test_measure_verify_two_runs_and_swapped_labels() -> None:
    """2 回突き合わせても、ラベル表の行順を入れ替えても、判定部分のバイト列が同じ。"""
    out = E.verify(FIX / "taba_a", labels("a"), decl())
    assert out["ok"] is True and out["突き合わせの結果"] == "一致"
    assert out["sha256"] == out["2 回目の sha256"] == out["入れ替えた表の sha256"]
    ng = E.verify(FIX / "taba_b", labels("b"), decl())
    assert ng["ok"] is True and ng["突き合わせの結果"] == "不一致"
    assert ng["sha256"] == ng["入れ替えた表の sha256"]
    print(f"[measure] taba_a を 2 回 + ラベル順を逆順に入れ替えて突き合わせ: "
          f"判定部分の sha256 は 3 回とも同じ {out['sha256'][:12]}(3/3 一致)")
    print(f"[measure] 不一致だった taba_b でも 2 回 + 入れ替えで sha256 は同じ"
          f" {ng['sha256'][:12]}(結果が 不一致 であることと、突き合わせが決定論であることは別)")


def test_verify_needs_a_declared_swap() -> None:
    """入れ替え方が宣言されていなければ verify は走らせない(乱数の既定を持たない)。"""
    lb = E.Labels.parse((FIX / "label_a.csv").read_text(encoding="utf-8").replace(",逆順", ","))
    assert lb.swap == ""
    with pytest.raises(E.ReadError):
        E.verify(FIX / "taba_a", lb, decl())


# ---------------------------------------------------------------- 止まる理由コード

STOP_FIXTURES = {
    E.STOP_REASONS[0]: ("a", "sengen_0gyou", None),
    E.STOP_REASONS[1]: ("a", None, "label_hitotsu"),
    E.STOP_REASONS[2]: ("a", None, "label_juufuku"),
    E.STOP_REASONS[3]: ("a", None, "label_element_kuuran"),
    E.STOP_REASONS[4]: ("a", "sengen_shutten_nashi", None),
    E.STOP_REASONS[5]: ("a", "sengen_riyuu_mitouroku", None),
    E.STOP_REASONS[6]: ("c", None, None),
    E.STOP_REASONS[7]: ("a", "sengen_shutsuryoku_ni_nai", None),
    E.STOP_REASONS[8]: ("d", None, None),
    E.STOP_REASONS[9]: ("a", None, "label_kijun_ihou"),
}


@pytest.mark.parametrize("code", list(STOP_FIXTURES))
def test_stop_reasons_from_fixtures(code: str) -> None:
    """崩した表 10 枚で、止まる理由コード 12 個のうち 10 個に道がある。"""
    bundle, d, lab = STOP_FIXTURES[code]
    base = "a" if bundle == "a" else bundle
    lb = E.Labels.load(kowashita(lab)) if lab else labels(base)
    dd = E.Decl.load(kowashita(d)) if d else decl()
    m = E.match(E.Outputs.load(FIX / f"taba_{bundle}", lb), lb, dd)
    assert m.report.ok is False
    assert code in {p.reason for p in m.report.pending}
    assert {p.reason for p in m.report.pending} <= set(E.STOP_REASONS)


def test_stop_reason_base_not_declared() -> None:
    """基準ラベルが宣言されていない表も、同じ理由コードで止まる。"""
    lb = E.Labels.load(kowashita("label_kijun_nashi"))
    m = E.match(E.Outputs.load(FIX / "taba_a", lb), lb, decl())
    assert E.STOP_REASONS[9] in {p.reason for p in m.report.pending}


def test_measure_stop_reason_second_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """2 回目だけ判定部分を変える実装に差し替えると、指紋の突合で止まる(11 個目)。"""
    real, calls = E.Matched.judgement_bytes, {"n": 0}

    def flaky(self: E.Matched) -> bytes:
        calls["n"] += 1
        return real(self) + (b"2 \xe5\x9b\x9e\xe7\x9b\xae\n" if calls["n"] == 2 else b"")

    monkeypatch.setattr(E.Matched, "judgement_bytes", flaky)
    out = E.verify(FIX / "taba_a", labels("a"), decl())
    assert out["ok"] is False
    assert E.STOP_REASONS[10] in {p["reason"] for p in out["pending"]}
    print(f"[measure] 2 回目だけ判定部分を変えた verify: 理由コード「{E.STOP_REASONS[10]}」"
          f"が返り、どちらが正しいかは決めない")


def test_measure_stop_reason_label_order(monkeypatch: pytest.MonkeyPatch) -> None:
    """ラベルの読み込み順に依存する実装に差し替えると、入れ替えた表で止まる(12 個目)。"""
    real = E.Matched.judgement_bytes

    def order_sensitive(self: E.Matched) -> bytes:
        return real(self) + "|".join(x.name for x in self.labels.items).encode("utf-8")

    monkeypatch.setattr(E.Matched, "judgement_bytes", order_sensitive)
    out = E.verify(FIX / "taba_a", labels("a"), decl())
    assert out["ok"] is False
    assert {p["reason"] for p in out["pending"]} == {E.STOP_REASONS[11]}
    print(f"[measure] ラベルの読み込み順に依存する実装に差し替えた verify: 理由コード"
          f"「{E.STOP_REASONS[11]}」が返る(入れ替えた表の sha256 "
          f"{out['入れ替えた表の sha256'][:12]})")


def test_measure_stop_reasons_all_have_a_path() -> None:
    """止まる理由コード 12 個のうち 10 個は崩した表で、残り 2 個は差し替えた実装で出した。"""
    assert len(E.STOP_REASONS) == 12
    assert len(STOP_FIXTURES) == 10
    print(f"[measure] 止まる理由コード {len(E.STOP_REASONS)} 個すべてに道がある"
          f"(崩した表 {len(STOP_FIXTURES)} 枚 + 差し替えた実装 2 本)")


@pytest.mark.parametrize("name", ["sengen_retsu_nashi", "sengen_hantei_mitouroku",
                                  "sengen_ireru_ni_riyuu", "sengen_onaji_ran"])
def test_decl_unreadable_is_exit_two(name: str) -> None:
    """語彙の外・列不足・二重宣言は理由コードにせず「表として読めない」で返す。"""
    with pytest.raises(E.ReadError):
        E.Decl.load(kowashita(name))


@pytest.mark.parametrize("name", ["label_0gyou", "label_swap_mitouroku",
                                  "label_setting_kuuran", "label_kijun_futatsu"])
def test_labels_unreadable_is_exit_two(name: str) -> None:
    with pytest.raises(E.ReadError):
        E.Labels.load(kowashita(name))


@pytest.mark.parametrize("data", [b"\xe6\xac\x84\t1\t2\n", b"\xe6\xac\x84 1\n",
                                  b"\xe6\xac\x84\t1\n\xe6\xac\x84\t2\n", b"\t1\n"])
def test_bundle_unreadable_is_exit_two(data: bytes) -> None:
    """タブが 2 個 / タブが無い / 同じ欄名が 2 行 / 欄名が空は「表として読めない」。"""
    with pytest.raises(E.ReadError):
        E.Output.parse("合成", data)


# ---------------------------------------------------------------- 持たせていないもの

def source_tree() -> ast.Module:
    return ast.parse((ROOT / "env_match.py").read_text(encoding="utf-8"))


def test_measure_no_path_to_run_anything() -> None:
    """自分で走らせる経路が無い(子プロセスも環境変数も import していない)。"""
    imported: set[str] = set()
    for n in ast.walk(source_tree()):
        if isinstance(n, ast.Import):
            imported |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            imported.add(n.module.split(".")[0])
    assert imported == {"__future__", "argparse", "csv", "datetime", "hashlib", "json",
                        "platform", "sys", "dataclasses", "pathlib"}
    body = (ROOT / "env_match.py").read_text(encoding="utf-8")
    for word in ("subprocess", "os.environ", "getenv", "popen", "system(", "shutil"):
        assert word not in body, word
    print(f"[measure] 部品が import している module は {len(imported)} 個で、"
          f"subprocess / os / 環境変数を読む呼び出しは 0 件"
          f"(走らせるのは人、この部品は突き合わせるだけ)")


def test_no_tolerance_or_normalize_arguments() -> None:
    """許容誤差・近似一致・正規化の引数が、関数にも CLI にも無い。"""
    tree = source_tree()
    code = ast.unparse(ast.Module(body=[n for n in tree.body
                                        if not (isinstance(n, ast.Expr)
                                                and isinstance(n.value, ast.Constant))],
                                  type_ignores=[]))
    for word in ("tolerance", "atol", "rtol", "normalize", "casefold", "NFKC",
                 "unicodedata", "round("):
        assert word not in code, word
    args: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args |= {a.arg for a in n.args.args + n.args.kwonlyargs}
        if isinstance(n, ast.Call):
            args |= {k.arg or "" for k in n.keywords}
    assert not args & {"tolerance", "atol", "rtol", "normalize", "strict", "fuzzy"}


def test_cli_is_four_positional_subcommands() -> None:
    """CLI は 4 つの下位コマンドで、option は -h 以外に 1 つも無い。"""
    ap = E.build_parser()
    choices = [a for a in ap._actions if hasattr(a, "choices") and a.choices][0].choices
    assert tuple(choices) == E.SUBCOMMANDS
    for name in E.SUBCOMMANDS:
        for a in choices[name]._actions:
            assert a.dest == "help" or not a.option_strings, (name, a.dest)


def test_no_path_to_write_the_inputs() -> None:
    """突き合わせの前後で、束 9 ファイルと表 5 枚の sha256 が変わらない。"""
    files = sorted(FIX.glob("*.csv")) + sorted(FIX.glob("taba_*/*.tsv"))
    assert len(files) == 14
    before = {p: digest(p) for p in files}
    for name in ("a", "b", "c", "d"):
        m = matched(name)
        m.counts(), m.pairs()
        if m.report.ok:
            m.sha256()
    after = {p: digest(p) for p in files}
    assert before == after
    print(f"[measure] 突き合わせの前後で入力 {len(files)} ファイルの sha256 が同じ"
          f"(束 {len(files) - 5} + 表 5 を 1 文字も書き換えていない)")


def test_stopped_match_has_no_result() -> None:
    """止まったときは結果も指紋も取りに行けない(一部だけ返す経路が無い)。"""
    lb = E.Labels.load(kowashita("label_hitotsu"))
    m = E.match(E.Outputs.load(FIX / "taba_a", lb), lb, decl())
    assert m.cells == ()
    assert "突き合わせていない" in str(m.counts()["突き合わせたか"])
    for call in (lambda: m.verdict, m.judgement_bytes, m.sha256):
        with pytest.raises(RuntimeError):
            call()


def test_current_environment_is_not_a_default_label() -> None:
    """今の環境は既定のラベルとして混ざらない(基準は宣言から取る)。"""
    import platform
    m = matched("a")
    assert platform.node() not in m.labels.names
    assert m.labels.base == "既定" and m.labels.base in m.labels.names
    body = (ROOT / "env_match.py").read_text(encoding="utf-8")
    assert body.count("platform.node()") == 1      # 読んだ条件の 1 か所だけ


def test_inline_bundle_helper_matches_fixture_behaviour() -> None:
    """文字列から組んだ束でも、fixture と同じ 4 値の分け方になる。"""
    rows = [["欄1", "入れる", "", "合成のメモ L1"], ["時刻", "入れない", "時刻", "合成のメモ L2"]]
    m = inline({"既定": [("欄1", "12"), ("時刻", "09:12")],
                "別": [("欄1", "12"), ("時刻", "00:12")]}, rows)
    assert m.verdict == "一致" and m.counts()["外した欄で差が出た欄数"] == 1
    crlf = inline({"既定": [("欄1", "12")], "別": [("欄1", "12")]},
                  [["欄1", "入れる", "", "合成のメモ L1"]], newline={"別": "\r\n"})
    assert crlf.verdict == "不一致"
