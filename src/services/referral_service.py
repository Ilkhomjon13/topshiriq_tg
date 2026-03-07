from datetime import datetime

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


async def mark_referral_counted(db: AsyncSession, referral_id: int, admin_id: int | None = None) -> bool:
    referral = await db.get(Referral, referral_id)
    if not referral or referral.status == ReferralStatus.COUNTED.value:
        return False

    referral.status = ReferralStatus.COUNTED.value
    referral.counted_at = datetime.utcnow()

    inviter = await db.get(User, referral.inviter_user_id)
    if inviter:
        inviter.total_referrals += 1

    await write_log(
        db,
        "admin" if admin_id else "system",
        admin_id or 0,
        "referral_counted",
        "referral",
        referral.id,
        {"inviter_user_id": referral.inviter_user_id},
    )
    return True


async def list_pending_referrals_for_invited(db: AsyncSession, invited_user_id: int) -> list[Referral]:
    result = await db.scalars(
        select(Referral).where(
            and_(Referral.invited_user_id == invited_user_id, Referral.status == ReferralStatus.PENDING.value)
        )
    )
    return list(result)
