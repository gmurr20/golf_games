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
    
    # Initialize Database and Migrations
    with app.app_context():
        from flask_migrate import upgrade, stamp
        from sqlalchemy import inspect

        # Check if the database has any tables
        inspector = inspect(db.engine)
        try:
            tables = inspector.get_table_names()
        except Exception:
            tables = []

        if not tables:
            # Case 1: Brand new database
            # Running upgrade() will create all tables from scratch via migrations
            # and properly initialize the alembic_version table.
            try:
                upgrade()
                print("Fresh database initialized via migrations.")
            except Exception as e:
                print(f"Error initializing fresh database: {e}")
        elif 'alembic_version' not in tables:
            # Case 2: Existing database created with create_all() but no migration history
            # This is likely the "stuck" state in production.
            # We stamp the database with the current migration history so it can move forward.
            try:
                # We stamp as 'head' if we assume the tables match models, 
                # OR we just try upgrade and see if it can resolve the differences.
                stamp() 
                upgrade()
                print("Existing untracked database has been stamped and upgraded.")
            except Exception as e:
                print(f"Error syncing untracked database: {e}")
        else:
            # Case 3: Standard migration-tracked database
            # Just run upgrade() to apply any new changes (like the gender column).
            try:
                upgrade()
                print("Database schema successfully updated via migrations.")
            except Exception as e:
                print(f"Standard migration update failed: {e}")

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
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
