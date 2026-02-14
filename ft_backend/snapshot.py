
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Dict, Any, Tuple
import pandas as pd

from ..io.github_store import GitHubStore


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def build_manifest(files: Dict[str, bytes]) -> Dict[str, Any]:
    manifest = {
        "files": {},
    }
    for path, b in files.items():
        manifest["files"][path] = {
            "sha256": _sha256(b),
            "bytes": len(b),
        }
    return manifest


def publish_snapshot(
    store: GitHubStore,
    snapshot_prefix: str,
    latest_prefix: str,
    datasets: Dict[str, pd.DataFrame],
    latest_json_path: str,
    message_prefix: str = "Publish snapshot",
) -> Dict[str, Any]:
    """
    Scrive:
      - data/public/snapshots/<ts>/*.csv
      - data/public/latest/*.csv
      - manifest.json in entrambi
      - latest.json puntatore
    """
    files_bytes: Dict[str, bytes] = {}
    for name, df in datasets.items():
        b = df.to_csv(index=False).encode("utf-8")
        files_bytes[f"{snapshot_prefix}/{name}.csv"] = b
        files_bytes[f"{latest_prefix}/{name}.csv"] = b

    manifest = build_manifest(files_bytes)
    manifest_b = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    files_bytes[f"{snapshot_prefix}/manifest.json"] = manifest_b
    files_bytes[f"{latest_prefix}/manifest.json"] = manifest_b

    # write all
    for path, b in files_bytes.items():
        store.write_bytes(path, b, f"{message_prefix}: {path}")

    # write latest.json
    latest_obj = {"latest_snapshot": snapshot_prefix}
    store.write_bytes(latest_json_path, json.dumps(latest_obj, ensure_ascii=False, indent=2).encode("utf-8"),
                     f"{message_prefix}: update latest.json")

    return {"snapshot_prefix": snapshot_prefix, "latest_prefix": latest_prefix, "manifest": manifest}
