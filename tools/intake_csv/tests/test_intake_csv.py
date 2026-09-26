"""intake_csv のテスト。fixture は全て合成データ(fixtures/make_fixtures.py)、氏名も部署も金額も架空。

後半の test_measure_* は、合成した 1,000 行の支給控除一覧で
  (a) 現場でよく見る書き出し(検査なし・読み戻しなし。cp932 は errors="replace"、カンマはクォートで逃がす)
  (b) この部品(検査 → 書く → 読み戻して件数・合計・全セルを突き合わせる)
を比べる(記事の数値はここから取る。固定 seed で決定論的に再現し、変わったら記事の数字も変える)。
"""
from __future__ import annotations

import csv
import random
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FX))
import intake_csv as I  # noqa: E402
import make_fixtures as MF  # noqa: E402

SPEC = I.Spec.from_csv(FX / "retsu_shiyou.csv")


def rows_of(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def one(**over: str) -> dict[str, str]:
    """そのまま書ける 1 行を作り、渡した列だけ差し替える。"""
    base = {"社員番号": "100001", "氏名": "山田太郎", "部署": "営業部",
            "支給合計": "382000", "控除合計": "61200", "差引支給額": "320800"}
    base.update(over)
    return base


# ---- 列仕様の表 ------------------------------------------------------------------------------

def test_spec_from_csv():
    assert SPEC.names == ("社員番号", "氏名", "部署", "支給合計", "控除合計", "差引支給額")
    assert SPEC.total_names == ("支給合計", "控除合計", "差引支給額")
    assert SPEC.columns[0].zero_pad and SPEC.columns[0].width == 6
    assert SPEC.columns[2].needed is False       # 部署は空を許す
    assert SPEC.columns[1].needed is True


@pytest.mark.parametrize("kwargs", [
    {"name": "x", "kind": "日付"},                      # 表に無い型
    {"name": "x", "kind": "コード", "zero_pad": True},   # ゼロ埋めに桁が無い
    {"name": "x", "kind": "文字列", "total": True},      # 文字列の合計は取れない
])
def test_spec_rejects_broken_column(kwargs):
    with pytest.raises(I.SpecError):
        I.Column(**kwargs)


def test_spec_rejects_duplicate_heading():
    with pytest.raises(I.SpecError):
        I.Spec((I.Column("氏名"), I.Column("氏名")))


def test_spec_rejects_empty():
    with pytest.raises(I.SpecError):
        I.Spec(())


def test_missing_column_stops_instead_of_filling_blank():
    """足りない列は空欄で埋めない。止まる。"""
    rows = [{k: v for k, v in one().items() if k != "控除合計"}]
    with pytest.raises(I.SpecError) as e:
        I.check_rows(SPEC, rows)
    assert "控除合計" in str(e.value) and "空欄で埋めない" in str(e.value)


def test_columns_outside_the_spec_are_not_written():
    rows = [one(備考="社内メモ", 期待="")]
    lines, pending, dropped = I.check_rows(SPEC, rows)
    assert dropped == ["備考", "期待"] and pending == []
    assert len(lines[0]) == len(SPEC.columns)


# ---- 出力の形を作る(勝手に変えない) ----------------------------------------------------------

def test_zero_pad_keeps_leading_zero():
    assert I.render(SPEC.columns[0], "42") == "000042"


def test_zero_pad_leaves_long_value_alone():
    assert I.render(SPEC.columns[0], "1234567") == "1234567"     # 切り詰めない(桁あふれとして返す)


def test_render_strips_only_the_edges():
    assert I.render(SPEC.columns[1], "　山田　太郎 ") == "山田　太郎"


@pytest.mark.parametrize("value", ["ｲﾄｳ ﾋﾛｼ", "髙﨑一郎", "第①製造部", "㈱の字", "山田　太郎"])
def test_render_does_not_normalize(value):
    """NFKC で寄せない。半角カナも合字もそのまま出す(寄せること自体が判断になる)。"""
    assert I.render(SPEC.columns[1], value) == value


def test_render_of_none_is_empty():
    assert I.render(SPEC.columns[2], None) == ""


# ---- 値の検査(判断待ちの理由コード) ----------------------------------------------------------

@pytest.mark.parametrize("col, value", [
    ("氏名", "山田太郎"),
    ("氏名", "ｲﾄｳ ﾋﾛｼ"),        # 半角カナは cp932 にある
    ("氏名", "髙﨑一郎"),        # 髙 U+9AD9 と 﨑 U+FA11 は cp932 にある
    ("部署", "第①製造部"),      # ① U+2460 も ㈱ U+3231 も cp932 にある
    ("部署", "㈱の字"),
    ("部署", ""),                # 空を許す列
    ("差引支給額", "-41200"),    # 負数
    ("支給合計", "0"),
])
def test_value_is_writable(col, value):
    c = next(x for x in SPEC.columns if x.name == col)
    assert I.check_value(c, value, 1) is None


@pytest.mark.parametrize("col, value, reason", [
    ("氏名", "", "必要な値が空"),
    ("支給合計", "1,200", "数字でない"),
    ("支給合計", "１２３４５６", "数字でない"),
    ("支給合計", "382000円", "数字でない"),
    ("差引支給額", "‐268700", "数字でない"),        # 符号が U+2010(ハイフンでない)
    ("社員番号", "00A123", "数字でない"),
    ("社員番号", "1234567", "桁あふれ"),
    ("氏名", "森本" + "郎" * 39, "桁あふれ"),
    ("氏名", "伊藤\r\n四郎", "改行が値の中にある"),
    ("氏名", "伊藤\n四郎", "改行が値の中にある"),
    ("氏名", '渡辺"五郎"', "引用符が値の中にある"),
    ("部署", "営業部,第一課", "区切り文字が値の中にある"),
    ("氏名", "中村😀六郎", "cp932 に無い文字"),
    ("氏名", "吉田𠮷郎", "cp932 に無い文字"),
    ("部署", "経費½部", "cp932 に無い文字"),
    ("部署", "開発部〜第二", "書いて読むと別の文字になる"),   # U+301C → 読み戻すと U+FF5E
    ("部署", "開発部−第二", "書いて読むと別の文字になる"),   # U+2212 → 読み戻すと U+FF0D
])
def test_value_is_pending(col, value, reason):
    c = next(x for x in SPEC.columns if x.name == col)
    p = I.check_value(c, value, 7)
    assert p is not None and (p.reason, p.row, p.column) == (reason, 7, col)
    assert p.note == I.REASONS[reason]


def test_every_reason_has_a_note():
    assert len(I.REASONS) == 8
    assert all(v for v in I.REASONS.values())


def test_wave_dash_is_encodable_but_not_the_same_字():
    """cp932 に書けることと、読み戻して同じ字になることは別(多対一の対応がある)。"""
    assert "〜".encode("cp932") == "～".encode("cp932")
    assert "〜".encode("cp932").decode("cp932") == "～" != "〜"


# ---- 読み戻し --------------------------------------------------------------------------------

def test_read_back_does_not_interpret_quotes(tmp_path):
    p = tmp_path / "x.csv"
    p.write_bytes('氏名,部署\r\n"山田,太郎",営業部\r\n'.encode("cp932"))
    assert I.read_back(p) == [["氏名", "部署"], ['"山田', '太郎"', "営業部"]]


def test_read_back_requires_crlf(tmp_path):
    p = tmp_path / "x.csv"
    p.write_bytes("氏名\n山田\n".encode("cp932"))
    with pytest.raises(ValueError):
        I.read_back(p)


def test_read_back_stops_on_undecodable_bytes(tmp_path):
    p = tmp_path / "x.csv"
    p.write_bytes(b"\x81\x20\r\n")
    with pytest.raises(UnicodeDecodeError):
        I.read_back(p)


def test_read_back_of_empty_file(tmp_path):
    p = tmp_path / "x.csv"
    p.write_bytes(b"")
    assert I.read_back(p) == []


# ---- 書く(通ったものだけ渡す) ----------------------------------------------------------------

def test_write_ok(tmp_path):
    out = tmp_path / "out.csv"
    r = I.write(out, SPEC, [one(), one(社員番号="42", 氏名="鈴木花子", 部署="")])
    assert r.ok and r.written and r.count == 2 and r.diffs == () and r.pending == ()
    assert r.totals == {"支給合計": "764000", "控除合計": "122400", "差引支給額": "641600"}
    raw = out.read_bytes()
    assert raw.endswith(b"\r\n") and b'"' not in raw
    assert raw.decode("cp932").splitlines()[1].startswith("100001,")
    assert I.read_back(out)[2][0] == "000042"        # 先頭ゼロが残っている


def test_write_makes_no_file_when_pending(tmp_path):
    out = tmp_path / "out.csv"
    r = I.write(out, SPEC, [one(), one(部署="営業部,第一課")])
    assert not r.written and not r.ok and len(r.pending) == 1
    assert r.pending[0].reason == "区切り文字が値の中にある" and r.pending[0].row == 2
    assert list(tmp_path.iterdir()) == []            # 作業ファイルも残さない


def test_write_deletes_the_work_file_when_the_readback_differs(tmp_path, monkeypatch):
    """検査を通っても、読み戻しが合わなければ渡さない(書き出しの段が壊れた場合の関所)。"""
    real = I._write_lines

    def broken(path, spec, lines):
        real(path, spec, [list(line) for line in lines][:-1])   # 1 行落として書く

    monkeypatch.setattr(I, "_write_lines", broken)
    out = tmp_path / "out.csv"
    r = I.write(out, SPEC, [one(), one(社員番号="100002")])
    assert not r.written and not out.exists() and list(tmp_path.iterdir()) == []
    assert [(d.row, d.column, d.original, d.readback) for d in r.diffs][0] == (0, "件数", "2", "1")


def test_write_reports_totals_difference(tmp_path, monkeypatch):
    real = I._write_lines

    def broken(path, spec, lines):
        changed = [list(line) for line in lines]
        changed[0][3] = "382001"
        real(path, spec, changed)

    monkeypatch.setattr(I, "_write_lines", broken)
    r = I.write(tmp_path / "out.csv", SPEC, [one()])
    cols = [d.column for d in r.diffs]
    assert "支給合計" in cols and not r.written
    assert any(d.row == 1 and d.original == "382000" and d.readback == "382001" for d in r.diffs)


def test_write_of_zero_rows(tmp_path):
    out = tmp_path / "out.csv"
    r = I.write(out, SPEC, [])
    assert r.ok and r.count == 0 and I.read_back(out) == [list(SPEC.names)]


def test_no_replacement_character_outside_the_comparison_helper():
    """本番の経路に errors='replace' が無いこと(化けたまま書き進める道を持たない)。"""
    src = (ROOT / "intake_csv.py").read_text(encoding="utf-8")
    assert src.count('errors="replace"') == 1        # naive_write(比較用)の 1 か所だけ
    assert 'errors="strict"' in src
    for word in ("difflib", "SequenceMatcher", "threshold", "しきい値", 'errors="ignore"'):
        assert word not in src, word


# ---- 比較用の素朴な書き出し(差が読み戻しで見えること) ----------------------------------------

def test_naive_write_hides_the_replacement(tmp_path):
    out = tmp_path / "naive.csv"
    rows = [one(氏名="中村😀六郎")]
    I.naive_write(out, SPEC, rows)
    assert "?" in out.read_bytes().decode("cp932")          # 書いた側では例外にならない
    lines, _p, _d = I.check_rows(SPEC, rows)
    diffs = I.verify(out, SPEC, lines)
    assert [(d.row, d.column) for d in diffs] == [(1, "氏名")]
    assert diffs[0].readback == "中村?六郎"


def test_naive_write_shifts_the_columns(tmp_path):
    out = tmp_path / "naive.csv"
    rows = [one(部署="営業部,第一課")]
    I.naive_write(out, SPEC, rows)
    lines, _p, _d = I.check_rows(SPEC, rows)
    diffs = I.verify(out, SPEC, lines)
    assert ("列数", "6", "7") == (diffs[0].column, diffs[0].original, diffs[0].readback)
    assert any(d.column == "差引支給額" for d in diffs)      # 後ろの列が 1 つずれる


def test_naive_write_breaks_the_row_count(tmp_path):
    out = tmp_path / "naive.csv"
    rows = [one(氏名="伊藤\r\n四郎"), one(社員番号="100002")]
    I.naive_write(out, SPEC, rows)
    lines, _p, _d = I.check_rows(SPEC, rows)
    diffs = I.verify(out, SPEC, lines)
    assert diffs[0] == I.Diff(0, "件数", "2", "3")


# ---- fixture(合成した支給控除一覧 17 行) ----------------------------------------------------

def test_fixture_rows_match_their_expected_reason():
    rows = rows_of(FX / "shikyu_koujo.csv")
    assert len(rows) == 17
    _lines, pending, dropped = I.check_rows(SPEC, rows)
    assert dropped == ["備考", "期待"]
    by_row: dict[int, list[str]] = {}
    for p in pending:
        by_row.setdefault(p.row, []).append(p.reason)
    for i, r in enumerate(rows, 1):
        got = by_row.get(i, [])
        assert got == ([r["期待"]] if r["期待"] else []), (i, r["氏名"], got)
    assert len(pending) == 12 and len(set(p.reason for p in pending)) == 8


def test_fixture_clean_rows_round_trip(tmp_path):
    rows = [r for r in rows_of(FX / "shikyu_koujo.csv") if not r["期待"]]
    out = tmp_path / "out.csv"
    r = I.write(out, SPEC, rows)
    assert r.ok and r.count == 5
    assert r.totals == {"支給合計": "1616500", "控除合計": "562600", "差引支給額": "1053900"}
    assert I.verify(out, SPEC, I.check_rows(SPEC, rows)[0]) == []


# ---- CLI ------------------------------------------------------------------------------------

def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "intake_csv.py"), *args],
                          capture_output=True, text=True, encoding="utf-8")


def test_cli_check_exits_3_and_lists_reasons():
    r = run_cli(str(FX / "shikyu_koujo.csv"), "--spec", str(FX / "retsu_shiyou.csv"), "--check")
    assert r.returncode == 3
    assert "検査 17 行 / 判断待ち 12 件" in r.stderr
    assert "6\t部署\t区切り文字が値の中にある" in r.stdout
    assert "仕様に無い列(書かない): 備考" in r.stderr


def test_cli_write_exits_3_when_pending(tmp_path):
    out = tmp_path / "out.csv"
    r = run_cli(str(FX / "shikyu_koujo.csv"), str(out), "--spec", str(FX / "retsu_shiyou.csv"))
    assert r.returncode == 3 and not out.exists()
    assert "判断待ち 12 件" in r.stderr


def test_cli_write_exits_0(tmp_path):
    src, out = tmp_path / "src.csv", tmp_path / "out.csv"
    with src.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, list(SPEC.names))
        w.writeheader()
        w.writerow(one())
    r = run_cli(str(src), str(out), "--spec", str(FX / "retsu_shiyou.csv"))
    assert r.returncode == 0 and out.exists()
    assert "書いて読み戻して一致: 1 行" in r.stderr and "支給合計 382000" in r.stderr


def test_cli_missing_column_exits_2(tmp_path):
    src = tmp_path / "src.csv"
    src.write_text("社員番号,氏名\n100001,山田太郎\n", encoding="utf-8")
    r = run_cli(str(src), str(tmp_path / "out.csv"), "--spec", str(FX / "retsu_shiyou.csv"))
    assert r.returncode == 2 and "列がデータに無い" in r.stderr


def test_cli_broken_spec_exits_2(tmp_path):
    spec = tmp_path / "spec.csv"
    spec.write_text("見出し,型,桁,ゼロ埋め,空を許す,合計\n氏名,日付,0,,,\n", encoding="utf-8")
    r = run_cli(str(FX / "shikyu_koujo.csv"), str(tmp_path / "out.csv"), "--spec", str(spec))
    assert r.returncode == 2 and "型が表に無い" in r.stderr


# ---- 合成 1,000 行での比較(固定 seed。記事の数値はここから) --------------------------------

SEED = 20260926
N = 1000

SEI = "山田 鈴木 高橋 田中 伊藤 渡辺 中村 小林 加藤 吉田 松本 森本 岩崎 川口 三好 平野 福井 秋山 白石 黒田".split()
MEI = "太郎 花子 一郎 次郎 三郎 四郎 五郎 六郎 七郎 八郎 九郎 十郎 詩織 陽子 直樹 健一 美咲 沙織 拓也 亮".split()
BUSHO = "営業部 総務部 製造部 管理部 経理部 開発部 品質部 物流部 購買部 情報部".split()

# 1 行につき 1 か所だけ仕込む。合計 50 行(残り 950 行はそのまま書ける)
INJECT = (("区切り文字が値の中にある", 12), ("cp932 に無い文字", 8), ("改行が値の中にある", 7),
          ("書いて読むと別の文字になる", 6), ("数字でない", 6), ("引用符が値の中にある", 5),
          ("桁あふれ", 4), ("必要な値が空", 2))
PENDING_ROWS = sum(n for _r, n in INJECT)


def build_rows(seed: int = SEED) -> list[dict[str, str]]:
    """支給控除一覧を 1,000 行合成する。金額も氏名も架空。仕込みは行番号で決まる。"""
    rng = random.Random(seed)
    plan: dict[int, str] = {}
    picks = rng.sample(range(N), PENDING_ROWS)
    at = 0
    for reason, count in INJECT:
        for p in picks[at:at + count]:
            plan[p] = reason
        at += count
    rows = []
    for i in range(N):
        shikyu = 200000 + rng.randrange(0, 2600) * 100
        koujo = 30000 + rng.randrange(0, 500) * 100
        row = {"社員番号": str(100001 + i), "氏名": rng.choice(SEI) + rng.choice(MEI),
               "部署": rng.choice(BUSHO), "支給合計": str(shikyu), "控除合計": str(koujo),
               "差引支給額": str(shikyu - koujo)}
        reason = plan.get(i)
        if reason == "区切り文字が値の中にある":
            row["部署"] += ",第一課"
        elif reason == "cp932 に無い文字":
            row["氏名"] = row["氏名"][:2] + "😀" + row["氏名"][2:]
        elif reason == "改行が値の中にある":
            row["氏名"] = row["氏名"][:2] + "\r\n" + row["氏名"][2:]
        elif reason == "書いて読むと別の文字になる":
            row["部署"] += "〜第二"                                  # U+301C
        elif reason == "数字でない":
            row["支給合計"] = f"{shikyu:,}"
        elif reason == "引用符が値の中にある":
            row["氏名"] = '"' + row["氏名"] + '"'
        elif reason == "桁あふれ":
            row["社員番号"] = "1" + row["社員番号"]
        elif reason == "必要な値が空":
            row["氏名"] = ""
        rows.append(row)
    return rows


def summarize(diffs: list[I.Diff]) -> dict[str, int]:
    return {"差": len(diffs), "巻き込まれた行": len({d.row for d in diffs if d.row}),
            "件数と合計の差": len([d for d in diffs if d.row == 0])}


def test_measure_rows_are_built_as_declared():
    """合成の内訳を固定する(内訳が変われば記事の数字も変える)。"""
    rows = build_rows()
    assert len(rows) == N
    _lines, pending, dropped = I.check_rows(SPEC, rows)
    assert dropped == []
    counts: dict[str, int] = {}
    for p in pending:
        counts[p.reason] = counts.get(p.reason, 0) + 1
    assert counts == dict(INJECT)
    assert len(pending) == PENDING_ROWS == 50
    assert len({p.row for p in pending}) == 50       # 1 行に 1 か所だけ


def test_measure_naive_write(tmp_path):
    """検査も読み戻しもしない書き出しは、1,000 行すべてを書き切る。壊れ方は取込側で出る。"""
    rows = build_rows()
    out = tmp_path / "naive.csv"
    assert I.naive_write(out, SPEC, rows) == N
    lines, _p, _d = I.check_rows(SPEC, rows)
    got = I.read_back(out)
    diffs = I.verify(out, SPEC, lines)
    s = summarize(diffs)
    off = {d.column: (Decimal(d.readback) - Decimal(d.original)) for d in diffs
           if d.row == 0 and d.column in SPEC.total_names}
    print(f"\n[measure] naive write: {N} rows out, read back {len(got) - 1} lines, "
          f"diffs {s['差']}, rows dragged in {s['巻き込まれた行']}, totals off {off}")
    # 記事に載せた値。固定 seed(20260926)で決定論的に再現する。変わったら記事の数字も変える
    assert (len(got) - 1, s["差"], s["巻き込まれた行"]) == (1007, 5590, 950)
    assert off == {"支給合計": Decimal("-5707000"), "控除合計": Decimal("-1331900"),
                   "差引支給額": Decimal("-6528200")}
    assert min(d.row for d in diffs if d.row) == 17        # 最初に差が出た行
    assert sorted({d.row for d in diffs if d.row})[-1] == N


def test_measure_this_tool_writes_nothing_when_pending(tmp_path):
    """この部品は 50 行の判断待ちを返し、出力ファイルを 1 つも作らない。"""
    out = tmp_path / "out.csv"
    r = I.write(out, SPEC, build_rows())
    print(f"[measure] this tool: pending {len(r.pending)} rows, files written {len(list(tmp_path.iterdir()))}")
    assert len(r.pending) == 50 and not r.written
    assert list(tmp_path.iterdir()) == []


def test_measure_this_tool_after_the_pending_rows_are_removed(tmp_path):
    """判断待ちの 50 行を外した 950 行は、書けて、読み戻しも全セル一致する。"""
    rows = build_rows()
    _lines, pending, _d = I.check_rows(SPEC, rows)
    bad = {p.row for p in pending}
    kept = [r for i, r in enumerate(rows, 1) if i not in bad]
    out = tmp_path / "out.csv"
    r = I.write(out, SPEC, kept)
    got = I.read_back(out)
    print(f"[measure] this tool, {len(bad)} pending rows removed: wrote {r.count} rows, "
          f"read back {len(got) - 1} rows, diffs {len(r.diffs)}, totals {r.totals}")
    assert len(kept) == 950 and r.ok and r.count == 950 and len(got) - 1 == 950
    assert r.totals == {"支給合計": "314404600", "控除合計": "52586100", "差引支給額": "261818500"}
    assert I.verify(out, SPEC, I.check_rows(SPEC, kept)[0]) == []
