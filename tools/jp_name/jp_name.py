"""jp_name — 氏名を決定論で寄せて照合キーを作り、同一人物かどうかの判断は人に返す部品。

氏名の突合を「似ているから同じ人」で自動的に寄せると、間違いが静かに混ざる。この道具は
機械にできるところ(表記を決定論で寄せてキーを作る)までを引き受け、そこから先(このキーの
一致が同一人物を意味するか)は理由コードを付けて人に返す。類似度のしきい値で同一人物と
決めることはしない。しきい値は一切持たない。

流れ(固定。変えない):
  1. 表記の正規化   NFKC(全角 → 半角、半角カナ → 全角カナ)/ 空白と区切りを除く
  2. 異体字の同値化 同値表(VARIANT_GROUPS)で代表字に畳む / ひらがな → カタカナ
  3. キー照合       相手側の索引を引く。ヒット数で決める
  4. 判断待ち       0 件 / 2 件以上 / 自分側にも重複 / 対象外表記 は理由コードを付けて人に返す

畳んでよい範囲は VARIANT_GROUPS に書いてあるものだけ。表に無い組(斉 と 斎、井ノ口 と 井之口)は
別のキーになる。表を増やすこと自体が判断なので、増やすときはテストを足す。

stdlib のみ(unicodedata / re)。関数(to_key / match / match_all)と CLI の両方。
CLI: python jp_name.py --key 渡邊太郎 ワタナベタロウ    → 表記 TAB 照合キー
     python jp_name.py A.csv B.csv --column 氏名        → A の各行を B と突合(判断待ちが 1 件でもあれば exit 3)
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from collections.abc import Iterable
from typing import NamedTuple

__all__ = ["VARIANT_GROUPS", "Decision", "OK", "PENDING", "REASONS",
           "normalize", "to_key", "scope_reason", "build_index", "match", "match_all", "main"]

# 同値表。各組の先頭が代表字。「この組は同じ字として畳んでよい」という判断そのものなので、
# 増減させるときはテストを足す。ここに無い組(斉 と 斎、藤 と 籐)は別のキーになる。
VARIANT_GROUPS: tuple[tuple[str, ...], ...] = (
    ("辺", "邊", "邉"),
    ("斉", "齊"),
    ("斎", "齋"),      # 斉 の組とは別。斉藤 と 斎藤 は畳まない
    ("高", "髙"),
    ("崎", "﨑"),
    ("沢", "澤"),
    ("浜", "濱", "濵"),
    ("島", "嶋", "嶌"),
    ("吉", "𠮷"),
    ("富", "冨"),
    ("徳", "德"),
    ("国", "國"),
    ("広", "廣"),
    ("郎", "郞"),
    ("竜", "龍"),
    ("真", "眞"),
    ("恵", "惠"),
    ("瀬", "瀨"),
    ("柳", "栁"),
    ("桧", "檜"),
    ("亀", "龜"),
    ("増", "增"),
)
_VARIANT_MAP = {ord(v): g[0] for g in VARIANT_GROUPS for v in g[1:]}
_KANA_MAP = {c: c + 0x60 for c in range(0x3041, 0x3097)}      # ひらがな → カタカナ

# 空白と区切り。NFKC のあとに残るものだけを並べる(長音 ー U+30FC は残す)
_DROP = re.compile(r"[\s,.、。/\|_\-−–—~〜・:;]+")
_SPLIT = re.compile(r"[\s,.、。/\|_\-−–—~〜・:;]+")
_BRACKET = re.compile(r"[(\[{（【〔][^)\]}）】〕]*[)\]}）】〕]")
_ALIAS_WORD = re.compile(r"旧姓|通称|改姓|前姓|別名")

OK = "照合"
PENDING = "判断待ち"
REASONS: dict[str, str] = {
    "空の氏名": "氏名が空、または記号だけで照合キーが作れない",
    "対象外表記": "旧姓・通称の併記、または 3 語以上(ミドルネーム)。畳まずに人へ返す",
    "相手なし": "同じ照合キーの相手がいない。別表記・未登録・別人のどれかは機械では決まらない",
    "相手が複数": "同じ照合キーの相手が 2 件以上ある(同姓同名の可能性)",
    "自分側が重複": "同じ照合キーの行が自分側にも 2 件以上ある。キーが人を一意に指さない",
}


class Decision(NamedTuple):
    name: str                    # 入力の表記(そのまま)
    key: str                     # 照合キー
    status: str                  # OK(照合)/ PENDING(判断待ち)
    reason: str                  # OK のときは ""。それ以外は REASONS のキー
    candidates: tuple[str, ...]  # 相手側で同じキーだったものの表記

    @property
    def note(self) -> str:
        return REASONS.get(self.reason, "")


def normalize(text: str) -> str:
    """NFKC で全角 → 半角・半角カナ → 全角カナに寄せ、空白と区切りを除く。異体字は畳まない。"""
    if not isinstance(text, str):
        raise TypeError("文字列を渡す")
    return _DROP.sub("", unicodedata.normalize("NFKC", text))


def to_key(text: str) -> str:
    """照合キー。正規化のうえで異体字を代表字に畳み、ひらがなをカタカナに寄せる。

    漢字と読み(カナ)は畳まない。読みを持っていないので、同じ人かどうかを決められないため。
    """
    s = normalize(text)
    return s.translate(_VARIANT_MAP).translate(_KANA_MAP)


def scope_reason(text: str) -> str:
    """この部品が畳まないと決めている表記なら理由コード、そうでなければ ""。"""
    s = unicodedata.normalize("NFKC", text)
    if _ALIAS_WORD.search(s) or _BRACKET.search(s):
        return "対象外表記"
    if len([t for t in _SPLIT.split(s.strip()) if t]) >= 3:
        return "対象外表記"
    if not to_key(text):
        return "空の氏名"
    return ""


def build_index(names: Iterable[str]) -> dict[str, tuple[str, ...]]:
    """照合キー → その表記の一覧。同じキーが 2 件以上なら、そのキーは人を一意に指さない。"""
    idx: dict[str, list[str]] = {}
    for n in names:
        k = to_key(n)
        if k:
            idx.setdefault(k, []).append(n)
    return {k: tuple(v) for k, v in idx.items()}


def match(name: str, index: dict[str, tuple[str, ...]],
          self_index: dict[str, tuple[str, ...]] | None = None) -> Decision:
    """1 件を相手側の索引に当てる。決まるのはキーの一致だけで、同一人物かどうかは決めない。"""
    reason = scope_reason(name)
    key = to_key(name)
    if reason:
        return Decision(name, key, PENDING, reason, ())
    if self_index is not None and len(self_index.get(key, ())) >= 2:
        return Decision(name, key, PENDING, "自分側が重複", self_index[key])
    hits = index.get(key, ())
    if not hits:
        return Decision(name, key, PENDING, "相手なし", ())
    if len(hits) >= 2:
        return Decision(name, key, PENDING, "相手が複数", hits)
    return Decision(name, key, OK, "", hits)


def match_all(left: Iterable[str], right: Iterable[str]) -> list[Decision]:
    """左の名簿の各行を、右の名簿に当てる。左側の同姓同名も判断待ちに落とす。"""
    left = list(left)
    return [match(n, build_index(right), build_index(left)) for n in left]


def _read_column(path: str, column: str) -> list[str]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if rows and column not in rows[0]:
        raise SystemExit(f"列 {column} が {path} に無い(列: {', '.join(rows[0])})")
    return [r[column] for r in rows]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="jp_name", description="氏名を決定論で寄せて照合キーを作り、判断は人に返す")
    ap.add_argument("values", nargs="*", help="--key のときは氏名。そうでなければ CSV 2 つ(左 右)")
    ap.add_argument("--key", action="store_true", help="照合キーだけを表示する")
    ap.add_argument("--column", default="氏名", help="CSV の氏名列(既定: 氏名)")
    a = ap.parse_args(argv)
    if a.key:
        for v in a.values:
            print(f"{v}\t{to_key(v)}")
        return 0
    if len(a.values) != 2:
        ap.error("CSV を 2 つ渡す(左の名簿 右の名簿)。照合キーだけなら --key")
    left, right = _read_column(a.values[0], a.column), _read_column(a.values[1], a.column)
    counts: dict[str, int] = {}
    pending = 0
    for d in match_all(left, right):
        if d.status == OK:
            print(f"{d.name}\t{OK}\t{d.candidates[0]}")
        else:
            pending += 1
            counts[d.reason] = counts.get(d.reason, 0) + 1
            print(f"{d.name}\t{PENDING}\t{d.reason}\t{'|'.join(d.candidates)}")
    summary = ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
    print(f"照合 {len(left) - pending} / 判断待ち {pending}" + (f" ({summary})" if summary else ""), file=sys.stderr)
    return 3 if pending else 0


if __name__ == "__main__":
    raise SystemExit(main())
