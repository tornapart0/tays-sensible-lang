import unittest
from unittest.mock import patch
from mylang.timing import every

class TimingTests(unittest.TestCase):
    def test_skips_missed_samples(self):
        current = [0.0]

        def sleep(seconds):
            current[0] += seconds

        with patch('mylang.timing.time.monotonic', side_effect=lambda: current[0]), patch('mylang.timing.time.sleep', side_effect=sleep):
            ticks = every(0.1, 0.5)
            self.assertEqual(next(ticks), 0)
            current[0] = 0.35
            self.assertAlmostEqual(next(ticks), 0.4)
            with self.assertRaises(StopIteration):
                next(ticks)
