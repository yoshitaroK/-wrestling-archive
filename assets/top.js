// トップページ(index.html と、en_index.py が作る英語版 en/index.html)の JavaScript。手で書いたファイル(ビルドでは作らない)。
// 中身を変えたら、index.html の <script src="/assets/top.js?v=…"> の番号を1つ上げる(ブラウザに古いファイルを使わせないため)。
// 英語版では、画面で使う英語名を <script type="application/json" id="en-names"> から読む(Issue #18。CSP で止まらないように)。
window.thumbFail = function(img){
  var order = ['maxresdefault','hqdefault','mqdefault','sddefault','default'], m = /\/vi\/([^/]+)\/([a-z]+)\.jpg/.exec(img.src);
  var tried = (img.dataset.tried||'').split(',');
  if(m){ tried.push(m[2]); var next = order.filter(function(o){ return tried.indexOf(o)<0; })[0];
    if(next){ img.dataset.tried = tried.join(','); img.src = 'https://i.ytimg.com/vi/'+m[1]+'/'+next+'.jpg'; return; } }
  img.remove();
};
(async function(){
'use strict';
/* ---------- 言語(英語版は /en/ に、この index.html をもとに自動で作られる) ---------- */
var LANG = document.documentElement.lang === 'en' ? 'en' : 'ja';
function L(j, en){ return LANG === 'en' ? en : j; }
var EN = (function(){ try{ return JSON.parse(document.getElementById("en-names").textContent); }catch(x){ return {}; } })();
function N(x){ return LANG === 'en' && x && EN[x] ? EN[x] : x; }
function U(path){ return LANG === 'en' ? '/en' + path : path; }
var MON = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
function plural(n, w, ws){ return n + ' ' + (n === 1 ? w : (ws || w + 's')); }
function nv(n){ return L(n + '本', plural(n, 'video')); }
function yl(y){ return L(y + '年', String(y)); }
function fyEn(s){ var m = /^(令和|平成)(元|\d+)年度$/.exec(s||''); if(!m) return s; var n = m[2]==='元' ? 1 : +m[2]; return 'FY' + ((m[1]==='令和' ? 2018 : 1988) + n); }
/* ---------- メニューを特集の写真の上に重ねる(スクロールすると黒い帯にする) ---------- */
(function(){
  var root = document.documentElement, top = document.querySelector('.top'), off = document.querySelector('.official'); if(!top) return;
  function size(){ root.style.setProperty('--hdr-h', top.offsetHeight+'px'); }
  function onScroll(){ top.classList.toggle('see-through', window.scrollY <= (off ? off.offsetHeight : 0) + 8); }
  root.classList.add('overlay'); size(); onScroll();
  window.addEventListener('resize', size); window.addEventListener('scroll', onScroll, {passive:true});
})();
// 特集の写真(assets/hero.json)と、技術動画・写真の列(assets/home.json)。data.json と並べて読み込む
function getJSON(u){ return fetch(u,{cache:'no-cache'}).then(function(r){ return r.ok ? r.json() : null; }).catch(function(){ return null; }); }
var heroP = getJSON('/assets/hero.json'), homeP = getJSON('/assets/home.json');
var DATA = window.__DATA__;
if(!DATA){
  try{ var res = await fetch('/data.json',{cache:'no-cache'}); DATA = await res.json(); }
  catch(e){ document.getElementById('main').innerHTML = L('<p class="empty"><strong>データを読み込めませんでした。</strong>ページを再読み込みしてください。解決しない場合は data.json がリポジトリにあるか確認してください。</p>', '<p class="empty"><strong>Could not load the data.</strong> Please reload the page.</p>'); return; }
}

/* ---------- 大会・開催回ページのURL ---------- */
var PAGES = {};
try{ var pr = await fetch('/page_slugs.json',{cache:'no-cache'}); if(pr.ok) PAGES = (await pr.json()).events || {}; }catch(e){}
// 英語版:動画タイトルなどの機械翻訳(translate_en.py が作る)
var TR = {};
if(LANG==='en'){ try{ var trr = await fetch('/translations_en.json',{cache:'no-cache'}); if(trr.ok) TR = (await trr.json()).texts || {}; }catch(e){} }
function trLine(ja){ var t = LANG==='en' && ja ? TR[String(ja).trim()] : ''; return t ? '<div class="vtr" lang="en">'+esc(t)+' <span class="mt">auto-translated</span></div>' : ''; }
function eventPage(eid){ return PAGES[eid] ? U('/events/'+PAGES[eid]+'/') : ''; }
function seriesPage(sid){ var x = DATA.series.filter(function(s){return s.id===sid;})[0]; return x && x.n>0 ? U('/events/'+sid+'/') : ''; }

/* ---------- 準備 ---------- */
var TODAY = new Date(); var TODAY_ISO = TODAY.toISOString().slice(0,10);
var S = {}, E = {}, V = DATA.videos;
DATA.series.forEach(function(s){ S[s.id]=s; s.events=[]; s.videoIds=[]; });
DATA.events.forEach(function(e){ E[e.id]=e; if(S[e.series]) S[e.series].events.push(e); });
Object.keys(S).forEach(function(k){ S[k].events.sort(function(a,b){ return (a.start||a.year+'-99') < (b.start||b.year+'-99') ? -1 : 1; }); });
var byEvent = {}, bySeriesLoose = {}, candByEvent = {}, loose = [];
V.forEach(function(v){
  if(v.e){ (byEvent[v.e]=byEvent[v.e]||[]).push(v); }
  else if(v.s){ (bySeriesLoose[v.s]=bySeriesLoose[v.s]||[]).push(v); }
  else { loose.push(v); }
  if(!v.e && v.c){ v.c.forEach(function(c){ (candByEvent[c]=candByEvent[c]||[]).push(v); }); }
  if(v.s && S[v.s]) S[v.s].videoIds.push(v.id);
});

var HERO = ((await heroP)||{})[LANG] || [], HOME = ((await homeP)||{})[LANG] || {};

function skey(s){
  s = String(s||'').replace(/\u309b/g,'\u3099').replace(/\u309c/g,'\u309a').normalize('NFKC').toLowerCase();
  s = s.replace(/[\u3041-\u3096]/g,function(c){return String.fromCharCode(c.charCodeAt(0)+0x60);});
  s = s.replace(/[髙﨑德]/g,function(c){return {'髙':'高','﨑':'崎','德':'徳'}[c];}); // 名前の異体字は普通の字として探す
  s = s.replace(/[\s・･\/／「」『』()（）\[\]【】\u200b-\u200f\u2060\ufeff]/g,'').replace(/レスリング/g,'');
  return s;
}
DATA.series.forEach(function(s){
  // 英語名でも探せるように、英語名を別名の最後に足す
  s.aliases = (s.aliases||[]).slice(); if(EN[s.name] && s.aliases.indexOf(EN[s.name])<0) s.aliases.push(EN[s.name]);
  s.keys = [s.name].concat(s.aliases).map(skey);
  s.evKeys = s.events.map(function(e){ return skey((e.name||'')+' '+(e.official_name||'')); });
  s.years = {}; s.events.forEach(function(e){ s.years[e.year]=true; });
  s.latest = s.events.reduce(function(m,e){ return (e.n>0 && (e.start||'')>m) ? e.start : m; }, '');
});
V.forEach(function(v){ v.key = skey(v.t); });

var CATS = ['一般','大学','高校','中学','少年少女','年代別','女子','社会人','マスターズ','ビーチ','未確認'];
var STYLES = ['フリー','グレコ','女子','未確認'];
var SCOPES = ['国内','海外','未確認'];
var KIND = L({match:'試合', interview:'インタビュー', announcement:'告知・抽選会など', highlight:'ダイジェストなど', other:'その他'},
             {match:'Match', interview:'Interview', announcement:'Announcement / draw', highlight:'Highlights', other:'Other'});
// 絞り込み用の動画の種類(1本の動画は必ず1つだけに入るので、内訳の合計は総数と一致する)
var KINDS = L([['match','試合配信'],['interview','インタビュー'],['announcement','告知・抽選会'],['other','その他・未分類']],
              [['match','Match streams'],['interview','Interviews'],['announcement','Announcements & draws'],['other','Other / unclassified']]);
function kindOf(v){ return v.k==='match'||v.k==='interview'||v.k==='announcement' ? v.k : 'other'; }
function kindLabel(k){ for(var i=0;i<KINDS.length;i++) if(KINDS[i][0]===k) return KINDS[i][1]; return ''; }
function kindCounts(vids){ var c={}, seen={}; vids.forEach(function(v){ if(seen[v.id]) return; seen[v.id]=1; var k=kindOf(v); c[k]=(c[k]||0)+1; }); return c; }
function kindText(vids){
  var c = kindCounts(vids), parts = [];
  parts.push(L('試合配信'+(c.match||0)+'本', 'Match streams: '+(c.match||0)));
  KINDS.slice(1).forEach(function(k){ if(c[k[0]]) parts.push(L(k[1]+c[k[0]]+'本', k[1]+': '+c[k[0]])); });
  return parts.join(L('・', ', '));
}
var LINK = L({manual:'手動で確認済み', matched:'タイトルで照合', livedate:'配信日で照合', derived:'開催情報を確認中', candidate:'確認待ち', series_only:'開催回を確認中', unmatched:'対応未確認'},
             {manual:'Manually verified', matched:'Matched by title', livedate:'Matched by stream date', derived:'Event details TBC', candidate:'Pending review', series_only:'Edition unconfirmed', unmatched:'Tournament unconfirmed'});
var STATUS = L({held:'', cancelled:'中止', postponed:'延期', scheduled:'開催予定', unverified:'日付は動画の公開日から推定'},
               {held:'', cancelled:'Cancelled', postponed:'Postponed', scheduled:'Upcoming', unverified:'Date estimated from publish dates'});

function esc(s){ return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];}); }
function fmtDate(iso){ if(!iso) return L('日付未確認','Date TBC'); var p=iso.slice(0,10).split('-'); return L(+p[0]+'年'+(+p[1])+'月'+(+p[2])+'日', MON[+p[1]-1]+' '+(+p[2])+', '+p[0]); }
function fmtShort(iso){ if(!iso) return ''; var p=iso.slice(0,10).split('-'); return L((+p[1])+'/'+(+p[2]), MON[+p[1]-1]+' '+(+p[2])); }
function fmtRange(a,b){ if(!a) return L('日付未確認','Date TBC'); if(!b||a===b) return fmtDate(a); var pa=a.split('-'), pb=b.split('-');
  if(LANG==='en'){ if(pa[0]!==pb[0]) return fmtDate(a)+' – '+fmtDate(b);
    return MON[+pa[1]-1]+' '+(+pa[2])+(pa[1]===pb[1] ? '–'+(+pb[2]) : ' – '+MON[+pb[1]-1]+' '+(+pb[2]))+', '+pa[0]; }
  if(pa[0]===pb[0]) return fmtDate(a)+'〜'+(pa[1]===pb[1] ? (+pb[2])+'日' : (+pb[1])+'月'+(+pb[2])+'日'); return fmtDate(a)+'〜'+fmtDate(b); }
function jstDate(iso){ if(!iso) return ''; var d=new Date(iso); d=new Date(d.getTime()+9*3600e3); return d.toISOString().slice(0,10); }
function dur(iso){ var m=/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/.exec(iso||''); if(!m) return ''; var h=+(m[1]||0), mi=+(m[2]||0);
  if(LANG==='en') return h ? h+' h'+(mi? ' '+mi+' min':'') : (mi ? mi+' min' : (m[3]||0)+' sec');
  return h ? h+'時間'+(mi? mi+'分':'') : (mi ? mi+'分' : (m[3]||0)+'秒'); }
var PALETTE = [['#16161c','#34343f'],['#16161c','#6e1424'],['#1c1c24','#3d3d4a'],['#5a1220','#18181e'],
  ['#20202a','#45454f'],['#7a1628','#26262e'],['#121216','#2c2c36'],['#3c0e18','#9a1a30']];
function hashStr(s){ var h=0; s=String(s||''); for(var i=0;i<s.length;i++){ h=(h*31+s.charCodeAt(i))|0; } return Math.abs(h); }
function grad(name){ var p = PALETTE[hashStr(name)%PALETTE.length]; return 'linear-gradient('+(100+hashStr(name)%60)+'deg,'+p[0]+','+p[1]+')'; }
function thumb(id,label,rank){
  return '<div class="thumb" style="background:'+grad(label||id)+'">'+(rank?'<span class="rk">'+rank+'</span>':'')+
    (id?'<img src="https://i.ytimg.com/vi/'+esc(id)+'/mqdefault.jpg" alt="" loading="lazy" referrerpolicy="no-referrer" data-thumb>':'')+
    '<div class="ph">'+esc(label||'')+'</div></div>';
}
function seriesThumb(s){
  var evs = s.events.filter(function(e){return e.n>0;});
  for(var i=evs.length-1;i>=0;i--){ var vs = byEvent[evs[i].id]||[]; var m = vs.filter(function(v){return v.k==='match';})[0]||vs[0]; if(m) return m.id; }
  var l = bySeriesLoose[s.id]||[]; return l.length ? l[0].id : '';
}
function yt(id){ return 'https://www.youtube.com/watch?v='+encodeURIComponent(id); }

/* ---------- 状態(URLに保存) ---------- */
function blankState(){ return {q:'',y:'',c:'',sty:'',sc:'',k:'',all:false,s:'',e:'',sort:'date'}; }
var st = blankState();
function readHash(){
  var h = location.hash.replace(/^#/,'');
  var sq = !h && new URLSearchParams(location.search).get('q');
  if(sq){ h = 'q='+encodeURIComponent(sq); history.replaceState(null,'',location.pathname+'#'+h); }
  // 旧リンク(#series/名前・#occurrence/名前)を新しいページへ誘導
  var m = /^(series|occurrence)\/(.*)$/.exec(h);
  if(m){
    var name = decodeURIComponent(m[2]), map = (DATA.legacy||{})[m[1]]||{}, hit = map[name];
    var ns = blankState();
    if(hit){ var dest = (hit.e && eventPage(hit.e)) || (!hit.e && hit.s && seriesPage(hit.s)); if(dest){ location.replace(dest); return; }
      ns.s = hit.s||''; ns.e = hit.e||''; legacyNote = L('以前のリンク「'+name+'」を新しいページに移しました。', 'The old link "'+name+'" now points to the new page.'); }
    else { ns.q = name; legacyNote = L('以前のリンク「'+name+'」に対応するページが見つからないため、名前で検索しています。', 'No page matches the old link "'+name+'", so we are searching by name.'); }
    st = ns; history.replaceState(null,'',toHash()); return;
  }
  var p = new URLSearchParams(h);
  st = {q:p.get('q')||'', y:p.get('y')||'', c:p.get('c')||'', sty:p.get('st')||'', sc:p.get('sc')||'', k:p.get('k')||'',
        all:p.get('all')==='1', s:p.get('s')||'', e:p.get('e')||'', sort:p.get('o')||'date'};
}
function toHash(){
  var p = new URLSearchParams();
  if(st.q) p.set('q',st.q); if(st.y) p.set('y',st.y); if(st.c) p.set('c',st.c); if(st.sty) p.set('st',st.sty);
  if(st.sc) p.set('sc',st.sc); if(st.k) p.set('k',st.k); if(st.all) p.set('all','1'); if(st.s) p.set('s',st.s); if(st.e) p.set('e',st.e);
  if(st.sort && st.sort!=='date') p.set('o',st.sort);
  var s = p.toString(); return s ? '#'+s : location.pathname+location.search;
}
function commit(push){ var h = toHash(); if(push) history.pushState(null,'',h); else history.replaceState(null,'',h); render(); }
var legacyNote = '';

/* ---------- 絞り込み ---------- */
function eventVisible(e){ return st.all || e.n>0; }
// 検索語に含まれる西暦(例:「天皇杯 2022」の2022)。全角数字も NFKC で半角になる
function queryYear(){
  var toks = st.q.split(/\s+/).map(skey).filter(function(t){ return /^(19|20)\d{2}$/.test(t); });
  return toks.length ? toks[toks.length-1] : '';
}
// 開く開催回を決めるときに使う年。開催年の欄を優先し、なければ検索語の年
function effYear(){ return st.y || queryYear(); }
function yearConflict(){ var qy = queryYear(); return st.y && qy && qy!==st.y ? qy : ''; }
function kindOk(v){ return !st.k || kindOf(v)===st.k; }
function vidOk(v){ return styleOk(v) && kindOk(v); }
function eventHasKind(e){ if(!st.k) return true; return (byEvent[e.id]||[]).some(kindOk); }
function seriesMatch(s){
  var why = '';
  if(st.q){
    var toks = st.q.split(/\s+/).filter(Boolean);
    for(var i=0;i<toks.length;i++){
      var t = skey(toks[i]); if(!t) continue;
      var ok = false;
      if(/^\d{4}$/.test(t) && s.years[+t]) ok = true;
      for(var j=0;j<s.keys.length && !ok;j++){ if(s.keys[j].indexOf(t)>=0 || (t.length>=3 && t.indexOf(s.keys[j])>=0 && s.keys[j].length>=3)){ ok=true; if(j>0 && !why) why=L('「'+(s.aliases[j-1])+'」として一致', 'Matched as "'+(s.aliases[j-1])+'"'); } }
      for(var k=0;k<s.evKeys.length && !ok;k++){ if(s.evKeys[k].indexOf(t)>=0){ ok=true; if(!why) why=L('開催回の名称で一致', 'Matched an edition name'); } }
      if(!ok) return null;
    }
  }
  if(st.c && s.groups.indexOf(st.c)<0) return null;
  if(st.sc && s.scope!==st.sc) return null;
  if(st.sty && (s.styles||[]).indexOf(st.sty)<0) return null;
  var evs = s.events.filter(eventVisible);
  if(st.y) evs = evs.filter(function(e){ return String(e.year)===st.y; });
  if(st.k) evs = evs.filter(eventHasKind);
  if(!evs.length && !(st.all && !st.y && !st.k && s.events.length===0)){
    if(!(s.n>0 && !st.y && (bySeriesLoose[s.id]||[]).filter(kindOk).length)) return null;
  }
  var qy = queryYear();
  if(qy && !st.y && !why){ var hitE = s.events.filter(function(e){ return String(e.year)===qy && eventVisible(e); }); if(hitE.length) why = L(qy+'年の開催回あり', 'Has a '+qy+' edition'); }
  return {why:why};
}
function filteredSeries(){
  var out = [];
  DATA.series.forEach(function(s){ if(!st.all && !s.n) return; var m = seriesMatch(s); if(m) out.push({s:s, why:m.why}); });
  out.sort(function(a,b){
    if(st.sort==='count') return b.s.n - a.s.n;
    if(st.sort==='name') return N(a.s.name).localeCompare(N(b.s.name), LANG);
    return (b.s.latest||'') < (a.s.latest||'') ? -1 : 1;
  });
  return out;
}
function styleOk(v){ if(!st.sty) return true; if(st.sty==='未確認') return !(v.st&&v.st.length); return (v.st||[]).indexOf(st.sty)>=0; }

/* ---------- 描画 ---------- */
function fillSelect(id, values, current, fmt){
  fmt = fmt || N;
  var el = document.getElementById(id), first = el.options[0].outerHTML;
  el.innerHTML = first + values.map(function(v){ return '<option value="'+esc(v)+'"'+(String(v)===current?' selected':'')+'>'+esc(fmt?fmt(v):v)+'</option>'; }).join('');
}
function renderControls(){
  var yrs = {}; DATA.events.forEach(function(e){ if(st.all || e.n>0) yrs[e.year]=1; });
  fillSelect('f-year', Object.keys(yrs).sort().reverse(), st.y, yl);
  fillSelect('f-cat', CATS, st.c); fillSelect('f-style', STYLES, st.sty); fillSelect('f-scope', SCOPES, st.sc);
  fillSelect('f-kind', KINDS.map(function(k){return k[0];}), st.k, kindLabel);
  document.getElementById('f-all').checked = st.all;
  var q = document.getElementById('q'); if(document.activeElement!==q) q.value = st.q;
}
// スマホの「絞り込み」ボタン:選んでいる条件の数を出し、条件があるときは開いておく
function updateFilterToggle(){
  var b = document.getElementById('ftoggle'), f = document.getElementById('filters'); if(!b || !f) return;
  var n = [st.y, st.c, st.sty, st.sc, st.k, st.all].filter(Boolean).length;
  b.textContent = L('絞り込み','Filters') + (n ? L('('+n+')',' ('+n+')') : '');
  if(n && !f.classList.contains('open')){ f.classList.add('open'); b.setAttribute('aria-expanded','true'); }
}
document.addEventListener('click', function(ev){
  var b = ev.target.closest && ev.target.closest('#ftoggle'); if(!b) return;
  var f = document.getElementById('filters'), open = f.classList.toggle('open'); b.setAttribute('aria-expanded', open ? 'true' : 'false');
});
function renderStatus(list, nVid, nPl){
  updateFilterToggle();
  var chips = [];
  if(st.q) chips.push(['q',L('検索:','Search: ')+st.q]); if(st.y) chips.push(['y',yl(st.y)]); if(st.c) chips.push(['c',L('区分:','Category: ')+N(st.c)]);
  if(st.sty) chips.push(['sty',L('スタイル:','Style: ')+N(st.sty)]); if(st.sc) chips.push(['sc',N(st.sc)]); if(st.k) chips.push(['k',L('種類:','Type: ')+kindLabel(st.k)]);
  if(st.all) chips.push(['all',L('動画のない大会も表示','Including tournaments without videos')]);
  var html = '<span class="count">'+L((nPl?'選手'+nPl+'人・':'')+'大会'+list.length+'件'+(nVid!=null?'・動画'+nVid+'本':''), (nPl?plural(nPl,'player')+', ':'')+plural(list.length,'tournament')+(nVid!=null?', '+plural(nVid,'video'):''))+'</span>';
  html += chips.map(function(c){ return '<span class="chip">'+esc(c[1])+'<button type="button" data-drop="'+c[0]+'" aria-label="'+esc(L(c[1]+'の条件を外す','Remove filter: '+c[1]))+'">×</button></span>'; }).join('');
  if(chips.length) html += '<button type="button" class="clear" id="clear">'+L('条件をすべてクリア','Clear all filters')+'</button>';
  if(legacyNote) html += '<span class="chip">'+esc(legacyNote)+'</span>';
  var cf = yearConflict();
  if(cf) html += '<div class="conflict" role="alert">'+L('検索語の「'+esc(cf)+'」と開催年「'+esc(st.y)+'年」が食い違っています。', 'The year in your search ("'+esc(cf)+'") differs from the selected year ('+esc(st.y)+').')+
    '<button type="button" data-setyear="'+esc(cf)+'">'+L(esc(cf)+'年にする','Use '+esc(cf))+'</button><button type="button" data-drop="y">'+L('開催年の指定を外す','Clear the year filter')+'</button></div>';
  document.getElementById('status').innerHTML = html;
}
function tileEvent(e){
  var vs = (byEvent[e.id]||[]).slice().sort(function(a,b){ return a.k==='match' ? -1 : 1; });
  var first = vs[0]; var s = S[e.series];
  return '<a class="tile" href="'+esc(eventPage(e.id)||linkTo(e.series,e.id))+'">'+ thumb(first?first.id:'', s?s.name:'') +
    '<div class="tt">'+esc(N(s?s.name:e.name))+'</div><div class="tm"><span class="num">'+e.n+'</span>'+L('本 '+e.year+'年 ',' videos · '+e.year+' · ')+fmtShort(e.start)+(e.end&&e.end!==e.start?L('〜','–')+fmtShort(e.end):'')+'</div></a>';
}
function tileSeries(s){
  var lastE = s.events.filter(function(e){return e.n>0;}).pop(), lv = lastE ? (byEvent[lastE.id]||[]) : [];
  var fv = lv.filter(function(v){return v.k==='match';})[0] || lv[0];
  var yrs = s.events.filter(function(e){return e.n>0;}).map(function(e){return e.year;});
  return '<a class="tile" href="'+esc(seriesPage(s.id)||linkTo(s.id,''))+'">'+thumb(fv?fv.id:'', N(s.name))+'<div class="tt">'+esc(N(s.name))+'</div><div class="tm"><span class="num">'+s.n+'</span>'+L('本 ',' videos · ')+
    (yrs.length? Math.min.apply(null,yrs)+(Math.min.apply(null,yrs)!==Math.max.apply(null,yrs)?L('〜','–')+Math.max.apply(null,yrs):'')+L('年',''):'')+'</div></a>';
}
// 横に流れる列。tiles は1枚ずつの HTML、more は見出しの右の「すべて見る」
var shelfN = 0;
function shelf(title, sub, tiles, more){
  if(!tiles.length) return '';
  var id = 'row'+(++shelfN);
  return '<section class="shelf" aria-labelledby="'+id+'-h"><div class="shelf-h"><h2 id="'+id+'-h">'+esc(title)+(sub?'<span class="sub">'+esc(sub)+'</span>':'')+'</h2>'+(more||'')+'</div>'+
    '<div class="rowwrap"><button type="button" class="rbtn prev" data-row="'+id+'" data-dir="-1" tabindex="-1" aria-hidden="true">‹</button>'+
    '<div class="row" id="'+id+'">'+tiles.join('')+'</div>'+
    '<button type="button" class="rbtn next" data-row="'+id+'" data-dir="1" tabindex="-1" aria-hidden="true">›</button></div></section>';
}
// 列の端まで来たら矢印を消す。矢印の高さはサムネイルに合わせる
function updRow(r){
  var w = r.parentNode, p = w.querySelector('.prev'), n = w.querySelector('.next'), t = r.querySelector('.thumb');
  if(t) w.style.setProperty('--rb-h', t.offsetHeight+'px');
  p.disabled = r.scrollLeft <= 4; n.disabled = r.scrollLeft + r.clientWidth >= r.scrollWidth - 4;
}
var SHELF_CATS = L([['大学','大学の大会'],['高校','高校の大会'],['社会人','社会人の大会'],['少年少女','少年少女の大会']],
                   [['大学','University'],['高校','High school'],['社会人','Working adults'],['少年少女','Kids']]);

/* ---------- 特集(トップの大きな写真。‹ › で切り替える) ---------- */
// 大きな枠に出さない大会(主催者の希望)。下の列には出る
var NO_HERO = {'x-fujinami-cup':1};
// 特集の背景に使う、大会ごとに作った絵(assets/feature/)。写真も動画もまだない大会に使う。pos はスマホで見せる横の位置
var FEATURE_ART = {'wre-2026-kokutai-1012': {src:'/assets/feature/kokutai-2026.jpg', pos:'22% 50%'}};
var FEAT = [], featI = 0;
function buildFeature(){
  var past = DATA.events.filter(function(e){ return e.n>0 && e.start && e.start<=TODAY_ISO && e.status!=='cancelled' && !NO_HERO[e.series]; })
    .sort(function(a,b){ return a.start<b.start?1:-1; });
  var future = DATA.events.filter(function(e){ return e.n>0 && e.start && e.start>TODAY_ISO && !NO_HERO[e.series]; })
    .sort(function(a,b){ return a.start<b.start?-1:1; });
  var used = {};
  // 大会の写真(hero.json に載っている写真だけ)があればそれを、なければ試合動画のサムネイルを背景にする
  function photoFor(e){
    var keys = [PAGES[e.id] ? U('/photos/'+PAGES[e.id]+'/') : '', U('/photos/'+e.series+'/')];
    for(var i=0;i<HERO.length;i++) if(!used[i] && keys.indexOf(HERO[i].href)>=0){ used[i]=1; return HERO[i]; }
    return null;
  }
  function evSlide(e, kind){
    var s = S[e.series], vs = byEvent[e.id]||[], v = vs.filter(function(x){return x.k==='match';})[0] || vs[0];
    return {kind:kind, href:eventPage(e.id)||linkTo(e.series,e.id), name:L(e.official_name||e.name, N(s?s.name:e.name)+' '+e.year),
      meta:'<span><span class="num">'+e.n+'</span>'+L('本',' videos')+'</span><span>'+esc(fmtRange(e.start,e.end))+'</span>'+(e.venue?'<span>'+esc(N(e.venue))+'</span>':''),
      photo:photoFor(e), vid:v?v.id:''};
  }
  // 開催中(終わってから7日まで)で、結果・速報のリンク(overrides.json の event_links)がある大会を一番前に出す
  var today = jstDate(new Date().toISOString()), weekAgo = jstDate(new Date(Date.now()-7*864e5).toISOString());
  var live = DATA.events.filter(function(e){ return e.links && e.links.length && PAGES[e.id] && e.start && e.start<=today && (e.end||e.start)>=weekAgo && e.status!=='cancelled' && !NO_HERO[e.series]; })
    .sort(function(a,b){ return a.start<b.start?1:-1; });
  var out = live.map(function(e){
    var x = evSlide(e, (e.end||e.start)>=today ? 'live' : 'result');
    // 配信動画がまだない大会は、同じ大会の前の年の試合動画を背景にする
    if(!x.photo && FEATURE_ART[e.id]) x.art = FEATURE_ART[e.id];
    if(!x.photo && !x.art && !x.vid){ var s = S[e.series], pv = s ? s.events.filter(function(o){ return o.n>0; }).pop() : null, vs = pv ? (byEvent[pv.id]||[]) : [];
      var m = vs.filter(function(v){ return v.k==='match'; })[0] || vs[0]; if(m) x.vid = m.id; }
    if(!e.n) x.meta = '<span>'+esc(fmtRange(e.start,e.end))+'</span>'+(e.venue?'<span>'+esc(N(e.venue))+'</span>':'');
    x.ext = e.links[0].url; x.extLabel = e.links[0].label;
    return x;
  });
  out = out.concat(past.slice(0,2).map(function(e){ return evSlide(e,'recent'); }));
  if(future[0]) out.push(evSlide(future[0],'upcoming'));
  HERO.forEach(function(p,i){ if(!used[i] && out.length<5){ used[i]=1; out.push({kind:'photo', href:p.href, name:p.label, meta:'', photo:p, vid:''}); } });
  return out;
}
var FEAT_TXT = L({live:['開催中','結果・速報を見る'], result:['結果が出ています','結果を見る'], recent:['最近開催された大会','配信一覧を見る'], upcoming:['これから開催される大会','配信予定を見る'], photo:['新しく載った写真','写真を見る']},
                 {live:['Happening now','See the live results'], result:['Results are in','See the results'], recent:['Latest tournament','Watch the streams'], upcoming:['Upcoming tournament','See the stream schedule'], photo:['New photos','See the photos']});
function showFeature(i){
  if(!FEAT.length) return;
  featI = (i + FEAT.length) % FEAT.length;
  var f = FEAT[featI], box = document.getElementById('feat'), img = document.getElementById('jhero-img'), cr = document.getElementById('jhero-credit');
  var t = FEAT_TXT[f.kind];
  box.innerHTML = '<div class="feat-main" aria-live="polite"><div class="badge-l'+(f.kind==='live'?' live':'')+'">'+t[0]+'</div><a class="fn" href="'+esc(f.href)+'">'+esc(f.name)+'</a>'+
    (f.meta?'<div class="fm">'+f.meta+'</div>':'')+
    (f.ext ? '<div class="ctas"><a class="cta" href="'+esc(f.ext)+'" target="_blank" rel="noopener">'+t[1]+' ↗</a><a class="cta2" href="'+esc(f.href)+'">'+L('大会ページへ','Tournament page')+'</a></div>'
           : '<a class="cta" href="'+esc(f.href)+'" tabindex="-1">'+t[1]+'</a>')+'</div>'+
    (FEAT.length>1 ? '<div class="fnav"><button type="button" class="fb" data-feat="-1" aria-label="'+L('前の特集','Previous')+'">‹</button><div class="fdots">'+
      FEAT.map(function(x,k){ return '<button type="button" data-featto="'+k+'" aria-label="'+L((k+1)+'件目('+FEAT.length+'件中)','Item '+(k+1)+' of '+FEAT.length)+'"'+(k===featI?' aria-current="true"':'')+'></button>'; }).join('')+
      '</div><button type="button" class="fb" data-feat="1" aria-label="'+L('次の特集','Next')+'">›</button></div>' : '');
  box.hidden = false;
  img.classList.remove('on'); img.onload = function(){ img.classList.add('on'); }; img.onerror = function(){ if(this.src.indexOf('ytimg')>=0) thumbFail(this); };
  img.style.objectPosition = f.art && f.art.pos || '';
  if(f.art){ img.removeAttribute('srcset'); img.src=f.art.src; }
  else if(f.photo){ img.sizes='100vw'; img.srcset=f.photo.srcset; img.src=f.photo.src; if(f.photo.w&&f.photo.h){ img.width=f.photo.w; img.height=f.photo.h; } }
  else if(f.vid){ img.removeAttribute('srcset'); img.src='https://i.ytimg.com/vi/'+encodeURIComponent(f.vid)+'/maxresdefault.jpg'; img.referrerPolicy='no-referrer'; }
  if(f.photo && f.photo.credit){ cr.href=f.photo.href; cr.textContent=f.photo.credit; cr.title=f.photo.label;
    if(f.photo.label){ var sp=document.createElement('span'); sp.className='jl'; sp.textContent=L(f.photo.label+'の写真','Photo from '+f.photo.label)+' · '; cr.insertBefore(sp, cr.firstChild); }
    cr.hidden=false; } else cr.hidden=true;
}
function linkTo(sid,eid){ var p = new URLSearchParams(); p.set('s',sid); if(eid) p.set('e',eid); return '#'+p.toString(); }
function renderShelves(){
  shelfN = 0;
  var past = DATA.events.filter(function(e){ return e.n>0 && e.start && e.start<=TODAY_ISO && e.status!=='cancelled'; })
    .sort(function(a,b){ return a.start<b.start?1:-1; }).slice(0,12);
  var future = DATA.events.filter(function(e){ return e.n>0 && e.start && e.start>TODAY_ISO; })
    .sort(function(a,b){ return a.start<b.start?-1:1; });
  var recent = V.filter(function(v){ return v.vs!=='unavailable'; }).slice().sort(function(a,b){ return a.p<b.p?1:-1; }).slice(0,12);
  var rich = DATA.series.filter(function(s){ return s.master && s.n>0; }).sort(function(a,b){ return b.n-a.n; }).slice(0,12);
  var h = '';
  if(future.length) h += shelf(L('これから開催される大会','Upcoming tournaments'), L('配信枠が公開されています','Stream pages are already published'), future.map(tileEvent), '<a class="all" href="'+U('/events/calendar/')+'">'+L('カレンダーを見る ›','See the calendar ›')+'</a>');
  h += shelf(L('最近開催された大会','Recent tournaments'), '', past.map(tileEvent), '<a class="all" href="'+U('/events/')+'">'+L('すべて見る ›','See all ›')+'</a>');
  h += shelf(L('最近追加した動画','Recently added videos'), L('YouTubeへの公開が新しい順','Newest on YouTube first'), recent.map(function(v){
    var s = v.s && S[v.s];
    return '<a class="tile" href="'+esc(yt(v.id))+'" target="_blank" rel="noopener">'+thumb(v.id, s?N(s.name):'')+'<div class="tt"'+L('',' lang="ja"')+'>'+esc(v.t)+'</div><div class="tm">'+L(esc(fmtDate(jstDate(v.p)))+'に公開','Published '+esc(fmtDate(jstDate(v.p))))+'</div></a>';
  }));
  // 区分ごとの列(開催日の新しい大会から)
  SHELF_CATS.forEach(function(c){
    var list = DATA.series.filter(function(s){ return s.n>0 && (s.groups||[]).indexOf(c[0])>=0; }).sort(function(a,b){ return (b.latest||'') < (a.latest||'') ? -1 : 1; }).slice(0,12);
    if(list.length) h += shelf(c[1], '', list.map(tileSeries), '<button type="button" class="all" data-cat="'+esc(c[0])+'">'+L('すべて見る ›','See all ›')+'</button>');
  });
  var tech = HOME.tech || [];
  if(tech.length) h += shelf(L('技術動画','Technique videos'), L('レスリングクラブが公開している技術・トレーニングの動画','Technique and training videos from wrestling clubs'), tech.map(function(v){
    return '<a class="tile" href="'+esc(yt(v.id))+'" target="_blank" rel="noopener">'+thumb(v.id, v.cat)+'<div class="tt"'+L('',' lang="ja"')+'>'+esc(v.t)+'</div><div class="tm">'+esc(v.cat)+'</div></a>';
  }), '<a class="all" href="'+U('/technique/')+'">'+L('すべて見る ›','See all ›')+'</a>');
  var photos = HOME.photos || [];
  if(photos.length) h += shelf(L('写真','Photos'), L('大会で撮影された写真','Photos taken at tournaments'), photos.map(function(p){
    return '<a class="tile" href="'+esc(p.href)+'"><div class="thumb photo"><img src="'+esc(p.src)+'" alt="" loading="lazy" decoding="async"></div><div class="tt">'+esc(p.label)+'</div><div class="tm"><span class="num">'+p.n+'</span>'+L('枚',' photos')+'</div></a>';
  }), '<a class="all" href="'+U('/photos/')+'">'+L('すべて見る ›','See all ›')+'</a>');
  h += shelf(L('動画が充実している大会','Tournaments with the most videos'), L('収録本数の多い順','Most videos first'), rich.map(tileSeries));
  return h;
}
function videoRow(v, showBasis){
  var meta = [];
  if(v.ch) meta.push('<span class="chlabel">'+esc(N(v.ch))+'</span>');
  if(v.dh) meta.push('<span class="d tabnum">'+esc(fmtDate(v.dh))+'</span>');
  if(v.m) meta.push('<span>'+esc(L(v.m+'マット','Mat '+v.m))+'</span>');
  if(v.st && v.st.length) meta.push('<span>'+esc(L(v.st.join('・'), v.st.map(N).join(' / ')))+'</span>');
  if(v.k && v.k!=='match') meta.push('<span>'+esc(KIND[v.k])+'</span>');
  if(v.du) meta.push('<span class="tabnum">'+esc(dur(v.du))+'</span>');
  meta.push('<span>'+L('公開 ','Published ')+esc(fmtDate(jstDate(v.p)))+'</span>');
  if(v.vs==='upcoming') meta.push('<span class="lk">'+L('配信予定','Scheduled stream')+'</span>');
  if(v.vs==='unavailable') meta.push('<span class="lk unmatched">'+L('現在YouTubeで取得できません','Currently unavailable on YouTube')+'</span>');
  meta.push('<span class="lk '+esc(v.l)+'" title="'+esc(v.b||'')+'">'+esc(LINK[v.l]||v.l)+'</span>');
  return '<li class="v"><a href="'+esc(yt(v.id))+'" target="_blank" rel="noopener" tabindex="-1" aria-hidden="true">'+thumb(v.id,'')+'</a>'+
    '<div><div class="vt"><a href="'+esc(yt(v.id))+'" target="_blank" rel="noopener"'+L('',' lang="ja"')+'>'+esc(v.t)+'</a></div>'+trLine(v.t)+
    '<div class="vm">'+meta.join('')+'</div>'+(showBasis&&v.b?'<div class="basis">'+L('根拠:','Basis: ')+(TR[v.b]&&LANG==='en' ? esc(TR[v.b])+' <span class="mt">auto-translated</span>' : '<span'+L('',' lang="ja"')+'>'+esc(v.b)+'</span>')+'</div>':'')+'</div></li>';
}
function vgroup(title, sub, vids, showBasis, id, lv){
  if(!vids.length) return '';
  var LIMIT = 40, more = vids.length>LIMIT;
  return '<div class="vgroup"'+(id?' id="'+id+'"':'')+'><h'+(lv||4)+'>'+esc(title)+(sub?'<small>'+esc(sub)+'</small>':'')+'</h'+(lv||4)+'><ul class="vlist">'+
    vids.slice(0,LIMIT).map(function(v){return videoRow(v,showBasis);}).join('')+'</ul>'+
    (more?'<button type="button" class="more" data-more="'+esc(id||'')+'">'+L('残り'+(vids.length-LIMIT)+'本を表示','Show '+(vids.length-LIMIT)+' more')+'</button>':'')+'</div>';
}
var moreCache = {};
function eventPanel(e){
  var s = S[e.series];
  var title = L(e.official_name || e.name, N(s ? s.name : e.name) + ' ' + e.year);
  var h = '<div class="event" id="ev-'+esc(e.id)+'"><h3>'+esc(title)+(e.status!=='held'&&STATUS[e.status]?'<span class="badge '+esc(e.status)+'">'+esc(STATUS[e.status])+'</span>':'')+'</h3>';
  if(eventPage(e.id)) h += '<p class="pagelink"><a href="'+esc(eventPage(e.id))+'">'+L('この開催回のページを開く(共有やブックマークに便利)','Open the page for this edition (handy for sharing and bookmarks)')+'</a></p>';
  h += '<dl class="facts">';
  h += '<dt>'+L('開催年','Year')+'</dt><dd class="tabnum">'+yl(e.year)+(e.fy_label?L('(',' (')+esc(L(e.fy_label, fyEn(e.fy_label)))+')':'')+'</dd>';
  if(e.sessions && e.sessions.length){
    var ss = e.sessions.slice().sort(function(a,b){return a.start_date<b.start_date?-1:1;});
    h += '<dt>'+L('日程','Schedule')+'</dt><dd><ul class="sessions">'+ss.map(function(x){ return '<li>'+esc(fmtRange(x.start_date,x.end_date))+' '+esc(N(x.label||''))+(x.venue?L('(',' (')+esc(N(x.venue))+')':'')+'</li>'; }).join('')+'</ul></dd>';
  } else {
    h += '<dt>'+(e.derived?L('配信日','Stream dates'):L('開催日','Dates'))+'</dt><dd>'+esc(fmtRange(e.start,e.end))+(e.status==='scheduled'?L('(予定)',' (scheduled)'):'')+'</dd>';
  }
  if(e.venue && !(e.sessions&&e.sessions.length)) h += '<dt>'+L('会場','Venue')+'</dt><dd>'+esc(N(e.venue))+'</dd>';
  h += '<dt>'+L('収録','Videos')+'</dt><dd>'+esc(kindText(byEvent[e.id]||[]))+'</dd>';
  if(e.group){ var sib = DATA.events.filter(function(x){return x.group===e.group && x.id!==e.id;});
    if(sib.length) h += '<dt>'+L('同時開催','Held together with')+'</dt><dd>'+sib.map(function(x){ return '<a href="'+esc(linkTo(x.series,x.id))+'">'+esc(N((S[x.series]||{}).name||x.name))+L('(',' (')+fmtShort(x.start)+')</a>'; }).join(L('、',', '))+'</dd>'; }
  h += '</dl>';
  // 記録の種類・出典・メモは折りたたむ(削除はしない)
  var more = '';
  if(e.evidence) more += '<dt>'+L('記録の種類','Record type')+'</dt><dd>'+esc(N(e.evidence))+(e.jwf_relationship?L('(',' (')+esc(N(e.jwf_relationship))+')':'')+'</dd>';
  if(e.sources && e.sources.length) more += '<dt>'+L('出典','Sources')+'</dt><dd><ul class="sources">'+e.sources.map(function(x){ return '<li><span class="st">'+esc(N(x.type))+'</span><a href="'+esc(x.url)+'" target="_blank" rel="noopener">'+esc(x.url.replace(/^https?:\/\//,''))+'</a></li>'; }).join('')+'</ul></dd>';
  var notes = (e.notes||[]).slice();
  if(e.schedule_history) e.schedule_history.forEach(function(x){ if(x.source_text) notes.push('日程の経緯:'+x.source_text); });
  if(notes.length) more += '<dt>'+L('メモ','Notes')+'</dt><dd>'+notes.map(function(n){
    if(LANG!=='en') return '<p>'+esc(n)+'</p>';
    var hist = n.indexOf('日程の経緯:')===0, body = hist ? n.slice(6) : n, t = TR[body];
    return t ? '<p>'+(hist?'Schedule history: ':'')+esc(t)+' <span class="mt">auto-translated</span></p><p class="orig" lang="ja">'+esc(n)+'</p>' : '<p lang="ja">'+esc(n)+'</p>';
  }).join('')+'</dd>';
  if(more) h += '<details class="more-info"><summary>'+L('大会情報・出典を詳しく見る','Event details and sources')+'</summary><dl class="facts">'+more+'</dl></details>';

  var vids = (byEvent[e.id]||[]).filter(vidOk);
  var matches = vids.filter(function(v){return v.k==='match';}), related = vids.filter(function(v){return v.k!=='match';});
  if(!vids.length && !(candByEvent[e.id]||[]).length){
    h += '<p class="empty">'+L('この開催回に対応づけた動画はまだありません。'+(e.status==='cancelled'?'この大会は中止の記録があります。':'動画が未登録でも、配信がなかったとは限りません。'),
      'No videos are linked to this edition yet. '+(e.status==='cancelled'?'This tournament is recorded as cancelled.':'That does not necessarily mean it was not streamed.'))+'</p>';
  }
  // 日付ごと → マット順
  var byDay = {}; matches.forEach(function(v){ var k = v.dh||''; (byDay[k]=byDay[k]||[]).push(v); });
  Object.keys(byDay).sort().forEach(function(day){
    var list = byDay[day].sort(function(a,b){ return (a.m||'~')<(b.m||'~')?-1:((a.m||'~')>(b.m||'~')?1:(a.p<b.p?-1:1)); });
    var sess = day && e.sessions ? e.sessions.filter(function(x){return x.start_date<=day && day<=x.end_date;})[0] : null;
    var gid = 'g-'+e.id+'-'+(day||'x'); moreCache[gid]=list;
    h += vgroup(day ? fmtDate(day) : L('競技日の特定できない試合動画','Match videos (day unconfirmed)'), (sess?N(sess.label)+L('、',', '):'')+nv(list.length), list, false, gid);
  });
  if(related.length){ var rid='r-'+e.id; moreCache[rid]=related; h += vgroup(L('インタビュー・告知など','Interviews, announcements and more'), nv(related.length), related, false, rid); }
  var cands = (candByEvent[e.id]||[]).filter(vidOk);
  if(cands.length){ var cid='c-'+e.id; moreCache[cid]=cands; h += vgroup(L('確認待ち:この開催回の候補','Pending review: possible videos for this edition'), L('まだ確定していません。根拠を表示しています','Not confirmed yet; the basis is shown'), cands, true, cid); }
  if(st.sty || st.k) h += '<p class="hint">'+L((st.sty?'スタイル「'+esc(st.sty)+'」':'')+(st.sty&&st.k?'・':'')+(st.k?'種類「'+esc(kindLabel(st.k))+'」':'')+'の動画だけを表示しています。',
    'Showing only '+[st.sty?'style "'+esc(N(st.sty))+'"':'', st.k?'type "'+esc(kindLabel(st.k))+'"':''].filter(Boolean).join(' and ')+' videos.')+'</p>';
  if((byEvent[e.id]||[]).length && !vids.length) h += '<p class="empty">'+L('この開催回には、いまの条件に合う動画がありません。','No videos in this edition match the current filters.')+'</p>';
  h += '</div>';
  return h;
}
function seriesBlock(item){
  var s = item.s, open = st.s===s.id;
  var visibleEvents = s.events.filter(eventVisible);
  var yrs = visibleEvents.map(function(e){return e.year;});
  var span = yrs.length ? (Math.min.apply(null,yrs)===Math.max.apply(null,yrs) ? yl(yrs[0]) : Math.min.apply(null,yrs)+L('〜','–')+Math.max.apply(null,yrs)+L('年','')) : '';
  var h = '<div class="series'+(open?' open':'')+'" id="s-'+esc(s.id)+'">';
  h += '<button type="button" class="shead" aria-expanded="'+open+'" aria-controls="sb-'+esc(s.id)+'" data-series="'+esc(s.id)+'"><span class="sthumb" aria-hidden="true">'+thumb(seriesThumb(s), '')+'</span><span class="body">'+
    '<span class="sname">'+esc(N(s.name))+'</span><span class="smeta">'+
    '<span class="pill"><span class="num">'+s.n+'</span>'+L('本',' videos')+'</span>'+(span?'<span class="tabnum">'+span+'</span>':'')+
    s.groups.map(function(g){return '<span class="tag">'+esc(N(g))+'</span>';}).join('')+
    (s.scope==='海外'?'<span class="tag">'+L('海外','Overseas')+'</span>':'')+(s.master?'':'<span class="tag unlisted">'+L('開催情報を確認中','Event details TBC')+'</span>')+
    '<span class="kinds">'+esc(kindText(seriesVids(s)))+'</span>'+
    (item.why?'<span class="why">'+esc(item.why)+'</span>':'')+'</span></span><span class="mark" aria-hidden="true">+</span></button>';
  if(open){
    h += '<div class="sbody" id="sb-'+esc(s.id)+'">';
    if(seriesPage(s.id)) h += '<p class="pagelink"><a href="'+esc(seriesPage(s.id))+'">'+L(esc(s.name)+'のページを開く','Open the '+esc(N(s.name))+' page')+'</a></p>';
    if(LANG==='en'){ if(N(s.name)!==s.name) h += '<p class="aliases">Japanese name: <span lang="ja">'+esc(s.name)+'</span></p>'; }
    else if(s.aliases && s.aliases.length) h += '<p class="aliases">この名前でも探せます:'+esc(s.aliases.join('、'))+'</p>';
    if(!s.master) h += '<p class="aliases">'+L('この大会の公式の開催日・会場は確認中です。表示している日付は動画の公開日から推定した参考値です(動画はすべて見られます)。','Official dates and venues for this tournament are being confirmed. Dates shown are estimated from video publish dates (all videos are available).')+'</p>';
    var evs = visibleEvents.slice();
    if(st.y) evs = evs.filter(function(e){ return String(e.year)===st.y; }).concat([]);
    var railEvs = visibleEvents;
    // 開く開催回:URLで指定された回を優先。ただし開催年・検索語の年・動画の種類の条件から外れていれば、条件に合う回に切り替える
    var ey = effYear();
    var fits = function(e){ return (!ey || String(e.year)===ey) && eventHasKind(e); };
    var sel = st.e && E[st.e] && E[st.e].series===s.id && fits(E[st.e]) ? E[st.e] : null;
    if(!sel){
      var pool = railEvs.filter(fits); if(!pool.length) pool = ey ? railEvs.filter(function(e){ return String(e.year)===ey; }) : [];
      if(!pool.length) pool = railEvs;
      sel = pool.filter(function(e){return e.n>0;}).pop() || pool[pool.length-1] || null;
    }
    if(railEvs.length){
      var sameYear = {}; railEvs.forEach(function(e){ sameYear[e.year]=(sameYear[e.year]||0)+1; });
      h += '<div class="rail" role="group" aria-label="'+L('開催年を選ぶ','Choose a year')+'">'+railEvs.map(function(e){
        var cls = e.status==='cancelled'?'cancelled':e.status==='scheduled'?'scheduled':e.derived?'unverified':(e.n>0?'':'none');
        var label = sameYear[e.year]>1 && e.start ? e.year+'.'+(+e.start.slice(5,7)) : String(e.year);
        var sr = L(e.year+'年'+(STATUS[e.status]?'、'+STATUS[e.status]:'')+'、動画'+e.n+'本', e.year+(STATUS[e.status]?', '+STATUS[e.status]:'')+', '+plural(e.n,'video'));
        return '<button type="button" class="yr '+cls+'" aria-pressed="'+(sel&&sel.id===e.id)+'" data-event="'+esc(e.id)+'" aria-label="'+esc(sr)+'">'+
          '<span class="dot" aria-hidden="true"></span><span class="y tabnum">'+label+'</span><span class="n tabnum">'+(e.status==='cancelled'?L('中止','Cancelled'):L(e.n+'本', String(e.n)))+'</span></button>';
      }).join('')+'</div>';
    }
    if(sel) h += eventPanel(sel);
    var lv = (bySeriesLoose[s.id]||[]).filter(vidOk);
    if(lv.length){ var lid='l-'+s.id; moreCache[lid]=lv; h += vgroup(L('開催回が決まっていない動画','Videos with unconfirmed edition'), L('この大会の動画ですが、どの年の開催回か特定できていません','From this tournament, but the year is not yet identified'), lv, true, lid); }
    h += '</div>';
  }
  h += '</div>';
  return h;
}
function seriesVids(s){
  var out = []; s.events.forEach(function(e){ out = out.concat(byEvent[e.id]||[]); });
  return out.concat(bySeriesLoose[s.id]||[]);
}
// 動画タイトル検索。開催年・区分・国内海外は、動画が結びついた大会・開催回から判定する
function videoHits(){
  if(!st.q) return {hits:[], unknownYear:0};
  var toks = st.q.split(/\s+/).map(skey).filter(Boolean); if(!toks.length) return {hits:[], unknownYear:0};
  var seen = {}, hits = [], unknownYear = 0;
  V.forEach(function(v){
    if(seen[v.id]) return;
    var ev = v.e && E[v.e], se = S[v.s || (ev && ev.series)];
    var ok = toks.every(function(t){ return v.key.indexOf(t)>=0 || (/^(19|20)\d{2}$/.test(t) && ev && String(ev.year)===t); });
    if(!ok || !vidOk(v)) return;
    if(st.c && !(se && se.groups.indexOf(st.c)>=0)) return;
    if(st.sc && !(se && se.scope===st.sc)) return;
    if(st.y){ if(!ev){ unknownYear++; return; } if(String(ev.year)!==st.y) return; }
    seen[v.id] = 1; hits.push(v);
  });
  hits.sort(function(a,b){return a.p<b.p?1:-1;});
  return {hits:hits, unknownYear:unknownYear};
}
function videoSearch(r, first){
  if(!r.hits.length) return '';
  moreCache['vs']=r.hits;
  return '<section class="section" style="margin-top:'+(first?'8':'34')+'px"><h2>'+L('動画タイトルで一致した動画','Videos matching the title')+'<small class="hint" style="margin-left:8px">'+L('条件に一致 '+r.hits.length+'本', plural(r.hits.length,'match','matches'))+'</small></h2>'+
    (r.unknownYear?'<p class="hint">'+L('開催年が確定していない動画'+r.unknownYear+'本は、開催年の条件を判定できないため除いています。', plural(r.unknownYear,'video')+' with an unconfirmed year are excluded because the year filter cannot be applied.')+'</p>':'')+
    (LANG==='en'?'<p class="hint">Video titles are shown in Japanese as published.</p>':'')+
    vgroup(L('公開日の新しい順','Newest first'), '', r.hits, false, 'vs', 3)+'</section>';
}
/* ---------- 選手(選手ページの一覧 assets/players.json。検索語が入ったときだけ読む) ---------- */
var PL = null, plLoading = false;
function loadPlayers(){
  if(PL || plLoading) return; plLoading = true;
  fetch('/assets/players.json',{cache:'no-cache'}).then(function(r){ return r.ok ? r.json() : []; }).then(function(d){
    PL = (d||[]).map(function(p){ p.key = skey([p.n,p.k,p.r,p.c,p.ce].join(' ')); return p; });
    if(st.q) render();
  }).catch(function(){ PL = []; });
}
function playerHits(){
  if(!st.q) return [];
  if(!PL){ loadPlayers(); return []; }
  var toks = st.q.split(/\s+/).map(skey).filter(Boolean); if(!toks.length) return [];
  return PL.filter(function(p){ return toks.every(function(t){ return p.key.indexOf(t)>=0; }); });
}
function playerSection(ps){
  if(!ps.length) return '';
  var MAX = 12;
  return '<section class="section psec"><h2>'+L('選手','Players')+'<small class="hint" style="margin-left:8px">'+L(ps.length+'人', plural(ps.length,'player'))+'</small></h2><ul class="pcards">'+
    ps.slice(0,MAX).map(function(p){
      var nm = LANG==='en' ? (p.r||p.n) : p.n, sub = LANG==='en' ? '' : p.k, club = LANG==='en' ? p.ce : p.c;
      return '<li><a href="'+U('/players/'+p.id+'/')+'"><span class="pn">'+esc(nm)+(p.o?' <span class="olym">'+L('オリンピック代表','Olympian')+'</span>':'')+'</span>'+
        (sub?'<span class="pk">'+esc(sub)+'</span>':'')+(club?'<span class="pcl">'+esc(club)+'</span>':'')+'</a></li>';
    }).join('')+'</ul>'+
    (ps.length>MAX?'<p class="hint"><a href="'+U('/players/')+'#q='+encodeURIComponent(st.q)+'">'+L('ほかの'+(ps.length-MAX)+'人も選手一覧で見る','See '+(ps.length-MAX)+' more in the player list')+'</a></p>':'')+'</section>';
}
/* ---------- 国際大会(UWW)の動画(assets/uww.json。検索語が入ったときだけ読む) ---------- */
var UW = null, uwLoading = false;
function loadUww(){
  if(UW || uwLoading) return; uwLoading = true;
  fetch('/assets/uww.json',{cache:'no-cache'}).then(function(r){ return r.ok ? r.json() : null; }).then(function(d){
    d = d || {v:[]};
    UW = (d.v||[]).map(function(v){
      var c = (d.cat||{})[v.c] || ['', ''];
      v.cl = c; v.ee = (d.ev||{})[v.e] || (v.e ? v.e : 'Other events');
      v.key = skey([v.t, v.e, v.ee, c[0], c[1], v.y].concat(v.pl.map(function(p){ return p.slice(1).join(' '); })).join(' '));
      return v;
    });
    if(st.q) render();
  }).catch(function(){ UW = []; });
}
function uwwHits(){
  if(!st.q) return [];
  if(!UW){ loadUww(); return []; }
  var toks = st.q.split(/\s+/).map(skey).filter(Boolean); if(!toks.length) return [];
  return UW.filter(function(v){ return toks.every(function(t){ return v.key.indexOf(t)>=0; }); });
}
function uwwSection(us){
  if(!us.length) return '';
  var MAX = 10;
  return '<section class="section psec"><h2>'+L('国際大会','International')+'<small class="hint" style="margin-left:8px">'+L(us.length+'本', plural(us.length,'video'))+'</small></h2>'+
    '<p class="hint">'+L('世界レスリング連合(UWW)の公式 YouTube の動画です。','Videos from the official YouTube channel of United World Wrestling (UWW).')+'</p><ul class="vlist">'+
    us.slice(0,MAX).map(function(v){
      var meta = '<span>'+esc(L((v.e||'その他の大会')+' '+v.y, v.ee+' '+v.y))+'</span><span>'+esc(L(v.cl[0], v.cl[1]))+'</span><span>'+L('公開 ','Published ')+esc(fmtDate(v.p))+'</span>';
      var who = v.pl.map(function(p){ return '<a href="'+U('/players/'+p[0]+'/')+'">'+esc(LANG==='en' ? (p[2]||p[1]) : p[1])+'</a>'; }).join(' ');
      return '<li class="v"><a href="'+esc(yt(v.i))+'" target="_blank" rel="noopener" tabindex="-1" aria-hidden="true">'+thumb(v.i,'')+'</a>'+
        '<div><div class="vt"><a href="'+esc(yt(v.i))+'" target="_blank" rel="noopener"'+L(' lang="en"','')+'>'+esc(v.t)+'</a></div>'+
        '<div class="vm">'+meta+'</div>'+(who?'<div class="vm">'+L('出ている選手:','Japanese wrestlers: ')+who+'</div>':'')+'</div></li>';
    }).join('')+'</ul>'+
    '<p class="hint"><a href="'+U('/uww/')+'">'+(us.length>MAX ? L('ほかの'+(us.length-MAX)+'本は国際大会のページで見る','See '+(us.length-MAX)+' more on the International videos page') : L('国際大会のページを見る','Open the International videos page'))+'</a></p></section>';
}
function looseSection(){
  var list = loose.filter(vidOk); if(!list.length) return '';
  moreCache['loose']=list;
  return '<details class="loose"><summary>'+L('大会を特定できていない動画('+list.length+'本)','Videos with no identified tournament ('+list.length+')')+'</summary><p class="hint">'+L('タイトルに大会名がない動画です。候補がある場合は根拠とともに示しています。','Their titles do not name a tournament. Possible matches are shown with the basis.')+'</p>'+vgroup(L('公開日の新しい順','Newest first'),'',list.slice().sort(function(a,b){return a.p<b.p?1:-1;}),true,'loose',3)+'</details>';
}
function render(){
  renderControls();
  var list = filteredSeries();
  var vr = videoHits();
  // 選手名で一致した選手は、大会より上に出す
  var ph = st.s ? [] : playerHits();
  var uh = st.s ? [] : uwwHits();
  renderStatus(list, st.q && (vr.hits.length || !list.length) ? vr.hits.length : null, ph.length);
  var anyFilter = st.q||st.y||st.c||st.sty||st.sc||st.k||st.all;
  var h = '';
  document.getElementById('jhero').classList.toggle('compact', !!(anyFilter || st.s));
  if(!anyFilter && !st.s) h += renderShelves();
  h += playerSection(ph);
  h += uwwSection(uh);
  // 大会が0件で動画だけ見つかったときは、動画を先に出す
  var videosFirst = !list.length && vr.hits.length && !st.s;
  if(videosFirst){
    h += '<p class="noser">'+L('大会名では一致しませんでしたが、動画タイトルで'+vr.hits.length+'本見つかりました。','No tournament matched, but '+plural(vr.hits.length,'video')+' matched by title.')+'</p>' + videoSearch(vr, true);
    document.getElementById('main').innerHTML = h; afterRender(); return;
  }
  if(!list.length && !st.s && (ph.length || uh.length)){ document.getElementById('main').innerHTML = h; afterRender(); return; }
  if(!list.length && !st.s){
    h += '<div class="empty"><p>'+L('<strong>条件に合う大会・動画はありません。</strong>検索語を短くするか、条件を外してください。','<strong>No tournaments or videos match.</strong> Try a shorter search or remove filters. Video titles are in Japanese, so English words only match tournament names.')+'</p>'+
      '<p>'+L('いまの条件:','Current filters: ')+esc(currentConditions())+'</p><button type="button" class="clear" id="clear">'+L('条件をすべてクリア','Clear all filters')+'</button></div>';
    document.getElementById('main').innerHTML = h; afterRender(); return;
  }
  h += '<section class="section"><div class="listhead"><h2>'+(anyFilter?L('条件に合う大会','Matching tournaments'):L('すべての大会','All tournaments'))+'</h2>'+
    '<label class="hint" style="margin:0">'+L('並び順','Sort')+' <select id="sort"><option value="date"'+(st.sort==='date'?' selected':'')+'>'+L('最近開催された順','Most recent')+'</option><option value="count"'+(st.sort==='count'?' selected':'')+'>'+L('動画の多い順','Most videos')+'</option><option value="name"'+(st.sort==='name'?' selected':'')+'>'+L('名前順','Name')+'</option></select></label></div>';
  if(!list.length){
    h += '<p class="empty">'+L('<strong>条件に合う大会はありません。</strong>検索語を短くするか、上の条件を外してください。','<strong>No tournaments match.</strong> Try a shorter search or remove filters above.')+'</p>';
  } else {
    // 開いている大会が一覧にない場合(条件で外れた)も表示する
    if(st.s && S[st.s] && !list.some(function(x){return x.s.id===st.s;})) list.unshift({s:S[st.s], why:L('選択中の大会','Selected tournament')});
    h += '<div class="slist">'+list.map(seriesBlock).join('')+'</div>';
  }
  h += '</section>';
  h += videoSearch(vr, false);
  if(!st.q && !st.s) h += looseSection();
  document.getElementById('main').innerHTML = h;
  afterRender();
}
function currentConditions(){
  var c = [];
  if(st.q) c.push(L('検索「'+st.q+'」','search "'+st.q+'"')); if(st.y) c.push(yl(st.y)); if(st.c) c.push(L('区分:','category: ')+N(st.c)); if(st.sty) c.push(L('スタイル:','style: ')+N(st.sty));
  if(st.sc) c.push(N(st.sc)); if(st.k) c.push(L('種類:','type: ')+kindLabel(st.k)); if(st.all) c.push(L('動画のない大会も表示','including tournaments without videos'));
  return c.join(L('、',', ')) || L('なし','none');
}
function afterRender(){
  document.getElementById('master-asof').textContent = fmtDate(DATA.master_as_of);
  var sv = document.getElementById('stat-v');
  // 入口の演出:収録本数を 0 から数え上げる(最初の1回だけ)
  if(document.documentElement.classList.contains('intro') && !sv.dataset.done && window.requestAnimationFrame){
    sv.dataset.done = '1'; var n = V.length + (window.UWW_N||0), t0 = 0;
    var step = function(t){ if(!t0) t0 = t; var k = Math.min(1, (t - t0) / 1400); sv.textContent = Math.round(n * (1 - Math.pow(1 - k, 3))); if(k < 1) requestAnimationFrame(step); };
    sv.textContent = '0'; requestAnimationFrame(step);
  } else if(!sv.dataset.done) sv.textContent = V.length + (window.UWW_N||0);
  var r = DATA.report||{};
  document.getElementById('build-info').textContent = L('データ更新:'+fmtDate(DATA.as_of)+'。動画'+(r.video_count||V.length)+'本。', 'Data updated: '+fmtDate(DATA.as_of)+'. '+plural(r.video_count||V.length,'video')+'.');
  // 年表レールは選択中の年が見える位置までスクロールする
  Array.prototype.forEach.call(document.querySelectorAll('.rail'), function(r){
    var b = r.querySelector('.yr[aria-pressed="true"]'); if(b) r.scrollLeft = Math.max(0, b.offsetLeft - r.clientWidth/2 + b.offsetWidth/2);
  });
  Array.prototype.forEach.call(document.querySelectorAll('.rowwrap .row'), function(r){ updRow(r); r.addEventListener('scroll', function(){ updRow(r); }, {passive:true}); });
  if(pendingScroll){ var el = document.getElementById(pendingScroll); pendingScroll=''; if(el){ el.scrollIntoView({block:'start'}); var f = el.querySelector('.shead'); if(f) f.focus({preventScroll:true}); } }
}
var pendingScroll = '';

/* ---------- 操作 ---------- */
var qTimer;
document.getElementById('q').addEventListener('input', function(ev){
  clearTimeout(qTimer); var val = ev.target.value;
  qTimer = setTimeout(function(){ st.q = val.trim(); legacyNote=''; commit(false); }, 180);
});
document.getElementById('q').addEventListener('keydown', function(ev){ if(ev.key==='Enter'){ clearTimeout(qTimer); st.q = ev.target.value.trim(); commit(true); } });
[['f-year','y'],['f-cat','c'],['f-style','sty'],['f-scope','sc'],['f-kind','k']].forEach(function(p){
  document.getElementById(p[0]).addEventListener('change', function(ev){ st[p[1]] = ev.target.value; if(p[1]==='y') st.e=''; commit(true); });
});
document.getElementById('f-all').addEventListener('change', function(ev){ st.all = ev.target.checked; commit(true); });
document.getElementById('home').addEventListener('click', function(ev){ ev.preventDefault(); st = blankState(); legacyNote=''; commit(true); window.scrollTo(0,0); });
document.addEventListener('change', function(ev){ if(ev.target.id==='sort'){ st.sort = ev.target.value; commit(true); } });
document.addEventListener('click', function(ev){
  var t = ev.target.closest('[data-series],[data-event],[data-drop],[data-setyear],[data-more],[data-cat],[data-feat],[data-featto],.rbtn,#clear,a.tile[href^="#"],.event a[href^="#"]');
  if(!t) return;
  if(t.dataset.row){ var r = document.getElementById(t.dataset.row); if(r) r.scrollBy({left:(+t.dataset.dir)*r.clientWidth*0.9, behavior:'smooth'}); return; }
  if(t.dataset.feat){ showFeature(featI + (+t.dataset.feat)); var nb = document.querySelector('[data-feat="'+t.dataset.feat+'"]'); if(nb) nb.focus(); return; }
  if(t.dataset.featto){ showFeature(+t.dataset.featto); var db = document.querySelector('[data-featto="'+t.dataset.featto+'"]'); if(db) db.focus(); return; }
  if(t.dataset.cat){ st = blankState(); st.c = t.dataset.cat; legacyNote=''; commit(true); var sb = document.getElementById('status'); if(sb) sb.scrollIntoView({block:'start'}); return; }
  if(t.id==='clear'){ var keep = {s:st.s, e:st.e, sort:st.sort}; st = blankState(); st.s=keep.s; st.e=keep.e; st.sort=keep.sort; legacyNote=''; document.getElementById('q').value=''; commit(true); return; }
  if(t.dataset.setyear){ st.y = t.dataset.setyear; st.e=''; commit(true); return; }
  if(t.dataset.drop){ var k=t.dataset.drop; if(k==='all') st.all=false; else st[k]=''; if(k==='y') st.e=''; if(k==='q') document.getElementById('q').value=''; commit(true); return; }
  if(t.dataset.more){ var id=t.dataset.more, list=moreCache[id], box=document.getElementById(id);
    if(list && box){ box.querySelector('.vlist').innerHTML = list.map(function(v){return videoRow(v, id.charAt(0)==='c'||id.charAt(0)==='l'||id==='loose');}).join(''); t.remove(); } return; }
  if(t.dataset.series){ var sid=t.dataset.series; if(st.s===sid){ st.s=''; st.e=''; } else { st.s=sid; st.e=''; pendingScroll='s-'+sid; } commit(true); return; }
  if(t.dataset.event){ st.e=t.dataset.event; commit(true); var p=document.getElementById('ev-'+st.e); if(p) p.scrollIntoView({block:'nearest'}); var b=document.querySelector('[data-event="'+CSS.escape(st.e)+'"]'); if(b) b.focus({preventScroll:true}); return; }
  if(t.tagName==='A'){ ev.preventDefault(); var p2 = new URLSearchParams(t.getAttribute('href').slice(1)); st.s=p2.get('s')||''; st.e=p2.get('e')||''; st.q=''; st.y=''; st.c=''; st.sty=''; st.sc=''; st.k=''; pendingScroll='s-'+st.s; commit(true); }
});
window.addEventListener('popstate', function(){ readHash(); render(); });
// 表示色の切り替え(アイコンは今の状態:白なら☀、黒なら🌙)
var themeBtn = document.getElementById('theme-btn');
function themeLabel(){ var light = document.documentElement.getAttribute('data-theme')==='light';
  themeBtn.setAttribute('aria-label', light ? L('いまはライト表示。ダーク表示に切り替え','Light mode. Switch to dark mode') : L('いまはダーク表示。ライト表示に切り替え','Dark mode. Switch to light mode')); themeBtn.title = themeBtn.getAttribute('aria-label'); }
themeBtn.addEventListener('click', function(){ window.__setTheme(document.documentElement.getAttribute('data-theme')==='light' ? 'dark' : 'light'); themeLabel(); });
themeLabel();

readHash();
if(st.s) pendingScroll = 's-'+st.s;
FEAT = buildFeature(); showFeature(0);
render();
// 画面の幅が変わったら、列の矢印の高さと表示を合わせ直す
window.addEventListener('resize', function(){ Array.prototype.forEach.call(document.querySelectorAll('.rowwrap .row'), updRow); });
})();
