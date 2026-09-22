import unittest
from plan_tracking import register, advance, update_plans


class PlanTests(unittest.TestCase):
    def quality(self):
        return dict(as_of='2026-09-01',policy='test',grade='A',setup='리더 수축',trigger=100,zone_low=98,invalidation=90)

    def bar(self, day, close, low=None):
        return dict(date=f'2026-09-{day:02}',close=close,low=close-1 if low is None else low,high=close+1)

    def test_forward_path_and_terminal_invalidation(self):
        plan=register('TEST',self.quality(),99,'registered')
        bars=[self.bar(1,99),self.bar(2,102),self.bar(3,101,99),self.bar(4,97),self.bar(5,99),self.bar(6,102),self.bar(7,89),self.bar(8,105)]
        final=advance(plan,bars,'2026-09-08','observed')
        self.assertEqual([e['state'] for e in final['events']],['broken_out','retested','below_zone','inside_zone','reclaimed','invalidated'])
        self.assertEqual(final['last_as_of'],'2026-09-07')
        self.assertEqual(final['trigger'],100)
        self.assertEqual(final,advance(final,bars,'2026-09-08','again'))

    def test_above_at_registration_requires_a_new_cross(self):
        plan=register('TEST',self.quality(),101,'registered')
        bars=[self.bar(1,101),self.bar(2,103)]
        p=advance(plan,bars,'2026-09-02','observed')
        self.assertFalse(p['events'])
        p=advance(p,bars+[self.bar(3,99),self.bar(4,102)],'2026-09-04','observed')
        self.assertEqual(p['state'],'broken_out')

    def test_idempotency_future_exclusion_and_price_revision(self):
        plan=register('TEST',self.quality(),99,'registered')
        bars=[self.bar(1,99),self.bar(2,102),self.bar(3,80)]
        p=advance(plan,bars,'2026-09-02','observed')
        self.assertEqual(p['state'],'broken_out')
        self.assertEqual(p,advance(p,bars,'2026-09-02','again'))
        revised=advance(p,[self.bar(2,51),self.bar(3,53)],'2026-09-03','later')
        self.assertIn('가격 수정',revised['data_status'])
        self.assertEqual(revised['last_as_of'],p['last_as_of'])

    def test_registration_does_not_replay_history_or_move_levels(self):
        row=dict(symbol='TEST',status='ok',quality=self.quality(),metrics=dict(close=99))
        saved=update_plans({},[row],'2026-09-01','first',lambda _:[])
        self.assertFalse(saved['plans'][0]['events'])
        row['quality']['trigger']=110
        again=update_plans(saved,[row],'2026-09-01','second',lambda _:[self.bar(1,99)])
        self.assertEqual(len(again['plans']),1)
        self.assertEqual(again['plans'][0]['trigger'],100)

    def test_unknown_preserves_registered_plan(self):
        p=register('TEST',self.quality(),99,'registered')
        result=update_plans({'plans':[p]},[dict(symbol='TEST',status='unknown')],'2026-09-02','later',lambda _:[])
        self.assertEqual(result['plans'][0]['trigger'],100)
        self.assertIn('판정 불가',result['plans'][0]['data_status'])
