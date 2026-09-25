function showTimeframes(row, metadata) {
  const host = document.getElementById('charts');
  host.replaceChildren();
  if (!row.charts) { host.textContent = '데이터 검증을 통과하지 못해 차트를 표시하지 않습니다.'; return; }
  const frames = [
    ['monthly', '01 · 월봉', '장기 상승·하락 흐름과 과거 고점의 위치를 먼저 확인하세요.', 120],
    ['weekly', '02 · 주봉', '베이스의 깊이·기간, 저점의 변화와 반복 저항을 확인하세요.', 156],
    ['daily', '03 · 일봉', '최근 수축과 가격 반응, 돌파 전후 거래량을 확인하세요.', 126]
  ];
  frames.forEach(([key, title, prompt, limit]) => {
    const all = row.charts[key], panel = document.createElement('article');
    panel.className = 'frame';
    const heading = document.createElement('h2'); heading.textContent = title;
    const note = document.createElement('p'); note.textContent = prompt + ' ' + frameObservation(all, key);
    const controls = document.createElement('div'); controls.className = 'controls';
    const range = document.createElement('select'); range.setAttribute('aria-label', title + ' 표시 기간');
    [[limit, `최근 ${limit}봉`], [all.length, '제공된 전체 기간']].forEach(([value, label]) => { const o = document.createElement('option'); o.value = value; o.textContent = label; range.append(o); });
    const scale = document.createElement('select'); scale.setAttribute('aria-label', title + ' 가격 축');
    [['linear', '선형 가격 축'], ['log', '로그 가격 축']].forEach(([value, label]) => { const o = document.createElement('option'); o.value = value; o.textContent = label; scale.append(o); });
    if (key === 'monthly') scale.value = 'log';
    const coverage = document.createElement('p');
    const wrap = document.createElement('div'); wrap.className = 'chart-scroll';
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); svg.setAttribute('viewBox', '0 0 1000 360'); svg.setAttribute('role', 'img'); svg.setAttribute('aria-label', row.symbol + ' ' + title + ' 가격과 거래량'); wrap.append(svg);
    const readout = document.createElement('p'); readout.className = 'bar-readout';
    controls.append(range, scale); panel.append(heading, note, controls, coverage, wrap, readout); host.append(panel);
    const render = () => {
      svg.replaceChildren(); const bars = all.slice(-Number(range.value));
      if (!bars.length) { coverage.textContent = '제공된 봉 없음'; return; }
      coverage.textContent = `${bars[0].start} ~ ${bars.at(-1).end} · 표시 ${bars.length}봉 / 보유 ${all.length}봉 · ${metadata.source}`;
      if (key !== 'daily') coverage.textContent += ' · 첫 기간은 일부일 수 있고, 마지막 기간의 마감 여부는 미확인(황색 테두리). 중간 기간도 누락 거래일 검사는 미수행.';
      if (key === 'monthly' && all.length < 60) coverage.textContent += ' · 월봉 60개 미만: 장기 가격 맥락이 제한됩니다. 이는 매매 필터가 아닌 이력 안내입니다.';
      const add = (tag, attrs, text) => { const node = document.createElementNS(svg.namespaceURI, tag); Object.entries(attrs).forEach(([k,v]) => node.setAttribute(k,v)); if (text !== undefined) node.textContent = text; svg.append(node); return node; };
      const transform = v => scale.value === 'log' ? Math.log(v) : v;
      const lo = Math.min(...bars.map(b => transform(b.low))), hi = Math.max(...bars.map(b => transform(b.high)));
      const y = v => 235 - (transform(v) - lo) / (hi - lo || 1) * 215;
      const maxVol = Math.max(...bars.map(b => b.volume)), step = 890 / bars.length, width = Math.max(1, Math.min(18, step * .7));
      for (let i=0;i<5;i++) { const value=lo+(hi-lo)*i/4, py=235-i*215/4; add('line',{x1:20,x2:920,y1:py,y2:py,stroke:'#29364b'}); add('text',{x:930,y:py+4,fill:'#9aacc4','font-size':14},(scale.value==='log'?Math.exp(value):value).toFixed(2)); }
      add('text',{x:20,y:265,fill:'#9aacc4','font-size':14},'거래량 · 각 기간 합계');
      const describe = b => { readout.textContent = `${b.start} ~ ${b.end} | 시 ${b.open.toFixed(2)} · 고 ${b.high.toFixed(2)} · 저 ${b.low.toFixed(2)} · 종 ${b.close.toFixed(2)} | 거래량 ${Math.round(b.volume).toLocaleString()} · ${b.sessions}거래일${b.boundary_unverified?' · 기간 경계 미확인':''}`; };
      bars.forEach((b,i) => {
        const x=20+step*(i+.5), color=b.close>=b.open?'#5de3bd':'#ff8496';
        add('line',{x1:x,x2:x,y1:y(b.high),y2:y(b.low),stroke:color});
        add('rect',{x:x-width/2,y:Math.min(y(b.open),y(b.close)),width,height:Math.max(1,Math.abs(y(b.open)-y(b.close))),fill:color,stroke:b.boundary_unverified?'#ffd078':color,'stroke-dasharray':b.boundary_unverified?'2 2':'none'});
        const vh=b.volume/maxVol*48; add('rect',{x:x-width/2,y:322-vh,width,height:vh,fill:color,opacity:.55});
        const hit=add('rect',{x:x-step/2,y:15,width:step,height:310,fill:'transparent',tabindex:i===bars.length-1?0:-1});
        const tooltip=document.createElementNS(svg.namespaceURI,'title'); tooltip.textContent=`${b.start} ~ ${b.end}: O ${b.open} H ${b.high} L ${b.low} C ${b.close} V ${b.volume}`;hit.append(tooltip);
        hit.onmouseenter=()=>describe(b);hit.onclick=()=>describe(b);hit.onfocus=()=>describe(b);
      });
      // SMA uses each timeframe's own closes and excludes no bars silently.
      const colors=['#ffd078','#a9a0ff'];
      [10,20].forEach((period,j)=>{
        const points=[];
        for(let i=period-1;i<all.length;i++){
          const shown=i-(all.length-bars.length);if(shown<0)continue;
          const average=all.slice(i-period+1,i+1).reduce((s,b)=>s+b.close,0)/period;
          if(transform(average)<lo||transform(average)>hi)continue;
          points.push(`${20+step*(shown+.5)},${y(average)}`);
        }
        add('polyline',{points:points.join(' '),fill:'none',stroke:colors[j],'stroke-width':1.5,'pointer-events':'none'});
        add('text',{x:20+j*210,y:12,fill:colors[j],'font-size':12},`${key} SMA${period} · 표시용`);
      });
      [0, Math.floor((bars.length-1)/2), bars.length-1].filter((v,i,a)=>a.indexOf(v)===i).forEach(i=>add('text',{x:20+step*(i+.5),y:348,fill:'#9aacc4','font-size':14,'text-anchor':i===0?'start':i===bars.length-1?'end':'middle'},bars[i].start));
      describe(bars.at(-1));
      if(row.quality){
        const q=row.quality;
        [[q.trigger,'실행 역치','#ffd078'],[q.invalidation,'종가 무효화','#ff8496'],[q.overhead,'과거 저항','#a9a0ff']].forEach(([value,label,color],i)=>{
          if(!Number.isFinite(value))return;
          // Current plan only: do not draw today's level across earlier history.
          if(transform(value)>=lo&&transform(value)<=hi)add('line',{x1:895,x2:920,y1:y(value),y2:y(value),stroke:color,'stroke-width':2});
          add('text',{x:430,y:12+i*16,fill:color,'font-size':12},`${label} ${value.toFixed(2)} · 현재 계획`);
        });
      }
    };
    range.onchange=render;scale.onchange=render;render();
  });
}
