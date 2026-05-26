from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SnapshotRegistry:
    def __init__(self, root: Path) -> None:
        self.root = root

    def list_manifests(self) -> list[dict[str, Any]]:
        self.root.mkdir(parents=True, exist_ok=True)
        manifests = [self._read(path) for path in sorted(self.root.glob("*.manifest.json"))]
        return [manifest for manifest in manifests if manifest is not None]

    def get(self, snapshot_id: str) -> dict[str, Any] | None:
        return self._read(self._manifest_path(snapshot_id))

    def save(self, manifest: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self._manifest_path(str(manifest["snapshot_id"])).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def find_by_request_hash(self, value: str) -> dict[str, Any] | None:
        for manifest in self.list_manifests():
            if manifest.get("request_hash") == value:
                return manifest
        return None

    def data_path(self, snapshot_id: str, format_name: str) -> Path:
        return self.root / f"{snapshot_id}.{format_name}"

    def _manifest_path(self, snapshot_id: str) -> Path:
        return self.root / f"{snapshot_id}.manifest.json"

    def _read(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
