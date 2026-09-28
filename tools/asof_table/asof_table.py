"""asof_table — 毎年変わる数表を「基準日・対象・公表時点」で引く部品。

表は 1 枚の行の表(CSV か JSON)。1 行 = 1 条項の適用単位で、次の列を持つ。

    key            何を求めるか(表の中で同じ key の行は同じ basis を持つ)
    basis          case のどの日付で有効期間を引くかの名前(対象月初日 / 賃金締切日 / 請求日 …)
    valid_from     有効時間の始まり(半開区間 [valid_from, valid_to))。空 = 施行日未定(引けない行)
    valid_to       有効時間の終わり。空 = 開いたまま
    known_from     知識時間の始まり(公表日)。空は許さない
    known_to       知識時間の終わり(差し替えられた行)。空 = 最新
    known_quality  known_from の質。実値 / 仮置き(空 = 仮置き として扱う)
    priority       0 本則 / 10 経過措置 / 20 特例
    value          値。文字列のまま返す(型変換・端数処理・数式評価はしない)
    source         出典。返り値に必ず付ける
    sel_*          対象セグメントの次元。列名は呼ぶ側が決める。空欄 = ワイルドカード

引き方は resolve(table, key, case, as_of)。知識時間 → 有効時間 → 対象 → 最高 priority の 1 行、の順に絞る。
決まらないときは理由コードで止まる。黙って現行値や直近値へ落ちる経路は無い(fallback の引数も持たない)。

標準ライブラリのみ(csv / json / datetime / argparse)。CLI と関数の両方。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

SEL_PREFIX = "sel_"
REQUIRED = ("key", "basis", "valid_from", "known_from", "priority", "value", "source")
OPTIONAL = ("valid_to", "known_to", "known_quality")
PRIORITIES = {0: "本則", 10: "経過措置", 20: "特例"}

REAL, PROVISIONAL = "実値", "仮置き"

# 決まらないときに返す理由コード(この 5 つで全部。値は返さない)
REASONS = {
    "基準日が case に無い": "この key は basis で宣言した日付で引く。case にその名前の日付が無いので、どの日付で引くかを機械では選べない",
    "as_of 時点で未公表": "有効時間では当たる行があるが、その行は as_of の時点ではまだ公表されていない。当時の知識では引けない",
    "収録範囲の外": "key が表に無いか、基準日が表の期間のどれにも入らない(前後の外か、期間の穴)",
    "同順位で複数該当": "同じ priority の行が 2 つ以上当たった。どちらを採るかは表の外の判断になる",
    "公表日が仮置き": "当たるはずの行の known_from が仮置き(実際の公表日ではない)なので、as_of 時点で公表済みだったかを機械では決められない",
}

# validate() が返す不備の種類
FINDINGS = ("期間の逆転", "知識期間の逆転", "基準日の不一致", "priority が登録外", "有効期間の重なり", "期間の穴")


class TableError(ValueError):
    """表そのものが読めない / 形が違う。引き当ての失敗(理由コード)とは別に扱う。"""


def parse_date(s: str, what: str) -> date:
    try:
        return date.fromisoformat(str(s).strip())
    except ValueError as e:
        raise TableError(f"{what} が YYYY-MM-DD で読めない: {s!r}({e})") from e


def _opt_date(s: str, what: str) -> date | None:
    s = (s or "").strip()
    return parse_date(s, what) if s else None


@dataclass(frozen=True)
class Row:
    number: int          # 表の中の行番号(データ行の 1 始まり)。返り値に必ず付ける
    key: str
    basis: str
    valid_from: date | None
    valid_to: date | None
    known_from: date
    known_to: date | None
    known_quality: str
    priority: int
    value: str
    source: str
    sel: dict[str, str] = field(default_factory=dict)

    @property
    def provisional(self) -> bool:
        return self.known_quality != REAL

    def valid_on(self, on: date) -> bool:
        """有効時間 [valid_from, valid_to) に入るか。valid_from が空の行は決して当たらない(施行日未定)。"""
        if self.valid_from is None:
            return False
        return self.valid_from <= on and (self.valid_to is None or on < self.valid_to)

    def known_at(self, as_of: date | None) -> bool:
        """知識時間 [known_from, known_to) に入るか。as_of が None なら差し替えられていない行 = いまの知識。"""
        if as_of is None:
            return self.known_to is None
        return self.known_from <= as_of and (self.known_to is None or as_of < self.known_to)

    def matches(self, case: dict[str, str], dims: tuple[str, ...]) -> bool:
        """対象セグメントの一致。行の側が空欄の次元はワイルドカード(何にでも当たる)。"""
        for d in dims:
            want = self.sel.get(d, "")
            if want == "":
                continue
            if str(case.get(d, "")) != want:
                return False
        return True

    def sel_key(self, dims: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(self.sel.get(d, "") for d in dims)


@dataclass(frozen=True)
class Result:
    """引き当ての結果。ok なら値と出典、ok でなければ理由コード。どちらでも key と basis は付く。"""
    ok: bool
    key: str
    basis: str = ""
    value: str = ""
    source: str = ""
    valid_from: date | None = None
    priority: int | None = None
    row: int | None = None
    reason: str = ""
    detail: str = ""
    rows: tuple[int, ...] = ()

    def as_dict(self) -> dict:
        if self.ok:
            return {"ok": True, "key": self.key, "basis": self.basis, "value": self.value,
                    "source": self.source, "valid_from": self.valid_from.isoformat(),
                    "priority": self.priority, "priority_name": PRIORITIES.get(self.priority, "?"),
                    "row": self.row}
        return {"ok": False, "key": self.key, "basis": self.basis, "reason": self.reason,
                "detail": self.detail, "rows": list(self.rows)}


@dataclass(frozen=True)
class Finding:
    kind: str
    key: str
    rows: tuple[int, ...]
    detail: str

    def as_dict(self) -> dict:
        return {"kind": self.kind, "key": self.key, "rows": list(self.rows), "detail": self.detail}


class Table:
    """行の表。読んだ時点で形だけを検査する(中身の検査は validate)。"""

    def __init__(self, rows: list[Row], dims: tuple[str, ...], origin: str = ""):
        self.rows = rows
        self.dims = dims
        self.origin = origin

    def __len__(self) -> int:
        return len(self.rows)

    @classmethod
    def from_records(cls, records: list[dict], origin: str = "") -> "Table":
        if not records:
            raise TableError("表に行が 1 つも無い")
        cols = list(records[0].keys())
        missing = [c for c in REQUIRED if c not in cols]
        if missing:
            raise TableError(f"必要な列が無い: {'/'.join(missing)}")
        dims = tuple(c for c in cols if c.startswith(SEL_PREFIX))
        rows: list[Row] = []
        for i, rec in enumerate(records, 1):
            def get(c: str, _rec: dict = rec) -> str:
                v = _rec.get(c, "")
                return "" if v is None else str(v).strip()
            key, basis = get("key"), get("basis")
            if not key:
                raise TableError(f"行 {i}: key が空")
            if not basis:
                raise TableError(f"行 {i}: basis が空(どの日付で引くかを行の側で宣言する)")
            if not get("known_from"):
                raise TableError(f"行 {i}: known_from が空(公表時点を空にすると、当時の知識を再現できない)")
            pr = get("priority")
            if not pr.lstrip("-").isdigit():
                raise TableError(f"行 {i}: priority が整数でない: {pr!r}")
            rows.append(Row(
                number=i, key=key, basis=basis,
                valid_from=_opt_date(get("valid_from"), f"行 {i} の valid_from"),
                valid_to=_opt_date(get("valid_to"), f"行 {i} の valid_to"),
                known_from=parse_date(get("known_from"), f"行 {i} の known_from"),
                known_to=_opt_date(get("known_to"), f"行 {i} の known_to"),
                known_quality=get("known_quality") or PROVISIONAL,
                priority=int(pr), value=get("value"), source=get("source"),
                sel={d: get(d) for d in dims},
            ))
        return cls(rows, dims, origin)

    @classmethod
    def from_csv(cls, path: str | Path) -> "Table":
        p = Path(path)
        with p.open(encoding="utf-8-sig", newline="") as f:
            return cls.from_records(list(csv.DictReader(f)), str(p))

    @classmethod
    def from_json(cls, path: str | Path) -> "Table":
        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        if not isinstance(data, list):
            raise TableError("JSON は行の配列で書く")
        return cls.from_records(data, str(p))

    @classmethod
    def load(cls, path: str | Path) -> "Table":
        p = Path(path)
        return cls.from_json(p) if p.suffix.lower() == ".json" else cls.from_csv(p)

    def keys(self) -> list[str]:
        seen: dict[str, None] = {}
        for r in self.rows:
            seen.setdefault(r.key, None)
        return list(seen)

    def basis_of(self, key: str) -> str:
        """key の basis。表の中で食い違っていたら表の不備として止める(引き当てで黙って片方を採らない)。"""
        names = {r.basis for r in self.rows if r.key == key}
        if len(names) > 1:
            raise TableError(f"key『{key}』の basis が行ごとに違う: {'/'.join(sorted(names))}")
        return names.pop() if names else ""


def resolve(table: Table, key: str, case: dict[str, str], as_of: date | None = None) -> Result:
    """key を case と as_of で引く。決まらないときは理由コードを返す(値は返さない)。

    as_of=None は「いまの知識」= 差し替えられていない行だけを見る、の意味。
    """
    rows = [r for r in table.rows if r.key == key]
    if not rows:
        return Result(False, key, reason="収録範囲の外", detail=f"key『{key}』は表に無い")
    basis = table.basis_of(key)
    if basis not in case:
        return Result(False, key, basis, reason="基準日が case に無い",
                      detail=f"この key は『{basis}』で引く。case にあるのは {'/'.join(sorted(case)) or '(空)'}")
    on = parse_date(str(case[basis]), f"case の『{basis}』")

    # 有効時間と対象だけで当たる行(= 知識時間を外したら当たるはずの行)
    shadow = [r for r in rows if r.valid_on(on) and r.matches(case, table.dims)]
    matched = [r for r in shadow if r.known_at(as_of)]

    if not matched:
        if as_of is not None and shadow:
            prov = [r for r in shadow if r.provisional and as_of < r.known_from]
            if prov:
                return Result(False, key, basis, reason="公表日が仮置き",
                              detail=f"行 {'/'.join(str(r.number) for r in prov)} の known_from は仮置き。"
                                     f"as_of {as_of.isoformat()} に公表済みだったかは表から決まらない",
                              rows=tuple(r.number for r in prov))
            return Result(False, key, basis, reason="as_of 時点で未公表",
                          detail=f"行 {'/'.join(str(r.number) for r in shadow)} は {as_of.isoformat()} の時点で未公表",
                          rows=tuple(r.number for r in shadow))
        return Result(False, key, basis, reason="収録範囲の外",
                      detail=f"『{basis}』{on.isoformat()} と対象に当たる行が無い")

    top = max(r.priority for r in matched)
    best = [r for r in matched if r.priority == top]
    if len(best) > 1:
        return Result(False, key, basis, reason="同順位で複数該当",
                      detail=f"priority {top}({PRIORITIES.get(top, '?')})の行が {len(best)} 本当たった",
                      rows=tuple(r.number for r in best))
    r = best[0]
    return Result(True, key, basis, value=r.value, source=r.source, valid_from=r.valid_from,
                  priority=r.priority, row=r.number)


def validate(table: Table) -> list[Finding]:
    """表そのものの検査。直さない、一覧で返すだけ。"""
    out: list[Finding] = []
    for r in table.rows:
        if r.valid_from is not None and r.valid_to is not None and r.valid_from >= r.valid_to:
            out.append(Finding("期間の逆転", r.key, (r.number,),
                               f"valid_from {r.valid_from} >= valid_to {r.valid_to}"))
        if r.known_to is not None and r.known_from >= r.known_to:
            out.append(Finding("知識期間の逆転", r.key, (r.number,),
                               f"known_from {r.known_from} >= known_to {r.known_to}"))
        if r.priority not in PRIORITIES:
            out.append(Finding("priority が登録外", r.key, (r.number,),
                               f"priority {r.priority} は 0/10/20 のどれでもない"))
    for key in table.keys():
        names = sorted({r.basis for r in table.rows if r.key == key})
        if len(names) > 1:
            out.append(Finding("基準日の不一致", key,
                               tuple(r.number for r in table.rows if r.key == key),
                               f"同じ key に basis が {len(names)} 種類: {'/'.join(names)}"))
    groups: dict[tuple, list[Row]] = {}
    for r in table.rows:
        if r.valid_from is None:
            continue   # 施行日未定の行は期間を持たないので、重なりにも穴にも数えない
        groups.setdefault((r.key, r.sel_key(table.dims), r.priority), []).append(r)
    for (key, sel, pr), rs in groups.items():
        rs = sorted(rs, key=lambda r: (r.valid_from, r.number))
        for i, a in enumerate(rs):
            for b in rs[i + 1:]:
                if _overlap(a.valid_from, a.valid_to, b.valid_from, b.valid_to) and \
                        _overlap(a.known_from, a.known_to, b.known_from, b.known_to):
                    out.append(Finding("有効期間の重なり", key, (a.number, b.number),
                                       f"対象 {_sel_text(table.dims, sel)} / priority {pr} で期間が重なる"))
        for a, b in zip(rs, rs[1:]):
            if a.valid_to is not None and a.valid_to < b.valid_from:
                out.append(Finding("期間の穴", key, (a.number, b.number),
                                   f"対象 {_sel_text(table.dims, sel)} / priority {pr} で "
                                   f"{a.valid_to} 〜 {b.valid_from} が空いている"))
    return out


def _overlap(af: date, at: date | None, bf: date, bt: date | None) -> bool:
    """半開区間 [af, at) と [bf, bt) が重なるか。None = 開いたまま。"""
    if at is not None and bf >= at:
        return False
    if bt is not None and af >= bt:
        return False
    return True


def _sel_text(dims: tuple[str, ...], sel: tuple[str, ...]) -> str:
    parts = [f"{d.removeprefix(SEL_PREFIX)}={v or '*'}" for d, v in zip(dims, sel)]
    return ",".join(parts) if parts else "(次元なし)"


def naive_lookup(table: Table, key: str, on: date, fold: dict[str, str] | None = None) -> Row | None:
    """比較用。「適用開始日つきの履歴」= key と 1 つの日付だけで、その日以前の最新の行を返す。

    fold は、その形でも key の側に畳めていた対象の次元(例: 地域ごとに別の key にしてある場合)。
    畳めていない次元・公表時点・priority は見ない。同じ適用開始日に 2 行あれば並び順で後ろの行になる。
    当たらなければ None(この形には理由コードが無く、None と「値が無い」を区別できない)。
    """
    fold = fold or {}
    cands = [r for r in table.rows
             if r.key == key and r.valid_from is not None and r.valid_from <= on
             and all(r.sel.get(d, "") in ("", v) for d, v in fold.items())]
    if not cands:
        return None
    return max(cands, key=lambda r: (r.valid_from, r.number))


def _cli_resolve(args) -> int:
    table = Table.load(args.table)
    case: dict[str, str] = {}
    for item in args.case or []:
        if "=" not in item:
            raise TableError(f"--case は 名前=値 で書く: {item!r}")
        k, v = item.split("=", 1)
        case[k.strip()] = v.strip()
    as_of = parse_date(args.as_of, "--as-of") if args.as_of else None
    res = resolve(table, args.key, case, as_of)
    print(json.dumps(res.as_dict(), ensure_ascii=False))
    return 0 if res.ok else 3


def _cli_validate(args) -> int:
    table = Table.load(args.table)
    found = validate(table)
    print(json.dumps({"ok": not found, "rows": len(table), "keys": len(table.keys()),
                      "findings": [f.as_dict() for f in found]}, ensure_ascii=False))
    return 3 if found else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="毎年変わる数表を基準日・対象・公表時点で引く")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("resolve", help="1 件引く")
    r.add_argument("table")
    r.add_argument("--key", required=True)
    r.add_argument("--case", action="append", metavar="名前=値", help="case の属性。繰り返せる")
    r.add_argument("--as-of", metavar="YYYY-MM-DD", help="この時点の知識で引く(省略 = いまの知識)")
    r.set_defaults(func=_cli_resolve)
    v = sub.add_parser("validate", help="表そのものを検査する")
    v.add_argument("table")
    v.set_defaults(func=_cli_validate)
    args = p.parse_args(argv)
    try:
        return args.func(args)
    except TableError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except OSError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
