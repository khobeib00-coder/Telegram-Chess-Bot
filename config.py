# -*- coding: utf-8 -*-
"""⚙️ إعدادات بوت الشطرنج — Dev @khobeib0"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _int(k, d=0):
    try:
        return int(os.environ.get(k, d) or d)
    except ValueError:
        return d


def _flag(k, d="1"):
    return os.environ.get(k, d).strip().lower() in ("1", "true", "yes", "on")


# ═══════════ الأساسيات ═══════════
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
OWNER_ID  = _int("OWNER_ID")
DATA_DIR  = os.environ.get("DATA_DIR", "data")
PORT      = _int("PORT", 8080)

SELF_URL = (os.environ.get("SELF_URL")
            or os.environ.get("RENDER_EXTERNAL_URL")
            or os.environ.get("KOYEB_PUBLIC_DOMAIN")
            or os.environ.get("RAILWAY_PUBLIC_DOMAIN") or "").strip().rstrip("/")
if SELF_URL and not SELF_URL.startswith("http"):
    SELF_URL = "https://" + SELF_URL

WEB_ENABLED    = _flag("WEB_ENABLED", "1")
PING_EVERY     = _int("PING_EVERY", 240)
BACKUP_CHAT_ID = _int("BACKUP_CHAT_ID") or OWNER_ID

DEV = "@khobeib0"

# ═══════════ 🔒 الاشتراك الإجباري ═══════════
FORCE_SUB        = os.environ.get("FORCE_SUB", "@HFEE55").strip()
FORCE_SUB_URL    = os.environ.get("FORCE_SUB_URL", "https://t.me/HFEE55").strip()
FORCE_SUB_STRICT = _flag("FORCE_SUB_STRICT", "0")
SUB_CACHE_TTL    = 300

# ═══════════ 🤖 الذكاء الاصطناعي ═══════════
AI_THINK_TIME  = float(os.environ.get("AI_THINK_TIME", "2.5"))
AI_TIME_MED    = float(os.environ.get("AI_TIME_MED", "1.5"))
AI_DEPTH_MED   = _int("AI_DEPTH_MED", 4)
AI_DEPTH_HARD  = _int("AI_DEPTH_HARD", 8)
TT_MAX_ENTRIES = _int("TT_MAX_ENTRIES", 250000)

# ═══════════ 🎨 الرقعة (مربعات شفافة) ═══════════
EMPTY_LIGHT = os.environ.get("EMPTY_LIGHT", "\u2800")
EMPTY_DARK  = os.environ.get("EMPTY_DARK",  "\u2800")
MARK_SELECT = "🎯"
MARK_MOVE   = "🟢"
MARK_TAKE   = "❌"

SHOW_HINTS     = _flag("SHOW_HINTS")
FLIP_FOR_BLACK = _flag("FLIP_BLACK")
SHOW_HISTORY   = _flag("SHOW_HISTORY")

PIECES = {
    'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙',
    'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟',
}

# ═══════════ 🚦 حد معدّل الضغطات ═══════════
RL_ENABLED       = _flag("RL_ENABLED", "1")
RL_CALLBACK_GAP  = float(os.environ.get("RL_CALLBACK_GAP", "1.0"))
RL_MESSAGE_GAP   = float(os.environ.get("RL_MESSAGE_GAP", "0.4"))
RL_BURST         = _int("RL_BURST", 4)
RL_WINDOW        = float(os.environ.get("RL_WINDOW", "6"))
RL_WARN_COOLDOWN = float(os.environ.get("RL_WARN_COOLDOWN", "4"))
RL_EXEMPT_ADMINS = _flag("RL_EXEMPT_ADMINS", "0")

# ═══════════ 🗃 التذاكر والتدقيق ═══════════
TICKET_TTL_DAYS   = _int("TICKET_TTL_DAYS", 30)
TICKET_ARCH_EVERY = _int("TICKET_ARCH_EVERY", 21600)
TICKET_ARCH_MAX   = _int("TICKET_ARCH_MAX", 5000)
AUDIT_MAX         = _int("AUDIT_MAX", 3000)

# ═══════════ ⏱ التوقيتات ═══════════
CHALLENGE_TTL   = 3600
STATE_TTL       = 600
IDLE_TIMEOUT    = _int("IDLE_TIMEOUT", 2700)
BACKUP_EVERY    = _int("BACKUP_EVERY", 21600)
JANITOR_TICK    = 60
ADMIN_CACHE_TTL = 180
ANON_ADMIN_ID   = 1087968824

# ═══════════ ⭐ النقاط ═══════════
PTS = {"win_pvp": 10, "win_ai": 5, "loss": 1, "draw_pvp": 5, "draw_ai": 2}

# ═══════════ ✨ الترحيب ═══════════
WELCOME_MESSAGE = (
    "↳︎𝟔𝟒 𝐒𝐪𝐮𝐚𝐫𝐞𝐬... 𝐄𝐧𝐝𝐥𝐞𝐬𝐬 𝐏𝐨𝐬𝐬𝐢𝐛𝐢𝐥𝐢𝐭𝐢𝐞𝐬! ✨•\n"
    "↳︎𝐄𝐯𝐞𝐫𝐲 𝐦𝐨𝐯𝐞 𝐢𝐬 𝐚 𝐝𝐞𝐜𝐢𝐬𝐢𝐨𝐧, 𝐞𝐯𝐞𝐫𝐲 𝐦𝐚𝐭𝐜𝐡 𝐚 𝐛𝐚𝐭𝐭𝐥𝐞 𝐨𝐟 𝐦𝐢𝐧𝐝𝐬•\n"
    "↳︎𝐅𝐫𝐨𝐦 𝐭𝐡𝐞 𝐟𝐢𝐫𝐬𝐭 𝐦𝐨𝐯𝐞 𝐭𝐨 𝐭𝐡𝐞 𝐟𝐢𝐧𝐚𝐥 𝐜𝐡𝐞𝐜𝐤𝐦𝐚𝐭𝐞... 𝐰𝐫𝐢𝐭𝐞 𝐲𝐨𝐮𝐫 𝐨𝐰𝐧 𝐥𝐞𝐠𝐞𝐧𝐝•\n"
    "↳︎𝐀𝐫𝐞 𝐲𝐨𝐮 𝐭𝐡𝐞 𝐧𝐞𝐱𝐭 𝐜𝐡𝐚𝐦𝐩𝐢𝐨𝐧?!!•\n\n"
    f"↳︎𝐃𝐞𝐯 {DEV}"
)
