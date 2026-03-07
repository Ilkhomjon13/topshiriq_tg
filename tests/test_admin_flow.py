from src.core.enums import CertificateStatus
from src.db.models import Certificate, RewardLevel, Task, User
from src.services.admin_service import approve_certificate
from src.services.certificate_service import create_or_upgrade_certificate, request_redemption


async def test_admin_approve_creates_promo(db_session):
    user = User(telegram_id=33, full_name="User", username="user3")
    task = Task(title="Task", description="D", rules_text="R")
    db_session.add_all([user, task])
    await db_session.flush()

    level = RewardLevel(
        task_id=task.id,
        level_number=2,
        required_count=100,
        reward_name="Termos",
        reward_description="100",
    )
    db_session.add(level)
    await db_session.flush()

    cert = await create_or_upgrade_certificate(db_session, user_id=user.id, task_id=task.id, level=level)
    await request_redemption(db_session, certificate_id=cert.id, user_id=user.id)

    promo = await approve_certificate(db_session, certificate_id=cert.id, admin_id=1, shop_id=None)
    await db_session.commit()

    assert promo is not None
    refreshed = await db_session.get(Certificate, cert.id)
    assert refreshed.status == CertificateStatus.APPROVED.value
    assert promo.code.startswith("TOP-")
