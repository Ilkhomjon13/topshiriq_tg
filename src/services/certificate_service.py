from datetime import datetime, timedelta

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.enums import CertificateStatus
from src.db.models import Certificate, RedemptionRequest, RewardLevel
from src.services.audit_service import write_log
from src.utils.codes import build_certificate_code


async def get_best_level_for_count(db: AsyncSession, task_id: int, referrals_count: int) -> RewardLevel | None:
    return await db.scalar(
        select(RewardLevel)
        .where(
            and_(
                RewardLevel.task_id == task_id,
                RewardLevel.required_count <= referrals_count,
                RewardLevel.is_active.is_(True),
            )
        )
        .order_by(desc(RewardLevel.required_count))
    )


async def create_or_upgrade_certificate(db: AsyncSession, user_id: int, task_id: int, level: RewardLevel) -> Certificate:
    active = await db.scalar(
        select(Certificate).where(
            and_(
                Certificate.user_id == user_id,
                Certificate.task_id == task_id,
                Certificate.status.in_(
                    [
                        CertificateStatus.AVAILABLE.value,
                        CertificateStatus.PENDING.value,
                        CertificateStatus.APPROVED.value,
                    ]
                ),
            )
        )
    )

    if active and active.reward_level_id == level.id:
        return active

    if active:
        active.status = CertificateStatus.CANCELLED.value
        active.cancelled_at = datetime.utcnow()
        await write_log(db, "system", 0, "certificate_cancelled", "certificate", active.id, {"reason": "upgraded"})

    cert = Certificate(
        user_id=user_id,
        task_id=task_id,
        reward_level_id=level.id,
        certificate_code=build_certificate_code(user_id, level.required_count),
        status=CertificateStatus.AVAILABLE.value,
        issued_at=datetime.utcnow(),
        expired_at=(datetime.utcnow() + timedelta(days=level.validity_days)) if level.validity_days else None,
    )
    db.add(cert)
    await db.flush()
    await write_log(db, "system", 0, "certificate_created", "certificate", cert.id, {"reward_level_id": level.id})
    return cert


async def get_user_certificates(db: AsyncSession, user_id: int) -> list[Certificate]:
    result = await db.scalars(select(Certificate).where(Certificate.user_id == user_id).order_by(Certificate.id.desc()))
    return list(result)


async def request_redemption(db: AsyncSession, certificate_id: int, user_id: int) -> bool:
    cert = await db.get(Certificate, certificate_id)
    if not cert or cert.user_id != user_id or cert.status != CertificateStatus.AVAILABLE.value:
        return False

    existing_pending = await db.scalar(
        select(RedemptionRequest).where(
            and_(
                RedemptionRequest.certificate_id == certificate_id,
                RedemptionRequest.status == CertificateStatus.PENDING.value,
            )
        )
    )
    if existing_pending:
        return False

    cert.status = CertificateStatus.PENDING.value
    db.add(
        RedemptionRequest(
            certificate_id=certificate_id,
            user_id=user_id,
            status=CertificateStatus.PENDING.value,
        )
    )
    await write_log(db, "user", user_id, "certificate_pending", "certificate", cert.id, {})
    return True
