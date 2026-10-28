"""
どのページにも共通の小さな JavaScript(Issue #18)。

これまでページの中に直接書いていた次の処理を、assets/head.js という1つのファイルにまとめる。
ページの中に直接書いた JavaScript が無くなるほど、CSP(セキュリティヘッダー)で
'unsafe-inline' を外せるようになり、改ざんされたスクリプトを動かされにくくなる。

- Google アナリティクスの初期設定
- 日本語以外のブラウザを英語版へ移す(日本語版のページだけ。<script data-redirect> のとき)
- テーマ(明るい・暗い)の切り替え
- YouTube のサムネイルが読み込めないときに、別の大きさの画像に替える(<img data-thumb>)
- ヘッダーの言語切り替え(<a class="lang" data-lang>)で、選んだ言語を覚える
- ヘッダーの検索欄(<form class="hsearch">)で、トップページの検索に移る
- 画像が読み込めないときに消す(<img data-gone>。書籍の表紙など)
- トップページを開いた最初の1回だけ、ロゴの動き(intro)を出す(<script data-intro>)

assets/site.js(defer で読み込む)には、ページを読み終えてから動けばよい処理をまとめる。

- 開催年の帯(<nav class="rail">)を、表示中の年が見える位置まで動かす
- メールアドレスのリンクを組み立てる(<a class="eml" data-u data-d>)
- 選手ページの国際大会の動画を、何本かずつのページに分ける(<section data-per>)
- 写真の拡大表示(<dialog class="plb">)と「写真をもっと見る」ボタン
- アドレスの # が閉じた欄(<details id>。開催回ページの #winners など)を指すときは、その欄を開く
- 選手一覧の検索欄(#pq)。ひらがなはカタカナに、名前の異体字(髙・﨑・德)はふつうの字にしてくらべる

- build_pages.py が assets/head.js に書き出し、すべてのページの <head> から読み込む。
  色の切り替えが画面に出る前に終わるよう、defer や async は付けない
- 中身を変えたときは HEAD_VER・SITE_VER を上げる(ブラウザに古いファイルを使わせないため)
- カレンダーの JavaScript は calendar_page.py が assets/calendar.js に書き出す
- お問い合わせフォームの JavaScript は assets/contact.js。文言・送り先は実行しない JSON としてページに置く
- index.html(トップページ)の JavaScript は、手で書いた assets/top.js にある(ビルドでは作らない)
"""
import os

HEAD_VER = "3"
SITE_VER = "3"
CONTACT_VER = "1"


def script_tag(redirect=False, intro=False):
    """index.html(手で書いたトップページ)には script_tag(redirect=True, intro=True) と同じタグを書いておく。
    HEAD_VER を上げたら index.html の番号も直す(合っていないと en_index.py がビルドを止める)"""
    return (f'<script src="/assets/head.js?v={HEAD_VER}"{" data-redirect" if redirect else ""}'
            f'{" data-intro" if intro else ""}></script>')


# ページを読み終えてから動けばよい処理は assets/site.js にまとめ、defer で読み込む
SITE_TAG = f'<script defer src="/assets/site.js?v={SITE_VER}"></script>'


HEAD_JS = r"""(function(){
'use strict';
var d=document.documentElement,me=document.currentScript;
window.dataLayer=window.dataLayer||[];
window.gtag=function(){dataLayer.push(arguments);};
gtag('js',new Date());gtag('config','__GA_ID__');
if(me&&me.hasAttribute('data-redirect'))(function(){
  try{if(localStorage.getItem('lang'))return;}catch(x){return;}
  var u=navigator.userAgent||'';
  if(/bot|crawl|spider|slurp|lighthouse|headless|preview|facebookexternalhit|embedly/i.test(u))return;
  var l=(navigator.languages&&navigator.languages.length?navigator.languages:[navigator.language||'']).join(',').toLowerCase();
  if(!l||/(^|,)ja/.test(l))return;
  location.replace('/en'+location.pathname+location.search+location.hash);
})();
var m=window.matchMedia&&matchMedia('(prefers-color-scheme: light)'),t;
try{t=sessionStorage.getItem('theme');localStorage.removeItem('theme');}catch(e){}
function set(v){d.setAttribute('data-theme',v);var c=document.querySelector('meta[name="theme-color"]');if(c)c.content=v==='light'?'#0b0b0e':'#08080a';}
set(t==='light'||t==='dark'?t:(m&&m.matches?'light':'dark'));
if(m&&m.addEventListener&&t!=='light'&&t!=='dark')m.addEventListener('change',function(e){try{if(sessionStorage.getItem('theme'))return;}catch(x){}set(e.matches?'light':'dark');});
window.__setTheme=function(v){set(v);try{sessionStorage.setItem('theme',v);}catch(e){}};
if(me&&me.hasAttribute('data-intro'))(function(){
  try{if(location.hash||location.search||sessionStorage.getItem('intro'))return;sessionStorage.setItem('intro','1');}catch(e){return;}
  if(window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches)return;
  d.classList.add('intro');
})();
window.thumbFail=function(i){
  var o=['mqdefault','hqdefault','default'],r=/\/vi\/([^/]+)\/([a-z]+)\.jpg/.exec(i.src);
  if(r){var n=o[o.indexOf(r[2])+1];if(n){i.src='https://i.ytimg.com/vi/'+r[1]+'/'+n+'.jpg';return;}}
  i.remove();
};
document.addEventListener('error',function(ev){
  var i=ev.target;
  if(!i||i.tagName!=='IMG')return;
  if(i.hasAttribute('data-thumb'))thumbFail(i);
  else if(i.hasAttribute('data-gone'))i.remove();
},true);
document.addEventListener('click',function(ev){
  var a=ev.target.closest&&ev.target.closest('a.lang[data-lang]');
  if(!a)return;
  try{localStorage.setItem('lang',a.getAttribute('data-lang'));}catch(x){}
  a.href=a.getAttribute('href').split('#')[0]+location.hash;
});
document.addEventListener('submit',function(ev){
  var f=ev.target;
  if(!f.classList||!f.classList.contains('hsearch'))return;
  ev.preventDefault();
  var v=f.q.value.trim();
  if(!v){f.q.focus();return;}
  location.href=f.action+'#q='+encodeURIComponent(v);
});
})();
"""


SITE_JS = r"""(function(){
'use strict';
var each=function(sel,f){[].forEach.call(document.querySelectorAll(sel),f);};
each('nav.rail',function(r){
  var c=r.querySelector('[aria-current]');
  if(c)r.scrollLeft=Math.max(0,c.offsetLeft-r.clientWidth/2+c.offsetWidth/2);
});
each('a.eml[data-u][data-d]',function(a){
  a.href='mailto:'+a.dataset.u+'@'+a.dataset.d;a.textContent=a.dataset.u+'@'+a.dataset.d;
});
each('section[data-per]',function(s){
  var l=s.querySelector('.vlist');if(!l)return;
  var it=[].slice.call(l.children),n=+s.dataset.per,pg=Math.ceil(it.length/n),nav=document.createElement('nav');
  if(pg<2)return;
  nav.className='pager';nav.setAttribute('aria-label',s.dataset.label);
  function show(k,go){
    it.forEach(function(x,i){x.hidden=i<k*n||i>=(k+1)*n;});
    var h='<button type="button" data-k="'+(k-1)+'"'+(k?'':' disabled')+' aria-label="'+s.dataset.prev+'">‹</button>';
    for(var i=0;i<pg;i++)h+='<button type="button" data-k="'+i+'"'+(i==k?' aria-current="page"':'')+'>'+(i+1)+'</button>';
    h+='<button type="button" data-k="'+(k+1)+'"'+(k<pg-1?'':' disabled')+' aria-label="'+s.dataset.next+'">›</button>';
    h+='<span class="pg-n">'+s.dataset.range.replace('{a}',k*n+1).replace('{b}',Math.min((k+1)*n,it.length))+'</span>';
    nav.innerHTML=h;if(go)s.scrollIntoView({block:'start'});
  }
  nav.addEventListener('click',function(ev){var b=ev.target.closest('button');if(b&&!b.disabled)show(+b.dataset.k,1);});
  l.after(nav);show(0);
});
each('dialog.plb',function(d){
  var g=d.previousElementSibling,mb=g.querySelector('.pshow');
  if(mb)mb.addEventListener('click',function(){[].forEach.call(g.querySelectorAll('.pgrid li[hidden]'),function(li){li.hidden=false;});mb.remove();});
  if(!d.showModal)return;
  var as=[].slice.call(g.querySelectorAll('.pgrid a')),im=d.querySelector('img'),fc=d.querySelector('figcaption'),i=0,x0=null;
  function show(k){
    i=(k+as.length)%as.length;var a=as[i],t=a.querySelector('img');
    im.src=a.getAttribute('data-full');im.alt=t.alt;fc.textContent=a.getAttribute('data-cap')||'';
    var cr=a.getAttribute('data-credit');
    if(cr){var sp=document.createElement('span');sp.className='pcredit';sp.textContent=cr;fc.appendChild(sp);}
    d.classList.toggle('one',as.length<2);
  }
  as.forEach(function(a,k){a.addEventListener('click',function(ev){ev.preventDefault();show(k);d.showModal();});});
  d.querySelector('.plb-x').addEventListener('click',function(){d.close();});
  d.querySelector('.plb-p').addEventListener('click',function(){show(i-1);});
  d.querySelector('.plb-n').addEventListener('click',function(){show(i+1);});
  d.addEventListener('click',function(ev){if(ev.target===d||ev.target.tagName==='FIGURE')d.close();});
  d.addEventListener('keydown',function(ev){if(ev.key==='ArrowLeft')show(i-1);if(ev.key==='ArrowRight')show(i+1);});
  d.addEventListener('touchstart',function(ev){x0=ev.touches[0].clientX;},{passive:true});
  d.addEventListener('touchend',function(ev){if(x0===null)return;var dx=ev.changedTouches[0].clientX-x0;x0=null;if(Math.abs(dx)>50)show(dx<0?i+1:i-1);});
  d.addEventListener('close',function(){im.removeAttribute('src');});
});
(function(){
function op(){var d=location.hash.length>1&&document.getElementById(location.hash.slice(1));if(d&&d.tagName==='DETAILS'){d.open=true;d.scrollIntoView({block:'start'});}}
op();window.addEventListener('hashchange',op);
})();
(function(){
var q=document.getElementById('pq'),c=document.getElementById('pcount');
if(!q||!c)return;
var items=[].slice.call(document.querySelectorAll('#plist li')),groups=[].slice.call(document.querySelectorAll('#plist .pgroup'));
function n(s){
  s=(s||'').replace(/\u309b/g,'\u3099').replace(/\u309c/g,'\u309a').normalize('NFKC').toLowerCase();
  s=s.replace(/[\u3041-\u3096]/g,function(c){return String.fromCharCode(c.charCodeAt(0)+0x60);});
  s=s.replace(/[\u9ad9\ufa11\u5fb7]/g,function(c){return {'\u9ad9':'\u9ad8','\ufa11':'\u5d0e','\u5fb7':'\u5fb3'}[c];});
  return s.replace(/[\s\u30fb\uff65]/g,'');
}
items.forEach(function(li){li._k=n(li.getAttribute('data-k'));});
function run(){
  var t=n(q.value),hit=0;
  items.forEach(function(li){var ok=!t||li._k.indexOf(t)>=0;li.hidden=!ok;if(ok)hit++;});
  groups.forEach(function(g){var has=!!g.querySelector('li:not([hidden])');g.hidden=!has;if(t)g.open=has;else if(q._was)g.open=false;});
  q._was=!!t;
  c.textContent=t?(hit?c.dataset.hit.replace('{n}',hit):c.dataset.none):c.dataset.all.replace('{n}',items.length);
  try{history.replaceState(null,'',t?'#q='+encodeURIComponent(q.value):location.pathname);}catch(x){}
}
var m=/[#&]q=([^&]*)/.exec(location.hash);if(m){try{q.value=decodeURIComponent(m[1]);}catch(x){}}
q.addEventListener('input',run);run();
})();
})();
"""


def contact_tags(formspree_id, email_user, email_domain, text):
    """お問い合わせフォームの設定(実行しない JSON)と、動かす処理(assets/contact.js)を読み込むタグ"""
    import json
    conf = {"formspree": formspree_id, "u": email_user, "d": email_domain, "t": text}
    return ('<script type="application/json" id="c-conf">' + json.dumps(conf, ensure_ascii=False).replace("</", "<\\/") + "</script>"
            f'<script src="/assets/contact.js?v={CONTACT_VER}"></script>')


CONTACT_JS = r"""(function(){
  var conf; try{ conf = JSON.parse(document.getElementById("c-conf").textContent); }catch(x){ return; }
  var T = conf.t, FORMSPREE_ID = conf.formspree, TO = [conf.u, conf.d].join("@");
  function f(k, o){ return T[k].replace(/\{(\w+)\}/g, function(_, x){ return o && x in o ? o[x] : ""; }); }
  var form = document.getElementById("contact-form"), result = document.getElementById("c-result"),
      btn = document.getElementById("c-send"), em = document.getElementById("c-email"), composing = false;
  if (!form) return;
  function half(s){
    return s.replace(/[\uFF01-\uFF5E]/g, function(c){ return String.fromCharCode(c.charCodeAt(0) - 0xFEE0); })
            .replace(/[\u3000\s]/g, "").replace(/[\u30fc\uff0d\u2015\u2010]/g, "-");
  }
  em.addEventListener("compositionstart", function(){ composing = true; });
  em.addEventListener("compositionend", function(){ composing = false; em.value = half(em.value); });
  em.addEventListener("input", function(){ if (!composing) em.value = half(em.value); });
  em.addEventListener("blur", function(){ em.value = half(em.value); });
  try{ var q = new URLSearchParams(location.search), o = form.kind.querySelector('option[data-k="' + q.get("kind") + '"]');
    if (o) { o.selected = true; var pg = q.get("page"); if (pg && /^\/[\w\-\/%.\u3040-\u30ff\u4e00-\u9fff]*$/.test(pg) && !form.message.value) form.message.value = T.page + location.origin + pg + "\n"; } }catch(x){}
  function show(t, msg){ result.className = "cresult " + t; result.textContent = msg; }
  form.addEventListener("submit", function(ev){
    ev.preventDefault();
    var name = form.name.value.trim(), email = half(form.email.value.trim()),
        kind = form.kind.value, msg = form.message.value.trim(), o = {name: name, email: email, kind: kind, msg: msg, to: TO};
    form.email.value = email;
    if (!name || !email || !msg){ show("ng", f("required", o)); return; }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)){ show("ng", f("format", o)); return; }
    if (!FORMSPREE_ID){
      location.href = "mailto:" + TO + "?subject=" + encodeURIComponent(f("subject", o)) + "&body=" + encodeURIComponent(f("body", o));
      show("ok", f("mailapp", o));
      return;
    }
    btn.disabled = true; btn.textContent = f("sending", o);
    fetch("https://formspree.io/f/" + encodeURIComponent(FORMSPREE_ID), {method: "POST", headers: {"Accept": "application/json"}, body: new FormData(form)})
      .then(function(r){
        if (r.ok){ form.reset(); show("ok", f("sent", o)); }
        else { show("ng", f("failed", o)); }
      })
      .catch(function(){ show("ng", f("network", o)); })
      .then(function(){ btn.disabled = false; btn.textContent = f("send", o); });
  });
})();
"""


def write_asset(root, ga_id):
    with open(os.path.join(root, "assets", "head.js"), "w", encoding="utf-8") as f:
        f.write(HEAD_JS.replace("__GA_ID__", ga_id))
    with open(os.path.join(root, "assets", "site.js"), "w", encoding="utf-8") as f:
        f.write(SITE_JS)
    with open(os.path.join(root, "assets", "contact.js"), "w", encoding="utf-8") as f:
        f.write(CONTACT_JS)
