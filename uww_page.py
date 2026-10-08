"""
国際大会(UWW)の動画のページ(Issue #101)。uww_videos.csv から作る。

- /uww/            入り口(年代のカードと新着)
- /uww/<年代>/      年代ごとのページ。大会×年ごとに見出しを付けて折りたたむ
- uww_videos.csv は _work/uww/uww_videos.py が作る(週1回のワークフロー uww-weekly.yml で新しい動画を足す)
- 出すのは確かさ「高」「中」の動画だけ
- シニア・U23 は全部出す。U20・U17・U15 は、タイトルに出てくる日本人選手が全員
  「公開=はい・未成年=いいえ」の選手(ctx["players"] にいる人)の動画だけ出す(サイトの未成年の決まり)
- 選手名は ctx["players"] にいる人だけ出し、選手ページへのリンクにする
"""
import csv
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
                             "ev": r["大会"], "y": r["年"], "players": names})
    for lst in out.values():
        lst.sort(key=lambda v: (v["p"], v["id"]), reverse=True)
    return out


def cat_name(cat):
    _, _, ja, en = next(c for c in CATS if c[0] == cat)
    return L(ja, en)


def ev_name(ev):
    return L(ev or "その他の大会", EV_EN.get(ev, ev))


def row(v, bp):
    e = bp.e
    url = bp.yt(v["id"])
    meta = [f'<span class="d">{L("公開日", "Published")} {e(bp.fmt_date(v["p"]))}</span>']
    if v["du"]:
        meta.append(f'<span class="tabnum">{e(v["du"])}</span>')
    meta.append(f'<span>{e(L(v["k"], KINDS.get(v["k"], "Other")))}</span>')
    pl = "".join(f'<a href="{U("/players/" + p["id"] + "/")}">{e((p["roman"] or p["name"]) if i18n.en() else p["name"])}</a>'
                 for p in v["players"])
    who = f'<div class="uww-who">{L("出ている選手:", "Japanese wrestlers: ")}{pl}</div>' if pl else ""
    return (f'<li class="v"><a href="{e(url)}" target="_blank" rel="noopener" tabindex="-1" aria-hidden="true">{bp.thumb(v["id"])}</a>'
            f'<div><div class="vt"><a href="{e(url)}" target="_blank" rel="noopener"{L(" lang=" + chr(34) + "en" + chr(34), "")}>{e(v["t"])}</a></div>'
            f'<div class="vm">{"".join(meta)}</div>{who}</div></li>')


def intro():
    return L("世界レスリング連合(UWW)の公式 YouTube にある、日本人選手が出ている試合・ハイライトなどの動画を年代ごとにまとめました。"
             "動画は YouTube で再生されます。動画のタイトルは UWW が公開しているもの(英語)をそのまま表示しています。",
             "Videos featuring Japanese wrestlers from the official YouTube channel of United World Wrestling (UWW), "
             "organized by age category. All videos play on YouTube. Titles are shown as published by UWW.")


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
    return h + '<main class="wrap page uww">' + bp.breadcrumb_html(crumbs) + body + "</main>" + bp.footer(ctx["as_of"])


def build(root, ctx, bp):
    """(パス, HTML, 更新日) のリストを返す"""
    e = bp.e
    data = load(root, ctx)
    # トップページの「収録○本」に国際大会の本数も足すため、本数を書き出す(index.html が読む)
    with open(os.path.join(root, "assets", "uww-count.js"), "w", encoding="utf-8") as f:
        f.write(f"window.UWW_N={sum(len(v) for v in data.values())};\n")
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
    body = (f'<h1>{top_t}</h1><p class="lead">{e(intro())}</p>'
            f'<h2>{L("年代から選ぶ", "Choose an age category")}</h2><ul class="uww-cards">{cards}</ul>'
            f'<h2>{L("新着の動画", "Latest videos")}</h2><ul class="vlist">{"".join(row(v, bp) for v in new)}</ul>')
    out.append(("/uww/", page(bp, ctx, "/uww/", top_t, intro(), [home, (top_t, None)], body), latest))
    # 年代ごと
    for cat, _, _, _ in CATS:
        lst = data.get(cat, [])
        if not lst:
            continue
        groups = defaultdict(list)
        for v in lst:
            groups[(v["y"], v["ev"])].append(v)
        keys = sorted(groups, key=lambda k: (-int(k[0] or 0), EV_ORDER.get(k[1], 99)))
        title = L(f"国際大会の動画({cat_name(cat)})", f"International videos ({cat_name(cat)})")
        nav = "".join(f'<a href="{U("/uww/" + c + "/")}"{" aria-current=" + chr(34) + "page" + chr(34) if c == cat else ""}>{e(cat_name(c))}</a>'
                      for c, _, _, _ in CATS if data.get(c))
        body = f'<h1>{e(title)}</h1><p class="lead">{e(intro())}</p>'
        if note(cat):
            body += f'<p class="hint">{e(note(cat))}</p>'
        body += f'<nav class="uww-tabs" aria-label="{L("年代", "Age category")}">{nav}</nav>'
        body += f'<p class="uww-count">{L(f"{len(lst):,}本", f"{len(lst):,} videos")}</p>'
        for i, k in enumerate(keys):
            vids = sorted(groups[k], key=lambda v: (v["p"], v["t"]))
            head = f'{ev_name(k[1])} {k[0]}'
            body += (f'<details class="uww-g"{" open" if i < 2 else ""}><summary>{e(head)}<small>{L(f"{len(vids)}本", f"{len(vids)} videos")}</small></summary>'
                     f'<ul class="vlist">{"".join(row(v, bp) for v in vids)}</ul></details>')
        path = f"/uww/{cat}/"
        out.append((path, page(bp, ctx, path, title, intro(), [home, (top_t, "/uww/"), (cat_name(cat), None)], body),
                    max(v["p"] for v in lst)))
    return out


UWW_CSS = """
.uww{padding-bottom:44px}
.uww h2{font-size:19px;margin:26px 0 10px}
.uww-cards{list-style:none;margin:0 0 6px;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px}
.uww-cards a{display:flex;flex-direction:column;gap:2px;padding:14px 16px;background:var(--surface);border:1px solid var(--line);border-left:3px solid var(--pink);border-radius:10px;text-decoration:none;color:var(--ink)}
.uww-cards a:hover{border-color:var(--pink)}
.uww-cards .uc-n{font-size:20px;font-weight:900}
.uww-cards .uc-c{font-size:15px;font-weight:700;color:var(--pink)}
.uww-cards .uc-s{font-size:12px;color:var(--ink3)}
.uww-tabs{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 12px}
.uww-tabs a{padding:6px 14px;border:1px solid var(--line);border-radius:999px;text-decoration:none;font-weight:700;font-size:14px;color:var(--ink)}
.uww-tabs a[aria-current]{background:var(--pink);border-color:var(--pink);color:#fff}
.uww-count{font-size:13px;color:var(--ink3);margin:0 0 8px}
.uww-g{margin:10px 0;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:10px 14px}
.uww-g summary{cursor:pointer;font-weight:700;font-size:16px}
.uww-g summary small{margin-left:8px;font-weight:400;font-size:12px;color:var(--ink3)}
.uww-g .vlist{margin-top:10px}
.uww-who{font-size:13px;margin-top:4px;color:var(--ink2)}
.uww-who a{margin-right:10px;font-weight:700}
"""
