"""recalc_scope — 数表を差し替えた後に出し直す対象を出す。再計算はしない、範囲を出すだけ。

**数表を差し替えた後、過去に出した結果のどれを出し直すかは「最終実行の日付」では決まらない。
結果の側に「引いた版の指紋」と「引いた行のキー」を残していないと、全部出し直すか何も出し
直さないかの二択になる。** この部品は、結果の台帳・版の台帳・版間の差分の台帳の 3 枚から、
結果 1 行ごとに 4 値(**影響あり / 影響なし / 決まらない / 止まった**)を付ける。決まらない
ものは理由別(見本だけ / キー無し / 鎖が切れている)に分けて数え、分母(結果台帳の行数)と
内訳を併記して返す。

持たせていないものが規律になっている。

  - **版は指紋で指し、日付で指さない**(同じ内容に戻った版があるので日付順では一意に
    ならない。日付の列は表示にだけ使い、突き合わせには入れない)
  - **差分台帳が「見本だけ」と宣言している区間は「決まらない」に落ちる**(見本から全件を
    推定しない)
  - **結果の行に引いたキーが無ければ「決まらない」**(キーが空の結果を「影響なし」に寄せない)
  - **指紋が空の版(検証に落ちた回)は版として使わずに止まる**
  - **版の鎖が辿れない区間は「決まらない」**(区間の差分が台帳に無いとき、間を推定で繋がない)
  - **再計算しない**(値を計算し直す経路も、他の道具を呼ぶ経路も持たない)
  - **出し直すべきだと勧めない / 優先順位も付けない**(返すのは件数と内訳だけ)
  - **影響の判定は「結果が引いたキー ∩ 区間で変わったキー ≠ 空」までで、値がどう変わるかは
    判定しない**
  - **件数は理由別に分母(結果台帳の行数)と内訳つきで出す**(率を単独で返さない)
  - **4 つを混ぜない**(影響あり / 影響なし / 決まらない / 止まった)
  - **入力表を書き換えず、キーも指紋も生成しない**
  - **出典の欄が空の行は使わずに止まる**
  - **float を使わない**(件数は整数、値は 1 つも持たない)
  - **同じ入力には同じバイト列**(判定部分に時刻・絶対パス・ホスト名・日付を入れない)

入力は 3 つ。結果の台帳(CSV)、版の台帳(CSV)、版間の差分の台帳(CSV)。

結果の台帳の列は 8 つ。

    result_id   結果 id(空欄は「表として読めない」。2 行あると止まる)
    target      対象(空欄は「表として読めない」)
    item        項目(空欄は「表として読めない」)
    version     引いた版の指紋。空欄は止まる。版台帳に無い指紋も止まる
    keys        引いた行のキー(縦棒で区切る。0 件以上。空欄なら決まらない)
    issued      出した日(表示だけに使う。判定部分には入れない)
    source      出典。空欄は止まる
    swap        入れ替え方(verify が行順を入れ替えるときの宣言。全行で同じ値)

版の台帳の列は 4 つ。

    version     版の指紋(空欄は「表として読めない」)
    date        版の日付(表示だけに使う。判定部分にも鎖の辿り方にも入れない)
    parent      前の版の指紋(空欄 = 鎖の始まり。台帳に無い指紋でもよい)
    source      出典。空欄は止まる

版間の差分の台帳の列は 6 つ。1 区間 × 1 変更種別で 1 行。

    from_version  前の版の指紋
    to_version    後の版の指紋
    keys          変わった行のキー(縦棒で区切る。0 件でもよい)
    change        変更種別。登録の 3 種(追加 / 削除 / 変更)。外は止まる
    coverage      キーの一覧が全件か見本だけかの宣言。空欄は止まる
    source        出典。空欄は止まる

使い方:

    python recalc_scope.py init ひな型/
    python recalc_scope.py check  結果の台帳.csv 版の台帳.csv 差分の台帳.csv
    python recalc_scope.py scope  結果の台帳.csv 版の台帳.csv 差分の台帳.csv
    python recalc_scope.py verify 結果の台帳.csv 版の台帳.csv 差分の台帳.csv
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import platform
import sys
from dataclasses import dataclass
from pathlib import Path

KEKKA_COLUMNS = ("result_id", "target", "item", "version", "keys", "issued",
                 "source", "swap")
HAN_COLUMNS = ("version", "date", "parent", "source")
SABUN_COLUMNS = ("from_version", "to_version", "keys", "change", "coverage", "source")

# 登録の語彙
CHANGES = ("追加", "削除", "変更")
COVERAGES = ("全件", "見本だけ")
SWAPS = ("逆順", "両端入れ替え", "1 つずらす")
KEY_SEP = "|"

# 結果ごとの 4 値。4 つを混ぜない
RESULTS = ("影響あり", "影響なし", "決まらない", "止まった")

# 決まらない理由(3 種。影響あり / 影響なし とは別の欄で数える)
UNDECIDED = ("見本だけ", "キー無し", "鎖が切れている")

# 止まる理由コード(9 個)
STOP_REASONS = ("出典の欄が空", "版の指紋が版台帳に無い", "指紋が空の版を参照",
                "同じ指紋に別の日付が 2 つ", "全件か見本かの宣言が空",
                "変更種別が宣言外", "件数の合計が合わない",
                "2 回目の判定部分が不一致", "行順を入れ替えた表で出力が変わる")

# CLI の下位コマンド。この 4 つだけで、option は -h 以外に 1 つも無い
SUBCOMMANDS = ("scope", "check", "verify", "init")

# 判定部分に入れない欄(sha256 の対象にもしない)
SCOPE_KEYS = ("読んだ結果の台帳の絶対パス", "読んだ版の台帳の絶対パス",
              "読んだ差分の台帳の絶対パス", "読んだ時刻", "ホスト名")


class ReadError(Exception):
    """表として読めない(理由コードにせず終了コード 2 で返す = 表を書く側の話)。"""


def split_keys(text: str, where: str) -> tuple[str, ...]:
    """縦棒で区切ったキーの一覧。順は入力に依らせない(並べ替えて持つ)。"""
    keys = tuple(k.strip() for k in text.split(KEY_SEP) if k.strip())
    if len(set(keys)) != len(keys):
        raise ReadError(f"{where}: キーの一覧に同じキーが 2 つある")
    return tuple(sorted(keys))


@dataclass(frozen=True)
class Pending:
    reason: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"reason": self.reason, "detail": self.detail}


# ------------------------------------------------------------ 版の台帳

@dataclass(frozen=True)
class Version:
    version: str
    date: str
    parent: str
    source: str
    number: int


@dataclass(frozen=True)
class Versions:
    items: tuple[Version, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Versions":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"版の台帳が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Versions":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in HAN_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("版の台帳に " + " / ".join(lack) + " の列が無い")
        items: list[Version] = []
        pending: list[Pending] = []
        seen: dict[str, Version] = {}
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in HAN_COLUMNS}
            where = f"版の台帳 行 {i}"
            if not cell["version"]:
                raise ReadError(f"{where}: 版の指紋が空欄")
            if not cell["date"]:
                raise ReadError(f"{where}: 版の日付が空欄({cell['version'][:8]})")
            if cell["parent"] == cell["version"]:
                raise ReadError(f"{where}: 前の版が自分と同じ指紋({cell['version'][:8]})")
            old = seen.get(cell["version"])
            if old is not None:
                if old.date != cell["date"]:
                    # 同じ内容の版に 2 つの日付。日付で版を指せないことがここで出る
                    pending.append(Pending(
                        STOP_REASONS[3],
                        f"{cell['version'][:8]}: {old.date} と {cell['date']}"))
                else:
                    raise ReadError(f"{where}: 版 {cell['version'][:8]} の宣言が 2 行ある")
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0],
                                       f"{where}({cell['version'][:8]})"))
            v = Version(version=cell["version"], date=cell["date"],
                        parent=cell["parent"], source=cell["source"], number=i)
            seen.setdefault(cell["version"], v)
            items.append(v)
        if not items:
            raise ReadError("版の台帳に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    def of(self, version: str) -> Version | None:
        return next((v for v in self.items if v.version == version), None)


@dataclass(frozen=True)
class Chain:
    """版の鎖(古い → 新しい)。日付では並べず、前の版の指紋だけで辿る。"""
    order: tuple[str, ...]

    @property
    def newest(self) -> str:
        return self.order[-1]

    def index(self, version: str) -> int | None:
        return self.order.index(version) if version in self.order else None

    def steps(self, version: str) -> tuple[tuple[str, str], ...]:
        """その版から新しい版までの区間(前の版 → 後の版 の組)。"""
        i = self.index(version)
        if i is None:
            return ()
        return tuple((self.order[k], self.order[k + 1])
                     for k in range(i, len(self.order) - 1))


def chain_of(versions: Versions) -> Chain:
    """指紋の親子関係だけで鎖を組む(日付は見ない)。1 本に決まらなければ読めない表。"""
    known = {v.version: v for v in versions.items}
    used = {v.parent for v in versions.items if v.parent in known}
    heads = sorted(v for v in known if v not in used)
    if len(heads) != 1:
        raise ReadError(
            "新しい版が 1 つに決まらない(鎖の先頭が "
            f"{len(heads)} 個: {' / '.join(h[:8] for h in heads) or 'なし'})。"
            "日付では決めない")
    walked: list[str] = []
    seen: set[str] = set()
    cur = heads[0]
    while True:
        if cur in seen:                       # 輪になっていたら辿り切れない
            raise ReadError(f"前の版の指紋が輪になっている({cur[:8]})")
        seen.add(cur)
        walked.append(cur)
        nxt = known[cur].parent
        if nxt not in known:
            break
        cur = nxt
    if len(walked) != len(known):
        rest = sorted(set(known) - set(walked))
        raise ReadError("鎖から外れた版がある(推定で繋がない): "
                        + " / ".join(r[:8] for r in rest))
    return Chain(order=tuple(reversed(walked)))


# ------------------------------------------------------------ 差分の台帳

@dataclass(frozen=True)
class Diff:
    from_version: str
    to_version: str
    keys: tuple[str, ...]
    change: str
    coverage: str
    source: str
    number: int

    @property
    def sampled(self) -> bool:
        return self.coverage == COVERAGES[1]


@dataclass(frozen=True)
class Diffs:
    items: tuple[Diff, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Diffs":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"差分の台帳が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Diffs":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in SABUN_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("差分の台帳に " + " / ".join(lack) + " の列が無い")
        items: list[Diff] = []
        pending: list[Pending] = []
        seen: set[tuple[str, str, str]] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in SABUN_COLUMNS}
            where = f"差分の台帳 行 {i}"
            if not cell["from_version"]:
                raise ReadError(f"{where}: 前の版の指紋が空欄")
            if not cell["to_version"]:
                raise ReadError(f"{where}: 後の版の指紋が空欄")
            if cell["from_version"] == cell["to_version"]:
                raise ReadError(f"{where}: 前の版と後の版が同じ指紋")
            span = f"{cell['from_version'][:8]} → {cell['to_version'][:8]}"
            key = (cell["from_version"], cell["to_version"], cell["change"])
            if key in seen:
                raise ReadError(f"{where}: {span} の {cell['change']} の宣言が 2 行ある")
            seen.add(key)
            if cell["change"] not in CHANGES:
                pending.append(Pending(STOP_REASONS[5],
                                       f"{where}({span}): {cell['change'] or '空欄'}"))
            if not cell["coverage"]:
                pending.append(Pending(STOP_REASONS[4], f"{where}({span})"))
            elif cell["coverage"] not in COVERAGES:
                raise ReadError(f"{where}: 全件か見本かの宣言は "
                                f"{' / '.join(COVERAGES)}({cell['coverage']})")
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0], f"{where}({span})"))
            items.append(Diff(from_version=cell["from_version"],
                              to_version=cell["to_version"],
                              keys=split_keys(cell["keys"], f"{where} のキー"),
                              change=cell["change"], coverage=cell["coverage"],
                              source=cell["source"], number=i))
        if not items:
            raise ReadError("差分の台帳に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    def of_step(self, step: tuple[str, str]) -> tuple[Diff, ...]:
        return tuple(d for d in self.items
                     if (d.from_version, d.to_version) == step)


# ------------------------------------------------------------ 結果の台帳

@dataclass(frozen=True)
class Result:
    result_id: str
    target: str
    item: str
    version: str
    keys: tuple[str, ...]
    issued: str
    source: str
    number: int


@dataclass(frozen=True)
class Ledger:
    items: tuple[Result, ...]
    swap: str
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Ledger":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"結果の台帳が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Ledger":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in KEKKA_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("結果の台帳に " + " / ".join(lack) + " の列が無い")
        items: list[Result] = []
        pending: list[Pending] = []
        swaps: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in KEKKA_COLUMNS}
            where = f"結果の台帳 行 {i}"
            if not cell["result_id"]:
                raise ReadError(f"{where}: 結果 id が空欄")
            if not cell["target"]:
                raise ReadError(f"{where}: 対象が空欄({cell['result_id']})")
            if not cell["item"]:
                raise ReadError(f"{where}: 項目が空欄({cell['result_id']})")
            if not cell["issued"]:
                raise ReadError(f"{where}: 出した日が空欄({cell['result_id']})")
            if cell["swap"]:
                if cell["swap"] not in SWAPS:
                    raise ReadError(f"{where}: 入れ替え方 {cell['swap']} は登録の外"
                                    f"({' / '.join(SWAPS)})")
                swaps.add(cell["swap"])
            where_row = f"{where}({cell['result_id']})"
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0], where_row))
            if not cell["version"]:
                # 検証に落ちた回は指紋が無い。版として指せないので止まる
                pending.append(Pending(STOP_REASONS[2], where_row))
            items.append(Result(result_id=cell["result_id"], target=cell["target"],
                                item=cell["item"], version=cell["version"],
                                keys=split_keys(cell["keys"], f"{where} のキー"),
                                issued=cell["issued"], source=cell["source"],
                                number=i))
        if not items:
            raise ReadError("結果の台帳に行が無い(ヘッダだけ)")
        if len(swaps) > 1:
            raise ReadError("入れ替え方の宣言が 2 通り以上ある: " + " / ".join(sorted(swaps)))
        return cls(items=tuple(items), swap=next(iter(swaps), ""),
                   pending=tuple(pending), path=path)

    @property
    def ordered(self) -> tuple[Result, ...]:
        """結果 id の順に並べ替えて返す(表の行順には依らせない)。"""
        return tuple(sorted(self.items, key=lambda r: r.result_id))

    def swapped(self, how: str) -> "Ledger":
        """宣言された入れ替え方で行順だけを入れ替える(乱数の既定は持たない)。"""
        if how not in SWAPS:
            raise ReadError(f"入れ替え方が登録の外: {how}")
        rows = list(self.items)
        if len(rows) >= 2:
            if how == SWAPS[0]:
                rows.reverse()
            elif how == SWAPS[1]:
                rows[0], rows[-1] = rows[-1], rows[0]
            else:
                rows = rows[1:] + rows[:1]
        return Ledger(items=tuple(rows), swap=self.swap, pending=self.pending,
                      path=self.path)


# ------------------------------------------------------------ 範囲を出す

@dataclass(frozen=True)
class Scope:
    """結果 1 行の読み。値は 1 つも持たず、出し直すべきだとも言わない。"""
    row: Result
    result: str
    why: str = ""                  # 決まらないときだけ、3 種のどれか
    steps: int = 0                 # 引いた版から新しい版までの区間の段数
    hit: tuple[str, ...] = ()      # 引いたキー ∩ 区間で変わったキー
    compared: int = 0              # 突き合わせた区間のキーの件数


@dataclass(frozen=True)
class Report:
    ok: bool
    pending: tuple[Pending, ...]
    rows: int
    versions: int
    diffs: int


@dataclass(frozen=True)
class Table:
    report: Report
    scopes: tuple[Scope, ...]
    chain: Chain | None
    ledger: Ledger
    versions: Versions
    diffs: Diffs
    read_at: str
    host: str

    # -------------------------------------------------- 4 値と分母
    def by_result(self, result: str) -> tuple[Scope, ...]:
        return tuple(s for s in self.scopes if s.result == result)

    @property
    def verdict(self) -> str:
        """全体の結果。1 行でも決まらなければ 決まらない。"""
        self._guard()
        if self.by_result(RESULTS[2]):
            return RESULTS[2]
        if self.by_result(RESULTS[0]):
            return RESULTS[0]
        return RESULTS[1]

    def by_why(self) -> dict[str, int]:
        """決まらない理由別の件数(宣言の順に並べる。率は返さない)。"""
        out: dict[str, int] = {}
        for why in UNDECIDED:
            n = sum(1 for s in self.scopes if s.why == why)
            if n:
                out[why] = n
        return out

    def counts(self) -> dict[str, object]:
        """件数は理由別に、分母(結果台帳の行数)と内訳つきで出す。率は単独で返さない。"""
        four = {r: len(self.by_result(r)) for r in RESULTS}
        why = self.by_why()
        out: dict[str, object] = {
            "結果の台帳の行数": self.report.rows,
            "版の台帳の行数": self.report.versions,
            "差分の台帳の行数": self.report.diffs,
            "版の鎖の段数": len(self.chain.order) if self.chain else 0,
            "新しい版": self.chain.newest[:8] if self.chain else "",
            "4 値": four,
            "決まらない理由別": why,
            "出し直す対象": four[RESULTS[0]],
            "読んだか": ("読んだ" if self.scopes else
                         "読んでいない(表が揃う前に止まったので 4 値は全て 0)"),
        }
        out["分母に含めたもの"] = (
            f"結果の台帳の行数 {self.report.rows} 行。4 値の内訳は "
            f"影響あり {four[RESULTS[0]]} + 影響なし {four[RESULTS[1]]}"
            f" + 決まらない {four[RESULTS[2]]} + 止まった {four[RESULTS[3]]}。"
            f"決まらないの内訳は 決まらない理由別 の欄に出した")
        out["件数の合計の検算"] = (
            f"4 値の合計 {sum(four.values())} / 結果の台帳の行数 {self.report.rows}"
            f"(決まらない理由別の合計 {sum(why.values())} = 決まらない"
            f" {four[RESULTS[2]]})")
        out["版は指紋で指す"] = (
            "引いた版は指紋だけで突き合わせた。版の日付も出した日も表示だけに使い、"
            "鎖の辿り方にも判定部分にも入れていない(同じ内容に戻った版があるので"
            "日付順では版が一意にならない)")
        out["見本から全件を推定しない"] = (
            "差分台帳が 見本だけ と宣言している区間を含む結果は 決まらない に落とした。"
            "見本から全件を補う経路も、足すべきキーを提案する経路も無い")
        out["再計算しない"] = (
            "値を計算し直す経路も、他の道具を呼ぶ経路も、出し直す順番を付ける経路も無い。"
            "判定は 引いたキー ∩ 区間で変わったキー ≠ 空 までで、値がどう変わるかは見ない")
        return out

    def table(self) -> list[dict[str, object]]:
        """結果ごとの読み。率の欄は無い。"""
        return [{"結果 id": s.row.result_id, "対象": s.row.target, "項目": s.row.item,
                 "引いた版": s.row.version[:8], "引いたキーの件数": len(s.row.keys),
                 "結果": s.result, "決まらない理由": s.why, "区間の段数": s.steps,
                 "突き合わせたキーの件数": s.compared,
                 "当たったキー": list(s.hit), "出した日": s.row.issued,
                 "出典": s.row.source}
                for s in self.scopes]

    def targets(self) -> list[dict[str, object]]:
        """影響ありだけを別に並べる(出し直す対象。順番は付けない = 結果 id の順)。"""
        return [{"結果 id": s.row.result_id, "対象": s.row.target, "項目": s.row.item,
                 "引いた版": s.row.version[:8], "当たったキー": list(s.hit)}
                for s in self.scopes if s.result == RESULTS[0]]

    # -------------------------------------------------- 判定部分
    def judgement_bytes(self) -> bytes:
        """判定部分 = 読んだ結果の表。時刻・絶対パス・ホスト名・日付は入れない。"""
        self._guard()
        assert self.chain is not None
        lines = ["\t".join(["鎖", str(len(self.chain.order)),
                            self.chain.newest, str(self.report.rows)])]
        for s in self.scopes:
            lines.append("\t".join([
                s.row.result_id, s.row.target, s.row.item, s.row.version,
                KEY_SEP.join(s.row.keys), s.result, s.why,
                str(s.steps), str(s.compared), KEY_SEP.join(s.hit)]))
        return ("\n".join(lines) + "\n").encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.judgement_bytes()).hexdigest()

    def read_condition(self) -> dict[str, str]:
        return {SCOPE_KEYS[0]: self.ledger.path, SCOPE_KEYS[1]: self.versions.path,
                SCOPE_KEYS[2]: self.diffs.path, SCOPE_KEYS[3]: self.read_at,
                SCOPE_KEYS[4]: self.host}

    def _guard(self) -> None:
        if not self.report.ok:
            raise RuntimeError("止まっているので読んだ範囲は無い。"
                               "report.pending の理由コードを見る")


def scope(ledger: Ledger, versions: Versions, diffs: Diffs) -> Table:
    """出し直す範囲を出す。表が揃う前に止まったら 1 行も読まない。"""
    now = datetime.datetime.now().isoformat(timespec="seconds")
    host = platform.node()
    pending = list(ledger.pending) + list(versions.pending) + list(diffs.pending)

    def made(pend: tuple[Pending, ...], chain: Chain | None = None,
             scopes: tuple[Scope, ...] = ()) -> Table:
        return Table(report=Report(not pend, pend, len(ledger.items),
                                   len(versions.items), len(diffs.items)),
                     scopes=scopes, chain=chain, ledger=ledger, versions=versions,
                     diffs=diffs, read_at=now, host=host)

    # 引いた版の指紋が版台帳に在るか(日付ではなく指紋で突き合わせる)
    for r in ledger.items:
        if r.version and versions.of(r.version) is None:
            pending.append(Pending(STOP_REASONS[1],
                                   f"結果の台帳 行 {r.number}({r.result_id}): "
                                   f"{r.version[:8]}"))
    # 結果 id が 2 行あると、件数を結果 1 件ずつに割り当てられない
    seen: dict[str, int] = {}
    for r in ledger.items:
        seen[r.result_id] = seen.get(r.result_id, 0) + 1
    for rid, n in sorted(kv for kv in seen.items() if kv[1] > 1):
        pending.append(Pending(STOP_REASONS[6], f"2 行ある結果 id: {rid}({n} 行)"))

    if pending:                      # 表が揃う前に止まる(1 行も読まない)
        return made(tuple(pending))

    chain = chain_of(versions)       # 鎖が 1 本に決まらなければ「表として読めない」
    scopes: list[Scope] = []
    for r in ledger.ordered:
        steps = chain.steps(r.version)
        if not r.keys:
            # キーが空の結果を「影響なし」に寄せない
            scopes.append(Scope(row=r, result=RESULTS[2], why=UNDECIDED[1],
                                steps=len(steps)))
            continue
        rows_of_steps = [diffs.of_step(s) for s in steps]
        if any(not rows for rows in rows_of_steps):
            # 区間の差分が台帳に無い。間を推定で繋がない
            scopes.append(Scope(row=r, result=RESULTS[2], why=UNDECIDED[2],
                                steps=len(steps)))
            continue
        if any(d.sampled for rows in rows_of_steps for d in rows):
            # 見本だけと宣言された区間。見本から全件を推定しない
            scopes.append(Scope(row=r, result=RESULTS[2], why=UNDECIDED[0],
                                steps=len(steps)))
            continue
        changed: set[str] = set()
        for rows in rows_of_steps:
            for d in rows:
                changed |= set(d.keys)
        hit = tuple(sorted(set(r.keys) & changed))
        scopes.append(Scope(row=r, result=RESULTS[0] if hit else RESULTS[1],
                            steps=len(steps), hit=hit, compared=len(changed)))
    return made((), chain, tuple(scopes))


def verify(ledger: Ledger, versions: Versions, diffs: Diffs) -> dict[str, object]:
    """2 回読んで sha256 を比べ、行順を入れ替えても同じかを見て、件数を検算する。"""
    first = scope(ledger, versions, diffs)
    if not first.report.ok:
        return {"ok": False, "stage": "止まった(読んだ範囲は返さない)", **first.counts(),
                "pending": [p.as_dict() for p in first.report.pending]}
    if not ledger.swap:
        raise ReadError("結果の台帳に入れ替え方(swap)が無いので verify は走らせない")
    second = scope(ledger, versions, diffs)
    third = scope(ledger.swapped(ledger.swap), versions, diffs)
    pending: list[Pending] = []
    if first.sha256() != second.sha256():
        pending.append(Pending(STOP_REASONS[7], f"2 回目 {second.sha256()[:12]}"))
    if not (third.report.ok and first.sha256() == third.sha256()):
        pending.append(Pending(STOP_REASONS[8],
                               f"入れ替え方 {ledger.swap} の表で {third.sha256()[:12]}"
                               if third.report.ok else
                               f"入れ替え方 {ledger.swap} の表では止まった"))
    four = {r: len(first.by_result(r)) for r in RESULTS}
    why = first.by_why()
    if sum(four.values()) != first.report.rows:
        pending.append(Pending(STOP_REASONS[6],
                               f"4 値の合計 {sum(four.values())}"
                               f" / 結果の台帳の行数 {first.report.rows}"))
    if sum(why.values()) != four[RESULTS[2]]:
        pending.append(Pending(STOP_REASONS[6],
                               f"決まらない理由別の合計 {sum(why.values())}"
                               f" / 決まらない {four[RESULTS[2]]}"))
    out: dict[str, object] = {
        "ok": not pending, "読んだ結果": first.verdict, "読んだ回数": 2,
        "入れ替え方": ledger.swap, "sha256": first.sha256(),
        "2 回目の sha256": second.sha256(),
        "入れ替えた表の sha256": third.sha256() if third.report.ok else "",
        "件数の検算": {"4 値": four, "4 値の合計": sum(four.values()),
                       "決まらない理由別の合計": sum(why.values()),
                       "結果の台帳の行数": first.report.rows},
    }
    if pending:
        out["観測"] = ("同じ表から違うバイト列が出た(平均も多数決もしない。"
                       "どちらが正しいかも決めない)")
        out["pending"] = [p.as_dict() for p in pending]
    return out


# ------------------------------------------------------------ ひな型

_V1 = "a7b2c1d4e8f3a6b9"
_V2 = "b3c8d1e6f2a9b4c7"
_K1 = "合成のキーA(架空)"
_K2 = "合成のキーB(架空)"

TEMPLATE_LEDGER = [
    list(KEKKA_COLUMNS),
    ["R01", "合成の区分A", "合成の項目(架空)", _V1, _K1, "2026-02-10",
     "合成の結果メモ(架空)L1", "逆順"],
    ["R02", "合成の区分B", "合成の項目(架空)", _V2, _K2, "2026-03-10",
     "合成の結果メモ(架空)L2", ""],
]
TEMPLATE_VERSIONS = [
    list(HAN_COLUMNS),
    [_V1, "2026-01-05", "", "合成の版メモ(架空)L1"],
    [_V2, "2026-02-09", _V1, "合成の版メモ(架空)L2"],
]
TEMPLATE_DIFFS = [
    list(SABUN_COLUMNS),
    [_V1, _V2, _K1, "変更", "全件", "合成の差分メモ(架空)L1"],
]


def write_csv(path: Path, rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    return path


def init(dest: str | Path) -> tuple[Path, Path, Path]:
    d = Path(dest)
    return (write_csv(d / "結果の台帳.csv", TEMPLATE_LEDGER),
            write_csv(d / "版の台帳.csv", TEMPLATE_VERSIONS),
            write_csv(d / "差分の台帳.csv", TEMPLATE_DIFFS))


# ------------------------------------------------------------ CLI

def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def build_parser() -> argparse.ArgumentParser:
    """CLI は scope / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = argparse.ArgumentParser(prog="recalc_scope",
                                 description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in SUBCOMMANDS[:3]:
        p = sub.add_parser(name)
        p.add_argument("ledger")
        p.add_argument("versions")
        p.add_argument("diffs")
    sub.add_parser(SUBCOMMANDS[3]).add_argument("dest")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == "init":
        print("書いた: " + " / ".join(str(p) for p in init(a.dest)))
        return 0
    try:
        ledger, versions = Ledger.load(a.ledger), Versions.load(a.versions)
        diffs = Diffs.load(a.diffs)
        if a.cmd == "verify":
            out = verify(ledger, versions, diffs)
            _print(out)
            return 0 if out["ok"] else 3
        t = scope(ledger, versions, diffs)
    except ReadError as e:
        print(f"表として読めない: {e}", file=sys.stderr)
        return 2
    if not t.report.ok:
        _print({"ok": False, "stage": "止まった(読んだ範囲は返さない)", **t.counts(),
                "pending": [p.as_dict() for p in t.report.pending]})
        return 3
    body: dict[str, object] = {"ok": True, "読んだ結果": t.verdict, **t.counts()}
    if a.cmd == "scope":
        body["結果ごと"] = t.table()
        body["出し直す対象の一覧"] = t.targets()
        body["sha256"] = t.sha256()
        body["読んだ条件"] = t.read_condition()
    _print(body)
    return 0 if not t.by_result(RESULTS[2]) else 3


if __name__ == "__main__":
    raise SystemExit(main())
