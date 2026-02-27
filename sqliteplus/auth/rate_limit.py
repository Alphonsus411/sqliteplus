from __future__ import annotations

import os
import time

from sqliteplus.auth.rate_limit_store import (
    RateLimitConfig,
    RateLimitStore,
    create_rate_limit_store,
)


class LoginRateLimiter:
    """Rate limiter para proteger el endpoint /token desacoplado del almacenamiento."""

    def __init__(
        self,
        *,
        max_attempts: int = 5,
        window_seconds: int = 60,
        base_block_seconds: int = 30,
        max_block_seconds: int = 900,
        state_ttl_seconds: int = 1800,
        metrics_ttl_seconds: int | None = None,
        max_states: int | None = None,
        max_metrics_keys: int = 1024,
        prune_every_ops: int | None = None,
        store: RateLimitStore | None = None,
    ) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.base_block_seconds = base_block_seconds
        self.max_block_seconds = max_block_seconds
        self.state_ttl_seconds = state_ttl_seconds
        self.metrics_ttl_seconds = state_ttl_seconds if metrics_ttl_seconds is None else metrics_ttl_seconds
        self.max_states = max_states
        self.max_metrics_keys = max(1, max_metrics_keys)
        self.prune_every_ops = prune_every_ops
        self._store = store or _create_store_from_env()

    def _config(self) -> RateLimitConfig:
        return RateLimitConfig(
            max_attempts=self.max_attempts,
            window_seconds=self.window_seconds,
            base_block_seconds=self.base_block_seconds,
            max_block_seconds=self.max_block_seconds,
            state_ttl_seconds=self.state_ttl_seconds,
            metrics_ttl_seconds=self.metrics_ttl_seconds,
            max_states=self.max_states,
            max_metrics_keys=self.max_metrics_keys,
        )

    def is_blocked(self, *, ip: str, username: str | None, now: float | None = None) -> bool:
        current = now if now is not None else time.time()
        return self._store.is_blocked(ip=ip, username=username, config=self._config(), now=current)

    def register_failure(self, *, ip: str, username: str | None, now: float | None = None) -> None:
        current = now if now is not None else time.time()
        self._store.register_failure(ip=ip, username=username, config=self._config(), now=current)

    def register_success(self, *, ip: str, username: str | None, now: float | None = None) -> None:
        current = now if now is not None else time.time()
        self._store.register_success(ip=ip, username=username, config=self._config(), now=current)

    def metrics_snapshot(self) -> dict[str, object]:
        return self._store.metrics_snapshot(config=self._config(), now=time.time())

    def reset(
        self,
        *,
        max_attempts: int | None = None,
        window_seconds: int | None = None,
        base_block_seconds: int | None = None,
        max_block_seconds: int | None = None,
        state_ttl_seconds: int | None = None,
        metrics_ttl_seconds: int | None = None,
        max_states: int | None = None,
        max_metrics_keys: int | None = None,
        prune_every_ops: int | None = None,
        store: RateLimitStore | None = None,
    ) -> None:
        if max_attempts is not None:
            self.max_attempts = max_attempts
        if window_seconds is not None:
            self.window_seconds = window_seconds
        if base_block_seconds is not None:
            self.base_block_seconds = base_block_seconds
        if max_block_seconds is not None:
            self.max_block_seconds = max_block_seconds
        if state_ttl_seconds is not None:
            self.state_ttl_seconds = state_ttl_seconds
            if metrics_ttl_seconds is None:
                self.metrics_ttl_seconds = state_ttl_seconds
        if metrics_ttl_seconds is not None:
            self.metrics_ttl_seconds = metrics_ttl_seconds
        self.max_states = max_states
        if max_metrics_keys is not None:
            self.max_metrics_keys = max(1, max_metrics_keys)
        if prune_every_ops is not None:
            self.prune_every_ops = prune_every_ops

        self._store = store or self._store
        self._store.reset()



def _create_store_from_env() -> RateLimitStore:
    backend = os.getenv("SQLITEPLUS_RATE_LIMIT_BACKEND", "memory")
    redis_url = os.getenv("SQLITEPLUS_RATE_LIMIT_REDIS_URL")
    return create_rate_limit_store(backend=backend, redis_url=redis_url)


login_rate_limiter = LoginRateLimiter()


def reset_login_rate_limiter(**kwargs: int) -> None:
    login_rate_limiter.reset(**kwargs)


def get_login_rate_limit_metrics() -> dict[str, object]:
    return login_rate_limiter.metrics_snapshot()
