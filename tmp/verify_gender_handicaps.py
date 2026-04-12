import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Mock models since we don't want to rely on the actual DB for a quick logic check
class MockTee:
    def __init__(self, rating, slope, rating_female=None, slope_female=None, par=72):
        self.rating = rating
        self.slope = slope
        self.rating_female = rating_female
        self.slope_female = slope_female
        self.par = par

class MockPlayer:
    def __init__(self, name, index, gender='male'):
        self.name = name
        self.handicap_index = index
        self.gender = gender

from services.handicap import calculate_course_handicap

def test_handicap_selection():
    tee = MockTee(rating=70.0, slope=120, rating_female=72.0, slope_female=125, par=72)
    
    male_player = MockPlayer("Bob", 10.0, 'male')
    female_player = MockPlayer("Alice", 10.0, 'female')
    
    # Logic from match_engine.py
    def get_ch(p, t):
        r = t.rating_female if p.gender == 'female' and t.rating_female else t.rating
        s = t.slope_female if p.gender == 'female' and t.slope_female else t.slope
        return calculate_course_handicap(p.handicap_index, s, r, t.par)

    ch_male = get_ch(male_player, tee)
    ch_female = get_ch(female_player, tee)
    
    print(f"Male (10.0 index, 70.0/120): CH = {ch_male}")
    print(f"Female (10.0 index, 72.0/125): CH = {ch_female}")
    
    # Expected Male: (10.0 * (120/113)) + (70.0 - 72) = 10.619 + (-2) = 8.619 -> 9
    # Expected Female: (10.0 * (125/113)) + (72.0 - 72) = 11.06 + 0 = 11.06 -> 11
    
    assert ch_male == 9
    assert ch_female == 11
    
    # Test fallback
    tee_no_female = MockTee(rating=70.0, slope=120, par=72)
    ch_female_fallback = get_ch(female_player, tee_no_female)
    print(f"Female Fallback (10.0 index, 70.0/120): CH = {ch_female_fallback}")
    assert ch_female_fallback == 9
    
    print("Verification SUCCESSFUL!")

if __name__ == "__main__":
    test_handicap_selection()
