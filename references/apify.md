# Apify reference (verified July 2026)

## Actors

| Actor | ID | Use for |
|---|---|---|
| Google Maps Scraper (Compass, Apify-maintained) | `compass~crawler-google-places` | Default. Full data, contact/leads/email-verification add-ons. ~$1.50/1,000 places. |
| Google Maps Extractor | `compass~google-maps-extractor` | Faster/cheaper for basic fields only (no add-ons). Hundreds of places quickly. |
| Google Maps Email Extractor | `lukaskrivka~google-maps-with-contact-details` | Alternative when the goal is purely contact details per place. |
| Google Maps Reviews Scraper | `compass~Google-Maps-Reviews-Scraper` | Reviews for known place URLs. |
| Northdata Search Scraper (3rd party) | `powerai~northdata-search-scraper` | Scrapes northdata.com search UI — only if the user has no official North Data API key. |

Pass a different actor to `apify_gmaps.py` via `--actor` (input schema is compatible across the compass actors).

## API endpoints (token via `?token=` or `Authorization: Bearer`)

- Start run: `POST https://api.apify.com/v2/acts/{actorId}/runs` (body = actor input JSON)
- Run status: `GET /v2/actor-runs/{runId}` → `data.status` ∈ READY/RUNNING/SUCCEEDED/FAILED/ABORTED/TIMED-OUT
- Results: `GET /v2/datasets/{data.defaultDatasetId}/items?format=json&clean=true&offset=0&limit=1000`
- Small quick jobs (<5 min, <300s hard limit): `POST /v2/acts/{actorId}/run-sync-get-dataset-items`

## Key input fields for `compass~crawler-google-places`

- `searchStringsArray` (array) — search terms; supports `place_id:ChIJ...` entries. City in the term caps results at ~120 (scroll limit) → keep location out of terms.
- `locationQuery` (string) — "City, Country" free text; simplest format wins. Alternative structured fields: `countryCode`, `city`, `state`, `county`, `postalCode` (postal code only with country, not city).
- `customGeolocation` (GeoJSON) — precise polygons/circles for area splits.
- `maxCrawledPlacesPerSearch` (int) — omit to scrape all.
- `language` (e.g. `en`, `de`), `skipClosedPlaces` (bool), `website` = `allPlaces|withWebsite|withoutWebsite`, `placeMinimumStars`, `categoryFilterWords` (array; risky — miscategorized places get filtered out), `searchMatching` = `all|only_includes|only_exact`.
- Add-ons ($): `scrapeContacts` (emails + socials from the business website; big chains excluded), `scrapeSocialMediaProfiles` (object of booleans), `maximumLeadsEnrichmentRecords` (int; people/job titles/LinkedIn per place — multiplier cost!), `leadsEnrichmentDepartments` (e.g. `["sales","c_suite"]`), `verifyLeadsEnrichmentEmails` (bool; needs leads enrichment), `scrapePlaceDetailPage` (opening hours, popular times…), `maxReviews`, `maxImages`, `maxQuestions`.

## Useful output fields

`title`, `categoryName`, `address`, `street`, `city`, `postalCode`, `countryCode`, `website`, `phone`, `phoneUnformatted`, `totalScore`, `reviewsCount`, `url` (maps link), `placeId`, `location {lat,lng}`, `permanentlyClosed`, `temporarilyClosed`; with contacts add-on: `emails`, `linkedIns`, `instagrams`, `facebooks`, `twitters`, `youtubes`.

## Troubleshooting

- **Result count exactly 120 per term**: Google scroll limit — split the area (postal codes or `customGeolocation` polygons) or add more specific terms.
- **`ACTOR-MEMORY-LIMIT` / run FAILED**: retry; if persistent, lower `--max` or check the run log in the console.
- **Rate limits (429)**: the script retries with backoff; runs themselves are queued by Apify, so parallel runs are fine within plan limits.
- **Cost estimate before running**: places × $0.0015, + contacts add-on per place with website (see the actor's Pricing tab; discounts on higher plans).
