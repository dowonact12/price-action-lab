"""Forward-only candidate observations, not simulated executions or backtests."""
import json
from collections import Counter
from pathlib import Path


def failure_category(row):
    reason = ' '.join(row.get('reasons', [])).lower()
    if 'insufficient' in reason or '504 required' in reason:
        return '이력 부족 / 오류 이후 워밍업 부족'
    if 'stale data' in reason:
        return '기준일 불일치'
    if any(x in reason for x in ('http', 'timeout', 'timed out', 'not found', 'no chart', 'urlopen')):
        return '공급원 응답 실패'
    if any(x in reason for x in ('instrument', 'currency', 'timezone')):
        return '지원 범위 밖'
    if any(x in reason for x in ('volume', 'finite', 'inconsistent', 'denominator', 'duplicate')):
        return '가격·거래량 검증 실패'
    return '기타 / 원인 확인 필요'


def record_snapshot(data, snapshot):
    """Keep the first completed observation per session AND rule version immutable."""
    folder = Path(data) / 'history'
    folder.mkdir(parents=True, exist_ok=True)
    meta = snapshot['metadata']
    version = meta.get('engine', 'legacy-v1')
    filename = meta['as_of'] + '-' + version + '.json'
    path = folder / filename
    record = dict(as_of=meta['as_of'], observed_at=meta['generated_at'], rule_version=version,
                  requested=meta['universe_requested'], valid=meta['universe_valid'],
                  candidates=[dict(symbol=r['symbol'], routes=r['routes'], quality=r.get('quality'), close=r['metrics']['close'])
                              for r in snapshot['results'] if r['status']=='ok' and (r.get('quality') if version in ('us_daily_research_v3', 'us_daily_research_v4') else r['routes'])])
    try:
        with path.open('x', encoding='utf-8') as stream:
            json.dump(record, stream, ensure_ascii=False, allow_nan=False)
    except FileExistsError:
        pass
    records = [json.loads(p.read_text(encoding='utf-8')) for p in sorted(folder.glob('*.json'))]
    current={r['symbol']:r for r in snapshot['results'] if r['status']=='ok'}
    tracking=[]
    for record in records:
        for candidate in record['candidates']:
            row=current.get(candidate['symbol'])
            later=meta['as_of']>record['as_of']
            value=row['metrics']['close'] if row and later else None
            tracking.append(dict(symbol=candidate['symbol'],observed_as_of=record['as_of'],
                observed_at=record['observed_at'],rule_version=record['rule_version'],
                observed_close=candidate['close'],latest_as_of=meta['as_of'],latest_close=value,
                change_pct=100*(value/candidate['close']-1) if value is not None else None,
                state='후속 가격 관찰' if value is not None else ('후속 거래일 대기' if not later else '현재 가격 미확인')))
    return dict(records=records, tracking=tracking, note='최초 완결 수집 이후 관찰 기록. 등락률은 관찰 당시 종가 대비 후속 종가이며 매매 수익률·체결·승률이 아님. 가격 조정 변경은 별도 검증되지 않음.')


def coverage(results):
    return dict(Counter(failure_category(r) for r in results if r['status'] != 'ok'))
