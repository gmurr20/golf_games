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
        comp = Competition(name='Murray Cup 2026', admin_key=admin_key)
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
        if 'name' in data: comp.name = data['name']
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
        gender=data.get('gender', 'male'),
        profile_picture=data.get('profile_picture')
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
    return jsonify([{"id": p.id, "name": p.name, "handicap_index": p.handicap_index, "team": p.team, "gender": p.gender, "profile_picture": p.profile_picture} for p in players]), 200

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
        if 'profile_picture' in data: player.profile_picture = data['profile_picture']
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
                "total_yardage": sum(h.yardage for h in holes if h.yardage is not None),
                "holes": [{
                    "id": h.id, "hole_number": h.hole_number,
                    "par": h.par, "yardage": h.yardage,
                    "handicap_index": h.handicap_index
                } for h in holes]
            })
        out.append({"id": c.id, "name": c.name, "logo": c.logo, "tees": tees_out})
    return jsonify(out), 200

@admin_bp.route('/courses/upload', methods=['POST'])
def upload_scorecard():
    admin_key = request.headers.get('admin-key')
    comp = Competition.query.filter_by(admin_key=admin_key).first()
    if not comp: return jsonify({"error": "Unauthorized"}), 403
    
    files = []
    if 'images' in request.files:
        files = request.files.getlist('images')
    elif 'image' in request.files:
        files = request.files.getlist('image')
        
    if not files or len(files) == 0 or (len(files) == 1 and files[0].filename == ''):
        return jsonify({"error": "No image uploaded"}), 400
        
    api_key = current_app.config['GEMINI_API_KEY']
    if not api_key: return jsonify({"error": "Gemini API key missing"}), 500
        
    client = genai.Client(api_key=api_key)
    
    prompt = """
    You are an elite, highly precise golf data extraction and OCR intelligence. You will be provided with one or more images of a golf scorecard.
    Your goal is to extract the course name, all tee box metadata (names, ratings, slopes), and the complete hole-by-hole information (hole number, par, yardage, and handicap index) for each tee.

    Scorecards are complex grids. To guarantee 100% extraction accuracy, you MUST perform your work in two steps: a Transcription Pass and a JSON Generation Pass.

    ---

    ### STEP 1: TRANSCRIPTION PASS (Chain of Thought Scratchpad)
    Before generating any JSON, write out a clean markdown table transcribing each row of the scorecard exactly as it appears in the images.
    1. Identify all columns (e.g., Hole numbers 1-9, OUT, 10-18, IN, TOT).
    2. Transcribe each Tee Box row horizontally in a plain markdown table, showing the exact numbers written under each column.
    3. Check for any arrow symbols (▲ or ▼) or colored dots on the rows. In your scratchpad, explicitly resolve them to the correct yardage number of the row above or below.
    4. Write a brief alignment verification (e.g., "Verified: Tee 'White' has exactly 18 hole yardages, matching the 18 holes").

    ### STEP 2: JSON GENERATION PASS
    Translate your intermediate scratchpad transcription into the final structured JSON object. 
    Summary/aggregate columns (like OUT, IN, TOT, TOTAL, NET) MUST be completely excluded from the individual hole lists. Only include numbered holes (1, 2, 3, etc.).

    Ensure the following keys are populated in your final JSON structure:
    - **course_name**: String. The official course name.
    - **tees**: A list of objects, one for each tee set found.
      - **tee_name**: String (e.g. "Blue", "White/Gold").
      - **rating**: Decimal number (default Men's/general rating).
      - **slope**: Integer (default Men's/general slope).
      - **rating_female**: Decimal number or null.
      - **slope_female**: Integer or null.
      - **holes**: A list of objects, one for each hole.
        - **hole_number**: Integer (1, 2, 3, etc.).
        - **par**: Integer (typically 3, 4, or 5).
        - **yardage**: Integer. Must be resolved to the absolute yardage number.
        - **handicap_index**: Integer (typically 1 to 18).

    ---

    ### TEMPLATE FOR YOUR RESPONSE:

    ### STEP 1: TRANSCRIPTION
    [Your markdown transcription tables go here]

    ### STEP 2: JSON
    ```json
    {
      "course_name": "Name of the Course",
      "tees": [
        {
          "tee_name": "Blue",
          "rating": 71.4,
          "slope": 128,
          "rating_female": null,
          "slope_female": null,
          "holes": [
            {
              "hole_number": 1,
              "par": 4,
              "yardage": 419,
              "handicap_index": 12
            }
          ]
        }
      ]
    }
    ```
    """
    
    try:
        contents = [prompt]
        for file in files:
            img_data = file.read()
            mime_type = file.mimetype
            contents.append(types.Part.from_bytes(data=img_data, mime_type=mime_type))

        try:
            response = client.models.generate_content(
                model='gemini-3.5-flash',
                contents=contents
            )
        except Exception as e:
            # Automatic fallback to gemini-2.5-flash if gemini-3.5-flash is experiencing demand spikes
            print(f"Gemini 3.5 Flash rate-limited or unavailable (falling back to gemini-2.5-flash): {e}")
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=contents
            )
            
        resp_text = response.text.strip()
        
        # Robustly extract JSON block from markdown chain of thought
        import re
        json_match = re.search(r'```json\s*(.*?)\s*```', resp_text, re.DOTALL)
        if json_match:
            resp_text = json_match.group(1).strip()
        else:
            code_match = re.search(r'```\s*(.*?)\s*```', resp_text, re.DOTALL)
            if code_match:
                resp_text = code_match.group(1).strip()
            else:
                start_idx = resp_text.find('{')
                end_idx = resp_text.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    resp_text = resp_text[start_idx:end_idx+1].strip()
                    
        parsed = json.loads(resp_text)
        
        expanded_tees = []
        warnings = []
        
        for tee in parsed.get('tees', []):
            r = tee.get('rating')
            s = tee.get('slope')
            rf = tee.get('rating_female')
            sf = tee.get('slope_female')

            # Fallback logic: Ensure both gender ratings are populated if at least one is present
            if r is None and rf is not None: r = rf
            if s is None and sf is not None: s = sf
            if rf is None and r is not None: rf = r
            if sf is None and s is not None: sf = s

            # If STILL None, we use 72.0/113 and flag it
            if r is None:
                warnings.append(f"Tee '{tee.get('tee_name')}' missing all ratings, defaulted to 72.0/113.")

            holes = []
            if 'holes' in tee and len(tee['holes']) > 0:
                # Direct format: each tee has its own holes list
                for h in tee['holes']:
                    holes.append({
                        "hole_number": int(h.get('hole_number')),
                        "par": int(h.get('par', 4)),
                        "yardage": int(h['yardage']) if h.get('yardage') is not None else None,
                        "handicap_index": int(h.get('handicap_index', h.get('hole_number')))
                    })
            else:
                # Legacy compact format fallback
                hole_defaults = {h['hole_number']: h for h in parsed.get('hole_defaults', [])}
                max_hole = max(hole_defaults.keys()) if hole_defaults else 18
                yardages = tee.get('yardages', [])
                overrides = {o['hole_number']: o for o in tee.get('overrides', [])}
                
                for i in range(1, max_hole + 1):
                    default = hole_defaults.get(i, {})
                    override = overrides.get(i, {})
                    holes.append({
                        "hole_number": i,
                        "par": override.get('par', default.get('par', 4)),
                        "yardage": yardages[i-1] if i-1 < len(yardages) else None,
                        "handicap_index": override.get('handicap_index', default.get('handicap_index', i))
                    })

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
    course_name = data.get('name')
    if not course_name:
        course_name = 'Unknown Course'
    course = Course(name=course_name, logo=data.get('logo'))
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
            "total_yardage": sum(h.yardage for h in holes if h.yardage is not None),
            "holes": [{
                "id": h.id, "hole_number": h.hole_number,
                "par": h.par, "yardage": h.yardage,
                "handicap_index": h.handicap_index
            } for h in holes]
        })
    return jsonify({"id": c.id, "name": c.name, "logo": c.logo, "tees": tees_out}), 200

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

@admin_bp.route('/courses/<int:id>/image', methods=['POST'])
def update_course_image(id):
    admin_key = request.headers.get('admin-key')
    comp = Competition.query.filter_by(admin_key=admin_key).first()
    if not comp: return jsonify({"error": "Unauthorized"}), 403
    
    c = Course.query.get_or_404(id)
    data = request.json
    if 'logo' in data: c.logo = data['logo']
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

    tee_max_hole = db.session.query(db.func.max(Hole.hole_number)).filter_by(tee_id=data['tee_id']).scalar() or 18

    matchup = Matchup(
        tournament_id=tourney.id,
        tee_id=data['tee_id'],
        format=data['format'],
        scoring_type=data.get('scoring_type', 'match_play'),
        use_handicaps=data.get('use_handicaps', True),
        points_for_win=data.get('points_for_win', 1.0),
        points_for_push=data.get('points_for_push', 0.5),
        hole_start=data.get('hole_start', 1),
        hole_end=data.get('hole_end', tee_max_hole),
        tee_time=tee_time,
    )
    db.session.add(matchup)
    db.session.flush()
    
    overrides = data.get('handicap_overrides', {})

    for team, pids in data['teams'].items():
        for pid in pids: 
            # Lock in the handicap: Use override if provided, else current player index
            player = db.session.get(Player, pid)
            hcp_to_lock = player.handicap_index
            if str(pid) in overrides and overrides[str(pid)] is not None:
                try:
                    hcp_to_lock = float(overrides[str(pid)])
                except (ValueError, TypeError):
                    pass

            mp = MatchupPlayer(
                matchup_id=matchup.id, 
                player_id=pid, 
                team=team,
                handicap_index=hcp_to_lock
            )
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
    
    matchups = Matchup.query.filter(Matchup.tournament_id.in_(tourney_ids)).order_by(Matchup.tee_time, Matchup.hole_start, Matchup.id).all()
    
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
            teams_dict[mp.team].append({
                "id": mp.player_id,
                "name": mp.player.name,
                "handicap_index": mp.handicap_index if mp.handicap_index is not None else mp.player.handicap_index
            })
            
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
            "course_logo": m.tee.course.logo if m.tee and m.tee.course else None,
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

@admin_bp.route('/players/<int:player_id>/image', methods=['POST'])
def upload_player_image(player_id):
    admin_key = request.headers.get('admin-key')
    comp = Competition.query.filter_by(admin_key=admin_key).first()
    if not comp: return jsonify({"error": "Unauthorized"}), 403
    
    player = Player.query.filter_by(id=player_id, competition_id=comp.id).first()
    if not player: return jsonify({"error": "Player not found"}), 404
    
    data = request.json
    image_data = data.get('image') # Base64 string
    
    if not image_data:
        return jsonify({"error": "No image data provided"}), 400
        
    player.profile_picture = image_data
    db.session.commit()
    
    return jsonify({"success": True, "profile_picture": player.profile_picture}), 200

