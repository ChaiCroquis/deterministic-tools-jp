"""locator_kind — 原本の置き場が年度ごとにどう決まるかを、出どころごとに層で並べる。

読むのは渡された 5 枚の表だけ(置き場の台帳 / 出どころの台帳 / 決まり方の登録表 / 型の台帳 / 依存の台帳)。
ネットワークに出ない。ディスクを歩かない。場所の文字列を URL として読まない。置き場が在るか・取れるかを
確かめない。年度の記号は文字列のまま写し、数として読まない(1 足さない、和暦と西暦を換算しない)。
型を既存の場所から推し当てない。足し忘れの危なさに点数も順位も付けない。時計を読まない。float を使わない。

使い方:
  python locator_kind.py check  places.csv origins.csv kinds.csv patterns.csv deps.csv [--kigou 記号]
  python locator_kind.py rows   places.csv origins.csv kinds.csv patterns.csv deps.csv   # 出どころ 1 件 1 行の CSV
  python locator_kind.py verify places.csv origins.csv kinds.csv patterns.csv deps.csv   # 5 つの検算
終了コード: 0 = 判定した / 3 = verify のどれかが合わない / 2 = 表の形の誤り(1 件も判定しない)
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys

ORDER = ("places", "origins", "kinds", "patterns", "deps")
TABLE_NAME = {"places": "置き場の台帳", "origins": "出どころの台帳", "kinds": "決まり方の登録表",
              "patterns": "型の台帳", "deps": "依存の台帳"}
COLUMNS = {
    "places": ("置き場 id", "出どころ id", "年度の記号", "場所", "出典"),
    "origins": ("出どころ id", "領域", "決まり方の記号", "型 id", "足す人と機会", "版の記録の在り所", "出典"),
    "kinds": ("記号", "意味", "出典"),
    "patterns": ("型 id", "型", "印に入れる欄名", "出典"),
    "deps": ("rule id", "出どころ id", "出典"),
}
MARK = "{N}"                                   # 型の中の、置き換える印
MARK_COLUMNS = ("年度の記号", "置き場 id")      # 印に入れてよい欄(置き場の台帳の欄)
K_PATTERN, K_HAND, K_UPSTREAM = "型から作る", "人が足す", "上流が運ぶ"
NO_KIND, NO_WHO, NO_VERSION, NONE = "決まり方の記載なし", "足す人の記載なし", "版の記録の記載なし", "記載なし"
NOT_IN_LEDGER = "出どころの台帳に無い"
MIXED = "決まり方が混ざる"

KUBUN = (
    "(A) 型が宣言され、台帳の場所がすべて型と一致する",
    "(B) 型が宣言されているが、一致しない場所が在る",
    "(C) 人が足す",
    "(D) 上流が運ぶ",
    "(E) A〜D に当たらない",
)
E_SUB = (
    "決まり方の記載なし",
    "型から作る なのに比べる場所が無い",
    "人が足す なのに型 id が在る",
    "上流が運ぶ なのに場所の行か型 id が在る",
    "登録表に在るその他の記号",
)
BETSU = (
    "出典が空",
    "決まり方の記号が登録表に無い",
    "置き場 id が重複",
    "型 id が型の台帳に無い",
    "型から作る なのに型 id が空",
    "依存の台帳の出どころ id が出どころの台帳に無い",
)
SHINAI = {
    "ネットワークに出ない": "取りに行く引数が無い",
    "ディスクを歩かない": "読むのは渡された 5 枚だけ",
    "置き場が在るかを確かめない": "場所の文字列は写して比べるだけで、URL としても読まない",
    "年度の記号を進めない": "記号は文字列のまま。次の記号は引数で受ける",
    "型を推し当てない": "型は型の台帳に書かれたものだけ",
    "足し忘れに順位を付けない": "点数の欄も順位の欄も無い",
    "時計を読まない": "今日の日付を使う経路が無い",
}


class FormError(Exception):
    """表の形の誤り(1 件も判定しない)。"""


def blank(s: str) -> bool:
    return s.strip() == ""


def read_table(path: str, kind: str) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        head = reader.fieldnames or []
        lack = [c for c in COLUMNS[kind] if c not in head]
        if lack:
            raise FormError(f"{TABLE_NAME[kind]}に列が無い: {' / '.join(lack)}")
        return [{c: (row.get(c) or "") for c in COLUMNS[kind]} for row in reader]


def read_all(paths: list[str]) -> dict[str, list[dict[str, str]]]:
    if len(paths) != len(ORDER):
        raise FormError(f"表は {len(ORDER)} 枚渡す(いま {len(paths)} 枚)")
    return {kind: read_table(p, kind) for kind, p in zip(ORDER, paths)}


def check_form(t: dict[str, list[dict[str, str]]]) -> None:
    """鍵が鍵として読めるかだけを見る。落ちたら 1 件も判定しない。"""
    for kind, key in (("origins", "出どころ id"), ("kinds", "記号"), ("patterns", "型 id")):
        seen: set[str] = set()
        for r in t[kind]:
            if blank(r[key]):
                raise FormError(f"{TABLE_NAME[kind]}に {key} が空の行が在る")
            if r[key] in seen:
                raise FormError(f"{TABLE_NAME[kind]}の {key} が重複: {r[key]}")
            seen.add(r[key])
    for r in t["patterns"]:
        if MARK not in r["型"]:
            raise FormError(f"型の台帳の型に、置き換える印 {MARK} が無い: {r['型 id']}")
        if r["印に入れる欄名"] not in MARK_COLUMNS:
            raise FormError(f"型の台帳の「印に入れる欄名」は {' / '.join(MARK_COLUMNS)} のどれか: {r['型 id']}")
    for r in t["places"]:
        if blank(r["置き場 id"]):
            raise FormError("置き場の台帳に 置き場 id が空の行が在る")
    for r in t["deps"]:
        if blank(r["rule id"]) or blank(r["出どころ id"]):
            raise FormError("依存の台帳に rule id か 出どころ id が空の行が在る")


def apply_pattern(pattern: str, value: str) -> str:
    """型の印を、渡された文字列でそのまま置き換える(数として読まない)。"""
    return pattern.replace(MARK, value)


def _digest(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def judge(t: dict[str, list[dict[str, str]]], kigou: str | None = None) -> dict:
    check_form(t)
    unused: list[dict[str, str]] = []

    def skip(kind: str, key: str, why: str) -> None:
        unused.append({"表": TABLE_NAME[kind], "鍵": key, "理由": why})

    kinds: dict[str, dict[str, str]] = {}
    for r in t["kinds"]:
        if blank(r["出典"]):
            skip("kinds", r["記号"], "出典が空")
        else:
            kinds[r["記号"]] = r
    patterns: dict[str, dict[str, str]] = {}
    for r in t["patterns"]:
        if blank(r["出典"]):
            skip("patterns", r["型 id"], "出典が空")
        else:
            patterns[r["型 id"]] = r
    origins = {r["出どころ id"]: r for r in t["origins"]}

    places: dict[str, list[dict[str, str]]] = {oid: [] for oid in origins}
    id_count: dict[str, int] = {}
    for r in t["places"]:
        if blank(r["出典"]):
            skip("places", r["置き場 id"], "出典が空")
        elif r["出どころ id"] not in origins:
            skip("places", r["置き場 id"], "出どころ id が出どころの台帳に無い")
        else:
            places[r["出どころ id"]].append(r)
            id_count[r["置き場 id"]] = id_count.get(r["置き場 id"], 0) + 1
    for oid in places:
        places[oid].sort(key=lambda p: tuple(p[c] for c in COLUMNS["places"]))

    pairs: set[tuple[str, str]] = set()
    for r in t["deps"]:
        pair = (r["rule id"], r["出どころ id"])
        if blank(r["出典"]):
            skip("deps", " → ".join(pair), "出典が空")
        elif pair in pairs:
            skip("deps", " → ".join(pair), "同じ行が 2 度在る")
        else:
            pairs.add(pair)
    rules_of: dict[str, list[str]] = {}
    origins_of: dict[str, list[str]] = {}
    for rule, oid in sorted(pairs):
        rules_of.setdefault(oid, []).append(rule)
        origins_of.setdefault(rule, []).append(oid)
    phantoms = sorted(oid for oid in rules_of if oid not in origins)

    rows: list[dict] = []
    shown: dict[str, str] = {}          # 出どころ id → 表に出す決まり方の記号
    for oid in sorted(origins):
        o, mine = origins[oid], places[oid]
        sym, tid = o["決まり方の記号"], o["型 id"]
        shown[oid] = NO_KIND if blank(sym) else sym
        kubun = betsu = sub = ""
        mismatch: list[dict[str, str]] = []
        if blank(o["出典"]):
            betsu = BETSU[0]
        elif not blank(sym) and sym not in kinds:
            betsu = BETSU[1]
        elif any(id_count[p["置き場 id"]] > 1 for p in mine):
            betsu = BETSU[2]
        elif not blank(tid) and tid not in patterns:
            betsu = BETSU[3]
        elif sym == K_PATTERN and blank(tid):
            betsu = BETSU[4]
        elif blank(sym):
            kubun, sub = KUBUN[4], E_SUB[0]
        elif sym == K_PATTERN:
            if not mine:
                kubun, sub = KUBUN[4], E_SUB[1]
            else:
                pat = patterns[tid]
                for p in mine:
                    want = apply_pattern(pat["型"], p[pat["印に入れる欄名"]])
                    if p["場所"] != want:
                        mismatch.append({"置き場 id": p["置き場 id"], "年度の記号": p["年度の記号"],
                                         "台帳の場所": p["場所"], "型に年度の記号を当てた文字列": want,
                                         "出典": p["出典"]})
                kubun = KUBUN[1] if mismatch else KUBUN[0]
        elif sym == K_HAND:
            kubun, sub = (KUBUN[2], "") if blank(tid) else (KUBUN[4], E_SUB[2])
        elif sym == K_UPSTREAM:
            kubun, sub = (KUBUN[3], "") if not mine and blank(tid) else (KUBUN[4], E_SUB[3])
        else:
            kubun, sub = KUBUN[4], E_SUB[4]

        kind_layer = shown[oid]
        if not blank(tid) and tid in patterns:
            kind_layer += f"(型 {patterns[tid]['型']})"
        layers = {
            "rule": "、".join(rules_of.get(oid, [])) or NONE,
            "出どころ": o["領域"] if not blank(o["領域"]) else NONE,
            "置き場": "、".join(f"{p['置き場 id']}({p['年度の記号']})" for p in mine) or NONE,
            "決まり方": kind_layer,
            "足す人と機会": o["足す人と機会"] if not blank(o["足す人と機会"]) else NO_WHO,
            "版の記録の在り所": o["版の記録の在り所"] if not blank(o["版の記録の在り所"]) else NO_VERSION,
        }
        rows.append({
            "出どころ id": oid, "領域": o["領域"], "決まり方の記号": shown[oid],
            "区分": kubun, "E の内訳": sub, "別枠の理由": betsu,
            "年度の記号の一覧": sorted({p["年度の記号"] for p in mine}),
            "置き場の件数": len(mine), "一致しない場所": mismatch,
            "層": layers, "層の 1 行": " → ".join(layers[k] for k in layers), "出典": o["出典"],
        })
    for oid in phantoms:
        shown[oid] = NOT_IN_LEDGER
        layers = {"rule": "、".join(rules_of[oid]), "出どころ": NONE, "置き場": NONE, "決まり方": NOT_IN_LEDGER,
                  "足す人と機会": NO_WHO, "版の記録の在り所": NO_VERSION}
        rows.append({
            "出どころ id": oid, "領域": "", "決まり方の記号": NOT_IN_LEDGER,
            "区分": "", "E の内訳": "", "別枠の理由": BETSU[5],
            "年度の記号の一覧": [], "置き場の件数": 0, "一致しない場所": [],
            "層": layers, "層の 1 行": " → ".join(layers[k] for k in layers), "出典": "",
        })

    rule_rows: list[dict] = []
    for rule in sorted(origins_of):
        tally: dict[str, int] = {}
        for oid in origins_of[rule]:
            tally[shown[oid]] = tally.get(shown[oid], 0) + 1
        rule_rows.append({"rule id": rule, "依存する出どころの数": len(origins_of[rule]),
                          "出どころ": origins_of[rule], "決まり方の内訳": dict(sorted(tally.items())),
                          "印": MIXED if len(tally) > 1 else ""})

    n_kubun = {k: sum(1 for r in rows if r["区分"] == k) for k in KUBUN}
    n_betsu = {b: sum(1 for r in rows if r["別枠の理由"] == b) for b in BETSU}
    total_k, total_b = sum(n_kubun.values()), sum(n_betsu.values())
    res: dict = {
        "ok": True,
        "分母(出どころの件数)": len(rows),
        "分母の内訳": {"出どころの台帳の行数": len(origins), "依存の台帳にだけ出る出どころ id": len(phantoms)},
        "区分": n_kubun,
        "E の内訳": {s: sum(1 for r in rows if r["E の内訳"] == s) for s in E_SUB},
        "別枠": n_betsu,
        "出どころごと": rows,
        "rule ごと": rule_rows,
        "決まり方が混ざる rule の数": sum(1 for r in rule_rows if r["印"]),
        "使わなかった行": sorted(unused, key=lambda u: (u["表"], u["鍵"], u["理由"])),
        "件数の合計の検算": f"区分 {total_k} + 別枠 {total_b} = {total_k + total_b} / 分母 {len(rows)}",
    }
    if kigou is not None:
        res["型に当てた文字列"] = {
            "渡された年度の記号": kigou,
            "出どころ": [{"出どころ id": r["出どころ id"], "型 id": origins[r["出どころ id"]]["型 id"],
                          "型": patterns[origins[r["出どころ id"]]["型 id"]]["型"],
                          "型に当てた文字列": apply_pattern(patterns[origins[r["出どころ id"]]["型 id"]]["型"], kigou)}
                         for r in rows if r["区分"] == KUBUN[0]],
            "読み方": "型の印を渡された記号で置き換えた文字列。その場所に何かが在るかは見ていない",
        }
    res["判定部分の sha256"] = _digest(res)
    res["しないこと"] = SHINAI
    return res


def _copy(t: dict[str, list[dict[str, str]]]) -> dict[str, list[dict[str, str]]]:
    return {k: [dict(r) for r in v] for k, v in t.items()}


def _by_id(res: dict, key: str, name: str) -> dict[str, dict]:
    return {r[name]: r for r in res[key]}


def _one_char(s: str) -> str:
    if s == "":
        return "x"
    return s[:-1] + ("y" if s[-1] == "x" else "x")


def verify(t: dict[str, list[dict[str, str]]]) -> dict:
    base = judge(t)
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"検算": name, "ok": ok, "詳細": detail})

    again = judge(_copy(t))
    add("二度走って同じ指紋", again["判定部分の sha256"] == base["判定部分の sha256"], base["判定部分の sha256"][:12])

    rev = judge({k: list(reversed(v)) for k, v in _copy(t).items()})
    add("5 枚の行順を入れ替えても同じ出力", rev == base, "逆順で読み直した")

    total = sum(base["区分"].values()) + sum(base["別枠"].values())
    add("区分 + 別枠 = 出どころの件数", total == base["分母(出どころの件数)"], base["件数の合計の検算"])

    b_rows = _by_id(base, "出どころごと", "出どころ id")
    a_ids = {oid for oid, r in b_rows.items() if r["区分"] == KUBUN[0]}
    tried = bad = 0
    for i, p in enumerate(t["places"]):
        if p["出どころ id"] not in a_ids or blank(p["出典"]):
            continue
        tried += 1
        c = _copy(t)
        c["places"][i]["場所"] = _one_char(p["場所"])
        got = _by_id(judge(c), "出どころごと", "出どころ id")
        moved = {oid for oid in b_rows if got[oid]["区分"] != b_rows[oid]["区分"]
                 or got[oid]["別枠の理由"] != b_rows[oid]["別枠の理由"]}
        if moved != {p["出どころ id"]} or got[p["出どころ id"]]["区分"] != KUBUN[1]:
            bad += 1
    add("(A) の場所を 1 行だけ 1 文字替えると、その出どころだけ (B) に動く", bad == 0,
        f"替えた行 {tried} / 合わない {bad}")

    b_rules = _by_id(base, "rule ごと", "rule id")
    tried = bad = 0
    for i, o in enumerate(t["origins"]):
        oid = o["出どころ id"]
        if o["決まり方の記号"] != K_PATTERN or b_rows[oid]["区分"] not in KUBUN[:2]:
            continue
        tried += 1
        c = _copy(t)
        c["origins"][i]["決まり方の記号"], c["origins"][i]["型 id"] = K_HAND, ""
        res = judge(c)
        got, got_rules = _by_id(res, "出どころごと", "出どころ id"), _by_id(res, "rule ごと", "rule id")
        moved = {x for x in b_rows if got[x] != b_rows[x]}
        moved_rules = {x for x in b_rules if got_rules[x] != b_rules[x]}
        want_rules = {x for x, r in b_rules.items() if oid in r["出どころ"]}
        if moved != {oid} or moved_rules != want_rules:
            bad += 1
    add("型から作る を 人が足す に替えると、その出どころと、そこに依存する rule だけが変わる", bad == 0,
        f"替えた行 {tried} / 合わない {bad}")
    return {"ok": all(c["ok"] for c in checks), "検算": checks}


ROW_HEAD = ("出どころ id", "領域", "決まり方の記号", "区分", "E の内訳", "別枠の理由", "年度の記号の一覧",
            "置き場の件数", "一致しない場所の件数", "rule", "置き場", "足す人と機会", "版の記録の在り所", "出典")


def as_rows(res: dict) -> list[list[str]]:
    out = [list(ROW_HEAD)]
    for r in res["出どころごと"]:
        la = r["層"]
        out.append([r["出どころ id"], r["領域"], r["決まり方の記号"], r["区分"], r["E の内訳"], r["別枠の理由"],
                    " / ".join(r["年度の記号の一覧"]), str(r["置き場の件数"]), str(len(r["一致しない場所"])),
                    la["rule"], la["置き場"], la["足す人と機会"], la["版の記録の在り所"], r["出典"]])
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="原本の置き場の決まり方を、出どころごとに層で並べる")
    ap.add_argument("command", choices=("check", "rows", "verify"))
    ap.add_argument("tables", nargs="+", help="places origins kinds patterns deps の順に 5 枚")
    ap.add_argument("--kigou", default=None, help="(A) の型に当てる年度の記号(文字列のまま置き換える)")
    a = ap.parse_args(argv)
    try:
        t = read_all(a.tables)
        if a.command == "verify":
            v = verify(t)
            print(json.dumps(v, ensure_ascii=False, indent=1))
            return 0 if v["ok"] else 3
        res = judge(t, a.kigou)
    except FormError as e:
        print(json.dumps({"ok": False, "表の形の誤り": str(e)}, ensure_ascii=False))
        return 2
    if a.command == "rows":
        csv.writer(sys.stdout, lineterminator="\n").writerows(as_rows(res))
    else:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
