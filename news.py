"""
ニュース(/news/)のページを作る。日本語版だけ。

記事は2つのファイルで書く(どちらも手で編集する)。
  news.json            … 記事の一覧。1件 = {"slug", "date", "title", "category", "event_id", "lead", "tags", "file"}
                          slug は URL(/news/<slug>/)に使う半角英小文字・数字・ハイフン。date は YYYY-MM-DD。
                          event_id(開催回ID)を書くと、右の欄に大会ページへのリンクが出る。
                          image を書くと、見出しの下に写真を出し、SNS で共有したときの画像にも使う。
                          "image": {"file": "2026-univ-greco-final.jpg", "alt": "写真の説明", "credit": "撮影:…"}
                          写真は assets/news/ に入れる(長い辺 1600 ピクセルくらい・撮影データ(EXIF)は消す)
  articles/<slug>.md   … 記事の本文。次の書き方が使える
      空行            … 段落の区切り
      ## 見出し       … 小見出し
      | a | b |       … 表(1行目が見出しの行)
      [[p-xxxxxx|元木咲良]]                 … 選手ページへのリンク(選手IDは players.csv。公開していない選手は文字だけになる)
      [[event:wre-2026-kokutai-1012|国スポ]] … 開催回ページへのリンク
      [[news:2026-kokutai-day2|第2日]]       … ほかのニュース記事へのリンク
      [[https://…|出典]]                     … 外のサイトへのリンク
      [[photo:file.jpg|写真の説明|撮影:…]]     … 本文の途中の写真(1行だけで書く。写真は assets/news/。撮影者は省略可)

見た目は白地のニュース記事(ヘッダー・フッターはほかのページと同じ黒)。右の欄に、大会ページ・記事に出てくる選手・新着ニュースを出す。
"""
import html
import json
import os
import re

import i18n
import players
from i18n import U

NEWS_JSON = "news.json"
IMAGE_DIR = "assets/news"  # 記事の写真(手で入れる)
PHOTO_RE = re.compile(r"\[\[photo:([\w.-]+)\|([^\]|]+)(?:\|([^\]]+))?\]\]")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")
WEEK = "月火水木金土日"


def load(root, report):
    path = os.path.join(root, NEWS_JSON)
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8-sig") as f:
            items = json.load(f).get("articles", [])
    except (ValueError, OSError) as ex:
        report["errors"].append(f"news.json を読めませんでした: {ex}")
        return []
    out = []
    for i, a in enumerate(items, 1):
        slug = str(a.get("slug") or "")
        body_path = os.path.join(root, "articles", a.get("file") or f"{slug}.md")
        if not SLUG_RE.match(slug):
            report["errors"].append(f"news.json {i}件目: slug「{slug}」は半角英小文字・数字・ハイフンで書いてください")
        elif not re.match(r"^\d{4}-\d{2}-\d{2}$", str(a.get("date") or "")):
            report["errors"].append(f"news.json {i}件目: date は YYYY-MM-DD で書いてください")
        elif not os.path.exists(body_path):
            report["errors"].append(f"news.json {i}件目: 本文のファイル {os.path.relpath(body_path, root)} がありません")
        else:
            with open(body_path, encoding="utf-8-sig") as f:
                out.append(dict(a, body=f.read()))
    for a in out:
        img = a.get("image")
        if img and not os.path.exists(os.path.join(root, IMAGE_DIR, img.get("file") or "")):
            report["errors"].append(f"news.json「{a['slug']}」: 写真 {IMAGE_DIR}/{img.get('file')} がありません")
            a.pop("image")
        elif img:
            a["image"] = with_size(root, img)
    out.sort(key=lambda a: (a["date"], a["slug"]), reverse=True)
    return out


def with_size(root, img):
    """写真の縦横の大きさを足す(読み込み中に文章がずれないように)。分からないときはそのまま"""
    try:
        from PIL import Image
        with Image.open(os.path.join(root, IMAGE_DIR, img["file"])) as im:
            return dict(img, w=im.width, h=im.height)
    except Exception:  # Pillow が無い・root が分からないときは大きさを書かずに出す
        return img


def image_html(img, e, top=False):
    """記事の写真(見出しの下・本文の途中)"""
    wh = f' width="{img["w"]}" height="{img["h"]}"' if img.get("w") else ""
    return (f'<figure class="nw-fig"><img src="/{IMAGE_DIR}/{e(img["file"])}" alt="{e(img.get("alt") or "")}"{wh} decoding="async"'
            + (' fetchpriority="high">' if top else ' loading="lazy">')
            + (f'<figcaption>{e(img["credit"])}</figcaption>' if img.get("credit") else "") + "</figure>")


def fmt_day(d):
    import datetime
    y, m, dd = map(int, d.split("-"))
    w = WEEK[datetime.date(y, m, dd).weekday()]
    return f"{y}年{m}月{dd}日({w})"


def render_body(text, ctx, report, slug):
    """本文の書き方(上の説明)を HTML にする。出てきた選手を順に返す"""
    e = html.escape
    by_id = {p["id"]: p for p in ctx.get("players", [])}
    seen = []

    def link(m):
        target, label = m.group(1), m.group(2)
        if target.startswith("p-"):
            p = by_id.get(target)
            if not p:
                report["warnings"].append(f"{slug}: 選手 {target} は公開していないか、ありません(文字だけにしました)")
                return e(label)
            if p not in seen:
                seen.append(p)
            return f'<a href="{U("/players/" + p["id"] + "/")}">{e(label)}</a>'
        if target.startswith("event:"):
            eid = target[6:]
            if eid not in ctx["slugs"]:
                report["warnings"].append(f"{slug}: 開催回 {eid} のページがありません(文字だけにしました)")
                return e(label)
            return f'<a href="{U("/events/" + ctx["slugs"][eid] + "/")}">{e(label)}</a>'
        if target.startswith("news:"):
            ns = target[5:]
            if ns not in ctx.get("news_slugs", ()):
                report["warnings"].append(f"{slug}: ニュース {ns} がありません(文字だけにしました)")
                return e(label)
            return f'<a href="{U("/news/" + ns + "/")}">{e(label)}</a>'
        if target.startswith("https://"):
            return f'<a href="{e(target)}" target="_blank" rel="noopener">{e(label)} ↗</a>'
        report["warnings"].append(f"{slug}: リンク先「{target}」が分かりません")
        return e(label)

    def inline(s):
        parts = re.split(r"(\[\[[^\]|]+\|[^\]]+\]\])", s)
        return "".join(link(re.match(r"\[\[([^\]|]+)\|([^\]]+)\]\]", p)) if p.startswith("[[") else e(p) for p in parts)

    # 表のセルの「名前(所属)」は、選手検索にいる選手(公開・成人)と名前が1人だけ合えば選手ページへリンクする
    def name_key(x):
        return players.same_name(x).replace("・", "").replace("･", "").replace("=", "")
    by_name = {}
    for p in ctx.get("players", []):
        by_name.setdefault(name_key(p["name"]), []).append(p)

    def cell(c):
        if "[[" in c:
            return inline(c)
        if " − " in c:  # 「A(所属) − B(所属)」の対戦カードは、1人ずつリンクする
            return " − ".join(cell(x) for x in c.split(" − "))
        m = re.match(r"^([^(（|]+?)([(（].*)?$", c.strip())
        # 高校・中学の選手(未成年)はリンクしない(同じ名前の大人の選手ページへ誤ってつながないように)
        if m and re.search(r"(高|高校|中|中学|学園)[)）]|高等学校|中学校", m.group(2) or ""):
            return inline(c)
        hit = by_name.get(name_key(m.group(1))) if m and m.group(1).strip() else None
        if not hit or len(hit) != 1:
            return inline(c)
        p = hit[0]
        if p not in seen:
            seen.append(p)
        return f'<a href="{U("/players/" + p["id"] + "/")}">{e(m.group(1).strip())}</a>{e(m.group(2) or "")}'

    out = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l.rstrip() for l in block.strip().split("\n")]
        m = PHOTO_RE.fullmatch(lines[0]) if len(lines) == 1 else None
        if m:
            img = {"file": m.group(1), "alt": m.group(2), "credit": m.group(3) or ""}
            root = ctx.get("news_root")
            if root and not os.path.exists(os.path.join(root, IMAGE_DIR, img["file"])):
                report["errors"].append(f"{slug}: 写真 {IMAGE_DIR}/{img['file']} がありません")
                continue
            out.append(image_html(with_size(root, img), e))
            continue
        if lines[0].startswith("## "):
            out.append(f'<h2>{inline(lines[0][3:].strip())}</h2>')
            lines = lines[1:]
            if not lines:
                continue
        if all(l.startswith("|") for l in lines):
            rows = [[c.strip() for c in l.strip("|").split("|")] for l in lines if not re.match(r"^\|[\s:|-]+\|$", l)]
            th = "".join(f"<th>{inline(c)}</th>" for c in rows[0])
            trs = "".join("<tr>" + "".join(f'<td data-l="{e(rows[0][i]) if i < len(rows[0]) else ""}">{cell(c)}</td>' for i, c in enumerate(r)) + "</tr>" for r in rows[1:])
            out.append(f'<div class="nw-tbl"><table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>')
        else:
            out.append("<p>" + "<br>".join(inline(l) for l in lines) + "</p>")
    return "".join(out), seen


def by_player(root, ctx):
    """選手ID → その選手が出てくる記事(新しい順)。選手ページの「この選手が出てくるニュース」に使う"""
    quiet = {"errors": [], "warnings": []}
    arts = load(root, quiet)
    ctx = dict(ctx, news_slugs={a["slug"] for a in arts})
    out = {}
    for a in arts:
        for p in render_body(a["body"], ctx, quiet, a["slug"])[1]:
            out.setdefault(p["id"], []).append(a)
    return out


def by_event(root):
    """開催回ID → その開催回の記事(新しい順)。開催回ページの「この大会のニュース」に使う(#221)"""
    out = {}
    for a in load(root, {"errors": [], "warnings": []}):
        if a.get("event_id"):
            out.setdefault(a["event_id"], []).append(a)
    return out


def event_section(arts, e):
    """開催回ページの「この大会のニュース」。リンクの文字は記事の見出しのまま。選手ページへのリンクは足さない"""
    if not arts:
        return ""
    return ('<section id="ev-news"><h2>この大会のニュース</h2><ul class="pl-news">' + "".join(
        f'<li><a href="{U("/news/" + a["slug"] + "/")}">{e(a["title"])}</a><small>{e(fmt_day(a["date"]))}</small></li>'
        for a in arts) + "</ul></section>")


def build(root, ctx, bp, report):
    """ニュースのページ [(path, html, lastmod)]。日本語版だけ"""
    if i18n.en():
        return []
    arts = load(root, report)
    report["articles"] = len(arts)
    if not arts:
        return []
    e = bp.e
    pages = []
    ctx = dict(ctx, news_slugs={a["slug"] for a in arts}, news_root=root)
    rendered = {a["slug"]: render_body(a["body"], ctx, report, a["slug"]) for a in arts}

    def side(a, players):
        h = ""
        eid = a.get("event_id")
        if eid and eid in ctx["slugs"]:
            ev = ctx["events_by_id"][eid]
            s = ctx["S"].get(ev["series"], {"id": ev["series"], "name": ev["name"]})
            h += ('<section><h2>この大会のページ</h2><ul>'
                  f'<li><a href="{U("/events/" + ctx["slugs"][eid] + "/")}">{e(bp.event_name(ev, s))}<small>結果・大会情報・動画</small></a></li>'
                  f'<li><a href="{U("/events/" + s["id"] + "/")}">{e(bp.series_name(s))}<small>歴代の開催</small></a></li></ul></section>')
        if players:
            h += '<section><h2>記事に出てくる選手</h2><ul>'
            for p in players:
                n = len(p["results"])
                h += f'<li><a href="{U("/players/" + p["id"] + "/")}">{e(p["name"])}<small>{e(p["club"])}{"・大会成績" + str(n) + "件" if n else ""}</small></a></li>'
            h += "</ul></section>"
        others = [x for x in arts if x["slug"] != a["slug"]][:5]
        if others:
            h += '<section><h2>新着ニュース</h2><ul>' + "".join(
                f'<li><a href="{U("/news/" + x["slug"] + "/")}">{e(x["title"])}<small>{e(fmt_day(x["date"]))}</small></a></li>' for x in others) + "</ul></section>"
        return h

    # 記事のページ
    for a in arts:
        body, players = rendered[a["slug"]]
        path = f"/news/{a['slug']}/"
        crumbs = [("トップ", "/"), ("ニュース", "/news/"), (a["title"], None)]
        desc = a.get("lead") or a["title"]
        jsonld = {"@context": "https://schema.org", "@graph": [bp.breadcrumb_ld(crumbs), {
            "@type": "NewsArticle", "headline": a["title"], "datePublished": a["date"], "description": desc,
            "url": bp.SITE + path, "mainEntityOfPage": bp.SITE + path, "inLanguage": "ja",
            "author": {"@type": "Organization", "name": bp.SITE_NAME, "url": bp.SITE + "/about/"},
            "publisher": {"@type": "Organization", "name": bp.SITE_NAME}}]}
        # 記事の元になった発表・記事(news.json の sources)。AI や検索エンジンが出典を機械で読めるようにする
        srcs = [s for s in a.get("sources") or [] if isinstance(s, str) and s.startswith("http")]
        if srcs:
            jsonld["@graph"][1]["isBasedOn"] = srcs
        img = a.get("image")
        og = f"{bp.SITE}/{IMAGE_DIR}/{img['file']}" if img else ""
        if og:
            jsonld["@graph"][1]["image"] = og
        h = bp.head(f"{a['title']}|{bp.SITE_NAME}", desc, path, og, jsonld, ctx["css"], alternates=False)
        tags = "".join(f'<span>#{e(t)}</span>' for t in a.get("tags") or [])
        h += ('<div class="nw"><div class="wrap nw-grid"><main id="content" class="nw-main">' + bp.breadcrumb_html(crumbs)
              + (f'<p class="nw-cat">{e(a["category"])}</p>' if a.get("category") else "")
              + f'<h1>{e(a["title"])}</h1>'
              + f'<p class="nw-meta"><b>{e(bp.SITE_NAME)}</b><time datetime="{e(a["date"])}">{e(fmt_day(a["date"]))}</time></p>'
              + (image_html(img, e, top=True) if img else "")
              + f'<div class="nw-body">{body}</div>'
              + (f'<p class="nw-tags">{tags}</p>' if tags else "")
              + f'</main><aside class="nw-side">{side(a, players)}</aside></div></div>')
        h += bp.footer(ctx["as_of"])
        pages.append((path, h, a["date"]))

    # 一覧のページ
    path = "/news/"
    crumbs = [("トップ", "/"), ("ニュース", None)]
    desc = "レスリングの大会の結果や話題を、Japan Wrestling Channel がまとめたニュースです。"
    jsonld = {"@context": "https://schema.org", "@graph": [bp.breadcrumb_ld(crumbs), {
        "@type": "CollectionPage", "name": "ニュース", "url": bp.SITE + path,
        "hasPart": [{"@type": "NewsArticle", "headline": a["title"], "url": bp.SITE + f"/news/{a['slug']}/", "datePublished": a["date"]} for a in arts]}]}
    h = bp.head(f"ニュース|{bp.SITE_NAME}", desc, path, "", jsonld, ctx["css"], alternates=False)
    h += ('<div class="nw"><div class="wrap nw-grid"><main id="content" class="nw-main">' + bp.breadcrumb_html(crumbs)
          + f'<h1>ニュース</h1><p class="nw-lead">{e(desc)}</p><ul class="nw-list">')
    for a in arts:
        h += (f'<li><a href="{U("/news/" + a["slug"] + "/")}">'
              + (f'<span class="nw-cat">{e(a["category"])}</span>' if a.get("category") else "")
              + f'<span class="nw-t">{e(a["title"])}</span>'
              + (f'<span class="nw-l">{e(a["lead"])}</span>' if a.get("lead") else "")
              + f'<time datetime="{e(a["date"])}">{e(fmt_day(a["date"]))}</time></a></li>')
    h += '</ul></main><aside class="nw-side">' + side({"slug": ""}, []) + "</aside></div></div>"
    h += bp.footer(ctx["as_of"])
    pages.append((path, h, arts[0]["date"]))
    return pages


# 白地の記事。ヘッダー・フッターはほかのページと同じ黒のまま、間の帯だけ白テーマの色にする
NEWS_CSS = """
.nw{--bg:#f2f3f5;--surface:#ffffff;--surface-2:#eef0f4;--ink:#1d1f23;--ink2:#4a4f58;--ink3:#626873;--line:#e2e4e8;--line-hi:#c4c8d0;
  --pink:#c8102e;--pink-deep:#a50d26;--pink-line:#f0bcc4;--link:#0b57c2;background:var(--bg);color:var(--ink);padding:18px 0 48px;color-scheme:light}
.nw-grid{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:20px;align-items:start}
@media (max-width:860px){.nw-grid{grid-template-columns:1fr}}
.nw-main{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:22px 28px 28px;min-width:0}
@media (max-width:520px){.nw-main{padding:16px 16px 22px}}
.nw .crumbs a{color:var(--ink2)}
.nw h1{font-size:26px;line-height:1.5;margin:4px 0 10px;font-weight:700;letter-spacing:.01em;text-wrap:balance}
@media (max-width:520px){.nw h1{font-size:21px}}
.nw-cat{display:inline-block;margin:0;font-size:12px;font-weight:700;color:var(--pink)}
.nw-meta{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:13px;color:var(--ink3);margin:0 0 18px;padding-bottom:14px;border-bottom:1px solid var(--line)}
.nw-meta b{color:var(--ink)}
.nw-body{font-size:16px;line-height:1.95;max-width:680px}
.nw-fig{margin:0 0 22px;max-width:680px}
.nw-fig img{display:block;width:100%;height:auto;border-radius:6px;background:var(--surface-2)}
.nw-fig figcaption{margin-top:6px;font-size:12px;color:var(--ink3);text-align:right}
.nw-body p{margin:0 0 1.2em}
.nw-body a{color:var(--link);text-decoration:none}
.nw-body a:hover{text-decoration:underline}
.nw-body h2{font-size:17px;line-height:1.5;margin:1.8em 0 .7em;padding-left:10px;border-left:4px solid var(--pink)}
.nw-tbl{overflow-x:auto;border:1px solid var(--line);border-radius:4px;margin:0 0 1.2em}
.nw-tbl table{border-collapse:collapse;width:100%;min-width:520px;font-size:14px;line-height:1.6}
.nw-tbl th,.nw-tbl td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
.nw-tbl th{background:var(--surface-2);color:var(--ink2);font-weight:500;font-size:12.5px;white-space:nowrap}
.nw-tbl td:first-child{white-space:nowrap;color:var(--ink2);font-variant-numeric:tabular-nums}
/* スマートフォンでは表を1行ずつのカードにする(横にはみ出さない) */
@media (max-width:520px){.nw-tbl{border:0;overflow:visible}.nw-tbl table{min-width:0}.nw-tbl thead{display:none}
  .nw-tbl tr{display:block;border:1px solid var(--line);border-radius:4px;padding:8px 12px;margin-bottom:8px}
  .nw-tbl td{display:flex;gap:10px;border:0;padding:2px 0}
  .nw-tbl td::before{content:attr(data-l);flex:0 0 4.5em;color:var(--ink3);font-size:12px;padding-top:2px}
  .nw-tbl td:nth-child(2){font-weight:700}}
.nw-tags{display:flex;flex-wrap:wrap;gap:6px;margin:18px 0 0}
.nw-tags span{background:var(--surface-2);font-size:12.5px;padding:3px 10px;border-radius:999px;color:var(--ink2)}
.nw-side{display:grid;gap:16px;min-width:0}
.nw-side section{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:14px 16px}
.nw-side h2{font-size:14px;margin:0 0 6px;padding-bottom:8px;border-bottom:2px solid var(--pink)}
.nw-side ul{list-style:none;margin:0;padding:0}
.nw-side li+li{border-top:1px solid var(--line)}
.nw-side a{display:block;padding:9px 0;color:var(--ink);text-decoration:none;font-size:14px;line-height:1.55}
.nw-side a:hover{color:var(--link)}
.nw-side small{display:block;color:var(--ink3);font-size:12px}
.nw-lead{color:var(--ink2);margin:0 0 10px}
.nw-list{list-style:none;margin:0;padding:0}
.nw-list li{border-top:1px solid var(--line)}
.nw-list a{display:grid;gap:3px;padding:14px 0;color:var(--ink);text-decoration:none}
.nw-list a:hover .nw-t{color:var(--link);text-decoration:underline}
.nw-list .nw-t{font-size:17px;font-weight:700;line-height:1.5}
.nw-list .nw-l{font-size:14px;color:var(--ink2);line-height:1.7}
.nw-list time{font-size:12.5px;color:var(--ink3)}
.nw :focus-visible{outline-color:var(--pink)}
"""
