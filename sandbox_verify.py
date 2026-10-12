"""One-command Airwallex sandbox verification.

Runs the exact "first prompt" sequence from the Airwallex Developer Lab
hackathon guide:

    1. log in (x-client-id / x-api-key -> bearer token)
    2. list global accounts - create one if none exists
    3. simulate a $25,000 deposit (major units!)
    4. list wallet balances
    5. list transfers

Usage:
    set AIRWALLEX_CLIENT_ID=...        (Windows: $env:...)
    set AIRWALLEX_API_KEY=...
    python sandbox_verify.py

Prints PASS/FAIL per step and tells you exactly what is missing on failure.
"""

from __future__ import annotations

import sys

from payops.airwallex_client import AirwallexClient, AirwallexError


def main() -> int:
    print("=" * 62)
    print(" PayOpsSentinel - Airwallex sandbox verification")
    print("=" * 62)

    try:
        client = AirwallexClient()
    except AirwallexError as exc:
        print(f"\n[FAIL] {exc}")
        print("\nFix: create a sandbox at https://sandbox.airwallex.com,")
        print("then Account > Developer > API Keys, and export:")
        print("  AIRWALLEX_CLIENT_ID / AIRWALLEX_API_KEY")
        return 1

    ok = True

    # 1) login is implicit on first call, but make it explicit for clarity
    try:
        client.login(force=True)
        print("[PASS] login - bearer token issued (valid 30 minutes)")
    except AirwallexError as exc:
        print(f"[FAIL] login: {exc}")
        print("       -> credentials or scope problem; re-copy the keys")
        return 1

    # 2) global accounts (create if empty - developer MCP cannot create these)
    try:
        accounts = client.list_global_accounts()
        print(f"[PASS] global accounts: {len(accounts)} found")
        if not accounts:
            print("       none exist -> creating a USD/US account...")
            created = client.create_global_account(country_code="US",
                                                   currency="USD",
                                                   transfer_method="LOCAL")
            print(f"[PASS] created global account: {created.get('id')}")
            accounts = client.list_global_accounts()
    except AirwallexError as exc:
        print(f"[FAIL] global accounts: {exc}")
        ok = False
        accounts = []

    # 3) simulate deposit into the first account
    if accounts:
        try:
            ga_id = accounts[0].get("id")
            dep = client.simulate_deposit(ga_id, 25000, payer_name="Seed funding")
            print(f"[PASS] simulated deposit $25,000 -> {ga_id} "
                  f"(resp id: {dep.get('id', 'ok')})")
        except AirwallexError as exc:
            print(f"[FAIL] simulate deposit: {exc}")
            ok = False

    # 4) balances
    try:
        balances = client.get_balances()
        print("[PASS] balances: " + ", ".join(
            f"{v:,.2f} {k}" for k, v in balances.items()))
    except AirwallexError as exc:
        print(f"[FAIL] balances: {exc}")
        ok = False

    # 5) transfers
    try:
        transfers = client.list_transfers()
        print(f"[PASS] transfers: {len(transfers)} found")
    except AirwallexError as exc:
        print(f"[FAIL] transfers: {exc}")
        ok = False

    print("\n" + ("ALL CHECKS PASSED - sandbox is wired up. "
                  "You can run: python -m payops.cli --live"
                  if ok else
                  "SOME CHECKS FAILED - see messages above."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
