"""Input validators."""


def is_positive_int(value: str) -> bool:
    return value.isdigit() and int(value) > 0
