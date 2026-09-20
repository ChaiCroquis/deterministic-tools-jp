"""fig-kit 共通スタイル(全ての図がここから描く。意匠を変える時はここだけ変える)。

方針(2026-09-20 決定): 1 アクセント色 + 無彩色、余白を広く、白いカード + 淡い影、角丸、細い矢印、
番号は丸バッジ、関所はピル。赤 / 緑の塗り分けはしない(比較は「淡い無彩色 vs アクセント」で示す)。
フォントは UD ゴシック優先(BIZ UDPGothic → Yu Gothic UI → Meiryo UI)。
"""
from __future__ import annotations
from xml.sax.saxutils import escape

FONT = "'BIZ UDPGothic', 'Yu Gothic UI', 'Meiryo UI', sans-serif"
BG = "#f5f6fa"           # 台紙
CARD = "#ffffff"         # カード
INK = "#1b1f2a"          # 本文
INK2 = "#5b6272"         # 補足
LINE = "#d9dce6"         # 罫線
ACCENT = "#3b5bdb"       # アクセント(藍)
ACCENT_SOFT = "#e7ecfb"  # アクセントの淡色(背景)
ACCENT_INK = "#24409b"   # アクセント上の文字
MUTED = "#eef0f5"        # 比較の「前」側
WARN = "#c2410c"         # 関所(橙)
WARN_SOFT = "#fff1e8"
SCALE = ["#e7ecfb", "#d6def9", "#c4d0f6", "#b0c1f2", "#9cb1ee"]   # 段階の淡→濃(同一色相)
ACCENT_LINE = "#c4d0f6"   # アクセント淡色カードの枠
WARN_LINE = "#f5c9ae"     # 橙淡色カードの枠


def svg_open(w: int, h: int) -> list[str]:
    """台紙 + 影フィルタ + 矢印マーカーの定義。"""
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="{FONT}">',
        '<defs>'
        # feDropShadow は Inkscape 1.4 で描画されない(要素ごと消える)ので、古典的な primitive で組む
        '<filter id="shadow" x="-5%" y="-5%" width="110%" height="120%">'
        '<feGaussianBlur in="SourceAlpha" stdDeviation="3" result="blur"/>'
        '<feOffset in="blur" dx="0" dy="2" result="off"/>'
        '<feFlood flood-color="#1b1f2a" flood-opacity="0.10" result="col"/>'
        '<feComposite in="col" in2="off" operator="in" result="sh"/>'
        '<feMerge><feMergeNode in="sh"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
        f'<marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="userSpaceOnUse">'
        f'<path d="M0,0.5 L7,4 L0,7.5" fill="none" stroke="{INK2}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></marker>'
        '</defs>',
        f'<rect width="{w}" height="{h}" fill="{BG}"/>',
    ]


def title(x: int, y: int, text: str, sub: str = "") -> list[str]:
    o = [f'<text x="{x}" y="{y}" font-size="24" font-weight="bold" fill="{INK}">{escape(text)}</text>']
    if sub:
        o.append(f'<text x="{x}" y="{y + 26}" font-size="14" fill="{INK2}">{escape(sub)}</text>')
    return o


def card(x: float, y: float, w: float, h: float, fill: str = CARD, stroke: str = LINE, accent_bar: str | None = None) -> list[str]:
    o = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="{stroke}" stroke-width="1" filter="url(#shadow)"/>']
    if accent_bar:
        o.append(f'<rect x="{x}" y="{y}" width="6" height="{h}" rx="3" fill="{accent_bar}"/>')
    return o


def badge(cx: float, cy: float, label: str, fill: str = ACCENT, ink: str = "#ffffff", r: float = 14) -> list[str]:
    return [f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"/>',
            f'<text x="{cx}" y="{cy + 5}" font-size="14" font-weight="bold" text-anchor="middle" fill="{ink}">{escape(label)}</text>']


def pill(cx: float, cy: float, text: str, fill: str = WARN_SOFT, stroke: str = WARN, ink: str = WARN, size: int = 13) -> list[str]:
    w = size * 0.95 * len(text) + 28
    return [f'<rect x="{cx - w / 2}" y="{cy - 14}" width="{w}" height="28" rx="14" fill="{fill}" stroke="{stroke}" stroke-width="1"/>',
            f'<text x="{cx}" y="{cy + 5}" font-size="{size}" text-anchor="middle" fill="{ink}">{escape(text)}</text>']


def arrow(x1: float, y1: float, x2: float, y2: float) -> str:
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{INK2}" stroke-width="1.6" stroke-linecap="round" marker-end="url(#arrow)"/>'


def text(x: float, y: float, s: str, size: int = 14, fill: str = INK, weight: str = "normal", anchor: str = "start") -> str:
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" fill="{fill}">{escape(s)}</text>'


def bullets(x: float, y: float, items: list[str], size: int = 14, gap: int = 24, fill: str = INK, dot: str = ACCENT) -> list[str]:
    o = []
    for k, it in enumerate(items):
        yy = y + gap * k
        o.append(f'<circle cx="{x}" cy="{yy - 5}" r="2.5" fill="{dot}"/>')
        o.append(text(x + 12, yy, it, size, fill))
    return o


def footer(x: int, y: int, s: str) -> str:
    return text(x, y, s, 13, INK2)
