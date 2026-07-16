"""
Candlestick Pattern strategy.
Uses the 8 patterns (Bullish/Bearish Engulfing, Hammer, Shooting Star, Doji,
Pin Bar, Morning Star, Evening Star) as the actual trigger - but only takes
a trade when the pattern is backed up by context, same as a real discretionary
trader would check:

1. TREND - EMA20 vs EMA50 decides if we're in an uptrend, downtrend, or flat.
2. SUPPORT/RESISTANCE - recent swing highs/lows mark key levels.
3. SETUP TYPE:
   a. BOUNCE  - bullish pattern right at support (in an up/flat trend) -> buy
                 bearish pattern right at resistance (in a down/flat trend) -> sell
   b. BREAKOUT - bullish pattern as price closes above resistance -> buy
                  bearish pattern as price closes below support -> sell
4. RISK MANAGEMENT - stop-loss placed just beyond the relevant level (support/
   resistance, with a small ATR buffer so normal noise doesn't stop us out
   instantly), take-profit sized as a multiple of that risk distance.

Doji is intentionally never a signal alone - it just means indecision, so it's
skipped (matches its "neutral" rating from the candlestick detector).
"""

from indicators import calculate_ema, calculate_atr, find_swing_points
from strategies.confluence_strategy import detect_candlestick_pattern


class CandlestickStrategy:
    def __init__(self, name="Candlestick + S/R", trend_fast=20, trend_slow=50,
                 swing_lookback=5, level_window=60, proximity_atr_mult=1.0,
                 atr_period=14, sl_buffer_atr_mult=0.3, reward_multiple=2.0):
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

        start = max(self.trend_slow, self.atr_period, self.level_window) + 1

        high_ptr, low_ptr = 0, 0
        window_highs, window_lows = [], []

        for i in range(start, len(prices)):
            p = prices[i]

            while high_ptr < len(swing_highs) and swing_highs[high_ptr][0] < i:
                window_highs.append(swing_highs[high_ptr])
                high_ptr += 1
            while window_highs and window_highs[0][0] < i - self.level_window:
                window_highs.pop(0)

            while low_ptr < len(swing_lows) and swing_lows[low_ptr][0] < i:
                window_lows.append(swing_lows[low_ptr])
                low_ptr += 1
            while window_lows and window_lows[0][0] < i - self.level_window:
                window_lows.pop(0)

            if ema_fast[i] is None or ema_slow[i] is None or atr[i] is None:
                continue
            if not window_highs or not window_lows:
                continue

            price = closes[i]

            # Trend: 1 = up, -1 = down, 0 = flat/unclear
            if ema_fast[i] > ema_slow[i]:
                trend = 1
            elif ema_fast[i] < ema_slow[i]:
                trend = -1
            else:
                trend = 0

            # Nearest support (below price) and resistance (above price)
            supports_below = [v for _, v in window_lows if v <= price]
            resistances_above = [v for _, v in window_highs if v >= price]
            support = max(supports_below) if supports_below else None
            resistance = min(resistances_above) if resistances_above else None

            candle_dir, pattern_name, candle_conf = detect_candlestick_pattern(prices, i)
            if candle_dir == 0:
                continue  # no pattern, or just a Doji (neutral)

            proximity = atr[i] * self.proximity_atr_mult
            sl_buffer = atr[i] * self.sl_buffer_atr_mult

            signal_fired = False

            # --- BOUNCE at support ---
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

            # --- BOUNCE at resistance ---
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

            # --- BREAKOUT above resistance ---
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

            # --- BREAKDOWN below support ---
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
