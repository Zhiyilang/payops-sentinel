# Contest Declaration

**Project:** PayOpsSentinel
**Hackathon:** Airwallex Agentic Banking Hackathon 2026 (Oct 25 – Nov 13, 2026)
**Track:** Payment Ops Incident Commander (Track 03)
**Author:** Zhiyilang (solo entrant)
**License:** MIT

## Declarations

- This project was built by the declared author during the hackathon window.
- All third-party libraries are open source and credited in `requirements.txt`
  (only `requests`; everything else is Python standard library).
- The demo scenario (`payops/mock_adapter.py`:
  `make_scenario_delayed_supplier`) is synthetic test data created for this
  project. No real customer data is involved.
- The mock backend exists so the project runs with zero credentials; the live
  path (`payops/airwallex_client.py`) targets the official Airwallex sandbox
  API and is exercised with sandbox credentials during the build period.
- All agent actions are logged to an append-only JSONL audit trail
  (`payops_audit.jsonl`); irreversible actions require human approval.
