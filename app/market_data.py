"""Experimental, keyless Yahoo chart reader for personal research. No LLM calls."""
import csv
import io
import json
import math
import re
from datetime import datetime, timezone
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

NY = ZoneInfo('America/New_York')


def read_url(url):
    with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=25) as response:
        return response.read().decode('utf-8')


def listed_symbols():
    """Current US exchange directory including ETFs; exclude test issues.

    Unsupported symbol spellings are retained and reported as provider failures.
    OTC securities are not covered by these exchange directories.
    """
    symbols = set()
    for filename, column in [('nasdaqlisted.txt', 'Symbol'), ('otherlisted.txt', 'ACT Symbol')]:
        rows = csv.DictReader(io.StringIO(read_url('https://www.nasdaqtrader.com/dynamic/SymDir/' + filename)), delimiter='|')
        for row in rows:
            name, symbol = row.get('Security Name', ''), row.get(column, '')
            if row.get('Test Issue') != 'N':
                continue
            if symbol:
                symbols.add(symbol.replace('.', '-'))
    if not symbols:
        raise ValueError('Empty symbol directory')
    return sorted(symbols)


def chart(symbol, interval, period):
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol, safe="")}?range={period}&interval={interval}&includePrePost=false&events=splits'
    payload = json.loads(read_url(url))['chart']
    if payload.get('error') or not payload.get('result'):
        raise ValueError('Provider returned no chart')
    return payload['result'][0]


def daily_bars(payload, now):
    meta = payload['meta']
    if meta.get('currency') != 'USD' or meta.get('instrumentType') not in ('EQUITY', 'ETF') or meta.get('exchangeTimezoneName') != 'America/New_York':
        raise ValueError('Not a supported US USD instrument')
    values = payload['indicators']['quote'][0]
    bars = []
    for i, stamp in enumerate(payload.get('timestamp', [])):
        day = datetime.fromtimestamp(stamp, NY)
        # Wait until 16:30 ET even on early-close days. Never certify an intraday bar.
        cutoff = day.replace(hour=16, minute=30, second=0, microsecond=0)
        if now < cutoff:
            continue
        bars.append(dict(date=day.date().isoformat(), **{key: values[key][i] for key in ('open', 'high', 'low', 'close', 'volume')}))
    # An incomplete trailing provider bar is not a confirmed close. Historical gaps
    # remain in place so engine validation rejects them rather than concealing them.
    while bars and any(not isinstance(bars[-1][k], (int, float)) or not math.isfinite(bars[-1][k]) for k in ('open', 'high', 'low', 'close', 'volume')):
        bars.pop()
    return bars


def intraday_quote(payload, now):
    meta = payload['meta']
    if meta.get('currency') != 'USD':
        raise ValueError('Not USD')
    period = meta['currentTradingPeriod']['regular']
    stamp = meta.get('regularMarketTime')
    if not isinstance(stamp, (int, float)):
        raise ValueError('Quote timestamp missing')
    active = period['start'] <= now.timestamp() < period['end']
    same_session = datetime.fromtimestamp(stamp, NY).date() == now.astimezone(NY).date()
    return dict(price=meta.get('regularMarketPrice'), high=meta.get('regularMarketDayHigh'), low=meta.get('regularMarketDayLow'), volume=meta.get('regularMarketVolume'),
                quote_at=datetime.fromtimestamp(stamp, timezone.utc).isoformat(), age_seconds=max(0, int(now.timestamp()-stamp)),
                market_open=active, current_session=same_session, provider_delay='not_certified', session_date=datetime.fromtimestamp(stamp, NY).date().isoformat())
