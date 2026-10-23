"""Contract tests for scripts/generate_sbom.py — CycloneDX emitted from uv.lock.

Loads the script's ``build_bom`` directly (stdlib-only pure function; no
subprocess) and asserts the output is valid CycloneDX with every component
carrying name/version/purl. No snapshot of component counts.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "generate_sbom.py"
_spec = importlib.util.spec_from_file_location("generate_sbom", _SCRIPT)
generate_sbom = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generate_sbom)

LOCK = """\
version = 1
revision = 5
requires-python = ">=3.11, <3.14"

[[package]]
name = "hermes-agent"
version = "0.21.3"
source = { editable = "." }
dependencies = [
    { name = "requests" },
]

[[package]]
name = "requests"
version = "2.33.0"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "certifi"
version = "2026.10.19"
source = { registry = "https://pypi.org/simple" }
"""


def _bom(tmp_path: Path, lock: str = LOCK) -> dict:
    lock_path = tmp_path / "uv.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(lock, encoding="utf-8")
    return generate_sbom.build_bom(lock_path, "1.5")


class TestGenerateSbom:
    def test_emits_valid_cyclonedx(self, tmp_path: Path):
        bom = _bom(tmp_path)
        assert bom["bomFormat"] == "CycloneDX"
        assert bom["specVersion"] == "1.5"
        assert bom["serialNumber"].startswith("urn:uuid:")
        # Every locked package is a library component with full purl identity.
        for comp in bom["components"]:
            assert comp["type"] == "library"
            assert comp["purl"] == f"pkg:pypi/{comp['name'].lower()}@{comp['version']}"
            assert comp["bom-ref"] == comp["purl"]
        # The root project is metadata.component, not a member of components.
        assert {c["name"] for c in bom["components"]} == {"requests", "certifi"}
        assert bom["metadata"]["component"]["name"] == "hermes-agent"

    def test_deterministic_serial_for_same_inputs(self, tmp_path: Path):
        assert _bom(tmp_path / "a")["serialNumber"] == _bom(tmp_path / "b")["serialNumber"]

    def test_changed_dependency_set_changes_serial(self, tmp_path: Path):
        serial1 = _bom(tmp_path / "a")["serialNumber"]
        serial2 = _bom(tmp_path / "b", lock=LOCK.replace('"certifi"', '"idna"'))["serialNumber"]
        assert serial1 != serial2

    def test_missing_root_fails_loudly(self, tmp_path: Path):
        lock = 'version = 1\n[[package]]\nname = "x"\nversion = "1.0"\nsource = { registry = "https://pypi.org/simple" }\n'
        with pytest.raises(SystemExit, match="root"):
            _bom(tmp_path, lock=lock)

    def test_main_writes_output_file(self, tmp_path: Path, monkeypatch, capsys):
        lock_path = tmp_path / "uv.lock"
        lock_path.write_text(LOCK, encoding="utf-8")
        out = tmp_path / "dist" / "sbom.json"
        monkeypatch.setattr("sys.argv", ["generate_sbom.py", "--uv-lock", str(lock_path), "--output", str(out)])
        assert generate_sbom.main() == 0
        assert json.loads(out.read_text(encoding="utf-8"))["bomFormat"] == "CycloneDX"
