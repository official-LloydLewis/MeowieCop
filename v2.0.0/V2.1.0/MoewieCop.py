import os
import time
import re
import logging
import threading
import copy
import tempfile
import random
from typing import Optional, Dict, Any, Tuple, List
import requests
import yaml

##########################
# Config
##########################
BOT_TOKEN = os.getenv("BOT_TOKEN", "ENTER THE TOKEN HERE")
API_BASE = f"https://tapi.bale.ai/bot{BOT_TOKEN}"
DB_PATH = "database.yml"
POLL_TIMEOUT = 30

##########################
# Logging Setup
##########################
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(threadName)s | %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("MeowieHelper")

##########################
# Global Locks
##########################
# Lock for Database Safety
db_lock = threading.Lock()
# Lock for RAM Cache Safety
muted_cache_lock = threading.Lock()

##########################
# In-memory cache
##########################
MUTED_USERS: Dict[int, Dict[int, Dict[str, Any]]] = {}

##########################
# Global Command Lists
##########################
mute_cmds = {"mute", "sokut", "سکوت", "میوت", "خفه"}
unmute_cmds = {"unmute", "بازکردن سکوت", "رفع سکوت", "آزاد", "ازاد"}
ban_cmds = {"ban", "بن", "سیک", "گمشو بیرون", "اخراج"}
unban_cmds = {"unban", "انبن", "آنبن"}
info_cmds = {"info", "راهنما", "-info"}
ALL_COMMANDS = list(mute_cmds | unmute_cmds | ban_cmds | unban_cmds | info_cmds)
ALL_COMMANDS.sort(key=len, reverse=True)

##########################
# YAML helpers
##########################
def _ensure_yaml_file(path: str, default_obj: dict) -> None:
    """Create YAML file if not exists."""
    if not os.path.exists(path):
        try:
            with open(path, "w", encoding="utf-8") as f:
                yaml.safe_dump(default_obj, f, allow_unicode=True, sort_keys=False)
        except IOError as e:
            logger.error("Cannot create YAML file %s: %s", path, e)

def load_yaml(path: str, default_obj: dict) -> dict:
    """Load YAML data safely."""
    try:
        _ensure_yaml_file(path, default_obj)
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else default_obj.copy()
    except Exception as e:
        logger.error("Failed to load YAML %s: %s", path, e)
        return default_obj.copy()

def save_yaml_atomic(path: str, data: dict) -> None:
    """Save YAML data atomically to prevent corruption."""
    dir_name = os.path.dirname(path) or '.'
    try:
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
                f.flush()
                os.fsync(f.fileno())
        except Exception:
            os.unlink(tmp_path)
            raise
        os.replace(tmp_path, path)
    except Exception as e:
        logger.error("Failed to save YAML atomically %s: %s", path, e)

##########################
# Database Helpers
##########################
def load_db() -> dict:
    """Load database with lock."""
    with db_lock:
        default = {"users": {}, "muted": {}, "blacklisted_users": {}}
        db = load_yaml(DB_PATH, default)
        db.setdefault("users", {})
        db.setdefault("muted", {})
        db.setdefault("blacklisted_users", {})
        return copy.deepcopy(db)

def save_db(db: dict) -> None:
    """Save database with lock."""
    with db_lock:
        db.setdefault("users", {})
        db.setdefault("muted", {})
        db.setdefault("blacklisted_users", {})
        save_yaml_atomic(DB_PATH, db)

##########################
# API wrapper
##########################
def api_call(method: str, payload: Optional[dict] = None, http_method: str = "POST", max_retries: int = 5) -> dict:
    """Make API call with robust retry logic."""
    url = f"{API_BASE}/{method}"
    payload = payload or {}
    attempt = 0
    
    while True:
        try:
            if http_method.upper() == "GET":
                r = requests.get(url, params=payload, timeout=60)
            else:
                r = requests.post(url, json=payload, timeout=60)
            
            # Handle Rate Limiting
            if r.status_code == 429:
                retry_after = int(r.headers.get("Retry-After", 5))
                logger.warning("Rate limit (429) on %s - waiting %ds", method, retry_after)
                time.sleep(retry_after)
                continue
            
            # Handle Server Errors (5xx) with Exponential Backoff + Jitter
            if r.status_code >= 500 and attempt < max_retries:
                base_wait = 0.5 * (2 ** attempt)
                jitter = random.uniform(0, 0.5)
                wait = min(15, base_wait + jitter)
                logger.warning("API %s Error %s (Attempt %s) - retrying in %.2fs", method, r.status_code, attempt + 1, wait)
                time.sleep(wait)
                attempt += 1
                continue
            
            r.raise_for_status()
            return r.json()
            
        except requests.exceptions.HTTPError as e:
            logger.error("HTTP Error on %s: %s", method, e)
            return {"ok": False, "error": str(e)}
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt < max_retries:
                wait = min(10, 0.5 * (2 ** attempt))
                logger.warning("Conn/Timeout on %s - retrying in %.1fs", method, wait)
                time.sleep(wait)
                attempt += 1
                continue
            logger.error("Conn/Timeout fatal on %s: %s", method, e)
            return {"ok": False, "error": str(e)}
        except Exception as e:
            logger.critical("Unexpected error in API %s: %s", method, e)
            return {"ok": False, "error": str(e)}
            
    return {"ok": False, "error": "max_retries_reached"}

def get_user_name_from_id(chat_id: int, user_id: int) -> str:
    """Get user name by ID."""
    try:
        res = api_call("getChatMember", {"chat_id": chat_id, "user_id": user_id}, "GET")
        if res.get("ok"):
            user_obj = res.get("result", {}).get("user", {})
            username = user_obj.get("username", "")
            if username:
                return f"@{username}"
            return user_obj.get("first_name", "User")
    except Exception as e:
        logger.debug(f"Name fetch fail for {user_id}: {e}")
    return f"کاربر {user_id}"

def send_message(chat_id, text, reply_to_message_id=None, parse_mode=None):
    """Send message to chat."""
    payload = {"chat_id": chat_id, "text": text, "reply_to_message_id": reply_to_message_id}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    return api_call("sendMessage", payload)

##########################
# Utilities
##########################
def now_ts() -> int:
    """Get current timestamp."""
    return int(time.time())

def update_user_cache(msg: dict) -> None:
    """Update user cache in database."""
    db = load_db()
    chat_id = msg.get("chat", {}).get("id")
    user = msg.get("from", {})
    if not chat_id or not user:
        return
    
    user_id = user.get("id")
    username = user.get("username")
    first_name = user.get("first_name")
    
    if not user_id:
        return
        
    chat_str = str(chat_id)
    db["users"].setdefault(chat_str, {})
    if username:
        db["users"][chat_str][username.lower().lstrip("@")] = user_id
    if first_name:
        key = first_name.strip().lower()
        if key not in db["users"][chat_str]:
            db["users"][chat_str][key] = user_id
    save_db(db)

def is_admin(chat_id: int, user_id: int) -> bool:
    """Check if user is admin."""
    try:
        res = api_call("getChatMember", {"chat_id": chat_id, "user_id": user_id}, "GET")
        if not res.get("ok"):
            return False
        return res.get("result", {}).get("status") in ("administrator", "creator")
    except Exception as e:
        logger.error("Admin check error: %s", e)
        return False

##########################
# Time Parser & Formatter
##########################
def parse_time(time_str: str) -> Optional[int]:
    """Parse time string to seconds."""
    if not time_str:
        return None
    time_str = time_str.strip().lower()
    match = re.match(r'^(\d+)\s*(min|h|d|w)$', time_str)
    if not match:
        return None
    value = int(match.group(1))
    unit = match.group(2)
    multipliers = {'min': 60, 'h': 3600, 'd': 86400, 'w': 604800}
    return value * multipliers[unit]

def format_duration(seconds: int) -> str:
    """Format seconds to Persian duration string."""
    if seconds <= 0:
        return "نامحدود"
    def to_persian_num(n):
        return str(n).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    parts = []
    if days > 0: parts.append(f"{to_persian_num(days)} روز")
    if hours > 0: parts.append(f"{to_persian_num(hours)} ساعت")
    if minutes > 0: parts.append(f"{to_persian_num(minutes)} دقیقه")
    if not parts:
        return f"{to_persian_num(seconds)} ثانیه"
    return " و ".join(parts)

##########################
# Blacklist helpers
##########################
def add_to_blacklist(user_id: int, username: str = "", reason: str = "") -> None:
    """Add user to blacklist."""
    db = load_db()
    db["blacklisted_users"][str(user_id)] = {
        "username": username,
        "reason": reason,
        "updated_at": now_ts()
    }
    save_db(db)

def remove_from_blacklist(user_id: int) -> None:
    """Remove user from blacklist."""
    db = load_db()
    db["blacklisted_users"].pop(str(user_id), None)
    save_db(db)

def is_blacklisted(user_id: int) -> bool:
    """Check if user is blacklisted."""
    db = load_db()
    return str(user_id) in db.get("blacklisted_users", {})

##########################
# Mute logic
##########################
def _normalize_mute_data(old_data: Any) -> Dict[str, Any]:
    """Normalize mute data structure."""
    if isinstance(old_data, dict):
        old_data.setdefault("until", 0)
        old_data.setdefault("duration_raw", "infinity")
        old_data.setdefault("duration_seconds", 0)
        old_data.setdefault("admin_id", 0)
        old_data.setdefault("timestamp_action", 0)
        old_data.setdefault("username", "")
        return old_data
    return {"until": 9999999999, "duration_raw": "infinity", "duration_seconds": 0, "admin_id": 0, "timestamp_action": now_ts(), "username": ""}

def add_mute_transaction(chat_id: int, user_id: int, duration_seconds: int, duration_raw: str, admin_id: int, username: str = "") -> None:
    """Add mute with atomic DB and Cache update."""
    with db_lock:
        db = load_yaml(DB_PATH, {"users": {}, "muted": {}, "blacklisted_users": {}})
        db.setdefault("muted", {})
        
        chat_str, user_str = str(chat_id), str(user_id)
        until_ts = now_ts() + duration_seconds if duration_seconds > 0 else 9999999999
        
        mute_data = {
            "until": until_ts,
            "duration_raw": duration_raw,
            "duration_seconds": duration_seconds,
            "admin_id": admin_id,
            "timestamp_action": now_ts(),
            "username": username
        }
        
        db["muted"].setdefault(chat_str, {})
        db["muted"][chat_str][user_str] = mute_data
        
        save_yaml_atomic(DB_PATH, db)

    with muted_cache_lock:
        MUTED_USERS.setdefault(chat_id, {})
        MUTED_USERS[chat_id][user_id] = mute_data

def remove_mute_transaction(chat_id: int, user_id: int) -> None:
    """Remove mute with atomic DB and Cache update."""
    with db_lock:
        db = load_yaml(DB_PATH, {"users": {}, "muted": {}, "blacklisted_users": {}})
        db.setdefault("muted", {})
        chat_str, user_str = str(chat_id), str(user_id)
        
        if chat_str in db["muted"]:
            db["muted"][chat_str].pop(user_str, None)
            if not db["muted"][chat_str]:
                db["muted"].pop(chat_str, None)
        save_yaml_atomic(DB_PATH, db)

    with muted_cache_lock:
        if chat_id in MUTED_USERS:
            MUTED_USERS[chat_id].pop(user_id, None)
            if not MUTED_USERS[chat_id]:
                MUTED_USERS.pop(chat_id, None)

def restore_mutes_from_db() -> None:
    """Restore mutes from DB on startup, removing expired ones."""
    logger.info("Restoring mutes from DB...")
    db = load_db()
    muted = db.get("muted", {})
    current_time = now_ts()
    
    restored_count = 0
    removed_expired = 0
    
    with muted_cache_lock:
        for chat_id_str, members in muted.items():
            try:
                chat_id = int(chat_id_str)
                MUTED_USERS.setdefault(chat_id, {})
                for user_id_str, data in members.items():
                    user_id = int(user_id_str)
                    data = _normalize_mute_data(data)
                    
                    # Check expiration immediately
                    if data["until"] < current_time and data["until"] != 9999999999:
                        removed_expired += 1
                        continue
                        
                    MUTED_USERS[chat_id][user_id] = data
                    restored_count += 1
            except (ValueError, KeyError) as e:
                logger.warning("Failed to restore mute for %s: %s", chat_id_str, e)
                
    logger.info(f"Restored {restored_count} mutes. Removed {removed_expired} expired mutes.")

def resolve_user(chat_id: int, username_from_text: str = None, reply_user: dict = None) -> Tuple[Optional[int], Optional[str]]:
    """Resolve user ID from text or reply."""
    # 1. Reply Priority (Highest)
    if reply_user:
        return reply_user.get("id"), reply_user.get("username", "")
        
    if not username_from_text:
        return None, None
        
    db = load_db()
    chat_users = db.get("users", {}).get(str(chat_id), {})
    key = username_from_text.lower().lstrip("@")
    
    # 2. Exact Match
    if key in chat_users:
        return chat_users[key], key
        
    # 3. Unique Prefix Match
    candidates = []
    for k, uid in chat_users.items():
        if k.startswith(key) and len(k) >= 3:
            candidates.append((k, uid))
            
    if candidates:
        candidates.sort(key=lambda x: len(x[0]))
        return candidates[0][1], candidates[0][0]
        
    return None, None

def handle_mute(chat_id: int, msg_id: int, msg: dict, target_id: int, username: str, duration_seconds: int, duration_raw: str) -> None:
    """Handle mute command."""
    sender_id = msg.get("from", {}).get("id")
    add_mute_transaction(chat_id, target_id, duration_seconds, duration_raw, sender_id, username)
    
    readable_time = format_duration(duration_seconds) if duration_seconds > 0 else "نامحدود"
    mention = f"@{username}" if username else f"کاربر {target_id}"
    admin_name = get_user_name_from_id(chat_id, sender_id)
    
    if duration_seconds > 0:
        send_message(chat_id, f"🔇 ادمین {admin_name} کاربر {mention} را برای {readable_time} میوت کرد!", msg_id)
    else:
        send_message(chat_id, f"🔇 ادمین {admin_name} کاربر {mention} را برای همیشه میوت کرد!", msg_id)
    logger.info(f"Mute applied: {mention} for {readable_time} by {admin_name}")

def handle_unmute(chat_id: int, msg_id: int, msg: dict, target_id: int, username: str) -> None:
    """Handle unmute command."""
    sender_id = msg.get("from", {}).get("id")
    remove_mute_transaction(chat_id, target_id)
    
    mention = f"@{username}" if username else f"کاربر {target_id}"
    admin_name = get_user_name_from_id(chat_id, sender_id)
    send_message(chat_id, f"🔊 ادمین {admin_name} کاربر {mention} را از سکوت آزاد کرد!", msg_id)
    logger.info(f"Unmute applied: {mention} by {admin_name}")

def enforce_mute(msg: dict) -> None:
    """Enforce mute by deleting messages."""
    chat_id = msg.get("chat", {}).get("id")
    user_id = msg.get("from", {}).get("id")
    message_id = msg.get("message_id")
    
    if chat_id is None or user_id is None:
        return
        
    is_muted = False
    mute_data = None
    
    with muted_cache_lock:
        if chat_id in MUTED_USERS and user_id in MUTED_USERS[chat_id]:
            mute_data = MUTED_USERS[chat_id][user_id]
            is_muted = True
            
    if is_muted:
        until = mute_data.get("until", 0)
        current_time = now_ts()
        
        if current_time >= until and until != 9999999999:
            # Expired during message processing
            logger.info(f"Mute expired for {user_id} in {chat_id} during enforce_mute.")
            remove_mute_transaction(chat_id, user_id)
        else:
            # Still muted
            try:
                api_call("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
            except Exception as e:
                logger.error("Delete msg failed: %s", e)

def check_expired_mutes():
    """Background thread to check and remove expired mutes."""
    while True:
        try:
            time.sleep(30)
            current_time = now_ts()
            expired_mutes = []
            
            with muted_cache_lock:
                for chat_id, users in list(MUTED_USERS.items()):
                    for user_id, mute_data in list(users.items()):
                        until = mute_data.get("until", 0)
                        if until != 9999999999 and current_time >= until:
                            expired_mutes.append((chat_id, user_id, mute_data))
            
            for chat_id, user_id, mute_data in expired_mutes:
                try:
                    username = mute_data.get("username", "")
                    mention = f"@{username}" if username else f"کاربر {user_id}"
                    send_message(chat_id, f"⏰ زمان سکوت {mention} به پایان رسید.")
                    remove_mute_transaction(chat_id, user_id)
                    logger.info(f"Auto-unmuted {mention}")
                except Exception as e:
                    logger.error(f"Auto-unmute error: {e}")
                    
        except Exception as e:
            logger.error(f"Checker thread error: {e}")
            time.sleep(5)

##########################
# Ban logic
##########################
def handle_ban(chat_id: int, msg_id: int, msg: dict, target_id: int, username: str) -> None:
    """Handle ban command."""
    sender_id = msg.get("from", {}).get("id")
    mention = f"@{username}" if username else f"کاربر {target_id}"
    admin_name = get_user_name_from_id(chat_id, sender_id)
    
    add_to_blacklist(target_id, username, "")
    r = api_call("banChatMember", {"chat_id": chat_id, "user_id": target_id})
    
    if r.get("ok"):
        send_message(chat_id, f"🚫 ادمین {admin_name} کاربر {mention} را بن کرد!", msg_id)
        logger.info(f"Ban applied: {mention}")
    else:
        send_message(chat_id, f"❌ خطا در بن: {r.get('description') or r.get('error')}", msg_id)

def handle_unban(chat_id: int, msg_id: int, msg: dict, target_id: int, username: str) -> None:
    """Handle unban command."""
    sender_id = msg.get("from", {}).get("id")
    mention = f"@{username}" if username else f"کاربر {target_id}"
    admin_name = get_user_name_from_id(chat_id, sender_id)
    
    remove_from_blacklist(target_id)
    r = api_call("unbanChatMember", {"chat_id": chat_id, "user_id": target_id})
    
    if r.get("ok"):
        send_message(chat_id, f"🔓 ادمین {admin_name} کاربر {mention} را آنبن کرد!", msg_id)
        logger.info(f"Unban applied: {mention}")
    else:
        send_message(chat_id, f"❌ خطا در آنبن: {r.get('description') or r.get('error')}", msg_id)

##########################
# Join handler
##########################
def auto_reban_on_join(msg: dict) -> None:
    """Auto-reban blacklisted users on join."""
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
        
    if isinstance(joined_user, dict) and "user" in joined_user:
        user_obj = joined_user.get("user") or {}
    else:
        user_obj = joined_user or {}
        
    user_id = user_obj.get("id")
    username = user_obj.get("username", "")
    
    if user_id and username:
        db = load_db()
        db.setdefault("users", {})
        db["users"].setdefault(str(chat_id), {})
        db["users"][str(chat_id)][username.lower()] = user_id
        save_db(db)
        
    if user_id is None:
        return
        
    if is_blacklisted(user_id):
        try:
            api_call("banChatMember", {"chat_id": chat_id, "user_id": user_id})
            api_call("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})
            logger.warning(f"Auto-rebanned blacklisted user {user_id} on join.")
        except Exception as e:
            logger.error("Auto-reban fail: %s", e)

##########################
# Command parsing
##########################
def parse_mention_and_time(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse mention and time from text."""
    username = None
    time_str = None
    mentions = re.findall(r'@(\w+)', text)
    if mentions:
        username = mentions[0]
    times = re.findall(r'(\d+\s*(?:min|h|d|w))', text, re.IGNORECASE)
    if times:
        time_str = times[-1].strip()
    return username, time_str

def detect_command(text: str) -> Optional[Tuple[str, Optional[str], Optional[str]]]:
    """Detect command from text."""
    text = (text or "").strip()
    if not text:
        return None
    if text.startswith("/"):
        text = text[1:]
        
    for cmd in ALL_COMMANDS:
        if text.startswith(cmd):
            after_cmd_idx = len(cmd)
            if len(text) == after_cmd_idx:
                return (cmd, None, None)
            if text[after_cmd_idx] != ' ':
                continue
            rest = text[after_cmd_idx:].strip()
            if not rest:
                return (cmd, None, None)
            if cmd in info_cmds:
                return (cmd, None, None)
            username, time_str = parse_mention_and_time(rest)
            return (cmd, username, time_str)
    return None

def handle_message(msg: dict) -> None:
    """Handle incoming message."""
    update_user_cache(msg)
    enforce_mute(msg)
    auto_reban_on_join(msg)
    
    text = msg.get("text", "")
    result = detect_command(text)
    if not result:
        return
        
    cmd, username_from_text, time_str_from_text = result
    chat_id = msg.get("chat", {}).get("id")
    sender_id = msg.get("from", {}).get("id")
    msg_id = msg.get("message_id")
    
    if chat_id is None or sender_id is None or msg_id is None:
        return
        
    if not is_admin(chat_id, sender_id):
        send_message(chat_id, "⛔ شما ادمین نیستید", msg_id)
        return
        
    requires_target = cmd not in info_cmds
    target_id = None
    username_for_msg = None
    
    # 1. Check Entities (Mentions)
    entities = msg.get("entities", [])
    if entities:
        for entity in entities:
            if entity.get("type") == "text_mention":
                user_obj = entity.get("user", {})
                target_id = user_obj.get("id")
                username_for_msg = user_obj.get("username", "")
                break
            elif entity.get("type") == "mention":
                offset = entity.get("offset")
                length = entity.get("length")
                mention_text = text[offset:offset+length]
                username_clean = mention_text.lstrip("@").lower()
                t_id, u_name = resolve_user(chat_id, username_from_text=username_clean)
                if t_id:
                    target_id = t_id
                    username_for_msg = u_name
                    break
                    
    # 2. Reply
    if target_id is None and requires_target:
        reply = msg.get("reply_to_message")
        reply_user = None
        if reply:
            reply_user = reply.get("from", {})
        t_id, u_name = resolve_user(chat_id, username_from_text=username_from_text, reply_user=reply_user)
        if t_id:
            target_id = t_id
            username_for_msg = u_name
            
    if requires_target and target_id is None:
        send_message(
            chat_id,
            f"⚠️ کاربر @{username_from_text if username_from_text else 'نامشخص'} پیدا نشد. "
            f"لطفاً روی پیام او ریپلای کنید یا از او بخواهید یک پیام ارسال کند.",
            msg_id
        )
        return
        
    if cmd in mute_cmds:
        if time_str_from_text:
            parsed_seconds = parse_time(time_str_from_text)
            if parsed_seconds:
                duration_seconds = parsed_seconds
                duration_raw = time_str_from_text
            else:
                send_message(chat_id, "⚠️ فرمت زمان اشتباه است. مثال: 10min, 2h, 3d, 1w", msg_id)
                return
        else:
            duration_seconds = 0
            duration_raw = "infinity"
        handle_mute(chat_id, msg_id, msg, target_id, username_for_msg, duration_seconds, duration_raw)
        
    elif cmd in unmute_cmds:
        handle_unmute(chat_id, msg_id, msg, target_id, username_for_msg)
        
    elif cmd in ban_cmds:
        handle_ban(chat_id, msg_id, msg, target_id, username_for_msg)
        
    elif cmd in unban_cmds:
        handle_unban(chat_id, msg_id, msg, target_id, username_for_msg)
        
    elif cmd in info_cmds:
        send_message(
            chat_id,
            "======[ بات پلیس میویی 😼 ]======\n\n"
            "📦 نسخه: 2.1.0 (Stable)  \n"
            "👨‍💻 دولوپر ها: \n"
            "- @karormc\n"
            "- @freakballs\n\n"
            "🧰 کامندها: \n"
            "- بن / انبن\n"
            "- سکوت [زمان] / رفع سکوت\n\n"
            "❓ استفاده: \n"
            "1.  ریپلای: روی پیام کاربر ریپلای کنید و کامند رو بزنید\n"
            "2. منشن: کامند رو بزنید و در آخر پیام کاربر مورد نظر رو تگ کنید\n\n"
            "⛔ ادمین های فعلی گروه:  \n"
            "- @TahaFz0\n"
            "- @RealMeow\n\n"
            "- @CallmeMonte\n"
            "- @neznayu\n"
            "- @ryuIR\n"
            "- @swsahar\n"
            "=============================",
            parse_mode="Markdown"
        )

##########################
# Update loop
##########################
def process_update(update: dict) -> None:
    """Process a single update."""
    try:
        msg = update.get("message")
        if msg:
            handle_message(msg)
    except Exception as e:
        logger.error("Error processing update %s: %s", update.get("update_id"), e, exc_info=True)

def main() -> None:
    """Main entry point."""
    logger.info("Starting bot...")
    restore_mutes_from_db()
    mute_checker = threading.Thread(target=check_expired_mutes, daemon=True)
    mute_checker.start()
    logger.info("Mute expiration checker started")
    
    offset = None
    logger.info("Bot started successfully")
    
    while True:
        try:
            params = {"timeout": POLL_TIMEOUT}
            if offset is not None:
                params["offset"] = offset
            res = api_call("getUpdates", params, "GET")
            
            if res.get("ok"):
                updates = res.get("result", [])
                if updates:
                    for upd in updates:
                        offset = upd["update_id"] + 1
                        process_update(upd)
            if not res.get("ok") or not res.get("result"):
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            break
        except Exception as e:
            logger.critical("Main loop crashed: %s", e, exc_info=True)
            time.sleep(5)

if __name__ == "__main__":
    print("""
                ███╗   ███╗███████╗ ██████╗ ██╗    ██╗██╗███████╗     ██████╗ ██████╗ ██████╗
                ████╗ ████║██╔════╝██╔═══██╗██║    ██║██║██╔════╝    ██╔════╝██╔═══██╗██╔══██╗
                ██╔████╔██║█████╗  ██║   ██║██║ █╗ ██║██║█████╗      ██║     ██║   ██║██████╔╝
                ██║╚██╔╝██║██╔══╝  ██║   ██║██║███╗██║██║██╔══╝      ██║     ██║   ██║██╔═══╝
                ██║ ╚═╝ ██║███████╗╚██████╔╝╚███╔███╔╝██║███████╗    ╚██████╗╚██████╔╝██║
                ╚═╝     ╚═╝╚══════╝ ╚═════╝  ╚══╝╚══╝ ╚═╝╚══════╝     ╚═════╝ ╚═════╝ ╚═╝  version 2.1.0
                ===============================  Production Ready  ============================
    """)
    main()