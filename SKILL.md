---
name: lead-scraper
description: >-
  Scrape, verify, enrich, and export business leads from Google Maps (via Apify) with optional
  North Data company-registry enrichment and website email extraction. Use this skill whenever the
  user asks to find leads, prospects, businesses, agencies, shops, restaurants, or companies in a
  place — e.g. "give me all the web design agencies in Berlin", "find plumbers in Manchester with
  emails", "build a lead list of dentists in Madrid", "scrape Google Maps for X in Y" — even if
  they don't say "scrape" or "Apify". Also use it for people-prospecting via LinkedIn ("find
  marketing directors in Munich"), SERP-based company discovery, enriching an existing lead list
  with emails or registry data (legal form, financials, directors), or for deduping/verifying/
  exporting leads to CSV/Excel. Incorporates Apify's official ultimate-scraper actor catalog, so
  it also covers lead workflows on Instagram, Facebook, X, Reddit, Yelp, and other platforms.
---

# Lead Scraper

Turn a request like "give me all the website agencies in Hamburg" into a verified, deduplicated, founder-level CSV + Excel lead list. Two flows — pick by niche:

**Flow A — person-first (DEFAULT for B2B niches visible on LinkedIn: agencies, consultants, e-commerce).** Start from verified *people*, not businesses — this kills the fake-founder problem at the source:

1. Find founders directly: `run_actor.py --actor harvestapi~linkedin-profile-search` with founder/owner keywords + niche + location (PPE — apply the cost protocol in `references/gotchas.md`). Output: real names, roles, `currentCompany`, profile URLs. **Volume policy**: fetch ~2.5× the lead count the user asked for (filter attrition buffer), capped at 150; no count stated → default `limit: 50`. Never exceed 500 unless the user explicitly asks — `run_actor.py` refuses uncapped or >500 inputs without `--allow-unlimited`, which you only pass after the user has named a bigger number.
2. Attach the business: per person, Serper-search the company → website; `serper_leads.py discover` or a Maps lookup for phone/address.
3. Verify the business: `founders.py` (register IDs, site excerpt, Impressum cross-check), `northdata.py free`, `handelsregister.py`.
4. ICP-score every lead (Step 3.5c — real judgment, never a category script).
5. **Email verification LAST** (Step 4), only on ICP-fit leads.

**Flow B — maps-first (niches weak on LinkedIn: local trades, wellness, restaurants).** The classic **scrape → check coverage → enrich → qualify → export**, steps below, with founder identity reconstructed from Impressum/LinkedIn-slug/business-name evidence. Same rule: verification last, ICP always.

## Phase 0 — Keys (before ANY scraping, in ONE clear message)

Do this first — never launch a scrape and let it fail on a missing key. Check what's available:

```bash
python3 scripts/env_loader.py
```

This prints SET/MISSING for all four keys (it reads env vars *and* the persisted file `~/.claude/lead-scraper.env`, where keys survive across sessions). If anything needed is missing, send the user **one** consolidated message — not a drip of questions — structured like:

> To scrape leads I need at least ONE of these two (either works, both is best):
> - **SERPER_API_KEY** — cheapest, recommended to start. Sign up at **serper.dev** (2,500 free credits, no card), copy the key from the dashboard.
> - **APIFY_TOKEN** — exhaustive coverage + 100 other platforms. **console.apify.com** → Settings → API & Integrations.
>
> Optional, add anytime: **MILLIONVERIFIER_API_KEY** (real email verification, ~$0.0007/email, app.millionverifier.com). German registry data (North Data) needs NO key — the skill uses its free public info via Serper.
>
> Paste any key here and I'll save it locally (one-time — you won't be asked again), or export it yourself in the terminal if you'd rather keep it out of the chat.

When the user pastes a key: sanity-check that it looks like a key (long alphanumeric, not a URL or sentence — reject and re-ask otherwise), then persist it:

```bash
python3 scripts/env_loader.py SERPER_API_KEY "<pasted-value>"
```

All scripts auto-load `~/.claude/lead-scraper.env`, so once saved everything works with no exports or re-sourcing. Confirm "Saved — won't ask again", say which pipeline tiers are now available, and move on.

Python 3.9+; scripts are stdlib-only except optional `openpyxl` for Excel export (`pip install openpyxl`; pipeline still writes CSV without it). Every script supports `--help`. **Run scripts in the foreground** — they finish in 1–5 minutes and print their own progress; backgrounding them just creates wait-and-poll busywork.

## Step 0 — Clarify only what's truly ambiguous

Don't interrogate the user. Infer sensible defaults: language from the country, `--max 200` for maps scrapes unless "all" was implied ("give me ALL the agencies" → no cap), skip closed places, prefer places with websites for B2B queries. Ask only if the location is ambiguous (e.g. "Springfield") or the niche is vague.

**Volume discipline (applies to every paid source)**: scrape ~2.5× the requested lead count to survive founder/ICP attrition — not 10×. User asks for 20 → fetch ~50; asks for 100 → ~250; names no number → 50 for people search, 200 for maps. Anything beyond 500 requires the user to have explicitly asked for that scale.

**Cost awareness**: the Google Maps actor costs ~$1.50 per 1,000 places, contact enrichment extra. For requests likely to exceed ~2,000 places, tell the user the estimated scale before launching. For pay-per-event actors (all LinkedIn actors, SEO tools), follow the cost protocol in `references/gotchas.md`: estimate first (`run_actor.py --info-only`), warn above $5, get explicit confirmation above $20.

**Pick the right pipeline**: Google Maps is the default for "businesses in a place", but not every lead request is a maps request. People by role → LinkedIn; niche companies with no map category → SERP discovery; existing URL list → contact extraction. The decision table and seven ready pipelines are in `references/lead-workflows.md` — read it whenever the request isn't a plain local-business search. Any actor from `references/actor-index.md` can be run with `scripts/run_actor.py --actor <ID> --input '<JSON>'`.

**Climb the cost ladder, don't start at the top** (details in `references/budget-stack.md`):

| Stage | Cheap default | Escalate to | Escalate when |
|---|---|---|---|
| Discovery | Serper Maps (`serper_leads.py discover`, ~$0.003/query, 20 places each) | Apify (`apify_gmaps.py`, ~$1.50/1k) | user wants ALL places, needs filters/rich fields, or no Serper key |
| Emails | Serper snippets (`serper_leads.py emails`, ~$0.001/lead) → free crawl (`enrich_emails.py`) | Apify `--contacts` | remaining email gap matters to the user |
| Verification | MillionVerifier (`millionverifier.py`, ~$0.0007/email) — run LAST, on the ICP-fit shortlist only | — | no MV key → pipeline's free DNS check |
| Registry | Free public North Data snippets (`northdata.py free`) + Impressum/Handelsregister | — | paid ND API only if the user ever adds a key |

A typical 1,000-lead budget run lands around $1.50 all-in vs ~$5+ Apify-only — same deliverable.

## Step 1 — Scrape Google Maps

**Budget tier first** (when `SERPER_API_KEY` is set): fan out one query per city/district —

```bash
python3 scripts/serper_leads.py discover \
  --search "web design agency" --search "webdesign agentur" \
  --city "Hamburg, Germany" --city "Norderstedt, Germany" --city "Pinneberg, Germany" \
  --gl de --output work/raw_gmaps.json
```

The script warns when results sit at Serper's 20-per-query ceiling — that's the signal to add more sub-locations or escalate. **Serper sometimes ignores the location** and returns far-away fallback matches (observed: Minneapolis results for a Saarland query), so for any well-defined region pass `--postal-prefix` upfront (e.g. `--postal-prefix 66` covers all of Saarland). Forgot it? **Never re-scrape** — `serper_leads.py filter --input raw.json --output clean.json --postal-prefix 66` re-filters the existing file for zero credits. For a whole state/region, query its individual cities, not the state name. **Apify tier** (exhaustive coverage, filters, rich fields):

```bash
python3 scripts/apify_gmaps.py \
  --search "web design agency" --search "webdesign agentur" \
  --location "Hamburg, Germany" \
  --max 200 --language de --contacts --skip-closed \
  --output work/raw_gmaps.json
```

Key flags: repeat `--search` for term variants; `--contacts` turns on the actor's website-contact enrichment (emails + social profiles — usually the cheapest way to get emails); `--with-website-only` for B2B lists; `--all` to remove the per-search cap. The script starts the run, polls until completion, downloads the dataset, and prints a summary (places found, % with website/phone/email).

**Choose search terms like a local**: include synonyms and the local language ("web design agency", "webdesign agentur", "internetagentur"). 2–4 distinct terms beat one generic term. A single search term maxes out around 120 results per Google Maps scroll limit when location is embedded in the term — always use `--location`, never put the city inside `--search`.

## Step 2 — Double-check coverage (this is what makes the skill strong)

Never trust the first pass. After the scrape:

1. Read the summary. If the count suspiciously hits a round limit (exactly `--max`, or ~120 per term), coverage is likely truncated → re-run with `--all` or split the area (`--location` per district/postal code) and merge.
2. Sanity-check against expectation: a major city should have hundreds of agencies, a village a handful. If the count looks low, run a second pass with additional synonym terms and merge — `pipeline.py` dedupes across files, so over-fetching is safe and cheap.
3. Spot-check 3–5 rows: does the category match the request? If irrelevant categories dominate (e.g. "printing shop" for "agency"), re-scrape with tighter terms or filter by `categoryName` in the pipeline step.

## Step 3 — Enrich

**Emails/socials** — waterfall, cheapest first, each step only on rows still missing an email:

```bash
python3 scripts/serper_leads.py emails --input work/raw_gmaps.json --output work/e1.json --gl de
python3 scripts/enrich_emails.py --input work/e1.json --output work/enriched.json
```

The Serper step auto-assigns own-domain emails and puts ambiguous finds in `email_candidates` — review those with judgment (rules in `references/budget-stack.md`: never accept noreply@/social-platform addresses; freemail only if clearly this business's). If a meaningful gap remains and the user wants max coverage, the Apify `--contacts` add-on (or `compass~enrich-google-maps-dataset-with-contacts` on the run's dataset) is the paid last resort.

**Email verification runs LAST — not here.** Don't verify 900 emails to ship 50 leads. Order: enrich → founders → registry → ICP → *then* `millionverifier.py` on the ICP-fit shortlist only (Step 4). Shipping rule: `invalid` emails are cleared; `unknown`/`risky`/unverified emails SHIP when the lead is ICP-fit and has a correct phone number — phone is the primary channel (German law restricts cold email), the email is a bonus. Disclose the split in the summary.

**Registry data (North Data, free public info only)** — no API key involved. Uses North Data's public Google-indexed profiles via Serper snippets (~$0.001/company): legal name, legal form, register ID, status hint, and the profile URL. Run on all DE/AT/CH leads:

```bash
python3 scripts/northdata.py free --input work/verified.json --output work/enriched_nd.json --gl de
```

Financials/shareholders/representatives are paywalled and NOT part of this pipeline — do not suggest the paid API unless the user brings it up (a `northdata.py enrich` subcommand exists if they ever add a key). Founder verification comes from Impressum + Handelsregister instead (Step 3.5).

North Data can also *originate* leads when the query is registry-shaped ("GmbHs in Munich with revenue > 1M", "newly founded companies in Hamburg") — use `northdata.py power --keywords ... --address ...` for that instead of Google Maps, or combine both. Pick the source that fits the query: Google Maps for local/consumer-visible businesses, North Data for legal/financial criteria, both for the richest result.

## Step 3.5 — Qualify: founders, registry, ICP (MANDATORY — every run, no exceptions)

The deliverable is founder-level, ICP-matched leads — never a raw business dump. Do not skip these sub-steps for "simple" or research-style requests; the user has been explicit that every list must be founder-only and ICP-scored. Three sub-steps:

**a) Identify founders** (the lead IS the founder; no founder = not a lead):

```bash
python3 scripts/founders.py --input work/verified.json --output work/founders.json
```

Crawls Impressum/about/team pages (German Impressum legally names the Geschäftsführer — for owner-led businesses that's the founder), pulls names + roles + personal LinkedIn + register IDs, and flags placeholder/parked websites. Sole traders often list "Inhaber" — that counts.

**b) Verify against Handelsregister** (official German registry; EXPERIMENTAL scraper — run only on the shortlist, keep the 3s delay):

```bash
python3 scripts/handelsregister.py --input work/founders.json --output work/hr.json --max 100
```

Confirms the business still exists (`register_status`), cross-checks the Impressum register ID, and flags mismatches. `not_found` is only disqualifying for GmbH/UG/AG-type companies — sole traders legitimately aren't registered. If the site blocks (it changes often), the script degrades to `unchecked` and North Data public status is the fallback.

**c) ICP scoring** — this is YOUR job, not a script's. **Never score with a category-bucket script** — a real run did that and let a 4,000-person global network through at 75 because its Maps category matched. Load the config: use `~/.claude/lead-scraper-icp.json` if it exists, otherwise copy `assets/icp-default.json` there first. Merge any per-run criteria the user stated (e.g. "website agencies, ~100k/month, ~5 employees") over the config for this run only. Then score each lead individually on lead-specific evidence: `categoryName`, `_site_excerpt`, founder/registry data, review count and multi-location markers (chain signals), and — for anything unclear or scoring above the threshold — a quick web search of the company. Check size/chain status explicitly: "offices in", career pages, international domains are >500-employee tells. Score 0–100 per the config's rules (out-of-scope caps at 20; hard disqualifiers = 0). Every `icp_reason` must cite evidence specific to that lead — if your reasons read like templates, you're not scoring, you're bucketing. Write results back into the JSON:

```python
# merge {placeId: (score, reason)} you assessed into the lead file
import json
leads = json.load(open("work/hr.json"))
scores = {"cid:123": (85, "web design agency, ~6 staff, founder-led"), ...}
for l in leads:
    if l.get("placeId") in scores:
        l["icp_score"], l["icp_reason"] = scores[l["placeId"]]
json.dump(leads, open("work/icp.json", "w"), ensure_ascii=False, indent=1)
```

Keep `icp_reason` to one short sentence — it's a CSV column the user reads at a glance.

## Step 4 — Verify, dedupe, score, export

```bash
python3 scripts/pipeline.py work/icp.json \
  --query "web design agency Hamburg" \
  --require-founder --strict-quality --icp-threshold 60 \
  --output-dir output/
```

Accepts multiple input files (merges them). **`--require-founder --strict-quality --icp-threshold 60` are ALWAYS on — every run, every request type.** This is a standing user requirement, not a judgment call: a lead without an identified founder/owner is not a lead, and unscored leads don't ship. Solo practitioners pass naturally (their name IS the business — founders.py auto-detects that); what these filters exclude on purpose are chains, branch offices, and institutions where the contact wouldn't be the decision-maker. The only per-run adjustments allowed: the threshold value (if the user asks) and category constraints, which you should ALWAYS also set since broad terms sweep in neighbors (a "wellness coach" search returns gyms and physios): `--include-category "coach" --include-category "counselor"`. If filtering leaves fewer leads than the user asked for, deliver the qualified ones and say what was excluded and why — never pad the list with unqualified entries. The pipeline:

- **Dedupes** by Google placeId, then normalized phone, then website domain.
- **Verifies**: email syntax + domain DNS resolution (flags dead domains), phone normalization, URL normalization.
- **Filters**: drops leads without an identified founder, below the ICP threshold, or with junk websites — and reports exactly how many each filter removed.
- **Scores** 0–100, phone-first (phone 25 > email 20 > website 15 > founder 15; registry + verified-email bonuses) — phone matters most because German law (UWG §7) restricts cold email, so calls come first.
- **Exports** CSV + Excel sorted by ICP score then lead score, one column per social platform (linkedin, facebook, instagram, x_twitter, youtube, tiktok) plus separate founder columns (founder_name, founder_role, founder_linkedin), and `report.md` with dedupe/filter stats.

**Then verify emails — the actual last step.** Build the shortlist JSON of leads that survived the filters, run `millionverifier.py` on it (now you're paying for ~50 verifications instead of ~900), merge `email_status` back, and re-run the pipeline export so the final file carries verification status.

Read `report.md` and relay the headline numbers to the user. The final summary MUST disclose, honestly: emails verified-valid vs shipped-unverified (counts), registry-check coverage (if Handelsregister came back 0/N `unchecked`, say the check failed — never imply verification that didn't happen), founder-source mix (impressum/registry/LinkedIn vs assumed-from-name), and any coverage caps hit during scraping. If more than ~20% of rows were flagged or dropped, offer a re-run with adjusted parameters.

**Output location**: write final files to a directory the user can find — their project directory (the original working directory) under `output/`, never a temp scratchpad. Tell them the exact path.

## Step 5 — Append to the master Google Sheet

Every run's final leads go into the user's master sheet (it grows run over run; place_ids already in the sheet are skipped, so re-runs don't duplicate):

```bash
python3 scripts/gsheets.py append --csv output/<slug>.csv --run-label "<query + region>"
```

The user's master sheet: ID `1ldfNyghlKqriE1aEHFCSUBMjikgj5zrMX_1FBcGvksk`, tab gid `1347092156`. If `env_loader.py` shows GSHEET_ID missing, save these once:

```bash
python3 scripts/env_loader.py GSHEET_ID 1ldfNyghlKqriE1aEHFCSUBMjikgj5zrMX_1FBcGvksk
python3 scripts/env_loader.py GSHEET_GID 1347092156
```

Auth is a Google service account — one-time setup, walk the user through it the first time (the script's `--help` has the exact steps): enable the Sheets API in console.cloud.google.com, create a service account with a JSON key, **share the spreadsheet with the service account's client_email as Editor**, save the key path via `env_loader.py GOOGLE_SERVICE_ACCOUNT_FILE`. Needs `pip install google-auth`. If a Google Sheets/Drive MCP connector is available in the session instead, using it is fine — same outcome, append-don't-overwrite.

## Reference files

- `references/apify.md` — Google Maps actor deep-dive: full input schema notes, API endpoints, costs, troubleshooting. Read when a maps scrape fails or needs tuning beyond the flags above.
- `references/lead-workflows.md` — seven multi-source pipelines (LinkedIn prospecting, SERP discovery, contact extraction, ABM research, warm-lead mining, Reddit intent) with a decision table. Read whenever the request isn't a plain local-business search.
- `references/actor-index.md` — Apify's official catalog of ~100 actors across 15+ platforms. Read when a lead source outside Google Maps/North Data is needed; run any of them via `scripts/run_actor.py`.
- `references/gotchas.md` — Apify's official cost guardrails (PPE estimation protocol), platform rate limits, error recovery. Read before running unfamiliar or pay-per-event actors.
- `references/budget-stack.md` — Serper + MillionVerifier details: batching, the 20-results ceiling, email-candidate judgment rules, MV API quirks, and the full cost ladder. Read before any budget-tier run.
- `references/northdata.md` — endpoints, power-search parameters, detail flags, billing notes. Read before any non-trivial North Data usage.

## Failure playbook

- `401/403` from Apify → token invalid/expired; ask user to re-export `APIFY_TOKEN`.
- Run stuck in `RUNNING` beyond `--max-wait` → the script prints the run URL; offer the user the console link and retry with smaller `--max`.
- Zero results → almost always a location/term mismatch: verify the location string on nominatim.openstreetmap.org phrasing (City + Country, nothing more), try local-language terms.
- North Data `404` on lookup → normal for small unregistered businesses; the enricher records `northdata_match: none` and moves on. `503` → retried automatically up to 3×.
- MillionVerifier Cloudflare error 1010/403 → the script already sends a browser UA and retries with backoff; if it still fails, don't loop — fall back to the pipeline's DNS check, tell the user verification was skipped and why, and suggest retrying later or verifying via the MV dashboard upload.
- Serper results from the wrong region → filter with `--postal-prefix`, re-check the spread line.
- Respect the data: results may include personal data (GDPR). Don't scrape reviewer personal data unless asked, and remind the user of compliance if they request bulk personal emails.
