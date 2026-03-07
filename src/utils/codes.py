import random
import string


def random_suffix(length: int = 4) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


def build_promo_code(level_required_count: int) -> str:
    return f"TOP-{level_required_count}-{random_suffix()}"


def build_certificate_code(user_id: int, level_required_count: int) -> str:
    return f"CERT-{user_id}-{level_required_count}-{random_suffix(5)}"
