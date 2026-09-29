"""
写真ギャラリー(大会ページ・開催回ページ)

  photos/       … 元の写真を入れるフォルダ(JPG / PNG / WebP)。手でアップロードする
  photos.json   … どの写真をどのページに載せるかの設定。手で編集する
  assets/photos/ … 自動生成。縮小した写真(長辺1600px)とサムネイル(長辺480px)。手で編集しない

photos.json の1件の書き方
  {"file": "interhigh-2024-01.jpg", "page": "interhigh/2024",
   "caption": "決勝の表彰式", "credit": "撮影:山田太郎", "confirmed": true, "hidden": false}

  - page は大会ページまたは開催回ページのURLの /events/ の後ろ(例: "interhigh" や "interhigh/2024")
  - confirmed が true の写真だけ表示する(未成年が写っている場合は、掲載してよいか確認してから true にする)
  - hidden を true にすると一時的に表示しない
  - credit(撮影者・提供元)が空のときはビルド時に警告を出す

ルール
  - 縮小した写真からは撮影場所(GPS)などの情報を取り除く。元の写真には残るので、アップロード前に消しておく
  - 表示しなくなった写真の縮小版は assets/photos/ から自動で削除する
  - Pillow が入っていない環境では新しい写真は作れない(作成済みの縮小版があればそれを使う)
"""
import hashlib
import json
import os
import re
from collections import defaultdict
from urllib.parse import unquote

PHOTOS_DIR = "photos"
PHOTOS_JSON = "photos.json"
OUT_DIR = os.path.join("assets", "photos")
EXTS = {".jpg", ".jpeg", ".png", ".webp"}
FULL_SIZE = 1600
THUMB_SIZE = 480
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

    by_page = defaultdict(list)
    keep = set()
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
        if not os.path.isfile(src):
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

        with open(src, "rb") as f:
            digest = hashlib.sha1(f.read()).hexdigest()[:12]
        # 中身が変わるとファイル名も変わるので、古い写真がブラウザに残らない
        stem = digest
        full = os.path.join(out_dir, f"{stem}.jpg")
        thumb = os.path.join(out_dir, f"{stem}-t.jpg")
        if os.path.exists(full) and os.path.exists(thumb):
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
        caption = str(x.get("caption") or "").strip()
        by_page[ppath].append({"full": f"/{OUT_DIR.replace(os.sep, '/')}/{stem}.jpg",
                               "thumb": f"/{OUT_DIR.replace(os.sep, '/')}/{stem}-t.jpg",
                               "fw": fs[0] if fs else None, "fh": fs[1] if fs else None,
                               "tw": ts[0] if ts else None, "th": ts[1] if ts else None,
                               "caption": caption, "credit": credit})

    # 表示しなくなった写真(hidden・未確認・設定から削除)の縮小版を消して、サイトから見えないようにする。
    # photos.json が読めなかったときは、直すまでのあいだ消さずに残す
    if os.path.isdir(out_dir) and not json_broken:
        for name in os.listdir(out_dir):
            if name not in keep:
                os.remove(os.path.join(out_dir, name))

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


def gallery_html(photos, e, title):
    """写真があるページだけギャラリーを出す。無いときは空文字"""
    if not photos:
        return ""

    def wh(w, h):
        return f' width="{w}" height="{h}"' if w and h else ""

    items = []
    for i, p in enumerate(photos):
        alt = p["caption"] or f"{title}の写真{i + 1}"
        cap = e(p["caption"]) + (f' <span class="pcredit">{e(p["credit"])}</span>' if p["credit"] else "")
        items.append(
            f'<li><a href="{e(p["full"])}" data-full="{e(p["full"])}">'
            f'<img src="{e(p["thumb"])}" alt="{e(alt)}" loading="lazy" decoding="async"{wh(p["tw"], p["th"])}></a>'
            + (f'<p class="pcap">{cap}</p>' if cap else "") + "</li>")
    return (f'<section class="section photos" aria-label="写真"><h2 class="vh">写真 <small>{len(photos)}枚</small></h2>'
            f'<ul class="pgrid">{"".join(items)}</ul></section>' + LIGHTBOX)


LIGHTBOX = """<dialog class="plb" aria-label="写真の拡大表示"><figure><img alt=""><figcaption></figcaption></figure>
<button type="button" class="plb-x" aria-label="閉じる">×</button><button type="button" class="plb-p" aria-label="前の写真">‹</button><button type="button" class="plb-n" aria-label="次の写真">›</button></dialog>
<script>(function(){var s=document.currentScript,d=s.previousElementSibling,g=d.previousElementSibling;if(!d.showModal)return;
var as=[].slice.call(g.querySelectorAll('.pgrid a')),im=d.querySelector('img'),fc=d.querySelector('figcaption'),i=0,x0=null;
function show(k){i=(k+as.length)%as.length;var a=as[i],t=a.querySelector('img'),c=a.parentNode.querySelector('.pcap');
im.src=a.getAttribute('data-full');im.alt=t.alt;fc.innerHTML=c?c.innerHTML:'';d.classList.toggle('one',as.length<2);}
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
.plb{padding:0;border:0;background:transparent;max-width:100vw;max-height:100vh;width:100vw;height:100vh;color:var(--ink)}
.plb::backdrop{background:rgba(0,0,0,.92)}
.plb figure{margin:0;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;padding:48px 56px 20px;box-sizing:border-box}
.plb img{max-width:100%;max-height:calc(100% - 60px);object-fit:contain;border-radius:6px}
.plb figcaption{max-width:70ch;text-align:center;font-size:14px;color:var(--ink2)}
.plb figcaption .pcredit{margin-top:2px}
.plb button{position:absolute;border:1px solid var(--line);background:rgba(22,22,26,.85);color:var(--ink);border-radius:999px;width:44px;height:44px;font-size:24px;line-height:1;cursor:pointer}
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
