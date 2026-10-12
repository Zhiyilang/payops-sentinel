"""PayOpsSentinel - real Airwallex sandbox client.

API surface per the Airwallex Developer Lab hackathon guide:

    login           POST /api/v1/authentication/login
                    headers: x-client-id, x-api-key (no body)
                    -> bearer token, valid 30 minutes
    balances        GET  /api/v1/balances/current
    global accounts GET  /api/v1/global_accounts
                    POST /api/v1/global_accounts/create
    beneficiaries   POST /api/v1/beneficiaries/create
    transfers       GET  /api/v1/transfers
                    POST /api/v1/transfers/create
                    POST /api/v1/transfers/{id}/cancel
    simulations     POST /api/v1/simulation/deposit/create
                    POST /api/v1/simulation/transfers/{id}/transition

Rules baked in from the guide:
- amounts are MAJOR units (100 = one hundred dollars), never cents
- every mutating call carries a request_id; reuse it when retrying the
  same logical operation, generate a new one for a new payment
- tokens expire after 30 minutes -> cached and re-login automatically

Credentials come from the environment, never from code:

    AIRWALLEX_CLIENT_ID   - sandbox client id
    AIRWALLEX_API_KEY     - sandbox api key
    AIRWALLEX_BASE_URL    - defaults to the sandbox base

The client mirrors MockAirwallex's method names so the engine runs
unchanged against either backend.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any, Optional

try:
    import requests
except ImportError:  # pragma: no cover - requests is in requirements.txt
    requests = None

from .models import Transfer

SANDBOX_BASE = "https://api-sandbox.airwallex.com/api/v1"
PROD_BASE = "https://api.airwallex.com/api/v1"
TOKEN_TTL_SECONDS = 30 * 60          # guide: tokens last 30 minutes
TOKEN_REFRESH_MARGIN = 5 * 60        # refresh 5 minutes early


class AirwallexError(RuntimeError):
    pass


class AirwallexClient:
    def __init__(self, client_id: Optional[str] = None,
                 api_key: Optional[str] = None,
                 base_url: Optional[str] = None,
                 timeout: float = 20.0,
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
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self.calls: list[str] = []

    # ------------------------------------------------------------- plumbing
    def _new_request_id(self) -> str:
        """Stable per logical operation; caller reuses it across retries."""
        return uuid.uuid4().hex

    def login(self, force: bool = False) -> str:
        if not force and self._token and time.time() < self._token_expires_at:
            return self._token
        resp = requests.post(
            f"{self.base_url}/authentication/login",
            headers={"x-client-id": self.client_id,
                     "x-api-key": self.api_key},
            timeout=self.timeout)
        self.calls.append(f"POST /authentication/login -> {resp.status_code}")
        if resp.status_code != 200:
            raise AirwallexError(
                f"login failed {resp.status_code}: {resp.text[:300]} "
                "(check AIRWALLEX_CLIENT_ID / AIRWALLEX_API_KEY)")
        data = resp.json()
        self._token = data.get("token") or data.get("access_token")
        if not self._token:
            raise AirwallexError(f"login response had no token: {data}")
        self._token_expires_at = time.time() + TOKEN_TTL_SECONDS - TOKEN_REFRESH_MARGIN
        return self._token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.login()}",
                "Content-Type": "application/json"}

    def _request(self, method: str, path: str, payload: Optional[dict] = None,
                 request_id: Optional[str] = None) -> Any:
        """One logical call: the request_id is generated once and reused
        across transport-level retries, per the guide."""
        rid = request_id or self._new_request_id()
        body = dict(payload or {})
        if method != "GET" and "request_id" not in body:
            body["request_id"] = rid
        last: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = requests.request(
                    method, f"{self.base_url}{path}", json=body or None,
                    headers=self._headers(), timeout=self.timeout)
                self.calls.append(f"{method} {path} -> {resp.status_code}")
                if resp.status_code == 401:            # token expired mid-run
                    self.login(force=True)
                    continue
                if resp.status_code in (429, 500, 502, 503, 504):
                    time.sleep(2 * (attempt + 1))
                    last = AirwallexError(f"{resp.status_code} {resp.text[:200]}")
                    continue
                if resp.status_code >= 400:
                    raise AirwallexError(f"{resp.status_code} {resp.text[:300]}")
                return resp.json() if resp.content else {}
            except AirwallexError:
                raise
            except Exception as exc:                   # network hiccups
                last = exc
                time.sleep(2 * (attempt + 1))
        raise AirwallexError(f"request failed after retries: {last}")

    # ------------------------------------------------------------------ read
    def list_transfers(self, state: Optional[str] = None) -> list[Transfer]:
        path = "/transfers" + (f"?status={state}" if state else "")
        data = self._request("GET", path)
        items = data.get("items", data) if isinstance(data, dict) else data
        return [Transfer.from_dict(self._norm_transfer(d)) for d in items]

    def get_transfer(self, transfer_id: str) -> Transfer:
        return Transfer.from_dict(
            self._norm_transfer(self._request("GET", f"/transfers/{transfer_id}")))

    def get_balances(self) -> dict[str, float]:
        data = self._request("GET", "/balances/current")
        out: dict[str, float] = {}
        rows = data.get("items", data) if isinstance(data, dict) else data
        for b in rows:
            out[b.get("currency", "USD")] = float(
                b.get("available_amount", b.get("total_amount",
                                                b.get("amount", 0))))
        return out

    def list_global_accounts(self) -> list[dict]:
        data = self._request("GET", "/global_accounts")
        return data.get("items", data) if isinstance(data, dict) else data

    # ----------------------------------------------------------------- write
    def create_global_account(self, country_code: str = "US",
                              currency: str = "USD",
                              transfer_method: str = "LOCAL") -> dict:
        return self._request("POST", "/global_accounts/create", {
            "country_code": country_code,
            "required_features": [{"currency": currency,
                                   "transfer_method": transfer_method}],
        })

    def simulate_deposit(self, global_account_id: str, amount: float,
                         payer_name: str = "Seed funding") -> dict:
        return self._request("POST", "/simulation/deposit/create", {
            "global_account_id": global_account_id,
            "amount": amount,               # major units: 25000 = $25,000
            "payer_name": payer_name,
        })

    def create_beneficiary(self, name: str, **extra: Any) -> dict:
        return self._request("POST", "/beneficiaries/create",
                             {"beneficiary_name": name, **extra})

    def cancel_transfer(self, transfer_id: str, reason: str) -> dict[str, Any]:
        return self._request("POST", f"/transfers/{transfer_id}/cancel",
                             {"reason": reason})

    def create_transfer(self, beneficiary: str, amount: float,
                        currency: str, reference: str) -> Transfer:
        data = self._request("POST", "/transfers/create", {
            "beneficiary_id": beneficiary,
            "amount": amount,
            "currency": currency,
            "reference": reference,
            "reason": "reissued by PayOpsSentinel",
        })
        return Transfer.from_dict(self._norm_transfer(data))

    def simulate_transition(self, transfer_id: str, to_state: str) -> dict:
        """Sandbox-only: drive a transfer SENT -> PAID."""
        return self._request("POST",
                             f"/simulation/transfers/{transfer_id}/transition",
                             {"to_state": to_state})

    # ------------------------------------------------------------- internals
    @staticmethod
    def _norm_transfer(d: dict) -> dict:
        """Map Airwallex transfer fields onto our Transfer model."""
        return {
            "id": d.get("id") or d.get("transfer_id"),
            "beneficiary": (d.get("beneficiary_id")
                            or d.get("beneficiary_name")
                            or d.get("beneficiary", "")),
            "amount": float(d.get("amount", 0)),
            "currency": d.get("currency", "USD"),
            "state": (d.get("status") or d.get("state", "PENDING")).upper(),
            "created_at": d.get("created_at") or d.get("create_time") or "",
            "reference": d.get("reference", ""),
            "reason": d.get("reason", ""),
        }
