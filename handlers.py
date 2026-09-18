# ══════════════════════════════════════════════════════
#                 ⚔️ قبول وإلغاء التحديات
# ══════════════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("ga|"))
def cb_group_accept(c):
    if not rl_callback(c):
        return
    uid = c.from_user.id
    if is_banned(uid):
        return ack(c, "🚫", True)
    touch_user(c.from_user)
    code = c.data[3:]
    ch = CHALLENGES.get(code)
    if not ch:
        return ack(c, "⚠️ التحدي غير صالح أو انتهى.", True)
    if ch["host"] == uid:
        return ack(c, "⚠️ لا يمكنك قبول تحديك بنفسك!", True)
    if in_game(uid) or in_game(ch["host"]):
        return ack(c, "⚠️ أحد اللاعبين في مباراة أخرى حالياً.", True)
    
    CHALLENGES.pop(code, None)
    ack(c, "⚔️ بدأت المباراة!")
    start_group_game(c.message.chat.id, ch["host"], uid,
                     edit=(c.message.chat.id, c.message.message_id))


@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("gc|"))
def cb_group_cancel(c):
    if not rl_callback(c):
        return
    uid = c.from_user.id
    code = c.data[3:]
    ch = CHALLENGES.get(code)
    if not ch:
        return ack(c, "⚠️ التحدي غير موجود.", True)
    sc = getattr(c.message, "sender_chat", None)
    if uid != ch["host"] and not is_boss(c.message.chat.id, uid, sc):
        return ack(c, "⛔ إلغاء التحدي لصاحبه أو للمشرفين فقط.", True)
    
    CHALLENGES.pop(code, None)
    ack(c, "تم إلغاء التحدي.")
    try:
        bot.delete_message(c.message.chat.id, c.message.message_id)
    except Exception as e:
        log.debug(f"del challenge msg: {e}")


# ══════════════════════════════════════════════════════
#                 ♟️ أحداث ورقعة الشطرنج
# ══════════════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("sq|"))
def cb_square(c):
    if not rl_callback(c):
        return
    uid = c.from_user.id
    if is_banned(uid):
        return ack(c, "🚫 أنت محظور.", True)
    
    p = c.data.split("|")
    if len(p) < 3:
        return ack(c)
    
    gid, sq = p[1], int(p[2])
    with GL:
        g = GAMES.get(gid)
        if not g:
            return ack(c, "⚠️ هذه المباراة لم تعد قائمة.", True)
        if g.get("thinking"):
            return ack(c, "⏳ الحاسوب يفكر… انتظر قليلاً.", True)
        if uid not in (g["white"], g["black"]):
            return ack(c, "👀 أنت مشاهد في هذه المباراة.", True)
        if uid != g["turn"]:
            return ack(c, "⏳ ليس دورك الآن!", True)

        b = g["board"]
        sel = g.get("selected")

        # إلغاء التحديد بالضغط على نفس المربع
        if sel == sq:
            g["selected"] = None
            ack(c, "تم إلغاء التحديد.")
            push(g, only=uid)
            return

        # إذا كان المربع المحدد يضم قطعة للاعب الحالي -> إعادة تحديد
        pc = b.piece_at(sq)
        my_color = chess.WHITE if uid == g["white"] else chess.BLACK
        if pc and pc.color == my_color:
            g["selected"] = sq
            ack(c)
            push(g, only=uid)
            return

        # محاولة لعب نقلة إن كان هناك تحديد سابق
        if sel is not None:
            mv = chess.Move(sel, sq)
            
            # الترقية المقترحة (الترقية التلقائية إلى ملكة ثم تأكيد الخيارات)
            if (b.piece_type_at(sel) == chess.PAWN and 
                chess.square_rank(sq) in (0, 7)):
                promo_mv = chess.Move(sel, sq, promotion=chess.QUEEN)
                if promo_mv in b.legal_moves:
                    g["promo"] = (sel, sq, uid)
                    ack(c, "اختر قطعة الترقية 👇")
                    push(g, "✨ اختر قطعة الترقية من الأسفل:")
                    return

            if mv in b.legal_moves:
                ack(c)
                apply_move(g, mv, uid)
                return

        ack(c, "❌ نقلة غير قانونية!", True)


@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("pr|"))
def cb_promo(c):
    if not rl_callback(c):
        return
    uid = c.from_user.id
    p = c.data.split("|")
    if len(p) < 3:
        return ack(c)
    
    gid, piece_code = p[1], p[2]
    with GL:
        g = GAMES.get(gid)
        if not g:
            return ack(c, "⚠️ انتهت المباراة.", True)
        promo = g.get("promo")
        if not promo or promo[2] != uid:
            return ack(c, "⛔ غير مسموح لك بهذا الإجراء.", True)

        sel, sq, _ = promo
        mv = chess.Move(sel, sq, promotion=PROMO.get(piece_code, chess.QUEEN))
        if mv in g["board"].legal_moves:
            ack(c)
            apply_move(g, mv, uid)
        else:
            ack(c, "❌ ترقية غير صالحة.", True)


@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("pc|"))
def cb_promo_cancel(c):
    if not rl_callback(c):
        return
    uid = c.from_user.id
    gid = c.data.split("|")[1]
    with GL:
        g = GAMES.get(gid)
        if g and g.get("promo") and g["promo"][2] == uid:
            g["promo"] = None
            g["selected"] = None
            ack(c, "تم إلغاء الترقية.")
            push(g, only=uid)


@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("rs|"))
def cb_resign(c):
    if not rl_callback(c):
        return
    uid = c.from_user.id
    gid = c.data.split("|")[1]
    with GL:
        g = GAMES.get(gid)
        if not g:
            return ack(c, "⚠️ انتهت المباراة.", True)
        if uid not in (g["white"], g["black"]):
            return ack(c, "⛔ لست لاعباً في هذه المباراة.", True)

        side = "black" if g["white"] == uid else "white"
        ack(c, "استسلمت!")
        finish(g, side, f"🏳️ <b>استسلم {esc(uname(uid))}</b>\n"
                        f"🎉 الفائز: <b>{esc(uname(g[side]))}</b>")


@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("dr|"))
def cb_draw_request(c):
    if not rl_callback(c):
        return
    uid = c.from_user.id
    gid = c.data.split("|")[1]
    with GL:
        g = GAMES.get(gid)
        if not g:
            return ack(c, "⚠️ انتهت المباراة.", True)
        if uid not in (g["white"], g["black"]):
            return ack(c, "⛔ لست لاعباً في هذه المباراة.", True)

        if g["mode"] == "ai":
            if ai_accepts_draw(g):
                ack(c, "وافق الحاسوب على التعادل.")
                finish(g, "draw", "🤝 <b>تم التعادل باتفاق الطرفين</b>")
            else:
                ack(c, "❌ رفض الحاسوب طلب التعادل، استمر باللعب!", True)
            return

        other = g["black"] if g["white"] == uid else g["white"]
        g["draw_offer"] = uid
        ack(c, "تم إرسال طلب التعادل.")
        push(g, f"🤝 <b>طلب {esc(uname(uid))} التعادل!</b> "
                f"بانتظار موافقة {esc(uname(other))}…")


@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("da|"))
def cb_draw_answer(c):
    if not rl_callback(c):
        return
    uid = c.from_user.id
    p = c.data.split("|")
    gid, ans = p[1], p[2]
    with GL:
        g = GAMES.get(gid)
        if not g:
            return ack(c, "⚠️ انتهت المباراة.", True)
        off = g.get("draw_offer")
        if not off or off == uid or uid not in (g["white"], g["black"]):
            return ack(c, "⛔ ليس لديك عرض تعادل معلق.", True)

        g["draw_offer"] = None
        if ans == "y":
            ack(c, "وافقت على التعادل.")
            finish(g, "draw", "🤝 <b>تم التعادل بالتراضي!</b>")
        else:
            ack(c, "رفضت التعادل.")
            push(g, f"❌ رفض {esc(uname(uid))} طلب التعادل!")


@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("ae|"))
def cb_admin_end(c):
    if not rl_callback(c):
        return
    uid = c.from_user.id
    gid = c.data.split("|")[1]
    sc = getattr(c.message, "sender_chat", None)
    with GL:
        g = GAMES.get(gid)
        if not g:
            return ack(c, "⚠️ انتهت المباراة.", True)
        if not is_boss(c.message.chat.id, uid, sc) and uid not in (g["white"], g["black"]):
            return ack(c, "⛔ هذا الإجراء للمشرفين واللاعبين فقط.", True)

        ack(c, "تم إنهاء المباراة.")
        finish(g, "abort", f"🛑 <b>أُنهيت المباراة بواسطة "
                           f"{esc(uname(uid))}</b>")
        audit_record("end_game", uid, uname(uid),
                     detail=f"{uname(g['white'])} vs {uname(g['black'])}",
                     chat_id=c.message.chat.id)


# ══════════════════════════════════════════════════════
#                 🆘 الدعم والتذاكر
# ══════════════════════════════════════════════════════
def open_support(chat_id, uid):
    STATES[uid] = {"action": "support", "ts": now()}
    txt = ("🆘 <b>مركز الدعم الفني</b>\n━━━━━━━━━━━━━━━\n"
           "اكتب رسالتك الآن أو استفسارك وسوف يتم إرساله إلى الإدارة مباشرةً.\n\n"
           "<i>أرسل /cancel لإلغاء المراسلة.</i>")
    safe_send(chat_id, txt)


@bot.message_handler(commands=['support', 'دعم', 'تذكرة'])
def cmd_support(m):
    uid = m.from_user.id
    if is_banned(uid):
        return
    touch_user(m.from_user)
    open_support(m.chat.id, uid)


@bot.message_handler(commands=['reply', 'رد'])
def cmd_reply(m):
    """الرد على تذكرة: /reply <آيدي> <النص>"""
    uid = m.from_user.id
    if not is_admin(uid):
        return
    parts = (m.text or "").split(maxsplit=2)
    if len(parts) < 3:
        return bot.reply_to(m, "الاستخدام: <code>/reply 12345678 نص الرسالة</code>")
    
    target_id = parts[1]
    text = parts[2]
    
    msg = safe_send(target_id,
                    f"✍️ <b>رد من الدعم الفني:</b>\n━━━━━━━━━━━━━━━\n{esc(text)}")
    if msg:
        bot.reply_to(m, f"✅ تم إرسال الرد إلى <code>{target_id}</code> بنجاح.")
        audit_record("reply", uid, uname(uid), target_id=target_id, detail=text[:100])
    else:
        bot.reply_to(m, f"❌ فشل إرسال الرسالة إلى <code>{target_id}</code> (قد يكون حظر البوت).")


# ══════════════════════════════════════════════════════
#                 🛠 أوامر الإدارة والمالك
# ══════════════════════════════════════════════════════
@bot.message_handler(commands=['stats', 'احصائيات'])
def cmd_stats(m):
    uid = m.from_user.id
    if not is_admin(uid):
        return
    up = now() - START_TS
    tt = tt_stats()
    rl = rl_stats()
    ts = ticket_stats()
    
    txt = (
        "📊 <b>إحصائيات النظام الشاملة</b>\n━━━━━━━━━━━━━━━\n"
        f"⏱ مدة التشغيل: <b>{human(up)}</b>\n"
        f"👥 المسجلون: <b>{len(users)}</b>\n"
        f"👑 المشرفون: <b>{len(admins)}</b>\n"
        f"🚫 المحظورون: <b>{len(banned)}</b>\n"
        f"♟ المباريات النشطة: <b>{len(GAMES)}</b>\n"
        f"⚔️ التحديات المعلقة: <b>{len(CHALLENGES)}</b>\n"
        "━━━━━━━━━━━━━━━\n"
        f"🧠 <b>ذاكرة المحرك (TT):</b> {tt['size']} عنصر (ضربات: {tt['hits']})\n"
        f"🚦 <b>الضغطات:</b> مسموح {rl['allowed']} │ محظور {rl['blocked']}\n"
        f"📩 <b>التذاكر:</b> نشطة {ts['active']} │ مؤرشفة {ts['archived']}"
    )
    bot.reply_to(m, txt)


@bot.message_handler(commands=['audit', 'تدقيق'])
def cmd_audit(m):
    uid = m.from_user.id
    if not is_admin(uid):
        return
    p = (m.text or "").split()
    n = int(p[1]) if len(p) > 1 and p[1].isdigit() else 10
    rec = audit_recent(n)
    if not rec:
        return bot.reply_to(m, "📋 سجل التدقيق فارغ.")
    
    txt = f"📋 <b>آخر {len(rec)} إجراءات مسجلة:</b>\n━━━━━━━━━━━━━━━\n"
    txt += "\n\n".join(audit_fmt(e) for e in rec)
    bot.reply_to(m, txt)


@bot.message_handler(commands=['reset_game', 'انهاء_لاعب'])
def cmd_reset_game(m):
    uid = m.from_user.id
    if not is_admin(uid):
        return
    p = (m.text or "").split()
    if len(p) < 2:
        return bot.reply_to(m, "الاستخدام: <code>/reset_game <ID></code>")
    try:
        t_id = int(p[1])
    except ValueError:
        return bot.reply_to(m, "❌ آيدي غير صالح.")
    
    with GL:
        gid = in_game(t_id)
        if not gid or gid not in GAMES:
            return bot.reply_to(m, "⚠️ هذا اللاعب ليس في مباراة حالياً.")
        g = GAMES[gid]
        finish(g, "abort", f"🔄 <b>أُنهيت المباراة بواسطة الإدارة</b>")
        audit_record("reset_game", uid, uname(uid), target_id=t_id)
    bot.reply_to(m, f"✅ تم إنهاء مباراة اللاعب <code>{t_id}</code>.")


@bot.message_handler(commands=['ban', 'حظر'])
def cmd_ban(m):
    uid = m.from_user.id
    if not is_admin(uid):
        return
    p = (m.text or "").split()
    if len(p) < 2:
        return bot.reply_to(m, "الاستخدام: <code>/ban <ID></code>")
    try:
        t_id = int(p[1])
    except ValueError:
        return bot.reply_to(m, "❌ آيدي غير صالح.")
    
    if is_owner(t_id):
        return bot.reply_to(m, "❌ لا يمكنك حظر مالك البوت!")
    
    if t_id not in banned:
        banned.append(t_id)
        save_json("banned", banned)
        audit_record("ban", uid, uname(uid), target_id=t_id)
        
        # إنهاء أي مباراة قائمة للمحظور
        with GL:
            gid = in_game(t_id)
            if gid and gid in GAMES:
                finish(GAMES[gid], "abort", "🚫 أُنهيت المباراة بسبب حظر أحد اللاعبين.")
        bot.reply_to(m, f"🚫 تم حظر المستخدم <code>{t_id}</code> بنجاح.")
    else:
        bot.reply_to(m, "⚠️ هذا المستخدم محظور بالفعل.")


@bot.message_handler(commands=['unban', 'الغاء_حظر'])
def cmd_unban(m):
    uid = m.from_user.id
    if not is_admin(uid):
        return
    p = (m.text or "").split()
    if len(p) < 2:
        return bot.reply_to(m, "الاستخدام: <code>/unban <ID></code>")
    try:
        t_id = int(p[1])
    except ValueError:
        return bot.reply_to(m, "❌ آيدي غير صالح.")
    
    if t_id in banned:
        banned.remove(t_id)
        save_json("banned", banned)
        audit_record("unban", uid, uname(uid), target_id=t_id)
        bot.reply_to(m, f"✅ تم إلغاء حظر <code>{t_id}</code>.")
    else:
        bot.reply_to(m, "⚠️ هذا المستخدم ليس محظوراً.")


# ══════════════════════════════════════════════════════
#                 👑 أوامر المالك
# ══════════════════════════════════════════════════════
@bot.message_handler(commands=['addadmin', 'ترقية'])
def cmd_addadmin(m):
    uid = m.from_user.id
    if not is_owner(uid):
        return
    p = (m.text or "").split()
    if len(p) < 2:
        return bot.reply_to(m, "الاستخدام: <code>/addadmin <ID></code>")
    try:
        t_id = int(p[1])
    except ValueError:
        return bot.reply_to(m, "❌ آيدي غير صالح.")
    
    if t_id not in admins:
        admins.append(t_id)
        save_json("admins", admins)
        audit_record("promote", uid, uname(uid), target_id=t_id)
        bot.reply_to(m, f"👑 تم رفع <code>{t_id}</code> مشرفاً في البوت.")
    else:
        bot.reply_to(m, "⚠️ هذا المستخدم مشرف بالفعل.")


@bot.message_handler(commands=['removeadmin', 'تنزيل'])
def cmd_removeadmin(m):
    uid = m.from_user.id
    if not is_owner(uid):
        return
    p = (m.text or "").split()
    if len(p) < 2:
        return bot.reply_to(m, "الاستخدام: <code>/removeadmin <ID></code>")
    try:
        t_id = int(p[1])
    except ValueError:
        return bot.reply_to(m, "❌ آيدي غير صالح.")
    
    if t_id in admins:
        admins.remove(t_id)
        save_json("admins", admins)
        audit_record("demote", uid, uname(uid), target_id=t_id)
        bot.reply_to(m, f"⬇️ تم تنزيل <code>{t_id}</code> من المشرفين.")
    else:
        bot.reply_to(m, "⚠️ هذا المستخدم ليس مشرفاً.")


@bot.message_handler(commands=['admins', 'المشرفين'])
def cmd_admins(m):
    if not is_owner(m.from_user.id):
        return
    txt = f"👑 <b>مالك البوت:</b> <code>{C.OWNER_ID}</code>\n\n🛠 <b>المشرفون ({len(admins)}):</b>\n"
    for a in admins:
        txt += f"• {esc(uname(a))} (<code>{a}</code>)\n"
    bot.reply_to(m, txt)


@bot.message_handler(commands=['broadcast', 'إذاعة', 'اذاعة'])
def cmd_broadcast(m):
    uid = m.from_user.id
    if not is_owner(uid):
        return
    text = m.text.partition(' ')[2]
    if not text and not m.reply_to_message:
        return bot.reply_to(m, "الاستخدام: <code>/broadcast نص الرسالة</code> (أو بالرد على رسالة)")
    
    msg = bot.reply_to(m, "📢 جاري بدء الإذاعة…")
    ok, fail = 0, 0
    u_keys = list(users.keys())
    
    def _run_bc():
        nonlocal ok, fail
        for u_id in u_keys:
            try:
                if m.reply_to_message:
                    bot.copy_message(u_id, m.chat.id, m.reply_to_message.message_id)
                else:
                    bot.send_message(u_id, text)
                ok += 1
            except Exception:
                fail += 1
            time.sleep(0.04) # حماية من حدود تلغرام
        safe_edit(m.chat.id, msg.message_id,
                  f"📢 <b>اكتملت الإذاعة!</b>\n━━━━━━━━━━━━━━━\n"
                  f"✅ وصلت: <b>{ok}</b>\n❌ فشلت: <b>{fail}</b>")
        audit_record("broadcast", uid, uname(uid), detail=f"ok={ok}, fail={fail}")

    Thread(target=_run_bc, daemon=True).start()


@bot.message_handler(commands=['backup', 'نسخة'])
def cmd_backup(m):
    uid = m.from_user.id
    if not is_owner(uid):
        return
    bot.reply_to(m, "🗄 جاري إنشاء وإرسال النسخة الاحتياطية…")
    count = do_backup(m.chat.id)
    audit_record("backup", uid, uname(uid), detail=f"files={count}")
    bot.send_message(m.chat.id, f"✅ اكتمل النسخ الاحتياطي ({count} ملفات).")


@bot.message_handler(commands=['archive', 'ارشفة'])
def cmd_archive(m):
    uid = m.from_user.id
    if not is_owner(uid):
        return
    p = (m.text or "").split()
    days = int(p[1]) if len(p) > 1 and p[1].isdigit() else C.TICKET_TTL_DAYS
    archived = archive_old_tickets(days)
    audit_record("archive", uid, uname(uid), detail=f"tickets={archived}, days={days}")
    bot.reply_to(m, f"🗃 تم أرشفة <b>{archived}</b> تذكرة أقدم من {days} يوم.")


@bot.message_handler(commands=['restore', 'استعادة'])
def cmd_restore(m):
    """استعادة ملف json آمنة بالرد على ملف مقترن مع الفحص Structural Validation"""
    uid = m.from_user.id
    if not is_owner(uid):
        return
    if not m.reply_to_message or not m.reply_to_message.document:
        return bot.reply_to(m, "↩️ أرسل هذا الأمر بالرد على ملف <code>.json</code> للاستعادة.")
    
    doc = m.reply_to_message.document
    filename = doc.file_name or ""
    file_base = filename.replace(".json", "").strip()
    
    if file_base not in BACKUP_FILES:
        return bot.reply_to(m, f"❌ اسم الملف غير مسموح. الملفات المسموحة: {', '.join(BACKUP_FILES)}")

    try:
        file_info = bot.get_file(doc.file_id)
        downloaded = bot.download_file(file_info.file_path)
        data = json.loads(downloaded.decode("utf-8"))
    except Exception as e:
        return bot.reply_to(m, f"❌ فشل قراءة الملف كـ JSON صالح: {e}")

    valid, msg, clean_data = schema_validate(file_base, data)
    if not valid:
        return bot.reply_to(m, f"❌ <b>فشل فحص البنية:</b>\n{msg}")

    # استبدال وتطبيق البيانات
    if file_base == "users":
        users.clear(); users.update(clean_data)
    elif file_base == "admins":
        admins.clear(); admins.extend(clean_data)
    elif file_base == "banned":
        banned.clear(); banned.extend(clean_data)
    elif file_base == "tickets":
        tickets.clear(); tickets.update(clean_data)
    elif file_base == "tickets_archive":
        tickets_archive.clear(); tickets_archive.update(clean_data)
    elif file_base == "audit":
        audit_reload()

    save_json(file_base, clean_data)
    audit_record("restore", uid, uname(uid), detail=f"restored {file_base}.json")
    bot.reply_to(m, f"✅ <b>تمت الاستعادة بنجاح!</b>\n{msg}")


# ══════════════════════════════════════════════════════
#                 💬 معالج الرسائل النصية
# ══════════════════════════════════════════════════════
@bot.message_handler(func=lambda m: True, content_types=['text'])
def handle_text(m):
    uid = m.from_user.id
    if is_banned(uid):
        return
    if not rl_message(uid):
        return rl_notify(m.chat.id, uid)
    
    txt = (m.text or "").strip()
    
    # التعامل مع أزرار لوحة التوجيه السريعة (Reply Keyboard)
    if txt == "♟ بدء":
        return cmd_start(m)
    elif txt == "🏆 المتصدرين":
        return cmd_top(m)
    elif txt == "👤 ملفي":
        return cmd_me(m)
    elif txt == "📖 المساعدة":
        return cmd_help(m)
    elif txt == "🆘 الدعم":
        return cmd_support(m)

    # حالة الدعم الفني المعلقة
    st = STATES.get(uid)
    if st and st.get("action") == "support":
        STATES.pop(uid, None)
        tid = uuid.uuid4().hex[:8]
        ticket = {"uid": uid, "name": uname(uid),
                  "username": m.from_user.username or "",
                  "text": txt, "ts": now()}
        tickets[tid] = ticket
        save_json("tickets", tickets)

        # إشعار المالك والمشرفين
        info_txt = (f"📩 <b>تذكرة دعم جديدة #{tid}</b>\n━━━━━━━━━━━━━━━\n"
                    f"👤 من: {mention(uid, uname(uid))} (<code>{uid}</code>)\n"
                    f"💬 النص:\n<i>{esc(txt)}</i>")
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("✍️ رد سريـع",
                                          callback_data=f"rep|{uid}"))
        
        safe_send(C.OWNER_ID, info_txt, kb)
        bot.reply_to(m, "✅ تم إرسال رسالتك إلى فريق الدعم بنجاح! سنرد عليك في أقرب وقت.")
        return


@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("rep|"))
def cb_admin_reply_btn(c):
    if not rl_callback(c):
        return
    uid = c.from_user.id
    if not is_admin(uid):
        return ack(c, "⛔", True)
    t_id = c.data.split("|")[1]
    ack(c)
    safe_send(c.message.chat.id,
              f"للرد على المستخدم، استخدم الأمر التالي:\n"
              f"<code>/reply {t_id} نص_الرد</code>")
