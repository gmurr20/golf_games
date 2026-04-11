from flask import Blueprint, jsonify, current_app, request
from models.models import Competition, Tournament, Matchup, Score, Player, Tee, MatchupPlayer
from services.match_engine import calculate_match_status, calculate_overall_winner
from services.handicap import calculate_course_handicap, allocate_pops
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
    
    player_stats = defaultdict(lambda: {
        'birdies': 0, 'eagles': 0, 'strokes': 0, 'holes': 0, 
        'wins': 0, 'losses': 0, 'ties': 0, 'points_earned': 0.0, 
        'name': '', 'team': '', 'team_display_name': '',
        'total_par': 0, 'total_net_strokes': 0
    })

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
            for pid, player_dict in ms.get('player_stats', {}).items():
                p_stats = player_stats[pid]
                if p_stats['name'] == '':
                    p = Player.query.get(pid)
                    if p:
                        p_stats['name'] = p.name
                        team_str = p.team or ''
                        if team_str == comp.team_a_name:
                            p_stats['team'] = 'A'
                            p_stats['team_display_name'] = comp.team_a_name
                        elif team_str == comp.team_b_name:
                            p_stats['team'] = 'B'
                            p_stats['team_display_name'] = comp.team_b_name
                        else:
                            p_stats['team'] = team_str
                            p_stats['team_display_name'] = team_str

            m_players = MatchupPlayer.query.filter_by(matchup_id=m.id).all()
            players_in_match = Player.query.filter(Player.id.in_([mp.player_id for mp in m_players])).all()
            all_holes = m.tee.holes
            player_course_pops = {}
            for p in players_in_match:
                ch = calculate_course_handicap(p.handicap_index, m.tee.slope, m.tee.rating, m.tee.par)
                player_course_pops[p.id] = allocate_pops(ch, all_holes)

            player_match_to_par = {}
            for h_st in ms.get('scorecard', []):
                h_par = h_st.get('par', 0)
                for pid, p_hole_data in h_st.get('players', {}).items():
                    if pid not in player_match_to_par:
                        player_match_to_par[pid] = 0
                    raw = p_hole_data.get('raw')
                    net = p_hole_data.get('net')
                    if raw is not None:
                        player_match_to_par[pid] += (raw - h_par)
                        
                        # Accrue live overall player stats using matchplay net scores!
                        p_stats = player_stats[pid]
                        p_stats['strokes'] += raw
                        p_stats['total_net_strokes'] += (net if net is not None else raw)
                        p_stats['total_par'] += h_par
                        p_stats['holes'] += 1
                        
                        diff = raw - h_par
                        if diff <= -2:
                            p_stats['eagles'] += 1
                            p_stats['birdies'] += 1
                        elif diff == -1:
                            p_stats['birdies'] += 1

            # Match display summary filtering
            if derived_status == 'upcoming':
                continue
                
            winner = res.get('winner')
            if winner and derived_status == 'completed':
                for mp in m_players:
                    p_stats = player_stats[mp.player_id]
                    if winner == 'Push':
                        p_stats['ties'] += 1
                        p_stats['points_earned'] += m.points_for_push
                    elif winner == mp.team:
                        p_stats['wins'] += 1
                        p_stats['points_earned'] += m.points_for_win
                    else:
                        p_stats['losses'] += 1

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
                "display_value": ms.get('display_value'),
                "display_thru": ms.get('display_thru'),
                "leading_team": ms.get('leading_team'),
                "format": m.format,
                "players": players,
                "competition_name": comp.name,
                "points_a": res.get('points_a', 0),
                "points_b": res.get('points_b', 0),
                "hole_start": m.hole_start or 1,
                "hole_end": m.hole_end or 18
            })

    # Convert stats to a list and sort
    sorted_stats = []
    for pid, s in player_stats.items():
        s['player_id'] = pid
        
        # Calculate final relative to par numbers
        gross_rel = s['strokes'] - s['total_par']
        net_rel = s['total_net_strokes'] - s['total_par']
        
        s['gross_to_par'] = f"+{gross_rel}" if gross_rel > 0 else ("E" if gross_rel == 0 else str(gross_rel))
        s['net_to_par'] = f"+{net_rel}" if net_rel > 0 else ("E" if net_rel == 0 else str(net_rel))
        
        sorted_stats.append(s)
    
    # Sort by points earned descending, then wins, then net_to_par
    sorted_stats.sort(key=lambda x: (x['points_earned'], x['wins'], -x['birdies']), reverse=True)

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
                handicap_index = 0
                total_pops = 0
                if m.id in matchup_stats:
                    match_st = matchup_stats[m.id]
                    p_st = match_st.get('player_stats', {}).get(mp.player_id, {})
                    handicap_index = p_st.get('handicap_index', 0)
                    total_pops = p_st.get('playing_handicap', 0)
                    print(total_pops, h.handicap_index)
                    pops = 1 if h.handicap_index <= total_pops else 0
                hole_data["players"][str(mp.player_id)] = {
                    "name": p.name if p else "Unknown",
                    "team": mp.team,
                    "score": scores_lookup.get((h.hole_number, mp.player_id)),
                    "pops": pops,
                    "handicap_index": handicap_index,
                    "total_pops": total_pops
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
