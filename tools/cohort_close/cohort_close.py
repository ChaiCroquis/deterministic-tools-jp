"""cohort_close — 数表の行がどう閉じるかを、人が台帳に書いた分だけで 1 行 1 件に並べる。

行の終わり方は 2 通り在る。有効期間の終わり(日付)で閉じる行と、対象の線(生年月日・
到達日・年齢・裁定の別)で閉じる行だ。後者は有効期間が開いたままなので、日付だけを見ると
「まだ続いている行」に見える。この部品は rule 1 件ごとに 4 値を付ける。

    (A) 日付で閉じる記載だけ在る
    (B) 対象の線で閉じる記載だけ在る
    (C) 両方在る
    (D) 読んだ範囲に閉じ方の記載なし

持たせていないもの: 線を引いた理由を当てる経路 / 行を消してよいかを決める経路 / いつ対象者が
いなくなるかを当てる経路 / 年齢から生年月日を逆算する経路 / 年度生まれを日付に直す経路 /
語の似かたから記号を当てる経路 / 率・合計の 1 値 / 通信 / 時計を読む経路 / 入力を書き換える
経路 / float。

    python cohort_close.py init   ひな型/
    python cohort_close.py check  行.csv 線.csv 記号.csv 収録.csv
    python cohort_close.py report 行.csv 線.csv 記号.csv 収録.csv
    python cohort_close.py verify 行.csv 線.csv 記号.csv 収録.csv
    python cohort_close.py side   行.csv 線.csv 記号.csv 収録.csv <基準日> <生年月日>

終了コード: 0 = 止まらず別枠 0 件 / 3 = 止まった・別枠が在る・verify が合わない / 2 = 表として読めない
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

ROW_COLS = ("rule_id", "end_text", "none_note", "source")
LINE_COLS = ("rule_id", "line_text", "side_word", "symbol", "source")
SYMBOL_COLS = ("symbol", "means", "source")
COVER_COLS = ("rule_id", "state", "source")

NONE_NOTE = "閉じ方の記載なし"          # 行の台帳の none_note に書ける唯一の語
STATES = ("収録", "未収録", "記載なし")   # 収録の台帳の state
NO_COVER_ROW = "収録の台帳に行が無い"     # 書かれた「記載なし」とは別の値
SYM_BIRTH = "生年月日の線"                # 補助の判定が読む唯一の記号
SYM_UNSPLIT = "範囲か閉じる線か書き分けなし"   # この記号の線は区分に入れない

KUBUN = ("(A) 日付で閉じる記載だけ在る",
         "(B) 対象の線で閉じる記載だけ在る",
         "(C) 両方在る",
         "(D) 読んだ範囲に閉じ方の記載なし")
# 別枠は上から順に当たり、4 値より先に当たる。5 つは rule の単位、6 つめだけ線の単位
EXTRAS = ("id の重複",
          "出典が空",
          "登録表に無い記号",
          "範囲か閉じる線か書き分けなし の記号が付いた線",
          "閉じる記載と 閉じ方の記載なし が同時に書かれた")
ORPHAN = "台帳に無い rule id を指す線"

STOPS = ("記号の登録表が空",
         "記号の登録表の行の出典が空",
         "収録の状態が決めた 3 つの外",
         "none_note が決めた語の外")

SIDE_IN, SIDE_OUT = "線の内側", "線の外側"
SIDE_NO_WORD = "含む側の語なし"
SIDE_UNREADABLE = "読めない線"
_SIDE_FORM = re.compile(r"(\d{4}-\d{2}-\d{2}) (以前|以降)(生まれ|生まれのみ)?")

NOT_HELD = {
    "理由を当てない": "線を引いた理由の欄が無い。線の文字列と含む側の語を写すだけ",
    "消してよいかを決めない": "rule を「まだ要る / もう要らない」の 1 値に丸める列が無い",
    "対象者がいなくなる時期を当てない": "寿命も人数も推計しない。基準日は出力に写すだけで判定に使わない",
    "年齢や年度生まれを日付に直さない": "補助の判定が読むのは `YYYY-MM-DD 以前` と `YYYY-MM-DD 以降` の 2 形だけ",
    "語の似かたから記号を当てない": "記号は線の台帳の欄から取るだけで、線の文字列は判定に入らない",
    "率や合計の 1 値を返さない": "返すのは区分ごとの件数と、区分 × 収録の状態の内訳だけ",
    "取りに行かない": "通信の経路が無い。読むのは渡された 4 表だけ",
    "時計を読まない": "現在時刻を読む呼び出しを持たない",
    "入力を書き換えない": "verify が作る写しはメモリの中だけ",
    "float を使わない": "件数は整数、ほかは文字列",
}


class Unreadable(Exception):
    """表として読めない(終了コード 2)。"""


class Stopped(Exception):
    """1 件も数えずに止まった結果から、区分や sha256 を取りに行った。"""


# ---------------------------------------------------------------- 読む

def read_table(path: str | Path, cols: tuple[str, ...]) -> list[list[str]]:
    p = Path(path)
    if not p.exists():
        raise Unreadable(f"ファイルが無い: {p.name}")
    with p.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        raise Unreadable(f"行が無い: {p.name}")
    if tuple(c.strip() for c in rows[0]) != cols:
        raise Unreadable(f"列が決めた並びでない: {p.name}(要る列 = {' / '.join(cols)})")
    out = []
    for i, r in enumerate(rows[1:], 2):
        if not any(c.strip() for c in r):
            continue
        if len(r) != len(cols):
            raise Unreadable(f"列の数が合わない: {p.name} {i} 行目")
        out.append([c.strip() for c in r])
    return out


def load(rows_p, lines_p, symbols_p, cover_p) -> tuple[list, list, list, list]:
    return (read_table(rows_p, ROW_COLS), read_table(lines_p, LINE_COLS),
            read_table(symbols_p, SYMBOL_COLS), read_table(cover_p, COVER_COLS))


def _shape(rows, lines, symbols, cover) -> None:
    """表として読めない形を先に落とす。"""
    if not rows:
        raise Unreadable("行の台帳に rule が 1 件も無い")
    for name, table in (("行の台帳", rows), ("線の台帳", lines), ("収録の台帳", cover)):
        if any(not r[0] for r in table):
            raise Unreadable(f"{name}に rule id が空の行が在る")
    if any(not ln[1] for ln in lines):
        raise Unreadable("線の台帳に線の文字列が空の行が在る")
    syms = [s[0] for s in symbols]
    if len(set(syms)) != len(syms):
        raise Unreadable("記号の登録表に同じ記号が 2 行在る")
    cids = [c[0] for c in cover]
    if len(set(cids)) != len(cids):
        raise Unreadable("収録の台帳に同じ rule id が 2 行在る")
    known = {r[0] for r in rows}
    if any(c not in known for c in cids):
        raise Unreadable("収録の台帳の rule id が行の台帳に無い")


def _stop_reasons(rows, symbols, cover) -> list[str]:
    reasons = []
    if not symbols:
        reasons.append(STOPS[0])
    if any(not s[2] for s in symbols):
        reasons.append(STOPS[1])
    if any(c[1] not in STATES for c in cover):
        reasons.append(STOPS[2])
    if any(r[2] not in ("", NONE_NOTE) for r in rows):
        reasons.append(STOPS[3])
    return reasons


# ---------------------------------------------------------------- 判定

def judge(rows, lines, symbols, cover) -> dict:
    """rule 1 件ごとに 4 値か別枠を付ける。入力は書き換えない。"""
    _shape(rows, lines, symbols, cover)
    reasons = _stop_reasons(rows, symbols, cover)
    if reasons:
        return {"ok": False, "止まった理由": reasons}
    registered = {s[0] for s in symbols}
    cover_of = {c[0]: c for c in cover}
    seen: dict[str, int] = {}
    for r in rows:
        seen[r[0]] = seen.get(r[0], 0) + 1
    rule_ids = sorted(seen)
    first_row = {}
    for r in rows:
        first_row.setdefault(r[0], r)

    rules = []
    for rid in rule_ids:
        row = first_row[rid]
        mine = sorted((ln for ln in lines if ln[0] == rid), key=lambda x: x[1:])
        cov = cover_of.get(rid)
        state = cov[1] if cov else NO_COVER_ROW
        has_end = bool(row[1])
        has_line = bool(mine)
        if seen[rid] > 1:
            value = EXTRAS[0]
        elif not row[3] or any(not ln[4] for ln in mine) or (cov is not None and not cov[2]):
            value = EXTRAS[1]
        elif any(ln[3] not in registered for ln in mine):
            value = EXTRAS[2]
        elif any(ln[3] == SYM_UNSPLIT for ln in mine):
            value = EXTRAS[3]
        elif row[2] == NONE_NOTE and (has_end or has_line):
            value = EXTRAS[4]
        elif has_end and has_line:
            value = KUBUN[2]
        elif has_line:
            value = KUBUN[1]
        elif has_end:
            value = KUBUN[0]
        else:
            value = KUBUN[3]
        no_word = [ln[1] for ln in mine if not ln[2]]
        rules.append({
            "rule_id": rid, "区分": value, "収録の状態": state,
            "有効期間の終わりの記載": row[1],
            "線": [{"線の文字列": ln[1], "含む側の語": ln[2], "記号": ln[3], "出典": ln[4]}
                  for ln in mine],
            "含む側の語なし": bool(no_word) and value in KUBUN[1:3],
            "出典": row[3],
        })
    orphans = sorted({ln[0] for ln in lines if ln[0] not in seen})
    return {"ok": True, "rules": rules, "台帳に無い rule id": orphans,
            "線の台帳の行数": len(lines)}


def _need(result: dict) -> None:
    if not result.get("ok"):
        raise Stopped("止まった結果に区分は無い: " + " / ".join(result.get("止まった理由", [])))


def counts(result: dict) -> dict:
    """区分ごとの件数と、区分 × 収録の状態の内訳。"""
    _need(result)
    four = {k: 0 for k in KUBUN}
    extra = {k: 0 for k in EXTRAS}
    cross = {k: {s: 0 for s in STATES + (NO_COVER_ROW,)} for k in KUBUN}
    for r in result["rules"]:
        if r["区分"] in four:
            four[r["区分"]] += 1
            cross[r["区分"]][r["収録の状態"]] += 1
        else:
            extra[r["区分"]] += 1
    return {"4 値": four, "別枠": extra, "区分 × 収録の状態": cross}


def fingerprint(result: dict) -> str:
    """判定部分(rule id・区分・収録の状態・印・台帳に無い id)の sha256。"""
    _need(result)
    core = [[r["rule_id"], r["区分"], r["収録の状態"], r["含む側の語なし"]]
            for r in result["rules"]]
    blob = json.dumps([core, result["台帳に無い rule id"]], ensure_ascii=False,
                      separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def check(rows, lines, symbols, cover) -> dict:
    result = judge(rows, lines, symbols, cover)
    if not result["ok"]:
        out = {"ok": False, "止まった理由": result["止まった理由"],
               "4 値": {k: 0 for k in KUBUN}, "別枠": {k: 0 for k in EXTRAS}}
        out.update(NOT_HELD)
        return out
    c = counts(result)
    n_rules = len(result["rules"])
    n_four, n_extra = sum(c["4 値"].values()), sum(c["別枠"].values())
    used = sum(len(r["線"]) for r in result["rules"])
    out = {
        "ok": True,
        "rule の件数": n_rules,
        "4 値": c["4 値"],
        "別枠": c["別枠"],
        ORPHAN: {"rule id の数": len(result["台帳に無い rule id"]),
                 "線の行数": result["線の台帳の行数"] - used},
        "区分 × 収録の状態": c["区分 × 収録の状態"],
        "含む側の語なし の印が付いた rule": sum(1 for r in result["rules"] if r["含む側の語なし"]),
        "件数の合計の検算": f"4 値 {n_four} + 別枠 {n_extra} = {n_four + n_extra} / rule の件数 {n_rules}",
    }
    out.update(NOT_HELD)
    return out


def report(rows, lines, symbols, cover) -> dict:
    result = judge(rows, lines, symbols, cover)
    out = check(rows, lines, symbols, cover)
    if result["ok"]:
        out["rule ごとの一覧"] = result["rules"]
        out["判定部分の sha256"] = fingerprint(result)
    return out


# ---------------------------------------------------------------- 補助(線のどちら側か)

def _iso(text: str, what: str) -> str:
    try:
        date.fromisoformat(text)
    except ValueError:
        raise Unreadable(f"{what}が YYYY-MM-DD でない: {text}") from None
    return text


def side_of(line_text: str, side_word: str, symbol: str, birth: str) -> str:
    """生年月日の線 1 本について、その生年月日が線のどちら側かを返す。

    読むのは `YYYY-MM-DD 以前` / `YYYY-MM-DD 以降` の 2 形だけ(後ろの「生まれ」「生まれのみ」は
    在ってよい)。境目ちょうどの日は含む側の語に従い、語が無ければどの日でも止まる。
    """
    _iso(birth, "生年月日")
    if symbol != SYM_BIRTH:
        return SIDE_UNREADABLE
    m = _SIDE_FORM.fullmatch(line_text)
    if not m:
        return SIDE_UNREADABLE
    try:
        date.fromisoformat(m.group(1))
    except ValueError:
        return SIDE_UNREADABLE
    if not side_word:
        return SIDE_NO_WORD
    if side_word != m.group(2):
        return SIDE_UNREADABLE
    edge = m.group(1)   # ISO の日付は文字列のまま大小を比べられる
    if side_word == "以前":
        return SIDE_IN if birth <= edge else SIDE_OUT
    return SIDE_IN if birth >= edge else SIDE_OUT


def side(rows, lines, symbols, cover, asof: str, birth: str) -> dict:
    """生年月日の線が付いた rule ごとに、その人が線のどちら側かを並べる。"""
    _iso(asof, "基準日")
    _iso(birth, "生年月日")
    result = judge(rows, lines, symbols, cover)
    _need(result)
    out = []
    for r in result["rules"]:
        if r["区分"] not in KUBUN:
            continue
        for ln in r["線"]:
            if ln["記号"] == SYM_BIRTH:
                out.append({"rule_id": r["rule_id"], "線の文字列": ln["線の文字列"],
                            "含む側の語": ln["含む側の語"],
                            "判定": side_of(ln["線の文字列"], ln["含む側の語"], ln["記号"], birth),
                            "出典": ln["出典"]})
    return {"ok": True, "基準日(写すだけで判定に使わない)": asof, "生年月日": birth,
            "生年月日の線": out}


# ---------------------------------------------------------------- verify

def _shift(iso: str, days: int) -> str:
    return date.fromordinal(date.fromisoformat(iso).toordinal() + days).isoformat()


def verify(rows, lines, symbols, cover) -> dict:
    """この手続きが決定論かを 5 つ測る。写しはメモリの中だけ。"""
    base = judge(rows, lines, symbols, cover)
    _need(base)
    fp = fingerprint(base)
    # ① 二度走り
    v1 = fingerprint(judge(rows, lines, symbols, cover)) == fp
    # ② 線の台帳の行順の入れ替え(逆順 / 1 つ回す)
    perms = [list(reversed(lines)), lines[1:] + lines[:1]]
    v2 = all(fingerprint(judge(rows, p, symbols, cover)) == fp for p in perms)
    # ③ 合計
    c = counts(base)
    v3 = (sum(c["4 値"].values()) + sum(c["別枠"].values()) == len(base["rules"])
          and all(sum(c["区分 × 収録の状態"][k].values()) == c["4 値"][k] for k in KUBUN))
    # ④ 線 1 行を消す
    value_of = {r["rule_id"]: r["区分"] for r in base["rules"]}
    moved, v4 = 0, True
    for i, ln in enumerate(lines):
        rid = ln[0]
        if value_of.get(rid) not in KUBUN[1:3] or sum(1 for x in lines if x[0] == rid) != 1:
            continue
        after = {r["rule_id"]: r["区分"]
                 for r in judge(rows, lines[:i] + lines[i + 1:], symbols, cover)["rules"]}
        want = KUBUN[3] if value_of[rid] == KUBUN[1] else KUBUN[0]
        changed = [k for k in value_of if after[k] != value_of[k]]
        v4 = v4 and changed == [rid] and after[rid] == want
        moved += 1
    # ⑤ 補助の判定を境目の前日・当日・翌日に置く
    tried, v5 = 0, True
    for ln in lines:
        m = _SIDE_FORM.fullmatch(ln[1])
        if ln[3] != SYM_BIRTH or not m or ln[2] != m.group(2):
            continue
        days = [_shift(m.group(1), d) for d in (-1, 0, 1)]
        got = [side_of(ln[1], ln[2], ln[3], d) for d in days]
        want = [SIDE_IN, SIDE_IN, SIDE_OUT] if ln[2] == "以前" else [SIDE_OUT, SIDE_IN, SIDE_IN]
        blank = [side_of(ln[1], "", ln[3], d) for d in days]
        v5 = v5 and got == want and blank == [SIDE_NO_WORD] * 3
        tried += 1
    checks = {"① 二度走りの sha256 が同一": v1,
              "② 線の台帳の行順を入れ替えても同一": v2,
              "③ 4 値 + 別枠 = rule の件数、内訳の合計 = 区分の件数": v3,
              "④ 線 1 行を消すとその rule だけが動く": v4,
              "⑤ 境目の前日・当日・翌日で、語の無い線は 3 日とも止まる": v5}
    return {"ok": all(checks.values()), "検査": checks, "判定部分の sha256": fp,
            "④ で消してみた線の数": moved, "⑤ で試した線の数": tried}


# ---------------------------------------------------------------- CLI

TEMPLATES = {
    "rows.csv": [ROW_COLS, ("R01", "合成の終わりの記載(架空)", "", "合成のメモ(架空)L1")],
    "lines.csv": [LINE_COLS, ("R02", "1970-01-01 以前生まれのみ", "以前", SYM_BIRTH,
                              "合成のメモ(架空)L2")],
    "symbols.csv": [SYMBOL_COLS,
                    (SYM_BIRTH, "生年月日で引かれた線", "合成の登録のメモ(架空)L1"),
                    ("到達日の線", "ある年齢に到達した日で引かれた線", "合成の登録のメモ(架空)L2"),
                    ("年齢の線", "年齢で引かれた線", "合成の登録のメモ(架空)L3"),
                    ("裁定の別", "新規か既存かの別で引かれた線", "合成の登録のメモ(架空)L4"),
                    ("文書に閉じると書いてある", "文書がそう書いている", "合成の登録のメモ(架空)L5"),
                    (SYM_UNSPLIT, "対象の範囲か閉じる線かが書き分けられていない",
                     "合成の登録のメモ(架空)L6")],
    "coverage.csv": [COVER_COLS, ("R01", "収録", "合成の収録のメモ(架空)L1")],
}


def write_templates(folder: str | Path) -> list[str]:
    d = Path(folder)
    d.mkdir(parents=True, exist_ok=True)
    for name, table in TEMPLATES.items():
        with (d / name).open("w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows(table)
    return sorted(TEMPLATES)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cohort_close", description="数表の行の閉じ方を 1 行 1 件に並べる")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").add_argument("folder")
    for name in ("check", "report", "verify", "side"):
        p = sub.add_parser(name)
        for a in ("rows", "lines", "symbols", "coverage"):
            p.add_argument(a)
        if name == "side":
            p.add_argument("asof")
            p.add_argument("birth")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "init":
            out = {"ok": True, "書いたひな型": write_templates(args.folder)}
        else:
            tables = load(args.rows, args.lines, args.symbols, args.coverage)
            if args.cmd == "side":
                out = side(*tables, args.asof, args.birth)
            else:
                out = {"check": check, "report": report, "verify": verify}[args.cmd](*tables)
    except Unreadable as e:
        print(json.dumps({"ok": False, "表として読めない": str(e)}, ensure_ascii=False, indent=1))
        return 2
    except Stopped as e:
        print(json.dumps({"ok": False, "止まった": str(e)}, ensure_ascii=False, indent=1))
        return 3
    print(json.dumps(out, ensure_ascii=False, indent=1))
    if not out.get("ok"):
        return 3
    if args.cmd in ("check", "report"):
        dirty = sum(out["別枠"].values()) + out[ORPHAN]["rule id の数"]
        return 3 if dirty else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
