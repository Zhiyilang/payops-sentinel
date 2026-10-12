"""PayOpsSentinel - the policy engine.

Turns raw incidents into decisions. Every rule is explicit and inspectable:
no black box, and every threshold is a dataclass field a finance-ops team can
review before the agent is allowed to touch anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import Decision, Incident, Transfer


@dataclass
class Policy:
    # a PENDING transfer older than this is considered delayed
    delayed_after_hours: float = 48.0
    # near-duplicate window: same beneficiary+amount within this many hours
    duplicate_window_hours: float = 24.0
    duplicate_amount_tolerance: float = 0.005   # 0.5%
    # amounts at/above this always require human approval before acting
    approval_threshold: float = 1000.0
    # never auto-cancel anything; humans always gate irreversible moves
    always_require_approval_for: tuple[str, ...] = (
        "CANCEL_AND_REISSUE",)


class PolicyEngine:
    def __init__(self, policy: Policy | None = None):
        self.policy = policy or Policy()

    # ------------------------------------------------------------ detection
    def detect(self, transfers: Iterable[Transfer],
               age_hours) -> list[Incident]:
        incidents: list[Incident] = []
        pending = [t for t in transfers if t.state == "PENDING"]

        # 1) delayed transfers
        for t in pending:
            age = age_hours(t)
            if age >= self.policy.delayed_after_hours:
                incidents.append(Incident(
                    kind="DELAYED_TRANSFER",
                    severity="high" if age >= 72 else "medium",
                    summary=(f"{t.id} to {t.beneficiary} "
                             f"({t.amount:.2f} {t.currency}) has been PENDING "
                             f"for {age:.1f}h"),
                    transfer_ids=[t.id],
                    evidence={"age_hours": round(age, 2),
                              "reference": t.reference},
                ))

        # 2) duplicate-payment risk: same beneficiary + same amount, close in time
        for i, a in enumerate(pending):
            for b in pending[i + 1:]:
                if a.beneficiary != b.beneficiary:
                    continue
                if abs(a.amount - b.amount) > self.policy.duplicate_amount_tolerance * a.amount:
                    continue
                gap = abs(age_hours(a) - age_hours(b))
                if gap <= self.policy.duplicate_window_hours:
                    incidents.append(Incident(
                        kind="DUPLICATE_RISK",
                        severity="high",
                        summary=(f"{a.id} and {b.id} look like a double-payment: "
                                 f"same beneficiary ({a.beneficiary}) and amount "
                                 f"({a.amount:.2f} {a.currency}), "
                                 f"{gap:.1f}h apart"),
                        transfer_ids=[a.id, b.id],
                        evidence={"amount": a.amount,
                                  "currency": a.currency,
                                  "gap_hours": round(gap, 2)},
                    ))
        return incidents

    # -------------------------------------------------------------- decision
    def decide(self, incident: Incident,
               transfers: dict[str, Transfer]) -> Decision:
        p = self.policy
        if incident.kind == "DELAYED_TRANSFER":
            age = incident.evidence.get("age_hours", 0)
            t = transfers[incident.transfer_ids[0]]
            high_value = t.amount >= p.approval_threshold
            return Decision(
                action="CANCEL_AND_REISSUE",
                risk="high",
                rationale=(f"transfer pending {age:.1f}h (> {p.delayed_after_hours:.0f}h "
                           f"SLA); cancel-and-reissue keeps the supplier paid "
                           f"without ever risking a double payment"
                           + ("; amount exceeds auto-approval threshold"
                              if high_value else "")),
                requires_approval=True,   # irreversible -> always human-gated
                transfer_ids=list(incident.transfer_ids),
            )
        if incident.kind == "DUPLICATE_RISK":
            # hold the NEWER transfer; the older one is dealt with by its own
            # delayed-transfer incident (cancel + reissue)
            pair = [transfers[i] for i in incident.transfer_ids]
            newer = max(pair, key=lambda t: t.created_at)
            return Decision(
                action="HOLD",
                risk="high",
                rationale=(incident.summary + f" -> hold {newer.id} (the newer "
                           f"copy) until the older transfer is cancelled and "
                           f"reissued; paying both would be a double payment"),
                requires_approval=True,
                transfer_ids=[newer.id],
            )
        return Decision(
            action="ESCALATE",
            risk="medium",
            rationale="unrecognised incident shape -> human review",
            requires_approval=True,
            transfer_ids=list(incident.transfer_ids),
        )
