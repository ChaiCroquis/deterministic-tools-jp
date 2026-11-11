"""source_shift — rule ごとの主の出どころが替わった瞬間を 1 行 1 件の一覧にする判定器。

読むのは 5 枚の表(動きの台帳 / 出どころの登録表 / 役の記号の登録表 / 引き継ぎの突合の台帳 /
いまの由来の台帳)で、出すのは rule ごとの区分 4 値 + 別枠、動きごとの 1 行、歩いた最後の主と
いまの由来の台帳の主が食い違う rule の一覧。

持たせていないもの: 値を比べる経路、実行の台帳の増減の件数を rule に割り振る経路、日付を補う経路、
動いた理由を言い当てる経路、どちらの出どころがよいかの列・順位・点数、一致率の 1 値、時計を読む経路、
入力を書き換える経路。標準ライブラリのみ。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

MOVE_COLS = ("move_id", "seq", "date_text", "rule", "from_source", "to_source",
             "old_role", "actor", "scope", "source")
SOURCE_COLS = ("source_id", "name", "kind", "covers", "source")
ROLE_COLS = ("role", "meaning", "source")
CHECK_COLS = ("check_id", "move_id", "scope", "compared", "matched", "source")
CURRENT_COLS = ("rule", "current_source", "source")
TABLES = (("moves", MOVE_COLS, "move_id"), ("sources", SOURCE_COLS, "source_id"),
          ("roles", ROLE_COLS, "role"), ("checks", CHECK_COLS, "check_id"),
          ("current", CURRENT_COLS, "rule"))

R_SOURCE = "出典が空"
R_UNREGISTERED = "記号か出どころ id が登録表に無い"
R_SEQ = "順の番号が重複か整数でない"
R_CHAIN = "線がつながらない"
R_ROLE = "古い側の役が空"
R_COUNT = "件数が読めない"
REASONS = (R_SOURCE, R_UNREGISTERED, R_SEQ, R_CHAIN, R_ROLE, R_COUNT)

CAT_A = "(A) 主が替わり、古い側の役と引き継ぎの突合が在る"
CAT_B = "(B) 主が替わったが、突合の記載が無い入れ替えが在る"
CAT_C = "(C) 主が替わっていない(入れ替える相手は登録表に在る)"
CAT_D = "(D) 出どころが 1 つだけ(入れ替える相手が登録表に無い)"
CATEGORIES = (CAT_A, CAT_B, CAT_C, CAT_D)
SIDE = "別枠(区分を付けずに止めた)"

NOT_HELD = (
    "値を比べない: 入るのは id・記号・件数・文字列・出典だけで、値の列が無い",
    "実行の台帳の件数を rule に割り振らない: 増えた・減った件数を受け取る引数が無い",
    "日付を補わない: 日付の欄は渡された文字列を写すだけで、空は「日付の記載なし」と出す",
    "理由を言い当てない: 動いた理由の欄も、差の原因の欄も無い",
    "よい側を決めない: 出どころの種別は写すだけで、順位・点数・勧める側の列が無い",
    "一致率を出さない: 比べた件数と一致した件数を並べるだけで、割った値を作らない",
    "時計を読まない: 順は呼ぶ側が渡した整数だけで決まる",
    "入力を書き換えない: verify の写しはメモリの中だけに作る",
)


class ShiftError(Exception):
    """表として読めない(列が無い / id が空か重複)。区分を付ける前に止まる。"""


def read_table(path: str, cols: tuple[str, ...]) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in cols if c not in (reader.fieldnames or [])]
        if missing:
            raise ShiftError(f"列が無い: {path} に {missing}")
        return [{c: (row.get(c) or "").strip() for c in cols} for row in reader]


def load(paths: list[str]) -> dict[str, list[dict[str, str]]]:
    return {name: read_table(p, cols) for (name, cols, _), p in zip(TABLES, paths)}


def to_int(text: str) -> int | None:
    """ASCII の整数だけを読む(符号は先頭の - 1 つまで)。読めなければ None。"""
    body = text[1:] if text.startswith("-") else text
    if body and body.isascii() and body.isdigit():
        return int(text)
    return None


def _structure(t: dict[str, list[dict[str, str]]]) -> None:
    for name, _, key in TABLES:
        seen: set[str] = set()
        for row in t[name]:
            if not row[key]:
                raise ShiftError(f"id が空: {name} の {key}")
            if row[key] in seen:
                raise ShiftError(f"id が重複: {name} の {key} = {row[key]}")
            seen.add(row[key])
    for m in t["moves"]:
        if not m["rule"]:
            raise ShiftError(f"rule が空: moves の {m['move_id']}")


def _seq_key(text: str) -> str:
    n = to_int(text)
    return f"int:{n}" if n is not None else f"raw:{text}"


def judge(t: dict[str, list[dict[str, str]]]) -> dict:
    """5 枚の表から、rule ごとの行・動きごとの行・食い違いの一覧を作る。入力は書き換えない。"""
    _structure(t)
    src = {s["source_id"]: s for s in t["sources"]}
    role = {r["role"]: r for r in t["roles"]}
    cur = {c["rule"]: c for c in t["current"]}
    move_ids = {m["move_id"] for m in t["moves"]}
    covers: dict[str, set[str]] = {}
    for s in t["sources"]:
        for r in s["covers"].split(";"):
            if r.strip():
                covers.setdefault(r.strip(), set()).add(s["source_id"])
    seq_seen: dict[str, int] = {}
    for m in t["moves"]:
        seq_seen[_seq_key(m["seq"])] = seq_seen.get(_seq_key(m["seq"]), 0) + 1
    checks_of: dict[str, list[dict[str, str]]] = {}
    loose = []
    for c in sorted(t["checks"], key=lambda c: c["check_id"]):
        if c["move_id"] in move_ids:
            checks_of.setdefault(c["move_id"], []).append(c)
        else:
            loose.append({"突合": c["check_id"], "動き id": c["move_id"], "出典": c["source"]})

    rule_rows, move_rows, gaps = [], [], []
    for rule in sorted(set(cur) | {m["rule"] for m in t["moves"]}):
        ms = [m for m in t["moves"] if m["rule"] == rule]
        c = cur.get(rule)
        why: set[str] = set()
        used_src = [x for m in ms for x in (m["from_source"], m["to_source"]) if x]
        if c:
            used_src.append(c["current_source"])
        used_role = [m["old_role"] for m in ms if m["old_role"]]
        cs = [x for m in ms for x in checks_of.get(m["move_id"], [])]
        # 出典が空(その rule に触れる行と、参照している登録表の行)
        cited = [m["source"] for m in ms] + [x["source"] for x in cs] + ([c["source"]] if c else [])
        cited += [src[x]["source"] for x in used_src if x in src]
        cited += [role[x]["source"] for x in used_role if x in role]
        if any(not s for s in cited):
            why.add(R_SOURCE)
        if any(x not in src for x in used_src) or any(not m["to_source"] for m in ms) \
                or any(x not in role for x in used_role) or (c and not c["current_source"]):
            why.add(R_UNREGISTERED)
        if any(to_int(m["seq"]) is None or seq_seen[_seq_key(m["seq"])] > 1 for m in ms):
            why.add(R_SEQ)
        else:
            ms.sort(key=lambda m: to_int(m["seq"]))
            if any(b["from_source"] != a["to_source"] for a, b in zip(ms, ms[1:])):
                why.add(R_CHAIN)
        if any(m["from_source"] and not m["old_role"] for m in ms):
            why.add(R_ROLE)
        for x in cs:
            a, b = to_int(x["compared"]), to_int(x["matched"])
            if a is None or b is None or a < 0 or b < 0 or b > a:
                why.add(R_COUNT)
        if why:
            rule_rows.append({"rule": rule, "区分": SIDE,
                              "止まった理由": [r for r in REASONS if r in why],
                              "動きの回数(台帳の行数)": len(ms)})
            continue

        walked = ms[-1]["to_source"] if ms else c["current_source"]
        switches = [m for m in ms if m["from_source"]]
        lacking = [m["move_id"] for m in switches if not checks_of.get(m["move_id"])]
        if switches:
            cat = CAT_B if lacking else CAT_A
        else:
            cat = CAT_C if covers.get(rule, set()) - {walked} else CAT_D
        row = {"rule": rule, "区分": cat,
               "歩いた最後の主": walked,
               "いまの由来の台帳の主": c["current_source"] if c else "いまの由来の記載なし",
               "動きの回数(台帳の行数)": len(ms),
               "うち主が替わった回数": len(switches),
               "最後に動いた順の番号": to_int(ms[-1]["seq"]) if ms else "動きなし"}
        if lacking:
            row["突合の記載が無い入れ替え"] = lacking
        rule_rows.append(row)
        if ms and (not c or c["current_source"] != walked):
            gaps.append({"rule": rule, "歩いた最後の主": walked,
                         "いまの由来の台帳の主": c["current_source"] if c else "いまの由来の記載なし"})
        for m in ms:
            found = [{"突合": x["check_id"], "比べた範囲": x["scope"] or "範囲の記載なし",
                      "比べた件数": to_int(x["compared"]), "一致した件数": to_int(x["matched"]),
                      "範囲": "同じ文字列" if x["scope"] == m["scope"] else "範囲が違う",
                      "出典": x["source"]} for x in checks_of.get(m["move_id"], [])]
            move_rows.append({
                "順の番号": to_int(m["seq"]), "動き": m["move_id"], "rule": rule,
                "日付": m["date_text"] or "日付の記載なし",
                "前": m["from_source"] or "無かった", "後": m["to_source"],
                "前の種別": src[m["from_source"]]["kind"] if m["from_source"] else "無かった",
                "後の種別": src[m["to_source"]]["kind"],
                "古い側の役": m["old_role"] or "古い側なし",
                "動かした主体": m["actor"] or "記載なし",
                "入れ替えた範囲": m["scope"] or "範囲の記載なし",
                "引き継ぎの突合": found or "突合の記載なし",
                "出典": m["source"]})
    move_rows.sort(key=lambda r: r["順の番号"])

    counts = {cat: sum(1 for r in rule_rows if r["区分"] == cat) for cat in CATEGORIES}
    side = sum(1 for r in rule_rows if r["区分"] == SIDE)
    core = {"rule ごとの行": rule_rows, "動きごとの行": move_rows,
            "歩いた最後の主といまの由来の台帳が食い違う rule": gaps,
            "動きに結び付かない突合": loose}
    digest = hashlib.sha256(json.dumps(core, ensure_ascii=False, sort_keys=True,
                                       separators=(",", ":")).encode("utf-8")).hexdigest()
    return {"ok": side == 0 and not gaps,
            "分母(rule の件数)": len(rule_rows),
            "分母(動きの件数)": len(t["moves"]),
            "区分": counts,
            SIDE: side,
            "件数の検算": f"区分 4 値 + 別枠の合計 {sum(counts.values()) + side} / rule の件数 {len(rule_rows)}",
            **core,
            "判定部分の sha256": digest,
            "持たせていないもの": list(NOT_HELD)}


def _copy(t: dict[str, list[dict[str, str]]]) -> dict[str, list[dict[str, str]]]:
    return {k: [dict(r) for r in v] for k, v in t.items()}


def _by_rule(result: dict) -> dict[str, dict]:
    return {r["rule"]: r for r in result["rule ごとの行"]}


def verify(t: dict[str, list[dict[str, str]]]) -> dict:
    """この手続きが決定論かを 5 つ見る。写しはメモリの中だけで、入力には書かない。"""
    base = judge(t)
    rows = _by_rule(base)
    same_twice = judge(_copy(t))["判定部分の sha256"] == base["判定部分の sha256"]

    shuffled = _copy(t)
    shuffled["moves"] = shuffled["moves"][::-1]
    turned = _copy(t)
    turned["moves"] = turned["moves"][1:] + turned["moves"][:1]
    order_free = all(judge(x)["判定部分の sha256"] == base["判定部分の sha256"] for x in (shuffled, turned))

    total_ok = sum(base["区分"].values()) + base[SIDE] == base["分母(rule の件数)"]

    rule_of = {m["move_id"]: m["rule"] for m in t["moves"] if m["from_source"]}   # 主の入れ替えだけ
    per_move: dict[str, int] = {}
    for c in t["checks"]:
        per_move[c["move_id"]] = per_move.get(c["move_id"], 0) + 1
    drop_ok, drop_n = True, 0
    for c in t["checks"]:
        rule = rule_of.get(c["move_id"])
        if rule is None or rows[rule]["区分"] != CAT_A or per_move[c["move_id"]] != 1:
            continue
        x = _copy(t)
        x["checks"] = [r for r in x["checks"] if r["check_id"] != c["check_id"]]
        after = _by_rule(judge(x))
        drop_n += 1
        drop_ok = drop_ok and after[rule]["区分"] == CAT_B \
            and all(after[k] == rows[k] for k in rows if k != rule)

    gap_rules = {g["rule"] for g in base["歩いた最後の主といまの由来の台帳が食い違う rule"]}
    seqs = [to_int(m["seq"]) for m in t["moves"]]
    back_ok, back_n = True, 0
    if all(s is not None for s in seqs):
        for rule, row in rows.items():
            ms = sorted((m for m in t["moves"] if m["rule"] == rule), key=lambda m: to_int(m["seq"]))
            if row["区分"] == SIDE or not ms or not ms[-1]["from_source"] or rule in gap_rules:
                continue
            last = ms[-1]
            x = _copy(t)
            x["moves"].append({**last, "move_id": "verify の写し", "seq": str(max(seqs) + 1),
                               "from_source": last["to_source"], "to_source": last["from_source"],
                               "source": "verify の写し(メモリの中だけ)"})
            res = judge(x)
            after = _by_rule(res)
            back_n += 1
            back_ok = back_ok \
                and after[rule]["動きの回数(台帳の行数)"] == row["動きの回数(台帳の行数)"] + 1 \
                and {g["rule"] for g in res["歩いた最後の主といまの由来の台帳が食い違う rule"]} == gap_rules | {rule} \
                and all(after[k] == rows[k] for k in rows if k != rule)

    checks = {"二度走って判定部分の sha256 が同じ": same_twice,
              "動きの台帳の行順を入れ替えても同じ出力": order_free,
              "区分 4 値 + 別枠の合計 = rule の件数": total_ok,
              "突合を 1 行外すとその rule だけ (A) → (B)": drop_ok,
              "主を元へ戻す動きを 1 行足すとその rule だけ回数 +1 と食い違い 1 件": back_ok}
    return {"ok": all(checks.values()), "verify": checks,
            "突合を外した写しの枚数": drop_n, "動きを足した写しの枚数": back_n,
            "判定部分の sha256": base["判定部分の sha256"]}


def init(dest: str) -> list[str]:
    """見出しだけのひな型 5 枚を書く(既に在るファイルには書かない)。"""
    d = Path(dest)
    d.mkdir(parents=True, exist_ok=True)
    made = []
    for name, cols, _ in TABLES:
        p = d.joinpath(f"{name}.csv")
        if p.exists():
            raise ShiftError(f"既に在る: {p}")
        p.write_text(",".join(cols) + "\n", encoding="utf-8")
        made.append(str(p))
    return made


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="主の出どころが替わった瞬間を 1 行 1 件の一覧にする")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").add_argument("dest")
    for cmd in ("check", "rows", "verify"):
        p = sub.add_parser(cmd)
        for name, _, _ in TABLES:
            p.add_argument(name)
    a = ap.parse_args(argv)
    out = sys.stdout
    try:
        if a.cmd == "init":
            print(json.dumps({"ok": True, "書いたひな型": init(a.dest)}, ensure_ascii=False), file=out)
            return 0
        t = load([getattr(a, name) for name, _, _ in TABLES])
        if a.cmd == "verify":
            res = verify(t)
            print(json.dumps(res, ensure_ascii=False, indent=1), file=out)
            return 0 if res["ok"] else 3
        res = judge(t)
    except (ShiftError, OSError) as e:
        print(json.dumps({"ok": False, "読めない": str(e)}, ensure_ascii=False), file=out)
        return 2
    if a.cmd == "rows":
        for key in ("rule ごとの行", "動きごとの行", "歩いた最後の主といまの由来の台帳が食い違う rule",
                    "動きに結び付かない突合"):
            for row in res[key]:
                print(json.dumps(row, ensure_ascii=False), file=out)
    else:
        brief = {k: v for k, v in res.items() if k not in ("rule ごとの行", "動きごとの行")}
        print(json.dumps(brief, ensure_ascii=False, indent=1), file=out)
    return 0 if res["ok"] else 3


if __name__ == "__main__":
    sys.exit(main())
