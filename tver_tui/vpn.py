from __future__ import annotations

import requests

_SERVICES = [
    ("https://ipapi.co/json/", "country_code", "ip"),
    ("https://api.myip.com", "cc", "ip"),
    ("https://ip.seeip.org/geoip", "country_code", "ip"),
]


def check_ip() -> tuple[bool, str, str]:
    """Return (is_japanese, country_code, ip_address). Tries services in order."""
    for url, cc_key, ip_key in _SERVICES:
        try:
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            country = data.get(cc_key, "")
            ip = data.get(ip_key, "unknown")
            if country:
                return country == "JP", country, ip
        except Exception:
            continue
    return False, "unknown", "unknown"
