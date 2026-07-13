"""SQLite ma'lumotlar bazasi. Bitta jadval yetarli — referal bot uchun ORM shart emas."""
from datetime import datetime, timezone

import aiosqlite

from config import CHANNELS as DEFAULT_CHANNELS
from config import DB_PATH  # noqa: F401  (testlarda db.DB_PATH orqali override qilinadi)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    telegram_id       INTEGER PRIMARY KEY,
    full_name         TEXT,
    phone             TEXT,
    coins             INTEGER NOT NULL DEFAULT 0,
    inviter_id        INTEGER,                     -- kim taklif qilgan (kutilayotgan holatda ham saqlanadi)
    registered        INTEGER NOT NULL DEFAULT 0,  -- 0 = start bosgan, 1 = to'liq ro'yxatdan o'tgan
    referral_credited INTEGER NOT NULL DEFAULT 0,  -- taklif qilgan odamga coin berilganmi (bir marta)
    created_at        TEXT
);
CREATE INDEX IF NOT EXISTS idx_users_coins ON users(coins DESC);

CREATE TABLE IF NOT EXISTS channels (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    chat  TEXT UNIQUE NOT NULL,   -- @username (get_chat_member uchun)
    title TEXT NOT NULL,
    url   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,       -- masalan 'banner_file_id'
    value TEXT
);

CREATE TABLE IF NOT EXISTS admins (
    telegram_id INTEGER PRIMARY KEY,
    added_by    INTEGER,
    created_at  TEXT
);
"""


def _now():
    return datetime.now(timezone.utc).isoformat()


async def init_db():
    async with aiosqlite.connect(DB_PATH) as d:
        await d.executescript(SCHEMA)
        # config.py dagi standart kanallarni birinchi ishga tushishda joylash (mavjudini o'zgartirmaydi)
        for ch in DEFAULT_CHANNELS:
            await d.execute(
                "INSERT OR IGNORE INTO channels (chat, title, url) VALUES (?,?,?)",
                (ch["chat"], ch["title"], ch["url"]),
            )
        await d.commit()


# ----------------------------- Kanallar (admin) -----------------------------
async def get_channels():
    async with aiosqlite.connect(DB_PATH) as d:
        d.row_factory = aiosqlite.Row
        cur = await d.execute("SELECT id, chat, title, url FROM channels ORDER BY id")
        return await cur.fetchall()


async def add_channel(chat, title, url):
    async with aiosqlite.connect(DB_PATH) as d:
        await d.execute(
            "INSERT OR IGNORE INTO channels (chat, title, url) VALUES (?,?,?)",
            (chat, title, url),
        )
        await d.commit()


async def delete_channel(cid):
    async with aiosqlite.connect(DB_PATH) as d:
        await d.execute("DELETE FROM channels WHERE id=?", (cid,))
        await d.commit()


# ----------------------------- Sozlamalar (key/value) -----------------------------
async def get_setting(key):
    async with aiosqlite.connect(DB_PATH) as d:
        cur = await d.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = await cur.fetchone()
        return row[0] if row else None


async def set_setting(key, value):
    async with aiosqlite.connect(DB_PATH) as d:
        await d.execute(
            "INSERT INTO settings (key, value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        await d.commit()


# ----------------------------- Adminlar (super admin qo'shadi) -----------------------------
async def get_admins():
    async with aiosqlite.connect(DB_PATH) as d:
        cur = await d.execute("SELECT telegram_id FROM admins")
        return [r[0] for r in await cur.fetchall()]


async def add_admin(tid, added_by):
    async with aiosqlite.connect(DB_PATH) as d:
        await d.execute(
            "INSERT OR IGNORE INTO admins (telegram_id, added_by, created_at) VALUES (?,?,?)",
            (tid, added_by, _now()),
        )
        await d.commit()


async def get_user(tid):
    async with aiosqlite.connect(DB_PATH) as d:
        d.row_factory = aiosqlite.Row
        cur = await d.execute("SELECT * FROM users WHERE telegram_id=?", (tid,))
        return await cur.fetchone()


async def start_user(tid, inviter_id):
    """Foydalanuvchini yaratadi (yoki mavjudini qaytaradi). Ro'yxatdan o'tgan holatini qaytaradi (0/1).

    Anti-cheat: o'zini o'zi taklif qilish e'tiborsiz qoldiriladi; mavjud inviter O'ZGARTIRILMAYDI
    (faqat hali bo'sh va foydalanuvchi ro'yxatdan o'tmagan bo'lsa birinchi marta yoziladi).
    """
    inv = inviter_id if (inviter_id and inviter_id != tid) else None
    async with aiosqlite.connect(DB_PATH) as d:
        d.row_factory = aiosqlite.Row
        cur = await d.execute(
            "SELECT registered, inviter_id FROM users WHERE telegram_id=?", (tid,)
        )
        row = await cur.fetchone()
        if row is not None:
            if row["registered"] == 0 and row["inviter_id"] is None and inv is not None:
                await d.execute("UPDATE users SET inviter_id=? WHERE telegram_id=?", (inv, tid))
                await d.commit()
            return row["registered"]
        await d.execute(
            "INSERT INTO users (telegram_id, inviter_id, created_at) VALUES (?,?,?)",
            (tid, inv, _now()),
        )
        await d.commit()
        return 0


async def set_name(tid, name):
    async with aiosqlite.connect(DB_PATH) as d:
        await d.execute("UPDATE users SET full_name=? WHERE telegram_id=?", (name, tid))
        await d.commit()


async def complete_registration(tid, phone):
    """Ro'yxatdan o'tishni yakunlaydi va (agar shartlar bajarilsa) taklif qilgan odamga +1 coin beradi.

    Coin kredit qilingan inviter_id ni qaytaradi (xabar yuborish uchun), aks holda None.
    ponytail: bitta jarayonli bot + SQLite yozuvlarni serial qiladi, shuning uchun
    `WHERE registered=0` guard va oldindan o'qish takroriy kreditni oldini oladi.
    """
    async with aiosqlite.connect(DB_PATH) as d:
        d.row_factory = aiosqlite.Row
        cur = await d.execute(
            "SELECT inviter_id, registered, referral_credited FROM users WHERE telegram_id=?",
            (tid,),
        )
        row = await cur.fetchone()
        if row is None or row["registered"] == 1:
            return None  # allaqachon ro'yxatdan o'tgan — takroriy kredit yo'q

        await d.execute(
            "UPDATE users SET phone=?, registered=1 WHERE telegram_id=? AND registered=0",
            (phone, tid),
        )

        credited = None
        inviter_id = row["inviter_id"]
        if inviter_id and inviter_id != tid and not row["referral_credited"]:
            inv = await (
                await d.execute(
                    "SELECT 1 FROM users WHERE telegram_id=? AND registered=1", (inviter_id,)
                )
            ).fetchone()
            if inv:
                await d.execute("UPDATE users SET coins = coins + 1 WHERE telegram_id=?", (inviter_id,))
                await d.execute("UPDATE users SET referral_credited=1 WHERE telegram_id=?", (tid,))
                credited = inviter_id

        await d.commit()
        return credited


async def get_coins(tid):
    async with aiosqlite.connect(DB_PATH) as d:
        cur = await d.execute("SELECT coins FROM users WHERE telegram_id=?", (tid,))
        row = await cur.fetchone()
        return row[0] if row else 0


async def get_top(limit=10):
    async with aiosqlite.connect(DB_PATH) as d:
        cur = await d.execute(
            "SELECT full_name, coins FROM users WHERE registered=1 "
            "ORDER BY coins DESC, telegram_id ASC LIMIT ?",
            (limit,),
        )
        return await cur.fetchall()


async def get_rank(tid):
    """(rank, coins) qaytaradi. Rank = o'zidan ko'proq coin to'plaganlar soni + 1."""
    async with aiosqlite.connect(DB_PATH) as d:
        coins = await get_coins(tid)
        cur = await d.execute(
            "SELECT COUNT(*)+1 FROM users WHERE registered=1 AND coins > ?", (coins,)
        )
        return (await cur.fetchone())[0], coins


async def get_all_users_ranked():
    """Ro'yxatdan o'tgan barcha foydalanuvchilar, coin bo'yicha kamayish tartibida (Excel eksport uchun)."""
    async with aiosqlite.connect(DB_PATH) as d:
        d.row_factory = aiosqlite.Row
        cur = await d.execute(
            "SELECT full_name, phone, coins, inviter_id, created_at FROM users "
            "WHERE registered=1 ORDER BY coins DESC, telegram_id ASC"
        )
        return await cur.fetchall()


async def get_all_user_ids():
    """Botni ishga tushirgan barcha foydalanuvchilar ID'lari (broadcast uchun)."""
    async with aiosqlite.connect(DB_PATH) as d:
        cur = await d.execute("SELECT telegram_id FROM users")
        return [r[0] for r in await cur.fetchall()]


async def admin_stats():
    async with aiosqlite.connect(DB_PATH) as d:
        cur = await d.execute(
            "SELECT COUNT(*), COALESCE(SUM(registered),0), COALESCE(SUM(coins),0) FROM users"
        )
        return await cur.fetchone()  # (jami, ro'yxatdan o'tgan, umumiy coin)
