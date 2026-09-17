import os
import telebot
from flask import Flask
from threading import Thread
from handlers import register_handlers
from config import BOT_TOKEN

app = Flask(__name__)

@app.route('/')
def home():
    return "♟ Chess Bot is Running 24/7 Safely!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False)

Thread(target=run_web, daemon=True).start()

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")
register_handlers(bot)

if __name__ == "__main__":
    print("♟ Bot is starting...")
    bot.infinity_polling(skip_pending=True, timeout=60)
