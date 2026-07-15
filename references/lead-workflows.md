# Multi-source lead workflows

> Pipelines vendored from Apify's official `apify-ultimate-scraper` skill (lead-generation,
> contact-enrichment, company-research guides), adapted to this skill's scripts. Every pipeline
> ends in `pipeline.py` for dedupe/verify/score/export. LinkedIn actors are PPE — apply the cost
> protocol in `gotchas.md` before running.

## 1. Local business leads with email enrichment (default)

Covered by SKILL.md steps 1–4. Alternative to the `--contacts` add-on: run the base scrape, then
pipe the run's dataset into `compass/enrich-google-maps-dataset-with-contacts`:

```bash
python3 scripts/run_actor.py --actor compass~enrich-google-maps-dataset-with-contacts \
  --input '{"datasetId": "<defaultDatasetId from the gmaps run>"}' --output work/contacts.json
```

Gotcha: results vary by language/location — set `language` explicitly, use city-level `locationQuery`.

## 2. B2B prospects via LinkedIn (people, not places)

When the user wants *people* by role/industry ("marketing directors in Hamburg"):

1. `harvestapi~linkedin-profile-search` — input: `{"keyword", "location", "title", "limit"}`
   → `fullName`, `headline`, `profileUrl`, `currentCompany`.
2. `harvestapi~linkedin-profile-scraper` — pipe `profileUrl`s into `urls`, set `"includeEmail": true`
   (~$0.01/profile → ~$5 per 500; confirm cost first) → `email`, `phone`, `experience[]`.
3. `pipeline.py` merge/export (map `fullName`→name manually or keep raw JSON columns).

Batches under 100 profiles, runs ≥5 min apart; empty results happen — retry once.

## 3. SERP-based company discovery

For niche B2B queries Google Maps can't answer ("companies doing X"):

1. `apify~google-search-scraper` — `{"queries": [...], "countryCode": "de"}` → `organicResults[].url`.
2. Filter to root domains only (drop blog-post URLs, directories, LinkedIn links).
3. `apify~website-content-crawler` — `{"startUrls": [...], "maxCrawlDepth": 2, "maxCrawlPages": 5}`
   → clean site text; qualify each company against the user's ICP yourself (you're the AI step).
4. Extract contacts: `enrich_emails.py` on the domain list, or `vdrmota~contact-info-scraper` for batches.
5. `pipeline.py` export.

## 4. Contact extraction from an existing URL/domain list

User already has websites (Apollo export, CRM dump):

- Batch, cost-effective: `vdrmota~contact-info-scraper` — `{"startUrls": [...], "maxDepth": 2}`.
- Real-time/low-latency: `compass~contact-details-scraper-standby` (<1s, standby actor).
- Free/local: `enrich_emails.py` (this skill's crawler) — fine for ≤ a few hundred sites.

Filter input for `http` URLs first — LinkedIn URLs in the list will block crawlers.

## 5. Company intelligence / ABM profiling

Target-account research (firmographics + key people):

1. `apify~website-content-crawler` on company domains, `includeUrlGlobs` for about/pricing/team/careers.
2. `harvestapi~linkedin-company` for `employeeCount`, `industry`, `headquarters`.
3. North Data lookup (`northdata.py lookup --financials --representatives`) for registry
   financials and directors where covered (DACH+).
4. Synthesize per-account signals (size, tech stack, key personnel, pain signals) yourself; export.

Keep `maxCrawlPages` ~5 per company or depth-2 crawls balloon to 20–50 pages.

## 6. Warm leads from LinkedIn post comments

Prospects engaging with competitor/thought-leader content:

1. `harvestapi~linkedin-post-comments` — `{"postUrl", "maxComments"}` (~$0.005/comment).
2. `harvestapi~linkedin-profile-scraper` on commenter `profileUrl`s with `includeEmail: true`.
3. Filter by ICP (headline/company), export. ~$1.50 per 100 commenters enriched.

Private/restricted posts return zero items with no error — test the post URL first.

## 7. Reddit intent mining

Prospects describing the exact problem the user's product solves:

1. `trudax~reddit-scraper-lite` — `{"startUrls": [subreddits], "searchTerms": [pain keywords], "maxItems", "sort"}`.
2. Qualify posts against ICP yourself; output post URLs + intent summary.

No email path — Reddit is pseudonymous; deliverable is intent signals for manual outreach.

## Choosing a pipeline

| User asks for… | Pipeline |
|---|---|
| businesses/shops/agencies in a place | 1 (Google Maps, default) |
| people by role/title/industry | 2 (LinkedIn) |
| companies by niche keyword, no map category | 3 (SERP) |
| emails for a list they already have | 4 (contact extraction) |
| deep research on named accounts | 5 (ABM) + North Data |
| engaged/warm prospects | 6 (post comments) |
| people with a specific problem | 7 (Reddit) |

Combine freely: e.g. 1 + North Data enrichment + 5 for the top-scored leads.
