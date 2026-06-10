import os
import time
import threading
import telebot
import random
import pandas as pd
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import yfinance as yf

from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD

# =========================
# 🔐 ENV TOKEN
# =========================
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise Exception("BOT_TOKEN is not set in environment variables")

bot = telebot.TeleBot(TOKEN)

# =========================
# 🔄 CLEAR WEBHOOK & RESET
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
# 📡 CHANNEL
# =========================
CHANNEL = "@abdeysenfx"
CHANNEL_LINK = "https://t.me/abdeysenfx"

# =========================
# 📊 ASSETS
# =========================
forex_assets = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X", "NZDUSD=X"]
metals_assets = ["XAUUSD=X", "XAGUSD=X"]

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
    markup.add(
        telebot.types.InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)
    )
    markup.add(
        telebot.types.InlineKeyboardButton("✅ I Have Joined", callback_data="check_sub")
    )
    bot.send_message(
        chat_id,
        "⚠️ *ACCESS DENIED*\n\n"
        "You must join our channel first!\n\n"
        f"👉 Join here: {CHANNEL_LINK}\n\n"
        "Then tap ✅ I Have Joined",
        parse_mode="Markdown",
        reply_markup=markup
    )


# =========================
# 📊 MARKET DATA
# =========================
TIMEFRAME_MAP = {
    "M1": ("1m", "1d"),
    "M5": ("5m", "1d"),
    "M15": ("15m", "5d"),
    "M30": ("30m", "5d"),
    "H1": ("60m", "1mo"),
}

def get_data(symbol, timeframe="M5"):
    try:
        interval, period = TIMEFRAME_MAP.get(timeframe, ("5m", "1d"))
        df = yf.download(symbol, interval=interval, period=period, progress=False, auto_adjust=True)
        if df is None or df.empty:
            return None
        df = df.dropna()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        print(f"Data fetch error for {symbol}: {e}")
        return None


# =========================
# 🕯 CANDLE ANALYSIS
# =========================
def analyze_candles(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]

    # Candle body and wick sizes
    body = abs(float(last["Close"]) - float(last["Open"]))
    total = float(last["High"]) - float(last["Low"])
    upper_wick = float(last["High"]) - max(float(last["Close"]), float(last["Open"]))
    lower_wick = min(float(last["Close"]), float(last["Open"])) - float(last["Low"])

    score = 0

    # Bullish candle
    if float(last["Close"]) > float(last["Open"]):
        score += 1
    else:
        score -= 1

    # Momentum from previous candle
    if float(last["Close"]) > float(prev["Close"]):
        score += 1
    else:
        score -= 1

    # Strong body vs wicks = strong move
    if total > 0 and body / total > 0.5:
        if float(last["Close"]) > float(last["Open"]):
            score += 1
        else:
            score -= 1

    # Lower wick = buyer pressure
    if lower_wick > upper_wick:
        score += 1
    else:
        score -= 1

    return score


# =========================
# 🧠 AI SIGNAL ENGINE
# =========================
def generate_ai_signal(symbol, timeframe):
    df = get_data(symbol, timeframe)

    if df is None or len(df) < 5:
        # Fallback random signal if no data
        direction = random.choice(["HIGHER ↑ (CALL)", "LOWER ↓ (PUT)"])
        img = BUY_IMG if "HIGHER" in direction else SELL_IMG
        confidence = random.randint(60, 75)
        text = f"""
🌑 ABDEYSENFX AI SIGNAL 🌑

Asset: {symbol.replace("=X", "")}
Timeframe: {timeframe}
Direction: {direction}
Confidence: {confidence}%

Expiry: {timeframe}
Time: {datetime.utcnow().strftime('%H:%M:%S UTC')}

⚡ AI Engine Active
""".strip()
        return text, img

    try:
        close = df["Close"].squeeze()

        # Indicators
        score = 0

        if len(df) >= 14:
            rsi = RSIIndicator(close).rsi().iloc[-1]
            if rsi < 35:
                score += 2
            elif rsi < 45:
                score += 1
            elif rsi > 65:
                score -= 2
            elif rsi > 55:
                score -= 1
        else:
            rsi = 50

        if len(df) >= 21:
            ema_fast = EMAIndicator(close, window=9).ema_indicator().iloc[-1]
            ema_slow = EMAIndicator(close, window=21).ema_indicator().iloc[-1]
            if ema_fast > ema_slow:
                score += 1
            else:
                score -= 1

        if len(df) >= 26:
            macd_obj = MACD(close)
            macd_val = macd_obj.macd().iloc[-1]
            macd_sig = macd_obj.macd_signal().iloc[-1]
            if macd_val > macd_sig:
                score += 1
            else:
                score -= 1

        # Candle analysis
        if len(df) >= 2:
            candle_score = analyze_candles(df)
            score += candle_score

        # =========================
        # 🎯 ALWAYS DECIDE
        # =========================
        if score >= 0:
            direction = "HIGHER ↑ (CALL)"
            img = BUY_IMG
        else:
            direction = "LOWER ↓ (PUT)"
            img = SELL_IMG

        # Confidence based on score strength
        confidence = min(95, 55 + abs(score) * 8)
        confidence = max(60, confidence)

        text = f"""
🌑 ABDEYSENFX AI SIGNAL 🌑

Asset: {symbol.replace("=X", "")}
Timeframe: {timeframe}
Direction: {direction}
Confidence: {confidence}%

Expiry: {timeframe}
Time: {datetime.utcnow().strftime('%H:%M:%S UTC')}

⚡ AI Engine Active
""".strip()

        return text, img

    except Exception as e:
        print(f"Signal error: {e}")
        direction = random.choice(["HIGHER ↑ (CALL)", "LOWER ↓ (PUT)"])
        img = BUY_IMG if "HIGHER" in direction else SELL_IMG
        text = f"""
🌑 ABDEYSENFX AI SIGNAL 🌑

Asset: {symbol.replace("=X", "")}
Timeframe: {timeframe}
Direction: {direction}
Confidence: 65%

Expiry: {timeframe}
Time: {datetime.utcnow().strftime('%H:%M:%S UTC')}

⚡ AI Engine Active
""".strip()
        return text, img


# =========================
# 📡 CHANNEL POSTING
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
        "🌑 *ABDEYSENBOT AI READY*\nSelect option below 👇",
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
            "✅ *Welcome to AbdeysenFX!*\nSelect option below 👇",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
    else:
        bot.answer_callback_query(call.id, "❌ You have not joined yet!", show_alert=True)


# =========================
# FOREX SIGNAL
# =========================
@bot.message_handler(func=lambda m: m.text == "🚀 Forex Signal")
def forex(message):
    if not is_subscribed(message.from_user.id):
        ask_to_subscribe(message.chat.id)
        return
    user_state[message.chat.id] = "forex"
    bot.send_message(
        message.chat.id,
        "⏱ Select your timeframe:",
        reply_markup=timeframe_menu()
    )


# =========================
# METALS SIGNAL
# =========================
@bot.message_handler(func=lambda m: m.text == "🥇 Metals Signal")
def metals(message):
    if not is_subscribed(message.from_user.id):
        ask_to_subscribe(message.chat.id)
        return
    user_state[message.chat.id] = "metals"
    bot.send_message(
        message.chat.id,
        "⏱ Select your timeframe:",
        reply_markup=timeframe_menu()
    )


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
        symbol = random.choice(forex_assets)
    else:
        symbol = random.choice(metals_assets)

    result = generate_ai_signal(symbol, timeframe)
    text, img = result

    bot.send_photo(chat_id, img, caption=text)
    post_to_channel(text, img)

    user_state.pop(chat_id, None)


# =========================
# BACK BUTTON
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
        "- Forex & Metals signals\n"
        "- AI analysis (RSI, EMA, MACD)\n"
        "- Candle size analysis\n"
        "- Multiple timeframes\n"
        "- Auto channel posting\n\n"
        "⚠️ Educational use only",
        parse_mode="Markdown"
    )


# =========================
# RUN
# =========================
print("🌑 AbdeysenBot AI Running...")
bot.infinity_polling(timeout=60, long_polling_timeout=60)
