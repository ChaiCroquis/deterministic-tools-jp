"""basis_map — 行を引く前に「どの日付を渡すか」が 1 つに決まるかを出す。引かない、決まるかを出すだけ。

**日付は 1 種類ではない。手元にあるのが支払日でも、行が求めているのは対象月初日や離職日や
請求日で、どの種別を渡すかを台帳に書いていないと、似た名前の日付が黙って代入される。**
この部品は、日付の種別の台帳・rule ごとの要求表・手元の表の 3 枚から、(rule × 対象)の組
1 つごとに 4 値(**決まった / 手元に無い / 決まらない / 止まった**)を付ける。決まらないものは
理由別(候補どまり / 宣言外の表記 / 同じ種別に 2 つ)に分けて数え、分母(rule 数 × 対象数)と
内訳を併記して返す。

持たせていないものが規律になっている。

  - **別名は台帳に宣言された分だけ写す**(「賃金締切日」と「賃金締め日」を寄せるのは台帳に
    そう書いてある時だけ。文字列が似ていることを理由に寄せる経路を持たない)
  - **手元に無い種別を別の日付で代用しない**(支払日から対象月初日を作らない。月初・月末へ
    丸める引数も、前営業日へずらす引数も、今日やシステム日付を使う経路も無い)
  - **要求する種別が台帳に登録されていなければ「決まらない」に落ちる**(候補の但し書きが
    付いた種別を登録済み扱いにしない)
  - **同じ種別に日付が 2 つあれば「決まらない」**(新しい方・先に出てきた方を採らない)
  - **同じ別名が 2 つの種別に宣言されていれば止まる**(どちらかに寄せない)
  - **日付の書式を推測して読まない**(台帳に宣言された書式だけ)
  - **日付の値を作らない・ずらさない・比べない**(引く段には入らない)
  - **空欄の意味は決めない**(欠けている理由は読まず「手元に無い」で止める)
  - **足すべき種別も別名も提案しない**(決めるのは台帳を書く人)
  - **件数は理由別に分母(rule 数 × 対象数)と内訳つきで出す**(率を単独で返さない)
  - **4 つを混ぜない**(決まった / 手元に無い / 決まらない / 止まった)
  - **入力表を書き換えず、種別も別名も生成しない**
  - **出典の欄が空の行は使わずに止まる**
  - **float を使わない**(件数は整数、日付は文字列のまま持つ)
  - **同じ入力には同じバイト列**(判定部分に時刻・絶対パス・ホスト名を入れない)

入力は 3 つ。日付の種別の台帳(CSV)、rule ごとの要求表(CSV)、手元の表(CSV)。

種別の台帳の列は 7 つ。

    kind_id   種別 id(空欄は「表として読めない」。2 行あると止まる)
    name      正式な表記(空欄は「表として読めない」)
    aliases   宣言された別名(縦棒で区切る。0 件以上)
    meaning   意味の 1 行(空欄は「表として読めない」)
    format    日付の書式。登録の 2 種(YYYY-MM-DD / YYYY-MM)。外は読めない表
    status    状態。登録の 2 種(登録済 / 候補)。外は止まる
    source    出典。空欄は止まる

要求表の列は 3 つ。1 rule が 1 行。

    rule_id   rule id(空欄は「表として読めない」。2 行あると止まる)
    kind_id   その rule が要求する種別 id。台帳に無い id は止まる
    source    出典。空欄は止まる

手元の表の列は 5 つ。1 対象 × 1 表記で 1 行。

    target_id   対象 id(空欄は「表として読めない」)
    kind_label  手元に書かれている表記(正式な表記か、宣言された別名)
    date        日付(文字列のまま持つ。宣言された書式に合わなければ止まる)
    source      出典。空欄は止まる
    swap        入れ替え方(verify が 3 枚の行順を入れ替えるときの宣言。全行で同じ値)

使い方:

    python basis_map.py init ひな型/
    python basis_map.py check  種別の台帳.csv 要求表.csv 手元の表.csv
    python basis_map.py map    種別の台帳.csv 要求表.csv 手元の表.csv
    python basis_map.py verify 種別の台帳.csv 要求表.csv 手元の表.csv
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

SHUBETSU_COLUMNS = ("kind_id", "name", "aliases", "meaning", "format", "status",
                    "source")
YOUKYUU_COLUMNS = ("rule_id", "kind_id", "source")
TEMOTO_COLUMNS = ("target_id", "kind_label", "date", "source", "swap")

# 登録の語彙
FORMATS = {"YYYY-MM-DD": "%Y-%m-%d", "YYYY-MM": "%Y-%m"}
STATUSES = ("登録済", "候補")
SWAPS = ("逆順", "両端入れ替え", "1 つずらす")
ALIAS_SEP = "|"

# 組ごとの 4 値。4 つを混ぜない
RESULTS = ("決まった", "手元に無い", "決まらない", "止まった")

# 決まらない理由(3 種。決まった / 手元に無い とは別の欄で数える)
UNDECIDED = ("候補どまり", "宣言外の表記", "同じ種別に 2 つ")

# 止まる理由コード(9 個)
STOP_REASONS = ("出典の欄が空", "種別 id が台帳に無い", "同じ別名が 2 種別に宣言",
                "台帳に同じ種別 id が 2 行", "書式が宣言外", "状態が宣言外",
                "件数の合計が合わない", "2 回目の判定部分が不一致",
                "行順を入れ替えた表で出力が変わる")

# CLI の下位コマンド。この 4 つだけで、option は -h 以外に 1 つも無い
SUBCOMMANDS = ("map", "check", "verify", "init")

# 判定部分に入れない欄(sha256 の対象にもしない)
SCOPE_KEYS = ("読んだ種別の台帳の絶対パス", "読んだ要求表の絶対パス",
              "読んだ手元の表の絶対パス", "読んだ時刻", "ホスト名")


class ReadError(Exception):
    """表として読めない(理由コードにせず終了コード 2 で返す = 表を書く側の話)。"""


def split_aliases(text: str, where: str) -> tuple[str, ...]:
    """縦棒で区切った別名の一覧。順は入力に依らせない(並べ替えて持つ)。"""
    names = tuple(a.strip() for a in text.split(ALIAS_SEP) if a.strip())
    if len(set(names)) != len(names):
        raise ReadError(f"{where}: 別名の一覧に同じ表記が 2 つある")
    return tuple(sorted(names))


def swap_rows(rows: list, how: str) -> list:
    """宣言された入れ替え方で行順だけを入れ替える(乱数の既定は持たない)。"""
    if how not in SWAPS:
        raise ReadError(f"入れ替え方が登録の外: {how}")
    out = list(rows)
    if len(out) >= 2:
        if how == SWAPS[0]:
            out.reverse()
        elif how == SWAPS[1]:
            out[0], out[-1] = out[-1], out[0]
        else:
            out = out[1:] + out[:1]
    return out


@dataclass(frozen=True)
class Pending:
    reason: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"reason": self.reason, "detail": self.detail}


# ------------------------------------------------------------ 種別の台帳

@dataclass(frozen=True)
class Kind:
    kind_id: str
    name: str
    aliases: tuple[str, ...]
    meaning: str
    format: str
    status: str
    source: str
    number: int

    @property
    def registered(self) -> bool:
        return self.status == STATUSES[0]

    @property
    def labels(self) -> tuple[str, ...]:
        """この種別を指してよい表記。正式な表記と、宣言された別名だけ。"""
        return (self.name,) + self.aliases


@dataclass(frozen=True)
class Registry:
    items: tuple[Kind, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Registry":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"種別の台帳が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Registry":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in SHUBETSU_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("種別の台帳に " + " / ".join(lack) + " の列が無い")
        items: list[Kind] = []
        pending: list[Pending] = []
        seen: set[str] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in SHUBETSU_COLUMNS}
            where = f"種別の台帳 行 {i}"
            if not cell["kind_id"]:
                raise ReadError(f"{where}: 種別 id が空欄")
            if not cell["name"]:
                raise ReadError(f"{where}: 正式な表記が空欄({cell['kind_id']})")
            if not cell["meaning"]:
                raise ReadError(f"{where}: 意味の 1 行が空欄({cell['kind_id']})")
            if cell["format"] not in FORMATS:
                raise ReadError(f"{where}: 書式は {' / '.join(FORMATS)} の宣言だけ"
                                f"({cell['format'] or '空欄'})")
            if cell["kind_id"] in seen:
                pending.append(Pending(STOP_REASONS[3], f"{where}: {cell['kind_id']}"))
            seen.add(cell["kind_id"])
            if cell["status"] not in STATUSES:
                pending.append(Pending(STOP_REASONS[5],
                                       f"{where}({cell['kind_id']}): "
                                       f"{cell['status'] or '空欄'}"))
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0], f"{where}({cell['kind_id']})"))
            items.append(Kind(kind_id=cell["kind_id"], name=cell["name"],
                              aliases=split_aliases(cell["aliases"],
                                                    f"{where} の別名"),
                              meaning=cell["meaning"], format=cell["format"],
                              status=cell["status"], source=cell["source"],
                              number=i))
        if not items:
            raise ReadError("種別の台帳に行が無い(ヘッダだけ)")
        # 同じ表記が 2 つの種別に宣言されていたら、どちらに寄せるかを決めずに止まる
        owner: dict[str, str] = {}
        for k in items:
            for label in k.labels:
                old = owner.get(label)
                if old is not None and old != k.kind_id:
                    pending.append(Pending(STOP_REASONS[2],
                                           f"{label}: {old} と {k.kind_id}"))
                owner.setdefault(label, k.kind_id)
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    def of(self, kind_id: str) -> Kind | None:
        return next((k for k in self.items if k.kind_id == kind_id), None)

    def by_label(self, label: str) -> Kind | None:
        """宣言された表記だけで写す。似ているという理由で寄せる経路は無い。"""
        return next((k for k in self.items if label in k.labels), None)

    def swapped(self, how: str) -> "Registry":
        return Registry(items=tuple(swap_rows(list(self.items), how)),
                        pending=self.pending, path=self.path)


# ------------------------------------------------------------ 要求表

@dataclass(frozen=True)
class Demand:
    rule_id: str
    kind_id: str
    source: str
    number: int


@dataclass(frozen=True)
class Demands:
    items: tuple[Demand, ...]
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Demands":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"要求表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Demands":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in YOUKYUU_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("要求表に " + " / ".join(lack) + " の列が無い")
        items: list[Demand] = []
        pending: list[Pending] = []
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in YOUKYUU_COLUMNS}
            where = f"要求表 行 {i}"
            if not cell["rule_id"]:
                raise ReadError(f"{where}: rule id が空欄")
            if not cell["kind_id"]:
                raise ReadError(f"{where}: 要求する種別 id が空欄({cell['rule_id']})")
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0], f"{where}({cell['rule_id']})"))
            items.append(Demand(rule_id=cell["rule_id"], kind_id=cell["kind_id"],
                                source=cell["source"], number=i))
        if not items:
            raise ReadError("要求表に行が無い(ヘッダだけ)")
        return cls(items=tuple(items), pending=tuple(pending), path=path)

    @property
    def ordered(self) -> tuple[Demand, ...]:
        """rule id の順に並べ替えて返す(表の行順には依らせない)。"""
        return tuple(sorted(self.items, key=lambda d: d.rule_id))

    def swapped(self, how: str) -> "Demands":
        return Demands(items=tuple(swap_rows(list(self.items), how)),
                       pending=self.pending, path=self.path)


# ------------------------------------------------------------ 手元の表

@dataclass(frozen=True)
class Have:
    target_id: str
    kind_label: str
    date: str
    source: str
    number: int


@dataclass(frozen=True)
class Hand:
    items: tuple[Have, ...]
    swap: str
    pending: tuple[Pending, ...] = ()
    path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Hand":
        p = Path(path)
        if not p.exists():
            raise ReadError(f"手元の表が無い: {p}")
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @classmethod
    def parse(cls, text: str, path: str = "") -> "Hand":
        reader = csv.DictReader(text.splitlines())
        lack = [c for c in TEMOTO_COLUMNS if c not in tuple(reader.fieldnames or ())]
        if lack:
            raise ReadError("手元の表に " + " / ".join(lack) + " の列が無い")
        items: list[Have] = []
        pending: list[Pending] = []
        swaps: set[str] = set()
        seen: set[tuple[str, str]] = set()
        for i, raw in enumerate(reader, start=2):
            cell = {k: (raw.get(k) or "").strip() for k in TEMOTO_COLUMNS}
            where = f"手元の表 行 {i}"
            if not cell["target_id"]:
                raise ReadError(f"{where}: 対象 id が空欄")
            if not cell["kind_label"]:
                raise ReadError(f"{where}: 表記が空欄({cell['target_id']})")
            if not cell["date"]:
                raise ReadError(f"{where}: 日付が空欄({cell['target_id']})")
            key = (cell["target_id"], cell["kind_label"])
            if key in seen:
                raise ReadError(f"{where}: {cell['target_id']} の "
                                f"{cell['kind_label']} が 2 行ある")
            seen.add(key)
            if cell["swap"]:
                if cell["swap"] not in SWAPS:
                    raise ReadError(f"{where}: 入れ替え方 {cell['swap']} は登録の外"
                                    f"({' / '.join(SWAPS)})")
                swaps.add(cell["swap"])
            if not cell["source"]:
                pending.append(Pending(STOP_REASONS[0],
                                       f"{where}({cell['target_id']} / "
                                       f"{cell['kind_label']})"))
            items.append(Have(target_id=cell["target_id"],
                              kind_label=cell["kind_label"], date=cell["date"],
                              source=cell["source"], number=i))
        if not items:
            raise ReadError("手元の表に行が無い(ヘッダだけ)")
        if len(swaps) > 1:
            raise ReadError("入れ替え方の宣言が 2 通り以上ある: "
                            + " / ".join(sorted(swaps)))
        return cls(items=tuple(items), swap=next(iter(swaps), ""),
                   pending=tuple(pending), path=path)

    @property
    def targets(self) -> tuple[str, ...]:
        """対象 id を並べ替えて返す(表の行順には依らせない)。"""
        return tuple(sorted({h.target_id for h in self.items}))

    def rows_of(self, target_id: str) -> tuple[Have, ...]:
        return tuple(sorted((h for h in self.items if h.target_id == target_id),
                            key=lambda h: h.kind_label))

    def swapped(self, how: str) -> "Hand":
        return Hand(items=tuple(swap_rows(list(self.items), how)), swap=self.swap,
                    pending=self.pending, path=self.path)


# ------------------------------------------------------------ 写す

def fits(date: str, fmt: str) -> bool:
    """台帳に宣言された書式だけで読む。推測で別の書式を試す経路は無い。"""
    try:
        datetime.datetime.strptime(date, FORMATS[fmt])
    except ValueError:
        return False
    return True


@dataclass(frozen=True)
class Mapped:
    """手元の 1 行を、宣言された表記で種別へ写した結果。"""
    row: Have
    kind_id: str          # 写せなければ空文字(= 宣言外の表記)


def map_hand(registry: Registry, hand: Hand) -> dict[str, tuple[Mapped, ...]]:
    """対象ごとに、手元の行を宣言された表記だけで種別へ写す。"""
    out: dict[str, tuple[Mapped, ...]] = {}
    for t in hand.targets:
        rows = []
        for h in hand.rows_of(t):
            k = registry.by_label(h.kind_label)
            rows.append(Mapped(row=h, kind_id=k.kind_id if k else ""))
        out[t] = tuple(rows)
    return out


# ------------------------------------------------------------ 決まるかを出す

@dataclass(frozen=True)
class Pair:
    """(rule × 対象)1 組の読み。日付を作らず、どの種別が正しいかも言わない。"""
    rule_id: str
    kind_id: str
    target_id: str
    result: str
    why: str = ""          # 決まらないときだけ、3 種のどれか
    label: str = ""        # 決まったときだけ、手元に書かれていた表記
    date: str = ""         # 決まったときだけ、手元の日付(文字列のまま)
    others: int = 0        # その対象で、写せなかった行の件数


@dataclass(frozen=True)
class Report:
    ok: bool
    pending: tuple[Pending, ...]
    kinds: int
    rules: int
    hand_rows: int
    targets: int


@dataclass(frozen=True)
class Table:
    report: Report
    pairs: tuple[Pair, ...]
    registry: Registry
    demands: Demands
    hand: Hand
    read_at: str
    host: str

    # -------------------------------------------------- 4 値と分母
    def by_result(self, result: str) -> tuple[Pair, ...]:
        return tuple(p for p in self.pairs if p.result == result)

    @property
    def verdict(self) -> str:
        """全体の結果。1 組でも決まらなければ 決まらない。"""
        self._guard()
        if self.by_result(RESULTS[2]):
            return RESULTS[2]
        if self.by_result(RESULTS[1]):
            return RESULTS[1]
        return RESULTS[0]

    def by_why(self) -> dict[str, int]:
        """決まらない理由別の件数(宣言の順に並べる。率は返さない)。"""
        out: dict[str, int] = {}
        for why in UNDECIDED:
            n = sum(1 for p in self.pairs if p.why == why)
            if n:
                out[why] = n
        return out

    @property
    def denominator(self) -> int:
        return self.report.rules * self.report.targets

    def counts(self) -> dict[str, object]:
        """件数は理由別に、分母(rule 数 × 対象数)と内訳つきで出す。率は単独で返さない。"""
        four = {r: len(self.by_result(r)) for r in RESULTS}
        why = self.by_why()
        out: dict[str, object] = {
            "種別の台帳の行数": self.report.kinds,
            "要求表の行数": self.report.rules,
            "手元の表の行数": self.report.hand_rows,
            "対象数": self.report.targets,
            "分母(rule 数 × 対象数)": self.denominator,
            "4 値": four,
            "決まらない理由別": why,
            "読んだか": ("読んだ" if self.pairs else
                         "読んでいない(表が揃う前に止まったので 4 値は全て 0)"),
        }
        out["分母に含めたもの"] = (
            f"rule 数 {self.report.rules} × 対象数 {self.report.targets}"
            f" = {self.denominator} 組。4 値の内訳は "
            f"決まった {four[RESULTS[0]]} + 手元に無い {four[RESULTS[1]]}"
            f" + 決まらない {four[RESULTS[2]]} + 止まった {four[RESULTS[3]]}。"
            f"決まらないの内訳は 決まらない理由別 の欄に出した")
        out["件数の合計の検算"] = (
            f"4 値の合計 {sum(four.values())} / 分母 {self.denominator}"
            f"(決まらない理由別の合計 {sum(why.values())} = 決まらない"
            f" {four[RESULTS[2]]})")
        out["似た表記を自分で寄せない"] = (
            "手元の表記を種別へ写したのは、台帳の正式な表記と宣言された別名に一致した"
            "時だけ。文字列が似ていることを理由に寄せる経路も、寄せ方を推測する経路も無い")
        out["手元に無い種別を代用しない"] = (
            "要求する種別の行が手元に無いとき、別の日付で作る経路が無い。"
            "月初・月末へ丸める引数も、前営業日へずらす引数も、今日やシステム日付を"
            "使う経路も持たない")
        out["日付を作らない・ずらさない・比べない"] = (
            "日付は文字列のまま持ち、宣言された書式に合うかだけを見た。版を選ぶ段にも、"
            "期間を切る段にも、帯に当てる段にも入らない。足すべき種別も別名も提案しない")
        return out

    def table(self) -> list[dict[str, object]]:
        """組ごとの読み。率の欄は無い。"""
        return [{"rule id": p.rule_id, "要求する種別": p.kind_id,
                 "対象 id": p.target_id, "結果": p.result, "決まらない理由": p.why,
                 "手元の表記": p.label, "渡す日付": p.date,
                 "写せなかった行の件数": p.others}
                for p in self.pairs]

    def decided(self) -> list[dict[str, object]]:
        """決まった組だけを別に並べる(順番は付けない = rule id と対象 id の順)。"""
        return [{"rule id": p.rule_id, "要求する種別": p.kind_id,
                 "対象 id": p.target_id, "手元の表記": p.label, "渡す日付": p.date}
                for p in self.pairs if p.result == RESULTS[0]]

    # -------------------------------------------------- 判定部分
    def judgement_bytes(self) -> bytes:
        """判定部分 = 読んだ組の表。時刻・絶対パス・ホスト名は入れない。"""
        self._guard()
        lines = ["\t".join(["組", str(self.report.rules), str(self.report.targets),
                            str(self.denominator)])]
        for p in self.pairs:
            lines.append("\t".join([p.rule_id, p.kind_id, p.target_id, p.result,
                                    p.why, p.label, p.date, str(p.others)]))
        return ("\n".join(lines) + "\n").encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.judgement_bytes()).hexdigest()

    def read_condition(self) -> dict[str, str]:
        return {SCOPE_KEYS[0]: self.registry.path, SCOPE_KEYS[1]: self.demands.path,
                SCOPE_KEYS[2]: self.hand.path, SCOPE_KEYS[3]: self.read_at,
                SCOPE_KEYS[4]: self.host}

    def _guard(self) -> None:
        if not self.report.ok:
            raise RuntimeError("止まっているので読んだ組は無い。"
                               "report.pending の理由コードを見る")


def basis_map(registry: Registry, demands: Demands, hand: Hand) -> Table:
    """渡す日付が台帳から 1 つに決まるかを出す。表が揃う前に止まったら 1 組も読まない。"""
    now = datetime.datetime.now().isoformat(timespec="seconds")
    host = platform.node()
    pending = list(registry.pending) + list(demands.pending) + list(hand.pending)
    targets = hand.targets

    # 要求する種別 id が台帳に在るか(似た表記で探し直す経路は無い)
    for d in demands.items:
        if registry.of(d.kind_id) is None:
            pending.append(Pending(STOP_REASONS[1],
                                   f"要求表 行 {d.number}({d.rule_id}): {d.kind_id}"))
    # rule id が 2 行あると、件数を rule 1 件ずつに割り当てられない
    seen: dict[str, int] = {}
    for d in demands.items:
        seen[d.rule_id] = seen.get(d.rule_id, 0) + 1
    for rid, n in sorted(kv for kv in seen.items() if kv[1] > 1):
        pending.append(Pending(STOP_REASONS[6], f"2 行ある rule id: {rid}({n} 行)"))
    # 手元の日付が、写した先の種別に宣言された書式に合うか
    if not pending:
        for h in hand.items:
            k = registry.by_label(h.kind_label)
            if k is not None and not fits(h.date, k.format):
                pending.append(Pending(STOP_REASONS[4],
                                       f"手元の表 行 {h.number}"
                                       f"({h.target_id} / {h.kind_label}): "
                                       f"{h.date} は {k.format} でない"))

    def made(pend: tuple[Pending, ...], pairs: tuple[Pair, ...] = ()) -> Table:
        return Table(report=Report(not pend, pend, len(registry.items),
                                   len(demands.items), len(hand.items),
                                   len(targets)),
                     pairs=pairs, registry=registry, demands=demands, hand=hand,
                     read_at=now, host=host)

    if pending:                      # 表が揃う前に止まる(1 組も読まない)
        return made(tuple(pending))

    written = map_hand(registry, hand)
    pairs: list[Pair] = []
    for d in demands.ordered:
        kind = registry.of(d.kind_id)
        assert kind is not None      # 台帳に無い id は上で止めている
        for t in targets:
            rows = written[t]
            others = sum(1 for m in rows if not m.kind_id)
            if not kind.registered:
                # 候補の但し書きが付いた種別を登録済み扱いにしない
                pairs.append(Pair(d.rule_id, d.kind_id, t, RESULTS[2],
                                  why=UNDECIDED[0], others=others))
                continue
            hit = [m for m in rows if m.kind_id == d.kind_id]
            if len(hit) >= 2:
                # 新しい方・先に出てきた方を採らない
                pairs.append(Pair(d.rule_id, d.kind_id, t, RESULTS[2],
                                  why=UNDECIDED[2], others=others))
            elif len(hit) == 1:
                pairs.append(Pair(d.rule_id, d.kind_id, t, RESULTS[0],
                                  label=hit[0].row.kind_label, date=hit[0].row.date,
                                  others=others))
            elif others:
                # 写せない表記が残っている間は「手元に無い」と言い切らない
                pairs.append(Pair(d.rule_id, d.kind_id, t, RESULTS[2],
                                  why=UNDECIDED[1], others=others))
            else:
                pairs.append(Pair(d.rule_id, d.kind_id, t, RESULTS[1], others=others))
    return made((), tuple(pairs))


def verify(registry: Registry, demands: Demands, hand: Hand) -> dict[str, object]:
    """2 回読んで sha256 を比べ、3 枚の行順を入れ替えても同じかを見て、件数を検算する。"""
    first = basis_map(registry, demands, hand)
    if not first.report.ok:
        return {"ok": False, "stage": "止まった(読んだ組は返さない)", **first.counts(),
                "pending": [p.as_dict() for p in first.report.pending]}
    if not hand.swap:
        raise ReadError("手元の表に入れ替え方(swap)が無いので verify は走らせない")
    second = basis_map(registry, demands, hand)
    third = basis_map(registry.swapped(hand.swap), demands.swapped(hand.swap),
                      hand.swapped(hand.swap))
    pending: list[Pending] = []
    if first.sha256() != second.sha256():
        pending.append(Pending(STOP_REASONS[7], f"2 回目 {second.sha256()[:12]}"))
    if not (third.report.ok and first.sha256() == third.sha256()):
        pending.append(Pending(STOP_REASONS[8],
                               f"入れ替え方 {hand.swap} の 3 枚で "
                               f"{third.sha256()[:12]}" if third.report.ok else
                               f"入れ替え方 {hand.swap} の 3 枚では止まった"))
    four = {r: len(first.by_result(r)) for r in RESULTS}
    why = first.by_why()
    if sum(four.values()) != first.denominator:
        pending.append(Pending(STOP_REASONS[6],
                               f"4 値の合計 {sum(four.values())}"
                               f" / 分母 {first.denominator}"))
    if sum(why.values()) != four[RESULTS[2]]:
        pending.append(Pending(STOP_REASONS[6],
                               f"決まらない理由別の合計 {sum(why.values())}"
                               f" / 決まらない {four[RESULTS[2]]}"))
    out: dict[str, object] = {
        "ok": not pending, "読んだ結果": first.verdict, "読んだ回数": 2,
        "入れ替え方": hand.swap, "sha256": first.sha256(),
        "2 回目の sha256": second.sha256(),
        "入れ替えた 3 枚の sha256": third.sha256() if third.report.ok else "",
        "件数の検算": {"4 値": four, "4 値の合計": sum(four.values()),
                       "決まらない理由別の合計": sum(why.values()),
                       "分母(rule 数 × 対象数)": first.denominator},
    }
    if pending:
        out["観測"] = ("同じ表から違うバイト列が出た(平均も多数決もしない。"
                       "どちらが正しいかも決めない)")
        out["pending"] = [p.as_dict() for p in pending]
    return out


# ------------------------------------------------------------ ひな型

TEMPLATE_REGISTRY = [
    list(SHUBETSU_COLUMNS),
    ["K01", "合成の種別A(架空)", "合成の別名A(架空)", "合成の意味の 1 行(架空)",
     "YYYY-MM-DD", "登録済", "合成の台帳メモ(架空)L1"],
    ["K02", "合成の種別B(架空)", "", "合成の意味の 1 行(架空)",
     "YYYY-MM-DD", "候補", "合成の台帳メモ(架空)L2"],
]
TEMPLATE_DEMANDS = [
    list(YOUKYUU_COLUMNS),
    ["R01", "K01", "合成の要求メモ(架空)L1"],
    ["R02", "K02", "合成の要求メモ(架空)L2"],
]
TEMPLATE_HAND = [
    list(TEMOTO_COLUMNS),
    ["T01", "合成の種別A(架空)", "2026-04-01", "合成の手元メモ(架空)L1", "逆順"],
    ["T02", "合成の別名A(架空)", "2026-04-01", "合成の手元メモ(架空)L2", ""],
]


def write_csv(path: Path, rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    return path


def init(dest: str | Path) -> tuple[Path, Path, Path]:
    d = Path(dest)
    return (write_csv(d / "種別の台帳.csv", TEMPLATE_REGISTRY),
            write_csv(d / "要求表.csv", TEMPLATE_DEMANDS),
            write_csv(d / "手元の表.csv", TEMPLATE_HAND))


# ------------------------------------------------------------ CLI

def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def build_parser() -> argparse.ArgumentParser:
    """CLI は map / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = argparse.ArgumentParser(prog="basis_map",
                                 description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in SUBCOMMANDS[:3]:
        p = sub.add_parser(name)
        p.add_argument("registry")
        p.add_argument("demands")
        p.add_argument("hand")
    sub.add_parser(SUBCOMMANDS[3]).add_argument("dest")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == "init":
        print("書いた: " + " / ".join(str(p) for p in init(a.dest)))
        return 0
    try:
        registry, demands = Registry.load(a.registry), Demands.load(a.demands)
        hand = Hand.load(a.hand)
        if a.cmd == "verify":
            out = verify(registry, demands, hand)
            _print(out)
            return 0 if out["ok"] else 3
        t = basis_map(registry, demands, hand)
    except ReadError as e:
        print(f"表として読めない: {e}", file=sys.stderr)
        return 2
    if not t.report.ok:
        _print({"ok": False, "stage": "止まった(読んだ組は返さない)", **t.counts(),
                "pending": [p.as_dict() for p in t.report.pending]})
        return 3
    body: dict[str, object] = {"ok": True, "読んだ結果": t.verdict, **t.counts()}
    if a.cmd == "map":
        body["組ごと"] = t.table()
        body["決まった組の一覧"] = t.decided()
        body["sha256"] = t.sha256()
        body["読んだ条件"] = t.read_condition()
    _print(body)
    return 0 if not t.by_result(RESULTS[2]) else 3


if __name__ == "__main__":
    raise SystemExit(main())
