from flask import Flask, jsonify, send_from_directory
from models import db
from config import Config
from routes import register_routes
from flask_migrate import Migrate
import os

def create_app():
    # Set the static folder to the built frontend directory
    # We use a path relative to this file
    dist_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist'))
    app = Flask(__name__, static_folder=dist_path, static_url_path='/')
    app.config.from_object(Config)
    
    db.init_app(app)
    Migrate(app, db)
    
    register_routes(app)

    @app.route("/health")
    def health():
        return jsonify(status="ok")
    
    # Catch-all route to serve the frontend app
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        else:
            return send_from_directory(app.static_folder, 'index.html')
    
    return app

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
