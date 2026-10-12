"""PayOpsSentinel - real Airwallex API client (sandbox-ready).

Credentials come from the environment, never from code:

    AIRWALLEX_CLIENT_ID   - sandbox client id
    AIRWALLEX_API_KEY     - sandbox api key
    AIRWALLEX_BASE_URL    - defaults to the sandbox base

The client intentionally mirrors MockAirwallex's method names so the engine
runs unchanged against either backend.
"""

from __future__ import annotations

import os
import time
from typing import Any, Optional

try:
    import requests
except ImportError:  # pragma: no cover - requests is in requirements.txt
    requests = None

from .models import Transfer

SANDBOX_BASE = "https://api-sandbox.airwallex.com/api/v1"
PROD_BASE = "https://api.airwallex.com/api/v1"


class AirwallexError(RuntimeError):
    pass


class AirwallexClient:
    def __init__(self, client_id: Optional[str] = None,
                 api_key: Optional[str] = None,
                 base_url: Optional[str] = None,
                 timeout: float = 15.0,
                 max_retries: int = 3):
        self.client_id = client_id or os.environ.get("AIRWALLEX_CLIENT_ID", "")
        self.api_key = api_key or os.environ.get("AIRWALLEX_API_KEY", "")
        self.base_url = (base_url or os.environ.get("AIRWALLEX_BASE_URL")
                         or SANDBOX_BASE).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        if requests is None:
            raise AirwallexError("`requests` is required for live mode "
                                 "(pip install -r requirements.txt)")
        if not (self.client_id and self.api_key):
            raise AirwallexError(
                "missing credentials: set AIRWALLEX_CLIENT_ID and "
                "AIRWALLEX_API_KEY, or run --demo to use the offline mock")
        self.calls: list[str] = []

    # ------------------------------------------------------------- plumbing
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "X-Client-Id": self.client_id,
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str,
                 payload: Optional[dict] = None) -> Any:
        url = f"{self.base_url}{path}"
        last: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = requests.request(method, url, json=payload,
                                        headers=self._headers(),
                                        timeout=self.timeout)
                self.calls.append(f"{method} {path} -> {resp.status_code}")
                if resp.status_code in (429, 500, 502, 503, 504):
                    time.sleep(2 * (attempt + 1))
                    last = AirwallexError(f"{resp.status_code} {resp.text[:200]}")
                    continue
                if resp.status_code >= 400:
                    raise AirwallexError(f"{resp.status_code} {resp.text[:300]}")
                return resp.json()
            except AirwallexError:
                raise
            except Exception as exc:  # network hiccups
                last = exc
                time.sleep(2 * (attempt + 1))
        raise AirwallexError(f"request failed after retries: {last}")

    # ------------------------------------------------------------------ read
    def list_transfers(self, state: Optional[str] = None) -> list[Transfer]:
        params = f"?status={state}" if state else ""
        data = self._request("GET", f"/transfers{params}")
        items = data.get("items", data) if isinstance(data, dict) else data
        return [Transfer.from_dict(d) for d in items]

    def get_transfer(self, transfer_id: str) -> Transfer:
        return Transfer.from_dict(
            self._request("GET", f"/transfers/{transfer_id}"))

    def get_balances(self) -> dict[str, float]:
        data = self._request("GET", "/balances")
        out: dict[str, float] = {}
        for b in data.get("items", data) if isinstance(data, dict) else data:
            out[b.get("currency", "USD")] = float(
                b.get("available_amount", b.get("amount", 0)))
        return out

    # ----------------------------------------------------------------- write
    def cancel_transfer(self, transfer_id: str, reason: str) -> dict[str, Any]:
        return self._request("POST", f"/transfers/{transfer_id}/cancel",
                             {"reason": reason})

    def create_transfer(self, beneficiary: str, amount: float,
                        currency: str, reference: str) -> Transfer:
        data = self._request("POST", "/transfers", {
            "beneficiary_id": beneficiary,
            "amount": amount,
            "currency": currency,
            "reference": reference,
            "reason": "reissued by PayOpsSentinel",
        })
        return Transfer.from_dict(data)
