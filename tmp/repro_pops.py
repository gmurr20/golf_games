
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app import create_app
from models import db
from models.models import Competition, Tournament, Matchup, MatchupPlayer, Player, Course, Tee, Hole, Score
from services.match_engine import calculate_match_status

app = create_app()
app.app_context().push()

def test_pops():
    # Find a match or create a mock one
    matchup = Matchup.query.first()
    if not matchup:
        print("No matchups found in DB. Please run the app and create one.")
        return

    print(f"Testing Matchup ID: {matchup.id}")
    print(f"Format: {matchup.format}, Scoring: {matchup.scoring_type}")
    
    ms = calculate_match_status(matchup.id)
    
    for pid, stats in ms['player_stats'].items():
        player = Player.query.get(pid)
        print(f"\nPlayer: {player.name} (Index: {player.handicap_index})")
        print(f"Course Handicap: {stats['course_handicap']}")
        print(f"Playing Handicap (Reduced): {stats['playing_handicap']}")
        
        pops = stats['pops_per_hole']
        total_dots = sum(pops.values())
        print(f"Total Dots on Card: {total_dots}")
        
        # Check if dots are missing on any holes
        missing = [h for h, p in pops.items() if p == 0]
        # (This just means they don't get a stroke there, not necessarily a bug)
        
    # Check first few holes (even if they have no scores)
    print("\nScorecard Results for Holes 1-18:")
    for h in ms['scorecard']:
        h_num = h['hole_number']
        p_count = len(h['players'])
        print(f"Hole {h_num}: Players with dots/data: {p_count}")
        if p_count > 0:
            pid = list(h['players'].keys())[0]
            pdata = h['players'][pid]
            print(f"  Example Player {pid}: Pops={pdata.get('pops')}, MatchPops={pdata.get('match_pops')}, Raw={pdata.get('raw')}")
        
        if h_num == 3: # Just show a few
            print("...")
            break

if __name__ == "__main__":
    test_pops()
