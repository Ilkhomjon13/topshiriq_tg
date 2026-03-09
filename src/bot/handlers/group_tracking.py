from datetime import datetime

from aiogram import F, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.types import ChatMemberUpdated, Message, User as TgUser

from src.core.config import get_settings
from src.core.enums import ReferralStatus
from src.db.models import User as DbUser
from src.db.session import SessionLocal
from src.services.certificate_service import create_or_upgrade_certificate, get_best_level_for_count
from src.services.referral_service import count_valid_referrals, get_or_create_user, register_referral_fast
from src.services.task_service import is_user_participant, list_active_participant_task_ids

router = Router(name="group_tracking")
settings = get_settings()


def _is_target_group(chat_id: int) -> bool:
    if not settings.target_group_id:
        return True
    configured_id = int(settings.target_group_id)
    allowed_ids = {configured_id, abs(configured_id), -abs(configured_id)}
    return chat_id in allowed_ids


async def _count_manual_add(adder_tg_user: TgUser, invited_members: list[TgUser]) -> None:
    async with SessionLocal() as db:
        adder = await get_or_create_user(
            db,
            telegram_id=adder_tg_user.id,
            full_name=adder_tg_user.full_name,
            username=adder_tg_user.username,
        )

        default_task_id = settings.tracking_task_id
        if default_task_id and await is_user_participant(db, task_id=default_task_id, user_id=adder.id):
            adder_task_ids = [default_task_id]
        else:
            adder_task_ids = await list_active_participant_task_ids(db, user_id=adder.id)

        if not adder_task_ids:
            await db.commit()
            return

        created_counts: dict[tuple[int, int], int] = {}

        for member in invited_members:
            if member.is_bot:
                continue

            invited = await get_or_create_user(
                db,
                telegram_id=member.id,
                full_name=member.full_name,
                username=member.username,
            )

            for task_id in adder_task_ids:
                referral = await register_referral_fast(
                    db=db,
                    task_id=task_id,
                    inviter=adder,
                    invited=invited,
                    source_code="group_add",
                )
                if not referral:
                    continue

                referral.status = ReferralStatus.COUNTED.value
                referral.counted_at = datetime.utcnow()
                key = (adder.id, task_id)
                created_counts[key] = created_counts.get(key, 0) + 1

        for (inviter_id, task_id), count in created_counts.items():
            inviter = await db.get(DbUser, inviter_id)
            if not inviter:
                continue

            inviter.total_referrals += count
            counted = await count_valid_referrals(db, task_id=task_id, inviter_user_id=inviter_id)
            level = await get_best_level_for_count(db, task_id=task_id, referrals_count=counted)
            if level:
                await create_or_upgrade_certificate(db, user_id=inviter_id, task_id=task_id, level=level)

        await db.commit()


@router.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}), F.new_chat_members)
async def track_group_invites(message: Message) -> None:
    if not _is_target_group(message.chat.id):
        return
    if not message.from_user or not message.new_chat_members:
        return

    await _count_manual_add(message.from_user, list(message.new_chat_members))


@router.chat_member()
async def track_group_invites_via_chat_member(event: ChatMemberUpdated) -> None:
    if event.chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
        return
    if not _is_target_group(event.chat.id):
        return
    if not event.from_user:
        return

    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status
    became_member = new_status in {
        ChatMemberStatus.MEMBER,
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.RESTRICTED,
    } and old_status in {
        ChatMemberStatus.LEFT,
        ChatMemberStatus.KICKED,
    }

    if not became_member:
        return

    invited_user = event.new_chat_member.user
    if invited_user.id == event.from_user.id:
        return

    await _count_manual_add(event.from_user, [invited_user])
