"""part_sum — 文書に書かれた総数の宣言と、その下に並ぶ内訳の数を足した数を横に置く。

入力は 3 表(どれも UTF-8 の CSV)。数は人が文書から写して書く。この部品は文書を読まない。
  ① 総数の台帳      : 総数id / 数 / 単位 / 出典
  ② 内訳の台帳      : 項目id / 総数id / 項目の名前 / 数(空でもよい)/ 単位(空でもよい)/ 読みの種類 / 出典
  ③ 読みの種類の登録表: 読みの種類 / 足す側(入れる・入れない・数が無い)

出力は総数ごとに、足した数を 2 列(登録表で `入れる` の項目だけ / `入れない` の項目も入れた場合)、
総数の宣言、差を 2 列、数の付いていない項目の名前の一覧、区分 4 値を 2 列、出典の行ごとの小計。
並びは総数の台帳の順 → 内訳の台帳の順で固定する。

持たない経路(関数にも CLI にも引数が無い):
  差を数の付いていない項目に割り振る / 「各 n」「n 種」を掛けて数にする / 文書の文字列から数を拾う /
  単位の違う数を換算する / 総数と内訳のどちらが正しいかを返す / 割合に直す

使い方: python part_sum.py --totals <総数の台帳.csv> --parts <内訳の台帳.csv> --kinds <読みの種類の登録表.csv> [--json]
終了コード: 0 = 全ての総数が 2 列とも区分 A で別枠も 0 / 3 = それ以外(人が見る行がある)/ 2 = 表が読めない
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path

TOTAL_COLS = ("総数id", "数", "単位", "出典")
PART_COLS = ("項目id", "総数id", "項目の名前", "数", "単位", "読みの種類", "出典")
KIND_COLS = ("読みの種類", "足す側")

IRERU, IRENAI, KAZU_NASHI = "入れる", "入れない", "数が無い"
SIDES = (IRERU, IRENAI, KAZU_NASHI)

CAT_A = "A 数の付いていない項目が 0 で差が 0"
CAT_B = "B 数の付いていない項目が 0 で差が 0 でない"
CAT_C = "C 数の付いていない項目が在り、足した数が総数以下"
CAT_D = "D 数の付いていない項目が在り、足した数が総数を超える"
CATS = (CAT_A, CAT_B, CAT_C, CAT_D)

B_KIND = "登録表に無い読みの種類"
B_TOTAL = "属する総数idが台帳に無い"
B_SOURCE = "出典が空"
B_DUP = "同じ項目idが2回"
B_INT = "数が整数でない"
B_MISMATCH = "読みの種類と数の有無が合わない"
BETSU = (B_KIND, B_TOTAL, B_SOURCE, B_DUP, B_INT, B_MISMATCH)

NOT_HELD = (
    "差を数の付いていない項目に割り振る経路は持たない",
    "「各 n」「n 種」を掛けて数にする経路は持たない(掛けた数は人が書き、読みの種類で分ける)",
    "文書の文字列から数を拾う経路は持たない(数は人が台帳に写す)",
    "単位の違う数を換算する経路は持たない(単位の字が違う項目に印を付けるだけ)",
    "総数と内訳のどちらが正しいかを返す経路は持たない",
    "割合に直す経路は持たない",
)

# 半角の数字だけ。桁区切りのカンマは 3 桁ごとに正しく入っているものだけ読む
_INT_RE = re.compile(r"(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)\Z")


class PartSumError(Exception):
    """表そのものが読めないとき(1 件も足さずに止まる)。"""


def parse_int(s: str) -> int | None:
    """整数の字なら int、そうでなければ None。掛け算の字(「各 4」「4×4」)は整数でない。"""
    if not _INT_RE.match(s):
        return None
    return int(s.replace(",", ""))


def read_table(path: str | Path, cols: tuple[str, ...]) -> list[dict[str, str]]:
    """CSV を読む。必要な列が無ければ止まる。値は前後の空白だけ落とし、ほかは書かれた字のまま。"""
    text = Path(path).read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    head = reader.fieldnames or []
    missing = [c for c in cols if c not in head]
    if missing:
        raise PartSumError(f"必要な列が無い: {Path(path).name} に {' / '.join(missing)}")
    return [{c: (row.get(c) or "").strip() for c in cols} for row in reader]


def _category(unnumbered: int, total: int, added: int) -> str:
    if unnumbered == 0:
        return CAT_A if added == total else CAT_B
    return CAT_C if added <= total else CAT_D


def tally(totals: list[dict[str, str]], parts: list[dict[str, str]],
          kinds: list[dict[str, str]]) -> dict:
    """3 表から、総数ごとの足した数・差・数の付いていない項目・区分を返す。入力は書き換えない。"""
    # 読みの種類の登録表
    side_of: dict[str, str] = {}
    for k in kinds:
        name, side = k["読みの種類"], k["足す側"]
        if not name:
            raise PartSumError("読みの種類の登録表に、種類の字が空の行がある")
        if name in side_of:
            raise PartSumError(f"読みの種類の登録表に同じ種類が 2 回ある: {name}")
        if side not in SIDES:
            raise PartSumError(f"足す側の字が登録の 3 つに無い: {name} = {side}")
        side_of[name] = side

    # 総数の台帳
    declared: dict[str, int] = {}
    for t in totals:
        tid = t["総数id"]
        if not tid:
            raise PartSumError("総数の台帳に、総数id が空の行がある")
        if tid in declared:
            raise PartSumError(f"総数の台帳に同じ総数id が 2 回ある: {tid}")
        n = parse_int(t["数"])
        if n is None:
            raise PartSumError(f"総数の数が整数でない: {tid} = {t['数']}")
        if not t["出典"]:
            raise PartSumError(f"総数の出典が空: {tid}")
        declared[tid] = n

    # 内訳の台帳を、足せる行と別枠に分ける(1 行は別枠の理由を 1 つだけ持つ。順は BETSU の順)
    seen: dict[str, int] = {}
    for p in parts:
        seen[p["項目id"]] = seen.get(p["項目id"], 0) + 1
    betsu: list[dict] = []
    usable: list[tuple[dict[str, str], str, int | None]] = []
    for i, p in enumerate(parts, start=1):
        side = side_of.get(p["読みの種類"])
        n = parse_int(p["数"]) if p["数"] else None
        if side is None:
            reason = B_KIND
        elif p["総数id"] not in declared:
            reason = B_TOTAL
        elif not p["出典"]:
            reason = B_SOURCE
        elif seen[p["項目id"]] > 1:
            reason = B_DUP
        elif p["数"] and n is None:
            reason = B_INT
        elif (side == KAZU_NASHI) != (n is None):
            reason = B_MISMATCH
        else:
            usable.append((p, side, n))
            continue
        betsu.append({"行": i, "項目id": p["項目id"], "項目の名前": p["項目の名前"],
                      "書かれていた数": p["数"], "理由": reason})

    out_totals: list[dict] = []
    for t in totals:
        tid, total = t["総数id"], declared[t["総数id"]]
        mine = [(p, side, n) for p, side, n in usable if p["総数id"] == tid]
        strict = sum(n for _, side, n in mine if side == IRERU)
        extra = sum(n for _, side, n in mine if side == IRENAI)
        unnumbered = [{"項目id": p["項目id"], "項目の名前": p["項目の名前"], "出典": p["出典"]}
                      for p, side, _ in mine if side == KAZU_NASHI]
        unit_diff = [{"項目id": p["項目id"], "項目の名前": p["項目の名前"], "数": n,
                      "単位": p["単位"], "出典": p["出典"]}
                     for p, side, n in mine if p["単位"] and p["単位"] != t["単位"]]
        names: dict[str, list[str]] = {}
        for p, _, _ in mine:
            names.setdefault(p["項目の名前"], []).append(p["項目id"])
        dup_names = [{"項目の名前": k, "項目id": v} for k, v in names.items() if len(v) > 1]

        by_source: dict[str, dict] = {}
        for p, side, n in mine:
            b = by_source.setdefault(p["出典"], {
                "出典": p["出典"], "入れるの項目数": 0, "入れるの小計": 0,
                "入れないの項目数": 0, "入れないの小計": 0,
                "数の付いていない項目数": 0, "単位の字が違う項目数": 0})
            if side == IRERU:
                b["入れるの項目数"] += 1
                b["入れるの小計"] += n
            elif side == IRENAI:
                b["入れないの項目数"] += 1
                b["入れないの小計"] += n
            else:
                b["数の付いていない項目数"] += 1
            if p["単位"] and p["単位"] != t["単位"]:
                b["単位の字が違う項目数"] += 1

        out_totals.append({
            "総数id": tid, "総数の宣言": total, "単位": t["単位"], "出典": t["出典"],
            "足した数_入れるだけ": strict, "足した数_入れないも": strict + extra,
            "差_入れるだけ": total - strict, "差_入れないも": total - strict - extra,
            "入れるの項目数": sum(1 for _, s, _ in mine if s == IRERU),
            "入れないの項目数": sum(1 for _, s, _ in mine if s == IRENAI),
            "数の付いていない項目数": len(unnumbered),
            "数の付いていない項目": unnumbered,
            "区分_入れるだけ": _category(len(unnumbered), total, strict),
            "区分_入れないも": _category(len(unnumbered), total, strict + extra),
            "出典の行ごとの小計": list(by_source.values()),
            "印_単位の字が総数と違う": unit_diff,
            "印_同じ項目の名前が2回": dup_names,
        })

    kind_counts = {k: 0 for k in side_of}
    for p, _, _ in usable:
        kind_counts[p["読みの種類"]] += 1
    return {
        "総数ごと": out_totals,
        "区分ごとの件数_入れるだけ": {c: sum(1 for t in out_totals if t["区分_入れるだけ"] == c) for c in CATS},
        "区分ごとの件数_入れないも": {c: sum(1 for t in out_totals if t["区分_入れないも"] == c) for c in CATS},
        "読みの種類ごとの項目数": kind_counts,
        "内訳の台帳の行数": len(parts),
        "別枠の件数": {r: sum(1 for b in betsu if b["理由"] == r) for r in BETSU},
        "別枠": betsu,
        "持たせていないもの": list(NOT_HELD),
    }


def exit_code(result: dict) -> int:
    clean = all(t["区分_入れるだけ"] == CAT_A and t["区分_入れないも"] == CAT_A for t in result["総数ごと"])
    return 0 if clean and not result["別枠"] else 3


def render(result: dict) -> str:
    """人が読む形。末尾の「持たせていないもの」は消す引数が無い。"""
    o: list[str] = []
    for t in result["総数ごと"]:
        o.append(f"■ {t['総数id']}  総数の宣言 {t['総数の宣言']:,} {t['単位']}(出典 {t['出典']})")
        o.append(f"  足した数   入れるだけ {t['足した数_入れるだけ']:,}({t['入れるの項目数']} 項目)"
                 f" / 入れないも {t['足した数_入れないも']:,}(+{t['入れないの項目数']} 項目)")
        o.append(f"  差         入れるだけ {t['差_入れるだけ']:,} / 入れないも {t['差_入れないも']:,}")
        o.append(f"  区分       入れるだけ {t['区分_入れるだけ']}")
        o.append(f"             入れないも {t['区分_入れないも']}")
        o.append(f"  数の付いていない項目 {t['数の付いていない項目数']} 件")
        for u in t["数の付いていない項目"]:
            o.append(f"    - {u['項目の名前']}({u['出典']})")
        o.append("  出典の行ごとの小計")
        for b in t["出典の行ごとの小計"]:
            o.append(f"    {b['出典']}: 入れる {b['入れるの項目数']} 項目 {b['入れるの小計']:,}"
                     f" / 入れない {b['入れないの項目数']} 項目 {b['入れないの小計']:,}"
                     f" / 数なし {b['数の付いていない項目数']} / 単位違い {b['単位の字が違う項目数']}")
        for u in t["印_単位の字が総数と違う"]:
            o.append(f"  印 単位の字が総数と違う: {u['項目の名前']} {u['数']:,} {u['単位']}({u['出典']})")
        for d in t["印_同じ項目の名前が2回"]:
            o.append(f"  印 同じ項目の名前が 2 回: {d['項目の名前']}({' / '.join(d['項目id'])})")
    o.append("■ 読みの種類ごとの項目数: "
             + " / ".join(f"{k} {v}" for k, v in result["読みの種類ごとの項目数"].items()))
    o.append(f"■ 別枠 {len(result['別枠'])} 件(内訳の台帳 {result['内訳の台帳の行数']} 行のうち。どの和にも入れていない)")
    for b in result["別枠"]:
        o.append(f"    行 {b['行']} {b['項目id']} {b['項目の名前']}: {b['理由']}")
    o.append("■ 持たせていないもの")
    o.extend(f"    - {x}" for x in result["持たせていないもの"])
    return "\n".join(o) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="総数の宣言と、内訳の数を足した数を横に置く")
    ap.add_argument("--totals", required=True, help="総数の台帳(CSV)")
    ap.add_argument("--parts", required=True, help="内訳の台帳(CSV)")
    ap.add_argument("--kinds", required=True, help="読みの種類の登録表(CSV)")
    ap.add_argument("--json", action="store_true", help="JSON で出す")
    a = ap.parse_args(argv)
    try:
        result = tally(read_table(a.totals, TOTAL_COLS), read_table(a.parts, PART_COLS),
                       read_table(a.kinds, KIND_COLS))
    except (PartSumError, OSError, UnicodeDecodeError) as e:
        print(f"止まった: {e}", file=sys.stderr)
        return 2
    out = json.dumps(result, ensure_ascii=False, indent=1) + "\n" if a.json else render(result)
    sys.stdout.buffer.write(out.encode("utf-8"))
    return exit_code(result)


if __name__ == "__main__":
    sys.exit(main())
