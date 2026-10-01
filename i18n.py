"""
日本語版と英語版(/en/)を作り分けるための小さな道具。

  L("日本語", "English")   … いま作っているページの言語に合わせて片方を返す
  U("/events/")            … 英語版のときは "/en/events/" にする(サイト内リンク用)
  N("天皇杯全日本選手権")  … 大会名・会場名などを en_names.csv の英語名に置き換える(日本語版ではそのまま)

en_names.csv(Excelで編集できる)
  種類, 日本語, 英語, 確認済み
  - 英語名が空の行や、表に無い名前は、英語版でも日本語のまま表示し、build_report.json の en_missing に出す
  - 「確認済み」は運営者が確認した印。表示には影響しない(未確認でも英語名の案を表示する)
"""
import csv
import os
import re

NAMES_CSV = "en_names.csv"
LANG = "ja"
_names = {}
missing = set()

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def set_lang(lang):
    global LANG
    LANG = lang


def en():
    return LANG == "en"


def L(ja, en_text):
    return en_text if LANG == "en" else ja


def U(path):
    """サイト内のページへのリンク。英語版では /en/ の下を指す"""
    if LANG == "en" and path.startswith("/") and not path.startswith("/en/") and not path.startswith("/assets/"):
        return "/en" + path
    return path


def load_names(root):
    _names.clear()
    path = os.path.join(root, NAMES_CSV)
    if not os.path.exists(path):
        return
    for enc in ("utf-8-sig", "cp932"):
        try:
            with open(path, encoding=enc, newline="") as f:
                for row in csv.DictReader(f):
                    ja, eng = (row.get("日本語") or "").strip(), (row.get("英語") or "").strip()
                    if ja and eng:
                        _names[ja] = eng
            return
        except UnicodeDecodeError:
            _names.clear()


def N(ja):
    """大会名・会場名などの固有名を英語にする。英語名が無ければ日本語のまま(足りない名前は記録する)"""
    if LANG != "en" or not ja:
        return ja
    if ja in _names:
        return _names[ja]
    if re.search(r"[぀-ヿ一-鿿]", ja):
        fy = fy_label(ja)
        if fy != ja:
            return fy
        missing.add(ja)
    return ja


def names_table():
    return dict(_names)


def fy_label(s):
    """令和6年度 → FY2024、平成30年度 → FY2018"""
    m = re.fullmatch(r"(令和|平成)(元|\d+)年度", s or "")
    if not m:
        return s
    n = 1 if m.group(2) == "元" else int(m.group(2))
    return f"FY{(2018 if m.group(1) == '令和' else 1988) + n}"


def en_date(iso):
    y, m, d = iso[:10].split("-")
    return f"{MONTHS[int(m) - 1]} {int(d)}, {int(y)}"


def en_range(a, b):
    pa, pb = a[:10].split("-"), b[:10].split("-")
    if pa[0] != pb[0]:
        return f"{en_date(a)} – {en_date(b)}"
    if pa[1] != pb[1]:
        return f"{MONTHS[int(pa[1]) - 1]} {int(pa[2])} – {MONTHS[int(pb[1]) - 1]} {int(pb[2])}, {int(pa[0])}"
    return f"{MONTHS[int(pa[1]) - 1]} {int(pa[2])}–{int(pb[2])}, {int(pa[0])}"


def plural(n, word, words=None):
    return f"{n} {word if n == 1 else (words or word + 's')}"
