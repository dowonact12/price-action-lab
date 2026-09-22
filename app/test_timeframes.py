import unittest
from timeframes import chart_timeframes


class TimeframeTests(unittest.TestCase):
    def test_ohlcv_and_iso_week_year_boundary(self):
        bars = [dict(date=d, open=o, high=h, low=l, close=c, volume=v) for d, o, h, l, c, v in [
            ('2021-01-04', 15, 18, 14, 17, 30),
            ('2020-12-31', 10, 14, 9, 13, 10),
            ('2021-01-01', 13, 16, 11, 15, 20),
            ('2021-02-01', 17, 20, 16, 19, 40)]]
        result = chart_timeframes(bars, '2021-01-04')
        weekly = result['weekly']
        self.assertEqual(len(weekly), 2)
        self.assertEqual([weekly[0][k] for k in ('open', 'high', 'low', 'close', 'volume', 'sessions')], [10, 16, 9, 15, 30, 2])
        self.assertEqual(len(result['monthly']), 2)
        self.assertEqual(result['monthly'][1]['volume'], 50)
        self.assertEqual(len(result['daily']), 3)
        self.assertTrue(all(b['boundary_unverified'] for b in weekly))
        self.assertFalse(any(b['boundary_unverified'] for b in result['daily']))

    def test_empty_and_single_period(self):
        self.assertEqual(chart_timeframes([], '2026-01-01'), dict(monthly=[], weekly=[], daily=[]))
        bar = dict(date='2026-01-01', open=1, high=1, low=1, close=1, volume=5)
        result = chart_timeframes([bar], '2026-01-01')
        self.assertTrue(result['monthly'][0]['boundary_unverified'])
        self.assertEqual(result['weekly'][0]['sessions'], 1)
