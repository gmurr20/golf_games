from flask import Blueprint, request, jsonify, current_app
from models import db
from models.models import (
    Player, Matchup, MatchupPlayer, Score, Hole, Tournament, Tee, Course, Competition
)
from services.handicap import calculate_course_handicap, calculate_playing_handicaps, allocate_pops
from services.match_engine import calculate_match_status, calculate_overall_winner
from collections import defaultdict
from datetime import datetime

player_bp = Blueprint('player', __name__)


@player_bp.route('/players/list', methods=['GET'])
def list_players():
    """Return players from the active competition (scoped by master password)."""
    admin_key = current_app.config['MASTER_PASSWORD']
    comp = Competition.query.filter_by(admin_key=admin_key).first()
    if comp:
        players = Player.query.filter_by(competition_id=comp.id).all()
    else:
        players = Player.query.all()
    return jsonify([
        {"id": p.id, "name": p.name, "team": p.team, "handicap_index": p.handicap_index, "profile_picture": p.profile_picture}
        for p in players
    ]), 200


@player_bp.route('/competition/active', methods=['GET'])
def get_active_competition():
    """Return the active competition and tournament name."""
    admin_key = current_app.config['MASTER_PASSWORD']
    comp = Competition.query.filter_by(admin_key=admin_key).first()
    if not comp:
        # Fallback to first if admin key doesn't match for some reason
        comp = Competition.query.first()
    
    if not comp:
        return jsonify({"name": "Golf Games", "tournament": None}), 200
        
    tourney = Tournament.query.filter_by(competition_id=comp.id).first()
    
    return jsonify({
        "name": comp.name,
        "tournament_name": tourney.name if tourney else None
    }), 200


@player_bp.route('/players/<int:player_id>/rounds', methods=['GET'])
def get_player_rounds(player_id):
    """
    Return 'rounds' for a player. A round = group of matchups sharing
    the same tournament + tee + tee_time. Sorted by tee_time ascending.
    """
    player = db.session.get(Player, player_id)
    if not player:
        return jsonify({"error": "Player not found"}), 404

    # Find all matchup_player entries for this player
    mp_entries = MatchupPlayer.query.filter_by(player_id=player_id).all()
    matchup_ids = [mp.matchup_id for mp in mp_entries]

    if not matchup_ids:
        return jsonify([]), 200

    matchups = Matchup.query.filter(Matchup.id.in_(matchup_ids)).all()

    # Group matchups by (tee_id, tee_time) — not tournament_id, since
    # the admin creates a new tournament per matchup batch
    round_groups = defaultdict(list)
    for m in matchups:
        tee_time_key = m.tee_time.isoformat() if m.tee_time else "none"
        key = (m.tee_id, tee_time_key)
        round_groups[key].append(m)

    rounds = []
    for (tee_id, tee_time_key), group_matchups in round_groups.items():
        # Use first matchup's tournament for display name
        tournament = db.session.get(Tournament, group_matchups[0].tournament_id)
        tee = db.session.get(Tee, tee_id)
        course = db.session.get(Course, tee.course_id) if tee else None

        # Calculate total holes and completion
        all_holes = set()
        for m in group_matchups:
            for h in range(m.hole_start or 1, (m.hole_end or 18) + 1):
                all_holes.add(h)

        total_holes = len(all_holes)

        # Count completed holes uniquely using a dictionary of scores
        scored_holes_for_round = Score.query.filter(
            Score.matchup_id.in_([m.id for m in group_matchups]),
            Score.player_id == player_id
        ).all()
        
        distinct_scores = {s.hole_number: s.strokes for s in scored_holes_for_round}
        completed_holes = len(distinct_scores)
        
        total_strokes = sum(distinct_scores.values())
        
        holes_obj = Hole.query.filter_by(tee_id=tee_id).all() if tee else []
        hole_pars = {h.hole_number: h.par for h in holes_obj}
        par_for_played = sum(hole_pars.get(h_num, 4) for h_num in distinct_scores.keys())
        to_par = total_strokes - par_for_played

        # Derive round status
        if completed_holes == 0:
            status = "upcoming"
        elif completed_holes >= total_holes:
            status = "completed"
        else:
            status = "in_progress"

        # Build matchup summaries with opponents
        matchup_summaries = []
        for m in sorted(group_matchups, key=lambda x: x.hole_start or 1):
            all_mps = MatchupPlayer.query.filter_by(matchup_id=m.id).all()
            my_team = None
            for mp in all_mps:
                if mp.player_id == player_id:
                    my_team = mp.team
                    break

            opponents = []
            teammates = []
            for mp in all_mps:
                if mp.player_id == player_id:
                    continue
                p = db.session.get(Player, mp.player_id)
                if p:
                    if mp.team == my_team:
                        teammates.append({"id": p.id, "name": p.name})
                    else:
                        opponents.append({"id": p.id, "name": p.name})

            # Get match result for match_play formats
            match_result = None
            if completed_holes > 0:
                if m.scoring_type == 'match_play':
                    ms = calculate_match_status(m.id)
                    if my_team and 'error' not in ms:
                        opp_team = 'B' if my_team == 'A' else 'A'
                        diff = ms['team_a_wins'] - ms['team_b_wins']
                        my_diff = diff if my_team == 'A' else -diff
                        total_match_holes = (m.hole_end or 18) - (m.hole_start or 1) + 1
                        holes_remaining = total_match_holes - ms['holes_played']
    
                        if ms['holes_played'] == 0:
                            match_result = None
                        elif my_diff == 0:
                            if holes_remaining == 0:
                                match_result = 'A/S'
                            else:
                                match_result = f'AS thru {ms["holes_played"]}'
                        elif my_diff > 0:
                            if my_diff > holes_remaining or holes_remaining == 0:
                                match_result = f'Won {my_diff}&{holes_remaining}' if holes_remaining > 0 else f'{my_diff} UP'
                            else:
                                match_result = f'{my_diff} UP thru {ms["holes_played"]}'
                        else:
                            ad = abs(my_diff)
                            if ad > holes_remaining or holes_remaining == 0:
                                match_result = f'Lost {ad}&{holes_remaining}' if holes_remaining > 0 else f'{ad} DN'
                            else:
                                match_result = f'{ad} DN thru {ms["holes_played"]}'
                elif m.scoring_type == 'stroke_play':
                    res = calculate_overall_winner(m.id)
                    if 'error' not in res and res.get('score_a') is not None:
                        my_score = res['score_a'] if my_team == 'A' else res['score_b']
                        opp_score = res['score_b'] if my_team == 'A' else res['score_a']
                        if res['winner'] == 'Push':
                            match_result = f"Tied {my_score} ({my_score})"
                        elif res['winner'] == my_team:
                            match_result = f"Won by {opp_score - my_score} ({my_score})"
                        else:
                            match_result = f"Lost by {my_score - opp_score} ({my_score})"

            matchup_summaries.append({
                "id": m.id,
                "hole_start": m.hole_start or 1,
                "hole_end": m.hole_end or 18,
                "format": m.format,
                "use_handicaps": m.use_handicaps if m.use_handicaps is not None else True,
                "status": m.status,
                "opponents": opponents,
                "teammates": teammates,
                "match_result": match_result,
            })

        tee_time_val = group_matchups[0].tee_time
        tee_time_epoch = int(tee_time_val.timestamp()) if tee_time_val else 0
        # Use the first matchup's tournament_id for routing purposes
        first_tournament_id = group_matchups[0].tournament_id

        rounds.append({
            "round_id": f"tee{tee_id}_{tee_time_epoch}",
            "tournament_id": first_tournament_id,
            "tee_id": tee_id,
            "tournament_name": tournament.name if tournament else "Unknown",
            "course_name": course.name if course else "Unknown",
            "tee_name": tee.name if tee else "Unknown",
            "tee_time": tee_time_val.isoformat() if tee_time_val else None,
            "status": status,
            "holes_completed": completed_holes,
            "total_holes": total_holes,
            "total_strokes": total_strokes,
            "to_par": to_par,
            "matchups": matchup_summaries,
        })

    # Sort by status (in progress, upcoming, completed) then tee_time ascending
    status_priority = {"in_progress": 0, "upcoming": 1, "completed": 2}
    rounds.sort(key=lambda r: (status_priority.get(r["status"], 3), r["tee_time"] or "9999"))

    return jsonify(rounds), 200


@player_bp.route('/players/<int:player_id>/round/<int:tournament_id>/<int:tee_id>/scorecard', methods=['GET'])
def get_round_scorecard(player_id, tournament_id, tee_id):
    """
    Return the full scorecard for a player's round.
    Optional query param: tee_time (ISO string) to disambiguate same-course rounds.
    """
    tee_time_param = request.args.get('tee_time')

    player = db.session.get(Player, player_id)
    if not player:
        return jsonify({"error": "Player not found"}), 404

    tee = db.session.get(Tee, tee_id)
    if not tee:
        return jsonify({"error": "Tee not found"}), 404

    # Get all matchups for this player with this tee
    mp_entries = MatchupPlayer.query.filter_by(player_id=player_id).all()
    matchup_ids = [mp.matchup_id for mp in mp_entries]

    matchups = Matchup.query.filter(
        Matchup.id.in_(matchup_ids),
        Matchup.tee_id == tee_id,
    ).all()

    # Filter by tee_time if provided
    if tee_time_param and tee_time_param != 'null':
        try:
            target_tt = datetime.fromisoformat(tee_time_param)
            matchups = [m for m in matchups if m.tee_time and abs((m.tee_time - target_tt).total_seconds()) < 60]
        except ValueError:
            pass
    elif not tee_time_param or tee_time_param == 'null':
        # No tee_time specified — filter to matchups with no tee_time
        matchups = [m for m in matchups if m.tee_time is None]

    if not matchups:
        return jsonify({"error": "No matchups found for this round"}), 404

    # Gather all holes for this tee
    holes = Hole.query.filter_by(tee_id=tee_id).order_by(Hole.hole_number).all()

    # Determine all players involved across all matchups in this round
    all_player_ids = set()
    matchup_map = {}  # hole_number -> matchup
    for m in sorted(matchups, key=lambda x: x.hole_start or 1):
        mps = MatchupPlayer.query.filter_by(matchup_id=m.id).all()
        for mp in mps:
            all_player_ids.add(mp.player_id)
        for h_num in range(m.hole_start or 1, (m.hole_end or 18) + 1):
            matchup_map[h_num] = m

    # Get player info
    players_data = {}
    for pid in all_player_ids:
        p = db.session.get(Player, pid)
        if p:
            players_data[pid] = {
                "id": p.id,
                "name": p.name,
                "handicap_index": p.handicap_index,
                "team": p.team,
            }

    # Fetch match status for each matchup to get correct pops/handicaps
    matchup_stats = {}
    for m in matchups:
        ms = calculate_match_status(m.id)
        if "error" not in ms:
            matchup_stats[m.id] = ms

    # Fetch all existing scores for these matchups
    all_matchup_ids = [m.id for m in matchups]
    scores = Score.query.filter(Score.matchup_id.in_(all_matchup_ids)).all()
    scores_lookup = {}
    for s in scores:
        scores_lookup[(s.hole_number, s.player_id)] = s.strokes

    # Determine team assignment for this player
    my_team = None
    for m in matchups:
        mps = MatchupPlayer.query.filter_by(matchup_id=m.id, player_id=player_id).first()
        if mps:
            my_team = mps.team
            break

    # Build per-hole scorecard
    scorecard = []
    for h in holes:
        matchup = matchup_map.get(h.hole_number)
        if not matchup:
            continue

        # Get players relevant to this hole's matchup
        hole_mps = MatchupPlayer.query.filter_by(matchup_id=matchup.id).all()
        hole_player_ids = [mp.player_id for mp in hole_mps]

        hole_data = {
            "hole_number": h.hole_number,
            "par": h.par,
            "yardage": h.yardage,
            "handicap_index": h.handicap_index,
            "matchup_id": matchup.id,
            "players": {},
        }

        for pid in hole_player_ids:
            pdata = players_data.get(pid, {})
            mp_entry = next((mp for mp in hole_mps if mp.player_id == pid), None)
            
            # Use data directly from the match engine 
            raw = None
            net = None
            pops = 0
            if matchup.id in matchup_stats:
                ms = matchup_stats[matchup.id]
                # Player general stats
                p_st_gen = ms.get('player_stats', {}).get(pid, {})
                # Pull pops from the full 18-hole mapping in player_stats
                pops = p_st_gen.get('pops_per_hole', {}).get(h.hole_number, 0)

                # Find hole in ms scorecard for scores
                h_st = next((sh for sh in ms['scorecard'] if sh['hole_number'] == h.hole_number), None)
                if h_st:
                    p_st = h_st['players'].get(pid)
                    if p_st:
                        raw = p_st.get('raw')
                        net = p_st.get('net')

            hole_data["players"][str(pid)] = {
                "name": pdata.get("name", "Unknown"),
                "team": mp_entry.team if mp_entry else None,
                "is_me": pid == player_id,
                "pops": pops,
                "score": raw,
                "net": net
            }

        scorecard.append(hole_data)

    course = db.session.get(Course, tee.course_id)

    # Compute per-hole match play results and overall match results
    match_results_data = []
    for m in sorted(matchups, key=lambda x: x.hole_start or 1):
        if m.scoring_type == 'match_play':
            ms = calculate_match_status(m.id)
            if 'error' not in ms:
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

    # Inject match results into scorecard hole data
    for hole_data in scorecard:
        hole_data['match_result'] = None
        for mr in match_results_data:
            hr = mr['hole_results'].get(hole_data['hole_number'])
            if hr is not None:
                hole_data['match_result'] = hr

    # Consolidate player totals across all matchups in this round
    player_totals = {}
    for pid, pdata in players_data.items():
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

    use_handicaps = any(m.use_handicaps for m in matchups)
    return jsonify({
        "player_id": player_id,
        "player_name": player.name,
        "my_team": my_team,
        "tournament_id": tournament_id,
        "tee_id": tee_id,
        "course_name": course.name if course else "Unknown",
        "tee_name": tee.name,
        "tee_par": tee.par,
        "use_handicaps": use_handicaps,
        "scorecard": scorecard,
        "player_totals": player_totals,
        "match_results": match_results_data,
        "format": matchups[0].format if matchups else 'individual',
        "scoring_type": matchups[0].scoring_type if matchups else 'match_play'
    }), 200


@player_bp.route('/players/<int:player_id>/stats', methods=['GET'])
def get_player_stats(player_id):
    """
    Return comprehensive stats for a player:
    - Aggregate Birdie+ (Gross and Net)
    - Match Record (W-L-T)
    - Total Competition Points
    - Round History
    - Matchup History
    """
    player = db.session.get(Player, player_id)
    if not player:
        return jsonify({"error": "Player not found"}), 404

    # Determine Active Competition (scoped by admin_key)
    admin_key = current_app.config['MASTER_PASSWORD']
    comp = Competition.query.filter_by(admin_key=admin_key).first()
    if not comp:
        comp = Competition.query.first()
        
    if not comp:
        return jsonify({"error": "No competition found"}), 404

    # Get all tournaments for this competition
    tournaments = Tournament.query.filter_by(competition_id=comp.id).all()
    tournament_ids = [t.id for t in tournaments]

    # Determine Team (A or B)
    team_letter = ""
    team_display = ""
    if player.team:
        if player.team == comp.team_a_name:
            team_letter = "A"
            team_display = comp.team_a_name
        elif player.team == comp.team_b_name:
            team_letter = "B"
            team_display = comp.team_b_name
        else:
            team_letter = player.team
            team_display = player.team

    # Initialize stats
    stats = {
        "player_id": player.id,
        "name": player.name,
        "profile_picture": player.profile_picture,
        "handicap_index": player.handicap_index,
        "team": team_letter,
        "team_display_name": team_display,
        "gross_birdies_plus": 0,
        "net_birdies_plus": 0,
        "wins": 0,
        "losses": 0,
        "ties": 0,
        "total_points": 0.0,
        "rounds": [],
        "matchups": []
    }

    # Fetch all matchups for this player in these tournaments
    mp_entries = MatchupPlayer.query.filter(
        MatchupPlayer.player_id == player_id
    ).all()
    
    matchup_ids = [mp.matchup_id for mp in mp_entries]
    all_matchups = Matchup.query.filter(
        Matchup.id.in_(matchup_ids),
        Matchup.tournament_id.in_(tournament_ids)
    ).all()
    
    matchup_lookup = {m.id: m for m in all_matchups}

    # Group matchups by round (tee_id, tee_time)
    round_groups = defaultdict(list)
    for m in all_matchups:
        tee_time_key = m.tee_time.isoformat() if m.tee_time else "none"
        key = (m.tee_id, tee_time_key)
        round_groups[key].append(m)

    # Process Stats and Records
    for m in all_matchups:
        # Match Status & Results
        ms = calculate_match_status(m.id)
        res = calculate_overall_winner(m.id)
        
        my_team = next((mp.team for mp in mp_entries if mp.matchup_id == m.id), None)
        
        if res.get('winner') and ms.get('is_completed'):
            if res['winner'] == 'Push':
                stats['ties'] += 1
                stats['total_points'] += m.points_for_push
            elif res['winner'] == my_team:
                stats['wins'] += 1
                stats['total_points'] += m.points_for_win
            else:
                stats['losses'] += 1

        # Scores for Birdie+ counters
        if 'scorecard' in ms:
            for h_st in ms['scorecard']:
                # The match engine might use int keys; jsonify converts to str keys later.
                # Since we are calling it internally, we check both.
                p_hole = h_st['players'].get(player_id) or h_st['players'].get(str(player_id))
                
                if p_hole and p_hole.get('raw') is not None:
                    h_par = h_st.get('par', 0)
                    if p_hole['raw'] <= h_par - 1:
                        stats['gross_birdies_plus'] += 1
                    if p_hole.get('net') is not None and p_hole['net'] <= h_par - 1:
                        stats['net_birdies_plus'] += 1

        # Matchup Item for list
        opponents = []
        for mp in MatchupPlayer.query.filter_by(matchup_id=m.id).all():
            if mp.player_id != player_id and mp.team != my_team:
                opp = db.session.get(Player, mp.player_id)
                if opp: opponents.append(opp.name)

        matchup_result = "Upcoming"
        if ms.get('holes_played', 0) > 0:
            matchup_result = ms.get('display_value', 'In Progress')
            if ms.get('display_thru'):
                matchup_result += f" {ms['display_thru']}"

        stats['matchups'].append({
            "id": m.id,
            "tournament_id": m.tournament_id,
            "tee_id": m.tee_id,
            "tee_time": m.tee_time.isoformat() if m.tee_time else None,
            "course_name": m.tee.course.name if m.tee and m.tee.course else "Unknown",
            "format": m.format,
            "opponents": opponents,
            "result": matchup_result,
            "is_completed": ms.get('is_completed', False)
        })

    # Round History
    for (tee_id, tee_time_key), group_matchups in round_groups.items():
        tee = db.session.get(Tee, tee_id)
        course = tee.course if tee else None
        
        # Calculate total holes and completion
        all_holes = set()
        for m in group_matchups:
            for h in range(m.hole_start or 1, (m.hole_end or 18) + 1):
                all_holes.add(h)
        
        total_holes = len(all_holes)
        
        # Use scorecard logic to get consistent totals
        raw_scores = {}
        net_scores = {}
        pars = {}
        
        for m in group_matchups:
            ms = calculate_match_status(m.id)
            if 'scorecard' in ms:
                for h_st in ms['scorecard']:
                    h_num = h_st['hole_number']
                    p_hole = h_st['players'].get(player_id) or h_st['players'].get(str(player_id))
                    if p_hole and p_hole.get('raw') is not None:
                        raw_scores[h_num] = p_hole['raw']
                        net_scores[h_num] = p_hole['net']
                        pars[h_num] = h_st['par']

        completed_holes = len(raw_scores)
        if completed_holes == 0: continue # Skip if no scores entered

        gross_total = sum(raw_scores.values())
        net_total = sum(net_scores.values())
        par_total = sum(pars.values())
        
        to_par = gross_total - par_total
        net_to_par = net_total - par_total

        stats['rounds'].append({
            "tournament_id": group_matchups[0].tournament_id,
            "tee_id": tee_id,
            "tee_time": group_matchups[0].tee_time.isoformat() if group_matchups[0].tee_time else None,
            "course_name": course.name if course else "Unknown",
            "tee_name": tee.name if tee else "Unknown",
            "gross_score": gross_total,
            "net_score": net_total,
            "to_par": f"+{to_par}" if to_par > 0 else ("E" if to_par == 0 else str(to_par)),
            "net_to_par": f"+{net_to_par}" if net_to_par > 0 else ("E" if net_to_par == 0 else str(net_to_par)),
            "completed_holes": completed_holes,
            "total_holes": total_holes
        })

    # Sort historical lists
    stats['rounds'].sort(key=lambda r: r['tee_time'] or "0", reverse=True)
    stats['matchups'].sort(key=lambda m: m['tee_time'] or "0", reverse=True)

    return jsonify(stats), 200


@player_bp.route('/matchups/<int:matchup_id>/finalize', methods=['POST'])
def finalize_matchup(matchup_id):
    """
    Validate that all holes for all players in the matchup have scores,
    then mark the matchup as completed.
    """
    matchup = db.session.get(Matchup, matchup_id)
    if not matchup:
        return jsonify({"error": "Matchup not found"}), 404
        
    # Get all players in this matchup
    mps = MatchupPlayer.query.filter_by(matchup_id=matchup_id).all()
    player_ids = [mp.player_id for mp in mps]
    
    # Determine the range of holes
    hole_start = matchup.hole_start or 1
    hole_end = matchup.hole_end or 18
    
    # Check every hole for every player
    for h_num in range(hole_start, hole_end + 1):
        for pid in player_ids:
            score = Score.query.filter_by(
                matchup_id=matchup_id,
                player_id=pid,
                hole_number=h_num
            ).first()
            if not score:
                p = db.session.get(Player, pid)
                player_name = p.name if p else "Unknown Player"
                return jsonify({
                    "error": "Incomplete Scores",
                    "message": f"Hole {h_num} is missing a score for {player_name}.",
                    "missing_hole": h_num
                }), 400
                
    # If all scores are present, update status
    matchup.status = 'completed'
    db.session.commit()
    
    return jsonify({"status": "success", "message": "Matchup finalized"}), 200


@player_bp.route('/scores/batch', methods=['POST'])
def batch_upsert_scores():
    """Accept an array of scores and upsert them all."""
    data = request.json
    if not isinstance(data, list):
        data = data.get('scores', [])

    results = []
    for entry in data:
        score = Score.query.filter_by(
            matchup_id=entry['matchup_id'],
            player_id=entry['player_id'],
            hole_number=entry['hole_number'],
        ).first()

        if score:
            if entry.get('strokes') is None:
                db.session.delete(score)
            else:
                score.strokes = entry['strokes']
        else:
            if entry.get('strokes') is not None:
                score = Score(
                    matchup_id=entry['matchup_id'],
                    player_id=entry['player_id'],
                    hole_number=entry['hole_number'],
                    strokes=entry['strokes'],
                )
                db.session.add(score)

        results.append({"matchup_id": entry['matchup_id'], "hole": entry['hole_number'], "player_id": entry['player_id']})

    db.session.commit()
    return jsonify({"status": "success", "saved": results}), 200
