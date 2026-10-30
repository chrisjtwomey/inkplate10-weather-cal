"""``even_select``, a sampling helper for the weather providers."""


def even_select(n, l):
    """Pick ``n`` evenly spaced entries from ``l`` (first and last included)."""
    if n == 1:
        return [l[0]]
    return [l[round(i * (len(l) - 1) / (n - 1))] for i in range(n)]
