import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ember_engine import Session, mines_stats


class MinesTests(unittest.TestCase):
    def test_three_mines_first_pick(self):
        self.assertAlmostEqual(mines_stats(3, 0)['next_safe_probability'], 22 / 25)

    def test_three_mines_after_safe(self):
        self.assertAlmostEqual(mines_stats(3, 1)['next_safe_probability'], 21 / 24)
        self.assertAlmostEqual(mines_stats(3, 1)['survival_probability'], 22 / 25)

    def test_all_safe_revealed(self):
        self.assertEqual(mines_stats(3, 22)['next_safe_probability'], 0)

    def test_invalid_mines(self):
        with self.assertRaises(ValueError):
            mines_stats(25, 0)

    def test_payout_accounting(self):
        s = Session(starting_balance_sats=100)
        s.begin(10, 3)
        s.mark_safe()
        s.complete('cashout', 12)
        self.assertEqual(s.net_sats, 2)
        s.begin(5, 4)
        s.complete('mine')
        self.assertEqual(s.tracked_balance_sats, 97)
        self.assertEqual(len(s.records), 2)

    def test_round_requires_start(self):
        with self.assertRaises(ValueError):
            Session().mark_safe()

    def test_no_reinterpretation_of_old_data(self):
        s = Session(100)
        s.begin(10, 3)
        with self.assertRaises(ValueError):
            s.begin(1, 2)
        self.assertEqual(Session.from_dict(s.as_dict()).active['bet_sats'], 10)

    def test_payout_rejects_fractional(self):
        s = Session(100)
        s.begin(10, 3)
        with self.assertRaises(ValueError):
            s.complete('cashout', '10.3')


if __name__ == '__main__':
    unittest.main()
