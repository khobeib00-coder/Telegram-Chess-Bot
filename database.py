import os
import json
import threading
from config import DATA_DIR, OWNER_ID

os.makedirs(DATA_DIR, exist_ok=True)

# 🔒 أقفال لحماية البيانات من التعارض
file_lock = threading.Lock()
games_lock = threading.Lock()
challenges_lock = threading.Lock()

def _path(name: str) -> str:
    return os.path.join(DATA_DIR, f"{name}.json")

def load_json(name: str, default):
    p = _path(name)
    if not os.path.exists(p):
        return default
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(name: str, data):
    with file_lock:
        with open(_path(name), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

# 🗄️ قواعد البيانات في الذاكرة
users_db = load_json("users", {})
admins_db = load_json("admins", [])
games_db = {}
pending_challenges = {}
group_challenges = {}

def register_user(user):
    uid = str(user.id)
    name = f"@{user.username}" if user.username else user.first_name
    if uid not in users_db:
        users_db[uid] = {"name": name, "lang": "ar", "points": 0, "wins": 0, "losses": 0}
        save_json("users", users_db)

def add_points(user_id, is_win=True):
    uid = str(user_id)
    if uid in users_db:
        users_db[uid]["points"] += 10 if is_win else 3
        users_db[uid]["wins" if is_win else "losses"] += 1
        save_json("users", users_db)

def is_owner(uid): return uid == OWNER_ID
def is_admin(uid): return uid == OWNER_ID or uid in admins_db
