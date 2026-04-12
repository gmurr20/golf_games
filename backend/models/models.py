from . import db
from datetime import datetime

class Competition(db.Model):
    __tablename__ = 'competitions'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    admin_key = db.Column(db.String(50), nullable=False)
    team_a_name = db.Column(db.String(50), nullable=True)
    team_b_name = db.Column(db.String(50), nullable=True)
    
class Player(db.Model):
    __tablename__ = 'players'
    id = db.Column(db.Integer, primary_key=True)
    competition_id = db.Column(db.Integer, db.ForeignKey('competitions.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    handicap_index = db.Column(db.Float, nullable=False, default=0.0)
    team = db.Column(db.String(50), nullable=True)
    gender = db.Column(db.String(10), nullable=False, default='male')
    profile_picture = db.Column(db.Text, nullable=True) # Base64 encoded image string

    competition = db.relationship('Competition', backref=db.backref('players', cascade="all, delete-orphan", lazy=True))

class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

class Tee(db.Model):
    __tablename__ = 'tees'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)  # e.g., 'Blue', 'White'
    rating = db.Column(db.Float, nullable=False) # Default/Male
    slope = db.Column(db.Integer, nullable=False) # Default/Male
    rating_female = db.Column(db.Float, nullable=True)
    slope_female = db.Column(db.Integer, nullable=True)
    par = db.Column(db.Integer, nullable=False)

    course = db.relationship('Course', backref=db.backref('tees', cascade="all, delete-orphan", lazy=True))

class Hole(db.Model):
    __tablename__ = 'holes'
    id = db.Column(db.Integer, primary_key=True)
    tee_id = db.Column(db.Integer, db.ForeignKey('tees.id'), nullable=False)
    hole_number = db.Column(db.Integer, nullable=False) # 1-18
    par = db.Column(db.Integer, nullable=False)
    yardage = db.Column(db.Integer, nullable=True)  # Distance in yards
    handicap_index = db.Column(db.Integer, nullable=False) # 1-18 relative difficulty

    tee = db.relationship('Tee', backref=db.backref('holes', cascade="all, delete-orphan", lazy=True))

class Tournament(db.Model):
    __tablename__ = 'tournaments'
    id = db.Column(db.Integer, primary_key=True)
    competition_id = db.Column(db.Integer, db.ForeignKey('competitions.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='upcoming') # 'upcoming', 'in_progress', 'completed'

    competition = db.relationship('Competition', backref=db.backref('tournaments', cascade="all, delete-orphan", lazy=True))

class Matchup(db.Model):
    __tablename__ = 'matchups'
    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournaments.id'), nullable=False)
    tee_id = db.Column(db.Integer, db.ForeignKey('tees.id'), nullable=False)
    format = db.Column(db.String(20), nullable=False) # 'individual', 'scramble', 'shamble', 'best_ball'
    scoring_type = db.Column(db.String(20), nullable=False, default='match_play') # 'match_play', 'stroke_play'

    use_handicaps = db.Column(db.Boolean, default=True)
    points_for_win = db.Column(db.Float, default=1.0)
    points_for_push = db.Column(db.Float, default=0.5)
    hole_start = db.Column(db.Integer, default=1)   # First hole in this matchup
    hole_end = db.Column(db.Integer, default=18)     # Last hole in this matchup
    tee_time = db.Column(db.DateTime, nullable=True) # When the group tees off
    status = db.Column(db.String(20), default='upcoming')
    
    tournament = db.relationship('Tournament', backref=db.backref('matchups', cascade="all, delete-orphan", lazy=True))
    tee = db.relationship('Tee', backref=db.backref('matchups', cascade="all, delete-orphan", lazy=True))

class MatchupPlayer(db.Model):
    __tablename__ = 'matchup_players'
    id = db.Column(db.Integer, primary_key=True)
    matchup_id = db.Column(db.Integer, db.ForeignKey('matchups.id'), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False)
    team = db.Column(db.String(5), nullable=False) # 'A' or 'B'

    matchup = db.relationship('Matchup', backref=db.backref('player_links', cascade="all, delete-orphan", lazy=True))
    player = db.relationship('Player', backref=db.backref('matchup_players', cascade="all, delete-orphan", lazy=True))

class Score(db.Model):
    __tablename__ = 'scores'
    id = db.Column(db.Integer, primary_key=True)
    matchup_id = db.Column(db.Integer, db.ForeignKey('matchups.id'), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False)
    hole_number = db.Column(db.Integer, nullable=False)
    strokes = db.Column(db.Integer, nullable=False)

    matchup = db.relationship('Matchup', backref=db.backref('scores', cascade="all, delete-orphan", lazy=True))
    player = db.relationship('Player', backref=db.backref('scores', cascade="all, delete-orphan", lazy=True))
