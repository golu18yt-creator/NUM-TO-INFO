import os
import random
import string
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime

# ================= CONFIGURATION =================
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = 8927308711
EXTERNAL_API_BASE = "https://paid-flix-num-info-api.alphamovies.workers.dev/"
API_KEY = "premium_key_99"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
DATA_FILE = "user_data.json"
CODES_FILE = "redeem_codes.json"

# ================= CHANNEL VERIFICATION =================
CHANNELS = ["Chirag_48776"]

def is_user_member(user_id, channel_username):
    try:
        url = f"{TELEGRAM_API_URL}/getChatMember"
        payload = {"chat_id": f"@{channel_username}", "user_id": user_id}
        resp = requests.get(url, params=payload, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                status = data["result"]["status"]
                return status in ("member", "administrator", "creator")
        return False
    except Exception:
        return False

def check_user_verification(user_id):
    user_data = get_user(user_id)
    for ch in CHANNELS:
        if not is_user_member(user_id, ch):
            if user_data:
                user_data["verified"] = False
                update_user(user_id, user_data)
            return False
    if user_data:
        user_data["verified"] = True
        update_user(user_id, user_data)
    return True

# ================= DATA MANAGEMENT =================
def load_user_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_user_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_user(uid):
    data = load_user_data()
    return data.get(str(uid))

def update_user(uid, user_info):
    data = load_user_data()
    data[str(uid)] = user_info
    save_user_data(data)

def load_codes():
    if os.path.exists(CODES_FILE):
        with open(CODES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_codes(codes):
    with open(CODES_FILE, "w", encoding="utf-8") as f:
        json.dump(codes, f, indent=2, ensure_ascii=False)

def get_bot_username():
    try:
        resp = requests.get(f"{TELEGRAM_API_URL}/getMe", timeout=5)
        if resp.status_code == 200:
            info = resp.json()
            if info.get("ok"):
                return info["result"]["username"]
    except:
        pass
    return "YourBotUsername"

# ================= HELPER FUNCTIONS =================
def tg_api_request(method, data=None):
    url = f"{TELEGRAM_API_URL}/{method}"
    try:
        response = requests.post(url, json=data) if data else requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] API request failed: {e}")
        return None

def send_message(chat_id, text, reply_markup=None, parse_mode=None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    if parse_mode:
        payload["parse_mode"] = parse_mode
    return tg_api_request("sendMessage", payload)

def get_updates(offset=None, timeout=30):
    payload = {"timeout": timeout}
    if offset is not None:
        payload["offset"] = offset
    result = tg_api_request("getUpdates", payload)
    if result and result.get("ok"):
        return result.get("result", [])
    return []

# ================= ACTIVITY TRACKING =================
def update_last_active(user_id):
    user_data = get_user(user_id)
    if user_data:
        user_data["last_active_date"] = datetime.now().strftime("%Y-%m-%d")
        update_user(user_id, user_data)

# ================= STYLISH KEYBOARD =================
reply_keyboard = {
    "keyboard": [
        [{"text": "🔍 𝐒𝐄𝐀𝐑𝐂𝐇 𝐍𝐔𝐌𝐁𝐄𝐑"}],
        [{"text": "📢 𝐑𝐄𝐅𝐄𝐑 & 𝐄𝐀𝐑𝐍"}, {"text": "👤 𝐏𝐑𝐎𝐅𝐈𝐋𝐄"}],
        [{"text": "🎫 𝐑𝐄𝐃𝐄𝐄𝐌 𝐂𝐎𝐃𝐄"}, {"text": "📢 𝐔𝐏𝐃𝐀𝐓𝐄 𝐂𝐇𝐀𝐍𝐍𝐄𝐋"}],
        [{"text": "👑 𝐀𝐃𝐌𝐈𝐍 𝐏𝐀𝐍𝐄𝐋"}]
    ],
    "resize_keyboard": True,
    "one_time_keyboard": False
}

# ================= MODIFY API RESPONSE =================
def clean_api_response(raw_json):
    # Replace all branding/credit fields with @DGDRIFT
    branding_keys = ["credit", "processed_by", "branding", "developer"]
    for key in branding_keys:
        if key in raw_json:
            raw_json[key] = "@DGDRIFT"
    return raw_json

# ================= DAILY FREE LIMIT CHECK =================
def check_free_searches(user_data, user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    last_date = user_data.get("free_date", "")
    used_today = user_data.get("free_used_today", 0)
    if last_date != today:
        user_data["free_date"] = today
        user_data["free_used_today"] = 0
        update_user(user_id, user_data)
        return 0
    return used_today

def use_free_search(user_data, user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    if user_data.get("free_date") != today:
        user_data["free_date"] = today
        user_data["free_used_today"] = 0
    used = user_data.get("free_used_today", 0)
    if used < 2:
        user_data["free_used_today"] = used + 1
        update_user(user_id, user_data)
        return True
    return False

# ================= REDEEM CODE SYSTEM =================
def generate_redeem_code(admin_id, coin_value):
    codes = load_codes()
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        if code not in codes:
            codes[code] = {
                "value": coin_value,
                "created_by": admin_id,
                "created_at": datetime.now().isoformat(),
                "claimed_by": None
            }
            save_codes(codes)
            return code

def redeem_code(user_id, code):
    codes = load_codes()
    code = code.upper().strip()
    if code not in codes:
        return False, "❌ Invalid or unknown code."
    entry = codes[code]
    if entry.get("claimed_by") is not None:
        return False, "❌ This code has already been used."
    entry["claimed_by"] = user_id
    save_codes(codes)
    user_data = get_user(user_id)
    if user_data is None:
        return False, "User not found."
    user_data["balance"] = user_data.get("balance", 0) + entry["value"]
    update_user(user_id, user_data)
    return True, f"✅ You claimed {entry['value']} coins! New balance: {user_data['balance']}."

def list_active_codes():
    codes = load_codes()
    active = {k: v for k, v in codes.items() if v.get("claimed_by") is None}
    if not active:
        return "No active codes."
    result = "🎫 **Active Redeem Codes**\n\n"
    for code, info in active.items():
        result += f"`{code}` → {info['value']} coins (created: {info['created_at'][:10]})\n"
    return result

def get_user_stats():
    users = load_user_data()
    total_users = len(users)
    total_coins = sum(u.get("balance", 0) for u in users.values())
    total_searches = sum(u.get("total_searches", 0) for u in users.values())
    return total_users, total_coins, total_searches

# ================= FULL STATUS =================
def get_full_status():
    users = load_user_data()
    total_users = len(users)
    total_referrals = sum(1 for u in users.values() if u.get("referred_by") is not None)
    total_searches = sum(u.get("total_searches", 0) for u in users.values())
    today = datetime.now().strftime("%Y-%m-%d")
    daily_active = sum(1 for u in users.values() if u.get("last_active_date") == today)
    msg = (
        f"📊 **FULL STATUS**\n\n"
        f"👥 Total Users: {total_users}\n"
        f"🔗 Total Referrals: {total_referrals}\n"
        f"🔍 Total Searches: {total_searches}\n"
        f"⭐ Daily Active Users (today): {daily_active}"
    )
    return msg

# ================= ADMIN FUNCTIONS =================
def ban_user(admin_id, target_id):
    if admin_id != OWNER_ID:
        return False, "Unauthorized"
    target = get_user(target_id)
    if target is None:
        return False, "User not found."
    current = target.get("banned", False)
    target["banned"] = not current
    update_user(target_id, target)
    status = "banned" if not current else "unbanned"
    return True, f"User {target_id} has been {status}."

def adjust_balance(admin_id, target_id, amount):
    if admin_id != OWNER_ID:
        return False, "Unauthorized"
    target = get_user(target_id)
    if target is None:
        return False, "User not found."
    new_balance = target.get("balance", 0) + amount
    if new_balance < 0:
        return False, "Balance cannot go negative."
    target["balance"] = new_balance
    update_user(target_id, target)
    return True, f"Updated balance for user {target_id}. New balance: {new_balance} coins."

def get_user_status(admin_id, target_id):
    if admin_id != OWNER_ID:
        return False, "Unauthorized"
    user = get_user(target_id)
    if user is None:
        return False, "User not found."
    all_users = load_user_data()
    referral_count = 0
    for uid, data in all_users.items():
        if data.get("referred_by") == target_id:
            referral_count += 1
    free_used = user.get("free_used_today", 0)
    free_left = 2 - free_used
    msg = (
        f"👤 **User Status**\n\n"
        f"🆔 ID: `{target_id}`\n"
        f"📛 Name: {user.get('first_name', '')} {user.get('last_name', '')}\n"
        f"🔖 Username: @{user.get('username', 'None')}\n"
        f"💰 Balance: {user.get('balance', 0)}\n"
        f"🔍 Total Searches: {user.get('total_searches', 0)}\n"
        f"👥 Referrals: {referral_count}\n"
        f"🆓 Free searches used today: {free_used}/2\n"
        f"🚫 Banned: {'Yes' if user.get('banned', False) else 'No'}\n"
        f"🔗 Referred by: {user.get('referred_by', 'None')}\n"
        f"📅 Last active: {user.get('last_active_date', 'Never')}\n"
        f"✅ Verified channels: {'Yes' if user.get('verified', False) else 'No'}"
    )
    return True, msg

# ================= ADMIN PANEL INLINE KEYBOARD =================
def send_admin_panel(chat_id):
    inline_keyboard = {
        "inline_keyboard": [
            [{"text": "🎁 Generate Code", "callback_data": "gen_code"}],
            [{"text": "📋 List Active Codes", "callback_data": "list_codes"}],
            [{"text": "📊 User Stats", "callback_data": "user_stats"}],
            [{"text": "📈 FULL STATUS", "callback_data": "full_status"}],
            [{"text": "🔨 Ban/Unban User", "callback_data": "ban_user"}],
            [{"text": "💰 Add/Remove Balance", "callback_data": "balance_user"}],
            [{"text": "ℹ️ User Status", "callback_data": "status_user"}],
            [{"text": "❌ Close", "callback_data": "close_admin"}]
        ]
    }
    send_message(chat_id, "👑 **Admin Panel**\nChoose an action:", reply_markup=inline_keyboard, parse_mode="Markdown")

# ================= VERIFICATION PROMPT =================
def send_verification_prompt(chat_id, user_id):
    keyboard = {
        "inline_keyboard": [
            [{"text": "📢 Join Chirag Channel", "url": "https://t.me/Chirag_48776"}],
            [{"text": "✅ I have joined", "callback_data": "verify_join"}]
        ]
    }
    text = (
        "🔒 **Access Restricted**\\n\\n"
        "You must join our official channel to use this bot:\\n"
        "1. [Chirag Channel](https://t.me/Chirag_48776)\\n\\n"
        "After joining, click the **'✅ I have joined'** button below to verify.\\n"
        "You need to join only once."
    )
    send_message(chat_id, text, reply_markup=keyboard, parse_mode="Markdown")

# ================= FILE SAVING FOR GROUP SEARCH =================
def save_and_send_result(chat_id, user_id, phone, result_json, cost_type):
    filename = "Drift-number.txt"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"\n==================\nTime: {timestamp}\nUser ID: {user_id}\nPhone: {phone}\nResult:\n{json.dumps(result_json, indent=2, ensure_ascii=False)}\n==================\n"
    with open(filename, "a", encoding="utf-8") as f:
        f.write(entry)
    try:
        with open(filename, "rb") as f:
            files = {"document": f}
            url = f"{TELEGRAM_API_URL}/sendDocument"
            payload = {"chat_id": chat_id, "caption": f"🔍 Search result for `{phone}` (used {cost_type})", "parse_mode": "Markdown"}
            requests.post(url, data=payload, files=files, timeout=10)
    except Exception as e:
        send_message(chat_id, f"❌ Failed to send file: {e}")

# ================= PERFORM SEARCH (common function) =================
def perform_search(user_id, chat_id, phone_number, user_data):
    free_used = check_free_searches(user_data, user_id)
    if free_used < 2:
        use_free_search(user_data, user_id)
        cost_type = "free"
    else:
        if user_data.get("balance", 0) >= 1:
            user_data["balance"] -= 1
            cost_type = "1 coin"
        else:
            return False, "❌ No free searches left and insufficient coins. Use referral or redeem code.", None, None
    # NEW API CALL
    api_url = f"{EXTERNAL_API_BASE}?num={phone_number}&key={API_KEY}"
    try:
        resp = requests.get(api_url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        data = clean_api_response(data)   # 🔄 Replace branding fields
        user_data["total_searches"] = user_data.get("total_searches", 0) + 1
        update_user(user_id, user_data)
        return True, f"✅ Search completed! Used {cost_type}. Remaining free today: {2 - user_data.get('free_used_today',0)}, Coin balance: {user_data.get('balance',0)}", cost_type, data
    except Exception as e:
        return False, f"❌ API error: {str(e)}. No charge for this attempt.", None, None

# ================= RENDER HTTP HEALTH SERVER =================
def run_http_server():
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Bot is running!")

        def log_message(self, format, *args):
            pass

    port = int(os.environ.get("PORT", 10000))
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    print(f"HTTP health server listening on port {port}")
    server.serve_forever()


# ================= MAIN BOT LOOP =================
def main():
    if not BOT_TOKEN:
        print("FATAL: BOT_TOKEN is empty.")
        return

    threading.Thread(target=run_http_server, daemon=True).start()

    bot_username = get_bot_username()
    print(f"Bot username: @{bot_username}")

    expecting_phone = set()
    expecting_redeem = set()
    admin_gen_state = {}
    admin_ban_state = {}
    admin_balance_state = {}
    admin_status_state = {}
    last_update_id = 0
    print("Bot started. Polling for updates...")

    while True:
        try:
            updates = get_updates(offset=last_update_id + 1 if last_update_id else None)
        except Exception as e:
            print(f"[ERROR] Polling failed: {e}")
            time.sleep(2)
            continue

        for update in updates:
            if "update_id" in update:
                last_update_id = update["update_id"]

            # ========== CALLBACK QUERIES ==========
            if "callback_query" in update:
                callback = update["callback_query"]
                callback_id = callback["id"]
                chat_id = callback["message"]["chat"]["id"]
                user_id = callback["from"]["id"]
                data = callback["data"]

                if data == "verify_join":
                    if check_user_verification(user_id):
                        user_data = get_user(user_id)
                        free_left = 2 - check_free_searches(user_data, user_id)
                        welcome_msg = (
                            f"🔥 𝐃𝐑𝐈𝐅𝐓 𝐍𝐔𝐌𝐁𝐄𝐑 𝐈𝐍𝐅𝐎 𝐁𝐎𝐓 𝐋𝐈𝐕𝐄 🚀\n\n"
                            f"👑 𝐎𝐖𝐍𝐄𝐑 ➤ @DGDRIFT\n\n"
                            f"👋 Welcome {user_data.get('first_name', '')}!\n"
                            f"💰 Coins: {user_data['balance']}\n"
                            f"🆓 Daily free searches left: {free_left}\n\n"
                            "Use the buttons below to search numbers.\n"
                            "First 2 searches each day are free! Afterwards each search costs 1 coin."
                        )
                        send_message(chat_id, welcome_msg, reply_markup=reply_keyboard)
                    else:
                        send_message(chat_id, "❌ You haven't joined the channel yet. Please join using the links above and then click verify again.")
                    tg_api_request("answerCallbackQuery", {"callback_query_id": callback_id})
                    continue

                if user_id != OWNER_ID:
                    send_message(chat_id, "⛔ You are not authorized to use the admin panel.")
                    tg_api_request("answerCallbackQuery", {"callback_query_id": callback_id})
                    continue

                if data == "gen_code":
                    admin_gen_state[chat_id] = True
                    send_message(chat_id, "💰 Enter the **coin amount** for the new redeem code (integer, e.g., `10`):", parse_mode="Markdown")
                elif data == "list_codes":
                    active_codes = list_active_codes()
                    send_message(chat_id, active_codes, parse_mode="Markdown")
                elif data == "user_stats":
                    total_users, total_coins, total_searches = get_user_stats()
                    stats_msg = f"📊 **User Statistics**\n\n👥 Total users: {total_users}\n💰 Total coins in circulation: {total_coins}\n🔍 Total searches performed: {total_searches}"
                    send_message(chat_id, stats_msg, parse_mode="Markdown")
                elif data == "full_status":
                    full_status_msg = get_full_status()
                    send_message(chat_id, full_status_msg, parse_mode="Markdown")
                elif data == "ban_user":
                    admin_ban_state[chat_id] = True
                    send_message(chat_id, "🔨 Send the **User ID** to ban/unban:")
                elif data == "balance_user":
                    admin_balance_state[chat_id] = {"target": None, "amount": None}
                    send_message(chat_id, "💰 Send the **User ID** to adjust balance:")
                elif data == "status_user":
                    admin_status_state[chat_id] = True
                    send_message(chat_id, "ℹ️ Send the **User ID** to view full details:")
                elif data == "close_admin":
                    send_message(chat_id, "Admin panel closed.")
                tg_api_request("answerCallbackQuery", {"callback_query_id": callback_id})
                continue

            # ========== NORMAL MESSAGES ==========
            message = update.get("message")
            if not message:
                continue

            chat_id = message["chat"]["id"]
            chat_type = message["chat"].get("type")
            text = message.get("text", "").strip()
            user_id = message["from"]["id"]
            first_name = message["from"].get("first_name", "")
            last_name = message["from"].get("last_name", "")
            full_name = f"{first_name} {last_name}".strip() if last_name else first_name
            username = message["from"].get("username", "")

            user_data = get_user(user_id)
            is_banned = user_data.get("banned", False) if user_data else False

            if is_banned and user_id != OWNER_ID:
                if text == "/start":
                    send_message(chat_id, "🚫 You have been banned from using this bot. Contact @DGDRIFT for assistance.")
                else:
                    send_message(chat_id, "🚫 You are banned. You cannot use this bot.")
                continue

            if user_data is None:
                user_data = {
                    "balance": 0,
                    "total_searches": 0,
                    "referred_by": None,
                    "first_name": first_name,
                    "last_name": last_name,
                    "username": username,
                    "free_date": datetime.now().strftime("%Y-%m-%d"),
                    "free_used_today": 0,
                    "banned": False,
                    "last_active_date": None,
                    "verified": False
                }
                update_user(user_id, user_data)
            else:
                if (user_data.get("first_name") != first_name or 
                    user_data.get("last_name") != last_name or 
                    user_data.get("username") != username):
                    user_data["first_name"] = first_name
                    user_data["last_name"] = last_name
                    user_data["username"] = username
                    update_user(user_id, user_data)

            update_last_active(user_id)

            # ========== ADMIN STATE MACHINES ==========
            if chat_id in admin_gen_state:
                try:
                    coin_value = int(text)
                    if coin_value <= 0:
                        raise ValueError
                    code = generate_redeem_code(user_id, coin_value)
                    send_message(chat_id, f"🎁 **New Redeem Code Created**\n\nCode: `{code}`\nValue: {coin_value} coins\nShare this code with users.")
                except ValueError:
                    send_message(chat_id, "❌ Invalid amount. Please enter a positive integer (e.g., `10`).")
                del admin_gen_state[chat_id]
                continue

            if chat_id in admin_ban_state:
                try:
                    target_id = int(text)
                    success, msg = ban_user(user_id, target_id)
                    send_message(chat_id, msg)
                except ValueError:
                    send_message(chat_id, "❌ Invalid User ID. Please send a numeric ID.")
                del admin_ban_state[chat_id]
                continue

            if chat_id in admin_balance_state:
                state = admin_balance_state[chat_id]
                if state["target"] is None:
                    try:
                        target_id = int(text)
                        state["target"] = target_id
                        send_message(chat_id, "Now send the **amount** to add (positive) or remove (negative), e.g., `+10` or `-5`:")
                    except ValueError:
                        send_message(chat_id, "❌ Invalid User ID. Try again using the admin panel.")
                        del admin_balance_state[chat_id]
                    continue
                else:
                    try:
                        amount = int(text)
                        success, msg = adjust_balance(user_id, state["target"], amount)
                        send_message(chat_id, msg)
                    except ValueError:
                        send_message(chat_id, "❌ Invalid amount. Must be an integer.")
                    del admin_balance_state[chat_id]
                continue

            if chat_id in admin_status_state:
                try:
                    target_id = int(text)
                    success, msg = get_user_status(user_id, target_id)
                    send_message(chat_id, msg, parse_mode="Markdown")
                except ValueError:
                    send_message(chat_id, "❌ Invalid User ID. Please send a numeric ID.")
                del admin_status_state[chat_id]
                continue

            # ========== VERIFICATION CHECK ==========
            if text != "/start" and user_id != OWNER_ID:
                if not check_user_verification(user_id):
                    send_verification_prompt(chat_id, user_id)
                    continue

            # ========== COMMAND: /search ==========
            if text.startswith("/search"):
                parts = text.split(maxsplit=1)
                if len(parts) != 2:
                    send_message(chat_id, "Usage: `/search <10-digit number>`", parse_mode="Markdown")
                else:
                    number = parts[1].strip()
                    if number.isdigit() and len(number) == 10:
                        success, msg, cost_type, result = perform_search(user_id, chat_id, number, user_data)
                        if success:
                            if chat_type in ["group", "supergroup"]:
                                save_and_send_result(chat_id, user_id, number, result, cost_type)
                            else:
                                pretty_json = json.dumps(result, indent=2, ensure_ascii=False)
                                send_message(chat_id, f"<pre>{pretty_json}</pre>\n\n{msg}", parse_mode="HTML")
                        else:
                            send_message(chat_id, msg)
                    else:
                        send_message(chat_id, "❌ Please provide a **10-digit** number (digits only).")
                continue

            # ========== /start COMMAND ==========
            if text.startswith("/start"):
                parts = text.split()
                ref_uid = None
                if len(parts) > 1:
                    param = parts[1]
                    if param.startswith("ref_"):
                        ref_uid = param[4:]
                    elif param.isdigit():
                        ref_uid = param
                    if ref_uid:
                        try:
                            ref_uid = int(ref_uid)
                        except:
                            ref_uid = None

                if ref_uid and ref_uid != user_id and user_data.get("referred_by") is None:
                    referrer_data = get_user(ref_uid)
                    if referrer_data:
                        user_data["referred_by"] = ref_uid
                        referrer_data["balance"] = referrer_data.get("balance", 0) + 1
                        update_user(ref_uid, referrer_data)
                        update_user(user_id, user_data)
                        send_message(chat_id, f"✅ You were referred! Your referrer @{referrer_data.get('username', ref_uid)} got +1 coin.")
                        send_message(ref_uid, f"🎉 Someone used your referral link!\nYou received +1 coin.\nCurrent balance: {referrer_data['balance']} coins.")

                if check_user_verification(user_id):
                    free_left = 2 - check_free_searches(user_data, user_id)
                    welcome_msg = (
                        f"🔥 𝐃𝐑𝐈𝐅𝐓 𝐍𝐔𝐌𝐁𝐄𝐑 𝐈𝐍𝐅𝐎 𝐁𝐎𝐓 𝐋𝐈𝐕𝐄 🚀\n\n"
                        f"👑 𝐎𝐖𝐍𝐄𝐑 ➤ @DGDRIFT\n\n"
                        f"👋 Welcome {full_name}!\n"
                        f"💰 Coins: {user_data['balance']}\n"
                        f"🆓 Daily free searches left: {free_left}\n\n"
                        "Use the buttons below to search numbers.\n"
                        "First 2 searches each day are free! Afterwards each search costs 1 coin."
                    )
                    if chat_type in ["group", "supergroup"]:
                        send_message(chat_id, welcome_msg)
                    else:
                        send_message(chat_id, welcome_msg, reply_markup=reply_keyboard)
                else:
                    send_verification_prompt(chat_id, user_id)
                expecting_phone.discard(chat_id)
                expecting_redeem.discard(chat_id)
                continue

            # ========== BUTTON HANDLING (private only) ==========
            if chat_type not in ["group", "supergroup"]:
                if text == "🔍 𝐒𝐄𝐀𝐑𝐂𝐇 𝐍𝐔𝐌𝐁𝐄𝐑":
                    expecting_redeem.discard(chat_id)
                    expecting_phone.discard(chat_id)
                    free_used = check_free_searches(user_data, user_id)
                    free_left = 2 - free_used
                    if free_left > 0:
                        expecting_phone.add(chat_id)
                        send_message(chat_id, f"🆓 You have {free_left} free search(es) left today.\nSend 10 digit mobile number:")
                    else:
                        if user_data.get("balance", 0) >= 1:
                            expecting_phone.add(chat_id)
                            send_message(chat_id, f"⚠️ No free searches left. This search will cost 1 coin.\nSend 10 digit mobile number:")
                        else:
                            send_message(chat_id, "❌ No free searches left and insufficient coins. Earn coins by referring friends or using a redeem code!")

                elif text == "📢 𝐑𝐄𝐅𝐄𝐑 & 𝐄𝐀𝐑𝐍":
                    expecting_phone.discard(chat_id)
                    expecting_redeem.discard(chat_id)
                    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
                    msg = (f"📢 **Refer & Earn**\n\n"
                           f"Share your referral link:\n`{ref_link}`\n\n"
                           f"For each friend who joins via your link, you get **1 coin**.\n"
                           f"1 coin = 1 phone search (after free daily limit).\n\n"
                           f"Your current balance: {user_data['balance']} coins.")
                    send_message(chat_id, msg, parse_mode="Markdown")

                elif text == "👤 𝐏𝐑𝐎𝐅𝐈𝐋𝐄":
                    expecting_phone.discard(chat_id)
                    expecting_redeem.discard(chat_id)
                    user_data = get_user(user_id)
                    if not user_data:
                        send_message(chat_id, "❌ Error loading profile. Please try /start again.")
                        continue

                    all_users = load_user_data()
                    referral_count = 0
                    for uid, data in all_users.items():
                        if data.get("referred_by") == user_id:
                            referral_count += 1

                    free_used = check_free_searches(user_data, user_id)
                    free_left = 2 - free_used

                    profile_msg = (
                        f"👤 PROFILE\n\n"
                        f"📛 Full Name: {full_name}\n"
                        f"🔖 Username: @{username if username else 'None'}\n"
                        f"🆔 User ID: {user_id}\n"
                        f"👥 Total Referrals: {referral_count}\n"
                        f"💰 Coin Balance: {user_data.get('balance', 0)}\n"
                        f"🔍 Total Searches: {user_data.get('total_searches', 0)}\n"
                        f"🆓 Free searches left today: {free_left}/2"
                    )
                    send_message(chat_id, profile_msg)

                elif text == "🎫 𝐑𝐄𝐃𝐄𝐄𝐌 𝐂𝐎𝐃𝐄":
                    expecting_phone.discard(chat_id)
                    expecting_redeem.add(chat_id)
                    send_message(chat_id, "🔑 Please send the redeem code (e.g., `ABCD1234`):", parse_mode="Markdown")

                elif text == "📢 𝐔𝐏𝐃𝐀𝐓𝐄 𝐂𝐇𝐀𝐍𝐍𝐄𝐋":
                    expecting_phone.discard(chat_id)
                    expecting_redeem.discard(chat_id)
                    keyboard = {
                        "inline_keyboard": [
                            [{"text": "Chirag Channel", "url": "https://t.me/Chirag_48776"}]
                        ]
                    }
                    send_message(chat_id, "📢 **Our Channel**\n\nClick below to join:", reply_markup=keyboard, parse_mode="Markdown")

                elif text == "👑 𝐀𝐃𝐌𝐈𝐍 𝐏𝐀𝐍𝐄𝐋":
                    expecting_phone.discard(chat_id)
                    expecting_redeem.discard(chat_id)
                    if user_id == OWNER_ID:
                        send_admin_panel(chat_id)
                    else:
                        send_message(chat_id, "⛔ You are not the bot owner. This panel is restricted.")

                elif chat_id in expecting_redeem:
                    success, msg = redeem_code(user_id, text)
                    send_message(chat_id, msg)
                    expecting_redeem.discard(chat_id)

                elif chat_id in expecting_phone:
                    if text.isdigit() and len(text) == 10:
                        success, msg, cost_type, result = perform_search(user_id, chat_id, text, user_data)
                        if success:
                            pretty_json = json.dumps(result, indent=2, ensure_ascii=False)
                            send_message(chat_id, f"<pre>{pretty_json}</pre>\n\n{msg}", parse_mode="HTML")
                        else:
                            send_message(chat_id, msg)
                        expecting_phone.discard(chat_id)
                    else:
                        send_message(chat_id, "❌ Invalid input. Please send a **10-digit** mobile number (digits only).")

                else:
                    send_message(chat_id, "Please use the buttons below.", reply_markup=reply_keyboard)

        time.sleep(1)

if __name__ == "__main__":
    main()
