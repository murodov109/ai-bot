import sqlite3
import asyncio
from pyrogram import filters
from pyrogram.types import ReplyKeyboardMarkup, KeyboardButton, Message
from pyrogram.enums import ParseMode

user_states = {}

def get_admin_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📊 Barcha statistika")],
        [KeyboardButton("➕ Kanal qo'shish"), KeyboardButton("➖ Kanal o'chirish")],
        [KeyboardButton("💎 Premium berish"), KeyboardButton("📢 Reklama yuborish")],
        [KeyboardButton("👥 Foydalanuvchilar")],
        [KeyboardButton("🔙 Orqaga")]
    ], resize_keyboard=True)

def get_cancel_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("❌ Bekor qilish")]], resize_keyboard=True)

def get_main_keyboard(user_id):
    kb = [[KeyboardButton("🎨 Rasm yaratish")], [KeyboardButton("📊 Statistikam"), KeyboardButton("ℹ️ Yordam")]]
    if user_id:
        kb.append([KeyboardButton("👨‍💼 Admin Panel")])
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def get_stats():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE premium=1")
    premium = c.fetchone()[0]
    conn.close()
    return total, premium

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

def set_premium(user_id, days=30):
    from datetime import datetime, timedelta
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    until = (datetime.now() + timedelta(days=days)).isoformat()
    c.execute("UPDATE users SET premium=1, premium_until=? WHERE user_id=?", (until, user_id))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = c.fetchall()
    conn.close()
    return [u[0] for u in users]

def setup_admin_handlers(app, ADMIN_ID):
    
    @app.on_message(filters.regex("^👨‍💼 Admin Panel$") & filters.private)
    async def admin_panel(client, message):
        if message.from_user.id != ADMIN_ID:
            return
        
        total, premium = get_stats()
        channels = get_channels()
        await message.reply_text(
            f"👨‍💼 <b>Admin Panel</b>\n\n"
            f"👥 Users: <b>{total}</b>\n"
            f"💎 Premium: <b>{premium}</b>\n"
            f"📢 Channels: <b>{len(channels)}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_admin_keyboard()
        )
    
    @app.on_message(filters.regex("^📊 Barcha statistika$") & filters.private)
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
        
        await message.reply_text(
            f"📊 <b>Stats:</b>\n\n"
            f"👥 Total: <b>{total}</b>\n"
            f"💎 Premium: <b>{premium}</b>\n"
            f"🆕 Today: <b>{today}</b>\n"
            f"📢 Channels: <b>{len(channels)}</b>",
            parse_mode=ParseMode.HTML
        )
    
    @app.on_message(filters.regex("^👥 Foydalanuvchilar$") & filters.private)
    async def users_list(client, message):
        if message.from_user.id != ADMIN_ID:
            return
        
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT user_id, username, premium, image_limit FROM users ORDER BY join_date DESC LIMIT 30")
        users = c.fetchall()
        conn.close()
        
        text = "👥 <b>Last 30:</b>\n\n"
        for u in users:
            st = "💎" if u[2] == 1 else "🆓"
            un = u[1] if u[1] else "NoUser"
            text += f"{st} <code>{u[0]}</code> | @{un} | {u[3]}/3\n"
        
        await message.reply_text(text, parse_mode=ParseMode.HTML)
    
    @app.on_message(filters.regex("^➕ Kanal qo'shish$") & filters.private)
    async def add_ch(client, message):
        if message.from_user.id != ADMIN_ID:
            return
        user_states[ADMIN_ID] = "add_ch"
        await message.reply_text(
            "➕ <b>Kanal:</b>\n\nUsername yuboring\n<code>@channel</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_cancel_keyboard()
        )
    
    @app.on_message(filters.regex("^➖ Kanal o'chirish$") & filters.private)
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
    
    @app.on_message(filters.regex("^💎 Premium berish$") & filters.private)
    async def give_prem(client, message):
        if message.from_user.id != ADMIN_ID:
            return
        user_states[ADMIN_ID] = "give_prem"
        await message.reply_text(
            "💎 <b>Premium:</b>\n\nUser ID\n<code>123456</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_cancel_keyboard()
        )
    
    @app.on_message(filters.regex("^📢 Reklama yuborish$") & filters.private)
    async def send_ad(client, message):
        if message.from_user.id != ADMIN_ID:
            return
        user_states[ADMIN_ID] = "send_ad"
        await message.reply_text(
            "📢 <b>Ad:</b>\n\nXabar",
            parse_mode=ParseMode.HTML,
            reply_markup=get_cancel_keyboard()
        )
    
    @app.on_message(filters.regex("^🔙 Orqaga$") & filters.private)
    async def back(client, message):
        if message.from_user.id != ADMIN_ID:
            return
        user_states.pop(ADMIN_ID, None)
        await message.reply_text("🏠 Menu", reply_markup=get_main_keyboard(ADMIN_ID))
    
    @app.on_message(filters.user(ADMIN_ID) & filters.text & filters.private)
    async def admin_text(client, message):
        state = user_states.get(ADMIN_ID)
        
        if state == "add_ch":
            try:
                ch = message.text.strip()
                chat = await client.get_chat(ch)
                add_channel(str(chat.id), ch)
                await message.reply_text(f"✅ Qo'shildi: {ch}", reply_markup=get_admin_keyboard())
            except Exception as e:
                await message.reply_text(f"❌ Xato: {str(e)}", reply_markup=get_admin_keyboard())
            user_states.pop(ADMIN_ID, None)
            
        elif state == "rem_ch":
            try:
                remove_channel(message.text.strip())
                await message.reply_text("✅ O'chirildi!", reply_markup=get_admin_keyboard())
            except:
                await message.reply_text("❌ Xato!", reply_markup=get_admin_keyboard())
            user_states.pop(ADMIN_ID, None)
            
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
            
            await status.edit_text(
                f"✅ <b>Yuborildi!</b>\n\n"
                f"📊 OK: <b>{success}</b>\n"
                f"❌ Fail: <b>{failed}</b>",
                parse_mode=ParseMode.HTML
            )
            await message.reply_text("🏠 Menu", reply_markup=get_admin_keyboard())
            user_states.pop(ADMIN_ID, None)
