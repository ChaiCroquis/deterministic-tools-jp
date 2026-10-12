"""order_table のテスト。合成 fixture は `fixtures/` に commit 済(実データ・実在の取引先名は入れない)。

test_measure_* が記事に載せた数値の出どころで、assert で固定している(値が変われば記事も変える前提)。
測っているものは 4 つある。

  (1) 密な鍵(支給日 → 区分 → 社員番号)で順が一意に決まる側と、粗い鍵(支給日 → 区分)で
      同値の組が残って止まる側
  (2) 同じ列を 整数 と宣言した場合と コードポイント列 と宣言した場合で、出力のバイト列が違うこと
      (= 値の種類の宣言が並び順そのものを決めている)
  (3) 宣言された鍵で順が一意に決まるなら、入力表の行順を入れ替えても出力が同じバイト列になること
  (4) **並べ方を宣言しない安定ソート**(テストの側に書いた naive 実装)は、同じ中身でも入力の
      行順で出力のバイト列が変わること = この記事の骨

(4) の naive 実装は部品の関数を呼ばずにテストの中に別に書いてある。
"""
from __future__ import annotations

import ast
import dataclasses
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
import order_table as O  # noqa: E402

DATA = FIX / "data_shikyuu.csv"

# 宣言表の出典のうち、この repo 内の実在の行を指すもの -> その行に在るはずの語
REAL_SOURCES = {
    M.SRC_HIDUKE: "引く日付がルールごとに違う",
    M.SRC_KUBUN: "同じ鍵の行が 2 つあると",
    M.SRC_SHAIN: "列の順と見出しは固定",
    M.SRC_KINGAKU: "バイト列の一致でだけ束ねる",
}


@pytest.fixture(scope="session")
def table() -> O.Table:
    return O.Table.load(DATA)


def order(name: str) -> O.Order:
    return O.Order.load(FIX / f"{name}.csv")


def sorted_with(name: str, data: Path = DATA) -> O.Sorted:
    return O.sort_table(O.Table.load(data), order(name))


def naive_stable(table: O.Table) -> tuple[int, ...]:
    """**並べ方を宣言しない** 側の実装。粗い鍵だけで安定ソートする(部品の関数は呼ばない)。"""
    h, k = table.header.index("支給日"), table.header.index("区分")
    return tuple(sorted(range(len(table.rows)),
                        key=lambda i: (table.rows[i][h], table.rows[i][k])))


def build_sub_actions() -> list[object]:
    """下位コマンドごとに登録されている引数(位置引数だけであることを見るため)。"""
    out = []
    for sub in build_subparsers():
        out += [a for a in sub._actions if a.dest != "help"]
    return out


def build_subparsers() -> list[object]:
    ap = O.build_parser()
    choices = [a for a in ap._actions if hasattr(a, "choices") and a.choices][0].choices
    return [choices[name] for name in O.SUBCOMMANDS]


def digest(table: O.Table, index: tuple[int, ...]) -> str:
    return hashlib.sha256(table.csv_text(index).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- 入り口

def test_committed_tables_load(table: O.Table) -> None:
    """commit 済のデータ表と宣言表は、表として読める(止まる理由が 0 件)。"""
    o = order("sengen_mitsu")
    assert len(table.rows) == 12 and len(table.header) == 6
    assert o.pending == ()
    assert [k.column for k in o.keys] == ["支給日", "区分", "社員番号"]
    assert [k.kind for k in o.keys] == ["日付", "宣言された列挙", "整数"]
    assert all(k.source for k in o.keys)
    assert o.choices["区分"].values == ("甲", "乙", "丙")
    assert o.swap == "逆順"


def test_sources_point_at_real_lines() -> None:
    """repo 内の行を指す出典は、その行に宣言の語が実際に在る(開いて突き合わせる)。"""
    for src, word in REAL_SOURCES.items():
        rel, _, lineno = src.rpartition(" L")
        lines = (PLAN / rel).read_text(encoding="utf-8-sig").splitlines()
        assert word in lines[int(lineno) - 1], src


def test_registries_are_closed() -> None:
    """語彙は閉じている。理由コードは 11 個、入れ替え方は 3 通り。"""
    assert O.KINDS == ("コードポイント列", "整数", "Decimal", "日付", "宣言された列挙")
    assert O.DIRECTIONS == ("昇順", "降順") and O.MISSING_PLACES == ("先", "後")
    assert len(O.SWAPS) == 3 and len(O.STOP_REASONS) == 11
    assert len(set(O.STOP_REASONS)) == 11


def test_cli_has_no_options() -> None:
    """CLI は sort / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    tree = ast.parse((ROOT / "order_table.py").read_text(encoding="utf-8"))
    flags = [a.value for n in ast.walk(tree) if isinstance(n, ast.Call)
             and getattr(n.func, "attr", "") == "add_argument"
             for a in n.args if isinstance(a, ast.Constant)]
    assert sorted(set(flags)) == ["data", "dest", "order"]   # 位置引数だけ
    assert not [f for f in flags if f.startswith("-")]       # - で始まる名前が 1 つも無い
    assert O.SUBCOMMANDS == ("sort", "check", "verify", "init")
    assert [n.dest for n in build_sub_actions()] == ["data", "order"] * 3 + ["dest"]


def test_no_locale_no_random_no_tolerance() -> None:
    """ロケール依存の照合順・乱数の既定・許容誤差の引数を、ソースのどこにも持たない。"""
    src = (ROOT / "order_table.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)
                for a in n.names}
    imported |= {n.module.split(".")[0] for n in ast.walk(tree)
                 if isinstance(n, ast.ImportFrom) and n.module}
    assert not imported & {"locale", "unicodedata", "random", "secrets"}
    names = {a.arg for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
             for a in (*n.args.posonlyargs, *n.args.args, *n.args.kwonlyargs)}
    assert not {x for x in names if any(w in x for w in ("tol", "approx", "eps", "fuzzy"))}
    # 「許容誤差」「近似一致」「NFKC」「ロケール」は docstring の「持たない」宣言にしか出てこない
    docs = "".join(ast.get_docstring(n) or "" for n in ast.walk(tree)
                   if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef)))
    for word in ("許容", "近似", "NFKC", "ロケール"):
        assert src.count(word) == docs.count(word) >= 1
    for word in ("casefold", "str.lower", "strcoll", "collator"):
        assert word not in src


def test_missing_column_is_not_a_reason_code() -> None:
    """列が足りない宣言表は理由コードにせず、表として読めないことにする(終了コード 2)。"""
    with pytest.raises(O.ReadError):
        order("kowashita/sengen_retsu_nashi")
    assert O.main(["check", str(DATA), str(FIX / "kowashita/sengen_retsu_nashi.csv")]) == 2


# ---------------------------------------------------------------- (1) 密な鍵と粗い鍵

def test_measure_dense_key_is_unique() -> None:
    s = sorted_with("sengen_mitsu")
    c = s.counts()
    assert s.report.ok
    assert (c["データ表の行数"], c["鍵の組数"]) == (12, 12)
    assert (c["同値の組の件数"], c["同値の組に関与した行数"]) == (0, 0)
    assert c["順が一意に決まった行数"] == 12
    print(f"[measure] 密な鍵(支給日 → 区分 → 社員番号): データ表 {c['データ表の行数']} 行 /"
          f" 鍵の組数 {c['鍵の組数']} / 同値の組 {c['同値の組の件数']} 組"
          f" → 順が一意に決まった行数 {c['順が一意に決まった行数']}")
    print(f"[measure] 並べた判定部分の sha256 先頭 12 桁 {s.sha256()[:12]}")


def test_measure_coarse_key_stops() -> None:
    s = sorted_with("sengen_sokaku")
    c = s.counts()
    assert s.report.ok is False
    assert [p.reason for p in s.report.pending] == [O.STOP_REASONS[8]]
    assert (c["鍵の組数"], c["同値の組の件数"]) == (9, 3)
    assert (c["同値の組に関与した行数"], c["順が一意に決まった行数"]) == (6, 6)
    assert [t["行数"] for t in s.ties()] == [2, 2, 2]
    assert [t["データ表の行番号"] for t in s.ties()] == [[2, 4], [6, 9], [10, 13]]
    print(f"[measure] 粗い鍵(支給日 → 区分): 鍵の組数 {c['鍵の組数']} /"
          f" 同値の組 {c['同値の組の件数']} 組 / 関与した行数 {c['同値の組に関与した行数']}"
          f" / 順が一意に決まった行数 {c['順が一意に決まった行数']}(分母はデータ表の 12 行)")
    print("[measure] 同値の組の鍵: " + " / ".join(
        f"{t['鍵']['支給日']} {t['鍵']['区分']} 行{t['データ表の行番号']}" for t in s.ties()))


def test_measure_counts_never_stand_alone() -> None:
    """一意になった率を単独では返さない(分母の内訳と「鍵は宣言された列だけ」が必ず付く)。"""
    for name in ("sengen_mitsu", "sengen_sokaku"):
        c = sorted_with(name).counts()
        assert "分母に含めたもの" in c and "鍵は宣言された列だけ" in c
        assert not [k for k in c if "率" in k]
        assert str(c["データ表の行数"]) in str(c["分母に含めたもの"])


def test_stopped_returns_no_rows() -> None:
    """止まったときは 1 行も並べない(並べた表を取りに行くと例外)。"""
    s = sorted_with("sengen_sokaku")
    assert s.index == ()
    for call in (s.rows, s.judgement_bytes, s.sha256):
        with pytest.raises(RuntimeError):
            call()


# ---------------------------------------------------------------- (2) 値の種類の宣言が順を決める

def test_measure_kind_decides_the_order() -> None:
    """同じ列でも 整数 と コードポイント列 で並びが変わる(10 が 9 の前に来るかどうか)。"""
    seisuu, code = sorted_with("sengen_shain_seisuu"), sorted_with("sengen_shain_codepoint")
    col = seisuu.table.header.index("社員番号")
    a = [seisuu.table.rows[i][col] for i in seisuu.index]
    b = [code.table.rows[i][col] for i in code.index]
    assert a == ["2", "7", "8", "9", "10", "12", "31", "45", "60", "100", "103", ""]
    assert b == ["10", "100", "103", "12", "2", "31", "45", "60", "7", "8", "9", ""]
    moved = sum(1 for x, y in zip(seisuu.index, code.index) if x != y)
    assert moved == 11
    assert seisuu.sha256() != code.sha256()
    print(f"[measure] 社員番号を 整数 と宣言: {' / '.join(a[:5])} …(先頭 5 行)")
    print(f"[measure] 社員番号を コードポイント列 と宣言: {' / '.join(b[:5])} …(先頭 5 行)")
    print(f"[measure] 同じ 12 行で位置が変わった行数 {moved}(欠損の 1 行だけ同じ位置)。"
          f"判定部分の sha256 は {seisuu.sha256()[:12]} と {code.sha256()[:12]} で別")


def test_measure_decimal_ties_what_codepoint_keeps_apart() -> None:
    """Decimal と宣言すると 829 と 829.0 は同値になり、コードポイント列なら別の値のまま残る。"""
    dec, code = sorted_with("sengen_kingaku_decimal"), sorted_with("sengen_kingaku_codepoint")
    assert dec.report.ok is False
    assert [p.reason for p in dec.report.pending] == [O.STOP_REASONS[8]]
    assert dec.counts()["鍵の組数"] == 11 and dec.counts()["同値の組の件数"] == 1
    assert dec.ties()[0]["データ表の行番号"] == [3, 4]
    assert code.report.ok is True and code.counts()["鍵の組数"] == 12
    col = code.table.header.index("金額")
    assert [code.table.rows[i][col] for i in code.index][:5] == \
        ["10450", "11045", "11046", "829", "829.0"]
    print(f"[measure] 金額を Decimal と宣言: 鍵の組数 {dec.counts()['鍵の組数']} /"
          f" 同値の組 {dec.counts()['同値の組の件数']} 組(829 と 829.0 = 行"
          f"{dec.ties()[0]['データ表の行番号']})→ 並べずに止まる")
    print(f"[measure] 金額を コードポイント列 と宣言: 鍵の組数 {code.counts()['鍵の組数']} /"
          f" 同値の組 0 組 → 並ぶ(10450 が 829 の前に来る)")


def test_measure_missing_place_and_direction() -> None:
    """欠損の置き場所と向きは宣言どおりにだけ掛かる(欠損は向きに引きずられない)。"""
    ato, saki = sorted_with("sengen_shain_seisuu"), sorted_with("sengen_shain_kesson_saki")
    kudari = sorted_with("sengen_shain_kouzyun")
    empty = [i for i, r in enumerate(ato.table.rows) if r[ato.table.header.index("社員番号")] == ""]
    assert len(empty) == 1
    assert ato.index[-1] == empty[0] and saki.index[0] == empty[0]
    assert ato.index[:-1] == saki.index[1:]
    assert kudari.index == tuple(reversed(ato.index[:-1])) + (empty[0],)
    assert len({ato.sha256(), saki.sha256(), kudari.sha256()}) == 3
    print(f"[measure] 欠損の置き場所を 後 → 先 に変えると、空欄の 1 行が 12 行目から 1 行目へ移り、"
          f"残り 11 行の順は変わらない(sha256 は {ato.sha256()[:12]} と {saki.sha256()[:12]})")
    print("[measure] 向きを 降順 にすると値のある 11 行が逆順になり、欠損の行は宣言どおり後ろに残る")


# ---------------------------------------------------------------- (3) 入力の行順に依存しない

def test_measure_output_survives_every_declared_swap(table: O.Table) -> None:
    """宣言された鍵で一意に決まるなら、入力表の行順を入れ替えても同じバイト列になる。"""
    o = order("sengen_mitsu")
    base = O.sort_table(table, o)
    same = []
    for how in O.SWAPS:
        s = O.sort_table(table.swapped(how), o)
        same.append(s.report.ok and s.sha256() == base.sha256())
    assert same == [True, True, True]
    assert O.verify(table, o)["ok"] is True
    print(f"[measure] 入力表の行順を 3 通り({' / '.join(O.SWAPS)})に入れ替えても"
          f"判定部分の sha256 は同じ {base.sha256()[:12]}(3/3 一致)")


def test_measure_twice_is_the_same_bytes(table: O.Table) -> None:
    o = order("sengen_mitsu")
    first, second = O.sort_table(table, o), O.sort_table(table, o)
    assert first.sha256() == second.sha256()
    raw = first.judgement_bytes().decode("utf-8")
    for key in (first.read_at, first.host, str(ROOT), "読んだ時刻", "ホスト名"):
        assert key not in raw
    assert set(first.read_condition()) == set(O.READ_KEYS)
    print(f"[measure] 同じ入力で 2 回並べる: 判定部分の sha256 が一致"
          f"(先頭 12 桁 {first.sha256()[:12]})。時刻・ホスト名・絶対パスは判定部分に入らない")


def test_measure_input_tables_are_not_touched(table: O.Table) -> None:
    before = {p: p.read_bytes() for p in sorted(FIX.rglob("*.csv"))}
    s = O.sort_table(table, order("sengen_mitsu"))
    s.judgement_bytes()
    O.verify(table, order("sengen_mitsu"))
    after = {p: p.read_bytes() for p in sorted(FIX.rglob("*.csv"))}
    assert before == after
    print(f"[measure] 並べる前後でデータ表と宣言表の sha256 が同じ"
          f"(入力 {len(before)} ファイルを 1 文字も書き換えていない)")


def test_rows_are_a_permutation_and_columns_do_not_grow(table: O.Table) -> None:
    """行は 1 行も増えず減らず書き換わらず、列も増えない(行番号も連番も振らない)。"""
    s = O.sort_table(table, order("sengen_mitsu"))
    assert sorted(s.rows()) == sorted(table.rows)
    out = s.judgement_bytes().decode("utf-8").splitlines()
    assert out[0] == ",".join(table.header)
    assert len(out) == len(table.rows) + 1
    assert O.Table.parse(s.judgement_bytes().decode("utf-8")).header == table.header


def test_comma_in_a_cell_survives_the_round_trip(table: O.Table) -> None:
    """値の中のカンマは引用符で囲まれ、読み戻すと同じ値に戻る(列がずれない)。"""
    s = O.sort_table(table, order("sengen_mitsu"))
    text = s.judgement_bytes().decode("utf-8")
    assert '"4 月分,調整あり(合成)"' in text
    assert sorted(O.Table.parse(text).rows) == sorted(table.rows)


# ---------------------------------------------------------------- (4) 宣言しないまま並べた側

def test_measure_undeclared_stable_sort_depends_on_input_order(table: O.Table) -> None:
    """**並べ方を宣言しない安定ソートは、同じ中身でも入力の行順で出力のバイト列が変わる。**"""
    reversed_table = table.swapped("逆順")
    i1, i2 = naive_stable(table), naive_stable(reversed_table)
    rows1 = [table.rows[i] for i in i1]
    rows2 = [reversed_table.rows[i] for i in i2]
    h1, h2 = digest(table, i1), digest(reversed_table, i2)
    moved = sum(1 for x, y in zip(rows1, rows2) if x != y)
    assert sorted(rows1) == sorted(rows2)          # 中身は同じ
    assert h1 != h2 and moved == 6                 # それでもバイト列は違う
    print(f"[measure] 宣言しない安定ソート(粗い鍵で並べるテスト側の実装): 中身が同じ 12 行でも"
          f" 入力の行順を逆にすると {moved} 行が別の位置に来て、sha256 は {h1[:12]} と {h2[:12]} で別")
    print("[measure] 同じ 12 行に同じ鍵を宣言して order_table で並べると、入れ替えても"
          " sha256 は変わらない(上の 3/3 一致)。差は鍵が足りているかだけ")


def test_measure_order_dependent_implementation_trips_reason_11(monkeypatch: pytest.MonkeyPatch,
                                                                table: O.Table) -> None:
    """入力順に依存する実装に差し替えると、入れ替えた表で出力が変わり理由コードが返る。"""
    monkeypatch.setattr(O, "_compare", lambda a, b, keys: 0)   # 前後を決めない = 入力順のまま
    out = O.verify(table, order("sengen_mitsu"))
    assert out["ok"] is False
    assert [p["reason"] for p in out["pending"]] == [O.STOP_REASONS[10]]
    print(f"[measure] 前後を決めない実装に差し替えた verify: 理由コード「{O.STOP_REASONS[10]}」"
          f"が返る(入れ替えた表の sha256 が {out['入れ替えた表の sha256'][:12]})")


def test_measure_second_pass_mismatch_trips_reason_10(monkeypatch: pytest.MonkeyPatch,
                                                      table: O.Table) -> None:
    """2 回目だけ並びを変える実装に差し替えると、バイト列の突合で止まる。"""
    real, calls = O.sort_table, {"n": 0}

    def fake(t: O.Table, o: O.Order) -> O.Sorted:
        s = real(t, o)
        calls["n"] += 1
        if calls["n"] == 2 and s.report.ok:
            return dataclasses.replace(s, index=tuple(reversed(s.index)))
        return s

    monkeypatch.setattr(O, "sort_table", fake)
    out = O.verify(table, order("sengen_mitsu"))
    assert out["ok"] is False
    assert [p["reason"] for p in out["pending"]] == [O.STOP_REASONS[9]]
    assert "平均も多数決もしない" in str(out["観測"])
    print(f"[measure] 2 回目だけ並びを変えた verify: 理由コード「{O.STOP_REASONS[9]}」が返り、"
          "どちらが正しいかは決めない")


# ---------------------------------------------------------------- 止まる理由コードの出そろい

STOPS = {
    O.STOP_REASONS[0]: ("data_shikyuu", "kowashita/sengen_0gyou"),
    O.STOP_REASONS[1]: ("data_shikyuu", "kowashita/sengen_juufuku"),
    O.STOP_REASONS[2]: ("data_shikyuu", "kowashita/sengen_shutten_nashi"),
    O.STOP_REASONS[3]: ("data_shikyuu", "kowashita/sengen_shurui_kuuran"),
    O.STOP_REASONS[4]: ("data_shikyuu", "kowashita/sengen_kesson_kuuran"),
    O.STOP_REASONS[5]: ("data_shikyuu", "kowashita/sengen_sengen_ni_nai_retsu"),
    O.STOP_REASONS[6]: ("data_shikyuu", "kowashita/sengen_data_ni_nai_retsu"),
    O.STOP_REASONS[7]: ("kowashita/data_float", "sengen_shain_seisuu"),
    O.STOP_REASONS[8]: ("data_shikyuu", "sengen_sokaku"),
}


@pytest.mark.parametrize("reason", list(STOPS))
def test_each_stop_reason_has_a_path(reason: str) -> None:
    data, decl = STOPS[reason]
    s = O.sort_table(O.Table.load(FIX / f"{data}.csv"), order(decl))
    assert s.report.ok is False
    assert reason in {p.reason for p in s.report.pending}
    assert s.index == ()


def test_measure_all_eleven_reason_codes_have_a_path() -> None:
    """11 個の理由コードのうち 9 個は表 9 枚で、残り 2 個は実装を差し替えて通してある。"""
    assert len(STOPS) == 9
    assert set(STOPS) == set(O.STOP_REASONS[:9])
    print(f"[measure] 止まる理由コード {len(O.STOP_REASONS)} 個すべてに道がある"
          f"({len(STOPS)} 個は表 {len(STOPS)} 枚 = 崩した 8 枚と粗い鍵のままの 1 枚、"
          "残り 2 個は差し替えた実装)")


def test_unregistered_kind_and_enum_without_choices() -> None:
    """種類が未登録の行と、宣言された列挙なのに候補の並びが無い行は、同じ理由コードに入る。"""
    for name in ("kowashita/sengen_shurui_mitouroku", "kowashita/sengen_rettukyo_kouho_nashi"):
        s = O.sort_table(O.Table.load(DATA), order(name))
        assert {p.reason for p in s.report.pending} == {O.STOP_REASONS[3]}


def test_value_outside_declared_choices_stops() -> None:
    s = O.sort_table(O.Table.load(FIX / "kowashita/data_rettukyo_gai.csv"), order("sengen_sokaku"))
    assert s.report.ok is False
    assert {p.reason for p in s.report.pending} == {O.STOP_REASONS[3]}
    assert "候補に無い値" in s.report.pending[0].detail


@pytest.mark.parametrize("data,decl", [
    ("data_shikyuu", "kowashita/sengen_muki_kuuran"),
    ("data_shikyuu", "kowashita/sengen_kesson_mitouroku"),
    ("data_shikyuu", "kowashita/sengen_junni_hi_seisuu"),
    ("data_shikyuu", "kowashita/sengen_irekae_mitouroku"),
    ("kowashita/data_hidzuke_yomenai", "sengen_mitsu"),
    ("kowashita/data_suu_yomenai", "sengen_shain_seisuu"),
])
def test_unreadable_tables_are_not_reason_codes(data: str, decl: str) -> None:
    """語彙の外・数として読めない値は理由コードにせず、表として読めない(終了コード 2)。"""
    assert O.main(["check", str(FIX / f"{data}.csv"), str(FIX / f"{decl}.csv")]) == 2


def test_float_object_through_the_function_api() -> None:
    """関数として float を渡しても止まる(数は宣言どおりにだけ比較する)。"""
    t = O.Table(header=("社員番号",), rows=((1.5,), ("2",)))
    s = O.sort_table(t, order("sengen_shain_seisuu"))
    assert {p.reason for p in s.report.pending} == {O.STOP_REASONS[7]}


# ---------------------------------------------------------------- 終了コードとひな型

def test_exit_codes(capsys: pytest.CaptureFixture[str]) -> None:
    assert O.main(["sort", str(DATA), str(FIX / "sengen_mitsu.csv")]) == 0
    assert O.main(["check", str(DATA), str(FIX / "sengen_mitsu.csv")]) == 0
    assert O.main(["verify", str(DATA), str(FIX / "sengen_mitsu.csv")]) == 0
    assert O.main(["check", str(DATA), str(FIX / "sengen_sokaku.csv")]) == 3
    out = capsys.readouterr().out
    assert "並べる前に止まった" in out


def test_init_template_is_usable(tmp_path: Path) -> None:
    """ひな型は 2 枚で、そのまま並べると順が一意に決まる。"""
    data, decl = O.init(tmp_path / "ひな型")
    assert data.exists() and decl.exists()
    s = O.sort_table(O.Table.load(data), O.Order.load(decl))
    assert s.report.ok and s.counts()["鍵の組数"] == 2
    assert O.main(["verify", str(data), str(decl)]) == 0


def test_verify_without_declared_swap_does_not_run(tmp_path: Path) -> None:
    """入れ替え方の宣言が無ければ verify は走らない(乱数の既定を持たないので勝手に選ばない)。"""
    text = (FIX / "sengen_mitsu.csv").read_text(encoding="utf-8").replace("逆順", "")
    p = tmp_path / "swap_nashi.csv"
    p.write_text(text, encoding="utf-8")
    with pytest.raises(O.ReadError):
        O.verify(O.Table.load(DATA), O.Order.load(p))


def test_fixtures_are_regenerated_byte_for_byte(tmp_path: Path) -> None:
    """commit 済の fixture は make_fixtures の出力そのもの(手で直していない)。"""
    M.build(tmp_path)
    for p in sorted(FIX.rglob("*.csv")):
        assert p.read_bytes() == (tmp_path / p.relative_to(FIX)).read_bytes(), p.name
