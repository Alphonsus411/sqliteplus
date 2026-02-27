from __future__ import annotations

import ipaddress
import os
from typing import Iterable

from fastapi import Request


_TRUSTED_PROXIES_ENV = "TRUSTED_PROXIES"


def _parse_trusted_proxies(raw_value: str | None) -> tuple[ipaddress._BaseNetwork, ...]:
    if not raw_value:
        return ()

    parsed_networks: list[ipaddress._BaseNetwork] = []
    for token in raw_value.split(","):
        candidate = token.strip()
        if not candidate:
            continue
        try:
            parsed_networks.append(ipaddress.ip_network(candidate, strict=False))
        except ValueError:
            continue
    return tuple(parsed_networks)


def _extract_remote_addr(request: Request) -> str:
    client = request.scope.get("client")
    if client and isinstance(client, tuple) and client[0]:
        return str(client[0])
    if request.client and request.client.host:
        return str(request.client.host)
    return "unknown"


def _is_trusted_proxy(remote_addr: str, trusted_proxies: Iterable[ipaddress._BaseNetwork]) -> bool:
    try:
        remote_ip = ipaddress.ip_address(remote_addr)
    except ValueError:
        return False
    return any(remote_ip in network for network in trusted_proxies)


def _normalize_ip_candidate(value: str) -> str | None:
    candidate = value.strip().strip('"')
    if not candidate or candidate.lower() == "unknown":
        return None

    if candidate.startswith("[") and "]" in candidate:
        candidate = candidate[1:candidate.index("]")]

    if ":" in candidate and candidate.count(":") == 1 and "." in candidate:
        maybe_ip, maybe_port = candidate.rsplit(":", 1)
        if maybe_port.isdigit():
            candidate = maybe_ip

    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def _ip_from_x_forwarded_for(header_value: str | None) -> str | None:
    if not header_value:
        return None

    for item in header_value.split(","):
        parsed = _normalize_ip_candidate(item)
        if parsed:
            return parsed
    return None


def _ip_from_forwarded(header_value: str | None) -> str | None:
    if not header_value:
        return None

    for field_value in header_value.split(","):
        directives = field_value.split(";")
        for directive in directives:
            key, sep, value = directive.partition("=")
            if sep != "=" or key.strip().lower() != "for":
                continue
            parsed = _normalize_ip_candidate(value)
            if parsed:
                return parsed
    return None


def get_client_ip(request: Request) -> str:
    """Resuelve IP de cliente de forma segura detrás de proxies confiables.

    - Por defecto no confía en cabeceras de forwarding.
    - Solo evalúa `Forwarded`/`X-Forwarded-For` si la IP remota (`REMOTE_ADDR`)
      pertenece a `TRUSTED_PROXIES`.
    """

    remote_addr = _extract_remote_addr(request)
    trusted_proxies = _parse_trusted_proxies(os.getenv(_TRUSTED_PROXIES_ENV))

    if not _is_trusted_proxy(remote_addr, trusted_proxies):
        return remote_addr

    forwarded_ip = _ip_from_forwarded(request.headers.get("forwarded"))
    if forwarded_ip:
        return forwarded_ip

    xff_ip = _ip_from_x_forwarded_for(request.headers.get("x-forwarded-for"))
    if xff_ip:
        return xff_ip

    return remote_addr
