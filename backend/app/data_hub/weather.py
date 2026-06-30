"""Weather connector — real precipitation from Open-Meteo (free, no API key).

Open-Meteo is used because its **historical archive** is free and keyless, which is what we
need to ground the dataset in real weather. (OpenWeatherMap's historical data requires a paid
plan; if you have a key you can swap `forecast_is_rainy` to call it.)

- `fetch_daily_precip` (archive) — past daily precipitation, used to build the dataset.
- `forecast_is_rainy` (forecast) — is the target day rainy? used live, best-effort.

All calls are best-effort with a short timeout; failures return empty/None so nothing in the
request path or the data generator hard-depends on the network.
"""
from __future__ import annotations

import datetime as dt
import json
import urllib.parse
import urllib.request

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
RAIN_THRESHOLD_MM = 2.0
TIMEOUT = 20


def _get(url: str, params: dict) -> dict | None:
    try:
        full = url + "?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(full, timeout=TIMEOUT) as resp:
            return json.load(resp)
    except Exception:
        return None


def fetch_daily_precip(lat: float, lon: float, start: dt.date,
                       end: dt.date) -> dict[dt.date, float]:
    """Real daily precipitation (mm) for a coordinate over a past date range."""
    data = _get(ARCHIVE_URL, {
        "latitude": lat, "longitude": lon,
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "daily": "precipitation_sum", "timezone": "Europe/Madrid",
    })
    out: dict[dt.date, float] = {}
    if not data or "daily" not in data:
        return out
    for d, mm in zip(data["daily"]["time"], data["daily"]["precipitation_sum"]):
        out[dt.date.fromisoformat(d)] = float(mm) if mm is not None else 0.0
    return out


def forecast_is_rainy(lat: float, lon: float, date: dt.date) -> bool | None:
    """Best-effort: will `date` be rainy at this location? None if unavailable."""
    data = _get(FORECAST_URL, {
        "latitude": lat, "longitude": lon, "daily": "precipitation_sum",
        "start_date": date.isoformat(), "end_date": date.isoformat(),
        "timezone": "Europe/Madrid",
    })
    try:
        mm = data["daily"]["precipitation_sum"][0]
        return (mm or 0.0) >= RAIN_THRESHOLD_MM
    except Exception:
        return None
