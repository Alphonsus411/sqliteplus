from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import Deque

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimitConfig:
    max_attempts: int = 5
    window_seconds: int = 60
    base_block_seconds: int = 30
    max_block_seconds: int = 900
    state_ttl_seconds: int = 1800
    metrics_ttl_seconds: int = 1800
    max_states: int | None = None
    max_metrics_keys: int = 1024


@dataclass
class AttemptState:
    failures: Deque[float] = field(default_factory=deque)
    blocked_until: float = 0.0
    penalty_level: int = 0
    last_seen: float = 0.0


@dataclass
class MetricState:
    failures: int = 0
    last_seen: float = 0.0


class RateLimitStore(ABC):
    @abstractmethod
    def is_blocked(self, *, ip: str, username: str | None, config: RateLimitConfig, now: float) -> bool:
        raise NotImplementedError

    @abstractmethod
    def register_failure(self, *, ip: str, username: str | None, config: RateLimitConfig, now: float) -> None:
        raise NotImplementedError

    @abstractmethod
    def register_success(self, *, ip: str, username: str | None, config: RateLimitConfig, now: float) -> None:
        raise NotImplementedError

    @abstractmethod
    def metrics_snapshot(self, *, config: RateLimitConfig, now: float) -> dict[str, object]:
        raise NotImplementedError

    @abstractmethod
    def reset(self) -> None:
        raise NotImplementedError


class InMemoryRateLimitStore(RateLimitStore):
    def __init__(self) -> None:
        self._ip_states: dict[str, AttemptState] = {}
        self._user_states: dict[str, AttemptState] = {}
        self.failed_attempts_total = 0
        self.failed_attempts_ip_total = 0
        self.failed_attempts_user_total = 0
        self.blocked_requests_total = 0
        self.rate_limit_triggered_total = 0
        self._metrics_by_ip: OrderedDict[str, MetricState] = OrderedDict()
        self._metrics_by_user: OrderedDict[str, MetricState] = OrderedDict()
        self.metrics_dropped_total = 0

    def _record_metric_failure(
        self,
        metrics: OrderedDict[str, MetricState],
        key: str,
        now: float,
        *,
        max_metrics_keys: int,
    ) -> None:
        entry = metrics.pop(key, None)
        if entry is None:
            entry = MetricState()
        entry.failures += 1
        entry.last_seen = now
        metrics[key] = entry

        while len(metrics) > max_metrics_keys:
            metrics.popitem(last=False)
            self.metrics_dropped_total += 1

    def _purge_window(self, state: AttemptState, *, now: float, config: RateLimitConfig) -> None:
        lower_bound = now - config.window_seconds
        while state.failures and state.failures[0] < lower_bound:
            state.failures.popleft()

    def _is_state_blocked(self, state: AttemptState, *, now: float, config: RateLimitConfig) -> bool:
        state.last_seen = now
        self._purge_window(state, now=now, config=config)
        return state.blocked_until > now

    def _register_failure_state(self, state: AttemptState, *, now: float, config: RateLimitConfig) -> bool:
        state.last_seen = now
        self._purge_window(state, now=now, config=config)
        state.failures.append(now)

        if len(state.failures) >= config.max_attempts:
            state.penalty_level += 1
            duration = min(
                config.base_block_seconds * (2 ** (state.penalty_level - 1)),
                config.max_block_seconds,
            )
            state.blocked_until = max(state.blocked_until, now + duration)
            state.failures.clear()
            return True
        return False

    def _prune_state_dict(self, states: dict[str, AttemptState], *, now: float, config: RateLimitConfig) -> None:
        ttl_cutoff = now - config.state_ttl_seconds
        stale_keys: list[str] = []
        for key, state in states.items():
            self._purge_window(state, now=now, config=config)
            if state.blocked_until <= now and not state.failures and state.last_seen < ttl_cutoff:
                stale_keys.append(key)

        for key in stale_keys:
            states.pop(key, None)

        if config.max_states is None or len(states) <= config.max_states:
            return

        candidates = [
            (key, state.last_seen)
            for key, state in states.items()
            if state.blocked_until <= now
        ]
        candidates.sort(key=lambda item: item[1])

        overflow = len(states) - config.max_states
        for key, _ in candidates[:overflow]:
            states.pop(key, None)

    def _prune_metrics(self, metrics: OrderedDict[str, MetricState], *, now: float, config: RateLimitConfig) -> None:
        ttl_cutoff = now - config.metrics_ttl_seconds
        stale_keys = [key for key, state in metrics.items() if state.last_seen < ttl_cutoff]
        for key in stale_keys:
            metrics.pop(key, None)

        while len(metrics) > config.max_metrics_keys:
            metrics.popitem(last=False)
            self.metrics_dropped_total += 1

    def _prune(self, *, now: float, config: RateLimitConfig) -> None:
        self._prune_state_dict(self._ip_states, now=now, config=config)
        self._prune_state_dict(self._user_states, now=now, config=config)
        self._prune_metrics(self._metrics_by_ip, now=now, config=config)
        self._prune_metrics(self._metrics_by_user, now=now, config=config)

    def is_blocked(self, *, ip: str, username: str | None, config: RateLimitConfig, now: float) -> bool:
        self._prune(now=now, config=config)
        blocked = False
        ip_state = self._ip_states.get(ip)
        if ip_state and self._is_state_blocked(ip_state, now=now, config=config):
            blocked = True

        if username:
            user_state = self._user_states.get(username)
            if user_state and self._is_state_blocked(user_state, now=now, config=config):
                blocked = True

        if blocked:
            self.blocked_requests_total += 1
        return blocked

    def register_failure(self, *, ip: str, username: str | None, config: RateLimitConfig, now: float) -> None:
        self._prune(now=now, config=config)
        self.failed_attempts_total += 1
        self.failed_attempts_ip_total += 1
        self._record_metric_failure(
            self._metrics_by_ip,
            ip,
            now,
            max_metrics_keys=config.max_metrics_keys,
        )
        if username:
            self.failed_attempts_user_total += 1
            self._record_metric_failure(
                self._metrics_by_user,
                username,
                now,
                max_metrics_keys=config.max_metrics_keys,
            )

        ip_state = self._ip_states.setdefault(ip, AttemptState())
        ip_limited = self._register_failure_state(ip_state, now=now, config=config)

        user_limited = False
        if username:
            user_state = self._user_states.setdefault(username, AttemptState())
            user_limited = self._register_failure_state(user_state, now=now, config=config)

        if ip_limited or user_limited:
            self.rate_limit_triggered_total += 1

    def register_success(self, *, ip: str, username: str | None, config: RateLimitConfig, now: float) -> None:
        self._prune(now=now, config=config)
        ip_state = self._ip_states.get(ip)
        if ip_state:
            ip_state.failures.clear()
            ip_state.penalty_level = 0
            ip_state.blocked_until = 0.0
            ip_state.last_seen = now

        if username:
            user_state = self._user_states.get(username)
            if user_state:
                user_state.failures.clear()
                user_state.penalty_level = 0
                user_state.blocked_until = 0.0
                user_state.last_seen = now

    def metrics_snapshot(self, *, config: RateLimitConfig, now: float) -> dict[str, object]:
        return {
            "failed_attempts_total": self.failed_attempts_total,
            "failed_attempts_ip_total": self.failed_attempts_ip_total,
            "failed_attempts_user_total": self.failed_attempts_user_total,
            "blocked_requests_total": self.blocked_requests_total,
            "rate_limit_triggered_total": self.rate_limit_triggered_total,
            "ip_states_size": len(self._ip_states),
            "user_states_size": len(self._user_states),
            "retained_failed_by_ip": {
                key: state.failures for key, state in self._metrics_by_ip.items()
            },
            "retained_failed_by_user": {
                key: state.failures for key, state in self._metrics_by_user.items()
            },
            "metrics_ip_size": len(self._metrics_by_ip),
            "metrics_user_size": len(self._metrics_by_user),
            "metrics_dropped_total": self.metrics_dropped_total,
            "failed_by_ip": {key: state.failures for key, state in self._metrics_by_ip.items()},
            "failed_by_user": {key: state.failures for key, state in self._metrics_by_user.items()},
        }

    def reset(self) -> None:
        self._ip_states.clear()
        self._user_states.clear()
        self.failed_attempts_total = 0
        self.failed_attempts_ip_total = 0
        self.failed_attempts_user_total = 0
        self.blocked_requests_total = 0
        self.rate_limit_triggered_total = 0
        self._metrics_by_ip.clear()
        self._metrics_by_user.clear()
        self.metrics_dropped_total = 0


class RedisRateLimitStore(RateLimitStore):
    def __init__(self, redis_url: str, *, namespace: str = "sqliteplus:rate_limit") -> None:
        try:
            import redis
        except ImportError as exc:  # pragma: no cover - dependencia opcional
            raise RuntimeError("Redis backend requires redis package") from exc

        self._redis = redis.Redis.from_url(redis_url, decode_responses=True)
        self._namespace = namespace

    def _state_key(self, kind: str, key: str) -> str:
        return f"{self._namespace}:state:{kind}:{key}"

    def _metrics_hash_key(self, kind: str) -> str:
        return f"{self._namespace}:metrics:{kind}"

    def _metrics_seen_key(self, kind: str) -> str:
        return f"{self._namespace}:metrics_seen:{kind}"

    def _counter_key(self) -> str:
        return f"{self._namespace}:counters"

    def _all_keys_pattern(self) -> str:
        return f"{self._namespace}:*"

    def _load_state(self, kind: str, key: str, now: float, config: RateLimitConfig) -> dict[str, object]:
        state_key = self._state_key(kind, key)
        payload = self._redis.get(state_key)
        if not payload:
            return {"failures": [], "blocked_until": 0.0, "penalty_level": 0, "last_seen": now}
        state = json.loads(payload)
        failures = [ts for ts in state.get("failures", []) if ts >= (now - config.window_seconds)]
        return {
            "failures": failures,
            "blocked_until": float(state.get("blocked_until", 0.0)),
            "penalty_level": int(state.get("penalty_level", 0)),
            "last_seen": float(state.get("last_seen", now)),
        }

    def _save_state(self, kind: str, key: str, state: dict[str, object], config: RateLimitConfig) -> None:
        state_key = self._state_key(kind, key)
        ttl_seconds = max(1, config.state_ttl_seconds)
        self._redis.setex(state_key, ttl_seconds, json.dumps(state))

    def _update_metric(self, kind: str, key: str, now: float, config: RateLimitConfig) -> None:
        hash_key = self._metrics_hash_key(kind)
        seen_key = self._metrics_seen_key(kind)
        self._redis.hincrby(hash_key, key, 1)
        self._redis.zadd(seen_key, {key: now})
        ttl_cutoff = now - config.metrics_ttl_seconds
        stale_keys = self._redis.zrangebyscore(seen_key, "-inf", ttl_cutoff)
        if stale_keys:
            self._redis.zrem(seen_key, *stale_keys)
            self._redis.hdel(hash_key, *stale_keys)

        metric_size = self._redis.zcard(seen_key)
        if metric_size > config.max_metrics_keys:
            overflow = metric_size - config.max_metrics_keys
            old_keys = self._redis.zrange(seen_key, 0, overflow - 1)
            if old_keys:
                self._redis.zrem(seen_key, *old_keys)
                self._redis.hdel(hash_key, *old_keys)
                self._redis.hincrby(self._counter_key(), "metrics_dropped_total", len(old_keys))

    def is_blocked(self, *, ip: str, username: str | None, config: RateLimitConfig, now: float) -> bool:
        blocked = False
        for kind, key in (("ip", ip), ("user", username)):
            if not key:
                continue
            state = self._load_state(kind, key, now, config)
            if state["blocked_until"] > now:
                blocked = True
                break

        if blocked:
            self._redis.hincrby(self._counter_key(), "blocked_requests_total", 1)
        return blocked

    def _register_failure_for_key(self, kind: str, key: str, now: float, config: RateLimitConfig) -> bool:
        state = self._load_state(kind, key, now, config)
        failures = state["failures"]
        failures.append(now)
        state["last_seen"] = now
        limited = False
        if len(failures) >= config.max_attempts:
            penalty_level = int(state["penalty_level"]) + 1
            state["penalty_level"] = penalty_level
            duration = min(config.base_block_seconds * (2 ** (penalty_level - 1)), config.max_block_seconds)
            state["blocked_until"] = max(float(state["blocked_until"]), now + duration)
            state["failures"] = []
            limited = True
        else:
            state["failures"] = failures
        self._save_state(kind, key, state, config)
        return limited

    def register_failure(self, *, ip: str, username: str | None, config: RateLimitConfig, now: float) -> None:
        self._redis.hincrby(self._counter_key(), "failed_attempts_total", 1)
        self._redis.hincrby(self._counter_key(), "failed_attempts_ip_total", 1)
        self._update_metric("ip", ip, now, config)
        ip_limited = self._register_failure_for_key("ip", ip, now, config)
        user_limited = False
        if username:
            self._redis.hincrby(self._counter_key(), "failed_attempts_user_total", 1)
            self._update_metric("user", username, now, config)
            user_limited = self._register_failure_for_key("user", username, now, config)

        if ip_limited or user_limited:
            self._redis.hincrby(self._counter_key(), "rate_limit_triggered_total", 1)

    def register_success(self, *, ip: str, username: str | None, config: RateLimitConfig, now: float) -> None:
        for kind, key in (("ip", ip), ("user", username)):
            if not key:
                continue
            state = self._load_state(kind, key, now, config)
            state["failures"] = []
            state["blocked_until"] = 0.0
            state["penalty_level"] = 0
            state["last_seen"] = now
            self._save_state(kind, key, state, config)

    def metrics_snapshot(self, *, config: RateLimitConfig, now: float) -> dict[str, object]:
        counter_key = self._counter_key()
        with self._redis.pipeline(transaction=True) as pipe:
            pipe.hgetall(counter_key)
            pipe.hgetall(self._metrics_hash_key("ip"))
            pipe.hgetall(self._metrics_hash_key("user"))
            pipe.keys(self._state_key("ip", "*"))
            pipe.keys(self._state_key("user", "*"))
            counters, metrics_ip, metrics_user, ip_states, user_states = pipe.execute()

        return {
            "failed_attempts_total": int(counters.get("failed_attempts_total", 0)),
            "failed_attempts_ip_total": int(counters.get("failed_attempts_ip_total", 0)),
            "failed_attempts_user_total": int(counters.get("failed_attempts_user_total", 0)),
            "blocked_requests_total": int(counters.get("blocked_requests_total", 0)),
            "rate_limit_triggered_total": int(counters.get("rate_limit_triggered_total", 0)),
            "ip_states_size": len(ip_states),
            "user_states_size": len(user_states),
            "retained_failed_by_ip": {key: int(value) for key, value in metrics_ip.items()},
            "retained_failed_by_user": {key: int(value) for key, value in metrics_user.items()},
            "metrics_ip_size": len(metrics_ip),
            "metrics_user_size": len(metrics_user),
            "metrics_dropped_total": int(counters.get("metrics_dropped_total", 0)),
            "failed_by_ip": {key: int(value) for key, value in metrics_ip.items()},
            "failed_by_user": {key: int(value) for key, value in metrics_user.items()},
        }

    def reset(self) -> None:
        keys = self._redis.keys(self._all_keys_pattern())
        if keys:
            self._redis.delete(*keys)


def create_rate_limit_store(backend: str | None, redis_url: str | None) -> RateLimitStore:
    normalized = (backend or "memory").strip().lower()
    if normalized == "redis":
        if not redis_url:
            logger.warning("Redis rate limit backend seleccionado sin SQLITEPLUS_RATE_LIMIT_REDIS_URL; se usa memoria.")
            return InMemoryRateLimitStore()
        try:
            return RedisRateLimitStore(redis_url)
        except Exception as exc:  # pragma: no cover - fallback defensivo
            logger.warning("No se pudo inicializar backend Redis (%s); se usa memoria.", exc)
            return InMemoryRateLimitStore()
    return InMemoryRateLimitStore()
