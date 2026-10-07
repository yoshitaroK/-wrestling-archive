"""
選手名のローマ字(英語版で使う)の下書きを、漢字の名前から機械で作る。

    pip install pykakasi
    python3 make_romaji.py   → romaji_auto.csv(選手ID, 氏名, ローマ字)

- 書き方は「名 姓(姓は大文字)」(例:Kenichiro FUMITA)。世界レスリング連合の大会結果と同じ
- 伸ばす音は ou・uu・oo を o・u にする(例:Yuki、Ryota)
- ただし漢字に「内(うち)」があって読みに「ノウチ」があるときは、その「ウ」は伸ばす音ではないので残す
  (例:山内 ヤマノウチ → Yamanouchi。Yamanochi にしない)
- 漢字の読みは機械では正しく決まらないので、ここで作るのはあくまで下書き。
  players.csv の「ローマ字確認」が「はい」の行は、人が確かめた綴りなので上書きしない
- 毎日の自動更新では使わない(サイトの更新に pykakasi は要らない)
"""
import csv
import os
import re

import pykakasi

HERE = os.path.dirname(os.path.abspath(__file__))
_k = pykakasi.kakasi()


def part(s, kanji=""):
    s = s.translate(str.maketrans("德髙﨑", "徳高崎"))
    s = re.sub(r"(.)々", r"\1\1", s)
    lat = re.findall(r"[A-Za-z]+", s)
    jp = re.sub(r"[A-Za-z]+", "", s)
    r = "".join(x["hepburn"] for x in _k.convert(jp)) if jp else ""
    r = r.replace("'", "")
    if "内" in kanji:
        r = r.replace("nouchi", "no\0uchi")  # 「ノ・ウチ」(山之内・竹之内など)の ウ を伸ばす音として消さないよう、いったん印をつける
    r = re.sub(r"ou(?!e$)", "o", r)
    r = re.sub(r"uu", "u", r)
    r = re.sub(r"^oo", "o", r)
    r = r.replace("\0", "")
    out = [w for w in [r] + lat if w]
    return " ".join(w[:1].upper() + w[1:].lower() for w in out)


def romaji(name, kanji=""):
    """name は漢字かカタカナの名前。カタカナのときは kanji に漢字の名前を渡すと、読みの切れ目の手がかりにする"""
    bits, kbits = name.split(), (kanji or name).split()
    if len(bits) < 2:
        return part(name, kanji or name)
    family, given = bits[0], " ".join(bits[1:])
    kf, kg = (kbits[0], " ".join(kbits[1:])) if len(kbits) >= 2 else (kanji, kanji)
    return f"{part(given, kg)} {part(family, kf).upper()}"


def main():
    src = os.path.join(HERE, "players_candidates.csv")
    with open(src, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    with open(os.path.join(HERE, "romaji_auto.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["選手ID", "氏名", "ローマ字"])
        for r in rows:
            w.writerow([r["選手ID"], r["氏名"], romaji(r["氏名"])])


if __name__ == "__main__":
    main()
