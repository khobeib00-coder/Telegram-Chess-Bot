import json
import os
from config import DATA_DIR

os.makedirs(DATA_DIR, exist_ok=True)
USERS_FILE = os.path.join(DATA_DIR, "users.json")

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def add_user(user_id, username, first_name):
    users = load_users()
    uid = str(user_id)
    if uid not in users:
        users[uid] = {
            "username": username or "لا يوجد",
            "first_name": first_name or "لاعب",
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "points": 0
        }
    else:
        users[uid]["username"] = username or users[uid].get("username", "لا يوجد")
        users[uid]["first_name"] = first_name or users[uid].get("first_name", "لاعب")
    save_users(users)

def update_stats(user_id, result):
    users = load_users()
    uid = str(user_id)
    if uid not in users:
        return
    if result == "win":
        users[uid]["wins"] += 1
        users[uid]["points"] += 3
    elif result == "loss":
        users[uid]["losses"] += 1
    elif result == "draw":
        users[uid]["draws"] += 1
        users[uid]["points"] += 1
    save_users(users)

def get_leaderboard():
    users = load_users()
    sorted_users = sorted(users.values(), key=lambda x: x.get("points", 0), reverse=True)
    return sorted_users[:10]
