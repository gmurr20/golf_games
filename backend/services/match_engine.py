from models import db
from models.models import Matchup, MatchupPlayer, Hole, Score, Tee, Player
from services.handicap import calculate_course_handicap, calculate_playing_handicaps, allocate_pops

def calculate_match_status(matchup_id: int) -> dict:
    matchup = db.session.get(Matchup, matchup_id)
    if not matchup:
        return {"error": "Matchup not found"}
        
    tee = matchup.tee
    hole_start = matchup.hole_start or 1
    hole_end = matchup.hole_end or 18
    holes = Hole.query.filter(
        Hole.tee_id == tee.id,
        Hole.hole_number >= hole_start,
        Hole.hole_number <= hole_end
    ).order_by(Hole.hole_number).all()
    
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
    
    # Allocate pops per hole for each player using all holes for context
    all_holes = Hole.query.filter_by(tee_id=tee.id).order_by(Hole.hole_number).all()
    pops_per_hole = {
        p.id: allocate_pops(playing_handicaps[p.id], all_holes)
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
        "scorecard": [],
        "is_completed": False
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
    total_match_holes = hole_end - hole_start + 1
    holes_remaining = total_match_holes - match_status["holes_played"]
    
    is_match_play = matchup.format == 'match_play'
    if is_match_play:
        if abs(diff) > holes_remaining or holes_remaining == 0:
            match_status["is_completed"] = True
    else:
        # Stroke / Scramble is completed only when all holes are played
        if holes_remaining == 0:
            match_status["is_completed"] = True

    # Determine the 'Thru' label (e.g. 'thru 15' instead of 'thru 6' for back 9)
    last_hole_played = 0
    if match_status["scorecard"]:
        played_hole_nums = [h["hole_number"] for h in match_status["scorecard"] if h["winner"] is not None]
        if played_hole_nums:
            last_hole_played = max(played_hole_nums)
    
    thru_label = f"thru {last_hole_played}" if last_hole_played > 0 else "Upcoming"

    if diff == 0:
        if match_status["is_completed"]:
            match_status["status_string"] = "Final: AS"
        else:
            match_status["status_string"] = f"AS {thru_label}" if last_hole_played > 0 else "Upcoming"
    elif diff > 0:
        if is_match_play and diff > holes_remaining:
             match_status["status_string"] = f"Team A wins {diff} & {holes_remaining}" if holes_remaining > 0 else f"Team A wins {diff} UP"
        elif match_status["is_completed"]:
             match_status["status_string"] = f"Final: Team A wins {diff} UP"
        else:
            match_status["status_string"] = f"Team A is {diff} UP {thru_label}"
    else:
        ad = abs(diff)
        if is_match_play and ad > holes_remaining:
            match_status["status_string"] = f"Team B wins {ad} & {holes_remaining}" if holes_remaining > 0 else f"Team B wins {ad} UP"
        elif match_status["is_completed"]:
            match_status["status_string"] = f"Final: Team B wins {ad} UP"
        else:
            match_status["status_string"] = f"Team B is {ad} UP {thru_label}"

    return match_status

def calculate_overall_winner(matchup_id: int) -> dict:
    matchup = db.session.get(Matchup, matchup_id)
    if not matchup:
        return {"error": "Matchup not found"}
        
    if matchup.format == 'match_play':
        ms = calculate_match_status(matchup_id)
        if "error" in ms:
            return ms
            
        diff = ms["team_a_wins"] - ms["team_b_wins"]
        
        # Calculate points
        if diff > 0:
            pts_a, pts_b = matchup.points_for_win, 0.0
            winner = 'A'
        elif diff < 0:
            pts_a, pts_b = 0.0, matchup.points_for_win
            winner = 'B'
        else:
            pts_a, pts_b = matchup.points_for_push, matchup.points_for_push
            winner = 'Push'
            
        return {
            "winner": winner,
            "summary": ms["status_string"],
            "points_a": pts_a,
            "points_b": pts_b
        }
    
    # Stroke play / Scramble logic
    tee = matchup.tee
    holes = Hole.query.filter(Hole.tee_id == tee.id, Hole.hole_number >= (matchup.hole_start or 1), Hole.hole_number <= (matchup.hole_end or 18)).order_by(Hole.hole_number).all()
    
    m_players = MatchupPlayer.query.filter_by(matchup_id=matchup_id).all()
    team_a_pids = [mp.player_id for mp in m_players if mp.team == 'A']
    team_b_pids = [mp.player_id for mp in m_players if mp.team == 'B']
    
    players = Player.query.filter(Player.id.in_(team_a_pids + team_b_pids)).all()
    
    if matchup.use_handicaps:
        course_handicaps = { p.id: calculate_course_handicap(p.handicap_index, tee.slope, tee.rating, tee.par) for p in players }
        playing_handicaps = calculate_playing_handicaps(course_handicaps)
        all_holes = Hole.query.filter_by(tee_id=tee.id).order_by(Hole.hole_number).all()
        pops_per_hole = { p.id: allocate_pops(playing_handicaps[p.id], all_holes) for p in players }
    else:
        pops_per_hole = { p.id: {} for p in players }
    
    scores = Score.query.filter_by(matchup_id=matchup_id).all()
    scores_by_hole_player = {}
    for s in scores:
        if s.hole_number not in scores_by_hole_player:
            scores_by_hole_player[s.hole_number] = {}
        scores_by_hole_player[s.hole_number][s.player_id] = s.strokes
        
    team_a_total = 0
    team_b_total = 0
    
    for h in holes:
        a_scores = []
        b_scores = []
        for pid in team_a_pids + team_b_pids:
            raw_score = scores_by_hole_player.get(h.hole_number, {}).get(pid)
            if raw_score is not None:
                net_score = raw_score - pops_per_hole[pid].get(h.hole_number, 0)
                if pid in team_a_pids:
                    a_scores.append(net_score)
                else:
                    b_scores.append(net_score)
        
        if a_scores: team_a_total += min(a_scores)
        if b_scores: team_b_total += min(b_scores)
            
    if team_a_total < team_b_total:
        winner = 'A'
        summary = f"Team A won by {team_b_total - team_a_total} strokes"
        pts_a, pts_b = matchup.points_for_win, 0.0
    elif team_b_total < team_a_total:
        winner = 'B'
        summary = f"Team B won by {team_a_total - team_b_total} strokes"
        pts_a, pts_b = 0.0, matchup.points_for_win
    else:
        winner = 'Push'
        summary = "Tied"
        pts_a, pts_b = matchup.points_for_push, matchup.points_for_push
        
    return {
        "winner": winner,
        "summary": summary,
        "points_a": pts_a,
        "points_b": pts_b,
        "score_a": team_a_total,
        "score_b": team_b_total
    }
