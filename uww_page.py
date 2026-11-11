"""
国際大会(UWW)の動画のページ(Issue #101)。uww_videos.csv から作る。

- /uww/            入り口(年代のカードと新着)
- /uww/<年代>/      年代ごとのページ。大会×年ごとに見出しを付けて折りたたむ
- /uww/senior/<年>/ シニアは本数が多いので年ごとのページに分ける(Issue #294)。/uww/senior/ には
                   すべての年へのリンクと、新しい年(合計 HERE_MAX 本まで)の動画を載せる
- uww_videos.csv は _work/uww/uww_videos.py が作る(週1回のワークフロー uww-weekly.yml で新しい動画を足す)
- 出すのは確かさ「高」「中」の動画だけ
- シニア・U23 は全部出す。U20・U17・U15 は、タイトルに出てくる日本人選手が全員
  「公開=はい・未成年=いいえ」の選手(ctx["players"] にいる人)の動画だけ出す(サイトの未成年の決まり)
- 選手名は ctx["players"] にいる人だけ出し、選手ページへのリンクにする
"""
import csv
import json
import os
import re
from collections import defaultdict

import i18n
from i18n import L, U

CSV_NAME = "uww_videos.csv"
CATS = [("senior", "シニア(または不明)", "シニア", "Senior"), ("u23", "U23", "U23", "U23"), ("u20", "U20", "U20", "U20"),
        ("u17", "U17", "U17", "U17"), ("u15", "U15", "U15", "U15")]
MINOR_CATS = {"u20", "u17", "u15"}
# 大会の並び順と英語名
EVENTS = [("オリンピック", "Olympic Games"), ("オリンピック予選", "Olympic qualifiers"), ("ユース五輪", "Youth Olympic Games"), ("世界選手権", "World Championships"),
          ("ワールドカップ", "World Cup"), ("アジア大会", "Asian Games"), ("アジア選手権", "Asian Championships"),
          ("ランキングシリーズ等", "Ranking Series and other events"), ("", "Other events")]
EV_ORDER = {ja: i for i, (ja, _) in enumerate(EVENTS)}
EV_EN = dict(EVENTS)
KINDS = {"試合": "Match", "試合まとめ": "Match compilation", "ハイライト・特集": "Highlights & features", "インタビュー": "Interview",
         "表彰式": "Medal ceremony", "ショート": "Short", "その他": "Other"}
ROMAN_RE = re.compile(r"\(([A-Za-z][^()]*)\)")
JP_MARK = re.compile(r"\(JPN\)|🇯🇵")


def load(root, ctx):
    """表示する動画を年代ごとに分けて返す"""
    path = os.path.join(root, CSV_NAME)
    if not os.path.exists(path):
        return {}
    by_roman = {p["roman"]: p for p in ctx.get("players", []) if p.get("roman")}
    out = defaultdict(list)
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["確かさ"] not in ("高", "中"):
                continue
            cat = next((c for c, src, _, _ in CATS if src == r["年代"]), "senior")
            names = [by_roman[x] for x in ROMAN_RE.findall(r["日本人選手"]) if x in by_roman]
            if cat in MINOR_CATS:
                # 日本人選手が全員、公開している大人の選手と分かる動画だけ
                if "照合なし" in r["日本人選手"] or not names or len(names) < len(JP_MARK.findall(r["タイトル"])):
                    continue
            out[cat].append({"id": r["動画ID"], "t": r["タイトル"], "p": r["公開日"], "du": r["長さ"], "k": r["種類"],
                             "ev": r["大会"], "y": r["年"], "c": cat, "players": names})
    for lst in out.values():
        lst.sort(key=lambda v: (v["p"], v["id"]), reverse=True)
    return out


def cat_name(cat):
    _, _, ja, en = next(c for c in CATS if c[0] == cat)
    return L(ja, en)


def ev_name(ev):
    return L(ev or "その他の大会", EV_EN.get(ev, ev))


def row(v, bp, me=None):
    """動画1本の行。me(選手ID)を渡すと選手ページ用:大会名と年を出し、「出ている選手」からその選手を外す"""
    e = bp.e
    url = bp.yt(v["id"])
    meta = [f'<span class="d">{L("公開日", "Published")} {e(bp.fmt_date(v["p"]))}</span>']
    if me:
        meta.insert(0, f'<span class="uww-ev">{e(ev_name(v["ev"]))}{" " + e(v["y"]) if v["y"] else ""}{" · " + e(cat_name(v["c"])) if v["c"] != "senior" else ""}</span>')
    if v["du"]:
        meta.append(f'<span class="tabnum">{e(v["du"])}</span>')
    meta.append(f'<span>{e(L(v["k"], KINDS.get(v["k"], "Other")))}</span>')
    pl = "".join(f'<a href="{U("/players/" + p["id"] + "/")}">{e((p["roman"] or p["name"]) if i18n.en() else p["name"])}</a>'
                 for p in v["players"] if p["id"] != me)
    who = f'<div class="uww-who">{L("出ている選手:", "Japanese wrestlers: ")}{pl}</div>' if pl else ""
    return (f'<li class="v"><a href="{e(url)}" target="_blank" rel="noopener" tabindex="-1" aria-hidden="true">{bp.thumb(v["id"])}</a>'
            f'<div><div class="vt"><a href="{e(url)}" target="_blank" rel="noopener"{L(" lang=" + chr(34) + "en" + chr(34), "")}>{e(v["t"])}</a></div>'
            f'<div class="vm">{"".join(meta)}</div>{who}</div></li>')


def intro():
    return L("世界レスリング連合(UWW)の公式 YouTube にある、日本人選手が出ている試合・ハイライトなどの動画を年代ごとにまとめました。"
             "動画はこのサイトの中(YouTube のプレーヤー)で再生できます。動画のタイトルは UWW が公開しているもの(英語)をそのまま表示しています。",
             "Videos featuring Japanese wrestlers from the official YouTube channel of United World Wrestling (UWW), "
             "organized by age category. Videos play right on this site in the YouTube player. Titles are shown as published by UWW.")


def cat_desc(cat, lst, year=None):
    """年代ページの説明文(meta description)。年代名・本数と、そのページに載っている大会名(動画の多い順に最大2つ)をデータから入れる(Issue #224)"""
    cnt = defaultdict(int)
    for v in lst:
        if v["ev"]:
            cnt[v["ev"]] += 1
    top = sorted(cnt, key=lambda ev: (-cnt[ev], EV_ORDER.get(ev, 99)))[:2]
    n = len(lst)
    ja_ev = f"({'・'.join(top)}{'など' if len(cnt) > len(top) else ''})" if top else ""
    en_ev = f" ({', '.join(EV_EN.get(ev, ev) for ev in top)}{' and more' if len(cnt) > len(top) else ''})" if top else ""
    if year:
        return L(f"{year}年の国際大会{ja_ev}で日本人選手が出ている{cat_name(cat)}のレスリング動画{n:,}本を、大会ごとにまとめました。"
                 "世界レスリング連合(UWW)公式 YouTube の動画をこのサイトで再生できます。",
                 f"{year}: {n:,} {cat_name(cat)} international wrestling videos{en_ev} featuring Japanese wrestlers, organized by event. "
                 "Watch videos from the official United World Wrestling (UWW) YouTube channel on this site.")
    return L(f"{cat_name(cat)}の国際大会{ja_ev}で日本人選手が出ているレスリングの動画{n:,}本を、大会・年ごとにまとめました。"
             "世界レスリング連合(UWW)公式 YouTube の動画をこのサイトで再生できます。",
             f"{n:,} {cat_name(cat)} international wrestling videos{en_ev} featuring Japanese wrestlers, organized by event and year. "
             "Watch videos from the official United World Wrestling (UWW) YouTube channel on this site.")


def note(cat):
    if cat == "senior":
        return L("年代が分からない動画も、ここに入れています。", "Videos whose age category is unknown are also listed here.")
    if cat in MINOR_CATS:
        return L("未成年の選手の情報を載せないため、出ている日本人選手が全員、選手ページを公開している大人の選手と確認できた動画だけを載せています。",
                 "To protect minors, only videos in which every Japanese wrestler is a confirmed adult with a public player page are listed.")
    return ""


def page(bp, ctx, path, title, desc, crumbs, body):
    jsonld = {"@context": "https://schema.org", "@graph": [bp.breadcrumb_ld(crumbs),
              {"@type": "CollectionPage", "name": title, "url": bp.SITE + U(path)}]}
    h = bp.head(f"{title}{L('|', ' | ')}{bp.site_name()}", desc, path, "", jsonld, ctx["css"])
    return h + '<main id="content" class="wrap page uww">' + bp.breadcrumb_html(crumbs) + body + "</main>" + bp.footer(ctx["as_of"])


SPLIT_CATS = {"senior"}   # 年ごとのページに分ける年代(Issue #294)
HERE_MAX = 100            # 年代のまとめページに残す「新しい年」の本数の上限(薄い年ページを増やさない)


def here_years(years, by_year):
    """まとめページにそのまま載せる新しい年。新しい年から足していき、合計が HERE_MAX 本を超える手前まで(いちばん新しい年は必ず)"""
    kept, n = [], 0
    for y in years:
        if kept and n + len(by_year[y]) > HERE_MAX:
            break
        kept.append(y)
        n += len(by_year[y])
    return kept


def year_href(cat, y, kept):
    return U(f"/uww/{cat}/") + f"#y{y}" if y in kept else U(f"/uww/{cat}/{y}/")


def years_html(cat, years, by_year, kept, cur, bp, compact=False):
    """年の一覧。compact=False はまとめページのカード(年・本数・大会の数)、True は年ページの上の小さな並び"""
    e = bp.e
    if compact:
        items = "".join(f'<a href="{e(year_href(cat, y, kept))}"{" aria-current=" + chr(34) + "page" + chr(34) if y == cur else ""}>'
                        f'<span class="num">{e(y)}</span></a>' for y in years)
        return f'<nav class="uww-tabs uww-ytabs" aria-label="{L("年", "Year")}">{items}</nav>'
    items = ""
    for y in years:
        vids = by_year[y]
        n_ev = len({v["ev"] for v in vids})
        items += (f'<li><a href="{e(year_href(cat, y, kept))}"><span class="uy-y num">{e(y)}</span>'
                  f'<span class="uy-c">{L(f"{len(vids)}本", f"{len(vids)} videos")}</span>'
                  f'<span class="uy-s">{L(f"{n_ev}大会", i18n.plural(n_ev, "event"))}</span></a></li>')
    return f'<ul class="uww-years">{items}</ul>'


def groups_html(lst, bp, open_n=2):
    """大会×年ごとに折りたたんだ動画の一覧(新しい年・大会の順)。最初の open_n 個だけ開いておく"""
    e = bp.e
    groups = defaultdict(list)
    for v in lst:
        groups[(v["y"], v["ev"])].append(v)
    keys = sorted(groups, key=lambda k: (-int(k[0] or 0), EV_ORDER.get(k[1], 99)))
    h = ""
    for i, k in enumerate(keys):
        vids = sorted(groups[k], key=lambda v: (v["p"], v["t"]))
        head = f'{ev_name(k[1])} {k[0]}'.strip()
        h += (f'<details class="uww-g"{" open" if i < open_n else ""}><summary>{e(head)}<small>{L(f"{len(vids)}本", f"{len(vids)} videos")}</small></summary>'
              f'<ul class="vlist">{"".join(row(v, bp) for v in vids)}</ul></details>')
    return h


def eyebrow(cat=None):
    """見出しの上の細い英字(トップ・大会ページと同じ調子)"""
    return f'<p class="uww-eyebrow" aria-hidden="true">INTERNATIONAL{" / " + cat.upper() if cat else ""}</p>'


def build(root, ctx, bp):
    """(パス, HTML, 更新日) のリストを返す"""
    e = bp.e
    data = load(root, ctx)
    # トップページの「収録○本」に国際大会の本数も足すため、本数を書き出す(index.html が読む)
    with open(os.path.join(root, "assets", "uww-count.js"), "w", encoding="utf-8") as f:
        f.write(f"window.UWW_N={sum(len(v) for v in data.values())};\n")
    write_search_index(root, data)
    if not data:
        return []
    top_t = L("国際大会の動画", "International videos")
    home = (L("トップ", "Home"), "/")
    out = []
    latest = max((v["p"] for lst in data.values() for v in lst), default=None)
    # 入り口
    cards = ""
    for cat, _, _, _ in CATS:
        lst = data.get(cat, [])
        if not lst:
            continue
        evs = len({(v["ev"], v["y"]) for v in lst})
        cards += (f'<li><a href="{U("/uww/" + cat + "/")}"><span class="uc-n">{e(cat_name(cat))}</span>'
                  f'<span class="uc-c">{L(f"{len(lst):,}本", f"{len(lst):,} videos")}</span>'
                  f'<span class="uc-s">{L(f"{evs}大会・年", f"{evs} events")}</span></a></li>')
    new = sorted((v for lst in data.values() for v in lst), key=lambda v: (v["p"], v["id"]), reverse=True)[:20]
    body = (f'{eyebrow()}<h1>{top_t}</h1><p class="lead">{e(intro())}</p>'
            f'<h2>{L("年代から選ぶ", "Choose an age category")}</h2><ul class="uww-cards">{cards}</ul>'
            f'<h2>{L("新着の動画", "Latest videos")}</h2><ul class="vlist">{"".join(row(v, bp) for v in new)}</ul>')
    out.append(("/uww/", page(bp, ctx, "/uww/", top_t, intro(), [home, (top_t, None)], body), latest))
    # 年代ごと。シニアは本数が多い(1ページ 1.5MB)ので年ごとのページに分ける(Issue #294)
    for cat, _, _, _ in CATS:
        lst = data.get(cat, [])
        if not lst:
            continue
        title = L(f"国際大会の動画({cat_name(cat)})", f"International videos ({cat_name(cat)})")
        cpath = f"/uww/{cat}/"
        cat_crumbs = [home, (top_t, "/uww/"), (cat_name(cat), None)]
        nav = "".join(f'<a href="{U("/uww/" + c + "/")}"{" aria-current=" + chr(34) + "page" + chr(34) if c == cat else ""}>{e(cat_name(c))}</a>'
                      for c, _, _, _ in CATS if data.get(c))
        body = f'{eyebrow(cat)}<h1>{e(title)}</h1><p class="lead">{e(intro())}</p>'
        if note(cat):
            body += f'<p class="hint">{e(note(cat))}</p>'
        body += f'<nav class="uww-tabs" aria-label="{L("年代", "Age category")}">{nav}</nav>'
        body += f'<p class="uww-count">{L(f"{len(lst):,}本", f"{len(lst):,} videos")}</p>'
        if cat not in SPLIT_CATS:
            body += groups_html(lst, bp)
            out.append((cpath, page(bp, ctx, cpath, title, cat_desc(cat, lst), cat_crumbs, body), max(v["p"] for v in lst)))
            continue
        by_year = defaultdict(list)
        for v in lst:
            by_year[v["y"]].append(v)
        years = sorted((y for y in by_year if y), key=int, reverse=True)
        kept = here_years(years, by_year)
        # 年の一覧(ふつうのリンク。このページに載せている新しい年は、ページの中の見出しへ)
        body += f'<h2>{L("年から選ぶ", "Choose a year")}</h2>' + years_html(cat, years, by_year, kept, None, bp)
        if kept:
            body += f'<h2>{L("新しい年の動画", "Latest years")}</h2>'
            for y in kept:
                body += (f'<section class="uww-ys" id="y{e(y)}"><h3 class="uww-yh"><span class="num">{e(y)}</span>'
                         f'<small>{L(f"{len(by_year[y])}本", f"{len(by_year[y])} videos")}</small></h3>{groups_html(by_year[y], bp)}</section>')
        if by_year.get(""):
            body += f'<h2>{L("年が分からない動画", "Videos with no year")}</h2>' + groups_html(by_year[""], bp, open_n=0)
        out.append((cpath, page(bp, ctx, cpath, title, cat_desc(cat, lst), cat_crumbs, body), max(v["p"] for v in lst)))
        # 年ごとのページ(まとめページに載せている新しい年は作らない)
        for y in years:
            if y in kept:
                continue
            vids = by_year[y]
            n_ev = len({v["ev"] for v in vids})
            ytitle = L(f"{y}年 国際大会の動画({cat_name(cat)})", f"International videos {y} ({cat_name(cat)})")
            fact = L(f"{y}年の世界レスリング連合(UWW){cat_name(cat)}の大会動画 {len(vids):,}本({n_ev}大会)。",
                     f"{len(vids):,} {cat_name(cat)} videos from {i18n.plural(n_ev, 'United World Wrestling (UWW) event')} in {y}.")
            lead = fact + L("日本人選手が出ている試合・ハイライトなどを大会ごとにまとめました。動画はこのサイトの中で再生できます。動画のタイトルは UWW が公開しているもの(英語)です。",
                            " Matches and highlights featuring Japanese wrestlers, organized by event. Videos play right on this site. Titles are shown as published by UWW.")
            ypath = f"/uww/{cat}/{y}/"
            ybody = (f'{eyebrow(cat)}<h1>{e(ytitle)}</h1><p class="lead">{e(lead)}</p>'
                     + years_html(cat, years, by_year, kept, y, bp, compact=True)
                     + groups_html(vids, bp)
                     + f'<p class="uww-back"><a href="{U(cpath)}">{L(f"{cat_name(cat)}のすべての年を見る", f"See all years ({cat_name(cat)})")}</a></p>')
            crumbs = [home, (top_t, "/uww/"), (cat_name(cat), cpath), (L(f"{y}年", y), None)]
            out.append((ypath, page(bp, ctx, ypath, ytitle, cat_desc(cat, vids, y), crumbs, ybody), max(v["p"] for v in vids)))
    return out


def write_search_index(root, data):
    """トップページの検索で国際大会の動画も探せるように、サイトに出している動画の一覧を assets/uww.json に書く。
    v: i=動画ID t=タイトル p=公開日 c=年代 e=大会 y=年 pl=[選手ID, 氏名, ローマ字, 読み](公開している大人の選手だけ)"""
    rows = [{"i": v["id"], "t": v["t"], "p": v["p"], "c": cat, "e": v["ev"], "y": v["y"],
             "pl": [[p["id"], p["name"], p["roman"], p.get("kana", "")] for p in v["players"]]}
            for cat, lst in data.items() for v in lst]
    rows.sort(key=lambda r: (r["p"], r["i"]), reverse=True)
    out = {"ev": {ja: en for ja, en in EVENTS if ja}, "cat": {c: [ja, en] for c, _, ja, en in CATS}, "v": rows}
    with open(os.path.join(root, "assets", "uww.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))


UWW_CSS = """
.uww{padding-bottom:44px}
.uww h2{font-size:19px;margin:26px 0 10px}
.uww-cards{list-style:none;margin:0 0 6px;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px}
.uww-cards a{display:flex;flex-direction:column;gap:2px;padding:14px 16px;background:var(--surface);border:1px solid var(--line);border-left:3px solid var(--pink);border-radius:10px;text-decoration:none;color:var(--ink)}
.uww-cards a:hover{border-color:var(--line-hi);background:var(--surface-2)}
.uww-cards .uc-n{font-size:20px;font-weight:700}
.uww-cards .uc-c{font-size:15px;font-weight:700;color:var(--pink)}
.uww-cards .uc-s{font-size:12px;color:var(--ink3)}
.uww-tabs{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 12px}
.uww-tabs a{padding:6px 14px;border:1px solid var(--line);border-radius:999px;text-decoration:none;font-weight:700;font-size:14px;color:var(--ink)}
.uww-tabs a[aria-current]{background:var(--pink-fill);border-color:var(--pink-fill);color:#fff}
.uww-count{font-size:13px;color:var(--ink3);margin:0 0 8px}
.uww-g{margin:10px 0;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:10px 14px}
.uww-g summary{cursor:pointer;font-weight:700;font-size:16px}
.uww-g summary small{margin-left:8px;font-weight:400;font-size:12px;color:var(--ink3)}
.uww-g .vlist{margin-top:10px}
.uww-who{font-size:13px;margin-top:4px;color:var(--ink2)}
.uww-who a{margin-right:10px;font-weight:700;padding:6px 0}
.vm .uww-ev{font-weight:700;color:var(--ink2)}
.uww-eyebrow{margin:0 0 4px;font-family:var(--num);font-weight:600;font-size:15px;letter-spacing:.16em;color:var(--pink)}
.uww-years{list-style:none;margin:0 0 6px;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:8px}
.uww-years a{display:flex;flex-direction:column;padding:10px 14px;background:var(--surface);border:1px solid var(--line);border-left:3px solid var(--pink);border-radius:var(--card-r);text-decoration:none;color:var(--ink)}
.uww-years a:hover{border-color:var(--line-hi);background:var(--surface-2)}
.uww-years .uy-y{font-size:32px;line-height:1;padding-top:4px}
.uww-years .uy-c{font-size:14px;font-weight:700;color:var(--pink)}
.uww-years .uy-s{font-size:12px;color:var(--ink3)}
.uww-ytabs a{padding:4px 12px}
.uww-ytabs .num{font-size:18px;line-height:1}
.uww-yh{display:flex;align-items:baseline;gap:8px;margin:22px 0 4px;font-size:16px}
.uww-yh .num{font-size:30px;line-height:1}
.uww-yh small{font-size:12px;font-weight:400;color:var(--ink3)}
.uww-ys{scroll-margin-top:80px}
.uww-back{margin:18px 0 0}
.uww-back a{display:inline-block;padding:10px 0;font-weight:700}
@media (max-width:640px){.uww-years{grid-template-columns:repeat(3,1fr)}.uww-years a{padding:8px 10px}.uww-years .uy-y{font-size:26px}}
"""
