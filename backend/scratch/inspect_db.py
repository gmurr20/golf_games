from app import create_app, db
from models.models import Course, Tee, Hole, Matchup, Tournament

app = create_app()
with app.app_context():
    print("COURSES:")
    for c in Course.query.all():
        print(f"Course: {c.id} - {c.name}")
        for t in Tee.query.filter_by(course_id=c.id).all():
            print(f"  Tee: {t.id} - {t.name}, rating={t.rating}, slope={t.slope}, par={t.par}")
            holes = Hole.query.filter_by(tee_id=t.id).all()
            print(f"    Holes: {len(holes)} holes")

    print("\nMATCHUPS:")
    for m in Matchup.query.all():
        print(f"Matchup: {m.id}, format={m.format}, scoring_type={m.scoring_type}, use_handicaps={m.use_handicaps}, holes={m.hole_start}-{m.hole_end}")
