"""
Multi-factor confluence strategy.
Combines 4 categories of analysis, each voting bullish (+1), bearish (-1),
or no opinion (0). A trade only fires when at least 3 of 4 categories agree
on direction AND the combined confidence score is >= 70%.

Categories:
1. Breakout      - confirmed close beyond recent swing high/low, scored by
                    distance relative to ATR (bigger move = higher confidence).
2. Reversal      - RSI divergence, and approximate Double Top / Double Bottom
                    detection from recent swing points.
                    (Head & Shoulders is intentionally NOT included - reliably
                    detecting it algorithmically without excess false positives
                    is a much bigger project than the other patterns here.)
3. Momentum      - RSI, MACD, and Stochastic combined; majority vote among the three.
4. Candlestick   - Bullish/Bearish Engulfing, Hammer, Shooting Star, Doji,
                    Morning Star, Evening Star. Reliability weighted by whether
                    the pattern appears at a relevant swing point (context).

Risk flags:
- LOW VOLATILITY: current ATR far below its recent average -> market may be too
  quiet to trade cleanly.
- RANGING: price hasn't made a new swing high/low in a while -> no clear trend.
(No news-event flag - this bot has no news data feed.)
"""

from indicators import (
    calculate_rsi, calculate_atr, calculate_macd,
    calculate_stochastic, find_swing_points,
)


# ---------- Candlestick pattern helpers (operate on single/recent candles) ----------

def _body(c):
    return abs(c["close"] - c["open"])


def _range(c):
    return c["high"] - c["low"]


def _is_bullish(c):
    return c["close"] > c["open"]


def detect_candlestick_pattern(prices, i):
    """Returns (direction, pattern_name, reliability 0-1) or (0, None, 0)."""
    if i < 2:
        return 0, None, 0

    c0, c1, c2 = prices[i], prices[i - 1], prices[i - 2]  # c0 = current (latest)
    rng0 = _range(c0)
    if rng0 == 0:
        return 0, None, 0

    body0 = _body(c0)
    upper_wick = c0["high"] - max(c0["close"], c0["open"])
    lower_wick = min(c0["close"], c0["open"]) - c0["low"]

    # Doji: very small body relative to range
    if body0 < rng0 * 0.1:
        return 0, "Doji", 0.4  # neutral - signals indecision, not direction

    # Bullish Engulfing
    if not _is_bullish(c1) and _is_bullish(c0):
        if c0["open"] < c1["close"] and c0["close"] > c1["open"]:
            return 1, "Bullish Engulfing", 0.75

    # Bearish Engulfing
    if _is_bullish(c1) and not _is_bullish(c0):
        if c0["open"] > c1["close"] and c0["close"] < c1["open"]:
            return -1, "Bearish Engulfing", 0.75

    # Hammer: small body near top, long lower wick, little upper wick,
    # AND appears after a recent downward move (its actual intended context -
    # a random hammer-shaped candle in a flat/choppy stretch isn't meaningful)
    if lower_wick > body0 * 2 and upper_wick < body0 * 0.5 and body0 < rng0 * 0.4:
        prior_move = c2["close"] - prices[i - 4]["close"] if i >= 4 else 0
        if prior_move < 0:
            return 1, "Hammer", 0.6

    # Shooting Star: small body near bottom, long upper wick, little lower wick,
    # AND appears after a recent upward move
    if upper_wick > body0 * 2 and lower_wick < body0 * 0.5 and body0 < rng0 * 0.4:
        prior_move = c2["close"] - prices[i - 4]["close"] if i >= 4 else 0
        if prior_move > 0:
            return -1, "Shooting Star", 0.6

    # Morning Star (3-candle bullish reversal): big bearish, small body, big bullish closing into candle 1's body
    if (not _is_bullish(c2) and _body(c2) > _range(c2) * 0.5 and
            _body(c1) < _range(c1) * 0.3 and
            _is_bullish(c0) and c0["close"] > (c2["open"] + c2["close"]) / 2):
        return 1, "Morning Star", 0.7

    # Evening Star (3-candle bearish reversal): mirror of above
    if (_is_bullish(c2) and _body(c2) > _range(c2) * 0.5 and
            _body(c1) < _range(c1) * 0.3 and
            not _is_bullish(c0) and c0["close"] < (c2["open"] + c2["close"]) / 2):
        return -1, "Evening Star", 0.7

    # Three White Soldiers: 3 consecutive strong bullish candles, each closing higher than the last
    if (_is_bullish(c2) and _is_bullish(c1) and _is_bullish(c0) and
            _body(c2) > _range(c2) * 0.5 and _body(c1) > _range(c1) * 0.5 and _body(c0) > _range(c0) * 0.5 and
            c2["close"] < c1["close"] < c0["close"]):
        return 1, "Three White Soldiers", 0.7

    # Three Black Crows: mirror - 3 consecutive strong bearish candles, each closing lower than the last
    if (not _is_bullish(c2) and not _is_bullish(c1) and not _is_bullish(c0) and
            _body(c2) > _range(c2) * 0.5 and _body(c1) > _range(c1) * 0.5 and _body(c0) > _range(c0) * 0.5 and
            c2["close"] > c1["close"] > c0["close"]):
        return -1, "Three Black Crows", 0.7

    # Pin Bar (generic long-wick rejection, direction from which wick dominates)
    if lower_wick > rng0 * 0.6 and body0 < rng0 * 0.3:
        return 1, "Pin Bar (bullish)", 0.55
    if upper_wick > rng0 * 0.6 and body0 < rng0 * 0.3:
        return -1, "Pin Bar (bearish)", 0.55

    return 0, None, 0


class ConfluenceStrategy:
    def __init__(self, name="Confluence Analysis",
                 swing_lookback=5, breakout_lookback=20,
                 rsi_period=14, atr_period=14,
                 min_agreeing=3, min_confidence=70,
                 reward_multiple=2.0):
        self.name = name
        self.swing_lookback = swing_lookback
        self.breakout_lookback = breakout_lookback
        self.rsi_period = rsi_period
        self.atr_period = atr_period
        self.min_agreeing = min_agreeing
        self.min_confidence = min_confidence
        self.reward_multiple = reward_multiple

    def check_signal(self, prices):
        closes = [p["close"] for p in prices]
        highs = [p["high"] for p in prices]
        lows = [p["low"] for p in prices]

        rsi = calculate_rsi(closes, self.rsi_period)
        atr = calculate_atr(highs, lows, closes, self.atr_period)
        macd_line, signal_line, _ = calculate_macd(closes)
        percent_k, percent_d = calculate_stochastic(highs, lows, closes)
        swing_highs, swing_lows = find_swing_points(closes, self.swing_lookback)

        swing_high_idx = {i for i, _ in swing_highs}
        swing_low_idx = {i for i, _ in swing_lows}

        for p in prices:
            p["signal"] = 0

        start = max(self.breakout_lookback, self.atr_period, 26 + 9, self.swing_lookback * 2) + 1

        # Sliding window of recent swing points (within last 60 candles) -
        # advanced with pointers instead of rescanning the full list each
        # iteration, which was the slow part on lower-powered devices.
        high_ptr = 0
        low_ptr = 0
        recent_highs_window = []
        recent_lows_window = []

        for i in range(start, len(prices)):
            p = prices[i]

            # Add any new swing highs that are now behind us (idx < i)
            while high_ptr < len(swing_highs) and swing_highs[high_ptr][0] < i:
                recent_highs_window.append(swing_highs[high_ptr])
                high_ptr += 1
            # Drop ones that fell outside the 60-candle recency window
            while recent_highs_window and recent_highs_window[0][0] < i - 60:
                recent_highs_window.pop(0)

            while low_ptr < len(swing_lows) and swing_lows[low_ptr][0] < i:
                recent_lows_window.append(swing_lows[low_ptr])
                low_ptr += 1
            while recent_lows_window and recent_lows_window[0][0] < i - 60:
                recent_lows_window.pop(0)

            if atr[i] is None or rsi[i] is None:
                continue

            # ---------- 1. BREAKOUT ----------
            window_highs = highs[i - self.breakout_lookback:i]
            window_lows = lows[i - self.breakout_lookback:i]
            resistance = max(window_highs)
            support = min(window_lows)

            breakout_dir = 0
            breakout_conf = 0
            if closes[i] > resistance:
                breakout_dir = 1
                distance = (closes[i] - resistance) / atr[i] if atr[i] > 0 else 0
                breakout_conf = min(1.0, 0.4 + distance * 0.3)
            elif closes[i] < support:
                breakout_dir = -1
                distance = (support - closes[i]) / atr[i] if atr[i] > 0 else 0
                breakout_conf = min(1.0, 0.4 + distance * 0.3)

            # ---------- 2. REVERSAL (RSI divergence + double top/bottom) ----------
            reversal_dir = 0
            reversal_conf = 0

            recent_highs = recent_highs_window
            recent_lows = recent_lows_window

            # Bearish RSI divergence: price makes a higher high, RSI makes a lower high
            if len(recent_highs) >= 2:
                (idx_a, val_a), (idx_b, val_b) = recent_highs[-2], recent_highs[-1]
                if val_b > val_a and rsi[idx_b] is not None and rsi[idx_a] is not None and rsi[idx_b] < rsi[idx_a]:
                    reversal_dir = -1
                    reversal_conf = 0.65
                # Double top: two similar highs (within 0.3%) -> bearish
                elif abs(val_b - val_a) / val_a < 0.003:
                    reversal_dir = -1
                    reversal_conf = 0.55

            # Bullish RSI divergence: price makes a lower low, RSI makes a higher low
            if len(recent_lows) >= 2:
                (idx_a, val_a), (idx_b, val_b) = recent_lows[-2], recent_lows[-1]
                if val_b < val_a and rsi[idx_b] is not None and rsi[idx_a] is not None and rsi[idx_b] > rsi[idx_a]:
                    if reversal_dir == 0:
                        reversal_dir = 1
                        reversal_conf = 0.65
                elif abs(val_b - val_a) / val_a < 0.003:
                    if reversal_dir == 0:
                        reversal_dir = 1
                        reversal_conf = 0.55

            # ---------- 3. MOMENTUM (RSI + MACD + Stochastic majority vote) ----------
            votes = []
            if rsi[i] is not None:
                if rsi[i] < 30:
                    votes.append(1)
                elif rsi[i] > 70:
                    votes.append(-1)
                else:
                    votes.append(0)

            if macd_line[i] is not None and signal_line[i] is not None:
                votes.append(1 if macd_line[i] > signal_line[i] else -1)

            if percent_k[i] is not None:
                if percent_k[i] < 20:
                    votes.append(1)
                elif percent_k[i] > 80:
                    votes.append(-1)
                else:
                    votes.append(0)

            momentum_dir = 0
            momentum_conf = 0
            nonzero_votes = [v for v in votes if v != 0]
            if nonzero_votes:
                bulls = nonzero_votes.count(1)
                bears = nonzero_votes.count(-1)
                if bulls > bears:
                    momentum_dir = 1
                    momentum_conf = bulls / len(votes)
                elif bears > bulls:
                    momentum_dir = -1
                    momentum_conf = bears / len(votes)

            # ---------- 4. CANDLESTICK ----------
            candle_dir, pattern_name, candle_conf = detect_candlestick_pattern(prices, i)

            # ---------- COMBINE ----------
            directions = [breakout_dir, reversal_dir, momentum_dir, candle_dir]
            confidences = [breakout_conf, reversal_conf, momentum_conf, candle_conf]

            bulls = sum(1 for d in directions if d == 1)
            bears = sum(1 for d in directions if d == -1)

            final_dir = 0
            if bulls >= self.min_agreeing:
                final_dir = 1
            elif bears >= self.min_agreeing:
                final_dir = -1

            if final_dir == 0:
                continue

            agreeing_confidences = [c for d, c in zip(directions, confidences) if d == final_dir]
            confidence_score = (sum(agreeing_confidences) / len(agreeing_confidences)) * 100 if agreeing_confidences else 0

            # Risk flag: low volatility (current ATR well below its recent average)
            recent_atr = [a for a in atr[max(0, i - 20):i] if a is not None]
            if recent_atr:
                avg_atr = sum(recent_atr) / len(recent_atr)
                if avg_atr > 0 and atr[i] < avg_atr * 0.5:
                    confidence_score *= 0.7  # penalize low-volatility setups instead of a hard skip

            if confidence_score < self.min_confidence:
                continue

            entry = closes[i]
            if final_dir == 1:
                stop = entry - atr[i] * 1.5
                target = entry + atr[i] * 1.5 * self.reward_multiple
            else:
                stop = entry + atr[i] * 1.5
                target = entry - atr[i] * 1.5 * self.reward_multiple

            p["signal"] = final_dir
            p["entry"] = entry
            p["stop_loss"] = stop
            p["take_profit"] = target
            p["confidence"] = round(confidence_score, 1)

        return prices
