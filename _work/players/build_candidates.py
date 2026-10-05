"""入賞者一覧の PDF(jwf/)から、選手の候補の表(players_candidates.csv)と成績の表(player_results_candidates.csv)を作る"""
import json, re, hashlib, csv
from collections import defaultdict, Counter
import parse_winners as parsewin

idx = json.load(open("jwf_index.json"))
MINOR = re.compile(r"高校|高等学校|中学|中等教育|少年団|キッズ|ジュニア|Jr\.?|小学|学園$")
STAFF = re.compile(r"教員|職員|教諭|コーチ|監督|OB|ＯＢ")
CLUB = re.compile(r"クラブ|教室|club|Club|CLUB|道場|スクール|アカデミー")
BAD = re.compile(r"賞|#N/A|N/A|優勝|団体|位$|^該当|なし|棄権|不戦|選手$")
DEF = {"university-championship": "フリースタイル", "university-greco": "グレコローマン"}
SER = {"tenno-cup": "天皇杯", "meiji-cup": "明治杯", "shakaijin": "全日本社会人", "intercollegiate": "インカレ", "east-spring": "東日本学生春季",
       "east-autumn": "東日本学生秋季", "university-championship": "全日本大学", "university-greco": "全日本大学グレコ"}
res, minor = [], 0
for x in idx:
    for u in x["winners"]:
        fn = "jwf/" + hashlib.md5(u.encode()).hexdigest()[:10] + ".pdf"
        rows = (parsewin.parse_rotated(fn, x["rotated"]["pages"], {tuple(v) for v in x["rotated"]["six"]})
                if x.get("rotated") else parsewin.parse(fn))
        for r in rows:
            nm = re.sub(r"\s+", " ", r["name"]).strip()
            if BAD.search(nm) or not re.search(r"[一-龥ぁ-んァ-ヶ]", nm):
                continue
            if MINOR.search(r["org"]) and not STAFF.search(r["org"]):
                minor += 1
                continue
            st = (r["div"] + " " if r["div"] else "") + (r["style"] or DEF.get(x["series"], ""))
            res.append(dict(event=x["event"], series=x["series"], year=x["year"], ename=x["name"], style=st, weight=r["weight"],
                            place=r["place"], name=nm, org=r["org"], src=u))
seen, U = set(), []
for r in res:
    k = (r["event"], r["style"], r["weight"], r["name"].replace(" ", ""))
    if k not in seen:
        seen.add(k); U.append(r)
by = defaultdict(list)
for r in U:
    by[r["name"].replace(" ", "")].append(r)
P = []
for key, rs in by.items():
    rs.sort(key=lambda r: (r["year"], r["event"]))
    orgs = []
    for r in rs:
        if r["org"] and r["org"] not in orgs:
            orgs.append(r["org"])
    ws = [int(r["weight"][:-2]) for r in rs]
    memo = []
    club = any(CLUB.search(o) for o in orgs) and not any(re.search(r"大学|自衛隊|株式会社|㈱|\(株\)|警|庁|役所", o) for o in orgs)
    if club: memo.append("所属がクラブ・教室だけ(年齢を確認)")
    if len(orgs) > 1: memo.append("所属が複数: " + " / ".join(orgs))
    if max(ws) - min(ws) >= 20: memo.append(f"階級の幅が大きい({min(ws)}〜{max(ws)}kg)。同じ名前の別の人かもしれない")
    P.append(dict(pid="p-" + hashlib.sha1(key.encode()).hexdigest()[:6], name=max((r["name"] for r in rs), key=lambda n: (" " in n, len(n))),
                  org=orgs[-1] if orgs else "", n=len(rs), best=min(int(r["place"]) for r in rs), club=club, memo=memo, rs=rs))
P.sort(key=lambda p: (-p["n"], p["best"]))
with open("players_candidates.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["選手ID", "氏名", "ふりがな", "別表記", "所属", "公開", "未成年", "入賞回数", "最高順位", "主な成績", "確認メモ"])
    for p in P:
        top = sorted(p["rs"], key=lambda r: (int(r["place"]), -r["year"]))[:3]
        w.writerow([p["pid"], p["name"], "", "", p["org"], "いいえ" if p["memo"] else "はい", "要確認" if p["club"] else "いいえ", p["n"], f"{p['best']}位",
                    " / ".join(f"{r['year']} {SER.get(r['series'], r['series'])} {r['style']} {r['weight']} {r['place']}位" for r in top), "・".join(p["memo"])])
with open("player_results_candidates.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["選手ID", "開催回ID", "大会名", "開催年", "スタイル", "階級", "成績", "出典URL"])
    for p in P:
        for r in p["rs"]:
            w.writerow([p["pid"], r["event"], r["ename"], r["year"], r["style"], r["weight"], f"{r['place']}位", r["src"]])
print(len(P), "players", len(U), "results", "minor-excluded", minor, "flag-weight", sum(1 for p in P if any("階級" in m for m in p["memo"])),
      "club", sum(p["club"] for p in P), "multiorg", sum(1 for p in P if any("複数" in m for m in p["memo"])), "best1", sum(1 for p in P if p["best"] == 1))
print(Counter(SER[r["series"]] + str(r["year"]) for r in U))
