from flask import Blueprint, jsonify
from services.match_engine import calculate_match_status

query_bp = Blueprint('query', __name__)

@query_bp.route('/matchups/<int:matchup_id>', methods=['GET'])
def get_matchup(matchup_id):
    # This will use the match_engine to return formatted live data
    # For now, it's a placeholder until we write the service
    status = calculate_match_status(matchup_id)
    return jsonify(status), 200
