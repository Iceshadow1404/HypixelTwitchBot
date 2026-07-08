def format_number(num: float) -> str:
    """1_500_000 -> '1.50M' (two decimals, uppercase suffix)."""
    if num >= 1_000_000_000:
        return f"{num / 1_000_000_000:.2f}B"
    if num >= 1_000_000:
        return f"{num / 1_000_000:.2f}M"
    if num >= 1_000:
        return f"{num / 1_000:.2f}K"
    return f"{num:.0f}"


def format_price(price: int | float) -> str:
    """1_300_000 -> '1.3m' (one decimal, lowercase suffix)."""
    price = float(price)
    if price >= 1_000_000_000:
        return f"{price / 1_000_000_000:.1f}b"
    if price >= 1_000_000:
        return f"{price / 1_000_000:.1f}m"
    if price >= 1_000:
        return f"{price / 1_000:.1f}k"
    return f"{price:.0f}"
