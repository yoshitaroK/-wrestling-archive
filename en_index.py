"""
英語版の検索ページ(/en/index.html)を、日本語版の index.html から自動で作る。

- 画面の文字のうち JavaScript で作る部分は、index.html の中で L('日本語', 'English') と書き分けてある
  (<html lang="en"> のときに英語が選ばれる)
- ここでは、HTML に直接書いてある見出し・説明・ボタンなどを英語に置き換え、大会名などの英語名(en_names.csv)を渡す
- index.html の文言を変えて置き換えが見つからなくなったときは、ビルドを止めて知らせる(英語版に日本語が残らないように)
"""
import json
import os

import i18n

SITE = "https://japanwrestlingchannel.com"
DESC = ("The official Japan Wrestling Channel archive of Japanese wrestling streams and videos (from Japan Wrestling Channel and others), "
        "searchable by tournament, year and day. Emperor's Cup, Meiji Cup, Inter-College, Inter-High and more.")

PAIRS = [
    ('<html lang="ja">', '<html lang="en">'),
    ('<title>レスリング配信アーカイブ</title>', '<title>Japan Wrestling Archive – Japanese wrestling streams by tournament</title>'),
    ('<meta name="description" content="Japan Wrestling Channel 公式の配信アーカイブです。レスリングの配信・動画を、大会名・開催年・日程から探せます。天皇杯、明治杯、インカレ、インターハイなどの配信をまとめています。">',
     f'<meta name="description" content="{DESC}">'),
    ('<link rel="canonical" href="https://japanwrestlingchannel.com/">', '<link rel="canonical" href="https://japanwrestlingchannel.com/en/">'),
    ('<meta property="og:site_name" content="レスリング配信アーカイブ">', '<meta property="og:site_name" content="Japan Wrestling Archive">\n<meta property="og:locale" content="en_US">'),
    ('<meta property="og:title" content="レスリング配信アーカイブ">', '<meta property="og:title" content="Japan Wrestling Archive">'),
    ('<meta property="og:description" content="Japan Wrestling Channel 公式の配信アーカイブです。レスリングの配信・動画を、大会名・開催年・日程から探せます。">',
     f'<meta property="og:description" content="{DESC}">'),
    ('<meta property="og:url" content="https://japanwrestlingchannel.com/">', '<meta property="og:url" content="https://japanwrestlingchannel.com/en/">'),
    ('<meta property="og:image" content="https://japanwrestlingchannel.com/ogp.png?v=2">', '<meta property="og:image" content="https://japanwrestlingchannel.com/ogp-en.png?v=1">'),
    ('aria-label="レスリング配信アーカイブ(トップへ)"', 'aria-label="Japan Wrestling Archive (home)"'),
    ('<span class="official-t">Japan Wrestling Channel 公式サイト</span><a class="lang" href="/en/" hreflang="en" lang="en" title="English version" onclick="try{localStorage.setItem(\'lang\',\'en\')}catch(x){}this.href=this.getAttribute(\'href\').split(\'#\')[0]+location.hash">English</a>',
     '<span class="official-t">Official site of Japan Wrestling Channel</span><a class="lang" href="/" hreflang="ja" lang="ja" title="日本語版を表示" onclick="try{localStorage.setItem(\'lang\',\'ja\')}catch(x){}this.href=this.getAttribute(\'href\').split(\'#\')[0]+location.hash">日本語</a>'),
    ('<nav class="topnav" aria-label="メニュー"><a href="/events/">大会一覧</a><a href="/players/">選手検索</a><a href="/events/calendar/">カレンダー</a><a href="/technique/">技術動画</a><a href="/photos/">写真</a></nav>',
     '<nav class="topnav" aria-label="Menu"><a href="/en/events/">Tournaments</a><a href="/en/players/">Players</a><a href="/en/events/calendar/">Calendar</a><a href="/en/technique/">Technique</a><a href="/en/photos/">Photos</a></nav>'),
    ('<h1 id="jhero-h">レスリング配信アーカイブ</h1>', '<h1 id="jhero-h">Japan Wrestling Archive</h1>'),
    ('<p class="jlead" id="tagline">Japan Wrestling Channel 公式 · レスリングの配信・動画を、大会名・開催年・日程から探せます。収録<b class="num" id="stat-v"></b>本</p>',
     '<p class="jlead" id="tagline">Official Japan Wrestling Channel archive · Find wrestling streams and videos by tournament, year and day. <b class="num" id="stat-v"></b> videos</p>'),
    ('<div class="searchbox" role="group" aria-label="絞り込み">', '<div class="searchbox" role="group" aria-label="Filters">'),
    ('aria-label="表示色を切り替え"', 'aria-label="Switch color theme"'),
    ('<label for="q" class="sr">大会名・通称・動画タイトルで検索</label>', '<label for="q" class="sr">Search by tournament name or video title</label>'),
    ('placeholder="大会名や通称で検索(例:天皇杯、インカレ、明治杯)"', 'placeholder="Search tournaments (e.g. Emperor\'s Cup, Inter-High, 2022)"'),
    ('<p class="hint">通称・略称でも探せます。スペースで区切ると複数の語で絞り込みます(例:天皇杯 2022)。</p>',
     '<p class="hint">Search English or Japanese tournament names. Separate words with spaces to narrow down (e.g. Emperor 2022). Video titles are in Japanese.</p>'),
    ('<label>開催年<select id="f-year"><option value="">すべて</option></select></label>', '<label>Year<select id="f-year"><option value="">All</option></select></label>'),
    ('<label>区分<select id="f-cat"><option value="">すべて</option></select></label>', '<label>Category<select id="f-cat"><option value="">All</option></select></label>'),
    ('<label>スタイル<select id="f-style"><option value="">すべて</option></select></label>', '<label>Style<select id="f-style"><option value="">All</option></select></label>'),
    ('<label>国内・海外<select id="f-scope"><option value="">すべて</option></select></label>', '<label>Domestic / overseas<select id="f-scope"><option value="">All</option></select></label>'),
    ('<label>動画の種類<select id="f-kind"><option value="">すべて</option></select></label>', '<label>Video type<select id="f-kind"><option value="">All</option></select></label>'),
    ('<label class="check"><input type="checkbox" id="f-all"> 動画のない大会・開催回も表示</label>', '<label class="check"><input type="checkbox" id="f-all"> Include tournaments without videos</label>'),
    ('<div class="loading">データを読み込んでいます</div>', '<div class="loading">Loading data…</div>'),
    ('<p><a href="/events/">大会一覧(すべての大会のページ)</a>・<a href="/events/calendar/">大会カレンダー</a>・<a href="/technique/">技術動画</a>・<a href="/photos/">写真</a>・<a href="/players/">選手検索</a>・<a href="/contact.html">お問い合わせ</a>・<a href="/en/" hreflang="en" lang="en">English</a></p>',
     '<p><a href="/en/events/">Tournaments (all tournament pages)</a> · <a href="/en/events/calendar/">Calendar</a> · <a href="/en/technique/">Technique videos</a> · <a href="/en/photos/">Photos</a> · <a href="/en/players/">Players</a> · <a href="/en/contact.html">Contact</a> · <a href="/" hreflang="ja" lang="ja">日本語</a></p>'),
    ('<p>このサイトは Japan Wrestling Channel 公式の配信アーカイブです。Japan Wrestling Channel などの YouTube で公開されているレスリングの動画を、大会ごとに整理しています。動画はすべて YouTube で再生されます。</p>',
     '<p>The official archive of Japan Wrestling Channel. It organizes Japanese wrestling videos published on YouTube (Japan Wrestling Channel and others) by tournament. All videos play on YouTube. Video titles are shown as originally published, in Japanese.</p>'),
    ('<p>大会の開催日・会場・出典は照合用の大会データ(<span id="master-asof"></span>時点)に基づきます。出典の種類(日本協会の大会ページ、事業報告書、旧協会サイト由来の記録、専門媒体の記事など)は各開催回に表示しています。主催・公認の関係は資料に記載があるものだけを示しています。</p>',
     '<p>Dates, venues and sources come from our tournament reference data (as of <span id="master-asof"></span>). Source types (JWF event pages, annual reports, records from the former JWF site, specialist media, etc.) are shown for each edition. Organizer relationships are shown only where documented. English names of tournaments and venues are our own translations.</p>'),
    ('<p>動画と開催回の対応には根拠を表示しています。「確認待ち」は大会名や年が曖昧なため、候補を示しているだけの動画です。</p>',
     '<p>The basis for linking each video to an edition is shown. "Pending review" marks videos whose tournament name or year is ambiguous and are only suggested matches.</p>'),
]

JSONLD_JA_START = '<script type="application/ld+json">{"@context":"https://schema.org","@graph":['
JSONLD_EN = ('<script type="application/ld+json">' + json.dumps({"@context": "https://schema.org", "@graph": [
    {"@type": "WebSite", "@id": SITE + "/en/#website", "name": "Japan Wrestling Archive", "url": SITE + "/en/", "inLanguage": "en", "description": DESC},
    {"@type": "CollectionPage", "name": "Japan Wrestling Archive", "url": SITE + "/en/", "isPartOf": {"@id": SITE + "/en/#website"},
     "hasPart": [{"@type": "WebPage", "name": "Tournaments", "url": SITE + "/en/events/"},
                 {"@type": "WebPage", "name": "Technique videos", "url": SITE + "/en/technique/"},
                 {"@type": "ContactPage", "name": "Contact", "url": SITE + "/en/contact.html"}]}]}, ensure_ascii=False) + '</script>')


def write(root, data, slugs):
    with open(os.path.join(root, "index.html"), encoding="utf-8") as f:
        s = f.read()
    from build_pages import LANG_REDIRECT_JS
    missing = []
    for ja, en in [(LANG_REDIRECT_JS + "\n", "")] + PAIRS:
        if s.count(ja) != 1:
            missing.append(ja[:60])
            continue
        s = s.replace(ja, en)
    if missing:
        raise SystemExit("英語版の検索ページを作れませんでした。index.html の次の部分が見つかりません(en_index.py の PAIRS を直してください): " + " / ".join(missing))
    # 構造化データ(JSON-LD)は英語のものに差し替える
    a = s.index(JSONLD_JA_START)
    b = s.index("</script>", a) + len("</script>")
    s = s[:a] + JSONLD_EN + s[b:]
    # 画面で使う英語名(大会名・会場名・用語など)を渡す
    names = {k: v for k, v in i18n.names_table().items()}
    for ev in data.get("events", []):
        if ev.get("fy_label") and ev["fy_label"] not in names:
            names[ev["fy_label"]] = i18n.fy_label(ev["fy_label"])
    inject = "<script>window.__EN=" + json.dumps(names, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + ";</script>\n"
    s = s.replace("<script>\nwindow.thumbFail", inject + "<script>\nwindow.thumbFail", 1)
    os.makedirs(os.path.join(root, "en"), exist_ok=True)
    with open(os.path.join(root, "en", "index.html"), "w", encoding="utf-8") as f:
        f.write(s)
