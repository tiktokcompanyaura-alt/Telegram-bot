"""
RSI Oversold strategy.
Signal fires when RSI drops below the threshold (default 30) - a simple
"price has dropped a lot, might bounce" signal, as described in the video.
Same ATR-based stop-loss/take-profit approach as the EMA crossover strategy.
"""

from indicators import calculate_rsi, calculate_atr


class RSIOversoldStrategy:
    def __init__(self, name="RSI Oversold", rsi_period=14, threshold=30,
                 atr_period=14, atr_mult_sl=1.5, atr_mult_tp=3.0):
        self.name = name
        self.rsi_period = rsi_period
        self.threshold = threshold
        self.atr_period = atr_period
        self.atr_mult_sl = atr_mult_sl
        self.atr_mult_tp = atr_mult_tp

    def check_signal(self, prices):
        closes = [p["close"] for p in prices]
        highs = [p["high"] for p in prices]
        lows = [p["low"] for p in prices]

        rsi = calculate_rsi(closes, self.rsi_period)
        atr = calculate_atr(highs, lows, closes, self.atr_period)

        for i, p in enumerate(prices):
            p["signal"] = 0

            if rsi[i] is None or atr[i] is None:
                continue

            if rsi[i] < self.threshold:
                entry = p["close"]
                p["signal"] = 1
                p["entry"] = entry
                p["stop_loss"] = entry - (atr[i] * self.atr_mult_sl)
                p["take_profit"] = entry + (atr[i] * self.atr_mult_tp)

        return prices
