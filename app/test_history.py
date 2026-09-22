import tempfile
import unittest
from pathlib import Path
from history import record_snapshot, coverage


class HistoryTests(unittest.TestCase):
    def test_same_session_observation_is_immutable(self):
        snapshot=dict(metadata=dict(as_of='2026-09-21',generated_at='2026-09-22T00:00:00Z',engine='v2',universe_requested=1,universe_valid=1),
                      results=[dict(symbol='TEST',status='ok',routes=['A'],metrics=dict(close=100))])
        with tempfile.TemporaryDirectory() as directory:
            first=record_snapshot(Path(directory),snapshot)
            snapshot['results'][0]['metrics']['close']=900
            second=record_snapshot(Path(directory),snapshot)
            self.assertEqual(first['records'],second['records'])
            self.assertEqual(second['records'][0]['candidates'][0]['close'],100)

    def test_forward_tracking_does_not_invent_same_day_returns(self):
        snapshot=dict(metadata=dict(as_of='2026-09-21',generated_at='2026-09-22T00:00:00Z',engine='v2',universe_requested=1,universe_valid=1),results=[dict(symbol='TEST',status='ok',routes=['A'],metrics=dict(close=100))])
        with tempfile.TemporaryDirectory() as directory:
            first=record_snapshot(directory,snapshot)
            self.assertIsNone(first['tracking'][0]['change_pct'])
            snapshot['metadata']['as_of']='2026-09-22'
            snapshot['results'][0]['metrics']['close']=90
            second=record_snapshot(directory,snapshot)
            self.assertAlmostEqual(second['tracking'][0]['change_pct'],-10)
            self.assertIsNone(second['tracking'][1]['change_pct'])

    def test_failure_groups_keep_unknown_denominator(self):
        rows=[dict(status='unknown',reasons=[reason]) for reason in
              ['stale data', 'HTTP Error 404', 'insufficient eligible history', 'unrecognized error']]
        rows.append(dict(status='ok',reasons=[]))
        self.assertEqual(sum(coverage(rows).values()),4)


if __name__=='__main__':
    unittest.main()
