# jp_charset — 日本語 CSV の文字コードを、推測せずに固定の順番で厳密に決める

<!-- article-links:begin (publish/readme_links.py が台帳から生成。手で直さない) -->
解説記事: [日本語 CSV の文字コードは、推測せずに順番に試す](https://chronicles-of-solo-parenting.blogspot.com/2026/09/csv.html)(2026-09-21 公開)
<!-- article-links:end -->

取込のたびに文字化けと戦う原因の多くは「文字コードの推測」にある。この道具は推測しない。
決まった順番で `errors="strict"` に復号を試し、最初に通った文字コード名と本文を返す。
全部失敗したら例外で止まる(置換文字で読み進めない)。stdlib のみ、依存なし。

## 判定の順番(固定)

| 段 | 見るもの | 結果 |
|---|---|---|
| 1 | BOM `EF BB BF` / `FF FE` / `FE FF` | `utf-8-sig` / `utf-16`(BOM 付きだけ)。BOM の示す文字コードで読めなければ `UndecodableError`(ほかの段に回さない) |
| 2 | NUL(`0x00`)を含む | 判定しない(BOM 無し UTF-16 かバイナリの疑い)→ 例外 |
| 3 | `utf-8` を strict | 通れば `utf-8` |
| 4 | `cp932` を strict | 通れば `cp932` |
| 5 | 全部失敗 | `UndecodableError` |

cp932 を先に試さない理由: cp932 のデコーダは UTF-8 のバイト列をかなりの割合で受け入れて、文字化けした文字列を返す。
逆(cp932 のバイト列が utf-8 strict を通る)はほぼ起きない。`tests/test_jp_charset.py` の `test_measure_*` が合成データで数えている。

## いつも成り立つこと

どんなバイト列を渡しても、結果は 2 通りしかない。**判定の順番(BOM → NUL → utf-8 → cp932)で最初に strict に通る文字コードの名前と、その文字コードで strict に読んだ本文(BOM は除く)が返る**か、**`UndecodableError` で止まる**か。置換文字で読み進めた本文が返ることも、ほかの例外で落ちることもない(CLI の終了コードは 0 / 3 / 2 のどれか)。

この 1 文は `tests/test_jp_charset_property.py` が性質テスト(hypothesis)で確かめている。書ける本文を utf-8 / BOM 付き utf-8 / BOM 付き utf-16 / cp932 で書いたバイト列を乱数で作り、半分の確率で困るバイト列(末尾を 1 バイト欠いたもの、途中に NUL を挟んだもの、BOM 無し utf-16、2 つの書き方の連結など)に差し替えて、毎回この 1 文が成り立つかを見る(乱数は固定で、毎回同じ 600 通り)。期待値は道具の関数を使わず、テストの中で別に作っている。テストの実行には pytest と hypothesis が要る(道具そのものは標準ライブラリだけで動く)。

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
