import telebot
import os
import random
from datetime import datetime

TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

forex_assets = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD", "NZD/USD"]
metals_assets = ["XAU/USD", "XAG/USD"]

def generate_signal(asset_type="forex"):
    if asset_type == "metals":
        asset = random.choice(metals_assets)
    else:
        asset = random.choice(forex_assets)

    direction = random.choice(["HIGHER ↑ (Call)", "LOWER ↓ (Put)"])
    confidence = random.randint(78, 93)

    text = f"""
🌑 ABDEYSENBOT AI SIGNAL 🌑
Asset: {asset}
Direction: {direction}
Expiry: M1 (1 min)
Confidence: {confidence}%
Est. Win Rate: {random.randint(74,88)}%

🕒 {datetime.utcnow().strftime('%H:%M:%S UTC')}
Dark Precision Signals
""".strip()

    return text

def main_menu():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🚀 Forex Signal", "🥇 Metals Signal")
    markup.add("❓ Help")
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "ABDEYSENBOT Ready\nUse buttons below 👇",
                 reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "🚀 Forex Signal")
def forex(message):
    text = generate_signal("forex")
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("Trade", url="https://pocketoption.com"))
    bot.reply_to(message, text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🥇 Metals Signal")
def metals(message):
    text = generate_signal("metals")
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("Trade", url="https://pocketoption.com"))
    bot.reply_to(message, text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "❓ Help")
def help_cmd(message):
    bot.reply_to(message, "Signals for education only. Trade responsibly!")

print("Bot Started...")
bot.infinity_polling()
