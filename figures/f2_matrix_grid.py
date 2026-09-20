"""fig-kit F2: matrix_grid — 2 軸の対応表を SVG で生成し Inkscape CLI で PNG 化する。
入力 JSON: {"title","x_axis":{"label","cols":[..]},"y_axis":{"label","rows":[..]},"cells":[[{"name","items":[..]},..],..],"out"}
使い方: python f2_matrix_grid.py <spec.json>
"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
from xml.sax.saxutils import escape

INKSCAPE = r"C:\Program Files\Inkscape\bin\inkscape.exe"
FONT = "Meiryo, 'Yu Gothic', sans-serif"
PALETTE = ["#dbeafe", "#dcfce7", "#fef3c7", "#fde2e2"]


def build_svg(spec: dict) -> str:
    cols, rows = spec["x_axis"]["cols"], spec["y_axis"]["rows"]
    cw, ch, lx, ty, pad = 420, 250, 170, 110, 24
    W, H = lx + cw * len(cols) + pad, ty + ch * len(rows) + pad
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">',
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
         f'<text x="{pad}" y="40" font-size="26" font-weight="bold" fill="#111">{escape(spec["title"])}</text>',
         f'<text x="{lx + cw * len(cols) / 2}" y="78" font-size="16" text-anchor="middle" fill="#444">{escape(spec["x_axis"]["label"])}</text>']
    for j, c in enumerate(cols):
        o.append(f'<text x="{lx + cw * j + cw / 2}" y="{ty - 10}" font-size="18" font-weight="bold" text-anchor="middle" fill="#222">{escape(c)}</text>')
    o.append(f'<text transform="translate(28,{ty + ch * len(rows) / 2}) rotate(-90)" font-size="16" text-anchor="middle" fill="#444">{escape(spec["y_axis"]["label"])}</text>')
    k = 0
    for i, r in enumerate(rows):
        y = ty + ch * i
        o.append(f'<text x="{lx - 12}" y="{y + ch / 2}" font-size="17" font-weight="bold" text-anchor="end" fill="#222">{escape(r)}</text>')
        for j, _ in enumerate(cols):
            x = lx + cw * j
            cell = spec["cells"][i][j]
            o.append(f'<rect x="{x + 4}" y="{y + 4}" width="{cw - 8}" height="{ch - 8}" rx="10" fill="{PALETTE[k % 4]}" stroke="#94a3b8"/>')
            o.append(f'<text x="{x + 18}" y="{y + 38}" font-size="19" font-weight="bold" fill="#0f172a">{escape(cell["name"])}</text>')
            for n, it in enumerate(cell["items"]):
                o.append(f'<text x="{x + 22}" y="{y + 68 + 24 * n}" font-size="15" fill="#1e293b">・{escape(it)}</text>')
            k += 1
    o.append("</svg>")
    return "\n".join(o)


def main(path: str) -> None:
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    out = Path(path).with_suffix("")
    svg, png = out.with_suffix(".svg"), out.with_suffix(".png")
    svg.write_text(build_svg(spec), encoding="utf-8")
    subprocess.run([INKSCAPE, str(svg), "--export-type=png", f"--export-filename={png}", "--export-width=1600"], check=True)
    print(f"wrote {svg}\nwrote {png}")


if __name__ == "__main__":
    main(sys.argv[1])
