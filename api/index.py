import os
import json
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
}

DIVIDER = "─" * 22

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
    Build a (text, entities) pair from segments.
    Each segment is either:
      - a plain string, or
      - a tuple (emoji_key,) to insert a premium custom emoji from PREMIUM_EMOJIS
    Returns text ready to send with entities for the custom emoji.
    """
    full_text = ""
    entities = []
    for seg in segments:
        if isinstance(seg, tuple):
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


def tg(method, payload):
    r = requests.post(f"{TELEGRAM_API}/{method}", json=payload, timeout=15)
    return r.json()


def send_message(chat_id, text, entities=None, reply_markup=None, parse_mode="Markdown"):
    payload = {"chat_id": chat_id, "text": text}
    if entities:
        payload["entities"] = entities
        payload.pop("parse_mode", None)  # entities and parse_mode are mutually exclusive
    elif parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return tg("sendMessage", payload)


def edit_message(chat_id, message_id, text, entities=None, reply_markup=None, parse_mode="Markdown"):
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
    premium = is_premium(user_id)

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

    if premium:
        text, entities = compose(
            ("thumbs_up",), " *PREMIUM VAULT*\n",
            f"{DIVIDER}\n\n",
            "Welcome back, Premium member.\n",
            "Every feature below is unlocked for you.\n\n",
            ("memo",), " Forward any file → get an instant link\n",
            ("check",), " Use /batch to hand-pick files into one shareable link\n\n",
            "*Commands*\n",
            "/list – your files\n",
            "/link <id> – get a link\n",
            "/delete <id> – delete a file\n",
            "/clear – wipe all your files\n",
            "/batch – build a batch\n",
            "/mybatch – your saved batches\n",
            "/stats – bot statistics\n\n",
            f"{DIVIDER}\n",
            ("heart_black",), f" Developer: {DEVELOPER}",
        )
        markup = kb(
            [
                [btn("📋 My Files", "list"), btn("📦 Build Batch", "batch")],
                [btn("👑 Premium Status", "premium")],
            ]
        )
        send_message(chat_id, text, entities=entities, reply_markup=markup)
    else:
        text = (
            "🚀 *File Share Bot*\n\n"
            "Forward any file to me – I'll give you a shareable link!\n\n"
            "*Commands*\n"
            "/list – your files\n"
            "/link <id> – get link\n"
            "/delete <id> – delete a file\n"
            "/clear – delete all files\n\n"
            f"⭐ Upgrade to Premium: {DEVELOPER}"
        )
        markup = kb([[btn("📋 My Files", "list")]])
        send_message(chat_id, text, reply_markup=markup)


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
    premium = is_premium(user_id)

    if premium:
        text, entities = compose(
            ("check",), " *File Saved*\n",
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
    else:
        send_message(
            chat_id,
            f"✅ *File Saved!*\n\n📁 {fname}\n💾 {format_size(entry['file_size'])}\n🔗 {link}\n\n"
            f"⭐ Upgrade to Premium: {DEVELOPER}",
        )


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
    text = f"📁 *Your Files* ({len(files)})\n\n"
    for idx, f in enumerate(files):
        line = (
            f"{idx + 1}. {f['file_name']}\n"
            f"   💾 {format_size(f['file_size'])}\n"
            f"   🆔 `{f['unique_id']}`\n"
            f"   🔗 https://t.me/{bot_username}?start={f['unique_id']}\n\n"
        )
        if len(text) + len(line) > 3500:
            text += "... (truncated, use /list again for more)"
            break
        text += line

    if edit:
        edit_message(chat_id, edit, text)
    else:
        send_message(chat_id, text)


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

    rows = []
    for f in files:
        mark = "✅" if f["unique_id"] in selected else "⬜"
        label = f"{mark} {f['file_name'][:30]}"
        rows.append([btn(label, f"pick_{f['unique_id']}")])
    rows.append([btn("📦 Finish Batch", "finishbatch"), btn("❌ Cancel", "cancelbatch")])

    text = (
        f"📦 *Build a Batch*\n\n"
        f"Selected: {len(selected)}/{len(files)}\n"
        f"Tap files to select/deselect, then press Finish Batch."
    )
    markup = kb(rows)

    if edit:
        edit_message(chat_id, edit, text, reply_markup=markup)
    else:
        send_message(chat_id, text, reply_markup=markup)


def handle_batch_command(chat_id, user_id):
    if not is_premium(user_id):
        send_message(chat_id, f"❌ Premium feature. Contact {DEVELOPER}")
        return
    uid = str(user_id)
    files = get_json(f"files:{uid}", [])
    if not files:
        send_message(chat_id, "📭 No files to batch. Forward some files first.")
        return
    set_json(f"pick:{uid}", [])
    render_batch_picker(chat_id, user_id)


def handle_mybatch(chat_id, user_id):
    if not is_premium(user_id):
        send_message(chat_id, "❌ Premium only.")
        return
    uid = str(user_id)
    batches = get_json(f"batches:{uid}", [])
    if not batches:
        send_message(chat_id, "📭 No batches yet.")
        return
    bot_username = get_me_username()
    text = "📦 *Your Batches*\n\n"
    for b in batches:
        link = f"https://t.me/{bot_username}?start=batch_{b['batch_id']}"
        text += f"🆔 `{b['batch_id']}` – {len(b['files'])} files\n🔗 {link}\n\n"
    send_message(chat_id, text)


def handle_stats(chat_id):
    index = get_json("files_index", {})
    total_files = len(index)
    owners = set(index.values())
    total_users = len(owners)
    premium_count = len([u for u in owners if is_premium(int(u))])
    send_message(
        chat_id,
        f"📊 *Bot Statistics*\n\n"
        f"👥 Users: {total_users}\n"
        f"📁 Files: {total_files}\n"
        f"👑 Premium Users: {premium_count}\n"
        f"👨‍💻 Developer: {DEVELOPER}",
    )


# ==================== CALLBACK QUERY HANDLER ====================
def handle_callback(callback):
    data = callback["data"]
    callback_id = callback["id"]
    user_id = callback["from"]["id"]
    uid = str(user_id)
    chat_id = callback["message"]["chat"]["id"]
    message_id = callback["message"]["message_id"]

    if data == "list":
        answer_callback(callback_id)
        render_file_list(chat_id, user_id)
        return

    if data == "batch":
        answer_callback(callback_id)
        if not is_premium(user_id):
            edit_message(chat_id, message_id, f"❌ Premium feature. Contact {DEVELOPER}")
            return
        files = get_json(f"files:{uid}", [])
        if not files:
            edit_message(chat_id, message_id, "📭 No files to batch.")
            return
        set_json(f"pick:{uid}", [])
        render_batch_picker(chat_id, user_id, edit=message_id)
        return

    if data == "premium":
        answer_callback(callback_id)
        if is_premium(user_id):
            edit_message(chat_id, message_id, f"👑 You are a Premium user! Enjoy all features.\nDev: {DEVELOPER}")
        else:
            edit_message(chat_id, message_id, f"⭐ You are a Free user. Upgrade: {DEVELOPER}")
        return

    if data.startswith("copy_"):
        answer_callback(callback_id)
        file_uid = data[5:]
        bot_username = get_me_username()
        link = f"https://t.me/{bot_username}?start={file_uid}"
        edit_message(chat_id, message_id, f"📋 Copy this link:\n{link}")
        return

    if data.startswith("addbatch_"):
        answer_callback(callback_id, "Use /batch to pick your files", show_alert=True)
        return

    if data.startswith("pick_"):
        if not is_premium(user_id):
            answer_callback(callback_id, "Premium feature.", show_alert=True)
            return
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

    if data == "finishbatch":
        answer_callback(callback_id)
        selected = get_json(f"pick:{uid}", [])
        if not selected:
            edit_message(chat_id, message_id, "❌ You didn't select any files. Batch cancelled.")
            redis_del(f"pick:{uid}")
            return
        batch_id = generate_id()
        batches = get_json(f"batches:{uid}", [])
        batches.append(
            {"batch_id": batch_id, "files": selected, "created": datetime.now().isoformat()}
        )
        set_json(f"batches:{uid}", batches)

        index = get_json("batches_index", {})
        index[batch_id] = uid
        set_json("batches_index", index)

        redis_del(f"pick:{uid}")

        bot_username = get_me_username()
        link = f"https://t.me/{bot_username}?start=batch_{batch_id}"
        edit_message(
            chat_id,
            message_id,
            f"📦 *Batch Created Successfully*\n\n"
            f"📁 Files included: {len(selected)}\n"
            f"🔗 Share this link:\n{link}\n\n"
            f"Anyone who opens it will receive all selected files.",
        )
        return

    if data == "cancelbatch":
        answer_callback(callback_id)
        redis_del(f"pick:{uid}")
        edit_message(chat_id, message_id, "❌ Batch build cancelled.")
        return


# ==================== MESSAGE HANDLER ====================
def handle_message(message):
    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]
    text = message.get("text", "")

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
