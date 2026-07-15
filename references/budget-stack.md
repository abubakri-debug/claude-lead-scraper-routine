# Budget stack: Serper.dev + MillionVerifier

> Cheap tier of the pipeline. Serper Maps discovery is ~10x cheaper than Apify; MillionVerifier
> does real SMTP-level email verification for ~$0.0007/email. Adapted from the community
> `scrape-google-maps` skill; implemented here as `scripts/serper_leads.py` and
> `scripts/millionverifier.py` (same JSON format as the rest of the stack).

## Costs at a glance

| Component | Unit cost | Notes |
|---|---|---|
| Serper Maps (`/maps`) | 3 credits/query (~$0.003) | max 20 places/query; 100 queries per POST |
| Serper Search (`/search`) | 1 credit/lead (~$0.001) | email-snippet search |
| MillionVerifier bulk | ~$0.0007/email | $10 ≈ 14,000 verifications |
| Apify Google Maps | ~$1.50/1,000 places | + add-ons; exhaustive scroll, rich fields |
| Apify contacts add-on | extra per place | emails + socials from business website |

Rule-of-thumb full budget runs: 100 leads ≈ $0.10, 1,000 ≈ $1.50, 10,000 ≈ $13.

## Serper specifics

- Free tier: 2,500 credits, no card (https://serper.dev). Key via `SERPER_API_KEY`.
- Both endpoints accept an **array of up to 100 query objects per POST** — always batch.
- Maps query object: `{"q": "dentist", "location": "Austin, Texas", "gl": "us", "num": 20}`.
- 20 results/query is a hard ceiling → coverage comes from **fan-out**: one query per
  city/district/suburb/ZIP. `serper_leads.py discover` takes repeated `--city` flags and warns
  when results sit at the ceiling (truncation signal → add sub-locations or escalate to Apify).
- Dedupe key is Google `cid` (stored as `placeId: "cid:..."` — pipeline dedupe works as usual).

## Email selection needs AI judgment, not regex

`serper_leads.py emails` auto-assigns only **own-domain** emails (high confidence). Everything
else lands in `email_candidates` for you to judge. Rules (from the source skill — non-negotiable):

- PREFER: emails on the lead's own domain; owner/manager addresses tied to this business;
  freemail (gmail/yahoo) only if it appears repeatedly in the lead's *own* website snippets.
- REJECT: noreply@/donotreply@/wordpress@/mailer@/postmaster@/webmaster@; emails belonging to a
  different company; privacy-policy template emails on third-party domains; quoted/testimonial emails.
- Many Maps listings use Instagram/Facebook as their "website" — never pick `support@instagram.com`
  etc. The script already deny-lists social/aggregator hosts, but apply the same judgment to
  candidates. Accepted candidates: move into the lead's `emails` list, set `email_confidence`.

## MillionVerifier bulk API quirks

- Host is `bulkapi.millionverifier.com` (NOT `api.`); `file_id` and `key` are **query params**.
- Endpoints: `POST /bulkapi/v2/upload` (multipart `file_contents` + `file_name`),
  `GET /fileinfo?file_id&key`, `GET /download?file_id&key&filter=all` (**filter=all required**,
  otherwise 400).
- Polling often **stalls at 95–99%** — `millionverifier.py` caps at 5 min, downloads partial
  results, marks the rest `unverified`, and prints the `file_id` for resuming (`--file-id`).
- Result mapping: `ok`→valid, `catch_all`→risky (domain accepts everything), `unknown`→unknown,
  `disposable`/`invalid`/`error`→invalid. Never call an email "verified" unless status is `valid`.
- Upload failures are almost always missing credits — surface the error verbatim.

## The cost ladder (when to spend more)

1. **Discovery**: Serper first when `SERPER_API_KEY` is set and the user gave (or accepts) a
   city list. Escalate to Apify (`apify_gmaps.py`) when: the user wants *all* places in an area
   (Serper's 20/query ceiling makes exhaustive coverage impractical), needs filters
   (min stars, with/without website, categories) or rich fields (hours, popular times), or has
   no Serper key.
2. **Emails**, cheapest first, each step only on leads still missing an email:
   a. Serper snippet search (~$0.001/lead) → b. free website crawl (`enrich_emails.py`, $0) →
   c. Apify `--contacts` re-scrape or `compass~enrich-google-maps-dataset-with-contacts`, only
   if the remaining gap matters to the user.
3. **Verification**: MillionVerifier on all found emails (cheap enough to always run when the key
   exists); otherwise the pipeline's free DNS check. Apify's `verifyLeadsEnrichmentEmails` add-on
   is redundant when MV is available.
4. **Registry enrichment (North Data)**: free tier first — `northdata.py free` extracts legal
   name/form, register ID, and status from North Data's *public* Google-indexed profiles via
   Serper snippets (~$0.001/company, no ND key, no scraping of their site). Escalate to the paid
   API (`northdata.py enrich`) only for leads where financials, shareholders, or representatives
   matter — those are paywalled and never appear in snippets. Snippet data can lag the live
   register; treat `status` from the free tier as a hint, not authority.

Always present the cost estimate before phases that spend money, and sample-check 1-2 raw
responses early before scaling a run.
