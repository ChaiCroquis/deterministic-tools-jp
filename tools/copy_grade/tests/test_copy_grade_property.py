"""copy_grade の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 読んだ範囲は 2 通りしかない。
  (a) 組を作った: 同じ部品の **2 箇所の組 1 つごとに 4 段か別枠 4 のどれか 1 つ**が付き、
      **その合計 = 部品ごとの C(箇所の件数, 2) の総和**、**部品ごとの内訳の合計も
      注記の組ごとの内訳の合計も同じ数**になる。**違う行の番号が出るのは (C) の組だけ**で、
      **(D) の組だけが違う行数の組を返し**、**注記が何と書いてあっても段は写しの文字で決まり**
      (`指紋一致と注記` を (A) に読み替える経路が無い)、**宣言されている箇所数の文字列は
      生の文字列のまま**で整数に直らない。判定部分に絶対パスも写しのファイル名も入らず、
      3 枚の行順を 3 通りに入れ替えても同じバイト列になる
  (b) 1 組も数えずに理由コードが返る(作った組や sha256 を取りに行くと例外)
どちらの場合も、この部品は 3 枚の表と置き場の写しを 1 文字も書き換えない。

部品を 1〜3 件、箇所を部品ごとに 0〜3 件、注記記号の登録を 6 行から引く。写しは
「同じ断片 / 行末の空白と改行だけ違う / 同じ行数で中身が違う / 行数が違う」の 4 通りを
引いて tmp の置き場へ書く。4 回に 1 回くらいどこか 1 か所を崩す(6 通りを平らに引き、
1 組も数えずに止まる理由コード 6 個すべてに道が付く)。derandomize=True で毎回同じ
200 通りを使い、database=None で例を保存しない。

**段の分け方はテストの側で別に実装している**(部品の grade / four を呼ばず、正規化も
テストの中に別に書く)。2 本目は「写しの文字だけが段を決める」ことを総当たりで見る。
"""
from __future__ import annotations

import csv as _csv
import hashlib
import io
import sys
from pathlib import Path

import pytest
from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import copy_grade as H  # noqa: E402

PART = "合成の棚卸しのメモ(架空)L1"
SITE = "合成の箇所のメモ(架空)L1"
NOTE = "合成の注記の登録のメモ(架空)L1"

BASE = ("def f(x):\n"
        "    y = g(x)\n"
        "    return y\n")
KINDS = ("同じ", "空白と改行だけ違う", "同じ行数で中身が違う", "行数が違う")
BODIES = {
    KINDS[0]: BASE,
    KINDS[1]: BASE.replace("    y = g(x)\n", "    y = g(x)  \n").replace("\n", "\r\n"),
    KINDS[2]: BASE.replace("    y = g(x)\n", "    y = h(x)\n"),
    KINDS[3]: BASE.replace("    return y\n", "    y += 1\n    return y\n"),
}

NOTE_ROWS = [["指紋一致と注記", "指紋が一致すると書かれている", "写し", NOTE],
             ["同型と注記", "人が見て同じ形だと書かれている", "写し", NOTE],
             ["派生と注記", "行数の違う派生だと書かれている", "行数", NOTE],
             ["散在と注記のみ", "散在とだけ書かれている", "—", NOTE],
             ["注記なし", "根拠が書かれていない", "—", NOTE],
             ["版が違うと注記", "版の違う写しだと書かれている", "—", NOTE]]
NOTE_NAMES = tuple(r[0] for r in NOTE_ROWS)
UNREGISTERED = "まだ登録していない注記"
DECLARED = ("17", "8+", "18 ファイル", "4 + 5", "3 本が派生複製(451 / 483 / 486 行)")

KOWASHIKATA = ("宣言の出典を空にする", "部品 id を重複させる", "箇所 id を重複させる",
               "箇所の部品 id を台帳に無いものにする", "同じ注記記号を 2 行にする",
               "同じ部品の 2 箇所に同じ写しを指させる")


def my_normalize(text: str) -> list[str]:
    """正規化をテストの側に別に書く(部品の normalize を呼ばない)。"""
    out: list[str] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        while line[-1:] in (" ", "\t"):
            line = line[:-1]
        out.append(line)
    while out and out[-1] == "":
        out.pop()
    return out


def classify(parts: list[list[str]], sites: list[list[str]],
             notes: list[list[str]], bodies: dict[str, str]
             ) -> dict[str, tuple[str, str]]:
    """組ごとの (段, 違う行 or 行数の組) をテストの側で別に出す。"""
    requires = {r[0]: r[2] for r in notes}
    by_site = {r[0]: r for r in sites}
    by_part: dict[str, list[str]] = {}
    for r in sites:
        by_part.setdefault(r[1], []).append(r[0])
    out: dict[str, tuple[str, str]] = {}
    for part in sorted({r[0] for r in parts}):
        ids = sorted(by_part.get(part, []))
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = by_site[ids[i]], by_site[ids[j]]
                key = f"{part}:{ids[i]}>{ids[j]}"
                if not a[5] or not b[5]:
                    out[key] = (H.BETSUWAKU[0], "")
                elif any(x[3] not in requires for x in (a, b)):
                    out[key] = (H.BETSUWAKU[1], "")
                elif any((requires[x[3]] == "写し" and not x[2])
                         or (requires[x[3]] == "行数" and not x[4])
                         for x in (a, b)):
                    out[key] = (H.BETSUWAKU[2], "")
                elif not a[2] or not b[2]:
                    out[key] = (H.BETSUWAKU[3], "")
                else:
                    ra, rb = bodies[a[2]].encode("utf-8"), bodies[b[2]].encode("utf-8")
                    la, lb = my_normalize(bodies[a[2]]), my_normalize(bodies[b[2]])
                    if ra == rb:
                        out[key] = (H.DAN[0], "")
                    elif la == lb:
                        out[key] = (H.DAN[1], "")
                    elif len(la) == len(lb):
                        out[key] = (H.DAN[2],
                                    ",".join(str(k + 1) for k, (x, y)
                                             in enumerate(zip(la, lb)) if x != y))
                    else:
                        out[key] = (H.DAN[3], f"{len(la)}/{len(lb)}")
    return out


@st.composite
def 合成の3枚(draw: st.DrawFn) -> dict[str, object]:
    """部品の台帳 / 箇所の台帳 / 注記記号の登録表(と写しと崩し方)を作る。"""
    parts: list[list[str]] = []
    for k in range(1, draw(st.integers(1, 3)) + 1):
        parts.append([f"P{k}", f"合成の部品 {k}", draw(st.sampled_from(DECLARED)),
                      draw(st.sampled_from(H.INDUSTRY)),
                      draw(st.sampled_from(H.UNIFIED)), PART])

    sites: list[list[str]] = []
    bodies: dict[str, str] = {}
    n = 0
    how_many = [draw(st.integers(0, 3)) for _ in parts]
    if not any(how_many):           # 箇所が 0 行の表は読めないので 1 件は作る
        how_many[0] = 1
    for part, k in zip(parts, how_many):
        for _ in range(k):
            n += 1
            site_id = f"S{n:02d}"
            handed = draw(st.integers(0, 3)) > 0        # 4 回に 1 回は写しが無い
            name = ""
            if handed:
                name = f"{site_id}.txt"
                bodies[name] = BODIES[draw(st.sampled_from(KINDS))]
            sites.append([site_id, part[0], name,
                          draw(st.sampled_from(NOTE_NAMES + (UNREGISTERED,))),
                          draw(st.sampled_from(("—", "451", ""))),
                          draw(st.sampled_from((SITE, SITE, SITE, SITE, "")))])
    notes = [list(r) for r in NOTE_ROWS]

    # 4 回に 1 回くらい崩す。崩す側は 6 通りを平らに引く
    kowasu = (draw(st.sampled_from(KOWASHIKATA))
              if draw(st.integers(0, 3)) == 0 else None)
    if kowasu == KOWASHIKATA[0]:
        parts[0][5] = ""
    elif kowasu == KOWASHIKATA[1]:
        parts.append([parts[0][0], "二重に書いた部品", DECLARED[0], H.INDUSTRY[0],
                      H.UNIFIED[2], PART])
    elif kowasu == KOWASHIKATA[2] and sites:
        sites.append([sites[0][0], sites[0][1], "", "注記なし", "—", SITE])
    elif kowasu == KOWASHIKATA[3]:
        sites.append(["S99", "P99", "", "注記なし", "—", SITE])
    elif kowasu == KOWASHIKATA[4]:
        notes.append(["注記なし", "二重に登録した記号", "—", NOTE])
    elif kowasu == KOWASHIKATA[5]:
        handed_sites = [s for s in sites if s[2]]
        if len(handed_sites) >= 2:
            pair = [s for s in sites if s[1] == handed_sites[0][1] and s[2]]
            if len(pair) >= 2:
                pair[1][2] = pair[0][2]
            else:
                kowasu = None
        else:
            kowasu = None
    if kowasu in (KOWASHIKATA[2],) and not sites:
        kowasu = None

    def csv(head: tuple[str, ...], body: list[list[str]]) -> str:
        buf = io.StringIO()
        _csv.writer(buf, lineterminator="\n").writerows([list(head)] + body)
        return buf.getvalue()

    return {"parts": csv(H.PART_COLUMNS, parts), "sites": csv(H.SITE_COLUMNS, sites),
            "notes": csv(H.NOTE_COLUMNS, notes), "parts_rows": parts,
            "sites_rows": sites, "notes_rows": notes, "bodies": bodies,
            "kowasu": kowasu}


def box_of(tmp: Path, bodies: dict[str, str]) -> H.Copies:
    for name, body in sorted(bodies.items()):
        (tmp / name).write_bytes(body.encode("utf-8"))
    return H.Copies.load(tmp, tuple(sorted(bodies)))


@settings(max_examples=200, derandomize=True, database=None, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(plan=合成の3枚())
def test_いつも成り立つこと_作った組か理由コードか(plan: dict[str, object],
                                                tmp_path: Path) -> None:
    parts = H.Parts.parse(plan["parts"])     # type: ignore[arg-type]
    sites = H.Sites.parse(plan["sites"])     # type: ignore[arg-type]
    notes = H.Notes.parse(plan["notes"])     # type: ignore[arg-type]
    box = tmp_path / "copies"
    box.mkdir(exist_ok=True)
    copies = box_of(box, plan["bodies"])     # type: ignore[arg-type]
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(box.iterdir())}
    t = H.copy_grade(parts, sites, notes, copies)

    expect_stop = plan["kowasu"] is not None
    c = t.counts()
    four, extras = c["4 段"], c["別枠"]
    assert c["部品の台帳の行数"] == len(plan["parts_rows"])   # type: ignore[arg-type]
    assert c["箇所の台帳の行数"] == len(plan["sites_rows"])   # type: ignore[arg-type]
    assert {x.grade for x in t.pairs} <= set(H.DAN + H.BETSUWAKU)
    assert all(isinstance(v, int) for v in four.values())   # type: ignore[union-attr]
    # **出力に「まとめてよいか」「正本」「類似度」の欄が無い**
    for key in c:
        for word in ("類似度", "一致率", "統合すべき", "正本", "優先度"):
            assert word not in key
    # **宣言されている箇所数は生の文字列のまま**
    declared = {str(r["宣言されている箇所数の文字列"])
                for r in t.declared_vs_handed()}
    assert declared <= {row[2] for row in plan["parts_rows"]}   # type: ignore[union-attr]
    assert all(s in DECLARED for s in declared)

    if expect_stop:
        event("(b) 1 組も数えずに止まった")
        assert t.report.ok is False and t.report.pending
        assert {x.reason for x in t.report.pending} <= set(H.TABLE_REASONS)
        assert t.pairs == ()
        assert four == {k: 0 for k in H.DAN}
        assert extras == {k: 0 for k in H.BETSUWAKU}
        assert t.pair_denominator() == 0
        for call in (t.judgement_bytes, t.sha256):
            with pytest.raises(RuntimeError):
                call()
    else:
        event("(a) 組を作った")
        assert t.report.ok is True
        mine = {x.name: (x.grade, ",".join(str(k) for k in x.diff_lines)
                         if x.grade == H.DAN[2]
                         else (f"{x.lines[0]}/{x.lines[1]}"
                               if x.grade == H.DAN[3] else ""))
                for x in t.pairs}
        assert mine == classify(plan["parts_rows"], plan["sites_rows"],   # type: ignore[arg-type]
                                plan["notes_rows"], plan["bodies"])      # type: ignore[arg-type]
        # 組の件数 = 部品ごとの C(箇所の件数, 2) の総和
        want = 0
        for part in parts.ids:
            k = len(sites.of_part(part))
            want += k * (k - 1) // 2
        assert t.pair_denominator() == want
        total = sum(four.values()) + sum(extras.values())   # type: ignore[union-attr]
        assert total == t.pair_denominator()
        assert sum(int(r["組の件数"]) for r in t.by_part()) == total
        assert sum(int(r["組の件数"]) for r in t.by_note()) == total
        # 違う行の番号が出るのは (C) の組だけ、行数が違うのは (D) の組だけ
        for x in t.pairs:
            assert bool(x.diff_lines) == (x.grade == H.DAN[2] and x.lines[0] > 0
                                          and bool(x.diff_lines))
            if x.grade == H.DAN[2]:
                assert x.lines[0] == x.lines[1] and x.diff_lines
                assert all(1 <= k <= x.lines[0] for k in x.diff_lines)
            elif x.grade == H.DAN[3]:
                assert x.lines[0] != x.lines[1] and not x.diff_lines
            elif x.grade in (H.DAN[0], H.DAN[1]):
                assert x.lines[0] == x.lines[1] and not x.diff_lines
            else:
                assert x.lines == (0, 0) and not x.diff_lines
            # **注記が何と書いてあっても、段は写しの文字で決まる**
            if "指紋一致と注記" in x.notes and x.graded:
                a = next(s for s in sites.ordered if s.site_id == x.a)
                b = next(s for s in sites.ordered if s.site_id == x.b)
                same = copies.of(a.copy).raw_sha == copies.of(b.copy).raw_sha
                assert (x.grade == H.DAN[0]) is same
        body = t.judgement_bytes().decode("utf-8")
        for word in ("読んだ条件", "絶対パス", str(ROOT), ".txt"):
            assert word not in body
        # 3 枚の行順を 3 通りに入れ替えても同じバイト列
        for how in H.SWAPS:
            again = H.copy_grade(parts.swapped(how), sites.swapped(how),
                                 notes.swapped(how), copies)
            assert again.judgement_bytes() == t.judgement_bytes()
            assert again.sha256() == t.sha256()

    # どちらの場合も入力は 1 文字も書き換わらない
    assert H.Parts.parse(plan["parts"]).items == parts.items   # type: ignore[arg-type]
    assert H.Sites.parse(plan["sites"]).items == sites.items   # type: ignore[arg-type]
    assert H.Notes.parse(plan["notes"]).items == notes.items   # type: ignore[arg-type]
    assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(box.iterdir())} == before


@settings(max_examples=300, derandomize=True, database=None)
@given(left=st.sampled_from(KINDS), right=st.sampled_from(KINDS),
       note=st.sampled_from(NOTE_NAMES))
def test_段を決めるのは写しの文字だけ(left: str, right: str, note: str) -> None:
    """注記が何と書いてあっても、段は写しの文字の一致で決まる。

    **`指紋一致と注記` を (A) に読み替える経路が無く**、**行末の空白と改行だけの差は
    必ず (B)**、**行数が同じで中身が違えば必ず (C) で違う行の番号が出る**、
    **行数が違えば必ず (D) で行数の組が出る**。
    """
    la, lb = my_normalize(BODIES[left]), my_normalize(BODIES[right])
    if BODIES[left] == BODIES[right]:
        want = H.DAN[0]
    elif la == lb:
        want = H.DAN[1]
    elif len(la) == len(lb):
        want = H.DAN[2]
    else:
        want = H.DAN[3]
    sa = H.Site("S01", "P1", "a.txt", note, "451", SITE)
    sb = H.Site("S02", "P1", "b.txt", note, "451", SITE)
    notes = H.Notes.parse("\n".join([",".join(H.NOTE_COLUMNS)]
                                    + [",".join(r) for r in NOTE_ROWS]))
    copies = H.Copies(Path("."), {"a.txt": H.Copy(BODIES[left].encode("utf-8"),
                                                  BODIES[left]),
                                  "b.txt": H.Copy(BODIES[right].encode("utf-8"),
                                                  BODIES[right])})
    pair = H.grade("P1", sa, sb, notes, copies)
    assert pair.grade == want
    assert bool(pair.diff_lines) == (want == H.DAN[2])
    if want == H.DAN[3]:
        assert pair.lines[0] != pair.lines[1]
    else:
        assert pair.lines[0] == pair.lines[1]
