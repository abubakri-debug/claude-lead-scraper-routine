# Setup checklist — Airtable-triggered lead-scraper routine

Two people, split by who owns what. **You (Abu)** do steps 1–3 and 6. **Your boss** (whose Claude
account will host the routine) does steps 4–5. ~30–40 min total, one time.

---

## YOU — Step 1: Create the repo (company GitHub)

1. Create a private repo in the company org, e.g. `company/lead-scraper-routine`.
2. Push the contents of this folder to it (scripts/, assets/, references/, SKILL.md,
   ROUTINE_PROMPT.md, README.md). **Do NOT commit any API keys** — there are none in these files;
   keep it that way.
3. Note the repo URL — your boss needs it for step 4.

## YOU — Step 2: Have the Claude GitHub App authorized on the repo

The routine clones the repo, so your boss's Claude environment needs read access. A company
GitHub **org admin** installs the Claude GitHub App (https://github.com/apps/claude) on the org
or specifically on this repo. (If your boss's account already has it on the org, skip.)

## YOU — Step 3: Build the Airtable intake (form + automation)

In the Airtable base that will hold the form:

1. Create a table **Lead Requests** with fields:
   - `Count` (Number, integer)
   - `Location` (Single line text) — e.g. "Berlin, Germany"
   - `Industry` (Single line text) — e.g. "marketing agency"
   - `Country code` (Single line text, optional; default "de")
   - `Status` (Single select: Requested / Running / Done) — optional, nice for tracking
2. Create a **Form view** on that table exposing Count, Location, Industry (+ Country code).
3. Add an **Automation**: trigger "When a record is created" on Lead Requests →
   action "Run a script" using `airtable_automation.js` from this repo. Paste the routine's
   **Fire URL** and **token** into the two constants at the top (your boss gives you these after
   step 5). The script POSTs `{count, location, industry}` to the routine.

## BOSS — Prerequisite: Claude Code on the web must be enabled

Routines and cloud environments only exist if **Claude Code on the web** is enabled on your plan
(Pro/Max/Team/Enterprise). If you don't see **Routines** at https://claude.ai/code/routines, or no
cloud/environment icon inside a routine, it isn't enabled. Team/Enterprise Owners toggle it at
https://claude.ai/admin-settings/claude-code. Enable it before continuing.

## BOSS — Step 4: Create the routine in your Claude account

At https://claude.ai/code/routines → **New routine**:

- **Name**: Lead Scraper (Airtable)
- **Prompt / Instructions**: paste the entire contents of `ROUTINE_PROMPT.md`
- **Model**: claude-sonnet-4-6
- **Repositories**: the company repo URL from step 1
- **Trigger**: choose **API** (URL + token are generated after you save — see step 5). No schedule
  needed; this is webhook-driven.
- Save with **Create**.

## BOSS — Step 5: Add the secrets, network access, and the API token

There is **no separate "environments" page** — environment settings live inside the routine.

1. **Open the environment settings**: on the routine, click the pencil (**Edit**) → below the
   **Instructions** box click the **cloud icon** showing the environment name (e.g. "Default") →
   hover the environment in the list → click the **settings gear** → the **"Update cloud
   environment"** dialog opens.
2. In that dialog, under **Environment variables**, add:
   - `APIFY_TOKEN` = company Apify token
   - `SERPER_API_KEY` = company Serper key
   - `MILLIONVERIFIER_API_KEY` = company MV key (optional)
   - `LEAD_WEBHOOK_URL` = `https://jkdxs.app.n8n.cloud/webhook/claude-lead-scraper` (optional —
     already the default baked into `webhook_sink.py`; set it only to override)

   No Google service account is needed — the routine POSTs each lead to the n8n webhook, which
   appends to the sheet on its end.
3. In the **same dialog**, set **Network access → Custom** (keep "include default list of common
   package managers" checked) and add these **Allowed domains** — otherwise every API call fails
   with `403 host_not_allowed`. **Add each domain as a SEPARATE entry** (press Enter / Add between
   each — do NOT paste them comma-joined, the field rejects that as one invalid domain):
   ```
   api.apify.com
   google.serper.dev
   bulkapi.millionverifier.com
   www.northdata.com
   www.handelsregister.de
   jkdxs.app.n8n.cloud
   ```
   (If the field accepts wildcards you can shorten to `*.apify.com`, `*.millionverifier.com`,
   plus the other hosts above.) **Save changes.**
4. **Generate the API token**: back in Edit routine → **Select a trigger** → **Add another
   trigger → API** → copy the **Fire URL**, then **Generate token** and copy it (shown once).
   Give both to Abu for step 3.

## YOU — Step 6: Test end to end

1. Submit the Airtable form with a small request (Count 10, a real city, a clear industry).
2. Watch the run at `https://claude.ai/code/scheduled` (your boss may need to share access, or
   test from their account).
3. Confirm rows land in the master Google Sheet and the summary looks honest.

---

### Notes

- **Billing**: Apify/Serper/MV usage bills to whichever company accounts those keys belong to,
  regardless of whose Claude account hosts the routine.
- **Cost per run** is bounded by the 2.5×/max-150 volume cap in `routine_run.py` — a 20-lead
  request fetches ~50 raw, not hundreds.
- **Cloud limits**: the routine has no local files or local MCP — only the cloned repo and the
  secrets. That's why keys are env vars and the Sheet uses a service account (no browser login).
