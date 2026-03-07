from aiogram import F, Router
from aiogram.filters import Command, Filter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from src.bot.inline_keyboards import pending_request_inline
from src.bot.keyboards import admin_main_keyboard
from src.core.config import get_settings
from src.core.enums import TaskStatus
from src.db.models import Admin, AuditLog, Certificate, RewardLevel, Task, User
from src.db.session import SessionLocal
from src.services.admin_service import approve_certificate, list_pending_requests_view, reject_certificate
from src.services.auth_service import get_active_admin
from src.services.stats_service import collect_dashboard_stats

router = Router(name="admin")
settings = get_settings()


class IsAdminFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        if not message.from_user:
            return False
        async with SessionLocal() as db:
            admin = await get_active_admin(db, telegram_id=message.from_user.id)
        if admin is not None:
            setattr(message, "_admin_cached", admin)
        return admin is not None


class RejectState(StatesGroup):
    waiting_reason = State()


class AddTaskState(StatesGroup):
    waiting_title = State()
    waiting_description = State()
    waiting_rules = State()
    waiting_group_link = State()
    waiting_image = State()


class BroadcastState(StatesGroup):
    waiting_text = State()


class RewardManageState(StatesGroup):
    waiting_required_count = State()
    waiting_reward_name = State()
    waiting_reward_description = State()
    waiting_reward_image = State()


async def _get_admin_or_reject(message: Message) -> Admin | None:
    if not message.from_user:
        return None
    cached_admin = getattr(message, "_admin_cached", None)
    if cached_admin is not None:
        return cached_admin

    async with SessionLocal() as db:
        admin = await get_active_admin(db, telegram_id=message.from_user.id)

    if not admin:
        await message.answer("Sizda admin huquqi yo'q.")
        return None
    return admin


async def _get_admin_from_callback(callback: CallbackQuery) -> Admin | None:
    if not callback.from_user:
        return None

    async with SessionLocal() as db:
        admin = await get_active_admin(db, telegram_id=callback.from_user.id)

    if not admin:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return None
    return admin


def _task_action_keyboard(task_id: int, is_active: bool) -> InlineKeyboardMarkup:
    stop_text = "⏹ To'xtatish" if is_active else "▶️ Faollashtirish"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=stop_text, callback_data=f"admin:task_stop:{task_id}")],
            [InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"admin:task_delete:{task_id}")],
        ]
    )


@router.message(Command("admin"))
async def admin_start_handler(message: Message) -> None:
    admin = await _get_admin_or_reject(message)
    if not admin:
        return
    await message.answer(f"Admin menyu ({admin.role})", reply_markup=admin_main_keyboard())


@router.message(IsAdminFilter(), Command("block_user"))
async def block_user_cmd(message: Message) -> None:
    admin = await _get_admin_or_reject(message)
    if not admin:
        return

    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Foydalanish: /block_user <telegram_id>")
        return

    tg_id = int(parts[1])
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.telegram_id == tg_id))
        if not user:
            await message.answer("User topilmadi.")
            return
        user.is_blocked = True
        db.add(AuditLog(actor_type="admin", actor_id=admin.id, action="user_blocked", entity_type="user", entity_id=user.id, payload_json={}))
        await db.commit()

    await message.answer(f"User bloklandi: {tg_id}")


@router.message(IsAdminFilter(), Command("unblock_user"))
async def unblock_user_cmd(message: Message) -> None:
    admin = await _get_admin_or_reject(message)
    if not admin:
        return

    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Foydalanish: /unblock_user <telegram_id>")
        return

    tg_id = int(parts[1])
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.telegram_id == tg_id))
        if not user:
            await message.answer("User topilmadi.")
            return
        user.is_blocked = False
        db.add(AuditLog(actor_type="admin", actor_id=admin.id, action="user_unblocked", entity_type="user", entity_id=user.id, payload_json={}))
        await db.commit()

    await message.answer(f"User blokdan ochildi: {tg_id}")


@router.message(IsAdminFilter(), Command("task_stop"))
async def task_stop_cmd(message: Message) -> None:
    admin = await _get_admin_or_reject(message)
    if not admin:
        return

    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Foydalanish: /task_stop <task_id>")
        return

    task_id = int(parts[1])
    async with SessionLocal() as db:
        task = await db.get(Task, task_id)
        if not task:
            await message.answer("Topshiriq topilmadi.")
            return
        task.status = TaskStatus.INACTIVE.value if task.status == TaskStatus.ACTIVE.value else TaskStatus.ACTIVE.value
        db.add(
            AuditLog(
                actor_type="admin",
                actor_id=admin.id,
                action="task_status_changed",
                entity_type="task",
                entity_id=task.id,
                payload_json={"status": task.status},
            )
        )
        await db.commit()
    await message.answer(f"Task #{task_id} status -> {task.status}")


@router.message(IsAdminFilter(), Command("task_delete"))
async def task_delete_cmd(message: Message) -> None:
    admin = await _get_admin_or_reject(message)
    if not admin:
        return

    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Foydalanish: /task_delete <task_id>")
        return

    task_id = int(parts[1])
    async with SessionLocal() as db:
        task = await db.get(Task, task_id)
        if not task:
            await message.answer("Topshiriq topilmadi.")
            return
        task.status = TaskStatus.ARCHIVED.value
        db.add(
            AuditLog(
                actor_type="admin",
                actor_id=admin.id,
                action="task_archived",
                entity_type="task",
                entity_id=task.id,
                payload_json={},
            )
        )
        await db.commit()
    await message.answer(f"Task #{task_id} o'chirildi (archived).")


@router.message(IsAdminFilter(), F.text == "📋 Topshiriqlar")
async def tasks_list_handler(message: Message) -> None:
    admin = await _get_admin_or_reject(message)
    if not admin:
        return

    async with SessionLocal() as db:
        tasks = list(
            (
                await db.scalars(
                    select(Task).where(Task.status.in_([TaskStatus.ACTIVE.value, TaskStatus.INACTIVE.value])).order_by(Task.id.asc())
                )
            ).all()
        )
        if not tasks:
            await message.answer("Topshiriqlar yo'q.")
            return

        for task in tasks[:30]:
            await message.answer(
                f"#{task.id} {task.title}\n"
                f"Status: {task.status}\n"
                f"Group: {task.group_link or '-'}\n"
                f"Start: {task.start_date or '-'} | End: {task.end_date or '-'}\n"
                f"Buyruqlar: /task_stop {task.id} | /task_delete {task.id}",
                reply_markup=_task_action_keyboard(task.id, task.status == TaskStatus.ACTIVE.value),
            )


@router.callback_query(F.data.startswith("admin:task_stop:"))
async def task_stop_handler(callback: CallbackQuery) -> None:
    admin = await _get_admin_from_callback(callback)
    if not admin or not callback.data:
        return

    task_id = int(callback.data.split(":")[-1])
    async with SessionLocal() as db:
        task = await db.get(Task, task_id)
        if not task:
            await callback.answer("Topshiriq topilmadi", show_alert=True)
            return
        task.status = TaskStatus.INACTIVE.value if task.status == TaskStatus.ACTIVE.value else TaskStatus.ACTIVE.value
        db.add(AuditLog(actor_type="admin", actor_id=admin.id, action="task_status_changed", entity_type="task", entity_id=task.id, payload_json={"status": task.status}))
        await db.commit()

    await callback.message.answer(f"Task #{task_id} status -> {task.status}")
    await callback.answer()


@router.callback_query(F.data.startswith("admin:task_delete:"))
async def task_delete_handler(callback: CallbackQuery) -> None:
    admin = await _get_admin_from_callback(callback)
    if not admin or not callback.data:
        return

    task_id = int(callback.data.split(":")[-1])
    async with SessionLocal() as db:
        task = await db.get(Task, task_id)
        if not task:
            await callback.answer("Topshiriq topilmadi", show_alert=True)
            return
        # soft delete to keep referral/certificate history intact
        task.status = TaskStatus.ARCHIVED.value
        db.add(
            AuditLog(
                actor_type="admin",
                actor_id=admin.id,
                action="task_archived",
                entity_type="task",
                entity_id=task.id,
                payload_json={},
            )
        )
        await db.commit()

    await callback.message.answer(f"Task #{task_id} o'chirildi (archived).")
    await callback.answer()


@router.message(IsAdminFilter(), F.text == "➕ Topshiriq qo'shish")
async def add_task_start(message: Message, state: FSMContext) -> None:
    admin = await _get_admin_or_reject(message)
    if not admin:
        return
    await state.set_state(AddTaskState.waiting_title)
    await message.answer("Yangi topshiriq nomini yuboring:")


@router.message(AddTaskState.waiting_title)
async def add_task_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=(message.text or "").strip())
    await state.set_state(AddTaskState.waiting_description)
    await message.answer("Topshiriq tavsifini yuboring:")


@router.message(AddTaskState.waiting_description)
async def add_task_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=(message.text or "").strip())
    await state.set_state(AddTaskState.waiting_rules)
    await message.answer("Topshiriq qoidalarini yuboring:")


@router.message(AddTaskState.waiting_rules)
async def add_task_rules(message: Message, state: FSMContext) -> None:
    await state.update_data(rules_text=(message.text or "").strip())
    await state.set_state(AddTaskState.waiting_group_link)
    await message.answer("Group link yuboring yoki '-' deb yozing:")


@router.message(AddTaskState.waiting_group_link)
async def add_task_group_link(message: Message, state: FSMContext) -> None:
    group_link = (message.text or "").strip()
    if group_link == "-":
        group_link = None
    await state.update_data(group_link=group_link)
    await state.set_state(AddTaskState.waiting_image)
    await message.answer("Topshiriq rasmi yuboring yoki '-' deb yozing:")


@router.message(AddTaskState.waiting_image)
async def add_task_image(message: Message, state: FSMContext) -> None:
    admin = await _get_admin_or_reject(message)
    if not admin:
        await state.clear()
        return

    data = await state.get_data()
    image_file_id = None
    if message.photo:
        image_file_id = message.photo[-1].file_id
    elif (message.text or "").strip() != "-":
        await message.answer("Rasm yuboring yoki '-' deb yozing.")
        return

    async with SessionLocal() as db:
        task = Task(
            title=data.get("title", "Yangi topshiriq"),
            description=data.get("description", ""),
            rules_text=data.get("rules_text", ""),
            group_link=data.get("group_link"),
            image_file_id=image_file_id,
            status=TaskStatus.ACTIVE.value,
        )
        db.add(task)
        await db.flush()
        db.add_all(
            [
                RewardLevel(
                    task_id=task.id,
                    level_number=1,
                    required_count=50,
                    reward_name="Tefal",
                    reward_description="50 ta referal uchun",
                    certificate_text="50 bosqich sertifikati",
                    validity_days=30,
                ),
                RewardLevel(
                    task_id=task.id,
                    level_number=2,
                    required_count=100,
                    reward_name="Termos",
                    reward_description="100 ta referal uchun",
                    certificate_text="100 bosqich sertifikati",
                    validity_days=30,
                ),
                RewardLevel(
                    task_id=task.id,
                    level_number=3,
                    required_count=200,
                    reward_name="Serviz nabor",
                    reward_description="200 ta referal uchun",
                    certificate_text="200 bosqich sertifikati",
                    validity_days=30,
                ),
            ]
        )
        db.add(AuditLog(actor_type="admin", actor_id=admin.id, action="task_created", entity_type="task", entity_id=task.id, payload_json={}))
        await db.commit()

    await state.clear()
    await message.answer(f"Topshiriq yaratildi: #{task.id} {task.title}\nDefault sovg'a bosqichlari (50/100/200) qo'shildi.")


@router.message(IsAdminFilter(), F.text == "🎁 Sovg'alar")
async def rewards_handler(message: Message) -> None:
    admin = await _get_admin_or_reject(message)
    if not admin:
        return

    async with SessionLocal() as db:
        tasks = list((await db.scalars(select(Task).order_by(Task.id.asc()))).all())
        if not tasks:
            await message.answer("Avval topshiriq yarating.")
            return

        for task in tasks[:30]:
            add_markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Bosqich qo'shish", callback_data=f"admin:reward_add_start:{task.id}")]
                ]
            )
            await message.answer(f"Task #{task.id}: {task.title}", reply_markup=add_markup)

            levels = list(
                (
                    await db.scalars(
                        select(RewardLevel)
                        .where(RewardLevel.task_id == task.id)
                        .order_by(RewardLevel.required_count.asc())
                    )
                ).all()
            )
            if not levels:
                await message.answer("  - Bosqichlar yo'q")
                continue

            for level in levels:
                actions = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="✏️ Tahrirlash", callback_data=f"admin:reward_edit_start:{level.id}"
                            ),
                            InlineKeyboardButton(
                                text="🔁 Faollik", callback_data=f"admin:reward_toggle:{level.id}"
                            ),
                        ],
                        [InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"admin:reward_delete:{level.id}")],
                    ]
                )
                await message.answer(
                    f"Level #{level.level_number} | {level.required_count} ta\n"
                    f"Sovg'a: {level.reward_name}\n"
                    f"Tavsif: {level.reward_description}\n"
                    f"Holat: {'active' if level.is_active else 'inactive'}",
                    reply_markup=actions,
                )


@router.callback_query(F.data.startswith("admin:reward_add_start:"))
async def reward_add_start_handler(callback: CallbackQuery, state: FSMContext) -> None:
    admin = await _get_admin_from_callback(callback)
    if not admin or not callback.data:
        return

    task_id = int(callback.data.split(":")[-1])
    await state.set_state(RewardManageState.waiting_required_count)
    await state.update_data(action="add", task_id=task_id)
    await callback.message.answer("Kerakli odam sonini kiriting (masalan: 300):")
    await callback.answer()


@router.callback_query(F.data.startswith("admin:reward_edit_start:"))
async def reward_edit_start_handler(callback: CallbackQuery, state: FSMContext) -> None:
    admin = await _get_admin_from_callback(callback)
    if not admin or not callback.data:
        return

    level_id = int(callback.data.split(":")[-1])
    await state.set_state(RewardManageState.waiting_required_count)
    await state.update_data(action="edit", level_id=level_id)
    await callback.message.answer("Yangi kerakli odam sonini kiriting (masalan: 100):")
    await callback.answer()


@router.message(RewardManageState.waiting_required_count)
async def reward_required_count_handler(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("Faqat son kiriting. Masalan: 100")
        return
    await state.update_data(required_count=int(text))
    await state.set_state(RewardManageState.waiting_reward_name)
    await message.answer("Sovg'a nomini kiriting:")


@router.message(RewardManageState.waiting_reward_name)
async def reward_name_handler(message: Message, state: FSMContext) -> None:
    reward_name = (message.text or "").strip()
    if not reward_name:
        await message.answer("Sovg'a nomi bo'sh bo'lmasin.")
        return
    await state.update_data(reward_name=reward_name)
    await state.set_state(RewardManageState.waiting_reward_description)
    await message.answer("Sovg'a tavsifini kiriting:")


@router.message(RewardManageState.waiting_reward_description)
async def reward_description_handler(message: Message, state: FSMContext) -> None:
    reward_description = (message.text or "").strip()
    if not reward_description:
        await message.answer("Tavsif bo'sh bo'lmasin.")
        return
    await state.update_data(reward_description=reward_description)
    await state.set_state(RewardManageState.waiting_reward_image)
    await message.answer("Sovg'a rasmini yuboring yoki '-' deb yozing:")


@router.message(RewardManageState.waiting_reward_image)
async def reward_image_handler(message: Message, state: FSMContext) -> None:
    admin = await _get_admin_or_reject(message)
    if not admin:
        await state.clear()
        return

    image_file_id = None
    if message.photo:
        image_file_id = message.photo[-1].file_id
    elif (message.text or "").strip() != "-":
        await message.answer("Rasm yuboring yoki '-' deb yozing.")
        return

    data = await state.get_data()
    required_count = int(data.get("required_count", 0))
    reward_name = str(data.get("reward_name", "")).strip()
    reward_description = str(data.get("reward_description", "")).strip()
    if required_count <= 0 or not reward_name or not reward_description:
        await message.answer("Ma'lumotlar to'liq emas. Qaytadan boshlang.")
        await state.clear()
        return

    action = data.get("action")

    async with SessionLocal() as db:
        if action == "add":
            task_id = int(data.get("task_id"))
            last_level_no = (
                await db.scalar(
                    select(RewardLevel.level_number)
                    .where(RewardLevel.task_id == task_id)
                    .order_by(RewardLevel.level_number.desc())
                )
            ) or 0
            level = RewardLevel(
                task_id=task_id,
                level_number=int(last_level_no) + 1,
                required_count=required_count,
                reward_name=reward_name,
                reward_description=reward_description,
                reward_image_file_id=image_file_id,
                certificate_text=f"{required_count} bosqich sertifikati",
                validity_days=30,
                is_active=True,
            )
            db.add(level)
            await db.flush()
            db.add(
                AuditLog(
                    actor_type="admin",
                    actor_id=admin.id,
                    action="reward_level_created",
                    entity_type="reward_level",
                    entity_id=level.id,
                    payload_json={},
                )
            )
            await db.commit()
            await message.answer(f"Yangi bosqich qo'shildi: #{level.id} ({required_count} ta -> {reward_name})")
        else:
            level_id = int(data.get("level_id"))
            level = await db.get(RewardLevel, level_id)
            if not level:
                await message.answer("Bosqich topilmadi.")
                await state.clear()
                return
            level.required_count = required_count
            level.reward_name = reward_name
            level.reward_description = reward_description
            if image_file_id:
                level.reward_image_file_id = image_file_id
            db.add(
                AuditLog(
                    actor_type="admin",
                    actor_id=admin.id,
                    action="reward_level_updated",
                    entity_type="reward_level",
                    entity_id=level.id,
                    payload_json={},
                )
            )
            await db.commit()
            await message.answer(f"Bosqich yangilandi: #{level.id}")

    await state.clear()


@router.callback_query(F.data.startswith("admin:reward_toggle:"))
async def reward_toggle_handler(callback: CallbackQuery) -> None:
    admin = await _get_admin_from_callback(callback)
    if not admin or not callback.data:
        return

    level_id = int(callback.data.split(":")[-1])
    status_text = "inactive"
    async with SessionLocal() as db:
        level = await db.get(RewardLevel, level_id)
        if not level:
            await callback.answer("Bosqich topilmadi", show_alert=True)
            return
        level.is_active = not level.is_active
        status_text = "active" if level.is_active else "inactive"
        db.add(
            AuditLog(
                actor_type="admin",
                actor_id=admin.id,
                action="reward_level_toggled",
                entity_type="reward_level",
                entity_id=level.id,
                payload_json={"is_active": level.is_active},
            )
        )
        await db.commit()

    await callback.message.answer(f"Bosqich #{level_id} holati -> {status_text}")
    await callback.answer()


@router.callback_query(F.data.startswith("admin:reward_delete:"))
async def reward_delete_handler(callback: CallbackQuery) -> None:
    admin = await _get_admin_from_callback(callback)
    if not admin or not callback.data:
        return

    level_id = int(callback.data.split(":")[-1])
    async with SessionLocal() as db:
        level = await db.get(RewardLevel, level_id)
        if not level:
            await callback.answer("Bosqich topilmadi", show_alert=True)
            return

        used_in_cert = await db.scalar(select(Certificate.id).where(Certificate.reward_level_id == level_id))
        if used_in_cert:
            await callback.message.answer(
                "Bu bosqich sertifikatlarga bog'langan. O'chirish o'rniga inactive qilindi."
            )
            level.is_active = False
            await db.commit()
            await callback.answer()
            return

        await db.delete(level)
        db.add(
            AuditLog(
                actor_type="admin",
                actor_id=admin.id,
                action="reward_level_deleted",
                entity_type="reward_level",
                entity_id=level_id,
                payload_json={},
            )
        )
        await db.commit()

    await callback.message.answer(f"Bosqich o'chirildi: #{level_id}")
    await callback.answer()


@router.message(IsAdminFilter(), F.text == "👥 Foydalanuvchilar")
async def users_handler(message: Message) -> None:
    admin = await _get_admin_or_reject(message)
    if not admin:
        return

    async with SessionLocal() as db:
        users = list((await db.scalars(select(User).order_by(User.id.desc()))).all())

    if not users:
        await message.answer("Foydalanuvchilar yo'q.")
        return

    await message.answer("Buyruqlar: /block_user <telegram_id> va /unblock_user <telegram_id>")
    for user in users[:20]:
        await message.answer(
            f"{user.full_name} (@{user.username or '-'})\n"
            f"Telegram ID: {user.telegram_id}\n"
            f"Referrals: {user.total_referrals}\n"
            f"Holat: {'blocked' if user.is_blocked else 'active'}"
        )


@router.message(IsAdminFilter(), F.text == "📢 Xabarnoma")
async def broadcast_start(message: Message, state: FSMContext) -> None:
    admin = await _get_admin_or_reject(message)
    if not admin:
        return
    await state.set_state(BroadcastState.waiting_text)
    await message.answer("Yuboriladigan xabar matnini kiriting:")


@router.message(BroadcastState.waiting_text)
async def broadcast_send(message: Message, state: FSMContext) -> None:
    admin = await _get_admin_or_reject(message)
    if not admin:
        await state.clear()
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Xabar bo'sh bo'lmasin.")
        return

    async with SessionLocal() as db:
        users = list((await db.scalars(select(User).where(User.is_blocked.is_(False)))).all())

    sent = 0
    failed = 0
    for user in users:
        try:
            await message.bot.send_message(user.telegram_id, text)
            sent += 1
        except Exception:
            failed += 1

    await state.clear()
    await message.answer(f"Xabarnoma yakunlandi. Yuborildi: {sent}, xato: {failed}")


@router.message(IsAdminFilter(), F.text == "⚙️ Sozlamalar")
async def settings_handler(message: Message) -> None:
    admin = await _get_admin_or_reject(message)
    if not admin:
        return

    await message.answer(
        "Sozlamalar:\n"
        f"TRACKING_TASK_ID: {settings.tracking_task_id}\n"
        f"TARGET_GROUP_ID: {settings.target_group_id}\n"
        f"BASE_BOT_USERNAME: {settings.base_bot_username}"
    )


@router.message(IsAdminFilter(), F.text == "🧾 Loglar")
async def logs_handler(message: Message) -> None:
    admin = await _get_admin_or_reject(message)
    if not admin:
        return

    async with SessionLocal() as db:
        logs = list((await db.scalars(select(AuditLog).order_by(AuditLog.id.desc()))).all())

    if not logs:
        await message.answer("Loglar topilmadi.")
        return

    for log in logs[:20]:
        await message.answer(
            f"{log.created_at} | {log.action}\n"
            f"actor: {log.actor_type}:{log.actor_id} | entity: {log.entity_type}:{log.entity_id}"
        )


@router.message(IsAdminFilter(), F.text == "⏳ So'rovlar")
async def pending_requests_handler(message: Message) -> None:
    admin = await _get_admin_or_reject(message)
    if not admin:
        return

    async with SessionLocal() as db:
        pending = await list_pending_requests_view(db, limit=20)
        if not pending:
            await message.answer("Pending so'rovlar mavjud emas.")
            return

        for req in pending:
            await message.answer(
                f"So'rov #{req.request_id}\n"
                f"User: {req.user_full_name or 'Nomalum'}\n"
                f"Telegram ID: {req.user_telegram_id or '-'}\n"
                f"Sovg'a: {req.reward_name or 'Nomalum'}\n"
                f"Bosqich: {req.reward_required_count or 0}\n"
                f"Sertifikat ID: {req.certificate_id}\n"
                f"Yuborilgan vaqt: {req.created_at}",
                reply_markup=pending_request_inline(req.certificate_id),
            )


@router.callback_query(F.data.startswith("admin:approve:"))
async def approve_handler(callback: CallbackQuery) -> None:
    admin = await _get_admin_from_callback(callback)
    if not admin or not callback.data:
        return

    cert_id = int(callback.data.split(":")[-1])

    async with SessionLocal() as db:
        promo = await approve_certificate(db, certificate_id=cert_id, admin_id=admin.id, shop_id=None)
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
    admin = await _get_admin_from_callback(callback)
    if not admin or not callback.data:
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


@router.message(IsAdminFilter(), F.text == "📊 Statistika")
async def stats_handler(message: Message) -> None:
    admin = await _get_admin_or_reject(message)
    if not admin:
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
