#!/usr/bin/env python3
"""Cloud-routine entrypoint: parse form params, run the person-first pipeline, append to Sheet.

Invoked by the Claude routine after it parses count/location/industry from the Airtable
webhook text. Orchestrates the same scripts the local skill uses, headless, with the volume
cap enforced. Reads keys from environment variables (cloud secrets).

  python3 routine_run.py --count 50 --location "Berlin, Germany" --industry "marketing agency"

Env vars expected (cloud-environment secrets):
  APIFY_TOKEN, SERPER_API_KEY, MILLIONVERIFIER_API_KEY (optional),
  GOOGLE_SERVICE_ACCOUNT_JSON (the key file *contents*), GSHEET_ID, GSHEET_GID

ICP scoring is a judgment step the *routine model* performs on work/icp_input.json, not this
script. This script stops after producing the enriched, founder-verified file and prints its
path; the routine then scores, writes icp_score/icp_reason back, and runs export + gsheets.
See ROUTINE_PROMPT.md for the exact sequence.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def sh(cmd):
    print("+ " + " ".join(cmd), flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
    return r.returncode == 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--count", type=int, required=True, help="Lead count the requester asked for")
    p.add_argument("--location", required=True)
    p.add_argument("--industry", required=True)
    p.add_argument("--gl", default="de", help="Serper country code (default de)")
    p.add_argument("--workdir", default="work")
    args = p.parse_args()

    os.makedirs(args.workdir, exist_ok=True)

    # Volume cap: 2.5x the request, hard-capped at 150 unless the requester named a bigger number.
    fetch = min(max(int(args.count * 2.5), args.count), 150)
    print(f"Request: {args.count} {args.industry} in {args.location} → fetching {fetch} raw "
          f"(2.5x buffer, capped 150).", flush=True)

    if not os.environ.get("APIFY_TOKEN") and not os.environ.get("SERPER_API_KEY"):
        sys.exit("Missing APIFY_TOKEN and SERPER_API_KEY — add them at claude.ai/code/environments.")

    # Materialize the Google service-account JSON secret to a file for gsheets.py
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if sa_json:
        sa_path = os.path.join(args.workdir, "sa.json")
        with open(sa_path, "w") as f:
            f.write(sa_json)
        os.chmod(sa_path, 0o600)
        os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"] = os.path.abspath(sa_path)

    raw = os.path.join(args.workdir, "raw.json")
    ok = sh(["python3", f"{HERE}/serper_leads.py", "discover",
             "--search", args.industry, "--city", args.location, "--gl", args.gl,
             "--num", "20", "--output", raw])
    if not ok:
        sys.exit("Discovery failed — see stderr above.")

    e1 = os.path.join(args.workdir, "e1.json")
    enr = os.path.join(args.workdir, "enriched.json")
    nd = os.path.join(args.workdir, "nd.json")
    fnd = os.path.join(args.workdir, "founders.json")
    sh(["python3", f"{HERE}/serper_leads.py", "emails", "--input", raw, "--output", e1, "--gl", args.gl])
    sh(["python3", f"{HERE}/enrich_emails.py", "--input", e1, "--output", enr])
    sh(["python3", f"{HERE}/northdata.py", "free", "--input", enr, "--output", nd, "--gl", args.gl])
    sh(["python3", f"{HERE}/founders.py", "--input", nd, "--output", fnd])

    icp_input = os.path.join(args.workdir, "icp_input.json")
    os.replace(fnd, icp_input)
    print(json.dumps({"stage": "ready_for_icp", "icp_input": icp_input,
                      "count_requested": args.count, "fetched": fetch}), flush=True)
    print("\nNEXT: score each lead in", icp_input, "(real per-lead ICP judgment, not a category "
          "script), write icp_score + icp_reason back, then pipeline.py with --require-founder "
          "--strict-quality --icp-threshold 60, then millionverifier.py on the shortlist, then "
          "gsheets.py append. See ROUTINE_PROMPT.md.")


if __name__ == "__main__":
    main()
