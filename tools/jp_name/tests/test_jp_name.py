"""jp_name のテスト。fixture は全て合成データ(fixtures/make_fixtures.py)、氏名は架空。

後半の test_measure_* は、合成した 1,000 人の名簿 2 つで
  (a) 文字列の完全一致だけの突合
  (b) 類似度 0.8 以上を「同じ人」として自動採用する突合
  (c) この道具(キー照合 + 判断待ち)
を比べる(記事の数値はここから取る。固定 seed で決定論的に再現し、変わったら記事の数字も変える)。
"""
from __future__ import annotations

import csv
import difflib
import random
import subprocess
import sys
import unicodedata
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
import jp_name as J  # noqa: E402


# ---- 正規化と照合キー(F2 の各行) ------------------------------------------------------------

@pytest.mark.parametrize("a, b", [
    ("渡辺 太郎", "渡辺太郎"),            # 半角空白 / 区切り無し
    ("渡辺 太郎", "渡辺　太郎"),          # 全角空白
    ("渡辺 太郎", "渡辺・太郎"),          # 中黒
    ("渡辺 太郎", "渡辺,太郎"),           # コンマ
    ("渡辺 太郎", "渡邊 太郎"),           # 異体字
    ("渡辺 太郎", "渡邉太郎"),
    ("高橋 一郎", "髙橋 一郞"),           # はしごだか / 旧字の郎
    ("山崎 美咲", "山﨑 美咲"),           # 﨑(U+FA11)
    ("吉田 翔太", "𠮷田 翔太"),           # つちよし(U+20BB7、BMP 外)
    ("沢田 健", "澤田 健"),
    ("富田 結衣", "冨田 結衣"),
    ("広瀬 真一", "廣瀬 眞一"),
    ("浜田 恵子", "濵田 惠子"),
    ("島田 徳子", "嶋田 德子"),
    ("ワタナベ ハナコ", "ﾜﾀﾅﾍﾞ ﾊﾅｺ"),     # 半角カナ
    ("ワタナベ ハナコ", "わたなべ はなこ"),   # ひらがな
    ("ヤマダ タロウ", "ﾔﾏﾀﾞ･ﾀﾛｳ"),
    ("Yamada Taro", "Ｙａｍａｄａ　Ｔａｒｏ"),   # 全角英字(大文字小文字は畳まない)
])
def test_same_key(a, b):
    assert J.to_key(a) == J.to_key(b) != ""


@pytest.mark.parametrize("a, b", [
    ("斉藤 大輔", "斎藤 大輔"),        # 同値表に無い組(別の字)
    ("井ノ口 学", "井之口 学"),        # ノ と 之 は畳まない
    ("渡辺 太郎", "渡辺 次郎"),
    ("渡辺 太郎", "ワタナベ タロウ"),  # 漢字と読みは畳まない(読みを持っていない)
    ("高木 亮", "高本 亮"),
])
def test_different_key(a, b):
    assert J.to_key(a) != J.to_key(b)


def test_normalize_keeps_choon_and_drops_separators():
    assert J.normalize("ｻﾄｳ ﾏﾘｰ") == "サトウマリー"
    assert J.normalize("佐藤\t太郎\n") == "佐藤太郎"


def test_non_str_is_type_error():
    with pytest.raises(TypeError):
        J.to_key(12345)  # type: ignore[arg-type]


# ---- 同値表そのものの不変式 --------------------------------------------------------------

def test_variant_groups_are_disjoint_and_distinct():
    """どの字も 2 つの組に属さない。組の中の字は全て別のコードポイント。"""
    seen: set[str] = set()
    for g in J.VARIANT_GROUPS:
        assert len(g) >= 2 and len(set(g)) == len(g), g
        for ch in g:
            assert ch not in seen, ch
            seen.add(ch)


def test_variant_folding_is_idempotent():
    """代表字を畳んでも動かない(= 代表字が他の組の異体字になっていない)。"""
    for g in J.VARIANT_GROUPS:
        assert J.to_key(g[0]) == g[0]
        for v in g[1:]:
            assert J.to_key(v) == g[0]


def test_sai_groups_are_not_merged_on_purpose():
    """斉 と 斎 は別の字。畳まないことをテストで固定する(畳むなら同値表を直して、ここも直す)。"""
    assert J.to_key("斉") != J.to_key("斎")
    assert J.to_key("齊") == J.to_key("斉") and J.to_key("齋") == J.to_key("斎")


# ---- 対象外表記(畳まずに人へ返すと決めている形) ---------------------------------------------

@pytest.mark.parametrize("text", [
    "山田(旧姓 川口) 花子",
    "山田（佐藤）花子",
    "小林 桃子 旧姓 加藤",
    "田中 太郎 通称 タロー",
    "マリア クリスティーナ サトウ",
    "ﾏﾘｱ･ｸﾘｽﾃｨｰﾅ･ｻﾄｳ",
])
def test_scope_reason_out_of_scope(text):
    assert J.scope_reason(text) == "対象外表記"


@pytest.mark.parametrize("text", ["", "   ", "---", "・・"])
def test_scope_reason_empty(text):
    assert J.scope_reason(text) == "空の氏名"


@pytest.mark.parametrize("text", ["渡辺 太郎", "渡邊太郎", "ﾜﾀﾅﾍﾞ ﾊﾅｺ", "Yamada Taro"])
def test_scope_reason_ok(text):
    assert J.scope_reason(text) == ""


# ---- 照合と判断待ち ------------------------------------------------------------------------

def test_match_single_hit():
    idx = J.build_index(["渡邊太郎", "佐藤 花子"])
    d = J.match("渡辺 太郎", idx)
    assert (d.status, d.reason, d.candidates) == (J.OK, "", ("渡邊太郎",))
    assert d.key == "渡辺太郎"


def test_match_no_candidate():
    d = J.match("中村 直樹", J.build_index(["渡邊太郎"]))
    assert d.status == J.PENDING and d.reason == "相手なし" and d.candidates == ()
    assert "別表記・未登録・別人" in d.note


def test_match_multiple_candidates():
    d = J.match("佐藤 誠", J.build_index(["佐藤 誠", "佐藤誠"]))
    assert d.status == J.PENDING and d.reason == "相手が複数" and len(d.candidates) == 2


def test_match_self_duplicate_wins_over_single_hit():
    """自分側に同じキーが 2 行あるときは、相手が 1 件でも決めない。"""
    left = ["鈴木 優子", "鈴木優子"]
    d = J.match("鈴木 優子", J.build_index(["鈴木 優子"]), J.build_index(left))
    assert d.status == J.PENDING and d.reason == "自分側が重複"


def test_match_out_of_scope_is_checked_first():
    """相手が 1 件でも、旧姓併記は畳まずに人へ返す。"""
    d = J.match("山田(旧姓 川口) 花子", J.build_index(["山田 花子"]))
    assert d.status == J.PENDING and d.reason == "対象外表記"


def test_no_threshold_anywhere():
    """しきい値で自動的に寄せる経路を持たない(似ている順の候補も返さない)。"""
    src = (ROOT / "jp_name.py").read_text(encoding="utf-8")
    for word in ("difflib", "SequenceMatcher", "ratio", "threshold"):
        assert word not in src


def test_reasons_cover_every_emitted_reason():
    decisions = J.match_all(["渡辺 太郎", "中村 直樹", "佐藤 誠", "鈴木 優子", "鈴木優子",
                             "山田(旧姓 川口) 花子", ""],
                            ["渡邊太郎", "佐藤 誠", "佐藤誠", "鈴木 優子", "山田 花子"])
    for d in decisions:
        assert (d.reason == "" and d.status == J.OK) or d.reason in J.REASONS
        assert d.note == J.REASONS.get(d.reason, "")


# ---- fixture(合成した 2 つの名簿) ------------------------------------------------------------

def _read(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8", newline="")))


def test_fixture_meibo_pairs():
    a, b = _read(FX / "meibo_a.csv"), _read(FX / "meibo_b.csv")
    assert len(a) == 19 and len(b) == 15
    decisions = J.match_all([r["氏名"] for r in a], [r["氏名"] for r in b])
    for row, d in zip(a, decisions):
        got = J.OK if d.status == J.OK else d.reason
        assert got == row["期待"], (row["社員番号"], row["氏名"], got)


# ---- CLI ------------------------------------------------------------------------------------

def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "jp_name.py"), *args],
                          capture_output=True, text=True, encoding="utf-8")


def test_cli_key():
    r = run_cli("--key", "渡邊 太郎", "ﾜﾀﾅﾍﾞ ﾊﾅｺ")
    assert r.returncode == 0
    assert r.stdout.splitlines() == ["渡邊 太郎\t渡辺太郎", "ﾜﾀﾅﾍﾞ ﾊﾅｺ\tワタナベハナコ"]


def test_cli_match_exits_3_when_pending():
    r = run_cli(str(FX / "meibo_a.csv"), str(FX / "meibo_b.csv"))
    assert r.returncode == 3
    assert "渡辺 太郎\t照合\t渡邊太郎" in r.stdout
    assert "中村 直樹\t判断待ち\t相手なし" in r.stdout
    assert "照合 9 / 判断待ち 10" in r.stderr


def test_cli_match_exits_0_when_nothing_pending(tmp_path):
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    a.write_text("社員番号,氏名\n1,渡辺 太郎\n", encoding="utf-8")
    b.write_text("コード,氏名\nB1,渡邊太郎\n", encoding="utf-8")
    r = run_cli(str(a), str(b))
    assert r.returncode == 0 and "照合 1 / 判断待ち 0" in r.stderr


def test_cli_missing_column(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("コード,name\n1,佐藤\n", encoding="utf-8")
    r = run_cli(str(p), str(FX / "meibo_b.csv"))
    assert r.returncode != 0 and "氏名" in (r.stderr + r.stdout)


# ---- 素朴な突合との比較。合成 1,000 人、固定 seed -------------------------------------------

SEED = 20260923
N = 1000

SURNAMES = ("佐藤 鈴木 高橋 田中 伊藤 渡辺 山本 中村 小林 加藤 吉田 山田 佐々木 山口 松本 "
            "井上 木村 林 斎藤 清水 山崎 阿部 森 池田 橋本 石川 前田 藤田 後藤 小川 "
            "岡田 村上 長谷川 近藤 石井 坂本 遠藤 青木 藤井 西村 福田 太田 三浦 藤原 岡本 "
            "松田 中川 中野 原田 小野 田村 竹内 金子 和田 中山 石田 上田 森田 原 柴田").split()
GIVEN = ("太郎 花子 一郎 美咲 健 翔太 結衣 大輔 直樹 優子 誠 陽菜 拓也 隆 愛 "
         "浩二 恵子 慎一 由美 和也 真一 学 千尋 亮 舞 勇気 彩 聡 香織 剛 "
         "綾 徹 七海 修 桃子 豊 楓 弘 未来 広志").split()

_TO_VARIANT = {g[0]: g[1] for g in J.VARIANT_GROUPS}
STYLES = ("そのまま", "区切り無し", "全角空白", "異体字", "中黒")


def as_variant(s: str) -> str | None:
    for i, ch in enumerate(s):
        if ch in _TO_VARIANT:
            return s[:i] + _TO_VARIANT[ch] + s[i + 1:]
    return None


def render(sei: str, mei: str, style: str) -> str:
    if style == "区切り無し":
        return f"{sei}{mei}"
    if style == "全角空白":
        return f"{sei}　{mei}"
    if style == "中黒":
        return f"{sei}・{mei}"
    if style == "異体字":
        vs, vm = as_variant(sei), as_variant(mei)
        if vs:
            return f"{vs} {mei}"
        if vm:
            return f"{sei} {vm}"
        return f"{sei}{mei}"
    return f"{sei} {mei}"


def build_rosters(seed: int = SEED):
    """左 1,000 行 / 右 975 行の名簿を合成する。内訳は決定論的に作る。

    左: 970 通りの姓名。うち 30 通りは同姓同名の別人が 2 行ずつ(= 60 行)。うち 20 行は旧姓併記。
    右: 左の 1,000 人のうち 40 人が未登録(960 行)+ 右にだけいる同姓同名の別人 15 行 = 975 行。
        表記は 5 種類(そのまま / 区切り無し / 全角空白 / 異体字 / 中黒)に散らす。
    """
    rng = random.Random(seed)
    combos = [(s, g) for s in SURNAMES for g in GIVEN]
    rng.shuffle(combos)
    base = combos[:970]
    persons = [(i, s, g) for i, (s, g) in enumerate(base)]
    persons += [(970 + j, s, g) for j, (s, g) in enumerate(base[:30])]      # 同姓同名の別人 30 組
    dup_ids = {p[0] for p in persons[970:]} | {p[0] for p in persons[:30]}

    clean = [p for p in persons if p[0] not in dup_ids]                     # 920 人
    alias_ids = {p[0] for p in rng.sample(clean, 20)}                       # 旧姓併記にする 20 行
    rest = [p for p in clean if p[0] not in alias_ids]                      # 900 人
    missing_ids = {p[0] for p in rng.sample(rest, 40)}                      # 右に載せない 40 人
    extra_ids = {p[0] for p in rng.sample([p for p in rest if p[0] not in missing_ids], 15)}

    left = []
    for pid, s, g in persons:
        if pid in alias_ids:
            left.append((pid, f"{s}({rng.choice(SURNAMES)}) {g}"))
        else:
            left.append((pid, f"{s} {g}"))
    right = []
    for pid, s, g in persons:
        if pid in missing_ids:
            continue
        right.append((pid, render(s, g, rng.choice(STYLES))))
        if pid in extra_ids:                                                # 右にだけいる同姓同名の別人
            right.append((10000 + pid, render(s, g, rng.choice(STYLES))))
    return left, right


def _owner_map(right):
    owner: dict[str, list[int]] = {}
    for pid, n in right:
        owner.setdefault(n, []).append(pid)
    return owner


def test_measure_rosters_are_built_as_declared():
    left, right = build_rosters()
    assert len(left) == N and len(right) == 975
    assert sum(1 for _, n in left if "(" in n) == 20


def test_measure_exact_match_only():
    """文字列の完全一致だけで突合すると何件決まるか(表記が揺れた分は落ちる)。"""
    left, right = build_rosters()
    owner = _owner_map(right)
    hit = [(pid, owner[n]) for pid, n in left if len(owner.get(n, [])) == 1]
    wrong = sum(1 for pid, ids in hit if ids[0] != pid)
    print(f"\n[measure] exact string match: {len(hit)}/{N} matched, wrong {wrong}")
    # 記事に載せた値。固定 seed(20260923)で決定論的に再現する。変わったら記事の数字も変える。
    # wrong 13 = 同姓同名の相手が「そのまま」表記で右にいて、本人の表記は揺れていた行(完全一致でも別人に当たる)
    assert (len(hit), wrong) == (187, 13)


def test_measure_similarity_threshold_merges_different_people():
    """類似度 0.8 以上を『同じ人』として自動採用すると、別人が静かに混ざる。"""
    left, right = build_rosters()
    names = [n for _, n in right]
    owner = _owner_map(right)
    adopted = wrong = 0
    for pid, n in left:
        cand = difflib.get_close_matches(n, names, n=1, cutoff=0.8)
        if not cand:
            continue
        adopted += 1
        if pid not in owner[cand[0]]:
            wrong += 1
    print(f"[measure] similarity >= 0.8 auto-adopt: {adopted}/{N} adopted, different person {wrong}")
    # 記事に載せた値。固定 seed で決定論的に再現する。変わったら記事の数字も変える
    assert (adopted, wrong) == (793, 116)


def test_measure_this_tool():
    """この道具: キーで決まるものだけ照合し、残りは理由コード付きで人に返す。誤った結合は 0 件。"""
    left, right = build_rosters()
    decisions = J.match_all([n for _, n in left], [n for _, n in right])
    owner = _owner_map(right)
    counts: dict[str, int] = {}
    matched = wrong = 0
    for (pid, _), d in zip(left, decisions):
        if d.status == J.OK:
            matched += 1
            if pid not in owner[d.candidates[0]]:
                wrong += 1
        else:
            counts[d.reason] = counts.get(d.reason, 0) + 1
    print(f"[measure] this tool: matched {matched}/{N}, wrong {wrong}, pending {sum(counts.values())} {counts}")
    # 記事に載せた値。固定 seed で決定論的に再現する。変わったら記事の数字も変える
    assert (matched, wrong) == (865, 0)
    assert counts == {"自分側が重複": 60, "相手が複数": 15, "相手なし": 40, "対象外表記": 20}


KANA_SEI = ("ワタナベ タカハシ ヤマザキ サワダ トミタ シマダ ヨシダ サトウ スズキ タナカ "
            "イトウ ヤマモト ナカムラ コバヤシ カトウ ヤマダ ヤマグチ マツモト イノウエ キムラ "
            "サイトウ シミズ アベ モリ イケダ ハシモト イシカワ マエダ フジタ ゴトウ "
            "オガワ オカダ ムラカミ コンドウ イシイ サカモト エンドウ アオキ フジイ ニシムラ").split()
KANA_MEI = ("タロウ ハナコ イチロウ ミサキ ケン ショウタ ユイ ダイスケ ナオキ ユウコ "
            "マコト ヒナ タクヤ タカシ アイ コウジ ケイコ シンイチ ユミ カズヤ "
            "シンイチロウ マナブ チヒロ リョウ マイ ユウキ アヤ サトシ カオリ ツヨシ "
            "トオル ナナミ オサム モモコ ユタカ カエデ ヒロシ ミク サクラ ツバサ").split()


def to_hiragana(s: str) -> str:
    return s.translate({c: c - 0x60 for c in range(0x30A1, 0x30F7)})


_REV_HALF = {unicodedata.normalize("NFKC", chr(c)): chr(c) for c in range(0xFF61, 0xFFA0)}


def to_halfwidth_kana(s: str) -> str:
    out = []
    for ch in s:
        if ch in _REV_HALF:
            out.append(_REV_HALF[ch])
            continue
        d = unicodedata.normalize("NFD", ch)
        if len(d) == 2 and d[0] in _REV_HALF and d[1] in _REV_HALF:
            out.append(_REV_HALF[d[0]] + _REV_HALF[d[1]])
        else:
            out.append(ch)
    return "".join(out)


def test_measure_kana_notation_1000():
    """カナの名簿 1,000 件を 全角カナ / ひらがな / 半角カナ の 3 表記に散らすと、全部同じキーになる。"""
    rng = random.Random(SEED)
    combos = [(s, g) for s in KANA_SEI for g in KANA_MEI]
    rng.shuffle(combos)
    same = 0
    for s, g in combos[:N]:
        full = f"{s} {g}"
        keys = {J.to_key(full), J.to_key(to_hiragana(full)), J.to_key(to_halfwidth_kana(full))}
        same += len(keys) == 1
    print(f"[measure] kana 3 notations x 1000: same key {same}/{N}")
    assert same == N
