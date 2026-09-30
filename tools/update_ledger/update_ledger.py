"""update_ledger — 数表の更新を「実行 1 回 = 台帳 1 行」で残し、検査に落ちた回は本番ファイルを書き換えない部品。

毎年書き換わる数表(料率・限度額・等級表)を更新するとき、更新そのものの記録が無いと
「いつ何が変わったか」を後から数えられない。この部品は 1 回の更新について次を 1 行にして、
追記専用の台帳(JSONL)へ残す。

    run_at        いつ実行したか
    inputs        取得したファイルごとの指紋(sha256 + 取得時刻)
    counts        差分 6 種の件数(追加 / 削除 / 値の変更 / 有効期間の変更 / 公表時点の変更 / 出典欄の変更)
    changed       何行が動いたか(1 行が 2 つの側面で動くことがあるので counts の合計とは別に持つ)
    status        ok / failed
    reason        止まった理由コード(8 つ。REASONS)
    applied       本番ファイルを差し替えたか
    sha256        この回のあとの本番ファイルの sha256
    prev_sha256   この回の前の本番ファイルの sha256(前の行の sha256 と繋がる = 鎖)

表の形は asof_table と同じ行の表(key / basis / valid_from / valid_to / known_from / known_to /
known_quality / priority / value / source / sel_*)。CSV でも JSON でもよい。

検査に落ちたときは本番ファイルを書かない。差し替えは呼び出し側が apply=True と明示した回だけで、
「最新の値へ黙って進む」経路も fallback の引数も持たない。値そのものの正しさ・改正の解釈は判定しない。

標準ライブラリのみ(json / csv / hashlib / datetime / argparse)。CLI と関数の両方。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

SEL_PREFIX = "sel_"
REQUIRED = ("key", "valid_from", "known_from", "priority", "value", "source")

# 行の識別。対象 + valid_from + known_from に priority を足してある。
# 同じ有効期間・同じ公表時点で本則と経過措置が並ぶ表が実在するので、順位を入れないと 2 行が同じ識別になる。
IDENTITY_COLS = ("key", "valid_from", "known_from", "priority")

KINDS = ("追加", "削除", "値の変更", "有効期間の変更", "公表時点の変更", "出典欄の変更")

# 識別が同じ行どうしで、どの列が動いたらどの種に数えるか
GROUPS = {
    "有効期間の変更": ("valid_to",),
    "公表時点の変更": ("known_to", "known_quality"),
    "出典欄の変更": ("source", "source_url", "meta", "note"),
}
# GROUPS のどこにも無い列の変化は、引き当ての結果を変えうる側(= 安全な側)に数える
DEFAULT_KIND = "値の変更"

# 止まる理由コード(この 8 つで全部。本番ファイルは書き換えない)
REASONS = {
    "有効期間の重なり": "同じ key × 対象 × priority で、有効時間も知識時間も重なる行がある",
    "期間の穴": "同じ key × 対象 × priority で、前の行の valid_to と次の行の valid_from が離れている",
    "行数の急変": "行数が前回から max_row_change を超えて動いた。取得か抽出の失敗を疑う",
    "指紋が前回と同一なのに差分あり": "入力ファイルの sha256 が前回と同じなのに行の差分が出た。抽出側が変わったか、入力以外から行が入っている",
    "指紋が違うのに差分 0": "入力ファイルの sha256 が前回と違うのに行の差分が 0。取得したファイルの変化が行に反映されていない",
    "台帳の鎖が切れている": "前の行の sha256 と今の本番ファイルが繋がらない(台帳を通さない書き換えがあった)、または台帳の中の件数が積み上がらない",
    "run_at の重複": "同じ run_at の行がすでにある。追記すると実行の順序が台帳から決まらなくなるので追記しない",
    "入力の列が足りない": "入力が行の表として読めない(必要な列が無い / 日付が YYYY-MM-DD で読めない)",
}

# 表そのものの検査(関所)が返す不備の種類
FINDINGS = ("有効期間の重なり", "期間の穴")

MAX_ROW_CHANGE = 0.2   # 行数がこの割合を超えて動いたら止める(既定 20%)
SAMPLE_LIMIT = 3       # 台帳 1 行に残す差分・不備の見本の数


class TableError(ValueError):
    """入力が行の表として読めない。台帳には failed の 1 行として残る。"""


class LedgerError(ValueError):
    """台帳そのものが読めない / 追記すると台帳が検証できなくなる。台帳には何も書かない。"""


# ---------------------------------------------------------------- 表

def _parse_date(s: str, what: str) -> date:
    try:
        return date.fromisoformat(str(s).strip())
    except ValueError as e:
        raise TableError(f"{what} が YYYY-MM-DD で読めない: {s!r}") from e


def _opt_date(s: str, what: str) -> date | None:
    s = (s or "").strip()
    return _parse_date(s, what) if s else None


class Table:
    """行の表。読んだ時点で列の有無と日付の形だけを見る(期間の検査は validate_rows)。"""

    def __init__(self, records: list[dict], origin: str = ""):
        if not records:
            raise TableError("表に行が 1 つも無い")
        cols = list(records[0].keys())
        missing = [c for c in REQUIRED if c not in cols]
        if missing:
            raise TableError("必要な列が無い: " + "/".join(missing))
        self.columns = tuple(cols)
        self.dims = tuple(c for c in cols if c.startswith(SEL_PREFIX))
        self.origin = origin
        self.records: list[dict] = []
        for i, rec in enumerate(records, 1):
            row = {c: ("" if rec.get(c) is None else str(rec.get(c, "")).strip()) for c in cols}
            if not row["key"]:
                raise TableError(f"行 {i}: key が空")
            if not row["known_from"]:
                raise TableError(f"行 {i}: known_from が空(公表時点を空にすると、当時の知識を再現できない)")
            _opt_date(row["valid_from"], f"行 {i} の valid_from")
            _opt_date(row.get("valid_to", ""), f"行 {i} の valid_to")
            _parse_date(row["known_from"], f"行 {i} の known_from")
            _opt_date(row.get("known_to", ""), f"行 {i} の known_to")
            pr = row["priority"]
            if not pr.lstrip("-").isdigit():
                raise TableError(f"行 {i}: priority が整数でない: {pr!r}")
            row["priority"] = str(int(pr))
            self.records.append(row)

    def __len__(self) -> int:
        return len(self.records)

    @classmethod
    def from_csv(cls, path: str | Path) -> "Table":
        p = Path(path)
        with p.open(encoding="utf-8-sig", newline="") as f:
            return cls(list(csv.DictReader(f)), str(p))

    @classmethod
    def from_json(cls, path: str | Path) -> "Table":
        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        if not isinstance(data, list):
            raise TableError("JSON は行の配列で書く")
        return cls(data, str(p))

    @classmethod
    def load(cls, path: str | Path) -> "Table":
        p = Path(path)
        try:
            return cls.from_json(p) if p.suffix.lower() == ".json" else cls.from_csv(p)
        except json.JSONDecodeError as e:
            raise TableError(f"JSON として読めない: {e}") from e

    def identity(self, rec: dict) -> tuple:
        return (tuple(rec.get(c, "") for c in IDENTITY_COLS),
                tuple(rec.get(d, "") for d in self.dims))

    def by_identity(self) -> dict:
        """識別 → その識別の行。同じ識別が 2 行あれば表の順に並べて持つ(重なりは関所が拾う)。"""
        out: dict = {}
        for rec in self.records:
            out.setdefault(self.identity(rec), []).append(rec)
        return out

    def serialize(self) -> bytes:
        """本番ファイルの中身。列順・行順を固定して、同じ表なら必ず同じ sha256 になる形で書く。"""
        body = json.dumps(self.records, ensure_ascii=False, indent=2, sort_keys=True)
        return (body + "\n").encode("utf-8")


# ---------------------------------------------------------------- 差分

@dataclass(frozen=True)
class Diff:
    rows_prev: int
    rows_now: int
    changed: int                # 何行が動いたか(識別が同じで中身が違う行の数)
    counts: dict                # KINDS ごとの件数。1 行が 2 側面で動くと合計は changed を超える
    samples: tuple = ()

    @property
    def any_change(self) -> bool:
        return any(self.counts.get(k, 0) for k in KINDS)


def _kind_of(col: str) -> str:
    for kind, cols in GROUPS.items():
        if col in cols:
            return kind
    return DEFAULT_KIND


def _ident_text(ident: tuple) -> str:
    head, sel = ident
    parts = [f"{c}={v or '*'}" for c, v in zip(IDENTITY_COLS, head)]
    parts += [v for v in sel if v]
    return " ".join(parts)


def diff_tables(prev: "Table | None", now: Table) -> Diff:
    """前回の表と今回の表を識別で突き合わせ、6 種に分けて数える。件数は丸めない。"""
    counts = {k: 0 for k in KINDS}
    samples: list = []
    if prev is None:
        counts["追加"] = len(now)
        return Diff(0, len(now), 0, counts, ())
    a, b = prev.by_identity(), now.by_identity()
    cols = [c for c in dict.fromkeys(prev.columns + now.columns) if c not in IDENTITY_COLS]
    changed = 0
    for ident in dict.fromkeys(list(a) + list(b)):
        old, new = a.get(ident, []), b.get(ident, [])
        for i in range(max(len(old), len(new))):
            if i >= len(new):
                counts["削除"] += 1
                if len(samples) < SAMPLE_LIMIT:
                    samples.append({"kind": "削除", "identity": _ident_text(ident)})
                continue
            if i >= len(old):
                counts["追加"] += 1
                if len(samples) < SAMPLE_LIMIT:
                    samples.append({"kind": "追加", "identity": _ident_text(ident)})
                continue
            moved = sorted({_kind_of(c) for c in cols if old[i].get(c, "") != new[i].get(c, "")})
            if not moved:
                continue
            changed += 1
            for kind in moved:
                counts[kind] += 1
            if len(samples) < SAMPLE_LIMIT:
                samples.append({"kind": "/".join(moved), "identity": _ident_text(ident),
                                "old": old[i].get("value", ""), "new": new[i].get("value", "")})
    return Diff(len(prev), len(now), changed, counts, tuple(samples))


# ---------------------------------------------------------------- 表そのものの検査(関所)

@dataclass(frozen=True)
class Finding:
    kind: str
    key: str
    rows: tuple
    detail: str

    def as_dict(self) -> dict:
        return {"kind": self.kind, "key": self.key, "rows": list(self.rows), "detail": self.detail}


def _overlap(af: date, at: "date | None", bf: date, bt: "date | None") -> bool:
    """半開区間 [af, at) と [bf, bt) が重なるか。None = 開いたまま。"""
    if at is not None and bf >= at:
        return False
    if bt is not None and af >= bt:
        return False
    return True


def _sel_text(dims: tuple, sel: tuple) -> str:
    parts = [f"{d.removeprefix(SEL_PREFIX)}={v or '*'}" for d, v in zip(dims, sel)]
    return ",".join(parts) if parts else "(次元なし)"


def validate_rows(table: Table) -> list:
    """有効期間の重なりと期間の穴だけを見る。直さない、一覧で返すだけ。"""
    out: list = []
    groups: dict = {}
    for i, rec in enumerate(table.records, 1):
        if not rec["valid_from"]:
            continue   # 施行日未定の行は期間を持たないので、重なりにも穴にも数えない
        gkey = (rec["key"], tuple(rec.get(d, "") for d in table.dims), rec["priority"])
        groups.setdefault(gkey, []).append((i, rec))
    for (key, sel, pr), rs in sorted(groups.items()):
        rs = sorted(rs, key=lambda it: (_parse_date(it[1]["valid_from"], f"行 {it[0]} の valid_from"), it[0]))
        for n, (i, x) in enumerate(rs):
            xf = _parse_date(x["valid_from"], f"行 {i} の valid_from")
            xt = _opt_date(x.get("valid_to", ""), f"行 {i} の valid_to")
            xkf = _parse_date(x["known_from"], f"行 {i} の known_from")
            xkt = _opt_date(x.get("known_to", ""), f"行 {i} の known_to")
            for j, y in rs[n + 1:]:
                yf = _parse_date(y["valid_from"], f"行 {j} の valid_from")
                yt = _opt_date(y.get("valid_to", ""), f"行 {j} の valid_to")
                ykf = _parse_date(y["known_from"], f"行 {j} の known_from")
                ykt = _opt_date(y.get("known_to", ""), f"行 {j} の known_to")
                if _overlap(xf, xt, yf, yt) and _overlap(xkf, xkt, ykf, ykt):
                    out.append(Finding("有効期間の重なり", key, (i, j),
                                       f"対象 {_sel_text(table.dims, sel)} / priority {pr} で期間が重なる"))
        for (i, x), (j, y) in zip(rs, rs[1:]):
            xt = _opt_date(x.get("valid_to", ""), f"行 {i} の valid_to")
            yf = _parse_date(y["valid_from"], f"行 {j} の valid_from")
            if xt is not None and xt < yf:
                out.append(Finding("期間の穴", key, (i, j),
                                   f"対象 {_sel_text(table.dims, sel)} / priority {pr} で "
                                   f"{xt} 〜 {yf} が空いている"))
    return out


# ---------------------------------------------------------------- 指紋

def sha256_of(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class Fingerprint:
    name: str
    sha256: str
    fetched_at: str

    def as_dict(self) -> dict:
        return {"name": self.name, "sha256": self.sha256, "fetched_at": self.fetched_at}

    @classmethod
    def of_file(cls, name: str, path: str | Path) -> "Fingerprint":
        p = Path(path)
        ts = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).replace(microsecond=0)
        return cls(name, sha256_of(p), ts.isoformat())


def _fp_key(fps) -> tuple:
    out = []
    for f in fps:
        out.append((f["name"], f["sha256"]) if isinstance(f, dict) else (f.name, f.sha256))
    return tuple(sorted(out))


# ---------------------------------------------------------------- 台帳の 1 行

@dataclass(frozen=True)
class Entry:
    run_at: str
    status: str
    reason: str = ""
    detail: str = ""
    inputs: tuple = ()
    first_run: bool = False
    rows_prev: int = 0
    rows_now: int = 0
    changed: "int | None" = None
    counts: "dict | None" = None
    findings_total: int = 0
    findings: tuple = ()
    samples: tuple = ()
    applied: bool = False
    sha256: str = ""
    prev_sha256: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def as_dict(self) -> dict:
        return {"run_at": self.run_at, "status": self.status, "reason": self.reason, "detail": self.detail,
                "inputs": [dict(i) for i in self.inputs], "first_run": self.first_run,
                "rows_prev": self.rows_prev, "rows_now": self.rows_now,
                "changed": self.changed, "counts": self.counts,
                "findings_total": self.findings_total, "findings": [dict(f) for f in self.findings],
                "samples": [dict(s) for s in self.samples], "applied": self.applied,
                "sha256": self.sha256, "prev_sha256": self.prev_sha256}

    @classmethod
    def from_dict(cls, d: dict) -> "Entry":
        counts = d.get("counts")
        return cls(run_at=str(d.get("run_at", "")), status=str(d.get("status", "")),
                   reason=str(d.get("reason", "")), detail=str(d.get("detail", "")),
                   inputs=tuple(d.get("inputs") or ()), first_run=bool(d.get("first_run", False)),
                   rows_prev=int(d.get("rows_prev", 0)), rows_now=int(d.get("rows_now", 0)),
                   changed=None if d.get("changed") is None else int(d["changed"]),
                   counts=None if counts is None else {k: int(counts.get(k, 0)) for k in KINDS},
                   findings_total=int(d.get("findings_total", 0)),
                   findings=tuple(d.get("findings") or ()), samples=tuple(d.get("samples") or ()),
                   applied=bool(d.get("applied", False)), sha256=str(d.get("sha256", "")),
                   prev_sha256=str(d.get("prev_sha256", "")))


def read_ledger(path: str | Path) -> list:
    """追記専用の台帳を読む。行の削除・書き換えはこの部品からはできない。"""
    p = Path(path)
    if not p.exists():
        return []
    out: list = []
    for n, line in enumerate(p.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError as e:
            raise LedgerError(f"台帳 行 {n} が JSON として読めない: {e}") from e
        if not isinstance(d, dict):
            raise LedgerError(f"台帳 行 {n} が 1 行 1 件のかたちでない")
        out.append(Entry.from_dict(d))
    return out


def _append(path: str | Path, entry: Entry) -> Entry:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8", newline="") as f:
        f.write(json.dumps(entry.as_dict(), ensure_ascii=False) + "\n")
    return entry


# ---------------------------------------------------------------- 1 回の更新を記録する

def record(ledger: str | Path, now: str | Path, prev: "str | Path | None" = None,
           output: "str | Path | None" = None, fingerprints=(), run_at: "str | None" = None,
           apply: bool = False, max_row_change: float = MAX_ROW_CHANGE) -> Entry:
    """更新 1 回を台帳に 1 行追記する。検査に落ちたら本番ファイルは書き換えない。

    apply=True の回だけ本番ファイルを差し替える。「見つからなければ最新へ」に相当する引数は無い。
    run_at が台帳の最後の行と同じか、それより前のときは追記しない(LedgerError)。
    """
    entries = read_ledger(ledger)
    last = entries[-1] if entries else None
    stamp = run_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if last is not None:
        if stamp == last.run_at:
            raise LedgerError(f"run_at の重複: {stamp} の行はすでにある。追記すると実行の順序が台帳から決まらない")
        if stamp < last.run_at:
            raise LedgerError(f"run_at が台帳の最後の行({last.run_at})より前: {stamp}")
    fps = tuple(f.as_dict() if isinstance(f, Fingerprint) else dict(f) for f in fingerprints)
    out_path = Path(output) if output is not None else None
    prev_sha = sha256_of(out_path) if out_path is not None and out_path.exists() else ""

    def fail(reason: str, detail: str, **kw) -> Entry:
        return _append(ledger, Entry(run_at=stamp, status="failed", reason=reason, detail=detail,
                                     inputs=fps, applied=False, sha256=prev_sha, prev_sha256=prev_sha, **kw))

    # 1. 台帳の鎖(本番ファイルが台帳を通さずに変わっていないか)
    if last is not None and last.sha256 != prev_sha:
        return fail("台帳の鎖が切れている",
                    f"前の行の sha256({last.sha256[:12] or '(なし)'})と"
                    f"今の本番ファイル({prev_sha[:12] or '(なし)'})が繋がらない")
    # 2. 入力が表として読めるか
    try:
        now_table = Table.load(now)
        prev_table = Table.load(prev) if prev is not None and Path(prev).exists() else None
    except TableError as e:
        return fail("入力の列が足りない", str(e))
    # 3. 差分を数える(関所に落ちた回も、何を変えようとした回だったかを残す)
    diff = diff_tables(prev_table, now_table)
    found = validate_rows(now_table)
    common = {"first_run": prev_table is None, "rows_prev": diff.rows_prev, "rows_now": diff.rows_now,
              "changed": diff.changed, "counts": diff.counts, "findings_total": len(found),
              "findings": tuple(f.as_dict() for f in found[:SAMPLE_LIMIT]), "samples": diff.samples}
    # 4. 指紋と差分の食い違い
    if last is not None and fps and last.inputs:
        same_fp = _fp_key(fps) == _fp_key(last.inputs)
        if same_fp and (diff.any_change or diff.changed):
            return fail("指紋が前回と同一なのに差分あり",
                        f"入力の sha256 は前回と同じだが、差分が {diff.changed} 行 / "
                        f"追加 {diff.counts['追加']} / 削除 {diff.counts['削除']} 出た", **common)
        if not same_fp and not diff.any_change and not diff.changed:
            return fail("指紋が違うのに差分 0",
                        "入力の sha256 が前回と違うのに、行の差分が 1 件も出ていない", **common)
    # 5. 行数の急変
    if diff.rows_prev and abs(diff.rows_now - diff.rows_prev) > diff.rows_prev * max_row_change:
        return fail("行数の急変",
                    f"行数が {diff.rows_prev} から {diff.rows_now} へ動いた(しきい値 {max_row_change})",
                    **common)
    # 6. 表そのものの検査
    for kind in FINDINGS:
        hit = [f for f in found if f.kind == kind]
        if hit:
            rows = "/".join(str(n) for n in hit[0].rows)
            return fail(kind, f"{kind} が {len(hit)} 件({hit[0].key} 行 {rows})", **common)
    # 7. ここまで通った回だけ、呼び出し側が明示したときに差し替える
    sha, applied = prev_sha, False
    if apply and out_path is not None:
        data = now_table.serialize()
        tmp = out_path.with_name(out_path.name + ".tmp")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(data)
        os.replace(tmp, out_path)
        sha, applied = hashlib.sha256(data).hexdigest(), True
    return _append(ledger, Entry(run_at=stamp, status="ok", inputs=fps, applied=applied,
                                 sha256=sha, prev_sha256=prev_sha, **common))


# ---------------------------------------------------------------- 一覧と自己検査

def inventory(entries: list) -> list:
    """台帳を 1 行 1 件の時系列一覧にして返す。記事の表と図はこの出力をそのまま使う。"""
    out: list = []
    for n, e in enumerate(entries, 1):
        out.append({"n": n, "run_at": e.run_at, "status": e.status, "reason": e.reason,
                    "inputs": [str(f.get("sha256", ""))[:8] for f in e.inputs],
                    "rows_prev": e.rows_prev, "rows_now": e.rows_now, "changed": e.changed,
                    "counts": e.counts, "applied": e.applied,
                    "sha": e.sha256[:8], "prev_sha": e.prev_sha256[:8],
                    "sha_moved": bool(e.sha256 != e.prev_sha256)})
    return out


@dataclass(frozen=True)
class Replay:
    ok: bool
    runs: int = 0
    rows: int = 0
    sha256: str = ""
    reason: str = ""
    detail: str = ""
    line: "int | None" = None

    def as_dict(self) -> dict:
        if self.ok:
            return {"ok": True, "runs": self.runs, "rows": self.rows, "sha256": self.sha256}
        return {"ok": False, "reason": self.reason, "detail": self.detail, "line": self.line}


def replay(entries: list, at: "str | None" = None) -> Replay:
    """台帳を先頭から辿り、指定時点の行数と本番ファイルの sha を再構成して台帳の行と突き合わせる。

    台帳そのものが一覧として使えるかの自己検査。鎖・run_at・件数の積み上げのどれかが合わなければ止まる。
    """
    seen: dict = {}
    rows, sha, used = 0, "", 0
    for n, e in enumerate(entries, 1):
        if at is not None and e.run_at > at:
            break
        if e.run_at in seen:
            return Replay(False, reason="run_at の重複",
                          detail=f"行 {seen[e.run_at]} と行 {n} の run_at が同じ({e.run_at})", line=n)
        if used and e.run_at < entries[n - 2].run_at:
            return Replay(False, reason="台帳の鎖が切れている",
                          detail=f"行 {n} の run_at({e.run_at})が行 {n - 1} より前", line=n)
        seen[e.run_at] = n
        if used and e.prev_sha256 != sha:
            return Replay(False, reason="台帳の鎖が切れている",
                          detail=f"行 {n} の prev_sha256({e.prev_sha256[:12] or '(なし)'})が"
                                 f"行 {n - 1} の sha256({sha[:12] or '(なし)'})と繋がらない", line=n)
        if not e.applied and e.sha256 != e.prev_sha256:
            return Replay(False, reason="台帳の鎖が切れている",
                          detail=f"行 {n} は applied でないのに sha256 が動いている", line=n)
        if e.counts is not None:
            expect = e.rows_prev + e.counts["追加"] - e.counts["削除"]
            if expect != e.rows_now:
                return Replay(False, reason="台帳の鎖が切れている",
                              detail=f"行 {n} の件数が積み上がらない: {e.rows_prev} + 追加 "
                                     f"{e.counts['追加']} - 削除 {e.counts['削除']} = {expect} だが "
                                     f"rows_now は {e.rows_now}", line=n)
            total = sum(e.counts[k] for k in KINDS[2:])
            if e.changed is not None and (e.changed > total or (total and e.changed == 0)):
                return Replay(False, reason="台帳の鎖が切れている",
                              detail=f"行 {n} の changed({e.changed})が種別の合計({total})と合わない",
                              line=n)
        if e.status == "ok" and used and e.inputs and entries[n - 2].inputs and e.counts is not None:
            same_fp = _fp_key(e.inputs) == _fp_key(entries[n - 2].inputs)
            moved = bool(e.changed) or any(e.counts[k] for k in KINDS)
            if same_fp and moved:
                return Replay(False, reason="指紋が前回と同一なのに差分あり",
                              detail=f"行 {n} は入力の sha256 が行 {n - 1} と同じだが差分がある", line=n)
            if not same_fp and not moved:
                return Replay(False, reason="指紋が違うのに差分 0",
                              detail=f"行 {n} は入力の sha256 が行 {n - 1} と違うのに差分が 0", line=n)
        if e.reason and e.reason not in REASONS:
            return Replay(False, reason="台帳の鎖が切れている",
                          detail=f"行 {n} の理由コード『{e.reason}』は登録されていない", line=n)
        if e.status == "ok" and e.counts is not None:
            rows = e.rows_now
        sha = e.sha256
        used = n
    return Replay(True, runs=used, rows=rows, sha256=sha)


# ---------------------------------------------------------------- CLI

def _inputs(args) -> tuple:
    out: list = []
    for item in args.input or []:
        if "=" not in item:
            raise TableError(f"--input は 名前=パス で書く: {item!r}")
        name, path = item.split("=", 1)
        out.append(Fingerprint.of_file(name.strip(), path.strip()))
    return tuple(out)


def _cli_record(args) -> int:
    e = record(args.ledger, args.now, args.prev, args.output, _inputs(args),
               run_at=args.run_at, apply=args.apply, max_row_change=args.max_row_change)
    print(json.dumps(e.as_dict(), ensure_ascii=False))
    return 0 if e.ok else 3


def _cli_inventory(args) -> int:
    rows = inventory(read_ledger(args.ledger))
    print(json.dumps({"ok": True, "runs": len(rows), "rows": rows}, ensure_ascii=False))
    return 0


def _cli_replay(args) -> int:
    r = replay(read_ledger(args.ledger), args.at)
    print(json.dumps(r.as_dict(), ensure_ascii=False))
    return 0 if r.ok else 3


def _cli_validate(args) -> int:
    table = Table.load(args.table)
    found = validate_rows(table)
    print(json.dumps({"ok": not found, "rows": len(table),
                      "findings": [f.as_dict() for f in found]}, ensure_ascii=False))
    return 3 if found else 0


def main(argv: "list | None" = None) -> int:
    p = argparse.ArgumentParser(description="数表の更新を 実行 1 回 = 台帳 1 行 で残す")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record", help="更新 1 回を台帳に追記する")
    r.add_argument("--ledger", required=True)
    r.add_argument("--now", required=True, help="今回の行の表(CSV / JSON)")
    r.add_argument("--prev", help="前回の行の表。省略 = 初回")
    r.add_argument("--output", help="本番ファイル。apply した回だけ書き換える")
    r.add_argument("--input", action="append", metavar="名前=パス",
                   help="取得したファイル。sha256 と更新時刻を指紋にする。繰り返せる")
    r.add_argument("--run-at", metavar="ISO8601")
    r.add_argument("--apply", action="store_true", help="関所を全部通ったら本番ファイルを差し替える")
    r.add_argument("--max-row-change", type=float, default=MAX_ROW_CHANGE)
    r.set_defaults(func=_cli_record)
    i = sub.add_parser("inventory", help="台帳を 1 行 1 件の時系列一覧にする")
    i.add_argument("--ledger", required=True)
    i.set_defaults(func=_cli_inventory)
    rp = sub.add_parser("replay", help="台帳を先頭から辿って自己検査する")
    rp.add_argument("--ledger", required=True)
    rp.add_argument("--at", metavar="ISO8601", help="この時点までを辿る")
    rp.set_defaults(func=_cli_replay)
    v = sub.add_parser("validate", help="表そのものを検査する(重なり・穴)")
    v.add_argument("table")
    v.set_defaults(func=_cli_validate)
    args = p.parse_args(argv)
    try:
        return args.func(args)
    except (TableError, LedgerError) as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except OSError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
