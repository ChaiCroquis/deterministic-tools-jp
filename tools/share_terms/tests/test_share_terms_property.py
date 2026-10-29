"""share_terms の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 読んだ範囲は 2 通りしかない。
  (a) rule 1 件ごとに 5 値のどれか 1 つが付き、**5 値の合計 = rule の数**、**4 値の合計 =
      許諾の名前が登録表に在る rule の数**、**出典元ごとと数表ごとの内訳の合計 = rule の数**、
      **出典元ごとの行数の合計 = 全体の行数**、**5 値ごとの行数の合計 = 全体の行数** で、
      **「揃っている」行はその許諾が要求すると宣言した欄が 1 つも空でなく**、**「欄が空」の行は
      空の欄が 1 つ以上あって名前つきの一覧に出て**、**出さないと宣言された行・出す宣言が無い
      行・別枠の行は空の欄を 1 件も持たず**、**配布物ごとに要る帰属の文字列は入力に書かれた
      文字列だけ**で、判定部分に絶対パスが入らず、4 枚の行順を入れ替えても同じバイト列になる
  (b) 1 件も数えずに理由コードが返る(数えた rule や指紋を取りに行くと例外)
どちらの場合も、この部品は 4 枚の表を 1 文字も書き換えない。

出典元を 1〜3 つ(許諾の名前が書かれている場所が在る / 無い を引く)、数表を 1〜2 つ、その中の
rule を 1〜2 件ずつ、許諾の名前を 3 通り(登録表に在る 2 つ + 無い 1 つ)、帰属の文字列・原文の
URL・版の指紋をそれぞれ 空 / 埋まっている から引き、外に出す宣言を 3 通りから引く。3 割くらいの
確率でどこか 1 か所を崩す(10 通り = 1 件も数えずに止まる理由コード 10 個に 1 対 1 で対応)。
derandomize=True で毎回同じ入力列を使い、database=None で例を保存しない。

**5 値の分け方はテストの側で別に実装している**(部品の judge / five を呼ばない)。
2 本目は「出さないと宣言された行と出す宣言が無い行は空の欄を持たない」ことだけを、総当たりで見る。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from hypothesis import event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import share_terms as H  # noqa: E402

SOURCE = "合成の出典メモ(架空)L1"
GOT_ON = "2026-05-11"
ATTR = "合成の帰属の文字列(架空)"
URL = "https://example.invalid/synthetic"
IRU, IRANAI = H.YESNO
DASU, DASANAI = H.DASU, H.DASANAI
ATTRIBUTION, SOURCE_URL, FINGERPRINT = H.FIELDS

L1, L2, L3 = "L1", "L2", "L3"          # L3 は登録表に無い名前
REGISTRY_ROWS = [[L1, IRU, IRANAI, IRANAI, SOURCE],
                 [L2, IRU, IRU, IRU, SOURCE]]
NEEDS = {L1: (ATTRIBUTION,), L2: (ATTRIBUTION, SOURCE_URL, FINGERPRINT)}

KOWASHIKATA = ("出典を空にする", "同じ rule id を台帳に 2 行書く",
               "同じ rule id を別の数表にも書く", "同じ組を目録に 2 行書く",
               "同じ出す先に 2 通りのファイル名を書く",
               "出さないと宣言された行を目録に載せる",
               "出す宣言の無い行を目録に載せる", "版の指紋を食い違わせる",
               "場所の無い出典元の行に許諾の名前を書く",
               "場所の在る出典元の行の許諾の名前を空にする")


def fp_of(origin_id: str) -> str:
    return f"fp{origin_id}"


def classify(daichou: list[list[str]]) -> list[tuple[str, str]]:
    """rule ごとの (rule id, 5 値) をテストの側で別に出す(部品を呼ばない)。"""
    column = {ATTRIBUTION: 5, SOURCE_URL: 6, FINGERPRINT: 7}
    out: list[tuple[str, str]] = []
    for row in daichou:
        share, name = row[8], row[4]
        if share == DASANAI:
            out.append((row[1], "出さないと宣言された"))
        elif share != DASU:
            out.append((row[1], "出す宣言が無い"))
        elif name not in NEEDS:
            out.append((row[1], "登録表に無い許諾の名前"))
        elif all(row[column[f]] for f in NEEDS[name]):
            out.append((row[1], "宣言が揃っている"))
        else:
            out.append((row[1], "出すと宣言されたが欄が空"))
    return sorted(out)


@st.composite
def 合成の4枚(draw: st.DrawFn) -> dict[str, object]:
    """行の台帳 / 許諾の登録表 / 出典元の台帳 / 配布物の目録(と崩し方)を作る。"""
    # 出典元。G1 は必ず「許諾の名前が書かれている場所」を持つ(宣言の宛先を 1 つ残す)
    origins: list[list[str]] = []
    places: dict[str, bool] = {}
    for n in range(draw(st.integers(1, 3))):
        origin_id = f"G{n + 1}"
        has_place = True if n == 0 else draw(st.booleans())
        places[origin_id] = has_place
        origins.append([origin_id, fp_of(origin_id), GOT_ON,
                        SOURCE if has_place else ""])

    daichou: list[list[str]] = []
    for n, table_id in enumerate(f"H{i + 1}" for i in range(draw(st.integers(1, 2)))):
        for k in range(draw(st.integers(1, 2))):
            first = n == 0 and k == 0
            origin_id = "G1" if first else draw(st.sampled_from(sorted(places)))
            # 名前の有無は、出典元の台帳の「場所」の有無と食い違わせない
            name = draw(st.sampled_from((L1, L2, L3))) if places[origin_id] else ""
            share = DASU if first else draw(st.sampled_from(H.SHARES))
            attribution = draw(st.sampled_from(("", ATTR)))
            source_url = draw(st.sampled_from(("", URL)))
            fingerprint = draw(st.sampled_from(("", fp_of(origin_id))))
            daichou.append([table_id, f"K{n + 1}{k + 1}",
                            str(draw(st.integers(0, 9))), origin_id, name,
                            attribution, source_url, fingerprint, share, SOURCE])

    dasu = [r[1] for r in daichou if r[8] == DASU]
    mokuroku: list[list[str]] = [["B1", "合成の配布(架空).json", dasu[0],
                                  H.SWAPS[0], SOURCE]]
    for rule_id in dasu[1:]:
        if draw(st.booleans()):
            mokuroku.append(["B1", "合成の配布(架空).json", rule_id, "", SOURCE])
    # 台帳に無い rule を指す目録の行(= 逆向きの欠け。止まらずに一覧へ出る)
    if draw(st.booleans()):
        mokuroku.append(["B2", "合成の配布 2(架空).json", "K99", "", SOURCE])

    kowasu = draw(st.sampled_from([None] * 23 + list(KOWASHIKATA)))
    if kowasu == KOWASHIKATA[0]:
        daichou[0][9] = ""
    elif kowasu == KOWASHIKATA[1]:
        daichou.append(list(daichou[0]))
    elif kowasu == KOWASHIKATA[2]:
        daichou.append(["H9"] + list(daichou[0][1:]))
    elif kowasu == KOWASHIKATA[3]:
        mokuroku.append(list(mokuroku[0]))
    elif kowasu == KOWASHIKATA[4]:
        mokuroku.append(["B1", "合成の別名(架空).json", "K99", "", SOURCE])
    elif kowasu == KOWASHIKATA[5]:
        daichou.append(["H8", "K81", "1", "G1", L1, "", "", "", DASANAI, SOURCE])
        mokuroku.append(["B1", "合成の配布(架空).json", "K81", "", SOURCE])
    elif kowasu == KOWASHIKATA[6]:
        daichou.append(["H8", "K81", "1", "G1", L1, "", "", "", "", SOURCE])
        mokuroku.append(["B1", "合成の配布(架空).json", "K81", "", SOURCE])
    elif kowasu == KOWASHIKATA[7]:
        daichou[0][7] = "fpG9"
    elif kowasu == KOWASHIKATA[8]:
        origins.append(["G8", fp_of("G8"), GOT_ON, ""])
        daichou.append(["H8", "K81", "1", "G8", L1, "", "", "", DASU, SOURCE])
    elif kowasu == KOWASHIKATA[9]:
        daichou.append(["H8", "K81", "1", "G1", "", "", "", "", DASU, SOURCE])

    def csv(head: tuple[str, ...], body: list[list[str]]) -> str:
        return "\n".join([",".join(head)] + [",".join(r) for r in body])

    return {"daichou": csv(H.DAICHOU_COLUMNS, daichou),
            "kyodaku": csv(H.KYODAKU_COLUMNS, REGISTRY_ROWS),
            "shutten": csv(H.SHUTTEN_COLUMNS, origins),
            "mokuroku": csv(H.MOKUROKU_COLUMNS, mokuroku),
            "daichou_rows": daichou, "mokuroku_rows": mokuroku,
            "shutten_rows": origins, "kowasu": kowasu}


@settings(max_examples=200, derandomize=True, database=None, deadline=None)
@given(plan=合成の4枚())
def test_いつも成り立つこと_数えた_rule_か理由コードか(plan: dict[str, object]) -> None:
    ledger = H.Ledger.parse(plan["daichou"])          # type: ignore[arg-type]
    registry = H.Registry.parse(plan["kyodaku"])      # type: ignore[arg-type]
    origins = H.Origins.parse(plan["shutten"])        # type: ignore[arg-type]
    bundles = H.Bundles.parse(plan["mokuroku"])       # type: ignore[arg-type]
    t = H.share_terms(ledger, registry, origins, bundles)

    expect_stop = plan["kowasu"] is not None
    c = t.counts()
    five = c["5 値"]
    assert c["行の台帳の行数"] == len(plan["daichou_rows"])     # type: ignore[arg-type]
    assert c["出典元の台帳の行数"] == len(plan["shutten_rows"])  # type: ignore[arg-type]
    assert c["配布物の目録の行数"] == len(plan["mokuroku_rows"])  # type: ignore[arg-type]
    assert {j.result for j in t.judged} <= set(H.KEKKA)
    assert all(isinstance(v, int) for v in five.values())      # type: ignore[union-attr]

    if expect_stop:
        event("(b) 1 件も数えずに止まった")
        assert t.report.ok is False and t.report.pending
        assert {p.reason for p in t.report.pending} <= set(H.TABLE_REASONS)
        assert t.judged == ()
        assert five == {k: 0 for k in H.KEKKA}
        assert t.settled_denominator == 0 and t.empty_field_count() == 0
        assert t.empty_fields() == [] and t.unregistered_licenses() == []
        for call in (t.judgement_bytes, t.sha256):
            with pytest.raises(RuntimeError):
                call()
    else:
        event("(a) 数えた")
        assert t.report.ok is True
        # rule 1 件ごとに 5 値のどれか 1 つ。テスト側の別実装と一致する
        mine = sorted((j.row.rule_id, j.result) for j in t.judged)
        assert mine == classify(plan["daichou_rows"])   # type: ignore[arg-type]
        # 5 通りの数え方が全て合う
        assert sum(five.values()) == t.rule_denominator()
        assert sum(five[k] for k in H.YOTSU) == t.settled_denominator
        tables, origins_out = t.by_table(), t.by_origin()
        assert sum(int(r["rule の数"]) for r in tables) == t.rule_denominator()
        assert sum(int(r["rule の数"]) for r in origins_out) == t.rule_denominator()
        assert sum(int(r["行数"]) for r in tables) == t.total_rows()
        assert sum(int(r["行数"]) for r in origins_out) == t.total_rows()
        assert sum(t.rows_by_result().values()) == t.total_rows()
        for k in H.KEKKA:
            assert sum(int(r["5 値"][k]) for r in tables) == five[k]
            assert sum(int(r["5 値"][k]) for r in origins_out) == five[k]
        listed = t.empty_fields()
        assert len(listed) == five[H.KEKKA[1]]
        assert sum(len(e["足りない欄"]) for e in listed) == t.empty_field_count()
        for j in t.judged:
            if j.result == H.KEKKA[0]:      # 揃っている = 要求された欄が 1 つも空でない
                assert j.missing == ()
                assert all(getattr(j.row, H.FIELD_COLUMNS[f]) for f in j.needs)
            elif j.result == H.KEKKA[1]:    # 欄が空 = 足りない欄が 1 つ以上
                assert j.missing and set(j.missing) <= set(j.needs)
            else:                           # 出さない / 宣言が無い / 別枠
                assert j.missing == () and j.needs == ()
        # 配布物ごとに要る帰属の文字列は、入力に書かれた文字列だけ
        written = {r[5] for r in plan["daichou_rows"]}   # type: ignore[union-attr]
        for r in t.attributions():
            assert all(text in written for text in r["要る帰属の文字列"])
            assert len(r["要る帰属の文字列"]) <= int(r["要る帰属の文字列(畳む前)"])
        body = t.judgement_bytes().decode("utf-8")
        for word in ("読んだ条件", "絶対パス", str(ROOT), GOT_ON):
            assert word not in body
        # 4 枚の行順を入れ替えても同じバイト列
        how = bundles.swap or H.SWAPS[0]
        again = H.share_terms(ledger.swapped(how), registry.swapped(how),
                              origins.swapped(how), bundles.swapped(how))
        assert again.sha256() == t.sha256()
        assert again.judgement_bytes() == t.judgement_bytes()

    # どちらの場合も入力は 1 文字も書き換わらない
    assert H.Ledger.parse(plan["daichou"]).items == ledger.items        # type: ignore[arg-type]
    assert H.Registry.parse(plan["kyodaku"]).items == registry.items    # type: ignore[arg-type]
    assert H.Origins.parse(plan["shutten"]).items == origins.items      # type: ignore[arg-type]
    assert H.Bundles.parse(plan["mokuroku"]).items == bundles.items     # type: ignore[arg-type]


@settings(max_examples=300, derandomize=True, database=None)
@given(share=st.sampled_from(H.SHARES), name=st.sampled_from((L1, L2, L3)),
       attribution=st.sampled_from(("", ATTR)), source_url=st.sampled_from(("", URL)),
       fingerprint=st.sampled_from(("", fp_of("G1"))), rows=st.integers(0, 9))
def test_出さない行と宣言の無い行は空の欄を持たない(share: str, name: str,
                                                      attribution: str,
                                                      source_url: str,
                                                      fingerprint: str,
                                                      rows: int) -> None:
    """外に出す宣言 × 許諾の名前 × 3 欄の埋まり方 の総当たり。

    欄が空に入るのは「出すと宣言され、名前が登録表に在り、要求された欄のどれかが空」の行
    だけだ。**出さないと宣言された行・出す宣言が無い行・名前が登録表に無い行は、欄がいくら
    空でも空の欄を 1 件も持たない。**
    """
    daichou = [",".join(H.DAICHOU_COLUMNS),
               f"H1,K11,{rows},G1,{name},{attribution},{source_url},"
               f"{fingerprint},{share},{SOURCE}",
               f"H1,K12,1,G1,{L1},{ATTR},,,{DASU},{SOURCE}"]
    kyodaku = [",".join(H.KYODAKU_COLUMNS)] + [",".join(r) for r in REGISTRY_ROWS]
    shutten = [",".join(H.SHUTTEN_COLUMNS), f"G1,{fp_of('G1')},{GOT_ON},{SOURCE}"]
    mokuroku = [",".join(H.MOKUROKU_COLUMNS),
                f"B1,合成の配布(架空).json,K12,{H.SWAPS[0]},{SOURCE}"]
    t = H.share_terms(H.Ledger.parse("\n".join(daichou)),
                      H.Registry.parse("\n".join(kyodaku)),
                      H.Origins.parse("\n".join(shutten)),
                      H.Bundles.parse("\n".join(mokuroku)))
    assert t.report.ok
    assert next(x for x in t.judged if x.row.rule_id == "K12").result == H.KEKKA[0]
    j = next(x for x in t.judged if x.row.rule_id == "K11")
    filled = {ATTRIBUTION: attribution, SOURCE_URL: source_url,
              FINGERPRINT: fingerprint}
    if share == DASANAI:
        assert j.result == "出さないと宣言された"
    elif share != DASU:
        assert j.result == "出す宣言が無い"
    elif name == L3:
        assert j.result == "登録表に無い許諾の名前"
    elif all(filled[f] for f in NEEDS[name]):
        assert j.result == "宣言が揃っている"
    else:
        assert j.result == "出すと宣言されたが欄が空"
    if j.result == H.KEKKA[1]:
        assert j.missing == tuple(f for f in NEEDS[name] if not filled[f])
        assert t.empty_field_count() == len(j.missing)
    else:
        assert j.missing == ()
        assert t.empty_field_count() == 0
    assert sum(t.five().values()) == 2 == t.rule_denominator()
    assert t.total_rows() == rows + 1
