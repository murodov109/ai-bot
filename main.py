import os
import sqlite3
import requests
import io
import threading
import time
import asyncio
from datetime import datetime, timedelta
from urllib.parse import quote_plus
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID") or 0)
except:
    ADMIN_ID = 0
IMAGE_DAILY_LIMIT = int(os.getenv("IMAGE_DAILY_LIMIT", "3"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
AI_IMAGE_API = os.getenv("AI_IMAGE_API")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

conn = sqlite3.connect("database.db", check_same_thread=False)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, image_used INTEGER DEFAULT 0, last_date TEXT, is_premium INTEGER DEFAULT 0, premium_expiry TEXT)')
cur.execute('CREATE TABLE IF NOT EXISTS channels (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE)')
cur.execute('CREATE TABLE IF NOT EXISTS stats (day TEXT PRIMARY KEY, images_generated INTEGER DEFAULT 0)')
cur.execute('CREATE TABLE IF NOT EXISTS promo (code TEXT PRIMARY KEY, active INTEGER DEFAULT 1)')
conn.commit()

lock = threading.Lock()

BAD_WORDS = [
"sex","porn","anal","hentai","18+","xxx","nude","erotic","fuck","boobs","dick","pussy","gandon",
"shit","bitch","asshole","slut","whore","cum","milf","incest","pedo","rapist","rape","masturbate",
"terror","bomb","seks","murder","drugs","cocaine","heroin","suicide","selfharm"
]

def is_bad_prompt(text):
    if not text:
        return False
    t = text.lower()
    for w in BAD_WORDS:
        if w in t:
            return True
    return False

def extract_gemini_response_json(j):
    if not isinstance(j, dict):
        return None
    if "candidates" in j and isinstance(j["candidates"], list) and j["candidates"]:
        c = j["candidates"][0]
        if isinstance(c, dict):
            content = c.get("content")
            if isinstance(content, dict):
                parts = content.get("parts")
                if isinstance(parts, list) and parts:
                    p = parts[0]
                    if isinstance(p, str):
                        return p
            if isinstance(content, str):
                return content
    if "output" in j:
        out = j["output"]
        if isinstance(out, dict) and "content" in out:
            cont = out["content"]
            if isinstance(cont, list) and cont:
                first = cont[0]
                if isinstance(first, dict) and "text" in first:
                    return first["text"]
    if "candidates" in j:
        try:
            return j["candidates"][0]["text"]
        except:
            pass
    if "choices" in j:
        try:
            ch = j["choices"][0]
            if isinstance(ch, dict) and "message" in ch and isinstance(ch["message"], dict):
                return ch["message"].get("content")
        except:
            pass
    for v in j.values():
        if isinstance(v, str):
            return v
    return None

def ask_ai_sync(text):
    if not GEMINI_API_KEY:
        return "Xatolik: API kalit topilmadi"
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [
                {"parts": [{"text": text}]}
            ]
        }
        r = requests.post(url, json=payload, timeout=40)
        r.raise_for_status()
        j = r.json()
        resp = extract_gemini_response_json(j)
        if resp:
            return resp
        return "Xatolik"
    except:
        try:
            return "Xatolik"
        except:
            return "Xatolik"

async def ask_ai(text):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, ask_ai_sync, text)

def generate_image_bytes_sync(prompt):
    if not AI_IMAGE_API:
        raise RuntimeError("Image API not configured")
    url = AI_IMAGE_API + quote_plus(prompt)
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.content

async def generate_image_bytes(prompt):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, generate_image_bytes_sync, prompt)

def get_today_str():
    return datetime.utcnow().strftime('%Y-%m-%d')

def ensure_user(user_id):
    with lock:
        cur.execute('SELECT * FROM users WHERE user_id=?',(user_id,))
        row = cur.fetchone()
        if not row:
            cur.execute('INSERT INTO users(user_id,image_used,last_date,is_premium,premium_expiry) VALUES(?,?,?,?,?)',(user_id,0,get_today_str(),0,None))
            conn.commit()
            return {"user_id":user_id,"image_used":0,"last_date":get_today_str(),"is_premium":0,"premium_expiry":None}
        row = dict(row)
        if row.get("last_date") != get_today_str():
            cur.execute('UPDATE users SET image_used=0,last_date=? WHERE user_id=?',(get_today_str(),user_id))
            conn.commit()
            row["image_used"] = 0
            row["last_date"] = get_today_str()
        return row

def increment_usage(user_id):
    if user_id == ADMIN_ID:
        return
    with lock:
        cur.execute('UPDATE users SET image_used=image_used+1 WHERE user_id=?',(user_id,))
        conn.commit()
        day = get_today_str()
        cur.execute('SELECT images_generated FROM stats WHERE day=?',(day,))
        s = cur.fetchone()
        if not s:
            cur.execute('INSERT INTO stats(day,images_generated) VALUES(?,?)',(day,1))
        else:
            cur.execute('UPDATE stats SET images_generated=images_generated+1 WHERE day=?',(day,))
        conn.commit()

def set_premium(user_id, months=1):
    expiry = datetime.utcnow() + timedelta(days=30*months)
    with lock:
        ensure_user(user_id)
        cur.execute('UPDATE users SET is_premium=1, premium_expiry=? WHERE user_id=?',(expiry.isoformat(),user_id))
        conn.commit()

def unset_premium(user_id):
    with lock:
        cur.execute('UPDATE users SET is_premium=0, premium_expiry=NULL WHERE user_id=?',(user_id,))
        conn.commit()

def check_premium(user):
    if user.get('is_premium'):
        pe = user.get('premium_expiry')
        if pe:
            try:
                exp = datetime.fromisoformat(pe)
                if exp > datetime.utcnow():
                    return True
                else:
                    unset_premium(user['user_id'])
            except:
                unset_premium(user['user_id'])
    return False

def premium_cleaner():
    while True:
        with lock:
            cur.execute('SELECT user_id, premium_expiry FROM users WHERE is_premium=1')
            rows = cur.fetchall()
            for r in rows:
                pe = r['premium_expiry']
                if not pe:
                    continue
                try:
                    exp = datetime.fromisoformat(pe)
                    if exp <= datetime.utcnow():
                        unset_premium(r['user_id'])
                except:
                    pass
        time.sleep(3600)

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    ensure_user(message.from_user.id)
    with lock:
        cur.execute('SELECT username FROM channels')
        rows = cur.fetchall()
        channels = [r['username'] for r in rows]
    if channels:
        kb = types.InlineKeyboardMarkup()
        for ch in channels:
            kb.add(types.InlineKeyboardButton(ch, url=f'https://t.me/{ch.replace("@","")}'))
        kb.add(types.InlineKeyboardButton("Tasdiqlash", callback_data="check_sub"))
        await message.reply("Iltimos, quyidagi kanallarga obuna bo‘ling:", reply_markup=kb)
    else:
        await message.reply("Salom! Matn yuboring — chat yoki rasm yarataman. Rasm kunlik limit bilan.")

@dp.callback_query_handler(lambda c: c.data=="check_sub")
async def check_subscription(call: types.CallbackQuery):
    with lock:
        cur.execute('SELECT username FROM channels')
        rows = cur.fetchall()
        channels = [r['username'] for r in rows]
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch, call.from_user.id)
            if member.status in ('left','kicked'):
                await call.answer("Hali barcha kanallarga obuna bo‘lmadingiz.")
                return
        except:
            await call.answer("Tekshiruvda xato.")
            return
    await bot.send_message(call.from_user.id,"Tasdiqlandi! Endi botdan foydalanishingiz mumkin.")

@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("Faqat admin.")
        return
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📈 Statistika","📢 Reklama")
    kb.add("➕ Kanal qo‘shish","➖ Kanal o‘chirish","📜 Kanal ro‘yxati")
    kb.add("🎁 Promo kod yaratish")
    await bot.send_message(message.chat.id,"Admin panel:",reply_markup=kb)

@dp.message_handler(lambda m: m.text=="📈 Statistika")
async def stat(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    with lock:
        cur.execute('SELECT COUNT(*) as c FROM users')
        users = cur.fetchone()['c']
        cur.execute('SELECT COUNT(*) as c FROM users WHERE is_premium=1')
        premiums = cur.fetchone()['c']
        cur.execute('SELECT images_generated FROM stats WHERE day=?',(get_today_str(),))
        s = cur.fetchone()
        images = s['images_generated'] if s else 0
    await bot.send_message(message.chat.id,f"Foydalanuvchilar: {users}\nPremium: {premiums}\nBugun rasmlar: {images}")

@dp.message_handler(lambda m: m.text=="➕ Kanal qo‘shish")
async def add_ch(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    msg = await bot.send_message(message.chat.id,"Kanal username yuboring (@kanal)")
    dp.register_message_handler(save_channel, lambda m: True, state=None)

async def save_channel(message: types.Message):
    username = message.text.strip()
    with lock:
        try:
            cur.execute('INSERT INTO channels(username) VALUES(?)',(username,))
            conn.commit()
            await bot.send_message(message.chat.id,f"Kanal qo‘shildi: {username}")
        except:
            await bot.send_message(message.chat.id,"Bu kanal allaqachon mavjud.")

@dp.message_handler(lambda m: m.text=="➖ Kanal o‘chirish")
async def del_ch(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    msg = await bot.send_message(message.chat.id,"O‘chiriladigan kanalni yuboring (@kanal)")
    dp.register_message_handler(remove_channel, lambda m: True, state=None)

async def remove_channel(message: types.Message):
    username = message.text.strip()
    with lock:
        cur.execute('DELETE FROM channels WHERE username=?',(username,))
        conn.commit()
        await bot.send_message(message.chat.id,f"{username} o‘chirildi.")

@dp.message_handler(lambda m: m.text=="📜 Kanal ro‘yxati")
async def list_ch(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    with lock:
        cur.execute('SELECT username FROM channels')
        rows = cur.fetchall()
    if not rows:
        await bot.send_message(message.chat.id,"Hech qanday kanal yo‘q.")
    else:
        await bot.send_message(message.chat.id,"\n".join([r['username'] for r in rows]))

@dp.message_handler(lambda m: m.text=="🎁 Promo kod yaratish")
async def promo_create(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    code = str(int(time.time()))
    with lock:
        cur.execute('INSERT INTO promo(code,active) VALUES(?,?)',(code,1))
        conn.commit()
    await bot.send_message(message.chat.id,f"Promo kod: {code}")

@dp.message_handler()
async def handler(message: types.Message):
    user_id = message.from_user.id
    prompt = (message.text or "").strip()
    if not prompt:
        return
    if is_bad_prompt(prompt):
        await message.reply("Taqiqlangan so‘z.")
        return
    user = ensure_user(user_id)
    photo_keywords = ["rasm","image","foto","picture","draw","generate","rasm_yasash","rasm_yarat"]
    is_photo = any(k in prompt.lower() for k in photo_keywords)
    if not is_photo:
        await bot.send_chat_action(user_id, "typing")
        ans = await ask_ai(prompt)
        await message.reply(ans)
        return
    if user_id != ADMIN_ID and user.get("image_used",0) >= IMAGE_DAILY_LIMIT:
        await message.reply("Rasm yaratish bo‘yicha kunlik limit tugadi.")
        return
    try:
        await bot.send_chat_action(user_id, "upload_photo")
        img = await generate_image_bytes(prompt)
        bio = io.BytesIO(img)
        bio.name = "ai.jpg"
        bio.seek(0)
        await bot.send_photo(user_id, photo=bio, caption=prompt)
        increment_usage(user_id)
    except:
        await message.reply("Xatolik.")

def start_workers():
    threading.Thread(target=premium_cleaner,daemon=True).start()

if __name__ == "__main__":
    start_workers()
    executor.start_polling(dp, skip_updates=True)
