"""step_carry — 前の文書で宣言した「次の一歩」を約束の単位で、後の文書のどこに記載が在るかを、人が台帳に書いた記載だけで並べる。

読むのは渡された 4 枚の表(文書の登録表 / 約束の台帳 / 記載の台帳 / 記号の登録表)だけ。
文を約束に割らない(句読点や矢印で割る経路が無い)、語の似かたから記載を当てない(類似度・部分一致の経路が無い)、
項目を「済み / 未」の 1 値に丸めない、進み具合の率・完了率・合計の 1 値を出さない、理由を当てない、
どちらの文書が正しいかを決めない、記載なしを「やっていない」と言い換えない、ネットワークに出ない、
入力フォルダの外を読まない、時計を読まない、入力を書き換えない、float を使わない。
補助の語数え(words)は literal 一致の件数を返すだけで、判定には使わない。
標準ライブラリのみ(csv / json / hashlib / argparse)。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys

ORDER = ("bunsho", "yakusoku", "kisai", "kigou")
COLS = {
    "bunsho": ("文書 id", "時点", "次の候補の行", "出典"),
    "yakusoku": ("約束 id", "項目 id", "宣言の文字列", "宣言側の出典"),
    "kisai": ("約束 id", "後の文書 id", "記号", "後の側の行", "後の側の出典", "後の側の文字列"),
    "kigou": ("記号", "意味", "要求する欄", "出典"),
}
DONE, NEXT, WAIT, ELSE, NONE, NEAR = ("済みの記載", "次の候補に在る", "判断待ちに在る", "別の欄に在る",
                                      "読んだ範囲に記載なし", "近い語のみ")
SYMS = (DONE, NEXT, WAIT, ELSE, NONE, NEAR)
REQ_OK = ("後の側の行", "後の側の出典", "後の側の文字列")
YONCHI = (
    "(A) 後の文書に済みの記載が在る",
    "(B) 後の文書の次の候補か判断待ちに在る",
    "(C) 後の文書の別の欄に在る",
    "(D) 読んだ範囲に記載なし",
)
TO_VAL = {DONE: YONCHI[0], NEXT: YONCHI[1], WAIT: YONCHI[1], ELSE: YONCHI[2], NONE: YONCHI[3]}
BETSU = (
    "出典が空",
    "宣言の文字列が空",
    "台帳に無い id を指す記載",
    "登録表に無い記号",
    "id の重複",
    "同じ約束に (A) と (D) が同時に書かれた",
)
SHINAI = {
    "文を割らない": "1 項目を何個の約束に割るかは人が台帳に書く。句読点や矢印で割る経路が無い",
    "記載を当てない": "語の似かた・部分一致で記載を探す経路が無い。判定に使うのは人が台帳に書いた行だけ",
    "1 値に丸めない": "項目ごとに返すのは約束の内訳だけ。済み / 未、完了率、進み具合の率、合計の 1 値の欄が無い",
    "理由を当てない": "なぜ記載が無いかの欄が無い",
    "正しい側を決めない": "宣言と後の文書の言い方が違っても、どちらが正しいかの欄が無い",
    "言い換えない": "(D) は「読んだ範囲に記載なし」で固定。やっていない・放置、とは言わない",
    "取りに行かない": "ネットワークに出ない。原本やソースを開かない。渡されたファイルの外を読まない",
    "時計を読まない": "時点は文字列のまま写す。日付を出力に入れない",
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
        raise ShapeError("表は 4 枚(文書 約束 記載 記号 の順)")
    return {k: read_table(p) for k, p in zip(ORDER, paths)}


def parse_lines(spec: str) -> list[int]:
    """「137-143」「20-26,40」の形だけを読む。空なら候補の行は無い。"""
    out: list[int] = []
    for part in (p.strip() for p in spec.split(",")):
        if part == "":
            continue
        a, sep, b = part.partition("-")
        if not a.strip().isdigit() or (sep and not b.strip().isdigit()):
            raise ShapeError(f"次の候補の行は「137-143」の形で書く: {spec}")
        lo, hi = int(a), int(b) if sep else int(a)
        if hi < lo:
            raise ShapeError(f"次の候補の行の範囲が逆: {spec}")
        out.extend(range(lo, hi + 1))
    return sorted(set(out))


def _shape(t: dict[str, list[dict[str, str]]]) -> tuple[dict[str, tuple[str, ...]], dict[str, dict], dict[str, list[int]]]:
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
        if s not in SYMS:
            raise ShapeError(f"道具が意味を持たない記号は登録できない: {s}")
        cols = tuple(c.strip() for c in r["要求する欄"].split("/") if c.strip())
        bad = [c for c in cols if c not in REQ_OK]
        if bad:
            raise ShapeError(f"要求する欄に書けるのは後の側の欄だけ: {bad}")
        req[s] = cols
    did = [r["文書 id"].strip() for r in t["bunsho"]]
    if any(x == "" for x in did) or len(set(did)) != len(did):
        raise ShapeError("文書の登録表に空か重複の id")
    docs = {r["文書 id"].strip(): r for r in t["bunsho"]}
    cand = {d: parse_lines(r["次の候補の行"]) for d, r in docs.items()}
    if any(_blank(r["約束 id"]) for r in t["yakusoku"]):
        raise ShapeError("約束の台帳に約束 id が空の行")
    if any(_blank(r["項目 id"]) for r in t["yakusoku"]):
        raise ShapeError("約束の台帳に項目 id が空の行")
    for r in t["kisai"]:
        if _blank(r["約束 id"]):
            raise ShapeError("記載の台帳に約束 id が空の行")
        if not _blank(r["後の側の行"]) and not r["後の側の行"].strip().isdigit():
            raise ShapeError(f"後の側の行は数字だけ: {r['後の側の行']}")
    return req, docs, cand


def _first(reasons: set[str]) -> str | None:
    for b in BETSU:
        if b in reasons:
            return b
    return None


def _kkey(r: dict) -> str:
    return json.dumps(r, ensure_ascii=False, sort_keys=True)


def _lkey(r: dict) -> tuple:
    ln = r["後の側の行"].strip()
    return (r["後の文書 id"].strip(), int(ln) if ln.isdigit() else -1, _kkey(r))


def judge(t: dict[str, list[dict[str, str]]]) -> dict:
    req, docs, cand = _shape(t)
    yid = [r["約束 id"].strip() for r in t["yakusoku"]]
    yn = {x: yid.count(x) for x in yid}

    def kisai_reasons(r: dict) -> set[str]:
        s = set()
        sym = r["記号"].strip()
        d = r["後の文書 id"].strip()
        if _blank(r["後の側の出典"]) or (sym in req and any(_blank(r[c]) for c in req[sym])):
            s.add(BETSU[0])
        if d in docs and _blank(docs[d]["出典"]):
            s.add(BETSU[0])
        if d not in docs:
            s.add(BETSU[2])
        if sym not in req:
            s.add(BETSU[3])
        return s

    by_y: dict[str, list[dict]] = {}
    orphans = 0
    for r in t["kisai"]:
        y = r["約束 id"].strip()
        if y in yn:
            by_y.setdefault(y, []).append(r)
        else:
            orphans += 1

    def view(r: dict) -> dict:
        return {"記号": r["記号"].strip(), "後の文書 id": r["後の文書 id"].strip(), "後の側の行": r["後の側の行"].strip(),
                "後の側の出典": r["後の側の出典"], "後の側の文字列": r["後の側の文字列"]}

    rows = []
    for r in t["yakusoku"]:
        y = r["約束 id"].strip()
        mine = sorted(by_y.get(y, []), key=_lkey)
        reasons: set[str] = set()
        if _blank(r["宣言側の出典"]):
            reasons.add(BETSU[0])
        if _blank(r["宣言の文字列"]):
            reasons.add(BETSU[1])
        if yn[y] > 1:
            reasons.add(BETSU[4])
        for x in mine:
            reasons |= kisai_reasons(x)
        syms = {x["記号"].strip() for x in mine}
        if DONE in syms and NONE in syms:
            reasons.add(BETSU[5])
        row = {"約束 id": y, "項目 id": r["項目 id"].strip(), "宣言の文字列": r["宣言の文字列"],
               "宣言側の出典": r["宣言側の出典"]}
        why = _first(reasons)
        if why:
            row["別枠"] = why
            rows.append(row)
            continue
        counted = [x for x in mine if x["記号"].strip() in (DONE, NEXT, WAIT, ELSE)]
        vals = {TO_VAL[x["記号"].strip()] for x in counted}
        row["4 値"] = next((v for v in YONCHI[:3] if v in vals), YONCHI[3])
        row["記載"] = [view(x) for x in counted]
        row["記載なしと書いた行"] = [view(x) for x in mine if x["記号"].strip() == NONE]
        row["近い語のみ(数えない)"] = [view(x) for x in mine if x["記号"].strip() == NEAR]
        rows.append(row)
    order = {k: n for n, k in enumerate(YONCHI + BETSU)}
    rows.sort(key=lambda r: (r["項目 id"], r["約束 id"], order[r.get("4 値") or r["別枠"]], _kkey(r)))

    items = []
    for it in sorted({r["項目 id"] for r in rows}):
        mine = [r for r in rows if r["項目 id"] == it]
        uchi = {k: sum(1 for r in mine if r.get("4 値") == k) for k in YONCHI}
        uchi["別枠"] = sum(1 for r in mine if "別枠" in r)
        items.append({"項目 id": it, "約束の数": len(mine), "内訳": uchi,
                      "約束 id": [r["約束 id"] for r in mine]})

    carry = []
    for d in sorted(docs):
        if not cand[d]:
            continue
        used = {int(x["後の側の行"]) for x in t["kisai"]
                if x["後の文書 id"].strip() == d and x["約束 id"].strip() in yn
                and x["記号"].strip() in (DONE, NEXT, WAIT, ELSE) and not _blank(x["後の側の行"])}
        near = {int(x["後の側の行"]) for x in t["kisai"]
                if x["後の文書 id"].strip() == d and x["記号"].strip() == NEAR and not _blank(x["後の側の行"])}
        unused = [n for n in cand[d] if n not in used]
        carry.append({"後の文書 id": d, "時点(文字列のまま)": docs[d]["時点"], "次の候補の行数": len(cand[d]),
                      "どの約束の記載にも使われていない行": unused,
                      "使われていない行の数": len(unused),
                      "そのうち近い語のみで指された行": [n for n in unused if n in near],
                      "読み方": "新しく足された候補か、対応を書いていない候補かは決めない"})

    yon = {k: sum(1 for r in rows if r.get("4 値") == k) for k in YONCHI}
    betsu = {k: sum(1 for r in rows if r.get("別枠") == k) for k in BETSU}
    core = {"4 値": yon, "別枠": betsu, "約束ごと": rows, "項目ごと": items,
            "後の文書の次の候補": carry, "どの約束にも付かない記載": orphans}
    digest = hashlib.sha256(json.dumps(core, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    per_y = sum(len(by_y.get(y, [])) for y in yn)
    return {"ok": True, "分母(約束の行数)": len(t["yakusoku"]), "記載の行数": len(t["kisai"]), **core,
            "件数の合計の検算": (f"4 値 {sum(yon.values())} + 別枠 {sum(betsu.values())} = "
                          f"{sum(yon.values()) + sum(betsu.values())} / 分母 {len(t['yakusoku'])}。"
                          f"約束に付いた記載 {per_y} + 付かない記載 {orphans} = {per_y + orphans} / 記載の行数 {len(t['kisai'])}"),
            "判定部分の sha256": digest, "しないこと": SHINAI}


def count_words(text: str, words: list[str]) -> dict:
    """補助。語が何行目に何回出るかを literal 一致で数える。判定には使わない。0 件を (D) に入れない。"""
    lines = text.splitlines()
    out = {}
    for w in words:
        hits = [[i, ln.count(w)] for i, ln in enumerate(lines, 1) if w and w in ln]
        out[w] = {"件数": sum(c for _, c in hits), "行と回数": hits}
    return {"読んだ行数": len(lines), "語": out,
            "読み方": "literal 一致の件数だけ。判定(4 値)には使わない。0 件でも (D) に自動では入れない"}


def _copy(t: dict) -> dict:
    return {k: [dict(r) for r in rows] for k, rows in t.items()}


def verify(t: dict[str, list[dict[str, str]]]) -> dict:
    base = judge(t)
    again = judge(t)
    rev_k = _copy(t)
    rev_k["kisai"] = list(reversed(rev_k["kisai"]))
    rev = judge(rev_k)
    items_ok = all(sum(i["内訳"].values()) == i["約束の数"] for i in base["項目ごと"])
    checks = {
        "二度走って同じ指紋": base["判定部分の sha256"] == again["判定部分の sha256"],
        "記載の台帳の行順を入れ替えても同じ出力": json.dumps(rev, ensure_ascii=False, sort_keys=True)
        == json.dumps(base, ensure_ascii=False, sort_keys=True),
        "4 値 + 別枠 = 約束の件数、項目ごとの内訳の合計 = その項目の約束の数":
            sum(base["4 値"].values()) + sum(base["別枠"].values()) == base["分母(約束の行数)"] and items_ok,
    }
    note = {}

    def ymap(res: dict) -> dict:
        return {r["約束 id"]: r for r in res["約束ごと"]}

    by = ymap(base)
    one = sorted(y for y, r in by.items() if r.get("4 値") in YONCHI[:3] and len(r["記載"]) == 1)
    if one:
        y = one[0]
        drop = by[y]["記載"][0]
        v = _copy(t)
        idx = next(i for i, x in enumerate(v["kisai"]) if x["約束 id"].strip() == y and x["記号"].strip() == drop["記号"]
                   and x["後の側の行"].strip() == drop["後の側の行"] and x["後の側の出典"] == drop["後の側の出典"])
        del v["kisai"][idx]
        b2 = ymap(judge(v))
        others = all(b2[k] == r for k, r in by.items() if k != y)
        checks["記載 1 行を消すと、その約束だけが (A)〜(C) から (D) へ動く"] = others and b2[y]["4 値"] == YONCHI[3]
        note["消した記載"] = f'{y} - {drop["記号"]}(後の側の行 {drop["後の側の行"]})'
    else:
        note["消した記載"] = "該当なし(記載がちょうど 1 行で (A)〜(C) の約束が無い)"
    ok_y = sorted(y for y, r in by.items() if "4 値" in r)
    if ok_y:
        y = ok_y[0]
        parent = by[y]["項目 id"]
        v = _copy(t)
        src = next(r for r in v["yakusoku"] if r["約束 id"].strip() == y)
        v["yakusoku"].append({**src, "約束 id": y + "/割り直し"})
        b2 = judge(v)
        ia = {i["項目 id"]: i for i in base["項目ごと"]}
        ib = {i["項目 id"]: i for i in b2["項目ごと"]}
        checks["1 約束を 2 つに割り直すと、その親の項目の内訳だけが動く"] = (
            all(ib[k] == ia[k] for k in ia if k != parent) and ib[parent]["約束の数"] == ia[parent]["約束の数"] + 1)
        note["割り直した約束"] = y
    else:
        note["割り直した約束"] = "該当なし(別枠でない約束が無い)"
    return {"ok": all(checks.values()), "検算": checks, "使ったもの": note,
            "判定部分の sha256": base["判定部分の sha256"]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "rows", "verify"):
        s = sub.add_parser(name)
        s.add_argument("tables", nargs=4, metavar="CSV", help="文書 約束 記載 記号 の順")
    w = sub.add_parser("words")
    w.add_argument("text", help="後の文書(UTF-8 のテキスト)")
    w.add_argument("word", nargs="+")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "words":
            with open(a.text, encoding="utf-8-sig") as f:
                print(json.dumps(count_words(f.read(), a.word), ensure_ascii=False, indent=1))
            return 0
        t = read_all(a.tables)
        if a.cmd == "verify":
            res = verify(t)
            print(json.dumps(res, ensure_ascii=False, indent=1))
            return 0 if res["ok"] else 3
        res = judge(t)
        if a.cmd == "rows":
            cw = csv.writer(sys.stdout, lineterminator="\n")
            cw.writerow(["項目 id", "約束 id", "4 値または別枠", "後の側の行", "近い語のみの行", "宣言の文字列", "宣言側の出典"])
            for r in res["約束ごと"]:
                cw.writerow([r["項目 id"], r["約束 id"], r.get("4 値") or r["別枠"],
                             " / ".join(f'{x["後の文書 id"]} L{x["後の側の行"]}' for x in r.get("記載", [])),
                             " / ".join(f'{x["後の文書 id"]} L{x["後の側の行"]}' for x in r.get("近い語のみ(数えない)", [])),
                             r["宣言の文字列"], r["宣言側の出典"]])
            return 0
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0
    except ShapeError as e:
        print(json.dumps({"ok": False, "表の形の誤り": str(e)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
