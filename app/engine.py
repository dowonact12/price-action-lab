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
ENGINE_VERSION = "us_daily_research_v5"


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
    if start and len(suffix) < 504:
        raise ValueError(f"recent invalid history: {last_error}; {len(suffix)} valid trailing bars; 504 required after a history break")
    return suffix, ({'excluded_through': ordered[start-1]['date'], 'excluded_bars': start,
                     'reason': last_error, 'note': '오류 봉 이전 이력 제외. 이후 연속 유효 504봉 이상으로 계산; 장기 차트 범위 축소.'} if start else None)


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


def calculate_metrics(bars: list[dict[str, float]]) -> dict[str, float]:
    """Calculate metrics from at least 252 validated, ascending daily bars."""
    if len(bars) < 252:
        raise ValueError("at least 252 eligible bars are required")

    closes = [bar["close"] for bar in bars]
    current = closes[-1]
    window252 = bars[-252:]
    high252 = max(bar["high"] for bar in window252)
    low252 = min(bar["low"] for bar in window252)
    previous_volume20 = sum(bar["volume"] for bar in bars[-21:-1]) / 20.0
    prior_range = _range(bars[-10:-5])
    if bars[-1]['volume'] == 0:
        raise ValueError('latest session has zero volume; trading activity unconfirmed')
    if previous_volume20 <= 0 or prior_range <= 0 or sum(b['volume'] for b in bars[-10:-5]) <= 0:
        raise ValueError("metric denominator is zero")

    metric_values = {
        "close": current,
        "ret21_pct": 100.0 * (current / closes[-22] - 1.0),
        "ret63_pct": 100.0 * (current / closes[-64] - 1.0),
        "ret126_pct": 100.0 * (current / closes[-127] - 1.0),
        "ema10": _ema(closes, 10),
        "ema20": _ema(closes, 20),
        "ema50": _ema(closes, 50),
        "ema100": _ema(closes, 100),
        "sma200": sum(closes[-200:]) / 200.0,
        "high252": high252,
        "low252": low252,
        "offHigh252_pct": 100.0 * (current / high252 - 1.0),
        "aboveLow252_pct": 100.0 * (current / low252 - 1.0),
        "ADR20_pct": 100.0 * sum(
            (bar["high"] - bar["low"]) / bar["close"] for bar in bars[-20:]
        ) / 20.0,
        "ATR14_pct": 100.0 * _atr_wilder(bars, 14) / current,
        "RVOL20_completed": bars[-1]["volume"] / previous_volume20,
        "rangeRatio5": _range(bars[-5:]) / prior_range,
        "volumeRatio5": (
            sum(bar["volume"] for bar in bars[-5:])
            / sum(bar["volume"] for bar in bars[-10:-5])
        ),
        "turnover20": sum(
            bar["close"] * bar["volume"] for bar in bars[-20:]
        ) / 20.0,
    }
    if not all(math.isfinite(value) for value in metric_values.values()):
        raise ValueError("calculated metric is not finite")
    return metric_values


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
            if len(bars) < 252:
                raise ValueError(f"insufficient eligible history: {len(bars)} bars; 252 required")
            metrics = calculate_metrics(bars)
            routes, reasons = _routes(metrics, minimum_turnover, minimum_adr)
            frames = chart_timeframes(history, as_of)
            quality = assess(history, metrics, frames, routes, warning)
            results.append({"quality": quality, "symbol": symbol, "status": "ok", "reasons": reasons, "metrics": metrics, "routes": routes, "history_warning": warning, "charts": frames})
        except (KeyError, TypeError, ValueError) as exc:
            results.append({"symbol": symbol, "status": "unknown", "reasons": [str(exc)], "metrics": {}, "routes": []})

    output_metadata = dict(metadata)
    output_metadata["as_of"] = as_of
    output_metadata["engine"] = ENGINE_VERSION
    output_metadata["min_turnover"] = minimum_turnover
    output_metadata["min_adr"] = minimum_adr
    return {"metadata": output_metadata, "results": results}
