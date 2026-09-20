# articles/ — 記事の正本

1 記事 = 1 Markdown。先頭に frontmatter を置く。

```
---
title: 記事タイトル
labels: 設計, CSV
tool_url: https://github.com/<owner>/<repo>   # 記事で使う道具(ハブページの「道具(GitHub)」リンクになる)
---
本文…
```

使える記法(投稿係が HTML に変換する範囲): 見出し `##` `###`、箇条書き `- `、段落、リンク、`**強調**`、
画像 `![説明](figures/x.png)`(相対パスは GitHub raw URL に書き換わる)、フェンス付きコード、表。
それ以外は段落として素通しされる。

公開の順序: figures/ を push → dry-run で HTML を確認 → 画像 URL が 200 を返すことを確認 → `--publish`。
