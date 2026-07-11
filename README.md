# Referal Bot

Telegram referal bot: 4 kanalga obuna → ro'yxatdan o'tish (ism + telefon) → do'st taklif qilish (+1 coin) → TOP 10 statistika.

## Ishga tushirish

```bash
pip install -r requirements.txt
cp .env.example .env        # BOT_TOKEN va ADMIN_IDS to'ldiring
python bot.py
```

Testni ishga tushirish: `python test_db.py`

## Kanallar

`config.py` ichida. Botni **@ustozai** ga admin qiling — a'zolik faqat shu yerda tekshiriladi.

### Obuna tekshiruvi haqida (muhim)

Telegram Bot API bot **admin bo'lmagan** kanalda a'zolikni **hech qanday** usul bilan tekshira olmaydi
(deep-link, token, forwarding — hech biri ishonchli emas). Shuning uchun:

- **@ustozai** — bot admin, `get_chat_member` bilan tekshiriladi (majburiy).
- Qolgan 3 kanal — bot admin emas, tugma foydalanuvchini kanalga yo'naltiradi, lekin API majburlay olmaydi.

Botni istalgan kanalga **admin** qilsangiz, kod o'zgarmasdan o'sha kanal ham avtomatik tekshirila boshlaydi.
Barcha 4 ta kanalga majburiy tekshiruv kerak bo'lsa — botni 4 tasiga ham admin qiling.

## Serverga joylash (Linux VPS, systemd)

```bash
# 1. Fayllarni serverga ko'chiring (masalan /opt/referal_bot ga)
sudo mkdir -p /opt/referal_bot && cd /opt/referal_bot
# ... fayllarni yuklang (scp / git) ...

# 2. Virtual muhit + kutubxonalar
python3 -m venv venv
venv/bin/pip install -r requirements.txt

# 3. .env yarating (BOT_TOKEN, ADMIN_IDS)
cp .env.example .env && nano .env

# 4. Foydalanuvchi (ixtiyoriy, root ostida ishlatmaslik uchun)
sudo useradd -r -s /usr/sbin/nologin botuser
sudo chown -R botuser:botuser /opt/referal_bot

# 5. systemd xizmati
sudo cp deploy/referal-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now referal-bot

# Loglar / boshqarish
sudo journalctl -u referal-bot -f
sudo systemctl restart referal-bot
```

`referal-bot.service` da yo'l `/opt/referal_bot`, foydalanuvchi `botuser` — boshqacha bo'lsa tahrirlang.

> ⚠️ **Xavfsizlik:** haqiqiy `BOT_TOKEN` faqat serverdagi `.env` da bo'lsin. Repozitoriyaga
> yuborishdan oldin `.env.example` dagi tokenni namunaga (`123456:ABC...`) almashtiring.
> `.env` va `bot.db` `.gitignore` da — commit qilinmaydi.

## Nima ataylab qo'yilmadi

Postgres/Redis/Docker/Alembic/Clean-Architecture — bu hajmdagi bot uchun ortiqcha. SQLite bitta jadval bilan
o'n minglab foydalanuvchini ko'taradi. Yuk shu chegaradan oshsa yoki bir nechta jarayonda ishlatsangiz —
Postgres'ga o'tiladi. Broadcast / CSV eksport kerak bo'lsa — `/stats` yoniga qo'shiladi.
