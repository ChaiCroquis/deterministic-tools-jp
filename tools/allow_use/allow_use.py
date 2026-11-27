"""allow_use — 許した語の一覧と、式の束に実際に出てくる語を、1 語 1 行で並べる。

入力は 4 表(CSV、UTF-8)。どの行にも出典の欄が要る。
  ① 許可の台帳      word, kind(名前 / 構文の種類), origin(一覧の出どころ id), source
  ② 式の台帳        expr_id, bundle(束の id), expr(式の文字列 verbatim), source
  ③ 数え方の登録    mode(書かれた字のまま / 書き換えの後), main_bundle(主の束の id), pattern, repl, source  … 1 行だけ
  ④ 別の在り所      word, note(在り所の記載 verbatim), source  … 0 行でもよい

式の読み方: ast.parse(mode="eval") で木にし、構文の種類は節の型の名前、名前は呼び出しの先の名前だけを拾う
(変数の名前は拾わない)。式は評価しない。

区分は 4 値: (A) 主の束に出てくる / (B) 主の束には出ず他の束にだけ出てくる / (C) どの束にも出てこない /
(D) 式には出てくるが許可の台帳に無い(線の外)。

持たせていないもの: 式を評価する経路 / 語を削る・足す候補 / 危険かどうか / コードや JSON を自分で開いて
一覧や式を抜く経路 / 書き換えの規則そのもの / token の数 / 通信。標準ライブラリのみ。
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import re
import sys
import warnings
from pathlib import Path

KIND_NAME = "名前"
KIND_NODE = "構文の種類"
KINDS = (KIND_NAME, KIND_NODE)
MODE_RAW = "書かれた字のまま"
MODE_REWRITTEN = "書き換えの後"
MODES = (MODE_RAW, MODE_REWRITTEN)

A = "(A) 主の束に出てくる"
B = "(B) 主の束には出ず他の束にだけ出てくる"
C = "(C) どの束にも出てこない"
D = "(D) 式には出てくるが許可の台帳に無い"
CLASSES = (A, B, C, D)

X_UNREADABLE = "式として読めない"
X_NO_SOURCE = "出典が空"
X_BAD_KIND = "種別が 2 つの値以外"
X_BAD_MODE = "数え方が 2 つの値以外"
X_DUP = "同じ (語, 種別, 出どころ) が 2 行"
X_NO_MAIN = "主の束の id が式の台帳に無い"
SIDE = (X_UNREADABLE, X_NO_SOURCE, X_BAD_KIND, X_BAD_MODE, X_DUP, X_NO_MAIN)

MARK_ONE_SIDED = "一覧の出どころの片方にしか無い"
MARK_ELSEWHERE = "(C) の語に別の在り所の登録が在る"

COLUMNS = {
    "allow": ("word", "kind", "origin", "source"),
    "exprs": ("expr_id", "bundle", "expr", "source"),
    "counting": ("mode", "main_bundle", "pattern", "repl", "source"),
    "elsewhere": ("word", "note", "source"),
}

NOT_HELD = (
    "式を評価する経路(式は木にして語を拾うだけで、値を求めない)",
    "語を一覧から削る・足す候補を返す経路",
    "語や式が危険かどうかを返す経路",
    "コードのファイルを自分で開いて一覧を抜く経路",
    "JSON を自分で探して式を抜く経路",
    "書き換えの規則そのもの(正規表現と置き換えの字は登録表で受ける)",
    "(C) の語が要るか要らないかを返す経路",
    "token を数える経路",
    "通信の経路",
)


class TableError(Exception):
    """表として読めない(列が足りない、数え方の登録が 1 行でない、書き換えの規則が読めない)。"""


def read_table(path: str | Path, kind: str) -> list[dict[str, str]]:
    """CSV を読む。列が足りなければ TableError。値は切り詰めも空白の除去もしない。"""
    need = COLUMNS[kind]
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        got = reader.fieldnames or []
        missing = [c for c in need if c not in got]
        if missing:
            raise TableError(f"{Path(path).name}: 列が足りない {missing}")
        rows = []
        for r in reader:
            if any(r.get(c) is None for c in need):
                raise TableError(f"{Path(path).name}: 列の数が足りない行が在る")
            rows.append({c: r[c] for c in need})
    return rows


def words_of(text: str) -> frozenset[tuple[str, str]] | None:
    """式 1 本を木にして (種別, 語) の集合を返す。読めなければ None。式は評価しない。"""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse(text, mode="eval")
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return None
    found = set()
    for node in ast.walk(tree):
        found.add((KIND_NODE, type(node).__name__))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            found.add((KIND_NAME, node.func.id))
    return frozenset(found)


def _check_counting(counting: list[dict[str, str]]) -> dict[str, str]:
    if len(counting) != 1:
        raise TableError(f"数え方の登録は 1 行だけ受け取る(いま {len(counting)} 行)")
    reg = counting[0]
    if reg["mode"] == MODE_REWRITTEN:
        if reg["pattern"] == "":
            raise TableError("書き換えの後で数えるのに、書き換えの規則(pattern)が空")
        try:
            re.sub(reg["pattern"], reg["repl"], "")
        except (re.error, IndexError) as e:
            raise TableError(f"書き換えの規則が読めない: {e}") from None
    return reg


def judge(allow: list[dict[str, str]], exprs: list[dict[str, str]], counting: list[dict[str, str]],
          elsewhere: list[dict[str, str]], _extra: tuple[tuple[str, frozenset], ...] = ()) -> dict:
    """4 表から語ごとの行・区分・別枠を作る。入力は書き換えない。

    _extra は verify ④ だけが使う(木にした後の語の集合を、式 1 本ぶんとして束に足す)。
    """
    reg = _check_counting(counting)
    mode, main = reg["mode"], reg["main_bundle"]
    bundles = sorted({e["bundle"] for e in exprs} | {b for b, _ in _extra})

    # --- 全体に掛かる別枠(どの語も数えない) ---
    overall = None
    if mode not in MODES:
        overall = X_BAD_MODE
    elif main not in bundles:
        overall = X_NO_MAIN
    elif reg["source"] == "":
        overall = X_NO_SOURCE

    # --- 許可の台帳: (語, 種別) ごとにまとめる ---
    types: dict[tuple[str, str], list[dict[str, str]]] = {}
    for r in allow:
        types.setdefault((r["word"], r["kind"]), []).append(r)

    def side_of(key: tuple[str, str], rows: list[dict[str, str]]) -> str | None:
        if overall:
            return overall
        if key[1] not in KINDS:
            return X_BAD_KIND
        origins = [r["origin"] for r in rows]
        if len(origins) != len(set(origins)):
            return X_DUP
        if any(r["source"] == "" for r in rows):
            return X_NO_SOURCE
        return None

    sides = {key: side_of(key, rows) for key, rows in types.items()}
    good = {key for key, s in sides.items() if s is None}
    ledger_words = {key[0] for key in types}

    # --- 式の台帳: 木にして語を拾う ---
    per_bundle: dict[str, list[frozenset]] = {b: [] for b in bundles}
    unreadable, expr_no_source = [], []
    if not overall:
        for e in exprs:
            if e["source"] == "":
                expr_no_source.append({"束": e["bundle"], "式 id": e["expr_id"]})
                continue
            text = e["expr"]
            if mode == MODE_REWRITTEN:
                text = re.sub(reg["pattern"], reg["repl"], text)
            found = words_of(text)
            if found is None:
                unreadable.append({"束": e["bundle"], "式 id": e["expr_id"], "式": e["expr"], "出典": e["source"]})
            else:
                per_bundle[e["bundle"]].append(found)
        for b, found in _extra:
            per_bundle[b].append(found)
    unreadable.sort(key=lambda u: (u["束"], u["式 id"], u["式"]))
    expr_no_source.sort(key=lambda u: (u["束"], u["式 id"]))

    def counts(key: tuple[str, str]) -> dict[str, int]:
        kind, word = key[1], key[0]
        return {b: sum(1 for found in per_bundle[b] if (kind, word) in found) for b in bundles}

    # --- 別の在り所 ---
    notes: dict[str, list[dict[str, str]]] = {}
    else_no_source = else_unknown = 0
    for r in elsewhere:
        if r["source"] == "":
            else_no_source += 1
        elif r["word"] not in ledger_words:
            else_unknown += 1
        else:
            notes.setdefault(r["word"], []).append({"記載": r["note"], "出典": r["source"]})
    for v in notes.values():
        v.sort(key=lambda n: (n["出典"], n["記載"]))

    # --- 語ごとの行 ---
    origins_of_kind: dict[str, set[str]] = {}
    for key in good:
        origins_of_kind.setdefault(key[1], set()).update(r["origin"] for r in types[key])

    rows_out, side_rows = [], []
    for key in sorted(types, key=lambda k: (KINDS.index(k[1]) if k[1] in KINDS else len(KINDS), k[1], k[0])):
        word, kind = key
        if sides[key]:
            side_rows.append({"種別": kind, "語": word, "別枠": sides[key]})
            continue
        n = counts(key)
        cls = A if n[main] > 0 else (B if any(n.values()) else C)
        has = sorted({r["origin"] for r in types[key]})
        lacks = sorted(origins_of_kind[kind] - set(has))
        marks = []
        if lacks:
            marks.append(MARK_ONE_SIDED)
        if cls == C and notes.get(word):
            marks.append(MARK_ELSEWHERE)
        rows_out.append({
            "種別": kind, "語": word, "区分": cls, "束ごとの式の本数": n,
            "一覧の出どころ": has, "載っていない出どころ": lacks, "印": marks,
            "別の在り所": notes.get(word, []),
            "出典": sorted({r["source"] for r in types[key]}),
        })

    # --- 線の外 (D) ---
    seen: set[tuple[str, str]] = set()
    for b in bundles:
        for found in per_bundle[b]:
            seen |= found
    outside = []
    for kind, word in sorted(seen, key=lambda t: (KINDS.index(t[0]), t[1])):
        if (word, kind) in types or word in {k[0] for k, s in sides.items() if s}:
            continue
        outside.append({"種別": kind, "語": word, "区分": D,
                        "束ごとの式の本数": counts((word, kind))})

    by_class = {c: sum(1 for r in rows_out if r["区分"] == c) for c in (A, B, C)}
    by_class[D] = len(outside)
    by_kind = {k: {c: sum(1 for r in rows_out + outside if r["種別"] == k and r["区分"] == c) for c in CLASSES}
               for k in KINDS}
    side_words = {x: sum(1 for s in side_rows if s["別枠"] == x) for x in SIDE}
    n_types, n_side = len(types), len(side_rows)
    total = by_class[A] + by_class[B] + by_class[C]

    judged = {
        "数え方": mode, "主の束": main,
        "束ごとの読めた式の本数": {b: len(per_bundle[b]) for b in bundles},
        "語ごとの行": rows_out, "線の外の語": outside, "別枠に落ちた語": side_rows,
        "区分ごとの語数": by_class, "種別ごとの区分の語数": by_kind,
        "別枠": {
            X_UNREADABLE: {"式": len(unreadable)},
            X_NO_SOURCE: {"語": side_words[X_NO_SOURCE], "式": len(expr_no_source), "在り所の行": else_no_source},
            X_BAD_KIND: {"語": side_words[X_BAD_KIND]},
            X_BAD_MODE: {"語": side_words[X_BAD_MODE]},
            X_DUP: {"語": side_words[X_DUP]},
            X_NO_MAIN: {"語": side_words[X_NO_MAIN]},
        },
        "読めなかった式": unreadable, "出典が空の式": expr_no_source,
        "印の件数": {m: sum(1 for r in rows_out if m in r["印"]) for m in (MARK_ONE_SIDED, MARK_ELSEWHERE)},
        "台帳に無い語を指す在り所の行数": else_unknown,
    }
    blob = json.dumps(judged, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "ok": True,
        "許可の台帳の行数": len(allow), "許可の台帳の語の種類数": n_types,
        "式の台帳の行数": len(exprs),
        "書き換えの規則を使ったか": mode == MODE_REWRITTEN,
        **judged,
        "語数の検算": f"区分 (A)+(B)+(C) {total} + 別枠に落ちた語 {n_side} = {total + n_side} / 語の種類数 {n_types}",
        "検算が合うか": total + n_side == n_types,
        "判定部分の sha256": hashlib.sha256(blob.encode("utf-8")).hexdigest(),
        "持たせていないもの": list(NOT_HELD),
    }


def own_forbidden_calls(path: str | Path | None = None) -> int:
    """このファイルのソースを木にして、eval / exec / compile の呼び出しを数える(名前でも属性でも)。"""
    tree = ast.parse(Path(path or __file__).read_text(encoding="utf-8"))
    banned = {"eval", "exec", "compile"}
    n = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if (isinstance(f, ast.Name) and f.id in banned) or (isinstance(f, ast.Attribute) and f.attr in banned):
                n += 1
    return n


def verify(allow: list[dict[str, str]], exprs: list[dict[str, str]], counting: list[dict[str, str]],
           elsewhere: list[dict[str, str]]) -> dict:
    """手続きが決定論かを 5 つ見る。"""
    r1 = judge(allow, exprs, counting, elsewhere)
    r2 = judge(allow, exprs, counting, elsewhere)
    r3 = judge(allow, list(reversed(exprs)), counting, elsewhere)
    main = r1["主の束"]
    base = {(r["種別"], r["語"]): r for r in r1["語ごとの行"]}
    targets = [k for k, r in base.items() if r["区分"] == C]
    moved_alone = 0
    for kind, word in targets:
        r = judge(allow, exprs, counting, elsewhere, _extra=((main, frozenset({(kind, word)})),))
        after = {(x["種別"], x["語"]): x for x in r["語ごとの行"]}
        others_same = all(after[k] == v for k, v in base.items() if k != (kind, word))
        me = after[(kind, word)]
        if (others_same and me["区分"] == A and me["束ごとの式の本数"][main] == 1
                and r["線の外の語"] == r1["線の外の語"] and r["別枠に落ちた語"] == r1["別枠に落ちた語"]):
            moved_alone += 1
    forbidden = own_forbidden_calls()
    checks = {
        "① 二度走らせて判定部分の sha256 が同じ": r1["判定部分の sha256"] == r2["判定部分の sha256"],
        "② 式の台帳の行順を逆にしても同じ": r1["判定部分の sha256"] == r3["判定部分の sha256"],
        "③ 区分 (A)+(B)+(C) + 別枠に落ちた語 = 語の種類数": r1["検算が合うか"],
        "④ (C) の語 1 つだけを持つ式 1 本ぶんを主の束に足すと、その語だけが (A) へ動く": moved_alone == len(targets),
        "⑤ この道具のソースに eval / exec / compile の呼び出しが無い": forbidden == 0,
    }
    return {
        "ok": all(checks.values()), "verify": checks,
        "④ の内訳": f"{moved_alone}/{len(targets)}",
        "⑤ の件数": forbidden,
        "判定部分の sha256": r1["判定部分の sha256"],
    }


def lines(result: dict) -> list[str]:
    """語ごとの行を、並んだ順のまま 1 語 1 行の文字列にする。"""
    bundles = list(result["束ごとの読めた式の本数"])
    out = []
    for r in result["語ごとの行"] + result["線の外の語"]:
        n = "  ".join(f"{b} {r['束ごとの式の本数'][b]}" for b in bundles)
        tail = ""
        if r.get("印"):
            tail += "  印: " + " / ".join(r["印"])
        if r.get("別の在り所"):
            tail += "  別の在り所: " + " / ".join(x["出典"] for x in r["別の在り所"])
        out.append(f"{r['種別']}  {r['語']}  {r['区分'][:3]}  {n}{tail}")
    for s in result["別枠に落ちた語"]:
        out.append(f"{s['種別']}  {s['語']}  別枠: {s['別枠']}")
    return out


TEMPLATES = {
    "allow.csv": [list(COLUMNS["allow"])],
    "exprs.csv": [list(COLUMNS["exprs"])],
    "counting.csv": [list(COLUMNS["counting"]), [MODE_RAW, "", "", "", ""]],
    "elsewhere.csv": [list(COLUMNS["elsewhere"])],
}


def init(folder: str | Path) -> list[str]:
    """4 表のひな型を書く。既に在るファイルは上書きしない。"""
    d = Path(folder)
    d.mkdir(parents=True, exist_ok=True)
    made = []
    for name, rows in TEMPLATES.items():
        p = d / name
        if p.exists():
            continue
        with open(p, "w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows(rows)
        made.append(name)
    return made


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="許した語の一覧と、式に出てくる語を 1 語 1 行で並べる")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init", help="4 表のひな型を書く")
    p.add_argument("folder")
    for name in ("check", "verify"):
        p = sub.add_parser(name)
        p.add_argument("allow")
        p.add_argument("exprs")
        p.add_argument("counting")
        p.add_argument("elsewhere")
        if name == "check":
            p.add_argument("--lines", action="store_true", help="語ごとの行を 1 語 1 行で出す")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if a.cmd == "init":
        print(json.dumps({"ok": True, "書いたひな型": init(a.folder)}, ensure_ascii=False))
        return 0
    try:
        tables = [read_table(getattr(a, k), k) for k in ("allow", "exprs", "counting", "elsewhere")]
        result = judge(*tables) if a.cmd == "check" else verify(*tables)
    except (TableError, OSError, UnicodeDecodeError, csv.Error) as e:
        print(json.dumps({"ok": False, "読めない": str(e)}, ensure_ascii=False))
        return 2
    if a.cmd == "check" and a.lines:
        print("\n".join(lines(result)))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
