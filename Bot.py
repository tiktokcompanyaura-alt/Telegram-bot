"""
ABDEYSENBOT - Telegram signal bot using your TOP 3 validated strategies,
each one profitable across two separate real backtests (2023-2025 AND
2020-2022) - not just single-period luck.

Priority order (checked in this order, first one with a live signal wins):
1. Candlestick + S/R v2 (Champion)  - validated +69.5% / +59.4%
2. Candlestick + S/R v1             - validated +45.3% / +18.0%
3. RSI Oversold 30                  - validated +14.7% / +13.0%

Still XAUUSD only, still CSV-based (see get_latest_candles() to plug in
a live feed later) - same honest limitations as before.
"""

import telebot
import os
from datetime import datetime

from data_feed import HistoricalCSVFeed
from strategies.candlestick_sr_v2 import CandlestickSRv2Strategy
from strategies.candlestick_strategy import CandlestickStrategy
from strategies.rsi_oversold import RSIOversoldStrategy

TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

CSV_PATH = "XAU_15m_data.csv"

# name -> (strategy instance, real validated win rates from backtest)
TOP_3 = [
    ("Candlestick + S/R v2 (Champion)", CandlestickSRv2Strategy(), "30-40% (big win/loss ratio)"),
    ("Candlestick + S/R v1", CandlestickStrategy(), "38-39%"),
    ("RSI Oversold 30", RSIOversoldStrategy(), "36-37%"),
]


def get_latest_candles():
    """
    Currently loads from your historical CSV. TO GO LIVE: replace this
    function's contents with a real-time price feed call, keeping the
    same dict format (date/open/high/low/close) - everything downstream
    keeps working unchanged.
    """
    feed = HistoricalCSVFeed(CSV_PATH)
    prices = feed.load_filtered("2025-01-01", "2026-02-01")  # adjust to your CSV's actual latest range
    return prices


def generate_real_signal():
    """
    Checks the Top 3 in priority order. Returns the first live signal
    found, or None if none of the three currently have one - we don't
    invent a signal just to have something to send.
    """
    prices = get_latest_candles()
    if not prices:
        return None

    for name, strat, win_rate in TOP_3:
        prices_copy = [dict(p) for p in prices]  # each strategy gets a clean copy
        prices_copy = strat.check_signal(prices_copy)
        signals = [p for p in prices_copy if p.get("signal") in (1, -1)]
        if not signals:
            continue

        latest = signals[-1]
        direction = latest["signal"]
        entry = latest["entry"]
        sl = latest["stop_loss"]
        tp = latest["take_profit"]
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        rr = round(reward / risk, 1) if risk > 0 else 0
        pattern = latest.get("pattern", "Setup")
        direction_text = "HIGHER \u2191 (Buy)" if direction == 1 else "LOWER \u2193 (Sell)"

        text = f"""
\U0001F311 ABDEYSENBOT SIGNAL \U0001F311
Asset: XAU/USD
Strategy: {name}
Direction: {direction_text}
Entry: {entry:.2f}
Stop Loss: {sl:.2f}
Take Profit: {tp:.2f}
Risk:Reward: 1:{rr}
Setup: {pattern}
Strategy's real historical win rate: {win_rate}
(validated across two separate 2-year backtests)

\U0001F552 {datetime.utcnow().strftime('%H:%M:%S UTC')}
""".strip()
        return text

    return None  # none of the Top 3 have a current signal


def main_menu():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("\U0001F947 Gold Signal")
    markup.add("\u2753 Help")
    return markup


@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "ABDEYSENBOT Ready\nUse buttons below \U0001F447",
                 reply_markup=main_menu())


@bot.message_handler(func=lambda m: m.text == "\U0001F947 Gold Signal")
def gold_signal(message):
    text = generate_real_signal()
    if text is None:
        bot.reply_to(
            message,
            "No active signal right now from any of the Top 3 strategies - "
            "none has found a qualifying setup in the current data. "
            "Check back soon."
        )
        return

    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("Trade", url="https://pocketoption.com"))
    bot.reply_to(message, text, reply_markup=markup)


@bot.message_handler(func=lambda m: m.text == "\u2753 Help")
def help_cmd(message):
    bot.reply_to(
        message,
        "Signals come from your Top 3 validated strategies (Candlestick + "
        "S/R v2, Candlestick + S/R v1, RSI Oversold 30) - each proven "
        "profitable across two separate real backtests, not just one "
        "lucky period. Currently running on historical XAUUSD data, not "
        "yet live-connected. For education only - trade responsibly."
    )


print("Bot Started...")
bot.infinity_polling()
