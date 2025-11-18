import os
import sqlite3
import asyncio
import aiohttp
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.enums import ParseMode
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

app = Client(
    "ai_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

BAD_WORDS = [
    "jinsi", "jinsiy", "seks", "sex", "porn", "xxx", 
    "qiziqaman", "yotsex", "18+", "fuck", "shit"
]

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
    c.execute('''CREATE TABLE IF NOT EXISTS ads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message TEXT,
        photo TEXT,
        button_text TEXT,
        button_url TEXT
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
    c.execute("INSERT OR IGNORE INTO users VALUES (?,?,3,100,0,NULL,?,?)",
              (user_id, username, now, now))
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
    c.execute("UPDATE users SET image_limit=3, chat_limit=100, last_reset=? WHERE user_id=? AND premium=0",
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

async def generate_image_pollinations(prompt):
    try:
        safe_prompt = prompt.replace(" ", "%20")
        image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                if response.status == 200:
                    return image_url
        return None
    except Exception as e:
        print(f"Image generation error: {e}")
        return None

user_states = {}

@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Foydalanuvchi"
    
    user_states.pop(user_id, None)
    
    add_user(user_id, username)
    
    if not await check_subscription(client, user_id):
        channels = get_channels()
        keyboard = []
        for channel in channels:
            keyboard.append([InlineKeyboardButton(f"📢 {channel[1]}", url=f"https://t.me/{channel[1].replace('@', '')}")])
        keyboard.append([InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_sub")])
        
        await message.reply_text(
            f"👋 Salom {username}!\n\n"
            "🔐 Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎨 Rasm yaratish", callback_data="generate_image"),
         InlineKeyboardButton("💬 AI Chat", callback_data="ai_chat")],
        [InlineKeyboardButton("📊 Statistika", callback_data="my_stats"),
         InlineKeyboardButton("ℹ️ Yordam", callback_data="help")]
    ])
    
    if user_id == ADMIN_ID:
        keyboard.inline_keyboard.append([InlineKeyboardButton("👨‍💼 Admin Panel", callback_data="admin_panel")])
    
    await message.reply_text(
        f"👋 Salom {username}!\n\n"
        "🤖 Men sizning AI yordamchingizman!\n"
        "🎨 Rasm yaratish va 💬 AI chat xizmatlarim mavjud.\n\n"
        "📝 Kerakli bo'limni tanlang:",
        reply_markup=keyboard
    )

@app.on_message(filters.command("cancel"))
async def cancel_command(client, message: Message):
    user_id = message.from_user.id
    user_states.pop(user_id, None)
    await message.reply_text("❌ Bekor qilindi. /start ni bosing.")

@app.on_callback_query(filters.regex("check_sub"))
async def check_sub_callback(client, callback_query):
    user_id = callback_query.from_user.id
    
    if await check_subscription(client, user_id):
        await callback_query.message.delete()
        await start_command(client, callback_query.message)
    else:
        await callback_query.answer("❌ Siz hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)

@app.on_callback_query(filters.regex("generate_image"))
async def generate_image_callback(client, callback_query):
    user_id = callback_query.from_user.id
    check_and_reset_limits(user_id)
    
    user = get_user(user_id)
    is_premium = check_premium(user_id)
    
    if not is_premium and user[2] <= 0:
        await callback_query.answer(
            "⚠️ Kunlik limitingiz tugadi!\n💎 Premium obunani xarid qiling.",
            show_alert=True
        )
        return
    
    user_states[user_id] = "waiting_image_prompt"
    
    await callback_query.message.edit_text(
        "🎨 Rasm yaratish uchun tavsif yuboring:\n\n"
        f"📊 Qolgan limitingiz: {user[2] if not is_premium else '♾️ Cheksiz'}\n\n"
        "Misol: 'a beautiful sunset over mountains'\n"
        "❌ Bekor qilish: /cancel"
    )
    await callback_query.answer()

@app.on_callback_query(filters.regex("ai_chat"))
async def ai_chat_callback(client, callback_query):
    user_id = callback_query.from_user.id
    check_and_reset_limits(user_id)
    
    user = get_user(user_id)
    is_premium = check_premium(user_id)
    
    if not is_premium and user[3] <= 0:
        await callback_query.answer(
            "⚠️ Kunlik limitingiz tugadi!\n💎 Premium obunani xarid qiling.",
            show_alert=True
        )
        return
    
    user_states[user_id] = "ai_chat"
    
    await callback_query.message.edit_text(
        "💬 AI Chat rejimi yoqildi!\n\n"
        f"📊 Qolgan limitingiz: {user[3] if not is_premium else '♾️ Cheksiz'}\n\n"
        "Savolingizni yuboring:\n"
        "❌ Bekor qilish: /cancel"
    )
    await callback_query.answer()

@app.on_callback_query(filters.regex("my_stats"))
async def my_stats_callback(client, callback_query):
    user_id = callback_query.from_user.id
    user = get_user(user_id)
    is_premium = check_premium(user_id)
    
    status = "💎 Premium" if is_premium else "🆓 Oddiy"
    premium_until = "N/A" if not is_premium else user[5].split("T")[0]
    
    text = (
        f"📊 <b>Sizning statistikangiz:</b>\n\n"
        f"👤 Status: {status}\n"
        f"🎨 Rasm limiti: {user[2] if not is_premium else '♾️'}\n"
        f"💬 Chat limiti: {user[3] if not is_premium else '♾️'}\n"
        f"📅 Qo'shilgan sana: {user[7].split('T')[0]}\n"
    )
    
    if is_premium:
        text += f"⏰ Premium amal qilish: {premium_until}"
    
    await callback_query.message.edit_text(text, parse_mode=ParseMode.HTML)
    await callback_query.answer()

@app.on_callback_query(filters.regex("help"))
async def help_callback(client, callback_query):
    text = (
        "ℹ️ <b>Yordam bo'limi:</b>\n\n"
        "🎨 <b>Rasm yaratish:</b> Tavsif yuboring va AI rasm yaratadi\n"
        "💬 <b>AI Chat:</b> Har qanday savolingizga javob beradi\n\n"
        "📊 <b>Limitlar (kunlik):</b>\n"
        "🆓 Oddiy: 3 rasm, 100 chat\n"
        "💎 Premium: Cheksiz\n\n"
        "⚠️ Taqiqlangan so'zlardan foydalanmang!"
    )
    await callback_query.message.edit_text(text, parse_mode=ParseMode.HTML)
    await callback_query.answer()

@app.on_callback_query(filters.regex("admin_panel"))
async def admin_panel_callback(client, callback_query):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ Sizda ruxsat yo'q!", show_alert=True)
        return
    
    total_users, premium_users = get_stats()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton("➕ Kanal qo'shish", callback_data="add_channel"),
         InlineKeyboardButton("➖ Kanal o'chirish", callback_data="remove_channel")],
        [InlineKeyboardButton("💎 Premium berish", callback_data="give_premium")],
        [InlineKeyboardButton("📢 Reklama yuborish", callback_data="send_ad")]
    ])
    
    await callback_query.message.edit_text(
        f"👨‍💼 <b>Admin Panel</b>\n\n"
        f"👥 Jami foydalanuvchilar: {total_users}\n"
        f"💎 Premium foydalanuvchilar: {premium_users}",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await callback_query.answer()

@app.on_callback_query(filters.regex("admin_stats"))
async def admin_stats_callback(client, callback_query):
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    total_users, premium_users = get_stats()
    channels = get_channels()
    
    text = (
        f"📊 <b>Umumiy statistika:</b>\n\n"
        f"👥 Jami foydalanuvchilar: {total_users}\n"
        f"💎 Premium: {premium_users}\n"
        f"🆓 Oddiy: {total_users - premium_users}\n"
        f"📢 Majburiy kanallar: {len(channels)}"
    )
    
    await callback_query.answer(text, show_alert=True)

@app.on_callback_query(filters.regex("add_channel"))
async def add_channel_callback(client, callback_query):
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    user_states[ADMIN_ID] = "waiting_channel_add"
    await callback_query.message.edit_text(
        "➕ Kanal qo'shish:\n\n"
        "Kanal username yoki ID yuboring\n"
        "Misol: @channelname\n"
        "❌ Bekor qilish: /cancel"
    )
    await callback_query.answer()

@app.on_callback_query(filters.regex("remove_channel"))
async def remove_channel_callback(client, callback_query):
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    channels = get_channels()
    if not channels:
        await callback_query.answer("❌ Kanallar yo'q!", show_alert=True)
        return
    
    user_states[ADMIN_ID] = "waiting_channel_remove"
    text = "➖ Kanal o'chirish:\n\nKanal ID yuboring:\n\n"
    for ch in channels:
        text += f"📢 {ch[1]} - ID: {ch[0]}\n"
    text += "\n❌ Bekor qilish: /cancel"
    
    await callback_query.message.edit_text(text)
    await callback_query.answer()

@app.on_callback_query(filters.regex("give_premium"))
async def give_premium_callback(client, callback_query):
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    user_states[ADMIN_ID] = "waiting_premium_user"
    await callback_query.message.edit_text(
        "💎 Premium berish:\n\n"
        "Foydalanuvchi ID yuboring\n"
        "❌ Bekor qilish: /cancel"
    )
    await callback_query.answer()

@app.on_callback_query(filters.regex("send_ad"))
async def send_ad_callback(client, callback_query):
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    user_states[ADMIN_ID] = "waiting_ad_message"
    await callback_query.message.edit_text(
        "📢 Reklama yuborish:\n\n"
        "Xabar yuboring (matn yoki rasm)\n"
        "❌ Bekor qilish: /cancel"
    )
    await callback_query.answer()

@app.on_message(filters.text & filters.private)
async def handle_messages(client, message: Message):
    user_id = message.from_user.id
    
    if not await check_subscription(client, user_id):
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
            await message.reply_text("⚠️ Kunlik limitingiz tugadi!")
            user_states.pop(user_id, None)
            return
        
        wait_msg = await message.reply_text("🎨 Rasm yaratilmoqda, iltimos kuting...")
        
        try:
            image_url = await generate_image_pollinations(message.text)
            
            if image_url:
                await message.reply_photo(
                    photo=image_url,
                    caption=f"🎨 Rasm tayyor!\n📝 Tavsif: {message.text}"
                )
                
                if not is_premium:
                    update_limits(user_id, image_limit=user[2]-1)
                    remaining = user[2] - 1
                    await message.reply_text(f"✅ Qolgan limit: {remaining}")
            else:
                await message.reply_text("❌ Rasm yaratishda xatolik yuz berdi. Qaytadan urinib ko'ring.")
            
            await wait_msg.delete()
        except Exception as e:
            await wait_msg.delete()
            await message.reply_text("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")
        
        user_states.pop(user_id, None)
        return
    
    elif state == "ai_chat":
        check_and_reset_limits(user_id)
        user = get_user(user_id)
        is_premium = check_premium(user_id)
        
        if not is_premium and user[3] <= 0:
            await message.reply_text("⚠️ Kunlik chat limitingiz tugadi!")
            user_states.pop(user_id, None)
            return
        
        try:
            response = model.generate_content(message.text)
            await message.reply_text(f"🤖 {response.text}")
            
            if not is_premium:
                update_limits(user_id, chat_limit=user[3]-1)
        except Exception as e:
            await message.reply_text("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")
        return
    
    elif user_id == ADMIN_ID:
        if state == "waiting_channel_add":
            try:
                channel_username = message.text.strip()
                chat = await client.get_chat(channel_username)
                add_channel(str(chat.id), channel_username)
                await message.reply_text(f"✅ Kanal qo'shildi: {channel_username}")
            except Exception as e:
                await message.reply_text(f"❌ Xatolik: {str(e)}")
            user_states.pop(ADMIN_ID, None)
            return
        
        elif state == "waiting_channel_remove":
            try:
                channel_id = message.text.strip()
                remove_channel(channel_id)
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
            for user in users:
                try:
                    await client.send_message(user[0], message.text)
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
    
    if not is_premium and user[3] <= 0:
        await message.reply_text("⚠️ Kunlik chat limitingiz tugadi! 💎 Premium oling.")
        return
    
    try:
        response = model.generate_content(message.text)
        await message.reply_text(f"🤖 {response.text}")
        
        if not is_premium:
            update_limits(user_id, chat_limit=user[3]-1)
    except Exception as e:
        await message.reply_text("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")

print("✅ Bot ishga tushdi!")
app.run()
