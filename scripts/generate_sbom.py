#!/usr/bin/env python3
"""Generate a CycloneDX 1.5 SBOM for the Python dependency tree from uv.lock.

npm ships its own SBOM generator (`npm sbom`); uv has no SBOM export, and
pulling a third-party CycloneDX tool just to reformat a lockfile we already
parse would add one more pinned dependency — so emit the (small, stable)
JSON here with stdlib only. Used by .github/workflows/sbom.yml and safe to
run locally.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tomllib
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _purl(name: str, version: str) -> str:
    return f"pkg:pypi/{name.lower().replace('_', '-')}@{version}"


def _component(name: str, version: str, comp_type: str) -> dict:
    purl = _purl(name, version)
    return {"type": comp_type, "bom-ref": purl, "name": name, "version": version, "purl": purl}


def build_bom(uv_lock: Path, spec_version: str) -> dict:
    """Parse ``uv.lock`` and return a CycloneDX BOM dict. The editable/virtual root
    project becomes ``metadata.component``; every locked package is a library component.
    """
    data = tomllib.loads(uv_lock.read_text(encoding="utf-8"))
    components: list[dict] = []
    root: dict | None = None
    for pkg in data.get("package", []):
        source = pkg.get("source") or {}
        comp = _component(pkg["name"], pkg["version"], "library")
        if isinstance(source, dict) and (source.get("editable") or source.get("virtual")):
            root = _component(pkg["name"], pkg["version"], "application")
        else:
            components.append(comp)
    if root is None:
        raise SystemExit(f"{uv_lock}: no editable/virtual root package found")

    # Deterministic serial: same dependency set -> same serialNumber, so SBOMs diff.
    digest = hashlib.sha256("\n".join(sorted(c["purl"] for c in components)).encode("utf-8")).hexdigest()
    serial = uuid.uuid5(uuid.NAMESPACE_URL, f"urn:hermes-agent:sbom:{digest}")
    return {
        "bomFormat": "CycloneDX",
        "specVersion": spec_version,
        "serialNumber": f"urn:uuid:{serial}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "tools": {"components": [_component("hermes-agent", "1", "application") | {"name": "scripts/generate_sbom.py"}]},
            "component": root,
        },
        "components": components,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--uv-lock", type=Path, default=Path("uv.lock"))
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--spec-version", default="1.5")
    args = ap.parse_args()
    bom = build_bom(args.uv_lock, args.spec_version)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bom, indent=2) + "\n", encoding="utf-8")
    print(f"{args.output}: {len(bom['components'])} components (root: {bom['metadata']['component']['name']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
