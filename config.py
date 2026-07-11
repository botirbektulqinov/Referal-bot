import os

from dotenv import load_dotenv

load_dotenv()

# BOT_TOKEN import paytida emas, main() da tekshiriladi (testlar token so'ramasligi uchun).
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x}
DB_PATH = os.getenv("DB_PATH", "bot.db")

# Har bir kanal: `chat` — get_chat_member uchun (@username), `url` — tugma havolasi.
# Bot faqat @ustozai da admin, shuning uchun faqat o'shani API orqali tekshira olamiz.
# Qolganlarida bot admin bo'lmasa get_chat_member xato beradi -> tekshirilmaydi (pastda izohga qarang).
CHANNELS = [
    {"title": "Ustoz AI", "chat": "@ustozai", "url": "https://t.me/ustozai"},
    {"title": "Turonbank", "chat": "@turonbankuz", "url": "https://t.me/turonbankuz"},
    {"title": "Alisher Sadullaev", "chat": "@alisher_sadullaev", "url": "https://t.me/alisher_sadullaev"},
    {"title": "Yoshlar agentligi", "chat": "@yoshlaragentligi", "url": "https://t.me/yoshlaragentligi"},
]
