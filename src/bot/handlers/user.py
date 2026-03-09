import re

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from src.bot.keyboards import (
    user_certificates_keyboard,
    user_confirm_keyboard,
    user_main_keyboard,
    user_task_actions_keyboard,
    user_tasks_keyboard,
)
from src.db.session import SessionLocal
from src.services.certificate_service import (
    get_user_certificates,
    request_redemption,
)
from src.services.referral_service import (
    get_or_create_user,
    get_task_referral_count,
    get_user_by_telegram_id,
    register_referral,
)
from src.services.task_service import (
    get_task_by_id,
    get_task_levels,
    is_user_participant,
    join_task,
    list_active_tasks,
    list_user_tasks,
)
from src.utils.referral_codes import parse_ref_source_code

router = Router(name="user")


class UserFlowState(StatesGroup):
    selecting_task = State()
    task_actions = State()
    choosing_certificate = State()
    confirm_certificate = State()


def _extract_start_param(message: Message) -> str | None:
    if not message.text:
        return None
    parts = message.text.split(maxsplit=1)
    if len(parts) == 2:
        return parts[1].strip()
    return None


def _task_id_from_button(text: str) -> int | None:
    # button format: "📌 {id}. title"
    match = re.match(r"^📌\s+(\d+)\.", text.strip())
    if not match:
        return None
    return int(match.group(1))


def _cert_id_from_button(text: str) -> int | None:
    # button format: "🎁 Foydalanish #{id}"
    match = re.match(r"^🎁\s+Foydalanish\s+#(\d+)$", text.strip())
    if not match:
        return None
    return int(match.group(1))


async def _send_task_card(message: Message, task_id: int, user_id: int) -> None:
    async with SessionLocal() as db:
        task = await get_task_by_id(db, task_id)
        if not task:
            await message.answer("Topshiriq topilmadi.", reply_markup=user_main_keyboard())
            return
        joined = await is_user_participant(db, task_id=task_id, user_id=user_id)
        has_group_link = bool((task.group_link or "").strip())

    short_description = (task.description or "").strip()
    if len(short_description) > 220:
        short_description = short_description[:217].rstrip() + "..."
    text = f"{task.title}\n\n{short_description}"

    if task.image_file_id:
        await message.answer_photo(
            photo=task.image_file_id,
            caption=text,
            reply_markup=user_task_actions_keyboard(is_joined=joined, has_group_link=has_group_link),
        )
    else:
        await message.answer(text, reply_markup=user_task_actions_keyboard(is_joined=joined, has_group_link=has_group_link))


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext) -> None:
    if not message.from_user:
        return

    await state.clear()
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
        "Topshiriqlar botiga xush kelibsiz.\n"
        "Quyidagi bo'limlardan birini tanlang."
    )
    await message.answer(text, reply_markup=user_main_keyboard())


@router.message(F.text == "📋 Topshiriqlar")
async def tasks_handler(message: Message, state: FSMContext) -> None:
    async with SessionLocal() as db:
        tasks = await list_active_tasks(db)

    if not tasks:
        await message.answer("Hozircha aktiv topshiriqlar mavjud emas.", reply_markup=user_main_keyboard())
        return

    await state.set_state(UserFlowState.selecting_task)
    await message.answer(
        "Aktiv topshiriqlardan birini tanlang:",
        reply_markup=user_tasks_keyboard([(task.id, task.title) for task in tasks]),
    )


@router.message(UserFlowState.selecting_task)
async def select_task_handler(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == "🔙 Orqaga":
        await state.clear()
        await message.answer("Asosiy menyu", reply_markup=user_main_keyboard())
        return

    task_id = _task_id_from_button(text)
    if not task_id or not message.from_user:
        await message.answer("Topshiriqni tugmadan tanlang.")
        return

    async with SessionLocal() as db:
        user = await get_user_by_telegram_id(db, telegram_id=message.from_user.id)

    if not user:
        await message.answer("Avval /start yuboring.", reply_markup=user_main_keyboard())
        await state.clear()
        return

    await state.set_state(UserFlowState.task_actions)
    await state.update_data(task_id=task_id)
    await _send_task_card(message, task_id=task_id, user_id=user.id)


@router.message(UserFlowState.task_actions, F.text == "🔙 Orqaga")
async def task_actions_back_handler(message: Message, state: FSMContext) -> None:
    async with SessionLocal() as db:
        tasks = await list_active_tasks(db)

    await state.set_state(UserFlowState.selecting_task)
    await message.answer(
        "Topshiriqlar ro'yxati:",
        reply_markup=user_tasks_keyboard([(task.id, task.title) for task in tasks]),
    )


@router.message(UserFlowState.task_actions, F.text.in_({"✅ Qatnashish", "✅ Siz qatnashyapsiz"}))
async def task_join_handler(message: Message, state: FSMContext) -> None:
    if not message.from_user:
        return

    data = await state.get_data()
    task_id = int(data.get("task_id", 0))
    if task_id <= 0:
        await message.answer("Topshiriq tanlanmagan.")
        return

    async with SessionLocal() as db:
        user = await get_or_create_user(
            db,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username,
        )
        already_joined = await is_user_participant(db, task_id=task_id, user_id=user.id)
        await join_task(db, task_id=task_id, user_id=user.id)
        await db.commit()

    await _send_task_card(message, task_id=task_id, user_id=user.id)
    if already_joined:
        await message.answer("Siz allaqachon ushbu topshiriqda qatnashyapsiz.")
        return

    await message.answer(
        "Siz topshiriqda qatnashyapsiz.\n"
        "Endi guruhga odamlarni qo'lda qo'shing, bot qo'shish servis xabari bo'yicha hisoblaydi."
    )


@router.message(UserFlowState.task_actions, F.text == "📈 Progressim")
async def task_progress_handler(message: Message, state: FSMContext) -> None:
    if not message.from_user:
        return

    data = await state.get_data()
    task_id = int(data.get("task_id", 0))
    if task_id <= 0:
        await message.answer("Topshiriq tanlanmagan.")
        return

    async with SessionLocal() as db:
        user = await get_user_by_telegram_id(db, telegram_id=message.from_user.id)
        if not user:
            await message.answer("Avval /start yuboring.")
            return

        if not await is_user_participant(db, task_id=task_id, user_id=user.id):
            await message.answer("Avval ushbu topshiriqqa qatnashing.")
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

    await message.answer(msg)


@router.message(UserFlowState.task_actions, F.text == "ℹ️ Qoidalar")
async def task_rules_handler(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    task_id = int(data.get("task_id", 0))
    if task_id <= 0:
        await message.answer("Topshiriq tanlanmagan.")
        return

    async with SessionLocal() as db:
        task = await get_task_by_id(db, task_id)

    if not task:
        await message.answer("Topshiriq topilmadi.")
        return

    await message.answer(f"Qoidalar:\n{task.rules_text}")


@router.message(UserFlowState.task_actions, F.text == "🎁 Sovg'alar")
async def task_rewards_handler(message: Message, state: FSMContext) -> None:
    if not message.from_user:
        return

    data = await state.get_data()
    task_id = int(data.get("task_id", 0))
    if task_id <= 0:
        await message.answer("Topshiriq tanlanmagan.")
        return

    async with SessionLocal() as db:
        user = await get_user_by_telegram_id(db, telegram_id=message.from_user.id)
        levels = await get_task_levels(db, task_id=task_id)
        current_count = 0
        if user:
            current_count = await get_task_referral_count(db, task_id=task_id, inviter_user_id=user.id)

    if not levels:
        await message.answer("Sovg'a bosqichlari hali kiritilmagan.")
        return

    await message.answer(f"Sizning joriy natijangiz: {current_count} ta odam.")

    cards_sent = 0
    for level in levels:
        required = level.required_count
        progress_percent = min(100, int((current_count / required) * 100)) if required > 0 else 0
        filled = min(10, progress_percent // 10)
        bar = "█" * filled + "░" * (10 - filled)

        if current_count >= required:
            status_text = "✅ Ushbu sertifikat bosqichiga yetgansiz."
            remain_text = "Keyingi bosqichga o'tishingiz mumkin."
        else:
            remaining = required - current_count
            status_text = f"⏳ Yana {remaining} ta odam qoldi."
            remain_text = f"{required} talik sertifikatni faollashtirish uchun {remaining} ta kerak."

        card_text = (
            f"🏆 {level.reward_name}\n"
            f"🎯 Talab: {required} ta odam\n"
            f"📈 Hozir: {current_count} ta odam\n"
            f"📊 Progress: {bar} {progress_percent}%\n"
            f"{status_text}\n"
            f"{remain_text}"
        )
        if level.reward_description:
            card_text += f"\n📝 {level.reward_description}"

        if level.reward_image_file_id:
            await message.answer_photo(photo=level.reward_image_file_id, caption=card_text)
        else:
            await message.answer(card_text)
        cards_sent += 1

    if cards_sent == 0:
        await message.answer("Sovg'a kartalari topilmadi.")


@router.message(UserFlowState.task_actions, F.text == "🔗 Guruhga o'tish")
async def task_group_link_handler(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    task_id = int(data.get("task_id", 0))
    if task_id <= 0:
        await message.answer("Topshiriq tanlanmagan.")
        return

    async with SessionLocal() as db:
        task = await get_task_by_id(db, task_id=task_id)

    if not task or not (task.group_link or "").strip():
        await message.answer("Bu topshiriq uchun guruh havolasi kiritilmagan.")
        return

    await message.answer(f"Guruhga o'tish havolasi:\n{task.group_link}")


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

    await message.answer("\n".join(lines), reply_markup=user_main_keyboard())


@router.message(F.text == "🏆 Mening sovg'alarim")
async def gifts_handler(message: Message, state: FSMContext) -> None:
    if not message.from_user:
        return

    async with SessionLocal() as db:
        user = await get_user_by_telegram_id(db, telegram_id=message.from_user.id)
        if not user:
            await message.answer("Avval /start yuboring.")
            return

        certs = await get_user_certificates(db, user_id=user.id)

    if not certs:
        await message.answer("Sizda sertifikatlar mavjud emas.", reply_markup=user_main_keyboard())
        return

    available_ids: list[int] = []
    for cert in certs:
        await message.answer(f"ID: {cert.id}\nKod: {cert.certificate_code}\nHolat: {cert.status}")
        if cert.status == "available":
            available_ids.append(cert.id)

    if available_ids:
        await state.set_state(UserFlowState.choosing_certificate)
        await message.answer(
            "Foydalanish uchun sertifikat tanlang:",
            reply_markup=user_certificates_keyboard(available_ids),
        )
    else:
        await state.clear()
        await message.answer("Aktiv sertifikat yo'q.", reply_markup=user_main_keyboard())


@router.message(UserFlowState.choosing_certificate)
async def choose_certificate_handler(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == "🔙 Orqaga":
        await state.clear()
        await message.answer("Asosiy menyu", reply_markup=user_main_keyboard())
        return

    cert_id = _cert_id_from_button(text)
    if not cert_id:
        await message.answer("Sertifikatni tugmadan tanlang.")
        return

    await state.set_state(UserFlowState.confirm_certificate)
    await state.update_data(certificate_id=cert_id)
    await message.answer(
        "Siz ushbu sertifikatdan foydalanish uchun so'rov yubormoqchisiz.\n"
        "Admin tasdiqlagach sovg'ani olish uchun ma'lumot yuboriladi.",
        reply_markup=user_confirm_keyboard(),
    )


@router.message(UserFlowState.confirm_certificate, F.text.in_({"❌ Bekor qilish", "🔙 Orqaga"}))
async def cert_confirm_cancel_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("So'rov bekor qilindi.", reply_markup=user_main_keyboard())


@router.message(UserFlowState.confirm_certificate, F.text == "✅ Tasdiqlayman")
async def cert_confirm_handler(message: Message, state: FSMContext) -> None:
    if not message.from_user:
        return

    data = await state.get_data()
    cert_id = int(data.get("certificate_id", 0))
    ok = False

    async with SessionLocal() as db:
        user = await get_user_by_telegram_id(db, telegram_id=message.from_user.id)
        if not user:
            await message.answer("Avval /start yuboring.")
            await state.clear()
            return

        ok = await request_redemption(db, certificate_id=cert_id, user_id=user.id)
        if ok:
            await db.commit()

    await state.clear()
    if ok:
        await message.answer("So'rovingiz adminga yuborildi. Iltimos, tasdiqlanishini kuting.", reply_markup=user_main_keyboard())
    else:
        await message.answer("So'rov yuborilmadi. Sertifikat holatini tekshiring.", reply_markup=user_main_keyboard())


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
        f"Holat: {'bloklangan' if user.is_blocked else 'active'}",
        reply_markup=user_main_keyboard(),
    )


@router.message(F.text == "ℹ️ Qoidalar")
async def rules_handler(message: Message) -> None:
    await message.answer(
        "Qoidalar:\n"
        "- faqat haqiqiy foydalanuvchilar hisoblanadi\n"
        "- fake akkauntlar hisobga olinmaydi\n"
        "- bir foydalanuvchi bir marta hisoblanadi\n"
        "- o'z-o'zini referal qilish taqiqlanadi\n"
        "- promo kod bir martalik",
        reply_markup=user_main_keyboard(),
    )


@router.message(F.text == "📞 Yordam")
async def help_handler(message: Message) -> None:
    await message.answer("Yordam uchun admin bilan bog'laning: @topibolindi", reply_markup=user_main_keyboard())
