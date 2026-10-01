"""update_ledger の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 更新を何回どんな順で流しても、
  (1) 1 回につき台帳にちょうど 1 行増える(前の行は 1 バイトも変わらない)。
      run_at が前の行と同じ回だけは、行を足さずに LedgerError で拒む
  (2) 本番ファイルが書き換わるのは、関所を全部通って apply を指定した回だけで、そのとき中身は今回の表になる
  (3) 止まった回は本番ファイルのバイト列が変わらず、その行の sha256 は前の行の sha256 のまま繋がる

既存の test_measure_tampering は「出来上がった台帳を 1 か所ずつ書き換えて replay が止めるか」を数える。
このテストは向きが逆で、乱数で作った更新の列を record に流し、台帳と本番ファイルの実物の関係を毎回見る。

入力は乱数で作る。合成の数表(料率_甲 × 地域 3 つ + 上限額_乙、年度 1〜3 期)を作り、回ごとに値・期・出典・
公表の質を少しずつ動かす。指紋は中身が動いたら変え、ときどきわざと食い違わせる(指紋を付けない回もある)。
困る値として、期間の穴・重なり・同じ識別の行・読めない日付・列が足りない表・行が無い表・行が急に減った表・
施行日未定の行、台帳を通さない本番ファイルの書き換えと削除、前の行と同じ run_at、apply なしの回を混ぜる。

期待(関所を全部通るはずか、どれかで止まるはずか)は道具の関数(validate_rows / diff_tables / replay /
read_ledger / sha256_of)を使わず、このテストの中で別に書く。台帳は 1 行ずつ json で読み、本番ファイルは
バイト列のまま hashlib で sha256 を取る。指紋の関所で、行の並びだけが前回と違う回はどちらとも決めず、
その回は (1)(2)(3) だけを見る。derandomize=True で毎回同じ入力列を使い、database=None で見つけた例を保存しない(この版の hypothesis は実行した場所に .hypothesis/ を作るが、git と公開側への export では除外される)。
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from itertools import combinations
from pathlib import Path

from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import update_ledger as U  # noqa: E402

列 = ["key", "basis", "valid_from", "valid_to", "known_from", "known_to", "known_quality",
      "priority", "value", "source", "sel_地域"]
読むのに要る列 = ("key", "valid_from", "known_from", "priority", "value", "source")   # README の入力の表の形
期 = [("2024-04-01", "2024-02-01"), ("2025-04-01", "2025-02-01"), ("2026-04-01", "2026-02-01")]
系列 = [("料率_甲", "地域A"), ("料率_甲", "地域B"), ("料率_甲", "地域C"), ("上限額_乙", "")]
値の候補 = ["9.50", "9.60", "9.70", "8600", "8800"]
出典の候補 = ["合成の通知 第 1 版(架空)", "合成の通知 第 2 版(架空)"]
困りごと = ["なし"] * 6 + ["穴", "重なり", "同じ識別の行", "読めない日付", "列が足りない", "行が無い", "施行日未定の行",
          "行が急に減る"]
外の書き換え = ["なし"] * 8 + ["値を書き換える", "消す"]
BASE = datetime(2026, 9, 21, 9, 0, 0, tzinfo=timezone.utc)
取得元 = "取得元"


def 時刻(k: int) -> str:
    return (BASE + timedelta(hours=k)).isoformat()


def sha(b: bytes | None) -> str:
    return hashlib.sha256(b).hexdigest() if b is not None else ""


def 指紋(letter: str) -> str:
    return hashlib.sha256(f"合成の取得ファイル {letter}".encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- 表を組む

def 表(spec: tuple) -> list[dict]:
    """spec = 系列ごとの期の並び((値, 出典, 公表の質), ...)。期は前の期の終わりから次の期が始まる。"""
    rows: list[dict] = []
    for (key, area), periods in zip(系列, spec):
        for p, (value, source, quality) in enumerate(periods):
            rows.append({"key": key, "basis": "対象月初日", "valid_from": 期[p][0],
                         "valid_to": 期[p + 1][0] if p + 1 < len(periods) else "",
                         "known_from": 期[p][1], "known_to": "", "known_quality": quality,
                         "priority": "0", "value": value, "source": source, "sel_地域": area})
    return rows


def 困らせる(rows: list[dict], how: str, k: int) -> tuple[list[dict], list[str], str]:
    """今回の表に困る値を 1 つ入れる。返り値 = (行, 見出し, 実際に入れた困りごと)。"""
    rows = [dict(r) for r in rows]
    closed = [i for i, r in enumerate(rows) if r["valid_to"]]
    if how in ("穴", "重なり") and closed:
        i = closed[k % len(closed)]
        year = rows[i]["valid_to"][:4]
        rows[i]["valid_to"] = f"{year}-01-01" if how == "穴" else f"{year}-10-01"
    elif how == "同じ識別の行":
        rows.append(dict(rows[k % len(rows)]))
    elif how == "読めない日付":
        rows[k % len(rows)]["valid_from"] = rows[k % len(rows)]["valid_from"].replace("-", "/")
    elif how == "列が足りない":
        for r in rows:
            del r["source"]
        return rows, [c for c in 列 if c != "source"], how
    elif how == "行が無い":
        return [], list(列), how
    elif how == "行が急に減る":                            # 取得の失敗で地域 B・C が落ちた形
        rows = [r for r in rows if r["sel_地域"] in ("地域A", "")]
    elif how == "施行日未定の行":
        rows.append({"key": "上限額_乙", "basis": "請求日", "valid_from": "", "valid_to": "",
                     "known_from": "2026-06-13", "known_to": "", "known_quality": "実値", "priority": "0",
                     "value": "撤廃", "source": "合成の改正法(架空、施行日は政令)", "sel_地域": ""})
    else:
        how = "なし"
    return rows, list(列), how


@dataclass
class 回:
    rows: list
    header: list
    困りごと: str
    letter: str | None
    apply: bool
    外: str
    同じ時刻: bool


@st.composite
def 動かす(draw: st.DrawFn, spec: tuple) -> tuple:
    spec = [list(ps) for ps in spec]
    for _ in range(draw(st.integers(0, 2))):
        ps = spec[draw(st.integers(0, len(spec) - 1))]
        how = draw(st.sampled_from(["値", "期を足す", "期を落とす", "出典", "公表の質"]))
        p = draw(st.integers(0, len(ps) - 1))
        v, s, q = ps[p]
        if how == "値":
            ps[p] = (draw(st.sampled_from(値の候補)), s, q)
        elif how == "期を足す" and len(ps) < len(期):
            ps.append((draw(st.sampled_from(値の候補)), 出典の候補[0], "実値"))
        elif how == "期を落とす" and len(ps) > 1:
            ps.pop()
        elif how == "出典":
            ps[p] = (v, 出典の候補[1] if s == 出典の候補[0] else 出典の候補[0], q)
        elif how == "公表の質":
            ps[p] = (v, s, "仮置き" if q == "実値" else "実値")
    return tuple(tuple(ps) for ps in spec)


@st.composite
def 更新の列(draw: st.DrawFn) -> list[回]:
    spec = tuple(tuple((draw(st.sampled_from(値の候補)), 出典の候補[0], "実値")
                       for _ in range(draw(st.integers(2, 3)))) for _ in 系列)
    runs: list[回] = []
    prev_rows: list | None = None
    letter, fresh = None, 0
    for i in range(draw(st.integers(2, 5))):
        if i:
            spec = draw(動かす(spec))
        rows, header, how = 困らせる(表(spec), draw(st.sampled_from(困りごと)), draw(st.integers(0, 50)))
        # 指紋: 中身が動いたら新しい指紋、同じなら同じ指紋(ときどきわざと食い違わせる / 付けない)
        same = prev_rows is not None and rows == prev_rows and letter is not None
        kind = draw(st.sampled_from(["合わせる"] * 4 + ["食い違わせる", "付けない"]))
        if kind == "付けない":
            this = None
        elif same != (kind == "食い違わせる") and letter is not None:
            this = letter
        else:
            fresh += 1
            this = chr(ord("A") + fresh)
        runs.append(回(rows, header, how, this, draw(st.sampled_from([True, True, True, False])),
                      draw(st.sampled_from(外の書き換え)) if i else "なし",
                      bool(i) and draw(st.integers(0, 9)) == 0))
        prev_rows = rows
        letter = this if this is not None else letter
    return runs


# ---------------------------------------------------------------- 期待(道具の関数を使わずに作る)

def _日付(s: str) -> bool:
    try:
        date.fromisoformat(s)
        return True
    except ValueError:
        return False


def 読める(rows: list[dict], header: list[str]) -> bool:
    if not rows or any(c not in header for c in 読むのに要る列):
        return False
    for r in rows:
        if not r["key"] or not r["known_from"] or not r["priority"].lstrip("-").isdigit():
            return False
        if any(r[c] and not _日付(r[c]) for c in ("valid_from", "valid_to", "known_from", "known_to")):
            return False
    return True


def _重なる(af: str, at: str, bf: str, bt: str) -> bool:
    """半開区間 [af, at) と [bf, bt) が重なるか。空 = 開いたまま(ISO の日付は文字列のまま比べられる)。"""
    return max(af, bf) < min(at or "9999-12-31", bt or "9999-12-31")


def 期間の不備(rows: list[dict]) -> set[str]:
    """README の「同じ key × 対象 × priority で」の重なりと穴。施行日未定の行は数えない。"""
    groups: dict = {}
    for r in rows:
        if r["valid_from"]:
            groups.setdefault((r["key"], r["sel_地域"], int(r["priority"])), []).append(r)
    found: set[str] = set()
    for rs in groups.values():
        rs = sorted(rs, key=lambda r: r["valid_from"])
        for a, b in combinations(rs, 2):
            if _重なる(a["valid_from"], a["valid_to"], b["valid_from"], b["valid_to"]) and \
                    _重なる(a["known_from"], a["known_to"], b["known_from"], b["known_to"]):
                found.add("有効期間の重なり")
        for a, b in zip(rs, rs[1:]):
            if a["valid_to"] and a["valid_to"] < b["valid_from"]:
                found.add("期間の穴")
    return found


def 期待(r: 回, lines: list[dict], before: bytes | None) -> str:
    """関所を全部通るはず = 通る / どれかで止まるはず = 止まる / 決めない = 不明。"""
    if lines and lines[-1]["sha256"] != sha(before):
        return "止まる"                                    # 台帳の鎖
    if not 読める(r.rows, r.header):
        return "止まる"                                    # 入力の列
    prev = json.loads(before) if before is not None else None
    if lines and r.letter is not None and lines[-1]["inputs"]:   # 指紋と差分
        same_fp = sorted((f["name"], f["sha256"]) for f in lines[-1]["inputs"]) == [(取得元, 指紋(r.letter))]
        if prev is None:
            moved: bool | None = True
        elif r.rows == prev:
            moved = False
        elif Counter(tuple(sorted(x.items())) for x in r.rows) != Counter(tuple(sorted(x.items())) for x in prev):
            moved = True
        else:
            moved = None                                   # 並びだけが違う
        if moved is not None and same_fp == moved:
            return "止まる"
        if moved is None:
            return "不明"
    if prev is not None and abs(len(r.rows) - len(prev)) * 5 > len(prev):
        return "止まる"                                    # 行数の急変(既定 0.2)
    if 期間の不備(r.rows):
        return "止まる"                                    # 重なり・穴
    return "通る"


# ---------------------------------------------------------------- 性質テスト

def 台帳の行(led: Path) -> list[dict]:
    if not led.exists():
        return []
    return [json.loads(x) for x in led.read_text(encoding="utf-8").splitlines() if x.strip()]


def 書く(path: Path, rows: list[dict], header: list[str]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows)
    return path


@settings(max_examples=200, derandomize=True, database=None, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(runs=更新の列())
def test_いつも成り立つこと_1回1行_止まった回は本番が動かない(runs: list[回]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        led, out = d / "daichou.jsonl", d / "honban.json"
        k = 0
        for i, r in enumerate(runs):
            if r.外 == "値を書き換える" and out.exists():          # 台帳を通さない書き換え
                data = json.loads(out.read_bytes())
                data[0]["value"] += "0"
                out.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            elif r.外 == "消す" and out.exists():
                out.unlink()
            now = 書く(d / f"now_{i}.csv", r.rows, r.header)
            fps = (U.Fingerprint(取得元, 指紋(r.letter), 時刻(k)),) if r.letter else ()
            ledger_before = led.read_bytes() if led.exists() else b""
            before = out.read_bytes() if out.exists() else None
            lines = 台帳の行(led)
            if r.同じ時刻 and lines:
                try:
                    U.record(led, now, out if out.exists() else None, out, fps,
                             run_at=lines[-1]["run_at"], apply=r.apply)
                    refused = False
                except U.LedgerError:
                    refused = True
                event("(c) run_at が前の行と同じ回を LedgerError で拒んだ")
                assert refused
                assert (led.read_bytes() if led.exists() else b"") == ledger_before
                assert (out.read_bytes() if out.exists() else None) == before
                continue
            k += 1
            want = 期待(r, lines, before)
            U.record(led, now, out if out.exists() else None, out, fps, run_at=時刻(k), apply=r.apply)
            after = out.read_bytes() if out.exists() else None
            got = 台帳の行(led)
            new = got[-1]
            # (1) ちょうど 1 行増え、前の行は 1 バイトも変わらない
            assert len(got) == len(lines) + 1
            assert led.read_bytes()[:len(ledger_before)] == ledger_before
            # (3) 行の sha256 は本番ファイルの実物と繋がる
            assert new["prev_sha256"] == sha(before)
            assert new["sha256"] == sha(after)
            if r.外 == "なし" and lines:
                assert new["prev_sha256"] == lines[-1]["sha256"]
            if new["status"] != "ok":
                event(f"(b) 止まった: {new['reason']}")
                assert after == before and not new["applied"]
            # (2) 書き換わるのは、関所を全部通って apply を指定した回だけ。中身は今回の表
            if after != before:
                assert new["status"] == "ok" and r.apply and new["applied"]
            if new["status"] == "ok":
                event("(a) 通って本番を今回の表にした" if r.apply else "(a) 通ったが apply なしで本番はそのまま")
                if r.apply:
                    assert after is not None and json.loads(after) == r.rows
                else:
                    assert after == before
            if want == "不明":
                event("期待を決めない回(並びだけが違う)")
            else:
                assert new["status"] == ("ok" if want == "通る" else "failed"), (want, new["reason"], r.困りごと)
