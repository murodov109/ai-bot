import os
import sqlite3
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
from dotenv import load_dotenv

load_dotenv()
ADMIN_ID = int(os.getenv("ADMIN_ID"))

def get_advanced_stats():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE premium=1")
    premium = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE date(join_date) = date('now')")
    today = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE date(join_date) >= date('now', '-7 days')")
    week = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE date(join_date) >= date('now', '-30 days')")
    month = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM channels")
    channels = c.fetchone()[0]
    conn.close()
    return total, premium, today, week, month, channels

def search_user_by_id(user_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def get_channel_list():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM channels")
    channels = c.fetchall()
    conn.close()
    return channels

def remove_premium(user_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE users SET premium=0, premium_until=NULL WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def reset_user_limit(user_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("UPDATE users SET image_limit=3, last_reset=? WHERE user_id=?", (now, user_id))
    conn.commit()
    conn.close()

def get_top_active_users(limit=10):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT user_id, username, image_limit FROM users WHERE premium=0 ORDER BY (3-image_limit) DESC LIMIT ?", (limit,))
    users = c.fetchall()
    conn.close()
    return users

def set_premium(user_id, days=30):
    from datetime import timedelta
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    until = (datetime.now() + timedelta(days=days)).isoformat()
    c.execute("UPDATE users SET premium=1, premium_until=? WHERE user_id=?", (until, user_id))
    conn.commit()
    conn.close()

def remove_channel_db(channel_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("DELETE FROM channels WHERE channel_id=?", (channel_id,))
    conn.commit()
    conn.close()

def setup_admin_panel(app: Client):
    
    @app.on_message(filters.command("panel") & filters.user(ADMIN_ID))
    async def panel_command(client, message):
        total, premium, today, week, month, channels = get_advanced_stats()
        text = (
            f"📊 <b>Kengaytirilgan Admin Panel</b>\n\n"
            f"👥 Jami: <b>{total}</b> | 💎 Premium: <b>{premium}</b>\n"
            f"🆕 Bugun: <b>{today}</b> | 📅 Hafta: <b>{week}</b> | 📆 Oy: <b>{month}</b>\n"
            f"📢 Kanallar: <b>{channels}</b>\n\n"
            f"🔍 <b>Qo'shimcha funksiyalar:</b>\n"
            f"/search [ID] - Foydalanuvchi qidirish\n"
            f"/channels - Barcha kanallar\n"
            f"/topactive - Eng faol foydalanuvchilar\n"
            f"/removepremium [ID] - Premium olib tashlash\n"
            f"/resetlimit [ID] - Limitni tiklash\n"
            f"/backup - Database zaxirasi"
        )
        await message.reply_text(text, parse_mode=ParseMode.HTML)
    
    @app.on_message(filters.command("search") & filters.user(ADMIN_ID))
    async def search_command(client, message):
        try:
            user_id = int(message.text.split()[1])
            user = search_user_by_id(user_id)
            if user:
                is_premium = "💎 Premium" if user[3] == 1 else "🆓 Oddiy"
                premium_until = user[4].split('T')[0] if user[4] else "Yo'q"
                text = (
                    f"👤 <b>Foydalanuvchi ma'lumotlari:</b>\n\n"
                    f"🆔 ID: <code>{user[0]}</code>\n"
                    f"👤 Username: @{user[1] if user[1] else 'Yo\'q'}\n"
                    f"📊 Limit: <b>{user[2]}/3</b>\n"
                    f"💎 Status: <b>{is_premium}</b>\n"
                    f"⏰ Premium tugash: <code>{premium_until}</code>\n"
                    f"📅 Qo'shilgan: <code>{user[6].split('T')[0]}</code>\n"
                    f"🕐 Oxirgi reset: <code>{user[5].split('T')[0]}</code>"
                )
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("💎 Premium berish", callback_data=f"give_prem:{user_id}")],
                    [InlineKeyboardButton("🔄 Limitni tiklash", callback_data=f"reset_lim:{user_id}")],
                    [InlineKeyboardButton("❌ Premium o'chirish", callback_data=f"rem_prem:{user_id}")]
                ])
                await message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            else:
                await message.reply_text("❌ Foydalanuvchi topilmadi!")
        except:
            await message.reply_text("❌ To'g'ri format: /search [ID]")
    
    @app.on_message(filters.command("channels") & filters.user(ADMIN_ID))
    async def channels_command(client, message):
        channels = get_channel_list()
        if not channels:
            await message.reply_text("❌ Kanallar yo'q!")
            return
        text = "📢 <b>Barcha kanallar:</b>\n\n"
        for ch in channels:
            text += f"📢 {ch[1]}\n   ID: <code>{ch[0]}</code>\n\n"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("➖ Kanalni o'chirish", callback_data="show_del_ch")]])
        await message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    
    @app.on_message(filters.command("topactive") & filters.user(ADMIN_ID))
    async def topactive_command(client, message):
        users = get_top_active_users(10)
        if not users:
            await message.reply_text("❌ Ma'lumot yo'q!")
            return
        text = "🏆 <b>Eng faol foydalanuvchilar (bugun):</b>\n\n"
        for i, u in enumerate(users, 1):
            used = 3 - u[2]
            username = f"@{u[1]}" if u[1] else "Username yo'q"
            text += f"{i}. <code>{u[0]}</code> - {username}\n   🎨 Bugun: <b>{used}</b> ta rasm\n\n"
        await message.reply_text(text, parse_mode=ParseMode.HTML)
    
    @app.on_message(filters.command("removepremium") & filters.user(ADMIN_ID))
    async def removepremium_command(client, message):
        try:
            user_id = int(message.text.split()[1])
            remove_premium(user_id)
            await message.reply_text(f"✅ User {user_id} dan Premium olib tashlandi!")
        except:
            await message.reply_text("❌ To'g'ri format: /removepremium [ID]")
    
    @app.on_message(filters.command("resetlimit") & filters.user(ADMIN_ID))
    async def resetlimit_command(client, message):
        try:
            user_id = int(message.text.split()[1])
            reset_user_limit(user_id)
            await message.reply_text(f"✅ User {user_id} limiti tiklandi (3/3)!")
        except:
            await message.reply_text("❌ To'g'ri format: /resetlimit [ID]")
    
    @app.on_message(filters.command("backup") & filters.user(ADMIN_ID))
    async def backup_command(client, message):
        try:
            total, premium, today, week, month, channels = get_advanced_stats()
            backup_text = (
                f"📦 Database Backup\n"
                f"📅 Sana: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"👥 Jami: {total}\n"
                f"💎 Premium: {premium}\n"
                f"📢 Kanallar: {channels}\n"
            )
            await message.reply_document(
                document="database.db",
                caption=backup_text,
                file_name=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            )
        except Exception as e:
            await message.reply_text(f"❌ Xatolik: {str(e)}")
    
    @app.on_callback_query(filters.regex("^give_prem:"))
    async def give_prem_callback(client, callback_query):
        if callback_query.from_user.id != ADMIN_ID:
            return
        user_id = int(callback_query.data.split(":")[1])
        set_premium(user_id, 30)
        await callback_query.answer("✅ Premium berildi!", show_alert=True)
        try:
            await client.send_message(user_id, "🎉 Sizga 30 kunlik Premium obuna berildi!\n♾️ Cheksiz rasm yarating!")
        except:
            pass
    
    @app.on_callback_query(filters.regex("^reset_lim:"))
    async def reset_lim_callback(client, callback_query):
        if callback_query.from_user.id != ADMIN_ID:
            return
        user_id = int(callback_query.data.split(":")[1])
        reset_user_limit(user_id)
        await callback_query.answer("✅ Limit tiklandi!", show_alert=True)
    
    @app.on_callback_query(filters.regex("^rem_prem:"))
    async def rem_prem_callback(client, callback_query):
        if callback_query.from_user.id != ADMIN_ID:
            return
        user_id = int(callback_query.data.split(":")[1])
        remove_premium(user_id)
        await callback_query.answer("✅ Premium o'chirildi!", show_alert=True)
    
    @app.on_callback_query(filters.regex("^show_del_ch$"))
    async def show_del_ch_callback(client, callback_query):
        if callback_query.from_user.id != ADMIN_ID:
            return
        channels = get_channel_list()
        if not channels:
            await callback_query.answer("❌ Kanallar yo'q!")
            return
        keyboard = []
        for ch in channels:
            keyboard.append([InlineKeyboardButton(f"🗑 {ch[1]}", callback_data=f"del_ch:{ch[0]}")])
        keyboard.append([InlineKeyboardButton("❌ Yopish", callback_data="close_panel")])
        await callback_query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
    
    @app.on_callback_query(filters.regex("^del_ch:"))
    async def del_ch_callback(client, callback_query):
        if callback_query.from_user.id != ADMIN_ID:
            return
        ch_id = callback_query.data.split(":")[1]
        remove_channel_db(ch_id)
        await callback_query.answer("✅ Kanal o'chirildi!", show_alert=True)
        channels = get_channel_list()
        if channels:
            keyboard = []
            for ch in channels:
                keyboard.append([InlineKeyboardButton(f"🗑 {ch[1]}", callback_data=f"del_ch:{ch[0]}")])
            keyboard.append([InlineKeyboardButton("❌ Yopish", callback_data="close_panel")])
            await callback_query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await callback_query.message.edit_text("✅ Barcha kanallar o'chirildi!")
    
    @app.on_callback_query(filters.regex("^close_panel$"))
    async def close_panel_callback(client, callback_query):
        if callback_query.from_user.id != ADMIN_ID:
            return
        await callback_query.message.delete()

print("✅ Panel moduli yuklandi!")
