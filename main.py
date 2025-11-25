import os
import sqlite3
import asyncio
import aiohttp
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import ReplyKeyboardMarkup, KeyboardButton, Message, ReplyKeyboardRemove
from pyrogram.enums import ParseMode
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_USERNAME = os.getenv("BOT_USERNAME", "your_bot_username")

app = Client(
    "ai_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

BAD_WORDS = [
    "seks", "sex", "porn", "xxx", "18+", "nude", "naked",
    "sikish", "sik", "sikmoq", "yalingoch", "yalangoch",
    "fuck", "fucking", "shit", "bitch", "ass", "dick", "cock",
    "pussy", "cunt", "whore", "slut", "nigger", "rape",
    "porno", "pornography", "nsfw", "erotic", "orgasm",
    "секс", "порно", "голый", "голая", "трахать", "ебать",
    "блять", "хуй", "пизда", "шлюха", "сиськи"
]

def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        image_limit INTEGER DEFAULT 3,
        bonus_limit INTEGER DEFAULT 0,
        premium INTEGER DEFAULT 0,
        premium_until TEXT,
        last_reset TEXT,
        join_date TEXT,
        referrer_id INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS channels (
        channel_id TEXT PRIMARY KEY,
        channel_username TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER,
        referred_id INTEGER,
        date TEXT
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

def add_user(user_id, username, referrer_id=None):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("INSERT OR IGNORE INTO users VALUES (?,?,3,0,0,NULL,?,?,?)",
              (user_id, username, now, now, referrer_id))
    conn.commit()
    conn.close()

def add_referral(referrer_id, referred_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("INSERT INTO referrals (referrer_id, referred_id, date) VALUES (?,?,?)",
              (referrer_id, referred_id, now))
    c.execute("UPDATE users SET bonus_limit = bonus_limit + 1 WHERE user_id=?", (referrer_id,))
    conn.commit()
    conn.close()

def get_referral_count(user_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

def update_image_limit(user_id, limit):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE users SET image_limit=? WHERE user_id=?", (limit, user_id))
    conn.commit()
    conn.close()

def reset_daily_limits(user_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("UPDATE users SET image_limit=3, last_reset=? WHERE user_id=? AND premium=0",
              (now, user_id))
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

async def check_subscription(client, user_id):
    channels = get_channels()
    if not channels:
        return True
    
    not_subscribed = []
    for channel in channels:
        try:
            member = await client.get_chat_member(channel[0], user_id)
            if member.status not in ["member", "administrator", "creator"]:
                not_subscribed.append(channel[1])
        except:
            not_subscribed.append(channel[1])
    
    return len(not_subscribed) == 0

def contains_bad_words(text):
    text_lower = text.lower()
    for word in BAD_WORDS:
        if word in text_lower:
            return True
    return False

def get_stats():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE premium=1")
    premium_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM referrals")
    total_referrals = c.fetchone()[0]
    conn.close()
    return total_users, premium_users, total_referrals

def get_all_users():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = c.fetchall()
    conn.close()
    return [user[0] for user in users]

async def translate_to_english(text):
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://translate.googleapis.com/translate_a/single"
            params = {
                'client': 'gtx',
                'sl': 'auto',
                'tl': 'en',
                'dt': 't',
                'q': text
            }
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    result = await response.json()
                    translated = ''.join([item[0] for item in result[0]])
                    return translated
        return text
    except Exception as e:
        print(f"Translation error: {e}")
        return text

async def generate_image_pollinations(prompt):
    try:
        translated_prompt = await translate_to_english(prompt)
        print(f"Original: {prompt}")
        print(f"Translated: {translated_prompt}")
        
        if len(translated_prompt) > 200:
            translated_prompt = translated_prompt[:200]
        
        enhanced_prompt = f"{translated_prompt}, high quality, detailed"
        safe_prompt = enhanced_prompt.replace(" ", "%20")
        
        image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true&enhance=true"
        
        print(f"Image URL: {image_url}")
        return image_url, translated_prompt
        
    except Exception as e:
        print(f"Error: {e}")
        safe_prompt = prompt[:100].replace(" ", "%20")
        return f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024", prompt[:100]

user_states = {}

def get_main_keyboard(user_id):
    keyboard = [
        [KeyboardButton("🎨 Rasm yaratish")],
        [KeyboardButton("📊 Statistikam"), KeyboardButton("👥 Referal")],
        [KeyboardButton("ℹ️ Yordam")]
    ]
    if user_id == ADMIN_ID:
        keyboard.append([KeyboardButton("👨‍💼 Admin Panel")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_admin_keyboard():
    keyboard = [
        [KeyboardButton("📊 Barcha statistika")],
        [KeyboardButton("➕ Kanal qo'shish"), KeyboardButton("➖ Kanal o'chirish")],
        [KeyboardButton("💎 Premium berish"), KeyboardButton("📢 Reklama yuborish")],
        [KeyboardButton("👥 Foydalanuvchilar ro'yxati")],
        [KeyboardButton("🔙 Orqaga")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_cancel_keyboard():
    keyboard = [[KeyboardButton("❌ Bekor qilish")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Foydalanuvchi"
    
    user_states.pop(user_id, None)
    
    referrer_id = None
    if len(message.command) > 1:
        try:
            referrer_id = int(message.command[1])
            if referrer_id == user_id:
                referrer_id = None
        except:
            referrer_id = None
    
    existing_user = get_user(user_id)
    if not existing_user:
        add_user(user_id, username, referrer_id)
        if referrer_id and get_user(referrer_id):
            add_referral(referrer_id, user_id)
            try:
                await client.send_message(
                    referrer_id,
                    f"🎉 Tabriklaymiz!\n\n"
                    f"👤 Yangi foydalanuvchi sizning havolangiz orqali qo'shildi!\n"
                    f"🎁 +1 bonus limit qo'shildi!"
                )
            except:
                pass
    
    if not await check_subscription(client, user_id):
        channels = get_channels()
        channel_text = "\n".join([f"📢 {ch[1]}" for ch in channels])
        
        await message.reply_text(
            f"👋 Salom {username}!\n\n"
            f"🔐 Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:\n\n"
            f"{channel_text}\n\n"
            "✅ Obuna bo'lganingizdan keyin /start ni qayta bosing",
            reply_markup=ReplyKeyboardRemove()
        )
        return
    
    await message.reply_text(
        f"👋 Salom {username}!\n\n"
        "🎨 Men professional AI rasm yaratish botiman!\n"
        "🖼 Har qanday tasvirlangan rasmni yaratib beraman.\n\n"
        "📝 Kerakli bo'limni tanlang:",
        reply_markup=get_main_keyboard(user_id)
    )

@app.on_message(filters.regex("^🎨 Rasm yaratish$") & filters.private)
async def generate_image_button(client, message: Message):
    user_id = message.from_user.id
    
    if not await check_subscription(client, user_id):
        await message.reply_text("❌ Avval kanallarga obuna bo'ling! /start")
        return
    
    check_and_reset_limits(user_id)
    user = get_user(user_id)
    is_premium = check_premium(user_id)
    
    total_limit = user[2] + user[3]
    
    if not is_premium and total_limit <= 0:
        ref_count = get_referral_count(user_id)
        await message.reply_text(
            f"⚠️ Kunlik limitingiz tugadi!\n\n"
            f"📊 Kunlik limit: 0/3\n"
            f"🎁 Bonus limit: {user[3]}\n"
            f"👥 Referallar: {ref_count}\n\n"
            f"💡 Do'stlaringizni taklif qiling va bonus limitlar oling!\n"
            f"👥 Referal bo'limiga o'ting",
            reply_markup=get_main_keyboard(user_id)
        )
        return
    
    user_states[user_id] = "waiting_image_prompt"
    
    await message.reply_text(
        "🎨 <b>Rasm yaratish</b>\n\n"
        f"📊 Limitlar:\n"
        f"📅 Kunlik: <b>{user[2]}/3</b>\n"
        f"🎁 Bonus: <b>{user[3]}</b>\n"
        f"💎 Status: <b>{'Premium ♾️' if is_premium else 'Oddiy'}</b>\n\n"
        "📝 Rasm uchun tavsif yuboring:\n"
        "🌐 Har qanday tilda yozishingiz mumkin!\n\n"
        "Misol:\n"
        "• <i>tog'lar ustida go'zal quyosh botishi</i>\n"
        "• <i>a beautiful sunset over mountains</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=get_cancel_keyboard()
    )

@app.on_message(filters.regex("^📊 Statistikam$") & filters.private)
async def my_stats_button(client, message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    is_premium = check_premium(user_id)
    ref_count = get_referral_count(user_id)
    
    status = "💎 Premium" if is_premium else "🆓 Oddiy"
    premium_until = "N/A" if not is_premium else user[5].split("T")[0]
    
    text = (
        f"📊 <b>Sizning statistikangiz:</b>\n\n"
        f"👤 Status: <b>{status}</b>\n"
        f"📅 Kunlik limit: <b>{user[2]}/3</b>\n"
        f"🎁 Bonus limit: <b>{user[3]}</b>\n"
        f"👥 Referallar: <b>{ref_count}</b>\n"
        f"📅 Qo'shilgan: <code>{user[7].split('T')[0]}</code>\n"
    )
    
    if is_premium:
        text += f"\n⏰ Premium tugash: <code>{premium_until}</code>"
    
    await message.reply_text(text, parse_mode=ParseMode.HTML)

@app.on_message(filters.regex("^👥 Referal$") & filters.private)
async def referral_button(client, message: Message):
    user_id = message.from_user.id
    ref_count = get_referral_count(user_id)
    user = get_user(user_id)
    
    ref_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
    
    text = (
        f"👥 <b>Referal tizimi</b>\n\n"
        f"🎁 Har bir do'stingiz uchun +1 bonus limit!\n"
        f"♾️ Bonus limitlar hech qachon yangilanmaydi!\n\n"
        f"📊 Sizning statistikangiz:\n"
        f"👥 Taklif qilganlar: <b>{ref_count}</b> ta\n"
        f"🎁 Bonus limitlar: <b>{user[3]}</b> ta\n\n"
        f"🔗 Sizning havolangiz:\n"
        f"<code>{ref_link}</code>\n\n"
        f"💡 Havolani do'stlaringizga yuboring!"
    )
    
    await message.reply_text(text, parse_mode=ParseMode.HTML)

@app.on_message(filters.regex("^ℹ️ Yordam$") & filters.private)
async def help_button(client, message: Message):
    text = (
        "ℹ️ <b>Yordam bo'limi:</b>\n\n"
        "🎨 <b>Rasm yaratish:</b>\n"
        "AI professional rasm yaratadi\n"
        "🌐 Har qanday tilda yozishingiz mumkin!\n\n"
        "📊 <b>Limitlar:</b>\n"
        "📅 Kunlik: 3 rasm (har kuni yangilanadi)\n"
        "🎁 Bonus: Do'stlaringizni taklif qiling!\n"
        "💎 Premium: ♾️ Cheksiz\n\n"
        "👥 <b>Referal tizimi:</b>\n"
        "• 1 do'st = 1 bonus limit\n"
        "• Bonus limitlar doim qoladi!\n"
        "• Cheksiz do'st taklif qiling\n\n"
        "⚠️ Taqiqlangan so'zlardan foydalanmang!"
    )
    await message.reply_text(text, parse_mode=ParseMode.HTML)

@app.on_message(filters.regex("^👨‍💼 Admin Panel$") & filters.private)
async def admin_panel_button(client, message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply_text("❌ Sizda ruxsat yo'q!")
        return
    
    total_users, premium_users, total_referrals = get_stats()
    channels = get_channels()
    
    text = (
        f"👨‍💼 <b>Admin Panel</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{total_users}</b>\n"
        f"💎 Premium: <b>{premium_users}</b>\n"
        f"🆓 Oddiy: <b>{total_users - premium_users}</b>\n"
        f"📢 Majburiy kanallar: <b>{len(channels)}</b>\n"
        f"👥 Jami referallar: <b>{total_referrals}</b>"
    )
    
    await message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=get_admin_keyboard())

@app.on_message(filters.regex("^📊 Barcha statistika$") & filters.private)
async def admin_stats_button(client, message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    total_users, premium_users, total_referrals = get_stats()
    channels = get_channels()
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE date(join_date) = date('now')")
    today_users = c.fetchone()[0]
    c.execute("SELECT SUM(bonus_limit) FROM users")
    total_bonus = c.fetchone()[0] or 0
    conn.close()
    
    text = (
        f"📊 <b>Umumiy statistika:</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{total_users}</b>\n"
        f"💎 Premium: <b>{premium_users}</b>\n"
        f"🆓 Oddiy: <b>{total_users - premium_users}</b>\n"
        f"📢 Majburiy kanallar: <b>{len(channels)}</b>\n"
        f"🆕 Bugungi yangi: <b>{today_users}</b>\n"
        f"👥 Jami referallar: <b>{total_referrals}</b>\n"
        f"🎁 Jami bonus limitlar: <b>{total_bonus}</b>"
    )
    
    await message.reply_text(text, parse_mode=ParseMode.HTML)

@app.on_message(filters.regex("^👥 Foydalanuvchilar ro'yxati$") & filters.private)
async def users_list_button(client, message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT user_id, username, premium, bonus_limit, join_date FROM users ORDER BY join_date DESC LIMIT 50")
    users = c.fetchall()
    conn.close()
    
    text = "👥 <b>Oxirgi 50 ta foydalanuvchi:</b>\n\n"
    
    for user in users:
        status = "💎" if user[2] == 1 else "🆓"
        username = user[1] if user[1] else "No username"
        join_date = user[4].split("T")[0]
        ref_count = get_referral_count(user[0])
        text += f"{status} <code>{user[0]}</code> | @{username} | 🎁{user[3]} | 👥{ref_count} | {join_date}\n"
    
    await message.reply_text(text, parse_mode=ParseMode.HTML)

@app.on_message(filters.regex("^➕ Kanal qo'shish$") & filters.private)
async def add_channel_button(client, message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    user_states[ADMIN_ID] = "waiting_channel_add"
    await message.reply_text(
        "➕ <b>Kanal qo'shish:</b>\n\n"
        "Kanal username yoki ID yuboring\n"
        "Misol: <code>@channelname</code> yoki <code>-1001234567890</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=get_cancel_keyboard()
    )

@app.on_message(filters.regex("^➖ Kanal o'chirish$") & filters.private)
async def remove_channel_button(client, message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    channels = get_channels()
    if not channels:
        await message.reply_text("❌ Kanallar yo'q!", reply_markup=get_admin_keyboard())
        return
    
    user_states[ADMIN_ID] = "waiting_channel_remove"
    text = "➖ <b>Kanal o'chirish:</b>\n\nKanal ID yuboring:\n\n"
    for ch in channels:
        text += f"📢 {ch[1]} - <code>{ch[0]}</code>\n"
    
    await message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=get_cancel_keyboard())

@app.on_message(filters.regex("^💎 Premium berish$") & filters.private)
async def give_premium_button(client, message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    user_states[ADMIN_ID] = "waiting_premium_user"
    await message.reply_text(
        "💎 <b>Premium berish:</b>\n\n"
        "Foydalanuvchi ID yuboring\n"
        "Misol: <code>123456789</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=get_cancel_keyboard()
    )

@app.on_message(filters.regex("^📢 Reklama yuborish$") & filters.private)
async def send_ad_button(client, message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    user_states[ADMIN_ID] = "waiting_ad_message"
    await message.reply_text(
        "📢 <b>Reklama yuborish:</b>\n\n"
        "Xabar yuboring (matn yoki rasm + matn)",
        parse_mode=ParseMode.HTML,
        reply_markup=get_cancel_keyboard()
    )

@app.on_message(filters.regex("^🔙 Orqaga$") & filters.private)
async def back_button(client, message: Message):
    user_id = message.from_user.id
    user_states.pop(user_id, None)
    await message.reply_text("🏠 Bosh sahifa", reply_markup=get_main_keyboard(user_id))

@app.on_message(filters.regex("^❌ Bekor qilish$") & filters.private)
async def cancel_button(client, message: Message):
    user_id = message.from_user.id
    user_states.pop(user_id, None)
    
    if user_id == ADMIN_ID and message.reply_markup and "🔙 Orqaga" in str(message.reply_markup):
        await message.reply_text("❌ Bekor qilindi", reply_markup=get_admin_keyboard())
    else:
        await message.reply_text("❌ Bekor qilindi", reply_markup=get_main_keyboard(user_id))

@app.on_message(filters.text & filters.private)
async def handle_messages(client, message: Message):
    user_id = message.from_user.id
    
    if not await check_subscription(client, user_id):
        await message.reply_text("❌ Avval kanallarga obuna bo'ling! /start")
        return
    
    if contains_bad_words(message.text):
        await message.reply_text("⚠️ Taqiqlangan so'zdan foydalanmang!")
        return
    
    state = user_states.get(user_id)
    
    if state == "waiting_image_prompt":
        check_and_reset_limits(user_id)
        user = get_user(user_id)
        is_premium = check_premium(user_id)
        
        total_limit = user[2] + user[3]
        
        if not is_premium and total_limit <= 0:
            await message.reply_text("⚠️ Limitingiz tugadi!", reply_markup=get_main_keyboard(user_id))
            user_states.pop(user_id, None)
            return
        
        wait_msg = await message.reply_text("🎨 Rasm tayyorlanmoqda...")
        
        image_url, translated_text = await generate_image_pollinations(message.text)
        
        try:
            await message.reply_photo(
                photo=image_url,
                caption=(
                    f"✅ <b>Rasm tayyor!</b>\n\n"
                    f"📝 Tavsif: <i>{message.text[:100]}</i>\n"
                    f"🌐 Tarjima: <i>{translated_text[:100]}</i>"
                ),
                parse_mode=ParseMode.HTML
            )
            
            if not is_premium:
                conn = sqlite3.connect('database.db')
                c = conn.cursor()
                if user[2] > 0:
                    c.execute("UPDATE users SET image_limit = image_limit - 1 WHERE user_id=?", (user_id,))
                else:
                    c.execute("UPDATE users SET bonus_limit = bonus_limit - 1 WHERE user_id=?", (user_id,))
                conn.commit()
                conn.close()
                
                updated_user = get_user(user_id)
                await message.reply_text(
                    f"📊 Limitlar:\n"
                    f"📅 Kunlik: <b>{updated_user[2]}/3</b>\n"
                    f"🎁 Bonus: <b>{updated_user[3]}</b>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=get_main_keyboard(user_id)
                )
            else:
                await message.reply_text("✅ Premium - cheksiz!", reply_markup=get_main_keyboard(user_id))
            
            await wait_msg.delete()
            
        except Exception as e:
            print(f"Error: {e}")
            await wait_msg.delete()
            await message.reply_text("🔄 Qayta urinib ko'ring.", reply
