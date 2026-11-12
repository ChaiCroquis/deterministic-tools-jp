"""regen_axis — ファイルの一覧を「書き手」と「作り直す元」の軸で並べ直す判定器。

読むのは渡された 5 枚の表(CSV)だけ。ディスクを歩かない、ファイルの中身や更新時刻を読まない、
消さない、動かさない、走らせない、消してよいかを決めない。名前や拡張子から書き手を当てない。
文言の意味を読まない。時計を読まない。標準ライブラリのみ(csv / json / hashlib / argparse)。

使い方:
  python regen_axis.py check  <ファイルの台帳> <書き手の登録表> <作る線の台帳> <言い方の台帳> <一覧の台帳>
  python regen_axis.py rows   (同じ 5 枚)      # ファイル 1 件 1 行の CSV
  python regen_axis.py verify (同じ 5 枚)      # 決定論かどうかの 5 つの検算
終了コード: 0 = 判定した / 3 = verify のどれかが合わない / 2 = 表の形の誤り(1 件も判定しない)
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys

# ---- 語彙(ここに無い語は出力に出ない) ---------------------------------------------
HITO, JIKKOU, SOTO, HIKAE = "人が書く", "実行が書く", "外から取る", "控え"
NO_WRITER = "書き手の記載なし"
NO_ORIGIN = "取り先の記載なし"
NO_LINE = "作り直す線の記載なし"
MIXED = "書き手が混ざる"

KUBUN = (
    "(A) 人が書き、どの線の出力にも出ない",
    "(B) 実行が書き、出力として出る線が在る",
    "(C) 外から取り、取り先の記載が在る",
    "(D) 控え",
    "(E) A〜D に当たらない",
)
A, B, C, D, E = KUBUN
E_UCHIWAKE = ("どの線にも出ない", "入力にだけ出る", "出力に出るが書き手が実行でない")

# 別枠の理由。手前が勝つ(この順番そのものが仕様)
BETSUWAKU = (
    "file id が重複",
    "出典が空",
    "書き手の記号が登録表に無い",
    "外から取るのに取り先が空",
    "線の端が台帳に無い",
    "線が輪になる",
)

COLUMNS = {
    "files": ("file id", "名前", "置き場", "役割", "書き手の記号", "取り先", "出典"),
    "writers": ("記号", "意味", "出典"),
    "lines": ("線 id", "入力の file id", "出力の file id", "出典"),
    "sayings": ("言い方 id", "file id", "文言", "出典"),
    "lists": ("一覧 id", "file id", "出典"),
}
TABLE_NAMES = {"files": "ファイルの台帳", "writers": "書き手の登録表", "lines": "作る線の台帳",
               "sayings": "言い方の台帳", "lists": "一覧の台帳"}
ROW_COLUMNS = ("file id", "名前", "置き場", "役割", "書き手の記号", "取り先", "入力に出る回数",
               "出力に出る回数", "作り直す元", "遡った端", "区分", "E の内訳", "別枠の理由", "出典")

SHINAIKOTO = {
    "ディスクを歩かない": "読むのは渡された 5 枚の表だけ。フォルダの実物は数えていない",
    "中身と更新時刻を読まない": "名前は渡された文字列を写すだけ",
    "消さない・動かさない・走らせない": "入力の表にも 1 文字も書かない",
    "消してよいかを決めない": "消してよいかの列も、危なさの点数も、順位も持たない",
    "名前から書き手を当てない": "書き手は台帳に宣言された記号だけ。空なら「書き手の記載なし」のまま",
    "文言の意味を読まない": "同じファイルへの言い方は並べるだけで、どちらが正しいとも言わない",
    "載っていない理由を言い当てない": "片方の一覧にしか無いことを返すだけ",
    "時計を読まない": "今日の日付も経過日数も使わない",
}


class TableError(ValueError):
    """表の形の誤り。1 件も判定しない。"""


# ---- 読む ---------------------------------------------------------------------------
def read_table(path: str, kind: str) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return normalize(list(csv.DictReader(f)), kind)


def normalize(rows: list[dict], kind: str) -> list[dict[str, str]]:
    cols = COLUMNS[kind]
    out = []
    for r in rows:
        missing = [c for c in cols if c not in r or r[c] is None]
        if missing:
            raise TableError(f"{TABLE_NAMES[kind]}: 列が無い {missing}")
        out.append({c: str(r[c]).strip() for c in cols})
    return out


def read_all(paths: list[str]) -> dict[str, list[dict[str, str]]]:
    kinds = ("files", "writers", "lines", "sayings", "lists")
    return {k: read_table(p, k) for k, p in zip(kinds, paths)}


# ---- 判定 ---------------------------------------------------------------------------
def _key(row: dict[str, str], kind: str) -> tuple:
    return tuple(row[c] for c in COLUMNS[kind])


def judge(tables: dict[str, list[dict]]) -> dict:
    t = {k: sorted(normalize(tables.get(k, []), k), key=lambda r, k=k: _key(r, k)) for k in COLUMNS}
    files = t["files"]
    if not files:
        raise TableError("ファイルの台帳: 行が無い")
    unused: list[dict[str, str]] = []

    def drop(kind: str, row: dict, reason: str) -> None:
        unused.append({"表": TABLE_NAMES[kind], "行": " / ".join(_key(row, kind)), "理由": reason})

    ids = [f["file id"] for f in files]
    idset = set(ids)
    dup = {i for i in idset if ids.count(i) > 1}

    registered = set()
    for w in t["writers"]:
        if not w["出典"]:
            drop("writers", w, "出典が空")
        elif w["記号"]:
            registered.add(w["記号"])

    # 線: 出典が在り、両端が台帳に在るものだけを数える
    edges: list[tuple[str, str]] = []
    dangling_in: set[str] = set()          # 入力の端が台帳に無い線の、出力の側
    for ln in t["lines"]:
        i, o = ln["入力の file id"], ln["出力の file id"]
        if not ln["出典"]:
            drop("lines", ln, "出典が空")
        elif o not in idset:
            drop("lines", ln, "出力の端が台帳に無い")
        elif i not in idset:
            dangling_in.add(o)
        else:
            edges.append((i, o))
    n_in = {i: 0 for i in idset}
    n_out = {i: 0 for i in idset}
    made_from: dict[str, set[str]] = {i: set() for i in idset}
    for i, o in edges:
        n_in[i] += 1
        n_out[o] += 1
        made_from[o].add(i)

    def ancestors(start: str) -> set[str]:
        seen: set[str] = set()
        stack = sorted(made_from[start])
        while stack:
            x = stack.pop()
            if x not in seen:
                seen.add(x)
                stack.extend(sorted(made_from[x]))
        return seen

    anc = {i: ancestors(i) for i in sorted(idset)}
    looped = {i for i in idset if i in anc[i]}

    rows = []
    for f in files:
        fid, sym = f["file id"], f["書き手の記号"]
        reason = ""
        if fid in dup:
            reason = BETSUWAKU[0]
        elif not f["出典"]:
            reason = BETSUWAKU[1]
        elif sym and sym not in registered:
            reason = BETSUWAKU[2]
        elif sym == SOTO and not f["取り先"]:
            reason = BETSUWAKU[3]
        elif fid in dangling_in:
            reason = BETSUWAKU[4]
        elif fid in looped:
            reason = BETSUWAKU[5]
        kubun = uchiwake = ""
        if not reason:
            if sym == HIKAE:
                kubun = D
            elif sym == SOTO:
                kubun = C
            elif sym == JIKKOU and n_out[fid] > 0:
                kubun = B
            elif sym == HITO and n_out[fid] == 0:
                kubun = A
            else:
                kubun = E
                uchiwake = (E_UCHIWAKE[2] if n_out[fid] > 0 else
                            E_UCHIWAKE[1] if n_in[fid] > 0 else E_UCHIWAKE[0])
        roots = sorted(x for x in anc[fid] if n_out[x] == 0)
        rows.append({
            "file id": fid, "名前": f["名前"], "置き場": f["置き場"], "役割": f["役割"],
            "書き手の記号": sym or NO_WRITER,
            "取り先": f["取り先"] or (NO_ORIGIN if sym == SOTO else ""),
            "入力に出る回数": n_in[fid], "出力に出る回数": n_out[fid],
            "作り直す元": " / ".join(sorted(made_from[fid])) or NO_LINE,
            "遡った端": " / ".join(roots),
            "区分": kubun, "E の内訳": uchiwake, "別枠の理由": reason, "出典": f["出典"],
        })

    # 置き場ごと(別枠のファイルは数えない)
    places: dict[str, dict[str, int]] = {}
    for r in rows:
        if not r["別枠の理由"]:
            d = places.setdefault(r["置き場"], {})
            d[r["書き手の記号"]] = d.get(r["書き手の記号"], 0) + 1
    place_rows = []
    for p in sorted(places):
        d = places[p]
        kinds = sorted(k for k in d if k != NO_WRITER)
        place_rows.append({
            "置き場": p, "ファイルの件数": sum(d.values()),
            "書き手の記号の種類の数": len(kinds),
            "内訳": {k: d[k] for k in sorted(d)},
            "印": MIXED if len(kinds) >= 2 else "",
        })

    # 同じファイルへの言い方(2 行以上在るものだけ。意味は読まない)
    said: dict[str, list[dict[str, str]]] = {}
    for s in t["sayings"]:
        if not s["出典"]:
            drop("sayings", s, "出典が空")
        elif s["file id"] not in idset:
            drop("sayings", s, "file id が台帳に無い")
        else:
            said.setdefault(s["file id"], []).append(
                {"言い方 id": s["言い方 id"], "文言": s["文言"], "出典": s["出典"]})
    saying_rows = [{"file id": i, "行数": len(v), "文言の種類の数": len({x["文言"] for x in v}), "言い方": v}
                   for i, v in sorted(said.items()) if len(v) >= 2]

    # 一覧(片方にしか載らないファイル。理由は言い当てない)
    on: dict[str, set[str]] = {}
    list_ids: set[str] = set()
    for l in t["lists"]:
        if not l["出典"]:
            drop("lists", l, "出典が空")
        elif l["file id"] not in idset:
            drop("lists", l, "file id が台帳に無い")
        else:
            list_ids.add(l["一覧 id"])
            on.setdefault(l["file id"], set()).add(l["一覧 id"])
    only = {li: sorted(i for i, s in on.items() if s == {li}) for li in sorted(list_ids)}
    nowhere = sorted(i for i in idset if i not in on)

    kubun_count = {k: sum(1 for r in rows if r["区分"] == k) for k in KUBUN}
    betsu_count = {k: sum(1 for r in rows if r["別枠の理由"] == k) for k in BETSUWAKU}
    e_count = {k: sum(1 for r in rows if r["E の内訳"] == k) for k in E_UCHIWAKE}
    nk, nb = sum(kubun_count.values()), sum(betsu_count.values())
    return {
        "軸の定義": "旧軸 = 役割(何のためのファイルか) / 新軸 = 書き手(誰が書くか)と作り直す元(どの線の出力か)",
        "分母(ファイルの件数)": len(rows),
        "区分": kubun_count,
        "E の内訳": e_count,
        "別枠": betsu_count,
        "数えた線の本数": len(edges),
        "ファイルごと": rows,
        "置き場ごと": place_rows,
        "同じファイルへの言い方": saying_rows,
        "その一覧にしか載らないファイル": only,
        "どの一覧にも載らないファイル": nowhere,
        "使わなかった行": sorted(unused, key=lambda u: (u["表"], u["行"], u["理由"])),
        "件数の合計の検算": f"区分 {nk} + 別枠 {nb} = {nk + nb} / 分母 {len(rows)}",
    }


def digest(result: dict) -> str:
    blob = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def check(tables: dict[str, list[dict]]) -> dict:
    r = judge(tables)
    out = {"ok": True}
    out.update(r)
    out["判定部分の sha256"] = digest(r)
    out["しないこと"] = dict(SHINAIKOTO)
    return out


# ---- verify(写しはメモリの中だけ。入力の表には書かない) -----------------------------
def _answers(result: dict) -> list[tuple]:
    return [(r["file id"], r["名前"], r["出典"], r["区分"], r["別枠の理由"]) for r in result["ファイルごと"]]


def verify(tables: dict[str, list[dict]]) -> dict:
    base = judge(tables)
    files = normalize(tables["files"], "files")
    lines = normalize(tables.get("lines", []), "lines")
    checks = {}

    checks["1 二度走っても同じ sha256"] = digest(base) == digest(judge(tables))

    flipped = {k: list(reversed(v)) for k, v in tables.items()}
    checks["2 行順を入れ替えても同じ出力"] = digest(judge(flipped)) == digest(base)

    total = sum(base["区分"].values()) + sum(base["別枠"].values())
    checks["3 区分 + 別枠 = ファイルの件数"] = total == base["分母(ファイルの件数)"] == len(files)

    # 4: 線を 1 行ずつ外す。動いてよいのは、その線の出力のファイルと、輪の上に居たファイルだけ
    on_loop = {r["file id"] for r in base["ファイルごと"] if r["別枠の理由"] == BETSUWAKU[5]}
    ok4, moved4 = True, 0
    for n in range(len(lines)):
        res = judge({**tables, "lines": lines[:n] + lines[n + 1:]})
        moved = {a[0] for a, b in zip(_answers(base), _answers(res)) if a != b}
        moved4 += len(moved)
        if not moved <= ({lines[n]["出力の file id"]} | on_loop):
            ok4 = False
    checks["4 線を 1 行外すと、その線の出力のファイルだけ区分が動く"] = ok4

    # 5: 書き手の記号を 1 行だけ 実行が書く → 人が書く に替える
    ok5, tried5, moved5 = True, 0, 0
    base_places = {p["置き場"]: p for p in base["置き場ごと"]}
    for n, f in enumerate(files):
        if f["書き手の記号"] != JIKKOU:
            continue
        tried5 += 1
        res = judge({**tables, "files": files[:n] + [{**f, "書き手の記号": HITO}] + files[n + 1:]})
        b_rows = sorted(base["ファイルごと"], key=lambda r: json.dumps(r, ensure_ascii=False, sort_keys=True))
        target = {**next(r for r in base["ファイルごと"]
                         if all(r[c] == f[c] for c in ("file id", "名前", "置き場", "役割", "出典"))
                         and r["書き手の記号"] == JIKKOU)}
        rest_b = [r for r in b_rows if r != target]
        rest_r = list(res["ファイルごと"])
        for r in rest_b:
            if r in rest_r:
                rest_r.remove(r)
            else:
                ok5 = False
        if len(rest_r) != 1:
            ok5 = False
        elif (rest_r[0]["区分"], rest_r[0]["別枠の理由"]) != (target["区分"], target["別枠の理由"]):
            moved5 += 1
        res_places = {p["置き場"]: p for p in res["置き場ごと"]}
        for p in set(base_places) | set(res_places):
            if p != f["置き場"] and base_places.get(p) != res_places.get(p):
                ok5 = False
    checks["5 書き手を 1 行替えると、そのファイルと同じ置き場の印だけが変わる"] = ok5

    return {
        "ok": all(checks.values()),
        "検算": checks,
        "線を 1 行ずつ外して区分が動いた延べ件数": moved4,
        "外した線の本数": len(lines),
        "書き手を替えた行数": tried5,
        "書き手を替えて区分が動いた件数": moved5,
        "判定部分の sha256": digest(base),
    }


# ---- CLI ----------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="ファイルの一覧を、書き手と作り直す元の軸で並べ直す")
    ap.add_argument("command", choices=("check", "rows", "verify"))
    ap.add_argument("tables", nargs=5, metavar="CSV",
                    help="ファイルの台帳 / 書き手の登録表 / 作る線の台帳 / 言い方の台帳 / 一覧の台帳")
    a = ap.parse_args(argv)
    try:
        tables = read_all(a.tables)
        if a.command == "check":
            print(json.dumps(check(tables), ensure_ascii=False, indent=1))
            return 0
        if a.command == "rows":
            w = csv.DictWriter(sys.stdout, fieldnames=ROW_COLUMNS, lineterminator="\n")
            w.writeheader()
            w.writerows(judge(tables)["ファイルごと"])
            return 0
        v = verify(tables)
        print(json.dumps(v, ensure_ascii=False, indent=1))
        return 0 if v["ok"] else 3
    except (TableError, OSError) as e:
        print(json.dumps({"ok": False, "理由": str(e), "区分": {k: 0 for k in KUBUN}}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
