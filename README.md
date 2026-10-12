# PayOpsSentinel

**An offline-first payment-ops incident agent for [Airwallex](https://www.airwallex.com/) — built for the Agentic Banking Hackathon 2026, Track 03: Payment Ops Incident Commander.**

> *Resolve a delayed supplier transfer without paying twice.*

A supplier payout is stuck in `PENDING` for 72 hours. Someone, reasonably, re-sends it. Now you have two identical payments in flight and a finance team having a bad day. **PayOpsSentinel watches your transfers, catches the double-payment before it happens, and fixes the stuck one — with a human approving every irreversible move and an append-only audit trail of every decision.**

It runs **fully offline against a bundled mock** of the Airwallex API — no credentials, no network, no data leaving your machine — and flips to the **real Airwallex sandbox** with two environment variables.

```bash
# offline demo, zero setup (decisions auto-approved for scripted runs)
python -m payops.cli --demo --yes

# ask before every irreversible action
python -m payops.cli --demo

# real Airwallex sandbox
export AIRWALLEX_CLIENT_ID=... AIRWALLEX_API_KEY=...
python -m payops.cli --live
```

## Real demo output

```
==============================================================
 PayOpsSentinel - DEMO (offline mock, no credentials)
==============================================================

balances: 25,000.00 USD

[INCIDENT:HIGH] DELAYED_TRANSFER
  T-1001 to Acme Steel Works (18400.00 USD) has been PENDING for 72.0h

[INCIDENT:MEDIUM] DELAYED_TRANSFER
  T-1002 to Acme Steel Works (18400.00 USD) has been PENDING for 70.0h

[INCIDENT:HIGH] DUPLICATE_RISK
  T-1001 and T-1002 look like a double-payment: same beneficiary (Acme Steel Works) and amount (18400.00 USD), 2.0h apart

[DECISION] HOLD (risk=high)
  ... -> hold T-1002 (the newer copy) until the older transfer is cancelled and reissued; paying both would be a double payment
  approved=True executed=True

[DECISION] CANCEL_AND_REISSUE (risk=high)
  transfer pending 72.0h (> 48h SLA); cancel-and-reissue keeps the supplier paid without ever risking a double payment; amount exceeds auto-approval threshold
  approved=True executed=True

[ACTION] HOLD -> held (flagged) T-1002 - no money moved

[ACTION] CANCEL_AND_REISSUE -> cancelled T-1001, reissued as T-RE-0001 (18400.00 USD to Acme Steel Works)

audit: examples/demo_audit.jsonl (11 entries this run)
```

The order matters: the **duplicate-payment incident is evaluated first**, so the near-duplicate is held *before* any per-transfer decision could move money twice. The supplier still gets paid — via a fresh, tracked transfer.

## How it works

```
observe ──▶ detect ──▶ decide ──▶ approve ──▶ act ──▶ audit
 (client)   (policy)   (policy)   (human)    (client)  (JSONL)
```

| Stage | What happens | Where |
|---|---|---|
| **Observe** | Pull transfers + balances from Airwallex (sandbox or mock) | `payops/airwallex_client.py`, `payops/mock_adapter.py` |
| **Detect** | Delayed transfers (> SLA) and near-duplicates (same beneficiary + amount within a window) | `payops/policy.py` |
| **Decide** | Rule-based, inspectable decisions: `HOLD` / `CANCEL_AND_REISSUE` / `ESCALATE` | `payops/policy.py` |
| **Approve** | Every irreversible action is human-gated (`--yes` only for scripted demos) | `payops/engine.py`, `payops/cli.py` |
| **Act** | Cancel + reissue via the API — never both copies of a duplicate | `payops/engine.py` |
| **Audit** | Append-only JSONL: every observation, incident, decision, approval, action | `payops/audit.py` |

## Design choices worth defending

- **Rules in the hot path, not a black box.** Finance-ops teams need to review exactly why money moved before they let an agent near it. Every decision carries a human-readable rationale and every threshold is a dataclass field in `Policy`. (An open-weight LLM can be layered on later as an optional *explainer* of the audit trail — the decisions themselves stay reviewable.)
- **The mock is a first-class backend.** Same method surface as the real client, so the entire loop — including double-payment prevention — runs in CI, on a plane, and in a hackathon demo with zero credentials.
- **Approval is structural, not a flag someone forgets.** `requires_approval` is set by the policy engine, and irreversible actions (`CANCEL_AND_REISSUE`) always require it.
- **The duplicate wins.** Incident ordering puts `DUPLICATE_RISK` ahead of per-transfer handling, so "fix the stuck transfer" can never degenerate into "pay it twice".

## Project layout

```
payops-sentinel/
├── payops/
│   ├── models.py            # Transfer / Incident / Decision / AuditEntry
│   ├── mock_adapter.py      # offline Airwallex-shaped backend + demo scenario
│   ├── airwallex_client.py  # real sandbox client (env credentials, retries)
│   ├── policy.py            # detection rules + decision policy
│   ├── engine.py            # observe -> detect -> decide -> approve -> act
│   ├── audit.py             # append-only JSONL audit trail
│   └── cli.py               # --demo / --live / --dry-run / --watch / --yes
├── examples/
│   ├── demo_output.txt      # captured run (above)
│   └── demo_audit.jsonl     # the audit trail that run produced
├── CONTEST_DECLARATION.md
├── LICENSE                  # MIT
└── requirements.txt         # requests (everything else is stdlib)
```

## Roadmap

- [x] Offline mock backend + double-payment prevention demo
- [x] Audit trail + human approval gate
- [ ] Live sandbox integration (Airwallex credentials at hackathon start, Oct 25)
- [ ] Webhook-driven watch mode (react to transfer state changes in real time)
- [ ] Optional open-weight LLM "explain the audit trail" layer (local, offline)

## Hackathon

Built solo for the **Airwallex Agentic Banking Hackathon 2026** (Oct 25 – Nov 13), Track 03 *Payment Ops Incident Commander*. MIT licensed.
