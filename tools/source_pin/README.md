# source_pin — 原本から取った値 1 件を「ピン 1 行」で持ち、毎回原本に突き合わせる

<!-- article-links:begin (publish/readme_links.py が台帳から生成。手で直さない) -->
解説記事: [公式の数表は、取れない場所を先に地図にしてから取りに行く](https://chronicles-of-solo-parenting.blogspot.com/2026/09/blog-post_30.html)(2026-10-01 公開)
<!-- article-links:end -->

数表を行で持つ部品([asof_table](../asof_table))も、更新を台帳に残す部品([update_ledger](../update_ledger))も、
**「行がすでにある」ことを前提にしている**。その行を作る工程、つまり配布元の xlsx / PDF / HTML から
値を取り出す工程は、取れる場所と取れない場所がまだらだ。取れなかった場所を空欄のまま下流に流すと、
前年の値や近い行で静かに埋まる。

この部品は 値 1 件 = ピン 1 行 として持ち、使うたびに原本と突き合わせる。
**取れない原本は value を空にした `unavailable` の行として残す**(取れない物が表から消えないことが要点)。

## ピン 1 行の列

| 列 | 中身 |
|---|---|
| `key` | 何の値か |
| `value` | 正規化したあとの値(下流が使う値) |
| `raw_text` | **原本にある生の文字そのまま** |
| `source_kind` | 原本の種類。`map()` の行になる(空欄は「(種類の記載なし)」に入る) |
| `source_file` | 原本のファイル(ピンの表からの相対パス、または絶対パス) |
| `source_sha256` | 原本の sha256。**配布元が差し替えたら止まる** |
| `locator` | 原本の中の場所(`シート名!B12` / 行番号 / 人が読んだ場所) |
| `method` | 取り出し方(下の 5 種) |
| `normalizer` | `raw_text` から `value` を作る正規化の名前。`+` で連ねる。**既定は無い** |
| `captured_at` | 取り出した時刻 |
| `note` | 覚え書き |

入力は CSV でも JSON でもよい([asof_table](../asof_table) の行の表に足せる列構成)。

## 取り出し方(4 種 + 1)

| `method` | 何をするか | 接地の検査 |
|---|---|---|
| `xlsx_cell` | `zipfile` と `xml.etree` で `xl/worksheets` と `xl/sharedStrings.xml` を直接読む。`locator` = `シート名!B12` | セルの中身と `raw_text` が**一致**するか(セルは 1 値なので部分一致は認めない) |
| `text_line` | 取り出し済みテキストの `locator` 行目。`locator` = 行番号 | その行に `raw_text` が literal で在るか |
| `html_text` | `html.parser` で tag を外し、空行を落として 1 から数えた行。`locator` = 行番号 | 同じ |
| `manual` | 人が転記した。値は使えるが、返り値に必ず**転記の印**(`transcribed`)が付く | できない(原本の sha256 だけ張る) |
| `unavailable` | 原本から取れない。`value` は空でなければ止まる | 値が無いので不要 |

**PDF は自前で読まない。** PDF から取り出したテキストを `text_line` の入力として受け、PDF 本体には
sha256 と `locator` だけを張る。テキスト層の無い(画像だけの)PDF は `unavailable` の行になる。

## 正規化(名前で呼ぶ。部品は既定を持たない)

`そのまま` / `全角半角`(NFKC)/ `カンマ除去` / `パーセント` / `円` / `日付`。`+` で左から順に適用する。
`全角半角+カンマ除去+円` で `１，２３０，０００円` → `1230000`。桁は丸めないので `1.60%` は `1.60` のまま。

`normalizer` が空欄の行は **評価せずに止める**。「何もしない」も `そのまま` と名前で書く
(丸めの規律は [formula_table](../formula_table) と同じ考え方)。

## 検査(verify)が見る 3 つ

- ① `source_file` の現物の sha256 が `source_sha256` と一致するか
- ② `locator` の指す場所に `raw_text` が literal で在るか(接地)
- ③ `normalizer` を通した `raw_text` が `value` と一致するか

## いつも成り立つこと

`get(key)` が値を返すのは、**その key の行が 1 行だけで、原本の現物の sha256 が列と一致し、`locator` の場所に `raw_text` が literal で在り(`xlsx_cell` はセルの中身と一致)、名前で指定した正規化を通した `raw_text` が `value` と一致する行だけ**。それ以外(`unavailable`・検査落ち・台帳に無い key)は**値を返さず `PinError` で止まる**。`manual` の行は場所を検査できないので、返り値に必ず転記の印(`transcribed`)が付く。

この 1 文は `tests/test_source_pin_property.py` が性質テスト(hypothesis)で確かめている。原本(テキスト・HTML・xlsx・手元の記録・画像だけの PDF に見立てた合成ファイル)とピンの表を毎回乱数で作り直す。値は正規化したあとの値を先に決め、そこから原本に書く生の文字を組み立てる(`1230000` から `１，２３０，０００円` と `全角半角+カンマ除去+円` を作る、など)ので、期待値は道具の正規化・読み取り・検査を通さずに分かる。ピンの 3 割くらいに 1 か所だけ困る値(value を 1 字変える・生の文字に原本に無い字を足す・`locator` を原本の外や隣へずらす・sha256 列の書き換え・`normalizer` の空欄や登録外の名前・`captured_at` の空・登録外の `method`・xlsx の生の文字を部分文字列にする・`unavailable` の行に value)を入れ、原本ファイルの書き換えと削除・同じ key の行・台帳に無い key も混ぜて、毎回この 1 文が成り立つかを見る(乱数は固定で、毎回同じ 200 通り)。決まった fixture を 1 か所ずつ書き換える `test_measure_tampering` と違い、原本もピンも毎回作り直す。テストの実行には pytest と hypothesis が要る(道具そのものは標準ライブラリだけで動く)。

## 止まる理由コード(8 つ)

| 理由コード | 何が起きたか |
|---|---|
| 原本の sha が違う | 配布元が差し替えた / 原本が見つからない |
| locator が範囲外 | シート・セル・行番号が原本の範囲の外 |
| 生の文字が指定場所に無い | 接地が切れている(場所はあるが文字が違う) |
| normalizer 空欄 | 正規化の名前が書かれていない。評価せずに止める |
| normalizer を通しても value と合わない | 通した結果が `value` と一致しない |
| unavailable なのに value がある | 取れないと書いた行に値が入っている(推測値の混入) |
| 同じ key が 2 行 | どちらを使うかが表から決まらない |
| 列が足りない | ピン行として読めない(必要な列が空 / 登録されていない `method`・`normalizer` 名) |

`get(key)` は **検査を通った行だけ** 返す。`unavailable`・検査落ち・台帳に無い key は止まり、
近い key・前年の行・直近の値へ落ちる経路は無い(引数も持たない)。

## 使い方

```
python -X utf8 source_pin.py init pins.csv                  # 見出しを書き出す
python -X utf8 source_pin.py verify fixtures/pins.csv       # 全ピンを原本に突き合わせる
python -X utf8 source_pin.py get fixtures/pins.csv 等級上限  # 検査を通った行だけ返す
python -X utf8 source_pin.py map fixtures/pins.csv          # 原本の種類 × 取り出し方の対応表
```

終了コード: `0` = 検査を通った(`unavailable` の行は止まらない。取れないことは記録であって異常ではない)/
`3` = 止まったピンがある / `2` = ピンの表が読めない。

関数で呼ぶなら `PinTable.load` / `verify` / `verify_pin` / `get` / `source_map` / `normalize`。

## 試験

```
python -m pytest tools/source_pin -q
```

fixture は全て合成データ(`fixtures/make_fixtures.py`)で、地域名も値も出典名も架空。実在の料率・限度額は
入っていない。`genpon_ryouritsu.xlsx` も生成器が `zipfile` で最小の OOXML を組んで作るので、
外部ライブラリなしで毎回同じ sha256 になる。

後半の `test_measure_*` が記事の数値の出どころ。決定論なので、値が変われば記事の数字も変える。

## できないこと

- 値そのものの正しさ・原本の解釈は判定しない(原本の場所と文字に合っているかだけ)
- `manual` の行は接地を検査できない。生の文字と `value` を揃えて書き換えられると検査は通る
- 配布元の URL が生きているか・最新かは見ない(ファイルの指紋と場所だけ)
- xlsx の計算式セルは計算結果(`<v>`)の生の文字を返す。式そのものは見ない
- 依存は標準ライブラリだけ(`zipfile` / `xml.etree` / `hashlib` / `csv` / `json` / `html.parser` /
  `unicodedata` / `decimal` / `argparse`)

ライセンス MIT。
