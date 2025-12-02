import os
import sqlite3
import asyncio
import aiohttp
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.enums import ParseMode
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

app = Client("ai_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

BAD_WORDS = ["seks", "sex", "porn", "xxx", "18+", "nude", "naked", "sikish", "sik", "yalingoch", "fuck", "shit", "bitch", "dick", "cock", "pussy", "cunt", "whore", "slut", "nigger", "rape", "porno", "nsfw", "erotic", "секс", "порно", "голый", "трахать", "ебать", "блять", "хуй", "пизда", "шлюха"]

def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, image_limit INTEGER DEFAULT 3, premium INTEGER DEFAULT 0, premium_until TEXT, last_reset TEXT, join_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS channels (channel_id TEXT PRIMARY KEY, channel_username TEXT)''')
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
    c.execute("INSERT OR IGNORE INTO users VALUES (?,?,3,0,NULL,?,?)", (user_id, username, now, now))
    conn.commit()
    conn.close()

def get_channels():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM channels")
    channels = c.fetchall()
    conn.close()
    return channels

async def check_subscription(client, user_id):
    if user_id == ADMIN_ID:
        return True
    
    channels = get_channels()
    if not channels:
        return True
    
    for channel in channels:
        try:
            chat_id = channel[0]
            if not chat_id.startswith('-'):
                chat_id = f"@{channel[1].replace('@', '')}"
            
            member = await client.get_chat_member(chat_id, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except Exception as e:
            print(f"Check error: {e}")
            return False
    
    return True

def check_and_reset_limits(user_id):
    user = get_user(user_id)
    if user:
        last_reset = datetime.fromisoformat(user[5])
        if datetime.now() - last_reset > timedelta(days=1):
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            now = datetime.now().isoformat()
            c.execute("UPDATE users SET image_limit=3, last_reset=? WHERE user_id=? AND premium=0", (now, user_id))
            conn.commit()
            conn.close()

def check_premium(user_id):
    user = get_user(user_id)
    if user and user[3] == 1:
        if user[4] and datetime.now() < datetime.fromisoformat(user[4]):
            return True
        else:
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute("UPDATE users SET premium=0 WHERE user_id=?", (user_id,))
            conn.commit()
            conn.close()
    return False

def contains_bad_words(text):
    return any(word in text.lower() for word in BAD_WORDS)

async def translate_to_english(text):
    for attempt in range(2):
        try:
            async with aiohttp.ClientSession() as session:
                params = {'client': 'gtx', 'sl': 'auto', 'tl': 'en', 'dt': 't', 'q': text}
                async with session.get("https://translate.googleapis.com/translate_a/single", params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        result = await response.json()
                        return ''.join([item[0] for item in result[0]])
        except:
            if attempt < 1:
                await asyncio.sleep(0.5)
    return text

async def generate_image(prompt):
    translated = await translate_to_english(prompt)
    enhanced = f"{translated}, high quality, detailed"[:150]
    safe = enhanced.replace(" ", "%20").replace(",", "%2C")
    
    urls = [
        f"https://image.pollinations.ai/prompt/{safe}?width=1024&height=1024&nologo=true&enhance=true",
        f"https://pollinations.ai/p/{safe}?width=1024&height=1024&nologo=true",
        f"https://image.pollinations.ai/prompt/{safe}?width=1024&height=1024"
    ]
    
    for url in urls:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        return url, translated
        except:
            await asyncio.sleep(0.3)
    
    return f"https://image.pollinations.ai/prompt/{translated[:80].replace(' ', '%20')}", translated

user_states = {}

def get_main_keyboard(user_id):
    kb = [[KeyboardButton("🎨 Rasm yaratish")], [KeyboardButton("📊 Statistikam"), KeyboardButton("ℹ️ Yordam")]]
    if user_id == ADMIN_ID:
        kb.append([KeyboardButton("👨‍💼 Admin Panel")])
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def get_cancel_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("❌ Bekor qilish")]], resize_keyboard=True)

@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    user_id = message.from_user.id
    username = message.from_user.username or "User"
    user_states.pop(user_id, None)
    
    if not get_user(user_id):
        add_user(user_id, username)
    
    if user_id != ADMIN_ID:
        channels = get_channels()
        if channels:
            is_sub = await check_subscription(client, user_id)
            if not is_sub:
                keyboard = []
                for ch in channels:
                    link = f"https://t.me/{ch[1].replace('@', '')}"
                    keyboard.append([InlineKeyboardButton(f"📢 {ch[1]}", url=link)])
                keyboard.append([InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_sub")])
                
                ch_list = "\n".join([f"📢 {ch[1]}" for ch in channels])
                await message.reply_text(
                    f"👋 Salom {username}!\n\n"
                    f"🔐 Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:\n\n"
                    f"{ch_list}\n\n"
                    f"✅ Obuna bo'lgandan keyin pastdagi tugmani bosing 👇",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return
    
    await message.reply_text(
        f"👋 Salom {username}!\n\n"
        f"🎨 Men professional AI rasm yaratish botiman!\n"
        f"🖼 Har qanday rasmni yaratib beraman.\n"
        f"🌐 Har qanday tilda yozing!\n\n"
        f"📝 Tugmani tanlang:",
        reply_markup=get_main_keyboard(user_id)
    )

@app.on_callback_query(filters.regex("^check_sub$"))
async def check_sub_callback(client, callback_query):
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username or "User"
    
    if await check_subscription(client, user_id):
        await callback_query.message.delete()
        await callback_query.message.reply_text(
            f"✅ Obuna tasdiqlandi!\n\n"
            f"👋 Salom {username}!\n\n"
            f"🎨 Men professional AI rasm yaratish botiman!\n"
            f"📝 Tugmani tanlang:",
            reply_markup=get_main_keyboard(user_id)
        )
    else:
        await callback_query.answer("❌ Hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)

@app.on_message(filters.regex("^🎨 Rasm yaratish$") & filters.private)
async def gen_img(client, message):
    user_id = message.from_user.id
    
    if not await check_subscription(client, user_id):
        await message.reply_text("❌ Avval kanallarga obuna bo'ling! /start")
        return
    
    check_and_reset_limits(user_id)
    user = get_user(user_id)
    is_premium = check_premium(user_id)
    
    if not is_premium and user[2] <= 0:
        await message.reply_text("⚠️ Kunlik limit tugadi!\n\n📊 0/3\n💎 Premium uchun adminга murojaat qiling", reply_markup=get_main_keyboard(user_id))
        return
    
    user_states[user_id] = "wait_img"
    await message.reply_text(
        f"🎨 <b>Rasm yaratish</b>\n\n"
        f"📊 Limit: <b>{user[2]}/3</b>\n"
        f"💎 Status: <b>{'Premium' if is_premium else 'Oddiy'}</b>\n\n"
        f"📝 Rasm tavsifini yuboring:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_cancel_keyboard()
    )

@app.on_message(filters.regex("^📊 Statistikam$") & filters.private)
async def stats(client, message):
    user = get_user(message.from_user.id)
    is_premium = check_premium(message.from_user.id)
    status = "💎 Premium" if is_premium else "🆓 Oddiy"
    text = f"📊 <b>Statistika:</b>\n\n👤 Status: <b>{status}</b>\n📅 Limit: <b>{user[2]}/3</b>\n📅 Sana: <code>{user[6].split('T')[0]}</code>"
    if is_premium and user[4]:
        text += f"\n⏰ Premium: <code>{user[4].split('T')[0]}</code>"
    await message.reply_text(text, parse_mode=ParseMode.HTML)

@app.on_message(filters.regex("^ℹ️ Yordam$") & filters.private)
async def help_cmd(client, message):
    await message.reply_text(
        "ℹ️ <b>Yordam:</b>\n\n"
        "🎨 AI professional rasm yaratadi\n"
        "🌐 Har qanday tilda\n"
        "📊 Limit: 3/kun (Oddiy)\n"
        "💎 Premium: Cheksiz",
        parse_mode=ParseMode.HTML
    )

@app.on_message(filters.regex("^❌ Bekor qilish$") & filters.private)
async def cancel(client, message):
    user_states.pop(message.from_user.id, None)
    await message.reply_text("❌ Bekor qilindi", reply_markup=get_main_keyboard(message.from_user.id))

@app.on_message(filters.text & filters.private)
async def handle_text(client, message):
    user_id = message.from_user.id
    
    if not await check_subscription(client, user_id):
        await message.reply_text("❌ Avval kanallarga obuna bo'ling! /start")
        return
    
    if contains_bad_words(message.text):
        await message.reply_text("⚠️ Taqiqlangan so'z!")
        return
    
    if user_states.get(user_id) == "wait_img":
        check_and_reset_limits(user_id)
        user = get_user(user_id)
        is_premium = check_premium(user_id)
        
        if not is_premium and user[2] <= 0:
            await message.reply_text("⚠️ Limit tugadi!", reply_markup=get_main_keyboard(user_id))
            user_states.pop(user_id, None)
            return
        
        wait = await message.reply_text("🎨 Tayyorlanmoqda...")
        url, trans = await generate_image(message.text)
        
        success = False
        for attempt in range(3):
            try:
                await message.reply_photo(
                    photo=url,
                    caption=f"✅ <b>Tayyor!</b>\n\n📝 <i>{message.text[:100]}</i>",
                    parse_mode=ParseMode.HTML
                )
                success = True
                break
            except:
                if attempt < 2:
                    await asyncio.sleep(1)
                    url, trans = await generate_image(message.text)
        
        if not success:
            try:
                backup = f"https://image.pollinations.ai/prompt/{message.text[:40].replace(' ', '%20')}"
                await message.reply_photo(photo=backup, caption="✅ Tayyor!")
            except:
                await message.reply_text(f"✅ Tayyor!\n\n🔗 {backup}")
        
        if not is_premium:
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute("UPDATE users SET image_limit = image_limit - 1 WHERE user_id=?", (user_id,))
            conn.commit()
            conn.close()
            upd = get_user(user_id)
            await message.reply_text(f"📊 Qolgan: <b>{upd[2]}/3</b>", parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(user_id))
        else:
            await message.reply_text("✅ Premium!", reply_markup=get_main_keyboard(user_id))
        
        try:
            await wait.delete()
        except:
            pass
        
        user_states.pop(user_id, None)
        return
    
    await message.reply_text("❓ Tushunmadim", reply_markup=get_main_keyboard(user_id))

if __name__ == "__main__":
    from panel import setup_admin_handlers
    setup_admin_handlers(app, ADMIN_ID)
    print("✅ Bot ishga tushdi!")
    app.run()
