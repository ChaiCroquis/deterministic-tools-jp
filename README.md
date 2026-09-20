# deterministic-tools-jp — 決定論の道具で現実の仕事を再現する(記事・図・スクリプトの置き場)

現実の仕事(データ移行、給与・社会保険の計算、帳票の突合)を **AI + 決定論の道具** で再現できるかを実測し、
手順・スクリプト・検証方法を省略せずに公開しています。記事は Blogger、道具と図の生成器はこの repo。

軸は「**SaaS と現場の実データのあいだをどう埋めるか**」。例は給与・社会保険(社労士の仕事)で書きますが、
部品は業種に依りません。記事ごとに「別の業種ならこう応用する」を添えます。

- 記事の一覧(ハブ): [決定論ツール — 記事と道具の一覧](https://chronicles-of-solo-parenting.blogspot.com/p/blog-page.html)(Blogger の固定ページ)
- 記事 #0: [同じ仕事を、AI と決定論の道具で組み直すと何が変わるか](https://chronicles-of-solo-parenting.blogspot.com/2026/09/ai.html)
- 立ち位置: 生成 AI(画像・動画モデル)ではなく、コードが計算で描く・検算する側。正確さ・再現性・量産が要る場所に寄せる

## この repo に入っているもの

| ディレクトリ | 中身 |
|---|---|
| `articles/` | 記事の正本(Markdown、frontmatter 付き)。Blogger へはここから投稿する |
| `figures/` | 図の生成器(fig-kit)と、その入力 JSON・生成済み SVG / PNG。記事内の図は全てここから決定論で生成(数値が変われば図も変わる) |
| `publish/` | Blogger 投稿係(公式 API v3)。既定は dry-run。設定ファイルの実体は含めない(`blogger.example.toml` を参照) |
| `tools/` | 記事ごとの小さな道具(1 記事 = 1 道具)。stdlib 中心、`tests/` と合成データの `fixtures/` 付き。CI でテストを実行 |

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

2026-09-20 開設。記事 1 本(#0)。記事が増えるごとに `articles/` と Blogger のハブページを更新します。
