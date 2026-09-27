"""
選手ページの生成(players/)

データは次の2つのCSVファイルから読み込む。どちらもExcelで編集できる。
ファイルが無い・中身が空のときは、選手ページは作られない(サイトには何も出ない)。

  players.csv         … 選手の基本情報(1行 = 1選手)
    選手ID, 氏名, ふりがな, 別表記, 所属, 公開, 未成年

  player_results.csv  … 大会成績(1行 = 1大会の成績)
    選手ID, 開催回ID, 大会名, 開催年, スタイル, 階級, 成績, 出典URL

ルール
  - 「公開」が「はい」で、かつ「未成年」が「いいえ」の選手だけページを作る
    (未成年の選手・公開していない選手は、ページも検索対象も作らない)
  - 選手IDは半角の英小文字・数字・ハイフンのみ(例: yamada-taro)。URLに使われる
  - 別表記は「;」区切り(例: 山田太郎;山田 太朗)
  - 動画との結びつけは、動画タイトルに氏名(または別表記)が含まれるかで自動判定する。
    3文字未満の名前は誤判定が多いので自動判定しない
  - 開催回IDを入れると、成績から開催回ページへリンクする
"""
import csv
import os
import re
import unicodedata
from collections import defaultdict

PLAYERS_CSV = "players.csv"
RESULTS_CSV = "player_results.csv"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
YES = {"はい", "yes", "y", "1", "true", "○", "〇"}


def read_csv(path):
    """Excelで保存したCSV(UTF-8 / Shift-JIS どちらでも)を読む"""
    if not os.path.exists(path):
        return []
    for enc in ("utf-8-sig", "cp932"):
        try:
            with open(path, encoding=enc, newline="") as f:
                return [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]
        except UnicodeDecodeError:
            continue
    return []


def norm(s):
    """全角・半角やスペースの違いを無視して比べるための形にそろえる"""
    s = unicodedata.normalize("NFKC", s or "")
    return re.sub(r"\s+", "", s)


def is_yes(v):
    return norm(v).lower() in YES


def load(root):
    rows = read_csv(os.path.join(root, PLAYERS_CSV))
    results = read_csv(os.path.join(root, RESULTS_CSV))
    report = {"total": len(rows), "published": 0, "hidden_minor": 0, "hidden_private": 0, "errors": []}
    players = []
    seen = set()
    for i, r in enumerate(rows, start=2):  # 2行目からがデータ
        pid, name = r.get("選手ID", ""), r.get("氏名", "")
        if not pid and not name:
            continue
        if not ID_RE.match(pid):
            report["errors"].append(f"players.csv {i}行目: 選手ID「{pid}」は半角英小文字・数字・ハイフンで入力してください")
            continue
        if pid in seen:
            report["errors"].append(f"players.csv {i}行目: 選手ID「{pid}」が重複しています")
            continue
        if not name:
            report["errors"].append(f"players.csv {i}行目: 氏名が空です")
            continue
        seen.add(pid)
        if is_yes(r.get("未成年")):
            report["hidden_minor"] += 1
            continue
        if not is_yes(r.get("公開")):
            report["hidden_private"] += 1
            continue
        names = [name] + [a for a in (r.get("別表記") or "").split(";") if a.strip()]
        players.append({"id": pid, "name": name, "kana": r.get("ふりがな", ""), "club": r.get("所属", ""),
                        "keys": sorted({norm(n) for n in names if len(norm(n)) >= 3}, key=len, reverse=True),
                        "results": [], "videos": []})
    report["published"] = len(players)
    by_id = {p["id"]: p for p in players}
    for r in results:
        p = by_id.get(r.get("選手ID", ""))
        if p:
            p["results"].append(r)
    return players, report


def attach_videos(players, videos):
    """動画タイトルに選手名が含まれる動画を結びつける"""
    n = 0
    titles = [(v, norm(v.get("t"))) for v in videos]
    for p in players:
        if not p["keys"]:
            continue
        hits = {}
        for v, t in titles:
            if any(k in t for k in p["keys"]):
                hits[v["id"]] = v
        p["videos"] = sorted(hits.values(), key=lambda v: v.get("p") or "", reverse=True)
        n += len(p["videos"])
    return n


def result_rows(p, ctx, bp):
    e = bp.e
    slugs = ctx["slugs"]
    rows = sorted(p["results"], key=lambda r: r.get("開催年", ""), reverse=True)
    out = []
    for r in rows:
        name = r.get("大会名", "")
        eid = r.get("開催回ID", "")
        if eid and eid in slugs:
            name_html = f'<a href="/events/{e(slugs[eid])}/">{e(name or eid)}</a>'
        else:
            name_html = e(name)
        src = r.get("出典URL", "")
        src_html = f'<a href="{e(src)}" target="_blank" rel="noopener">出典</a>' if src.startswith("http") else ""
        out.append(f"<tr><td>{e(r.get('開催年', ''))}</td><td>{name_html}</td><td>{e(r.get('スタイル', ''))}</td>"
                   f"<td>{e(r.get('階級', ''))}</td><td><b>{e(r.get('成績', ''))}</b></td><td>{src_html}</td></tr>")
    return out


def player_page(p, ctx, bp):
    e, SITE, SITE_NAME = bp.e, bp.SITE, bp.SITE_NAME
    path = f"/players/{p['id']}/"
    crumbs = [("トップ", "/"), ("選手", "/players/"), (p["name"], None)]
    nv, nr = len(p["videos"]), len(p["results"])
    parts = [f"{p['name']}選手"]
    if p["club"]:
        parts.append(f"({p['club']})")
    parts.append(f"の大会成績{nr}件と試合動画{nv}本。" if nr else f"の試合動画{nv}本。")
    desc = "".join(parts)
    person = {"@type": "Person", "name": p["name"], "url": SITE + path}
    if p["kana"]:
        person["alternateName"] = p["kana"]
    if p["club"]:
        person["affiliation"] = {"@type": "SportsOrganization", "name": p["club"]}
    jsonld = {"@context": "https://schema.org", "@graph": [bp.breadcrumb_ld(crumbs), {
        "@type": "ProfilePage", "url": SITE + path, "mainEntity": person}]}
    og = f"https://i.ytimg.com/vi/{p['videos'][0]['id']}/hqdefault.jpg" if p["videos"] else ""
    h = bp.head(f"{p['name']} 選手 大会成績・試合動画|{SITE_NAME}", desc, path, og, jsonld, ctx["css"])
    h += '<main class="wrap page">' + bp.breadcrumb_html(crumbs)
    kana = f' <small class="kana">{e(p["kana"])}</small>' if p["kana"] else ""
    h += f'<h1>{e(p["name"])}{kana}</h1>'
    h += f'<p class="lead">{e(desc)}</p>'
    if p["club"]:
        h += f'<dl class="facts"><dt>所属</dt><dd>{e(p["club"])}</dd></dl>'
    rows = result_rows(p, ctx, bp)
    if rows:
        h += ('<h2>大会成績</h2><div class="rtable"><table class="results"><thead><tr><th>年</th><th>大会</th>'
              '<th>スタイル</th><th>階級</th><th>成績</th><th></th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>")
    if p["videos"]:
        h += bp.vgroup("試合動画", f"{nv}本・タイトルに選手名を含む動画", p["videos"])
    h += "</main>" + bp.footer(ctx["as_of"])
    return path, h


def index_page(players, ctx, bp):
    e, SITE, SITE_NAME = bp.e, bp.SITE, bp.SITE_NAME
    path = "/players/"
    crumbs = [("トップ", "/"), ("選手", None)]
    ps = sorted(players, key=lambda p: norm(p["kana"] or p["name"]))
    desc = f"掲載している選手{len(ps)}人の一覧。選手ごとの大会成績と試合動画を見られます。"
    jsonld = {"@context": "https://schema.org", "@graph": [bp.breadcrumb_ld(crumbs), {
        "@type": "CollectionPage", "name": "選手一覧", "url": SITE + path,
        "hasPart": [{"@type": "ProfilePage", "name": p["name"], "url": f"{SITE}/players/{p['id']}/"} for p in ps]}]}
    h = bp.head(f"選手一覧({len(ps)}人)|{SITE_NAME}", desc, path, "", jsonld, ctx["css"])
    h += '<main class="wrap page">' + bp.breadcrumb_html(crumbs) + "<h1>選手一覧</h1>"
    h += f'<p class="lead">{e(desc)}</p><ol class="occ slist-static">'
    for p in ps:
        sub = " ".join(x for x in [p["kana"], p["club"]] if x)
        h += (f'<li><a href="/players/{e(p["id"])}/"><span class="ob"><span class="od sname">{e(p["name"])}</span>'
              f'<span class="ov">{e(sub)}</span></span><span class="on"><b class="num">{len(p["videos"])}</b>本</span></a></li>')
    h += "</ol></main>" + bp.footer(ctx["as_of"])
    return path, h


PLAYER_CSS = """
.page h1 .kana{font-size:.5em;font-weight:500;color:var(--ink3);margin-left:10px}
.rtable{overflow-x:auto;margin:8px 0 22px}
table.results{border-collapse:collapse;width:100%;min-width:560px;font-size:14px}
table.results th,table.results td{padding:9px 10px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
table.results th{color:var(--ink3);font-weight:500;font-size:12px}
table.results td b{color:var(--pink)}
"""


def build(root, data, ctx, bp):
    """選手ページを作って (path, doc, lastmod) のリストとレポートを返す"""
    players, report = load(root)
    report["video_links"] = attach_videos(players, data.get("videos", [])) if players else 0
    if not players:
        return [], report
    pages = [(*player_page(p, ctx, bp), data.get("as_of")) for p in players]
    pages.append((*index_page(players, ctx, bp), data.get("as_of")))
    return pages, report
