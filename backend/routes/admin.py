import json
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from models import db
from models.models import Competition, Player, Course, Tee, Hole, Tournament, Matchup, MatchupPlayer
from services.match_engine import calculate_overall_winner
from google import genai
from google.genai import types
import base64
from PIL import Image
import io

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/auth', methods=['POST'])
def authenticate():
    data = request.json
    password = data.get('password', '')
    
    if password != current_app.config['MASTER_PASSWORD']:
        return jsonify({"error": "Invalid password"}), 403
    
    # Use the master password as the admin key
    admin_key = current_app.config['MASTER_PASSWORD']
    comp = Competition.query.filter_by(admin_key=admin_key).first()
    
    if not comp:
        comp = Competition(name='Golf Games', admin_key=admin_key)
        db.session.add(comp)
        db.session.flush()
    
    # Ensure a default tournament exists
    tourney = Tournament.query.filter_by(competition_id=comp.id).first()
    if not tourney:
        tourney = Tournament(competition_id=comp.id, name='Main Competition')
        db.session.add(tourney)
    
    db.session.commit()
    
    return jsonify({"admin_key": admin_key, "name": comp.name}), 200

@admin_bp.route('/competitions/settings', methods=['GET', 'PUT'])
def manage_competition():
    admin_key = request.headers.get('admin-key')
    comp = Competition.query.filter_by(admin_key=admin_key).first()
    if not comp: return jsonify({"error": "Unauthorized"}), 403

    if request.method == 'PUT':
        data = request.json
        if 'team_a_name' in data: comp.team_a_name = data['team_a_name']
        if 'team_b_name' in data: comp.team_b_name = data['team_b_name']
        db.session.commit()
    
    return jsonify({
        "name": comp.name,
        "team_a_name": comp.team_a_name or 'Team A',
        "team_b_name": comp.team_b_name or 'Team B'
    }), 200

@admin_bp.route('/players', methods=['POST'])
def create_player():
    data = request.json
    admin_key = request.headers.get('admin-key')
    comp = Competition.query.filter_by(admin_key=admin_key).first()
    if not comp: return jsonify({"error": "Unauthorized"}), 403
    
    player = Player(
        competition_id=comp.id, 
        name=data['name'], 
        handicap_index=data['handicap_index'], 
        team=data.get('team'),
        gender=data.get('gender', 'male')
    )
    db.session.add(player)
    db.session.commit()
    return jsonify({"id": player.id}), 201

@admin_bp.route('/players', methods=['GET'])
def get_players():
    admin_key = request.headers.get('admin-key')
    comp = Competition.query.filter_by(admin_key=admin_key).first()
    if not comp: return jsonify({"error": "Unauthorized"}), 403
    
    players = Player.query.filter_by(competition_id=comp.id).all()
    return jsonify([{"id": p.id, "name": p.name, "handicap_index": p.handicap_index, "team": p.team, "gender": p.gender} for p in players]), 200

@admin_bp.route('/players/<int:id>', methods=['PUT', 'DELETE'])
def manage_player(id):
    admin_key = request.headers.get('admin-key')
    comp = Competition.query.filter_by(admin_key=admin_key).first()
    if not comp: return jsonify({"error": "Unauthorized"}), 403
    
    player = Player.query.filter_by(id=id, competition_id=comp.id).first()
    if not player: return jsonify({"error": "Player not found"}), 404
    
    if request.method == 'DELETE':
        # Find all matchups this player is part of
        matchup_ids = [mp.matchup_id for mp in player.matchup_players]
        for mid in matchup_ids:
            m = Matchup.query.get(mid)
            if m: db.session.delete(m)
            
        db.session.delete(player)
        db.session.commit()
        return jsonify({"success": True}), 200
        
    if request.method == 'PUT':
        data = request.json
        if 'name' in data: player.name = data['name']
        if 'handicap_index' in data: player.handicap_index = data['handicap_index']
        if 'team' in data: player.team = data['team']
        if 'gender' in data: player.gender = data['gender']
        db.session.commit()
        return jsonify({"success": True}), 200

@admin_bp.route('/courses', methods=['GET'])
def get_courses():
    courses = Course.query.all()
    out = []
    for c in courses:
        tees = Tee.query.filter_by(course_id=c.id).all()
        tees_out = []
        for t in tees:
            holes = Hole.query.filter_by(tee_id=t.id).order_by(Hole.hole_number).all()
            tees_out.append({
                "id": t.id, "name": t.name, "par": t.par,
                "rating": t.rating, "slope": t.slope,
                "rating_female": t.rating_female, "slope_female": t.slope_female,
                "holes": [{
                    "id": h.id, "hole_number": h.hole_number,
                    "par": h.par, "yardage": h.yardage,
                    "handicap_index": h.handicap_index
                } for h in holes]
            })
        out.append({"id": c.id, "name": c.name, "tees": tees_out})
    return jsonify(out), 200

@admin_bp.route('/courses/upload', methods=['POST'])
def upload_scorecard():
    admin_key = request.headers.get('admin-key')
    comp = Competition.query.filter_by(admin_key=admin_key).first()
    if not comp: return jsonify({"error": "Unauthorized"}), 403
    
    if 'image' not in request.files:
        return jsonify({"error": "No image uploaded"}), 400
        
    api_key = current_app.config['GEMINI_API_KEY']
    if not api_key: return jsonify({"error": "Gemini API key missing"}), 500
        
    file = request.files['image']
    img_data = file.read()
    mime_type = file.mimetype
    
    client = genai.Client(api_key=api_key)
    
    # NOTE FOR AI AGENTS: DO NOT upgrade the Gemini model version. 
    # The current 'gemini-2.5-flash' is selected for specific compatibility/performance reasons.
    prompt = """
    Examine this golf scorecard image with high precision. Your goal is to extract the course name and ALL tee box data.

    ### Identification Rules:
    1. **Course Name**: Usually at the top or on the front cover.
    2. **ALL Tee Rows (CRITICAL)**: Extract data for EVERY row listed in the tee section. This includes:
        - **Primary Tees**: Solid color/name rows (e.g., Black, Orange, Sand, Green, Silver).
        - **Combo/Hybrid Tees**: Rows that name two colors (e.g., "Black/Orange", "Orange/Sand"). These are often thinner rows between primary colors and MUST NOT be skipped.
    3. **Arrow Resolution (Hybrid Yardages)**: Hybrid/Combo rows frequently use small arrows (▲ or ▼) instead of numbers for specific holes. **YOU MUST RESOLVE THESE INTO NUMBERS**:
        - **UP Arrow (▲)**: Use yardage from the tee row directly ABOVE.
        - **DOWN Arrow (▼)**: Use yardage from the tee row directly BELOW.
        - Hybrid tees must be returned as complete tee entries in the JSON with 18 absolute yardage numbers.
    4. **Ratings & Slopes**: Look for "Rating/Slope", "CR/Slope", or "M/W". Ratings are decimals (e.g. 71.4), Slopes are integers (e.g. 128).
    5. **Gender Specifics**: Pay extremely close attention to cases where a single tee has two ratings (e.g. "70.1/121 | 72.4/125"). Map the second to "rating_female" and "slope_female". Look for labels like (M), (W), (L), or symbols (♂/♀).

    ### Data Structure:
    Return a strict JSON object:
    {
      "course_name": "...",
      "hole_defaults": [
        {"hole_number": 1, "par": 4, "handicap_index": 12} // List all 18 holes here
      ],
      "tees": [
        {
          "tee_name": "...",
          "rating": float, 
          "slope": int,
          "rating_female": float (optional),
          "slope_female": int (optional),
          "yardages": [419, 395, 536, ...], // List all 18 absolute yardages, resolve arrows (▲/▼) into numbers
          "overrides": [
            {"hole_number": 1, "par": 5} // Optional: only if this tee differs from hole_defaults
          ]
        }
      ]
    }
    Extract the 18 pars and handicap indexes into `hole_defaults`. For every tee row, resolve all 18 yardages into the `yardages` array.
    Return ONLY raw JSON, do not use markdown codeblocks. Do not include anything else.
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt, types.Part.from_bytes(data=img_data, mime_type=mime_type)]
        )
        resp_text = response.text.strip()
        if resp_text.startswith('```json'): resp_text = resp_text[7:-3].strip()
        if resp_text.startswith('```'): resp_text = resp_text[3:-3].strip()
        parsed = json.loads(resp_text)
        
        # COMPACT TO VERBOSE EXPANSION:
        # To avoid AI timeouts, the AI returns a compact format which we now expand
        # for compatibility with the rest of the application.
        expanded_tees = []
        hole_defaults = {h['hole_number']: h for h in parsed.get('hole_defaults', [])}
        warnings = []
        
        for tee in parsed.get('tees', []):
            holes = []
            yardages = tee.get('yardages', [])
            overrides = {o['hole_number']: o for o in tee.get('overrides', [])}
            
            for i in range(1, 19):
                # Get the base par/handicap from defaults
                default = hole_defaults.get(i, {})
                # Apply any tee-specific overrides
                override = overrides.get(i, {})
                
                holes.append({
                    "hole_number": i,
                    "par": override.get('par', default.get('par', 4)),
                    "yardage": yardages[i-1] if i-1 < len(yardages) else None,
                    "handicap_index": override.get('handicap_index', default.get('handicap_index', i))
                })
            
            r = tee.get('rating')
            s = tee.get('slope')
            rf = tee.get('rating_female')
            sf = tee.get('slope_female')

            # Fallback logic: Ensure both gender ratings are populated if at least one is present
            if r is None and rf is not None: r = rf
            if s is None and sf is not None: s = sf
            if rf is None and r is not None: rf = r
            if sf is None and s is not None: sf = s

            # If STILL None, we use 72/113 and flag it
            if r is None:
                warnings.append(f"Tee '{tee.get('tee_name')}' missing all ratings, defaulted to 72.0/113.")

            expanded_tees.append({
                "tee_name": tee.get('tee_name'),
                "rating": r if r is not None else 72.0,
                "slope": s if s is not None else 113,
                "rating_female": rf if rf is not None else 72.0,
                "slope_female": sf if sf is not None else 113,
                "holes": holes
            })
            
        return jsonify({
            "course_name": parsed.get('course_name'),
            "tees": expanded_tees,
            "warnings": warnings
        }), 200

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/courses', methods=['POST'])
def create_course():
    admin_key = request.headers.get('admin-key')
    data = request.json
    course = Course(name=data['name'])
    db.session.add(course)
    db.session.commit()
    
    if 'tees' in data:
        for t_data in data['tees']:
            r = t_data.get('rating')
            s = t_data.get('slope')
            rf = t_data.get('rating_female')
            sf = t_data.get('slope_female')

            # Fallback logic: Ensure both gender ratings are populated if at least one is present
            if r is None and rf is not None: r = rf
            if s is None and sf is not None: s = sf
            if rf is None and r is not None: rf = r
            if sf is None and s is not None: sf = s

            tee = Tee(
                course_id=course.id, 
                name=t_data.get('name', 'Main'), 
                rating=r if r is not None else 72.0, 
                slope=s if s is not None else 113,
                rating_female=rf,
                slope_female=sf,
                par=t_data.get('par', 72)
            )

            db.session.add(tee)
            db.session.flush()
            
            if 'holes' in t_data:
                for h_data in t_data['holes']:
                    hole = Hole(
                        tee_id=tee.id,
                        hole_number=h_data['hole_number'],
                        par=h_data['par'],
                        yardage=h_data.get('yardage'),
                        handicap_index=h_data['handicap_index']
                    )
                    db.session.add(hole)
    db.session.commit()
    return jsonify({"id": course.id, "name": course.name}), 201

@admin_bp.route('/courses/<int:id>', methods=['GET'])
def get_course(id):
    c = Course.query.get_or_404(id)
    tees = Tee.query.filter_by(course_id=c.id).all()
    tees_out = []
    for t in tees:
        holes = Hole.query.filter_by(tee_id=t.id).order_by(Hole.hole_number).all()
        tees_out.append({
            "id": t.id, "name": t.name, "par": t.par,
            "rating": t.rating, "slope": t.slope,
            "rating_female": t.rating_female, "slope_female": t.slope_female,
            "holes": [{
                "id": h.id, "hole_number": h.hole_number,
                "par": h.par, "yardage": h.yardage,
                "handicap_index": h.handicap_index
            } for h in holes]
        })
    return jsonify({"id": c.id, "name": c.name, "tees": tees_out}), 200

@admin_bp.route('/courses/<int:id>', methods=['PUT'])
def update_course(id):
    admin_key = request.headers.get('admin-key')
    comp = Competition.query.filter_by(admin_key=admin_key).first()
    if not comp: return jsonify({"error": "Unauthorized"}), 403
    
    c = Course.query.get_or_404(id)
    data = request.json
    if 'name' in data: c.name = data['name']
    db.session.commit()
    return jsonify({"success": True}), 200

@admin_bp.route('/courses/<int:id>', methods=['DELETE'])
def delete_course(id):
    admin_key = request.headers.get('admin-key')
    comp = Competition.query.filter_by(admin_key=admin_key).first()
    if not comp: return jsonify({"error": "Unauthorized"}), 403
    
    c = Course.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    return jsonify({"success": True}), 200

@admin_bp.route('/tees/<int:id>', methods=['PUT'])
def update_tee(id):
    admin_key = request.headers.get('admin-key')
    comp = Competition.query.filter_by(admin_key=admin_key).first()
    if not comp: return jsonify({"error": "Unauthorized"}), 403
    
    tee = Tee.query.get_or_404(id)
    data = request.json
    if 'name' in data: tee.name = data['name']
    if 'rating' in data or 'rating_female' in data:
        r = data.get('rating', tee.rating)
        rf = data.get('rating_female', tee.rating_female)
        # If one is updated to non-null, and the other is null, sync them
        if r is None and rf is not None: r = rf
        if rf is None and r is not None: rf = r
        tee.rating = r if r is not None else 72.0
        tee.rating_female = rf

    if 'slope' in data or 'slope_female' in data:
        s = data.get('slope', tee.slope)
        sf = data.get('slope_female', tee.slope_female)
        if s is None and sf is not None: s = sf
        if sf is None and s is not None: sf = s
        tee.slope = s if s is not None else 113
        tee.slope_female = sf

    if 'par' in data: tee.par = data['par']
    
    if 'holes' in data:
        for h_data in data['holes']:
            hole = Hole.query.get(h_data['id'])
            if hole and hole.tee_id == tee.id:
                if 'par' in h_data: hole.par = h_data['par']
                if 'yardage' in h_data: hole.yardage = h_data['yardage']
                if 'handicap_index' in h_data: hole.handicap_index = h_data['handicap_index']
    
    db.session.commit()
    return jsonify({"success": True}), 200

@admin_bp.route('/matchups', methods=['POST'])
def create_matchup():
    data = request.json
    admin_key = request.headers.get('admin-key')
    comp = Competition.query.filter_by(admin_key=admin_key).first()
    if not comp: return jsonify({"error": "Unauthorized"}), 403
    
    # Validation for 2v2 formats
    if data.get('format') in ['shamble', 'scramble', 'best_ball']:
        teams = data.get('teams', {})
        if len(teams) != 2 or any(len(pids) != 2 for pids in teams.values()):
            return jsonify({"error": f"{data['format'].capitalize()} requires exactly 2 players per team"}), 400
    
    # Validation for Individual (must be 1v1)
    if data.get('format') == 'individual':
        teams = data.get('teams', {})
        if len(teams) != 2 or any(len(pids) != 1 for pids in teams.values()):
            return jsonify({"error": "Individual format requires exactly 1 player per team (1v1)"}), 400
    
    # Use existing tournament for this competition
    tourney = Tournament.query.filter_by(competition_id=comp.id).first()
    if not tourney:
        tourney = Tournament(competition_id=comp.id, name='Main Competition')
        db.session.add(tourney)
        db.session.flush()
    
    tee_time = None
    if data.get('tee_time'):
        try:
            tee_time = datetime.fromisoformat(data['tee_time'])
        except (ValueError, TypeError):
            pass

    matchup = Matchup(
        tournament_id=tourney.id,
        tee_id=data['tee_id'],
        format=data['format'],
        scoring_type=data.get('scoring_type', 'match_play'),
        use_handicaps=data.get('use_handicaps', True),
        points_for_win=data.get('points_for_win', 1.0),
        points_for_push=data.get('points_for_push', 0.5),
        hole_start=data.get('hole_start', 1),
        hole_end=data.get('hole_end', 18),
        tee_time=tee_time,
    )
    db.session.add(matchup)
    db.session.flush()
    
    for team, pids in data['teams'].items():
        for pid in pids: 
            mp = MatchupPlayer(matchup_id=matchup.id, player_id=pid, team=team)
            db.session.add(mp)
            
    db.session.commit()
    return jsonify({"id": matchup.id}), 201

@admin_bp.route('/matchups', methods=['GET'])
def get_matchups():
    admin_key = request.headers.get('admin-key')
    comp = Competition.query.filter_by(admin_key=admin_key).first()
    if not comp: return jsonify({"error": "Unauthorized"}), 403

    tourneys = Tournament.query.filter_by(competition_id=comp.id).all()
    tourney_ids = [t.id for t in tourneys]
    
    if not tourney_ids: return jsonify([]), 200
    
    matchups = Matchup.query.filter(Matchup.tournament_id.in_(tourney_ids)).order_by(Matchup.tee_time, Matchup.id).all()
    
    out = []
    for m in matchups:
        from models.models import Score
        # Dynamically compute completion status using the match engine
        from services.match_engine import calculate_match_status
        ms_data = calculate_match_status(m.id)
        
        if "error" in ms_data:
            actual_status = "error"
        elif ms_data["holes_played"] == 0:
            actual_status = "upcoming"
        elif ms_data.get("is_completed"):
            actual_status = "completed"
        else:
            actual_status = "in_progress"

        players = MatchupPlayer.query.filter_by(matchup_id=m.id).all()
        teams_dict = {}
        for mp in players:
            if mp.team not in teams_dict: teams_dict[mp.team] = []
            teams_dict[mp.team].append(mp.player.name)
            
        hole_label = f"Holes {m.hole_start}-{m.hole_end}" if (m.hole_start != 1 or m.hole_end != 18) else "Full 18"
        
        # Determine player count per team for display
        team_sizes = [len(v) for v in teams_dict.values()]
        is_2v2 = any(s >= 2 for s in team_sizes)
        
        # Calculate winner if completed
        result_data = None
        if actual_status == "completed":
            result_data = calculate_overall_winner(m.id)
            if "error" in result_data:
                result_data = None
                
        out.append({
            "id": m.id,
            "format": m.format,
            "scoring_type": m.scoring_type,
            "use_handicaps": m.use_handicaps if m.use_handicaps is not None else True,
            "is_2v2": is_2v2,
            "course": m.tee.course.name if m.tee else "Unknown Course",
            "tee": m.tee.name if m.tee else "Unknown Tee",
            "status": actual_status,
            "points_for_win": m.points_for_win,
            "points_for_push": m.points_for_push,
            "hole_start": m.hole_start or 1,
            "hole_end": m.hole_end or 18,
            "hole_label": hole_label,
            "tee_time": m.tee_time.isoformat() if m.tee_time else None,
            "tournament_id": m.tournament_id,
            "tee_id": m.tee_id,
            "first_player_id": players[0].player_id if players else None,
            "first_player_name": players[0].player.name if players else "Admin",
            "teams": teams_dict,
            "live_status": ms_data.get("status_string"),
            "result": result_data
        })
    return jsonify(out), 200

@admin_bp.route('/matchups/<int:id>', methods=['DELETE'])
def delete_matchup(id):
    admin_key = request.headers.get('admin-key')
    comp = Competition.query.filter_by(admin_key=admin_key).first()
    if not comp: return jsonify({"error": "Unauthorized"}), 403
    
    matchup = Matchup.query.get_or_404(id)
    # Verify ownership through tournament
    tourney = Tournament.query.get(matchup.tournament_id)
    if not tourney or tourney.competition_id != comp.id:
        return jsonify({"error": "Unauthorized"}), 403
    
    db.session.delete(matchup)
    db.session.commit()
    return jsonify({"success": True}), 200

