"""
Full candlestick pattern library - covers nearly the entire catalog:
single-candle, two-candle, three-candle, continuation, and gap patterns.

SKIPPED (too rare / inconsistently defined across sources to implement
reliably): Concealing Baby Swallow, Ladder Bottom, Ladder Top.

detect_pattern(prices, i) checks EVERY pattern definition against the
candle (no early exit), collects every one that matches, and returns
the BEST-FITTING match (highest confidence score) rather than whichever
happened to be checked first. This avoids one pattern's check accidentally
"stealing" a candle that a later, more specific pattern would have matched
better.
"""


def _o(c): return c["open"]
def _h(c): return c["high"]
def _l(c): return c["low"]
def _cl(c): return c["close"]
def _body(c): return abs(_cl(c) - _o(c))
def _range(c): return _h(c) - _l(c)
def _bull(c): return _cl(c) > _o(c)
def _bear(c): return _cl(c) < _o(c)
def _upper_wick(c): return _h(c) - max(_o(c), _cl(c))
def _lower_wick(c): return min(_o(c), _cl(c)) - _l(c)


def _prior_move(prices, i, lookback=4):
    """Positive = price has been rising into this candle, negative = falling."""
    if i - 1 - lookback < 0:
        return 0
    return prices[i - 1]["close"] - prices[i - 1 - lookback]["close"]


def detect_pattern(prices, i):
    if i < 5:
        return 0, None, 0

    c0, c1, c2, c3, c4 = prices[i], prices[i - 1], prices[i - 2], prices[i - 3], prices[i - 4]
    r0 = _range(c0)
    if r0 == 0:
        return 0, None, 0
    trend_in = _prior_move(prices, i)
    candidates = []  # each: (direction, name, reliability)

    # ================= 5-CANDLE CONTINUATION =================
    if (_bull(c4) and _body(c4) > _range(c4) * 0.6 and
            all(c["high"] <= c4["high"] and c["low"] >= c4["low"] for c in (c3, c2, c1)) and
            _bull(c0) and _cl(c0) > _cl(c4)):
        candidates.append((1, "Rising Three Methods", 0.65))

    if (_bear(c4) and _body(c4) > _range(c4) * 0.6 and
            all(c["high"] <= c4["high"] and c["low"] >= c4["low"] for c in (c3, c2, c1)) and
            _bear(c0) and _cl(c0) < _cl(c4)):
        candidates.append((-1, "Falling Three Methods", 0.65))

    if (_bull(c4) and _body(c4) > _range(c4) * 0.6 and
            all(c["low"] >= c4["close"] * 0.997 for c in (c3, c2, c1)) and
            _bull(c0) and _cl(c0) > _cl(c4)):
        candidates.append((1, "Mat Hold", 0.6))

    # ================= GAP PATTERNS =================
    gap_up_10 = _o(c1) > _h(c2)
    gap_down_10 = _o(c1) < _l(c2)
    gap_up_01 = _o(c0) > _h(c1)
    gap_down_01 = _o(c0) < _l(c1)

    if (_bear(c2) and gap_down_10 and _body(c1) < _range(c1) * 0.1 and
            gap_up_01 and _bull(c0)):
        candidates.append((1, "Bullish Abandoned Baby", 0.7))

    if (_bull(c2) and gap_up_10 and _body(c1) < _range(c1) * 0.1 and
            gap_down_01 and _bear(c0)):
        candidates.append((-1, "Bearish Abandoned Baby", 0.7))

    if (_bull(c2) and gap_up_10 and _bull(c1) and
            _bear(c0) and _o(c0) < _cl(c1) and _o(c0) > _o(c1) and _cl(c0) > _h(c2)):
        candidates.append((1, "Upside Tasuki Gap", 0.55))

    if (_bear(c2) and gap_down_10 and _bear(c1) and
            _bull(c0) and _o(c0) > _cl(c1) and _o(c0) < _o(c1) and _cl(c0) < _l(c2)):
        candidates.append((-1, "Downside Tasuki Gap", 0.55))

    if (trend_in < 0 and _bear(c4) and _body(c4) > _range(c4) * 0.5 and
            _o(c3) < _cl(c4) and _bull(c0) and _cl(c0) > _cl(c3) and _cl(c0) < _o(c4)):
        candidates.append((1, "Breakaway", 0.5))

    if (trend_in > 0 and _bull(c4) and _body(c4) > _range(c4) * 0.5 and
            _o(c3) > _cl(c4) and _bear(c0) and _cl(c0) < _cl(c3) and _cl(c0) > _o(c4)):
        candidates.append((-1, "Breakaway", 0.5))

    if (trend_in > 0 and gap_up_10 and _bull(c1) and _bull(c0) and
            abs(_body(c1) - _body(c0)) < max(_body(c1), _body(c0)) * 0.3):
        candidates.append((1, "Side-by-Side White Lines", 0.45))

    # ================= 3-CANDLE PATTERNS =================
    if (_bear(c2) and _body(c2) > _range(c2) * 0.5 and
            _body(c1) < _range(c1) * 0.1 and
            _bull(c0) and _cl(c0) > (_o(c2) + _cl(c2)) / 2):
        candidates.append((1, "Morning Doji Star", 0.75))

    if (_bull(c2) and _body(c2) > _range(c2) * 0.5 and
            _body(c1) < _range(c1) * 0.1 and
            _bear(c0) and _cl(c0) < (_o(c2) + _cl(c2)) / 2):
        candidates.append((-1, "Evening Doji Star", 0.75))

    if (_bear(c2) and _body(c2) > _range(c2) * 0.5 and
            _body(c1) < _range(c1) * 0.3 and
            _bull(c0) and _cl(c0) > (_o(c2) + _cl(c2)) / 2):
        candidates.append((1, "Morning Star", 0.7))

    if (_bull(c2) and _body(c2) > _range(c2) * 0.5 and
            _body(c1) < _range(c1) * 0.3 and
            _bear(c0) and _cl(c0) < (_o(c2) + _cl(c2)) / 2):
        candidates.append((-1, "Evening Star", 0.7))

    if (_bull(c2) and _bull(c1) and _bull(c0) and
            _body(c2) > _range(c2) * 0.5 and _body(c1) > _range(c1) * 0.5 and _body(c0) > _range(c0) * 0.5 and
            _cl(c2) < _cl(c1) < _cl(c0)):
        candidates.append((1, "Three White Soldiers", 0.7))

    if (_bear(c2) and _bear(c1) and _bear(c0) and
            _body(c2) > _range(c2) * 0.5 and _body(c1) > _range(c1) * 0.5 and _body(c0) > _range(c0) * 0.5 and
            _cl(c2) > _cl(c1) > _cl(c0)):
        candidates.append((-1, "Three Black Crows", 0.7))

    if (_bull(c2) and _bull(c1) and _bull(c0) and
            _cl(c2) < _cl(c1) < _cl(c0) and
            _body(c1) < _body(c2) * 0.9 and _body(c0) < _body(c1) * 0.9):
        candidates.append((-1, "Advance Block", 0.5))

    if (_bull(c2) and _bull(c1) and _body(c2) > _range(c2) * 0.5 and _body(c1) > _range(c1) * 0.5 and
            _cl(c1) > _cl(c2) and _body(c0) < _range(c0) * 0.3 and _cl(c0) >= _cl(c1)):
        candidates.append((-1, "Deliberation", 0.45))

    if (_bear(c2) and _o(c1) > _cl(c2) and _cl(c1) < _o(c2) and _bull(c1) and
            _bull(c0) and _cl(c0) > _o(c2)):
        candidates.append((1, "Three Inside Up", 0.65))

    if (_bull(c2) and _o(c1) < _cl(c2) and _cl(c1) > _o(c2) and _bear(c1) and
            _bear(c0) and _cl(c0) < _o(c2)):
        candidates.append((-1, "Three Inside Down", 0.65))

    if (_bear(c2) and _bull(c1) and _o(c1) < _cl(c2) and _cl(c1) > _o(c2) and
            _bull(c0) and _cl(c0) > _cl(c1)):
        candidates.append((1, "Three Outside Up", 0.65))

    if (_bull(c2) and _bear(c1) and _o(c1) > _cl(c2) and _cl(c1) < _o(c2) and
            _bear(c0) and _cl(c0) < _cl(c1)):
        candidates.append((-1, "Three Outside Down", 0.65))

    if (_bear(c2) and _bull(c1) and _bear(c0) and
            abs(_cl(c2) - _cl(c0)) < r0 * 0.1 and _cl(c1) > _cl(c2)):
        candidates.append((1, "Stick Sandwich", 0.5))

    if (_bear(c2) and _body(c2) > _range(c2) * 0.5 and
            _l(c1) < _l(c2) and _body(c1) < _range(c1) * 0.3 and _lower_wick(c1) > _body(c1) and
            _bull(c0) and _h(c0) < _h(c1) and _body(c0) < _body(c2)):
        candidates.append((1, "Unique Three River Bottom", 0.55))

    if (_body(c2) < _range(c2) * 0.1 and _body(c1) < _range(c1) * 0.1 and _body(c0) < _range(c0) * 0.1):
        candidates.append(((1 if trend_in < 0 else -1), "Tri-Star", 0.45))

    # ================= 2-CANDLE PATTERNS =================
    if (_bear(c1) and _body(c1) > _range(c1) * 0.9 and
            _bull(c0) and _body(c0) > _range(c0) * 0.9 and _o(c0) > _o(c1)):
        candidates.append((1, "Kicking Pattern", 0.65))

    if (_bull(c1) and _body(c1) > _range(c1) * 0.9 and
            _bear(c0) and _body(c0) > _range(c0) * 0.9 and _o(c0) < _o(c1)):
        candidates.append((-1, "Kicking Pattern", 0.65))

    if _bear(c1) and _bull(c0) and _o(c0) < _cl(c1) and _cl(c0) > _o(c1):
        candidates.append((1, "Bullish Engulfing", 0.75))

    if _bull(c1) and _bear(c0) and _o(c0) > _cl(c1) and _cl(c0) < _o(c1):
        candidates.append((-1, "Bearish Engulfing", 0.75))

    if _bear(c1) and _bull(c0) and _o(c0) > _cl(c1) and _cl(c0) < _o(c1) and _body(c0) < _body(c1) * 0.6:
        candidates.append((1, "Bullish Harami", 0.55))

    if _bull(c1) and _bear(c0) and _o(c0) < _cl(c1) and _cl(c0) > _o(c1) and _body(c0) < _body(c1) * 0.6:
        candidates.append((-1, "Bearish Harami", 0.55))

    if (_bear(c1) and _bull(c0) and _o(c0) < _l(c1) and
            _cl(c0) > (_o(c1) + _cl(c1)) / 2 and _cl(c0) < _o(c1)):
        candidates.append((1, "Piercing Line", 0.65))

    if (_bull(c1) and _bear(c0) and _o(c0) > _h(c1) and
            _cl(c0) < (_o(c1) + _cl(c1)) / 2 and _cl(c0) > _o(c1)):
        candidates.append((-1, "Dark Cloud Cover", 0.65))

    if abs(_l(c1) - _l(c0)) < r0 * 0.1 and _bear(c1) and _bull(c0):
        candidates.append((1, "Tweezer Bottom", 0.5))

    if abs(_h(c1) - _h(c0)) < r0 * 0.1 and _bull(c1) and _bear(c0):
        candidates.append((-1, "Tweezer Top", 0.5))

    if trend_in < 0 and abs(_cl(c1) - _cl(c0)) < r0 * 0.08 and _bear(c1):
        candidates.append((1, "Matching Low", 0.45))

    if trend_in > 0 and abs(_cl(c1) - _cl(c0)) < r0 * 0.08 and _bull(c1):
        candidates.append((-1, "Matching High", 0.45))

    if _bear(c1) and _bear(c0) and _o(c0) < _o(c1) and _cl(c0) > _cl(c1):
        candidates.append((1, "Homing Pigeon", 0.45))

    if (_bear(c1) and _bull(c0) and _body(c1) > _range(c1) * 0.5 and _body(c0) > _range(c0) * 0.5 and
            abs(_cl(c1) - _cl(c0)) < r0 * 0.1):
        candidates.append((1, "Meeting Lines", 0.5))

    if (_bull(c1) and _bear(c0) and _body(c1) > _range(c1) * 0.5 and _body(c0) > _range(c0) * 0.5 and
            abs(_cl(c1) - _cl(c0)) < r0 * 0.1):
        candidates.append((-1, "Meeting Lines", 0.5))

    if (_bear(c1) and _bull(c0) and abs(_cl(c1) - _cl(c0)) < r0 * 0.08 and
            abs(_body(c1) - _body(c0)) < max(_body(c1), _body(c0)) * 0.3):
        candidates.append((1, "Counterattack Lines", 0.45))
    if (_bull(c1) and _bear(c0) and abs(_cl(c1) - _cl(c0)) < r0 * 0.08 and
            abs(_body(c1) - _body(c0)) < max(_body(c1), _body(c0)) * 0.3):
        candidates.append((-1, "Counterattack Lines", 0.45))

    if trend_in > 0 and _bear(c1) and _bull(c0) and abs(_o(c1) - _o(c0)) < r0 * 0.08:
        candidates.append((1, "Separating Lines", 0.45))

    if trend_in < 0 and _bull(c1) and _bear(c0) and abs(_o(c1) - _o(c0)) < r0 * 0.08:
        candidates.append((-1, "Separating Lines", 0.45))

    if (trend_in < 0 and _bear(c1) and _body(c1) > _range(c1) * 0.5 and
            _bull(c0) and _o(c0) < _l(c1) and abs(_cl(c0) - _l(c1)) < r0 * 0.15):
        candidates.append((-1, "On-Neck Pattern", 0.45))

    if (trend_in < 0 and _bear(c1) and _body(c1) > _range(c1) * 0.5 and
            _bull(c0) and _o(c0) < _l(c1) and
            _cl(c0) > _l(c1) and _cl(c0) < _cl(c1) + _body(c1) * 0.15):
        candidates.append((-1, "In-Neck Pattern", 0.4))

    if (trend_in < 0 and _bear(c1) and _bull(c0) and _o(c0) < _l(c1) and
            _cl(c0) > _cl(c1) and _cl(c0) < (_o(c1) + _cl(c1)) / 2):
        candidates.append((-1, "Thrusting Pattern", 0.4))

    # ================= 1-CANDLE PATTERNS =================
    body0 = _body(c0)
    uw, lw = _upper_wick(c0), _lower_wick(c0)

    if body0 > r0 * 0.9:
        candidates.append(((1 if _bull(c0) else -1), ("Bullish Marubozu" if _bull(c0) else "Bearish Marubozu"), 0.6))

    if _bull(c0) and lw < r0 * 0.05 and body0 > r0 * 0.7:
        candidates.append((1, "Bullish Belt Hold", 0.5))
    if _bear(c0) and uw < r0 * 0.05 and body0 > r0 * 0.7:
        candidates.append((-1, "Bearish Belt Hold", 0.5))

    if body0 < r0 * 0.1 and lw > r0 * 0.6 and uw < r0 * 0.1:
        candidates.append((1, "Dragonfly Doji", 0.55))

    if body0 < r0 * 0.1 and uw > r0 * 0.6 and lw < r0 * 0.1:
        candidates.append((-1, "Gravestone Doji", 0.55))

    if body0 < r0 * 0.1 and uw > r0 * 0.3 and lw > r0 * 0.3:
        candidates.append((0, "Long-Legged Doji", 0.3))

    if body0 < r0 * 0.1:
        candidates.append((0, "Doji", 0.3))

    if r0 * 0.1 <= body0 < r0 * 0.35 and uw > body0 * 0.5 and lw > body0 * 0.5:
        candidates.append((0, "Spinning Top", 0.3))

    if lw > body0 * 2 and uw < body0 * 0.5 and body0 < r0 * 0.4:
        if trend_in < 0:
            candidates.append((1, "Hammer", 0.6))
        elif trend_in > 0:
            candidates.append((-1, "Hanging Man", 0.55))

    if uw > body0 * 2 and lw < body0 * 0.5 and body0 < r0 * 0.4:
        if trend_in < 0:
            candidates.append((1, "Inverted Hammer", 0.55))
        elif trend_in > 0:
            candidates.append((-1, "Shooting Star", 0.6))

    if lw > r0 * 0.6 and body0 < r0 * 0.3:
        candidates.append((1, "Pin Bar (bullish)", 0.55))
    if uw > r0 * 0.6 and body0 < r0 * 0.3:
        candidates.append((-1, "Pin Bar (bearish)", 0.55))

    # ================= PICK THE BEST FIT =================
    # Prefer directional patterns over neutral ones (Doji/Spinning Top) if
    # both technically match - a directional signal is more decision-useful.
    directional = [c for c in candidates if c[0] != 0]
    if directional:
        return max(directional, key=lambda c: c[2])
    if candidates:
        return max(candidates, key=lambda c: c[2])
    return 0, None, 0
