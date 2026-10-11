import os
import json
import html
import base64
import random
from datetime import datetime, timedelta

import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ==================== CONFIG (set these as Vercel Environment Variables) ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
DEVELOPER = os.environ.get("DEVELOPER", "@SeongEra")

# Comma separated numeric Telegram user IDs, e.g. "8932695749,123456789"
PREMIUM_USERS = [
    int(x) for x in os.environ.get("PREMIUM_USERS", "").split(",") if x.strip().isdigit()
]

# Comma separated numeric Telegram user IDs allowed to use /admin.
# Your ID is included by default; add more via the ADMIN_USERS env var.
ADMIN_USERS = [8932695749] + [
    int(x) for x in os.environ.get("ADMIN_USERS", "").split(",") if x.strip().isdigit()
]

UPSTASH_URL = os.environ.get("UPSTASH_REDIS_REST_URL", "").rstrip("/")
UPSTASH_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ==================== YOUR PREMIUM CUSTOM EMOJI SET ====================
# key -> (unicode fallback char, custom_emoji_id)
PREMIUM_EMOJIS = {
    "heart_black": ("🖤", "5258470752759353832"),
    "thumbs_up":   ("👍", "5217785575536337304"),
    "memo":        ("📝", "5258123719401813951"),
    "heart_red":   ("❤️", "5258033752721884482"),
    "check":       ("✅", "6077838869456227983"),
    "desktop":     ("🖥", "5787638984511328327"),
    "envelope":    ("✉️", "5282927670932287621"),
    "card_index":  ("🗂", "5292165466981147510"),
    "folder":      ("📁", "5998867331554481689"),
    "floppy":      ("💾", "5364222176255813371"),
    # --- newer batch ---
    "check_a":        ("✔️", "6275845846873412055"),
    "star_a":         ("⭐️", "6276090329296802466"),
    "star_b":         ("⭐️", "6275893435111053023"),
    "check_b":        ("✅", "6276314883071939299"),
    "star_c":         ("⭐️", "6275806917289841253"),
    "star_d":         ("⭐️", "6275929942333068649"),
    "star_e":         ("⭐️", "6275971302868128701"),
    "star_f":         ("⭐️", "6273559403853517250"),
    "check_c":        ("✅", "6276009124350138166"),
    "check_d":        ("✅", "6276254916738552451"),
    "check_e":        ("✅", "6276238759071586100"),
    "check_f":        ("✅", "6276164035230569281"),
    "check_g":        ("✅", "6276173703201952620"),
    "check_h":        ("✅", "6339148111423739788"),
    "cross_a":        ("❌", "6337074299349768690"),
    "check_i":        ("✅", "6276126643245289780"),
    "check_j":        ("✅", "6276090299232031662"),
    "check_k":        ("✅", "6276190011192775282"),
    "check_l":        ("✅", "6276133850200413718"),
    "check_m":        ("✅", "6276265190300325185"),
    "pink_heart":     ("🩷", "6336888383100426308"),
    "check_n":        ("✅", "6338853910458930994"),
    "cross_b":        ("❌", "6337074578522642080"),
    "cross_c":        ("❌", "6275999280285094803"),
    "cross_d":        ("❌", "6273865673676428425"),
    "cross_e":        ("❌", "6276115154207774402"),
    "cross_f":        ("❌", "6276025694333966034"),
    "cross_g":        ("❌", "6276272470269891500"),
    "warning_a":      ("⚠️", "6337081377455872512"),
    "warning_b":      ("⚠️", "6275791747465352530"),
    "warning_c":      ("⚠️", "6276132901012640832"),
    "chart":          ("📊", "6336963167070984229"),
    "businessman":    ("👨‍💼", "6275873639606785095"),
    "money_bag":      ("💰", "6338884189978367024"),
    "money_mouth_a":  ("🤑", "6275881112849880302"),
    "money_wings_a":  ("💸", "6276028580551987901"),
    "money_wings_b":  ("💸", "6337027711839508720"),
    "starstruck":     ("🤩", "6336565697912510423"),
    "dollar":         ("💵", "6336788658254780641"),
    "money_mouth_b":  ("🤑", "6339054416712177543"),
    "heart_a":        ("❤️", "6276172887158166707"),
    "heart_b":        ("❤️", "6276220934957307252"),
    "heart_c":        ("❤", "6275902922693808220"),
    "sparkle_heart":  ("💖", "6275840074437366659"),
    "heart_fire":     ("❤️‍🔥", "6276189409897353982"),
    "heart_d":        ("❤️", "6276135473698051177"),
    "devil":          ("😈", "6336780965968353744"),
    "zap":            ("⚡️", "6336932114457435936"),
    "angry":          ("😡", "6336770640866973087"),
    "cat_a":          ("🐱", "6339091748567915249"),
    "gift_a":         ("🎁", "6338851110140254471"),
    "bat_a":          ("🦇", "6336723164298483006"),
    "bat_b":          ("🦇", "6339164578328352187"),
    "bat_c":          ("🦇", "6336900838505583774"),
    "bat_d":          ("🦇", "6336641766078290717"),
    "bat_e":          ("🦇", "6336603867286870404"),
    "cat_b":          ("😺", "6339215031309178286"),
    "cat_c":          ("😺", "6336818912004412825"),
    "cat_d":          ("😺", "6336877229070360017"),
    "rocket_a":       ("🚀", "6276279784599196845"),
    "rocket_b":       ("🚀", "6276311855119994929"),
    "check_o":        ("✔️", "6276282773896434467"),
    "rocket_c":       ("🚀", "6276327209628078918"),
    "cart":           ("🛒", "6275872969591887000"),
    "gift_b":         ("🎁", "6276134137963222688"),
    "gift_c":         ("🎁", "6276192588173154244"),
    "check_p":        ("✅", "6276085720796893665"),
    "link_icon":      ("🔗", "6275878213746955453"),
    "star_g":         ("⭐", "6275781881925473305"),
    "star_h":         ("⭐", "6275815429915022612"),
    "star_i":         ("⭐", "6276191574560871499"),
    "postal_horn":    ("📯", "6276242985319403942"),
    "check_q":        ("✔️", "6276239815633540328"),
    "radio_a":        ("🔘", "6276241469195949589"),
    "radio_b":        ("🔘", "6275811074818184964"),
    "radio_c":        ("🔘", "6276005757095776702"),
    "star_j":         ("⭐", "6276302328882533160"),
    "party":          ("🎉", "6276010683423265379"),
    "record_btn":     ("⏺", "6276258146553959491"),
    "arrow_right":    ("➡️", "6336820492552377728"),
    "question":       ("❓", "6336612732099368492"),
}

DIVIDER = "─" * 22

# ==================== REQUIRED CHANNEL / CHAT (force-join) ====================
# Bot must be an admin (or at least a member) of both for getChatMember to work.
REQUIRED_CHATS = [
    {
        "chat_id": -1004485651677,
        "title": "GpsirEra Community",
        "url": "https://t.me/Black_hats_ops",
        "request_based": False,
    },
    {
        "chat_id": -1003927824087,
        "title": "GpsirEra Community | Chat",
        "url": "https://t.me/+NPI9QsQiETBjNjI1",
        "request_based": True,
    },
    {
        "chat_id": -1004297567227,
        "title": "GpsirEra Community | Channel",
        "url": "https://t.me/+JnxnXtxpsmg2MjBl",
        "request_based": True,
    },
]

# ==================== REDIS (Upstash REST) ====================
def _redis_headers():
    return {"Authorization": f"Bearer {UPSTASH_TOKEN}"}


def redis_get(key):
    if not UPSTASH_URL:
        return None
    r = requests.get(f"{UPSTASH_URL}/get/{key}", headers=_redis_headers(), timeout=10)
    result = r.json().get("result")
    return result


def redis_set(key, value):
    if not UPSTASH_URL:
        return
    requests.post(f"{UPSTASH_URL}/set/{key}", headers=_redis_headers(), data=value, timeout=10)


def redis_del(key):
    if not UPSTASH_URL:
        return
    requests.get(f"{UPSTASH_URL}/del/{key}", headers=_redis_headers(), timeout=10)


def get_json(key, default):
    raw = redis_get(key)
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def set_json(key, value):
    redis_set(key, json.dumps(value))


def is_duplicate_update(update_id):
    """Telegram retries a webhook delivery if the function doesn't respond
    in time (e.g. a slow /broadcast loop on Vercel's execution limit).
    Without this guard, a single retry re-runs the ENTIRE handler again -
    including re-sending a full broadcast to every user. This remembers
    the last ~500 update_ids so a retried delivery is a safe no-op."""
    if update_id is None:
        return False
    seen = get_json("processed_update_ids", [])
    if update_id in seen:
        return True
    seen.append(update_id)
    if len(seen) > 500:
        seen = seen[-500:]
    set_json("processed_update_ids", seen)
    return False


# ==================== HELPERS ====================
def is_premium(user_id):
    return int(user_id) in PREMIUM_USERS


def is_admin(user_id):
    return int(user_id) in ADMIN_USERS


def record_user_activity(user, is_upload=False):
    """Tracks every user who has ever touched the bot (even ones blocked
    by the force-join gate), for the /admin panel. Stored under a single
    key so it never collides with existing files:*/batches:* data."""
    uid = str(user.get("id"))
    all_users = get_json("all_users", {})
    now = datetime.now().isoformat()
    entry = all_users.get(uid, {
        "id": uid,
        "username": None,
        "first_name": None,
        "first_seen": now,
        "message_count": 0,
        "upload_count": 0,
    })
    entry["username"] = user.get("username")
    entry["first_name"] = user.get("first_name")
    entry["last_seen"] = now
    entry["message_count"] = entry.get("message_count", 0) + 1
    if is_upload:
        entry["upload_count"] = entry.get("upload_count", 0) + 1
    all_users[uid] = entry
    set_json("all_users", all_users)


def generate_id():
    return base64.urlsafe_b64encode(os.urandom(6)).decode("utf-8").rstrip("=")


def format_size(size):
    size = size or 0
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def utf16_len(s):
    """Telegram counts entity offset/length in UTF-16 code units, not
    Python characters. Emoji outside the Basic Multilingual Plane
    (like 👍 🖤 📝) are surrogate pairs = 2 units, not 1. Getting this
    wrong is what causes 'Entity beginning at utf-16 offset...' crashes."""
    return len(s.encode("utf-16-le")) // 2


def compose(*segments):
    """
    Build a (text, entities) pair from segments. Because a message using
    custom_emoji entities can't ALSO use parse_mode (Telegram rejects the
    combination), any bold/code formatting here must be its own entity too
    -- plain "<b>" tags would just show up as literal text.

    Each segment is either:
      - a plain string (sent as-is, no markup interpretation happens)
      - ("bold", text) to bold that text
      - ("code", text) for monospace
      - (emoji_key,) to insert a premium custom emoji from PREMIUM_EMOJIS
    """
    full_text = ""
    entities = []
    for seg in segments:
        if isinstance(seg, tuple):
            if seg[0] in ("bold", "code"):
                kind, inner_text = seg
                offset = utf16_len(full_text)
                length = utf16_len(inner_text)
                entities.append({"type": kind, "offset": offset, "length": length})
                full_text += inner_text
            else:
                emoji_key = seg[0]
                char, custom_id = PREMIUM_EMOJIS[emoji_key]
                offset = utf16_len(full_text)
                length = utf16_len(char)
                entities.append(
                    {
                        "type": "custom_emoji",
                        "offset": offset,
                        "length": length,
                        "custom_emoji_id": custom_id,
                    }
                )
                full_text += char
        else:
            full_text += seg
    return full_text, entities


def esc(s):
    """Escape user/file-controlled text before dropping it into an HTML
    parse_mode message. Filenames or IDs containing <, >, or & would
    otherwise break the message the same way stray underscores broke
    Markdown mode."""
    return html.escape(str(s), quote=False)


def tg(method, payload, timeout=15):
    r = requests.post(f"{TELEGRAM_API}/{method}", json=payload, timeout=timeout)
    return r.json()


def send_message(chat_id, text, entities=None, reply_markup=None, parse_mode="HTML", timeout=15):
    payload = {"chat_id": chat_id, "text": text}
    if entities:
        payload["entities"] = entities
        payload.pop("parse_mode", None)  # entities and parse_mode are mutually exclusive
    elif parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return tg("sendMessage", payload, timeout=timeout)


def edit_message(chat_id, message_id, text, entities=None, reply_markup=None, parse_mode="HTML"):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if entities:
        payload["entities"] = entities
        payload.pop("parse_mode", None)
    elif parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return tg("editMessageText", payload)


def answer_callback(callback_id, text=None, show_alert=False):
    payload = {"callback_query_id": callback_id}
    if text:
        payload["text"] = text
        payload["show_alert"] = show_alert
    return tg("answerCallbackQuery", payload)


def send_document(chat_id, file_id, caption=None):
    payload = {"chat_id": chat_id, "document": file_id}
    if caption:
        payload["caption"] = caption
    return tg("sendDocument", payload)


def send_photo_file(chat_id, file_id, caption=None):
    payload = {"chat_id": chat_id, "photo": file_id}
    if caption:
        payload["caption"] = caption
    return tg("sendPhoto", payload)


def send_video_file(chat_id, file_id, caption=None):
    payload = {"chat_id": chat_id, "video": file_id}
    if caption:
        payload["caption"] = caption
    return tg("sendVideo", payload)


def send_audio_file(chat_id, file_id, caption=None):
    payload = {"chat_id": chat_id, "audio": file_id}
    if caption:
        payload["caption"] = caption
    return tg("sendAudio", payload)


def send_voice_file(chat_id, file_id, caption=None):
    payload = {"chat_id": chat_id, "voice": file_id}
    if caption:
        payload["caption"] = caption
    return tg("sendVoice", payload)


def deliver_file(chat_id, entry):
    """Sends a stored file back to a user via the SAME Bot API method it
    came in as. The old code always used sendDocument, which silently
    fails (or mis-renders) for a photo's file_id - photo/video/audio/voice
    file_id values are scoped to their own type on Telegram's servers and
    sendDocument expects a document-type reference. This is what broke
    photo links."""
    file_type = entry.get("file_type", "document")
    caption = f"📁 {entry['file_name']}\n💾 {format_size(entry['file_size'])}\n"
    if entry.get("caption"):
        caption += f"📝 {entry['caption']}\n"
    caption += f"Powered by {DEVELOPER}"

    if file_type == "photo":
        return send_photo_file(chat_id, entry["file_id"], caption=caption)
    if file_type == "video":
        return send_video_file(chat_id, entry["file_id"], caption=caption)
    if file_type == "audio":
        return send_audio_file(chat_id, entry["file_id"], caption=caption)
    if file_type == "voice":
        return send_voice_file(chat_id, entry["file_id"], caption=caption)
    return send_document(chat_id, entry["file_id"], caption=caption)


def get_me_username():
    cached = redis_get("bot_username")
    if cached:
        return cached
    data = tg("getMe", {})
    username = data.get("result", {}).get("username", "")
    if username:
        redis_set("bot_username", username)
    return username


def find_file_by_uid(uid):
    """Files are stored per-owner as files:{owner_id}. We keep a global
    index files_index -> {uid: owner_id} for O(1) lookups on deep links."""
    index = get_json("files_index", {})
    owner = index.get(uid)
    if not owner:
        return None, None
    files = get_json(f"files:{owner}", [])
    for f in files:
        if f["unique_id"] == uid:
            return owner, f
    return None, None


def is_actual_member(chat_id, user_id):
    try:
        r = tg("getChatMember", {"chat_id": chat_id, "user_id": user_id})
        status = r.get("result", {}).get("status")
        return status in ("member", "administrator", "creator")
    except Exception:
        return False


def has_pending_request(chat_id, user_id):
    """True if we've recorded a chat_join_request from this user for this
    chat, even if you (the admin) haven't approved it yet."""
    requested = get_json(f"join_requests:{chat_id}", [])
    return user_id in requested


def missing_joins(user_id):
    """Returns the list of required chats the user has NOT satisfied yet.
    Empty list = gate passes. For request_based chats, having SENT a join
    request is enough — approval isn't required."""
    missing = []
    for ch in REQUIRED_CHATS:
        if ch.get("request_based"):
            if has_pending_request(ch["chat_id"], user_id) or is_actual_member(ch["chat_id"], user_id):
                continue
        else:
            if is_actual_member(ch["chat_id"], user_id):
                continue
        missing.append(ch)
    return missing


def send_join_prompt(chat_id, missing):
    rows = [[{"text": f"➕ Join {esc(ch['title'])}", "url": ch["url"]}] for ch in missing]
    rows.append([btn("✅ I've Joined", "checkjoin")])
    lines = "\n".join(f"• {esc(c['title'])}" for c in missing)
    text = (
        "🔒 <b>Access Locked</b>\n\n"
        "Please join our official channel and community chat to use this bot:\n\n"
        f"{lines}\n\n"
        "After joining, tap the button below."
    )
    send_message(chat_id, text, reply_markup=kb(rows))


def find_batch_by_id(batch_id):
    index = get_json("batches_index", {})
    owner = index.get(batch_id)
    if not owner:
        return None, None
    batches = get_json(f"batches:{owner}", [])
    for b in batches:
        if b["batch_id"] == batch_id:
            return owner, b
    return None, None


# ==================== LINK EXPIRY & SUPER PRIVATE (VIEW-LIMITED) LINKS ====================
def parse_duration(s):
    """Parses '30m', '2h', '1d' into a timedelta. Returns None if invalid."""
    s = s.strip().lower()
    if len(s) < 2:
        return None
    unit = s[-1]
    num_part = s[:-1]
    if not num_part.replace(".", "", 1).isdigit():
        return None
    num = float(num_part)
    if unit == "m":
        return timedelta(minutes=num)
    if unit == "h":
        return timedelta(hours=num)
    if unit == "d":
        return timedelta(days=num)
    return None


def find_link_by_id(link_id):
    """A link_id might be a file's unique_id or a batch_id - admin commands
    accept either. Returns (kind, owner, entry) where kind is 'file' or
    'batch', or (None, None, None) if nothing matches."""
    owner, f = find_file_by_uid(link_id)
    if f:
        return "file", owner, f
    owner, b = find_batch_by_id(link_id)
    if b:
        return "batch", owner, b
    return None, None, None


def update_file_entry(owner, uid, updates):
    files = get_json(f"files:{owner}", [])
    for f in files:
        if f["unique_id"] == uid:
            f.update(updates)
            break
    set_json(f"files:{owner}", files)


def update_batch_entry(owner, batch_id, updates):
    batches = get_json(f"batches:{owner}", [])
    for b in batches:
        if b["batch_id"] == batch_id:
            b.update(updates)
            break
    set_json(f"batches:{owner}", batches)


def check_and_record_access(kind, owner, entry, viewer_id):
    """Checks expiry + view-limit ('Super Private Link') for a file or
    batch. If access is allowed, records this view (increments the
    counter, logs the viewer for the admin) and returns (True, None).
    If blocked, returns (False, <message to show the viewer>)."""
    expires_at = entry.get("expires_at")
    if expires_at:
        try:
            if datetime.now() > datetime.fromisoformat(expires_at):
                return False, "❌ This link has expired."
        except Exception:
            pass

    view_limit = entry.get("view_limit")
    if view_limit:
        view_count = entry.get("view_count", 0)
        if view_count >= view_limit:
            return False, (
                "🔒 This is a Super Private Link and it has expired — "
                f"all {view_limit} allowed view(s) have already been used."
            )

    viewers = entry.get("viewers", [])
    viewers.append({"user_id": viewer_id, "viewed_at": datetime.now().isoformat()})
    updates = {"view_count": entry.get("view_count", 0) + 1, "viewers": viewers}

    link_id = entry.get("unique_id") if kind == "file" else entry.get("batch_id")
    if kind == "file":
        update_file_entry(owner, link_id, updates)
    else:
        update_batch_entry(owner, link_id, updates)

    return True, None


# ==================== KEYBOARDS ====================
def kb(rows):
    return {"inline_keyboard": rows}


def btn(text, callback_data):
    return {"text": text, "callback_data": callback_data}


# ==================== COMMAND HANDLERS ====================
def handle_start(chat_id, user_id, args):
    if args:
        arg = args[0]

        if arg.startswith("batch_"):
            batch_id = arg[6:]
            owner, batch = find_batch_by_id(batch_id)
            if not batch:
                send_message(chat_id, "❌ Batch not found or expired.")
                return
            ok, err = check_and_record_access("batch", owner, batch, user_id)
            if not ok:
                send_message(chat_id, err)
                return
            send_message(chat_id, f"📦 Sending {len(batch['files'])} files...")
            for file_uid in batch["files"]:
                _, f = find_file_by_uid(file_uid)
                if f:
                    if f.get("type") == "text":
                        send_message(chat_id, f"📝 {f.get('file_name', 'Note')}\n\n{f.get('content', '')}")
                        continue
                    deliver_file(chat_id, f)
            return

        owner, f = find_file_by_uid(arg)
        if f:
            ok, err = check_and_record_access("file", owner, f, user_id)
            if not ok:
                send_message(chat_id, err)
                return
            if f.get("type") == "text":
                text_out = f"📝 {f.get('content', '')}\n\nPowered by {DEVELOPER}"
                send_message(chat_id, text_out)
                return
            deliver_file(chat_id, f)
        else:
            send_message(chat_id, "❌ File not found.")
        return

    admin_line = "/admin – admin panel\n" if is_admin(user_id) else ""

    text, entities = compose(
        ("thumbs_up",), " ", ("bold", "GpsirEra File Vault"), "\n",
        f"{DIVIDER}\n\n",
        "All features below are free for everyone.\n\n",
        ("memo",), " Forward any file → get an instant link\n",
        ("check",), " Use /batch to build a shareable multi-file batch\n\n",
        ("bold", "Commands"), "\n",
        "/list – your files\n",
        "/link <id> – get a link\n",
        "/delete <id> – delete a file\n",
        "/clear – wipe all your files\n",
        "/batch – build a batch\n",
        "/mybatch – your saved batches\n",
        "/stats – bot statistics\n",
        admin_line,
        f"{DIVIDER}\n",
        ("heart_black",), f" Developer: {DEVELOPER}",
    )
    markup = kb(
        [
            [btn("📋 My Files", "list"), btn("📦 Build Batch", "batch")],
            [btn("🗑 Delete All Files", "clearall_ask")],
        ]
    )
    send_message(chat_id, text, entities=entities, reply_markup=markup)


def handle_forwarded_file(chat_id, user_id, message):
    uid = str(user_id)

    file_obj = None
    fname = "file"
    file_type = "document"
    if "document" in message:
        file_obj = message["document"]
        fname = file_obj.get("file_name", "document")
        file_type = "document"
    elif "video" in message:
        file_obj = message["video"]
        fname = file_obj.get("file_name", "video.mp4")
        file_type = "video"
    elif "audio" in message:
        file_obj = message["audio"]
        fname = file_obj.get("file_name", "audio.mp3")
        file_type = "audio"
    elif "voice" in message:
        file_obj = message["voice"]
        fname = f"voice_{datetime.now().strftime('%H%M%S')}.ogg"
        file_type = "voice"
    elif "photo" in message:
        file_obj = message["photo"][-1]
        fname = f"photo_{datetime.now().strftime('%H%M%S')}.jpg"
        file_type = "photo"
    else:
        send_message(chat_id, "❌ Unsupported file type!")
        return

    files = get_json(f"files:{uid}", [])
    file_uid = generate_id()
    caption = message.get("caption", "") or ""
    entry = {
        "unique_id": file_uid,
        "file_id": file_obj["file_id"],
        "file_type": file_type,
        "file_name": fname,
        "file_size": file_obj.get("file_size", 0),
        "caption": caption,
        "timestamp": datetime.now().isoformat(),
    }
    files.append(entry)
    set_json(f"files:{uid}", files)

    index = get_json("files_index", {})
    index[file_uid] = uid
    set_json("files_index", index)

    bot_username = get_me_username()
    link = f"https://t.me/{bot_username}?start={file_uid}"

    text, entities = compose(
        ("check",), " ", ("bold", "File Saved"), "\n",
        f"{DIVIDER}\n",
        f"📁 {fname}\n",
        f"💾 {format_size(entry['file_size'])}\n",
        (f"📝 {caption}\n" if caption else ""),
        f"🔗 {link}\n",
    )
    markup = kb(
        [
            [btn("📋 Copy Link", f"copy_{file_uid}")],
            [btn("📦 Add to Batch", f"addbatch_{file_uid}")],
            [btn("⏰ Set Expiry", f"fileexp_{file_uid}"), btn("🔒 Set View Limit", f"fileviews_{file_uid}")],
        ]
    )
    send_message(chat_id, text, entities=entities, reply_markup=markup)


FILES_PER_PAGE = 6


def render_file_list(chat_id, user_id, page=0, edit=None):
    uid = str(user_id)
    files = get_json(f"files:{uid}", [])
    if not files:
        text = "📭 No files found. Forward a file to get started!"
        if edit:
            edit_message(chat_id, edit, text)
        else:
            send_message(chat_id, text)
        return

    total_pages = max(1, (len(files) + FILES_PER_PAGE - 1) // FILES_PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    start = page * FILES_PER_PAGE
    chunk = files[start:start + FILES_PER_PAGE]

    rows = []
    for f in chunk:
        badge = ""
        if f.get("expires_at"):
            badge += "⏰"
        if f.get("view_limit"):
            badge += "🔒"
        label = f"{badge} {f['file_name'][:35]}".strip()
        rows.append([btn(label, f"filemenu_{f['unique_id']}")])

    nav_row = []
    if page > 0:
        nav_row.append(btn("⬅️ Prev", f"listpage_{page - 1}"))
    nav_row.append(btn(f"📄 {page + 1}/{total_pages}", "noop"))
    if page < total_pages - 1:
        nav_row.append(btn("Next ➡️", f"listpage_{page + 1}"))
    rows.append(nav_row)
    rows.append([btn("🗑 Delete All Files", "clearall_ask")])

    text = (
        f"📁 <b>Your Files</b> ({len(files)} total)\n\n"
        "Tap a file to view its link, set an expiry, limit views, or delete it.\n"
        "⏰ = has expiry · 🔒 = view-limited"
    )
    markup = kb(rows)
    if edit:
        edit_message(chat_id, edit, text, reply_markup=markup)
    else:
        send_message(chat_id, text, reply_markup=markup)


def render_file_detail(chat_id, user_id, file_uid, edit=None):
    owner, f = find_file_by_uid(file_uid)
    if not f:
        msg = "❌ File not found - it may have been deleted."
        (edit_message(chat_id, edit, msg) if edit else send_message(chat_id, msg))
        return

    bot_username = get_me_username()
    link = f"https://t.me/{bot_username}?start={file_uid}"
    can_manage = (str(user_id) == owner) or is_admin(user_id)

    extra_lines = ""
    if f.get("caption"):
        extra_lines += f"📝 {esc(f['caption'])}\n"
    if f.get("expires_at"):
        nice = f["expires_at"][:16].replace("T", " ")
        extra_lines += f"⏰ Expires: {nice}\n"
    if f.get("view_limit"):
        extra_lines += f"🔒 Views used: {f.get('view_count', 0)}/{f['view_limit']}\n"

    text = (
        f"📁 <b>{esc(f['file_name'])}</b>\n"
        f"💾 {format_size(f.get('file_size', 0))}\n"
        f"{extra_lines}"
        f"🔗 {esc(link)}"
    )

    rows = [[btn("📋 Copy Link", f"copy_{file_uid}")]]
    if can_manage:
        rows.append([btn("📦 Add to Batch", f"addbatch_{file_uid}")])
        rows.append([btn("⏰ Set Expiry", f"fileexp_{file_uid}"), btn("🔒 Set View Limit", f"fileviews_{file_uid}")])
        rows.append([btn("🗑 Delete This File", f"filedel_{file_uid}")])
    rows.append([btn("⬅️ Back to List", "list")])

    markup = kb(rows)
    if edit:
        edit_message(chat_id, edit, text, reply_markup=markup)
    else:
        send_message(chat_id, text, reply_markup=markup)


def render_expiry_menu(chat_id, message_id, file_uid):
    rows = [
        [btn("⏱ 30 min", f"setexp_{file_uid}_30m"), btn("🕑 2 hours", f"setexp_{file_uid}_2h")],
        [btn("📅 1 day", f"setexp_{file_uid}_1d"), btn("📅 7 days", f"setexp_{file_uid}_7d")],
        [btn("❌ No Expiry", f"setexp_{file_uid}_remove")],
        [btn("⬅️ Back", f"filemenu_{file_uid}")],
    ]
    edit_message(chat_id, message_id, "⏰ Choose an expiry for this link:", reply_markup=kb(rows))


def render_views_menu(chat_id, message_id, file_uid):
    rows = [
        [btn("👁 1 view", f"setviews_{file_uid}_1"), btn("👁 5 views", f"setviews_{file_uid}_5")],
        [btn("👁 10 views", f"setviews_{file_uid}_10"), btn("👁 25 views", f"setviews_{file_uid}_25")],
        [btn("❌ No Limit", f"setviews_{file_uid}_remove")],
        [btn("⬅️ Back", f"filemenu_{file_uid}")],
    ]
    edit_message(
        chat_id, message_id,
        "🔒 Make this a Super Private Link - choose the max number of views:",
        reply_markup=kb(rows),
    )


def handle_link(chat_id, user_id, args):
    if not args:
        send_message(chat_id, "❌ Usage: /link <file_id>")
        return
    uid = str(user_id)
    files = get_json(f"files:{uid}", [])
    for f in files:
        if f["unique_id"] == args[0]:
            bot_username = get_me_username()
            link = f"https://t.me/{bot_username}?start={f['unique_id']}"
            send_message(chat_id, f"🔗 {f['file_name']}\n{link}")
            return
    send_message(chat_id, "❌ File not found.")


def handle_delete(chat_id, user_id, args):
    if not args:
        send_message(chat_id, "❌ Usage: /delete <file_id>")
        return
    uid = str(user_id)
    files = get_json(f"files:{uid}", [])
    for idx, f in enumerate(files):
        if f["unique_id"] == args[0]:
            name = f["file_name"]
            del files[idx]
            set_json(f"files:{uid}", files)
            index = get_json("files_index", {})
            index.pop(args[0], None)
            set_json("files_index", index)
            send_message(chat_id, f"✅ Deleted: {name}")
            return
    send_message(chat_id, "❌ File not found.")


def handle_clear(chat_id, user_id):
    uid = str(user_id)
    files = get_json(f"files:{uid}", [])
    if not files:
        send_message(chat_id, "📭 No files to delete.")
        return
    count = len(files)
    index = get_json("files_index", {})
    for f in files:
        index.pop(f["unique_id"], None)
    set_json("files_index", index)
    redis_del(f"files:{uid}")
    send_message(chat_id, f"✅ Deleted all {count} files.")


def render_batch_picker(chat_id, user_id, edit=None):
    uid = str(user_id)
    files = get_json(f"files:{uid}", [])
    selected = get_json(f"pick:{uid}", [])
    target = redis_get(f"batch_target:{uid}") or "new"

    if target == "new":
        batches = get_json(f"batches:{uid}", [])
        title = f"Batch {len(batches) + 1} (new)"
        finish_label = "📦 Create Batch"
    else:
        _, existing = find_batch_by_id(target)
        title = existing["name"] if existing and existing.get("name") else target
        finish_label = "💾 Update Batch"

    rows = []
    for f in files:
        mark = "✅" if f["unique_id"] in selected else "⬜"
        label = f"{mark} {f['file_name'][:30]}"
        rows.append([btn(label, f"pick_{f['unique_id']}")])
    rows.append([btn("☑️ Select All", "batchselectall"), btn("⬜ Clear Selection", "batchclearsel")])
    rows.append([btn(finish_label, "finishbatch"), btn("❌ Cancel", "cancelbatch")])

    text = (
        f"📦 <b>Building: {esc(title)}</b>\n\n"
        f"Selected: {len(selected)}/{len(files)}\n"
        f"Tap files to select/deselect, then press {esc(finish_label)}."
    )
    markup = kb(rows)

    if edit:
        edit_message(chat_id, edit, text, reply_markup=markup)
    else:
        send_message(chat_id, text, reply_markup=markup)


def render_batch_menu(chat_id, user_id, edit=None):
    """Entry point for /batch: choose to start a brand new named batch
    (Batch 1, Batch 2, Batch 3...) or keep adding files into one that
    already exists."""
    uid = str(user_id)
    files = get_json(f"files:{uid}", [])
    if not files:
        msg = "📭 No files to batch. Forward some files first."
        if edit:
            edit_message(chat_id, edit, msg)
        else:
            send_message(chat_id, msg)
        return

    batches = get_json(f"batches:{uid}", [])
    rows = [[btn("🆕 Create New Batch", "newbatch")]]
    for b in batches:
        name = b.get("name") or b["batch_id"]
        rows.append([btn(f"➕ Add files to: {name}", f"editbatch_{b['batch_id']}")])

    text = (
        "📦 <b>Batches</b>\n\n"
        f"You have {len(batches)} existing batch(es). Create a brand new one, "
        "or keep adding files into an existing one below."
    )
    markup = kb(rows)
    if edit:
        edit_message(chat_id, edit, text, reply_markup=markup)
    else:
        send_message(chat_id, text, reply_markup=markup)


def handle_batch_command(chat_id, user_id):
    render_batch_menu(chat_id, user_id)


def handle_mybatch(chat_id, user_id):
    uid = str(user_id)
    batches = get_json(f"batches:{uid}", [])
    if not batches:
        send_message(chat_id, "📭 No batches yet. Use /batch to create one.")
        return
    bot_username = get_me_username()

    header, entities = compose(("gift_a",), " ", ("bold", "Your Batches"))
    send_message(chat_id, header, entities=entities)

    for b in batches:
        link = f"https://t.me/{bot_username}?start=batch_{b['batch_id']}"
        name = esc(b.get("name") or b["batch_id"])
        text = (
            f"🗂 <b>{name}</b>\n"
            f"📁 {len(b['files'])} files\n"
            f"🔗 {esc(link)}"
        )
        markup = kb(
            [
                [btn("➕ Add More Files", f"editbatch_{b['batch_id']}")],
                [btn("🗑 Delete This Batch", f"delbatch_{b['batch_id']}")],
            ]
        )
        send_message(chat_id, text, reply_markup=markup)


def handle_admin(chat_id, user_id):
    if not is_admin(user_id):
        send_message(chat_id, "❌ Admins only.")
        return

    all_users = get_json("all_users", {})
    files_index = get_json("files_index", {})
    batches_index = get_json("batches_index", {})

    total_seen = len(all_users)
    total_files = len(files_index)
    total_batches = len(batches_index)
    uploaders = [u for u in all_users.values() if u.get("upload_count", 0) > 0]
    premium_seen = [u for u in all_users.values() if is_premium(u["id"])]

    header, entities = compose(("chart",), " ", ("bold", "Admin Panel"))
    summary = (
        f"{header}\n{DIVIDER}\n\n"
        f"👥 Total people who opened the bot: {total_seen}\n"
        f"📤 People who uploaded at least 1 file: {len(uploaders)}\n"
        f"👑 Premium users seen: {len(premium_seen)}\n"
        f"📁 Total files stored: {total_files}\n"
        f"📦 Total batches: {total_batches}\n"
    )
    send_message(chat_id, summary, entities=entities)

    # Most recently active users first
    recent = sorted(all_users.values(), key=lambda u: u.get("last_seen", ""), reverse=True)[:25]
    if recent:
        text = "🖥 <b>Recent Users</b> (latest 25)\n\n"
        admin_rows = []
        for u in recent:
            uname = f"@{esc(u['username'])}" if u.get("username") else "(no username)"
            name = esc(u.get("first_name") or "")
            line = (
                f"• <code>{u['id']}</code> {uname} {name}\n"
                f"  msgs: {u.get('message_count', 0)} | uploads: {u.get('upload_count', 0)} | "
                f"last seen: {u.get('last_seen', '?')[:16]}\n\n"
            )
            if len(text) + len(line) <= 3800:
                text += line
                admin_rows.append([btn(f"👁 View files of {u['id']}", f"adminview_{u['id']}")])
        send_message(chat_id, text, reply_markup=kb(admin_rows) if admin_rows else None)

    send_message(
        chat_id,
        "ℹ️ Use <code>/adminfiles &lt;user_id&gt;</code> to view any user's files & links directly.\n"
        "Use <code>/broadcast &lt;message&gt;</code> to message every user who has opened the bot.\n\n"
        "🔗 <b>Link controls</b> (use a file's or batch's ID, from /adminfiles or /adminbatches):\n"
        "<code>/setexpiry &lt;id&gt; &lt;30m|2h|1d&gt;</code> — expire a link after a time\n"
        "<code>/removeexpiry &lt;id&gt;</code> — clear its expiry\n"
        "<code>/setviews &lt;id&gt; &lt;count&gt;</code> — make it a Super Private Link (max views)\n"
        "<code>/removeviews &lt;id&gt;</code> — remove the view limit\n"
        "<code>/linkviewers &lt;id&gt;</code> — see who has opened a link\n"
        "<code>/newtext &lt;text&gt;</code> — create a shareable link from plain text",
    )


def handle_stats(chat_id):
    index = get_json("files_index", {})
    total_files = len(index)
    owners = set(index.values())
    total_users = len(owners)
    send_message(
        chat_id,
        f"📊 <b>Bot Statistics</b>\n\n"
        f"👥 Users with files stored: {total_users}\n"
        f"📁 Files: {total_files}\n"
        f"👨‍💻 Developer: {esc(DEVELOPER)}",
    )


def handle_admin_files(chat_id, admin_id, target_uid):
    if not is_admin(admin_id):
        send_message(chat_id, "❌ Admins only.")
        return
    target_uid = str(target_uid)
    files = get_json(f"files:{target_uid}", [])
    if not files:
        send_message(chat_id, f"📭 User <code>{esc(target_uid)}</code> has no files stored.")
        return
    bot_username = get_me_username()
    text = f"📁 <b>Files uploaded by</b> <code>{esc(target_uid)}</code> ({len(files)})\n\n"
    for idx, f in enumerate(files):
        line = (
            f"{idx + 1}. {esc(f['file_name'])}\n"
            f"   💾 {format_size(f['file_size'])}\n"
            f"   🔗 https://t.me/{bot_username}?start={f['unique_id']}\n\n"
        )
        if len(text) + len(line) > 3800:
            text += "... (truncated)"
            break
        text += line
    send_message(chat_id, text)


def handle_admin_batches(chat_id, admin_id, target_uid):
    if not is_admin(admin_id):
        send_message(chat_id, "❌ Admins only.")
        return
    target_uid = str(target_uid)
    batches = get_json(f"batches:{target_uid}", [])
    if not batches:
        send_message(chat_id, f"📭 User <code>{esc(target_uid)}</code> has no batches.")
        return
    bot_username = get_me_username()
    text = f"📦 <b>Batches created by</b> <code>{esc(target_uid)}</code> ({len(batches)})\n\n"
    for b in batches:
        link = f"https://t.me/{bot_username}?start=batch_{b['batch_id']}"
        name = esc(b.get("name") or b["batch_id"])
        text += f"🗂 {name} – {len(b['files'])} files\n🔗 {esc(link)}\n\n"
    send_message(chat_id, text)


def handle_set_expiry(chat_id, admin_id, args):
    if not is_admin(admin_id):
        send_message(chat_id, "❌ Admins only.")
        return
    if len(args) < 2:
        send_message(chat_id, "❌ Usage: /setexpiry <link_id> <duration e.g. 30m, 2h, 1d>")
        return
    link_id, duration_str = args[0], args[1]
    delta = parse_duration(duration_str)
    if not delta:
        send_message(chat_id, "❌ Invalid duration. Use formats like 30m, 2h, 1d.")
        return
    kind, owner, entry = find_link_by_id(link_id)
    if not entry:
        send_message(chat_id, "❌ Link not found.")
        return
    expires_at = (datetime.now() + delta).isoformat()
    updates = {"expires_at": expires_at}
    if kind == "file":
        update_file_entry(owner, entry["unique_id"], updates)
    else:
        update_batch_entry(owner, entry["batch_id"], updates)
    nice_time = expires_at[:16].replace("T", " ")
    send_message(chat_id, f"⏰ Expiry set on <code>{esc(link_id)}</code>.\nIt will expire at {nice_time}.")


def handle_remove_expiry(chat_id, admin_id, args):
    if not is_admin(admin_id):
        send_message(chat_id, "❌ Admins only.")
        return
    if not args:
        send_message(chat_id, "❌ Usage: /removeexpiry <link_id>")
        return
    kind, owner, entry = find_link_by_id(args[0])
    if not entry:
        send_message(chat_id, "❌ Link not found.")
        return
    updates = {"expires_at": None}
    if kind == "file":
        update_file_entry(owner, entry["unique_id"], updates)
    else:
        update_batch_entry(owner, entry["batch_id"], updates)
    send_message(chat_id, "✅ Expiry removed. This link no longer expires by time.")


def handle_set_views(chat_id, admin_id, args):
    if not is_admin(admin_id):
        send_message(chat_id, "❌ Admins only.")
        return
    if len(args) < 2 or not args[1].isdigit():
        send_message(chat_id, "❌ Usage: /setviews <link_id> <max_views>")
        return
    link_id, limit = args[0], int(args[1])
    kind, owner, entry = find_link_by_id(link_id)
    if not entry:
        send_message(chat_id, "❌ Link not found.")
        return
    updates = {"view_limit": limit}
    if "view_count" not in entry:
        updates["view_count"] = 0
    if kind == "file":
        update_file_entry(owner, entry["unique_id"], updates)
    else:
        update_batch_entry(owner, entry["batch_id"], updates)
    send_message(
        chat_id,
        f"🔒 Super Private Link set on <code>{esc(link_id)}</code>.\n"
        f"Only the first {limit} person(s) to open it will get access.",
    )


def handle_remove_views(chat_id, admin_id, args):
    if not is_admin(admin_id):
        send_message(chat_id, "❌ Admins only.")
        return
    if not args:
        send_message(chat_id, "❌ Usage: /removeviews <link_id>")
        return
    kind, owner, entry = find_link_by_id(args[0])
    if not entry:
        send_message(chat_id, "❌ Link not found.")
        return
    updates = {"view_limit": None}
    if kind == "file":
        update_file_entry(owner, entry["unique_id"], updates)
    else:
        update_batch_entry(owner, entry["batch_id"], updates)
    send_message(chat_id, "✅ View limit removed. This is a normal link again.")


def handle_link_viewers(chat_id, admin_id, args):
    if not is_admin(admin_id):
        send_message(chat_id, "❌ Admins only.")
        return
    if not args:
        send_message(chat_id, "❌ Usage: /linkviewers <link_id>")
        return
    kind, owner, entry = find_link_by_id(args[0])
    if not entry:
        send_message(chat_id, "❌ Link not found.")
        return
    viewers = entry.get("viewers", [])
    if not viewers:
        send_message(chat_id, "📭 No one has viewed this link yet.")
        return
    text = f"👁 <b>Viewers</b> ({len(viewers)})\n\n"
    for v in viewers:
        nice_time = v["viewed_at"][:16].replace("T", " ")
        text += f"🆔 <code>{esc(v['user_id'])}</code> — {nice_time}\n"
    send_message(chat_id, text)


def handle_new_text(chat_id, admin_id, text_content):
    if not is_admin(admin_id):
        send_message(chat_id, "❌ Admins only.")
        return
    if not text_content:
        send_message(chat_id, "❌ Usage: /newtext <your text here>")
        return
    uid = str(admin_id)
    files = get_json(f"files:{uid}", [])
    file_uid = generate_id()
    preview_name = (text_content[:30] + "…") if len(text_content) > 30 else text_content
    entry = {
        "unique_id": file_uid,
        "type": "text",
        "content": text_content,
        "file_name": preview_name,
        "file_size": 0,
        "caption": "",
        "timestamp": datetime.now().isoformat(),
    }
    files.append(entry)
    set_json(f"files:{uid}", files)

    index = get_json("files_index", {})
    index[file_uid] = uid
    set_json("files_index", index)

    bot_username = get_me_username()
    link = f"https://t.me/{bot_username}?start={file_uid}"
    send_message(
        chat_id,
        f"📝 <b>Text Link Created</b>\n\n{esc(text_content[:200])}\n\n🔗 {esc(link)}",
    )


def handle_broadcast(chat_id, admin_id, message_text):
    if not is_admin(admin_id):
        send_message(chat_id, "❌ Admins only.")
        return
    if not message_text:
        send_message(chat_id, "❌ Usage: /broadcast <message>")
        return

    all_users = get_json("all_users", {})
    if not all_users:
        send_message(chat_id, "📭 No known users to broadcast to yet.")
        return

    header, entities = compose(("envelope",), " ", ("bold", "Broadcast"))
    broadcast_text = f"{header}\n{DIVIDER}\n\n{message_text}"

    sent, failed = 0, 0
    for target_uid in all_users.keys():
        try:
            # Short timeout per recipient - a single slow/unreachable user
            # must not be able to stall the whole loop toward Vercel's
            # execution limit (that's what caused the repeat-broadcast bug).
            result = send_message(int(target_uid), broadcast_text, entities=entities, timeout=5)
            if result.get("ok"):
                sent += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    send_message(
        chat_id,
        f"📢 Broadcast finished.\n✅ Delivered: {sent}\n❌ Failed (blocked bot / invalid): {failed}",
    )


# ==================== CALLBACK QUERY HANDLER ====================
def handle_callback(callback):
    data = callback["data"]
    callback_id = callback["id"]
    user_id = callback["from"]["id"]
    uid = str(user_id)
    chat_id = callback["message"]["chat"]["id"]
    message_id = callback["message"]["message_id"]

    # Always allow the "I've joined" recheck button through the gate.
    if data != "checkjoin" and REQUIRED_CHATS:
        missing = missing_joins(user_id)
        if missing:
            answer_callback(callback_id, "Please join the required channel/chat first.", show_alert=True)
            return

    if data == "list":
        answer_callback(callback_id)
        render_file_list(chat_id, user_id, edit=message_id)
        return

    if data == "noop":
        answer_callback(callback_id)
        return

    if data.startswith("listpage_"):
        answer_callback(callback_id)
        page = int(data[9:])
        render_file_list(chat_id, user_id, page=page, edit=message_id)
        return

    if data.startswith("filemenu_"):
        answer_callback(callback_id)
        file_uid = data[9:]
        render_file_detail(chat_id, user_id, file_uid, edit=message_id)
        return

    if data.startswith("fileexp_"):
        answer_callback(callback_id)
        file_uid = data[8:]
        owner, f = find_file_by_uid(file_uid)
        if not f or not ((str(user_id) == owner) or is_admin(user_id)):
            edit_message(chat_id, message_id, "❌ You can only manage your own files.")
            return
        render_expiry_menu(chat_id, message_id, file_uid)
        return

    if data.startswith("fileviews_"):
        answer_callback(callback_id)
        file_uid = data[10:]
        owner, f = find_file_by_uid(file_uid)
        if not f or not ((str(user_id) == owner) or is_admin(user_id)):
            edit_message(chat_id, message_id, "❌ You can only manage your own files.")
            return
        render_views_menu(chat_id, message_id, file_uid)
        return

    if data.startswith("setexp_"):
        answer_callback(callback_id)
        remainder = data[len("setexp_"):]
        file_uid, preset = remainder.rsplit("_", 1)  # preset has no underscores, safe from the right
        owner, f = find_file_by_uid(file_uid)
        if not f or not ((str(user_id) == owner) or is_admin(user_id)):
            edit_message(chat_id, message_id, "❌ You can only manage your own files.")
            return
        if preset == "remove":
            update_file_entry(owner, file_uid, {"expires_at": None})
        else:
            delta = parse_duration(preset)
            expires_at = (datetime.now() + delta).isoformat()
            update_file_entry(owner, file_uid, {"expires_at": expires_at})
        render_file_detail(chat_id, user_id, file_uid, edit=message_id)
        return

    if data.startswith("setviews_"):
        answer_callback(callback_id)
        remainder = data[len("setviews_"):]
        file_uid, preset = remainder.rsplit("_", 1)
        owner, f = find_file_by_uid(file_uid)
        if not f or not ((str(user_id) == owner) or is_admin(user_id)):
            edit_message(chat_id, message_id, "❌ You can only manage your own files.")
            return
        if preset == "remove":
            update_file_entry(owner, file_uid, {"view_limit": None})
        else:
            updates = {"view_limit": int(preset)}
            if "view_count" not in f:
                updates["view_count"] = 0
            update_file_entry(owner, file_uid, updates)
        render_file_detail(chat_id, user_id, file_uid, edit=message_id)
        return

    if data.startswith("filedel_"):
        answer_callback(callback_id)
        file_uid = data[8:]
        owner, f = find_file_by_uid(file_uid)
        if not f or not ((str(user_id) == owner) or is_admin(user_id)):
            edit_message(chat_id, message_id, "❌ You can only delete your own files.")
            return
        files = get_json(f"files:{owner}", [])
        files = [x for x in files if x["unique_id"] != file_uid]
        set_json(f"files:{owner}", files)
        index = get_json("files_index", {})
        index.pop(file_uid, None)
        set_json("files_index", index)
        edit_message(chat_id, message_id, "✅ File deleted.")
        return

    if data == "batch":
        answer_callback(callback_id)
        render_batch_menu(chat_id, user_id, edit=message_id)
        return

    if data == "newbatch":
        answer_callback(callback_id)
        edit_message(
            chat_id,
            message_id,
            "📦 Name this batch:",
            reply_markup=kb(
                [
                    [btn("🏷 Custom Name", "newbatch_custom")],
                    [btn("🔢 Default Name (Batch N)", "newbatch_default")],
                ]
            ),
        )
        return

    if data == "newbatch_default":
        answer_callback(callback_id)
        set_json(f"pick:{uid}", [])
        redis_set(f"batch_target:{uid}", "new")
        redis_del(f"batch_custom_name:{uid}")
        render_batch_picker(chat_id, user_id, edit=message_id)
        return

    if data == "newbatch_custom":
        answer_callback(callback_id)
        set_json(f"pick:{uid}", [])
        redis_set(f"batch_target:{uid}", "new")
        redis_set(f"awaiting_batch_name:{uid}", "1")
        edit_message(chat_id, message_id, "✏️ Send the name you want for this batch.")
        return

    if data.startswith("editbatch_"):
        answer_callback(callback_id)
        batch_id = data[10:]
        _, batch = find_batch_by_id(batch_id)
        if not batch:
            edit_message(chat_id, message_id, "❌ Batch not found.")
            return
        set_json(f"pick:{uid}", list(batch["files"]))
        redis_set(f"batch_target:{uid}", batch_id)
        render_batch_picker(chat_id, user_id, edit=message_id)
        return

    if data.startswith("copy_"):
        answer_callback(callback_id)
        file_uid = data[5:]
        bot_username = get_me_username()
        link = f"https://t.me/{bot_username}?start={file_uid}"
        edit_message(chat_id, message_id, f"📋 Copy this link:\n{esc(link)}")
        return

    if data.startswith("addbatch_"):
        answer_callback(callback_id, "Use /batch to pick your files", show_alert=True)
        return

    if data.startswith("pick_"):
        file_uid = data[5:]
        selected = get_json(f"pick:{uid}", [])
        if file_uid in selected:
            selected.remove(file_uid)
        else:
            selected.append(file_uid)
        set_json(f"pick:{uid}", selected)
        answer_callback(callback_id)
        render_batch_picker(chat_id, user_id, edit=message_id)
        return

    if data == "batchselectall":
        files = get_json(f"files:{uid}", [])
        set_json(f"pick:{uid}", [f["unique_id"] for f in files])
        answer_callback(callback_id, "All files selected")
        render_batch_picker(chat_id, user_id, edit=message_id)
        return

    if data == "batchclearsel":
        set_json(f"pick:{uid}", [])
        answer_callback(callback_id, "Selection cleared")
        render_batch_picker(chat_id, user_id, edit=message_id)
        return

    if data == "finishbatch":
        answer_callback(callback_id)
        selected = get_json(f"pick:{uid}", [])
        if not selected:
            edit_message(chat_id, message_id, "❌ You didn't select any files. Batch cancelled.")
            redis_del(f"pick:{uid}")
            redis_del(f"batch_target:{uid}")
            return

        target = redis_get(f"batch_target:{uid}") or "new"
        batches = get_json(f"batches:{uid}", [])
        bot_username = get_me_username()

        if target == "new":
            batch_id = generate_id()
            custom_name = redis_get(f"batch_custom_name:{uid}")
            name = custom_name if custom_name else f"Batch {len(batches) + 1}"
            redis_del(f"batch_custom_name:{uid}")
            batches.append(
                {
                    "batch_id": batch_id,
                    "name": name,
                    "files": selected,
                    "created": datetime.now().isoformat(),
                }
            )
            set_json(f"batches:{uid}", batches)
            index = get_json("batches_index", {})
            index[batch_id] = uid
            set_json("batches_index", index)
            action_text = f"<b>{esc(name)}</b> created"
        else:
            batch_id = target
            for b in batches:
                if b["batch_id"] == batch_id:
                    b["files"] = selected
                    name = b.get("name") or batch_id
                    break
            else:
                name = batch_id
            set_json(f"batches:{uid}", batches)
            action_text = f"<b>{esc(name)}</b> updated"

        redis_del(f"pick:{uid}")
        redis_del(f"batch_target:{uid}")

        link = f"https://t.me/{bot_username}?start=batch_{batch_id}"
        edit_message(
            chat_id,
            message_id,
            f"📦 {action_text} successfully!\n\n"
            f"📁 Files included: {len(selected)}\n"
            f"🔗 Share this link:\n{esc(link)}\n\n"
            f"Anyone who opens it will receive all files in this batch.",
        )
        return

    if data == "cancelbatch":
        answer_callback(callback_id)
        redis_del(f"pick:{uid}")
        redis_del(f"batch_target:{uid}")
        edit_message(chat_id, message_id, "❌ Batch build cancelled.")
        return

    if data == "clearall_ask":
        answer_callback(callback_id)
        files = get_json(f"files:{uid}", [])
        if not files:
            edit_message(chat_id, message_id, "📭 No files to delete.")
            return
        markup = kb(
            [[btn("✅ Yes, delete all", "clearall_yes"), btn("❌ No, cancel", "clearall_no")]]
        )
        edit_message(
            chat_id,
            message_id,
            f"⚠️ Delete all {len(files)} of your saved files? This can't be undone.",
            reply_markup=markup,
        )
        return

    if data == "clearall_yes":
        answer_callback(callback_id)
        files = get_json(f"files:{uid}", [])
        count = len(files)
        index = get_json("files_index", {})
        for f in files:
            index.pop(f["unique_id"], None)
        set_json("files_index", index)
        redis_del(f"files:{uid}")
        edit_message(chat_id, message_id, f"✅ Deleted all {count} files.")
        return

    if data == "clearall_no":
        answer_callback(callback_id, "Cancelled")
        edit_message(chat_id, message_id, "❌ Deletion cancelled. Your files are safe.")
        return

    if data.startswith("delbatch_"):
        answer_callback(callback_id)
        batch_id = data[9:]
        batches = get_json(f"batches:{uid}", [])
        batches = [b for b in batches if b["batch_id"] != batch_id]
        set_json(f"batches:{uid}", batches)
        index = get_json("batches_index", {})
        index.pop(batch_id, None)
        set_json("batches_index", index)
        edit_message(chat_id, message_id, "✅ Batch deleted. Your files themselves are untouched.")
        return

    if data.startswith("adminview_"):
        answer_callback(callback_id)
        if not is_admin(user_id):
            edit_message(chat_id, message_id, "❌ Admins only.")
            return
        target_uid = data[10:]
        handle_admin_files(chat_id, user_id, target_uid)
        return

    if data == "checkjoin":
        missing = missing_joins(user_id)
        if missing:
            answer_callback(callback_id, "You haven't joined everything yet.", show_alert=True)
            return
        answer_callback(callback_id, "Access granted!")

        # If they were trying to open a file/batch link before the gate
        # stopped them, deliver it now automatically instead of making
        # them click the link a second time.
        pending_args = get_json(f"pending_start:{uid}", None)
        if pending_args:
            redis_del(f"pending_start:{uid}")
            edit_message(chat_id, message_id, "✅ Verified! Delivering your file(s) now...")
            handle_start(chat_id, user_id, pending_args)
        else:
            edit_message(chat_id, message_id, "✅ You're all set! Send /start to begin.")
        return


# ==================== MESSAGE HANDLER ====================
def handle_message(message):
    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]
    text = message.get("text", "")

    is_file_msg = any(k in message for k in ("document", "photo", "video", "audio", "voice"))
    record_user_activity(message["from"], is_upload=is_file_msg)

    # If this user is mid-flow providing a custom batch name, capture it
    # here before any other routing.
    if text and redis_get(f"awaiting_batch_name:{user_id}"):
        redis_del(f"awaiting_batch_name:{user_id}")
        redis_set(f"batch_custom_name:{user_id}", text.strip()[:60])
        render_batch_picker(chat_id, user_id)
        return

    # Force-join gate: everyone must join the required channel + chat first.
    if REQUIRED_CHATS:
        missing = missing_joins(user_id)
        if missing:
            # Remember what they were trying to open so we can deliver it
            # automatically once they pass verification, instead of making
            # them click the link again.
            if text.startswith("/start"):
                parts = text.split(maxsplit=1)
                args = parts[1].split() if len(parts) > 1 else []
                if args:
                    set_json(f"pending_start:{user_id}", args)
            send_join_prompt(chat_id, missing)
            return

    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        args = parts[1].split() if len(parts) > 1 else []
        handle_start(chat_id, user_id, args)
        return

    if text.startswith("/list"):
        render_file_list(chat_id, user_id)
        return

    if text.startswith("/link"):
        parts = text.split()
        handle_link(chat_id, user_id, parts[1:])
        return

    if text.startswith("/delete"):
        parts = text.split()
        handle_delete(chat_id, user_id, parts[1:])
        return

    if text.startswith("/clear"):
        handle_clear(chat_id, user_id)
        return

    if text.startswith("/batch"):
        handle_batch_command(chat_id, user_id)
        return

    if text.startswith("/mybatch"):
        handle_mybatch(chat_id, user_id)
        return

    if text.startswith("/stats"):
        handle_stats(chat_id)
        return

    if text.startswith("/broadcast"):
        parts = text.split(maxsplit=1)
        broadcast_msg = parts[1] if len(parts) > 1 else ""
        handle_broadcast(chat_id, user_id, broadcast_msg)
        return

    if text.startswith("/adminfiles"):
        parts = text.split()
        if len(parts) > 1:
            handle_admin_files(chat_id, user_id, parts[1])
        else:
            send_message(chat_id, "❌ Usage: /adminfiles <user_id>")
        return

    if text.startswith("/adminbatches"):
        parts = text.split()
        if len(parts) > 1:
            handle_admin_batches(chat_id, user_id, parts[1])
        else:
            send_message(chat_id, "❌ Usage: /adminbatches <user_id>")
        return

    if text.startswith("/admin"):
        handle_admin(chat_id, user_id)
        return

    if text.startswith("/setexpiry"):
        handle_set_expiry(chat_id, user_id, text.split()[1:])
        return

    if text.startswith("/removeexpiry"):
        handle_remove_expiry(chat_id, user_id, text.split()[1:])
        return

    if text.startswith("/setviews"):
        handle_set_views(chat_id, user_id, text.split()[1:])
        return

    if text.startswith("/removeviews"):
        handle_remove_views(chat_id, user_id, text.split()[1:])
        return

    if text.startswith("/linkviewers"):
        handle_link_viewers(chat_id, user_id, text.split()[1:])
        return

    if text.startswith("/newtext"):
        parts = text.split(maxsplit=1)
        content = parts[1] if len(parts) > 1 else ""
        handle_new_text(chat_id, user_id, content)
        return

    # File forwarded to the bot
    if message.get("forward_origin") or message.get("forward_from") or message.get("forward_from_chat"):
        handle_forwarded_file(chat_id, user_id, message)
        return

    if any(k in message for k in ("document", "photo", "video", "audio", "voice")):
        send_message(
            chat_id,
            "❌ <b>Please forward this file instead of sending it directly.</b>\n\n"
            "Here's the easiest way:\n"
            "1️⃣ Open the chat with the file (or find it in any chat)\n"
            "2️⃣ Long-press it → <b>Forward</b> → choose <b>Saved Messages</b>\n"
            "3️⃣ Open <b>Saved Messages</b>, find it there\n"
            "4️⃣ Long-press it again → <b>Forward</b> → send it to me\n\n"
            "This keeps the file's original quality and lets me generate a "
            "proper shareable link for it.",
        )
        return


def handle_join_request(jr):
    """Records that a user sent a join request to a required chat, so
    they can pass the force-join gate even before you approve them."""
    chat_id = jr["chat"]["id"]
    user_id = jr["from"]["id"]
    key = f"join_requests:{chat_id}"
    requested = get_json(key, [])
    if user_id not in requested:
        requested.append(user_id)
        set_json(key, requested)


# ==================== WEBHOOK ROUTE ====================
@app.route("/api/index", methods=["POST"])
def webhook():
    update = request.get_json(force=True, silent=True) or {}

    if is_duplicate_update(update.get("update_id")):
        return jsonify({"ok": True})

    if "message" in update:
        handle_message(update["message"])
    elif "callback_query" in update:
        handle_callback(update["callback_query"])
    elif "chat_join_request" in update:
        handle_join_request(update["chat_join_request"])

    return jsonify({"ok": True})


@app.route("/api/index", methods=["GET"])
def health():
    return jsonify({"status": "Bot is alive", "developer": DEVELOPER})


# Vercel's Python runtime looks for a top-level WSGI `app` object, which
# we already have via Flask - no extra handler needed.
