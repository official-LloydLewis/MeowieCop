"""Thin wrapper for Bale API methods."""


def send_message(chat_id: str, text: str) -> None:
    # TODO: implement Bale API call.
    _ = (chat_id, text)


def delete_message(chat_id: str, message_id: str) -> None:
    _ = (chat_id, message_id)


def ban_chat_member(chat_id: str, user_id: str) -> None:
    _ = (chat_id, user_id)


def get_chat_member(chat_id: str, user_id: str) -> dict:
    _ = (chat_id, user_id)
    return {"is_admin": False}
