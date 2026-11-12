"""regen_axis の性質テスト(hypothesis)。README「いつも成り立つこと」の 1 文をそのまま検査にする。

いつも成り立つこと: ファイルの台帳の 1 行には、区分 5 つか別枠の理由 6 つのうち 1 つだけが付き、
その合計は台帳の行数に等しく、表の行順を入れ替えても答えは変わらず、渡した表は 1 文字も書き換わらない。

台帳・登録表・線は乱数で作る(file id の重複、空の出典、登録に無い記号、台帳に無い端、輪を含む)。
区分の引き直しは regen_axis.judge を使わず、このテストの中で別の書き方で行う(輪は行列の閉包で見る)。
derandomize=True で毎回同じ入力列、database=None で見つけた例を保存しない。
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import regen_axis as R  # noqa: E402

IDS = ["F1", "F2", "F3", "F4", "F5", "F6"]
SYMS = ["人が書く", "実行が書く", "外から取る", "控え", "その他の書き手", "だれか", ""]

ファイル = st.fixed_dictionaries({
    "file id": st.sampled_from(IDS), "名前": st.sampled_from(["甲", "乙", "丙"]),
    "置き場": st.sampled_from(["直下", "出力/"]), "役割": st.just("合成の役割"),
    "書き手の記号": st.sampled_from(SYMS), "取り先": st.sampled_from(["", "配布元(架空)"]),
    "出典": st.sampled_from(["合成 L1", "合成 L1", "合成 L1", ""]),
})
登録 = st.fixed_dictionaries({
    "記号": st.sampled_from(SYMS[:5]), "意味": st.just("合成"), "出典": st.sampled_from(["合成 L1", "合成 L1", ""]),
})
線 = st.fixed_dictionaries({
    "線 id": st.sampled_from(["M1", "M2", "M3", "M4"]),
    "入力の file id": st.sampled_from(IDS + ["X9"]), "出力の file id": st.sampled_from(IDS + ["X9"]),
    "出典": st.sampled_from(["合成 L1", "合成 L1", "合成 L1", ""]),
})


def 引き直す(files: list[dict], writers: list[dict], lines: list[dict]) -> list[tuple]:
    """(行の全欄, 答え) の並びを返す。答え = 区分 か 別枠の理由。道具の関数は使わない。"""
    ids = sorted({f["file id"] for f in files})
    pos = {x: n for n, x in enumerate(ids)}
    登録済み = {w["記号"] for w in writers if w["出典"] != "" and w["記号"] != ""}
    reach = [[False] * len(ids) for _ in ids]         # reach[i][o]: i から o へ線が在る
    出力に出る = dict.fromkeys(ids, 0)
    入力に出る = dict.fromkeys(ids, 0)
    端が無い = set()
    for ln in lines:
        i, o = ln["入力の file id"], ln["出力の file id"]
        if ln["出典"] == "" or o not in pos:
            continue
        if i not in pos:
            端が無い.add(o)
            continue
        reach[pos[i]][pos[o]] = True
        入力に出る[i] += 1
        出力に出る[o] += 1
    for k in range(len(ids)):                           # 閉包
        for a in range(len(ids)):
            for b in range(len(ids)):
                if reach[a][k] and reach[k][b]:
                    reach[a][b] = True
    out = []
    for f in files:
        x, s = f["file id"], f["書き手の記号"]
        if sum(1 for g in files if g["file id"] == x) >= 2:
            ans = "file id が重複"
        elif f["出典"] == "":
            ans = "出典が空"
        elif s != "" and s not in 登録済み:
            ans = "書き手の記号が登録表に無い"
        elif s == "外から取る" and f["取り先"] == "":
            ans = "外から取るのに取り先が空"
        elif x in 端が無い:
            ans = "線の端が台帳に無い"
        elif reach[pos[x]][pos[x]]:
            ans = "線が輪になる"
        elif s == "控え":
            ans = R.KUBUN[3]
        elif s == "外から取る":
            ans = R.KUBUN[2]
        elif s == "実行が書く" and 出力に出る[x] >= 1:
            ans = R.KUBUN[1]
        elif s == "人が書く" and 出力に出る[x] == 0:
            ans = R.KUBUN[0]
        else:
            ans = R.KUBUN[4]
        out.append((tuple(f[c] for c in R.COLUMNS["files"]), ans))
    return sorted(out)


@settings(max_examples=300, derandomize=True, database=None, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(files=st.lists(ファイル, min_size=1, max_size=7), writers=st.lists(登録, max_size=6),
       lines=st.lists(線, max_size=6), data=st.data())
def test_いつも成り立つこと_答えは1つで合計は行数に等しく行順で変わらず入力を書き換えない(files, writers, lines, data):
    tables = {"files": files, "writers": writers, "lines": lines, "sayings": [], "lists": []}
    before = copy.deepcopy(tables)
    res = R.judge(tables)
    rows = res["ファイルごと"]

    # 答えは 1 つだけ
    got = []
    for r in rows:
        assert (r["区分"] in R.KUBUN) != (r["別枠の理由"] in R.BETSUWAKU)
        assert r["区分"] in R.KUBUN + ("",) and r["別枠の理由"] in R.BETSUWAKU + ("",)
        key = (r["file id"], r["名前"], r["置き場"], r["役割"],
               "" if r["書き手の記号"] == R.NO_WRITER else r["書き手の記号"],
               "" if r["取り先"] == R.NO_ORIGIN else r["取り先"], r["出典"])
        got.append((key, r["区分"] or r["別枠の理由"]))
        event("区分" if r["区分"] else "別枠")
    # 別の書き方で引き直した答えと同じ
    assert sorted(got) == 引き直す(files, writers, lines)
    # 合計は台帳の行数に等しい
    assert sum(res["区分"].values()) + sum(res["別枠"].values()) == len(files) == res["分母(ファイルの件数)"]
    # 行順を入れ替えても同じ
    shuffled = {k: data.draw(st.permutations(v)) for k, v in tables.items()}
    assert R.digest(R.judge(shuffled)) == R.digest(res)
    # 渡した表は書き換わらない
    assert tables == before
