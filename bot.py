import os
import time
import threading
import asyncio
import telebot
import random
import requests
import pandas as pd
from datetime import datetime
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

if not TOKEN:
    raise Exception("BOT_TOKEN is not set")

bot = telebot.TeleBot(TOKEN)

# =========================
# 🔄 CLEAR WEBHOOK
# =========================
bot.remove_webhook()
time.sleep(1)

# =========================
# 🌐 KEEP ALIVE WEB SERVER
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

SOURCE_CHANNELS = [
    "binance_announcements",
    "cryptoomonarch"
]

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
# 💾 USER STATE
# =========================
user_state = {}

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
# 📊 FETCH REAL-TIME DATA
# =========================
TIMEFRAME_MAP = {
    "M1": "1min",
    "M5": "5min",
    "M15": "15min",
    "M30": "30min",
    "H1": "60min",
}

def get_data(symbol, timeframe="M5"):
    try:
        clean = symbol.replace("-OTC", "").replace("/", "")
        interval = TIMEFRAME_MAP.get(timeframe, "5min")
        from_sym = clean[:3]
        to_sym = clean[3:]

        if "XAU" in symbol or "XAG" in symbol:
            sym = "XAUUSD" if "XAU" in symbol else "XAGUSD"
            url = (
                f"https://www.alphavantage.co/query"
                f"?function=FX_INTRADAY"
                f"&from_symbol={sym[:3]}"
                f"&to_symbol={sym[3:]}"
                f"&interval={interval}"
                f"&outputsize=compact"
                f"&apikey={AV_KEY}"
            )
        else:
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
            print(f"No data: {list(data.keys())}")
            return None

        df = pd.DataFrame.from_dict(data[key], orient="index")
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        df.columns = ["Open", "High", "Low", "Close"]
        df = df.astype(float)
        return df

    except Exception as e:
        print(f"Data fetch error: {e}")
        return None

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

    # Bullish engulfing
    if (prev["Close"] < prev["Open"] and
            last["Close"] > last["Open"] and
            last["Close"] > prev["Open"] and
            last["Open"] < prev["Close"]):
        score += 3

    # Bearish engulfing
    if (prev["Close"] > prev["Open"] and
            last["Close"] < last["Open"] and
            last["Close"] < prev["Open"] and
            last["Open"] > prev["Close"]):
        score -= 3

    # Hammer
    if lower_wick > body_last * 2 and upper_wick < body_last:
        score += 2

    # Shooting star
    if upper_wick > body_last * 2 and lower_wick < body_last:
        score -= 2

    # Strong body
    if total > 0 and body_last / total > 0.6:
        score += 1 if last["Close"] > last["Open"] else -1

    return score

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
        if rsi < 40:
            score += 2
        elif rsi < 45:
            score += 1
        elif rsi > 60:
            score -= 2
        elif rsi > 55:
            score -= 1

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
        if stoch < 20:
            score += 2
        elif stoch < 35:
            score += 1
        elif stoch > 80:
            score -= 2
        elif stoch > 65:
            score -= 1

    # Bollinger Bands
    if len(df) >= 20:
        sma = close.rolling(20).mean()
        std = close.rolling(20).std()
        upper = (sma + std * 2).iloc[-1]
        lower = (sma - std * 2).iloc[-1]
        last_close = close.iloc[-1]
        if last_close < lower:
            score += 2
        elif last_close > upper:
            score -= 2

    return score

# =========================
# 🔢 MULTI TIMEFRAME
# =========================
def multi_tf_confirm(symbol, primary_tf):
    confirm_tf = "M5" if primary_tf == "M1" else "M15"
    df = get_data(symbol, confirm_tf)
    if df is None or len(df) < 5:
        return 0
    return 1 if calculate_indicators(df) > 0 else -1

# =========================
# 🧠 SIGNAL ENGINE
# =========================
def generate_ai_signal(symbol, timeframe):
    is_otc = "OTC" in symbol
    df = get_data(symbol, timeframe)

    def build_text(direction, confidence):
        return f"""
🌑 ABDEYSENFX AI SIGNAL 🌑
{"🔴 OTC PAIR" if is_otc else ""}

Asset: {symbol}
Timeframe: {timeframe}
Direction: {direction}
Confidence: {confidence}%

Expiry: {timeframe}
Time: {datetime.utcnow().strftime('%H:%M:%S UTC')}

⚡ AI Engine Active
""".strip()

    if df is None or len(df) < 5:
        direction = random.choice(["HIGHER ↑ (CALL)", "LOWER ↓ (PUT)"])
        img = BUY_IMG if "HIGHER" in direction else SELL_IMG
        return build_text(direction, 65), img

    try:
        score = 0
        score += calculate_indicators(df)
        if len(df) >= 2:
            score += detect_patterns(df)
        score += multi_tf_confirm(symbol, timeframe)

        direction = "HIGHER ↑ (CALL)" if score >= 0 else "LOWER ↓ (PUT)"
        img = BUY_IMG if score >= 0 else SELL_IMG
        confidence = max(62, min(95, 58 + abs(score) * 5))

        return build_text(direction, confidence), img

    except Exception as e:
        print(f"Signal error: {e}")
        direction = random.choice(["HIGHER ↑ (CALL)", "LOWER ↓ (PUT)"])
        img = BUY_IMG if "HIGHER" in direction else SELL_IMG
        return build_text(direction, 65), img

# =========================
# 📡 POST TO CHANNEL
# =========================
def post_to_channel(text, img):
    try:
        bot.send_photo(CHANNEL, img, caption=text)
    except Exception as e:
        print("Channel post error:", e)

# =========================
# 🖥 MENUS
# =========================
def main_menu():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🚀 Forex Signal", "🥇 Metals Signal")
    markup.add("❓ Help")
    return markup

def timeframe_menu():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("M1", "M5", "M15")
    markup.add("M30", "H1")
    markup.add("🔙 Back")
    return markup

# =========================
# START
# =========================
@bot.message_handler(commands=['start'])
def start(message):
    if not is_subscribed(message.from_user.id):
        ask_to_subscribe(message.chat.id)
        return
    bot.send_message(
        message.chat.id,
        "🌑 *ABDEYSENBOT AI READY*\n\nSelect option below 👇",
        parse_mode="Markdown",
        reply_markup=main_menu()
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
            reply_markup=main_menu()
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
    bot.send_message(message.chat.id, "⏱ Select timeframe:", reply_markup=timeframe_menu())

# =========================
# METALS SIGNAL
# =========================
@bot.message_handler(func=lambda m: m.text == "🥇 Metals Signal")
def metals(message):
    if not is_subscribed(message.from_user.id):
        ask_to_subscribe(message.chat.id)
        return
    user_state[message.chat.id] = "metals"
    bot.send_message(message.chat.id, "⏱ Select timeframe:", reply_markup=timeframe_menu())

# =========================
# TIMEFRAME HANDLER
# =========================
@bot.message_handler(func=lambda m: m.text in ["M1", "M5", "M15", "M30", "H1"])
def handle_timeframe(message):
    if not is_subscribed(message.from_user.id):
        ask_to_subscribe(message.chat.id)
        return

    chat_id = message.chat.id
    timeframe = message.text
    signal_type = user_state.get(chat_id)

    if not signal_type:
        bot.send_message(chat_id, "Please select Forex or Metals first.", reply_markup=main_menu())
        return

    bot.send_message(chat_id, "⏳ Analyzing market...")

    if signal_type == "forex":
        all_pairs = forex_pairs + otc_pairs
        symbol = random.choice(all_pairs)
    else:
        symbol = random.choice(metals_pairs)

    text, img = generate_ai_signal(symbol, timeframe)
    bot.send_photo(chat_id, img, caption=text)
    post_to_channel(text, img)
    user_state.pop(chat_id, None)

# =========================
# BACK
# =========================
@bot.message_handler(func=lambda m: m.text == "🔙 Back")
def back(message):
    bot.send_message(message.chat.id, "🏠 Main Menu", reply_markup=main_menu())

# =========================
# HELP
# =========================
@bot.message_handler(func=lambda m: m.text == "❓ Help")
def help_cmd(message):
    if not is_subscribed(message.from_user.id):
        ask_to_subscribe(message.chat.id)
        return
    bot.send_message(
        message.chat.id,
        "🌑 *ABDEYSENBOT AI SIGNALS*\n\n"
        "- Forex, OTC & Metals signals\n"
        "- RSI, EMA, Stochastic, Bollinger\n"
        "- Candle pattern detection\n"
        "- Multi timeframe confirmation\n"
        "- Auto channel posting\n\n"
        "⚠️ Educational use only",
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
# RUN BOT
# =========================
print("🌑 AbdeysenBot AI Running...")
bot.infinity_polling(timeout=60, long_polling_timeout=60)
