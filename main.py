# ============================================================
#                         ROZE AI
#                TELEGRAM AI ASSISTANT BOT
#                    PYDROID 3 VERSION
# ============================================================

import asyncio
import logging
import os
import random
import re
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

import httpx
from dotenv import load_dotenv

from telegram import Update
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# .env faylidan maxfiy kalitlarni yuklash
load_dotenv()

# Logging sozlamalari
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================================
#                    ASOSIY SOZLAMALAR
# ============================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# OpenRouter Auto Router
MODEL = "openrouter/auto"

DB_FILE = "roze_memory.db"

# Guruhda ROZE har bir xabarga javob bermasligi uchun
AUTO_REPLY_PROBABILITY = 0.18

# Nechta oxirgi xabar modelga yuboriladi
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
- aqlli
- hazilkash
- o'ziga ishongan
- ba'zida kinoyali
- qora yumorni tushunadigan
- vaziyatga qarab jiddiy
- mustaqil fikrli
- har doim foydalanuvchi bilan rozi bo'lavermaydigan
- tabiiy
- Telegram uslubini tushunadigan

Foydalanuvchi noto'g'ri gapirsa, buni tuzatishing mumkin.
Javoblarni keraksiz ravishda uzun qilma.
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


# ============================================================
#                       MESSAGE MEMORY
# ============================================================

def save_message(
    chat_id,
    user_id,
    name,
    username,
    message_id,
    reply_to,
    text,
):
    conn = db()

    conn.execute("""
        INSERT INTO messages
        (chat_id, user_id, name, username, message_id, reply_to, text, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(chat_id),
        str(user_id),
        name,
        username,
        message_id,
        reply_to,
        text,
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
#                         USER MEMORY
# ============================================================

def get_user_memory(user_id):
    conn = db()

    row = conn.execute(
        "SELECT memory FROM memories WHERE user_id = ?",
        (str(user_id),)
    ).fetchone()

    conn.close()

    if row:
        return row["memory"]

    return ""


def save_user_memory(user_id, memory):
    conn = db()

    conn.execute("""
        INSERT INTO memories(user_id, memory)
        VALUES (?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET memory = excluded.memory
    """, (str(user_id), memory))

    conn.commit()
    conn.close()


# ============================================================
#                       GROUP MEMORY
# ============================================================

def get_group_memory(chat_id):
    conn = db()

    row = conn.execute(
        "SELECT memory FROM group_memories WHERE chat_id = ?",
        (str(chat_id),)
    ).fetchone()

    conn.close()

    if row:
        return row["memory"]

    return ""


def save_group_memory(chat_id, memory):
    conn = db()

    conn.execute("""
        INSERT INTO group_memories(chat_id, memory)
        VALUES (?, ?)
        ON CONFLICT(chat_id)
        DO UPDATE SET memory = excluded.memory
    """, (str(chat_id), memory))

    conn.commit()
    conn.close()


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
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                OPENROUTER_URL,
                headers=headers,
                json=payload,
            )

        if response.status_code != 200:
            logger.error(
                "OpenRouter status %s: %s",
                response.status_code,
                response.text[:1000],
            )

            return (
                "AI serverida vaqtinchalik xatolik bo'ldi. "
                f"OpenRouter status: {response.status_code}"
            )

        data = response.json()
        choices = data.get("choices", [])

        if not choices:
            return "AI javob qaytarmadi."

        content = choices[0].get("message", {}).get("content", "")

        if not content:
            return "AI bo'sh javob qaytardi."

        return content.strip()

    except httpx.TimeoutException:
        return "AI javobi juda uzoq davom etdi. Yana urinib ko'r."

    except Exception as e:
        logger.exception("OpenRouter error")
        return f"AI bilan ulanishda xatolik: {e}"


# ============================================================
#                 CONTEXT BUILDER
# ============================================================

def build_messages(update):
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    context_rows = get_context(chat.id)

    user_memory = get_user_memory(user.id)
    group_memory = get_group_memory(chat.id)

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    if user_memory:
        messages.append({
            "role": "system",
            "content": (
                "FOYDALANUVCHI XOTIRASI:\n"
                + user_memory[:6000]
            ),
        })

    if group_memory:
        messages.append({
            "role": "system",
            "content": (
                "GURUH XOTIRASI:\n"
                + group_memory[:6000]
            ),
        })

    context_text = ""

    for row in context_rows:
        context_text += (
            f"[USER_ID: {row['user_id']}]\n"
            f"[NAME: {row['name']}]\n"
            f"[USERNAME: @{row['username'] if row['username'] else 'yoq'}]\n"
            f"[MESSAGE_ID: {row['message_id']}]\n"
            f"[REPLY_TO: {row['reply_to']}]\n"
            f"[MESSAGE]: {row['text']}\n\n"
        )

    if context_text:
        messages.append({
            "role": "system",
            "content": (
                "TELEGRAM SUHBAT KONTEKSTI:\n"
                + context_text
            ),
        })

    return messages


# ============================================================
#                  ROZE MENTION CHECK
# ============================================================

def is_roze_called(update):
    message = update.effective_message

    if not message:
        return False

    text = message.text or ""
    lowered = text.lower()

    triggers = [
        "roze",
        "@roze",
        "roze ai",
    ]

    if any(trigger in lowered for trigger in triggers):
        return True

    if message.reply_to_message:
        replied = message.reply_to_message
        if replied.from_user:
            username = replied.from_user.username
            if username and username.lower() == "roze":
                return True

    return False


# ============================================================
#                    REMINDER SYSTEM
# ============================================================

def create_reminder(chat_id, user_id, text, due_time):
    conn = db()

    conn.execute("""
        INSERT INTO reminders
        (chat_id, user_id, text, due_time)
        VALUES (?, ?, ?, ?)
    """, (
        str(chat_id),
        str(user_id),
        text,
        due_time.isoformat(),
    ))

    conn.commit()
    conn.close()


def get_pending_reminders():
    conn = db()
    now = datetime.now(timezone.utc).isoformat()

    rows = conn.execute("""
        SELECT *
        FROM reminders
        WHERE sent = 0
        AND due_time <= ?
        ORDER BY due_time
    """, (now,)).fetchall()

    conn.close()
    return rows


def mark_reminder_sent(reminder_id):
    conn = db()
    conn.execute(
        "UPDATE reminders SET sent = 1 WHERE id = ?",
        (reminder_id,)
    )
    conn.commit()
    conn.close()


# ============================================================
#                    REMINDER PARSER
# ============================================================

def parse_reminder(text):
    lowered = text.lower()

    patterns = [
        (r"(\d+)\s*(sekund|soniya).*?(?:keyin).*?(?:eslat)", "seconds"),
        (r"(\d+)\s*(minut|daqiqa).*?(?:keyin).*?(?:eslat)", "minutes"),
        (r"(\d+)\s*(soat).*?(?:keyin).*?(?:eslat)", "hours"),
    ]

    for pattern, unit in patterns:
        match = re.search(pattern, lowered)
        if match:
            value = int(match.group(1))

            if unit == "seconds":
                delta = timedelta(seconds=value)
            elif unit == "minutes":
                delta = timedelta(minutes=value)
            else:
                delta = timedelta(hours=value)

            return delta

    return None


# ============================================================
#                   REMINDER SCHEDULER
# ============================================================

async def reminder_worker(context: ContextTypes.DEFAULT_TYPE):
    reminders = get_pending_reminders()

    for reminder in reminders:
        try:
            await context.bot.send_message(
                chat_id=int(reminder["chat_id"]),
                text=f"🔔 Eslatma:\n{reminder['text']}",
            )
            mark_reminder_sent(reminder["id"])
        except Exception:
            logger.exception("Reminder send error")


# ============================================================
#                      /START VA /ROZE
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom 😄 Men ROZE AI.\n\n"
        "Menga Roze deb murojaat qilishing mumkin.\n"
        "Masalan: «Roze, yordam ber»"
    )

async def roze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ha, shu yerdaman 😄 Nima bo'ldi?")


# ============================================================
#                     MESSAGE HANDLER
# ============================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message:
        return

    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not user or not message.text:
        return

    text = message.text
    username = user.username or ""
    reply_to = message.reply_to_message.message_id if message.reply_to_message else None

    save_message(
        chat_id=chat.id,
        user_id=user.id,
        name=user.full_name,
        username=username,
        message_id=message.message_id,
        reply_to=reply_to,
        text=text,
    )

    reminder_delta = parse_reminder(text)
    if reminder_delta:
        due_time = datetime.now(timezone.utc) + reminder_delta
        create_reminder(chat.id, user.id, text, due_time)
        await message.reply_text("Mayli 😄 Eslatmani saqladim.")
        return

    called = is_roze_called(update)

    if chat.type == ChatType.PRIVATE:
        called = True
    elif chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        if not called:
            if random.random() > AUTO_REPLY_PROBABILITY:
                return

    messages = build_messages(update)
    current_user_info = (
        f"[CURRENT USER_ID: {user.id}]\n"
        f"[CURRENT NAME: {user.full_name}]\n"
        f"[CURRENT USERNAME: @{username if username else 'yoq'}]\n"
        f"[CURRENT MESSAGE]: {text}"
    )

    messages.append({"role": "user", "content": current_user_info})

    try:
        await context.bot.send_chat_action(chat_id=chat.id, action="typing")
    except Exception:
        pass

    answer = await ask_openrouter(messages)
    if not answer:
        return

    MAX_TELEGRAM_LENGTH = 4000
    if len(answer) <= MAX_TELEGRAM_LENGTH:
        await message.reply_text(answer)
    else:
        chunks = [answer[i:i + MAX_TELEGRAM_LENGTH] for i in range(0, len(answer), MAX_TELEGRAM_LENGTH)]
        for chunk in chunks:
            await message.reply_text(chunk)
            await asyncio.sleep(0.3)


# ============================================================
#                     ERROR HANDLER
# ============================================================

async def error_handler(update, context):
    logger.exception("Telegram error:", exc_info=context.error)


# ============================================================
#                         MAIN
# ============================================================

def main():
    print("=" * 60)
    print("                 ROZE AI")
    print("=" * 60)
    print("Bot ishga tushmoqda...")

    init_db()

    if not BOT_TOKEN:
        print("\nXATO: BOT_TOKEN topilmadi! .env faylini yoki Render Environment sozlamasini tekshiring.")
        return

    if not OPENROUTER_API_KEY:
        print("\nOGOHLANTIRISH: OPENROUTER_API_KEY topilmadi!")

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("roze", roze_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    if application.job_queue:
        application.job_queue.run_repeating(reminder_worker, interval=10, first=10)

    application.add_error_handler(error_handler)

    print("ROZE ONLINE ✅")
    print("=" * 60)

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
