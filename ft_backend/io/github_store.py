
from __future__ import annotations

import base64
import io
import json
from dataclasses import dataclass
from typing import Any, Optional, Tuple

import pandas as pd
import requests


@dataclass(frozen=True)
class GitHubConfig:
    token: str
    repo: str           # "owner/name"
    branch: str = "main"

    @property
    def api_base(self) -> str:
        return f"https://api.github.com/repos/{self.repo}/contents"


class GitHubStore:
    """Minimal GitHub contents API store (create/update/read)."""

    def __init__(self, cfg: GitHubConfig):
        self.cfg = cfg

    def _headers(self) -> dict:
        return {
            "Authorization": f"token {self.cfg.token}",
            "Accept": "application/vnd.github+json",
        }

    def read_bytes(self, path: str) -> Tuple[Optional[bytes], Optional[str]]:
        url = f"{self.cfg.api_base}/{path}"
        resp = requests.get(url, headers=self._headers())
        if resp.status_code == 200:
            data = resp.json()
            content = base64.b64decode(data["content"])
            return content, data["sha"]
        if resp.status_code == 404:
            return None, None
        raise RuntimeError(f"GitHub GET {path}: {resp.status_code} - {resp.text}")

    def write_bytes(self, path: str, content_bytes: bytes, message: str) -> None:
        url = f"{self.cfg.api_base}/{path}"
        existing, sha = self.read_bytes(path)

        payload = {
            "message": message,
            "content": base64.b64encode(content_bytes).decode("utf-8"),
            "branch": self.cfg.branch,
        }
        if sha is not None:
            payload["sha"] = sha

        resp = requests.put(url, headers=self._headers(), data=json.dumps(payload))
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"GitHub PUT {path}: {resp.status_code} - {resp.text}")

    # Convenience helpers
    def read_csv(self, path: str) -> pd.DataFrame:
        b, _ = self.read_bytes(path)
        if b is None:
            return pd.DataFrame()
        return pd.read_csv(io.StringIO(b.decode("utf-8")))

    def write_csv(self, path: str, df: pd.DataFrame, message: str) -> None:
        self.write_bytes(path, df.to_csv(index=False).encode("utf-8"), message)

    def read_json(self, path: str, default: Any) -> Any:
        b, _ = self.read_bytes(path)
        if b is None:
            return default
        return json.loads(b.decode("utf-8"))

    def write_json(self, path: str, obj: Any, message: str) -> None:
        self.write_bytes(path, json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8"), message)
