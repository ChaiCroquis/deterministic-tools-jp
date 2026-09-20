"""公開してはいけないものの混入検査(公開 repo 側でも動く汎用版。顧客名の検査は非公開側の export が担う)。

検査: 秘密らしき文字列(トークン / 鍵 / client_secret / パスワード代入)、ローカル PC のパス、メールアドレス、
資格情報っぽいファイル名。ヒットがあれば file:line を列挙して exit 2、無ければ "OK" で exit 0。

使い方: python -X utf8 scan_public.py <dir or file> [...]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SCAN_EXT = {".md", ".py", ".toml", ".json", ".yml", ".yaml", ".txt", ".svg", ".html", ".ps1", ".bat", ".cfg", ".ini"}
BAD_NAMES = re.compile(r"(^|[\\/])(\.env[^\\/]*|[^\\/]*token[^\\/]*\.json|[^\\/]*client_secret[^\\/]*\.json|[^\\/]*\.(pfx|pem|key))$", re.I)
PATTERNS = {
    "github token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    "google api key": re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}"),
    "slack token": re.compile(r"\bxox[abpr]-[A-Za-z0-9\-]{10,}"),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "secret assignment": re.compile(r"(client_secret|refresh_token|access_token|api[_-]?key|password|passwd)\s*[:=]\s*[\"'][^\"']{8,}[\"']", re.I),
    "local user path": re.compile(r"[A-Za-z]:\\+Users\\+[^\\\s\"']+", re.I),
    "local work path": re.compile(r"[A-Za-z]:\\+(work|Claude|workspace(-next)?)\\+", re.I),
    "unc host path": re.compile(r"\\\\\\\\[A-Za-z0-9_\-]+\\\\"),
    "email": re.compile(r"[A-Za-z0-9._%+-]+@(gmail|yahoo|outlook|icloud|hotmail)\.[a-z]{2,}", re.I),
    # 所属をにおわせる語(2026-09-20 決定: 公開物は「私の経験」の言い方に統一し、事務所・顧問先・自社・機器名を出さない)
    "affiliation word": re.compile(r"事務所|顧問先|弊所|当所|自社|所長|勤務先|PC42"),
}
# 検査自体の定義行(本ファイル)と、説明のために置いたプレースホルダは除外
ALLOW_LINE = re.compile(r"<owner>|<repo>|example\.blogspot|noreply@", re.I)


def scan_file(path: Path) -> list[str]:
    hits: list[str] = []
    if BAD_NAMES.search(str(path)):
        hits.append(f"{path}: 資格情報らしきファイル名")
        return hits
    if path.suffix.lower() not in SCAN_EXT:
        return hits
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return hits
    for i, line in enumerate(text.splitlines(), 1):
        if ALLOW_LINE.search(line):
            continue
        for name, pat in PATTERNS.items():
            if pat.search(line):
                hits.append(f"{path}:{i}: {name}: {line.strip()[:120]}")
    return hits


def scan(paths: list[str]) -> list[str]:
    hits: list[str] = []
    me = Path(__file__).resolve()
    for p in paths:
        root = Path(p)
        files = [root] if root.is_file() else [f for f in root.rglob("*") if f.is_file() and ".git" not in f.parts]
        for f in files:
            if f.resolve() == me:
                continue
            hits.extend(scan_file(f))
    return hits


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    hits = scan(argv)
    if hits:
        print("\n".join(hits))
        print(f"NG: {len(hits)} hits(公開しない。該当行を業種表現 / プレースホルダ / 設定ファイルへ移す)")
        return 2
    print("OK: 0 hits(秘密 / ローカルパス / メール なし)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
