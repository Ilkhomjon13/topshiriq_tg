from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from src.bot.inline_keyboards import (
    certificate_use_inline,
    confirm_use_inline,
    task_detail_inline,
    task_list_inline,
)
from src.bot.keyboards import user_main_keyboard
from src.core.config import get_settings
from src.db.session import SessionLocal
from src.services.certificate_service import get_user_certificates, get_user_task_certificates, request_redemption
from src.services.referral_service import get_or_create_user, get_task_referral_count, get_user_by_telegram_id, register_referral
from src.services.task_service import (
    get_task_by_id,
    get_task_levels,
    is_user_participant,
    join_task,
    list_active_tasks,
    list_user_tasks,
)
from src.utils.referral_codes import build_ref_source_code, parse_ref_source_code

router = Router(name="user")
settings = get_settings()


class UseCertificateState(StatesGroup):
    waiting_confirm = State()


def _extract_start_param(message: Message) -> str | None:
    if not message.text:
        return None
    parts = message.text.split(maxsplit=1)
    if len(parts) == 2:
        return parts[1].strip()
    return None


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    if not message.from_user:
        return

    start_param = _extract_start_param(message)

    async with SessionLocal() as db:
        user = await get_or_create_user(
            db,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username,
        )

        if start_param:
            source = parse_ref_source_code(start_param)
            if source:
                await register_referral(
                    db,
                    task_id=source.task_id,
                    inviter_user_id=source.inviter_user_id,
                    invited_user_id=user.id,
                    source_code=start_param,
                )

        await db.commit()

    text = (
        f"Assalomu alaykum, {user.full_name}.\n"
        "@topibolindi topshiriqlar botiga xush kelibsiz.\n"
        "Quyidagi bo'limlardan birini tanlang."
    )
    await message.answer(text, reply_markup=user_main_keyboard())


@router.message(F.text == "📋 Topshiriqlar")
async def tasks_handler(message: Message) -> None:
    async with SessionLocal() as db:
        tasks = await list_active_tasks(db)

    if not tasks:
        await message.answer("Hozircha aktiv topshiriqlar mavjud emas.")
        return

    kb = task_list_inline([(task.id, task.title) for task in tasks])
    await message.answer("Aktiv topshiriqlardan birini tanlang:", reply_markup=kb)


@router.callback_query(F.data.startswith("task:view:"))
async def task_view_handler(callback: CallbackQuery) -> None:
    if not callback.data:
        return
    task_id = int(callback.data.split(":")[-1])

    async with SessionLocal() as db:
        task = await get_task_by_id(db, task_id)
        levels = await get_task_levels(db, task_id)

    if not task:
        await callback.answer("Topshiriq topilmadi.", show_alert=True)
        return

    level_lines = [f"{level.required_count} ta - {level.reward_name}" for level in levels]
    text = (
        f"{task.title}\n\n"
        f"{task.description}\n\n"
        f"Qoidalar: {task.rules_text}\n\n"
        "Sovg'a bosqichlari:\n"
        + ("\n".join(level_lines) if level_lines else "- Bosqichlar hali kiritilmagan")
    )
    await callback.message.answer(text, reply_markup=task_detail_inline(task_id))
    await callback.answer()


@router.callback_query(F.data == "task:back")
async def task_back_handler(callback: CallbackQuery) -> None:
    await callback.message.answer("Asosiy menyu", reply_markup=user_main_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("task:join:"))
async def task_join_handler(callback: CallbackQuery) -> None:
    if not callback.data or not callback.from_user:
        return

    task_id = int(callback.data.split(":")[-1])

    async with SessionLocal() as db:
        user = await get_or_create_user(
            db,
            telegram_id=callback.from_user.id,
            full_name=callback.from_user.full_name,
            username=callback.from_user.username,
        )
        await join_task(db, task_id=task_id, user_id=user.id)
        await db.commit()

    source_code = build_ref_source_code(task_id=task_id, inviter_user_id=user.id)
    ref_link = f"https://t.me/{settings.base_bot_username}?start={source_code}"

    await callback.message.answer(
        "Siz topshiriqqa qo'shildingiz.\n"
        "Taklif uchun maxsus havolangiz:\n"
        f"{ref_link}\n\n"
        "Eslatma: referal botga shu havola orqali kirib /start qilganda hisoblanadi."
    )
    await callback.answer("Qatnashish muvaffaqiyatli")


@router.callback_query(F.data.startswith("task:progress:"))
async def task_progress_handler(callback: CallbackQuery) -> None:
    if not callback.data or not callback.from_user:
        return

    task_id = int(callback.data.split(":")[-1])

    async with SessionLocal() as db:
        user = await get_user_by_telegram_id(db, telegram_id=callback.from_user.id)
        if not user:
            await callback.message.answer("Avval /start yuboring.")
            await callback.answer()
            return

        if not await is_user_participant(db, task_id=task_id, user_id=user.id):
            await callback.message.answer("Avval ushbu topshiriqqa qatnashing.")
            await callback.answer()
            return

        current_count = await get_task_referral_count(db, task_id=task_id, inviter_user_id=user.id)
        levels = await get_task_levels(db, task_id=task_id)

    next_level = next((level for level in levels if level.required_count > current_count), None)
    if next_level:
        remain = next_level.required_count - current_count
        msg = (
            f"Siz {current_count} ta odam taklif qildingiz.\n"
            f"Keyingi sovg'agacha {remain} ta odam qoldi.\n"
            f"Eng yaqin sovg'a: {next_level.reward_name}."
        )
    else:
        msg = f"Siz {current_count} ta odam taklif qilgansiz. Siz eng yuqori bosqichdasiz."

    await callback.message.answer(msg)
    await callback.answer()


@router.callback_query(F.data.startswith("task:gifts:"))
async def task_gifts_handler(callback: CallbackQuery) -> None:
    if not callback.data or not callback.from_user:
        return

    task_id = int(callback.data.split(":")[-1])

    async with SessionLocal() as db:
        user = await get_user_by_telegram_id(db, telegram_id=callback.from_user.id)
        if not user:
            await callback.message.answer("Avval /start yuboring.")
            await callback.answer()
            return

        certs = await get_user_task_certificates(db, user_id=user.id, task_id=task_id)

    if not certs:
        await callback.message.answer("Sizda bu topshiriq bo'yicha sertifikatlar yo'q.")
        await callback.answer()
        return

    for cert, level in certs:
        text = (
            f"Sovg'a: {level.reward_name}\n"
            f"Bosqich: {level.required_count} ta\n"
            f"Sertifikat ID: {cert.id}\n"
            f"Kod: {cert.certificate_code}\n"
            f"Holat: {cert.status}"
        )
        markup = certificate_use_inline(cert.id) if cert.status == "available" else None
        await callback.message.answer(text, reply_markup=markup)

    await callback.answer()


@router.callback_query(F.data.startswith("cert:use:"))
async def certificate_use_handler(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data:
        return
    cert_id = int(callback.data.split(":")[-1])
    await state.set_state(UseCertificateState.waiting_confirm)
    await state.update_data(certificate_id=cert_id)
    await callback.message.answer(
        "Siz ushbu sertifikatdan foydalanish uchun so'rov yubormoqchisiz.\n"
        "Admin tasdiqlagach sovg'ani olish uchun manzil, telefon va promo kod yuboriladi.",
        reply_markup=confirm_use_inline(),
    )
    await callback.answer()


@router.callback_query(UseCertificateState.waiting_confirm, F.data == "cert:cancel")
async def cert_confirm_cancel_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer("So'rov bekor qilindi.")
    await callback.answer()


@router.callback_query(UseCertificateState.waiting_confirm, F.data == "cert:confirm")
async def cert_confirm_handler(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.from_user:
        return

    data = await state.get_data()
    cert_id = int(data.get("certificate_id", 0))
    ok = False

    async with SessionLocal() as db:
        user = await get_user_by_telegram_id(db, telegram_id=callback.from_user.id)
        if not user:
            await callback.message.answer("Avval /start yuboring.")
            await callback.answer()
            await state.clear()
            return

        ok = await request_redemption(db, certificate_id=cert_id, user_id=user.id)
        if ok:
            await db.commit()

    await state.clear()
    if ok:
        await callback.message.answer("So'rovingiz adminga yuborildi. Iltimos, tasdiqlanishini kuting.")
    else:
        await callback.message.answer("So'rov yuborilmadi. Sertifikat holatini tekshiring.")
    await callback.answer()


@router.message(F.text == "📊 Mening natijam")
async def result_handler(message: Message) -> None:
    if not message.from_user:
        return

    async with SessionLocal() as db:
        user = await get_user_by_telegram_id(db, telegram_id=message.from_user.id)
        if not user:
            await message.answer("Avval /start yuboring.")
            return

        tasks = await list_user_tasks(db, user_id=user.id)
        if not tasks:
            await message.answer("Siz hali hech qaysi topshiriqqa qo'shilmagansiz.")
            return

        lines: list[str] = []
        for task in tasks:
            count = await get_task_referral_count(db, task_id=task.id, inviter_user_id=user.id)
            levels = await get_task_levels(db, task_id=task.id)
            next_level = next((level for level in levels if level.required_count > count), None)
            if next_level:
                lines.append(f"{task.title}: {count} ta, keyingi sovg'agacha {next_level.required_count - count} ta")
            else:
                lines.append(f"{task.title}: {count} ta, maksimal bosqichga yetgansiz")

    await message.answer("\n".join(lines))


@router.message(F.text == "🏆 Mening sovg'alarim")
async def gifts_handler(message: Message) -> None:
    if not message.from_user:
        return

    async with SessionLocal() as db:
        user = await get_user_by_telegram_id(db, telegram_id=message.from_user.id)
        if not user:
            await message.answer("Avval /start yuboring.")
            return

        certs = await get_user_certificates(db, user_id=user.id)

    if not certs:
        await message.answer("Sizda sertifikatlar mavjud emas.")
        return

    for cert in certs:
        text = f"ID: {cert.id}\nKod: {cert.certificate_code}\nHolat: {cert.status}"
        markup = certificate_use_inline(cert.id) if cert.status == "available" else None
        await message.answer(text, reply_markup=markup)


@router.message(F.text == "👤 Profilim")
async def profile_handler(message: Message) -> None:
    if not message.from_user:
        return

    async with SessionLocal() as db:
        user = await get_user_by_telegram_id(db, telegram_id=message.from_user.id)

    if not user:
        await message.answer("Avval /start yuboring.")
        return

    await message.answer(
        f"Ism: {user.full_name}\n"
        f"Username: @{user.username if user.username else '-'}\n"
        f"Telegram ID: {user.telegram_id}\n"
        f"Jami referal: {user.total_referrals}\n"
        f"Holat: {'bloklangan' if user.is_blocked else 'active'}"
    )


@router.message(F.text == "ℹ️ Qoidalar")
async def rules_handler(message: Message) -> None:
    await message.answer(
        "Qoidalar:\n"
        "- faqat haqiqiy foydalanuvchilar hisoblanadi\n"
        "- fake akkauntlar hisobga olinmaydi\n"
        "- bir foydalanuvchi bir marta hisoblanadi\n"
        "- o'z-o'zini referal qilish taqiqlanadi\n"
        "- promo kod bir martalik"
    )


@router.message(F.text == "📞 Yordam")
async def help_handler(message: Message) -> None:
    await message.answer("Yordam uchun admin bilan bog'laning: @topibolindi")
