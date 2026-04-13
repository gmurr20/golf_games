import os
import sys
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from models import db
from models.models import Matchup, MatchupPlayer, Hole, Score, Tee, Player, Tournament, Competition

def test_shamble_match_play():
    # Setup mock data
    mock_comp = Competition(id=1, name="Comp", team_a_name="Team A", team_b_name="Team B")
    mock_tournament = Tournament(id=1, competition_id=1, competition=mock_comp)
    mock_tee = Tee(id=1, rating=72.0, slope=113, par=72)
    
    # Shamble Match Play
    mock_matchup = Matchup(
        id=1, 
        tournament_id=1, 
        tee_id=1, 
        format='shamble', 
        scoring_type='match_play',
        tournament=mock_tournament,
        tee=mock_tee,
        use_handicaps=True,
        points_for_win=1.0,
        points_for_push=0.5
    )
    
    # Player A: Index 10 -> CH 10 (Norm) -> Shamble CH 8
    # Player B: Index 20 -> CH 20 (Norm) -> Shamble CH 15
    p1 = Player(id=1, handicap_index=10.0, name="Player A", gender='male')
    p2 = Player(id=2, handicap_index=20.0, name="Player B", gender='male')
    
    mp1 = MatchupPlayer(matchup_id=1, player_id=1, team='A')
    mp2 = MatchupPlayer(matchup_id=1, player_id=2, team='B')
    
    holes = [Hole(hole_number=i, par=4, handicap_index=i, tee_id=1) for i in range(1, 19)]
    
    # Mock DB session
    db.session.get = MagicMock(return_value=mock_matchup)
    
    # Mock queries
    from sqlalchemy.orm import Query
    def mock_query(model):
        q = MagicMock(spec=Query)
        if model == Hole:
            q.filter.return_value.order_by.return_value.all.return_value = holes
            q.filter_by.return_value.order_by.return_value.all.return_value = holes
        elif model == MatchupPlayer:
            q.filter_by.return_value.all.return_value = [mp1, mp2]
            q.filter.return_value.all.return_value = [mp1, mp2]
        elif model == Score:
            q.filter_by.return_value.all.return_value = []
            q.filter.return_value.all.return_value = []
        elif model == Player:
            q.filter.return_value.all.return_value = [p1, p2]
            q.get.side_effect = lambda pid: p1 if pid == 1 else p2
        return q

    import services.match_engine as engine
    engine.Hole.query = mock_query(Hole)
    engine.MatchupPlayer.query = mock_query(MatchupPlayer)
    engine.Score.query = mock_query(Score)
    engine.Player.query = mock_query(Player)
    
    # Test Shamble Match Play
    status = engine.calculate_match_status(1)
    p1_st = status['player_stats'][1]
    p2_st = status['player_stats'][2]
    
    print("--- SHAMBLE MATCH PLAY ---")
    print(f"Player A (CH 10): Adjusted CH={p1_st['course_handicap']}, Playing CH={p1_st['playing_handicap']}")
    print(f"Player B (CH 20): Adjusted CH={p2_st['course_handicap']}, Playing CH={p2_st['playing_handicap']}")
    
    # Expected Shamble: A=8, B=15. Relative: A=0, B=7.
    # Expected Norm: A=10, B=20. Relative: A=0, B=10.
    
    # Test Standard Match Play (for comparison)
    mock_matchup.format = 'individual'
    status_norm = engine.calculate_match_status(1)
    p1_st_n = status_norm['player_stats'][1]
    p2_st_n = status_norm['player_stats'][2]
    
    print("\n--- NORMAL MATCH PLAY ---")
    print(f"Player A (CH 10): CH={p1_st_n['course_handicap']}, Playing CH={p1_st_n['playing_handicap']}")
    print(f"Player B (CH 20): CH={p2_st_n['course_handicap']}, Playing CH={p2_st_n['playing_handicap']}")

if __name__ == "__main__":
    test_shamble_match_play()
