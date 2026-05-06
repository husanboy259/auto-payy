import asyncio
from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup,
    InlineKeyboardButton, WebAppInfo
)
from aiogram.filters import CommandStart

import database as db
from config import (
    CARD_NUMBER, CARD_HOLDER, BANK_NAME,
    PAYMENT_AMOUNT, PAYMENT_TIMEOUT, ADMIN_IDS, MINI_APP_URL
)

router = Router()

# Active timers: {telegram_id: asyncio.Task}
active_timers: dict[int, asyncio.Task] = {}


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 To'lov qilish", callback_data="start_payment")],
        [InlineKeyboardButton(text="💰 Balansim",      callback_data="my_balance")],
        [InlineKeyboardButton(text="📱 Mini App",      web_app=WebAppInfo(url=MINI_APP_URL))],
    ])


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_payment")]
    ])


# ── /start ───────────────────────────────────────────────────────────────────
@router.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user
    await db.create_user(user.id, user.username or "", user.full_name)
    record = await db.get_user(user.id)

    await message.answer(
        f"👋 Assalomu alaykum, <b>{user.full_name}</b>!\n\n"
        f"🤖 <b>Auto To'lov Botiga xush kelibsiz!</b>\n\n"
        f"💰 Joriy balans: <b>{record['balance']:,} so'm</b>\n\n"
        f"To'lov qilish uchun tugmani bosing 👇",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )


# ── Balans ───────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "my_balance")
async def show_balance(call: CallbackQuery):
    record = await db.get_user(call.from_user.id)
    if not record:
        await call.answer("Avval /start bosing!", show_alert=True)
        return
    await call.message.edit_text(
        f"💰 <b>Sizning balansingiz</b>\n\n"
        f"👤 Foydalanuvchi: <b>{call.from_user.full_name}</b>\n"
        f"🆔 Telegram ID: <code>{call.from_user.id}</code>\n"
        f"💵 Balans: <b>{record['balance']:,} so'm</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_main")]
        ]),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data == "back_main")
async def back_to_main(call: CallbackQuery):
    record = await db.get_user(call.from_user.id)
    await call.message.edit_text(
        f"👋 Asosiy menyu\n\n"
        f"💰 Joriy balans: <b>{record['balance']:,} so'm</b>",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )
    await call.answer()


# ── To'lov boshlash ───────────────────────────────────────────────────────────
@router.callback_query(F.data == "start_payment")
async def start_payment(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id

    existing = await db.get_pending_payment(user_id)
    if existing:
        await call.answer("⏳ Sizda kutilayotgan to'lov mavjud!", show_alert=True)
        return

    expires_at = (datetime.now() + timedelta(seconds=PAYMENT_TIMEOUT)).isoformat()
    payment_id = await db.create_payment(user_id, PAYMENT_AMOUNT, expires_at)

    mins = PAYMENT_TIMEOUT // 60
    secs = PAYMENT_TIMEOUT % 60

    msg = await call.message.edit_text(
        f"💳 <b>TO'LOV MA'LUMOTLARI</b>\n\n"
        f"🏦 Bank:         <b>{BANK_NAME}</b>\n"
        f"💳 Karta raqami:\n<code>{CARD_NUMBER}</code>\n"
        f"👤 Karta egasi:  <b>{CARD_HOLDER}</b>\n\n"
        f"💵 To'lov miqdori: <b>{PAYMENT_AMOUNT:,} so'm</b>\n\n"
        f"⏱ Qolgan vaqt: <b>{mins:02d}:{secs:02d}</b> 🟢\n\n"
        f"📸 To'lovni amalga oshirib, <b>chek rasmini yuboring!</b>",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )

    if user_id in active_timers:
        active_timers[user_id].cancel()

    task = asyncio.create_task(
        countdown_timer(bot, user_id, msg.chat.id, msg.message_id, payment_id, PAYMENT_TIMEOUT)
    )
    active_timers[user_id] = task
    await call.answer()


# ── Countdown timer ───────────────────────────────────────────────────────────
async def countdown_timer(bot: Bot, user_id: int, chat_id: int, message_id: int, payment_id: int, total: int):
    try:
        for remaining in range(total - 1, -1, -1):
            await asyncio.sleep(1)

            payment = await db.get_payment(payment_id)
            if not payment or payment["status"] != "pending":
                return

            if remaining % 10 == 0 or remaining <= 30:
                mins = remaining // 60
                secs = remaining % 60
                dot = "🔴" if remaining <= 60 else "🟡" if remaining <= 120 else "🟢"
                try:
                    await bot.edit_message_text(
                        f"💳 <b>TO'LOV MA'LUMOTLARI</b>\n\n"
                        f"🏦 Bank:         <b>{BANK_NAME}</b>\n"
                        f"💳 Karta raqami:\n<code>{CARD_NUMBER}</code>\n"
                        f"👤 Karta egasi:  <b>{CARD_HOLDER}</b>\n\n"
                        f"💵 To'lov miqdori: <b>{PAYMENT_AMOUNT:,} so'm</b>\n\n"
                        f"⏱ Qolgan vaqt: <b>{mins:02d}:{secs:02d}</b> {dot}\n\n"
                        f"📸 To'lovni amalga oshirib, <b>chek rasmini yuboring!</b>",
                        chat_id=chat_id,
                        message_id=message_id,
                        reply_markup=cancel_kb(),
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

        # Vaqt tugadi
        payment = await db.get_payment(payment_id)
        if payment and payment["status"] == "pending":
            await db.update_payment_status(payment_id, "expired")
            try:
                await bot.edit_message_text(
                    "⌛ <b>Vaqt tugadi!</b>\n\n"
                    "To'lov muddati o'tdi. Qaytadan urinib ko'ring.",
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔄 Qaytadan", callback_data="start_payment")],
                        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back_main")],
                    ]),
                    parse_mode="HTML"
                )
            except Exception:
                pass

    except asyncio.CancelledError:
        pass
    finally:
        active_timers.pop(user_id, None)


# ── Chek rasm qabul qilish ────────────────────────────────────────────────────
@router.message(F.photo | F.document)
async def receive_check(message: Message, bot: Bot):
    user_id = message.from_user.id
    user = message.from_user

    payment = await db.get_pending_payment(user_id)
    if not payment:
        await message.answer(
            "⚠️ Sizda faol to'lov yo'q.\n"
            "Avval <b>💳 To'lov qilish</b> tugmasini bosing.",
            reply_markup=main_menu_kb(),
            parse_mode="HTML"
        )
        return

    payment_id = payment["id"]

    # Timer ni to'xtatish
    if user_id in active_timers:
        active_timers[user_id].cancel()

    await db.update_payment_status(payment_id, "waiting_approval")

    now = datetime.now()

    # ── Userga tasdiq xabari ──────────────────────────────────────────────
    await message.answer(
        f"📨 <b>CHEK QABUL QILINDI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 Chek ID:    <code>#{payment_id}</code>\n"
        f"📅 Sana:       {now.strftime('%d.%m.%Y')}\n"
        f"🕐 Vaqt:       {now.strftime('%H:%M:%S')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏦 Bank:       <b>{BANK_NAME}</b>\n"
        f"💵 Miqdor:     <b>{payment['amount']:,} so'm</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏳ Holat:      <b>Admin tekshirmoqda...</b>\n\n"
        f"Tez orada balans qo'shiladi. 🙏",
        parse_mode="HTML"
    )

    # ── Adminga chek foto + ma'lumotlar ──────────────────────────────────
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"admin_approve:{payment_id}"),
            InlineKeyboardButton(text="❌ Rad etish",  callback_data=f"admin_reject:{payment_id}"),
        ]
    ])

    caption = (
        f"🔔 <b>YANGI TO'LOV CHEKI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 Chek ID:    <code>#{payment_id}</code>\n"
        f"📅 Sana:       {now.strftime('%d.%m.%Y %H:%M:%S')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Ism:        <b>{user.full_name}</b>\n"
        f"🆔 ID:         <code>{user.id}</code>\n"
        f"📎 Username:   @{user.username or 'nomaʼlum'}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏦 Bank:       <b>{BANK_NAME}</b>\n"
        f"💳 Karta:      <code>{CARD_NUMBER}</code>\n"
        f"💵 Miqdor:     <b>{payment['amount']:,} so'm</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏳ Holat:      <b>Kutilmoqda</b>"
    )

    for admin_id in ADMIN_IDS:
        try:
            if message.photo:
                await bot.send_photo(
                    admin_id,
                    photo=message.photo[-1].file_id,
                    caption=caption,
                    reply_markup=admin_kb,
                    parse_mode="HTML"
                )
            else:
                await bot.send_document(
                    admin_id,
                    document=message.document.file_id,
                    caption=caption,
                    reply_markup=admin_kb,
                    parse_mode="HTML"
                )
        except Exception:
            pass


# ── Bekor qilish ─────────────────────────────────────────────────────────────
@router.callback_query(F.data == "cancel_payment")
async def cancel_payment(call: CallbackQuery):
    user_id = call.from_user.id

    if user_id in active_timers:
        active_timers[user_id].cancel()

    payment = await db.get_pending_payment(user_id)
    if payment:
        await db.update_payment_status(payment["id"], "cancelled")

    record = await db.get_user(user_id)
    await call.message.edit_text(
        "❌ <b>To'lov bekor qilindi.</b>\n\n"
        f"💰 Balansingiz: <b>{record['balance']:,} so'm</b>",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )
    await call.answer()
