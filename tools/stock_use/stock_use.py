"""stock_use — 置き場に取ってきた原本の本数と、後の文書でそれが使われたと書かれた記載を、人が台帳に書いた分だけで並べる。

読むのは渡された 4 枚の表(置き場の台帳 / 記載の台帳 / 記号の登録表 / 対の登録表)だけ。
フォルダの実物を数えない(ディレクトリを読む経路が無い)、ファイル名から使い道を当てない、差がどのファイルかを推し当てない、
消してよいか・要らないかを決めない、滞留の理由を当てない(理由の欄が無い)、利用率・合計の 1 値を出さない、
「多い」「少ない」の語を出さない(出力は件数だけ)、ネットワークに出ない、時計を読まない、入力を書き換えない、float を使わない。
補助の語数え(words)は literal 一致の件数を返すだけで、判定には使わない。
標準ライブラリのみ(csv / json / hashlib / argparse)。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys

ORDER = ("okiba", "kisai", "kigou", "tsui")
COLS = {
    "okiba": ("置き場 id", "種類", "取得の本数", "出典"),
    "kisai": ("記載 id", "記号", "名指された数", "後の側の文字列", "出典"),
    "kigou": ("記号", "意味", "要求する欄", "出典"),
    "tsui": ("記載 id", "置き場 id", "種類", "出典"),
}
SRC, CHK, MISHO, NEXT, NONE, IIKATA = ("出典の欄に在る", "検証の欄に在る", "未抽出の欄に在る", "次の作業の欄に在る",
                                       "読んだ範囲に記載なし", "置き場と書き手の言い方が違う")
SYMS = (SRC, CHK, MISHO, NEXT, NONE, IIKATA)
USED = (SRC, CHK)
LATER = (MISHO, NEXT)
REQ_OK = ("名指された数", "後の側の文字列", "出典")
GOCHI = (
    "(A) 使われた記載が在り、本数と名指された数が一致",
    "(B) 使われた記載が在り、本数と名指された数が一致しない",
    "(C) 使われた記載は在るが、比べる数が片側に無い",
    "(D) 未抽出か次の作業の欄にだけ記載が在る",
    "(E) 読んだ範囲に記載なし",
)
BETSU = (
    "出典が空",
    "取得の本数が整数でない",
    "台帳に無い id を指す対",
    "登録表に無い記号",
    "id の重複",
    "同じ種類に (A)(B) と (E) が同時に書かれた",
)
SHINAI = {
    "フォルダを数えない": "ディレクトリを読む経路が無い。本数は人が台帳に書いた数だけ",
    "ファイル名から当てない": "どのファイルが何に使われたかを名前から当てる経路が無い。対は人が書く",
    "差のファイルを当てない": "差は整数で返すだけ。どのファイルが差かの欄が無い",
    "消すかを決めない": "消してよい・要らない、の欄が無い",
    "理由を当てない": "滞留の理由の欄が無い",
    "1 値に丸めない": "置き場ごとに返すのは 5 値の内訳だけ。利用率・合計の 1 値・使っている / いない、の欄が無い",
    "量の語を出さない": "多い・少ない、とは書かない。出力は件数だけ",
    "取りに行かない": "ネットワークに出ない。原本を開かない。渡されたファイルの外を読まない。時計を読まない",
}


class ShapeError(ValueError):
    """表の形の誤り。1 件も判定しない(終了コード 2)。"""


def _blank(s: str | None) -> bool:
    return s is None or s.strip() == ""


def _int(s: str) -> int | None:
    s = s.strip()
    return int(s) if s.isdigit() and s.isascii() else None


def read_table(path: str) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def read_all(paths: list[str]) -> dict[str, list[dict[str, str]]]:
    if len(paths) != 4:
        raise ShapeError("表は 4 枚(置き場 記載 記号 対 の順)")
    return {k: read_table(p) for k, p in zip(ORDER, paths)}


def parse_lines(spec: str) -> tuple[int, int] | None:
    """「1-150」の形だけを読む。空なら全行。"""
    if _blank(spec):
        return None
    a, sep, b = spec.strip().partition("-")
    if not (a.strip().isdigit() and sep and b.strip().isdigit()) or int(b) < int(a):
        raise ShapeError(f"行の範囲は「1-150」の形で書く: {spec}")
    return int(a), int(b)


def _shape(t: dict[str, list[dict[str, str]]]) -> dict[str, tuple[str, ...]]:
    for k in ORDER:
        for i, r in enumerate(t[k], 1):
            miss = [c for c in COLS[k] if c not in r or r[c] is None]
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
            raise ShapeError(f"要求する欄に書けるのは記載の台帳の欄だけ: {bad}")
        req[s] = cols
    if any(_blank(r["置き場 id"]) or _blank(r["種類"]) for r in t["okiba"]):
        raise ShapeError("置き場の台帳に置き場 id か種類が空の行")
    for r in t["kisai"]:
        if _blank(r["記載 id"]):
            raise ShapeError("記載の台帳に記載 id が空の行")
        if not _blank(r["名指された数"]) and _int(r["名指された数"]) is None:
            raise ShapeError(f"名指された数は整数だけ: {r['名指された数']}")
    if any(_blank(r["記載 id"]) for r in t["tsui"]):
        raise ShapeError("対の登録表に記載 id が空の行")
    return req


def _key(r: dict) -> tuple[str, str]:
    return (r["置き場 id"].strip(), r["種類"].strip())


def _dump(x: object) -> str:
    return json.dumps(x, ensure_ascii=False, sort_keys=True)


def _first(reasons: set[str]) -> str | None:
    return next((b for b in BETSU if b in reasons), None)


def judge(t: dict[str, list[dict[str, str]]]) -> dict:
    req = _shape(t)
    keys = [_key(r) for r in t["okiba"]]
    kn = {k: keys.count(k) for k in keys}
    kid = [r["記載 id"].strip() for r in t["kisai"]]
    kisai: dict[str, list[dict]] = {}
    for r in t["kisai"]:
        kisai.setdefault(r["記載 id"].strip(), []).append(r)
    tsui_by_key: dict[tuple[str, str], list[dict]] = {}
    stray = []
    for r in t["tsui"]:
        k = _key(r)
        if k in kn:
            tsui_by_key.setdefault(k, []).append(r)
        else:
            stray.append(r)
    used_kinds: dict[str, set] = {}
    for r in t["tsui"]:
        used_kinds.setdefault(r["記載 id"].strip(), set()).add(_key(r))

    def view(x: dict) -> dict:
        return {"記載 id": x["記載 id"].strip(), "記号": x["記号"].strip(), "名指された数": x["名指された数"].strip(),
                "後の側の文字列": x["後の側の文字列"], "出典": x["出典"]}

    rows = []
    for r in t["okiba"]:
        k = _key(r)
        pairs = sorted(tsui_by_key.get(k, []), key=_dump)
        reasons: set[str] = set()
        if _blank(r["出典"]):
            reasons.add(BETSU[0])
        if not _blank(r["取得の本数"]) and _int(r["取得の本数"]) is None:
            reasons.add(BETSU[1])
        if kn[k] > 1:
            reasons.add(BETSU[4])
        mine = []
        for p in pairs:
            i = p["記載 id"].strip()
            if _blank(p["出典"]):
                reasons.add(BETSU[0])
            if i not in kisai:
                reasons.add(BETSU[2])
                continue
            if kid.count(i) > 1 or len(used_kinds[i]) > 1:
                reasons.add(BETSU[4])
            for x in kisai[i]:
                sym = x["記号"].strip()
                if _blank(x["出典"]) or (sym in req and any(_blank(x[c]) for c in req[sym])):
                    reasons.add(BETSU[0])
                if sym not in req:
                    reasons.add(BETSU[3])
                mine.append(x)
        mine.sort(key=_dump)
        syms = {x["記号"].strip() for x in mine}
        if syms & set(USED) and NONE in syms:
            reasons.add(BETSU[5])
        row = {"置き場 id": k[0], "種類": k[1], "取得の本数": r["取得の本数"].strip(), "置き場の出典": r["出典"]}
        why = _first(reasons)
        if why:
            row["別枠"] = why
            rows.append(row)
            continue
        used = [x for x in mine if x["記号"].strip() in USED]
        later = [x for x in mine if x["記号"].strip() in LATER]
        if used:
            named = sorted({_int(x["名指された数"]) for x in used if not _blank(x["名指された数"])})
            have = _int(r["取得の本数"]) if not _blank(r["取得の本数"]) else None
            if have is None or len(named) != 1:
                row["5 値"] = GOCHI[2]
                row["比べない訳"] = ("取得の本数が空" if have is None else
                                "名指された数が無い" if not named else "名指された数が記載ごとに違う")
            elif have == named[0]:
                row["5 値"] = GOCHI[0]
            else:
                row["5 値"] = GOCHI[1]
                row["差(取得の本数 − 名指された数)"] = have - named[0]
            row["名指された数"] = named
        elif later:
            row["5 値"] = GOCHI[3]
        else:
            row["5 値"] = GOCHI[4]
        row["使われた記載"] = [view(x) for x in used]
        row["未抽出・次の作業の記載"] = [view(x) for x in later]
        row["記載なしと書いた行"] = [view(x) for x in mine if x["記号"].strip() == NONE]
        row["言い方の違い(区分に効かせない)"] = [view(x) for x in mine if x["記号"].strip() == IIKATA]
        rows.append(row)
    order = {v: n for n, v in enumerate(GOCHI + BETSU)}
    rows.sort(key=lambda r: (r["置き場 id"], r["種類"], order[r.get("5 値") or r["別枠"]], _dump(r)))

    per = []
    for o in sorted({r["置き場 id"] for r in rows}):
        mine_r = [r for r in rows if r["置き場 id"] == o]
        uchi = {v: sum(1 for r in mine_r if r.get("5 値") == v) for v in GOCHI}
        uchi["別枠"] = sum(1 for r in mine_r if "別枠" in r)
        per.append({"置き場 id": o, "種類の数": len(mine_r), "内訳": uchi})

    attached = {r["記載 id"].strip() for r in t["tsui"] if _key(r) in kn}
    loose = sorted({i for i in kid if i not in attached})
    gochi = {v: sum(1 for r in rows if r.get("5 値") == v) for v in GOCHI}
    betsu = {v: sum(1 for r in rows if r.get("別枠") == v) for v in BETSU}
    core = {"5 値": gochi, "別枠": betsu, "置き場の種類ごと": rows, "置き場ごと": per,
            "どの種類にも当てていない記載": [{"記載 id": i, "記号": " / ".join(sorted({x["記号"].strip() for x in kisai[i]}))}
                                          for i in loose],
            "台帳に無い置き場を指す対": len(stray)}
    digest = hashlib.sha256(_dump(core).encode("utf-8")).hexdigest()
    n = len(t["okiba"])
    return {"ok": True, "分母(置き場の種類の行数)": n, "記載の行数": len(t["kisai"]), **core,
            "件数の合計の検算": (f"5 値 {sum(gochi.values())} + 別枠 {sum(betsu.values())} = "
                          f"{sum(gochi.values()) + sum(betsu.values())} / 分母 {n}。"
                          f"置き場ごとの内訳の合計 {sum(sum(p['内訳'].values()) for p in per)} / 分母 {n}"),
            "判定部分の sha256": digest, "しないこと": SHINAI}


def count_words(text: str, words: list[str], span: tuple[int, int] | None = None) -> dict:
    """補助。語が指定した行の範囲の何行目に何回出るかを literal 一致で数える。判定には使わない。0 件を (E) に入れない。"""
    lines = text.splitlines()
    lo, hi = span if span else (1, len(lines))
    out = {}
    for w in words:
        hits = [[i, ln.count(w)] for i, ln in enumerate(lines, 1) if lo <= i <= hi and w and w in ln]
        out[w] = {"件数": sum(c for _, c in hits), "行と回数": hits}
    return {"読んだ範囲": f"{lo}-{hi}", "語": out,
            "読み方": "literal 一致の件数だけ。判定(5 値)には使わない。0 件でも (E) に自動では入れない"}


def _copy(t: dict) -> dict:
    return {k: [dict(r) for r in rows] for k, rows in t.items()}


def verify(t: dict[str, list[dict[str, str]]]) -> dict:
    base = judge(t)
    again = judge(t)
    rev_k = _copy(t)
    rev_k["kisai"] = list(reversed(rev_k["kisai"]))
    rev = judge(rev_k)
    per_ok = all(sum(p["内訳"].values()) == p["種類の数"] for p in base["置き場ごと"])
    checks = {
        "二度走って同じ指紋": base["判定部分の sha256"] == again["判定部分の sha256"],
        "記載の台帳の行順を入れ替えても同じ出力": _dump(rev) == _dump(base),
        "5 値 + 別枠 = 置き場の種類の件数、置き場ごとの内訳の合計 = その置き場の種類の数":
            sum(base["5 値"].values()) + sum(base["別枠"].values()) == base["分母(置き場の種類の行数)"] and per_ok,
    }
    note = {}

    def kmap(res: dict) -> dict:
        return {(r["置き場 id"], r["種類"]): r for r in res["置き場の種類ごと"]}

    by = kmap(base)
    one = sorted(k for k, r in by.items() if r.get("5 値") in GOCHI[:4]
                 and len(r["使われた記載"]) + len(r["未抽出・次の作業の記載"]) + len(r["記載なしと書いた行"])
                 + len(r["言い方の違い(区分に効かせない)"]) == 1)
    if one:
        k = one[0]
        r0 = by[k]
        x = (r0["使われた記載"] + r0["未抽出・次の作業の記載"])[0]
        v = _copy(t)
        v["kisai"] = [y for y in v["kisai"] if y["記載 id"].strip() != x["記載 id"]]
        v["tsui"] = [y for y in v["tsui"] if y["記載 id"].strip() != x["記載 id"]]
        b2 = kmap(judge(v))
        checks["記載 1 行を消すと、その種類だけが動き他は変わらない"] = (
            all(b2[kk] == rr for kk, rr in by.items() if kk != k) and b2[k] != r0)
        note["消した記載"] = f'{x["記載 id"]}({k[0]} / {k[1]}: {r0["5 値"][:3]} → {b2[k].get("5 値", b2[k].get("別枠"))[:3]})'
    else:
        note["消した記載"] = "該当なし(記載がちょうど 1 行で (A)〜(D) の種類が無い)"
    a_k = sorted(k for k, r in by.items() if r.get("5 値") == GOCHI[0])
    if a_k:
        k = a_k[0]
        v = _copy(t)
        src = next(y for y in v["okiba"] if _key(y) == k)
        src["取得の本数"] = str(int(src["取得の本数"].strip()) + 1)
        b2 = kmap(judge(v))
        moved = b2[k]
        checks["取得の本数を 1 増やすと、その種類だけが (A) から (B) へ動き差が 1 になる"] = (
            all(b2[kk] == rr for kk, rr in by.items() if kk != k)
            and moved.get("5 値") == GOCHI[1] and moved.get("差(取得の本数 − 名指された数)") == 1)
        note["本数を増やした種類"] = f"{k[0]} / {k[1]}"
    else:
        note["本数を増やした種類"] = "該当なし((A) の種類が無い)"
    return {"ok": all(checks.values()), "検算": checks, "使ったもの": note,
            "判定部分の sha256": base["判定部分の sha256"]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "rows", "verify"):
        s = sub.add_parser(name)
        s.add_argument("tables", nargs=4, metavar="CSV", help="置き場 記載 記号 対 の順")
    w = sub.add_parser("words")
    w.add_argument("text", help="後の文書(UTF-8 のテキスト)")
    w.add_argument("word", nargs="+")
    w.add_argument("--lines", default="", help="数える行の範囲(例 1-150)。空なら全行")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "words":
            with open(a.text, encoding="utf-8-sig") as f:
                print(json.dumps(count_words(f.read(), a.word, parse_lines(a.lines)), ensure_ascii=False, indent=1))
            return 0
        t = read_all(a.tables)
        if a.cmd == "verify":
            res = verify(t)
            print(json.dumps(res, ensure_ascii=False, indent=1))
            return 0 if res["ok"] else 3
        res = judge(t)
        if a.cmd == "rows":
            cw = csv.writer(sys.stdout, lineterminator="\n")
            cw.writerow(["置き場 id", "種類", "取得の本数", "名指された数", "5 値または別枠", "差",
                         "使われた記載", "未抽出・次の作業の記載", "言い方の違い"])
            for r in res["置き場の種類ごと"]:
                cw.writerow([r["置き場 id"], r["種類"], r["取得の本数"],
                             " / ".join(str(n) for n in r.get("名指された数", [])),
                             (r.get("5 値") or r["別枠"]), r.get("差(取得の本数 − 名指された数)", ""),
                             " / ".join(x["記載 id"] for x in r.get("使われた記載", [])),
                             " / ".join(x["記載 id"] for x in r.get("未抽出・次の作業の記載", [])),
                             " / ".join(x["記載 id"] for x in r.get("言い方の違い(区分に効かせない)", []))])
            return 0
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0
    except ShapeError as e:
        print(json.dumps({"ok": False, "表の形の誤り": str(e)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
