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
       "east-autumn": "東日本学生秋季", "university-championship": "全日本大学", "university-greco": "全日本大学グレコ",
       "shakaijin-open": "全国社会人オープン"}
res, minor, skipped_merged = [], 0, []
for x in idx:
    if x.get("skip"):  # 使わない一覧(理由は jwf_index.json の skip に書く)
        continue
    for u in x["winners"]:
        fn = "jwf/" + hashlib.md5(u.encode()).hexdigest()[:10] + ".pdf"
        rows = (parsewin.parse_rotated(fn, x["rotated"]["pages"], {tuple(v) for v in x["rotated"]["six"]}) if x.get("rotated")
                else parsewin.parse_table(fn) if x.get("table")  # 1行に1人ずつ並んだ表(2020年全日本大学グレコなど)
                else parsewin.parse(fn))
        award = False
        for r in rows:
            nm = re.sub(r"\s+", " ", r["name"]).strip()
            # 一覧のいちばん下の「最優秀選手」などの賞の欄から後は入賞者ではない(重量級の2位などと読まれてしまう)
            if re.search(r"最優秀|優秀選手|敢闘賞|技能賞", nm + r["org"]) or award:  # 「最優秀選手」が所属の欄にある一覧もある(2021年インカレ)
                award = True
                continue
            # 古い入賞者一覧(2014〜2019年ごろ)は「高 橋 侑 希」のように1文字ずつ空ける書き方で、姓と名の区切りが分からない。
            # 空白を取って比べ、名前の形は新しい一覧のもの(「高橋 侑希」)を使う。古い一覧にしか出ない人は区切りが分からないので公開しない
            toks = nm.split()
            unsplit = len(toks) >= 3 and sum(len(t) == 1 for t in toks) >= len(toks) - 1
            if unsplit:
                nm = "".join(toks)
            elif len(toks) > 2:
                skipped_merged.append((x["event"], r["weight"], nm))  # 2人分の名前がくっついた行など(「宮内 勇真バドバヤル ナンバルダグワ山本」)
                continue
            if BAD.search(nm) or not re.search(r"[一-龥ぁ-んァ-ヶ]", nm) or "〓" in nm + r["org"]:  # 〓=fix_glyphs.py で分からなかった字
                continue
            if MINOR.search(r["org"]) and not STAFF.search(r["org"]):
                minor += 1
                continue
            fname = u.rsplit("/", 1)[-1]
            # 見出しにスタイルが書かれていない一覧(2024年全日本社会人の ichiranFS-2.pdf など)は、ファイル名から
            by_name = "女子" if re.search(r"WW|女子", fname) else "グレコローマン" if re.search(r"GR|グレコ", fname) else "フリースタイル" if re.search(r"FS|フリー", fname) else ""
            style = r["style"] or DEF.get(x["series"], "") or by_name
            if re.search(r"WW", u.rsplit("/", 1)[-1]) and style == "フリースタイル":
                style = "女子"  # 女子の一覧(ファイル名が WW)なのに見出しから「フリースタイル」と読まれることがある(全日本社会人 2022・2023)
            st = (r["div"] + " " if r["div"] else "") + style
            res.append(dict(event=x["event"], series=x["series"], year=x["year"], ename=x["name"], style=st, weight=r["weight"],
                            place=r["place"], name=nm, org=r["org"], src=u, unsplit=unsplit))
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
    # 全日本社会人選手権は大人だけの大会なので、そこに出ている人には「年齢を確認」の印を付けない
    club = (any(CLUB.search(o) for o in orgs) and not any(re.search(r"大学|自衛隊|株式会社|㈱|\(株\)|警|庁|役所", o) for o in orgs)
            and not any(r["series"] == "shakaijin" for r in rs))
    if club: memo.append("所属がクラブ・教室だけ(年齢を確認)")
    if len(orgs) > 1: memo.append("所属が複数: " + " / ".join(orgs))
    # 重量級(86kg 以上)どうしの移動は、階級の区分の変わり目(97・125・130kg など)で幅が大きく見えるだけなので印を付けない
    if max(ws) - min(ws) >= 20 and min(ws) < 86: memo.append(f"階級の幅が大きい({min(ws)}〜{max(ws)}kg)。同じ名前の別の人かもしれない")
    if all(r.get("unsplit") for r in rs) or " " not in max((r["name"] for r in rs), key=len):
        memo.append("姓と名の区切りが分からない(古い入賞者一覧にだけ出てくる)")
    P.append(dict(pid="p-" + hashlib.sha1(key.encode()).hexdigest()[:6], name=max((r["name"] for r in rs), key=lambda n: (len(n.split()) == 2, " " in n, len(n))),
                  org=next((r["org"] for r in reversed(rs) if r["org"]), ""), n=len(rs),  # 所属はいちばん新しい大会のもの
                  best=min(int(r["place"]) for r in rs), club=club, memo=memo, rs=rs))
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
print("名前がくっついた・3つ以上に分かれた行(取り込まない):", skipped_merged)
