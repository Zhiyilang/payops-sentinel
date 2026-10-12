"""PayOpsSentinel - offline mock of the Airwallex API surface.

Produces realistic, Airwallex-shaped responses from a JSON scenario so the
whole agent loop (observe -> detect -> decide -> act -> audit) can run, be
demoed and be tested with ZERO credentials and ZERO network access.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from .models import Transfer


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MockAirwallex:
    """In-memory stand-in for the Airwallex sandbox.

    Mirrors the shape of the real client (same method names) so
    ``engine.py`` never knows or cares which one it is talking to.
    """

    def __init__(self, scenario_path: Optional[str] = None,
                 scenario: Optional[dict] = None):
        if scenario is None and scenario_path:
            with open(scenario_path, "r", encoding="utf-8") as fh:
                scenario = json.load(fh)
        scenario = scenario or {}
        self.name = scenario.get("name", "mock-sandbox")
        self._balances = scenario.get("balances", {"USD": 25000.0})
        self._transfers: dict[str, Transfer] = {}
        self._counter = 0
        for raw in scenario.get("transfers", []):
            t = Transfer.from_dict(raw)
            self._transfers[t.id] = t
        self.calls: list[str] = []   # every mutation is logged -> demo gold

    # ------------------------------------------------------------------ read
    def list_transfers(self, state: Optional[str] = None) -> list[Transfer]:
        self.calls.append(f"GET /transfers state={state or '*'}")
        out = list(self._transfers.values())
        if state:
            out = [t for t in out if t.state == state]
        return sorted(out, key=lambda t: t.created_at)

    def get_transfer(self, transfer_id: str) -> Transfer:
        self.calls.append(f"GET /transfers/{transfer_id}")
        return self._transfers[transfer_id]

    def get_balances(self) -> dict[str, float]:
        self.calls.append("GET /balances")
        return dict(self._balances)

    # ----------------------------------------------------------------- write
    def cancel_transfer(self, transfer_id: str, reason: str) -> dict[str, Any]:
        self.calls.append(f"POST /transfers/{transfer_id}/cancel ({reason})")
        t = self._transfers[transfer_id]
        if t.state in ("SETTLED", "CANCELLED"):
            raise ValueError(f"cannot cancel {transfer_id} in state {t.state}")
        t.state = "CANCELLED"
        t.reason = reason
        return {"id": t.id, "state": t.state}

    def create_transfer(self, beneficiary: str, amount: float,
                        currency: str, reference: str) -> Transfer:
        self._counter += 1
        tid = f"T-RE-{self._counter:04d}"
        t = Transfer(
            id=tid,
            beneficiary=beneficiary,
            amount=amount,
            currency=currency,
            state="PENDING",
            created_at=_now().isoformat(),
            reference=reference,
            reason="reissued by PayOpsSentinel",
        )
        self._transfers[tid] = t
        self.calls.append(
            f"POST /transfers -> {tid} {amount} {currency} to {beneficiary}")
        return t

    # ------------------------------------------------------------- utilities
    def age_hours(self, transfer: Transfer) -> float:
        created = datetime.fromisoformat(transfer.created_at)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return (_now() - created).total_seconds() / 3600.0

    def make_scenario_delayed_supplier(self) -> dict:
        """A realistic incident: supplier payout stuck 72h + a near-duplicate."""
        base = _now() - timedelta(hours=72)
        return {
            "name": "delayed-supplier-with-duplicate",
            "balances": {"USD": 25000.0},
            "transfers": [
                {"id": "T-1001", "beneficiary": "Acme Steel Works",
                 "amount": 18400.0, "currency": "USD", "state": "PENDING",
                 "created_at": base.isoformat(),
                 "reference": "INV-2043", "reason": "Q3 steel invoice"},
                {"id": "T-1002", "beneficiary": "Acme Steel Works",
                 "amount": 18400.0, "currency": "USD", "state": "PENDING",
                 "created_at": (base + timedelta(hours=2)).isoformat(),
                 "reference": "INV-2043", "reason": "manual re-send after first looked stuck"},
                {"id": "T-1000", "beneficiary": "Northwind Logistics",
                 "amount": 3200.0, "currency": "USD", "state": "SETTLED",
                 "created_at": (_now() - timedelta(days=5)).isoformat(),
                 "reference": "INV-1990", "reason": "freight"},
            ],
        }
