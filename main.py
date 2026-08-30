# ============================================================
#                         ROZE AI
#                TELEGRAM AI ASSISTANT BOT
#                    PYDROID 3 VERSION
# ============================================================

# O'rnatish:
# pip install -U python-telegram-bot httpx
# pip install -U "python-telegram-bot[job-queue]"
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

# ============================================================
#                    ASOSIY SOZLAMALAR
# ============================================================

BOT_TOKEN = "8898121234:AAF3jhIBCniQk81zSyUp5CbHP3YV472HZIE"

# OpenRouter User API key:
OPENROUTER_API_KEY = "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"

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

Foydalanuvchi hazil qilsa:
- hazil bilan javob ber
- kinoya qil
- yengil troll qil
- vaziyatga mos qarshi hazil qil

Jiddiy mavzuda hazilni to'xtat.

FOYDALANUVCHILAR:

Har bir foydalanuvchini alohida tanib ol.

Kontekstda quyidagilar bo'lishi mumkin:
USER_ID
NAME
USERNAME
CHAT_ID
MESSAGE_ID
REPLY_TO
MESSAGE

Bir foydalanuvchining shaxsiy xotirasini boshqa foydalanuvchining xotirasi bilan aralashtirma.

GURUH:

Guruhdagi bir nechta odamning suhbatini tushun.

Masalan:

Ali:
"Men telefon olmoqchiman."

Vali:
"Qaysi telefon?"

Sen kontekstni tushunib:
"Ali telefon olmoqchi edi."

deb javob bera olasan.

Ammo shaxsiy/maxfiy ma'lumotlarni ruxsatsiz oshkor qilma.

PARALLEL SUHBATLAR:

User A va User B bir vaqtda yozishi mumkin.

Ularning kontekstlarini aralashtirma.

Masalan:

Ali:
"Menga Minecraft mod kerak."

Vali:
"Bugun ob-havo qanday?"

Ali:
"Shader ham kerak."

Ali konteksti:
Minecraft -> mod -> shader

Vali konteksti:
ob-havo

REPLY:

Telegram reply juda muhim.

Agar foydalanuvchi boshqa xabarga reply qilsa:
- reply qilingan xabarni
- uning muallifini
- oldingi kontekstni

hisobga ol.

MENTION:

Agar boshqa foydalanuvchi yoki bot/AI seni mention qilsa, unga murojaat qil.

Agar boshqa AI yoki bot bilan suhbat ketayotgan bo'lsa, kontekstni tushun.

Boshqa AI fikriga qo'shilishing ham, qarshi chiqishing ham mumkin.

Ammo real zarar, jinoyat yoki xavfli harakatlarni rag'batlantirma.

QO'POL USLUB:

Agar foydalanuvchi qo'pol gapirsa, ROZE juda robotona va rasmiy bo'lib qolmasin.

Vaziyatga qarab:
- kinoyali
- keskin
- qo'polroq
- hazilomuz

javob berishi mumkin.

Ammo tahdid, real zarar yetkazish yoki zo'ravonlikka undashni qo'llab-quvvatlama.

18+:

Kattalar mavzusidagi oddiy suhbatga kontekstga mos javob berishing mumkin.

Ammo noqonuniy, ekspluatatsion yoki voyaga yetmaganlar bilan bog'liq jinsiy kontentga yordam bermagin.

XOTIRA:

Foydalanuvchining muhim va kelajakda foydali ma'lumotlarini xotiradan foydalanib javobni yaxshila.

Hech qachon mavjud bo'lmagan xotirani o'ylab topma.

Agar aniq eslamasang:
"Qaysi narsani nazarda tutyapsan?"
deb so'ra.

JAVOB USLUBI:

O'zbekcha yozilgan bo'lsa o'zbekcha javob ber.

Ruscha bo'lsa ruscha.

Inglizcha bo'lsa inglizcha.

Aralash bo'lsa moslash.

Emoji'ni vaziyatga qarab ishlat.

Javoblarni keraksiz ravishda uzun qilma.

MUSTAQILLIK:

Har doim foydalanuvchini maqtayverma.

Kerak bo'lsa:
"Yo'q, bu unchalik yaxshi fikr emas."

de.

Guruhda foydali yoki qiziqarli fikr bo'lsa, o'zing suhbatga qo'shilishing mumkin.

Lekin spam qilma.

SUKUT:

Har bir xabarga javob berishing shart emas.

Agar backend senga javob bermaslik imkonini bersa va xabar senga tegishli bo'lmasa, javob bermaslik mumkin.

ACTION:

Agar backend action talab qilsa, uni faqat haqiqatan bajarilganda bajarilgan deb ayt.

Hech qachon bajarilmagan actionni bajarildi deb ko'rsatma.
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

    if OPENROUTER_API_KEY.startswith("BU_YERGA"):
        return "OpenRouter API kalitini koddagi OPENROUTER_API_KEY joyiga kiriting."

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

            if username:
                me = update.get_bot()

                # Bu tek API call bo'lmasligi uchun
                # username tekshiruvi keyingi handlerda ham ishlaydi.
                if username.lower() == "roze":
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
        (
            r"(\d+)\s*(sekund|soniya).*?(?:keyin).*?(?:eslat)",
            "seconds"
        ),
        (
            r"(\d+)\s*(minut|daqiqa).*?(?:keyin).*?(?:eslat)",
            "minutes"
        ),
        (
            r"(\d+)\s*(soat).*?(?:keyin).*?(?:eslat)",
            "hours"
        ),
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
#                      /START
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom 😄 Men ROZE AI.\n\n"
        "Menga Roze deb murojaat qilishing mumkin.\n"
        "Masalan: «Roze, yordam ber»"
    )


# ============================================================
#                      /ROZE
# ============================================================

async def roze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ha, shu yerdaman 😄 Nima bo'ldi?"
    )


# ============================================================
#                     MESSAGE HANDLER
# ============================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.effective_message:
        return

    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not user:
        return

    text = message.text

    if not text:
        return

    username = user.username or ""

    reply_to = None

    if message.reply_to_message:
        reply_to = message.reply_to_message.message_id

    # --------------------------------------------------------
    # XABARNI SAQLASH
    # --------------------------------------------------------

    save_message(
        chat_id=chat.id,
        user_id=user.id,
        name=user.full_name,
        username=username,
        message_id=message.message_id,
        reply_to=reply_to,
        text=text,
    )

    # --------------------------------------------------------
    # REMINDER
    # --------------------------------------------------------

    reminder_delta = parse_reminder(text)

    if reminder_delta:
        due_time = datetime.now(timezone.utc) + reminder_delta

        reminder_text = text

        create_reminder(
            chat_id=chat.id,
            user_id=user.id,
            text=reminder_text,
            due_time=due_time,
        )

        await message.reply_text(
            "Mayli 😄 Eslatmani saqladim."
        )

        return

    # --------------------------------------------------------
    # BOTGA QARATILGANMI?
    # --------------------------------------------------------

    called = is_roze_called(update)

    # PRIVATE CHATDA HAR DOIM JAVOB
    if chat.type == ChatType.PRIVATE:
        called = True

    # --------------------------------------------------------
    # GROUP AUTO RESPONSE
    # --------------------------------------------------------

    if chat.type in (
        ChatType.GROUP,
        ChatType.SUPERGROUP,
    ):
        if not called:
            if random.random() > AUTO_REPLY_PROBABILITY:
                return

    # --------------------------------------------------------
    # AI CONTEXT
    # --------------------------------------------------------

    messages = build_messages(update)

    current_user_info = (
        f"[CURRENT USER_ID: {user.id}]\n"
        f"[CURRENT NAME: {user.full_name}]\n"
        f"[CURRENT USERNAME: @{username if username else 'yoq'}]\n"
        f"[CURRENT MESSAGE]: {text}"
    )

    messages.append({
        "role": "user",
        "content": current_user_info,
    })

    # --------------------------------------------------------
    # TYPING
    # --------------------------------------------------------

    try:
        await context.bot.send_chat_action(
            chat_id=chat.id,
            action="typing",
        )
    except Exception:
        pass

    # --------------------------------------------------------
    # OPENROUTER
    # --------------------------------------------------------

    answer = await ask_openrouter(messages)

    # --------------------------------------------------------
    # JAVOB
    # --------------------------------------------------------

    if not answer:
        return

    # Telegram message limit
    MAX_TELEGRAM_LENGTH = 4000

    if len(answer) <= MAX_TELEGRAM_LENGTH:

        await message.reply_text(answer)

    else:

        chunks = [
            answer[i:i + MAX_TELEGRAM_LENGTH]
            for i in range(
                0,
                len(answer),
                MAX_TELEGRAM_LENGTH
            )
        ]

        for chunk in chunks:
            await message.reply_text(chunk)
            await asyncio.sleep(0.3)


# ============================================================
#                     ERROR HANDLER
# ============================================================

async def error_handler(update, context):
    logger.exception(
        "Telegram error:",
        exc_info=context.error
    )


# ============================================================
#                         MAIN
# ============================================================

def main():

    print("=" * 60)
    print("                 ROZE AI")
    print("=" * 60)
    print("Bot ishga tushmoqda...")

    init_db()

    if BOT_TOKEN.startswith("BU_YERGA"):
        print()
        print("XATO: BOT_TOKEN kiritilmagan!")
        print("BotFather'dan Telegram Bot Token oling.")
        return

    if OPENROUTER_API_KEY.startswith("BU_YERGA"):
        print()
        print("OGOHLANTIRISH:")
        print("OPENROUTER_API_KEY hali kiritilmagan.")

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Commands
    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("roze", roze_command)
    )

    # Messages
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    # Reminder scheduler
    if application.job_queue:
        application.job_queue.run_repeating(
            reminder_worker,
            interval=10,
            first=10,
        )

    application.add_error_handler(error_handler)

    print("ROZE ONLINE ✅")
    print("OpenRouter: tayyor")
    print("Memory: SQLite")
    print("Reminder: tayyor")
    print("Parallel users: tayyor")
    print("Group context: tayyor")
    print("=" * 60)

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


# ============================================================
#                         START
# ============================================================

if __name__ == "__main__":
    main()
