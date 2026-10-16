"""
ニュース(/news/)のページを作る。日本語版だけ。

記事は2つのファイルで書く(どちらも手で編集する)。
  news.json            … 記事の一覧。1件 = {"slug", "date", "title", "category", "event_id", "lead", "tags", "file"}
                          slug は URL(/news/<slug>/)に使う半角英小文字・数字・ハイフン。date は YYYY-MM-DD。
                          event_id(開催回ID)を書くと、右の欄に大会ページへのリンクが出る。
  articles/<slug>.md   … 記事の本文。次の書き方が使える
      空行            … 段落の区切り
      ## 見出し       … 小見出し
      | a | b |       … 表(1行目が見出しの行)
      [[p-xxxxxx|元木咲良]]                 … 選手ページへのリンク(選手IDは players.csv。公開していない選手は文字だけになる)
      [[event:wre-2026-kokutai-1012|国スポ]] … 開催回ページへのリンク
      [[news:2026-kokutai-day2|第2日]]       … ほかのニュース記事へのリンク
      [[https://…|出典]]                     … 外のサイトへのリンク

見た目は白地のニュース記事(ヘッダー・フッターはほかのページと同じ黒)。右の欄に、大会ページ・記事に出てくる選手・新着ニュースを出す。
"""
import html
import json
import os
import re

import i18n
from i18n import U

NEWS_JSON = "news.json"
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
    out.sort(key=lambda a: (a["date"], a["slug"]), reverse=True)
    return out


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

    out = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l.rstrip() for l in block.strip().split("\n")]
        if lines[0].startswith("## "):
            out.append(f'<h2>{inline(lines[0][3:].strip())}</h2>')
            lines = lines[1:]
            if not lines:
                continue
        if all(l.startswith("|") for l in lines):
            rows = [[c.strip() for c in l.strip("|").split("|")] for l in lines if not re.match(r"^\|[\s:|-]+\|$", l)]
            th = "".join(f"<th>{inline(c)}</th>" for c in rows[0])
            trs = "".join("<tr>" + "".join(f'<td data-l="{e(rows[0][i]) if i < len(rows[0]) else ""}">{inline(c)}</td>' for i, c in enumerate(r)) + "</tr>" for r in rows[1:])
            out.append(f'<div class="nw-tbl"><table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>')
        else:
            out.append("<p>" + "<br>".join(inline(l) for l in lines) + "</p>")
    return "".join(out), seen


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
    ctx = dict(ctx, news_slugs={a["slug"] for a in arts})
    rendered = {a["slug"]: render_body(a["body"], ctx, report, a["slug"]) for a in arts}

    def side(a, players):
        h = ""
        eid = a.get("event_id")
        if eid and eid in ctx["slugs"]:
            ev = ctx["events_by_id"][eid]
            s = ctx["S"].get(ev["series"], {"id": ev["series"], "name": ev["name"]})
            h += ('<section><h3>この大会のページ</h3><ul>'
                  f'<li><a href="{U("/events/" + ctx["slugs"][eid] + "/")}">{e(bp.event_name(ev, s))}<small>結果・大会情報・動画</small></a></li>'
                  f'<li><a href="{U("/events/" + s["id"] + "/")}">{e(bp.series_name(s))}<small>歴代の開催</small></a></li></ul></section>')
        if players:
            h += '<section><h3>記事に出てくる選手</h3><ul>'
            for p in players:
                n = len(p["results"])
                h += f'<li><a href="{U("/players/" + p["id"] + "/")}">{e(p["name"])}<small>{e(p["club"])}{"・大会成績" + str(n) + "件" if n else ""}</small></a></li>'
            h += "</ul></section>"
        others = [x for x in arts if x["slug"] != a["slug"]][:5]
        if others:
            h += '<section><h3>新着ニュース</h3><ul>' + "".join(
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
            "url": bp.SITE + path, "publisher": {"@type": "Organization", "name": bp.SITE_NAME}}]}
        h = bp.head(f"{a['title']}|{bp.SITE_NAME}", desc, path, "", jsonld, ctx["css"], alternates=False)
        tags = "".join(f'<span>#{e(t)}</span>' for t in a.get("tags") or [])
        h += ('<div class="nw"><div class="wrap nw-grid"><main id="content" class="nw-main">' + bp.breadcrumb_html(crumbs)
              + (f'<p class="nw-cat">{e(a["category"])}</p>' if a.get("category") else "")
              + f'<h1>{e(a["title"])}</h1>'
              + f'<p class="nw-meta"><b>{e(bp.SITE_NAME)}</b><time datetime="{e(a["date"])}">{e(fmt_day(a["date"]))}</time></p>'
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
.nw-side h3{font-size:14px;margin:0 0 6px;padding-bottom:8px;border-bottom:2px solid var(--pink)}
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
