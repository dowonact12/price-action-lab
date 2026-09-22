import copy
import unittest
from setup_quality import assess
from engine import evaluate_document
from test_engine import make_bars, document


class QualityTests(unittest.TestCase):
    def fixture(self):
        bars = make_bars(260, start=90, step=0)
        for b in bars[-21:-11]:
            b.update(high=110, low=90)
        for b in bars[-11:-1]:
            b.update(high=104, low=98, close=101, open=101, volume=500000)
        bars[-1].update(high=104, low=99, close=103, open=101)
        frames={key:[dict(close=n, boundary_unverified=False) for n in (90,95,99,103)] for key in ('weekly','monthly')}
        return bars, dict(close=103, ATR14_pct=3), frames

    def test_trigger_excludes_observation_bar_and_unknown_resistance_blocks_s(self):
        b,m,f=self.fixture()
        q=assess(b,m,f,['A'])
        self.assertEqual(q['trigger'],104)
        self.assertEqual(q['invalidation'],98)
        self.assertNotEqual(q['grade'],'S')
        b[-1]['high']=140
        self.assertEqual(assess(b,m,f,['A'])['trigger'],104)

    def test_broken_extended_and_missing_route_are_not_graded(self):
        b,m,f=self.fixture()
        self.assertIsNone(assess(b,m,f,[]))
        for close in (97,120):
            self.assertIsNone(assess(b,{**m,'close':close},f,['A']))

    def test_recovery_uses_same_plan_without_high_proximity_requirement(self):
        b,m,f=self.fixture()
        self.assertEqual(assess(b,m,f,['B'])['setup'],'회복 베이스')

    def test_future_bars_do_not_change_quality(self):
        b=make_bars()
        d=document(b)
        expected=evaluate_document(d)
        d=copy.deepcopy(d)
        d['symbols'][0]['bars'].append(dict(b[-1],date='2099-01-01',high=9999))
        self.assertEqual(evaluate_document(d),expected)
