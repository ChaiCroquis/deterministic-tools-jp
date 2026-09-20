"""blogger_publish の決定論部のオフライン検証(API も Sentinel も不要)。python -X utf8 test_blogger_publish.py"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import blogger_publish as P  # noqa: E402

cfg = P.load_cfg() if P.CFG_PATH.exists() else {"hub": {"intro": "x"}, "github": {"org_url": "https://github.com/x"}}
results = []


def case(name: str, ok: bool, detail: str = "") -> None:
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}: {name}{(' — ' + detail) if detail and not ok else ''}")


# 1. frontmatter
meta, body = P.parse_frontmatter("---\ntitle: T\nlabels: a, b\ntool_url: https://x\n---\n# H\ntext")
case("frontmatter parse", meta == {"title": "T", "labels": ["a", "b"], "tool_url": "https://x"} and body.startswith("# H"), str(meta))

# 2. image rewrite
md = "![図](figures/a.png)\n![](https://h/x.png)"
rw = P.rewrite_images(md, "https://raw/base/")
case("image rewrite relative only", rw == "![図](https://raw/base/figures/a.png)\n![](https://h/x.png)", rw)

# 3. md_to_html: code / table / image / heading / list
md = "## 見出し\n- 項目 **強** [l](https://e)\n\n```bash\npython -X utf8 x.py <a>\n```\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n![cap](https://h/i.png)\n段落"
h = P.md_to_html(md)
case("code block escaped", "<pre><code>python -X utf8 x.py &lt;a&gt;</code></pre>" in h, h)
case("table", "<table" in h and "<th>a</th>" in h and "<td>2</td>" in h, h)
case("image + caption", 'src="https://h/i.png"' in h and ">cap<" in h, h)
case("heading/list/inline", "<h2>見出し</h2>" in h and "<li>項目 <b>強</b> <a href=\"https://e\">l</a></li>" in h, h)
case("paragraph after", h.rstrip().endswith("<p>段落</p>"), h)

# 4. hub page
rows = [{"date": "2026-09-01", "title": "A", "url": "https://b/a", "published": True, "tool_url": "https://g/a"},
        {"date": "2026-09-05", "title": "B", "url": "https://b/b", "published": True},
        {"date": "2026-09-06", "title": "C(下書き)", "url": "", "published": False}]
page = P.hub_page_html(cfg, rows)
case("hub newest first, drafts excluded", page.index(">B<") < page.index(">A<") and "C(" not in page, page)
case("hub tool link", 'href="https://g/a"' in page, page)
case("hub empty", "(記事はまだありません)" in P.hub_page_html(cfg, []))

n = sum(results)
print(f"Summary: {n}/{len(results)} passed")
raise SystemExit(0 if n == len(results) else 1)
