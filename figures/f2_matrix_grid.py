"""fig-kit F2: matrix_grid — 2 軸の対応表を SVG で生成し Inkscape CLI で PNG 化する。意匠は style.py(共通)。
セルは白カード。`tone` で塗りを変える: default(白) / accent(藍の淡色 = 「後」「使用中」) / muted(無彩 = 「前」「封印」) / warn(橙の淡色 = 注意)。
入力 JSON: {"title","subtitle"?,"x_axis":{"label","cols":[..]},"y_axis":{"label","rows":[..]},
            "cells":[[{"name","items":[..],"tone"?},..],..],"legend"?:[[name,tone],..]}
使い方: python f2_matrix_grid.py <spec.json>
"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style as S  # noqa: E402

INKSCAPE = r"C:\Program Files\Inkscape\bin\inkscape.exe"
TONES = {"default": (S.CARD, S.LINE, S.ACCENT), "accent": (S.ACCENT_SOFT, S.ACCENT_LINE, S.ACCENT),
         "muted": (S.MUTED, S.LINE, S.INK2), "warn": (S.WARN_SOFT, S.WARN_LINE, S.WARN)}


def build_svg(spec: dict) -> str:
    cols, rows = spec["x_axis"]["cols"], spec["y_axis"]["rows"]
    max_items = max(len(c.get("items", [])) for row in spec["cells"] for c in row)
    cw, ch, gap, lx, pad = 430, max(120, 92 + 24 * max_items), 16, 190, 36
    ty = 132 if spec.get("subtitle") else 112
    W = lx + (cw + gap) * len(cols) - gap + pad
    H = ty + (ch + gap) * len(rows) - gap + pad + (36 if spec.get("legend") else 0)
    o = S.svg_open(W, H)
    o += S.title(pad, 48, spec["title"], spec.get("subtitle", ""))
    if spec["x_axis"].get("label"):
        o.append(S.text(lx + ((cw + gap) * len(cols) - gap) / 2, ty - 40, spec["x_axis"]["label"], 13, S.INK2, anchor="middle"))
    for j, c in enumerate(cols):
        o.append(S.text(lx + (cw + gap) * j + cw / 2, ty - 14, c, 16, S.INK, "bold", "middle"))
    if spec["y_axis"].get("label"):
        o.append(f'<text transform="translate({pad},{ty + ((ch + gap) * len(rows) - gap) / 2}) rotate(-90)" font-size="13" text-anchor="middle" fill="{S.INK2}">{S.escape(spec["y_axis"]["label"])}</text>')
    for i, r in enumerate(rows):
        y = ty + (ch + gap) * i
        o.append(S.text(lx - 18, y + ch / 2 + 5, r, 15, S.INK, "bold", "end"))
        for j, _ in enumerate(cols):
            x = lx + (cw + gap) * j
            cell = spec["cells"][i][j]
            fill, stroke, dot = TONES.get(cell.get("tone", "default"), TONES["default"])
            o += S.card(x, y, cw, ch, fill, stroke)
            o.append(S.text(x + 22, y + 36, cell["name"], 17, S.INK, "bold"))
            o += S.bullets(x + 26, y + 68, cell.get("items", []), 14, 24, S.INK, dot)
    if spec.get("legend"):
        ly, lx0 = H - pad + 2, lx
        for name, tone in spec["legend"]:
            fill, stroke, _ = TONES.get(tone, TONES["default"])
            o.append(f'<rect x="{lx0}" y="{ly - 12}" width="18" height="14" rx="4" fill="{fill}" stroke="{stroke}"/>')
            o.append(S.text(lx0 + 26, ly, name, 13, S.INK2))
            lx0 += 26 + 14 * len(name) + 28
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
