import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from market_data import NY, daily_bars, intraday_quote
import updater


class MarketTests(unittest.TestCase):
    def test_transient_windows_reader_lock_retries_atomic_save(self):
        real_replace=updater.os.replace
        calls=[]
        def replace(source,target):
            calls.append(1)
            if len(calls)==1:
                raise PermissionError('reader holds destination')
            return real_replace(source,target)
        with tempfile.TemporaryDirectory() as folder, patch.object(updater,'DATA',Path(folder)), patch.object(updater.os,'replace',side_effect=replace), patch.object(updater.time,'sleep'):
            updater.save('test.json',{'complete':True})
            self.assertEqual(updater.read_saved('test.json'),{'complete':True})
            self.assertEqual(len(calls),2)

    def payload(self):
        stamp = int(datetime(2026, 9, 21, 9, 30, tzinfo=NY).timestamp())
        return dict(meta=dict(currency='USD', instrumentType='EQUITY', exchangeTimezoneName='America/New_York', regularMarketTime=stamp+60, regularMarketPrice=101,
                    currentTradingPeriod=dict(regular=dict(start=stamp, end=stamp+23400))), timestamp=[stamp],
                    indicators=dict(quote=[dict(open=[100], high=[102], low=[99], close=[101], volume=[10])]))

    def test_unfinished_daily_is_excluded_until_1630(self):
        self.assertEqual(daily_bars(self.payload(), datetime(2026, 9, 21, 16, 29, tzinfo=NY)), [])
        self.assertEqual(daily_bars(self.payload(), datetime(2026, 9, 21, 16, 30, tzinfo=NY))[0]['close'], 101)

    def test_missing_trailing_close_is_not_fabricated(self):
        p = self.payload(); p['indicators']['quote'][0]['close'] = [None]
        self.assertEqual(daily_bars(p, datetime(2026, 9, 22, tzinfo=NY)), [])

    def test_session_and_quote_age(self):
        p = self.payload()
        live = intraday_quote(p, datetime(2026, 9, 21, 9, 32, tzinfo=NY))
        self.assertTrue(live['market_open']); self.assertTrue(live['current_session']); self.assertEqual(live['age_seconds'], 60)
        after = intraday_quote(p, datetime(2026, 9, 21, 16, 1, tzinfo=NY))
        self.assertFalse(after['market_open'])

    def test_stale_and_closed_quotes_do_not_signal(self):
        quote = dict(price=101, high=103, market_open=True, current_session=True, age_seconds=181)
        row = dict(symbol='TEST', reference_high20=100)
        self.assertIn('보류', updater.monitor_row(row, quote)['state'])
        quote.update(age_seconds=20)
        self.assertEqual(updater.monitor_row(row, quote)['state'], '최근 20일 고가 위')
        quote.update(price=99)
        self.assertIn('되밀림', updater.monitor_row(row, quote)['state'])
        quote.update(market_open=False)
        self.assertEqual(updater.monitor_row(row, quote)['state'], '정규장 종료/대기')

    def test_failed_refresh_preserves_last_snapshot(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(updater, 'DATA', Path(folder)), patch.object(updater, 'chart', side_effect=ValueError('source unavailable')), patch.object(updater, 'update_intraday') as intraday:
            previous = dict(metadata=dict(as_of='2026-09-18'), results=[])
            updater.save('latest.json', previous)
            updater.run_cycle(['AAPL'], force_daily=True)
            self.assertEqual(updater.read_saved('latest.json'), previous)
            self.assertEqual(updater.read_saved('update-status.json')['state'], 'failed')
            intraday.assert_called_once_with(previous)

    def test_reference_high_does_not_include_future_bars(self):
        sample = json.loads(Path(__file__).with_name('example-data.json').read_text(encoding='utf-8-sig'))
        bars = sample['symbols'][0]['bars']
        future = dict(bars[-1], date='2026-08-14', high=10000)
        with tempfile.TemporaryDirectory() as folder, patch.object(updater, 'DATA', Path(folder)), patch.object(updater, 'chart', return_value={'meta': {}}), patch.object(updater, 'daily_bars', side_effect=[bars, bars+[future]]):
            snapshot = updater.update_daily(['TEST'])
            self.assertEqual(snapshot['results'][0]['reference_high20'], max(b['high'] for b in bars[-20:]))
            self.assertNotIn('charts', snapshot['results'][0])
            self.assertTrue((Path(folder)/'charts'/(snapshot['results'][0]['chart_id']+'.json.gz')).exists())

    def test_intraday_covers_more_than_fifty_symbols(self):
        rows = [dict(symbol=f'TEST{i}', status='ok', routes=[], reference_high20=100) for i in range(57)]
        quote = dict(price=101, high=102, market_open=False, current_session=True, age_seconds=10)
        with tempfile.TemporaryDirectory() as folder, patch.object(updater, 'DATA', Path(folder)), patch.object(updater, 'chart', return_value={}), patch.object(updater, 'intraday_quote', return_value=quote):
            result = updater.update_intraday(dict(metadata=dict(as_of='2026-09-18'), results=rows))
            self.assertEqual(result['watch_count'], 57)
            self.assertEqual(len(result['rows']), 57)
            self.assertFalse(result['failures'])
