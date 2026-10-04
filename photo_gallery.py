"""
写真ギャラリー(大会ページ・開催回ページ)

  photos/       … 元の写真を入れるフォルダ(JPG / PNG / WebP)。手でアップロードする
  photos.json   … どの写真をどのページに載せるかの設定。手で編集する
  assets/photos/ … 自動生成。縮小した写真(長辺1600px)とサムネイル(長辺480px)。手で編集しない

photos.json の1件の書き方
  {"file": "interhigh-2024-01.jpg", "page": "interhigh/2024",
   "caption": "決勝の表彰式", "credit": "撮影:山田太郎", "confirmed": true, "hidden": false}

  - page は大会ページまたは開催回ページのURLの /events/ の後ろ(例: "interhigh" や "interhigh/2024")
  - 大会ページに載せる写真は "year": "2026" を書くと、写真ページで「2026年」として表示・並べる
  - confirmed が true の写真だけ表示する(未成年が写っている場合は、掲載してよいか確認してから true にする)
  - hidden を true にすると一時的に表示しない
  - credit(撮影者・提供元)が空のときはビルド時に警告を出す

ルール
  - 縮小した写真からは撮影場所(GPS)などの情報を取り除く。元の写真には残るので、アップロード前に消しておく
  - 表示しなくなった写真の縮小版は assets/photos/ から自動で削除する
  - 縮小版を作ったあとは、photos/ の元の写真を消してよい(assets/photos/manifest.json の記録から縮小版を使い続ける)。
    元の写真は公開リポジトリの容量を使い、撮影場所などの情報が残ることがあるため
  - 1ページの写真はファイル名の順に並べ、最初は GALLERY_FIRST 枚だけ表示する(残りは「もっと見る」で表示)
  - photos.json の albums に書いたページには、ギャラリーの下に外部アルバム(Google フォトなど)へのボタンを出す
      "albums": [{"page": "intercollegiate/2026", "url": "https://photos.app.goo.gl/…", "count": "1000"}]
    (アルバムを公開してよいか、撮影者に確認してから書く)
    1ページに複数書ける。year を書くとボタンが「2026年の写真をアルバムで見る」になる。credit を書くとボタンの下に出す
  - 配信動画が無い開催回でも、写真・アルバムがあれば開催回ページを作る(wanted_pages)
  - Pillow が入っていない環境では新しい写真は作れない(作成済みの縮小版があればそれを使う)
"""
import hashlib
import json
import os
import re
from collections import defaultdict
from urllib.parse import unquote

import i18n
from i18n import L, U

PHOTOS_DIR = "photos"
PHOTOS_JSON = "photos.json"
OUT_DIR = os.path.join("assets", "photos")
EXTS = {".jpg", ".jpeg", ".png", ".webp"}
FULL_SIZE = 1600
THUMB_SIZE = 480
GALLERY_FIRST = 12
MANIFEST = "manifest.json"
YES = {"true", "yes", "はい", "1", "○", "〇"}


def flag(v):
    if isinstance(v, bool):
        return v
    return str(v or "").strip().lower() in YES


def norm_page(p):
    """"/events/interhigh/2024/" や URL をそのまま貼っても "interhigh/2024" にそろえる"""
    p = unquote(str(p or "").strip())
    p = re.sub(r"^https?://[^/]+", "", p)
    p = p.split("#")[0].split("?")[0].strip("/")
    if p.startswith("events/"):
        p = p[len("events/"):]
    return p


def make_images(src, out_dir, stem):
    """縮小版とサムネイルを作る。作れなかったときは None"""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return None
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)  # スマホ写真の向きを直す
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            bg = Image.new("RGB", im.size, (13, 13, 16))
            bg.paste(im, mask=im.split()[-1])
            im = bg
        else:
            im = im.convert("RGB")
        sizes = {}
        for suffix, limit in (("", FULL_SIZE), ("-t", THUMB_SIZE)):
            c = im.copy()
            c.thumbnail((limit, limit), Image.LANCZOS)
            # exif を渡さないので、撮影場所などの情報は保存されない
            c.save(os.path.join(out_dir, f"{stem}{suffix}.jpg"), "JPEG", quality=82, optimize=True, progressive=True)
            sizes[suffix] = c.size
    return sizes



def image_size(path):
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        return None


ALBUMS = {}


def wanted_pages(root):
    """photos.json の写真・アルバムが指している開催回("interhigh/2026" の形)。
    配信動画が無い開催回でも、写真やアルバムがあればページを作るために使う"""
    try:
        with open(os.path.join(root, PHOTOS_JSON), encoding="utf-8-sig") as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        return set()
    if not isinstance(cfg, dict):
        return set()
    items = [x for x in cfg.get("photos") or [] if isinstance(x, dict) and flag(x.get("confirmed")) and not flag(x.get("hidden"))]
    items += [a for a in cfg.get("albums") or [] if isinstance(a, dict)]
    return {norm_page(x.get("page")) for x in items if "/" in norm_page(x.get("page"))}


def load_albums(cfg, page_paths, report):
    """外部アルバムへのリンク(albums)を読む。1ページに複数のアルバムを書ける"""
    ALBUMS.clear()
    n = 0
    for i, a in enumerate((cfg.get("albums") or []) if isinstance(cfg, dict) else [], 1):
        url = str((a or {}).get("url") or "").strip()
        page = norm_page((a or {}).get("page"))
        if not url.startswith("https://"):
            report["errors"].append(f"albums {i}件目: url は https:// で始まるアドレスを書いてください")
        elif f"/events/{page}/" not in page_paths:
            report["errors"].append(f"albums {i}件目: page「{a.get('page') or ''}」のページが見つかりません")
        else:
            ALBUMS.setdefault(f"/events/{page}/", []).append({
                "url": url, "count": str(a.get("count") or "").strip(), "year": str(a.get("year") or "").strip(),
                "credit": str(a.get("credit") or "").strip()})
            n += 1
    report["albums"] = n


def load(root, page_paths):
    """photos.json を読んで {ページのパス: [写真]} とレポートを返す。
    page_paths は作られるページの "/events/…/" の集合"""
    report = {"entries": 0, "shown": 0, "hidden": 0, "unconfirmed": 0, "pages_with_photos": 0,
              "by_page": {}, "warnings": [], "errors": [], "unlisted_files": []}
    src_dir = os.path.join(root, PHOTOS_DIR)
    out_dir = os.path.join(root, OUT_DIR)
    path = os.path.join(root, PHOTOS_JSON)
    entries = []
    json_broken = False
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8-sig") as f:
                cfg = json.load(f)
            entries = cfg.get("photos", []) if isinstance(cfg, dict) else cfg
        except (ValueError, OSError) as ex:
            json_broken = True
            report["errors"].append(f"photos.json を読めませんでした(カンマや \" の抜けを確認してください): {ex}")
    report["entries"] = len(entries)
    load_albums(cfg if not json_broken and os.path.exists(path) else {}, page_paths, report)

    # 縮小版の記録(元の写真のファイル名 → 縮小版の名前と大きさ)。元の写真を消したあとも縮小版を使うため
    try:
        with open(os.path.join(out_dir, MANIFEST), encoding="utf-8") as f:
            manifest = json.load(f).get("files", {})
    except (OSError, ValueError):
        manifest = {}
    new_manifest = {}
    report["from_manifest"] = 0
    by_page = defaultdict(list)
    keep = {MANIFEST}
    listed = set()
    seen = set()
    for i, x in enumerate(entries, 1):
        if not isinstance(x, dict):
            report["errors"].append(f"{i}件目: {{ }} で囲んだ形になっていません")
            continue
        fn = str(x.get("file") or "").strip()
        label = f"{i}件目({fn or 'file なし'})"
        listed.add(fn)
        if flag(x.get("hidden")):
            report["hidden"] += 1
            continue
        if not flag(x.get("confirmed")):
            report["unconfirmed"] += 1
            report["warnings"].append(f"{label}: confirmed が true ではないため表示していません")
            continue
        if not fn:
            report["errors"].append(f"{label}: file(写真のファイル名)が空です")
            continue
        ext = os.path.splitext(fn)[1].lower()
        if ext not in EXTS:
            report["errors"].append(f"{label}: JPG・PNG・WebP 以外の形式です")
            continue
        src = os.path.join(src_dir, fn)
        rec = manifest.get(fn)
        has_rec = bool(rec) and all(os.path.exists(os.path.join(out_dir, f"{rec['stem']}{sfx}.jpg")) for sfx in ("", "-t"))
        if not os.path.isfile(src) and not has_rec:
            report["errors"].append(f"{label}: photos フォルダにファイルがありません(大文字・小文字も区別されます)")
            continue
        page = norm_page(x.get("page"))
        ppath = f"/events/{page}/"
        if not page or ppath not in page_paths:
            report["errors"].append(f"{label}: page「{x.get('page') or ''}」のページが見つかりません")
            continue
        if (fn, ppath) in seen:
            report["warnings"].append(f"{label}: 同じページに同じ写真が2回書かれているため、2回目は無視しました")
            continue
        seen.add((fn, ppath))
        credit = str(x.get("credit") or "").strip()
        if not credit:
            report["warnings"].append(f"{label}: credit(撮影者・提供元)が空です")

        if not os.path.isfile(src):
            # 元の写真は消してあるので、前に作った縮小版をそのまま使う
            stem = rec["stem"]
            fs, ts = rec.get("full_size"), rec.get("thumb_size")
            report["from_manifest"] += 1
        else:
            with open(src, "rb") as f:
                stem = hashlib.sha1(f.read()).hexdigest()[:12]
        # 中身が変わるとファイル名も変わるので、古い写真がブラウザに残らない
        full = os.path.join(out_dir, f"{stem}.jpg")
        thumb = os.path.join(out_dir, f"{stem}-t.jpg")
        if not os.path.isfile(src):
            pass
        elif os.path.exists(full) and os.path.exists(thumb):
            fs, ts = image_size(full), image_size(thumb)
        else:
            os.makedirs(out_dir, exist_ok=True)
            try:
                sizes = make_images(src, out_dir, stem)
            except Exception as ex:
                report["errors"].append(f"{label}: 写真を読み込めませんでした({ex})")
                continue
            if sizes is None:
                report["errors"].append(f"{label}: Pillow が入っていないため縮小版を作れませんでした(pip install Pillow)")
                continue
            fs, ts = sizes[""], sizes["-t"]
        keep.update({f"{stem}.jpg", f"{stem}-t.jpg"})
        new_manifest[fn] = {"stem": stem, "full_size": list(fs) if fs else None, "thumb_size": list(ts) if ts else None}
        caption = str(x.get("caption") or "").strip()
        by_page[ppath].append({"file": fn, "full": f"/{OUT_DIR.replace(os.sep, '/')}/{stem}.jpg",
                               "thumb": f"/{OUT_DIR.replace(os.sep, '/')}/{stem}-t.jpg",
                               "fw": fs[0] if fs else None, "fh": fs[1] if fs else None,
                               "tw": ts[0] if ts else None, "th": ts[1] if ts else None,
                               "caption": caption, "credit": credit, "year": str(x.get("year") or "").strip()})

    # 表示しなくなった写真(hidden・未確認・設定から削除)の縮小版を消して、サイトから見えないようにする。
    # photos.json が読めなかったときは、直すまでのあいだ消さずに残す
    if os.path.isdir(out_dir) and not json_broken:
        for name in os.listdir(out_dir):
            if name not in keep:
                os.remove(os.path.join(out_dir, name))
        with open(os.path.join(out_dir, MANIFEST), "w", encoding="utf-8") as f:
            json.dump({"about": "自動生成。元の写真のファイル名と縮小版の対応(元の写真を消しても縮小版を使い続けるため)。手で編集しない",
                       "files": dict(sorted(new_manifest.items()))}, f, ensure_ascii=False, indent=1)
    # 1ページの中はファイル名の順(数字は数として比べる:IMG_2 < IMG_10)
    nat = lambda n: [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", n)]
    for lst in by_page.values():
        lst.sort(key=lambda p: nat(p["file"]))

    if os.path.isdir(src_dir):
        report["unlisted_files"] = sorted(n for n in os.listdir(src_dir)
                                          if os.path.splitext(n)[1].lower() in EXTS and n not in listed)
    report["shown"] = sum(len(v) for v in by_page.values())
    report["pages_with_photos"] = len(by_page)
    report["by_page"] = {k: len(v) for k, v in sorted(by_page.items())}
    for w in report["warnings"]:
        print(f"[写真・警告] {w}")
    for w in report["errors"]:
        print(f"[写真・エラー] {w}")
    return dict(by_page), report


def album_html(albums, e):
    """外部アルバムへのボタン。year があれば「2026年の写真(アルバム)」、無ければ「アルバムですべての写真を見る」"""
    out = []
    for album in albums or []:
        n, y = album["count"], album["year"]
        cnt = L(f"({n}枚)", f" ({n} photos)") if n else ""
        label = (L(f"{y}年の写真をアルバムで見る", f"See {y} photos in the album") if y
                 else L("アルバムですべての写真を見る", "See all photos in the album")) + cnt
        cr = credit_text(album["credit"])
        out.append(f'<a class="palbum" href="{e(album["url"])}" target="_blank" rel="noopener">{e(label)} ↗</a>'
                   + (f'<p class="palbum-c">{e(cr)}</p>' if cr else ""))
    return "".join(out)


def gallery_html(photos, e, title, path=None, more=None):
    """写真があるページだけギャラリーを出す。無いときは空文字(外部アルバムだけ設定されていればボタンだけ出す)。
    more は写真ページのURL(大会ページから写真ページへのボタン)"""
    album = ALBUMS.get(path)
    if not photos:
        return (f'<section class="section photos" aria-label="{L("写真", "Photos")}"><h2 class="vh">{L("写真", "Photos")}</h2>'
                + album_html(album, e) + '</section>') if album else ""

    def wh(w, h):
        return f' width="{w}" height="{h}"' if w and h else ""

    items = []
    rest = len(photos) - GALLERY_FIRST
    # 全部の写真のクレジットが同じなら、見出しの下に1回だけ出す(拡大表示では写真ごとに出す)
    credits = {credit_text(p["credit"]) for p in photos}
    shared = credits.pop() if len(credits) == 1 else ""
    for i, p in enumerate(photos):
        alt = p["caption"] or L(f"{title}の写真{i + 1}", f"{title} – photo {i + 1}")
        credit = credit_text(p["credit"])
        credit_html = f'<span class="pcredit">{e(credit)}</span>' if credit else ""
        cap = e(p["caption"]) + ((" " + credit_html) if credit_html and not shared else "")
        items.append(
            f'<li{" hidden" if i >= GALLERY_FIRST else ""}><a href="{e(p["full"])}" data-full="{e(p["full"])}"'
            f' data-cap="{e(e(p["caption"]) + (" " + credit_html if credit_html else ""))}">'
            f'<img src="{e(p["thumb"])}" alt="{e(alt)}" loading="lazy" decoding="async"{wh(p["tw"], p["th"])}></a>'
            + (f'<p class="pcap">{cap}</p>' if cap else "") + "</li>")
    return (f'<section class="section photos" aria-label="{L("写真", "Photos")}"><h2 class="vh">{L("写真", "Photos")} <small>{L(f"{len(photos)}枚", str(len(photos)))}</small></h2>'
            + (f'<p class="pcredit-all">{e(shared)}</p>' if shared else "")
            + f'<ul class="pgrid">{"".join(items)}</ul>'
            + (f'<button type="button" class="pshow">{L(f"もっと見る(残り{rest}枚)", f"Show {rest} more photos")}</button>' if rest > 0 else "")
            + (f'<a class="palbum pmore" href="{e(more)}">{L("写真ページで見る", "Open the photo page")} →</a>' if more else "")
            + album_html(album, e)
            + '</section>' + L(LIGHTBOX, LIGHTBOX_EN))


def credit_text(c):
    c = (c or "").strip()
    m = re.match(r"^(撮影|写真|提供)\s*[:：]\s*(.+)$", c)
    if m:
        return L(c, {"撮影": "Photo", "写真": "Photo", "提供": "Courtesy of"}[m.group(1)] + ": " + re.sub(r"\s*[(（]", " (", m.group(2)).replace("）", ")"))
    return c


LIGHTBOX = """<dialog class="plb" aria-label="写真の拡大表示"><figure><img alt=""><figcaption></figcaption></figure>
<button type="button" class="plb-x" aria-label="閉じる">×</button><button type="button" class="plb-p" aria-label="前の写真">‹</button><button type="button" class="plb-n" aria-label="次の写真">›</button></dialog>
<script>(function(){var s=document.currentScript,d=s.previousElementSibling,g=d.previousElementSibling,mb=g.querySelector('.pshow');
if(mb)mb.addEventListener('click',function(){[].forEach.call(g.querySelectorAll('.pgrid li[hidden]'),function(li){li.hidden=false;});mb.remove();});
if(!d.showModal)return;
var as=[].slice.call(g.querySelectorAll('.pgrid a')),im=d.querySelector('img'),fc=d.querySelector('figcaption'),i=0,x0=null;
function show(k){i=(k+as.length)%as.length;var a=as[i],t=a.querySelector('img');
im.src=a.getAttribute('data-full');im.alt=t.alt;fc.innerHTML=a.getAttribute('data-cap')||'';d.classList.toggle('one',as.length<2);}
as.forEach(function(a,k){a.addEventListener('click',function(ev){ev.preventDefault();show(k);d.showModal();});});
d.querySelector('.plb-x').onclick=function(){d.close();};d.querySelector('.plb-p').onclick=function(){show(i-1);};d.querySelector('.plb-n').onclick=function(){show(i+1);};
d.addEventListener('click',function(ev){if(ev.target===d||ev.target.tagName==='FIGURE')d.close();});
d.addEventListener('keydown',function(ev){if(ev.key==='ArrowLeft')show(i-1);if(ev.key==='ArrowRight')show(i+1);});
d.addEventListener('touchstart',function(ev){x0=ev.touches[0].clientX;},{passive:true});
d.addEventListener('touchend',function(ev){if(x0===null)return;var dx=ev.changedTouches[0].clientX-x0;x0=null;if(Math.abs(dx)>50)show(dx<0?i+1:i-1);});
d.addEventListener('close',function(){im.removeAttribute('src');});})();</script>"""
LIGHTBOX_EN = """<dialog class="plb" aria-label="Enlarged photo"><figure><img alt=""><figcaption></figcaption></figure>
<button type="button" class="plb-x" aria-label="Close">×</button><button type="button" class="plb-p" aria-label="Previous photo">‹</button><button type="button" class="plb-n" aria-label="Next photo">›</button></dialog>
<script>(function(){var s=document.currentScript,d=s.previousElementSibling,g=d.previousElementSibling,mb=g.querySelector('.pshow');
if(mb)mb.addEventListener('click',function(){[].forEach.call(g.querySelectorAll('.pgrid li[hidden]'),function(li){li.hidden=false;});mb.remove();});
if(!d.showModal)return;
var as=[].slice.call(g.querySelectorAll('.pgrid a')),im=d.querySelector('img'),fc=d.querySelector('figcaption'),i=0,x0=null;
function show(k){i=(k+as.length)%as.length;var a=as[i],t=a.querySelector('img');
im.src=a.getAttribute('data-full');im.alt=t.alt;fc.innerHTML=a.getAttribute('data-cap')||'';d.classList.toggle('one',as.length<2);}
as.forEach(function(a,k){a.addEventListener('click',function(ev){ev.preventDefault();show(k);d.showModal();});});
d.querySelector('.plb-x').onclick=function(){d.close();};d.querySelector('.plb-p').onclick=function(){show(i-1);};d.querySelector('.plb-n').onclick=function(){show(i+1);};
d.addEventListener('click',function(ev){if(ev.target===d||ev.target.tagName==='FIGURE')d.close();});
d.addEventListener('keydown',function(ev){if(ev.key==='ArrowLeft')show(i-1);if(ev.key==='ArrowRight')show(i+1);});
d.addEventListener('touchstart',function(ev){x0=ev.touches[0].clientX;},{passive:true});
d.addEventListener('touchend',function(ev){if(x0===null)return;var dx=ev.changedTouches[0].clientX-x0;x0=null;if(Math.abs(dx)>50)show(dx<0?i+1:i-1);});
d.addEventListener('close',function(){im.removeAttribute('src');});})();</script>"""


PHOTO_CSS = """
.photos{margin-top:26px}
.pgrid{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px}
.pgrid li{margin:0;min-width:0}
.pgrid a{display:block;aspect-ratio:4/3;overflow:hidden;border-radius:10px;background:var(--surface);border:1px solid var(--line)}
.pgrid a:hover,.pgrid a:focus-visible{border-color:var(--pink);outline:none}
.pgrid img{display:block;width:100%;height:100%;object-fit:cover;transition:transform .2s}
.pgrid a:hover img{transform:scale(1.03)}
.pcap{margin:6px 2px 0;font-size:12px;line-height:1.5;color:var(--ink2)}
.pcredit{display:block;font-size:11px;color:var(--ink3)}
.palbum{display:block;width:max-content;max-width:100%;margin:12px auto 0;padding:9px 22px;border:1px solid var(--pink-line);border-radius:999px;color:var(--pink);text-decoration:none;font-size:14px;font-weight:700}
.palbum:hover{border-color:var(--pink)}
.palbum-c{margin:4px 0 0;text-align:center;font-size:11.5px;color:var(--ink3)}
.pcredit-all{margin:-4px 0 10px;font-size:12px;color:var(--ink3)}
.pshow{display:block;margin:12px auto 0;padding:9px 22px;border:1px solid var(--line);border-radius:999px;background:var(--surface);color:var(--ink);font:inherit;font-size:14px;cursor:pointer}
.pshow:hover{border-color:var(--pink);color:var(--pink)}
.pshow:focus-visible{outline:2px solid var(--pink);outline-offset:2px}
.plb{padding:0;border:0;background:transparent;max-width:100vw;max-height:100vh;width:100vw;height:100vh;color:#fff}
.plb::backdrop{background:rgba(0,0,0,.92)}
.plb figure{margin:0;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;padding:48px 56px 20px;box-sizing:border-box}
.plb img{max-width:100%;max-height:calc(100% - 60px);object-fit:contain;border-radius:6px}
.plb figcaption{max-width:70ch;text-align:center;font-size:14px;color:#d8d7de}
.plb figcaption .pcredit{color:#a9a8b2}
.plb figcaption .pcredit{margin-top:2px}
.plb button{position:absolute;border:1px solid #3a3a42;background:rgba(22,22,26,.85);color:#fff;border-radius:999px;width:44px;height:44px;font-size:24px;line-height:1;cursor:pointer}
.plb button:hover{border-color:var(--pink);color:var(--pink)}
.plb-x{top:10px;right:10px}
.plb-p{left:8px;top:50%;transform:translateY(-50%)}
.plb-n{right:8px;top:50%;transform:translateY(-50%)}
.plb.one .plb-p,.plb.one .plb-n{display:none}
@media (max-width:520px){
  .pgrid{grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}
  .plb figure{padding:56px 8px 16px}
  .plb-p,.plb-n{top:auto;bottom:12px;transform:none}
}
"""


# ---------------------------------------------------------------- 写真ページ(/photos/)

def photo_path(events_path):
    """大会ページのURL(/events/intercollegiate/2026/)に対応する写真ページのURL(/photos/intercollegiate/2026/)"""
    return "/photos/" + events_path[len("/events/"):]


def photo_targets(ctx, bp):
    """写真があるページごとに、名前・開催日・会場・並び順を調べる"""
    out = {}
    for ev in ctx["all_events"]:
        if ev["id"] in ctx["slugs"]:
            s = ctx["S"].get(ev["series"], {"id": ev["series"], "name": ev["name"]})
            out[f"/events/{ctx['slugs'][ev['id']]}/"] = {
                "series": bp.series_name(s), "full": bp.event_name(ev, s), "year": ev["year"], "start": ev.get("start"),
                "end": ev.get("end"), "venue": ev.get("venue") if not ev.get("derived") else None,
                "sort": ev.get("start") or f"{ev['year']}-99"}
    for s in ctx["S"].values():
        evs = ctx["events_by_series"].get(s["id"], [])
        out[f"/events/{s['id']}/"] = {"series": bp.series_name(s), "full": bp.series_name(s), "year": None, "start": None, "end": None,
                                      "venue": None, "sort": max((x.get("start") or "" for x in evs), default="")}
    return out


def photo_pages(ctx, photos_by_page, bp):
    """写真トップ(/photos/)と、大会ごとの写真ページ(/photos/…/)を作る。[(path, html, lastmod)]"""
    e, N = bp.e, bp.N
    info = photo_targets(ctx, bp)
    for p, lst in photos_by_page.items():
        # 大会ページ(年なし)に載せた写真は、photos.json の year を開催年として扱う
        yrs = {x["year"] for x in lst if x.get("year")}
        if p in info and info[p]["year"] is None and len(yrs) == 1:
            y = yrs.pop()
            info[p] = dict(info[p], year=y, sort=f"{y}-99")
    paths = sorted((p for p in photos_by_page if p in info), key=lambda p: info[p]["sort"], reverse=True)
    home, photos_t = L("トップ", "Home"), L("写真", "Photos")
    total = sum(len(photos_by_page[p]) for p in paths)
    pages = []

    def label(p):
        x = info[p]
        return x["series"] + ((" " + bp.year_label(x["year"])) if x["year"] else "")

    def shared_credit(lst):
        cs = {credit_text(x["credit"]) for x in lst}
        return cs.pop() if len(cs) == 1 else ""

    # 写真トップ
    path = "/photos/"
    crumbs = [(home, "/"), (photos_t, None)]
    title = f"{photos_t}{L('|', ' | ')}{bp.site_name()}"
    desc = L(f"レスリング大会で撮影された写真を大会ごとに見られます。{len(paths)}大会・{total}枚を掲載。",
             f"Photos taken at Japanese wrestling tournaments, organized by tournament. {i18n.plural(len(paths), 'tournament')}, {i18n_plural(total)}.")
    jsonld = {"@context": "https://schema.org", "@graph": [bp.breadcrumb_ld(crumbs), {
        "@type": "CollectionPage", "name": photos_t, "url": bp.SITE + U(path),
        "hasPart": [{"@type": "ImageGallery", "name": label(p), "url": bp.SITE + U(photo_path(p))} for p in paths]}]}
    cover = photos_by_page[paths[0]][0] if paths else None
    h = bp.head(title, desc, path, (bp.SITE + cover["full"]) if cover else "", jsonld, ctx["css"])
    h += '<main class="wrap page">' + bp.breadcrumb_html(crumbs) + f"<h1>{e(photos_t)}</h1>"
    h += '<p class="lead">' + e(L(f"レスリング大会で撮影された写真です。大会を選ぶと、その大会の写真をまとめて見られます。写真は撮影者の許可を得て掲載しています。現在{len(paths)}大会・{total}枚。",
                                  f"Photos taken at wrestling tournaments. Choose a tournament to see all of its photos. Photos are published with the photographers' permission. {i18n.plural(len(paths), 'tournament')}, {i18n_plural(total)}.")) + "</p>"
    if paths:
        h += '<ul class="pcards">'
        for p in paths:
            lst, x = photos_by_page[p], info[p]
            c = lst[0]
            wh = f' width="{c["tw"]}" height="{c["th"]}"' if c.get("tw") and c.get("th") else ""
            sub = " · ".join(t for t in [bp.fmt_range(x["start"], x["end"]) if x["start"] else "", L(f"{len(lst)}枚", i18n_plural(len(lst)))] if t)
            cr = shared_credit(lst)
            h += (f'<li><a href="{e(U(photo_path(p)))}"><span class="pc-img"><img src="{e(c["thumb"])}" alt="" loading="lazy" decoding="async"{wh}></span>'
                  f'<span class="pc-t">{e(label(p))}</span><span class="pc-s">{e(sub)}</span>'
                  + (f'<span class="pc-c">{e(cr)}</span>' if cr else "") + "</a></li>")
        h += "</ul>"
    else:
        h += f'<p class="empty">{L("まだ写真はありません。", "No photos yet.")}</p>'
    h += "</main>" + bp.footer(ctx["as_of"])
    pages.append((path, h, ctx["as_of"]))

    # 大会ごとの写真ページ
    for p in paths:
        lst, x = photos_by_page[p], info[p]
        path = photo_path(p)
        name = label(p)
        crumbs = [(home, "/"), (photos_t, "/photos/"), (name, None)]
        cr = shared_credit(lst)
        title = L(f"{name}の写真({len(lst)}枚)|{bp.SITE_NAME}", f"{name} – Photos ({len(lst)}) | {bp.site_name()}")
        when = bp.fmt_range(x["start"], x["end"]) if x["start"] else ""
        venue = N(x["venue"]) if x["venue"] else ""
        desc = L(f"{x['full']}" + (f"({when}" + (f"・{venue}" if venue else "") + ")" if when else "") + f"の写真{len(lst)}枚。" + (f"{cr}。" if cr else ""),
                 f"{len(lst)} photos from the {name}" + (f" ({when}" + (f", {venue}" if venue else "") + ")" if when else "") + "." + (f" {cr}." if cr else ""))
        jsonld = {"@context": "https://schema.org", "@graph": [bp.breadcrumb_ld(crumbs), {
            "@type": "ImageGallery", "name": L(f"{name}の写真", f"{name} photos"), "url": bp.SITE + U(path),
            "associatedMedia": [dict({"@type": "ImageObject", "contentUrl": bp.SITE + ph["full"], "thumbnailUrl": bp.SITE + ph["thumb"]},
                                     **({"creditText": credit_text(ph["credit"])} if ph["credit"] else {}),
                                     **({"caption": ph["caption"]} if ph["caption"] else {})) for ph in lst]}]}
        h = bp.head(title, desc, path, bp.SITE + lst[0]["full"], jsonld, ctx["css"])
        h += '<main class="wrap page">' + bp.breadcrumb_html(crumbs)
        h += f'<h1>{e(x["series"])} <span class="yr-h">{e(bp.year_label(x["year"]) if x["year"] else "")}</span><span class="badge ph">{photos_t}</span></h1>'
        lead = L((f"{when}" + (f"、{venue}で" if venue else "に") + "開催。" if when else "") + f"写真{len(lst)}枚を掲載しています。",
                 (f"Held {when}" + (f" at {venue}" if venue else "") + ". " if when else "") + f"{i18n_plural(len(lst))}.")
        h += f'<p class="lead">{e(lead)}</p>'
        back = (f'<p class="elinks"><a class="elink" href="{e(U(p))}">'
                f'{L("この大会の動画・大会情報を見る", "Videos and details for this tournament")} →</a></p>')
        h += back
        h += gallery_html(lst, e, name, p)
        h += back.replace('class="elinks"', 'class="elinks pback"')
        h += "</main>" + bp.footer(ctx["as_of"])
        pages.append((path, h, ctx["as_of"]))
    return pages


def i18n_plural(n):
    return f"{n} photo" if n == 1 else f"{n} photos"


PHOTO_CSS += """
.pcards{list-style:none;margin:18px 0 32px;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px}
.pcards li{margin:0;min-width:0}
.pcards a{display:flex;flex-direction:column;gap:3px;height:100%;padding:0 0 12px;border:1px solid var(--line);border-radius:12px;background:var(--surface);color:var(--ink);text-decoration:none;overflow:hidden}
.pcards a:hover,.pcards a:focus-visible{border-color:var(--pink);outline:none}
.pc-img{display:block;aspect-ratio:4/3;overflow:hidden;margin-bottom:8px;background:var(--surface)}
.pc-img img{display:block;width:100%;height:100%;object-fit:cover}
.pc-t,.pc-s,.pc-c{padding:0 12px}
.pc-t{font-weight:700;font-size:15px;line-height:1.4}
.pc-s{font-size:12.5px;color:var(--ink2)}
.pc-c{font-size:11.5px;color:var(--ink3)}
.badge.ph{background:var(--pink-line);color:var(--pink)}
.pback{margin:22px 0 32px;justify-content:center}
.pmark{margin-left:6px;font-size:.9em;text-decoration:none}
"""
