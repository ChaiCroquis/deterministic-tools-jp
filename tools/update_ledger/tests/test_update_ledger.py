"""update_ledger のテスト。fixture は全て合成データ(fixtures/make_fixtures.py)、地域名も値も出典名も架空。

後半の test_measure_* が記事の数値の出どころ。
  measure_operation  20 回の更新を合成の表で流し、止まった回に本番ファイルが動かないかを数える
  measure_tampering  出来上がった台帳を 1 か所ずつ書き換え、自己検査(replay)が止めるかを数える
  measure_diff       前回の表と今回の表の差分 6 種の件数
決定論なので、値が変われば記事の数字も変える。
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FX))
import make_fixtures as MF  # noqa: E402
import update_ledger as U  # noqa: E402

ZENKAI = FX / "hyou_zenkai.csv"
KONKAI = FX / "hyou_konkai.csv"
KASANARI = FX / "hyou_kasanari.csv"
ANA = FX / "hyou_ana.csv"
KYUHEN = FX / "hyou_kyuhen.csv"
TARINAI = FX / "hyou_retsu_tarinai.csv"

BASE = datetime(2026, 9, 21, 9, 0, 0, tzinfo=timezone.utc)
SOURCE_NAME = "取得元"


def stamp(i: int) -> str:
    return (BASE + timedelta(hours=6 * i)).isoformat()


def write_table(path: Path, rows: list) -> Path:
    MF.write(path, rows)
    return path


def fingerprint(tmp: Path, letter: str) -> U.Fingerprint:
    """取得したファイルの指紋。同じ letter なら同じ sha256 になる(= 同じものを取得した回)。"""
    p = tmp / f"torikomi_{letter}.txt"
    p.write_text(f"合成の取得ファイル {letter}\n", encoding="utf-8")
    return U.Fingerprint.of_file(SOURCE_NAME, p)


# ---------------------------------------------------------------- 表と差分

def test_zenkai_table_shape() -> None:
    t = U.Table.from_csv(ZENKAI)
    assert len(t) == 43
    assert t.dims == ("sel_地域",)
    assert [r["key"] for r in t.records].count("料率_甲") == 36


def test_konkai_table_shape() -> None:
    assert len(U.Table.from_csv(KONKAI)) == 47


def test_missing_column_is_a_table_error() -> None:
    with pytest.raises(U.TableError, match="source"):
        U.Table.from_csv(TARINAI)


def test_unreadable_date_is_a_table_error(tmp_path: Path) -> None:
    rows = [dict(r) for r in MF.rows_zenkai()]
    rows[0]["valid_from"] = "2026/03/01"
    p = write_table(tmp_path / "hizuke.csv", rows)
    with pytest.raises(U.TableError, match="valid_from"):
        U.Table.from_csv(p)


def test_first_run_counts_every_row_as_added() -> None:
    d = U.diff_tables(None, U.Table.from_csv(ZENKAI))
    assert d.counts["追加"] == 43
    assert d.rows_prev == 0 and d.changed == 0


def test_identity_includes_priority(tmp_path: Path) -> None:
    """同じ期間・同じ公表時点で本則と経過措置が並ぶ表。順位を識別に入れないと 2 行が同じ識別になる。"""
    def two(honsoku: str, keika: str) -> list:
        return [MF._row(key="支給率_丙", valid_from="2025-04-01", valid_to="",
                        known_from="2024-06-10", priority="0", value=honsoku, source="合成(架空)"),
                MF._row(key="支給率_丙", valid_from="2025-04-01", valid_to="",
                        known_from="2024-06-10", priority="10", value=keika, source="合成(架空)")]
    a = U.Table(two("10", "15"))
    b = U.Table(two("10", "12"))
    d = U.diff_tables(a, b)
    assert d.changed == 1
    assert d.counts["値の変更"] == 1 and d.counts["追加"] == 0 and d.counts["削除"] == 0


def test_unknown_column_change_counts_as_value_change() -> None:
    """GROUPS に無い列が動いたら、引き当てに効きうる側(値の変更)に数える。"""
    def one(kubun: str) -> list:
        r = MF._row(key="料率_甲", valid_from="2025-03-01", valid_to="", known_from="2025-02-05",
                    value="9.60", source="合成(架空)")
        r["区分"] = kubun
        return [r]
    d = U.diff_tables(U.Table(one("甲")), U.Table(one("乙")))
    assert d.counts["値の変更"] == 1 and d.changed == 1
    assert d.counts["出典欄の変更"] == 0


def test_valid_to_change_is_not_a_value_change() -> None:
    a = U.Table([MF._row(key="上限額_乙", valid_from="2026-04-01", valid_to="",
                         known_from="2026-02-01", value="9000", source="合成(架空)")])
    b = U.Table([MF._row(key="上限額_乙", valid_from="2026-04-01", valid_to="2027-04-01",
                         known_from="2026-02-01", value="9000", source="合成(架空)")])
    d = U.diff_tables(a, b)
    assert d.counts == {"追加": 0, "削除": 0, "値の変更": 0, "有効期間の変更": 1,
                        "公表時点の変更": 0, "出典欄の変更": 0}


# ---------------------------------------------------------------- 関所(表そのものの検査)

def test_validate_finds_overlap() -> None:
    found = U.validate_rows(U.Table.from_csv(KASANARI))
    assert [f.kind for f in found] == ["有効期間の重なり", "有効期間の重なり"]
    assert all(f.key == "料率_甲" for f in found)


def test_validate_finds_hole() -> None:
    found = U.validate_rows(U.Table.from_csv(ANA))
    assert [f.kind for f in found] == ["期間の穴"]
    assert "2025-04-01 〜 2025-10-01" in found[0].detail


def test_clean_tables_have_no_findings() -> None:
    assert U.validate_rows(U.Table.from_csv(ZENKAI)) == []
    assert U.validate_rows(U.Table.from_csv(KONKAI)) == []
    assert U.validate_rows(U.Table.from_csv(KYUHEN)) == []


def test_validate_ignores_rows_without_valid_from() -> None:
    """施行日が政令待ちの行は期間を持たないので、重なりにも穴にも数えない。"""
    rows = [dict(r) for r in MF.rows_zenkai()]
    rows.append(MF._row(key="上限額_乙", basis="請求日", valid_from="", valid_to="",
                        known_from="2026-06-13", value="撤廃", source="合成の改正法(架空、施行日は政令)"))
    assert U.validate_rows(U.Table(rows)) == []


# ---------------------------------------------------------------- record(1 回 = 1 行)

def one_run(tmp_path: Path, rows_or_path, letter: str, i: int, apply: bool = True,
            ledger: str = "daichou.jsonl", output: str = "honban.json"):
    led, out = tmp_path / ledger, tmp_path / output
    now = rows_or_path if isinstance(rows_or_path, Path) else write_table(tmp_path / f"now_{i}.csv", rows_or_path)
    return U.record(led, now, out if out.exists() else None, out,
                    (fingerprint(tmp_path, letter),), run_at=stamp(i), apply=apply)


def test_first_record_writes_one_line_and_applies(tmp_path: Path) -> None:
    e = one_run(tmp_path, ZENKAI, "A", 0)
    assert e.status == "ok" and e.applied and e.first_run
    assert e.counts["追加"] == 43 and e.rows_prev == 0 and e.rows_now == 43
    assert e.prev_sha256 == "" and len(e.sha256) == 64
    assert len((tmp_path / "daichou.jsonl").read_text(encoding="utf-8").splitlines()) == 1
    assert (tmp_path / "honban.json").exists()


def test_second_run_with_the_same_input_changes_nothing(tmp_path: Path) -> None:
    first = one_run(tmp_path, ZENKAI, "A", 0)
    second = one_run(tmp_path, ZENKAI, "A", 1)
    assert second.status == "ok" and second.changed == 0
    assert second.counts == {k: 0 for k in U.KINDS}
    assert second.sha256 == first.sha256 == second.prev_sha256


def test_apply_false_leaves_the_output_alone(tmp_path: Path) -> None:
    one_run(tmp_path, ZENKAI, "A", 0)
    before = U.sha256_of(tmp_path / "honban.json")
    e = one_run(tmp_path, MF.rows_konkai(), "B", 1, apply=False)
    assert e.status == "ok" and e.applied is False
    assert e.changed == 15 and e.sha256 == before == U.sha256_of(tmp_path / "honban.json")


def test_record_has_no_fallback_argument() -> None:
    """『決まらなければ最新へ』に相当する引数を持たない。"""
    import inspect
    sig = inspect.signature(U.record)
    assert list(sig.parameters) == ["ledger", "now", "prev", "output", "fingerprints",
                                    "run_at", "apply", "max_row_change"]
    assert sig.parameters["apply"].default is False


def test_overlap_stops_and_the_output_is_not_rewritten(tmp_path: Path) -> None:
    one_run(tmp_path, ZENKAI, "A", 0)
    before = U.sha256_of(tmp_path / "honban.json")
    e = one_run(tmp_path, KASANARI, "B", 1)
    assert e.status == "failed" and e.reason == "有効期間の重なり"
    assert e.applied is False and e.sha256 == before == e.prev_sha256
    assert U.sha256_of(tmp_path / "honban.json") == before


def test_a_stopped_run_keeps_the_diff_it_would_have_made(tmp_path: Path) -> None:
    """関所に落ちた回も、何を変えようとした回だったかを台帳に残す。"""
    one_run(tmp_path, ZENKAI, "A", 0)
    e = one_run(tmp_path, KASANARI, "B", 1)
    assert e.counts["追加"] == 1 and e.rows_now == 44 and e.findings_total == 2
    assert e.findings[0]["kind"] == "有効期間の重なり"


def test_hole_stops(tmp_path: Path) -> None:
    one_run(tmp_path, ZENKAI, "A", 0)
    e = one_run(tmp_path, ANA, "B", 1)
    assert e.status == "failed" and e.reason == "期間の穴"


def test_row_spike_stops(tmp_path: Path) -> None:
    one_run(tmp_path, ZENKAI, "A", 0)
    e = one_run(tmp_path, KYUHEN, "B", 1)
    assert e.status == "failed" and e.reason == "行数の急変"
    assert e.rows_prev == 43 and e.rows_now == 31


def test_row_spike_threshold_is_explicit(tmp_path: Path) -> None:
    one_run(tmp_path, ZENKAI, "A", 0)
    e = U.record(tmp_path / "daichou.jsonl", KYUHEN, tmp_path / "honban.json",
                 tmp_path / "honban.json", (fingerprint(tmp_path, "B"),),
                 run_at=stamp(1), apply=True, max_row_change=0.5)
    assert e.status == "ok" and e.rows_now == 31


def test_same_fingerprint_with_a_diff_stops(tmp_path: Path) -> None:
    one_run(tmp_path, ZENKAI, "A", 0)
    e = one_run(tmp_path, KONKAI, "A", 1)
    assert e.status == "failed" and e.reason == "指紋が前回と同一なのに差分あり"
    assert e.changed == 15


def test_a_new_fingerprint_without_a_diff_stops(tmp_path: Path) -> None:
    one_run(tmp_path, ZENKAI, "A", 0)
    e = one_run(tmp_path, ZENKAI, "B", 1)
    assert e.status == "failed" and e.reason == "指紋が違うのに差分 0"


def test_missing_column_stops_without_counts(tmp_path: Path) -> None:
    one_run(tmp_path, ZENKAI, "A", 0)
    e = one_run(tmp_path, TARINAI, "B", 1)
    assert e.status == "failed" and e.reason == "入力の列が足りない"
    assert e.counts is None and e.changed is None


def test_a_rewrite_outside_the_ledger_stops_the_next_run(tmp_path: Path) -> None:
    one_run(tmp_path, ZENKAI, "A", 0)
    (tmp_path / "honban.json").write_text("[]\n", encoding="utf-8")   # 台帳を通さない書き換え
    e = one_run(tmp_path, KONKAI, "B", 1)
    assert e.status == "failed" and e.reason == "台帳の鎖が切れている"


def test_duplicate_run_at_is_refused_without_appending(tmp_path: Path) -> None:
    one_run(tmp_path, ZENKAI, "A", 0)
    with pytest.raises(U.LedgerError, match="run_at の重複"):
        one_run(tmp_path, KONKAI, "B", 0)
    assert len((tmp_path / "daichou.jsonl").read_text(encoding="utf-8").splitlines()) == 1


def test_a_run_at_before_the_last_line_is_refused(tmp_path: Path) -> None:
    one_run(tmp_path, ZENKAI, "A", 1)
    with pytest.raises(U.LedgerError):
        one_run(tmp_path, KONKAI, "B", 0)
    assert len((tmp_path / "daichou.jsonl").read_text(encoding="utf-8").splitlines()) == 1


def test_the_ledger_is_append_only(tmp_path: Path) -> None:
    one_run(tmp_path, ZENKAI, "A", 0)
    first_line = (tmp_path / "daichou.jsonl").read_text(encoding="utf-8").splitlines()[0]
    one_run(tmp_path, MF.rows_konkai(), "B", 1)
    lines = (tmp_path / "daichou.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and lines[0] == first_line


def test_the_output_file_is_byte_identical_for_the_same_table(tmp_path: Path) -> None:
    a = U.Table.from_csv(KONKAI).serialize()
    b = U.Table.from_csv(KONKAI).serialize()
    assert a == b
    one_run(tmp_path, KONKAI, "A", 0)
    assert U.sha256_of(tmp_path / "honban.json") == U.hashlib.sha256(a).hexdigest()


def test_every_reason_code_is_reachable(tmp_path: Path) -> None:
    """8 つの理由コードに全部到達する道があること(7 つは台帳の行、1 つは追記の拒否)。"""
    seen = set()
    for i, (rows, letter) in enumerate([(ZENKAI, "A"), (KASANARI, "B"), (ANA, "C"),
                                        (KYUHEN, "D"), (KONKAI, "D"), (ZENKAI, "E"), (TARINAI, "F")]):
        d = tmp_path / f"c{i}"
        d.mkdir()
        one_run(d, ZENKAI, "A", 0)
        if i == 4:   # 直前の行と同じ指紋のまま中身を変える
            one_run(d, rows, "A", 1)
        else:
            one_run(d, rows, letter, 1)
        seen.add(U.read_ledger(d / "daichou.jsonl")[-1].reason)
    d = tmp_path / "chain"
    d.mkdir()
    one_run(d, ZENKAI, "A", 0)
    (d / "honban.json").write_text("[]\n", encoding="utf-8")
    one_run(d, KONKAI, "B", 1)
    seen.add(U.read_ledger(d / "daichou.jsonl")[-1].reason)
    seen.discard("")
    seen.add("run_at の重複")   # record は追記せず LedgerError で拒む(別テストで確認)
    assert seen == set(U.REASONS)


# ---------------------------------------------------------------- 一覧と自己検査

def test_inventory_is_one_row_per_run(tmp_path: Path) -> None:
    one_run(tmp_path, ZENKAI, "A", 0)
    one_run(tmp_path, KASANARI, "B", 1)
    one_run(tmp_path, MF.rows_konkai(), "C", 2)
    rows = U.inventory(U.read_ledger(tmp_path / "daichou.jsonl"))
    assert [r["n"] for r in rows] == [1, 2, 3]
    assert [r["status"] for r in rows] == ["ok", "failed", "ok"]
    assert [r["sha_moved"] for r in rows] == [True, False, True]
    assert all(len(r["sha"]) in (0, 8) for r in rows)


def test_replay_walks_a_clean_ledger(tmp_path: Path) -> None:
    one_run(tmp_path, ZENKAI, "A", 0)
    one_run(tmp_path, MF.rows_konkai(), "B", 1)
    r = U.replay(U.read_ledger(tmp_path / "daichou.jsonl"))
    assert r.ok and r.runs == 2 and r.rows == 47
    assert r.sha256 == U.sha256_of(tmp_path / "honban.json")


def test_replay_at_reconstructs_a_past_point(tmp_path: Path) -> None:
    one_run(tmp_path, ZENKAI, "A", 0)
    first_sha = U.sha256_of(tmp_path / "honban.json")
    one_run(tmp_path, MF.rows_konkai(), "B", 1)
    r = U.replay(U.read_ledger(tmp_path / "daichou.jsonl"), at=stamp(0))
    assert r.ok and r.runs == 1 and r.rows == 43 and r.sha256 == first_sha


# ---------------------------------------------------------------- 測定

def measure_diff() -> dict:
    d = U.diff_tables(U.Table.from_csv(ZENKAI), U.Table.from_csv(KONKAI))
    aspects = sum(d.counts[k] for k in U.KINDS[2:])
    return {"rows_prev": d.rows_prev, "rows_now": d.rows_now, "changed": d.changed,
            "counts": d.counts, "aspects": aspects,
            "two_sided": aspects - d.changed}


SCRIPT = [
    ("初回", "zenkai", "A"),
    ("同じものを取得して再実行", "zenkai", "A"),
    ("期間が重なる表", "kasanari", "B"),
    ("期間に穴がある表", "ana", "C"),
    ("年度の改定を反映", "konkai", "D"),
    ("取得に失敗して 1 年度落ちた表", "kyuhen", "E"),
    ("指紋は前回と同じまま中身が違う", "bumped:1", "E"),
    ("指紋だけ変わって中身は同じ", "konkai", "F"),
    ("列が足りない表", "tarinai", "G"),
    ("値を 1 つ訂正", "bumped:1", "H"),
    ("同じものを取得して再実行", "bumped:1", "H"),
    ("値を 1 つ訂正", "bumped:2", "I"),
    ("同じものを取得して再実行", "bumped:2", "I"),
    ("値を 1 つ訂正", "bumped:3", "J"),
    ("値を 1 つ訂正", "bumped:4", "K"),
    ("値を 1 つ訂正", "bumped:5", "L"),
    ("値を 1 つ訂正", "bumped:6", "M"),
    ("値を 1 つ訂正", "bumped:7", "N"),
    ("同じものを取得して再実行", "bumped:7", "N"),
    ("値を 1 つ訂正", "bumped:8", "O"),
]


def rows_named(name: str) -> list:
    if name.startswith("bumped:"):
        return MF.rows_bumped(int(name.split(":")[1]))
    return {"zenkai": MF.rows_zenkai, "konkai": MF.rows_konkai, "kasanari": MF.rows_kasanari,
            "ana": MF.rows_ana, "kyuhen": MF.rows_kyuhen, "tarinai": MF.rows_retsu_tarinai}[name]()


def run_script(tmp_path: Path) -> list:
    """SCRIPT の 20 回を順に流す。prev は本番ファイル、apply は毎回明示する。"""
    led, out = tmp_path / "daichou.jsonl", tmp_path / "honban.json"
    for i, (_, name, letter) in enumerate(SCRIPT):
        now = write_table(tmp_path / f"now_{i:02d}.csv", rows_named(name))
        U.record(led, now, out if out.exists() else None, out,
                 (fingerprint(tmp_path, letter),), run_at=stamp(i), apply=True)
    return U.read_ledger(led)


def measure_operation(tmp_path: Path) -> dict:
    entries = run_script(tmp_path)
    inv = U.inventory(entries)
    failed = [r for r in inv if r["status"] == "failed"]
    return {"runs": len(inv), "ok": len(inv) - len(failed), "failed": len(failed),
            "sha_moved": sum(1 for r in inv if r["sha_moved"]),
            "failed_sha_moved": sum(1 for r in failed if r["sha_moved"]),
            "reasons": [r["reason"] for r in failed],
            "replay": U.replay(entries).as_dict()}


def _tamper_cases(lines: list) -> dict:
    """出来上がった台帳を 1 か所だけ書き換える 13 通り。最後の 1 通りは台帳の中からは分からないもの。"""
    def at(pred, skip: int = 0) -> int:
        return [i for i, d in enumerate(lines) if pred(d)][skip]
    applied = at(lambda d: d["applied"] and d["sha256"] != d["prev_sha256"], skip=1)   # 台帳の途中の行
    moved = at(lambda d: d["counts"] and d["changed"])
    quiet = at(lambda d: d["counts"] and not d["changed"] and not any(d["counts"].values()))

    def case(fn):
        copy = [json.loads(json.dumps(d)) for d in lines]
        fn(copy)
        return copy

    def drop(c):
        del c[applied]

    def drop_head(c):
        del c[0]

    def swap(c):
        c[applied], c[applied + 1] = c[applied + 1], c[applied]

    def dup_run_at(c):
        c[applied]["run_at"] = c[applied - 1]["run_at"]

    def bump_added(c):
        c[moved]["counts"]["追加"] += 1

    def bump_rows(c):
        c[moved]["rows_now"] += 1

    def rewrite_sha(c):
        c[applied]["sha256"] = "0" * 64

    def rewrite_prev_sha(c):
        c[applied]["prev_sha256"] = "0" * 64

    def unset_applied(c):
        c[applied]["applied"] = False

    def unknown_reason(c):
        c[moved]["reason"] = "よく分からない理由"

    def copy_fingerprint(c):
        c[moved]["inputs"] = [dict(f) for f in c[moved - 1]["inputs"]]

    def new_fingerprint(c):
        c[quiet]["inputs"] = [{**f, "sha256": "f" * 64} for f in c[quiet]["inputs"]]

    def zero_changed(c):
        c[moved]["changed"] = 0

    return {"台帳の途中の 1 行を消す": case(drop), "行の順序を入れ替える": case(swap),
            "run_at を前の行と同じにする": case(dup_run_at), "追加の件数を 1 増やす": case(bump_added),
            "行数を 1 増やす": case(bump_rows), "出力の sha256 を書き換える": case(rewrite_sha),
            "前回の sha256 を書き換える": case(rewrite_prev_sha),
            "差し替えたのに applied を下げる": case(unset_applied),
            "登録外の理由コードにする": case(unknown_reason),
            "指紋を前の行と同じにする": case(copy_fingerprint),
            "差分 0 の行の指紋だけ変える": case(new_fingerprint),
            "動いた行数を 0 にする": case(zero_changed),
            "先頭の行を消す": case(drop_head)}


def measure_tampering(tmp_path: Path) -> dict:
    led = tmp_path / "daichou.jsonl"
    entries = run_script(tmp_path)
    clean = [json.loads(x) for x in led.read_text(encoding="utf-8").splitlines()]
    assert U.replay(entries).ok
    out = {}
    for name, lines in _tamper_cases(clean).items():
        p = tmp_path / "tampered.jsonl"
        p.write_text("".join(json.dumps(d, ensure_ascii=False) + "\n" for d in lines), encoding="utf-8")
        r = U.replay(U.read_ledger(p))
        out[name] = r.reason if not r.ok else ""
    return {"cases": len(out), "stopped": sum(1 for v in out.values() if v), "by_case": out}


def test_measure_diff(capsys: pytest.CaptureFixture) -> None:
    m = measure_diff()
    assert m["rows_prev"] == 43 and m["rows_now"] == 47
    assert m["counts"] == {"追加": 6, "削除": 2, "値の変更": 5, "有効期間の変更": 5,
                           "公表時点の変更": 1, "出典欄の変更": 6}
    assert m["changed"] == 15 and m["aspects"] == 17 and m["two_sided"] == 2
    with capsys.disabled():
        c = m["counts"]
        print(f"\n[measure] 前回 {m['rows_prev']} 行 → 今回 {m['rows_now']} 行: "
              f"追加 {c['追加']} / 削除 {c['削除']} / 値の変更 {c['値の変更']} / "
              f"有効期間の変更 {c['有効期間の変更']} / 公表時点の変更 {c['公表時点の変更']} / "
              f"出典欄の変更 {c['出典欄の変更']}")
        print(f"[measure] 動いた行は {m['changed']} 行、種別の合計は {m['aspects']} 件"
              f"(2 つの側面が同時に動いた行が {m['two_sided']} 行)")


def test_measure_operation(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    m = measure_operation(tmp_path)
    assert m["runs"] == 20 and m["ok"] == 14 and m["failed"] == 6
    assert m["sha_moved"] == 10 and m["failed_sha_moved"] == 0
    assert m["reasons"] == ["有効期間の重なり", "期間の穴", "行数の急変",
                            "指紋が前回と同一なのに差分あり", "指紋が違うのに差分 0", "入力の列が足りない"]
    assert m["replay"] == {"ok": True, "runs": 20, "rows": 47,
                           "sha256": m["replay"]["sha256"]}
    with capsys.disabled():
        print(f"\n[measure] 更新 {m['runs']} 回: 通った {m['ok']} 回 / 止まった {m['failed']} 回、"
              f"本番ファイルの sha が動いた {m['sha_moved']} 回")
        print(f"[measure] 止まった {m['failed']} 回で本番ファイルの sha が動いた回数: {m['failed_sha_moved']}"
              f"(理由コードの内訳 {' / '.join(m['reasons'])})")
        print(f"[measure] 台帳の自己検査: {m['replay']['runs']} 行を辿って行数 {m['replay']['rows']} を再構成")


def test_measure_tampering(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    m = measure_tampering(tmp_path)
    assert m["cases"] == 13 and m["stopped"] == 12
    assert m["by_case"]["run_at を前の行と同じにする"] == "run_at の重複"
    assert m["by_case"]["指紋を前の行と同じにする"] == "指紋が前回と同一なのに差分あり"
    assert m["by_case"]["差分 0 の行の指紋だけ変える"] == "指紋が違うのに差分 0"
    assert m["by_case"]["先頭の行を消す"] == ""   # 台帳の中からは分からない 1 通り
    assert sum(1 for v in m["by_case"].values() if v == "台帳の鎖が切れている") == 9
    with capsys.disabled():
        print(f"\n[measure] 台帳を 1 か所ずつ書き換えた {m['cases']} 通り: "
              f"自己検査が止めた {m['stopped']} 通り(止められなかった 1 通り = 先頭の行を消す)")
        for k, v in m["by_case"].items():
            print(f"[measure]   {k} → {v}")


# ---------------------------------------------------------------- CLI

def cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "update_ledger.py"), *args],
                          capture_output=True, text=True, encoding="utf-8", cwd=str(cwd or ROOT))


def test_cli_record_prints_one_json_line_and_exits_zero(tmp_path: Path) -> None:
    r = cli("record", "--ledger", str(tmp_path / "d.jsonl"), "--now", str(ZENKAI),
            "--output", str(tmp_path / "h.json"), "--run-at", stamp(0), "--apply")
    assert r.returncode == 0
    d = json.loads(r.stdout.strip())
    assert d["status"] == "ok" and d["applied"] and d["counts"]["追加"] == 43


def test_cli_record_exits_three_when_stopped(tmp_path: Path) -> None:
    cli("record", "--ledger", str(tmp_path / "d.jsonl"), "--now", str(ZENKAI),
        "--output", str(tmp_path / "h.json"), "--run-at", stamp(0), "--apply")
    r = cli("record", "--ledger", str(tmp_path / "d.jsonl"), "--now", str(KASANARI),
            "--prev", str(tmp_path / "h.json"), "--output", str(tmp_path / "h.json"),
            "--run-at", stamp(1), "--apply")
    assert r.returncode == 3
    assert json.loads(r.stdout.strip())["reason"] == "有効期間の重なり"


def test_cli_record_hashes_the_input_file(tmp_path: Path) -> None:
    src = tmp_path / "toritsuke.csv"
    src.write_text("合成の取得ファイル\n", encoding="utf-8")
    r = cli("record", "--ledger", str(tmp_path / "d.jsonl"), "--now", str(ZENKAI),
            "--output", str(tmp_path / "h.json"), "--run-at", stamp(0),
            "--input", f"表={src}", "--apply")
    d = json.loads(r.stdout.strip())
    assert d["inputs"][0]["name"] == "表"
    assert d["inputs"][0]["sha256"] == U.sha256_of(src)


def test_cli_inventory_and_replay(tmp_path: Path) -> None:
    for i, t in enumerate([ZENKAI, KONKAI]):
        cli("record", "--ledger", str(tmp_path / "d.jsonl"), "--now", str(t),
            *(["--prev", str(tmp_path / "h.json")] if i else []),
            "--output", str(tmp_path / "h.json"), "--run-at", stamp(i), "--apply")
    inv = json.loads(cli("inventory", "--ledger", str(tmp_path / "d.jsonl")).stdout.strip())
    assert inv["runs"] == 2 and inv["rows"][1]["rows_now"] == 47
    rp = cli("replay", "--ledger", str(tmp_path / "d.jsonl"))
    assert rp.returncode == 0 and json.loads(rp.stdout.strip())["rows"] == 47


def test_cli_replay_exits_three_on_a_tampered_ledger(tmp_path: Path) -> None:
    led = tmp_path / "d.jsonl"
    for i, t in enumerate([ZENKAI, KONKAI]):
        cli("record", "--ledger", str(led), "--now", str(t),
            *(["--prev", str(tmp_path / "h.json")] if i else []),
            "--output", str(tmp_path / "h.json"), "--run-at", stamp(i), "--apply")
    lines = [json.loads(x) for x in led.read_text(encoding="utf-8").splitlines()]
    lines[1]["prev_sha256"] = "0" * 64
    led.write_text("".join(json.dumps(d, ensure_ascii=False) + "\n" for d in lines), encoding="utf-8")
    r = cli("replay", "--ledger", str(led))
    assert r.returncode == 3 and json.loads(r.stdout.strip())["reason"] == "台帳の鎖が切れている"


def test_cli_validate_exits_three_on_a_broken_table() -> None:
    r = cli("validate", str(KASANARI))
    assert r.returncode == 3
    assert len(json.loads(r.stdout.strip())["findings"]) == 2
    assert cli("validate", str(ZENKAI)).returncode == 0


def test_cli_exits_two_on_an_unreadable_ledger(tmp_path: Path) -> None:
    led = tmp_path / "d.jsonl"
    led.write_text("これは JSON ではない\n", encoding="utf-8")
    r = cli("replay", "--ledger", str(led))
    assert r.returncode == 2 and "JSON" in r.stderr


# ---------------------------------------------------------------- fixture

def test_fixtures_on_disk_match_the_generator(tmp_path: Path) -> None:
    """合成 fixture が生成器から決定論的に出ること(ディスク上の CSV と突き合わせる)。"""
    for name, rows in [("hyou_zenkai.csv", MF.rows_zenkai()), ("hyou_konkai.csv", MF.rows_konkai()),
                       ("hyou_kasanari.csv", MF.rows_kasanari()), ("hyou_ana.csv", MF.rows_ana()),
                       ("hyou_kyuhen.csv", MF.rows_kyuhen()),
                       ("hyou_retsu_tarinai.csv", MF.rows_retsu_tarinai())]:
        p = tmp_path / name
        MF.write(p, rows)
        assert p.read_bytes() == (FX / name).read_bytes(), name


def test_fixtures_hold_no_real_values() -> None:
    """実在の料率・地域名が入っていないこと(合成データだけで測る)。"""
    text = "".join((FX / n).read_text(encoding="utf-8") for n in
                   ["hyou_zenkai.csv", "hyou_konkai.csv"])
    assert "架空" in text
    for word in ["東京", "大阪", "北海道", "協会けんぽ", "厚生労働省"]:
        assert word not in text
