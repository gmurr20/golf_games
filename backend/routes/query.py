from flask import Blueprint, jsonify, current_app, request
from models.models import Competition, Tournament, Matchup, Score, Player, Tee, MatchupPlayer
from services.match_engine import calculate_match_status, calculate_overall_winner
from services.handicap import calculate_course_handicap, allocate_pops
from collections import defaultdict

query_bp = Blueprint('query', __name__)

@query_bp.route('/matchups/<int:matchup_id>', methods=['GET'])
def get_matchup(matchup_id):
    status = calculate_match_status(matchup_id)
    m = Matchup.query.get(matchup_id)
    if m and m.tee and m.tee.course:
        status['course_logo'] = m.tee.course.logo
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

    # Get the latest/active tournament for this competition
    tourney = Tournament.query.filter_by(competition_id=comp.id).order_by(Tournament.start_date.desc()).first()
    tournaments = [tourney] if tourney else []
    tournament_ids = [t.id for t in tournaments]

    team_a_points = 0.0
    team_b_points = 0.0
    total_points_available = 0.0
    matches = []
    
    player_stats = defaultdict(lambda: {
        'birdies': 0, 'eagles': 0, 'net_birdies': 0, 'strokes': 0, 'holes': 0, 
        'wins': 0, 'losses': 0, 'ties': 0, 'points_earned': 0.0, 
        'name': '', 'team': '', 'team_display_name': '', 'profile_picture': None,
        'total_par': 0, 'total_net_strokes': 0,
        'worst_hole_rel': -99, # Max (raw - par)
        'worst_hole_num': None,
        'worst_hole_course': '',
        'worst_hole_tournament_id': None,
        'worst_hole_tee_id': None,
        'worst_hole_tee_time': None,
        'eagle_details': []
    })

    # Track per-tournament-per-tee stats for Best/Worst round
    # {player_id: {tournament_id: {tee_id: {'net': 0, 'par': 0, 'gross': 0, 'holes': 0, 'name': ''}}}}
    player_round_stats = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {
        'net': 0, 'par': 0, 'gross': 0, 'holes': 0, 'name': '', 'tee_id': None, 'tee_time': None, 'hole_counts': set()
    })))

    freeloader_candidates = []

    for t in tournaments:
        matchups = Matchup.query.filter_by(tournament_id=t.id).order_by(Matchup.tee_time, Matchup.hole_start, Matchup.id).all()
        for m in matchups:
            total_points_available += float(m.points_for_win or 0.0)
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
            seen_player_holes = defaultdict(set) # {pid: set(hole_numbers)}
            for h_st in ms.get('scorecard', []):
                h_par = h_st.get('par', 0)
                h_num = h_st['hole_number']
                for pid, p_hole_data in h_st.get('players', {}).items():
                    raw = p_hole_data.get('raw')
                    net = p_hole_data.get('net')
                    if raw is not None:
                        p_stats = player_stats[pid]
                        r_stats = player_round_stats[pid][t.id][m.tee_id]
                        
                        # Use uniqueness check to avoid double-counting overlapping matchups
                        if h_num not in seen_player_holes[pid]:
                            p_stats['strokes'] += raw
                            p_stats['total_net_strokes'] += (net if net is not None else raw)
                            p_stats['total_par'] += h_par
                            p_stats['holes'] += 1
                            
                            # Natural Birdies+
                            diff = raw - h_par
                            if diff <= -2:
                                p_stats['eagles'] += 1
                                p_stats['birdies'] += 1
                                p_stats['eagle_details'].append({
                                    'hole_number': h_num,
                                    'course': m.tee.course.name if m.tee and m.tee.course else 'Unknown Course',
                                    'tournament_id': t.id,
                                    'tee_id': m.tee_id,
                                    'tee_time': m.tee_time.isoformat() if m.tee_time else None
                                })
                            elif diff == -1:
                                p_stats['birdies'] += 1
                            
                            # Net Birdies+
                            net_diff = net - h_par if net is not None else diff
                            if net_diff <= -1:
                                p_stats['net_birdies'] += 1

                            # Worst Hole
                            if diff > p_stats['worst_hole_rel']:
                                p_stats['worst_hole_rel'] = diff
                                p_stats['worst_hole_num'] = h_num
                                p_stats['worst_hole_course'] = m.tee.course.name if m.tee and m.tee.course else "Unknown Course"
                                p_stats['worst_hole_tournament_id'] = t.id
                                p_stats['worst_hole_tee_id'] = m.tee_id
                                p_stats['worst_hole_tee_time'] = m.tee_time.isoformat() if m.tee_time else None

                            # Round Stats (Unique Holes per Tee)
                            if h_num not in r_stats['hole_counts']:
                                r_stats['net'] += (net if net is not None else raw)
                                r_stats['gross'] += raw
                                r_stats['par'] += h_par
                                r_stats['hole_counts'].add(h_num)
                                r_stats['holes'] = len(r_stats['hole_counts'])
                            
                            seen_player_holes[pid].add(h_num)

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

                # Freeloader logic (match play, completed, and team win)
                if m.scoring_type == 'match_play' and winner != 'Push':
                    winning_players = [mp for mp in m_players if mp.team == winner]
                    if len(winning_players) == 2:
                        pid1 = winning_players[0].player_id
                        pid2 = winning_players[1].player_id
                        losing_players = [mp for mp in m_players if mp.team != winner]
                        
                        contrib1 = 0.0
                        contrib2 = 0.0
                        
                        for hd in ms.get('scorecard', []):
                            if hd.get("winner") is not None:
                                opp_scores = []
                                for lp in losing_players:
                                    p_hd = hd["players"].get(lp.player_id)
                                    if p_hd and p_hd.get("match_net") is not None:
                                        opp_scores.append(p_hd["match_net"])
                                
                                opp_best = min(opp_scores) if opp_scores else None
                                s1 = hd["players"].get(pid1, {}).get("match_net")
                                s2 = hd["players"].get(pid2, {}).get("match_net")
                                
                                if hd["winner"] == winner: # Winning team won the hole
                                    p1_won = (s1 is not None) and (opp_best is None or s1 < opp_best)
                                    p2_won = (s2 is not None) and (opp_best is None or s2 < opp_best)
                                    if p1_won and p2_won:
                                        contrib1 += 1.0
                                        contrib2 += 1.0
                                    elif p1_won:
                                        contrib1 += 1.0
                                    elif p2_won:
                                        contrib2 += 1.0
                                elif hd["winner"] == "Push": # Halved the hole
                                    p1_tied = (s1 is not None) and (opp_best is not None and s1 == opp_best)
                                    p2_tied = (s2 is not None) and (opp_best is not None and s2 == opp_best)
                                    if p1_tied and p2_tied:
                                        contrib1 += 0.5
                                        contrib2 += 0.5
                                    elif p1_tied:
                                        contrib1 += 1.0
                                    elif p2_tied:
                                        contrib2 += 1.0
                                        
                        if contrib1 != contrib2:
                            if contrib1 < contrib2:
                                freeloader_id = pid1
                                partner_id = pid2
                            else:
                                freeloader_id = pid2
                                partner_id = pid1
                                
                            diff = abs(contrib1 - contrib2)
                            p_fl = Player.query.get(freeloader_id)
                            p_pt = Player.query.get(partner_id)
                            if p_fl and p_pt:
                                freeloader_candidates.append({
                                    "freeloader_id": freeloader_id,
                                    "freeloader_name": p_fl.name,
                                    "freeloader_profile_picture": p_fl.profile_picture,
                                    "partner_id": partner_id,
                                    "partner_name": p_pt.name,
                                    "freeloader_contrib": min(contrib1, contrib2),
                                    "partner_contrib": max(contrib1, contrib2),
                                    "diff": diff,
                                    "tournament_id": t.id,
                                    "tee_id": m.tee_id,
                                    "tee_time": m.tee_time.isoformat() if m.tee_time else None,
                                    "course_name": m.tee.course.name if m.tee and m.tee.course else "Unknown Course"
                                })

            # Match summary for display
            players = []
            for mp in m_players:
                p = Player.query.get(mp.player_id)
                if p:
                    # Logic for to_par string in this match
                    # (Quickly recalculate or pull from ms if preferred)
                    match_rel = 0
                    for h_st in ms.get('scorecard', []):
                        if p.id in h_st.get('players', {}):
                            phd = h_st['players'][p.id]
                            if phd.get('raw') is not None:
                                match_rel += (phd['raw'] - h_st['par'])
                    
                    to_par_str = 'E' if match_rel == 0 else (f'+{match_rel}' if match_rel > 0 else f'{match_rel}')
                    players.append({
                        "id": p.id,
                        "name": p.name,
                        "profile_picture": p.profile_picture,
                        "team": mp.team,
                        "team_name": (comp.team_a_name or "Team A") if mp.team == 'A' else (comp.team_b_name or "Team B"),
                        "handicap_index": mp.handicap_index if mp.handicap_index is not None else p.handicap_index,
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
                    "course_logo": m.tee.course.logo if m.tee and m.tee.course else None,
                    "points_a": res.get('points_a', 0),
                    "points_b": res.get('points_b', 0),
                    "hole_start": m.hole_start or 1,
                    "hole_end": m.hole_end or 18
                })

    target_to_win = (total_points_available / 2.0) + 0.5 if total_points_available > 0 else 0.0
    team_a_needed = max(0.0, target_to_win - team_a_points) if total_points_available > 0 else 0.0
    team_b_needed = max(0.0, target_to_win - team_b_points) if total_points_available > 0 else 0.0
    
    is_decided = False
    winning_team = None
    if total_points_available > 0:
        if team_a_points >= target_to_win:
            is_decided = True
            winning_team = 'A'
        elif team_b_points >= target_to_win:
            is_decided = True
            winning_team = 'B'
        else:
            # Check if all matches in the tournament are completed
            all_completed = True
            for t in tournaments:
                matchups = Matchup.query.filter_by(tournament_id=t.id).all()
                for m in matchups:
                    m_status = calculate_match_status(m.id)
                    if not m_status.get('is_completed'):
                        all_completed = False
                        break
                if not all_completed:
                    break
            if all_completed:
                is_decided = True
                if team_a_points > team_b_points:
                    winning_team = 'A'
                elif team_b_points > team_a_points:
                    winning_team = 'B'
                else:
                    winning_team = 'Tie'

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
                        'gross_rel': r['gross'] - r['par'],
                        'holes': r['holes']
                    })
    
    # Sort for Leaderboard
    sorted_stats.sort(key=lambda x: (x['points_earned'], -x['net_rel_num'], -x['gross_rel_num'], x['birdies']), reverse=True)

    # Award Calculations
    # MVP
    mvp = sorted_stats[0] if sorted_stats else None
    
    # Birdie King (Most natural birdies+)
    birdie_king = max(sorted_stats, key=lambda x: x['birdies']) if sorted_stats else None
    birdie_king_tie = (len([x for x in sorted_stats if x['birdies'] == birdie_king['birdies']]) > 1) if (birdie_king and birdie_king['birdies'] > 0) else False

    # Net Birdie King
    net_birdie_king = max(sorted_stats, key=lambda x: x['net_birdies']) if sorted_stats else None
    net_birdie_king_tie = (len([x for x in sorted_stats if x['net_birdies'] == net_birdie_king['net_birdies']]) > 1) if (net_birdie_king and net_birdie_king['net_birdies'] > 0) else False

    # Best Golfer (Lowest cumulative gross relative to par)
    active_players = [x for x in sorted_stats if x.get('holes', 0) > 0]
    best_golfer = min(active_players, key=lambda x: x['gross_rel_num']) if active_players else None
    best_golfer_tie = (len([x for x in active_players if x['gross_rel_num'] == best_golfer['gross_rel_num']]) > 1) if best_golfer else False


    # Worst Hole (Triple or higher)
    worst_hole = max(sorted_stats, key=lambda x: x['worst_hole_rel']) if sorted_stats else None
    worst_hole_tie = (len([x for x in sorted_stats if x['worst_hole_rel'] == worst_hole['worst_hole_rel']]) > 1) if worst_hole else False

    # Filter rounds_data to only include "full enough" rounds if possible, or just all
    # Include any round with at least 9 holes finished
    valid_rounds = [r for r in rounds_data if r['holes'] >= 9]
    if valid_rounds:
        max_holes = max(r['holes'] for r in valid_rounds)
        valid_rounds = [r for r in valid_rounds if r['holes'] == max_holes]

    best_round = min(valid_rounds, key=lambda x: x['net_rel']) if valid_rounds else None
    best_round_tie = (len([x for x in valid_rounds if x['net_rel'] == best_round['net_rel']]) > 1) if best_round else False

    worst_round = max(valid_rounds, key=lambda x: x['net_rel']) if valid_rounds else None
    worst_round_tie = (len([x for x in valid_rounds if x['net_rel'] == worst_round['net_rel']]) > 1) if worst_round else False

    best_round_gross = min(valid_rounds, key=lambda x: x['gross_rel']) if valid_rounds else None
    best_round_gross_tie = (len([x for x in valid_rounds if x['gross_rel'] == best_round_gross['gross_rel']]) > 1) if best_round_gross else False

    def fmt_rel(val):
        return f"+{val}" if val > 0 else ("E" if val == 0 else str(val))

    # Eagle King calculation
    eagle_king = max(sorted_stats, key=lambda x: x['eagles']) if sorted_stats else None
    eagle_king_tie = (len([x for x in sorted_stats if x['eagles'] == eagle_king['eagles']]) > 1) if (eagle_king and eagle_king['eagles'] > 0) else False
    total_eagles = sum(x['eagles'] for x in sorted_stats) if sorted_stats else 0

    # Matchplay Blowout calculation
    blowouts = []
    for t in tournaments:
        matchups = Matchup.query.filter_by(tournament_id=t.id).all()
        for m in matchups:
            if m.scoring_type == 'match_play':
                ms = calculate_match_status(m.id)
                if ms.get('is_completed'):
                    diff = ms["team_a_wins"] - ms["team_b_wins"]
                    lead = abs(diff)
                    if lead > 0:
                        total_match_holes = (m.hole_end or 18) - (m.hole_start or 1) + 1
                        holes_played = ms["holes_played"]
                        remaining = total_match_holes - holes_played
                        
                        # Determine winning team and players
                        winner_team = 'A' if diff > 0 else 'B'
                        m_players = MatchupPlayer.query.filter_by(matchup_id=m.id).all()
                        winning_players = [mp.player for mp in m_players if mp.team == winner_team]
                        winner_names = " & ".join([p.name for p in winning_players])
                        profile_pic = winning_players[0].profile_picture if winning_players else None
                        
                        val_str = f"{lead} & {remaining}" if remaining > 0 else f"{lead} UP"
                        course_name = m.tee.course.name if m.tee and m.tee.course else "Unknown Course"
                        subtext = f"{val_str} at {course_name}"
                        
                        blowouts.append({
                            'id': m.id,
                            'tournament_id': t.id,
                            'tee_id': m.tee_id,
                            'tee_time': m.tee_time.isoformat() if m.tee_time else None,
                            'display_value': val_str,
                            'winner_names': winner_names,
                            'profile_picture': profile_pic,
                            'subtext': subtext,
                            'remaining': remaining,
                            'lead': lead
                        })

    best_blowout = None
    blowout_tie = False
    if blowouts:
        blowouts.sort(key=lambda x: (x['remaining'], x['lead']), reverse=True)
        best_blowout = blowouts[0]
        blowout_tie = len([b for b in blowouts if b['remaining'] == best_blowout['remaining'] and b['lead'] == best_blowout['lead']]) > 1

    best_freeloader = None
    freeloader_tie = False
    if freeloader_candidates:
        freeloader_candidates.sort(key=lambda x: x['diff'], reverse=True)
        best_freeloader = freeloader_candidates[0]
        freeloader_tie = len([c for c in freeloader_candidates if c['diff'] == best_freeloader['diff']]) > 1

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
        "best_golfer": {
            "player_id": best_golfer['player_id'] if best_golfer else None,
            "name": best_golfer['name'] if best_golfer else "N/A",
            "profile_picture": best_golfer.get('profile_picture') if best_golfer else None,
            "value": best_golfer['gross_to_par'] if best_golfer else "E",
            "subtext": f"{best_golfer['holes']} Holes" if best_golfer else "No holes played",
            "is_tie": best_golfer_tie
        },

        "worst_hole": {
            "player_id": worst_hole['player_id'] if worst_hole else None,
            "name": worst_hole['name'] if worst_hole else "N/A",
            "profile_picture": worst_hole.get('profile_picture') if worst_hole else None,
            "value": fmt_rel(worst_hole['worst_hole_rel']) if worst_hole else "E",
            "is_tie": worst_hole_tie if worst_hole and worst_hole['worst_hole_rel'] >= 3 else False,
            "hidden": worst_hole['worst_hole_rel'] < 3 if worst_hole else True,
            "subtext": f"Hole {worst_hole['worst_hole_num']} at {worst_hole['worst_hole_course']}" if worst_hole and worst_hole['worst_hole_num'] else "No stats yet",
            "tournament_id": worst_hole['worst_hole_tournament_id'] if worst_hole else None,
            "tee_id": worst_hole['worst_hole_tee_id'] if worst_hole else None,
            "tee_time": worst_hole['worst_hole_tee_time'] if worst_hole else None
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
        "best_round_gross": {
            "tournament_id": best_round_gross['tournament_id'] if best_round_gross else None,
            "tee_id": best_round_gross['tee_id'] if best_round_gross else None,
            "tee_time": best_round_gross['tee_time'] if best_round_gross else None,
            "player_id": best_round_gross['player_id'] if best_round_gross else None,
            "name": best_round_gross['name'] if best_round_gross else "N/A",
            "value": fmt_rel(best_round_gross['gross_rel']) if best_round_gross else "E",
            "subtext": best_round_gross['tournament_name'] if best_round_gross else "No rounds finished",
            "is_tie": best_round_gross_tie
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
        },
        "eagle_king": {
            "player_id": eagle_king['player_id'] if (eagle_king and eagle_king['eagles'] > 0) else None,
            "name": eagle_king['name'] if (eagle_king and eagle_king['eagles'] > 0) else "N/A",
            "profile_picture": eagle_king.get('profile_picture') if (eagle_king and eagle_king['eagles'] > 0) else None,
            "value": f"{eagle_king['eagles']} Eagles" if (eagle_king and eagle_king['eagles'] > 0) else "0 Eagles",
            "subtext": f"Hole {eagle_king['eagle_details'][0]['hole_number']} at {eagle_king['eagle_details'][0]['course']}" if (eagle_king and eagle_king['eagles'] > 0 and total_eagles == 1 and eagle_king['eagle_details']) else None,
            "tournament_id": eagle_king['eagle_details'][0]['tournament_id'] if (eagle_king and eagle_king['eagles'] > 0 and total_eagles == 1 and eagle_king['eagle_details']) else None,
            "tee_id": eagle_king['eagle_details'][0]['tee_id'] if (eagle_king and eagle_king['eagles'] > 0 and total_eagles == 1 and eagle_king['eagle_details']) else None,
            "tee_time": eagle_king['eagle_details'][0]['tee_time'] if (eagle_king and eagle_king['eagles'] > 0 and total_eagles == 1 and eagle_king['eagle_details']) else None,
            "is_tie": eagle_king_tie,
            "hidden": not (eagle_king and eagle_king['eagles'] > 0)
        },
        "matchplay_blowout": {
            "tournament_id": best_blowout['tournament_id'] if best_blowout else None,
            "tee_id": best_blowout['tee_id'] if best_blowout else None,
            "tee_time": best_blowout['tee_time'] if best_blowout else None,
            "name": best_blowout['winner_names'] if best_blowout else "N/A",
            "profile_picture": best_blowout['profile_picture'] if best_blowout else None,
            "value": best_blowout['display_value'] if best_blowout else "N/A",
            "subtext": best_blowout['subtext'] if best_blowout else "No match play blowouts yet",
            "is_tie": blowout_tie,
            "hidden": best_blowout is None
        },
        "freeloader": {
            "player_id": best_freeloader['freeloader_id'] if best_freeloader else None,
            "name": best_freeloader['freeloader_name'] if best_freeloader else "N/A",
            "profile_picture": best_freeloader.get('freeloader_profile_picture') if best_freeloader else None,
            "value": f"{best_freeloader['diff']:.1f} PTS Diff" if best_freeloader else "0 PTS Diff",
            "subtext": f"Carried by {best_freeloader['partner_name']} ({best_freeloader['partner_contrib']:.1f} vs {best_freeloader['freeloader_contrib']:.1f}) at {best_freeloader['course_name']}" if best_freeloader else "No match play partners yet",
            "is_tie": freeloader_tie,
            "hidden": best_freeloader is None,
            "tournament_id": best_freeloader['tournament_id'] if best_freeloader else None,
            "tee_id": best_freeloader['tee_id'] if best_freeloader else None,
            "tee_time": best_freeloader['tee_time'] if best_freeloader else None
        }
    }

    return jsonify({
        "competition": {
            "id": comp.id,
            "name": comp.name,
            "team_a_name": comp.team_a_name or "Team A",
            "team_b_name": comp.team_b_name or "Team B",
            "team_a_points": team_a_points,
            "team_b_points": team_b_points,
            "points_to_win": target_to_win,
            "team_a_points_needed": team_a_needed,
            "team_b_points_needed": team_b_needed,
            "total_points_available": total_points_available,
            "is_decided": is_decided,
            "winning_team": winning_team
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
    matchup_id_param = request.args.get('matchup_id')
    tee = db.session.get(Tee, tee_id)
    if not tee:
        return jsonify({"error": "Tee not found"}), 404

    # Get all matchups for this tournament and tee
    matchups = Matchup.query.filter_by(
        tournament_id=tournament_id,
        tee_id=tee_id
    ).order_by(Matchup.tee_time, Matchup.hole_start, Matchup.id).all()

    # Filter by matchup_id if provided
    if matchup_id_param:
        try:
            mid = int(matchup_id_param)
            matchups = [m for m in matchups if m.id == mid]
        except ValueError:
            pass

    # Filter by player_id if provided (useful for Awards/History split rounds)
    if player_id_param and not matchup_id_param:
        try:
            pid = int(player_id_param)
            matchups = [m for m in matchups if any(mp.player_id == pid for mp in m.player_links)]
        except ValueError:
            pass

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
            elif hole_stats and hole_stats.get('decided_status'):
                hole_data["match_result"] = {
                    "winner": None,
                    "running": hole_stats['decided_status']
                }

        for mp in mps:
            if mp.matchup_id in all_matchup_ids:
                # Find which matchup handles this hole
                m = next((m_obj for m_obj in matchups if m_obj.id == mp.matchup_id), None)
                if not m: continue
                
                # Check if hole is within matchup range
                if h.hole_number < (m.hole_start or 1) or h.hole_number > (m.hole_end or 18):
                    continue

                hole_data["matchup_id"] = m.id

                # Use data directly from the match engine 
                raw = None
                net = None
                pops = 0
                handicap_index = 0
                total_pops = 0
                won_hole = False

                if m.id in matchup_stats:
                    ms = matchup_stats[m.id]
                    # Player general stats
                    p_st_gen = ms.get('player_stats', {}).get(mp.player_id, {})
                    handicap_index = p_st_gen.get('handicap_index', 0)
                    total_pops = p_st_gen.get('course_handicap', 0)
                    
                    # Pull pops from the full 18-hole mapping in player_stats
                    pops = p_st_gen.get('pops_per_hole', {}).get(h.hole_number, 0)
                    
                    # Hole-specific stats (raw/net)
                    h_st = next((sh for sh in ms['scorecard'] if sh['hole_number'] == h.hole_number), None)
                    if h_st:
                        p_st_hole = h_st['players'].get(mp.player_id)
                        if p_st_hole:
                            raw = p_st_hole.get('raw')
                            net = p_st_hole.get('net')
                            won_hole = p_st_hole.get('won_hole', False)

                p = player_map.get(mp.player_id)
                hole_data["players"][str(mp.player_id)] = {
                    "name": p.name if p else "Unknown",
                    "team": mp.team,
                    "score": raw,
                    "net": net,
                    "pops": pops,
                    "handicap_index": handicap_index,
                    "total_pops": total_pops,
                    "won_hole": won_hole,
                    "profile_picture": p.profile_picture if p else None
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

    matchups_serialized = []
    for m in sorted(matchups, key=lambda x: x.hole_start or 1):
        matchups_serialized.append({
            "id": m.id,
            "hole_start": m.hole_start or 1,
            "hole_end": m.hole_end or 18,
            "format": m.format,
            "scoring_type": m.scoring_type,
            "points_for_win": m.points_for_win,
            "points_for_push": m.points_for_push,
        })

    viewer_player_id = None
    if player_id_param:
        try:
            viewer_player_id = int(player_id_param)
        except ValueError:
            pass

    match_results_data = []
    for m in sorted(matchups, key=lambda x: x.hole_start or 1):
        if m.scoring_type == 'match_play':
            ms = matchup_stats.get(m.id)
            if ms and 'error' not in ms:
                my_team = 'A'
                if viewer_player_id:
                    mp_link = next((mp for mp in m.player_links if mp.player_id == viewer_player_id), None)
                    if mp_link:
                        my_team = mp_link.team

                diff = ms['team_a_wins'] - ms['team_b_wins']
                my_diff = diff if my_team == 'A' else -diff
                total_match_holes = (m.hole_end or 18) - (m.hole_start or 1) + 1
                holes_remaining = total_match_holes - ms['holes_played']

                # Final result string
                if ms['holes_played'] == 0:
                    result_str = 'Not Started'
                elif my_diff == 0:
                    result_str = 'A/S' if holes_remaining == 0 else f'AS thru {ms["holes_played"]}'
                elif my_diff > 0:
                    if my_diff > holes_remaining or holes_remaining == 0:
                        result_str = f'Won {my_diff}&{holes_remaining}' if holes_remaining > 0 else f'{my_diff} UP'
                    else:
                        result_str = f'{my_diff} UP thru {ms["holes_played"]}'
                else:
                    ad = abs(my_diff)
                    if ad > holes_remaining or holes_remaining == 0:
                        result_str = f'Lost {ad}&{holes_remaining}' if holes_remaining > 0 else f'{ad} DN'
                    else:
                        result_str = f'{ad} DN thru {ms["holes_played"]}'

                # Per-hole results for this matchup
                hole_results = {}
                running = 0
                for hd in ms['scorecard']:
                    if hd['winner'] == 'A':
                        running += 1
                    elif hd['winner'] == 'B':
                        running -= 1

                    my_running = running if my_team == 'A' else -running

                    if hd['winner'] is None:
                        hole_results[hd['hole_number']] = None
                    elif hd['winner'] == 'Push':
                        hole_results[hd['hole_number']] = {'result': 'halved', 'running': my_running}
                    elif (hd['winner'] == my_team):
                        hole_results[hd['hole_number']] = {'result': 'won', 'running': my_running}
                    else:
                        hole_results[hd['hole_number']] = {'result': 'lost', 'running': my_running}

                match_results_data.append({
                    'matchup_id': m.id,
                    'hole_start': m.hole_start or 1,
                    'hole_end': m.hole_end or 18,
                    'result_string': result_str,
                    'hole_results': hole_results,
                })

    return jsonify({
        "course_name": course.name if course else "Unknown",
        "course_logo": course.logo if course else None,
        "tee_name": tee.name,
        "tee_time": matchups[0].tee_time.isoformat() if matchups[0].tee_time else None,
        "current_hole": current_hole,
        "is_completed": all(stats.get("is_completed", False) for stats in matchup_stats.values()) if matchups else False,
        "scorecard": scorecard_data,
        "player_totals": player_totals,
        "matchups": matchups_serialized,
        "match_results": match_results_data,
        "format": matchups[0].format if matchups else 'individual',
        "scoring_type": matchups[0].scoring_type if matchups else 'match_play'
    }), 200
