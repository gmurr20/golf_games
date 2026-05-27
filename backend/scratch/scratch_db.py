from app import create_app
from models.models import Score
from models import db

app = create_app()
with app.app_context():
    scores = Score.query.all()
    print(f"Total scores: len({scores})")
    for s in scores:
        print(f"Score: player={s.player_id}, hole={s.hole_number}, strokes={s.strokes}")
