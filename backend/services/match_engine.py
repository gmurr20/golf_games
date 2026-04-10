from models import db
from models.models import Matchup, MatchupPlayer, Hole, Score, Tee, Player
from services.handicap import calculate_course_handicap, calculate_playing_handicaps, allocate_pops

def calculate_match_status(matchup_id: int) -> dict:
    matchup = db.session.get(Matchup, matchup_id)
    if not matchup:
        return {"error": "Matchup not found"}
        
    tee = matchup.tee
    holes = Hole.query.filter_by(tee_id=tee.id).order_by(Hole.hole_number).all()
    
    m_players = MatchupPlayer.query.filter_by(matchup_id=matchup_id).all()
    # Separate teams
    team_a_pids = [mp.player_id for mp in m_players if mp.team == 'A']
    team_b_pids = [mp.player_id for mp in m_players if mp.team == 'B']
    
    players = Player.query.filter(Player.id.in_(team_a_pids + team_b_pids)).all()
    player_map = {p.id: p for p in players}
    
    # Calculate Course Handicaps
    course_handicaps = {
        p.id: calculate_course_handicap(p.handicap_index, tee.slope, tee.rating, tee.par)
        for p in players
    }
    
    # Calculate Playing Handicaps
    playing_handicaps = calculate_playing_handicaps(course_handicaps)
    
    # Allocate pops per hole for each player
    pops_per_hole = {
        p.id: allocate_pops(playing_handicaps[p.id], holes)
        for p in players
    }
    
    # Fetch Scores
    scores = Score.query.filter_by(matchup_id=matchup_id).all()
    scores_by_hole_player = {}
    for s in scores:
        if s.hole_number not in scores_by_hole_player:
            scores_by_hole_player[s.hole_number] = {}
        scores_by_hole_player[s.hole_number][s.player_id] = s.strokes
        
    match_status = {
        "team_a_wins": 0,
        "team_b_wins": 0,
        "holes_played": 0,
        "status_string": "All Square",
        "scorecard": []
    }
    
    # Evaluate holes in order
    for h in holes:
        hole_data = {
            "hole_number": h.hole_number,
            "par": h.par,
            "handicap_index": h.handicap_index,
            "players": {},
            "winner": None
        }
        
        # Did all required players score? For 1v1 we need both. For 2v2 we at least need 1 score from A and 1 from B.
        a_scores = []
        b_scores = []
        
        for pid in team_a_pids + team_b_pids:
            raw_score = scores_by_hole_player.get(h.hole_number, {}).get(pid)
            if raw_score is not None:
                net_score = raw_score - pops_per_hole[pid].get(h.hole_number, 0)
                hole_data["players"][pid] = {
                    "raw": raw_score,
                    "net": net_score,
                    "pops": pops_per_hole[pid].get(h.hole_number, 0)
                }
                if pid in team_a_pids:
                    a_scores.append(net_score)
                else:
                    b_scores.append(net_score)
                    
        if a_scores and b_scores:
            match_status["holes_played"] += 1
            best_a = min(a_scores)
            best_b = min(b_scores)
            
            if best_a < best_b:
                hole_data["winner"] = "A"
                match_status["team_a_wins"] += 1
            elif best_b < best_a:
                hole_data["winner"] = "B"
                match_status["team_b_wins"] += 1
            else:
                hole_data["winner"] = "Push"
                
        match_status["scorecard"].append(hole_data)
        
    # Build status string
    diff = match_status["team_a_wins"] - match_status["team_b_wins"]
    holes_remaining = 18 - match_status["holes_played"]
    
    if diff == 0:
        match_status["status_string"] = f"AS thru {match_status['holes_played']}" if match_status['holes_played'] > 0 else "Upcoming"
    elif diff > 0:
        if diff > holes_remaining:
            match_status["status_string"] = f"Team A wins {diff} & {holes_remaining}"
        else:
            match_status["status_string"] = f"Team A is {diff} UP thru {match_status['holes_played']}"
    else:
        if abs(diff) > holes_remaining:
            match_status["status_string"] = f"Team B wins {abs(diff)} & {holes_remaining}"
        else:
            match_status["status_string"] = f"Team B is {abs(diff)} UP thru {match_status['holes_played']}"

    return match_status
