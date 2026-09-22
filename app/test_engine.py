import json
import unittest
from datetime import date, timedelta

from engine import calculate_metrics, evaluate_document


def make_bars(count=260, *, start=100.0, step=0.5, volume=1_000_000):
    first = date(2025, 1, 1)
    bars = []
    for i in range(count):
        close = start + step * i
        spread = 2.0 if i < count - 5 else 0.5
        bars.append({
            "date": (first + timedelta(days=i)).isoformat(),
            "open": close - 0.1,
            "high": close + spread,
            "low": close - spread,
            "close": close,
            "volume": volume,
        })
    return bars


def document(bars):
    return {
        "metadata": {
            "market": "US",
            "currency": "USD",
            "adjustment_policy": "split_adjusted_ohlcv",
            "session": "regular",
            "source": "unit-test",
            "as_of": bars[-1]["date"],
        },
        "symbols": [{"symbol": "TEST", "bars": bars}],
    }


class EngineTests(unittest.TestCase):
    def test_old_invalid_bar_uses_contiguous_suffix(self):
        bars = make_bars(800)
        bars[50]['volume'] = 0
        row = evaluate_document(document(bars))['results'][0]
        self.assertEqual(row['status'], 'ok')
        self.assertEqual(row['history_warning']['excluded_bars'], 51)
        self.assertEqual(row['charts']['daily'][0]['start'], bars[51]['date'])
        expected = calculate_metrics([{k:v for k,v in b.items() if k != 'date'} for b in bars[51:]])
        self.assertEqual(row['metrics'], expected)

    def test_history_break_requires_warmup_and_never_bridges(self):
        bars = make_bars(800)
        bars[400]['volume'] = 0
        row = evaluate_document(document(bars))['results'][0]
        self.assertEqual(row['status'], 'unknown')
        self.assertIn('504 required', row['reasons'][0])

    def test_formula_values_and_json_serializable(self):
        bars = make_bars()
        result = evaluate_document(document(bars), min_turnover=0, min_adr=0)
        item = result["results"][0]
        self.assertEqual(item["status"], "ok")
        metrics = item["metrics"]
        close = bars[-1]["close"]
        self.assertAlmostEqual(metrics["ret21_pct"], 100 * (close / bars[-22]["close"] - 1))
        self.assertAlmostEqual(metrics["sma200"], sum(x["close"] for x in bars[-200:]) / 200)
        self.assertAlmostEqual(metrics["RVOL20_completed"], 1.0)
        self.assertAlmostEqual(metrics["volumeRatio5"], 1.0)
        self.assertLess(metrics["rangeRatio5"], 1.0)
        self.assertIn("A", item["routes"])
        json.dumps(result, allow_nan=False)

    def test_future_bars_after_as_of_do_not_change_result(self):
        bars = make_bars()
        base_document = document(bars)
        base_document["metadata"]["as_of"] = bars[251]["date"]
        base = evaluate_document(base_document, min_turnover=0, min_adr=0)
        changed = make_bars()
        for bar in changed[252:]:
            bar.update(open=9_000.0, high=10_000.0, low=8_000.0, close=9_500.0, volume=999_000_000)
        future_document = document(changed)
        future_document["metadata"]["as_of"] = bars[251]["date"]
        future = evaluate_document(future_document, min_turnover=0, min_adr=0)
        self.assertEqual(base["results"], future["results"])

    def test_wrong_adjustment_policy_is_rejected(self):
        payload = document(make_bars())
        payload["metadata"]["adjustment_policy"] = "raw"
        with self.assertRaisesRegex(ValueError, "adjustment_policy"):
            evaluate_document(payload)

    def test_recovery_base_route_b(self):
        bars = make_bars(step=0.0, start=200.0)
        for i, bar in enumerate(bars):
            if i < 134:
                close = 200.0
            elif i < 214:
                close = 200.0 - 1.5 * (i - 133)
            else:
                close = 80.0 + (50.0 / 45.0) * (i - 214)
            bar.update(open=close, high=close + 2.0, low=close - 2.0, close=close)
        item = evaluate_document(document(bars), min_turnover=0, min_adr=0)["results"][0]
        self.assertEqual(item["status"], "ok")
        self.assertIn("B", item["routes"])

    def test_filter_thresholds_must_be_finite_and_nonnegative(self):
        payload = document(make_bars())
        with self.assertRaisesRegex(ValueError, "nonnegative"):
            evaluate_document(payload, min_turnover=-1)
        with self.assertRaisesRegex(ValueError, "finite"):
            evaluate_document(payload, min_adr=float("inf"))

    def test_missing_or_invalid_numeric_data_is_unknown(self):
        bars = make_bars()
        bars[-1]["volume"] = None
        item = evaluate_document(document(bars))["results"][0]
        self.assertEqual(item["status"], "unknown")
        self.assertEqual(item["metrics"], {})
        self.assertEqual(item["routes"], [])
        self.assertIn("volume", item["reasons"][0])

    def test_insufficient_history_after_as_of_is_unknown(self):
        bars = make_bars()
        payload = document(bars)
        payload["metadata"]["as_of"] = bars[250]["date"]
        item = evaluate_document(payload)["results"][0]
        self.assertEqual(item["status"], "unknown")
        self.assertIn("252 required", item["reasons"][0])

    def test_stale_last_bar_is_unknown(self):
        bars = make_bars()
        payload = document(bars)
        payload["metadata"]["as_of"] = (date.fromisoformat(bars[-1]["date"]) + timedelta(days=1)).isoformat()
        item = evaluate_document(payload)["results"][0]
        self.assertEqual(item["status"], "unknown")
        self.assertIn("stale data", item["reasons"][0])

    def test_zero_volume_is_unknown(self):
        bars = make_bars()
        bars[-3]["volume"] = 0
        item = evaluate_document(document(bars))["results"][0]
        self.assertEqual(item["status"], "unknown")
        self.assertIn("greater than zero", item["reasons"][0])

    def test_metadata_source_and_as_of_are_required(self):
        payload = document(make_bars())
        payload["metadata"].pop("source")
        with self.assertRaisesRegex(ValueError, "source"):
            evaluate_document(payload)

    def test_zero_metric_denominator_is_unknown(self):
        bars = make_bars(step=0.0)
        for bar in bars:
            bar["high"] = bar["close"]
            bar["low"] = bar["close"]
            bar["open"] = bar["close"]
        item = evaluate_document(document(bars), min_turnover=0, min_adr=0)["results"][0]
        self.assertEqual(item["status"], "unknown")
        self.assertIn("denominator", item["reasons"][0])


if __name__ == "__main__":
    unittest.main()
