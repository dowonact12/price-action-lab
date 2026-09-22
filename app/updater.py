"""Deterministic daily scanning and intraday polling; runs with the local server.

    python updater.py --symbols AAPL MSFT NVDA  # bounded connectivity check
    python updater.py --all                    # current listed universe, one run
"""
import argparse
import json
import gzip
import hashlib
import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path

from engine import evaluate_document, ENGINE_VERSION
from history import record_snapshot, coverage, failure_category
from market_data import NY, chart, daily_bars, intraday_quote, listed_symbols

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
LOCK = threading.Lock()


def read_saved(name, default=None):
    try:
        return json.loads((DATA / name).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return default


def save(name, payload):
    DATA.mkdir(exist_ok=True)
    path = DATA / name
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(',', ':')), encoding='utf-8')
    for attempt in range(6):
        try:
            os.replace(temporary, path)
            break
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.05 * (attempt + 1))


def utc_now():
    return datetime.now(timezone.utc)


def metadata(as_of):
    return dict(market='US', currency='USD', session='regular', adjustment_policy='split_adjusted_ohlcv', source='Yahoo chart · experimental personal research', as_of=as_of,
                adjustment_note='Provider split-adjusted OHLCV used as returned; no dividend adjustment, no independent corporate-action audit.', completeness_note='최신 일봉이 불완전하면 제외. 기준일 이후 가격은 확정 일봉 판정에 포함되지 않음.')


def update_daily(symbols=None, resume=False):
    now = utc_now()
    symbols = list(dict.fromkeys(symbols if symbols is not None else listed_symbols()))
    save('update-status.json', dict(state='collecting', started_at=now.isoformat(), requested=len(symbols), completed=0))
    # A reference session anchors stale-symbol detection; never let one stale stock set the date.
    reference_payload = chart('SPY', '1d', '1mo')
    reference = daily_bars(reference_payload, now)
    if not reference:
        raise ValueError('No completed reference session')
    as_of = reference[-1]['date']
    previous = read_saved('latest.json', {}) if resume else {}
    previous_rows = {r['symbol']: r for r in previous.get('results', [])} if previous.get('metadata', {}).get('as_of') == as_of and previous.get('metadata', {}).get('engine') == ENGINE_VERSION else {}
    observed_stamps = reference_payload.get('timestamp', [])
    observed_date = datetime.fromtimestamp(observed_stamps[-1], NY).date().isoformat() if observed_stamps else as_of
    results, failures = [], []

    def publish_progress(completed):
        valid_count = sum(r['status'] == 'ok' for r in results)
        snapshot = dict(metadata={**metadata(as_of), 'latest_observed_daily_date': observed_date, 'awaiting_daily_close': observed_date > as_of,
            'generated_at': utc_now().isoformat(), 'universe_requested': len(symbols), 'universe_completed': completed,
            'universe_pending': len(symbols)-completed, 'universe_valid': valid_count, 'universe_label': '미국 거래소 상장 목록 · ETF 포함 · OTC 제외',
            'failures': failures, 'failure_categories': coverage(results), 'engine': ENGINE_VERSION, 'min_turnover': 10_000_000, 'min_adr': 3}, results=sorted(results, key=lambda r:r['symbol']))
        if valid_count:
            save('latest.json', snapshot)
        return snapshot

    def one(symbol):
        cache_id = hashlib.sha256((symbol+as_of).encode()).hexdigest()
        cached = read_saved('rows/' + cache_id + '.json')
        if cached and cached.get('engine_version') == ENGINE_VERSION and (cached.get('status') == 'ok' or resume):
            return cached
        if resume and symbol in previous_rows:
            return previous_rows[symbol]
        raw = chart(symbol, '1d', '10y')
        bars = daily_bars(raw, now)
        document = dict(metadata=metadata(as_of), symbols=[dict(symbol=symbol, bars=bars)])
        row = evaluate_document(document)['results'][0]
        row['engine_version'] = ENGINE_VERSION
        if row['status'] != 'ok':
            row['failure_category'] = failure_category(row)
        row['name'] = raw['meta'].get('longName', symbol)
        row['instrument'] = raw['meta'].get('instrumentType', 'UNKNOWN')
        if row['status'] == 'ok':
            try:
                row['_observed_quote'] = intraday_quote(raw, utc_now())
            except (KeyError, ValueError, TypeError):
                pass
            # Mechanical monitoring reference, not an inferred Jesse/Ian pivot.
            row['reference_high20'] = max(b['high'] for b in [b for b in bars if b['date'] <= as_of][-20:])
            charts = row.pop('charts')
            # Keep monthly context and sufficient weekly/daily detail without shipping
            # every raw bar in the market-wide index. Load each chart only on selection.
            charts['daily'] = charts['daily'][-252:]
            charts['weekly'] = charts['weekly'][-260:]
            for series in charts.values():
                for bar in series:
                    for key in ('open', 'high', 'low', 'close'):
                        bar[key] = round(bar[key], 4)
            row['chart_id'] = cache_id
            folder = DATA / 'charts'; folder.mkdir(parents=True, exist_ok=True)
            (folder / (cache_id+'.json.gz')).write_bytes(gzip.compress(json.dumps(dict(charts=charts), separators=(',', ':')).encode()))
        save('rows/' + cache_id + '.json', row)
        return row

    completed = 0
    with ThreadPoolExecutor(max_workers=16) as pool:
        jobs = {pool.submit(one, symbol): symbol for symbol in symbols}
        for job in as_completed(jobs):
            symbol = jobs[job]
            try:
                row = job.result()
                results.append(row)
                if row['status'] != 'ok':
                    failures.append(dict(symbol=symbol, error='; '.join(row['reasons'])))
            except Exception as exc:
                failures.append(dict(symbol=symbol, error=type(exc).__name__ + ': ' + str(exc)))
                results.append(dict(symbol=symbol, status='unknown', reasons=[str(exc)], routes=[], metrics={}))
            completed += 1
            if completed % 25 == 0 or completed == len(symbols):
                save('update-status.json', dict(state='collecting', started_at=now.isoformat(), requested=len(symbols), completed=completed, failures=len(failures)))
            if completed % 250 == 0:
                publish_progress(completed)
    valid = [r for r in results if r['status'] == 'ok']
    if not valid:
        raise ValueError('No valid symbols; previous snapshot retained')
    snapshot = publish_progress(len(symbols))
    save('history.json', record_snapshot(DATA, snapshot))
    observed = [monitor_row(row, row['_observed_quote']) for row in valid if row.get('_observed_quote')]
    save('intraday.json', dict(generated_at=utc_now().isoformat(), reference_as_of=as_of, watch_count=len(observed), universe_valid=len(valid), rows=observed, failures=[], note='일봉 수집 응답에 포함된 정규장 관측값. 종목별 시세 시각이 다르며 실시간 동시 스냅샷이 아님.'))
    save('update-status.json', dict(state='partial' if failures else 'ready', completed_at=utc_now().isoformat(), requested=len(symbols), valid=len(valid), failures=len(failures)))
    return snapshot


def monitor_row(row, quote):
    value, level = quote['price'], row.get('reference_high20')
    finite = lambda x: isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x > 0
    state = '가격 확인 불가'
    if finite(value) and finite(level):
        if not quote['market_open']:
            state = '정규장 종료/대기'
        elif not quote['current_session'] or quote['age_seconds'] > 180:
            state = '시세 지연 · 판정 보류'
        elif value > level:
            state = '최근 20일 고가 위'
        elif finite(quote['high']) and quote['high'] > level:
            state = '20일 고가 상회 후 되밀림'
        else:
            state = '최근 20일 고가 이하'
    return dict(symbol=row['symbol'], **quote, reference_high20=level, state=state,
                distance_pct=(value/level-1)*100 if finite(value) and finite(level) else None,
                reference_note='개발용 20일 고가. Jesse/Ian 피벗·진입·손절 판정 아님.')


def update_intraday(snapshot):
    started_at = utc_now()
    started = time.monotonic()
    # Rotate the entire valid universe; prioritise candidates without dropping others.
    valid = [r for r in snapshot['results'] if r['status'] == 'ok']
    watch = sorted(valid, key=lambda r: (not bool(r['routes']), r['symbol']))
    rows, failures = [], []
    def poll(row):
        quote = intraday_quote(chart(row['symbol'], '1m', '1d'), utc_now())
        return monitor_row(row, quote)
    with ThreadPoolExecutor(max_workers=16) as pool:
        jobs = {pool.submit(poll, row): row for row in watch}
        for future in as_completed(jobs):
            row = jobs[future]
            try:
                rows.append(future.result())
            except Exception as exc:
                failures.append(dict(symbol=row['symbol'], error=type(exc).__name__))
    payload = dict(generated_at=utc_now().isoformat(), started_at=started_at.isoformat(), batch_seconds=round(time.monotonic()-started, 1), successful_count=len(rows), reference_as_of=snapshot['metadata']['as_of'], poll_seconds=300, watch_count=len(watch), universe_valid=len(valid), rows=rows, failures=failures,
                   note='유효 종목 전체를 순환 조회. 무료 공급원 지연 보장 없음. 전체 1회 처리시간에 따라 갱신 간격이 늘어남.')
    save('intraday.json', payload)
    return payload


def run_cycle(symbols=None, force_daily=False, daily_only=False):
    if not LOCK.acquire(blocking=False):
        return
    try:
        settings = read_saved('universe.json', {})
        symbols = symbols or settings.get('symbols') or listed_symbols()
        snapshot = read_saved('latest.json')
        now = utc_now().astimezone(NY)
        # Refresh after 16:30 ET, including startup recovery. Holidays can retry once/day.
        refresh_date = read_saved('last-daily-attempt.json', {}).get('date')
        if force_daily or snapshot is None or (now.hour*60+now.minute >= 990 and (refresh_date != now.date().isoformat() or snapshot['metadata'].get('awaiting_daily_close'))):
            try:
                if settings.get('mode') == 'all':
                    symbols = listed_symbols()
                    save('universe.json', dict(mode='all', symbols=symbols))
                snapshot = update_daily(symbols)
                if not snapshot['metadata'].get('awaiting_daily_close'):
                    save('last-daily-attempt.json', dict(date=now.date().isoformat()))
            except Exception as exc:
                save('update-status.json', dict(state='failed', failed_at=utc_now().isoformat(), error=type(exc).__name__ + ': ' + str(exc), previous_snapshot_retained=True))
                if snapshot is None:
                    return
        if not daily_only:
            update_intraday(snapshot)
    except Exception as exc:
        save('update-status.json', dict(state='failed', failed_at=utc_now().isoformat(), error=type(exc).__name__ + ': ' + str(exc), previous_snapshot_retained=True))
    finally:
        LOCK.release()


def serve_updates():
    first = True
    while True:
        started = time.monotonic()
        run_cycle(force_daily=first)
        first = False
        # Regular hours: 300s between batch starts. Closed: 15m to detect the next session.
        local = utc_now().astimezone(NY)
        if local.weekday() < 5 and 570 <= local.hour*60+local.minute < 960:
            delay = max(1, 300 - (time.monotonic()-started))
        else:
            next_open = local.replace(hour=9, minute=30, second=0, microsecond=0)
            if next_open <= local:
                next_open += timedelta(days=1)
            delay = min(900, max(1, (next_open-local).total_seconds()))
        time.sleep(delay)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--symbols', nargs='+')
    group.add_argument('--all', action='store_true')
    parser.add_argument('--daily-only', action='store_true')
    args = parser.parse_args()
    symbols = args.symbols if args.symbols else listed_symbols()
    save('universe.json', dict(mode='selected' if args.symbols else 'all', symbols=symbols))
    run_cycle(symbols, force_daily=True, daily_only=args.daily_only)
    print(json.dumps(read_saved('update-status.json'), ensure_ascii=False))
