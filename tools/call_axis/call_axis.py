"""call_axis — 式が呼べる語の一覧を、人が登録した働きの記号の軸で並べ直し、
式の一覧の側の記載と検証の表の側の記載を横に置く。

式を読まない・評価しない・走らせない。語の名前から働きを当てない。名前の似かたで記載と結び付けない。
記載が無い語を「未検証」「危険」と評価しない(「読んだ範囲に記載なし」とだけ返す)。

入力は 4 表(どの行にも出典の欄が要る):
  語の台帳       word_id, word, order, role, source     order = 旧軸(一覧に書かれた順)の整数
  働きの登録表   role, edge, source                     edge = 境目を持つ働きなら「境目」、そうでなければ空
  記載の台帳     note_id, side, text, result, source    side = 「式の一覧」か「検証の表」
  対の登録表     word_id, note_id, source               人が書いた対応だけ

使い方:
  python call_axis.py init <dir>
  python call_axis.py check 語.csv 働き.csv 記載.csv 対.csv [--doc 文書.md --label 文書の名前]
  python call_axis.py verify 語.csv 働き.csv 記載.csv 対.csv
終了コード: 0 = 並べた / 3 = 理由コードで止まった / 2 = 表として読めない
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

COLS = {
    "words": ["word_id", "word", "order", "role", "source"],
    "roles": ["role", "edge", "source"],
    "notes": ["note_id", "side", "text", "result", "source"],
    "pairs": ["word_id", "note_id", "source"],
}
NEED_ROWS = ("words", "roles")          # 0 行では読めない表(記載の台帳と対の登録表は 0 行でも読める)
SIDE_F, SIDE_V = "式の一覧", "検証の表"
SIDES = (SIDE_F, SIDE_V)
EDGE = "境目"
CLASSES = {
    "A": "(A) 式の側にも検証の側にも記載が在る",
    "B": "(B) 検証の側だけに記載が在る",
    "C": "(C) 式の側だけに記載が在る",
    "D": "(D) 読んだ範囲に記載なし",
}
BOXES = [
    "登録表に無い働きの記号",
    "働きの記号が空",
    "出典が空",
    "同じ語 id が 2 回",
    "対の登録表が台帳に無い記載を指す",
    "旧軸の順が重なる",
]
BOX_HEAD = "別枠: "
STOPS = {
    "ROLE_TABLE": "働きの登録表が崩れている(記号が空 / 同じ記号が 2 回 / 出典が空 / 境目の印が 2 値以外)",
    "NOTE_TABLE": "記載の台帳が崩れている(id が空か 2 回 / 側が 2 語以外 / 記載の文字列が空 / 出典が空)",
    "PAIR_TABLE": "対の登録表が崩れている(語 id・記載 id・出典のどれかが空)",
    "WORD_TABLE": "語の台帳が崩れている(語 id か語の文字列が空 / 旧軸の順が整数でない)",
}
MARK_EDGE = "境目を持つ働きなのに検証の側の記載が無い"
MARK_LITERAL = "語の文字列を literal に含まない記載と対になっている"
NOT_HELD = [
    "語の名前から働きを当てる経路(働きの記号は人が登録した分だけ)",
    "式の文字列を読んで、どの語を呼んでいるかを拾う経路",
    "式を評価する経路・走らせる経路",
    "名前の似かたで記載と結び付ける経路(対の登録表に書かれた行だけを使う)",
    "記載が無い語を「未検証」「危険」と評価する経路",
    "検証の結果の数が正しいかを返す経路",
    "語を足す・減らす提案",
    "通信、現在時刻、浮動小数点",
    "入力を書き換える経路",
]


class TableError(Exception):
    """表として読めない(列が違う / 行の欄の数が違う / 要る表が 0 行)。"""


def read_table(path: str | Path, kind: str) -> list[dict]:
    want = COLS[kind]
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            rd = csv.reader(f)
            head = next(rd, None)
            if head != want:
                raise TableError(f"{kind}: 列は {','.join(want)} の順で書く(読んだ列: {head})")
            rows = []
            for i, cells in enumerate(rd, 2):
                if len(cells) != len(want):
                    raise TableError(f"{kind}: 行 {i} の欄の数が {len(want)} でない")
                rows.append(dict(zip(want, cells)))
    except (OSError, UnicodeDecodeError, csv.Error) as e:
        raise TableError(f"{kind}: 読めない({e})") from e
    if kind in NEED_ROWS and not rows:
        raise TableError(f"{kind}: 0 行")
    return rows


def _stop(code: str) -> dict:
    return {"ok": False, "止まった理由": code, "説明": STOPS[code], "語": []}


def _is_int(s: str) -> bool:
    return s.isascii() and s.isdigit()


def check(words: list[dict], roles: list[dict], notes: list[dict], pairs: list[dict]) -> dict:
    """4 表から、語ごとの行(働きの記号 → 旧軸の順)と件数を返す。入力は書き換えない。"""
    edge: dict[str, bool] = {}
    for r in roles:
        if not r["role"] or not r["source"] or r["role"] in edge or r["edge"] not in ("", EDGE):
            return _stop("ROLE_TABLE")
        edge[r["role"]] = r["edge"] == EDGE
    note: dict[str, dict] = {}
    for n in notes:
        if not n["note_id"] or n["note_id"] in note or n["side"] not in SIDES or not n["text"] or not n["source"]:
            return _stop("NOTE_TABLE")
        note[n["note_id"]] = n
    for p in pairs:
        if not p["word_id"] or not p["note_id"] or not p["source"]:
            return _stop("PAIR_TABLE")
    for w in words:
        if not w["word_id"] or not w["word"] or not _is_int(w["order"]):
            return _stop("WORD_TABLE")

    ids: dict[str, int] = {}
    orders: dict[int, int] = {}
    for w in words:
        ids[w["word_id"]] = ids.get(w["word_id"], 0) + 1
        orders[int(w["order"])] = orders.get(int(w["order"]), 0) + 1
    by_word: dict[str, set[str]] = {}
    for p in pairs:
        by_word.setdefault(p["word_id"], set()).add(p["note_id"])

    classed, boxed, placed = [], [], set()
    n_class = {v: 0 for v in CLASSES.values()}
    n_box = {b: 0 for b in BOXES}
    n_role: dict[str, int] = {}
    n_pair = n_literal = n_mark_edge = n_mark_literal = 0
    for w in words:
        wid, mine = w["word_id"], sorted(by_word.get(w["word_id"], ()))
        row = {"語 id": wid, "語": w["word"], "旧軸の順": int(w["order"]), "働きの記号": w["role"], "出典": w["source"],
               "区分": "", SIDE_F: [], SIDE_V: [], "印": []}
        if ids[wid] > 1:
            box = BOXES[3]
        elif not w["source"]:
            box = BOXES[2]
        elif not w["role"]:
            box = BOXES[1]
        elif w["role"] not in edge:
            box = BOXES[0]
        elif orders[int(w["order"])] > 1:
            box = BOXES[5]
        elif any(nid not in note for nid in mine):
            box = BOXES[4]
        else:
            box = ""
        if box:
            row["区分"] = BOX_HEAD + box
            n_box[box] += 1
            boxed.append((BOXES.index(box), wid, row["旧軸の順"], w["word"], w["role"], w["source"], row))
            continue
        for nid in mine:
            n = note[nid]
            lit = w["word"] in n["text"]
            row[n["side"]].append({"記載 id": nid, "記載": n["text"], "結果": n["result"], "出典": n["source"],
                                   "語を literal に含む": lit})
            n_pair += 1
            n_literal += lit
            placed.add(nid)
        has_f, has_v = bool(row[SIDE_F]), bool(row[SIDE_V])
        row["区分"] = CLASSES["A" if has_f and has_v else "B" if has_v else "C" if has_f else "D"]
        if edge[w["role"]] and not has_v:
            row["印"].append(MARK_EDGE)
            n_mark_edge += 1
        if any(not x["語を literal に含む"] for x in row[SIDE_F] + row[SIDE_V]):
            row["印"].append(MARK_LITERAL)
            n_mark_literal += 1
        n_class[row["区分"]] += 1
        n_role[w["role"]] = n_role.get(w["role"], 0) + 1
        classed.append((w["role"], row["旧軸の順"], wid, row))

    rows = [t[-1] for t in sorted(classed, key=lambda t: t[:-1])] + [t[-1] for t in sorted(boxed, key=lambda t: t[:-1])]
    n4, nb = sum(n_class.values()), sum(n_box.values())
    out = {
        "ok": True,
        "語の台帳の行数": len(words),
        "区分": n_class,
        "別枠": n_box,
        "働きの記号ごとの語の件数": dict(sorted(n_role.items())),
        "補助の印(区分には使わない)": {MARK_EDGE: n_mark_edge, MARK_LITERAL: n_mark_literal},
        "対": {"横に置いた対の数": n_pair, "うち語の文字列を literal に含む記載との対": n_literal,
               "台帳に無い語 id を指す対の行数": sum(1 for p in pairs if p["word_id"] not in ids),
               "同じ対が重なった行数": len(pairs) - len({(p["word_id"], p["note_id"]) for p in pairs})},
        "どの語の横にも置かれなかった記載の件数": {s: sum(1 for n in notes if n["side"] == s and n["note_id"] not in placed)
                                                   for s in SIDES},
        "件数の合計の検算": f"区分 {n4} + 別枠 {nb} = {n4 + nb} / 語の台帳の行数 {len(words)}",
        "語": rows,
    }
    out["sha256"] = hashlib.sha256(json.dumps(out, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    out["持たせていないもの"] = list(NOT_HELD)
    return out


def check_doc(words: list[dict], notes: list[dict], doc_lines: list[str], label: str) -> dict:
    """出典が `<label> L<行番号>` の行について、文字列がその行に literal で在るかを見る(写し間違いの検出)。"""
    head, n_ref, missing = label + " L", 0, []
    items = [(w["word_id"], w["source"], [w["word"]]) for w in words]
    items += [(n["note_id"], n["source"], [n["text"]] + ([n["result"]] if n["result"] else [])) for n in notes]
    for ident, src, texts in items:
        if not (src.startswith(head) and _is_int(src[len(head):])):
            continue
        n_ref += 1
        no = int(src[len(head):])
        line = doc_lines[no - 1] if 1 <= no <= len(doc_lines) else ""
        if any(t not in line for t in texts):
            missing.append(ident)
    return {"文書の行数": len(doc_lines), "出典がこの文書の行を指す行数": n_ref, "文字列が出典の行に無い id": sorted(missing)}


def _classed(out: dict) -> dict[str, dict]:
    return {r["語 id"]: r for r in out["語"] if not r["区分"].startswith(BOX_HEAD)}


def verify(words: list[dict], roles: list[dict], notes: list[dict], pairs: list[dict]) -> dict:
    """手続きが決定論かを 5 つ測る。"""
    base = check(words, roles, notes, pairs)
    if not base["ok"]:
        return {"ok": False, "止まった理由": base["止まった理由"]}
    res: dict[str, object] = {}
    res["① 二度走らせて sha256 が同じ"] = check(words, roles, notes, pairs)["sha256"] == base["sha256"]
    res["② 4 表の行順を逆にしても同じ"] = check(words[::-1], roles[::-1], notes[::-1], pairs[::-1])["sha256"] == base["sha256"]
    res["③ 区分 + 別枠 = 語の台帳の行数"] = sum(base["区分"].values()) + sum(base["別枠"].values()) == len(words)

    a = _classed(base)
    names = sorted(r["role"] for r in roles)
    tried4 = ok4 = 0
    if len(names) > 1:
        for wid, row in a.items():
            other = names[(names.index(row["働きの記号"]) + 1) % len(names)]
            new = check([dict(w, role=other) if w["word_id"] == wid else w for w in words], roles, notes, pairs)
            b = _classed(new) if new["ok"] else {}
            tried4 += 1
            ok4 += (b.keys() == a.keys() and all(b[k] == a[k] for k in a if k != wid)
                    and b[wid]["働きの記号"] == other and b[wid]["区分"] == row["区分"]
                    and b[wid][SIDE_F] == row[SIDE_F] and b[wid][SIDE_V] == row[SIDE_V]
                    and new["区分"] == base["区分"] and new["別枠"] == base["別枠"])
    res["④ 1 語の働きの記号を替えると、その語の段だけが動き区分は変わらない"] = ok4 == tried4

    tried5 = ok5 = moved5 = 0
    for wid, row in a.items():
        for x in row[SIDE_F] + row[SIDE_V]:
            nid = x["記載 id"]
            new = check(words, roles, notes, [p for p in pairs if (p["word_id"], p["note_id"]) != (wid, nid)])
            b = _classed(new) if new["ok"] else {}
            tried5 += 1
            if b.keys() != a.keys() or any(b[k] != a[k] for k in a if k != wid):
                continue
            rest = [y["記載 id"] for y in b[wid][SIDE_F] + b[wid][SIDE_V]]
            if rest == [y["記載 id"] for y in row[SIDE_F] + row[SIDE_V] if y["記載 id"] != nid]:
                ok5 += 1
                moved5 += b[wid]["区分"] != row["区分"]
    res["⑤ 対を 1 行抜くと、その語だけが動き他は変わらない"] = ok5 == tried5
    return {"ok": all(v is True for v in res.values()), "結果": res,
            "④ 試した語": f"{ok4}/{tried4}", "⑤ 試した対": f"{ok5}/{tried5}", "⑤ で区分が動いた対": moved5,
            "sha256": base["sha256"]}


TEMPLATE = {
    "words": [],
    "roles": [["表を引く", EDGE, "私の登録"], ["端数を落とす", EDGE, "私の登録"], ["大小で選ぶ", "", "私の登録"]],
    "notes": [],
    "pairs": [],
}


def init(dirpath: str | Path) -> list[str]:
    """ひな型の 4 表を書く。既に在るファイルは書き換えない。"""
    d = Path(dirpath)
    d.mkdir(parents=True, exist_ok=True)
    made = []
    for kind, rows in TEMPLATE.items():
        p = d / f"{kind}.csv"
        if p.exists():
            continue
        with open(p, "w", encoding="utf-8", newline="") as f:
            wr = csv.writer(f, lineterminator="\n")
            wr.writerow(COLS[kind])
            wr.writerows(rows)
        made.append(p.name)
    return made


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="式が呼べる語の一覧を働きの記号の軸で並べ直し、記載を横に置く")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").add_argument("dir")
    for name in ("check", "verify"):
        sp = sub.add_parser(name)
        for k in COLS:
            sp.add_argument(k)
        if name == "check":
            sp.add_argument("--doc")
            sp.add_argument("--label", default="文書")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if a.cmd == "init":
        print(json.dumps({"書いたひな型": init(a.dir)}, ensure_ascii=False))
        return 0
    try:
        tables = [read_table(getattr(a, k), k) for k in COLS]
        doc = Path(a.doc).read_text(encoding="utf-8-sig").splitlines() if a.cmd == "check" and a.doc else None
    except (TableError, OSError, UnicodeDecodeError) as e:
        print(json.dumps({"ok": False, "読めない": str(e)}, ensure_ascii=False))
        return 2
    out = check(*tables) if a.cmd == "check" else verify(*tables)
    if doc is not None and out["ok"]:
        out["文書の行の写し"] = check_doc(tables[0], tables[2], doc, a.label)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if out["ok"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
