import unittest
from engine import evaluate_document
from test_engine import make_bars, document


class PartialHistoryTests(unittest.TestCase):
    def test_single_bar_is_visible_without_fake_long_indicators(self):
        row=evaluate_document(document(make_bars(1)))['results'][0]
        self.assertEqual(row['status'],'ok')
        self.assertEqual(row['history_sessions'],1)
        self.assertEqual(len(row['charts']['monthly']),1)
        self.assertEqual(row['metrics']['atr_sessions'],1)
        for key in ('ema10','sma200','ATR14_pct','ret63_pct','high252','RVOL20_completed'):
            self.assertIsNone(row['metrics'][key])
        self.assertIsNone(row['quality'])

    def test_indicator_boundaries_are_independent(self):
        for n in (4,5,10,14,20,21,22,63,64,100,200,251,252):
            with self.subTest(n=n):
                m=evaluate_document(document(make_bars(n)))['results'][0]['metrics']
                self.assertEqual(m['ema10'] is not None,n>=10)
                self.assertEqual(m['ATR14_pct'] is not None,n>=14)
                self.assertEqual(m['ret63_pct'] is not None,n>=64)
                self.assertEqual(m['sma200'] is not None,n>=200)
                self.assertEqual(m['high252'] is not None,n>=252)

    def test_five_bar_setup_can_qualify_without_monthly_history(self):
        bars=make_bars(5,start=100,step=0)
        for b in bars[:2]:
            b.update(open=100,close=100,high=106,low=95,volume=2000000)
        for b in bars[2:4]:
            b.update(open=102,close=102,high=104,low=98,volume=1000000)
        bars[-1].update(open=102,close=103,high=104,low=99)
        row=evaluate_document(document(bars))['results'][0]
        self.assertEqual(row['status'],'ok')
        self.assertEqual(row['routes'],['SHORT'])
        self.assertIsNotNone(row['quality'])
        self.assertEqual(row['quality']['window_sessions'],2)
        self.assertEqual(row['quality']['trigger'],104)
        self.assertIsNone(row['quality']['checks'][2]['passed'])
        self.assertIsNone(row['quality']['checks'][3]['passed'])

    def test_recent_gap_keeps_three_valid_bars_without_bridging(self):
        bars=make_bars(260)
        bars[-4]['close']=None
        row=evaluate_document(document(bars))['results'][0]
        self.assertEqual(row['status'],'ok')
        self.assertEqual(row['history_sessions'],3)
        self.assertEqual(len(row['charts']['daily']),3)
        self.assertIsNone(row['metrics']['ema10'])
