"""
候補の表から、サイトが読む players.csv / player_results.csv(リポジトリの一番上)を作る。

    python3 make_romaji.py        (ローマ字の下書き romaji_auto.csv。pykakasi が要る)
    python3 make_players_csv.py

- 確認用の列(入賞回数・最高順位・主な成績・確認メモ)は外す
- 「ローマ字」列:romaji_fix.tsv に直した綴りがあればそれ、無ければ機械の下書き
- 「ふりがな」列:エントリーリストの読み(kana_entries.csv)。同じ名前で読みが1つに決まる人だけ
- 読みが分かった人は、ローマ字をその読みから作る(romaji_fix.tsv で「はい」の綴りがある人はそちら)
- 「ローマ字確認」列:romaji_fix.tsv で「はい」の人だけ「はい」(英語版で注記を出さない。読みが分かった人も注記を出さない)
- PDF で「(氏名)」とかっこ付きで載っている人や、「髙/高」「﨑/崎」など字の違いだけの人は、1人にまとめる(すでに公開している選手IDを残す)
- 確認メモが「所属が複数」だけの人は「公開=はい」にする(移籍や「(株)」の書き方の違いがほとんどのため。運営者が決定)。
  「クラブ・教室だけ(年齢を確認)」「階級の幅が大きい」の人は「いいえ」のまま
- 新しい大会を足して「クラブ・教室だけ」「階級の幅が大きい」のメモが付いた人は、前の players.csv で公開でも「いいえ」に戻す
- すでに players.csv があるときは、運営者が変えた「公開」「未成年」「ローマ字」「ローマ字確認」をそのまま残す
- player_results.csv にある UWW の行(オリンピック・世界選手権・U23世界選手権。uww_results.py で足したもの)は、作り直しても残す
"""
import csv
import os
import re
import unicodedata

from make_romaji import romaji

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
COLS = ["選手ID", "氏名", "ふりがな", "別表記", "所属", "公開", "未成年", "ローマ字", "ローマ字確認"]
KEEP = ["公開", "未成年", "ローマ字", "ローマ字確認"]


def read(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def is_yes(v):
    return (v or "").strip() in ("はい", "yes", "1", "○", "〇")


def name_key(name):
    s = unicodedata.normalize("NFKC", name or "").translate(str.maketrans("髙﨑德", "高崎徳"))
    return re.sub(r"\s+", "", s)


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
    kanas = {}
    for r in read(os.path.join(HERE, "kana_entries.csv")):
        kanas.setdefault(name_key(r["氏名"]), set()).add(r["ふりがな"])

    # 同じ人が「(氏名)」のかっこ付きや「髙/高」「﨑/崎」などの字の違いで分かれているときは、1人にまとめる。
    # 残すのは、すでに公開している選手ID(ページのアドレスを変えない)→ かっこの無い名前 → 先に出てきたもの
    def rank(r):
        o = old.get(r["選手ID"], {})
        return (not is_yes(o.get("公開")), r["選手ID"] not in old, r["氏名"].startswith(("(", "(")))
    keep = {}
    for r in sorted(cands, key=rank):
        keep.setdefault(name_key(unparen(r["氏名"])), r["選手ID"])
    merged = {}
    out = []
    for r in cands:
        name, club = unparen(r["氏名"]), unparen(r["所属"])
        main_id = keep[name_key(name)]
        if main_id != r["選手ID"]:
            merged[r["選手ID"]] = main_id
            continue
        roma, ok = fix.get(r["選手ID"], (auto.get(r["選手ID"], ""), ""))
        kana = next(iter(kanas.get(name_key(name), ())), "") if len(kanas.get(name_key(name), ())) == 1 else ""
        foreign = re.match(r"^[ァ-ヶー]+ ", name) and r["選手ID"] in fix  # カタカナの外国名は、元の綴りに近い romaji_fix.tsv を使う
        if kana and not is_yes(ok) and not foreign:
            roma = romaji(kana)
        roma = " ".join(re.sub(r"[()()]", "", roma).split())
        memo = [m for m in (r.get("確認メモ") or "").split("・") if m]
        public = "はい" if memo and all(m.startswith("所属が複数") for m in memo) else r["公開"]
        risky = any(not m.startswith("所属が複数") for m in memo)  # 年齢の確認が必要・別の人かもしれない
        row = {"選手ID": r["選手ID"], "氏名": name, "ふりがな": kana or r["ふりがな"], "別表記": r["別表記"], "所属": club,
               "公開": public, "未成年": r["未成年"], "ローマ字": roma, "ローマ字確認": ok}
        if r["選手ID"] in old:
            for k in KEEP:
                if k == "公開" and (risky or (public != r["公開"] and old[r["選手ID"]].get(k) == r["公開"])):
                    continue  # 新しく「年齢の確認」などのメモが付いた人は、前に公開でも隠す  # 上の「所属が複数」の決定を、前の players.csv の値で打ち消さない
                if k in ("ローマ字", "ローマ字確認") and (r["選手ID"] in fix or kana) and not is_yes(old[r["選手ID"]].get("ローマ字確認")):
                    continue  # 直した綴り・読みから作った綴りを使う(運営者が確かめた綴りは残す)
                if old[r["選手ID"]].get(k):
                    row[k] = old[r["選手ID"]][k]
        out.append(row)
    with open(os.path.join(ROOT, "players.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(out)
    # オリンピック・世界選手権・U23世界選手権の成績(UWW の結果)は候補の表に無いので、前の player_results.csv から持ってくる
    olympics = [r for r in read(os.path.join(ROOT, "player_results.csv")) if r.get("出典URL", "").startswith("https://cdn.uww.org/")]
    seen = set()
    rows = []
    for r in results + olympics:
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
