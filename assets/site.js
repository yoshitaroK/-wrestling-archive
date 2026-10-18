(function(){
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
