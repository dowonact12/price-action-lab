"""Explicit research policy, not an author's formula or a calibrated probability."""
POLICY = 'setup-quality-v4'


def assess(history, metrics, frames, routes, warning=None):
    if not routes:
        return None
    # The observation bar cannot move its own trigger or invalidation line.
    prior = history[:-1]
    short = 'SHORT' in routes
    window = min(10, len(prior)//2) if short else 20 if 'B' in routes else 10
    if window < 2 or len(prior) < 2*window:
        return None
    recent, earlier, base = prior[-window:], prior[-2*window:-window], prior[-60:]
    trigger = max(b['high'] for b in recent)
    stop = min(b['low'] for b in recent)
    atr_pct = metrics.get('ATR14_pct')
    if atr_pct is None:
        atr_pct = metrics.get('ATR_observed_pct')
    if atr_pct is None:
        return None
    atr = metrics['close'] * atr_pct / 100
    risk = trigger - stop
    previous_range = max(b['high'] for b in earlier) - min(b['low'] for b in earlier)
    if atr <= 0 or risk <= 0 or previous_range <= 0:
        return None
    contraction = risk / previous_range
    earlier_volume = sum(b['volume'] for b in earlier)
    if earlier_volume <= 0:
        return None
    volume = sum(b['volume'] for b in recent) / earlier_volume
    base_high = max(b['high'] for b in base)
    depth = 100 * (base_high - min(b['low'] for b in base)) / base_high
    # Confirmed local highs, with two subsequent bars, from before the final contraction.
    peaks = [prior[i]['high'] for i in range(2, len(prior)-window)
             if prior[i]['high'] > trigger and
             all(prior[i]['high'] >= prior[j]['high'] for j in (i-2, i-1, i+1, i+2))]
    overhead = min(peaks) if peaks else None
    room = (overhead-trigger)/risk if overhead else None
    close = metrics['close']
    extension = min(atr, risk * .5)
    distance = (trigger-close)/atr
    # Hard gates prevent momentum alone, broken structures and chasing from grading.
    if not (.75 <= risk/atr <= 4 and risk/trigger <= .15 and
            contraction <= 1.2 and stop < close <= trigger+extension and
            distance <= 2 and (room is None or room >= 1)):
        return None
    def rising(key):
        bars = [b for b in frames[key] if not b.get('boundary_unverified')]
        return bars[-1]['close'] > bars[-4]['close'] if len(bars) >= 4 else None
    checks = [
        (f'최근 {window}봉 가격 범위 ≤ 이전 {window}봉의 75%', contraction <= .75),
        (f'최근 {window}봉 거래량 ≤ 이전 {window}봉의 80%', volume <= .8),
        ('확정 주봉 종가 > 3개 주봉 전', rising('weekly')),
        ('확정 월봉 종가 > 3개 월봉 전', rising('monthly')),
        ('역치까지 1 ATR 이내 · 돌파 후 0.25 ATR 이내', -.25 <= distance <= 1),
        ('확인된 과거 저항까지 2R 이상', room >= 2 if room is not None else None),
    ]
    known = [ok for _, ok in checks if ok is not None]
    count = sum(known)
    grade = 'S' if count == 6 and not warning else 'A' if len(known)>=4 and count/len(known)>=.8 else 'B' if len(known)>=3 and count/len(known)>=.5 else 'C'
    if len(history) < 21 and grade in ('S','A'):
        grade = 'B'
    return dict(policy=POLICY, grade=grade, rank={'S':4,'A':3,'B':2,'C':1}[grade],
                setup='단기 이력 수축' if short else '회복 베이스' if 'B' in routes else '리더 수축',
                evidence_count=len(known), total_checks=len(checks), history_sessions=len(history),
                volatility_sessions=min(14,len(history)), base_sessions=len(base),
                as_of=history[-1]['date'], level_as_of=prior[-1]['date'],
                window_start=recent[0]['date'], window_sessions=window,
                trigger=trigger, invalidation=stop, zone_low=trigger-min(.25*atr, .25*risk),
                structural_high=base_high if base_high > trigger else None,
                overhead=overhead, room_r=room, risk_pct=100*risk/trigger,
                risk_atr=risk/atr, distance_atr=distance, extension_limit=trigger+extension,
                contraction=contraction, volume_ratio=volume, base_depth_pct=depth,
                state='역치 상회 관찰' if close > trigger else '돌파 대기',
                checks=[dict(label=label, passed=ok) for label, ok in checks],
                note=f'관찰일 이전 확정 {window}봉 고가·저가로 산출한 새 계획. 등록된 추적 계획의 가격선은 별도로 고정 유지. 무효화는 일봉 종가 기준이며 실제 주문 손절을 지시하지 않음. 과거 저항 부재는 매물 부재를 뜻하지 않음.')
