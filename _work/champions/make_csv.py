"""parse_pdf.py の出力(JSON lines)から champions.csv を作る
使い方(リポジトリの一番上で):
  for f in <PDFのフォルダ>/*.pdf; do python3 _work/champions/parse_pdf.py $f $(basename $f .pdf); done > all.jsonl
  python3 _work/champions/make_csv.py all.jsonl
"""
import csv
import json
import re
import sys
import unicodedata

BASE = "https://wrestling-spirits.jp/www/wp-content/data/80/ichiran_domestic/"
# PDF のファイル名 → (大会ID, スタイル)。東日本学生は春・秋で大会IDを分ける
FILES = {
    "AllJapan-FF": ("tenno-cup", "フリースタイル"), "AllJapan-GR": ("tenno-cup", "グレコローマン"), "AllJapan-Fe": ("tenno-cup", "女子"),
    "Meiji_FF": ("meiji-cup", "フリースタイル"), "Meiji_GR": ("meiji-cup", "グレコローマン"), "Meiji_Fe": ("meiji-cup", "女子"),
    "intercollege_FF": ("intercollegiate", "フリースタイル"), "intercollege_GR": ("intercollegiate", "グレコローマン"),
    "intercollege_Fe": ("intercollegiate", "女子"),
    "Daigaku_FF": ("university-championship", "フリースタイル"), "Daigaku_GR": ("university-greco", "グレコローマン"),
    "syakaijin_FF": ("shakaijin", "フリースタイル"), "syakaijin_GR": ("shakaijin", "グレコローマン"), "syakaijin_Fe": ("shakaijin", "女子"),
    "east_college_FS": ("east", "フリースタイル"), "east_college_GR": ("east", "グレコローマン"), "east_female": ("east", "女子"),
}
STYLE_ORDER = ["フリースタイル", "グレコローマン", "女子"]


def series(r):
    sid, style = FILES[r["file"]]
    if sid != "east":
        return sid, style
    if r["season"] == "秋":
        return "east-autumn", style
    if r["season"] == "春":
        return "east-spring", style
    # 春・秋の印がない年: 男子の2016年は12月、女子の2020年は11月(秋)。ほかの女子は6〜7月(春)
    if r["file"] != "east_female" or r["year"] == 2020:
        return "east-autumn", style
    return "east-spring", style


def squeeze(s):
    """全角を半角にそろえ、字送りのための空白を消す(英字どうしの間の空白は残す)"""
    s = unicodedata.normalize("NFKC", s).strip()
    s = re.sub(r"\s+", " ", s)
    return re.sub(r"(?<![A-Za-z]) | (?![A-Za-z])", "", s)


def name_of(s):
    s = unicodedata.normalize("NFKC", s).strip()
    return re.sub(r"\s+", " ", s)


def weight_of(w):
    w = unicodedata.normalize("NFKC", w)
    return re.sub(r"kg(以上)?級$", r"kg\1", w)


def main(path):
    out = []
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        sid, style = series(r)
        club = squeeze(r["club"]).strip("()【】「」")
        out.append({"大会ID": sid, "スタイル": style, "開催年": r["year"], "階級": weight_of(r["weight"]),
                    "氏名": name_of(r["name"]), "所属": club, "出典URL": BASE + r["file"] + ".pdf"})
    m = re.compile(r"(\d+)")
    out.sort(key=lambda o: (o["大会ID"], STYLE_ORDER.index(o["スタイル"]), -o["開催年"],
                            int(m.match(o["階級"]).group(1)) if m.match(o["階級"]) else 0, o["階級"], o["氏名"]))
    with open("champions.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(len(out), "rows")


if __name__ == "__main__":
    main(sys.argv[1])
