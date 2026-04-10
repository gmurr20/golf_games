from flask import Blueprint, request, jsonify
from models import db
from models.models import Competition, Player, Course, Tee, Hole, Tournament, Matchup, MatchupPlayer

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/competitions', methods=['POST'])
def create_competition():
    data = request.json
    comp = Competition(name=data['name'], admin_key=data['admin_key'])
    db.session.add(comp)
    db.session.commit()
    return jsonify({"id": comp.id, "name": comp.name}), 201

@admin_bp.route('/courses', methods=['POST'])
def create_course():
    data = request.json
    course = Course(name=data['name'])
    db.session.add(course)
    db.session.commit()
    
    tees = []
    if 'tees' in data:
        for t_data in data['tees']:
            tee = Tee(
                course_id=course.id, 
                name=t_data['name'], 
                rating=t_data['rating'], 
                slope=t_data['slope'], 
                par=t_data['par']
            )
            db.session.add(tee)
            db.session.flush() # get tee.id
            tees.append(tee)
            
            if 'holes' in t_data:
                for h_data in t_data['holes']:
                    hole = Hole(
                        tee_id=tee.id,
                        hole_number=h_data['hole_number'],
                        par=h_data['par'],
                        handicap_index=h_data['handicap_index']
                    )
                    db.session.add(hole)
    db.session.commit()
    return jsonify({"id": course.id, "name": course.name}), 201
