"""トップページの検索欄で、ニュース・大会の結果(速報)・よくある質問も探せるようにする(assets/search.json・assets/search-en.json)。

トップページを遅くしないため、このファイルはトップでは最初に読まず、検索欄にフォーカスしたとき・文字を打ったときに初めて読む(assets/top.js)。

中身(短い名前でファイルを小さくする):
  news : ニュース(日本語版だけ。英語版にはニュースのページが無い) {u:リンク, t:見出し, l:リード, d:日付, c:分類, g:タグ}
  res  : 大会の結果(速報)の大人の部だけ [開催回ID, 種別, 階級, 成績, 氏名, 都道府県, 所属, 選手ID(選手ページがある人だけ。無ければ "")]
         英語版はさらに [部名の英語, 所属の英語(無ければ日本語), ローマ字の名前(無ければ "")]
  faq  : よくある質問(/faq/ の FAQPage と同じ文) {q, a, u:リンク(無ければ "")}
  syn  : 言い換え。同じ組の言葉はどれで検索しても同じものが見つかる(大会名と series_aliases.json の別名+下の EXTRA_SYNONYMS)

高校生以下の部の結果は入れない(#未成年の決まり)。次のどれかに当たる行は外す:
  1. 種別が ADULT_DIVISIONS に無い(少年男子・U15 など。新しい部名も、ここに足すまでは入れない)
  2. 所属が高校・中学校など(「〜高」「〜高校」「〜中」「〜中学」などで終わる。「〜高教」=先生は大人なので残す。
     「含む」ではなく「終わる」で見る。中大(中央大)・中京学院大を消さないため)
     ※ 国体の「女子」や女子オープンの「シニア」には高校生も出ている
  3. 氏名が players.csv で「未成年」が「いいえ」になっていない人と同じ
選手ページへのリンクは、選手ページを作っている人(公開・大人)だけに付ける。
"""
import csv
import json
import os
import re

import i18n
import players as players_mod

# 大人の部として検索に入れる「種別」(event_results.csv)。ここに無い部名は入れない
ADULT_DIVISIONS = {"成年男子フリースタイル", "成年男子グレコローマン", "男子グレコローマン", "シニア", "女子"}
# 高校・中学校の所属(生徒)。「高教」「中教」(先生)は当てはまらない
SCHOOL_CLUB_RE = re.compile(r"(高|高校|高等学校|高専|中|中学|中学校|中等教育学校|特別支援学校|高等支援学校)$")
# 英語版の部名(players.DIVISION_EN に無いもの)
DIVISION_EN = {"シニア": "Senior", "男子グレコローマン": "Men's Greco-Roman"}
# 子どものクラブ・学校の部(所属にこの言葉を含む行は外す。大人の指導者の所属かもしれないが、念のため)
YOUTH_CLUB_WORDS = ("少年団", "ジュニア", "キッズ", "高等部", "中等部")
# 大会名の別名(series_aliases.json)のほかに足す言い換え。同じ意味だと確かなものだけ
EXTRA_SYNONYMS = [
    ["フリースタイル", "フリー"],
    ["グレコローマン", "グレコ"],
    ["オリンピック", "五輪"],
    ["世界レスリング連合", "UWW"],
    ["国民スポーツ大会", "国民体育大会", "国スポ", "国体"],
]


def adult_result_rows(root, minor_names):
    """event_results.csv から、検索に入れてよい大人の部の行だけを返す。(行のリスト, 外した行数)"""
    path = os.path.join(root, players_mod.EVENT_RESULTS_CSV)
    if not os.path.exists(path):
        return [], 0
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out, dropped = [], 0
    for r in rows:
        name, club = (r.get("氏名") or "").strip(), players_mod.norm(r.get("所属") or "")
        if not r.get("開催回ID") or not name:
            continue
        if (r.get("種別") or "").strip() not in ADULT_DIVISIONS or SCHOOL_CLUB_RE.search(club) \
                or any(w in club for w in YOUTH_CLUB_WORDS) \
                or players_mod.same_name(name) in minor_names:
            dropped += 1
            continue
        out.append(r)
    return out, dropped


def minor_names(root):
    """players.csv で大人と確かめられていない人(未成年が「いいえ」以外)の名前(異体字をそろえた形)"""
    path = os.path.join(root, players_mod.PLAYERS_CSV)
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    names = set()
    for r in rows:
        if not players_mod.is_adult(r.get("未成年")):
            for n in [r.get("氏名", "")] + (r.get("別表記") or "").split(";"):
                if n.strip():
                    names.add(players_mod.same_name(n))
    return names


def synonyms(root):
    groups = []
    try:
        with open(os.path.join(root, "series_aliases.json"), encoding="utf-8") as f:
            series = json.load(f).get("series", [])
    except (OSError, ValueError):
        series = []
    for s in series:
        g = list(dict.fromkeys([s.get("display_name", "")] + (s.get("search_aliases") or [])))
        g = [x for x in g if x]
        if len(g) > 1:
            groups.append(g)
    return groups + EXTRA_SYNONYMS


def write(root, ctx, faq, news_articles, report):
    """assets/search.json(日本語)か assets/search-en.json(英語)を書く。faq は build_pages.faq_items() の結果"""
    en = i18n.en()
    by_name, roman = {}, {}
    for p in ctx.get("players") or []:
        for k in [p["name"]] + p.get("aliases", []):
            by_name.setdefault(players_mod.same_name(k), set()).add(p["id"])
        if p.get("roman"):
            roman[p["id"]] = p["roman"]
    rows, dropped = adult_result_rows(root, minor_names(root))
    res = []
    for r in rows:
        ids = by_name.get(players_mod.same_name(r["氏名"]), set())
        pid = next(iter(ids)) if len(ids) == 1 else ""
        row = [r["開催回ID"], r.get("種別", ""), r.get("階級", ""), r.get("成績", ""), r["氏名"],
               r.get("都道府県", ""), r.get("所属", ""), pid]
        if en:  # 英語版:部名・所属の英語名と、ローマ字の名前(選手ページのある人だけ)を後ろに足す
            d = row[1]
            row += [DIVISION_EN.get(d) or players_mod.DIVISION_EN.get(d, d), i18n.N(row[6]) if row[6] else "",
                    roman.get(pid, "")]
        res.append(row)
    news = [] if en else [{"u": f"/news/{a['slug']}/", "t": a.get("title", ""), "l": a.get("lead", ""), "d": a.get("date", ""),
                           "c": a.get("category", ""), "g": a.get("tags", [])} for a in news_articles]
    faq_rows = [{"q": q, "a": a, "u": (link[0] if link[0].startswith("/en/") or link[0] == "/" and en else i18n.U(link[0])) if link else ""}
                for q, a, link in faq]
    doc = {"news": news, "res": res, "faq": faq_rows, "syn": synonyms(root)}
    os.makedirs(os.path.join(root, "assets"), exist_ok=True)
    name = "search-en.json" if en else "search.json"
    with open(os.path.join(root, "assets", name), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    report["en" if en else "ja"] = {
        "news": len(news), "results": len(res), "results_excluded": dropped,
        "results_linked": sum(1 for x in res if x[7]), "faq": len(faq_rows)}
