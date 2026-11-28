"""switch_lag — セグメントごとに開始日が違う数表について、回が替わる窓と、登録した日ごとの
「新しい回の行に居るセグメント / 前の回の行に居るセグメント」を並べる。

値を計算しない。開始日を推さない。今日の日付を読まない。遅い・早いを返さない。
入力は人が書いた 3 表(行の表 / 見る日の登録表 / 比べ方の登録)。標準ライブラリのみ。

終了コード: 0 = 区分が全て A で印も別枠も無い / 3 = 人が見る行がある / 2 = 表が読めない / 4 = --verify が合わない
"""
from __future__ import annotations

import argparse
import ast
import csv
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

ROW_COLS = ("rule", "セグメント", "回", "開始日", "終了日", "出典")
DAY_COLS = ("見る日", "理由", "出典")
SETUP_COLS = ("種類", "値", "出典")
EDGES = ("半開", "両閉")
OPEN_END = ("INF", "")          # 終了日が閉じていない行
CATS = "ABCD"
CAT_TEXT = {
    "A": "その日すでに新しい回(かそれより後ろの回)の行に当たる",
    "B": "その日は前の回かそれより前の行に当たり、新しい回の行が後の日に在る",
    "C": "その日は前の回かそれより前の行に当たり、後の日に始まる新しい回の行が無い",
    "D": "その日に当たる行が 1 つも無い",
}


class Unreadable(Exception):
    """表が読めない(1 行も並べずに止まる)。"""


def read_csv(path: str | Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [{k: (v or "").strip() for k, v in r.items() if k is not None} for r in csv.DictReader(f)]


def read_header(path: str | Path) -> list[str]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return next(csv.reader(f), [])


def parse_day(s: str) -> dt.date | None:
    if len(s) != 10 or s[4] != "-" or s[7] != "-":
        return None
    try:
        return dt.date(int(s[:4]), int(s[5:7]), int(s[8:]))
    except ValueError:
        return None


def _need(rows: list[dict], cols: tuple[str, ...], name: str) -> None:
    for r in rows:
        miss = [c for c in cols if c not in r]
        if miss:
            raise Unreadable(f"{name}に列が無い: {' / '.join(miss)}")


def _setup(setup: list[dict]) -> tuple[list[str], list[str], str | None, list[dict]]:
    """比べ方の登録を読む。返すのは 回の順 / セグメントの全体 / 区間の端(別枠なら None)/ 別枠。"""
    _need(setup, SETUP_COLS, "比べ方の登録")
    out: list[dict] = []
    order: list[str] = []
    segs: list[str] = []
    edges = [s for s in setup if s["種類"] == "区間の端"]
    if len(edges) != 1:
        raise Unreadable(f"比べ方の登録の「区間の端」は 1 行だけ(いま {len(edges)} 行)")
    for s in setup:
        if s["種類"] not in ("回", "区間の端", "セグメント"):
            raise Unreadable(f"比べ方の登録の種類が読めない: {s['種類']!r}")
        if s["種類"] != "区間の端" and s["値"] == "":
            raise Unreadable(f"比べ方の登録の「{s['種類']}」に値が空の行がある")
    edge: str | None = edges[0]["値"]
    if edge not in EDGES:
        out.append({"表": "比べ方", "値": edges[0]["値"], "理由": "区間の端が 2 つの値(半開 / 両閉)以外"})
        edge = None
    elif edges[0]["出典"] == "":
        out.append({"表": "比べ方", "値": edges[0]["値"], "理由": "出典が空"})
        edge = None
    for kind, bag in (("回", order), ("セグメント", segs)):
        vals = [s["値"] for s in setup if s["種類"] == kind]
        if len(vals) != len(set(vals)):
            raise Unreadable(f"比べ方の登録の「{kind}」に同じ値が 2 行ある")
        for s in setup:
            if s["種類"] != kind:
                continue
            if s["出典"] == "":
                out.append({"表": "比べ方", "値": f"{kind} {s['値']}", "理由": "出典が空"})
            else:
                bag.append(s["値"])
    if not order:
        raise Unreadable("比べ方の登録に、出典の付いた「回」が 1 つも無い")
    if not segs:
        raise Unreadable("比べ方の登録に、出典の付いた「セグメント」が 1 つも無い")
    return order, segs, edge, out


def _covers(start: dt.date, end: dt.date | None, day: dt.date, edge: str) -> bool:
    if day < start:
        return False
    if end is None:
        return True
    return day < end if edge == "半開" else day <= end


def _joined(prev_end: dt.date | None, new_start: dt.date, edge: str) -> bool:
    """前の回の行の終わりと新しい回の行の始まりがつながっているか(半開 = 同じ日 / 両閉 = 翌日)。"""
    if prev_end is None:
        return False
    return prev_end == new_start if edge == "半開" else prev_end + dt.timedelta(days=1) == new_start


def judge(rows: list[dict], days: list[dict], setup: list[dict]) -> dict:
    """3 表を読み、回ごとの窓の表と、見る日 × 回の対ごとのセグメントの区分を返す(判定部分。純関数)。"""
    _need(rows, ROW_COLS, "行の表")
    _need(days, DAY_COLS, "見る日の登録表")
    order, segs, edge, aside_setup = _setup(setup)
    pos = {r: i for i, r in enumerate(order)}
    segset = set(segs)
    if any(r["rule"] == "" for r in rows):
        raise Unreadable("行の表に rule が空の行がある")
    day_vals = [d["見る日"] for d in days]
    if len(day_vals) != len(set(day_vals)):
        raise Unreadable("見る日の登録表に同じ日が 2 行ある")

    # ---- 行の表: 別枠を除く ----
    aside_rows: list[dict] = []
    keys: dict[tuple[str, str, str], int] = {}
    for r in rows:
        k = (r["rule"], r["セグメント"], r["回"])
        keys[k] = keys.get(k, 0) + 1
    used: list[dict] = []
    for r in rows:
        why = None
        start = parse_day(r["開始日"])
        end = None if r["終了日"] in OPEN_END else parse_day(r["終了日"])
        if r["出典"] == "":
            why = "出典が空"
        elif start is None or (r["終了日"] not in OPEN_END and end is None):
            why = "日付として読めない"
        elif r["回"] not in pos:
            why = "回の id が回の順に無い"
        elif r["セグメント"] not in segset:
            why = "セグメントが全体の一覧に無い"
        elif keys[(r["rule"], r["セグメント"], r["回"])] > 1:
            why = "同じ (rule, セグメント, 回) が 2 行"
        if why:
            aside_rows.append({"rule": r["rule"], "セグメント": r["セグメント"], "回": r["回"],
                               "開始日": r["開始日"], "終了日": r["終了日"], "理由": why})
        else:
            used.append({"rule": r["rule"], "seg": r["セグメント"], "round": r["回"], "start": start, "end": end})
    aside_rows.sort(key=lambda x: (x["rule"], x["セグメント"], x["回"], x["開始日"], x["終了日"], x["理由"]))

    # ---- 見る日の登録表: 別枠を除く ----
    aside_days: list[dict] = []
    look: list[tuple[dt.date, str]] = []
    for d in days:
        day = parse_day(d["見る日"])
        if d["出典"] == "":
            aside_days.append({"見る日": d["見る日"], "理由": "出典が空"})
        elif day is None:
            aside_days.append({"見る日": d["見る日"], "理由": "日付として読めない"})
        else:
            look.append((day, d["理由"]))
    look.sort()
    aside_days.sort(key=lambda x: (x["見る日"], x["理由"]))

    rules = sorted({r["rule"] for r in rows})
    by: dict[tuple[str, str], dict[str, dict]] = {}       # (rule, seg) → 回 → 行
    for u in used:
        by.setdefault((u["rule"], u["seg"]), {})[u["round"]] = u

    # ---- 出力 1: 回ごとの窓 ----
    windows: list[dict] = []
    for rule in rules:
        for rd in order:
            mine = [u for u in used if u["rule"] == rule and u["round"] == rd]
            starts = sorted({u["start"] for u in mine})
            have = {u["seg"] for u in mine}
            windows.append({
                "rule": rule, "回": rd, "行数": len(mine),
                "最初の開始日": starts[0].isoformat() if starts else "",
                "最後の開始日": starts[-1].isoformat() if starts else "",
                "日数": (starts[-1] - starts[0]).days if starts else None,
                "開始日の種類": len(starts),
                "行の無いセグメント": sorted(s for s in segs if s not in have),
                "印_窓が暦の年をまたぐ": bool(starts) and starts[0].year != starts[-1].year,
            })

    # ---- 出力 2: 見る日 × 回の対 ----
    pairs: list[dict] = []
    if edge is not None:
        for day, reason in look:
            for rule in rules:
                for i in range(1, len(order)):
                    pairs.append(_pair(rule, day, reason, order[i - 1], order[i], pos, segs, by, edge, windows))

    n_cat = [{"見る日": p["見る日"], "rule": p["rule"], "前の回": p["前の回"], "新しい回": p["新しい回"], **p["件数"]}
             for p in pairs]
    return {
        "区間の端": edge,
        "回の順": order,
        "セグメントの全体の数": len(segs),
        "窓": windows,
        "日ごと": pairs,
        "件数": {
            "行の表の行": len(rows), "使った行": len(used), "別枠の行": len(aside_rows),
            "見る日": len(look), "別枠の見る日": len(aside_days), "別枠の比べ方": len(aside_setup),
            "回ごとの行数の合計": sum(w["行数"] for w in windows),
            "区分": n_cat,
        },
        "別枠": {"行": aside_rows, "見る日": aside_days, "比べ方": aside_setup},
        "区分の意味": CAT_TEXT,
    }


def _pair(rule: str, day: dt.date, reason: str, prev: str, new: str, pos: dict[str, int], segs: list[str],
          by: dict, edge: str, windows: list[dict]) -> dict:
    lines = []
    for seg in segs:
        mine = by.get((rule, seg), {})
        hits = [u for u in mine.values() if _covers(u["start"], u["end"], day, edge)]
        hit = max(hits, key=lambda u: pos[u["round"]]) if hits else None
        n, p = mine.get(new), mine.get(prev)
        line = {"セグメント": seg, "当たる行の回": hit["round"] if hit else "", "当たる行の数": len(hits),
                "新しい回の開始日": n["start"].isoformat() if n else "", "その日までの日数": None,
                "印_つながらない": bool(n and p) and not _joined(p["end"], n["start"], edge)}
        if hit is None:
            line["区分"] = "D"
        elif pos[hit["round"]] >= pos[new]:
            line["区分"] = "A"
        elif n is not None and n["start"] > day:
            line["区分"] = "B"
            line["その日までの日数"] = (n["start"] - day).days
        else:
            line["区分"] = "C"
        lines.append(line)
    lines.sort(key=lambda x: (x["区分"], x["セグメント"]))
    win = next(w for w in windows if w["rule"] == rule and w["回"] == new)
    return {"見る日": day.isoformat(), "理由": reason, "rule": rule, "前の回": prev, "新しい回": new,
            "印_窓が暦の年をまたぐ": win["印_窓が暦の年をまたぐ"],
            "件数": {c: sum(1 for x in lines if x["区分"] == c) for c in CATS},
            "印_つながらないの数": sum(1 for x in lines if x["印_つながらない"]),
            "セグメント": lines}


def digest(res: dict) -> str:
    return hashlib.sha256(json.dumps(res, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def clock_calls(source: str) -> int:
    """ソースの中の now / today の呼び出しの数(今日の日付を読む経路が無いことの検算)。"""
    n = 0
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
            if name in ("now", "today", "utcnow"):
                n += 1
    return n


def verify(rows: list[dict], days: list[dict], setup: list[dict]) -> list[tuple[str, bool]]:
    res = judge(rows, days, setup)
    out = [("検算 1 二度走りの sha256 が同じ", digest(judge(rows, days, setup)) == digest(res)),
           ("検算 2 行の表の行順を逆にしても同じ", digest(judge(rows[::-1], days, setup)) == digest(res))]
    total = res["セグメントの全体の数"]
    out.append(("検算 3 見る日ごとに A+B+C+D = セグメントの全体の数",
                all(sum(p["件数"].values()) == total for p in res["日ごと"])))
    # 検算 4: 新しい回より後ろの回の行を除いた表で、窓の最後の開始日に置くと B が 0、最初の開始日の前日に置くと A が 0
    ok4 = True
    order = res["回の順"]
    if res["区間の端"] is not None:
        for w in res["窓"]:
            i = order.index(w["回"])
            if i == 0 or not w["行数"]:
                continue
            keep = set(order[: i + 1])
            sub = [r for r in rows if r["rule"] == w["rule"] and r["回"] in keep]
            first, last = parse_day(w["最初の開始日"]), parse_day(w["最後の開始日"])
            two = [{"見る日": last.isoformat(), "理由": "検算", "出典": "検算"},
                   {"見る日": (first - dt.timedelta(days=1)).isoformat(), "理由": "検算", "出典": "検算"}]
            got = {p["見る日"]: p["件数"] for p in judge(sub, two, setup)["日ごと"]
                   if p["rule"] == w["rule"] and p["新しい回"] == w["回"]}
            if got[two[0]["見る日"]]["B"] != 0 or got[two[1]["見る日"]]["A"] != 0:
                ok4 = False
    out.append(("検算 4 窓の最後の開始日に置くと B が 0、最初の開始日の前日に置くと A が 0", ok4))
    out.append(("検算 5 道具のソースに now / today の呼び出しが 0",
                clock_calls(Path(__file__).read_text(encoding="utf-8")) == 0))
    return out


def exit_code(res: dict) -> int:
    n = res["件数"]
    if n["別枠の行"] or n["別枠の見る日"] or n["別枠の比べ方"]:
        return 3
    if any(p["件数"]["B"] or p["件数"]["C"] or p["件数"]["D"] or p["印_つながらないの数"] for p in res["日ごと"]):
        return 3
    if any(w["行の無いセグメント"] or w["印_窓が暦の年をまたぐ"] for w in res["窓"]):
        return 3
    return 0


def render(res: dict) -> str:
    o = [f"■ 区間の端: {res['区間の端'] or '(別枠。日ごとの表は出さない)'} / セグメントの全体 {res['セグメントの全体の数']}"
         f" / 回 {len(res['回の順'])}"]
    o.append("■ 回ごとの窓(rule | 回 | 行数 | 最初の開始日 | 最後の開始日 | 日数 | 開始日の種類 | 行の無いセグメント)")
    for w in res["窓"]:
        none = w["行の無いセグメント"]
        tail = f"{len(none)}" + (f"({' '.join(none)})" if 0 < len(none) <= 8 else "")
        mark = " 印 窓が暦の年をまたぐ" if w["印_窓が暦の年をまたぐ"] else ""
        days = "" if w["日数"] is None else w["日数"]
        o.append(f"  {w['rule']} | {w['回']} | {w['行数']} | {w['最初の開始日']} | {w['最後の開始日']} | {days} | "
                 f"{w['開始日の種類']} | {tail}{mark}")
    o.append(f"■ 回ごとの行数の合計 {res['件数']['回ごとの行数の合計']}")
    last_day = None
    for p in res["日ごと"]:
        if p["見る日"] != last_day:
            o.append(f"■ 見る日 {p['見る日']}(理由: {p['理由']})")
            last_day = p["見る日"]
        n = p["件数"]
        mark = " 印 窓が暦の年をまたぐ" if p["印_窓が暦の年をまたぐ"] else ""
        gap = f" 印 つながらない {p['印_つながらないの数']}" if p["印_つながらないの数"] else ""
        o.append(f"  {p['rule']} | {p['前の回']} → {p['新しい回']} | A {n['A']} / B {n['B']} / C {n['C']} / D {n['D']}{mark}{gap}")
        if n["B"] or n["C"] or n["D"]:      # 全て A の対は件数だけ(1 行ずつは --json に在る)
            for x in p["セグメント"]:
                extra = ""
                if x["区分"] == "B":
                    extra = f" | 新しい回の開始日 {x['新しい回の開始日']} | その日まで {x['その日までの日数']} 日"
                elif x["区分"] == "C" and x["新しい回の開始日"]:
                    extra = f" | 新しい回の開始日 {x['新しい回の開始日']}"
                hit = x["当たる行の回"] or "(無し)"
                o.append(f"      {x['区分']} | {x['セグメント']} | 当たる行の回 {hit}{extra}"
                         + (" | 印 つながらない" if x["印_つながらない"] else ""))
    b = res["別枠"]
    o.append(f"■ 別枠 行 {len(b['行'])} 件 / 見る日 {len(b['見る日'])} 件 / 比べ方 {len(b['比べ方'])} 件")
    for x in b["行"]:
        o.append(f"  行 {x['rule']} | {x['セグメント']} | {x['回']} | {x['開始日']} | {x['終了日']}: {x['理由']}")
    for x in b["見る日"]:
        o.append(f"  見る日 {x['見る日']}: {x['理由']}")
    for x in b["比べ方"]:
        o.append(f"  比べ方 {x['値']}: {x['理由']}")
    n = res["件数"]
    o.append(f"■ 行の表 {n['行の表の行']} 行(使った行 {n['使った行']} / 別枠 {n['別枠の行']})/ 見る日 {n['見る日']}")
    o.append("■ 持たせていないもの: 額や率を読む経路 / 開始日の予測 / 今日の日付 / 遅い・早い・順位 / 名前の訳し・寄せ")
    return "\n".join(o)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="回が替わる窓と、登録した日ごとのセグメントの区分を並べる")
    ap.add_argument("--rows", required=True, help="行の表(CSV)")
    ap.add_argument("--days", help="見る日の登録表(CSV。無ければ窓の表だけ)")
    ap.add_argument("--setup", required=True, help="比べ方の登録(CSV)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        for path, cols, name in ((a.rows, ROW_COLS, "行の表"), (a.days, DAY_COLS, "見る日の登録表"),
                                 (a.setup, SETUP_COLS, "比べ方の登録")):
            if path:
                miss = [c for c in cols if c not in read_header(path)]
                if miss:
                    raise Unreadable(f"{name}に列が無い: {' / '.join(miss)}")
        rows, setup = read_csv(a.rows), read_csv(a.setup)
        days = read_csv(a.days) if a.days else []
        res = judge(rows, days, setup)
    except (Unreadable, OSError, UnicodeDecodeError) as e:
        print(f"読めない: {e}")
        return 2
    if a.json:
        print(json.dumps({**res, "sha256": digest(res)}, ensure_ascii=False, indent=1))
    else:
        print(render(res))
        print(f"sha256 {digest(res)}")
    code = exit_code(res)
    if a.verify:
        for name, ok in verify(rows, days, setup):
            print(f"{name}: {'合う' if ok else '合わない'}")
            if not ok:
                code = 4
    return code


if __name__ == "__main__":
    sys.exit(main())
