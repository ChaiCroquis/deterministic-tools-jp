"""idle_rows の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 読んだ範囲は 2 通りしかない。
  (a) rule 1 件ごとに 6 値のどれか 1 つが付き、**6 値の合計 = rule の数**、**5 値の合計 =
      参照候補の数**、**数表ごとの内訳の合計 = rule の数**、**由来ごとの行数の合計 =
      全体の行数**、**6 値ごとの行数の合計 = 全体の行数**、**一次の空白 + 二次の空白 =
      滞留している行数**で、**照合専用の行と基準日より後に有効になる行は滞留の行数に
      入らず**、**一次の空白の行は指している参照元が 0 件**、**二次の空白の行は指している
      参照元が 1 件以上で呼ばれている参照元が 0 件**、**理由コードを全部空にしても 6 値と
      滞留している行数が動かず**、判定部分に絶対パスが入らず、3 枚の行順を入れ替えても
      同じバイト列になる
  (b) 1 件も数えずに理由コードが返る(数えた rule や指紋を取りに行くと例外)
どちらの場合も、この部品は 4 枚の表を 1 文字も書き換えない。

数表を 1〜3 つ、その中の rule を 1〜2 件ずつ、由来を 3 通り、有効開始日を 3 通り(空 /
基準日より前 / 基準日より後)から引き、参照の宣言を 0〜3 本ずつ、問いを 1〜2 件引く。
理由コードも 5 通り(空 / 出典が要る 2 つ / 要らない 1 つ / 登録表に無い 1 つ)から引くので、
6 値のどれも出る。3 割くらいの確率でどこか 1 か所を崩す(10 通り = 1 件も数えずに止まる
理由コード 10 個に 1 対 1 で対応)。derandomize=True で毎回同じ入力列を使い、database=None
で例を保存しない。

**6 値の分け方はテストの側で別に実装している**(部品の judge / six を呼ばない)。
2 本目は「照合専用の行と未来有効行は滞留に入らない」ことだけを、総当たりで見ている。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from hypothesis import event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import idle_rows as H  # noqa: E402

SOURCE = "合成の出典メモ(架空)L1"
ASOF = "2026-05-20"
MUKASHI, MIRAI_HI = "2026-01-01", "2027-09-01"
JIMAE, JOURYUU, SHOUGOU = H.ORIGINS
SHIKI_KIND, TOI_KIND = H.REF_KINDS
NYUURYOKU, CHOKUSETSU, KEIYU = H.HOWS
IRU, IRANAI = H.SOURCE_NEEDED

REGISTRY_ROWS = [["未実装", "参照する側の実装がまだ", IRU],
                 ["未収録の相手がいる", "参照する側の行がまだ台帳に無い", IRU],
                 ["未来の有効行", "有効開始日が基準日より後", IRANAI]]
NEEDS_SOURCE = {"未実装", "未収録の相手がいる"}
REASONS = ("", "未実装", "未収録の相手がいる", "未来の有効行", "画像 PDF")

KOWASHIKATA = ("出典を空にする", "同じ rule id を台帳に 2 行書く",
               "同じ rule id を別の数表にも書く", "同じ参照元と rule の組を 2 行書く",
               "理由の出典を空にする", "照合専用の行に理由コードを入れる",
               "照合専用の行を指す宣言を足す",
               "問いの要る参照元をどの宣言にも無い id にする",
               "参照元の種別を問いにして一覧に無い id にする",
               "参照元の種別と参照の仕方を食い違わせる")


def classify(daichou: list[list[str]], sengen: list[list[str]],
             toi: list[list[str]]) -> list[tuple[str, str]]:
    """rule ごとの (rule id, 6 値) をテストの側で別に出す(部品を呼ばない)。"""
    table_of = {r[1]: r[0] for r in daichou}
    surveyed = {table_of[r[2]] for r in sengen if r[2] in table_of}
    question_ids = {q[0] for q in toi}
    needed = {q[2] for q in toi}
    out: list[tuple[str, str]] = []
    for table_id, rule_id, _rows, origin, valid_from, *_rest in daichou:
        mine = [r for r in sengen if r[2] == rule_id]
        called = [r for r in mine
                  if (r[0] in question_ids if r[1] == TOI_KIND else r[0] in needed)]
        if origin == SHOUGOU:
            out.append((rule_id, "照合専用"))
        elif valid_from and valid_from > ASOF:
            out.append((rule_id, "基準日より後に有効になる行"))
        elif table_id not in surveyed:
            out.append((rule_id, "参照の宣言が無い"))
        elif not mine:
            out.append((rule_id, "どの参照元からも参照されない"))
        elif not called:
            out.append((rule_id, "参照元は在るが問いから呼ばれない"))
        else:
            out.append((rule_id, "参照されている"))
    return sorted(out)


@st.composite
def 合成の4枚(draw: st.DrawFn) -> dict[str, object]:
    """行の台帳 / 参照の宣言表 / 問いの一覧 / 理由コードの登録表(と崩し方)を作る。"""
    tables = [f"H{i + 1}" for i in range(draw(st.integers(1, 3)))]

    daichou: list[list[str]] = []
    for n, table_id in enumerate(tables):
        for k in range(draw(st.integers(1, 2))):
            first = n == 0 and k == 0
            # 1 行目は照合専用にしない(= 宣言の宛先を必ず 1 つ残す)
            origin = JIMAE if first else draw(st.sampled_from(H.ORIGINS))
            valid_from = draw(st.sampled_from(("", MUKASHI, MIRAI_HI)))
            reason = "" if origin == SHOUGOU else draw(st.sampled_from(REASONS))
            rsrc = SOURCE if reason in NEEDS_SOURCE else ""
            daichou.append([table_id, f"K{n + 1}{k + 1}", str(draw(st.integers(0, 9))),
                            origin, valid_from, reason, rsrc, SOURCE])

    eligible = [r[1] for r in daichou if r[3] != SHOUGOU]

    sengen: list[list[str]] = [["F1", SHIKI_KIND, eligible[0], NYUURYOKU, SOURCE]]
    for rule_id in eligible:
        if rule_id != eligible[0] and draw(st.booleans()):
            sengen.append(["F1", SHIKI_KIND, rule_id,
                           draw(st.sampled_from((NYUURYOKU, KEIYU))), SOURCE])
        if draw(st.booleans()):
            sengen.append(["F2", SHIKI_KIND, rule_id,
                           draw(st.sampled_from((NYUURYOKU, KEIYU))), SOURCE])
        if draw(st.booleans()):
            sengen.append(["Q1", TOI_KIND, rule_id, CHOKUSETSU, SOURCE])
    # 台帳に無い rule を指す宣言(= 逆向きの欠け。止まらずに別枠の一覧へ出る)
    if draw(st.booleans()):
        sengen.append(["F3", SHIKI_KIND, "K99", NYUURYOKU, SOURCE])

    used = sorted({r[0] for r in sengen if r[1] == SHIKI_KIND})
    toi: list[list[str]] = [["Q1", "合成の求める値(架空)", draw(st.sampled_from(used)),
                             ASOF, H.SWAPS[0], SOURCE]]
    if draw(st.booleans()):
        toi.append(["Q2", "合成の求める値(架空)", draw(st.sampled_from(used)),
                    "", "", SOURCE])

    kowasu = draw(st.sampled_from([None] * 23 + list(KOWASHIKATA)))
    if kowasu == KOWASHIKATA[0]:
        daichou[0][7] = ""
    elif kowasu == KOWASHIKATA[1]:
        daichou.append(list(daichou[0]))
    elif kowasu == KOWASHIKATA[2]:
        daichou.append(["H9"] + list(daichou[0][1:]))
    elif kowasu == KOWASHIKATA[3]:
        sengen.append(list(sengen[0]))
    elif kowasu == KOWASHIKATA[4]:
        daichou[0][5], daichou[0][6] = "未実装", ""
    elif kowasu == KOWASHIKATA[5]:
        daichou.append(["H8", "K81", "1", SHOUGOU, "", "未実装", SOURCE, SOURCE])
    elif kowasu == KOWASHIKATA[6]:
        daichou.append(["H8", "K81", "1", SHOUGOU, "", "", "", SOURCE])
        sengen.append(["F7", SHIKI_KIND, "K81", NYUURYOKU, SOURCE])
    elif kowasu == KOWASHIKATA[7]:
        toi[0][2] = "F9"
    elif kowasu == KOWASHIKATA[8]:
        sengen.append(["Q9", TOI_KIND, eligible[0], CHOKUSETSU, SOURCE])
    elif kowasu == KOWASHIKATA[9]:
        sengen[0][3] = CHOKUSETSU

    def csv(head: tuple[str, ...], body: list[list[str]]) -> str:
        return "\n".join([",".join(head)] + [",".join(r) for r in body])

    return {"daichou": csv(H.DAICHOU_COLUMNS, daichou),
            "sengen": csv(H.SENGEN_COLUMNS, sengen),
            "toi": csv(H.TOI_COLUMNS, toi),
            "riyuu": csv(H.RIYUU_COLUMNS, REGISTRY_ROWS),
            "daichou_rows": daichou, "sengen_rows": sengen, "toi_rows": toi,
            "kowasu": kowasu}


@settings(max_examples=200, derandomize=True, database=None, deadline=None)
@given(plan=合成の4枚())
def test_いつも成り立つこと_数えた_rule_か理由コードか(plan: dict[str, object]) -> None:
    ledger = H.Ledger.parse(plan["daichou"])          # type: ignore[arg-type]
    decls = H.Declarations.parse(plan["sengen"])      # type: ignore[arg-type]
    questions = H.Questions.parse(plan["toi"])        # type: ignore[arg-type]
    registry = H.Registry.parse(plan["riyuu"])        # type: ignore[arg-type]
    t = H.idle_rows(ledger, decls, questions, registry)

    expect_stop = plan["kowasu"] is not None
    c = t.counts()
    six = c["6 値"]
    assert c["行の台帳の行数"] == len(plan["daichou_rows"])   # type: ignore[arg-type]
    assert c["参照の宣言表の行数"] == len(plan["sengen_rows"])  # type: ignore[arg-type]
    assert c["問いの数"] == len(plan["toi_rows"])              # type: ignore[arg-type]
    assert {j.result for j in t.judged} <= set(H.KEKKA)
    assert all(isinstance(v, int) for v in six.values())      # type: ignore[union-attr]

    if expect_stop:
        event("(b) 1 件も数えずに止まった")
        assert t.report.ok is False and t.report.pending
        assert {p.reason for p in t.report.pending} <= set(H.TABLE_REASONS)
        assert t.judged == ()
        assert six == {k: 0 for k in H.KEKKA}
        assert t.denominator == 0 and t.referenced_rows() == 0
        assert t.idle_row_counts() == {"一次の空白": 0, "二次の空白": 0, "合計": 0}
        for call in (t.judgement_bytes, t.sha256):
            with pytest.raises(RuntimeError):
                call()
    else:
        event("(a) 数えた")
        assert t.report.ok is True
        # rule 1 件ごとに 6 値のどれか 1 つ。テスト側の別実装と一致する
        mine = sorted((j.row.rule_id, j.result) for j in t.judged)
        assert mine == classify(plan["daichou_rows"], plan["sengen_rows"],
                                plan["toi_rows"])
        # 6 通りの数え方が全て合う
        assert sum(six.values()) == t.rule_denominator()
        assert sum(six[k] for k in H.GOCHI) == t.denominator
        tables = t.by_table()
        origins = t.by_origin()
        assert sum(int(r["rule の数"]) for r in tables) == t.rule_denominator()
        assert sum(int(r["rule の数"]) for r in origins) == t.rule_denominator()
        assert sum(int(r["行数"]) for r in tables) == t.total_rows()
        assert sum(int(r["行数"]) for r in origins) == t.total_rows()
        assert sum(t.rows_by_result().values()) == t.total_rows()
        for k in H.KEKKA:
            assert sum(int(r["6 値"][k]) for r in tables) == six[k]
            assert sum(int(r["6 値"][k]) for r in origins) == six[k]
        idle = t.idle_row_counts()
        assert idle["一次の空白"] + idle["二次の空白"] == idle["合計"]
        assert len(t.listed()) == len(H.KEKKA)
        for j in t.judged:
            # 照合専用の行と基準日より後に有効になる行は滞留に入らない
            if j.row.origin == SHOUGOU:
                assert j.result == "照合専用" and j.idle is False
            if j.row.valid_from == MIRAI_HI and j.row.origin != SHOUGOU:
                assert j.result == "基準日より後に有効になる行"
                assert j.idle is False and j.candidate is False
            # 一次の空白は指している参照元が 0 件、二次の空白は 1 件以上で呼ばれて 0 件
            if j.result == H.TAIRYUU[0]:
                assert j.refs == () and j.called == ()
            if j.result == H.TAIRYUU[1]:
                assert j.refs and j.called == ()
            if j.result == H.KEKKA[0]:
                assert j.refs and j.called
        body = t.judgement_bytes().decode("utf-8")
        for word in ("読んだ条件", "絶対パス", str(ROOT)):
            assert word not in body
        # 理由コードを全部空にしても 6 値と滞留している行数は動かない
        bare_rows = [list(r) for r in plan["daichou_rows"]]   # type: ignore[union-attr]
        for row in bare_rows:
            row[5], row[6] = "", ""
        bare_text = "\n".join([",".join(H.DAICHOU_COLUMNS)]
                              + [",".join(r) for r in bare_rows])
        bare = H.idle_rows(H.Ledger.parse(bare_text), decls, questions, registry)
        assert bare.report.ok and bare.six() == six
        assert bare.idle_row_counts() == idle
        # 3 枚の行順を入れ替えても同じバイト列
        how = questions.swap or H.SWAPS[0]
        again = H.idle_rows(ledger.swapped(how), decls.swapped(how),
                            questions.swapped(how), registry)
        assert again.sha256() == t.sha256()
        assert again.judgement_bytes() == t.judgement_bytes()

    # どちらの場合も入力は 1 文字も書き換わらない
    assert H.Ledger.parse(plan["daichou"]).items == ledger.items        # type: ignore[arg-type]
    assert H.Declarations.parse(plan["sengen"]).items == decls.items    # type: ignore[arg-type]
    assert H.Questions.parse(plan["toi"]).items == questions.items      # type: ignore[arg-type]
    assert H.Registry.parse(plan["riyuu"]).items == registry.items      # type: ignore[arg-type]


@settings(max_examples=300, derandomize=True, database=None)
@given(origin=st.sampled_from(H.ORIGINS),
       valid_from=st.sampled_from(("", MUKASHI, MIRAI_HI)),
       pointed=st.booleans(), called=st.booleans(),
       rows=st.integers(0, 9))
def test_照合専用と未来有効行は滞留に入らない(origin: str, valid_from: str,
                                              pointed: bool, called: bool,
                                              rows: int) -> None:
    """由来 × 有効開始日 × 指されているか × 呼ばれているか の総当たり。

    滞留に入るのは「由来が照合専用でなく、有効開始日が基準日より後でもない行」のうち、
    指す参照元が無い行(一次の空白)と、指す参照元は在るが呼ばれていない行(二次の空白)
    だけだ。**照合専用と未来有効行は、指されていようといまいと滞留の行数に入らない。**
    """
    daichou = [",".join(H.DAICHOU_COLUMNS),
               f"H1,K11,{rows},{origin},{valid_from},,,{SOURCE}",
               f"H1,K12,1,{JOURYUU},,,,{SOURCE}"]
    sengen = [",".join(H.SENGEN_COLUMNS), f"F1,{SHIKI_KIND},K12,{NYUURYOKU},{SOURCE}"]
    points = pointed and origin != SHOUGOU
    if points:
        sengen.append(f"F2,{SHIKI_KIND},K11,{NYUURYOKU},{SOURCE}")
    # Q1 は必ず F1 を要るので K12 は常に参照されている。K11 を呼ぶのは Q2 だけ
    toi = [",".join(H.TOI_COLUMNS),
           f"Q1,合成の求める値(架空),F1,{ASOF},{H.SWAPS[0]},{SOURCE}"]
    if points and called:
        toi.append(f"Q2,合成の求める値(架空),F2,,,{SOURCE}")
    t = H.idle_rows(H.Ledger.parse("\n".join(daichou)),
                    H.Declarations.parse("\n".join(sengen)),
                    H.Questions.parse("\n".join(toi)), H.Registry.parse(
                        "\n".join([",".join(H.RIYUU_COLUMNS)]
                                  + [",".join(r) for r in REGISTRY_ROWS])))
    assert t.report.ok
    assert next(x for x in t.judged if x.row.rule_id == "K12").result == H.KEKKA[0]
    j = next(x for x in t.judged if x.row.rule_id == "K11")
    if origin == SHOUGOU:
        assert j.result == "照合専用"
    elif valid_from == MIRAI_HI:
        assert j.result == "基準日より後に有効になる行"
    elif not pointed:
        assert j.result == H.TAIRYUU[0]
    elif called:
        assert j.result == H.KEKKA[0]
    else:
        assert j.result == H.TAIRYUU[1]
    idle = t.idle_row_counts()
    if j.idle:
        assert idle["合計"] == rows
        assert idle["一次の空白"] == (rows if j.result == H.TAIRYUU[0] else 0)
        assert idle["二次の空白"] == (rows if j.result == H.TAIRYUU[1] else 0)
    else:
        assert idle["合計"] == 0
    assert sum(t.six().values()) == 2 == t.rule_denominator()
    assert t.total_rows() == rows + 1
