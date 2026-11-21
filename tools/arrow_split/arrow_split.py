"""arrow_split — 改定の記載に在る矢印を、人が登録した意味の記号で分け、前後の値の行だけを前と後に割って並べる。

入力は 4 表(どの行にも出典の欄 source が要る):
  記載の台帳   entry_id, rule, field, text, symbol, date_text, source
  記号の登録表 symbol, split, source          (split = 「割る」か空)
  収録の台帳   cov_id, rule, state, source    (state = 「収録」か「未収録」)
  対の登録表   entry_id, cov_id, side, source (side = 「前」「後」か空)

割るのは登録表で「割る」の印が付いた記号の行だけ。矢印の字 1 つで左右に切った文字列をそのまま返す。
矢印の意味を字面から当てる経路・前後を数に直す経路・単位や日を補う経路・名前の似かたで収録と結び付ける経路・
前後の値が正しいかや動いた方向の良し悪しを返す経路・通信・入力を書き換える経路は持たない。
標準ライブラリのみ(csv / json / hashlib / argparse)。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ARROW = "→"
SPLIT_MARK = "割る"
STATES = ("収録", "未収録")
SIDES = ("前", "後", "")

A = "(A) 前と後の両方に収録の記載が在る"
B = "(B) 収録の記載が在るが前と後の両方にはそろわない"
C = "(C) 未収録の記載が在る"
D = "(D) 読んだ範囲に記載なし"
CLASSES = (A, B, C, D)
NOSPLIT = "割らない記号"

X_DUP = "同じ記載 id が 2 回"
X_SRC = "出典が空"
X_SYM = "登録表に無い記号"
X_NOARROW = "割る記号なのに矢印の字が無い"
X_MANY = "矢印の字が 2 つ以上"
X_PAIR = "対の登録表が収録の台帳に無い行を指す"
EXTRAS = (X_DUP, X_SRC, X_SYM, X_NOARROW, X_MANY, X_PAIR)

F_UNIT = "単位の字が片側だけ"
F_ETC = "後ろに「等」が付く"
F_NOSIDE = "収録の記載に前後の別が書かれていない"
F_MIXED = "収録と未収録の記載が両方在る"

STOP_SYM_SRC = "記号の登録表に出典が空の行が在る"
STOP_SYM_DUP = "記号の登録表に同じ記号が 2 回在る"
STOP_COV = "収録の台帳に 出典が空・状態が 2 語以外・id の重複 のどれかが在る"
STOP_PAIR = "対の登録表に 出典が空・側が 3 値以外 のどれかが在る"
STOPS = (STOP_SYM_SRC, STOP_SYM_DUP, STOP_COV, STOP_PAIR)

COLUMNS = {
    "entries": ("entry_id", "rule", "field", "text", "symbol", "date_text", "source"),
    "symbols": ("symbol", "split", "source"),
    "coverage": ("cov_id", "rule", "state", "source"),
    "pairs": ("entry_id", "cov_id", "side", "source"),
}

NOT_HELD = (
    "意味を当てない: 矢印の意味は人が登録した記号だけで決まり、記載の字面からは決めない",
    "数に直さない: 前と後は切った文字列のまま返し、差も倍率も出さない",
    "単位を補わない: 片側にしか無い単位の字は印を付けるだけで、もう片側へ写さない",
    "日を補わない: 日付の記載は台帳に書かれた文字列をそのまま写す",
    "名前で結び付けない: 収録の記載との対応は対の登録表に書かれた行だけを使う",
    "正しさを返さない: 前後の値が正しいかを返す欄が無い",
    "方向を評価しない: 引上げか引下げか、良いか悪いかを返す欄が無い",
    "値を引かない: 収録の台帳は記載の語を写すだけで、表そのものは読まない",
    "通信しない: 読むのは渡された 4 表と、渡されたときの文書の写しだけ",
    "書き換えない: 入力の 4 表は読むだけで、同じ場所へ書き戻さない",
)


def read_table(path: str | Path, kind: str) -> list[dict[str, str]]:
    """CSV(UTF-8)を読む。列が足りない・行が無い表は ValueError で止める。"""
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        head = reader.fieldnames or []
        missing = [c for c in COLUMNS[kind] if c not in head]
        if missing:
            raise ValueError(f"{kind}: 列が足りない {missing}")
        rows = [{c: (r.get(c) or "").strip() for c in COLUMNS[kind]} for r in reader]
    if not rows and kind != "pairs":
        raise ValueError(f"{kind}: 行が無い")
    return rows


def _digit_suffix(s: str) -> str | None:
    """最後の半角数字より後ろの文字列。数字が無ければ None。"""
    last = -1
    for i, ch in enumerate(s):
        if ch in "0123456789":
            last = i
    return None if last < 0 else s[last + 1:].strip()


def text_flags(before: str, after: str) -> list[str]:
    flags = []
    tail = after
    if after.endswith("等"):
        flags.append(F_ETC)
        tail = after[:-1].strip()
    sb, sa = _digit_suffix(before), _digit_suffix(tail)
    if sb is not None and sa is not None and (sb == "") != (sa == ""):
        flags.append(F_UNIT)
    return sorted(flags)


def _stop(reason: str) -> dict:
    return {"ok": False, "止まった理由": reason, "記載": [], "持たせていないもの": list(NOT_HELD)}


def check(entries: list[dict], symbols: list[dict], coverage: list[dict], pairs: list[dict]) -> dict:
    """4 表から、記載ごとの意味の記号・前・後・日付の記載・区分を並べる。入力は書き換えない。"""
    if any(not s["source"] for s in symbols):
        return _stop(STOP_SYM_SRC)
    names = [s["symbol"] for s in symbols]
    if len(set(names)) != len(names):
        return _stop(STOP_SYM_DUP)
    cov_ids = [c["cov_id"] for c in coverage]
    if (any(not c["source"] or c["state"] not in STATES for c in coverage)
            or len(set(cov_ids)) != len(cov_ids)):
        return _stop(STOP_COV)
    if any(not p["source"] or p["side"] not in SIDES for p in pairs):
        return _stop(STOP_PAIR)

    split_of = {s["symbol"]: s["split"] == SPLIT_MARK for s in symbols}
    cov_of = {c["cov_id"]: c for c in coverage}
    id_count: dict[str, int] = {}
    for e in entries:
        id_count[e["entry_id"]] = id_count.get(e["entry_id"], 0) + 1
    pairs_of: dict[str, list[dict]] = {}
    orphan_pairs = 0
    for p in pairs:
        if p["entry_id"] not in id_count:
            orphan_pairs += 1
        else:
            pairs_of.setdefault(p["entry_id"], []).append(p)

    rows = []
    for e in entries:
        row = {"記載 id": e["entry_id"], "rule": e["rule"], "欄": e["field"], "記載": e["text"],
               "意味の記号": e["symbol"], "前": "", "後": "", "日付の記載": e["date_text"],
               "区分": "", "印": [], "収録の記載": [], "出典": e["source"]}
        mine = pairs_of.get(e["entry_id"], [])
        n_arrow = e["text"].count(ARROW)
        if id_count[e["entry_id"]] > 1:
            row["区分"] = "別枠: " + X_DUP
        elif not e["source"]:
            row["区分"] = "別枠: " + X_SRC
        elif e["symbol"] not in split_of:
            row["区分"] = "別枠: " + X_SYM
        elif split_of[e["symbol"]] and n_arrow == 0:
            row["区分"] = "別枠: " + X_NOARROW
        elif split_of[e["symbol"]] and n_arrow > 1:
            row["区分"] = "別枠: " + X_MANY
        elif any(p["cov_id"] not in cov_of for p in mine):
            row["区分"] = "別枠: " + X_PAIR
        else:
            covs = sorted(
                ({"収録の id": p["cov_id"], "状態": cov_of[p["cov_id"]]["state"], "側": p["side"],
                  "出典": cov_of[p["cov_id"]]["source"]} for p in mine),
                key=lambda c: (c["収録の id"], c["側"]))
            row["収録の記載"] = covs
            if not split_of[e["symbol"]]:
                row["区分"] = NOSPLIT
            else:
                left, right = e["text"].split(ARROW)
                row["前"], row["後"] = left.strip(), right.strip()
                flags = text_flags(row["前"], row["後"])
                held = [c for c in covs if c["状態"] == "収録"]
                if any(c["状態"] == "未収録" for c in covs):
                    row["区分"] = C
                    if held:
                        flags.append(F_MIXED)
                elif any(c["側"] == "前" for c in held) and any(c["側"] == "後" for c in held):
                    row["区分"] = A
                elif held:
                    row["区分"] = B
                    if any(c["側"] == "" for c in held):
                        flags.append(F_NOSIDE)
                else:
                    row["区分"] = D
                row["印"] = sorted(flags)
        rows.append(row)
    rows.sort(key=lambda r: (r["記載 id"], json.dumps(r, ensure_ascii=False, sort_keys=True)))

    four = {k: sum(1 for r in rows if r["区分"] == k) for k in CLASSES}
    extra = {k: sum(1 for r in rows if r["区分"] == "別枠: " + k) for k in EXTRAS}
    nosplit = sum(1 for r in rows if r["区分"] == NOSPLIT)
    by_symbol: dict[str, int] = {}
    for r in rows:
        if not r["区分"].startswith("別枠"):
            by_symbol[r["意味の記号"]] = by_symbol.get(r["意味の記号"], 0) + 1
    used = {p["cov_id"] for p in pairs}
    judged = {
        "記載の台帳の行数": len(entries),
        "4 値": four,
        "割らない記号の件数": nosplit,
        "別枠": extra,
        "意味の記号ごとの件数": dict(sorted(by_symbol.items())),
        "台帳に無い記載 id を指す対の行数": orphan_pairs,
        "対に使われていない収録の台帳の行数": sum(1 for c in coverage if c["cov_id"] not in used),
        "記載": rows,
    }
    total = sum(four.values()) + nosplit + sum(extra.values())
    out = {"ok": True, **judged}
    out["件数の合計の検算"] = (f"4 値 {sum(four.values())} + 割らない記号 {nosplit} + 別枠 {sum(extra.values())}"
                       f" = {total} / 記載の台帳の行数 {len(entries)}")
    out["検算が合う"] = total == len(entries)
    out["sha256"] = digest(judged)
    out["持たせていないもの"] = list(NOT_HELD)
    return out


def digest(judged: dict) -> str:
    blob = json.dumps(judged, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def scan(doc_lines: list[str], label: str, entries: list[dict]) -> dict:
    """文書の行の写しから、矢印の字を含む行を literal 一致で数え、台帳の出典(`<label> L<行番号>`)と突き合わせる。"""
    cited: dict[int, list[dict]] = {}
    prefix = label + " L"
    for e in entries:
        if e["source"].startswith(prefix) and e["source"][len(prefix):].isdigit():
            cited.setdefault(int(e["source"][len(prefix):]), []).append(e)
    arrow_lines = [i for i, line in enumerate(doc_lines, 1) if ARROW in line]
    missing = [i for i in arrow_lines if i not in cited]
    unmatched = sorted(e["entry_id"] for n, es in cited.items() for e in es
                       if n > len(doc_lines) or e["text"] not in doc_lines[n - 1])
    return {
        "文書の行数": len(doc_lines),
        "矢印の字を含む行": len(arrow_lines),
        "うち台帳に在る行": len(arrow_lines) - len(missing),
        "矢印の字を含むのに台帳に無い行": {"件数": len(missing), "行番号": missing},
        "記載の文字列が出典の行に無い記載 id": unmatched,
    }


def _rows_by_id(out: dict) -> dict[str, dict]:
    return {r["記載 id"]: r for r in out["記載"]}


def verify(entries: list[dict], symbols: list[dict], coverage: list[dict], pairs: list[dict]) -> dict:
    """手続きが決定論かを 5 つ見る。"""
    base = check(entries, symbols, coverage, pairs)
    if not base["ok"]:
        return {"ok": False, "止まった理由": base["止まった理由"]}
    res: dict = {}
    res["1 二度走りの sha256 が同一"] = check(entries, symbols, coverage, pairs)["sha256"] == base["sha256"]
    rev = check(entries[::-1], symbols[::-1], coverage[::-1], pairs[::-1])
    res["2 4 表の行順を逆にしても出力が同一"] = rev["sha256"] == base["sha256"]
    res["3 件数の合計が行数に戻る"] = base["検算が合う"]

    base_rows = _rows_by_id(base)
    four_ids = sorted(i for i, r in base_rows.items() if r["区分"] in CLASSES)
    other = sorted(s["symbol"] for s in symbols if s["split"] != SPLIT_MARK)
    n4 = ok4 = 0
    if other:
        for eid in four_ids:
            changed = [{**e, "symbol": other[0]} if e["entry_id"] == eid else e for e in entries]
            got = _rows_by_id(check(changed, symbols, coverage, pairs))
            n4 += 1
            same = all(got[i] == base_rows[i] for i in base_rows if i != eid)
            ok4 += int(got[eid]["区分"] == NOSPLIT and got[eid]["前"] == "" and same)
    res["4 記号を割らない記号に替えるとその 1 行だけが割られなくなる"] = {"確かめた件数": n4, "合った件数": ok4}

    n5 = ok5 = 0
    for eid in four_ids:
        mine = [p for p in pairs if p["entry_id"] == eid]
        if len(mine) != 1:
            continue
        got = _rows_by_id(check(entries, symbols, coverage, [p for p in pairs if p is not mine[0]]))
        n5 += 1
        same = all(got[i] == base_rows[i] for i in base_rows if i != eid)
        ok5 += int(got[eid]["区分"] == D and same)
    res["5 対を 1 行抜くとその記載だけが (D) へ動く"] = {"確かめた件数": n5, "合った件数": ok5}
    res["ok"] = (res["1 二度走りの sha256 が同一"] and res["2 4 表の行順を逆にしても出力が同一"]
                 and res["3 件数の合計が行数に戻る"] and n4 == ok4 and n5 == ok5)
    res["sha256"] = base["sha256"]
    return res


TEMPLATES = {
    "entries.csv": "entry_id,rule,field,text,symbol,date_text,source\n",
    "symbols.csv": ("symbol,split,source\n前後の値,割る,ひな型\n後だけ,,ひな型\n対応,,ひな型\n公表と適用,,ひな型\n"
                    "日付と出来事,,ひな型\n行き先,,ひな型\n版,,ひな型\n"),
    "coverage.csv": "cov_id,rule,state,source\n",
    "pairs.csv": "entry_id,cov_id,side,source\n",
}


def init(dest: str | Path) -> list[str]:
    d = Path(dest)
    d.mkdir(parents=True, exist_ok=True)
    made = []
    for name, body in TEMPLATES.items():
        p = d / name
        if p.exists():
            raise ValueError(f"すでに在る: {p}")
        p.write_text(body, encoding="utf-8", newline="")
        made.append(str(p))
    return made


def _load(args: argparse.Namespace) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    return (read_table(args.entries, "entries"), read_table(args.symbols, "symbols"),
            read_table(args.coverage, "coverage"), read_table(args.pairs, "pairs"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="矢印の意味を登録した記号で分け、前後の値の行だけを前と後に割って並べる")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_init = sub.add_parser("init", help="4 表のひな型を出す")
    p_init.add_argument("dest")
    for name in ("check", "verify"):
        p = sub.add_parser(name)
        for a in ("entries", "symbols", "coverage", "pairs"):
            p.add_argument(a)
    sub.choices["check"].add_argument("--doc", help="文書の行の写し(矢印の字を含む行を数える)")
    sub.choices["check"].add_argument("--label", default="", help="台帳の出典で文書を指す名前(`<名前> L<行番号>`)")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        if args.cmd == "init":
            out: dict = {"ok": True, "作ったファイル": init(args.dest)}
        else:
            tables = _load(args)
            if args.cmd == "verify":
                out = verify(*tables)
            else:
                out = check(*tables)
                if args.doc and out["ok"]:
                    lines = Path(args.doc).read_text(encoding="utf-8-sig").split("\n")
                    if lines and lines[-1] == "":
                        lines.pop()
                    out["文書の行の写し"] = scan(lines, args.label, tables[0])
    except (ValueError, OSError) as exc:
        print(json.dumps({"ok": False, "読めない": str(exc)}, ensure_ascii=False, indent=1))
        return 2
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if out["ok"] else 3


if __name__ == "__main__":
    sys.exit(main())
