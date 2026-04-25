(function(){
  // フィルタ機能（ページ内のカードを非表示/表示）
  var cards = document.querySelectorAll('.clinic-card');
  var qInput = document.getElementById('q-input');
  var visitOnly = document.getElementById('filter-visit');
  var hygOnly = document.getElementById('filter-hyg');
  var countLabel = document.getElementById('count-label');
  var total = cards.length;

  function applyFilter(){
    var q = qInput ? qInput.value.trim().toLowerCase() : '';
    var v = visitOnly && visitOnly.checked;
    var hy = hygOnly && hygOnly.checked;
    var shown = 0;
    cards.forEach(function(c){
      var name = (c.dataset.name||'').toLowerCase();
      var addr = (c.dataset.addr||'').toLowerCase();
      var hasV = c.dataset.visit === '1';
      var hasH = c.dataset.hyg === '1';
      var ok = true;
      if(q && name.indexOf(q)<0 && addr.indexOf(q)<0) ok = false;
      if(v && !hasV) ok = false;
      if(hy && !hasH) ok = false;
      c.style.display = ok ? '' : 'none';
      if(ok) shown++;
    });
    if(countLabel){
      countLabel.textContent = shown + ' / ' + total + ' 件表示中';
    }
  }

  if(qInput) qInput.addEventListener('input', applyFilter);
  if(visitOnly) visitOnly.addEventListener('change', applyFilter);
  if(hygOnly) hygOnly.addEventListener('change', applyFilter);
  applyFilter();

  // 検索JSON（他ページへのジャンプ用、都道府県ページのみ）
  var input=document.getElementById('search-input');
  var results=document.getElementById('search-results');
  var data=[];
  var prefCode=document.body.dataset.prefCode||'';
  if(prefCode && input){
    fetch('/data/search/'+prefCode+'.json')
      .then(function(r){return r.json()})
      .then(function(d){data=d})
      .catch(function(){});
    var timer;
    input.addEventListener('input',function(){
      clearTimeout(timer);
      timer=setTimeout(function(){doSearch()},200);
    });
    function doSearch(){
      var q=input.value.trim().toLowerCase();
      if(q.length<2){results.innerHTML='';return;}
      var hits=data.filter(function(o){
        return(o.st||'').toLowerCase().indexOf(q)>=0;
      }).slice(0,30);
      if(!hits.length){results.innerHTML='<p style="color:#999;margin-top:8px">該当する歯科が見つかりません</p>';return;}
      var html=hits.map(function(o){
        var badges='';
        if(o.v) badges += '<span class="badge badge-visit">訪問歯科対応</span>';
        if(o.h) badges += '<span class="badge badge-hyg">歯科衛生士訪問</span>';
        return '<div class="card" style="margin-bottom:8px"><h3><a href="/clinic/'+esc(o.slug)+'.html">'+esc(o.n)+'</a></h3>'
          +'<div class="meta"><span class="addr">'+esc(o.a)+'</span>'
          +(o.tel?'<span class="tel">TEL: '+esc(o.tel)+'</span>':'')
          +'</div>'
          +(badges?'<div class="badges">'+badges+'</div>':'')
          +'</div>';
      }).join('');
      results.innerHTML=html;
    }
  }
  function esc(s){if(!s)return'';var d=document.createElement('div');d.textContent=s;return d.innerHTML;}
})();
