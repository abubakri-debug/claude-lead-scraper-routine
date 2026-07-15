# Gotchas and cost guardrails

> Vendored from Apify's official `apify-ultimate-scraper` skill (github.com/apify/agent-skills),
> adapted for this skill's scripts.

## Pricing models

| Model | How it works | Action before running |
|-------|-------------|----------------------|
| FREE | No per-result cost, only platform compute | None needed |
| PAY_PER_EVENT (PPE) | Charged per result item | MUST estimate cost first |
| FLAT_PRICE_PER_MONTH | Monthly subscription | Verify user has active subscription |

Check pricing/deprecation: `python3 scripts/run_actor.py --actor <ID> --info-only`
(reads pricing model, per-event price, and `isDeprecated`).

## Cost estimation protocol

Before running any PPE actor:

1. Get the per-event price (`--info-only`).
2. Multiply by the requested result count.
3. Present the estimate to the user as a rough figure — actual costs vary with retries, data
   complexity, and platform changes; the billing dashboard is the source of truth.
4. Estimate > $5: warn explicitly. Estimate > $20: require explicit user confirmation.

## Common pitfalls

- **Cookie-dependent actors**: some social scrapers need cookies/login. Auth errors or empty
  results → check the actor's README for "cookies", "login", "session", "proxy".
- **Rate limiting on large scrapes**: use `"proxyConfiguration": {"useApifyProxy": true}` when
  available; keep concurrency reasonable; split 1,000+ result jobs into batches.
- **Empty results**: too-narrow query or geo-restriction; platform blocking without proxy; missing
  cookies; or a wrong input field name — always verify against the actor's input schema.
- **Limit field naming varies**: `maxResults` / `resultsLimit` / `maxItems` (output items) vs
  `maxCrawledPages` / `maxRequestsPerCrawl` (pages visited). Fetch the schema, don't guess.
- **Deprecated actors**: if `isDeprecated: true`, search for a replacement; prefer `apify`-tier.
- **LinkedIn pricing**: all PPE. `harvestapi/` cheapest ($0.001–0.01/result), `apimaestro/`
  pricier ($0.005–0.02), `dev_fusion/` mid-range with email enrichment. Compare before selecting.
- **SEO tools (`radeance/`)**: highest per-result costs ($0.005–0.0275). Estimate carefully.

## Error recovery

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `status: FAILED` | Actor crashed or input invalid | Read `statusMessage`; run log at console.apify.com/actors/runs/RUN_ID/log |
| `isDeprecated: true` | Actor end-of-life | Search store for replacement |
| Empty dataset | Narrow query, geo-restriction, anti-bot | Broaden terms; enable Apify Proxy; check README |
| Run > 10 min | Large scrape / slow target | Scripts already poll async; raise `--max-wait` |

## Platform-specific rate limits

- **Instagram**: aggressive limits — keep results under 200/run; API-based scraper has higher limits.
- **LinkedIn**: blocks at scale — batches under 100 profiles, runs ≥5 min apart, expect occasional empties.
- **TikTok**: increasing anti-bot — enable residential proxy for blocked regions.
- **Google Maps**: stable; set `language` explicitly; prefer specific location queries over broad ones.
- **Amazon/e-commerce**: heavy anti-bot; use `apify/e-commerce-scraping-tool`.

## Why Apify actors instead of raw HTTP scraping

Cloudflare/WAF bypass, JS rendering for SPAs, TLS-fingerprint rotation, session/cookie management,
and serverless scale are all handled by the actors — raw `requests`/Puppeteer hits these walls.
Toughest sites: `apify/camoufox-scraper`.
