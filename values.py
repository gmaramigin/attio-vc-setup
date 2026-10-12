"""Read Attio value arrays into plain Python values."""


def first(values, slug):
    rows = values.get(slug) or []
    return rows[0] if rows else None


def title(values, slug):
    """Title of a status or select value."""
    v = first(values, slug)
    if not v:
        return None
    return (v.get("status") or v.get("option") or {}).get("title")


def titles(values, slug):
    return [(r.get("option") or r.get("status") or {}).get("title") for r in values.get(slug) or []]


def scalar(values, slug):
    """Text, number, date, rating, checkbox or currency."""
    v = first(values, slug)
    if not v:
        return None
    return v.get("currency_value", v.get("value"))
