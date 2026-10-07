"""
大会のエントリーリスト(PDF。jwf_index.json の entry_lists)から、選手名の読みがなを取り出して kana_entries.csv に書く。
英語版の選手名(ローマ字)は、ここで分かった読みから作る(漢字から機械で推測するより確か)。

    python3 fetch_pdfs.py   (エントリーリストも一緒に取ってくる)
    python3 kana_entries.py

entry_lists_known_only のリスト(U23 など、年の若い選手が混ざるかもしれない区分)からは、
players.csv で「公開=はい」「未成年=いいえ」の選手と同じ名前の人の読みだけを取る(ほかの人の名前は残さない)。
"""
import csv
import hashlib
import json
import os
import re
import subprocess
import unicodedata

ROW = re.compile(r"^\s*\d+\s+\S+\s+(\S+(?: \S+)?)\s{2,}([ァ-ヶー]+ [ァ-ヶー]+)\s{2,}(.*?)\s*$")
# U23 のリストの書き方(番号が無い・「U23の部」が付くなど)。氏名は「姓 名」の形のものだけ取る
ROW_U23 = re.compile(r"^\s*(?:\d+\s+)?(?:\S+の部\s+)?(\S+ \S+)\s+([ァ-ヶー]+ [ァ-ヶー]+)\s+(\S+)")
# PDF によっては「⻑」「⻄」などの部首の字が使われているので、ふつうの字にする
RADICALS = str.maketrans("⻑⻄⻘⻝⻆⻨⻤⻭⻩⻯⻲", "長西青食角麦鬼歯黄竜亀")


def entries(pdf, u23=False):
    text = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True).stdout
    for line in text.splitlines():
        m = (ROW_U23 if u23 else ROW).match(line)
        if m:
            yield tuple(unicodedata.normalize("NFKC", g).translate(RADICALS).strip() for g in m.groups())


def name_key(name):
    # make_players_csv.py の name_key と同じ(字の違い・空白を無視して比べる)
    s = unicodedata.normalize("NFKC", name or "").translate(str.maketrans("髙﨑德", "高崎徳"))
    return re.sub(r"\s+", "", s)


def adult_public_names():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "players.csv")
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {name_key(r["氏名"]) for r in csv.DictReader(f) if r.get("公開") == "はい" and r.get("未成年") == "いいえ"}


def main():
    out = {}
    known = adult_public_names()
    for x in json.load(open("jwf_index.json", encoding="utf-8")):
        lists = [(u, False) for u in x.get("entry_lists", [])] + [(u, True) for u in x.get("entry_lists_known_only", [])]
        for u, known_only in lists:
            fn = "jwf/" + hashlib.md5(u.encode()).hexdigest()[:10] + ".pdf"
            for name, kana, club in entries(fn, u23=known_only):
                if known_only and name_key(name) not in known:
                    continue
                if any(len(t) >= 4 and t[:len(t) // 2] == t[len(t) // 2:] for t in kana.split()):
                    continue  # 「ヨシノブヨシノブ」のように読みが二重に書かれている誤記は使わない
                out.setdefault((name, kana), (club, u))
    with open("kana_entries.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["氏名", "ふりがな", "所属", "出典URL"])
        for (name, kana), (club, u) in sorted(out.items()):
            w.writerow([name, kana, club, u])
    print(f"kana_entries.csv {len(out)}人")


if __name__ == "__main__":
    main()
