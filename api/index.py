import os
import json
import html
import base64
import random
from datetime import datetime

import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ==================== CONFIG (set these as Vercel Environment Variables) ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
DEVELOPER = os.environ.get("DEVELOPER", "@GpsirEra")

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
}

DIVIDER = "─" * 22

# ==================== REQUIRED CHANNEL / CHAT (force-join) ====================
# Bot must be an admin (or at least a member) of both for getChatMember to work.
REQUIRED_CHATS = [
    {
        "chat_id": -1004485651677,
        "title": "GpsirEra Community",
        "url": "https://t.me/Black_hats_ops",
    },
    {
        "chat_id": -1003927824087,
        "title": "GpsirEra Community | Chat",
        "url": "https://t.me/+VXs73pFfyEphMzJl",
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


def tg(method, payload):
    r = requests.post(f"{TELEGRAM_API}/{method}", json=payload, timeout=15)
    return r.json()


def send_message(chat_id, text, entities=None, reply_markup=None, parse_mode="HTML"):
    payload = {"chat_id": chat_id, "text": text}
    if entities:
        payload["entities"] = entities
        payload.pop("parse_mode", None)  # entities and parse_mode are mutually exclusive
    elif parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return tg("sendMessage", payload)


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


def missing_joins(user_id):
    """Returns the list of required chats the user has NOT joined yet.
    Empty list = fully joined, gate passes."""
    missing = []
    for ch in REQUIRED_CHATS:
        try:
            r = tg("getChatMember", {"chat_id": ch["chat_id"], "user_id": user_id})
            status = r.get("result", {}).get("status")
            if status not in ("member", "administrator", "creator"):
                missing.append(ch)
        except Exception:
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
            _, batch = find_batch_by_id(batch_id)
            if not batch:
                send_message(chat_id, "❌ Batch not found or expired.")
                return
            send_message(chat_id, f"📦 Sending {len(batch['files'])} files...")
            for file_uid in batch["files"]:
                _, f = find_file_by_uid(file_uid)
                if f:
                    send_document(chat_id, f["file_id"], caption=f"📁 {f['file_name']}")
            return

        _, f = find_file_by_uid(arg)
        if f:
            caption = (
                f"📁 {f['file_name']}\n"
                f"💾 {format_size(f['file_size'])}\n"
                f"Powered by {DEVELOPER}"
            )
            send_document(chat_id, f["file_id"], caption=caption)
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
    if "document" in message:
        file_obj = message["document"]
        fname = file_obj.get("file_name", "document")
    elif "video" in message:
        file_obj = message["video"]
        fname = file_obj.get("file_name", "video.mp4")
    elif "audio" in message:
        file_obj = message["audio"]
        fname = file_obj.get("file_name", "audio.mp3")
    elif "voice" in message:
        file_obj = message["voice"]
        fname = f"voice_{datetime.now().strftime('%H%M%S')}.ogg"
    elif "photo" in message:
        file_obj = message["photo"][-1]
        fname = f"photo_{datetime.now().strftime('%H%M%S')}.jpg"
    else:
        send_message(chat_id, "❌ Unsupported file type!")
        return

    files = get_json(f"files:{uid}", [])
    file_uid = generate_id()
    entry = {
        "unique_id": file_uid,
        "file_id": file_obj["file_id"],
        "file_name": fname,
        "file_size": file_obj.get("file_size", 0),
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
        f"🔗 {link}\n\n",
        "Use /batch to add this into a multi-file batch link.",
    )
    markup = kb(
        [
            [btn("📋 Copy Link", f"copy_{file_uid}")],
            [btn("📦 Add to Batch", f"addbatch_{file_uid}")],
        ]
    )
    send_message(chat_id, text, entities=entities, reply_markup=markup)


def render_file_list(chat_id, user_id, edit=None):
    uid = str(user_id)
    files = get_json(f"files:{uid}", [])
    if not files:
        text = "📭 No files found."
        if edit:
            edit_message(chat_id, edit, text)
        else:
            send_message(chat_id, text)
        return

    bot_username = get_me_username()
    text = f"📁 <b>Your Files</b> ({len(files)})\n\n"
    for idx, f in enumerate(files):
        line = (
            f"{idx + 1}. {esc(f['file_name'])}\n"
            f"   💾 {format_size(f['file_size'])}\n"
            f"   🆔 <code>{esc(f['unique_id'])}</code>\n"
            f"   🔗 https://t.me/{bot_username}?start={f['unique_id']}\n\n"
        )
        if len(text) + len(line) > 3500:
            text += "... (truncated, use /list again for more)"
            break
        text += line

    markup = kb([[btn("🗑 Delete All Files", "clearall_ask")]])
    if edit:
        edit_message(chat_id, edit, text, reply_markup=markup)
    else:
        send_message(chat_id, text, reply_markup=markup)


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

    header, entities = compose(("card_index",), " ", ("bold", "Your Batches"))
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

    header, entities = compose(("desktop",), " ", ("bold", "Admin Panel"))
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
        "Use <code>/broadcast &lt;message&gt;</code> to message every user who has opened the bot.",
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
            result = send_message(int(target_uid), broadcast_text, entities=entities)
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
        render_file_list(chat_id, user_id)
        return

    if data == "batch":
        answer_callback(callback_id)
        render_batch_menu(chat_id, user_id, edit=message_id)
        return

    if data == "newbatch":
        answer_callback(callback_id)
        set_json(f"pick:{uid}", [])
        redis_set(f"batch_target:{uid}", "new")
        render_batch_picker(chat_id, user_id, edit=message_id)
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
            name = f"Batch {len(batches) + 1}"
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

    # File forwarded to the bot
    if message.get("forward_origin") or message.get("forward_from") or message.get("forward_from_chat"):
        handle_forwarded_file(chat_id, user_id, message)
        return

    if any(k in message for k in ("document", "photo", "video", "audio", "voice")):
        send_message(chat_id, "❌ Please *forward* a file to me (not send it directly)!")
        return


# ==================== WEBHOOK ROUTE ====================
@app.route("/api/index", methods=["POST"])
def webhook():
    update = request.get_json(force=True, silent=True) or {}

    if "message" in update:
        handle_message(update["message"])
    elif "callback_query" in update:
        handle_callback(update["callback_query"])

    return jsonify({"ok": True})


@app.route("/api/index", methods=["GET"])
def health():
    return jsonify({"status": "Bot is alive", "developer": DEVELOPER})


# Vercel's Python runtime looks for a top-level WSGI `app` object, which
# we already have via Flask - no extra handler needed.
