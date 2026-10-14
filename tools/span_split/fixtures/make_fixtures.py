"""span_split の合成 fixture。値は全て架空で、実データ・実在の取引先名は 1 つも入れない。

境界日と動いたものの名前だけは、私の棚卸し記録(非公開)に出典つきで並んでいる実在の改定を
写している(日付と動かした主体は公表されている情報)。**行の表の値・対象・期間は全て架空**で、
金額も率も入れていない(この部品は金額を触らないので、値は文字列のまま運ばれるだけ)。

書くもの(どれも決定論。同じ実行で同じバイト列になる)。

  kikan_a.csv        期間表 5 行。境界をまたぐ期間・またがない期間・経過措置の対象を混ぜた
  kikan_b.csv        期間表 1 行。段階施行の 2 つの境界をまたぐ期間
  kikan_c.csv        期間表 1 行。公表時点が期間の終わりより後の境界を内側に持つ期間
  kyoukai_a.csv      境界表 3 行。当日の帰属は全て 新側
  kyoukai_b.csv      境界表 3 行。kyoukai_a の 1 行だけ 当日の帰属 を 旧側 にした
  kyoukai_c.csv      境界表 2 行。段階施行(段階の順 1 / 2)
  kyoukai_d.csv      境界表 4 行。境界日が未定(施行日が政令待ち)の行を 1 行足した
  kyoukai_e.csv      境界表 1 行。公表時点が期間より後で、宣言は 切らない
  kyoukai_f.csv      境界表 1 行。kyoukai_e の宣言だけを 切る にした
  kyoukai_step.csv   境界表 3 行。2025-04-01 の行に段階の順を書いた
  gyou_a.csv         行の表 5 行。本則 4 行 + 経過措置 1 行(順位 10)
  gyou_douten.csv    行の表 5 行。同じ有効開始日の行が 2 行、順位はどちらも空
  gyou_osoi.csv      行の表 1 行。期間の開始日より後にしか有効開始日が無い
  kowashita/*.csv    止まる理由コードと「表として読めない」を出すために 1 か所だけ崩した表

使い方: python fixtures/make_fixtures.py   (この置き場に書き直す)
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import span_split as S  # noqa: E402

# 出典のうち、この repo 内の実在の行を指すもの(テストがその行を開いて語の在ることを見る)
SRC_TOUJITSU = "articles/02_wareki.md L13"        # 「改元日当日は新元号」= 当日の帰属の先例
SRC_KAISHIBI = "articles/02_wareki.md L40"        # 「開始日は改元日当日で」
SRC_JUNI = "articles/07_asof_table.md L15"        # 「どちらが勝つかは順位の列に書く」
SRC_KOUHYOU = "articles/07_asof_table.md L45"     # 「いつ公表された知識か」
SRC_KEIKA = "articles/07_asof_table.md L46"       # 「0 が本則、10 が経過措置」
SRC_KIRIKATA = "articles/19_variant_fan.md L32"   # 「期間の切り方が 2 通り」

# 境界の出典(動かした主体 + 非公開の棚卸し記録)。日付と主体は公表されている情報
TANAOROSHI = "私の棚卸し記録(非公開)"
SRC_NENKIN = f"日本年金機構 / {TANAOROSHI}"
SRC_KOUROU = f"厚生労働省 / {TANAOROSHI}"

# 動いたもの(棚卸しに出典つきで並んでいる実在の改定。値は写していない)
M_TOUKYUU = "標準報酬月額等級表_厚年の上限"
M_WARIMASHI = "割増賃金率の猶予終了"
M_KOUNENREI = "高年齢雇用継続給付の支給率"
M_IZOKU = "遺族厚生年金の有期給付"
M_YOUKEN = "雇用保険の適用要件(週所定労働時間)"
M_CHINGIN = "短時間労働者の賃金要件の撤廃"
M_GOUSEI = "合成の改定(架空)"

TAISHOU_A = "合成の区分A"
TAISHOU_B = "合成の区分B"

KIKAN_A = [
    [TAISHOU_A, "2025-01-01", "2025-06-30", "対象月初日"],   # 2025-04-01 をまたぐ
    [TAISHOU_A, "2025-04-01", "2025-09-30", "対象月初日"],   # 境界日が開始日 = またがない
    [TAISHOU_A, "2024-10-01", "2025-12-31", "対象月初日"],   # 2025-04-01 をまたぐ(長い)
    [TAISHOU_B, "2025-01-01", "2025-06-30", "対象月初日"],   # 経過措置の対象
    [TAISHOU_A, "2023-03-01", "2023-05-31", "賃金締切日"],   # 2023-04-01 をまたぐ
]
KIKAN_B = [[TAISHOU_A, "2027-10-01", "2029-03-31", "請求日"]]
KIKAN_C = [[TAISHOU_A, "2025-10-01", "2026-06-30", "対象月初日"]]

KYOUKAI_A = [
    ["2020-09-01", M_TOUKYUU, "新側", "", "", "", SRC_NENKIN, "逆順"],
    ["2023-04-01", M_WARIMASHI, "新側", "", "", "", SRC_KOUROU, ""],
    ["2025-04-01", M_KOUNENREI, "新側", "", "", "", SRC_TOUJITSU, ""],
]
KYOUKAI_C = [
    ["2028-04-01", M_IZOKU, "新側", "1", "", "", SRC_KOUROU, "逆順"],
    ["2028-10-01", M_YOUKEN, "新側", "2", "", "", SRC_KAISHIBI, ""],
]
# 公表時点が期間の終わりより後にある境界(遡って適用される形)。公表時点は架空
KYOUKAI_E = [["2026-04-01", M_GOUSEI, "新側", "", "2026-07-10", "切らない",
              SRC_KOUHYOU, "逆順"]]

GYOU_A = [
    ["合成の旧い値(架空)", "2015-04-01", "", "", "0", SRC_JUNI],
    ["合成の上限を足した値(架空)", "2020-09-01", "", "", "0", SRC_NENKIN],
    ["合成の猶予が終わった値(架空)", "2023-04-01", "", "", "0", SRC_KOUROU],
    ["合成の下がった値(架空)", "2025-04-01", "2024-11-25", "", "0", SRC_KOUROU],
    ["合成の経過措置の値(架空)", "2025-04-01", "2024-11-25", TAISHOU_B, "10", SRC_KEIKA],
]
GYOU_DOUTEN = GYOU_A[:3] + [
    ["合成の下がった値(架空)", "2025-04-01", "", "", "", SRC_KOUROU],
    ["合成のもう 1 本の値(架空)", "2025-04-01", "", "", "", SRC_KIRIKATA],
]
GYOU_OSOI = [["合成の下がった値(架空)", "2025-04-01", "", "", "0", SRC_KOUROU]]


def rows(header: tuple[str, ...], body: list[list[str]]) -> list[list[str]]:
    return [list(header)] + [list(r) for r in body]


def kikan(body: list[list[str]]) -> list[list[str]]:
    return rows(S.KIKAN_COLUMNS, body)


def kyoukai(body: list[list[str]]) -> list[list[str]]:
    return rows(S.KYOUKAI_COLUMNS, body)


def gyou(body: list[list[str]]) -> list[list[str]]:
    return rows(S.GYOU_COLUMNS, body)


def edit(body: list[list[str]], i: int, j: int, value: str) -> list[list[str]]:
    out = [list(r) for r in body]
    out[i][j] = value
    return out


def main() -> None:
    S.write_csv(HERE / "kikan_a.csv", kikan(KIKAN_A))
    S.write_csv(HERE / "kikan_b.csv", kikan(KIKAN_B))
    S.write_csv(HERE / "kikan_c.csv", kikan(KIKAN_C))

    S.write_csv(HERE / "kyoukai_a.csv", kyoukai(KYOUKAI_A))
    S.write_csv(HERE / "kyoukai_b.csv", kyoukai(edit(KYOUKAI_A, 2, 2, S.ONDAYS[1])))
    S.write_csv(HERE / "kyoukai_c.csv", kyoukai(KYOUKAI_C))
    S.write_csv(HERE / "kyoukai_d.csv", kyoukai(
        KYOUKAI_A + [[S.MITEI, M_CHINGIN, "新側", "", "", "", SRC_KOUROU, ""]]))
    S.write_csv(HERE / "kyoukai_e.csv", kyoukai(KYOUKAI_E))
    S.write_csv(HERE / "kyoukai_f.csv", kyoukai(edit(KYOUKAI_E, 0, 5, S.KNOWN_USES[0])))
    S.write_csv(HERE / "kyoukai_step.csv", kyoukai(edit(KYOUKAI_A, 2, 3, "1")))

    S.write_csv(HERE / "gyou_a.csv", gyou(GYOU_A))
    S.write_csv(HERE / "gyou_douten.csv", gyou(GYOU_DOUTEN))
    S.write_csv(HERE / "gyou_osoi.csv", gyou(GYOU_OSOI))

    # ---------------------------------------------------------- 崩した表
    k = HERE / "kowashita"

    # 止まる理由コードを出す側
    S.write_csv(k / "kyoukai_0gyou.csv", kyoukai([]))
    S.write_csv(k / "kyoukai_toujitsu_kuuran.csv", kyoukai(edit(KYOUKAI_A, 2, 2, "")))
    S.write_csv(k / "kyoukai_mitei.csv", kyoukai(edit(KYOUKAI_A, 1, 0, S.MITEI)))
    S.write_csv(k / "kyoukai_koushu_mibun.csv", kyoukai(edit(KYOUKAI_E, 0, 5, "")))
    S.write_csv(k / "kyoukai_shutten_nashi.csv", kyoukai(edit(KYOUKAI_A, 0, 6, "")))
    S.write_csv(k / "kyoukai_juufuku.csv", kyoukai(KYOUKAI_A + [list(KYOUKAI_A[2])]))
    S.write_csv(k / "gyou_shutten_nashi.csv", gyou(edit(GYOU_A, 3, 5, "")))
    S.write_csv(k / "kikan_basis_mitouroku.csv", kikan(edit(KIKAN_A, 0, 3, "支払日")))
    S.write_csv(k / "kikan_gyakusa.csv", kikan(edit(KIKAN_A, 0, 2, "2024-12-31")))

    # 「表として読めない」側(終了コード 2)
    S.write_csv(k / "kyoukai_retsu_nashi.csv",
                [[c for c in S.KYOUKAI_COLUMNS if c != "onday"]]
                + [[v for c, v in zip(S.KYOUKAI_COLUMNS, r) if c != "onday"]
                   for r in KYOUKAI_A])
    S.write_csv(k / "kyoukai_toujitsu_mitouroku.csv", kyoukai(edit(KYOUKAI_A, 2, 2, "どちらでも")))
    S.write_csv(k / "kyoukai_koushu_mitouroku.csv", kyoukai(edit(KYOUKAI_E, 0, 5, "寄せる")))
    S.write_csv(k / "kyoukai_koushu_nashi_ni_atsukai.csv",
                kyoukai(edit(KYOUKAI_A, 2, 5, S.KNOWN_USES[0])))
    S.write_csv(k / "kyoukai_swap_mitouroku.csv",
                kyoukai(edit(KYOUKAI_A, 0, 7, "ランダムに並べ替え")))
    S.write_csv(k / "kyoukai_swap_futatsu.csv", kyoukai(edit(KYOUKAI_A, 1, 7, "1 つずつずらす")))
    S.write_csv(k / "kyoukai_moved_kuuran.csv", kyoukai(edit(KYOUKAI_A, 1, 1, "")))
    S.write_csv(k / "kyoukai_hizuke_yomenai.csv", kyoukai(edit(KYOUKAI_A, 1, 0, "令和5年4月1日")))
    S.write_csv(k / "kyoukai_dankai_yomenai.csv", kyoukai(edit(KYOUKAI_C, 0, 3, "一段目")))
    S.write_csv(k / "kikan_taishou_kuuran.csv", kikan(edit(KIKAN_A, 1, 0, "")))
    S.write_csv(k / "kikan_basis_kuuran.csv", kikan(edit(KIKAN_A, 1, 3, "")))
    S.write_csv(k / "kikan_0gyou.csv", kikan([]))
    S.write_csv(k / "gyou_atai_kuuran.csv", gyou(edit(GYOU_A, 2, 0, "")))
    S.write_csv(k / "gyou_0gyou.csv", gyou([]))

    n = len(list(k.glob("*.csv")))
    print(f"書いた: {HERE}(期間表 3 / 境界表 7 / 行の表 3 / 崩した表 {n})")


if __name__ == "__main__":
    main()
