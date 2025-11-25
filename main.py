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
    c.execute("INSERT OR IGNORE INTO users VALUES (?,?,3,0,NULL,?,?)",
              (user_id, username, now, now))
    conn.commit()
    conn.close()

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
        last_reset = datetime.fromisoformat(user[5])
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
    conn.close()
    return total_users, premium_users

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

async def generate_image_with_flux(prompt):
    try:
        translated_prompt = await translate_to_english(prompt)
        print(f"Original: {prompt}")
        print(f"Translated: {translated_prompt}")
        
        if len(translated_prompt) > 200:
            translated_prompt = translated_prompt[:200]
        
        enhanced_prompt = f"{translated_prompt}, masterpiece, detailed"
        safe_prompt = enhanced_prompt.replace(" ", "%20").replace(",", "%2C").replace("'", "%27").replace('"', "%22")
        
        image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true"
        
        print(f"Generated URL: {image_url}")
        return image_url, translated_prompt
        
    except Exception as e:
        print(f"Error in generation: {e}")
        safe_prompt = prompt[:100].replace(" ", "%20")
        return f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024", prompt[:100]

user_states = {}

def get_main_keyboard(user_id):
    keyboard = [
        [KeyboardButton("🎨 Rasm yaratish")],
        [KeyboardButton("📊 Statistikam"), KeyboardButton("ℹ️ Yordam")]
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
    add_user(user_id, username)
    
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
    
    if not is_premium and user[2] <= 0:
        await message.reply_text(
            "⚠️ Kunlik limitingiz tugadi!\n"
            "💎 Premium obunani admin orqali oling.",
            reply_markup=get_main_keyboard(user_id)
        )
        return
    
    user_states[user_id] = "waiting_image_prompt"
    
    await message.reply_text(
        "🎨 <b>Rasm yaratish</b>\n\n"
        f"📊 Qolgan limitingiz: <b>{user[2] if not is_premium else '♾️ Cheksiz'}</b>\n\n"
        "📝 Rasm uchun tavsif yuboring:\n"
        "🌐 Har qanday tilda yozishingiz mumkin!\n\n"
        "Misol:\n"
        "• <i>tog'lar ustida go'zal quyosh botishi</i>\n"
        "• <i>a beautiful sunset over mountains</i>\n"
        "• <i>красивый закат над горами</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=get_cancel_keyboard()
    )

@app.on_message(filters.regex("^📊 Statistikam$") & filters.private)
async def my_stats_button(client, message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    is_premium = check_premium(user_id)
    
    status = "💎 Premium" if is_premium else "🆓 Oddiy"
    premium_until = "N/A" if not is_premium else user[4].split("T")[0]
    
    text = (
        f"📊 <b>Sizning statistikangiz:</b>\n\n"
        f"👤 Status: <b>{status}</b>\n"
        f"🎨 Rasm limiti: <b>{user[2] if not is_premium else '♾️'}</b>\n"
        f"📅 Qo'shilgan sana: <code>{user[6].split('T')[0]}</code>\n"
    )
    
    if is_premium:
        text += f"⏰ Premium tugash: <code>{premium_until}</code>"
    
    await message.reply_text(text, parse_mode=ParseMode.HTML)

@app.on_message(filters.regex("^ℹ️ Yordam$") & filters.private)
async def help_button(client, message: Message):
    text = (
        "ℹ️ <b>Yordam bo'limi:</b>\n\n"
        "🎨 <b>Rasm yaratish:</b>\n"
        "AI professional rasm yaratadi\n"
        "🌐 Har qanday tilda yozishingiz mumkin!\n"
        "🤖 AI Model: <b>Flux Pro</b>\n\n"
        "📊 <b>Limitlar (kunlik):</b>\n"
        "🆓 Oddiy: 3 rasm\n"
        "💎 Premium: ♾️ Cheksiz\n\n"
        "💡 <b>Maslahatlar:</b>\n"
        "• O'zbek, Rus, Ingliz - istalgan tilda\n"
        "• Detallarga e'tibor bering\n"
        "• Matn avtomatik tarjima va takomillashtiriladi\n"
        "• 10-15 soniya kutib turing\n\n"
        "⚠️ Taqiqlangan so'zlardan foydalanmang!"
    )
    await message.reply_text(text, parse_mode=ParseMode.HTML)

@app.on_message(filters.regex("^👨‍💼 Admin Panel$") & filters.private)
async def admin_panel_button(client, message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply_text("❌ Sizda ruxsat yo'q!")
        return
    
    total_users, premium_users = get_stats()
    channels = get_channels()
    
    text = (
        f"👨‍💼 <b>Admin Panel</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{total_users}</b>\n"
        f"💎 Premium: <b>{premium_users}</b>\n"
        f"🆓 Oddiy: <b>{total_users - premium_users}</b>\n"
        f"📢 Majburiy kanallar: <b>{len(channels)}</b>"
    )
    
    await message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=get_admin_keyboard())

@app.on_message(filters.regex("^📊 Barcha statistika$") & filters.private)
async def admin_stats_button(client, message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    total_users, premium_users = get_stats()
    channels = get_channels()
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE date(join_date) = date('now')")
    today_users = c.fetchone()[0]
    conn.close()
    
    text = (
        f"📊 <b>Umumiy statistika:</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{total_users}</b>\n"
        f"💎 Premium: <b>{premium_users}</b>\n"
        f"🆓 Oddiy: <b>{total_users - premium_users}</b>\n"
        f"📢 Majburiy kanallar: <b>{len(channels)}</b>\n"
        f"🆕 Bugungi yangi: <b>{today_users}</b>"
    )
    
    await message.reply_text(text, parse_mode=ParseMode.HTML)

@app.on_message(filters.regex("^👥 Foydalanuvchilar ro'yxati$") & filters.private)
async def users_list_button(client, message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT user_id, username, premium, join_date FROM users ORDER BY join_date DESC LIMIT 50")
    users = c.fetchall()
    conn.close()
    
    text = "👥 <b>Oxirgi 50 ta foydalanuvchi:</b>\n\n"
    
    for user in users:
        status = "💎" if user[2] == 1 else "🆓"
        username = user[1] if user[1] else "No username"
        join_date = user[3].split("T")[0]
        text += f"{status} <code>{user[0]}</code> | @{username} | {join_date}\n"
    
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
        
        if not is_premium and user[2] <= 0:
            await message.reply_text("⚠️ Kunlik limitingiz tugadi!", reply_markup=get_main_keyboard(user_id))
            user_states.pop(user_id, None)
            return
        
        wait_msg = await message.reply_text("🎨 Rasm tayyorlanmoqda...")
        
        image_url, translated_text = await generate_image_with_flux(message.text)
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await message.reply_photo(
                    photo=image_url,
                    caption=(
                        f"✅ <b>Rasm tayyor!</b>\n\n"
                        f"📝 Sizning matningiz:\n<i>{message.text[:100]}</i>\n\n"
                        f"🌐 Tarjima:\n<i>{translated_text[:100]}</i>"
                    ),
                    parse_mode=ParseMode.HTML
                )
                
                if not is_premium:
                    update_image_limit(user_id, user[2]-1)
                    remaining = user[2] - 1
                    await message.reply_text(
                        f"📊 Qolgan limit: <b>{remaining}</b>",
                        parse_mode=ParseMode.HTML,
                        reply_markup=get_main_keyboard(user_id)
                    )
                else:
                    await message.reply_text("✅ Premium - cheksiz!", reply_markup=get_main_keyboard(user_id))
                
                await wait_msg.delete()
                break
                
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                    image_url, translated_text = await generate_image_with_flux(message.text)
                else:
                    await wait_msg.delete()
                    
                    simple_prompt = message.text[:50].replace(" ", "%20")
                    backup_url = f"https://image.pollinations.ai/prompt/{simple_prompt}?width=512&height=512"
                    
                    try:
                        await message.reply_photo(
                            photo=backup_url,
                            caption=f"✅ Rasm tayyor!\n\n📝 {message.text[:100]}",
                            parse_mode=ParseMode.HTML
                        )
                        
                        if not is_premium:
                            update_image_limit(user_id, user[2]-1)
                            remaining = user[2] - 1
                            await message.reply_text(
                                f"📊 Qolgan limit: <b>{remaining}</b>",
                                parse_mode=ParseMode.HTML,
                                reply_markup=get_main_keyboard(user_id)
                            )
                        else:
                            await message.reply_text("✅ Premium - cheksiz!", reply_markup=get_main_keyboard(user_id))
                    except:
                        await message.reply_text(
                            "🔄 Iltimos qayta urinib ko'ring.",
                            reply_markup=get_main_keyboard(user_id)
                        )
        
        user_states.pop(user_id, None)
        return
    
    elif user_id == ADMIN_ID:
        if state == "waiting_channel_add":
            try:
                channel_username = message.text.strip()
                chat = await client.get_chat(channel_username)
                add_channel(str(chat.id), channel_username)
                await message.reply_text(f"✅ Kanal qo'shildi: {channel_username}", reply_markup=get_admin_keyboard())
            except Exception as e:
                await message.reply_text(f"❌ Xatolik: {str(e)}", reply_markup=get_admin_keyboard())
            user_states.pop(ADMIN_ID, None)
            return
        
        elif state == "waiting_channel_remove":
            try:
                channel_id = message.text.strip()
                remove_channel(channel_id)
                await message.reply_text("✅ Kanal o'chirildi!", reply_markup=get_admin_keyboard())
            except:
                await message.reply_text("❌ Xatolik yuz berdi!", reply_markup=get_admin_keyboard())
            user_states.pop(ADMIN_ID, None)
            return
        
        elif state == "waiting_premium_user":
            try:
                target_user_id = int(message.text.strip())
                set_premium(target_user_id, 30)
                
                try:
                    await client.send_message(
                        target_user_id,
                        "🎉 Tabriklaymiz!\n\n"
                        "💎 Sizga 30 kunlik Premium obuna berildi!\n"
                        "♾️ Endi cheksiz rasm yaratishingiz mumkin!"
                    )
                except:
                    pass
                
                await message.reply_text(f"✅ User {target_user_id} ga Premium berildi!", reply_markup=get_admin_keyboard())
            except:
                await message.reply_text("❌ Noto'g'ri ID!", reply_markup=get_admin_keyboard())
            user_states.pop(ADMIN_ID, None)
            return
        
        elif state == "waiting_ad_message":
            users = get_all_users()
            success = 0
            failed = 0
            
            status_msg = await message.reply_text("📢 Reklama yuborilmoqda...")
            
            for uid in users:
                try:
                    if message.photo:
                        await client.send_photo(uid, message.photo.file_id, caption=message.caption)
                    else:
                        await client.send_message(uid, message.text)
                    success += 1
                    await asyncio.sleep(0.05)
                except:
                    failed += 1
            
            await status_msg.edit_text(
                f"✅ <b>Reklama yuborildi!</b>\n\n"
                f"📊 Yuborildi: <b>{success}</b>\n"
                f"❌ Xatolik: <b>{failed}</b>",
                parse_mode=ParseMode.HTML
            )
            
            await message.reply_text("🏠 Bosh sahifa", reply_markup=get_admin_keyboard())
            user_states.pop(ADMIN_ID, None)
            return
    
    await message.reply_text(
        "❓ Buyruqni tushunmadim.\n"
        "🎨 Rasm yaratish uchun tugmani bosing.",
        reply_markup=get_main_keyboard(user_id)
    )

@app.on_message(filters.photo & filters.private)
async def handle_photo(client, message: Message):
    user_id = message.from_user.id
    
    if user_id == ADMIN_ID and user_states.get(ADMIN_ID) == "waiting_ad_message":
        return
    
    await message.reply_text(
        "📸 Rasm qabul qilindi, lekin men faqat matnli tavsif orqali rasm yarataman.\n"
        "🎨 Rasm yaratish tugmasini bosing va tavsif yuboring."
    )

print("✅ Bot ishga tushdi!")
app.run()=get_admin_keyboard())
            user_states.pop(ADMIN_ID, None)
            return
        
        elif state == "waiting_premium_user":
            try:
                target_user_id = int(message.text.strip())
                set_premium(target_user_id, 30)
                
                try:
                    await client.send_message(
                        target_user_id,
                        "🎉 Tabriklaymiz!\n\n"
                        "💎 Sizga 30 kunlik Premium obuna berildi!\n"
                        "♾️ Endi cheksiz rasm yaratishingiz mumkin!"
                    )
                except:
                    pass
                
                await message.reply_text(f"✅ User {target_user_id} ga 30 kunlik Premium berildi!", reply_markup=get_admin_keyboard())
            except:
                await message.reply_text("❌ Noto'g'ri ID!", reply_markup=get_admin_keyboard())
            user_states.pop(ADMIN_ID, None)
            return
        
        elif state == "waiting_ad_message":
            users = get_all_users()
            success = 0
            failed = 0
            
            status_msg = await message.reply_text("📢 Reklama yuborilmoqda...")
            
            for user_id in users:
                try:
                    if message.photo:
                        await client.send_photo(user_id, message.photo.file_id, caption=message.caption)
                    else:
                        await client.send_message(user_id, message.text)
                    success += 1
                    await asyncio.sleep(0.05)
                except:
                    failed += 1
            
            await status_msg.edit_text(
                f"✅ <b>Reklama yuborildi!</b>\n\n"
                f"📊 Yuborildi: <b>{success}</b>\n"
                f"❌ Xatolik: <b>{failed}</b>",
                parse_mode=ParseMode.HTML
            )
            
            await message.reply_text("🏠 Bosh sahifa", reply_markup=get_admin_keyboard())
            user_states.pop(ADMIN_ID, None)
            return
    
    await message.reply_text(
        "❓ Buyruqni tushunmadim.\n"
        "🎨 Rasm yaratish uchun tugmani bosing.",
        reply_markup=get_main_keyboard(user_id)
    )

@app.on_message(filters.photo & filters.private)
async def handle_photo(client, message: Message):
    user_id = message.from_user.id
    
    if user_id == ADMIN_ID and user_states.get(ADMIN_ID) == "waiting_ad_message":
        return
    
    await message.reply_text(
        "📸 Rasm qabul qilindi, lekin men faqat matnli tavsif orqali rasm yarataman.\n"
        "🎨 Rasm yaratish tugmasini bosing va tavsif yuboring."
    )

print("✅ Bot ishga tushdi!")
app.run()
