# Shared HTTP client and a small in-memory cache with expiry.
# Reads: the network, through the callers. Writes: nothing.
from __future__ import annotations

import time

import httpx

USER_AGENT = "envoituresimone/0.1 (personal demo app)"
_client: httpx.AsyncClient | None = None
_cache: dict[str, tuple[float, object]] = {}


def client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=30, headers={"User-Agent": USER_AGENT})
    return _client


def cached(key: str, ttl_s: float):
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < ttl_s:
        return hit[1]
    return None


def store(key: str, value):
    if len(_cache) > 500:
        _cache.clear()
    _cache[key] = (time.monotonic(), value)
    return value
