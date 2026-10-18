(function(){
  function data(id){ try{ return JSON.parse(document.getElementById(id).textContent); }catch(x){ return null; } }
  var EV = data("cal-ev") || [], T = data("cal-t"), MON = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
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
