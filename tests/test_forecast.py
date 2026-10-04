import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.forecast import linear_forecast, minutes_to_limit


class ForecastTest(unittest.TestCase):
    def test_linear_forecast_continues_a_straight_climb(self):
        self.assertEqual(linear_forecast([10, 20, 30, 40], 1), 50)

    def test_minutes_to_limit_for_a_leak(self):
        self.assertEqual(minutes_to_limit([10, 20, 30, 40], 100, 60), 6)

    def test_flat_series_has_no_breach(self):
        self.assertIsNone(minutes_to_limit([40, 40, 40], 100, 60))


if __name__ == "__main__":
    unittest.main()
