"""合成の 3 枚(問いの台帳 / 置き場の登録表 / 新軸の定義)を作る。実在の料率・金額・名前は入れない。

印の並びは fill_owner.MARK_COLS と同じ 7 つ:
  行政が誰でも同じ答えを出すか | 主体内では一意か | 履歴を舐めないと決まらないか | 人が読んで決めるか |
  起算日 + N 日で書けるか | 施行日が決まっているか | 法が値を決めているか

置き場の登録表は **手で書いた宣言** で、道具はこの表に当てるだけ。印から置き場を導く規則は
道具の中に無い(この表の行を差し替えれば、同じ印の問いが別の置き場へ動く)。
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import fill_owner as F  # noqa: E402

Y, N, U = "はい", "いいえ", "宣言なし"

# 置き場の登録表(8 行)。鍵 = 印 7 つの組み合わせ。
OKIBA_ROWS = [
    ((Y, Y, N, N, N, Y, Y), "①", "A",  "行政",   "有効開始日",           "設計の記録 L129 の前"),
    ((Y, Y, N, N, Y, Y, Y), "②", "C3", "行政",   "起算日の欄の名前",     "設計の記録 L131"),
    ((N, Y, N, N, N, Y, Y), "③", "C2", "主体",   "順位の欄",             "設計の記録 L130"),
    ((N, N, N, Y, N, Y, N), "④", "C1", "人",     "受け取る属性の名前",   "設計の記録 L129"),
    ((Y, Y, Y, N, N, Y, Y), "⑤", "C5", "数式側", "供給する閾値の名前",   "設計の記録 L133"),
    ((N, N, N, Y, N, Y, Y), "⑥", "C4", "人",     "参照する解釈メモの名前", "設計の記録 L132"),
    ((Y, Y, N, N, N, N, Y), "⑦", "C6", "行政",   "施行日が決まったら埋める欄の名前", "設計の記録 L134"),
    ((N, Y, N, Y, N, Y, N), "⑧", "C7", "主体",   "—",                   "設計の記録 L135"),
]

JIKU_ROW = ("置き場(どの層の行になるか)", "出口と実装の状態", "設計の記録 L137 / 旧軸は公開済みの記事の一覧")

# 問いの台帳(20 行)。求める値の名前はすべて架空。一覧 id は「一覧 id#行#一覧に書かれた旧軸の値」。
_UCHI, _NOKORU, _SOTO, _TOMARU = "道具の中で済む", "返るが一手残る", "外から渡す前提", "止まる"
TOI_ROWS: list[tuple[str, str, str, str, str, tuple[str, ...], str, str]] = [
    ("Q01", "合成の値 甲(架空)", _UCHI,   "L31#1#" + _UCHI,   "A",
     (Y, Y, N, N, N, Y, Y), "合成の開始日(架空)", "設計の記録 L129 の前"),
    ("Q02", "合成の値 乙(架空)", _UCHI,   "L31#2#" + _UCHI,   "C3",
     (Y, Y, N, N, Y, Y, Y), "合成の起算日の欄(架空)", "設計の記録 L131"),
    ("Q02", "合成の値 乙(架空)", _UCHI,   "L31#2#" + _UCHI,   "C3",
     (Y, Y, N, N, Y, Y, Y), "合成の起算日の欄(架空)", "設計の記録 L131"),
    ("Q03", "合成の値 丙(架空)", _NOKORU, "L31#3#" + _NOKORU, "C5",
     (Y, Y, Y, N, N, Y, Y), "合成の閾値 甲(架空)", "設計の記録 L133"),
    ("Q04", "合成の値 丁(架空)", _SOTO,   "L31#4#" + _SOTO,   "C1",
     (N, N, N, Y, N, Y, N), "合成の属性 甲(架空)", "設計の記録 L129"),
    ("Q05", "合成の値 戊(架空)", _SOTO,   "L31#5#" + _SOTO,   "C2",
     (N, Y, N, N, N, Y, Y), "順位 20(架空)", "設計の記録 L130"),
    ("Q06", "合成の値 己(架空)", _SOTO,   "L31#6#" + _SOTO,   "C3",
     (Y, Y, N, N, Y, Y, Y), "合成の起算日の欄(架空)", "設計の記録 L131"),
    ("Q07", "合成の値 庚(架空)", _SOTO,   "L31#7#" + _SOTO,   "C4",
     (N, N, N, Y, N, Y, Y), "合成の解釈メモ 甲(架空)", "設計の記録 L132"),
    ("Q08", "合成の値 辛(架空)", _SOTO,   "L31#8#" + _SOTO,   "C5",
     (Y, Y, Y, N, N, Y, Y), "合成の閾値 乙(架空)", "設計の記録 L133"),
    ("Q09", "合成の値 壬(架空)", _SOTO,   "L31#9#" + _SOTO,   "C6",
     (Y, Y, N, N, N, N, Y), "合成の開始日の欄(架空)", "設計の記録 L134"),
    ("Q10", "合成の値 癸(架空)", _SOTO,   "L31#10#" + _SOTO,  "C7",
     (N, Y, N, Y, N, Y, N), "", "設計の記録 L135"),
    ("Q11", "合成の値 子(架空)", _TOMARU, "L31#11#" + _TOMARU, "C6",
     (Y, Y, N, N, N, N, Y), "合成の開始日の欄(架空)", "設計の記録 L134"),
    ("Q12", "合成の値 丑(架空)", _TOMARU, "L31#12#" + _TOMARU, "C3",
     (Y, N, N, N, N, Y, Y), "合成のチェックリスト(架空)", "設計の記録 L131 の後半"),
    ("Q13", "合成の値 寅(架空)", _NOKORU, "L31#13#" + _NOKORU, "C2",
     (N, Y, N, N, N, Y, Y), "", "設計の記録 L130"),
    ("Q14", "合成の値 卯(架空)", _SOTO,   "L31#14#" + _SOTO,  "C1",
     (N, N, U, Y, N, Y, N), "合成の属性 乙(架空)", "設計の記録 L129"),
    ("Q15", "合成の値 辰(架空)", _SOTO,   "L31#15#" + _SOTO,  "C9",
     (N, N, N, Y, N, Y, N), "合成の属性 丙(架空)", "設計の記録 L129"),
    ("Q16", "合成の値 巳(架空)", _SOTO,   "",                 "C2",
     (N, Y, N, N, N, Y, Y), "順位 21(架空)", "設計の記録 L130"),
    ("Q17", "合成の値 午(架空)", _UCHI,   "L31#17#" + _SOTO,  "A",
     (Y, Y, N, N, N, Y, Y), "合成の開始日(架空)", "設計の記録 L129 の前"),
    ("Q18", "合成の値 未(架空)", _SOTO,   "L31#18#" + _SOTO,  "C1",
     (N, N, N, Y, N, Y, N), "合成の属性 丁(架空)", ""),
    ("Q19", "合成の値 申(架空)", _SOTO,   "L31#19#" + _SOTO,  "C7",
     (N, N, N, Y, N, Y, N), "合成の属性 戊(架空)", "設計の記録 L135 / L129"),
]


def _write(path: Path, header: tuple[str, ...], rows: list[tuple[str, ...]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return path


def write_all(dest: Path) -> list[Path]:
    toi = [(i, v, o, lid, k) + m + (req, src) for i, v, o, lid, k, m, req, src in TOI_ROWS]
    okiba = [("|".join(m), p, k, d, need, src) for m, p, k, d, need, src in OKIBA_ROWS]
    return [
        _write(dest / "toi_daichou.csv", F.TOI_COLS, toi),
        _write(dest / "okiba_touroku.csv", F.OKIBA_COLS, okiba),
        _write(dest / "jiku_teigi.csv", F.JIKU_COLS, [JIKU_ROW]),
    ]


if __name__ == "__main__":
    for p in write_all(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE):
        print(f"wrote {p}")
