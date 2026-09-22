/* Deterministic explanations. Thresholds are ours; source links describe principles. */
function showResearch(row, metadata) {
  const host=document.getElementById('research');host.replaceChildren();
  const add=(tag,text,parent=host)=>{const el=document.createElement(tag);el.textContent=text;parent.append(el);return el;};
  add('h3','왜 이 종목을 보는가');
  if(row.status!=='ok'){add('p',(row.reasons||[]).join(' · '));return;}
  const m=row.metrics, a=row.routes.includes('A'), b=row.routes.includes('B');
  add('p',a?'상승 추세·고점 근처에서 최근 가격 범위가 줄어든 연구 후보입니다. 실제 저항과 수축의 질을 차트에서 확인하세요.':b?'고점에서 크게 하락한 뒤 저점 대비 회복한 연구 후보입니다. 반등인지 새 베이스인지는 별도 확인이 필요합니다.':'현재 연구 필터를 통과하지 않았습니다. 아래 조건으로 이유를 확인할 수 있습니다.');
  add('p','A/B의 숫자 기준은 개발용 가정입니다. Jesse·Ian 원본 스크리너 또는 매수 신호로 간주하지 않습니다.',host).className='warning';
  const definitions=[
    ['공통 · 20일 평균 거래대금',m.turnover20>=metadata.min_turnover,`$${Math.round(m.turnover20).toLocaleString()} / 최소 $${Number(metadata.min_turnover).toLocaleString()}`],
    ['공통 · ADR20',m.ADR20_pct>=metadata.min_adr,`${m.ADR20_pct.toFixed(2)}% / 최소 ${metadata.min_adr}%`],
    ['A · 추세 정렬',m.close>m.ema50&&m.ema50>m.ema100,'종가 > EMA50 > EMA100'],
    ['A · 63일 성과',m.ret63_pct>0,`${m.ret63_pct.toFixed(2)}% > 0%`],
    ['A · 252일 고점 거리',m.offHigh252_pct>=-25,`${m.offHigh252_pct.toFixed(2)}% ≥ −25%`],
    ['A · 최근/이전 5일 범위',m.rangeRatio5<1,`${m.rangeRatio5.toFixed(3)}배 < 1배`],
    ['B · 이평 회복',m.close>m.ema50&&m.close>m.ema100,'종가 > EMA50 및 EMA100'],
    ['B · 고점에서 하락',m.offHigh252_pct<=-30,`${m.offHigh252_pct.toFixed(2)}% ≤ −30%`],
    ['B · 저점에서 회복',m.aboveLow252_pct>=40,`${m.aboveLow252_pct.toFixed(2)}% ≥ 40%`],
    ['B · 126일 성과',m.ret126_pct<=-20,`${m.ret126_pct.toFixed(2)}% ≤ −20%`]
  ];
  const table=add('table',''),body=add('tbody','',table);
  definitions.forEach(([label,pass,value])=>{const tr=add('tr','',body);add('td',label,tr);add('td',pass?'충족':'미충족',tr).className=pass?'pos':'neg';add('td',value,tr);});
  add('p',`거래량 변화: 최근 5일 / 이전 5일 ${m.volumeRatio5.toFixed(2)}배. 확정 일봉 RVOL ${m.RVOL20_completed.toFixed(2)}배. 감소만으로 매물 소진·VCP 완성을 판정하지 않습니다.`);
  add('h3','원문 근거와 사람이 확인할 부분');
  const links=[['Jesse · 후보 최소 기준','https://x.com/Trader_Jesse_/status/1950094226290856055'],['Ian · Base0 위치','https://x.com/tmmrwseoul/status/2075888396116041996/photo/1'],['Ian · 다중 시간축','https://x.com/tmmrwseoul/status/2054815970968166522']];
  links.forEach(([label,url])=>{const p=add('p',''),link=add('a',label,p);link.href=url;link.target='_blank';link.rel='noopener noreferrer';});
  add('p','미확인: 실제 피벗 영역·기준봉·무효화 가격·베이스 번호·업종 내 리더 여부. 아래 가격 측정은 이 판단을 대신하지 않습니다.');
  if(row.history_warning)add('p',`장기 이력 제한: ${row.history_warning.excluded_through}까지 ${row.history_warning.excluded_bars}봉 제외. ${row.history_warning.note}`).className='warning';
}

function frameObservation(bars, key) {
  const confirmed=key==='daily'?bars:bars.filter(b=>!b.boundary_unverified);
  if(confirmed.length<13)return '완결 여부가 확인된 비교 이력이 부족합니다.';
  const last=confirmed.at(-1),prior=confirmed.slice(-13,-1),high=Math.max(...prior.map(b=>b.high)),low=Math.min(...prior.map(b=>b.low));
  const distance=(last.close/high-1)*100, change=(last.close/prior[0].close-1)*100;
  return `경계 미확인 봉 제외 · ${last.end} 종가 기준: 직전 12봉 고점 ${high.toFixed(2)} 대비 ${distance.toFixed(2)}%, 저점 ${low.toFixed(2)}. 12봉 전 대비 ${change.toFixed(2)}%. ${distance>0?'직전 12봉 고점 위':'직전 12봉 고점 아래'}이며, 이 고점은 자동 계산 참고선입니다.`;
}

async function showHistory(snapshotMode) {
  const host=document.getElementById('history-content');
  try {
    const response=await fetch(snapshotMode?'data/history.json':'/api/history',{cache:'no-store'});
    if(!response.ok)throw Error('아직 저장된 완결 기록이 없습니다.');
    const data=await response.json();host.replaceChildren();
    const note=document.createElement('p');note.textContent=data.note;host.append(note);
    [...data.records].reverse().forEach(record=>{const details=document.createElement('details'),summary=document.createElement('summary'),p=document.createElement('p');
      summary.textContent=`${record.as_of} · 후보 ${record.candidates.length}개 · 유효 ${record.valid}/${record.requested} · ${record.rule_version}`;
      p.textContent=`최초 관찰 ${record.observed_at} — `+record.candidates.map(r=>{const t=(data.tracking||[]).find(t=>t.symbol===r.symbol&&t.observed_as_of===record.as_of&&t.rule_version===record.rule_version);return `${r.symbol} (${r.routes.join('+')}, $${r.close.toFixed(2)}) ${Number.isFinite(t?.change_pct)?t.change_pct.toFixed(2)+'%':t?.state||'후속 관찰 대기'}`}).join(' · ');details.append(summary,p);host.append(details);});
  } catch(e){host.textContent=e.message;}
}
