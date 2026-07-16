"""
Candlestick + S/R v2 - upgrade of the #1 strategy.
Same trend + support/resistance + breakout framework as the original, but
swaps the small 8-pattern detector for the full 45-pattern best-fit library,
pruned to the 20 patterns proven individually profitable.
"""

from indicators import calculate_ema, calculate_atr, find_swing_points
from strategies.pattern_library import detect_pattern

KEPT_PATTERNS = {
    "Three Black Crows", "Bearish Harami", "Mat Hold", "Morning Star",
    "Pin Bar (bullish)", "Morning Doji Star", "Tweezer Top", "Dragonfly Doji",
    "Bearish Engulfing", "Bullish Engulfing", "Falling Three Methods",
    "Three Inside Up", "Homing Pigeon", "Matching Low", "Downside Tasuki Gap",
    "Matching High", "Deliberation", "Unique Three River Bottom",
    "Three White Soldiers", "In-Neck Pattern",
}


class CandlestickSRv2Strategy:
    def __init__(self, name="Candlestick + S/R v2", trend_fast=20, trend_slow=50,
                 swing_lookback=5, level_window=60, proximity_atr_mult=1.0,
                 atr_period=14, sl_buffer_atr_mult=0.5, reward_multiple=3.0):
        self.name = name
        self.trend_fast = trend_fast
        self.trend_slow = trend_slow
        self.swing_lookback = swing_lookback
        self.level_window = level_window
        self.proximity_atr_mult = proximity_atr_mult
        self.atr_period = atr_period
        self.sl_buffer_atr_mult = sl_buffer_atr_mult
        self.reward_multiple = reward_multiple

    def check_signal(self, prices):
        closes = [p["close"] for p in prices]
        highs = [p["high"] for p in prices]
        lows = [p["low"] for p in prices]

        ema_fast = calculate_ema(closes, self.trend_fast)
        ema_slow = calculate_ema(closes, self.trend_slow)
        atr = calculate_atr(highs, lows, closes, self.atr_period)
        swing_highs, swing_lows = find_swing_points(closes, self.swing_lookback)

        for p in prices:
            p["signal"] = 0

        start = max(self.trend_slow, self.atr_period, self.level_window, 5) + 2

        high_ptr, low_ptr = 0, 0
        window_highs, window_lows = [], []

        for i in range(start, len(prices)):
            p = prices[i]

            while high_ptr < len(swing_highs) and swing_highs[high_ptr][0] < i:
                window_highs.append(swing_highs[high_ptr]); high_ptr += 1
            while window_highs and window_highs[0][0] < i - self.level_window:
                window_highs.pop(0)
            while low_ptr < len(swing_lows) and swing_lows[low_ptr][0] < i:
                window_lows.append(swing_lows[low_ptr]); low_ptr += 1
            while window_lows and window_lows[0][0] < i - self.level_window:
                window_lows.pop(0)

            if ema_fast[i] is None or ema_slow[i] is None or atr[i] is None:
                continue
            if not window_highs or not window_lows:
                continue

            price = closes[i]

            if ema_fast[i] > ema_slow[i]:
                trend = 1
            elif ema_fast[i] < ema_slow[i]:
                trend = -1
            else:
                trend = 0

            supports_below = [v for _, v in window_lows if v <= price]
            resistances_above = [v for _, v in window_highs if v >= price]
            support = max(supports_below) if supports_below else None
            resistance = min(resistances_above) if resistances_above else None

            candle_dir, pattern_name, _ = detect_pattern(prices, i)
            if candle_dir == 0 or pattern_name not in KEPT_PATTERNS:
                continue

            proximity = atr[i] * self.proximity_atr_mult
            sl_buffer = atr[i] * self.sl_buffer_atr_mult
            signal_fired = False

            if candle_dir == 1 and trend >= 0 and support is not None and (price - support) <= proximity:
                entry = price
                stop = support - sl_buffer
                risk = entry - stop
                if risk > 0:
                    p["signal"] = 1
                    p["entry"] = entry
                    p["stop_loss"] = stop
                    p["take_profit"] = entry + risk * self.reward_multiple
                    p["pattern"] = pattern_name
                    signal_fired = True

            elif candle_dir == -1 and trend <= 0 and resistance is not None and (resistance - price) <= proximity:
                entry = price
                stop = resistance + sl_buffer
                risk = stop - entry
                if risk > 0:
                    p["signal"] = -1
                    p["entry"] = entry
                    p["stop_loss"] = stop
                    p["take_profit"] = entry - risk * self.reward_multiple
                    p["pattern"] = pattern_name
                    signal_fired = True

            if not signal_fired and candle_dir == 1 and resistance is not None and price > resistance:
                entry = price
                stop = resistance - sl_buffer
                risk = entry - stop
                if risk > 0:
                    p["signal"] = 1
                    p["entry"] = entry
                    p["stop_loss"] = stop
                    p["take_profit"] = entry + risk * self.reward_multiple
                    p["pattern"] = f"{pattern_name} (breakout)"

            elif not signal_fired and candle_dir == -1 and support is not None and price < support:
                entry = price
                stop = support + sl_buffer
                risk = stop - entry
                if risk > 0:
                    p["signal"] = -1
                    p["entry"] = entry
                    p["stop_loss"] = stop
                    p["take_profit"] = entry - risk * self.reward_multiple
                    p["pattern"] = f"{pattern_name} (breakdown)"

        return prices
