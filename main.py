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

app = Client("ai_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

BAD_WORDS = ["seks", "sex", "porn", "xxx", "18+", "nude", "naked", "sikish", "sik", "sikmoq", "yalingoch", "yalangoch", "fuck", "fucking", "shit", "bitch", "ass", "dick", "cock", "pussy", "cunt", "whore", "slut", "nigger", "rape", "porno", "pornography", "nsfw", "erotic", "orgasm", "секс", "порно", "голый", "голая", "трахать", "ебать", "блять", "хуй", "пизда", "шлюха", "сиськи"]

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

def reset_daily_limits(user_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("UPDATE users SET image_limit=3, last_reset=? WHERE user_id=? AND premium=0", (now, user_id))
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
    for channel in channels:
        try:
            member = await client.get_chat_member(channel[0], user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except:
            return False
    return True

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
            params = {'client': 'gtx', 'sl': 'auto', 'tl': 'en', 'dt': 't', 'q': text}
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    result = await response.json()
                    translated = ''.join([item[0] for item in result[0]])
                    return translated
        return text
    except:
        return text

async def generate_image(prompt):
    try:
        translated = await translate_to_english(prompt)
        if len(translated) > 200:
            translated = translated[:200]
        enhanced = f"{translated}, masterpiece, high quality, 8k, detailed"
        safe = enhanced.replace(" ", "%20").replace(",", "%2C").replace("'", "%27").replace('"', "%22")
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
                continue
        simple = translated[:100].replace(" ", "%20")
        return f"https://image.pollinations.ai/prompt/{simple}?width=1024&height=1024", translated
    except:
        simple = prompt[:100].replace(" ", "%20")
        return f"https://image.pollinations.ai/prompt/{simple}?width=1024&height=1024", prompt[:100]

user_states = {}

def get_main_keyboard(user_id):
    kb = [[KeyboardButton("🎨 Rasm yaratish")], [KeyboardButton("📊 Statistikam"), KeyboardButton("ℹ️ Yordam")]]
    if user_id == ADMIN_ID:
        kb.append([KeyboardButton("👨‍💼 Admin Panel")])
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def get_admin_keyboard():
    kb = [[KeyboardButton("📊 Barcha statistika")], [KeyboardButton("➕ Kanal qo'shish"), KeyboardButton("➖ Kanal o'chirish")], [KeyboardButton("💎 Premium berish"), KeyboardButton("📢 Reklama yuborish")], [KeyboardButton("👥 Foydalanuvchilar")], [KeyboardButton("🔙 Orqaga")]]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def get_cancel_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("❌ Bekor qilish")]], resize_keyboard=True)

@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    user_id = message.from_user.id
    username = message.from_user.username or "User"
    user_states.pop(user_id, None)
    existing = get_user(user_id)
    if not existing:
        add_user(user_id, username)
    if not await check_subscription(client, user_id):
        channels = get_channels()
        channel_text = "\n".join([f"📢 {ch[1]}" for ch in channels])
        await message.reply_text(f"👋 Salom {username}!\n\n🔐 Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:\n\n{channel_text}\n\n✅ Obuna bo'lgandan keyin /start ni qayta bosing", reply_markup=ReplyKeyboardRemove())
        return
    await message.reply_text(f"👋 Salom {username}!\n\n🎨 Men professional AI rasm yaratish botiman!\n🖼 Har qanday tasvirlangan rasmni yaratib beraman.\n🌐 Har qanday tilda yozishingiz mumkin!\n\n📝 Kerakli bo'limni tanlang:", reply_markup=get_main_keyboard(user_id))

@app.on_message(filters.regex("^🎨 Rasm yaratish$") & filters.private)
async def gen_img_btn(client, message):
    user_id = message.from_user.id
    if not await check_subscription(client, user_id):
        await message.reply_text("❌ Avval kanallarga obuna bo'ling! /start")
        return
    check_and_reset_limits(user_id)
    user = get_user(user_id)
    is_premium = check_premium(user_id)
    if not is_premium and user[2] <= 0:
        await message.reply_text(f"⚠️ Kunlik limitingiz tugadi!\n\n📊 Kunlik limit: 0/3\n💎 Premium obuna olish uchun adminга murojaat qiling", reply_markup=get_main_keyboard(user_id))
        return
    user_states[user_id] = "waiting_image"
    await message.reply_text(f"🎨 <b>Rasm yaratish</b>\n\n📊 Limitlar:\n📅 Kunlik: <b>{user[2]}/3</b>\n💎 Status: <b>{'Premium ♾️' if is_premium else 'Oddiy'}</b>\n\n📝 Rasm uchun tavsif yuboring:\n🌐 Har qanday tilda yozishingiz mumkin!\n\nMisol:\n• <i>tog'lar ustida go'zal quyosh botishi</i>\n• <i>beautiful sunset over mountains</i>\n• <i>красивый закат над горами</i>", parse_mode=ParseMode.HTML, reply_markup=get_cancel_keyboard())

@app.on_message(filters.regex("^📊 Statistikam$") & filters.private)
async def my_stats_btn(client, message):
    user_id = message.from_user.id
    user = get_user(user_id)
    is_premium = check_premium(user_id)
    status = "💎 Premium" if is_premium else "🆓 Oddiy"
    text = f"📊 <b>Sizning statistikangiz:</b>\n\n👤 Status: <b>{status}</b>\n📅 Kunlik limit: <b>{user[2]}/3</b>\n📅 Qo'shilgan: <code>{user[6].split('T')[0]}</code>"
    if is_premium and user[4]:
        text += f"\n⏰ Premium tugash: <code>{user[4].split('T')[0]}</code>"
    await message.reply_text(text, parse_mode=ParseMode.HTML)

@app.on_message(filters.regex("^ℹ️ Yordam$") & filters.private)
async def help_btn(client, message):
    text = "ℹ️ <b>Yordam bo'limi:</b>\n\n🎨 <b>Rasm yaratish:</b>\n• AI professional rasm yaratadi\n• Har qanday tilda yozishingiz mumkin\n• Avtomatik ingliz tiliga tarjima qilinadi\n• Yuqori sifat (1024x1024)\n\n📊 <b>Limitlar:</b>\n• 🆓 Oddiy: 3 rasm/kun\n• 💎 Premium: ♾️ Cheksiz\n\n💡 <b>Maslahatlar:</b>\n• Detallarga e'tibor bering\n• 'realistic', 'detailed', '4k' so'zlarini qo'shing\n• Qisqa va aniq tavsif yuboring\n\n⚠️ <b>Qoidalar:</b>\n• Taqiqlangan so'zlardan foydalanmang\n• Har kuni limit avtomatik yangilanadi"
    await message.reply_text(text, parse_mode=ParseMode.HTML)

@app.on_message(filters.regex("^👨‍💼 Admin Panel$") & filters.private)
async def admin_panel_btn(client, message):
    if message.from_user.id != ADMIN_ID:
        await message.reply_text("❌ Sizda ruxsat yo'q!")
        return
    total, premium = get_stats()
    channels = get_channels()
    text = f"👨‍💼 <b>Admin Panel</b>\n\n👥 Jami foydalanuvchilar: <b>{total}</b>\n💎 Premium: <b>{premium}</b>\n🆓 Oddiy: <b>{total - premium}</b>\n📢 Majburiy kanallar: <b>{len(channels)}</b>"
    await message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=get_admin_keyboard())

@app.on_message(filters.regex("^📊 Barcha statistika$") & filters.private)
async def admin_stats_btn(client, message):
    if message.from_user.id != ADMIN_ID:
        return
    total, premium = get_stats()
    channels = get_channels()
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE date(join_date) = date('now')")
    today = c.fetchone()[0]
    conn.close()
    text = f"📊 <b>Umumiy statistika:</b>\n\n👥 Jami foydalanuvchilar: <b>{total}</b>\n💎 Premium: <b>{premium}</b>\n🆓 Oddiy: <b>{total - premium}</b>\n📢 Majburiy kanallar: <b>{len(channels)}</b>\n🆕 Bugungi yangi: <b>{today}</b>"
    await message.reply_text(text, parse_mode=ParseMode.HTML)

@app.on_message(filters.regex("^👥 Foydalanuuvchilar$") & filters.private)
async def users_list_btn(client, message):
    if message.from_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT user_id, username, premium, image_limit, join_date FROM users ORDER BY join_date DESC LIMIT 30")
    users = c.fetchall()
    conn.close()
    text = "👥 <b>Oxirgi 30 ta foydalanuvchi:</b>\n\n"
    for u in users:
        st = "💎" if u[2] == 1 else "🆓"
        un = u[1] if u[1] else "NoUser"
        jd = u[4].split("T")[0]
        text += f"{st} <code>{u[0]}</code> | @{un} | 📊{u[3]}/3 | {jd}\n"
    await message.reply_text(text, parse_mode=ParseMode.HTML)

@app.on_message(filters.regex("^➕ Kanal qo'shish$") & filters.private)
async def add_ch_btn(client, message):
    if message.from_user.id != ADMIN_ID:
        return
    user_states[ADMIN_ID] = "add_channel"
    await message.reply_text("➕ <b>Kanal qo'shish:</b>\n\nKanal username yoki ID yuboring\nMisol: <code>@channelname</code> yoki <code>-1001234567890</code>", parse_mode=ParseMode.HTML, reply_markup=get_cancel_keyboard())

@app.on_message(filters.regex("^➖ Kanal o'chirish$") & filters.private)
async def rem_ch_btn(client, message):
    if message.from_user.id != ADMIN_ID:
        return
    channels = get_channels()
    if not channels:
        await message.reply_text("❌ Kanallar yo'q!", reply_markup=get_admin_keyboard())
        return
    user_states[ADMIN_ID] = "remove_channel"
    text = "➖ <b>Kanal o'chirish:</b>\n\nKanal ID yuboring:\n\n"
    for ch in channels:
        text += f"📢 {ch[1]} - <code>{ch[0]}</code>\n"
    await message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=get_cancel_keyboard())

@app.on_message(filters.regex("^💎 Premium berish$") & filters.private)
async def give_prem_btn(client, message):
    if message.from_user.id != ADMIN_ID:
        return
    user_states[ADMIN_ID] = "give_premium"
    await message.reply_text("💎 <b>Premium berish:</b>\n\nFoydalanuvchi ID yuboring\nMisol: <code>123456789</code>", parse_mode=ParseMode.HTML, reply_markup=get_cancel_keyboard())

@app.on_message(filters.regex("^📢 Reklama yuborish$") & filters.private)
async def send_ad_btn(client, message):
    if message.from_user.id != ADMIN_ID:
        return
    user_states[ADMIN_ID] = "send_ad"
    await message.reply_text("📢 <b>Reklama yuborish:</b>\n\nXabar yuboring (matn yoki rasm + matn)", parse_mode=ParseMode.HTML, reply_markup=get_cancel_keyboard())

@app.on_message(filters.regex("^🔙 Orqaga$") & filters.private)
async def back_btn(client, message):
    user_id = message.from_user.id
    user_states.pop(user_id, None)
    await message.reply_text("🏠 Bosh sahifa", reply_markup=get_main_keyboard(user_id))

@app.on_message(filters.regex("^❌ Bekor qilish$") & filters.private)
async def cancel_btn(client, message):
    user_id = message.from_user.id
    user_states.pop(user_id, None)
    if user_id == ADMIN_ID:
        await message.reply_text("❌ Bekor qilindi", reply_markup=get_admin_keyboard())
    else:
        await message.reply_text("❌ Bekor qilindi", reply_markup=get_main_keyboard(user_id))

@app.on_message(filters.text & filters.private)
async def handle_text(client, message):
    user_id = message.from_user.id
    if not await check_subscription(client, user_id):
        await message.reply_text("❌ Avval kanallarga obuna bo'ling! /start")
        return
    if contains_bad_words(message.text):
        await message.reply_text("⚠️ Taqiqlangan so'zdan foydalanmang!")
        return
    state = user_states.get(user_id)
    if state == "waiting_image":
        check_and_reset_limits(user_id)
        user = get_user(user_id)
        is_premium = check_premium(user_id)
        if not is_premium and user[2] <= 0:
            await message.reply_text("⚠️ Limitingiz tugadi!", reply_markup=get_main_keyboard(user_id))
            user_states.pop(user_id, None)
            return
        wait = await message.reply_text("🎨 Rasm tayyorlanmoqda...\n⏳ Iltimos kutib turing...")
        try:
            url, trans = await generate_image(message.text)
            await message.reply_photo(photo=url, caption=f"✅ <b>Rasm tayyor!</b>\n\n📝 Sizning matningiz:\n<i>{message.text[:150]}</i>\n\n🌐 Ingliz tiliga:\n<i>{trans[:150]}</i>", parse_mode=ParseMode.HTML)
            if not is_premium:
                conn = sqlite3.connect('database.db')
                c = conn.cursor()
                c.execute("UPDATE users SET image_limit = image_limit - 1 WHERE user_id=?", (user_id,))
                conn.commit()
                conn.close()
                upd = get_user(user_id)
                await message.reply_text(f"📊 Qolgan limit: <b>{upd[2]}/3</b>", parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(user_id))
            else:
                await message.reply_text("✅ Premium - cheksiz!", reply_markup=get_main_keyboard(user_id))
            try:
                await wait.delete()
            except:
                pass
        except:
            try:
                await wait.delete()
            except:
                pass
            await message.reply_text("🔄 Xatolik yuz berdi. Iltimos qayta urinib ko'ring.", reply_markup=get_main_keyboard(user_id))
        user_states.pop(user_id, None)
        return
    elif user_id == ADMIN_ID:
        if state == "add_channel":
            try:
                ch_user = message.text.strip()
                chat = await client.get_chat(ch_user)
                add_channel(str(chat.id), ch_user)
                await message.reply_text(f"✅ Kanal qo'shildi: {ch_user}", reply_markup=get_admin_keyboard())
            except Exception as e:
                await message.reply_text(f"❌ Xatolik: {str(e)}", reply_markup=get_admin_keyboard())
            user_states.pop(ADMIN_ID, None)
            return
        elif state == "remove_channel":
            try:
                ch_id = message.text.strip()
                remove_channel(ch_id)
                await message.reply_text("✅ Kanal o'chirildi!", reply_markup=get_admin_keyboard())
            except:
                await message.reply_text("❌ Xatolik yuz berdi!", reply_markup=get_admin_keyboard())
            user_states.pop(ADMIN_ID, None)
            return
        elif state == "give_premium":
            try:
                uid = int(message.text.strip())
                set_premium(uid, 30)
                try:
                    await client.send_message(uid, "🎉 Tabriklaymiz!\n\n💎 Sizga 30 kunlik Premium obuna berildi!\n♾️ Endi cheksiz rasm yaratishingiz mumkin!")
                except:
                    pass
                await message.reply_text(f"✅ User {uid} ga Premium berildi!", reply_markup=get_admin_keyboard())
            except:
                await message.reply_text("❌ Noto'g'ri ID!", reply_markup=get_admin_keyboard())
            user_states.pop(ADMIN_ID, None)
            return
        elif state == "send_ad":
            users = get_all_users()
            success = 0
            failed = 0
            status = await message.reply_text("📢 Reklama yuborilmoqda...")
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
            await status.edit_text(f"✅ <b>Reklama yuborildi!</b>\n\n📊 Yuborildi: <b>{success}</b>\n❌ Xatolik: <b>{failed}</b>", parse_mode=ParseMode.HTML)
            await message.reply_text("🏠 Bosh sahifa", reply_markup=get_admin_keyboard())
            user_states.pop(ADMIN_ID, None)
            return
    await message.reply_text("❓ Buyruqni tushunmadim.\n🎨 Rasm yaratish tugmasini bosing.", reply_markup=get_main_keyboard(user_id))

@app.on_message(filters.photo & filters.private)
async def handle_photo(client, message):
    user_id = message.from_user.id
    if user_id == ADMIN_ID and user_states.get(ADMIN_ID) == "send_ad":
        return
    await message.reply_text("📸 Rasm qabul qilindi.\n\n🎨 Men faqat matnli tavsif orqali rasm yarataman.\nRasm yaratish tugmasini bosing va tavsif yuboring.")

print("✅ Bot ishga tushdi!")
app.run()
