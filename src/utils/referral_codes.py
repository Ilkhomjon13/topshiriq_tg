from dataclasses import dataclass


@dataclass(frozen=True)
class ReferralSource:
    task_id: int
    inviter_user_id: int


PREFIX = "ref"


def build_ref_source_code(task_id: int, inviter_user_id: int) -> str:
    return f"{PREFIX}_{task_id}_{inviter_user_id}"


def parse_ref_source_code(value: str) -> ReferralSource | None:
    if not value:
        return None

    parts = value.split("_")
    if len(parts) != 3 or parts[0] != PREFIX:
        return None

    try:
        task_id = int(parts[1])
        inviter_user_id = int(parts[2])
    except ValueError:
        return None

    if task_id <= 0 or inviter_user_id <= 0:
        return None

    return ReferralSource(task_id=task_id, inviter_user_id=inviter_user_id)
