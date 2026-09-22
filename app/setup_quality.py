"""Explicit research policy, not an author's formula or a calibrated probability."""
POLICY = 'setup-quality-v2'


def assess(history, metrics, frames, routes, warning=None):
    if not routes:
        return None
    # The observation bar cannot move its own trigger or invalidation line.
    prior = history[:-1]
    recent, earlier, base = prior[-10:], prior[-20:-10], prior[-60:]
    trigger = max(b['high'] for b in recent)
    stop = min(b['low'] for b in recent)
    atr = metrics['close'] * metrics['ATR14_pct'] / 100
    risk = trigger - stop
    previous_range = max(b['high'] for b in earlier) - min(b['low'] for b in earlier)
    if atr <= 0 or risk <= 0 or previous_range <= 0:
        return None
    contraction = risk / previous_range
    volume = sum(b['volume'] for b in recent) / sum(b['volume'] for b in earlier)
    base_high = max(b['high'] for b in base)
    depth = 100 * (base_high - min(b['low'] for b in base)) / base_high
    # Confirmed local highs, with two subsequent bars, from before the final contraction.
    peaks = [prior[i]['high'] for i in range(2, len(prior)-10)
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
        return len(bars) >= 4 and bars[-1]['close'] > bars[-4]['close']
    checks = [
        ('최근 10봉 가격 범위 ≤ 이전 10봉의 75%', contraction <= .75),
        ('최근 10봉 거래량 ≤ 이전 10봉의 80%', volume <= .8),
        ('확정 주봉 종가 > 3개 주봉 전', rising('weekly')),
        ('확정 월봉 종가 > 3개 월봉 전', rising('monthly')),
        ('역치까지 1 ATR 이내 · 돌파 후 0.25 ATR 이내', -.25 <= distance <= 1),
        ('확인된 과거 저항까지 2R 이상', room is not None and room >= 2),
    ]
    count = sum(ok for _, ok in checks)
    grade = 'S' if count == 6 and not warning else 'A' if count >= 5 else 'B' if count >= 3 else 'C'
    return dict(policy=POLICY, grade=grade, rank={'S':4,'A':3,'B':2,'C':1}[grade],
                setup='회복 베이스' if 'B' in routes else '리더 수축',
                as_of=history[-1]['date'], level_as_of=prior[-1]['date'],
                window_start=recent[0]['date'], trigger=trigger, invalidation=stop,
                structural_high=base_high if base_high > trigger else None,
                overhead=overhead, room_r=room, risk_pct=100*risk/trigger,
                risk_atr=risk/atr, distance_atr=distance, extension_limit=trigger+extension,
                contraction=contraction, volume_ratio=volume, base_depth_pct=depth,
                state='역치 상회 관찰' if close > trigger else '돌파 대기',
                checks=[dict(label=label, passed=ok) for label, ok in checks],
                note='전일 확정 10봉 고가·저가로 산출한 일일 연구 계획. 일봉 종가가 무효화선 이하이면 탈락. 매일 별도 재산출하며 기존 포지션의 손절선을 변경하는 지시가 아님. 과거 저항 부재는 매물 부재를 뜻하지 않음.')
