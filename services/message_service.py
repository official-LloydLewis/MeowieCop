"""Message template loader and formatter."""

from core.database import load_yaml


MESSAGES_PATH = "config/messages.yml"


def get_message(key: str, **kwargs: str) -> str:
    messages = load_yaml(MESSAGES_PATH)
    template = messages.get(key, key)
    return template.format(**kwargs)
