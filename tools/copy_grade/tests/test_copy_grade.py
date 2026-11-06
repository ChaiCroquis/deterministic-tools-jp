"""copy_grade のテスト。合成 fixture は `fixtures/` に commit 済(実データ・実在のコードは入れない)。

test_measure_* が記事に載せた数値の出どころで、assert で固定している(値が変われば記事も変える前提)。
測っているものは 8 つある。

  (1) 部品 9 件 / 箇所 19 件(写しが渡されたのは 18 件)で、2 箇所の組 16 件が
      4 段 10 件 + 別枠 6 件に分かれる側
  (2) **(A) そのままで同一 が 1 件だけで、注記と段がずれた組が 2 件**という側 = 記事の骨
      (`指紋一致と注記` の組が (B)、`同型と注記` の組が (C))
  (3) (C) の組が **違う行の番号だけ**を返す側(3 組が 3 行目、1 組が 2 行目と 4 行目)
  (4) `派生と注記` の 3 組が (D) 1 件 + 別枠「その注記が要求する欄が空」2 件に割れる側
  (5) 宣言されている箇所数の文字列と写しの件数が並び、**整数に直す経路が無い**側
  (6) 1 件の写しの行末に空白を 1 つ足すと、その組だけが (A) → (B) へ移る側
  (7) 1 件の写しに空行でない 1 行を足すと、その組だけが (D) へ移り行数の組が出る側
  (8) 出力の末尾の「持たせていないもの」が 12 行で、禁則の語が件数の側に無い側

(1) の 4 段は、テストの側でも 3 枚の行と写しのバイト列から直に組み立てて確かめている
(部品の grade / four / counts を呼ばず、正規化もテストの中に別に書く)。
"""
from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIX = ROOT / "fixtures"
BOX = FIX / "copies"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FIX))
import copy_grade as H  # noqa: E402
import make_fixtures as M  # noqa: E402

# まとめてよいか・正しさ・似ている度合いを指す語(件数と一覧の側に持たせない)
KINSOKU = ("類似度", "一致率", "割合", "距離", "まとめてよい", "統合すべき", "正本",
           "優先度", "推奨", "削減", "トークン", "成功率", "健全")

# 出力の末尾に並ぶ「持たせていないもの」(**消す引数も option も無い**)
MOTANAI_KEYS = (
    "まとめてよいかを決めない",
    "写しの中身を出力に出さない",
    "名前を出力に出さない",
    "振る舞いが同じかを見ない",
    "似ている度合いを出さない",
    "注記を段の代わりに使わない",
    "宣言されている箇所数を整数に直さない",
    "テストの有無を段に混ぜない",
    "写しを取りに行かない",
    "正規化は 3 つだけ",
    "時計を読まない",
    "入力を書き換えない",
)

# 持たせていない呼び出し(動く側のコードに 1 つも無いことを見る)
MOTANAI_CALLS = ("eval", "exec", "round", "float", "now", "today", "time", "Popen",
                 "check_output", "run", "random", "choice", "shuffle", "mean",
                 "median", "urlopen", "urlretrieve", "ratio", "SequenceMatcher",
                 "get_close_matches", "unified_diff", "ndiff")

NORMAL = ("parts_a", "sites_a", "notes_a")


def path_of(name: str) -> Path:
    return FIX / f"{name}.csv" if name in NORMAL else FIX / "kowashita" / f"{name}.csv"


def three(p: str = "parts_a", s: str = "sites_a", n: str = "notes_a"):
    parts = H.Parts.load(path_of(p))
    sites = H.Sites.load(path_of(s))
    notes = H.Notes.load(path_of(n))
    return parts, sites, notes, H.Copies.load(BOX, sites.copies)


def pull(**kw) -> H.Table:
    return H.copy_grade(*three(**kw))


def reasons_of(t: H.Table) -> set[str]:
    return {x.reason for x in t.report.pending}


def pair_of(t: H.Table, name: str) -> H.Pair:
    return next(p for p in t.pairs if p.name == name)


# ---------------------------------------------------------------- 別実装(テスト側)

def my_normalize(text: str) -> list[str]:
    """正規化をテストの側に別に書く(部品の normalize を呼ばない)。"""
    out = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        while line[-1:] in (" ", "\t"):
            line = line[:-1]
        out.append(line)
    while out and out[-1] == "":
        out.pop()
    return out


def expect_pairs() -> dict[str, tuple[str, str]]:
    """3 枚の行と写しのバイト列から (段, 違う行 or 行数の組) を別に出す。"""
    requires = {r[0]: r[2] for r in M.NOTES[1:]}
    sites = {r[0]: r for r in M.SITES[1:]}
    by_part: dict[str, list[str]] = {}
    for r in M.SITES[1:]:
        by_part.setdefault(r[1], []).append(r[0])
    out: dict[str, tuple[str, str]] = {}
    for part in sorted({r[0] for r in M.PARTS[1:]}):
        ids = sorted(by_part.get(part, []))
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = sites[ids[i]], sites[ids[j]]
                key = f"{part}:{ids[i]}>{ids[j]}"
                if not a[5] or not b[5]:
                    out[key] = (H.BETSUWAKU[0], "")
                elif any(x[3] not in requires for x in (a, b)):
                    out[key] = (H.BETSUWAKU[1], "")
                elif any((requires[x[3]] == "写し" and not x[2])
                         or (requires[x[3]] == "行数" and not x[4])
                         for x in (a, b)):
                    out[key] = (H.BETSUWAKU[2], "")
                elif not a[2] or not b[2]:
                    out[key] = (H.BETSUWAKU[3], "")
                else:
                    ra = (BOX / a[2]).read_bytes()
                    rb = (BOX / b[2]).read_bytes()
                    la, lb = my_normalize(ra.decode("utf-8")), my_normalize(
                        rb.decode("utf-8"))
                    if ra == rb:
                        out[key] = (H.DAN[0], "")
                    elif la == lb:
                        out[key] = (H.DAN[1], "")
                    elif len(la) == len(lb):
                        diff = [k + 1 for k, (x, y) in enumerate(zip(la, lb))
                                if x != y]
                        out[key] = (H.DAN[2], ",".join(str(n) for n in diff))
                    else:
                        out[key] = (H.DAN[3], f"{len(la)}/{len(lb)}")
    return out


# ---------------------------------------------------------------- 記事に載せた数値

def test_measure_16_pairs_split_into_four_grades() -> None:
    """(1) 組 16 件が 4 段 10 件 + 別枠 6 件に分かれ、分母の内訳が付く。"""
    t = pull()
    assert t.report.ok, [p.as_dict() for p in t.report.pending]
    c = t.counts()
    assert (c["部品の台帳の行数"], c["箇所の台帳の行数"], c["注記記号の登録表の行数"]) == (9, 19, 7)
    assert c["写しのファイルの本数"] == 18
    assert (t.part_denominator(), t.site_denominator()) == (9, 19)
    assert (t.handed_denominator(), t.pair_denominator()) == (18, 16)
    four, extras = t.four(), t.extras()
    assert four == {H.DAN[0]: 1, H.DAN[1]: 3, H.DAN[2]: 4, H.DAN[3]: 2}
    assert extras == {H.BETSUWAKU[0]: 1, H.BETSUWAKU[1]: 1,
                      H.BETSUWAKU[2]: 2, H.BETSUWAKU[3]: 2}
    assert sum(four.values()) == 10 and sum(extras.values()) == 6
    assert sum(four.values()) + sum(extras.values()) == 16
    # テストの側の別実装と一致する
    mine = {p.name: (p.grade, ",".join(str(n) for n in p.diff_lines)
                     if p.grade == H.DAN[2]
                     else (f"{p.lines[0]}/{p.lines[1]}" if p.grade == H.DAN[3] else ""))
            for p in t.pairs}
    assert mine == expect_pairs()
    assert (c["箇所が 1 行も無い部品"], c["どの箇所も使っていない注記記号の登録"]) == (1, 1)
    assert sum(int(r["組の件数"]) for r in t.by_part()) == 16
    assert sum(int(r["組の件数"]) for r in t.by_note()) == 16
    print("[measure] parts_a / sites_a / notes_a + 写しの置き場: 部品 9 行 / 箇所 19 行"
          "(写しが渡されたのは 18 件)/ 注記記号の登録 7 行")
    print(f"[measure] 分母は 同じ部品の 2 箇所の組 16 件、4 段は "
          f"{json.dumps(four, ensure_ascii=False)}")
    print(f"[measure] 別枠は {json.dumps(extras, ensure_ascii=False)}。"
          f"合計 {sum(four.values()) + sum(extras.values())} = 組 16")
    print("[measure] 箇所が 1 行も無い部品 1 件、どの箇所も使っていない注記記号の登録 1 件。"
          "どちらも止めずに一覧へ出す")


def test_measure_only_one_pair_is_identical() -> None:
    """(2) (A) は 1 件だけで、注記と段がずれた組が 2 件ある = 記事の骨。"""
    t = pull()
    assert t.four()[H.DAN[0]] == 1
    assert [p.name for p in t.pairs if p.grade == H.DAN[0]] == ["P1:S01>S02"]
    # `指紋一致と注記` の組は (B)。注記を段に読み替える経路が無い
    fp = [p for p in t.pairs if p.notes == ("指紋一致と注記", "指紋一致と注記")]
    assert len(fp) == 1 and fp[0].grade == H.DAN[1] and fp[0].name == "P6:S15>S16"
    # `同型と注記` の組は (C)。人が同じ形だと書いても、文字は同じでない
    same = [p for p in t.pairs if p.notes == ("同型と注記", "同型と注記")]
    assert len(same) == 1 and same[0].grade == H.DAN[2] and same[0].name == "P3:S08>S09"
    assert len(fp) + len(same) == 2
    # 注記の組ごとの一覧は、注記と段を別の列で並べる
    rows = {r["注記の組"]: r for r in t.by_note()}
    assert rows["指紋一致と注記 / 指紋一致と注記"]["4 段"][H.DAN[0]] == 0
    assert rows["同型と注記 / 同型と注記"]["4 段"][H.DAN[0]] == 0
    print("[measure] (A) そのままで同一 は 1 件だけ(P1:S01>S02)。残り 9 件の段は"
          " (B) 3 / (C) 4 / (D) 2")
    print("[measure] 注記と段がずれた組は 2 件 = `指紋一致と注記` の 1 組が (B)"
          "(P6:S15>S16)、`同型と注記` の 1 組が (C)(P3:S08>S09)")
    print("[measure] 注記の組ごとの一覧でも、この 2 つの (A) の欄は 0 のまま")


def test_measure_c_grade_returns_line_numbers_only() -> None:
    """(3) (C) の組は違う行の番号だけを返す(中身は返さない)。"""
    t = pull()
    cs = [p for p in t.pairs if p.grade == H.DAN[2]]
    assert len(cs) == 4
    assert {p.name: p.diff_lines for p in cs} == {
        "P1:S01>S04": (3,), "P1:S02>S04": (3,), "P1:S03>S04": (3,),
        "P3:S08>S09": (2, 4)}
    assert all(p.lines[0] == p.lines[1] for p in cs)
    # 出力に写しの中身が 1 文字も出ない
    body = json.dumps([p.as_dict() for p in t.pairs], ensure_ascii=False)
    for name, text in M.COPIES.items():
        for line in text.splitlines():
            if len(line.strip()) >= 8:
                assert line.strip() not in body, line
        assert name not in body
    print("[measure] (C) は 4 組で、返るのは違う行の番号だけ(P1 の 3 組が 3 行目、"
          "P3:S08>S09 が 2 行目と 4 行目)。行数の組はどちらも同じ")
    print("[measure] 組の一覧に写しの行の中身は 1 つも出ない(写しのファイル名も出ない)")


def test_measure_derived_note_splits_into_d_and_extras() -> None:
    """(4) `派生と注記` の 3 組が (D) 1 件 + 別枠 2 件に割れる。"""
    t = pull()
    here = [p for p in t.pairs if p.notes == ("派生と注記", "派生と注記")]
    assert len(here) == 3
    assert [p.grade for p in here] == [H.DAN[3], H.BETSUWAKU[2], H.BETSUWAKU[2]]
    d = next(p for p in here if p.grade == H.DAN[3])
    assert d.name == "P5:S12>S13" and d.lines == (7, 8)
    # 行数の記載は宣言のままで、整数に直さない
    assert [r[4] for r in M.SITES[1:] if r[1] == "P5"] == ["451", "483", ""]
    assert all(not isinstance(p.lines[0], str) for p in here)
    print("[measure] `派生と注記` の 3 組は (D) 1 件(P5:S12>S13、行数の組は 7 と 8)と、"
          "別枠「その注記が要求する欄が空」2 件に割れる")
    print("[measure] 注記に書かれた行数(451 / 483 / 空欄)は宣言のまま持ち、"
          "測った行数(7 / 8 / 9)とは別の列に並ぶ")


def test_measure_declared_string_is_never_an_integer() -> None:
    """(5) 宣言されている箇所数の文字列と写しの件数が並び、整数に直す経路が無い。"""
    t = pull()
    rows = t.declared_vs_handed()
    assert len(rows) == 9
    declared = [str(r["宣言されている箇所数の文字列"]) for r in rows]
    assert declared == ["17", "8+", "7", "18 ファイル",
                        "3 本が派生複製(451 / 483 / 486 行)", "4 / 3",
                        "5(同一関数コピー)", "8+", "4 + 5"]
    plain = [s for s in declared if s.isascii() and s.isdigit()]
    assert plain == ["17", "7"]
    handed = [int(r["写しが渡された箇所の件数"]) for r in rows]
    assert handed == [4, 2, 2, 2, 3, 2, 2, 1, 0]
    assert sum(handed) == 18
    # 宣言の文字列と写しの件数が同じ数になる部品は 1 つも無い
    assert not [r for r in rows
                if str(r["宣言されている箇所数の文字列"])
                == str(r["写しが渡された箇所の件数"])]
    print("[measure] 宣言されている箇所数の文字列は 9 件のうち 2 件だけが整数 1 つで"
          "(17 と 7)、残り 7 件は `8+` `18 ファイル` `4 / 3` `4 + 5` のような形")
    print("[measure] 写しが渡された箇所の件数は 4 / 2 / 2 / 2 / 3 / 2 / 2 / 1 / 0 の"
          "合計 18 件。宣言の文字列と同じ数になる部品は 0 件で、整数に直す経路も無い")
    print("[measure] `統一済みと宣言` の部品(P8)は宣言が `8+` で写しは 1 本 = 組 0 件")


def test_measure_trailing_space_moves_one_pair() -> None:
    """(6) 1 件の写しの行末に空白を 1 つ足すと、その組だけが (A) → (B) へ移る。"""
    parts, sites, notes, copies = three()
    first = H.copy_grade(parts, sites, notes, copies)
    out = H.space_probe(parts, sites, notes, copies, first)
    assert out["合うか"] is True
    assert out["替えた箇所"] == "S01" and out["動いた組"] == ["P1:S01>S02"]
    assert (out["(A)(前)"], out["(A)(後)"]) == (1, 0)
    assert (out["(B)(前)"], out["(B)(後)"]) == (3, 4)
    assert out["別枠(前)"] == out["別枠(後)"]
    print("[measure] 行末に空白を足した写し: S01 の写しの行末に空白を 1 つ足すと、"
          "P1:S01>S02 の 1 組だけが (A) → (B) へ移る((A) 1 → 0 件 / (B) 3 → 4 件)")
    print("[measure] ほかで動いた組は 0 件、別枠の 4 つも不変"
          "(正規化が行末の空白を落とすので、正規化後の指紋は動かない)")


def test_measure_one_extra_line_moves_only_that_pair() -> None:
    """(7) 1 件の写しに空行でない 1 行を足すと、その組だけが (D) へ移る。"""
    parts, sites, notes, copies = three()
    first = H.copy_grade(parts, sites, notes, copies)
    out = H.line_probe(parts, sites, notes, copies, first)
    assert out["合うか"] is True
    assert out["替えた箇所"] == "S08" and out["動いた組"] == ["P3:S08>S09"]
    assert out["行数の組(後)"] == [[6, 5]]
    assert (out["(D)(前)"], out["(D)(後)"]) == (2, 3)
    assert out["別枠(前)"] == out["別枠(後)"]
    print("[measure] 1 行足した写し: S08 の写しに空行でない 1 行を足すと P3:S08>S09 の"
          "1 組だけが (C) → (D) へ移り、行数の組 6 と 5 が出る((D) 2 → 3 件)")
    print("[measure] ほかで動いた組は 0 件、別枠も不変。写しはメモリの中だけで、"
          "置き場のファイルは 1 文字も書き換わらない")


def test_measure_output_has_no_merge_column() -> None:
    """(8) 出力の末尾の「持たせていないもの」が 12 行で、禁則の語が件数の側に無い。"""
    t = pull()
    c = t.counts()
    assert tuple(k for k in c if k in MOTANAI_KEYS) == MOTANAI_KEYS
    assert len(MOTANAI_KEYS) == 12
    for word in KINSOKU:
        hit = [k for k in c if word in k]
        assert set(hit) <= set(MOTANAI_KEYS), (word, hit)
    for pair in t.pairs:
        for key in pair.as_dict():
            assert not any(w in key for w in KINSOKU), key
    tree = ast.parse((ROOT / "copy_grade.py").read_text(encoding="utf-8"))
    called: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            f = n.func
            called.add(f.id if isinstance(f, ast.Name) else
                       (f.attr if isinstance(f, ast.Attribute) else ""))
    assert not (called & set(MOTANAI_CALLS)), called & set(MOTANAI_CALLS)
    mods = {n.names[0].name.split(".")[0] if isinstance(n, ast.Import)
            else (n.module or "").split(".")[0]
            for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))}
    assert len(mods) == 8, sorted(mods)
    assert sum(1 for n in ast.walk(tree) if isinstance(n, ast.Call)
               and isinstance(n.func, ast.Attribute)
               and isinstance(n.func.value, ast.Name)
               and n.func.value.id == "hashlib") == 3
    assert c["決めた正規化"] == list(H.NORMALIZE) and len(H.NORMALIZE) == 3
    print(f"[measure] 出力の末尾の「持たせていないもの」は 12 行で、消す引数も option も"
          f"無い。禁則の語({len(KINSOKU)} 語)を含む key は、その 12 行だけ")
    print("[measure] 部品が import している module は 8 個で、eval / exec / float /"
          " round / 現在時刻 / subprocess / random / 平均 / 通信 / 類似度の呼び出しは"
          " 0 件。hashlib を呼ぶのは 3 か所(生の指紋 / 正規化後の指紋 / 判定部分)")


# ---------------------------------------------------------------- 止まる側

def test_stop_reasons_are_nine() -> None:
    assert len(H.STOP_REASONS) == 9
    assert len(H.TABLE_REASONS) == 6 and len(H.VERIFY_REASONS) == 3
    assert len(set(H.STOP_REASONS)) == 9


@pytest.mark.parametrize("name,reason", [
    ("parts_shutten_kuuran", H.TABLE_REASONS[0]),
    ("notes_shutten_kuuran", H.TABLE_REASONS[0]),
    ("parts_id_juufuku", H.TABLE_REASONS[1]),
    ("sites_id_juufuku", H.TABLE_REASONS[2]),
    ("sites_buhin_nashi", H.TABLE_REASONS[3]),
    ("notes_kigou_juufuku", H.TABLE_REASONS[4]),
    ("sites_onaji_utsushi", H.TABLE_REASONS[5]),
])
def test_broken_table_counts_nothing(name: str, reason: str) -> None:
    """崩した表では 1 組も数えず、理由コードが返る。"""
    key = {"parts_": "p", "sites_": "s", "notes_": "n"}[name[:6]]
    t = pull(**{key: name})
    assert t.report.ok is False
    assert reason in reasons_of(t)
    assert t.pairs == ()
    assert t.four() == {k: 0 for k in H.DAN}
    assert t.extras() == {k: 0 for k in H.BETSUWAKU}
    assert t.pair_denominator() == 0
    for call in (t.judgement_bytes, t.sha256):
        with pytest.raises(RuntimeError):
            call()


def test_all_table_reasons_have_a_broken_fixture() -> None:
    """表の側の 6 つの理由コードすべてに、崩した表の道が在る。"""
    got: set[str] = set()
    for p in sorted((FIX / "kowashita").glob("*.csv")):
        key = {"parts_": "p", "sites_": "s", "notes_": "n"}[p.stem[:6]]
        try:
            got |= reasons_of(pull(**{key: p.stem}))
        except H.ReadError:
            continue
    assert set(H.TABLE_REASONS) <= got, set(H.TABLE_REASONS) - got
    print("[measure] 止まる理由コードは 9 個(表の側 6 + verify 3)で、表の側 6 個"
          "すべてに崩した表で道がある")


def test_unreadable_tables_exit_two() -> None:
    """表として読めない形は終了コード 2 で、組は 1 つも数えない。"""
    unreadable, stopped = 0, 0
    for p in sorted((FIX / "kowashita").glob("*.csv")):
        key = {"parts_": "p", "sites_": "s", "notes_": "n"}[p.stem[:6]]
        try:
            t = pull(**{key: p.stem})
        except H.ReadError:
            unreadable += 1
            continue
        assert t.report.ok is False
        stopped += 1
    assert unreadable + stopped == 22
    assert (stopped, unreadable) == (7, 15)
    print("[measure] 崩した表 22 枚の内訳 = 1 組も数えずに止まる 7 枚 / "
          "表として読めない 15 枚(列が無い 3 / 行が無い 3 / 登録の外の記号 3 / "
          "id が空か区切り文字 3 / 写しが読めない 3)")


# ---------------------------------------------------------------- verify と CLI

def test_verify_is_deterministic() -> None:
    out = H.verify(*three())
    assert out["ok"] is True
    assert out["sha256"] == out["2 回目の sha256"]
    assert set(out["入れ替えた 3 枚の sha256"].values()) == {out["sha256"]}
    assert out["件数の検算"]["合計"] == 16
    assert out["行末に空白を足した写し"]["合うか"] is True
    assert out["1 行足した写し"]["合うか"] is True
    assert out["sha256"][:12] == H.copy_grade(*three()).sha256()[:12]
    print(f"[measure] 2 回 + 3 通りの入れ替えで読み直し: 判定部分の sha256 は 4 回とも"
          f"同じ(4/4 一致、先頭 12 桁 {out['sha256'][:12]})")


def test_judgement_bytes_has_no_paths() -> None:
    t = pull()
    body = t.judgement_bytes().decode("utf-8")
    for word in ("読んだ条件", "絶対パス", str(ROOT), str(BOX), ".txt"):
        assert word not in body, word


def test_cli_prints_counts(capsys: pytest.CaptureFixture[str]) -> None:
    code = H.main(["check", str(FIX / "parts_a.csv"), str(FIX / "sites_a.csv"),
                   str(FIX / "notes_a.csv"), str(BOX)])
    body = json.loads(capsys.readouterr().out)
    assert code == 3            # 別枠と (A) 以外の段が在るので 0 ではない
    assert body["ok"] is True and body["分母(2 箇所の組の件数)"] == 16
    code = H.main(["verify", str(FIX / "parts_a.csv"), str(FIX / "sites_a.csv"),
                   str(FIX / "notes_a.csv"), str(BOX)])
    assert code == 0
    capsys.readouterr()
    code = H.main(["check", str(FIX / "parts_a.csv"),
                   str(FIX / "kowashita" / "sites_soto.csv"),
                   str(FIX / "notes_a.csv"), str(BOX)])
    assert code == 2


def test_init_writes_three_templates(tmp_path: Path) -> None:
    out = H.init(tmp_path)
    assert len(out) == 5 and all(p.exists() for p in out)
    parts, sites, notes = (H.Parts.load(tmp_path / "部品の台帳.csv"),
                           H.Sites.load(tmp_path / "箇所の台帳.csv"),
                           H.Notes.load(tmp_path / "注記記号の登録表.csv"))
    copies = H.Copies.load(tmp_path / "写しの置き場", sites.copies)
    t = H.copy_grade(parts, sites, notes, copies)
    assert t.report.ok and t.pair_denominator() == 1
    assert t.four()[H.DAN[0]] == 1


def test_input_is_never_rewritten() -> None:
    """verify の 2 つの写しを通しても、3 枚の CSV と写しのファイルが 1 バイトも動かない。"""
    def digest() -> dict[str, str]:
        out = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted(FIX.glob("*.csv"))}
        out.update({p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(BOX.iterdir())})
        return out
    before = digest()
    assert H.verify(*three())["ok"] is True
    assert digest() == before
    assert len(before) == 3 + 19


def test_normalize_touches_only_three_things() -> None:
    """正規化は 3 つだけ。字下げ・コメント・識別子・引用符には触らない。"""
    assert H.normalize("a  \r\nb\t\n\n\n") == "a\nb"
    assert H.normalize("    a\n") == "    a"          # 字下げは揃えない
    assert H.normalize("a  # note\n") == "a  # note"  # コメントは外さない
    assert H.normalize("x = 'a'\n") == "x = 'a'"      # 引用符は揃えない
    assert H.normalize("") == "" and H.normalize("\n\n") == ""
