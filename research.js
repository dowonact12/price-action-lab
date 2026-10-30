/* Deterministic explanations. Thresholds are ours; source links describe principles. */
function showResearch(row, metadata) {
  const host=document.getElementById('research');host.replaceChildren();
  const add=(tag,text,parent=host)=>{const el=document.createElement(tag);el.textContent=text;parent.append(el);return el;};
  const q=row.quality;
  add('h3',`보유 이력 ${row.history_sessions??'—'}봉 · 가능한 지표만 평가`);
  const m=row.metrics||{},nf=v=>Number.isFinite(v)?v.toFixed(2):'계산 불가';
  add('p',`보유 기간 ${m.average_sessions??'—'}봉 평균 거래대금 $${nf(m.turnover_observed)} · 평균 가격 범위 ${nf(m.ADR_observed_pct)}% · ${m.atr_sessions??'—'}봉 변동폭 ${nf(m.ATR_observed_pct)}%`);
  const metricNames={ema10:'10일 EMA',ema20:'20일 EMA',ema50:'50일 EMA',ema100:'100일 EMA',sma200:'200일 SMA',high252:'252봉 고점',low252:'252봉 저점',offHigh252_pct:'252봉 고점 대비',aboveLow252_pct:'252봉 저점 대비',ret21_pct:'21거래일 수익률',ret63_pct:'63거래일 수익률',ret126_pct:'126거래일 수익률',ADR20_pct:'20봉 ADR',ATR14_pct:'14봉 ATR',RVOL20_completed:'20봉 비교 거래량',turnover20:'20봉 평균 거래대금',rangeRatio5:'5봉 가격 범위비',volumeRatio5:'5봉 거래량비'};
  if(row.unavailable_metrics?.length)add('p','이력 또는 계산 분모 부족 · '+row.unavailable_metrics.map(k=>metricNames[k]||k).join(', '));
  if(row.history_warning)add('p',row.history_warning.note);
  if(!q){add('p','현재 등급 없음 · '+((row.reasons||[]).join(' · ')||'가격 구조·역치·위험 폭의 필수 조건 미충족'));return;}
  add('h3',`${q.grade} · ${q.setup} · 자리의 질`);
  add('p',`기준 ${q.as_of} · 가격선 계산 종료 ${q.level_as_of} · ${q.policy}`);
  add('p','자체 정량화 연구 기준입니다. Jesse/Ian 원본 공식 또는 검증된 승률이 아닙니다. 리더·회복·단기 이력 수축을 구분하며 모든 셋업을 포괄하지 않습니다.').className='warning';
  const f=v=>Number.isFinite(v)?v.toFixed(2):'미확인';
  add('p',`실행 역치 $${f(q.trigger)} / 일봉 종가 무효화 $${f(q.invalidation)} / 추격 제외선 $${f(q.extension_limit)}`);
  add('p',`${q.base_sessions??60}봉 구조 고점 $${f(q.structural_high)} / 과거 확인 저항 $${f(q.overhead)} / 저항 여유 ${f(q.room_r)}R`);
  add('p',`위험 폭 ${f(q.risk_pct)}% · ${f(q.risk_atr)} ATR / 역치 거리 ${f(q.distance_atr)} ATR / 범위비 ${f(q.contraction)} / 거래량비 ${f(q.volume_ratio)}`);
  q.checks.forEach(c=>add('p',`${c.passed===null?'평가 불가':c.passed?'충족':'미충족'} · ${c.label}`));
  add('p','필수: 위험 폭 0.75–4 ATR 및 역치의 15% 이하, 범위비 ≤1.2, 역치까지 ≤2 ATR, 알려진 저항 여유 ≥1R. 추격 한도=역치+min(1 ATR, 0.5R). 평가 불가 항목은 미충족으로 세지 않습니다. S=6항목 전부·이력 경고 없음, A=평가 가능 4개 이상·80% 충족, B=평가 가능 3개 이상·50% 충족, C=나머지 필수 통과. 21봉 미만은 잠정 등급으로 최대 B.');
  add('p','미충족 항목이 상위 등급 확인 조건입니다. 저항 미확인은 통과로 계산하지 않습니다. 상대강도 백분위·뉴스·호가 검증은 아직 포함하지 않습니다.');
  add('p',`평가 가능 ${q.evidence_count}/${q.total_checks}항목 · 변동폭 산출 ${q.volatility_sessions}봉. 짧은 이력을 장기 지표로 간주하지 않습니다.`);
  add('p',q.note);
  const plan=row.tracked_plan;
  if(plan){
    add('h3','등록 당시 가격선 · 고정 추적');
    add('p',`${plan.registered_as_of} 등록 · ${plan.label} · ${plan.data_status}`);
    add('p',`고정 역치 $${f(plan.trigger)} / 재접촉 구간 $${f(plan.zone_low)}–${f(plan.trigger)} / 종가 무효화 $${f(plan.invalidation)}. 위의 새 후보 계산값과 구분합니다.`);
  }
}

async function showPlans(snapshotMode){
  const host=document.getElementById('plan-content');
  try{
    const response=await fetch(snapshotMode?'data/plans.json':'/api/plans',{cache:'no-store'});
    if(!response.ok)throw Error('아직 등록된 추적 계획이 없습니다.');
    const data=await response.json();host.replaceChildren();
    if(!data.plans.length){host.textContent='아직 등록된 추적 계획이 없습니다.';return;}
    [...data.plans].reverse().forEach(plan=>{
      const details=document.createElement('details'),summary=document.createElement('summary'),body=document.createElement('p');
      summary.textContent=`${plan.symbol} · ${plan.label} · 등록 ${plan.registered_as_of}`;
      body.textContent=`등록 등급 ${plan.grade} / ${plan.setup} · 역치 ${plan.trigger.toFixed(2)} · 지지구간 하단 ${plan.zone_low.toFixed(2)} · 무효화 ${plan.invalidation.toFixed(2)} · ${plan.data_status}`;
      details.append(summary,body);
      const events=document.createElement('p');events.textContent=plan.events.length?plan.events.map(e=>`${e.as_of}: ${e.label} (종가 ${e.close.toFixed(2)})`).join(' → '):'등록 이후 발생한 확정 이벤트 없음. 과거 돌파를 소급해서 기록하지 않습니다.';
      details.append(events);host.append(details);
    });
  }catch(error){host.textContent=error.message;}
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
      p.textContent=`최초 관찰 ${record.observed_at} — `+record.candidates.map(r=>{const t=(data.tracking||[]).find(t=>t.symbol===r.symbol&&t.observed_as_of===record.as_of&&t.rule_version===record.rule_version);return `${r.symbol} (${r.quality ? '등급 '+r.quality.grade : '이전 연구 경로 '+r.routes.join('+')}, $${r.close.toFixed(2)}) ${Number.isFinite(t?.change_pct)?t.change_pct.toFixed(2)+'%':t?.state||'후속 관찰 대기'}`}).join(' · ');details.append(summary,p);host.append(details);});
  } catch(e){host.textContent=e.message;}
}
