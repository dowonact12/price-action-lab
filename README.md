# Price Action Lab

US listed-stock and ETF research dashboard. OTC is not covered.

Calculations and scheduled collection run as ordinary Python: no LLM APIs or token usage. A/B thresholds are development assumptions, not reproductions of a trader’s proprietary method.

## Scheduled operation
GitHub Actions attempts a run every 5 minutes around US market hours. The script gates execution using America/New_York, including DST. All valid symbols are polled; a batch may exceed 5 minutes. GitHub schedules and the experimental Yahoo data feed do not guarantee real-time delivery.

The dedicated `market-state` branch is generated current state, replaced after successful publication. Forward observations remain in `data/history.json`. Do not place hand-authored files on that branch. Source and research history are not force-pushed.

Enable Pages with source **GitHub Actions**, then run **Market data and Pages** manually once. No API key is required. Failures are visible in Actions and the last successfully published page stays available.

## Development
`python -m unittest discover -s app -q`
`python app/updater.py --all --daily-only`
`python app/build_pages.py`

## Scope
Monthly, weekly, daily OHLCV charts; transparent filter checks; source links; forward candidate observations. No trade execution or validated profitability claim. Private subscriber articles, screenshots, and research collections are excluded.
