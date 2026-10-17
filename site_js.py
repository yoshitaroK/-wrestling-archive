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

assets/site.js(defer で読み込む)には、ページを読み終えてから動けばよい処理をまとめる。

- 開催年の帯(<nav class="rail">)を、表示中の年が見える位置まで動かす
- メールアドレスのリンクを組み立てる(<a class="eml" data-u data-d>)
- 選手ページの国際大会の動画を、何本かずつのページに分ける(<section data-per>)
- 写真の拡大表示(<dialog class="plb">)と「写真をもっと見る」ボタン

- build_pages.py が assets/head.js に書き出し、すべてのページの <head> から読み込む。
  色の切り替えが画面に出る前に終わるよう、defer や async は付けない
- 中身を変えたときは HEAD_VER・SITE_VER を上げる(ブラウザに古いファイルを使わせないため)
- index.html(トップページ)と、開催回ページの動画の並べ替え・選手一覧・カレンダー・お問い合わせフォームの
  JavaScript は、まだページの中に書いたまま。次の作業で移す
"""
import os

HEAD_VER = "2"
SITE_VER = "1"


def script_tag(redirect=False):
    return f'<script src="/assets/head.js?v={HEAD_VER}"{" data-redirect" if redirect else ""}></script>'


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
})();
"""


def write_asset(root, ga_id):
    with open(os.path.join(root, "assets", "head.js"), "w", encoding="utf-8") as f:
        f.write(HEAD_JS.replace("__GA_ID__", ga_id))
    with open(os.path.join(root, "assets", "site.js"), "w", encoding="utf-8") as f:
        f.write(SITE_JS)
