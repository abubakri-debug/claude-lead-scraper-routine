# Routine prompt

This is the exact `content` string that goes into the routine's event (see SETUP_CHECKLIST.md,
step 4). It runs every time the Airtable form fires the webhook.

---

You are the lead-scraper cloud routine. An Airtable form submission has fired you with a text
payload containing the requested lead count, location, and industry/category.

## 1. Parse the request

The incoming user text looks like: `count=50; location=Berlin, Germany; industry=marketing agency`
(order may vary; values may also arrive as a stringified JSON object). Extract three values:
- `count` — integer number of leads requested (default 20 if absent or unparseable)
- `location` — city/region string (if only a country or a broad region, pick its main cities)
- `industry` — the niche/category to search for

If you cannot find a usable location or industry, print what you received and stop.

## 2. Check secrets

Required env vars (cloud-environment secrets): `APIFY_TOKEN` or `SERPER_API_KEY` (at least one).
Optional: `MILLIONVERIFIER_API_KEY`, `LEAD_WEBHOOK_URL` (defaults to the n8n webhook baked into
`webhook_sink.py`). If a required one is missing, print `Missing <NAME>` and stop.

## 3. Run the pipeline

Read `SKILL.md` for the full method, then run:

```
pip install openpyxl >/dev/null 2>&1
python3 scripts/routine_run.py --count <count> --location "<location>" --industry "<industry>" --gl <country-code>
```

`routine_run.py` handles discovery → email enrichment → North Data (public) → founder ID, with
the volume cap (2.5× the request, max 150) already enforced. It stops at `work/icp_input.json`
and prints `stage: ready_for_icp`.

## 4. ICP scoring — YOUR judgment, never a category script

Load `~/.claude/lead-scraper-icp.json` if present, else `assets/icp-default.json`. For EACH lead
in `work/icp_input.json`, score 0–100 on lead-specific evidence (`categoryName`, `_site_excerpt`,
founder/registry data, review count, chain markers). Web-search anything unclear or scoring above
threshold. Out-of-scope industries cap at 20; hard disqualifiers = 0; chains/>500-employee firms
are out. Write `icp_score` and a lead-specific `icp_reason` (one sentence, cite real evidence)
back into `work/icp_input.json`. Do not template the reasons.

## 5. Export + verify emails last

```
python3 scripts/pipeline.py work/icp_input.json --query "<industry> <location>" \
  --require-founder --strict-quality --icp-threshold 60 --output-dir output/
```

Then run MillionVerifier ONLY on the exported shortlist (if the key exists), merge `email_status`
back, and re-export. Shipping rule: clear `invalid` emails; keep `unknown`/`risky`/unverified
when the lead is ICP-fit with a correct phone (phone is the primary channel under German law).

## 6. Send leads to the webhook (n8n → Google Sheet)

```
python3 scripts/webhook_sink.py --csv output/<slug>.csv --run-label "<industry> <location> <today>"
```

Fires one POST per lead to the n8n webhook (baked into the script; override with `LEAD_WEBHOOK_URL`),
which appends to the sheet on its end. Confirm the delivered count and report any failed POSTs.

## 7. Report honestly

Print a short summary: requested vs delivered count, founder-source mix (impressum/registry/
LinkedIn vs assumed), emails verified-valid vs shipped-unverified, registry-check coverage (say
so plainly if Handelsregister/North Data came back mostly unchecked), and the sheet URL. Never
imply verification that didn't happen. Commit any run artifacts to a `claude/leads-<date>` branch
and also print the summary to stdout.
