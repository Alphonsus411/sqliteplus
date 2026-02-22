"""Utilidades para normalizar valores antes de serializarlos en JSON."""

from __future__ import annotations

import base64
import math
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any


def normalize_json_value(value: Any) -> Any:
    """Convierte valores complejos en representaciones compatibles con JSON."""

    if isinstance(value, memoryview):
        value = value.tobytes()

    if isinstance(value, (bytes, bytearray)):
        return "base64:" + base64.b64encode(value).decode("ascii")

    if isinstance(value, Decimal):
        try:
            float_value = float(value)
        except (ValueError, OverflowError):
            return str(value)
        else:
            if math.isfinite(float_value):
                return float_value
            return str(value)

    if isinstance(value, (datetime, date, time)):
        return value.isoformat()

    return value


__all__ = ["normalize_json_value"]
