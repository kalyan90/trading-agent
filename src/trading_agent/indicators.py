def calculate_sma(prices: list[float], period: int) -> float:
    if len(prices) < period:
        raise ValueError(
            f"Need at least {period} prices, got {len(prices)}"
        )

    recent_prices = prices[-period:]
    return sum(recent_prices) / period