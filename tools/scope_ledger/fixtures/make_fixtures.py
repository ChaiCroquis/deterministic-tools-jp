"""scope_ledger の合成 fixture を作る。実データ・実在の取引先名・実在のパスは 1 つも入れない。

作るもの(destination の下)

  src/            突き合わせる対象に見立てた小さな python script(と、python でないファイル 1 つ)
  sengen.csv      宣言表(18 行)。4 値と「機械では読めない」の理由コード 4 個が出そろう形
  sengen_*.csv    崩した宣言表(止まる理由コードを 1 つずつ通すため)

**構文として壊れたファイル(src/kowareta.py)は、この生成器が書くときだけ存在する。** repo には
置かない(置くと、道具の依存を検査する側がその 1 本を読めずに落ちる)。テストは tmp に build して使う。

合成 script はどれも実行されない。scope_ledger は対象を実行も import もせず、構文木だけを読む。
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

HEADER = ("tool", "line", "declaration", "source", "kind", "target", "path")

# 突き合わせる対象に見立てた合成 script。1 本につき 1 つの形だけを持たせている
SCRIPTS = {
    "src/net_ok.py": (
        '# 外向きの通信を持たない形に見立てた合成 script\n'
        'import csv\n'
        'import json\n\n\n'
        'def load(path):\n'
        '    return list(csv.DictReader(open(path, encoding="utf-8").read().splitlines()))\n\n\n'
        'def dump(rows):\n'
        '    return json.dumps(rows, ensure_ascii=False)\n'
    ),
    "src/net_ng.py": (
        '# 宣言と一致しない形に見立てた合成 script(名指しのモジュールを取り込んでいる)\n'
        'import json\n'
        'import urllib.request\n\n\n'
        'def fetch(url):\n'
        '    return urllib.request.urlopen(url).read()\n\n\n'
        'def dump(rows):\n'
        '    return json.dumps(rows, ensure_ascii=False)\n'
    ),
    "src/shell_ok.py": (
        '# シェルを経由しない形に見立てた合成 script\n'
        'import subprocess\n\n\n'
        'def run(argv, folder, seconds):\n'
        '    return subprocess.run(argv, cwd=folder, timeout=seconds, shell=False)\n'
    ),
    "src/shell_ng.py": (
        '# 宣言と一致しない形に見立てた合成 script(名指しの値まで一致する)\n'
        'import subprocess\n\n\n'
        'def run(command, folder):\n'
        '    return subprocess.run(command, cwd=folder, shell=True)\n'
    ),
    "src/write_ok.py": (
        '# 書き込まない形に見立てた合成 script(読み取りだけ)\n'
        'import hashlib\n\n\n'
        'def fingerprint(path):\n'
        '    with open(path, "rb") as f:\n'
        '        return hashlib.sha256(f.read()).hexdigest()\n'
    ),
    "src/write_ng.py": (
        '# 宣言と一致しない形に見立てた合成 script(書き込みのモードで開いている)\n'
        'import json\n\n\n'
        'def save(path, rows):\n'
        '    with open(path, "w", encoding="utf-8", newline="") as f:\n'
        '        f.write(json.dumps(rows, ensure_ascii=False))\n'
    ),
    "src/opt_ok.py": (
        '# 名指しの引数を持たない形に見立てた合成 script\n'
        'def resolve(table, key, case, on=None):\n'
        '    row = table.get(key)\n'
        '    return row if row else None\n'
    ),
    "src/opt_ng.py": (
        '# 宣言と一致しない形に見立てた合成 script(名指しの引数が定義に在る)\n'
        'def resolve(table, key, case, on=None, fallback=None):\n'
        '    row = table.get(key)\n'
        '    return row if row else fallback\n'
    ),
    "src/cli_ok.py": (
        '# CLI に名指しの option を持たない形に見立てた合成 script\n'
        'import argparse\n\n\n'
        'def build_parser():\n'
        '    ap = argparse.ArgumentParser()\n'
        '    ap.add_argument("decl")\n'
        '    return ap\n'
    ),
    "src/cli_ng.py": (
        '# 宣言と一致しない形に見立てた合成 script(名指しの option が定義に在る)\n'
        'import argparse\n\n\n'
        'def build_parser():\n'
        '    ap = argparse.ArgumentParser()\n'
        '    ap.add_argument("decl")\n'
        '    ap.add_argument("--rate", action="store_true")\n'
        '    return ap\n'
    ),
    "src/dyn_name.py": (
        '# 名前を動的に組み立てる形に見立てた合成 script(構文では呼び先が見えない)\n'
        'def call(module, name, value):\n'
        '    return getattr(module, name)(value)\n'
    ),
    "src/dyn_mode.py": (
        '# 開き方を変数で渡す形に見立てた合成 script(読み取りか書き込みかが構文では見えない)\n'
        'def touch(path, mode):\n'
        '    with open(path, mode) as f:\n'
        '        return f\n'
    ),
    "src/dyn_kwargs.py": (
        '# キーワードを辞書展開で渡す形に見立てた合成 script(中身が構文では見えない)\n'
        'import subprocess\n\n\n'
        'def run(argv, options):\n'
        '    return subprocess.run(argv, **options)\n'
    ),
    "src/kowareta.py": (
        '# 構文として壊れている形に見立てた合成 script(この生成器が書くときだけ存在する)\n'
        'def broken(:\n'
        '    return 1\n'
    ),
    "src/tsukurikake.txt": (
        "python でない対象に見立てた合成ファイル。中身は読まれない(拡張子で「機械では読めない」に落ちる)。\n"
    ),
}

SRC = "合成の宣言(架空)"

# 宣言表 18 行。4 値と、「機械では読めない」の理由コード 4 個が出そろう形にしてある
ROWS = [
    ["道具あ", "外向きの通信を持たない", "ネットワークを持たない(取りに行く経路が無い)",
     SRC + " L19", "import", "urllib", "src/net_ok.py"],
    ["道具い", "外向きの通信を持たない", "ネットワークを持たない(取りに行く経路が無い)",
     SRC + " L19", "import", "urllib", "src/net_ng.py"],
    ["道具う", "シェルを経由しない", "シェルを経由しない(文字列を結合してコマンドを作る経路が無い)",
     SRC + " L16", "kwarg", "shell=True", "src/shell_ok.py"],
    ["道具え", "シェルを経由しない", "シェルを経由しない(文字列を結合してコマンドを作る経路が無い)",
     SRC + " L16", "kwarg", "shell=True", "src/shell_ng.py"],
    ["道具お", "書き込まない", "書き出しを持たない(ファイルはこの部品からは開かない)",
     SRC + " L21", "write", "open", "src/write_ok.py"],
    ["道具か", "書き込まない", "書き出しを持たない(ファイルはこの部品からは開かない)",
     SRC + " L21", "write", "open", "src/write_ng.py"],
    ["道具き", "名指しの引数を持たない", "黙って直近値へ落ちる経路は無い(resolve に fallback の引数も無い)",
     SRC + " L18", "option", "resolve:fallback", "src/opt_ok.py"],
    ["道具く", "名指しの引数を持たない", "黙って直近値へ落ちる経路は無い(resolve に fallback の引数も無い)",
     SRC + " L18", "option", "resolve:fallback", "src/opt_ng.py"],
    ["道具け", "CLI に名指しの option が無い", "合格率だけを返す option を持たない",
     SRC + " L24", "option", "rate", "src/cli_ok.py"],
    ["道具こ", "CLI に名指しの option が無い", "合格率だけを返す option を持たない",
     SRC + " L24", "option", "rate", "src/cli_ng.py"],
    ["道具さ", "文字列を評価しない", "受け取った文字列を評価する経路が無い",
     SRC + " L30", "call", "eval", "src/net_ok.py"],
    ["道具し", "文字列を評価しない", "受け取った文字列を評価する経路が無い",
     SRC + " L30", "call", "eval", "src/dyn_name.py"],
    ["道具す", "書き込まない", "書き出しを持たない(ファイルはこの部品からは開かない)",
     SRC + " L21", "write", "open", "src/dyn_mode.py"],
    ["道具せ", "シェルを経由しない", "シェルを経由しない(文字列を結合してコマンドを作る経路が無い)",
     SRC + " L16", "kwarg", "shell=True", "src/dyn_kwargs.py"],
    ["道具そ", "外向きの通信を持たない", "ネットワークを持たない(取りに行く経路が無い)",
     SRC + " L19", "import", "urllib", "src/kowareta.py"],
    ["道具た", "外向きの通信を持たない", "ネットワークを持たない(取りに行く経路が無い)",
     SRC + " L19", "import", "urllib", "src/tsukurikake.txt"],
    ["道具ち", "値の正しさを判定しない", "値そのものの正しさは判定しない。解釈もしない",
     SRC + " L40", "", "", ""],
    ["道具つ", "書き込まない", "",
     SRC + " の できないこと 節を見た(この線についての宣言は無い)", "", "", ""],
]

# 崩した宣言表(止まる理由コードを 1 つずつ通す)。崩すのは 1 か所だけ
BROKEN = {
    "sengen_shutten_kuuhaku.csv": ("出典を空にする", 3),
    "sengen_path_nashi.csv": ("パスを空にする", 6),
    "sengen_shurui_gai.csv": ("種類を 5 種の外にする", 4),
    "sengen_meizashi_kuuhaku.csv": ("名指しの対象を空にする", 5),
    "sengen_juufuku.csv": ("同じ道具名と線の名前を 2 行にする", -1),
    "sengen_retsu_nashi.csv": ("path の列そのものを落とす", -2),
}


def write_csv(path: Path, header: tuple[str, ...], rows: list[list[str]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return path


def build(dest: Path) -> Path:
    """合成の対象 script と宣言表を dest の下に作る。"""
    dest = Path(dest)
    for name, body in SCRIPTS.items():
        p = dest / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8", newline="\n")
    write_csv(dest / "sengen.csv", HEADER, [list(r) for r in ROWS])
    for name, (_, column) in BROKEN.items():
        rows = [list(r) for r in ROWS]
        if column == -1:
            rows.append(list(rows[0]))
        elif column == -2:
            write_csv(dest / name, HEADER[:-1], [r[:-1] for r in rows])
            continue
        elif column == 4:
            rows[0][column] = "ast"
        else:
            rows[0][column] = ""
        write_csv(dest / name, HEADER, rows)
    return dest


if __name__ == "__main__":
    print(f"書いた: {build(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent)}")
