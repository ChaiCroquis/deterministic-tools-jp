"""change_kind の測定テスト。記事に載せる数はここで `assert 変数 == 値` として固定する(合成の 3 表、乱数なし)。"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
import change_kind as K  # noqa: E402

PATHS = (FX / "runs_a.csv", FX / "samples_a.jsonl", FX / "fields_a.csv")


def load() -> tuple[list[dict], list[dict], list[dict]]:
    return K.read_runs(PATHS[0]), K.read_samples(PATHS[1]), K.read_fields(PATHS[2])


def sample(**kw: object) -> dict:
    base = {"run_id": "R1", "kind": "changed", "key": "k", "old": {"value": K.Num("1")},
            "new": {"value": K.Num("1")}, "source": "合成(架空)"}
    return {**base, **kw}


RUN1 = [{"run_id": "R1", "added": "0", "removed": "0", "changed": "9", "source": "合成(架空)"}]
REG = [{"field": "value", "symbol": "数値の欄", "source": "合成(架空)"},
       {"field": "text", "symbol": "文言の欄", "source": "合成(架空)"},
       {"field": "id", "symbol": "識別子の欄", "source": "合成(架空)"}]


def one(old: dict, new: dict) -> str:
    out = K.check(RUN1, [sample(old=old, new=new)], REG, detail=True)
    return out["見本ごと"][0]["区分"]


def test_measure_three_tables_split_into_five_and_aside() -> None:
    runs, samples, fields = load()
    out = K.check(runs, samples, fields)
    n_runs, n_rows, n_fields = out["回の件数"], out["見本の台帳の行数"], len(fields)
    kinds = out["種別ごとの見本の本数"]
    classes = list(out["区分"].values())
    aside = list(out["別枠(changed の見本)"].values())
    aside_other = sum(out["別枠(added / removed の見本)"].values())
    print(f"\n[measure] runs_a / samples_a / fields_a: 回 {n_runs} 行 / 見本 {n_rows} 行 / 欄 {n_fields} 行")
    print(f"[measure] 種別ごとの見本は {kinds}")
    print(f"[measure] changed の見本 {kinds['changed']} 本 → 区分 {out['区分']}")
    print(f"[measure] 別枠(changed の見本) {out['別枠(changed の見本)']}")
    print(f"[measure] 別枠(added / removed の見本)は {aside_other} 本(出典が空)")
    assert n_runs == 9
    assert n_rows == 19
    assert n_fields == 6
    assert kinds == {"added": 4, "removed": 1, "changed": 14}
    assert classes == [2, 1, 1, 1, 1]
    assert aside == [1, 1, 1, 2, 2, 1]
    assert aside_other == 1
    assert out["別枠(added / removed の見本)"][K.ASIDE_SOURCE] == 1


def test_measure_sums_two_ways() -> None:
    out = K.check(*load())
    s = out["件数の検算"]
    classified, aside = sum(out["区分"].values()), sum(out["別枠(changed の見本)"].values())
    print(f"\n[measure] 件数の検算: 区分 {classified} + 別枠 {aside} = {s['区分 + 別枠']} = changed の見本 "
          f"{s['changed の見本の本数']}、回ごとの見本の本数の合計 + 回の台帳に無い回を指す見本 = "
          f"{s['回ごとの見本の本数の合計 + 回の台帳に無い回を指す見本']} = 見本の台帳の行数 {s['見本の台帳の行数']}")
    assert classified == 6
    assert aside == 8
    assert s["区分 + 別枠"] == 14
    assert s["changed の見本の本数"] == 14
    assert s["回ごとの見本の本数の合計 + 回の台帳に無い回を指す見本"] == 19
    assert s["見本の台帳の行数"] == 19
    assert s["合う"] is True


def test_measure_each_classified_sample() -> None:
    out = K.check(*load(), detail=True)
    got = {(r["run_id"], r["key"]): r for r in out["見本ごと"] if r["区分"]}
    names = lambda r: [(d["欄"], d["記号"], d["片側だけ"]) for d in r["違った欄"]]  # noqa: E731
    a1, a2 = got[("R04", "合成の規則A / 区分 甲 / 期 P1 / 0")], got[("R05", "合成の規則A / 区分 甲 / 期 P1 / 0")]
    b = got[("R06", "合成の規則B / 全体 / 期 P1 / 0")]
    c = got[("R06", "合成の規則C / 区分 乙 / 期 P1 / 0")]
    e = got[("R06", "合成の規則D / 全体 / 期 P1 / 0")]
    d = got[("R07", "合成の規則F / 区分 甲 / 期 P1 / 0")]
    print(f"\n[measure] (A) の 2 本は R04 / R05 の同じ key で、同じだった欄は {a1['同じだった欄']}、違った欄は 0 個")
    print(f"[measure] (B) の 1 本は違った欄 {names(b)}、同じだった欄 {b['同じだった欄']}")
    print(f"[measure] (C) の 1 本は違った欄 {names(c)}(0.125 → 0.135)")
    print(f"[measure] (E) の 1 本は違った欄 {names(e)}、(D) の 1 本は違った欄 {names(d)}")
    assert len(got) == 6
    assert a1["区分"] == K.A and a2["区分"] == K.A
    assert a1["違った欄"] == [] and a1["同じだった欄"] == ["kind", "unit", "value"]
    assert b["区分"] == K.B
    assert names(b) == [("text", "文言の欄", ""), ("text_note", "文言の欄", "new にだけ")]
    assert b["同じだった欄"] == ["id", "kind"]
    assert c["区分"] == K.C and names(c) == [("value", "数値の欄", "")]
    assert e["区分"] == K.E and names(e) == [("id", "識別子の欄", "")]
    assert d["区分"] == K.D and names(d) == [("memo", "登録なし", "")]


def test_measure_counts_and_samples_side_by_side() -> None:
    out = K.check(*load(), detail=True)
    rows = {r["run_id"]: r for r in out["回ごと"]}
    cover = {rid: r["見本の範囲"] for rid, r in rows.items()}
    pairs = {rid: (r["件数の合計"], r["見本の本数の合計"]) for rid, r in rows.items()}
    missing = {rid: r["件数は在るのに見本が 1 本も無い種別"] for rid, r in rows.items() if r["件数は在るのに見本が 1 本も無い種別"]}
    by_cover = out["見本の範囲ごとの回の件数"]
    print(f"\n[measure] 件数の合計と見本の本数の対: {pairs}")
    print(f"[measure] 見本の範囲ごとの回の件数: {by_cover}")
    print(f"[measure] 件数は在るのに見本が 1 本も無い種別: {missing}")
    assert pairs == {"R01": (40, 0), "R02": (0, 0), "R03": (None, 1), "R04": (2, 2), "R05": (2, 1),
                     "R06": (21, 7), "R07": (2, 2), "R08": (1, 2), "R09": (5, 3)}
    assert cover == {"R01": K.COVER_NONE, "R02": K.COVER_ZERO, "R03": K.COVER_EMPTY, "R04": K.COVER_ALL,
                     "R05": K.COVER_PART, "R06": K.COVER_PART, "R07": K.COVER_ALL, "R08": K.COVER_OVER,
                     "R09": K.COVER_PART}
    assert list(by_cover.values()) == [2, 3, 1, 1, 1, 1]
    assert sum(by_cover.values()) == 9
    assert missing == {"R01": ["added"], "R05": ["removed"]}


def test_values_are_compared_as_written_strings() -> None:
    n = K.Num
    assert one({"value": n("5000")}, {"value": n("5000")}) == K.A
    assert one({"value": n("5000")}, {"value": n("5000.0")}) == K.C      # 数として同じでも、書かれた文字列が違う
    assert one({"value": n("1226")}, {"value": "1226"}) == K.C           # 数と文字列は別物
    assert one({"value": {"a": n("1"), "b": n("2")}}, {"value": {"b": n("2"), "a": n("1")}}) == K.A   # 対の順は見ない
    assert one({"value": [n("1"), n("2")]}, {"value": [n("2"), n("1")]}) == K.C                       # 並びの順は見る
    assert one({"text": "あ"}, {"text": "あ "}) == K.B                    # 空白 1 つも違い


def test_precedence_of_classes() -> None:
    n = K.Num
    assert one({"value": n("1"), "memo": "x"}, {"value": n("2"), "memo": "y"}) == K.D   # 登録なしが在れば (D)
    assert one({"value": n("1"), "text": "x"}, {"value": n("2"), "text": "y"}) == K.C
    assert one({"id": "a", "text": "x"}, {"id": "b", "text": "y"}) == K.E
    assert one({"text": "x"}, {"text": "x", "value": n("3")}) == K.C     # 片側だけの欄は、その欄の記号で区分する
    assert one({"text": "x"}, {"text": "x", "memo": "m"}) == K.D


def test_measure_verify_five_things() -> None:
    out = K.verify(*load())
    v = out["verify"]
    print(f"\n[measure] verify: {json.dumps(v, ensure_ascii=False)}")
    assert out["ok"] is True
    assert [x["合う"] for x in v.values()] == [True] * 5
    assert len(v) == 5
    assert v["① 二度走りの sha256 が同一"]["先頭 12 桁"] == "20cab5bf1d87"
    assert v["② 行順と欄の順を入れ替えても同一"]["入れ替え方"] == 2
    assert v["④ (A) の見本の数値の欄を 1 文字変えた写し"]["試した見本"] == 2
    assert v["④ (A) の見本の数値の欄を 1 文字変えた写し"]["その 1 本だけが (C) へ動いた"] == 2
    assert v["⑤ 欄の登録表から 1 欄を消した写し"]["消した欄"] == 6
    assert v["⑤ 欄の登録表から 1 欄を消した写し"]["その欄が違う見本だけが (D) になった"] == 6
    assert v["⑤ 欄の登録表から 1 欄を消した写し"]["(D) へ動いた見本の延べ本数"] == 4


def test_tweak_moves_only_that_sample() -> None:
    runs, samples, fields = load()
    before = K._labels(runs, samples, fields)
    i = next(j for j, s in enumerate(samples) if s["run_id"] == "R04" and s["kind"] == "changed")
    copy = [dict(s) for s in samples]
    copy[i]["new"] = {**copy[i]["new"], "value": K.Num("5001")}
    after = K._labels(runs, copy, fields)
    moved = [j for j in range(len(before)) if before[j] != after[j]]
    assert moved == [i]
    assert (before[i], after[i]) == (K.A, K.C)


def _broken(tmp_path: Path) -> dict[str, tuple[Path, Path, Path]]:
    """止まる理由コード 1 つにつき、崩した表を 1 組作る(メモリの外に置くのは一時フォルダだけ)。"""
    r_txt, s_txt, f_txt = (p.read_text(encoding="utf-8") for p in PATHS)
    first = s_txt.splitlines()[1]
    cases = {
        K.STOP_HEADER: (r_txt.replace("run_id,added", "id,added"), s_txt, f_txt),
        K.STOP_RUN_DUP: (r_txt.replace("R02,", "R01,"), s_txt, f_txt),
        K.STOP_RUN_SOURCE: (r_txt.replace("R02,0,0,0,合成の実行履歴のメモ(架空)L2", "R02,0,0,0,"), s_txt, f_txt),
        K.STOP_COUNT: (r_txt.replace("R01,40,", "R01,4０,"), s_txt, f_txt),
        K.STOP_FIELD_DUP: (r_txt, s_txt, f_txt + "kind,種別の欄,合成の登録のメモ(架空)L7\n"),
        K.STOP_SYMBOL: (r_txt, s_txt, f_txt.replace("value,数値の欄", "value,金額の欄")),
        K.STOP_FIELD_SOURCE: (r_txt, s_txt, f_txt.replace("id,識別子の欄,合成の登録のメモ(架空)L2", "id,識別子の欄,")),
        K.STOP_JSON: (r_txt, s_txt + "{こわれた行\n", f_txt),
        K.STOP_SAMPLE_COLS: (r_txt, s_txt + first.replace('"key"', '"kagi"') + "\n", f_txt),
        K.STOP_KIND: (r_txt, s_txt + first.replace('"kind": "changed"', '"kind": "updated"') + "\n", f_txt),
        K.STOP_PAYLOAD: (r_txt, s_txt + first.replace('"old": {"kind": "param", "value": 5000, "unit": "点"}', '"old": "param"') + "\n", f_txt),
    }
    out = {}
    for n, (code, (r, s, f)) in enumerate(cases.items()):
        d = tmp_path / f"kowashita_{n:02d}"
        d.mkdir()
        (d / "runs.csv").write_text(r, encoding="utf-8")
        (d / "samples.jsonl").write_text(s, encoding="utf-8")
        (d / "fields.csv").write_text(f, encoding="utf-8")
        out[code] = (d / "runs.csv", d / "samples.jsonl", d / "fields.csv")
    return out


def test_measure_every_stop_code_has_a_broken_table(tmp_path: Path, capsys) -> None:
    broken = _broken(tmp_path)
    seen = []
    for code, (r, s, f) in broken.items():
        try:
            out = K.check(K.read_runs(r), K.read_samples(s), K.read_fields(f), detail=True)
        except K.Stop as e:        # 読む段で止まる(見出し・JSON)
            out = {"ok": False, "止まった理由": e.code, "区分": {c: 0 for c in K.CLASSES}, "見本ごと": []}
        assert out["ok"] is False
        assert out["止まった理由"] == code
        assert sum(out["区分"].values()) == 0 and out["見本ごと"] == []
        assert K.main(["check", str(r), str(s), str(f)]) == 2
        seen.append(code)
    print(f"\n[measure] 止まる理由コードは {len(K.STOPS)} 個で、崩した表 {len(broken)} 組のすべてで 1 本も区分せずに止まる")
    assert len(K.STOPS) == 11
    assert len(broken) == 11
    assert sorted(seen) == sorted(K.STOPS)


def test_measure_tail_lines_and_no_single_value() -> None:
    out = K.check(*load(), detail=True)
    text = json.dumps({k: v for k, v in out.items() if k != "持たせていないもの"}, ensure_ascii=False)
    banned = ["実質", "変更なし", "割合", "率", "理由", "推計"]
    hits = [w for w in banned if w in text]
    print(f"\n[measure] 出力の末尾の「持たせていないもの」は {len(out['持たせていないもの'])} 行。"
          f"それ以外の出力に {banned} のどの語も現れない({len(hits)} 件)")
    assert len(out["持たせていないもの"]) == 10
    assert out["持たせていないもの"] == list(K.NOT_HELD)
    assert hits == []
    assert len(K.CLASSES) == 5 and len(K.ASIDE) == 6 and len(K.SYMBOLS) == 4


def test_input_is_not_rewritten_and_exit_codes(tmp_path: Path, capsys) -> None:
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in PATHS]
    args = [str(p) for p in PATHS]
    codes = [K.main([cmd, *args]) for cmd in ("check", "rows", "verify")]
    capsys.readouterr()
    after = [hashlib.sha256(p.read_bytes()).hexdigest() for p in PATHS]
    assert before == after
    assert codes == [3, 3, 0]          # 別枠が 1 本でも在れば 3。verify は 5 つとも合えば 0
    clean = tmp_path / "clean.jsonl"
    keep = [ln for ln in PATHS[1].read_text(encoding="utf-8").splitlines() if '"run_id": "R04"' in ln]
    clean.write_text("\n".join(keep) + "\n", encoding="utf-8")
    assert K.main(["check", args[0], str(clean), args[2]]) == 0
    capsys.readouterr()


def test_measure_source_has_no_clock_network_float() -> None:
    src = (ROOT / "change_kind.py").read_text(encoding="utf-8")
    imports = sorted(ln.split()[1].split(".")[0] for ln in src.splitlines() if ln.startswith(("import ", "from ")))
    banned = ["float(", "round(", "eval(", "exec(", "datetime", "import time", "random", "urllib", "socket",
              "subprocess", "requests"]
    hits = [w for w in banned if w in src]
    print(f"\n[measure] 部品が import している module は {len(imports)} 個 {imports}。"
          f"時計・通信・float・round・乱数の呼び出しは {len(hits)} 件。hashlib を呼ぶのは {src.count('hashlib.')} か所")
    assert imports == ["__future__", "argparse", "csv", "hashlib", "json", "pathlib", "sys"]
    assert hits == []
    assert src.count("hashlib.") == 1
