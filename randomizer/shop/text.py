"""Player-facing Shop currency labels."""


def gem_text(amount):
    """Format a Gem amount with correct singular or plural wording."""
    amount = int(amount)
    return f'{amount} Gem' if abs(amount) == 1 else f'{amount} Gems'
