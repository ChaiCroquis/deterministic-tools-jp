"""合成 fixture を作り直す: python fixtures/make_fixtures.py

実データは使わない。会社名も法人番号も架空で、番号は jp_corp.check_digit と同じ算式で作った合成値。
左(torihikisaki_a.csv)の各行に 期待 列を持たせ、テストがその期待どおりかを確かめる。
期待 = 照合したときは 番号 / 名前、判断待ちのときは理由コード。
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import jp_corp as J  # noqa: E402


def synth_number(seq: int) -> str:
    """架空の 13 桁番号。下 12 桁を連番から作り、検査数字を先頭に付ける。"""
    base = f"{seq:012d}"
    return f"{J.check_digit(base)}{base}"


N1, N2, N3, N4 = (synth_number(n) for n in (100000000001, 100000000002, 100000000003, 100000000004))
BROKEN = N1[:-1] + str((int(N1[-1]) + 1) % 10)      # 末尾 1 桁を書き換えた番号(検査に落ちる)

LEFT = [
    ("A001", "山田商事株式会社", N1, "番号"),
    ("A002", "鈴木工業(株)", "", "名前"),
    ("A003", "ＡＢＣ物産株式会社", "", "名前"),
    ("A004", "みどり会医療法人社団", "", "名前"),
    ("A005", "山田商事有限会社", "", "法人格が違う"),
    ("A006", "東海運輸株式会社 大阪支店", "", "名前"),
    ("A007", "東海運輸株式会社", "", "名前"),
    ("A008", "さくら建設株式会社", "", "相手が複数"),
    ("A009", "のぞみ電機株式会社", "", "相手なし"),
    ("A010", "ひかり産業株式会社", "", "自分側が重複"),
    ("A011", "ひかり産業(株)", "", "自分側が重複"),
    ("A012", "株式会社", "", "空の会社名"),
    ("A013", "みやこ商会株式会社", BROKEN, "番号の検査に落ちる"),
    ("A014", "かえで工業株式会社", N2, "番号が食い違う"),
    ("A015", "ヤマト機械株式会社", N4, "番号"),
    ("A016", "一般社団法人日本ものづくり協会", "", "名前"),
    ("A017", "NPO法人あおぞら", "", "名前"),
]

RIGHT = [
    ("B001", "㈱山田商事", N1),
    ("B002", "鈴木工業株式会社", ""),
    ("B003", "ABC物産㈱", ""),
    ("B004", "医療法人社団みどり会", ""),
    ("B005", "東海運輸(株)大阪支店", ""),
    ("B006", "東海運輸株式会社", ""),
    ("B007", "さくら建設㈱", ""),
    ("B008", "さくら建設株式会社", ""),
    ("B009", "ひかり産業株式会社", ""),
    ("B010", "みやこ商会株式会社", ""),
    ("B011", "かえで工業株式会社", N3),
    ("B012", "大和機械株式会社", N4),
    ("B013", "一般社団法人日本ものづくり協会", ""),
    ("B014", "特定非営利活動法人あおぞら", ""),
]


def write(path: Path, header: list[str], rows: list[tuple]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"wrote {path} ({len(rows)} 行)")


if __name__ == "__main__":
    write(HERE / "torihikisaki_a.csv", ["取引先コード", "会社名", "法人番号", "期待"], LEFT)
    write(HERE / "torihikisaki_b.csv", ["コード", "会社名", "法人番号"], RIGHT)
