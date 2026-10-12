# PayOpsSentinel — Ideation Pitch (paste into the Internshala submission)

**Project name:** PayOpsSentinel
**Track:** Payment Ops Incident Commander
**Team:** Ohana (solo builder)
**Hackathon:** Airwallex Agentic Banking Hackathon 2026

---

## The problem

A supplier payout gets stuck in PENDING for days. Someone on the finance team, reasonably worried, re-sends it. Now two identical payments are in flight — and the classic outcome is paying the supplier twice, or cancelling the wrong one and paying late anyway. Today this is handled with spreadsheets, Slack threads, and someone manually eyeballing the Airwallex dashboard at 11pm.

## What I'm building

**PayOpsSentinel** — an agentic payment-ops copilot on Airwallex APIs that resolves stuck transfers *without ever paying twice*.

The agent runs a closed loop:

1. **Observe** — pulls transfers and balances from Airwallex (sandbox).
2. **Detect** — flags transfers pending past SLA, and near-duplicates (same beneficiary + same amount within a time window).
3. **Decide** — a reviewable rule engine chooses: HOLD the near-duplicate, CANCEL_AND_REISSUE the stuck one, or ESCALATE.
4. **Approve** — every irreversible action is human-gated. Money never moves on the agent's own authority.
5. **Act** — executes via Airwallex APIs with idempotent `request_id`s.
6. **Audit** — every observation, decision, approval and action lands in an append-only JSONL trail.

The ordering is the core insight: the duplicate-payment check runs *before* any per-transfer fix, so "repair the stuck payment" can never degrade into "pay it twice."

## Why it fits the track

Track 03 asks: *resolve a delayed supplier transfer without paying twice.* That is exactly the demo: a $18,400 supplier payout stuck 72 hours, a manual re-send 2 hours later, and an agent that holds the duplicate, cancels the stuck original, and reissues a fresh tracked transfer — supplier paid once, on time, with a full audit trail.

## Tech approach

- Python + `requests` against the Airwallex sandbox REST API (bearer-token auth, 30-min token caching, `request_id` idempotency on all mutations).
- The same agent loop runs against an offline mock backend, so the demo works with zero credentials and the whole system is testable in CI.
- Rule-based decisions in the hot path — finance teams can review exactly why money moved before letting an agent near production. An open-weight LLM can later be layered on as an *explainer* of the audit trail without changing the decision logic.

## Demo plan (submission)

A scripted incident in the Airwallex sandbox: seed a delayed transfer, simulate a duplicate re-send, and show the agent catch the double-payment, hold the duplicate, cancel-and-reissue the stuck transfer — then show the JSONL audit trail as the compliance artifact.

## What happens after the hackathon

The rule engine generalizes beyond this incident: reserve floors, FX timing, and approval-threshold policies are all dataclass fields — the same loop becomes a treasury and spend-policy agent.
