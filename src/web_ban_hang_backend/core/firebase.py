import json
import firebase_admin
from firebase_admin import credentials
from web_ban_hang_backend.config import settings

def init_firebase() -> None:
    if not firebase_admin._apps:
        if settings.FIREBASE_CREDENTIALS_JSON:
            try:
                cred_dict = json.loads(settings.FIREBASE_CREDENTIALS_JSON)
            except json.JSONDecodeError:
                import ast
                cred_dict = ast.literal_eval(settings.FIREBASE_CREDENTIALS_JSON)
            cred = credentials.Certificate(cred_dict)
            
        else:
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
            
        firebase_admin.initialize_app(cred)