(function(){
'use strict';
var d=document.documentElement,me=document.currentScript;
window.dataLayer=window.dataLayer||[];
window.gtag=function(){dataLayer.push(arguments);};
gtag('js',new Date());gtag('config','G-KWLY01JCWV');
document.addEventListener('load',function(e){var l=e.target;if(l&&l.tagName==='LINK'&&l.hasAttribute('data-font'))l.media='all';},true);
if(me&&me.hasAttribute('data-redirect'))(function(){
  try{if(localStorage.getItem('lang'))return;}catch(x){return;}
  var u=navigator.userAgent||'';
  if(/bot|crawl|spider|slurp|lighthouse|headless|preview|facebookexternalhit|embedly/i.test(u))return;
  var l=(navigator.languages&&navigator.languages.length?navigator.languages:[navigator.language||'']).join(',').toLowerCase();
  if(!l||/(^|,)ja/.test(l))return;
  location.replace('/en'+location.pathname+location.search+location.hash);
})();
var t;
try{t=localStorage.getItem('theme2');localStorage.removeItem('theme');sessionStorage.removeItem('theme');}catch(e){}
function set(v){d.setAttribute('data-theme',v);var c=document.querySelector('meta[name="theme-color"]');if(c)c.content=v==='light'?'#0b0b0e':'#08080a';}
set(t==='light'?'light':'dark');
window.__setTheme=function(v){set(v);try{localStorage.setItem('theme2',v);}catch(e){}};
if(me&&me.hasAttribute('data-intro'))(function(){
  try{if(location.hash||location.search||sessionStorage.getItem('intro'))return;sessionStorage.setItem('intro','1');}catch(e){return;}
  if(window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches)return;
  d.classList.add('intro');
})();
if(me&&me.hasAttribute('data-overlay'))(function(){
  d.classList.add('overlay');
  var t=null,mo=null;
  function size(){d.style.setProperty('--hdr-h',t.offsetHeight+'px');}
  function grab(){
    if(t)return true;
    t=document.querySelector('.top');if(!t)return false;
    if(window.ResizeObserver)new ResizeObserver(size).observe(t);else size();
    return true;
  }
  if(window.MutationObserver){mo=new MutationObserver(function(){if(grab())mo.disconnect();});mo.observe(d,{childList:true,subtree:true});}
  document.addEventListener('DOMContentLoaded',function(){if(mo)mo.disconnect();grab();});
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
d.classList.add('hs');
document.addEventListener('click',function(ev){
  var b=ev.target.closest&&ev.target.closest('.hs-btn');
  if(!b)return;
  var f=document.getElementById('hsearch');if(!f)return;
  var o=f.classList.toggle('open');b.setAttribute('aria-expanded',o?'true':'false');
  if(o)f.q.focus();
});
document.addEventListener('click',function(ev){
  var b=ev.target.closest&&ev.target.closest('[data-share]');
  if(!b)return;
  var c=document.querySelector('link[rel="canonical"]'),u=c&&c.href||location.href.split('#')[0],en=d.lang==='en',s=b.querySelector('span');
  if(navigator.share){navigator.share({title:document.title,url:u}).catch(function(){});return;}
  function say(t){s.textContent=t;b.classList.add('ok');setTimeout(function(){s.textContent=en?'Share':'共有';b.classList.remove('ok');},2400);}
  if(navigator.clipboard&&navigator.clipboard.writeText)navigator.clipboard.writeText(u).then(function(){say(en?'Link copied':'リンクをコピーしました');},function(){window.prompt(en?'Copy this link':'このリンクをコピーしてください',u);});
  else window.prompt(en?'Copy this link':'このリンクをコピーしてください',u);
});
document.addEventListener('DOMContentLoaded',function(){
  var n=document.querySelector('.topnav'),c=n&&n.querySelector('[aria-current]');
  if(c&&n.scrollWidth>n.clientWidth){var nr=n.getBoundingClientRect(),cr=c.getBoundingClientRect();if(cr.right>nr.right-40)n.scrollLeft=cr.left-nr.left-(nr.width-cr.width)/2;}
  var b=document.createElement('button'),on=false;
  b.type='button';b.className='totop';b.setAttribute('aria-label',d.lang==='en'?'Back to top':'ページの先頭へ戻る');
  b.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 14.5l6-6 6 6"/></svg>';
  document.body.appendChild(b);
  function chk(){var v=window.scrollY>window.innerHeight*1.5;if(v!==on){on=v;b.classList.toggle('on',v);}}
  window.addEventListener('scroll',chk,{passive:true});chk();
  b.addEventListener('click',function(){
    var calm=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
    window.scrollTo({top:0,behavior:calm?'auto':'smooth'});
  });
});
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
