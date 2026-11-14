"""recall_tally — 同じ項目について 2 つの経路に書かれた数を、単位をそろえてから横に並べる。

読むのは渡された 4 枚の表(経路の登録表 / 数の台帳 / 単位の記号の登録表 / 対の台帳)だけ。
ネットワークに出ない、ディスクを歩かない、値を取りに行かない、数の文字列から単位を読み取らない、
単位を換算しない、概数の印を落として比べない、どちらの経路が正しいかを決めない、原因を言い当てない、
一致率の 1 値を返さない、時計を読まない。標準ライブラリのみ(csv / json / hashlib / argparse)。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys

ORDER = ("routes", "counts", "units", "pairs")
COLS = {
    "routes": ("経路 id", "経路の素性", "出典"),
    "counts": ("数 id", "経路 id", "項目 id", "数の文字列", "単位の記号", "概数の印", "数え方の記載", "出典"),
    "units": ("記号", "意味", "出典"),
    "pairs": ("項目 id", "経路 1 の数 id", "経路 2 の数 id", "根拠", "出典"),
}
KUBUN = (
    "(A) 単位が同じで、数の文字列が一致",
    "(B) 単位が同じで、整数の形で、一致しない",
    "(C) 単位の記号が違う",
    "(D) 片側にしか数が無い",
    "(E) どちらかに概数の印が在る",
)
BETSU = (
    "出典が空",
    "単位の記号が登録表に無い",
    "数 id が重複",
    "対の台帳の数 id が数の台帳に無い",
    "対の両側が同じ経路",
    "(B) に入るはずの数の文字列が整数の形でない",
)
APPROX = ("在る", "無い")
NO_NUM = "数の記載なし"
NO_HOW = "数え方の記載なし"
INT_FORM = re.compile(r"[0-9]+")   # 半角の数字だけ。桁区切り・小数・範囲・全角は整数の形と見ない
SPACE = re.compile(r"[ 　\t]")
SHINAI = {
    "ネットワークに出ない": "値を取りに行く経路が無い。原本を開いて数え直すのは人の仕事",
    "単位を読み取らない": "単位は台帳の欄で受ける。数の文字列の中の「等級」「%」は読まない",
    "単位を換算しない": "行を年度の数で割る、のような経路が無い。単位が違う対は比べずに並べる",
    "概数の印を落とさない": "印が在る数は比べない。印を外して引き算に入れる経路が無い",
    "どちらが正しいかを決めない": "正しい側の欄・順位・点数・一致率の 1 値が無い。差の符号は「経路 2 − 経路 1」と決めてあるだけ",
    "原因を言い当てない": "原因の欄が無い。違いは「定義が違う可能性」として人が読む",
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
        raise ShapeError("表は 4 枚(routes counts units pairs の順)")
    return {k: read_table(p) for k, p in zip(ORDER, paths)}


def _shape(t: dict[str, list[dict[str, str]]]) -> None:
    for k in ORDER:
        for i, r in enumerate(t[k], 1):
            miss = [c for c in COLS[k] if c not in r]
            if miss:
                raise ShapeError(f"{k} の {i} 行目に列が無い: {miss}")
    rid = [r["経路 id"].strip() for r in t["routes"]]
    if any(x == "" for x in rid) or len(set(rid)) != len(rid):
        raise ShapeError("経路 id が空か重複")
    uk = [r["記号"].strip() for r in t["units"]]
    if any(x == "" for x in uk) or len(set(uk)) != len(uk):
        raise ShapeError("単位の記号の登録表に空か重複")
    for r in t["counts"]:
        if _blank(r["数 id"]) or _blank(r["項目 id"]):
            raise ShapeError("数の台帳に数 id か項目 id が空の行")
        if r["経路 id"].strip() not in rid:
            raise ShapeError(f"数の台帳の経路 id が経路の登録表に無い: {r['経路 id']}")
        if r["概数の印"].strip() not in APPROX:
            raise ShapeError(f"概数の印は「在る」か「無い」: {r['概数の印']}")
    for r in t["pairs"]:
        if _blank(r["項目 id"]):
            raise ShapeError("対の台帳に項目 id が空の行")
        if _blank(r["経路 1 の数 id"]) and _blank(r["経路 2 の数 id"]):
            raise ShapeError(f"対の両側の数 id が空: {r['項目 id']}")


def same_string(a: str, b: str) -> bool:
    """空白(半角・全角・タブ)だけを除き、残りを 1 文字ずつ比べる。"""
    return SPACE.sub("", a) == SPACE.sub("", b)


def int_form(s: str) -> bool:
    return INT_FORM.fullmatch(SPACE.sub("", s)) is not None


def _as_int(s: str) -> int:
    return int(SPACE.sub("", s))


def _judge_pair(p: dict[str, str], index: dict[str, list[dict[str, str]]], units: set[str]) -> dict:
    ids = [p["経路 1 の数 id"].strip(), p["経路 2 の数 id"].strip()]
    sides = [index.get(i, []) if i else [] for i in ids]
    found = [s[0] if len(s) == 1 else None for s in sides]   # 重複した数 id はどの行とも決めない(行順に依らない)
    every = [r for s in sides for r in s]
    row = {"項目 id": p["項目 id"].strip(), "経路 1 の数 id": ids[0] or "", "経路 2 の数 id": ids[1] or "",
           "根拠": p["根拠"], "対の出典": p["出典"]}
    for n, (i, f) in enumerate(zip(ids, found), 1):
        row[f"経路 {n}"] = ({"経路 id": f["経路 id"].strip(), "数の文字列": f["数の文字列"] if not _blank(f["数の文字列"]) else NO_NUM,
                            "単位の記号": f["単位の記号"].strip(), "概数の印": f["概数の印"].strip(), "出典": f["出典"]}
                           if f else {"数の文字列": NO_NUM if not i else "数 id が重複" if i in index else "数の台帳に無い"})
    used = [f for f in found if f]
    # 別枠(手前が勝つ)
    reason = None
    if _blank(p["出典"]) or any(_blank(f["出典"]) for f in every):
        reason = BETSU[0]
    elif any(f["単位の記号"].strip() not in units for f in every):
        reason = BETSU[1]
    elif any(i and len(index.get(i, [])) > 1 for i in ids):
        reason = BETSU[2]
    elif any(i and i not in index for i in ids):
        reason = BETSU[3]
    elif len(used) == 2 and used[0]["経路 id"].strip() == used[1]["経路 id"].strip():
        reason = BETSU[4]
    if reason:
        row["別枠"] = reason
        return row
    if len(used) < 2 or any(_blank(f["数の文字列"]) for f in used):
        row["区分"] = KUBUN[3]
        return row
    a, b = used
    if "在る" in (a["概数の印"].strip(), b["概数の印"].strip()):
        row["区分"] = KUBUN[4]
    elif a["単位の記号"].strip() != b["単位の記号"].strip():
        row["区分"] = KUBUN[2]
    elif same_string(a["数の文字列"], b["数の文字列"]):
        row["区分"] = KUBUN[0]
    elif int_form(a["数の文字列"]) and int_form(b["数の文字列"]):
        row["区分"] = KUBUN[1]
        row["差(経路 2 − 経路 1)"] = _as_int(b["数の文字列"]) - _as_int(a["数の文字列"])
    else:
        row["別枠"] = BETSU[5]
    return row


def judge(t: dict[str, list[dict[str, str]]]) -> dict:
    _shape(t)
    units = {r["記号"].strip() for r in t["units"]}
    index: dict[str, list[dict[str, str]]] = {}
    for r in t["counts"]:
        index.setdefault(r["数 id"].strip(), []).append(r)
    rows = [_judge_pair(p, index, units) for p in t["pairs"]]
    order = {k: n for n, k in enumerate(KUBUN + BETSU)}
    rows.sort(key=lambda r: (order[r.get("区分") or r["別枠"]], r["項目 id"], r["経路 1 の数 id"], r["経路 2 の数 id"],
                             json.dumps(r, ensure_ascii=False, sort_keys=True)))   # 残りの欄まで見て行順に依らない
    kubun = {k: sum(1 for r in rows if r.get("区分") == k) for k in KUBUN}
    betsu = {k: sum(1 for r in rows if r.get("別枠") == k) for k in BETSU}
    in_pair = {i for r in rows for i in (r["経路 1 の数 id"], r["経路 2 の数 id"]) if i}
    items: dict[str, list[dict]] = {}
    for r in sorted(t["counts"], key=lambda r: tuple(r[c] for c in ("項目 id", "数 id", "経路 id", "数の文字列", "単位の記号", "概数の印", "数え方の記載", "出典"))):
        items.setdefault(r["項目 id"].strip(), []).append(
            {"数 id": r["数 id"].strip(), "経路 id": r["経路 id"].strip(),
             "数の文字列": r["数の文字列"] if not _blank(r["数の文字列"]) else NO_NUM,
             "単位の記号": r["単位の記号"].strip(), "概数の印": r["概数の印"].strip(),
             "数え方の記載": r["数え方の記載"] if not _blank(r["数え方の記載"]) else NO_HOW,
             "出典": r["出典"], "対": "対の中" if r["数 id"].strip() in in_pair else "対の外"})
    per_item = [{"項目 id": k, "数の件数": len(v), "数": v} for k, v in sorted(items.items())]
    per_route = []
    for rt in sorted(t["routes"], key=lambda r: r["経路 id"].strip()):
        mine = [c for c in t["counts"] if c["経路 id"].strip() == rt["経路 id"].strip()]
        uc: dict[str, int] = {}
        for c in mine:
            uc[c["単位の記号"].strip()] = uc.get(c["単位の記号"].strip(), 0) + 1
        per_route.append({"経路 id": rt["経路 id"].strip(), "経路の素性": rt["経路の素性"], "出典": rt["出典"],
                          "数の件数": len(mine), "単位の記号ごと": dict(sorted(uc.items())),
                          "数え方の記載が空": sum(1 for c in mine if _blank(c["数え方の記載"]))})
    core = {"区分": kubun, "別枠": betsu, "対ごと": rows, "項目ごと": per_item, "経路ごと": per_route}
    digest = hashlib.sha256(json.dumps(core, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    total = sum(kubun.values()) + sum(betsu.values())
    return {"ok": True, "分母(対の件数)": len(t["pairs"]), **core,
            "対の外の数の件数": sum(1 for v in items.values() for c in v if c["対"] == "対の外"),
            "件数の合計の検算": f"区分 {sum(kubun.values())} + 別枠 {sum(betsu.values())} = {total} / 分母 {len(t['pairs'])}",
            "判定部分の sha256": digest, "しないこと": SHINAI}


def count_table_rows(text: str, sep: str = "|", head: int = 2) -> dict:
    """表の行を節ごとに数える。見出し(# で始まる行)で節を切り、sep で始まる連続した行を 1 つの表とし、
    表ごとに先頭 head 行を除いた行を数える。行の中身は読まない・重複を除かない。"""
    if head < 0 or sep == "":
        raise ShapeError("区切りの文字が空か、見出しの行数が負")
    sections: list[list] = [["(見出しの前)", 0, 0]]
    block = 0

    def close() -> None:
        nonlocal block
        if block:
            sections[-1][1] += max(0, block - head)
            sections[-1][2] += 1
        block = 0

    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            close()
            sections.append([s.lstrip("#").strip(), 0, 0])
        elif s.startswith(sep):
            block += 1
        else:
            close()
    close()
    out = [{"節": n, "表の数": k, "表の行の数": c} for n, c, k in sections if k]
    return {"節ごと": out, "表の行の数の合計": sum(x["表の行の数"] for x in out),
            "読み方": "表の行の数。rule の数だとは言っていない(1 行に 2 つの rule が書かれていても 1 と数える)"}


def _variant(t: dict, key: str, cid: str, col: str, value: str) -> dict:
    v = {k: [dict(r) for r in rows] for k, rows in t.items()}
    for r in v[key]:
        if r["数 id"].strip() == cid:
            r[col] = value
    return v


def verify(t: dict[str, list[dict[str, str]]]) -> dict:
    base = judge(t)
    again = judge(t)
    rev = judge({k: list(reversed(rows)) for k, rows in t.items()})
    checks = {"二度走って同じ指紋": base["判定部分の sha256"] == again["判定部分の sha256"],
              "行順を入れ替えても同じ出力": json.dumps(rev, ensure_ascii=False, sort_keys=True)
              == json.dumps(base, ensure_ascii=False, sort_keys=True),
              "区分 + 別枠 = 対の件数": sum(base["区分"].values()) + sum(base["別枠"].values()) == base["分母(対の件数)"]}

    def key(r: dict) -> tuple:
        return (r["項目 id"], r["経路 1 の数 id"], r["経路 2 の数 id"])

    def moved(a: dict, b: dict) -> list[tuple]:
        da = {key(r): r for r in a["対ごと"]}
        return [k for k, r in ((key(r), r) for r in b["対ごと"]) if r != da.get(k)]

    note = {}
    cand = [r for r in base["対ごと"] if r.get("区分") == KUBUN[0] and r["経路 2 の数 id"]
            and int_form(r["経路 2"]["数の文字列"]) and int_form(r["経路 1"]["数の文字列"])]
    if cand:
        r = cand[0]
        new = str(_as_int(r["経路 2"]["数の文字列"]) + 1)
        b2 = judge(_variant(t, "counts", r["経路 2 の数 id"], "数の文字列", new))
        hit = {key(x): x for x in b2["対ごと"]}[key(r)]
        checks["(A) の片側を 1 だけ替えると、その対だけ (B) へ動き差が 1"] = (
            moved(base, b2) == [key(r)] and hit.get("区分") == KUBUN[1] and hit.get("差(経路 2 − 経路 1)") == 1)
        note["(A) → (B) に使った対"] = r["項目 id"]
    else:
        note["(A) → (B) に使った対"] = "該当する対なし(整数の形の (A) が無い)"
    cand = [r for r in base["対ごと"] if r.get("区分") == KUBUN[1]]
    others = sorted({u["記号"].strip() for u in t["units"]})
    if cand:
        r = cand[0]
        cur = r["経路 2"]["単位の記号"]
        new = [u for u in others if u != cur][0]
        b2 = judge(_variant(t, "counts", r["経路 2 の数 id"], "単位の記号", new))
        hit = {key(x): x for x in b2["対ごと"]}[key(r)]
        checks["(B) の片側の単位を替えると、その対だけ (C) へ動き差の欄が消える"] = (
            moved(base, b2) == [key(r)] and hit.get("区分") == KUBUN[2] and "差(経路 2 − 経路 1)" not in hit)
        note["(B) → (C) に使った対"] = r["項目 id"]
    else:
        note["(B) → (C) に使った対"] = "該当する対なし((B) が無い)"
    return {"ok": all(checks.values()), "検算": checks, "使った対": note,
            "判定部分の sha256": base["判定部分の sha256"]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "rows", "verify"):
        s = sub.add_parser(name)
        s.add_argument("tables", nargs=4, metavar="CSV", help="routes counts units pairs の順")
    s = sub.add_parser("table-rows")
    s.add_argument("file")
    s.add_argument("--sep", default="|")
    s.add_argument("--head", type=int, default=2)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "table-rows":
            with open(a.file, encoding="utf-8-sig") as f:
                print(json.dumps(count_table_rows(f.read(), a.sep, a.head), ensure_ascii=False, indent=1))
            return 0
        t = read_all(a.tables)
        if a.cmd == "verify":
            res = verify(t)
            print(json.dumps(res, ensure_ascii=False, indent=1))
            return 0 if res["ok"] else 3
        res = judge(t)
        if a.cmd == "rows":
            w = csv.writer(sys.stdout, lineterminator="\n")
            w.writerow(["項目 id", "経路 1 の数", "経路 1 の単位", "経路 1 の出典", "経路 2 の数", "経路 2 の単位",
                        "経路 2 の出典", "区分または別枠", "差(経路 2 − 経路 1)"])
            for r in res["対ごと"]:
                s1, s2 = r["経路 1"], r["経路 2"]
                w.writerow([r["項目 id"], s1["数の文字列"], s1.get("単位の記号", ""), s1.get("出典", ""),
                            s2["数の文字列"], s2.get("単位の記号", ""), s2.get("出典", ""),
                            r.get("区分") or r["別枠"], r.get("差(経路 2 − 経路 1)", "")])
            return 0
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0
    except ShapeError as e:
        print(json.dumps({"ok": False, "表の形の誤り": str(e)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
