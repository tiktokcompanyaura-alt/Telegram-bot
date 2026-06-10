import os
import telebot
import random
from datetime import datetime
import yfinance as yf

from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD

# =========================
# 🔐 ENV TOKEN (RENDER SAFE)
# =========================
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise Exception("BOT_TOKEN is not set in environment variables")

bot = telebot.TeleBot(TOKEN)

# =========================
# 📡 YOUR CHANNEL
# =========================
CHANNEL = "@abdeysenfx"

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
# 📊 MARKET DATA
# =========================
def get_data(symbol):
    try:
        df = yf.download(symbol, interval="5m", period="1d", progress=False)
        if df is None or df.empty:
            return None
        return df.dropna()
    except:
        return None


# =========================
# 🧠 AI SIGNAL ENGINE
# =========================
def generate_ai_signal(symbol):
    df = get_data(symbol)
    if df is None or len(df) < 50:
        return None

    try:
        df["rsi"] = RSIIndicator(df["Close"]).rsi()
        df["ema_fast"] = EMAIndicator(df["Close"], window=9).ema_indicator()
        df["ema_slow"] = EMAIndicator(df["Close"], window=21).ema_indicator()

        macd = MACD(df["Close"])
        df["macd"] = macd.macd()
        df["macd_signal"] = macd.macd_signal()

        last = df.iloc[-1]
        score = 0

        # RSI logic
        if last["rsi"] < 30:
            score += 1
        elif last["rsi"] > 70:
            score -= 1

        # EMA trend
        if last["ema_fast"] > last["ema_slow"]:
            score += 1
        else:
            score -= 1

        # MACD momentum
        if last["macd"] > last["macd_signal"]:
            score += 1
        else:
            score -= 1

        # =========================
        # 🎯 DECISION LOGIC
        # =========================
        if score >= 2:
            direction = "HIGHER ↑ (CALL)"
            img = BUY_IMG
        elif score <= -2:
            direction = "LOWER ↓ (PUT)"
            img = SELL_IMG
        else:
            return None  # HOLD

        confidence = min(95, 60 + abs(score) * 12)

        text = f"""
🌑 ABDEYSENFX AI SIGNAL 🌑

Asset: {symbol.replace("=X","")}
Direction: {direction}
Confidence: {confidence}%
Score: {score}

Expiry: M1 (1 min)
Time: {datetime.utcnow().strftime('%H:%M:%S UTC')}

⚡ AI Engine Active
""".strip()

        return text, img

    except:
        return None


# =========================
# 📡 CHANNEL POSTING
# =========================
def post_to_channel(text, img):
    try:
        bot.send_photo(CHANNEL, img, caption=text)
    except Exception as e:
        print("Channel post error:", e)


# =========================
# 🖥 MENU
# =========================
def main_menu():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🚀 Forex Signal", "🥇 Metals Signal")
    markup.add("❓ Help")
    return markup


# =========================
# START
# =========================
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "🌑 ABDEYSENBOT AI READY\nSelect option below 👇",
        reply_markup=main_menu()
    )


# =========================
# FOREX SIGNAL
# =========================
@bot.message_handler(func=lambda m: m.text == "🚀 Forex Signal")
def forex(message):
    symbol = random.choice(forex_assets)

    result = generate_ai_signal(symbol)
    if not result:
        bot.send_message(message.chat.id, "⚠️ No clear setup right now. Try again.")
        return

    text, img = result

    bot.send_photo(message.chat.id, img, caption=text)
    post_to_channel(text, img)


# =========================
# METALS SIGNAL
# =========================
@bot.message_handler(func=lambda m: m.text == "🥇 Metals Signal")
def metals(message):
    symbol = random.choice(metals_assets)

    result = generate_ai_signal(symbol)
    if not result:
        bot.send_message(message.chat.id, "⚠️ No clear metals setup right now.")
        return

    text, img = result

    bot.send_photo(message.chat.id, img, caption=text)
    post_to_channel(text, img)


# =========================
# HELP
# =========================
@bot.message_handler(func=lambda m: m.text == "❓ Help")
def help_cmd(message):
    bot.send_message(
        message.chat.id,
        "🌑 ABDEYSENBOT AI SIGNALS\n\n"
        "- Forex & Metals signals\n"
        "- AI analysis (RSI, EMA, MACD)\n"
        "- Auto channel posting\n\n"
        "⚠️ Educational use only"
    )


# =========================
# RUN
# =========================
print("🌑 AbdeysenBot AI Running...")
bot.infinity_polling()
