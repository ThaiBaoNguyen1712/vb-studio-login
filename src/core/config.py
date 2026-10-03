import os
import sys
from pathlib import Path
from dotenv import load_dotenv

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent.parent

ENV_PATH = BASE_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    load_dotenv()


class Config:
    STORAGE_MODE: str = os.getenv("STORAGE_MODE", "LOCAL").upper()
    CURRENT_USER_NAME: str = os.getenv("CURRENT_USER_NAME", "User_01")
    
    # Path configuration
    BASE_DIR: Path = BASE_DIR
    PROFILES_DIR: Path = BASE_DIR / os.getenv("PROFILES_DIR", "profiles")
    DATA_DIR: Path = BASE_DIR / "data"
    LOCAL_DB_FILE: Path = DATA_DIR / "local_db.json"
    
    # PostgreSQL Configuration
    DB_HOST: str = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "vb_login_db")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_SSLMODE: str = os.getenv("DB_SSLMODE", "prefer")
    
    @classmethod
    def ensure_directories(cls):
        cls.PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_profile_path(cls, channel_id: str) -> Path:
        profile_path = cls.PROFILES_DIR / channel_id
        profile_path.mkdir(parents=True, exist_ok=True)
        return profile_path
