import os
import time
import logging
from typing import Optional, Dict, Any, Tuple
import requests
import yaml

# =========================
# Config
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN", "ENTER THE TOKEN HERE")
API_BASE = f"https://tapi.bale.ai/bot{BOT_TOKEN}"
MUTE_DB_PATH = "database.yml"     
BLACKLIST_PATH = "blacklist.yml"
POLL_TIMEOUT = 30

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("MeowieHelper")

# In-memory mute cache
# Structure: { chat_id: { user_id: {"username": "@name", "until": timestamp} } }
MUTED_USERS: Dict[int, Dict[int, Dict[str, Any]]] = {}

# =========================
# YAML helpers
# =========================
def _ensure_yaml_file(path: str, default_obj: dict) -> None:
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(default_obj, f, allow_unicode=True, sort_keys=False)

def load_yaml(path: str, default_obj: dict) -> dict:
    try:
        _ensure_yaml_file(path, default_obj)
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else default_obj.copy()
    except Exception as e:
        logger.error("Failed to load YAML %s: %s", path, e)
        return default_obj.copy()

def save_yaml(path: str, data: dict) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
    except Exception as e:
        logger.error("Failed to save YAML %s: %s", path, e)

def load_db() -> dict:
    db = load_yaml(MUTE_DB_PATH, {"users": {}, "muted": {}})
    db.setdefault("users", {})
    db.setdefault("muted", {})
    return db

def save_db(db: dict) -> None:
    db.setdefault("users", {})
    db.setdefault("muted", {})
    save_yaml(MUTE_DB_PATH, db)

def load_blacklist() -> dict:
    data = load_yaml(BLACKLIST_PATH, {"blacklisted_users": {}})
    data.setdefault("blacklisted_users", {})
    return data

def save_blacklist(data: dict) -> None:
    data.setdefault("blacklisted_users", {})
    save_yaml(BLACKLIST_PATH, data)

# =========================
# API wrapper
# =========================
def api_call(method: str, payload: Optional[dict] = None, http_method: str = "POST") -> dict:
    url = f"{API_BASE}/{method}"
    payload = payload or {}
    try:
        if http_method.upper() == "GET":
            r = requests.get(url, params=payload, timeout=60)
        else:
            r = requests.post(url, json=payload, timeout=60)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error("API error on %s: %s", method, e)
        return {"ok": False, "error": str(e)}

def send_message(chat_id, text, reply_to_message_id=None, parse_mode=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "reply_to_message_id": reply_to_message_id,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    return api_call("sendMessage", payload)

# =========================
# Utilities
# =========================
def now_ts() -> int:
    return int(time.time())

def summarize_replied_message(reply: dict) -> str:
    if not reply:
        return "unknown"
    text = (reply.get("text") or "").strip()
    if text:
        return text
    caption = (reply.get("caption") or "").strip()
    if caption:
        return caption
    for key in ("photo", "sticker", "voice", "video", "animation", "document", "audio", "video_note"):
        if reply.get(key):
            return key
    return "other"

def resolve_target_from_reply(msg: dict) -> Tuple[Optional[int], Optional[str], str]:
    """
    Returns: (user_id, username_string, reason_text)
    """
    reply = msg.get("reply_to_message")
    if not reply:
        return None, None, "no_reply"
    
    user = reply.get("from", {}) or {}
    user_id = user.get("id")
    username = user.get("username")
    username_str = f"@{username}" if username else ""
    
    reason_text = summarize_replied_message(reply)
    return user_id, username_str, reason_text

def is_admin(chat_id: int, user_id: int) -> bool:
    res = api_call("getChatMember", {"chat_id": chat_id, "user_id": user_id}, "GET")
    if not res.get("ok"):
        return False
    status = res.get("result", {}).get("status")
    return status in ("administrator", "creator")

# =========================
# Blacklist helpers
# =========================
def add_to_blacklist(user_id: int, username: str = "", reason: str = "") -> None:
    data = load_blacklist()
    data["blacklisted_users"][str(user_id)] = {
        "username": username or "",
        "reason": reason or "",
        "updated_at": now_ts(),
    }
    save_blacklist(data)

def remove_from_blacklist(user_id: int) -> None:
    data = load_blacklist()
    data["blacklisted_users"].pop(str(user_id), None)
    save_blacklist(data)

def is_blacklisted(user_id: int) -> bool:
    data = load_blacklist()
    return str(user_id) in data.get("blacklisted_users", {})

def blacklist_record(user_id: int) -> dict:
    data = load_blacklist()
    return data.get("blacklisted_users", {}).get(str(user_id), {})

# =========================
# Mute logic (FIXED)
# =========================

def add_mute(chat_id: int, user_id: int, username: str = "") -> None:
    """
    Adds a user to the mute list with their username and an indefinite 'until' time.
    Note: If you want timed mutes, you need to pass 'until' timestamp here.
    For now, we set it to a far future date so auto-unmute doesn't trigger immediately,
    but admin can still unmute manually.
    """
    # Prepare data structure
    mute_data = {
        "username": username,
        "until": 9999999999  # Far future
    }
    
    # Update in-memory
    MUTED_USERS.setdefault(chat_id, {})[user_id] = mute_data
    
    # Update in DB
    db = load_db()
    db.setdefault("muted", {})
    db["muted"].setdefault(str(chat_id), {})
    db["muted"][str(chat_id)][str(user_id)] = mute_data
    save_db(db)

def remove_mute(chat_id: int, user_id: int) -> None:
    """
    Removes a user from the mute list in both memory and DB.
    """
    # Remove from memory
    if chat_id in MUTED_USERS:
        MUTED_USERS[chat_id].pop(user_id, None)
        if not MUTED_USERS[chat_id]:
            MUTED_USERS.pop(chat_id, None)
            
    # Remove from DB
    db = load_db()
    if str(chat_id) in db.get("muted", {}):
        db["muted"][str(chat_id)].pop(str(user_id), None)
        if not db["muted"][str(chat_id)]:
            db["muted"].pop(str(chat_id), None)
    save_db(db)

def restore_mutes_from_db() -> None:
    """
    Loads muted users from DB into memory.
    Handles old format (True) and converts to new format.
    """
    db = load_db()
    muted = db.get("muted", {})
    
    for chat_id_str, members in muted.items():
        try:
            chat_id = int(chat_id_str)
            MUTED_USERS.setdefault(chat_id, {})
            
            for user_id_str, value in members.items():
                user_id = int(user_id_str)
                
                # If old format (True or just missing keys), convert to new format
                if value is True or (isinstance(value, dict) and "until" not in value):
                    # We don't know the username here if it wasn't saved, so we leave it empty
                    # or try to fetch it later. For now, we set a default structure.
                    new_data = {
                        "username": "",
                        "until": 9999999999
                    }
                    MUTED_USERS[chat_id][user_id] = new_data
                    # Update DB immediately to fix structure
                    db["muted"][chat_id_str][user_id_str] = new_data
                else:
                    # New format, just load it
                    MUTED_USERS[chat_id][user_id] = value
        except Exception as e:
            logger.error(f"Error restoring mute for {chat_id_str}: {e}")
            continue
            
    # Save back the fixed DB structure
    save_db(db)

def handle_mute(chat_id: int, msg_id: int, msg: dict) -> None:
    target_id, username, reason = resolve_target_from_reply(msg)
    if not target_id:
        send_message(chat_id, "⚠️ روی پیام کاربر ریپلای کنید", msg_id)
        return
    
    add_mute(chat_id, target_id, username)
    send_message(chat_id, f"✅ کاربر {username or target_id} ساکت شد", msg_id)

def handle_unmute(chat_id: int, msg_id: int, msg: dict) -> None:
    target_id, username, reason = resolve_target_from_reply(msg)
    if not target_id:
        send_message(chat_id, "⚠️ روی پیام کاربر ریپلای کنید", msg_id)
        return
        
    remove_mute(chat_id, target_id)
    send_message(chat_id, f"🔓 سکوت کاربر {username or target_id} برداشته شد", msg_id)

def enforce_mute(msg: dict) -> bool:
    chat_id = msg.get("chat", {}).get("id")
    user_id = msg.get("from", {}).get("id")
    if chat_id is None or user_id is None:
        return False
        
    # Check if user is muted
    if chat_id in MUTED_USERS and user_id in MUTED_USERS[chat_id]:
        # Delete the message
        api_call("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})
        return True
    return False

# =========================
# Auto Unmute Logic (FIXED)
# =========================
def check_expired_mutes():
    """
    Checks all muted users. If their 'until' time has passed, removes the mute.
    This runs in a separate loop to avoid blocking the main poll.
    """
    current_time = now_ts()
    
    # Iterate over a copy of items to avoid modification during iteration issues
    chats_to_check = list(MUTED_USERS.keys())
    
    for chat_id in chats_to_check:
        users_to_check = list(MUTED_USERS[chat_id].keys())
        
        for user_id in users_to_check:
            mute_info = MUTED_USERS[chat_id].get(user_id)
            
            if mute_info and isinstance(mute_info, dict):
                until_time = mute_info.get("until", 0)
                username = mute_info.get("username", "")
                
                # If 'until' is 0 or far future (indefinite), skip auto-unmute
                # If you want timed mutes, set 'until' to a specific timestamp in add_mute
                if until_time == 0 or until_time > current_time:
                    continue
                
                # Time is up! Remove mute
                logger.info(f"Auto-unmuting user {user_id} in chat {chat_id} due to expiration.")
                
                # 1. Remove from memory
                remove_mute(chat_id, user_id)
                
                # 2. Send notification (optional, can be annoying if too frequent, so maybe skip or do once)
                # Only send if we have username, otherwise just ID
                display_name = username if username else str(user_id)
                send_message(
                    chat_id, 
                    f"⏰ زمان سکوت کاربر {display_name} تمام شد. سکوت برداشته شد.", 
                    parse_mode="Markdown"
                )

# =========================
# Ban logic
# =========================
def handle_ban(chat_id: int, msg_id: int, msg: dict) -> None:
    target_id, target_username, reason = resolve_target_from_reply(msg)
    if not target_id:
        send_message(chat_id, "⚠️ روی پیام کاربر ریپلای کنید", msg_id)
        return
    
    add_to_blacklist(target_id, target_username, reason)
    r = api_call("banChatMember", {"chat_id": chat_id, "user_id": target_id})
    if r.get("ok"):
        send_message(chat_id, "✅ کاربر بن شد", msg_id)
    else:
        send_message(chat_id, f"❌ خطا در بن: {r.get('description') or r.get('error') or 'unknown'}", msg_id)

def handle_unban(chat_id: int, msg_id: int, msg: dict) -> None:
    target_id, _,_ = resolve_target_from_reply(msg)
    if not target_id:
        send_message(chat_id, "⚠️ روی پیام کاربر ریپلای کنید", msg_id)
        return
    
    remove_from_blacklist(target_id)
    r = api_call("unbanChatMember", {"chat_id": chat_id, "user_id": target_id})
    if r.get("ok"):
        send_message(chat_id, "🔓 کاربر آنبن شد", msg_id)
    else:
        send_message(chat_id, f"❌ خطا در آنبن: {r.get('description') or r.get('error') or 'unknown'}", msg_id)

# =========================
# Join handler: auto re-ban blacklisted users
# =========================
def auto_reban_on_join(msg: dict) -> None:
    chat = msg.get("chat", {}) or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return
    
    joined_user = None
    if "new_chat_member" in msg:
        joined_user = msg.get("new_chat_member")
    elif "new_chat_members" in msg and isinstance(msg["new_chat_members"], list):
        joined_user = msg["new_chat_members"][0] if msg["new_chat_members"] else None
    elif msg.get("new_chat_member", {}).get("user"):
        joined_user = msg["new_chat_member"].get("user")
        
    if not joined_user:
        return
        
    # normalize
    if isinstance(joined_user, dict) and "user" in joined_user:
        user_obj = joined_user.get("user") or {}
    else:
        user_obj = joined_user or {}
        
    user_id = user_obj.get("id")
    if user_id is None:
        return
        
    if is_blacklisted(user_id):
        api_call("banChatMember", {"chat_id": chat_id, "user_id": user_id})
        api_call("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})

# =========================
# Command parsing
# =========================
def detect_command(text: str) -> Optional[str]:
    text = (text or "").strip()
    if text in ("سیک","بن", "انبن", "سکوت", "بازکردن سکوت", "رفع سکوت","ban","unban","mute","unmute","info", "راهنما", "-info"):
        return text
    return None

def handle_message(msg: dict) -> None:
    enforce_mute(msg)
    auto_reban_on_join(msg)
    
    text = msg.get("text", "")
    cmd = detect_command(text)
    
    if not cmd:
        return
        
    chat_id = msg.get("chat", {}).get("id")
    sender_id = msg.get("from", {}).get("id")
    msg_id = msg.get("message_id")
    
    if chat_id is None or sender_id is None or msg_id is None:
        return
        
    if not is_admin(chat_id, sender_id):
        send_message(chat_id, "⛔ شما ادمین نیستید", msg_id)
        return
        
    if cmd in ("بن", "سیک", "ban"):
        handle_ban(chat_id, msg_id, msg)
    elif cmd in ("انبن", "unban"):
        handle_unban(chat_id, msg_id, msg)
    elif cmd in ("سکوت", "mute"):
        handle_mute(chat_id, msg_id, msg)
    elif cmd in ("بازکردن سکوت", "رفع سکوت", "unmute"):
        handle_unmute(chat_id, msg_id, msg)
    elif cmd in ("info", "راهنما", "-info"):
        send_message(
            chat_id,
            "*=====[ بات هلپر میویی 😼 ]=====*\n\n"
            "📦 نسخه: _1.7.1-b (Fixed Mute Structure)_\n"
            "👨‍💻 توسعه‌دهندگان:\n"
            "• @karormc\n"
            "• @freakballs\n\n"
            "🧰 کامندها:\n"
            "• بن / انبن\n"
            "• سکوت / رفع سکوت\n\n"
            "*===========================*",
            parse_mode="Markdown"
        )

# =========================
# Update loop
# =========================
def process_update(update: dict) -> None:
    msg = update.get("message")
    if msg:
        handle_message(msg)

def main() -> None:
    logger.info("Loading database and restoring mutes...")
    restore_mutes_from_db()
    logger.info("Mutes restored.")
    
    offset = None
    logger.info("Bot started")
    
    last_mute_check = 0
    
    while True:
        # 1. Check expired mutes every 10 seconds
        current_time = now_ts()
        if current_time - last_mute_check >= 10:
            check_expired_mutes()
            last_mute_check = current_time
            
        # 2. Poll updates
        params = {"timeout": POLL_TIMEOUT}
        if offset is not None:
            params["offset"] = offset
            
        res = api_call("getUpdates", params, "GET")
        if res.get("ok"):
            for upd in res.get("result", []):
                offset = upd["update_id"] + 1
                process_update(upd)
                
        time.sleep(1)

if __name__ == "__main__":
    print("""   
            ███╗   ███╗███████╗ ██████╗ ██╗    ██╗██╗███████╗    ██╗  ██╗███████╗██╗     ██████╗ ███████╗██████╗
            ████╗ ████║██╔════╝██╔═══██╗██║    ██║██║██╔════╝    ██║  ██║██╔════╝██║     ██╔══██╗██╔════╝██╔══██╗
            ██╔████╔██║█████╗  ██║   ██║██║ █╗ ██║██║█████╗      ███████║█████╗  ██║     ██████╔╝█████╗  ██████╔╝
            ██║╚██╔╝██║██╔══╝  ██║   ██║██║███╗██║██║██╔══╝      ██╔══██║██╔══╝  ██║     ██╔═══╝ ██╔══╝  ██╔══██╗
            ██║ ╚═╝ ██║███████╗╚██████╔╝╚███╔███╔╝██║███████╗    ██║  ██║███████╗███████╗██║     ███████╗██║  ██║
            ╚═╝     ╚═╝╚══════╝ ╚═════╝  ╚══╝╚══╝ ╚═╝╚══════╝    ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝     ╚══════╝╚═╝  ╚═╝ v1.9.0
        """)
    main()