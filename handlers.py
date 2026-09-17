import chess
import uuid
from telebot import types, apihelper
import database as db
from config import PIECES, WELCOME_MSG, HELP_MSG, CHANNEL_USERNAME, OWNER_ID

# 🛡️ التحقق من الاشتراك الإجباري
def is_subscribed(bot, user_id):
    if not CHANNEL_USERNAME or CHANNEL_USERNAME == "@YourChannelUsername":
        return True
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['creator', 'administrator', 'member']
    except Exception:
        return True

def send_sub_request(bot, chat_id):
    clean_username = CHANNEL_USERNAME.replace("@", "")
    markup = types.InlineKeyboardMarkup()
    btn_channel = types.InlineKeyboardButton("📢 اشترك في القناة أولاً", url=f"https://t.me/{clean_username}")
    btn_check = types.InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_subscription")
    markup.add(btn_channel)
    markup.add(btn_check)
    
    bot.send_message(
        chat_id, 
        "⚠️ **عذراً عزيزي!**\nعليك الاشتراك في القناة أولاً لاستخدام البوت.", 
        reply_markup=markup,
        parse_mode="Markdown"
    )

# 🎨 رسم الرقعة كأزرار تفاعلية
def render_board_markup(board, selected_sq=None):
    markup = types.InlineKeyboardMarkup(row_width=8)
    buttons = []
    for sq in range(64):
        rank = 7 - (sq // 8)
        file = sq % 8
        square_id = chess.square(file, rank)
        piece = board.piece_at(square_id)
        symbol = PIECES.get(piece.symbol(), '▫️') if piece else '▫️'
        if selected_sq == square_id:
            symbol = "🎯"
        buttons.append(types.InlineKeyboardButton(text=symbol, callback_data=f"sq_{square_id}"))
        if len(buttons) == 8:
            markup.row(*buttons)
            buttons = []
    return markup

# 🛡️ تحديث آمن للرقعة بدون وميض أو أخطاء
def safe_edit_markup(bot, chat_id, msg_id, markup):
    try:
        bot.edit_message_reply_markup(chat_id, msg_id, reply_markup=markup)
    except apihelper.ApiTelegramException as e:
        if "message is not modified" not in str(e).lower():
            pass

def safe_edit_text(bot, chat_id, msg_id, text, markup=None):
    try:
        bot.edit_message_text(text, chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    except apihelper.ApiTelegramException as e:
        if "message is not modified" not in str(e).lower():
            pass

# 🎮 بدء مباراة ضد البوت
def start_bot_game(bot, chat_id, user_id, message_id=None):
    gid = f"bot_{user_id}"
    with db.games_lock:
        db.games_db[gid] = {
            "board": chess.Board(), "white": user_id, "black": "BOT",
            "selected": None, "turn": user_id, "msg_ids": {}
        }
    board = db.games_db[gid]["board"]
    markup = render_board_markup(board)
    txt = "♟️ **دورك (الأبيض)** | اضغط قطعة ثم المربع الهدف"
    
    if message_id:
        safe_edit_text(bot, chat_id, message_id, txt, markup)
        with db.games_lock: db.games_db[gid]["msg_ids"][user_id] = message_id
    else:
        msg = bot.send_message(chat_id, txt, reply_markup=markup, parse_mode="Markdown")
        with db.games_lock: db.games_db[gid]["msg_ids"][user_id] = msg.message_id

# ⚔️ بدء مباراة لاعب ضد لاعب
def start_pvp_game(bot, w_id, b_id, group_chat_id=None):
    gid = f"pvp_{w_id}_{b_id}"
    with db.games_lock:
        db.games_db[gid] = {
            "board": chess.Board(), "white": w_id, "black": b_id,
            "selected": None, "turn": w_id, "msg_ids": {}
        }
    board = db.games_db[gid]["board"]
    markup = render_board_markup(board)
    w_name = db.users_db.get(str(w_id), {}).get("name", "لاعب1")
    b_name = db.users_db.get(str(b_id), {}).get("name", "لاعب2")
    
    txt_w = f"♟️ **دورك (أبيض)** ضد {b_name}"
    txt_b = f"♟️ **دور الخصم** (أنت أسود) ضد {w_name}"
    
    if group_chat_id:
        msg = bot.send_message(group_chat_id, f"⚔️ مباراة مجموعة:\n⚪ {w_name} vs ⚫ {b_name}\n♟️ دور: {w_name}", reply_markup=markup, parse_mode="Markdown")
        with db.games_lock: db.games_db[gid]["msg_ids"] = {w_id: msg.message_id, b_id: msg.message_id}
    else:
        m1 = bot.send_message(w_id, txt_w, reply_markup=markup, parse_mode="Markdown")
        m2 = bot.send_message(b_id, txt_b, reply_markup=markup, parse_mode="Markdown")
        with db.games_lock: db.games_db[gid]["msg_ids"] = {w_id: m1.message_id, b_id: m2.message_id}

# 🔄 تحديث واجهة اللعبة بعد كل نقلة
def update_game_ui(bot, gid, status_msg):
    with db.games_lock:
        g = db.games_db.get(gid)
    if not g: return
    
    board = g["board"]
    markup = render_board_markup(board)
    w_name = db.users_db.get(str(g["white"]), {}).get("name", "?")
    b_name = db.users_db.get(str(g["black"]), {}).get("name", "البوت") if g["black"] != "BOT" else "البوت"
    turn_name = w_name if g["turn"] == g["white"] else b_name
    
    txt = f"{status_msg}\n♟️ **دور:** {turn_name}"
    for pid, mid in g["msg_ids"].items():
        safe_edit_text(bot, pid, mid, txt, markup)

# 🖱️ معالجة الضغط على المربعات
def handle_square_click(bot, call):
    sq = int(call.data.split("_")[1])
    uid = call.from_user.id
    u_name = db.users_db.get(str(uid), {}).get("name", call.from_user.first_name)

    with db.games_lock:
        gid, g = next(((k, v) for k, v in db.games_db.items() if v["white"] == uid or v["black"] == uid), (None, None))
    
    if not g:
        bot.answer_callback_query(call.id, "لا توجد مباراة نشطة.")
        return
    if g["turn"] != uid:
        bot.answer_callback_query(call.id, "ليس دورك! انتظر الخصم.")
        return

    board = g["board"]
    sel = g["selected"]

    if sel is None:
        piece = board.piece_at(sq)
        if piece and ((g["turn"] == g["white"] and piece.color == chess.WHITE) or 
                      (g["turn"] == g["black"] and piece.color == chess.BLACK)):
            g["selected"] = sq
            markup = render_board_markup(board, sq)
            safe_edit_markup(bot, call.message.chat.id, call.message.message_id, markup)
            bot.answer_callback_query(call.id, f"تم تحديد {chess.square_name(sq)}")
    else:
        move = chess.Move(sel, sq)
        if board.piece_at(sel).piece_type == chess.PAWN and (sq // 8 in [0, 7]):
            move.promotion = chess.QUEEN
            
        if move in board.legal_moves:
            cap = board.is_capture(move)
            board.push(move)
            g["selected"] = None
            status = "⚔️ أكل قطعة!" if cap else f"♟️ نقلة بواسطة {u_name}"
            g["turn"] = g["black"] if g["turn"] == g["white"] else g["white"]

            if board.is_checkmate():
                db.add_points(uid, True)
                for pid, mid in g["msg_ids"].items():
                    safe_edit_text(bot, pid, mid, f"🎉 كش مات! فاز {u_name}!")
                with db.games_lock: del db.games_db[gid]
                bot.answer_callback_query(call.id, "🏆 انتهت المباراة!")
                return
            if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
                for pid, mid in g["msg_ids"].items():
                    safe_edit_text(bot, pid, mid, "🤝 تعادل!")
                with db.games_lock: del db.games_db[gid]
                bot.answer_callback_query(call.id, "🤝 انتهت بالتعادل!")
                return

            if g["black"] == "BOT":
                legal = list(board.legal_moves)
                if legal:
                    board.push(legal[0])
                g["turn"] = g["white"]
                if board.is_checkmate():
                    db.add_points(uid, False)
                    safe_edit_text(bot, call.message.chat.id, call.message.message_id, "🤖 فاز البوت!")
                    with db.games_lock: del db.games_db[gid]
                    bot.answer_callback_query(call.id, "❌ خسرت!")
                    return
                if board.is_stalemate() or board.is_insufficient_material():
                    safe_edit_text(bot, call.message.chat.id, call.message.message_id, "🤝 تعادل!")
                    with db.games_lock: del db.games_db[gid]
                    bot.answer_callback_query(call.id, "🤝 تعادل!")
                    return

            update_game_ui(bot, gid, status)
            bot.answer_callback_query(call.id)
        else:
            g["selected"] = None
            safe_edit_markup(bot, call.message.chat.id, call.message.message_id, render_board_markup(board))
            bot.answer_callback_query(call.id, "❌ نقلة غير قانونية!")

# 📥 تسجيل جميع الأوامر
def register_handlers(bot):
    @bot.message_handler(commands=['start', 'menu'])
    def cmd_start(message):
        db.register_user(message.from_user)
        uid = message.from_user.id

        # 🔒 فحص الاشتراك
        if not is_subscribed(bot, uid):
            send_sub_request(bot, message.chat.id)
            return

        args = message.text.split()
        if len(args) > 1 and args[1].startswith("game_"):
            cid = args[1].replace("game_", "")
            with db.challenges_lock:
                if cid in db.pending_challenges:
                    host = db.pending_challenges.pop(cid)["host_id"]
                    if host != uid:
                        start_pvp_game(bot, host, uid)
                        return
                    bot.reply_to(message, "⚠️ لا يمكنك تحدي نفسك!")
                    return
                bot.reply_to(message, "⚠️ الرابط غير صالح أو مستخدم.")
                return

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🤖 ضد البوت", callback_data="mode_bot"),
            types.InlineKeyboardButton("⚔️ تحدي صديق", callback_data="mode_friend"),
            types.InlineKeyboardButton("👥 مجموعة", callback_data="mode_group"),
            types.InlineKeyboardButton("🏆 المتصدرين", callback_data="view_top"),
            types.InlineKeyboardButton("📖 التعليمات", callback_data="view_help"),
            types.InlineKeyboardButton("🆘 الدعم", callback_data="view_support"),
            types.InlineKeyboardButton("🌐 اللغة", callback_data="toggle_lang")
        )
        bot.send_message(message.chat.id, f"{WELCOME_MSG}\n\nاختر نمط اللعب:", reply_markup=markup)

    @bot.message_handler(commands=['help', 'التعليمات'])
    def cmd_help(message):
        txt = HELP_MSG
        if db.is_admin(message.from_user.id):
            txt += "\n🛠 **إشراف:** `/reset_game <ID>` | `/stats`"
        if db.is_owner(message.from_user.id):
            txt += "\n👑 **مالك:** `/addadmin <ID>` | `/removeadmin <ID>` | `/admins` | `/broadcast <نص>`"
        bot.send_message(message.chat.id, txt, parse_mode="Markdown")

    @bot.message_handler(commands=['support', 'الدعم'])
    def cmd_support(message):
        bot.reply_to(message, "📩 قل ماذا تريد لمساعدتك؟ سأحول رسالتك للمالك مباشرة.")
        bot.register_next_step_handler(message, forward_support)

    def forward_support(message):
        uid = message.from_user.id
        name = message.from_user.first_name
        username = f"@{message.from_user.username}" if message.from_user.username else "غير متوفر"
        txt = f"🆘 **رسالة دعم جديدة**\n👤 `{name}` | 🆔 `{uid}` | 🔗 {username}\n\n📝 {message.text}"
        try:
            bot.send_message(OWNER_ID, txt, parse_mode="Markdown")
            bot.reply_to(message, "✅ تم الإرسال للمالك. سنرد قريباً.")
        except:
            bot.reply_to(message, "❌ تعذر الإرسال. تأكد من أن المالك شغل البوت.")

    @bot.message_handler(commands=['addadmin'])
    def add_admin(message):
        if not db.is_owner(message.from_user.id): return bot.reply_to(message, "⚠️ للمالك فقط.")
        try:
            aid = int(message.text.split()[1])
            if aid not in db.admins_db:
                db.admins_db.append(aid); db.save_json("admins", db.admins_db)
                bot.reply_to(message, f"✅ تم تعيين `{aid}`")
            else: bot.reply_to(message, "⚠️ موجود مسبقاً")
        except: bot.reply_to(message, "`/addadmin <ID>`")

    @bot.message_handler(commands=['removeadmin'])
    def rem_admin(message):
        if not db.is_owner(message.from_user.id): return bot.reply_to(message, "⚠️ للمالك فقط.")
        try:
            aid = int(message.text.split()[1])
            if aid in db.admins_db:
                db.admins_db.remove(aid); db.save_json("admins", db.admins_db)
                bot.reply_to(message, f"✅ تم إزالة `{aid}`")
            else: bot.reply_to(message, "⚠️ ليس مساعداً")
        except: bot.reply_to(message, "`/removeadmin <ID>`")

    @bot.message_handler(commands=['admins'])
    def list_admins(message):
        if not db.is_owner(message.from_user.id): return bot.reply_to(message, "⚠️ للمالك فقط.")
        bot.reply_to(message, "📋 **المساعدون:**\n" + "\n".join(f"• `{a}`" for a in db.admins_db) or "لا يوجد", parse_mode="Markdown")

    @bot.message_handler(commands=['broadcast'])
    def broadcast(message):
        if not db.is_owner(message.from_user.id): return bot.reply_to(message, "⚠️ للمالك فقط.")
        txt = message.text.replace("/broadcast", "").strip()
        if not txt: return bot.reply_to(message, "`/broadcast نص الرسالة`")
        c = 0
        for uid in list(db.users_db.keys()):
            try: bot.send_message(int(uid), f"📢 **تنبيه:**\n{txt}", parse_mode="Markdown"); c+=1
            except: pass
        bot.reply_to(message, f"✅ تم لـ {c} مستخدم")

    @bot.message_handler(commands=['reset_game'])
    def reset_game(message):
        if not db.is_admin(message.from_user.id): return bot.reply_to(message, "⚠️ للمشرفين فقط.")
        try:
            tid = int(message.text.split()[1])
            with db.games_lock:
                for gid, g in list(db.games_db.items()):
                    if g["white"] == tid or g["black"] == tid:
                        del db.games_db[gid]
                        return bot.reply_to(message, f"✅ تم إنهاء مباراة `{tid}`")
            bot.reply_to(message, "❌ لا توجد مباراة نشطة له")
        except: bot.reply_to(message, "`/reset_game <ID>`")

    @bot.message_handler(commands=['stats'])
    def stats(message):
        if not db.is_admin(message.from_user.id): return bot.reply_to(message, "⚠️ للمشرفين فقط.")
        with db.games_lock, db.challenges_lock:
            bot.reply_to(message, f"📊 **إحصائيات:**\n• مستخدمون: `{len(db.users_db)}`\n• مباريات: `{len(db.games_db)}`\n• تحديات: `{len(db.pending_challenges)}`", parse_mode="Markdown")

    @bot.message_handler(commands=['cancel', 'stop'])
    def cancel(message):
        uid = message.from_user.id
        with db.games_lock:
            for gid, g in list(db.games_db.items()):
                if g["white"] == uid or g["black"] == uid:
                    del db.games_db[gid]
                    return bot.reply_to(message, "🚫 تم الإلغاء")
        bot.reply_to(message, "⚠️ لا توجد مباراة نشطة")

    @bot.message_handler(commands=['leaderboard', 'top'])
    def leaderboard(message):
        top = sorted(db.users_db.items(), key=lambda x: x[1].get("points", 0), reverse=True)[:10]
        if not top: return bot.send_message(message.chat.id, "لا يوجد لاعبون بعد.")
        txt = "🏆 **أفضل 10:**\n\n" + "\n".join(f"{i}️⃣ **{u.get('name','?')}** — ⭐ `{u.get('points',0)}`" for i, (_, u) in enumerate(top, 1))
        bot.send_message(message.chat.id, txt, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda c: True)
    def callbacks(call):
        uid = call.from_user.id
        db.register_user(call.from_user)

        # 🔒 زر التحقق من الاشتراك
        if call.data == "check_subscription":
            if is_subscribed(bot, uid):
                bot.answer_callback_query(call.id, "✅ تم التحقق بنجاح!")
                bot.delete_message(call.message.chat.id, call.message.message_id)
                cmd_start(call.message)
            else:
                bot.answer_callback_query(call.id, "❌ لم تشترك في القناة بعد!", show_alert=True)
            return

        if not is_subscribed(bot, uid):
            send_sub_request(bot, call.message.chat.id)
            bot.answer_callback_query(call.id)
            return

        if call.data == "toggle_lang":
            db.users_db[str(uid)]["lang"] = "en" if db.users_db[str(uid)].get("lang") == "ar" else "ar"
            db.save_json("users", db.users_db)
            bot.answer_callback_query(call.id, "Language changed!")
            cmd_start(call.message)
        elif call.data == "view_top": leaderboard(call.message); bot.answer_callback_query(call.id)
        elif call.data == "view_help": cmd_help(call.message); bot.answer_callback_query(call.id)
        elif call.data == "view_support": cmd_support(call.message); bot.answer_callback_query(call.id)
        elif call.data == "mode_bot":
            start_bot_game(bot, call.message.chat.id, uid, call.message.message_id)
            bot.answer_callback_query(call.id)
        elif call.data == "mode_friend":
            cid = str(uuid.uuid4())[:8]
            with db.challenges_lock: db.pending_challenges[cid] = {"host_id": uid}
            bot_username = bot.get_me().username
            bot.send_message(call.message.chat.id, f"أرسل هذا الرابط لصديقك:\nhttps://t.me/{bot_username}?start=game_{cid}")
            bot.answer_callback_query(call.id)
        elif call.data == "mode_group":
            if call.message.chat.type in ['group', 'supergroup']:
                cid = f"grp_{call.message.chat.id}_{uid}"
                with db.challenges_lock: db.group_challenges[cid] = {"host_id": uid}
                mk = types.InlineKeyboardMarkup()
                mk.add(types.InlineKeyboardButton("⚔️ قبول التحدي", callback_data=f"join_grp_{cid}"))
                bot.send_message(call.message.chat.id, f"⚔️ تحدي جديد من {db.users_db.get(str(uid),{}).get('name', call.from_user.first_name)}!", reply_markup=mk)
                bot.answer_callback_query(call.id)
            else:
                bot.answer_callback_query(call.id, "⚠️ للمجموعات فقط!", show_alert=True)
        elif call.data.startswith("join_grp_"):
            cid = call.data.replace("join_grp_", "")
            with db.challenges_lock:
                if cid in db.group_challenges:
                    host = db.group_challenges.pop(cid)["host_id"]
                    if host != uid:
                        start_pvp_game(bot, host, uid, group_chat_id=call.message.chat.id)
                        bot.answer_callback_query(call.id)
                    else: bot.answer_callback_query(call.id, "⚠️ لا يمكنك تحدي نفسك!", show_alert=True)
                else: bot.answer_callback_query(call.id, "⚠️ التحدي انتهى.", show_alert=True)
        elif call.data.startswith("sq_"):
            handle_square_click(bot, call)
