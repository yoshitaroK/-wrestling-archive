"""
大会カレンダー(/events/calendar/)の生成

master_events.json(data.json の events)に入っている大会を月ごとのカレンダーに並べる。
大会を押すと、次の順でリンク先を決める。
  1. その開催回のページがある(動画がある)→ 開催回ページ
  2. 大会(系列)のページがある           → 大会ページ(過去の開催回の動画が見られる)
  3. どちらもないが公式の情報源URLがある → 公式サイト(別タブ)
  4. どれもない                         → リンクなし(名前だけ表示)
events/ フォルダの中に作るので、自動更新の保存対象(update.yml)を変える必要はない。
"""
import hashlib
import json
import re
from urllib.parse import urlencode
from datetime import datetime, timedelta, timezone

import i18n
from i18n import L, U, N

JST = timezone(timedelta(hours=9))
SITE = "https://japanwrestlingchannel.com"
ICS_DIR = "/events/calendar/ics/"   # 「カレンダーに追加」用のファイル(.ics)を置く場所。ビルドのたびに作り直す


def today_jst():
    return datetime.now(JST).strftime("%Y-%m-%d")


def ics_text(s):
    return str(s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def ics_fold(line):
    """iCalendar の決まりで、1行を75バイト以内に折り返す"""
    out, cur = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        if len(cur) + len(b) > (75 if not out else 74):
            out.append(cur.decode("utf-8"))
            cur = b""
        cur += b
    out.append(cur.decode("utf-8"))
    return "\r\n ".join(out)


def add_to_calendar(key, name, start, end, venue, url, ctx):
    """これから開催される大会の「カレンダーに追加」。Google カレンダーのURLと .ics ファイルのURLを返し、
    .ics の中身は ctx["ics"] に入れておく(build_pages.build() がまとめて書き出す)"""
    end1 = (datetime.strptime(end or start, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y%m%d")
    s0 = start.replace("-", "")
    page = (SITE + url) if url.startswith("/") else url
    detail = (L("大会の情報と配信:", "Tournament info and streams: ") + page) if page else ""
    gc = "https://calendar.google.com/calendar/render?" + urlencode(
        {"action": "TEMPLATE", "text": name, "dates": f"{s0}/{end1}", "location": venue or "", "details": detail})
    k = re.sub(r"[^a-z0-9-]", "", key.lower())
    if k != key.lower():
        k += "-" + hashlib.md5(key.encode("utf-8")).hexdigest()[:6]
    ic = U(ICS_DIR + k + ".ics")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Japan Wrestling Channel//Archive//" + L("JA", "EN"), "CALSCALE:GREGORIAN",
             "METHOD:PUBLISH", "BEGIN:VEVENT", f"UID:{k}@japanwrestlingchannel.com", f"DTSTAMP:{s0}T000000Z",
             f"DTSTART;VALUE=DATE:{s0}", f"DTEND;VALUE=DATE:{end1}", "SUMMARY:" + ics_text(name)]
    if venue:
        lines.append("LOCATION:" + ics_text(venue))
    if page:
        lines += ["URL:" + page, "DESCRIPTION:" + ics_text(detail)]
    lines += ["END:VEVENT", "END:VCALENDAR"]
    ctx.setdefault("ics", {})[ic] = "\r\n".join(ics_fold(x) for x in lines) + "\r\n"
    return gc, ic


def add_buttons_html(gc, ic, e, cls="elink"):
    return (f'<a class="{cls} addcal" href="{e(gc)}" target="_blank" rel="noopener">{L("Google カレンダーに追加", "Add to Google Calendar")} ↗</a>'
            f'<a class="{cls} addcal" href="{e(ic)}" download>{L("iPhone・Outlook などに追加(.ics)", "Add to Apple / Outlook (.ics)")}</a>')
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def entries(data, ctx):
    slugs, S = ctx["slugs"], ctx["S"]
    out = []
    for ev in data["events"]:
        name = ev.get("official_name") or ev.get("name") or ""
        if i18n.en():
            # 英語版は開催回の正式名ではなく、大会名の英語を使う
            name = N(S.get(ev["series"], {}).get("name") or name)
        if ev["id"] in slugs:
            url, ext = U(f"/events/{slugs[ev['id']]}/"), False
        elif S.get(ev["series"], {}).get("n"):
            url, ext = U(f"/events/{ev['series']}/"), False
        else:
            src = next((x.get("url") for x in ev.get("sources") or [] if (x.get("url") or "").startswith("http")), "")
            url, ext = src, bool(src)
        base = {"u": url, "x": ext, "vid": bool(ev.get("n")), "st": ev.get("status") or "",
                "d": bool(ev.get("derived"))}
        sessions = [x for x in ev.get("sessions") or [] if DATE_RE.match(x.get("start_date") or "")]
        if sessions:
            for i, x in enumerate(sessions, 1):
                base["k"] = f"{ev['id']}-{i}"
                label = N(x.get("label") or "")
                out.append(dict(base, n=(f"{name} {label}" if not i18n.en() else (label or name)).strip(), s=x["start_date"][:10],
                                e=(x.get("end_date") or x["start_date"])[:10], v=N(x.get("venue") or ev.get("venue") or "")))
        elif DATE_RE.match(ev.get("start") or ""):
            base["k"] = ev["id"]
            out.append(dict(base, n=name, s=ev["start"][:10], e=(ev.get("end") or ev["start"])[:10],
                            v=N(ev.get("venue") or "")))
    today = today_jst()
    for x in out:
        if x["e"] >= today and x["st"] not in ("cancelled", "postponed") and not x["d"]:
            x["gc"], x["ic"] = add_to_calendar(x["k"], x["n"], x["s"], x["e"], x["v"], x["u"], ctx)
        x.pop("k")
    out.sort(key=lambda x: (x["s"], x["n"]))
    return out


def fmt_md(s, e):
    a = f"{int(s[5:7])}/{int(s[8:10])}"
    if e and e != s:
        b = f"{int(e[5:7])}/{int(e[8:10])}" if e[:7] != s[:7] else f"{int(e[8:10])}"
        return f"{a}{L('〜', '–')}{b}"
    return a


# カレンダーの画面に出す文字(JavaScript に渡す)
JS_TEXT = {
    "ja": {"ym": "{y}年{m}月", "wd": ["日", "月", "火", "水", "木", "金", "土"], "more": "ほか{n}件", "cell": "{m}月{d}日 大会{n}件",
           "day": "{m}月{d}日の大会", "month": "この月の大会({n}件)", "can": "中止", "vid": "動画あり", "sch": "予定",
           "derived": "(配信日)", "noday": "この日の大会はありません。", "nomonth": "この月に登録されている大会はありません。", "dash": "〜",
           "gc": "＋ Google カレンダー", "ic": "＋ iPhone・Outlook など"},
    "en": {"ym": "{M} {y}", "wd": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"], "more": "+{n} more", "cell": "{M} {d}: {n} tournaments",
           "day": "Tournaments on {M} {d}", "month": "Tournaments this month ({n})", "can": "Cancelled", "vid": "Videos", "sch": "Scheduled",
           "derived": " (stream dates)", "noday": "No tournaments on this day.", "nomonth": "No tournaments listed for this month.", "dash": "–",
           "gc": "+ Google Calendar", "ic": "+ Apple / Outlook"},
}


def calendar_page(data, ctx, bp):
    e, SITE = bp.e, bp.SITE
    path = "/events/calendar/"
    cal_t = L("大会カレンダー", "Tournament calendar")
    crumbs = [(L("トップ", "Home"), "/"), (L("大会一覧", "Tournaments"), "/events/"), (cal_t, None)]
    items = entries(data, ctx)
    today = datetime.now(JST).strftime("%Y-%m-%d")
    soon = [x for x in items if x["e"] >= today][:40]
    desc = L("レスリング大会の開催予定と過去の大会をカレンダーで確認できます。大会を選ぶと、その大会の配信動画ページへ移動します。",
             "Upcoming and past Japanese wrestling tournaments on a calendar. Choose a tournament to open its video page.")
    ld_events = [{"@type": "SportsEvent", "name": x["n"], "startDate": x["s"], "endDate": x["e"],
                  **({"location": {"@type": "Place", "name": x["v"]}} if x["v"] else {}),
                  **({"url": SITE + x["u"]} if x["u"] and not x["x"] else {})}
                 for x in soon if not x["d"] and x["st"] != "cancelled"][:20]
    jsonld = {"@context": "https://schema.org", "@graph": [bp.breadcrumb_ld(crumbs),
              {"@type": "CollectionPage", "name": cal_t, "url": SITE + U(path), "hasPart": ld_events}]}
    h = bp.head(f"{cal_t}{L('|', ' | ')}{bp.site_name()}", desc, path, "", jsonld, ctx["css"])
    h += '<main class="wrap page cal">' + bp.breadcrumb_html(crumbs)
    h += f'<h1>{cal_t}</h1><p class="lead">{e(desc)}</p>'
    h += (f'<div class="cal-bar"><button type="button" class="cal-nav" id="cal-prev" aria-label="{L("前の月", "Previous month")}">‹</button>'
          '<h2 id="cal-title" aria-live="polite"></h2>'
          f'<button type="button" class="cal-nav" id="cal-next" aria-label="{L("次の月", "Next month")}">›</button>'
          f'<button type="button" class="cal-today" id="cal-today">{L("今月", "This month")}</button></div>'
          f'<p class="cal-legend"><span class="lg vid">{L("動画あり", "Videos available")}</span><span class="lg sch">{L("開催予定・動画なし", "Scheduled / no videos")}</span>'
          f'<span class="lg can">{L("中止", "Cancelled")}</span></p>'
          '<div class="cal-grid" id="cal-grid" role="grid"></div>'
          f'<div class="cal-listhead"><h2 id="cal-listtitle">{L("この月の大会", "Tournaments this month")}</h2>'
          f'<button type="button" class="cal-all" id="cal-all" hidden>{L("月の大会をすべて表示", "Show the whole month")}</button></div>')
    # JavaScriptが動かない環境・検索エンジン向けに、これからの大会を最初から書いておく
    h += '<ol class="cal-list" id="cal-list">'
    for x in soon:
        h += list_item(x, e)
    if not soon:
        h += f'<li class="cal-empty">{L("登録されている予定の大会はありません。", "No upcoming tournaments are listed.")}</li>'
    h += "</ol></main>"
    h += "<script>var CAL_T=" + json.dumps(JS_TEXT[i18n.LANG], ensure_ascii=False) + ";</script>"
    h += "<script>var CAL_EVENTS=" + json.dumps(items, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + ";</script>"
    h += CAL_JS + bp.footer(ctx["as_of"])
    return path, h


def list_item(x, e):
    cls = "can" if x["st"] == "cancelled" else ("vid" if x["vid"] else "sch")
    badge = JS_TEXT[i18n.LANG][cls]
    name = e(x["n"])
    if x["u"]:
        tgt = ' target="_blank" rel="noopener"' if x["x"] else ""
        name = f'<a href="{e(x["u"])}"{tgt}>{name}{" ↗" if x["x"] else ""}</a>'
    note = JS_TEXT[i18n.LANG]["derived"] if x["d"] else ""
    T = JS_TEXT[i18n.LANG]
    add = (f'<span class="addc"><a href="{e(x["gc"])}" target="_blank" rel="noopener">{T["gc"]}</a>'
           f'<a href="{e(x["ic"])}" download>{T["ic"]}</a></span>') if x.get("gc") else ""
    return (f'<li class="{cls}"><span class="cd">{e(fmt_md(x["s"], x["e"]))}{note}</span>'
            f'<span class="cn">{name}<small>{e(x["v"])}</small>{add}</span><span class="cb">{badge}</span></li>')


CAL_CSS = """
.cal{padding-bottom:40px}
.cal-bar{display:flex;align-items:center;gap:10px;margin:14px 0 8px;flex-wrap:wrap}
.cal-bar h2{margin:0;min-width:150px;text-align:center;font-size:22px}
.cal-nav,.cal-today,.cal-all{font:inherit;color:var(--ink);background:var(--surface);border:1px solid var(--line);border-radius:999px;cursor:pointer}
.cal-nav{width:40px;height:40px;font-size:22px;line-height:1}
.cal-today,.cal-all{padding:7px 14px;font-size:13px}
.cal-nav:hover,.cal-today:hover,.cal-all:hover{border-color:var(--pink)}
.cal-legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--ink3);margin:0 0 10px}
.cal-legend .lg::before{content:"";display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px;vertical-align:0}
.lg.vid::before{background:var(--pink)}.lg.sch::before{background:#5b8def}.lg.can::before{background:#6b6a73}
.cal-grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));border:1px solid var(--line);border-radius:12px;overflow:hidden;background:var(--line);gap:1px}
.cal-grid .wd{background:var(--bg2);text-align:center;font-size:12px;color:var(--ink3);padding:6px 0}
.cal-grid .wd.sun{color:#ff6a8a}.cal-grid .wd.sat{color:#7aa6ff}
.cal-grid .day{background:var(--surface);min-height:104px;padding:5px;display:flex;flex-direction:column;gap:3px;cursor:pointer;border:0;text-align:left;font:inherit;color:inherit}
.cal-grid .day.out{background:var(--bg2);opacity:.45;cursor:default}
.cal-grid .day.today{box-shadow:inset 0 0 0 2px var(--pink)}
.cal-grid .day.sel{background:var(--surface-2)}
.cal-grid .dn{font-size:13px;font-weight:700;color:var(--ink2)}
.cal-grid .day.sun .dn{color:#ff6a8a}.cal-grid .day.sat .dn{color:#7aa6ff}
.cal-grid .chip{display:block;font-size:11px;line-height:1.35;padding:2px 5px;border-radius:5px;color:#fff;text-decoration:none;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.chip.vid{background:var(--pink)}.chip.sch{background:#2f4f8f}.chip.can{background:#3a3a42;text-decoration:line-through}
.cal-grid .cal-more{font-size:11px;color:var(--ink3)}
.cal-grid .dots{display:none;gap:3px;flex-wrap:wrap}
.cal-grid .dots i{width:7px;height:7px;border-radius:50%}
.dots i.vid{background:var(--pink)}.dots i.sch{background:#5b8def}.dots i.can{background:#6b6a73}
.cal-listhead{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:26px 0 6px;flex-wrap:wrap}
.cal-listhead h2{margin:0;font-size:18px}
.cal-list{list-style:none;padding:0;margin:0;border-top:1px solid var(--line)}
.cal-list li{display:grid;grid-template-columns:88px 1fr auto;gap:12px;align-items:center;padding:11px 4px;border-bottom:1px solid var(--line)}
.cal-list .cd{font-weight:700;font-size:14px;color:var(--ink2)}
.cal-list .cn{font-size:15px;line-height:1.45}
.cal-list .cn small{display:block;font-size:12px;color:var(--ink3)}
.cal-list .cn a{color:var(--ink);text-decoration:none}
.cal-list .cn a:hover{color:var(--pink)}
.cal-list .cb{font-size:11px;padding:2px 9px;border-radius:999px;white-space:nowrap}
.cal-list .vid .cb{background:var(--pink-tint);color:var(--pink)}
.cal-list .sch .cb{background:rgba(91,141,239,.16);color:#8fb0ff}
.cal-list .can .cb{background:#26262c;color:var(--ink3)}
[data-theme="light"] .cal-grid .wd.sun,[data-theme="light"] .cal-grid .day.sun .dn{color:#c62850}
[data-theme="light"] .cal-grid .wd.sat,[data-theme="light"] .cal-grid .day.sat .dn{color:#1d5bbf}
[data-theme="light"] .cal-list .sch .cb{background:#e7effa;color:#1d4f91}[data-theme="light"] .cal-list .can .cb{background:#ececf0}
[data-theme="light"] .lg.can::before,[data-theme="light"] .dots i.can{background:#9a9aa3}[data-theme="light"] .chip.can{background:#6b6b75}
.cal-list .can .cn{text-decoration:line-through;color:var(--ink3)}
.cal-list .cal-empty{display:block;color:var(--ink3);padding:16px 4px}
.cal-list .addc{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.cal-list .addc a{font-size:12px;font-weight:700;color:var(--pink);border:1px solid var(--pink-line);border-radius:999px;padding:2px 10px;text-decoration:none}
.cal-list .addc a:hover{border-color:var(--pink)}
@media (max-width:640px){
  .cal-grid .day{min-height:54px;align-items:center}
  .cal-grid .chip,.cal-grid .cal-more{display:none}
  .cal-grid .dots{display:flex;justify-content:center}
  .cal-list li{grid-template-columns:70px 1fr;}
  .cal-list .cb{grid-column:2;justify-self:start}
}
"""

CAL_JS = r"""<script>
(function(){
  var EV = window.CAL_EVENTS || [], T = window.CAL_T, MON = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  function t(k, o){ return T[k].replace(/\{(\w)\}/g, function(_, x){ return x === "M" ? MON[o.m - 1] : o[x]; }); }
  var grid = document.getElementById("cal-grid"), title = document.getElementById("cal-title"),
      list = document.getElementById("cal-list"), ltitle = document.getElementById("cal-listtitle"),
      allBtn = document.getElementById("cal-all");
  function pad(n){ return (n < 10 ? "0" : "") + n; }
  function ymd(d){ return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()); }
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]; }); }
  var now = new Date(Date.now() + (9 * 60 + new Date().getTimezoneOffset()) * 60000); // 日本時間
  var today = ymd(now), cur, sel = null;
  function kind(x){ return x.st === "cancelled" ? "can" : (x.vid ? "vid" : "sch"); }
  function md(s, e){
    var a = (+s.slice(5,7)) + "/" + (+s.slice(8,10));
    if (e && e !== s) a += T.dash + (e.slice(0,7) !== s.slice(0,7) ? (+e.slice(5,7)) + "/" : "") + (+e.slice(8,10));
    return a;
  }
  function link(x, inner){
    if (!x.u) return inner;
    return '<a href="' + esc(x.u) + '"' + (x.x ? ' target="_blank" rel="noopener"' : '') + '>' + inner + (x.x ? ' ↗' : '') + '</a>';
  }
  function onDay(d){ return EV.filter(function(x){ return x.s <= d && d <= x.e; }); }
  function render(){
    var y = cur.getFullYear(), m = cur.getMonth();
    title.textContent = t("ym", {y: y, m: m + 1});
    history.replaceState(null, "", "#" + y + "-" + pad(m + 1));
    var html = "", wd = T.wd;
    for (var i = 0; i < 7; i++) html += '<div class="wd' + (i === 0 ? " sun" : i === 6 ? " sat" : "") + '">' + wd[i] + '</div>';
    var first = new Date(y, m, 1), start = new Date(y, m, 1 - first.getDay());
    var weeks = Math.ceil((first.getDay() + new Date(y, m + 1, 0).getDate()) / 7);
    for (var k = 0; k < weeks * 7; k++){
      var d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + k), ds = ymd(d), out = d.getMonth() !== m;
      var evs = out ? [] : onDay(ds);
      var cls = "day" + (out ? " out" : "") + (ds === today ? " today" : "") + (ds === sel ? " sel" : "") +
                (d.getDay() === 0 ? " sun" : d.getDay() === 6 ? " sat" : "");
      var chips = evs.slice(0, 3).map(function(x){
        return x.u ? '<a class="chip ' + kind(x) + '" href="' + esc(x.u) + '"' + (x.x ? ' target="_blank" rel="noopener"' : '') + ' title="' + esc(x.n) + '">' + esc(x.n) + '</a>'
                   : '<span class="chip ' + kind(x) + '" title="' + esc(x.n) + '">' + esc(x.n) + '</span>';
      }).join("");
      if (evs.length > 3) chips += '<span class="cal-more">' + t("more", {n: evs.length - 3}) + '</span>';
      var dots = '<span class="dots">' + evs.slice(0, 4).map(function(x){ return '<i class="' + kind(x) + '"></i>'; }).join("") + '</span>';
      html += '<div class="' + cls + '" data-d="' + ds + '"' + (out ? "" : ' role="gridcell" tabindex="0" aria-label="' + t("cell", {m: d.getMonth() + 1, d: d.getDate(), n: evs.length}) + '"') + '><span class="dn">' + d.getDate() + '</span>' + chips + dots + '</div>';
    }
    grid.innerHTML = html;
    renderList();
  }
  function renderList(){
    var y = cur.getFullYear(), m = cur.getMonth(), from = y + "-" + pad(m + 1) + "-01", to = y + "-" + pad(m + 1) + "-31";
    var evs = sel ? onDay(sel) : EV.filter(function(x){ return x.s <= to && x.e >= from; });
    ltitle.textContent = sel ? t("day", {m: +sel.slice(5,7), d: +sel.slice(8,10)}) : t("month", {n: evs.length});
    allBtn.hidden = !sel;
    list.innerHTML = evs.length ? evs.map(function(x){
      var k = kind(x), badge = T[k];
      return '<li class="' + k + '"><span class="cd">' + md(x.s, x.e) + (x.d ? T.derived : "") + '</span><span class="cn">' +
             link(x, esc(x.n)) + '<small>' + esc(x.v) + '</small>' +
             (x.gc ? '<span class="addc"><a href="' + esc(x.gc) + '" target="_blank" rel="noopener">' + T.gc + '</a><a href="' + esc(x.ic) + '" download>' + T.ic + '</a></span>' : '') +
             '</span><span class="cb">' + badge + '</span></li>';
    }).join("") : '<li class="cal-empty">' + (sel ? T.noday : T.nomonth) + '</li>';
  }
  grid.addEventListener("click", function(ev){
    if (ev.target.closest("a")) return;
    var c = ev.target.closest(".day"); if (!c || c.classList.contains("out")) return;
    sel = (sel === c.dataset.d) ? null : c.dataset.d; render();
  });
  grid.addEventListener("keydown", function(ev){
    if (ev.key === "Enter" || ev.key === " "){ var c = ev.target.closest(".day"); if (c){ ev.preventDefault(); c.click(); } }
  });
  function move(n){ cur = new Date(cur.getFullYear(), cur.getMonth() + n, 1); sel = null; render(); }
  document.getElementById("cal-prev").onclick = function(){ move(-1); };
  document.getElementById("cal-next").onclick = function(){ move(1); };
  document.getElementById("cal-today").onclick = function(){ cur = new Date(now.getFullYear(), now.getMonth(), 1); sel = null; render(); };
  allBtn.onclick = function(){ sel = null; render(); };
  var h = /^#(\d{4})-(\d{2})$/.exec(location.hash);
  cur = h ? new Date(+h[1], +h[2] - 1, 1) : new Date(now.getFullYear(), now.getMonth(), 1);
  render();
})();
</script>"""
