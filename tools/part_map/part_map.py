"""part_map — 計画に書かれた「部品」と「詰まり方」の対応を、人が台帳に書いた記載だけで 1 枚の境界の地図にする。

読むのは渡された 4 枚の表(詰まり方の台帳 / 部品の台帳 / 対応の台帳 / 記号の登録表)だけ。
名前や語の似かたから対応を当てない(文字列比較・類似度の経路が無い)、どの部品を線の内に入れるべきかを決めない、
記載が無いことを「対応する部品が存在しない」と言い換えない、該当本数を足さない、1 対 1 が成り立つかの真偽を返さない、
ネットワークに出ない、ディスクを歩かない、時計を読まない、入力を書き換えない、float を使わない。
標準ライブラリのみ(csv / json / hashlib / argparse)。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys

ORDER = ("kadai", "buhin", "taiou", "kigou")
COLS = {
    "kadai": ("詰まり方 id", "説明", "該当本数", "出典"),
    "buhin": ("部品 id", "内容", "線の記号", "業種依存", "出典"),
    "taiou": ("詰まり方 id", "部品 id", "記載の種類", "対応を書いた側の出典", "部品の側の出典"),
    "kigou": ("記号", "意味", "要求する欄", "出典"),
}
LINE_IN, LINE_OUT = "線の内と宣言", "線の外"
LINES = (LINE_IN, LINE_OUT)
SAME, WORD, NEAR = "同じ数が両側に在る", "内容の語が代表例に在る", "近い語のみ"
KINDS = (SAME, WORD, NEAR)
SOURCE_COLS = ("出典", "対応を書いた側の出典", "部品の側の出典")
SANCHI = (
    "(A) 線の内の部品に対応の記載が在る",
    "(B) 線の外の部品にだけ記載が在る",
    "(C) 読んだ範囲に記載なし",
)
BETSU = (
    "出典が空",
    "対応の片側の出典が空",
    "台帳に無い id を指す対応",
    "登録表に無い記号",
    "id の重複",
)
SHINAI = {
    "対応を当てない": "名前や語の似かたを比べる経路が無い。対応は人が台帳に書いた行だけ",
    "線を引き直さない": "どの部品を線の内に入れるべきかの欄が無い。線の記号は台帳のまま読む",
    "記載なしを言い換えない": "(C) は「読んだ範囲に記載なし」で固定。対応する部品が存在しない、とは言わない",
    "該当本数を足さない": "1 本の道具が複数の詰まり方に数えられているので、合計を作る経路が無い",
    "真偽を返さない": "1 対 1 の宣言に対して返すのは件数だけ。成り立つ / 成り立たない、一致率、順位、合計の 1 値の欄が無い",
    "取りに行かない": "ネットワークに出ない。原本やソースを開かない。入力フォルダの外を読まない",
    "時計を読まない": "日付を出力に入れない",
}


class ShapeError(ValueError):
    """表の形の誤り。1 件も判定しない(終了コード 2)。"""


def _blank(s: str | None) -> bool:
    return s is None or s.strip() == ""


def read_table(path: str) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def read_all(paths: list[str]) -> dict[str, list[dict[str, str]]]:
    if len(paths) != 4:
        raise ShapeError("表は 4 枚(詰まり方 部品 対応 記号 の順)")
    return {k: read_table(p) for k, p in zip(ORDER, paths)}


def _shape(t: dict[str, list[dict[str, str]]]) -> dict[str, tuple[str, ...]]:
    for k in ORDER:
        for i, r in enumerate(t[k], 1):
            miss = [c for c in COLS[k] if c not in r]
            if miss:
                raise ShapeError(f"{k} の {i} 行目に列が無い: {miss}")
    sym = [r["記号"].strip() for r in t["kigou"]]
    if any(x == "" for x in sym) or len(set(sym)) != len(sym):
        raise ShapeError("記号の登録表に空か重複")
    req: dict[str, tuple[str, ...]] = {}
    for r in t["kigou"]:
        s = r["記号"].strip()
        if s not in LINES + KINDS:
            raise ShapeError(f"道具が意味を持たない記号は登録できない: {s}")
        cols = tuple(c.strip() for c in r["要求する欄"].split("/") if c.strip())
        bad = [c for c in cols if c not in SOURCE_COLS]
        if bad:
            raise ShapeError(f"要求する欄に書けるのは出典の欄だけ: {bad}")
        req[s] = cols
    for k, col in (("kadai", "詰まり方 id"), ("buhin", "部品 id")):
        if any(_blank(r[col]) for r in t[k]):
            raise ShapeError(f"{k} に {col} が空の行")
    if any(_blank(r["詰まり方 id"]) or _blank(r["部品 id"]) for r in t["taiou"]):
        raise ShapeError("対応の台帳に詰まり方 id か部品 id が空の行")
    return req


def _first(reasons: set[str]) -> str | None:
    for b in BETSU:
        if b in reasons:
            return b
    return None


def _req_blank(r: dict[str, str], cols: tuple[str, ...]) -> bool:
    return any(c in r and _blank(r[c]) for c in cols)


def judge(t: dict[str, list[dict[str, str]]]) -> dict:
    req = _shape(t)
    reg = set(req)
    kid = [r["詰まり方 id"].strip() for r in t["kadai"]]
    bid = [r["部品 id"].strip() for r in t["buhin"]]
    kn = {x: kid.count(x) for x in kid}
    bn = {x: bid.count(x) for x in bid}

    def own_kadai(r: dict) -> set[str]:
        s = set()
        if _blank(r["出典"]):
            s.add(BETSU[0])
        if kn[r["詰まり方 id"].strip()] > 1:
            s.add(BETSU[4])
        return s

    def own_buhin(r: dict) -> set[str]:
        s = set()
        line = r["線の記号"].strip()
        if _blank(r["出典"]) or (line in req and _req_blank(r, req[line])):
            s.add(BETSU[0])
        if line not in reg or line not in LINES:
            s.add(BETSU[3])
        if bn[r["部品 id"].strip()] > 1:
            s.add(BETSU[4])
        return s

    kadai_by = {}
    for r in t["kadai"]:
        kadai_by.setdefault(r["詰まり方 id"].strip(), []).append(r)
    buhin_by = {}
    for r in t["buhin"]:
        buhin_by.setdefault(r["部品 id"].strip(), []).append(r)

    def taiou_reasons(r: dict) -> set[str]:
        s = set()
        kind = r["記載の種類"].strip()
        if _blank(r["対応を書いた側の出典"]) or _blank(r["部品の側の出典"]) or (kind in req and _req_blank(r, req[kind])):
            s.add(BETSU[1])
        k, b = r["詰まり方 id"].strip(), r["部品 id"].strip()
        if k not in kadai_by or b not in buhin_by:
            s.add(BETSU[2])
        if kind not in reg or kind not in KINDS:
            s.add(BETSU[3])
        for x in kadai_by.get(k, []):
            s |= own_kadai(x)
        for x in buhin_by.get(b, []):
            s |= own_buhin(x)
        return s

    tr = [(r, _first(taiou_reasons(r))) for r in t["taiou"]]

    def part_line(b: str) -> str:
        return buhin_by[b][0]["線の記号"].strip()

    def link(r: dict) -> dict:
        b = r["部品 id"].strip()
        return {"部品 id": b, "部品の内容": buhin_by[b][0]["内容"], "記載の種類": r["記載の種類"].strip(),
                "対応を書いた側の出典": r["対応を書いた側の出典"], "部品の側の出典": r["部品の側の出典"]}

    def lkey(x: dict) -> tuple:
        return (x.get("部品 id", ""), json.dumps(x, ensure_ascii=False, sort_keys=True))

    rows = []
    for r in t["kadai"]:
        k = r["詰まり方 id"].strip()
        mine = [(x, why) for x, why in tr if x["詰まり方 id"].strip() == k]
        reason = _first(own_kadai(r) | {why for _, why in mine if why})
        row = {"詰まり方 id": k, "説明": r["説明"], "該当本数(文字列のまま)": r["該当本数"], "出典": r["出典"]}
        if reason:
            row["別枠"] = reason
            rows.append(row)
            continue
        solid = [x for x, _ in mine if x["記載の種類"].strip() != NEAR]
        inside = sorted((link(x) for x in solid if part_line(x["部品 id"].strip()) == LINE_IN), key=lkey)
        outside = sorted((link(x) for x in solid if part_line(x["部品 id"].strip()) == LINE_OUT), key=lkey)
        near = sorted((link(x) for x, _ in mine if x["記載の種類"].strip() == NEAR), key=lkey)
        row["3 値"] = SANCHI[0] if inside else SANCHI[1] if outside else SANCHI[2]
        row["線の内の部品"] = inside
        row["線の外の部品"] = outside
        row["近い語のみ(数えない)"] = near
        rows.append(row)
    order = {k: n for n, k in enumerate(SANCHI + BETSU)}
    rows.sort(key=lambda r: (order[r.get("3 値") or r["別枠"]], r["詰まり方 id"], lkey(r)))

    per_part = []
    for b in sorted(buhin_by):
        mine = [(x, why) for x, why in tr if x["部品 id"].strip() == b]
        ok = sum(1 for x, why in mine if not why and x["記載の種類"].strip() != NEAR)
        own = _first(set().union(*(own_buhin(x) for x in buhin_by[b])))
        per_part.append({
            "部品 id": b, "内容": buhin_by[b][0]["内容"],
            "線の記号": sorted({x["線の記号"].strip() for x in buhin_by[b]}),
            "業種依存(文字列のまま)": sorted({x["業種依存"] for x in buhin_by[b]}),
            "出典": sorted({x["出典"] for x in buhin_by[b]}),
            "部品の行の別枠": own or "",
            "対応の記載(近い語のみを除く)": ok,
            "件数の段": "0" if ok == 0 else "1" if ok == 1 else "2 以上",
            "近い語のみ": sum(1 for x, why in mine if not why and x["記載の種類"].strip() == NEAR),
            "別枠の対応": sum(1 for _, why in mine if why)})
    missing = sum(1 for x, _ in tr if x["部品 id"].strip() not in buhin_by)

    sanchi = {k: sum(1 for r in rows if r.get("3 値") == k) for k in SANCHI}
    betsu = {k: sum(1 for r in rows if r.get("別枠") == k) for k in BETSU}
    clean_in = [p for p in per_part if not p["部品の行の別枠"] and p["線の記号"] == [LINE_IN]]
    kensan = {
        "線の内と宣言された部品の数": len(clean_in),
        "そのうち対応の記載がちょうど 1 件": sum(1 for p in clean_in if p["対応の記載(近い語のみを除く)"] == 1),
        "そのうち対応の記載が 0 件": sum(1 for p in clean_in if p["対応の記載(近い語のみを除く)"] == 0),
        "そのうち対応の記載が 2 件以上": sum(1 for p in clean_in if p["対応の記載(近い語のみを除く)"] >= 2),
        "詰まり方の数(別枠を除く)": sum(sanchi.values()),
        "線の内の部品がちょうど 1 つの詰まり方": sum(1 for r in rows if r.get("3 値") == SANCHI[0] and len(r["線の内の部品"]) == 1),
        "(C) 読んだ範囲に記載なしの詰まり方": sanchi[SANCHI[2]],
        "読み方": "件数だけ。1 対 1 が成り立つかどうかの欄・一致率・合計の 1 値は無い",
    }
    core = {"3 値": sanchi, "別枠": betsu, "詰まり方ごと": rows, "部品ごと": per_part,
            "台帳に無い部品 id を指す対応": missing, "宣言の検算(件数だけ)": kensan}
    digest = hashlib.sha256(json.dumps(core, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    part_sum = sum(p["対応の記載(近い語のみを除く)"] + p["近い語のみ"] + p["別枠の対応"] for p in per_part) + missing
    return {"ok": True, "分母(詰まり方の行数)": len(t["kadai"]), "対応の行数": len(t["taiou"]), **core,
            "件数の合計の検算": (f"3 値 {sum(sanchi.values())} + 別枠 {sum(betsu.values())} = "
                          f"{sum(sanchi.values()) + sum(betsu.values())} / 分母 {len(t['kadai'])}。"
                          f"部品ごとの合計 {part_sum} / 対応の行数 {len(t['taiou'])}"),
            "_part_sum": part_sum, "判定部分の sha256": digest, "しないこと": SHINAI}


def _copy(t: dict) -> dict:
    return {k: [dict(r) for r in rows] for k, rows in t.items()}


def verify(t: dict[str, list[dict[str, str]]]) -> dict:
    base = judge(t)
    again = judge(t)
    rev = judge({k: list(reversed(rows)) for k, rows in t.items()})
    checks = {
        "二度走って同じ指紋": base["判定部分の sha256"] == again["判定部分の sha256"],
        "行順を入れ替えても同じ出力": json.dumps(rev, ensure_ascii=False, sort_keys=True)
        == json.dumps(base, ensure_ascii=False, sort_keys=True),
        "3 値 + 別枠 = 詰まり方の件数、部品ごとの合計 = 対応の行数":
            sum(base["3 値"].values()) + sum(base["別枠"].values()) == base["分母(詰まり方の行数)"]
            and base["_part_sum"] == base["対応の行数"],
    }
    note = {}

    def kmap(res: dict) -> dict:
        return {json.dumps([r["詰まり方 id"], r["出典"], r["説明"]], ensure_ascii=False): r for r in res["詰まり方ごと"]}

    def pmap(res: dict) -> dict:
        return {p["部品 id"]: p for p in res["部品ごと"]}

    def moved(a: dict, b: dict) -> tuple[set, set]:
        ka, kb, pa, pb = kmap(a), kmap(b), pmap(a), pmap(b)
        return ({json.loads(k)[0] for k in ka if ka[k] != kb.get(k)}, {k for k in pa if pa[k] != pb.get(k)})

    valid = sorted((r for r in t["taiou"]), key=lambda r: (r["詰まり方 id"].strip(), r["部品 id"].strip(),
                                                         json.dumps(r, ensure_ascii=False, sort_keys=True)))
    ok_ids = {r["詰まり方 id"] for r in base["詰まり方ごと"] if "3 値" in r}
    valid = [r for r in valid if r["詰まり方 id"].strip() in ok_ids]
    if valid:
        drop = valid[0]
        v = _copy(t)
        v["taiou"] = [r for r in v["taiou"] if r != drop] + [r for r in v["taiou"] if r == drop][1:]
        b2 = judge(v)
        ks, ps = moved(base, b2)
        checks["対応 1 行を消すと、その詰まり方と部品の行だけが動く"] = (
            ks <= {drop["詰まり方 id"].strip()} and ps <= {drop["部品 id"].strip()} and len(ks) + len(ps) >= 1)
        note["消した対応"] = f'{drop["詰まり方 id"].strip()} - {drop["部品 id"].strip()}'
    else:
        note["消した対応"] = "該当なし(別枠でない詰まり方に対応が無い)"
    cand = [p for p in base["部品ごと"] if p["線の記号"] == [LINE_IN] and not p["部品の行の別枠"]
            and p["対応の記載(近い語のみを除く)"] >= 1]
    if cand:
        p = cand[0]
        v = _copy(t)
        for r in v["buhin"]:
            if r["部品 id"].strip() == p["部品 id"]:
                r["線の記号"] = LINE_OUT
        b2 = judge(v)
        linked = {r["詰まり方 id"].strip() for r in t["taiou"] if r["部品 id"].strip() == p["部品 id"]}
        ka, kb = kmap(base), kmap(b2)
        ks, _ = moved(base, b2)
        okv = all(kb[k].get("3 値") in SANCHI[:2] for k in ka if json.loads(k)[0] in ks)
        kk = base["宣言の検算(件数だけ)"], b2["宣言の検算(件数だけ)"]
        checks["線の内の部品 1 つを線の外にすると、つながる詰まり方だけが (A)(B) の間で動き、検算が 1 部品分だけ変わる"] = (
            ks <= linked and okv and kk[1]["線の内と宣言された部品の数"] == kk[0]["線の内と宣言された部品の数"] - 1)
        note["線の外にした部品"] = p["部品 id"]
    else:
        note["線の外にした部品"] = "該当なし(対応の記載が在る線の内の部品が無い)"
    return {"ok": all(checks.values()), "検算": checks, "使ったもの": note,
            "判定部分の sha256": base["判定部分の sha256"]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "rows", "verify"):
        s = sub.add_parser(name)
        s.add_argument("tables", nargs=4, metavar="CSV", help="詰まり方 部品 対応 記号 の順")
    a = ap.parse_args(argv)
    try:
        t = read_all(a.tables)
        if a.cmd == "verify":
            res = verify(t)
            print(json.dumps(res, ensure_ascii=False, indent=1))
            return 0 if res["ok"] else 3
        res = judge(t)
        res.pop("_part_sum")
        if a.cmd == "rows":
            w = csv.writer(sys.stdout, lineterminator="\n")
            w.writerow(["詰まり方 id", "3 値または別枠", "線の内の部品", "線の外の部品", "近い語のみ", "該当本数(文字列のまま)", "出典"])
            for r in res["詰まり方ごと"]:
                def ids(key: str) -> str:
                    return " / ".join(f'{x["部品 id"]}({x["部品の側の出典"]})' for x in r.get(key, []))
                w.writerow([r["詰まり方 id"], r.get("3 値") or r["別枠"], ids("線の内の部品"), ids("線の外の部品"),
                            ids("近い語のみ(数えない)"), r["該当本数(文字列のまま)"], r["出典"]])
            return 0
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0
    except ShapeError as e:
        print(json.dumps({"ok": False, "表の形の誤り": str(e)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
