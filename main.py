import os
import requests
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
POLITAIONS_API_KEY = os.getenv("POLITAIONS_API_KEY")

app = Client("AI_BOT", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

users_data = {}
CHANNELS = ["@Channel1", "@Channel2"]
BLOCKED_WORDS = [
    "18+", "sex", "xxx", "porn", "porno", "nude", "naked", "boobs", "breasts",
    "penis", "vagina", "dick", "cock", "ass", "pussy", "fuck", "fucking",
    "bitch", "slut", "whore", "cum", "orgasm", "masturbation", "anal", "erotic",
    "bdsm", "fetish", "hentai", "threesome", "gangbang", "xxxvideo", "adult",
    "sexvideo", "sexchat", "strip", "escort", "sexshop", "pornhub", "xvideos",
    "xhamster", "redtube", "tube8", "tube8video", "camgirl", "sexcam", "banned_word"
]

def is_subscribed(user_id):
    for ch in CHANNELS:
        member = app.get_chat_member(ch, user_id)
        if member.status not in ["member", "creator", "administrator"]:
            return False
    return True

def check_limits(user_id, type_):
    data = users_data.get(user_id, {"ai_count":0, "img_count":0, "premium_until":None})
    now = datetime.now()
    if data.get("premium_until") and data["premium_until"] > now:
        return True
    if type_ == "ai":
        return data.get("ai_count", 0) < 100
    if type_ == "img":
        return data.get("img_count", 0) < 3
    return False

def increment_count(user_id, type_):
    if user_id not in users_data:
        users_data[user_id] = {"ai_count":0, "img_count":0, "premium_until":None}
    users_data[user_id][f"{type_}_count"] += 1

@app.on_message(filters.command("start"))
def start(client, message: Message):
    user = message.from_user
    username = user.username if user.username else user.first_name
    text = f"Salom {username}!\nBotdan foydalanish uchun quyidagi kanallarga obuna bo'ling:"
    buttons = [[InlineKeyboardButton(ch, url=f"https://t.me/{ch[1:]}")] for ch in CHANNELS]
    buttons.append([InlineKeyboardButton("Obunani Tekshirish ✅", callback_data="check_sub")])
    message.reply(text, reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex("check_sub"))
def check_sub(client, query):
    user_id = query.from_user.id
    if is_subscribed(user_id):
        query.answer("Siz barcha kanallarga obuna bo'lgansiz! ✅")
    else:
        query.answer("Iltimos barcha kanallarga obuna bo'ling! ❌")

@app.on_message(filters.text & ~filters.command(["start"]))
def ai_chat(client, message: Message):
    user_id = message.from_user.id
    text = message.text.lower()
    if any(word in text for word in BLOCKED_WORDS):
        return
    if not check_limits(user_id, "ai"):
        message.reply("Sizning kunlik AI chat limitingiz tugadi!")
        return
    response = requests.post(
        "https://api.gemini.ai/generate",
        headers={"Authorization": f"Bearer {GEMINI_API_KEY}"},
        json={"prompt": text, "max_tokens":150}
    ).json()
    ai_reply = response.get("text", "")
    if ai_reply:
        increment_count(user_id, "ai")
        message.reply(ai_reply)

@app.on_message(filters.command("image"))
def generate_image(client, message: Message):
    user_id = message.from_user.id
    prompt = message.text.replace("/image","").strip().lower()
    if not prompt or any(word in prompt for word in BLOCKED_WORDS):
        return
    if not check_limits(user_id, "img"):
        message.reply("Sizning kunlik rasm limitingiz tugadi!")
        return
    response = requests.post(
        "https://api.politai.ons/generate-image",
        headers={"Authorization": f"Bearer {POLITAIONS_API_KEY}"},
        json={"prompt": prompt}
    ).json()
    image_url = response.get("url")
    if image_url:
        increment_count(user_id, "img")
        message.reply_photo(image_url)

@app.on_message(filters.user(ADMIN_ID) & filters.command("admin"))
def admin_panel(client, message: Message):
    buttons = [
        [InlineKeyboardButton("Statistika 📊", callback_data="admin_stats")],
        [InlineKeyboardButton("Premium berish 💎", callback_data="admin_premium")],
        [InlineKeyboardButton("Reklama 📢", callback_data="admin_ads")],
        [InlineKeyboardButton("Majburiy obuna ➕", callback_data="admin_sub_add")],
        [InlineKeyboardButton("Majburiy obuna ➖", callback_data="admin_sub_remove")]
    ]
    message.reply("Admin panelga xush kelibsiz!", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.user(ADMIN_ID))
def admin_callbacks(client, query):
    data = query.data
    if data == "admin_stats":
        total_users = len(users_data)
        total_ai = sum(u["ai_count"] for u in users_data.values())
        total_img = sum(u["img_count"] for u in users_data.values())
        query.message.edit(f"Foydalanuvchilar: {total_users}\nAI Chat: {total_ai}\nRasm: {total_img}")
    elif data == "admin_premium":
        query.message.edit("Premium berish uchun /premium [user_id] komandasi ishlatiladi")
    elif data == "admin_ads":
        query.message.edit("Reklama xabarini yuboring: /ads [text]")
    elif data == "admin_sub_add":
        query.message.edit("Majburiy kanal qo'shish uchun /sub_add [kanal] yozing")
    elif data == "admin_sub_remove":
        query.message.edit("Majburiy kanal olib tashlash uchun /sub_remove [kanal] yozing")

@app.on_message(filters.user(ADMIN_ID) & filters.command("premium"))
def give_premium(client, message: Message):
    try:
        user_id = int(message.text.split()[1])
        if user_id not in users_data:
            users_data[user_id] = {"ai_count":0, "img_count":0, "premium_until":None}
        users_data[user_id]["premium_until"] = datetime.now() + timedelta(days=30)
        message.reply(f"{user_id} ga premium berildi ✅")
    except:
        pass

app.run()
