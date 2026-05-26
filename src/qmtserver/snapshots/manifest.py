from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def request_hash(request: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json(request).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def content_hash(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"
