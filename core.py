# -*- coding: utf-8 -*-
"""
🧠 نواة بوت الشطرنج
التخزين · الأدوات · التدقيق · الفحص · حد الضغطات · الاشتراك
الصلاحيات · المحرك (TT) · الرقعة · المباريات · المهام · النسخ
"""
import os
import json
import html
import time
import uuid
import random
import logging
import threading
from collections import deque
from threading import RLock, Thread

import chess
import chess.polyglot
import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException

import config as C

# ══════════════════════════════════════════════════════
#                    🤖 البوت واللوجر
# ══════════════════════════════════════════════════════
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("chess")

if not C.BOT_TOKEN:
    raise SystemExit("❌ متغيّر البيئة BOT_TOKEN غير موجود!")

bot = telebot.TeleBot(C.BOT_TOKEN, parse_mode="HTML",
                      threaded=True, num_threads=8)
ME = {"username": ""}

# ══════════════════════════════════════════════════════
#                    💾 التخزين
# ══════════════════════════════════════════════════════
os.makedirs(C.DATA_DIR, exist_ok=True)
_io = RLock()


def path(name):
    return os.path.join(C.DATA_DIR, f"{name}.json")


def load_json(name, default):
    p = path(name)
    if not os.path.exists(p):
        return default
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        log.error(f"❌ {name}.json تالف (JSON): {e}")
        return default
    except Exception as e:
        log.error(f"❌ فشل قراءة {name}.json: {e}")
        return default


def save_json(name, data):
    with _io:
        tmp = path(name) + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path(name))
        except Exception as e:
            log.error(f"فشل حفظ {name}: {e}")


users           = load_json("users", {})
admins          = load_json("admins", [])
banned          = load_json("banned", [])
tickets         = load_json("tickets", {})
tickets_archive = load_json("tickets_archive", {})

if not isinstance(users, dict):           users = {}
if not isinstance(admins, list):          admins = []
if not isinstance(banned, list):          banned = []
if not isinstance(tickets, dict):         tickets = {}
if not isinstance(tickets_archive, dict): tickets_archive = {}

_dirty = set()


def mark(name):
    _dirty.add(name)


def flush():
    try:
        if "users" in _dirty:
            save_json("users", users)
        if "tickets" in _dirty:
            save_json("tickets", tickets)
        _dirty.clear()
    except Exception as e:
        log.error(f"flush: {e}")


def flush_all():
    try:
        save_json("users", users)
        save_json("admins", admins)
        save_json("banned", banned)
        save_json("tickets", tickets)
        save_json("tickets_archive", tickets_archive)
        _dirty.clear()
    except Exception as e:
        log.error(f"flush_all: {e}")


# ══════════════════════════════════════════════════════
#                    🧰 أدوات
# ══════════════════════════════════════════════════════
START_TS = int(time.time())


def now():
    return int(time.time())


def esc(t):
    return html.escape(str(t))


def mention(uid, name):
    return f'<a href="tg://user?id={uid}">{esc(name)}</a>'


def human(sec):
    sec = int(sec)
    d, r = divmod(sec, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    return f"{d}ي {h}س {m}د" if d else (f"{h}س {m}د" if h else f"{m}د {s}ث")


def touch_user(u):
    uid = str(u.id)
    name = (u.first_name or "لاعب").strip()[:40]
    try:
        rec = users.get(uid)
        if not rec:
            users[uid] = {"name": name, "username": u.username or "",
                          "points": 0, "wins": 0, "losses": 0, "draws": 0,
                          "joined": now(), "last": now()}
            save_json("users", users)
        else:
            if rec.get("name") != name or rec.get("username") != (u.username or ""):
                rec["name"] = name
                rec["username"] = u.username or ""
                mark("users")
            rec["last"] = now()
        return users[uid]
    except Exception as e:
        log.error(f"touch_user {uid}: {e}")
        return users.get(uid, {"name": name, "points": 0,
                               "wins": 0, "losses": 0, "draws": 0})


def uname(uid):
    if uid == "AI":
        return "🤖 الحاسوب"
    return users.get(str(uid), {}).get("name", f"لاعب {uid}")


def is_owner(uid):  return uid == C.OWNER_ID
def is_admin(uid):  return uid == C.OWNER_ID or uid in admins
def is_banned(uid): return uid in banned and uid != C.OWNER_ID


def kb_sig(text, markup):
    m = json.dumps(markup.to_dict(), ensure_ascii=False,
                   sort_keys=True) if markup else ""
    return hash(text + "|" + m)


def safe_edit(chat_id, msg_id, text=None, markup=None):
    try:
        if text is None:
            bot.edit_message_reply_markup(chat_id, msg_id, reply_markup=markup)
        else:
            bot.edit_message_text(text, chat_id, msg_id, reply_markup=markup,
                                  disable_web_page_preview=True)
        return True
    except ApiTelegramException as e:
        s = str(e).lower()
        if "not modified" in s:
            return True
        if "not found" in s or "can't be edited" in s:
            log.debug(f"edit skip {chat_id}/{msg_id}: {e}")
        else:
            log.warning(f"edit fail {chat_id}/{msg_id}: {e}")
        return False
    except Exception as e:
        log.error(f"edit error: {e}")
        return False


def safe_send(chat_id, text, markup=None):
    try:
        return bot.send_message(chat_id, text, reply_markup=markup,
                                disable_web_page_preview=True)
    except ApiTelegramException as e:
        s = str(e).lower()
        if "blocked" in s or "deactivated" in s or "chat not found" in s:
            log.debug(f"send skip {chat_id}: {e}")
        else:
            log.warning(f"send fail {chat_id}: {e}")
        return None
    except Exception as e:
        log.error(f"send error {chat_id}: {e}")
        return None


def edit_or_send(chat_id, msg_id, text, markup=None):
    if msg_id and safe_edit(chat_id, msg_id, text, markup):
        return msg_id
    m = safe_send(chat_id, text, markup)
    return m.message_id if m else None


def ack(call, text=None, alert=False):
    try:
        bot.answer_callback_query(call.id, text, show_alert=alert)
    except ApiTelegramException as e:
        s = str(e).lower()
        if "too old" in s or "invalid" in s:
            log.debug(f"ack expired: {e}")
        else:
            log.warning(f"ack fail: {e}")
    except Exception as e:
        log.error(f"ack error: {e}")


# ══════════════════════════════════════════════════════
#                    📋 سجل التدقيق
# ══════════════════════════════════════════════════════
_audit = load_json("audit", [])
if not isinstance(_audit, list):
    _audit = []
_alk = RLock()

AUDIT_ICONS = {"ban": "🚫", "unban": "✅", "promote": "👑", "demote": "⬇️",
               "broadcast": "📢", "restore": "♻️", "backup": "🗄",
               "reset_game": "🔄", "end_game": "🛑", "reply": "✍️",
               "archive": "🗃"}


def audit_record(action, actor_id, actor_name="", target_id=None,
                 target_name="", detail="", chat_id=None):
    e = {"ts": now(), "action": str(action)[:32], "actor_id": actor_id,
         "actor_name": str(actor_name or "")[:40], "target_id": target_id,
         "target_name": str(target_name or "")[:40],
         "detail": str(detail or "")[:200], "chat_id": chat_id}
    try:
        with _alk:
            _audit.append(e)
            if len(_audit) > C.AUDIT_MAX:
                del _audit[:len(_audit) - C.AUDIT_MAX]
            save_json("audit", _audit)
        log.info(f"AUDIT {action} by={actor_id} → {target_id} {detail}")
    except Exception as ex:
        log.error(f"audit: {ex}")
    return e


def audit_recent(n=20, action=None):
    with _alk:
        out = list(_audit)
    if action:
        out = [e for e in out if e.get("action") == action]
    return out[-n:][::-1]


def audit_count():
    with _alk:
        return len(_audit)


def audit_reload():
    global _audit
    d = load_json("audit", [])
    with _alk:
        _audit = d if isinstance(d, list) else []


def audit_fmt(e):
    ic = AUDIT_ICONS.get(e.get("action"), "•")
    ts = time.strftime("%m-%d %H:%M", time.localtime(e.get("ts", 0)))
    s = (f"{ic} <b>{esc(e.get('action'))}</b> — <code>{ts}</code>\n"
         f"   👤 {esc(e.get('actor_name') or e.get('actor_id'))} "
         f"(<code>{e.get('actor_id')}</code>)")
    if e.get("target_id"):
        s += (f"\n   🎯 {esc(e.get('target_name') or '')} "
              f"(<code>{e.get('target_id')}</code>)")
    if e.get("detail"):
        s += f"\n   📝 <i>{esc(e.get('detail'))}</i>"
    return s


# ══════════════════════════════════════════════════════
#                 🛡 فحص بنية النسخ (Schema)
# ══════════════════════════════════════════════════════
_UNUM = ("points", "wins", "losses", "draws", "joined", "last")


def _serr(m):
    return False, m, None


def schema_validate(name, data):
    if name == "users":
        if isinstance(data, list):
            return _serr("❌ <b>users</b> يجب أن يكون <code>dict</code> "
                         "وليس <code>list</code>.")
        if not isinstance(data, dict):
            return _serr(f"❌ <b>users</b> نوعه "
                         f"<code>{type(data).__name__}</code>.")
        clean, bad = {}, 0
        for k, v in data.items():
            try:
                uid = str(int(k))
            except Exception:
                bad += 1
                continue
            if not isinstance(v, dict):
                bad += 1
                continue
            rec = {"name": str(v.get("name", "لاعب"))[:64],
                   "username": str(v.get("username", ""))[:64]}
            for f in _UNUM:
                try:
                    rec[f] = int(v.get(f, 0) or 0)
                except Exception:
                    rec[f] = 0
            clean[uid] = rec
        if not clean:
            return _serr("❌ لا يوجد أي سجل مستخدم صالح.")
        if bad > len(data) * 0.5:
            return _serr(f"❌ {bad}/{len(data)} سجل تالف — الملف مرفوض.")
        msg = f"✅ <b>users</b>: {len(clean)} سجل"
        return True, msg + (f" · ⚠️ تُجوهل {bad}" if bad else ""), clean

    if name in ("admins", "banned"):
        if isinstance(data, dict):
            return _serr(f"❌ <b>{name}</b> يجب أن يكون <code>list</code>.")
        if not isinstance(data, list):
            return _serr(f"❌ <b>{name}</b> نوعه "
                         f"<code>{type(data).__name__}</code>.")
        clean, bad = [], 0
        for x in data:
            try:
                n = int(x)
                if n and n not in clean:
                    clean.append(n)
            except Exception:
                bad += 1
        msg = f"✅ <b>{name}</b>: {len(clean)} معرّف"
        return True, msg + (f" · ⚠️ تُجوهل {bad}" if bad else ""), clean

    if name in ("tickets", "tickets_archive"):
        if isinstance(data, list):
            return _serr(f"❌ <b>{name}</b> يجب أن يكون <code>dict</code>.")
        if not isinstance(data, dict):
            return _serr(f"❌ <b>{name}</b> نوعه "
                         f"<code>{type(data).__name__}</code>.")
        clean, bad = {}, 0
        for tid, v in data.items():
            if not isinstance(v, dict) or "uid" not in v:
                bad += 1
                continue
            try:
                uid = int(v["uid"])
            except Exception:
                bad += 1
                continue
            rec = {"uid": uid, "name": str(v.get("name", ""))[:64],
                   "username": str(v.get("username", ""))[:64],
                   "text": str(v.get("text", ""))[:2000],
                   "ts": int(v.get("ts", 0) or 0)}
            if "archived_at" in v:
                try:
                    rec["archived_at"] = int(v["archived_at"])
                except Exception:
                    pass
            clean[str(tid)[:32]] = rec
        msg = f"✅ <b>{name}</b>: {len(clean)} تذكرة"
        return True, msg + (f" · ⚠️ تُجوهل {bad}" if bad else ""), clean

    if name == "audit":
        if not isinstance(data, list):
            return _serr("❌ <b>audit</b> يجب أن يكون <code>list</code>.")
        clean = [e for e in data
                 if isinstance(e, dict) and "action" in e and "ts" in e]
        return True, f"✅ <b>audit</b>: {len(clean)} سجل", clean

    return _serr(f"❌ اسم ملف غير معروف: <code>{name}</code>")


# ══════════════════════════════════════════════════════
#                 🚦 حد معدّل الضغطات
# ══════════════════════════════════════════════════════
_rl_lk = RLock()
_rl_last, _rl_hits, _rl_warn = {}, {}, {}
_rl_stats = {"blocked": 0, "allowed": 0}


def _rl_fast(uid, kind, gap):
    t = time.time()
    key = (uid, kind)
    with _rl_lk:
        if t - _rl_last.get(key, 0.0) < gap:
            _rl_stats["blocked"] += 1
            return True, "gap"
        dq = _rl_hits.setdefault(key, deque(maxlen=C.RL_BURST * 3))
        while dq and t - dq[0] > C.RL_WINDOW:
            dq.popleft()
        if len(dq) >= C.RL_BURST:
            _rl_stats["blocked"] += 1
            return True, "burst"
        dq.append(t)
        _rl_last[key] = t
        _rl_stats["allowed"] += 1
        return False, None


def rl_callback(call):
    """True = مسموح | False = محظور"""
    if not C.RL_ENABLED:
        return True
    uid = call.from_user.id
    if C.RL_EXEMPT_ADMINS and is_admin(uid):
        return True
    blocked, why = _rl_fast(uid, "cb", C.RL_CALLBACK_GAP)
    if not blocked:
        return True
    try:
        msg = "🐢 تمهّل قليلاً…" if why == "gap" else "⏳ ضغطات كثيرة — انتظر."
        bot.answer_callback_query(call.id, msg, show_alert=(why == "burst"))
    except Exception as e:
        log.debug(f"rl ack: {e}")
    return False


def rl_message(uid):
    if not C.RL_ENABLED:
        return True
    blocked, _ = _rl_fast(uid, "msg", C.RL_MESSAGE_GAP)
    return not blocked


def rl_notify(chat_id, uid):
    t = time.time()
    with _rl_lk:
        if t - _rl_warn.get(uid, 0) < C.RL_WARN_COOLDOWN:
            return
        _rl_warn[uid] = t
    try:
        bot.send_message(chat_id, "🐢 تمهّل قليلاً من فضلك.")
    except Exception as e:
        log.debug(f"rl notify: {e}")


def rl_cleanup(max_age=600):
    t = time.time()
    with _rl_lk:
        for d in (_rl_last, _rl_warn):
            for k in [k for k, v in list(d.items()) if t - v > max_age]:
                d.pop(k, None)
        for k in [k for k, dq in list(_rl_hits.items())
                  if not dq or t - dq[-1] > max_age]:
            _rl_hits.pop(k, None)


def rl_stats():
    with _rl_lk:
        return dict(_rl_stats, tracked=len(_rl_last))


# ══════════════════════════════════════════════════════
#                 🗃 أرشفة التذاكر
# ══════════════════════════════════════════════════════
def archive_old_tickets(days=None):
    days = C.TICKET_TTL_DAYS if days is None else int(days)
    cutoff = now() - days * 86400
    stamp = now()
    keep, old = {}, {}
    try:
        for tid, tk in tickets.items():
            if not isinstance(tk, dict):
                continue
            try:
                ts = int(tk.get("ts", 0) or 0)
            except Exception:
                ts = 0
            if ts and ts < cutoff:
                rec = dict(tk)
                rec["archived_at"] = stamp
                old[tid] = rec
            else:
                keep[tid] = tk
        if not old:
            return 0
        tickets.clear()
        tickets.update(keep)
        tickets_archive.update(old)
        if len(tickets_archive) > C.TICKET_ARCH_MAX:
            items = sorted(tickets_archive.items(),
                           key=lambda kv: int(kv[1].get("ts", 0) or 0))
            for k, _ in items[:len(items) - C.TICKET_ARCH_MAX]:
                tickets_archive.pop(k, None)
        save_json("tickets", tickets)
        save_json("tickets_archive", tickets_archive)
        log.info(f"🗃 أُرشفت {len(old)} تذكرة (أقدم من {days} يوم)")
        return len(old)
    except Exception as e:
        log.error(f"archive_old_tickets: {e}")
        return 0


def ticket_stats():
    return {"active": len(tickets), "archived": len(tickets_archive),
            "ttl_days": C.TICKET_TTL_DAYS}


# ══════════════════════════════════════════════════════
#                 🔒 الاشتراك الإجباري
# ══════════════════════════════════════════════════════
_sub_cache = {}
_sub_warned = {"x": False}
_SUB_OK = ("member", "administrator", "creator")


def _sub_link():
    return C.FORCE_SUB_URL or f"https://t.me/{C.FORCE_SUB.lstrip('@')}"


def sub_clear(uid):
    _sub_cache.pop(uid, None)


def is_subscribed(uid, use_cache=True):
    if not C.FORCE_SUB or is_admin(uid):
        return True
    if use_cache:
        c = _sub_cache.get(uid)
        if c and time.time() - c[1] < C.SUB_CACHE_TTL:
            return c[0]
    try:
        ok = bot.get_chat_member(C.FORCE_SUB, uid).status in _SUB_OK
    except ApiTelegramException as e:
        s = str(e).lower()
        if "user not found" in s:
            ok = False
        else:
            if not _sub_warned["x"]:
                _sub_warned["x"] = True
                log.warning(f"⚠️ تعذّر التحقق من {C.FORCE_SUB}: {e} "
                            f"— تأكد أن البوت مشرف في القناة!")
            ok = False if C.FORCE_SUB_STRICT else True
    except Exception as e:
        log.debug(f"sub check: {e}")
        ok = True
    _sub_cache[uid] = (ok, time.time())
    return ok


def sub_kb():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📢 اشترك في القناة", url=_sub_link()))
    kb.add(types.InlineKeyboardButton("تحققت ✅", callback_data="sub:check"))
    return kb


def sub_gate(user, chat_id, call=None):
    """True = مسموح | False = أُرسلت رسالة الاشتراك"""
    if is_subscribed(user.id):
        return True
    txt = ("🔒 <b>اشتراك إجباري</b>\n━━━━━━━━━━━━━━━\n"
           f"عذراً <b>{esc(user.first_name or '')}</b>، "
           "لاستخدام البوت يجب الاشتراك في القناة أولاً 👇\n\n"
           "بعد الاشتراك اضغط <b>«تحققت ✅»</b>")
    if call:
        ack(call, "❌ لم تشترك بعد!", True)
    safe_send(chat_id, txt, sub_kb())
    return False


# ══════════════════════════════════════════════════════
#                 🛡 صلاحيات المجموعة
# ══════════════════════════════════════════════════════
_ga_cache = {}
_GA_BOSS = ("administrator", "creator")


def is_group_admin(chat_id, uid):
    if uid == C.ANON_ADMIN_ID or is_admin(uid):
        return True
    if chat_id is None or chat_id >= 0:
        return False
    key = (chat_id, uid)
    c = _ga_cache.get(key)
    if c and time.time() - c[1] < C.ADMIN_CACHE_TTL:
        return c[0]
    ok = False
    try:
        ok = bot.get_chat_member(chat_id, uid).status in _GA_BOSS
    except Exception as e:
        log.debug(f"get_chat_member {chat_id}/{uid}: {e}")
    _ga_cache[key] = (ok, time.time())
    return ok


def is_boss(chat_id, uid, sender_chat=None):
    if sender_chat is not None and getattr(sender_chat, "id", None) == chat_id:
        return True
    return is_group_admin(chat_id, uid)


# ══════════════════════════════════════════════════════
#          🧠 محرك الشطرنج — Negamax + TT
# ══════════════════════════════════════════════════════
VAL = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
       chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 0}

PST = {
chess.PAWN: [0,0,0,0,0,0,0,0, 50,50,50,50,50,50,50,50, 10,10,20,30,30,20,10,10,
             5,5,10,25,25,10,5,5, 0,0,0,20,20,0,0,0, 5,-5,-10,0,0,-10,-5,5,
             5,10,10,-20,-20,10,10,5, 0,0,0,0,0,0,0,0],
chess.KNIGHT:[-50,-40,-30,-30,-30,-30,-40,-50, -40,-20,0,0,0,0,-20,-40,
             -30,0,10,15,15,10,0,-30, -30,5,15,20,20,15,5,-30,
             -30,0,15,20,20,15,0,-30, -30,5,10,15,15,10,5,-30,
             -40,-20,0,5,5,0,-20,-40, -50,-40,-30,-30,-30,-30,-40,-50],
chess.BISHOP:[-20,-10,-10,-10,-10,-10,-10,-20, -10,0,0,0,0,0,0,-10,
             -10,0,5,10,10,5,0,-10, -10,5,5,10,10,5,5,-10,
             -10,0,10,10,10,10,0,-10, -10,10,10,10,10,10,10,-10,
             -10,5,0,0,0,0,5,-10, -20,-10,-10,-10,-10,-10,-10,-20],
chess.ROOK:  [0,0,0,0,0,0,0,0, 5,10,10,10,10,10,10,5, -5,0,0,0,0,0,0,-5,
             -5,0,0,0,0,0,0,-5, -5,0,0,0,0,0,0,-5, -5,0,0,0,0,0,0,-5,
             -5,0,0,0,0,0,0,-5, 0,0,0,5,5,0,0,0],
chess.QUEEN: [-20,-10,-10,-5,-5,-10,-10,-20, -10,0,0,0,0,0,0,-10,
             -10,0,5,5,5,5,0,-10, -5,0,5,5,5,5,0,-5, 0,0,5,5,5,5,0,-5,
             -10,5,5,5,5,5,0,-10, -10,0,5,0,0,0,0,-10,
             -20,-10,-10,-5,-5,-10,-10,-20],
chess.KING:  [-30,-40,-40,-50,-50,-40,-40,-30, -30,-40,-40,-50,-50,-40,-40,-30,
             -30,-40,-40,-50,-50,-40,-40,-30, -30,-40,-40,-50,-50,-40,-40,-30,
             -20,-30,-30,-40,-40,-30,-30,-20, -10,-20,-20,-20,-20,-20,-20,-10,
             20,20,0,0,0,0,20,20, 20,30,10,0,0,10,30,20],
}
KING_END = [-50,-40,-30,-20,-20,-30,-40,-50, -30,-20,-10,0,0,-10,-20,-30,
            -30,-10,20,30,30,20,-10,-30, -30,-10,30,40,40,30,-10,-30,
            -30,-10,30,40,40,30,-10,-30, -30,-10,20,30,30,20,-10,-30,
            -30,-30,0,0,0,0,-30,-30, -50,-30,-30,-30,-30,-30,-30,-50]

INF, MATE = 10 ** 7, 100000
EXACT, LOWER, UPPER = 0, 1, 2
TT = {}
TT_STATS = {"hits": 0, "cuts": 0, "stores": 0}

BOOK_W = ["e2e4", "d2d4", "c2c4", "g1f3", "g2g3", "b1c3"]
BOOK_B = ["e7e5", "c7c5", "e7e6", "c7c6", "d7d5", "g8f6",
          "d7d6", "b8c6", "g7g6", "a7a6"]


class _TimeUp(Exception):
    pass


def tt_clear():
    TT.clear()
    for k in TT_STATS:
        TT_STATS[k] = 0


def tt_stats():
    return dict(TT_STATS, size=len(TT))


def _tt_probe(key, depth, alpha, beta):
    e = TT.get(key)
    if not e:
        return None, None
    ed, esc_, ef, em = e
    if ed < depth:
        return None, em
    TT_STATS["hits"] += 1
    if ef == EXACT:
        TT_STATS["cuts"] += 1
        return esc_, em
    if ef == LOWER and esc_ >= beta:
        TT_STATS["cuts"] += 1
        return esc_, em
    if ef == UPPER and esc_ <= alpha:
        TT_STATS["cuts"] += 1
        return esc_, em
    return None, em


def _tt_store(key, depth, score, flag, move):
    if abs(score) > MATE - 1000:
        return
    if len(TT) >= C.TT_MAX_ENTRIES:
        for i, k in enumerate(list(TT.keys())):
            if i >= C.TT_MAX_ENTRIES // 4:
                break
            TT.pop(k, None)
    old = TT.get(key)
    if old and old[0] > depth:
        return
    TT[key] = (depth, score, flag, move)
    TT_STATS["stores"] += 1


def evaluate(board):
    pm = board.piece_map()
    endgame = len(pm) <= 12
    s = 0
    for sq, pc in pm.items():
        idx = (sq ^ 56) if pc.color == chess.WHITE else sq
        pt = pc.piece_type
        v = KING_END[idx] if (pt == chess.KING and endgame) \
            else VAL[pt] + PST[pt][idx]
        s += v if pc.color == chess.WHITE else -v
    return s if board.turn == chess.WHITE else -s


def _ordered(board, tt_move=None):
    def key(m):
        if tt_move is not None and m == tt_move:
            return -99999
        s = 0
        if board.is_capture(m):
            vic = board.piece_type_at(m.to_square) or chess.PAWN
            att = board.piece_type_at(m.from_square) or chess.PAWN
            s += 1000 + VAL.get(vic, 100) - VAL.get(att, 0) // 10
        if m.promotion:
            s += 800
        if board.gives_check(m):
            s += 120
        return -s
    return sorted(board.legal_moves, key=key)


def _quiesce(board, alpha, beta, dl, d=4):
    if time.time() > dl:
        raise _TimeUp
    stand = evaluate(board)
    if stand >= beta:
        return beta
    if d == 0:
        return stand
    if stand > alpha:
        alpha = stand
    caps = [m for m in board.legal_moves if board.is_capture(m)]
    caps.sort(key=lambda m: -(VAL.get(board.piece_type_at(m.to_square)
                                      or chess.PAWN, 100)))
    for m in caps:
        board.push(m)
        try:
            sc = -_quiesce(board, -beta, -alpha, dl, d - 1)
        finally:
            board.pop()
        if sc >= beta:
            return beta
        if sc > alpha:
            alpha = sc
    return alpha


def _negamax(board, depth, alpha, beta, dl, ply=0):
    if time.time() > dl:
        raise _TimeUp
    alpha0 = alpha
    key = chess.polyglot.zobrist_hash(board)
    cached, tt_move = _tt_probe(key, depth, alpha, beta)
    if cached is not None and ply > 0:
        return cached
    if board.is_checkmate():
        return -MATE + ply
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    if board.halfmove_clock >= 100:
        return 0
    if board.halfmove_clock >= 8 and board.is_repetition(3):
        return 0
    if depth <= 0:
        return _quiesce(board, alpha, beta, dl)

    best, best_mv = -INF, None
    for m in _ordered(board, tt_move):
        board.push(m)
        try:
            sc = -_negamax(board, depth - 1, -beta, -alpha, dl, ply + 1)
        finally:
            board.pop()
        if sc > best:
            best, best_mv = sc, m
        if best > alpha:
            alpha = best
        if alpha >= beta:
            break

    flag = EXACT
    if best <= alpha0:
        flag = UPPER
    elif best >= beta:
        flag = LOWER
    _tt_store(key, depth, best, flag, best_mv)
    return best


def _book(board):
    if board.fullmove_number > 4:
        return None
    pool = BOOK_W if board.turn == chess.WHITE else BOOK_B
    legal = []
    for u in pool:
        try:
            m = chess.Move.from_uci(u)
            if m in board.legal_moves:
                legal.append(m)
        except Exception:
            pass
    return random.choice(legal) if legal and random.random() < 0.9 else None


def pick_move(board, level=2):
    """level: 1 سهل · 2 متوسط · 3 صعب"""
    moves = list(board.legal_moves)
    if not moves:
        return None
    if len(moves) == 1:
        return moves[0]

    bm = _book(board)
    if bm:
        return bm

    if level <= 1:
        caps = [m for m in moves if board.is_capture(m)]
        if caps and random.random() < 0.55:
            return random.choice(caps)
        return random.choice(moves)

    if len(TT) > C.TT_MAX_ENTRIES:
        tt_clear()

    max_depth = C.AI_DEPTH_MED if level == 2 else C.AI_DEPTH_HARD
    budget = C.AI_TIME_MED if level == 2 else C.AI_THINK_TIME
    noise = 40 if level == 2 else 12
    dl = time.time() + budget
    best, prev = random.choice(moves), None

    try:
        for d in range(1, max_depth + 1):
            scored, alpha = [], -INF
            for m in _ordered(board, prev):
                board.push(m)
                try:
                    pen = 70 if (board.halfmove_clock >= 4
                                 and board.is_repetition(2)) else 0
                    sc = -_negamax(board, d - 1, -INF, INF, dl, 1) - pen
                finally:
                    board.pop()
                scored.append((sc, m))
                if sc > alpha:
                    alpha = sc
            if scored:
                jit = [(s + random.randint(-noise, noise), m) for s, m in scored]
                jit.sort(key=lambda x: x[0], reverse=True)
                best = jit[0][1]
                prev = max(scored, key=lambda x: x[0])[1]
            if time.time() > dl:
                break
    except _TimeUp:
        pass
    return best


# ══════════════════════════════════════════════════════
#                 🎨 رسم الرقعة
# ══════════════════════════════════════════════════════
def _emoji(b, sq, sel, targets, dead):
    if not dead:
        if sq == sel:
            return C.MARK_SELECT
        if C.SHOW_HINTS and sq in targets:
            return C.MARK_TAKE if targets[sq] else C.MARK_MOVE
    pc = b.piece_at(sq)
    if pc:
        return C.PIECES[pc.symbol()]
    f, r = chess.square_file(sq), chess.square_rank(sq)
    return C.EMPTY_LIGHT if (f + r) % 2 else C.EMPTY_DARK


def _grid(g, viewer=None, dead=False):
    b = g["board"]
    flip = C.FLIP_FOR_BLACK and viewer is not None and viewer == g["black"]
    sel = None if dead else g.get("selected")
    targets = {}
    if sel is not None and C.SHOW_HINTS:
        for m in b.legal_moves:
            if m.from_square == sel:
                targets[m.to_square] = b.is_capture(m)
    ranks = range(7, -1, -1) if not flip else range(0, 8)
    files = range(0, 8) if not flip else range(7, -1, -1)
    rows = []
    for r in ranks:
        row = []
        for f in files:
            sq = chess.square(f, r)
            row.append(types.InlineKeyboardButton(
                _emoji(b, sq, sel, targets, dead),
                callback_data="noop" if dead else f"sq|{g['id']}|{sq}"))
        rows.append(row)
    return rows


def _actions(g, viewer):
    gid = g["id"]
    promo = g.get("promo")
    if promo and (viewer is None or viewer == promo[2]):
        return [[types.InlineKeyboardButton("♕", callback_data=f"pr|{gid}|q"),
                 types.InlineKeyboardButton("♖", callback_data=f"pr|{gid}|r"),
                 types.InlineKeyboardButton("♗", callback_data=f"pr|{gid}|b"),
                 types.InlineKeyboardButton("♘", callback_data=f"pr|{gid}|n")],
                [types.InlineKeyboardButton("✖️ إلغاء",
                                            callback_data=f"pc|{gid}")]]
    off = g.get("draw_offer")
    if off and viewer != off:
        return [[types.InlineKeyboardButton("✅ أوافق",
                                            callback_data=f"da|{gid}|y"),
                 types.InlineKeyboardButton("❌ أرفض",
                                            callback_data=f"da|{gid}|n")]]
    row = [types.InlineKeyboardButton("🏳️ استسلام", callback_data=f"rs|{gid}"),
           types.InlineKeyboardButton("🤝 تعادل", callback_data=f"dr|{gid}")]
    if g.get("chat_type") == "group":
        row.append(types.InlineKeyboardButton("🛑", callback_data=f"ae|{gid}"))
    return [row]


def board_markup(g, viewer=None):
    kb = types.InlineKeyboardMarkup()
    for r in _grid(g, viewer):
        kb.row(*r)
    for r in _actions(g, viewer):
        kb.row(*r)
    return kb


def final_markup(g, extra=None):
    kb = types.InlineKeyboardMarkup()
    for r in _grid(g, None, dead=True):
        kb.row(*r)
    if extra:
        kb.row(*extra)
    return kb


LEVEL_NAME = {1: "😴 سهل", 2: "🙂 متوسط", 3: "😈 صعب"}


def game_text(g, note="", viewer=None):
    b = g["board"]
    head = ("🤖 <b>مباراة ضد الحاسوب</b>  "
            f"<i>({LEVEL_NAME.get(g.get('level', 2), '')})</i>"
            if g["mode"] == "ai" else "⚔️ <b>مباراة ثنائية</b>")
    L = [head, "━━━━━━━━━━━━━━━",
         f"⚪ {esc(uname(g['white']))}",
         f"⚫ {esc(uname(g['black']))}",
         "━━━━━━━━━━━━━━━"]
    if note:
        L.append(note)
    if b.is_check():
        L.append("🚨 <b>كِـش على الملك!</b>")
    if C.SHOW_HISTORY and g["history"]:
        L.append(f"📜 <code>{esc(' '.join(g['history'][-3:]))}</code>")
    turn = f"🎯 الدور: <b>{esc(uname(g['turn']))}</b>"
    if viewer is not None and viewer == g["turn"]:
        turn += "  ← <i>دورك</i>"
    L.append(turn)
    L.append(f"🔢 النقلة: <code>{b.fullmove_number}</code>")
    return "\n".join(L)


# ══════════════════════════════════════════════════════
#                 ♟️ إدارة المباريات
# ══════════════════════════════════════════════════════
GAMES = {}
PLAYER_GAME = {}
CHALLENGES = {}
STATES = {}
TICKET_MAP = {}
GL = RLock()


def in_game(uid):
    return PLAYER_GAME.get(uid)


def find_game_by_message(chat_id, message_id):
    for g in list(GAMES.values()):
        for v in g["views"]:
            if v["chat_id"] == chat_id and v["message_id"] == message_id:
                return g
    return None


def new_game(mode, white, black, chat_type, level=2):
    gid = uuid.uuid4().hex[:8]
    g = {"id": gid, "mode": mode, "level": level, "white": white, "black": black,
         "board": chess.Board(), "selected": None, "promo": None,
         "draw_offer": None, "turn": white, "history": [], "views": [],
         "chat_type": chat_type, "ts": now(), "thinking": False}
    GAMES[gid] = g
    for p in (white, black):
        if p != "AI":
            PLAYER_GAME[p] = gid
    if len(TT) > 200000:
        tt_clear()
    return g


def attach_view(g, chat_id, message_id, viewer):
    g["views"].append({"chat_id": chat_id, "message_id": message_id,
                       "viewer": viewer, "sig": None})


def push(g, note="", only=None):
    for v in g["views"]:
        if only is not None and v["viewer"] is not None and v["viewer"] != only:
            continue
        text = game_text(g, note, v["viewer"])
        kb = board_markup(g, v["viewer"])
        sig = kb_sig(text, kb)
        if v.get("sig") == sig:
            continue
        if safe_edit(v["chat_id"], v["message_id"], text, kb):
            v["sig"] = sig


def _award(uid, kind, vs_ai):
    u = users.get(str(uid))
    if not u:
        return 0
    if kind == "win":
        pts, f = (C.PTS["win_ai"] if vs_ai else C.PTS["win_pvp"]), "wins"
    elif kind == "loss":
        pts, f = C.PTS["loss"], "losses"
    else:
        pts, f = (C.PTS["draw_ai"] if vs_ai else C.PTS["draw_pvp"]), "draws"
    u["points"] = u.get("points", 0) + pts
    u[f] = u.get(f, 0) + 1
    mark("users")
    return pts


def finish(g, result, note):
    """result: white | black | draw | abort"""
    if g["id"] not in GAMES:
        return
    vs_ai = g["mode"] == "ai"
    earned = {}
    if result in ("white", "black"):
        w, l = ((g["white"], g["black"]) if result == "white"
                else (g["black"], g["white"]))
        if w != "AI":
            earned[w] = _award(w, "win", vs_ai)
        if l != "AI":
            earned[l] = _award(l, "loss", vs_ai)
    elif result == "draw":
        for p in (g["white"], g["black"]):
            if p != "AI":
                earned[p] = _award(p, "draw", vs_ai)

    b = g["board"]
    L = [note, "━━━━━━━━━━━━━━━",
         f"⚪ {esc(uname(g['white']))}   ⚫ {esc(uname(g['black']))}",
         f"🔢 عدد النقلات: <code>{b.fullmove_number}</code>"]
    if g["history"]:
        L.append(f"📜 <code>{esc(' '.join(g['history'][-8:]))}</code>")
    if earned:
        L.append("━━━━━━━━━━━━━━━")
        for uid, p in earned.items():
            L.append(f"⭐ {esc(uname(uid))}: <b>+{p}</b> نقطة")
    text = "\n".join(L)

    lbl = "⚔️ تحدٍّ جديد" if g["chat_type"] == "group" else "🔄 مباراة جديدة"
    cbd = "gnew" if g["chat_type"] == "group" else "m:back"
    kb = final_markup(g, [types.InlineKeyboardButton(lbl, callback_data=cbd)])
    for v in g["views"]:
        safe_edit(v["chat_id"], v["message_id"], text, kb)

    GAMES.pop(g["id"], None)
    for p in (g["white"], g["black"]):
        if p != "AI" and PLAYER_GAME.get(p) == g["id"]:
            PLAYER_GAME.pop(p, None)
    save_json("users", users)


def check_end(g):
    b = g["board"]
    if b.is_checkmate():
        side = "black" if b.turn == chess.WHITE else "white"
        finish(g, side, f"🏁 <b>كِـش مات!</b>\n🎉 الفائز: "
                        f"<b>{esc(uname(g[side]))}</b>")
        return True
    if b.is_stalemate():
        finish(g, "draw", "🤝 <b>تعادل — الملك محاصَر بلا نقلات</b>")
        return True
    if b.is_insufficient_material():
        finish(g, "draw", "🤝 <b>تعادل — لا توجد قطع كافية للمات</b>")
        return True
    if b.is_repetition(3):
        finish(g, "draw", "🤝 <b>تعادل — تكرار الوضع ٣ مرّات</b>")
        return True
    if b.is_fifty_moves():
        finish(g, "draw", "🤝 <b>تعادل — قاعدة الـ٥٠ نقلة</b>")
        return True
    return False


def _ai_worker(gid):
    with GL:
        g = GAMES.get(gid)
        if not g or g["turn"] != "AI":
            return
        snap, lvl = g["board"].copy(), g.get("level", 2)
    try:
        mv = pick_move(snap, lvl)
    except Exception as e:
        log.error(f"ai_worker pick: {e}")
        mv = None
    with GL:
        g = GAMES.get(gid)
        if not g or g["turn"] != "AI":
            return
        g["thinking"] = False
        b = g["board"]
        if mv is None or mv not in b.legal_moves:
            legal = list(b.legal_moves)
            if not legal:
                check_end(g)
                return
            mv = legal[0]
        cap, san = b.is_capture(mv), b.san(mv)
        b.push(mv)
        g["history"].append(san)
        g["turn"] = g["white"]
        g["ts"] = now()
        if check_end(g):
            return
        push(g, f"{'⚔️' if cap else '🤖'} الحاسوب: <code>{esc(san)}</code>")


def apply_move(g, mv, uid):
    b = g["board"]
    cap, san = b.is_capture(mv), b.san(mv)
    b.push(mv)
    g["history"].append(san)
    g["selected"] = None
    g["promo"] = None
    g["draw_offer"] = None
    g["ts"] = now()
    g["turn"] = g["black"] if g["turn"] == g["white"] else g["white"]
    if check_end(g):
        return
    note = (f"{'⚔️ أكل!' if cap else '♟'} {esc(uname(uid))}: "
            f"<code>{esc(san)}</code>")
    if g["mode"] == "ai" and g["turn"] == "AI":
        g["thinking"] = True
        push(g, note)
        Thread(target=_ai_worker, args=(g["id"],), daemon=True).start()
    else:
        push(g, note)


def ai_accepts_draw(g):
    return evaluate(g["board"]) < -150


# ══════════════════════════════════════════════════════
#                 🗄 النسخ الاحتياطي
# ══════════════════════════════════════════════════════
BACKUP_FILES = ("users", "admins", "banned", "tickets",
                "tickets_archive", "audit")


def do_backup(chat_id=None):
    try:
        flush_all()
    except Exception as e:
        log.error(f"flush before backup: {e}")
    target = chat_id or C.BACKUP_CHAT_ID
    if not target:
        return 0
    ok = 0
    for n in BACKUP_FILES:
        p = path(n)
        if not os.path.exists(p):
            continue
        try:
            with open(p, "rb") as f:
                bot.send_document(target, f,
                                  caption=f"🗄 نسخة احتياطية — "
                                          f"<code>{n}.json</code>",
                                  visible_file_name=f"{n}.json")
            ok += 1
        except Exception as e:
            log.warning(f"backup {n}: {e}")
    return ok


# ══════════════════════════════════════════════════════
#                 🧹 مهام الخلفية
# ══════════════════════════════════════════════════════
HEALTH = {"probes": 0, "pings": 0, "restarts": 0, "errors": 0,
          "last_update": 0}


def janitor():
    last_backup = now()
    last_arch = now()
    tick = 0
    while True:
        time.sleep(C.JANITOR_TICK)
        tick += 1
        try:
            flush()
            t = now()
            for k, v in list(CHALLENGES.items()):
                if t - v["ts"] > C.CHALLENGE_TTL:
                    CHALLENGES.pop(k, None)
            for k, v in list(STATES.items()):
                if t - v["ts"] > C.STATE_TTL:
                    STATES.pop(k, None)
            with GL:
                for g in list(GAMES.values()):
                    if t - g["ts"] > C.IDLE_TIMEOUT:
                        finish(g, "abort",
                               "⌛ <b>أُنهيت المباراة لعدم النشاط.</b>")
            if tick % 5 == 0:
                rl_cleanup()
            if t - last_arch > C.TICKET_ARCH_EVERY:
                last_arch = t
                archive_old_tickets()
            if t - last_backup > C.BACKUP_EVERY:
                last_backup = t
                do_backup()
        except Exception as e:
            HEALTH["errors"] += 1
            log.error(f"janitor: {e}", exc_info=True)


def keep_alive():
    if not C.SELF_URL:
        log.warning("⚠️ SELF_URL غير مضبوط — النبضة الذاتية معطّلة.")
        return
    try:
        import requests
    except ImportError as e:
        log.warning(f"⚠️ requests غير مثبّت: {e}")
        return
    log.info(f"🔋 النبضة الذاتية: {C.SELF_URL}/ping كل {C.PING_EVERY}s")
    time.sleep(25)
    sess = requests.Session()
    fails = 0
    while True:
        try:
            r = sess.get(f"{C.SELF_URL}/ping", timeout=25)
            if r.status_code == 200:
                HEALTH["pings"] += 1
                fails = 0
            else:
                fails += 1
        except Exception as e:
            fails += 1
            log.debug(f"ping fail #{fails}: {e}")
        if fails and fails % 5 == 0:
            log.warning(f"⚠️ فشلت النبضة {fails} مرات — تحقق من SELF_URL")
        time.sleep(C.PING_EVERY + random.randint(-15, 15))
