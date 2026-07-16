"""Thin client for the Wyscout Data API (v3).

Handles Basic Auth, the documented 12 req/s per-key rate limit, and
retries on 429/5xx. No caching, no pagination logic — every endpoint
used by this tool returns a single JSON payload.
"""
from __future__ import annotations

import os
import threading
import time

import requests

DEFAULT_BASE_URL = "https://apirest.wyscout.com/v3"
MAX_REQUESTS_PER_SECOND = 12
MAX_RETRIES = 5


class WyscoutError(RuntimeError):
    def __init__(self, status_code: int, url: str, body: str):
        super().__init__(f"Wyscout API error {status_code} for {url}: {body[:500]}")
        self.status_code = status_code
        self.url = url
        self.body = body


class RateLimiter:
    """Keeps requests under N/second across a shared session."""

    def __init__(self, max_per_second: int):
        self._min_interval = 1.0 / max_per_second
        self._lock = threading.Lock()
        self._last_call = 0.0

    def wait(self):
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
            self._last_call = time.monotonic()


class WyscoutClient:
    def __init__(self, username: str | None = None, password: str | None = None,
                 base_url: str = DEFAULT_BASE_URL):
        username = username or os.environ.get("WYSCOUT_USER")
        password = password or os.environ.get("WYSCOUT_PASS")
        if not username or not password:
            raise ValueError(
                "Wyscout credentials missing: pass username/password or set "
                "WYSCOUT_USER / WYSCOUT_PASS in the environment."
            )
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.auth = (username, password)
        self._rate_limiter = RateLimiter(MAX_REQUESTS_PER_SECOND)

    def get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        backoff = 1.0
        for attempt in range(1, MAX_RETRIES + 1):
            self._rate_limiter.wait()
            resp = self.session.get(url, params=params, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429 and attempt < MAX_RETRIES:
                retry_after = float(resp.headers.get("Retry-After", backoff))
                time.sleep(retry_after)
                backoff *= 2
                continue
            if resp.status_code >= 500 and attempt < MAX_RETRIES:
                time.sleep(backoff)
                backoff *= 2
                continue
            raise WyscoutError(resp.status_code, url, resp.text)
        raise WyscoutError(resp.status_code, url, resp.text)

    # --- convenience wrappers for the endpoints this tool needs ---

    def search(self, query: str, obj_type: str) -> dict:
        return self.get("/search", {"query": query, "objType": obj_type})

    def competition(self, competition_id) -> dict:
        return self.get(f"/competitions/{competition_id}")

    def competition_seasons(self, competition_id) -> dict:
        return self.get(f"/competitions/{competition_id}/seasons")

    def season_matches(self, season_id) -> dict:
        return self.get(f"/seasons/{season_id}/matches")

    def match_events(self, match_id) -> dict:
        return self.get(f"/matches/{match_id}/events", {"details": "tag"})
