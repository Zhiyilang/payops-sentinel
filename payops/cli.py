"""PayOpsSentinel CLI.

    python -m payops.cli --demo --yes          # offline demo, auto-approve
    python -m payops.cli --demo                # offline demo, ask before acting
    python -m payops.cli --live --yes          # real Airwallex sandbox (env creds)
    python -m payops.cli --demo --dry-run      # decide only, touch nothing
"""

from __future__ import annotations

import argparse
import sys

from .audit import JsonlAuditor
from .engine import SentinelEngine
from .mock_adapter import MockAirwallex


def _hr(title: str) -> str:
    return "\n" + "=" * 62 + f"\n {title}\n" + "=" * 62


def _ask(decision) -> bool:
    print(f"\n  [APPROVAL REQUIRED] {decision.action}")
    print(f"    transfers : {', '.join(decision.transfer_ids)}")
    print(f"    risk      : {decision.risk}")
    print(f"    rationale : {decision.rationale}")
    try:
        ans = input("    approve? [y/N] ").strip().lower()
    except EOFError:
        return False
    return ans in ("y", "yes")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="payops",
        description="Offline-first payment-ops incident agent for Airwallex")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--demo", action="store_true", default=True,
                      help="run against the built-in offline mock (default)")
    mode.add_argument("--live", action="store_true",
                      help="run against the real Airwallex sandbox API "
                           "(needs AIRWALLEX_CLIENT_ID / AIRWALLEX_API_KEY)")
    p.add_argument("--scenario", default=None,
                   help="path to a custom mock scenario JSON (demo mode)")
    p.add_argument("--yes", action="store_true",
                   help="auto-approve decisions (scripted demo)")
    p.add_argument("--dry-run", action="store_true",
                   help="detect + decide but never move money")
    p.add_argument("--audit", default="payops_audit.jsonl",
                   help="audit log path (default: payops_audit.jsonl)")
    p.add_argument("--watch", type=int, default=0, metavar="SECONDS",
                   help="keep polling every N seconds (0 = single pass)")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    auditor = JsonlAuditor(args.audit)

    if args.live:
        from .airwallex_client import AirwallexClient
        client = AirwallexClient()
        print(_hr("PayOpsSentinel - LIVE (Airwallex sandbox)"))
    else:
        mock = MockAirwallex()
        if args.scenario:
            client = MockAirwallex(scenario_path=args.scenario)
        else:
            client = MockAirwallex(
                scenario=mock.make_scenario_delayed_supplier())
        print(_hr("PayOpsSentinel - DEMO (offline mock, no credentials)"))

    engine = SentinelEngine(client, auditor, approver=_ask)

    passes = 0
    while True:
        passes += 1
        report = engine.run_once(auto_approve=args.yes, dry_run=args.dry_run)

        print(f"\nbalances: " + ", ".join(
            f"{v:,.2f} {k}" for k, v in report["balances"].items()))

        if not report["incidents"]:
            print("no incidents detected - all transfers within SLA")
        for inc in report["incidents"]:
            print(f"\n[INCIDENT:{inc['severity'].upper()}] {inc['kind']}")
            print(f"  {inc['summary']}")

        for dec in report["decisions"]:
            print(f"\n[DECISION] {dec['action']} (risk={dec['risk']})")
            print(f"  {dec['rationale']}")
            print(f"  approved={dec['approved']} executed={dec['executed']}")
        for act in report["actions"]:
            print(f"\n[ACTION] {act['action']} -> {act['result']}")

        print(f"\naudit: {args.audit} "
              f"({len(auditor.entries())} entries this run)")

        if args.watch <= 0:
            break
        import time
        time.sleep(args.watch)

    return 0


if __name__ == "__main__":
    sys.exit(main())
