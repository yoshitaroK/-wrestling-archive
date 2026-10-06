"""
大会ごとの歴代優勝者のページ(champions/)。いまは日本語版だけ作る(英語版は作らない)

  /champions/            … 歴代優勝者のまとめ(大会の一覧と、何年分の記録があるか)
  /champions/<大会ID>/   … その大会の歴代優勝者の表(例: /champions/tenno-cup/)

データは player_results.csv の「成績」が「1位」の行。開催回ID → data.json の events → series で大会にまとめる。

決まり(/grill-me で決定)
  - 国内の大会だけ(data.json の series の scope が「海外」の大会は載せない)。新人戦の部は載せない
  - スタイルごと(フリースタイル → グレコローマン → 女子)に表を1つ。縦に年(新しい年が上)、横に階級。
    階級の区分が変わった年で表を分ける
  - 優勝者の名前は選手ページへのリンク(公開している選手だけ)。
    players.csv で「公開」が「はい」でない人は名前だけ(リンクなし)。「未成年」が「はい」の人は「—」
  - 出典はページの一番下にまとめて載せる
"""
import os
from collections import defaultdict

import i18n
from i18n import U
import players as P

STYLES = ["フリースタイル", "グレコローマン", "女子"]
# まとめページでの大会の並び順(ここにない大会は後ろに、名前順で並ぶ)
ORDER = ["tenno-cup", "meiji-cup", "intercollegiate", "university-championship", "university-greco",
         "east-spring", "east-autumn", "shakaijin"]
HERE_NOTE_MINOR = "未成年の選手は名前を載せていません(—)。"


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
        if not s or s.get("scope") == "海外":
            continue
        p = people.get(r.get("選手ID", ""), {})
        minor = P.is_yes(p.get("未成年"))
        public = P.is_yes(p.get("公開")) and not minor
        year = int(r.get("開催年") or ev["year"])
        table[s["id"]][style][year][r.get("階級", "")].append(
            {"name": p.get("氏名", ""), "club": p.get("所属", ""), "id": p.get("選手ID") if public else None, "hidden": minor})
        if r.get("出典URL", "").startswith("http"):
            sources[s["id"]][year].add((r["出典URL"], style))
        report["rows"] += 1
        report["hidden_minor"] += minor
        report["no_link"] += (not public and not minor)
    return table, sources, report


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
    return [(ys, sorted(ws, key=P.weight_key)) for ys, ws in out]


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


def cell(winners, e):
    if not winners:
        return '<td class="none">—</td>'
    parts = []
    for w in winners:
        if w["hidden"]:
            parts.append('<span class="cw">—</span>')
            continue
        nm = f'<a href="{U("/players/" + w["id"] + "/")}">{e(w["name"])}</a>' if w["id"] else e(w["name"])
        club = f'<small>{e(w["club"])}</small>' if w["club"] else ""
        parts.append(f'<span class="cw">{nm}{club}</span>')
    return "<td>" + "".join(parts) + "</td>"


def style_tables(sid, by_year, ctx, e):
    h = ""
    for years, ws in eras(by_year):
        cap = (f"{years[-1]}〜{years[0]}年" if len(years) > 1 else f"{years[0]}年") + "の階級"
        head = "".join(f'<th scope="col">{e(w)}</th>' for w in ws)
        rows = ""
        for y in years:
            link = edition_link(sid, y, ctx)
            yh = f'<a href="{U(link)}">{y}</a>' if link else str(y)
            rows += f'<tr><th scope="row">{yh}</th>' + "".join(cell(by_year[y].get(w), e) for w in ws) + "</tr>"
        h += (f'<div class="ctable"><table class="champs"><caption>{e(cap)}</caption>'
              f'<thead><tr><th scope="col">年</th>{head}</tr></thead><tbody>{rows}</tbody></table></div>')
    return h


def series_page(s, t, src, ctx, bp):
    e = bp.e
    path = f"/champions/{s['id']}/"
    name = s["name"]
    years = all_years(t)
    span = years_text(years)
    crumbs = [("トップ", "/"), ("歴代優勝者", "/champions/"), (name, None)]
    title = f"{name} 歴代優勝者({span})|{bp.SITE_NAME}"
    desc = f"{name}の歴代優勝者を、スタイル・階級ごとに年別にまとめた表({span})。選手名から選手ページへ移れます。"
    jsonld = {"@context": "https://schema.org", "@graph": [bp.breadcrumb_ld(crumbs), {
        "@type": "WebPage", "name": f"{name} 歴代優勝者", "url": bp.SITE + path}]}
    h = bp.head(title, desc, path, "", jsonld, ctx["css"], alternates=False)
    h += '<main class="wrap page champ">' + bp.breadcrumb_html(crumbs)
    h += f"<h1>{e(name)} 歴代優勝者</h1>"
    h += (f'<p class="lead">{e(name)}の優勝者を、スタイル・階級ごとに年別にまとめています。いま載せているのは{e(span)}の記録です。'
          f'選手名を押すと、その選手のページへ移れます。</p>')
    nav = "".join(f'<a href="#{["fs", "gr", "ww"][STYLES.index(st)]}">{e(st)}</a>' for st in STYLES if st in t)
    if len([st for st in STYLES if st in t]) > 1:
        h += f'<nav class="catnav" aria-label="スタイル">{nav}</nav>'
    for st in STYLES:
        if st not in t:
            continue
        h += f'<section class="section" id="{["fs", "gr", "ww"][STYLES.index(st)]}"><h2>{e(st)}</h2>'
        h += style_tables(s["id"], t[st], ctx, e) + "</section>"
    h += ('<p class="hint">「—」はその年にその階級の記録がないか、名前を載せていないことを表します。'
          '所属は大会のときのものです。リンクのない名前は、選手ページを作っていない選手です。' + HERE_NOTE_MINOR + "</p>")
    # 出典(年ごと)
    items = ""
    for y in sorted(src, reverse=True):
        by_url = defaultdict(list)
        for u, st in src[y]:
            by_url[u].append(st)
        links = "・".join(f'<a href="{e(u)}" target="_blank" rel="noopener">{e("・".join(sorted(sts, key=STYLES.index)))}</a>'
                         for u, sts in sorted(by_url.items(), key=lambda x: min(STYLES.index(s) for s in x[1])))
        items += f"<li><b>{y}年</b> {links}</li>"
    if items:
        h += (f'<section class="section csrc"><h2>出典</h2><p class="hint">日本レスリング協会が公開している入賞者一覧(PDF)から作っています。</p>'
              f'<ul>{items}</ul></section>')
    h += f'<p class="tosearch-line"><a href="{U("/events/" + s["id"] + "/")}">{e(name)}の配信動画を見る</a> / <a href="/champions/">ほかの大会の歴代優勝者</a></p>'
    h += P.optout_note(listing=True)
    h += "</main>" + bp.footer(ctx["as_of"])
    return path, h


def index_page(listed, ctx, bp):
    e = bp.e
    path = "/champions/"
    crumbs = [("トップ", "/"), ("歴代優勝者", None)]
    desc = f"天皇杯・明治杯・インカレなど国内{len(listed)}大会の歴代優勝者を、大会ごと・スタイル・階級ごとにまとめています。"
    jsonld = {"@context": "https://schema.org", "@graph": [bp.breadcrumb_ld(crumbs), {
        "@type": "CollectionPage", "name": "歴代優勝者", "url": bp.SITE + path,
        "hasPart": [{"@type": "WebPage", "name": f"{s['name']} 歴代優勝者", "url": bp.SITE + f"/champions/{s['id']}/"} for s, _ in listed]}]}
    h = bp.head(f"歴代優勝者({len(listed)}大会)|{bp.SITE_NAME}", desc, path, "", jsonld, ctx["css"], alternates=False)
    h += '<main class="wrap page">' + bp.breadcrumb_html(crumbs) + "<h1>歴代優勝者</h1>"
    h += f'<p class="lead">{e(desc)}大会名を押すと、その大会の歴代優勝者の表が開きます。</p>'
    h += '<ol class="occ slist-static champ-list">'
    for s, t in listed:
        ys = all_years(t)
        n = sum(len(ws) for st in t.values() for ws in st.values())
        h += (f'<li><a href="/champions/{s["id"]}/"><span class="ob"><span class="od sname">{e(s["name"])}</span>'
              f'<span class="ov">{e(years_text(ys))}の記録</span></span><span class="on"><b class="num">{len(ys)}</b>年分</span></a></li>')
    h += "</ol>"
    h += ('<p class="hint">日本レスリング協会が公開している入賞者一覧から作っています。いまは2024年以降の記録だけです。'
          'それより前の年の記録も、順に足していきます。</p>')
    h += "</main>" + bp.footer(ctx["as_of"])
    return path, h


def prepare(root, data, ctx):
    """優勝者の表を読み、ctx["champions"] に {大会ID: 表} を入れる(大会ページのリンクでも使う)"""
    table, sources, report = load(root, data)
    ctx["champions"], ctx["champion_sources"] = table, sources
    report["series"] = len(table)
    return report


def link_html(s, ctx):
    """大会ページに出す「歴代優勝者」へのリンク(日本語版で、表がある大会だけ)"""
    if i18n.en() or s["id"] not in ctx.get("champions", {}):
        return ""
    return f'<p class="champ-link"><a href="/champions/{s["id"]}/">{s["name"]}の歴代優勝者を見る</a></p>'


def build(ctx, bp):
    """歴代優勝者のページを作って (path, doc) のリストを返す。日本語版だけ"""
    if i18n.en():
        return []
    table, sources = ctx.get("champions", {}), ctx.get("champion_sources", {})
    if not table:
        return []
    S = ctx["S"]
    sids = sorted(table, key=lambda x: (ORDER.index(x) if x in ORDER else len(ORDER), S[x]["name"]))
    listed = [(S[x], table[x]) for x in sids]
    pages = [series_page(s, t, sources[s["id"]], ctx, bp) for s, t in listed]
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
"""
