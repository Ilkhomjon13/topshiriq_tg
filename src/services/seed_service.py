from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.enums import TaskStatus
from src.db.models import RewardLevel, Task


async def ensure_seed_data(db: AsyncSession) -> None:
    task_count = await db.scalar(select(func.count(Task.id)))
    if task_count and task_count > 0:
        return

    task = Task(
        title="@topibolindi guruhiga taklif",
        description="Referal havola orqali foydalanuvchilarni taklif qiling.",
        rules_text="Azo bo'lgan va botni /start qilgan foydalanuvchilar hisoblanadi.",
        group_link="https://t.me/topibolindi",
        status=TaskStatus.ACTIVE.value,
        start_date=date.today(),
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
                reward_description="50 ta haqiqiy referal uchun.",
                certificate_text="Tefal sovg'asi sertifikati",
                validity_days=30,
            ),
            RewardLevel(
                task_id=task.id,
                level_number=2,
                required_count=100,
                reward_name="Termos",
                reward_description="100 ta haqiqiy referal uchun.",
                certificate_text="Termos sovg'asi sertifikati",
                validity_days=30,
            ),
            RewardLevel(
                task_id=task.id,
                level_number=3,
                required_count=200,
                reward_name="Serviz nabor",
                reward_description="200 ta haqiqiy referal uchun.",
                certificate_text="Serviz nabor sertifikati",
                validity_days=30,
            ),
        ]
    )
