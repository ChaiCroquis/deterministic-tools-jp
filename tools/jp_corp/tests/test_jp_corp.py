"""jp_corp のテスト。fixture は全て合成データ(fixtures/make_fixtures.py)、会社名も番号も架空。

後半の test_measure_* は、合成した 1,000 行の取引先台帳 2 つで
  (a) 文字列の完全一致だけの突合
  (b) 法人格を除去してから、外れたら類似度 0.8 以上を自動採用する突合(現場でよく見る形)
  (c) この道具(番号の経路 → 名前の経路 → 判断待ち)
を比べる(記事の数値はここから取る。固定 seed で決定論的に再現し、変わったら記事の数字も変える)。

法人番号は jp_corp.check_digit と同じ算式で作った合成値なので、このテストが確かめているのは
「実装が自分の算式と整合していること」までで、算式が公表値と合うことではない。
"""
from __future__ import annotations

import csv
import difflib
import random
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FX = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FX))
import jp_corp as J  # noqa: E402
import make_fixtures as MF  # noqa: E402


# ---- 正規化と分離(法人格を捨てない) ----------------------------------------------------------

@pytest.mark.parametrize("a, b", [
    ("山田商事株式会社", "株式会社山田商事"),          # 前株 / 後株
    ("山田商事株式会社", "㈱山田商事"),                # 合字
    ("山田商事株式会社", "山田商事(株)"),              # 丸括弧
    ("山田商事株式会社", "山田商事　株式会社"),        # 全角空白
    ("山田商事株式会社", "山田商事・株式会社"),        # 中黒
    ("ＡＢＣ物産株式会社", "ABC物産㈱"),               # 全角英字 + 合字
    ("ABC物産株式会社", "abc物産株式会社"),            # ローマ字の大文字小文字は畳む
    ("有限会社みなと", "みなと㈲"),
    ("医療法人社団みどり会", "みどり会医療法人社団"),
    ("NPO法人あおぞら", "特定非営利活動法人あおぞら"),
    ("東海運輸株式会社 大阪支店", "東海運輸(株)大阪支店"),
])
def test_same_key(a, b):
    assert J.to_key(a) == J.to_key(b) != ""


@pytest.mark.parametrize("a, b", [
    ("山田商事株式会社", "山田商事有限会社"),          # 法人格が違えば別法人
    ("山田商事株式会社", "山田商事合同会社"),
    ("医療法人社団みどり会", "医療法人財団みどり会"),
    ("東海運輸株式会社", "東海運輸株式会社 大阪支店"),  # 本社行と支店行
    ("東海運輸株式会社 大阪支店", "東海運輸株式会社 東京支店"),
    ("山田商事株式会社", "山田商会株式会社"),
])
def test_different_key(a, b):
    assert J.to_key(a) != J.to_key(b)


@pytest.mark.parametrize("name, kind, position", [
    ("株式会社山田商事", "株式会社", "前"),
    ("山田商事株式会社", "株式会社", "後"),
    ("山田商事株式会社大阪支店", "株式会社", "中"),
    ("山田商事", "", "無"),
])
def test_position(name, kind, position):
    c = J.parse(name)
    assert (c.kind, c.position) == (kind, position)


def test_legal_form_is_separated_not_removed():
    """法人格は屋号から外れるが、キーには残る(捨てない)。"""
    c = J.parse("㈱山田商事")
    assert (c.kind, c.yago, c.branch) == ("株式会社", "山田商事", "")
    assert c.kind in c.key and c.yago in c.key


def test_longest_form_wins():
    """医療法人社団 が 医療法人 に食われない。"""
    assert J.parse("医療法人社団みどり会").kind == "医療法人社団"
    assert J.parse("医療法人みどり会").kind == "医療法人"
    assert J.parse("一般社団法人あおば").kind == "一般社団法人"


@pytest.mark.parametrize("name, branch", [
    ("東海運輸株式会社 大阪支店", "支店"),
    ("東海運輸株式会社 名古屋営業所", "営業所"),
    ("東海運輸株式会社 北陸支社", "支社"),
    ("東海運輸株式会社 仙台出張所", "出張所"),
    ("東海運輸株式会社", ""),
    ("株式会社支店", ""),        # 屋号が残らない形では印を立てない
])
def test_branch_mark(name, branch):
    assert J.parse(name).branch == branch


def test_branch_text_stays_in_yago():
    """支店名は屋号から切り離さない(区切りが無いと地名の切れ目が機械では決まらないため)。"""
    c = J.parse("東海運輸株式会社 大阪支店")
    assert c.yago == "東海運輸大阪支店" and c.branch == "支店"


def test_empty_key_when_only_legal_form():
    for name in ("株式会社", "㈱", "  ", "・・", "医療法人"):
        assert J.parse(name).key == ""


def test_non_str_is_type_error():
    with pytest.raises(TypeError):
        J.to_key(12345)  # type: ignore[arg-type]


def test_legal_forms_table_is_consistent():
    """表記の重複が無く、種類の名前自体もその種類として認める表記に入っている。"""
    seen: set[str] = set()
    for kind, aliases in J.LEGAL_FORMS:
        assert kind in aliases, kind
        for a in aliases:
            assert a not in seen, a
            seen.add(a)
    # 記事に載せた値。表を増やすときはここも直す
    assert len(J.LEGAL_FORMS) == 24
    assert len(J.BRANCH_SUFFIXES) == 6


def test_reason_codes_count():
    """記事に載せた理由コードの数。増やすときはここも直す。"""
    assert len(J.REASONS) == 7


# ---- 法人番号の検査数字 ----------------------------------------------------------------------

def test_check_digit_round_trip():
    """合成番号 1,000 件が自分の算式で必ず通る(算式と実装の整合)。"""
    for n in range(1000):
        assert J.number_reason(MF.synth_number(900000000000 + n)) == ""


def bump(num: str, pos: int) -> str:
    """1 桁だけ書き換える。9 のときは 0 でなく 8 にする(0 と 9 の取り違えは検査で見えないため)。"""
    d = int(num[pos])
    return num[:pos] + str(d - 1 if d == 9 else d + 1) + num[pos + 1:]


def test_check_digit_catches_single_digit_error():
    """1 桁だけ書き換えた番号が検査に落ちることを、合成番号 200 件で確かめる。"""
    caught = total = 0
    for n in range(100):
        num = MF.synth_number(900000000000 + n)
        for pos in (3, 9):
            total += 1
            caught += J.number_reason(bump(num, pos)) == "番号の検査に落ちる"
    assert (caught, total) == (200, 200)


def test_check_digit_cannot_see_zero_nine_swap():
    """限界: 1 桁を 0 と 9 で取り違えても、この算式では検査に通ってしまう。"""
    seen = 0
    for n in range(300):
        num = MF.synth_number(900000000000 + n)
        for pos in range(1, 13):
            if num[pos] in "09":
                swapped = num[:pos] + ("9" if num[pos] == "0" else "0") + num[pos + 1:]
                seen += 1
                assert J.number_reason(swapped) == "", (num, pos)
    assert seen > 0


@pytest.mark.parametrize("text, expected", [
    ("", "空"),
    ("   ", "空"),
    ("123", "番号の検査に落ちる"),
    ("12345678901234", "番号の検査に落ちる"),
])
def test_number_reason_edges(text, expected):
    assert J.number_reason(text) == expected


def test_number_separators_and_fullwidth_are_normalized():
    num = MF.synth_number(900000000123)
    spaced = f"{num[0]} {num[1:5]}-{num[5:]}"
    fullwidth = num.translate({c: c + 0xFEE0 for c in range(0x30, 0x3A)})
    assert J.number_reason(spaced) == "" and J.number_reason(fullwidth) == ""


def test_check_digit_rejects_bad_input():
    with pytest.raises(ValueError):
        J.check_digit("12345")


# ---- 突合と判断待ち ------------------------------------------------------------------------

def _idx(*names_numbers):
    return J.build_index([J.Row(n, num) for n, num in names_numbers])


def test_match_by_name():
    d = J.match(J.Row("山田商事株式会社"), _idx(("㈱山田商事", ""), ("鈴木工業株式会社", "")))
    assert (d.status, d.by, d.reason) == (J.OK, J.BY_NAME, "")


def test_match_by_number_wins_over_name():
    """番号が通れば名前が違っても照合する(名前の経路より先)。"""
    num = MF.synth_number(900000000007)
    d = J.match(J.Row("ヤマト機械株式会社", num), _idx(("大和機械株式会社", num)))
    assert (d.status, d.by) == (J.OK, J.BY_NUMBER)
    assert d.candidates[0].name == "大和機械株式会社"


def test_legal_form_difference_is_pending_not_merged():
    """A 株式会社 と A 有限会社 は畳まない。近い相手として理由コードで返す。"""
    d = J.match(J.Row("山田商事有限会社"), _idx(("山田商事株式会社", "")))
    assert d.status == J.PENDING and d.reason == "法人格が違う"
    assert d.candidates[0].name == "山田商事株式会社"


def test_match_no_candidate():
    d = J.match(J.Row("のぞみ電機株式会社"), _idx(("山田商事株式会社", "")))
    assert d.status == J.PENDING and d.reason == "相手なし" and d.candidates == ()
    assert "別表記・未登録・別法人" in d.note


def test_match_multiple_candidates():
    d = J.match(J.Row("さくら建設株式会社"), _idx(("さくら建設㈱", ""), ("さくら建設株式会社", "")))
    assert d.status == J.PENDING and d.reason == "相手が複数" and len(d.candidates) == 2


def test_match_self_duplicate_wins_over_single_hit():
    left = [J.Row("ひかり産業株式会社"), J.Row("ひかり産業(株)")]
    d = J.match(left[0], _idx(("ひかり産業株式会社", "")), J.build_index(left))
    assert d.status == J.PENDING and d.reason == "自分側が重複"


def test_broken_number_is_not_rescued_by_name():
    """番号が壊れている行は、名前で当たっても照合しない。"""
    d = J.match(J.Row("みやこ商会株式会社", "1234567890123"), _idx(("みやこ商会株式会社", "")))
    assert d.status == J.PENDING and d.reason == "番号の検査に落ちる"


def test_number_conflict_is_pending():
    a, b = MF.synth_number(900000000011), MF.synth_number(900000000012)
    d = J.match(J.Row("かえで工業株式会社", a), _idx(("かえで工業株式会社", b)))
    assert d.status == J.PENDING and d.reason == "番号が食い違う"


def test_same_number_on_both_sides_is_ok():
    num = MF.synth_number(900000000013)
    d = J.match(J.Row("かえで工業株式会社", num), _idx(("かえで工業株式会社", num)))
    assert (d.status, d.by) == (J.OK, J.BY_NUMBER)


def test_missing_number_falls_back_to_name():
    """番号が無い行は判断待ちにせず、名前の経路に回す。"""
    d = J.match(J.Row("かえで工業株式会社", ""), _idx(("かえで工業㈱", MF.synth_number(900000000014))))
    assert (d.status, d.by) == (J.OK, J.BY_NAME)


def test_duplicate_number_on_the_other_side_is_pending():
    num = MF.synth_number(900000000015)
    d = J.match(J.Row("かえで工業株式会社", num), _idx(("かえで工業株式会社", num), ("別会社株式会社", num)))
    assert d.status == J.PENDING and d.reason == "相手が複数"


def test_empty_company_name():
    d = J.match(J.Row("株式会社"), _idx(("山田商事株式会社", "")))
    assert d.status == J.PENDING and d.reason == "空の会社名"


def test_no_threshold_anywhere():
    """しきい値で自動的に寄せる経路を持たない(似ている順の候補も返さない)。"""
    src = (ROOT / "jp_corp.py").read_text(encoding="utf-8")
    for word in ("difflib", "SequenceMatcher", "ratio", "threshold", "Levenshtein"):
        assert word not in src


def test_reasons_cover_every_emitted_reason():
    left = [J.Row(n, num) for n, num, _e in [(r[1], r[2], r[3]) for r in MF.LEFT]]
    right = [J.Row(n, num) for _c, n, num in MF.RIGHT]
    for d in J.match_all(left, right):
        assert (d.reason == "" and d.status == J.OK) or d.reason in J.REASONS
        assert d.note == J.REASONS.get(d.reason, "")


# ---- fixture(合成した 2 つの台帳) ------------------------------------------------------------

def _read(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8", newline="")))


def test_fixture_pairs():
    a, b = _read(FX / "torihikisaki_a.csv"), _read(FX / "torihikisaki_b.csv")
    assert len(a) == 17 and len(b) == 14
    left = [J.Row(r["会社名"], r["法人番号"]) for r in a]
    right = [J.Row(r["会社名"], r["法人番号"]) for r in b]
    for row, d in zip(a, J.match_all(left, right)):
        got = d.by if d.status == J.OK else d.reason
        assert got == row["期待"], (row["取引先コード"], row["会社名"], got)


# ---- CLI ------------------------------------------------------------------------------------

def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "jp_corp.py"), *args],
                          capture_output=True, text=True, encoding="utf-8")


def test_cli_key():
    r = run_cli("--key", "㈱山田商事", "東海運輸株式会社 大阪支店")
    assert r.returncode == 0
    assert r.stdout.splitlines()[0] == "㈱山田商事\t株式会社\t山田商事\t\t株式会社|山田商事|"
    assert r.stdout.splitlines()[1].endswith("株式会社|東海運輸大阪支店|支店")


def test_cli_check():
    good = MF.synth_number(900000000021)
    r = run_cli("--check", good, "1234567890123")
    assert r.returncode == 3
    assert r.stdout.splitlines()[0] == f"{good}\tOK"
    assert "NG 番号の検査に落ちる" in r.stdout.splitlines()[1]


def test_cli_match_exits_3_when_pending():
    r = run_cli(str(FX / "torihikisaki_a.csv"), str(FX / "torihikisaki_b.csv"))
    assert r.returncode == 3
    assert "山田商事株式会社\t照合\t番号\t㈱山田商事" in r.stdout
    assert "山田商事有限会社\t判断待ち\t法人格が違う" in r.stdout
    assert "照合 9 / 判断待ち 8" in r.stderr


def test_cli_match_exits_0_when_nothing_pending(tmp_path):
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    a.write_text("取引先コード,会社名,法人番号\n1,山田商事株式会社,\n", encoding="utf-8")
    b.write_text("コード,会社名,法人番号\nB1,㈱山田商事,\n", encoding="utf-8")
    r = run_cli(str(a), str(b))
    assert r.returncode == 0 and "照合 1 / 判断待ち 0" in r.stderr


def test_cli_missing_column(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("コード,name\n1,山田商事\n", encoding="utf-8")
    r = run_cli(str(p), str(FX / "torihikisaki_b.csv"))
    assert r.returncode != 0 and "会社名" in (r.stderr + r.stdout)


# ---- 素朴な突合との比較。合成 1,000 行、固定 seed --------------------------------------------

SEED = 20260924
N = 1000

HEADS = (("山田", "ヤマダ"), ("鈴木", "スズキ"), ("高橋", "タカハシ"), ("田中", "タナカ"),
         ("伊藤", "イトウ"), ("渡辺", "ワタナベ"), ("中村", "ナカムラ"), ("小林", "コバヤシ"),
         ("加藤", "カトウ"), ("吉田", "ヨシダ"), ("東海", "トウカイ"), ("北陸", "ホクリク"),
         ("関西", "カンサイ"), ("九州", "キュウシュウ"), ("信州", "シンシュウ"), ("湘南", "ショウナン"),
         ("武蔵", "ムサシ"), ("近江", "オウミ"), ("越後", "エチゴ"), ("大和", "ヤマト"),
         ("朝日", "アサヒ"), ("青空", "アオゾラ"), ("若葉", "ワカバ"), ("桜井", "サクライ"),
         ("松本", "マツモト"), ("森本", "モリモト"), ("岩崎", "イワサキ"), ("川口", "カワグチ"),
         ("長谷", "ナガタニ"), ("三好", "ミヨシ"), ("平野", "ヒラノ"), ("福井", "フクイ"),
         ("秋山", "アキヤマ"), ("香川", "カガワ"), ("白石", "シライシ"), ("黒田", "クロダ"),
         ("緑川", "ミドリカワ"), ("星野", "ホシノ"), ("月島", "ツキシマ"), ("天野", "アマノ"))
TAILS = ("商事 産業 物産 工業 建設 運輸 電機 機械 製作所 精密 通商 興業 商会 工務店 設備 "
         "電設 塗装 環境 資材 販売 開発 農産 水産 食品 印刷 包装 物流 倉庫 製菓 製薬").split()
KINDS = ("株式会社", "株式会社", "株式会社", "株式会社", "有限会社", "合同会社",
         "一般社団法人", "医療法人", "社会福祉法人", "税理士法人")
PLACES = "大阪 東京 名古屋 福岡 札幌 仙台 広島 横浜 神戸 京都".split()
STYLES = ("そのまま", "合字", "括弧", "空白", "中黒")
LIGATURE = {"株式会社": "㈱", "有限会社": "㈲"}
PAREN = {"株式会社": "(株)", "有限会社": "(有)", "合同会社": "(同)"}


def render(yago: str, kind: str, style: str, front: bool) -> str:
    """法人格の表記を散らす。どの表記でも照合キーは変わらない。"""
    form = kind
    if style == "合字":
        form = LIGATURE.get(kind, kind)
    elif style == "括弧":
        form = PAREN.get(kind, kind)
    sep = "　" if style == "空白" else ("・" if style == "中黒" else "")
    return f"{form}{sep}{yago}" if front else f"{yago}{sep}{form}"


def synth(pid: int) -> str:
    return MF.synth_number(900000000000 + pid)


def build_rosters(seed: int = SEED):
    """左 1,000 行 / 右 970 行の取引先台帳を合成する。内訳は決定論的に作る。

    左 = 一意の法人 895 + 同じ屋号で法人格だけ違う 20 組(40 行)+ 同じキーの別法人 15 組(30 行)
         + 支店の行 30 + 屋号が残らない行 5。
    右 = 左から「右に載せない 40 行」と「屋号が残らない 5 行」を除き、表記を 5 種類に散らし、
         同じキーの別法人 15 行を足したもの。
    仕込み: 相手なし 40 / 相手が複数 15 / 法人格が違う 10 / 番号の検査に落ちる 10 /
            番号が食い違う 5 / 屋号をカナ表記に変える 50(番号でしか当たらない)。
    """
    rng = random.Random(seed)
    combos = [f"{h}{t}" for h, _k in HEADS for t in TAILS]
    kana = {f"{h}{t}": f"{k}{t}" for h, k in HEADS for t in TAILS}
    rng.shuffle(combos)

    plain_yago = combos[:895]
    pair_yago = combos[895:915]      # 法人格だけ違う 2 社が同じ屋号を使う
    dup_yago = combos[915:930]       # 同じ屋号・同じ法人格の別法人

    left: list[tuple[int, J.Row]] = []
    pid = 0
    plain: list[tuple[int, str, str]] = []
    for y in plain_yago:
        k = rng.choice(KINDS)
        plain.append((pid, y, k))
        left.append((pid, J.Row(render(y, k, "そのまま", rng.random() < 0.5))))
        pid += 1
    for y in pair_yago:              # 20 組 40 行。別法人なので畳んではいけない
        for k in ("株式会社", "有限会社"):
            left.append((pid, J.Row(render(y, k, "そのまま", True))))
            pid += 1
    for y in dup_yago:               # 15 組 30 行。同じキーなので機械では決まらない
        for _ in range(2):
            left.append((pid, J.Row(render(y, "株式会社", "そのまま", True))))
            pid += 1
    branch_src = plain[:30]          # 支店の行(本社の行とは別のキーになる)
    for i, (_p, y, k) in enumerate(branch_src):
        left.append((pid, J.Row(render(f"{y}{PLACES[i % len(PLACES)]}支店", k, "そのまま", True))))
        pid += 1
    for name in ("株式会社", "㈱", "有限会社", "---", "・・"):
        left.append((pid, J.Row(name)))
        pid += 1

    rest = plain[30:]                # 支店の親になっていない一意の法人から仕込みを取る
    missing = {p for p, _y, _k in rest[:40]}          # 右に載せない
    extra = {p for p, _y, _k in rest[40:55]}          # 右に同じキーの別法人を足す
    wrong_form = {p for p, _y, _k in rest[55:65]}     # 右の法人格を書き間違える
    broken = {p for p, _y, _k in rest[65:75]}         # 左の番号を壊す
    conflict = {p for p, _y, _k in rest[75:80]}       # 右に別の番号が入っている
    kana_only = {p for p, _y, _k in rest[80:130]}     # 右の屋号がカナ表記(名前では当たらない)
    numbered = {p for p, _y, _k in rest[130:380]} | kana_only | broken | conflict

    left_rows: list[tuple[int, J.Row]] = []
    for p, row in left:
        num = ""
        if p in broken:
            num = bump(synth(p), 12)
        elif p in numbered:
            num = synth(p)
        left_rows.append((p, J.Row(row.name, num)))

    yago_kind = {p: (y, k) for p, y, k in plain}
    right: list[tuple[int, J.Row]] = []
    for p, row in left:
        if p in missing or not J.parse(row.name).key:
            continue
        y, k = yago_kind.get(p, (None, None))
        style = rng.choice(STYLES)
        if y is None:                                  # 組・重複・支店の行はそのままの屋号で散らす
            c = J.parse(row.name)
            name = render(c.yago, c.kind, style, rng.random() < 0.5)
        elif p in kana_only:
            name = render(kana[y], k, style, rng.random() < 0.5)
        elif p in wrong_form:
            name = render(y, "有限会社" if k != "有限会社" else "株式会社", style, True)
        else:
            name = render(y, k, style, rng.random() < 0.5)
        num = synth(p) if (p in numbered and p not in broken) else ""
        if p in conflict:
            num = MF.synth_number(800000000000 + p)
        if p in broken:
            num = synth(p)
        right.append((p, J.Row(name, num)))
        if p in extra:                                 # 右にだけいる同じキーの別法人
            right.append((10000 + p, J.Row(name, "")))
    return left_rows, right


def _owner(right):
    owner: dict[str, list[int]] = {}
    for p, row in right:
        owner.setdefault(row.name, []).append(p)
    return owner


def test_measure_rosters_are_built_as_declared():
    """記事に書いた合成台帳の内訳を固定する(内訳が変われば記事の数字も変える)。"""
    left, right = build_rosters()
    assert len(left) == N and len(right) == 970
    assert sum(1 for _p, r in left if not J.parse(r.name).key) == 5
    assert sum(1 for _p, r in left if r.number) == 315
    assert sum(1 for _p, r in left if J.parse(r.name).branch) == 30
    keys: dict[str, int] = {}
    kinds_of: dict[str, set[str]] = {}
    for _p, r in left:
        c = J.parse(r.name)
        if c.key:
            keys[c.key] = keys.get(c.key, 0) + 1
            kinds_of.setdefault(c.plain_key, set()).add(c.kind)
    assert sum(1 for _p, r in left if keys.get(J.parse(r.name).key, 0) >= 2) == 30
    assert sum(1 for _p, r in left if len(kinds_of.get(J.parse(r.name).plain_key, ())) >= 2) == 40


def test_measure_exact_match_only():
    """文字列の完全一致だけで突合すると何件決まるか(表記が揺れた分は落ちる)。"""
    left, right = build_rosters()
    owner = _owner(right)
    hit = [(p, owner[r.name]) for p, r in left if len(owner.get(r.name, [])) == 1]
    wrong = sum(1 for p, ids in hit if ids[0] != p)
    print(f"\n[measure] exact string match: {len(hit)}/{N} matched, wrong {wrong}")
    # 記事に載せた値。固定 seed(20260924)で決定論的に再現する。変わったら記事の数字も変える
    assert (len(hit), wrong) == (178, 3)


def _strip_forms(name: str) -> str:
    """現場でよく見る前処理: 法人格を『除去』して残りだけを見る。"""
    return J._FORM_RE.sub("", J.normalize(name)).casefold()


def test_measure_strip_forms_and_similarity():
    """法人格を除去して寄せると、A 株式会社 と A 有限会社 が同じ文字列になり、別法人が混ざる。"""
    left, right = build_rosters()
    stripped = [(p, _strip_forms(r.name)) for p, r in right]
    bucket: dict[str, list[int]] = {}
    for p, s in stripped:
        bucket.setdefault(s, []).append(p)
    names = [s for _p, s in stripped]
    adopted = wrong = 0
    for p, r in left:
        s = _strip_forms(r.name)
        ids = bucket.get(s)
        if not ids:
            cand = difflib.get_close_matches(s, names, n=1, cutoff=0.8)
            if not cand:
                continue
            ids = bucket[cand[0]]
        adopted += 1
        if ids[0] != p:          # 先頭の 1 件を採用する(現場でよく見る実装)
            wrong += 1
    print(f"[measure] strip legal form + similarity >= 0.8: {adopted}/{N} adopted, different company {wrong}")
    # 記事に載せた値。固定 seed で決定論的に再現する。変わったら記事の数字も変える
    assert (adopted, wrong) == (907, 37)


def test_measure_this_tool():
    """この道具: 番号と照合キーで決まるものだけ照合し、残りは理由コード付きで人に返す。"""
    left, right = build_rosters()
    decisions = J.match_all([r for _p, r in left], [r for _p, r in right])
    owner: dict[str, list[int]] = {}
    for p, r in right:
        owner.setdefault(r.name, []).append(p)
    counts: dict[str, int] = {}
    by: dict[str, int] = {}
    matched = wrong = 0
    for (p, _r), d in zip(left, decisions):
        if d.status == J.OK:
            matched += 1
            by[d.by] = by.get(d.by, 0) + 1
            if p not in owner[d.candidates[0].name]:
                wrong += 1
        else:
            counts[d.reason] = counts.get(d.reason, 0) + 1
    print(f"[measure] this tool: matched {matched}/{N} {by}, wrong {wrong}, "
          f"pending {sum(counts.values())} {counts}")
    # 記事に載せた値。固定 seed で決定論的に再現する。変わったら記事の数字も変える
    assert (matched, wrong) == (885, 0)
    assert by == {"番号": 300, "名前": 585}
    assert counts == {"相手なし": 40, "相手が複数": 15, "法人格が違う": 10,
                      "番号の検査に落ちる": 10, "番号が食い違う": 5,
                      "自分側が重複": 30, "空の会社名": 5}


def test_measure_legal_form_pairs_are_never_merged():
    """同じ屋号で法人格だけ違う 20 組(40 行)は、1 行も取り違えない。"""
    left, right = build_rosters()
    decisions = J.match_all([r for _p, r in left], [r for _p, r in right])
    owner: dict[str, list[int]] = {}
    for p, r in right:
        owner.setdefault(r.name, []).append(p)
    kinds_of: dict[str, set[str]] = {}
    for _p, r in left:
        c = J.parse(r.name)
        if c.key:
            kinds_of.setdefault(c.plain_key, set()).add(c.kind)
    target = [(p, d) for (p, r), d in zip(left, decisions)
              if d.status == J.OK and len(kinds_of.get(J.parse(r.name).plain_key, ())) >= 2]
    wrong = sum(1 for p, d in target if p not in owner[d.candidates[0].name])
    print(f"[measure] legal-form pairs: {len(target)} matched, wrong {wrong}")
    assert wrong == 0
