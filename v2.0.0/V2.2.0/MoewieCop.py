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
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")
API_BASE = f"https://tapi.bale.ai/bot{BOT_TOKEN}"
DB_PATH = "database.yml"
POLL_TIMEOUT = 30
PERMANENT_MUTE_TIMESTAMP = 9999999999
MAX_MUTE_DURATION = 365 * 86400

USER_CACHE_TTL = 24 * 3600  
USER_CACHE_MAX_SIZE = 5000  
USER_CACHE_MAX_CHATS = int(os.getenv("USER_CACHE_MAX_CHATS", "2000"))

MUTED_USERS_MAX_CHATS = int(os.getenv("MUTED_USERS_MAX_CHATS", "2000"))

RATE_LIMIT_PER_SEC = int(os.getenv("RATE_LIMIT_PER_SEC", "15"))
RATE_LIMIT_BURST = int(os.getenv("RATE_LIMIT_BURST", "30"))

DB_FLUSH_INTERVAL = int(os.getenv("DB_FLUSH_INTERVAL", "5"))

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
db_lock = threading.RLock()
muted_cache_lock = threading.Lock()
user_cache_lock = threading.Lock()

##########################
# Rate limiter state
##########################
_rate_lock = threading.Lock()
_rate_tokens = RATE_LIMIT_BURST
_rate_last = time.monotonic()

##########################
# HTTP Session (Connection Pooling)
##########################
_http_session = requests.Session()

##########################
# In-memory cache
##########################
MUTED_USERS: Dict[int, Dict[int, Dict[str, Any]]] = {}
USER_CACHE: Dict[int, Dict[str, Dict[str, int]]] = {}

CHAT_ACTIVITY: Dict[int, int] = {}
chat_activity_lock = threading.Lock()

USER_PENDING: Dict[int, Dict[str, int]] = {}
user_pending_lock = threading.Lock()

_mute_enforce_locks: Dict[Tuple[int, int], threading.Lock] = {}
_mute_enforce_locks_lock = threading.Lock()

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
    if not os.path.exists(path):
        try:
            with open(path, "w", encoding="utf-8") as f:
                yaml.safe_dump(default_obj, f, allow_unicode=True, sort_keys=False)
        except IOError as e:
            logger.error("Cannot create YAML file %s: %s", path, e)

def load_yaml(path: str, default_obj: dict) -> dict:
    try:
        _ensure_yaml_file(path, default_obj)
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else default_obj.copy()
    except Exception as e:
        logger.error("Failed to load YAML %s: %s", path, e)
        return default_obj.copy()

def _load_yaml_unsafe(path: str, default_obj: dict) -> dict:
    _ensure_yaml_file(path, default_obj)
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else default_obj.copy()

def save_yaml_atomic(path: str, data: dict) -> None:
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
    with db_lock:
        default = {"users": {}, "muted": {}, "blacklisted_users": {}, "admins": {}}
        try:
            db = _load_yaml_unsafe(DB_PATH, default)
        except Exception as e:
            logger.error("Failed to load DB: %s", e)
            db = default.copy()
        db.setdefault("users", {})
        db.setdefault("muted", {})
        db.setdefault("blacklisted_users", {})
        db.setdefault("admins", {})
        return copy.deepcopy(db)

def save_db(db: dict) -> None:
    with db_lock:
        db.setdefault("users", {})
        db.setdefault("muted", {})
        db.setdefault("blacklisted_users", {})
        db.setdefault("admins", {})
        save_yaml_atomic(DB_PATH, db)

##########################
# Rate limiter
##########################
def _rate_limit_acquire():
    global _rate_tokens, _rate_last
    while True:
        with _rate_lock:
            now = time.monotonic()
            elapsed = now - _rate_last
            _rate_tokens = min(RATE_LIMIT_BURST, _rate_tokens + elapsed * RATE_LIMIT_PER_SEC)
            _rate_last = now
            if _rate_tokens >= 1:
                _rate_tokens -= 1
                return
            sleep_for = (1 - _rate_tokens) / max(RATE_LIMIT_PER_SEC, 1)
        time.sleep(sleep_for)

##########################
# API wrapper
##########################
def api_call(method: str, payload: Optional[dict] = None, http_method: str = "POST", max_retries: int = 5, timeout: int = 60) -> dict:
    url = f"{API_BASE}/{method}"
    payload = payload or {}
    attempt = 0

    while True:
        try:
            _rate_limit_acquire()

            if http_method.upper() == "GET":
                r = _http_session.get(url, params=payload, timeout=timeout)
            else:
                r = _http_session.post(url, json=payload, timeout=timeout)

            if r.status_code == 429:
                if attempt >= max_retries:
                    return {"ok": False, "error": "rate_limit_max_retries"}
                retry_after = int(r.headers.get("Retry-After", 5))
                logger.warning("Rate limit (429) on %s - waiting %ds (attempt %d/%d)", 
                            method, retry_after, attempt + 1, max_retries)
                attempt += 1
                time.sleep(retry_after)
                continue

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
    payload = {"chat_id": chat_id, "text": text}
    if reply_to_message_id is not None:
        payload["reply_to_message_id"] = reply_to_message_id
    if parse_mode:
        payload["parse_mode"] = parse_mode
    return api_call("sendMessage", payload)

##########################
# Utilities
##########################
def now_ts() -> int:
    return int(time.time())

def safe_get_chat_id(msg: dict) -> Optional[int]:
    chat = msg.get("chat") or {}
    return chat.get("id")

def safe_get_from_user(msg: dict) -> dict:
    return msg.get("from") or {}

def _touch_chat(chat_id: int) -> None:
    if chat_id is None:
        return
    with chat_activity_lock:
        CHAT_ACTIVITY[chat_id] = now_ts()
        if len(CHAT_ACTIVITY) > USER_CACHE_MAX_CHATS * 2:
            sorted_chats = sorted(CHAT_ACTIVITY.items(), key=lambda x: x[1])
            excess = len(CHAT_ACTIVITY) - USER_CACHE_MAX_CHATS
            for cid, _ in sorted_chats[:excess]:
                CHAT_ACTIVITY.pop(cid, None)

def _prune_user_cache(chat_id: Optional[int] = None) -> None:
    now = now_ts()
    with user_cache_lock:
        targets = [chat_id] if chat_id is not None else list(USER_CACHE.keys())
        for cid in targets:
            cache = USER_CACHE.get(cid)
            if not cache:
                continue

            expired_keys = [k for k, v in cache.items() if now - v.get("ts", 0) > USER_CACHE_TTL]
            for k in expired_keys:
                cache.pop(k, None)

            if len(cache) > USER_CACHE_MAX_SIZE:
                sorted_items = sorted(cache.items(), key=lambda x: x[1].get("ts", 0))
                excess = len(cache) - USER_CACHE_MAX_SIZE
                for i in range(excess):
                    cache.pop(sorted_items[i][0], None)

            if not cache:
                USER_CACHE.pop(cid, None)

def _prune_user_cache_chats() -> None:
    with chat_activity_lock:
        if len(USER_CACHE) <= USER_CACHE_MAX_CHATS:
            return
        sorted_chats = sorted(CHAT_ACTIVITY.items(), key=lambda x: x[1])
        excess = len(USER_CACHE) - USER_CACHE_MAX_CHATS
        to_remove = [cid for cid, _ in sorted_chats if cid in USER_CACHE][:excess]

    if to_remove:
        with user_cache_lock:
            for cid in to_remove:
                USER_CACHE.pop(cid, None)
        with chat_activity_lock:
            for cid in to_remove:
                CHAT_ACTIVITY.pop(cid, None)

def _prune_muted_chats() -> None:
    with muted_cache_lock:
        empty_chats = [cid for cid, users in MUTED_USERS.items() if not users]
        for cid in empty_chats:
            MUTED_USERS.pop(cid, None)

        if len(MUTED_USERS) > MUTED_USERS_MAX_CHATS:
            logger.warning("MUTED_USERS chats exceed limit (%d > %d). Consider reviewing capacity.",
                           len(MUTED_USERS), MUTED_USERS_MAX_CHATS)

def _get_mute_lock(chat_id: int, user_id: int) -> threading.Lock:
    key = (chat_id, user_id)
    with _mute_enforce_locks_lock:
        if key not in _mute_enforce_locks:
            _mute_enforce_locks[key] = threading.Lock()
        return _mute_enforce_locks[key]

def _cleanup_mute_lock(chat_id: int, user_id: int) -> None:
    key = (chat_id, user_id)
    with _mute_enforce_locks_lock:
        lock = _mute_enforce_locks.get(key)
        if lock and not lock.locked():
            _mute_enforce_locks.pop(key, None)

def update_user_cache(msg: dict) -> None:
    chat_id = safe_get_chat_id(msg)
    user = safe_get_from_user(msg)
    if not chat_id or not user:
        return

    user_id = user.get("id")
    username = user.get("username")
    first_name = user.get("first_name")

    if not user_id:
        return

    _touch_chat(chat_id)

    with user_cache_lock:
        USER_CACHE.setdefault(chat_id, {})
        now = now_ts()

        if username:
            uname = username.lower().lstrip("@")
            existing = USER_CACHE[chat_id].get(uname)
            USER_CACHE[chat_id][uname] = {"id": user_id, "ts": now}
            if not existing or existing.get("id") != user_id:
                with user_pending_lock:
                    USER_PENDING.setdefault(chat_id, {})
                    USER_PENDING[chat_id][uname] = user_id

        if first_name:
            key = first_name.strip().lower()
            existing = USER_CACHE[chat_id].get(key)
            USER_CACHE[chat_id][key] = {"id": user_id, "ts": now}
            if not existing or existing.get("id") != user_id:
                with user_pending_lock:
                    USER_PENDING.setdefault(chat_id, {})
                    USER_PENDING[chat_id][key] = user_id

    _prune_user_cache(chat_id)
    _prune_user_cache_chats()

def _flush_user_cache_worker():
    while True:
        try:
            time.sleep(DB_FLUSH_INTERVAL)

            with user_pending_lock:
                if not USER_PENDING:
                    if random.randint(0, 10) == 0:
                        _prune_user_cache_chats()
                        _prune_muted_chats()
                    continue

                pending = copy.deepcopy(USER_PENDING)
                USER_PENDING.clear()

            with db_lock:
                default = {"users": {}, "muted": {}, "blacklisted_users": {}, "admins": {}}
                db = _load_yaml_unsafe(DB_PATH, default)
                db.setdefault("users", {})
                for chat_id, user_map in pending.items():
                    chat_str = str(chat_id)
                    db["users"].setdefault(chat_str, {})
                    for k, uid in user_map.items():
                        db["users"][chat_str][k] = uid
                save_yaml_atomic(DB_PATH, db)

            if random.randint(0, 10) == 0:
                _prune_user_cache_chats()
                _prune_muted_chats()

        except Exception as e:
            logger.error("User cache flush error: %s", e)
            with user_pending_lock:
                USER_PENDING.clear()

def is_admin(chat_id: int, user_id: int) -> bool:
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
    if not time_str:
        return None
    time_str = time_str.strip().lower()
    match = re.match(r'^(\d+)\s*(m|min|h|d|w)$', time_str)
    if not match:
        return None
    value = int(match.group(1))
    if value < 1:
        return None
    unit = match.group(2)
    multipliers = {'m': 60, 'min': 60, 'h': 3600, 'd': 86400, 'w': 604800}
    seconds = value * multipliers[unit]
    if seconds > MAX_MUTE_DURATION:
        return None
    return seconds

def format_duration(seconds: int) -> str:
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
    db = load_db()
    db["blacklisted_users"][str(user_id)] = {
        "username": username,
        "reason": reason,
        "updated_at": now_ts()
    }
    save_db(db)

def remove_from_blacklist(user_id: int) -> None:
    db = load_db()
    db["blacklisted_users"].pop(str(user_id), None)
    save_db(db)

def is_blacklisted(user_id: int) -> bool:
    db = load_db()
    return str(user_id) in db.get("blacklisted_users", {})

##########################
# Mute logic
##########################
def _normalize_mute_data(old_data: dict) -> Dict[str, Any]:
    if isinstance(old_data, dict):
        old_data.setdefault("until", 0)
        old_data.setdefault("duration_raw", "infinity")
        old_data.setdefault("duration_seconds", 0)
        old_data.setdefault("admin_id", 0)
        old_data.setdefault("timestamp_action", 0)
        old_data.setdefault("username", "")
        return old_data
    return {
        "until": PERMANENT_MUTE_TIMESTAMP,
        "duration_raw": "infinity",
        "duration_seconds": 0,
        "admin_id": 0,
        "timestamp_action": now_ts(),
        "username": ""
    }

def add_mute_transaction(chat_id: int, user_id: int, duration_seconds: int, duration_raw: str, admin_id: int, username: str = "") -> None:
    with db_lock:
        db = _load_yaml_unsafe(DB_PATH, {"users": {}, "muted": {}, "blacklisted_users": {}, "admins": {}})
        db.setdefault("muted", {})
        chat_str, user_str = str(chat_id), str(user_id)
        until_ts = now_ts() + duration_seconds if duration_seconds > 0 else PERMANENT_MUTE_TIMESTAMP

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

    try:
        with muted_cache_lock:
            MUTED_USERS.setdefault(chat_id, {})
            MUTED_USERS[chat_id][user_id] = mute_data
    except Exception as e:
        logger.error("Cache update failed for mute: %s", e)

def remove_mute_transaction(chat_id: int, user_id: int) -> None:
    lock = _get_mute_lock(chat_id, user_id)
    with lock:
        with db_lock:
            db = _load_yaml_unsafe(DB_PATH, {"users": {}, "muted": {}, "blacklisted_users": {}, "admins": {}})
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

    _cleanup_mute_lock(chat_id, user_id)
    _prune_muted_chats()

def restore_mutes_from_db() -> None:
    logger.info("Restoring mutes from DB...")
    db = load_db()
    muted = db.get("muted", {})
    users_map = db.get("users", {})
    current_time = now_ts()

    restored_count = 0
    removed_expired = 0

    with muted_cache_lock:
        for chat_id_str, members in muted.items():
            try:
                chat_id = int(chat_id_str)
                MUTED_USERS.setdefault(chat_id, {})

                with user_cache_lock:
                    USER_CACHE.setdefault(chat_id, {})
                    for uname, uid in users_map.get(chat_id_str, {}).items():
                        if isinstance(uname, str) and isinstance(uid, int):
                            key = uname.lower().lstrip("@")
                            USER_CACHE[chat_id][key] = {"id": uid, "ts": now_ts()}

                for user_id_str, data in members.items():
                    user_id = int(user_id_str)
                    data = _normalize_mute_data(data)
                    if data["until"] < current_time and data["until"] != PERMANENT_MUTE_TIMESTAMP:
                        removed_expired += 1
                        continue
                    MUTED_USERS[chat_id][user_id] = data
                    restored_count += 1
            except (ValueError, KeyError) as e:
                logger.warning("Failed to restore mute for %s: %s", chat_id_str, e)

    _prune_user_cache()
    _prune_user_cache_chats()
    _prune_muted_chats()
    logger.info(f"Restored {restored_count} mutes. Removed {removed_expired} expired mutes.")

def resolve_user(chat_id: int, username_from_text: str = None, reply_user: dict = None) -> Tuple[Optional[int], Optional[str]]:
    if reply_user:
        return reply_user.get("id"), reply_user.get("username", "")

    if not username_from_text:
        return None, None

    key = username_from_text.lower().lstrip("@")

    with user_cache_lock:
        chat_cache = USER_CACHE.get(chat_id, {})
        if key in chat_cache:
            chat_cache[key]["ts"] = now_ts()
            return chat_cache[key]["id"], key

    db = load_db()
    chat_users = db.get("users", {}).get(str(chat_id), {})

    with user_cache_lock:
        USER_CACHE.setdefault(chat_id, {})
        for k, uid in chat_users.items():
            if isinstance(k, str) and isinstance(uid, int):
                USER_CACHE[chat_id][k.lower().lstrip("@")] = {"id": uid, "ts": now_ts()}
        chat_cache = USER_CACHE.get(chat_id, {})

        if key in chat_cache:
            chat_cache[key]["ts"] = now_ts()
            _prune_user_cache(chat_id)
            return chat_cache[key]["id"], key

        candidates = []
        for k, v in chat_cache.items():
            if k.startswith(key) and len(key) >= 3:
                candidates.append((k, v["id"]))

    _prune_user_cache(chat_id)

    if len(candidates) == 1:
        return candidates[0][1], candidates[0][0]

    return None, None

def handle_mute(chat_id: int, msg_id: int, msg: dict, target_id: int, username: str, duration_seconds: int, duration_raw: str) -> None:
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
    sender_id = msg.get("from", {}).get("id")
    remove_mute_transaction(chat_id, target_id)

    mention = f"@{username}" if username else f"کاربر {target_id}"
    admin_name = get_user_name_from_id(chat_id, sender_id)
    send_message(chat_id, f"🔊 ادمین {admin_name} کاربر {mention} را از سکوت آزاد کرد!", msg_id)
    logger.info(f"Unmute applied: {mention} by {admin_name}")

def enforce_mute(msg: dict) -> None:
    chat_id = safe_get_chat_id(msg)
    user_id = safe_get_from_user(msg).get("id")
    message_id = msg.get("message_id")

    if chat_id is None or user_id is None:
        return

    if msg.get("new_chat_member") or msg.get("new_chat_members"):
        return

    lock = _get_mute_lock(chat_id, user_id)
    with lock:
        with muted_cache_lock:
            mute_data = MUTED_USERS.get(chat_id, {}).get(user_id)

        if not mute_data:
            return

        until = mute_data.get("until", 0)
        current_time = now_ts()

        if current_time >= until and until != PERMANENT_MUTE_TIMESTAMP:
            logger.info(f"Mute expired for {user_id} in {chat_id} during enforce_mute.")
            remove_mute_transaction(chat_id, user_id)
            return

        if message_id is not None:
            try:
                api_call("deleteMessage", {"chat_id": chat_id, "message_id": message_id}, timeout=20)
            except Exception as e:
                logger.error("Delete msg failed: %s", e)

def check_expired_mutes():
    while True:
        try:
            time.sleep(30)
            current_time = now_ts()

            with muted_cache_lock:
                snapshot = [
                    (chat_id, user_id, mute_data.copy())
                    for chat_id, users in MUTED_USERS.items()
                    for user_id, mute_data in users.items()
                ]

            expired_mutes = []
            for chat_id, user_id, mute_data in snapshot:
                until = mute_data.get("until", 0)
                if until != PERMANENT_MUTE_TIMESTAMP and current_time >= until:
                    expired_mutes.append((chat_id, user_id, mute_data))

            for chat_id, user_id, mute_data in expired_mutes:
                try:
                    username = mute_data.get("username", "")
                    mention = f"@{username}" if username else f"کاربر {user_id}"
                    send_message(chat_id, f"⏰ زمان سکوت {mention} به پایان رسید.")
                    remove_mute_transaction(chat_id, user_id)
                    _cleanup_mute_lock(chat_id, user_id)
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
    chat_id = safe_get_chat_id(msg)
    if chat_id is None:
        return

    joined_user = None
    if "new_chat_members" in msg and isinstance(msg["new_chat_members"], list):
        joined_user = msg["new_chat_members"][0] if msg["new_chat_members"] else None
    elif "new_chat_member" in msg:
        member = msg["new_chat_member"]
        if isinstance(member, dict) and "user" in member:
            joined_user = member["user"]
        else:
            joined_user = member

    if not joined_user:
        return

    user_obj = joined_user if isinstance(joined_user, dict) else {}
    user_id = user_obj.get("id")
    username = user_obj.get("username", "")

    if user_id and username:
        uname = username.lower()
        with user_cache_lock:
            USER_CACHE.setdefault(chat_id, {})
            USER_CACHE[chat_id][uname] = {"id": user_id, "ts": now_ts()}
        with user_pending_lock:
            USER_PENDING.setdefault(chat_id, {})
            USER_PENDING[chat_id][uname] = user_id
        _prune_user_cache(chat_id)
        _prune_user_cache_chats()

    if user_id is None:
        return

    if is_blacklisted(user_id):
        try:
            message_id = msg.get("message_id")
            if message_id is not None:
                try:
                    api_call("deleteMessage", {"chat_id": chat_id, "message_id": message_id}, timeout=20)
                except Exception as e:
                    logger.error("Delete join msg failed: %s", e)

            api_call("banChatMember", {"chat_id": chat_id, "user_id": user_id})
            logger.warning(f"Auto-rebanned blacklisted user {user_id} on join.")
        except Exception as e:
            logger.error("Auto-reban fail: %s", e)

##########################
# Command parsing
##########################
def parse_mention_and_time(text: str) -> Tuple[Optional[str], Optional[str]]:
    username = None
    time_str = None
    mentions = re.findall(r'@(\w+)', text)
    if mentions:
        username = mentions[0]
    times = re.findall(r'(\d+\s*(?:m|min|h|d|w))', text, re.IGNORECASE)
    if times:
        time_str = times[-1].strip()
    return username, time_str

def detect_command(text: str) -> Optional[Tuple[str, Optional[str], Optional[str]]]:
    text = (text or "").strip()
    if not text:
        return None
    if text.startswith("/"):
        text = text[1:]
        if not text:
            return None

    for cmd in ALL_COMMANDS:
        if text.lower().startswith(cmd.lower()) if cmd.isascii() else text.startswith(cmd):
            after_cmd_idx = len(cmd)
            if len(text) == after_cmd_idx:
                return (cmd, None, None)
            next_char = text[after_cmd_idx]
            if next_char not in (' ', '\t', '\u200c', '\u200d'):
                continue
            rest = text[after_cmd_idx:].strip()
            if not rest:
                return (cmd, None, None)
            if cmd in info_cmds:
                return (cmd, None, None)
            username, time_str = parse_mention_and_time(rest)
            return (cmd, username, time_str)
    return None

#V3
def _get_admins_from_db(chat_id: int) -> List[str]:
    db = load_db()
    admins = db.get("admins", {}).get(str(chat_id), [])
    return admins if isinstance(admins, list) else []

def handle_message(msg: dict) -> None:
    update_user_cache(msg)
    auto_reban_on_join(msg)
    enforce_mute(msg)

    text = msg.get("text", "")
    result = detect_command(text)
    if not result:
        return

    cmd, username_from_text, time_str_from_text = result
    chat_id = safe_get_chat_id(msg)
    sender_id = safe_get_from_user(msg).get("id")
    msg_id = msg.get("message_id")

    if chat_id is None or sender_id is None or msg_id is None:
        return

    if not is_admin(chat_id, sender_id):
        send_message(chat_id, "⛔ شما ادمین نیستید", msg_id)
        return

    requires_target = cmd not in info_cmds
    target_id = None
    username_for_msg = None

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
                if isinstance(offset, int) and isinstance(length, int):
                    if offset + length <= len(text):
                        mention_text = text[offset:offset+length]
                        username_clean = mention_text.lstrip("@").lower()
                        t_id, u_name = resolve_user(chat_id, username_from_text=username_clean)
                        if t_id:
                            target_id = t_id
                            username_for_msg = u_name
                            break

    if target_id is None and requires_target:
        reply = msg.get("reply_to_message")
        reply_user = reply.get("from", {}) if reply else None
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

    if requires_target:
        if target_id == sender_id:
            send_message(chat_id, "⛔ شما نمی‌توانید این دستور را روی خودتان اجرا کنید.", msg_id)
            return
        if is_admin(chat_id, target_id):
            send_message(chat_id, "⛔ این دستور روی ادمین‌ها قابل اجرا نیست.", msg_id)
            return

    if cmd in mute_cmds:
        if time_str_from_text:
            parsed_seconds = parse_time(time_str_from_text)
            if parsed_seconds is None:
                send_message(chat_id, "⚠️ زمان باید بزرگ‌تر از صفر باشد. مثال: 10min, 2h, 3d, 1w", msg_id)
                return
            duration_seconds = parsed_seconds
            duration_raw = time_str_from_text
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
        #admins = _get_admins_from_db(chat_id)
        #admin_lines = "\n".join([f"- @{a.lstrip('@')}" for a in admins]) if admins else "- (نامشخص)"

        send_message(
            chat_id,
            "======[  پلیس میویی 😼 ]======\n\n"
            "📦 نسخه: 2.2.0 (Stable)  \n"
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
            "- @RealMeow\n"
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
    try:
        msg = update.get("message") or update.get("edited_message")
        if msg:
            handle_message(msg)
    except Exception as e:
        logger.error("Error processing update %s: %s", update.get("update_id"), e, exc_info=True)

def main() -> None:
    logger.info("Starting bot...")
    restore_mutes_from_db()

    mute_checker = threading.Thread(target=check_expired_mutes, daemon=True)
    mute_checker.start()
    logger.info("Mute expiration checker started")

    flush_thread = threading.Thread(target=_flush_user_cache_worker, daemon=True)
    flush_thread.start()
    logger.info("User cache flush worker started")

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
            else:
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
                ╚═╝     ╚═╝╚══════╝ ╚═════╝  ╚══╝╚══╝ ╚═╝╚══════╝     ╚═════╝ ╚═════╝ ╚═╝  version 2.2.0
                ===============================  Production Ready ;) ============================
    """)
    main()