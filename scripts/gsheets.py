#!/usr/bin/env python3
"""Append pipeline results to a Google Sheet — the master lead list grows with every run.

Auth is a Google service account (one-time setup, then fully automatic):
  1. console.cloud.google.com → create/select project → enable "Google Sheets API"
  2. IAM & Admin → Service Accounts → create → Keys → add JSON key → download
  3. Share the target spreadsheet with the service account's client_email (Editor)
  4. Save the key path + sheet once:
       python3 env_loader.py GOOGLE_SERVICE_ACCOUNT_FILE /path/to/key.json
       python3 env_loader.py GSHEET_ID <spreadsheet id from the URL>
       python3 env_loader.py GSHEET_GID <tab gid from the URL, e.g. 1347092156>

Requires: pip install google-auth  (only non-stdlib dependency; used for JWT signing)

  python3 gsheets.py append --csv output/leads.csv --run-label "web agencies saarland"

Behavior: if the tab is empty, writes the header row first (plus run_date/run_label columns);
every run appends below existing data. Dedupes against place_ids already in the sheet.
"""
import argparse
import csv
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from env_loader import load_env  # noqa: E402
load_env()

API = "https://sheets.googleapis.com/v4/spreadsheets"


def token():
    sa_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
    if not sa_file or not os.path.exists(sa_file):
        sys.exit("ERROR: GOOGLE_SERVICE_ACCOUNT_FILE not set or file missing.\n"
                 "One-time setup: enable the Google Sheets API in console.cloud.google.com, "
                 "create a service account + JSON key, share the spreadsheet with the service "
                 "account's client_email, then:\n"
                 "  python3 scripts/env_loader.py GOOGLE_SERVICE_ACCOUNT_FILE /path/to/key.json")
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
    except ImportError:
        sys.exit("ERROR: google-auth not installed. Run: pip install google-auth")
    creds = service_account.Credentials.from_service_account_file(
        sa_file, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    creds.refresh(Request())
    return creds.token


def call(method, url, tok, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 method=method,
                                 headers={"Authorization": f"Bearer {tok}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode(errors="replace")[:400]
        hint = ""
        if e.code == 403:
            hint = ("\n(403 usually means the spreadsheet isn't shared with the service "
                    "account's client_email — open the sheet, Share, add that email as Editor.)")
        sys.exit(f"ERROR: Sheets API {e.code}: {body_txt}{hint}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("append", help="Append a results CSV to the master sheet")
    sp.add_argument("--csv", required=True, help="Pipeline output CSV to append")
    sp.add_argument("--sheet-id", default=os.environ.get("GSHEET_ID", ""),
                    help="Spreadsheet ID (default: saved GSHEET_ID)")
    sp.add_argument("--gid", default=os.environ.get("GSHEET_GID", "0"),
                    help="Worksheet gid from the URL (default: saved GSHEET_GID or 0)")
    sp.add_argument("--run-label", default="", help="Short label for this run (query/region)")
    args = p.parse_args()

    if not args.sheet_id:
        sys.exit("ERROR: no sheet ID. Save it once: python3 scripts/env_loader.py GSHEET_ID <id>")

    with open(args.csv, encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    if len(rows) < 2:
        sys.exit("CSV has no data rows — nothing to append.")
    header, data = rows[0], rows[1:]

    tok = token()

    # resolve gid -> tab title (values API addresses tabs by title)
    meta = call("GET", f"{API}/{args.sheet_id}?fields=sheets.properties", tok)
    title = None
    for s in meta.get("sheets", []):
        props = s["properties"]
        if str(props.get("sheetId")) == str(args.gid):
            title = props["title"]
            break
    if title is None:
        titles = [s["properties"]["title"] for s in meta.get("sheets", [])]
        sys.exit(f"ERROR: no tab with gid={args.gid}. Available tabs: {titles}")
    rng = urllib.parse.quote(f"'{title}'")

    # existing content: header present? which place_ids already there?
    existing = call("GET", f"{API}/{args.sheet_id}/values/{rng}?majorDimension=ROWS", tok)
    evalues = existing.get("values", [])
    from datetime import date
    run_cols = ["run_date", "run_label"]
    out_rows = []
    if not evalues:
        out_rows.append(header + run_cols)
        seen_pids = set()
    else:
        sheet_header = evalues[0]
        if sheet_header[:len(header)] != header:
            print("NOTE: existing sheet header differs from this CSV's columns — appending in "
                  "this CSV's column order anyway; verify alignment in the sheet.")
        try:
            pid_idx = sheet_header.index("place_id")
            seen_pids = {r[pid_idx] for r in evalues[1:] if len(r) > pid_idx and r[pid_idx]}
        except ValueError:
            seen_pids = set()

    try:
        csv_pid_idx = header.index("place_id")
    except ValueError:
        csv_pid_idx = None
    stamp = [date.today().isoformat(), args.run_label or os.path.basename(args.csv)]
    skipped = 0
    for r in data:
        pid = r[csv_pid_idx] if csv_pid_idx is not None and len(r) > csv_pid_idx else ""
        if pid and pid in seen_pids:
            skipped += 1
            continue
        out_rows.append(r + stamp)

    n_new = len(out_rows) - (1 if not evalues else 0)
    if n_new <= 0:
        print(f"Nothing new to append ({skipped} leads already in the sheet).")
        return
    call("POST",
         f"{API}/{args.sheet_id}/values/{rng}:append?valueInputOption=USER_ENTERED"
         f"&insertDataOption=INSERT_ROWS", tok, body={"values": out_rows})
    print(f"Appended {n_new} leads to '{title}' "
          f"({skipped} duplicates already in sheet skipped).")
    print(f"https://docs.google.com/spreadsheets/d/{args.sheet_id}/edit#gid={args.gid}")


if __name__ == "__main__":
    main()
