(function(){
'use strict';
if(typeof HTMLDialogElement!=='function')return;
var RE=/^https?:\/\/(?:www\.|m\.)?(?:youtube\.com\/watch\?(?:[^#]*&)?v=|youtu\.be\/)([\w-]{11})/;
var EN=document.documentElement.lang==='en';
function L(j,e){return EN?e:j;}
var dlg,box,ttl,ext,last;
function setup(){
  var s=document.createElement('style');
  s.textContent='html.vp-open{overflow:hidden}'+
  '.vplayer{padding:0;border:0;background:transparent;color:#fff;width:min(1100px,calc(100vw - 24px));max-width:none;max-height:none;margin:auto;overflow:visible}'+
  '.vplayer::backdrop{background:rgba(0,0,0,.85)}'+
  '.vp-bar{display:flex;align-items:flex-start;gap:12px;margin-bottom:8px}'+
  '.vp-t{flex:1;margin:0;font-size:15px;font-weight:700;line-height:1.5;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}'+
  '.vp-x{flex:none;width:40px;height:40px;border:0;border-radius:50%;background:rgba(255,255,255,.15);color:#fff;font-size:24px;line-height:1;cursor:pointer}'+
  '.vp-x:hover,.vp-x:focus-visible{background:rgba(255,255,255,.3)}'+
  '.vp-box{position:relative;width:min(100%,calc((100vh - 140px)*16/9));margin:0 auto;aspect-ratio:16/9;background:#000;border-radius:8px;overflow:hidden}'+
  '.vp-box iframe{position:absolute;inset:0;width:100%;height:100%;border:0}'+
  '.vp-foot{margin:8px 0 0;text-align:right;font-size:13px}'+
  '.vp-foot a{color:#fff;opacity:.85}.vp-foot a:hover{opacity:1}';
  document.head.appendChild(s);
  dlg=document.createElement('dialog');
  dlg.className='vplayer';
  dlg.setAttribute('aria-labelledby','vp-t');
  dlg.innerHTML='<div class="vp-bar"><p class="vp-t" id="vp-t"></p><button type="button" class="vp-x" aria-label="'+L('動画を閉じる','Close video')+'">×</button></div>'+
    '<div class="vp-box"></div><p class="vp-foot"><a target="_blank" rel="noopener">'+L('YouTubeで見る','Watch on YouTube')+' ↗</a></p>';
  box=dlg.querySelector('.vp-box');ttl=dlg.querySelector('.vp-t');ext=dlg.querySelector('.vp-foot a');
  dlg.querySelector('.vp-x').addEventListener('click',function(){dlg.close();});
  // 黒い背景(動画の外)を押しても閉じる
  dlg.addEventListener('click',function(ev){if(ev.target===dlg)dlg.close();});
  ext.addEventListener('click',function(){dlg.close();});
  dlg.addEventListener('close',function(){
    box.innerHTML='';
    document.documentElement.classList.remove('vp-open');
    if(last&&document.contains(last))try{last.focus({preventScroll:true});}catch(x){}
  });
  document.body.appendChild(dlg);
}
function titleOf(a){
  var x=a.querySelector('.tt'),row=a.closest('li.v');
  if(!x&&row)x=row.querySelector('.vt a,.vt');
  return ((x||a).textContent||'').replace(/\s+/g,' ').trim();
}
function startOf(href){
  var m=/[?&#]t=(?:(\d+)h)?(?:(\d+)m)?(\d+)?s?(?:&|$)/.exec(href);
  return m?(+(m[1]||0))*3600+(+(m[2]||0))*60+(+(m[3]||0)):0;
}
function open(a,id){
  if(!dlg)setup();
  var t=titleOf(a),st=startOf(a.href),f=document.createElement('iframe');
  f.src='https://www.youtube-nocookie.com/embed/'+id+'?autoplay=1&rel=0&playsinline=1'+(st?'&start='+st:'');
  f.title=t||L('YouTube 動画プレーヤー','YouTube video player');
  f.allow='autoplay; encrypted-media; picture-in-picture; fullscreen; web-share';
  f.allowFullscreen=true;
  f.referrerPolicy='strict-origin-when-cross-origin';
  box.innerHTML='';box.appendChild(f);
  ttl.textContent=t;
  ext.href=a.href;
  last=a.getAttribute('aria-hidden')==='true'&&a.closest('li.v')?(a.closest('li.v').querySelector('.vt a')||a):a;
  document.documentElement.classList.add('vp-open');
  dlg.showModal();
  dlg.querySelector('.vp-x').focus();
  if(typeof window.gtag==='function')window.gtag('event','video_play',{video_id:id});
}
document.addEventListener('click',function(ev){
  if(ev.defaultPrevented||ev.button!==0||ev.metaKey||ev.ctrlKey||ev.shiftKey||ev.altKey)return;
  var a=ev.target.closest&&ev.target.closest('a[href]');
  if(!a||(dlg&&dlg.contains(a)))return;
  var m=RE.exec(a.href);
  if(!m)return;
  ev.preventDefault();
  open(a,m[1]);
});
})();
