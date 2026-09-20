"""fig-kit F1: pipeline_flow — 段(stage)を左から右へ並べ、矢印でつなぎ、段の下に関所(gate)を置く流れ図。
意匠は style.py(共通)。段は番号バッジ付きの白カード、段階は同一色相の淡→濃、関所は橙のピル。
入力 JSON:
  {"title", "subtitle"?, "stages":[{"name","items":[..]}], "gates":[{"after":<stage index>,"label"}], "footer"?}
使い方: python f1_pipeline_flow.py <spec.json>
"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style as S  # noqa: E402

INKSCAPE = r"C:\Program Files\Inkscape\bin\inkscape.exe"


def build_svg(spec: dict) -> str:
    stages, gates = spec["stages"], spec.get("gates", [])
    n = len(stages)
    sw, gap, pad = 260, 56, 36
    top = 96 if not spec.get("subtitle") else 118
    max_items = max(len(s.get("items", [])) for s in stages)
    sh = 76 + 24 * max_items
    gate_h = 56 if gates else 0
    W = pad * 2 + sw * n + gap * (n - 1)
    H = top + sh + gate_h + (44 if spec.get("footer") else 0) + pad
    o = S.svg_open(W, H)
    o += S.title(pad, 48, spec["title"], spec.get("subtitle", ""))
    for i, s in enumerate(stages):
        x = pad + i * (sw + gap)
        o += S.card(x, top, sw, sh)
        o.append(f'<rect x="{x}" y="{top}" width="{sw}" height="6" rx="3" fill="{S.SCALE[min(i, len(S.SCALE) - 1)]}"/>')
        o += S.badge(x + 26, top + 34, str(i + 1))
        o.append(S.text(x + 48, top + 40, s["name"], 17, S.INK, "bold"))
        o += S.bullets(x + 24, top + 76, s.get("items", []), 14, 24, S.INK, S.ACCENT)
        if i < n - 1:
            o.append(S.arrow(x + sw + 8, top + sh / 2, x + sw + gap - 8, top + sh / 2))
    gy = top + sh + 34
    for g in gates:
        x = pad + g["after"] * (sw + gap) + sw + gap / 2
        o.append(f'<line x1="{x}" y1="{top + sh + 2}" x2="{x}" y2="{gy - 16}" stroke="{S.WARN}" stroke-width="1.2" stroke-dasharray="3 4" stroke-linecap="round"/>')
        o += S.pill(x, gy, g["label"])
    if spec.get("footer"):
        o.append(S.footer(pad, H - pad + 6, spec["footer"]))
    o.append("</svg>")
    return "\n".join(o)


def main(path: str) -> None:
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    out = Path(path).with_suffix("")
    svg, png = out.with_suffix(".svg"), out.with_suffix(".png")
    svg.write_text(build_svg(spec), encoding="utf-8")
    subprocess.run([INKSCAPE, str(svg), "--export-type=png", f"--export-filename={png}", "--export-width=1800"], check=True)
    print(f"wrote {svg}\nwrote {png}")


if __name__ == "__main__":
    main(sys.argv[1])
