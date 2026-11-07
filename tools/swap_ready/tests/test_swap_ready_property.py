"""swap_ready の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文を検査にする。

いつも成り立つこと: 読んだ範囲は 2 通りしかない。
  (a) 4 値を付けた: **経路 1 件ごとに 4 値の 5 欄か別枠 6 のどれか 1 つ**が付き、
      **その合計 = 経路の件数**、**種別ごとの内訳の合計も束ごとの内訳の合計も同じ数**に
      なる。**許す側の宣言が無い経路は (A)(B)(C) に入らず**、**検査が独立でない経路は
      (A)(C) に入らず**、**跡の欄が無い経路は件数に `数えられない` を返して 0 件と同じ値に
      ならない**。**範囲つきで許す経路は、通す対象の種別が範囲の記号の列に在るときだけ
      4 値へ進む**(注記の文字は読まない)。理由は入力の注記のままで、判定部分は 5 枚の
      行順を 3 通りに入れ替えても同じバイト列になる
  (b) 1 経路も数えずに理由コードが返る(4 値や sha256 を取りに行くと例外)
どちらの場合も、この部品は 5 枚の表を 1 文字も書き換えない。

経路を 1〜3 件、検査を経路ごとに 0〜2 件、跡を経路ごとに 0〜2 件引く。3 回に 1 回くらい
どこか 1 か所を崩す(崩し方は 7 通りで、どれが引かれるかは hypothesis が決めるので、7 通り
すべてが毎回出るとは限らない。**7 個の理由コード全部に道が在ることは、崩した表を直に通す
test_measure_seven_stop_reasons_all_reachable の側で決定論的に確かめている**)。
derandomize=True で毎回同じ 200 通りを使い、database=None で例を保存しない。

**4 値の決め方はテストの側で別に実装している**(部品の judge / five / extras を呼ばない)。
2 本目は「4 値を決めるのは許す宣言と検査の所属と跡の件数だけ」を総当たりで見る。
"""
from __future__ import annotations

import csv as _csv
import io
import sys
from pathlib import Path

import pytest
from hypothesis import event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import swap_ready as H  # noqa: E402

ASOF = "2026-09-20"
R_SRC = "合成の経路のメモ(架空)L1"
C_SRC = "合成の検査のメモ(架空)L1"
T_SRC = "合成の跡のメモ(架空)L1"
P_SRC = "合成の許す宣言の登録のメモ(架空)L1"
Q_SRC = "合成の検査の所属の登録のメモ(架空)L1"

BUNDLES = ("束 A", "束 B")
CROSS = "照合用の束"
NOTES = ("—", "照合専用", "読むだけ", "data だけ通す")
SCOPES = ("—", "data", "data/行", "版")
DATES = ("—", "2026-01-05", "2026-06-20")
UNREGISTERED_PERM = "たぶん許す"
UNREGISTERED_PLACE = "たぶん独立"
FIELDS = ("—", "版の欄", "入れ替えの欄")
OBSERVED = ("—", "0", "1", "2")

PERM_ROWS = [[H.PERMISSIONS[0], "入れ替えてよい", H.PERM_REQUIRES[1], P_SRC],
             [H.PERMISSIONS[1], "範囲を限って入れ替えてよい", H.PERM_REQUIRES[2], P_SRC],
             [H.PERMISSIONS[2], "入れ替えない", H.PERM_REQUIRES[0], P_SRC],
             [H.PERMISSIONS[3], "宣言が無い", H.PERM_REQUIRES[0], P_SRC]]
PLACE_ROWS = [[H.PLACEMENTS[0], "別の束に在る", H.PLACE_REQUIRES[1], Q_SRC],
              [H.PLACEMENTS[1], "同じ束に在る", H.PLACE_REQUIRES[0], Q_SRC],
              [H.PLACEMENTS[2], "検査が無い", H.PLACE_REQUIRES[0], Q_SRC]]

KOWASHIKATA = ("登録の行の出典を空にする", "経路 id を重複させる",
               "登録表から記号を 1 つ落とす", "登録表の要求する欄を決めた外にする",
               "宣言された日を基準日より後にする", "跡の件数を整数でない文字にする",
               "基準日を渡さない")


def my_value(route: list[str], checks: list[list[str]], traces: list[list[str]],
             perms: list[list[str]], places: list[list[str]]) -> str:
    """経路 1 件の 4 値 / 別枠をテストの側で出す(部品の judge を呼ばない)。"""
    rid, kind, bundle, perm, note, kinds, declared, source = route
    req_perm = {r[0]: r[2] for r in perms}
    req_place = {r[0]: r[2] for r in places}
    mine = [c for c in checks if c[1] == rid]
    mytr = [t for t in traces if t[0] == rid]
    scope = [] if kinds in ("—", "") else [x for x in kinds.split("/") if x]

    if not source or any(not c[4] for c in mine) or any(not t[5] for t in mytr):
        return H.BETSUWAKU[0]
    if perm not in req_perm or any(c[2] not in req_place for c in mine):
        return H.BETSUWAKU[1]
    if req_perm[perm] == H.PERM_REQUIRES[1] and declared in ("—", ""):
        return H.BETSUWAKU[2]
    if req_perm[perm] == H.PERM_REQUIRES[2] and (note in ("—", "") or not scope):
        return H.BETSUWAKU[2]
    if any(req_place[c[2]] == H.PLACE_REQUIRES[1] and not c[3] for c in mine):
        return H.BETSUWAKU[2]
    placements = {c[2] for c in mine}
    if len(placements) > 1:
        return H.BETSUWAKU[3]
    if any(c[2] == H.PLACEMENTS[0] and c[3] == bundle for c in mine):
        return H.BETSUWAKU[3]
    fields = [t[1] for t in mytr if t[1] not in ("—", "")]
    if len(fields) != len(set(fields)):
        return H.BETSUWAKU[3]
    if perm == H.PERMISSIONS[1] and kind not in scope:
        return H.BETSUWAKU[4]
    if perm == H.PERMISSIONS[2]:
        return H.VALUES[3]
    if perm == H.PERMISSIONS[3]:
        return H.VALUES[4]
    if placements != {H.PLACEMENTS[0]}:
        return H.VALUES[1]
    counted = [t for t in mytr if t[1] not in ("—", "")]
    if not counted:
        return H.BETSUWAKU[5]
    total = sum(int(t[2]) for t in counted if t[2].isdigit())
    return H.VALUES[0] if total >= 1 else H.VALUES[2]


@st.composite
def 合成の5枚(draw: st.DrawFn) -> dict[str, object]:
    """経路 / 検査 / 跡 の 3 枚と記号の登録表 2 枚(と崩し方)を作る。"""
    routes: list[list[str]] = []
    checks: list[list[str]] = []
    traces: list[list[str]] = []
    n = 0
    for k in range(1, draw(st.integers(1, 3)) + 1):
        rid = f"R{k}"
        routes.append([rid, draw(st.sampled_from(H.KINDS)),
                       draw(st.sampled_from(BUNDLES)),
                       draw(st.sampled_from(H.PERMISSIONS + (UNREGISTERED_PERM,))),
                       draw(st.sampled_from(NOTES)), draw(st.sampled_from(SCOPES)),
                       draw(st.sampled_from(DATES)),
                       draw(st.sampled_from((R_SRC, R_SRC, R_SRC, "")))])
        for _ in range(draw(st.integers(0, 2))):
            n += 1
            checks.append([f"C{n:02d}", rid,
                           draw(st.sampled_from(H.PLACEMENTS + (UNREGISTERED_PLACE,))),
                           draw(st.sampled_from(("—", "", CROSS) + BUNDLES)),
                           draw(st.sampled_from((C_SRC, C_SRC, C_SRC, "")))])
        for _ in range(draw(st.integers(0, 2))):
            traces.append([rid, draw(st.sampled_from(FIELDS)),
                           draw(st.sampled_from(OBSERVED)),
                           draw(st.sampled_from(("—", "11 行"))),
                           draw(st.sampled_from(("", "", "合成の理由(架空)"))),
                           draw(st.sampled_from((T_SRC, T_SRC, T_SRC, "")))])
    perms = [list(r) for r in PERM_ROWS]
    places = [list(r) for r in PLACE_ROWS]
    asof = ASOF

    # 3 回に 1 回くらい崩す。崩す側は 7 通りを平らに引く(負の数は「崩さない」)
    pick = draw(st.sampled_from(tuple(range(-14, len(KOWASHIKATA)))))
    kowasu = KOWASHIKATA[pick] if pick >= 0 else None
    if kowasu == KOWASHIKATA[0]:
        perms[0][3] = ""
    elif kowasu == KOWASHIKATA[1]:
        routes.append([routes[0][0], H.KINDS[0], BUNDLES[0], H.PERMISSIONS[0], "—",
                       "—", "2026-01-05", R_SRC])
    elif kowasu == KOWASHIKATA[2]:
        places = places[:-1]
    elif kowasu == KOWASHIKATA[3]:
        perms[0][2] = "跡の欄"
    elif kowasu == KOWASHIKATA[4]:
        routes[0][6] = "2026-12-01"
    elif kowasu == KOWASHIKATA[5]:
        traces.append([routes[0][0], FIELDS[1], "3 件", "11 行", "", T_SRC])
    elif kowasu == KOWASHIKATA[6]:
        asof = ""

    def table(head: tuple[str, ...], body: list[list[str]]) -> str:
        buf = io.StringIO()
        _csv.writer(buf, lineterminator="\n").writerows([list(head)] + body)
        return buf.getvalue()

    return {"routes": table(H.ROUTE_COLUMNS, routes),
            "checks": table(H.CHECK_COLUMNS, checks),
            "traces": table(H.TRACE_COLUMNS, traces),
            "perms": table(H.PERM_COLUMNS, perms),
            "places": table(H.PLACE_COLUMNS, places),
            "routes_rows": routes, "checks_rows": checks, "traces_rows": traces,
            "perms_rows": perms, "places_rows": places,
            "asof": asof, "kowasu": kowasu}


def five_of(plan: dict[str, object]):
    routes = H.Routes.parse(plan["routes"])        # type: ignore[arg-type]
    ids = routes.ids
    return (routes, H.Checks.parse(plan["checks"], ids),     # type: ignore[arg-type]
            H.Traces.parse(plan["traces"], ids),             # type: ignore[arg-type]
            H.Registry.parse(plan["perms"], H.PERM_COLUMNS, H.PERMISSIONS,   # type: ignore[arg-type]
                             H.PERM_REQUIRES, "許す宣言の登録表"),
            H.Registry.parse(plan["places"], H.PLACE_COLUMNS, H.PLACEMENTS,  # type: ignore[arg-type]
                             H.PLACE_REQUIRES, "検査の所属の登録表"))


@settings(max_examples=200, derandomize=True, database=None, deadline=None)
@given(plan=合成の5枚())
def test_いつも成り立つこと_4値か理由コードか(plan: dict[str, object]) -> None:
    five = five_of(plan)
    routes, checks, traces, perms, places = five
    asof = plan["asof"]
    t = H.swap_ready(*five, asof)    # type: ignore[arg-type]

    expect_stop = plan["kowasu"] is not None
    c = t.counts()
    assert c["経路の台帳の行数"] == len(plan["routes_rows"])    # type: ignore[arg-type]
    assert c["受け入れ検査の台帳の行数"] == len(plan["checks_rows"])   # type: ignore[arg-type]
    assert {x.value for x in t.rows} <= set(H.VALUES + H.BETSUWAKU)
    assert all(isinstance(v, int) for v in t.five().values())
    # **件数の側に「入れ替えるべきか」の欄が無い**(末尾の 10 行だけがその語を持つ)
    for key in (k for k in c if k not in H.MOTANAI):
        for word in ("推奨", "順位", "優先度", "点数", "割合", "入れ替えるべき"):
            assert word not in key

    if expect_stop:
        event(f"(b) 止まった: {plan['kowasu']}")
        assert t.report.ok is False and t.report.pending
        assert {x.reason for x in t.report.pending} <= set(H.TABLE_REASONS)
        assert t.rows == () and t.denominator() == 0
        assert t.five() == {k: 0 for k in H.VALUES}
        assert t.extras() == {k: 0 for k in H.BETSUWAKU}
        assert t.stall()["(B) + (C) の件数"] == 0
        for call in (t.judgement_bytes, t.sha256):
            with pytest.raises(RuntimeError):
                call()
    else:
        event("(a) 4 値を付けた")
        assert t.report.ok is True
        mine = {r[0]: my_value(r, plan["checks_rows"], plan["traces_rows"],   # type: ignore[arg-type]
                               plan["perms_rows"], plan["places_rows"])      # type: ignore[arg-type]
                for r in plan["routes_rows"]}                                # type: ignore[union-attr]
        assert {x.route_id: x.value for x in t.rows} == mine
        total = sum(t.five().values()) + sum(t.extras().values())
        assert total == t.denominator() == len(t.rows)
        assert sum(int(r["経路の件数"]) for r in t.by_kind()) == total
        assert sum(int(r["経路の件数"]) for r in t.by_bundle()) == total
        for x in t.rows:
            # **許す側の宣言が無い経路は (A)(B)(C) に入らない**
            if x.permission not in (H.PERMISSIONS[0], H.PERMISSIONS[1]):
                assert x.value not in (H.VALUES[0], H.VALUES[1], H.VALUES[2])
            # **検査が独立でない経路は (A)(C) に入らない**
            if x.placement != H.PLACEMENTS[0]:
                assert x.value not in (H.VALUES[0], H.VALUES[2])
            # **0 件と欄が無いを同じ値にしない**
            if x.observed == H.UNCOUNTABLE:
                assert x.value != H.VALUES[0] and x.value != H.VALUES[2]
                assert x.field == H.NO_MARK
            elif x.value in (H.VALUES[0], H.VALUES[2]):
                assert x.observed.isdigit()
                assert (int(x.observed) >= 1) == (x.value == H.VALUES[0])
            # **範囲つきで許すは、種別が範囲の記号の列に在るときだけ 4 値へ進む**
            if x.permission == H.PERMISSIONS[1] and x.value in H.VALUES:
                assert x.kind in routes.of(x.route_id).in_scope
            # 日数は整数か「記載なし」、理由は入力の注記のまま
            assert x.days == H.NO_DECLARED or x.days.lstrip("-").isdigit()
            for r in x.reasons:
                assert r == H.NO_REASON or "(出典 = " in r
        body = t.judgement_bytes().decode("utf-8")
        for word in ("読んだ条件", str(ROOT), "照合専用", "読むだけ"):
            assert word not in body
        # 5 枚の行順を 3 通りに入れ替えても同じバイト列
        for how in H.SWAPS:
            again = H.swap_ready(routes.swapped(how), checks.swapped(how),
                                 traces.swapped(how), perms.swapped(how),
                                 places.swapped(how), asof)   # type: ignore[arg-type]
            assert again.judgement_bytes() == t.judgement_bytes()
            assert again.sha256() == t.sha256()

    # どちらの場合も入力は 1 文字も書き換わらない
    assert H.Routes.parse(plan["routes"]).rows == routes.rows      # type: ignore[arg-type]
    assert H.Checks.parse(plan["checks"], routes.ids).rows == checks.rows   # type: ignore[arg-type]
    assert H.Traces.parse(plan["traces"], routes.ids).rows == traces.rows   # type: ignore[arg-type]


@settings(max_examples=300, derandomize=True, database=None)
@given(permission=st.sampled_from(H.PERMISSIONS), placement=st.sampled_from(H.PLACEMENTS),
       field=st.sampled_from(FIELDS), observed=st.sampled_from(OBSERVED),
       note=st.sampled_from(NOTES[1:]))
def test_4値を決めるのは宣言と所属と跡の件数だけ(permission: str, placement: str,
                                                field: str, observed: str,
                                                note: str) -> None:
    """注記の文字が何であっても、同じ (宣言, 所属, 跡) なら同じ 4 値になる。"""
    route = ["R1", "data", BUNDLES[0], permission, note, "data", "2026-01-05", R_SRC]
    checks = [["C01", "R1", placement, CROSS, C_SRC]]
    traces = [["R1", field, observed, "11 行", "", T_SRC]]
    buf = io.StringIO()
    _csv.writer(buf, lineterminator="\n").writerows([list(H.ROUTE_COLUMNS), route])
    routes = H.Routes.parse(buf.getvalue())
    t = H.swap_ready(routes,
                     H.Checks(checks, routes.ids), H.Traces(traces, routes.ids),
                     H.Registry(PERM_ROWS, H.PERM_COLUMNS, H.PERMISSIONS,
                                H.PERM_REQUIRES, "許す宣言の登録表"),
                     H.Registry(PLACE_ROWS, H.PLACE_COLUMNS, H.PLACEMENTS,
                                H.PLACE_REQUIRES, "検査の所属の登録表"), ASOF)
    assert t.report.ok
    got = t.rows[0].value
    assert got == my_value(route, checks, traces, PERM_ROWS, PLACE_ROWS)
    if permission == H.PERMISSIONS[2]:
        assert got == H.VALUES[3]
    elif permission == H.PERMISSIONS[3]:
        assert got == H.VALUES[4]
    elif placement != H.PLACEMENTS[0]:
        assert got == H.VALUES[1]
    elif field == "—":
        assert got == H.BETSUWAKU[5]
    elif observed in ("—", "0"):
        assert got == H.VALUES[2]
    else:
        assert got == H.VALUES[0]
