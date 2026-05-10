"""Simple per-key rate limiter."""

from collections import defaultdict, deque
from time import time

REQUESTS = defaultdict(deque)


def allow(key: str, limit: int, window_seconds: int = 1) -> bool:
    now = time()
    bucket = REQUESTS[key]
    while bucket and now - bucket[0] > window_seconds:
        bucket.popleft()
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True
