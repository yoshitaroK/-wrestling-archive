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
})();
