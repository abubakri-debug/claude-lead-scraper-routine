#!/usr/bin/env python3
"""Generic Apify actor runner: start any actor, poll, download the dataset.

Use for actors beyond Google Maps (see references/actor-index.md), e.g. LinkedIn,
Google Search, contact-info scrapers. Requires APIFY_TOKEN. Stdlib only.

  python3 run_actor.py --actor harvestapi~linkedin-profile-search \
      --input '{"keyword": "marketing director", "location": "Hamburg", "limit": 50}' \
      --output linkedin.json
  python3 run_actor.py --actor vdrmota~contact-info-scraper --input @input.json --output out.json
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
    p.add_argument("--actor", required=True, help="Actor ID, slash or tilde form (a/b or a~b)")
    p.add_argument("--input", required=True, help="Actor input as JSON string, or @path/to/file.json")
    p.add_argument("--output", required=True, help="Output JSON file for dataset items")
    p.add_argument("--max-wait", type=int, default=2700, help="Max seconds to wait (default 2700)")
    p.add_argument("--info-only", action="store_true",
                   help="Print actor pricing/deprecation info and exit (cost check before PPE runs)")
    p.add_argument("--allow-unlimited", action="store_true",
                   help="Skip the result-limit guard (only when the user explicitly asked for "
                        "an uncapped run)")
    args = p.parse_args()

    token = os.environ.get("APIFY_TOKEN")
    if not token:
        sys.exit("ERROR: APIFY_TOKEN env var is not set.")

    actor = args.actor.replace("/", "~")

    if args.info_only:
        info = api("GET", f"/acts/{actor}", token)["data"]
        out = {"name": info.get("name"), "title": info.get("title"),
               "isDeprecated": info.get("isDeprecated"),
               "pricingInfo": info.get("pricingInfos", [{}])[-1] if info.get("pricingInfos") else
               info.get("currentPricingInfo")}
        print(json.dumps(out, indent=2))
        return

    if args.input.startswith("@"):
        with open(args.input[1:], encoding="utf-8") as f:
            run_input = json.load(f)
    else:
        run_input = json.loads(args.input)

    # Guard against unbounded (and expensively metered) runs: the input must carry a
    # recognizable result cap unless the user explicitly asked for everything.
    LIMIT_KEYS = ("limit", "maxResults", "resultsLimit", "maxItems", "maxResultsPerPage",
                  "maxCrawledPlacesPerSearch", "maxCrawledPlaces", "maxRequestsPerCrawl",
                  "maxCrawlPages", "maxComments", "maxPosts")
    caps = {k: run_input[k] for k in LIMIT_KEYS if isinstance(run_input.get(k), int)}
    if not args.allow_unlimited:
        if not caps:
            sys.exit("ERROR: no result limit found in the actor input (looked for: "
                     f"{', '.join(LIMIT_KEYS)}).\nSet one (default policy: 50, or ~2.5x the "
                     "lead count the user asked for), or pass --allow-unlimited if the user "
                     "explicitly requested an uncapped run.")
        big = {k: v for k, v in caps.items() if v > 500}
        if big:
            sys.exit(f"ERROR: limit(s) {big} exceed the 500 safety cap. Confirm with the user, "
                     "then re-run with --allow-unlimited.")

    print(f"Starting {actor} …")
    run = api("POST", f"/acts/{actor}/runs", token, body=run_input)["data"]
    run_id = run["id"]
    console_url = f"https://console.apify.com/actors/runs/{run_id}"
    print(f"Run {run_id} → {console_url}")

    start = time.time()
    status = run["status"]
    while status in ("READY", "RUNNING"):
        if time.time() - start > args.max_wait:
            sys.exit(f"ERROR: still {status} after {args.max_wait}s. Check {console_url}")
        time.sleep(15)
        run = api("GET", f"/actor-runs/{run_id}", token)["data"]
        status = run["status"]
        print(f"  status={status} elapsed={int(time.time()-start)}s")

    if status != "SUCCEEDED":
        sys.exit(f"ERROR: run finished {status} ({run.get('statusMessage', '')}). Log: {console_url}/log")

    dataset_id = run["defaultDatasetId"]
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
    print(f"Done: {len(items)} items → {args.output}")
    print(f"Dataset: https://console.apify.com/storage/datasets/{dataset_id}")


if __name__ == "__main__":
    main()
