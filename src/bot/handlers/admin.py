from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from src.bot.inline_keyboards import pending_request_inline
from src.bot.keyboards import admin_main_keyboard
from src.db.models import Certificate, RewardLevel, User
from src.db.session import SessionLocal
from src.services.admin_service import approve_certificate, list_pending_requests, reject_certificate
from src.services.auth_service import get_active_admin
from src.services.stats_service import collect_dashboard_stats

router = Router(name="admin")


class RejectState(StatesGroup):
    waiting_reason = State()


async def _get_admin_or_reject(message: Message) -> int | None:
    if not message.from_user:
        return None

    async with SessionLocal() as db:
        admin = await get_active_admin(db, telegram_id=message.from_user.id)

    if not admin:
        await message.answer("Sizda admin huquqi yo'q.")
        return None
    return admin.id


async def _get_admin_from_callback(callback: CallbackQuery) -> int | None:
    if not callback.from_user:
        return None

    async with SessionLocal() as db:
        admin = await get_active_admin(db, telegram_id=callback.from_user.id)

    if not admin:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return None
    return admin.id


@router.message(Command("admin"))
async def admin_start_handler(message: Message) -> None:
    admin_id = await _get_admin_or_reject(message)
    if not admin_id:
        return
    await message.answer("Admin menyu", reply_markup=admin_main_keyboard())


@router.message(F.text == "⏳ So'rovlar")
async def pending_requests_handler(message: Message) -> None:
    admin_id = await _get_admin_or_reject(message)
    if not admin_id:
        return

    async with SessionLocal() as db:
        pending = await list_pending_requests(db)
        if not pending:
            await message.answer("Pending so'rovlar mavjud emas.")
            return

        for req in pending[:20]:
            cert = await db.get(Certificate, req.certificate_id)
            if not cert:
                continue
            user = await db.get(User, cert.user_id)
            level = await db.get(RewardLevel, cert.reward_level_id)
            level_name = level.reward_name if level else "Noma'lum"
            level_count = level.required_count if level else 0
            await message.answer(
                f"So'rov #{req.id}\n"
                f"User: {user.full_name if user else cert.user_id}\n"
                f"Telegram ID: {user.telegram_id if user else '-'}\n"
                f"Sovg'a: {level_name}\n"
                f"Bosqich: {level_count}\n"
                f"Sertifikat ID: {cert.id}\n"
                f"Yuborilgan vaqt: {req.created_at}",
                reply_markup=pending_request_inline(cert.id),
            )


@router.callback_query(F.data.startswith("admin:approve:"))
async def approve_handler(callback: CallbackQuery) -> None:
    admin_id = await _get_admin_from_callback(callback)
    if not admin_id or not callback.data:
        return

    cert_id = int(callback.data.split(":")[-1])

    async with SessionLocal() as db:
        promo = await approve_certificate(db, certificate_id=cert_id, admin_id=admin_id, shop_id=None)
        cert = await db.get(Certificate, cert_id)
        cert_user = await db.get(User, cert.user_id) if cert else None
        if promo:
            await db.commit()

    if promo:
        await callback.message.answer(f"Tasdiqlandi. Promo kod: {promo.code}")
        if cert_user:
            await callback.message.bot.send_message(
                cert_user.telegram_id,
                "Sertifikatingiz tasdiqlandi.\n"
                f"Promo kod: {promo.code}\n"
                "Sovg'ani olish bo'yicha ma'lumot uchun admin bilan bog'laning.",
            )
    else:
        await callback.message.answer("Tasdiqlash amalga oshmadi.")
    await callback.answer()


@router.callback_query(F.data.startswith("admin:reject:"))
async def reject_start_handler(callback: CallbackQuery, state: FSMContext) -> None:
    admin_id = await _get_admin_from_callback(callback)
    if not admin_id or not callback.data:
        return

    cert_id = int(callback.data.split(":")[-1])
    await state.set_state(RejectState.waiting_reason)
    await state.update_data(certificate_id=cert_id)
    await callback.message.answer("Rad etish sababini yuboring:")
    await callback.answer()


@router.message(RejectState.waiting_reason)
async def reject_reason_handler(message: Message, state: FSMContext) -> None:
    if not message.from_user:
        return

    async with SessionLocal() as db:
        admin = await get_active_admin(db, telegram_id=message.from_user.id)
        if not admin:
            await message.answer("Sizda admin huquqi yo'q.")
            await state.clear()
            return

        data = await state.get_data()
        cert_id = int(data.get("certificate_id", 0))
        cert = await db.get(Certificate, cert_id)
        cert_user = await db.get(User, cert.user_id) if cert else None
        ok = await reject_certificate(db, certificate_id=cert_id, admin_id=admin.id, reason=message.text or "Sabab berilmadi")
        if ok:
            await db.commit()

    await state.clear()
    if ok:
        await message.answer("So'rov rad etildi.")
        if cert_user:
            await message.bot.send_message(
                cert_user.telegram_id,
                f"Afsuski, sertifikatdan foydalanish so'rovingiz rad etildi.\nSabab: {message.text or 'Sabab berilmadi'}",
            )
    else:
        await message.answer("Rad etish amalga oshmadi.")


@router.message(F.text == "📊 Statistika")
async def stats_handler(message: Message) -> None:
    admin_id = await _get_admin_or_reject(message)
    if not admin_id:
        return

    async with SessionLocal() as db:
        stats = await collect_dashboard_stats(db)

    await message.answer(
        "Statistika:\n"
        f"- Jami userlar: {stats.total_users}\n"
        f"- Bugungi yangi userlar: {stats.today_new_users}\n"
        f"- Pending sertifikatlar: {stats.pending_certificates}\n"
        f"- Approved sertifikatlar: {stats.approved_certificates}\n"
        f"- Used sertifikatlar: {stats.used_certificates}\n"
        f"- Rejected sertifikatlar: {stats.rejected_certificates}"
    )
