from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.types import Message

from src.core.config import get_settings
from src.db.session import SessionLocal
from src.services.certificate_service import create_or_upgrade_certificate, get_best_level_for_count
from src.services.referral_service import count_valid_referrals, get_or_create_user, mark_referral_counted, register_referral
from src.services.task_service import is_user_participant

router = Router(name="group_tracking")
settings = get_settings()


@router.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}), F.new_chat_members)
async def track_group_invites(message: Message) -> None:
    if settings.target_group_id and message.chat.id != settings.target_group_id:
        return

    if not message.from_user or not message.new_chat_members:
        return

    # who added users to the group
    adder_tg_id = message.from_user.id

    async with SessionLocal() as db:
        inviter = await get_or_create_user(
            db,
            telegram_id=adder_tg_id,
            full_name=message.from_user.full_name,
            username=message.from_user.username,
        )

        # count only for users who joined the task
        if not await is_user_participant(db, task_id=settings.tracking_task_id, user_id=inviter.id):
            await db.commit()
            return

        for member in message.new_chat_members:
            invited = await get_or_create_user(
                db,
                telegram_id=member.id,
                full_name=member.full_name,
                username=member.username,
            )
            referral = await register_referral(
                db,
                task_id=settings.tracking_task_id,
                inviter_user_id=inviter.id,
                invited_user_id=invited.id,
                source_code="group_add",
            )
            if not referral:
                continue

            # Immediate counting mode: referral is counted as soon as user is added to group.
            await mark_referral_counted(db, referral_id=referral.id)
            counted = await count_valid_referrals(db, task_id=settings.tracking_task_id, inviter_user_id=inviter.id)
            level = await get_best_level_for_count(db, task_id=settings.tracking_task_id, referrals_count=counted)
            if level:
                await create_or_upgrade_certificate(
                    db,
                    user_id=inviter.id,
                    task_id=settings.tracking_task_id,
                    level=level,
                )

        await db.commit()
