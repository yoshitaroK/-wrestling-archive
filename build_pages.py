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


def head(title, desc, path, og_image, jsonld, css):
    url = SITE + path
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
<a class="tosearch" href="/">大会を検索</a>
</div></div></header>
"""


def footer(as_of):
    return f"""<footer class="wrap">
<p>このサイトは Japan Wrestling Channel(YouTube)の公開動画を大会ごとに整理した非公式のアーカイブです。動画はすべて YouTube で再生されます。</p>
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
    lead_parts.append(f"Japan Wrestling Channel の配信{len(vids)}本({counts})を{'日程ごとに' if matches else ''}掲載しています。")
    lead = "".join(lead_parts)

    title = f"{name} {ev['year']}年 配信動画一覧({len(vids)}本)|{SITE_NAME}"
    desc = f"{name}({ev['year']}年)の配信動画{len(vids)}本。{counts}。" + (
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
    lead = f"Japan Wrestling Channel の配信{total}本を開催年ごとに整理しています。" + (f"動画があるのは{span}の{len(with_v)}開催回です。" if with_v else "")
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
.brand{justify-content:space-between}
.home{display:flex;align-items:center;gap:10px;color:var(--ink);text-decoration:none}
.tosearch{font-size:13px;color:var(--ink);text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:5px 14px}
.tosearch:hover{border-color:var(--pink);color:var(--pink)}
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
.v .thumb img{width:100%;height:100%}
@media (max-width:760px){
  .page h1{font-size:22px}
  .brand{flex-wrap:nowrap}
  .tosearch{font-size:12px;padding:4px 10px;white-space:nowrap}
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
        def latest(sr):
            return max((x.get("start") or "" for x in events_by_series[sr["id"]] if x.get("n")), default="")
        listed = sorted([x for x in data["series"] if x.get("n")], key=latest, reverse=True)
        path, doc = index_page(ctx, listed)
        pages.append((path, doc, data.get("as_of")))
        with open(os.path.join(root, "404.html"), "w", encoding="utf-8") as f:
            f.write(not_found_page(ctx))
    for path, doc, _ in pages:
        d = os.path.join(root, path.strip("/"))
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(doc)

    if only is None:
        urls = [(f"{SITE}/", data.get("as_of"))] + [(SITE + p, lm) for p, _, lm in sorted(pages)]
        with open(os.path.join(root, "sitemap.xml"), "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
            for u, lm in urls:
                f.write(f"  <url><loc>{e(u)}</loc>{f'<lastmod>{lm}</lastmod>' if lm else ''}</url>\n")
            f.write("</urlset>\n")
        with open(os.path.join(root, "robots.txt"), "w", encoding="utf-8") as f:
            f.write(f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n")
    print(f"ページを生成しました: {len(pages)}ページ(開催回 {sum(1 for p in pages if p[0].count('/') == 4)}・大会 {sum(1 for p in pages if p[0].count('/') == 3)})")
    return pages


if __name__ == "__main__":
    build()
