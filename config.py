import os

from dotenv import load_dotenv

load_dotenv()

# BOT_TOKEN import paytida emas, main() da tekshiriladi (testlar token so'ramasligi uchun).
BOT_TOKEN = os.getenv("BOT_TOKEN")
# Birinchi ID — super admin (u yangi admin qo'sha oladi). Ro'yxat tartibi muhim, shuning uchun list.
_admin_list = [int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x]
SUPER_ADMIN_ID = _admin_list[0] if _admin_list else None
ADMIN_IDS = set(_admin_list)
DB_PATH = os.getenv("DB_PATH", "bot.db")

# Har bir kanal: `chat` — get_chat_member uchun (@username), `url` — tugma havolasi.
# Bot faqat @ustozai da admin, shuning uchun faqat o'shani API orqali tekshira olamiz.
# Qolganlarida bot admin bo'lmasa get_chat_member xato beradi -> tekshirilmaydi (pastda izohga qarang).
CHANNELS = [
    {"title": "Ustoz AI", "chat": "@ustozai", "url": "https://t.me/ustozai"},
]
