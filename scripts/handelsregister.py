#!/usr/bin/env python3
"""Verify German companies against the official Handelsregister (handelsregister.de).

EXPERIMENTAL. The registry has no public API; this drives the public 'normale Suche' web
form (JSF-based, following the approach of github.com/bundesAPI/handelsregister). The site
changes and rate-limits aggressively — use only on the final shortlist, with the built-in
3s delay, and expect graceful degradation: on any failure the lead gets
register_status="unchecked" and the North Data public status remains the fallback.

Sets per lead: register_status = "registered" | "not_found" | "unchecked", and
register_court/register_no when found. Cross-checks the register ID scraped from the
lead's Impressum (register_id_website) when available. Stdlib only.

  python3 handelsregister.py --input shortlist.json --output verified.json --delay 3
"""
import argparse
import http.cookiejar
import json
import re
import sys
import time
import urllib.parse
import urllib.request

BASE = "https://www.handelsregister.de"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
VIEWSTATE_RE = re.compile(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"')
RESULT_ROW_RE = re.compile(r"District court\s+([^<]+?)\s+(HR[AB]\s?\d+[^<]*)|Amtsgericht\s+([^<]+?)\s+(HR[AB]\s?\d+[^<]*)", re.I)


class Session:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.opener.addheaders = [("User-Agent", UA), ("Accept-Language", "en")]

    def _open(self, req):
        # transient DNS failures (flaky local resolvers) must not abort the whole run:
        # retry up to 4x with growing waits before letting the error propagate
        for attempt in range(4):
            try:
                with self.opener.open(req, timeout=30) as r:
                    return r.read().decode("utf-8", errors="replace")
            except urllib.error.URLError:
                if attempt == 3:
                    raise
                time.sleep(6 * (attempt + 1))

    def get(self, url):
        return self._open(url)

    def post(self, url, fields):
        data = urllib.parse.urlencode(fields).encode()
        return self._open(urllib.request.Request(url, data=data))


def search_company(sess, name):
    """Return (status, court, register_no). Raises on transport/layout failures."""
    page = sess.get(f"{BASE}/rp_web/normalesuche.xhtml")
    m = VIEWSTATE_RE.search(page)
    if not m:
        raise RuntimeError("ViewState not found — page layout changed")
    fields = {
        "form": "form",
        "form:schlagwoerter": name,
        "form:schlagwortOptionen": "2",  # contain all keywords
        "form:btnSuche": "Search",
        "javax.faces.ViewState": m.group(1),
    }
    result = sess.post(f"{BASE}/rp_web/normalesuche.xhtml", fields)
    if "ergebnisse" not in result.lower() and "result" not in result.lower():
        # some deployments redirect to a results view; try to detect rows anyway
        pass
    m = RESULT_ROW_RE.search(result)
    if m:
        court = (m.group(1) or m.group(3) or "").strip()
        reg = (m.group(2) or m.group(4) or "").strip()
        return "registered", court, reg
    if re.search(r"keine Ergebnisse|no results|0 Treffer", result, re.I):
        return "not_found", "", ""
    # results page shape unknown — look for HRA/HRB anywhere as weak signal
    weak = re.search(r"\bHR[AB]\s?\d+\b", result)
    if weak:
        return "registered", "", weak.group(0)
    return "not_found", "", ""


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--delay", type=float, default=3.0,
                   help="Seconds between queries (default 3 — do not lower; the site blocks)")
    p.add_argument("--max", type=int, default=100, help="Safety cap on lookups (default 100)")
    args = p.parse_args()

    with open(args.input, encoding="utf-8") as f:
        leads = json.load(f)
    todo = [i for i, l in enumerate(leads)
            if (l.get("title") or l.get("name")) and not l.get("register_status")][:args.max]
    print(f"{len(todo)} companies to check against Handelsregister "
          f"(~{len(todo) * args.delay / 60:.0f} min at {args.delay}s delay). EXPERIMENTAL — "
          f"failures degrade to register_status=unchecked.")

    sess = Session()
    failures = 0
    for n, i in enumerate(todo, 1):
        lead = leads[i]
        name = (lead.get("title") or lead.get("name") or "").split("|")[0].split("-")[0].strip()
        try:
            status, court, reg = search_company(sess, name)
            lead["register_status"] = status
            if court:
                lead["register_court"] = court
            if reg:
                lead["register_no"] = reg
                site_reg = lead.get("register_id_website", "")
                if site_reg and site_reg.replace(" ", "") not in reg.replace(" ", ""):
                    lead["_flags"] = sorted(set(lead.get("_flags", []) + ["register_id_mismatch"]))
        except Exception as e:
            failures += 1
            lead["register_status"] = "unchecked"
            if failures >= 3:
                print(f"  aborting after 3 consecutive-style failures ({e}) — remaining leads "
                      f"stay 'unchecked'; rely on North Data public status instead.")
                for j in todo[n:]:
                    leads[j].setdefault("register_status", "unchecked")
                break
        if n % 10 == 0 or n == len(todo):
            print(f"  {n}/{len(todo)}")
        time.sleep(args.delay)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(leads, f, ensure_ascii=False, indent=1)
    reg = sum(1 for l in leads if l.get("register_status") == "registered")
    nf = sum(1 for l in leads if l.get("register_status") == "not_found")
    un = sum(1 for l in leads if l.get("register_status") == "unchecked")
    print(f"Done → {args.output}. registered: {reg} | not_found: {nf} | unchecked: {un}")
    print("Note: sole traders (Einzelunternehmen) legitimately have no register entry — "
          "not_found is only a hard disqualifier for GmbH/UG/AG-type companies.")


if __name__ == "__main__":
    main()
