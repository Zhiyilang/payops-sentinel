"""PayOpsSentinel - data models."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


class TransferState(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    SETTLED = "SETTLED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class Action(str, Enum):
    WAIT = "WAIT"                          # within SLA, keep watching
    RETRY = "RETRY"                        # nudge / re-poll the transfer
    CANCEL_AND_REISSUE = "CANCEL_AND_REISSUE"  # cancel stuck, issue fresh
    HOLD = "HOLD"                          # block a risky near-duplicate
    ESCALATE = "ESCALATE"                  # hand to a human


@dataclass
class Transfer:
    id: str
    beneficiary: str
    amount: float
    currency: str
    state: str                      # TransferState value
    created_at: str                 # ISO-8601
    reference: str = ""
    reason: str = ""                # e.g. "invoice INV-2043"

    @staticmethod
    def from_dict(d: dict) -> "Transfer":
        return Transfer(
            id=d["id"],
            beneficiary=d.get("beneficiary", ""),
            amount=float(d.get("amount", 0)),
            currency=d.get("currency", "USD"),
            state=d.get("state", "PENDING"),
            created_at=d.get("created_at", ""),
            reference=d.get("reference", ""),
            reason=d.get("reason", ""),
        )


@dataclass
class Incident:
    kind: str                       # DELAYED_TRANSFER | DUPLICATE_RISK | STUCK
    severity: str                   # low | medium | high
    summary: str
    transfer_ids: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class Decision:
    action: str                     # Action value
    risk: str                       # low | medium | high
    rationale: str
    requires_approval: bool
    transfer_ids: list[str] = field(default_factory=list)
    approved: Optional[bool] = None
    executed: bool = False
    result: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AuditEntry:
    ts: str
    event: str                      # observed | incident | decision | approval | action | report
    payload: dict[str, Any]

    def to_dict(self) -> dict:
        return asdict(self)
