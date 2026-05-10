"""Time parsing and formatting utilities."""


def parse_duration(raw: str) -> int:
    mapping = {"min": 60, "h": 3600, "d": 86400}
    for suffix, mult in mapping.items():
        if raw.endswith(suffix):
            return int(raw[: -len(suffix)]) * mult
    raise ValueError("Unsupported duration")
