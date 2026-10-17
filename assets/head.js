(function(){
'use strict';
var d=document.documentElement,me=document.currentScript;
window.dataLayer=window.dataLayer||[];
window.gtag=function(){dataLayer.push(arguments);};
gtag('js',new Date());gtag('config','G-KWLY01JCWV');
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
