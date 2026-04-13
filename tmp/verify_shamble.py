import os
import sys

# Setup paths
sys.path.append(os.path.join(os.getcwd(), 'backend'))

os.environ['FLASK_MIGRATING'] = '1'

from app import create_app
from models import db
from models.models import Matchup, Player, MatchupPlayer
from services.match_engine import calculate_match_status

def test_shamble_handicaps():
    app = create_app()
    with app.app_context():
        # Find a shamble matchup
        matchup = Matchup.query.filter_by(format='shamble').first()
        if not matchup:
            print("No shamble matchup found in DB.")
            return

        print(f"Testing Matchup ID: {matchup.id} (Format: {matchup.format})")
        status = calculate_match_status(matchup.id)
        
        if 'error' in status:
            print(f"Error: {status['error']}")
            return

        for pid, stats in status['player_stats'].items():
            player = db.session.get(Player, pid)
            print(f"Player: {player.name}")
            print(f"  Handicap Index: {stats['handicap_index']}")
            print(f"  Course Handicap (Adjusted): {stats['course_handicap']}")
            print(f"  Playing Handicap (Relative): {stats['playing_handicap']}")
            
            # Verify if adjusted is roughly 75% or 65% of index
            # This is a rough check since it involves slope/rating
            idx = stats['handicap_index']
            adj = stats['course_handicap']
            if idx > 0:
                ratio = adj / idx
                print(f"  Ratio: {ratio:.2f}")

if __name__ == "__main__":
    test_shamble_handicaps()
