"""change_slot — 数表の「改定」の記載を、確認をどこに置くかの枠に割り振って 1 行 1 件の一覧にする判定器。

次にいつ動くかを計算しない。日付を補完しない。値を引かない。今日を読まない。
**種別を記載の文字列から推測しない**(「不定期」「通達」「固定」のような語を見て種別を当てる
辞書も regex も持たない。種別は台帳に宣言された記号だけを読む)。要照合を確定として扱わない。
改定の内容を要約しない。優先度・重要度・手間の見積りを付けない。実行の履歴を読まない。
行を足さない・閉じない(渡す先の記号を返すだけ)。入力を書き換えない。

入力は 3 枚の CSV:
  改定の台帳         : rule id / 領域 / 改定の記載(原文の文字列をそのまま写す)/ 種別記号 /
                       時期の欄(YYYY-MM / MM-DD / 記載なし の 3 形)/
                       地域で発効日が違うか(はい / いいえ / 宣言なし)/ 対象記号 /
                       照合の印(照合済 / 要照合)/ 公表する側(機関の名前)/
                       置き所が要求する欄の値 / 出典(ファイル名 + 行番号)
  置き場の登録表     : 種別記号 / 次に動く時期が言えるか(言える / 言えない / 動かない / 済み)/
                       確認の置き所の記号(定例の枠 / 随時の枠 / 置かない / 施行日が決まるまで保留)/
                       要求する欄の名前 / 登録の出典
  変わる対象の登録表 : 対象記号 / 直す場所の記号 / 再検証の範囲の記号 / 出典

使い方:
  python change_slot.py init   <置き場ディレクトリ>
  python change_slot.py check  <改定の台帳> <置き場の登録表> <変わる対象の登録表>
  python change_slot.py rows   <改定の台帳> <置き場の登録表> <変わる対象の登録表>
  python change_slot.py verify <改定の台帳> <置き場の登録表> <変わる対象の登録表>

終了コード: 0 = 割り振れた / 3 = 表の側が壊れていて 1 件も割り振らない / 2 = 引数・読み書きの誤り
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

# ---- 宣言の語彙(ここに無い語を書くと止まるか別枠に出る。既定値を当てる経路は無い)---------

KAITEI_COLS = ("rule id", "領域", "改定の記載", "種別記号", "時期の欄", "地域で発効日が違うか",
               "対象記号", "照合の印", "公表する側", "置き所が要求する欄の値", "出典")
OKIBA_COLS = ("種別記号", "次に動く時期が言えるか", "確認の置き所の記号", "要求する欄の名前", "登録の出典")
TAISHOU_COLS = ("対象記号", "直す場所の記号", "再検証の範囲の記号", "出典")

TIMING_FORMS = ("年月", "月日", "記載なし")      # 時期の欄の 3 形。これ以外は別枠
REGION_VALUES = ("はい", "いいえ", "宣言なし")
MATCH_VALUES = ("照合済", "要照合")
SAYABLE = ("言える", "言えない", "動かない", "済み")
SLOTS = ("定例の枠", "随時の枠", "置かない", "施行日が決まるまで保留")
FIX_PLACES = ("行の値", "行の形", "式の実装", "行の追加", "行の閉じ")
ADD_OR_CLOSE = ("行の追加", "行の閉じ")

PLACE_MARKS = ("①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨")
PLACES = {
    "①": "① 定例の枠に置く(時期が月日まで書かれている)",
    "②": "② 定例の枠に置くが時期は年月までで日は書かれていない",
    "③": "③ 定例だが発効日が地域ごとに違うので枠を地域ごとに割る(割った先の値は入れない)",
    "④": "④ 随時の枠(時期を書かない)",
    "⑤": "⑤ 済んだ一回限りの改正(記載は過去の時期。確認の枠に置かない)",
    "⑥": "⑥ 新設・廃止・期間限定(行の追加または行の閉じが要る側へ渡す)",
    "⑦": "⑦ 将来の施行日が書かれている(確認の枠だけ置いて値は入れない)",
    "⑧": "⑧ 施行日未定(枠に置けない)",
    "⑨": "⑨ 動かない(固定・法定。確認の枠に置かない)",
}

# 公表している割り振りの表。鍵は 2 つとも **登録表の欄** で、改定の記載の文字列は入らない。
# 登録表の 1 行を差し替えれば、同じ種別の rule が別の枠へ動く(= 行き先は登録表が決める)。
FRAME_TABLE = {
    ("言える", "定例の枠"): "定例",
    ("言えない", "随時の枠"): "随時",
    ("済み", "置かない"): "済み",
    ("動かない", "置かない"): "動かない",
    ("言える", "施行日が決まるまで保留"): "将来",
    ("言えない", "施行日が決まるまで保留"): "未定",
}

# 止まる理由コード 14 個 = 表の側 5(1 件も割り振らない)+ rule ごとの別枠 9
TABLE_STOP = ("表が読めない", "登録表の鍵が壊れている", "登録表の欄が壊れている",
              "枠の組み合わせが登録外", "対象の登録表が壊れている")
ASIDE = ("rule id の重複", "出典が空", "時期の欄が 3 形でない", "地域の印が宣言なし",
         "種別記号が登録外", "対象記号が登録外", "照合の印が要照合",
         "置き所が要求する欄が空", "定例の枠なのに時期が記載なし")
REASONS = TABLE_STOP + ASIDE

NOT_DOING = {
    "種別を記載の文字列から推測しない": "「不定期」「通達」「固定」のような語を見て種別を当てる辞書も "
                                        "regex も持たない。種別は台帳に宣言された記号だけを読み、"
                                        "登録表に無い記号は別枠に出す",
    "今日を読まない": "次の改定までの残りを出さない。過去か未来かも判定しない。基準は入力の欄だけ",
    "日付を計算しない": "暦も休日表も年度表も持たない。年度から年度初めの日を作る経路が無く、"
                        "「10 月頃」を日に直す経路も無い",
    "要照合を確定として扱わない": "照合の印が要照合の行は 9 値に入れず別枠に出す",
    "記載の無い時期を埋めない": "時期の欄の記載なしを既定値で補う経路が無い",
    "値を引かない": "値(料率・金額)の欄そのものを持たない。計算もしない",
    "改定の内容を要約しない": "改定の記載は写すだけで、中身を解釈する経路が無い",
    "優先度を付けない": "大事な改定・軽い改定・着手の順・手間の見積りの語彙を持たない",
    "網羅と言わない": "件数は入力の件数だけを返し、割合にしない",
    "実行の履歴を読まない": "道具が何回動いたかを読む経路が無い。読むのは制度側の記載だけ",
    "行を閉じない・足さない": "⑥ は渡す先の記号(行の追加 / 行の閉じ)を返すだけ",
    "人の名前・役職を出さない": "公表する側は機関の名前の欄だけで、人名も役職も持たない",
    "枠を道具が決めない": "確認の置き所は登録表の種別行から写すだけ。登録表の 1 行を差し替えれば "
                          "同じ種別の rule が別の枠へ動く",
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
        raise Stop("表が読めない", f"{p.name} に列が無い: {len(missing)} 列")
    return [{c: (r.get(c) or "").strip() for c in cols} for r in rows]


def timing_form(s: str) -> str:
    """時期の欄の形を 3 つのどれかに言う。暦を持たないので月や日の値の範囲は見ない。"""
    if s == "記載なし":
        return "記載なし"
    parts = s.split("-")
    if len(parts) == 2 and all(p.isascii() and p.isdigit() for p in parts):
        if (len(parts[0]), len(parts[1])) == (4, 2):
            return "年月"
        if (len(parts[0]), len(parts[1])) == (2, 2):
            return "月日"
    return ""


def load_okiba(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    table: dict[str, dict[str, str]] = {}
    for i, r in enumerate(rows, 1):
        kind = r["種別記号"]
        if not kind:
            raise Stop("登録表の鍵が壊れている", f"行 {i} の種別記号が空")
        if kind in table:
            raise Stop("登録表の鍵が壊れている", f"行 {i} の種別記号が重複している")
        if r["次に動く時期が言えるか"] not in SAYABLE:
            raise Stop("登録表の鍵が壊れている", f"行 {i} の「次に動く時期が言えるか」が 4 値以外")
        if r["確認の置き所の記号"] not in SLOTS:
            raise Stop("登録表の鍵が壊れている", f"行 {i} の確認の置き所の記号が 4 値以外")
        for c in ("要求する欄の名前", "登録の出典"):
            if not r[c]:
                raise Stop("登録表の欄が壊れている", f"行 {i} の「{c}」が空")
        pair = (r["次に動く時期が言えるか"], r["確認の置き所の記号"])
        if pair not in FRAME_TABLE:
            raise Stop("枠の組み合わせが登録外",
                       f"行 {i} の組み合わせは公表している割り振りの表に無い")
        table[kind] = r
    if not table:
        raise Stop("登録表の鍵が壊れている", "置き場の登録表に行が無い")
    return table


def load_taishou(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    table: dict[str, dict[str, str]] = {}
    for i, r in enumerate(rows, 1):
        key = r["対象記号"]
        if not key:
            raise Stop("対象の登録表が壊れている", f"行 {i} の対象記号が空")
        if key in table:
            raise Stop("対象の登録表が壊れている", f"行 {i} の対象記号が重複している")
        if r["直す場所の記号"] not in FIX_PLACES:
            raise Stop("対象の登録表が壊れている", f"行 {i} の直す場所の記号が登録外")
        for c in ("再検証の範囲の記号", "出典"):
            if not r[c]:
                raise Stop("対象の登録表が壊れている", f"行 {i} の「{c}」が空")
        table[key] = r
    if not table:
        raise Stop("対象の登録表が壊れている", "変わる対象の登録表に行が無い")
    return table


# ---- 割り振る -----------------------------------------------------------------------------

def _canon(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """行順で結果が動かないように、全欄の組で並べ替える。"""
    return sorted(rows, key=lambda r: tuple(r[c] for c in KAITEI_COLS))


def _required_missing(r: dict[str, str], need: str) -> bool:
    """置き所が要求する欄が埋まっているか。名前が台帳の列名ならその列、そうでなければ汎用の欄。"""
    if need == "—":
        return False
    if need in KAITEI_COLS:
        return not r[need]
    return not r["置き所が要求する欄の値"]


def slot_rows(kaitei: list[dict[str, str]], okiba: dict[str, dict[str, str]],
              taishou: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    """rule ごとに 1 つだけ答えを付ける。確認の置き所は登録表の種別行から写すだけ。"""
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for r in _canon(kaitei):
        rid = r["rule id"]
        form = timing_form(r["時期の欄"])
        reg = okiba.get(r["種別記号"])
        tgt = taishou.get(r["対象記号"])
        reason = None
        if rid in seen:
            reason = "rule id の重複"
        elif not r["出典"]:
            reason = "出典が空"
        elif not form:
            reason = "時期の欄が 3 形でない"
        elif r["地域で発効日が違うか"] not in REGION_VALUES or r["地域で発効日が違うか"] == "宣言なし":
            reason = "地域の印が宣言なし"
        elif reg is None:
            reason = "種別記号が登録外"
        elif tgt is None:
            reason = "対象記号が登録外"
        elif r["照合の印"] not in MATCH_VALUES or r["照合の印"] == "要照合":
            reason = "照合の印が要照合"
        elif _required_missing(r, reg["要求する欄の名前"]):
            reason = "置き所が要求する欄が空"
        seen.add(rid)

        mark = ""
        if reason is None and reg is not None and tgt is not None:
            frame = FRAME_TABLE[(reg["次に動く時期が言えるか"], reg["確認の置き所の記号"])]
            if frame == "定例":
                if r["地域で発効日が違うか"] == "はい":
                    mark = "③"      # 全国 1 本の時期が書けないのが当たり前の行。記載なしでも別枠にしない
                elif form == "月日":
                    mark = "①"
                elif form == "年月":
                    mark = "②"
                else:
                    reason = "定例の枠なのに時期が記載なし"
            elif frame == "随時":
                mark = "④"
            elif frame == "済み":
                mark = "⑥" if tgt["直す場所の記号"] in ADD_OR_CLOSE else "⑤"
            elif frame == "動かない":
                mark = "⑨"
            elif frame == "将来":
                mark = "⑦"
            else:
                mark = "⑧"

        out.append({
            "rule id": rid,
            "領域": r["領域"],
            "時期の欄": r["時期の欄"],
            "時期の形": form or "登録外",
            "公表する側": r["公表する側"],
            "変わる対象": r["対象記号"],
            "直す場所": "" if reason else tgt["直す場所の記号"],
            "再検証の範囲": "" if reason else tgt["再検証の範囲の記号"],
            "種別": r["種別記号"],
            "確認の置き所": "" if reason else reg["確認の置き所の記号"],
            "枠": "" if reason else PLACES[mark],
            "別枠の理由": reason or "",
            "照合の印": r["照合の印"],
            "改定の記載": r["改定の記載"],
            "出典": r["出典"],
        })
    return out


def lists(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    """並びは **時期の欄の文字列だけ** で決まる。年月と月日は別の表にして混ぜない。"""
    key = {"年月": "年月の一覧", "月日": "月日の一覧",
           "記載なし": "時期の記載なし", "登録外": "時期の形が登録外"}
    groups: dict[str, list[dict[str, str]]] = {v: [] for v in key.values()}
    for r in rows:
        groups[key[r["時期の形"]]].append(r)
    # rows は _canon 済み(全欄の総順序)なので、安定ソートで並びが一意に決まる
    return {k: sorted(v, key=lambda r: (r["時期の欄"], r["rule id"])) for k, v in groups.items()}


def tally(rows: list[dict[str, str]]) -> dict[str, object]:
    places = {PLACES[k]: 0 for k in PLACE_MARKS}
    aside = {k: 0 for k in ASIDE}
    by_kind: dict[str, dict[str, int]] = {}
    by_fix: dict[str, int] = {}
    by_form: dict[str, int] = {}
    for r in rows:
        key = f"別枠 / {r['別枠の理由']}" if r["別枠の理由"] else r["枠"]
        if r["別枠の理由"]:
            aside[r["別枠の理由"]] += 1
        else:
            places[r["枠"]] += 1
        by_kind.setdefault(r["種別"], {})
        by_kind[r["種別"]][key] = by_kind[r["種別"]].get(key, 0) + 1
        fix = r["直す場所"] or "割り振らなかった"
        by_fix[fix] = by_fix.get(fix, 0) + 1
        by_form[r["時期の形"]] = by_form.get(r["時期の形"], 0) + 1
    return {
        "分母(rule の件数)": len(rows),
        "9 値": places,
        "別枠": aside,
        "種別ごとの内訳": {k: dict(sorted(by_kind[k].items())) for k in sorted(by_kind)},
        "直す場所ごとの件数": {k: by_fix[k] for k in sorted(by_fix)},
        "時期の形ごとの件数": {k: by_form[k] for k in sorted(by_form)},
    }


def judge(kaitei: list[dict[str, str]], okiba: dict[str, dict[str, str]],
          taishou: dict[str, dict[str, str]]) -> dict[str, object]:
    rows = slot_rows(kaitei, okiba, taishou)
    t = tally(rows)
    grouped = lists(rows)
    core = {
        "割り振り": [[r["rule id"], r["枠"] or f"別枠 / {r['別枠の理由']}"] for r in rows],
        "一覧": {k: [r["rule id"] for r in v] for k, v in sorted(grouped.items())},
        "集計": t,
    }
    blob = json.dumps(core, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    n = int(t["分母(rule の件数)"])
    s9 = sum(t["9 値"].values())
    sa = sum(t["別枠"].values())
    sk = sum(sum(v.values()) for v in t["種別ごとの内訳"].values())
    return {
        "ok": True,
        **t,
        "一覧の行数": {k: len(v) for k, v in sorted(grouped.items())},
        "件数の合計の検算": (f"9 値 {s9} + 別枠 {sa} = {s9 + sa} / 分母 {n}、"
                             f"種別ごとの内訳の合計 {sk} / 分母 {n}"),
        "合計が合う": s9 + sa == n and sk == n,
        "判定部分の sha256": hashlib.sha256(blob.encode("utf-8")).hexdigest(),
        "しないこと": NOT_DOING,
    }


# ---- verify -------------------------------------------------------------------------------

def _answers(kaitei: list[dict[str, str]], okiba: dict[str, dict[str, str]],
             taishou: dict[str, dict[str, str]]) -> dict[str, str]:
    """rule id ごとの答え。同じ id が 2 行あるときは先に来た 1 行(= 割り振った方)を採る。"""
    out: dict[str, str] = {}
    for r in slot_rows(kaitei, okiba, taishou):
        out.setdefault(r["rule id"], r["枠"] or f"別枠 / {r['別枠の理由']}")
    return out


def _unique_ids(kaitei: list[dict[str, str]]) -> set[str]:
    ids = [r["rule id"] for r in kaitei]
    return {i for i in ids if ids.count(i) == 1}


def _swap_cell(kaitei: list[dict[str, str]], rid: str, col: str, to: str) -> list[dict[str, str]]:
    """写しはメモリの中だけ。入力の表には書かない。"""
    return [({**r, col: to} if r["rule id"] == rid else dict(r)) for r in kaitei]


def _swap_okiba(okiba: dict[str, dict[str, str]], kind: str,
                sayable: str, slot: str) -> dict[str, dict[str, str]]:
    out = {k: dict(v) for k, v in okiba.items()}
    if kind in out:
        out[kind] = {**out[kind], "次に動く時期が言えるか": sayable, "確認の置き所の記号": slot}
    return out


def verify(kaitei: list[dict[str, str]], okiba: dict[str, dict[str, str]],
           taishou: dict[str, dict[str, str]]) -> dict[str, object]:
    a, b = judge(kaitei, okiba, taishou), judge(kaitei, okiba, taishou)
    rev = judge(list(reversed(kaitei)), {k: okiba[k] for k in reversed(list(okiba))},
                {k: taishou[k] for k in reversed(list(taishou))})
    base = _answers(kaitei, okiba, taishou)
    uniq = _unique_ids(kaitei)

    # 4. 照合の印を 1 件だけ 要照合 → 照合済 に替え、登録表の行だけを差し替えて 2 通り出す
    one = next((r["rule id"] for r in _canon(kaitei)
                if r["rule id"] in uniq and r["照合の印"] == "要照合"
                and base.get(r["rule id"]) == "別枠 / 照合の印が要照合"), None)
    four: dict[str, object] = {"替えた rule": one}
    if one is not None:
        src = next(r for r in _canon(kaitei) if r["rule id"] == one)
        kind = src["種別記号"]
        now = (okiba[kind]["次に動く時期が言えるか"], okiba[kind]["確認の置き所の記号"])
        other = next(p for p in FRAME_TABLE if p != now)
        fixed = _swap_cell(kaitei, one, "照合の印", "照合済")
        after1 = _answers(fixed, okiba, taishou)
        after2 = _answers(fixed, _swap_okiba(okiba, kind, *other), taishou)
        four |= {
            "替える前": base[one],
            "登録表そのまま": after1[one],
            "登録表の種別行だけ差し替え": after2[one],
            "差し替えた先": f"{other[0]} / {other[1]}",
            "別枠から 9 値へ移る": base[one].startswith("別枠") and not after1[one].startswith("別枠"),
            "登録表が指す先へ動く": after1[one] != after2[one] and not after2[one].startswith("別枠"),
            "動いたのはこの rule だけ": sum(1 for k in base if base[k] != after1[k]) == 1,
            "合計は変わらない": (sum(a["9 値"].values()) + sum(a["別枠"].values())
                                 == int(a["分母(rule の件数)"])),
        }

    # 5. 時期の欄を 記載なし → 年月 に替えると、その rule だけが別枠から ② へ移り年月の一覧が 1 行増える
    two = next((r["rule id"] for r in _canon(kaitei)
                if r["rule id"] in uniq and timing_form(r["時期の欄"]) == "記載なし"
                and base.get(r["rule id"]) == "別枠 / 定例の枠なのに時期が記載なし"), None)
    donor = next((r["時期の欄"] for r in _canon(kaitei) if timing_form(r["時期の欄"]) == "年月"), None)
    five: dict[str, object] = {"替えた rule": two, "借りた年月": donor}
    if two is not None and donor is not None:
        moved = _swap_cell(kaitei, two, "時期の欄", donor)   # 日付は作らず、台帳に在る年月を借りる
        after = _answers(moved, okiba, taishou)
        n0 = len(lists(slot_rows(kaitei, okiba, taishou))["年月の一覧"])
        n1 = len(lists(slot_rows(moved, okiba, taishou))["年月の一覧"])
        five |= {"替える前": base[two], "替えた後": after[two],
                 "② へ移る": after[two] == PLACES["②"],
                 "動いたのはこの rule だけ": sum(1 for k in base if base[k] != after[k]) == 1,
                 "年月の一覧": f"{n0} 行 → {n1} 行", "1 行増える": n1 == n0 + 1}

    return {
        "1 二度走りの sha256 が同じ": a["判定部分の sha256"] == b["判定部分の sha256"],
        "sha256": a["判定部分の sha256"],
        "2 3 表の行順を入れ替えても同じ": rev["判定部分の sha256"] == a["判定部分の sha256"],
        "3 件数の合計が合う": a["合計が合う"],
        "4 照合の印を 1 件替えると登録表が指す枠へ移る": four,
        "5 時期の欄を記載なしから年月に替えると ② へ移る": five,
        "ok": bool(a["判定部分の sha256"] == b["判定部分の sha256"]
                   and rev["判定部分の sha256"] == a["判定部分の sha256"] and a["合計が合う"]
                   and four.get("別枠から 9 値へ移る") and four.get("登録表が指す先へ動く")
                   and four.get("動いたのはこの rule だけ") and four.get("合計は変わらない")
                   and five.get("② へ移る") and five.get("動いたのはこの rule だけ")
                   and five.get("1 行増える")),
    }


# ---- CLI ----------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="改定の記載を確認の枠に割り振って 1 行 1 件の一覧にする")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("init", help="合成のひな型 3 枚を書き出す")
    g.add_argument("dest")
    for name, helptext in (("check", "件数の内訳を出す"), ("rows", "1 行 1 件の一覧を出す"),
                           ("verify", "決定論かどうかを 5 つ見る")):
        s = sub.add_parser(name, help=helptext)
        s.add_argument("kaitei")
        s.add_argument("okiba")
        s.add_argument("taishou")
    args = ap.parse_args(argv)

    if args.cmd == "init":
        sys.path.insert(0, str(Path(__file__).resolve().parent / "fixtures"))
        import make_fixtures
        for p in make_fixtures.write_all(Path(args.dest)):
            print(f"wrote {p.name}")
        return 0
    try:
        kaitei = read_table(args.kaitei, KAITEI_COLS)
        okiba = load_okiba(read_table(args.okiba, OKIBA_COLS))
        taishou = load_taishou(read_table(args.taishou, TAISHOU_COLS))
    except Stop as e:
        print(json.dumps({"ok": False, "理由コード": e.code, "詳細": e.detail,
                          "9 値": {PLACES[k]: 0 for k in PLACE_MARKS},
                          "1 件も割り振らない": True}, ensure_ascii=False, indent=1))
        return 3
    out: object = {"check": lambda: judge(kaitei, okiba, taishou),
                   "rows": lambda: lists(slot_rows(kaitei, okiba, taishou)),
                   "verify": lambda: verify(kaitei, okiba, taishou)}[args.cmd]()
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
