"""数表の JSON から、行の表(suuhyo/rows.csv)と比べ方の登録(suuhyo/setup.csv)を写す手伝い。
道具の本体ではない(本体は JSON を読まない)。

写すのは rule 1 つぶんの rule / meta.prefecture_ja / meta.fiscal_year / valid_from / valid_to の 5 つだけ。
額(payload)・出典の文・公表時点は写さない。回の id は meta.fiscal_year の値をそのまま写す(開始日から回を作らない)。
セグメントの全体は、--universe-round で指した回に行が在る地域の一覧を写す(人が決めた回。行ぜんたいからは作らない)。

使い方: python utsusu.py <rules_unified.json のパス> --rule 地域別最低賃金 --universe-round 2025 --edge 半開 --edge-source "..."
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--rule", required=True)
    ap.add_argument("--universe-round", required=True)
    ap.add_argument("--edge", required=True)
    ap.add_argument("--edge-source", required=True)
    a = ap.parse_args()
    name = Path(a.src).name
    doc = json.loads(Path(a.src).read_text(encoding="utf-8"))
    picked = [(i, r) for i, r in enumerate(doc["rows"]) if r["rule"] == a.rule]
    # 和名と selector の値が 1 対 1 であること(和名をセグメントの字に使うので、写す前に確かめる)
    pairs = {(next(iter(r["selector"].values())), r["meta"]["prefecture_ja"]) for _, r in picked}
    assert len(pairs) == len({p[0] for p in pairs}) == len({p[1] for p in pairs}), "selector と和名が 1 対 1 でない"
    out = HERE / "suuhyo"
    out.mkdir(exist_ok=True)
    rows = sorted((str(r["meta"]["fiscal_year"]), r["meta"]["prefecture_ja"], r["valid_from"], r["valid_to"], i) for i, r in picked)
    with (out / "rows.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["rule", "セグメント", "回", "開始日", "終了日", "出典"])
        for rd, seg, vf, vt, i in rows:
            w.writerow([a.rule, seg, rd, vf, vt, f"{name} rows[{i}]"])
    rounds = sorted({rd for rd, *_ in rows}, key=int)
    universe = sorted((seg, i) for rd, seg, _, _, i in rows if rd == a.universe_round)
    with (out / "setup.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["種類", "値", "出典"])
        for rd in rounds:
            w.writerow(["回", rd, f"{name} meta.fiscal_year の値(数の昇順に並べたのは私の決めごと)"])
        w.writerow(["区間の端", a.edge, a.edge_source])
        for seg, i in universe:
            w.writerow(["セグメント", seg, f"{name} rows[{i}].meta.prefecture_ja({a.universe_round} の回に行が在る地域)"])
    print(f"rows.csv: {len(rows)} 行 / 回 {len(rounds)} / セグメント {len(universe)}(元の行 {len(doc['rows'])} 行、generated {doc.get('generated')})")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
