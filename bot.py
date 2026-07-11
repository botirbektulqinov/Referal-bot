import asyncio
import html
import logging
from urllib.parse import quote

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatMemberStatus, ParseMode
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

import db
from config import ADMIN_IDS, BOT_TOKEN
from excel_export import build_excel

logging.basicConfig(level=logging.INFO)
dp = Dispatcher()
BOT_USERNAME = None  # startup da to'ldiriladi

WELCOME = (
    "👋 <b>Assalomu alaykum!</b>\n\n"
    "«Ustoz AI oromgohi» saralash bosqichi rasmiy botiga xush kelibsiz! "
    "Oromgohda ishtirok etish uchun quyidagi kanallarga obuna boʻling va "
    "doʻstlaringizni taklif qilib, <b>Turoncoin</b>lar toʻplang! 👇"
)

# /start bosilганda birinchi chiqadigan tanishtiruv xabari
INFO_TEXT = (
    "🏕️ <b>“Ustoz AI elchilari” oromgohiga yoʻllanma yutib oling!</b>\n\n"
    "Oromgohda qanday ishtirok etish mumkin?\n\n"
    "✅ <b>1-Yoʻl:</b>\n"
    "Ustoz AI haqida video tayyorlang va uni Ustoz AI Instagram sahifasiga collab sifatida "
    "video yuboring. Eng koʻp koʻrilgan videolar mualliflari oromgoh yoʻllanmasini qoʻlga "
    "kiritish imkoniyatiga ega boʻladi.\n\n"
    "✅ <b>2-Yoʻl:</b>\n"
    "Ustoz AI botidan roʻyxatdan oʻting va sizga berilgan taklif havolasi orqali doʻstlaringizni "
    "taklif qiling. Eng faol targʻibotchilar oromgohga yoʻllanmani qoʻlga kiritishadi.\n\n"
    "✅ <b>3-Yoʻl:</b>\n"
    "Ustoz AI ilovasidagi eng koʻp doʻstini taklif qilgan ishtirokchi yoʻllanmani qoʻlga kiritadi.\n\n"
    "✅ <b>4-Yoʻl:</b>\n"
    "Ustoz AI ilovasidagi eng koʻp sertifikat olgan foydalanuvchilar saralab olinadi.\n\n"
    "💥 Siz qaysi yoʻl orqali Ustoz AI elchilari oromgohiga yoʻllanmani qoʻlga kiritmoqchisiz?"
)

# "Do'st taklif qilish" postining matni ({link} — foydalanuvchining shaxsiy havolasi)
INVITE_CAPTION = (
    "🏕 <b>Bu yozni Boʻstonliq oromgohida mazmunli oʻtkazishga tayyormisiz?</b>\n\n"
    "📅 27-iyul — 2-avgust\n\n"
    "Ustoz AI Elchilari Oromgohida qatnashish imkoniyatini qoʻldan boy bermang!\n\n"
    "🔥 Hozirdanoq doʻstlaringizni taklif qilishni boshlang — har bir taklif sizni "
    "oromgohga bir qadam yaqinlashtiradi.\n\n"
    "🔗 <b>Referal havolangiz:</b>\n{link}"
)
SHARE_TEXT = "🏕 Ustoz AI Elchilari oromgohiga yoʻllanma yutib oling! Roʻyxatdan oʻting:"

NOT_SUBSCRIBED = (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED)


class Reg(StatesGroup):
    name = State()
    phone = State()


class AdminSG(StatesGroup):
    add_channel = State()
    broadcast = State()
    set_banner = State()


def is_admin(uid):
    return uid in ADMIN_IDS


# ----------------------------- Klaviaturalar -----------------------------
def subscription_kb(channels):
    rows = [
        [InlineKeyboardButton(text=f"{i} - kanal", url=ch["url"])]
        for i, ch in enumerate(channels, 1)
    ]
    rows.append([InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def contact_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Telefon raqamni ulashish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def main_menu_kb(admin=False):
    rows = [
        [KeyboardButton(text="👥 Do'st taklif qilish")],
        [KeyboardButton(text="🏆 Umumiy statistika")],
    ]
    if admin:
        rows.append([KeyboardButton(text="🛠 Admin panel")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def admin_panel_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Habar yuborish (broadcast)", callback_data="adm_broadcast")],
            [InlineKeyboardButton(text="🖼 Referal banner rasmini o'rnatish", callback_data="adm_setbanner")],
            [InlineKeyboardButton(text="📊 Excel hisobot yuklab olish", callback_data="adm_excel")],
            [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="adm_addch")],
            [InlineKeyboardButton(text="📋 Kanallar ro'yxati", callback_data="adm_listch")],
            [InlineKeyboardButton(text="📈 Umumiy statistika", callback_data="adm_stats")],
        ]
    )


# ----------------------------- Obuna tekshiruvi -----------------------------
async def missing_channels(bot: Bot, user_id: int, channels):
    missing = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch["chat"], user_id)
            if member.status in NOT_SUBSCRIBED:
                missing.append(ch)
        except (TelegramBadRequest, TelegramForbiddenError):
            # Bot bu kanalda admin emas -> Bot API a'zolikni tekshira olmaydi.
            # ponytail: faqat bot admin bo'lgan kanal majburlanadi; admin qilinsa o'zi tekshiradi.
            pass
    return missing


# ----------------------------- Foydalanuvchi oqimi -----------------------------
@dp.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext):
    await state.clear()
    tid = message.from_user.id
    inviter = int(command.args) if command.args and command.args.isdigit() else None
    registered = await db.start_user(tid, inviter)
    if registered:
        await message.answer("🏠 Asosiy menyu", reply_markup=main_menu_kb(is_admin(tid)))
        return
    await message.answer(INFO_TEXT)  # avval tanishtiruv (4 yo'l)
    channels = await db.get_channels()
    await message.answer(WELCOME, reply_markup=subscription_kb(channels))  # keyin kanallar


@dp.callback_query(F.data == "check_sub")
async def check_sub(cb: CallbackQuery, state: FSMContext):
    channels = await db.get_channels()
    if await missing_channels(cb.bot, cb.from_user.id, channels):
        await cb.answer("❌ Avval barcha kanallarga obuna bo'ling!", show_alert=True)
        return
    await cb.message.delete()
    await state.set_state(Reg.name)
    await cb.message.answer("👤 Ism va familyangizni kiriting:")
    await cb.answer()


@dp.message(Reg.name, F.text)
async def reg_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 3:
        await message.answer("Iltimos, to'liq ism va familyangizni kiriting:")
        return
    await db.set_name(message.from_user.id, name)
    await state.set_state(Reg.phone)
    await message.answer("📱 Telefon raqamingizni tugma orqali ulashing 👇", reply_markup=contact_kb())


@dp.message(Reg.phone, F.contact)
async def reg_phone(message: Message, state: FSMContext):
    if message.contact.user_id != message.from_user.id:
        await message.answer("⚠️ Iltimos, o'zingizning raqamingizni ulashing.", reply_markup=contact_kb())
        return
    inviter = await db.complete_registration(message.from_user.id, message.contact.phone_number)
    await state.clear()
    await message.answer(
        "✅ <b>Siz muvaffaqiyatli ro'yxatdan o'tdingiz!</b>\n\n🪙 Coin: <b>0</b>",
        reply_markup=main_menu_kb(is_admin(message.from_user.id)),
    )
    if inviter:
        try:
            await message.bot.send_message(
                inviter, "🎉 Sizning havolangiz orqali yangi do'st qo'shildi!\n🪙 <b>+1 coin</b>"
            )
        except Exception:
            pass


@dp.message(Reg.phone)
async def reg_phone_invalid(message: Message):
    await message.answer("📱 Telefon raqamni faqat tugma orqali ulashing 👇", reply_markup=contact_kb())


# ----------------------------- Admin panel -----------------------------
@dp.message(Command("admin"))
@dp.message(F.text == "🛠 Admin panel")
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("🛠 <b>Admin panel</b>", reply_markup=admin_panel_kb())


@dp.callback_query(F.data == "adm_excel")
async def adm_excel(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return await cb.answer()
    await cb.answer("⏳ Tayyorlanmoqda...")
    rows = await db.get_all_users_ranked()
    if not rows:
        return await cb.message.answer("Hozircha ro'yxatdan o'tgan foydalanuvchi yo'q.")
    data = build_excel(rows)
    await cb.message.answer_document(
        BufferedInputFile(data, filename="foydalanuvchilar.xlsx"),
        caption=f"📊 Jami <b>{len(rows)}</b> ta ro'yxatdan o'tgan foydalanuvchi",
    )


@dp.callback_query(F.data == "adm_addch")
async def adm_addch(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer()
    await state.set_state(AdminSG.add_channel)
    await cb.message.answer(
        "➕ Kanal @username yoki havolasini yuboring:\n\n"
        "Masalan: <code>@mychannel</code>\n\n"
        "⚠️ Bot a'zolikni tekshira olishi uchun kanalga <b>admin</b> qilinishi kerak."
    )
    await cb.answer()


def _extract_username(text):
    text = text.strip()
    if "t.me/" in text:
        text = text.split("t.me/")[-1]
    text = text.lstrip("@").strip("/").split("/")[0].split("?")[0].strip()
    return text or None


@dp.message(AdminSG.add_channel)
async def adm_addch_input(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    username = _extract_username(message.text or "")
    if not username:
        await message.answer("❌ Noto'g'ri format. @username ko'rinishida yuboring.")
        return
    chat = f"@{username}"
    title, url = username, f"https://t.me/{username}"
    try:
        info = await message.bot.get_chat(chat)
        title = info.title or username
    except (TelegramBadRequest, TelegramForbiddenError):
        pass  # kanal nomini olib bo'lmadi — username bilan saqlaymiz
    await db.add_channel(chat, title, url)
    await state.clear()
    await message.answer(f"✅ Kanal qo'shildi: <b>{html.escape(title)}</b>", reply_markup=admin_panel_kb())


@dp.callback_query(F.data == "adm_listch")
async def adm_listch(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return await cb.answer()
    channels = await db.get_channels()
    if not channels:
        await cb.message.answer("📋 Kanallar yo'q.")
        return await cb.answer()
    rows = [
        [InlineKeyboardButton(text=f"❌ {c['title']}", callback_data=f"adm_delch:{c['id']}")]
        for c in channels
    ]
    await cb.message.answer(
        "📋 <b>Kanallar</b> (o'chirish uchun bosing):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await cb.answer()


@dp.callback_query(F.data.startswith("adm_delch:"))
async def adm_delch(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return await cb.answer()
    await db.delete_channel(int(cb.data.split(":")[1]))
    await cb.answer("O'chirildi ✅")
    await cb.message.edit_text("🗑 Kanal o'chirildi.")


@dp.callback_query(F.data == "adm_stats")
async def adm_stats(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return await cb.answer()
    total, registered, coins = await db.admin_stats()
    await cb.message.answer(
        f"📈 <b>Statistika</b>\n\n👥 Jami: <b>{total}</b>\n"
        f"✅ Ro'yxatdan o'tgan: <b>{registered}</b>\n🪙 Umumiy coin: <b>{coins}</b>"
    )
    await cb.answer()


# ----------------------------- Broadcast -----------------------------
@dp.callback_query(F.data == "adm_broadcast")
async def adm_broadcast(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer()
    await state.set_state(AdminSG.broadcast)
    await cb.message.answer(
        "📢 Yubormoqchi bo'lgan xabaringizni yuboring — <b>matn, rasm, video, post</b> "
        "yoki istalgan tur.\n\nBekor qilish uchun: /bekor"
    )
    await cb.answer()


@dp.message(AdminSG.broadcast, Command("bekor"))
async def broadcast_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Bekor qilindi.", reply_markup=admin_panel_kb())


@dp.message(AdminSG.broadcast)
async def do_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    await state.clear()
    user_ids = await db.get_all_user_ids()
    await message.answer(f"📤 Yuborilmoqda... ({len(user_ids)} ta foydalanuvchi)")
    # Alohida task — polling bloklanmasin. ponytail: bot qayta ishga tushsa broadcast to'xtaydi.
    asyncio.create_task(
        _run_broadcast(message.bot, message.chat.id, message.message_id, user_ids, message.from_user.id)
    )


async def _run_broadcast(bot, from_chat, msg_id, user_ids, admin_id):
    sent = failed = 0
    for uid in user_ids:
        try:
            await bot.copy_message(uid, from_chat, msg_id)  # har qanday xabar turini ko'chiradi
            sent += 1
        except TelegramRetryAfter as e:  # flood limit — kutamiz va qayta urinamiz
            await asyncio.sleep(e.retry_after)
            try:
                await bot.copy_message(uid, from_chat, msg_id)
                sent += 1
            except Exception:
                failed += 1
        except (TelegramForbiddenError, TelegramBadRequest):  # bloklagan/topilmadi
            failed += 1
        await asyncio.sleep(0.05)  # ponytail: ~20 msg/s, Telegram limitidan past
    try:
        await bot.send_message(admin_id, f"✅ Yuborildi: <b>{sent}</b>\n❌ Xato: <b>{failed}</b>")
    except Exception:
        pass


# ----------------------------- Banner o'rnatish -----------------------------
@dp.callback_query(F.data == "adm_setbanner")
async def adm_setbanner(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer()
    await state.set_state(AdminSG.set_banner)
    await cb.message.answer(
        "🖼 Referal post uchun <b>banner rasmini</b> yuboring.\n\nBekor qilish: /bekor"
    )
    await cb.answer()


@dp.message(AdminSG.set_banner, Command("bekor"))
async def setbanner_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Bekor qilindi.", reply_markup=admin_panel_kb())


@dp.message(AdminSG.set_banner, F.photo)
async def setbanner_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    await db.set_setting("banner_file_id", message.photo[-1].file_id)
    await state.clear()
    await message.answer(
        "✅ Banner o'rnatildi. Endi \"👥 Do'st taklif qilish\" postida shu rasm chiqadi.",
        reply_markup=admin_panel_kb(),
    )


@dp.message(AdminSG.set_banner)
async def setbanner_invalid(message: Message):
    await message.answer("Iltimos, <b>rasm</b> yuboring. Bekor qilish: /bekor")


# ----------------------------- Asosiy menyu -----------------------------
@dp.message(F.text == "👥 Do'st taklif qilish")
async def invite(message: Message):
    link = f"https://t.me/{BOT_USERNAME}?start={message.from_user.id}"
    caption = INVITE_CAPTION.format(link=link)
    share_url = f"https://t.me/share/url?url={quote(link)}&text={quote(SHARE_TEXT)}"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="📤 Do'stlarni taklif qilish", url=share_url)]]
    )
    banner = await db.get_setting("banner_file_id")  # admin panel orqali o'rnatiladi
    if banner:
        await message.answer_photo(banner, caption=caption, reply_markup=kb)
    else:
        await message.answer(caption, reply_markup=kb)


@dp.message(F.text == "🏆 Umumiy statistika")
async def statistics(message: Message):
    top = await db.get_top(10)
    rank, coins = await db.get_rank(message.from_user.id)
    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    lines = ["🏆 <b>TOP 10 foydalanuvchilar</b>\n"]
    for i, (name, c) in enumerate(top):
        lines.append(f"{medals[i]} {html.escape(name or 'Nomsiz')} — <b>{c}</b> 🪙")
    lines.append("\n━━━━━━━━━━━━━━━━")
    lines.append(f"👤 Siz: <b>#{rank}</b>\n🪙 Coin: <b>{coins}</b>")
    await message.answer("\n".join(lines))


async def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN topilmadi. .env faylini to'ldiring.")
    await db.init_db()
    bot = Bot(
        BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            link_preview_is_disabled=True,
        ),
    )
    global BOT_USERNAME
    BOT_USERNAME = (await bot.get_me()).username
    logging.info("Bot ishga tushdi: @%s", BOT_USERNAME)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
