"""合成データの fixture を生成する(実データは使わない)。python -X utf8 make_fixtures.py で再生成。"""
from __future__ import annotations
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROWS = [
    "社員番号,氏名,部署,基本給",
    "0001,佐藤 太郎,営業部,250000",
    "0002,鈴木 花子,総務部,232000",
    "0003,高橋 一郎,経理部,268000",
    "0004,田中 美咲,製造部,214000",
    "0005,伊藤 健,開発部,301000",
]
TEXT = "\r\n".join(ROWS) + "\r\n"
# 機種依存文字(NEC 特殊文字・IBM 拡張): ㈱ ① 髙 﨑 は cp932 では表せるが JIS X 0208 には無い
EXT_ROWS = [
    "社員番号,氏名,部署,基本給",
    "0006,髙橋 ①太,㈱営業部,255000",
    "0007,山﨑 花子,総務部Ⅱ,240000",
]
EXT_TEXT = "\r\n".join(EXT_ROWS) + "\r\n"


def main() -> None:
    (HERE / "cp932.csv").write_bytes(TEXT.encode("cp932"))
    (HERE / "utf8_bom.csv").write_bytes(TEXT.encode("utf-8-sig"))
    (HERE / "utf8.csv").write_bytes(TEXT.encode("utf-8"))
    (HERE / "utf16_bom.csv").write_bytes(TEXT.encode("utf-16"))          # BOM 付き(LE)
    (HERE / "utf16_nobom.csv").write_bytes(TEXT.encode("utf-16-le"))     # BOM 無し(判定を拒否する対象)
    (HERE / "cp932_ext.csv").write_bytes(EXT_TEXT.encode("cp932"))
    # 途中で混在: 先頭 3 行は cp932、残りは utf-8(別ツールの出力を手で連結した状況)
    head = "\r\n".join(ROWS[:3]) + "\r\n"
    tail = "\r\n".join(ROWS[3:]) + "\r\n"
    (HERE / "mixed.csv").write_bytes(head.encode("cp932") + tail.encode("utf-8"))
    (HERE / "empty.csv").write_bytes(b"")
    (HERE / "ascii.csv").write_bytes("id,amount\r\n1,100\r\n".encode("ascii"))
    print("fixtures written:", sorted(p.name for p in HERE.glob("*.csv")))


if __name__ == "__main__":
    main()
