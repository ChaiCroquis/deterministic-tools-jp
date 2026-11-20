"""stamp_day のテスト。測定はすべて合成した 2 表(fixtures/stamps_a.csv / zones_a.csv)に対するもの。
記事に載せる数は、ここで `assert 変数 == 値` として固定している(値が変われば記事も変える)。
"""
from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
import stamp_day as T  # noqa: E402

STAMPS, ZONES = T.load(FX / "stamps_a.csv", FX / "zones_a.csv")
ZONE = "換算先A"


def res():
    return T.judge(STAMPS, ZONES, ZONE)


def test_measure_two_tables_split_into_three_and_aside():
    r = res()
    print(f"\n[measure] stamps_a / zones_a: 時刻の台帳 {len(STAMPS)} 行 / 換算先の登録表 {len(ZONES)} 行、"
          f"使った 1 行は {r['換算先']}")
    print(f"[measure] 区分 {r['区分']}")
    print(f"[measure] 別枠 {r['別枠']}")
    assert len(STAMPS) == 20
    assert len(ZONES) == 3
    assert r["換算先"] == {"名前": "換算先A", "時差": "+09:00"}
    assert r["区分"] == {T.KUBUN_A: 7, T.KUBUN_B: 4, T.KUBUN_C: 1}
    assert r["別枠"] == {T.ASIDE_SOURCE: 1, T.ASIDE_DUP: 2, T.ASIDE_SHAPE: 3, T.ASIDE_NO_MARK: 2}


def test_measure_day_counts_stay_two_columns():
    r = res()
    pairs = {d["日付"]: (d["書かれたままの読み"], d["換算後の読み"]) for d in r["日ごとの回数"]}
    print(f"\n[measure] 日ごとの回数(書かれたままの読み, 換算後の読み): {pairs}")
    assert pairs == {"2031-04-01": (8, 5), "2031-04-02": (4, 7)}
    # 1 列に丸めた欄が無い
    assert set(r["日ごとの回数"][0]) == {"日付", "書かれたままの読み", "換算後の読み"}


def test_measure_sums_two_ways():
    c = res()["件数の検算"]
    print(f"\n[measure] 件数の検算: 区分 12 + 別枠 8 = {c['区分 + 別枠']} = 台帳の行数 {c['台帳の行数']}、"
          f"日ごとの回数の合計は書かれたままの読み {c['日ごとの回数の合計(書かれたままの読み)']} / "
          f"換算後の読み {c['日ごとの回数の合計(換算後の読み)']} = 区分に入った行数 {c['区分に入った行数']}")
    assert c["区分 + 別枠"] == 20
    assert c["台帳の行数"] == 20
    assert c["日ごとの回数の合計(書かれたままの読み)"] == 12
    assert c["日ごとの回数の合計(換算後の読み)"] == 12
    assert c["区分に入った行数"] == 12
    assert c["合う"] is True


def test_measure_order_first_last_and_changed_rows():
    r = res()
    order = [x["row_id"] for x in r["rows"]]
    print(f"\n[measure] 並べた順(行の番号): {order}")
    print(f"[measure] 最初の時刻 {r['最初の時刻']} / 最後の時刻 {r['最後の時刻']}")
    print(f"[measure] 日付が替わった行の番号 {r['日付が替わった行の番号']}")
    assert order == ["1", "2", "3", "10", "4", "5", "6", "7", "9", "8", "11", "12"]
    assert r["最初の時刻"] == {"row_id": "1", "書かれた時刻": "2031-04-01T09:55:21+00:00",
                          "換算後": "2031-04-01 18:55:21"}
    assert r["最後の時刻"] == {"row_id": "12", "書かれた時刻": "2031-04-02T06:15:30.250+00:00",
                          "換算後": "2031-04-02 15:15:30.250000"}
    assert r["日付が替わった行の番号"] == ["10", "5", "6", "7", "11"]
    assert r["並べ方"] == T.ORDER_NOTE


def test_measure_edge_of_day_is_one_second():
    by = {x["row_id"]: x for x in res()["rows"]}
    print(f"\n[measure] 行 4({by['4']['書かれた時刻']})→ {by['4']['換算後の日付']} {by['4']['換算後の時刻']} {by['4']['区分']}")
    print(f"[measure] 行 5({by['5']['書かれた時刻']})→ {by['5']['換算後の日付']} {by['5']['換算後の時刻']} {by['5']['区分']}")
    assert (by["4"]["換算後の日付"], by["4"]["換算後の時刻"], by["4"]["区分"]) == ("2031-04-01", "23:59:59", T.KUBUN_A)
    assert (by["5"]["換算後の日付"], by["5"]["換算後の時刻"], by["5"]["区分"]) == ("2031-04-02", "00:00:00", T.KUBUN_B)


def test_measure_z_is_read_with_a_note_and_no_mark_is_not_guessed():
    r = res()
    z = [x["row_id"] for x in r["rows"] if x["Z の読み"] == T.Z_NOTE]
    no_mark = [x["row_id"] for x in r["aside"] if x["別枠"] == T.ASIDE_NO_MARK]
    print(f"\n[measure] Z を +00:00 と読んだ行は {r['Z を +00:00 と読んだ行']} 行 {z}。"
          f"時差の印が無い行 {no_mark} は区分に入らず、日ごとの回数にも入らない")
    assert r["Z を +00:00 と読んだ行"] == 2
    assert z == ["7", "8"]
    assert no_mark == ["13", "14"]
    assert all("換算後の日付" not in x for x in r["aside"])


def test_measure_verify_five_things():
    v = T.verify(STAMPS, ZONES, ZONE)
    print(f"\n[measure] verify: ① 二度走りの sha256 が同一(先頭 12 桁 {v['① 二度走りの sha256']['sha256'][:12]})/ "
          f"② 入れ替え方 {v['② 行順の入れ替え']['入れ替え方']} 通りで同一 {v['② 行順の入れ替え']['同一']} / "
          f"③ 合う {v['③ 件数の検算']['合う']} / "
          f"④ 時差の印 {v['④ 書かれている時差へ換算']['時差の印の種類']} 種類・"
          f"{v['④ 書かれている時差へ換算']['試した行数']} 行が全部 (A) / "
          f"⑤ 試した {v['⑤ 日付の境目の 1 秒']['試した行数']} 行、手前で (A) のまま "
          f"{v['⑤ 日付の境目の 1 秒']['手前の 1 秒で (A) のままだった行数']} 行、その 1 行だけが動いた "
          f"{v['⑤ 日付の境目の 1 秒']['向こうの 1 秒でその 1 行だけが動いた行数']} 行、"
          f"境目が無くて試せない {v['⑤ 日付の境目の 1 秒']['境目が無くて試せない行数']} 行")
    assert v["ok"] is True
    assert v["① 二度走りの sha256"]["同一"] is True
    assert v["① 二度走りの sha256"]["sha256"][:12] == "f24d1e4c8821"
    assert v["② 行順の入れ替え"] == {"入れ替え方": 3, "同一": 3, "合う": True}
    assert v["④ 書かれている時差へ換算"] == {"時差の印の種類": 5, "試した行数": 12, "(A) になった行数": 12,
                                  "2 列の回数が一致した種類": 5, "合う": True}
    assert v["⑤ 日付の境目の 1 秒"] == {"試した行数": 6, "手前の 1 秒で (A) のままだった行数": 6,
                                 "向こうの 1 秒でその 1 行だけが動いた行数": 6,
                                 "境目が無くて試せない行数": 1, "合う": True}


def test_measure_other_zone_moves_rows_the_other_way():
    r = T.judge(STAMPS, ZONES, "換算先B")
    pairs = {d["日付"]: (d["書かれたままの読み"], d["換算後の読み"]) for d in r["日ごとの回数"]}
    print(f"\n[measure] 換算先B(-05:00)に替えると 区分 {r['区分']}、日ごとの回数 {pairs}")
    assert r["区分"] == {T.KUBUN_A: 9, T.KUBUN_B: 0, T.KUBUN_C: 3}   # 手で数えた: 行 8・9・10 が前の日付へ
    assert pairs == {"2031-04-01": (8, 11), "2031-04-02": (4, 1)}
    same = T.judge(STAMPS, ZONES, "書かれたまま")
    print(f"[measure] 換算先を +00:00 にしても、+00:00 以外で書かれた行は動く: 区分 {same['区分']}")
    assert same["区分"] == {T.KUBUN_A: 9, T.KUBUN_B: 1, T.KUBUN_C: 2}


def test_two_day_shift_is_reported_as_days():
    r = T.judge([{"row_id": "1", "stamp": "2031-04-01T23:30:00-12:00", "source": "合成 L1"}],
                [{"name": "x", "offset": "+14:00"}])
    row = r["rows"][0]
    assert (row["換算後の日付"], row["日付の差(日)"], row["区分"]) == ("2031-04-03", 2, T.KUBUN_B)


def test_shapes_that_are_not_read():
    bad = ["2031-04-01", "2031-04-01 10:00:00+00:00", "2031-04-01T10:00+00:00", "2031-04-01T24:00:00+00:00",
           "2031-04-01T10:00:00+0900", "2031-04-01T10:00:00+24:00", "２０３１-04-01T10:00:00+00:00",
           "2031-04-01T10:00:00+00:00 ", "", "2031-04-01T10:00:00z"]
    assert [T.parse_stamp(s)[0] for s in bad] == [T.ASIDE_SHAPE] * len(bad)
    assert T.parse_stamp("2031-04-01T10:00:00")[0] == T.ASIDE_NO_MARK
    assert T.parse_stamp("2031-04-01T10:00:00-00:00")[0] == "ok"


def test_row_number_order_is_numeric_for_digits():
    stamps = [{"row_id": i, "stamp": "2031-04-01T10:00:00+00:00", "source": "合成 L1"} for i in ["10", "2", "b", "a", "1"]]
    r = T.judge(stamps, [{"name": "x", "offset": "+09:00"}])
    assert [x["row_id"] for x in r["rows"]] == ["1", "2", "10", "a", "b"]


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_measure_every_stop_code_has_a_broken_table(tmp_path):
    ok_s = "row_id,stamp,source\n1,2031-04-01T10:00:00+00:00,合成 L1\n"
    ok_z = "name,offset\nx,+09:00\n"
    two_z = "name,offset\nx,+09:00\ny,-05:00\n"
    broken = {
        T.STOPS[0]: ("id,stamp,source\n1,2031-04-01T10:00:00+00:00,合成 L1\n", ok_z, None),
        T.STOPS[1]: ("row_id,stamp,source\n1,2031-04-01T10:00:00+00:00\n", ok_z, None),
        T.STOPS[2]: ("row_id,stamp,source\n,2031-04-01T10:00:00+00:00,合成 L1\n", ok_z, None),
        T.STOPS[3]: (ok_s, "name,tz\nx,+09:00\n", None),
        T.STOPS[4]: (ok_s, "name,offset\nx,+09:00,余分\n", None),
        T.STOPS[5]: (ok_s, "name,offset\n", None),
        T.STOPS[6]: (ok_s, "name,offset\nx,+09:00\nx,-05:00\n", "x"),
        T.STOPS[7]: (ok_s, "name,offset\nx,Asia/Tokyo\n", None),
        T.STOPS[8]: (ok_s, two_z, None),
        T.STOPS[9]: (ok_s, two_z, "z"),
    }
    stopped = 0
    for i, (reason, (s, z, name)) in enumerate(broken.items()):
        r = T.run_files(_write(tmp_path / f"s{i}.csv", s), _write(tmp_path / f"z{i}.csv", z), name)
        assert r == {"ok": False, "止まった理由": reason, "区分した行数": 0}
        stopped += 1
    print(f"\n[measure] 止まる理由コードは {len(T.STOPS)} 個で、崩した表 {stopped} 組のすべてで 1 行も区分せずに止まる")
    assert len(T.STOPS) == 10
    assert stopped == 10
    assert set(broken) == set(T.STOPS)


def test_measure_tail_lines_and_no_verdict_words():
    r = res()
    body = json.dumps(T.judged_part(r), ensure_ascii=False)
    words = ["正しい", "誤り", "本当", "現地", "推定", "理由"]
    hits = sum(body.count(w) for w in words)
    print(f"\n[measure] 出力の末尾の「持たせていないもの」は {len(r['持たせていないもの'])} 行。"
          f"それ以外の出力に {words} のどの語も現れない({hits} 件)")
    assert len(r["持たせていないもの"]) == 10
    assert hits == 0


def test_measure_imports_and_calls_not_held():
    src = (ROOT / "stamp_day.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            modules.add(node.module)
    names = [n.id for n in ast.walk(tree) if isinstance(n, ast.Name)]
    attrs = [n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)]
    banned = ["now", "utcnow", "today", "astimezone", "localtime", "fromtimestamp", "float", "round",
              "random", "timezone", "ZoneInfo", "tzlocal", "urlopen", "socket"]
    hits = sum(names.count(b) + attrs.count(b) for b in banned)
    writes = sum(1 for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "open"
                 and any(isinstance(a, ast.Constant) and a.value in ("w", "a", "wb", "r+") for a in n.args))
    sha_calls = attrs.count("sha256")
    print(f"\n[measure] 部品が import している module は {len(modules)} 個 {sorted(modules)}。"
          f"時計・端末の時間帯・通信・float・round・乱数の呼び出しは {hits} 件、書き込みで開く open は {writes} 件。"
          f"hashlib を呼ぶのは {sha_calls} か所")
    assert modules == {"__future__", "argparse", "csv", "hashlib", "json", "re", "sys", "datetime", "pathlib"}
    assert len(modules) == 9
    assert hits == 0
    assert writes == 0
    assert sha_calls == 1


def test_cli_exit_codes_and_inputs_untouched(tmp_path):
    def sha(p: Path) -> str:
        return hashlib.sha256(p.read_bytes()).hexdigest()

    before = (sha(FX / "stamps_a.csv"), sha(FX / "zones_a.csv"))
    exe = [sys.executable, "-X", "utf8", str(ROOT / "stamp_day.py")]
    args = [str(FX / "stamps_a.csv"), str(FX / "zones_a.csv")]
    codes = [subprocess.run(exe + [cmd] + args + extra, capture_output=True).returncode
             for cmd, extra in [("check", ["--zone", ZONE]), ("rows", ["--zone", ZONE]),
                                ("verify", ["--zone", ZONE]), ("check", [])]]
    assert codes == [3, 3, 0, 2]       # 別枠あり = 3 / verify が通る = 0 / 止まる = 2
    clean = _write(tmp_path / "s.csv", "row_id,stamp,source\n1,2031-04-01T10:00:00+00:00,合成 L1\n")
    one = _write(tmp_path / "z.csv", "name,offset\nx,+09:00\n")
    assert subprocess.run(exe + ["check", str(clean), str(one)], capture_output=True).returncode == 0
    assert (sha(FX / "stamps_a.csv"), sha(FX / "zones_a.csv")) == before
