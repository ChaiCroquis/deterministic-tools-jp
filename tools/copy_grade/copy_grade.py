"""copy_grade — 同じ処理の写しを、文字の一致だけで 4 段に分ける。まとめてよいかは決めない。

**「同じ処理が N か所に散っている」と数えた箇所も、同じだと言える根拠は箇所ごとに別だ。**
指紋が一致すると注記された組・人が見て同型だと注記された組・行数が 3 通りある派生・
「散在」としか書かれていない組が、1 つの箇所数の中に入っている。**まとめる前にその段を
分けないと、写しを消すだけで済む箇所と、読んで判断しないと挙動が変わる箇所が、同じ工程に
乗る。**

この部品は、部品の台帳・箇所の台帳・注記記号の登録表(3 枚)と、写しの置き場から、
同じ部品 id の **2 箇所の組**(箇所 id の昇順)を 4 段 + 別枠 4 へ分ける。

  (A) そのままで同一        正規化の前の sha256 が一致
  (B) 空白と改行だけの差    決めた 3 つの正規化の後で sha256 が一致(正規化前は不一致)
  (C) 行数が同じで中身が違う 行数一致・正規化後も不一致。**違う行の番号だけ**を出す
  (D) 行数が違う            2 つの行数をそのまま出す

別枠 4 = 出典が空 / 注記記号が登録表に無い / その注記が要求する欄が空 / 写しが渡されていない。

合わせて部品ごとに **「宣言されている箇所数の文字列」と「写しが渡された箇所の件数」を並べて
返す**(= 一方をもう一方の代わりに使わせない。`8+` や `18 ファイル` を整数に直す経路が無い)。

持たせていないものが規律になっている。

  - **まとめてよいかを決めない**(統合の可否・順序・優先度・どの箇所が正本かを出す経路が無い)
  - **写しの中身を出力に出さない**(出すのは段・行番号・件数・箇所 id だけ。入力の文字を
    出力へ貼る経路が無い = 読んだコードそのものが公開物へ流れない物理形)
  - **名前を出力に出さない**(ファイル名・パス・道具名の列を持たず、箇所 id だけで返す)
  - **振る舞いが同じかを見ない**(実行しない・import しない・構文解析しない・テストを
    走らせない)
  - **似ている度合いを出さない**(類似度・距離・一致率・割合を出す経路が無く、段は
    ちょうど一致の階段 4 つだけ)
  - **注記を段の代わりに使わない**(`指紋一致と注記` が在っても写しが一致しなければ (A) に
    入れる経路が無く、注記と段は別の列で並ぶ)
  - **テストの有無を段に混ぜない**(走らせた結果を台帳に残すのは別の部品の領分)
  - **写しを取りに行かない**(通信の経路が無く、置き場の外を読まない)
  - **正規化は 3 つだけ**(字下げを揃えない・コメントを外さない・識別子を揃えない・
    引用符を揃えない。増やす引数が無い)
  - **時計を読まない**、**入力を書き換えない**、**float を使わない**、判定部分に時刻・
    絶対パス・ホスト名を入れない

入力は 3 枚 + 写しの置き場。**登録の側(部品の台帳 / 注記記号の登録表)の行に出典が無ければ
1 組も数えずに止まる。**

部品の台帳(CSV)の列は 6。

    part_id    部品 id(同じ id が 2 行あると止まる)
    what       部品の内容を表す説明
    declared   **宣言されている箇所数の文字列**(`17` / `8+` / `18 ファイル` / `4 + 5` の
               ような生の文字列をそのまま持つ。**整数に直す経路が無い**)
    industry   業種依存の記号(なし / あり)
    unified    統一の宣言記号(統一済みと宣言 / モジュール化は 1 本だけと宣言 / 宣言なし)
    source     出典(ファイル名 + 行番号)。空欄は止まる

箇所の台帳(CSV)の列は 6。

    site_id        箇所 id(同じ id が 2 行あると止まる)
    part_id        部品 id(部品の台帳に無いと止まる)
    copy           **その箇所のテキストの写しを置いたファイル**(置き場からの相対パス)。
                   空欄のとき、その箇所の組は別枠「写しが渡されていない」へ入る
    note           注記記号(登録表に在る記号だけ。無ければ別枠へ)
    declared_lines 注記に書かれている行数の記載(**生の文字列**。要求されない注記では `—`)
    source         出典。空欄のとき、その箇所の組は別枠「出典が空」へ入る

注記記号の登録表(CSV)の列は 4。**「その注記が何を要求するか」はここに在る。**

    note      記号(例 = 指紋一致と注記 / 同型と注記 / 派生と注記 / 散在と注記のみ / 注記なし)
    means     意味(1 行)
    requires  その注記が要求する欄(— / 写し / 行数)
    source    出典。空欄は止まる

使い方:

    python copy_grade.py init ひな型/
    python copy_grade.py check 部品.csv 箇所.csv 注記.csv 写しの置き場/
    python copy_grade.py pairs 部品.csv 箇所.csv 注記.csv 写しの置き場/
    python copy_grade.py verify 部品.csv 箇所.csv 注記.csv 写しの置き場/

終了コードは、別枠と止まった行と (A) 以外の段が 0 件のときだけ 0、在れば 3、表として読めな
ければ 2。**0 は「まとめてよい」ではなく「渡された写しが全部そのままで同一だった」の意味で、
統合の可否はこの部品の出力に出ない。**
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

PART_COLUMNS = ("part_id", "what", "declared", "industry", "unified", "source")
SITE_COLUMNS = ("site_id", "part_id", "copy", "note", "declared_lines", "source")
NOTE_COLUMNS = ("note", "means", "requires", "source")

# 業種依存の記号(**この 2 つの外に記号を作る経路が無い**)
INDUSTRY = ("なし", "あり")
# 統一の宣言記号(**寄せ先が 1 本決まったという宣言。段の代わりには使わない**)
UNIFIED = ("統一済みと宣言", "モジュール化は 1 本だけと宣言", "宣言なし")
# 注記が要求する欄(**記号の綴りから当てる経路が無く、登録表の側に書く**)
REQUIRES = ("—", "写し", "行数")

NO_MARK = "—"
NOT_REGISTERED = "(登録に無い)"

# 2 箇所の組 1 つに付く 4 段。**ちょうど一致の階段で、似ている度合いは出さない。**
DAN = (
    "(A) そのままで同一",
    "(B) 空白と改行だけの差",
    "(C) 行数が同じで中身が違う",
    "(D) 行数が違う",
)
# 4 段の外へ出す別枠 4。**上から順に当たり、4 段より先に当たる。**
BETSUWAKU = (
    "出典が空",
    "注記記号が登録表に無い",
    "その注記が要求する欄が空",
    "写しが渡されていない",
)
# 決めた 3 つの正規化。**それ以外は何もしない(増やす引数が無い)。**
NORMALIZE = ("行末の空白を落とす", "改行を LF に揃える", "末尾の空行を落とす")

SWAPS = ("逆順", "両端入れ替え", "1 つずらす")

STOP_REASONS = (
    # 表の側。1 組も数えずに止まる(6)
    "宣言の出典が空",
    "部品 id の重複",
    "箇所 id の重複",
    "箇所が指す部品 id が部品の台帳に無い",
    "同じ注記記号が登録表に 2 行ある",
    "同じ部品の 2 箇所が同じ写しのファイルを指している",
    # verify が見つける(3)
    "件数の合計が合わない", "2 回目の判定部分が不一致", "行順を入れ替えた表で出力が変わる",
)
TABLE_REASONS = STOP_REASONS[:6]
VERIFY_REASONS = STOP_REASONS[6:]

SUBCOMMANDS = ("pairs", "check", "verify", "init")
SCOPE_KEYS = ("読んだ部品の台帳の絶対パス", "読んだ箇所の台帳の絶対パス",
              "読んだ注記記号の登録表の絶対パス", "読んだ写しの置き場の絶対パス")

NG_ID = set(" \t,|;")


class ReadError(Exception):
    """表として読めない / 写しが読めない(終了コード 2)。2 箇所の組は 1 つも数えない。"""


@dataclass(frozen=True)
class Pending:
    reason: str
    detail: str = ""

    def as_dict(self) -> dict[str, str]:
        return {"理由コード": self.reason, "どこ": self.detail}


def bad_id(s: str) -> bool:
    return (not s) or any(ch in NG_ID for ch in s)


def swap_rows(rows: list, how: str) -> list:
    """登録された入れ替え方で行順を入れ替える(verify が使う)。"""
    if how == SWAPS[0]:
        return list(reversed(rows))
    if how == SWAPS[1]:
        out = list(rows)
        if len(out) >= 2:
            out[0], out[-1] = out[-1], out[0]
        return out
    if how == SWAPS[2]:
        return list(rows[1:]) + list(rows[:1])
    raise ReadError(f"登録されていない入れ替え方: {how or '空欄'}")


def _rows_of(text: str, columns: tuple[str, ...], what: str):
    reader = csv.DictReader(text.splitlines())
    lack = [c for c in columns if c not in tuple(reader.fieldnames or ())]
    if lack:
        raise ReadError(f"{what}に " + " / ".join(lack) + " の列が無い")
    for i, raw in enumerate(reader, start=2):
        yield i, {k: (raw.get(k) or "").strip() for k in columns}


# ------------------------------------------------------------ 正規化と写し


def normalize(text: str) -> str:
    """決めた 3 つだけ。**字下げ・コメント・識別子・引用符には触らない。**"""
    body = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.rstrip(" \t") for ln in body.split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


@dataclass(frozen=True)
class Copy:
    """写し 1 本。**中身は出力に出さず、指紋と行数と違う行の番号だけを外へ出す。**"""
    raw: bytes
    text: str

    @property
    def raw_sha(self) -> str:
        return hashlib.sha256(self.raw).hexdigest()

    @property
    def norm(self) -> str:
        return normalize(self.text)

    @property
    def norm_sha(self) -> str:
        return hashlib.sha256(self.norm.encode("utf-8")).hexdigest()

    @property
    def lines(self) -> tuple[str, ...]:
        return tuple(self.norm.split("\n")) if self.norm else ()


class Copies:
    """写しの置き場。**置き場の外は読まない。通信の経路を持たない。**"""

    def __init__(self, root: Path, items: dict[str, Copy]) -> None:
        self.root = root
        self.items = dict(items)

    @property
    def path(self) -> str:
        return str(self.root)

    @classmethod
    def load(cls, root: str | Path, relpaths: tuple[str, ...]) -> Copies:
        base = Path(root)
        if not base.is_dir():
            raise ReadError(f"写しの置き場が無い: {base}")
        items: dict[str, Copy] = {}
        for rel in sorted({r for r in relpaths if r}):
            p = Path(rel)
            if p.is_absolute() or ".." in p.parts:
                raise ReadError(f"写しの置き場の外を指している: {rel}")
            q = base / p
            if not q.is_file():
                raise ReadError(f"写しのファイルが置き場に無い: {rel}")
            raw = q.read_bytes()
            try:
                items[rel] = Copy(raw, raw.decode("utf-8"))
            except UnicodeDecodeError as e:
                raise ReadError(f"写しを utf-8 として読めない: {rel}({e.reason})")
        return cls(base, items)

    def of(self, rel: str) -> Copy:
        return self.items[rel]

    def patched(self, rel: str, text: str) -> Copies:
        """写し 1 本を替えた写しを **メモリの中だけ** に作る(入力は書き換えない)。"""
        items = dict(self.items)
        items[rel] = Copy(text.encode("utf-8"), text)
        return Copies(self.root, items)


# ------------------------------------------------------------ 注記記号の登録表


@dataclass(frozen=True)
class Note:
    """注記記号 1 つ。**その注記が何を要求するかは人が書いた宣言。**"""
    note: str
    means: str
    requires: str
    source: str


class Notes:
    def __init__(self, items: list[Note], path: str = "") -> None:
        self.items = list(items)
        self.path = path
        self.pending: list[Pending] = []
        for n in items:
            if not n.source:
                self.pending.append(Pending(STOP_REASONS[0],
                                            f"注記記号の登録表 {n.note}"))

    @classmethod
    def parse(cls, text: str, path: str = "") -> Notes:
        items: list[Note] = []
        for i, r in _rows_of(text, NOTE_COLUMNS, "注記記号の登録表"):
            where = f"注記記号の登録表 {i} 行目"
            if bad_id(r["note"]):
                raise ReadError(f"{where}: 記号が空か区切り文字を含む"
                                f"({r['note'] or '空欄'})")
            if r["requires"] not in REQUIRES:
                raise ReadError(f"{where}: 要求する欄が登録の外"
                                f"({r['requires'] or '空欄'})")
            items.append(Note(r["note"], r["means"], r["requires"], r["source"]))
        if not items:
            raise ReadError("注記記号の登録表に行が無い")
        return cls(items, path)

    @classmethod
    def load(cls, path: str | Path) -> Notes:
        p = Path(path)
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @property
    def ordered(self) -> list[Note]:
        return sorted(self.items, key=lambda n: n.note)

    def of(self, note: str) -> Note | None:
        for n in self.items:
            if n.note == note:
                return n
        return None

    def swapped(self, how: str) -> Notes:
        return Notes(swap_rows(self.items, how), self.path)

    def issues(self) -> list[Pending]:
        out: list[Pending] = []
        seen: dict[str, int] = {}
        for n in self.items:
            seen[n.note] = seen.get(n.note, 0) + 1
        for note, k in sorted(seen.items()):
            if k > 1:
                out.append(Pending(STOP_REASONS[4], f"{note} が {k} 行"))
        return out


# ------------------------------------------------------------ 部品の台帳


@dataclass(frozen=True)
class Part:
    """部品 1 つ。**declared は生の文字列で、整数に直す経路が無い。**"""
    part_id: str
    what: str
    declared: str
    industry: str
    unified: str
    source: str


class Parts:
    def __init__(self, items: list[Part], path: str = "") -> None:
        self.items = list(items)
        self.path = path
        self.pending: list[Pending] = []
        for p in items:
            if not p.source:
                self.pending.append(Pending(STOP_REASONS[0], f"部品の台帳 {p.part_id}"))

    @classmethod
    def parse(cls, text: str, path: str = "") -> Parts:
        items: list[Part] = []
        for i, r in _rows_of(text, PART_COLUMNS, "部品の台帳"):
            where = f"部品の台帳 {i} 行目"
            if bad_id(r["part_id"]):
                raise ReadError(f"{where}: 部品 id が空か区切り文字を含む"
                                f"({r['part_id'] or '空欄'})")
            if r["industry"] not in INDUSTRY:
                raise ReadError(f"{where}: 業種依存の記号が登録の外"
                                f"({r['industry'] or '空欄'})")
            if r["unified"] not in UNIFIED:
                raise ReadError(f"{where}: 統一の宣言記号が登録の外"
                                f"({r['unified'] or '空欄'})")
            items.append(Part(r["part_id"], r["what"], r["declared"], r["industry"],
                              r["unified"], r["source"]))
        if not items:
            raise ReadError("部品の台帳に行が無い")
        return cls(items, path)

    @classmethod
    def load(cls, path: str | Path) -> Parts:
        p = Path(path)
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @property
    def ordered(self) -> list[Part]:
        return sorted(self.items, key=lambda p: p.part_id)

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(p.part_id for p in self.ordered)

    def of(self, part_id: str) -> Part | None:
        for p in self.items:
            if p.part_id == part_id:
                return p
        return None

    def swapped(self, how: str) -> Parts:
        return Parts(swap_rows(self.items, how), self.path)

    def issues(self) -> list[Pending]:
        out: list[Pending] = []
        seen: dict[str, int] = {}
        for p in self.items:
            seen[p.part_id] = seen.get(p.part_id, 0) + 1
        for part_id, k in sorted(seen.items()):
            if k > 1:
                out.append(Pending(STOP_REASONS[1], f"{part_id} が {k} 行"))
        return out


# ------------------------------------------------------------ 箇所の台帳


@dataclass(frozen=True)
class Site:
    """箇所 1 つ。**写しの置き場所は持つが、出力には箇所 id しか出さない。**"""
    site_id: str
    part_id: str
    copy: str
    note: str
    declared_lines: str
    source: str


class Sites:
    def __init__(self, items: list[Site], path: str = "") -> None:
        self.items = list(items)
        self.path = path
        self.pending: list[Pending] = []

    @classmethod
    def parse(cls, text: str, path: str = "") -> Sites:
        items: list[Site] = []
        for i, r in _rows_of(text, SITE_COLUMNS, "箇所の台帳"):
            where = f"箇所の台帳 {i} 行目"
            for key, what in (("site_id", "箇所 id"), ("part_id", "部品 id")):
                if bad_id(r[key]):
                    raise ReadError(f"{where}: {what} が空か区切り文字を含む"
                                    f"({r[key] or '空欄'})")
            items.append(Site(r["site_id"], r["part_id"], r["copy"], r["note"],
                              r["declared_lines"], r["source"]))
        if not items:
            raise ReadError("箇所の台帳に行が無い")
        return cls(items, path)

    @classmethod
    def load(cls, path: str | Path) -> Sites:
        p = Path(path)
        return cls.parse(p.read_text(encoding="utf-8-sig"), str(p.resolve()))

    @property
    def ordered(self) -> list[Site]:
        return sorted(self.items, key=lambda s: s.site_id)

    @property
    def copies(self) -> tuple[str, ...]:
        return tuple(s.copy for s in self.ordered if s.copy)

    def of_part(self, part_id: str) -> list[Site]:
        return [s for s in self.ordered if s.part_id == part_id]

    def swapped(self, how: str) -> Sites:
        return Sites(swap_rows(self.items, how), self.path)

    def issues(self, parts: Parts) -> list[Pending]:
        out: list[Pending] = []
        seen: dict[str, int] = {}
        for s in self.items:
            seen[s.site_id] = seen.get(s.site_id, 0) + 1
        for site_id, k in sorted(seen.items()):
            if k > 1:
                out.append(Pending(STOP_REASONS[2], f"{site_id} が {k} 行"))
        for s in self.ordered:
            if parts.of(s.part_id) is None:
                out.append(Pending(STOP_REASONS[3], f"{s.site_id} → {s.part_id}"))
        for part_id in parts.ids:
            here: dict[str, list[str]] = {}
            for s in self.of_part(part_id):
                if s.copy:
                    here.setdefault(s.copy, []).append(s.site_id)
            for ids in here.values():
                if len(ids) > 1:
                    out.append(Pending(STOP_REASONS[5],
                                       f"{part_id} の {' / '.join(sorted(ids))}"))
        return out


# ------------------------------------------------------------ 2 箇所の組


@dataclass(frozen=True)
class Pair:
    """2 箇所の組 1 つ。**まとめてよいかも、どちらが正本かも持たない。**"""
    part_id: str
    a: str
    b: str
    grade: str
    notes: tuple[str, str]
    lines: tuple[int, int] = (0, 0)
    diff_lines: tuple[int, ...] = ()
    sources: tuple[str, ...] = ()

    @property
    def name(self) -> str:
        return f"{self.part_id}:{self.a}>{self.b}"

    @property
    def note_key(self) -> str:
        return " / ".join(sorted(self.notes))

    @property
    def graded(self) -> bool:
        return self.grade in DAN

    def line(self) -> str:
        return (f"{self.name}:{self.grade}:{self.note_key}"
                f":{self.lines[0]}/{self.lines[1]}"
                f":{','.join(str(n) for n in self.diff_lines)}")

    def as_dict(self) -> dict[str, object]:
        out: dict[str, object] = {
            "部品": self.part_id, "箇所の組": [self.a, self.b], "段": self.grade,
            "注記の組": list(self.notes), "出典": list(self.sources)}
        if self.graded:
            out["行数の組"] = list(self.lines)
        if self.grade == DAN[2]:
            out["違う行の番号"] = list(self.diff_lines)
        return out


def grade(part_id: str, sa: Site, sb: Site, notes: Notes, copies: Copies) -> Pair:
    """2 箇所の組 1 つを 4 段 + 別枠 4 のどれか 1 つへ入れる。

    上から順に見る。どちらかの出典が空なら、そこで終わり(別枠)。注記記号が登録表に無ければ
    終わり。その注記が要求する欄が空なら終わり。写しが渡されていなければ終わり。そこを抜けて
    から、はじめて **写しの文字だけ** を比べる。**注記が何と書いてあっても、段は文字の一致で
    決まる**(`指紋一致と注記` を (A) に読み替える経路が無い)。
    """
    pair = (sa.note, sb.note)
    both = (sa, sb)
    if not sa.source or not sb.source:
        return Pair(part_id, sa.site_id, sb.site_id, BETSUWAKU[0], pair,
                    sources=tuple(s.source or "(空欄)" for s in both))
    if any(notes.of(s.note) is None for s in both):
        return Pair(part_id, sa.site_id, sb.site_id, BETSUWAKU[1], pair,
                    sources=tuple(s.source for s in both))
    for s in both:
        req = notes.of(s.note).requires
        if (req == REQUIRES[1] and not s.copy) or (req == REQUIRES[2]
                                                   and not s.declared_lines):
            return Pair(part_id, sa.site_id, sb.site_id, BETSUWAKU[2], pair,
                        sources=tuple(x.source for x in both))
    if not sa.copy or not sb.copy:
        return Pair(part_id, sa.site_id, sb.site_id, BETSUWAKU[3], pair,
                    sources=tuple(s.source for s in both))
    ca, cb = copies.of(sa.copy), copies.of(sb.copy)
    n = (len(ca.lines), len(cb.lines))
    src = (sa.source, sb.source)
    if ca.raw_sha == cb.raw_sha:
        return Pair(part_id, sa.site_id, sb.site_id, DAN[0], pair, n, (), src)
    if ca.norm_sha == cb.norm_sha:
        return Pair(part_id, sa.site_id, sb.site_id, DAN[1], pair, n, (), src)
    if n[0] == n[1]:
        diff = tuple(k + 1 for k, (x, y) in enumerate(zip(ca.lines, cb.lines))
                     if x != y)
        return Pair(part_id, sa.site_id, sb.site_id, DAN[2], pair, n, diff, src)
    return Pair(part_id, sa.site_id, sb.site_id, DAN[3], pair, n, (), src)


# ------------------------------------------------------------ 台帳


@dataclass(frozen=True)
class Report:
    ok: bool
    pending: tuple[Pending, ...]
    parts: int
    sites: int
    notes: int
    copies: int


@dataclass(frozen=True)
class Table:
    report: Report
    pairs: tuple[Pair, ...]
    parts: Parts
    sites: Sites
    notes: Notes
    copies: Copies

    # ---------------- 分母

    def part_denominator(self) -> int:
        return self.report.parts

    def site_denominator(self) -> int:
        return self.report.sites

    def handed_denominator(self) -> int:
        return len(self.sites.copies)

    def pair_denominator(self) -> int:
        return len(self.pairs)

    # ---------------- 件数

    def four(self) -> dict[str, int]:
        return {k: sum(1 for p in self.pairs if p.grade == k) for k in DAN}

    def extras(self) -> dict[str, int]:
        return {k: sum(1 for p in self.pairs if p.grade == k) for k in BETSUWAKU}

    def by_part(self) -> list[dict[str, object]]:
        """部品ごとの内訳(**合計が全組に戻るのが検算**)。"""
        out: list[dict[str, object]] = []
        for part in self.parts.ordered:
            here = [p for p in self.pairs if p.part_id == part.part_id]
            sites = self.sites.of_part(part.part_id)
            out.append({"部品": part.part_id, "内容": part.what,
                        "宣言されている箇所数の文字列": part.declared or "(空欄)",
                        "箇所の台帳に在る箇所の件数": len(sites),
                        "写しが渡された箇所の件数": sum(1 for s in sites if s.copy),
                        "業種依存": part.industry, "統一の宣言": part.unified,
                        "4 段": {k: sum(1 for p in here if p.grade == k) for k in DAN},
                        "別枠": {k: sum(1 for p in here if p.grade == k)
                                 for k in BETSUWAKU},
                        "組の件数": len(here), "出典": part.source})
        return out

    def by_note(self) -> list[dict[str, object]]:
        """注記の組ごとの内訳(**注記と段を別の列で並べる。合計が 2 つめの検算**)。"""
        out: list[dict[str, object]] = []
        for key in sorted({p.note_key for p in self.pairs}):
            here = [p for p in self.pairs if p.note_key == key]
            out.append({"注記の組": key, "組の件数": len(here),
                        "4 段": {k: sum(1 for p in here if p.grade == k) for k in DAN},
                        "別枠": {k: sum(1 for p in here if p.grade == k)
                                 for k in BETSUWAKU}})
        return out

    def declared_vs_handed(self) -> list[dict[str, object]]:
        """宣言されている箇所数の文字列と、写しが渡された箇所の件数を並べる。

        **一方をもう一方の代わりに使わせない**(`8+` や `18 ファイル` を整数に直す経路が無い)。
        """
        out: list[dict[str, object]] = []
        for part in self.parts.ordered:
            sites = self.sites.of_part(part.part_id)
            out.append({"部品": part.part_id,
                        "宣言されている箇所数の文字列": part.declared or "(空欄)",
                        "箇所の台帳に在る箇所の件数": len(sites),
                        "写しが渡された箇所の件数": sum(1 for s in sites if s.copy),
                        "統一の宣言": part.unified, "出典": part.source})
        return out

    def partless_notes(self) -> list[dict[str, str]]:
        """どの箇所も使っていない注記記号の登録(**黙って落とさずに並べる**)。"""
        used = {s.note for s in self.sites.ordered}
        return [{"注記記号": n.note, "意味": n.means, "要求する欄": n.requires,
                 "出典": n.source} for n in self.notes.ordered if n.note not in used]

    def siteless_parts(self) -> list[dict[str, str]]:
        """箇所の台帳に 1 行も無い部品(**止めずに並べる**)。"""
        return [{"部品": p.part_id, "内容": p.what,
                 "宣言されている箇所数の文字列": p.declared or "(空欄)",
                 "統一の宣言": p.unified, "出典": p.source}
                for p in self.parts.ordered if not self.sites.of_part(p.part_id)]

    def note_rows(self) -> list[dict[str, str]]:
        """注記記号の登録表の写し(**「何を要求するか」が表の側に在ることを出力でも示す**)。"""
        return [{"注記記号": n.note, "意味": n.means, "要求する欄": n.requires,
                 "出典": n.source} for n in self.notes.ordered]

    def listed(self) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for k in DAN + BETSUWAKU:
            here = [p for p in self.pairs if p.grade == k]
            out.append({"段": k, "件数": len(here),
                        "組": [p.as_dict() for p in here]})
        return out

    def stopped(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for p in self.report.pending:
            out[p.reason] = out.get(p.reason, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: STOP_REASONS.index(kv[0])))

    # ---------------- まとめ

    def counts(self) -> dict[str, object]:
        """件数を、分母の内訳つきで出す。**統合の可否も似ている度合いも返さない。**"""
        four, extras = self.four(), self.extras()
        out: dict[str, object] = {
            "部品の台帳の行数": self.report.parts,
            "箇所の台帳の行数": self.report.sites,
            "注記記号の登録表の行数": self.report.notes,
            "写しのファイルの本数": self.report.copies,
            "分母(部品の件数)": self.part_denominator(),
            "分母(箇所の件数)": self.site_denominator(),
            "分母(写しが渡された箇所の件数)": self.handed_denominator(),
            "分母(2 箇所の組の件数)": self.pair_denominator(),
            "4 段": four,
            "別枠": extras,
            "決めた正規化": list(NORMALIZE),
            "部品ごと": self.by_part(),
            "注記の組ごと": self.by_note(),
            "宣言されている箇所数の文字列と写しの件数": self.declared_vs_handed(),
            "注記記号の登録表": self.note_rows(),
            "箇所が 1 行も無い部品": len(self.siteless_parts()),
            "どの箇所も使っていない注記記号の登録": len(self.partless_notes()),
            "理由別の止まった件数": self.stopped(),
            "読んだか": ("読んだ" if self.pairs else
                         "読んでいない(組を作る前に止まったので 4 段は全て 0)"),
        }
        out["分母に含めたもの"] = (
            f"部品 {self.part_denominator()} 件 / 箇所 {self.site_denominator()} 件"
            f"(写しが渡されたのは {self.handed_denominator()} 件)/ 同じ部品の 2 箇所の組 "
            f"{self.pair_denominator()} 件。内訳は "
            + " + ".join(f"{k} {four[k]}" for k in DAN)
            + " + " + " + ".join(f"{k} {extras[k]}" for k in BETSUWAKU))
        out["件数の合計の検算"] = (
            f"4 段 + 別枠 の合計 {sum(four.values()) + sum(extras.values())} / "
            f"組の件数 {self.pair_denominator()}(部品ごとの内訳の合計 "
            f"{sum(int(r['組の件数']) for r in self.by_part())}、"
            f"注記の組ごとの内訳の合計 "
            f"{sum(int(r['組の件数']) for r in self.by_note())} も同じ)")
        out["まとめてよいかを決めない"] = (
            "統合の可否・順序・優先度・どの箇所が正本かを出す列が無い。終了コード 0 も"
            "「まとめてよい」ではなく「渡された写しが全部そのままで同一だった」の意味")
        out["写しの中身を出力に出さない"] = (
            "出すのは段・行番号・件数・箇所 id だけ。入力の文字を出力へ貼る経路が無い"
            "(= 読んだコードそのものが公開物へ流れない物理形)")
        out["名前を出力に出さない"] = (
            "ファイル名・パス・道具名の列を持たず、箇所 id だけで返す")
        out["振る舞いが同じかを見ない"] = (
            "実行しない・import しない・構文解析しない・テストを走らせない。"
            "段は文字の一致で、同じ結果を返すかは分からない")
        out["似ている度合いを出さない"] = (
            "類似度・距離・一致率・割合を出す列が無く、段はちょうど一致の階段 4 つだけ")
        out["注記を段の代わりに使わない"] = (
            "`指紋一致と注記` が在っても写しが一致しなければ (A) に入れる経路が無い。"
            "注記と段は別の列で並ぶ")
        out["宣言されている箇所数を整数に直さない"] = (
            "`8+` や `18 ファイル` のような生の文字列をそのまま持ち、整数に直す経路が無い。"
            "写しが渡された箇所の件数とは別の列に並べる")
        out["テストの有無を段に混ぜない"] = (
            "検証が在るか / 走らせた結果がどうかの列を持たない(別の部品の領分)")
        out["写しを取りに行かない"] = (
            "通信の経路が無く、置き場の外(絶対パス・`..`)を指す行は読まずに止まる")
        out["正規化は 3 つだけ"] = (
            " / ".join(NORMALIZE) + "。字下げを揃えない・コメントを外さない・"
            "識別子を揃えない・引用符を揃えない(増やす引数が無い)")
        out["時計を読まない"] = (
            "入力に日付の列も時刻の列も無く、現在時刻を読む呼び出しも持たない")
        out["入力を書き換えない"] = (
            "verify が作る写し(行末に空白を足した写し・1 行足した写し)はメモリの中だけで、"
            "置き場のファイルにも 3 枚の CSV にも 1 文字も書かない")
        return out

    def judgement_bytes(self) -> bytes:
        """判定部分 = 組ごとの段と行番号。時刻・絶対パス・ファイル名は入れない。"""
        self._guard()
        lines = ["\t".join(["件", str(self.report.parts), str(self.report.sites),
                            str(self.report.notes), str(self.report.copies),
                            str(self.handed_denominator())])]
        lines.extend(p.line() for p in self.pairs)
        four = self.four()
        lines.append("\t".join(["段"] + [str(four[k]) for k in DAN]))
        return ("\n".join(lines) + "\n").encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.judgement_bytes()).hexdigest()

    def read_condition(self) -> dict[str, str]:
        return dict(zip(SCOPE_KEYS, (self.parts.path, self.sites.path,
                                     self.notes.path, self.copies.path)))

    def _guard(self) -> None:
        if not self.report.ok:
            raise RuntimeError("止まっているので作った組は無い。"
                               "report.pending の理由コードを見る")


def copy_grade(parts: Parts, sites: Sites, notes: Notes, copies: Copies) -> Table:
    """同じ部品の 2 箇所の組ごとに 4 段 + 別枠 4 のどれか 1 つを付ける。

    3 枚のどれかが 1 行でも壊れていたら 1 組も数えない(4 段は全て 0)。
    """
    pending = list(parts.pending) + list(sites.pending) + list(notes.pending)
    pending.extend(notes.issues())
    pending.extend(parts.issues())
    pending.extend(sites.issues(parts))
    report = Report(not pending, tuple(pending), len(parts.items), len(sites.items),
                    len(notes.items), len(copies.items))
    if pending:                 # 1 組も数えずに止まる
        return Table(report, (), parts, sites, notes, copies)
    pairs: list[Pair] = []
    for part_id in parts.ids:
        here = sites.of_part(part_id)
        for i in range(len(here)):
            for j in range(i + 1, len(here)):
                pairs.append(grade(part_id, here[i], here[j], notes, copies))
    return Table(report, tuple(pairs), parts, sites, notes, copies)


# ------------------------------------------------------------ verify


def moved(first: Table, after: Table) -> list[str]:
    """段か行番号が動いた組の名前。"""
    before = {p.name: p.line() for p in first.pairs}
    now = {p.name: p.line() for p in after.pairs}
    return sorted(k for k in before if before[k] != now.get(k, ""))


def space_probe_plan(first: Table) -> tuple[str, str, str] | None:
    """行末に空白を 1 つ足す写しを決める = (A) の組をちょうど 1 件持つ最初の箇所。"""
    for p in first.pairs:
        if p.grade != DAN[0]:
            continue
        for site_id in (p.a, p.b):
            same = [q for q in first.pairs if q.grade == DAN[0]
                    and site_id in (q.a, q.b)]
            if len(same) == 1:
                site = next(s for s in first.sites.ordered if s.site_id == site_id)
                return site_id, site.copy, p.name
    return None


def space_probe(parts: Parts, sites: Sites, notes: Notes, copies: Copies,
                first: Table) -> dict[str, object]:
    """**1 件の写しの行末に空白を 1 つ足すと、その組だけが (A) → (B) へ移る。**

    正規化が行末の空白を落とすので、正規化後の指紋は動かない = 動くのは (A) の組だけ。
    別枠の件数も (C)(D) の件数も動かないのが、段が階段になっていることの物理形。
    """
    plan = space_probe_plan(first)
    if plan is None:
        return {"合うか": True, "観測": "(A) の組をちょうど 1 件持つ箇所が無いので見ない"}
    site_id, rel, pair_name = plan
    patched = copies.patched(rel, copies.of(rel).text + " ")
    after = copy_grade(parts, sites, notes, patched)
    if not after.report.ok:
        return {"合うか": False, "観測": "写しを替えたら止まった"}
    moved_pairs = moved(first, after)
    changed = next((p for p in after.pairs if p.name == pair_name), None)
    ok = (moved_pairs == [pair_name] and changed is not None
          and changed.grade == DAN[1] and after.extras() == first.extras())
    return {"合うか": ok, "替えた箇所": site_id, "替え方": "行末に空白を 1 つ足す",
            "動くはずだった組": pair_name, "動いた組": moved_pairs,
            "(A)(前)": first.four()[DAN[0]], "(A)(後)": after.four()[DAN[0]],
            "(B)(前)": first.four()[DAN[1]], "(B)(後)": after.four()[DAN[1]],
            "別枠(前)": first.extras(), "別枠(後)": after.extras(),
            "写しはメモリの中だけ": True}


def line_probe_plan(first: Table) -> tuple[str, str, tuple[str, ...]] | None:
    """1 行足す写しを決める = 箇所が 2 件だけで両方に写しが在り、組が (D) でない最初の部品。"""
    for part_id in first.parts.ids:
        here = first.sites.of_part(part_id)
        if len(here) != 2 or not all(s.copy for s in here):
            continue
        pair = next((p for p in first.pairs if p.part_id == part_id), None)
        if pair is None or pair.grade not in (DAN[0], DAN[1], DAN[2]):
            continue
        return here[0].site_id, here[0].copy, (pair.name,)
    return None


def line_probe(parts: Parts, sites: Sites, notes: Notes, copies: Copies,
               first: Table) -> dict[str, object]:
    """**1 件の写しに空行でない 1 行を足すと、その写しを含む組が (D) へ移る。**

    行数が変わるので、段は行数の階段の一番下へ落ち、行数の組がそのまま出る。
    他の組と別枠の件数は動かない。
    """
    plan = line_probe_plan(first)
    if plan is None:
        return {"合うか": True, "観測": "箇所が 2 件だけの部品が無いので見ない"}
    site_id, rel, want = plan
    text = copies.of(rel).text
    patched = copies.patched(rel, text + ("" if text.endswith("\n") else "\n")
                             + "# 足した 1 行\n")
    after = copy_grade(parts, sites, notes, patched)
    if not after.report.ok:
        return {"合うか": False, "観測": "写しを替えたら止まった"}
    moved_pairs = moved(first, after)
    changed = [p for p in after.pairs if p.name in want]
    ok = (moved_pairs == sorted(want) and bool(changed)
          and all(p.grade == DAN[3] and p.lines[0] != p.lines[1] for p in changed)
          and after.extras() == first.extras())
    return {"合うか": ok, "替えた箇所": site_id, "替え方": "空行でない 1 行を足す",
            "動くはずだった組": sorted(want), "動いた組": moved_pairs,
            "行数の組(後)": [list(p.lines) for p in changed],
            "(D)(前)": first.four()[DAN[3]], "(D)(後)": after.four()[DAN[3]],
            "別枠(前)": first.extras(), "別枠(後)": after.extras(),
            "写しはメモリの中だけ": True}


def verify(parts: Parts, sites: Sites, notes: Notes,
           copies: Copies) -> dict[str, object]:
    """5 つ見る。二度走りの sha256 / 3 枚の行順の入れ替え / 件数の検算 /
    行末に空白を足した写し / 1 行足した写し。"""
    first = copy_grade(parts, sites, notes, copies)
    if not first.report.ok:
        return {"ok": False, "stage": "止まった(作った組は返さない)", **first.counts(),
                "pending": [p.as_dict() for p in first.report.pending]}
    second = copy_grade(parts, sites, notes, copies)
    pending: list[Pending] = []
    if first.sha256() != second.sha256():
        pending.append(Pending(STOP_REASONS[7], f"2 回目 {second.sha256()[:12]}"))
    swapped: dict[str, str] = {}
    for how in SWAPS:
        third = copy_grade(parts.swapped(how), sites.swapped(how),
                           notes.swapped(how), copies)
        swapped[how] = third.sha256() if third.report.ok else ""
        if not (third.report.ok and first.sha256() == third.sha256()):
            pending.append(Pending(STOP_REASONS[8],
                                   f"入れ替え方 {how} で {swapped[how] or '止まった'}"))
    four, extras = first.four(), first.extras()
    total = sum(four.values()) + sum(extras.values())
    if total != first.pair_denominator():
        pending.append(Pending(STOP_REASONS[6],
                               f"4 段 + 別枠 の合計 {total} / 組の件数 "
                               f"{first.pair_denominator()}"))
    for what, rows in (("部品ごと", first.by_part()),
                       ("注記の組ごと", first.by_note())):
        got = sum(int(r["組の件数"]) for r in rows)
        if got != first.pair_denominator():
            pending.append(Pending(STOP_REASONS[6],
                                   f"{what}の内訳の合計 {got} / 組の件数 "
                                   f"{first.pair_denominator()}"))
    out: dict[str, object] = {
        "ok": not pending, "読んだ回数": 2, "入れ替え方": list(SWAPS),
        "sha256": first.sha256(), "2 回目の sha256": second.sha256(),
        "入れ替えた 3 枚の sha256": swapped,
        "件数の検算": {"4 段": four, "別枠": extras, "合計": total,
                       "部品ごとの内訳の合計":
                           sum(int(r["組の件数"]) for r in first.by_part()),
                       "注記の組ごとの内訳の合計":
                           sum(int(r["組の件数"]) for r in first.by_note()),
                       "分母(部品の件数)": first.part_denominator(),
                       "分母(箇所の件数)": first.site_denominator(),
                       "分母(写しが渡された箇所の件数)": first.handed_denominator(),
                       "分母(2 箇所の組の件数)": first.pair_denominator()},
        "行末に空白を足した写し": space_probe(parts, sites, notes, copies, first),
        "1 行足した写し": line_probe(parts, sites, notes, copies, first),
    }
    for key in ("行末に空白を足した写し", "1 行足した写し"):
        if not out[key]["合うか"]:        # type: ignore[index]
            pending.append(Pending(STOP_REASONS[6], f"{key} の件数が合わない"))
            out["ok"] = False
    if pending:
        out["観測"] = ("同じ 3 枚と同じ写しから違うバイト列が出た、または件数が合わない"
                       "(平均も多数決もしない。まとめてよいかも当てない)")
        out["pending"] = [p.as_dict() for p in pending]
    return out


# ------------------------------------------------------------ ひな型

T_PART = "合成の棚卸しのメモ(架空)L1"
T_SITE = "合成の箇所のメモ(架空)L1"
T_NOTE = "合成の注記の登録のメモ(架空)L1"

TEMPLATE_PARTS = [
    list(PART_COLUMNS),
    ["P1", "CSV の文字コードの判定", "17", INDUSTRY[0], UNIFIED[2], T_PART],
    ["P2", "氏名の正規化", "8+", INDUSTRY[0], UNIFIED[2], T_PART],
]
TEMPLATE_SITES = [
    list(SITE_COLUMNS),
    ["S01", "P1", "S01.txt", "注記なし", NO_MARK, T_SITE],
    ["S02", "P1", "S02.txt", "注記なし", NO_MARK, T_SITE],
    ["S03", "P2", "", "注記なし", NO_MARK, T_SITE],
]
TEMPLATE_NOTES = [
    list(NOTE_COLUMNS),
    ["指紋一致と注記", "機械が出した指紋が一致すると書かれている", REQUIRES[1], T_NOTE],
    ["同型と注記", "人が見て同じ形だと書かれている", REQUIRES[1], T_NOTE],
    ["派生と注記", "行数の違う派生だと書かれている", REQUIRES[2], T_NOTE],
    ["散在と注記のみ", "散在とだけ書かれ、何か所が同じ実装かは数えていない",
     REQUIRES[0], T_NOTE],
    ["注記なし", "同じだと言える根拠が書かれていない", REQUIRES[0], T_NOTE],
]
TEMPLATE_COPIES = {
    "S01.txt": 'def read_text(path):\n    return path.read_bytes().decode("cp932")\n',
    "S02.txt": 'def read_text(path):\n    return path.read_bytes().decode("cp932")\n',
}


def write_csv(path: Path, rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    return path


def init(dest: str | Path) -> tuple[Path, ...]:
    d = Path(dest)
    out = [write_csv(d / "部品の台帳.csv", TEMPLATE_PARTS),
           write_csv(d / "箇所の台帳.csv", TEMPLATE_SITES),
           write_csv(d / "注記記号の登録表.csv", TEMPLATE_NOTES)]
    box = d / "写しの置き場"
    box.mkdir(parents=True, exist_ok=True)
    for name, body in sorted(TEMPLATE_COPIES.items()):
        (box / name).write_text(body, encoding="utf-8", newline="")
        out.append(box / name)
    return tuple(out)


# ------------------------------------------------------------ CLI

def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def build_parser() -> argparse.ArgumentParser:
    """CLI は pairs / check / verify / init の 4 つで、option は -h 以外に 1 つも無い。"""
    ap = argparse.ArgumentParser(prog="copy_grade",
                                 description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in SUBCOMMANDS[:3]:
        p = sub.add_parser(name)
        for arg in ("parts", "sites", "notes", "box"):
            p.add_argument(arg)
    sub.add_parser(SUBCOMMANDS[3]).add_argument("dest")
    return ap


def load_four(a) -> tuple[Parts, Sites, Notes, Copies]:
    parts, sites = Parts.load(a.parts), Sites.load(a.sites)
    notes = Notes.load(a.notes)
    return parts, sites, notes, Copies.load(a.box, sites.copies)


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == "init":
        print("書いた: " + " / ".join(str(p) for p in init(a.dest)))
        return 0
    try:
        four = load_four(a)
        if a.cmd == "verify":
            out = verify(*four)
            _print(out)
            return 0 if out["ok"] else 3
        t = copy_grade(*four)
    except ReadError as e:
        print(f"表として読めない: {e}", file=sys.stderr)
        return 2
    if not t.report.ok:
        _print({"ok": False, "stage": "止まった(作った組は返さない)", **t.counts(),
                "pending": [p.as_dict() for p in t.report.pending]})
        return 3
    body: dict[str, object] = {"ok": True, **t.counts()}
    if a.cmd == SUBCOMMANDS[0]:
        body["段ごとの一覧"] = t.listed()
        body["箇所が 1 行も無い部品の一覧"] = t.siteless_parts()
        body["どの箇所も使っていない注記記号の登録の一覧"] = t.partless_notes()
        body["sha256"] = t.sha256()
        body["読んだ条件"] = t.read_condition()
    _print(body)
    clean = (not sum(t.extras().values()) and not t.stopped()
             and not sum(t.four()[k] for k in DAN[1:]))
    return 0 if clean else 3


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
