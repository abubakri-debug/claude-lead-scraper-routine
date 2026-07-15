#!/usr/bin/env python3
"""Verify lead emails via the MillionVerifier bulk API (~$0.0007/email).

Requires env var MILLIONVERIFIER_API_KEY. Uploads all unique emails from a leads JSON,
polls (capped — the API often hangs at 95-99%), downloads results, and writes the leads
back with an email_status field: valid | risky | unknown | invalid | unverified.
Stdlib only.

  python3 millionverifier.py --input leads.json --output leads_verified.json
  python3 millionverifier.py --input leads.json --output out.json --file-id 1234  # resume poll
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from env_loader import load_env  # noqa: E402
load_env()

# NOTE: bulk API host is bulkapi.millionverifier.com (NOT api.); file_id & key are QUERY params.
BASE = "https://bulkapi.millionverifier.com/bulkapi/v2"
# Cloudflare fronts this API and blocks Python's default urllib UA with error 1010 —
# a browser-like UA is required.
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

STATUS_MAP = {"ok": "valid", "catch_all": "risky", "unknown": "unknown",
              "disposable": "invalid", "invalid": "invalid", "error": "invalid"}


def key():
    k = os.environ.get("MILLIONVERIFIER_API_KEY")
    if not k:
        sys.exit("ERROR: MILLIONVERIFIER_API_KEY env var not set "
                 "(https://app.millionverifier.com, ~$0.0007/email).")
    return k


def http(url, data=None, headers=None):
    h = {"User-Agent": UA, "Accept": "*/*"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:400]
            if e.code in (403, 429, 500, 502, 503) and attempt < 2:
                time.sleep(8 * (attempt + 1))
                continue
            hint = ("(400 on download usually means missing filter=all; upload failures are "
                    "usually billing/credits — check the MV dashboard.)")
            if e.code == 403 or "1010" in body:
                hint = ("(Cloudflare block, error 1010: the API rejected this client signature. "
                        "Retried with a browser UA already — if it persists, wait a few minutes, "
                        "try from the user's normal network, or verify via the MV dashboard "
                        "upload instead. Don't burn more retries.)")
            sys.exit(f"ERROR: MillionVerifier {e.code}: {body}\n{hint}")
        except urllib.error.URLError as e:
            if attempt < 2:
                time.sleep(5)
                continue
            sys.exit(f"ERROR: network failure calling MillionVerifier: {e}")


def upload(emails, name):
    boundary = uuid.uuid4().hex
    file_body = "\n".join(emails).encode()
    parts = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file_contents\"; "
        f"filename=\"{name}.txt\"\r\nContent-Type: text/plain\r\n\r\n".encode() + file_body +
        f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"file_name\"\r\n\r\n{name}"
        f"\r\n--{boundary}--\r\n".encode()
    )
    resp = http(f"{BASE}/upload?key={key()}", data=parts,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    data = json.loads(resp.decode())
    fid = data.get("file_id")
    if not fid:
        sys.exit(f"ERROR: upload gave no file_id: {data}")
    return fid


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--file-id", help="Resume: skip upload, poll/download this existing file id")
    p.add_argument("--max-wait", type=int, default=300,
                   help="Poll cap in seconds (default 300 — MV often stalls at 95-99%%; "
                        "partial results are downloaded and the rest marked 'unverified')")
    args = p.parse_args()

    with open(args.input, encoding="utf-8") as f:
        leads = json.load(f)

    emails = sorted({e.lower() for l in leads
                     for e in (l.get("emails") or ([l["email"]] if l.get("email") else []))
                     if e and "@" in e})
    if not emails:
        sys.exit("No emails found in input — nothing to verify.")
    print(f"{len(emails)} unique emails (~${len(emails) * 0.0007:.2f})")

    fid = args.file_id or upload(emails, "lead-scraper")
    print(f"file_id={fid} (save this to resume if interrupted)")

    start = time.time()
    while True:
        info = json.loads(http(f"{BASE}/fileinfo?file_id={fid}&key={key()}").decode())
        status = info.get("status")
        # 'total' isn't always present/reliable in fileinfo — fall back to what we uploaded
        total = max(info.get("total") or len(emails), 1)
        verified = info.get("verified", 0) or 0
        print(f"  status={status} verified={min(100, 100 * verified // total)}%")
        if status == "finished":
            break
        if time.time() - start > args.max_wait:
            print(f"  Poll cap hit ({args.max_wait}s) — downloading partial results. "
                  f"Re-run later with --file-id {fid} to finish.")
            break
        time.sleep(20)

    csv_bytes = http(f"{BASE}/download?file_id={fid}&key={key()}&filter=all")  # filter=all required
    results = {}
    for line in csv_bytes.decode(errors="replace").splitlines()[1:]:
        cols = [c.strip().strip('"') for c in line.split(",")]
        if len(cols) >= 3 and "@" in cols[0]:
            results[cols[0].lower()] = STATUS_MAP.get(cols[2].lower(), "unknown")

    for lead in leads:
        lead_emails = lead.get("emails") or ([lead["email"]] if lead.get("email") else [])
        statuses = [(e, results.get(e.lower(), "unverified")) for e in lead_emails]
        if not statuses:
            continue
        # keep the best-verified email first
        rank = {"valid": 0, "risky": 1, "unknown": 2, "unverified": 3, "invalid": 4}
        statuses.sort(key=lambda x: rank[x[1]])
        lead["emails"] = [e for e, _ in statuses]
        lead["email_status"] = statuses[0][1]

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(leads, f, ensure_ascii=False, indent=1)

    counts = {}
    for s in results.values():
        counts[s] = counts.get(s, 0) + 1
    missing = len(emails) - len(results)
    if missing:
        counts["unverified"] = counts.get("unverified", 0) + missing
    print(f"Done → {args.output}")
    print("  " + " | ".join(f"{k}: {v}" for k, v in sorted(counts.items())))


if __name__ == "__main__":
    main()
