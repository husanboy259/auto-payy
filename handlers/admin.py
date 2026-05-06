from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from config import ADMIN_IDS, BANK_NAME, CARD_NUMBER

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


class BroadcastState(StatesGroup):
    waiting_message = State()


@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Sizda admin huquqi yo'q!")
        return

    users = await db.get_all_users()
    pending = await db.get_all_pending_payments()

    await message.answer(
        f"🛠 <b>ADMIN PANEL</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{len(users)}</b>\n"
        f"⏳ Kutilayotgan to'lovlar: <b>{len(pending)}</b>\n",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin_users")],
            [InlineKeyboardButton(text="⏳ Kutilayotgan to'lovlar", callback_data="admin_pending")],
            [InlineKeyboardButton(text="📢 Hammaga xabar", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="💰 Balans qo'shish", callback_data="admin_add_balance")],
        ]),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_users")
async def admin_users(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    users = await db.get_all_users()
    if not users:
        await call.answer("Foydalanuvchilar yo'q!", show_alert=True)
        return

    text = "👥 <b>FOYDALANUVCHILAR RO'YXATI</b>\n\n"
    for i, u in enumerate(users[:20], 1):
        username = f"@{u['username']}" if u['username'] else "yo'q"
        text += (
            f"{i}. <b>{u['full_name']}</b>\n"
            f"   🆔 <code>{u['telegram_id']}</code> | {username}\n"
            f"   💰 {u['balance']:,} so'm\n\n"
        )

    if len(users) > 20:
        text += f"... va yana {len(users) - 20} ta foydalanuvchi"

    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_back")]
        ]),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data == "admin_pending")
async def admin_pending(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    payments = await db.get_all_pending_payments()
    if not payments:
        await call.answer("Kutilayotgan to'lovlar yo'q!", show_alert=True)
        return

    text = "⏳ <b>KUTILAYOTGAN TO'LOVLAR</b>\n\n"
    buttons = []
    for p in payments:
        username = f"@{p['username']}" if p['username'] else "yo'q"
        text += (
            f"📋 ID: #{p['id']}\n"
            f"👤 {p['full_name']} ({username})\n"
            f"🆔 <code>{p['telegram_id']}</code>\n"
            f"💵 {p['amount']:,} so'm\n\n"
        )
        buttons.append([
            InlineKeyboardButton(text=f"✅ #{p['id']} Tasdiqlash", callback_data=f"admin_approve:{p['id']}"),
            InlineKeyboardButton(text=f"❌ Rad", callback_data=f"admin_reject:{p['id']}"),
        ])

    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_back")])

    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data.startswith("admin_approve:"))
async def admin_approve(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    payment_id = int(call.data.split(":")[1])
    payment = await db.get_payment(payment_id)

    if not payment:
        await call.answer("To'lov topilmadi!", show_alert=True)
        return

    if payment["status"] not in ("pending", "waiting_approval"):
        await call.answer("Bu to'lov allaqachon qayta ishlangan!", show_alert=True)
        return

    await db.update_payment_status(payment_id, "approved")
    await db.update_user_balance(payment["telegram_id"], payment["amount"])

    user = await db.get_user(payment["telegram_id"])
    now = datetime.now()

    # ── Admin sees processed receipt ──────────────────────────────────────
    await call.message.edit_text(
        f"✅ <b>TO'LOV TASDIQLANDI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 Chek ID:      <code>#{payment_id}</code>\n"
        f"📅 Sana:         {now.strftime('%d.%m.%Y')}\n"
        f"🕐 Vaqt:         {now.strftime('%H:%M:%S')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Foydalanuvchi: <b>{user['full_name']}</b>\n"
        f"🆔 Telegram ID:  <code>{payment['telegram_id']}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏦 Bank:         <b>{BANK_NAME}</b>\n"
        f"💳 Karta:        <code>{CARD_NUMBER}</code>\n"
        f"💵 Miqdor:       <b>{payment['amount']:,} so'm</b>\n"
        f"💰 Yangi balans: <b>{user['balance']:,} so'm</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Holat:        <b>TASDIQLANDI</b>\n"
        f"👮 Admin:        <b>{call.from_user.full_name}</b>",
        parse_mode="HTML"
    )

    # ── User receives processed receipt ──────────────────────────────────
    try:
        await bot.send_message(
            payment["telegram_id"],
            f"✅ <b>TO'LOV TASDIQLANDI!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 Chek ID:      <code>#{payment_id}</code>\n"
            f"📅 Sana:         {now.strftime('%d.%m.%Y')}\n"
            f"🕐 Vaqt:         {now.strftime('%H:%M:%S')}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🏦 Bank:         <b>{BANK_NAME}</b>\n"
            f"💳 Karta:        <code>{CARD_NUMBER}</code>\n"
            f"💵 To'langan:    <b>{payment['amount']:,} so'm</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Yangi balans: <b>{user['balance']:,} so'm</b>\n"
            f"✅ Holat:        <b>MUVAFFAQIYATLI</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎉 Rahmat! Xizmatimizdan foydalanganingiz uchun!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 Balansimni ko'rish", callback_data="my_balance")],
                [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back_main")],
            ]),
            parse_mode="HTML"
        )
    except Exception:
        pass

    await call.answer("✅ Tasdiqlandi!", show_alert=True)


@router.callback_query(F.data.startswith("admin_reject:"))
async def admin_reject(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    payment_id = int(call.data.split(":")[1])
    payment = await db.get_payment(payment_id)

    if not payment:
        await call.answer("To'lov topilmadi!", show_alert=True)
        return

    if payment["status"] not in ("pending", "waiting_approval"):
        await call.answer("Bu to'lov allaqachon qayta ishlangan!", show_alert=True)
        return

    await db.update_payment_status(payment_id, "rejected")
    user = await db.get_user(payment["telegram_id"])
    now = datetime.now()

    await call.message.edit_text(
        f"❌ <b>TO'LOV RAD ETILDI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 Chek ID:      <code>#{payment_id}</code>\n"
        f"📅 Sana:         {now.strftime('%d.%m.%Y')}\n"
        f"🕐 Vaqt:         {now.strftime('%H:%M:%S')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Foydalanuvchi: <b>{user['full_name']}</b>\n"
        f"🆔 Telegram ID:  <code>{payment['telegram_id']}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 Miqdor:       <b>{payment['amount']:,} so'm</b>\n"
        f"❌ Holat:        <b>RAD ETILDI</b>\n"
        f"👮 Admin:        <b>{call.from_user.full_name}</b>",
        parse_mode="HTML"
    )

    # ── User receives rejection receipt ──────────────────────────────────
    try:
        await bot.send_message(
            payment["telegram_id"],
            f"❌ <b>TO'LOV RAD ETILDI</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 Chek ID:      <code>#{payment_id}</code>\n"
            f"📅 Sana:         {now.strftime('%d.%m.%Y')}\n"
            f"🕐 Vaqt:         {now.strftime('%H:%M:%S')}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🏦 Bank:         <b>{BANK_NAME}</b>\n"
            f"💵 Miqdor:       <b>{payment['amount']:,} so'm</b>\n"
            f"❌ Holat:        <b>RAD ETILDI</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ Muammo bo'lsa admin bilan bog'laning.\n"
            f"Qaytadan urinib ko'rishingiz mumkin.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Qaytadan to'lov", callback_data="start_payment")],
                [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back_main")],
            ]),
            parse_mode="HTML"
        )
    except Exception:
        pass

    await call.answer("❌ Rad etildi!", show_alert=True)


@router.callback_query(F.data == "admin_back")
async def admin_back(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    users = await db.get_all_users()
    pending = await db.get_all_pending_payments()

    await call.message.edit_text(
        f"🛠 <b>ADMIN PANEL</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{len(users)}</b>\n"
        f"⏳ Kutilayotgan to'lovlar: <b>{len(pending)}</b>\n",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin_users")],
            [InlineKeyboardButton(text="⏳ Kutilayotgan to'lovlar", callback_data="admin_pending")],
            [InlineKeyboardButton(text="📢 Hammaga xabar", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="💰 Balans qo'shish", callback_data="admin_add_balance")],
        ]),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    await state.set_state(BroadcastState.waiting_message)
    await call.message.edit_text(
        "📢 <b>Hammaga xabar yuborish</b>\n\n"
        "Barcha foydalanuvchilarga yubormoqchi bo'lgan xabarni yozing:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_back")]
        ]),
        parse_mode="HTML"
    )
    await call.answer()


@router.message(BroadcastState.waiting_message)
async def broadcast_send(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return

    await state.clear()
    users = await db.get_all_users()

    sent = 0
    failed = 0
    for user in users:
        try:
            await bot.send_message(
                user["telegram_id"],
                f"📢 <b>Xabar admindan:</b>\n\n{message.text}",
                parse_mode="HTML"
            )
            sent += 1
        except Exception:
            failed += 1

    await message.answer(
        f"✅ Xabar yuborildi!\n\n"
        f"✅ Muvaffaqiyatli: {sent}\n"
        f"❌ Xato: {failed}",
        parse_mode="HTML"
    )


class AddBalanceState(StatesGroup):
    waiting_user_id = State()
    waiting_amount = State()


@router.callback_query(F.data == "admin_add_balance")
async def admin_add_balance_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    await state.set_state(AddBalanceState.waiting_user_id)
    await call.message.edit_text(
        "💰 <b>Balans qo'shish</b>\n\n"
        "Foydalanuvchi Telegram ID sini yuboring:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_back")]
        ]),
        parse_mode="HTML"
    )
    await call.answer()


@router.message(AddBalanceState.waiting_user_id)
async def add_balance_get_user(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Noto'g'ri ID. Raqam kiriting:")
        return

    user = await db.get_user(user_id)
    if not user:
        await message.answer("❌ Bu ID li foydalanuvchi topilmadi!")
        return

    await state.update_data(target_user_id=user_id, target_name=user["full_name"])
    await state.set_state(AddBalanceState.waiting_amount)
    await message.answer(
        f"👤 Foydalanuvchi: <b>{user['full_name']}</b>\n"
        f"💰 Joriy balans: <b>{user['balance']:,} so'm</b>\n\n"
        f"Qo'shmoqchi bo'lgan miqdorni kiriting (so'mda):",
        parse_mode="HTML"
    )


@router.message(AddBalanceState.waiting_amount)
async def add_balance_finish(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return

    try:
        amount = int(message.text.strip().replace(" ", "").replace(",", ""))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Noto'g'ri miqdor. Musbat son kiriting:")
        return

    data = await state.get_data()
    target_id = data["target_user_id"]
    target_name = data["target_name"]
    await state.clear()

    await db.update_user_balance(target_id, amount)
    user = await db.get_user(target_id)
    now = datetime.now()

    await message.answer(
        f"✅ <b>Balans qo'shildi!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Foydalanuvchi: <b>{target_name}</b>\n"
        f"🆔 ID: <code>{target_id}</code>\n"
        f"💵 Qo'shildi: <b>+{amount:,} so'm</b>\n"
        f"💰 Yangi balans: <b>{user['balance']:,} so'm</b>",
        parse_mode="HTML"
    )

    try:
        await bot.send_message(
            target_id,
            f"💰 <b>Balansingiz to'ldirildi!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 Sana: {now.strftime('%d.%m.%Y %H:%M')}\n"
            f"💵 Qo'shildi: <b>+{amount:,} so'm</b>\n"
            f"💰 Yangi balans: <b>{user['balance']:,} so'm</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"Admin tomonidan qo'shildi. ✅",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 Balansimni ko'rish", callback_data="my_balance")],
            ]),
            parse_mode="HTML"
        )
    except Exception:
        pass
