from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.enums import AdminRole, CertificateStatus, ParticipantStatus, PromoCodeStatus, ReferralStatus, TaskStatus
from src.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="uz")
    referred_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    total_referrals: Mapped[int] = mapped_column(Integer, default=0)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    rules_text: Mapped[str] = mapped_column(Text)
    group_link: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=TaskStatus.ACTIVE.value)
    start_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[Date | None] = mapped_column(Date, nullable=True)


class TaskParticipant(Base):
    __tablename__ = "task_participants"
    __table_args__ = (UniqueConstraint("task_id", "user_id", name="uq_task_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(20), default=ParticipantStatus.ACTIVE.value)


class RewardLevel(Base, TimestampMixin):
    __tablename__ = "reward_levels"
    __table_args__ = (UniqueConstraint("task_id", "required_count", name="uq_task_required_count"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    level_number: Mapped[int] = mapped_column(Integer)
    required_count: Mapped[int] = mapped_column(Integer)
    reward_name: Mapped[str] = mapped_column(String(255))
    reward_description: Mapped[str] = mapped_column(Text)
    reward_image_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    certificate_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    validity_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Referral(Base):
    __tablename__ = "referrals"
    __table_args__ = (UniqueConstraint("task_id", "invited_user_id", name="uq_task_invited_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    inviter_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    invited_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    source_code: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(20), default=ReferralStatus.PENDING.value)
    counted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Certificate(Base, TimestampMixin):
    __tablename__ = "certificates"
    __table_args__ = (UniqueConstraint("certificate_code", name="uq_certificate_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    reward_level_id: Mapped[int] = mapped_column(ForeignKey("reward_levels.id"), index=True)
    certificate_code: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(20), default=CertificateStatus.AVAILABLE.value)
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RedemptionRequest(Base):
    __tablename__ = "redemption_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    certificate_id: Mapped[int] = mapped_column(ForeignKey("certificates.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("admins.id"), nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Shop(Base, TimestampMixin):
    __tablename__ = "shops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    address: Mapped[str] = mapped_column(Text)
    phone: Mapped[str] = mapped_column(String(40))
    seller_name: Mapped[str] = mapped_column(String(255))
    working_hours: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class PromoCode(Base):
    __tablename__ = "promo_codes"
    __table_args__ = (UniqueConstraint("code", name="uq_promo_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    certificate_id: Mapped[int] = mapped_column(ForeignKey("certificates.id"), unique=True)
    code: Mapped[str] = mapped_column(String(40), index=True)
    shop_id: Mapped[int | None] = mapped_column(ForeignKey("shops.id"), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=PromoCodeStatus.ACTIVE.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default=AdminRole.ADMIN.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_type: Mapped[str] = mapped_column(String(50))
    actor_id: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[int] = mapped_column(Integer)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
