"""24h cache for :mod:`hermes_cli.security_audit` results, shared by doctor and the CLI.

The OSV scan takes seconds and needs network; doctor runs often and must stay
fast and offline-safe. Scan results are cached in ``HERMES_HOME`` and served
for up to a day — matching the production-closure target that a newly
published GHSA becomes visible within 24h. Malformed or unwritable cache is
silently ignored: a broken cache degrades to "no cache", never to a crash.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from hermes_constants import get_hermes_home
from hermes_cli.security_audit import Component, Finding, Vulnerability

logger = logging.getLogger(__name__)

CACHE_FILE = "security-audit-osv.json"
MAX_AGE_HOURS = 24


def cache_path() -> Path:
    return Path(get_hermes_home()) / CACHE_FILE


def _finding_to_dict(f: Finding) -> dict:
    return {
        "component": {"name": f.component.name, "version": f.component.version,
                      "ecosystem": f.component.ecosystem, "source": f.component.source},
        "vuln": {"osv_id": f.vuln.osv_id, "severity": f.vuln.severity,
                 "summary": f.vuln.summary, "fixed_versions": f.vuln.fixed_versions},
    }


def _finding_from_dict(d: dict) -> Optional[Finding]:
    try:
        comp = d["component"]
        vuln = d["vuln"]
        return Finding(
            Component(name=comp["name"], version=comp["version"], ecosystem=comp["ecosystem"], source=comp["source"]),
            Vulnerability(osv_id=vuln["osv_id"], severity=vuln.get("severity", "UNKNOWN"),
                          summary=vuln.get("summary", ""), fixed_versions=list(vuln.get("fixed_versions") or [])),
        )
    except (KeyError, TypeError):
        return None


def write_cache(findings: list[Finding], *, component_count: int) -> str:
    """Persist a scan result and return the ``scanned_at`` stamp stored with it.
    Best-effort: an unwritable HERMES_HOME skips the cache but the stamp is
    still returned so the caller can display it."""
    scanned_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {
        "scanned_at": scanned_at,
        "component_count": component_count,
        "findings": [_finding_to_dict(f) for f in findings],
    }
    try:
        cache_path().write_text(json.dumps(payload), encoding="utf-8")
    except OSError as exc:
        logger.debug("security-audit cache write skipped: %s", exc)
    return scanned_at


def _read(max_age_hours: Optional[float]) -> Optional[tuple[list[Finding], int, str]]:
    path = cache_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        scanned_at = raw["scanned_at"]
        parsed = [f for f in (_finding_from_dict(d) for d in raw["findings"]) if f is not None]
        if len(parsed) != len(raw["findings"]):
            return None  # partial corruption — treat as no cache rather than a partial view
        if max_age_hours is not None:
            age = datetime.now(timezone.utc) - datetime.fromisoformat(scanned_at)
            if age > timedelta(hours=max_age_hours):
                return None
        return parsed, int(raw.get("component_count") or 0), scanned_at
    except (OSError, ValueError, KeyError, TypeError):
        return None


def read_cache(max_age_hours: float = MAX_AGE_HOURS) -> Optional[tuple[list[Finding], int, str]]:
    """Fresh cache only: ``(findings, component_count, scanned_at_iso)`` or None when
    absent, malformed, or older than ``max_age_hours``."""
    return _read(max_age_hours)


def read_cache_any() -> Optional[tuple[list[Finding], int, str]]:
    """Cache regardless of age — the offline fallback in doctor."""
    return _read(None)
