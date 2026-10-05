"""
大会のエントリーリスト(PDF。jwf_index.json の entry_lists)から、選手名の読みがなを取り出して kana_entries.csv に書く。
英語版の選手名(ローマ字)は、ここで分かった読みから作る(漢字から機械で推測するより確か)。

    python3 fetch_pdfs.py   (エントリーリストも一緒に取ってくる)
    python3 kana_entries.py
"""
import csv
import hashlib
import json
import re
import subprocess
import unicodedata

ROW = re.compile(r"^\s*\d+\s+\S+\s+(\S+(?: \S+)?)\s{2,}([ァ-ヶー]+ [ァ-ヶー]+)\s{2,}(.*?)\s*$")


def entries(pdf):
    text = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True).stdout
    for line in text.splitlines():
        m = ROW.match(line)
        if m:
            yield (unicodedata.normalize("NFKC", m.group(1)).strip(), unicodedata.normalize("NFKC", m.group(2)).strip(),
                   unicodedata.normalize("NFKC", m.group(3)).strip())


def main():
    out = {}
    for x in json.load(open("jwf_index.json", encoding="utf-8")):
        for u in x.get("entry_lists", []):
            fn = "jwf/" + hashlib.md5(u.encode()).hexdigest()[:10] + ".pdf"
            for name, kana, club in entries(fn):
                out.setdefault((name, kana), (club, u))
    with open("kana_entries.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["氏名", "ふりがな", "所属", "出典URL"])
        for (name, kana), (club, u) in sorted(out.items()):
            w.writerow([name, kana, club, u])
    print(f"kana_entries.csv {len(out)}人")


if __name__ == "__main__":
    main()
