#!/usr/bin/env python3
"""North Data API client: lookup, power search, and lead-list enrichment.

Requires env var NORTHDATA_API_KEY (form XXXX-XXXX; from northdata.com).
Coverage is strongest for DE/AT/CH; see https://www.northdata.com/_coverage
Stdlib only.

Subcommands:
  lookup  --name "1000mikes AG" --address "Hamburg" [--financials --representatives]
  power   --keywords "webdesign" --address "Hamburg" [--status active] [--max 100]
  enrich  --input leads.json --output out.json [--financials --representatives]
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from env_loader import load_env  # noqa: E402
load_env()

BASE = "https://www.northdata.com/_api"

DETAIL_FLAGS = ["history", "financials", "sheets", "events", "relations",
                "owners", "ownerships", "representatives", "extras"]


def key():
    k = os.environ.get("NORTHDATA_API_KEY")
    if not k:
        sys.exit("ERROR: NORTHDATA_API_KEY env var not set. North Data enrichment unavailable "
                 "(API keys: support@northdata.com).")
    return k


def get(path, params, ok404=False):
    qs = urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "", False)})
    url = f"{BASE}{path}?{qs}"
    req = urllib.request.Request(url, headers={"X-Api-Key": key(), "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 404 and ok404:
                return None
            if e.code == 503 and attempt < 2:
                time.sleep(3 * (attempt + 1))
                continue
            sys.exit(f"ERROR: North Data API {e.code} on {path}: {e.read().decode(errors='replace')[:300]}")
        except urllib.error.URLError as e:
            if attempt < 2:
                time.sleep(3)
                continue
            sys.exit(f"ERROR: network failure calling North Data: {e}")


def add_detail_params(params, args):
    for flag in DETAIL_FLAGS:
        if getattr(args, flag, False):
            params[flag] = "true"


def cmd_lookup(args):
    params = {"name": args.name, "address": args.address, "language": args.language}
    add_detail_params(params, args)
    result = get("/company/v1/company", params, ok404=True)
    print(json.dumps(result, ensure_ascii=False, indent=2) if result else "Not found (404).")


def cmd_power(args):
    params = {"keywords": args.keywords, "address": args.address, "language": args.language}
    if args.status:
        params["status"] = args.status
    if args.max_distance_km:
        params["maxDistanceKm"] = args.max_distance_km
    if args.legal_form:
        params["legalForm"] = args.legal_form
    add_detail_params(params, args)
    results, pos = [], None
    while True:
        if pos:
            params["pos"] = pos
        resp = get("/search/v1/power", params)
        results.extend(resp.get("results", []) or resp.get("companies", []) or [])
        pos = resp.get("nextPos")
        print(f"  fetched {len(results)} …", file=sys.stderr)
        if not pos or len(results) >= args.max:
            break
    results = results[:args.max]
    out = json.dumps(results, ensure_ascii=False, indent=1)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"{len(results)} companies → {args.output}")
    else:
        print(out)


LEGAL_FORM_RE = re.compile(
    r"\b(GmbH & Co\.? KG|gGmbH|GmbH|UG \(haftungsbeschränkt\)|UG|AG & Co\.? KG|AG|KG|OHG|e\.?K\.?|"
    r"e\.?V\.?|SE|Ltd\.?|PartG(?:mbB)?|eG)(?!\w)")
REGISTER_RE = re.compile(r"\b(HR[AB]\s?\d+(?:\s?[A-Z]{1,3})?|VR\s?\d+|GnR\s?\d+|PR\s?\d+)\b")
STATUS_RE = re.compile(r"\b(liquidation|aufgelöst|gelöscht|terminated|insolvenz)\b", re.I)


def cmd_free(args):
    """Registry basics from North Data's PUBLIC Google-indexed profiles via Serper snippets.

    No North Data API key needed — costs ~1 Serper credit/company. Gets legal name/form,
    register ID, status hints, and the public profile URL. Financials/representatives are
    paywalled and need the paid API ('enrich' subcommand).
    """
    serper_key = os.environ.get("SERPER_API_KEY")
    if not serper_key:
        sys.exit("ERROR: the free registry tier searches via Serper — SERPER_API_KEY required.")
    with open(args.input, encoding="utf-8") as f:
        leads = json.load(f)
    todo = [i for i, l in enumerate(leads)
            if (l.get("title") or l.get("name")) and not l.get("northdata")]
    print(f"{len(todo)} companies via public-snippet lookup (~{len(todo)} Serper credits, "
          f"~${len(todo) / 1000:.2f})")

    def serper(queries):
        req = urllib.request.Request("https://google.serper.dev/search",
                                     data=json.dumps(queries).encode(),
                                     headers={"X-API-KEY": serper_key,
                                              "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=90) as r:
            out = json.loads(r.read().decode())
            return out if isinstance(out, list) else [out]

    matched = 0
    for b in range(0, len(todo), 100):
        chunk = todo[b:b + 100]
        queries = []
        for i in chunk:
            name = leads[i].get("title") or leads[i].get("name") or ""
            city = leads[i].get("city") or ""
            queries.append({"q": f'site:northdata.com "{name.split("|")[0].strip()}" {city}'.strip(),
                            "num": 3, "gl": args.gl})
        for i, entry in zip(chunk, serper(queries)):
            lead = leads[i]
            organic = entry.get("organic") or []
            hit = next((o for o in organic if "northdata.com" in o.get("link", "")), None)
            if not hit:
                lead["northdata_match"] = "none_public"
                continue
            text = f"{hit.get('title', '')} {hit.get('snippet', '')}"
            reg = REGISTER_RE.search(text)
            form = LEGAL_FORM_RE.search(text)
            status = STATUS_RE.search(text)
            lead["northdata_match"] = "public_snippet"
            lead["northdata"] = {
                "legalName": hit.get("title", "").split(",")[0].strip(),
                "legalForm": form.group(1) if form else "",
                "registerId": reg.group(1) if reg else "",
                # only report status when a negative marker is present; never invent "active"
                "status": "check:" + status.group(1).lower() if status else "",
                "profileUrl": hit.get("link", ""),
                "source": "public snippet — basics only; financials/directors need the paid API",
            }
            matched += 1
        print(f"  {min(b + 100, len(todo))}/{len(todo)} (matched {matched})", file=sys.stderr)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(leads, f, ensure_ascii=False, indent=1)
    print(f"Done → {args.output}. Public-profile matches: {matched}/{len(todo)}. "
          f"Snippet data is registry basics only and may lag the live register.")


def cmd_enrich(args):
    with open(args.input, encoding="utf-8") as f:
        leads = json.load(f)
    matched = 0
    for i, lead in enumerate(leads):
        name = lead.get("title") or lead.get("name") or ""
        city = lead.get("city") or ""
        if not name:
            lead["northdata_match"] = "skipped_no_name"
            continue
        params = {"name": name, "address": city or lead.get("address", ""), "language": args.language,
                  "fuzzy": "true"}
        add_detail_params(params, args)
        c = get("/company/v1/company", params, ok404=True)
        if not c:
            lead["northdata_match"] = "none"
        else:
            matched += 1
            lead["northdata_match"] = "found"
            lead["northdata"] = {
                "id": c.get("id"),
                "legalName": (c.get("name") or {}).get("name"),
                "legalForm": (c.get("name") or {}).get("legalForm"),
                "status": c.get("status"),
                "registerId": (c.get("register") or {}).get("id"),
                "registerCity": (c.get("register") or {}).get("city"),
            }
            for k in ("financials", "representatives", "events", "extras"):
                if k in c:
                    lead["northdata"][k] = c[k]
        if (i + 1) % 10 == 0:
            print(f"  {i + 1}/{len(leads)} (matched {matched})", file=sys.stderr)
        time.sleep(args.delay)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(leads, f, ensure_ascii=False, indent=1)
    print(f"Done → {args.output}. Matched {matched}/{len(leads)} leads in North Data.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--language", default="en")
    sub = p.add_subparsers(dest="cmd", required=True)

    def detail_args(sp):
        for flag in DETAIL_FLAGS:
            sp.add_argument(f"--{flag}", action="store_true")

    sp = sub.add_parser("lookup", help="Look up one company by name + address")
    sp.add_argument("--name", required=True)
    sp.add_argument("--address", default="")
    detail_args(sp)
    sp.set_defaults(func=cmd_lookup)

    sp = sub.add_parser("power", help="Power search for companies by criteria")
    sp.add_argument("--keywords", default="")
    sp.add_argument("--address", default="")
    sp.add_argument("--status", help="active|terminated|liquidation (pipe-separated for multiple)")
    sp.add_argument("--legal-form", help="e.g. GmbH|AG")
    sp.add_argument("--max-distance-km", type=int)
    sp.add_argument("--max", type=int, default=100)
    sp.add_argument("--output")
    detail_args(sp)
    sp.set_defaults(func=cmd_power)

    sp = sub.add_parser("free", help="FREE registry basics from public Google-indexed North Data "
                                     "profiles (needs SERPER_API_KEY, not a North Data key)")
    sp.add_argument("--input", required=True)
    sp.add_argument("--output", required=True)
    sp.add_argument("--gl", default="de")
    sp.set_defaults(func=cmd_free)

    sp = sub.add_parser("enrich", help="Enrich a leads JSON file with registry data (paid ND API)")
    sp.add_argument("--input", required=True)
    sp.add_argument("--output", required=True)
    sp.add_argument("--delay", type=float, default=0.3, help="Seconds between API calls (default 0.3)")
    detail_args(sp)
    sp.set_defaults(func=cmd_enrich)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
