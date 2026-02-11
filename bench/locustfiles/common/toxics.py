"""Toxiproxy helpers — apply and remove toxics on a timed schedule.

Provides a simple API for benchmark scenarios to inject faults
via the Toxiproxy REST API.
"""

from __future__ import annotations

import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

TOXIPROXY_HOST = os.environ.get("TOXIPROXY_HOST", "toxiproxy")
TOXIPROXY_API = f"http://{TOXIPROXY_HOST}:8474"


def _url(path: str) -> str:
    return f"{TOXIPROXY_API}{path}"


def add_toxic(
    proxy_name: str,
    toxic_type: str,
    toxic_name: str | None = None,
    stream: str = "downstream",
    toxicity: float = 1.0,
    attributes: dict | None = None,
) -> dict:
    """Add a toxic to a proxy.

    Args:
        proxy_name: Name of the proxy (e.g., "clickhouse", "redis").
        toxic_type: Type of toxic (e.g., "latency", "timeout", "bandwidth").
        toxic_name: Optional name for the toxic (defaults to type_stream).
        stream: "downstream" or "upstream".
        toxicity: Probability of the toxic being applied (0.0-1.0).
        attributes: Toxic-specific attributes (e.g., {"latency": 500}).

    Returns:
        The created toxic definition.
    """
    toxic_name = toxic_name or f"{toxic_type}_{stream}"
    payload = {
        "name": toxic_name,
        "type": toxic_type,
        "stream": stream,
        "toxicity": toxicity,
        "attributes": attributes or {},
    }
    resp = requests.post(
        _url(f"/proxies/{proxy_name}/toxics"),
        json=payload,
        timeout=5,
    )
    resp.raise_for_status()
    result = resp.json()
    logger.info("Added toxic %s to %s: %s", toxic_name, proxy_name, result)
    return result


def remove_toxic(proxy_name: str, toxic_name: str) -> None:
    """Remove a toxic from a proxy."""
    resp = requests.delete(
        _url(f"/proxies/{proxy_name}/toxics/{toxic_name}"),
        timeout=5,
    )
    resp.raise_for_status()
    logger.info("Removed toxic %s from %s", toxic_name, proxy_name)


def remove_all_toxics(proxy_name: str) -> None:
    """Remove all toxics from a proxy."""
    resp = requests.get(_url(f"/proxies/{proxy_name}"), timeout=5)
    resp.raise_for_status()
    proxy = resp.json()
    for toxic in proxy.get("toxics", []):
        remove_toxic(proxy_name, toxic["name"])


def reset_all_proxies() -> None:
    """Remove all toxics from all proxies."""
    resp = requests.get(_url("/proxies"), timeout=5)
    resp.raise_for_status()
    proxies = resp.json()
    for proxy_name in proxies:
        remove_all_toxics(proxy_name)
    logger.info("Reset all proxies")


def apply_latency(
    proxy_name: str,
    latency_ms: int,
    jitter_ms: int = 0,
    toxic_name: str | None = None,
) -> dict:
    """Add latency to a proxy."""
    return add_toxic(
        proxy_name=proxy_name,
        toxic_type="latency",
        toxic_name=toxic_name or f"{proxy_name}_latency",
        attributes={"latency": latency_ms, "jitter": jitter_ms},
    )


def apply_timeout(
    proxy_name: str,
    timeout_ms: int = 0,
    toxic_name: str | None = None,
) -> dict:
    """Add a timeout toxic (drops connections after timeout_ms, 0=immediate)."""
    return add_toxic(
        proxy_name=proxy_name,
        toxic_type="timeout",
        toxic_name=toxic_name or f"{proxy_name}_timeout",
        attributes={"timeout": timeout_ms},
    )


def timed_toxic(
    proxy_name: str,
    toxic_type: str,
    duration_seconds: float,
    attributes: dict | None = None,
    toxic_name: str | None = None,
) -> None:
    """Apply a toxic for a fixed duration, then remove it.

    This is a blocking call — use it from a background thread/greenlet.
    """
    name = toxic_name or f"{proxy_name}_{toxic_type}_timed"
    add_toxic(
        proxy_name=proxy_name,
        toxic_type=toxic_type,
        toxic_name=name,
        attributes=attributes or {},
    )
    time.sleep(duration_seconds)
    try:
        remove_toxic(proxy_name, name)
    except Exception:
        logger.warning("Failed to remove timed toxic %s from %s", name, proxy_name)
