#!/usr/bin/env python3
"""Identify the founder/owner of each lead from its website, and grade website quality.

German Impressum pages legally must name the Geschäftsführer (managing director) — for
owner-led small businesses that IS the founder, making this the most reliable free source.
Also checks about/team pages, extracts the register ID for cross-verification, captures a
site-text excerpt for ICP scoring, and flags placeholder/parked/unfinished websites.

Adds per lead: founder_name, founder_role, founder_source, founder_linkedin (if a personal
/in/ link is found), register_id_website, _site_excerpt; flags placeholder_website.
Also merges founders from North Data `representatives` (paid API) when present. Stdlib only.

  python3 founders.py --input leads.json --output leads_founders.json --workers 8
"""
import argparse
import concurrent.futures
import json
import re
import sys
import urllib.parse
import urllib.request

PAGES = ["/impressum", "", "/imprint", "/ueber-uns", "/uber-uns", "/about", "/about-us",
         "/team", "/kontakt", "/legal-notice"]
UA = "Mozilla/5.0 (compatible; lead-enrichment/1.0)"

# (?![A-ZÄÖÜ]) prevents partial matches inside legal forms: 'GmbH' must not yield 'Gmb'
_TOKEN = r"[A-ZÄÖÜ][a-zäöüß']+(?:-[A-ZÄÖÜa-zäöüß][a-zäöüß']*)*(?![A-ZÄÖÜa-zäöüß])"
NAME = rf"((?:{_TOKEN}\.?\s){{1,3}}{_TOKEN})"

# Common first names (German + international) used to validate business-name founder guesses.
# A guess whose first token is NOT in this list stays a candidate, never a confirmed founder.
FIRST_NAMES = frozenset("""
alexander andreas anja anna anne annette antje axel barbara bastian beate benjamin bernd bettina
birgit bjoern björn brigitte carsten carola carolin christa christian christiane christina
christoph claudia cornelia dagmar daniel daniela david dennis diana dieter dirk dominik doris
dorothea eva fabian felix florian frank franziska friedrich gabi gabriele georg gerd gerhard
gisela grit gudrun guido gunter günter hannah hanna hans harald heike heiko heinz helga helmut
henning herbert hermann holger horst ines inga ingo ingrid iris isabel isabelle jan jana janina
jens jessica joachim jochen johanna johannes jonas jörg joerg josef juergen jürgen julia julian
juliane karin karl karsten katharina kathrin katja katrin kerstin kevin kim klaus kristin lars
laura lea lena leon lisa lukas lutz manfred manuel manuela marc marcel marco marcus maren maria
marie marion mark markus martin martina mathias matthias max maximilian melanie michael michaela
mike miriam monika nadine nadja natalia natalie nicole nils nina norbert olaf oliver patrick paul
peter petra philip philipp ralf ralph ramona rebecca regina reinhard renate rene rené richard
robert roland rolf rüdiger ruediger sabine sabrina sandra sara sarah sascha sebastian silke
simon simone sonja stefan stefanie steffen stephan stephanie susanne sven tanja thomas thorsten
tim timo tobias tom torsten ulrich ulrike ursula uta ute uwe vanessa vera verena viktor volker
walter waltraud werner wilhelm wolfgang yvonne
mohamed mohammed ahmed ali fatima aisha omar hassan hussein ibrahim yusuf emre murat mehmet
ayse elif can deniz kemal mustafa
adam alice amanda amy andrew angela anthony ashley brian bruce carol charles chris christopher
daniela david deborah donald edward elizabeth emily emma eric frances gary george grace harry
helen henry jack jacob james jane jason jennifer jessica john jonathan joseph joshua karen
kate katherine kelly kenneth kevin kimberly laura linda lisa margaret mark mary matthew melissa
michelle nancy nathan nicholas oliver patricia rachel raymond rebecca richard robert ronald
ryan samantha samuel sandra sarah scott sharon stephen steven susan thomas timothy tyler
victoria william
alejandro ana antonio carlos carmen diego elena francesca francesco gabriel giovanni giulia
hugo ivan jose josé juan luca lucia luis marco mario marta miguel pablo paolo pedro rosa sofia
agnieszka aleksandra andrzej anna ewa jacek jan janusz katarzyna krzysztof lech maciej magdalena
malgorzata marek michal pawel piotr tomasz wojciech zofia
chen wei li ming yuki hiroshi kenji sakura anh linh minh ngoc thi van hai le nguyen tran
""".split())
ROLE_PATTERNS = [
    (re.compile(r"Gesch[äa]ftsf[üu]hr(?:er(?:in)?|ung)[:\s,]*(?:und Inhaber(?:in)?[:\s,]*)?" + NAME), "Geschäftsführer"),
    (re.compile(r"Inhaber(?:in)?[:\s,]*" + NAME), "Inhaber"),
    (re.compile(r"Gr[üu]nder(?:in)?(?:\s*(?:&|und)\s*(?:CEO|Gesch[äa]ftsf[üu]hrer(?:in)?))?[:\s,]*" + NAME), "Gründer"),
    (re.compile(r"[Vv]ertreten durch[:\s,]*" + NAME), "Vertretungsberechtigt"),
    (re.compile(NAME + r"\s*[,–\-|]\s*(?:Founder|Co-Founder|CEO|Owner|Gesch[äa]ftsf[üu]hrer(?:in)?|Inhaber(?:in)?|Gr[üu]nder(?:in)?)"), "Founder/CEO"),
    (re.compile(r"(?:Founder|Co-Founder|Owner|CEO)[:\s,]*" + NAME), "Founder/CEO"),
]
REGISTER_RE = re.compile(r"\b(HR[AB]\s?\d+(?:\s?[A-Z]{1,3})?)\b")
LINKEDIN_PERSONAL_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/in/[A-Za-z0-9_\-%]+")
PLACEHOLDER_RE = re.compile(
    r"under construction|coming soon|im aufbau|demn[äa]chst verf[üu]gbar|diese domain (?:kaufen|steht zum verkauf)|"
    r"domain ist (?:noch )?(?:frei|registriert)|sedo|parked|default web ?site page|hello world.*wordpress|"
    r"website (?:wird|befindet sich) (?:gerade )?(?:überarbeitet|im aufbau)", re.I)
NAME_STOPWORDS = re.compile(
    r"\b(GmbH|Gmb|mbH|UG|AG|KG|Str|Stra[ßs]e|Impressum|Kontakt|Amtsgericht|Registergericht|"
    r"Handelsregister|Sitz|Deutschland|Datenschutz|Telefon|Telefax|Website|Agentur|Marketing|"
    r"Design|Media|Consulting|Verantwortlich|Inhaltlich|Vertreten|Als|Der|Die|Das|Unser[e]?|"
    r"Ust|USt|Steuernummer|Postfach|Berlin|Hamburg|M[üu]nchen)\b"
    r"|\w+(?:stra[ßs]e|str)\b", re.I)
# extra stopwords when guessing a person from the BUSINESS NAME (solo practitioners)
BIZ_STOPWORDS = re.compile(
    r"\b(Coaching|Coach|Beratung|Praxis|Studio|Fitness|Wellness|Gesundheit(?:s\w*)?|Life|Balance|"
    r"Training(?:stherapie)?|Institut|Akademie|Zentrum|Team|Yoga|Massage|Kosmetik|Physiotherapie|"
    r"Ern[äa]hrung(?:sberatung)?|Personal|Business|Systemische?|Heilpraktiker(?:in)?|Naturheil\w*|"
    r"Mental|Entspannung(?:scoach|straining)?|Stressbew[äa]ltigung|Burnout\w*|Pr[äa]vention|"
    r"Werbeagentur|Werbetechnik|Webdesign|Best|Next|Level|Top|First|Smart|New|Your|The|And|Und|Für|"
    r"Raum|Haus|Club|Shop|Store|Service[s]?|Solutions|Group|Partner[s]?|International|Digital)\b", re.I)


BIZNAME = rf"((?:{_TOKEN}\.?\s){{1,5}}{_TOKEN})"  # wider window than NAME: descriptor + name


def name_from_linkedin(url):
    """Derive a person name from a LinkedIn slug: /in/sebastian-radtke-417962b3 -> 'Sebastian Radtke'.
    LinkedIn slugs are self-chosen by the actual profile owner, which makes them more reliable
    than regex-extracted page text (verified twice against real-world runs). Single-token slugs
    (e.g. /in/lehaininh) can't be split -> returns ''."""
    slug = url.rstrip("/").split("/")[-1]
    slug = re.sub(r"-[0-9a-f]{5,}$|-\d+$", "", slug)  # strip LinkedIn's numeric/hash suffix
    toks = [t for t in slug.split("-") if t.isalpha()]
    if 2 <= len(toks) <= 4 and all(2 <= len(t) <= 20 for t in toks):
        return " ".join(t.capitalize() for t in toks)
    return ""


def names_agree(a, b):
    """True if two person names share at least one substantial token."""
    ta = {t.lower() for t in re.findall(r"[A-Za-zÄÖÜäöüß]+", a or "") if len(t) > 2}
    tb = {t.lower() for t in re.findall(r"[A-Za-zÄÖÜäöüß]+", b or "") if len(t) > 2}
    return bool(ta & tb)


def reconcile_linkedin_name(lead):
    """The LinkedIn slug wins name conflicts (it belongs to the actual profile owner)."""
    li = lead.get("founder_linkedin", "")
    if not li:
        return
    slug_name = name_from_linkedin(li)
    fn = lead.get("founder_name", "")
    if slug_name and fn and not names_agree(fn, slug_name):
        lead["founder_name"] = slug_name
        lead["founder_role"] = lead.get("founder_role") or "Founder"
        lead["founder_source"] = "linkedin_slug"
        lead["_flags"] = sorted(set(lead.get("_flags", []) + ["founder_name_from_linkedin"]))
    elif slug_name and not fn:
        lead["founder_name"], lead["founder_role"] = slug_name, "Founder (LinkedIn)"
        lead["founder_source"] = "linkedin_slug"
    elif not slug_name and fn and lead.get("founder_source") not in ("impressum", "northdata"):
        # unsplittable slug + weakly-sourced name: keep both, flag for review
        lead["_flags"] = sorted(set(lead.get("_flags", []) + ["founder_linkedin_unconfirmed"]))


def founder_from_business_name(title):
    """Solo practitioners often trade under their own name ('Claudia Steimer',
    'Leitstern-Life Coaching Daniela Bäuml'). Extract a plausible person name from the
    business name: within each capitalized-token run, keep the segment AFTER the last
    business-word ('Hello Yoga Waltraud Selina Schirra' -> 'Waltraud Selina Schirra').
    Take the LAST valid candidate — names usually trail the descriptor."""
    best = ""
    for part in re.split(r"[|–—:•·,/]|\s-\s", str(title)):
        for m in re.finditer(BIZNAME, part.strip()):
            toks = [t.rstrip(".") for t in m.group(1).split()]
            stops = [i for i, t in enumerate(toks)
                     if BIZ_STOPWORDS.search(t) or NAME_STOPWORDS.search(t)]
            if stops:
                toks = toks[max(stops) + 1:]
            name = " ".join(toks)
            if 2 <= len(toks) <= 3 and name and not BIZ_STOPWORDS.search(name) \
                    and not NAME_STOPWORDS.search(name):
                best = name
    return best


def fetch(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "de,en"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if "text/html" not in r.headers.get("Content-Type", "text/html"):
                return ""
            return r.read(600_000).decode("utf-8", errors="replace")
    except Exception:
        return ""


def strip_html(html):
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</h\d>", "\n", html, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"[ \t]+", " ", text)


def find_founder(text):
    for pat, role in ROLE_PATTERNS:
        for m in pat.finditer(text):
            raw = next(g for g in m.groups() if g).strip()
            toks = [t.rstrip(".") for t in raw.split()]
            while toks and NAME_STOPWORDS.search(toks[-1]):   # greedy tail like "Telefon"
                toks.pop()
            while toks and NAME_STOPWORDS.search(toks[0]):
                toks.pop(0)
            name = " ".join(toks)
            if 2 <= len(toks) <= 4 and not NAME_STOPWORDS.search(name):
                return name, role
    return "", ""


def process(lead):
    # Cheapest source first: North Data representatives (already fetched, authoritative)
    reps = (lead.get("northdata") or {}).get("representatives") or []
    if reps and isinstance(reps, list):
        r0 = reps[0] if isinstance(reps[0], dict) else {}
        nm = r0.get("name") or (r0.get("person") or {}).get("name")
        if isinstance(nm, dict):
            nm = nm.get("name")
        if nm:
            lead["founder_name"], lead["founder_role"], lead["founder_source"] = nm, "Geschäftsführer", "northdata"
    site = (lead.get("website") or "").strip()
    if not site:
        if not lead.get("founder_name"):
            guess = founder_from_business_name(lead.get("title") or lead.get("name") or "")
            if guess and guess.split()[0].lower() in FIRST_NAMES:
                lead["founder_name"], lead["founder_role"] = guess, "Inhaber (assumed from business name)"
                lead["founder_source"] = "business_name"
            elif guess:
                lead["founder_candidate"] = guess
        reconcile_linkedin_name(lead)
        return lead
    if not site.startswith("http"):
        site = "https://" + site
    base = f"{urllib.parse.urlparse(site).scheme}://{urllib.parse.urlparse(site).netloc}"
    for path in PAGES:
        html = fetch(base + path if path else site)
        if not html:
            continue
        text = strip_html(html)
        if path == "" or path == "/impressum":
            if not lead.get("_site_excerpt"):
                lead["_site_excerpt"] = re.sub(r"\s+", " ", text)[:1500]
            if path == "" and PLACEHOLDER_RE.search(text[:3000]) and len(text.strip()) < 2500:
                lead["_flags"] = sorted(set(lead.get("_flags", []) + ["placeholder_website"]))
        if not lead.get("register_id_website"):
            m = REGISTER_RE.search(text)
            if m:
                lead["register_id_website"] = m.group(1)
        if not lead.get("founder_linkedin"):
            m = LINKEDIN_PERSONAL_RE.search(html)
            if m:
                lead["founder_linkedin"] = m.group(0)
        if not lead.get("founder_name"):
            name, role = find_founder(text)
            if name:
                lead["founder_name"], lead["founder_role"] = name, role
                lead["founder_source"] = (path or "/").strip("/") or "homepage"
        if lead.get("founder_name") and lead.get("register_id_website") and lead.get("founder_linkedin"):
            break
    if not lead.get("founder_name"):
        guess = founder_from_business_name(lead.get("title") or lead.get("name") or "")
        if guess and guess.split()[0].lower() in FIRST_NAMES:
            # validated: first token is a known first name -> confident it's a person
            lead["founder_name"] = guess
            lead["founder_role"] = "Inhaber (assumed from business name)"
            lead["founder_source"] = "business_name"
        elif guess:
            # unvalidated guess: record as candidate only — NEVER counts as a founder
            lead["founder_candidate"] = guess
    reconcile_linkedin_name(lead)
    return lead


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--workers", type=int, default=8)
    args = p.parse_args()

    with open(args.input, encoding="utf-8") as f:
        leads = json.load(f)
    todo = [i for i, l in enumerate(leads) if not l.get("founder_name")]
    print(f"{len(leads)} leads; hunting founders on {len(todo)} …")

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(process, leads[i]): i for i in todo}
        done = 0
        for fut in concurrent.futures.as_completed(futures):
            leads[futures[fut]] = fut.result()
            done += 1
            if done % 10 == 0 or done == len(todo):
                print(f"  {done}/{len(todo)}")

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(leads, f, ensure_ascii=False, indent=1)
    found = sum(1 for l in leads if l.get("founder_name"))
    placeholders = sum(1 for l in leads if "placeholder_website" in l.get("_flags", []))
    print(f"Done → {args.output}. Founders identified: {found}/{len(leads)}; "
          f"placeholder websites flagged: {placeholders}.")
    print("Leads without a founder will be dropped by pipeline.py --require-founder.")


if __name__ == "__main__":
    main()
