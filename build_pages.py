"""
大会ページ・開催回ページ(静的HTML)と sitemap.xml / robots.txt を data.json から自動生成する。

- 大会ページ:   /events/<大会ID>/            (例: /events/tenno-cup/)
- 開催回ページ: /events/<大会ID>/<年>/       (例: /events/tenno-cup/2022/)
  同じ年に同じ大会が2回ある場合は /events/<大会ID>/<開始日>/ (例: 2023-07-17)
- 一度決めたURLは page_slugs.json に記録し、あとから変えない(共有されたリンクが切れないように)。
- 動画の元タイトル・URL・公開日時は加工せずに表示する。

使い方: python build_pages.py   (update_site.py の最後から自動で呼ばれる)
"""
import html
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone

SITE = "https://japanwrestlingchannel.com"
SITE_NAME = "レスリング配信アーカイブ"
GA_ID = "G-KWLY01JCWV"
HERE = os.path.dirname(os.path.abspath(__file__))
JST = timezone(timedelta(hours=9))

KIND_ORDER = ["match", "interview", "announcement", "highlight", "other"]
KIND_LABEL = {"match": "試合配信", "interview": "インタビュー", "announcement": "告知・抽選会",
              "highlight": "ダイジェスト", "other": "その他"}
STATUS_LABEL = {"cancelled": "中止", "postponed": "延期", "scheduled": "開催予定",
                "unverified": "開催日は動画の公開日からの推定"}
LINK_LABEL = {"manual": "手動で確認済み", "livedate": "配信日で照合", "candidate": "確認待ち",
              "series_only": "開催回を確認中", "unmatched": "大会を確認中"}
SCHEMA_STATUS = {"cancelled": "EventCancelled", "postponed": "EventPostponed"}


def e(s):
    return html.escape("" if s is None else str(s), quote=True)


def fmt_date(iso):
    if not iso:
        return "日付未確認"
    y, m, d = iso[:10].split("-")
    return f"{int(y)}年{int(m)}月{int(d)}日"


def fmt_range(a, b):
    if not a:
        return "日付未確認"
    if not b or a == b:
        return fmt_date(a)
    pa, pb = a.split("-"), b.split("-")
    if pa[0] == pb[0]:
        tail = f"{int(pb[2])}日" if pa[1] == pb[1] else f"{int(pb[1])}月{int(pb[2])}日"
        return f"{fmt_date(a)}〜{tail}"
    return f"{fmt_date(a)}〜{fmt_date(b)}"


def jst_date(iso):
    if not iso:
        return ""
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(JST).strftime("%Y-%m-%d")


def dur(iso):
    m = re.fullmatch(r"P(?:\d+D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return ""
    h, mi, se = (int(x or 0) for x in m.groups())
    if h:
        return f"{h}時間{mi}分" if mi else f"{h}時間"
    return f"{mi}分" if mi else f"{se}秒"


def yt(vid):
    return f"https://www.youtube.com/watch?v={vid}"


# ---------------------------------------------------------------- URL(スラッグ)

def assign_slugs(data, slug_path):
    try:
        with open(slug_path, encoding="utf-8") as f:
            saved = json.load(f)
    except FileNotFoundError:
        saved = {}
    ev_slugs = dict(saved.get("events", {}))
    used = set(ev_slugs.values())
    per_year = defaultdict(list)
    for ev in data["events"]:
        per_year[(ev["series"], ev["year"])].append(ev)
    for ev in sorted(data["events"], key=lambda x: (x.get("start") or f"{x['year']}-99", x["id"])):
        if ev["id"] in ev_slugs or not page_worthy(ev):
            continue
        base = f"{ev['series']}/{ev['year']}"
        siblings = [x for x in per_year[(ev["series"], ev["year"])] if x["id"] != ev["id"]]
        if base in used or any(page_worthy(x) for x in siblings):
            base = f"{ev['series']}/{ev.get('start') or ev['id']}"
        slug, i = base, 2
        while slug in used:
            slug, i = f"{base}-{i}", i + 1
        ev_slugs[ev["id"]] = slug
        used.add(slug)
    with open(slug_path, "w", encoding="utf-8") as f:
        json.dump({"about": "開催回ページのURL対応表(自動生成)。一度決めたURLは変えないために記録しています。手で編集しないでください。",
                   "events": dict(sorted(ev_slugs.items()))}, f, ensure_ascii=False, indent=1)
    return ev_slugs


def page_worthy(ev):
    return ev.get("n", 0) > 0


# ---------------------------------------------------------------- 共通パーツ

THUMB_JS = ("<script>function thumbFail(i){var o=['mqdefault','hqdefault','default'],m=/\\/vi\\/([^/]+)\\/([a-z]+)\\.jpg/.exec(i.src);"
            "if(m){var n=o[o.indexOf(m[2])+1];if(n){i.src='https://i.ytimg.com/vi/'+m[1]+'/'+n+'.jpg';return;}}i.remove();}</script>")


OG_DEFAULT = SITE + "/ogp.png"


def head(title, desc, path, og_image, jsonld, css):
    url = SITE + path
    og_image = og_image or OG_DEFAULT
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','{GA_ID}');</script>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(url)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(url)}">
{f'<meta property="og:image" content="{e(og_image)}">' if og_image else ''}
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
<meta name="theme-color" content="#000000">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&family=Teko:wght@500;600&display=swap" rel="stylesheet">
{css}
<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>
{THUMB_JS}
</head>
<body>
<header class="top"><div class="wrap"><div class="brand">
<a class="home" href="/" aria-label="{SITE_NAME}(トップへ)"><span class="logo-mark" aria-hidden="true">W</span><span class="logo-type">WRESTLING <span class="ac">ARCHIVE</span></span></a>
<nav class="topnav"><a href="/">大会を検索</a><a href="/technique/">技術動画</a></nav>
</div></div></header>
"""


def footer(as_of):
    return f"""<footer class="wrap">
<p><a href="/events/">大会一覧</a>・<a href="/technique/">技術動画</a>・<a href="/contact.html">お問い合わせ</a></p>
<p>このサイトは Japan Wrestling Channel などの YouTube で公開されているレスリングの動画を、大会ごとに整理した非公式のアーカイブです。動画はすべて YouTube で再生されます。</p>
<p>開催日・会場・出典は照合用の大会データに基づきます。動画と開催回の対応が確定していないものは「確認待ち」として区別しています。</p>
<p>データ更新:{e(fmt_date(as_of))}</p>
</footer>
</body>
</html>
"""


def breadcrumb_html(items):
    lis = []
    for i, (name, path) in enumerate(items):
        last = i == len(items) - 1
        lis.append(f'<li><span aria-current="page">{e(name)}</span></li>' if last or not path
                   else f'<li><a href="{e(path)}">{e(name)}</a></li>')
    return f'<nav class="crumbs" aria-label="現在の位置"><ol>{"".join(lis)}</ol></nav>'


def breadcrumb_ld(items):
    return {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, **({"item": SITE + p} if p else {})}
        for i, (n, p) in enumerate(items)]}


def thumb(vid, w=320, h=180):
    return (f'<div class="thumb"><img src="https://i.ytimg.com/vi/{e(vid)}/mqdefault.jpg" alt="" width="{w}" height="{h}" '
            f'loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="thumbFail(this)"></div>')


def video_row(v, show_basis=False):
    meta = []
    if v.get("ch"):
        meta.append(f'<span class="chlabel">{e(v["ch"])}</span>')
    if v.get("dh"):
        meta.append(f'<span class="d">{e(fmt_date(v["dh"]))}</span>')
    if v.get("m"):
        meta.append(f'<span>{e(v["m"])}マット</span>')
    if v.get("st"):
        meta.append(f'<span>{e("・".join(v["st"]))}</span>')
    if v.get("du"):
        meta.append(f'<span class="tabnum">{e(dur(v["du"]))}</span>')
    meta.append(f'<span>公開日 {e(fmt_date(jst_date(v.get("p"))))}</span>')
    if v.get("vs") == "upcoming":
        meta.append('<span class="lk">配信予定</span>')
    elif v.get("vs") == "unavailable":
        meta.append('<span class="lk unmatched">現在YouTubeで見られません</span>')
    if v.get("l") in LINK_LABEL:
        meta.append(f'<span class="lk {e(v["l"])}">{e(LINK_LABEL[v["l"]])}</span>')
    basis = f'<div class="basis">根拠:{e(v["b"])}</div>' if show_basis and v.get("b") else ""
    return (f'<li class="v"><a href="{e(yt(v["id"]))}" target="_blank" rel="noopener" tabindex="-1" aria-hidden="true">{thumb(v["id"])}</a>'
            f'<div><div class="vt"><a href="{e(yt(v["id"]))}" target="_blank" rel="noopener">{e(v["t"])}</a></div>'
            f'<div class="vm">{"".join(meta)}</div>{basis}</div></li>')


def vgroup(title, sub, vids, show_basis=False, gid=""):
    if not vids:
        return ""
    return (f'<section class="vgroup"{f" id={chr(34)}{gid}{chr(34)}" if gid else ""}><h3>{e(title)}<small>{e(sub)}</small></h3>'
            f'<ul class="vlist">{"".join(video_row(v, show_basis) for v in vids)}</ul></section>')


def kind_counts(vids):
    c = defaultdict(int)
    for v in vids:
        c[v.get("k") or "other"] += 1
    return [(k, c[k]) for k in KIND_ORDER if c[k]]


def counts_text(vids):
    return "・".join(f"{KIND_LABEL[k]}{n}本" for k, n in kind_counts(vids))


# ---------------------------------------------------------------- 開催回ページ

def event_page(ev, ctx):
    S, slugs, by_event, cand_by_event = ctx["S"], ctx["slugs"], ctx["by_event"], ctx["cand"]
    s = S.get(ev["series"], {"id": ev["series"], "name": ev["name"], "master": False})
    path = f"/events/{slugs[ev['id']]}/"
    spath = f"/events/{s['id']}/"
    name = ev.get("official_name") or ev["name"]
    vids = by_event.get(ev["id"], [])
    uniq = {v["id"]: v for v in vids}
    vids = list(uniq.values())
    matches = [v for v in vids if v.get("k") == "match"]
    first = (matches or vids or [None])[0]
    counts = counts_text(vids)
    status = ev.get("status")

    when = "配信日" if ev.get("derived") else "開催日"
    lead_parts = []
    if status == "cancelled":
        lead_parts.append(f"{ev['year']}年の{s['name']}は中止の記録があります。")
    elif ev.get("start"):
        verb = "開催予定" if status == "scheduled" else "開催"
        lead_parts.append(f"{fmt_range(ev['start'], ev.get('end'))}{('、' + ev['venue'] + 'で') if ev.get('venue') else 'に'}{verb}。"
                          if not ev.get("derived") else f"動画の配信日は{fmt_range(ev['start'], ev.get('end'))}です(公式の開催日は確認中)。")
    others = sorted({v["ch"] for v in vids if v.get("ch")})
    src = "Japan Wrestling Channel の配信" if not others else "YouTubeの配信・動画"
    lead_parts.append(f"{src}{len(vids)}本({counts})を{'日程ごとに' if matches else ''}掲載しています。")
    if others:
        n_main = sum(1 for v in vids if not v.get("ch"))
        lead_parts.append(f"Japan Wrestling Channel の配信{n_main}本のほか、{'、'.join(others)}の動画を含みます。" if n_main
                          else f"いずれも{'、'.join(others)}が公開している動画です。")
    lead = "".join(lead_parts)

    title = f"{name} {ev['year']}年 配信動画一覧({len(vids)}本)|{SITE_NAME}"
    desc = f"{name}({ev['year']}年)の配信・動画{len(vids)}本。{counts}。" + (
        f"{fmt_range(ev['start'], ev.get('end'))}開催" if ev.get("start") and not ev.get("derived") else "") + (
        f"、会場は{ev['venue']}。" if ev.get("venue") and not ev.get("derived") else "。")
    crumbs = [("トップ", "/"), ("大会一覧", "/events/"), (s["name"], spath), (f"{ev['year']}年" + (f"({fmt_date(ev['start'])[5:]})" if re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", slugs[ev['id']].split('/')[-1]) else ""), None)]

    ld = [breadcrumb_ld(crumbs)]
    if not ev.get("derived") and ev.get("start"):
        se = {"@type": "SportsEvent", "name": f"{name} {ev['year']}", "sport": "Wrestling", "url": SITE + path,
              "startDate": ev["start"], "endDate": ev.get("end") or ev["start"],
              "eventStatus": "https://schema.org/" + SCHEMA_STATUS.get(status, "EventScheduled")}
        if ev.get("venue"):
            se["location"] = {"@type": "Place", "name": ev["venue"]}
        ld.append(se)
    jsonld = {"@context": "https://schema.org", "@graph": ld}

    h = head(title, desc, path, f"https://i.ytimg.com/vi/{first['id']}/hqdefault.jpg" if first else "", jsonld, ctx["css"])
    h += '<main class="wrap page">' + breadcrumb_html(crumbs)
    badge = f'<span class="badge {e(status)}">{e(STATUS_LABEL[status])}</span>' if status in STATUS_LABEL else ""
    h += f'<h1>{e(name)} <span class="yr-h">{ev["year"]}年</span>{badge}</h1>'
    h += f'<p class="lead">{e(lead)}</p>'

    h += '<dl class="facts">'
    if ev.get("sessions"):
        ss = sorted(ev["sessions"], key=lambda x: x.get("start_date", ""))
        h += "<dt>日程</dt><dd><ul class=\"sessions\">" + "".join(
            f"<li>{e(fmt_range(x.get('start_date'), x.get('end_date')))} {e(x.get('label', ''))}{('(' + e(x['venue']) + ')') if x.get('venue') else ''}</li>" for x in ss) + "</ul></dd>"
    else:
        h += f"<dt>{when}</dt><dd>{e(fmt_range(ev.get('start'), ev.get('end')))}{'(予定)' if status == 'scheduled' else ''}</dd>"
        if ev.get("venue"):
            h += f"<dt>会場</dt><dd>{e(ev['venue'])}</dd>"
    if ev.get("fy_label"):
        h += f"<dt>年度</dt><dd>{e(ev['fy_label'])}</dd>"
    h += f"<dt>収録</dt><dd>{e(counts)}</dd>"
    if ev.get("group"):
        sib = [x for x in ctx["all_events"] if x.get("group") == ev["group"] and x["id"] != ev["id"]]
        if sib:
            h += "<dt>同時開催</dt><dd>" + "、".join(
                (f'<a href="/events/{e(slugs[x["id"]])}/">{e(S.get(x["series"], {}).get("name") or x["name"])}</a>' if x["id"] in slugs
                 else e(S.get(x["series"], {}).get("name") or x["name"])) for x in sib) + "</dd>"
    h += "</dl>"

    # 開催年の年表(ほかの年へのリンク)
    h += year_rail(s, ev["id"], ctx)

    # 動画(試合配信は日付→マット順)
    by_day = defaultdict(list)
    for v in matches:
        by_day[v.get("dh") or ""].append(v)
    for day in sorted(by_day):
        lst = sorted(by_day[day], key=lambda v: (v.get("m") or "~", v.get("p") or ""))
        sess = next((x for x in ev.get("sessions") or [] if x.get("start_date", "") <= day <= x.get("end_date", "")), None) if day else None
        h += vgroup(f"試合配信 {fmt_date(day)}" if day else "試合配信(競技日を確認中)",
                    f"{(sess['label'] + '、') if sess else ''}{len(lst)}本", lst, gid=f"d-{day}" if day else "d-x")
    for k in KIND_ORDER[1:]:
        lst = sorted([v for v in vids if (v.get("k") or "other") == k], key=lambda v: v.get("p") or "", reverse=True)
        h += vgroup(KIND_LABEL[k], f"{len(lst)}本", lst, gid=k)
    cands = [v for v in cand_by_event.get(ev["id"], []) if v["id"] not in uniq]
    if cands:
        h += ('<details class="more-box"><summary>この開催回の可能性がある動画(確認待ち ' + str(len(cands)) + '本)</summary>'
              '<p class="hint">大会名や年が曖昧なため、まだこの開催回と確定していない動画です。根拠を表示しています。</p>'
              + vgroup("確認待ち", f"{len(cands)}本", cands, show_basis=True) + '</details>')

    h += info_details(ev)
    h += f'<p class="tosearch-line"><a href="/#s={e(s["id"])}&amp;e={e(ev["id"])}">スタイルなどで絞り込む(検索ページで開く)</a></p>'
    h += "</main>" + footer(ctx["as_of"])
    return path, h


def source_label(src):
    t = src.get("type") or "出典"
    u = src.get("url", "")
    if "japan-wrestling.jp" in u and "報告書" in t:
        return t
    if "japan-wrestling.jp" in u:
        return "日本協会の大会ページ" if "報告" not in t else t
    return t


def info_details(ev):
    rows = []
    if ev.get("evidence"):
        rows.append(f"<dt>記録の種類</dt><dd>{e(ev['evidence'])}{('(' + e(ev['jwf_relationship']) + ')') if ev.get('jwf_relationship') else ''}</dd>")
    if ev.get("sources"):
        rows.append("<dt>出典</dt><dd><ul class=\"sources\">" + "".join(
            f'<li><a href="{e(x["url"])}" target="_blank" rel="noopener">{e(source_label(x))}</a> <span class="url">{e(re.sub("^https?://", "", x["url"]))}</span></li>'
            for x in ev["sources"]) + "</ul></dd>")
    notes = list(ev.get("notes") or [])
    for x in ev.get("schedule_history") or []:
        if x.get("source_text"):
            notes.append("日程の経緯:" + x["source_text"])
    if notes:
        rows.append("<dt>メモ</dt><dd>" + "".join(f"<p>{e(n)}</p>" for n in notes) + "</dd>")
    if ev.get("derived"):
        rows.append("<dt>開催情報</dt><dd>公式の開催日・会場を確認中です。表示している日付は動画の配信日です。</dd>")
    if not rows:
        return ""
    return '<details class="more-box info"><summary>大会情報・出典を詳しく見る</summary><dl class="facts">' + "".join(rows) + "</dl></details>"


def year_rail(s, current_id, ctx):
    evs = ctx["events_by_series"].get(s["id"], [])
    if len(evs) < 2:
        return ""
    same = defaultdict(int)
    for x in evs:
        same[x["year"]] += 1
    items = []
    for x in evs:
        cls = "cancelled" if x.get("status") == "cancelled" else "scheduled" if x.get("status") == "scheduled" else "unverified" if x.get("derived") else ("" if x.get("n") else "none")
        label = f"{x['year']}.{int(x['start'][5:7])}" if same[x["year"]] > 1 and x.get("start") else str(x["year"])
        n = "中止" if x.get("status") == "cancelled" else f"{x.get('n', 0)}本"
        inner = f'<span class="dot" aria-hidden="true"></span><span class="y">{label}</span><span class="n">{n}</span>'
        sr = f"{x['year']}年、{n}"
        if x["id"] == current_id:
            items.append(f'<span class="yr {cls}" aria-current="page" aria-label="{e(sr)}(表示中)">{inner}</span>')
        elif x["id"] in ctx["slugs"]:
            items.append(f'<a class="yr {cls}" href="/events/{e(ctx["slugs"][x["id"]])}/" aria-label="{e(sr)}">{inner}</a>')
        else:
            items.append(f'<span class="yr {cls} off" aria-label="{e(sr)}(動画なし)">{inner}</span>')
    return (f'<nav class="rail" aria-label="開催年">{"".join(items)}</nav>'
            '<script>(function(){var r=document.currentScript.previousElementSibling,c=r.querySelector("[aria-current]");'
            'if(c)r.scrollLeft=Math.max(0,c.offsetLeft-r.clientWidth/2+c.offsetWidth/2);})();</script>')


# ---------------------------------------------------------------- 大会ページ

def series_page(s, ctx):
    path = f"/events/{s['id']}/"
    evs = ctx["events_by_series"].get(s["id"], [])
    with_v = [x for x in evs if x.get("n")]
    years = [x["year"] for x in with_v]
    span = (f"{min(years)}年" if min(years) == max(years) else f"{min(years)}〜{max(years)}年") if years else ""
    loose = sorted(ctx["loose_by_series"].get(s["id"], []), key=lambda v: v.get("p") or "", reverse=True)
    total = s.get("n", 0)
    first_v = None
    for x in reversed(with_v):
        vs = ctx["by_event"].get(x["id"], [])
        first_v = next((v for v in vs if v.get("k") == "match"), vs[0] if vs else None)
        if first_v:
            break

    title = f"{s['name']} 配信動画アーカイブ({span}・{total}本)|{SITE_NAME}"
    alias = [a for a in (s.get("aliases") or []) if a != s["name"]]
    desc = f"{s['name']}の配信動画{total}本を開催年ごとに掲載。{span + '、' if span else ''}{len(with_v)}開催回。" + (f"別名:{'、'.join(alias[:4])}。" if alias else "")
    crumbs = [("トップ", "/"), ("大会一覧", "/events/"), (s["name"], None)]
    jsonld = {"@context": "https://schema.org", "@graph": [breadcrumb_ld(crumbs), {
        "@type": "CollectionPage", "name": f"{s['name']} 配信動画アーカイブ", "url": SITE + path,
        "hasPart": [{"@type": "WebPage", "name": f"{s['name']} {x['year']}年", "url": f"{SITE}/events/{ctx['slugs'][x['id']]}/"}
                    for x in with_v if x["id"] in ctx["slugs"]]}]}

    h = head(title, desc, path, f"https://i.ytimg.com/vi/{first_v['id']}/hqdefault.jpg" if first_v else "", jsonld, ctx["css"])
    h += '<main class="wrap page">' + breadcrumb_html(crumbs)
    h += f"<h1>{e(s['name'])}</h1>"
    lead = f"YouTubeで公開されている配信・動画{total}本を開催年ごとに整理しています。" + (f"動画があるのは{span}の{len(with_v)}開催回です。" if with_v else "")
    if not s.get("master"):
        lead += "この大会の公式の開催日・会場は確認中です。"
    h += f'<p class="lead">{e(lead)}</p>'
    if alias:
        h += f'<p class="aliases">この名前でも探せます:{e("、".join(alias))}</p>'

    h += '<section class="section"><h2>開催年から選ぶ</h2><ol class="occ">'
    for x in reversed(evs):
        badge = f'<span class="badge {e(x.get("status"))}">{e(STATUS_LABEL[x["status"]])}</span>' if x.get("status") in STATUS_LABEL else ""
        when = fmt_range(x.get("start"), x.get("end")) if x.get("start") else "日付未確認"
        body = (f'<span class="oy">{x["year"]}</span><span class="ob"><span class="od">{e(when)}{badge}</span>'
                f'<span class="ov">{e(x.get("venue") or "")}</span></span><span class="on">{("<b class=num>" + str(x.get("n")) + "</b>本") if x.get("n") else "動画なし"}</span>')
        if x["id"] in ctx["slugs"]:
            h += f'<li><a href="/events/{e(ctx["slugs"][x["id"]])}/">{body}</a></li>'
        else:
            h += f'<li class="off"><div>{body}</div></li>'
    h += "</ol></section>"
    if loose:
        h += vgroup("開催回を確認中の動画", f"この大会の動画ですが、どの年の開催回か特定できていません({len(loose)}本)", loose, show_basis=True)
    h += f'<p class="tosearch-line"><a href="/#s={e(s["id"])}">スタイルなどで絞り込む(検索ページで開く)</a></p>'
    h += "</main>" + footer(ctx["as_of"])
    return path, h


# ---------------------------------------------------------------- 技術動画

def norm_kw(t):
    import unicodedata
    t = unicodedata.normalize("NFKC", str(t or "")).lower()
    t = "".join(chr(ord(c) + 0x60) if "\u3041" <= c <= "\u3096" else c for c in t)
    return re.sub(r"\s+", "", t)


def load_json(root, name, default):
    try:
        with open(os.path.join(root, name), encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def classify_tech(tech, root):
    """技術動画ページに載せる動画(区分付き)と、どこにも載らない動画を分ける。
    大会と判定された動画は大会ページ側(update_site.py で照合)に出るので、ここでは除く。"""
    from channel_sort import Sorter
    sorter = Sorter(root)
    shown, unclassified, to_tournament = [], [], 0
    for ch in tech.get("channels", []):
        for v in ch.get("videos", []):
            if v.get("unavailable"):
                continue
            use, cat, basis = sorter.judge(v["id"], v.get("t", ""))
            item = dict(v, _ch=ch["name"], _chslug=ch["slug"], cat=cat, cat_basis=basis)
            if use == "technique":
                shown.append(item)
            elif use == "tournament":
                to_tournament += 1
            elif use == "other":
                unclassified.append(item)
    shown.sort(key=lambda v: v.get("p") or "", reverse=True)
    unclassified.sort(key=lambda v: v.get("p") or "", reverse=True)
    return shown, unclassified, to_tournament


def tech_video_row(v, cat_names, show_channel=True):
    meta = []
    if v.get("cat"):
        meta.append(f'<a class="catlink" href="/technique/{e(v["cat"])}/">{e(cat_names.get(v["cat"], ""))}</a>')
    if show_channel:
        meta.append(f'<a class="ch" href="/technique/{e(v["_chslug"])}/">{e(v["_ch"])}</a>')
    if v.get("du"):
        meta.append(f'<span class="tabnum">{e(dur(v["du"]))}</span>')
    meta.append(f'<span>公開日 {e(fmt_date(jst_date(v.get("p"))))}</span>')
    return (f'<li class="v"><a href="{e(yt(v["id"]))}" target="_blank" rel="noopener" tabindex="-1" aria-hidden="true">{thumb(v["id"])}</a>'
            f'<div><div class="vt"><a href="{e(yt(v["id"]))}" target="_blank" rel="noopener">{e(v["t"])}</a></div>'
            f'<div class="vm">{"".join(meta)}</div></div></li>')


def tech_list(title, sub, vids, cat_names, show_channel=True, gid=""):
    if not vids:
        return ""
    return (f'<section class="vgroup"{f" id={chr(34)}{gid}{chr(34)}" if gid else ""}><h2 class="vh">{e(title)}<small>{e(sub)}</small></h2>'
            f'<ul class="vlist">{"".join(tech_video_row(v, cat_names, show_channel) for v in vids)}</ul></section>')


def cat_nav(cats, counts, current=None, base="/technique/"):
    items = [f'<a href="/technique/"{" aria-current=" + chr(34) + "page" + chr(34) if current is None and base == "/technique/" else ""}>すべて<b>{sum(counts.values())}</b></a>']
    for c in cats:
        n = counts.get(c["slug"], 0)
        if not n:
            continue
        cur = ' aria-current="page"' if current == c["slug"] else ""
        items.append(f'<a href="/technique/{e(c["slug"])}/"{cur}>{e(c["name"])}<b>{n}</b></a>')
    return f'<nav class="catnav" aria-label="区分">{"".join(items)}</nav>'


def tech_pages(tech, cats, shown, ctx):
    cat_names = {c["slug"]: c["name"] for c in cats}
    counts = defaultdict(int)
    for v in shown:
        counts[v["cat"]] += 1
    channels = tech.get("channels", [])
    pages = []

    # 技術動画トップ
    path = "/technique/"
    crumbs = [("トップ", "/"), ("技術動画", None)]
    title = f"技術動画|{SITE_NAME}"
    desc = ("レスリングクラブが公開している技術・トレーニング動画を、" + "・".join(c["name"] for c in cats if counts.get(c["slug"])) +
            f"などの区分で探せます。{len(shown)}本掲載。")
    jsonld = {"@context": "https://schema.org", "@graph": [breadcrumb_ld(crumbs), {
        "@type": "CollectionPage", "name": "技術動画", "url": SITE + path,
        "hasPart": [{"@type": "WebPage", "name": c["name"], "url": f"{SITE}/technique/{c['slug']}/"} for c in cats if counts.get(c["slug"])]}]}
    h = head(title, desc, path, f"https://i.ytimg.com/vi/{shown[0]['id']}/hqdefault.jpg" if shown else "", jsonld, ctx["css"])
    h += '<main class="wrap page">' + breadcrumb_html(crumbs) + "<h1>技術動画</h1>"
    h += (f'<p class="lead">レスリングクラブが公開している、技術やトレーニング方法を紹介する動画です。'
          f'区分を選ぶと、その技術の動画だけを見られます。現在{len(shown)}本を掲載しています。</p>')
    h += cat_nav(cats, counts)
    h += '<ul class="catcards">' + "".join(
        f'<li><a href="/technique/{e(c["slug"])}/"><span class="cn">{e(c["name"])}</span><span class="cd">{e(c.get("description", ""))}</span>'
        f'<span class="cc"><b class="num">{counts[c["slug"]]}</b>本</span></a></li>'
        for c in cats if counts.get(c["slug"])) + "</ul>"
    h += tech_list("新着", f"公開日の新しい順", shown[:30], cat_names, gid="new")
    if channels:
        h += '<section class="section"><h2>チャンネル</h2><ul class="chlist">' + "".join(
            f'<li><a href="/technique/{e(c["slug"])}/"><span class="cn">{e(c["name"])}</span>'
            f'<span class="cm">{e(c.get("note", ""))}<b class="num">{sum(1 for v in shown if v["_chslug"] == c["slug"])}</b>本</span></a></li>'
            for c in channels) + "</ul></section>"
    h += "</main>" + footer(ctx["as_of"])
    pages.append((path, h, shown))

    # 区分ごとのページ
    for c in cats:
        vids = [v for v in shown if v["cat"] == c["slug"]]
        if not vids:
            continue
        path = f"/technique/{c['slug']}/"
        crumbs = [("トップ", "/"), ("技術動画", "/technique/"), (c["name"], None)]
        title = f"{c['name']}の技術動画({len(vids)}本)|{SITE_NAME}"
        desc = f"レスリングの{c['name']}の技術・練習動画{len(vids)}本。{c.get('description', '')}。"
        jsonld = {"@context": "https://schema.org", "@graph": [breadcrumb_ld(crumbs),
                  {"@type": "CollectionPage", "name": f"{c['name']}の技術動画", "url": SITE + path}]}
        h = head(title, desc, path, f"https://i.ytimg.com/vi/{vids[0]['id']}/hqdefault.jpg", jsonld, ctx["css"])
        h += '<main class="wrap page">' + breadcrumb_html(crumbs) + f"<h1>{e(c['name'])}</h1>"
        h += f'<p class="lead">{e(c.get("description", ""))}。レスリングクラブが公開している動画{len(vids)}本を、公開日の新しい順に並べています。</p>'
        h += cat_nav(cats, counts, current=c["slug"])
        h += tech_list(c["name"], f"{len(vids)}本", vids, cat_names, gid="list")
        h += "</main>" + footer(ctx["as_of"])
        pages.append((path, h, vids))

    # チャンネルごとのページ(区分ごとに見出しを分ける)
    for ch in channels:
        vids = [v for v in shown if v["_chslug"] == ch["slug"]]
        path = f"/technique/{ch['slug']}/"
        crumbs = [("トップ", "/"), ("技術動画", "/technique/"), (ch["name"], None)]
        title = f"{ch['name']} 技術動画一覧({len(vids)}本)|{SITE_NAME}"
        desc = f"{ch['name']}が公開している技術・トレーニング動画{len(vids)}本を区分ごとに掲載。" + (f"{ch['note']}。" if ch.get("note") else "")
        jsonld = {"@context": "https://schema.org", "@graph": [breadcrumb_ld(crumbs)]}
        h = head(title, desc, path, f"https://i.ytimg.com/vi/{vids[0]['id']}/hqdefault.jpg" if vids else "", jsonld, ctx["css"])
        h += '<main class="wrap page">' + breadcrumb_html(crumbs) + f"<h1>{e(ch['name'])}</h1>"
        if ch.get("note"):
            h += f'<p class="lead">{e(ch["note"])}。技術・トレーニング動画{len(vids)}本を区分ごとに並べています。</p>'
        ch_counts = defaultdict(int)
        for v in vids:
            ch_counts[v["cat"]] += 1
        jump = [f'<a href="#{e(c["slug"])}">{e(c["name"])}<b>{ch_counts[c["slug"]]}</b></a>' for c in cats if ch_counts.get(c["slug"])]
        if jump:
            h += f'<nav class="catnav" aria-label="このページ内の区分">{"".join(jump)}</nav>'
        for c in cats:
            lst = [v for v in vids if v["cat"] == c["slug"]]
            h += tech_list(c["name"], f"{len(lst)}本", lst, cat_names, show_channel=False, gid=c["slug"])
        if not vids:
            h += '<p class="empty">このチャンネルの動画はまだ区分けされていません。</p>'
        h += "</main>" + footer(ctx["as_of"])
        pages.append((path, h, vids))

    slugs_seen = [p for p, _, _ in pages]
    assert len(slugs_seen) == len(set(slugs_seen)), "技術動画の区分とチャンネルのURLが重なっています(tech_categories.json と tech_channels.json の slug を確認してください)"
    return [(p, h, max((jst_date(v.get("p")) for v in vs), default=ctx["as_of"])) for p, h, vs in pages]


# ---------------------------------------------------------------- 大会一覧・404

def index_page(ctx, series_list):
    path = "/events/"
    crumbs = [("トップ", "/"), ("大会一覧", None)]
    total = sum(x.get("n", 0) for x in series_list)
    title = f"大会一覧({len(series_list)}大会・{total}本)|{SITE_NAME}"
    desc = f"Japan Wrestling Channel で配信されたレスリング大会{len(series_list)}大会の一覧。天皇杯全日本選手権、明治杯、インカレ、インターハイなどの配信を開催年ごとに探せます。"
    jsonld = {"@context": "https://schema.org", "@graph": [breadcrumb_ld(crumbs), {
        "@type": "CollectionPage", "name": "大会一覧", "url": SITE + path,
        "hasPart": [{"@type": "WebPage", "name": x["name"], "url": f"{SITE}/events/{x['id']}/"} for x in series_list]}]}
    h = head(title, desc, path, "", jsonld, ctx["css"])
    h += '<main class="wrap page">' + breadcrumb_html(crumbs) + "<h1>大会一覧</h1>"
    h += f'<p class="lead">{e(f"配信動画のある{len(series_list)}大会です。開催日の新しい順に並んでいます。スタイルや開催年での絞り込みは検索ページで行えます。")}</p>'
    h += '<ol class="occ slist-static">'
    for x in series_list:
        evs = [v for v in ctx["events_by_series"].get(x["id"], []) if v.get("n")]
        yrs = [v["year"] for v in evs]
        span = (f"{min(yrs)}年" if min(yrs) == max(yrs) else f"{min(yrs)}〜{max(yrs)}年") if yrs else "開催年を確認中"
        tags = "".join(f'<span class="tag">{e(g)}</span>' for g in x.get("groups") or [])
        if x.get("scope") == "海外":
            tags += '<span class="tag">海外</span>'
        h += (f'<li><a href="/events/{e(x["id"])}/"><span class="ob"><span class="od sname">{e(x["name"])}</span>'
              f'<span class="ov">{e(span)} {tags}</span></span><span class="on"><b class="num">{x.get("n", 0)}</b>本</span></a></li>')
    h += "</ol></main>" + footer(ctx["as_of"])
    return path, h


CONTACT_EMAIL = "kitamura@japanwrestlingchannel.com"
# Formspree に登録したら発行された ID(例: xabcdefg)をここに入れる。空なら送信時にメールアプリが開く
FORMSPREE_ID = ""


def contact_page(ctx):
    h = head(f"お問い合わせ|{SITE_NAME}",
             "レスリング配信アーカイブへのお問い合わせページです。動画の掲載・非表示のご依頼、掲載内容の誤り、サイトの不具合、お仕事のご相談はこちらから。",
             "/contact.html", "",
             {"@context": "https://schema.org", "@type": "ContactPage", "name": "お問い合わせ",
              "url": SITE + "/contact.html"}, ctx["css"])
    body = CONTACT_BODY.replace("__EMAIL__", CONTACT_EMAIL).replace("__FORMSPREE_ID__", FORMSPREE_ID)
    return h + body + footer(ctx["as_of"])


CONTACT_BODY = r"""<main class="wrap page contact">
<nav class="crumbs" aria-label="パンくずリスト"><ol><li><a href="/">トップ</a></li><li>お問い合わせ</li></ol></nav>
<h1>お問い合わせ</h1>
<p class="lead">動画の掲載・非表示のご依頼、掲載内容の誤りのご指摘、サイトの不具合のご報告、お仕事のご相談など、お気軽にお送りください。内容を確認のうえ、ご返信いたします。</p>
<div class="direct"><span>メールで直接お送りいただくこともできます</span><a href="mailto:__EMAIL__">__EMAIL__</a></div>
<form id="contact-form" class="cform" novalidate>
<div class="field"><label for="c-name">お名前<span class="req">必須</span></label>
<input type="text" id="c-name" name="name" autocomplete="name" required></div>
<div class="field"><label for="c-email">返信先のメールアドレス<span class="req">必須</span></label>
<input type="email" id="c-email" name="email" autocomplete="email" inputmode="email" autocapitalize="off" spellcheck="false" required>
<p class="fhint">全角で入力しても、自動で半角に直ります。</p></div>
<div class="field"><label for="c-kind">お問い合わせの種類</label>
<select id="c-kind" name="kind">
<option>動画の掲載・非表示について</option>
<option>掲載内容の誤り(大会名・日付など)</option>
<option>サイトの不具合</option>
<option>取材・お仕事のご相談</option>
<option>その他</option>
</select></div>
<div class="field"><label for="c-msg">お問い合わせ内容<span class="req">必須</span></label>
<p class="fhint">動画についてのご依頼は、該当するページのURLか動画のタイトルを添えてください。</p>
<textarea id="c-msg" name="message" required></textarea></div>
<input class="hp" type="text" name="_gotcha" tabindex="-1" autocomplete="off" aria-hidden="true">
<p class="fhint">いただいたお名前・メールアドレスは、お問い合わせへの返信のためだけに使用します。</p>
<button type="submit" id="c-send">送信する</button>
<div class="cresult" id="c-result" role="status"></div>
</form>
</main>
<script>
(function(){
  var FORMSPREE_ID = "__FORMSPREE_ID__", TO = "__EMAIL__";
  var form = document.getElementById("contact-form"), result = document.getElementById("c-result"),
      btn = document.getElementById("c-send"), em = document.getElementById("c-email"), composing = false;
  function half(s){
    return s.replace(/[\uFF01-\uFF5E]/g, function(c){ return String.fromCharCode(c.charCodeAt(0) - 0xFEE0); })
            .replace(/[\u3000\s]/g, "").replace(/[ー－―‐]/g, "-");
  }
  em.addEventListener("compositionstart", function(){ composing = true; });
  em.addEventListener("compositionend", function(){ composing = false; em.value = half(em.value); });
  em.addEventListener("input", function(){ if (!composing) em.value = half(em.value); });
  em.addEventListener("blur", function(){ em.value = half(em.value); });
  function show(t, msg){ result.className = "cresult " + t; result.textContent = msg; }
  form.addEventListener("submit", function(ev){
    ev.preventDefault();
    var name = form.name.value.trim(), email = half(form.email.value.trim()),
        kind = form.kind.value, msg = form.message.value.trim();
    form.email.value = email;
    if (!name || !email || !msg){ show("ng", "お名前・メールアドレス・お問い合わせ内容を入力してください。"); return; }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)){ show("ng", "メールアドレスの形式を確認してください。"); return; }
    if (!FORMSPREE_ID){
      var body = "お名前: " + name + "\n返信先: " + email + "\n種類: " + kind + "\n\n" + msg;
      location.href = "mailto:" + TO + "?subject=" + encodeURIComponent("【お問い合わせ】" + kind) + "&body=" + encodeURIComponent(body);
      show("ok", "メールアプリが開きます。内容を確認して送信してください。開かない場合は " + TO + " へ直接お送りください。");
      return;
    }
    btn.disabled = true; btn.textContent = "送信しています…";
    fetch("https://formspree.io/f/" + FORMSPREE_ID, {method: "POST", headers: {"Accept": "application/json"}, body: new FormData(form)})
      .then(function(r){
        if (r.ok){ form.reset(); show("ok", "送信しました。内容を確認のうえ、ご返信いたします。"); }
        else { show("ng", "送信できませんでした。時間をおいて再度お試しいただくか、" + TO + " へ直接お送りください。"); }
      })
      .catch(function(){ show("ng", "通信に失敗しました。インターネット接続を確認するか、" + TO + " へ直接お送りください。"); })
      .then(function(){ btn.disabled = false; btn.textContent = "送信する"; });
  });
})();
</script>
"""


def llms_txt(data, series_list, ctx):
    """AI(ChatGPT・Claude・Perplexityなど)向けに、サイトの概要と主なページを平文でまとめる"""
    n_videos = len(data.get("videos", []))
    lines = [
        f"# {SITE_NAME}(Japan Wrestling Channel アーカイブ)",
        "",
        f"> YouTubeで公開されている日本のレスリング大会の配信・動画{n_videos:,}本を、大会名・開催年・日程ごとに整理した非公式のアーカイブです。"
        "動画そのものはYouTubeで再生されます。大会の開催日・会場は照合用の大会データに基づきます。",
        "",
        f"- サイト: {SITE}/",
        f"- データ更新日: {fmt_date(data.get('as_of'))}",
        f"- お問い合わせ: {SITE}/contact.html",
        "",
        "## 主なページ",
        f"- [大会一覧]({SITE}/events/): 配信動画のある{len(series_list)}大会の一覧",
        f"- [技術動画]({SITE}/technique/): レスリングクラブが公開している技術・トレーニング動画を、タックル・投げ技・グラウンドなどの区分で整理",
        f"- [検索ページ]({SITE}/): 大会名・通称・動画タイトルで検索",
        "",
        "## 大会(開催回ごとのページへのリンクを含む)",
    ]
    for x in series_list:
        evs = [v for v in ctx["events_by_series"].get(x["id"], []) if v.get("n")]
        yrs = [v["year"] for v in evs]
        span = (f"{min(yrs)}年" if min(yrs) == max(yrs) else f"{min(yrs)}〜{max(yrs)}年") if yrs else ""
        lines.append(f"- [{x['name']}]({SITE}/events/{x['id']}/): {span} 動画{x.get('n', 0)}本")
    return "\n".join(lines) + "\n"


def not_found_page(ctx):
    h = head(f"ページが見つかりません|{SITE_NAME}", "お探しのページは見つかりませんでした。", "/404.html", "",
             {"@context": "https://schema.org", "@type": "WebPage", "name": "ページが見つかりません"}, ctx["css"])
    h = h.replace('<link rel="canonical" href="https://japanwrestlingchannel.com/404.html">', '<meta name="robots" content="noindex">')
    h += ('<main class="wrap page"><h1>ページが見つかりません</h1>'
          '<p class="lead">URLが変わったか、削除された可能性があります。大会一覧か検索ページから探してください。</p>'
          '<p><a href="/events/">大会一覧を見る</a> / <a href="/">検索ページへ</a></p></main>' + footer(ctx["as_of"]))
    return h


# ---------------------------------------------------------------- 本体

PAGE_CSS = """
.contact{padding-bottom:44px}
.contact .direct{max-width:640px;margin:4px 0 22px;padding:12px 16px;background:var(--surface);border:1px solid var(--line);border-left:3px solid var(--pink);border-radius:8px}
.contact .direct span{display:block;font-size:12px;color:var(--ink3)}
.contact .direct a{font-size:17px;font-weight:700;text-decoration:none;word-break:break-all}
.cform{max-width:640px;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:22px 22px 24px}
.cform .field{margin-bottom:18px}
.cform label{display:block;font-weight:700;font-size:14px;margin-bottom:6px}
.cform .req{display:inline-block;margin-left:8px;padding:0 7px;border-radius:4px;background:var(--pink);color:#fff;font-size:11px;font-weight:700;vertical-align:1px}
.cform .fhint{font-size:12px;color:var(--ink3);margin:6px 0}
.cform input[type=text],.cform input[type=email],.cform select,.cform textarea{width:100%;box-sizing:border-box;font:inherit;font-size:16px;padding:11px 13px;border:1px solid var(--surface-2);border-radius:10px;background:var(--bg2);color:var(--ink)}
.cform textarea{min-height:170px;resize:vertical}
.cform input:focus,.cform select:focus,.cform textarea:focus{outline:none;border-color:var(--pink);box-shadow:0 0 0 3px var(--pink-tint)}
.cform button{display:block;width:100%;margin-top:14px;padding:13px;border:0;border-radius:999px;background:var(--pink);color:#fff;font:inherit;font-size:16px;font-weight:700;cursor:pointer}
.cform button:hover{background:var(--pink-deep)}
.cform button:disabled{opacity:.6;cursor:wait}
.cform .hp{position:absolute;left:-9999px}
.cresult{display:none;margin-top:14px;padding:12px 14px;border-radius:8px;font-size:14px}
.cresult.ok{display:block;background:#12301f;border:1px solid #2f6b47}
.cresult.ng{display:block;background:var(--st-cancel-bg);border:1px solid var(--st-cancel)}
@media (max-width:520px){.cform{padding:18px 14px 20px}}
.brand{justify-content:space-between}
.home{display:flex;align-items:center;gap:10px;color:var(--ink);text-decoration:none}
.topnav{display:flex;gap:8px}
.topnav a{font-size:13px;color:var(--ink);text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:5px 14px}
.topnav a:hover{border-color:var(--pink);color:var(--pink)}
.page{padding-top:18px}
.crumbs ol{list-style:none;margin:0 0 14px;padding:0;display:flex;flex-wrap:wrap;gap:4px;font-size:12px;color:var(--ink3)}
.crumbs li+li::before{content:"/";margin-right:4px;color:var(--line)}
.crumbs a{color:var(--ink2);text-decoration:none}.crumbs a:hover{color:var(--pink)}
.page h1{font-size:28px;font-weight:900;line-height:1.35;margin:0 0 8px;letter-spacing:.01em}
.page h1 .yr-h{font-family:var(--num);font-weight:600;font-size:1.25em;color:var(--pink);letter-spacing:.02em}
.lead{color:var(--ink2);margin:0 0 14px;max-width:70ch}
.page .facts{font-size:14px;margin-bottom:6px}
.page .vgroup h3{margin:0 0 8px;font-size:16px;font-weight:700;display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}
.page .vgroup h3 small{font-weight:400;color:var(--ink3);font-size:12px}
.vgroup{margin-top:26px}
a.yr{text-decoration:none}
.yr[aria-current] .dot{width:24px;height:24px;margin:2px auto;background:linear-gradient(120deg,var(--grad-a),var(--grad-b));box-shadow:0 0 0 3px var(--pink)}
.yr[aria-current] .y{color:var(--pink)}
.yr.off{cursor:default;opacity:.55}
.rail{margin:14px 0 4px;scrollbar-width:thin}
.more-box{margin-top:28px;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:12px 16px}
.more-box summary{cursor:pointer;font-weight:700}
.more-box .facts{margin-top:12px}
.sources .url{display:block;color:var(--ink3);font-size:11px}
.sources li+li{margin-top:6px}
.tosearch-line{margin:26px 0 0;font-size:13px}
.page .section{margin-top:24px}
.page .aliases{margin:0 0 6px}
.occ{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:6px}
.occ a,.occ .off>div{display:grid;grid-template-columns:72px 1fr auto;gap:12px;align-items:center;padding:12px 14px;border-radius:10px;background:var(--surface);border:1px solid var(--line);color:var(--ink);text-decoration:none}
.occ a:hover{border-color:var(--pink)}
.occ .off>div{opacity:.6}
.occ .oy{font-family:var(--num);font-weight:600;font-size:26px;line-height:1;color:var(--pink)}
.occ .off .oy{color:var(--ink3)}
.occ .ob{min-width:0;display:flex;flex-direction:column}
.occ .od{font-size:14px}
.occ .ov{font-size:12px;color:var(--ink3)}
.occ .on{font-size:12px;color:var(--ink3);white-space:nowrap}
.occ .on .num{font-size:18px;color:var(--ink);margin-right:1px}
.slist-static a{grid-template-columns:1fr auto}
.slist-static .sname{font-weight:700}
.slist-static .tag{margin-left:4px}
.chlist{list-style:none;margin:0 0 30px;padding:0;display:flex;flex-direction:column;gap:6px}
.chlist a{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:14px 16px;border-radius:10px;background:var(--surface);border:1px solid var(--line);color:var(--ink);text-decoration:none}
.chlist a:hover{border-color:var(--pink)}
.chlist .cn{font-weight:700;min-width:0}
.chlist .cm{font-size:12px;color:var(--ink3);display:flex;align-items:center;gap:8px;white-space:nowrap;flex:0 0 auto}
.chlist .cm .num{font-size:16px;color:var(--ink);font-family:var(--num)}
@media (max-width:520px){
  .page .catcards{grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}
  .page .catcards a{padding:10px 12px;gap:2px}
  .page .catcards .cn{font-size:14px}
  .page .catcards .cd{display:none}
  .page .catcards .cc .num{font-size:18px}
  .chlist a{flex-direction:column;align-items:flex-start;gap:6px}
  .chlist .cm{white-space:normal}
}
.v .ch{color:var(--ink2);text-decoration:none}
.v .chlabel{font-size:11px;color:var(--ink2);border:1px solid var(--line);border-radius:4px;padding:0 6px}
.v .ch:hover{color:var(--pink)}
.v .catlink{font-size:11px;border:1px solid var(--pink-line);color:var(--pink-deep);border-radius:4px;padding:0 7px;text-decoration:none}
.v .catlink:hover{border-color:var(--pink)}
.catnav{display:flex;gap:6px;overflow-x:auto;padding:4px 2px 10px;margin:4px 0 8px;scrollbar-width:thin}
.catnav a{flex:0 0 auto;display:inline-flex;align-items:baseline;gap:5px;font-size:13px;color:var(--ink);text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:6px 14px;background:var(--surface)}
.catnav a b{font-family:var(--num);font-weight:600;font-size:15px;color:var(--ink3)}
.catnav a:hover{border-color:var(--pink)}
.catnav a[aria-current]{background:var(--pink);border-color:var(--pink);color:#fff}
.catnav a[aria-current] b{color:#fff}
.catcards{list-style:none;margin:10px 0 10px;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:8px}
.catcards a{display:flex;flex-direction:column;gap:4px;height:100%;padding:14px 16px;border-radius:12px;background:var(--surface);border:1px solid var(--line);color:var(--ink);text-decoration:none;border-top:3px solid var(--pink)}
.catcards a:hover{border-color:var(--pink)}
.catcards .cn{font-weight:900;font-size:16px}
.catcards .cd{font-size:12px;color:var(--ink3);line-height:1.55;flex:1}
.catcards .cc{font-size:12px;color:var(--ink3)}
.catcards .cc .num{font-size:20px;color:var(--pink);margin-right:2px}
.page h2.vh{margin:0 0 8px;font-size:17px;font-weight:900;display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}
.page h2.vh small{font-weight:400;color:var(--ink3);font-size:12px}
.v .thumb img{width:100%;height:100%}
@media (max-width:760px){
  .page h1{font-size:22px}
  .brand{flex-wrap:wrap}
  .topnav{gap:6px}
  .topnav a{font-size:11.5px;padding:4px 9px;white-space:nowrap}
  .logo-type{font-size:21px;white-space:nowrap}
  .page .facts{grid-template-columns:max-content 1fr}
  .page .facts dt{margin-top:0}
  .occ a,.occ .off>div{grid-template-columns:56px 1fr auto;gap:10px;padding:10px 12px}
  .occ .oy{font-size:22px}
}
"""


def extract_css(index_path):
    with open(index_path, encoding="utf-8") as f:
        src = f.read()
    m = re.search(r"<style>(.*?)</style>", src, re.S)
    return (m.group(1) if m else "") + PAGE_CSS


def build(root=HERE, inline_css=False, only=None):
    with open(os.path.join(root, "data.json"), encoding="utf-8") as f:
        data = json.load(f)
    tech = data.get("tech", {"channels": []})
    css_text = extract_css(os.path.join(root, "index.html"))
    os.makedirs(os.path.join(root, "assets"), exist_ok=True)
    with open(os.path.join(root, "assets", "site.css"), "w", encoding="utf-8") as f:
        f.write(css_text)
    css = f"<style>{css_text}</style>" if inline_css else '<link rel="stylesheet" href="/assets/site.css">'

    slugs = assign_slugs(data, os.path.join(root, "page_slugs.json"))
    S = {s["id"]: s for s in data["series"]}
    events_by_series = defaultdict(list)
    for ev in data["events"]:
        events_by_series[ev["series"]].append(ev)
    for lst in events_by_series.values():
        lst.sort(key=lambda x: x.get("start") or f"{x['year']}-99")
    by_event, cand, loose_by_series = defaultdict(list), defaultdict(list), defaultdict(list)
    for v in data["videos"]:
        if v.get("e"):
            by_event[v["e"]].append(v)
        elif v.get("s"):
            loose_by_series[v["s"]].append(v)
        if not v.get("e"):
            for c in v.get("c") or []:
                cand[c].append(v)
    ctx = dict(S=S, slugs=slugs, by_event=by_event, cand=cand, loose_by_series=loose_by_series,
               events_by_series=events_by_series, all_events=data["events"], css=css, as_of=data.get("as_of"))

    pages = []
    for ev in data["events"]:
        if ev["id"] in slugs and (only is None or ev["id"] in only):
            path, doc = event_page(ev, ctx)
            lastmod = max((jst_date(v.get("p")) for v in by_event.get(ev["id"], [])), default=data.get("as_of"))
            pages.append((path, doc, lastmod))
    for s in data["series"]:
        if s.get("n") and (only is None or s["id"] in only):
            path, doc = series_page(s, ctx)
            vids = [v for x in events_by_series[s["id"]] for v in by_event.get(x["id"], [])] + loose_by_series[s["id"]]
            lastmod = max((jst_date(v.get("p")) for v in vids), default=data.get("as_of"))
            pages.append((path, doc, lastmod))
    if only is None:
        tcfg = load_json(root, "tech_categories.json", {"categories": []})
        cats = tcfg.get("categories", [])
        shown, unclassified, to_tournament = classify_tech(tech, root)
        order = {slug: i for i, slug in enumerate(tcfg.get("display_order", []))}
        cats_view = sorted(cats, key=lambda c: order.get(c["slug"], len(order)))
        pages.extend(tech_pages(tech, cats_view, shown, ctx))
        # 区分けできなかった動画はサイトに出さず、build_report.json に一覧を残す
        rp = os.path.join(root, "build_report.json")
        report = load_json(root, "build_report.json", {})
        cnt = defaultdict(int)
        for v in shown:
            cnt[v["cat"]] += 1
        report["tech"] = {"shown": len(shown), "by_category": dict(cnt), "moved_to_tournament": to_tournament,
                          "unclassified_count": len(unclassified),
                          "tech_unclassified": [{"video_id": v["id"], "title": v["t"], "channel": v["_ch"]} for v in unclassified]}
        with open(rp, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)

        def latest(sr):
            return max((x.get("start") or "" for x in events_by_series[sr["id"]] if x.get("n")), default="")
        listed = sorted([x for x in data["series"] if x.get("n")], key=latest, reverse=True)
        path, doc = index_page(ctx, listed)
        pages.append((path, doc, data.get("as_of")))
        with open(os.path.join(root, "404.html"), "w", encoding="utf-8") as f:
            f.write(not_found_page(ctx))
        with open(os.path.join(root, "contact.html"), "w", encoding="utf-8") as f:
            f.write(contact_page(ctx))
        with open(os.path.join(root, "llms.txt"), "w", encoding="utf-8") as f:
            f.write(llms_txt(data, listed, ctx))
    for path, doc, _ in pages:
        d = os.path.join(root, path.strip("/"))
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(doc)

    if only is None:
        urls = [(f"{SITE}/", data.get("as_of"))] + [(SITE + p, lm) for p, _, lm in sorted(pages)]
        urls.append((f"{SITE}/contact.html", None))
        with open(os.path.join(root, "sitemap.xml"), "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
            for u, lm in urls:
                f.write(f"  <url><loc>{e(u)}</loc>{f'<lastmod>{lm}</lastmod>' if lm else ''}</url>\n")
            f.write("</urlset>\n")
        with open(os.path.join(root, "robots.txt"), "w", encoding="utf-8") as f:
            f.write(f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n")
    n_ev = sum(1 for p in pages if p[0].startswith("/events/") and p[0].count("/") == 4)
    n_se = sum(1 for p in pages if p[0].startswith("/events/") and p[0].count("/") == 3)
    n_te = sum(1 for p in pages if p[0].startswith("/technique/"))
    print(f"ページを生成しました: {len(pages)}ページ(開催回 {n_ev}・大会 {n_se}・技術動画 {n_te})")
    return pages


if __name__ == "__main__":
    build()
