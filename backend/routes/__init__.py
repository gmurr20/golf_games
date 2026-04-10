from flask import Flask

def register_routes(app: Flask):
    from .admin import admin_bp
    from .play import play_bp
    from .query import query_bp
    from .player_routes import player_bp

    app.register_blueprint(admin_bp, url_prefix='/api')
    app.register_blueprint(play_bp, url_prefix='/api')
    app.register_blueprint(query_bp, url_prefix='/api')
    app.register_blueprint(player_bp, url_prefix='/api')

