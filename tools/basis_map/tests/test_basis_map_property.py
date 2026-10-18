"""basis_map の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 読んだ範囲は 2 通りしかない。
  (a) (rule × 対象)の組ごとに 4 値が 1 つだけ付き、4 値の合計が rule 数 × 対象数に等しく、
      決まらない理由別の合計が決まらないの件数に等しく、決まった組の渡す日付は手元の表に
      そのまま在る文字列で(ほかの 3 値には日付が付かず)、判定部分に時刻・ホスト名・
      絶対パスが入らず、3 枚の行順を入れ替えても同じバイト列になる
  (b) 1 組も読まずに理由コードが返る(読んだ組や指紋を取りに行くと例外)
どちらの場合も、この部品は種別の台帳も要求表も手元の表も 1 文字も書き換えない。

種別を 2〜4 個作り、別名を宣言するかどうかを種別ごとに振り、状態(登録済 / 候補)も振る。
rule を 1〜3 本、対象を 1〜3 件作り、手元の表記は「宣言された表記」と「どこにも宣言されて
いない表記」から引く。さらに 3 割くらいの確率で 1 か所だけ崩す(出典を空にする /
台帳に無い種別 id を要求する / 同じ別名を 2 種別に宣言する / 同じ種別 id を 2 行書く /
書式に合わない日付を書く / 状態を宣言外にする / 同じ rule id を 2 行書く)。
derandomize=True で毎回同じ入力列を使い、database=None で見つけた例を保存しない。

**4 値はテストの側で別に組み立てている**(部品の判定を呼ばず、3 枚の表の行から直に決める)。
2 本目は「宣言されていない表記は、どれだけ正式な表記に似ていても寄らない」ことを見ている
(文字列が似ていることを理由に寄せる経路が無い、の物理形)。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from hypothesis import event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import basis_map as B  # noqa: E402

SOURCE = "合成の出典メモ(架空)L1"
IDS = ("K01", "K02", "K03", "K04")
NAMES = ("合成の種別A(架空)", "合成の種別B(架空)", "合成の種別C(架空)",
         "合成の種別D(架空)")
ALIASES = ("合成の別名A(架空)", "合成の別名B(架空)", "合成の別名C(架空)",
           "合成の別名D(架空)")
SOTO = "合成の宣言外の表記(架空)"        # どの種別にも宣言されていない表記
DATES = ("2026-01-05", "2026-02-09", "2026-03-02", "2026-04-06")
FMT = "YYYY-MM-DD"

KOWASHIKATA = ("出典を空にする", "台帳に無い種別 id を要求する",
               "同じ別名を 2 種別に宣言する", "同じ種別 id を 2 行書く",
               "書式に合わない日付を書く", "状態を宣言外にする",
               "同じ rule id を 2 行書く")


@st.composite
def 合成の3枚(draw: st.DrawFn) -> dict[str, object]:
    """種別の台帳 / 要求表 / 手元の表(と崩し方)を作る。"""
    n = draw(st.integers(2, 4))
    shubetsu: list[list[str]] = []
    labels: list[tuple[str, str]] = []          # (表記, 種別 id)
    for i in range(n):
        alias = ALIASES[i] if draw(st.booleans()) else ""
        shubetsu.append([IDS[i], NAMES[i], alias, "合成の意味の 1 行(架空)", FMT,
                         draw(st.sampled_from(B.STATUSES)), SOURCE])
        labels.append((NAMES[i], IDS[i]))
        if alias:
            labels.append((alias, IDS[i]))

    youkyuu = [[f"R{i + 1:02d}", draw(st.sampled_from(IDS[:n])), SOURCE]
               for i in range(draw(st.integers(1, 3)))]

    temoto: list[list[str]] = []
    for i in range(draw(st.integers(1, 3))):
        target = f"T{i + 1:02d}"
        pool = [lab for lab, _ in labels] + [SOTO]
        chosen = draw(st.lists(st.sampled_from(pool), max_size=4, unique=True))
        for lab in sorted(chosen):
            temoto.append([target, lab, draw(st.sampled_from(DATES)), SOURCE, ""])
    if not temoto:                               # 手元の表が 0 行だと読めない表
        temoto.append(["T01", NAMES[0], DATES[0], SOURCE, ""])
    temoto[0][4] = B.SWAPS[0]

    kowasu = draw(st.sampled_from([None] * 7 + list(KOWASHIKATA)))
    if kowasu == "出典を空にする":
        shubetsu[0][6] = ""
    elif kowasu == "台帳に無い種別 id を要求する":
        youkyuu[0][1] = "K09"
    elif kowasu == "同じ別名を 2 種別に宣言する":
        shubetsu[1][2] = NAMES[0]
    elif kowasu == "同じ種別 id を 2 行書く":
        shubetsu.append([IDS[0], "合成の種別Z(架空)", "", "合成の意味の 1 行(架空)",
                         FMT, B.STATUSES[0], SOURCE])
    elif kowasu == "書式に合わない日付を書く":
        temoto[0][1], temoto[0][2] = NAMES[0], "2026/01/05"
    elif kowasu == "状態を宣言外にする":
        shubetsu[0][5] = "検討中"
    elif kowasu == "同じ rule id を 2 行書く":
        youkyuu.append([youkyuu[0][0], IDS[0], SOURCE])

    def csv(head: tuple[str, ...], body: list[list[str]]) -> str:
        return "\n".join([",".join(head)] + [",".join(r) for r in body])

    return {"shubetsu": csv(B.SHUBETSU_COLUMNS, shubetsu),
            "youkyuu": csv(B.YOUKYUU_COLUMNS, youkyuu),
            "temoto": csv(B.TEMOTO_COLUMNS, temoto),
            "shubetsu_rows": shubetsu, "youkyuu_rows": youkyuu,
            "temoto_rows": temoto, "kowasu": kowasu}


def 期待する4値(plan: dict[str, object]) -> dict[str, int]:
    """4 値を、3 枚の表の行から直に組み立てる(部品の判定は呼ばない)。"""
    label_of: dict[str, str] = {}
    status: dict[str, str] = {}
    for kid, name, alias, _m, _f, st_, _s in plan["shubetsu_rows"]:   # type: ignore[union-attr]
        status.setdefault(kid, st_)
        for lab in [name] + ([alias] if alias else []):
            label_of.setdefault(lab, kid)
    targets = sorted({r[0] for r in plan["temoto_rows"]})             # type: ignore[union-attr]
    out = dict.fromkeys(B.RESULTS, 0)
    for _rid, kind_id, _s in plan["youkyuu_rows"]:                    # type: ignore[union-attr]
        for t in targets:
            rows = [r for r in plan["temoto_rows"] if r[0] == t]      # type: ignore[union-attr]
            others = sum(1 for r in rows if r[1] not in label_of)
            hit = [r for r in rows if label_of.get(r[1]) == kind_id]
            if status[kind_id] != B.STATUSES[0] or len(hit) >= 2 \
                    or (not hit and others):
                out[B.RESULTS[2]] += 1
            elif hit:
                out[B.RESULTS[0]] += 1
            else:
                out[B.RESULTS[1]] += 1
    return out


@settings(max_examples=150, derandomize=True, database=None, deadline=None)
@given(plan=合成の3枚())
def test_いつも成り立つこと_読んだ組か理由コードか(plan: dict[str, object]) -> None:
    registry = B.Registry.parse(plan["shubetsu"])                     # type: ignore[arg-type]
    demands = B.Demands.parse(plan["youkyuu"])                        # type: ignore[arg-type]
    hand = B.Hand.parse(plan["temoto"])                               # type: ignore[arg-type]
    t = B.basis_map(registry, demands, hand)

    expect_stop = plan["kowasu"] is not None
    c = t.counts()
    four = c["4 値"]
    assert c["種別の台帳の行数"] == len(plan["shubetsu_rows"])        # type: ignore[arg-type]
    assert c["要求表の行数"] == len(plan["youkyuu_rows"])             # type: ignore[arg-type]
    assert c["手元の表の行数"] == len(plan["temoto_rows"])            # type: ignore[arg-type]
    assert c["分母(rule 数 × 対象数)"] == t.report.rules * t.report.targets
    assert sum(four.values()) == len(t.pairs)                         # type: ignore[union-attr]
    # 表が揃う前に止まったら 1 組も読まない。読んだなら組と 1 対 1 で付く
    assert len(t.pairs) in (0, t.denominator)
    assert {p.result for p in t.pairs} <= set(B.RESULTS)
    if t.pairs:
        assert four == 期待する4値(plan)

    # 渡す日付が付くのは「決まった」組だけ。しかも手元の表にそのまま在る文字列
    have = {(h.target_id, h.kind_label, h.date) for h in hand.items}
    for p in t.pairs:
        if p.result == B.RESULTS[0]:
            assert (p.target_id, p.label, p.date) in have
            assert p.why == ""
        else:
            assert p.label == "" and p.date == ""
            assert (p.why in B.UNDECIDED) == (p.result == B.RESULTS[2])

    if expect_stop:
        event("(b) 止まった")
        assert t.report.ok is False
        assert t.report.pending
        assert {p.reason for p in t.report.pending} <= set(B.STOP_REASONS)
        for call in (lambda: t.verdict, t.judgement_bytes, t.sha256):
            with pytest.raises(RuntimeError):
                call()
    else:
        event("(a) 読んだ")
        assert t.report.ok is True
        assert four[B.RESULTS[3]] == 0                                # type: ignore[index]
        # 決まらない理由別の合計 = 決まらないの件数
        assert sum(t.by_why().values()) == four[B.RESULTS[2]]         # type: ignore[index]
        assert sum(four.values()) == t.denominator
        body = t.judgement_bytes().decode("utf-8")
        for word in (t.read_at, t.host, "読んだ時刻", "ホスト名"):
            assert word not in body
        # 3 枚の行順を入れ替えても同じバイト列
        again = B.basis_map(registry.swapped(B.SWAPS[0]),
                            demands.swapped(B.SWAPS[0]),
                            hand.swapped(hand.swap or B.SWAPS[0]))
        assert again.sha256() == t.sha256()
        assert again.judgement_bytes() == t.judgement_bytes()

    # どちらの場合も入力は 1 文字も書き換わらない
    assert B.Registry.parse(plan["shubetsu"]).items == registry.items  # type: ignore[arg-type]
    assert B.Demands.parse(plan["youkyuu"]).items == demands.items     # type: ignore[arg-type]
    assert B.Hand.parse(plan["temoto"]).items == hand.items            # type: ignore[arg-type]


@settings(max_examples=300, derandomize=True, database=None)
@given(suffix=st.sampled_from(("", "・", "の日", "(確認)", "2")),
       prefix=st.sampled_from(("", "新", "旧")),
       status=st.sampled_from(B.STATUSES))
def test_宣言されていない表記は似ていても寄らない(suffix: str, prefix: str,
                                                  status: str) -> None:
    """正式な表記をどれだけ崩しても、台帳に宣言が無ければ種別へ写らない。

    寄せてよいのは、正式な表記そのものと、台帳に宣言された別名だけだ。似ている / 2 文字しか
    違わない / 片方が片方を含む、のどれも寄せる理由にしない。
    """
    name, alias = NAMES[0], ALIASES[0]
    label = f"{prefix}{name}{suffix}"
    shubetsu = "\n".join([",".join(B.SHUBETSU_COLUMNS),
                          f"{IDS[0]},{name},{alias},合成の意味の 1 行(架空),{FMT},"
                          f"{status},{SOURCE}"])
    youkyuu = "\n".join([",".join(B.YOUKYUU_COLUMNS),
                         f"R01,{IDS[0]},{SOURCE}"])
    temoto = "\n".join([",".join(B.TEMOTO_COLUMNS),
                        f"T01,{label},{DATES[0]},{SOURCE},{B.SWAPS[0]}"])
    registry = B.Registry.parse(shubetsu)
    t = B.basis_map(registry, B.Demands.parse(youkyuu), B.Hand.parse(temoto))
    assert t.report.ok
    declared = label in (name, alias)
    assert (registry.by_label(label) is not None) is declared
    if declared and status == B.STATUSES[0]:
        assert t.pairs[0].result == B.RESULTS[0]
        assert t.pairs[0].label == label and t.pairs[0].date == DATES[0]
    elif status != B.STATUSES[0]:
        assert t.pairs[0].result == B.RESULTS[2]
        assert t.pairs[0].why == B.UNDECIDED[0]
    else:
        # 宣言が無い表記は写らないので、手元に無い種別を別の日付で埋めない
        assert t.pairs[0].result == B.RESULTS[2]
        assert t.pairs[0].why == B.UNDECIDED[1]
        assert t.pairs[0].date == ""
