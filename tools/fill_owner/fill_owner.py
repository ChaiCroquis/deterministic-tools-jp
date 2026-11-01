"""fill_owner — 表の外に置いた項目を「誰が値を決めるか」「どの層の行になるか」の軸で並べ直す判定器。

分類の規則を道具が持たない。印から置き場を導く if 文は無く、**宣言された印の組み合わせを
置き場の登録表に当てるだけ**。登録表に無い組み合わせは別枠に出す(既定値を当てない)。
自然文を読まない。期限を計算しない。判断を起票しない。履歴を舐めない。値を引かない。
順位・良し悪し・難易度・優先度を付けない。入力を書き換えない。時計を読まない。

入力は 3 枚の CSV:
  問いの台帳     : 問い id / 求める値の名前 / 旧軸の値 / 旧軸の一覧 id / 外し方の記号 /
                   印 7 つ(はい・いいえ・宣言なし)/ 置き場が要求する欄の値 / 出典
  置き場の登録表 : 印の組み合わせ(7 つを | で並べる)/ 置き場の記号 / 外し方の記号 /
                   誰が決めるかの記号 / その置き場が要求する欄の名前 / 登録の出典
  新軸の定義     : 新軸の欄名 / 旧軸の欄名 / 出典(1 行だけ。新軸と旧軸が同じ欄名なら止まる)

使い方:
  python fill_owner.py init   <置き場ディレクトリ>
  python fill_owner.py check  <問いの台帳> <置き場の登録表> <新軸の定義>
  python fill_owner.py rows   <問いの台帳> <置き場の登録表> <新軸の定義>
  python fill_owner.py verify <問いの台帳> <置き場の登録表> <新軸の定義>

終了コード: 0 = 判定できた / 3 = 表の側が壊れていて 1 件も判定しない / 2 = 引数・読み書きの誤り
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

# ---- 宣言の語彙(ここに無い語を書くと止まる。既定値を当てる経路は無い)-------------------

MARK_COLS = ("印_行政一意", "印_主体内一意", "印_履歴依存", "印_人が読む",
             "印_起算日加算", "印_施行日確定", "印_法が決める")
MARK_LABELS = ("行政が誰でも同じ答えを出すか", "主体内では一意か", "履歴を舐めないと決まらないか",
               "人が読んで決めるか", "起算日 + N 日で書けるか", "施行日が決まっているか",
               "法が値を決めているか")
MARK_VALUES = ("はい", "いいえ", "宣言なし")

TOI_COLS = (("問い id", "求める値の名前", "旧軸の値", "旧軸の一覧 id", "外し方の記号")
            + MARK_COLS + ("要求する欄の値", "出典"))
OKIBA_COLS = ("印の組み合わせ", "置き場の記号", "外し方の記号", "誰が決めるか", "要求する欄の名前", "出典")
JIKU_COLS = ("新軸の欄名", "旧軸の欄名", "出典")

PLACE_MARKS = ("①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧")
PLACES = {
    "①": "① 公的層の行で埋まる",
    "②": "② 起算日 + N 日の式として公的層の行に入る(準整理可)",
    "③": "③ 第 2 層(主体ごと)の行で埋まる",
    "④": "④ case の属性として人が起票してから渡す",
    "⑤": "⑤ 数式側の状態機械へ閾値だけ供給する",
    "⑥": "⑥ 解釈メモ層から参照し、特例の順位の行として計算に入る場合だけ表に入る",
    "⑦": "⑦ 施行日が決まるまで登録だけして計算に使わない行",
    "⑧": "⑧ 置き場なし",
}

# 止まる理由コード 12 個 = 表の側 4(1 件も判定しない)+ 問いごとの別枠 8
TABLE_STOP = ("表が読めない", "軸が同じ", "登録表の鍵が壊れている", "登録表の欄が壊れている")
ASIDE = ("問い id の重複", "出典が空", "一覧 id が無い", "一覧の記載と違う",
         "外し方の記号が登録外", "宣言なしを含む", "組み合わせが登録外", "要求する欄が空")
REASONS = TABLE_STOP + ASIDE

NOT_DOING = {
    "分類の規則を持たない": "印から置き場を導く if 文が無い。置き場は登録表の行から写すだけで、"
                            "登録表に無い組み合わせは別枠に出し、既定値を当てない",
    "自然文を読まない": "求める値の名前や例示の文から印を推測する経路が無い。印は宣言された欄だけ",
    "期限を計算しない": "② は置き場を仕分けるだけで、起算日に N 日を足す経路も暦も休日表も持たない",
    "判断を起票しない": "④ は受け取る属性の名前を返すだけで、値を作る経路も既定値も無い",
    "履歴を舐めない": "⑤ は供給する閾値の名前を返すだけで、通算も待期も実装しない",
    "未定と未来を混ぜない": "⑦ は施行日が決まっていない行だけ。決まっている行は別の部品の仕事で、"
                            "分かれ目は印 1 つ",
    "順位を付けない": "置き場に良し悪し・難易度・優先度・着手の順を付ける経路が無い",
    "同じ軸で並べ直さない": "新軸の欄名が旧軸の欄名と同じなら止まる",
    "一覧 id の無い問いは判定しない": "旧軸の一覧 id が 3 つ組で書かれていない問いは別枠に出す",
    "値を引かない": "値の欄そのものを持たない。計算もしない",
    "人の名前を出さない": "誰が決めるかは登録表の記号だけで、人名も役職も持たない",
    "時計を読まない": "今日の日付を読む経路が無い。基準は入力の欄だけ",
    "入力を書き換えない": "verify が作る写しはメモリの中だけで、入力の表には 1 文字も書かない",
}


class Stop(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code, self.detail = code, detail


# ---- 読む ---------------------------------------------------------------------------------

def read_table(path: str | Path, cols: tuple[str, ...]) -> list[dict[str, str]]:
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8-sig")
    except OSError as e:
        raise Stop("表が読めない", f"{p.name} を開けない") from e
    rows = list(csv.DictReader(text.splitlines()))
    if not rows:
        raise Stop("表が読めない", f"{p.name} に行が無い")
    missing = [c for c in cols if c not in rows[0].keys()]
    if missing:
        raise Stop("表が読めない", f"{p.name} に列が無い: {' / '.join(missing)}")
    return [{c: (r.get(c) or "").strip() for c in cols} for r in rows]


def load_jiku(rows: list[dict[str, str]]) -> dict[str, str]:
    if len(rows) != 1:
        raise Stop("軸が同じ", f"新軸の定義は 1 行で書く(いま {len(rows)} 行)")
    r = rows[0]
    if not r["新軸の欄名"] or not r["旧軸の欄名"] or not r["出典"]:
        raise Stop("軸が同じ", "新軸の定義に空欄がある(新軸・旧軸・出典の 3 つを書く)")
    if r["新軸の欄名"] == r["旧軸の欄名"]:
        raise Stop("軸が同じ", f"新軸と旧軸が同じ欄名「{r['新軸の欄名']}」= 同じ軸での並べ直しは受け付けない")
    return r


def load_okiba(rows: list[dict[str, str]]) -> dict[tuple[str, ...], dict[str, str]]:
    table: dict[tuple[str, ...], dict[str, str]] = {}
    for i, r in enumerate(rows, 1):
        marks = tuple(x.strip() for x in r["印の組み合わせ"].split("|"))
        if len(marks) != len(MARK_COLS):
            raise Stop("登録表の鍵が壊れている", f"行 {i} の印が {len(marks)} 個(7 個で書く)")
        bad = [m for m in marks if m not in MARK_VALUES]
        if bad:
            raise Stop("登録表の鍵が壊れている", f"行 {i} の印に 3 値以外がある: {' / '.join(bad)}")
        if marks in table:
            raise Stop("登録表の鍵が壊れている", f"行 {i} の印の組み合わせが重複している")
        if r["置き場の記号"] not in PLACES:
            raise Stop("登録表の欄が壊れている", f"行 {i} の置き場の記号が登録外")
        for c in ("外し方の記号", "誰が決めるか", "要求する欄の名前", "出典"):
            if not r[c]:
                raise Stop("登録表の欄が壊れている", f"行 {i} の「{c}」が空")
        table[marks] = r
    if not table:
        raise Stop("登録表の鍵が壊れている", "登録表に行が無い")
    return table


# ---- 並べ直す -----------------------------------------------------------------------------

def _canon(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """行順で結果が動かないように、問い id を先頭にした全欄の組で並べ替える。"""
    return sorted(rows, key=lambda r: tuple(r[c] for c in TOI_COLS))


def sort_rows(toi: list[dict[str, str]], okiba: dict[tuple[str, ...], dict[str, str]],
              jiku: dict[str, str]) -> list[dict[str, str]]:
    """問いごとに 1 つだけ答えを付ける。置き場は登録表の行から写すだけ。"""
    kinds = {r["外し方の記号"] for r in okiba.values()}
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for r in _canon(toi):
        tid = r["問い id"]
        marks = tuple(r[c] for c in MARK_COLS)
        rec = okiba.get(marks)
        parts = r["旧軸の一覧 id"].split("#")
        reason = None
        if tid in seen:
            reason = "問い id の重複"
        elif not r["出典"]:
            reason = "出典が空"
        elif len(parts) != 3 or not all(p.strip() for p in parts):
            reason = "一覧 id が無い"
        elif parts[2].strip() != r["旧軸の値"]:
            reason = "一覧の記載と違う"
        elif any(m not in MARK_VALUES or m == "宣言なし" for m in marks):
            reason = "宣言なしを含む"
        elif rec is None:
            reason = "組み合わせが登録外"
        elif r["外し方の記号"] not in kinds:
            reason = "外し方の記号が登録外"
        elif rec["要求する欄の名前"] != "—" and not r["要求する欄の値"]:
            reason = "要求する欄が空"
        seen.add(tid)
        out.append({
            "問い id": tid,
            "求める値の名前": r["求める値の名前"],
            jiku["旧軸の欄名"]: r["旧軸の値"],
            "旧軸の一覧 id": r["旧軸の一覧 id"],
            jiku["新軸の欄名"]: "" if reason else PLACES[rec["置き場の記号"]],
            "別枠の理由": reason or "",
            "誰が決めるか": "" if reason else rec["誰が決めるか"],
            "要求する欄": "" if reason else rec["要求する欄の名前"],
            "要求する欄の値": r["要求する欄の値"],
            "原文の外し方の記号": r["外し方の記号"],
            "登録表の外し方の記号": "" if reason else rec["外し方の記号"],
            "出典": r["出典"],
        })
    return out


def tally(rows: list[dict[str, str]], jiku: dict[str, str]) -> dict[str, object]:
    new, old = jiku["新軸の欄名"], jiku["旧軸の欄名"]
    places = {PLACES[k]: 0 for k in PLACE_MARKS}
    aside = {k: 0 for k in ASIDE}
    by_old: dict[str, dict[str, int]] = {}
    kind_count: dict[str, int] = {}
    moved = 0
    for r in rows:
        key = f"別枠 / {r['別枠の理由']}" if r["別枠の理由"] else r[new]
        if r["別枠の理由"]:
            aside[r["別枠の理由"]] += 1
        else:
            places[r[new]] += 1
            if r["原文の外し方の記号"] != r["登録表の外し方の記号"]:
                moved += 1
        by_old.setdefault(r[old], {})
        by_old[r[old]][key] = by_old[r[old]].get(key, 0) + 1
        kind_count[r["原文の外し方の記号"]] = kind_count.get(r["原文の外し方の記号"], 0) + 1
    return {
        "分母(問いの件数)": len(rows),
        "8 値": places,
        "別枠": aside,
        f"{old}ごとの内訳": {k: dict(sorted(by_old[k].items())) for k in sorted(by_old)},
        "原文の外し方の記号ごとの件数": {k: kind_count[k] for k in sorted(kind_count)},
        "原文の記号と登録表の記号が違う問い": moved,
    }


def judge(toi: list[dict[str, str]], okiba: dict[tuple[str, ...], dict[str, str]],
          jiku: dict[str, str]) -> dict[str, object]:
    rows = sort_rows(toi, okiba, jiku)
    t = tally(rows, jiku)
    old, new = jiku["旧軸の欄名"], jiku["新軸の欄名"]
    core = {
        "判定": [[r["問い id"], r[new] or f"別枠 / {r['別枠の理由']}"] for r in rows],
        "集計": t,
        "軸": [old, new],
    }
    blob = json.dumps(core, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    n = int(t["分母(問いの件数)"])
    s8 = sum(t["8 値"].values())
    sa = sum(t["別枠"].values())
    so = sum(sum(v.values()) for v in t[f"{old}ごとの内訳"].values())
    return {
        "ok": True,
        "軸の定義": f"旧軸 = {old} / 新軸 = {new}(出典 {jiku['出典']})",
        **t,
        "件数の合計の検算": (f"8 値 {s8} + 別枠 {sa} = {s8 + sa} / 分母 {n}、"
                             f"{old}ごとの内訳の合計 {so} / 分母 {n}"),
        "合計が合う": s8 + sa == n and so == n,
        "判定部分の sha256": hashlib.sha256(blob.encode("utf-8")).hexdigest(),
        "しないこと": NOT_DOING,
    }


# ---- verify -------------------------------------------------------------------------------

def _answers(toi: list[dict[str, str]], okiba: dict[tuple[str, ...], dict[str, str]],
             jiku: dict[str, str]) -> dict[str, str]:
    """問い id ごとの答え。同じ id が 2 行あるときは先に来た 1 行(= 判定した方)を採る。"""
    new = jiku["新軸の欄名"]
    out: dict[str, str] = {}
    for r in sort_rows(toi, okiba, jiku):
        out.setdefault(r["問い id"], r[new] or f"別枠 / {r['別枠の理由']}")
    return out


def _unique_ids(toi: list[dict[str, str]]) -> set[str]:
    ids = [r["問い id"] for r in toi]
    return {i for i in ids if ids.count(i) == 1}


def _swap_mark(toi: list[dict[str, str]], tid: str, col: str, to: str) -> list[dict[str, str]]:
    """写しはメモリの中だけ。入力の表には書かない。"""
    return [({**r, col: to} if r["問い id"] == tid else dict(r)) for r in toi]


def _swap_okiba(okiba: dict[tuple[str, ...], dict[str, str]], marks: tuple[str, ...],
                to: str) -> dict[tuple[str, ...], dict[str, str]]:
    out = {k: dict(v) for k, v in okiba.items()}
    if marks in out:
        out[marks] = {**out[marks], "置き場の記号": to}
    return out


def verify(toi: list[dict[str, str]], okiba: dict[tuple[str, ...], dict[str, str]],
           jiku: dict[str, str]) -> dict[str, object]:
    a, b = judge(toi, okiba, jiku), judge(toi, okiba, jiku)
    rev = judge(list(reversed(toi)), {k: okiba[k] for k in reversed(list(okiba))}, jiku)
    base = _answers(toi, okiba, jiku)
    uniq = _unique_ids(toi)   # 写しは 1 行だけ替える。同じ id が 2 行ある問いは替えない

    # 4. 行政一意の印を 1 件だけ はい → いいえ に替え、登録表の行だけを差し替えて 2 通り出す
    one = next((r["問い id"] for r in _canon(toi)
                if r["問い id"] in uniq and r["印_行政一意"] == "はい"
                and base.get(r["問い id"]) == PLACES["①"]), None)
    four: dict[str, object] = {"替えた問い": one}
    if one is not None:
        flipped = _swap_mark(toi, one, "印_行政一意", "いいえ")
        src = next(r for r in _canon(flipped) if r["問い id"] == one)
        marks = tuple(src[c] for c in MARK_COLS)
        after1 = _answers(flipped, okiba, jiku)
        other = "⑧" if okiba.get(marks, {}).get("置き場の記号") != "⑧" else "④"
        after2 = _answers(flipped, _swap_okiba(okiba, marks, other), jiku)
        four |= {
            "替える前": base[one],
            "登録表そのまま": after1[one],
            "登録表の行だけ差し替え": after2[one],
            "登録表が指す先へ動く": (after1[one] != base[one] and after2[one] == PLACES[other]
                                     and after1[one] != after2[one]),
            "動いたのはこの問いだけ": sum(1 for k in base if base[k] != after1[k]) == 1,
        }

    # 5. 施行日確定の印を いいえ → はい に替えると ⑦ から ① へ移る
    two = next((r["問い id"] for r in _canon(toi)
                if r["問い id"] in uniq and r["印_施行日確定"] == "いいえ"
                and base.get(r["問い id"]) == PLACES["⑦"]), None)
    five: dict[str, object] = {"替えた問い": two}
    if two is not None:
        after = _answers(_swap_mark(toi, two, "印_施行日確定", "はい"), okiba, jiku)
        five |= {"替える前": base[two], "替えた後": after[two],
                 "⑦ から ① へ移る": base[two] == PLACES["⑦"] and after[two] == PLACES["①"],
                 "動いたのはこの問いだけ": sum(1 for k in base if base[k] != after[k]) == 1}

    return {
        "1 二度走りの sha256 が同じ": a["判定部分の sha256"] == b["判定部分の sha256"],
        "sha256": a["判定部分の sha256"],
        "2 3 表の行順を入れ替えても同じ": rev["判定部分の sha256"] == a["判定部分の sha256"],
        "3 件数の合計が合う": a["合計が合う"],
        "4 行政一意の印を 1 件替えると登録表が指す先へ移る": four,
        "5 施行日確定の印を 1 件替えると ⑦ から ① へ移る": five,
        "ok": bool(a["判定部分の sha256"] == b["判定部分の sha256"]
                   and rev["判定部分の sha256"] == a["判定部分の sha256"] and a["合計が合う"]
                   and four.get("登録表が指す先へ動く") and four.get("動いたのはこの問いだけ")
                   and five.get("⑦ から ① へ移る") and five.get("動いたのはこの問いだけ")),
    }


# ---- CLI ----------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="表の外に置いた項目を置き場の軸で並べ直す")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("init", help="合成のひな型 3 枚を書き出す")
    g.add_argument("dest")
    for name, helptext in (("check", "件数の内訳を出す"), ("rows", "問いごとの並べ直した一覧を出す"),
                           ("verify", "決定論かどうかを 5 つ見る")):
        s = sub.add_parser(name, help=helptext)
        s.add_argument("toi")
        s.add_argument("okiba")
        s.add_argument("jiku")
    args = ap.parse_args(argv)

    if args.cmd == "init":
        sys.path.insert(0, str(Path(__file__).resolve().parent / "fixtures"))
        import make_fixtures
        for p in make_fixtures.write_all(Path(args.dest)):
            print(f"wrote {p.name}")
        return 0
    try:
        toi = read_table(args.toi, TOI_COLS)
        okiba = load_okiba(read_table(args.okiba, OKIBA_COLS))
        jiku = load_jiku(read_table(args.jiku, JIKU_COLS))
    except Stop as e:
        print(json.dumps({"ok": False, "理由コード": e.code, "詳細": e.detail,
                          "8 値": {PLACES[k]: 0 for k in PLACE_MARKS},
                          "1 件も判定しない": True}, ensure_ascii=False, indent=1))
        return 3
    out: object = {"check": lambda: judge(toi, okiba, jiku),
                   "rows": lambda: sort_rows(toi, okiba, jiku),
                   "verify": lambda: verify(toi, okiba, jiku)}[args.cmd]()
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
