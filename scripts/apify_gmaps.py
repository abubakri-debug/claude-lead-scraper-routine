#!/usr/bin/env python3
"""Run Apify's Google Maps scraper and download results as JSON.

Requires env var APIFY_TOKEN. Stdlib only.

Examples:
  python3 apify_gmaps.py --search "web design agency" --location "Hamburg, Germany" \
      --max 200 --language de --contacts --output raw.json
  python3 apify_gmaps.py --search "dentist" --location "Madrid, Spain" --all --skip-closed \
      --with-website-only --output dentists.json
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from env_loader import load_env  # noqa: E402
load_env()

API_BASE = "https://api.apify.com/v2"
DEFAULT_ACTOR = "compass~crawler-google-places"


def api(method, path, token, body=None, timeout=60):
    url = f"{API_BASE}{path}{'&' if '?' in path else '?'}token={urllib.parse.quote(token)}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:500]
            if e.code in (429, 500, 502, 503) and attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            sys.exit(f"ERROR: Apify API {e.code} on {path}: {detail}")
        except urllib.error.URLError as e:
            if attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            sys.exit(f"ERROR: network failure calling Apify: {e}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--search", action="append", required=True,
                   help="Search term; repeat for multiple terms. Do NOT embed the city here.")
    p.add_argument("--location", required=True, help='Free-text location, e.g. "Hamburg, Germany"')
    p.add_argument("--max", type=int, default=200, help="Max places per search term (default 200)")
    p.add_argument("--all", action="store_true", help="No cap — scrape all places found")
    p.add_argument("--language", default="en", help="Result language code (default en)")
    p.add_argument("--contacts", action="store_true",
                   help="Enable website contact enrichment add-on (emails, social profiles). Extra cost.")
    p.add_argument("--verify-emails", action="store_true",
                   help="Enable Apify email verification add-on (requires leads enrichment; extra cost)")
    p.add_argument("--leads-per-place", type=int, default=0,
                   help="Business leads (people) per place via Apify add-on (extra cost, default 0=off)")
    p.add_argument("--skip-closed", action="store_true", help="Skip temporarily/permanently closed places")
    p.add_argument("--with-website-only", action="store_true", help="Only places that have a website")
    p.add_argument("--min-stars", choices=["two", "twoAndHalf", "three", "threeAndHalf", "four", "fourAndHalf"],
                   help="Minimum star rating filter")
    p.add_argument("--actor", default=DEFAULT_ACTOR, help=f"Actor to run (default {DEFAULT_ACTOR})")
    p.add_argument("--extra-input", help="JSON string merged into the actor input for advanced options")
    p.add_argument("--max-wait", type=int, default=2700, help="Max seconds to wait for the run (default 2700)")
    p.add_argument("--output", required=True, help="Output JSON file path")
    args = p.parse_args()

    token = os.environ.get("APIFY_TOKEN")
    if not token:
        sys.exit("ERROR: APIFY_TOKEN env var is not set. Get a token at "
                 "https://console.apify.com/settings/integrations and `export APIFY_TOKEN=...`")

    run_input = {
        "searchStringsArray": args.search,
        "locationQuery": args.location,
        "language": args.language,
        "skipClosedPlaces": args.skip_closed,
        "scrapeContacts": args.contacts,
    }
    if not args.all:
        run_input["maxCrawledPlacesPerSearch"] = args.max
    if args.with_website_only:
        run_input["website"] = "withWebsite"
    if args.min_stars:
        run_input["placeMinimumStars"] = args.min_stars
    if args.leads_per_place:
        run_input["maximumLeadsEnrichmentRecords"] = args.leads_per_place
        if args.verify_emails:
            run_input["verifyLeadsEnrichmentEmails"] = True
    if args.extra_input:
        run_input.update(json.loads(args.extra_input))

    print(f"Starting actor {args.actor} …")
    print(json.dumps(run_input, indent=2, ensure_ascii=False))
    run = api("POST", f"/acts/{args.actor}/runs", token, body=run_input)["data"]
    run_id = run["id"]
    console_url = f"https://console.apify.com/actors/runs/{run_id}"
    print(f"Run {run_id} started → {console_url}")

    start = time.time()
    status = run["status"]
    while status in ("READY", "RUNNING"):
        if time.time() - start > args.max_wait:
            sys.exit(f"ERROR: run still {status} after {args.max_wait}s. Check {console_url} "
                     f"and re-download later with: GET /actor-runs/{run_id}")
        time.sleep(15)
        run = api("GET", f"/actor-runs/{run_id}", token)["data"]
        status = run["status"]
        stats = run.get("stats", {})
        print(f"  status={status} elapsed={int(time.time()-start)}s items={run.get('itemCount', '?')} "
              f"computeUnits={stats.get('computeUnits', '?')}")

    if status != "SUCCEEDED":
        sys.exit(f"ERROR: run finished with status {status}. Inspect {console_url}")

    dataset_id = run["defaultDatasetId"]
    print("Downloading dataset …")
    items, offset, limit = [], 0, 1000
    while True:
        batch = api("GET", f"/datasets/{dataset_id}/items?format=json&clean=true&offset={offset}&limit={limit}", token)
        items.extend(batch)
        if len(batch) < limit:
            break
        offset += limit

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)

    n = len(items)
    def pct(key):
        return f"{100 * sum(1 for i in items if i.get(key)) / n:.0f}%" if n else "0%"
    emails = sum(1 for i in items if i.get("emails") or i.get("email"))
    print(f"\nDone: {n} places → {args.output}")
    if n:
        print(f"  with website: {pct('website')} | with phone: {pct('phone')} | "
              f"with email: {100 * emails / n:.0f}%")
        if not args.all and n >= args.max * len(args.search):
            print("  WARNING: hit the --max cap — coverage is likely truncated. "
                  "Re-run with a higher --max or --all.")


if __name__ == "__main__":
    main()
