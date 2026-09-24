"""jp_corp — 会社名を法人格を捨てずに正規化し、法人番号があればそちらで突き合わせる部品。

会社名の突合を「法人格を取ってから似ている順」で寄せると、別法人が静かに 1 件に畳まれる。
「山田商事株式会社」と「山田商事有限会社」は、法人格を外すとどちらも「山田商事」になる。
この道具は法人格を除去ではなく分離して保持し、照合キーの一部として使う。そのうえで、
公表されている 13 桁の法人番号が列にあれば、名前より先に番号で突き合わせる。
決まらない行は理由コードを付けて人に返す。類似度のしきい値は 1 つも持たない。

流れ(固定。変えない):
  1. 表記の正規化   NFKC(合字 / 全角英数 / 全角カナ)/ 空白と区切りを除く
  2. 法人格の分離   前株・後株・中間のどこにあっても種類として取り出す(捨てない)
  3. 事業所の印     支店・支社・営業所・事業所・出張所・支部で終わるなら印を立てる(屋号からは切らない)
  4. 番号の経路     13 桁の法人番号があれば検査数字を確かめ、通った番号で突合(名前より先)
  5. 名前の経路     照合キー(法人格の種類 + 屋号 + 事業所の印)で相手側の索引を引く
  6. 判断待ち       決まらない行は理由コード付きで人に返す

番号が無い行は名前の経路に回る。名前でも決まらなければ判断待ちになる。

注意(限界): 13 桁の検査数字の算式は、この道具が持っている実装であって、公表されている仕様と
一致することをこの場で確かめたわけではない。テストは同じ算式で作った合成番号でしか通っていない。
実際の番号で使う前に、算式が公表値と合うかを自分で確かめること。

stdlib のみ(unicodedata / re)。関数(parse / to_key / match / match_all)と CLI の両方。
CLI: python jp_corp.py --key 会社名...              → 表記 TAB 法人格 TAB 屋号 TAB 事業所 TAB 照合キー
     python jp_corp.py --check 5835678256246        → 番号 TAB OK / NG(理由)
     python jp_corp.py A.csv B.csv --column 取引先名 --number-column 法人番号
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from collections.abc import Iterable
from typing import NamedTuple

__all__ = ["LEGAL_FORMS", "BRANCH_SUFFIXES", "Corp", "Row", "Index", "Decision",
           "OK", "PENDING", "REASONS", "BY_NUMBER", "BY_NAME",
           "normalize", "parse", "to_key", "number_reason", "check_digit",
           "build_index", "match", "match_all", "main"]

# 法人格の表。各行の先頭が種類の名前、うしろがその種類として認める表記。
# 除去ではなく分離して保持する。捨てると「山田商事株式会社」と「山田商事有限会社」が同じキーになる。
# 丸括弧に入った合字は NFKC で (株) (有) の形になるので、合字そのものはここに並べなくてよい。
LEGAL_FORMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("株式会社", ("株式会社", "(株)")),
    ("有限会社", ("有限会社", "(有)")),
    ("合同会社", ("合同会社", "(同)")),
    ("合資会社", ("合資会社", "(資)")),
    ("合名会社", ("合名会社", "(名)")),
    ("特定非営利活動法人", ("特定非営利活動法人", "NPO法人")),
    ("一般社団法人", ("一般社団法人",)),
    ("一般財団法人", ("一般財団法人",)),
    ("公益社団法人", ("公益社団法人",)),
    ("公益財団法人", ("公益財団法人",)),
    ("医療法人社団", ("医療法人社団",)),
    ("医療法人財団", ("医療法人財団",)),
    ("医療法人", ("医療法人", "(医)")),
    ("社会福祉法人", ("社会福祉法人", "(福)")),
    ("学校法人", ("学校法人", "(学)")),
    ("宗教法人", ("宗教法人", "(宗)")),
    ("独立行政法人", ("独立行政法人",)),
    ("社会保険労務士法人", ("社会保険労務士法人",)),
    ("税理士法人", ("税理士法人",)),
    ("弁護士法人", ("弁護士法人",)),
    ("司法書士法人", ("司法書士法人",)),
    ("行政書士法人", ("行政書士法人",)),
    ("事業協同組合", ("事業協同組合",)),
    ("協同組合", ("協同組合",)),
)
_ALIAS_TO_KIND = {a: k for k, aliases in LEGAL_FORMS for a in aliases}
# 長い表記から先に当てる(医療法人社団 が 医療法人 に食われないように)
_FORM_RE = re.compile("|".join(re.escape(a) for a in sorted(_ALIAS_TO_KIND, key=len, reverse=True)))

# 事業所の印。屋号からは切り離さない(区切りの無い表記では、地名がどこまでかが機械では決まらない)
BRANCH_SUFFIXES: tuple[str, ...] = ("支店", "支社", "営業所", "事業所", "出張所", "支部")

# 空白と区切り。NFKC のあとに残るものだけを並べる(長音と丸括弧は残す)
_DROP = re.compile(r"[\s,、。/\|_\-−–—~〜・:;]+")
_DIGITS = re.compile(r"\D+")

OK = "照合"
PENDING = "判断待ち"
BY_NUMBER = "番号"
BY_NAME = "名前"
REASONS: dict[str, str] = {
    "空の会社名": "法人格を分離すると屋号が残らない(法人格だけ、記号だけ)",
    "番号の検査に落ちる": "13 桁でない、または検査数字が合わない。壊れた番号を名前で救わない",
    "番号が食い違う": "照合キーは一致するが、双方の法人番号が別の番号になっている",
    "法人格が違う": "屋号と事業所の印は同じだが、法人格の種類が違う(別法人の可能性)",
    "相手なし": "同じ照合キーの相手がいない。別表記・未登録・別法人のどれかは機械では決まらない",
    "相手が複数": "同じ照合キーの相手が 2 件以上ある(同じ屋号・同じ法人格の別法人の可能性)",
    "自分側が重複": "同じ照合キーの行が自分側にも 2 件以上ある。キーが 1 社を指さない",
}


class Corp(NamedTuple):
    raw: str        # 入力の表記(そのまま)
    kind: str       # 法人格の種類("" = 見つからない)
    yago: str       # 屋号(事業所の名前を含む。切り離さない)
    branch: str     # 事業所の印(支店 / 営業所 など。"" = 無い)
    position: str   # 法人格の位置(前 / 後 / 中 / 無)

    @property
    def key(self) -> str:
        """照合キー = 法人格の種類 + 屋号 + 事業所の印。法人格を捨てない。"""
        return f"{self.kind}|{self.yago}|{self.branch}" if self.yago else ""

    @property
    def plain_key(self) -> str:
        """法人格を無視したキー。照合には使わない(『法人格が違う』を見つけるためだけに使う)。"""
        return f"{self.yago}|{self.branch}" if self.yago else ""


class Row(NamedTuple):
    name: str
    number: str = ""


class Index(NamedTuple):
    by_key: dict[str, tuple[Row, ...]]
    by_plain: dict[str, tuple[Row, ...]]
    by_number: dict[str, tuple[Row, ...]]


class Decision(NamedTuple):
    row: Row                     # 入力の行(そのまま)
    key: str                     # 照合キー
    status: str                  # OK(照合)/ PENDING(判断待ち)
    by: str                      # OK のとき 番号 / 名前。PENDING のときは ""
    reason: str                  # OK のときは ""。それ以外は REASONS のキー
    candidates: tuple[Row, ...]  # 相手側で当たったもの

    @property
    def note(self) -> str:
        return REASONS.get(self.reason, "")


def normalize(text: str) -> str:
    """NFKC で合字・全角英数・全角カナを寄せ、空白と区切りを除く。法人格は落とさない。"""
    if not isinstance(text, str):
        raise TypeError("文字列を渡す")
    return _DROP.sub("", unicodedata.normalize("NFKC", text))


def parse(text: str) -> Corp:
    """会社名を 法人格の種類 / 屋号 / 事業所の印 に分ける。除去ではなく分離する。"""
    s = normalize(text)
    kind, position, rest = "", "無", s
    m = _FORM_RE.search(s)
    if m:
        kind = _ALIAS_TO_KIND[m.group(0)]
        position = "前" if m.start() == 0 else ("後" if m.end() == len(s) else "中")
        rest = s[:m.start()] + s[m.end():]
    branch = ""
    for suf in BRANCH_SUFFIXES:
        if rest.endswith(suf) and len(rest) > len(suf):
            branch = suf
            break
    return Corp(text, kind, rest.casefold(), branch, position)


def to_key(text: str) -> str:
    """照合キー。法人格の種類を含むので、A 株式会社 と A 有限会社 は別のキーになる。"""
    return parse(text).key


def check_digit(base12: str) -> int:
    """13 桁の法人番号のうち、下 12 桁から検査数字(先頭 1 桁)を作る。

    算式: 9 -(下 12 桁を右から数え、奇数番目は 1 倍・偶数番目は 2 倍して合計した値)を 9 で割った余り。
    この算式はこの道具が持っている実装で、公表されている仕様と一致するかは利用者が確かめること。
    """
    if len(base12) != 12 or not base12.isdigit():
        raise ValueError("下 12 桁の数字を渡す")
    total = sum(int(c) * (1 if i % 2 == 0 else 2) for i, c in enumerate(reversed(base12)))
    return 9 - total % 9


def number_reason(text: str) -> str:
    """法人番号として使えるなら空文字、列が空なら 空、使えないなら理由コードを返す。"""
    s = _DIGITS.sub("", unicodedata.normalize("NFKC", text or ""))
    if not s:
        return "空"
    if len(s) != 13:
        return "番号の検査に落ちる"
    return "" if int(s[0]) == check_digit(s[1:]) else "番号の検査に落ちる"


def _clean_number(text: str) -> str:
    return _DIGITS.sub("", unicodedata.normalize("NFKC", text or ""))


def build_index(rows: Iterable[Row]) -> Index:
    """照合キー / 法人格抜きのキー / 検査に通った法人番号 の 3 つの索引を作る。"""
    by_key: dict[str, list[Row]] = {}
    by_plain: dict[str, list[Row]] = {}
    by_number: dict[str, list[Row]] = {}
    for r in rows:
        c = parse(r.name)
        if c.key:
            by_key.setdefault(c.key, []).append(r)
            by_plain.setdefault(c.plain_key, []).append(r)
        if not number_reason(r.number):
            by_number.setdefault(_clean_number(r.number), []).append(r)
    return Index({k: tuple(v) for k, v in by_key.items()},
                 {k: tuple(v) for k, v in by_plain.items()},
                 {k: tuple(v) for k, v in by_number.items()})


def match(row: Row, index: Index, self_index: Index | None = None) -> Decision:
    """1 行を相手側の索引に当てる。番号の経路を先に見て、番号が無ければ名前の経路に回す。"""
    c = parse(row.name)
    if not c.key:
        return Decision(row, "", PENDING, "", "空の会社名", ())
    nr = number_reason(row.number)
    if nr not in ("", "空"):
        return Decision(row, c.key, PENDING, "", nr, ())
    if nr == "":
        hits = index.by_number.get(_clean_number(row.number), ())
        if len(hits) == 1:
            return Decision(row, c.key, OK, BY_NUMBER, "", hits)
        if len(hits) >= 2:
            return Decision(row, c.key, PENDING, "", "相手が複数", hits)
    if self_index is not None and len(self_index.by_key.get(c.key, ())) >= 2:
        return Decision(row, c.key, PENDING, "", "自分側が重複", self_index.by_key[c.key])
    hits = index.by_key.get(c.key, ())
    if not hits:
        near = index.by_plain.get(c.plain_key, ())
        if near:
            return Decision(row, c.key, PENDING, "", "法人格が違う", near)
        return Decision(row, c.key, PENDING, "", "相手なし", ())
    if len(hits) >= 2:
        return Decision(row, c.key, PENDING, "", "相手が複数", hits)
    other = hits[0]
    if nr == "" and not number_reason(other.number) and _clean_number(other.number) != _clean_number(row.number):
        return Decision(row, c.key, PENDING, "", "番号が食い違う", hits)
    return Decision(row, c.key, OK, BY_NAME, "", hits)


def match_all(left: Iterable[Row], right: Iterable[Row]) -> list[Decision]:
    """左の台帳の各行を、右の台帳に当てる。左側の同じキーの重複も判断待ちに落とす。"""
    left = list(left)
    ri, li = build_index(right), build_index(left)
    return [match(r, ri, li) for r in left]


def _read_rows(path: str, column: str, number_column: str) -> list[Row]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if rows and column not in rows[0]:
        raise SystemExit(f"列 {column} が {path} に無い(列: {', '.join(rows[0])})")
    return [Row(r[column], (r.get(number_column) or "")) for r in rows]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="jp_corp", description="会社名を法人格を捨てずに寄せ、番号があれば番号で突合する")
    ap.add_argument("values", nargs="*", help="--key / --check のときはその値。そうでなければ CSV 2 つ(左 右)")
    ap.add_argument("--key", action="store_true", help="法人格 / 屋号 / 事業所 / 照合キーを表示する")
    ap.add_argument("--check", action="store_true", help="13 桁の法人番号を検査する")
    ap.add_argument("--column", default="会社名", help="CSV の会社名列(既定: 会社名)")
    ap.add_argument("--number-column", default="法人番号", help="CSV の法人番号列(既定: 法人番号)")
    a = ap.parse_args(argv)
    if a.check:
        bad = 0
        for v in a.values:
            r = number_reason(v)
            bad += r not in ("", "空")
            label = "OK" if r == "" else ("空" if r == "空" else "NG " + r)
            print(f"{v}\t{label}")
        return 3 if bad else 0
    if a.key:
        for v in a.values:
            c = parse(v)
            print(f"{v}\t{c.kind}\t{c.yago}\t{c.branch}\t{c.key}")
        return 0
    if len(a.values) != 2:
        ap.error("CSV を 2 つ渡す(左の台帳 右の台帳)。1 件だけ見るなら --key か --check")
    left = _read_rows(a.values[0], a.column, a.number_column)
    right = _read_rows(a.values[1], a.column, a.number_column)
    counts: dict[str, int] = {}
    pending = 0
    for d in match_all(left, right):
        if d.status == OK:
            print(f"{d.row.name}\t{OK}\t{d.by}\t{d.candidates[0].name}")
        else:
            pending += 1
            counts[d.reason] = counts.get(d.reason, 0) + 1
            print(f"{d.row.name}\t{PENDING}\t{d.reason}\t{'|'.join(r.name for r in d.candidates)}")
    summary = ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
    print(f"照合 {len(left) - pending} / 判断待ち {pending}" + (f" ({summary})" if summary else ""), file=sys.stderr)
    return 3 if pending else 0


if __name__ == "__main__":
    raise SystemExit(main())
