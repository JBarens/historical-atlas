"""Live-mode access control: invite codes, per-code rate limits and a global daily spend cap.

Codes are never stored in clear: INVITE_CODES_SHA256 holds comma-separated sha256 hex digests, each optionally
prefixed with a label ("alice:3f2a...,9b1c..."). Create one with backend/scripts/make_invite_code.py.

Counters live in memory: correct for a single instance (one Hugging Face Space container). A restart resets the
per-minute/per-day counts and the spend total; the spend cap is therefore a per-process cap, not a billing limit.
"""
import hashlib
import os
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone


def sha256(code):
    return hashlib.sha256(code.strip().encode()).hexdigest()


def _utc_day(now=None):
    return datetime.fromtimestamp(now if now is not None else time.time(), timezone.utc).strftime("%Y-%m-%d")


class Denied(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


class Access:
    def __init__(self, codes_env=None, per_min=None, per_day=None, cap_usd=None, clock=time.time):
        raw = os.environ.get("INVITE_CODES_SHA256", "") if codes_env is None else codes_env
        self.codes = {}                                   # hash -> label
        for item in (x.strip() for x in raw.split(",")):
            if not item:
                continue
            label, _, h = item.rpartition(":")
            self.codes[h.strip().lower()] = label.strip() or h.strip()[:8]
        self.per_min = int(per_min if per_min is not None else os.environ.get("RATE_LIMIT_PER_MIN", 5))
        self.per_day = int(per_day if per_day is not None else os.environ.get("RATE_LIMIT_PER_DAY", 50))
        self.cap_usd = float(cap_usd if cap_usd is not None else os.environ.get("DAILY_SPEND_CAP_USD", 2.00))
        self.clock = clock
        self._lock = threading.Lock()
        self._recent = defaultdict(deque)                 # hash -> timestamps in the last 60 s
        self._daily = defaultdict(int)                    # (hash, day) -> count
        self._spend = defaultdict(float)                  # day -> USD

    def spent_today(self):
        return self._spend[_utc_day(self.clock())]

    def cap_reached(self):
        return self.spent_today() >= self.cap_usd

    def admit(self, code):
        """Check code, cap and limits, and count the request. Returns the label. Raises Denied."""
        if not code:
            raise Denied(401, "invite_required", "An invite code is required for live questions.")
        h = sha256(code)
        if h not in self.codes:
            raise Denied(401, "invite_invalid", "This invite code is not valid.")
        now = self.clock()
        with self._lock:
            if self.cap_reached():
                raise Denied(503, "daily_cap", "The daily budget for live questions is used up. "
                                               "Live mode is back tomorrow; the examples still work.")
            q = self._recent[h]
            while q and now - q[0] >= 60:
                q.popleft()
            if len(q) >= self.per_min:
                raise Denied(429, "rate_minute", f"Limit of {self.per_min} questions per minute reached. "
                                                 "Please wait a moment.")
            day = (h, _utc_day(now))
            if self._daily[day] >= self.per_day:
                raise Denied(429, "rate_day", f"Limit of {self.per_day} questions per day reached for this code.")
            q.append(now)
            self._daily[day] += 1
        return self.codes[h]

    def record_cost(self, usd):
        with self._lock:
            self._spend[_utc_day(self.clock())] += float(usd or 0)
