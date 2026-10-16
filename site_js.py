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

- build_pages.py が assets/head.js に書き出し、すべてのページの <head> から読み込む。
  色の切り替えが画面に出る前に終わるよう、defer や async は付けない
- 中身を変えたときは HEAD_VER を上げる(ブラウザに古いファイルを使わせないため)
- index.html(トップページ)と、写真の拡大表示・選手一覧・カレンダーなど一部のページの JavaScript は
  まだページの中に書いたまま。次の作業で移す
"""
import os

HEAD_VER = "1"


def script_tag(redirect=False):
    return f'<script src="/assets/head.js?v={HEAD_VER}"{" data-redirect" if redirect else ""}></script>'


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
  if(i&&i.tagName==='IMG'&&i.hasAttribute('data-thumb'))thumbFail(i);
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


def write_asset(root, ga_id):
    with open(os.path.join(root, "assets", "head.js"), "w", encoding="utf-8") as f:
        f.write(HEAD_JS.replace("__GA_ID__", ga_id))
