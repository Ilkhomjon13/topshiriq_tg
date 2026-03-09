from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.enums import ParticipantStatus, TaskStatus
from src.db.models import RewardLevel, Task, TaskParticipant
from src.services.audit_service import write_log


async def list_active_tasks(db: AsyncSession) -> list[Task]:
    result = await db.scalars(select(Task).where(Task.status == TaskStatus.ACTIVE.value).order_by(Task.id.asc()))
    return list(result)


async def get_task_by_id(db: AsyncSession, task_id: int) -> Task | None:
    return await db.get(Task, task_id)


async def get_task_levels(db: AsyncSession, task_id: int) -> list[RewardLevel]:
    result = await db.scalars(
        select(RewardLevel)
        .where(and_(RewardLevel.task_id == task_id, RewardLevel.is_active.is_(True)))
        .order_by(RewardLevel.required_count.asc())
    )
    return list(result)


async def list_user_tasks(db: AsyncSession, user_id: int) -> list[Task]:
    result = await db.scalars(
        select(Task)
        .join(TaskParticipant, TaskParticipant.task_id == Task.id)
        .where(and_(TaskParticipant.user_id == user_id, TaskParticipant.status == ParticipantStatus.ACTIVE.value))
        .order_by(Task.id.asc())
    )
    return list(result)


async def join_task(db: AsyncSession, task_id: int, user_id: int) -> TaskParticipant:
    participant = await db.scalar(
        select(TaskParticipant).where(and_(TaskParticipant.task_id == task_id, TaskParticipant.user_id == user_id))
    )
    if participant:
        participant.status = ParticipantStatus.ACTIVE.value
        return participant

    participant = TaskParticipant(task_id=task_id, user_id=user_id)
    db.add(participant)
    await db.flush()
    await write_log(db, "user", user_id, "task_joined", "task_participant", participant.id, {"task_id": task_id})
    return participant


async def is_user_participant(db: AsyncSession, task_id: int, user_id: int) -> bool:
    participant = await db.scalar(
        select(TaskParticipant).where(
            and_(
                TaskParticipant.task_id == task_id,
                TaskParticipant.user_id == user_id,
                TaskParticipant.status == ParticipantStatus.ACTIVE.value,
            )
        )
    )
    return participant is not None


async def get_latest_active_participant_task_id(db: AsyncSession, user_id: int) -> int | None:
    task_id = await db.scalar(
        select(TaskParticipant.task_id)
        .join(Task, Task.id == TaskParticipant.task_id)
        .where(
            and_(
                TaskParticipant.user_id == user_id,
                TaskParticipant.status == ParticipantStatus.ACTIVE.value,
                Task.status == TaskStatus.ACTIVE.value,
            )
        )
        .order_by(TaskParticipant.joined_at.desc(), TaskParticipant.id.desc())
        .limit(1)
    )
    return int(task_id) if task_id is not None else None
