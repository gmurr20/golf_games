from flask import Blueprint, jsonify, current_app, request
from models.models import Competition, Tournament, Matchup, Score, Player, Tee, MatchupPlayer
from services.match_engine import calculate_match_status, calculate_overall_winner
from collections import defaultdict

query_bp = Blueprint('query', __name__)

@query_bp.route('/matchups/<int:matchup_id>', methods=['GET'])
def get_matchup(matchup_id):
    status = calculate_match_status(matchup_id)
    return jsonify(status), 200

@query_bp.route('/leaderboard', methods=['GET'])
def get_leaderboard():
    """
    Returns the overall leaderboard for the active competition:
    - Team A vs Team B points
    - List of matches with status
    - Player specific stats (Birdies+, etc)
    """
    admin_key = current_app.config.get('MASTER_PASSWORD')
    comp = Competition.query.filter_by(admin_key=admin_key).first()
    if not comp:
        comp = Competition.query.first()
    
    if not comp:
        return jsonify({"error": "No competition found"}), 404

    # Get all tournaments for this competition
    tournaments = Tournament.query.filter_by(competition_id=comp.id).all()
    tournament_ids = [t.id for t in tournaments]

    team_a_points = 0.0
    team_b_points = 0.0
    matches = []
    
    # Track player stats
    # player_stats = { player_id: { 'birdies': 0, 'eagles': 0, 'strokes': 0, 'holes': 0, 'name': '' } }
    player_stats = defaultdict(lambda: {'birdies': 0, 'eagles': 0, 'strokes': 0, 'holes': 0, 'name': ''})

    for t in tournaments:
        matchups = Matchup.query.filter_by(tournament_id=t.id).all()
        for m in matchups:
            # Match Status for status string and live indicator
            # Match Status for status string and live indicator
            ms = calculate_match_status(m.id)
            
            # Points for the overall team score
            res = calculate_overall_winner(m.id)
            if 'error' not in res:
                team_a_points += res.get('points_a', 0)
                team_b_points += res.get('points_b', 0)

            # Derived status and filtering
            derived_status = 'completed' if ms.get('is_completed') else ('in_progress' if ms.get('holes_played', 0) > 0 else 'upcoming')
            
            # User only wants Live and Completed
            if derived_status == 'upcoming':
                continue

            # Calculate each player's to_par for THIS specific match
            player_match_to_par = {}
            for h_st in ms.get('scorecard', []):
                h_par = h_st.get('par', 0)
                for pid, p_hole_data in h_st.get('players', {}).items():
                    if pid not in player_match_to_par:
                        player_match_to_par[pid] = 0
                    raw = p_hole_data.get('raw')
                    if raw is not None:
                        player_match_to_par[pid] += (raw - h_par)

            # Match summary for display
            players = []
            m_players = MatchupPlayer.query.filter_by(matchup_id=m.id).all()
            for mp in m_players:
                p = Player.query.get(mp.player_id)
                if p:
                    # Format to_par string
                    rel = player_match_to_par.get(p.id, 0)
                    to_par_str = 'E' if rel == 0 else (f'+{rel}' if rel > 0 else f'{rel}')
                    
                    players.append({
                        "id": p.id,
                        "name": p.name,
                        "team": mp.team,
                        "team_name": (comp.team_a_name or "Team A") if mp.team == 'A' else (comp.team_b_name or "Team B"),
                        "handicap_index": p.handicap_index,
                        "to_par": to_par_str
                    })
            
            matches.append({
                "id": m.id,
                "tournament_id": t.id,
                "tee_id": m.tee_id,
                "tee_time": m.tee_time.isoformat() if m.tee_time else None,
                "status": derived_status,
                "status_string": ms.get('status_string', 'Upcoming'),
                "format": m.format,
                "players": players,
                "competition_name": comp.name,
                "points_a": res.get('points_a', 0),
                "points_b": res.get('points_b', 0),
                "hole_start": m.hole_start or 1,
                "hole_end": m.hole_end or 18
            })

    # Calculate player stats from all scores in this competition
    all_matchups = Matchup.query.filter(Matchup.tournament_id.in_(tournament_ids)).all()
    all_matchup_ids = [m.id for m in all_matchups]
    
    all_scores = Score.query.filter(Score.matchup_id.in_(all_matchup_ids)).all()
    
    # Need hole pars to identify birdies/eagles
    # Cache hole pars per tee
    tee_pars = {} # { tee_id: { hole_number: par } }

    for s in all_scores:
        m = next((m for m in all_matchups if m.id == s.matchup_id), None)
        if not m: continue
        
        if m.tee_id not in tee_pars:
            holes = m.tee.holes
            tee_pars[m.tee_id] = {h.hole_number: h.par for h in holes}
        
        par = tee_pars[m.tee_id].get(s.hole_number, 4)
        diff = s.strokes - par
        
        stats = player_stats[s.player_id]
        if stats['name'] == '':
            p = Player.query.get(s.player_id)
            stats['name'] = p.name if p else 'Unknown'
        
        stats['strokes'] += s.strokes
        stats['holes'] += 1
        if diff <= -2:
            stats['eagles'] += 1
            stats['birdies'] += 1 # Eagle is also a birdie or better
        elif diff == -1:
            stats['birdies'] += 1

    # Convert stats to a list and sort
    sorted_stats = []
    for pid, s in player_stats.items():
        s['player_id'] = pid
        # Calculate net or relative to par? 
        # Standard leaderboard often shows "Birdies" as a fun stat.
        sorted_stats.append(s)
    
    # Sort by birdies descending
    sorted_stats.sort(key=lambda x: x['birdies'], reverse=True)

    return jsonify({
        "competition": {
            "id": comp.id,
            "name": comp.name,
            "team_a_name": comp.team_a_name or "Team A",
            "team_b_name": comp.team_b_name or "Team B",
            "team_a_points": team_a_points,
            "team_b_points": team_b_points
        },
        "matches": matches,
        "player_stats": sorted_stats[:10] # Top 10
    }), 200

@query_bp.route('/scorecard/<int:tournament_id>/<int:tee_id>', methods=['GET'])
def get_public_scorecard(tournament_id, tee_id):
    """
    Return a read-only scorecard for a specific tournament tee.
    Optional query param: tee_time (ISO string)
    """
    from models import db
    from models.models import Hole, Score, Tee, Course, Player, MatchupPlayer
    from datetime import datetime
    
    tee_time_param = request.args.get('tee_time')
    tee = db.session.get(Tee, tee_id)
    if not tee:
        return jsonify({"error": "Tee not found"}), 404

    # Get all matchups for this tournament and tee
    matchups = Matchup.query.filter_by(
        tournament_id=tournament_id,
        tee_id=tee_id
    ).all()

    # Filter by tee_time if provided
    if tee_time_param and tee_time_param != 'null':
        try:
            target_tt = datetime.fromisoformat(tee_time_param)
            matchups = [m for m in matchups if m.tee_time and abs((m.tee_time - target_tt).total_seconds()) < 60]
        except ValueError:
            pass

    if not matchups:
        return jsonify({"error": "No matchups found"}), 404

    # Use match engine to get calculated stats (pops, running status) for each matchup
    matchup_stats = {}
    for m in matchups:
        stats = calculate_match_status(m.id)
        if "error" not in stats:
            matchup_stats[m.id] = stats

    # Gather all holes for this tee
    holes = Hole.query.filter_by(tee_id=tee_id).order_by(Hole.hole_number).all()
    all_matchup_ids = [m.id for m in matchups]

    # Get all players involved
    mps = MatchupPlayer.query.filter(MatchupPlayer.matchup_id.in_(all_matchup_ids)).all()
    player_ids = {mp.player_id for mp in mps}
    players = Player.query.filter(Player.id.in_(list(player_ids))).all()
    player_map = {p.id: p for p in players}

    # Get all scores
    scores = Score.query.filter(Score.matchup_id.in_(all_matchup_ids)).all()
    scores_lookup = {}
    for s in scores:
        scores_lookup[(s.hole_number, s.player_id)] = s.strokes

    # Build scorecard
    scorecard_data = []
    
    # Track running match status per matchup
    running_diffs = defaultdict(int)

    for h in holes:
        hole_data = {
            "hole_number": h.hole_number,
            "par": h.par,
            "yardage": h.yardage,
            "handicap_index": h.handicap_index,
            "players": {},
            "match_result": None
        }
        
        # Check if any matchup has results for this hole
        for m_id, stats in matchup_stats.items():
            hole_stats = next((sh for sh in stats.get('scorecard', []) if sh['hole_number'] == h.hole_number), None)
            if hole_stats and hole_stats.get('winner'):
                # Update running diff for THIS specific matchup (Team A win = +1, Team B win = -1)
                if hole_stats['winner'] == 'A': running_diffs[m_id] += 1
                elif hole_stats['winner'] == 'B': running_diffs[m_id] -= 1
                
                hole_data["match_result"] = {
                    "winner": hole_stats['winner'],
                    "running": running_diffs[m_id]
                }

        for mp in mps:
            if mp.matchup_id in all_matchup_ids:
                # Find which matchup handles this hole
                m = next((m_obj for m_obj in matchups if m_obj.id == mp.matchup_id), None)
                if not m: continue
                
                # Check if hole is within matchup range
                if h.hole_number < (m.hole_start or 1) or h.hole_number > (m.hole_end or 18):
                    continue

                p = player_map.get(mp.player_id)
                
                # Get pops from matchup stats
                pops = 0
                if m.id in matchup_stats:
                    hole_st = next((sh for sh in matchup_stats[m.id].get('scorecard', []) if sh['hole_number'] == h.hole_number), None)
                    if hole_st:
                        pops = hole_st.get('players', {}).get(mp.player_id, {}).get('pops', 0)

                hole_data["players"][str(mp.player_id)] = {
                    "name": p.name if p else "Unknown",
                    "team": mp.team,
                    "score": scores_lookup.get((h.hole_number, mp.player_id)),
                    "pops": pops
                }
        
        if hole_data["players"]:
            scorecard_data.append(hole_data)

    course = db.session.get(Course, tee.course_id)
    
    # Determine "Current Hole" for the match (latest hole with a score)
    current_hole = 0
    if scores:
        current_hole = max(s.hole_number for s in scores)
    
    return jsonify({
        "course_name": course.name if course else "Unknown",
        "tee_name": tee.name,
        "tee_time": matchups[0].tee_time.isoformat() if matchups[0].tee_time else None,
        "current_hole": current_hole,
        "scorecard": scorecard_data,
        "format": matchups[0].format if matchups else 'match_play'
    }), 200
