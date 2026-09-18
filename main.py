# -*- coding: utf-8 -*-
"""🚀 نقطة التشغيل الرئيسية وخادم خفيف مع إدارة دورة الحياة"""
import sys
import time
import signal
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import config as C
from core import (bot, log, ME, HEALTH, janitor, keep_alive, do_backup,
                  flush_all)
import handlers  # تسجيل معالجات الأوامر والأزرار


# ══════════════════════════════════════════════════════
#                 🌐 خادم الويب والصحة
# ══════════════════════════════════════════════════════
class WebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        HEALTH["probes"] += 1
        HEALTH["last_update"] = int(time.time())
        
        if self.path in ("/", "/ping", "/health"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"OK - Chess Bot is Running Successfully!")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # تعطيل سجّلات HTTP لتجنّب إغراق شاشة العرض


def start_web_server():
    if not C.WEB_ENABLED:
        return
    try:
        server = HTTPServer(("0.0.0.0", C.PORT), WebHandler)
        log.info(f"🌐 خادم الويب يعمـل على المنفذ: {C.PORT}")
        server.serve_forever()
    except Exception as e:
        log.error(f"❌ فشل تشغيل خادم الويب: {e}")


# ══════════════════════════════════════════════════════
#                 🛡 إدارة إشارات الإغلاق الآمن
# ══════════════════════════════════════════════════════
def graceful_shutdown(signum, frame):
    log.info("⚠️ جاري إغلاق البوت بآمان وحفظ البيانات…")
    try:
        bot.stop_polling()
    except Exception as e:
        log.debug(f"stop polling: {e}")
    try:
        flush_all()
        log.info("💾 تم حفظ كافة البيانات بنجاح.")
    except Exception as e:
        log.error(f"error flushing on exit: {e}")
    sys.exit(0)


signal.signal(signal.SIGINT, graceful_shutdown)
signal.signal(signal.SIGTERM, graceful_shutdown)


# ══════════════════════════════════════════════════════
#                 🚀 الدالة الرئيسية
# ══════════════════════════════════════════════════════
def main():
    try:
        me = bot.get_me()
        ME["username"] = me.username
        log.info(f"✅ تم الاتصال بنجاح! البوت: @{me.username} [{me.id}]")
    except Exception as e:
        log.error(f"❌ فشل الاتصال بتلغرام: {e}")
        sys.exit(1)

    # تشغيل المهام الجانبية في الخلفية
    threading.Thread(target=janitor, daemon=True, name="Janitor").start()
    threading.Thread(target=keep_alive, daemon=True, name="KeepAlive").start()
    threading.Thread(target=start_web_server, daemon=True, name="WebServer").start()

    log.info("🤖 البوت يعمل الآن ويستقبل الرسائل…")

    # الحلقة الرئيسية مع الاستعادة التلقائية عند انهيار الاتصال
    while True:
        try:
            bot.polling(non_stop=True, timeout=30, long_polling_timeout=20)
        except Exception as e:
            HEALTH["restarts"] += 1
            log.error(f"⚠️ خطأ في الاستعلام (Polling): {e} — إعادة الاتصال خلال 5 ثوانٍ…")
            time.sleep(5)


if __name__ == "__main__":
    main()
