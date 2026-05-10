"""Admin permission checks."""


def can_moderate(actor_id: str, target_id: str, is_admin: bool) -> bool:
    return is_admin and actor_id != target_id
