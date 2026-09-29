# formula_table — 数式を表の行に置き、丸め方を隣の列で指定して評価する

毎年変わる数表を行で持てても(post_007 の `asof_table`)、**計算の仕方そのものが改正される回**は
値の履歴では表せない。この部品は数式を文字列の列として行に持ち、有効期間と公表時点を値の行と同じ形で付ける。

そして **丸め方は式の隣の列で必ず指定させる**。規定の側は項目ごとに別の丸めを定めているのに、
実行環境の既定の丸めは項目を知らない。指定を省いた瞬間に静かに別の答えになるので、
**丸めを書いていない式は評価せずに止める**。部品は既定の丸めを持たない(`evaluate` に `rounding` 引数も無い)。

標準ライブラリのみ(`ast` / `decimal` / `json` / `csv` / `datetime` / `argparse`)、依存なし。

## 式の表(1 行 = 1 つの式の 1 つの版)

| 列 | 意味 |
|---|---|
| `id` | 何を計算するか |
| `expr` | 式の文字列。`ast` の allowlist で構文を絞る(下記) |
| `inputs` | 名前ごとの入力元。`名前=種類:参照先` を `;` で並べる。種類 = `case`(呼ぶ側が渡す項目)/ `value`(値の表の key)/ `formula`(別の式の id) |
| `rounding` | 丸めの名前。**空欄は許さない**(空欄の行は評価せずに止まる) |
| `valid_from` / `valid_to` | 有効時間。半開区間 `[valid_from, valid_to)`。`valid_from` 空 = 施行日未定(決して当たらない) |
| `known_from` / `known_to` | 知識時間(公表側)。`as_of` を渡すと「その時点の知識」で引ける。空は許さない |
| `known_quality` | `known_from` の質。`実値` / `仮置き` |
| `priority` | `0` 本則 / `10` 経過措置 / `20` 特例 |
| `source` | 出典。返り値に必ず付く |

値の表(式が `value:` で引く側)は `key` / `value` / `valid_from` / `valid_to` / `known_from` / `known_to` /
`known_quality` / `priority` / `source`。**式の版と値の版は同じ引き方**(知識時間 → 有効時間 → 最高 `priority`)で 1 行に決まる。

## 丸めの registry(`ROUNDINGS`、この 4 つで全部)

| 名前 | 中身 |
|---|---|
| `50銭以下切捨て` | 端数 0.50 以下を切り捨て、0.50 を超えたら切り上げる |
| `1円未満切捨て` | 1 円未満を切り捨てる |
| `円未満四捨五入` | 円未満を四捨五入する(端数 0.5 は上へ) |
| `丸めない` | 端数を残したまま次の式へ渡す |

名前が表に無ければ止まる。丸めの関数は式の中から呼べない(丸めるのは `rounding` 列だけ)。

## 構文の allowlist

許すのは 四則・単項マイナス・比較・条件式・登録済み関数(`min` / `max` / `abs`)の呼び出し・名前の参照だけ。
`import` / 属性アクセス / 添字 / 内包表記 / `lambda` / 代入 / `and`・`or` / べき乗 / 剰余 は **構文の段で拒否**する
(理由コードではなく表の不備として例外になる)。数は `Decimal` のみで、**float が混ざった時点で止める**。
式の中の小数リテラルは float を経由せず元の文字列から `Decimal` にするので、`0.1 + 0.2` は `0.3` になる。

## 止まる理由コード(`REASONS`、この 8 つで全部)

| 理由コード | 何が足りないか |
|---|---|
| `丸めが空欄` | 式の行に `rounding` が書かれていない。部品は既定の丸めを持たない |
| `未登録の丸めの名前` | `rounding` の名前が registry に無い |
| `未登録の関数` | 式が呼んでいる名前が関数の registry に無い |
| `float 混入` | 入力か定数に float が混ざっている |
| `式の版が as_of 時点で未公表` | 有効時間では当たる行があるが、`as_of` の時点では未公表 |
| `依存が循環している` | 式が直接または間接に自分自身を参照している |
| `入力が足りない` | `inputs` が要求している `case` の項目が渡されていない |
| `依存先が決まらない` | 引こうとした式の版か値の行が、収録範囲の外か、同順位で複数該当した |

**黙って既定の丸めや直近の版へ落ちる経路は作らない**(`evaluate` に fallback の引数も持たせていない)。

## 表そのものの検査(`validate`、直さない)

`有効期間の重なり` / `丸めが空欄` / `許可外の構文` / `依存の循環` を一覧で返すだけ。

## 使い方

```
python formula_table.py eval <式.csv> --id <id> --input 名前=値 [--input ...] [--values <値.csv>] --on YYYY-MM-DD [--as-of YYYY-MM-DD]
python formula_table.py validate <式.csv>
```

終了コードは 0 = 評価できた / 3 = 理由コードで止まった・表に不備があった / 2 = 表か引数の誤り。出力は 1 行 JSON。

```
$ python formula_table.py eval fixtures/keisan.csv --values fixtures/atai.csv --id 折半額 --input 報酬月額=300000 --on 2025-06-01
{"ok": true, "id": "折半額", "value": "15030", "raw": "15030.00", "rounding": "50銭以下切捨て", "used": [{"kind": "式", "name": "折半額", "row": 1, "valid_from": "2024-03-01", "source": "合成の端数処理メモ 2024(架空)"}, {"kind": "値", "name": "合成料率_甲", "row": 2, "valid_from": "2025-03-01", "source": "合成の料率表 2025 年度版(架空)"}]}
```

関数として呼ぶなら次のとおり。

```python
from datetime import date
from formula_table import FormulaTable, ValueTable, evaluate, validate

ft = FormulaTable.load("keisan.csv")     # .json でも同じ形
vt = ValueTable.load("atai.csv")
r = evaluate(ft, "折半額", {"報酬月額": "300000"}, on=date(2026, 4, 1), as_of=date(2026, 2, 5), values=vt)
print(r.value if r.ok else (r.reason, r.detail))
```

## fixture

`fixtures/make_fixtures.py` を実行すると `keisan.csv`(式 12 行)、`atai.csv`(値 7 行)、
`keisan_fuseigou.csv`(わざと壊した表 11 行)が出る。**全て合成データで、率も単価も出典名も架空。**
実在の料率・給付額・端数処理の規定値は 1 つも入れていない。

## テスト

```
python -m pytest tools/formula_table -q
```

## できないこと

- **値そのものの正しさ・式が制度に合っているかは判定しない。** 表に書いてあるとおりに計算するだけ
- 丸めの名前は 4 つしか持たない。別の丸め方が要るなら registry に足す(式の側には書けない)
- 状態を持つ計算(履歴を走査する判定)はできない。式は 1 回の評価で閉じる
- 表計算ソフトや他の言語の既定の丸めがどう振る舞うかは測っていない。測ったのは Python の `round` /
  `Decimal` の既定 / `int` の 3 つだけ
- 単位(円 / 銭 / %)を持たない。`/200` のような換算は式の側に書く
- `validate` が見るのは期間・丸めの空欄・構文・循環の形だけで、式の意味は見ない

ライセンス MIT。
