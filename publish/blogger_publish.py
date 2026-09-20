"""決定論ツール記事の Blogger 投稿係 — 公式 API v3 を使う薄い CLI。

- Markdown → HTML とハブページ生成は純関数で、外部依存なし(dry-run とテストは単体で完結)
- 認証・投稿は Sentinel(blogger.toml の sentinel_root)の `sentinel/blogloop/{gauth,blogger}.py` を
  `--publish` / `--info` の時だけ import する(同じ Google アカウント・同じ OAuth トークン。
  資格情報はこのファイルにも設定ファイルにも書かない = Windows 資格情報マネージャーのエントリ名だけ)
- 記事は Markdown(frontmatter 付き)。画像は Blogger にアップロードできないので
  GitHub 上の PNG を URL 参照する(`figures/x.png` → `raw_base_url/figures/x.png` に書き換え)
- 「専用のページ」= Blogger の固定ページをシリーズのハブとして 1 枚作り、投稿のたびに
  台帳(ledger.jsonl)から目次を再生成して更新する。記事にはラベル(config)を付ける
- 既定は dry-run(HTML を出力するだけ)。`--publish` を付けた時だけ API を叩く。
  公開の実行は運用者の明示指示がある時に限る(外向き・取消しに手間がかかる操作)

使い方:
  python -X utf8 blogger_publish.py article.md                # dry-run: HTML を publish/out/ に出す
  python -X utf8 blogger_publish.py article.md --publish      # 投稿(下書き扱いにするなら --draft)
  python -X utf8 blogger_publish.py --page                    # ハブ固定ページを台帳から再生成(dry-run)
  python -X utf8 blogger_publish.py --page --publish          # ハブ固定ページを作成 / 更新
  python -X utf8 blogger_publish.py --info                    # 設定した blog_id のブログ名・URL を読む(読み取りのみ)
"""
from __future__ import annotations

import argparse
import datetime
import html
import json
import re
import sys
import tomllib
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CFG_PATH = HERE / "blogger.toml"
OUT = HERE / "out"
LEDGER = HERE / "ledger.jsonl"

_IMG = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
_FRONT = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")


# ---------- 設定・Sentinel(API 呼び出し時のみ)----------

def load_cfg() -> dict:
    return tomllib.loads(CFG_PATH.read_text(encoding="utf-8-sig"))


def sentinel_modules(sentinel_root: str):
    """Sentinel の blogloop モジュールを import(認証・API 呼び出しは全てそちら)。API を叩く時だけ呼ぶ。"""
    root = Path(sentinel_root or "")
    if not (root / "sentinel" / "blogloop" / "blogger.py").exists():
        raise SystemExit(f"Sentinel が見つからない: {root}(blogger.toml の sentinel_root を確認)")
    sys.path.insert(0, str(root))
    from sentinel.blogloop import blogger as B, gauth as G  # noqa: E402
    return root, B, G


# ---------- Markdown → HTML(限定サブセット + 画像 / コード / 表、純関数)----------

def inline(text: str) -> str:
    """インライン変換: エスケープ → リンク → 強調(この順で安全)。"""
    out = html.escape(text, quote=False)
    out = _LINK.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', out)
    return _BOLD.sub(r"<b>\1</b>", out)


def split_title(md: str) -> tuple[str, str]:
    """先頭の `# 見出し` をタイトルとして取り出し (title, 本文md) を返す。無ければ ("", 全文)。"""
    lines = md.splitlines()
    for i, line in enumerate(lines):
        if line.strip():
            if line.startswith("# "):
                return line[2:].strip(), "\n".join(lines[i + 1:]).strip()
            break
    return "", md.strip()


def parse_frontmatter(md: str) -> tuple[dict, str]:
    """`---` で囲んだ key: value を dict に(純関数)。labels は `a, b` を list に。"""
    m = _FRONT.match(md)
    if not m:
        return {}, md
    meta: dict = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    if "labels" in meta:
        meta["labels"] = [x.strip() for x in meta["labels"].split(",") if x.strip()]
    return meta, md[m.end():]


def rewrite_images(md: str, base_url: str) -> str:
    """相対の画像パスを GitHub 上の URL へ(純関数)。絶対 URL はそのまま。"""
    def sub(m: re.Match) -> str:
        alt, src = m.group(1), m.group(2)
        if not src.startswith(("http://", "https://")):
            src = base_url.rstrip("/") + "/" + src.lstrip("./")
        return f"![{alt}]({src})"
    return _IMG.sub(sub, md)


def _plain_block(md: str) -> str:
    """見出し / 箇条書き / 段落(限定サブセット)。"""
    out: list[str] = []
    in_list = False
    for raw in md.splitlines():
        line = raw.rstrip()
        if in_list and not line.lstrip().startswith("- "):
            out.append("</ul>")
            in_list = False
        if not line.strip():
            continue
        if line.startswith("### "):
            out.append(f"<h3>{inline(line[4:])}</h3>")
        elif line.startswith("## "):
            out.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("# "):
            out.append(f"<h2>{inline(line[2:])}</h2>")   # 本文中の # も h2 に落とす(h1 はタイトル専用)
        elif line.lstrip().startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inline(line.lstrip()[2:])}</li>")
        else:
            out.append(f"<p>{inline(line)}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def md_to_html(md: str) -> str:
    """限定サブセット Markdown + 画像 / フェンス付きコード / 表 → HTML(純関数)。未知の記法は段落として素通し。"""
    out: list[str] = []
    buf: list[str] = []
    in_code, code = False, []
    in_table, table = False, []

    def flush_buf() -> None:
        if buf:
            out.append(_plain_block("\n".join(buf)))
            buf.clear()

    def flush_table() -> None:
        nonlocal in_table
        rows = [r for r in table if not re.match(r"^\s*\|?\s*:?-{2,}", r)]
        cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
        if cells:
            th = "".join(f"<th>{inline(c)}</th>" for c in cells[0])
            trs = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in cells[1:])
            out.append('<table border="1" cellpadding="6" style="border-collapse:collapse">'
                       f"<thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>")
        table.clear()
        in_table = False

    for raw in md.splitlines():
        line = raw.rstrip()
        if in_code:
            if line.startswith("```"):
                out.append(f"<pre><code>{html.escape(chr(10).join(code), quote=False)}</code></pre>")
                code, in_code = [], False
            else:
                code.append(raw)
            continue
        if line.startswith("```"):
            flush_buf()
            if in_table:
                flush_table()
            in_code = True
            continue
        if line.lstrip().startswith("|"):
            flush_buf()
            in_table = True
            table.append(line)
            continue
        if in_table:
            flush_table()
        m = _IMG.fullmatch(line.strip())
        if m:
            flush_buf()
            alt, src = html.escape(m.group(1), quote=True), html.escape(m.group(2), quote=True)
            out.append('<div class="separator" style="clear:both;text-align:center">'
                       f'<a href="{src}"><img alt="{alt}" src="{src}" style="max-width:100%"/></a></div>')
            if m.group(1):
                out.append(f'<p style="text-align:center;font-size:90%;color:#555">{html.escape(m.group(1), quote=False)}</p>')
            continue
        buf.append(line)
    if in_table:
        flush_table()
    flush_buf()
    return "\n".join(out)


# ---------- ハブ固定ページ ----------

def load_ledger() -> list[dict]:
    if not LEDGER.exists():
        return []
    rows = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def hub_page_html(cfg: dict, rows: list[dict]) -> str:
    """台帳 → ハブ固定ページの HTML(純関数)。公開済みの行だけ、新しい順。"""
    intro = cfg.get("hub", {}).get("intro", "")
    parts = [f"<p>{html.escape(intro, quote=False)}</p>" if intro else ""]
    pub = [r for r in rows if r.get("published")]
    pub.sort(key=lambda r: r.get("date", ""), reverse=True)
    if not pub:
        parts.append("<p>(記事はまだありません)</p>")
    else:
        parts.append("<ul>")
        for r in pub:
            t, u = html.escape(r.get("title", ""), quote=False), html.escape(r.get("url", ""), quote=True)
            tool = r.get("tool_url", "")
            extra = f' — <a href="{html.escape(tool, quote=True)}">道具(GitHub)</a>' if tool else ""
            parts.append(f'<li>{r.get("date", "")} <a href="{u}">{t}</a>{extra}</li>')
        parts.append("</ul>")
    gh = cfg.get("github", {}).get("org_url", "")
    if gh:
        parts.append(f'<p>道具と図の生成スクリプトは <a href="{html.escape(gh, quote=True)}">GitHub</a> に置いています。</p>')
    return "\n".join(p for p in parts if p)


def _api(url: str, token: str, method: str = "GET", body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def find_page(base: str, blog_id: str, token: str, title: str) -> dict | None:
    obj = _api(f"{base}/blogs/{blog_id}/pages?status=live&status=draft", token)
    for p in obj.get("items", []):
        if p.get("title") == title:
            return p
    return None


def upsert_page(base: str, blog_id: str, token: str, title: str, content: str, insert_page) -> dict:
    page = find_page(base, blog_id, token, title)
    if page is None:
        return insert_page(blog_id, token, title, content, is_draft=False)
    return _api(f"{base}/blogs/{blog_id}/pages/{page['id']}", token, "PUT",
                {"kind": "blogger#page", "id": page["id"], "title": title, "content": content})


# ---------- main ----------

def _client(G, cfg: dict, root: Path):
    """OAuth クライアントは Sentinel の資格情報リゾルバに委ねる(値はここを通らない)。"""
    sc = cfg.get("sentinel_credentials", {})
    return G.resolve_client(sc.get("oauth_client_id_entry", ""), sc.get("oauth_client_secret_entry", ""),
                            root / "data" / "blogloop_client_secret.json")


def _token_and_blog(cfg: dict) -> tuple[object, str, str]:
    root, B, G = sentinel_modules(cfg.get("sentinel_root", ""))
    token = G.get_access_token(root / "data" / "blogloop_token.json", _client(G, cfg, root))
    blog_id = str(cfg.get("blog_id") or "") or B.get_blog_id((cfg.get("blog_url") or "").rstrip("/"), token)
    return B, token, blog_id


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="決定論ツール記事の Blogger 投稿係(既定 dry-run)")
    ap.add_argument("article", nargs="?", help="記事 Markdown(frontmatter: title / labels / tool_url)")
    ap.add_argument("--page", action="store_true", help="ハブ固定ページを台帳から再生成する")
    ap.add_argument("--publish", action="store_true", help="API を叩く(無ければ HTML を出すだけ)")
    ap.add_argument("--draft", action="store_true", help="--publish 時に下書きとして保存する")
    ap.add_argument("--info", action="store_true", help="設定した blog_id のブログ名・URL を読む(読み取りのみ)")
    args = ap.parse_args(argv)
    cfg = load_cfg()

    if args.info:
        B, token, blog_id = _token_and_blog(cfg)
        obj = _api(f"{B.BASE}/blogs/{blog_id}", token)
        print(json.dumps({k: obj.get(k) for k in ("id", "name", "url", "published")}, ensure_ascii=False))
        return 0
    if not args.article and not args.page:
        ap.error("記事 md か --page のどちらかを指定")

    OUT.mkdir(exist_ok=True)
    label = cfg.get("label", "")
    hub_title = cfg.get("hub", {}).get("title", "")

    if args.page:
        content = hub_page_html(cfg, load_ledger())
        (OUT / "hub_page.html").write_text(content, encoding="utf-8")
        print(f"ハブ固定ページ HTML → {OUT / 'hub_page.html'}({len(content)} 字、{len(load_ledger())} 行の台帳)")
        if not args.publish:
            return 0
        if not (cfg.get("blog_url") or cfg.get("blog_id")) or not hub_title:
            print("blogger.toml の blog_id / blog_url / hub.title が空"); return 2
        B, token, blog_id = _token_and_blog(cfg)
        res = upsert_page(B.BASE, blog_id, token, hub_title, content, B.insert_page)
        print(f"固定ページ {res.get('status', '')}: {res.get('url', '')}")
        return 0

    md_path = Path(args.article)
    meta, body = parse_frontmatter(md_path.read_text(encoding="utf-8-sig"))
    head_title, rest = split_title(body)
    title = meta.get("title") or head_title
    if not title:
        print("タイトルが無い(frontmatter title: か先頭の # 見出し)"); return 2
    if title == head_title:
        body = rest
    base_url = cfg.get("github", {}).get("raw_base_url", "")
    if not base_url:
        print("blogger.toml の github.raw_base_url が空 — 画像 URL を書き換えられない"); return 2
    content = md_to_html(rewrite_images(body, base_url))
    labels = [x for x in [label] + list(meta.get("labels", [])) if x]
    out_path = OUT / (md_path.stem + ".html")
    out_path.write_text(content, encoding="utf-8")
    print(f"dry-run: title={title!r} labels={labels} html {len(content)} 字 → {out_path}")
    if not args.publish:
        return 0
    if not (cfg.get("blog_url") or cfg.get("blog_id")):
        print("blogger.toml の blog_id / blog_url が空(どのブログに出すかは運用者が決める)"); return 2
    B, token, blog_id = _token_and_blog(cfg)
    post = B.insert_post(blog_id, token, title, content, labels=labels, is_draft=args.draft)
    rec = {"date": datetime.date.today().isoformat(), "title": title, "url": post["url"],
           "published": not args.draft, "labels": labels, "tool_url": meta.get("tool_url", ""),
           "source": md_path.name}
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"{'下書き' if args.draft else '公開'}: {post['url'] or '(下書き)'} — 台帳に追記。ハブは --page --publish で更新")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
