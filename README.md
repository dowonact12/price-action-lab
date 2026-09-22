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

## Setup quality research policy
S/A/B/C are transparent, uncalibrated setup grades, separate from legacy A/B prefilters. Only graded symbols appear in active lists. The screen shows each passed/failed condition and price-line provenance. Current trigger/invalidation uses the ten completed sessions BEFORE the observation bar. Monthly/weekly comparisons exclude unverified boundary periods. Confirmed historical swing highs before that contraction constrain overhead room; absence is unknown, not clear air. Each daily snapshot is a new research plan, not a persistent trade or instruction to move a stop. Relative strength percentile, retest/reclaim lifecycle and execution cost checks are not yet implemented. Subscriber material is never published.

## Data quality and registered plans (v5)
Historical zero-volume bars are retained rather than treated as corrupt prices. Missing/negative volume and invalid OHLC still fail validation; latest-session zero volume is unconfirmed. The former 252/504-session blanket exclusion has been removed. Each indicator uses its own required lookback; unavailable indicators are null, never shortened and mislabeled. Available-history means, highs and volatility have separate names and actual sample counts. After invalid historical data, only the contiguous valid suffix is used without a blanket warmup exclusion. One-bar histories remain visible in the short-history tab. With at least five bars, a separate short-history contraction path can qualify using two prior comparison windows and an observation bar. Unknown checks are excluded from the grade denominator; fewer than 21 bars caps the provisional grade at B. Missing history never alone assigns a grade.

The leader plan uses the previous 10 sessions; recovery uses 20. These are research assumptions, not fitted or performance-validated thresholds. `plans.json` persists registered trigger, support band (trigger minus min(0.25 ATR, 0.25 initial risk)), and close-based invalidation. Only later daily bars can generate events. Registering above the trigger does not count as a breakout. Reclaim and rebreak are distinct; invalidation is terminal. Revised historical anchor prices or unavailable history pause tracking. A new plan can register on a later day after invalidation. Current candidate grading and fixed-plan history are separate. Intraday quotes never certify these daily-close events.
