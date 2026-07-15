#!/usr/bin/env python3
"""Fallback email/social enrichment: crawl each lead's website for contact details.

Reads a JSON array of leads (Apify Google Maps output format), visits the homepage plus
common contact pages (/contact, /kontakt, /impressum, /about, ...) of every lead that has a
website but no email yet, extracts emails (including simple [at]/(at) obfuscation) and social
links, and writes the enriched array. Stdlib only.

  python3 enrich_emails.py --input raw.json --output enriched.json --workers 8
"""
import argparse
import concurrent.futures
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

CONTACT_PATHS = ["", "/contact", "/contact-us", "/kontakt", "/impressum", "/about", "/about-us",
                 "/legal", "/imprint", "/team"]
UA = "Mozilla/5.0 (compatible; lead-enrichment/1.0)"
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
OBFUSCATED_RE = re.compile(
    r"([a-zA-Z0-9._%+\-]+)\s*[\[\(]\s*(?:at|@)\s*[\]\)]\s*([a-zA-Z0-9.\-]+)\s*[\[\(]\s*(?:dot|\.)\s*[\]\)]\s*([a-zA-Z]{2,})",
    re.IGNORECASE)
SOCIAL_RE = re.compile(
    r"https?://(?:www\.)?(linkedin\.com/[A-Za-z0-9_\-/.%]+|facebook\.com/[A-Za-z0-9_\-/.%]+|"
    r"instagram\.com/[A-Za-z0-9_\-/.%]+|x\.com/[A-Za-z0-9_\-/.%]+|twitter\.com/[A-Za-z0-9_\-/.%]+)")
JUNK_EMAIL = re.compile(r"\.(png|jpg|jpeg|gif|svg|webp|css|js)$|@(example|sentry|wixpress|domain)\.", re.IGNORECASE)


def fetch(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if "text/html" not in r.headers.get("Content-Type", "text/html"):
                return ""
            return r.read(600_000).decode("utf-8", errors="replace")
    except Exception:
        return ""


def extract(html):
    emails = set(m.group(0).lower() for m in EMAIL_RE.finditer(html))
    emails |= {f"{a}@{b}.{c}".lower() for a, b, c in OBFUSCATED_RE.findall(html)}
    emails = {e.strip(".") for e in emails if not JUNK_EMAIL.search(e) and len(e) < 80}
    socials = sorted({("https://" + m.group(1)) for m in SOCIAL_RE.finditer(html)})
    return emails, socials


def enrich_one(lead):
    site = (lead.get("website") or "").strip()
    if not site:
        return lead
    if not site.startswith("http"):
        site = "https://" + site
    parsed = urllib.parse.urlparse(site)
    base = f"{parsed.scheme}://{parsed.netloc}"
    emails, socials = set(), set()
    for path in CONTACT_PATHS:
        html = fetch(base + path if path else site)
        if not html:
            continue
        e, s = extract(html)
        emails |= e
        socials.update(s)
        if emails and path != "":
            break  # good enough once a contact page yielded emails
    domain = parsed.netloc.lower().removeprefix("www.")
    # prefer emails on the lead's own domain
    own = sorted(e for e in emails if e.endswith("@" + domain) or domain in e.split("@")[-1])
    lead.setdefault("emails", [])
    merged = list(dict.fromkeys((lead.get("emails") or []) + own + sorted(emails - set(own))))
    lead["emails"] = merged[:5]
    if socials:
        lead["socialLinks"] = sorted(set(lead.get("socialLinks") or []) | socials)[:10]
    lead["_email_enriched"] = True
    return lead


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--force", action="store_true", help="Also crawl leads that already have an email")
    args = p.parse_args()

    with open(args.input, encoding="utf-8") as f:
        leads = json.load(f)

    todo = [i for i, l in enumerate(leads)
            if l.get("website") and (args.force or not (l.get("emails") or l.get("email")))]
    print(f"{len(leads)} leads; crawling {len(todo)} websites for emails …")

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(enrich_one, leads[i]): i for i in todo}
        done = 0
        for fut in concurrent.futures.as_completed(futures):
            leads[futures[fut]] = fut.result()
            done += 1
            if done % 10 == 0 or done == len(todo):
                print(f"  {done}/{len(todo)}")

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(leads, f, ensure_ascii=False, indent=1)

    found = sum(1 for i in todo if leads[i].get("emails"))
    print(f"Done → {args.output}. Emails found for {found}/{len(todo)} crawled leads.")


if __name__ == "__main__":
    main()
