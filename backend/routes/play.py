from flask import Blueprint, request, jsonify
from models import db
from models.models import Score

play_bp = Blueprint('play', __name__)

@play_bp.route('/scores', methods=['POST'])
def upsert_score():
    data = request.json
    # Expected: matchup_id, player_id, hole_number, strokes
    score = Score.query.filter_by(
        matchup_id=data['matchup_id'],
        player_id=data['player_id'],
        hole_number=data['hole_number']
    ).first()
    
    if score:
        score.strokes = data['strokes']
    else:
        score = Score(
            matchup_id=data['matchup_id'],
            player_id=data['player_id'],
            hole_number=data['hole_number'],
            strokes=data['strokes']
        )
        db.session.add(score)
    
    db.session.commit()
    return jsonify({"status": "success", "id": score.id}), 200
