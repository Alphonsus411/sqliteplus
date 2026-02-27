from starlette.requests import Request

from sqliteplus.api.client_ip import get_client_ip
from sqliteplus.auth.rate_limit import LoginRateLimiter
from sqliteplus.auth.rate_limit_store import InMemoryRateLimitStore


def test_rate_limiter_prunes_inactive_states():
    limiter = LoginRateLimiter(
        max_attempts=3,
        window_seconds=5,
        base_block_seconds=1,
        max_block_seconds=10,
        state_ttl_seconds=10,
    )

    limiter.register_failure(ip="10.0.0.1", username="alice", now=1.0)
    assert limiter.metrics_snapshot()["ip_states_size"] == 1
    assert limiter.metrics_snapshot()["user_states_size"] == 1

    limiter.is_blocked(ip="other-ip", username=None, now=12.1)
    assert limiter.metrics_snapshot()["ip_states_size"] == 0
    assert limiter.metrics_snapshot()["user_states_size"] == 0


def test_rate_limiter_keeps_blocked_entries_until_block_expires():
    limiter = LoginRateLimiter(
        max_attempts=2,
        window_seconds=10,
        base_block_seconds=20,
        max_block_seconds=20,
        state_ttl_seconds=1,
    )

    limiter.register_failure(ip="10.0.0.2", username="bob", now=1.0)
    limiter.register_failure(ip="10.0.0.2", username="bob", now=2.0)

    assert limiter.is_blocked(ip="10.0.0.2", username="bob", now=3.0)

    limiter.is_blocked(ip="noise", username=None, now=6.0)
    metrics = limiter.metrics_snapshot()
    assert metrics["ip_states_size"] == 1
    assert metrics["user_states_size"] == 1

    limiter.is_blocked(ip="noise", username=None, now=30.0)
    metrics = limiter.metrics_snapshot()
    assert metrics["ip_states_size"] == 0
    assert metrics["user_states_size"] == 0


def test_rate_limiter_preserves_progressive_blocking_behavior():
    limiter = LoginRateLimiter(
        max_attempts=2,
        window_seconds=30,
        base_block_seconds=5,
        max_block_seconds=20,
        state_ttl_seconds=300,
    )

    limiter.register_failure(ip="127.0.0.1", username="admin", now=1.0)
    limiter.register_failure(ip="127.0.0.1", username="admin", now=2.0)

    assert limiter.is_blocked(ip="127.0.0.1", username="admin", now=6.9)

    limiter.register_failure(ip="127.0.0.1", username="admin", now=8.0)
    limiter.register_failure(ip="127.0.0.1", username="admin", now=9.0)

    assert limiter.is_blocked(ip="127.0.0.1", username="admin", now=18.9)


def test_rate_limiter_caps_metrics_cardinality_and_counts_drops():
    limiter = LoginRateLimiter(
        max_attempts=10,
        window_seconds=60,
        base_block_seconds=1,
        max_block_seconds=2,
        state_ttl_seconds=600,
        metrics_ttl_seconds=600,
        max_metrics_keys=50,
    )

    for idx in range(200):
        limiter.register_failure(
            ip=f"192.168.1.{idx}",
            username=f"user-{idx}",
            now=float(idx + 1),
        )

    metrics = limiter.metrics_snapshot()
    assert metrics["failed_attempts_total"] == 200
    assert metrics["failed_attempts_ip_total"] == 200
    assert metrics["failed_attempts_user_total"] == 200
    assert metrics["metrics_ip_size"] == 50
    assert metrics["metrics_user_size"] == 50
    assert metrics["metrics_dropped_total"] == 300
    retained_ips = metrics["retained_failed_by_ip"]
    retained_users = metrics["retained_failed_by_user"]
    assert "192.168.1.0" not in retained_ips
    assert "user-0" not in retained_users
    assert "192.168.1.199" in retained_ips
    assert "user-199" in retained_users


def test_rate_limiter_prunes_metrics_by_ttl():
    limiter = LoginRateLimiter(
        max_attempts=10,
        window_seconds=60,
        base_block_seconds=1,
        max_block_seconds=2,
        state_ttl_seconds=600,
        metrics_ttl_seconds=10,
        max_metrics_keys=100,
    )

    limiter.register_failure(ip="10.10.0.1", username="alice", now=1.0)
    metrics = limiter.metrics_snapshot()
    assert metrics["metrics_ip_size"] == 1
    assert metrics["metrics_user_size"] == 1

    limiter.is_blocked(ip="noise", username=None, now=20.1)

    metrics = limiter.metrics_snapshot()
    assert metrics["metrics_ip_size"] == 0
    assert metrics["metrics_user_size"] == 0


def test_shared_store_keeps_block_between_instances():
    shared_store = InMemoryRateLimitStore()
    limiter_a = LoginRateLimiter(max_attempts=2, base_block_seconds=30, max_block_seconds=30, store=shared_store)
    limiter_b = LoginRateLimiter(max_attempts=2, base_block_seconds=30, max_block_seconds=30, store=shared_store)

    limiter_a.register_failure(ip="20.0.0.1", username="carol", now=1.0)
    limiter_a.register_failure(ip="20.0.0.1", username="carol", now=2.0)

    assert limiter_b.is_blocked(ip="20.0.0.1", username="carol", now=3.0)


def test_shared_store_exposes_consistent_metrics_snapshot():
    shared_store = InMemoryRateLimitStore()
    limiter_a = LoginRateLimiter(store=shared_store)
    limiter_b = LoginRateLimiter(store=shared_store)

    limiter_a.register_failure(ip="40.0.0.1", username="dana", now=1.0)
    limiter_b.is_blocked(ip="40.0.0.1", username="dana", now=1.1)

    metrics = limiter_a.metrics_snapshot()
    assert metrics["failed_attempts_total"] == 1
    assert metrics["failed_attempts_ip_total"] == 1
    assert metrics["failed_attempts_user_total"] == 1
    assert metrics["blocked_requests_total"] == 0


def _build_request(*, client_host: str, headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "path": "/token",
        "raw_path": b"/token",
        "query_string": b"",
        "headers": headers or [],
        "client": (client_host, 4242),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope)


def test_client_ip_ignores_forwarding_headers_without_trusted_proxy(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXIES", raising=False)
    request = _build_request(
        client_host="203.0.113.10",
        headers=[(b"x-forwarded-for", b"198.51.100.7")],
    )

    assert get_client_ip(request) == "203.0.113.10"


def test_client_ip_uses_forwarding_headers_with_trusted_proxy(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "203.0.113.10")
    request = _build_request(
        client_host="203.0.113.10",
        headers=[(b"x-forwarded-for", b"198.51.100.7, 203.0.113.10")],
    )

    assert get_client_ip(request) == "198.51.100.7"


def test_client_ip_prioritizes_forwarded_header_over_xff(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "203.0.113.10")
    request = _build_request(
        client_host="203.0.113.10",
        headers=[
            (b"forwarded", b'for="198.51.100.9";proto=https;by=proxy'),
            (b"x-forwarded-for", b"198.51.100.7"),
        ],
    )

    assert get_client_ip(request) == "198.51.100.9"
