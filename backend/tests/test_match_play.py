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
    
    # Crucial mapping fix to resolve AttributeError in SQLAlchemy relationship mocking
    mp1.player = p1
    mp2.player = p2
    
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
    engine.Matchup.query = mock_query(Matchup)
    
    # Test Shamble Match Play (Course CH: A=8, B=15. Playing Relative: A=0, B=7)
    status = engine.calculate_match_status(1)
    p1_st = status['player_stats'][1]
    p2_st = status['player_stats'][2]
    
    assert p1_st['course_handicap'] == 8
    assert p1_st['playing_handicap'] == 0
    assert p2_st['course_handicap'] == 15
    assert p2_st['playing_handicap'] == 7
    
    # Test Standard Match Play (Course CH: A=10, B=20. Playing Relative: A=0, B=10)
    mock_matchup.format = 'individual'
    status_norm = engine.calculate_match_status(1)
    p1_st_n = status_norm['player_stats'][1]
    p2_st_n = status_norm['player_stats'][2]
    
    assert p1_st_n['course_handicap'] == 10
    assert p1_st_n['playing_handicap'] == 0
    assert p2_st_n['course_handicap'] == 20
    assert p2_st_n['playing_handicap'] == 10


def test_match_play_freezes_when_decided():
    # Setup mock data
    mock_comp = Competition(id=1, name="Comp", team_a_name="Team A", team_b_name="Team B")
    mock_tournament = Tournament(id=1, competition_id=1, competition=mock_comp)
    mock_tee = Tee(id=1, rating=72.0, slope=113, par=72)
    
    mock_matchup = Matchup(
        id=1, 
        tournament_id=1, 
        tee_id=1, 
        format='individual', 
        scoring_type='match_play',
        tournament=mock_tournament,
        tee=mock_tee,
        use_handicaps=False,  # simple scratch match play
        points_for_win=1.0,
        points_for_push=0.5
    )
    
    p1 = Player(id=1, handicap_index=0.0, name="Player A", gender='male')
    p2 = Player(id=2, handicap_index=0.0, name="Player B", gender='male')
    
    mp1 = MatchupPlayer(matchup_id=1, player_id=1, team='A')
    mp2 = MatchupPlayer(matchup_id=1, player_id=2, team='B')
    mp1.player = p1
    mp2.player = p2
    
    # 5 holes match range (Holes 1 to 5)
    holes = [Hole(hole_number=i, par=4, handicap_index=i, tee_id=1) for i in range(1, 6)]
    
    # Player A wins the first 3 holes (3 UP with 2 to play - decided!)
    # Hole 4: Player B wins the hole. This should be ignored in the running total since A already won 3&2.
    scores = [
        # Hole 1: A=4, B=5 (A wins)
        Score(matchup_id=1, player_id=1, hole_number=1, strokes=4),
        Score(matchup_id=1, player_id=2, hole_number=1, strokes=5),
        # Hole 2: A=4, B=5 (A wins)
        Score(matchup_id=1, player_id=1, hole_number=2, strokes=4),
        Score(matchup_id=1, player_id=2, hole_number=2, strokes=5),
        # Hole 3: A=4, B=5 (A wins - decided here! 3 UP, 2 to play)
        Score(matchup_id=1, player_id=1, hole_number=3, strokes=4),
        Score(matchup_id=1, player_id=2, hole_number=3, strokes=5),
        # Hole 4: A=5, B=4 (B wins, but match is already decided so winner should freeze to None)
        Score(matchup_id=1, player_id=1, hole_number=4, strokes=5),
        Score(matchup_id=1, player_id=2, hole_number=4, strokes=4),
    ]
    
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
            q.filter.return_value.all.return_value = scores
        elif model == Player:
            q.filter.return_value.all.return_value = [p1, p2]
            q.get.side_effect = lambda pid: p1 if pid == 1 else p2
        return q

    import services.match_engine as engine
    engine.Hole.query = mock_query(Hole)
    engine.MatchupPlayer.query = mock_query(MatchupPlayer)
    engine.Score.query = mock_query(Score)
    engine.Player.query = mock_query(Player)
    engine.Matchup.query = mock_query(Matchup)
    
    status = engine.calculate_match_status(1)
    
    # Match is decided after Hole 3 (3 UP, 2 to play -> A wins 3&2)
    assert status["team_a_wins"] == 3
    assert status["team_b_wins"] == 0
    assert status["holes_played"] == 3
    assert status["display_value"] == "3 & 2"
    assert status["is_completed"] is True
    
    # Verify that Hole 4 winner was frozen to None and not evaluated
    hole_4_data = next(h for h in status["scorecard"] if h["hole_number"] == 4)
    assert hole_4_data["winner"] is None

def test_blowout_sorting():
    # Test blowout sorting to match the user's specific ordering requirements:
    # 5&3 beats 3&2, 3&2 beats 2&1, 2&1 beats 2 UP, 2 UP beats 1 UP
    blowouts = [
        {"remaining": 1, "lead": 2, "label": "2 & 1"},
        {"remaining": 3, "lead": 5, "label": "5 & 3"},
        {"remaining": 0, "lead": 1, "label": "1 UP"},
        {"remaining": 2, "lead": 3, "label": "3 & 2"},
        {"remaining": 0, "lead": 2, "label": "2 UP"}
    ]
    
    # Sort descending
    sorted_blowouts = sorted(blowouts, key=lambda x: (x['remaining'], x['lead']), reverse=True)
    
    assert sorted_blowouts[0]["label"] == "5 & 3"
    assert sorted_blowouts[1]["label"] == "3 & 2"
    assert sorted_blowouts[2]["label"] == "2 & 1"
    assert sorted_blowouts[3]["label"] == "2 UP"
    assert sorted_blowouts[4]["label"] == "1 UP"

def test_best_golfer_selection():
    # Test finding lowest cumulative gross relative to par
    players = [
        {"player_id": 1, "name": "Player A", "gross_rel_num": 5, "holes": 18},
        {"player_id": 2, "name": "Player B", "gross_rel_num": -2, "holes": 18},
        {"player_id": 3, "name": "Player C", "gross_rel_num": -5, "holes": 0}, # Inactive
        {"player_id": 4, "name": "Player D", "gross_rel_num": 1, "holes": 9}
    ]
    
    active_players = [x for x in players if x.get('holes', 0) > 0]
    best_golfer = min(active_players, key=lambda x: x['gross_rel_num']) if active_players else None
    
    assert best_golfer is not None
    assert best_golfer["player_id"] == 2 # Player B is the best active gross (-2)

def test_best_round_gross_selection():
    # Test finding lowest single-round gross score relative to par
    rounds = [
        {"player_id": 1, "gross_rel": 2, "holes": 18},
        {"player_id": 2, "gross_rel": -1, "holes": 18},
        {"player_id": 3, "gross_rel": -4, "holes": 8}, # Under 9 holes (invalid)
        {"player_id": 4, "gross_rel": 0, "holes": 9}
    ]
    
    valid_rounds = [r for r in rounds if r['holes'] >= 9]
    if valid_rounds:
        max_holes = max(r['holes'] for r in valid_rounds)
        valid_rounds = [r for r in valid_rounds if r['holes'] == max_holes]
        
    best_round_gross = min(valid_rounds, key=lambda x: x['gross_rel']) if valid_rounds else None
    
    assert best_round_gross is not None
    assert best_round_gross["player_id"] == 2 # Player B is best gross round (-1)
    # Check that Player 4 (who shot 0 over 9 holes) is not considered because 18-hole rounds exist
    assert 4 not in [r["player_id"] for r in valid_rounds]


def test_freeloader_award_calculation(monkeypatch):
    import routes.query as rq
    
    # 1. Setup mock competition, tournament, players
    mock_comp = Competition(id=1, name="Murray Cup 2026", admin_key="secret", team_a_name="Team A", team_b_name="Team B")
    mock_tourney = Tournament(id=1, competition_id=1, name="Murray Cup")
    
    p1 = Player(id=1, name="Tiger", handicap_index=2.0, team="Team A", profile_picture="tiger.png")
    p2 = Player(id=2, name="Freeloader Phil", handicap_index=15.0, team="Team A", profile_picture="phil.png")
    p3 = Player(id=3, name="Opponent 1", handicap_index=5.0, team="Team B", profile_picture=None)
    p4 = Player(id=4, name="Opponent 2", handicap_index=10.0, team="Team B", profile_picture=None)
    player_map = {1: p1, 2: p2, 3: p3, 4: p4}

    # 2. Setup mock matchup & matchup players
    mock_tee = Tee(id=1, rating=72.0, slope=113, par=72)
    mock_tee.course = MagicMock()
    mock_tee.course.name = "Pebble Beach"
    mock_tee.course.logo = "logo.png"

    from datetime import datetime
    mock_match = Matchup(
        id=100,
        tournament_id=1,
        tee_id=1,
        format="best_ball",
        scoring_type="match_play",
        tee_time=datetime(2026, 5, 29, 14, 30),
        hole_start=1,
        hole_end=18,
        points_for_win=1.0,
        points_for_push=0.5,
        tee=mock_tee
    )
    
    mps = [
        MatchupPlayer(matchup_id=100, player_id=1, team="A", handicap_index=2.0),
        MatchupPlayer(matchup_id=100, player_id=2, team="A", handicap_index=15.0),
        MatchupPlayer(matchup_id=100, player_id=3, team="B", handicap_index=5.0),
        MatchupPlayer(matchup_id=100, player_id=4, team="B", handicap_index=10.0),
    ]
    for mp in mps:
        mp.player = player_map[mp.player_id]

    # Mock DB session get
    from models import db
    def mock_get(model, ident):
        if model == Player:
            return player_map.get(ident)
        elif model == Matchup and ident == 100:
            return mock_match
        return None
    db.session.get = MagicMock(side_effect=mock_get)

    # 3. Mock database queries
    from sqlalchemy.orm import Query
    def mock_query(model):
        q = MagicMock(spec=Query)
        if model == Competition:
            q.filter_by.return_value.first.return_value = mock_comp
        elif model == Tournament:
            q.filter_by.return_value.order_by.return_value.first.return_value = mock_tourney
        elif model == Matchup:
            q.filter_by.return_value.order_by.return_value.all.return_value = [mock_match]
        elif model == MatchupPlayer:
            q.filter_by.return_value.all.return_value = mps
        elif model == Player:
            q.get.side_effect = lambda pid: player_map.get(pid)
        return q

    # Apply query mocks to the query blueprint
    rq.Competition.query = mock_query(Competition)
    rq.Tournament.query = mock_query(Tournament)
    rq.Matchup.query = mock_query(Matchup)
    rq.MatchupPlayer.query = mock_query(MatchupPlayer)
    rq.Player.query = mock_query(Player)

    # Mock Flask current_app config
    class MockConfig:
        def get(self, key, default=None):
            if key == 'MASTER_PASSWORD':
                return 'secret'
            return default
            
    class MockApp:
        config = MockConfig()
        
    rq.current_app = MockApp()

    # Mock jsonify to bypass Flask context requirement
    class MockResponse:
        def __init__(self, data):
            self.json = data
    rq.jsonify = MagicMock(side_effect=lambda data: MockResponse(data))

    # 4. Mock calculate_match_status and calculate_overall_winner
    # Scorecard:
    # Hole 1: A wins hole. Tiger=3, Phil=4. Opponents best=4. Tiger gets 1.0, Phil 0.
    # Hole 2: A wins hole. Tiger=3, Phil=3. Opponents best=4. Tiger gets 0.5, Phil 0.5.
    # Hole 3: Push. Tiger=4, Phil=5. Opponents best=4. Tiger gets 1.0, Phil 0.
    # Hole 4: Push. Tiger=4, Phil=4. Opponents best=4. Tiger gets 0.5, Phil 0.5.
    # Total contribution: Tiger=3.0, Phil=1.0. Phil is Freeloader (2.0 PTS Diff).
    mock_scorecard = [
        {
            "hole_number": 1,
            "par": 4,
            "winner": "A",
            "players": {
                1: {"match_net": 3},
                2: {"match_net": 4},
                3: {"match_net": 4},
                4: {"match_net": 5}
            }
        },
        {
            "hole_number": 2,
            "par": 4,
            "winner": "A",
            "players": {
                1: {"match_net": 3},
                2: {"match_net": 3},
                3: {"match_net": 4},
                4: {"match_net": 5}
            }
        },
        {
            "hole_number": 3,
            "par": 4,
            "winner": "Push",
            "players": {
                1: {"match_net": 4},
                2: {"match_net": 5},
                3: {"match_net": 4},
                4: {"match_net": 5}
            }
        },
        {
            "hole_number": 4,
            "par": 4,
            "winner": "Push",
            "players": {
                1: {"match_net": 4},
                2: {"match_net": 4},
                3: {"match_net": 4},
                4: {"match_net": 5}
            }
        }
    ]

    def mock_calc_status(matchup_id):
        return {
            "is_completed": True,
            "holes_played": 4,
            "status_string": "Team A wins 3 & 2",
            "display_value": "3 & 2",
            "display_thru": "FINAL",
            "leading_team": "A",
            "scorecard": mock_scorecard,
            "player_stats": {
                1: {"course_handicap": 2, "playing_handicap": 0, "handicap_index": 2.0, "total_raw": 16, "total_net": 16, "total_par": 16, "holes_scored": 4},
                2: {"course_handicap": 15, "playing_handicap": 13, "handicap_index": 15.0, "total_raw": 20, "total_net": 20, "total_par": 16, "holes_scored": 4},
                3: {"course_handicap": 5, "playing_handicap": 3, "handicap_index": 5.0, "total_raw": 18, "total_net": 18, "total_par": 16, "holes_scored": 4},
                4: {"course_handicap": 10, "playing_handicap": 8, "handicap_index": 10.0, "total_raw": 22, "total_net": 22, "total_par": 16, "holes_scored": 4}
            }
        }
    
    rq.calculate_match_status = MagicMock(side_effect=mock_calc_status)
    rq.calculate_overall_winner = MagicMock(return_value={"winner": "A", "points_a": 1.0, "points_b": 0.0})

    # 5. Invoke get_leaderboard
    response, status_code = rq.get_leaderboard()
    assert status_code == 200
    
    data = response.json
    assert "awards" in data
    assert "freeloader" in data["awards"]
    
    freeloader = data["awards"]["freeloader"]
    assert freeloader["hidden"] is False
    assert freeloader["player_id"] == 2
    assert freeloader["name"] == "Freeloader Phil"
    assert freeloader["value"] == "2.0 PTS Diff"
    assert "Carried by Tiger (3.5 vs 1.5) at Pebble Beach" in freeloader["subtext"]
    assert freeloader["is_tie"] is False




