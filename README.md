# deterministic-tools-jp — 決定論の道具で現実の仕事を再現する(記事・図・スクリプトの置き場)

現実の仕事(データ移行、給与・社会保険の計算、帳票の突合)を **AI + 決定論の道具** で再現できるかを実測し、
手順・スクリプト・検証方法を省略せずに公開しています。記事は Blogger、道具と図の生成器はこの repo。

軸は「**SaaS と現場の実データのあいだをどう埋めるか**」。例は給与・社会保険(社労士の仕事)で書きますが、
部品は業種に依りません。記事ごとに「別の業種ならこう応用する」を添えます。

- 記事の一覧(ハブ): [決定論ツール — 記事と道具の一覧](https://chronicles-of-solo-parenting.blogspot.com/p/blog-page.html)(Blogger の固定ページ)
- 記事 #0: [同じ仕事を、AI と決定論の道具で組み直すと何が変わるか](https://chronicles-of-solo-parenting.blogspot.com/2026/09/ai.html)
- 立ち位置: 生成 AI(画像・動画モデル)ではなく、コードが計算で描く・検算する側。正確さ・再現性・量産が要る場所に寄せる

<!-- article-links:begin (publish/readme_links.py が台帳から生成。手で直さない) -->
## 記事の一覧

公開のたびに台帳から自動で更新しています。記事は Blogger、道具はこの repo の `tools/`。

| 公開日 | 記事 | 道具 |
|---|---|---|
| 2026-09-20 | [同じ仕事を、AI と決定論の道具で組み直すと何が変わるか](https://chronicles-of-solo-parenting.blogspot.com/2026/09/ai.html) | — |
| 2026-09-21 | [日本語 CSV の文字コードは、推測せずに順番に試す](https://chronicles-of-solo-parenting.blogspot.com/2026/09/csv.html) | [`tools/jp_charset`](tools/jp_charset) |
| 2026-09-22 | [和暦の日付は、改元の日を境界として西暦に直す](https://chronicles-of-solo-parenting.blogspot.com/2026/09/blog-post.html) | [`tools/wareki`](tools/wareki) |
| 2026-09-23 | [氏名の名寄せは、文字を寄せるところで止めて人に返す](https://chronicles-of-solo-parenting.blogspot.com/2026/09/blog-post_22.html) | [`tools/jp_name`](tools/jp_name) |
| 2026-09-24 | [会社名は寄せずに、公表されている番号で突き合わせる](https://chronicles-of-solo-parenting.blogspot.com/2026/09/blog-post_23.html) | [`tools/jp_corp`](tools/jp_corp) |
| 2026-09-26 | [書き出した取込 CSV は、読み戻して件数と合計を突き合わせる](https://chronicles-of-solo-parenting.blogspot.com/2026/09/csv_01431241508.html) | [`tools/intake_csv`](tools/intake_csv) |
| 2026-09-27 | [色は値ではないので、理由の列を先に置いてから塗る](https://chronicles-of-solo-parenting.blogspot.com/2026/09/blog-post_26.html) | [`tools/excel_report`](tools/excel_report) |
| 2026-09-28 | [同じ日付で引いても答えが変わるので、基準日と公表時点を列にする](https://chronicles-of-solo-parenting.blogspot.com/2026/09/blog-post_28.html) | [`tools/asof_table`](tools/asof_table) |
| 2026-09-29 | [数式は表の行に置き、丸め方は隣の列に書く](https://chronicles-of-solo-parenting.blogspot.com/2026/09/blog-post_137.html) | [`tools/formula_table`](tools/formula_table) |
| 2026-09-30 | [数表の更新は、いつ何が変わったかを台帳に残してから差し替える](https://chronicles-of-solo-parenting.blogspot.com/2026/09/blog-post_29.html) | [`tools/update_ledger`](tools/update_ledger) |
| 2026-10-01 | [公式の数表は、取れない場所を先に地図にしてから取りに行く](https://chronicles-of-solo-parenting.blogspot.com/2026/09/blog-post_30.html) | [`tools/source_pin`](tools/source_pin) |
| 2026-10-02 | [2 つの経路で同じ数字を取ったら、合わない前に「同じものか」を疑う](https://chronicles-of-solo-parenting.blogspot.com/2026/10/2.html) | [`tools/cross_route`](tools/cross_route) |
| 2026-10-03 | [人ごとと項目ごとに足して、両方が合うまで取込には渡さない](https://chronicles-of-solo-parenting.blogspot.com/2026/10/blog-post.html) | [`tools/tally_gate`](tools/tally_gate) |
| 2026-10-04 | [帳票の形が相手先ごとに違っても、核は太らせず読み取り係を足す](https://chronicles-of-solo-parenting.blogspot.com/2026/10/blog-post_03.html) | [`tools/reader_registry`](tools/reader_registry) |
| 2026-10-05 | [取り込めない行は直さずに、機械が決めてよいところまでで仕分ける](https://chronicles-of-solo-parenting.blogspot.com/2026/10/blog-post_04.html) | [`tools/intake_triage`](tools/intake_triage) |
| 2026-10-06 | [数表は AI に思い出させず、引いた行に版を焼いて渡す](https://chronicles-of-solo-parenting.blogspot.com/2026/10/ai.html) | [`tools/context_pack`](tools/context_pack) |
| 2026-10-07 | [AI が返した数値は、渡した行に在るかどうかだけで突き合わせる](https://chronicles-of-solo-parenting.blogspot.com/2026/10/ai_082792725.html) | [`tools/answer_check`](tools/answer_check) |
| 2026-10-08 | [検証は在るかを数えず、走らせた結果だけを台帳に残す](https://chronicles-of-solo-parenting.blogspot.com/2026/10/blog-post_07.html) | [`tools/check_census`](tools/check_census) |
<!-- article-links:end -->

## この repo に入っているもの

| ディレクトリ | 中身 |
|---|---|
| `articles/` | 記事の正本(Markdown、frontmatter 付き)。Blogger へはここから投稿する |
| `figures/` | 図の生成器(fig-kit)と、その入力 JSON・生成済み SVG / PNG。記事内の図は全てここから決定論で生成(数値が変われば図も変わる) |
| `publish/` | Blogger 投稿係(公式 API v3)。既定は dry-run。設定ファイルの実体は含めない(`blogger.example.toml` を参照) |
| `tools/` | 記事ごとの小さな道具(1 記事 = 1 道具)。stdlib 中心、`tests/` と合成データの `fixtures/` 付き。外部依存は道具ごとの `requirements.txt`(版を固定)。CI は道具ごとの venv にそれだけを入れてテストを実行 |

## 図の生成(fig-kit)

```bash
cd figures
python -X utf8 f2_matrix_grid.py core_pack_quadrant.json   # JSON → SVG → PNG(Inkscape CLI)
```

前提: Python 3.11+、Inkscape 1.4(`f2_matrix_grid.py` 冒頭の `INKSCAPE` パスを環境に合わせる)。3D の図は Blender 5.x + bpy(生成器は記事と一緒に追加していく)。

## 投稿係(publish/)

```bash
cd publish
python -X utf8 test_blogger_publish.py            # オフライン検証(API 不要)
python -X utf8 blogger_publish.py ../articles/x.md  # dry-run → out/x.html
```

`--publish` を付けた時だけ Blogger API を叩く。認証・投稿の実体は別 repo(Sentinel の blogloop)を `sentinel_root` から import する設計で、資格情報はこの repo に一切置かない。

## 入っていないもの(意図的)

- 顧客データ、取引先や個人を特定できる情報(業種表現のみ)。書き手の所属を示す情報も置かない(この repo は個人の記録として書く)
- 事業計画・棚卸し・台帳・設定の実体(別の非公開 repo)
- 資格情報・トークン(Windows 資格情報マネージャー側)

公開前に `publish/scan_public.py` が秘密・ローカルパス・メールアドレスの混入を検査する(CI でも実行)。

## ライセンス

[MIT License](LICENSE)。コード・図の生成器・生成した図・記事本文を含む repo 全体に適用します(第三者の再利用・改変・再配布を許可、著作権表示の保持のみ条件)。
図や手順を記事や資料に転載する場合は、この repo へのリンクを添えてもらえると助かります(義務ではありません)。

## 状態

2026-09-20 開設。記事が増えるごとに `articles/`、上の「記事の一覧」、Blogger のハブページを更新します(一覧は公開のたびに台帳から自動で更新)。
