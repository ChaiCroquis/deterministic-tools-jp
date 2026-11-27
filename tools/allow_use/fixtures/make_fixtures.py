"""合成 fixture を作り直す(語も式も架空。実在の制度・名前・金額は入っていない)。

python fixtures/make_fixtures.py
"""
from __future__ import annotations

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ① 許可の台帳: 出どころは「手引き」(人が読む文書)と「実装」(コードの一覧)の 2 つ
NAMES_BOTH = ["tier", "tier_span", "cut0", "half_up", "steps", "lower", "upper"]
NAMES_CODE_ONLY = ["Num", "clip"]
NODES = ["Expression", "BinOp", "UnaryOp", "Add", "Sub", "Mult", "Div", "Pow", "USub", "Call", "Name", "Load",
         "Constant", "Subscript", "Attribute", "Compare", "Lt", "GtE", "IfExp", "Tuple", "List"]

allow = [["word", "kind", "origin", "source"]]
for w in NAMES_BOTH:
    allow.append([w, "名前", "手引き", "合成の手引き L12"])
for w in NAMES_BOTH + NAMES_CODE_ONLY:
    allow.append([w, "名前", "実装", "合成の実装 L30"])
for i, w in enumerate(NODES):
    allow.append([w, "構文の種類", "実装", f"合成の実装 L{31 + i // 8}"])
# 別枠に落ちる行
allow.append(["old_cut", "名前", "実装", ""])                      # 出典が空
allow.append(["mix", "関数", "実装", "合成の実装 L30"])            # 種別が 2 つの値以外
allow.append(["pick", "名前", "実装", "合成の実装 L30"])           # 同じ (語, 種別, 出どころ) が 2 行
allow.append(["pick", "名前", "実装", "合成の実装 L30"])

# ② 式の台帳: 主の束 = 式の一覧、他の束 = 行の式
exprs = [["expr_id", "bundle", "expr", "source"]]
MAIN = [
    ("E01", "tier(tbl, base)"),
    ("E02", "tier_span(tbl, day)"),
    ("E03", "base * rate"),
    ("E04", "total / 2"),
    ("E05", "half_up(a + b)"),
    ("E06", "cut0(steps(plan, w))"),
    ("E07", "row['amount'] * rate / 2 if flag else Num(0)"),
    ("E08", "half_up(base * rate)"),
    ("E09", "clip * qty * months"),          # clip は変数の名前として出るだけ(呼び出しではない)
    ("E10", "ghost(base)"),                  # 台帳に無い名前
    ("E11", "base * ("),                     # 読めない
    ("E12", "a and b"),                      # 台帳に無い構文の種類
    ("E13", "row.amount * rate"),
]
ROWS = [
    ("R01", "0.8 * w"),
    ("R02", "0.8 * w - 0.3 * ((w - 4000) / (9000 - 4000)) * w"),
    ("R03", "0.5 * w"),
    ("R04", "6100"),
    ("R05", "lower(0.45 * w, 5000)"),
    ("R06", "-w + 100"),
    ("R07", "w ** 2"),
    ("R08", "w +"),                          # 読めない
]
for i, (eid, text) in enumerate(MAIN):
    exprs.append([eid, "式の一覧", text, f"合成の式の表 {eid}.expr"])
for eid, text in ROWS:
    exprs.append([eid, "行の式", text, f"合成の数表 {eid}.expr_row"])
exprs.append(["R09", "行の式", "0.6 * w", ""])                     # 出典が空

# ③ 数え方の登録(1 行だけ)
HEAD3 = ["mode", "main_bundle", "pattern", "repl", "source"]
RULE = [r"(?<![\w.])(\d+\.\d+|\d+)(?![\w.])", r"Num('\1')"]
counting_raw = [HEAD3, ["書かれた字のまま", "式の一覧", "", "", "私の登録"]]
counting_rewritten = [HEAD3, ["書き換えの後", "式の一覧", *RULE, "合成の実装 L40"]]

# ④ 別の在り所
elsewhere = [
    ["word", "note", "source"],
    ["upper", "v = upper(v, alt)", "合成の実装 L22(steps の関数の中)"],
    ["tier", "t = tier(cells, x)", "合成の実装 L25(tier_span の関数の中)"],
    ["nobody", "x = nobody(y)", "合成の実装 L27"],                # 台帳に無い語
]

for name, rows in [("allow_a.csv", allow), ("exprs_a.csv", exprs), ("counting_raw.csv", counting_raw),
                   ("counting_rewritten.csv", counting_rewritten), ("elsewhere_a.csv", elsewhere)]:
    with open(HERE / name, "w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    print("wrote", name, len(rows) - 1, "rows")
