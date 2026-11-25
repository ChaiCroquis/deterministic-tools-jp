"""label_fold — 2 つの文書の項目名の対を、登録した畳む手順に 1 段ずつ通し、同じ字になった段と、ならなかった対を並べる。

入力は 3 表(どれも UTF-8 の CSV)。名前も対も人が書く。この部品は文書を読まない。対を作らない。
  ① 名前の台帳      : 名前id / 文書id / 名前 / 切り方のメモ / 出典
  ② 畳む手順の登録表: 順番 / 手順の種類 / 除く記号 / 出典
  ③ 対の登録表      : 対id / 左の名前id / 右の名前id(片側は空でもよい = 相手なし)/ 読みのメモ / 出典

手順の種類は 4 つだけ: NFKC / 空白を除く / 登録した記号を除く / 英字の大文字小文字を揃える

持たない経路(関数にも CLI にも引数が無い):
  編集距離や似ている度合いを返す / 略語の辞書 / 読みがなに直す / 対を推す / C をどちらかの字に寄せる /
  どちらの呼び方が正しいかを返す / 文書から名前を切り出す / ネットワーク

使い方: python label_fold.py --names <名前の台帳.csv> --steps <畳む手順.csv> --pairs <対の登録表.csv> [--json] [--verify]
終了コード: 0 = 全ての対が A か B で別枠も「対に無いが畳むと同じ組」も無い / 3 = 人が見る行がある /
            2 = 表が読めない / 4 = --verify が合わない
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import unicodedata
from itertools import combinations
from pathlib import Path

NAME_COLS = ("名前id", "文書id", "名前", "切り方のメモ", "出典")
STEP_COLS = ("順番", "手順の種類", "除く記号", "出典")
PAIR_COLS = ("対id", "左の名前id", "右の名前id", "読みのメモ", "出典")

S_NFKC, S_SPACE, S_SYMBOL, S_CASE = "NFKC", "空白を除く", "登録した記号を除く", "英字の大文字小文字を揃える"
STEP_KINDS = (S_NFKC, S_SPACE, S_SYMBOL, S_CASE)

CAT_A, CAT_B, CAT_C, CAT_D = "A 書かれたまま同じ", "B 畳むと同じ", "C 全段を通しても違う", "D 相手なし"
CATS = (CAT_A, CAT_B, CAT_C, CAT_D)

B_STEP = "登録表に無い手順の種類"
B_NAME = "対が指す名前idが台帳に無い"
B_SOURCE = "出典が空"
B_DUP = "同じ名前idが2回"
B_TWICE = "同じ名前idが2つの対に出る"
B_SAMEDOC = "対の両側が同じ文書id"
BETSU = (B_STEP, B_NAME, B_SOURCE, B_DUP, B_TWICE, B_SAMEDOC)

NOT_HELD = (
    "編集距離や似ている度合いを返す経路は持たない",
    "略語の辞書は持たない",
    "読みがなに直す経路は持たない",
    "対を推す経路は持たない(対は人が登録する)",
    "C の対をどちらかの字に寄せる経路は持たない",
    "どちらの呼び方が正しいかを返す経路は持たない",
    "文書から名前を切り出す経路は持たない(名前は人が写す)",
    "ネットワークへ出る経路は持たない",
)

_LOWER = {c: c + 32 for c in range(ord("A"), ord("Z") + 1)}


class LabelFoldError(Exception):
    """表そのものが読めないとき(1 対も並べずに止まる)。"""


def read_table(path: str | Path, cols: tuple[str, ...]) -> list[dict[str, str]]:
    """CSV を読む。名前の列だけは空白も含めて書かれた字のまま残し、ほかの列は前後の空白を落とす。"""
    reader = csv.DictReader(io.StringIO(Path(path).read_text(encoding="utf-8-sig"), newline=""))
    missing = [c for c in cols if c not in (reader.fieldnames or [])]
    if missing:
        raise LabelFoldError(f"必要な列が無い: {Path(path).name} に {' / '.join(missing)}")
    return [{c: (r.get(c) or "") if c == "名前" else (r.get(c) or "").strip() for c in cols} for r in reader]


def apply_step(s: str, kind: str, symbols: str) -> str:
    if kind == S_NFKC:
        return unicodedata.normalize("NFKC", s)
    if kind == S_SPACE:
        return "".join(c for c in s if not c.isspace())
    if kind == S_SYMBOL:
        return "".join(c for c in s if c not in symbols)
    return s.translate(_LOWER)


def _steps(steps: list[dict[str, str]]) -> tuple[list[dict], list[dict]]:
    """(当てる手順を順番どおりに, 別枠の手順)。"""
    use: list[dict] = []
    betsu: list[dict] = []
    seen: set[int] = set()
    for i, s in enumerate(steps, start=1):
        if not (s["順番"].isascii() and s["順番"].isdigit()):
            raise LabelFoldError(f"畳む手順の順番が整数でない: 行 {i} = {s['順番']}")
        n = int(s["順番"])
        if n in seen:
            raise LabelFoldError(f"畳む手順に同じ順番が 2 回ある: {n}")
        seen.add(n)
        if s["手順の種類"] not in STEP_KINDS:
            betsu.append({"行": i, "手順の種類": s["手順の種類"], "理由": B_STEP})
        elif not s["出典"]:
            betsu.append({"行": i, "手順の種類": s["手順の種類"], "理由": B_SOURCE})
        elif (s["手順の種類"] == S_SYMBOL) != bool(s["除く記号"]):
            raise LabelFoldError(f"除く記号の有無が手順の種類と合わない: 行 {i}")
        else:
            use.append({"順番": n, "種類": s["手順の種類"], "除く記号": s["除く記号"]})
    return sorted(use, key=lambda x: x["順番"]), betsu


def _trail(name: str, use: list[dict]) -> list[str]:
    out = []
    for s in use:
        name = apply_step(name, s["種類"], s["除く記号"])
        out.append(name)
    return out


def fold_pairs(names: list[dict[str, str]], steps: list[dict[str, str]], pairs: list[dict[str, str]]) -> dict:
    """3 表から、対ごとの段ごとの字と区分を返す。入力は書き換えない。"""
    use, step_betsu = _steps(steps)
    by_id: dict[str, dict[str, str]] = {}
    n_id: dict[str, int] = {}
    for n in names:
        if not n["名前id"] or not n["文書id"] or not n["名前"].strip():
            raise LabelFoldError(f"名前の台帳に、名前id・文書id・名前のどれかが空の行がある: {n['名前id']}")
        n_id[n["名前id"]] = n_id.get(n["名前id"], 0) + 1
        by_id[n["名前id"]] = n
    pid_seen: set[str] = set()
    n_used: dict[str, int] = {}
    for p in pairs:
        if not p["対id"] or p["対id"] in pid_seen:
            raise LabelFoldError(f"対id が空か、2 回ある: {p['対id']}")
        pid_seen.add(p["対id"])
        for x in (p["左の名前id"], p["右の名前id"]):
            if x:
                n_used[x] = n_used.get(x, 0) + 1

    out_pairs: list[dict] = []
    betsu: list[dict] = []
    for i, p in enumerate(pairs, start=1):
        ids = [x for x in (p["左の名前id"], p["右の名前id"]) if x]
        if not ids or any(x not in by_id for x in ids):
            reason = B_NAME
        elif not p["出典"] or any(not by_id[x]["出典"] for x in ids):
            reason = B_SOURCE
        elif any(n_id[x] > 1 for x in ids):
            reason = B_DUP
        elif any(n_used[x] > 1 for x in ids):
            reason = B_TWICE
        elif len(ids) == 2 and by_id[ids[0]]["文書id"] == by_id[ids[1]]["文書id"]:
            reason = B_SAMEDOC
        else:
            reason = ""
        if reason:
            betsu.append({"行": i, "対id": p["対id"], "理由": reason})
            continue
        left, right = by_id.get(p["左の名前id"]), by_id.get(p["右の名前id"])
        lt = _trail(left["名前"], use) if left else []
        rt = _trail(right["名前"], use) if right else []
        cat, at, inside = CAT_C, None, False
        if left is None or right is None:
            cat = CAT_D
        elif left["名前"] == right["名前"]:
            cat = CAT_A
        else:
            for s, a, b in zip(use, lt, rt):
                if a == b and a:                       # 除いた結果どちらも空になったものは同じと言わない
                    cat, at = CAT_B, {"順番": s["順番"], "種類": s["種類"]}
                    break
            if cat == CAT_C:
                a = lt[-1] if lt else left["名前"]
                b = rt[-1] if rt else right["名前"]
                inside = bool(a and b) and (a in b or b in a)
        out_pairs.append({
            "対id": p["対id"], "区分": cat, "同じになった段": at,
            "左": left["名前"] if left else "", "左の文書": left["文書id"] if left else "",
            "左の出典": left["出典"] if left else "",
            "右": right["名前"] if right else "", "右の文書": right["文書id"] if right else "",
            "右の出典": right["出典"] if right else "",
            "段ごとの左": lt, "段ごとの右": rt, "印_片側がもう片側に含まれる": inside})

    # 補助の印: 畳んだ字が同じなのに対に登録されていない名前の組(名前id を並べるだけ)
    registered = {frozenset((p["左の名前id"], p["右の名前id"])) for p in pairs}
    ok = sorted(i for i, n in by_id.items() if n_id[i] == 1 and n["出典"])
    last = {i: (_trail(by_id[i]["名前"], use) or [by_id[i]["名前"]])[-1] for i in ok}
    unregistered = [[a, b] for a, b in combinations(ok, 2)
                    if last[a] and last[a] == last[b] and frozenset((a, b)) not in registered]

    docs: dict[str, int] = {}
    for n in names:
        docs[n["文書id"]] = docs.get(n["文書id"], 0) + 1
    result = {
        "対ごと": out_pairs,
        "区分ごとの件数": {c: sum(1 for p in out_pairs if p["区分"] == c) for c in CATS},
        "Bを同じになった段ごとに": [{"順番": s["順番"], "種類": s["種類"], "件数": sum(
            1 for p in out_pairs if p["同じになった段"] and p["同じになった段"]["順番"] == s["順番"])} for s in use],
        "文書ごとの名前の数": dict(sorted(docs.items())),
        "印_対に無いが畳むと同じ組": unregistered,
        "別枠_対": betsu, "別枠_手順": step_betsu,
        "対の登録表の行数": len(pairs),
        "持たせていないもの": list(NOT_HELD),
    }
    result["sha256"] = digest(result)
    return result


def digest(result: dict) -> str:
    body = {k: v for k, v in result.items() if k != "sha256"}
    return hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def verify(names: list[dict[str, str]], steps: list[dict[str, str]], pairs: list[dict[str, str]]) -> dict[str, bool]:
    r = fold_pairs(names, steps, pairs)
    cat = {p["対id"]: p["区分"] for p in r["対ごと"]}
    bare = {p["対id"]: p["区分"] for p in fold_pairs(names, [], pairs)["対ごと"]}
    same_ad = all({k for k, v in bare.items() if v == c} == {k for k, v in cat.items() if v == c}
                  for c in (CAT_A, CAT_D))
    moved = True
    for p in pairs:                                     # C の 1 対ずつ、右を左と同じ字に書き換える
        if cat.get(p["対id"]) != CAT_C:
            continue
        left = next(n["名前"] for n in names if n["名前id"] == p["左の名前id"])
        edited = [{**n, "名前": left} if n["名前id"] == p["右の名前id"] else n for n in names]
        after = {q["対id"]: q["区分"] for q in fold_pairs(edited, steps, pairs)["対ごと"]}
        moved = moved and after == {**cat, p["対id"]: CAT_A}
    return {
        "1 二度走りの sha256 が同じ": fold_pairs(names, steps, pairs)["sha256"] == r["sha256"],
        "2 名前の台帳の行順を逆にしても同じ": fold_pairs(names[::-1], steps, pairs)["sha256"] == r["sha256"],
        "3 区分 4 値 + 別枠 = 対の登録表の行数":
            sum(r["区分ごとの件数"].values()) + len(r["別枠_対"]) == len(pairs),
        "4 手順を空にすると B が 0 で A と D は同じ": CAT_B not in bare.values() and same_ad,
        "5 C の片側を同じ字にするとその対だけ A へ動く": moved,
    }


def exit_code(r: dict) -> int:
    c = r["区分ごとの件数"]
    look = c[CAT_C] or c[CAT_D] or r["別枠_対"] or r["別枠_手順"] or r["印_対に無いが畳むと同じ組"]
    return 3 if look else 0


def render(r: dict) -> str:
    o: list[str] = []
    for cat in CATS:
        o.append(f"■ {cat} {r['区分ごとの件数'][cat]} 対")
        for p in r["対ごと"]:
            if p["区分"] != cat:
                continue
            left = f"{p['左']}({p['左の出典']})" if p["左"] else "(なし)"
            right = f"{p['右']}({p['右の出典']})" if p["右"] else "(なし)"
            o.append(f"  {p['対id']} {left} | {right}")
            if p["同じになった段"]:
                o.append(f"      同じになった段 {p['同じになった段']['順番']} {p['同じになった段']['種類']}")
            if cat == CAT_C and p["段ごとの左"]:
                mark = "  印 片側がもう片側に含まれる" if p["印_片側がもう片側に含まれる"] else ""
                o.append(f"      畳んだ後 {p['段ごとの左'][-1]} | {p['段ごとの右'][-1]}{mark}")
    o.append("■ B を同じになった段ごとに: " + (" / ".join(
        f"{s['順番']} {s['種類']} {s['件数']}" for s in r["Bを同じになった段ごとに"]) or "手順なし"))
    o.append("■ 文書ごとの名前の数: " + " / ".join(f"{k} {v}" for k, v in r["文書ごとの名前の数"].items()))
    o.append(f"■ 印 対に無いが畳むと同じ組 {len(r['印_対に無いが畳むと同じ組'])} 組")
    o.extend(f"    {a} / {b}" for a, b in r["印_対に無いが畳むと同じ組"])
    o.append(f"■ 別枠 対 {len(r['別枠_対'])} 件 / 手順 {len(r['別枠_手順'])} 件(対の登録表 {r['対の登録表の行数']} 行)")
    o.extend(f"    対 行 {b['行']} {b['対id']}: {b['理由']}" for b in r["別枠_対"])
    o.extend(f"    手順 行 {b['行']} {b['手順の種類']}: {b['理由']}" for b in r["別枠_手順"])
    o.append("■ 持たせていないもの")
    o.extend(f"    - {x}" for x in r["持たせていないもの"])
    return "\n".join(o) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="項目名の対を畳む手順に通し、同じになる対とならない対を分けて並べる")
    ap.add_argument("--names", required=True, help="名前の台帳(CSV)")
    ap.add_argument("--steps", required=True, help="畳む手順の登録表(CSV)")
    ap.add_argument("--pairs", required=True, help="対の登録表(CSV)")
    ap.add_argument("--json", action="store_true", help="JSON で出す")
    ap.add_argument("--verify", action="store_true", help="検算 5 つを出す")
    a = ap.parse_args(argv)
    try:
        t = (read_table(a.names, NAME_COLS), read_table(a.steps, STEP_COLS), read_table(a.pairs, PAIR_COLS))
        r = fold_pairs(*t)
        checks = verify(*t) if a.verify else {}
    except (LabelFoldError, OSError, UnicodeDecodeError) as e:
        print(f"止まった: {e}", file=sys.stderr)
        return 2
    if a.json:
        out = json.dumps({**r, "検算": checks} if checks else r, ensure_ascii=False, indent=1) + "\n"
    else:
        out = render(r) + "".join(f"検算 {k}: {'合う' if v else '合わない'}\n" for k, v in checks.items())
    sys.stdout.buffer.write(out.encode("utf-8"))
    return exit_code(r) if all(checks.values()) else 4


if __name__ == "__main__":
    sys.exit(main())
