"""jp_charset のテスト。fixture は全て合成データ(fixtures/make_fixtures.py)。

後半の test_naive_order_* と test_measure_* は「cp932 を先に試す素朴な順」がどれだけ誤るかを
合成 1,000 行で数える(記事の数値はここから取る)。
"""
from __future__ import annotations

import random
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
import jp_charset as jc  # noqa: E402
from fixtures.make_fixtures import TEXT, EXT_TEXT  # noqa: E402


# ---- 各入力がどの段で通るか(F2 の各セル) --------------------------------------------------

@pytest.mark.parametrize("name, expected_enc, expected_text", [
    ("cp932.csv", "cp932", TEXT),
    ("utf8_bom.csv", "utf-8-sig", TEXT),
    ("utf8.csv", "utf-8", TEXT),
    ("utf16_bom.csv", "utf-16", TEXT),
    ("cp932_ext.csv", "cp932", EXT_TEXT),
    ("ascii.csv", "utf-8", "id,amount\r\n1,100\r\n"),
])
def test_detect_fixture(name, expected_enc, expected_text):
    r = jc.read_text(FX / name)
    assert r.encoding == expected_enc
    assert r.text == expected_text          # BOM が本文に残っていないことも含む


def test_empty_is_utf8_empty():
    assert jc.read_text(FX / "empty.csv") == jc.Decoded("utf-8", "")


def test_mixed_stops():
    """先頭 cp932 + 後半 utf-8 の連結ファイル。どの段も strict では通らず、止まる。"""
    with pytest.raises(jc.UndecodableError) as ei:
        jc.read_text(FX / "mixed.csv")
    assert "utf-8" in str(ei.value) and "cp932" in str(ei.value)


def test_utf16_without_bom_is_refused():
    """BOM 無し UTF-16 は NUL で拒否する(utf-8 strict を素通りして ASCII の残骸を返さない)。"""
    with pytest.raises(jc.UndecodableError) as ei:
        jc.read_text(FX / "utf16_nobom.csv")
    assert "NUL" in str(ei.value)


def test_never_replaces():
    """壊れたバイト列で '?' や U+FFFD を返さない(置換して読み進めない)。"""
    with pytest.raises(jc.UndecodableError):
        jc.detect(b"\x82\xa0\xff\xff\xfe\x00")


def test_str_input_is_type_error():
    with pytest.raises(TypeError):
        jc.detect("文字列")  # type: ignore[arg-type]


def test_bom_utf16_be():
    data = TEXT.encode("utf-16-be")
    assert jc.detect(b"\xfe\xff" + data) == jc.Decoded("utf-16", TEXT)


# ---- CLI ----------------------------------------------------------------------------------

def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "jp_charset.py"), *args],
                          capture_output=True, text=True, encoding="utf-8")


def test_cli_prints_encoding():
    r = run_cli(str(FX / "cp932.csv"))
    assert r.returncode == 0 and r.stdout.strip() == "cp932"


def test_cli_to_utf8(tmp_path):
    out = tmp_path / "out.csv"
    r = run_cli(str(FX / "cp932.csv"), "--to-utf8", str(out))
    assert r.returncode == 0
    assert out.read_bytes() == TEXT.replace("\r\n", "\n").encode("utf-8")   # BOM 無し・LF


def test_cli_exit3_when_undecodable():
    r = run_cli(str(FX / "mixed.csv"))
    assert r.returncode == 3 and "NG" in r.stderr


# ---- 「cp932 を先に試す」素朴な順がどれだけ誤るか(合成 1,000 行で数える) ------------------

FAMILY = ["佐藤", "鈴木", "高橋", "田中", "伊藤", "渡辺", "山本", "中村", "小林", "加藤",
          "吉田", "山田", "佐々木", "山口", "松本", "井上", "木村", "林", "斎藤", "清水"]
GIVEN = ["太郎", "花子", "一郎", "美咲", "健", "翔太", "陽菜", "大輔", "結衣", "拓也",
         "さくら", "ひろし", "ケンジ", "ミキ", "直樹", "優子", "誠", "恵", "浩二", "彩"]
DEPT = ["営業部", "総務部", "経理部", "製造部", "開発部", "人事部", "品質保証部", "物流センター", "第二工場", "本社"]


def synth_rows(n: int, seed: int = 20260921) -> list[str]:
    rng = random.Random(seed)
    rows = []
    for i in range(1, n + 1):
        rows.append(f"{i:04d},{rng.choice(FAMILY)} {rng.choice(GIVEN)},{rng.choice(DEPT)},{rng.randrange(180, 420) * 1000}")
    return rows


def naive_cp932_first(data: bytes) -> str:
    """カードで最初に計画した順(cp932 → utf-8-sig → utf-8 → utf-16)。比較用。"""
    for enc in ("cp932", "utf-8-sig", "utf-8", "utf-16"):
        try:
            return enc if data.decode(enc, errors="strict") is not None else enc
        except UnicodeDecodeError:
            continue
    raise ValueError("all failed")


HEADER = "社員番号,氏名,部署,基本給\r\n"


def test_measure_naive_order_on_utf8_rows():
    """UTF-8 の「ヘッダー + 1 行」ファイルを 1,000 本作って素朴な順に掛けると、何本が cp932 として『通ってしまう』か。"""
    rows = synth_rows(1000)
    # ヘッダーだけのファイル(列名の確認用に配られることがある)は、素朴な順では cp932 と判定される
    assert naive_cp932_first(HEADER.encode("utf-8")) == "cp932"
    wrong = sum(1 for r in rows if naive_cp932_first((HEADER + r + "\r\n").encode("utf-8")) == "cp932")
    # 記事に載せる数値。値そのものは固定 seed で決定論的に再現できる
    print(f"\n[measure] header+1row utf-8 files mis-taken as cp932 by naive order: {wrong}/1000")
    assert wrong == 351                    # 記事 #1 に載せた値。固定 seed(20260921)で決定論的に再現する。変わったら記事の数字も変える
    # この道具の順では 1,000 本全部 utf-8
    ok = sum(1 for r in rows if jc.detect((HEADER + r + "\r\n").encode("utf-8")).encoding == "utf-8")
    assert ok == 1000


def test_measure_this_order_on_cp932_rows():
    """cp932 の 1,000 行を 1 行ずつこの道具に掛けると、utf-8 strict を『通ってしまう』行が何行あるか。"""
    rows = synth_rows(1000)
    wrong = sum(1 for r in rows if jc.detect((r + "\r\n").encode("cp932")).encoding != "cp932")
    print(f"\n[measure] cp932 rows mis-taken as utf-8 by this order: {wrong}/1000")
    assert wrong == 0


def test_measure_whole_file_both_orders():
    """1,000 行をファイル 1 本として判定。UTF-8 ファイルは素朴な順で cp932 と誤判定されるか、この道具は正しいか。"""
    text = "社員番号,氏名,部署,基本給\r\n" + "\r\n".join(synth_rows(1000)) + "\r\n"
    u8, sj = text.encode("utf-8"), text.encode("cp932")
    print(f"\n[measure] whole utf-8 file: naive={naive_cp932_first(u8)} this={jc.detect(u8).encoding}")
    print(f"[measure] whole cp932 file: naive={naive_cp932_first(sj)} this={jc.detect(sj).encoding}")
    assert jc.detect(u8) == jc.Decoded("utf-8", text)
    assert jc.detect(sj) == jc.Decoded("cp932", text)
