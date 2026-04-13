from app import create_app
from models.models import Matchup, Player, MatchupPlayer
from services.match_engine import calculate_match_status

app = create_app()
with app.app_context():
    matchups = Matchup.query.all()
    for m in matchups:
        print(f"Matchup {m.id}: format={m.format}, scoring={m.scoring_type}")
        ms = calculate_match_status(m.id)
        for pid, stats in ms.get('player_stats', {}).items():
            print(f"  Player {pid}: CH={stats['course_handicap']}, PH={stats['playing_handicap']}")
