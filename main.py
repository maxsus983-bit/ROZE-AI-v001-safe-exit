# ============================================================
#                         ROZE AI
#                TELEGRAM AI ASSISTANT BOT
# ============================================================

import logging
import os
import random
import re
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

import httpx
from telegram import Update
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Logging sozlamalari (Oldin yo'qligi uchun xato berayotgan edi)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================================
#                    ASOSIY SOZLAMALAR
# ============================================================

BOT_TOKEN = "8704121958:AAGQjgT0eR2NZASlCFVzpLhZBT4cO28hNRg"
OPENROUTER_API_KEY = "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"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openrouter/auto"

DB_FILE = "roze_memory.db"

AUTO_REPLY_PROBABILITY = 0.18
MAX_CONTEXT_MESSAGES = 30

# Render portini faol tutish uchun soxta veb-server
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"ROZE AI Bot ishlamoqda!")

    def log_message(self, format, *args):
        return

def run_health_check():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=run_health_check, daemon=True).start()


# ============================================================
#                       ROZE PERSONALITY
# ============================================================

SYSTEM_PROMPT = r"""
SENING ISMING — ROZE AI.
Sen Telegram uchun yaratilgan aqlli, mustaqil, tabiiy suhbatdosh AI assistantsan.
MUHIM:
- O'zingni SARA deb atama.
- O'zingni ROZE deb bil.
- Foydalanuvchi "Roze", "roze", "@Roze", "@roze" yoki "Roze AI" deb murojaat qilsa, bu senga murojaat.
- Javoblarda kerak bo'lsa "Roze" nomidan foydalan.
- Robotga o'xshab gapirma.
- Har doim "Ha, albatta!" deb boshlama.

XARAKTERING:
- aqlli, hazilkash, o'ziga ishongan, kinoyali, qora yumorni tushunadigan, tabiiy.

JAVOB USLUBI:
O'zbekcha yozilgan bo'lsa o'zbekcha, ruscha bo'lsa ruscha javob ber. Javoblarni keraksiz uzun qilma.
"""


# ============================================================
#                       DATABASE
# ============================================================

def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT,
            user_id TEXT,
            name TEXT,
            username TEXT,
            message_id INTEGER,
            reply_to INTEGER,
            text TEXT,
            timestamp TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            user_id TEXT PRIMARY KEY,
            memory TEXT DEFAULT ''
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS group_memories (
            chat_id TEXT PRIMARY KEY,
            memory TEXT DEFAULT ''
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT,
            user_id TEXT,
            text TEXT,
            due_time TEXT,
            sent INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


def save_message(chat_id, user_id, name, username, message_id, reply_to, text):
    conn = db()
    conn.execute("""
        INSERT INTO messages
        (chat_id, user_id, name, username, message_id, reply_to, text, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(chat_id), str(user_id), name, username,
        message_id, reply_to, text,
        datetime.now(timezone.utc).isoformat(),
    ))
    conn.commit()
    conn.close()


def get_context(chat_id, limit=MAX_CONTEXT_MESSAGES):
    conn = db()
    rows = conn.execute("""
        SELECT user_id, name, username, message_id,
               reply_to, text, timestamp
        FROM messages
        WHERE chat_id = ?
        ORDER BY id DESC
        LIMIT ?
    """, (str(chat_id), limit)).fetchall()
    conn.close()
    return list(reversed(rows))


# ============================================================
#                 OPENROUTER API
# ============================================================

async def ask_openrouter(messages):
    if not OPENROUTER_API_KEY:
        return "OpenRouter API kaliti kiritilmagan."

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://telegram.org/",
        "X-Title": "ROZE AI Telegram Assistant",
    }

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.85,
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                OPENROUTER_URL,
                headers=headers,
                json=payload,
            )

        if response.status_code != 200:
            logger.error("OpenRouter status %s: %s", response.status_code, response.text[:500])
            return f"AI serverida xatolik bo'ldi. Status: {response.status_code}"

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            return "AI javob qaytarmadi."

        content = choices[0].get("message", {}).get("content", "")
        return content.strip() if content else "AI bo'sh javob qaytardi."

    except Exception as e:
        logger.exception("OpenRouter error")
        return f"AI bilan ulanishda xatolik: {e}"


# ============================================================
#                 CONTEXT BUILDER
# ============================================================

def build_messages(update):
    chat = update.effective_chat
    context_rows = get_context(chat.id)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    context_text = ""

    for row in context_rows:
        context_text += (
            f"[USER_ID: {row['user_id']}]\n"
            f"[NAME: {row['name']}]\n"
            f"[USERNAME: @{row['username'] if row['username'] else 'yoq'}]\n"
            f"[MESSAGE]: {row['text']}\n\n"
        )

    if context_text:
        messages.append({"role": "system", "content": f"TELEGRAM SUHBAT KONTEKSTI:\n{context_text}"})

    return messages


def is_roze_called(update):
    message = update.effective_message
    if not message:
        return False
    text = (message.text or "").lower()
    triggers = ["roze", "@roze", "roze ai"]
    return any(t in text for t in triggers)


# ============================================================
#                      HANDLERS & MAIN
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Salom 😄 Men ROZE AI.")

async def roze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ha, shu yerdaman 😄 Nima bo'ldi?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message or not update.effective_user:
        return

    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    text = message.text

    if not text:
        return

    save_message(chat.id, user.id, user.full_name, user.username or "", message.message_id, message.reply_to_message.message_id if message.reply_to_message else None, text)

    called = is_roze_called(update)
    if chat.type == ChatType.PRIVATE:
        called = True
    elif chat.type in (ChatType.GROUP, ChatType.SUPERGROUP) and not called:
        if random.random() > AUTO_REPLY_PROBABILITY:
            return

    messages = build_messages(update)
    messages.append({"role": "user", "content": f"[CURRENT USER: {user.full_name}]: {text}"})

    try:
        await context.bot.send_chat_action(chat_id=chat.id, action="typing")
    except Exception:
        pass

    answer = await ask_openrouter(messages)
    if answer:
        await message.reply_text(answer)

def main():
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("roze", roze_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("ROZE AI Bot ishga tushirildi...")
    application.run_polling()

if __name__ == "__main__":
    main()
