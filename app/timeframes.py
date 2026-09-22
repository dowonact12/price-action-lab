"""Chart aggregation of validated daily inputs; no additional trading signals."""
from datetime import date


def chart_timeframes(bars, as_of):
    daily = sorted((dict(b) for b in bars if b['date'] <= as_of), key=lambda b: b['date'])
    output = {}
    for frame in ('monthly', 'weekly', 'daily'):
        groups = {}
        for bar in daily:
            day = date.fromisoformat(bar['date'])
            key = bar['date'] if frame == 'daily' else (bar['date'][:7] if frame == 'monthly' else day.isocalendar()[:2])
            if key not in groups:
                groups[key] = dict(start=bar['date'], end=bar['date'], open=float(bar['open']), high=float(bar['high']), low=float(bar['low']), close=float(bar['close']), volume=float(bar['volume']), sessions=1)
            else:
                group = groups[key]
                group.update(end=bar['date'], high=max(group['high'], float(bar['high'])), low=min(group['low'], float(bar['low'])), close=float(bar['close']), volume=group['volume'] + float(bar['volume']), sessions=group['sessions'] + 1)
        values = list(groups.values())
        for i, value in enumerate(values):
            # Without an exchange calendar, neither boundary period is certified.
            value['boundary_unverified'] = frame != 'daily' and i in (0, len(values) - 1)
        output[frame] = values
    return output
