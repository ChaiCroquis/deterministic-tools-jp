"""roll_forward — 増減の台帳を期首から 1 回ずつ歩いて累計を出し、文書に書かれた総数がどの回の累計に当たるかを返す。

入力は 3 表(どの行にも出典の欄が要る):
  ① 増減の台帳   run_id, run_at, status, added, removed, changed, opening, unit, source
  ② 状態の記号の登録表 status, meaning(通った / 落ちた), needs_delta(要る / 要らない), source
  ③ 総数の宣言の台帳  claim_id, total, unit, quote, source

持たせていないもの: 行の中身を読む経路、指紋を比べる経路、足りない回を補う経路、空を 0 にする経路、
正しい側の列、一致率の 1 値、原因を言い当てる経路、時計を読む経路、入力を書き換える経路、float、通信。

使い方:
  python roll_forward.py init   <出力先 dir>
  python roll_forward.py check  runs.csv statuses.csv claims.csv
  python roll_forward.py rows   runs.csv statuses.csv claims.csv
  python roll_forward.py verify runs.csv statuses.csv claims.csv
終了コード: 0 = 全ての宣言に当たる回が在る / 1 = 当たる回なしの宣言が在る / 2 = 1 回も歩かずに止まった、または表として読めない
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

RUN_COLS = ["run_id", "run_at", "status", "added", "removed", "changed", "opening", "unit", "source"]
STATUS_COLS = ["status", "meaning", "needs_delta", "source"]
CLAIM_COLS = ["claim_id", "total", "unit", "quote", "source"]

MEANINGS = ("通った", "落ちた")
NEEDS = ("要る", "要らない")
OPENING_MARK = "期首"
NO_FIELD = "欄が無い"
NO_HIT = "当たる回なし"

CLASS_A = "(A) 増か減の片方だけが在り累計が動いた"
CLASS_B = "(B) 増減が 0 で累計が動かない"
CLASS_C = "(C) 増と減が両方在る"
CLASS_D = "(D) 増減の欄が無い"
CLASSES = (CLASS_A, CLASS_B, CLASS_C, CLASS_D)

REASONS = {
    "E1": "出典が空",
    "E2": "状態の記号が登録表に無い",
    "E3": "期首の印が 1 件でない、先頭の回に無い、または期首の回に増減の欄が無い",
    "E4": "件数が負か整数でない(3 欄の一部だけが空の行も含む)",
    "E5": "累計が負になる(在る以上に減った)",
    "E6": "単位の名前が空か、台帳と宣言で違う(比べずに止める)",
}

TAIL = [
    "行の中身を読まない: 入るのは件数と記号と出典だけで、増えた行・減った行が何であったかは見ない",
    "指紋を比べない: 出力の指紋の列を持たない(差分の件数と指紋の 2 経路を並べるのは diff_tally の仕事)",
    "足りない回を補わない: 台帳に行として無い回は歩かない。飛びを埋める経路が無い",
    "空を 0 にしない: 増減の欄が空の回は「欄が無い」のまま前の回の累計を引き継ぎ、0 とは書かない",
    "正しい側を決めない: 台帳と文書のどちらを直すかの列が無い。当たる回が在るか無いかだけを返す",
    "一致率を出さない: 当たる回が在る宣言の件数と宣言の総件数を必ず並べ、割った値は作らない",
    "原因を言い当てない: 当たる回なしのときに出すのは最も近い累計との差(整数)だけ",
    "どの回が「その宣言の時点」かを選ばない: 累計が一致した回を全部返すだけで、時計も読まない",
    "入力を書き換えない: verify が作る写しはメモリの中だけで、入力の表には 1 文字も書かない",
]


class TableError(Exception):
    """表として読めない(列が無い / 行が無い / id の重複 / 登録表の値が決めた語でない)。"""


# ---------- 読む ----------

def read_table(path: Path, cols: list[str]) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        missing = [c for c in cols if c not in header]
        if missing:
            raise TableError(f"{Path(path).name}: 列が無い {missing}")
        rows = [{c: (r.get(c) or "") for c in cols} for r in reader]
    if not rows:
        raise TableError(f"{Path(path).name}: 行が無い")
    return rows


def _is_count(s: str) -> bool:
    return s != "" and s.isascii() and s.isdigit()


def _check_shape(runs: list[dict], statuses: list[dict], claims: list[dict]) -> None:
    for name, rows, cols in (("増減の台帳", runs, RUN_COLS), ("状態の記号の登録表", statuses, STATUS_COLS),
                             ("総数の宣言の台帳", claims, CLAIM_COLS)):
        if not rows:
            raise TableError(f"{name}: 行が無い")
        for r in rows:
            for c in cols:
                if c not in r or not isinstance(r[c], str):
                    raise TableError(f"{name}: 列が無い {c}")
    for name, rows, key in (("増減の台帳", runs, "run_id"), ("状態の記号の登録表", statuses, "status"),
                            ("総数の宣言の台帳", claims, "claim_id")):
        ids = [r[key] for r in rows]
        if any(i == "" for i in ids):
            raise TableError(f"{name}: {key} が空の行が在る")
        if len(set(ids)) != len(ids):
            raise TableError(f"{name}: {key} が重複している")
    for s in statuses:
        if s["meaning"] not in MEANINGS:
            raise TableError(f"状態の記号の登録表: meaning は {MEANINGS} のどちらか({s['status']})")
        if s["needs_delta"] not in NEEDS:
            raise TableError(f"状態の記号の登録表: needs_delta は {NEEDS} のどちらか({s['status']})")
    for r in runs:
        if r["opening"] not in ("", OPENING_MARK):
            raise TableError(f"増減の台帳: opening は空か「{OPENING_MARK}」({r['run_id']})")


# ---------- 歩く ----------

def _find_reasons(runs: list[dict], reg: dict[str, dict], claims: list[dict]) -> list[dict]:
    out: list[dict] = []

    def add(code: str, where: str) -> None:
        out.append({"理由コード": code, "理由": REASONS[code], "どこ": where})

    for name, rows, key in (("増減の台帳", runs, "run_id"), ("状態の記号の登録表", list(reg.values()), "status"),
                            ("総数の宣言の台帳", claims, "claim_id")):
        for r in rows:
            if r["source"].strip() == "":
                add("E1", f"{name} {r[key]}")
    for r in runs:
        if r["status"] not in reg:
            add("E2", f"増減の台帳 {r['run_id']}")
    marks = [r for r in runs if r["opening"] == OPENING_MARK]
    if len(marks) != 1:
        add("E3", f"増減の台帳 期首の印 {len(marks)} 件")
    elif marks[0] is not runs[0]:
        add("E3", f"増減の台帳 {marks[0]['run_id']}(先頭の回は {runs[0]['run_id']})")
    elif all(runs[0][c] == "" for c in ("added", "removed", "changed")):
        add("E3", f"増減の台帳 {runs[0]['run_id']}(期首の回に増減の欄が無い)")
    for r in runs:
        cells = [r[c] for c in ("added", "removed", "changed")]
        if all(c == "" for c in cells):
            continue
        if not all(_is_count(c) for c in cells):
            add("E4", f"増減の台帳 {r['run_id']}")
    for c in claims:
        if not _is_count(c["total"]):
            add("E4", f"総数の宣言の台帳 {c['claim_id']}")
    units = {r["unit"] for r in runs}
    if "" in units or len(units) != 1:
        add("E6", "増減の台帳 unit")
    else:
        unit = next(iter(units))
        for c in claims:
            if c["unit"] != unit:
                add("E6", f"総数の宣言の台帳 {c['claim_id']}(台帳は {unit} / 宣言は {c['unit'] or '空'})")
    return out


def _stopped(n_runs: int, n_claims: int, reasons: list[dict]) -> dict:
    core = {
        "区分": {k: 0 for k in CLASSES},
        "別枠(1 回も歩かずに止まった回)": n_runs,
        "回": [],
        "宣言": [],
        "文書に現れない累計": [],
        "登録と欄の有無が食い違う回": [],
        "止まった理由": reasons,
    }
    return _wrap(False, n_runs, n_claims, 0, core)


def _wrap(ok: bool, n_runs: int, n_claims: int, n_hit: int, core: dict) -> dict:
    blob = json.dumps(core, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    total = sum(core["区分"].values()) + core["別枠(1 回も歩かずに止まった回)"]
    return {
        "ok": ok,
        "分母(回の件数)": n_runs,
        "分母(宣言の件数)": n_claims,
        "当たる回が在る宣言の件数 / 宣言の総件数": f"{n_hit} / {n_claims}",
        **core,
        "件数の検算": f"区分 4 値 + 別枠の合計 {total} / 回の件数 {n_runs}",
        "判定部分の sha256": hashlib.sha256(blob).hexdigest(),
        "持たせていないもの": list(TAIL),
    }


def roll(runs: list[dict], statuses: list[dict], claims: list[dict]) -> dict:
    """3 表(dict の list)を受け取り、累計と突き合わせの結果を返す。入力は書き換えない。"""
    _check_shape(runs, statuses, claims)
    runs = sorted(({k: r[k] for k in RUN_COLS} for r in runs), key=lambda r: r["run_id"])
    claims = sorted(({k: c[k] for k in CLAIM_COLS} for c in claims), key=lambda c: c["claim_id"])
    reg = {s["status"]: {k: s[k] for k in STATUS_COLS} for s in statuses}

    reasons = _find_reasons(runs, reg, claims)
    if reasons:
        return _stopped(len(runs), len(claims), reasons)

    rows: list[dict] = []
    mismatch: list[dict] = []
    cum = 0
    for r in runs:
        prev = cum
        has_delta = r["added"] != ""
        needs = reg[r["status"]]["needs_delta"]
        if has_delta:
            a, d, ch = int(r["added"]), int(r["removed"]), int(r["changed"])
            cum = prev + a - d
            if cum < 0:
                return _stopped(len(runs), len(claims),
                                [{"理由コード": "E5", "理由": REASONS["E5"], "どこ": f"増減の台帳 {r['run_id']}"}])
            if a > 0 and d > 0:
                cls = CLASS_C
            elif a == 0 and d == 0:
                cls = CLASS_B
            else:
                cls = CLASS_A
            row = {"回": r["run_id"], "時刻(写し)": r["run_at"], "状態": r["status"],
                   "意味": reg[r["status"]]["meaning"], "前の回の累計": prev, "増": a, "減": d,
                   "その回の累計": cum, "替わった件数(累計に入れない)": ch, "区分": cls,
                   "印": "", "出典": r["source"]}
            if cls == CLASS_C:
                row["純増減"] = a - d
                row["総増減"] = a + d
            if needs == "要らない":
                mismatch.append({"回": r["run_id"], "形": "登録では増減の欄が要らないのに在る"})
        else:
            row = {"回": r["run_id"], "時刻(写し)": r["run_at"], "状態": r["status"],
                   "意味": reg[r["status"]]["meaning"], "前の回の累計": prev, "増": NO_FIELD, "減": NO_FIELD,
                   "その回の累計": prev, "替わった件数(累計に入れない)": NO_FIELD, "区分": CLASS_D,
                   "印": f"{NO_FIELD}(前の回の累計を引き継いだ)", "出典": r["source"]}
            if needs == "要る":
                mismatch.append({"回": r["run_id"], "形": "登録では増減の欄が要るのに無い"})
        rows.append(row)

    walked = [r for r in rows if r["区分"] != CLASS_D]
    carried = [r for r in rows if r["区分"] == CLASS_D]
    cums = sorted({r["その回の累計"] for r in walked})
    out_claims: list[dict] = []
    n_hit = 0
    for c in claims:
        total = int(c["total"])
        hit = [r["回"] for r in walked if r["その回の累計"] == total]
        item = {"宣言": c["claim_id"], "総数": total, "単位": c["unit"], "文(写し)": c["quote"], "出典": c["source"],
                "累計が一致した回": hit if hit else NO_HIT,
                "引き継ぎで同じ値の回(欄が無い)": [r["回"] for r in carried if r["その回の累計"] == total]}
        if hit:
            n_hit += 1
        else:
            best = min(abs(total - v) for v in cums)
            item["最も近い累計との差(宣言 − 累計)"] = sorted(total - v for v in cums if abs(total - v) == best)
        out_claims.append(item)

    claimed = {int(c["total"]) for c in claims}
    unseen = [{"累計": v, "回": [r["回"] for r in walked if r["その回の累計"] == v]} for v in cums if v not in claimed]

    counts = {k: sum(1 for r in rows if r["区分"] == k) for k in CLASSES}
    core = {
        "区分": counts,
        "別枠(1 回も歩かずに止まった回)": 0,
        "回": rows,
        "宣言": out_claims,
        "文書に現れない累計": unseen,
        "登録と欄の有無が食い違う回": mismatch,
        "止まった理由": [],
    }
    return _wrap(True, len(runs), len(claims), n_hit, core)


# ---------- verify ----------

def verify(runs: list[dict], statuses: list[dict], claims: list[dict]) -> dict:
    """この手続きが決定論かを 5 つ見る。写しはメモリの中だけ。"""
    base = roll(runs, statuses, claims)
    out: dict = {"ok": True, "見たもの": []}

    def note(name: str, ok: bool, detail: str) -> None:
        out["見たもの"].append({"何を": name, "結果": "合う" if ok else "合わない", "中身": detail})
        out["ok"] = out["ok"] and ok

    again = roll(runs, statuses, claims)
    note("① 二度走りの判定部分の sha256", base["判定部分の sha256"] == again["判定部分の sha256"],
         base["判定部分の sha256"][:12])

    orders = [list(reversed(claims)), claims[1:] + claims[:1]]
    same = all(roll(runs, statuses, o)["判定部分の sha256"] == base["判定部分の sha256"] for o in orders)
    note("② 宣言の台帳の行順を入れ替えても同じ出力", same, f"入れ替え {len(orders)} 通り")

    total = sum(base["区分"].values()) + base["別枠(1 回も歩かずに止まった回)"]
    note("③ 区分 4 値 + 別枠の合計 = 回の件数", total == base["分母(回の件数)"], base["件数の検算"])

    if not base["ok"]:
        note("④⑤ 写し", True, "止まった表なので写しは作らない")
        return out

    ordered = sorted(runs, key=lambda r: r["run_id"])
    walked_ids = [r["回"] for r in base["回"] if r["区分"] != CLASS_D]
    ok4, n4 = True, 0
    for rid in walked_ids:
        copy = [dict(r) for r in ordered]
        i = next(k for k, r in enumerate(copy) if r["run_id"] == rid)
        copy[i]["added"] = str(int(copy[i]["added"]) + 1)
        got = roll(copy, statuses, claims)
        n4 += 1
        for k, (b, g) in enumerate(zip(base["回"], got["回"])):
            want = b["その回の累計"] + (1 if k >= i else 0)
            ok4 = ok4 and g["その回の累計"] == want
    note("④ 1 回の増えた件数を 1 増やすと、その回以降の累計だけが 1 増える", ok4, f"写し {n4} 枚")

    ok5, n5, skipped = True, 0, 0
    for rid in walked_ids[1:]:
        copy = [dict(r) for r in ordered]
        i = next(k for k, r in enumerate(copy) if r["run_id"] == rid)
        for c in ("added", "removed", "changed"):
            copy[i][c] = ""
        got = roll(copy, statuses, claims)
        if not got["ok"]:
            skipped += 1
            continue
        n5 += 1
        g = got["回"][i]
        ok5 = ok5 and g["区分"] == CLASS_D and g["その回の累計"] == g["前の回の累計"] == base["回"][i]["前の回の累計"]
        ok5 = ok5 and all(a["その回の累計"] == b["その回の累計"] for a, b in zip(base["回"][:i], got["回"][:i]))
    note("⑤ 1 回の増減を空にすると、その回だけ (D) へ移り前の回の累計を引き継ぐ", ok5,
         f"写し {n5} 枚(後ろの累計が負になって止まった写し {skipped} 枚は数えない)")
    return out


# ---------- CLI ----------

TEMPLATES = {
    "runs.csv": ",".join(RUN_COLS) + "\nR01,(時刻の写し),S1,0,0,0,期首,行,(ファイル名 + 行番号)\n",
    "statuses.csv": ",".join(STATUS_COLS) + "\nS1,通った,要る,(ファイル名 + 行番号)\nS2,落ちた,要らない,(ファイル名 + 行番号)\n",
    "claims.csv": ",".join(CLAIM_COLS) + "\nC1,0,行,(総数を書いた文の写し),(ファイル名 + 行番号)\n",
}


def _load(args: argparse.Namespace) -> tuple[list[dict], list[dict], list[dict]]:
    return (read_table(Path(args.runs), RUN_COLS), read_table(Path(args.statuses), STATUS_COLS),
            read_table(Path(args.claims), CLAIM_COLS))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="増減の台帳を期首から歩いて累計を出し、文書の総数に当てる")
    sub = p.add_subparsers(dest="cmd", required=True)
    pi = sub.add_parser("init")
    pi.add_argument("dir")
    for name in ("check", "rows", "verify"):
        ps = sub.add_parser(name)
        ps.add_argument("runs")
        ps.add_argument("statuses")
        ps.add_argument("claims")
    args = p.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    if args.cmd == "init":
        d = Path(args.dir)
        d.mkdir(parents=True, exist_ok=True)
        for name, text in TEMPLATES.items():
            target = d.joinpath(name)
            if target.exists():
                print(f"在るので書かない: {target}")
                continue
            target.write_text(text, encoding="utf-8", newline="")
            print(f"書いた: {target}")
        return 0

    try:
        runs, statuses, claims = _load(args)
        if args.cmd == "verify":
            res = verify(runs, statuses, claims)
            print(json.dumps(res, ensure_ascii=False, indent=1))
            return 0 if res["ok"] else 2
        res = roll(runs, statuses, claims)
    except TableError as e:
        print(json.dumps({"ok": False, "表として読めない": str(e)}, ensure_ascii=False, indent=1))
        return 2

    if args.cmd == "check":
        res = {k: v for k, v in res.items() if k not in ("回", "宣言")}
    print(json.dumps(res, ensure_ascii=False, indent=1))
    if not res["ok"]:
        return 2
    hit, n = res["当たる回が在る宣言の件数 / 宣言の総件数"].split(" / ")
    return 0 if hit == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
