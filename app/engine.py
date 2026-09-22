"""Daily OHLCV metric and US research-route engine.

The route names and thresholds are development definitions, not reproductions of
an author's proprietary screener.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any, Iterable
from timeframes import chart_timeframes
from setup_quality import assess


REQUIRED_ADJUSTMENT_POLICY = "split_adjusted_ohlcv"
ROUTE_A = "A"
ROUTE_B = "B"
ENGINE_VERSION = "us_daily_research_v6"


def screening_history(raw_bars, as_of):
    """Use the contiguous valid suffix; never bridge an invalid historical bar."""
    if not isinstance(raw_bars, list):
        raise ValueError("bars must be a list")
    ordered = []
    seen = set()
    for raw in raw_bars:
        if not isinstance(raw, dict):
            raise ValueError("bar must be an object")
        day = _iso_date(raw.get('date'), 'bar.date')
        if day > as_of:
            continue
        if day in seen:
            raise ValueError(f"duplicate bar date: {day}")
        seen.add(day)
        ordered.append(raw)
    ordered.sort(key=lambda b: b['date'])
    start, last_error = 0, None
    for index, raw in enumerate(ordered):
        try:
            _validated_bars([raw], as_of)
        except ValueError as exc:
            start, last_error = index + 1, str(exc)
    suffix = ordered[start:]
    if not suffix:
        raise ValueError(f"no valid trailing history: {last_error}")
    return suffix, ({'excluded_through': ordered[start-1]['date'], 'excluded_bars': start,
                     'reason': last_error, 'note': '오류 봉 이전과 이후를 이어 붙이지 않음. 이후 보유 이력으로 가능한 지표만 계산.'} if start else None)


def _number(value: Any, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite number")
    if positive and result <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return result


def _iso_date(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an ISO date string")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO date string") from exc
    return parsed.isoformat()


def _ema(values: list[float], period: int) -> float:
    value = sum(values[:period]) / period
    alpha = 2.0 / (period + 1.0)
    for current in values[period:]:
        value = alpha * current + (1.0 - alpha) * value
    return value


def _atr_wilder(bars: list[dict[str, float]], period: int = 14) -> float:
    true_ranges: list[float] = []
    previous_close: float | None = None
    for bar in bars:
        high, low = bar["high"], bar["low"]
        if previous_close is None:
            tr = high - low
        else:
            tr = max(high - low, abs(high - previous_close), abs(low - previous_close))
        true_ranges.append(tr)
        previous_close = bar["close"]
    atr = sum(true_ranges[:period]) / period
    for tr in true_ranges[period:]:
        atr = ((period - 1.0) * atr + tr) / period
    return atr


def _range(bars: list[dict[str, float]]) -> float:
    return max(bar["high"] for bar in bars) - min(bar["low"] for bar in bars)


def calculate_metrics(bars):
    """Compute each standard indicator only when its own lookback is available."""
    if not bars:
        raise ValueError('no valid history')
    n = len(bars)
    closes = [b['close'] for b in bars]
    current = closes[-1]
    if bars[-1]['volume'] == 0:
        raise ValueError('latest session has zero volume; trading activity unconfirmed')
    def ratio(a, b):
        return a/b if b > 0 else None
    recent = bars[-20:]
    observed_high = max(b['high'] for b in bars[-252:])
    observed_low = min(b['low'] for b in bars[-252:])
    adr = 100*sum((b['high']-b['low'])/b['close'] for b in recent)/len(recent)
    turnover = sum(b['close']*b['volume'] for b in recent)/len(recent)
    atr_period = min(14,n)
    atr = 100*_atr_wilder(bars,atr_period)/current
    metrics = dict(close=current, history_sessions=n,
        observedHigh=observed_high, observedLow=observed_low,
        offObservedHigh_pct=100*(current/observed_high-1),
        aboveObservedLow_pct=100*(current/observed_low-1),
        observedHigh_sessions=min(252,n), observedReturn_pct=100*(current/closes[0]-1),
        observedMean=sum(closes[-20:])/len(closes[-20:]),
        ADR_observed_pct=adr, turnover_observed=turnover, average_sessions=len(recent),
        ATR_observed_pct=atr, atr_sessions=atr_period,
        high252=observed_high if n>=252 else None,
        low252=observed_low if n>=252 else None,
        offHigh252_pct=100*(current/observed_high-1) if n>=252 else None,
        aboveLow252_pct=100*(current/observed_low-1) if n>=252 else None,
        sma200=sum(closes[-200:])/200 if n>=200 else None,
        ADR20_pct=adr if n>=20 else None,
        turnover20=turnover if n>=20 else None,
        ATR14_pct=atr if n>=14 else None,
        RVOL20_completed=ratio(bars[-1]['volume'],sum(b['volume'] for b in bars[-21:-1])/20) if n>=21 else None,
        rangeRatio5=ratio(_range(bars[-5:]),_range(bars[-10:-5])) if n>=10 else None,
        volumeRatio5=ratio(sum(b['volume'] for b in bars[-5:]),sum(b['volume'] for b in bars[-10:-5])) if n>=10 else None)
    for period in (21,63,126):
        metrics[f'ret{period}_pct']=100*(current/closes[-period-1]-1) if n>period else None
    for period in (10,20,50,100):
        metrics[f'ema{period}']=_ema(closes,period) if n>=period else None
    if not all(v is None or math.isfinite(v) for v in metrics.values()):
        raise ValueError('calculated metric is not finite')
    return metrics


def _validated_bars(raw_bars: Any, as_of: str) -> tuple[list[dict[str, float]], str | None]:
    if not isinstance(raw_bars, list):
        raise ValueError("bars must be a list")
    validated: list[tuple[str, dict[str, float]]] = []
    seen_dates: set[str] = set()
    for index, raw in enumerate(raw_bars):
        if not isinstance(raw, dict):
            raise ValueError(f"bars[{index}] must be an object")
        bar_date = _iso_date(raw.get("date"), f"bars[{index}].date")
        if bar_date > as_of:
            continue
        if bar_date in seen_dates:
            raise ValueError(f"duplicate bar date: {bar_date}")
        seen_dates.add(bar_date)
        bar = {
            name: _number(raw.get(name), f"bars[{index}].{name}", positive=name != 'volume')
            for name in ("open", "high", "low", "close", "volume")
        }
        if bar['volume'] < 0:
            raise ValueError(f"bars[{index}].volume must be nonnegative")
        if bar["high"] < max(bar["open"], bar["low"], bar["close"]):
            raise ValueError(f"bars[{index}].high is inconsistent")
        if bar["low"] > min(bar["open"], bar["high"], bar["close"]):
            raise ValueError(f"bars[{index}].low is inconsistent")
        validated.append((bar_date, bar))
    validated.sort(key=lambda item: item[0])
    return [bar for _, bar in validated], (validated[-1][0] if validated else None)


def _routes(
    metrics: dict[str, float], min_turnover: float, min_adr: float
) -> tuple[list[str], list[str]]:
    routes: list[str] = []
    reasons: list[str] = []
    if metrics['history_sessions'] < 252:
        if metrics['turnover_observed'] < min_turnover:
            reasons.append('보유 기간 평균 거래대금 미달')
        if metrics['ADR_observed_pct'] < min_adr:
            reasons.append('보유 기간 평균 변동폭 미달')
        if metrics['history_sessions'] < 5:
            reasons.append('가격 구조 관찰 중: 2봉씩의 수축 구간과 관찰봉이 아직 없음')
        if not (metrics['close'] > metrics['observedMean'] and metrics['observedReturn_pct'] > 0):
            reasons.append('보유 이력에서 상승 방향 미충족')
        if metrics['offObservedHigh_pct'] < -25:
            reasons.append('보유 기간 고점 대비 25% 초과 하락')
        return ([] if reasons else ['SHORT']), reasons
    if metrics['rangeRatio5'] is None:
        return [], ['가격 범위비 계산 불가: 이전 구간 가격 범위가 0']
    common = []
    if metrics["turnover20"] < min_turnover:
        common.append("turnover20 below minimum")
    if metrics["ADR20_pct"] < min_adr:
        common.append("ADR20_pct below minimum")
    failures_a = []
    if not (metrics["close"] > metrics["ema50"] > metrics["ema100"]):
        failures_a.append("requires close>ema50>ema100")
    if not metrics["ret63_pct"] > 0:
        failures_a.append("requires ret63_pct>0")
    if not metrics["offHigh252_pct"] >= -25:
        failures_a.append("requires offHigh252_pct>=-25")
    if not metrics["rangeRatio5"] < 1:
        failures_a.append("requires rangeRatio5<1")
    if not common and not failures_a:
        routes.append(ROUTE_A)
    else:
        reasons.extend(f"A: {reason}" for reason in common + failures_a)
    failures_b = []
    if not (metrics["close"] > metrics["ema50"] and metrics["close"] > metrics["ema100"]):
        failures_b.append("requires close>ema50 and close>ema100")
    if not metrics["offHigh252_pct"] <= -30:
        failures_b.append("requires offHigh252_pct<=-30")
    if not metrics["aboveLow252_pct"] >= 40:
        failures_b.append("requires aboveLow252_pct>=40")
    if not metrics["ret126_pct"] <= -20:
        failures_b.append("requires ret126_pct<=-20")
    if not common and not failures_b:
        routes.append(ROUTE_B)
    else:
        reasons.extend(f"B: {reason}" for reason in common + failures_b)
    return routes, reasons


def evaluate_document(
    document: dict[str, Any], min_turnover: float = 10_000_000, min_adr: float = 3.0
) -> dict[str, Any]:
    """Validate an input document and evaluate its symbols.

    Document-level contract failures raise ValueError. Symbol-level data failures
    are returned as ``status='unknown'`` with explicit reasons.
    """
    if not isinstance(document, dict):
        raise ValueError("document must be an object")
    metadata = document.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be an object")
    required = ("market", "currency", "adjustment_policy", "session", "source", "as_of")
    missing = [name for name in required if metadata.get(name) in (None, "")]
    if missing:
        raise ValueError("missing metadata: " + ", ".join(missing))
    if metadata["market"] != "US" or metadata["currency"] != "USD":
        raise ValueError("v1 supports market=US and currency=USD only")
    if metadata["session"] != "regular":
        raise ValueError("v1 supports regular session data only")
    if metadata["adjustment_policy"] != REQUIRED_ADJUSTMENT_POLICY:
        raise ValueError(f"adjustment_policy must be {REQUIRED_ADJUSTMENT_POLICY}")
    if not isinstance(metadata["source"], str) or not metadata["source"].strip():
        raise ValueError("metadata.source is required")
    as_of = _iso_date(metadata["as_of"], "metadata.as_of")
    minimum_turnover = _number(min_turnover, "min_turnover")
    minimum_adr = _number(min_adr, "min_adr")
    if minimum_turnover < 0 or minimum_adr < 0:
        raise ValueError("minimum thresholds must be nonnegative")
    symbols = document.get("symbols")
    if not isinstance(symbols, list):
        raise ValueError("symbols must be a list")

    results: list[dict[str, Any]] = []
    seen_symbols: set[str] = set()
    for index, item in enumerate(symbols):
        symbol = item.get("symbol") if isinstance(item, dict) else None
        if not isinstance(symbol, str) or not symbol.strip():
            symbol = f"<invalid:{index}>"
            results.append({"symbol": symbol, "status": "unknown", "reasons": ["invalid symbol"], "metrics": {}, "routes": []})
            continue
        symbol = symbol.strip().upper()
        if symbol in seen_symbols:
            results.append({"symbol": symbol, "status": "unknown", "reasons": ["duplicate symbol"], "metrics": {}, "routes": []})
            continue
        seen_symbols.add(symbol)
        try:
            history, warning = screening_history(item.get("bars"), as_of)
            bars, last_date = _validated_bars(history, as_of)
            if last_date != as_of:
                raise ValueError(f"stale data: last eligible date {last_date}; expected {as_of}")
            metrics = calculate_metrics(bars)
            routes, reasons = _routes(metrics, minimum_turnover, minimum_adr)
            frames = chart_timeframes(history, as_of)
            quality = assess(history, metrics, frames, routes, warning)
            results.append({"history_sessions": len(bars), "history_mode": "limited" if len(bars)<252 else "full", "unavailable_metrics": [k for k,v in metrics.items() if v is None], "quality": quality, "symbol": symbol, "status": "ok", "reasons": reasons, "metrics": metrics, "routes": routes, "history_warning": warning, "charts": frames})
        except (KeyError, TypeError, ValueError) as exc:
            results.append({"symbol": symbol, "status": "unknown", "reasons": [str(exc)], "metrics": {}, "routes": []})

    output_metadata = dict(metadata)
    output_metadata["as_of"] = as_of
    output_metadata["engine"] = ENGINE_VERSION
    output_metadata["min_turnover"] = minimum_turnover
    output_metadata["min_adr"] = minimum_adr
    return {"metadata": output_metadata, "results": results}
