from models import db
from models.models import Matchup, MatchupPlayer, Hole, Score, Tee, Player
from services.handicap import (
    calculate_course_handicap, 
    calculate_playing_handicaps, 
    allocate_pops, 
    calculate_shamble_pops,
    round_half_up
)

def calculate_match_status(matchup_id: int) -> dict:
    matchup = db.session.get(Matchup, matchup_id)
    if not matchup:
        return {"error": "Matchup not found"}
        
    tee = matchup.tee
    comp = matchup.tournament.competition
    team_a_name = comp.team_a_name or "Team A"
    team_b_name = comp.team_b_name or "Team B"
    
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
    
    # Calculate handicaps and pops
    all_holes = Hole.query.filter_by(tee_id=tee.id).order_by(Hole.hole_number).all()
    
    if matchup.format == 'shamble':
        # Shamble uses 75% for 2-person, 65% for 4-person
        team_size = len(team_a_pids)
        shamble_type = "4-person" if team_size >= 4 else "2-person"
        allowance = 0.75 if shamble_type == "2-person" else 0.65
        
        # Course handicaps (Course Net - full allowance adjusted)
        course_playing_handicaps = {}
        for p in players:
            r = tee.rating_female if p.gender == 'female' and tee.rating_female else tee.rating
            s = tee.slope_female if p.gender == 'female' and tee.slope_female else tee.slope
            ch_u = calculate_course_handicap(p.handicap_index, s, r, tee.par, rounded=False)
            course_playing_handicaps[p.id] = round_half_up(ch_u * allowance)
        
        # Match handicaps (Relative to low man in the matchup)
        match_playing_handicaps = calculate_playing_handicaps(course_playing_handicaps)
        
        # Pops for stats (Course Net)
        course_pops_per_hole = {
            p.id: allocate_pops(course_playing_handicaps[p.id], all_holes)
            for p in players
        }
        
        # Pops for Match UI (Relative)
        match_pops_per_hole = {
            p.id: allocate_pops(match_playing_handicaps[p.id], all_holes)
            for p in players
        }

        # For the engine logic: 
        # - course_handicaps (full WHS CH)
        # - playing_handicaps (reduced Match CH for UI)
        # - pops_per_hole (match relative dots)
        # - stats_pops_per_hole (full allowance dots for Net calculation)
        course_handicaps = {}
        for p in players:
            r = tee.rating_female if p.gender == 'female' and tee.rating_female else tee.rating
            s = tee.slope_female if p.gender == 'female' and tee.slope_female else tee.slope
            course_handicaps[p.id] = calculate_course_handicap(p.handicap_index, s, r, tee.par)
        playing_handicaps = match_playing_handicaps
        pops_per_hole = match_pops_per_hole
        stats_pops_per_hole = course_pops_per_hole # Used for net score calculation
    else:
        # Standard calculations
        # CH is used for Course Net
        ch_dict = {}
        for p in players:
            r = tee.rating_female if p.gender == 'female' and tee.rating_female else tee.rating
            s = tee.slope_female if p.gender == 'female' and tee.slope_female else tee.slope
            ch_dict[p.id] = calculate_course_handicap(p.handicap_index, s, r, tee.par)
        
        # PH (Relative) is used for Match Standings UI dots
        playing_handicaps = calculate_playing_handicaps(ch_dict)
        course_handicaps = ch_dict
        
        # Course Pops (Full CH) for stats/leaderboard
        stats_pops_per_hole = {
            p.id: allocate_pops(course_handicaps[p.id], all_holes)
            for p in players
        }
        # Match Pops (Relative) for visual dots
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
        "format": matchup.format,
        "status_string": "All Square",
        "scorecard": [],
        "is_completed": False,
        "player_stats": {
            pid: {
                "course_handicap": course_handicaps[pid],
                "playing_handicap": playing_handicaps[pid],
                "handicap_index": player_map[pid].handicap_index,
                "pops_per_hole": pops_per_hole[pid]
            } for pid in team_a_pids + team_b_pids
        }
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
                # 'net' is course-relative (Full CH) for leaderboard/stats
                course_net = raw_score - stats_pops_per_hole[pid].get(h.hole_number, 0)
                # 'match_net' is match-relative (Reduced PH) for winner determination
                match_net = raw_score - pops_per_hole[pid].get(h.hole_number, 0)
                
                hole_data["players"][pid] = {
                    "raw": raw_score,
                    "net": course_net,
                    "match_net": match_net,
                    "pops": pops_per_hole[pid].get(h.hole_number, 0)
                }
                if pid in team_a_pids:
                    a_scores.append(match_net)
                else:
                    b_scores.append(match_net)
                    
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
        
    # Build status string and structured data
    diff = match_status["team_a_wins"] - match_status["team_b_wins"]
    total_match_holes = hole_end - hole_start + 1
    holes_remaining = total_match_holes - match_status["holes_played"]
    
    is_match_play = matchup.scoring_type == 'match_play'
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

    match_status["display_thru"] = "FINAL" if match_status["is_completed"] else (f"THRU {last_hole_played}" if last_hole_played > 0 else "UPCOMING")
    match_status["leading_team"] = None

    if diff == 0:
        match_status["display_value"] = "AS"
        if match_status["is_completed"]:
            match_status["status_string"] = "Final: AS"
        else:
            match_status["status_string"] = f"AS {thru_label}" if last_hole_played > 0 else "Upcoming"
    elif diff > 0:
        match_status["leading_team"] = "A"
        if is_match_play and diff > holes_remaining:
             val = f"{diff} & {holes_remaining}" if holes_remaining > 0 else f"{diff} UP"
             match_status["display_value"] = val
             match_status["status_string"] = f"{team_a_name} wins {val}"
        elif match_status["is_completed"]:
             match_status["display_value"] = f"{diff} UP"
             match_status["status_string"] = f"Final: {team_a_name} wins {diff} UP"
        else:
            match_status["display_value"] = f"{diff} UP"
            match_status["status_string"] = f"{team_a_name} is {diff} UP {thru_label}"
    else:
        match_status["leading_team"] = "B"
        ad = abs(diff)
        if is_match_play and ad > holes_remaining:
            val = f"{ad} & {holes_remaining}" if holes_remaining > 0 else f"{ad} UP"
            match_status["display_value"] = val
            match_status["status_string"] = f"{team_b_name} wins {val}"
        elif match_status["is_completed"]:
            match_status["display_value"] = f"{ad} UP"
            match_status["status_string"] = f"Final: {team_b_name} wins {ad} UP"
        else:
            match_status["display_value"] = f"{ad} UP"
            match_status["status_string"] = f"{team_b_name} is {ad} UP {thru_label}"

    # Calculate player-level totals for the UI
    for pid in team_a_pids + team_b_pids:
        total_raw = 0
        total_net = 0
        total_par = 0
        holes_scored = 0
        for hd in match_status["scorecard"]:
            p_hd = hd["players"].get(pid)
            if p_hd and p_hd.get("raw") is not None:
                total_raw += p_hd["raw"]
                total_net += p_hd["net"]
                total_par += hd["par"]
                holes_scored += 1
        
        match_status["player_stats"][pid].update({
            "total_raw": total_raw,
            "total_net": total_net,
            "total_par": total_par,
            "holes_scored": holes_scored,
            "to_par": total_raw - total_par if holes_scored > 0 else 0,
            "net_to_par": total_net - total_par if holes_scored > 0 else 0
        })

    return match_status

def calculate_overall_winner(matchup_id: int) -> dict:
    matchup = db.session.get(Matchup, matchup_id)
    if not matchup:
        return {"error": "Matchup not found"}
        
    if matchup.scoring_type == 'match_play':
        ms = calculate_match_status(matchup_id)
        if "error" in ms:
            return ms
            
        diff = ms["team_a_wins"] - ms["team_b_wins"]
        
        # Only award points if the match is completed (mathematically or finished)
        if not ms.get("is_completed"):
            return {
                "winner": None,
                "summary": ms.get("status_string", "Upcoming"),
                "points_a": 0.0,
                "points_b": 0.0
            }

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
        course_handicaps = {}
        for p in players:
            r = tee.rating_female if p.gender == 'female' and tee.rating_female else tee.rating
            s = tee.slope_female if p.gender == 'female' and tee.slope_female else tee.slope
            course_handicaps[p.id] = calculate_course_handicap(p.handicap_index, s, r, tee.par)
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
    
    holes_played = 0
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
        
        if a_scores and b_scores: 
            team_a_total += min(a_scores)
            team_b_total += min(b_scores)
            holes_played += 1
            
    total_match_holes = (matchup.hole_end or 18) - (matchup.hole_start or 1) + 1
    if holes_played < total_match_holes:
        return {
            "winner": None,
            "summary": "In Progress" if holes_played > 0 else "Upcoming",
            "points_a": 0.0,
            "points_b": 0.0,
            "score_a": team_a_total,
            "score_b": team_b_total
        }
            
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
