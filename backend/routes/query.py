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
        'birdies': 0, 'eagles': 0, 'net_birdies': 0, 'strokes': 0, 'holes': 0, 
        'wins': 0, 'losses': 0, 'ties': 0, 'points_earned': 0.0, 
        'name': '', 'team': '', 'team_display_name': '', 'profile_picture': None,
        'total_par': 0, 'total_net_strokes': 0,
        'worst_hole_rel': -99, # Max (raw - par)
    })

    # Track per-tournament-per-tee stats for Best/Worst round
    # {player_id: {tournament_id: {tee_id: {'net': 0, 'par': 0, 'holes': 0, 'name': ''}}}}
    player_round_stats = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {
        'net': 0, 'par': 0, 'holes': 0, 'name': '', 'tee_id': None, 'tee_time': None, 'hole_counts': set()
    })))

    for t in tournaments:
        matchups = Matchup.query.filter_by(tournament_id=t.id).all()
        for m in matchups:
            ms = calculate_match_status(m.id)
            res = calculate_overall_winner(m.id)
            if 'error' not in res:
                team_a_points += res.get('points_a', 0)
                team_b_points += res.get('points_b', 0)

            # Determine status but don't skip score accrual yet
            derived_status = 'completed' if ms.get('is_completed') else ('in_progress' if ms.get('holes_played', 0) > 0 else 'upcoming')
            # If no holes have been scored by EITHER side, we can truly skip it
            if not any(h_st.get('players') for h_st in ms.get('scorecard', [])):
                continue

            # Basic Player Info & Tournament Name
            for pid, player_dict in ms.get('player_stats', {}).items():
                p_stats = player_stats[pid]
                r_box = player_round_stats[pid][t.id][m.tee_id]
                r_box['name'] = t.name
                r_box['tee_id'] = m.tee_id
                # Track the earliest tee time for the round link
                m_time = m.tee_time.isoformat() if m.tee_time else None
                if m_time and (not r_box.get('tee_time') or m_time < r_box['tee_time']):
                    r_box['tee_time'] = m_time
                if p_stats['name'] == '':
                    p = Player.query.get(pid)
                    if p:
                        p_stats['name'] = p.name
                        p_stats['profile_picture'] = p.profile_picture
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
            
            # Scorecard Accrual
            for h_st in ms.get('scorecard', []):
                h_par = h_st.get('par', 0)
                for pid, p_hole_data in h_st.get('players', {}).items():
                    raw = p_hole_data.get('raw')
                    net = p_hole_data.get('net')
                    if raw is not None:
                        p_stats = player_stats[pid]
                        p_stats['strokes'] += raw
                        p_stats['total_net_strokes'] += (net if net is not None else raw)
                        p_stats['total_par'] += h_par
                        p_stats['holes'] += 1
                        
                        # Natural Birdies+
                        diff = raw - h_par
                        if diff <= -2:
                            p_stats['eagles'] += 1
                            p_stats['birdies'] += 1
                        elif diff == -1:
                            p_stats['birdies'] += 1
                        
                        # Net Birdies+
                        net_diff = net - h_par if net is not None else diff
                        if net_diff <= -1:
                            p_stats['net_birdies'] += 1

                        # Worst Hole
                        if diff > p_stats['worst_hole_rel']:
                            p_stats['worst_hole_rel'] = diff

                        # Round Stats (Unique Holes per Tee)
                        r_stats = player_round_stats[pid][t.id][m.tee_id]
                        if h_st['hole_number'] not in r_stats['hole_counts']:
                            r_stats['net'] += (net if net is not None else raw)
                            r_stats['par'] += h_par
                            r_stats['hole_counts'].add(h_st['hole_number'])
                            r_stats['holes'] = len(r_stats['hole_counts'])

            # Points logic
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
            for mp in m_players:
                p = Player.query.get(mp.player_id)
                if p:
                    # Logic for to_par string in this match
                    # (Quickly recalculate or pull from ms if preferred)
                    match_rel = 0
                    for h_st in ms.get('scorecard', []):
                        if str(p.id) in h_st.get('players', {}):
                            phd = h_st['players'][str(p.id)]
                            if phd.get('raw') is not None:
                                match_rel += (phd['raw'] - h_st['par'])
                    
                    to_par_str = 'E' if match_rel == 0 else (f'+{match_rel}' if match_rel > 0 else f'{match_rel}')
                    players.append({
                        "id": p.id,
                        "name": p.name,
                        "profile_picture": p.profile_picture,
                        "team": mp.team,
                        "team_name": (comp.team_a_name or "Team A") if mp.team == 'A' else (comp.team_b_name or "Team B"),
                        "handicap_index": p.handicap_index,
                        "to_par": to_par_str
                    })
            
            if derived_status != 'upcoming':
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
                    "scoring_type": m.scoring_type,
                    "players": players,
                    "competition_name": comp.name,
                    "course_name": m.tee.course.name if m.tee and m.tee.course else "Unknown Course",
                    "points_a": res.get('points_a', 0),
                    "points_b": res.get('points_b', 0),
                    "hole_start": m.hole_start or 1,
                    "hole_end": m.hole_end or 18
                })

    # Prepare Player Data for Awards
    sorted_stats = []
    rounds_data = [] # List of {player_name, tournament_name, net_rel}
    for pid, s in player_stats.items():
        s['player_id'] = pid
        gross_rel = s['strokes'] - s['total_par']
        net_rel = s['total_net_strokes'] - s['total_par']
        s['gross_rel_num'] = gross_rel
        s['net_rel_num'] = net_rel
        s['gross_to_par'] = f"+{gross_rel}" if gross_rel > 0 else ("E" if gross_rel == 0 else str(gross_rel))
        s['net_to_par'] = f"+{net_rel}" if net_rel > 0 else ("E" if net_rel == 0 else str(net_rel))
        sorted_stats.append(s)

        # Flatten rounds for Best/Worst round search
        for tid, r_tees in player_round_stats[pid].items():
            for tee_id, r in r_tees.items():
                if r['holes'] > 0:
                    rounds_data.append({
                        'player_id': pid,
                        'tournament_id': tid,
                        'tee_id': r.get('tee_id'),
                        'tee_time': r.get('tee_time'),
                        'name': s['name'],
                        'tournament_name': r['name'],
                        'net_rel': r['net'] - r['par'],
                        'holes': r['holes']
                    })
    
    # Sort for Leaderboard
    sorted_stats.sort(key=lambda x: (x['points_earned'], -x['gross_rel_num'], x['birdies'], -x['net_rel_num']), reverse=True)

    # Award Calculations
    # MVP
    mvp = sorted_stats[0] if sorted_stats else None
    
    # Birdie King (Most natural birdies+)
    birdie_king = max(sorted_stats, key=lambda x: x['birdies']) if sorted_stats else None
    birdie_king_tie = (len([x for x in sorted_stats if x['birdies'] == birdie_king['birdies']]) > 1) if birdie_king else False

    # Net Birdie King
    net_birdie_king = max(sorted_stats, key=lambda x: x['net_birdies']) if sorted_stats else None
    net_birdie_king_tie = (len([x for x in sorted_stats if x['net_birdies'] == net_birdie_king['net_birdies']]) > 1) if net_birdie_king else False

    # Sandbagger (Lowest total net to par)
    sandbagger = min(sorted_stats, key=lambda x: x['net_rel_num']) if sorted_stats else None
    sandbagger_tie = (len([x for x in sorted_stats if x['net_rel_num'] == sandbagger['net_rel_num']]) > 1) if sandbagger else False

    # Most Honest (Closest to shooting +4 net per round)
    # diff = abs(net_to_par - (holes / 18 * 4))
    def honest_diff(x):
        target = (x['holes'] / 18.0) * 4.0
        return abs(x['net_rel_num'] - target)
    most_honest = min(sorted_stats, key=honest_diff) if sorted_stats else None
    most_honest_tie = (len([x for x in sorted_stats if honest_diff(x) == honest_diff(most_honest)]) > 1) if most_honest else False

    # Worst Hole (Triple or higher)
    worst_hole = max(sorted_stats, key=lambda x: x['worst_hole_rel']) if sorted_stats else None
    worst_hole_tie = (len([x for x in sorted_stats if x['worst_hole_rel'] == worst_hole['worst_hole_rel']]) > 1) if worst_hole else False

    # Filter rounds_data to only include "full enough" rounds if possible, or just all
    # Include any round with at least 9 holes finished
    valid_rounds = [r for r in rounds_data if r['holes'] >= 9]

    best_round = min(valid_rounds, key=lambda x: x['net_rel']) if valid_rounds else None
    best_round_tie = (len([x for x in valid_rounds if x['net_rel'] == best_round['net_rel']]) > 1) if best_round else False

    worst_round = max(valid_rounds, key=lambda x: x['net_rel']) if valid_rounds else None
    worst_round_tie = (len([x for x in valid_rounds if x['net_rel'] == worst_round['net_rel']]) > 1) if worst_round else False

    def fmt_rel(val):
        return f"+{val}" if val > 0 else ("E" if val == 0 else str(val))

    awards = {
        "mvp": {
            "player_id": mvp['player_id'] if mvp else None,
            "name": mvp['name'] if mvp else "N/A",
            "profile_picture": mvp.get('profile_picture') if mvp else None,
            "value": f"{mvp['points_earned']} PTS" if mvp else "0 PTS",
            "subtext": f"{mvp['gross_to_par']} Gross / {mvp['birdies']} Birdies" if mvp else "No stats yet",
            "is_tie": False 
        },
        "birdie_king": {
            "player_id": birdie_king['player_id'] if birdie_king else None,
            "name": birdie_king['name'] if birdie_king else "N/A",
            "profile_picture": birdie_king.get('profile_picture') if birdie_king else None,
            "value": f"{birdie_king['birdies']} Birdies" if birdie_king else "0 Birdies",
            "is_tie": birdie_king_tie
        },
        "net_birdie_king": {
            "player_id": net_birdie_king['player_id'] if net_birdie_king else None,
            "name": net_birdie_king['name'] if net_birdie_king else "N/A",
            "profile_picture": net_birdie_king.get('profile_picture') if net_birdie_king else None,
            "value": f"{net_birdie_king['net_birdies']} Net Birdies" if net_birdie_king else "0 Birdies",
            "is_tie": net_birdie_king_tie
        },
        "sandbagger": {
            "player_id": sandbagger['player_id'] if sandbagger else None,
            "name": sandbagger['name'] if sandbagger else "N/A",
            "profile_picture": sandbagger.get('profile_picture') if sandbagger else None,
            "value": sandbagger['net_to_par'] if sandbagger else "E",
            "subtext": "Lowest Total Net",
            "is_tie": sandbagger_tie
        },
        "most_honest": {
            "player_id": most_honest['player_id'] if most_honest else None,
            "name": most_honest['name'] if most_honest else "N/A",
            "profile_picture": most_honest.get('profile_picture') if most_honest else None,
            "value": most_honest['net_to_par'] if most_honest else "E",
            "subtext": f"Target: {fmt_rel(int((most_honest['holes']/18.0)*4))}" if most_honest else "Target: +4",
            "is_tie": most_honest_tie
        },
        "worst_hole": {
            "player_id": worst_hole['player_id'] if worst_hole else None,
            "name": worst_hole['name'] if worst_hole else "N/A",
            "value": fmt_rel(worst_hole['worst_hole_rel']) if worst_hole else "E",
            "is_tie": worst_hole_tie if worst_hole and worst_hole['worst_hole_rel'] >= 3 else False,
            "hidden": worst_hole['worst_hole_rel'] < 3 if worst_hole else True
        },
        "best_round": {
            "tournament_id": best_round['tournament_id'] if best_round else None,
            "tee_id": best_round['tee_id'] if best_round else None,
            "tee_time": best_round['tee_time'] if best_round else None,
            "player_id": best_round['player_id'] if best_round else None,
            "name": best_round['name'] if best_round else "N/A",
            "value": fmt_rel(best_round['net_rel']) if best_round else "E",
            "subtext": best_round['tournament_name'] if best_round else "No rounds finished",
            "is_tie": best_round_tie
        },
        "worst_round": {
            "tournament_id": worst_round['tournament_id'] if worst_round else None,
            "tee_id": worst_round['tee_id'] if worst_round else None,
            "tee_time": worst_round['tee_time'] if worst_round else None,
            "player_id": worst_round['player_id'] if worst_round else None,
            "name": worst_round['name'] if worst_round else "N/A",
            "profile_picture": player_stats[worst_round['player_id']].get('profile_picture') if worst_round else None,
            "value": fmt_rel(worst_round['net_rel']) if worst_round else "E",
            "subtext": worst_round['tournament_name'] if worst_round else "No rounds finished",
            "is_tie": worst_round_tie
        }
    }

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
        "player_stats": sorted_stats,
        "awards": awards
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
    player_id_param = request.args.get('player_id')
    tee = db.session.get(Tee, tee_id)
    if not tee:
        return jsonify({"error": "Tee not found"}), 404

    # Get all matchups for this tournament and tee
    matchups = Matchup.query.filter_by(
        tournament_id=tournament_id,
        tee_id=tee_id
    ).all()

    # Filter by player_id if provided (useful for Awards/History split rounds)
    if player_id_param:
        try:
            pid = int(player_id_param)
            matchups = [m for m in matchups if any(mp.player_id == pid for mp in m.player_links)]
        except ValueError:
            pass

    # Filter by tee_time if provided
    elif tee_time_param and tee_time_param != 'null':
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

                # Use data directly from the match engine 
                raw = None
                net = None
                pops = 0
                handicap_index = 0
                total_pops = 0

                if m.id in matchup_stats:
                    ms = matchup_stats[m.id]
                    # Player general stats
                    p_st_gen = ms.get('player_stats', {}).get(mp.player_id, {})
                    handicap_index = p_st_gen.get('handicap_index', 0)
                    total_pops = p_st_gen.get('playing_handicap', 0)
                    
                    # Pull pops from the full 18-hole mapping in player_stats
                    pops = p_st_gen.get('pops_per_hole', {}).get(h.hole_number, 0)
                    
                    # Hole-specific stats (raw/net)
                    h_st = next((sh for sh in ms['scorecard'] if sh['hole_number'] == h.hole_number), None)
                    if h_st:
                        p_st_hole = h_st['players'].get(mp.player_id)
                        if p_st_hole:
                            raw = p_st_hole.get('raw')
                            net = p_st_hole.get('net')

                p = player_map.get(mp.player_id)
                hole_data["players"][str(mp.player_id)] = {
                    "name": p.name if p else "Unknown",
                    "team": mp.team,
                    "score": raw,
                    "net": net,
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
    
    # Consolidate player totals
    player_totals = {}
    for pid in player_ids:
        grand_raw = 0
        grand_net = 0
        grand_par = 0
        h_played = 0
        for m_id, ms in matchup_stats.items():
            st = ms.get('player_stats', {}).get(pid)
            if st:
                grand_raw += st.get('total_raw', 0)
                grand_net += st.get('total_net', 0)
                grand_par += st.get('total_par', 0)
                h_played += st.get('holes_scored', 0)
        
        player_totals[str(pid)] = {
            "total_raw": grand_raw,
            "total_net": grand_net,
            "total_par": grand_par,
            "holes_played": h_played,
            "to_par": grand_raw - grand_par if h_played > 0 else 0,
            "net_to_par": grand_net - grand_par if h_played > 0 else 0
        }

    return jsonify({
        "course_name": course.name if course else "Unknown",
        "tee_name": tee.name,
        "tee_time": matchups[0].tee_time.isoformat() if matchups[0].tee_time else None,
        "current_hole": current_hole,
        "scorecard": scorecard_data,
        "player_totals": player_totals,
        "format": matchups[0].format if matchups else 'individual',
        "scoring_type": matchups[0].scoring_type if matchups else 'match_play'
    }), 200
