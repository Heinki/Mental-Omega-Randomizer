"""Small, shared collection helpers with explicit ordering semantics."""


def comma_items(value):
    """Split one INI comma list, removing whitespace and empty entries."""
    return [item.strip() for item in str(value or '').split(',') if item.strip()]


def unique_in_order(items):
    """Return strings once, preserving first spelling/order, ignoring case."""
    seen = set()
    result = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
