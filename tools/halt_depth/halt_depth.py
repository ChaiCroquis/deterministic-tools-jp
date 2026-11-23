"""halt_depth — 実行の記録のエラーの欄を行に割り、人が登録した印がどこまで出てから止まったかを回ごとに並べる。

止まった理由を当てない・印の後ろの文字列を数に直さない・状態の文字列を直さない。
印は人が登録した字を、行頭に literal で当てるだけ(字面から印を見つけない)。
伏せる行の登録表の字を含む行は、出力のどの欄にも写さず、件数だけ返す。

入力は 4 表(どの行にも出典の欄が要る):
  回の台帳         run_id, status, error, source        error は空でもよい。改行を含む文字列をそのまま
  印の登録表       mark_id, text, stage, order, kind, source
                   text = 行頭に literal で当てる字 / order = 並び順の整数 / kind = 「通過の印」か「止まった印」
  段の登録表       stage, name, source                  段の記号と、上の層の段の名前
  伏せる行の登録表 text, source                         この字を含む行は写さない

回の台帳は .jsonl でも読める(1 行 1 回。回 id は「L<行番号>」、出典は「<label> L<行番号>」になる)。

使い方:
  python halt_depth.py init <dir>
  python halt_depth.py check 回.csv 印.csv 段.csv 伏せる行.csv [--text]
  python halt_depth.py check 履歴.jsonl 印.csv 段.csv 伏せる行.csv --label 実行の履歴 [--text]
  python halt_depth.py verify 回.csv 印.csv 段.csv 伏せる行.csv
終了コード: 0 = 並べた / 3 = 理由コードで止まった / 2 = 表として読めない
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

COLS = {
    "runs": ["run_id", "status", "error", "source"],
    "marks": ["mark_id", "text", "stage", "order", "kind", "source"],
    "stages": ["stage", "name", "source"],
    "hides": ["text", "source"],
}
NEED_ROWS = ("runs",)                    # 0 行では読めない表(登録表 3 つは 0 行でも読める)
KIND_PASS, KIND_HALT = "通過の印", "止まった印"
KINDS = (KIND_PASS, KIND_HALT)
CLASSES = {
    "A": "(A) 止まった印が在り、登録した通過の印が全部在る",
    "B": "(B) 止まった印が在り、通過の印の一部が無い",
    "C": "(C) エラーの文字列は在るが、登録した印が 1 つも無い",
    "D": "(D) エラーの文字列が空",
    "E": "(E) 通過の印は在るが、止まった印が無い",
}
BOX_HEAD = "別枠: "
RUN_BOXES = ["同じ回 id が 2 回", "出典が空"]
MARK_BOXES = ["印の文字列が空", "出典が空", "登録表に無い段の記号", "並び順が重なる", "伏せる行の字が印の文字列を含む"]
REASONS = {
    "E1": "印の登録表で、印 id が空か、同じ印 id が 2 回在る",
    "E2": "印の種類が「通過の印」「止まった印」以外",
    "E3": "印の並び順が整数でない",
    "E4": "段の登録表で、記号・名前・出典のどれかが空か、同じ記号が 2 回在る",
    "E5": "伏せる行の登録表で、字か出典が空",
}
PRESENT, ABSENT = "在る", "無い"
FLAG_REPEAT = "同じ印が 1 回の中に 2 行以上在る"
FLAG_VARY = "同じ印の後ろの文字列が回によって違う"
NOT_HELD = [
    "止まった理由を分類する経路(返すのは、どの印が在ったか・無かったかまで)",
    "印の後ろの文字列を数に直して比べる経路(文字列のまま並べる)",
    "2 つの値のどちらが期待でどちらが実際かを当てる経路",
    "上流の変化か実装の不具合かを分ける経路",
    "状態の文字列を書き換える経路・語の意味を読む経路",
    "伏せた行の中身を返す経路(返すのは件数と行番号だけ)",
    "印を字面から自動で見つける経路(印は人が登録した字だけ)",
]


class TableError(Exception):
    """表として読めない(列が足りない・0 行・ファイルが無い など)。"""


def read_table(path: str | Path, kind: str) -> list[dict]:
    p = Path(path)
    if not p.is_file():
        raise TableError(f"{kind}: ファイルが無い: {p.name}")
    try:
        with p.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            head = reader.fieldnames or []
            rows = [dict(r) for r in reader]
    except (UnicodeDecodeError, csv.Error) as e:
        raise TableError(f"{kind}: 読めない({type(e).__name__})") from None
    lack = [c for c in COLS[kind] if c not in head]
    if lack:
        raise TableError(f"{kind}: 列が足りない: {', '.join(lack)}")
    out = []
    for r in rows:
        if any(r.get(c) is None for c in COLS[kind]):
            raise TableError(f"{kind}: 欄の数が足りない行が在る")
        out.append({c: r[c] for c in COLS[kind]})
    if kind in NEED_ROWS and not out:
        raise TableError(f"{kind}: 0 行")
    return out


def read_runs_jsonl(path: str | Path, label: str, status_key: str = "status", error_key: str = "error") -> list[dict]:
    """1 行 1 回の JSON を回の台帳として読む。回 id は L<行番号>、出典は <label> L<行番号>。"""
    p = Path(path)
    if not p.is_file():
        raise TableError(f"runs: ファイルが無い: {p.name}")
    out = []
    try:
        lines = p.read_text(encoding="utf-8-sig").split("\n")
    except UnicodeDecodeError:
        raise TableError("runs: 読めない(UnicodeDecodeError)") from None
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            raise TableError(f"runs: L{n} が JSON として読めない") from None
        if not isinstance(obj, dict) or status_key not in obj or error_key not in obj:
            raise TableError(f"runs: L{n} に {status_key} / {error_key} の欄が無い")
        err = obj[error_key]
        if err is None:
            err = ""
        if not isinstance(err, str) or not isinstance(obj[status_key], str):
            raise TableError(f"runs: L{n} の {status_key} / {error_key} が文字列でない")
        out.append({"run_id": f"L{n}", "status": obj[status_key], "error": err, "source": f"{label} L{n}"})
    if not out:
        raise TableError("runs: 0 行")
    return out


def read_runs(path: str | Path, label: str | None = None) -> list[dict]:
    p = Path(path)
    if p.suffix.lower() == ".jsonl":
        return read_runs_jsonl(p, label or p.name)
    return read_table(p, "runs")


def split_lines(error: str) -> list[str]:
    """エラーの文字列を行に割る。CRLF は LF として割る。末尾の空行も 1 行に数える。"""
    return error.replace("\r\n", "\n").split("\n")


def _stop(code: str) -> dict:
    return {"ok": False, "理由コード": code, "理由": REASONS[code], "回": [], "持たせていないもの": NOT_HELD}


def _is_int(s: str) -> bool:
    t = s[1:] if s[:1] == "-" else s
    return t != "" and t.isascii() and t.isdigit()


def _fingerprint(obj: dict) -> str:
    body = {k: v for k, v in obj.items() if k != "指紋"}
    return hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def check(runs: list[dict], marks: list[dict], stages: list[dict], hides: list[dict]) -> dict:
    # ---- 登録の側が崩れていたら、1 回も並べずに止まる(理由コードは決まった順で最初の 1 つ) ----
    ids = [m["mark_id"] for m in marks]
    if any(i == "" for i in ids) or len(set(ids)) != len(ids):
        return _stop("E1")
    if any(m["kind"] not in KINDS for m in marks):
        return _stop("E2")
    if any(not _is_int(m["order"]) for m in marks):
        return _stop("E3")
    syms = [s["stage"] for s in stages]
    if any(s["stage"] == "" or s["name"] == "" or s["source"] == "" for s in stages) or len(set(syms)) != len(syms):
        return _stop("E4")
    if any(h["text"] == "" or h["source"] == "" for h in hides):
        return _stop("E5")

    stage_name = {s["stage"]: s["name"] for s in stages}
    hide_texts = sorted({h["text"] for h in hides})

    # ---- 印の別枠 ----
    order_count: dict[int, int] = {}
    for m in marks:
        order_count[int(m["order"])] = order_count.get(int(m["order"]), 0) + 1

    def mark_box(m: dict) -> str | None:
        if m["text"] == "":
            return MARK_BOXES[0]
        if m["source"] == "":
            return MARK_BOXES[1]
        if m["stage"] not in stage_name:
            return MARK_BOXES[2]
        if order_count[int(m["order"])] > 1:
            return MARK_BOXES[3]
        if any(m["text"] in h for h in hide_texts):
            return MARK_BOXES[4]
        return None

    used, boxed_marks = [], []
    mark_box_n = {b: 0 for b in MARK_BOXES}
    for m in sorted(marks, key=lambda m: (int(m["order"]), m["mark_id"])):
        b = mark_box(m)
        if b is None:
            used.append(m)
        else:
            mark_box_n[b] += 1
            boxed_marks.append({"印": m["mark_id"], "区分": BOX_HEAD + b})
    boxed_marks.sort(key=lambda r: r["印"])
    pass_ids = [m["mark_id"] for m in used if m["kind"] == KIND_PASS]
    halt_ids = [m["mark_id"] for m in used if m["kind"] == KIND_HALT]

    # ---- 回の別枠 ----
    id_count: dict[str, int] = {}
    for r in runs:
        id_count[r["run_id"]] = id_count.get(r["run_id"], 0) + 1

    def run_box(r: dict) -> str | None:
        if id_count[r["run_id"]] > 1:
            return RUN_BOXES[0]
        if r["source"] == "":
            return RUN_BOXES[1]
        return None

    class_n = {v: 0 for v in CLASSES.values()}
    run_box_n = {b: 0 for b in RUN_BOXES}
    present_n = {m["mark_id"]: 0 for m in used}
    line_n = {"行数の合計": 0, "印に当たった行": 0, "伏せた行": 0, "空の行": 0, "どの印にも当たらなかった行": 0}
    repeats: list[dict] = []
    tails_by_mark: dict[str, set] = {m["mark_id"]: set() for m in used}
    out_runs, boxed_runs = [], []

    for r in runs:
        b = run_box(r)
        if b is not None:
            run_box_n[b] += 1
            boxed_runs.append({"回": r["run_id"], "状態": r["status"], "区分": BOX_HEAD + b})
            continue
        err = r["error"]
        lines = split_lines(err) if err != "" else []
        hidden = [any(h in ln for h in hide_texts) for ln in lines]
        per_mark = []
        hit_line = [False] * len(lines)
        for m in used:
            nums, tails, hid = [], [], 0
            for i, ln in enumerate(lines):
                if ln.startswith(m["text"]):
                    nums.append(i + 1)
                    hit_line[i] = True
                    if hidden[i]:
                        tails.append("")
                        hid += 1
                    else:
                        tails.append(ln[len(m["text"]):])
            per_mark.append({
                "印": m["mark_id"], "印の文字列": m["text"], "段": stage_name[m["stage"]], "種類": m["kind"],
                "並び順": int(m["order"]), "在る・無い": PRESENT if nums else ABSENT, "行番号": nums,
                "後ろの文字列": tails, "うち伏せた行": hid,
            })
            if nums:
                present_n[m["mark_id"]] += 1
                shown = tuple(t for t, i in zip(tails, nums) if not hidden[i - 1])
                if len(shown) > 0:               # 伏せた行にしか無い回は、比べる文字列が無いので数えない
                    tails_by_mark[m["mark_id"]].add(shown)
            if len(nums) >= 2:
                repeats.append({"回": r["run_id"], "印": m["mark_id"], "行数": len(nums)})
        n_hidden = sum(hidden)
        n_hit = sum(1 for i in range(len(lines)) if hit_line[i] and not hidden[i])
        n_empty = sum(1 for i, ln in enumerate(lines) if ln == "" and not hidden[i] and not hit_line[i])
        miss = [i + 1 for i, ln in enumerate(lines) if ln != "" and not hidden[i] and not hit_line[i]]
        got = {p["印"] for p in per_mark if p["行番号"]}
        got_pass = [i for i in pass_ids if i in got]
        got_halt = [i for i in halt_ids if i in got]
        if err == "":
            c = "D"
        elif not got:
            c = "C"
        elif not got_halt:
            c = "E"
        elif len(got_pass) == len(pass_ids):
            c = "A"
        else:
            c = "B"
        class_n[CLASSES[c]] += 1
        seen_stage: list[str] = []
        for p in per_mark:
            if p["行番号"] and p["段"] not in seen_stage:
                seen_stage.append(p["段"])
        line_n["行数の合計"] += len(lines)
        line_n["印に当たった行"] += n_hit
        line_n["伏せた行"] += n_hidden
        line_n["空の行"] += n_empty
        line_n["どの印にも当たらなかった行"] += len(miss)
        out_runs.append({
            "回": r["run_id"], "状態": r["status"], "出典": r["source"], "区分": CLASSES[c],
            "行数": len(lines), "印に当たった行の件数": n_hit, "伏せた行の件数": n_hidden, "空の行の件数": n_empty,
            "どの印にも当たらなかった行の件数": len(miss), "どの印にも当たらなかった行番号": miss,
            "在った通過の印のうち並び順が最後のもの": got_pass[-1] if got_pass else None,
            "止まった印": PRESENT if got_halt else ABSENT,
            "無かった通過の印": [i for i in pass_ids if i not in got],
            "印が在った段": seen_stage, "印": per_mark,
        })

    vary = sorted(i for i, s in tails_by_mark.items() if len(s) >= 2)
    n_class, n_box = sum(class_n.values()), sum(run_box_n.values())
    n_line4 = line_n["印に当たった行"] + line_n["伏せた行"] + line_n["空の行"] + line_n["どの印にも当たらなかった行"]
    out = {
        "ok": True,
        "回の台帳の行数": len(runs),
        "印の登録表の行数": len(marks),
        "使った印": {"通過の印": len(pass_ids), "止まった印": len(halt_ids)},
        "区分": class_n,
        "別枠": {"回": run_box_n, "印": mark_box_n},
        "印ごとの在る回数": present_n,
        "補助の印(区分には使わない)": {FLAG_REPEAT: repeats, FLAG_VARY: vary},
        "行の内訳": line_n,
        "件数の合計の検算": (
            f"区分 {n_class} + 別枠の回 {n_box} = {n_class + n_box} / 回の台帳の行数 {len(runs)}、"
            f"行の内訳 {n_line4} / 行数の合計 {line_n['行数の合計']}"
        ),
        "回": out_runs,
        "別枠の回": boxed_runs,
        "別枠の印": boxed_marks,
        "持たせていないもの": NOT_HELD,
    }
    out["指紋"] = _fingerprint(out)
    return out


def _mark_view(out: dict, skip: str | None = None) -> dict:
    """回 × 印の(在る・無い / 行番号 / 後ろの文字列)だけを取り出す。"""
    return {
        (r["回"], p["印"]): (p["在る・無い"], tuple(p["行番号"]), tuple(p["後ろの文字列"]))
        for r in out["回"] for p in r["印"] if p["印"] != skip
    }


def verify(runs: list[dict], marks: list[dict], stages: list[dict], hides: list[dict]) -> dict:
    a = check(runs, marks, stages, hides)
    if not a["ok"]:
        return {"ok": False, "理由コード": a["理由コード"], "理由": a["理由"]}
    b = check(runs, marks, stages, hides)
    c = check(runs, marks[::-1], stages[::-1], hides[::-1])
    d = check(runs[::-1], marks, stages, hides)
    by_a = {r["回"]: r for r in a["回"]}
    by_d = {r["回"]: r for r in d["回"]}
    n_class, n_box = sum(a["区分"].values()), sum(a["別枠"]["回"].values())
    ln = a["行の内訳"]
    sums_ok = (
        n_class + n_box == len(runs)
        and ln["印に当たった行"] + ln["伏せた行"] + ln["空の行"] + ln["どの印にも当たらなかった行"] == ln["行数の合計"]
        and all(
            r["印に当たった行の件数"] + r["伏せた行の件数"] + r["空の行の件数"] + r["どの印にも当たらなかった行の件数"] == r["行数"]
            for r in a["回"]
        )
    )
    used_ids = list(a["印ごとの在る回数"])
    drop_same = 0
    for mid in used_ids:
        e = check(runs, [m for m in marks if m["mark_id"] != mid], stages, hides)
        if e["ok"] and _mark_view(e) == _mark_view(a, skip=mid):
            drop_same += 1
    hide_texts = {h["text"] for h in hides}
    tails = [t for r in a["回"] for p in r["印"] for t in p["後ろの文字列"]]
    leak = sum(1 for t in tails for h in hide_texts if h in t)
    n_hidden = sum(
        1 for r in runs if r["run_id"] in by_a and r["error"] != ""
        for line in split_lines(r["error"]) if any(h in line for h in hide_texts)
    )
    checks = {
        "① 二度走らせて指紋が同じ": a["指紋"] == b["指紋"],
        "② 登録表 3 つの行順を逆にしても指紋が同じで、回の台帳を逆にしても回ごとの結果が同じ": (
            a["指紋"] == c["指紋"] and by_a == by_d and a["区分"] == d["区分"]
        ),
        "③ 区分と別枠の合計が回の台帳の行数に戻り、行の内訳の合計が行数に戻る": sums_ok,
        "④ 印を 1 つ抜いても、残りの印の在る・無い・行番号・後ろの文字列は変わらない": drop_same == len(used_ids),
        "⑤ 後ろの文字列のどれにも伏せる字が無く、伏せた行の件数が数え直しと合う": leak == 0 and n_hidden == ln["伏せた行"],
    }
    return {
        "ok": all(checks.values()), "検査": checks, "指紋": a["指紋"],
        "④ 抜いて確かめた印の数": f"{drop_same}/{len(used_ids)}", "⑤ 伏せた行の件数": ln["伏せた行"],
    }


def as_text(out: dict) -> str:
    """回 × 印を 1 行ずつの文字に並べる(回の台帳の順 → 印の並び順)。"""
    rows = []
    for r in out["回"]:
        rows.append(f"{r['回']}  状態 {r['状態']}  {r['区分']}  行数 {r['行数']}  伏せた行 {r['伏せた行の件数']}  "
                    f"当たらなかった行 {r['どの印にも当たらなかった行の件数']}  段 {' / '.join(r['印が在った段']) or 'なし'}")
        for p in r["印"]:
            if p["行番号"]:
                nums = ",".join(str(n) for n in p["行番号"])
                tails = " | ".join(json.dumps(t, ensure_ascii=False) for t in p["後ろの文字列"])
                rows.append(f"    {p['印']}  {p['種類']}  在る  {nums} 行目  後ろ {tails}")
            else:
                rows.append(f"    {p['印']}  {p['種類']}  無い")
    return "\n".join(rows)


TEMPLATES = {
    "回.csv": "run_id,status,error,source\nR1,failed,\"load done: 3\nHALT\",実行の記録 L1\nR2,ok,,実行の記録 L2\n",
    "印.csv": ("mark_id,text,stage,order,kind,source\n"
               "K1,load done:,S1,1,通過の印,私の登録\nK9,HALT,S1,9,止まった印,私の登録\n"),
    "段.csv": "stage,name,source\nS1,取込,私の登録\n",
    "伏せる行.csv": "text,source\n/home/,私の登録\n",
}


def init(dirpath: str | Path) -> list[str]:
    d = Path(dirpath)
    d.mkdir(parents=True, exist_ok=True)
    made = []
    for name, body in TEMPLATES.items():
        p = d / name
        if p.exists():
            continue
        with p.open("w", encoding="utf-8", newline="") as f:
            f.write(body)
        made.append(name)
    return made


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="halt_depth")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_init = sub.add_parser("init")
    p_init.add_argument("dir")
    for name in ("check", "verify"):
        p = sub.add_parser(name)
        p.add_argument("runs")
        p.add_argument("marks")
        p.add_argument("stages")
        p.add_argument("hides")
        p.add_argument("--label", default=None, help="回の台帳が .jsonl のとき、出典に書く名前")
        if name == "check":
            p.add_argument("--text", action="store_true", help="回 × 印を 1 行ずつの文字で出す")
    a = ap.parse_args(argv)
    if a.cmd == "init":
        print(json.dumps({"作ったファイル": init(a.dir)}, ensure_ascii=False))
        return 0
    try:
        runs = read_runs(a.runs, a.label)
        marks = read_table(a.marks, "marks")
        stages = read_table(a.stages, "stages")
        hides = read_table(a.hides, "hides")
    except TableError as e:
        print(json.dumps({"ok": False, "読めない": str(e)}, ensure_ascii=False))
        return 2
    if a.cmd == "verify":
        out = verify(runs, marks, stages, hides)
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0 if out["ok"] else 3
    out = check(runs, marks, stages, hides)
    if out["ok"] and a.text:
        print(as_text(out))
    else:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if out["ok"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
