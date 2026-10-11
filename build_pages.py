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
import urllib.parse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import i18n
from i18n import L, U, N, T

SITE = "https://japanwrestlingchannel.com"
SITE_NAME = "レスリング配信アーカイブ"
SITE_NAME_EN = "Japan Wrestling Archive"
GA_ID = "G-KWLY01JCWV"
HERE = os.path.dirname(os.path.abspath(__file__))
JST = timezone(timedelta(hours=9))

KIND_ORDER = ["match", "interview", "announcement", "highlight", "other"]
_KIND = {"match": ("試合配信", "Match streams"), "interview": ("インタビュー", "Interviews"),
         "announcement": ("告知・抽選会", "Announcements & draws"), "highlight": ("ダイジェスト", "Highlights"),
         "other": ("その他", "Other")}
_STATUS = {"cancelled": ("中止", "Cancelled"), "postponed": ("延期", "Postponed"), "scheduled": ("開催予定", "Upcoming"),
           "unverified": ("開催日は動画の公開日からの推定", "Date estimated from video publish dates")}
_LINK = {"manual": ("手動で確認済み", "Manually verified"), "livedate": ("配信日で照合", "Matched by stream date"),
         "candidate": ("確認待ち", "Pending review"), "series_only": ("開催回を確認中", "Edition unconfirmed"),
         "unmatched": ("大会を確認中", "Tournament unconfirmed")}
SCHEMA_STATUS = {"cancelled": "EventCancelled", "postponed": "EventPostponed"}


def _pick(table):
    return {k: L(*v) for k, v in table.items()}


def kind_label(k):
    return L(*_KIND[k])


def status_label():
    return _pick(_STATUS)


def link_label():
    return _pick(_LINK)


# 日本語版で使っていた名前(players.py などから参照される)
KIND_LABEL = {k: v[0] for k, v in _KIND.items()}
STATUS_LABEL = {k: v[0] for k, v in _STATUS.items()}
LINK_LABEL = {k: v[0] for k, v in _LINK.items()}


def site_name():
    return L(SITE_NAME, SITE_NAME_EN)


def e(s):
    return html.escape("" if s is None else str(s), quote=True)


def fmt_date(iso):
    if not iso:
        return L("日付未確認", "Date TBC")
    if i18n.en():
        return i18n.en_date(iso)
    y, m, d = iso[:10].split("-")
    return f"{int(y)}年{int(m)}月{int(d)}日"


def fmt_range(a, b):
    if not a:
        return L("日付未確認", "Date TBC")
    if not b or a == b:
        return fmt_date(a)
    if i18n.en():
        return i18n.en_range(a, b)
    pa, pb = a.split("-"), b.split("-")
    if pa[0] == pb[0]:
        tail = f"{int(pb[2])}日" if pa[1] == pb[1] else f"{int(pb[1])}月{int(pb[2])}日"
        return f"{fmt_date(a)}〜{tail}"
    return f"{fmt_date(a)}〜{fmt_date(b)}"


def year_label(y):
    return L(f"{y}年", str(y))


def year_span(yrs, empty=""):
    if not yrs:
        return empty
    a, b = min(yrs), max(yrs)
    if a == b:
        return year_label(a)
    return L(f"{a}〜{b}年", f"{a}–{b}")


def n_videos(n):
    return L(f"{n}本", i18n.plural(n, "video"))


def jst_date(iso):
    if not iso:
        return ""
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(JST).strftime("%Y-%m-%d")


def dur(iso):
    m = re.fullmatch(r"P(?:\d+D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return ""
    h, mi, se = (int(x or 0) for x in m.groups())
    if i18n.en():
        if h:
            return f"{h} h {mi} min" if mi else f"{h} h"
        return f"{mi} min" if mi else f"{se} sec"
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
    # 配信動画がある開催回のほか、写真・アルバム(photos.json)がある開催回もページを作る
    return ev.get("n", 0) > 0 or bool(ev.get("_photo_page"))


# ---------------------------------------------------------------- 共通パーツ

THUMB_JS = ("<script>function thumbFail(i){var o=['mqdefault','hqdefault','default'],m=/\\/vi\\/([^/]+)\\/([a-z]+)\\.jpg/.exec(i.src);"
            "if(m){var n=o[o.indexOf(m[2])+1];if(n){i.src='https://i.ytimg.com/vi/'+m[1]+'/'+n+'.jpg';return;}}i.remove();}</script>")


OG_DEFAULT = SITE + "/ogp.png?v=2"
OG_DEFAULT_EN = SITE + "/ogp-en.png?v=1"

# ブラウザが日本語以外で、言語をまだ選んでいない人は英語版へ移す(検索ロボットは移さない)。日本語版のページにだけ入れる
LANG_REDIRECT_JS = ("<script>(function(){try{if(localStorage.getItem('lang'))return;}catch(x){return;}"
                    "var u=navigator.userAgent||'';if(/bot|crawl|spider|slurp|lighthouse|headless|preview|facebookexternalhit|embedly/i.test(u))return;"
                    "var l=(navigator.languages&&navigator.languages.length?navigator.languages:[navigator.language||'']).join(',').toLowerCase();"
                    "if(!l||/(^|,)ja/.test(l))return;location.replace('/en'+location.pathname+location.search+location.hash);})();</script>")


def lang_switch(path):
    """ヘッダーの言語切り替え。押した言語を覚えて、次からは自動で移動しない"""
    if i18n.en():
        href, code, label, title = path, "ja", "日本語", "日本語版を表示"
    else:
        href, code, label, title = "/en" + path, "en", "English", "English version"
    return (f'<a class="lang" href="{e(href)}" hreflang="{code}" lang="{code}" title="{title}" '
            f'onclick="try{{localStorage.setItem(\'lang\',\'{code}\')}}catch(x){{}}this.href=this.getAttribute(\'href\').split(\'#\')[0]+location.hash">{label}</a>')


def official_bar(lang_link=""):
    """ヘッダーの上の細い帯(公式サイトであることと、言語の切り替え)"""
    return (f'<div class="official"><div class="wrap"><span class="official-t">{L("Japan Wrestling Channel 公式サイト", "Official site of Japan Wrestling Channel")}</span>'
            f'{lang_link}</div></div>')


NAV = [("/", "大会を検索", "Search"), ("/players/", "選手", "Players"), ("/events/calendar/", "カレンダー", "Calendar"), ("/technique/", "技術動画", "Technique"), ("/photos/", "写真", "Photos"), ("/uww/", "国際大会", "International")]


def nav_links(path):
    """上のメニュー。今いるページの項目に下線を引く(aria-current)"""
    cur = "/events/calendar/" if path.startswith("/events/calendar/") else next((p for p, _, _ in NAV[1:] if path.startswith(p)), "")
    here = ' aria-current="page"'
    return "".join(f'<a href="{U(p)}"{here if p == cur else ""}>{L(ja, en)}</a>' for p, ja, en in NAV)


def header_search():
    """どのページにもある検索欄。送るとトップページ(大会の検索)に移り、入れた言葉で検索する"""
    label = L("大会名・選手名で検索", "Search tournaments & players")
    return (f'<form class="hsearch" role="search" action="{U("/")}" method="get" '
            f'onsubmit="var v=this.q.value.trim();if(!v){{event.preventDefault();this.q.focus();return;}}event.preventDefault();location.href=this.action+\'#q=\'+encodeURIComponent(v)">'
            f'<label class="sr" for="hq">{label}</label><input id="hq" name="q" type="search" autocomplete="off" placeholder="{label}">'
            f'<button type="submit" aria-label="{L("検索", "Search")}"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5 21 21"/></svg></button></form>')


def head(title, desc, path, og_image, jsonld, css, alternates=True):
    """path は日本語版のパス(/events/…/)。英語版では /en を付けたURLにする"""
    url = SITE + U(path)
    og_image = og_image or L(OG_DEFAULT, OG_DEFAULT_EN)
    alt = (f'<link rel="alternate" hreflang="ja" href="{e(SITE + path)}">\n'
           f'<link rel="alternate" hreflang="en" href="{e(SITE + "/en" + path)}">\n'
           f'<link rel="alternate" hreflang="x-default" href="{e(SITE + path)}">\n') if alternates else ""
    return f"""<!DOCTYPE html>
<html lang="{L('ja', 'en')}">
<head>
<script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','{GA_ID}');</script>
{'' if i18n.en() or not alternates else LANG_REDIRECT_JS}
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(url)}">
{alt}<meta property="og:type" content="website">
<meta property="og:site_name" content="{e(site_name())}">
<meta property="og:locale" content="{L('ja_JP', 'en_US')}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(url)}">
{f'<meta property="og:image" content="{e(og_image)}">' if og_image else ''}
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/favicon.ico?v=2" sizes="any">
<link rel="icon" href="/favicon.svg?v=2" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png?v=2">
<link rel="manifest" href="/site.webmanifest">
<meta name="theme-color" content="#07111f">
<script>(function(){{var d=document.documentElement,m=window.matchMedia&&matchMedia('(prefers-color-scheme: light)'),t;
try{{t=sessionStorage.getItem('theme');localStorage.removeItem('theme');}}catch(e){{}}
function set(v){{d.setAttribute('data-theme',v);var c=document.querySelector('meta[name="theme-color"]');if(c)c.content=v==='light'?'#0d1f3c':'#07111f';}}
set(t==='light'||t==='dark'?t:(m&&m.matches?'light':'dark'));
if(m&&m.addEventListener&&t!=='light'&&t!=='dark')m.addEventListener('change',function(e){{try{{if(sessionStorage.getItem('theme'))return;}}catch(x){{}}set(e.matches?'light':'dark');}});
window.__setTheme=function(v){{set(v);try{{sessionStorage.setItem('theme',v);}}catch(e){{}}}};}})();</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&family=Teko:wght@500;600&display=swap" rel="stylesheet">
{css}
<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>
{THUMB_JS}
</head>
<body>
{official_bar(lang_switch(path) if alternates else '')}
<header class="top"><div class="wrap"><div class="brand">
<a class="home" href="{U('/')}" aria-label="{e(site_name())}{L('(トップへ)', ' (home)')}"><img class="logo-img" src="/assets/logo.png" alt="JAPAN WRESTLING CHANNEL" width="145" height="54"><span class="logo-type"><span class="ac">ARCHIVE</span></span></a>
<nav class="topnav" aria-label="{L('メニュー', 'Menu')}">{nav_links(path)}</nav>
{header_search()}
</div></div></header>
"""


def footer(as_of):
    if i18n.en():
        return f"""<footer class="site-foot"><div class="wrap">
<p><a href="/en/events/">Tournaments</a> · <a href="/en/events/calendar/">Calendar</a> · <a href="/en/technique/">Technique videos</a> · <a href="/en/photos/">Photos</a> · <a href="/en/players/">Players</a> · <a href="/en/uww/">International videos</a> · <a href="/en/about/">About</a> · <a href="/en/faq/">FAQ</a> · <a href="/en/contact.html">Contact</a> · <a href="/en/privacy/">Privacy Policy</a> · <a href="/">日本語</a></p>
<p>The official archive of Japan Wrestling Channel. It organizes Japanese wrestling videos published on YouTube (Japan Wrestling Channel and others) by tournament. All videos play on YouTube. Video titles are shown as originally published, in Japanese.</p>
<p>Dates, venues and sources come from our tournament reference data. Videos not yet confirmed to belong to a specific edition are marked "Pending review". English names of tournaments and venues are our own translations.</p>
<p>Data updated: {e(fmt_date(as_of))}</p>
</div></footer>
</body>
</html>
"""
    return f"""<footer class="site-foot"><div class="wrap">
<p><a href="/events/">大会一覧</a>・<a href="/events/calendar/">大会カレンダー</a>・<a href="/technique/">技術動画</a>・<a href="/photos/">写真</a>・<a href="/players/">選手検索</a>・<a href="/uww/">国際大会</a>・<a href="/about/">運営者情報</a>・<a href="/faq/">よくある質問</a>・<a href="/contact.html">お問い合わせ</a>・<a href="/privacy/">プライバシーポリシー</a>・<a href="/en/" hreflang="en" lang="en">English</a></p>
<p>このサイトは Japan Wrestling Channel 公式の配信アーカイブです。Japan Wrestling Channel などの YouTube で公開されているレスリングの動画を、大会ごとに整理しています。動画はすべて YouTube で再生されます。</p>
<p>開催日・会場・出典は照合用の大会データに基づきます。動画と開催回の対応が確定していないものは「確認待ち」として区別しています。</p>
<p>データ更新:{e(fmt_date(as_of))}</p>
</div></footer>
</body>
</html>
"""


def breadcrumb_html(items):
    lis = []
    for i, (name, path) in enumerate(items):
        last = i == len(items) - 1
        lis.append(f'<li><span aria-current="page">{e(name)}</span></li>' if last or not path
                   else f'<li><a href="{e(U(path))}">{e(name)}</a></li>')
    return f'<nav class="crumbs" aria-label="{L("現在の位置", "Breadcrumb")}"><ol>{"".join(lis)}</ol></nav>'


def breadcrumb_ld(items):
    return {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, **({"item": SITE + U(p)} if p else {})}
        for i, (n, p) in enumerate(items)]}


def thumb(vid, w=320, h=180):
    return (f'<div class="thumb"><img src="https://i.ytimg.com/vi/{e(vid)}/mqdefault.jpg" alt="" width="{w}" height="{h}" '
            f'loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="thumbFail(this)"></div>')


def styles_text(st):
    return L("・".join(st), " / ".join(N(x) for x in st))


def video_row(v, show_basis=False):
    meta = []
    if v.get("ch"):
        meta.append(f'<span class="chlabel">{e(N(v["ch"]))}</span>')
    if v.get("dh"):
        meta.append(f'<span class="d">{e(fmt_date(v["dh"]))}</span>')
    if v.get("m"):
        meta.append(f'<span>{e(L(v["m"] + "マット", "Mat " + v["m"]))}</span>')
    if v.get("st"):
        meta.append(f'<span>{e(styles_text(v["st"]))}</span>')
    if v.get("du"):
        meta.append(f'<span class="tabnum">{e(dur(v["du"]))}</span>')
    meta.append(f'<span>{L("公開日", "Published")} {e(fmt_date(jst_date(v.get("p"))))}</span>')
    if v.get("vs") == "upcoming":
        meta.append(f'<span class="lk">{L("配信予定", "Scheduled stream")}</span>')
    elif v.get("vs") == "unavailable":
        meta.append(f'<span class="lk unmatched">{L("現在YouTubeで見られません", "Currently unavailable on YouTube")}</span>')
    ll = link_label()
    if v.get("l") in ll:
        meta.append(f'<span class="lk {e(v["l"])}">{e(ll[v["l"]])}</span>')
    basis = ""
    if show_basis and v.get("b"):
        tb = T(v["b"])
        basis = (f'<div class="basis">{L("根拠:", "Basis: ")}' + (f'{e(tb)} <span class="mt">auto-translated</span>' if tb
                 else f'<span{L("", " lang=" + chr(34) + "ja" + chr(34))}>{e(v["b"])}</span>') + '</div>')
    return (f'<li class="v"><a href="{e(yt(v["id"]))}" target="_blank" rel="noopener" tabindex="-1" aria-hidden="true">{thumb(v["id"])}</a>'
            f'<div><div class="vt"><a href="{e(yt(v["id"]))}" target="_blank" rel="noopener"{L("", " lang=" + chr(34) + "ja" + chr(34))}>{e(v["t"])}</a></div>'
            f'{tr_line(v["t"])}<div class="vm">{"".join(meta)}</div>{basis}</div></li>')


def tr_line(ja):
    """英語版:元の日本語タイトルの下に機械翻訳を添える"""
    t = T(ja)
    return f'<div class="vtr" lang="en">{e(t)} <span class="mt">auto-translated</span></div>' if t else ""


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
    if i18n.en():
        return ", ".join(f"{kind_label(k)}: {n}" for k, n in kind_counts(vids))
    return "・".join(f"{KIND_LABEL[k]}{n}本" for k, n in kind_counts(vids))


# ---------------------------------------------------------------- 開催回ページ

def photo_mark():
    t = L("写真あり", "Has photos")
    return f'<span class="pmark" role="img" aria-label="{t}" title="{t}">📷</span>'


def series_name(s):
    return N(s["name"])


def event_name(ev, s):
    # 英語版は開催回ごとの正式名ではなく、大会名の英語を使う
    return L(ev.get("official_name") or ev["name"], series_name(s))


# overrides.json の event_links の label の英語。ここにない label は en_names.csv の英語名を使う
LINK_LABELS_EN = {"大会公式サイト": "Official tournament website", "結果": "Results", "大会結果": "Results",
                  "結果(速報)": "Live results", "組み合わせ": "Brackets", "要項": "Entry guidelines"}
JWF_COMPETITION = re.compile(r"^https://www\.japan-wrestling\.jp/competition/\d{4}/\d+")


def event_page(ev, ctx):
    S, slugs, by_event, cand_by_event = ctx["S"], ctx["slugs"], ctx["by_event"], ctx["cand"]
    s = S.get(ev["series"], {"id": ev["series"], "name": ev["name"], "master": False})
    path = f"/events/{slugs[ev['id']]}/"
    spath = f"/events/{s['id']}/"
    name = event_name(ev, s)
    vids = by_event.get(ev["id"], [])
    uniq = {v["id"]: v for v in vids}
    vids = list(uniq.values())
    matches = [v for v in vids if v.get("k") == "match"]
    first = (matches or vids or [None])[0]
    counts = counts_text(vids)
    status = ev.get("status")
    venue = N(ev.get("venue"))
    others = sorted({N(v["ch"]) for v in vids if v.get("ch")})
    n_main = sum(1 for v in vids if not v.get("ch"))
    rng = fmt_range(ev.get("start"), ev.get("end")) if ev.get("start") else ""

    lead_parts = []
    if i18n.en():
        if status == "cancelled":
            lead_parts.append(f"The {ev['year']} {series_name(s)} is recorded as cancelled.")
        elif ev.get("start"):
            lead_parts.append(f"Video publish dates: {rng} (official dates not yet confirmed)." if ev.get("derived")
                              else f"{'Scheduled for' if status == 'scheduled' else 'Held on'} {rng}{(' at ' + venue) if venue else ''}.")
        src = "Japan Wrestling Channel streams" if not others else "YouTube streams and videos"
        if vids:
            lead_parts.append(f" {i18n.plural(len(vids), 'video')} from {src} ({counts}){', organized by day' if matches else ''}.")
        else:
            lead_parts.append(" No videos for this edition yet. See the photos below.")
        if others:
            lead_parts.append(f" Includes {n_main} Japan Wrestling Channel streams plus videos from {', '.join(others)}." if n_main
                              else f" All videos are published by {', '.join(others)}.")
    else:
        if status == "cancelled":
            lead_parts.append(f"{ev['year']}年の{s['name']}は中止の記録があります。")
        elif ev.get("start"):
            verb = "開催予定" if status == "scheduled" else "開催"
            lead_parts.append(f"{rng}{('、' + ev['venue'] + 'で') if ev.get('venue') else 'に'}{verb}。"
                              if not ev.get("derived") else f"動画の配信日は{rng}です(公式の開催日は確認中)。")
        src = "Japan Wrestling Channel の配信" if not others else "YouTubeの配信・動画"
        if vids:
            lead_parts.append(f"{src}{len(vids)}本({counts})を{'日程ごとに' if matches else ''}掲載しています。")
        else:
            lead_parts.append("この開催回の配信動画はまだありません。下の「写真」から写真を見られます。")
        if others:
            lead_parts.append(f"Japan Wrestling Channel の配信{n_main}本のほか、{'、'.join(others)}の動画を含みます。" if n_main
                              else f"いずれも{'、'.join(others)}が公開している動画です。")
    lead = "".join(lead_parts).strip()

    if i18n.en():
        title = f"{name} {ev['year']} – {i18n.plural(len(vids), 'video')} | {site_name()}"
        desc = f"{name} ({ev['year']}): {i18n.plural(len(vids), 'stream/video', 'streams/videos')}. {counts}." + (
            f" Held {rng}" if ev.get("start") and not ev.get("derived") else "") + (
            f" at {venue}." if venue and not ev.get("derived") else "")
        if not vids:
            title = f"{name} {ev['year']} – Photos | {site_name()}"
            desc = f"{name} ({ev['year']}): photos." + (f" Held {rng}" if ev.get("start") else "") + (f" at {venue}." if venue else "")
    else:
        title = f"{name} {ev['year']}年 配信動画一覧({len(vids)}本)|{SITE_NAME}"
        desc = f"{name}({ev['year']}年)の配信・動画{len(vids)}本。{counts}。" + (
            f"{rng}開催" if ev.get("start") and not ev.get("derived") else "") + (
            f"、会場は{ev['venue']}。" if ev.get("venue") and not ev.get("derived") else "。")
        if not vids:
            title = f"{name} {ev['year']}年 写真|{SITE_NAME}"
            desc = f"{name}({ev['year']}年)の写真。" + (f"{rng}開催" if ev.get("start") else "") + (f"、会場は{ev['venue']}。" if ev.get("venue") else "。")
    dated = re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", slugs[ev['id']].split('/')[-1])
    crumbs = [(L("トップ", "Home"), "/"), (L("大会一覧", "Tournaments"), "/events/"), (series_name(s), spath),
              (year_label(ev["year"]) + ((L("(", " (") + (fmt_date(ev['start'])[5:] if not i18n.en() else fmt_date(ev['start']).rsplit(',', 1)[0]) + ")") if dated else ""), None)]

    ld = [breadcrumb_ld(crumbs)]
    if not ev.get("derived") and ev.get("start"):
        se = {"@type": "SportsEvent", "name": f"{name} {ev['year']}", "sport": "Wrestling", "url": SITE + U(path),
              "startDate": ev["start"], "endDate": ev.get("end") or ev["start"],
              "eventStatus": "https://schema.org/" + SCHEMA_STATUS.get(status, "EventScheduled")}
        if venue:
            se["location"] = {"@type": "Place", "name": venue}
        ld.append(se)
    jsonld = {"@context": "https://schema.org", "@graph": ld}

    h = head(title, desc, path, f"https://i.ytimg.com/vi/{first['id']}/hqdefault.jpg" if first else "", jsonld, ctx["css"])
    h += '<main class="wrap page">' + breadcrumb_html(crumbs)
    sl = status_label()
    badge = f'<span class="badge {e(status)}">{e(sl[status])}</span>' if status in sl else ""
    h += f'<h1>{e(name)} <span class="yr-h">{e(year_label(ev["year"]))}</span>{badge}</h1>'
    h += f'<p class="lead">{e(lead)}</p>'

    h += '<dl class="facts">'
    if ev.get("sessions"):
        ss = sorted(ev["sessions"], key=lambda x: x.get("start_date", ""))
        h += f"<dt>{L('日程', 'Schedule')}</dt><dd><ul class=\"sessions\">" + "".join(
            f"<li>{e(fmt_range(x.get('start_date'), x.get('end_date')))} {e(N(x.get('label', '')))}"
            f"{(L('(', ' (') + e(N(x['venue'])) + ')') if x.get('venue') else ''}</li>" for x in ss) + "</ul></dd>"
    else:
        when = L("配信日", "Stream dates") if ev.get("derived") else L("開催日", "Dates")
        h += f"<dt>{when}</dt><dd>{e(fmt_range(ev.get('start'), ev.get('end')))}{L('(予定)', ' (scheduled)') if status == 'scheduled' else ''}</dd>"
        if venue:
            h += f"<dt>{L('会場', 'Venue')}</dt><dd>{e(venue)}</dd>"
    if ev.get("fy_label"):
        h += f"<dt>{L('年度', 'Fiscal year')}</dt><dd>{e(N(ev['fy_label']))}</dd>"
    h += f"<dt>{L('収録', 'Videos')}</dt><dd>{e(counts or L('配信動画なし', 'No videos yet'))}</dd>"
    if ev.get("group"):
        sib = [x for x in ctx["all_events"] if x.get("group") == ev["group"] and x["id"] != ev["id"]]
        if sib:
            def sib_name(x):
                return N(S.get(x["series"], {}).get("name") or x["name"])
            h += f"<dt>{L('同時開催', 'Held together with')}</dt><dd>" + L("、", ", ").join(
                (f'<a href="{U("/events/" + slugs[x["id"]] + "/")}">{e(sib_name(x))}</a>' if x["id"] in slugs
                 else e(sib_name(x))) for x in sib) + "</dd>"
    h += "</dl>"
    # 大会の公式サイト・結果など(overrides.json の event_links)と、日本レスリング協会の大会ページ(結果が載る)
    links = [(x["url"], (LINK_LABELS_EN[x["label"]] if x["label"] in LINK_LABELS_EN else N(x["label"])) if i18n.en() else x["label"])
             for x in ev.get("links") or []]
    jwf = next((x["url"] for x in ev.get("sources") or [] if JWF_COMPETITION.match(x.get("url") or "")), "")
    if jwf and jwf not in {u for u, _ in links}:
        import calendar_page
        done = (ev.get("end") or ev.get("start") or "9999") < calendar_page.today_jst() and status != "cancelled"
        links.append((jwf, L("結果を見る(日本レスリング協会)", "Results (Japan Wrestling Federation)") if done
                      else L("大会情報(日本レスリング協会)", "Tournament info (Japan Wrestling Federation)")))
    if links:
        h += '<p class="elinks">' + "".join(
            f'<a class="elink" href="{e(u)}" target="_blank" rel="noopener">{e(t)} ↗</a>' for u, t in links) + "</p>"
    # これから開催される大会は「カレンダーに追加」
    import calendar_page
    if (ev.get("start") and not ev.get("derived") and status not in ("cancelled", "postponed")
            and (ev.get("end") or ev["start"]) >= calendar_page.today_jst()):
        gc, ic = calendar_page.add_to_calendar(ev["id"], f"{name} {year_label(ev['year'])}" if i18n.en() else name,
                                               ev["start"][:10], (ev.get("end") or ev["start"])[:10], venue or "", U(path), ctx)
        h += '<p class="elinks">' + calendar_page.add_buttons_html(gc, ic, e) + "</p>"

    # 開催年の年表(ほかの年へのリンク)
    h += year_rail(s, ev["id"], ctx)
    h += ctx["gallery"](path, f"{name} {year_label(ev['year'])}")

    # 動画(試合配信は日付→マット順)
    by_day = defaultdict(list)
    for v in matches:
        by_day[v.get("dh") or ""].append(v)
    for day in sorted(by_day):
        lst = sorted(by_day[day], key=lambda v: (v.get("m") or "~", v.get("p") or ""))
        sess = next((x for x in ev.get("sessions") or [] if x.get("start_date", "") <= day <= x.get("end_date", "")), None) if day else None
        h += vgroup(L(f"試合配信 {fmt_date(day)}", f"Match streams – {fmt_date(day)}") if day else L("試合配信(競技日を確認中)", "Match streams (day unconfirmed)"),
                    f"{(N(sess['label']) + L('、', ', ')) if sess else ''}{n_videos(len(lst))}", lst, gid=f"d-{day}" if day else "d-x")
    for k in KIND_ORDER[1:]:
        lst = sorted([v for v in vids if (v.get("k") or "other") == k], key=lambda v: v.get("p") or "", reverse=True)
        h += vgroup(kind_label(k), n_videos(len(lst)), lst, gid=k)
    cands = [v for v in cand_by_event.get(ev["id"], []) if v["id"] not in uniq]
    if cands:
        h += ('<details class="more-box"><summary>' + L(f"この開催回の可能性がある動画(確認待ち {len(cands)}本)",
                                                        f"Videos that may belong to this edition (pending review: {len(cands)})") + '</summary>'
              '<p class="hint">' + L("大会名や年が曖昧なため、まだこの開催回と確定していない動画です。根拠を表示しています。",
                                     "The tournament name or year in these titles is ambiguous, so they are not yet confirmed for this edition. The basis is shown.") + '</p>'
              + vgroup(L("確認待ち", "Pending review"), n_videos(len(cands)), cands, show_basis=True) + '</details>')

    import players
    import sys
    h += players.winners_html(ev, ctx, sys.modules[__name__])
    h += info_details(ev)
    h += f'<p class="tosearch-line"><a href="{U("/")}#s={e(s["id"])}&amp;e={e(ev["id"])}">{L("スタイルなどで絞り込む(検索ページで開く)", "Filter by style and more (open in search)")}</a></p>'
    h += "</main>" + footer(ctx["as_of"])
    return path, h


def source_label(src):
    t = src.get("type") or "出典"
    u = src.get("url", "")
    if "japan-wrestling.jp" in u and "報告書" not in t and "報告" not in t:
        t = "日本協会の大会ページ"
    return N(t) if t != "出典" else L("出典", "Source")


def source_url_text(url):
    """出典のリンクの横に出すアドレス。英語版はドメインだけにする(日本語のファイル名を英語版に出さないため。#74)"""
    if i18n.en():
        return urllib.parse.urlsplit(url).netloc or re.sub("^https?://", "", url)
    return re.sub("^https?://", "", url)


def info_details(ev):
    rows = []
    if ev.get("evidence"):
        rows.append(f"<dt>{L('記録の種類', 'Record type')}</dt><dd>{e(N(ev['evidence']))}{(L('(', ' (') + e(N(ev['jwf_relationship'])) + ')') if ev.get('jwf_relationship') else ''}</dd>")
    if ev.get("sources"):
        rows.append(f"<dt>{L('出典', 'Sources')}</dt><dd><ul class=\"sources\">" + "".join(
            f'<li><a href="{e(x["url"])}" target="_blank" rel="noopener">{e(source_label(x))}</a> <span class="url">{e(source_url_text(x["url"]))}</span></li>'
            for x in ev["sources"]) + "</ul></dd>")
    notes = list(ev.get("notes") or [])
    for x in ev.get("schedule_history") or []:
        if x.get("source_text"):
            notes.append("日程の経緯:" + x["source_text"])
    if notes:
        def note_html(n):
            # 英語版は機械翻訳を出し、元の日本語を小さく添える(訳が無ければ日本語だけ)
            if not i18n.en():
                return f"<p>{e(n)}</p>"
            body = n[len("日程の経緯:"):] if n.startswith("日程の経緯:") else n
            t = T(body)
            head_ = "Schedule history: " if body is not n else ""
            if t:
                return f'<p>{head_}{e(t)} <span class="mt">auto-translated</span></p><p class="orig" lang="ja">{e(n)}</p>'
            return f'<p lang="ja">{e(n)}</p>'
        rows.append(f"<dt>{L('メモ', 'Notes')}</dt><dd>" + "".join(note_html(n) for n in notes) + "</dd>")
    if ev.get("derived"):
        rows.append(f"<dt>{L('開催情報', 'Event details')}</dt><dd>" + L("公式の開催日・会場を確認中です。表示している日付は動画の配信日です。",
                    "Official dates and venue are being confirmed. The dates shown are the video stream dates.") + "</dd>")
    if not rows:
        return ""
    return f'<details class="more-box info"><summary>{L("大会情報・出典を詳しく見る", "Event details and sources")}</summary><dl class="facts">' + "".join(rows) + "</dl></details>"


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
        n = L("中止", "Cancelled") if x.get("status") == "cancelled" else L(f"{x.get('n', 0)}本", str(x.get("n", 0)))
        inner = f'<span class="dot" aria-hidden="true"></span><span class="y">{label}</span><span class="n">{n}</span>'
        sr = L(f"{x['year']}年、{n}", f"{x['year']}, {n if x.get('status') == 'cancelled' else i18n.plural(x.get('n', 0), 'video')}")
        if x["id"] == current_id:
            items.append(f'<span class="yr {cls}" aria-current="page" aria-label="{e(sr)}{L("(表示中)", " (current)")}">{inner}</span>')
        elif x["id"] in ctx["slugs"]:
            items.append(f'<a class="yr {cls}" href="{U("/events/" + ctx["slugs"][x["id"]] + "/")}" aria-label="{e(sr)}">{inner}</a>')
        else:
            items.append(f'<span class="yr {cls} off" aria-label="{e(sr)}{L("(動画なし)", " (no videos)")}">{inner}</span>')
    return (f'<nav class="rail" aria-label="{L("開催年", "Years")}">{"".join(items)}</nav>'
            '<script>(function(){var r=document.currentScript.previousElementSibling,c=r.querySelector("[aria-current]");'
            'if(c)r.scrollLeft=Math.max(0,c.offsetLeft-r.clientWidth/2+c.offsetWidth/2);})();</script>')


# ---------------------------------------------------------------- 大会ページ

AUDIENCE = [("大学", "大学生", "university students"), ("高校", "高校生", "high school students"), ("中学", "中学生", "junior high school students"),
            ("少年少女", "小学生などの子ども", "children"), ("社会人", "社会人", "working adults"), ("マスターズ", "マスターズ(ベテラン)の選手", "masters (veteran) wrestlers"),
            ("年代別", "", "")]
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def series_summary(s, evs, name):
    """大会ページの最初に置く1〜2文の要約(Google や AI が引用しやすい形)。
    大会データで確かめられることだけを書く:対象(大会の区分)と、例年の開催月(3回以上・6割以上が同じ月のときだけ)"""
    if not s.get("master"):
        return ""
    if s.get("scope") == "海外":
        first = L(f"{name}は、海外で開かれる国際大会です。", f"The {name} is an international tournament held outside Japan.")
    else:
        groups = s.get("groups") or []
        aud = next((a for g, *a in AUDIENCE if groups == [g]), None)
        if not aud:
            return ""  # 区分が複数(例:一般・高校生)や対象外のときは書かない
        if groups == ["年代別"]:
            ages = sorted({u for c in s.get("categories") or [] for u in re.findall(r"U\d+", c)}, key=lambda u: -int(u[1:]))
            if not ages:
                return ""
            aud = (f"年代別({'・'.join(ages)})の選手", f"{', '.join(ages)} age-group wrestlers")
        first = L(f"{name}は、{aud[0]}が出場する国内のレスリング大会です。", f"The {name} is a Japanese wrestling tournament for {aud[1]}.")
    months = [int(x["start"][5:7]) for x in evs if x.get("start") and not x.get("derived") and x.get("status") in ("held", "scheduled")]
    if len(months) >= 3:
        m, c = Counter(months).most_common(1)[0]
        if c / len(months) >= 0.6:
            first += L(f"例年{m}月ごろに開かれています。", f" It is usually held in {MONTHS_EN[m - 1]}.")
    return first

def series_page(s, ctx):
    path = f"/events/{s['id']}/"
    evs = ctx["events_by_series"].get(s["id"], [])
    with_v = [x for x in evs if x.get("n")]
    years = [x["year"] for x in with_v]
    span = year_span(years)
    loose = sorted(ctx["loose_by_series"].get(s["id"], []), key=lambda v: v.get("p") or "", reverse=True)
    total = s.get("n", 0)
    name = series_name(s)
    first_v = None
    for x in reversed(with_v):
        vs = ctx["by_event"].get(x["id"], [])
        first_v = next((v for v in vs if v.get("k") == "match"), vs[0] if vs else None)
        if first_v:
            break

    alias = [a for a in (s.get("aliases") or []) if a != s["name"]]
    if i18n.en():
        title = f"{name} – Video Archive ({span}, {i18n.plural(total, 'video')}) | {site_name()}"
        desc = f"{i18n.plural(total, 'stream/video', 'streams/videos')} from the {name}, organized by year. {span + ', ' if span else ''}{i18n.plural(len(with_v), 'edition')}." + (
            f" Japanese name: {s['name']}." if name != s["name"] else "")
    else:
        title = f"{s['name']} 配信動画アーカイブ({span}・{total}本)|{SITE_NAME}"
        desc = f"{s['name']}の配信動画{total}本を開催年ごとに掲載。{span + '、' if span else ''}{len(with_v)}開催回。" + (f"別名:{'、'.join(alias[:4])}。" if alias else "")
    crumbs = [(L("トップ", "Home"), "/"), (L("大会一覧", "Tournaments"), "/events/"), (name, None)]
    jsonld = {"@context": "https://schema.org", "@graph": [breadcrumb_ld(crumbs), {
        "@type": "CollectionPage", "name": L(f"{s['name']} 配信動画アーカイブ", f"{name} video archive"), "url": SITE + U(path),
        "hasPart": [{"@type": "WebPage", "name": f"{name} {year_label(x['year'])}", "url": SITE + U(f"/events/{ctx['slugs'][x['id']]}/")}
                    for x in with_v if x["id"] in ctx["slugs"]]}]}

    h = head(title, desc, path, f"https://i.ytimg.com/vi/{first_v['id']}/hqdefault.jpg" if first_v else "", jsonld, ctx["css"])
    h += '<main class="wrap page">' + breadcrumb_html(crumbs)
    h += f"<h1>{e(name)}</h1>"
    if i18n.en():
        lead = f"{i18n.plural(total, 'stream/video', 'streams/videos')} published on YouTube, organized by year." + (
            f" Videos are available for {i18n.plural(len(with_v), 'edition')} ({span})." if with_v else "")
        if not s.get("master"):
            lead += " Official dates and venues for this tournament are being confirmed."
    else:
        lead = f"YouTubeで公開されている配信・動画{total}本を開催年ごとに整理しています。" + (f"動画があるのは{span}の{len(with_v)}開催回です。" if with_v else "")
        if not s.get("master"):
            lead += "この大会の公式の開催日・会場は確認中です。"
    summary = series_summary(s, evs, name)
    if summary:
        lead = summary + L("", " ") + lead
    h += f'<p class="lead">{e(lead)}</p>'
    if i18n.en():
        if name != s["name"]:
            h += f'<p class="aliases">Japanese name: <span lang="ja">{e(s["name"])}</span></p>'
    elif alias:
        h += f'<p class="aliases">この名前でも探せます:{e("、".join(alias))}</p>'

    import champions
    h += champions.link_html(s, ctx)
    sl = status_label()
    h += f'<section class="section"><h2>{L("開催年から選ぶ", "Choose a year")}</h2><ol class="occ">'
    for x in reversed(evs):
        badge = f'<span class="badge {e(x.get("status"))}">{e(sl[x["status"]])}</span>' if x.get("status") in sl else ""
        when = fmt_range(x.get("start"), x.get("end")) if x.get("start") else L("日付未確認", "Date TBC")
        cnt = (L("<b class=num>" + str(x.get("n")) + "</b>本", "<b class=num>" + str(x.get("n")) + "</b> " + ("video" if x.get("n") == 1 else "videos"))
               if x.get("n") else L("動画なし", "No videos"))
        if x["id"] in ctx["slugs"] and f'/events/{ctx["slugs"][x["id"]]}/' in ctx["photo_paths"]:
            badge += photo_mark()
        body = (f'<span class="oy">{x["year"]}</span><span class="ob"><span class="od">{e(when)}{badge}</span>'
                f'<span class="ov">{e(N(x.get("venue")) or "")}</span></span><span class="on">{cnt}</span>')
        if x["id"] in ctx["slugs"]:
            h += f'<li><a href="{U("/events/" + ctx["slugs"][x["id"]] + "/")}">{body}</a></li>'
        else:
            h += f'<li class="off"><div>{body}</div></li>'
    h += "</ol></section>"
    h += ctx["gallery"](path, name)
    if loose:
        h += vgroup(L("開催回を確認中の動画", "Videos with unconfirmed edition"),
                    L(f"この大会の動画ですが、どの年の開催回か特定できていません({len(loose)}本)",
                      f"Videos from this tournament whose year is not yet identified ({len(loose)})"), loose, show_basis=True)
    h += f'<p class="tosearch-line"><a href="{U("/")}#s={e(s["id"])}">{L("スタイルなどで絞り込む(検索ページで開く)", "Filter by style and more (open in search)")}</a></p>'
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
        meta.append(f'<a class="catlink" href="{U("/technique/" + v["cat"] + "/")}">{e(N(cat_names.get(v["cat"], "")))}</a>')
    if show_channel:
        meta.append(f'<a class="ch" href="{U("/technique/" + v["_chslug"] + "/")}">{e(N(v["_ch"]))}</a>')
    if v.get("du"):
        meta.append(f'<span class="tabnum">{e(dur(v["du"]))}</span>')
    meta.append(f'<span>{L("公開日", "Published")} {e(fmt_date(jst_date(v.get("p"))))}</span>')
    return (f'<li class="v"><a href="{e(yt(v["id"]))}" target="_blank" rel="noopener" tabindex="-1" aria-hidden="true">{thumb(v["id"])}</a>'
            f'<div><div class="vt"><a href="{e(yt(v["id"]))}" target="_blank" rel="noopener"{L("", " lang=" + chr(34) + "ja" + chr(34))}>{e(v["t"])}</a></div>'
            f'{tr_line(v["t"])}<div class="vm">{"".join(meta)}</div></div></li>')


def tech_list(title, sub, vids, cat_names, show_channel=True, gid=""):
    if not vids:
        return ""
    return (f'<section class="vgroup"{f" id={chr(34)}{gid}{chr(34)}" if gid else ""}><h2 class="vh">{e(title)}<small>{e(sub)}</small></h2>'
            f'<ul class="vlist">{"".join(tech_video_row(v, cat_names, show_channel) for v in vids)}</ul></section>')


def cat_nav(cats, counts, current=None, base="/technique/"):
    items = [f'<a href="{U("/technique/")}"{" aria-current=" + chr(34) + "page" + chr(34) if current is None and base == "/technique/" else ""}>{L("すべて", "All")}<b>{sum(counts.values())}</b></a>']
    for c in cats:
        n = counts.get(c["slug"], 0)
        if not n:
            continue
        cur = ' aria-current="page"' if current == c["slug"] else ""
        items.append(f'<a href="{U("/technique/" + c["slug"] + "/")}"{cur}>{e(N(c["name"]))}<b>{n}</b></a>')
    return f'<nav class="catnav" aria-label="{L("区分", "Categories")}">{"".join(items)}</nav>'


def tech_pages(tech, cats, shown, ctx):
    cat_names = {c["slug"]: c["name"] for c in cats}
    counts = defaultdict(int)
    for v in shown:
        counts[v["cat"]] += 1
    channels = tech.get("channels", [])
    pages = []
    home, tech_t = L("トップ", "Home"), L("技術動画", "Technique videos")

    # 技術動画トップ
    path = "/technique/"
    crumbs = [(home, "/"), (tech_t, None)]
    title = f"{tech_t}{L('|', ' | ')}{site_name()}"
    cat_list = [N(c["name"]) for c in cats if counts.get(c["slug"])]
    desc = L("レスリングクラブが公開している技術・トレーニング動画を、" + "・".join(cat_list) + f"などの区分で探せます。{len(shown)}本掲載。",
             f"Wrestling technique and training videos published by clubs, organized by category ({', '.join(cat_list)}). {i18n.plural(len(shown), 'video')}.")
    jsonld = {"@context": "https://schema.org", "@graph": [breadcrumb_ld(crumbs), {
        "@type": "CollectionPage", "name": tech_t, "url": SITE + U(path),
        "hasPart": [{"@type": "WebPage", "name": N(c["name"]), "url": SITE + U(f"/technique/{c['slug']}/")} for c in cats if counts.get(c["slug"])]}]}
    h = head(title, desc, path, f"https://i.ytimg.com/vi/{shown[0]['id']}/hqdefault.jpg" if shown else "", jsonld, ctx["css"])
    h += '<main class="wrap page">' + breadcrumb_html(crumbs) + f"<h1>{e(tech_t)}</h1>"
    h += '<p class="lead">' + e(L(f"レスリングクラブが公開している、技術やトレーニング方法を紹介する動画です。区分を選ぶと、その技術の動画だけを見られます。現在{len(shown)}本を掲載しています。",
                                  f"Videos from wrestling clubs that teach techniques and training methods. Choose a category to see only those videos. {i18n.plural(len(shown), 'video')} listed. Titles are in Japanese.")) + '</p>'
    h += cat_nav(cats, counts)
    h += '<ul class="catcards">' + "".join(
        f'<li><a href="{U("/technique/" + c["slug"] + "/")}"><span class="cn">{e(N(c["name"]))}</span><span class="cd">{e(N(c.get("description", "")))}</span>'
        f'<span class="cc"><b class="num">{counts[c["slug"]]}</b>{L("本", " videos")}</span></a></li>'
        for c in cats if counts.get(c["slug"])) + "</ul>"
    h += tech_list(L("新着", "Latest"), L("公開日の新しい順", "Newest first"), shown[:30], cat_names, gid="new")
    if channels:
        h += f'<section class="section"><h2>{L("チャンネル", "Channels")}</h2><ul class="chlist">' + "".join(
            f'<li><a href="{U("/technique/" + c["slug"] + "/")}"><span class="cn">{e(N(c["name"]))}</span>'
            f'<span class="cm">{e(N(c.get("note", "")))}<b class="num">{sum(1 for v in shown if v["_chslug"] == c["slug"])}</b>{L("本", " videos")}</span></a></li>'
            for c in channels) + "</ul></section>"
    h += "</main>" + footer(ctx["as_of"])
    pages.append((path, h, shown))

    # 区分ごとのページ
    for c in cats:
        vids = [v for v in shown if v["cat"] == c["slug"]]
        if not vids:
            continue
        path = f"/technique/{c['slug']}/"
        cn, cd = N(c["name"]), N(c.get("description", ""))
        crumbs = [(home, "/"), (tech_t, "/technique/"), (cn, None)]
        title = L(f"{cn}の技術動画({len(vids)}本)|{SITE_NAME}", f"{cn} – Technique Videos ({len(vids)}) | {site_name()}")
        desc = L(f"レスリングの{cn}の技術・練習動画{len(vids)}本。{cd}。", f"{i18n.plural(len(vids), 'wrestling technique video')}: {cn}. {cd}.")
        jsonld = {"@context": "https://schema.org", "@graph": [breadcrumb_ld(crumbs),
                  {"@type": "CollectionPage", "name": L(f"{cn}の技術動画", f"{cn} technique videos"), "url": SITE + U(path)}]}
        h = head(title, desc, path, f"https://i.ytimg.com/vi/{vids[0]['id']}/hqdefault.jpg", jsonld, ctx["css"])
        h += '<main class="wrap page">' + breadcrumb_html(crumbs) + f"<h1>{e(cn)}</h1>"
        h += '<p class="lead">' + e(L(f"{cd}。レスリングクラブが公開している動画{len(vids)}本を、公開日の新しい順に並べています。",
                                      f"{cd}. {i18n.plural(len(vids), 'video')} published by wrestling clubs, newest first.")) + '</p>'
        h += cat_nav(cats, counts, current=c["slug"])
        h += tech_list(cn, n_videos(len(vids)), vids, cat_names, gid="list")
        h += "</main>" + footer(ctx["as_of"])
        pages.append((path, h, vids))

    # チャンネルごとのページ(区分ごとに見出しを分ける)
    for ch in channels:
        vids = [v for v in shown if v["_chslug"] == ch["slug"]]
        path = f"/technique/{ch['slug']}/"
        chn, note = N(ch["name"]), N(ch.get("note", ""))
        crumbs = [(home, "/"), (tech_t, "/technique/"), (chn, None)]
        title = L(f"{chn} 技術動画一覧({len(vids)}本)|{SITE_NAME}", f"{chn} – Technique Videos ({len(vids)}) | {site_name()}")
        desc = L(f"{chn}が公開している技術・トレーニング動画{len(vids)}本を区分ごとに掲載。" + (f"{note}。" if note else ""),
                 f"{i18n.plural(len(vids), 'technique and training video')} published by {chn}, by category." + (f" {note}." if note else ""))
        jsonld = {"@context": "https://schema.org", "@graph": [breadcrumb_ld(crumbs)]}
        h = head(title, desc, path, f"https://i.ytimg.com/vi/{vids[0]['id']}/hqdefault.jpg" if vids else "", jsonld, ctx["css"])
        h += '<main class="wrap page">' + breadcrumb_html(crumbs) + f"<h1>{e(chn)}</h1>"
        if note:
            h += '<p class="lead">' + e(L(f"{note}。技術・トレーニング動画{len(vids)}本を区分ごとに並べています。",
                                          f"{note}. {i18n.plural(len(vids), 'technique and training video')}, by category.")) + '</p>'
        ch_counts = defaultdict(int)
        for v in vids:
            ch_counts[v["cat"]] += 1
        jump = [f'<a href="#{e(c["slug"])}">{e(N(c["name"]))}<b>{ch_counts[c["slug"]]}</b></a>' for c in cats if ch_counts.get(c["slug"])]
        if jump:
            h += f'<nav class="catnav" aria-label="{L("このページ内の区分", "Categories on this page")}">{"".join(jump)}</nav>'
        for c in cats:
            lst = [v for v in vids if v["cat"] == c["slug"]]
            h += tech_list(N(c["name"]), n_videos(len(lst)), lst, cat_names, show_channel=False, gid=c["slug"])
        if not vids:
            h += f'<p class="empty">{L("このチャンネルの動画はまだ区分けされていません。", "Videos from this channel have not been categorized yet.")}</p>'
        h += "</main>" + footer(ctx["as_of"])
        pages.append((path, h, vids))

    slugs_seen = [p for p, _, _ in pages]
    assert len(slugs_seen) == len(set(slugs_seen)), "技術動画の区分とチャンネルのURLが重なっています(tech_categories.json と tech_channels.json の slug を確認してください)"
    return [(p, h, max((jst_date(v.get("p")) for v in vs), default=ctx["as_of"])) for p, h, vs in pages]


# ---------------------------------------------------------------- 大会一覧・404

def index_page(ctx, series_list):
    path = "/events/"
    crumbs = [(L("トップ", "Home"), "/"), (L("大会一覧", "Tournaments"), None)]
    total = sum(x.get("n", 0) for x in series_list)
    title = L(f"大会一覧({len(series_list)}大会・{total}本)|{SITE_NAME}", f"Tournaments ({len(series_list)} tournaments, {total} videos) | {site_name()}")
    desc = L(f"Japan Wrestling Channel で配信されたレスリング大会{len(series_list)}大会の一覧。天皇杯全日本選手権、明治杯、インカレ、インターハイなどの配信を開催年ごとに探せます。",
             f"{len(series_list)} Japanese wrestling tournaments streamed by Japan Wrestling Channel and others, including the Emperor's Cup, Meiji Cup, Inter-College and Inter-High. Browse streams by year.")
    jsonld = {"@context": "https://schema.org", "@graph": [breadcrumb_ld(crumbs), {
        "@type": "CollectionPage", "name": L("大会一覧", "Tournaments"), "url": SITE + U(path),
        "hasPart": [{"@type": "WebPage", "name": N(x["name"]), "url": SITE + U(f"/events/{x['id']}/")} for x in series_list]}]}
    h = head(title, desc, path, "", jsonld, ctx["css"])
    h += '<main class="wrap page">' + breadcrumb_html(crumbs) + f"<h1>{L('大会一覧', 'Tournaments')}</h1>"
    h += '<p class="lead">' + e(L(f"配信動画のある{len(series_list)}大会です。開催日の新しい順に並んでいます。スタイルや開催年での絞り込みは検索ページで行えます。",
                                  f"{len(series_list)} tournaments with videos, most recent first. Use the search page to filter by style or year.")) + '</p>'
    h += '<ol class="occ slist-static">'
    for x in series_list:
        evs = [v for v in ctx["events_by_series"].get(x["id"], []) if v.get("n")]
        span = year_span([v["year"] for v in evs], L("開催年を確認中", "Years TBC"))
        tags = "".join(f'<span class="tag">{e(N(g))}</span>' for g in x.get("groups") or [])
        if x.get("scope") == "海外":
            tags += f'<span class="tag">{L("海外", "Overseas")}</span>'
        has_photo = f'/events/{x["id"]}/' in ctx["photo_paths"] or any(
            f'/events/{ctx["slugs"][v["id"]]}/' in ctx["photo_paths"] for v in ctx["events_by_series"].get(x["id"], []) if v["id"] in ctx["slugs"])
        h += (f'<li><a href="{U("/events/" + x["id"] + "/")}"><span class="ob"><span class="od sname">{e(N(x["name"]))}{photo_mark() if has_photo else ""}</span>'
              f'<span class="ov">{e(span)} {tags}</span></span><span class="on"><b class="num">{x.get("n", 0)}</b>{L("本", " videos")}</span></a></li>')
    h += "</ol></main>" + footer(ctx["as_of"])
    return path, h


CONTACT_EMAIL = "kitamura@japanwrestlingchannel.com"
# Formspree に登録したら発行された ID(例: xabcdefg)をここに入れる。空なら送信時にメールアプリが開く
FORMSPREE_ID = ""


def contact_page(ctx):
    h = head(L(f"お問い合わせ|{SITE_NAME}", f"Contact | {site_name()}"),
             L("レスリング配信アーカイブへのお問い合わせページです。動画の掲載・非表示のご依頼、掲載内容の誤り、サイトの不具合、お仕事のご相談はこちらから。",
               "Contact the Japan Wrestling Archive: requests to list or hide videos, corrections, bug reports and business inquiries."),
             "/contact.html", "",
             {"@context": "https://schema.org", "@type": "ContactPage", "name": L("お問い合わせ", "Contact"),
              "url": SITE + U("/contact.html")}, ctx["css"])
    body = L(CONTACT_BODY, CONTACT_BODY_EN).replace("__EMAIL__", CONTACT_EMAIL).replace("__FORMSPREE_ID__", FORMSPREE_ID)
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
<option value="写真の掲載・取り下げについて" data-k="photo">写真の掲載・取り下げについて</option>
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
  // 写真ページの「取り下げのご依頼」から来たときは、種類と対象ページを入れておく
  try{ var q = new URLSearchParams(location.search), o = form.kind.querySelector('option[data-k="' + q.get("kind") + '"]');
    if (o) { o.selected = true; var pg = q.get("page"); if (pg && /^\/[\w\-\/%.\u3040-\u30ff\u4e00-\u9fff]*$/.test(pg) && !form.message.value) form.message.value = "対象のページ: " + location.origin + pg + "\n"; } }catch(x){}
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

CONTACT_BODY_EN = r"""<main class="wrap page contact">
<nav class="crumbs" aria-label="Breadcrumb"><ol><li><a href="/en/">Home</a></li><li>Contact</li></ol></nav>
<h1>Contact</h1>
<p class="lead">Requests to list or hide videos, corrections, bug reports, business inquiries — feel free to get in touch. We will reply after reviewing your message. English is welcome.</p>
<div class="direct"><span>You can also email us directly</span><a href="mailto:__EMAIL__">__EMAIL__</a></div>
<form id="contact-form" class="cform" novalidate>
<div class="field"><label for="c-name">Name<span class="req">Required</span></label>
<input type="text" id="c-name" name="name" autocomplete="name" required></div>
<div class="field"><label for="c-email">Email address for our reply<span class="req">Required</span></label>
<input type="email" id="c-email" name="email" autocomplete="email" inputmode="email" autocapitalize="off" spellcheck="false" required>
</div>
<div class="field"><label for="c-kind">Topic</label>
<select id="c-kind" name="kind">
<option>Listing or hiding a video</option>
<option value="Photos (removal request)" data-k="photo">Photos (removal request)</option>
<option>Incorrect information (tournament, date, etc.)</option>
<option>Website problem</option>
<option>Media or business inquiry</option>
<option>Other</option>
</select></div>
<div class="field"><label for="c-msg">Message<span class="req">Required</span></label>
<p class="fhint">For requests about a video, please include the page URL or the video title.</p>
<textarea id="c-msg" name="message" required></textarea></div>
<input class="hp" type="text" name="_gotcha" tabindex="-1" autocomplete="off" aria-hidden="true">
<p class="fhint">Your name and email address are used only to reply to your message.</p>
<button type="submit" id="c-send">Send</button>
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
  // Coming from a photo page's removal link: preselect the topic and the page
  try{ var q = new URLSearchParams(location.search), o = form.kind.querySelector('option[data-k="' + q.get("kind") + '"]');
    if (o) { o.selected = true; var pg = q.get("page"); if (pg && /^\/[\w\-\/%.\u3040-\u30ff\u4e00-\u9fff]*$/.test(pg) && !form.message.value) form.message.value = "Page: " + location.origin + pg + "\n"; } }catch(x){}
  function show(t, msg){ result.className = "cresult " + t; result.textContent = msg; }
  form.addEventListener("submit", function(ev){
    ev.preventDefault();
    var name = form.name.value.trim(), email = half(form.email.value.trim()),
        kind = form.kind.value, msg = form.message.value.trim();
    form.email.value = email;
    if (!name || !email || !msg){ show("ng", "Please enter your name, email address and message."); return; }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)){ show("ng", "Please check the email address format."); return; }
    if (!FORMSPREE_ID){
      var body = "Name: " + name + "\nReply to: " + email + "\nTopic: " + kind + "\n\n" + msg;
      location.href = "mailto:" + TO + "?subject=" + encodeURIComponent("[Contact] " + kind) + "&body=" + encodeURIComponent(body);
      show("ok", "Your email app will open. Please review and send the message. If it does not open, email " + TO + " directly.");
      return;
    }
    btn.disabled = true; btn.textContent = "Sending…";
    fetch("https://formspree.io/f/" + FORMSPREE_ID, {method: "POST", headers: {"Accept": "application/json"}, body: new FormData(form)})
      .then(function(r){
        if (r.ok){ form.reset(); show("ok", "Sent. We will reply after reviewing your message."); }
        else { show("ng", "Could not send. Please try again later or email " + TO + " directly."); }
      })
      .catch(function(){ show("ng", "Network error. Check your connection or email " + TO + " directly."); })
      .then(function(){ btn.disabled = false; btn.textContent = "Send"; });
  });
})();
</script>
"""


PRIVACY_UPDATED = "2026-10-07"


FAQ_UPDATED = "2026-10-09"


def faq_items(data, series_list):
    """よくある質問。数字はデータから入れるので、毎日の更新で最新になる"""
    n_videos = len(data.get("videos", []))
    years = [e["year"] for e in data.get("events", []) if e.get("n")]
    y0 = min(years) if years else ""
    n_series = len(series_list)
    return [
        (L("このサイトは何ですか?", "What is this site?"),
         L(f"Japan Wrestling Channel 公式の配信アーカイブです。YouTube で公開されている日本のレスリング大会の配信・動画{n_videos:,}本を、大会・開催年・日程ごとに整理しています。",
           f"The official archive of Japan Wrestling Channel. It organizes {n_videos:,} Japanese wrestling streams and videos published on YouTube by tournament, year and day."),
         None),
        (L("大会の配信はどこで見られますか?", "Where can I watch tournament streams?"),
         L("動画はすべて YouTube で再生されます。大会一覧から大会と開催年を選ぶと、その開催回の配信が日程・マットごとに並んでいます。",
           "All videos play on YouTube. Choose a tournament and year from the tournament list to see that edition's streams by day and mat."),
         ("/events/", L("大会一覧", "Tournaments"))),
        (L("これから行われる大会の配信予定はわかりますか?", "Can I see upcoming streams?"),
         L("大会カレンダーで、開催予定の大会を月ごとに確認できます。配信枠が公開されている大会は、大会のページに「配信予定」として表示されます。",
           "The tournament calendar shows upcoming tournaments by month. When stream slots are published, they appear on the tournament page as scheduled streams."),
         ("/events/calendar/", L("大会カレンダー", "Calendar"))),
        (L("過去の大会の動画はありますか?", "Are there videos of past tournaments?"),
         L(f"{y0}年以降の{n_series}大会の配信・動画を掲載しています。大会名・通称(例:インカレ、天皇杯)・年で検索できます。",
           f"Yes. Streams and videos from {n_series} tournaments since {y0} are listed. You can search by tournament name, nickname (e.g. Inter-College, Emperor's Cup) or year."),
         ("/", L("大会を検索", "Search"))),
        (L("選手の試合を探せますか?", "Can I find a wrestler's matches?"),
         L("選手検索から、選手ごとの出場大会・成績・関連する動画を見られます。",
           "Yes. Player pages list each wrestler's tournaments, results and related videos."),
         ("/players/", L("選手検索", "Players"))),
        (L("写真は使ってもいいですか? 取り下げてほしい写真があります", "Can I use the photos? I want a photo removed"),
         L("写真は撮影者の許可を得て掲載しています。著作権は撮影者にあるため、利用したい場合は撮影者にご確認ください。写真の取り下げのご依頼は、お問い合わせの「写真の掲載・取り下げについて」から受け付けています。",
           "Photos are published with the photographers' permission, and the copyright belongs to them. Please ask the photographer before using a photo. To request a removal, use the contact form and choose Photos (removal request)."),
         ("/contact.html?kind=photo", L("写真の取り下げのご依頼", "Photo removal request"))),
        (L("動画の掲載や非表示、情報の誤りを伝えたいです", "How do I report a mistake or ask to list or hide a video?"),
         L("お問い合わせフォームからお送りください。内容を確認のうえ対応します。",
           "Please use the contact form. We will review it and respond."),
         ("/contact.html", L("お問い合わせ", "Contact"))),
        (L("情報はいつ更新されますか?", "How often is the site updated?"),
         L("毎日、日本時間の朝6時ごろに YouTube の新しい動画を取り込み、ページを自動で作り直しています。",
           "Every day at around 6:00 a.m. Japan time, new YouTube videos are added and the pages are rebuilt automatically."),
         None),
        (L("英語版はありますか?", "Is there a Japanese version?"),
         L("あります。すべてのページに英語版があり、大会名・会場名は英語で表示されます(動画タイトルは日本語の原題のままです)。",
           "Yes. Every page has a Japanese version at the same address without /en/. English pages show tournament and venue names in English; video titles stay in Japanese as originally published."),
         (L("/en/", "/"), L("English version", "日本語版"))),
    ]


def about_page(data, series_list, ctx):
    """運営者情報(/about/)。誰が運営し、データをどこから集め、どう更新しているか(Google や AI が信頼できる情報源か判断する材料)"""
    n_videos = len(data.get("videos", []))
    years = [x["year"] for x in data.get("events", []) if x.get("n")]
    y0 = min(years) if years else ""
    crumbs = [(L("トップ", "Home"), "/"), (L("運営者情報", "About"), None)]
    org = {"@type": "Organization", "@id": SITE + "/#organization", "name": "Japan Wrestling Channel", "url": SITE + "/",
           "logo": SITE + "/assets/logo.png", "email": CONTACT_EMAIL}
    jsonld = {"@context": "https://schema.org", "@graph": [breadcrumb_ld(crumbs), org, {
        "@type": "AboutPage", "url": SITE + U("/about/"), "name": L("運営者情報", "About"),
        "about": {"@id": SITE + "/#organization"}, "publisher": {"@id": SITE + "/#organization"}}]}
    h = head(L(f"運営者情報|{SITE_NAME}", f"About | {site_name()}"),
             L("レスリング配信アーカイブは Japan Wrestling Channel 公式のサイトです。運営者、データの出典、更新のしかた、写真の掲載、連絡先について。",
               "The Japan Wrestling Archive is the official site of Japan Wrestling Channel. Who runs it, where the data comes from, how it is updated, photos and contact."),
             "/about/", "", jsonld, ctx["css"])
    rows = [
        (L("運営", "Operated by"), L("Japan Wrestling Channel(このサイトは Japan Wrestling Channel 公式の配信アーカイブです)",
                                     "Japan Wrestling Channel (this site is the official stream archive of Japan Wrestling Channel)")),
        (L("掲載している内容", "What is listed"),
         L(f"YouTube で公開されている日本のレスリング大会の配信・動画{n_videos:,}本({y0}年以降)を、大会・開催年・日程・マットごとに整理しています。あわせて、技術動画、選手ごとの出場大会と成績、国際大会の動画、大会の写真を掲載しています。動画はすべて YouTube で再生されます。",
           f"{n_videos:,} streams and videos of Japanese wrestling tournaments published on YouTube (since {y0}), organized by tournament, year, day and mat, plus technique videos, player pages with results, international videos and tournament photos. All videos play on YouTube.")),
        (L("データの出典", "Data sources"),
         L("動画は YouTube(Japan Wrestling Channel ほか)の公開情報から取得しています。大会の開催日・会場は、公益財団法人日本レスリング協会の大会ページ・事業報告書、旧協会サイト由来の記録、専門媒体の記事などをもとにした照合用の大会データに基づきます。出典は各開催回のページに表示しています。国際大会の動画は、世界レスリング連合(UWW)の公式 YouTube から日本人選手が出ている動画を集めています。",
           "Videos come from public YouTube information (Japan Wrestling Channel and others). Tournament dates and venues come from our reference data, based on Japan Wrestling Federation event pages and annual reports, records from the former federation site and specialist media. Sources are shown on each edition page. International videos featuring Japanese wrestlers come from the official YouTube channel of United World Wrestling (UWW).")),
        (L("更新", "Updates"),
         L("毎日、日本時間の朝6時ごろに新しい動画を取り込み、ページを自動で作り直しています。動画と大会の対応が確定していないものは「確認待ち」として区別し、確認できたものから手作業で直しています。",
           "Every day at around 6:00 a.m. Japan time, new videos are added and the pages are rebuilt automatically. Videos not yet confirmed to belong to an edition are marked \"Pending review\" and corrected by hand once checked.")),
        (L("写真", "Photos"),
         L("大会の写真は、撮影者の許可を得て掲載しています。著作権は撮影者にあります。写真の掲載・取り下げについては、お問い合わせからご連絡ください。",
           "Tournament photos are published with the photographers' permission, and the copyright belongs to them. For questions about a photo or removal requests, please contact us.")),
        (L("お問い合わせ", "Contact"),
         L("掲載内容の誤り、動画の掲載・非表示、写真の取り下げ、取材・お仕事のご相談は、お問い合わせフォームからお送りください。",
           "For corrections, listing or hiding a video, photo removal, or media and business inquiries, please use the contact form.")),
    ]
    h += '<main class="wrap page">' + breadcrumb_html(crumbs) + f'<h1>{L("運営者情報", "About this site")}</h1><dl class="facts">'
    h += "".join(f"<dt>{e(k)}</dt><dd>{e(v)}</dd>" for k, v in rows) + "</dl>"
    h += (f'<p class="tosearch-line"><a href="{U("/contact.html")}">{L("お問い合わせ", "Contact")} →</a>　'
          f'<a href="{U("/faq/")}">{L("よくある質問", "FAQ")} →</a>　<a href="{U("/privacy/")}">{L("プライバシーポリシー", "Privacy Policy")} →</a></p>')
    h += "</main>" + footer(ctx["as_of"])
    return "/about/", h


def faq_page(data, series_list, ctx):
    """よくある質問(/faq/)。FAQPage の構造化データ付き(Google や AI が答えとして引用しやすい形)"""
    items = faq_items(data, series_list)
    crumbs = [(L("トップ", "Home"), "/"), (L("よくある質問", "FAQ"), None)]
    jsonld = {"@context": "https://schema.org", "@graph": [breadcrumb_ld(crumbs), {
        "@type": "FAQPage", "url": SITE + U("/faq/"), "dateModified": FAQ_UPDATED,
        "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a, _ in items]}]}
    h = head(L(f"よくある質問|{SITE_NAME}", f"FAQ | {site_name()}"),
             L("レスリング配信アーカイブ(Japan Wrestling Channel 公式)についてよくある質問と答えです。配信の見方、過去の大会、選手、写真、更新の頻度など。",
               "Frequently asked questions about the Japan Wrestling Archive (official, Japan Wrestling Channel): watching streams, past tournaments, players, photos and updates."),
             "/faq/", "", jsonld, ctx["css"])
    h += '<main class="wrap page">' + breadcrumb_html(crumbs) + f'<h1>{L("よくある質問", "Frequently asked questions")}</h1>'
    for q, a, link in items:
        h += f'<section class="section faq"><h2>{e(q)}</h2><p>{e(a)}</p>'
        if link:
            href = link[0] if link[0].startswith("/en/") or link[0] == "/" and i18n.en() else U(link[0])
            h += f'<p><a href="{e(href)}">{e(link[1])} →</a></p>'
        h += "</section>"
    h += "</main>" + footer(ctx["as_of"])
    return "/faq/", h


def privacy_page(ctx):
    """プライバシーポリシー(/privacy/)。App Store・Google Play・Firebase に登録する URL。アプリの実際の動きと合わせて書く"""
    h = head(L(f"プライバシーポリシー|{SITE_NAME}", f"Privacy Policy | {site_name()}"),
             L("レスリング配信アーカイブ(japanwrestlingchannel.com)とスマホアプリ「JWC」で扱う情報と、その使い方についての説明です。",
               "How the Japan Wrestling Archive (japanwrestlingchannel.com) and the JWC mobile app handle information."),
             "/privacy/", "",
             {"@context": "https://schema.org", "@type": "WebPage", "name": L("プライバシーポリシー", "Privacy Policy"),
              "url": SITE + U("/privacy/"), "dateModified": PRIVACY_UPDATED}, ctx["css"])
    body = (L(PRIVACY_BODY, PRIVACY_BODY_EN).replace("__EMAIL__", CONTACT_EMAIL).replace("__UPDATED__", fmt_date(PRIVACY_UPDATED))
            .replace("__CONTACT__", U("/contact.html")))
    return "/privacy/", h + body + footer(ctx["as_of"])


PRIVACY_BODY = r"""<main class="wrap page policy">
<nav class="crumbs" aria-label="パンくずリスト"><ol><li><a href="/">トップ</a></li><li>プライバシーポリシー</li></ol></nav>
<h1>プライバシーポリシー</h1>
<p class="lead">Japan Wrestling Channel 公式の「レスリング配信アーカイブ」(japanwrestlingchannel.com。以下「サイト」)と、スマホアプリ「JWC - Japan Wrestling Channel」(iPhone・Android。以下「アプリ」)で扱う情報と、その使い方を説明します。</p>
<p class="upd">最終更新日:__UPDATED__</p>

<h2>1. サイトで扱う情報</h2>
<ul>
<li><b>アクセス解析</b>:サイトの使われ方を知るために Google アナリティクスを使っています。Cookie を使い、見たページ・おおよその地域・端末やブラウザの種類などを集めます。名前やメールアドレスなど、あなたを特定する情報は集めません。集めたくない場合は、<a href="https://tools.google.com/dlpage/gaoptout?hl=ja" rel="noopener">Google アナリティクス オプトアウト アドオン</a>を使うか、ブラウザで Cookie を無効にしてください。</li>
<li><b>お問い合わせ</b>:お問い合わせのときにいただいたお名前・メールアドレス・内容は、返信と対応のためだけに使います。</li>
<li><b>表示の設定</b>:言語やテーマ(白・黒)の設定は、あなたのブラウザの中だけに保存します。</li>
</ul>

<h2>2. アプリで扱う情報</h2>
<ul>
<li><b>アカウント登録はありません</b>。アプリが、お名前・メールアドレス・電話番号・位置情報・連絡先・写真などを集めることはありません。</li>
<li><b>お気に入り</b>:☆をつけた選手・大会は、<b>あなたのスマホの中だけ</b>に保存します。私たちのサーバーには送りません。アプリを削除すると、お気に入りも消えます。</li>
<li><b>通知</b>:通知を許可した場合に限り、Google の Firebase Cloud Messaging を使って通知を送ります。そのために、Firebase が発行する通知用の ID(トークン)と、受け取る通知の種類(新着動画、☆をつけた選手のお知らせ)が Firebase に登録されます。私たちはこの ID を、あなた個人と結びつけません。通知はアプリの設定やスマホの設定から、いつでもオフにできます。</li>
<li><b>アクセス解析・広告・追跡はしません</b>。アプリには広告を入れず、ほかのアプリやサイトをまたいだ行動の追跡(トラッキング)もしません。</li>
<li><b>大会・動画のデータ</b>:アプリは、大会や動画の情報を japanwrestlingchannel.com から読み込みます。このとき、ふつうのサイトを見るときと同じように、IP アドレスなどの通信の記録が、サイトの配信に使っている Cloudflare で処理されます。</li>
</ul>

<h2>3. 動画(YouTube)について</h2>
<p>サイトとアプリの動画は、YouTube の埋め込みプレーヤーで再生されます。再生のときには YouTube(Google)が Cookie などで情報を集めることがあり、その扱いは <a href="https://policies.google.com/privacy?hl=ja" rel="noopener">Google のプライバシーポリシー</a>に従います。</p>

<h2>4. 使っている外部のサービス</h2>
<table class="ptable">
<thead><tr><th>サービス</th><th>使う場所</th><th>目的</th></tr></thead>
<tbody>
<tr><td>Google アナリティクス</td><td>サイト</td><td>アクセス解析</td></tr>
<tr><td>Firebase Cloud Messaging(Google)</td><td>アプリ</td><td>通知を送る(許可した場合だけ)</td></tr>
<tr><td>YouTube(Google)</td><td>サイト・アプリ</td><td>動画の再生・サムネイルの表示</td></tr>
<tr><td>Cloudflare</td><td>サイト・アプリ</td><td>サイトとデータの配信、セキュリティ</td></tr>
<tr><td>Google Fonts</td><td>サイト</td><td>文字(フォント)の表示</td></tr>
</tbody>
</table>
<p>法令にもとづく場合を除き、いただいた情報を、上の目的のほかに第三者へ渡すことはありません。情報を売ることもありません。</p>

<h2>5. 選手の情報と写真</h2>
<ul>
<li>選手のお名前や成績は、大会の公式の結果など、公開されている情報をもとに載せています。<b>未成年の選手は、掲載の許可が確認できた方だけ</b>を載せています。</li>
<li>写真は、撮影した方の許可を得て載せています。写っているご本人や保護者の方から依頼があれば、取り下げます。</li>
<li>掲載内容の訂正・削除のご依頼は、下の窓口へお送りください。</li>
</ul>

<h2>6. お子さまの利用</h2>
<p>サイトとアプリは、お子さまから意図して個人情報を集めることはありません。</p>

<h2>7. このポリシーの変更</h2>
<p>サイトやアプリの機能が変わったときは、このページを更新し、最終更新日を書き換えます。</p>

<h2>8. お問い合わせ</h2>
<p>運営:Japan Wrestling Channel 公式<br>
情報の扱いについてのご質問、削除・訂正のご依頼は、<a href="__CONTACT__">お問い合わせ</a>、またはメール(<a href="mailto:__EMAIL__">__EMAIL__</a>)へお送りください。</p>
</main>
"""

PRIVACY_BODY_EN = r"""<main class="wrap page policy">
<nav class="crumbs" aria-label="Breadcrumb"><ol><li><a href="/en/">Home</a></li><li>Privacy Policy</li></ol></nav>
<h1>Privacy Policy</h1>
<p class="lead">This policy explains what information the Japan Wrestling Archive, the official archive of Japan Wrestling Channel (japanwrestlingchannel.com, the "Site"), and the mobile app "JWC - Japan Wrestling Channel" (iPhone and Android, the "App") handle, and how it is used.</p>
<p class="upd">Last updated: __UPDATED__</p>

<h2>1. Information on the Site</h2>
<ul>
<li><b>Analytics</b>: We use Google Analytics to understand how the Site is used. It uses cookies to collect the pages you view, your approximate region, and your device and browser type. It does not collect information that identifies you, such as your name or email address. To opt out, use the <a href="https://tools.google.com/dlpage/gaoptout" rel="noopener">Google Analytics Opt-out Browser Add-on</a> or disable cookies in your browser.</li>
<li><b>Contact</b>: The name, email address and message you send us are used only to reply to and handle your inquiry.</li>
<li><b>Display settings</b>: Your language and theme (light or dark) settings are stored only in your browser.</li>
</ul>

<h2>2. Information in the App</h2>
<ul>
<li><b>No account is required.</b> The App does not collect your name, email address, phone number, location, contacts or photos.</li>
<li><b>Favorites</b>: Players and tournaments you star are stored <b>only on your device</b>. They are never sent to our servers. Deleting the App deletes your favorites.</li>
<li><b>Notifications</b>: Only if you allow notifications, we send them through Google's Firebase Cloud Messaging. For this, a notification ID (token) issued by Firebase and the kinds of notifications you receive (new videos, news about players you starred) are registered with Firebase. We never link this ID to you as a person. You can turn notifications off at any time in the App or in your device settings.</li>
<li><b>No analytics, ads or tracking.</b> The App contains no ads and does not track you across other apps or websites.</li>
<li><b>Tournament and video data</b>: The App downloads tournament and video information from japanwrestlingchannel.com. As with visiting any website, connection records such as your IP address are processed by Cloudflare, which delivers the Site.</li>
</ul>

<h2>3. Videos (YouTube)</h2>
<p>Videos on the Site and in the App play in the embedded YouTube player. YouTube (Google) may collect information through cookies and similar technologies during playback, as described in <a href="https://policies.google.com/privacy" rel="noopener">Google's Privacy Policy</a>.</p>

<h2>4. Third-party services</h2>
<table class="ptable">
<thead><tr><th>Service</th><th>Used in</th><th>Purpose</th></tr></thead>
<tbody>
<tr><td>Google Analytics</td><td>Site</td><td>Analytics</td></tr>
<tr><td>Firebase Cloud Messaging (Google)</td><td>App</td><td>Sending notifications (only if you allow them)</td></tr>
<tr><td>YouTube (Google)</td><td>Site, App</td><td>Video playback and thumbnails</td></tr>
<tr><td>Cloudflare</td><td>Site, App</td><td>Delivering the Site and data, security</td></tr>
<tr><td>Google Fonts</td><td>Site</td><td>Displaying fonts</td></tr>
</tbody>
</table>
<p>Except where required by law, we do not share information with third parties beyond the purposes above, and we never sell it.</p>

<h2>5. Player information and photos</h2>
<ul>
<li>Player names and results are based on public information such as official tournament results. <b>Minors are listed only when permission has been confirmed.</b></li>
<li>Photos are published with the photographer's permission. We will take a photo down at the request of the person in it or their guardian.</li>
<li>For corrections or removal requests, please contact us below.</li>
</ul>

<h2>6. Children</h2>
<p>The Site and the App do not knowingly collect personal information from children.</p>

<h2>7. Changes to this policy</h2>
<p>When the features of the Site or the App change, we will update this page and its "Last updated" date.</p>

<h2>8. Contact</h2>
<p>Operated by: Japan Wrestling Channel (official)<br>
For questions about how information is handled, or for removal and correction requests, please use the <a href="__CONTACT__">contact form</a> or email <a href="mailto:__EMAIL__">__EMAIL__</a>.</p>
</main>
"""


def llms_txt(data, series_list, ctx):
    """AI(ChatGPT・Claude・Perplexityなど)向けに、サイトの概要と主なページを平文でまとめる"""
    n_videos = len(data.get("videos", []))
    lines = [
        f"# {SITE_NAME}(Japan Wrestling Channel アーカイブ)",
        "",
        f"> YouTubeで公開されている日本のレスリング大会の配信・動画{n_videos:,}本を、大会名・開催年・日程ごとに整理した Japan Wrestling Channel 公式のアーカイブです。"
        "動画そのものはYouTubeで再生されます。大会の開催日・会場は照合用の大会データに基づきます。",
        "",
        f"- サイト: {SITE}/",
        f"- データ更新日: {fmt_date(data.get('as_of'))}",
        f"- お問い合わせ: {SITE}/contact.html",
        "",
        "## 主なページ",
        f"- [大会一覧]({SITE}/events/): 配信動画のある{len(series_list)}大会の一覧",
        f"- [技術動画]({SITE}/technique/): レスリングクラブが公開している技術・トレーニング動画を、タックル・投げ技・グラウンドなどの区分で整理",
        f"- [写真]({SITE}/photos/): 大会で撮影された写真(撮影者の許可を得て掲載)を大会ごとに掲載",
        f"- [大会カレンダー]({SITE}/events/calendar/): 開催予定・過去の大会を月ごとに表示",
        f"- [選手検索]({SITE}/players/): 選手ごとの出場大会・成績・動画",
        f"- [歴代優勝者]({SITE}/champions/): 主な大会の階級ごとの歴代優勝者",
        f"- [検索ページ]({SITE}/): 大会名・通称・動画タイトルで検索",
        f"- [English version]({SITE}/en/): 英語版(同じ内容。大会名・会場名は英語、動画タイトルは日本語の原題)",
        f"- [運営者情報]({SITE}/about/): 運営者(Japan Wrestling Channel)、データの出典、更新のしかた、写真の掲載について",
        f"- [よくある質問]({SITE}/faq/): 配信の見方・過去の大会・選手・写真・更新の頻度などの質問と答え",
        f"- [プライバシーポリシー]({SITE}/privacy/)",
        "",
        "## 詳しい一覧",
        f"- [llms-full.txt]({SITE}/llms-full.txt): すべての大会の開催回(開催日・会場・動画の本数・ページのURL)の一覧",
        "",
        "## 大会(大会ごとのページ。各ページから開催回ごとのページへ移れます)",
    ]
    for x in series_list:
        evs = [v for v in ctx["events_by_series"].get(x["id"], []) if v.get("n")]
        yrs = [v["year"] for v in evs]
        span = (f"{min(yrs)}年" if min(yrs) == max(yrs) else f"{min(yrs)}〜{max(yrs)}年") if yrs else ""
        lines.append(f"- [{x['name']}]({SITE}/events/{x['id']}/): {span} 動画{x.get('n', 0)}本")
    return "\n".join(lines) + "\n"


def llms_full_txt(data, series_list, ctx):
    """llms.txt の詳しい版。大会ごとに、開催回の開催日・会場・動画の本数・ページのURLを並べる"""
    lines = [llms_txt(data, series_list, ctx).rstrip("\n"), "", "## 開催回の一覧(新しい順)", ""]
    for x in series_list:
        lines.append(f"### {x['name']}")
        lines.append(f"- 大会ページ: {SITE}/events/{x['id']}/")
        for v in sorted(ctx["events_by_series"].get(x["id"], []), key=lambda v: v.get("start") or f"{v['year']}-99", reverse=True):
            if v["id"] not in ctx["slugs"]:
                continue
            when = "中止" if v.get("status") == "cancelled" else (fmt_range(v.get("start"), v.get("end")) if v.get("start") else "日付未確認")
            if v.get("status") == "scheduled":
                when += "(予定)"
            parts = [when] + ([v["venue"]] if v.get("venue") and not v.get("derived") else []) + [f"動画{v.get('n', 0)}本"]
            if f"/events/{ctx['slugs'][v['id']]}/" in ctx.get("photo_paths", ()):
                parts.append("写真あり")
            lines.append(f"- [{v.get('official_name') or v['name']}]({SITE}/events/{ctx['slugs'][v['id']]}/): " + "・".join(parts))
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def not_found_page(ctx):
    h = head(f"ページが見つかりません / Page not found|{SITE_NAME}", "お探しのページは見つかりませんでした。 The page you are looking for was not found.", "/404.html", "",
             {"@context": "https://schema.org", "@type": "WebPage", "name": "ページが見つかりません"}, ctx["css"], alternates=False)
    h = h.replace('<link rel="canonical" href="https://japanwrestlingchannel.com/404.html">', '<meta name="robots" content="noindex">')
    h += ('<main class="wrap page"><h1>ページが見つかりません</h1>'
          '<p class="lead">URLが変わったか、削除された可能性があります。大会一覧か検索ページから探してください。</p>'
          '<p><a href="/events/">大会一覧を見る</a> / <a href="/">検索ページへ</a></p>'
          '<h2 lang="en">Page not found</h2>'
          '<p class="lead" lang="en">The URL may have changed or the page may have been removed. Try the tournament list or the search page.</p>'
          '<p lang="en"><a href="/en/events/">Tournaments</a> / <a href="/en/">Search</a></p></main>' + footer(ctx["as_of"]))
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
:root[data-theme="light"] .cresult.ok{background:#e6f4ea;border-color:#9ccfab}
.cresult.ng{display:block;background:var(--st-cancel-bg);border:1px solid var(--st-cancel)}
@media (max-width:520px){.cform{padding:18px 14px 20px}}
.page{padding-top:18px}
.policy{padding-bottom:44px}
.policy .upd{font-size:13px;color:var(--ink3);margin:0 0 8px}
.policy h2{font-size:18px;font-weight:700;margin:28px 0 8px;padding-left:10px;border-left:3px solid var(--pink)}
.policy p,.policy ul{max-width:70ch}
.policy li{margin:0 0 8px}
.ptable{border-collapse:collapse;font-size:14px;margin:4px 0 12px;max-width:70ch;width:100%}
.ptable th,.ptable td{border:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}
.ptable th{background:var(--surface);font-weight:700}
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
.elinks{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 0}
.elink{display:inline-block;padding:8px 18px;border:1px solid var(--pink-line);border-radius:999px;color:var(--pink);text-decoration:none;font-size:14px;font-weight:700}
.elink:hover{border-color:var(--pink)}
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
    import players
    import calendar_page
    import photo_gallery
    import champions
    import uww_page
    return (m.group(1) if m else "") + PAGE_CSS + players.PLAYER_CSS + calendar_page.CAL_CSS + photo_gallery.PHOTO_CSS + champions.CHAMP_CSS + uww_page.UWW_CSS


def build(root=HERE, inline_css=False, only=None):
    with open(os.path.join(root, "data.json"), encoding="utf-8") as f:
        data = json.load(f)
    tech = data.get("tech", {"channels": []})
    css_text = extract_css(os.path.join(root, "index.html"))
    os.makedirs(os.path.join(root, "assets"), exist_ok=True)
    with open(os.path.join(root, "assets", "site.css"), "w", encoding="utf-8") as f:
        f.write(css_text)
    # CSSの中身が変わるたびにURLの末尾(?v=…)も変わるので、ブラウザやCloudflareに古いCSSが残らない
    import hashlib
    ver = hashlib.md5(css_text.encode("utf-8")).hexdigest()[:8]
    css = f"<style>{css_text}</style>" if inline_css else f'<link rel="stylesheet" href="/assets/site.css?v={ver}">'

    import photo_gallery
    wanted = photo_gallery.wanted_pages(root)
    for ev in data["events"]:
        if f"{ev['series']}/{ev['year']}" in wanted:
            ev["_photo_page"] = True
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
    # 写真ギャラリー(photos.json)。写真があるページにだけ表示する
    import photo_gallery
    page_paths = {f"/events/{slugs[ev['id']]}/" for ev in data["events"] if ev["id"] in slugs}
    page_paths |= {f"/events/{s['id']}/" for s in data["series"] if s.get("n")}
    photos_by_page, photo_report = photo_gallery.load(root, page_paths)
    ctx = dict(S=S, slugs=slugs, by_event=by_event, cand=cand, loose_by_series=loose_by_series,
               events_by_series=events_by_series, all_events=data["events"], css=css, as_of=data.get("as_of"),
               gallery=lambda path, title: photo_gallery.gallery_html(photos_by_page.get(path), e, title, path,
                                                                     U(photo_gallery.photo_path(path)) if photos_by_page.get(path) else None),
               photo_paths=set(photos_by_page) | set(photo_gallery.ALBUMS))

    import players
    import calendar_page
    import sys
    me = sys.modules[__name__]
    i18n.load_names(root)
    i18n.load_translations(root)
    i18n.missing.clear()
    # 選手データ(players.csv / player_results.csv)。開催回ページの「入賞者」の欄でも使うので先に読む
    preport = players.prepare(root, data, ctx)
    # 大会ごとの歴代優勝者(player_results.csv の1位)。大会ページのリンクでも使うので先に読む
    import champions
    creport = champions.prepare(root, data, ctx)
    # 選手ページの SNS 用画像を作った数(日本語版・英語版。players.build が書き込む)
    preport["og_cards"] = ctx.setdefault("og_cards", {})
    report = load_json(root, "build_report.json", {}) if only is None else None

    def latest(sr):
        return max((x.get("start") or "" for x in events_by_series[sr["id"]] if x.get("n")), default="")
    listed = sorted([x for x in data["series"] if x.get("n")], key=latest, reverse=True)

    all_pages = []
    hero = {}
    # 日本語版(今までのURL)と英語版(/en/ の下)を同じ処理で作る
    for lang in ("ja", "en"):
        i18n.set_lang(lang)
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
            # 写真ページ(/photos/)。photos.json に写真があるページの分だけ作る
            pages.extend(photo_gallery.photo_pages(ctx, photos_by_page, me))
            hero[lang] = photo_gallery.hero_items(ctx, photos_by_page, me)
            # 選手ページ(players.csv / player_results.csv があるときだけ作られる)
            pages.extend(players.build(root, data, ctx, me))
            # 歴代優勝者のページ(/champions/)。日本語版だけ
            pages.extend((path, doc, data.get("as_of")) for path, doc in champions.build(ctx, me))
            path, doc = index_page(ctx, listed)
            pages.append((path, doc, data.get("as_of")))
            # 大会カレンダー(events/calendar/ に作るので update.yml の変更は不要)
            pages.append((*calendar_page.calendar_page(data, ctx, me), data.get("as_of")))
            # 国際大会(UWW)の動画のページ(uww_videos.csv があるときだけ作る)
            import uww_page
            pages.extend(uww_page.build(root, ctx, me))
            # プライバシーポリシー(アプリの審査・Firebase にも登録する URL)
            pages.append((*privacy_page(ctx), PRIVACY_UPDATED))
            # よくある質問
            pages.append((*faq_page(data, listed, ctx), data.get("as_of")))
            # 運営者情報
            pages.append((*about_page(data, listed, ctx), data.get("as_of")))
            contact = os.path.join(root, U("/contact.html").lstrip("/"))
            os.makedirs(os.path.dirname(contact), exist_ok=True)
            with open(contact, "w", encoding="utf-8") as f:
                f.write(contact_page(ctx))
            if lang == "ja":
                # 区分けできなかった動画はサイトに出さず、build_report.json に一覧を残す
                cnt = defaultdict(int)
                for v in shown:
                    cnt[v["cat"]] += 1
                report["players"] = preport
                report["champions"] = creport
                report["photos"] = photo_report
                report["tech"] = {"shown": len(shown), "by_category": dict(cnt), "moved_to_tournament": to_tournament,
                                  "unclassified_count": len(unclassified),
                                  "tech_unclassified": [{"video_id": v["id"], "title": v["t"], "channel": v["_ch"]} for v in unclassified]}
                with open(os.path.join(root, "404.html"), "w", encoding="utf-8") as f:
                    f.write(not_found_page(ctx))
                with open(os.path.join(root, "llms.txt"), "w", encoding="utf-8") as f:
                    f.write(llms_txt(data, listed, ctx))
                with open(os.path.join(root, "llms-full.txt"), "w", encoding="utf-8") as f:
                    f.write(llms_full_txt(data, listed, ctx))
            else:
                # 英語版の検索ページ(index.html をもとに作る)
                import en_index
                en_index.write(root, data, slugs)
        for path, doc, _ in pages:
            d = os.path.join(root, U(path).strip("/"))
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
                f.write(doc)
        all_pages.append((lang, pages))
    i18n.set_lang("ja")
    if only is None:
        photo_gallery.write_hero(root, hero)
        # 「カレンダーに追加」の .ics ファイル。終わった大会の分が残らないよう、毎回作り直す
        import shutil
        import calendar_page
        for pre in ("", "/en"):
            shutil.rmtree(os.path.join(root, (pre + calendar_page.ICS_DIR).strip("/")), ignore_errors=True)
        for p, text in ctx.get("ics", {}).items():
            fp = os.path.join(root, p.strip("/"))
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            with open(fp, "w", encoding="utf-8", newline="") as f:
                f.write(text)
    pages = all_pages[0][1]
    en_pages = all_pages[1][1]

    if only is None:
        report["en"] = {"pages": len(en_pages), "names": len(i18n.names_table()), "machine_translations": i18n.tr_count(),
                        "missing_names": sorted(i18n.missing)}
        with open(os.path.join(root, "build_report.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        urls = [(f"{SITE}/", data.get("as_of")), (f"{SITE}/en/", data.get("as_of"))]
        urls += [(SITE + p, lm) for p, _, lm in sorted(pages)] + [(SITE + "/en" + p, lm) for p, _, lm in sorted(en_pages)]
        urls += [(f"{SITE}/contact.html", None), (f"{SITE}/en/contact.html", None)]
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
    n_pl = sum(1 for p in pages if p[0].startswith("/players/"))
    n_ph = sum(1 for p in pages if p[0].startswith("/photos/"))
    n_ch = sum(1 for p in pages if p[0].startswith("/champions/"))
    print(f"ページを生成しました: {len(pages)}ページ(開催回 {n_ev}・大会 {n_se}・技術動画 {n_te}・選手 {n_pl}・写真 {n_ph}・歴代優勝者 {n_ch})+英語版 {len(en_pages)}ページ")
    if i18n.missing:
        print(f"[英語版] 英語名が無い名前 {len(i18n.missing)}件(日本語のまま表示): " + "、".join(sorted(i18n.missing)[:10]) + " … en_names.csv に追加してください")
    print(f"写真: {photo_report['shown']}枚を{photo_report['pages_with_photos']}ページに掲載"
          f"(非表示 {photo_report['hidden']}・未確認 {photo_report['unconfirmed']}・エラー {len(photo_report['errors'])}・警告 {len(photo_report['warnings'])})")
    return pages


if __name__ == "__main__":
    build()
