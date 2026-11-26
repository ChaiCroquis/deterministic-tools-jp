"""due_month — 数表の行に付いた「次回改定の予定」と、その rule の行が動いてきた開始日の月日を、rule ごとに並べる。

人が書いた 4 つの CSV(行の表 / 台帳の表 / 対応の登録表 / 比べ方の登録)を読み、rule ごとに
区分 A〜D か別枠のどれか 1 か所に置いて返す。**予定を予測しない。周期を数えない。どちらの日付が正しいかを返さない。**
今日の日付を読まない(期限超過・要注意を出さない)。JSON を探しに行かない。ネットワークを使わない。標準ライブラリのみ。

  A  予定が最後の開始日より後で、月日が登録した比べ方どおりに行の月日と同じ
  B  予定が最後の開始日より後で、月日が違う
  C  予定が最後の開始日以前(既に持っている行の開始日と同じなら印)
  D  予定が空

使い方: python due_month.py --rows R.csv --ledgers L.csv --links K.csv --compare C.csv [--json] [--verify]
終了コード: 0 = 全 rule が A で印も別枠も無い / 3 = 人が見る行がある / 2 = 表が読めない / 4 = --verify が合わない
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

COMPARES = ("最後の行", "どれかの行")
ROW_COLS = ("rule", "valid_from", "予定", "出どころ", "元の行数", "出典")
LEDGER_COLS = ("台帳id", "種別", "数表id", "予定", "出典")
LINK_COLS = ("出どころ", "台帳id", "出典")
COMPARE_COLS = ("比べ方", "出典")
LABEL = {
    "A": "予定が最後の開始日より後で、月日が行の月日と同じ",
    "B": "予定が最後の開始日より後で、月日が違う",
    "C": "予定が最後の開始日以前",
    "D": "予定が空",
}
R_DATE = "日付の形でない予定"
R_RULE = "行の表に rule が空"
R_LINK = "対応の登録表が指す台帳 id が台帳の表に無い"
R_SRC = "出典が空"
R_CMP = "比べ方が 2 つの値以外"
R_DUP = "同じ (rule, valid_from, 出どころ) が 2 行"
_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")


class TableError(Exception):
    """表が読めない(1 rule も並べずに止まる)。"""


def _date(s: str) -> date | None:
    if not _ISO.fullmatch(s):
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _clean(rows: list[dict], cols: tuple[str, ...], name: str) -> list[dict]:
    out = []
    for i, r in enumerate(rows, 1):
        for c in cols:
            if c not in r or r[c] is None:
                raise TableError(f"{name} {i} 行目: 列 {c} が無い")
        out.append({c: str(r[c]).strip() for c in cols})
    return out


def judge(rows: list[dict], ledgers: list[dict], links: list[dict], compare: list[dict]) -> dict:
    """4 表(dict の list)を受け取り、rule ごとの並びと件数を返す。入力は書き換えない。"""
    rows = _clean(rows, ROW_COLS, "行の表")
    ledgers = _clean(ledgers, LEDGER_COLS, "台帳の表")
    links = _clean(links, LINK_COLS, "対応の登録表")
    compare = _clean(compare, COMPARE_COLS, "比べ方の登録")
    if len(compare) != 1:
        raise TableError(f"比べ方の登録は 1 行だけ受け取る(いま {len(compare)} 行)")
    for i, r in enumerate(rows, 1):
        if _date(r["valid_from"]) is None:
            raise TableError(f"行の表 {i} 行目: valid_from が日付の形でない: {r['valid_from']!r}")
        if r["元の行数"] == "":
            r["元の行数"] = "1"
        if not re.fullmatch(r"[1-9]\d*", r["元の行数"]):
            raise TableError(f"行の表 {i} 行目: 元の行数が 1 以上の整数でない: {r['元の行数']!r}")
    seen_l: set[str] = set()
    for i, g in enumerate(ledgers, 1):
        if g["台帳id"] == "" or g["種別"] == "":
            raise TableError(f"台帳の表 {i} 行目: 台帳id か種別が空")
        if g["台帳id"] in seen_l:
            raise TableError(f"台帳の表 {i} 行目: 台帳id が重複: {g['台帳id']}")
        seen_l.add(g["台帳id"])
    seen_k: set[tuple[str, str]] = set()
    for i, k in enumerate(links, 1):
        if k["出どころ"] == "" or k["台帳id"] == "":
            raise TableError(f"対応の登録表 {i} 行目: 出どころ か 台帳id が空")
        if (k["出どころ"], k["台帳id"]) in seen_k:
            raise TableError(f"対応の登録表 {i} 行目: 同じ対応が 2 行: {k['出どころ']} → {k['台帳id']}")
        seen_k.add((k["出どころ"], k["台帳id"]))

    # ---- 比べ方 ----
    side_cmp: list[dict] = []
    way: str | None = compare[0]["比べ方"]
    if way not in COMPARES:
        side_cmp.append({"比べ方": compare[0]["比べ方"], "理由": R_CMP})
        way = None
    elif compare[0]["出典"] == "":
        side_cmp.append({"比べ方": compare[0]["比べ方"], "理由": R_SRC})
        way = None

    # ---- 台帳と対応 ----
    side_ledger: list[dict] = []
    ledger_ok: dict[str, dict] = {}
    for g in sorted(ledgers, key=lambda g: g["台帳id"]):
        why = []
        if g["出典"] == "":
            why.append(R_SRC)
        if g["予定"] != "" and _date(g["予定"]) is None:
            why.append(R_DATE)
        if why:
            side_ledger.append({"台帳id": g["台帳id"], "予定": g["予定"], "理由": why})
        else:
            ledger_ok[g["台帳id"]] = g
    side_link: list[dict] = []
    link_ok: dict[str, list[str]] = {}
    for k in sorted(links, key=lambda k: (k["出どころ"], k["台帳id"])):
        why = []
        if k["出典"] == "":
            why.append(R_SRC)
        if k["台帳id"] not in ledger_ok:
            why.append(R_LINK)
        if why:
            side_link.append({"出どころ": k["出どころ"], "台帳id": k["台帳id"], "理由": why})
        else:
            link_ok.setdefault(k["出どころ"], []).append(k["台帳id"])

    # ---- 行を rule ごとに集める ----
    side_row: list[dict] = []
    by_rule: dict[str, list[dict]] = {}
    for r in rows:
        if r["rule"] == "":
            side_row.append({"valid_from": r["valid_from"], "出どころ": r["出どころ"], "出典": r["出典"], "理由": R_RULE})
        else:
            by_rule.setdefault(r["rule"], []).append(r)
    side_row.sort(key=lambda x: (x["valid_from"], x["出どころ"], x["出典"]))

    out_rules: list[dict] = []
    side_rule: list[dict] = []
    for rule in sorted(by_rule):
        rs = by_rule[rule]
        n_orig = sum(int(r["元の行数"]) for r in rs)
        why: set[str] = set()
        keys = [(r["valid_from"], r["出どころ"]) for r in rs]
        if len(set(keys)) != len(keys):
            why.add(R_DUP)
        if any(r["出典"] == "" for r in rs):
            why.add(R_SRC)
        if any(r["予定"] != "" and _date(r["予定"]) is None for r in rs):
            why.add(R_DATE)
        starts = sorted({r["valid_from"] for r in rs})
        mds = sorted({s[5:] for s in starts})
        plans = sorted({r["予定"] for r in rs})
        dated = [p for p in plans if p != ""]
        cat = None
        same_as_row = False
        if not why:
            if not dated:
                cat = "D"
            else:
                plan = dated[0]                      # 2 通り以上のときは最も早い日付で区分を決め、印を付ける
                if plan <= starts[-1]:
                    cat = "C"
                    same_as_row = plan in starts
                elif way is None:
                    why.add(side_cmp[0]["理由"] if side_cmp[0]["理由"] == R_CMP else "比べ方の登録の" + R_SRC)
                else:
                    pool = [starts[-1][5:]] if way == "最後の行" else mds
                    cat = "A" if plan[5:] in pool else "B"
        if why:
            side_rule.append({"rule": rule, "理由": sorted(why), "行数": len(rs), "元の行数": n_orig})
            continue
        refs = []
        for origin in sorted({r["出どころ"] for r in rs if r["出どころ"] != ""}):
            row_plans = sorted({r["予定"] for r in rs if r["出どころ"] == origin})
            for lid in link_ok.get(origin, []):
                g = ledger_ok[lid]
                refs.append({"出どころ": origin, "台帳id": lid, "種別": g["種別"], "数表id": g["数表id"],
                             "台帳の予定": g["予定"], "行の予定": row_plans, "同じ": row_plans == [g["予定"]]})
        out_rules.append({
            "rule": rule, "区分": cat, "開始日": starts, "月日": mds, "予定": plans,
            "出どころ": sorted({r["出どころ"] for r in rs}), "台帳": refs,
            "印": {"既に持っている行の開始日と同じ": same_as_row, "予定が 2 通り以上": len(plans) > 1,
                   "台帳の予定と違う": any(not x["同じ"] for x in refs)},
            "行数": len(rs), "元の行数": n_orig,
        })

    counts = {c: {"rule": 0, "行": 0, "元の行": 0} for c in "ABCD"}
    for x in out_rules:
        counts[x["区分"]]["rule"] += 1
        counts[x["区分"]]["行"] += x["行数"]
        counts[x["区分"]]["元の行"] += x["元の行数"]
    by_ledger: dict[str, int] = {}
    for x in out_rules:
        for lid in sorted({t["台帳id"] for t in x["台帳"] if not t["同じ"]}):
            by_ledger[lid] = by_ledger.get(lid, 0) + 1
    return {
        "比べ方": way,
        "rules": out_rules,
        "別枠": {"rule": side_rule, "行": side_row, "台帳": side_ledger, "対応": side_link, "比べ方": side_cmp},
        "件数": {
            "区分": counts,
            "rule の種類": len(by_rule),
            "別枠の rule": len(side_rule),
            "行の表の行": len(rows),
            "元の行": sum(int(r["元の行数"]) for r in rows),
            "印": {"台帳の予定と違う": sum(x["印"]["台帳の予定と違う"] for x in out_rules),
                   "予定が 2 通り以上": sum(x["印"]["予定が 2 通り以上"] for x in out_rules),
                   "既に持っている行の開始日と同じ": sum(x["印"]["既に持っている行の開始日と同じ"] for x in out_rules)},
            "台帳ごとの違う rule": dict(sorted(by_ledger.items())),
        },
    }


def digest(result: dict) -> str:
    return hashlib.sha256(json.dumps(result, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _cats(result: dict) -> dict[str, str]:
    d = {x["rule"]: x["区分"] for x in result["rules"]}
    d.update({x["rule"]: "別枠" for x in result["別枠"]["rule"]})
    return d


def verify(rows: list[dict], ledgers: list[dict], links: list[dict], compare: list[dict]) -> list[tuple[str, bool]]:
    """検算 5 つ。(名前, 合うか) の list を返す。"""
    base = judge(rows, ledgers, links, compare)
    checks = [
        ("検算 1 二度走りの sha256 が同じ", digest(base) == digest(judge(rows, ledgers, links, compare))),
        ("検算 2 行の表の行順を逆にしても同じ", digest(base) == digest(judge(list(reversed(rows)), ledgers, links, compare))),
        ("検算 3 区分 4 値の rule 数 + 別枠の rule 数 = rule の種類数",
         sum(v["rule"] for v in base["件数"]["区分"].values()) + base["件数"]["別枠の rule"] == base["件数"]["rule の種類"]),
    ]
    src = compare[0].get("出典", "") or "検算"
    any_ = _cats(judge(rows, ledgers, links, [{"比べ方": "どれかの行", "出典": src}]))
    last = _cats(judge(rows, ledgers, links, [{"比べ方": "最後の行", "出典": src}]))
    ok4 = set(any_) == set(last) and all(any_[k] == last[k] or (any_[k], last[k]) == ("A", "B") for k in any_)
    checks.append(("検算 4 比べ方を「最後の行」に替えると A から B へだけ動く", ok4))
    d_rules = [x for x in base["rules"] if x["区分"] == "D"]
    if not d_rules:
        checks.append(("検算 5 D の 1 rule に予定を入れるとその rule だけ D から出る(D が無いので対象なし)", True))
    else:
        target = d_rules[0]
        plan = (date.fromisoformat(target["開始日"][-1]) + timedelta(days=1)).isoformat()
        rows2 = [{**r, "予定": plan} if str(r.get("rule", "")).strip() == target["rule"] else dict(r) for r in rows]
        after = judge(rows2, ledgers, links, compare)
        rest_a = [x for x in after["rules"] if x["rule"] != target["rule"]]
        rest_b = [x for x in base["rules"] if x["rule"] != target["rule"]]
        side_a = [x for x in after["別枠"]["rule"] if x["rule"] != target["rule"]]
        ok5 = _cats(after)[target["rule"]] != "D" and rest_a == rest_b and side_a == base["別枠"]["rule"]
        checks.append(("検算 5 D の 1 rule に予定を入れるとその rule だけ D から出る", ok5))
    return checks


def read_csv(path: str | Path) -> list[dict]:
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except (OSError, UnicodeDecodeError, csv.Error) as e:
        raise TableError(f"{path}: 読めない({e})") from e


def _span(xs: list[str]) -> str:
    if len(xs) <= 4:
        return " ".join(xs)
    return f"{xs[0]} {xs[1]} … {xs[-2]} {xs[-1]}({len(xs)} 通り)"


def render(result: dict) -> str:
    out = [f"■ 比べ方: {result['比べ方'] or '(登録が別枠)'}"]
    n = result["件数"]
    for c in "ABCD":
        k = n["区分"][c]
        out.append(f"■ {c} {LABEL[c]} {k['rule']} rule(行の表 {k['行']} 行 / 元の行 {k['元の行']} 行)")
        for x in result["rules"]:
            if x["区分"] != c:
                continue
            plan = " と ".join(p or "(空)" for p in x["予定"])
            out.append(f"  {x['rule']} | 開始日 {_span(x['開始日'])} | 月日 {_span(x['月日'])} | 予定 {plan}")
            if x["印"]["既に持っている行の開始日と同じ"]:
                out.append("      印 予定は既に持っている行の開始日と同じ日付")
            if x["印"]["予定が 2 通り以上"]:
                out.append("      印 行に付いた予定が 2 通り以上(区分は最も早い日付で決めた)")
            for t in x["台帳"]:
                if not t["同じ"]:
                    rp = " と ".join(p or "(空)" for p in t["行の予定"])
                    out.append(f"      印 台帳 {t['台帳id']}({t['種別']})の予定 {t['台帳の予定'] or '(空)'} / 行の予定 {rp}")
    m = n["印"]
    out.append(f"■ 印: 台帳の予定と違う {m['台帳の予定と違う']} rule / 予定が 2 通り以上 {m['予定が 2 通り以上']} rule / "
               f"既に持っている行の開始日と同じ {m['既に持っている行の開始日と同じ']} rule")
    if n["台帳ごとの違う rule"]:
        out.append("■ 台帳ごとの違う rule: " + " / ".join(f"{k} {v}" for k, v in n["台帳ごとの違う rule"].items()))
    s = result["別枠"]
    out.append(f"■ 別枠 rule {len(s['rule'])} 件 / 行 {len(s['行'])} 件 / 台帳 {len(s['台帳'])} 件 / 対応 {len(s['対応'])} 件 / 比べ方 {len(s['比べ方'])} 件")
    for x in s["rule"]:
        out.append(f"  rule {x['rule']}: {' / '.join(x['理由'])}")
    for x in s["行"]:
        out.append(f"  行 valid_from {x['valid_from']}({x['出典'] or '出典なし'}): {x['理由']}")
    for x in s["台帳"]:
        out.append(f"  台帳 {x['台帳id']}: {' / '.join(x['理由'])}")
    for x in s["対応"]:
        out.append(f"  対応 {x['出どころ']} → {x['台帳id']}: {' / '.join(x['理由'])}")
    for x in s["比べ方"]:
        out.append(f"  比べ方 {x['比べ方'] or '(空)'}: {x['理由']}")
    out.append(f"■ rule の種類 {n['rule の種類']} / 行の表 {n['行の表の行']} 行 / 元の行 {n['元の行']} 行")
    out.append("■ 持たせていないもの: 次の改定日を推す経路 / 周期を数える経路 / 予定を行の月日に直す経路 / "
               "どちらの台帳が正しいかを返す経路 / 今日の日付を読む経路")
    return "\n".join(out)


def exit_code(result: dict) -> int:
    n = result["件数"]
    quiet = (n["区分"]["A"]["rule"] == n["rule の種類"] and not any(n["印"].values())
             and not any(result["別枠"].values()))
    return 0 if quiet else 3


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="行に付いた次回改定の予定と、行の開始日の月日を rule ごとに並べる")
    ap.add_argument("--rows", required=True, help="行の表(rule / valid_from / 予定 / 出どころ / 元の行数 / 出典)")
    ap.add_argument("--ledgers", required=True, help="台帳の表(台帳id / 種別 / 数表id / 予定 / 出典)")
    ap.add_argument("--links", required=True, help="対応の登録表(出どころ / 台帳id / 出典)")
    ap.add_argument("--compare", required=True, help="比べ方の登録(比べ方 / 出典。1 行だけ)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args(argv)
    try:
        tables = [read_csv(p) for p in (a.rows, a.ledgers, a.links, a.compare)]
        result = judge(*tables)
    except TableError as e:
        print(f"表が読めない: {e}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=1) if a.json else render(result))
    code = exit_code(result)
    if a.verify:
        for name, ok in verify(*tables):
            print(f"{name}: {'合う' if ok else '合わない'}")
            if not ok:
                code = 4
    return code


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
