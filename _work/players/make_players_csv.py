"""
候補の表から、サイトが読む players.csv / player_results.csv(リポジトリの一番上)を作る。

    python3 make_romaji.py        (ローマ字の下書き romaji_auto.csv。pykakasi が要る)
    python3 make_players_csv.py

- 確認用の列(入賞回数・最高順位・主な成績・確認メモ)は外す
- 「ローマ字」列:romaji_fix.tsv に直した綴りがあればそれ、無ければ機械の下書き
- 「ローマ字確認」列:romaji_fix.tsv で「はい」の人だけ「はい」(英語版で注記を出さない)
- PDF で「(氏名)」とかっこ付きで載っている人は、かっこを外し、同じ名前・同じ所属の人がいればその人にまとめる
- すでに players.csv があるときは、運営者が変えた「公開」「未成年」「ローマ字」「ローマ字確認」をそのまま残す
"""
import csv
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
COLS = ["選手ID", "氏名", "ふりがな", "別表記", "所属", "公開", "未成年", "ローマ字", "ローマ字確認"]
KEEP = ["公開", "未成年", "ローマ字", "ローマ字確認"]


def read(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def unparen(s):
    return re.sub(r"^[((](.*)[))]$", r"\1", (s or "").strip())


def main():
    cands = read(os.path.join(HERE, "players_candidates.csv"))
    results = read(os.path.join(HERE, "player_results_candidates.csv"))
    auto = {r["選手ID"]: r["ローマ字"] for r in read(os.path.join(HERE, "romaji_auto.csv"))}
    fix = {}
    with open(os.path.join(HERE, "romaji_fix.tsv"), encoding="utf-8") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                bits = line.rstrip("\n").split("\t")
                fix[bits[0]] = (bits[1], bits[2] if len(bits) > 2 else "")
    old = {r["選手ID"]: r for r in read(os.path.join(ROOT, "players.csv"))}

    plain = {(r["氏名"], r["所属"]): r["選手ID"] for r in cands if not r["氏名"].startswith(("(", "("))}
    merged = {}
    out = []
    for r in cands:
        name, club = unparen(r["氏名"]), unparen(r["所属"])
        if name != r["氏名"] and (name, club) in plain:
            merged[r["選手ID"]] = plain[(name, club)]
            continue
        roma, ok = fix.get(r["選手ID"], (auto.get(r["選手ID"], ""), ""))
        roma = " ".join(re.sub(r"[()()]", "", roma).split())
        row = {"選手ID": r["選手ID"], "氏名": name, "ふりがな": r["ふりがな"], "別表記": r["別表記"], "所属": club,
               "公開": r["公開"], "未成年": r["未成年"], "ローマ字": roma, "ローマ字確認": ok}
        if r["選手ID"] in old:
            for k in KEEP:
                if old[r["選手ID"]].get(k):
                    row[k] = old[r["選手ID"]][k]
        out.append(row)
    with open(os.path.join(ROOT, "players.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(out)
    seen = set()
    rows = []
    for r in results:
        r = dict(r, 選手ID=merged.get(r["選手ID"], r["選手ID"]))
        key = tuple(r.values())
        if key not in seen:
            seen.add(key)
            rows.append(r)
    with open(os.path.join(ROOT, "player_results.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"players.csv {len(out)}人(かっこ付きの名前を {len(merged)}人まとめた)/ player_results.csv {len(rows)}件")


if __name__ == "__main__":
    main()
