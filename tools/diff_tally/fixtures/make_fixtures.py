"""diff_tally の合成 fixture を書き出す(**実データ・実在の料率・実在の金額は 1 つも入れない**)。

5 枚(実行の記録の台帳 13 行 / 棚卸しの台帳 2 行 / 欄の登録表 3 行 / 結果記号の登録表 3 行 /
差の理由の宣言表 3 行)と、崩した表を `kowashita/` に書く。

形だけ手元の記録にそろえてある(件数の桁、落ちた回の `記載なし`、指紋が過去の回へ戻る回、
差分 0 なのに指紋が替わる回)。**実行 id は記号、結果記号は記号、指紋は合成の文字列、
出典は「合成の…(架空)」。** 指紋は 20 文字の合成文字列で、実在のハッシュ値ではない。

使い方: python make_fixtures.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import diff_tally as H  # noqa: E402

LOG = "合成の実行履歴のメモ(架空)L"
STOCK = "合成の収録範囲のメモ(架空)L"
WORD = "合成の登録のメモ(架空)L1"
REASON = "合成の理由のメモ(架空)L"

NONE = H.NONE_MARK
S_OK, S_FAIL, S_SIDE = "S1", "S2", "S3"
ADDED, REMOVED, CHANGED = H.DIFF_FIELDS
FUYASU, HERASU, UGOKASANAI = H.MOVES
SASHIKAERU, SASHIKAENAI = H.REPLACES
IRERU, IRENAI = H.CUMULATIVE

# 合成の指紋(**20 文字でそろえた記号列。実在のハッシュ値ではない**)
FP_A = "sa01" + "0" * 16
FP_B = "sb02" + "0" * 16
FP_C = "sc03" + "0" * 16
FP_D = "sd04" + "0" * 16
FP_E = "se05" + "0" * 16


def runs_rows() -> list[list[str]]:
    """実行の記録の台帳 13 行。6 値のすべてと戻りの印に 1 件以上の道を付ける。

    前の 11 行は手元の記録と同じ形(初回 / 冪等な回 / 落ちた 2 回 / 指紋が戻る回 /
    足して引いた回 / 差分 0 なのに指紋が替わる回)。後ろの 2 行は、手元の記録に出て
    こない形(**差分は 0 でないのに指紋が同じ回**と、**累積に入れないと宣言された回**)。
    """
    return [
        # 初回。1,301 行を足した回
        ["R01", "1", S_OK, "1301", "0", "0", FP_A, LOG + "1"],
        # 差分 0 / 指紋も同じ(2 経路が揃って「動いていない」)
        ["R02", "2", S_OK, "0", "0", "0", FP_A, LOG + "2"],
        # 落ちた 2 回。差分も指紋も `記載なし`(本番の出力を差し替えていない)
        ["R03", "3", S_FAIL, NONE, NONE, NONE, NONE, LOG + "3"],
        ["R04", "4", S_FAIL, NONE, NONE, NONE, NONE, LOG + "4"],
        # 1 行足して 1 行の中身が替わった回(前の回の指紋が `記載なし`)
        ["R05", "5", S_OK, "1", "0", "1", FP_B, LOG + "5"],
        # 1 行引いて 1 行の中身が替わった回。**指紋が R01 / R02 に戻る**
        ["R06", "6", S_OK, "0", "1", "1", FP_A, LOG + "6"],
        # 差分 0 / 指紋も同じ
        ["R07", "7", S_OK, "0", "0", "0", FP_A, LOG + "7"],
        # 341 行足して 141 行引いて 1 行の中身が替わった回
        ["R08", "8", S_OK, "341", "141", "1", FP_C, LOG + "8"],
        # 180 行足した回
        ["R09", "9", S_OK, "180", "0", "0", FP_D, LOG + "9"],
        # **差分 0 なのに指紋が替わった回**
        ["R10", "10", S_OK, "0", "0", "0", FP_E, LOG + "10"],
        # 差分 0 / 指紋も同じ
        ["R11", "11", S_OK, "0", "0", "0", FP_E, LOG + "11"],
        # **差分は 0 でないのに指紋が前の回と同じ回**(足して同じ数だけ引いた)
        ["R12", "12", S_OK, "5", "5", "0", FP_E, LOG + "12"],
        # 累積に入れないと宣言された結果記号の回(差分は読める)
        ["R13", "13", S_SIDE, "7", "2", "0", FP_B, LOG + "13"],
    ]


def stocks_rows() -> list[list[str]]:
    """棚卸しの台帳 2 行(**突合に使うのは時点記号の並びで最後の 1 行だけ**)。"""
    return [
        ["A1", "1301", "15", STOCK + "1"],
        ["A2", "1681", "45", STOCK + "2"],
    ]


def fields_rows() -> list[list[str]]:
    """欄の登録表 3 行(**`changed` は `動かさない` = 累積に入る経路が無い**)。"""
    return [
        [ADDED, FUYASU, H.FIELD_UNITS[0], WORD],
        [REMOVED, HERASU, H.FIELD_UNITS[0], WORD],
        [CHANGED, UGOKASANAI, H.FIELD_UNITS[0], WORD],
    ]


def statuses_rows() -> list[list[str]]:
    """結果記号の登録表 3 行(**累積に入れるかの宣言はここに在る**)。"""
    return [
        [S_OK, SASHIKAERU, IRERU, WORD],
        [S_FAIL, SASHIKAENAI, IRENAI, WORD],
        [S_SIDE, SASHIKAENAI, IRENAI, WORD],
    ]


def reasons_rows() -> list[list[str]]:
    """差の理由の宣言表 3 行(最後の 1 行は隣り合っていない対 = どの対にも当たらない)。"""
    return [
        ["R02", "R03", "上流の値を崩した試験の回", REASON + "1"],
        ["R09", "R10", "出力の並べ方を変えた回", REASON + "2"],
        ["R01", "R11", "初回と最後の回を並べた宣言", REASON + "3"],
    ]


# ---------------------------------------------------------------- 崩した表

def kowashita() -> dict[str, tuple[tuple[str, ...], list[list[str]]]]:
    """崩した表。**8 個の理由コードすべてに道を付け、表として読めない形も並べる。**"""
    out: dict[str, tuple[tuple[str, ...], list[list[str]]]] = {}

    def runs(name: str, change) -> None:
        rows = [list(r) for r in runs_rows()]
        change(rows)
        out[f"runs_{name}"] = (H.RUN_COLUMNS, rows)

    def stocks(name: str, change) -> None:
        rows = [list(r) for r in stocks_rows()]
        change(rows)
        out[f"stocks_{name}"] = (H.STOCK_COLUMNS, rows)

    def fields(name: str, change) -> None:
        rows = [list(r) for r in fields_rows()]
        change(rows)
        out[f"fields_{name}"] = (H.FIELD_COLUMNS, rows)

    def statuses(name: str, change) -> None:
        rows = [list(r) for r in statuses_rows()]
        change(rows)
        out[f"statuses_{name}"] = (H.STATUS_COLUMNS, rows)

    def reasons(name: str, change) -> None:
        rows = [list(r) for r in reasons_rows()]
        change(rows)
        out[f"reasons_{name}"] = (H.REASON_COLUMNS, rows)

    # 1 対も数えずに止まる(理由コード 8 個)
    runs("shutten_kuuran", lambda r: r[0].__setitem__(7, ""))
    stocks("shutten_kuuran", lambda r: r[0].__setitem__(3, ""))
    fields("shutten_kuuran", lambda r: r[0].__setitem__(3, ""))
    statuses("shutten_kuuran", lambda r: r[0].__setitem__(3, ""))
    reasons("shutten_kuuran", lambda r: r[0].__setitem__(3, ""))
    fields("ran_tarinai", lambda r: r.pop())            # changed の登録が無い
    runs("kekka_kigou_gai", lambda r: r[0].__setitem__(2, "合成の未登録の結果記号"))
    runs("kekka_kigou_kuuran", lambda r: r[0].__setitem__(2, ""))
    runs("junjo_juufuku", lambda r: r[1].__setitem__(1, "1"))
    runs("junjo_tobi", lambda r: r[1].__setitem__(1, "4"))
    runs("kensuu_seisu_gai", lambda r: r[0].__setitem__(3, "1,301"))
    runs("kensuu_kuuran", lambda r: r[0].__setitem__(4, ""))
    runs("shimon_nagasa", lambda r: r[0].__setitem__(6, "sa010"))
    stocks("jiten_juufuku", lambda r: r.append(["A1", "1681", "45", STOCK + "3"]))
    reasons("jitsuzai_shinai", lambda r: r.append(["R01", "R99", "合成の理由コード",
                                                   REASON + "4"]))

    # 表として読めない(終了コード 2)
    runs("junjo_shousuu", lambda r: r[0].__setitem__(1, "1.5"))
    runs("junjo_zero", lambda r: r[0].__setitem__(1, "0"))
    runs("shimon_kuuran", lambda r: r[0].__setitem__(6, ""))
    runs("run_id_juufuku", lambda r: r.append(list(r[0])))
    runs("run_id_kugiri", lambda r: r[0].__setitem__(0, "R 01"))
    runs("0gyou", lambda r: r.clear())
    stocks("gyousuu_shousuu", lambda r: r[0].__setitem__(1, "1301.5"))
    stocks("rule_suu_kuuran", lambda r: r[0].__setitem__(2, ""))
    stocks("0gyou", lambda r: r.clear())
    fields("ugokasu_gai", lambda r: r[0].__setitem__(1, "合成の未登録の記号"))
    fields("tan_i_gai", lambda r: r[0].__setitem__(2, "合成の未登録の単位"))
    fields("tan_i_kuuran", lambda r: r[0].__setitem__(2, ""))
    fields("juufuku", lambda r: r.append(list(r[0])))
    fields("0gyou", lambda r: r.clear())
    statuses("sashikae_gai", lambda r: r[0].__setitem__(1, "合成の未登録の記号"))
    statuses("ruiseki_gai", lambda r: r[0].__setitem__(2, "合成の未登録の記号"))
    statuses("juufuku", lambda r: r.append(list(r[0])))
    statuses("0gyou", lambda r: r.clear())
    reasons("riyuu_kuuran", lambda r: r[0].__setitem__(2, ""))
    reasons("juufuku", lambda r: r.append(list(r[0])))
    out["runs_retsu_nashi"] = (H.RUN_COLUMNS[:7], [r[:7] for r in runs_rows()])
    out["stocks_retsu_nashi"] = (H.STOCK_COLUMNS[:3], [r[:3] for r in stocks_rows()])
    out["fields_retsu_nashi"] = (H.FIELD_COLUMNS[:3], [r[:3] for r in fields_rows()])
    out["statuses_retsu_nashi"] = (H.STATUS_COLUMNS[:3],
                                   [r[:3] for r in statuses_rows()])
    out["reasons_retsu_nashi"] = (H.REASON_COLUMNS[:3],
                                  [r[:3] for r in reasons_rows()])
    return out


def write_all(dest: Path | None = None) -> list[Path]:
    d = dest or HERE
    written = [
        H.write_csv(d / "runs_a.csv", [list(H.RUN_COLUMNS)] + runs_rows()),
        H.write_csv(d / "stocks_a.csv", [list(H.STOCK_COLUMNS)] + stocks_rows()),
        H.write_csv(d / "fields_a.csv", [list(H.FIELD_COLUMNS)] + fields_rows()),
        H.write_csv(d / "statuses_a.csv",
                    [list(H.STATUS_COLUMNS)] + statuses_rows()),
        H.write_csv(d / "reasons_a.csv", [list(H.REASON_COLUMNS)] + reasons_rows()),
    ]
    for name, (head, rows) in kowashita().items():
        written.append(H.write_csv(d / "kowashita" / f"{name}.csv",
                                   [list(head)] + rows))
    return written


if __name__ == "__main__":
    for p in write_all():
        print(f"wrote {p}")
