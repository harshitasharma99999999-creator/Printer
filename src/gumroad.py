import os
import json
from dataclasses import dataclass
from typing import Any, Optional

import requests


@dataclass
class GumroadResponse:
    ok: bool
    status_code: int
    text: str
    json: dict[str, Any]


class GumroadClient:
    """
    Best-effort Gumroad API client.

    Gumroad has multiple auth styles in the wild:
    - legacy: send `access_token` as a form field
    - newer: send `Authorization: Bearer <token>`

    This client tries both where helpful.
    """

    def __init__(
        self,
        token: str,
        *,
        base_url: str = "https://api.gumroad.com/v2",
        debug_dir: Optional[str] = None,
    ) -> None:
        self._token = (token or "").strip()
        self._base = base_url.rstrip("/")
        self._debug_dir = debug_dir

    def _write_debug(self, name: str, payload: dict[str, Any]) -> None:
        if not self._debug_dir:
            return
        try:
            os.makedirs(self._debug_dir, exist_ok=True)
            path = os.path.join(self._debug_dir, name)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _request(
        self,
        method: str,
        path: str,
        *,
        data: Optional[dict[str, Any]] = None,
        files: Any = None,
        timeout: int = 30,
        try_bearer_fallback: bool = True,
    ) -> GumroadResponse:
        if not self._token:
            return GumroadResponse(False, 0, "Missing Gumroad token.", {})

        url = f"{self._base}/{path.lstrip('/')}"
        payload = dict(data or {})

        # Attempt 1: legacy form `access_token`.
        legacy_payload = dict(payload)
        legacy_payload.setdefault("access_token", self._token)
        try:
            r = requests.request(
                method,
                url,
                data=legacy_payload,
                files=files,
                timeout=timeout,
            )
            resp_json: dict[str, Any] = {}
            try:
                resp_json = r.json()
            except Exception:
                resp_json = {}
            if r.ok or not try_bearer_fallback or r.status_code not in (401, 403, 404, 405):
                return GumroadResponse(bool(r.ok), int(r.status_code), str(r.text or ""), resp_json)
        except Exception as e:
            r = None
            legacy_err = str(e)
        else:
            legacy_err = ""

        # Attempt 2: Bearer token.
        try:
            headers = {"Authorization": f"Bearer {self._token}"}
            r2 = requests.request(
                method,
                url,
                data=payload,
                files=files,
                headers=headers,
                timeout=timeout,
            )
            resp2_json: dict[str, Any] = {}
            try:
                resp2_json = r2.json()
            except Exception:
                resp2_json = {}
            return GumroadResponse(bool(r2.ok), int(r2.status_code), str(r2.text or ""), resp2_json)
        except Exception as e:
            self._write_debug(
                "gumroad_api_error.json",
                {
                    "url": url,
                    "method": method,
                    "legacy_error": legacy_err,
                    "bearer_error": str(e),
                },
            )
            return GumroadResponse(False, 0, f"Request failed: {e}", {})

    def create_product(self, *, name: str, price_cents: int, description: str) -> dict[str, Any]:
        r = self._request(
            "POST",
            "/products",
            data={
                "name": name[:100],
                "price": int(price_cents),
                "description": (description or "")[:2000],
            },
            timeout=30,
        )
        if not r.ok:
            self._write_debug(
                "gumroad_create_failed.json",
                {"status": r.status_code, "text": r.text[:4000]},
            )
            return {}
        return r.json.get("product", {}) if isinstance(r.json, dict) else {}

    def upload_product_file(self, *, product_id: str, file_path: str, mime: str) -> bool:
        if not product_id or not os.path.exists(file_path):
            return False
        try:
            with open(file_path, "rb") as f:
                r = self._request(
                    "POST",
                    f"/products/{product_id}/product_files",
                    data={},
                    files={"file": (os.path.basename(file_path), f, mime)},
                    timeout=180,
                    try_bearer_fallback=True,
                )
            if not r.ok:
                self._write_debug(
                    "gumroad_upload_failed.json",
                    {
                        "product_id": product_id,
                        "file": os.path.basename(file_path),
                        "mime": mime,
                        "status": r.status_code,
                        "text": r.text[:4000],
                    },
                )
            return bool(r.ok)
        except Exception:
            return False

    def enable_product(self, *, product_id: str) -> bool:
        """
        Preferred publish path.
        Tries /enable first, falls back to legacy `published=true` update.
        """
        if not product_id:
            return False

        r = self._request("PUT", f"/products/{product_id}/enable", data={}, timeout=30)
        if r.ok:
            return True

        # Legacy fallback still used by older Gumroad API deployments.
        r2 = self._request(
            "PUT",
            f"/products/{product_id}",
            data={"published": "true"},
            timeout=30,
            try_bearer_fallback=True,
        )
        if not r2.ok:
            self._write_debug(
                "gumroad_enable_failed.json",
                {
                    "product_id": product_id,
                    "enable_status": r.status_code,
                    "enable_text": r.text[:2000],
                    "legacy_status": r2.status_code,
                    "legacy_text": r2.text[:2000],
                },
            )
        return bool(r2.ok)

