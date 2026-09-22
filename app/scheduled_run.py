"""One Actions run: daily universe refresh or regular-session whole-universe quotes."""
import json
import os
from datetime import datetime
from pathlib import Path
from market_data import NY, listed_symbols
from updater import read_saved, update_daily, update_intraday, save
from build_pages import build


def run(force=False):
    now=datetime.now(NY)
    minute=now.hour*60+now.minute
    saved=read_saved('latest.json')
    # All schedules use UTC; this gate handles US daylight saving automatically.
    regular=now.weekday()<5 and 570<=minute<960
    after_close=now.weekday()<5 and 990<=minute<1080
    refreshed=read_saved('scheduler.json',{}).get('daily_attempt')
    daily=force or saved is None or (after_close and refreshed!=now.date().isoformat())
    if not daily and not regular:
        return False
    if daily:
        saved=update_daily(listed_symbols())
        save('scheduler.json',dict(daily_attempt=now.date().isoformat()))
    if regular:
        result=update_intraday(saved)
        if not result['rows']:
            raise RuntimeError('No valid intraday quotes; do not publish a fresh success timestamp')
    build(Path(__file__).resolve().parent.parent/'dist')
    # Restore this small scheduling marker with the published data on the next run.
    marker=Path(__file__).resolve().parent/'data'/'scheduler.json'
    if marker.exists():
        (Path(__file__).resolve().parent.parent/'dist'/'data'/'scheduler.json').write_bytes(marker.read_bytes())
    output=os.environ.get('GITHUB_OUTPUT')
    if output:
        with open(output,'a',encoding='utf-8') as stream:
            stream.write('publish=true\n')
    return True


if __name__=='__main__':
    run(os.environ.get('FORCE_DAILY')=='true')
