"""change_kind — 差分の記録に「替わった」と数えられた行の見本を、前(old)と後(new)で欄ごとに見比べて区分する。

入力は 3 表。
  ① 回の台帳   (CSV)   run_id,added,removed,changed,source
  ② 見本の台帳 (JSONL) {"run_id","kind","key","old","new","source"} を 1 行 1 本
  ③ 欄の登録表 (CSV)   field,symbol,source   (symbol は SYMBOLS の 4 つ。人が登録した分だけ)

出力は、種別が changed の見本 1 本ごとの区分(CLASSES の 5 値)か別枠(ASIDE の 6 つ)と、
回ごとの「件数の合計と見本の本数」の対。値は書かれた文字列として等しいかだけを見る(数として近いかは見ない)。
見本の外は読まない。「実質の変更は N 件」のような 1 値は作らない。

標準ライブラリのみ(csv / json / hashlib / argparse)。入力は 1 文字も書き換えない。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

SYMBOLS = ("数値の欄", "文言の欄", "種別の欄", "識別子の欄")
KINDS = ("added", "removed", "changed")
UNREGISTERED = "登録なし"

A = "(A) 見本に写っている欄がすべて同じ"
B = "(B) 違うのは文言の欄だけ"
C = "(C) 数値の欄が違う"
D = "(D) 違う欄に登録表に無い欄が含まれる"
E = "(E) 数値の欄は同じで、種別か識別子の欄が違う"
CLASSES = (A, B, C, D, E)

ASIDE_SOURCE = "出典が空"
ASIDE_NO_RUN = "回の台帳に無い回を指す見本"
ASIDE_EMPTY_COUNT = "件数の欄が空の回の見本"
ASIDE_OVER = "見本の本数が件数を超える回の見本"
ASIDE_DUP = "同じ回に同じ key の見本が 2 本以上"
ASIDE_ONE_SIDE = "changed なのに old か new が無い"
ASIDE = (ASIDE_SOURCE, ASIDE_NO_RUN, ASIDE_EMPTY_COUNT, ASIDE_OVER, ASIDE_DUP, ASIDE_ONE_SIDE)

COVER_ALL = "見本が全件"
COVER_PART = "見本が一部"
COVER_NONE = "見本なし"
COVER_ZERO = "件数が 0"
COVER_EMPTY = "件数の欄が空"
COVER_OVER = "見本の本数が件数を超える"
COVERS = (COVER_ALL, COVER_PART, COVER_NONE, COVER_ZERO, COVER_EMPTY, COVER_OVER)

STOP_HEADER = "見出しが違う"
STOP_RUN_DUP = "回の id が重複"
STOP_RUN_SOURCE = "回の出典が空"
STOP_COUNT = "件数が整数でない"
STOP_FIELD_DUP = "欄の名前が重複"
STOP_SYMBOL = "欄の記号が登録の外"
STOP_FIELD_SOURCE = "欄の出典が空"
STOP_JSON = "見本の行が読めない"
STOP_SAMPLE_COLS = "見本の欄が足りない"
STOP_KIND = "見本の種別が登録の外"
STOP_PAYLOAD = "old か new が欄と値の対でない"
STOPS = (STOP_HEADER, STOP_RUN_DUP, STOP_RUN_SOURCE, STOP_COUNT, STOP_FIELD_DUP, STOP_SYMBOL,
         STOP_FIELD_SOURCE, STOP_JSON, STOP_SAMPLE_COLS, STOP_KIND, STOP_PAYLOAD)

RUN_HEADER = ["run_id", "added", "removed", "changed", "source"]
FIELD_HEADER = ["field", "symbol", "source"]
SAMPLE_KEYS = ("run_id", "kind", "key", "old", "new", "source")

NOT_HELD = (
    "見本の外を読まない: (A) の行で何が違ったかは当てない。見本に写っていない欄は比べていない",
    "同じ回に足された行・減った行と結び付けない",
    "替わった理由の欄を持たない",
    "見本から全件の内訳を推計しない(割合を掛けない)",
    "欄の名前から記号を当てない。登録表に無い欄は (D) のまま",
    "数として丸めて比べない。書かれた文字列が等しいかだけを見る(float を使わない)",
    "「変更なし」と言い換えない。(A) は見本に写っている欄が同じというだけ",
    "区分ごとの件数を「実質の変更は N 件」のような 1 値に丸めない",
    "通信しない。時計を読まない",
    "入力を書き換えない。verify が作る写しはメモリの中だけ",
)


class Stop(Exception):
    """表として読めない。1 本も区分しない。"""

    def __init__(self, code: str, where: str) -> None:
        super().__init__(f"{code}: {where}")
        self.code, self.where = code, where


class Num(str):
    """JSON の数を、書かれた文字列のまま持つ(float にしない)。"""


def canon(v: object) -> str:
    """値を「書かれた文字列」にする。数と文字列は別物(1226 と "1226" は等しくない)。対の欄の順は見ない。"""
    if isinstance(v, Num):
        return "数:" + str(v)
    if isinstance(v, str):
        return "字:" + v
    if v is True:
        return "真"
    if v is False:
        return "偽"
    if v is None:
        return "無"
    if isinstance(v, list):
        return "[" + ",".join(canon(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ",".join(f"{k}={canon(v[k])}" for k in sorted(v)) + "}"
    raise TypeError(type(v).__name__)


# ---------- 読む ----------

def _read_csv(path: Path, header: list[str]) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    if not rows or rows[0] != header:
        raise Stop(STOP_HEADER, f"{path.name}(期待 = {','.join(header)})")
    out = []
    for n, r in enumerate(rows[1:], 2):
        if not r:
            continue
        if len(r) != len(header):
            raise Stop(STOP_HEADER, f"{path.name} {n} 行目の列数")
        out.append(dict(zip(header, r)))
    return out


def read_runs(path: Path) -> list[dict[str, str]]:
    return _read_csv(path, RUN_HEADER)


def read_fields(path: Path) -> list[dict[str, str]]:
    return _read_csv(path, FIELD_HEADER)


def read_samples(path: Path) -> list[dict]:
    out = []
    with open(path, encoding="utf-8-sig") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line, parse_int=Num, parse_float=Num, parse_constant=Num)
            except json.JSONDecodeError:
                raise Stop(STOP_JSON, f"{path.name} {n} 行目") from None
            if not isinstance(row, dict):
                raise Stop(STOP_JSON, f"{path.name} {n} 行目")
            out.append(row)
    return out


# ---------- 判定 ----------

def _check_tables(runs: list[dict], samples: list[dict], fields: list[dict]) -> tuple[dict, dict]:
    run_map: dict[str, dict] = {}
    for r in runs:
        rid = r["run_id"]
        if rid in run_map:
            raise Stop(STOP_RUN_DUP, rid)
        if not r["source"].strip():
            raise Stop(STOP_RUN_SOURCE, rid)
        counts = {}
        for k in KINDS:
            s = r[k].strip()
            if s == "":
                counts[k] = None
            elif s.isascii() and s.isdigit():
                counts[k] = int(s)
            else:
                raise Stop(STOP_COUNT, f"{rid} の {k} = {s}")
        run_map[rid] = {"counts": counts, "source": r["source"]}
    reg: dict[str, str] = {}
    for f in fields:
        if f["field"] in reg:
            raise Stop(STOP_FIELD_DUP, f["field"])
        if f["symbol"] not in SYMBOLS:
            raise Stop(STOP_SYMBOL, f"{f['field']} = {f['symbol']}")
        if not f["source"].strip():
            raise Stop(STOP_FIELD_SOURCE, f["field"])
        reg[f["field"]] = f["symbol"]
    for i, s in enumerate(samples, 1):
        for k in SAMPLE_KEYS:
            if k not in s:
                raise Stop(STOP_SAMPLE_COLS, f"{i} 本目に {k} が無い")
        if s["kind"] not in KINDS:
            raise Stop(STOP_KIND, f"{i} 本目 = {s['kind']}")
        for side in ("old", "new"):
            if s[side] is not None and not isinstance(s[side], dict):
                raise Stop(STOP_PAYLOAD, f"{i} 本目の {side}")
        if not isinstance(s["run_id"], str) or not isinstance(s["key"], str) or not isinstance(s["source"], str):
            raise Stop(STOP_SAMPLE_COLS, f"{i} 本目の run_id / key / source は文字列で書く")
    return run_map, reg


def compare(old: dict, new: dict, reg: dict[str, str]) -> tuple[str, list[dict], list[str]]:
    """changed の見本 1 本を欄ごとに比べ、(区分, 違った欄の一覧, 同じだった欄の名前) を返す。"""
    diffs, same = [], []
    for name in sorted(set(old) | set(new)):
        if name in old and name in new:
            if canon(old[name]) == canon(new[name]):
                same.append(name)
                continue
            side = ""
        elif name in old:
            side = "old にだけ"
        else:
            side = "new にだけ"
        diffs.append({"欄": name, "記号": reg.get(name, UNREGISTERED), "片側だけ": side})
    marks = [d["記号"] for d in diffs]
    if not diffs:
        cls = A
    elif UNREGISTERED in marks:
        cls = D
    elif "数値の欄" in marks:
        cls = C
    elif all(m == "文言の欄" for m in marks):
        cls = B
    else:
        cls = E
    return cls, diffs, same


def _over(counts: dict, n_by_kind: dict) -> bool:
    return any(n_by_kind[k] > counts[k] for k in KINDS)


def judge(runs: list[dict], samples: list[dict], fields: list[dict]) -> dict:
    """3 表(読んだ後の行の一覧)から判定部分を作る。入力の一覧は書き換えない。"""
    return _judge(runs, samples, fields)[0]


def _judge(runs: list[dict], samples: list[dict], fields: list[dict]) -> tuple[dict, list[dict]]:
    """(判定部分, 見本の台帳の行順のままの見本ごとの行) を返す。"""
    run_map, reg = _check_tables(runs, samples, fields)

    n_by_run: dict[str, dict[str, int]] = {rid: {k: 0 for k in KINDS} for rid in run_map}
    key_count: dict[tuple[str, str], int] = {}
    for s in samples:
        if s["run_id"] in n_by_run:
            n_by_run[s["run_id"]][s["kind"]] += 1
        key_count[(s["run_id"], s["key"])] = key_count.get((s["run_id"], s["key"]), 0) + 1

    def aside_of(s: dict) -> str | None:
        if not s["source"].strip():
            return ASIDE_SOURCE
        run = run_map.get(s["run_id"])
        if run is None:
            return ASIDE_NO_RUN
        if None in run["counts"].values():
            return ASIDE_EMPTY_COUNT
        if _over(run["counts"], n_by_run[s["run_id"]]):
            return ASIDE_OVER
        if key_count[(s["run_id"], s["key"])] > 1:
            return ASIDE_DUP
        if s["kind"] == "changed" and (not s["old"] or not s["new"]):
            return ASIDE_ONE_SIDE
        return None

    classes = {c: 0 for c in CLASSES}
    aside_changed = {a: 0 for a in ASIDE}
    aside_other = {a: 0 for a in ASIDE}
    per_sample = []
    for s in samples:
        why = aside_of(s)
        row = {"run_id": s["run_id"], "種別": s["kind"], "key": s["key"], "出典": s["source"],
               "区分": "", "別枠": why or "", "違った欄": [], "同じだった欄": []}
        if why:
            (aside_changed if s["kind"] == "changed" else aside_other)[why] += 1
        elif s["kind"] == "changed":
            cls, diffs, same = compare(s["old"], s["new"], reg)
            classes[cls] += 1
            row.update({"区分": cls, "違った欄": diffs, "同じだった欄": same})
        per_sample.append(row)
    in_order = list(per_sample)
    per_sample = sorted(per_sample, key=lambda r: json.dumps(r, ensure_ascii=False, sort_keys=True))

    per_run = []
    for rid in sorted(run_map):
        counts, n = run_map[rid]["counts"], n_by_run[rid]
        n_total = sum(n.values())
        if None in counts.values():
            cover, total, missing = COVER_EMPTY, None, []
        else:
            total = sum(counts.values())
            missing = [k for k in KINDS if counts[k] > 0 and n[k] == 0]
            if _over(counts, n):
                cover = COVER_OVER
            elif total == 0:
                cover = COVER_ZERO
            elif n_total == 0:
                cover = COVER_NONE
            elif n_total == total:
                cover = COVER_ALL
            else:
                cover = COVER_PART
        per_run.append({"run_id": rid, "件数": dict(counts), "件数の合計": total, "見本の本数": dict(n),
                        "見本の本数の合計": n_total, "見本の範囲": cover,
                        "件数は在るのに見本が 1 本も無い種別": missing, "出典": run_map[rid]["source"]})

    n_kind = {k: sum(1 for s in samples if s["kind"] == k) for k in KINDS}
    return {
        "回の件数": len(runs),
        "見本の台帳の行数": len(samples),
        "種別ごとの見本の本数": n_kind,
        "区分": classes,
        "別枠(changed の見本)": aside_changed,
        "別枠(added / removed の見本)": aside_other,
        "見本の範囲ごとの回の件数": {c: sum(1 for r in per_run if r["見本の範囲"] == c) for c in COVERS},
        "回ごと": per_run,
        "見本ごと": per_sample,
    }, in_order


def digest(judged: dict) -> str:
    return hashlib.sha256(json.dumps(judged, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def sums(judged: dict) -> dict:
    """件数の検算(2 通りの数え方が合うか)。"""
    n_changed = judged["種別ごとの見本の本数"]["changed"]
    left = sum(judged["区分"].values()) + sum(judged["別枠(changed の見本)"].values())
    by_run = sum(r["見本の本数の合計"] for r in judged["回ごと"])
    no_run = sum(1 for r in judged["見本ごと"] if r["別枠"] == ASIDE_NO_RUN)
    return {"区分 + 別枠": left, "changed の見本の本数": n_changed,
            "回ごとの見本の本数の合計 + 回の台帳に無い回を指す見本": by_run + no_run,
            "見本の台帳の行数": judged["見本の台帳の行数"],
            "合う": left == n_changed and by_run + no_run == judged["見本の台帳の行数"]}


def check(runs: list[dict], samples: list[dict], fields: list[dict], detail: bool = False) -> dict:
    try:
        judged = judge(runs, samples, fields)
    except Stop as e:
        return {"ok": False, "止まった理由": e.code, "場所": e.where,
                "区分": {c: 0 for c in CLASSES}, "見本ごと": [], "持たせていないもの": list(NOT_HELD)}
    out = {"ok": True}
    out.update({k: v for k, v in judged.items() if detail or k not in ("回ごと", "見本ごと")})
    out["件数の検算"] = sums(judged)
    out["持たせていないもの"] = list(NOT_HELD)
    return out


# ---------- verify ----------

def _tweak(v: object) -> object:
    """値を 1 文字だけ変えた写しを返す。"""
    if isinstance(v, Num):
        s = str(v)
        return Num(s[:-1] + ("1" if s[-1] == "0" else "0"))
    if isinstance(v, str) and v:
        return v[:-1] + ("1" if v[-1] == "0" else "0")
    return Num("0") if canon(v) != "数:0" else Num("1")


def _reorder(samples: list[dict]) -> list[dict]:
    """行順を逆にし、old / new の欄の順も逆にした写し。"""
    def flip(d: object) -> object:
        return {k: d[k] for k in reversed(list(d))} if isinstance(d, dict) else d
    return [{**s, "old": flip(s["old"]), "new": flip(s["new"])} for s in reversed(samples)]


def _labels(runs: list[dict], samples: list[dict], fields: list[dict]) -> list[str]:
    """見本の台帳の行順のまま、区分か別枠の名前を並べる。"""
    return [r["区分"] or "別枠:" + r["別枠"] for r in _judge(runs, samples, fields)[1]]


def verify(runs: list[dict], samples: list[dict], fields: list[dict]) -> dict:
    try:
        base, rows = _judge(runs, samples, fields)
    except Stop as e:
        return {"ok": False, "止まった理由": e.code, "場所": e.where}
    d0 = digest(base)
    res: dict = {}

    res["① 二度走りの sha256 が同一"] = {"合う": digest(judge(runs, samples, fields)) == d0, "先頭 12 桁": d0[:12]}

    variants = [
        judge(list(reversed(runs)), _reorder(samples), list(reversed(fields))),
        judge(runs[1:] + runs[:1], samples[1:] + samples[:1], fields[1:] + fields[:1]),
    ]
    res["② 行順と欄の順を入れ替えても同一"] = {"合う": all(digest(v) == d0 for v in variants),
                                             "入れ替え方": len(variants)}

    res["③ 件数の検算"] = sums(base)

    reg = {f["field"]: f["symbol"] for f in fields}
    labels = [r["区分"] or "別枠:" + r["別枠"] for r in rows]

    tried = moved_ok = 0
    for i, smp in enumerate(samples):
        if labels[i] != A:
            continue
        nums = [n for n in sorted(smp["new"]) if reg.get(n) == "数値の欄"]
        if not nums:
            continue
        tried += 1
        copy = [dict(x) for x in samples]
        copy[i]["new"] = {**smp["new"], nums[0]: _tweak(smp["new"][nums[0]])}
        got = _labels(runs, copy, fields)
        moved_ok += got[i] == C and all(got[j] == labels[j] for j in range(len(labels)) if j != i)
    res["④ (A) の見本の数値の欄を 1 文字変えた写し"] = {
        "合う": tried == moved_ok, "試した見本": tried, "その 1 本だけが (C) へ動いた": moved_ok}

    ok_f = moved_total = 0
    for f in fields:
        name = f["field"]
        got = _labels(runs, samples, [x for x in fields if x["field"] != name])
        good = True
        for i, r in enumerate(rows):
            if any(dd["欄"] == name for dd in r["違った欄"]):
                good = good and got[i] == D
                moved_total += labels[i] != D
            else:
                good = good and got[i] == labels[i]
        ok_f += good
    res["⑤ 欄の登録表から 1 欄を消した写し"] = {
        "合う": ok_f == len(fields), "消した欄": len(fields), "その欄が違う見本だけが (D) になった": ok_f,
        "(D) へ動いた見本の延べ本数": moved_total}

    return {"ok": all(v["合う"] for v in res.values()), "verify": res}


# ---------- CLI ----------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="差分の記録の「替わった」の見本を、前と後で欄ごとに見比べて区分する")
    p.add_argument("command", choices=["check", "rows", "verify"])
    p.add_argument("runs", type=Path, help="回の台帳 (CSV)")
    p.add_argument("samples", type=Path, help="見本の台帳 (JSONL)")
    p.add_argument("fields", type=Path, help="欄の登録表 (CSV)")
    a = p.parse_args(argv)
    try:
        tables = (read_runs(a.runs), read_samples(a.samples), read_fields(a.fields))
    except Stop as e:
        out = {"ok": False, "止まった理由": e.code, "場所": e.where}
    else:
        out = verify(*tables) if a.command == "verify" else check(*tables, detail=a.command == "rows")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    if not out["ok"]:
        return 2
    if a.command != "verify" and (sum(out["別枠(changed の見本)"].values()) or sum(out["別枠(added / removed の見本)"].values())):
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
