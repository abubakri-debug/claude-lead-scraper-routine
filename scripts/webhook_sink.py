#!/usr/bin/env python3
"""POST each final lead to a webhook (e.g. an n8n workflow that appends to Google Sheets).

Replaces the direct-to-Sheets path when a service account isn't available. Reads the pipeline's
output CSV and fires one POST per lead (n8n receives one item per call), with a run label/date
attached so the receiving workflow can group and dedupe. Stdlib only.

  python3 webhook_sink.py --csv output/leads.csv --run-label "marketing agency Berlin"

Webhook URL resolution (first found wins):
  --url flag  >  $LEAD_WEBHOOK_URL env var  >  built-in default below.
"""
import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date

DEFAULT_URL = "https://jkdxs.app.n8n.cloud/webhook/claude-lead-scraper"


def post(url, payload, tries=4):
    data = json.dumps(payload).encode()
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, data=data, method="POST",
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return 200 <= r.status < 300, r.status
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            return False, e.code
        except urllib.error.URLError:
            if attempt < tries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            return False, "network"
    return False, "exhausted"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv", required=True, help="Pipeline output CSV to send")
    p.add_argument("--url", default=os.environ.get("LEAD_WEBHOOK_URL", DEFAULT_URL))
    p.add_argument("--run-label", default="", help="Short label for this run (query/region)")
    p.add_argument("--delay", type=float, default=0.2, help="Seconds between POSTs (default 0.2)")
    p.add_argument("--batch", action="store_true",
                   help="Send all leads in ONE POST as a JSON array instead of one-per-lead")
    args = p.parse_args()

    with open(args.csv, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        sys.exit("CSV has no data rows — nothing to send.")

    stamp = {"run_label": args.run_label or os.path.basename(args.csv),
             "run_date": date.today().isoformat()}
    print(f"Sending {len(rows)} leads to {args.url}"
          f"{' (single batch)' if args.batch else ' (one POST per lead)'} …")

    if args.batch:
        ok, status = post(args.url, {**stamp, "leads": rows})
        print(f"Batch POST → {'OK' if ok else 'FAILED'} (status {status}) for {len(rows)} leads")
        sys.exit(0 if ok else 1)

    sent = failed = 0
    for i, row in enumerate(rows, 1):
        ok, status = post(args.url, {**stamp, **row})
        if ok:
            sent += 1
        else:
            failed += 1
            print(f"  lead {i} ({row.get('name', '?')}) failed: status {status}")
        if i % 20 == 0 or i == len(rows):
            print(f"  {i}/{len(rows)} (sent {sent}, failed {failed})")
        time.sleep(args.delay)

    print(f"Done: {sent} leads delivered to the webhook, {failed} failed.")
    if failed:
        print("  Some POSTs failed — check the n8n execution log and the webhook URL. "
              "Re-running is safe if the n8n workflow dedupes by place_id.")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
