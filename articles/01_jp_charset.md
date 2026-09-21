---
title: 日本語 CSV の文字コードは、推測せずに順番に試す
labels: L1, 基礎部品
tool_url: https://github.com/ChaiCroquis/deterministic-tools-jp/tree/main/tools/jp_charset
pattern_id: I2
---

取込のたびに文字化けと戦う。その原因の多くは、CSV の文字コードを「推測している」ことにある。この記事では、推測をやめて固定の順番で厳密に復号を試し、全部失敗したら止まる判定器を 1 か所にまとめる。作ってみたら、最初に計画した順番が間違っていたので、それも含めて書く。

**なぜ重要か**: 文字コードの判定は、給与でも会計でも受注でも、CSV を受け取る仕事の一番手前にある。ここが揺れると、後ろの突合や検算が全部揺れる。私の記録では、この判定が 17 か所に別々に実装されていた。1 か所にまとめて、正しい順番を決めて、テストで固定する。それだけで後ろの道具が全部同じ挙動になる。

**要点**:
- 推測ライブラリは使わない。BOM を見て、NUL を見て、utf-8 と cp932 を厳密に試す。この順番を変えない
- cp932 を先に試してはいけない。UTF-8 のバイト列を cp932 のデコーダはかなりの割合で受け入れ、文字化けを黙って返す
- 全部失敗したら止まる。置換文字で読み進めない。止まった理由(どの段で失敗したか)を表示する
- 業種の語彙を一切持たないので、給与以外の CSV にそのまま持ち出せる

**数字で見る**: 合成した UTF-8 の CSV(ヘッダー + 1 行)を 1,000 本作って「cp932 を先に試す順」に掛けると、351 本が cp932 と誤判定された。順番を直した判定器では 1,000 本中 1,000 本が utf-8 と判定された。

---

## 何を解決するのか

給与ソフトが書き出す CSV は cp932(Shift_JIS の Windows 拡張)が多い。Excel で「CSV UTF-8」として保存すると BOM つきの UTF-8 になる。Web の業務システムからダウンロードすると BOM 無しの UTF-8 で、たまに UTF-16 が混ざる。取込側はこの全部を受け取る。

私の記録では、道具 67 本のうち 26 本が文字コードの問題を踏んでいて、判定処理は 17 か所に別々に書かれていた。全部、自分で書いたものだ。中身はどれも「cp932 で開いてみて、だめなら utf-8-sig、だめなら utf-8」という同じ形をしていて、微妙に順番や例外の扱いが違う。ある道具では通る CSV が、別の道具では文字化けする。原因を探すと、判定の順番の違いに行き着く。

推測ライブラリ(chardet のような、バイトの統計から文字コードを当てるもの)を使う手もある。私は使っていない。当たることが多いが、当たらなかったときに「なぜそう判定したか」を説明できず、同じファイルでもライブラリの版が変わると答えが変わることがあるからだ。この連載の道具は「同じ入力なら必ず同じ答え」を前提にしているので、推測は入れない。

代わりに、固定の順番で厳密に試す。厳密に、というのは Python の `errors="strict"` のことで、1 バイトでも解釈できない並びがあれば例外になる。この性質を使うと、推測なしで「この文字コードでは読めない」を確定できる。問題は、順番だ。

## 図 1 入力の種類ごとに、どこで通り、どこで止まるか

![入力の種類 × 判定の順番 — どこで通り、どこで止まるか](figures/jp_charset_cases.png)

最初に計画した順番は「cp932 → utf-8-sig → utf-8 → utf-16」だった。cp932 が一番多いから先に試す、という素朴な理由だ。テストを書いたら、これが壊れていた。

cp932 のデコーダは、UTF-8 の日本語バイト列をかなりの割合で「正しい cp932」として受け入れる。たとえば UTF-8 で書いた「社員番号,氏名,部署,基本給」という 1 行は、cp932 として例外なく復号でき、意味のない漢字の並びが返ってくる。ヘッダーだけの CSV(列名の確認用に配られることがある)を素朴な順に掛けると、cp932 と判定される。ヘッダー + 1 行のファイルを 1,000 本作ると、351 本が cp932 と誤判定された。逆方向、つまり cp932 のバイト列が utf-8 の厳密な復号を通ってしまうことは、同じ 1,000 行で 0 行だった。

だから順番は utf-8 → cp932 でなければならない。そして BOM は推測ではなく事実なので、最初に見て確定させる。BOM 無しの UTF-16 は NUL(0x00)を含むことで見分け、判定せずに止める。理由は後述する。

## 手順

判定器の中身は、これだけだ。stdlib のみで、依存はない。

```python
ORDER = ("utf-8", "cp932")   # BOM 判定の後に strict で試す順。変えない

def detect(data: bytes) -> Decoded:
    if data == b"":
        return Decoded("utf-8", "")
    # 1. BOM(決定論。推測ではない)
    if data.startswith(b"\xef\xbb\xbf"):
        return Decoded("utf-8-sig", data.decode("utf-8-sig", errors="strict"))
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return Decoded("utf-16", data.decode("utf-16", errors="strict"))
    # 2. NUL(BOM 無し UTF-16 / バイナリの疑い)
    if b"\x00" in data:
        raise UndecodableError("NUL(0x00)を含む: BOM 無し UTF-16 かバイナリの疑い。判定しない")
    # 3-4. 固定順で strict
    failures = []
    for enc in ORDER:
        try:
            return Decoded(enc, data.decode(enc, errors="strict"))
        except UnicodeDecodeError as e:
            failures.append(f"{enc}: byte {e.start} 付近 ({e.reason})")
    # 5. 全部失敗
    raise UndecodableError("固定順の全てで復号に失敗: " + " / ".join(failures))
```

`Decoded` は `(encoding, text)` の名前付きタプルで、`text` からは BOM が除かれている。呼ぶ側はこう書く。

```python
from jp_charset import read_text, UndecodableError

try:
    enc, text = read_text("kyuyo.csv")
except UndecodableError as e:
    print("止まった:", e)     # ここで人に戻す。置換して読み進めない
```

コマンドラインからも使える。文字コード名を 1 行返し、判定できなければ終了コード 3 で止まる。

```
python jp_charset.py kyuyo.csv                   # → cp932
python jp_charset.py kyuyo.csv --show            # 先頭 3 行も表示
python jp_charset.py kyuyo.csv --to-utf8 out.csv # UTF-8(BOM 無し・LF)で書き出す
```

後ろの道具は、全部この `read_text` を通す。判定の順番を変えたくなったら `ORDER` を 1 か所直し、テストで結果を見る。

## 検証

テストは 18 件。fixture は全て合成データで、氏名も部署も架空のものだ。実行結果をそのまま載せる。

```
$ python -m pytest tools/jp_charset -q
..................                                                       [100%]
18 passed in 0.31s
```

内訳は次のとおり。

| 入力 | 期待 | 結果 |
|---|---|---|
| cp932 の CSV | cp932 | 一致 |
| BOM つき UTF-8 | utf-8-sig(BOM は本文から除く) | 一致 |
| BOM 無し UTF-8 | utf-8 | 一致 |
| BOM つき UTF-16(LE と BE) | utf-16 | 一致 |
| 機種依存文字(㈱ ① 髙 﨑 Ⅱ)を含む cp932 | cp932 | 一致 |
| 空ファイル | utf-8、本文は空 | 一致 |
| 先頭 cp932 + 後半 UTF-8 の連結ファイル | 止まる(両方の失敗位置を表示) | 一致 |
| BOM 無し UTF-16 | NUL で止まる | 一致 |
| 壊れたバイト列 | 止まる(置換文字を返さない) | 一致 |
| CLI: 文字コード名の出力 / UTF-8 書き出し / 終了コード 3 | それぞれ | 一致 |

計測のテストも同じファイルにある。固定した乱数の種で合成した 1,000 行を使い、素朴な順(cp932 を先に)と、この道具の順を比べる。

```
[measure] header+1row utf-8 files mis-taken as cp932 by naive order: 351/1000
[measure] cp932 rows mis-taken as utf-8 by this order: 0/1000
[measure] whole utf-8 file: naive=utf-8-sig this=utf-8
[measure] whole cp932 file: naive=cp932 this=cp932
```

3 行目は補足で、1,000 行そろった UTF-8 のファイルなら素朴な順でも結果は正しい。どこかの行に cp932 として解釈できないバイトが混ざるからだ。つまり素朴な順は「大きいファイルなら当たり、小さいファイルでは中身次第」で、それは推測と同じことだと私は考えている。

## 図 2 判定の流れ

![文字コード判定の流れ — 推測せず、固定の順番で厳密に試す](figures/jp_charset_flow.png)

段は 5 つ。BOM を見る、NUL を見る、utf-8 を厳密に試す、cp932 を厳密に試す、全部失敗なら止まる。橙のピルが関所で、そこで確定するか止まる。止まるときは、どの段で何バイト目がだめだったかを表示する。人に戻すための情報だ。

## 道具

[jp_charset](https://github.com/ChaiCroquis/deterministic-tools-jp/tree/main/tools/jp_charset) に置いた。`jp_charset.py` 1 ファイルと、テスト、合成 fixture の生成スクリプトが入っている。ライセンスは MIT。

使い方は上の手順のとおり。関数として呼ぶなら `read_text(path)` か `detect(bytes)`、コマンドラインなら `python jp_charset.py FILE`。fixture を作り直したいときは `python fixtures/make_fixtures.py`。

## 別の業種なら

この判定器は、給与という語彙を 1 つも持っていない。持っているのは「BOM」「NUL」「utf-8」「cp932」だけだ。会計ソフトの仕訳 CSV、EC の受注 CSV、勤怠システムの打刻 CSV でも、書き出し側が cp932 か UTF-8 かで揺れる形は同じだと考えている。私が実測したのは給与まわりの CSV と、上の合成データだけなので、他の業種は「同じ詰まり方になりそうな例」であって実測ではない。変わるのは入力の例だけで、判定器そのものは書き換えずに持ち出せる。たとえば会計の仕訳 CSV なら「日付,借方科目,貸方科目,金額,摘要」のヘッダーが、上の「社員番号,氏名,部署,基本給」と同じ扱いになる。

## できないこと

- BOM 無しの UTF-16 は判定しない。NUL を含む時点で止める。素朴な順は utf-16 を最後に試すので OS の既定のバイト順と一致した時だけ正しく読めるが、それは環境依存なので私は採用しなかった。書き出し側に BOM を付けるか UTF-8 にしてもらう
- EUC-JP と ISO-2022-JP は順番に入れていない。私の環境では出会わないからで、必要なら `ORDER` に足してテストを追加する
- cp932 と utf-8 の両方で厳密に通るバイト列(ASCII だけの本文など)は、順番どおり utf-8 と答える。どちらでも同じ本文になるので実害は無いと考えているが、文字コード名を使って何かを分岐させる道具では注意がいる
- 途中で文字コードが変わるファイル(別のツールの出力を手で連結したもの)は止まる。分割して個別に判定する
- 上の数字は合成データと私の環境での実測で、他の人の環境で同じになるとは限らない。特に 351 という数は氏名や部署の語彙で変わる

自分でやる人へ: 道具と図の生成器は [GitHub](https://github.com/ChaiCroquis/deterministic-tools-jp) にあります(MIT、自由に使えます)。
自分の環境に合わせたい人へ: [GitHub の Issues](https://github.com/ChaiCroquis/deterministic-tools-jp/issues) で相談を受けます(道具の側を直して渡す形。データは預かりません)。
