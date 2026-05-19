"""Verify that hits claiming to be Googlebot really come from Google.

Two-stage check (fastest first):

1. **IP-range match.** Google publishes a JSON file of CIDR ranges used by
   each crawler. We download it once and check membership with the ``ipaddress``
   module. This is the canonical, authoritative answer per Google's docs.
2. **Forward-confirmed reverse DNS.** Fallback for IPs that don't match a
   range (or when the range file is unreachable). Reverse-resolve the IP, check
   the hostname ends in ``googlebot.com`` / ``google.com`` / ``googleusercontent.com``,
   then forward-resolve the hostname and confirm it returns the original IP.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Iterable

import pandas as pd
import requests

_GOOGLEBOT_RANGES_URL = "https://developers.google.com/search/apis/ipranges/googlebot.json"
_SPECIAL_CRAWLERS_URL = "https://developers.google.com/search/apis/ipranges/special-crawlers.json"
_USER_CRAWLERS_URL = "https://developers.google.com/search/apis/ipranges/user-triggered-fetchers.json"

_VALID_HOST_SUFFIXES = (".googlebot.com", ".google.com", ".googleusercontent.com")


@dataclass
class GoogleRanges:
    networks: list[ipaddress._BaseNetwork] = field(default_factory=list)

    @classmethod
    def empty(cls) -> "GoogleRanges":
        return cls(networks=[])

    def contains(self, ip_str: str) -> bool:
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return False
        return any(ip in net for net in self.networks)


def fetch_google_ranges(timeout: int = 15) -> GoogleRanges:
    """Download Google's published crawler IP ranges. On failure returns empty."""
    nets: list[ipaddress._BaseNetwork] = []
    for url in (_GOOGLEBOT_RANGES_URL, _SPECIAL_CRAWLERS_URL, _USER_CRAWLERS_URL):
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError):
            continue
        for prefix in data.get("prefixes", []) or []:
            cidr = prefix.get("ipv4Prefix") or prefix.get("ipv6Prefix")
            if not cidr:
                continue
            try:
                nets.append(ipaddress.ip_network(cidr))
            except ValueError:
                continue
    return GoogleRanges(networks=nets)


@lru_cache(maxsize=4096)
def _reverse_dns(ip: str) -> str | None:
    try:
        host, _, _ = socket.gethostbyaddr(ip)
        return host
    except (socket.herror, socket.gaierror, OSError):
        return None


@lru_cache(maxsize=4096)
def _forward_dns(host: str) -> tuple[str, ...]:
    try:
        infos = socket.getaddrinfo(host, None)
        return tuple({info[4][0] for info in infos})
    except (socket.gaierror, OSError):
        return ()


def reverse_forward_confirm(ip: str) -> bool:
    """Forward-confirmed reverse DNS check. Slow (~50-200ms per IP)."""
    host = _reverse_dns(ip)
    if not host:
        return False
    if not any(host.endswith(suffix) for suffix in _VALID_HOST_SUFFIXES):
        return False
    return ip in _forward_dns(host)


def verify_ips(
    ips: Iterable[str],
    ranges: GoogleRanges,
    use_dns_fallback: bool = False,
) -> dict[str, bool]:
    """Return ``{ip: is_verified}`` for each unique IP."""
    out: dict[str, bool] = {}
    for ip in set(ips):
        if not ip:
            out[ip] = False
            continue
        if ranges.contains(ip):
            out[ip] = True
        elif use_dns_fallback:
            out[ip] = reverse_forward_confirm(ip)
        else:
            out[ip] = False
    return out


def add_verification(
    df: pd.DataFrame,
    ranges: GoogleRanges,
    use_dns_fallback: bool = False,
    only_claimed: bool = True,
) -> pd.DataFrame:
    """Append an ``is_verified_googlebot`` column to ``df``.

    Only IPs whose request claimed a Google* user-agent are checked when
    ``only_claimed`` is True (the default), to keep noise low.
    """
    df = df.copy()
    if only_claimed:
        mask = df["claimed_bot"].fillna("").str.startswith(("Googlebot", "AdsBot-Google", "Mediapartners-Google"))
        ips_to_check = df.loc[mask, "ip"].dropna().unique().tolist()
    else:
        ips_to_check = df["ip"].dropna().unique().tolist()

    verdict = verify_ips(ips_to_check, ranges, use_dns_fallback=use_dns_fallback)
    df["is_verified_googlebot"] = df["ip"].map(verdict).fillna(False).astype("boolean")
    return df
