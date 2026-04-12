import os
from app import create_app, db
from sqlalchemy import inspect

app = create_app()
with app.app_context():
    print(f"DATABASE_URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
    inspector = inspect(db.engine)
    print(f"Tables: {inspector.get_table_names()}")
