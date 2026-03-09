from datetime import datetime

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.types import Message

from src.core.config import get_settings
from src.core.enums import ReferralStatus
from src.db.session import SessionLocal
from src.services.certificate_service import create_or_upgrade_certificate, get_best_level_for_count
from src.services.referral_service import count_valid_referrals, get_or_create_user, register_referral
from src.services.task_service import get_latest_active_participant_task_id, is_user_participant

router = Router(name="group_tracking")
settings = get_settings()


@router.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}), F.new_chat_members)
async def track_group_invites(message: Message) -> None:
    if settings.target_group_id:
        configured_id = int(settings.target_group_id)
        allowed_ids = {configured_id, abs(configured_id), -abs(configured_id)}
        if message.chat.id not in allowed_ids:
            return

    if not message.from_user or not message.new_chat_members:
        return

    async with SessionLocal() as db:
        adder = await get_or_create_user(
            db,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username,
        )

        default_task_id = settings.tracking_task_id
        if default_task_id and await is_user_participant(db, task_id=default_task_id, user_id=adder.id):
            adder_task_id = default_task_id
        else:
            adder_task_id = await get_latest_active_participant_task_id(db, user_id=adder.id)

        created_counts: dict[tuple[int, int], int] = {}

        for member in message.new_chat_members:
            if member.is_bot:
                continue

            inviter = adder
            resolved_task_id = adder_task_id

            if not resolved_task_id:
                continue

            invited = await get_or_create_user(
                db,
                telegram_id=member.id,
                full_name=member.full_name,
                username=member.username,
            )
            referral = await register_referral(
                db,
                task_id=resolved_task_id,
                inviter_user_id=inviter.id,
                invited_user_id=invited.id,
                source_code="group_add",
            )
            if not referral:
                continue

            referral.status = ReferralStatus.COUNTED.value
            referral.counted_at = datetime.utcnow()
            key = (inviter.id, resolved_task_id)
            created_counts[key] = created_counts.get(key, 0) + 1

        for (inviter_id, task_id), count in created_counts.items():
            inviter = await db.get(User, inviter_id)
            if not inviter:
                continue
            inviter.total_referrals += count
            counted = await count_valid_referrals(db, task_id=task_id, inviter_user_id=inviter_id)
            level = await get_best_level_for_count(db, task_id=task_id, referrals_count=counted)
            if level:
                await create_or_upgrade_certificate(db, user_id=inviter_id, task_id=task_id, level=level)

        await db.commit()
