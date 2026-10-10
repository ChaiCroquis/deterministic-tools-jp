"""scope_ledger — 文章で書いた「しないこと」を、対象のソースを走らせずに構文として読んで突き合わせる台帳。

記事や README の「できないこと」の節には、**その引数が無い / その経路が無い** と書いてある。
それは宣言であって、宣言は文章だ。**文章は読み手の側では確かめられない。** この部品は、宣言のうち
機械で見られる形のものだけを、名指しされた経路が対象のソースに静的に現れるかで突き合わせ、
宣言どおり / 一致しない / 宣言が無い / 機械では読めない の 4 値を、分母の内訳つきで台帳に残す。

持たせていないものが規律になっている。

  - **対象を実行しない。import もしない**(読むのは構文木だけ。走らせる側は check_census)
  - **ネットワークを持たない**(取りに行く経路が無い。読むのは宣言表と、名指しされたソースだけ)
  - **宣言の文から種類を推測しない**(種類の欄が空なら「機械では読めない」に落ちる。自然文を
    解釈して判定する経路が無い)
  - **一致しない行をそれ以上の言葉にしない**(嘘・違反・不正と書く経路が無い。理由も推定しない。
    出すのは宣言の verbatim と現れた行番号だけ)
  - **遵守率を単独で返さない**(4 値の件数と分母の内訳を必ず併記する)
  - **ソースも宣言表も書き換えない**(直す・生成する・宣言を書き戻す経路が無い)
  - **出典の欄が空の行は判定せずに止まる**(誰の宣言かを辿れない行を台帳に入れない)
  - **追えない形を黙って「宣言どおり」にしない**(別名での取り込み・再公開・動的な属性参照は
    追わず、「機械では読めない」に落とす。見えなかったことを守られていることの代わりにしない)

入力は宣言表 1 つだけ。

    tool          道具名
    line          線の名前(「外向きの通信を持たない」など)
    declaration   宣言の verbatim。**空欄はこの線について宣言が無いことを意味する**
    source        その宣言の出典(ファイル名 + 行番号)。空欄は止まる
    kind          機械判定の種類。import / call / kwarg / option / write の 5 種か空欄
    target        名指しの対象(モジュール名 / 呼び出しの名前 / shell=True / resolve:fallback など)
    path          対象ソースのパス(宣言表のある場所からの相対、または絶対)

判定したことは「名指しされた経路が静的に現れないか」までで、道具が宣言どおり振る舞うことも、
宣言が十分かも、書かれていない線の良し悪しも判定しない。標準ライブラリのみ(ast / csv / json /
hashlib / pathlib / datetime / platform / argparse)。
"""
from __future__ import annotations

import argparse
import ast
import csv
import datetime
import hashlib
import json
import platform
import sys
from dataclasses import dataclass
from pathlib import Path

# 宣言表の列(全部必要)
DECL_COLUMNS = ("tool", "line", "declaration", "source", "kind", "target", "path")

# 機械判定の種類は 5 種だけ。宣言の文から推測する経路は無い
KINDS = ("import", "call", "kwarg", "option", "write")

AS_DECLARED, MISMATCH, NO_DECLARATION, UNREADABLE = "宣言どおり", "一致しない", "宣言が無い", "機械では読めない"
VERDICTS = (AS_DECLARED, MISMATCH, NO_DECLARATION, UNREADABLE)

# 「機械では読めない」に付く理由コード(4 個)。他の 3 値には付かない
UNREADABLE_REASONS = ("種類の欄が無い", "対象が Python でない", "構文解析できない",
                      "名前が動的に組み立てられている")

# 止まる理由コード(6 個)。止まったときは 1 行も判定しない
STOP_REASONS = ("出典の欄が空", "対象ソースのパスが無い", "機械判定の種類が 5 種の外",
                "名指しの対象の欄が空", "同じ道具名と線の名前の行が 2 件以上",
                "2 回目の判定部分がバイト列として不一致")

# 書き込みと見なす open のモード文字
WRITE_MODE_CHARS = "wax+"
# 取り込みの名前を動的に組み立てる呼び出し
DYNAMIC_IMPORT_CALLS = ("import_module", "__import__")

# 台帳の判定部分に入る欄(この順で固定)。パスの絶対部分・時刻・ホスト名は入れない
JUDGEMENT_KEYS = ("道具名", "線の名前", "判定", "理由コード", "現れた行", "宣言", "出典")
# 判定部分から外す欄
READ_KEYS = ("道具名", "線の名前", "種類", "名指しの対象", "読んだ絶対パス", "読んだ時刻", "ホスト名")


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
    tool: str
    line: str
    declaration: str
    source: str
    kind: str
    target: str
    path: str
    number: int          # 宣言表の行番号(止まる理由の detail に使う)


@dataclass(frozen=True)
class Result:
    tool: str
    line: str
    verdict: str
    reason: str                   # 「機械では読めない」の理由コード(他は空)
    hits: tuple[int, ...]         # 名指しの経路が現れた行番号(「一致しない」以外は空)
    declaration: str
    source: str
    kind: str
    target: str
    abs_path: str                 # 判定部分に入れない
    read_at: str                  # 判定部分に入れない
    host: str                     # 判定部分に入れない

    def judgement(self) -> dict[str, object]:
        return {"道具名": self.tool, "線の名前": self.line, "判定": self.verdict,
                "理由コード": self.reason, "現れた行": list(self.hits),
                "宣言": self.declaration, "出典": self.source}

    def read_condition(self) -> dict[str, str]:
        return {"道具名": self.tool, "線の名前": self.line, "種類": self.kind,
                "名指しの対象": self.target, "読んだ絶対パス": self.abs_path,
                "読んだ時刻": self.read_at, "ホスト名": self.host}


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
        reader = csv.DictReader(p.read_text(encoding="utf-8-sig").splitlines())
        header = tuple(reader.fieldnames or ())
        missing = [c for c in DECL_COLUMNS if c not in header]
        if missing:
            raise DeclError("宣言表に " + " / ".join(missing) + " の列が無い")
        base = p.resolve().parent
        rows: list[Row] = []
        pending: list[Pending] = []
        seen: dict[tuple[str, str], int] = {}
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in DECL_COLUMNS}
            if not cell["tool"] or not cell["line"]:
                raise DeclError(f"行 {i}: tool と line は空欄にできない")
            where = f"行 {i}({cell['tool']} / {cell['line']})"
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0], where))
            if cell["kind"]:
                if cell["kind"] not in KINDS:
                    pending.append(Pending(STOP_REASONS[2], where + "の種類: " + cell["kind"]))
                if not cell["target"]:
                    pending.append(Pending(STOP_REASONS[3], where))
                if not cell["path"] or not (base / cell["path"]).exists():
                    pending.append(Pending(STOP_REASONS[1], where + "のパス: " + (cell["path"] or "空欄")))
            key = (cell["tool"], cell["line"])
            if key in seen:
                pending.append(Pending(STOP_REASONS[4],
                                       f"{cell['tool']} / {cell['line']}: 行 {seen[key]} と行 {i}"))
            else:
                seen[key] = i
            rows.append(Row(number=i, **cell))
        return cls(rows=tuple(rows), base=base, pending=tuple(pending))


# ------------------------------------------------------------------ 構文だけを読む

def read_source(path: Path) -> str:
    """対象ソースを **文字列として** 読む。import もしないし、実行もしない。"""
    return path.read_text(encoding="utf-8-sig")


def _call_name(node: ast.Call) -> str | None:
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return None


def _str_const(node: ast.expr | None) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _dynamic_attribute_lines(tree: ast.AST) -> list[int]:
    """名前を動的に組み立てる形(getattr に literal でない名前を渡す)の行。"""
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and _call_name(n) == "getattr" and len(n.args) >= 2:
            if _str_const(n.args[1]) is None:
                out.append(n.lineno)
    return out


def scan_import(tree: ast.AST, target: str) -> tuple[list[int], list[int]]:
    """名指しのモジュールを取り込んでいるか。別名での再公開は追わない。"""
    hits: list[int] = []
    dyn: list[int] = []
    top = target.split(".")[0]
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            if any(a.name.split(".")[0] == top for a in n.names):
                hits.append(n.lineno)
        elif isinstance(n, ast.ImportFrom):
            if n.level == 0 and n.module and n.module.split(".")[0] == top:
                hits.append(n.lineno)
        elif isinstance(n, ast.Call) and _call_name(n) in DYNAMIC_IMPORT_CALLS:
            name = _str_const(n.args[0]) if n.args else None
            if name is None:
                dyn.append(n.lineno)
            elif name.split(".")[0] == top:
                hits.append(n.lineno)
    return hits, dyn


def scan_call(tree: ast.AST, target: str) -> tuple[list[int], list[int]]:
    """名指しの呼び出しが現れるか。属性名を動的に引く形は追えないので別に数える。"""
    hits = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Call) and _call_name(n) == target]
    return hits, _dynamic_attribute_lines(tree)


def scan_write(tree: ast.AST, target: str) -> tuple[list[int], list[int]]:
    """名指しの書き込み経路。open はモードの literal に w / a / x / + を含む呼び出しだけ数える。"""
    if target != "open":
        return scan_call(tree, target)
    hits: list[int] = []
    dyn = _dynamic_attribute_lines(tree)
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and _call_name(n) == "open"):
            continue
        mode: ast.expr | None = n.args[1] if len(n.args) >= 2 else None
        for kw in n.keywords:
            if kw.arg == "mode":
                mode = kw.value
        if mode is None:
            continue                                   # 第 2 引数が無い = 既定の読み取り
        text = _str_const(mode)
        if text is None:
            dyn.append(n.lineno)                       # モードが変数 = 読み取りか書き込みか見えない
        elif any(c in WRITE_MODE_CHARS for c in text):
            hits.append(n.lineno)
    return hits, dyn


def scan_kwarg(tree: ast.AST, target: str) -> tuple[list[int], list[int]]:
    """shell のような名前、または shell=True のように値まで名指しされたキーワード引数。"""
    name, _, want = target.partition("=")
    name, want = name.strip(), want.strip()
    hits: list[int] = []
    dyn: list[int] = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        for kw in n.keywords:
            if kw.arg is None:
                dyn.append(n.lineno)                   # 辞書展開(**)の中身は構文では見えない
            elif kw.arg == name:
                if not want:
                    hits.append(n.lineno)
                elif isinstance(kw.value, ast.Constant):
                    if repr(kw.value.value) == want or str(kw.value.value) == want:
                        hits.append(n.lineno)
                else:
                    dyn.append(n.lineno)
    return hits, dyn


def _arg_names(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[list[str], bool]:
    a = fn.args
    names = [x.arg for x in (*a.posonlyargs, *a.args, *a.kwonlyargs)]
    if a.vararg:
        names.append(a.vararg.arg)
    if a.kwarg:
        names.append(a.kwarg.arg)
    return names, a.kwarg is not None


def scan_option(tree: ast.AST, target: str) -> tuple[list[int], list[int]]:
    """引数定義に名指しの文字列が現れるか。関数名:引数名 ならその関数の定義だけを見る。"""
    scope, _, arg_name = target.rpartition(":")
    hits: list[int] = []
    dyn: list[int] = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if scope and n.name != scope:
                continue
            names, has_kwargs = _arg_names(n)
            if arg_name in names:
                hits.append(n.lineno)
            elif has_kwargs:
                dyn.append(n.lineno)                   # **kwargs が受け取る名前は構文では見えない
        elif not scope and isinstance(n, ast.Call) and _call_name(n) == "add_argument":
            for a in n.args:
                text = _str_const(a)
                if text is None:
                    dyn.append(n.lineno)
                elif text.lstrip("-").replace("-", "_") == arg_name:
                    hits.append(n.lineno)
    return hits, dyn


SCANNERS = {"import": scan_import, "call": scan_call, "kwarg": scan_kwarg,
            "option": scan_option, "write": scan_write}


# ------------------------------------------------------------------ 1 行の判定

def judge(row: Row, base: Path) -> Result:
    """宣言 1 行を 4 値のどれかに入れる。対象は実行も import もしない。"""
    def made(verdict: str, reason: str = "", hits: tuple[int, ...] = (), abs_path: str = "") -> Result:
        return Result(tool=row.tool, line=row.line, verdict=verdict, reason=reason, hits=hits,
                      declaration=row.declaration, source=row.source, kind=row.kind, target=row.target,
                      abs_path=abs_path, read_at=datetime.datetime.now().isoformat(timespec="seconds"),
                      host=platform.node())

    if not row.declaration:
        return made(NO_DECLARATION)
    if not row.kind:
        return made(UNREADABLE, UNREADABLE_REASONS[0])
    path = Path(row.path)
    if not path.is_absolute():
        path = base / path
    if path.suffix != ".py":
        return made(UNREADABLE, UNREADABLE_REASONS[1], abs_path=str(path))
    try:
        tree = ast.parse(read_source(path))
    except (SyntaxError, ValueError):
        return made(UNREADABLE, UNREADABLE_REASONS[2], abs_path=str(path))
    hits, dyn = SCANNERS[row.kind](tree, row.target)
    if hits:
        return made(MISMATCH, hits=tuple(sorted(set(hits))), abs_path=str(path))
    if dyn:
        return made(UNREADABLE, UNREADABLE_REASONS[3], abs_path=str(path))
    return made(AS_DECLARED, abs_path=str(path))


# ------------------------------------------------------------------ 台帳

@dataclass
class Ledger:
    report: Report
    results: tuple[Result, ...]

    def counts(self) -> dict[str, int]:
        return {v: sum(1 for r in self.results if r.verdict == v) for v in VERDICTS}

    def denominator(self) -> dict[str, int]:
        c = self.counts()
        return {"宣言表の行数": self.report.declared_rows,
                "機械で読めた数": c[AS_DECLARED] + c[MISMATCH],
                "機械では読めなかった数": c[UNREADABLE],
                "宣言が無い数": c[NO_DECLARATION]}

    def unreadable_reasons(self) -> dict[str, int]:
        return {r: sum(1 for x in self.results if x.verdict == UNREADABLE and x.reason == r)
                for r in UNREADABLE_REASONS}

    def mismatched(self) -> tuple[str, ...]:
        return tuple(f"{r.tool} / {r.line}" for r in self.results if r.verdict == MISMATCH)

    def rate(self) -> dict[str, object]:
        """遵守率は単独で返さない。4 値の件数と分母の内訳を必ず併記する。"""
        self._guard()
        c, d = self.counts(), self.denominator()
        out: dict[str, object] = dict(c)
        out.update(d)
        out["遵守率_機械で読めた行のみ"] = _ratio(c[AS_DECLARED], d["機械で読めた数"])
        out["遵守率_宣言表の行すべて"] = _ratio(c[AS_DECLARED], d["宣言表の行数"])
        out["分母に含めたもの"] = (
            f"機械で読めた行のみ = 宣言どおり {c[AS_DECLARED]} + 一致しない {c[MISMATCH]} = {d['機械で読めた数']}"
            f"(機械では読めない {c[UNREADABLE]} + 宣言が無い {c[NO_DECLARATION]} を除いた分母) / "
            f"宣言表の行すべて = {d['宣言表の行数']}(読めなかった行と宣言が無い行を含む分母)")
        out["機械では読めない行を宣言どおりに寄せていない"] = (
            f"読めなかった {c[UNREADABLE]} 件は別の箱のまま(内訳 "
            + " / ".join(f"{k} {v}" for k, v in self.unreadable_reasons().items()) + ")")
        out["一致しない行"] = list(self.mismatched())
        return out

    def table(self) -> list[dict[str, object]]:
        """判定部分の行。宣言の verbatim と出典を全ての行に残す。"""
        self._guard()
        return [r.judgement() for r in self.results]

    def read_conditions(self) -> list[dict[str, str]]:
        """判定部分に入れない欄(絶対パス・時刻・ホスト名)。sha256 の対象にもしない。"""
        self._guard()
        return [r.read_condition() for r in self.results]

    def judgement_bytes(self) -> bytes:
        self._guard()
        payload = {"宣言表の行数": self.report.declared_rows, "行": self.table()}
        return json.dumps(payload, ensure_ascii=False, sort_keys=False,
                          separators=(",", ":")).encode("utf-8") + b"\n"

    def sha256(self) -> str:
        return hashlib.sha256(self.judgement_bytes()).hexdigest()

    def _guard(self) -> None:
        if not self.report.ok:
            raise RuntimeError("止まっているので台帳は無い。report.pending の理由コードを見る")


def _ratio(num: int, den: int) -> str:
    return "分母が 0" if den == 0 else f"{num / den:.4f}"


def ledger(decl: Declaration) -> Ledger:
    """宣言表を検査し、通れば 1 行ずつ構文として突き合わせる。止まったら 1 行も判定しない。"""
    if decl.pending:
        return Ledger(Report(False, decl.pending, len(decl.rows)), ())
    return Ledger(Report(True, (), len(decl.rows)), tuple(judge(r, decl.base) for r in decl.rows))


def verify(decl: Declaration) -> dict[str, object]:
    """2 回判定して判定部分の sha256 を突き合わせる。一致しなければ観測としてそのまま返す。"""
    first = ledger(decl)
    if not first.report.ok:
        return {"ok": False, "stage": "宣言表", "pending": [p.as_dict() for p in first.report.pending]}
    second = ledger(decl)
    same = first.sha256() == second.sha256()
    out: dict[str, object] = {"ok": same, "一致": same, "判定した回数": 2,
                              "sha256": first.sha256(), "2 回目の sha256": second.sha256()}
    if not same:
        diffs = []
        for a, b in zip(first.table(), second.table()):
            differed = {k: [a[k], b[k]] for k in JUDGEMENT_KEYS if a[k] != b[k]}
            if differed:
                diffs.append({"道具名": a["道具名"], "線の名前": a["線の名前"], "違った欄": differed})
        out["観測"] = "同じ宣言表から 2 回判定して違う答えが出た(平均も多数決もしない)"
        out["不一致の内訳"] = diffs
        out["pending"] = [Pending(STOP_REASONS[5], f"不一致の行 {len(diffs)} 件").as_dict()]
    return out


TEMPLATE = [
    list(DECL_COLUMNS),
    ["道具A", "外向きの通信を持たない", "ネットワークを持たない(取りに行く経路が無い)",
     "道具A/README.md L19", "import", "urllib", "../道具A/道具A.py"],
    ["道具A", "書き込まない", "書き出しを持たない(ファイルはこの部品からは開かない)",
     "道具A/README.md L21", "write", "open", "../道具A/道具A.py"],
    ["道具B", "値を直さない", "値そのものは直さない(ここは文章だけの宣言)",
     "道具B/README.md L30", "", "", ""],
    ["道具B", "外向きの通信を持たない", "",
     "道具B/README.md の できないこと 節を見た(この線の宣言は無い)", "", "", ""],
]


def init(path: str | Path) -> Path:
    p = Path(path)
    with p.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(TEMPLATE)
    return p


def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1))


def build_parser() -> argparse.ArgumentParser:
    """CLI は ledger / verify / init の 3 つで、option は -h 以外に 1 つも無い。"""
    ap = argparse.ArgumentParser(prog="scope_ledger", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("ledger", "verify", "init"):
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
    lg = ledger(decl)
    if not lg.report.ok:
        _print({"ok": False, "stage": "宣言表", "宣言表の行数": lg.report.declared_rows,
                "pending": [p.as_dict() for p in lg.report.pending]})
        return 3
    _print({"ok": True, "stage": "台帳にした", **lg.rate(), "行": lg.table(),
            "読んだ条件": lg.read_conditions()})
    return 3 if lg.mismatched() else 0


if __name__ == "__main__":
    raise SystemExit(main())
