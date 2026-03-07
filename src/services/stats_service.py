from dataclasses import dataclass
from datetime import date, datetime, time

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.enums import CertificateStatus
from src.db.models import Certificate, RedemptionRequest, User


@dataclass
class DashboardStats:
    total_users: int
    today_new_users: int
    pending_certificates: int
    approved_certificates: int
    used_certificates: int
    rejected_certificates: int


async def collect_dashboard_stats(db: AsyncSession) -> DashboardStats:
    today_start = datetime.combine(date.today(), time.min)

    total_users = int((await db.scalar(select(func.count(User.id)))) or 0)
    today_new_users = int((await db.scalar(select(func.count(User.id)).where(User.created_at >= today_start))) or 0)
    pending = int((await db.scalar(select(func.count(RedemptionRequest.id)).where(RedemptionRequest.status == CertificateStatus.PENDING.value))) or 0)
    approved = int((await db.scalar(select(func.count(Certificate.id)).where(Certificate.status == CertificateStatus.APPROVED.value))) or 0)
    used = int((await db.scalar(select(func.count(Certificate.id)).where(Certificate.status == CertificateStatus.USED.value))) or 0)
    rejected = int((await db.scalar(select(func.count(Certificate.id)).where(Certificate.status == CertificateStatus.REJECTED.value))) or 0)

    return DashboardStats(
        total_users=total_users,
        today_new_users=today_new_users,
        pending_certificates=pending,
        approved_certificates=approved,
        used_certificates=used,
        rejected_certificates=rejected,
    )
