from services.handicap import calculate_course_handicap, calculate_playing_handicaps, allocate_pops

class MockHole:
    def __init__(self, number, index):
        self.hole_number = number
        self.handicap_index = index

def test_calculate_course_handicap():
    ch = calculate_course_handicap(10.0, 120, 70.0, 72)
    assert ch == 9

def test_calculate_playing_handicaps():
    ch_dict = {
        1: 5,
        2: 12,
        3: 15,
        4: 0
    }
    ph_dict = calculate_playing_handicaps(ch_dict)
    assert ph_dict[1] == 5
    assert ph_dict[2] == 12
    assert ph_dict[3] == 15
    assert ph_dict[4] == 0

def test_allocate_pops():
    holes = [
        MockHole(1, 15), 
        MockHole(2, 1), 
        MockHole(3, 11),
        MockHole(4, 3) 
    ]
    pops = allocate_pops(2, holes)
    assert pops[2] == 1
    assert pops[4] == 1
    assert pops[1] == 0
    assert pops[3] == 0

    pops = allocate_pops(6, holes)
    assert pops[2] == 2
    assert pops[4] == 2
    assert pops[1] == 1
    assert pops[3] == 1
