# North Data API reference (verified July 2026)

Official company-registry database (strongest: DE; also AT, CH, UK and more — live coverage at
https://www.northdata.com/_coverage). Auth: header `X-Api-Key: XXXX-XXXX` (or `api_key` param).
JSON by default. Requests are billed — don't loop wastefully.

## Endpoints (base `https://www.northdata.com/_api`)

| Purpose | Endpoint |
|---|---|
| Retrieve one company | `GET /company/v1/company?name=...&address=...` |
| Power search | `GET /search/v1/power?keywords=...&address=...` |
| Universal search (one query string) | `GET /search/v1/universal?query=...` |
| Autocomplete | `GET /search/v1/suggest?query=...` |

Company lookup alternatives: `registerId` + `registerCity` (Germany), or internal `id`.
Add `fuzzy=true` to tolerate name variations (used by the enricher).

## Power search parameters

`keywords` (matches name/subject/segment), `address` (any precision), `maxDistanceKm` (address must
geocode — city-level or better), `status` (`active|terminated|liquidation`, pipe-separated),
`countries` (ISO codes, pipe-separated), `segmentCodes` + `segmentCodeStandard` (e.g. WZ2008 codes
for industry filtering), `legalForm` (e.g. `GmbH|AG`), financial filters via `indicatorId` +
`lowerBound`/`upperBound` (indicator list: https://www.northdata.com/_coverage#indicators),
event filters via `eventType` + `minDate`/`maxDate`.

**Pagination**: default 15 results; response contains `nextPos` → repeat with `pos={nextPos}` until absent.

## Detail flags (add to lookup or power search)

`financials`, `sheets` (balance sheet/earnings), `history`, `events` (+ `eventType`, `maxEvents`),
`relations`, `owners`, `ownerships`, `representatives` (managing directors/board), `extras`.
Power search returns base data only unless one of these is set.

## Response shape (company)

```json
{"id": "57514825",
 "name": {"name": "1000mikes AG", "legalForm": "AG"},
 "address": {"street": "...", "postalCode": "20099", "city": "Hamburg", "country": "DE", "lat": 0, "lng": 0},
 "register": {"city": "Hamburg", "id": "HRB 103038", "uniqueKey": "..."},
 "status": "active|liquidation|terminated"}
```

## Errors

400 bad params · 404 company not found (normal for unregistered sole traders — not an error) ·
503 retry up to 3× · `language=en` for English role/event labels.

## When North Data beats Google Maps as lead source

Registry-shaped queries: filter by legal form, revenue/employees (financial indicators), founding
date (event filter `eventType=founding` style), industry segment codes, or company status. Combine:
originate with power search, then match websites/phones via a Google Maps pass, merge in pipeline.py.
