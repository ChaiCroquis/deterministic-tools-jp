"""source_pin のテスト。fixture は全て合成データ(fixtures/make_fixtures.py)、地域名も値も出典名も架空。

後半の test_measure_* が記事の数値の出どころ。
  measure_pins      合成の原本 5 種に張った 13 本のピンを検査し、通った / 取れない / 止まったを数える
  measure_tampering 原本とピンの表を 1 か所ずつ書き換え、検査が止めるかを数える
  measure_map       原本の種類 × 取り出し方の対応表(記事の図 2 はこの出力をそのまま使う)
決定論なので、値が変われば記事の数字も変える。
"""
from __future__ import annotations

import inspect
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FX))
import make_fixtures as MF  # noqa: E402
import source_pin as SP  # noqa: E402

PINS = FX / "pins.csv"


def table() -> SP.PinTable:
    return SP.PinTable.load(PINS)


def _row(rows: list, key: str) -> dict:
    return next(r for r in rows if r["key"] == key)


def prepare(d: Path) -> list:
    """合成の原本とピンの表を d に作り、ピン行の list を返す。"""
    rows = MF.rows_pins(d)
    MF.write_pins(d / "pins.csv", rows)
    return rows


# ---------------------------------------------------------------- 正規化(既定を持たない)

def test_normalizers_are_named_not_guessed() -> None:
    assert set(SP.NORMALIZERS) == {"そのまま", "全角半角", "カンマ除去", "パーセント", "円", "日付"}
    assert SP.normalize("  9.98 ", "そのまま") == "9.98"
    assert SP.normalize("１，２３０，０００円", "全角半角+カンマ除去+円") == "1230000"
    assert SP.normalize("1.60%", "パーセント") == "1.60"
    assert SP.normalize("7,294円", "カンマ除去+円") == "7294"
    assert SP.normalize("2027年8月1日", "日付") == "2027-08-01"
    assert SP.normalize("2027/8/1", "日付") == "2027-08-01"


def test_unknown_normalizer_name_is_an_error() -> None:
    with pytest.raises(ValueError, match="登録されていない normalizer"):
        SP.normalize("9.98", "よくある正規化")
    assert not SP.known_chain("")
    assert not SP.known_chain("そのまま+よくある正規化")
    assert SP.known_chain("全角半角+円")


def test_normalizer_keeps_trailing_zero_as_written() -> None:
    """1.60% を 1.6 に丸めない(原本の桁をそのまま value にする)。"""
    assert SP.normalize("1.60%", "パーセント") == "1.60"
    assert SP.normalize("1.6%", "パーセント") == "1.6"


def test_date_normalizer_rejects_what_it_cannot_read() -> None:
    for bad in ["令和9年8月1日", "2027年8月", "8月1日"]:
        with pytest.raises(ValueError):
            SP.normalize(bad, "日付")


# ---------------------------------------------------------------- 原本を読む

def test_xlsx_cell_reads_shared_strings_and_numbers() -> None:
    p = FX / "genpon_ryouritsu.xlsx"
    assert SP.read_xlsx_cell(p, "料率!A3") == "地域I"
    assert SP.read_xlsx_cell(p, "料率!B3") == "9.98"
    assert SP.read_xlsx_cell(p, "料率!C3") == "１，２３０，０００円"
    assert SP.read_xlsx_cell(p, "料率!C4") == "650000"


def test_xlsx_cell_locator_out_of_range() -> None:
    p = FX / "genpon_ryouritsu.xlsx"
    with pytest.raises(SP.LocatorError, match="シートが無い"):
        SP.read_xlsx_cell(p, "別のシート!B3")
    with pytest.raises(SP.LocatorError, match="セルが無い"):
        SP.read_xlsx_cell(p, "料率!Z99")
    with pytest.raises(SP.LocatorError, match="シート名"):
        SP.read_xlsx_cell(p, "B3")


def test_text_line_reads_the_numbered_line() -> None:
    p = FX / "genpon_gendogaku.txt"
    assert SP.read_text_line(p, "7") == "  区分B  上限 7,294円"
    assert SP.read_text_line(p, "13") == "改定日 2027年8月1日"
    with pytest.raises(SP.LocatorError, match="範囲外"):
        SP.read_text_line(p, "99")


def test_html_text_lines_drop_empty_lines() -> None:
    lines = SP.html_text_lines(FX / "genpon_nissu.html")
    assert lines == ["合成(架空)の日数表", "区分ごとの日数(合成・架空)", "区分", "日数",
                     "区分A", "90", "区分B", "120",
                     "この表には適用開始日が書かれていない(合成データ)。"]
    assert SP.read_html_line(FX / "genpon_nissu.html", "6") == "90"


def test_pdf_is_not_read_by_this_part() -> None:
    """PDF は自前で読まない。テキストを受けるだけで、画像だけの PDF は unavailable の行になる。"""
    assert "pdf" not in " ".join(SP.METHODS)
    pdf_pins = [p for p in table().pins if p.source_file.endswith(".pdf")]
    assert pdf_pins and all(p.method == "unavailable" for p in pdf_pins)


# ---------------------------------------------------------------- 表とピン

def test_pin_table_shape() -> None:
    t = table()
    assert len(t) == 13
    assert [p.method for p in t.pins].count("unavailable") == 3
    assert [p.method for p in t.pins].count("manual") == 2


def test_missing_header_column_is_a_table_error(tmp_path: Path) -> None:
    p = tmp_path / "pins.csv"
    p.write_text("key,value\n料率_地域I,9.98\n", encoding="utf-8")
    with pytest.raises(SP.TableError, match="見出しの列が足りない"):
        SP.PinTable.load(p)


def test_pin_table_also_loads_json(tmp_path: Path) -> None:
    rows = prepare(tmp_path)
    p = tmp_path / "pins.json"
    p.write_text(json.dumps({"pins": rows}, ensure_ascii=False), encoding="utf-8")
    t = SP.PinTable.load(p)
    assert len(t) == 13
    assert SP.summary(SP.verify(t))["failed"] == 0


def test_broken_json_is_a_table_error(tmp_path: Path) -> None:
    p = tmp_path / "pins.json"
    p.write_text("これは JSON ではない", encoding="utf-8")
    with pytest.raises(SP.TableError, match="JSON"):
        SP.PinTable.load(p)


# ---------------------------------------------------------------- 検査

def test_every_pin_passes_on_the_untouched_fixtures() -> None:
    s = SP.summary(SP.verify(table()))
    assert s == {"pins": 13, "verified": 10, "transcribed": 2, "unavailable": 3,
                 "failed": 0, "by_reason": {}}


def test_unavailable_rows_stay_in_the_table() -> None:
    """取れない原本は消えずに 1 行として残り、値は空のまま。"""
    rows = [p for p in table().pins if p.method == "unavailable"]
    assert len(rows) == 3
    assert all(p.value == "" and p.raw_text == "" for p in rows)
    assert [r.status for r in SP.verify(table()) if r.method == "unavailable"] == \
           ["unavailable"] * 3


def test_unavailable_with_a_value_stops(tmp_path: Path) -> None:
    rows = prepare(tmp_path)
    _row(rows, "乗率_世代I")["value"] = "7.125"
    MF.write_pins(tmp_path / "pins.csv", rows)
    r = {x.key: x for x in SP.verify(SP.PinTable.load(tmp_path / "pins.csv"))}["乗率_世代I"]
    assert r.reason == "unavailable なのに value がある"


def test_blank_normalizer_stops_without_evaluating(tmp_path: Path) -> None:
    """normalizer 空欄の行は、生の文字が合っていても評価せずに止める。"""
    rows = prepare(tmp_path)
    _row(rows, "等級上限")["normalizer"] = ""
    MF.write_pins(tmp_path / "pins.csv", rows)
    r = {x.key: x for x in SP.verify(SP.PinTable.load(tmp_path / "pins.csv"))}["等級上限"]
    assert r.reason == "normalizer 空欄"


def test_manual_rows_carry_a_transcription_mark() -> None:
    marked = [r.key for r in SP.verify(table()) if r.transcribed]
    assert marked == ["日数_適用開始日", "来年度の配布ページ"]
    assert SP.get(table(), "日数_適用開始日").transcribed is True
    assert SP.get(table(), "料率_地域I").transcribed is False


def test_xlsx_grounding_is_equality_not_substring(tmp_path: Path) -> None:
    """セルは 1 値なので、部分一致では接地と認めない(19.98 に 9.98 が混じるのを防ぐ)。"""
    rows = prepare(tmp_path)
    _row(rows, "料率_地域I")["raw_text"] = "9.9"
    _row(rows, "料率_地域I")["value"] = "9.9"
    MF.write_pins(tmp_path / "pins.csv", rows)
    r = {x.key: x for x in SP.verify(SP.PinTable.load(tmp_path / "pins.csv"))}["料率_地域I"]
    assert r.reason == "生の文字が指定場所に無い"


def test_eight_reason_codes_and_no_more() -> None:
    assert len(SP.REASONS) == 8
    assert set(SP.REASONS) == {
        "原本の sha が違う", "locator が範囲外", "生の文字が指定場所に無い", "normalizer 空欄",
        "normalizer を通しても value と合わない", "unavailable なのに value がある",
        "同じ key が 2 行", "列が足りない"}


# ---------------------------------------------------------------- 引き当て(落ちる経路が無い)

def test_get_has_no_fallback_arguments() -> None:
    """近い key・前年・直近へ落ちる引数を持たないこと(引数の形で固定する)。"""
    assert list(inspect.signature(SP.get).parameters) == ["table", "key"]


def test_get_stops_instead_of_falling_back() -> None:
    t = table()
    with pytest.raises(SP.PinError) as e1:
        SP.get(t, "乗率_世代I")
    assert e1.value.reason == "unavailable"
    with pytest.raises(SP.PinError) as e2:
        SP.get(t, "料率_地域III")           # 近い key に落ちない
    assert e2.value.reason == "台帳に無い"
    assert SP.get(t, "料率_地域I").value == "9.98"


def test_get_stops_on_a_failed_row(tmp_path: Path) -> None:
    rows = prepare(tmp_path)
    _row(rows, "改定日")["raw_text"] = "2027年9月1日"
    MF.write_pins(tmp_path / "pins.csv", rows)
    with pytest.raises(SP.PinError) as e:
        SP.get(SP.PinTable.load(tmp_path / "pins.csv"), "改定日")
    assert e.value.reason == "生の文字が指定場所に無い"


def test_get_returns_where_the_value_came_from() -> None:
    g = SP.get(table(), "上限額_地域I")
    assert g.value == "1230000" and g.raw_text == "１，２３０，０００円"
    assert g.locator == "料率!C3" and g.method == "xlsx_cell"
    assert g.source_sha256 == SP.sha256_of(FX / "genpon_ryouritsu.xlsx")


# ---------------------------------------------------------------- 地図

def test_map_keeps_what_cannot_be_taken() -> None:
    m = SP.source_map(table())
    assert m["categories"] == ["機械で取り出せる", "人が転記するしかない", "取れない"]
    assert m["kinds"] == ["表形式の xlsx", "テキスト層のある PDF", "日付の無い HTML",
                          "画像だけの PDF", "URL が変わる配布元"]
    assert m["totals"] == {"機械で取り出せる": 8, "人が転記するしかない": 2, "取れない": 3}
    assert m["cells"]["画像だけの PDF"]["取れない"]["count"] == 2
    assert m["cells"]["URL が変わる配布元"]["取れない"]["keys"] == ["来年度の数表"]


def test_map_puts_rows_without_a_kind_in_a_named_bucket(tmp_path: Path) -> None:
    rows = prepare(tmp_path)
    _row(rows, "等級上限")["source_kind"] = ""
    MF.write_pins(tmp_path / "pins.csv", rows)
    m = SP.source_map(SP.PinTable.load(tmp_path / "pins.csv"))
    assert SP.NO_KIND in m["kinds"]
    assert m["cells"][SP.NO_KIND]["機械で取り出せる"]["count"] == 1


# ---------------------------------------------------------------- 測定(記事の数字)

def measure_pins() -> dict:
    t = table()
    results = SP.verify(t)
    grounded = 0
    for p in t.pins:
        if p.method not in SP.MACHINE:
            continue
        place = SP.READERS[p.method](t.path_of(p), p.locator)
        if (place == p.raw_text) if p.method == "xlsx_cell" else (p.raw_text in place):
            grounded += 1
    s = SP.summary(results)
    s["machine"] = sum(1 for r in results if r.method in SP.MACHINE and r.ok)
    s["grounded"] = grounded
    s["kinds"] = len(SP.source_map(t)["kinds"])
    return s


def _tamper_cases() -> dict:
    """原本とピンの表を 1 か所ずつ書き換える。値 = (書き換える関数, 見る key)。"""
    def pin(key: str, **sets):
        def go(d: Path, rows: list) -> None:
            _row(rows, key).update(sets)
        return go, key

    def touch_original(key: str, name: str):
        def go(d: Path, rows: list) -> None:
            (d / name).write_bytes((d / name).read_bytes() + b"\n")
        return go, key

    def drop_original(key: str, name: str):
        def go(d: Path, rows: list) -> None:
            (d / name).unlink()
        return go, key

    def duplicate(key: str):
        def go(d: Path, rows: list) -> None:
            rows.append(dict(_row(rows, key)))
        return go, key

    return {
        "原本の xlsx を書き換える": touch_original("料率_地域I", "genpon_ryouritsu.xlsx"),
        "ピンの sha256 列を書き換える": pin("等級上限", source_sha256="0" * 64),
        "原本のファイルを消す": drop_original("上限額_区分B", "genpon_gendogaku.txt"),
        "manual の行の原本を書き換える": touch_original("来年度の配布ページ", "haifu_kiroku.txt"),
        "locator のシート名を変える": pin("料率_地域II", locator="別のシート!B4"),
        "locator のセルを原本の外にする": pin("上限額_地域I", locator="料率!Z99"),
        "text_line の行番号を原本の行数より大きくする": pin("賃金日額_下限", locator="99"),
        "html_text の行番号を 0 にする": pin("日数_区分A", locator="0"),
        "raw_text を 1 文字変える": pin("改定日", raw_text="2027年9月1日"),
        "locator を別の行にずらす": pin("上限額_区分B", locator="6"),
        "xlsx の raw_text を部分文字列にする": pin("料率_地域I", raw_text="9.9", value="9.9"),
        "normalizer を空欄にする": pin("上限額_地域I", normalizer=""),
        "登録されていない normalizer 名にする": pin("賃金日額_下限", normalizer="よくある正規化"),
        "captured_at を空にする": pin("日数_区分A", captured_at=""),
        "value を 1 桁変える": pin("等級上限", value="65000"),
        "normalizer を そのまま に変える": pin("上限額_地域I", normalizer="そのまま"),
        "unavailable の行に value を入れる": pin("乗率_世代I", value="7.125"),
        "同じ key の行を 2 行にする": duplicate("料率_地域II"),
        "manual の生の文字と value を揃えて書き換える":
            pin("日数_適用開始日", raw_text="2020-04-01", value="2020-04-01"),
    }


def measure_tampering(tmp_path: Path) -> dict:
    out: dict = {}
    for i, (name, (mutate, key)) in enumerate(_tamper_cases().items()):
        d = tmp_path / f"case{i:02d}"
        rows = prepare(d)
        mutate(d, rows)
        MF.write_pins(d / "pins.csv", rows)
        results = SP.verify(SP.PinTable.load(d / "pins.csv"))
        hit = next(r for r in results if r.key == key)
        out[name] = hit.reason
    return {"cases": len(out), "stopped": sum(1 for v in out.values() if v), "by_case": out}


def measure_map() -> dict:
    m = SP.source_map(table())
    return {"kinds": m["kinds"], "totals": m["totals"],
            "grid": {k: {c: m["cells"][k][c]["count"] for c in m["categories"]}
                     for k in m["kinds"]}}


def test_measure_pins(capsys: pytest.CaptureFixture) -> None:
    m = measure_pins()
    assert m["pins"] == 13 and m["verified"] == 10 and m["unavailable"] == 3 and m["failed"] == 0
    assert m["machine"] == 8 and m["transcribed"] == 2 and m["grounded"] == 8
    assert m["kinds"] == 5
    with capsys.disabled():
        print(f"\n[measure] 原本 {m['kinds']} 種に張ったピン {m['pins']} 本: "
              f"検査を通った {m['verified']} 本(機械で接地 {m['machine']} 本 / 転記の印 {m['transcribed']} 本)"
              f" / 取れない {m['unavailable']} 本 / 止まった {m['failed']} 本")
        print(f"[measure] 機械で取り出した {m['machine']} 本すべてで、生の文字が原本の指定場所に "
              f"literal で在った({m['grounded']}/{m['machine']})")


def test_measure_tampering(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    m = measure_tampering(tmp_path)
    assert m["cases"] == 19 and m["stopped"] == 18
    assert m["by_case"]["manual の生の文字と value を揃えて書き換える"] == ""
    assert m["by_case"]["原本の xlsx を書き換える"] == "原本の sha が違う"
    assert m["by_case"]["manual の行の原本を書き換える"] == "原本の sha が違う"
    assert m["by_case"]["locator を別の行にずらす"] == "生の文字が指定場所に無い"
    assert m["by_case"]["normalizer を空欄にする"] == "normalizer 空欄"
    assert m["by_case"]["登録されていない normalizer 名にする"] == "列が足りない"
    assert m["by_case"]["同じ key の行を 2 行にする"] == "同じ key が 2 行"
    # 8 つの理由コードすべてに到達している
    assert {v for v in m["by_case"].values() if v} == set(SP.REASONS)
    with capsys.disabled():
        print(f"\n[measure] 原本とピンの表を 1 か所ずつ書き換えた {m['cases']} 通り: "
              f"検査が止めた {m['stopped']} 通り"
              f"(止められなかった 1 通り = manual の生の文字と value を揃えて書き換える)")
        for k, v in m["by_case"].items():
            print(f"[measure]   {k} → {v or '(止まらない)'}")


def test_measure_map(capsys: pytest.CaptureFixture) -> None:
    m = measure_map()
    assert m["totals"] == {"機械で取り出せる": 8, "人が転記するしかない": 2, "取れない": 3}
    assert m["grid"] == {
        "表形式の xlsx": {"機械で取り出せる": 4, "人が転記するしかない": 0, "取れない": 0},
        "テキスト層のある PDF": {"機械で取り出せる": 3, "人が転記するしかない": 0, "取れない": 0},
        "日付の無い HTML": {"機械で取り出せる": 1, "人が転記するしかない": 1, "取れない": 0},
        "画像だけの PDF": {"機械で取り出せる": 0, "人が転記するしかない": 0, "取れない": 2},
        "URL が変わる配布元": {"機械で取り出せる": 0, "人が転記するしかない": 1, "取れない": 1}}
    with capsys.disabled():
        print("\n[measure] 原本の種類 × 取り出し方(map の出力そのまま)")
        for k, row in m["grid"].items():
            print(f"[measure]   {k}: 機械 {row['機械で取り出せる']} / "
                  f"人が転記 {row['人が転記するしかない']} / 取れない {row['取れない']}")


# ---------------------------------------------------------------- CLI

def cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "source_pin.py"), *args],
                          capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT))


def test_cli_verify_exits_zero_on_the_fixtures() -> None:
    r = cli("verify", str(PINS))
    assert r.returncode == 0
    d = json.loads(r.stdout.strip())
    assert d["ok"] is True and d["pins"] == 13 and d["verified"] == 10 and d["unavailable"] == 3


def test_cli_verify_exits_three_when_a_pin_stops(tmp_path: Path) -> None:
    rows = prepare(tmp_path)
    _row(rows, "料率_地域I")["source_sha256"] = "0" * 64
    MF.write_pins(tmp_path / "pins.csv", rows)
    r = cli("verify", str(tmp_path / "pins.csv"))
    assert r.returncode == 3
    assert json.loads(r.stdout.strip())["by_reason"] == {"原本の sha が違う": 1}


def test_cli_get_exits_three_on_an_unavailable_key() -> None:
    r = cli("get", str(PINS), "乗率_世代I")
    assert r.returncode == 3
    assert json.loads(r.stdout.strip())["reason"] == "unavailable"
    assert cli("get", str(PINS), "料率_地域I").returncode == 0


def test_cli_map_prints_the_grid() -> None:
    d = json.loads(cli("map", str(PINS)).stdout.strip())
    assert d["totals"]["取れない"] == 3 and len(d["kinds"]) == 5


def test_cli_init_writes_the_header(tmp_path: Path) -> None:
    out = tmp_path / "new.csv"
    assert cli("init", str(out)).returncode == 0
    t = SP.PinTable.load(out)
    assert len(t) == 1 and t.pins[0].method == "unavailable"
    assert cli("init", str(out)).returncode == 2       # 上書きしない


def test_cli_exits_two_on_an_unreadable_table(tmp_path: Path) -> None:
    p = tmp_path / "pins.csv"
    p.write_text("key,value\n料率,9.98\n", encoding="utf-8")
    r = cli("verify", str(p))
    assert r.returncode == 2 and "見出しの列が足りない" in r.stderr


# ---------------------------------------------------------------- fixture

def test_fixtures_on_disk_match_the_generator(tmp_path: Path) -> None:
    """合成 fixture が生成器から決定論的に出ること(ディスク上のファイルと突き合わせる)。"""
    rows = prepare(tmp_path)
    for name in ["genpon_ryouritsu.xlsx", "genpon_gendogaku.txt", "genpon_nissu.html",
                 "genpon_gazou.pdf", "haifu_kiroku.txt", "pins.csv"]:
        assert (tmp_path / name).read_bytes() == (FX / name).read_bytes(), name
    assert len(rows) == 13


def test_fixtures_hold_no_real_values() -> None:
    text = "".join((FX / n).read_text(encoding="utf-8") for n in
                   ["genpon_gendogaku.txt", "genpon_nissu.html", "haifu_kiroku.txt", "pins.csv"])
    text += SP.read_xlsx_cell(FX / "genpon_ryouritsu.xlsx", "料率!A1")
    assert "架空" in text
    for word in ["東京", "大阪", "北海道", "協会けんぽ", "厚生労働省", "年金機構", "ハローワーク"]:
        assert word not in text
