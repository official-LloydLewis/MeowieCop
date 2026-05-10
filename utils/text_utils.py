"""Text normalization helpers."""


def normalize_username(username: str) -> str:
    return username.strip().lstrip("@")
