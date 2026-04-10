from flask import Flask, jsonify
from models import db
from config import Config
from routes import register_routes
from flask_migrate import Migrate
import os

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    db.init_app(app)
    Migrate(app, db)
    
    register_routes(app)

    @app.route("/health")
    def health():
        return jsonify(status="ok")
    
    return app

if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
