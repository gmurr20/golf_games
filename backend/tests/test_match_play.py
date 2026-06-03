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




def test_custom_pops_bypass():
    """Verify that custom_pops on a MatchupPlayer bypasses WHS allocations."""
    import json
    
    mock_comp = Competition(id=1, name="Comp", team_a_name="Team A", team_b_name="Team B", admin_key="key")
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
        use_handicaps=True,
        points_for_win=1.0,
        points_for_push=0.5
    )
    
    # Player A: Normal WHS index
    # Player B: Custom pops on holes 1(1 pop), 5(2 pops), 10(1 pop) = 4 total
    p1 = Player(id=1, handicap_index=10.0, name="Player A", gender='male')
    p2 = Player(id=2, handicap_index=20.0, name="Player B", gender='male')
    
    custom_pops_b = {"1": 1, "5": 2, "10": 1}
    
    mp1 = MatchupPlayer(matchup_id=1, player_id=1, team='A', handicap_index=10.0)
    mp2 = MatchupPlayer(matchup_id=1, player_id=2, team='B', handicap_index=20.0,
                         custom_pops=json.dumps(custom_pops_b))
    mp1.player = p1
    mp2.player = p2
    
    holes = [Hole(hole_number=i, par=4, handicap_index=i, tee_id=1) for i in range(1, 19)]
    
    # Mock DB
    db.session.get = MagicMock(return_value=mock_matchup)
    
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
        elif model == Matchup:
            q.filter_by.return_value.all.return_value = [mock_matchup]
        return q

    import services.match_engine as engine
    engine.Hole.query = mock_query(Hole)
    engine.MatchupPlayer.query = mock_query(MatchupPlayer)
    engine.Score.query = mock_query(Score)
    engine.Player.query = mock_query(Player)
    engine.Matchup.query = mock_query(Matchup)
    
    status = engine.calculate_match_status(1)
    
    p1_st = status['player_stats'][1]
    p2_st = status['player_stats'][2]
    
    # Player A: Standard WHS — CH=10 (normal course handicap for 10.0 index on 72/113)
    assert p1_st['course_handicap'] == 10
    
    # Player B: Custom pops — CH = sum of custom pops = 1 + 2 + 1 = 4
    assert p2_st['course_handicap'] == 4
    
    # Player B: playing_handicap should also equal 4 (custom pops bypass relative reduction)
    assert p2_st['playing_handicap'] == 4
    
    # Verify the custom pops are distributed on the correct holes
    p2_pops = p2_st['pops_per_hole']
    assert p2_pops.get(1) == 1
    assert p2_pops.get(5) == 2
    assert p2_pops.get(10) == 1
    # All other holes should have 0 pops
    for h in range(1, 19):
        if h not in (1, 5, 10):
            assert p2_pops.get(h, 0) == 0
    
    # Player A should have standard relative PH (reduced by low man)
    # Since Player B has custom pops (CH=4) and Player A has CH=10,
    # Player A's relative playing handicap is calculated only among standard players,
    # which is just Player A alone: PH = 10 - 10 = 0
    assert p1_st['playing_handicap'] == 0


def test_custom_pops_match_play_with_scores():
    """
    Full match play simulation with custom pops and actual scores.
    Verifies net scores, hole winners, match status, and overall winner.
    
    Setup:
    - 5-hole match (holes 1-5), par 4 each
    - Player A: NO custom pops, standard WHS → CH=10, but PH=0 (relative)
    - Player B: custom pops on hole 1 (1 pop), hole 3 (1 pop) = 2 total, PH=2
    
    Scores:
    - Hole 1: A=5, B=5 → A_net=5, B_net=5-1=4 → B wins
    - Hole 2: A=4, B=5 → A_net=4, B_net=5    → A wins (AS)
    - Hole 3: A=4, B=5 → A_net=4, B_net=5-1=4 → Push (AS)
    - Hole 4: A=5, B=4 → A_net=5, B_net=4    → B wins (B 1UP)
    - Hole 5: A=4, B=4 → A_net=4, B_net=4    → Push (B 1UP, FINAL)
    
    Expected: B wins 1 UP. is_completed=True.
    """
    import json
    
    mock_comp = Competition(id=1, name="Comp", team_a_name="Team A", team_b_name="Team B", admin_key="key")
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
        use_handicaps=True,
        points_for_win=1.0,
        points_for_push=0.5,
        hole_start=1,
        hole_end=5
    )
    
    p1 = Player(id=1, handicap_index=10.0, name="Player A", gender='male')
    p2 = Player(id=2, handicap_index=5.0, name="Player B", gender='male')
    
    # Player B gets custom pops: hole 1 (1 pop), hole 3 (1 pop)
    custom_pops_b = {"1": 1, "3": 1}
    
    mp1 = MatchupPlayer(matchup_id=1, player_id=1, team='A', handicap_index=10.0)
    mp2 = MatchupPlayer(matchup_id=1, player_id=2, team='B', handicap_index=5.0,
                         custom_pops=json.dumps(custom_pops_b))
    mp1.player = p1
    mp2.player = p2
    
    # Only 5 holes in the match range, but all_holes has full set for pops allocation
    holes_in_range = [Hole(hole_number=i, par=4, handicap_index=i, tee_id=1) for i in range(1, 6)]
    all_holes = [Hole(hole_number=i, par=4, handicap_index=i, tee_id=1) for i in range(1, 19)]
    
    scores = [
        # Hole 1: A=5, B=5 raw → B gets 1 pop → B net=4, A net=5 → B wins
        Score(matchup_id=1, player_id=1, hole_number=1, strokes=5),
        Score(matchup_id=1, player_id=2, hole_number=1, strokes=5),
        # Hole 2: A=4, B=5 → no pops → A net=4, B net=5 → A wins
        Score(matchup_id=1, player_id=1, hole_number=2, strokes=4),
        Score(matchup_id=1, player_id=2, hole_number=2, strokes=5),
        # Hole 3: A=4, B=5 → B gets 1 pop → A net=4, B net=4 → Push
        Score(matchup_id=1, player_id=1, hole_number=3, strokes=4),
        Score(matchup_id=1, player_id=2, hole_number=3, strokes=5),
        # Hole 4: A=5, B=4 → no pops → A net=5, B net=4 → B wins
        Score(matchup_id=1, player_id=1, hole_number=4, strokes=5),
        Score(matchup_id=1, player_id=2, hole_number=4, strokes=4),
        # Hole 5: A=4, B=4 → no pops → A net=4, B net=4 → Push
        Score(matchup_id=1, player_id=1, hole_number=5, strokes=4),
        Score(matchup_id=1, player_id=2, hole_number=5, strokes=4),
    ]
    
    db.session.get = MagicMock(return_value=mock_matchup)
    
    from sqlalchemy.orm import Query
    def mock_query(model):
        q = MagicMock(spec=Query)
        if model == Hole:
            # filter() for hole range returns holes_in_range
            q.filter.return_value.order_by.return_value.all.return_value = holes_in_range
            # filter_by() for all_holes returns all 18
            q.filter_by.return_value.order_by.return_value.all.return_value = all_holes
        elif model == MatchupPlayer:
            q.filter_by.return_value.all.return_value = [mp1, mp2]
            q.filter.return_value.all.return_value = [mp1, mp2]
        elif model == Score:
            q.filter.return_value.all.return_value = scores
        elif model == Player:
            q.filter.return_value.all.return_value = [p1, p2]
            q.get.side_effect = lambda pid: p1 if pid == 1 else p2
        elif model == Matchup:
            q.filter_by.return_value.all.return_value = [mock_matchup]
        return q

    import services.match_engine as engine
    engine.Hole.query = mock_query(Hole)
    engine.MatchupPlayer.query = mock_query(MatchupPlayer)
    engine.Score.query = mock_query(Score)
    engine.Player.query = mock_query(Player)
    engine.Matchup.query = mock_query(Matchup)
    
    status = engine.calculate_match_status(1)
    
    # ── Verify per-hole net scores ──
    sc = status['scorecard']
    
    # Key distinction:
    #   "net" = raw - course_pops (full CH, for leaderboard/stats)
    #   "match_net" = raw - match_pops (relative PH, for hole winner determination)
    #
    # Player A: CH=10, PH=0 (standard WHS, relative). So match_net = raw (no match pops).
    #   But "net" will subtract course pops (full 10 pops distributed on hardest holes).
    # Player B: custom_pops on holes 1,3 only. Both "net" and "match_net" use custom pops
    #   since custom_pops bypass both course and match allocations identically (PH=CH=2).
    
    # Hole 1: A raw=5, B raw=5. 
    #   B match_net=5-1=4, A match_net=5-0=5 → B wins (match_net comparison)
    h1 = sc[0]
    assert h1['hole_number'] == 1
    assert h1['players'][1]['raw'] == 5
    assert h1['players'][1]['match_net'] == 5  # A: PH=0, no match pops
    assert h1['players'][2]['raw'] == 5
    assert h1['players'][2]['match_net'] == 4  # B: custom pop on hole 1
    assert h1['winner'] == 'B'
    
    # Hole 2: A=4, B=5, no custom pops for B here
    h2 = sc[1]
    assert h2['hole_number'] == 2
    assert h2['players'][1]['match_net'] == 4  # A: raw 4, no match pops
    assert h2['players'][2]['match_net'] == 5  # B: no custom pop on hole 2
    assert h2['winner'] == 'A'
    
    # Hole 3: A=4, B=5, B gets 1 custom pop → B match_net=4
    h3 = sc[2]
    assert h3['hole_number'] == 3
    assert h3['players'][1]['match_net'] == 4
    assert h3['players'][2]['match_net'] == 4  # B: 1 custom pop on hole 3
    assert h3['winner'] == 'Push'
    
    # Hole 4: A=5, B=4 → B wins
    h4 = sc[3]
    assert h4['players'][1]['match_net'] == 5
    assert h4['players'][2]['match_net'] == 4
    assert h4['winner'] == 'B'
    
    # Hole 5: A=4, B=4 → Push
    h5 = sc[4]
    assert h5['players'][1]['match_net'] == 4
    assert h5['players'][2]['match_net'] == 4
    assert h5['winner'] == 'Push'
    
    # ── Verify match status ──
    assert status['team_a_wins'] == 1
    assert status['team_b_wins'] == 2
    assert status['holes_played'] == 5
    assert status['is_completed'] is True
    assert status['leading_team'] == 'B'
    assert '1 UP' in status['display_value']
    
    # ── Verify overall winner ──
    winner = engine.calculate_overall_winner(1)
    assert winner['winner'] == 'B'
    assert winner['points_a'] == 0.0
    assert winner['points_b'] == 1.0
    
    # ── Verify player totals ──
    p1_st = status['player_stats'][1]
    p2_st = status['player_stats'][2]
    
    # Player A: 5+4+4+5+4 = 22 raw
    assert p1_st['total_raw'] == 22
    assert p1_st['holes_scored'] == 5
    
    # Player B: 5+5+5+4+4 = 23 raw, 2 custom pops → total_net = 23-2 = 21
    assert p2_st['total_raw'] == 23
    assert p2_st['total_net'] == 21
    assert p2_st['holes_scored'] == 5
    
    # ── Verify custom pops player stats are correct ──
    assert p2_st['course_handicap'] == 2  # sum of custom pops
    assert p2_st['playing_handicap'] == 2  # custom pops bypass relative reduction
    
    # ── Verify status strings are reasonable ──
    assert status['status_string'] is not None  # Should have a status summary


def test_leaderboard_ryder_cup_calculations(monkeypatch):
    import routes.query as rq
    
    mock_comp = Competition(id=1, name="Murray Cup 2026", admin_key="secret", team_a_name="Team A", team_b_name="Team B")
    mock_tourney = Tournament(id=1, competition_id=1, name="Murray Cup")
    
    p1 = Player(id=1, name="Tiger", handicap_index=2.0, team="Team A", profile_picture=None)
    p2 = Player(id=2, name="Phil", handicap_index=15.0, team="Team B", profile_picture=None)
    player_map = {1: p1, 2: p2}

    mock_tee = Tee(id=1, rating=72.0, slope=113, par=72)
    mock_tee.course = MagicMock()
    mock_tee.course.name = "Pebble Beach"
    mock_tee.course.logo = "logo.png"

    from datetime import datetime
    mock_matchup_1 = Matchup(
        id=100,
        tournament_id=1,
        tee_id=1,
        format="individual",
        scoring_type="match_play",
        tee_time=datetime(2026, 5, 29, 14, 30),
        hole_start=1,
        hole_end=18,
        points_for_win=1.0,
        points_for_push=0.5,
        tee=mock_tee
    )
    mock_matchup_2 = Matchup(
        id=101,
        tournament_id=1,
        tee_id=1,
        format="individual",
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
        MatchupPlayer(matchup_id=100, player_id=2, team="B", handicap_index=15.0),
        MatchupPlayer(matchup_id=101, player_id=1, team="A", handicap_index=2.0),
        MatchupPlayer(matchup_id=101, player_id=2, team="B", handicap_index=15.0),
    ]
    for mp in mps:
        mp.player = player_map[mp.player_id]

    # Mock DB session get
    from models import db
    def mock_get(model, ident):
        if model == Player:
            return player_map.get(ident)
        elif model == Matchup:
            return mock_matchup_1 if ident == 100 else mock_matchup_2
        return None
    db.session.get = MagicMock(side_effect=mock_get)

    # Mock database queries
    from sqlalchemy.orm import Query
    def mock_query(model):
        q = MagicMock(spec=Query)
        if model == Competition:
            q.filter_by.return_value.first.return_value = mock_comp
        elif model == Tournament:
            q.filter_by.return_value.order_by.return_value.first.return_value = mock_tourney
        elif model == Matchup:
            q.filter_by.return_value.all.return_value = [mock_matchup_1, mock_matchup_2]
            q.filter_by.return_value.order_by.return_value.all.return_value = [mock_matchup_1, mock_matchup_2]
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

    # Mock jsonify
    class MockResponse:
        def __init__(self, data):
            self.json = data
    rq.jsonify = MagicMock(side_effect=lambda data: MockResponse(data))

    # Mock calculate_match_status
    def mock_calc_status(matchup_id):
        # Match 100 has some scorecard data so we don't skip it
        return {
            "is_completed": False,
            "holes_played": 2,
            "status_string": "1 UP",
            "scorecard": [{"hole_number": 1, "par": 4, "players": {1: {"raw": 4}}}]
        }
    rq.calculate_match_status = MagicMock(side_effect=mock_calc_status)

    # Mock calculate_overall_winner
    # Let's say Team A won matchup 100 (1.0 pts) and matchup 101 is not finished (0.0 pts)
    def mock_calc_overall_winner(matchup_id):
        if matchup_id == 100:
            return {"winner": "A", "points_a": 1.0, "points_b": 0.0}
        return {"winner": None, "points_a": 0.0, "points_b": 0.0}
    rq.calculate_overall_winner = MagicMock(side_effect=mock_calc_overall_winner)

    # Call get_leaderboard
    response, status_code = rq.get_leaderboard()
    assert status_code == 200
    
    data = response.json
    assert "competition" in data
    comp_data = data["competition"]
    
    # 2 matchups, each 1.0 points_for_win = 2.0 total points available
    assert comp_data["total_points_available"] == 2.0
    # Target to win: 2.0 / 2 + 0.5 = 1.5
    assert comp_data["points_to_win"] == 1.5
    
    # Team A has 1.0 points (from matchup 100)
    assert comp_data["team_a_points"] == 1.0
    # Team B has 0.0 points
    assert comp_data["team_b_points"] == 0.0
    
    # Team A needs: 1.5 - 1.0 = 0.5
    assert comp_data["team_a_points_needed"] == 0.5
    # Team B needs: 1.5 - 0.0 = 1.5
    assert comp_data["team_b_points_needed"] == 1.5
    
    # Not decided yet because neither team has reached 1.5 points
    assert comp_data["is_decided"] is False
    assert comp_data["winning_team"] is None


def test_stroke_play_handicapping_without_relative_reduction():
    # Setup mock data for 2v2 Stroke Play
    mock_comp = Competition(id=1, name="Comp", team_a_name="Team A", team_b_name="Team B")
    mock_tournament = Tournament(id=1, competition_id=1, competition=mock_comp)
    mock_tee = Tee(id=1, rating=72.0, slope=113, par=72)
    
    # 2v2 Stroke Play matchup
    mock_matchup = Matchup(
        id=1, 
        tournament_id=1, 
        tee_id=1, 
        format='best_ball', 
        scoring_type='stroke_play',
        tournament=mock_tournament,
        tee=mock_tee,
        use_handicaps=True,
        points_for_win=1.0,
        points_for_push=0.5,
        hole_start=1,
        hole_end=18
    )
    
    p1 = Player(id=1, handicap_index=10.0, name="Player A1", gender='male')
    p2 = Player(id=2, handicap_index=20.0, name="Player A2", gender='male')
    p3 = Player(id=3, handicap_index=10.0, name="Player B1", gender='male')
    p4 = Player(id=4, handicap_index=20.0, name="Player B2", gender='male')
    
    mp1 = MatchupPlayer(matchup_id=1, player_id=1, team='A')
    mp2 = MatchupPlayer(matchup_id=1, player_id=2, team='A')
    mp3 = MatchupPlayer(matchup_id=1, player_id=3, team='B')
    mp4 = MatchupPlayer(matchup_id=1, player_id=4, team='B')
    
    mp1.player = p1
    mp2.player = p2
    mp3.player = p3
    mp4.player = p4
    
    holes = [Hole(hole_number=i, par=4, handicap_index=i, tee_id=1) for i in range(1, 19)]
    
    scores = [
        Score(matchup_id=1, player_id=1, hole_number=1, strokes=5),
        Score(matchup_id=1, player_id=2, hole_number=1, strokes=6),
        Score(matchup_id=1, player_id=3, hole_number=1, strokes=5),
        Score(matchup_id=1, player_id=4, hole_number=1, strokes=6),
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
            q.filter_by.return_value.all.return_value = [mp1, mp2, mp3, mp4]
            q.filter.return_value.all.return_value = [mp1, mp2, mp3, mp4]
        elif model == Score:
            q.filter.return_value.all.return_value = scores
            q.filter_by.return_value.all.return_value = scores
        elif model == Player:
            q.filter.return_value.all.return_value = [p1, p2, p3, p4]
            q.get.side_effect = lambda pid: {1: p1, 2: p2, 3: p3, 4: p4}.get(pid)
        elif model == Matchup:
            q.filter_by.return_value.all.return_value = [mock_matchup]
        return q

    import services.match_engine as engine
    engine.Hole.query = mock_query(Hole)
    engine.MatchupPlayer.query = mock_query(MatchupPlayer)
    engine.Score.query = mock_query(Score)
    engine.Player.query = mock_query(Player)
    engine.Matchup.query = mock_query(Matchup)
    
    # Compute overall winner (uses the logic we modified)
    res = engine.calculate_overall_winner(1)
    
    # Under correct non-relative play:
    # Team A score on hole 1 = min(5-1, 6-2) = min(4, 4) = 4 strokes.
    # Team B score on hole 1 = min(5-1, 6-2) = min(4, 4) = 4 strokes.
    # Since other holes are not played, it returns "In Progress" but with correct score sums:
    assert res["score_a"] == 4
    assert res["score_b"] == 4


def test_12_hole_matchup_scaling():
    # Setup mock data for 12-hole individual matchup
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
        use_handicaps=True,
        points_for_win=1.0,
        points_for_push=0.5,
        hole_start=1,
        hole_end=12
    )
    
    # Player A: handicap index 18.0. On 18 holes, CH=18. 
    # Scaled to 12 holes: CH = 18.0 * (12/18) = 12.0.
    p1 = Player(id=1, handicap_index=18.0, name="Player A", gender='male')
    p2 = Player(id=2, handicap_index=0.0, name="Player B", gender='male')
    
    mp1 = MatchupPlayer(matchup_id=1, player_id=1, team='A')
    mp2 = MatchupPlayer(matchup_id=1, player_id=2, team='B')
    mp1.player = p1
    mp2.player = p2
    
    # 12 holes in matchup
    holes_in_range = [Hole(hole_number=i, par=4, handicap_index=i, tee_id=1) for i in range(1, 13)]
    
    from models import db
    db.session.get = MagicMock(return_value=mock_matchup)
    
    from sqlalchemy.orm import Query
    def mock_query(model):
        q = MagicMock(spec=Query)
        if model == Hole:
            q.filter.return_value.order_by.return_value.all.return_value = holes_in_range
            q.filter_by.return_value.order_by.return_value.all.return_value = holes_in_range
        elif model == MatchupPlayer:
            q.filter_by.return_value.all.return_value = [mp1, mp2]
            q.filter.return_value.all.return_value = [mp1, mp2]
        elif model == Score:
            q.filter.return_value.all.return_value = []
            q.filter_by.return_value.all.return_value = []
        elif model == Player:
            q.filter.return_value.all.return_value = [p1, p2]
            q.get.side_effect = lambda pid: p1 if pid == 1 else p2
        elif model == Matchup:
            q.filter_by.return_value.all.return_value = [mock_matchup]
        return q

    import services.match_engine as engine
    engine.Hole.query = mock_query(Hole)
    engine.MatchupPlayer.query = mock_query(MatchupPlayer)
    engine.Score.query = mock_query(Score)
    engine.Player.query = mock_query(Player)
    engine.Matchup.query = mock_query(Matchup)
    
    status = engine.calculate_match_status(1)
    
    p1_st = status['player_stats'][1]
    
    # Course handicap should be scaled to 12 (from 18)
    assert p1_st['course_handicap'] == 12
    # Playing handicap (relative difference) should also be scaled to 12
    assert p1_st['playing_handicap'] == 12
    
    # Pops should be exactly 1 on each of the 12 holes, and 0 elsewhere
    pops = p1_st['pops_per_hole']
    for i in range(1, 13):
        assert pops.get(i) == 1
    assert pops.get(13, 0) == 0


def test_split_matchup_18_hole_handicap_allocation():
    # Setup mock data for split matchup: front 9 and back 9 of an 18-hole round
    mock_comp = Competition(id=1, name="Comp", team_a_name="Team A", team_b_name="Team B")
    mock_tournament = Tournament(id=1, competition_id=1, competition=mock_comp)
    mock_tee = Tee(id=1, rating=72.8, slope=138, par=72)
    
    from datetime import datetime
    tee_time = datetime(2026, 6, 1, 12, 36)
    
    # Matchup 1: holes 1-9
    mock_matchup_1 = Matchup(
        id=1, 
        tournament_id=1, 
        tee_id=1, 
        format='best_ball', 
        scoring_type='match_play',
        tournament=mock_tournament,
        tee=mock_tee,
        use_handicaps=True,
        points_for_win=1.0,
        points_for_push=0.5,
        hole_start=1,
        hole_end=9,
        tee_time=tee_time
    )
    # Matchup 2: holes 10-18
    mock_matchup_2 = Matchup(
        id=2, 
        tournament_id=1, 
        tee_id=1, 
        format='best_ball', 
        scoring_type='match_play',
        tournament=mock_tournament,
        tee=mock_tee,
        use_handicaps=True,
        points_for_win=1.0,
        points_for_push=0.5,
        hole_start=10,
        hole_end=18,
        tee_time=tee_time
    )
    
    p1 = Player(id=1, handicap_index=5.4, name="Greg", gender='male') # 18-hole CH: 7
    p2 = Player(id=2, handicap_index=4.2, name="Vidur", gender='male') # 18-hole CH: 6
    
    mp1 = MatchupPlayer(matchup_id=1, player_id=1, team='A')
    mp2 = MatchupPlayer(matchup_id=1, player_id=2, team='A')
    mp1.player = p1
    mp2.player = p2
    
    # Holes: 18 holes. 
    # Hole 4: handicap index 1 (hardest). Hole 10: handicap index 2 (second hardest).
    holes = []
    for i in range(1, 19):
        # assign unique handicap index (1-18)
        if i == 4:
            hcp_idx = 1
        elif i == 10:
            hcp_idx = 2
        else:
            hcp_idx = i + 2 if i < 4 else i + 1
        holes.append(Hole(hole_number=i, par=4, handicap_index=hcp_idx, tee_id=1))
        
    holes_front = holes[:9]
    holes_back = holes[9:]
    
    from models import db
    db.session.get = MagicMock(side_effect=lambda model, ident: mock_matchup_1 if ident == 1 else mock_matchup_2)
    
    from sqlalchemy.orm import Query
    def mock_query(model):
        q = MagicMock(spec=Query)
        if model == Hole:
            # We want all_holes query to return all 18, and matchup query to return correct slice
            q.filter_by.return_value.order_by.return_value.all.return_value = holes
            q.filter.return_value.order_by.return_value.all.side_effect = lambda: holes_front
        elif model == MatchupPlayer:
            q.filter_by.return_value.all.return_value = [mp1, mp2]
            q.filter.return_value.all.return_value = [mp1, mp2]
        elif model == Score:
            q.filter_by.return_value.all.return_value = []
            q.filter.return_value.all.return_value = []
        elif model == Player:
            q.filter.return_value.all.return_value = [p1, p2]
            q.get.side_effect = lambda pid: p1 if pid == 1 else p2
        elif model == Matchup:
            q.filter_by.return_value.all.return_value = [mock_matchup_1, mock_matchup_2]
        return q

    import services.match_engine as engine
    engine.Hole.query = mock_query(Hole)
    engine.MatchupPlayer.query = mock_query(MatchupPlayer)
    engine.Score.query = mock_query(Score)
    engine.Player.query = mock_query(Player)
    engine.Matchup.query = mock_query(Matchup)
    
    status_1 = engine.calculate_match_status(1)
    
    p1_st = status_1['player_stats'][1]
    p2_st = status_1['player_stats'][2]
    
    # 18-hole course handicap should be calculated: Greg=7, Vidur=6
    assert p1_st['course_handicap'] == 7
    assert p2_st['course_handicap'] == 6
    
    # Relative playing handicap: Greg=7-6=1, Vidur=0
    assert p1_st['playing_handicap'] == 1
    assert p2_st['playing_handicap'] == 0
    
    # Greg's pops should be allocated over 18 holes, which gives him a pop on Hole 4
    # For matchup 1, we filter to holes 1-9. Greg should have pop=1 on Hole 4, and 0 on others.
    assert p1_st['pops_per_hole'].get(4) == 1
    for h in range(1, 10):
        if h != 4:
            assert p1_st['pops_per_hole'].get(h, 0) == 0
            
    # Now verify matchup 2 (back nine)
    engine.Hole.query.filter.return_value.order_by.return_value.all.side_effect = lambda: holes_back
    status_2 = engine.calculate_match_status(2)
    p1_st_2 = status_2['player_stats'][1]
    
    # Course handicap remains 7
    assert p1_st_2['course_handicap'] == 7
    # Playing handicap remains 1
    assert p1_st_2['playing_handicap'] == 1
    # For matchup 2, Greg should have 0 pops because the 1 stroke was allocated to Hole 4 (front 9)
    for h in range(10, 19):
        assert p1_st_2['pops_per_hole'].get(h, 0) == 0


def test_match_play_won_hole_allocation():
    # Setup mock data for a 2v2 matchup
    mock_comp = Competition(id=1, name="Comp", team_a_name="Team A", team_b_name="Team B")
    mock_tournament = Tournament(id=1, competition_id=1, competition=mock_comp)
    mock_tee = Tee(id=1, rating=72.0, slope=113, par=72)
    
    mock_matchup = Matchup(
        id=1, 
        tournament_id=1, 
        tee_id=1, 
        format='best_ball', 
        scoring_type='match_play',
        tournament=mock_tournament,
        tee=mock_tee,
        use_handicaps=True,
        points_for_win=1.0,
        points_for_push=0.5,
        hole_start=1,
        hole_end=9
    )
    
    p1 = Player(id=1, handicap_index=0.0, name="A1", gender='male')
    p2 = Player(id=2, handicap_index=0.0, name="A2", gender='male')
    p3 = Player(id=3, handicap_index=0.0, name="B1", gender='male')
    p4 = Player(id=4, handicap_index=0.0, name="B2", gender='male')
    
    mp1 = MatchupPlayer(matchup_id=1, player_id=1, team='A')
    mp2 = MatchupPlayer(matchup_id=1, player_id=2, team='A')
    mp3 = MatchupPlayer(matchup_id=1, player_id=3, team='B')
    mp4 = MatchupPlayer(matchup_id=1, player_id=4, team='B')
    
    mp1.player = p1
    mp2.player = p2
    mp3.player = p3
    mp4.player = p4
    
    holes = [Hole(hole_number=i, par=4, handicap_index=i, tee_id=1) for i in range(1, 10)]
    
    # Mock scores
    # Hole 1: A1=4, A2=5, B1=5, B2=5 -> Team A wins via A1 (net 4 vs 5). A1 wins hole.
    # Hole 2: A1=4, A2=4, B1=5, B2=5 -> Team A wins via A1&A2 (net 4 vs 5). A1 and A2 win hole.
    # Hole 3: A1=4, A2=5, B1=4, B2=5 -> Push. Nobody wins.
    scores = [
        # Hole 1
        Score(matchup_id=1, player_id=1, hole_number=1, strokes=4),
        Score(matchup_id=1, player_id=2, hole_number=1, strokes=5),
        Score(matchup_id=1, player_id=3, hole_number=1, strokes=5),
        Score(matchup_id=1, player_id=4, hole_number=1, strokes=5),
        # Hole 2
        Score(matchup_id=1, player_id=1, hole_number=2, strokes=4),
        Score(matchup_id=1, player_id=2, hole_number=2, strokes=4),
        Score(matchup_id=1, player_id=3, hole_number=2, strokes=5),
        Score(matchup_id=1, player_id=4, hole_number=2, strokes=5),
        # Hole 3
        Score(matchup_id=1, player_id=1, hole_number=3, strokes=4),
        Score(matchup_id=1, player_id=2, hole_number=3, strokes=5),
        Score(matchup_id=1, player_id=3, hole_number=3, strokes=4),
        Score(matchup_id=1, player_id=4, hole_number=3, strokes=5),
    ]
    
    from models import db
    db.session.get = MagicMock(return_value=mock_matchup)
    
    from sqlalchemy.orm import Query
    def mock_query(model):
        q = MagicMock(spec=Query)
        if model == Hole:
            q.filter.return_value.order_by.return_value.all.return_value = holes
            q.filter_by.return_value.order_by.return_value.all.return_value = holes
        elif model == MatchupPlayer:
            q.filter_by.return_value.all.return_value = [mp1, mp2, mp3, mp4]
            q.filter.return_value.all.return_value = [mp1, mp2, mp3, mp4]
        elif model == Score:
            q.filter_by.return_value.all.return_value = scores
            q.filter.return_value.all.return_value = scores
        elif model == Player:
            q.filter.return_value.all.return_value = [p1, p2, p3, p4]
            q.get.side_effect = lambda pid: {1: p1, 2: p2, 3: p3, 4: p4}.get(pid)
        elif model == Matchup:
            q.filter_by.return_value.all.return_value = [mock_matchup]
        return q

    import services.match_engine as engine
    engine.Hole.query = mock_query(Hole)
    engine.MatchupPlayer.query = mock_query(MatchupPlayer)
    engine.Score.query = mock_query(Score)
    engine.Player.query = mock_query(Player)
    engine.Matchup.query = mock_query(Matchup)
    
    status = engine.calculate_match_status(1)
    
    # Hole 1 checks
    h1 = next(h for h in status['scorecard'] if h['hole_number'] == 1)
    assert h1['winner'] == 'A'
    assert h1['players'][1]['won_hole'] is True
    assert h1['players'][2]['won_hole'] is False
    assert h1['players'][3]['won_hole'] is False
    assert h1['players'][4]['won_hole'] is False
    
    # Hole 2 checks
    h2 = next(h for h in status['scorecard'] if h['hole_number'] == 2)
    assert h2['winner'] == 'A'
    assert h2['players'][1]['won_hole'] is True
    assert h2['players'][2]['won_hole'] is True
    assert h2['players'][3]['won_hole'] is False
    assert h2['players'][4]['won_hole'] is False
    
    # Hole 3 checks (Push)
    h3 = next(h for h in status['scorecard'] if h['hole_number'] == 3)
    assert h3['winner'] == 'Push'
    assert h3['players'][1]['won_hole'] is False
    assert h3['players'][2]['won_hole'] is False
    assert h3['players'][3]['won_hole'] is False
    assert h3['players'][4]['won_hole'] is False



