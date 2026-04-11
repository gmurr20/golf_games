import os
import sys
import unittest
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from services.handicap import calculate_course_handicap, calculate_shamble_pops, allocate_pops, round_half_up

class TestShambleLogic(unittest.TestCase):
    def test_round_half_up(self):
        self.assertEqual(round_half_up(1.5), 2)
        self.assertEqual(round_half_up(1.4), 1)
        self.assertEqual(round_half_up(1.6), 2)
        self.assertEqual(round_half_up(-1.5), -1)
        self.assertEqual(round_half_up(-1.6), -2)
        self.assertEqual(round_half_up(-1.4), -1)

    def test_shamble_handicap_calculation(self):
        # Example: Index 10.0, Slope 113, Rating 72.0, Par 72
        # CH = (10.0 * (113/113)) + (72 - 72) = 10.0
        # Allowance 75% = 7.5
        # Round 7.5 -> 8
        
        class MockPlayer:
            def __init__(self, id, index):
                self.id = id
                self.handicap_index = index
        
        players = [MockPlayer(1, 10.0)]
        tee_data = {'slope': 113, 'rating': 72.0, 'par': 72}
        
        class MockHole:
            def __init__(self, num, si):
                self.hole_number = num
                self.handicap_index = si
        
        holes = [MockHole(i, i) for i in range(1, 19)]
        
        pops = calculate_shamble_pops(players, tee_data, holes, "2-person")
        
        # Check total pops for player 1
        total_pops = sum(pops[1].values())
        self.assertEqual(total_pops, 8)

    def test_plus_handicap_allocation(self):
        # Plus 2 handicap -> PH = -2
        class MockHole:
            def __init__(self, num, si):
                self.hole_number = num
                self.handicap_index = si # 1 is hardest, 18 is easiest
        
        holes = [MockHole(i, i) for i in range(1, 19)]
        
        strokes = -2
        pops = allocate_pops(strokes, holes)
        
        # Should be subtracted from easiest holes (highest handicap_index)
        # Easiest is SI 18 (hole 18 in our mock) and SI 17 (hole 17)
        self.assertEqual(pops[18], -1)
        self.assertEqual(pops[17], -1)
        self.assertEqual(pops[1], 0)
        self.assertEqual(sum(pops.values()), -2)

    def test_regular_handicap_allocation(self):
        class MockHole:
            def __init__(self, num, si):
                self.hole_number = num
                self.handicap_index = si
        
        holes = [MockHole(i, i) for i in range(1, 19)]
        
        strokes = 2
        pops = allocate_pops(strokes, holes)
        
        # Should be added to hardest holes (lowest handicap_index)
        self.assertEqual(pops[1], 1)
        self.assertEqual(pops[2], 1)
        self.assertEqual(pops[18], 0)
        self.assertEqual(sum(pops.values()), 2)

if __name__ == '__main__':
    unittest.main()
