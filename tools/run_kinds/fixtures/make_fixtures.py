"""run_kinds の合成 fixture。**実在の指紋・実在の実行 id は 1 つも入っていない。**

実行 id も指紋も架空で、差分の件数は桁だけ手元の記録と同じ形にそろえてある(値は架空)。
この部品は件数と指紋の動きだけを読むので、中身が何でも同じように動く。写したのは形、つまり

  - 初回の回が在る(比べる相手が無く、差分が収録の全件として記録されている)
  - 落ちて据え置きになった回が在り、そのうち試験と事前に宣言されたものと、宣言が事後の
    ものと、宣言そのものが無いものが混ざる
  - 通ったが差分 0 で指紋も動いていない回が在る(走ったが変わらない)
  - 通って差分があり指紋も動いた回が在る
  - 指紋が履歴の前の回の値へ戻る回が在る
  - 差分 0 なのに指紋が動いた回と、差分ありなのに指紋が同じ回が在る
  - 登録表に無い status 語の回が在る
  - 落ちたと宣言されたのに指紋が動いている回が在る
  - 台帳に無い実行 id を指す宣言が在る(= 逆向きの欠け)
  - 据え置きでない回に付いた宣言が在る(判定には使わない)

の 10 つで、これは私の記録に残っている形だ。記録そのものは出さない。**実行の回数(11 回)
より多い 17 回にしてあるのは、手元の台帳に出てこない形(事前の宣言・別枠 2 種)も 1 回ずつ
入れて数えるため。**

書くもの(どれも決定論。同じ実行で同じバイト列になる)。

  runs_a.csv          実行の台帳 17 行
  intents_a.csv       意図の宣言表 5 行(1 行は台帳に無い実行 id を指す)
  words_a.csv         語の登録表 5 行(1 語は台帳に出てこない)
  kowashita/*.csv     理由コードと「表として読めない」を出すために 1 か所崩した表

使い方: python fixtures/make_fixtures.py   (この置き場に書き直す)
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import run_kinds as H  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの(テストがその行を開いて語の在ることを見る)
SRC_LEDGER = "articles/09_update_ledger.md L13"     # 台帳を書く側の回
SRC_CENSUS = "articles/17_check_census.md L13"      # 宣言された検証を走らせる回

TANA = "私の実行の台帳(非公開)L11"
KEIKAKU = "私の計画の記録(非公開)L4"
ATOKARA = "私の作業状況の記録(非公開)L99"
TOUROKU = "私の語の登録の記録(非公開)L7"

OK, FAILED, ABORTED = "ok", "failed", "合成の未登録の語(架空)"
SKIPPED = "skipped"
SHIKEN_CODE = "失敗試験"
TORIKOMI = "仕様変更の取り込み"
MITOUROKU_CODE = "合成の未登録の意図(架空)"

FP_A = "a1c7f03b9e42"
FP_B = "4d8b20e7cf15"
FP_C = "7e03ab516d9c"
FP_D = "b96f4c08a2e7"
FP_E = "02da7b91e5c3"
FP_F = "c58e36fd07b1"
FP_G = "9f12e8b4a60d"

MAE, ATO = H.MAE, H.ATO
SHOKAI = H.SHOKAI


def words_rows() -> list[list[str]]:
    """語の登録表 5 行。**意味と据え置きの有無は人が書いた宣言をそのまま持つだけ。**

    `skipped` は登録してあるが台帳に出てこない(登録表に在る語を全部使う必要は無い)。
    """
    return [
        [OK, H.TOTTA, H.SUEOKANAI, TOUROKU],
        [FAILED, H.OCHITA, H.SUEOKI, TOUROKU],
        [SKIPPED, H.OCHITA, H.SUEOKI, TOUROKU],
        [SHIKEN_CODE, H.SHIKEN, H.SUEOKI, TOUROKU],
        [TORIKOMI, H.SHIKEN_DENAI, H.SUEOKANAI, TOUROKU],
    ]


def intents_rows() -> list[list[str]]:
    """意図の宣言表 5 行。R04 は事後の宣言、R06 は据え置きでない回、R99 は台帳に無い。"""
    return [
        ["R03", SHIKEN_CODE, MAE, KEIKAKU],
        ["R04", SHIKEN_CODE, ATO, ATOKARA],
        ["R06", TORIKOMI, MAE, KEIKAKU],
        ["R12", SHIKEN_CODE, MAE, KEIKAKU],
        ["R99", SHIKEN_CODE, MAE, KEIKAKU],
    ]


def runs_rows() -> list[list[str]]:
    """実行の台帳 17 行。**時刻の欄を持たず、並び順の番号だけで順が決まる。**"""
    return [
        # 初回。比べる相手が無く、差分が収録の全件として記録されている
        ["R01", "1", OK, "1284", "0", "0", SHOKAI, FP_A, SRC_LEDGER],
        # 走ったが何も変わらない回(差分 0・指紋も同じ)
        ["R02", "2", OK, "0", "0", "0", "", FP_A, TANA],
        # 落ちて据え置き。事前に試験と宣言されている / 事後の宣言 / 宣言そのものが無い
        ["R03", "3", FAILED, "0", "0", "0", "", "", KEIKAKU],
        ["R04", "4", FAILED, "0", "0", "0", "", "", TANA],
        ["R05", "5", FAILED, "0", "0", "0", "", "", TANA],
        # 入れ替わった回。R07 は指紋が履歴の前の回の値へ戻る
        ["R06", "6", OK, "1", "0", "1", "", FP_B, SRC_CENSUS],
        ["R07", "7", OK, "0", "1", "1", "", FP_A, TANA],
        ["R08", "8", OK, "0", "0", "0", "", FP_A, TANA],
        ["R09", "9", OK, "341", "141", "1", "", FP_C, TANA],
        ["R10", "10", OK, "180", "0", "0", "", FP_D, TANA],
        # 噛み合わない回 2 つ(差分 0 なのに動いた / 差分ありなのに同じ)
        ["R11", "11", OK, "0", "0", "0", "", FP_E, TANA],
        ["R12", "12", FAILED, "0", "0", "0", "", "", KEIKAKU],
        ["R13", "13", OK, "12", "0", "0", "", FP_E, TANA],
        # 別枠 2 種(登録表に無い status 語 / 落ちたのに指紋が動いた)
        ["R14", "14", ABORTED, "0", "0", "0", "", "", TANA],
        ["R15", "15", FAILED, "0", "0", "0", "", FP_F, TANA],
        ["R16", "16", OK, "23", "0", "2", "", FP_G, TANA],
        ["R17", "17", OK, "0", "0", "0", "", FP_G, TANA],
    ]


# ------------------------------------------------------------ 崩した表

def _rows(rows: list[list[str]], number: int, column: int, value: str) \
        -> list[list[str]]:
    """1 行 1 欄だけ書き換えた写し(number は 1 始まりの本文の行)。"""
    out = [list(r) for r in rows]
    out[number - 1][column] = value
    return out


def kowashita_runs() -> dict[str, list[list[str]]]:
    """実行の台帳を 1 か所崩した表。前半 6 枚が理由コード、後半が「表として読めない」。"""
    base = runs_rows()
    out: dict[str, list[list[str]]] = {
        # 1 回も数えずに止まる(理由コード)
        "runs_shutten_kuuran": _rows(base, 1, 8, ""),
        "runs_run_id_juufuku": base + [["R05", "18", OK, "0", "0", "0", "", FP_G,
                                        TANA]],
        "runs_seq_tobi": _rows(base, 17, 1, "18"),
        "runs_shokai_nikagyou": _rows(base, 8, 6, SHOKAI),
        "runs_sueoki_sabun": _rows(base, 3, 3, "3"),
        "runs_shimon_nashi": _rows(base, 2, 7, ""),
        "runs_shokai_nashi": _rows(base, 1, 6, ""),
        # 表として読めない
        "runs_0gyou": [],
        "runs_run_id_kuuran": _rows(base, 2, 0, ""),
        "runs_seq_shousuu": _rows(base, 2, 1, "2.5"),
        "runs_seq_zero": _rows(base, 1, 1, "0"),
        "runs_kensuu_shousuu": _rows(base, 1, 3, "12.5"),
        "runs_shokai_gai": _rows(base, 1, 6, "はじめて"),
        "runs_status_kuuran": _rows(base, 2, 2, ""),
    }
    return out


def kowashita_intents() -> dict[str, list[list[str]]]:
    base = intents_rows()
    return {
        # 理由コード
        "intents_shutten_kuuran": _rows(base, 1, 3, ""),
        "intents_futatsu": base + [["R03", TORIKOMI, MAE, KEIKAKU]],
        "intents_mitouroku": _rows(base, 1, 1, MITOUROKU_CODE),
        # 表として読めない
        "intents_kumi_juufuku": base + [["R03", SHIKEN_CODE, ATO, KEIKAKU]],
        "intents_mae_ato_gai": _rows(base, 1, 2, "あとで書いた"),
        "intents_run_id_kuuran": _rows(base, 1, 0, ""),
        "intents_intent_kuuran": _rows(base, 1, 1, ""),
    }


def kowashita_words() -> dict[str, list[list[str]]]:
    base = words_rows()
    return {
        # 理由コード
        "words_shutten_kuuran": _rows(base, 1, 3, ""),
        # 表として読めない
        "words_0gyou": [],
        "words_imi_gai": _rows(base, 1, 1, "よく分からない"),
        "words_holds_gai": _rows(base, 1, 2, "たぶん据え置き"),
        "words_juufuku": base + [[OK, H.TOTTA, H.SUEOKANAI, TOUROKU]],
        "words_word_kuuran": _rows(base, 1, 0, ""),
    }


# 列を落とした表(どの表も同じ形で崩す)
RETSU_NASHI = {
    "runs_retsu_nashi": (H.RUNS_COLUMNS, runs_rows),
    "intents_retsu_nashi": (H.INTENT_COLUMNS, intents_rows),
    "words_retsu_nashi": (H.WORDS_COLUMNS, words_rows),
}


def write_all() -> list[Path]:
    written: list[Path] = []
    for name, columns, rows in (("runs_a", H.RUNS_COLUMNS, runs_rows()),
                                ("intents_a", H.INTENT_COLUMNS, intents_rows()),
                                ("words_a", H.WORDS_COLUMNS, words_rows())):
        written.append(H.write_csv(HERE / f"{name}.csv",
                                   [list(columns)] + rows))
    kowashita = HERE / "kowashita"
    for name, rows in sorted({**kowashita_runs()}.items()):
        written.append(H.write_csv(kowashita / f"{name}.csv",
                                   [list(H.RUNS_COLUMNS)] + rows))
    for name, rows in sorted({**kowashita_intents()}.items()):
        written.append(H.write_csv(kowashita / f"{name}.csv",
                                   [list(H.INTENT_COLUMNS)] + rows))
    for name, rows in sorted({**kowashita_words()}.items()):
        written.append(H.write_csv(kowashita / f"{name}.csv",
                                   [list(H.WORDS_COLUMNS)] + rows))
    for name, (columns, maker) in sorted(RETSU_NASHI.items()):
        written.append(H.write_csv(kowashita / f"{name}.csv",
                                   [list(columns[1:])]
                                   + [r[1:] for r in maker()]))
    return written


if __name__ == "__main__":
    paths = write_all()
    print(f"書いた: {len(paths)} 枚")
    for p in paths:
        print(f"  {p.relative_to(HERE)}")
