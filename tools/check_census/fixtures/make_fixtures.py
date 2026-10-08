"""check_census の合成 fixture を作る。実データ・実在のツール名・実在のパスは 1 つも入れない。

作るもの

  proj/      合成プロジェクト。各フォルダに runner に見立てた小さな python script を 1 本置く
  sengen.csv 宣言表(10 行)。4 値と「走らなかった」の理由コードが出そろう形にしてある
  sengen_*.csv  崩した宣言表(止まる理由コードを 1 つずつ通すため)

runner の argv[0] は既定で "python"(PATH 上の python)。テストは build(dest, sys.executable) で
走っている処理系を指す宣言表を作り直すので、PATH に依存しない。

合成 runner は外へ 1 バイトも出ない。run_net.py は「外向きを使う検証」に見立てて、外向きの既定が
落とされている(proxy が閉じたポートを指す)ことを見て落ちるだけで、通信はしない。
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

SCRIPTS = {
    "tool_a/run_ok.py": '# 通る runner に見立てた合成 script\nprint("3 passed")\n',
    "tool_b/run_ng.py": '# 落ちる runner に見立てた合成 script\nimport sys\nprint("1 failed, 2 passed")\nsys.exit(1)\n',
    "tool_c/run_slow.py": '# timeout を超える runner に見立てた合成 script\nimport time\ntime.sleep(5)\nprint("3 passed")\n',
    "tool_e/run_ok.py": '# 在るか不明と数えられていた runner に見立てた合成 script\nprint("2 passed")\n',
    "tool_g/run_no_tests.py": ('# テストのファイルは在るが中に試験が 1 件も無い場合に見立てた合成 script\n'
                               'import sys\nprint("no tests ran")\nsys.exit(5)\n'),
    "tool_h/run_net.py": ('# 外向きを使う検証に見立てた合成 script。通信はせず、外向きの既定が落ちていることを見て落ちる\n'
                          'import os, sys\n'
                          'if os.environ.get("https_proxy", "").endswith(":9"):\n'
                          '    print("外向きの既定が落ちているので検証できない")\n'
                          '    sys.exit(1)\n'
                          'print("1 passed")\n'),
    "tool_k/run_net.py": ('# 同じ script を allow_network=はい の行から呼ぶ(宣言で許した側)\n'
                          'import os, sys\n'
                          'if os.environ.get("https_proxy", "").endswith(":9"):\n'
                          '    print("外向きの既定が落ちているので検証できない")\n'
                          '    sys.exit(1)\n'
                          'print("1 passed")\n'),
    "tool_i/run_yureru.py": ('# 2 回走らせると出力が変わる runner に見立てた合成 script(終了コードは毎回 0)\n'
                             'import time\nprint(f"3 passed in {time.perf_counter_ns()} ns")\n'),
    "tool_d/テストは無い.txt": "棚卸しの記録で「テストは無い」と数えられたフォルダに見立てた合成データ。\n",
    "tool_f/runnerは宣言されていない.txt": "テストは在ると数えられたが、走らせる argv が宣言されていないフォルダ。\n",
}

SOURCE = "合成の棚卸し記録(架空)"


def rows(python: str) -> list[list[str]]:
    def argv(*parts: str) -> str:
        return json.dumps([python, *parts], ensure_ascii=False)

    return [
        ["道具A_通る", "proj/tool_a", "在る", argv("run_ok.py"), "20", "はい", "", SOURCE],
        ["道具B_落ちる", "proj/tool_b", "在る", argv("run_ng.py"), "20", "いいえ", "", SOURCE],
        ["道具C_時間超過", "proj/tool_c", "在る", argv("run_slow.py"), "1", "いいえ", "", SOURCE],
        ["道具D_テスト無し", "proj/tool_d", "無い", "", "20", "いいえ", "", SOURCE],
        ["道具E_在るか不明", "proj/tool_e", "不明", argv("run_ok.py"), "20", "いいえ", "", SOURCE],
        ["道具F_runner未宣言", "proj/tool_f", "在る", "", "20", "いいえ", "", SOURCE],
        ["道具G_試験ゼロ", "proj/tool_g", "在る", argv("run_no_tests.py"), "20", "いいえ", "", SOURCE],
        ["道具H_外向き不許可", "proj/tool_h", "在る", argv("run_net.py"), "20", "いいえ", "", SOURCE],
        ["道具J_path無し", "proj/tool_j", "在る", argv("run_ok.py"), "20", "いいえ", "", SOURCE],
        ["道具K_外向き許可", "proj/tool_k", "在る", argv("run_net.py"), "20", "いいえ", "はい", SOURCE],
    ]


HEADER = ["name", "path", "declared", "runner", "timeout", "required", "allow_network", "source"]


def write_csv(path: Path, header: list[str], body: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(body)


def build(dest: Path, python: str = "python") -> Path:
    """合成プロジェクトと宣言表を dest に作る。"""
    dest.mkdir(parents=True, exist_ok=True)
    for rel, body in SCRIPTS.items():
        p = dest / "proj" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    base = rows(python)
    write_csv(dest / "sengen.csv", HEADER, base)

    # 2 回走らせると出力が変わる 1 行(本体の台帳には入れず、verify で観測する)
    write_csv(dest / "sengen_yureru.csv", HEADER,
              [["道具I_揺れる", "proj/tool_i", "在る",
                json.dumps([python, "run_yureru.py"], ensure_ascii=False), "20", "いいえ", "", SOURCE]])

    one = base[0]
    # 止まる理由コードを 1 つずつ通す崩した宣言表
    write_csv(dest / "sengen_runner_retsu_nashi.csv",
              [c for c in HEADER if c != "runner"], [[v for c, v in zip(HEADER, one) if c != "runner"]])
    write_csv(dest / "sengen_argv_moji.csv", HEADER,
              [[one[0], one[1], one[2], "python run_ok.py", one[4], one[5], one[6], one[7]]])
    write_csv(dest / "sengen_timeout_kuuhaku.csv", HEADER,
              [[one[0], one[1], one[2], one[3], "", one[5], one[6], one[7]]])
    write_csv(dest / "sengen_shutten_kuuhaku.csv", HEADER,
              [[one[0], one[1], one[2], one[3], one[4], one[5], one[6], ""]])
    write_csv(dest / "sengen_name_juufuku.csv", HEADER, [one, list(one)])
    # path 欄が空 = 走らなかった(宣言の列が空欄)
    write_csv(dest / "sengen_retsu_kuuhaku.csv", HEADER,
              [[one[0], "", one[2], one[3], one[4], one[5], one[6], one[7]]])
    # 宣言表として読めない(declared が 在る / 無い / 不明 のどれでもない)
    write_csv(dest / "sengen_yomenai.csv", HEADER,
              [[one[0], one[1], "たぶん在る", one[3], one[4], one[5], one[6], one[7]]])
    return dest


if __name__ == "__main__":
    out = build(HERE)
    print(f"書いた: {out}(runner の argv[0] は PATH 上の python。処理系は {sys.version.split()[0]})")
