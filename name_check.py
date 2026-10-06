"""
英語版の機械翻訳(動画タイトルなど)で、選手の名前の読み間違いを直す・見つける。

DeepL は日本人の名前の読みをよく間違える(例:高谷 惣亮 → Sosuke Takaya、藤波 朱理 → Shuri Fujinami)。
translate_en.py が新しく訳した文に fix_text() をかけ、players.csv の読みが確かな選手の名前を正しい英語名にする。
直せなかったものは suspects() で数え、build_report.json の translation.name_suspects に出す。

- 対象は players.csv で「ふりがな」があるか「ローマ字確認」が「はい」の選手だけ(読みが確かな人)
- タイトルの中では「Takahiro Tsuruda」のように名・姓の順、姓は先頭だけ大文字
- 次のときは直さない(取り違えを防ぐ):同じ名字の別の人がタイトルにいる/訳の中で名前の形が1つに決まらない
- 外部のライブラリは使わない(毎日の自動更新で動かすため)
"""
import csv
import os
import re
import unicodedata

PLAYERS_CSV = "players.csv"
W = r"[A-Z][a-zA-Zōūéā'’-]+"
NOT_NAMES = {"Cup", "Class", "University", "Championships", "Championship", "Interview", "High", "School", "Final", "Japan"}


def _n(s):
    """漢字の名前を比べるための形(空白を除き、髙・﨑・德をふつうの字に)"""
    s = unicodedata.normalize("NFKC", s or "").translate(str.maketrans("髙﨑德", "高崎徳"))
    return re.sub(r"\s+", "", s)


def _fold(s):
    """ローマ字を比べるための形(小文字、長音記号を外し、oh/ou・同じ母音の重なりをそろえる)"""
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"([aeiou])\1", r"\1", s.replace("oh", "o").replace("ou", "o"))


def load_names(root="."):
    """読みが確かな選手の一覧。[(氏名, 姓の漢字, 名, 姓)] を、氏名の長い順に"""
    path = os.path.join(root, PLAYERS_CSV)
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for p in csv.DictReader(f):
            roma = (p.get("ローマ字") or "").split()
            name = (p.get("氏名") or "").strip()
            sure = (p.get("ふりがな") or "").strip() or (p.get("ローマ字確認") or "").strip() == "はい"
            if len(roma) < 2 or " " not in name or not sure or len(_n(name)) < 3:
                continue
            fam = roma[-1].capitalize() if roma[-1].isupper() else roma[-1]
            out.append((_n(name), _n(name.split()[0]), roma[0], fam))
    return sorted(out, key=lambda x: -len(x[0]))


def _candidate(en, giv, fam):
    """訳の中から、この人の名前と思われる2語(名が違う/姓が違う/姓・名の順)を探す"""
    found = set()
    for m in re.finditer(rf"(?=\b({W}) ({W})\b)", en):
        a, b = m.group(1), m.group(2)
        if a in NOT_NAMES or b in NOT_NAMES:
            continue
        if _fold(b) == _fold(fam) and _fold(a) != _fold(giv):
            found.add(f"{a} {b}")
        elif _fold(a) == _fold(giv) and _fold(b) != _fold(fam):
            found.add(f"{a} {b}")
        elif _fold(a) == _fold(fam) and _fold(b) == _fold(giv):
            found.add(f"{a} {b}")
    return found.pop() if len(found) == 1 else None


def fix_text(ja, en, names):
    """訳 en の中の、選手の名前の読み間違いを直す。(直した訳, [(直す前, 直した後)]) を返す"""
    J = _n(ja)
    here = [x for x in names if x[0] in J]
    fixes = []
    for full, fam_k, giv, fam in here:
        right = f"{giv} {fam}"
        if _fold(right) in _fold(en):
            continue
        k = J.count(full)
        # 同じ名字の別の人がいるときは、取り違えるおそれがあるので直さない
        if J.count(fam_k) != k or any(o[0] != full and o[1] == fam_k for o in here):
            continue
        cand = _candidate(en, giv, fam)
        if cand and en.count(cand) == k:
            en = en.replace(cand, right)
            fixes.append((cand, right))
    return en, fixes


def suspects(texts, names):
    """選手の氏名が日本語にあるのに、訳に正しい英語名が無いもの(誤訳の疑い)。[(日本語, 訳, 正しい英語名)]"""
    out = []
    for ja, en in texts.items():
        J = _n(ja)
        for full, _, giv, fam in names:
            if full in J and _fold(f"{giv} {fam}") not in _fold(en):
                out.append((ja, en, f"{giv} {fam}"))
    return out
