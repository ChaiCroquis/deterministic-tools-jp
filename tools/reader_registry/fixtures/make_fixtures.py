"""reader_registry の合成 fixture を作る。**全て合成データ(架空)** で、実在の人・相手先・金額は無い。

作るもの(宣言表 1 + 表 13):
    registry.json      読み取り係の宣言表(4 係)
    a_yokogata.csv     行がレコード、横並び(素直な形)
    a_yokogata.tsv     同じ内容をタブ区切りにしたもの(区切りの宣言を変えるだけで同じ係で読める)
    b_tenchi.csv       列がレコード(行と列が入れ替わった形)
    c_kakko.csv        引く側が括弧で印字される形(時間も 60 進)
    d_kaimei.csv       a と同じ内容で、見出しが 2 つ改名された形
    e_setsumei.csv     見出し行の前に説明行が 2 行ある形
    f_nidan.csv        見出しが 2 段に分かれている形(1 行には全部そろわない)
    g_hasu.csv         データ 1 行だけ列数が足りない形
    h_yomenai.csv      時間が「7時間30分」と書かれている形(宣言した形で読めない)
    i_kesson.csv       空にできないと宣言した列が空の形
    j_fueta.csv        a に列が 2 つ増えた形(宣言した列数と違う)
    k_aimai.csv        2 つの係の match に同時に一致してしまう形
    l_michi.csv        どの係の match にも一致しない形

核の列は 7 つで、どの係も同じ 7 つへそろえる(= 核の側はこの 7 列しか知らない)。引く側は**核では負**で
持つ決まりにしてあるので、印字が符号なしの形(a / b / d)と括弧の形(c)が同じ形へ落ちる。金額は
「支給合計 + 控除合計 = 差引支給額」が成り立つように作ってある(次の工程の関所がそのまま通る形)。
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

CORE = ("社員番号", "氏名", "部署", "所定外時間", "支給合計", "控除合計", "差引支給額")
REQUIRED = ("社員番号", "氏名", "支給合計", "控除合計", "差引支給額")

FORMS_TEXT = {"社員番号": "文字列", "氏名": "文字列", "部署": "文字列"}
FORMS_NUM = {"所定外時間": "60進の時間", "支給合計": "整数", "差引支給額": "整数"}

# -- 4 係の宣言(核の列名は共通、原本の見出しと値の形だけが違う) ------------------

READER_ROWS = [
    {"reader_id": "相手先A_横並び",
     "match": {"headers": ["社員番号", "支給計"], "columns": 8},
     "orientation": "行がレコード",
     "column_map": {"社員番号": "社員番号", "氏名": "氏名", "部署": "部署",
                    "所定外時間": "所定外", "支給合計": "支給計", "控除合計": "控除計",
                    "差引支給額": "差引支給"},
     "value_form": {**FORMS_TEXT, **FORMS_NUM, "控除合計": "印字は符号なし"},
     "required": list(REQUIRED), "source": "合成の表(架空)"},
    {"reader_id": "相手先B_転置",
     "match": {"headers": ["社員コード", "差引"], "columns": 8},
     "orientation": "列がレコード",
     "column_map": {"社員番号": "社員コード", "氏名": "名前", "部署": "所属",
                    "所定外時間": "時間外", "支給合計": "支給計", "控除合計": "控除計",
                    "差引支給額": "差引"},
     "value_form": {**FORMS_TEXT, **FORMS_NUM, "控除合計": "印字は符号なし"},
     "required": list(REQUIRED), "source": "合成の表(架空)"},
    {"reader_id": "相手先C_括弧",
     "match": {"headers": ["社員番号", "控除額"], "columns": 8},
     "orientation": "行がレコード",
     "column_map": {"社員番号": "社員番号", "氏名": "氏名", "部署": "部署",
                    "所定外時間": "残業時間", "支給合計": "総支給", "控除合計": "控除額",
                    "差引支給額": "手取"},
     "value_form": {**FORMS_TEXT, **FORMS_NUM, "控除合計": "括弧は負"},
     "required": list(REQUIRED), "source": "合成の表(架空)"},
    {"reader_id": "相手先A_2026改名",
     "match": {"headers": ["社員番号", "総支給額"], "columns": 8},
     "orientation": "行がレコード",
     "column_map": {"社員番号": "社員番号", "氏名": "氏名", "部署": "部署",
                    "所定外時間": "所定外", "支給合計": "総支給額", "控除合計": "控除計",
                    "差引支給額": "差引支給額"},
     "value_form": {**FORMS_TEXT, **FORMS_NUM, "控除合計": "印字は符号なし"},
     "required": list(REQUIRED), "source": "合成の表(架空)。2026 年から見出しが 2 つ改名された"},
]

# -- 原本の表(全て架空) ---------------------------------------------------------

A_HEAD = ["社員番号", "氏名", "部署", "所定外", "支給計", "控除計", "差引支給", "備考"]
A_BODY = [
    ["000101", "山田 花子", "管理", "7:30", "312000", "48250", "263750", "新規"],
    ["000102", "佐藤 太郎", "製造", "1:15", "286500", "44120", "242380", ""],
    ["000103", "鈴木 一郎", "営業", "0:00", "240000", "38500", "201500", "再雇用"],
]
B_TABLE = [
    ["社員コード", "000201", "000202", "000203"],
    ["名前", "高橋 みどり", "伊藤 健", "渡辺 さくら"],
    ["所属", "介護", "介護", "事務"],
    ["時間外", "2:45", "0:30", "10:00"],
    ["支給計", "268000", "251000", "305000"],
    ["控除計", "41300", "39650", "47800"],
    ["差引", "226700", "211350", "257200"],
    ["メモ", "", "交替", ""],
]
C_HEAD = ["社員番号", "氏名", "部署", "残業時間", "総支給", "控除額", "手取", "調整"]
C_BODY = [
    ["000301", "中村 大輔", "運送", "7:45", "298400", "(45300)", "253100", ""],
    ["000302", "小林 ゆり", "運送", "0:20", "264000", "(41250)", "222750", ""],
    ["000303", "加藤 修", "整備", "12:05", "331500", "(52900)", "278600", ""],
]
D_HEAD = ["社員番号", "氏名", "部署", "所定外", "総支給額", "控除計", "差引支給額", "備考"]
D_BODY = [
    ["000401", "吉田 春", "医療", "3:20", "275000", "42600", "232400", ""],
    ["000402", "松本 隆", "医療", "0:45", "259000", "40100", "218900", "夜勤"],
    ["000403", "井上 愛", "看護", "8:10", "288000", "44300", "243700", ""],
]


def _rows(head: list, body: list) -> list:
    return [list(head), *[list(r) for r in body]]


def sheets() -> dict:
    """ファイル名 → 表(行の並び)。生成は決定論的で、乱数も日付も入らない。"""
    out: dict = {}
    out["a_yokogata.csv"] = _rows(A_HEAD, A_BODY)
    out["b_tenchi.csv"] = [list(r) for r in B_TABLE]
    out["c_kakko.csv"] = _rows(C_HEAD, C_BODY)
    out["d_kaimei.csv"] = _rows(D_HEAD, D_BODY)

    out["e_setsumei.csv"] = [["合成の表(架空)"], ["出力日", "2026-10-01"], *_rows(A_HEAD, A_BODY)]

    nidan_head = ["社員番号", "氏名", "部署", "所定外", "支給計", "控除計", "差引", "備考"]
    out["f_nidan.csv"] = [nidan_head, ["", "", "", "", "", "", "支給", ""],
                          *[list(r) for r in A_BODY]]

    hasu = _rows(A_HEAD, A_BODY)
    hasu[1] = hasu[1][:-1]                      # データ 1 行だけ列が足りない
    out["g_hasu.csv"] = hasu

    yomenai = _rows(A_HEAD, A_BODY)
    yomenai[1][3] = "7時間30分"                  # 60 進の時間として読めない
    out["h_yomenai.csv"] = yomenai

    kesson = _rows(A_HEAD, A_BODY)
    kesson[2][1] = ""                            # 空にできないと宣言した列が空
    out["i_kesson.csv"] = kesson

    out["j_fueta.csv"] = [[*A_HEAD, "新手当", "新控除"],
                          *[[*r, "3000", "500"] for r in A_BODY]]

    out["k_aimai.csv"] = _rows(["社員番号", "氏名", "部署", "所定外", "支給計", "総支給額",
                                "差引支給", "備考"], A_BODY)
    out["l_michi.csv"] = _rows(["整理番号", "名前", "区分", "勤務時間", "総額", "引去",
                                "振込", "摘要"], A_BODY)
    return out


def write(target: "str | Path" = HERE) -> list:
    """宣言表と表を書き出す。戻り値は書いたパスの一覧。"""
    d = Path(target)
    d.mkdir(parents=True, exist_ok=True)
    wrote = [d / "registry.json"]
    (d / "registry.json").write_text(
        json.dumps({"readers": READER_ROWS}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    for name, rows in sheets().items():
        p = d / name
        with open(p, "w", encoding="utf-8", newline="") as f:
            csv.writer(f, lineterminator="\n").writerows(rows)
        wrote.append(p)
    tsv = d / "a_yokogata.tsv"
    with open(tsv, "w", encoding="utf-8", newline="") as f:
        csv.writer(f, delimiter="\t", lineterminator="\n").writerows(sheets()["a_yokogata.csv"])
    wrote.append(tsv)
    return wrote


if __name__ == "__main__":
    for p in write():
        print(f"wrote {p}")
