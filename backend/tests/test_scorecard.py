import os
import sys
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from models.models import Player, Competition, Tournament, Matchup, MatchupPlayer, Hole, Score, Tee, Course

def test_scorecard_matchup_id_filtering(monkeypatch):
    import routes.query as rq

    # 1. Setup mock competition, tournament, tee, course
    mock_comp = Competition(id=1, name="Murray Cup 2026", admin_key="secret", team_a_name="Team A", team_b_name="Team B")
    mock_tourney = Tournament(id=1, competition_id=1, name="Murray Cup")
    
    mock_course = MagicMock()
    mock_course.name = "Pebble Beach"
    mock_course.logo = "logo.png"

    mock_tee = Tee(id=1, name="Blue", rating=72.0, slope=113, par=72, course_id=1)
    mock_tee.course = mock_course
    
    # 2. Setup mock players
    p1 = Player(id=1, name="Tiger", handicap_index=2.0, team="Team A", profile_picture="tiger.png")
    p2 = Player(id=2, name="Phil", handicap_index=5.0, team="Team B", profile_picture="phil.png")
    p3 = Player(id=3, name="Rory", handicap_index=1.0, team="Team A", profile_picture="rory.png")
    p4 = Player(id=4, name="Brooks", handicap_index=3.0, team="Team B", profile_picture="brooks.png")
    player_map = {1: p1, 2: p2, 3: p3, 4: p4}

    # 3. Setup mock matchups
    from datetime import datetime
    m1 = Matchup(
        id=100,
        tournament_id=1,
        tee_id=1,
        format="individual",
        scoring_type="match_play",
        tee_time=datetime(2026, 5, 29, 14, 30),
        hole_start=1,
        hole_end=18,
        tee=mock_tee
    )
    m2 = Matchup(
        id=101,
        tournament_id=1,
        tee_id=1,
        format="individual",
        scoring_type="match_play",
        tee_time=datetime(2026, 5, 29, 14, 30),
        hole_start=1,
        hole_end=18,
        tee=mock_tee
    )
    
    # Setup player links (player_links is used in player_id filtering)
    mp1 = MatchupPlayer(matchup_id=100, player_id=1, team="A")
    mp1.player = p1
    mp2 = MatchupPlayer(matchup_id=100, player_id=2, team="B")
    mp2.player = p2
    m1.player_links = [mp1, mp2]

    mp3 = MatchupPlayer(matchup_id=101, player_id=3, team="A")
    mp3.player = p3
    mp4 = MatchupPlayer(matchup_id=101, player_id=4, team="B")
    mp4.player = p4
    m2.player_links = [mp3, mp4]

    mps_all = [mp1, mp2, mp3, mp4]

    # Holes
    mock_holes = [Hole(hole_number=i, par=4, yardage=350, handicap_index=i, tee_id=1) for i in range(1, 19)]

    # Mock DB session get
    from models import db
    def mock_get(model, ident):
        if model == Tee and ident == 1:
            return mock_tee
        elif model == Course and ident == 1:
            return mock_course
        elif model == Player:
            return player_map.get(ident)
        elif model == Matchup:
            return m1 if ident == 100 else m2
        return None
    db.session.get = MagicMock(side_effect=mock_get)

    # 4. Mock database queries
    from sqlalchemy.orm import Query
    def mock_query(model):
        q = MagicMock(spec=Query)
        if model == Matchup:
            mock_order = MagicMock()
            mock_order.all.return_value = [m1, m2]
            q.filter_by.return_value.order_by.return_value = mock_order
        elif model == Hole:
            mock_order = MagicMock()
            mock_order.all.return_value = mock_holes
            q.filter_by.return_value.order_by.return_value = mock_order
        elif model == MatchupPlayer:
            mock_filter = MagicMock()
            q.filter.side_effect = lambda expr: mock_filter
            mock_filter.all.return_value = mps_all
        elif model == Player:
            mock_filter = MagicMock()
            mock_filter.all.return_value = [p1, p2, p3, p4]
            q.filter.return_value = mock_filter
        elif model == Score:
            q.filter.return_value.all.return_value = []
        return q

    import models.models as mm
    mm.Matchup.query = mock_query(Matchup)
    mm.Hole.query = mock_query(Hole)
    mm.MatchupPlayer.query = mock_query(MatchupPlayer)
    mm.Player.query = mock_query(Player)
    mm.Score.query = mock_query(Score)

    # Mock calculate_match_status
    def mock_calc_status(matchup_id):
        if matchup_id == 100:
            return {
                "team_a_wins": 18,
                "team_b_wins": 0,
                "holes_played": 18,
                "scorecard": [
                    {
                        "hole_number": h.hole_number,
                        "winner": "A",
                        "players": {
                            1: {"raw": 4, "net": 4, "pops_per_hole": {h.hole_number: 0}},
                            2: {"raw": 5, "net": 5, "pops_per_hole": {h.hole_number: 0}}
                        }
                    } for h in mock_holes
                ],
                "player_stats": {
                    1: {"handicap_index": 2.0, "course_handicap": 2, "pops_per_hole": {}, "total_raw": 72, "total_net": 70, "total_par": 72, "holes_scored": 18},
                    2: {"handicap_index": 5.0, "course_handicap": 5, "pops_per_hole": {}, "total_raw": 77, "total_net": 72, "total_par": 72, "holes_scored": 18}
                }
            }
        elif matchup_id == 101:
            return {
                "team_a_wins": 0,
                "team_b_wins": 0,
                "holes_played": 18,
                "scorecard": [
                    {
                        "hole_number": h.hole_number,
                        "winner": "Push",
                        "players": {
                            3: {"raw": 4, "net": 4, "pops_per_hole": {h.hole_number: 0}},
                            4: {"raw": 4, "net": 4, "pops_per_hole": {h.hole_number: 0}}
                        }
                    } for h in mock_holes
                ],
                "player_stats": {
                    3: {"handicap_index": 1.0, "course_handicap": 1, "pops_per_hole": {}, "total_raw": 72, "total_net": 71, "total_par": 72, "holes_scored": 18},
                    4: {"handicap_index": 3.0, "course_handicap": 3, "pops_per_hole": {}, "total_raw": 74, "total_net": 71, "total_par": 72, "holes_scored": 18}
                }
            }
        return {"error": "Not found"}

    rq.calculate_match_status = MagicMock(side_effect=mock_calc_status)

    # Mock jsonify to bypass Flask context requirement
    class MockResponse:
        def __init__(self, data):
            self.json = data
    rq.jsonify = MagicMock(side_effect=lambda data: MockResponse(data))

    # Mock request.args
    class MockRequest:
        def __init__(self, args):
            self.args = args
    
    # 5. TEST 1: Retrieve scorecard without filters (all players returned)
    rq.request = MockRequest({})
    rq.MatchupPlayer.query.filter.return_value.all.return_value = mps_all
    
    res, status_code = rq.get_public_scorecard(tournament_id=1, tee_id=1)
    assert status_code == 200
    data = res.json
    first_hole_players = data["scorecard"][0]["players"]
    assert len(first_hole_players) == 4
    assert "1" in first_hole_players
    assert "2" in first_hole_players
    assert "3" in first_hole_players
    assert "4" in first_hole_players

    # 6. TEST 2: Retrieve scorecard filtered by matchup_id=100 (only matchup 100 players returned)
    rq.request = MockRequest({"matchup_id": "100"})
    rq.MatchupPlayer.query.filter.return_value.all.return_value = [mp1, mp2]
    
    res, status_code = rq.get_public_scorecard(tournament_id=1, tee_id=1)
    assert status_code == 200
    data = res.json
    first_hole_players = data["scorecard"][0]["players"]
    assert len(first_hole_players) == 2
    assert "1" in first_hole_players
    assert "2" in first_hole_players
    assert "3" not in first_hole_players
    assert "4" not in first_hole_players

    # 7. TEST 3: Retrieve scorecard filtered concurrently by player_id and tee_time (round history style)
    rq.request = MockRequest({"player_id": "3", "tee_time": "2026-05-29T14:30:00"})
    rq.MatchupPlayer.query.filter.return_value.all.return_value = [mp3, mp4]
    
    res, status_code = rq.get_public_scorecard(tournament_id=1, tee_id=1)
    assert status_code == 200
    data = res.json
    first_hole_players = data["scorecard"][0]["players"]
    assert len(first_hole_players) == 2
    assert "3" in first_hole_players
    assert "4" in first_hole_players
    assert "1" not in first_hole_players
    assert "2" not in first_hole_players
