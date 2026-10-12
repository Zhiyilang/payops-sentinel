# Sandbox Setup Guide — what YOU do (5 minutes), then I take over

Registration is done (Internshala, team 「爆意一郎队」). Next: create the **Airwallex sandbox** and hand me the keys. Sandbox = fake money, instant, no approval.

## Step 1 — Create the sandbox (2 min)

1. Open **https://sandbox.airwallex.com**
2. Register with a **work email** (any email works in sandbox), your name, country = **China**, and a password.
3. Log in to the sandbox web app.

## Step 2 — Get your API keys (1 min)

1. **Account → Developer → API Keys**
2. You'll get a **Client ID** and an **API Key**.
3. ⚠️ Treat them like passwords. **Send them to me in this chat** — I'll wire them into the project as environment variables on your machine (never written into the repo code).

> ⚠️ If the web app asks you to add another business entity, the entity name **must** be `新业务沙盒` or `沙盒业务` — any other name stays stuck "in review" (this is a known sandbox quirk from the official guide).

## Step 3 — Send me the keys, then say "验证"

I'll run one command that:
1. Logs in (token lasts 30 min — auto-refreshed)
2. Lists global accounts, creates a USD one if empty
3. Simulates a $25,000 deposit
4. Prints wallet balances + transfers

Expected output ends with `ALL CHECKS PASSED`. After that I wire **PayOpsSentinel** to the live sandbox and we start the real incident demo (delayed supplier transfer + duplicate-payment catch — with simulated money).

## What I already prepared

- `payops/airwallex_client.py` — real client per the official guide: bearer-token login (30-min expiry, auto re-login), `request_id` on every mutation (reused on retry, new one = new payment), amounts in **major units** (25000 = $25,000, not cents).
- `sandbox_verify.py` — the one-command check above.
- `payops/` engine + mock — the same agent loop that already runs offline will run against the sandbox unchanged.

## Timeline reminder

| Date | Milestone |
|---|---|
| now – 10/23 | registration window (you're in) |
| **10/25** | build period starts (accepted teams notified) |
| 10/25 – 11/13 | I integrate + harden against the sandbox, build the demo |
| **11/13** | submission: working demo + ≤5 min video + repo link |
| 11/19 | Demo Day (remote is fine) |

**One thing to check on your Internshala dashboard now**: it shows 「注册与创意阶段 / 提交作品」 — there may be an **ideation submission** expected *before* the build phase. If the 「提交作品」 button asks for a project idea, paste the text from `IDEATION_PITCH.md` (already written for you).
