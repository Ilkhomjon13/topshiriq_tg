from src.core.enums import CertificateStatus
from src.db.models import Certificate, RewardLevel, Task, User
from src.services.certificate_service import create_or_upgrade_certificate, request_redemption


async def test_certificate_upgrade_cancels_previous(db_session):
    user = User(telegram_id=11, full_name="User", username="user")
    task = Task(title="Task", description="D", rules_text="R")
    db_session.add_all([user, task])
    await db_session.flush()

    level_50 = RewardLevel(
        task_id=task.id,
        level_number=1,
        required_count=50,
        reward_name="Tefal",
        reward_description="50",
    )
    level_100 = RewardLevel(
        task_id=task.id,
        level_number=2,
        required_count=100,
        reward_name="Termos",
        reward_description="100",
    )
    db_session.add_all([level_50, level_100])
    await db_session.flush()

    cert_50 = await create_or_upgrade_certificate(db_session, user_id=user.id, task_id=task.id, level=level_50)
    cert_100 = await create_or_upgrade_certificate(db_session, user_id=user.id, task_id=task.id, level=level_100)
    await db_session.commit()

    old = await db_session.get(Certificate, cert_50.id)
    new = await db_session.get(Certificate, cert_100.id)

    assert old.status == CertificateStatus.CANCELLED.value
    assert new.status == CertificateStatus.AVAILABLE.value


async def test_request_redemption_creates_pending(db_session):
    user = User(telegram_id=22, full_name="User", username="user2")
    task = Task(title="Task", description="D", rules_text="R")
    db_session.add_all([user, task])
    await db_session.flush()

    level = RewardLevel(
        task_id=task.id,
        level_number=1,
        required_count=50,
        reward_name="Tefal",
        reward_description="50",
    )
    db_session.add(level)
    await db_session.flush()

    cert = await create_or_upgrade_certificate(db_session, user_id=user.id, task_id=task.id, level=level)
    ok_first = await request_redemption(db_session, certificate_id=cert.id, user_id=user.id)
    ok_second = await request_redemption(db_session, certificate_id=cert.id, user_id=user.id)

    assert ok_first is True
    assert ok_second is False
