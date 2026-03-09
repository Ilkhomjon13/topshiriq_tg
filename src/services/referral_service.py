from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.enums import ReferralStatus
from src.db.models import Referral, User
from src.services.audit_service import write_log


async def get_user_by_telegram_id(db: AsyncSession, telegram_id: int) -> User | None:
    return await db.scalar(select(User).where(User.telegram_id == telegram_id))


async def get_or_create_user(db: AsyncSession, telegram_id: int, full_name: str, username: str | None) -> User:
    user = await get_user_by_telegram_id(db, telegram_id=telegram_id)
    if user:
        user.full_name = full_name
        user.username = username
        return user

    user = User(telegram_id=telegram_id, full_name=full_name, username=username)
    db.add(user)
    await db.flush()
    await write_log(db, "user", user.id, "user_started", "user", user.id, {})
    return user


async def register_referral(
    db: AsyncSession,
    task_id: int,
    inviter_user_id: int,
    invited_user_id: int,
    source_code: str,
) -> Referral | None:
    if inviter_user_id == invited_user_id:
        return None

    inviter = await db.get(User, inviter_user_id)
    invited = await db.get(User, invited_user_id)
    if not inviter or not invited:
        return None

    # minimal anti-fraud: blocked accounts are ignored.
    if inviter.is_blocked or invited.is_blocked:
        return None

    existing = await db.scalar(
        select(Referral).where(and_(Referral.task_id == task_id, Referral.invited_user_id == invited_user_id))
    )
    if existing:
        return None

    referral = Referral(
        task_id=task_id,
        inviter_user_id=inviter_user_id,
        invited_user_id=invited_user_id,
        source_code=source_code,
        status=ReferralStatus.PENDING.value,
    )
    db.add(referral)
    await db.flush()
    await write_log(db, "system", 0, "referral_created", "referral", referral.id, {"task_id": task_id})
    return referral


async def register_referral_fast(
    db: AsyncSession,
    task_id: int,
    inviter: User,
    invited: User,
    source_code: str,
) -> Referral | None:
    if inviter.id == invited.id:
        return None
    if inviter.is_blocked or invited.is_blocked:
        return None

    existing = await db.scalar(
        select(Referral).where(and_(Referral.task_id == task_id, Referral.invited_user_id == invited.id))
    )
    if existing:
        return None

    referral = Referral(
        task_id=task_id,
        inviter_user_id=inviter.id,
        invited_user_id=invited.id,
        source_code=source_code,
        status=ReferralStatus.PENDING.value,
    )
    db.add(referral)
    await db.flush()
    await write_log(db, "system", 0, "referral_created", "referral", referral.id, {"task_id": task_id})
    return referral


async def count_valid_referrals(db: AsyncSession, task_id: int, inviter_user_id: int) -> int:
    stmt: Select = select(func.count(Referral.id)).where(
        and_(
            Referral.task_id == task_id,
            Referral.inviter_user_id == inviter_user_id,
            Referral.status == ReferralStatus.COUNTED.value,
        )
    )
    return int((await db.scalar(stmt)) or 0)


async def get_task_referral_count(db: AsyncSession, task_id: int, inviter_user_id: int) -> int:
    stmt: Select = select(func.count(Referral.id)).where(
        and_(
            Referral.task_id == task_id,
            Referral.inviter_user_id == inviter_user_id,
            Referral.status.in_([ReferralStatus.PENDING.value, ReferralStatus.COUNTED.value]),
        )
    )
    return int((await db.scalar(stmt)) or 0)


async def get_task_referral_counts_for_user(db: AsyncSession, inviter_user_id: int, task_ids: list[int]) -> dict[int, int]:
    if not task_ids:
        return {}
    rows = (
        await db.execute(
            select(Referral.task_id, func.count(Referral.id))
            .where(
                and_(
                    Referral.inviter_user_id == inviter_user_id,
                    Referral.task_id.in_(task_ids),
                    Referral.status.in_([ReferralStatus.PENDING.value, ReferralStatus.COUNTED.value]),
                )
            )
            .group_by(Referral.task_id)
        )
    ).all()
    return {int(task_id): int(count) for task_id, count in rows}

