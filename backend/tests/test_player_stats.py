import os
import sys
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from models.models import Player, Competition, Tournament, Matchup, MatchupPlayer, Score, Tee
from routes.player_routes import get_player_stats

def test_get_player_stats_by_par(monkeypatch):
    # Setup mock competition & player
    mock_comp = Competition(id=1, name="Murray Cup 2026", admin_key="secret", team_a_name="Team A", team_b_name="Team B")
    mock_player = Player(id=42, name="Tiger", handicap_index=2.0, team="Team A", profile_picture=None)
    mock_tourney = Tournament(id=1, competition_id=1, name="Murray Cup")
    
    # Mock db.session.get
    from models import db
    def mock_get(model, ident):
        if model == Player and ident == 42:
            return mock_player
        elif model == Tournament and ident == 1:
            return mock_tourney
        return None
    db.session.get = MagicMock(side_effect=mock_get)
    
    # Mock queries
    from sqlalchemy.orm import Query
    def mock_query(model):
        q = MagicMock(spec=Query)
        if model == Competition:
            q.filter_by.return_value.first.return_value = mock_comp
        elif model == Tournament:
            q.filter_by.return_value.all.return_value = [mock_tourney]
        elif model == MatchupPlayer:
            mock_mp1 = MatchupPlayer(matchup_id=100, player_id=42, team="A")
            mock_mp1.player = mock_player
            mock_mp2 = MatchupPlayer(matchup_id=101, player_id=42, team="A")
            mock_mp2.player = mock_player
            q.filter.return_value.all.return_value = [mock_mp1, mock_mp2]
            q.filter_by.return_value.all.return_value = [mock_mp1, mock_mp2]
        elif model == Matchup:
            from datetime import datetime
            mock_matchup_1 = Matchup(
                id=100, 
                tournament_id=1, 
                tee_id=1, 
                format="individual", 
                scoring_type="match_play", 
                tee_time=datetime(2026, 5, 29, 14, 30),
                hole_start=1,
                hole_end=9,
                points_for_win=1.0,
                points_for_push=0.5
            )
            mock_matchup_2 = Matchup(
                id=101, 
                tournament_id=1, 
                tee_id=1, 
                format="individual", 
                scoring_type="match_play", 
                tee_time=datetime(2026, 5, 29, 14, 30),
                hole_start=10,
                hole_end=18,
                points_for_win=1.0,
                points_for_push=0.5
            )
            mock_tee = Tee(id=1, rating=72.0, slope=113, par=72)
            mock_matchup_1.tee = mock_tee
            mock_matchup_2.tee = mock_tee
            q.filter.return_value.all.return_value = [mock_matchup_1, mock_matchup_2]
        return q

    # Apply mocks to Flask app/models/blueprints
    import routes.player_routes as pr
    pr.Competition.query = mock_query(Competition)
    pr.Tournament.query = mock_query(Tournament)
    pr.MatchupPlayer.query = mock_query(MatchupPlayer)
    pr.Matchup.query = mock_query(Matchup)
    
    # Mock jsonify to bypass Flask application context requirement
    class MockResponse:
        def __init__(self, data):
            self.json = data
    pr.jsonify = MagicMock(side_effect=lambda data: MockResponse(data))
    
    # Mock current_app
    class MockConfig:
        def __getitem__(self, key):
            if key == 'MASTER_PASSWORD':
                return 'secret'
            return None
            
    class MockApp:
        config = MockConfig()
        
    pr.current_app = MockApp()

    # Mock calculate_match_status to return a scorecard with par 3, par 4, and par 5 holes
    mock_scorecard = [
        {
            "hole_number": 1,
            "par": 3,
            "yardage": 130,
            "players": {
                "42": {"raw": 3, "net": 3}
            }
        },
        {
            "hole_number": 2,
            "par": 4,
            "yardage": 350,
            "players": {
                "42": {"raw": 5, "net": 4}
            }
        },
        {
            "hole_number": 3,
            "par": 5,
            "yardage": 520,
            "players": {
                "42": {"raw": 4, "net": 4}
            }
        },
        {
            "hole_number": 4,
            "par": 3,
            "yardage": 150,
            "players": {
                "42": {"raw": 4, "net": 3}
            }
        }
    ]
    
    def mock_calc_status(matchup_id):
        if matchup_id == 100:
            return {
                "is_completed": True,
                "holes_played": 4,
                "scorecard": mock_scorecard
            }
        return {
            "is_completed": True,
            "holes_played": 0,
            "scorecard": []
        }
    pr.calculate_match_status = MagicMock(side_effect=mock_calc_status)
    pr.calculate_overall_winner = MagicMock(return_value={"winner": "A"})

    # Call the endpoint function directly
    response, status_code = get_player_stats(42)
    assert status_code == 200
    
    data = response.json
    assert data["name"] == "Tiger"
    assert "by_par" in data
    
    # Verify by_par statistics calculation:
    # Par 3s: holes 1 & 4. Raw scores: 3 & 4. Net scores: 3 & 3.
    # Expected: avg_gross = 3.50, avg_net = 3.00, best_gross = 3, total_holes = 2.
    assert data["by_par"]["3"]["avg_gross"] == 3.50
    assert data["by_par"]["3"]["avg_net"] == 3.00
    assert data["by_par"]["3"]["best_gross"] == 3
    assert data["by_par"]["3"]["total_holes"] == 2
    
    # Verify distance calculations for Par 3
    # "< 140y": hole 1 (yardage 130), raw score = 3
    # "140-180y": hole 4 (yardage 150), raw score = 4
    p3_dists = data["by_par"]["3"]["distances"]
    assert len(p3_dists) == 2
    d1 = next(x for x in p3_dists if x["range"] == "< 140y")
    assert d1["avg"] == 3.0
    assert d1["holes"] == 1
    d2 = next(x for x in p3_dists if x["range"] == "140-180y")
    assert d2["avg"] == 4.0
    assert d2["holes"] == 1
    
    # Par 4s: hole 2. Raw score: 5. Net score: 4.
    # Expected: avg_gross = 5.00, avg_net = 4.00, best_gross = 5, total_holes = 1.
    assert data["by_par"]["4"]["avg_gross"] == 5.00
    assert data["by_par"]["4"]["avg_net"] == 4.00
    assert data["by_par"]["4"]["best_gross"] == 5
    assert data["by_par"]["4"]["total_holes"] == 1
    
    # Verify distance calculations for Par 4
    # "< 360y": hole 2 (yardage 350), raw score = 5
    p4_dists = data["by_par"]["4"]["distances"]
    assert len(p4_dists) == 1
    d_p4 = p4_dists[0]
    assert d_p4["range"] == "< 360y"
    assert d_p4["avg"] == 5.0
    assert d_p4["holes"] == 1
    
    # Par 5s: hole 3. Raw score: 4. Net score: 4.
    # Expected: avg_gross = 4.00, avg_net = 4.00, best_gross = 4, total_holes = 1.
    assert data["by_par"]["5"]["avg_gross"] == 4.00
    assert data["by_par"]["5"]["avg_net"] == 4.00
    assert data["by_par"]["5"]["best_gross"] == 4
    assert data["by_par"]["5"]["total_holes"] == 1
    
    # Verify distance calculations for Par 5
    # "500-550y": hole 3 (yardage 520), raw score = 4
    p5_dists = data["by_par"]["5"]["distances"]
    assert len(p5_dists) == 1
    d_p5 = p5_dists[0]
    assert d_p5["range"] == "500-550y"
    assert d_p5["avg"] == 4.0
    assert d_p5["holes"] == 1

    # Verify matchup metadata & sorting order
    assert "matchups" in data
    assert len(data["matchups"]) == 2
    
    # Back Nine (hole_start=10) should be sorted first
    m0 = data["matchups"][0]
    assert m0["hole_range"] == "Back Nine"
    assert m0["tee_time_display"] == "May 29 • 2:30 PM"
    
    # Front Nine (hole_start=1) should be sorted second
    m1 = data["matchups"][1]
    assert m1["hole_range"] == "Front Nine"
    assert m1["tee_time_display"] == "May 29 • 2:30 PM"


def test_get_player_stats_matchup_teammates_and_opponents(monkeypatch):
    # Setup mock competition & players
    mock_comp = Competition(id=1, name="Murray Cup 2026", admin_key="secret", team_a_name="Team A", team_b_name="Team B")
    mock_player = Player(id=42, name="Tiger", handicap_index=2.0, team="Team A")
    mock_teammate = Player(id=43, name="Charlie", handicap_index=5.0, team="Team A")
    mock_opponent = Player(id=44, name="Phil", handicap_index=3.0, team="Team B")
    mock_tourney = Tournament(id=1, competition_id=1, name="Murray Cup")
    
    from models import db
    def mock_get(model, ident):
        if model == Player:
            if ident == 42: return mock_player
            if ident == 43: return mock_teammate
            if ident == 44: return mock_opponent
        elif model == Tournament and ident == 1:
            return mock_tourney
        return None
    db.session.get = MagicMock(side_effect=mock_get)
    
    from sqlalchemy.orm import Query
    def mock_query(model):
        q = MagicMock(spec=Query)
        if model == Competition:
            q.filter_by.return_value.first.return_value = mock_comp
        elif model == Tournament:
            q.filter_by.return_value.all.return_value = [mock_tourney]
        elif model == MatchupPlayer:
            mock_mp_me = MatchupPlayer(matchup_id=100, player_id=42, team="A")
            mock_mp_partner = MatchupPlayer(matchup_id=100, player_id=43, team="A")
            mock_mp_opp = MatchupPlayer(matchup_id=100, player_id=44, team="B")
            
            mock_mp_me.player = mock_player
            mock_mp_partner.player = mock_teammate
            mock_mp_opp.player = mock_opponent
            
            # For query filtering
            q.filter.return_value.all.return_value = [mock_mp_me]
            q.filter_by.return_value.all.return_value = [mock_mp_me, mock_mp_partner, mock_mp_opp]
        elif model == Matchup:
            from datetime import datetime
            mock_matchup = Matchup(
                id=100, 
                tournament_id=1, 
                tee_id=1, 
                format="fourball", 
                scoring_type="match_play", 
                tee_time=datetime(2026, 5, 29, 14, 30),
                hole_start=1,
                hole_end=18,
                points_for_win=1.0,
                points_for_push=0.5
            )
            mock_tee = Tee(id=1, rating=72.0, slope=113, par=72)
            mock_matchup.tee = mock_tee
            q.filter.return_value.all.return_value = [mock_matchup]
        return q

    import routes.player_routes as pr
    pr.Competition.query = mock_query(Competition)
    pr.Tournament.query = mock_query(Tournament)
    pr.MatchupPlayer.query = mock_query(MatchupPlayer)
    pr.Matchup.query = mock_query(Matchup)
    
    class MockResponse:
        def __init__(self, data):
            self.json = data
    pr.jsonify = MagicMock(side_effect=lambda data: MockResponse(data))
    
    class MockConfig:
        def __getitem__(self, key):
            if key == 'MASTER_PASSWORD': return 'secret'
            return None
    class MockApp:
        config = MockConfig()
    pr.current_app = MockApp()

    pr.calculate_match_status = MagicMock(return_value={"is_completed": True, "holes_played": 18, "scorecard": []})
    pr.calculate_overall_winner = MagicMock(return_value={"winner": "A"})

    response, status_code = get_player_stats(42)
    assert status_code == 200
    data = response.json
    
    assert len(data["matchups"]) == 1
    m = data["matchups"][0]
    assert m["opponents"] == ["Phil"]
    assert m["teammates"] == ["Charlie"]
