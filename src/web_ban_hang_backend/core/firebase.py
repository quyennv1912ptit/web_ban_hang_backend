import firebase_admin
from firebase_admin import credentials
from web_ban_hang_backend.config import settings

def init_firebase() -> None:
    if not firebase_admin._apps:
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred)