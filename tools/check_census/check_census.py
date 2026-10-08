"""check_census — 書かれている検証を数えるのではなく、宣言された runner を走らせて結果だけを台帳に残す。

棚卸しの記録に「テストが在る」と数えられた本数が並んでいても、それは **走らせた結果を 1 件も言っていない**。
在ることと通ったことは別の事実で、件数は前者しか言わない。この部品は宣言表に書かれた runner だけを実際に
走らせ、通った / 落ちた / 走らなかった / テストが無い の 4 値を、分母の内訳つきで台帳に残す。

持たせていないものが規律になっている。

  - **宣言に無いコマンドを実行しない**(フォルダを見て runner を推測で組み立てる経路が無い)
  - **シェルを経由しない**(argv は配列のまま渡す。文字列を結合してコマンドを作る経路が無い)
  - **ネットワークを既定で許さない**(allow_network が無い行は、外向きの既定を環境変数で落として走らせる)
  - **走らなかったものを通ったにも落ちたにも混ぜない**(4 値を 3 値に潰す引数が無い)
  - **合格率を単独で返さない**(4 値の件数と分母の内訳を必ず併記する)
  - **テストもコードも書き換えない**(直す・生成する・再試行する経路が無い。返すのは台帳と理由コードだけ)
  - **timeout を既定値で黙って延ばさない**(宣言表から取る。超えたら「走らなかった」に落ちて理由が付く)
  - **判定部分に所要時間・時刻・ホスト名を入れない**(非決定な値を一致判定に混ぜない)
  - **カバレッジを測らない**(テストの中身が妥当か・網羅しているかは部品の外)

入力は 1 つ、宣言表だけ。

    name           行を指す名前(重複は止まる)
    path           runner を走らせるフォルダ(宣言表のある場所からの相対パス、または絶対パス)
    declared       「テストが在るか」の grep 相当の宣言。在る / 無い / 不明
    runner         実行する argv を JSON の配列で明示(["python", "-m", "pytest", "-q"])
    timeout        秒。宣言表から取る
    required       はい / いいえ。はい の行が通らなければ終了コード 3
    allow_network  はい / いいえ / 空欄(列そのものが無くてもよい)。空欄は外向きの既定を落として走らせる
    source         その行の出典(どの記録から持ってきた宣言か)

判定したことは「宣言された runner が終了コード 0 を返したか」までで、テストが正しいことも、対象が
仕様どおり動くことも判定しない。標準ライブラリのみ(subprocess / csv / json / hashlib / pathlib /
datetime / platform / os / argparse)。
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# 宣言表の列。allow_network だけは無くてよい(無い = 外向きの既定を落とす)
DECL_COLUMNS = ("name", "path", "declared", "runner", "timeout", "required", "allow_network", "source")
NEEDED_COLUMNS = ("name", "path", "declared", "runner", "timeout", "required", "source")

DECLARED_VALUES = ("在る", "無い", "不明")
YES, NO = "はい", "いいえ"

PASSED, FAILED, NOT_RUN, NO_TESTS = "通った", "落ちた", "走らなかった", "テストが無い"
VERDICTS = (PASSED, FAILED, NOT_RUN, NO_TESTS)

# 「走らなかった」に付く理由コード(4 個)。通った / 落ちた には理由コードが付かない
NOT_RUN_REASONS = ("runner が無い", "timeout", "宣言の列が空欄", "path が無い")

# 止まる理由コード(6 個)。止まったときは 1 行も走らせない
STOP_REASONS = ("宣言表に必要な列が無い", "argv が配列でない", "timeout が空欄か数でない",
                "出典の列が空欄", "同じ name の行が 2 件以上", "2 回目の判定部分がバイト列として不一致")

TAIL_LINES = 10   # 出力のうち指紋を取る末尾の行数(固定。引数にしない)

# 台帳の判定部分に入る欄(この順で固定。所要時間・時刻・ホスト名は入れない)
JUDGEMENT_KEYS = ("name", "宣言", "判定", "理由コード", "終了コード", "出力の末尾の指紋")
# 判定部分から外す欄(非決定な値。sha256 の対象にしない)
TIMING_KEYS = ("name", "所要秒", "始めた時刻", "ホスト名")

# 外向きの既定を落とす環境変数(ソケットは塞がない。落ちたら落ちたと書くだけ)
NO_NETWORK_ENV = {
    "http_proxy": "http://127.0.0.1:9", "https_proxy": "http://127.0.0.1:9",
    "HTTP_PROXY": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9",
    "all_proxy": "http://127.0.0.1:9", "ALL_PROXY": "http://127.0.0.1:9",
    "no_proxy": "", "NO_PROXY": "",
    "PIP_NO_INDEX": "1", "PIP_RETRIES": "0", "PIP_TIMEOUT": "1",
    "CHECK_CENSUS_NETWORK": "dropped",
}


class DeclError(Exception):
    """宣言表として読めない(理由コードにせず終了コード 2 で返す = 宣言表を書く側の話)。"""


@dataclass(frozen=True)
class Pending:
    reason: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"reason": self.reason, "detail": self.detail}


@dataclass(frozen=True)
class Row:
    name: str
    path: str
    declared: str
    argv: tuple[str, ...]
    timeout: int
    required: bool
    allow_network: bool
    source: str


@dataclass(frozen=True)
class Result:
    name: str
    declared: str
    verdict: str
    reason: str                 # 走らなかった理由コード(走った行は空)
    exit_code: int | None       # 走らなかった / テストが無い 行は None
    tail_sha256: str            # 出力の末尾 TAIL_LINES 行の指紋(走らなかった行は空)
    required: bool
    source: str
    seconds: str                # 判定部分に入れない
    started: str                # 判定部分に入れない
    host: str                   # 判定部分に入れない

    def judgement(self) -> dict[str, object]:
        return {"name": self.name, "宣言": self.declared, "判定": self.verdict,
                "理由コード": self.reason, "終了コード": self.exit_code,
                "出力の末尾の指紋": self.tail_sha256}

    def timing(self) -> dict[str, str]:
        return {"name": self.name, "所要秒": self.seconds, "始めた時刻": self.started, "ホスト名": self.host}


@dataclass(frozen=True)
class Report:
    ok: bool
    pending: tuple[Pending, ...]
    declared_rows: int


@dataclass
class Declaration:
    rows: tuple[Row, ...]
    base: Path
    pending: tuple[Pending, ...] = ()

    @classmethod
    def load(cls, path: str | Path) -> "Declaration":
        p = Path(path)
        if not p.exists():
            raise DeclError(f"宣言表が無い: {p}")
        text = p.read_text(encoding="utf-8-sig")
        reader = csv.DictReader(text.splitlines())
        header = tuple(reader.fieldnames or ())
        pending: list[Pending] = []
        missing = [c for c in NEEDED_COLUMNS if c not in header]
        for c in missing:
            pending.append(Pending(STOP_REASONS[0], f"宣言表に {c} の列が無い"))
        if missing:
            return cls(rows=(), base=p.resolve().parent, pending=tuple(pending))
        rows: list[Row] = []
        seen: dict[str, int] = {}
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in header}
            name, declared = cell["name"], cell["declared"]
            if declared and declared not in DECLARED_VALUES:
                raise DeclError(f"行 {i}: declared は {' / '.join(DECLARED_VALUES)} のどれか: {declared}")
            for col in ("required", "allow_network"):
                if cell.get(col) and cell[col] not in (YES, NO):
                    raise DeclError(f"行 {i}: {col} は {YES} / {NO} か空欄: {cell[col]}")
            timeout = 0
            if not cell["timeout"].isdigit() or int(cell["timeout"]) <= 0:
                pending.append(Pending(STOP_REASONS[2],
                                       f"行 {i}({name or '名前なし'})の timeout: {cell['timeout'] or '空欄'}"))
            else:
                timeout = int(cell["timeout"])
            argv: tuple[str, ...] = ()
            if cell["runner"]:
                try:
                    parsed = json.loads(cell["runner"])
                except json.JSONDecodeError:
                    parsed = None
                if not isinstance(parsed, list) or not parsed or not all(isinstance(x, str) for x in parsed):
                    pending.append(Pending(STOP_REASONS[1],
                                           f"行 {i}({name or '名前なし'})の runner: {cell['runner']}"))
                else:
                    argv = tuple(parsed)
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[3], f"行 {i}({name or '名前なし'})の出典が空欄"))
            if name and name in seen:
                pending.append(Pending(STOP_REASONS[4], f"{name}: 行 {seen[name]} と行 {i}"))
            elif name:
                seen[name] = i
            rows.append(Row(name=name, path=cell["path"], declared=declared or "不明", argv=argv,
                            timeout=timeout, required=cell["required"] == YES,
                            allow_network=cell.get("allow_network", "") == YES, source=cell["source"]))
        return cls(rows=tuple(rows), base=p.resolve().parent, pending=tuple(pending))


@dataclass
class Census:
    report: Report
    results: tuple[Result, ...]

    # ---------------------------------------------------------------- 件数
    def counts(self) -> dict[str, int]:
        return {v: sum(1 for r in self.results if r.verdict == v) for v in VERDICTS}

    def declared_counts(self) -> dict[str, int]:
        return {d: sum(1 for r in self.results if r.declared == d) for d in DECLARED_VALUES}

    def denominator(self) -> dict[str, int]:
        c = self.counts()
        return {"宣言の行数": self.report.declared_rows,
                "走らせた数": c[PASSED] + c[FAILED],
                "走らなかった数": c[NOT_RUN],
                "テストが無い数": c[NO_TESTS]}

    def not_passed_required(self) -> tuple[str, ...]:
        return tuple(r.name for r in self.results if r.required and r.verdict != PASSED)

    def rate(self) -> dict[str, object]:
        """合格率は単独で返さない。4 値の件数と分母の内訳を必ず併記する。"""
        self._guard()
        c, d, dec = self.counts(), self.denominator(), self.declared_counts()
        out: dict[str, object] = {}
        out.update({f"宣言で{k}": v for k, v in dec.items()})
        out.update(c)
        out.update(d)
        out["合格率_走らせた行のみ"] = _ratio(c[PASSED], d["走らせた数"])
        out["合格率_宣言の行すべて"] = _ratio(c[PASSED], d["宣言の行数"])
        out["分母に含めたもの"] = (
            f"走らせた行のみ = 通った {c[PASSED]} + 落ちた {c[FAILED]} = {d['走らせた数']}"
            f"(走らなかった {c[NOT_RUN]} + テストが無い {c[NO_TESTS]} を除いた分母) / "
            f"宣言の行すべて = {d['宣言の行数']}(走らなかった行とテストが無い行を含む分母)")
        out["在ると数えた数は結果を 1 件も言わない"] = (
            f"宣言では在る {dec['在る']} / 走らせて通った {c[PASSED]}")
        out["必須で通らなかった"] = list(self.not_passed_required())
        return out

    # ---------------------------------------------------------------- 台帳
    def table(self) -> list[dict[str, object]]:
        """判定部分の行。宣言の列と結果の列を必ず並べて出す。"""
        self._guard()
        return [r.judgement() for r in self.results]

    def timing(self) -> list[dict[str, str]]:
        """非決定な値。判定部分に入れず、sha256 の対象にもしない。"""
        self._guard()
        return [r.timing() for r in self.results]

    def judgement_bytes(self) -> bytes:
        self._guard()
        payload = {"宣言の行数": self.report.declared_rows, "行": self.table()}
        return json.dumps(payload, ensure_ascii=False, sort_keys=False,
                          separators=(",", ":")).encode("utf-8") + b"\n"

    def sha256(self) -> str:
        return hashlib.sha256(self.judgement_bytes()).hexdigest()

    def _guard(self) -> None:
        if not self.report.ok:
            raise RuntimeError("止まっているので台帳は無い。report.pending の理由コードを見る")


def _ratio(num: int, den: int) -> str:
    return "分母が 0" if den == 0 else f"{num / den:.4f}"


def _env(allow_network: bool) -> dict[str, str]:
    env = dict(os.environ)
    if allow_network:
        env["CHECK_CENSUS_NETWORK"] = "allowed"
    else:
        env.update(NO_NETWORK_ENV)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _tail_fingerprint(stdout: str, stderr: str) -> str:
    lines = (stdout + stderr).splitlines()
    return hashlib.sha256("\n".join(lines[-TAIL_LINES:]).encode("utf-8")).hexdigest()


def _not_run(row: Row, reason: str) -> Result:
    return Result(name=row.name, declared=row.declared, verdict=NOT_RUN, reason=reason, exit_code=None,
                  tail_sha256="", required=row.required, source=row.source,
                  seconds="", started="", host=platform.node())


def run_row(row: Row, base: Path) -> Result:
    """宣言された argv だけを配列のまま走らせる。推測で runner を組み立てる経路は無い。"""
    if row.declared == "無い":
        return Result(name=row.name, declared=row.declared, verdict=NO_TESTS, reason="", exit_code=None,
                      tail_sha256="", required=row.required, source=row.source,
                      seconds="", started="", host=platform.node())
    if not row.name or not row.path:
        return _not_run(row, "宣言の列が空欄")
    folder = Path(row.path)
    if not folder.is_absolute():
        folder = base / folder
    if not folder.is_dir():
        return _not_run(row, "path が無い")
    if not row.argv:
        return _not_run(row, "runner が無い")
    started = datetime.datetime.now()
    try:
        done = subprocess.run(list(row.argv), cwd=str(folder), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=row.timeout,
                              env=_env(row.allow_network), shell=False)
    except subprocess.TimeoutExpired:
        return _not_run(row, "timeout")
    except OSError:
        return _not_run(row, "runner が無い")
    seconds = f"{(datetime.datetime.now() - started).total_seconds():.3f}"
    return Result(name=row.name, declared=row.declared,
                  verdict=PASSED if done.returncode == 0 else FAILED, reason="",
                  exit_code=done.returncode,
                  tail_sha256=_tail_fingerprint(done.stdout or "", done.stderr or ""),
                  required=row.required, source=row.source,
                  seconds=seconds, started=started.isoformat(timespec="seconds"), host=platform.node())


def census(decl: Declaration) -> Census:
    """宣言表を検査し、通れば宣言された runner を順に走らせる。止まったら 1 行も走らせない。"""
    if decl.pending:
        return Census(Report(False, decl.pending, len(decl.rows)), ())
    return Census(Report(True, (), len(decl.rows)), tuple(run_row(r, decl.base) for r in decl.rows))


def verify(decl: Declaration) -> dict[str, object]:
    """2 回走らせて判定部分の sha256 を突き合わせる。一致しなければ観測としてそのまま返す。"""
    first = census(decl)
    if not first.report.ok:
        return {"ok": False, "stage": "宣言表", "pending": [p.as_dict() for p in first.report.pending]}
    second = census(decl)
    same = first.sha256() == second.sha256()
    out: dict[str, object] = {"ok": same, "一致": same, "判定した回数": 2,
                              "sha256": first.sha256(), "2 回目の sha256": second.sha256()}
    if not same:
        diffs = []
        for a, b in zip(first.table(), second.table()):
            differed = {k: [a[k], b[k]] for k in JUDGEMENT_KEYS if a[k] != b[k]}
            if differed:
                diffs.append({"name": a["name"], "違った欄": differed})
        out["観測"] = "走らせた対象が同じ入力に同じ結果を返していない(平均も多数決もしない)"
        out["不一致の内訳"] = diffs
        out["pending"] = [Pending(STOP_REASONS[5], f"不一致の行 {len(diffs)} 件").as_dict()]
    return out


TEMPLATE = [
    list(DECL_COLUMNS),
    ["道具A", "../道具A", "在る", json.dumps(["python", "-m", "pytest", "-q"], ensure_ascii=False),
     "120", YES, "", "棚卸しの記録(ここに出典を書く)"],
    ["道具B", "../道具B", "無い", "", "120", NO, "", "棚卸しの記録(ここに出典を書く)"],
]


def init(path: str | Path) -> Path:
    p = Path(path)
    with p.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(TEMPLATE)
    return p


def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1))


def build_parser() -> argparse.ArgumentParser:
    """CLI は census / verify / init の 3 つで、option は -h 以外に 1 つも無い。"""
    ap = argparse.ArgumentParser(prog="check_census", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("census", "verify", "init"):
        sub.add_parser(name).add_argument("decl")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == "init":
        print(f"書いた: {init(a.decl)}")
        return 0
    try:
        decl = Declaration.load(a.decl)
    except DeclError as e:
        print(f"宣言表として読めない: {e}", file=sys.stderr)
        return 2
    if a.cmd == "verify":
        out = verify(decl)
        _print(out)
        return 0 if out["ok"] else 3
    c = census(decl)
    if not c.report.ok:
        _print({"ok": False, "stage": "宣言表", "宣言の行数": c.report.declared_rows,
                "pending": [p.as_dict() for p in c.report.pending]})
        return 3
    _print({"ok": True, "stage": "台帳にした", **c.rate(), "行": c.table(), "測った条件": c.timing()})
    return 3 if c.not_passed_required() else 0


if __name__ == "__main__":
    raise SystemExit(main())
