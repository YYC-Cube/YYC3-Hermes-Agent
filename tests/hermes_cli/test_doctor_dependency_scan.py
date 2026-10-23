"""Tests for doctor's OSV dependency-vulnerability check (production closure P1-9).

doctor reads the same OSV source as ``hermes security-audit`` through the 24h
cache in :mod:`hermes_cli.security_audit_cache`. Everything here is hermetic:
HTTP is never touched — ``run_audit`` is monkeypatched or the cache is
pre-seeded, and ``HERMES_HOME`` comes from the autouse fixture.
"""

from __future__ import annotations

import io
import json
import sys
from datetime import datetime, timedelta, timezone

import pytest

from hermes_cli import security_audit, security_audit_cache
from hermes_cli.doctor_platform import _check_dependency_vulnerabilities
from hermes_cli.doctor_report import Finding
from hermes_cli.security_audit import Component, Finding as SaFinding, Vulnerability


def _finding(name="requests", version="2.20.0", vid="GHSA-test-0001", severity="HIGH",
             source="venv", fixed=("2.33.0",)) -> SaFinding:
    return SaFinding(Component(name=name, version=version, ecosystem="PyPI", source=source),
                     Vulnerability(osv_id=vid, severity=severity, summary="it's bad", fixed_versions=list(fixed)))


class _Tty(io.StringIO):
    def isatty(self) -> bool:
        return True


def _run(monkeypatch, tty: bool = False) -> tuple[Finding, str]:
    """Invoke the raw check; return (Finding, rendered output). *tty* simulates an
    interactive stdout so the cache-refresh path runs."""
    f = Finding()
    buf = _Tty() if tty else io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    _check_dependency_vulnerabilities.__wrapped__(False, f)
    return f, buf.getvalue()


@pytest.fixture(autouse=True)
def _cache_home(tmp_path, monkeypatch):
    monkeypatch.setattr(security_audit_cache, "get_hermes_home", lambda: str(tmp_path))


class TestDoctorDependencyScan:
    def test_fresh_empty_cache_reports_ok_without_network(self, monkeypatch):
        security_audit_cache.write_cache([], component_count=7)
        monkeypatch.setattr(security_audit, "run_audit",
                            lambda **kw: pytest.fail("run_audit must not be called with a fresh cache"))
        f, out = _run(monkeypatch)
        assert not f.issues
        assert "No known vulnerabilities in 7 components" in out

    def test_fresh_cache_with_high_finding_fails_row(self, monkeypatch):
        security_audit_cache.write_cache([_finding()], component_count=7)
        f, out = _run(monkeypatch)
        # manual_issues carries the fix/action text; the row (component + GHSA id) prints.
        assert f.manual_issues and "2.33.0" in f.manual_issues[0]
        assert "requests==2.20.0" in out and "GHSA-test-0001" in out

    def test_non_interactive_without_cache_never_touches_network(self, monkeypatch):
        # pytest stdout is captured (not a tty), so the refresh path must be skipped.
        monkeypatch.setattr(security_audit, "run_audit",
                            lambda **kw: pytest.fail("run_audit must not be called when non-interactive"))
        f, out = _run(monkeypatch)
        assert not f.issues
        assert "not cached yet" in out

    def test_interactive_refresh_scans_and_caches(self, monkeypatch, tmp_path):
        monkeypatch.setattr(security_audit, "_discover_components", lambda **kw: [Component("requests", "2.20.0", "PyPI", "venv")])
        monkeypatch.setattr(security_audit, "run_audit", lambda **kw: [_finding()])
        f, out = _run(monkeypatch, tty=True)
        assert f.manual_issues and "requests==2.20.0" in out
        cached = security_audit_cache.read_cache()
        assert cached is not None
        findings, count, _ = cached
        assert count == 1 and findings[0].vuln.osv_id == "GHSA-test-0001"

    def test_offline_falls_back_to_stale_cache(self, monkeypatch, tmp_path):
        security_audit_cache.write_cache([_finding()], component_count=3)
        # Age the cache beyond MAX_AGE_HOURS so only read_cache_any() can serve it.
        path = security_audit_cache.cache_path()
        payload = json.loads(path.read_text(encoding="utf-8"))
        old = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat(timespec="seconds")
        payload["scanned_at"] = old
        path.write_text(json.dumps(payload), encoding="utf-8")

        monkeypatch.setattr(security_audit, "run_audit",
                            lambda **kw: (_ for _ in ()).throw(RuntimeError("OSV batch query failed: offline")))
        f, out = _run(monkeypatch, tty=True)
        assert f.manual_issues, "stale cache findings must still be surfaced offline"
        assert old in out + " ".join(f.manual_issues)

    def test_offline_without_cache_warns(self, monkeypatch):
        monkeypatch.setattr(security_audit, "run_audit",
                            lambda **kw: (_ for _ in ()).throw(RuntimeError("OSV batch query failed: offline")))
        f, out = _run(monkeypatch, tty=True)
        assert not f.manual_issues
        assert "unavailable" in out

    def test_high_findings_capped_at_ten_with_overflow_note(self, monkeypatch):
        findings = [_finding(vid=f"GHSA-test-{i:04d}") for i in range(12)]
        findings.append(_finding(vid="GHSA-test-low", severity="LOW"))
        security_audit_cache.write_cache(findings, component_count=50)
        f, out = _run(monkeypatch)
        assert len(f.manual_issues) == 10
        assert "and 2 more" in out
        assert "1 lower-severity OSV finding" in out


class TestCacheRoundTrip:
    def test_preserves_finding_fields(self, tmp_path):
        original = _finding(name="pkg_x", version="9.8.7", vid="GHSA-xyz", severity="CRITICAL",
                            source="plugin:foo", fixed=("9.9.0", "9.9.1"))
        security_audit_cache.write_cache([original], component_count=42)
        findings, count, scanned_at = security_audit_cache.read_cache()
        assert count == 42 and scanned_at
        got = findings[0]
        assert (got.component.name, got.component.version, got.component.source) == ("pkg_x", "9.8.7", "plugin:foo")
        assert got.vuln.severity == "CRITICAL" and got.vuln.fixed_versions == ["9.9.0", "9.9.1"]

    def test_corrupt_cache_reads_as_none(self, tmp_path):
        security_audit_cache.cache_path().write_text("{not json", encoding="utf-8")
        assert security_audit_cache.read_cache() is None
        assert security_audit_cache.read_cache_any() is None
