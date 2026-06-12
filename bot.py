import os
import time
import threading
import asyncio
import telebot
import random
import requests
import pandas as pd
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from telethon import TelegramClient, events

# =========================
# 🔐 ENV VARIABLES
# =========================
TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
PHONE = os.getenv("PHONE")
AV_KEY = os.getenv("AV_KEY")
TON_ADDRESS = "UQB69rdZZvxfYis4lXw_YIIxq9brv8dCRCP6pLrRh9MJupTw"

if not TOKEN:
    raise Exception("BOT_TOKEN is not set")

bot = telebot.TeleBot(TOKEN)
bot.remove_webhook()
time.sleep(1)

# =========================
# 🌐 KEEP ALIVE
# =========================
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"AbdeysenBot is running!")
    def log_message(self, *args):
        pass

def run_server():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()

threading.Thread(target=run_server, daemon=True).start()

# =========================
# 📡 CHANNELS
# =========================
CHANNEL = "@abdeysenfx"
CHANNEL_LINK = "https://t.me/abdeysenfx"
SOURCE_CHANNELS = ["binance_announcements", "cryptoomonarch"]

# =========================
# 📊 ASSETS
# =========================
forex_pairs = [
    "EUR/USD", "GBP/USD", "USD/JPY",
    "AUD/USD", "USD/CAD", "NZD/USD",
    "EUR/GBP", "USD/CHF"
]
otc_pairs = [
    "EUR/USD-OTC", "GBP/USD-OTC", "USD/JPY-OTC",
    "AUD/USD-OTC", "EUR/GBP-OTC", "USD/CAD-OTC"
]
metals_pairs = ["XAU/USD", "XAG/USD"]

# =========================
# 🖼 IMAGES
# =========================
BUY_IMG = "https://i.ibb.co/H8Nb16c/file-00000000c85071fda5bf3958ff7106f5-1.jpg"
SELL_IMG = "https://i.ibb.co/mrC2CH16/file-00000000c85071fda5bf3958ff7106f5-2.jpg"

# =========================
# 💾 DATABASE (IN MEMORY)
# =========================
users_db = {}
vip_db = {}
signal_count_db = {}
pending_payments = {}

def get_user(user_id):
    if user_id not in users_db:
        users_db[user_id] = {"id": user_id, "joined": datetime.utcnow()}
    return users_db[user_id]

def is_vip(user_id):
    if user_id not in vip_db:
        return False
    expiry = vip_db[user_id]["expiry"]
    if datetime.utcnow() > expiry:
        del vip_db[user_id]
        return False
    return True

def add_vip(user_id, plan):
    days = 7 if plan == "weekly" else 30
    expiry = datetime.utcnow() + timedelta(days=days)
    vip_db[user_id] = {"expiry": expiry, "plan": plan}

def increment_signals(user_id):
    signal_count_db[user_id] = signal_count_db.get(user_id, 0) + 1

def get_leaderboard():
    sorted_users = sorted(signal_count_db.items(), key=lambda x: x[1], reverse=True)
    return sorted_users[:10]

# =========================
# ✅ SUBSCRIPTION CHECK
# =========================
def is_subscribed(user_id):
    try:
        member = bot.get_chat_member(CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

def ask_to_subscribe(chat_id):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK))
    markup.add(telebot.types.InlineKeyboardButton("✅ I Have Joined", callback_data="check_sub"))
    bot.send_message(
        chat_id,
        "⚠️ *ACCESS DENIED*\n\n"
        "You must join our channel first!\n\n"
        f"👉 {CHANNEL_LINK}\n\n"
        "After joining tap ✅ I Have Joined",
        parse_mode="Markdown",
        reply_markup=markup
    )

# =========================
# 📊 FETCH DATA
# =========================
TIMEFRAME_MAP = {
    "M1": "1min", "M5": "5min",
    "M15": "15min", "M30": "30min", "H1": "60min",
    "10s": "1min", "20s": "1min", "30s": "1min"
}

def get_data(symbol, timeframe="M5"):
    try:
        clean = symbol.replace("-OTC", "").replace("/", "")
        interval = TIMEFRAME_MAP.get(timeframe, "5min")
        from_sym = clean[:3]
        to_sym = clean[3:]

        url = (
            f"https://www.alphavantage.co/query"
            f"?function=FX_INTRADAY"
            f"&from_symbol={from_sym}"
            f"&to_symbol={to_sym}"
            f"&interval={interval}"
            f"&outputsize=compact"
            f"&apikey={AV_KEY}"
        )

        response = requests.get(url, timeout=10)
        data = response.json()
        key = f"Time Series FX ({interval})"
        if key not in data:
            return None

        df = pd.DataFrame.from_dict(data[key], orient="index")
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        df.columns = ["Open", "High", "Low", "Close"]
        df = df.astype(float)
        return df

    except Exception as e:
        print(f"Data error: {e}")
        return None

# =========================
# 🕯 CANDLE DECOMPOSITION
# (For 10s/20s/30s)
# =========================
def candle_decomposition(df, seconds):
    last = df.iloc[-1]
    prev = df.iloc[-2]

    body = last["Close"] - last["Open"]
    candle_range = last["High"] - last["Low"]
    momentum = last["Close"] - prev["Close"]
    velocity = body / candle_range if candle_range > 0 else 0

    # Price pressure
    buy_pressure = (last["Close"] - last["Low"]) / candle_range if candle_range > 0 else 0.5
    sell_pressure = (last["High"] - last["Close"]) / candle_range if candle_range > 0 else 0.5

    score = 0

    # Momentum direction
    if momentum > 0:
        score += 2
    else:
        score -= 2

    # Velocity strength
    if velocity > 0.6:
        score += 2 if body > 0 else -2
    elif velocity > 0.3:
        score += 1 if body > 0 else -1

    # Buy/Sell pressure
    if buy_pressure > 0.6:
        score += 2
    elif sell_pressure > 0.6:
        score -= 2

    # Time decay factor for ultra short
    decay = seconds / 60
    adjusted_score = score * (1 - decay * 0.3)

    return adjusted_score

# =========================
# 📊 INDICATORS
# =========================
def calculate_indicators(df):
    score = 0
    close = df["Close"]
    high = df["High"]
    low = df["Low"]

    # RSI
    if len(df) >= 14:
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = -delta.clip(upper=0).rolling(14).mean()
        rs = gain / loss
        rsi = (100 - (100 / (1 + rs))).iloc[-1]
        if rsi < 40: score += 2
        elif rsi < 45: score += 1
        elif rsi > 60: score -= 2
        elif rsi > 55: score -= 1

    # EMA 3/8
    if len(df) >= 8:
        ema3 = close.ewm(span=3).mean().iloc[-1]
        ema8 = close.ewm(span=8).mean().iloc[-1]
        score += 2 if ema3 > ema8 else -2

    # Stochastic
    if len(df) >= 14:
        lowest = low.rolling(14).min()
        highest = high.rolling(14).max()
        stoch = (100 * (close - lowest) / (highest - lowest)).iloc[-1]
        if stoch < 20: score += 2
        elif stoch < 35: score += 1
        elif stoch > 80: score -= 2
        elif stoch > 65: score -= 1

    # Bollinger Bands
    if len(df) >= 20:
        sma = close.rolling(20).mean()
        std = close.rolling(20).std()
        upper = (sma + std * 2).iloc[-1]
        lower_b = (sma - std * 2).iloc[-1]
        last_close = close.iloc[-1]
        if last_close < lower_b: score += 2
        elif last_close > upper: score -= 2

    return score

# =========================
# 🕯 CANDLE PATTERNS
# =========================
def detect_patterns(df):
    score = 0
    last = df.iloc[-1]
    prev = df.iloc[-2]
    body_last = abs(last["Close"] - last["Open"])
    upper_wick = last["High"] - max(last["Close"], last["Open"])
    lower_wick = min(last["Close"], last["Open"]) - last["Low"]
    total = last["High"] - last["Low"]

    if (prev["Close"] < prev["Open"] and last["Close"] > last["Open"] and
            last["Close"] > prev["Open"] and last["Open"] < prev["Close"]):
        score += 3

    if (prev["Close"] > prev["Open"] and last["Close"] < last["Open"] and
            last["Close"] < prev["Open"] and last["Open"] > prev["Close"]):
        score -= 3

    if lower_wick > body_last * 2 and upper_wick < body_last:
        score += 2
    if upper_wick > body_last * 2 and lower_wick < body_last:
        score -= 2
    if total > 0 and body_last / total > 0.6:
        score += 1 if last["Close"] > last["Open"] else -1

    return score

# =========================
# 💬 AI COMMENTARY
# =========================
def get_commentary(score, timeframe, symbol):
    abs_score = abs(score)
    direction = "bullish" if score >= 0 else "bearish"

    if abs_score >= 8:
        strength = "very strong"
    elif abs_score >= 5:
        strength = "strong"
    elif abs_score >= 3:
        strength = "moderate"
    else:
        strength = "weak"

    comments = {
        "bullish": [
            f"📈 {strength.title()} buying pressure detected on {symbol}",
            f"⚡ Bulls are in control — {strength} upward momentum",
            f"🟢 Price action showing {strength} bullish bias on {timeframe}",
        ],
        "bearish": [
            f"📉 {strength.title()} selling pressure detected on {symbol}",
            f"⚡ Bears are in control — {strength} downward momentum",
            f"🔴 Price action showing {strength} bearish bias on {timeframe}",
        ]
    }
    return random.choice(comments[direction])

# =========================
# 🧠 SIGNAL ENGINE
# =========================
def generate_ai_signal(symbol, timeframe, user_id=None):
    is_otc = "OTC" in symbol
    is_ultra = timeframe in ["10s", "20s", "30s"]
    df = get_data(symbol, timeframe)

    def build_text(direction, confidence, commentary):
        vip_badge = "💎 VIP SIGNAL" if is_ultra else ""
        return f"""
🌑 ABDEYSENFX AI SIGNAL 🌑
{vip_badge}
{"🔴 OTC PAIR" if is_otc else ""}

Asset: {symbol}
Timeframe: {timeframe}
Direction: {direction}
Confidence: {confidence}%

{commentary}

Expiry: {timeframe}
Time: {datetime.utcnow().strftime('%H:%M:%S UTC')}

⚡ AI Engine Active
""".strip()

    if df is None or len(df) < 5:
        direction = random.choice(["HIGHER ↑ (CALL)", "LOWER ↓ (PUT)"])
        img = BUY_IMG if "HIGHER" in direction else SELL_IMG
        commentary = get_commentary(1 if "HIGHER" in direction else -1, timeframe, symbol)
        return build_text(direction, 65, commentary), img

    try:
        score = 0
        score += calculate_indicators(df)
        if len(df) >= 2:
            score += detect_patterns(df)

        # Ultra short timeframe — use candle decomposition
        if is_ultra:
            seconds = int(timeframe.replace("s", ""))
            decomp_score = candle_decomposition(df, seconds)
            score = score * 0.4 + decomp_score * 0.6
        else:
            # Multi TF confirm
            confirm_tf = "M5" if timeframe == "M1" else "M15"
            df2 = get_data(symbol, confirm_tf)
            if df2 is not None and len(df2) >= 5:
                score += 1 if calculate_indicators(df2) > 0 else -1

        direction = "HIGHER ↑ (CALL)" if score >= 0 else "LOWER ↓ (PUT)"
        img = BUY_IMG if score >= 0 else SELL_IMG
        confidence = max(62, min(95, 58 + abs(score) * 5))
        commentary = get_commentary(score, timeframe, symbol)

        if user_id:
            increment_signals(user_id)

        return build_text(direction, confidence, commentary), img

    except Exception as e:
        print(f"Signal error: {e}")
        direction = random.choice(["HIGHER ↑ (CALL)", "LOWER ↓ (PUT)"])
        img = BUY_IMG if "HIGHER" in direction else SELL_IMG
        commentary = get_commentary(1 if "HIGHER" in direction else -1, timeframe, symbol)
        return build_text(direction, 65, commentary), img

# =========================
# 📡 POST TO CHANNEL
# =========================
def post_to_channel(text, img):
    try:
        bot.send_photo(CHANNEL, img, caption=text)
    except Exception as e:
        print(f"Channel post error: {e}")

# =========================
# 💰 TON PAYMENT CHECK
# =========================
def check_ton_payment(user_id, amount_usdt):
    try:
        url = f"https://toncenter.com/api/v2/getTransactions?address={TON_ADDRESS}&limit=10"
        response = requests.get(url, timeout=10)
        data = response.json()

        if not data.get("ok"):
            return False

        transactions = data.get("result", [])
        for tx in transactions:
            msg = tx.get("in_msg", {})
            value = int(msg.get("value", 0)) / 1e9
            comment = msg.get("message", "")

            if str(user_id) in comment and value >= amount_usdt * 0.95:
                return True

        return False
    except Exception as e:
        print(f"TON check error: {e}")
        return False

# =========================
# 📚 COURSE CONTENT
# =========================
COURSE = {
    "1": {
        "title": "Chapter 1: The Power of Thought",
        "content": """
📚 *WEALTH MINDSET COURSE*
*Chapter 1: The Power of Thought*

Everything begins in the mind. Napoleon Hill wrote in Think and Grow Rich that *thoughts are things* — and when mixed with definiteness of purpose and burning desire, they can be transformed into riches.

💡 *Key Lesson:*
Your dominant thoughts become your reality. What you consistently think about, you move toward.

🔑 *Exercise:*
Write down ONE financial goal. Read it every morning and night for 7 days. Feel it as already real.

_"Whatever the mind can conceive and believe, it can achieve."_
— Napoleon Hill
        """.strip()
    },
    "2": {
        "title": "Chapter 2: Desire — The Starting Point",
        "content": """
📚 *WEALTH MINDSET COURSE*
*Chapter 2: Desire — The Starting Point of All Achievement*

A weak wish will not bring wealth. You need a burning, obsessive desire — a definiteness of purpose that consumes your thoughts.

💡 *Key Lesson:*
6 Steps to Turn Desire into Gold:
1. Fix exact amount of money you want
2. Decide what you'll give in return
3. Set a definite date
4. Create a plan and start immediately
5. Write it all down clearly
6. Read it aloud twice daily

🔑 *Law of Attraction:*
The universe responds to intensity of feeling, not just words. FEEL wealthy now.

_"Desire is the starting point of all achievement."_
— Napoleon Hill
        """.strip()
    },
    "3": {
        "title": "Chapter 3: Faith and Visualization",
        "content": """
📚 *WEALTH MINDSET COURSE*
*Chapter 3: Faith and Visualization*

Faith is the head chemist of the mind. When faith is blended with thought, the subconscious mind picks it up and translates it into its physical equivalent.

💡 *Key Lesson:*
Visualization is not daydreaming — it is mental rehearsal. See yourself already having what you want in vivid detail.

🔑 *Daily Practice:*
Spend 5 minutes every morning seeing your financial goal as complete. Feel the emotions. Use all your senses.

_"Faith is the only known antidote for failure."_
— Napoleon Hill
        """.strip()
    },
    "4": {
        "title": "Chapter 4: Law of Attraction",
        "content": """
📚 *WEALTH MINDSET COURSE*
*Chapter 4: The Law of Attraction*

The Law of Attraction states that like attracts like. Your thoughts emit a frequency and the universe matches that frequency with experiences.

💡 *3 Steps:*
1. ASK — Be specific about what you want
2. BELIEVE — Act as if it's already yours
3. RECEIVE — Be open and grateful

🔑 *Money Frequency:*
Poverty thinking attracts poverty.
Abundance thinking attracts abundance.
Change your self-talk about money immediately.

_"You are a living magnet. What you attract into your life is in harmony with your dominant thoughts."_
— Brian Tracy
        """.strip()
    },
    "5": {
        "title": "Chapter 5: Money Mindset",
        "content": """
📚 *WEALTH MINDSET COURSE*
*Chapter 5: Money Mindset*

Rich people think differently about money. They see money as a tool, a servant, and a result of value creation.

💡 *Rich vs Poor Mindset:*
❌ Poor: "I can't afford it"
✅ Rich: "How can I afford it?"

❌ Poor: Money is the root of evil
✅ Rich: Money amplifies who you are

❌ Poor: Play it safe
✅ Rich: Calculate risks and take action

🔑 *Affirmations:*
Say daily: "Money flows to me easily and frequently. I am worthy of abundance."
        """.strip()
    },
    "6": {
        "title": "Chapter 6: Taking Action",
        "content": """
📚 *WEALTH MINDSET COURSE*
*Chapter 6: Taking Action*

Knowledge without action is worthless. The final step is decisive, persistent action toward your goal every single day.

💡 *Key Principle:*
Do not wait for perfect conditions. Start where you are, with what you have.

🔑 *The 1% Rule:*
Improve by just 1% every day. In one year you will be 37x better than when you started.

🏆 *Final Message:*
You now have the mindset. Combine it with your trading signals, stay disciplined, manage risk, and wealth WILL follow.

_"The way to get started is to quit talking and begin doing."_
— Walt Disney

✅ Course Complete! Keep this knowledge alive daily.
        """.strip()
    }
}

# =========================
# 🖥 MENUS
# =========================
def main_menu(user_id):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🚀 Forex Signal", "🥇 Metals Signal")
    if is_vip(user_id):
        markup.add("💎 VIP Signals", "📚 Course")
    else:
        markup.add("💎 Get VIP", "📚 Course Preview")
    markup.add("🏆 Leaderboard", "❓ Help")
    return markup

def timeframe_menu(user_id):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("M1", "M5", "M15")
    markup.add("M30", "H1")
    markup.add("🔙 Back")
    return markup

def vip_timeframe_menu():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("⚡ 10s", "⚡ 20s", "⚡ 30s")
    markup.add("M1", "M5", "M15")
    markup.add("M30", "H1")
    markup.add("🔙 Back")
    return markup

def vip_payment_menu():
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("Weekly — $5 USDT", callback_data="pay_weekly"))
    markup.add(telebot.types.InlineKeyboardButton("Monthly — $15 USDT", callback_data="pay_monthly"))
    return markup

def course_menu():
    markup = telebot.types.InlineKeyboardMarkup()
    for key, val in COURSE.items():
        markup.add(telebot.types.InlineKeyboardButton(val["title"], callback_data=f"course_{key}"))
    return markup

# =========================
# USER STATE
# =========================
user_state = {}

# =========================
# START
# =========================
@bot.message_handler(commands=['start'])
def start(message):
    if not is_subscribed(message.from_user.id):
        ask_to_subscribe(message.chat.id)
        return
    get_user(message.from_user.id)
    vip_badge = "💎 VIP Member" if is_vip(message.from_user.id) else "Free Member"
    bot.send_message(
        message.chat.id,
        f"🌑 *ABDEYSENBOT AI*\n\n"
        f"Welcome! Status: {vip_badge}\n\n"
        f"Select option below 👇",
        parse_mode="Markdown",
        reply_markup=main_menu(message.from_user.id)
    )

# =========================
# SUBSCRIPTION CALLBACK
# =========================
@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_subscription(call):
    if is_subscribed(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ Access Granted!")
        bot.send_message(
            call.message.chat.id,
            "✅ *Welcome to AbdeysenFX!*\n\nSelect option below 👇",
            parse_mode="Markdown",
            reply_markup=main_menu(call.from_user.id)
        )
    else:
        bot.answer_callback_query(call.id, "❌ Not joined yet!", show_alert=True)

# =========================
# FOREX SIGNAL
# =========================
@bot.message_handler(func=lambda m: m.text == "🚀 Forex Signal")
def forex(message):
    if not is_subscribed(message.from_user.id):
        ask_to_subscribe(message.chat.id)
        return
    user_state[message.chat.id] = "forex"
    bot.send_message(message.chat.id, "⏱ Select timeframe:", reply_markup=timeframe_menu(message.from_user.id))

# =========================
# METALS SIGNAL
# =========================
@bot.message_handler(func=lambda m: m.text == "🥇 Metals Signal")
def metals(message):
    if not is_subscribed(message.from_user.id):
        ask_to_subscribe(message.chat.id)
        return
    user_state[message.chat.id] = "metals"
    bot.send_message(message.chat.id, "⏱ Select timeframe:", reply_markup=timeframe_menu(message.from_user.id))

# =========================
# VIP SIGNALS
# =========================
@bot.message_handler(func=lambda m: m.text == "💎 VIP Signals")
def vip_signals(message):
    if not is_vip(message.from_user.id):
        bot.send_message(message.chat.id, "❌ VIP only! Tap 💎 Get VIP to upgrade.")
        return
    user_state[message.chat.id] = "vip_forex"
    bot.send_message(message.chat.id, "⚡ VIP Timeframe:", reply_markup=vip_timeframe_menu())

# =========================
# GET VIP
# =========================
@bot.message_handler(func=lambda m: m.text == "💎 Get VIP")
def get_vip(message):
    bot.send_message(
        message.chat.id,
        "💎 *UPGRADE TO VIP*\n\n"
        "✅ 10s, 20s, 30s ultra scalp signals\n"
        "✅ All timeframes\n"
        "✅ AI market commentary\n"
        "✅ Wealth mindset course\n"
        "✅ Hot picks\n\n"
        "Select your plan:",
        parse_mode="Markdown",
        reply_markup=vip_payment_menu()
    )

# =========================
# PAYMENT CALLBACKS
# =========================
@bot.callback_query_handler(func=lambda call: call.data in ["pay_weekly", "pay_monthly"])
def handle_payment(call):
    plan = "weekly" if call.data == "pay_weekly" else "monthly"
    amount = 5 if plan == "weekly" else 15
    user_id = call.from_user.id

    pending_payments[user_id] = {"plan": plan, "amount": amount}

    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        f"💰 *PAYMENT INSTRUCTIONS*\n\n"
        f"Send *{amount} USDT* on TON network to:\n\n"
        f"`{TON_ADDRESS}`\n\n"
        f"⚠️ *IMPORTANT:*\n"
        f"In the memo/comment field write your Telegram ID:\n"
        f"`{user_id}`\n\n"
        f"After sending tap the button below 👇",
        parse_mode="Markdown",
        reply_markup=telebot.types.InlineKeyboardMarkup().add(
            telebot.types.InlineKeyboardButton("✅ I Have Paid", callback_data=f"verify_{plan}")
        )
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("verify_"))
def verify_payment(call):
    user_id = call.from_user.id
    plan = call.data.replace("verify_", "")
    payment_info = pending_payments.get(user_id)

    if not payment_info:
        bot.answer_callback_query(call.id, "❌ No pending payment found.", show_alert=True)
        return

    bot.answer_callback_query(call.id, "🔍 Checking payment...")
    bot.send_message(call.message.chat.id, "⏳ Verifying your payment on TON blockchain...")

    amount = payment_info["amount"]
    if check_ton_payment(user_id, amount):
        add_vip(user_id, plan)
        pending_payments.pop(user_id, None)
        expiry = vip_db[user_id]["expiry"].strftime("%Y-%m-%d")
        bot.send_message(
            call.message.chat.id,
            f"🎉 *VIP ACTIVATED!*\n\n"
            f"Plan: {plan.title()}\n"
            f"Expires: {expiry}\n\n"
            f"Welcome to the VIP family! 💎",
            parse_mode="Markdown",
            reply_markup=main_menu(user_id)
        )
    else:
        bot.send_message(
            call.message.chat.id,
            "❌ *Payment not found yet.*\n\n"
            "Make sure you:\n"
            "1. Sent the correct amount\n"
            "2. Added your Telegram ID in memo\n"
            "3. Wait 1-2 minutes and try again\n\n"
            "Contact @abdeysenfx if issue persists.",
            parse_mode="Markdown"
        )

# =========================
# TIMEFRAME HANDLER
# =========================
@bot.message_handler(func=lambda m: m.text in ["M1", "M5", "M15", "M30", "H1", "⚡ 10s", "⚡ 20s", "⚡ 30s"])
def handle_timeframe(message):
    if not is_subscribed(message.from_user.id):
        ask_to_subscribe(message.chat.id)
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    timeframe = message.text.replace("⚡ ", "")
    signal_type = user_state.get(chat_id)

    # Block ultra TF for non-VIP
    if timeframe in ["10s", "20s", "30s"] and not is_vip(user_id):
        bot.send_message(chat_id, "💎 Ultra scalp timeframes are VIP only!\nTap 💎 Get VIP to upgrade.")
        return

    if not signal_type:
        bot.send_message(chat_id, "Please select Forex or Metals first.", reply_markup=main_menu(user_id))
        return

    bot.send_message(chat_id, "⏳ Analyzing market...")

    if signal_type in ["forex", "vip_forex"]:
        all_pairs = forex_pairs + otc_pairs
        symbol = random.choice(all_pairs)
    else:
        symbol = random.choice(metals_pairs)

    text, img = generate_ai_signal(symbol, timeframe, user_id)
    bot.send_photo(chat_id, img, caption=text)
    post_to_channel(text, img)
    user_state.pop(chat_id, None)

# =========================
# COURSE
# =========================
@bot.message_handler(func=lambda m: m.text in ["📚 Course", "📚 Course Preview"])
def course(message):
    if not is_subscribed(message.from_user.id):
        ask_to_subscribe(message.chat.id)
        return

    if not is_vip(message.from_user.id):
        bot.send_message(
            message.chat.id,
            "📚 *WEALTH MINDSET COURSE*\n\n"
            "🔒 Full course is VIP only!\n\n"
            "*Preview — Chapter 1:*\n\n"
            "Everything begins in the mind. Your dominant thoughts become your reality. "
            "Napoleon Hill taught that thoughts are things — mix them with burning desire "
            "and they transform into wealth.\n\n"
            "💎 Upgrade to VIP to unlock all 6 chapters!",
            parse_mode="Markdown",
            reply_markup=telebot.types.InlineKeyboardMarkup().add(
                telebot.types.InlineKeyboardButton("💎 Get VIP Now", callback_data="pay_weekly")
            )
        )
        return

    bot.send_message(
        message.chat.id,
        "📚 *WEALTH MINDSET COURSE*\n\nSelect a chapter:",
        parse_mode="Markdown",
        reply_markup=course_menu()
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("course_"))
def show_chapter(call):
    chapter_key = call.data.replace("course_", "")
    chapter = COURSE.get(chapter_key)
    if chapter:
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            chapter["content"],
            parse_mode="Markdown"
        )

# =========================
# LEADERBOARD
# =========================
@bot.message_handler(func=lambda m: m.text == "🏆 Leaderboard")
def leaderboard(message):
    if not is_subscribed(message.from_user.id):
        ask_to_subscribe(message.chat.id)
        return

    top = get_leaderboard()
    if not top:
        bot.send_message(message.chat.id, "🏆 No signals generated yet! Be the first!")
        return

    text = "🏆 *TOP SIGNAL GENERATORS*\n\n"
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, (uid, count) in enumerate(top):
        try:
            user = bot.get_chat(uid)
            name = user.first_name or f"User{uid}"
        except:
            name = f"Trader#{uid}"
        text += f"{medals[i]} {name} — {count} signals\n"

    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# =========================
# BACK
# =========================
@bot.message_handler(func=lambda m: m.text == "🔙 Back")
def back(message):
    bot.send_message(message.chat.id, "🏠 Main Menu", reply_markup=main_menu(message.from_user.id))

# =========================
# HELP
# =========================
@bot.message_handler(func=lambda m: m.text == "❓ Help")
def help_cmd(message):
    if not is_subscribed(message.from_user.id):
        ask_to_subscribe(message.chat.id)
        return
    vip_status = "💎 VIP Active" if is_vip(message.from_user.id) else "Free Member"
    bot.send_message(
        message.chat.id,
        f"🌑 *ABDEYSENBOT AI*\n\n"
        f"Status: {vip_status}\n\n"
        f"*FREE:*\n"
        f"- Forex, OTC & Metals signals\n"
        f"- M1 to H1 timeframes\n"
        f"- AI commentary\n\n"
        f"*VIP ($5/week | $15/month):*\n"
        f"- ⚡ 10s, 20s, 30s ultra scalp\n"
        f"- All timeframes\n"
        f"- Wealth mindset course\n\n"
        f"⚠️ Educational use only",
        parse_mode="Markdown"
    )

# =========================
# 📢 TELETHON NEWS FORWARDER
# =========================
async def start_telethon():
    client = TelegramClient("abdeysen_session", API_ID, API_HASH)
    await client.start(phone=PHONE)
    print("✅ Telethon connected!")

    @client.on(events.NewMessage(chats=SOURCE_CHANNELS))
    async def handler(event):
        try:
            await client.forward_messages(CHANNEL, event.message)
            print(f"📢 Forwarded from {event.chat.username}")
        except Exception as e:
            print(f"Forward error: {e}")

    await client.run_until_disconnected()

def run_telethon():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_telethon())

threading.Thread(target=run_telethon, daemon=True).start()

# =========================
# RUN
# =========================
print("🌑 AbdeysenBot AI Running...")
bot.infinity_polling(timeout=60, long_polling_timeout=60)
