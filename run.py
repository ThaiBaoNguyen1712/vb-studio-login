import sys
from pathlib import Path

# Đảm bảo đường dẫn gốc dự án luôn nằm trong sys.path
if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
    BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", str(PROJECT_ROOT)))
    if str(BUNDLE_ROOT) not in sys.path:
        sys.path.insert(0, str(BUNDLE_ROOT))
else:
    PROJECT_ROOT = Path(__file__).resolve().parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import tường minh toàn bộ modules của dự án để PyInstaller đóng gói 100% không bị sót
import src.core
import src.core.config
import src.core.constants
import src.core.logger
import src.core.secure_store

import src.domain
import src.domain.models

import src.repositories
import src.repositories.base
import src.repositories.local_repo

import src.services
import src.services.account_service
import src.services.backup_service
import src.services.browser_service
import src.services.firebase_auth_service
import src.services.health_service
import src.services.notify_service
import src.services.platform_service
import src.services.session_service
import src.services.settings_service
import src.services.trash_service
import src.services.update_service

import src.web
import src.web.api_bridge

from src.main import main

if __name__ == "__main__":
    main()
