from __future__ import annotations

import logging
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Deque

logger = logging.getLogger(__name__)


@dataclass
class AttemptState:
    failures: Deque[float] = field(default_factory=deque)
    blocked_until: float = 0.0
    penalty_level: int = 0
    last_seen: float = 0.0


class LoginRateLimiter:
    """Rate limiter en memoria para proteger el endpoint /token.

    Aplica límites por IP y por usuario con bloqueo progresivo.
    """

    def __init__(
        self,
        *,
        max_attempts: int = 5,
        window_seconds: int = 60,
        base_block_seconds: int = 30,
        max_block_seconds: int = 900,
        state_ttl_seconds: int = 1800,
        prune_every_ops: int = 64,
        max_states: int | None = None,
    ) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.base_block_seconds = base_block_seconds
        self.max_block_seconds = max_block_seconds
        self.state_ttl_seconds = state_ttl_seconds
        self.prune_every_ops = max(1, prune_every_ops)
        self.max_states = max_states

        self._ip_states: dict[str, AttemptState] = {}
        self._user_states: dict[str, AttemptState] = {}
        self._ops_since_prune = 0

        self.failed_attempts_total = 0
        self.blocked_requests_total = 0
        self.rate_limit_triggered_total = 0
        self.failed_by_ip: Counter[str] = Counter()
        self.failed_by_user: Counter[str] = Counter()

    def _purge_window(self, state: AttemptState, now: float) -> None:
        lower_bound = now - self.window_seconds
        while state.failures and state.failures[0] < lower_bound:
            state.failures.popleft()

    def _is_state_blocked(self, state: AttemptState, now: float) -> bool:
        state.last_seen = now
        self._purge_window(state, now)
        if state.blocked_until > now:
            return True
        return False

    def _register_failure_state(self, state: AttemptState, now: float) -> bool:
        state.last_seen = now
        self._purge_window(state, now)
        state.failures.append(now)

        if len(state.failures) >= self.max_attempts:
            state.penalty_level += 1
            duration = min(
                self.base_block_seconds * (2 ** (state.penalty_level - 1)),
                self.max_block_seconds,
            )
            state.blocked_until = max(state.blocked_until, now + duration)
            state.failures.clear()
            return True
        return False

    def _maybe_prune_states(self, now: float) -> None:
        self._ops_since_prune += 1
        if self._ops_since_prune < self.prune_every_ops:
            return
        self._ops_since_prune = 0
        self._prune_states(now)

    def _prune_states(self, now: float) -> None:
        ttl_cutoff = now - self.state_ttl_seconds
        self._prune_state_dict(self._ip_states, ttl_cutoff, now)
        self._prune_state_dict(self._user_states, ttl_cutoff, now)

    def _prune_state_dict(
        self,
        states: dict[str, AttemptState],
        ttl_cutoff: float,
        now: float,
    ) -> None:
        stale_keys: list[str] = []
        for key, state in states.items():
            self._purge_window(state, now)
            if state.blocked_until <= now and not state.failures and state.last_seen < ttl_cutoff:
                stale_keys.append(key)

        for key in stale_keys:
            states.pop(key, None)

        if self.max_states is None or len(states) <= self.max_states:
            return

        candidates = [
            (key, state.last_seen)
            for key, state in states.items()
            if state.blocked_until <= now
        ]
        candidates.sort(key=lambda item: item[1])

        overflow = len(states) - self.max_states
        removed = 0
        for key, _ in candidates:
            states.pop(key, None)
            removed += 1
            if removed >= overflow:
                break

        if len(states) > self.max_states:
            hard_candidates = sorted(
                ((key, state.last_seen) for key, state in states.items()),
                key=lambda item: item[1],
            )
            remaining_overflow = len(states) - self.max_states
            for key, _ in hard_candidates[:remaining_overflow]:
                states.pop(key, None)

    def is_blocked(self, *, ip: str, username: str | None, now: float | None = None) -> bool:
        current = now if now is not None else time.time()
        self._maybe_prune_states(current)

        blocked = False
        ip_state = self._ip_states.get(ip)
        if ip_state and self._is_state_blocked(ip_state, current):
            blocked = True

        if username:
            user_state = self._user_states.get(username)
            if user_state and self._is_state_blocked(user_state, current):
                blocked = True

        if blocked:
            self.blocked_requests_total += 1
        return blocked

    def register_failure(self, *, ip: str, username: str | None, now: float | None = None) -> None:
        current = now if now is not None else time.time()
        self._maybe_prune_states(current)
        self.failed_attempts_total += 1
        self.failed_by_ip[ip] += 1
        if username:
            self.failed_by_user[username] += 1

        ip_state = self._ip_states.setdefault(ip, AttemptState())
        ip_limited = self._register_failure_state(ip_state, current)

        user_limited = False
        if username:
            user_state = self._user_states.setdefault(username, AttemptState())
            user_limited = self._register_failure_state(user_state, current)

        if ip_limited or user_limited:
            self.rate_limit_triggered_total += 1

        if self.max_states is not None:
            self._prune_states(current)

    def register_success(self, *, ip: str, username: str | None) -> None:
        current = time.time()
        self._maybe_prune_states(current)
        ip_state = self._ip_states.get(ip)
        if ip_state:
            ip_state.failures.clear()
            ip_state.penalty_level = 0
            ip_state.blocked_until = 0.0
            ip_state.last_seen = current

        if username:
            user_state = self._user_states.get(username)
            if user_state:
                user_state.failures.clear()
                user_state.penalty_level = 0
                user_state.blocked_until = 0.0
                user_state.last_seen = current

    def metrics_snapshot(self) -> dict[str, object]:
        return {
            "failed_attempts_total": self.failed_attempts_total,
            "blocked_requests_total": self.blocked_requests_total,
            "rate_limit_triggered_total": self.rate_limit_triggered_total,
            "ip_states_size": len(self._ip_states),
            "user_states_size": len(self._user_states),
            "failed_by_ip": dict(self.failed_by_ip),
            "failed_by_user": dict(self.failed_by_user),
        }

    def reset(
        self,
        *,
        max_attempts: int | None = None,
        window_seconds: int | None = None,
        base_block_seconds: int | None = None,
        max_block_seconds: int | None = None,
        state_ttl_seconds: int | None = None,
        prune_every_ops: int | None = None,
        max_states: int | None = None,
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
        if prune_every_ops is not None:
            self.prune_every_ops = max(1, prune_every_ops)
        self.max_states = max_states

        self._ip_states.clear()
        self._user_states.clear()
        self.failed_attempts_total = 0
        self.blocked_requests_total = 0
        self.rate_limit_triggered_total = 0
        self.failed_by_ip.clear()
        self.failed_by_user.clear()
        self._ops_since_prune = 0


login_rate_limiter = LoginRateLimiter()


def reset_login_rate_limiter(**kwargs: int) -> None:
    login_rate_limiter.reset(**kwargs)


def get_login_rate_limit_metrics() -> dict[str, object]:
    return login_rate_limiter.metrics_snapshot()
