"""change_kind の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 読んだ結果は 2 通りしかない。
  (a) 種別が changed の見本 1 本ごとに、5 つの区分か 6 つの別枠のどれか 1 つだけが付き、その合計が changed の
      見本の本数に等しく、(A) が付くのは old と new で欄の名前の集まりが同じで全部の欄の値が書かれたとおりに
      等しい見本だけで、(C) が付く見本には登録表で数値の欄とされた欄の違いが必ず在り、3 表の行順と old / new の
      欄の順を入れ替えても同じバイト列になる
  (b) 1 本も区分せず、止まった理由が 1 つ返る
どちらの場合も入力の 3 表は 1 文字も書き換わらない。

3 表は乱数で作って一時フォルダに書き、道具の読み方で読む。区分と別枠の照合は change_kind.compare / judge を
使わず、このテストの中で別に書く(JSONL を普通の json.loads で読み直して比べる。値は整数・文字列・null だけを
引くので、float の丸めは入らない)。derandomize=True で毎回同じ入力列を使い、database=None で例を保存しない。
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import change_kind as K  # noqa: E402

欄の名前 = ["kind", "id", "value", "rate", "text", "memo"]
値 = st.sampled_from([0, 1, 10, 11, "1", "10", "あ", "あ ", "", None])
対 = st.dictionaries(st.sampled_from(欄の名前), 値, max_size=4)
回のid = ["R1", "R2", "R3"]
件数 = st.sampled_from(["0", "1", "2", "3"])


@st.composite
def 三表(draw: st.DrawFn) -> tuple[list[list[str]], list[dict], list[list[str]]]:
    ids = draw(st.lists(st.sampled_from(回のid), min_size=1, max_size=3, unique=True))
    runs = []
    for rid in ids:
        c = ["", "", ""] if draw(st.integers(0, 7)) == 0 else [draw(件数), draw(件数), draw(件数)]
        runs.append([rid, *c, "合成(架空)"])
    if draw(st.integers(0, 9)) == 0:                      # (b) へ行く道: 回の id を重複させる
        runs.append(list(runs[0]))
    names = draw(st.lists(st.sampled_from(欄の名前), max_size=5, unique=True))
    fields = [[n, draw(st.sampled_from(K.SYMBOLS)), "合成(架空)"] for n in names]
    samples = []
    for _ in range(draw(st.integers(0, 7))):
        kind = draw(st.sampled_from(["changed", "changed", "changed", "added", "removed"]))
        old = draw(st.one_of(st.none(), 対)) if kind != "added" else None
        new = draw(st.one_of(st.none(), 対)) if kind != "removed" else None
        if kind == "changed" and old is not None and draw(st.booleans()):
            new = dict(old)                               # (A) が十分に出るように、半分は同じ対にする
        samples.append({"run_id": draw(st.sampled_from(ids + ["R9"])), "kind": kind,
                        "key": draw(st.sampled_from(["k1", "k2", "k3", "k4"])), "old": old, "new": new,
                        "source": draw(st.sampled_from(["合成(架空)", "合成(架空)", "合成(架空)", ""]))})
    return runs, samples, fields


def 書く(d: Path, runs: list, samples: list, fields: list) -> tuple[Path, Path, Path]:
    p = (d / "runs.csv", d / "samples.jsonl", d / "fields.csv")
    p[0].write_text("\n".join([",".join(K.RUN_HEADER)] + [",".join(r) for r in runs]) + "\n", encoding="utf-8")
    p[1].write_text("".join(json.dumps(s, ensure_ascii=False) + "\n" for s in samples), encoding="utf-8")
    p[2].write_text("\n".join([",".join(K.FIELD_HEADER)] + [",".join(f) for f in fields]) + "\n", encoding="utf-8")
    return p


def 同じ値(a: object, b: object) -> bool:
    return type(a) is type(b) and a == b


def 別に区分する(runs: list, samples: list, fields: list) -> list[str]:
    """道具の関数を使わずに、見本の台帳の行順で区分か別枠の名前を並べる。"""
    記号 = {f[0]: f[1] for f in fields}
    回 = {r[0]: r[1:4] for r in runs}
    本数 = {rid: {"added": 0, "removed": 0, "changed": 0} for rid in 回}
    for s in samples:
        if s["run_id"] in 本数:
            本数[s["run_id"]][s["kind"]] += 1
    out = []
    for s in samples:
        rid = s["run_id"]
        if s["source"] == "":
            out.append("別枠:" + K.ASIDE_SOURCE)
        elif rid not in 回:
            out.append("別枠:" + K.ASIDE_NO_RUN)
        elif "" in 回[rid]:
            out.append("別枠:" + K.ASIDE_EMPTY_COUNT)
        elif any(本数[rid][k] > int(c) for k, c in zip(("added", "removed", "changed"), 回[rid])):
            out.append("別枠:" + K.ASIDE_OVER)
        elif sum(1 for t in samples if t["run_id"] == rid and t["key"] == s["key"]) > 1:
            out.append("別枠:" + K.ASIDE_DUP)
        elif s["kind"] != "changed":
            out.append("別枠:")
        elif not s["old"] or not s["new"]:
            out.append("別枠:" + K.ASIDE_ONE_SIDE)
        else:
            違う = [n for n in set(s["old"]) | set(s["new"])
                   if n not in s["old"] or n not in s["new"] or not 同じ値(s["old"][n], s["new"][n])]
            印 = [記号.get(n) for n in 違う]
            if not 違う:
                out.append(K.A)
            elif None in 印:
                out.append(K.D)
            elif "数値の欄" in 印:
                out.append(K.C)
            elif set(印) == {"文言の欄"}:
                out.append(K.B)
            else:
                out.append(K.E)
    return out


@settings(max_examples=200, derandomize=True, database=None, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(t=三表())
def test_いつも成り立つこと_1_本に_1_つの区分か別枠_または_1_本も区分せず止まる(t: tuple[list, list, list]) -> None:
    runs, samples, fields = t
    with tempfile.TemporaryDirectory() as d:
        paths = 書く(Path(d), runs, samples, fields)
        before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
        tables = (K.read_runs(paths[0]), K.read_samples(paths[1]), K.read_fields(paths[2]))
        out = K.check(*tables, detail=True)
        if out["ok"]:
            event("(a) 区分した")
            n_changed = sum(1 for s in samples if s["kind"] == "changed")
            want = 別に区分する(runs, samples, fields)
            got = K._labels(*tables)
            assert got == want
            for c in K.CLASSES:
                assert out["区分"][c] == want.count(c)
            for a in K.ASIDE:
                assert out["別枠(changed の見本)"][a] == sum(
                    1 for s, w in zip(samples, want) if s["kind"] == "changed" and w == "別枠:" + a)
            assert sum(out["区分"].values()) + sum(out["別枠(changed の見本)"].values()) == n_changed
            assert len(out["見本ごと"]) == len(samples)
            for s, w in zip(samples, want):
                if w == K.A:
                    assert set(s["old"]) == set(s["new"])
                    assert all(同じ値(s["old"][n], s["new"][n]) for n in s["old"])
                if w == K.C:
                    reg = {f[0]: f[1] for f in fields}
                    assert any(reg.get(n) == "数値の欄" for n in set(s["old"]) | set(s["new"])
                               if n not in s["old"] or n not in s["new"] or not 同じ値(s["old"][n], s["new"][n]))
            base = K.digest(K.judge(*tables))
            flipped = (list(reversed(tables[0])), K._reorder(tables[1]), list(reversed(tables[2])))
            assert K.digest(K.judge(*flipped)) == base
        else:
            event("(b) 1 本も区分せず止まった")
            assert out["止まった理由"] in K.STOPS
            assert sum(out["区分"].values()) == 0
            assert out["見本ごと"] == []
        after = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
        assert before == after
