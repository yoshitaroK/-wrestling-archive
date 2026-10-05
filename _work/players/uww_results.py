"""
オリンピック・世界選手権・U23世界選手権の成績を、世界レスリング連合(UWW)の結果の冊子(PDF)から取り、
リポジトリの一番上の player_results.csv に足す。

    python3 uww_results.py

- PDF は uww.org の大会ページの「Results」のもの。uww/ に取ってくる
  (作業環境のネットワーク設定に uww.org と cdn.uww.org の許可が必要。pdftotext を使う)
- 各階級の「Ranking」の表から JPN の選手を取り、players.csv の「ローマ字」と同じ名前の人に結びつける
  (「TAKATANI Sohsuke」のように姓が先の冊子もある。「Sohsuke」の oh は o として比べる)
- players.csv にいない人・同じローマ字の人が2人以上いる人は足さずに表示する
- player_results.csv にある UWW の行(出典URL が https://cdn.uww.org/ のもの)はいったん消してから足すので、
  何度動かしても同じ結果になる
- make_players_csv.py で作り直しても、player_results.csv の UWW の行は残る
- 新しい大会を足すときは、下の GAMES に1行足す(大会名は players.py の OLYMPICS・WORLDS にあるもの)
"""
import csv
import os
import re
import subprocess
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
UWW = "https://cdn.uww.org/"

# 大会名・開催年・開催回ID(サイトの開催回ページ。無ければ空)・結果の冊子
GAMES = [
    ("オリンピック(パリ)", "2024", "x-olympics-2024-05-23",
     UWW + "2026-07/2024-olympic-games_final-book_20260722.pdf"),
    ("オリンピック(東京 2020)", "2021", "",
     UWW + "2026-01/results_tokyo_arena_upd_doping_case.pdf"),  # ドーピング違反の処分を反映した更新版
    # 世界選手権。2020年は中止、2024年(非五輪階級・ティラナ)は uww.org に結果が見つからない
    ("世界選手権", "2021", "x-world-championships-2021-10-05", UWW + "2026-01/results_10_oslo_upd_doping_case.pdf"),
    ("世界選手権", "2022", "x-world-championships-2022-09-12", UWW + "2026-01/results_09_belgrade_upd_doping_case_2.pdf"),
    ("世界選手権", "2023", "x-world-championships-2023-09-18", UWW + "2024-04/2023_seniors-world-chsips_final-book-20240424.pdf"),
    ("世界選手権", "2025", "", UWW + "2026-05/final-book-2025_senior_world_championships_20260528.pdf"),
    # U23世界選手権。2021年は日本が出ていない
    ("U23世界選手権", "2022", "", UWW + "2025-01/2022-u23-worlds_final-book_20250107.pdf"),
    ("U23世界選手権", "2023", "", UWW + "2023-10/2023-u23-world-championships_final-book.pdf"),
    ("U23世界選手権", "2024", "", UWW + "2026-06/results_10_tirana_u23_20260608.pdf"),
    ("U23世界選手権", "2025", "", UWW + "2025-10/final-book-1f0a015d-285b-6194-be9d-7d4675d42071.pdf"),
]
STYLE = {"Freestyle": "フリースタイル", "Greco-Roman": "グレコローマン", "Women's wrestling": "女子"}
# 冊子によって、階級の見出しの後ろに日付「(8 Aug - 9 Aug 2024)」があるものと無いものがある
HEAD = re.compile(r"^\s*(Freestyle|Greco-Roman|Women's wrestling)\s*-\s*(?:Seniors|U23)\s*-\s*(\d+)\s*kg\s*(?:\(|$)")
ROW = re.compile(r"^\s*(\d+)\s+JPN\s+(.+?)\s{2,}\d")


def text(url):
    os.makedirs(os.path.join(HERE, "uww"), exist_ok=True)
    pdf = os.path.join(HERE, "uww", url.rsplit("/", 1)[1])
    if not os.path.exists(pdf):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r, open(pdf, "wb") as f:
            f.write(r.read())
    return subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True, check=True).stdout


def rankings(txt):
    """各階級の「Ranking」の表から (スタイル, 階級, 順位, 名前) を取る"""
    out, cur, inrank = [], None, False
    for line in txt.split("\n"):  # splitlines() だとページの区切り(\f)が消える
        if "\f" in line:
            inrank = False  # ページが変わったら表はおしまい
        m = HEAD.search(line)
        if m:
            cur, inrank = (STYLE[m.group(1)], m.group(2) + "kg"), False
            continue
        if cur and re.match(r"^\s*Rank\s+Team\s+Wrestler", line):
            inrank = True
            continue
        r = ROW.match(line) if inrank else None
        if r:
            out.append((*cur, r.group(1), r.group(2)))
    return out


def key(name):
    """「Rei HIGUCHI」「TAKATANI Sohsuke」→ ('HIGUCHI', 'REI') の形にそろえる"""
    parts = name.split()
    fam = [w for w in parts if w.isupper() and len(w) > 1]
    if len(fam) == len(parts) > 1:
        fam = parts[-1:]  # 「HARUTO YABE」のように全部大文字のときは、最後を姓とする
    giv = [w for w in parts if w not in fam]
    k = (" ".join(fam).upper(), " ".join(giv).upper())
    return tuple(re.sub(r"OH(?=[^AEIOU]|$)", "O", s) for s in k)


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    players = read(os.path.join(ROOT, "players.csv"))
    by_key = {}
    for p in players:
        if p["ローマ字"]:
            by_key.setdefault(key(p["ローマ字"]), []).append(p)
    path = os.path.join(ROOT, "player_results.csv")
    rows = [r for r in read(path) if not r["出典URL"].startswith(UWW)]
    cols = list(rows[0].keys())
    added = []
    for name, year, eid, url in GAMES:
        found = rankings(text(url))
        print(f"{year} {name}: 日本の選手 {len(found)}人")
        for style, weight, rk, wname in found:
            hits = by_key.get(key(wname), [])
            if len(hits) != 1:
                print(f"  足さない: {wname} {style} {weight} {rk}位({'players.csv にいない' if not hits else '同じローマ字が' + str(len(hits)) + '人'})")
                continue
            p = hits[0]
            print(f"  {p['氏名']}({wname}){style} {weight} {rk}位{'' if p['公開'] == 'はい' else '  ※公開=いいえ'}")
            added.append({"選手ID": p["選手ID"], "開催回ID": eid, "大会名": name, "開催年": year,
                          "スタイル": style, "階級": weight, "成績": rk + "位", "出典URL": url})
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows + added)
    print(f"player_results.csv に UWW の成績を {len(added)}件 足した")


if __name__ == "__main__":
    main()
