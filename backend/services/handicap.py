import math

def calculate_course_handicap(handicap_index: float, slope: int, rating: float, par: int) -> int:
    """WHS 2020 Formula: CH = (Index * (Slope / 113)) + (Rating - Par)"""
    ch = (handicap_index * (slope / 113.0)) + (rating - par)
    return round(ch)

def calculate_playing_handicaps(course_handicaps: dict) -> dict:
    """
    Takes dict of {player_id: course_handicap} and returns playing handicaps (strokes received)
    Works for both 1v1 and 2v2 because it just reduces everyone by the minimum.
    """
    min_ch = min(course_handicaps.values())
    return {pid: ch - min_ch for pid, ch in course_handicaps.items()}

def allocate_pops(strokes: int, holes: list) -> dict:
    """
    Given a number of strokes and a list of Hole objects (with hole_number and handicap_index 1-18),
    returns a dict of {hole_number: pops}
    """
    pops = {h.hole_number: 0 for h in holes}
    if strokes == 0:
        return pops
    
    # Sort holes by difficulty: lowest handicap_index is hardest
    sorted_holes = sorted(holes, key=lambda h: h.handicap_index)
    
    num_holes = len(holes)
    if num_holes == 0:
        return pops
        
    base_pops = strokes // num_holes
    remainder = strokes % num_holes
    
    for h in sorted_holes:
        pops[h.hole_number] += base_pops
        
    for i in range(remainder):
        pops[sorted_holes[i].hole_number] += 1
        
    return pops
