import os
import sqlite3
import asyncio
import aiohttp
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import Message
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.Models.get("models/gemini-2.5-flash")

app = Client("ai_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

BAD_WORDS = ["jinsi","jinsiy","seks","sex","porn","xxx","qiziqaman","yotsex","18+","fuck","shit","anal","fuck you","xxxxxxx","hentai","zo'rlash","rape"]

def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        image_limit INTEGER DEFAULT 3,
        chat_limit INTEGER DEFAULT 100,
        premium INTEGER DEFAULT 0,
        premium_until TEXT,
        last_reset TEXT,
        join_date TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS channels (
        channel_id TEXT PRIMARY KEY,
        channel_username TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

def get_user(user_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def add_user(user_id, username):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("INSERT OR IGNORE INTO users VALUES (?,?,3,100,0,NULL,?,?)", (user_id, username, now, now))
    conn.commit()
    conn.close()

def update_limits(user_id, image_limit=None, chat_limit=None):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if image_limit is not None:
        c.execute("UPDATE users SET image_limit=? WHERE user_id=?", (image_limit, user_id))
    if chat_limit is not None:
        c.execute("UPDATE users SET chat_limit=? WHERE user_id=?", (chat_limit, user_id))
    conn.commit()
    conn.close()

def reset_daily_limits(user_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("UPDATE users SET image_limit=3, chat_limit=100, last_reset=? WHERE user_id=? AND premium=0", (now, user_id))
    conn.commit()
    conn.close()

def check_and_reset_limits(user_id):
    user = get_user(user_id)
    if user:
        last_reset = datetime.fromisoformat(user[6])
        if datetime.now() - last_reset > timedelta(days=1):
            reset_daily_limits(user_id)

def set_premium(user_id, days=30):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    until = (datetime.now() + timedelta(days=days)).isoformat()
    c.execute("UPDATE users SET premium=1, premium_until=? WHERE user_id=?", (until, user_id))
    conn.commit()
    conn.close()

def check_premium(user_id):
    user = get_user(user_id)
    if user and user[4] == 1:
        if user[5] and datetime.now() < datetime.fromisoformat(user[5]):
            return True
        else:
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute("UPDATE users SET premium=0 WHERE user_id=?", (user_id,))
            conn.commit()
            conn.close()
    return False

def contains_bad_words(text):
    text_lower = text.lower()
    for word in BAD_WORDS:
        if word in text_lower:
            return True
    return False

async def generate_image_pollinations(prompt):
    try:
        safe_prompt = prompt.replace(" ", "%20")
        image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true"
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                if response.status == 200:
                    return image_url
        return None
    except:
        return None

@app.on_message(filters.text & filters.private)
async def handle_messages(client, message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Foydalanuvchi"
    add_user(user_id, username)
    if contains_bad_words(message.text):
        await message.reply_text("⚠️ Taqiqlangan so'zdan foydalanmang!")
        return

    check_and_reset_limits(user_id)
    user = get_user(user_id)
    is_premium = check_premium(user_id)

    if any(word in message.text.lower() for word in ["rasm","chiz","draw","paint"]):
        if not is_premium and user[2] <= 0:
            await message.reply_text("⚠️ Kunlik rasm limitingiz tugadi!")
            return
        wait_msg = await message.reply_text("🎨 Rasm yaratilmoqda, kuting...")
        try:
            image_url = await generate_image_pollinations(message.text)
            if image_url:
                await message.reply_photo(photo=image_url, caption=f"🎨 Tavsif: {message.text}")
                if not is_premium:
                    update_limits(user_id, image_limit=user[2]-1)
                    await message.reply_text(f"✅ Qolgan rasm limiti: {user[2]-1}")
            else:
                await message.reply_text("❌ Rasm yaratishda xatolik yuz berdi.")
            await wait_msg.delete()
        except:
            await wait_msg.delete()
            await message.reply_text("❌ Xatolik yuz berdi.")
        return

    if not is_premium and user[3] <= 0:
        await message.reply_text("⚠️ Kunlik chat limitingiz tugadi! 💎 Premium oling.")
        return

    try:
        response = await asyncio.to_thread(model.generate_content, message.text)
        if hasattr(response, "candidates") and len(response.candidates) > 0:
            text = response.candidates[0].output_text
        else:
            text = str(response)
        await message.reply_text(f"🤖 {text}")
        if not is_premium:
            update_limits(user_id, chat_limit=user[3]-1)
    except Exception as e:
        await message.reply_text("❌ Xatolik yuz berdi.")

app.run()
