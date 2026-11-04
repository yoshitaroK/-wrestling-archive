"""
トップページ(index.html と en/index.html)に、特集の1件目と「これから開催される大会」「最近開催された大会」の列を、
ビルドのときに HTML として書き込む(Issue #288)。

- JavaScript(assets/top.js)が data.json を読み終えるまで、トップの特集と大会の列は空だった。
  そのため一番大きな表示(LCP)が遅く、JavaScript を動かさない検索エンジン・AI のクローラーには最新の大会が見えなかった。
- ここで作る HTML は、assets/top.js の buildFeature()・showFeature(0)・renderShelves() の最初の2列と同じものにする。
  読み込み後は top.js が今までどおり全部を描き直すので、見た目は変わらない(top.js を変えたら、ここも合わせる)。
- 特集の並びの決まり(FEAT_ORDER・HIDE_FEAT・FEAT_FROM・NO_HERO・FEATURE_ART)は assets/top.js に書いてあるものを読む
  (二か所に書かないため)。読めなかったときは書き込まずに、今までの空の形のままにする(ビルドは止めない)。
- 書き込む場所は index.html の <!--pre:名前--> と <!--/pre:名前--> の間。毎日の更新で中身が入れ替わる。
  元のファイル(PR で直す index.html)では、この間は空の形(DEFAULT)にしておく。en_index.py は英語版を作る前に strip() で空の形に戻す。
- 高校生以下の選手の決まり:書き込むのは大会名・日付・会場・本数・リンクだけで、選手の名前は入れない(top.js と同じ範囲)。
"""
import datetime
import json
import os
import re

import i18n

# 書き込む場所と、元のファイルに置く空の形
DEFAULT = {
    "img": '<img class="jhero-img" id="jhero-img" alt="" decoding="async" fetchpriority="high">',
    "feat": '<div class="feat" id="feat" hidden data-wait></div>',
    "credit": '<a class="jcredit" id="jhero-credit" hidden></a>',
    "main": '<div class="loading">データを読み込んでいます</div>',
}
_RE = re.compile(r"<!--pre:(\w+)-->(.*?)<!--/pre:\1-->", re.S)


DEFAULT_EN = dict(DEFAULT, main='<div class="loading">Loading data…</div>')  # en_index.py の PAIRS と同じ英語


def strip(s, lang="ja"):
    """書き込まれた中身を、空の形(DEFAULT)に戻す"""
    base = DEFAULT_EN if lang == "en" else DEFAULT
    return _RE.sub(lambda m: f"<!--pre:{m.group(1)}-->{base.get(m.group(1), '')}<!--/pre:{m.group(1)}-->", s)


def _fill(s, parts):
    def rep(m):
        k = m.group(1)
        return f"<!--pre:{k}-->{parts[k] if k in parts else m.group(2)}<!--/pre:{k}-->"
    return _RE.sub(rep, s)


# ---------- assets/top.js から特集の決まりを読む ----------
def _js_value(src, name):
    m = re.search(r"^var " + name + r" = (.*?);\s*$", src, re.S | re.M)
    if not m:
        raise ValueError(name)
    t = m.group(1)
    t = re.sub(r"'((?:[^'\\]|\\.)*)'", lambda x: json.dumps(x.group(1)), t)  # '...' → "..."
    t = re.sub(r"([{,]\s*)([A-Za-z_][\w-]*)\s*:", r'\1"\2":', t)  # キーに "" を付ける
    return json.loads(t)


def read_rules(root):
    with open(os.path.join(root, "assets", "top.js"), encoding="utf-8") as f:
        src = f.read()
    return {k: _js_value(src, k) for k in ("NO_HERO", "HIDE_FEAT", "FEAT_ORDER", "FEAT_FROM", "FEATURE_ART")}


# ---------- top.js と同じ書き方(文字の形をそろえる) ----------
MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
PALETTE = [['#16161c', '#34343f'], ['#16161c', '#6e1424'], ['#1c1c24', '#3d3d4a'], ['#5a1220', '#18181e'],
           ['#20202a', '#45454f'], ['#7a1628', '#26262e'], ['#121216', '#2c2c36'], ['#3c0e18', '#9a1a30']]


def L(ja, en):
    return i18n.L(ja, en)


def esc(s):
    s = "" if s is None else str(s)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")


def fmt_date(iso):
    if not iso:
        return L('日付未確認', 'Date TBC')
    p = iso[:10].split('-')
    return L(f"{int(p[0])}年{int(p[1])}月{int(p[2])}日", f"{MON[int(p[1]) - 1]} {int(p[2])}, {p[0]}")


def fmt_short(iso):
    if not iso:
        return ''
    p = iso[:10].split('-')
    return L(f"{int(p[1])}/{int(p[2])}", f"{MON[int(p[1]) - 1]} {int(p[2])}")


def fmt_range(a, b):
    if not a:
        return L('日付未確認', 'Date TBC')
    if not b or a == b:
        return fmt_date(a)
    pa, pb = a.split('-'), b.split('-')
    if i18n.LANG == 'en':
        if pa[0] != pb[0]:
            return fmt_date(a) + ' – ' + fmt_date(b)
        return (MON[int(pa[1]) - 1] + ' ' + str(int(pa[2])) +
                ('–' + str(int(pb[2])) if pa[1] == pb[1] else ' – ' + MON[int(pb[1]) - 1] + ' ' + str(int(pb[2]))) + ', ' + pa[0])
    if pa[0] == pb[0]:
        return fmt_date(a) + '〜' + (f"{int(pb[2])}日" if pa[1] == pb[1] else f"{int(pb[1])}月{int(pb[2])}日")
    return fmt_date(a) + '〜' + fmt_date(b)


def hash_str(s):
    h = 0
    b = str(s or '').encode('utf-16-le')
    for i in range(0, len(b), 2):
        h = (h * 31 + (b[i] | (b[i + 1] << 8))) & 0xFFFFFFFF
    if h >= 0x80000000:
        h -= 0x100000000
    return abs(h)


def grad(name):
    p = PALETTE[hash_str(name) % len(PALETTE)]
    return f"linear-gradient({100 + hash_str(name) % 60}deg,{p[0]},{p[1]})"


def thumb(vid, label):
    return ('<div class="thumb" style="background:' + grad(label or vid) + '">' +
            ('<img src="https://i.ytimg.com/vi/' + esc(vid) + '/mqdefault.jpg" alt="" loading="lazy" referrerpolicy="no-referrer" data-thumb>' if vid else '') +
            '<div class="ph">' + esc(label or '') + '</div></div>')


def _js_sort(items, before):
    """top.js の sort(function(a,b){ return 条件 ? 1 : -1; }) と同じ並べ方(Python の sort も同じ TimSort)"""
    import functools
    return sorted(items, key=functools.cmp_to_key(lambda a, b: 1 if before(a, b) else -1))


class _Top:
    def __init__(self, data, slugs, hero, rules, names, now):
        self.d, self.R = data, rules
        self.PAGES = slugs
        self.HERO = hero or []
        self.names = names
        self.S = {s["id"]: dict(s, events=[]) for s in data.get("series", [])}
        for e in data.get("events", []):
            if e.get("series") in self.S:
                self.S[e["series"]]["events"].append(e)
        for s in self.S.values():
            s["events"] = _js_sort(s["events"], lambda a, b: not ((a.get("start") or f"{a['year']}-99") < (b.get("start") or f"{b['year']}-99")))
        self.by_event = {}
        for v in data.get("videos", []):
            if v.get("e"):
                self.by_event.setdefault(v["e"], []).append(v)
        self.today_iso = now.astimezone(datetime.timezone.utc).date().isoformat()
        jst = datetime.timezone(datetime.timedelta(hours=9))
        self.today = now.astimezone(jst).date().isoformat()
        self.week_ago = (now - datetime.timedelta(days=7)).astimezone(jst).date().isoformat()
        self.soon_to = (now + datetime.timedelta(days=3)).astimezone(jst).date().isoformat()

    def N(self, x):
        return self.names.get(x, x) if i18n.LANG == 'en' and x else x

    def U(self, path):
        return '/en' + path if i18n.LANG == 'en' else path

    def event_page(self, eid):
        return self.U('/events/' + self.PAGES[eid] + '/') if eid in self.PAGES else ''

    @staticmethod
    def link_to(sid, eid):
        from urllib.parse import urlencode
        return '#' + urlencode([('s', sid)] + ([('e', eid)] if eid else []))

    # ---- 特集(buildFeature の1件目) ----
    def feature(self):
        R, E = self.R, self.d.get("events", [])
        past = _js_sort([e for e in E if e.get("n", 0) > 0 and e.get("start") and e["start"] <= self.today_iso and e.get("status") != 'cancelled' and not R["NO_HERO"].get(e["series"])],
                        lambda a, b: a["start"] < b["start"])
        future = _js_sort([e for e in E if e.get("n", 0) > 0 and e.get("start") and e["start"] > self.today_iso and not R["NO_HERO"].get(e["series"])],
                          lambda a, b: not (a["start"] < b["start"]))
        used = {}

        def photo_for(e):
            keys = [self.U('/photos/' + self.PAGES[e["id"]] + '/') if e["id"] in self.PAGES else '', self.U('/photos/' + e["series"] + '/')]
            for i, h in enumerate(self.HERO):
                if not used.get(i) and h.get("href") in keys:
                    used[i] = 1
                    return h
            return None

        def ev_slide(e, kind):
            s = self.S.get(e["series"])
            vs = self.by_event.get(e["id"], [])
            v = next((x for x in vs if x.get("k") == 'match'), vs[0] if vs else None)
            return {"kind": kind, "href": self.event_page(e["id"]) or self.link_to(e["series"], e["id"]),
                    "name": L(e.get("official_name") or e.get("name"), self.N(s["name"] if s else e.get("name")) + ' ' + str(e["year"])),
                    "meta": '<span><span class="num">' + str(e.get("n", 0)) + '</span>' + L('本', ' videos') + '</span><span>' + esc(fmt_range(e.get("start"), e.get("end"))) + '</span>' +
                            ('<span>' + esc(self.N(e["venue"])) + '</span>' if e.get("venue") else ''),
                    "photo": photo_for(e), "vid": v["id"] if v else ''}

        live = [e for e in E if e.get("links") and e["id"] in self.PAGES and e.get("start")
                and (e["start"] <= self.soon_to or (R["FEAT_FROM"].get(e["id"]) and R["FEAT_FROM"][e["id"]] <= self.today))
                and (e.get("end") or e["start"]) >= self.week_ago and e.get("status") != 'cancelled'
                and not R["NO_HERO"].get(e["series"]) and not R["HIDE_FEAT"].get(e["id"])]
        order = R["FEAT_ORDER"]

        def live_cmp(a, b):
            ia = order.index(a["id"]) if a["id"] in order else 99
            ib = order.index(b["id"]) if b["id"] in order else 99
            if ia != ib:
                return ia - ib
            return 1 if a["start"] < b["start"] else -1
        import functools
        live = sorted(live, key=functools.cmp_to_key(live_cmp))
        out = []
        for e in live:
            kind = 'soon' if e["start"] > self.today else ('live' if (e.get("end") or e["start"]) >= self.today else 'result')
            x = ev_slide(e, kind)
            if not x["photo"] and e["id"] in R["FEATURE_ART"]:
                x["art"] = R["FEATURE_ART"][e["id"]]
            if not x["photo"] and not x.get("art") and not x["vid"]:
                s = self.S.get(e["series"])
                pv = [o for o in s["events"] if o.get("n", 0) > 0][-1:] if s else []
                vs = self.by_event.get(pv[0]["id"], []) if pv else []
                m = next((v for v in vs if v.get("k") == 'match'), vs[0] if vs else None)
                if m:
                    x["vid"] = m["id"]
            if not e.get("n"):
                x["meta"] = '<span>' + esc(fmt_range(e.get("start"), e.get("end"))) + '</span>' + ('<span>' + esc(self.N(e["venue"])) + '</span>' if e.get("venue") else '')
            x["ext"], x["extLabel"] = e["links"][0]["url"], e["links"][0].get("label")
            out.append(x)
        rank = {'live': 0, 'soon': 1, 'result': 2}
        out = [p[0] for p in sorted([(x, i) for i, x in enumerate(out)], key=lambda p: (rank[p[0]["kind"]], p[1]))]
        out += [ev_slide(e, 'recent') for e in past[:2]]
        if future:
            out.append(ev_slide(future[0], 'upcoming'))
        for i, p in enumerate(self.HERO):
            if not used.get(i) and len(out) < 5:
                used[i] = 1
                out.append({"kind": 'photo', "href": p["href"], "name": p.get("label"), "meta": '', "photo": p, "vid": ''})
        return out

    FEAT_TXT = {
        'ja': {'soon': ['まもなく開催', '大会公式サイトを見る'], 'live': ['開催中', '結果・速報を見る'], 'result': ['結果が出ています', '結果を見る'],
               'recent': ['最近開催された大会', '配信一覧を見る'], 'upcoming': ['これから開催される大会', '配信予定を見る'], 'photo': ['新しく載った写真', '写真を見る']},
        'en': {'soon': ['Starting soon', 'See the official site'], 'live': ['Happening now', 'See the live results'], 'result': ['Results are in', 'See the results'],
               'recent': ['Latest tournament', 'Watch the streams'], 'upcoming': ['Upcoming tournament', 'See the stream schedule'], 'photo': ['New photos', 'See the photos']},
    }

    def feature_html(self, feat):
        """showFeature(0) と同じ HTML。特集が無いときは None(空の形のまま)"""
        if not feat:
            return None
        f, t = feat[0], self.FEAT_TXT[i18n.LANG][feat[0]["kind"]]
        n = len(feat)
        box = ('<div class="feat-main" aria-live="polite"><div class="badge-l' + (' live' if f["kind"] == 'live' else '') + '">' + t[0] + '</div><a class="fn" href="' + esc(f["href"]) + '">' + esc(f["name"]) + '</a>' +
               ('<div class="fm">' + f["meta"] + '</div>' if f.get("meta") else '') +
               ('<div class="ctas"><a class="cta" href="' + esc(f["ext"]) + '" target="_blank" rel="noopener">' + (esc(f["extLabel"]) + 'を見る' if i18n.LANG == 'ja' and f.get("extLabel") else t[1]) + ' ↗</a><a class="cta2" href="' + esc(f["href"]) + '">' + L('大会ページへ', 'Tournament page') + '</a></div>'
                if f.get("ext") else '<a class="cta" href="' + esc(f["href"]) + '" tabindex="-1">' + t[1] + '</a>') + '</div>' +
               ('<div class="fnav"><button type="button" class="fb" data-feat="-1" aria-label="' + L('前の特集', 'Previous') + '">‹</button><div class="fdots">' +
                ''.join('<button type="button" data-featto="' + str(k) + '" aria-label="' + L(f"{k + 1}件目({n}件中)", f"Item {k + 1} of {n}") + '"' + (' aria-current="true"' if k == 0 else '') + '></button>' for k in range(n)) +
                '</div><button type="button" class="fb" data-feat="1" aria-label="' + L('次の特集', 'Next') + '">›</button></div>' if n > 1 else ''))
        feat_div = '<div class="feat" id="feat" data-pre>' + box + '</div>'
        # 背景の写真(top.js の showFeature と同じ選び方)。class="on" を最初から付けて、top.js が同じ写真なら付け直さない
        a = ' class="jhero-img on" id="jhero-img" alt="" decoding="async" fetchpriority="high"'
        pos = f.get("art", {}).get("pos") if f.get("art") else ''
        style = ' style="object-position:' + esc(pos) + '"' if pos else ''
        if f.get("art"):
            art = f["art"]
            img = '<img' + a + style + (' sizes="100vw" srcset="' + esc(art["srcset"]) + '"' if art.get("srcset") else '') + ' src="' + esc(art["src"]) + '">'
        elif f.get("photo"):
            p = f["photo"]
            img = '<img' + a + ' sizes="100vw" srcset="' + esc(p.get("srcset", '')) + '" src="' + esc(p["src"]) + '"' + (f' width="{p["w"]}" height="{p["h"]}"' if p.get("w") and p.get("h") else '') + '>'
        elif f.get("vid"):
            img = '<img' + a + ' src="https://i.ytimg.com/vi/' + esc(f["vid"]) + '/maxresdefault.jpg" referrerpolicy="no-referrer">'
        else:
            img = None
        credit = None
        if f.get("photo") and f["photo"].get("credit"):
            p = f["photo"]
            jl = ('<span class="jl">' + esc(L(p["label"] + 'の写真', 'Photo from ' + p["label"]) + ' · ') + '</span>') if p.get("label") else ''
            credit = '<a class="jcredit" id="jhero-credit" href="' + esc(p["href"]) + '" title="' + esc(p.get("label") or '') + '">' + jl + esc(p["credit"]) + '</a>'
        return feat_div, img, credit

    # ---- 大会の列(renderShelves の最初の2列) ----
    def tile_event(self, e):
        vs = self.by_event.get(e["id"], [])
        vs = _js_sort(vs, lambda a, b: a.get("k") != 'match')  # top.js: a.k==='match' ? -1 : 1
        first = vs[0] if vs else None
        s = self.S.get(e["series"])
        art = (not first) and self.R["FEATURE_ART"].get(e["id"])
        if art:
            th = ('<div class="thumb"><img src="' + esc(art.get("small") or art["src"]) + '"' +
                  (' srcset="' + esc(art["tile"]) + '" sizes="(max-width:760px) 41vw, 260px"' if art.get("tile") else '') +
                  ' alt="" loading="lazy" decoding="async" style="object-position:' + esc(art.get("pos") or '50% 50%') + '"></div>')
        else:
            th = thumb(first["id"] if first else '', s["name"] if s else '')
        n = e.get("n", 0)
        cnt = ('<span class="num">' + str(n) + '</span>' + L(f"本 {e['year']}年 ", f" videos · {e['year']} · ")) if n else L(f"{e['year']}年 結果あり ", f"{e['year']} · Results · ")
        return ('<a class="tile" href="' + esc(self.event_page(e["id"]) or self.link_to(e["series"], e["id"])) + '">' + th +
                '<div class="tt">' + esc(self.N(s["name"] if s else e.get("name"))) + '</div><div class="tm">' + cnt + fmt_short(e.get("start")) +
                ((L('〜', '–') + fmt_short(e["end"])) if e.get("end") and e["end"] != e.get("start") else '') + '</div></a>')

    def shelf(self, k, title, sub, tiles, more):
        if not tiles:
            return ''
        rid = f"row{k}"
        return ('<section class="shelf" aria-labelledby="' + rid + '-h"><div class="shelf-h"><h2 id="' + rid + '-h">' + esc(title) + ('<span class="sub">' + esc(sub) + '</span>' if sub else '') + '</h2>' + (more or '') + '</div>' +
                '<div class="rowwrap"><button type="button" class="rbtn prev" data-row="' + rid + '" data-dir="-1" tabindex="-1" aria-hidden="true">‹</button>' +
                '<div class="row" id="' + rid + '">' + ''.join(tiles) + '</div>' +
                '<button type="button" class="rbtn next" data-row="' + rid + '" data-dir="1" tabindex="-1" aria-hidden="true">›</button></div></section>')

    def shelves_html(self):
        E = self.d.get("events", [])
        past = _js_sort([e for e in E if (e.get("n", 0) > 0 or (e.get("links") and e["id"] in self.PAGES)) and e.get("start") and e["start"] <= self.today_iso and e.get("status") != 'cancelled'],
                        lambda a, b: a["start"] < b["start"])[:12]
        future = _js_sort([e for e in E if e.get("n", 0) > 0 and e.get("start") and e["start"] > self.today_iso], lambda a, b: not (a["start"] < b["start"]))
        h, k = '', 0
        if future:
            k += 1
            h += self.shelf(k, L('これから開催される大会', 'Upcoming tournaments'), L('配信枠が公開されています', 'Stream pages are already published'),
                            [self.tile_event(e) for e in future], '<a class="all" href="' + self.U('/events/calendar/') + '">' + L('カレンダーを見る ›', 'See the calendar ›') + '</a>')
        if past:
            k += 1
            h += self.shelf(k, L('最近開催された大会', 'Recent tournaments'), '', [self.tile_event(e) for e in past],
                            '<a class="all" href="' + self.U('/events/') + '">' + L('すべて見る ›', 'See all ›') + '</a>')
        return h or None


def render(data, slugs, hero, rules, now=None):
    """いまの言語(i18n.LANG)のトップページに書き込む中身 {名前: HTML}"""
    names = {}
    if i18n.LANG == 'en':
        names = dict(i18n.names_table())
        for ev in data.get("events", []):
            if ev.get("fy_label") and ev["fy_label"] not in names:
                names[ev["fy_label"]] = i18n.fy_label(ev["fy_label"])
    t = _Top(data, slugs, hero, rules, names, now or datetime.datetime.now(datetime.timezone.utc))
    parts = {}
    fh = t.feature_html(t.feature())
    if fh:
        feat_div, img, credit = fh
        parts["feat"] = feat_div
        if img:
            parts["img"] = img
        if credit:
            parts["credit"] = credit
    sh = t.shelves_html()
    if sh:
        parts["main"] = sh
    return parts


def write(root, data, slugs, hero, report=None):
    """index.html と en/index.html の <!--pre:…--> の間を書き換える。うまく作れないときは空の形のままにする"""
    try:
        rules = read_rules(root)
    except Exception as ex:
        msg = f"トップページの書き込みをしませんでした(assets/top.js の特集の決まりを読めません: {ex!r})"
        print("[トップ] " + msg)
        if report is not None:
            report.append(msg)
        return
    keep = i18n.LANG
    try:
        for lang, path in (("ja", "index.html"), ("en", os.path.join("en", "index.html"))):
            fp = os.path.join(root, path)
            if not os.path.exists(fp):
                continue
            i18n.set_lang(lang)
            with open(fp, encoding="utf-8") as f:
                s = f.read()
            s = strip(s, lang)
            if s.count("<!--pre:") != len(DEFAULT):
                msg = f"トップページの書き込みをしませんでした({path} に書き込む場所の目印が {len(DEFAULT)} か所ありません)"
                print("[トップ] " + msg)
                if report is not None:
                    report.append(msg)
                continue
            try:
                parts = render(data, slugs, hero.get(lang, []), rules)
            except Exception as ex:
                msg = f"トップページの書き込みをしませんでした({path}: {ex!r})"
                print("[トップ] " + msg)
                if report is not None:
                    report.append(msg)
                parts = {}
            with open(fp, "w", encoding="utf-8") as f:
                f.write(_fill(s, parts))
    finally:
        i18n.set_lang(keep)


if __name__ == "__main__":
    # python3 top_prerender.py --strip : 手元でビルドしたあと、index.html に書き込まれた中身を空の形に戻す(PR に入れないため)
    import sys
    if "--strip" in sys.argv:
        fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
        with open(fp, encoding="utf-8") as f:
            s = f.read()
        with open(fp, "w", encoding="utf-8") as f:
            f.write(strip(s))
        print("index.html に書き込まれた中身を空の形に戻しました")
