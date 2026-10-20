(function(){
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
