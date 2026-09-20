"""jp_charset — 日本語 CSV の文字コードを「推測せず、固定の順番で厳密に試して」決める判定器。

順番(固定。変えない):
  1. BOM を見る       EF BB BF → utf-8-sig / FF FE・FE FF → utf-16(BOM 付きだけ)
  2. NUL を見る       0x00 を含む → BOM 無し UTF-16 かバイナリの疑い。判定せず止まる
  3. utf-8 を strict  通れば utf-8
  4. cp932 を strict  通れば cp932
  5. 全部失敗         UndecodableError で止まる(置換文字で読み進めない)

cp932 を先に試さない理由: cp932 のデコーダは UTF-8 のバイト列をかなりの割合でそのまま受け入れて
文字化けした文字列を返す(tests/test_jp_charset.py の test_naive_order_* が再現する)。
逆方向(cp932 のバイト列が utf-8 strict を通る)はほぼ起きないので、utf-8 → cp932 の順にする。

stdlib のみ。関数(detect / decode_bytes / read_text)と CLI の両方。
CLI: python jp_charset.py FILE            → 文字コード名を 1 行出力(exit 0)
     python jp_charset.py FILE --to-utf8 OUT → UTF-8(BOM 無し・LF)で書き出し
     判定できなければ exit 3
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import NamedTuple

__all__ = ["ORDER", "Decoded", "UndecodableError", "detect", "decode_bytes", "read_text", "main"]

# strict で順に試す文字コード(BOM 判定の後)。先頭から順に試し、最初に通ったものを採用する。
ORDER: tuple[str, ...] = ("utf-8", "cp932")

BOM_UTF8 = b"\xef\xbb\xbf"
BOM_UTF16_LE = b"\xff\xfe"
BOM_UTF16_BE = b"\xfe\xff"


class Decoded(NamedTuple):
    encoding: str   # 採用した文字コード名(utf-8-sig / utf-16 / utf-8 / cp932)
    text: str       # 復号した本文(BOM は除去済み)


class UndecodableError(ValueError):
    """固定順の全てで strict 復号に失敗した、または NUL を含むため判定を拒否した。"""


def detect(data: bytes) -> Decoded:
    """バイト列を固定順で厳密に復号し、最初に通った文字コード名と本文を返す。

    全部失敗したら UndecodableError。置換文字('?' や U+FFFD)で読み進めることはしない。
    """
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("detect() は bytes を受け取る(str を渡さない)")
    data = bytes(data)
    if data == b"":
        return Decoded("utf-8", "")

    # 1. BOM(決定論。推測ではない)
    if data.startswith(BOM_UTF8):
        return Decoded("utf-8-sig", data.decode("utf-8-sig", errors="strict"))
    if data.startswith(BOM_UTF16_LE) or data.startswith(BOM_UTF16_BE):
        # utf-16 コーデックは BOM を読んでエンディアンを決め、BOM を除去する
        return Decoded("utf-16", data.decode("utf-16", errors="strict"))

    # 2. NUL(BOM 無し UTF-16 / バイナリの疑い。UTF-8 や cp932 のテキストには現れない)
    if b"\x00" in data:
        raise UndecodableError("NUL(0x00)を含む: BOM 無し UTF-16 かバイナリの疑い。判定しない")

    # 3-4. 固定順で strict
    failures: list[str] = []
    for enc in ORDER:
        try:
            return Decoded(enc, data.decode(enc, errors="strict"))
        except UnicodeDecodeError as e:
            failures.append(f"{enc}: byte {e.start} 付近 ({e.reason})")

    # 5. 全部失敗
    raise UndecodableError("固定順の全てで復号に失敗: " + " / ".join(failures))


def decode_bytes(data: bytes) -> str:
    """本文だけ欲しいとき用。"""
    return detect(data).text


def read_text(path: str | Path) -> Decoded:
    """ファイルを読んで判定する。"""
    return detect(Path(path).read_bytes())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="jp_charset", description="日本語 CSV の文字コードを固定順で厳密に判定する")
    ap.add_argument("file", help="判定するファイル")
    ap.add_argument("--to-utf8", metavar="OUT", help="復号した本文を UTF-8(BOM 無し・改行 LF)で OUT に書く")
    ap.add_argument("--show", action="store_true", help="本文の先頭 3 行も表示する")
    a = ap.parse_args(argv)
    try:
        r = read_text(a.file)
    except UndecodableError as e:
        print(f"NG: {a.file}: {e}", file=sys.stderr)
        return 3
    except OSError as e:
        print(f"NG: {a.file}: {e}", file=sys.stderr)
        return 2
    print(r.encoding)
    if a.show:
        for line in r.text.splitlines()[:3]:
            print("  " + line)
    if a.to_utf8:
        Path(a.to_utf8).write_text(r.text.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
        print(f"wrote {a.to_utf8}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
