"""Forward-only daily-close observations of immutable registered price plans."""
from copy import deepcopy
import hashlib

LABELS = {'registered':'돌파 대기', 'above_at_registration':'역치 위에서 등록 · 재접근 대기',
          'broken_out':'종가 돌파', 'retested':'돌파 후 지지구간 재접촉',
          'inside_zone':'역치 구간 안', 'below_zone':'역치 구간 이탈',
          'reclaimed':'구간 이탈 후 회복', 'rebroken':'구간 안에서 재돌파',
          'invalidated':'종가 무효화 · 추적 종료'}


def register(symbol, quality, close, observed_at):
    identity = f"{symbol}|{quality['as_of']}|{quality['policy']}|{quality['trigger']}|{quality['invalidation']}"
    state = 'above_at_registration' if close > quality['trigger'] else 'registered'
    return dict(id=hashlib.sha256(identity.encode()).hexdigest()[:20], symbol=symbol,
                registered_at=observed_at, registered_as_of=quality['as_of'],
                policy=quality['policy'], grade=quality['grade'], setup=quality['setup'],
                trigger=quality['trigger'], zone_low=quality['zone_low'],
                invalidation=quality['invalidation'], last_as_of=quality['as_of'],
                last_close=close, state=state, label=LABELS[state], armed=close <= quality['trigger'],
                broken=False, below_seen=False, events=[], data_status='후속 확정 일봉 대기')


def advance(plan, bars, as_of, observed_at):
    result = deepcopy(plan)
    if result['state'] == 'invalidated':
        return result
    ordered = sorted((b for b in bars if b['date'] <= as_of), key=lambda b:b['date'])
    anchor = next((b for b in ordered if b['date'] == result['last_as_of']), None)
    if anchor is None:
        result['data_status'] = '연속 이력 확인 불가 · 추적 보류'
        return result
    # Split/revision changes must not silently compare against old price levels.
    if abs(anchor['close'] / result['last_close'] - 1) > .0001:
        result['data_status'] = '과거 가격 수정 감지 · 추적 보류'
        return result
    for bar in ordered:
        if bar['date'] <= result['last_as_of']:
            continue
        close, previous = bar['close'], result['last_close']
        state, trigger, low = result['state'], result['trigger'], result['zone_low']
        if close <= result['invalidation']:
            state = 'invalidated'
        elif result['broken']:
            if close < low:
                state = 'below_zone'
                result['below_seen'] = True
            elif close > trigger and result['below_seen']:
                state = 'reclaimed'
                result['below_seen'] = False
            elif close > trigger and previous <= trigger:
                state = 'rebroken'
            elif close > trigger and bar['low'] <= trigger and bar['high'] >= low:
                state = 'retested'
            elif close <= trigger:
                state = 'inside_zone'
        elif result['armed'] and previous <= trigger < close:
            state = 'broken_out'
            result['broken'] = True
        elif close <= trigger:
            result['armed'] = True
            state = 'registered'
        if state != result['state']:
            result['events'].append(dict(state=state, label=LABELS[state], as_of=bar['date'],
                                         observed_at=observed_at, close=close))
        result.update(state=state, label=LABELS[state], last_as_of=bar['date'], last_close=close)
        if state == 'invalidated':
            break
    result['data_status'] = '최신 확정 일봉 확인' if result['last_as_of'] == as_of else '추적 종료' if result['state']=='invalidated' else '후속 일봉 미확인'
    return result


def update_plans(previous, rows, as_of, observed_at, load_bars):
    plans = deepcopy(previous.get('plans', []))
    by_symbol = {r['symbol']:r for r in rows}
    for i, plan in enumerate(plans):
        if plan['state'] == 'invalidated':
            continue
        row = by_symbol.get(plan['symbol'])
        if row and row['status'] == 'ok':
            plans[i] = advance(plan, load_bars(row), as_of, observed_at)
        else:
            plans[i]['data_status'] = '당일 데이터 판정 불가 · 기존 가격선 유지'
    for row in rows:
        relevant = [p for p in plans if p['symbol'] == row['symbol']]
        latest = relevant[-1] if relevant else None
        # No resurrection or same-session replacement of an invalidated hypothesis.
        if row.get('quality') and (latest is None or
                (latest['state']=='invalidated' and latest['last_as_of'] < as_of)):
            latest = register(row['symbol'], row['quality'], row['metrics']['close'], observed_at)
            plans.append(latest)
        if latest:
            row['tracked_plan'] = latest
    return dict(plans=plans, as_of=as_of, observed_at=observed_at,
                note='등록 이후 확정 일봉만 추적. 가격선 고정, 무효화 후 같은 계획은 되살리지 않음. 체결·승률 기록이 아님. 장중 시세는 별도의 관측값.')
