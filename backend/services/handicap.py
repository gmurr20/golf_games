import math

def round_half_up(n: float) -> int:
    """USGA rounding: .5 rounds up (to the next highest integer)"""
    return int(math.floor(n + 0.5))

def calculate_course_handicap(handicap_index: float, slope: int, rating: float, par: int, rounded: bool = True) -> float:
    """WHS 2020 Formula: CH = (Index * (Slope / 113)) + (Rating - Par)"""
    ch = (handicap_index * (slope / 113.0)) + (rating - par)
    if rounded:
        return round_half_up(ch)
    return ch

def calculate_playing_handicaps(course_handicaps: dict) -> dict:
    """
    Takes dict of {player_id: course_handicap} and returns playing handicaps (strokes received)
    Works for both 1v1 and 2v2 because it just reduces everyone by the minimum.
    """
    min_ch = min(course_handicaps.values())
    return {pid: ch - min_ch for pid, ch in course_handicaps.items()}

def calculate_shamble_pops(players: list, tee_data: dict, holes: list, shamble_type: str = "2-person") -> dict:
    """
    Calculates Shamble pops per player.
    shamble_type: '2-person' (75% allowance) or '4-person' (65% allowance)
    Returns: {player_id: {hole_number: pops}}
    """
    allowance = 0.75 if shamble_type == "2-person" else 0.65
    
    player_pops = {}
    for p in players:
        # CH is calculated unrounded first
        ch_unrounded = calculate_course_handicap(
            p.handicap_index, 
            tee_data['slope'], 
            tee_data['rating'], 
            tee_data['par'], 
            rounded=False
        )
        # Apply allowance then round
        ph = round_half_up(ch_unrounded * allowance)
        # Allocate to holes
        player_pops[p.id] = allocate_pops(ph, holes)
        
    return player_pops

def allocate_pops(strokes: int, holes: list) -> dict:
    """
    Given a number of strokes and a list of Hole objects (with hole_number and handicap_index 1-18),
    returns a dict of {hole_number: pops}
    Handles plus handicaps (negative strokes) by subtracting from easiest holes first.
    """
    pops = {h.hole_number: 0 for h in holes}
    if strokes == 0:
        return pops
    
    num_holes = len(holes)
    if num_holes == 0:
        return pops

    is_negative = strokes < 0
    abs_strokes = abs(strokes)
    
    # Sort holes by difficulty
    if is_negative:
        # For plus handicaps, easiest holes first (highest handicap_index)
        sorted_holes = sorted(holes, key=lambda h: h.handicap_index, reverse=True)
    else:
        # For regular handicaps, hardest holes first (lowest handicap_index)
        sorted_holes = sorted(holes, key=lambda h: h.handicap_index)
        
    base_pops = abs_strokes // num_holes
    remainder = abs_strokes % num_holes
    
    fill_value = -1 if is_negative else 1
    
    for h in sorted_holes:
        pops[h.hole_number] += base_pops * fill_value
        
    for i in range(remainder):
        pops[sorted_holes[i].hole_number] += fill_value
        
    return pops
