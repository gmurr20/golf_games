import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Use absolute path for SQLite to avoid CWD issues
    _basedir = os.path.abspath(os.path.dirname(__file__))
    _db_path = os.path.join(_basedir, 'instance', 'app.db')
    
    # Ensure instance folder exists
    if not os.path.exists(os.path.dirname(_db_path)):
        os.makedirs(os.path.dirname(_db_path), exist_ok=True)

    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", f"sqlite:///{_db_path}")
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    MASTER_PASSWORD = os.environ.get("MASTER_PASSWORD", "hotdog")
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
