"""Shared key loading: env vars first, then the persisted ~/.claude/lead-scraper.env file.

Every script imports and calls load_env() before reading keys, so users set keys once
(paste in chat -> saved to the file) and never again — bash calls don't share state,
so a persisted file is the only reliable cross-call mechanism.
"""
import os

ENV_FILE = os.path.expanduser("~/.claude/lead-scraper.env")

KEYS = {
    "APIFY_TOKEN": "Apify (deep Google Maps + 100-actor catalog) — console.apify.com → Settings → API & Integrations",
    "SERPER_API_KEY": "Serper (cheap discovery + email search) — serper.dev, 2,500 free credits, no card",
    "MILLIONVERIFIER_API_KEY": "MillionVerifier (SMTP email verification, ~$0.0007/email) — app.millionverifier.com",
    "NORTHDATA_API_KEY": "OPTIONAL paid North Data API — NOT needed; the skill uses free public North Data info by default",
    "GOOGLE_SERVICE_ACCOUNT_FILE": "Path to Google service-account JSON key (for the master Google Sheet)",
    "GSHEET_ID": "Master Google Sheet spreadsheet ID (from its URL)",
    "GSHEET_GID": "Master sheet tab gid (from the URL after gid=)",
}


def load_env():
    """Populate os.environ from the persisted env file (env vars take precedence)."""
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def save_key(name, value):
    """Persist one key to the env file (0600), replacing any existing entry."""
    os.makedirs(os.path.dirname(ENV_FILE), exist_ok=True)
    lines = []
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, encoding="utf-8") as f:
            lines = [l for l in f.read().splitlines() if not l.startswith(f"{name}=")]
    lines.append(f"{name}={value}")
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(ENV_FILE, 0o600)


def status():
    """Print one line per key: set / missing, with how to get it."""
    load_env()
    for k, hint in KEYS.items():
        print(f"{'SET    ' if os.environ.get(k) else 'MISSING'} {k} — {hint}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3:  # env_loader.py KEY VALUE -> save
        if sys.argv[1] not in KEYS:
            sys.exit(f"Unknown key {sys.argv[1]}; expected one of {', '.join(KEYS)}")
        save_key(sys.argv[1], sys.argv[2])
        print(f"Saved {sys.argv[1]} to {ENV_FILE} (chmod 600) — won't ask again.")
    else:
        status()
