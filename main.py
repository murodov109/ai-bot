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
    for attempt in range(3):
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://translate.googleapis.com/translate_a/single"
                params = {'client': 'gtx', 'sl': 'auto', 'tl': 'en', 'dt': 't', 'q': text}
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=8)) as response:
                    if response.status == 200:
                        result = await response.json()
                        translated = ''.join([item[0] for item in result[0]])
                        return translated
        except:
            if attempt < 2:
                await asyncio.sleep(1)
            continue
    return text

async def generate_image_ultimate(prompt):
    translated = await translate_to_english(prompt)
    print(f"📝 Original: {prompt}")
    print(f"🌐 Translated: {translated}")
    
    if len(translated) > 180:
        translated = translated[:180]
    
    enhanced = f"{translated}, masterpiece, high quality, 8k, professional, detailed"
    safe = enhanced.replace(" ", "%20").replace(",", "%2C").replace("'", "%27").replace('"', "%22").replace("!", "%21").replace("?", "%3F")
    
    api_variants = [
        f"https://image.pollinations.ai/prompt/{safe}?width=1024&height=1024&nologo=true&enhance=true&seed={abs(hash(prompt)) % 10000}",
        f"https://pollinations.ai/p/{safe}?width=1024&height=1024&nologo=true&seed={abs(hash(prompt)) % 10000}",
        f"https://image.pollinations.ai/prompt/{safe}?width=1024&height=1024&enhance=true",
        f"https://image.pollinations.ai/prompt/{safe}?width=1024&height=1024&nologo=true",
        f"https://pollinations.ai/p/{safe}?width=1024&height=1024",
        f"https://image.pollinations.ai/prompt/{translated.replace(' ', '%20')}?width=1024&height=1024"
    ]
    
    for i, url in enumerate(api_variants):
        try:
            print(f"🔄 Trying API {i+1}/{len(api_variants)}")
            async with aiohttp.ClientSession() as session:
                async with session.head(url, timeout=aiohttp.ClientTimeout(total=8)) as response:
                    if response.status == 200:
                        print(f"✅ Success with API {i+1}")
                        return url, translated
        except Exception as e:
            print(f"❌ API {i+1} failed: {e}")
            if i < len(api_variants) - 1:
                await asyncio.sleep(0.5)
            continue
    
    simple = translated[:80].replace(" ", "%20")
    fallback = f"https://image.pollinations.ai/prompt/{simple}"
    print(f"⚠️ Using fallback URL")
    return fallback, translated

user_states = {}

def get_main_keyboard(user_id):
    kb = [[KeyboardButton("🎨 Rasm yaratish")], [KeyboardButton("📊 Statistikam"), KeyboardButton("ℹ️ Yordam")]]
    if user_id == ADMIN_ID:
        kb.append([KeyboardButton("👨‍💼 Admin Panel")])
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def get_admin_keyboard():
    kb = [[KeyboardButton("📊 Statistika")], [KeyboardButton("➕ Kanal"), KeyboardButton("➖ Kanal")], [KeyboardButton("💎 Premium"), KeyboardButton("📢 Reklama")], [KeyboardButton("👥 Users")], [KeyboardButton("🔙 Orqaga")]]
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
    
    if not await check_subscription(client, user_id):
        channels = get_channels()
        ch_text = "\n".join([f"📢 {ch[1]}" for ch in channels])
        await message.reply_text(f"👋 Salom {username}!\n\n🔐 Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:\n\n{ch_text}\n\n✅ Obuna bo'lgandan keyin /start ni bosing", reply_markup=ReplyKeyboardRemove())
        return
    
    await message.reply_text(f"👋 Salom {username}!\n\n🎨 Men professional AI rasm yaratish botiman!\n🖼 Har qanday rasmni yaratib beraman\n🌐 Har qanday tilda yozing!\n\n📝 Tugmani tanlang:", reply_markup=get_main_keyboard(user_id))

@app.on_message(filters.regex("^🎨 Rasm yaratish$") & filters.private)
async def gen_img(client, message):
    user_id = message.from_user.id
    
    if not await check_subscription(client, user_id):
        await message.reply_text("❌ Kanallarga obuna bo'ling! /start")
        return
    
    check_and_reset_limits(user_id)
    user = get_user(user_id)
    is_premium = check_premium(user_id)
    
    if not is_premium and user[2] <= 0:
        await message.reply_text(f"⚠️ Kunlik limit tugadi!\n\n📊 Limit: 0/3\n💎 Premium uchun adminга murojaat qiling", reply_markup=get_main_keyboard(user_id))
        return
    
    user_states[user_id] = "wait_img"
    await message.reply_text(f"🎨 <b>Rasm yaratish</b>\n\n📊 Limit: <b>{user[2]}/3</b>\n💎 Status: <b>{'Premium' if is_premium else 'Oddiy'}</b>\n\n📝 Rasm tavsifini yuboring:\n\nMisol:\n• go'zal manzara\n• beautiful landscape\n• красивый пейзаж", parse_mode=ParseMode.HTML, reply_markup=get_cancel_keyboard())

@app.on_message(filters.regex("^📊 Statistikam$") & filters.private)
async def stats(client, message):
    user_id = message.from_user.id
    user = get_user(user_id)
    is_premium = check_premium(user_id)
    
    status = "💎 Premium" if is_premium else "🆓 Oddiy"
    text = f"📊 <b>Statistika:</b>\n\n👤 Status: <b>{status}</b>\n📅 Limit: <b>{user[2]}/3</b>\n📅 Sana: <code>{user[6].split('T')[0]}</code>"
    
    if is_premium and user[4]:
        text += f"\n⏰ Premium: <code>{user[4].split('T')[0]}</code>"
    
    await message.reply_text(text, parse_mode=ParseMode.HTML)

@app.on_message(filters.regex("^ℹ️ Yordam$") & filters.private)
async def help_cmd(client, message):
    text = "ℹ️ <b>Yordam:</b>\n\n🎨 <b>Rasm yaratish:</b>\n• AI professional rasm yaratadi\n• Har qanday tilda\n• 1024x1024 sifat\n\n📊 <b>Limitlar:</b>\n• Oddiy: 3/kun\n• Premium: Cheksiz\n\n💡 <b>Maslahat:</b>\n• Qisqa va aniq yozing\n• Detallarga e'tibor bering"
    await message.reply_text(text, parse_mode=ParseMode.HTML)

@app.on_message(filters.regex("^👨‍💼 Admin Panel$") & filters.private)
async def admin_panel(client, message):
    if message.from_user.id != ADMIN_ID:
        return
    total, premium = get_stats()
    channels = get_channels()
    text = f"👨‍💼 <b>Admin</b>\n\n👥 Users: <b>{total}</b>\n💎 Premium: <b>{premium}</b>\n📢 Channels: <b>{len(channels)}</b>"
    await message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=get_admin_keyboard())

@app.on_message(filters.regex("^📊 Statistika$") & filters.private)
async def admin_stats(client, message):
    if message.from_user.id != ADMIN_ID:
        return
    total, premium = get_stats()
    channels = get_channels()
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE date(join_date) = date('now')")
    today = c.fetchone()[0]
    conn.close()
    text = f"📊 <b>Stats:</b>\n\n👥 Total: <b>{total}</b>\n💎 Premium: <b>{premium}</b>\n🆕 Today: <b>{today}</b>\n📢 Channels: <b>{len(channels)}</b>"
    await message.reply_text(text, parse_mode=ParseMode.HTML)

@app.on_message(filters.regex("^👥 Users$") & filters.private)
async def users_list(client, message):
    if message.from_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT user_id, username, premium, image_limit FROM users ORDER BY join_date DESC LIMIT 30")
    users = c.fetchall()
    conn.close()
    text = "👥 <b>Users (30):</b>\n\n"
    for u in users:
        st = "💎" if u[2] == 1 else "🆓"
        un = u[1] if u[1] else "NoUser"
        text += f"{st} <code>{u[0]}</code> | @{un} | {u[3]}/3\n"
    await message.reply_text(text, parse_mode=ParseMode.HTML)

@app.on_message(filters.regex("^➕ Kanal$") & filters.private)
async def add_ch(client, message):
    if message.from_user.id != ADMIN_ID:
        return
    user_states[ADMIN_ID] = "add_ch"
    await message.reply_text("➕ <b>Kanal:</b>\n\nUsername yuboring\n<code>@channel</code>", parse_mode=ParseMode.HTML, reply_markup=get_cancel_keyboard())

@app.on_message(filters.regex("^➖ Kanal$") & filters.private)
async def rem_ch(client, message):
    if message.from_user.id != ADMIN_ID:
        return
    channels = get_channels()
    if not channels:
        await message.reply_text("❌ Yo'q!", reply_markup=get_admin_keyboard())
        return
    user_states[ADMIN_ID] = "rem_ch"
    text = "➖ <b>Kanal:</b>\n\nID:\n\n"
    for ch in channels:
        text += f"📢 {ch[1]} - <code>{ch[0]}</code>\n"
    await message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=get_cancel_keyboard())

@app.on_message(filters.regex("^💎 Premium$") & filters.private)
async def give_prem(client, message):
    if message.from_user.id != ADMIN_ID:
        return
    user_states[ADMIN_ID] = "give_prem"
    await message.reply_text("💎 <b>Premium:</b>\n\nUser ID\n<code>123456</code>", parse_mode=ParseMode.HTML, reply_markup=get_cancel_keyboard())

@app.on_message(filters.regex("^📢 Reklama$") & filters.private)
async def send_ad(client, message):
    if message.from_user.id != ADMIN_ID:
        return
    user_states[ADMIN_ID] = "send_ad"
    await message.reply_text("📢 <b>Ad:</b>\n\nXabar", parse_mode=ParseMode.HTML, reply_markup=get_cancel_keyboard())

@app.on_message(filters.regex("^🔙 Orqaga$") & filters.private)
async def back(client, message):
    user_id = message.from_user.id
    user_states.pop(user_id, None)
    await message.reply_text("🏠 Menu", reply_markup=get_main_keyboard(user_id))

@app.on_message(filters.regex("^❌ Bekor qilish$") & filters.private)
async def cancel(client, message):
    user_id = message.from_user.id
    user_states.pop(user_id, None)
    kb = get_admin_keyboard() if user_id == ADMIN_ID else get_main_keyboard(user_id)
    await message.reply_text("❌ Bekor qilindi", reply_markup=kb)

@app.on_message(filters.text & filters.private)
async def handle_text(client, message):
    user_id = message.from_user.id
    
    if not await check_subscription(client, user_id):
        await message.reply_text("❌ Kanallarga obuna bo'ling! /start")
        return
    
    if contains_bad_words(message.text):
        await message.reply_text("⚠️ Taqiqlangan so'z!")
        return
    
    state = user_states.get(user_id)
    
    if state == "wait_img":
        check_and_reset_limits(user_id)
        user = get_user(user_id)
        is_premium = check_premium(user_id)
        
        if not is_premium and user[2] <= 0:
            await message.reply_text("⚠️ Limit tugadi!", reply_markup=get_main_keyboard(user_id))
            user_states.pop(user_id, None)
            return
        
        wait_msg = await message.reply_text("🎨 Rasm yaratilmoqda...")
        
        url, trans = await generate_image_ultimate(message.text)
        
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                await message.reply_photo(
                    photo=url,
                    caption=f"✅ <b>Tayyor!</b>\n\n📝 <i>{message.text[:120]}</i>\n\n🌐 <i>{trans[:120]}</i>",
                    parse_mode=ParseMode.HTML
                )
                
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
                    await wait_msg.delete()
                except:
                    pass
                break
                
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_attempts - 1:
                    await asyncio.sleep(2)
                    url, trans = await generate_image_ultimate(message.text)
                else:
                    try:
                        await wait_msg.delete()
                    except:
                        pass
                    
                    simple = message.text[:50].replace(" ", "%20")
                    backup_url = f"https://image.pollinations.ai/prompt/{simple}?width=512&height=512"
                    
                    try:
                        await message.reply_photo(photo=backup_url, caption=f"✅ Tayyor!\n\n📝 {message.text[:100]}", parse_mode=ParseMode.HTML)
                        
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
                    except:
                        await message.reply_text("✅ Rasm tayyor!\n\n🔗 " + backup_url, reply_markup=get_main_keyboard(user_id))
        
        user_states.pop(user_id, None)
        return
    
    elif user_id == ADMIN_ID:
        if state == "add_ch":
            try:
                ch = message.text.strip()
                chat = await client.get_chat(ch)
                add_channel(str(chat.id), ch)
                await message.reply_text(f"✅ Qo'shildi: {ch}", reply_markup=get_admin_keyboard())
            except Exception as e:
                await message.reply_text(f"❌ Xato: {str(e)}", reply_markup=get_admin_keyboard())
            user_states.pop(ADMIN_ID, None)
            return
        elif state == "rem_ch":
            try:
                remove_channel(message.text.strip())
                await message.reply_text("✅ O'chirildi!", reply_markup=get_admin_keyboard())
            except:
                await message.reply_text("❌ Xato!", reply_markup=get_admin_keyboard())
            user_states.pop(ADMIN_ID, None)
            return
        elif state == "give_prem":
            try:
                uid = int(message.text.strip())
                set_premium(uid, 30)
                try:
                    await client.send_message(uid, "🎉 Tabriklaymiz!\n\n💎 30 kunlik Premium!\n♾️ Cheksiz rasm!")
                except:
                    pass
                await message.reply_text(f"✅ {uid} Premium!", reply_markup=get_admin_keyboard())
            except:
                await message.reply_text("❌ Xato ID!", reply_markup=get_admin_keyboard())
            user_states.pop(ADMIN_ID, None)
            return
        elif state == "send_ad":
            users = get_all_users()
            success = 0
            failed = 0
            status = await message.reply_text("📢 Yuborilmoqda...")
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
            await status.edit_text(f"✅ <b>Yuborildi!</b>\n\n📊 OK: <b>{success}</b>\n❌ Fail: <b>{failed}</b>", parse_mode=ParseMode.HTML)
            await message.reply_text("🏠 Menu", reply_markup=get_admin_keyboard())
            user_states.pop(ADMIN_ID, None)
            return
    
    await message.reply_text("❓ Tushunmadim.\n🎨 Tugmani bosing.", reply_markup=get_main_keyboard(user_id))

@app.on_message(filters.photo & filters.private)
async def handle_photo(client, message):
    user_id = message.from_user.id
    if user_id == ADMIN_ID and user_states.get(ADMIN_ID) == "send_ad":
        return
    await message.reply_text("📸 Men faqat matnli tavsif qabul qilaman.\n🎨 Rasm yaratish tugmasini bosing.")

print("✅ Bot ishga tushdi!")
app.run()
