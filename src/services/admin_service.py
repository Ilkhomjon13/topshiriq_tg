from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.enums import CertificateStatus, PromoCodeStatus
from src.db.models import Certificate, PromoCode, RedemptionRequest, RewardLevel, User
from src.services.audit_service import write_log
from src.utils.codes import build_promo_code


@dataclass
class PendingRequestView:
    request_id: int
    certificate_id: int
    created_at: datetime
    user_full_name: str | None
    user_telegram_id: int | None
    reward_name: str | None
    reward_required_count: int | None


async def _generate_unique_promo(db: AsyncSession, level_required_count: int) -> str:
    while True:
        candidate = build_promo_code(level_required_count)
        exists = await db.scalar(select(PromoCode).where(PromoCode.code == candidate))
        if not exists:
            return candidate


async def list_pending_requests_view(db: AsyncSession, limit: int = 20) -> list[PendingRequestView]:
    rows = (
        await db.execute(
            select(
                RedemptionRequest.id,
                RedemptionRequest.certificate_id,
                RedemptionRequest.created_at,
                User.full_name,
                User.telegram_id,
                RewardLevel.reward_name,
                RewardLevel.required_count,
            )
            .join(Certificate, Certificate.id == RedemptionRequest.certificate_id)
            .join(User, User.id == Certificate.user_id)
            .join(RewardLevel, RewardLevel.id == Certificate.reward_level_id)
            .where(RedemptionRequest.status == CertificateStatus.PENDING.value)
            .order_by(RedemptionRequest.id.asc())
            .limit(limit)
        )
    ).all()

    return [
        PendingRequestView(
            request_id=row[0],
            certificate_id=row[1],
            created_at=row[2],
            user_full_name=row[3],
            user_telegram_id=row[4],
            reward_name=row[5],
            reward_required_count=row[6],
        )
        for row in rows
    ]


async def approve_certificate(db: AsyncSession, certificate_id: int, admin_id: int, shop_id: int | None) -> PromoCode | None:
    cert = await db.get(Certificate, certificate_id)
    if not cert or cert.status != CertificateStatus.PENDING.value:
        return None

    cert.status = CertificateStatus.APPROVED.value
    cert.approved_at = datetime.utcnow()

    level_required = 0
    level = await db.get(RewardLevel, cert.reward_level_id)
    if level:
        level_required = level.required_count

    promo = PromoCode(
        certificate_id=cert.id,
        code=await _generate_unique_promo(db, level_required_count=level_required),
        shop_id=shop_id,
        status=PromoCodeStatus.ACTIVE.value,
    )
    db.add(promo)

    request = await db.scalar(
        select(RedemptionRequest).where(
            and_(
                RedemptionRequest.certificate_id == certificate_id,
                RedemptionRequest.status == CertificateStatus.PENDING.value,
            )
        )
    )
    if request:
        request.status = CertificateStatus.APPROVED.value
        request.admin_id = admin_id
        request.reviewed_at = datetime.utcnow()

    await db.flush()
    await write_log(db, "admin", admin_id, "certificate_approved", "certificate", cert.id, {"promo_code": promo.code})
    return promo


async def reject_certificate(db: AsyncSession, certificate_id: int, admin_id: int, reason: str) -> bool:
    cert = await db.get(Certificate, certificate_id)
    if not cert or cert.status != CertificateStatus.PENDING.value:
        return False

    cert.status = CertificateStatus.REJECTED.value
    request = await db.scalar(
        select(RedemptionRequest).where(
            and_(
                RedemptionRequest.certificate_id == certificate_id,
                RedemptionRequest.status == CertificateStatus.PENDING.value,
            )
        )
    )
    if request:
        request.status = CertificateStatus.REJECTED.value
        request.admin_id = admin_id
        request.reject_reason = reason
        request.reviewed_at = datetime.utcnow()

    await write_log(db, "admin", admin_id, "certificate_rejected", "certificate", cert.id, {"reason": reason})
    return True


async def mark_certificate_used(db: AsyncSession, certificate_id: int, actor_admin_id: int) -> bool:
    cert = await db.get(Certificate, certificate_id)
    if not cert or cert.status != CertificateStatus.APPROVED.value:
        return False

    promo = await db.scalar(select(PromoCode).where(PromoCode.certificate_id == certificate_id))
    if promo:
        promo.status = PromoCodeStatus.USED.value
        promo.used_at = datetime.utcnow()

    cert.status = CertificateStatus.USED.value
    cert.used_at = datetime.utcnow()
    await write_log(db, "admin", actor_admin_id, "certificate_used", "certificate", cert.id, {})
    return True
