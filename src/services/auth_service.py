from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.enums import AdminRole
from src.db.models import Admin


async def ensure_superadmins(db: AsyncSession, telegram_ids: set[int]) -> None:
    if not telegram_ids:
        return

    existing = await db.scalars(select(Admin).where(Admin.telegram_id.in_(list(telegram_ids))))
    existing_ids = {admin.telegram_id for admin in existing}

    for tg_id in telegram_ids - existing_ids:
        db.add(
            Admin(
                telegram_id=tg_id,
                full_name=f"Superadmin {tg_id}",
                role=AdminRole.SUPERADMIN.value,
                is_active=True,
            )
        )


async def get_active_admin(db: AsyncSession, telegram_id: int) -> Admin | None:
    return await db.scalar(select(Admin).where(Admin.telegram_id == telegram_id, Admin.is_active.is_(True)))
