"""
Shared indicator calculations. No pandas - plain lists in, plain lists out.
Every strategy imports from here instead of recalculating its own math.
"""


def calculate_ema(values, period):
    ema_values = [None] * len(values)
    if len(values) < period:
        return ema_values

    multiplier = 2 / (period + 1)
    sma = sum(values[:period]) / period
    ema_values[period - 1] = sma

    for i in range(period, len(values)):
        ema_values[i] = (values[i] - ema_values[i - 1]) * multiplier + ema_values[i - 1]

    return ema_values


def calculate_rsi(values, period=14):
    rsi_values = [None] * len(values)
    if len(values) < period + 1:
        return rsi_values

    gains, losses = [], []
    for i in range(1, len(values)):
        change = values[i] - values[i - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    def rsi_from_averages(avg_gain, avg_loss):
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    rsi_values[period] = rsi_from_averages(avg_gain, avg_loss)

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rsi_values[i + 1] = rsi_from_averages(avg_gain, avg_loss)

    return rsi_values


def calculate_atr(highs, lows, closes, period=14):
    """Average True Range - measures volatility, used to size stop-loss/take-profit distances."""
    atr_values = [None] * len(closes)
    if len(closes) < period + 1:
        return atr_values

    true_ranges = []
    for i in range(1, len(closes)):
        high_low = highs[i] - lows[i]
        high_prev_close = abs(highs[i] - closes[i - 1])
        low_prev_close = abs(lows[i] - closes[i - 1])
        true_ranges.append(max(high_low, high_prev_close, low_prev_close))

    avg_tr = sum(true_ranges[:period]) / period
    atr_values[period] = avg_tr

    for i in range(period, len(true_ranges)):
        avg_tr = (avg_tr * (period - 1) + true_ranges[i]) / period
        atr_values[i + 1] = avg_tr

    return atr_values


def calculate_macd(values, fast_period=12, slow_period=26, signal_period=9):
    """Returns (macd_line, signal_line, histogram) - each a list same length as values."""
    ema_fast = calculate_ema(values, fast_period)
    ema_slow = calculate_ema(values, slow_period)

    macd_line = [None] * len(values)
    for i in range(len(values)):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            macd_line[i] = ema_fast[i] - ema_slow[i]

    # EMA of the MACD line itself, only over the non-None portion
    first_valid = next((i for i, v in enumerate(macd_line) if v is not None), None)
    signal_line = [None] * len(values)
    if first_valid is not None:
        macd_values_only = [v for v in macd_line if v is not None]
        signal_only = calculate_ema(macd_values_only, signal_period)
        for offset, val in enumerate(signal_only):
            signal_line[first_valid + offset] = val

    histogram = [None] * len(values)
    for i in range(len(values)):
        if macd_line[i] is not None and signal_line[i] is not None:
            histogram[i] = macd_line[i] - signal_line[i]

    return macd_line, signal_line, histogram


def calculate_stochastic(highs, lows, closes, k_period=14, d_period=3):
    """Returns (percent_k, percent_d) - each a list same length as closes."""
    percent_k = [None] * len(closes)

    for i in range(k_period - 1, len(closes)):
        window_high = max(highs[i - k_period + 1:i + 1])
        window_low = min(lows[i - k_period + 1:i + 1])
        if window_high == window_low:
            percent_k[i] = 50
        else:
            percent_k[i] = (closes[i] - window_low) / (window_high - window_low) * 100

    percent_d = [None] * len(closes)
    for i in range(len(closes)):
        window = [percent_k[j] for j in range(max(0, i - d_period + 1), i + 1) if percent_k[j] is not None]
        if len(window) == d_period:
            percent_d[i] = sum(window) / d_period

    return percent_k, percent_d


def find_swing_points(values, lookback=3):
    """
    A simple swing high/low detector: index i is a swing high if it's higher
    than `lookback` candles on each side, swing low if lower than both sides.
    Returns (swing_highs, swing_lows) as lists of (index, value) tuples.
    """
    swing_highs, swing_lows = [], []
    for i in range(lookback, len(values) - lookback):
        window = values[i - lookback:i + lookback + 1]
        if values[i] == max(window):
            swing_highs.append((i, values[i]))
        if values[i] == min(window):
            swing_lows.append((i, values[i]))
    return swing_highs, swing_lows
