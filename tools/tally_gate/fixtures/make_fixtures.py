"""tally_gate の合成 fixture を作る。**全て合成データ(架空)** で、実在の料率・税率・金額は入っていない。

作るもの:
    koumoku.csv   項目の宣言表(8 項目。item / group / sign / rounding / source)
    meisai.csv    明細(人 8 行 + 集計行 1 行、列 = 8 項目)

値は料率も人も架空で、計算は Decimal だけで閉じている。集計行は「人の行の、宣言された丸めを通した値」を
項目ごとに足したものなので、きれいな状態の表は 3 つの検査が全部一致する(= 壊れ方を 1 つずつ仕込んで
どの軸で見えるかを測るための土台になる)。

明細の保険料の列は **銭を残したまま** にしてある(丸めの名前が効く形にするため)。合成した 8 人のうち
2 人が端数ちょうど 50 銭に当たるので、50 銭以下切捨てと四捨五入で答えが分かれる。
"""
from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent

ID_COLUMN = "識別子"
TOTAL_ROW = "合計"
IDENTITY = "支給 - 控除 = 差引"

SEN = Decimal("0.01")
# 合成の料率(架空)。実在の保険料率・税率ではない
RATE_KOU = Decimal("0.0931")
RATE_OTSU = Decimal("0.0617")
RATE_TAX = Decimal("0.0421")

SPEC_ROWS = [
    {"item": "基本給", "group": "支給", "sign": "+", "rounding": "円未満四捨五入",
     "source": "合成の支給控除一覧(架空)"},
    {"item": "役職手当", "group": "支給", "sign": "+", "rounding": "円未満四捨五入",
     "source": "合成の支給控除一覧(架空)"},
    {"item": "通勤手当", "group": "支給", "sign": "+", "rounding": "1円未満切捨て",
     "source": "合成の支給控除一覧(架空)"},
    {"item": "保険料甲", "group": "控除", "sign": "+", "rounding": "50銭以下切捨て",
     "source": "合成の端数処理メモ(架空)"},
    {"item": "保険料乙", "group": "控除", "sign": "+", "rounding": "50銭以下切捨て",
     "source": "合成の端数処理メモ(架空)"},
    {"item": "源泉税", "group": "控除", "sign": "+", "rounding": "1円未満切捨て",
     "source": "合成の端数処理メモ(架空)"},
    {"item": "保険料の戻し", "group": "控除", "sign": "-", "rounding": "円未満四捨五入",
     "source": "合成の支給控除一覧(架空)。控除の group の中で引く側(印字は符号なし)"},
    {"item": "差引支給額", "group": "差引", "sign": "+", "rounding": "丸めない",
     "source": "合成の支給控除一覧(架空)"},
]

ITEMS = [r["item"] for r in SPEC_ROWS]

# 合成の人(8 人)。基本給 190000 と 230000 は保険料の端数がちょうど 50 銭になる
KIHON = [182000, 190000, 200000, 209000, 218000, 230000, 236000, 245000]
YAKUSHOKU = [25000, 0, 0, 25000, 0, 0, 25000, 0]
TSUKIN = ["4200", "4500", "", "5100", "5400", "5700", "6000", "6300"]
MODOSHI = ["", "1200", "", "", "", "3400", "", ""]


def _round50(x: Decimal) -> Decimal:
    i = x.to_integral_value(rounding="ROUND_FLOOR")
    return i if x - i <= Decimal("0.5") else i + 1


def _floor1(x: Decimal) -> Decimal:
    return x.to_integral_value(rounding="ROUND_FLOOR")


def _half_up(x: Decimal) -> Decimal:
    return x.to_integral_value(rounding="ROUND_HALF_UP")


ROUND = {"50銭以下切捨て": _round50, "1円未満切捨て": _floor1, "円未満四捨五入": _half_up,
         "丸めない": lambda x: x}
ROUND_OF = {r["item"]: ROUND[r["rounding"]] for r in SPEC_ROWS}


def _num(cell: str) -> Decimal:
    s = str(cell or "").strip()
    return Decimal(s) if s else Decimal(0)


def person_rows() -> list:
    """人 8 行(集計行は含まない)。値は全て架空。"""
    rows = []
    for i, kihon in enumerate(KIHON):
        kou = (Decimal(kihon) * RATE_KOU / 2).quantize(SEN)
        otsu = (Decimal(kihon) * RATE_OTSU / 2).quantize(SEN)
        shikyu = (_half_up(Decimal(kihon)) + _half_up(Decimal(YAKUSHOKU[i]))
                  + _floor1(_num(TSUKIN[i])))
        kazei = shikyu - _round50(kou) - _round50(otsu)
        tax = _floor1(kazei * RATE_TAX)
        koujo = _round50(kou) + _round50(otsu) + tax - _half_up(_num(MODOSHI[i]))
        rows.append({
            ID_COLUMN: f"1{i + 1:04d}",
            "基本給": str(kihon),
            "役職手当": str(YAKUSHOKU[i]) if YAKUSHOKU[i] else "",
            "通勤手当": TSUKIN[i],
            "保険料甲": format(kou, "f"),
            "保険料乙": format(otsu, "f"),
            "源泉税": format(tax, "f"),
            "保険料の戻し": MODOSHI[i],
            "差引支給額": format(shikyu - koujo, "f"),
        })
    return rows


def total_row(rows: list) -> dict:
    """集計行 = 項目ごとに、宣言された丸めを通した人の値を足したもの。"""
    out = {ID_COLUMN: TOTAL_ROW}
    for name in ITEMS:
        out[name] = format(sum((ROUND_OF[name](_num(r[name])) for r in rows), Decimal(0)), "f")
    return out


def meisai_rows() -> list:
    rows = person_rows()
    return [*rows, total_row(rows)]


def write(dest: "Path | None" = None) -> dict:
    d = Path(dest or HERE)
    spec = d / "koumoku.csv"
    meisai = d / "meisai.csv"
    with open(spec, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["item", "group", "sign", "rounding", "source"])
        w.writeheader()
        w.writerows(SPEC_ROWS)
    with open(meisai, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[ID_COLUMN, *ITEMS])
        w.writeheader()
        w.writerows(meisai_rows())
    return {"spec": spec, "meisai": meisai}


def main() -> None:
    out = write()
    rows = person_rows()
    print(f"wrote {out['spec']}({len(SPEC_ROWS)} 項目)")
    print(f"wrote {out['meisai']}({len(rows)} 人 + 集計行 1)")
    print(f"恒等式: {IDENTITY} / 識別子の列: {ID_COLUMN} / 集計行: {TOTAL_ROW}")


if __name__ == "__main__":
    main()
