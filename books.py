"""
書籍(/books/)のページを作る。日本語版だけ。ブクログのように、表紙を本棚に並べる。

登録は books.json(手で編集する)に ISBN を書くだけ。
  {"books": [{"isbn": "9784…", "category": "技術書", "players": ["p-xxxxxx"], "comment": "運営者のひとこと", "added": "2026-10-14"}]}
  - isbn は 13 けた(ハイフンなしでもありでもよい)。10 けたでもよい
  - isbn の代わりに、ブクログの本のページの URL(https://booklog.jp/item/1/4062880326 など)を "booklog" に書いてもよい。URL の中の ISBN を使う
  - "booklog_shelf" にブクログの本棚の URL を書くと、毎日の自動更新でその本棚の本を全部読み、この本棚に入れる
    (books に書いた本はそちらの設定が優先。本棚にだけある本は棚の名前が SHELF_CATEGORY になる。Kindle 本など ISBN の無い本は入らない)
  - category は本棚の棚の名前(技術書・自伝・雑誌など)。書かないと「その他」
  - players に選手ID(players.csv)を書くと、本のページから選手ページへ、選手ページから本へリンクする
  - title・authors・publisher・pubdate・cover を書くと、取ってきた内容より優先する(データが無い本や、直したいとき)

題名・著者・出版社・発売日・表紙・内容紹介は、毎日の自動更新(update_site.py)のときに openBD から取ってきて
books_cache.json(自動で作られる。手で編集しない)に入れておく。取れなかった本は、次の自動更新でもう一度試す。
"""
import html
import json
import os
import re

import i18n
from i18n import U

BOOKS_JSON = "books.json"
CACHE_JSON = "books_cache.json"
OPENBD = "https://api.openbd.jp/v1/get?isbn="
SHELF_CATEGORY = "本棚"
SHELF_MAX_PAGES = 50
UA = {"User-Agent": "Mozilla/5.0 (compatible; japanwrestlingchannel.com books)"}


def norm_isbn(s):
    """ISBN を 13 けたにそろえる。おかしな形なら空文字"""
    d = re.sub(r"[^0-9Xx]", "", str(s or "")).upper()
    if len(d) == 10:
        if sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(d)) % 11:
            return ""
        d = "978" + d[:9]
        return d + str((10 - sum((1 if i % 2 == 0 else 3) * int(c) for i, c in enumerate(d)) % 10) % 10)
    if len(d) == 13 and d.isdigit() and sum((1 if i % 2 == 0 else 3) * int(c) for i, c in enumerate(d)) % 10 == 0:
        return d
    return ""


def book_isbn(b):
    """books.json の1件の ISBN(13 けた)。isbn が無ければ、ブクログの URL の中の ISBN-10 から作る"""
    if b.get("isbn"):
        return norm_isbn(b["isbn"])
    m = re.search(r"booklog\.jp/(?:item/\d+|users/[^/]+/archives/\d+)/([0-9]{9}[0-9Xx])", str(b.get("booklog") or ""))
    return norm_isbn(m.group(1)) if m else ""


def isbn10(isbn13):
    """Amazon のリンク用の 10 けた(978 で始まる本だけ)"""
    if not isbn13.startswith("978"):
        return ""
    b = isbn13[3:12]
    c = (11 - sum((10 - i) * int(x) for i, x in enumerate(b)) % 11) % 11
    return b + ("X" if c == 10 else str(c))


def load_json(path, default):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def parse_openbd(rec):
    """openBD の1件から、使う項目だけを取り出す"""
    s = rec.get("summary") or {}
    out = {"title": s.get("title") or "", "authors": s.get("author") or "", "publisher": s.get("publisher") or "",
           "pubdate": s.get("pubdate") or "", "cover": s.get("cover") or "", "description": ""}
    try:
        for t in rec["onix"]["CollateralDetail"].get("TextContent", []):
            # 03 = 内容紹介(長いほう)、02 = 短い紹介
            if t.get("TextType") in ("03", "02") and t.get("Text"):
                out["description"] = t["Text"].strip()
                if t.get("TextType") == "03":
                    break
    except (KeyError, TypeError, AttributeError):
        pass
    # 著者は「名前/著」のような書き方なので、記号をそろえる
    out["authors"] = re.sub(r"\s*/\s*", "/", out["authors"]).strip()
    return out


def shelf_isbns(html_text, user):
    """ブクログの本棚のページから、その人の本(/users/<user>/archives/1/<ISBN-10>)の ISBN(13 けた)を順に取り出す。
    おすすめ・ランキングなど、ほかの本へのリンク(/item/…)は数えない"""
    out = []
    for m in re.finditer(r"/users/" + re.escape(user) + r"/archives/\d+/([0-9]{9}[0-9Xx])\b", html_text):
        i = norm_isbn(m.group(1))
        if i and i not in out:
            out.append(i)
    return out


def page_url(url, n):
    url = re.sub(r"([?&])page=\d+&?", r"\1", url).rstrip("?&")
    return url + ("&" if "?" in url else "?") + f"page={n}"


def items_from_api(data):
    """ブクログの本棚の API の答え(JSON)から、本を {isbn, title, authors, cover} の形で取り出す。
    答えの形が少し変わっても読めるよう、url / id / asin に ISBN-10 を持つものを全部探す"""
    out, seen = [], set()

    def walk(x):
        if isinstance(x, dict):
            key = " ".join(str(x.get(k) or "") for k in ("id", "asin", "isbn", "url", "item_url"))
            m = re.search(r"(?<![0-9A-Za-z])([0-9]{9}[0-9Xx]|97[89][0-9]{10})(?![0-9A-Za-z])", key)
            isbn = norm_isbn(m.group(1)) if m else ""
            if isbn and isbn not in seen:
                seen.add(isbn)
                out.append({"isbn": isbn, "title": str(x.get("title") or "").strip(),
                            "authors": str(x.get("author") or x.get("authors") or "").strip(),
                            "cover": str(x.get("image") or x.get("image_url") or x.get("large_image") or "").strip()})
                return
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(data)
    return out


def fetch_shelf(url, requests, report):
    """ブクログの本棚の本を全部集める。まずブログ用の本棚 API を使い、だめならページを読む。
    うまくいかなかったときに直せるよう、試したことを report["shelf_tries"] に残す"""
    import time
    m = re.match(r"https://booklog\.jp/users/([^/?#]+)", url)
    if not m:
        raise ValueError("ブクログの本棚の URL(https://booklog.jp/users/…)ではありません")
    user = m.group(1)
    q = re.search(r"[?&]status=(\d+)", url)
    status = f"&status={q.group(1)}" if q else ""
    tries = report.setdefault("shelf_tries", [])
    for api in (f"https://api.booklog.jp/v2/json/{user}?count=1000{status}", f"https://api.booklog.jp/json/{user}?count=1000{status}"):
        try:
            r = requests.get(api, headers=UA, timeout=30)
            note = {"url": api, "status": r.status_code, "bytes": len(r.content)}
            if r.ok:
                items = items_from_api(r.json())
                note["books"] = len(items)
                tries.append(note)
                if items:
                    return items
            else:
                tries.append(note)
        except Exception as ex:
            tries.append({"url": api, "error": str(ex)[:200]})
    found = []
    for n in range(1, SHELF_MAX_PAGES + 1):
        r = requests.get(page_url(url, n), headers=UA, timeout=30)
        r.raise_for_status()
        new = [i for i in shelf_isbns(r.text, user) if i not in found]
        if n == 1:
            tries.append({"url": page_url(url, 1), "status": r.status_code, "bytes": len(r.text), "books": len(new),
                          "links": re.findall(r'href="([^"]*(?:item|archives)[^"]*)"', r.text)[:5]})
        if not new:
            if n == 1:
                raise ValueError("本棚の1ページ目に本が見つかりませんでした(ブクログのページの作りが変わったかもしれません)")
            break
        found += new
        time.sleep(1)
    return [{"isbn": i} for i in found]


def shelf_list(cache):
    return (cache.get("_shelf") or {}).get("isbns") or []


def shelf_item(cache, isbn):
    """ブクログの本棚 API で取れた、その本の題名・著者・表紙(openBD に無い本の代わりに使う)"""
    return ((cache.get("_shelf") or {}).get("items") or {}).get(isbn) or {}


def fetch(root="."):
    """ブクログの本棚と、books.json の本のうち、まだ取ってきていないものを openBD から取る。失敗してもサイトの更新は止めない"""
    import datetime
    cfg = load_json(os.path.join(root, BOOKS_JSON), {})
    books = cfg.get("books", [])
    cache_path = os.path.join(root, CACHE_JSON)
    cache = load_json(cache_path, {})
    report = {"asked": 0, "found": 0, "missing": []}
    try:
        import requests
    except ImportError as ex:
        report["error"] = str(ex)
        return report
    shelf = str(cfg.get("booklog_shelf") or "").strip()
    if shelf.startswith("https://booklog.jp/"):
        try:
            items = fetch_shelf(shelf, requests, report)
            isbns = [x["isbn"] for x in items]
            if isbns or not shelf_list(cache):
                cache["_shelf"] = {"url": shelf, "isbns": isbns, "fetched": datetime.date.today().isoformat(),
                                   "items": {x["isbn"]: {k: v for k, v in x.items() if k != "isbn" and v} for x in items if x.get("title")}}
            report["shelf"] = len(isbns)
        except Exception as ex:
            report["shelf_error"] = str(ex)
            print(f"[書籍] ブクログの本棚を読めませんでした(前回の内容を使います): {ex}")
    want = [i for i in list(dict.fromkeys([book_isbn(b) for b in books] + shelf_list(cache)))
            if i and not (cache.get(i) or {}).get("title") and not (cache.get(i) or {}).get("tries", 0) >= 3]
    report["asked"] = len(want)
    try:
        for k in range(0, len(want), 100):
            part = want[k:k + 100]
            r = requests.get(OPENBD + ",".join(part), timeout=30)
            r.raise_for_status()
            for isbn, rec in zip(part, r.json()):
                if rec:
                    cache[isbn] = parse_openbd(rec)
                    report["found"] += 1
                else:
                    # openBD に無い本。3回試してだめなら、books.json に title を書くまで聞かない
                    cache[isbn] = {"tries": (cache.get(isbn) or {}).get("tries", 0) + 1}
                    report["missing"].append(isbn)
    except Exception as ex:
        report["error"] = str(ex)
        print(f"[書籍] 本のデータを取れませんでした(次の更新でもう一度試します): {ex}")
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return report


def load(root, ctx, report):
    """books.json と books_cache.json から、ページに出す本の一覧を作る"""
    raw = load_json(os.path.join(root, BOOKS_JSON), None)
    if raw is None:
        return []
    cache = load_json(os.path.join(root, CACHE_JSON), {})
    by_id = {p["id"]: p for p in ctx.get("players", [])}
    out, seen = [], set()
    listed = {book_isbn(b) for b in raw.get("books", [])}
    fetched = (cache.get("_shelf") or {}).get("fetched") or ""
    # ブクログの本棚にだけある本(本棚の並び順を保つため、新しい順の日付を少しずつずらす)
    extra = [{"isbn": x, "category": SHELF_CATEGORY, "added": fetched, "_order": k} for k, x in enumerate(shelf_list(cache)) if x not in listed]
    for i, b in enumerate(list(raw.get("books", [])) + extra, 1):
        isbn = book_isbn(b)
        if not isbn:
            report["errors"].append(f"books.json {i}件目: ISBN「{b.get('isbn') or b.get('booklog') or ''}」の形が正しくありません(ブクログの URL は本のページのものを書いてください)")
            continue
        if isbn in seen:
            report["warnings"].append(f"books.json {i}件目: ISBN {isbn} が2回書かれているので、2回目は無視しました")
            continue
        seen.add(isbn)
        # 取れなかった項目は空にそろえる(ブクログの本棚にだけある本は、著者などが無いことがある)
        d = {k: "" for k in ("title", "authors", "publisher", "pubdate", "cover", "description")}
        d.update({k: v for k, v in (cache.get(isbn) or {}).items() if k in d and v})
        alt = shelf_item(cache, isbn)
        if not d.get("title"):
            d.update({k: v for k, v in alt.items() if k in d and v})
        elif not d.get("cover") and alt.get("cover"):
            d["cover"] = alt["cover"]
        for k in ("title", "authors", "publisher", "pubdate", "cover", "description"):
            if b.get(k):
                d[k] = b[k]
        if not d.get("title"):
            if b.get("_order") is not None:
                report["shelf_without_data"] = report.get("shelf_without_data", 0) + 1
                continue
            report["warnings"].append(f"{isbn}: 題名がまだ分かりません(次の自動更新で openBD から取ります。データが無い本は books.json に title を書いてください)")
            continue
        players = []
        for pid in b.get("players") or []:
            if pid in by_id:
                players.append(by_id[pid])
            else:
                report["warnings"].append(f"{isbn}: 選手 {pid} は公開していないか、ありません")
        out.append(dict(d, isbn=isbn, category=b.get("category") or "その他", comment=b.get("comment") or "",
                        added=b.get("added") or "", players=players, order=b.get("_order", -1)))
    # 新しく足した順。ブクログの本棚の本は本棚の並び順(上ほど新しい)
    out.sort(key=lambda x: (x["added"], -x["order"]), reverse=True)
    report["books"] = len(out)
    return out


def fmt_pubdate(s):
    m = re.match(r"^(\d{4})-?(\d{2})?-?(\d{2})?", s or "")
    if not m:
        return s or ""
    y, mo, d = m.groups()
    return f"{y}年" + (f"{int(mo)}月" if mo else "") + (f"{int(d)}日" if d and d != "00" else "")


def cover_html(b, e, cls="bk-cover"):
    """表紙。画像が無い・読めないときは題名を書いた札にする"""
    title = f'<span class="bk-ph">{e(b["title"])}</span>'
    if not b.get("cover"):
        return f'<span class="{cls} none">{title}</span>'
    return (f'<span class="{cls}">{title}<img src="{e(b["cover"])}" alt="" loading="lazy" decoding="async" '
            f'referrerpolicy="no-referrer" onerror="this.remove()"></span>')


def books_for_player(ctx, pid):
    return [b for b in ctx.get("books", []) if any(p["id"] == pid for p in b["players"])]


def player_section(p, ctx, bp):
    """選手ページの「関連する本」の欄(日本語版だけ)"""
    if i18n.en():
        return ""
    lst = books_for_player(ctx, p["id"])
    if not lst:
        return ""
    e = bp.e
    return ('<h2>関連する本</h2><ul class="bk-shelf bk-small">' + "".join(
        f'<li><a href="{U("/books/" + b["isbn"] + "/")}">{cover_html(b, e)}<span class="bk-t">{e(b["title"])}</span></a></li>' for b in lst) + "</ul>")


def build(root, ctx, bp, report):
    """書籍のページ [(path, html, lastmod)]。日本語版だけ"""
    if i18n.en():
        return []
    books = ctx.get("books", [])
    e = bp.e
    pages = []
    for b in books:
        path = f"/books/{b['isbn']}/"
        crumbs = [("トップ", "/"), ("書籍", "/books/"), (b["title"], None)]
        desc = f"{b['title']}" + (f"({b['authors']})" if b["authors"] else "") + "。レスリングの本の紹介。"
        jsonld = {"@context": "https://schema.org", "@graph": [bp.breadcrumb_ld(crumbs), dict({
            "@type": "Book", "name": b["title"], "isbn": b["isbn"], "url": bp.SITE + path},
            **({"author": b["authors"]} if b["authors"] else {}), **({"publisher": b["publisher"]} if b["publisher"] else {}),
            **({"image": b["cover"]} if b.get("cover") else {}))]}
        h = bp.head(f"{b['title']}|書籍|{bp.SITE_NAME}", desc, path, b.get("cover") or "", jsonld, ctx["css"], alternates=False)
        facts = [("著者", b["authors"]), ("出版社", b["publisher"]), ("発売日", fmt_pubdate(b["pubdate"])), ("ISBN", b["isbn"]), ("棚", b["category"])]
        h += '<main id="content" class="wrap page bk-page">' + bp.breadcrumb_html(crumbs)
        h += f'<div class="bk-detail">{cover_html(b, e, "bk-cover bk-big")}<div class="bk-info"><h1>{e(b["title"])}</h1>'
        h += '<dl class="facts">' + "".join(f"<dt>{k}</dt><dd>{e(v)}</dd>" for k, v in facts if v) + "</dl>"
        a10 = isbn10(b["isbn"])
        links = [(f"https://www.hanmoto.com/bd/isbn/{b['isbn']}", "版元ドットコム"), (f"https://calil.jp/book/{a10 or b['isbn']}", "図書館で探す(カーリル)")]
        if a10:
            links.append((f"https://booklog.jp/item/1/{a10}", "ブクログ"))
            links.append((f"https://www.amazon.co.jp/dp/{a10}", "Amazon"))
        h += '<p class="elinks">' + "".join(f'<a class="elink" href="{e(u)}" target="_blank" rel="noopener">{t} ↗</a>' for u, t in links) + "</p></div></div>"
        if b["comment"]:
            h += f'<section class="section"><h2>運営者のひとこと</h2><p class="bk-comment">{e(b["comment"])}</p></section>'
        if b.get("description"):
            paras = "".join(f"<p>{e(x)}</p>" for x in re.split(r"\n\s*\n|\n", b["description"]) if x.strip())
            h += f'<section class="section"><h2>内容紹介</h2><div class="bk-desc">{paras}</div><p class="hint">出版社の紹介文(openBD)より</p></section>'
        if b["players"]:
            h += '<section class="section"><h2>この本に関係する選手</h2><ul class="bk-players">' + "".join(
                f'<li><a href="{U("/players/" + p["id"] + "/")}">{e(p["name"])}</a></li>' for p in b["players"]) + "</ul></section>"
        h += "</main>" + bp.footer(ctx["as_of"])
        pages.append((path, h, b["added"] or ctx["as_of"]))

    # 本棚(一覧)。棚(category)ごとに表紙を並べる
    path = "/books/"
    crumbs = [("トップ", "/"), ("書籍", None)]
    desc = f"レスリングの技術書・選手の本・雑誌など{len(books)}冊を、表紙の本棚で紹介しています。"
    jsonld = {"@context": "https://schema.org", "@graph": [bp.breadcrumb_ld(crumbs), {
        "@type": "CollectionPage", "name": "書籍", "url": bp.SITE + path,
        "hasPart": [{"@type": "Book", "name": b["title"], "isbn": b["isbn"], "url": bp.SITE + f"/books/{b['isbn']}/"} for b in books]}]}
    h = bp.head(f"書籍({len(books)}冊)|{bp.SITE_NAME}", desc, path, "", jsonld, ctx["css"], alternates=False)
    h += '<main id="content" class="wrap page bk-page">' + bp.breadcrumb_html(crumbs) + f'<h1>書籍 <small class="bk-n"><b class="num">{len(books)}</b>冊</small></h1>'
    if books:
        h += f'<p class="lead">{e(desc)}表紙を押すと、内容紹介や関係する選手が見られます。</p>'
    else:
        h += '<p class="lead">レスリングの技術書・選手の本・雑誌などを、表紙の本棚で紹介するページです。いま準備中です。</p>'
    cats = list(dict.fromkeys(b["category"] for b in books))
    if len(cats) > 1:
        h += '<nav class="bk-cats" aria-label="棚">' + "".join(f'<a href="#shelf-{i}">{e(c)}<small>{sum(1 for b in books if b["category"] == c)}</small></a>' for i, c in enumerate(cats)) + "</nav>"
    for i, c in enumerate(cats):
        lst = [b for b in books if b["category"] == c]
        h += f'<section class="section" id="shelf-{i}"><h2>{e(c)} <small class="bk-n">{len(lst)}冊</small></h2><ul class="bk-shelf">'
        for b in lst:
            h += (f'<li><a href="{U("/books/" + b["isbn"] + "/")}">{cover_html(b, e)}'
                  f'<span class="bk-t">{e(b["title"])}</span><span class="bk-a">{e(b["authors"])}</span></a></li>')
        h += "</ul></section>"
    h += "</main>" + bp.footer(ctx["as_of"])
    pages.append((path, h, ctx["as_of"]))
    return pages


BOOK_CSS = """
.bk-n{font-size:14px;font-weight:500;color:var(--ink3);margin-left:6px}
.bk-cats{display:flex;flex-wrap:wrap;gap:8px;margin:4px 0 18px}
.bk-cats a{display:inline-flex;gap:6px;align-items:center;padding:6px 14px;border:1px solid var(--line);border-radius:999px;color:var(--ink);text-decoration:none;font-size:14px;background:var(--surface)}
.bk-cats a:hover{border-color:var(--pink)}
.bk-cats small{color:var(--ink3);font-size:12px}
.bk-shelf{list-style:none;margin:10px 0 0;padding:0 0 4px;display:grid;grid-template-columns:repeat(auto-fill,minmax(128px,1fr));gap:22px 16px;border-bottom:6px solid var(--surface-2)}
.bk-shelf.bk-small{grid-template-columns:repeat(auto-fill,minmax(100px,1fr));border-bottom:0}
.bk-shelf li{min-width:0}
.bk-shelf a{display:flex;flex-direction:column;gap:6px;color:var(--ink);text-decoration:none}
.bk-shelf a:hover .bk-cover{transform:translateY(-3px);box-shadow:var(--shadow-hi)}
.bk-shelf a:hover .bk-t{color:var(--pink)}
.bk-cover{position:relative;display:block;aspect-ratio:2/3;max-width:100%;border-radius:3px;overflow:hidden;background:linear-gradient(150deg,var(--grad-a),var(--grad-b));box-shadow:0 2px 6px rgba(0,0,0,.35);transition:transform .2s,box-shadow .2s}
.bk-cover img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;background:var(--surface)}
.bk-ph{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;padding:10px;text-align:center;font-size:12px;font-weight:700;line-height:1.5;color:#fff;overflow:hidden}
.bk-t{font-size:13px;font-weight:500;line-height:1.45;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.bk-a{font-size:12px;color:var(--ink3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bk-detail{display:grid;grid-template-columns:200px minmax(0,1fr);gap:28px;align-items:start;margin:6px 0 10px}
@media (max-width:600px){.bk-detail{grid-template-columns:120px minmax(0,1fr);gap:16px}.bk-page h1{font-size:20px}}
.bk-big{box-shadow:0 8px 24px rgba(0,0,0,.4)}
.bk-info h1{margin-top:0}
.bk-comment{margin:0;padding:14px 16px;border:1px solid var(--line);border-radius:8px;background:var(--surface);max-width:70ch}
.bk-desc{max-width:70ch;color:var(--ink2)}
.bk-desc p{margin:0 0 .9em}
.bk-players{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:8px}
.bk-players a{display:inline-block;padding:6px 14px;border:1px solid var(--pink-line);border-radius:999px;color:var(--pink);text-decoration:none;font-weight:700;font-size:14px}
"""
