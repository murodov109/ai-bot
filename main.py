import os
import sqlite3
import asyncio
import aiohttp
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("models/gemini-2.5-flash")

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

def get_channels():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM channels")
    channels = c.fetchall()
    conn.close()
    return channels

def add_channel(channel_id, channel_username):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO channels VALUES (?,?)", (channel_id, channel_username))
    conn.commit()
    conn.close()

def remove_channel(channel_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("DELETE FROM channels WHERE channel_id=?", (channel_id,))
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE premium=1")
    premium_users = c.fetchone()[0]
    conn.close()
    return total_users, premium_users

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

user_states = {}

@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Foydalanuvchi"
    add_user(user_id, username)
    if user_id == ADMIN_ID:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
            [InlineKeyboardButton("➕ Kanal qo'shish", callback_data="add_channel"),
             InlineKeyboardButton("➖ Kanal o'chirish", callback_data="remove_channel")],
            [InlineKeyboardButton("💎 Premium berish", callback_data="give_premium")],
            [InlineKeyboardButton("📢 Reklama yuborish", callback_data="send_ad")]
        ])
        await message.reply_text("👨‍💼 Admin panelga xush kelibsiz!", reply_markup=keyboard)
    else:
        await message.reply_text(f"👋 Salom {username}!\nMatn yozing, rasm yaratish uchun 'rasm' so'zi bilan yuboring.")

@app.on_callback_query()
async def admin_callbacks(client, callback_query):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ Siz admin emassiz!", show_alert=True)
        return
    data = callback_query.data
    if data == "admin_stats":
        total, premium = get_stats()
        await callback_query.answer(f"👥 Jami: {total}, 💎 Premium: {premium}", show_alert=True)
    elif data == "add_channel":
        user_states[ADMIN_ID] = "waiting_channel_add"
        await callback_query.message.edit_text("➕ Kanal qo'shish: ID yoki @username yuboring")
    elif data == "remove_channel":
        channels = get_channels()
        if not channels:
            await callback_query.answer("❌ Kanallar yo'q!", show_alert=True)
            return
        user_states[ADMIN_ID] = "waiting_channel_remove"
        text = "➖ Kanal o'chirish:\n"
        for ch in channels:
            text += f"📢 {ch[1]} - ID: {ch[0]}\n"
        await callback_query.message.edit_text(text)
    elif data == "give_premium":
        user_states[ADMIN_ID] = "waiting_premium_user"
        await callback_query.message.edit_text("💎 Premium berish uchun foydalanuvchi ID yuboring")
    elif data == "send_ad":
        user_states[ADMIN_ID] = "waiting_ad_message"
        await callback_query.message.edit_text("📢 Reklama yuborish uchun xabar yuboring")

@app.on_message(filters.text & filters.private)
async def handle_messages(client, message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Foydalanuvchi"
    add_user(user_id, username)
    if contains_bad_words(message.text):
        await message.reply_text("⚠️ Taqiqlangan so'zdan foydalanmang!")
        return

    if user_id == ADMIN_ID:
        state = user_states.get(ADMIN_ID)
        if state == "waiting_channel_add":
            try:
                chat = await client.get_chat(message.text.strip())
                add_channel(str(chat.id), message.text.strip())
                await message.reply_text(f"✅ Kanal qo'shildi: {message.text.strip()}")
            except Exception as e:
                await message.reply_text(f"❌ Xatolik: {e}")
            user_states.pop(ADMIN_ID, None)
            return
        elif state == "waiting_channel_remove":
            try:
                remove_channel(message.text.strip())
                await message.reply_text("✅ Kanal o'chirildi!")
            except:
                await message.reply_text("❌ Xatolik yuz berdi!")
            user_states.pop(ADMIN_ID, None)
            return
        elif state == "waiting_premium_user":
            try:
                target_user_id = int(message.text.strip())
                set_premium(target_user_id, 30)
                await message.reply_text(f"✅ User {target_user_id} ga 30 kunlik Premium berildi!")
            except:
                await message.reply_text("❌ Noto'g'ri ID!")
            user_states.pop(ADMIN_ID, None)
            return
        elif state == "waiting_ad_message":
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute("SELECT user_id FROM users")
            users = c.fetchall()
            conn.close()
            success = 0
            for u in users:
                try:
                    await client.send_message(u[0], message.text)
                    success += 1
                    await asyncio.sleep(0.05)
                except:
                    pass
            await message.reply_text(f"✅ Reklama {success} ta foydalanuvchiga yuborildi!")
            user_states.pop(ADMIN_ID, None)
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
        except Exception as e:
            await wait_msg.delete()
            await message.reply_text(f"❌ Xatolik yuz berdi: {e}")
        return

    if not is_premium and user[3] <= 0:
        await message.reply_text("⚠️ Kunlik chat limitingiz tugadi! 💎 Premium oling.")
        return

    try:
        response = await asyncio.to_thread(model.generate_content, message.text)
        if hasattr(response, "candidates") and len(response.candidates) > 0:
            text = response.candidates[0].content.text
        else:
            text = str(response)
        await message.reply_text(f"🤖 {text}")
        if not is_premium:
            update_limits(user_id, chat_limit=user[3]-1)
    except Exception as e:
        print("Chat AI xatolik:", e)
        await message.reply_text(f"❌ Xatolik yuz berdi: {e}")

print("✅ Bot ishga tushdi!")
app.run()
