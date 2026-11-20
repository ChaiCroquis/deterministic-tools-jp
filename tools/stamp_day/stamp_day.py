"""stamp_day — 時刻の欄を、書かれたままの日付と、人が登録した換算先の時差での日付に分けて 1 行 1 件で並べる。

入力は 2 表(どちらも UTF-8 の CSV)。
  時刻の台帳      : row_id, stamp, source   (行の番号 / 時刻の文字列そのまま / 出典 = ファイル名 + 行番号)
  換算先の登録表  : name, offset            (名前 / 時差の文字列 +HH:MM か -HH:MM。1 回の実行で使うのは 1 行)

出力は行ごとに、書かれたままの日付(頭の 10 文字)/ 書かれている時差の印 / 換算後の日付と時刻 / 区分 3 値。
日ごとの回数は「書かれたままの読み」と「換算後の読み」の 2 列で返し、どちらが正しいかは返さない。

持たせていないもの: 時差の印が無い時刻に時差を当てる経路 / 端末の時間帯を読む経路 / 時計を読む経路 /
地名から時差を引く経路 / 文書の日付と結び付ける経路 / どちらの読みが正しいかを返す経路 /
日付だけの欄を時刻に広げる経路 / ネットワーク / 入力を書き換える経路 / 小数の計算。
標準ライブラリのみ(csv / json / datetime / hashlib / argparse / re)。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

STAMP_HEADER = ["row_id", "stamp", "source"]
ZONE_HEADER = ["name", "offset"]

# 数字は ASCII の 0-9 だけを受け取る(全角数字は「形が読めない」になる)
STAMP_RE = re.compile(
    r"^([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})"
    r"(?:\.([0-9]{1,6}))?(Z|[+-][0-9]{2}:[0-9]{2})?$"
)
OFFSET_RE = re.compile(r"^([+-])([0-9]{2}):([0-9]{2})$")
DIGITS_RE = re.compile(r"^[0-9]+$")

KUBUN_A = "(A) 日付が同じ"
KUBUN_B = "(B) 後の日付に替わる"
KUBUN_C = "(C) 前の日付に替わる"
KUBUN = [KUBUN_A, KUBUN_B, KUBUN_C]

ASIDE_SOURCE = "出典が空"
ASIDE_DUP = "同じ行の番号が 2 回以上"
ASIDE_SHAPE = "形が読めない時刻"
ASIDE_NO_MARK = "時差の印が無い時刻"
ASIDES = [ASIDE_SOURCE, ASIDE_DUP, ASIDE_SHAPE, ASIDE_NO_MARK]

Z_NOTE = "Z を +00:00 と読んだ"

STOPS = [
    "時刻の台帳の見出しが違う",
    "時刻の台帳に列の数が違う行がある",
    "時刻の台帳に行の番号が空の行がある",
    "換算先の登録表の見出しが違う",
    "換算先の登録表に列の数が違う行がある",
    "換算先の登録表が空",
    "換算先の登録表に同じ名前が 2 回以上ある",
    "換算先の登録表に読めない時差がある",
    "換算先の登録表が 2 行以上あるのに、使う 1 行の指定が無い",
    "指定した名前が換算先の登録表に無い",
]

ORDER_NOTE = "換算後の時刻の順。同じ時刻の行は行の番号の順(数字だけの番号は数として比べる)"

NOT_HELD = [
    "時差の印が無い時刻に時差を当てない: 印の無い行は別枠に出し、日ごとの回数に入れない",
    "端末の時間帯を読まない: 換算先は登録表の 1 行だけで決まる",
    "時計を読まない: いつ走らせても同じ入力から同じ出力になる",
    "地名から時差を引かない: 夏時間の表を持たないので、時差は +HH:MM か -HH:MM の文字列だけを受け取る",
    "文書に書かれた日付と結び付けない: 文書の日付を受け取る引数が無い",
    "どちらの読みを採るかを返さない: 日ごとの回数は 2 列のまま返す",
    "日付だけの欄を時刻に広げない: 時刻の無い値は「形が読めない時刻」に出す",
    "ネットワークを使わない",
    "入力を書き換えない: 2 表は読むだけ",
    "小数の計算をしない: 秒より下は書かれた桁のまま整数で持つ",
]


class Stop(Exception):
    """表として読めないとき。1 行も区分せずに理由を返す。"""

    def __init__(self, reason: str) -> None:
        assert reason in STOPS
        super().__init__(reason)
        self.reason = reason


def parse_offset(text: str) -> timedelta | None:
    """+HH:MM / -HH:MM を timedelta にする。読めなければ None。"""
    m = OFFSET_RE.match(text)
    if not m:
        return None
    hours, minutes = int(m.group(2)), int(m.group(3))
    if hours > 23 or minutes > 59:
        return None
    delta = timedelta(hours=hours, minutes=minutes)
    return -delta if m.group(1) == "-" else delta


def parse_stamp(text: str) -> tuple[str, datetime | None, str, timedelta | None]:
    """時刻の文字列を読む。返すのは (状態, 書かれた日付と時刻, 時差の印, 時差)。
    状態は "ok" / ASIDE_SHAPE / ASIDE_NO_MARK。時差の印が無い行に時差は当てない。"""
    m = STAMP_RE.match(text)
    if not m:
        return ASIDE_SHAPE, None, "", None
    y, mo, d, h, mi, s = (int(m.group(i)) for i in range(1, 7))
    micro = int(m.group(7).ljust(6, "0")) if m.group(7) else 0
    try:
        written = datetime(y, mo, d, h, mi, s, micro)
    except ValueError:
        return ASIDE_SHAPE, None, "", None
    mark = m.group(8)
    if mark is None:
        return ASIDE_NO_MARK, written, "", None
    if mark == "Z":
        return "ok", written, mark, timedelta(0)
    offset = parse_offset(mark)
    if offset is None:
        return ASIDE_SHAPE, None, "", None
    return "ok", written, mark, offset


def id_key(row_id: str) -> tuple[int, int, str]:
    """行の番号の並べ方。数字だけの番号は数として、それ以外は文字列として比べる。"""
    if DIGITS_RE.match(row_id):
        return (0, int(row_id), row_id)
    return (1, 0, row_id)


def read_table(path: str | Path, header: list[str], bad_header: str, bad_width: str) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        lines = [r for r in csv.reader(f) if r]
    if not lines or lines[0] != header:
        raise Stop(bad_header)
    out = []
    for r in lines[1:]:
        if len(r) != len(header):
            raise Stop(bad_width)
        out.append(dict(zip(header, r)))
    return out


def load(stamps_path: str | Path, zones_path: str | Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    stamps = read_table(stamps_path, STAMP_HEADER, STOPS[0], STOPS[1])
    zones = read_table(zones_path, ZONE_HEADER, STOPS[3], STOPS[4])
    return stamps, zones


def pick_zone(zones: list[dict[str, str]], zone_name: str | None) -> tuple[str, str, timedelta]:
    if not zones:
        raise Stop(STOPS[5])
    names = [z["name"] for z in zones]
    if len(set(names)) != len(names):
        raise Stop(STOPS[6])
    if any(parse_offset(z["offset"]) is None for z in zones):
        raise Stop(STOPS[7])
    if zone_name is None:
        if len(zones) != 1:
            raise Stop(STOPS[8])
        chosen = zones[0]
    else:
        hit = [z for z in zones if z["name"] == zone_name]
        if not hit:
            raise Stop(STOPS[9])
        chosen = hit[0]
    offset = parse_offset(chosen["offset"])
    assert offset is not None
    return chosen["name"], chosen["offset"], offset


def judge(stamps: list[dict[str, str]], zones: list[dict[str, str]], zone_name: str | None = None) -> dict:
    """2 表から、行ごとの一覧・別枠・日ごとの回数(2 列)を作る。入力は書き換えない。"""
    name, offset_text, target = pick_zone(zones, zone_name)
    if any(r["row_id"] == "" for r in stamps):
        raise Stop(STOPS[2])
    seen: dict[str, int] = {}
    for r in stamps:
        seen[r["row_id"]] = seen.get(r["row_id"], 0) + 1

    rows, aside = [], []
    for r in stamps:
        base = {"row_id": r["row_id"], "書かれた時刻": r["stamp"], "出典": r["source"]}
        if r["source"].strip() == "":
            aside.append({**base, "別枠": ASIDE_SOURCE})
            continue
        if seen[r["row_id"]] > 1:
            aside.append({**base, "別枠": ASIDE_DUP})
            continue
        state, written, mark, offset = parse_stamp(r["stamp"])
        if state != "ok":
            aside.append({**base, "別枠": state})
            continue
        assert written is not None and offset is not None
        try:
            converted = written + (target - offset)
            instant = written - offset
        except OverflowError:
            aside.append({**base, "別枠": ASIDE_SHAPE})
            continue
        days = (converted.date() - written.date()).days
        kubun = KUBUN_A if days == 0 else KUBUN_B if days > 0 else KUBUN_C
        rows.append({
            **base,
            "書かれたままの日付": r["stamp"][:10],
            "書かれている時差の印": mark,
            "Z の読み": Z_NOTE if mark == "Z" else "",
            "換算後の日付": converted.date().isoformat(),
            "換算後の時刻": converted.time().isoformat(),
            "日付の差(日)": days,
            "区分": kubun,
            "_instant": instant,
        })

    rows.sort(key=lambda x: (x["_instant"], id_key(x["row_id"])))
    for x in rows:
        del x["_instant"]
    aside.sort(key=lambda x: (id_key(x["row_id"]), x["書かれた時刻"], x["出典"], x["別枠"]))

    days_all = sorted({x["書かれたままの日付"] for x in rows} | {x["換算後の日付"] for x in rows})
    per_day = [{
        "日付": d,
        "書かれたままの読み": sum(1 for x in rows if x["書かれたままの日付"] == d),
        "換算後の読み": sum(1 for x in rows if x["換算後の日付"] == d),
    } for d in days_all]

    kubun_count = {k: sum(1 for x in rows if x["区分"] == k) for k in KUBUN}
    aside_count = {k: sum(1 for x in aside if x["別枠"] == k) for k in ASIDES}
    total_split = sum(kubun_count.values()) + sum(aside_count.values())
    sum_written = sum(d["書かれたままの読み"] for d in per_day)
    sum_converted = sum(d["換算後の読み"] for d in per_day)

    def edge(x: dict) -> dict:
        return {"row_id": x["row_id"], "書かれた時刻": x["書かれた時刻"],
                "換算後": x["換算後の日付"] + " " + x["換算後の時刻"]}

    return {
        "ok": True,
        "台帳の行数": len(stamps),
        "換算先": {"名前": name, "時差": offset_text},
        "並べ方": ORDER_NOTE,
        "区分": kubun_count,
        "別枠": aside_count,
        "Z を +00:00 と読んだ行": sum(1 for x in rows if x["Z の読み"]),
        "日ごとの回数": per_day,
        "最初の時刻": edge(rows[0]) if rows else None,
        "最後の時刻": edge(rows[-1]) if rows else None,
        "日付が替わった行の番号": [x["row_id"] for x in rows if x["区分"] != KUBUN_A],
        "件数の検算": {
            "区分 + 別枠": total_split,
            "台帳の行数": len(stamps),
            "日ごとの回数の合計(書かれたままの読み)": sum_written,
            "日ごとの回数の合計(換算後の読み)": sum_converted,
            "区分に入った行数": len(rows),
            "合う": total_split == len(stamps) and sum_written == len(rows) and sum_converted == len(rows),
        },
        "rows": rows,
        "aside": aside,
        "持たせていないもの": list(NOT_HELD),
    }


def judged_part(result: dict) -> dict:
    """判定部分(末尾の「持たせていないもの」を除いた全部)。"""
    return {k: v for k, v in result.items() if k != "持たせていないもの"}


def digest(result: dict) -> str:
    text = json.dumps(judged_part(result), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _others(result: dict, row_id: str) -> tuple:
    rows = [(x["row_id"], x["区分"], x["書かれたままの日付"], x["換算後の日付"], x["換算後の時刻"])
            for x in result["rows"] if x["row_id"] != row_id]
    return rows, result["aside"]


def _hms(delta: timedelta) -> str:
    seconds = delta.days * 86400 + delta.seconds
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def verify(stamps: list[dict[str, str]], zones: list[dict[str, str]], zone_name: str | None = None) -> dict:
    """この手続きが決定論かどうかを 5 つ見る。写しはメモリの中だけで、入力には書かない。"""
    stamps = [dict(r) for r in stamps]
    zones = [dict(z) for z in zones]
    base = judge(stamps, zones, zone_name)
    sha = digest(base)

    # ① 二度走り
    v1 = {"sha256": sha, "同一": digest(judge(stamps, zones, zone_name)) == sha}

    # ② 行順の入れ替え(3 通り)
    shuffles = [
        (list(reversed(stamps)), zones),
        (stamps[1:] + stamps[:1], zones),
        (sorted(stamps, key=lambda r: (r["stamp"], r["row_id"], r["source"])), list(reversed(zones))),
    ]
    zname = base["換算先"]["名前"]
    v2 = {"入れ替え方": len(shuffles),
          "同一": sum(1 for s, z in shuffles if digest(judge(s, z, zname)) == sha)}
    v2["合う"] = v2["同一"] == v2["入れ替え方"]

    # ③ 件数の検算
    v3 = dict(base["件数の検算"])

    # ④ 行に書かれている時差そのものを換算先にすると、その行はみな (A) になり 2 列の回数が一致する
    marks = sorted({x["書かれている時差の印"] for x in base["rows"]})
    tried_rows = all_a = cols_equal = 0
    for mark in marks:
        ids = {x["row_id"] for x in base["rows"] if x["書かれている時差の印"] == mark}
        sub = [r for r in stamps if r["row_id"] in ids]
        own = "+00:00" if mark == "Z" else mark
        res = judge(sub, [{"name": "書かれている時差", "offset": own}], None)
        tried_rows += len(sub)
        all_a += res["区分"][KUBUN_A]
        if all(d["書かれたままの読み"] == d["換算後の読み"] for d in res["日ごとの回数"]):
            cols_equal += 1
    v4 = {"時差の印の種類": len(marks), "試した行数": tried_rows, "(A) になった行数": all_a,
          "2 列の回数が一致した種類": cols_equal,
          "合う": tried_rows == all_a and cols_equal == len(marks)}

    # ⑤ (A) の 1 行を日付の境目の手前の 1 秒に置くと (A) のまま、向こうへ 1 秒動かすとその 1 行だけが動く
    target = parse_offset(base["換算先"]["時差"])
    assert target is not None
    tried = stay = moved = no_edge = 0
    for x in base["rows"]:
        if x["区分"] != KUBUN_A:
            continue
        mark = x["書かれている時差の印"]
        offset = timedelta(0) if mark == "Z" else parse_offset(mark)
        assert offset is not None
        delta = target - offset
        if delta == timedelta(0):
            no_edge += 1
            continue
        day = x["書かれたままの日付"]
        one = timedelta(seconds=1)
        if delta > timedelta(0):
            near, far, want = timedelta(days=1) - delta - one, timedelta(days=1) - delta, KUBUN_B
        else:
            near, far, want = -delta, -delta - one, KUBUN_C
        tried += 1
        results = []
        for t in (near, far):
            copy = [dict(r) for r in stamps]
            for r in copy:
                if r["row_id"] == x["row_id"]:
                    r["stamp"] = f"{day}T{_hms(t)}{mark}"
            results.append(judge(copy, zones, zname))
        got = [next(y["区分"] for y in res["rows"] if y["row_id"] == x["row_id"]) for res in results]
        same_others = all(_others(res, x["row_id"]) == _others(base, x["row_id"]) for res in results)
        if got[0] == KUBUN_A and same_others:
            stay += 1
        if got[1] == want and same_others:
            moved += 1
    v5 = {"試した行数": tried, "手前の 1 秒で (A) のままだった行数": stay,
          "向こうの 1 秒でその 1 行だけが動いた行数": moved, "境目が無くて試せない行数": no_edge,
          "合う": tried == stay == moved}

    ok = v1["同一"] and v2["合う"] and v3["合う"] and v4["合う"] and v5["合う"]
    return {"ok": ok, "① 二度走りの sha256": v1, "② 行順の入れ替え": v2, "③ 件数の検算": v3,
            "④ 書かれている時差へ換算": v4, "⑤ 日付の境目の 1 秒": v5}


def run_files(stamps_path: str | Path, zones_path: str | Path, zone_name: str | None = None) -> dict:
    try:
        stamps, zones = load(stamps_path, zones_path)
        return judge(stamps, zones, zone_name)
    except Stop as e:
        return {"ok": False, "止まった理由": e.reason, "区分した行数": 0}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="時刻の欄を、書かれたままの日付と換算後の日付に分けて並べる")
    p.add_argument("command", choices=["check", "rows", "verify"])
    p.add_argument("stamps", help="時刻の台帳(row_id,stamp,source)")
    p.add_argument("zones", help="換算先の登録表(name,offset)")
    p.add_argument("--zone", default=None, help="登録表が 2 行以上のとき、使う 1 行の名前")
    a = p.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    res = run_files(a.stamps, a.zones, a.zone)
    if not res["ok"]:
        print(json.dumps(res, ensure_ascii=False))
        return 2
    if a.command == "check":
        out = {k: v for k, v in res.items() if k not in ("rows", "aside")}
        print(json.dumps(out, ensure_ascii=False, indent=1))
    elif a.command == "rows":
        for x in res["rows"] + res["aside"]:
            print(json.dumps(x, ensure_ascii=False))
    else:
        stamps, zones = load(a.stamps, a.zones)
        v = verify(stamps, zones, a.zone)
        print(json.dumps(v, ensure_ascii=False, indent=1))
        return 0 if v["ok"] else 4
    return 3 if sum(res["別枠"].values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
