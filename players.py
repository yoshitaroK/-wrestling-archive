"""
選手ページの生成(players/)

データは次の2つのCSVファイルから読み込む。どちらもExcelで編集できる。
ファイルが無い・中身が空のときは、選手ページは作られない(サイトには何も出ない)。

  players.csv         … 選手の基本情報(1行 = 1選手)
    選手ID, 氏名, ふりがな, 別表記, 所属, 公開, 未成年, ローマ字, ローマ字確認

  player_results.csv  … 大会成績(1行 = 1大会の成績)
    選手ID, 開催回ID, 大会名, 開催年, スタイル, 階級, 成績, 出典URL

ルール
  - 「公開」が「はい」で、かつ「未成年」が「いいえ」の選手だけページを作る
    (未成年の選手・公開していない選手は、ページも検索対象も作らない)
  - 選手IDは半角の英小文字・数字・ハイフンのみ(例: yamada-taro)。URLに使われる
  - 別表記は「;」区切り(例: 山田太郎;山田 太朗)
  - 動画との結びつけは、動画タイトルに氏名(または別表記)が含まれるかで自動判定する。
    3文字未満の名前は誤判定が多いので自動判定しない
  - 開催回IDを入れると、成績から開催回ページへリンクする。開催回ページには「入賞者」の欄が出る
  - 英語版の選手名は「ローマ字」(例: Kenichiro FUMITA)。「ローマ字確認」が「はい」でない人は
    機械で作った綴りなので、英語版で「Name romanized automatically」と添える
  - 掲載の取りやめの連絡が来たら、その人の「公開」を「いいえ」にする
"""
import csv
import os
import re
import unicodedata
from collections import defaultdict

import i18n
from i18n import L, U, N

# 選手データ(players.csv)が無いときだけ /players/ に出す「準備中」ページの公開予定。空にすると日付なしの「準備中」表示になる
COMING_SOON = ""
COMING_SOON_EN = ""

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
                        "roman": r.get("ローマ字", ""), "roman_ok": is_yes(r.get("ローマ字確認")),
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


RANK_EN = {"1": "1st", "2": "2nd", "3": "3rd"}


def rank(v):
    """成績(例: 1位)。英語版は 1st・2nd・3rd・5th"""
    m = re.match(r"^(\d+)位$", v or "")
    if not i18n.en() or not m:
        return v
    return RANK_EN.get(m.group(1), m.group(1) + "th")


def pname(p):
    """選手名。英語版はローマ字(無ければ日本語のまま)"""
    return (p["roman"] or p["name"]) if i18n.en() else p["name"]


def weight_key(w):
    m = re.match(r"(\d+)", w or "")
    return int(m.group(1)) if m else 999


def tournament_name(r, ctx, bp):
    """成績の大会名。英語版は開催回ページの英語名"""
    ev = ctx["events_by_id"].get(r.get("開催回ID", ""))
    if i18n.en() and ev:
        return bp.event_name(ev, ctx["S"].get(ev["series"], {"id": ev["series"], "name": ev["name"]}))
    return N(r.get("大会名", ""))


def result_rows(p, ctx, bp):
    e = bp.e
    slugs = ctx["slugs"]
    rows = sorted(p["results"], key=lambda r: (r.get("開催年", ""), (ctx["events_by_id"].get(r.get("開催回ID", "")) or {}).get("start") or ""), reverse=True)
    out = []
    for r in rows:
        name = tournament_name(r, ctx, bp)
        eid = r.get("開催回ID", "")
        if eid and eid in slugs:
            name_html = f'<a href="{U("/events/" + slugs[eid] + "/")}">{e(name or eid)}</a>'
        else:
            name_html = e(name)
        src = r.get("出典URL", "")
        src_html = f'<a href="{e(src)}" target="_blank" rel="noopener">{L("出典", "Source")}</a>' if src.startswith("http") else ""
        out.append(f"<tr><td>{e(r.get('開催年', ''))}</td><td>{name_html}</td><td>{e(N(r.get('スタイル', '')))}</td>"
                   f"<td>{e(r.get('階級', ''))}</td><td><b>{e(rank(r.get('成績', '')))}</b></td><td>{src_html}</td></tr>")
    return out


def optout_note(listing=False):
    """選手ページ・選手一覧の下の「掲載の取りやめ」の案内"""
    if listing:
        return ('<p class="optout">' + L(
            f'掲載の取りやめをご希望の選手ご本人・関係者の方は、<a href="{U("/contact.html")}">お問い合わせ</a>からご連絡ください。',
            f'If you are a listed player (or represent one) and would like the listing removed, please contact us via the <a href="{U("/contact.html")}">contact page</a>.')
            + "</p>")
    return ('<p class="optout">' + L(
        f'掲載の取りやめをご希望の方は、<a href="{U("/contact.html")}">お問い合わせ</a>からご連絡ください。確認のうえ、ページを削除します。',
        f'If you would like this page removed, please let us know via the <a href="{U("/contact.html")}">contact page</a>. '
        'We will remove it after confirming the request.') + "</p>")


def player_page(p, ctx, bp):
    e, SITE = bp.e, bp.SITE
    path = f"/players/{p['id']}/"
    name = pname(p)
    club = N(p["club"])
    crumbs = [(L("トップ", "Home"), "/"), (L("選手", "Players"), "/players/"), (name, None)]
    nv, nr = len(p["videos"]), len(p["results"])
    if i18n.en():
        desc = f"{name}{(' (' + club + ')') if club else ''}: " + (
            f"{i18n.plural(nr, 'tournament result')} and {i18n.plural(nv, 'match video')}." if nr else f"{i18n.plural(nv, 'match video')}.")
    else:
        parts = [f"{name}選手"]
        if club:
            parts.append(f"({club})")
        parts.append(f"の大会成績{nr}件と試合動画{nv}本。" if nr else f"の試合動画{nv}本。")
        desc = "".join(parts)
    person = {"@type": "Person", "name": name, "url": SITE + U(path)}
    if p["kana"] and not i18n.en():
        person["alternateName"] = p["kana"]
    if club:
        person["affiliation"] = {"@type": "SportsOrganization", "name": club}
    jsonld = {"@context": "https://schema.org", "@graph": [bp.breadcrumb_ld(crumbs), {
        "@type": "ProfilePage", "url": SITE + U(path), "mainEntity": person}]}
    og = f"https://i.ytimg.com/vi/{p['videos'][0]['id']}/hqdefault.jpg" if p["videos"] else ""
    h = bp.head(L(f"{name} 選手 大会成績・試合動画|{bp.SITE_NAME}", f"{name} – Results & Match Videos | {bp.site_name()}"), desc, path, og, jsonld, ctx["css"])
    h += '<main class="wrap page">' + bp.breadcrumb_html(crumbs)
    if i18n.en():
        sub = "" if p["roman_ok"] or not p["roman"] else ' <small class="kana">Name romanized automatically</small>'
    else:
        jsub = p["kana"] or (p["roman"] if p["roman_ok"] else "")
        sub = f' <small class="kana">{e(jsub)}</small>' if jsub else ""
    h += f'<h1>{e(name)}{sub}</h1>'
    h += f'<p class="lead">{e(desc)}</p>'
    if club:
        h += f'<dl class="facts"><dt>{L("所属", "Club / school")}</dt><dd>{e(club)}</dd></dl>'
    rows = result_rows(p, ctx, bp)
    if rows:
        h += (f'<h2>{L("大会成績", "Tournament results")}</h2><div class="rtable"><table class="results"><thead><tr><th>{L("年", "Year")}</th><th>{L("大会", "Tournament")}</th>'
              f'<th>{L("スタイル", "Style")}</th><th>{L("階級", "Weight")}</th><th>{L("成績", "Result")}</th><th></th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>")
        h += '<p class="hint">' + L("成績は日本レスリング協会が公開している入賞者一覧から作っています。所属は大会のときのものです。",
                                    "Results are compiled from the medalist lists published by the Japan Wrestling Federation. Clubs are as of each tournament.") + "</p>"
    if p["videos"]:
        h += bp.vgroup(L("試合動画", "Match videos"), L(f"{nv}本・タイトルに選手名を含む動画", f"{i18n.plural(nv, 'video')} whose title contains the player's name"), p["videos"])
    h += optout_note()
    h += "</main>" + bp.footer(ctx["as_of"])
    return path, h


def index_page(players, ctx, bp):
    e, SITE = bp.e, bp.SITE
    path = "/players/"
    crumbs = [(L("トップ", "Home"), "/"), (L("選手", "Players"), None)]
    # 所属ごとにまとめ、人数の多い所属から。所属の中は入賞の多い順
    groups = defaultdict(list)
    for p in players:
        groups[p["club"]].append(p)
    order = sorted(groups, key=lambda c: (-len(groups[c]), c == "", norm(c)))
    desc = L(f"掲載している選手{len(players)}人の一覧。名前や所属で検索でき、選手ごとの大会成績と試合動画を見られます。",
             f"{i18n.plural(len(players), 'player')} listed. Search by name or club to see each player's tournament results and match videos.")
    jsonld = {"@context": "https://schema.org", "@graph": [bp.breadcrumb_ld(crumbs), {
        "@type": "CollectionPage", "name": L("選手一覧", "Players"), "url": SITE + U(path)}]}
    h = bp.head(L(f"選手検索・選手一覧({len(players)}人)|{bp.SITE_NAME}", f"Player search ({len(players)} players) | {bp.site_name()}"), desc, path, "", jsonld, ctx["css"])
    h += '<main class="wrap page">' + bp.breadcrumb_html(crumbs) + f"<h1>{L('選手検索', 'Player search')}</h1>"
    h += f'<p class="lead">{e(desc)}</p>'
    h += (f'<div class="psearch"><input type="search" id="pq" placeholder="{L("選手名・所属で検索", "Search by name or club")}" '
          f'aria-label="{L("選手名・所属で検索", "Search by name or club")}" autocomplete="off"><p class="pcount" id="pcount" aria-live="polite"></p></div>')
    h += '<div id="plist">'
    for c in order:
        ps = sorted(groups[c], key=lambda p: (-len(p["results"]), norm(p["roman"] or p["name"])))
        cname = N(c) or L("所属なし", "No club listed")
        h += f'<section class="pgroup"><h2 class="vh">{e(cname)} <small>{L(f"{len(ps)}人", i18n.plural(len(ps), "player"))}</small></h2><ol class="occ slist-static">'
        for p in ps:
            key = " ".join(norm(x).lower() for x in [p["name"], p["roman"], p["kana"], p["club"], N(p["club"]) if i18n.en() else ""] if x)
            # 日本語版では、確かめていないローマ字は出さない(英語版は名前そのものがローマ字)
            sub = (p["kana"] or (p["roman"] if p["roman_ok"] else "")) if not i18n.en() else ""
            nr, nv = len(p["results"]), len(p["videos"])
            stat = L(f"入賞{nr}回", i18n.plural(nr, "medal")) + (L(f"・動画{nv}本", f" · {i18n.plural(nv, 'video')}") if nv else "")
            h += (f'<li data-k="{e(key)}"><a href="{U("/players/" + p["id"] + "/")}"><span class="ob"><span class="od sname">{e(pname(p))}</span>'
                  f'<span class="ov">{e(sub)}</span></span><span class="on">{e(stat)}</span></a></li>')
        h += "</ol></section>"
    h += "</div>"
    h += '<p class="hint">' + L("日本レスリング協会が公開している、大人の大会(天皇杯・明治杯・全日本社会人・大学の大会など)の入賞者一覧から作っています。",
                                "Compiled from the medalist lists the Japan Wrestling Federation publishes for senior tournaments (Emperor's Cup, Meiji Cup, university championships and more).")
    h += L("英語版の選手名は、確認できた人を除き機械でローマ字にしています。", " Player names are romanized automatically unless confirmed.") + "</p>"
    h += optout_note(listing=True)
    h += PLAYER_SEARCH_JS.replace("__ALL__", L("全{n}人", "{n} players")).replace("__HIT__", L("{n}人が見つかりました", "{n} found")).replace("__NONE__", L("見つかりませんでした", "No players found"))
    h += "</main>" + bp.footer(ctx["as_of"])
    return path, h


PLAYER_SEARCH_JS = r"""<script>
(function(){
  var q=document.getElementById('pq'),c=document.getElementById('pcount');
  var items=[].slice.call(document.querySelectorAll('#plist li')),groups=[].slice.call(document.querySelectorAll('#plist .pgroup'));
  function n(s){return (s||'').normalize('NFKC').toLowerCase().replace(/\s+/g,'');}
  function run(){
    var t=n(q.value),hit=0;
    items.forEach(function(li){var ok=!t||li.getAttribute('data-k').replace(/\s+/g,'').indexOf(t)>=0;li.hidden=!ok;if(ok)hit++;});
    groups.forEach(function(g){g.hidden=!g.querySelector('li:not([hidden])');});
    c.textContent=t?(hit?'__HIT__'.replace('{n}',hit):'__NONE__'):'__ALL__'.replace('{n}',items.length);
    try{history.replaceState(null,'',t?'#q='+encodeURIComponent(q.value):location.pathname);}catch(x){}
  }
  var m=/[#&]q=([^&]*)/.exec(location.hash);if(m){try{q.value=decodeURIComponent(m[1]);}catch(x){}}
  q.addEventListener('input',run);run();
})();
</script>"""


def winners_html(ev, ctx, bp):
    """開催回ページの「入賞者」の欄(公開している選手だけ)"""
    lst = ctx.get("winners", {}).get(ev["id"])
    if not lst:
        return ""
    e = bp.e
    by_style = defaultdict(lambda: defaultdict(list))
    for p, r in lst:
        by_style[r.get("スタイル", "")][r.get("階級", "")].append((p, r))
    style_order = ["フリースタイル", "グレコローマン", "女子"]

    def skey(s):
        base = s.replace("新人戦", "").strip()
        return ("新人戦" in s, style_order.index(base) if base in style_order else 9, s)
    body = ""
    for st in sorted(by_style, key=skey):
        rows = ""
        for w in sorted(by_style[st], key=weight_key):
            cells = []
            for p, r in sorted(by_style[st][w], key=lambda x: (weight_key(x[1].get("成績", "").replace("位", "")), pname(x[0]))):
                cells.append(f'<span class="wr"><b>{e(rank(r.get("成績", "")))}</b> <a href="{U("/players/" + p["id"] + "/")}">{e(pname(p))}</a>'
                             f'{(" <small>" + e(N(p["club"])) + "</small>") if p["club"] else ""}</span>')
            rows += f"<tr><th>{e(w)}</th><td>{''.join(cells)}</td></tr>"
        body += f'<h3>{e(N(st))}</h3><div class="rtable"><table class="winners"><tbody>{rows}</tbody></table></div>'
    n = len({p["id"] for p, _ in lst})
    return (f'<details class="more-box winners-box"><summary>{L(f"入賞者({n}人)", "Medalists (" + i18n.plural(n, "player") + ")")}</summary>'
            '<p class="hint">' + L("日本レスリング協会の入賞者一覧から作っています。選手名から選手ページへ移れます。掲載していない選手もいます。",
                                   "From the Japan Wrestling Federation medalist list. Select a name to open the player page. Some players are not listed.") + "</p>"
            + body + "</details>")


def coming_soon_page(ctx, bp):
    e, SITE = bp.e, bp.SITE
    path = "/players/"
    title = L("選手検索", "Player search")
    crumbs = [(L("トップ", "Home"), "/"), (title, None)]
    if i18n.en():
        when = f"Coming {COMING_SOON_EN}" if COMING_SOON_EN else "In preparation"
        desc = f"Player search — find a wrestler's tournament results and match videos by name — is in preparation ({when})."
    else:
        when = f"{COMING_SOON}公開予定" if COMING_SOON else "準備中"
        desc = f"選手名から大会成績と試合動画を探せる「選手検索」を準備しています({when})。"
    jsonld = {"@context": "https://schema.org", "@graph": [bp.breadcrumb_ld(crumbs), {
        "@type": "WebPage", "name": L("選手検索(準備中)", "Player search (coming soon)"), "url": SITE + U(path)}]}
    h = bp.head(L(f"選手検索({when})|{bp.SITE_NAME}", f"Player search ({when}) | {bp.site_name()}"), desc, path, "", jsonld, ctx["css"])
    h += '<main class="wrap page soon">' + bp.breadcrumb_html(crumbs)
    h += f'<p class="soon-badge">COMING SOON</p><h1>{title}</h1><p class="soon-when">{e(when)}</p>'
    if i18n.en():
        h += ('<p class="lead">You will be able to search for a wrestler by name and see their tournament results and match videos in one place.</p>'
              '<ul class="soon-list">'
              '<li><b>Search by name</b><span>Full names and alternative spellings</span></li>'
              '<li><b>Tournament results</b><span>Tournaments, weight classes and results by year</span></li>'
              '<li><b>Match videos together</b><span>All streams featuring the wrestler in one place</span></li>'
              '</ul>'
              '<p class="soon-note">Until then, browse videos by tournament on the <a href="/en/events/">tournament list</a> '
              'or see the <a href="/en/technique/">technique videos</a>.</p>')
    else:
        h += ('<p class="lead">選手の名前から、その選手の大会成績と試合動画をまとめて探せるようになります。</p>'
              '<ul class="soon-list">'
              '<li><b>選手名で検索</b><span>フルネームや別の表記からでも探せます</span></li>'
              '<li><b>大会成績の一覧</b><span>出場した大会・階級・成績を年ごとに</span></li>'
              '<li><b>試合動画をまとめて</b><span>その選手が出ている配信動画を一か所に</span></li>'
              '</ul>'
              '<p class="soon-note">公開まで、大会ごとの動画は<a href="/events/">大会一覧</a>から、'
              '技術動画は<a href="/technique/">技術動画</a>からご覧いただけます。</p>')
    h += "</main>" + bp.footer(ctx["as_of"])
    return path, h


PLAYER_CSS = """
.soon{padding-bottom:48px}
.soon .soon-badge{display:inline-block;margin:10px 0 4px;padding:3px 12px;border-radius:999px;font-size:12px;font-weight:700;
  letter-spacing:.12em;color:#fff;background:linear-gradient(90deg,var(--grad-a),var(--grad-b))}
.soon h1{margin-top:4px}
.soon .soon-when{font-size:22px;font-weight:700;color:var(--pink);margin:0 0 10px}
.soon .soon-list{list-style:none;padding:0;margin:18px 0;display:grid;gap:10px;max-width:640px}
.soon .soon-list li{background:var(--surface);border:1px solid var(--line);border-left:3px solid var(--pink);border-radius:10px;padding:12px 16px}
.soon .soon-list b{display:block;font-size:16px}
.soon .soon-list span{font-size:13px;color:var(--ink3)}
.soon .soon-note{font-size:14px;color:var(--ink2)}
.page h1 .kana{font-size:.5em;font-weight:500;color:var(--ink3);margin-left:10px}
.psearch{margin:8px 0 6px}
.psearch input{width:100%;box-sizing:border-box;font-size:16px;padding:12px 14px;border-radius:10px;border:1px solid var(--line);background:var(--surface);color:var(--ink)}
.psearch input:focus{outline:2px solid var(--pink);outline-offset:1px}
.psearch .pcount{margin:6px 2px 0;font-size:13px;color:var(--ink3)}
.pgroup{margin:18px 0}
#plist .occ a{grid-template-columns:1fr auto}
.pgroup[hidden],#plist li[hidden]{display:none}
.optout{margin-top:28px;padding-top:14px;border-top:1px solid var(--line);font-size:13px;color:var(--ink3)}
table.winners{border-collapse:collapse;width:100%;font-size:14px}
table.winners th{width:64px;padding:8px 10px 8px 0;text-align:left;vertical-align:top;color:var(--ink3);font-weight:500;white-space:nowrap;border-bottom:1px solid var(--line)}
table.winners td{padding:6px 0;border-bottom:1px solid var(--line)}
table.winners .wr{display:inline-block;margin:2px 14px 2px 0}
table.winners .wr b{color:var(--pink);font-weight:700;margin-right:2px}
table.winners .wr small{color:var(--ink3);font-size:12px}
.winners-box h3{font-size:15px;margin:14px 0 4px}
.rtable{overflow-x:auto;margin:8px 0 22px}
table.results{border-collapse:collapse;width:100%;min-width:560px;font-size:14px}
table.results th,table.results td{padding:9px 10px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
table.results th{color:var(--ink3);font-weight:500;font-size:12px}
table.results td b{color:var(--pink)}
"""


def prepare(root, data, ctx):
    """選手データを読み、動画と開催回に結びつけて ctx に入れる(日本語版・英語版の前に1回だけ)"""
    players, report = load(root)
    report["video_links"] = attach_videos(players, data.get("videos", [])) if players else 0
    winners = defaultdict(list)
    for p in players:
        for r in p["results"]:
            if r.get("開催回ID"):
                winners[r["開催回ID"]].append((p, r))
    ctx["players"], ctx["winners"] = players, winners
    ctx["events_by_id"] = {ev["id"]: ev for ev in data.get("events", [])}
    return report


def build(root, data, ctx, bp):
    """選手ページを作って (path, doc, lastmod) のリストを返す(prepare のあとで呼ぶ)"""
    players = ctx.get("players") or []
    if not players:
        return [(*coming_soon_page(ctx, bp), data.get("as_of"))]
    pages = [(*player_page(p, ctx, bp), data.get("as_of")) for p in players]
    pages.append((*index_page(players, ctx, bp), data.get("as_of")))
    return pages
