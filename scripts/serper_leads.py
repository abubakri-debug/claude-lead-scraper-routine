#!/usr/bin/env python3
"""Budget-tier discovery and email finding via Serper.dev (Google Maps + Search).

Serper Maps: 3 credits/query, up to 20 places/query (~$0.15-0.45 per 1,000 leads at $1/1k
credits) — roughly 10x cheaper than full Apify scraping, at the cost of a 20-results/query
ceiling (fan out across cities/districts for coverage). Requires env var SERPER_API_KEY.
Output uses the same field names as the Apify Google Maps actor, so enrich_emails.py,
northdata.py, millionverifier.py, and pipeline.py all consume it unchanged. Stdlib only.

Subcommands:
  discover --search "dentist" --city "Austin, Texas" --city "Round Rock, Texas" \
           --gl us --output raw.json
  emails   --input raw.json --output raw_emails.json --gl us
           (batched "\"domain\" email" snippet search, ~1 credit/lead; auto-picks
            own-domain emails, leaves ambiguous candidates for AI review)
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from env_loader import load_env  # noqa: E402
load_env()

MAPS_URL = "https://google.serper.dev/maps"
SEARCH_URL = "https://google.serper.dev/search"
BATCH = 100  # Serper accepts up to 100 query objects per POST

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
DENY_LOCAL = re.compile(r"^(no-?reply|donotreply|wordpress|mailer|postmaster|webmaster|abuse)@", re.I)
DENY_HOSTS = {"instagram.com", "facebook.com", "linkedin.com", "yelp.com", "zocdoc.com",
              "healthgrades.com", "wellness.com", "vagaro.com", "yellowpages.com", "tiktok.com",
              "x.com", "twitter.com", "youtube.com", "sharecare.com", "apple.com", "google.com",
              "sentry.io", "wixpress.com", "example.com"}


def key():
    k = os.environ.get("SERPER_API_KEY")
    if not k:
        sys.exit("ERROR: SERPER_API_KEY env var not set (free tier: https://serper.dev, 2,500 credits).")
    return k


def post(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"X-API-KEY": key(), "Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 2:
                time.sleep(2 ** (attempt + 1))
                continue
            sys.exit(f"ERROR: Serper {e.code}: {e.read().decode(errors='replace')[:300]}")
        except urllib.error.URLError as e:
            if attempt < 2:
                time.sleep(2 ** (attempt + 1))
                continue
            sys.exit(f"ERROR: network failure calling Serper: {e}")


def domain_of(url):
    if not url or not url.startswith("http"):
        return ""
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return "" if any(host == h or host.endswith("." + h) for h in DENY_HOSTS) else host


def cmd_discover(args):
    queries = [{"q": s, "location": loc, "gl": args.gl, "num": args.num}
               for s in args.search for loc in args.city]
    credits = len(queries) * 3
    print(f"{len(queries)} maps queries ({len(args.search)} terms x {len(args.city)} locations) "
          f"= {credits} credits (~${credits / 1000:.2f})")

    seen, leads = set(), []
    for i in range(0, len(queries), BATCH):
        resp = post(MAPS_URL, queries[i:i + BATCH])
        for entry in (resp if isinstance(resp, list) else [resp]):
            for p in entry.get("places", []):
                cid = str(p.get("cid") or "")
                if not cid or cid in seen:
                    continue
                seen.add(cid)
                site = p.get("website") or ""
                leads.append({
                    "title": p.get("title", ""),
                    "categoryName": p.get("type", ""),
                    "address": p.get("address", ""),
                    "phone": p.get("phoneNumber", ""),
                    "website": site,
                    "totalScore": p.get("rating", ""),
                    "reviewsCount": p.get("ratingCount", ""),
                    "countryCode": args.gl.upper(),
                    "placeId": f"cid:{cid}",
                    "url": f"https://maps.google.com/?cid={cid}",
                    "location": {"lat": p.get("latitude"), "lng": p.get("longitude")},
                    "emails": [],
                    "_source": "serper_maps",
                })
        print(f"  batch {i // BATCH + 1}: {len(leads)} unique places so far")

    # --- geography check: Serper sometimes falls back to matches far outside the requested
    # location (observed: Minneapolis/Vienna results for Saarland queries). Filter if asked,
    # and always report the postal-code spread so contamination is visible.
    postal_re = re.compile(r"\b(\d{4,5})\b")
    if args.postal_prefix:
        before = len(leads)
        keep = []
        for l in leads:
            m = postal_re.search(l.get("address", ""))
            if m and any(m.group(1).startswith(p) for p in args.postal_prefix):
                keep.append(l)
        leads = keep
        print(f"Postal filter {args.postal_prefix}: kept {len(leads)}/{before} "
              f"({before - len(leads)} out-of-region results dropped)")

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(leads, f, ensure_ascii=False, indent=1)
    n = len(leads)
    with_site = sum(1 for l in leads if l["website"])
    print(f"\nDone: {n} places → {args.output} (with website: {with_site})")
    prefixes = {}
    for l in leads:
        m = postal_re.search(l.get("address", ""))
        prefixes[m.group(1)[:2] if m else "??"] = prefixes.get(m.group(1)[:2] if m else "??", 0) + 1
    top = sorted(prefixes.items(), key=lambda x: -x[1])[:8]
    print("  postal-prefix spread: " + ", ".join(f"{p}xx*: {c}" for p, c in top))
    if not args.postal_prefix and len(prefixes) > 3:
        print("  WARNING: wide postal spread — check for out-of-region contamination and "
              "re-run with --postal-prefix (e.g. --postal-prefix 66 for Saarland) if needed.")
    per_q = n / max(len(queries), 1)
    if per_q > args.num * 0.9:
        print(f"  NOTE: averaging {per_q:.0f} results/query — near Serper's {args.num}-result "
              f"ceiling. Coverage is likely truncated: add more sub-locations (districts, "
              f"suburbs, ZIPs) or escalate to the Apify scraper for exhaustive coverage.")


def cmd_filter(args):
    """Re-filter an existing discovery file offline — costs nothing, never re-scrape for this."""
    with open(args.input, encoding="utf-8") as f:
        leads = json.load(f)
    before = len(leads)
    postal_re = re.compile(r"\b(\d{4,5})\b")
    if args.postal_prefix:
        leads = [l for l in leads
                 if (m := postal_re.search(l.get("address", "")))
                 and any(m.group(1).startswith(p) for p in args.postal_prefix)]
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(leads, f, ensure_ascii=False, indent=1)
    print(f"Kept {len(leads)}/{before} → {args.output} (0 credits spent)")


def cmd_emails(args):
    with open(args.input, encoding="utf-8") as f:
        leads = json.load(f)
    todo = [(i, domain_of(l.get("website", ""))) for i, l in enumerate(leads)]
    todo = [(i, d) for i, d in todo if d and not (leads[i].get("emails") or leads[i].get("email"))]
    print(f"{len(leads)} leads; snippet-searching emails for {len(todo)} domains "
          f"(~{len(todo)} credits, ~${len(todo) / 1000:.2f})")

    with_organic = 0
    for b in range(0, len(todo), BATCH):
        chunk = todo[b:b + BATCH]
        resp = post(SEARCH_URL, [{"q": f'"{d}" email', "num": 10, "gl": args.gl} for _, d in chunk])
        resp = resp if isinstance(resp, list) else [resp]
        with_organic += sum(1 for e in resp if e.get("organic"))
        for (idx, dom), entry in zip(chunk, resp):
            candidates = {}
            for org in entry.get("organic", []):
                text = f"{org.get('title', '')} {org.get('snippet', '')}"
                src = urlparse(org.get("link", "")).netloc.lower().removeprefix("www.")
                for e in EMAIL_RE.findall(text):
                    e = e.lower().strip(".")
                    if DENY_LOCAL.match(e) or any(e.endswith("@" + h) for h in DENY_HOSTS):
                        continue
                    candidates.setdefault(e, src)
            own = [e for e in candidates if e.split("@")[-1] == dom or e.split("@")[-1].endswith("." + dom)]
            lead = leads[idx]
            if own:
                lead["emails"] = own[:3]
                lead["email_confidence"] = "high"
            elif candidates:
                # off-domain candidates: leave for AI judgment, don't auto-assign freemail/junk
                lead["email_candidates"] = [{"email": e, "found_on": s} for e, s in list(candidates.items())[:5]]
                lead["email_confidence"] = "low"
            lead["_email_searched"] = True
        print(f"  {min(b + BATCH, len(todo))}/{len(todo)}")

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(leads, f, ensure_ascii=False, indent=1)
    auto = sum(1 for i, _ in todo if leads[i].get("emails"))
    review = sum(1 for i, _ in todo if leads[i].get("email_candidates"))
    print(f"\nDone → {args.output}. Auto-assigned own-domain emails: {auto}; "
          f"needing AI candidate review (email_candidates field): {review}")
    print(f"  diagnostics: {with_organic}/{len(todo)} queries returned organic results "
          f"(low organic = small local sites simply aren't indexed with emails; "
          f"the website crawl fallback usually recovers these)")
    if review:
        print("  Review the email_candidates entries: accept an off-domain/freemail address only "
              "if it clearly belongs to this business (repeated on its own site, owner's name); "
              "move accepted ones into the lead's 'emails' list.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("discover", help="Google Maps discovery via Serper (3 credits/query, 20 places max)")
    sp.add_argument("--search", action="append", required=True, help="Search term; repeatable")
    sp.add_argument("--city", action="append", required=True,
                    help='Location, repeatable, e.g. "Hamburg, Germany" or "Austin, Texas"')
    sp.add_argument("--gl", default="us", help="Country code (default us)")
    sp.add_argument("--num", type=int, default=20, help="Results per query, max 20 (default 20)")
    sp.add_argument("--postal-prefix", action="append",
                    help="Keep only places whose postal code starts with this prefix; repeatable "
                         "(e.g. --postal-prefix 66 for Saarland). Guards against Serper's "
                         "out-of-region fallback results.")
    sp.add_argument("--output", required=True)
    sp.set_defaults(func=cmd_discover)

    sp = sub.add_parser("filter", help="Re-filter an existing discovery JSON offline (0 credits)")
    sp.add_argument("--input", required=True)
    sp.add_argument("--output", required=True)
    sp.add_argument("--postal-prefix", action="append", required=True,
                    help="Keep only postal codes starting with this prefix; repeatable")
    sp.set_defaults(func=cmd_filter)

    sp = sub.add_parser("emails", help="Find emails via Serper search snippets (~1 credit/lead)")
    sp.add_argument("--input", required=True)
    sp.add_argument("--output", required=True)
    sp.add_argument("--gl", default="us")
    sp.set_defaults(func=cmd_emails)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
