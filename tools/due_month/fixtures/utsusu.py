"""数表の JSON から行の表(suuhyo/rows.csv)を写す手伝い。道具の本体ではない(本体は JSON を読まない)。

写すのは rule / valid_from / meta.next_revision_expected / meta.extractor の 4 つだけ。値・selector・出典の文は写さない。
4 つが同じ行は 1 行にまとめ、まとめた数を「元の行数」に、最初の行の添字を「出典」に書く。

使い方: python utsusu.py <rules_unified.json のパス>
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main(src: str) -> int:
    doc = json.loads(Path(src).read_text(encoding="utf-8"))
    groups: dict[tuple[str, str, str, str], list[int]] = {}
    for i, r in enumerate(doc["rows"]):
        meta = r.get("meta") or {}
        key = (r["rule"], r["valid_from"], meta.get("next_revision_expected") or "", meta.get("extractor") or "")
        groups.setdefault(key, []).append(i)
    out = HERE / "suuhyo" / "rows.csv"
    out.parent.mkdir(exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["rule", "valid_from", "予定", "出どころ", "元の行数", "出典"])
        for (rule, vf, plan, origin), idx in sorted(groups.items()):
            w.writerow([rule, vf, plan, origin, len(idx), f"rules_unified.json rows[{idx[0]}].meta.next_revision_expected"])
    print(f"{out.name}: {len(groups)} 行(元の行 {len(doc['rows'])} 行、generated {doc.get('generated')})")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1]))
