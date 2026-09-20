# jp_charset — 日本語 CSV の文字コードを、推測せずに固定の順番で厳密に決める

取込のたびに文字化けと戦う原因の多くは「文字コードの推測」にある。この道具は推測しない。
決まった順番で `errors="strict"` に復号を試し、最初に通った文字コード名と本文を返す。
全部失敗したら例外で止まる(置換文字で読み進めない)。stdlib のみ、依存なし。

## 判定の順番(固定)

| 段 | 見るもの | 結果 |
|---|---|---|
| 1 | BOM `EF BB BF` / `FF FE` / `FE FF` | `utf-8-sig` / `utf-16`(BOM 付きだけ) |
| 2 | NUL(`0x00`)を含む | 判定しない(BOM 無し UTF-16 かバイナリの疑い)→ 例外 |
| 3 | `utf-8` を strict | 通れば `utf-8` |
| 4 | `cp932` を strict | 通れば `cp932` |
| 5 | 全部失敗 | `UndecodableError` |

cp932 を先に試さない理由: cp932 のデコーダは UTF-8 のバイト列をかなりの割合で受け入れて、文字化けした文字列を返す。
逆(cp932 のバイト列が utf-8 strict を通る)はほぼ起きない。`tests/test_jp_charset.py` の `test_measure_*` が合成データで数えている。

## 使い方

```
python jp_charset.py FILE                 # 文字コード名を 1 行出力(utf-8 / cp932 / utf-8-sig / utf-16)
python jp_charset.py FILE --show          # 先頭 3 行も表示
python jp_charset.py FILE --to-utf8 OUT   # UTF-8(BOM 無し・LF)で書き出す
# exit 0 = 判定できた / 3 = 判定できない(止まった) / 2 = ファイルが読めない
```

```python
from jp_charset import read_text, detect, UndecodableError

enc, text = read_text("kyuyo.csv")        # Decoded(encoding, text)
enc, text = detect(raw_bytes)
```

## テスト

```
python -m pytest tools/jp_charset -q      # fixture は全て合成データ(fixtures/make_fixtures.py で再生成可)
```

## できないこと

- BOM 無しの UTF-16 は判定しない(止まる)。書き出し側で BOM を付けるか UTF-8 にしてもらう
- EUC-JP / ISO-2022-JP は順番に入れていない(私の環境で出会わないため)。`ORDER` に足せば試せる
- cp932 と UTF-8 の両方で strict に通るバイト列(ASCII だけの本文など)は、順番どおり `utf-8` と答える
- 途中で文字コードが変わるファイル(別のツールの出力を手で連結したもの)は止まる。分割して個別に判定する

ライセンス: MIT
