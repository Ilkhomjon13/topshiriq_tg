from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AuditLog


async def write_log(
    db: AsyncSession,
    actor_type: str,
    actor_id: int,
    action: str,
    entity_type: str,
    entity_id: int,
    payload: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            payload_json=payload or {},
            created_at=datetime.utcnow(),
        )
    )
