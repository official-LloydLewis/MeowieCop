"""Command parser utilities."""


def parse_command(text: str) -> tuple[str, list[str]]:
    parts = text.strip().split()
    if not parts:
        return "", []
    return parts[0].lstrip("/"), parts[1:]
