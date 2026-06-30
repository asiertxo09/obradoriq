"""Holiday calendar for the target date — an external signal the forecast can use.

Uses the `holidays` package for Spain (incl. Catalonia, where the demo chain is) when
available; falls back to a small built-in set so the system never hard-depends on it or
the network.
"""
from __future__ import annotations

import datetime as dt

_FALLBACK = {
    (4, 23),  # Sant Jordi
    (5, 1),   # Labour Day
    (6, 24),  # Sant Joan
    (1, 1), (1, 6), (8, 15), (10, 12), (11, 1), (12, 6), (12, 25), (12, 26),
}


def is_holiday(date: dt.date, country: str = "ES", subdiv: str = "CT") -> bool:
    try:
        import holidays as _h

        return date in _h.country_holidays(country, subdiv=subdiv, years=date.year)
    except Exception:
        return (date.month, date.day) in _FALLBACK
