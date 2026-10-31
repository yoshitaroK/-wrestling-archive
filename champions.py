"""
大会ごとの歴代優勝者のページ(champions/)。日本語版と英語版(/en/champions/)を作る

  /champions/            … 歴代優勝者のまとめ(大会の一覧と、何年分の記録があるか)
  /champions/<大会ID>/   … その大会の歴代優勝者の表(例: /champions/tenno-cup/)

データは2つ。
  - player_results.csv の「成績」が「1位」の行。開催回ID → data.json の events → series で大会にまとめる
  - champions.csv … 古い年の優勝者。日本レスリング協会『歴代記録』(レスリング・スピリッツ調べ)の PDF から
    _work/champions/ のスクリプトで作った(大会ID, スタイル, 開催年, 階級, 氏名, 所属, 出典URL)。毎朝の自動更新では変わらない
  同じ大会・スタイル・年・階級に両方あるときは player_results.csv を使う(食い違いは build_report.json に出す)

決まり(/grill-me で決定)
  - 国内の大会だけ(data.json の series の scope が「海外」の大会は載せない)。新人戦の部は載せない
  - スタイルごと(フリースタイル → グレコローマン → 女子)に表を1つ。縦に年(新しい年が上)、横に階級。
    階級の区分が変わった年で表を分ける
  - 優勝者の名前は選手ページへのリンク(公開している選手だけ)。
    players.csv で「公開」が「はい」でない人・「未成年」が「いいえ」でない人は名前だけ(リンクなし)。「未成年」が「はい」の人は「—」
  - champions.csv の人は、players.csv の氏名(別表記も含む)が1人だけ一致するときだけ、その人として扱う。
    直近6年分(データ更新日の年から数えて)で所属が高校・中学などの人は「—」
  - 出典はページの一番下にまとめて載せる

英語版(#76、運営者の答えは案 A)
  - 名前は、選手ページがある人(ローマ字が確かな人)だけ出す。ほかは「—」(機械で作った綴りは出さない)
  - 所属は en_names.csv に英語名があるものだけ出す(英語版に日本語を出さない)
  - ページの上に、名前は日本語版で見られることと、日本語版へのリンクを出す
"""
import os
import re
import unicodedata
from collections import defaultdict

import i18n
from i18n import L, N, U
import players as P

STYLES = ["フリースタイル", "グレコローマン", "女子"]
# 歴代優勝者のページを作らない大会(選手ページ用に一部の選手の成績しか入れていないもの)
NO_CHAMPIONS = {"kokutai"}
# まとめページでの大会の並び順(ここにない大会は後ろに、名前順で並ぶ)
ORDER = ["tenno-cup", "meiji-cup", "intercollegiate", "university-championship", "university-greco",
         "east-spring", "east-autumn", "shakaijin"]
HERE_NOTE_MINOR = "未成年の選手(最近6年の記録で高校・中学などに所属していた選手を含む)は名前を載せていません(—)。"
CHAMPIONS_CSV = "champions.csv"
HISTORY_SOURCE = "日本レスリング協会『歴代記録』(レスリング・スピリッツ調べ)"
HISTORY_SOURCE_EN = "the Japan Wrestling Federation's historical records (compiled by Wrestling Spirits)"
RECENT_YEARS = 6
# 所属が高校・中学など(未成年とみなす)。「高教」(高校の先生)などは除く
SCHOOL_RE = re.compile(r"(高校|高等学校|中学|中等教育|高専|[^大]高$|[^大]中$|小学校|小$)")
# 昔の階級名の並び順
CLASSIC = ["ペーパー級", "ライトフライ級", "フライ級", "バンタム級", "フェザー級", "ライト級", "ウエルター級", "ミドル級",
           "ライトヘビー級", "ヘビー級"]
CLASSIC_EN = ["Paperweight", "Light flyweight", "Flyweight", "Bantamweight", "Featherweight", "Lightweight", "Welterweight",
              "Middleweight", "Light heavyweight", "Heavyweight"]
STYLE_ANCHOR = ["fs", "gr", "ww"]
STYLE_SHORT_EN = {"フリースタイル": "FS", "グレコローマン": "GR", "女子": "WW"}


def wname(w):
    """階級の表示。英語版は「100kg以上」→「100kg+」、昔の階級名は英語にする"""
    if not i18n.en():
        return w
    if w in CLASSIC:
        return CLASSIC_EN[CLASSIC.index(w)]
    return re.sub(r"以上$", "+", w or "")


def roman_by_id(ctx):
    """選手ID → ローマ字(英語版の名前。選手ページがある人だけ)"""
    if "_roman_by_id" not in ctx:
        ctx["_roman_by_id"] = {p["id"]: p.get("roman", "") for p in ctx.get("players") or []}
    return ctx["_roman_by_id"]


def shown_name(name, pid, ctx):
    """表に出す名前。英語版は選手ページがあってローマ字のある人だけ(ほかは空 → 「—」)"""
    if not i18n.en():
        return name
    return roman_by_id(ctx).get(pid, "") if pid else ""


def shown_club(club):
    """所属。英語版は英語名があるものだけ"""
    if not i18n.en():
        return club
    return i18n.names_table().get(club, "")


def wkey(w):
    """階級の並び順(軽い順)。「100kg以上」は「100kg」の後ろ。昔の階級名は CLASSIC の順"""
    if w in CLASSIC:
        return (CLASSIC.index(w), 0)
    m = re.match(r"(\d+)", w or "")
    return (int(m.group(1)), 1 if "以上" in w else 0) if m else (999, 0)


def name_key(s):
    """名前をくらべるときの形(全角半角・空白・中点の違いを無視する)"""
    return re.sub(r"[\s・･]", "", unicodedata.normalize("NFKC", s or ""))


def load(root, data):
    """大会ごとの優勝者を {大会ID: {スタイル: {年: {階級: [(氏名, 所属, 選手ID or None, 隠す), …]}}}} にまとめる"""
    people = {r.get("選手ID", ""): r for r in P.read_csv(os.path.join(root, P.PLAYERS_CSV))}
    results = P.read_csv(os.path.join(root, P.RESULTS_CSV))
    ev_by_id = {ev["id"]: ev for ev in data.get("events", [])}
    S = {s["id"]: s for s in data.get("series", [])}
    table = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
    sources = defaultdict(lambda: defaultdict(set))  # 大会ID → 年 → {(出典URL, スタイル)}
    report = {"rows": 0, "hidden_minor": 0, "no_link": 0, "skipped_unknown_event": 0}
    for r in results:
        if r.get("成績") != "1位":
            continue
        style = r.get("スタイル", "")
        if style not in STYLES:  # 新人戦の部は載せない
            continue
        ev = ev_by_id.get(r.get("開催回ID", ""))
        if not ev:
            report["skipped_unknown_event"] += 1
            continue
        s = S.get(ev["series"])
        if not s or s.get("scope") == "海外" or s["id"] in NO_CHAMPIONS:
            continue
        p = people.get(r.get("選手ID", ""), {})
        minor = P.is_yes(p.get("未成年"))
        public = P.is_yes(p.get("公開")) and P.is_adult(p.get("未成年")) and not minor
        year = int(r.get("開催年") or ev["year"])
        table[s["id"]][style][year][r.get("階級", "")].append(
            {"name": p.get("氏名", ""), "club": p.get("所属", ""), "id": p.get("選手ID") if public else None, "hidden": minor})
        if r.get("出典URL", "").startswith("http"):
            sources[s["id"]][year].add((r["出典URL"], style))
        report["rows"] += 1
        report["hidden_minor"] += minor
        report["no_link"] += (not public and not minor)
    history = load_history(root, data, people, table, S, report)
    return table, sources, history, report


def load_history(root, data, people, table, S, report):
    """champions.csv(古い年の優勝者)を table に足す。返すのは {大会ID: {(出典URL, スタイル): [年, …]}}"""
    path = os.path.join(root, CHAMPIONS_CSV)
    history = defaultdict(lambda: defaultdict(set))
    if not os.path.exists(path):
        return history
    by_name = defaultdict(set)
    for pid, p in people.items():
        for n in [p.get("氏名", "")] + (p.get("別表記") or "").split(";"):
            if name_key(n):
                by_name[name_key(n)].add(pid)
    as_of = str(data.get("as_of") or "")
    this_year = int(as_of[:4]) if as_of[:4].isdigit() else 0
    site_cells = {(sid, st, y, w) for sid, sts in table.items() for st, ys in sts.items() for y, ws in ys.items() for w in ws}
    added = defaultdict(list)
    report.update({"history_rows": 0, "history_linked": 0, "history_hidden": 0, "history_site_preferred": 0,
                   "history_mismatch": []})
    for r in P.read_csv(path):
        sid, style, w = r.get("大会ID", ""), r.get("スタイル", ""), r.get("階級", "")
        if sid not in S or style not in STYLES or not (r.get("開催年") or "").isdigit():
            continue
        year = int(r["開催年"])
        key = (sid, style, year, w)
        if key in site_cells:  # player_results.csv を優先する
            report["history_site_preferred"] += 1
            site = sorted(name_key(x["name"]) for x in table[sid][style][year][w])
            if name_key(r.get("氏名")) not in site:
                report["history_mismatch"].append(f"{sid} {style} {year} {w}: サイト「{'・'.join(x['name'] for x in table[sid][style][year][w])}」/ 歴代記録「{r.get('氏名')}」")
            continue
        added[key].append(r)
    for (sid, style, year, w), rows in added.items():
        for r in rows:
            ids = by_name.get(name_key(r.get("氏名")), set())
            p = people.get(next(iter(ids))) if len(ids) == 1 else None
            club = r.get("所属", "")
            minor = bool(p and P.is_yes(p.get("未成年")))
            if this_year and year > this_year - RECENT_YEARS and SCHOOL_RE.search(club):
                minor = True
            public = bool(p and P.is_yes(p.get("公開")) and P.is_adult(p.get("未成年"))) and not minor
            table[sid][style][year][w].append({"name": p["氏名"] if p else r.get("氏名", ""), "club": club,
                                                "id": p.get("選手ID") if public else None, "hidden": minor})
            if r.get("出典URL", "").startswith("http"):
                history[sid][(r["出典URL"], style)].add(year)
            report["history_rows"] += 1
            report["history_linked"] += public
            report["history_hidden"] += minor
    return history


def eras(by_year):
    """階級の区分が同じ年をまとめる(新しい年から)。[(年のリスト, 階級のリスト), …]
    ある年に記録のない階級があっても(片方の階級がもう片方に全部含まれていれば)同じ区分とみなし、そのマスは「—」にする"""
    out = []
    for y in sorted(by_year, reverse=True):
        ws = set(by_year[y])
        if out and (ws <= out[-1][1] or out[-1][1] <= ws):
            out[-1][0].append(y)
            out[-1][1] |= ws
        else:
            out.append([[y], ws])
    return [(ys, sorted(ws, key=wkey)) for ys, ws in out]


def years_text(years):
    ys = sorted(set(years))
    if len(ys) <= 4:
        return "・".join(str(y) for y in ys) + "年"
    return f"{ys[0]}〜{ys[-1]}年({len(ys)}年分)"


def all_years(t):
    return sorted({y for st in t.values() for y in st})


def edition_link(sid, year, ctx):
    """その年の開催回ページ(あれば)"""
    for ev in ctx["events_by_series"].get(sid, []):
        if ev["year"] == year and ev["id"] in ctx["slugs"]:
            return "/events/" + ctx["slugs"][ev["id"]] + "/"
    return ""


def cell(winners, e, ctx):
    if not winners:
        return '<td class="none">—</td>'
    parts = []
    for w in winners:
        name = "" if w["hidden"] else shown_name(w["name"], w["id"], ctx)
        if not name:
            parts.append('<span class="cw">—</span>')
            continue
        nm = f'<a href="{U("/players/" + w["id"] + "/")}">{e(name)}</a>' if w["id"] else e(name)
        club = shown_club(w["club"])
        club = f'<small>{e(club)}</small>' if club else ""
        parts.append(f'<span class="cw">{nm}{club}</span>')
    return "<td>" + "".join(parts) + "</td>"


def style_tables(sid, by_year, ctx, e):
    h = ""
    for years, ws in eras(by_year):
        if i18n.en():
            cap = "Weight classes, " + (f"{years[-1]}–{years[0]}" if len(years) > 1 else str(years[0]))
        else:
            cap = (f"{years[-1]}〜{years[0]}年" if len(years) > 1 else f"{years[0]}年") + "の階級"
        head = "".join(f'<th scope="col">{e(wname(w))}</th>' for w in ws)
        rows = ""
        for y in years:
            link = edition_link(sid, y, ctx)
            yh = f'<a href="{U(link)}">{y}</a>' if link else str(y)
            rows += f'<tr><th scope="row">{yh}</th>' + "".join(cell(by_year[y].get(w), e, ctx) for w in ws) + "</tr>"
        h += (f'<div class="ctable"><table class="champs"><caption>{e(cap)}</caption>'
              f'<thead><tr><th scope="col">{L("年", "Year")}</th>{head}</tr></thead><tbody>{rows}</tbody></table></div>')
    return h


RANK_MIN = 3     # ランキングに載せるのは優勝この回数以上の選手
RANK_TOP = 100   # 上位この順位まで(同じ回数の人は全員)
RANK_SERIES = {"tenno-cup", "meiji-cup"}  # ランキングを出す大会(天皇杯・明治杯だけ)
# ランキングで同じ字として数える旧字・異体字(players.VARIANTS に足りないもの。成國と成国、金澤と金沢など)
RANK_VARIANTS = str.maketrans("國澤嶋龍實廣瀨櫻惠榮", "国沢島竜実広瀬桜恵栄")


def ranking(t):
    """優勝回数のランキング。表の1マス(スタイル・年・階級)を1回と数え、名前が同じ人をまとめる。
    異体字(須崎と須﨑、高橋と髙橋など)は同じ名前として数え、表示は一番新しい年の書き方にする。
    名前を載せていない人(未成年など)は数えない。[(順位, 名前, 選手ID, 回数, {スタイル: 回数}, 最初の年, 最後の年), …]"""
    people = {}
    for st, by_year in t.items():
        for y, ws in by_year.items():
            for w, winners in ws.items():
                for x in winners:
                    if x["hidden"] or not name_key(x["name"]):
                        continue
                    p = people.setdefault(name_key(x["name"]).translate(P.VARIANTS).translate(RANK_VARIANTS),
                                          {"name": x["name"], "id": None, "n": 0, "st": defaultdict(int), "ys": set()})
                    if not p["ys"] or y > max(p["ys"]):
                        p["name"] = x["name"]
                    p["id"] = p["id"] or x["id"]
                    p["n"] += 1
                    p["st"][st] += 1
                    p["ys"].add(y)
    rows = sorted((p for p in people.values() if p["n"] >= RANK_MIN), key=lambda p: (-p["n"], min(p["ys"]), p["name"]))
    out, rank = [], 0
    for i, p in enumerate(rows):
        if i == 0 or p["n"] != rows[i - 1]["n"]:
            rank = i + 1
            if rank > RANK_TOP:
                break
        out.append((rank, p["name"], p["id"], p["n"], dict(p["st"]), min(p["ys"]), max(p["ys"])))
    return out


def ranking_html(s, t, e, ctx):
    if s["id"] not in RANK_SERIES:
        return ""
    rows = ranking(t)
    if len(rows) < 3:
        return ""
    en = i18n.en()
    body = ""
    for rank, name, pid, n, sts, y0, y1 in rows:
        name = shown_name(name, pid, ctx) or "—"
        nm = f'<a href="{U("/players/" + pid + "/")}">{e(name)}</a>' if pid else e(name)
        short = STYLE_SHORT_EN if en else {"フリースタイル": "フリー", "グレコローマン": "グレコ", "女子": "女子"}  # スマホで1行に収まるよう短く
        style = L("・", " · ").join(f"{short[st]}{L('', ' ')}{c}" if len(sts) > 1 else short[st]
                                   for st, c in sorted(sts.items(), key=lambda x: STYLES.index(x[0])))
        years = (str(y0) if y0 == y1 else f"{y0}–{y1}") if en else (f"{y0}年" if y0 == y1 else f"{y0}〜{y1}年")
        body += (f'<tr><th scope="row">{rank}</th><td class="rn">{nm}</td><td class="rc"><b>{n}</b>{L("回", "")}</td>'
                 f'<td class="rs">{e(style)}</td><td class="ry">{years}</td></tr>')
    sname = N(s["name"])
    hint = L(f'{e(sname)}で{RANK_MIN}回以上優勝した選手(上位{RANK_TOP}位まで)。'
             '1つの大会で1つの階級に優勝したら1回と数えています。名前の表記が同じ人を同じ選手として数えています。',
             f'Wrestlers who have won the {e(sname)} at least {RANK_MIN} times (top {RANK_TOP}). '
             'Each title in one weight class at one edition counts as one. Wrestlers without a player page are shown as "—".')
    return (f'<section class="section" id="rank"><h2>{L("優勝回数ランキング", "Most titles")}</h2>'
            f'<p class="hint">{hint}</p>'
            f'<div class="ctable"><table class="champs rank"><thead><tr><th scope="col">{L("順位", "Rank")}</th><th scope="col">{L("選手", "Wrestler")}</th>'
            f'<th scope="col">{L("優勝回数", "Titles")}</th><th scope="col">{L("スタイル", "Style")}</th><th scope="col">{L("優勝した年", "Years")}</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div></section>')


def years_text_en(years):
    ys = sorted(set(years))
    if len(ys) <= 4:
        return ", ".join(str(y) for y in ys)
    return f"{ys[0]}–{ys[-1]}, {len(ys)} years"


def span_text(years):
    return years_text_en(years) if i18n.en() else years_text(years)


def en_note(path, e):
    """英語版のページの上に出す、日本語版への案内(#76 案 A)"""
    return ('<p class="hint champ-ja">Names are shown only for wrestlers who have a player page on this site, '
            'so that we never show a guessed spelling. Other names (mostly from earlier years) are shown as "—"; '
            f'you can see them on the <a href="{e(path)}" hreflang="ja">Japanese version of this page</a> (<span lang="ja">日本語版</span>).</p>')


def series_page(s, t, src, hist, ctx, bp):
    e = bp.e
    en = i18n.en()
    path = f"/champions/{s['id']}/"
    name = N(s["name"])
    years = all_years(t)
    span = span_text(years)
    crumbs = [(L("トップ", "Home"), "/"), (L("歴代優勝者", "Past champions"), "/champions/"), (name, None)]
    title = L(f"{name} 歴代優勝者({span})|{bp.SITE_NAME}", f"{name} – Past Champions ({span}) | {bp.site_name()}")
    desc = L(f"{name}の歴代優勝者を、スタイル・階級ごとに年別にまとめた表({span})。選手名から選手ページへ移れます。",
             f"Past champions of the {name} by style, weight class and year ({span}). Names link to player pages.")
    jsonld = {"@context": "https://schema.org", "@graph": [bp.breadcrumb_ld(crumbs), {
        "@type": "WebPage", "name": L(f"{name} 歴代優勝者", f"{name} – Past Champions"), "url": bp.SITE + U(path),
        "inLanguage": L("ja", "en")}]}
    h = bp.head(title, desc, path, "", jsonld, ctx["css"])
    h += '<main id="content" class="wrap page champ">' + bp.breadcrumb_html(crumbs)
    h += f"<h1>{e(L(f'{name} 歴代優勝者', f'{name}: Past Champions'))}</h1>"
    if en:
        h += (f'<p class="lead">Champions of the {e(name)} by style and weight class, year by year. '
              f'This page covers {e(span)}. Click a name to open the wrestler\'s page.</p>')
        h += en_note(path, e)
    else:
        h += (f'<p class="lead">{e(name)}の優勝者を、スタイル・階級ごとに年別にまとめています。いま載せているのは{e(span)}の記録です。'
              f'選手名を押すと、その選手のページへ移れます。</p>')
    rank = ranking_html(s, t, e, ctx)
    nav = "".join(f'<a href="#{STYLE_ANCHOR[STYLES.index(st)]}">{e(N(st))}</a>' for st in STYLES if st in t) + (
        f'<a href="#rank">{L("優勝回数ランキング", "Most titles")}</a>' if rank else "")
    if len([st for st in STYLES if st in t]) > 1 or rank:
        h += f'<nav class="catnav" aria-label="{L("スタイル", "Style")}">{nav}</nav>'
    for st in STYLES:
        if st not in t:
            continue
        h += f'<section class="section" id="{STYLE_ANCHOR[STYLES.index(st)]}"><h2>{e(N(st))}</h2>'
        h += style_tables(s["id"], t[st], ctx, e) + "</section>"
    h += L('<p class="hint">「—」はその年にその階級の記録がないか、名前を載せていないことを表します。'
           '所属は大会のときのものです。リンクのない名前は、選手ページを作っていない選手です。' + HERE_NOTE_MINOR + "</p>",
           '<p class="hint">"—" means there is no record for that weight class in that year, or that the name is not shown. '
           'Teams are as of the tournament and are shown only when we have an English name for them. '
           'Names of minors (including wrestlers listed with a high school or junior high school in the last '
           f'{RECENT_YEARS} years) are not shown.</p>')
    # 優勝回数ランキングは表の下(出典の前)に置く
    h += rank
    # 出典(年ごと)
    items = ""
    for y in sorted(src, reverse=True):
        by_url = defaultdict(list)
        for u, st in src[y]:
            by_url[u].append(st)
        links = L("・", " · ").join(
            f'<a href="{e(u)}" target="_blank" rel="noopener">{e(L("・", " / ").join(N(x) for x in sorted(sts, key=STYLES.index)))}</a>'
            for u, sts in sorted(by_url.items(), key=lambda x: min(STYLES.index(s) for s in x[1])))
        items += f"<li><b>{y}{L('年', '')}</b> {links}</li>"
    hitems = ""
    for (u, st), ys in sorted(hist.items(), key=lambda x: STYLES.index(x[0][1])):
        hitems += (f'<li><a href="{e(u)}" target="_blank" rel="noopener">{e(N(st))}{L("(PDF)", " (PDF)")}</a> … '
                   f'{e(L(years_text(ys) + "の記録", "records for " + years_text_en(ys)))}</li>')
    if items or hitems:
        h += f'<section class="section csrc"><h2>{L("出典", "Sources")}</h2>'
        if items:
            h += L('<p class="hint">日本レスリング協会が公開している入賞者一覧(PDF)から作っています。</p>',
                   '<p class="hint">From the lists of medalists published by the Japan Wrestling Federation (PDF, in Japanese).</p>') + f'<ul>{items}</ul>'
        if hitems:
            h += L(f'<p class="hint">{"それより前の年は、" if items else ""}{e(HISTORY_SOURCE)}から作っています。</p>',
                   f'<p class="hint">{"Earlier years are from " if items else "From "}{e(HISTORY_SOURCE_EN)} (PDF, in Japanese).</p>') + f'<ul>{hitems}</ul>'
        h += "</section>"
    h += (f'<p class="tosearch-line"><a href="{U("/events/" + s["id"] + "/")}">{e(L(f"{name}の配信動画を見る", f"Watch {name} videos"))}</a> / '
          f'<a href="{U("/champions/")}">{L("ほかの大会の歴代優勝者", "Past champions of other tournaments")}</a></p>')
    h += P.optout_note(listing=True)
    h += "</main>" + bp.footer(ctx["as_of"])
    return path, h


def index_page(listed, ctx, bp):
    e = bp.e
    en = i18n.en()
    path = "/champions/"
    crumbs = [(L("トップ", "Home"), "/"), (L("歴代優勝者", "Past champions"), None)]
    desc = L(f"天皇杯・明治杯・インカレなど国内{len(listed)}大会の歴代優勝者を、大会ごと・スタイル・階級ごとにまとめています。",
             f"Past champions of {len(listed)} Japanese national tournaments, including the Emperor's Cup and the Meiji Cup, "
             "by tournament, style and weight class.")
    jsonld = {"@context": "https://schema.org", "@graph": [bp.breadcrumb_ld(crumbs), {
        "@type": "CollectionPage", "name": L("歴代優勝者", "Past champions"), "url": bp.SITE + U(path), "inLanguage": L("ja", "en"),
        "hasPart": [{"@type": "WebPage", "name": L(f"{N(s['name'])} 歴代優勝者", f"{N(s['name'])} – Past Champions"),
                     "url": bp.SITE + U(f"/champions/{s['id']}/")} for s, _ in listed]}]}
    h = bp.head(L(f"歴代優勝者({len(listed)}大会)|{bp.SITE_NAME}", f"Past Champions ({len(listed)} tournaments) | {bp.site_name()}"),
                desc, path, "", jsonld, ctx["css"])
    h += '<main id="content" class="wrap page">' + bp.breadcrumb_html(crumbs) + f'<h1>{L("歴代優勝者", "Past champions")}</h1>'
    h += f'<p class="lead">{e(desc)}{L("大会名を押すと、その大会の歴代優勝者の表が開きます。", " Choose a tournament to open its table of champions.")}</p>'
    if en:
        h += en_note(path, e)
    h += '<ol class="occ slist-static champ-list">'
    for s, t in listed:
        ys = all_years(t)
        span = L(years_text(ys) + "の記録", "Records for " + years_text_en(ys))
        h += (f'<li><a href="{U("/champions/" + s["id"] + "/")}"><span class="ob"><span class="od sname">{e(N(s["name"]))}</span>'
              f'<span class="ov">{e(span)}</span></span><span class="on"><b class="num">{len(ys)}</b>{L("年分", " years")}</span></a></li>')
    h += "</ol>"
    h += L('<p class="hint">日本レスリング協会が公開している入賞者一覧と、' + e(HISTORY_SOURCE) + 'から作っています。'
           '同じ年・階級の記録が両方にあるときは、入賞者一覧のほうを載せています。出典は各大会のページの一番下にあります。</p>',
           '<p class="hint">Compiled from the lists of medalists published by the Japan Wrestling Federation and from '
           + e(HISTORY_SOURCE_EN) + '. Where both cover the same year and weight class, we use the list of medalists. '
           'Sources are listed at the bottom of each tournament page.</p>')
    h += "</main>" + bp.footer(ctx["as_of"])
    return path, h


def prepare(root, data, ctx):
    """優勝者の表を読み、ctx["champions"] に {大会ID: 表} を入れる(大会ページのリンクでも使う)"""
    table, sources, history, report = load(root, data)
    ctx["champions"], ctx["champion_sources"], ctx["champion_history"] = table, sources, history
    report["series"] = len(table)
    return report


def link_html(s, ctx):
    """大会ページに出す「歴代優勝者」へのリンク(表がある大会だけ)"""
    if s["id"] not in ctx.get("champions", {}):
        return ""
    return (f'<p class="champ-link"><a href="{U("/champions/" + s["id"] + "/")}">'
            f'{L(s["name"] + "の歴代優勝者を見る", "Past champions of the " + N(s["name"]))}</a></p>')


def build(ctx, bp):
    """歴代優勝者のページを作って (path, doc) のリストを返す。日本語版・英語版とも同じ処理"""
    table, sources = ctx.get("champions", {}), ctx.get("champion_sources", {})
    if not table:
        return []
    S = ctx["S"]
    sids = sorted(table, key=lambda x: (ORDER.index(x) if x in ORDER else len(ORDER), S[x]["name"]))
    listed = [(S[x], table[x]) for x in sids]
    history = ctx.get("champion_history", {})
    pages = [series_page(s, t, sources[s["id"]], history.get(s["id"], {}), ctx, bp) for s, t in listed]
    pages.append(index_page(listed, ctx, bp))
    return pages


CHAMP_CSS = """
.champ .section h2{font-size:19px;margin:0 0 6px}
.ctable{overflow-x:auto;margin:6px 0 20px;border:1px solid var(--line);border-radius:10px;background:var(--surface)}
table.champs{border-collapse:separate;border-spacing:0;font-size:13px;min-width:100%}
table.champs caption{caption-side:top;text-align:left;padding:8px 12px 6px;font-size:12px;color:var(--ink3)}
table.champs th,table.champs td{padding:8px 10px;border-top:1px solid var(--line);text-align:left;vertical-align:top;white-space:nowrap}
table.champs thead th{color:var(--ink2);font-weight:600;font-size:15px;font-family:var(--num);letter-spacing:.03em}
table.champs tbody th{position:sticky;left:0;z-index:1;background:var(--surface);font-family:var(--num);font-weight:600;font-size:18px;color:var(--pink);border-right:1px solid var(--line)}
table.champs thead th:first-child{position:sticky;left:0;z-index:2;background:var(--surface);border-right:1px solid var(--line)}
table.champs tbody th a{color:var(--pink);text-decoration:none}
table.champs tbody th a:hover{text-decoration:underline}
table.champs td .cw{display:block;font-weight:700}
table.champs td .cw+.cw{margin-top:6px}
table.rank tbody th{text-align:center;min-width:3em}
table.rank td.rn{font-weight:700;font-size:15px}
table.rank td.rc b{font-family:var(--num);font-size:20px;color:var(--pink);margin-right:2px}
table.rank td.rs,table.rank td.ry{color:var(--ink2)}
table.champs td a{color:var(--ink);text-decoration:underline;text-decoration-color:var(--pink-line);text-underline-offset:3px}
table.champs td a:hover{color:var(--pink)}
table.champs td small{display:block;font-weight:400;font-size:11px;color:var(--ink3)}
table.champs td.none{color:var(--ink3)}
.csrc ul{margin:6px 0 0;padding-left:1.2em;font-size:13px}
.csrc li+li{margin-top:4px}
.csrc b{font-family:var(--num);font-weight:600;font-size:15px;margin-right:6px}
.champ-link{margin:4px 0 0}
.champ-link a{display:inline-block;padding:8px 18px;border:1px solid var(--pink-line);border-radius:999px;color:var(--pink);text-decoration:none;font-size:14px;font-weight:700}
.champ-link a:hover{border-color:var(--pink)}
.champ-list a{grid-template-columns:1fr auto}
.champ-ja{margin:-4px 0 14px}
"""
