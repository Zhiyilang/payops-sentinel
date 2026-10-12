"""PayOpsSentinel - the agent core.

One pass of the loop:

    observe -> detect -> decide -> (approve) -> act -> audit

The engine is backend-agnostic: give it anything with the AirwallexClient /
MockAirwallex method surface and it just runs. There is no LLM in the hot
path on purpose - every decision is a reviewable rule - but the decision
payloads are shaped so an open-weight LLM can be dropped in later as an
optional *explainer* (see README, "Why open-source AI").
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from .audit import JsonlAuditor
from .models import Decision, Incident, Transfer
from .policy import Policy, PolicyEngine


class SentinelEngine:
    def __init__(self, client, auditor: JsonlAuditor,
                 policy: Optional[Policy] = None,
                 approver: Optional[Callable[[Decision], bool]] = None):
        self.client = client
        self.auditor = auditor
        self.policy_engine = PolicyEngine(policy)
        self.approver = approver or (lambda d: True)

    # ------------------------------------------------------------------ loop
    def run_once(self, auto_approve: bool = False,
                 dry_run: bool = False) -> dict[str, Any]:
        report: dict[str, Any] = {"incidents": [], "decisions": [],
                                  "actions": [], "balances": {}}

        # 1) observe
        transfers = self.client.list_transfers()
        by_id = {t.id: t for t in transfers}
        report["balances"] = self.client.get_balances()
        self.auditor.log("observed", {
            "transfers": [t.__dict__ for t in transfers],
            "balances": report["balances"],
        })

        # 2) detect
        incidents = self.policy_engine.detect(
            transfers, age_hours=self.client_age)
        for inc in incidents:
            self.auditor.log("incident", inc.__dict__)
        report["incidents"] = [i.__dict__ for i in incidents]
        if not incidents:
            self.auditor.log("report", {"note": "no incidents"})
            return report

        # duplicate-payment risk is processed first: holding a near-duplicate
        # must win over any per-transfer decision that would move money twice
        incidents.sort(key=lambda i: (i.kind != "DUPLICATE_RISK",
                                      i.severity != "high"))
        handled: set[str] = set()

        # 3+4+5) decide, approve, act
        for inc in incidents:
            if inc.transfer_ids and all(
                    i in handled for i in inc.transfer_ids):
                continue                      # already covered by a decision
            decision = self.policy_engine.decide(inc, by_id)
            self.auditor.log("decision", decision.to_dict())

            if decision.requires_approval and not auto_approve:
                decision.approved = bool(self.approver(decision))
            else:
                decision.approved = auto_approve
            self.auditor.log("approval", {
                "action": decision.action,
                "transfer_ids": decision.transfer_ids,
                "approved": decision.approved,
            })

            if not decision.approved:
                decision.result = "not approved -> left untouched"
                report["decisions"].append(decision.to_dict())
                report["actions"].append(decision.to_dict())
                handled.update(decision.transfer_ids)
                continue
            if dry_run:
                decision.result = "dry-run -> would execute"
                report["decisions"].append(decision.to_dict())
                report["actions"].append(decision.to_dict())
                handled.update(decision.transfer_ids)
                continue

            decision.executed = True
            decision.result = self._execute(decision, by_id)
            self.auditor.log("action", decision.to_dict())
            report["decisions"].append(decision.to_dict())
            report["actions"].append(decision.to_dict())
            handled.update(decision.transfer_ids)

        self.auditor.log("report", {
            "incidents": len(report["incidents"]),
            "executed": sum(1 for a in report["actions"] if a["executed"]),
            "balances_after": self.client.get_balances(),
        })
        return report

    # -------------------------------------------------------------- internals
    def _execute(self, decision: Decision,
                 by_id: dict[str, Transfer]) -> str:
        if decision.action == "HOLD":
            return ("held (flagged) " + ", ".join(decision.transfer_ids) +
                    " - no money moved")
        if decision.action == "CANCEL_AND_REISSUE":
            old = by_id[decision.transfer_ids[0]]
            self.client.cancel_transfer(old.id,
                                        "delayed > SLA, reissuing")
            new = self.client.create_transfer(
                beneficiary=old.beneficiary, amount=old.amount,
                currency=old.currency, reference=old.reference)
            return (f"cancelled {old.id}, reissued as {new.id} "
                    f"({old.amount:.2f} {old.currency} to {old.beneficiary})")
        return "no-op"

    @property
    def client_age(self):
        """Age function bound to whichever backend we were handed."""
        if hasattr(self.client, "age_hours"):
            return self.client.age_hours
        # live client: derive age from the transfer timestamps
        from datetime import datetime, timezone

        def age(t: Transfer) -> float:
            created = datetime.fromisoformat(t.created_at)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - created).total_seconds() / 3600.0

        return age
