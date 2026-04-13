import os
import sys
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from models import db
from models.models import Matchup, MatchupPlayer, Hole, Score, Tee, Player, Tournament, Competition

def test_shamble_2v2():
    # Setup mock data 2v2
    mock_comp = Competition(id=1, name="Comp", team_a_name="Team A", team_b_name="Team B")
    mock_tournament = Tournament(id=1, competition_id=1, competition=mock_comp)
    mock_tee = Tee(id=1, rating=72.0, slope=113, par=72)
    
    mock_matchup = Matchup(
        id=1, 
        tournament_id=1, 
        tee_id=1, 
        format='shamble', 
        scoring_type='match_play',
        tournament=mock_tournament,
        tee=mock_tee,
        use_handicaps=True
    )
    
    # Team A: Scratch and 10 Index
    # Team B: 15 and 20 Index
    p1 = Player(id=1, handicap_index=0.0, name="A1 (0)", gender='male')
    p2 = Player(id=2, handicap_index=10.0, name="A2 (10)", gender='male')
    p3 = Player(id=3, handicap_index=15.0, name="B1 (15)", gender='male')
    p4 = Player(id=4, handicap_index=20.0, name="B2 (20)", gender='male')
    
    mp1 = MatchupPlayer(matchup_id=1, player_id=1, team='A')
    mp2 = MatchupPlayer(matchup_id=1, player_id=2, team='A')
    mp3 = MatchupPlayer(matchup_id=1, player_id=3, team='B')
    mp4 = MatchupPlayer(matchup_id=1, player_id=4, team='B')
    
    holes = [Hole(hole_number=i, par=4, handicap_index=i, tee_id=1) for i in range(1, 19)]
    db.session.get = MagicMock(return_value=mock_matchup)
    
    from sqlalchemy.orm import Query
    def mock_query(model):
        q = MagicMock(spec=Query)
        if model == Hole: q.filter.return_value.order_by.return_value.all.return_value = holes
        elif model == MatchupPlayer: q.filter_by.return_value.all.return_value = [mp1, mp2, mp3, mp4]
        elif model == Player: 
            q.filter.return_value.all.return_value = [p1, p2, p3, p4]
            q.get.side_effect = lambda pid: {1:p1, 2:p2, 3:p3, 4:p4}[pid]
        elif model == Score: q.filter_by.return_value.all.return_value = []
        return q

    import services.match_engine as engine
    engine.Hole.query = mock_query(Hole)
    engine.MatchupPlayer.query = mock_query(MatchupPlayer)
    engine.Score.query = mock_query(Score)
    engine.Player.query = mock_query(Player)
    
    print("--- 2v2 SHAMBLE MATCH PLAY ---")
    status = engine.calculate_match_status(1)
    for pid in [1,2,3,4]:
        st = status['player_stats'][pid]
        p = {1:p1, 2:p2, 3:p3, 4:p4}[pid]
        print(f"{p.name}: Adjusted CH={st['course_handicap']}, Playing CH={st['playing_handicap']}")

    print("\n--- 2v2 NORMAL MATCH PLAY ---")
    mock_matchup.format = 'individual' # Close enough for logic
    status2 = engine.calculate_match_status(1)
    for pid in [1,2,3,4]:
        st = status2['player_stats'][pid]
        p = {1:p1, 2:p2, 3:p3, 4:p4}[pid]
        print(f"{p.name}: CH={st['course_handicap']}, Playing CH={st['playing_handicap']}")

if __name__ == "__main__":
    test_shamble_2v2()
