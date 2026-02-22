from sqliteplus.auth.rate_limit import LoginRateLimiter


def test_rate_limiter_prunes_inactive_states_with_amortized_schedule():
    limiter = LoginRateLimiter(
        max_attempts=3,
        window_seconds=5,
        base_block_seconds=1,
        max_block_seconds=10,
        state_ttl_seconds=10,
        prune_every_ops=3,
    )

    limiter.register_failure(ip="10.0.0.1", username="alice", now=1.0)
    assert limiter.metrics_snapshot()["ip_states_size"] == 1
    assert limiter.metrics_snapshot()["user_states_size"] == 1

    limiter.is_blocked(ip="other-ip", username=None, now=12.0)
    assert limiter.metrics_snapshot()["ip_states_size"] == 1

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
        prune_every_ops=1,
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


def test_rate_limiter_applies_max_states_with_lru_eviction():
    limiter = LoginRateLimiter(
        max_attempts=5,
        window_seconds=60,
        base_block_seconds=1,
        max_block_seconds=2,
        state_ttl_seconds=1000,
        prune_every_ops=1,
        max_states=2,
    )

    limiter.register_failure(ip="ip-1", username="user-1", now=1.0)
    limiter.register_failure(ip="ip-2", username="user-2", now=2.0)
    limiter.register_failure(ip="ip-1", username="user-1", now=3.0)
    limiter.register_failure(ip="ip-3", username="user-3", now=4.0)

    assert "ip-1" in limiter._ip_states
    assert "ip-2" not in limiter._ip_states
    assert "ip-3" in limiter._ip_states
    assert "user-1" in limiter._user_states
    assert "user-2" not in limiter._user_states
    assert "user-3" in limiter._user_states

    metrics = limiter.metrics_snapshot()
    assert metrics["ip_states_size"] == 2
    assert metrics["user_states_size"] == 2


def test_rate_limiter_preserves_progressive_blocking_behavior():
    limiter = LoginRateLimiter(
        max_attempts=2,
        window_seconds=30,
        base_block_seconds=5,
        max_block_seconds=20,
        state_ttl_seconds=300,
        prune_every_ops=2,
    )

    limiter.register_failure(ip="127.0.0.1", username="admin", now=1.0)
    limiter.register_failure(ip="127.0.0.1", username="admin", now=2.0)

    state = limiter._ip_states["127.0.0.1"]
    assert state.blocked_until == 7.0
    assert state.penalty_level == 1

    limiter.register_failure(ip="127.0.0.1", username="admin", now=8.0)
    limiter.register_failure(ip="127.0.0.1", username="admin", now=9.0)

    state = limiter._ip_states["127.0.0.1"]
    assert state.blocked_until == 19.0
    assert state.penalty_level == 2
