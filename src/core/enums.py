from enum import StrEnum


class AdminRole(StrEnum):
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    OPERATOR = "operator"


class TaskStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class ParticipantStatus(StrEnum):
    ACTIVE = "active"
    LEFT = "left"
    BANNED = "banned"


class ReferralStatus(StrEnum):
    PENDING = "pending"
    COUNTED = "counted"
    REJECTED = "rejected"
    FRAUD = "fraud"


class CertificateStatus(StrEnum):
    AVAILABLE = "available"
    PENDING = "pending"
    APPROVED = "approved"
    USED = "used"
    EXPIRED = "expired"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class PromoCodeStatus(StrEnum):
    ACTIVE = "active"
    USED = "used"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
