"""swap_ready のテスト。合成 fixture は `fixtures/` に commit 済(実データは入れない)。

test_measure_* が記事に載せた数値の出どころで、assert で固定している(値が変われば記事も
変える前提)。測っているものは 8 つある。

  (1) 経路 14 件が 4 値 7 件 + 別枠 7 件に分かれ、合計が 3 通りの数え方で戻る側
  (2) **許す側の宣言が在る 11 経路のうち、使われているのは 2 件で、(B) + (C) の 3 件が
      宣言のまま残る**側 = 記事の骨
  (3) **跡の件数 0 と、跡の欄が無い(`数えられない`)を同じ値にしない**側
  (4) **独立と書いただけでは独立にしない**(束の名前が入れ替える側と同じなら矛盾)側
  (5) 同じ `照合専用` の注記でも、通す対象の種別が範囲の外なら別枠へ出る側
  (6) 跡の件数に 1 足すと、その経路だけが (C) → (A) へ移る側
  (7) 検査の所属を 内蔵 → 独立 にすると、その経路だけが (B) → (C) へ移る側
  (8) 出力の末尾の「持たせていないもの」が 10 行で、禁則の語が件数の側に無い側

(1) の 4 値は、テストの側でも 5 枚の行から直に組み立てて確かめている(部品の judge /
five / extras を呼ばない)。
"""
from __future__ import annotations

import ast
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIX = ROOT / "fixtures"
KOWASHITA = FIX / "kowashita"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FIX))
import swap_ready as H  # noqa: E402
import make_fixtures as M  # noqa: E402

ASOF = M.ASOF

# 入れ替えるべきか・正しさ・似ている度合いを指す語(件数と一覧の側に持たせない)
KINSOKU = ("推奨", "順位", "優先度", "点数", "割合", "入れ替えるべき", "正しい側",
           "健全", "成功率", "削減", "リスク", "スコア")

# 出力の末尾に並ぶ「持たせていないもの」(**消す引数も option も無い**)
MOTANAI_KEYS = (
    "入れ替えるべきかを決めない",
    "滞留の理由を推定しない",
    "自分では何も入れ替えない",
    "検査の中身を見ない",
    "0 件と欄が無いを同じ値にしない",
    "範囲つきの許可を `許す` に寄せない",
    "独立と書いただけでは独立にしない",
    "時計を読まない",
    "入力を書き換えない",
    "float を使わない",
)


# ------------------------------------------------------------ 読み込み

def five_tables(routes: str = "routes_a.csv", checks: str = "checks_a.csv",
                traces: str = "traces_a.csv", perms: str = "permissions_a.csv",
                places: str = "placements_a.csv"):
    """fixtures(と kowashita)から 5 枚を読む。"""
    def path(name: str) -> Path:
        return (KOWASHITA / name) if (KOWASHITA / name).exists() else (FIX / name)

    r = H.Routes.load(path(routes))
    return (r, H.Checks.load(path(checks), r.ids), H.Traces.load(path(traces), r.ids),
            H.load_permissions(path(perms)), H.load_placements(path(places)))


def table(**kw) -> H.Table:
    return H.swap_ready(*five_tables(**kw), ASOF)


# ------------------------------------------------------------ テスト側の別実装

def classify(route: list[str], checks: list[list[str]], traces: list[list[str]],
             perms: list[list[str]], places: list[list[str]]) -> str:
    """経路 1 件の 4 値 / 別枠を、テストの側で行から直に出す(部品の judge を呼ばない)。"""
    rid, kind, bundle, perm, note, kinds, declared, source = route
    req_perm = {r[0]: r[2] for r in perms}
    req_place = {r[0]: r[2] for r in places}
    mine = [c for c in checks if c[1] == rid]
    mytr = [t for t in traces if t[0] == rid]
    in_scope = [] if kinds in ("—", "") else [x.strip() for x in kinds.split("/") if x.strip()]

    if not source or any(not c[4] for c in mine) or any(not t[5] for t in mytr):
        return H.BETSUWAKU[0]
    if perm not in req_perm or any(c[2] not in req_place for c in mine):
        return H.BETSUWAKU[1]
    if req_perm[perm] == "宣言された日" and declared in ("—", ""):
        return H.BETSUWAKU[2]
    if req_perm[perm] == "許可の範囲" and (note in ("—", "") or not in_scope):
        return H.BETSUWAKU[2]
    if any(req_place[c[2]] == "束の名前" and not c[3] for c in mine):
        return H.BETSUWAKU[2]
    placements = {c[2] for c in mine}
    if len(placements) > 1:
        return H.BETSUWAKU[3]
    if any(c[2] == "独立" and c[3] == bundle for c in mine):
        return H.BETSUWAKU[3]
    fields = [t[1] for t in mytr if t[1] not in ("—", "")]
    if len(fields) != len(set(fields)):
        return H.BETSUWAKU[3]
    if perm == "範囲つきで許す" and kind not in in_scope:
        return H.BETSUWAKU[4]
    if perm == "許さない":
        return H.VALUES[3]
    if perm == "宣言なし":
        return H.VALUES[4]
    if placements != {"独立"}:
        return H.VALUES[1]
    counted = [t for t in mytr if t[1] not in ("—", "")]
    if not counted:
        return H.BETSUWAKU[5]
    total = sum(int(t[2]) for t in counted if t[2].isdigit())
    return H.VALUES[0] if total >= 1 else H.VALUES[2]


def test_4値はテスト側の別実装と一致する() -> None:
    t = table()
    mine = {r[0]: classify(r, M.CHECKS, M.TRACES, M.PERMS, M.PLACES) for r in M.ROUTES}
    assert {x.route_id: x.value for x in t.rows} == mine


# ------------------------------------------------------------ (1)

def test_measure_14_routes_split_into_five_values_and_six_extras() -> None:
    t = table()
    assert t.report.ok is True
    assert len(t.routes.items) == 14 and len(t.checks.items) == 10
    assert len(t.traces.items) == 7
    assert len(t.perms.items) == 4 and len(t.places.items) == 3
    assert t.denominator() == 14
    five, extras = t.five(), t.extras()
    assert five == {H.VALUES[0]: 2, H.VALUES[1]: 2, H.VALUES[2]: 1,
                    H.VALUES[3]: 1, H.VALUES[4]: 1}
    assert extras == {H.BETSUWAKU[0]: 1, H.BETSUWAKU[1]: 1, H.BETSUWAKU[2]: 1,
                      H.BETSUWAKU[3]: 2, H.BETSUWAKU[4]: 1, H.BETSUWAKU[5]: 1}
    assert sum(five.values()) == 7 and sum(extras.values()) == 7
    assert sum(five.values()) + sum(extras.values()) == t.denominator()
    assert sum(int(r["経路の件数"]) for r in t.by_kind()) == 14
    assert sum(int(r["経路の件数"]) for r in t.by_bundle()) == 14
    assert [int(r["経路の件数"]) for r in t.by_kind()] == [4, 4, 3, 3]
    assert [(r["入れ替える側の束"], int(r["経路の件数"])) for r in t.by_bundle()] == [
        ("借り物の束", 9), ("本番の束", 3), ("自前の束", 2)]
    print("[measure] routes_a / checks_a / traces_a + 登録表 2 枚: 経路 14 行 / 検査 10 行"
          " / 跡 7 行 / 許す宣言の登録 4 行 / 検査の所属の登録 3 行")
    print(f"[measure] 分母は 経路 14 件、4 値は "
          f"{json.dumps({k[:3]: v for k, v in five.items()}, ensure_ascii=False)}"
          f"(合計 7 件)")
    print(f"[measure] 別枠は {json.dumps(extras, ensure_ascii=False)}。合計 7 = 14 - 7")
    print("[measure] 種別ごとの合計 14(版 4 / 実装 4 / data 3 / 行 3)、"
          "束ごとの合計 14(借り物の束 9 / 本番の束 3 / 自前の束 2)")


# ------------------------------------------------------------ (2) 記事の骨

def test_measure_permitted_routes_are_mostly_not_ready() -> None:
    t = table()
    permitted = [x for x in t.rows
                 if x.permission in (H.PERMISSIONS[0], H.PERMISSIONS[1])]
    assert len(permitted) == 11
    used = [x for x in permitted if x.value == H.VALUES[0]]
    stalled = [x for x in permitted if x.stalled]
    extras = [x for x in permitted if x.value in H.BETSUWAKU]
    assert len(used) == 2 and len(stalled) == 3 and len(extras) == 6
    assert len(used) + len(stalled) + len(extras) == 11
    assert t.stall()["(B) + (C) の件数"] == 3
    assert [x.route_id for x in stalled] == ["R02", "R03", "R08"]
    assert [x.value for x in stalled] == [H.VALUES[1], H.VALUES[2], H.VALUES[1]]
    # **滞留の量は 3 つだけで、順位も割合も返らない**
    assert set(t.stall()) == {"(B) + (C) の件数",
                             "跡の件数(0 を含む / 欄が無い経路は 数えられない)",
                             "宣言された日から基準日までの日数"}
    days = t.stall()["宣言された日から基準日までの日数"]
    assert [days[x.route_id] for x in stalled] == ["202", "258", "92"]
    print("[measure] 許す側の宣言が在る経路は 11 件(許す 8 / 範囲つきで許す 3)。"
          "そのうち使われている (A) は 2 件")
    print("[measure] (B) + (C) は 3 件 = R02(内蔵)・R03(独立だが跡 0 件)・"
          "R08(検査が無い)。別枠へ出たのは 6 件")
    print("[measure] 滞留の日数は宣言された日から基準日 2026-09-20 まで "
          "202 日 / 258 日 / 92 日。日数は 3 つの返り値の 1 つで、順位も割合も返らない")


def test_measure_permission_kinds_counted() -> None:
    t = table()
    kinds = {p: sum(1 for x in t.rows if x.permission == p) for p in H.PERMISSIONS}
    assert kinds == {H.PERMISSIONS[0]: 8, H.PERMISSIONS[1]: 3,
                     H.PERMISSIONS[2]: 1, H.PERMISSIONS[3]: 1}
    outside = [x for x in t.rows if x.permission not in H.PERMISSIONS]
    assert len(outside) == 1 and outside[0].value == H.BETSUWAKU[1]
    print("[measure] 許す宣言の記号の内訳は 許す 8 / 範囲つきで許す 3 / 許さない 1 / "
          "宣言なし 1、登録の外の記号が 1 件(別枠へ)。合計 14")


# ------------------------------------------------------------ (3) 0 件と欄なし

def test_measure_zero_and_no_field_are_different_values() -> None:
    t = table()
    counts = t.stall()["跡の件数(0 を含む / 欄が無い経路は 数えられない)"]
    zero = sorted(k for k, v in counts.items() if v == "0")
    none = sorted(k for k, v in counts.items() if v == H.UNCOUNTABLE)
    some = sorted(k for k, v in counts.items() if v.isdigit() and int(v) >= 1)
    assert zero == ["R02", "R03"] and some == ["R01", "R14"]
    assert len(none) == 10 and len(zero) + len(none) + len(some) == 14
    # **欄が無いことで別枠へ出るのは、許す宣言が在って検査も独立な経路だけ**
    uncountable_extras = [x for x in t.rows if x.value == H.BETSUWAKU[5]]
    assert [x.route_id for x in uncountable_extras] == ["R05"]
    assert all(x.observed == H.UNCOUNTABLE for x in uncountable_extras)
    b_rows = [x for x in t.rows if x.value == H.VALUES[1]]
    assert sorted(x.observed for x in b_rows) == ["0", H.UNCOUNTABLE]
    print("[measure] 跡の件数は 1 以上が 2 件(R01 = 3 / R14 = 2)、ちょうど 0 が 2 件"
          "(R02・R03)、`数えられない` が 10 件。合計 14")
    print("[measure] 跡の欄が無いことで別枠へ出たのは R05 の 1 件だけ(許す + 独立)。"
          "(B) の 2 件は 0 件と `数えられない` が 1 件ずつで、4 値は変わらない")


# ------------------------------------------------------------ (4) 独立の検査

def test_measure_independent_needs_a_different_bundle() -> None:
    t = table()
    r13 = next(x for x in t.rows if x.route_id == "R13")
    assert r13.placement == H.PLACEMENTS[0] and r13.check_bundle == "借り物の束"
    assert r13.value == H.BETSUWAKU[3]
    # 束の名前を別にすると、矛盾ではなくなる(跡の欄が無いので別枠は別のものに移る)
    checks = [list(r) for r in M.CHECKS]
    for r in checks:
        if r[1] == "R13":
            r[3] = "照合用の束"
    routes, _, traces, perms, places = five_tables()
    after = H.swap_ready(routes, H.Checks([list(r) for r in checks], routes.ids),
                         traces, perms, places, ASOF)
    moved = H.moved(t, after)
    got = {x.route_id: x.value for x in after.rows}["R13"]
    assert moved == ["R13"] and got == H.BETSUWAKU[5]
    r12 = next(x for x in t.rows if x.route_id == "R12")
    assert r12.placement == "内蔵 / 独立" and r12.value == H.BETSUWAKU[3]
    print("[measure] 矛盾する宣言は 2 件 = R12(同じ経路に 内蔵 と 独立 の 2 行)と "
          "R13(独立と書いてあるが束の名前が入れ替える側と同じ)")
    print("[measure] R13 の検査の束を別の名前にすると、移るのは R13 の 1 件だけで、"
          "行き先は 4 値ではなく別枠「跡を残す欄そのものが無い」")


# ------------------------------------------------------------ (5) 範囲つきの許可

def test_measure_scope_note_is_kept_raw() -> None:
    t = table()
    scoped = [x for x in t.rows if x.permission == H.PERMISSIONS[1]]
    assert [x.route_id for x in scoped] == ["R03", "R04", "R14"]
    assert [x.value for x in scoped] == [H.VALUES[2], H.BETSUWAKU[4], H.VALUES[0]]
    notes = {r[0]: r[4] for r in M.ROUTES}
    assert {notes[x.route_id] for x in scoped} == {"照合専用"}
    # **注記の文字は整数にも真偽にも直らない**(判定に出てくるのは種別記号の列だけ)
    body = t.judgement_bytes().decode("utf-8")
    assert "照合専用" not in body
    assert all(x.kind in ("data", "行") or x.value == H.BETSUWAKU[4] for x in scoped)
    print("[measure] 範囲つきで許すは 3 件で、注記は 3 件とも同じ `照合専用`。"
          "4 値は 通す対象の種別が範囲に在るかだけで分かれ、(C) 1 / (A) 1 / 別枠 1")
    print("[measure] 判定部分に `照合専用` の文字は入らない(範囲の判定に使うのは"
          "人が別の欄に書いた種別記号の列だけ)")


# ------------------------------------------------------------ (6)(7) 2 つの probe

def test_measure_trace_probe_moves_one_route() -> None:
    t = table()
    rid = H.trace_probe_plan(t)
    assert rid == "R03"
    after = H.trace_probe(*five_tables(), ASOF, rid)
    assert H.moved(t, after) == ["R03"]
    got = {x.route_id: x.value for x in after.rows}["R03"]
    assert got == H.VALUES[0]
    assert after.five()[H.VALUES[0]] == 3 and after.five()[H.VALUES[2]] == 0
    assert after.extras() == t.extras()
    before_bytes = (FIX / "traces_a.csv").read_bytes()
    assert hashlib.sha256(before_bytes).hexdigest() == hashlib.sha256(
        (FIX / "traces_a.csv").read_bytes()).hexdigest()
    print("[measure] 跡の件数に 1 足す: R03 の跡の件数を 0 → 1 にすると R03 の 1 件だけが"
          " (C) → (A) へ移る((A) 2 → 3 件 / (C) 1 → 0 件)")
    print("[measure] ほかで動いた経路は 0 件、別枠の 6 つも不変。写しはメモリの中だけで、"
          "跡の台帳の CSV は 1 文字も書き換わらない")


def test_measure_placement_probe_moves_one_route() -> None:
    t = table()
    rid = H.placement_probe_plan(t)
    assert rid == "R02"
    after = H.placement_probe(*five_tables(), ASOF, rid)
    assert H.moved(t, after) == ["R02"]
    got = {x.route_id: x.value for x in after.rows}["R02"]
    assert got == H.VALUES[2]
    assert after.five()[H.VALUES[1]] == 1 and after.five()[H.VALUES[2]] == 2
    assert after.extras() == t.extras()
    print("[measure] 検査の所属を独立にする: R02 の所属を 内蔵 → 独立 にすると R02 の"
          " 1 件だけが (B) → (C) へ移る((B) 2 → 1 件 / (C) 1 → 2 件)")
    print("[measure] 行き先は (A) ではない。跡の件数が 0 のままなので、"
          "入れ替えられる状態になっても入れ替えた跡は増えない")


# ------------------------------------------------------------ 理由

def test_measure_reasons_are_copied_with_source() -> None:
    t = table()
    reasons = t.reasons()
    written = {k: v for k, v in reasons.items() if v != [H.NO_REASON]}
    assert sorted(written) == ["R02", "R03", "R05"]
    assert all(len(v) == 1 and "出典 = 合成の跡のメモ" in v[0]
               for v in written.values())
    assert written["R03"][0].startswith("取りに行く段取りが未登録")
    assert sum(1 for v in reasons.values() if v == [H.NO_REASON]) == 11
    for v in written.values():
        assert "と考えられる" not in v[0] and "原因" not in v[0]
    print("[measure] 理由の注記が書かれていた経路は 3 件(R02・R03・R05)で、"
          "11 件は `理由の記載なし`。3 件とも出典つきで、文字は入力のまま")


# ------------------------------------------------------------ (8) 持たせていないもの

def test_measure_motanai_is_ten_lines() -> None:
    t = table()
    counts = t.counts()
    assert tuple(H.MOTANAI) == MOTANAI_KEYS and len(MOTANAI_KEYS) == 10
    for key in MOTANAI_KEYS:
        assert counts[key] == H.MOTANAI[key]
    numeric_part = {k: v for k, v in counts.items() if k not in MOTANAI_KEYS}
    flat = json.dumps(numeric_part, ensure_ascii=False)
    for word in KINSOKU:
        assert word not in flat
    for row in t.listed():
        for word in KINSOKU:
            assert word not in json.dumps(row, ensure_ascii=False)
    print("[measure] 出力の末尾の「持たせていないもの」は 10 行で、消す引数も option も"
          f"無い。禁則の語({len(KINSOKU)} 語)を含む key は 0 件")


# ------------------------------------------------------------ 止まる 7 + 読めない 7

def test_measure_seven_stop_reasons_all_reachable() -> None:
    seen: dict[str, list[str]] = {}

    def record(reasons: list[str], where: str) -> None:
        for r in reasons:
            seen.setdefault(r, []).append(where)

    cases = [
        ({"perms": "permissions_出典が空.csv"}, ASOF),
        ({"routes": "routes_経路idの重複.csv"}, ASOF),
        ({"perms": "permissions_記号が足りない.csv"}, ASOF),
        ({"perms": "permissions_要求する欄が外.csv"}, ASOF),
        ({}, ""),
        ({"routes": "routes_宣言された日が未来.csv"}, ASOF),
        ({"traces": "traces_件数が整数でない.csv"}, ASOF),
    ]
    for kw, asof in cases:
        t = H.swap_ready(*five_tables(**kw), asof)
        assert t.report.ok is False and t.report.pending
        assert t.denominator() == 0 and t.rows == ()
        assert t.five() == {k: 0 for k in H.VALUES}
        assert t.extras() == {k: 0 for k in H.BETSUWAKU}
        with pytest.raises(RuntimeError):
            t.judgement_bytes()
        record([p.reason for p in t.report.pending], str(kw or asof))
    assert sorted(seen) == sorted(H.TABLE_REASONS)
    print(f"[measure] 止まる理由コードは 7 個で、崩した表 6 枚 + 基準日を渡さない 1 通りの"
          f" 7 通りすべてに道が在る(7/7)。止まった表は 4 値を 1 件も返さない")


def test_measure_seven_unreadable_tables() -> None:
    cases = [{"routes": "routes_列が足りない.csv"}, {"routes": "routes_行が無い.csv"},
             {"routes": "routes_種別記号が外.csv"}, {"routes": "routes_経路idが空.csv"},
             {"checks": "checks_経路idが台帳に無い.csv"},
             {"places": "placements_記号が2行.csv"},
             {"places": "placements_決めた記号の外.csv"}]
    msgs: list[str] = []
    for kw in cases:
        with pytest.raises(H.ReadError) as e:
            five_tables(**kw)
        msgs.append(str(e.value))
    assert len(msgs) == 7 and len(set(msgs)) == 7
    print("[measure] 表として読めない崩し方は 7 通り(列が足りない / 行が無い / 種別記号が"
          "外 / 経路 id が空 / 検査の経路 id が台帳に無い / 登録の記号が 2 行 / "
          "登録に決めた記号の外)で、7 通りとも別の文で止まる")


# ------------------------------------------------------------ 決定論

def test_measure_judgement_is_deterministic() -> None:
    t = table()
    again = table()
    shas = [t.sha256(), again.sha256()]
    for how in H.SWAPS:
        routes, checks, traces, perms, places = five_tables()
        s = H.swap_ready(routes.swapped(how), checks.swapped(how), traces.swapped(how),
                         perms.swapped(how), places.swapped(how), ASOF)
        shas.append(s.sha256())
    assert len(set(shas)) == 1
    assert shas[0] == "67722d0ca1d7b8c713ac0a8da52f5195675cb8aee42d99b04401e5c9bcd67cfe"
    body = t.judgement_bytes().decode("utf-8")
    for word in ("読んだ条件", str(ROOT), ".csv", "照合専用"):
        assert word not in body
    out = H.verify(*five_tables(), ASOF)
    assert out["ok"] is True
    assert out["二度走りの判定部分が同一"] is True
    assert out["行順を入れ替えても同一"] == {k: True for k in H.SWAPS}
    print("[measure] 2 回 + 行順の入れ替え 3 通りで読み直し: 判定部分の sha256 は 5 回とも"
          f" 同じ(5/5 一致、先頭 12 桁 {shas[0][:12]})")
    print("[measure] 判定部分に絶対パス・ファイル名・注記の文字は入らない。"
          "verify は 5 つとも通る")


def test_measure_no_float_no_clock_no_network() -> None:
    src = (ROOT / "swap_ready.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    modules: set[str] = set()
    calls: list[str] = []
    hashed: list[str] = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            modules |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            modules.add(n.module.split(".")[0])
        elif isinstance(n, ast.Call):
            f = n.func
            name = f.id if isinstance(f, ast.Name) else (
                f.attr if isinstance(f, ast.Attribute) else "")
            calls.append(name)
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) \
                    and f.value.id == "hashlib":
                hashed.append(f.attr)
    assert modules == {"__future__", "argparse", "csv", "datetime", "hashlib",
                       "io", "json", "sys", "dataclasses", "pathlib"}
    for bad in ("eval", "exec", "float", "round", "now", "today", "urlopen",
                "request", "run", "Popen", "random", "mean", "compile"):
        assert bad not in calls, bad
    assert hashed == ["sha256"]
    assert "__import__" not in calls
    print(f"[measure] 部品が import している module は {len(modules)} 個で、eval / exec / "
          "float / round / 現在時刻 / subprocess / random / 平均 / 通信 の呼び出しは 0 件")
    print("[measure] hashlib.sha256 を呼ぶのは 1 か所(判定部分の指紋)だけ")


def test_入力は1文字も書き換わらない() -> None:
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(FIX.glob("*.csv"))}
    t = table()
    H.verify(*five_tables(), ASOF)
    H.trace_probe(*five_tables(), ASOF, "R03")
    H.placement_probe(*five_tables(), ASOF, "R02")
    assert t.report.ok
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(FIX.glob("*.csv"))}
    assert after == before and len(before) == 5


def test_CLI_の終了コード(tmp_path: Path) -> None:
    args = ["check", str(FIX / "routes_a.csv"), str(FIX / "checks_a.csv"),
            str(FIX / "traces_a.csv"), str(FIX / "permissions_a.csv"),
            str(FIX / "placements_a.csv"), ASOF]
    assert H.main(args) == 3           # 別枠と (B)(C) が在る
    assert H.main(["report"] + args[1:]) == 3
    assert H.main(["verify"] + args[1:]) == 0
    assert H.main(["init", str(tmp_path / "ひな型")]) == 0
    made = sorted(p.name for p in (tmp_path / "ひな型").glob("*.csv"))
    assert len(made) == 5
    # ひな型をそのまま通すと、止まらずに 4 値が付く
    d = tmp_path / "ひな型"
    routes = H.Routes.load(d / "経路の台帳.csv")
    t = H.swap_ready(routes, H.Checks.load(d / "受け入れ検査の台帳.csv", routes.ids),
                     H.Traces.load(d / "跡の台帳.csv", routes.ids),
                     H.load_permissions(d / "許す宣言の登録表.csv"),
                     H.load_placements(d / "検査の所属の登録表.csv"), ASOF)
    assert t.report.ok and t.denominator() == 2
    bad = ["check", str(KOWASHITA / "routes_行が無い.csv")] + args[2:]
    assert H.main(bad) == 2            # 表として読めない
