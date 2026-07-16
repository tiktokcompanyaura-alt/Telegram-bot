"""
Execution layer.
BacktestExecutor: simulates fills using stop-loss/take-profit levels
(since the newer strategies only fire entry signals, not exit signals).
On each candle: if in a position, check whether price hit stop-loss or
take-profit first, and close there. Only one open position at a time.
"""


class BacktestExecutor:
    def __init__(self, starting_balance: float = 1000.0, lot_size: float = 0.01):
        self.balance = starting_balance
        self.lot_size = lot_size
        self.position = None  # None when flat, otherwise a dict with trade details
        self.trade_log = []

    def place_order(self, price_bar: dict):
        """
        price_bar: one row from the price list, e.g.
        {"date":..., "open":..., "high":..., "low":..., "close":...,
         "signal": 1 or -1, "entry":..., "stop_loss":..., "take_profit":...}
        """
        # Already in a trade -> check if this candle's high/low hit SL or TP
        if self.position is not None:
            direction = self.position["direction"]

            if direction == 1:  # long: profit if price rises, loss if it falls
                hit_tp = price_bar["high"] >= self.position["take_profit"]
                hit_sl = price_bar["low"] <= self.position["stop_loss"]
            else:  # short: profit if price falls, loss if it rises
                hit_tp = price_bar["low"] <= self.position["take_profit"]
                hit_sl = price_bar["high"] >= self.position["stop_loss"]

            # If both could have happened in the same candle, assume the
            # worse case (stop-loss) hits first - a common, conservative rule.
            if hit_sl:
                self._close_position(self.position["stop_loss"], price_bar["date"])
            elif hit_tp:
                self._close_position(self.position["take_profit"], price_bar["date"])
            return

        # Flat -> open a new position if there's a signal
        signal = price_bar.get("signal", 0)
        if signal != 0:
            self.position = {
                "direction": signal,
                "entry": price_bar["entry"],
                "stop_loss": price_bar["stop_loss"],
                "take_profit": price_bar["take_profit"],
                "opened_at": price_bar["date"],
            }
            self.trade_log.append({
                "time": price_bar["date"], "action": "OPEN",
                "direction": signal, "price": price_bar["entry"],
            })

    def _close_position(self, exit_price, timestamp):
        direction = self.position["direction"]
        pnl = (exit_price - self.position["entry"]) * direction * self.lot_size * 100
        self.balance += pnl
        self.trade_log.append({
            "time": timestamp, "action": "CLOSE",
            "price": exit_price, "pnl": pnl, "balance": self.balance,
        })
        self.position = None

    def summary(self):
        closed = [t for t in self.trade_log if t["action"] == "CLOSE"]
        wins = [t for t in closed if t["pnl"] > 0]
        return {
            "final_balance": round(self.balance, 2),
            "total_trades": len(closed),
            "win_rate": round((len(wins) / len(closed) * 100), 2) if closed else 0,
        }


class LiveMT5Executor:
    """Placeholder - implement with mt5.order_send() when you have MT5 running."""

    def __init__(self, symbol: str = "XAUUSD"):
        self.symbol = symbol

    def place_order(self, price_bar: dict):
        raise NotImplementedError("Implement with MetaTrader5.order_send() on the laptop")
