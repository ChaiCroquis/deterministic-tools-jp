"""env_match の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: 突き合わせの結果は 2 通りしかない。
  (a) 宣言表で 入れる と書かれた欄だけを基準ラベルのバイト列と突き合わせて 4 値に分け
      (一致 + 不一致 + 判定部分が取れない = 判定に入れた欄数、判定に入れた欄数 + 判定から
      外した欄数 = 宣言表の行数、宣言が無い = 出力に現れた欄のうち宣言表に無い欄の数)、
      判定部分に時刻・ホスト名・絶対パス・ラベル表の行順が 1 つも入らず、ラベル表の行順を
      入れ替えても同じバイト列になる
  (b) 1 つも結果を返さずに理由コードが返る(結果や指紋を取りに行くと例外になる)
どちらの場合も、この部品は出力の束もラベル表も宣言表も 1 文字も書き換えない。

ラベルは 2〜4 個、宣言は 1〜4 行を乱数で引き、判定に入れる / 入れない と理由の分類も振る。
値は 6 通りの短いバイト列(復帰文字で終わるものと空欄を含む)から引く。さらに 3 割くらいの確率で
1 か所だけ崩す(出典を空にする / 環境要素を空にする / ラベル名を重複させる / 宣言表を 0 行にする /
理由の分類を未登録にする / 基準を表に無い名前にする / ラベルを 1 つにする / 判定に入れた欄を
出力から落とす / 宣言表に無い欄を出力に足す)。derandomize=True で毎回同じ入力列を使い、
database=None で見つけた例を保存しない。

**期待する 4 値は部品の突き合わせを呼ばずにテストの側で計算している**(生成した値の辞書を
基準ラベルと直に比べる、別の実装)。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from hypothesis import event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import env_match as E  # noqa: E402

KIJUN = "既定"
LABEL_POOL = ("端末B", "端末C", "端末D")
FIELD_POOL = ("欄1", "欄2", "欄3", "欄4")
VALUE_POOL = ("12", "12\r", "13", "", "829.0", "あ")
SOURCE = "合成の宣言メモ(架空)L1"
EXTRA = "余りの欄"

KOWASHIKATA = ("出典を空にする", "環境要素を空にする", "ラベル名を重複させる",
               "宣言表を 0 行にする", "理由の分類を未登録にする", "基準を表に無い名前にする",
               "ラベルを 1 つにする", "判定に入れた欄を出力から落とす",
               "宣言表に無い欄を出力に足す")


@st.composite
def 合成の束(draw: st.DrawFn) -> dict[str, object]:
    """ラベル表 / 宣言表 / 出力の束(と崩し方)を作る。"""
    labels = [KIJUN] + draw(st.lists(st.sampled_from(LABEL_POOL), min_size=1, max_size=3,
                                     unique=True))
    fields = draw(st.lists(st.sampled_from(FIELD_POOL), min_size=1, max_size=4, unique=True))
    decl: list[list[str]] = []
    for f in fields:
        judge = draw(st.sampled_from(E.JUDGES))
        reason = draw(st.sampled_from(E.REASONS)) if judge == E.JUDGES[1] else ""
        decl.append([f, judge, reason, SOURCE])
    values: dict[str, dict[str, str]] = {}
    for i, name in enumerate(labels):
        values[name] = {f: draw(st.sampled_from(VALUE_POOL)) if i else
                        draw(st.sampled_from(VALUE_POOL)) for f in fields}

    kowasu = draw(st.sampled_from([None] * 7 + list(KOWASHIKATA)))
    base, swap = KIJUN, "逆順"
    dup = False
    if kowasu == "出典を空にする":
        decl[0][3] = ""
    elif kowasu == "環境要素を空にする":
        pass                                     # 下の label_text で空にする
    elif kowasu == "ラベル名を重複させる":
        dup = True
    elif kowasu == "宣言表を 0 行にする":
        decl = []
    elif kowasu == "理由の分類を未登録にする":
        rows = [r for r in decl if r[1] == E.JUDGES[1]]
        if rows:
            rows[0][2] = "既定の文字コード"
        else:
            decl[0][3], kowasu = "", "出典を空にする"
    elif kowasu == "基準を表に無い名前にする":
        base = "表に無い端末"
    elif kowasu == "ラベルを 1 つにする":
        labels = [KIJUN]
        values = {KIJUN: values[KIJUN]}
    elif kowasu == "判定に入れた欄を出力から落とす":
        rows = [r for r in decl if r[1] == E.JUDGES[0]]
        if rows and len(labels) >= 2:
            del values[labels[-1]][rows[0][0]]
        else:
            decl[0][3], kowasu = "", "出典を空にする"
    elif kowasu == "宣言表に無い欄を出力に足す":
        values[labels[-1]][EXTRA] = "1"

    label_rows = [",".join(E.LABEL_COLUMNS)]
    for i, name in enumerate(labels):
        element = "" if (kowasu == "環境要素を空にする" and i == len(labels) - 1) else "合成の要素"
        label_rows.append(f"{name},{element},合成の設定,{SOURCE},"
                          f"{base if i == 0 else ''},{swap if i == 0 else ''}")
    if dup:
        label_rows.append(f"{labels[-1]},合成の要素,合成の設定(2 行目),{SOURCE},,")
    decl_rows = [",".join(E.DECL_COLUMNS)] + [",".join(r) for r in decl]
    bundle = {n: ("\n".join(f"{k}\t{v}" for k, v in vs.items()) + "\n").encode("utf-8")
              for n, vs in values.items()}
    return {"label_text": "\n".join(label_rows), "decl_text": "\n".join(decl_rows),
            "bundle": bundle, "values": values, "decl": decl, "labels": labels,
            "kowasu": kowasu}


def 期待する4値(plan: dict[str, object]) -> dict[str, int]:
    """4 値をテストの側で別に数える(部品の match は呼ばない)。"""
    values: dict[str, dict[str, str]] = plan["values"]        # type: ignore[assignment]
    decl: list[list[str]] = plan["decl"]                      # type: ignore[assignment]
    labels: list[str] = plan["labels"]                        # type: ignore[assignment]
    base = values[KIJUN]
    four = dict.fromkeys(E.RESULTS, 0)
    for field, judge, _reason, _src in decl:
        if judge != E.JUDGES[0]:
            continue
        if any(field not in values[n] for n in labels):
            four[E.RESULTS[2]] += 1
        elif any(values[n][field] != base[field] for n in labels if n != KIJUN):
            four[E.RESULTS[1]] += 1
        else:
            four[E.RESULTS[0]] += 1
    declared = {r[0] for r in decl}
    union = {f for n in labels for f in values[n]}
    four[E.RESULTS[3]] = len(union - declared)
    return four


@settings(max_examples=120, derandomize=True, database=None, deadline=None)
@given(plan=合成の束())
def test_いつも成り立つこと_突き合わせた結果か理由コードか(plan: dict[str, object]) -> None:
    label_text, decl_text = plan["label_text"], plan["decl_text"]
    labels = E.Labels.parse(label_text)                       # type: ignore[arg-type]
    decl = E.Decl.parse(decl_text)                            # type: ignore[arg-type]
    outputs = E.Outputs.from_bytes(plan["bundle"], labels)    # type: ignore[arg-type]
    m = E.match(outputs, labels, decl)

    four = 期待する4値(plan)
    expect_stop = plan["kowasu"] is not None
    c = m.counts()

    # 分母の恒等式は、止まっても突き合わせても成り立つ
    assert c["判定に入れた欄数"] + c["判定から外した欄数"] == c["宣言表の行数"]
    if m.cells:
        assert (c["4 値"][E.RESULTS[0]] + c["4 値"][E.RESULTS[1]]
                + c["4 値"][E.RESULTS[2]]) == c["判定に入れた欄数"]
        assert c["4 値"] == four
        assert c["4 値"][E.RESULTS[3]] == len(set(outputs.union) - decl.names)

    if expect_stop:
        event("(b) 止まった")
        assert m.report.ok is False
        assert m.report.pending
        assert {p.reason for p in m.report.pending} <= set(E.STOP_REASONS)
        for call in (lambda: m.verdict, m.judgement_bytes, m.sha256):
            with pytest.raises(RuntimeError):
                call()
    else:
        event("(a) 突き合わせた")
        assert m.report.ok is True
        assert c["4 値"] == four and four[E.RESULTS[2]] == four[E.RESULTS[3]] == 0
        assert m.verdict == (E.RESULTS[1] if four[E.RESULTS[1]] else E.RESULTS[0])
        body = m.judgement_bytes().decode("utf-8")
        for word in (m.read_at, m.host, "読んだ時刻", "絶対パス"):
            assert word not in body
        for name in plan["labels"]:                           # type: ignore[union-attr]
            for v in plan["values"][name].values():           # type: ignore[index]
                assert not v.strip() or v not in body         # 値そのものは判定部分に入らない
        # ラベル表の行順を入れ替えても同じバイト列
        swapped = labels.swapped(labels.swap)
        again = E.match(E.Outputs.from_bytes(plan["bundle"], swapped), swapped, decl)
        assert again.sha256() == m.sha256()
        assert again.judgement_bytes() == m.judgement_bytes()

    # どちらの場合も入力は 1 文字も書き換わらない
    assert E.Labels.parse(label_text).items == labels.items   # type: ignore[arg-type]
    assert E.Decl.parse(decl_text).fields == decl.fields      # type: ignore[arg-type]
    assert E.Outputs.from_bytes(plan["bundle"], labels).items.keys() == outputs.items.keys()


@settings(max_examples=300, derandomize=True, database=None)
@given(perturb=st.lists(st.sampled_from(("入れる", "入れない")), min_size=1, max_size=5),
       value=st.sampled_from(VALUE_POOL))
def test_外した欄だけで差を作っても結果は一致のまま(perturb: list[str], value: str) -> None:
    """判定から外した欄の差は結果を動かさないが、入れた欄の差は 1 つで 不一致 になる。

    外す欄を増やすほど一致しやすくなる形だが、**外せるのは宣言表に書いた欄だけ** で、
    一致させるために部品の側が欄を外す経路は無い(宣言に無い欄は「宣言が無い」として残る)。
    """
    fields = [(f"欄{i + 1}", judge) for i, judge in enumerate(perturb)]
    decl_rows = [",".join(E.DECL_COLUMNS)]
    for f, judge in fields:
        reason = "時刻" if judge == "入れない" else ""
        decl_rows.append(f"{f},{judge},{reason},{SOURCE}")
    labels = E.Labels.parse("\n".join([
        ",".join(E.LABEL_COLUMNS),
        f"{KIJUN},合成の要素,合成の設定,{SOURCE},{KIJUN},逆順",
        f"端末B,合成の要素,合成の設定,{SOURCE},,"]))
    decl = E.Decl.parse("\n".join(decl_rows))

    base = {f: "12" for f, _ in fields}
    other = {f: (value if judge == "入れない" else "12") for f, judge in fields}
    bundle = {KIJUN: base, "端末B": other}
    data = {n: ("\n".join(f"{k}\t{v}" for k, v in vs.items()) + "\n").encode("utf-8")
            for n, vs in bundle.items()}
    m = E.match(E.Outputs.from_bytes(data, labels), labels, decl)
    c = m.counts()
    changed = sum(1 for f, judge in fields if judge == "入れない" and other[f] != base[f])
    assert m.verdict == E.RESULTS[0]                      # 外した欄の差では動かない
    assert c["外した欄で差が出た欄数"] == changed
    assert c["4 値"][E.RESULTS[0]] == len([1 for _, j in fields if j == "入れる"])

    # 入れた欄を 1 つだけ動かすと 不一致 になる(欄を外して一致にする経路は無い)
    included = [f for f, judge in fields if judge == "入れる"]
    if included and value != "12":
        other2 = dict(other)
        other2[included[0]] = value
        data2 = dict(data)
        data2["端末B"] = ("\n".join(f"{k}\t{v}" for k, v in other2.items())
                          + "\n").encode("utf-8")
        m2 = E.match(E.Outputs.from_bytes(data2, labels), labels, decl)
        assert m2.verdict == E.RESULTS[1]
        assert m2.counts()["4 値"][E.RESULTS[1]] == 1
