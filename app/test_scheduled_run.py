import unittest
from datetime import datetime
from unittest.mock import patch
import scheduled_run
from market_data import NY


class ScheduleTests(unittest.TestCase):
    def test_closed_session_without_daily_refresh_does_not_publish(self):
        with patch.object(scheduled_run,'datetime') as clock, patch.object(scheduled_run,'read_saved',return_value={'metadata':{}}), patch.object(scheduled_run,'build') as build:
            clock.now.return_value=datetime(2026,9,22,8,0,tzinfo=NY)
            self.assertFalse(scheduled_run.run())
            build.assert_not_called()

    def test_failed_intraday_batch_does_not_publish(self):
        with patch.object(scheduled_run,'datetime') as clock, patch.object(scheduled_run,'read_saved',return_value={'metadata':{}}), patch.object(scheduled_run,'update_intraday',return_value={'rows':[]}), patch.object(scheduled_run,'build') as build:
            clock.now.return_value=datetime(2026,9,22,10,0,tzinfo=NY)
            with self.assertRaisesRegex(RuntimeError,'No valid intraday'):
                scheduled_run.run()
            build.assert_not_called()


if __name__=='__main__':
    unittest.main()
