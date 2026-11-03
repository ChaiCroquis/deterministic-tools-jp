"""count_basis の合成 fixture を書き出す(**実データ・実在の料率・実在の金額は 1 つも入れない**)。

4 種 5 枚(検証の台帳 16 行 / 元の行の台帳 9 行 / 掛けた次元の宣言表 16 行 /
確かめ方の登録表 5 行 / 単位記号の登録表 6 行)と、崩した表を `kowashita/` に書く。

形だけ手元の記録にそろえてある(件数の桁、単位の混ざり方、「通過」とだけ書かれた行、
目で 1 件だけ見た行)。**数表 id は記号、rule id は架空の名前、出典は「合成の…(架空)」。**

使い方: python make_fixtures.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import count_basis as H  # noqa: E402

STATUS = "合成の作業状況のメモ(架空)L"
RANGE = "合成の収録範囲のメモ(架空)L"
PLAN = "合成の次元のメモ(架空)L"
WORD = "合成の登録のメモ(架空)L1"

CELL, SHIBU, ROW, ITEM, YEAR, RUN = "cell", "shibu", "row", "item", "year", "run"
M_CALC, M_TWO, M_NEIGHBOR, M_PUBLIC, M_EYE = "M1", "M2", "M3", "M4", "M5"
UNREG_UNIT, UNREG_METHOD = "合成の未登録の単位記号", "合成の未登録の確かめ方"

ARU, NAKA, HIROGETA = H.PLACES          # 行として在る / 1 行の中に在る / 計算で広げた
JIZEN, JORYU, SHOGO = H.ORIGINS         # 自前抽出 / 上流 / 照合専用


def checks_rows() -> list[list[str]]:
    """検証の台帳 16 行。7 値 + 別枠 4 種のすべてに 1 件以上の道を付ける。"""
    return [
        # 倍率が 1 行の持つ表の中に在る(= 行は増えていない)
        ["K01", "7,050", CELL, "T1", M_CALC, STATUS + "84"],
        # 件数が書かれていない(「通過」だけで単位も無い)
        ["K02", "通過", "", "T2", M_CALC, STATUS + "85"],
        # 次元の宣言が無い(2 系統の由来を要求する確かめ方)
        ["K03", "47", SHIBU, "T3;T8", M_TWO, STATUS + "86"],
        # 分解できた(次元 2 つ)
        ["K04", "24", ROW, "T4", M_CALC, STATUS + "90"],
        # 分解が合わない
        ["K05", "12", ROW, "T5", M_CALC, STATUS + "91"],
        # 他の検証と元の行を共有している(T1 を K01 と共有)
        ["K06", "423", CELL, "T1", M_CALC, STATUS + "87"],
        # 元の行の台帳に無い数表を指している
        ["K07", "100", ROW, "T99", M_CALC, STATUS + "92"],
        # 別枠(出典が空)
        ["K08", "5", ROW, "T6", M_CALC, ""],
        # 別枠(登録表に無いコード = 単位記号)
        ["K09", "10", UNREG_UNIT, "T6", M_CALC, STATUS + "93"],
        # 別枠(登録表に無いコード = 確かめ方)
        ["K10", "10", ROW, "T6", UNREG_METHOD, STATUS + "94"],
        # 別枠(単位記号が無い。件数は整数)
        ["K11", "30", "", "T6", M_CALC, STATUS + "95"],
        # 別枠(件数が整数でない)
        ["K12", "1.251", ITEM, "T6", M_CALC, STATUS + "96"],
        # 次元の宣言が無い(人の目視)
        ["K13", "1", ITEM, "T6", M_EYE, STATUS + "97"],
        # 分解できた(次元 1 つ)
        ["K14", "6", YEAR, "T9", M_CALC, STATUS + "98"],
        # 分解できた(倍率 1。分母そのものを宣言している行)
        ["K15", "1,681", ROW, "T7", M_NEIGHBOR, STATUS + "99"],
        # 他の検証と元の行を共有している(T3 を K03 と共有)
        ["K16", "47", SHIBU, "T3", M_CALC, STATUS + "100"],
    ]


def bases_rows() -> list[list[str]]:
    """元の行の台帳 9 行。由来は 自前抽出 6 / 上流 2 / 照合専用 1。"""
    return [
        ["T1", "合成の料率表_甲", "141", JIZEN, RANGE + "10"],
        ["T2", "合成の等級表_甲", "3", JIZEN, RANGE + "11"],
        ["T3", "合成の料率表_乙", "47", JORYU, RANGE + "12"],
        ["T4", "合成の上限額表", "4", JIZEN, RANGE + "13"],
        ["T5", "合成の下限額表", "3", JIZEN, RANGE + "14"],
        ["T6", "合成の期間帯表", "20", JIZEN, RANGE + "15"],
        ["T7", "合成の統一行の全体", "1681", JIZEN, RANGE + "16"],
        ["T8", "合成の照合用の料率表", "47", SHOGO, RANGE + "17"],
        ["T9", "合成の単価表", "2", JORYU, RANGE + "18"],
    ]


def dims_rows() -> list[list[str]]:
    """掛けた次元の宣言表 16 行(最後の 1 行は台帳に無い検証 id = 逆向きの欠け)。"""
    return [
        ["K01", "等級", "50", NAKA, PLAN + "4"],
        ["K02", "年", "3", ARU, PLAN + "5"],
        ["K04", "区分", "2", HIROGETA, PLAN + "6"],
        ["K04", "年", "3", ARU, PLAN + "7"],
        ["K05", "年", "3", ARU, PLAN + "8"],
        ["K06", "年", "3", ARU, PLAN + "9"],
        ["K07", "年", "2", ARU, PLAN + "10"],
        ["K08", "年", "2", ARU, PLAN + "11"],
        ["K09", "年", "2", ARU, PLAN + "12"],
        ["K10", "年", "2", ARU, PLAN + "13"],
        ["K11", "年", "2", ARU, PLAN + "14"],
        ["K12", "年", "2", ARU, PLAN + "15"],
        ["K14", "年", "3", ARU, PLAN + "16"],
        ["K15", "行", "1", ARU, PLAN + "17"],
        ["K16", "支部", "47", ARU, PLAN + "18"],
        ["K99", "年", "2", ARU, PLAN + "19"],
    ]


def methods_rows() -> list[list[str]]:
    """確かめ方の登録表 5 行(**順位も点数も列として無い**)。"""
    return [
        [M_CALC, H.METHOD_MEANINGS[0], H.REQUIRES[0], WORD],
        [M_TWO, H.METHOD_MEANINGS[1], H.REQUIRES[1], WORD],
        [M_NEIGHBOR, H.METHOD_MEANINGS[2], H.REQUIRES[2], WORD],
        [M_PUBLIC, H.METHOD_MEANINGS[3], H.REQUIRES[2], WORD],
        [M_EYE, H.METHOD_MEANINGS[4], H.REQUIRES[2], WORD],
    ]


def units_rows() -> list[list[str]]:
    """単位記号の登録表 6 行(台帳に出てこない記号も 1 つ在る = run)。"""
    return [[CELL, H.UNIT_MEANINGS[0], WORD], [SHIBU, H.UNIT_MEANINGS[1], WORD],
            [ROW, H.UNIT_MEANINGS[2], WORD], [ITEM, H.UNIT_MEANINGS[3], WORD],
            [YEAR, H.UNIT_MEANINGS[4], WORD], [RUN, H.UNIT_MEANINGS[5], WORD]]


# ---------------------------------------------------------------- 崩した表

def kowashita() -> dict[str, tuple[tuple[str, ...], list[list[str]]]]:
    """崩した表。**8 個の理由コードすべてに道を付け、表として読めない形も並べる。**"""
    out: dict[str, tuple[tuple[str, ...], list[list[str]]]] = {}

    def checks(name: str, change) -> None:
        rows = [list(r) for r in checks_rows()]
        change(rows)
        out[f"checks_{name}"] = (H.CHECK_COLUMNS, rows)

    def bases(name: str, change) -> None:
        rows = [list(r) for r in bases_rows()]
        change(rows)
        out[f"bases_{name}"] = (H.BASE_COLUMNS, rows)

    def dims(name: str, change) -> None:
        rows = [list(r) for r in dims_rows()]
        change(rows)
        out[f"dims_{name}"] = (H.DIM_COLUMNS, rows)

    def methods(name: str, change) -> None:
        rows = [list(r) for r in methods_rows()]
        change(rows)
        out[f"methods_{name}"] = (H.METHOD_COLUMNS, rows)

    def units(name: str, change) -> None:
        rows = [list(r) for r in units_rows()]
        change(rows)
        out[f"units_{name}"] = (H.UNIT_COLUMNS, rows)

    # 1 件も数えずに止まる(理由コード 8 個)
    bases("shutten_kuuran", lambda r: r[0].__setitem__(4, ""))
    dims("shutten_kuuran", lambda r: r[0].__setitem__(4, ""))
    methods("shutten_kuuran", lambda r: r[0].__setitem__(3, ""))
    units("shutten_kuuran", lambda r: r[0].__setitem__(2, ""))
    checks("check_id_juufuku",
           lambda r: r.append(["K01", "5", ROW, "T2", M_CALC, STATUS + "84"]))
    bases("table_id_juufuku",
          lambda r: r.append(["T1", "合成の料率表_甲", "141", JIZEN, RANGE + "10"]))
    dims("kumi_juufuku", lambda r: r.append(["K01", "等級", "2", ARU, PLAN + "4"]))
    checks("youkyuu_mitamase",      # 次元の宣言を要求する確かめ方なのに宣言が無い
           lambda r: r.append(["K17", "5", ROW, "T2", M_CALC, STATUS + "101"]))
    checks("youkyuu_yurai",         # 2 系統の由来を要求するのに由来が 1 種だけ
           lambda r: r.__setitem__(2, ["K03", "47", SHIBU, "T3", M_TWO, STATUS + "86"]))
    checks("youkyuu_kensuu",        # 件数と単位を要求するのに単位が空
           lambda r: r.__setitem__(14, ["K15", "1,681", "", "T7", M_NEIGHBOR,
                                        STATUS + "99"]))
    checks("suuhyou_kuuran", lambda r: r[0].__setitem__(3, ""))
    checks("suuhyou_nidosashi", lambda r: r[0].__setitem__(3, "T1;T1"))
    dims("jigenmei_kuuran", lambda r: r[0].__setitem__(1, ""))

    # 表として読めない(終了コード 2)
    bases("gyousuu_shousuu", lambda r: r[0].__setitem__(2, "141.5"))
    dims("bairitsu_shousuu", lambda r: r[0].__setitem__(2, "50.5"))
    dims("bairitsu_zero", lambda r: r[0].__setitem__(2, "0"))
    dims("arisho_gai", lambda r: r[0].__setitem__(3, "合成の未登録の在り所"))
    bases("yurai_gai", lambda r: r[0].__setitem__(3, "合成の未登録の由来"))
    methods("imi_gai", lambda r: r[0].__setitem__(1, "合成の未登録の意味"))
    methods("youkyuu_gai", lambda r: r[0].__setitem__(2, "合成の未登録の要求"))
    units("imi_gai", lambda r: r[0].__setitem__(1, "合成の未登録の意味"))
    units("juufuku", lambda r: r.append([CELL, H.UNIT_MEANINGS[0], WORD]))
    methods("juufuku", lambda r: r.append([M_CALC, H.METHOD_MEANINGS[0],
                                           H.REQUIRES[0], WORD]))
    checks("check_id_kugiri", lambda r: r[0].__setitem__(0, "K 01"))
    checks("0gyou", lambda r: r.clear())
    bases("0gyou", lambda r: r.clear())
    methods("0gyou", lambda r: r.clear())
    units("0gyou", lambda r: r.clear())
    out["checks_retsu_nashi"] = (H.CHECK_COLUMNS[:4],
                                 [r[:4] for r in checks_rows()])
    out["bases_retsu_nashi"] = (H.BASE_COLUMNS[:3], [r[:3] for r in bases_rows()])
    out["dims_retsu_nashi"] = (H.DIM_COLUMNS[:3], [r[:3] for r in dims_rows()])
    out["methods_retsu_nashi"] = (H.METHOD_COLUMNS[:2],
                                  [r[:2] for r in methods_rows()])
    out["units_retsu_nashi"] = (H.UNIT_COLUMNS[:2], [r[:2] for r in units_rows()])
    return out


def write_all(dest: Path | None = None) -> list[Path]:
    d = dest or HERE
    written = [
        H.write_csv(d / "checks_a.csv", [list(H.CHECK_COLUMNS)] + checks_rows()),
        H.write_csv(d / "bases_a.csv", [list(H.BASE_COLUMNS)] + bases_rows()),
        H.write_csv(d / "dims_a.csv", [list(H.DIM_COLUMNS)] + dims_rows()),
        H.write_csv(d / "methods_a.csv", [list(H.METHOD_COLUMNS)] + methods_rows()),
        H.write_csv(d / "units_a.csv", [list(H.UNIT_COLUMNS)] + units_rows()),
    ]
    for name, (head, rows) in kowashita().items():
        written.append(H.write_csv(d / "kowashita" / f"{name}.csv",
                                   [list(head)] + rows))
    return written


if __name__ == "__main__":
    for p in write_all():
        print(f"wrote {p}")
